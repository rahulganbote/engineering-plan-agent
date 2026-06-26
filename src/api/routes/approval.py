"""
src/api/routes/approval.py
══════════════════════════
Human-in-the-loop (HITL) approval / rejection routes.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from src.api.dependencies import verify_run_ownership
from src.api.models import ApprovalRequest, ApprovalResponse
from src.api.state import _push_event, _run_export, _runs
from src.core.logger import get_logger
from src.core.models import HITLDecision

log = get_logger(__name__)
router = APIRouter(tags=["approval"])


@router.post("/approve/{run_id}", response_model=ApprovalResponse)
async def hitl_approve(
    run_id: str,
    request: ApprovalRequest,
    background_tasks: BackgroundTasks,
    fastapi_request: Request,
):
    """
    Human-in-the-loop decision gate — fast path.

    Records the EM's decision synchronously in <1s and schedules the heavyweight
    export work (Google Sheets, Jira via MCP, Pinecone re-indexing) as a
    background task. Returns immediately.
    """
    # ── 1. Validate state ────────────────────────────────────────────────────
    verify_run_ownership(run_id, fastapi_request, allow_voice_agent=True)
    state = _runs.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Parse incoming decision once so we can compare against existing
    try:
        incoming_decision = HITLDecision(request.decision.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approved' or 'rejected'",
        )

    # Idempotency on any post-decision state.
    # Covers voice-agent double-fires, UI/voice races, and client retries
    # on the green path of either approve or reject.
    POST_DECISION_STATES = ("exporting", "exported", "rejected", "export_failed")
    if state.pipeline_status in POST_DECISION_STATES and state.hitl_decision is not None:
        if state.hitl_decision == incoming_decision:
            # Same decision retry — return existing export payload so the caller
            # gets a consistent response shape regardless of whether they were first.
            existing = _run_export.get(run_id, {})
            return ApprovalResponse(
                run_id=run_id,
                status=state.pipeline_status,
                decision=state.hitl_decision.value,
                sheet_url=existing.get("sheet_url"),
                jira_url=existing.get("jira_url"),
                message=(f"Already {state.hitl_decision.value} (idempotent retry — no-op)."),
            )
        # Different decision attempted after terminal state → conflict.
        raise HTTPException(
            status_code=409,
            detail={
                "code": "decision_immutable",
                "message": (
                    f"Run {run_id} was already {state.hitl_decision.value}; cannot change to {incoming_decision.value}."
                ),
                "next_step": "Start a new run via the Clear Plan & Reset button.",
            },
        )

    # Mid-pipeline (e.g., running, security_check) → preserve existing 400
    if state.pipeline_status != "awaiting_hitl":
        raise HTTPException(
            status_code=400,
            detail=f"Run {run_id} is not awaiting approval (status={state.pipeline_status})",
        )

    # Use parsed decision; no additional validation needed.
    decision = incoming_decision

    # ── 2. Record decision in state (fast, pure in-memory update) ────────────
    state.hitl_decision = decision
    if hasattr(state, "hitl_em_ratings") and request.em_rating > 0:
        state.hitl_em_ratings.append(
            {
                "rejection_count": state.hitl_rejection_count,
                "decision": decision.value,
                "reviewer": request.reviewer,
                "em_rating": request.em_rating,
                "notes": request.notes,
            }
        )
    if hasattr(state, "hitl_latest_note"):
        state.hitl_latest_note = request.notes

    if decision == HITLDecision.REJECTED:
        if request.notes:
            state.hitl_rejection_notes.append(request.notes)
        state.hitl_rejection_count += 1
        if state.hitl_rejection_count >= 2:
            _push_event(
                run_id,
                {
                    "type": "hitl_escalated",
                    "message": "Two rejections — flagging for audit review",
                },
            )

    # ── 3. Transition to "exporting" so concurrent retries are rejected ──────
    state.pipeline_status = "exporting"

    log.info(
        f"[{run_id}] HITL decision: {decision.value} by {request.reviewer} "
        f"| em_rating={request.em_rating} | exports scheduled in background"
    )

    _push_event(
        run_id,
        {
            "type": "hitl_decision",
            "decision": decision.value,
            "reviewer": request.reviewer,
        },
    )

    # Resolve email from request body, session, or default
    resolved_email = request.email.strip() if request.email else ""
    if not resolved_email:
        resolved_email = fastapi_request.session.get("auth_email") or ""

    if not resolved_email:
        from src.security.google_auth import is_configured

        if not is_configured():
            resolved_email = "local-dev@example.com"
        else:
            if "voice" in request.reviewer.lower() or "eleven" in request.reviewer.lower():
                resolved_email = "voice-agent@example.com"
            else:
                resolved_email = "anonymous@example.com"

    # ── 4. Schedule heavyweight exports as a background task ─────────────────
    from src.api.main import _run_export_handlers_background

    background_tasks.add_task(
        _run_export_handlers_background,
        run_id,
        decision,
        resolved_email,
    )

    # ── 5. Return immediately with pending markers ───────────────────────────
    return ApprovalResponse(
        run_id=run_id,
        decision=decision.value,
        message=(
            f"Decision recorded: {decision.value}. "
            "Exports running in the background — watch for the exports_finalized event."
        ),
        sheet_url=None,
        export_status="pending",
        export_mode=None,
        export_detail=None,
        jira_url=None,
        jira_status="pending",
        jira_detail=None,
        jira_issue_key=None,
        pipeline_status=state.pipeline_status,  # "exporting"
        rejection_count=state.hitl_rejection_count,
    )
