"""
tests/unit/test_resilience_timeout.py
══════════════════════════════════════

Regression test for the wall-clock timeout enforcement in
`src.core.resilience._run_with_timeout`.

Historical bug (RCA'd on branch long-term-cache):
  Prior implementation used `with ThreadPoolExecutor(max_workers=1) as ex:`.
  When the futures.result() timeout fired, the `with` block exit called
  `shutdown(wait=True)` which blocked until the worker thread actually
  finished. If the worker was inside a slow SDK call, the "timeout" wouldn't
  actually abort — it just delayed the TimeoutError until the SDK returned.
  Observed impact: OpenAI slowness caused 5-6 minute hangs despite a 40s
  policy timeout.

Fix: switch to manual `try / finally: ex.shutdown(wait=False, cancel_futures=True)`
so the caller unblocks immediately.

Invariant under test:
  _run_with_timeout(fn, ..., timeout_sec=T) must raise TimeoutError within
  T + a small overhead budget, even when `fn` sleeps for much longer than T.
"""

import time

import pytest

from src.core.resilience import _run_with_timeout


def _slow_fn(sleep_sec: float) -> str:
    """A function that sleeps deliberately longer than the timeout."""
    time.sleep(sleep_sec)
    return "should never see this"


def test_run_with_timeout_aborts_within_budget():
    """
    _run_with_timeout(timeout_sec=1) must raise TimeoutError in ~1s
    even though the underlying fn sleeps for 10s. Historical bug would
    have blocked the caller for the full 10s.
    """
    timeout_sec = 1.0
    slack_sec = 1.5  # generous overhead budget for Python thread scheduling

    started = time.perf_counter()
    with pytest.raises(TimeoutError):
        _run_with_timeout(_slow_fn, (10.0,), {}, timeout_sec)
    elapsed = time.perf_counter() - started

    assert elapsed < timeout_sec + slack_sec, (
        f"_run_with_timeout blocked for {elapsed:.2f}s; expected < "
        f"{timeout_sec + slack_sec:.2f}s. The context-manager shutdown-wait "
        f"regression may have returned."
    )


def test_run_with_timeout_returns_result_when_fn_fast():
    """
    _run_with_timeout must return the function's result when the call
    completes inside the timeout budget.
    """

    def _fast_fn(value: int) -> int:
        return value * 2

    result = _run_with_timeout(_fast_fn, (21,), {}, timeout_sec=5.0)
    assert result == 42


def test_run_with_timeout_propagates_underlying_exception():
    """
    If the wrapped function raises a non-timeout exception, that exception
    must propagate up unchanged (not be swallowed by the timeout wrapper).
    """

    class CustomError(RuntimeError):
        pass

    def _raiser():
        raise CustomError("boom")

    with pytest.raises(CustomError, match="boom"):
        _run_with_timeout(_raiser, (), {}, timeout_sec=5.0)


def test_run_with_timeout_does_not_leak_thread_pool():
    """
    Each call must create and dispose of its own ThreadPoolExecutor. This
    is a mild proxy check — we can't easily inspect the shutdown state
    of an ex we no longer have a reference to, so we assert two things:
      (1) many successive timeout calls don't cause resource exhaustion
      (2) the total elapsed time scales linearly with number-of-calls
          (i.e. successive calls aren't serializing behind a stuck worker)
    """
    per_call_timeout = 0.3
    n_calls = 5

    started = time.perf_counter()
    for _ in range(n_calls):
        with pytest.raises(TimeoutError):
            _run_with_timeout(_slow_fn, (10.0,), {}, per_call_timeout)
    elapsed = time.perf_counter() - started

    # Each call should take ~per_call_timeout; N calls should sum roughly to
    # N * per_call_timeout, NOT (per_call_timeout + 10 * N) which would
    # indicate we're serializing on stuck workers.
    linear_budget = n_calls * per_call_timeout + 2.0  # 2s slack for scheduling
    assert elapsed < linear_budget, (
        f"{n_calls} timeout calls took {elapsed:.2f}s; expected < "
        f"{linear_budget:.2f}s. Successive calls appear to be waiting on "
        f"the previous stuck worker — the shutdown-wait bug may have returned."
    )
