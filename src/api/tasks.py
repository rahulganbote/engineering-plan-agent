"""
src/api/tasks.py
════════════════
Background workers for running pipelines and approval exports.
"""

from __future__ import annotations

from src.api.state import _push_event, _run_export, _runs
from src.core.logger import get_logger
from src.core.models import HITLDecision
from src.core.pipeline_status import PipelineStatus

log = get_logger(__name__)


def _run_pipeline_task(
    file_bytes: bytes,
    brd_hash: str,
    run_id: str,
    brd_name: str,
    content_type: str = "text/plain",
    model_family: str = "openai",
    enable_fallback: bool = True,
) -> None:
    state = None
    try:
        from src.core.models import PipelineState
        state = PipelineState(run_id=run_id, brd_raw_hash=brd_hash, brd_name=brd_name)
        state.pipeline_status = PipelineStatus.SECURITY_CHECK.value
        _runs[run_id] = state

        _push_event(run_id, {"type": "pipeline_status", "status": PipelineStatus.SECURITY_CHECK.value})
        _push_event(run_id, {"type": "security_start"})

        from src.security.validator import SecurityValidator, ValidationStatus
        validator = SecurityValidator()
        val_result = validator.validate(
            file_bytes=file_bytes,
            filename=brd_name,
            content_type=content_type,
            model_family=model_family,
        )

        if val_result.status == ValidationStatus.BLOCKED:
            _push_event(run_id, {"type": "security_blocked", "message": val_result.user_message})
            state.pipeline_status = PipelineStatus.ERROR.value
            state.errors.append(val_result.user_message)
            _runs[run_id] = state
            return

        _push_event(run_id, {"type": "security_complete"})

        if val_result.pii_types_found:
            _push_event(
                run_id,
                {
                    "type": "pii_warning",
                    "pii_types": val_result.pii_types_found,
                    "message": val_result.user_message,
                },
            )

        brd_text = val_result.brd_text_clean or ""

        _push_event(run_id, {"type": "agent_start", "agent": "orchestrator"})
        from src.agents.pipeline import run_pipeline

        state = run_pipeline(brd_text, brd_hash, run_id, brd_name, model_family, enable_fallback)
        _runs[run_id] = state
        _push_event(
            run_id,
            {
                "type": "pipeline_complete",
                "status": state.pipeline_status,
                "final_status": state.pipeline_status,  # legacy alias used by some clients
                "processing_time_sec": getattr(state, "processing_time_sec", 0),
                "total_input_tokens": getattr(state, "total_input_tokens", 0),
                "total_output_tokens": getattr(state, "total_output_tokens", 0),
                "total_cost_usd": getattr(state, "total_cost_usd", 0.0),
            },
        )
        log.info(f"[{run_id}] Pipeline task complete | status={state.pipeline_status}")
    except Exception as e:
        from src.core.exceptions import GovernedFailure

        err_msg = str(e)
        if isinstance(e, GovernedFailure):
            err_msg = e.user_message

        log.error(f"[{run_id}] Pipeline task failed | error={e}")
        _push_event(run_id, {"type": "error", "message": err_msg})
        # Pipeline raised before producing a state - synthesize a minimal error
        # state so the failed run is still recorded and visible to the EM.
        if state is None:
            try:
                from src.core.models import PipelineState

                state = PipelineState(run_id=run_id, brd_raw_hash=brd_hash, brd_name=brd_name)
            except Exception:
                state = None
        if state is not None:
            state.pipeline_status = PipelineStatus.ERROR.value
            if err_msg not in state.errors:
                state.errors.append(err_msg)
            _runs[run_id] = state

    # A failed run never reaches the HITL gate / POST /approve, so log a Run
    # Summary row here too - the EM sees errored runs on the Sheets dashboard.
    if state is not None and state.pipeline_status == PipelineStatus.ERROR.value:
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


async def _run_export_handlers_background(
    run_id: str,
    decision: HITLDecision,
    email: str,
) -> None:
    """
    Background worker for /approve - runs Sheets, Jira (via MCP), and Pinecone
    re-indexing. Emits SSE events at each step so the UI can update progressively
    instead of waiting for a synchronous response that ElevenLabs would time out
    on after 20s.

    Wrapped in a top-level try/finally so any uncaught exception still:
      • sets pipeline_status to `export_failed`
      • marks _run_export[run_id]["finalized"] = True (so the UI poll path exits)
      • emits a terminal `exports_finalized` event with the failure reason

    No return value - observability is via SSE events and the /artifacts endpoint.
    """
    state = _runs.get(run_id)
    if not state:
        log.error(f"[{run_id}] background export: state lost during dispatch")
        return

    sheet_url: str | None = None
    export_status: str | None = None
    export_mode: str | None = None
    export_detail: str | None = None
    jira_url: str | None = None
    jira_status: str | None = None
    jira_mode: str | None = None
    jira_detail: str | None = None
    jira_issue_key: str | None = None

    try:
        # Import integration modules so they register themselves on first access.
        import src.integrations.jira_mcp  # noqa: F401
        import src.integrations.pdf_export  # noqa: F401
        import src.integrations.sheets  # noqa: F401
        from src.integrations.export_registry import get_handlers_for_decision

        registry_decision = "approve" if decision == HITLDecision.APPROVED else "reject"
        export_results: dict = {}

        for handler_name, handler_fn in get_handlers_for_decision(registry_decision):
            try:
                import inspect as _inspect

                sig = _inspect.signature(handler_fn)
                kwargs = {}
                if "email" in sig.parameters:
                    kwargs["email"] = email

                if _inspect.iscoroutinefunction(handler_fn):
                    result = await handler_fn(state, **kwargs)
                else:
                    result = handler_fn(state, **kwargs)
                export_results[handler_name] = result
                log.info(f"[{run_id}] export handler '{handler_name}' ok | {result.get('mode', '?')}")
            except Exception as e:
                err = f"{type(e).__name__}: {str(e)[:200]}"
                export_results[handler_name] = {"mode": "failed", "error": err}
                log.error(f"[{run_id}] export handler '{handler_name}' failed | {err}")

        # ── Unpack sheets result ───────────────────────────────────────────
        sheets_result = export_results.get("sheets", {})
        if sheets_result:
            sheet_url = sheets_result.get("url")
            export_mode = sheets_result.get("mode")
            export_detail = sheets_result.get("detail")
            export_status = (
                "ok" if export_mode == "sheets" else ("local_fallback" if export_mode == "local" else "failed")
            )
            if decision == HITLDecision.APPROVED:
                state.pipeline_status = PipelineStatus.EXPORTED.value
            elif decision == HITLDecision.REJECTED:
                state.pipeline_status = PipelineStatus.REJECTED.value
            _run_export[run_id] = {
                "sheet_url": sheet_url,
                "mode": export_mode,
                "detail": export_detail,
                "files": sheets_result.get("files", []),
                "fallback_reason": sheets_result.get("fallback_reason"),
                "status": export_status,
            }
            _push_event(
                run_id,
                {
                    "type": "export_complete",
                    "mode": export_mode,
                    "sheet_url": sheet_url,
                    "detail": export_detail,
                },
            )

        # ── Unpack Jira result ─────────────────────────────────────────────
        jira_result = export_results.get("jira", {})
        if jira_result:
            jira_mode = jira_result.get("mode")
            jira_issue_key = jira_result.get("key")
            jira_url = jira_result.get("url")
            jira_detail = jira_result.get("detail")
            jira_status = "jira" if jira_mode == "jira" else ("skipped" if jira_mode == "skipped" else "failed")
            _push_event(
                run_id,
                {
                    "type": "jira_pushed",
                    "mode": jira_mode,
                    "url": jira_url,
                    "issue_key": jira_issue_key,
                    "detail": jira_detail,
                },
            )
            log.info(f"[{run_id}] Jira {jira_mode} | key={jira_issue_key} | url={jira_url}")

        # ── Trigger Pinecone document ingestion ────────────────────────────
        # Now that the BRD is approved, register it into the RAG vector store
        # so subsequent runs benefit from the approved plan.
        if decision == HITLDecision.APPROVED:
            # Look up raw BRD file text from local cache
            brd_text = ""
            brd_name = state.brd_name or "uploaded_brd.txt"
            try:
                from src.core.cache import get_default_backend

                cached_brd = get_default_backend().get(state.brd_raw_hash, "brd")
                if cached_brd:
                    brd_text = cached_brd.get("text", "")
            except Exception as ce:
                log.warning(f"[{run_id}] Could not retrieve cached BRD for Pinecone ingest: {ce}")

            if brd_text.strip():
                try:
                    import os

                    from src.core.rag import ingest_document

                    _push_event(run_id, {"type": "pinecone_ingest", "status": "started"})
                    doc_id = os.path.splitext(brd_name)[0]
                    ingest_result = ingest_document(
                        text=brd_text,
                        doc_id=doc_id,
                        source_type="brd",
                    )
                    try:
                        chunks_added = int(ingest_result.split(" ")[0])
                    except Exception:
                        chunks_added = ingest_result

                    _push_event(
                        run_id,
                        {
                            "type": "pinecone_ingest",
                            "status": "completed",
                            "detail": f"Ingested approved BRD into Pinecone knowledge base ({chunks_added} chunks)",
                        },
                    )
                    log.info(f"[{run_id}] Approved BRD successfully indexed into Pinecone ({chunks_added} chunks)")
                except Exception as ie:
                    _push_event(
                        run_id,
                        {
                            "type": "pinecone_ingest",
                            "status": "failed",
                            "detail": f"RAG ingestion failed: {str(ie)[:200]}",
                        },
                    )
                    log.error(f"[{run_id}] Pinecone ingestion failed: {ie}")
            else:
                log.info(f"[{run_id}] Skipping Pinecone ingestion: empty BRD text.")
                _push_event(run_id, {"type": "pinecone_ingest", "status": "skipped", "detail": "Empty BRD text"})

        # Send Slack confirmation alerts (omitted as Slack incoming webhook is error-only)
        pass

    except Exception as e:
        log.exception(f"[{run_id}] background export worker crashed")
        # Ensure fallback state so frontend poll exit triggers
        _push_event(run_id, {"type": "error", "message": f"Background export worker crashed: {str(e)}"})
        if decision == HITLDecision.APPROVED:
            state.pipeline_status = PipelineStatus.EXPORT_FAILED.value
        elif decision == HITLDecision.REJECTED:
            state.pipeline_status = PipelineStatus.EXPORT_FAILED.value

    finally:
        # Mark finalized to release any waiting polling client
        if run_id in _run_export:
            _run_export[run_id]["finalized"] = True
            _run_export[run_id]["jira"] = {
                "url": jira_url,
                "mode": jira_mode or "skipped",
                "issue_key": jira_issue_key,
                "detail": jira_detail or "Not pushed",
            }
        else:
            _run_export[run_id] = {
                "sheet_url": sheet_url,
                "mode": export_mode,
                "detail": export_detail,
                "status": export_status or "failed",
                "finalized": True,
                "jira": {
                    "url": jira_url,
                    "mode": jira_mode or "skipped",
                    "issue_key": jira_issue_key,
                    "detail": jira_detail or "Not pushed",
                },
            }

        # Terminal SSE event carrying approval results
        _push_event(
            run_id,
            {
                "type": "exports_finalized",
                "run_id": run_id,
                "decision": decision.value,
                "pipeline_status": state.pipeline_status,
                "sheet_url": sheet_url,
                "export_status": export_status or "failed",
                "export_mode": export_mode or "failed",
                "export_detail": export_detail or "Failed to process",
                "jira_url": jira_url,
                "jira_status": jira_status or "failed",
                "jira_detail": jira_detail or "Not pushed",
                "jira_issue_key": jira_issue_key,
                "rejection_count": state.hitl_rejection_count,
            },
        )
        log.info(
            f"[{run_id}] Background exports finalized | status={state.pipeline_status} sheet={bool(sheet_url)} jira={bool(jira_url)}"
        )
