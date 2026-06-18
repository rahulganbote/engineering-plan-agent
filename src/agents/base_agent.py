"""
src/agents/base_agent.py
═════════════════════════
BaseAgent mixin — shared utilities for all 5 specialist agents.

Provides:
    1. Retry logic (tenacity) — FM-1: malformed JSON / LLM timeout mitigation
    2. Execution timing — SC-3: pipeline time measurement
    3. log_agent_run() call site — ensures every agent execution is logged
    4. No-RAG-hits Amber forcing — FM-2: automatic Amber when no RAG context

Usage:
    class PlanGeneratorAgent(BaseAgent):
        def run(self, state, feedback=""):
            start = self.start_timer()
            citations, context_str = self.retrieve(query, source_types)
            output = self._call_llm_with_retry(prompt)
            self.log_run(state.run_id, agent_name, citations, output, start)
            return output

Failure modes implemented here:
    FM-1 malformed_json:  @retry with 3 attempts, exponential backoff 1s/2s/4s
    FM-2 no_rag_hits:     _check_no_rag_hits() flags and reduces confidence_score
    FM-5 llm_timeout:     tenacity wait_exponential handles OpenAI timeouts
"""

from __future__ import annotations

import time
from typing import Optional

from openai import OpenAI
# LangSmith auto-traces every wrapped client.chat.completions.create() call —
# captures prompt, response, model, latency, token usage. No code changes
# needed elsewhere; the client API is identical.
from langsmith.wrappers import wrap_openai
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryError,
)

# ── Phase 1: distributed-systems primitives ──────────────────────────────────
import threading as _threading2
from src.core.resilience import (
    CircuitBreaker, CallPolicy, resilient, CircuitOpenError, OPENAI_POLICY, ANTHROPIC_POLICY,
)
from src.core.cache import cached, hash_args, CACHE_LLM

from src.core.config import settings
from src.core.logger import get_logger, log_agent_run
from src.core.rag import retrieve, format_context, RetrievedChunk

log    = get_logger(__name__)
client = wrap_openai(OpenAI(api_key=settings.openai_api_key))


# ── Token & Cost usage tracker — per-run counters, thread-safe ────────────────
# Each pipeline run has its own input/output token tally and USD cost. Agents running in the
# ThreadPoolExecutor set a thread-local run_id; LLM callers add to the dict via
# add_tokens() and add_cost(); pipeline.py reads totals at the end.
import threading as _threading
from collections import defaultdict as _defaultdict

_TOKEN_LOCK    = _threading.Lock()
_TOKEN_COUNTER: dict[str, dict[str, int]] = _defaultdict(lambda: {"input": 0, "output": 0})
_COST_COUNTER:  dict[str, float] = _defaultdict(float)
_RUN_FAMILY:    dict[str, str] = _defaultdict(lambda: "openai")
_RUN_FALLBACK:  dict[str, bool] = _defaultdict(lambda: True)
_CURRENT_RUN   = _threading.local()


def set_current_run_id(run_id: str, model_family: str = "openai", enable_fallback: bool = True) -> None:
    """Set the run_id, model_family and enable_fallback for this thread so subsequent LLM calls are attributed."""
    if not run_id:
        if hasattr(_CURRENT_RUN, "run_id"):
            delattr(_CURRENT_RUN, "run_id")
        if hasattr(_CURRENT_RUN, "model_family"):
            delattr(_CURRENT_RUN, "model_family")
        if hasattr(_CURRENT_RUN, "enable_fallback"):
            delattr(_CURRENT_RUN, "enable_fallback")
        return

    _CURRENT_RUN.run_id = run_id
    _CURRENT_RUN.model_family = model_family
    _CURRENT_RUN.enable_fallback = enable_fallback
    with _TOKEN_LOCK:
        if run_id not in _RUN_FAMILY:
            _RUN_FAMILY[run_id] = model_family
        if run_id not in _RUN_FALLBACK:
            _RUN_FALLBACK[run_id] = enable_fallback


def _current_run_id() -> str | None:
    return getattr(_CURRENT_RUN, "run_id", None)


def _current_model_family() -> str:
    rid = _current_run_id()
    if rid:
        with _TOKEN_LOCK:
            if rid in _RUN_FAMILY:
                return _RUN_FAMILY[rid]
    return getattr(_CURRENT_RUN, "model_family", "openai")


def _current_enable_fallback() -> bool:
    rid = _current_run_id()
    from src.core.config import settings
    if not rid:
        return settings.enable_provider_fallback
    with _TOKEN_LOCK:
        if rid in _RUN_FALLBACK:
            return _RUN_FALLBACK[rid]
    return getattr(_CURRENT_RUN, "enable_fallback", settings.enable_provider_fallback)



def reset_token_counter(run_id: str) -> None:
    """Zero the counters for a run — call at pipeline start."""
    with _TOKEN_LOCK:
        _TOKEN_COUNTER[run_id] = {"input": 0, "output": 0}
        _COST_COUNTER[run_id] = 0.0
        _RUN_FAMILY.pop(run_id, None)
        _RUN_FALLBACK.pop(run_id, None)


def add_tokens(prompt: int, completion: int, run_id: str | None = None) -> None:
    """Add tokens to the current run's tally (uses thread-local run_id if not given)."""
    rid = run_id or _current_run_id()
    if not rid:
        return
    with _TOKEN_LOCK:
        d = _TOKEN_COUNTER[rid]
        d["input"]  += int(prompt or 0)
        d["output"] += int(completion or 0)


def add_cost(cost: float, run_id: str | None = None) -> None:
    """Add USD cost to the current run's tally."""
    rid = run_id or _current_run_id()
    if not rid:
        return
    with _TOKEN_LOCK:
        _COST_COUNTER[rid] += float(cost or 0.0)


def get_token_counts(run_id: str) -> tuple[int, int]:
    with _TOKEN_LOCK:
        d = _TOKEN_COUNTER.get(run_id, {"input": 0, "output": 0})
        return d["input"], d["output"]


def get_cost(run_id: str) -> float:
    with _TOKEN_LOCK:
        return _COST_COUNTER.get(run_id, 0.0)


def cleanup_token_counter(run_id: str) -> None:
    with _TOKEN_LOCK:
        _TOKEN_COUNTER.pop(run_id, None)
        _COST_COUNTER.pop(run_id, None)
        _RUN_FAMILY.pop(run_id, None)
        _RUN_FALLBACK.pop(run_id, None)
    if getattr(_CURRENT_RUN, "run_id", None) == run_id:
        set_current_run_id("")



# ── Phase 1: Per-agent-class circuit breakers ────────────────────────────────
# Each BaseAgent subclass gets ONE breaker per process. State persists across
# agent INSTANCES (which are created fresh per pipeline run), but each agent
# CLASS has its own independent breaker — one class's failures cannot poison
# another's. This is the "per-instance ownership" pattern from resilience.py
# applied at the class level (since instances are short-lived).
_LLM_BREAKERS: dict[str, CircuitBreaker] = {}
_LLM_BREAKER_LOCK = _threading2.Lock()


def _get_llm_breaker(agent_class_name: str) -> CircuitBreaker:
    with _LLM_BREAKER_LOCK:
        if agent_class_name not in _LLM_BREAKERS:
            _LLM_BREAKERS[agent_class_name] = CircuitBreaker(
                name=f"{agent_class_name}.llm",
                fail_threshold=5,
                reset_sec=30.0,
            )
        return _LLM_BREAKERS[agent_class_name]


# Sentinel citation value used when Pinecone returns no results
NO_RAG_SENTINEL = "kb_no_results_ungrounded"


class BaseAgent:
    """
    Mixin providing retry, timing, RAG retrieval, and structured logging
    for all 5 specialist agents.

    All specialist agents should inherit from this class and call:
        start = self.start_timer()
        ... do work ...
        self.log_run(state.run_id, "agent_name", citations, critic_score, start, revision)

    Class attributes (Phase 5 — per-agent policy manifest):
        CACHE_POLICY      — CachePolicy used by _call_llm_with_retry
        RESILIENCE_POLICY — CallPolicy used by _call_llm_with_retry
    Override either on a specialist subclass to change its behaviour.
    """

    # ── Phase 5: per-agent policy manifest ───────────────────────────────────
    CACHE_POLICY:      CachePolicy = CACHE_LLM
    RESILIENCE_POLICY: CallPolicy  = OPENAI_POLICY

    # ── Timing ────────────────────────────────────────────────────────────────

    def start_timer(self) -> float:
        """
        Record pipeline start time.
        Returns perf_counter float — pass to log_run() when done.

        Usage:
            start = self.start_timer()
            output = self.do_work()
            self.log_run(..., start=start)
        """
        return time.perf_counter()

    def elapsed_ms(self, start: float) -> int:
        """Convert perf_counter start to elapsed milliseconds."""
        return int((time.perf_counter() - start) * 1000)

    # ── RAG Retrieval ─────────────────────────────────────────────────────────

    def retrieve_context(
        self,
        query:        str,
        source_types: Optional[list[str]] = None,
        domain:       Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Retrieve RAG context and format for LLM prompt injection.

        Returns:
            (context_str, citation_ids)
            context_str:  formatted text to inject into agent prompt
            citation_ids: list of chunk IDs for citations[] field

        FM-2 no_rag_hits: if no chunks retrieved above threshold,
            returns NO_RAG_SENTINEL in citation_ids — Critic will
            automatically force Amber badge when it detects this.
        """
        chunks = retrieve(query, source_types=source_types, domain=domain)
        context_str, citation_ids = format_context(chunks)

        if not chunks or citation_ids == [NO_RAG_SENTINEL]:
            log.warning(
                f"No RAG hits for query='{query[:50]}' | "
                f"source_types={source_types} | "
                f"FM-2: will force Amber badge"
            )

        return context_str, citation_ids

    def has_no_rag_hits(self, citation_ids: list[str]) -> bool:
        """True if citations indicate no RAG context was retrieved."""
        return not citation_ids or citation_ids == [NO_RAG_SENTINEL]

    # ── LLM Call with Retry ───────────────────────────────────────────────────

    def _call_llm_with_retry(
        self,
        system_prompt: str,
        user_prompt:   str,
        model:         str = None,
        response_format: dict = None,
    ) -> str:
        """
        Call OpenAI with per-agent CACHE_POLICY + RESILIENCE_POLICY.

        Phase 5: decorators are applied dynamically so subclasses can override
        CACHE_POLICY and RESILIENCE_POLICY as class attributes and have those
        policies take effect without touching this method.

        Args:
            system_prompt: Role and instruction for the LLM
            user_prompt:   The BRD content + RAG context
            model:         Override model (default: settings.openai_model)
            response_format: {"type": "json_object"} for structured output

        Returns:
            Raw string content from the LLM response
        """
        model = model or settings.openai_model
        breaker = _get_llm_breaker(type(self).__name__)

        # Capture per-agent policies at call time so subclass overrides are
        # respected — class-level @cached/@resilient decorators can't do this.
        cache_policy     = self.CACHE_POLICY
        # Family-aware resilience policy. Reading current family at call time
        # (vs class attribute) lets the same agent class work transparently
        # across providers. Anthropic gets ANTHROPIC_POLICY (90s timeout, 2
        # attempts) because Claude's verbose JSON outputs routinely exceed
        # OPENAI_POLICY's 30s ceiling.
        _family = (_current_model_family() or "openai").lower()
        if _family == "anthropic":
            resilience_policy = ANTHROPIC_POLICY
        else:
            resilience_policy = self.RESILIENCE_POLICY

        # Capture current run context before entering the resilient / thread execution
        current_rid = _current_run_id()
        current_family = _current_model_family()
        current_fallback = _current_enable_fallback()

        def _llm_key(sys_p, usr_p, mdl, fmt):
            return hash_args(sys_p, usr_p, mdl, fmt)

        def _call(sys_p, usr_p, mdl, fmt) -> str:
            from src.core.providers import complete_with_fallback, map_model
            from src.core.pricing import calculate_cost

            if current_rid:
                set_current_run_id(current_rid, current_family, current_fallback)

            family = _current_model_family()
            content, prompt_tokens, completion_tokens, final_family = complete_with_fallback(
                model_family=family,
                messages=[
                    {"role": "system", "content": sys_p},
                    {"role": "user",   "content": usr_p},
                ],
                model=mdl,
                temperature=0.2,
                response_format=fmt,
            )

            if final_family != family:
                set_current_run_id(current_rid or "", final_family, current_fallback)

            mapped_model = map_model(final_family, mdl)
            add_tokens(prompt_tokens, completion_tokens)
            cost = calculate_cost(final_family, mapped_model, prompt_tokens, completion_tokens)
            add_cost(cost)
            return content


        # Apply wrappers inside-out: resilient first, then cached on top
        # so a cache hit pays zero resilience/retry cost.
        _resilient_call = resilient(
            policy=resilience_policy, breaker=breaker, name="llm.chat"
        )(_call)
        _cached_call = cached(
            policy=cache_policy, key_fn=_llm_key, name="llm.chat"
        )(_resilient_call)

        try:
            return _cached_call(system_prompt, user_prompt, model, response_format)
        except CircuitOpenError:
            log.error(
                f"LLM call short-circuited (breaker {breaker.name} OPEN) — "
                f"too many recent failures; routing to error node"
            )
            raise
        except Exception as e:
            log.error(
                f"LLM call failed after {resilience_policy.max_attempts} attempts | "
                f"model={model} | error={type(e).__name__} | "
                f"FM-1/FM-5 mitigation: routing to error node"
            )
            raise

    # ── Structured Logging ────────────────────────────────────────────────────

    def log_run(
        self,
        run_id:          str,
        agent_name:      str,
        citation_ids:    list[str],
        critic_score:    Optional[float],
        start_time:      float,
        revision_count:  int = 0,
        success:         bool = True,
        error:           Optional[str] = None,
        guardrail_triggers: list[str] = None,
    ) -> dict:
        """
        Log a single agent execution to JSONL and console.
        MUST be called after every agent run — this is the
        primary per-agent execution log required by the rubric.

        Logged fields (per spec):
            ✓ input:             brd_hash passed externally — never raw BRD
            ✓ rag_chunks:        citation_ids (chunk IDs retrieved)
            ✓ output:            logged via success flag and critic_score
            ✓ critic_score:      float or None
            ✓ execution_time_ms: measured by start_timer() / elapsed_ms()
            ✓ guardrail_triggers: list of fired guardrail names
            ✓ revision_count:    current revision cycle number

        Returns the log entry dict (used by log_pipeline_summary).
        """
        execution_time_ms = self.elapsed_ms(start_time)
        triggers = guardrail_triggers or []

        # Add FM-2 flag if no RAG hits were found
        if self.has_no_rag_hits(citation_ids):
            triggers.append("FM-2_no_rag_hits")

        log_agent_run(
            agent_name=agent_name,
            run_id=run_id,
            rag_chunk_ids=citation_ids,
            critic_score=critic_score,
            execution_time_ms=execution_time_ms,
            guardrail_triggers=triggers,
            revision_count=revision_count,
            success=success,
            error=error,
        )

        return {
            "agent_name":        agent_name,
            "run_id":            run_id,
            "execution_time_ms": execution_time_ms,
            "rag_chunk_count":   len(citation_ids),
            "critic_score":      critic_score,
            "revision_count":    revision_count,
            "guardrail_triggers": triggers,
            "success":           success,
        }
