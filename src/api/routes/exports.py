"""
src/api/routes/exports.py
═════════════════════════
Artifact downloads, metadata retrieval, and logging.
"""

from __future__ import annotations

import copy

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from src.api.dependencies import verify_run_ownership
from src.api.models import ArtifactSummary, LogDownloadRequest
from src.api.state import _run_events, _run_export, _runs
from src.core.logger import get_logger
from src.core.models import HITLDecision

log = get_logger(__name__)
router = APIRouter(tags=["exports"])


@router.get("/results/{run_id}", response_model=ArtifactSummary)
async def get_results(run_id: str, request: Request):
    """Summary: badge, scores, has_* booleans + pipeline status."""
    verify_run_ownership(run_id, request)
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


@router.get("/artifacts/{run_id}")
async def get_artifacts(run_id: str, request: Request):
    """
    Full PipelineState JSON (plan, schedule, architecture+SVG, PoC,
    tech stack, Critic detail). Returns 202 if pipeline still initializing.
    """
    verify_run_ownership(run_id, request)
    state = _runs.get(run_id)
    if not state:
        if run_id in _run_events:
            return JSONResponse(
                status_code=202,
                content={
                    "run_id": run_id,
                    "pipeline_status": "initializing",
                    "message": "Pipeline starting up - poll /events for progress",
                },
            )
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    payload = state.model_dump(mode="json")
    export_meta = _run_export.get(run_id)
    if export_meta:
        payload["export"] = export_meta
    return payload


@router.get("/download/{run_id}")
async def download_artifacts_pdf(run_id: str, request: Request):
    verify_run_ownership(run_id, request)
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if not any(
        [
            state.plan_output,
            state.schedule_output,
            state.arch_output,
            state.poc_output,
            state.stack_output,
        ]
    ):
        raise HTTPException(status_code=409, detail="Artifacts are not ready yet")

    from src.integrations.pdf_export import build_artifacts_pdf

    pdf_bytes = build_artifacts_pdf(state)
    filename = f"em-copilot-{run_id}-artifacts.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/log-download/{run_id}")
async def log_download(run_id: str, req: LogDownloadRequest):
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    from src.integrations.sheets import write_artifacts_to_sheet

    state_copy = copy.copy(state)
    state_copy.hitl_decision = HITLDecision.DOWNLOAD_PDF

    try:
        write_artifacts_to_sheet(state_copy, email=req.email)
    except Exception as e:
        log.error(f"[{run_id}] Failed to log PDF download to sheet: {e}")

    return {"status": "ok"}
