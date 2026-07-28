"""
src/api/routes/runs.py
══════════════════════
Pipeline execution, status streaming, and event log routes.
"""

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_current_user_email, verify_run_ownership
from src.api.limiter import is_rate_limit_exempt, limiter
from src.api.models import PipelineRunResponse
from src.api.state import _run_cancel_flags, _run_events, _run_export, _run_owner, _runs
from src.api.tasks import _run_pipeline_task
from src.core.config import settings
from src.core.logger import get_logger
from src.core.pipeline_status import PipelineStatus

log = get_logger(__name__)
router = APIRouter(tags=["runs"])


def get_daily_limit(key: str) -> str | None:
    if key.startswith("guest-ip:"):
        return settings.rate_limit_guest_run_per_day
    if is_rate_limit_exempt(key):
        return None
    return settings.rate_limit_run_pipeline_per_day


def get_weekly_limit(key: str) -> str | None:
    if key.startswith("guest-ip:"):
        return "10/week"
    if is_rate_limit_exempt(key):
        return None
    return settings.rate_limit_run_pipeline_per_week


@router.post("/run-pipeline", response_model=PipelineRunResponse)
@limiter.limit(get_daily_limit)
@limiter.limit(get_weekly_limit)
async def trigger_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="BRD document (PDF, DOCX, or TXT)"),
    model_family: str = Form("openai", description="Model family to run: openai, anthropic, llama, mistral"),
    enable_fallback: bool = Form(True, description="Enable automatic provider fallback if primary fails"),
    consent_accepted: bool = Form(False, description="Confirm acceptance of Terms and Privacy Policy"),
):
    """BRD upload → Security validation → Agent pipeline → Artifacts."""
    user_email = get_current_user_email(request)

    is_guest = bool(request.session.get("is_guest"))
    if is_guest:
        model_family = "llama"

    if not consent_accepted:
        raise HTTPException(
            status_code=400, detail="You must accept the Terms of Service and Privacy Policy to upload documents."
        )

    if model_family.lower() not in ("openai", "anthropic", "llama"):
        raise HTTPException(status_code=400, detail=f"Model family '{model_family}' is not available.")

    content = await file.read()

    brd_hash = hashlib.sha256(content).hexdigest()

    # Log user consent acceptance to logs/consent.jsonl
    import datetime
    from pathlib import Path

    consent_dir = Path("logs")
    consent_dir.mkdir(exist_ok=True)
    consent_file = consent_dir / "consent.jsonl"

    consent_record = {
        "email": "guest" if is_guest else user_email,
        "is_guest": is_guest,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "brd_hash": brd_hash,
        "terms_version": "2026-07-01",
    }

    with open(consent_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(consent_record) + "\n")

    run_id = f"{brd_hash[:8]}-{uuid.uuid4().hex[:4]}"

    _run_owner[run_id] = user_email
    # Clear any prior run state for this run_id so polling never returns a stale awaiting_hitl
    _runs.pop(run_id, None)
    _run_export.pop(run_id, None)
    _run_events[run_id] = []

    background_tasks.add_task(
        _run_pipeline_task,
        content,
        brd_hash,
        run_id,
        file.filename or "upload.txt",
        file.content_type or "text/plain",
        model_family,
        enable_fallback,
    )

    log.info(
        f"Pipeline triggered | run_id={run_id} | file={file.filename} | family={model_family} | fallback={enable_fallback}"
    )
    return PipelineRunResponse(
        run_id=run_id,
        status="started",
        message=f"Pipeline started. Stream progress at GET /status/{run_id}",
    )


@router.get("/status/{run_id}")
async def stream_status(run_id: str, request: Request):
    """Server-Sent Events stream - UI connects here for live updates."""
    verify_run_ownership(run_id, request)

    async def event_generator() -> AsyncGenerator[str, None]:
        sent = 0
        timeout = settings.pipeline_timeout_sec
        elapsed = 0
        last_yielded_status: str | None = None
        long_running_emitted = False

        while elapsed < timeout:
            # Batched read: one LRANGE(sent, -1) per outer iteration returns
            # every event we haven't yielded yet. Previously this loop did
            # LLEN + LINDEX per event, giving 2N Redis roundtrips per second
            # while streaming — under Upstash latency (~50-200ms/call) that
            # was the dominant cost of the SSE endpoint. Slicing goes through
            # RedisListHelper.__getitem__(slice) which issues a single LRANGE.
            events_helper = _run_events.get(run_id, [])
            # Unconditional slice — one LRANGE if Redis, one list-slice if local.
            # Avoids an extra LLEN roundtrip that a truthiness check would trigger.
            for ev in events_helper[sent:]:
                yield f"data: {ev}\n\n"
                sent += 1

            state = _runs.get(run_id)
            if state and state.pipeline_status in ("exported", "export_failed", "error", "canceled", "rejected"):
                if state.pipeline_status != last_yielded_status:
                    yield f"data: {json.dumps({'type': 'status', 'status': state.pipeline_status, 'run_id': run_id})}\n\n"
                    last_yielded_status = state.pipeline_status
                break

            if elapsed >= timeout - 30 and not long_running_emitted:
                yield f"data: {json.dumps({'type': 'long_running', 'run_id': run_id, 'message': 'This run is taking longer than expected — still working, will refresh automatically.'})}\n\n"
                long_running_emitted = True

            await asyncio.sleep(1)
            elapsed += 1

        yield f"data: {json.dumps({'type': 'stream_end', 'run_id': run_id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# Terminal states where cancellation is meaningless (run is already finished).
# awaiting_hitl is deliberately EXCLUDED - even though the pipeline itself is
# done, the user might still want to abandon the run before deciding, so we
# treat awaiting_hitl as cancellable (frontend will just clear the UI).
_TERMINAL_STATES_FOR_CANCEL: frozenset[str] = frozenset(
    {
        PipelineStatus.EXPORTED.value,
        PipelineStatus.REJECTED.value,
        PipelineStatus.EXPORT_FAILED.value,
        PipelineStatus.ERROR.value,
        PipelineStatus.CANCELED.value,
    }
)


@router.post("/cancel/{run_id}")
async def cancel_run(run_id: str, request: Request):
    """
    Cooperative cancellation. Sets a flag on the run; the pipeline observes it
    between LangGraph nodes (inside _set_status) and raises RunCanceledError.

    URL pattern matches the flat convention used by /approve/{run_id},
    /status/{run_id}, /events/{run_id} - keeps the local Vite dev proxy simple
    and the routes readable side-by-side.

    - 404 if the run doesn't exist
    - 409 if the run is already in a terminal state (nothing to cancel)
    - 200 with {run_id, status: "cancel_requested"} on success

    Idempotent: calling multiple times on the same run returns 200 each time.
    In-flight LLM calls finish before the pipeline unwinds, so cancellation
    isn't instant - typically completes within one LLM-call worth of time.
    """
    verify_run_ownership(run_id, request)

    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if state.pipeline_status in _TERMINAL_STATES_FOR_CANCEL:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "run_already_terminal",
                "message": f"Run {run_id} is already {state.pipeline_status}; nothing to cancel.",
            },
        )

    _run_cancel_flags[run_id] = True
    log.info(f"[{run_id}] Cancel requested by user (current status={state.pipeline_status})")
    return {"run_id": run_id, "status": "cancel_requested"}


@router.get("/events/{run_id}")
async def get_events(run_id: str, request: Request, since: int = 0):
    """
    Snapshot of accumulated SSE events for a run.
    Clients poll /events/{run_id}?since=N where N is the next index to read.
    """
    verify_run_ownership(run_id, request)
    events_raw = _run_events.get(run_id, [])
    new_events = events_raw[since:]
    parsed: list[dict] = []
    for ev in new_events:
        try:
            parsed.append(json.loads(ev))
        except json.JSONDecodeError:
            parsed.append({"type": "raw", "data": ev})
    return {
        "run_id": run_id,
        "since": since,
        "next_index": len(events_raw),
        "events": parsed,
    }
