"""
src/core/events.py
═══════════════════════════════════════════════════════════════════════════
Lightweight event-emission bus for the resilience and cache layers.

Both `src/core/cache.py` and `src/core/resilience.py` emit structured events
(cache_hit, cache_miss, breaker_open, retry, etc.) through this module. The
FastAPI app installs a sink at startup that forwards events into the existing
per-run event stream (visible in the React UI raw event log).

Design
──────
• A single optional sink callback. Default = no-op.
• Emitters NEVER raise — observability must not break the call site.
• Best-effort attaches the current thread's run_id so events correlate to a run.
• If the sink isn't installed (e.g. local script outside FastAPI), events are
  silently dropped. Same code runs everywhere.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

_sink: Callable[[dict], None] | None = None


def set_event_sink(fn: Callable[[dict], None]) -> None:
    """Install the global event sink. Call once at app startup."""
    global _sink
    _sink = fn


def emit(event_type: str, **fields: Any) -> None:
    """
    Emit a structured event. Never raises. No-op if no sink is installed.

    The sink receives a single dict with keys:
        {"type": event_type, "run_id": <thread-local run_id or None>, **fields}
    """
    sink = _sink
    if sink is None:
        return
    try:
        # Best-effort: pick up the current run_id from base_agent's thread-local
        try:
            from src.agents.base_agent import _current_run_id  # type: ignore

            rid = _current_run_id()
        except Exception:
            rid = None
        sink({"type": event_type, "run_id": rid, **fields})
    except Exception:
        # Observability MUST NOT break the caller. Swallow.
        pass
