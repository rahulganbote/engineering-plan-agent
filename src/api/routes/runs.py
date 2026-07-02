"""
src/api/routes/runs.py
══════════════════════
Pipeline execution, status streaming, and event log routes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_current_user_email, verify_run_ownership
from src.api.limiter import limiter
from src.api.models import PipelineRunResponse
from src.api.state import _push_event, _run_events, _run_export, _run_owner, _runs
from src.api.tasks import _run_pipeline_task
from src.core.config import settings
from src.core.logger import get_logger
from src.security.validator import SecurityValidator, ValidationStatus

log = get_logger(__name__)
router = APIRouter(tags=["runs"])


@limiter.limit(settings.rate_limit_run_pipeline_per_day)
@limiter.limit(settings.rate_limit_run_pipeline_per_week)
@router.post("/run-pipeline", response_model=PipelineRunResponse)
async def trigger_pipeline(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="BRD document (PDF, DOCX, or TXT)"),
    model_family: str = Form("openai", description="Model family to run: openai, anthropic, llama, mistral"),
    enable_fallback: bool = Form(True, description="Enable automatic provider fallback if primary fails"),
):
    """BRD upload → Security validation → Agent pipeline → Artifacts."""
    user_email = get_current_user_email(request)

    if model_family.lower() not in ("openai", "anthropic"):
        raise HTTPException(
            status_code=400, detail=f"Model family '{model_family}' is coming soon. Please select OpenAI or Anthropic."
        )

    content = await file.read()

    brd_hash = hashlib.sha256(content).hexdigest()
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

        while elapsed < timeout:
            events = _run_events.get(run_id, [])
            while sent < len(events):
                yield f"data: {events[sent]}\n\n"
                sent += 1

            state = _runs.get(run_id)
            if state and state.pipeline_status in ("exported", "export_failed", "awaiting_hitl"):
                if state.pipeline_status != last_yielded_status:
                    yield f"data: {json.dumps({'type': 'status', 'status': state.pipeline_status, 'run_id': run_id})}\n\n"
                    last_yielded_status = state.pipeline_status
                if state.pipeline_status in ("exported", "export_failed"):
                    break

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
