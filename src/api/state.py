"""
src/api/state.py
════════════════
In-memory run storage and telemetry push helper.
"""

from __future__ import annotations

import json
import time

from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)

# ── In-memory run store ───────────────────────────────────────────────────────
_runs: dict[str, PipelineState] = {}
_run_events: dict[str, list[str]] = {}
_run_export: dict[str, dict] = {}  # run_id → {sheet_url, status, error}
_run_owner: dict[str, str] = {}  # run_id → user_email
# Cooperative cancellation flags. POST /runs/{run_id}/cancel sets True here;
# the pipeline checks the flag inside _set_status between LangGraph nodes and
# raises RunCanceledError. Not thread-safe by design - single-process in-memory
# store, one bit per run, race is benign (worst case: one extra LLM call runs).
_run_cancel_flags: dict[str, bool] = {}


def _push_event(run_id: str, data: dict) -> None:
    if run_id not in _run_events:
        _run_events[run_id] = []
    log.info(f"[_push_event] run_id={run_id} type={data.get('type')} data={data}")
    try:
        seq = len(_run_events[run_id])
        payload = {**data, "seq": seq, "ts": time.time()}
        _run_events[run_id].append(json.dumps(payload))
    except Exception as e:
        log.error(f"[_push_event] failed to serialize: {e}")
