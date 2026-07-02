"""
src/core/resilience.py
═════════════════════════════════════════════════════════════════════════════
Distributed-systems primitives for any external service call.

Provides: timeout enforcement, retry with jittered exponential backoff, and
optional circuit breaker. Composes with `src/core/cache.py` - cache hits skip
the resilience layer entirely.

Design principles
─────────────────
1. Types and tools only - NO global mutable state. The module exports classes,
   dataclasses, and a decorator factory. No shared breakers, no global counters.
2. Per-instance ownership - each caller (agent, integration) constructs its OWN
   CircuitBreaker. One agent's failures cannot poison another agent's calls.
3. Frozen policies - CallPolicy is an immutable dataclass. Callers may copy and
   modify, but no one mutates a shared default. This is what keeps the layer
   safe in a distributed/concurrent setting.

Usage
─────
    class PlanGenerator(BaseAgent):
        # Each agent OWNS its breaker and its policy
        _llm_breaker = CircuitBreaker(name="plan.llm", fail_threshold=5, reset_sec=40)

        @resilient(policy=OPENAI_POLICY, breaker=_llm_breaker)
        def _call_openai(self, sys, usr):
            return client.chat.completions.create(...)
"""

from __future__ import annotations

import functools
import random
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from enum import Enum

from src.core.events import emit as _emit
from src.core.logger import get_logger

log = get_logger(__name__)


# ── Policies ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CallPolicy:
    """
    Frozen policy for a call site. Callers may construct their own; defaults
    below are sensible starting points for OpenAI / Pinecone / generic HTTP.
    """

    timeout_sec: float = 40.0
    max_attempts: int = 3  # 1 initial attempt + (max_attempts-1) retries
    backoff_min: float = 1.0  # seconds - base for exponential backoff
    backoff_max: float = 8.0  # seconds - clamp
    jitter: bool = True  # ±50% randomization to avoid retry stampedes
    retry_on: tuple = (Exception,)  # retry only on these exception types
    do_not_retry: tuple = ()  # NEVER retry on these (e.g. AuthError)
    enforce_timeout: bool = True  # If False, rely on the underlying SDK


from src.core.exceptions import QuotaExceededError


OPENAI_POLICY = CallPolicy(
    timeout_sec=40.0, max_attempts=3, backoff_min=1.0, backoff_max=8.0, do_not_retry=(QuotaExceededError,)
)
# Anthropic's Claude models routinely take 50-120s for verbose JSON outputs.
# Giving each attempt 90s and using 2 attempts (vs OpenAI's 3) avoids the
# 40s x 3 = 120s wall-clock loss that triggered the cascading bulkhead trip we
# saw in runs 1c82f453-137b and 1c82f453-e588. Backoff is the same shape.
ANTHROPIC_POLICY = CallPolicy(
    timeout_sec=120.0, max_attempts=2, backoff_min=2.0, backoff_max=8.0, do_not_retry=(QuotaExceededError,)
)
PINECONE_POLICY = CallPolicy(
    timeout_sec=10.0, max_attempts=2, backoff_min=0.5, backoff_max=2.0, do_not_retry=(QuotaExceededError,)
)
EMBEDDING_POLICY = CallPolicy(
    timeout_sec=15.0, max_attempts=3, backoff_min=0.5, backoff_max=4.0, do_not_retry=(QuotaExceededError,)
)
HTTP_POLICY = CallPolicy(
    timeout_sec=10.0, max_attempts=2, backoff_min=0.5, backoff_max=2.0, do_not_retry=(QuotaExceededError,)
)
TAVILY_POLICY = CallPolicy(
    timeout_sec=5.0, max_attempts=3, backoff_min=0.5, backoff_max=2.0, do_not_retry=(QuotaExceededError,)
)
GITHUB_POLICY = CallPolicy(
    timeout_sec=3.0, max_attempts=2, backoff_min=0.5, backoff_max=1.0, do_not_retry=(QuotaExceededError,)
)


# ── Circuit breaker ──────────────────────────────────────────────────────────


class BreakerState(str, Enum):
    CLOSED = "closed"  # normal operation
    OPEN = "open"  # failing; short-circuit calls
    HALF_OPEN = "half_open"  # cooldown elapsed; let one probe through


class CircuitOpenError(Exception):
    """Raised when a call is short-circuited by an open breaker."""


@dataclass
class CircuitBreaker:
    """
    Per-instance state. Each owner constructs its own - no shared state.

    Behavior:
      • CLOSED → record_failure() N times → OPEN
      • OPEN   → after reset_sec, the next is_open() check transitions to HALF_OPEN
      • HALF_OPEN → next call is the probe: success → CLOSED, failure → OPEN
    """

    name: str
    fail_threshold: int = 5
    reset_sec: float = 40.0
    _state: BreakerState = field(default=BreakerState.CLOSED, init=False)
    _fail_count: int = field(default=0, init=False)
    _opened_at: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def is_open(self) -> bool:
        with self._lock:
            if self._state == BreakerState.OPEN:
                if time.monotonic() - self._opened_at >= self.reset_sec:
                    self._state = BreakerState.HALF_OPEN
                    log.info(f"[breaker:{self.name}] half-open - allowing probe")
                    return False
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state == BreakerState.HALF_OPEN:
                log.info(f"[breaker:{self.name}] probe succeeded → CLOSED")
            self._state = BreakerState.CLOSED
            self._fail_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._fail_count += 1
            if self._state == BreakerState.HALF_OPEN:
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
                log.warning(f"[breaker:{self.name}] probe failed → OPEN")
            elif self._fail_count >= self.fail_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
                log.warning(
                    f"[breaker:{self.name}] OPEN after {self._fail_count} consecutive "
                    f"failures (cooldown {self.reset_sec}s)"
                )
                _emit("breaker_open", breaker=self.name, fails=self._fail_count, reset_sec=self.reset_sec)

    def state(self) -> str:
        return self._state.value


# ── Decorator ────────────────────────────────────────────────────────────────


def resilient(
    policy: CallPolicy = HTTP_POLICY,
    breaker: CircuitBreaker | None = None,
    name: str = "",
):
    """
    Wrap a callable with timeout + retry-with-jitter + optional breaker.

    Returns the unwrapped result on success, propagates the last exception on
    exhaustion or CircuitOpenError if short-circuited.
    """

    def decorator(fn: Callable) -> Callable:
        call_name = name or fn.__name__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if breaker is not None and breaker.is_open():
                log.info(f"[{call_name}] short-circuited - breaker OPEN")
                _emit("breaker_short_circuit", call=call_name, breaker=breaker.name)
                raise CircuitOpenError(f"breaker {breaker.name} is open")

            last_exc: BaseException | None = None
            for attempt in range(1, policy.max_attempts + 1):
                try:
                    if policy.enforce_timeout and policy.timeout_sec > 0:
                        result = _run_with_timeout(fn, args, kwargs, policy.timeout_sec)
                    else:
                        result = fn(*args, **kwargs)
                    if breaker is not None:
                        breaker.record_success()
                    return result
                except BaseException as e:
                    # NEVER retry on these (e.g. AuthError → no point)
                    if policy.do_not_retry and isinstance(e, policy.do_not_retry):
                        if breaker is not None:
                            breaker.record_failure()
                        raise
                    # Only retry on the allowed exception types
                    if not isinstance(e, policy.retry_on):
                        if breaker is not None:
                            breaker.record_failure()
                        raise
                    last_exc = e
                    if attempt < policy.max_attempts:
                        wait_sec = _backoff(attempt, policy.backoff_min, policy.backoff_max, policy.jitter)
                        log.info(
                            f"[{call_name}] attempt {attempt}/{policy.max_attempts} failed "
                            f"({type(e).__name__}); retrying in {wait_sec:.2f}s"
                        )
                        _emit(
                            "retry",
                            call=call_name,
                            attempt=attempt,
                            max_attempts=policy.max_attempts,
                            exception=type(e).__name__,
                            wait_sec=round(wait_sec, 2),
                        )
                        time.sleep(wait_sec)

            # All attempts exhausted
            if breaker is not None:
                breaker.record_failure()
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator


# ── Internals ────────────────────────────────────────────────────────────────


def _run_with_timeout(fn, args, kwargs, timeout_sec: float):
    """Hard wall-clock timeout via a single-shot worker thread."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args, **kwargs)
        try:
            return future.result(timeout=timeout_sec)
        except FutureTimeout as e:
            raise TimeoutError(f"call exceeded {timeout_sec}s") from e


def _backoff(attempt: int, min_sec: float, max_sec: float, jitter: bool) -> float:
    """Exponential backoff (capped) with optional ±50% jitter."""
    base = min(max_sec, min_sec * (2 ** (attempt - 1)))
    if jitter:
        return base * (0.5 + random.random())  # range: 0.5×–1.5× of base
    return base
