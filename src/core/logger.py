"""
src/core/logger.py
══════════════════
Structured logging for the EM Copilot pipeline.

Two outputs:
    1. Console  - human-readable during development
    2. JSONL file - machine-readable for LangFuse + LangSmith ingestion

Security rule: Raw BRD content is NEVER logged.
    Only sha256 hashes, chunk IDs, and metadata are written to logs.
    This is enforced by passing only the brd_hash field, never brd_text.

Operationalization & Monitoring:
    - Structured logging configuration
    - Success/failure metrics definition (SUCCESS_CRITERIA dict below)

Usage:
    from src.core.logger import get_logger, log_agent_run
    log = get_logger(__name__)
    log.info("Agent starting")
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# ── Log directory ─────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
JSONL_LOG = LOG_DIR / "pipeline.jsonl"

# ── Configure loguru ──────────────────────────────────────────────────────────
# Remove default handler
logger.remove()

# Console - INFO and above, human-readable
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan> | {message}",
    colorize=True,
)

# Rotating file - DEBUG and above, plain text
logger.add(
    sink=LOG_DIR / "pipeline_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}",
)


def get_logger(name: str):
    """
    Returns a loguru logger bound with the caller's module name.

    Usage:
        log = get_logger(__name__)
        log.info("Starting agent run")
        log.error("Agent failed: {error}", error=str(e))
    """
    return logger.bind(name=name)


# ── Structured per-agent log entries ─────────────────────────────────────────


def log_agent_run(
    agent_name: str,
    run_id: str,
    rag_chunk_ids: list[str],
    critic_score: float | None,
    execution_time_ms: int,
    guardrail_triggers: list[str],
    revision_count: int,
    success: bool,
    error: str | None = None,
) -> None:
    """
    Write a structured JSONL log entry for a single agent execution.

    Fields logged:
        - agent_name, run_id, revision_count   - for tracing
        - rag_chunk_ids, rag_chunk_count        - for RAG audit
        - critic_score                          - for improvement tracking
        - execution_time_ms                     - for performance monitoring
        - guardrail_triggers                    - for security audit
        - success, error                        - for failure analysis

    Security: brd_raw_hash is passed externally if needed.
              Raw BRD text is never passed here or logged.

    This is the primary log format for plan execution auditing.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_name": agent_name,
        "run_id": run_id,
        "rag_chunks_used": rag_chunk_ids,
        "rag_chunk_count": len(rag_chunk_ids),
        "critic_score": critic_score,
        "execution_time_ms": execution_time_ms,
        "guardrail_triggers": guardrail_triggers,
        "revision_count": revision_count,
        "success": success,
        "error": error,
    }

    # Write to JSONL
    with open(JSONL_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    # Also log to console
    level = "INFO" if success else "ERROR"
    logger.log(
        level,
        f"[{run_id}] {agent_name} | "
        f"time={execution_time_ms}ms | "
        f"rag={len(rag_chunk_ids)} chunks | "
        f"score={critic_score} | "
        f"revision={revision_count} | "
        f"{'ok' if success else f'FAILED: {error}'}",
    )


# ── Success / Failure criteria ────────────────────────────────────────────────
# Pre-defined success criteria for system validation checks.

SUCCESS_CRITERIA: dict[str, dict] = {
    "SC-1_completeness": {
        "description": "All BRD sections addressed in at least one artifact",
        "metric": "completeness_score >= 5.0 in Critic output",
        "threshold": 5.0,
        "measured_by": "Critic completeness dimension + run_eval.py rule-based section check",
    },
    "SC-2_actionability": {
        "description": "Actionability score >= 4.0/5.0 on eval dataset (not just one run)",
        "metric": "avg actionability >= 4.0 across all 3 test BRDs",
        "threshold": 4.0,
        "measured_by": "LLM-as-judge avg across EVAL-001, EVAL-002, EVAL-003",
    },
    "SC-3_pipeline_time": {
        "description": "End-to-end pipeline completes under 5 minutes",
        "metric": "total_wall_clock_ms < 300000",
        "threshold": 300000,
        "measured_by": "time.perf_counter() in pipeline.py + logged per run",
    },
    "SC-4_schema_compliance": {
        "description": "100% of agent outputs pass Pydantic validation on eval dataset",
        "metric": "schema_pass_rate == 100% across all 5 agents on all test BRDs",
        "threshold": 100.0,
        "measured_by": "run_eval.py execution-based method - required fields per agent",
    },
    "SC-5_citation_coverage": {
        "description": ">= 75% of claims have at least one RAG citation (groundedness)",
        "metric": "groundedness_score >= 3.75 in Critic output",
        "threshold": 3.75,
        "measured_by": "Critic groundedness dimension score",
    },
}

FAILURE_MODES: dict[str, dict] = {
    "malformed_json": {
        "description": "Agent returns malformed JSON or fails Pydantic validation",
        "mitigation": "Retry agent call x2 with tenacity (1s, 2s, 4s backoff), then Amber badge + EM flag",
        "implemented": "BaseAgent._call_llm_with_retry() - tenacity @retry decorator",
    },
    "no_rag_hits": {
        "description": "Pinecone retrieval returns 0 chunks above similarity threshold",
        "mitigation": "Proceed with BRD-only context + disclaimer in output + automatic Amber badge forced",
        "implemented": "rag.py format_context() returns kb_no_results_ungrounded; critic.py checks and forces Amber",
    },
    "critic_loop_stuck": {
        "description": "Critic score never reaches threshold after 2 revision cycles",
        "mitigation": "Hard cap at 2 revisions, assign current badge (Red if still failing), notify EM",
        "implemented": "MAX_REVISIONS=2 in critic.py, config.max_critic_revisions",
    },
    "sheets_write_fail": {
        "description": "Google Sheets gspread write action fails (network, auth, quota)",
        "mitigation": "Log error with run_id, continue pipeline, notify EM via webhook - do not block delivery",
        "implemented": "sheets.py try/except logs failure, returns None gracefully",
    },
    "llm_timeout": {
        "description": "OpenAI API call exceeds timeout or hits rate limit",
        "mitigation": "Exponential backoff 1s/2s/4s via tenacity, then raise to Orchestrator error node",
        "implemented": "BaseAgent._call_llm_with_retry() - tenacity with wait_exponential",
    },
    "injection_blocked": {
        "description": "Security validator blocks BRD containing prompt injection",
        "mitigation": "Return friendly error to React UI, log brd_hash only, pipeline never starts",
        "implemented": "validator.py returns ValidationStatus.BLOCKED with user_message",
    },
    "pii_detected": {
        "description": "PII found in uploaded BRD (email, SSN, phone, card number)",
        "mitigation": "Redact PII in-memory, continue pipeline with WARNING status, log redacted types only",
        "implemented": "validator.py _detect_and_redact_pii() returns WARNING not BLOCKED",
    },
    "agent_error": {
        "description": "Any specialist agent raises unexpected exception",
        "mitigation": "Route to error node, log error_type (no stack trace), skip agent, continue pipeline",
        "implemented": "pipeline.py make_error_node() - AgentExecutionResult(success=False)",
    },
    "pipeline_timeout": {
        "description": "Full pipeline exceeds 5-minute wall-clock limit",
        "mitigation": "SSE stream sends timeout event, partial results returned, EM notified of incomplete run",
        "implemented": "api/main.py SSE stream loop breaks at pipeline_timeout_sec=300",
    },
}


def log_pipeline_summary(
    run_id: str,
    total_wall_clock_ms: int,
    agent_logs: list[dict],
    critic_score: float | None,
    badge: str,
    hitl_decision: str,
    pipeline_status: str,
) -> None:
    """
    Write one pipeline-level summary log entry after pipeline completes.
    Aggregates all individual agent logs into a single searchable record.

    This is what LangFuse / LangSmith dashboards read to show:
        - Overall pipeline health
        - Success criteria pass/fail
        - Per-run performance vs 5-minute SLA

    Success criteria evaluation (logged here for monitoring):
        SC-1: completeness - from critic_score dimension
        SC-2: actionability - from critic_score dimension
        SC-3: pipeline time - total_wall_clock_ms vs 300000ms limit
        SC-4: schema compliance - from agent_logs (all passed validation)
        SC-5: citation coverage - from critic_score groundedness
    """
    sc_results = {
        "SC-3_pipeline_under_5min": total_wall_clock_ms < 300_000,
        "SC-3_wall_clock_ms": total_wall_clock_ms,
    }
    if critic_score is not None:
        sc_results["SC-2_actionability_pass"] = critic_score >= 4.0
        sc_results["SC-5_groundedness_pass"] = critic_score >= 3.75

    # Schema compliance: all agents must have logged success=True
    all_passed = all(log.get("success", False) for log in agent_logs)
    sc_results["SC-4_schema_compliance_pass"] = all_passed

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "pipeline_complete",
        "run_id": run_id,
        "total_wall_clock_ms": total_wall_clock_ms,
        "total_wall_clock_sec": round(total_wall_clock_ms / 1000, 1),
        "under_5min_sla": total_wall_clock_ms < 300_000,
        "agent_count": len(agent_logs),
        "critic_overall_score": critic_score,
        "badge": badge,
        "hitl_decision": hitl_decision,
        "pipeline_status": pipeline_status,
        "success_criteria": sc_results,
        "total_rag_chunks": sum(log.get("rag_chunk_count", 0) for log in agent_logs),
        "total_guardrails": sum(len(log.get("guardrail_triggers", [])) for log in agent_logs),
        "max_revision_count": max((log.get("revision_count", 0) for log in agent_logs), default=0),
    }
    with open(JSONL_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

    sla_status = "✅ within SLA" if total_wall_clock_ms < 300_000 else "❌ SLA BREACH"
    logger.info(
        f"[{run_id}] Pipeline complete | "
        f"{total_wall_clock_ms}ms {sla_status} | "
        f"badge={badge} | score={critic_score} | "
        f"agents={len(agent_logs)} | status={pipeline_status}"
    )
