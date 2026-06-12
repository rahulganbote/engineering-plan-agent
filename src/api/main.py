"""
src/api/main.py
═══════════════
FastAPI gateway — exposes the LangGraph pipeline to the Streamlit UI
and any external callers (ElevenLabs voice agent, monitoring tools).

Endpoints:
    POST /run-pipeline          → Upload BRD, trigger full agent workflow
    GET  /status/{run_id}       → SSE stream of real-time agent progress events
    GET  /events/{run_id}       → Snapshot of accumulated SSE events (since=N)
    POST /approve/{run_id}      → HITL approval/rejection decision gate
                                  On "approved" → triggers Google Sheets export
    GET  /results/{run_id}      → Fetch final artifacts summary + scores + badge
    GET  /artifacts/{run_id}    → Full PipelineState JSON (for Streamlit rendering)
    GET  /health                → Health check for Docker/deployment

Design decisions:
    - Pipeline runs as a FastAPI BackgroundTask — non-blocking upload response
    - SSE streams progress to Streamlit; /events provides a snapshot fallback
    - In-memory run store is sufficient for single-user demo; replace with Redis for prod

Security:
    - BRD content passes through SecurityValidator before pipeline starts
    - Raw BRD content is never stored in run state or logged
    - Only brd_hash is persisted for audit trail
"""

from __future__ import annotations

# Load env vars BEFORE any module that reads them at import time.
# Without this, uvicorn started outside `source secrets/.env` would miss
# LANGCHAIN_TRACING_V2 / LANGCHAIN_API_KEY and LangSmith auto-instrumentation
# would silently send no spans.
from dotenv import load_dotenv
load_dotenv("secrets/.env")
load_dotenv(".env")  # tolerate root-level .env too

# Backfill LangSmith env vars from settings if not already exported.
# Ensures traces land in the named project even when .env only has the API key.
import os as _os
from src.core.config import settings as _settings  # noqa: E402
_os.environ.setdefault("LANGCHAIN_TRACING_V2", str(_settings.langchain_tracing_v2))
_os.environ.setdefault("LANGCHAIN_PROJECT",    _settings.langchain_project or "em-copilot-brd-agent")
if _settings.langchain_api_key:
    _os.environ.setdefault("LANGCHAIN_API_KEY", _settings.langchain_api_key)

import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.core.config import settings
from src.core.logger import get_logger, log_agent_run
from src.core.models import HITLDecision, PipelineState
from src.security.validator import SecurityValidator, ValidationStatus

log = get_logger(__name__)

# ── In-memory run store ───────────────────────────────────────────────────────
_runs:       dict[str, PipelineState] = {}
_run_events: dict[str, list[str]]     = {}
_run_export: dict[str, dict]          = {}   # run_id → {sheet_url, status, error}


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("EM Copilot API starting up")
    yield
    log.info("EM Copilot API shutting down")


app = FastAPI(
    title="EM Copilot — BRD to Engineering Plan API",
    description=(
        "7-agent LangGraph system that transforms BRDs into engineering artifacts. "
        "Hub-and-spoke architecture with Pinecone RAG, Critic revision loop, and HITL gate."
    ),
    version="1.1.0",
    lifespan=lifespan,
)


# ── Phase 8 + 10 wiring — cache backend + observability sink ────────────────
@app.on_event("startup")
async def _wire_resilience_and_cache() -> None:
    """Initialise the process-default cache backend and bridge resilience
    events into the per-run event stream. Idempotent."""
    try:
        from src.core.cache import init_default_backend_from_env
        init_default_backend_from_env()
    except Exception as e:
        log.warning(f"cache backend init failed: {e}")

    try:
        from src.core.events import set_event_sink

        def _bridge(event: dict) -> None:
            rid = event.pop("run_id", None)
            if not rid:
                return  # event outside any run — drop
            _push_event(rid, event)

        set_event_sink(_bridge)
    except Exception as e:
        log.warning(f"event sink wiring failed: {e}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class PipelineRunResponse(BaseModel):
    run_id:  str
    status:  str
    message: str


class ApprovalRequest(BaseModel):
    decision:  str       # "approved" | "rejected"
    reviewer:  str = "Engineering Manager"
    notes:     str = ""
    em_rating: int = 0   # 1-5 — EM rating for Method 5 eval tracking
    email:     str = ""


class ApprovalResponse(BaseModel):
    run_id:          str
    decision:        str
    message:         str
    sheet_url:       str | None = None
    export_status:   str | None = None   # "ok" | "local_fallback" | "failed"
    export_mode:     str | None = None   # "sheets" | "local"
    export_detail:   str | None = None   # human-friendly summary
    # ── Jira push (additive — never blocks approval) ─────────────────────────
    jira_url:        str | None = None   # browse URL on success
    jira_status:     str | None = None   # "jira" | "skipped" | "failed"
    jira_detail:     str | None = None
    jira_issue_key:  str | None = None   # e.g. "EMCP-42"
    pipeline_status: str | None = None
    rejection_count: int = 0


class ArtifactSummary(BaseModel):
    run_id:                str
    badge:                 str
    overall_score:         float
    critic_scores_history: list[dict]
    has_plan:              bool
    has_schedule:          bool
    has_architecture:      bool
    has_poc:               bool
    has_tech_stack:        bool
    pipeline_status:       str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/test-inject/{run_id}")
async def test_inject(run_id: str):
    """
    Test-only endpoint to inject a mock pipeline state directly into memory.
    Avoids calling actual LLM/Pinecone APIs in integration/smoke testing.
    """
    from src.core.models import PipelineState, CriticOutput, QualityBadge, DimensionScore
    
    dim_score = DimensionScore(
        score=3.5,
        threshold=3.0,
        passed=True,
        evidence="Good quality",
        improvement_suggestion="None"
    )
    
    critic = CriticOutput(
        run_id=run_id,
        revision_number=0,
        target_agents=[],
        groundedness=dim_score,
        completeness=dim_score,
        consistency=dim_score,
        actionability=dim_score,
        overall_score=3.5,
        badge=QualityBadge.AMBER,
        requires_revision=False
    )
    
    state = PipelineState(
        run_id=run_id,
        brd_raw_hash="mock_hash",
        brd_name="mock_test.txt",
        pipeline_status="awaiting_hitl",
        critic_output=critic
    )
    
    _runs[run_id] = state
    return {"status": "injected", "run_id": run_id}


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.1.0"}


@app.post("/run-pipeline", response_model=PipelineRunResponse)
async def trigger_pipeline(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="BRD document (PDF, DOCX, or TXT)"),
):
    """BRD upload → Security validation → Agent pipeline → Artifacts."""
    content = await file.read()

    validator = SecurityValidator()
    val_result = validator.validate(
        file_bytes=content,
        filename=file.filename or "upload.txt",
        content_type=file.content_type or "text/plain",
    )

    if val_result.status == ValidationStatus.BLOCKED:
        raise HTTPException(status_code=400, detail=val_result.user_message)

    import uuid
    brd_text = val_result.brd_text_clean or ""
    brd_hash = val_result.brd_hash or ""
    run_id   = f"{brd_hash[:8]}-{uuid.uuid4().hex[:4]}"

    # Clear any prior run state for this run_id so polling never returns
    # a stale "awaiting_hitl" from a previous session for the same BRD hash.
    _runs.pop(run_id, None)
    _run_export.pop(run_id, None)
    _run_events[run_id] = []
    if val_result.pii_types_found:
        _push_event(run_id, {
            "type":      "pii_warning",
            "pii_types": val_result.pii_types_found,
            "message":   val_result.user_message,
        })

    background_tasks.add_task(_run_pipeline_task, brd_text, brd_hash, run_id, file.filename or "upload.txt")

    log.info(f"Pipeline triggered | run_id={run_id} | file={file.filename}")
    return PipelineRunResponse(
        run_id=run_id,
        status="started",
        message=f"Pipeline started. Stream progress at GET /status/{run_id}",
    )


@app.get("/status/{run_id}")
async def stream_status(run_id: str):
    """Server-Sent Events stream — Streamlit connects here for live updates."""
    async def event_generator() -> AsyncGenerator[str, None]:
        sent    = 0
        timeout = settings.pipeline_timeout_sec
        elapsed = 0

        while elapsed < timeout:
            events = _run_events.get(run_id, [])
            while sent < len(events):
                yield f"data: {events[sent]}\n\n"
                sent += 1

            state = _runs.get(run_id)
            if state and state.pipeline_status in (
                "exported", "export_failed", "awaiting_hitl"
            ):
                yield f"data: {json.dumps({'type': 'status', 'status': state.pipeline_status, 'run_id': run_id})}\n\n"
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


@app.get("/events/{run_id}")
async def get_events(run_id: str, since: int = 0):
    """
    Snapshot of accumulated SSE events for a run. Easier to consume from
    Streamlit than the live SSE stream: client polls /events/{run_id}?since=N
    where N is the next index to read.
    """
    events_raw = _run_events.get(run_id, [])
    new_events = events_raw[since:]
    parsed: list[dict] = []
    for ev in new_events:
        try:
            parsed.append(json.loads(ev))
        except json.JSONDecodeError:
            parsed.append({"type": "raw", "data": ev})
    return {
        "run_id":     run_id,
        "since":      since,
        "next_index": len(events_raw),
        "events":     parsed,
    }


@app.post("/approve/{run_id}", response_model=ApprovalResponse)
async def hitl_approve(run_id: str, request: ApprovalRequest):
    """
    Human-in-the-loop decision gate.
    On APPROVAL  : triggers Google Sheets export and returns sheet_url.
    On REJECTION : records rejection, increments counter; Gate 2 reject pushes
                   an escalation event for the UI to surface.
    """
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    if state.pipeline_status != "awaiting_hitl":
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is not awaiting approval (status={state.pipeline_status})",
        )

    try:
        decision = HITLDecision(request.decision.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approved' or 'rejected'",
        )

    state.hitl_decision = decision
    if hasattr(state, "hitl_em_ratings") and request.em_rating > 0:
        state.hitl_em_ratings.append({
            "rejection_count": state.hitl_rejection_count,
            "decision":        decision.value,
            "reviewer":        request.reviewer,
            "em_rating":       request.em_rating,
            "notes":           request.notes,
        })
    log.info(
        f"[{run_id}] HITL decision: {decision.value} by {request.reviewer} "
        f"| em_rating={request.em_rating}"
    )

    _push_event(run_id, {
        "type":     "hitl_decision",
        "decision": decision.value,
        "reviewer": request.reviewer,
    })

    sheet_url:        str | None = None
    export_status:    str | None = None
    export_mode:      str | None = None
    export_detail:    str | None = None
    jira_url:         str | None = None
    jira_status:      str | None = None
    jira_detail:      str | None = None
    jira_issue_key:   str | None = None

    state.hitl_decision = decision
    if hasattr(state, "hitl_latest_note"):
        state.hitl_latest_note = request.notes

    if decision == HITLDecision.REJECTED:
        if request.notes:
            state.hitl_rejection_notes.append(request.notes)
        state.hitl_rejection_count += 1
        
        if state.hitl_rejection_count >= 2:
            _push_event(run_id, {
                "type":    "hitl_escalated",
                "message": "Two rejections — flagging for audit review",
            })

    # ── Export registry (Phase 7) ─────────────────────────────────────────────
    # Import integration modules so they register themselves on first access.
    import src.integrations.sheets    # noqa: F401
    import src.integrations.jira_mcp  # noqa: F401
    import src.integrations.pdf_export  # noqa: F401
    from src.integrations.export_registry import get_handlers_for_decision

    sheet_url:      str | None = None
    export_status:  str | None = None
    export_mode:    str | None = None
    export_detail:  str | None = None
    jira_url:       str | None = None
    jira_status:    str | None = None
    jira_detail:    str | None = None
    jira_issue_key: str | None = None

    decision_key = decision.value  # "approved" | "rejected"
    registry_decision = "approve" if decision_key == "approved" else "reject"
    export_results: dict = {}

    for handler_name, handler_fn in get_handlers_for_decision(registry_decision):
        try:
            import inspect as _inspect
            sig = _inspect.signature(handler_fn)
            kwargs = {}
            if "email" in sig.parameters:
                kwargs["email"] = request.email

            if _inspect.iscoroutinefunction(handler_fn):
                result = await handler_fn(state, **kwargs)
            else:
                result = handler_fn(state, **kwargs)
            export_results[handler_name] = result
            log.info(f"[{run_id}] export handler '{handler_name}' ok | {result.get('mode','?')}")
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
            export_results[handler_name] = {"mode": "failed", "error": err}
            log.error(f"[{run_id}] export handler '{handler_name}' failed | {err}")

    # ── Unpack sheets result (shape-stable for ApprovalResponse) ─────────────
    sheets_result = export_results.get("sheets", {})
    if sheets_result:
        sheet_url     = sheets_result.get("url")
        export_mode   = sheets_result.get("mode")
        export_detail = sheets_result.get("detail")
        export_status = "ok" if export_mode == "sheets" else (
            "local_fallback" if export_mode == "local" else "failed"
        )
        if decision == HITLDecision.APPROVED:
            state.pipeline_status = "exported"
        elif decision == HITLDecision.REJECTED:
            state.pipeline_status = "rejected"
        _run_export[run_id] = {
            "sheet_url":       sheet_url,
            "mode":            export_mode,
            "detail":          export_detail,
            "files":           sheets_result.get("files", []),
            "fallback_reason": sheets_result.get("fallback_reason"),
            "status":          export_status,
        }
        _push_event(run_id, {
            "type":      "export_complete",
            "mode":      export_mode,
            "sheet_url": sheet_url,
            "detail":    export_detail,
        })
    elif sheets_result.get("mode") == "failed":
        if decision == HITLDecision.APPROVED:
            state.pipeline_status = "export_failed"
        elif decision == HITLDecision.REJECTED:
            # Rejection still happens — audit row went to local CSV fallback.
            state.pipeline_status = "rejected"
        export_status = "failed"
        err_msg = sheets_result.get("error", "unknown")
        _run_export[run_id] = {"sheet_url": None, "status": "failed", "error": err_msg}
        _push_event(run_id, {"type": "export_failed", "error": err_msg})

    # ── Unpack jira result ────────────────────────────────────────────────────
    jresult = export_results.get("jira", {})
    if jresult:
        jira_url       = jresult.get("url")
        jira_mode      = jresult.get("mode") or "skipped"
        jira_detail    = jresult.get("detail")
        jira_issue_key = jresult.get("issue_key")
        jira_status    = jira_mode
        _run_export.setdefault(run_id, {})["jira"] = jresult
        _push_event(run_id, {
            "type":      "jira_pushed" if jira_url else "jira_skipped",
            "mode":      jira_mode,
            "url":       jira_url,
            "issue_key": jira_issue_key,
            "detail":    jira_detail,
        })
        log.info(f"[{run_id}] Jira {jira_mode} | key={jira_issue_key} | url={jira_url}")

        # ── Pinecone BRD Ingestion ──
        try:
            from src.core.rag import ingest_document
            # Reconstruct the text from sections since raw text is dropped from state for security
            brd_full_text = "\n\n".join(f"### {sec.section_name}\n{sec.content}" for sec in state.brd_sections)
            doc_id = state.brd_name or f"brd_{run_id}"
            
            ingest_res = ingest_document(
                text=brd_full_text,
                doc_id=doc_id,
                source_type="brd",
                domain="generic"
            )
            log.info(f"[{run_id}] BRD ingested to Pinecone | {ingest_res}")
            _push_event(run_id, {
                "type": "pinecone_ingest",
                "status": "ok",
                "detail": ingest_res
            })
        except Exception as e:
            err_msg = str(e)[:240]
            log.error(f"[{run_id}] Failed to ingest BRD to Pinecone: {err_msg}")
            _push_event(run_id, {
                "type": "pinecone_ingest_failed",
                "error": err_msg
            })

    # The whole /approve handler (Sheets + Jira + Pinecone) is now done. The UI
    # polls until it sees this flag, so it never freezes on a half-finished
    # export — e.g. Jira still creating the Epic when the page last refreshed.
    _run_export.setdefault(run_id, {})["finalized"] = True

    return ApprovalResponse(
        run_id=run_id,
        decision=decision.value,
        message=f"Decision recorded: {decision.value}",
        sheet_url=sheet_url,
        export_status=export_status,
        export_mode=export_mode,
        export_detail=export_detail,
        jira_url=jira_url,
        jira_status=jira_status,
        jira_detail=jira_detail,
        jira_issue_key=jira_issue_key,
        pipeline_status=state.pipeline_status,
        rejection_count=state.hitl_rejection_count,
    )


@app.get("/results/{run_id}", response_model=ArtifactSummary)
async def get_results(run_id: str):
    """Summary: badge, scores, has_* booleans + pipeline status."""
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    critic = state.critic_output
    return ArtifactSummary(
        run_id=run_id,
        badge=critic.badge.value if critic else "unknown",
        overall_score=critic.overall_score if critic else 0.0,
        critic_scores_history=state.critic_scores_history,
        has_plan=state.plan_output is not None,
        has_schedule=state.schedule_output is not None,
        has_architecture=state.arch_output is not None,
        has_poc=state.poc_output is not None,
        has_tech_stack=state.stack_output is not None,
        pipeline_status=state.pipeline_status,
    )


@app.get("/artifacts/{run_id}")
async def get_artifacts(run_id: str):
    """
    Full PipelineState JSON (plan, schedule, architecture+SVG, PoC,
    tech stack, Critic detail). Returns 202 if pipeline still initializing.
    """
    state = _runs.get(run_id)
    if not state:
        if run_id in _run_events:
            return JSONResponse(
                status_code=202,
                content={
                    "run_id":          run_id,
                    "pipeline_status": "initializing",
                    "message":         "Pipeline starting up — poll /events for progress",
                },
            )
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    payload = state.model_dump(mode="json")
    export_meta = _run_export.get(run_id)
    if export_meta:
        payload["export"] = export_meta
    return payload

@app.get("/download/{run_id}")
async def download_artifacts_pdf(run_id: str):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if not any([
        state.plan_output,
        state.schedule_output,
        state.arch_output,
        state.poc_output,
        state.stack_output,
    ]):
        raise HTTPException(status_code=409, detail="Artifacts are not ready yet")

    from src.integrations.pdf_export import build_artifacts_pdf

    pdf_bytes = build_artifacts_pdf(state)
    filename = f"em-copilot-{run_id}-artifacts.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class LogDownloadRequest(BaseModel):
    email: str


@app.post("/log-download/{run_id}")
async def log_download(run_id: str, req: LogDownloadRequest):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    from src.integrations.sheets import write_artifacts_to_sheet
    from src.core.models import HITLDecision
    import copy

    state_copy = copy.copy(state)
    state_copy.hitl_decision = HITLDecision.DOWNLOAD_PDF

    try:
        write_artifacts_to_sheet(state_copy, email=req.email)
    except Exception as e:
        log.error(f"[{run_id}] Failed to log PDF download to sheet: {e}")

    return {"status": "ok"}

# ── Background task ───────────────────────────────────────────────────────────

async def _run_pipeline_task(brd_text: str, brd_hash: str, run_id: str, brd_name: str) -> None:
    state = None
    try:
        _push_event(run_id, {"type": "agent_start", "agent": "orchestrator"})
        from src.agents.pipeline import run_pipeline
        state = run_pipeline(brd_text, brd_hash, run_id, brd_name)
        _runs[run_id] = state
        _push_event(run_id, {"type": "pipeline_complete", "status": state.pipeline_status})
        log.info(f"[{run_id}] Pipeline task complete | status={state.pipeline_status}")
    except Exception as e:
        log.error(f"[{run_id}] Pipeline task failed | error={e}")
        _push_event(run_id, {"type": "error", "message": str(e)})
        # Pipeline raised before producing a state — synthesize a minimal error
        # state so the failed run is still recorded and visible to the EM.
        if state is None:
            try:
                from src.core.models import PipelineState
                state = PipelineState(run_id=run_id, brd_raw_hash=brd_hash, brd_name=brd_name)
            except Exception:
                state = None
        if state is not None:
            state.pipeline_status = "error"
            if str(e)[:500] not in state.errors:
                state.errors.append(str(e)[:500])
            _runs[run_id] = state

    # A failed run never reaches the HITL gate / POST /approve, so log a Run
    # Summary row here too — the EM sees errored runs on the Sheets dashboard.
    if state is not None and state.pipeline_status == "error":
        try:
            from src.integrations.sheets import write_artifacts_to_sheet
            write_artifacts_to_sheet(state)
            log.info(f"[{run_id}] Errored run logged to the dashboard sheet")
        except Exception as se:
            log.warning(f"[{run_id}] Could not log errored run to sheet | {se}")
        try:
            from src.integrations.slack import send_pipeline_error_alert
            send_pipeline_error_alert(state)
        except Exception as se:
            log.warning(f"[{run_id}] Could not send Slack alert | {se}")


def _push_event(run_id: str, data: dict) -> None:
    if run_id not in _run_events:
        _run_events[run_id] = []
    _run_events[run_id].append(json.dumps(data))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=True,
        log_level="info",
    )
