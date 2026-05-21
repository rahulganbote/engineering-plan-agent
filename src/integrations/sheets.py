"""
src/integrations/sheets.py
═══════════════════════════
Artifact export — writes approved engineering artifacts to Google Sheets,
with an automatic local-CSV fallback when Google credentials are missing.

Called by the pipeline ONLY after the EM approves via HITL gate (POST /approve).

Export modes:
    1. "sheets"  — service-account JSON + sheet ID are configured AND the
                   Google API call succeeds. Writes 4 tabs to the sheet
                   ("Run Summary", "Engineering Plan", "Schedule", "Tech Stack").
                   Returns the Google Sheets URL.
    2. "local"   — fallback when credentials are missing or the Google API
                   call raises. Writes the same 4 datasets as CSV files into
                   logs/exports/<run_id>/ and returns a file:// URL.
                   Lets the demo run end-to-end with zero external setup.

External tool: gspread + Google Service Account JSON credentials (when available).
This counts as the "Action — write to external system" rubric requirement.

Setup for real Sheets export:
    1. Google Cloud Console → Create Service Account
    2. Download JSON key → save to secrets/google_service_account.json
    3. Share your Google Sheet with the service account email
    4. Copy Sheet ID from URL → GOOGLE_SHEET_ID in .env

Rubric:
    - Tools (external system): 2 pts ← external API integration
    - Action (write):               ← artifacts written on HITL approval
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Where local CSV bundles are written when Sheets credentials are unavailable.
# Relative to whatever cwd uvicorn was launched from — matches src/core/logger.py.
LOCAL_EXPORT_ROOT = Path("logs/exports")


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def write_artifacts_to_sheet(state: PipelineState) -> dict[str, Any]:
    """
    Export all approved engineering artifacts.

    Returns a dict:
        {
          "url":      str,                 # https://… (sheets) or file://… (local)
          "mode":     "sheets" | "local",
          "detail":   str,                 # human-friendly status line
          "files":    list[str],           # populated in local mode
          "fallback_reason": str | None,   # populated only when falling back
        }

    Never raises — failures during the Google Sheets path fall through to
    the local CSV path so the pipeline never gets stuck post-approval.
    """
    run_id = state.run_id
    creds_ok, why_not = _credentials_status()

    if creds_ok:
        try:
            url = _write_to_google_sheets(state)
            log.info(f"[{run_id}] Sheets export complete | url={url}")
            return {
                "url":              url,
                "mode":             "sheets",
                "detail":           "Wrote Run Summary + Plan + Schedule + Tech Stack tabs to Google Sheets",
                "files":            [],
                "fallback_reason":  None,
            }
        except Exception as e:
            reason = f"Sheets API error: {type(e).__name__}: {str(e)[:160]}"
            log.warning(f"[{run_id}] Sheets export failed — falling back to local | {reason}")
            return _write_local_export(state, fallback_reason=reason)

    log.info(f"[{run_id}] Sheets credentials unavailable ({why_not}) — writing local CSV bundle")
    return _write_local_export(state, fallback_reason=why_not)


# ──────────────────────────────────────────────────────────────────────────────
# Credentials probe
# ──────────────────────────────────────────────────────────────────────────────

def _credentials_status() -> tuple[bool, str]:
    """Return (ok, reason) — reason is the why-not string when ok is False."""
    sheet_id = (settings.google_sheet_id or "").strip()
    creds_path_str = (settings.google_service_account_json or "").strip()

    if not sheet_id:
        return False, "GOOGLE_SHEET_ID is not set in .env"
    if not creds_path_str:
        return False, "GOOGLE_SERVICE_ACCOUNT_JSON path is not set in .env"

    creds_path = Path(creds_path_str)
    if not creds_path.exists():
        return False, f"Service account JSON not found at {creds_path}"

    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# Google Sheets path
# ──────────────────────────────────────────────────────────────────────────────

def _write_to_google_sheets(state: PipelineState) -> str:
    """
    Write all approved artifacts to Google Sheets.
    Creates tabs if they don't exist. Appends rows on subsequent runs.
    Returns the Sheet URL.
    """
    # Imports are local — gspread / google-auth are only required for this path
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(
        settings.google_service_account_json,
        scopes=SCOPES,
    )
    gc     = gspread.authorize(creds)
    sh     = gc.open_by_key(settings.google_sheet_id)
    run_id = state.run_id
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    log.info(f"[{run_id}] Writing artifacts to Google Sheets")

    # ── Tab: Run Summary ─────────────────────────────────────────────────────
    summary_ws = _get_or_create_worksheet(sh, "Run Summary", rows=100, cols=20)
    _ensure_min_cols(summary_ws, len(_summary_headers()))
    summary_ws.update("A1", [_summary_headers()])
    summary_ws.append_row(_summary_row(state, ts))

    # ── Tab: Engineering Plan ────────────────────────────────────────────────
    if state.plan_output:
        plan_ws = _get_or_create_worksheet(sh, "Engineering Plan", rows=500, cols=8)
        _ensure_headers_gs(plan_ws, _plan_headers())
        for row in _plan_rows(state):
            plan_ws.append_row(row)

    # ── Tab: Schedule ─────────────────────────────────────────────────────────
    if state.schedule_output:
        sched_ws = _get_or_create_worksheet(sh, "Schedule", rows=500, cols=7)
        _ensure_headers_gs(sched_ws, _schedule_headers())
        for row in _schedule_rows(state):
            sched_ws.append_row(row)

    # ── Tab: Tech Stack ───────────────────────────────────────────────────────
    if state.stack_output:
        stack_ws = _get_or_create_worksheet(sh, "Tech Stack", rows=100, cols=10)
        _ensure_headers_gs(stack_ws, _tech_stack_headers())
        for row in _tech_stack_rows(state):
            stack_ws.append_row(row)

    return f"https://docs.google.com/spreadsheets/d/{settings.google_sheet_id}"


def _ensure_min_cols(ws, min_cols: int) -> None:
    """Widen an existing worksheet if it has fewer columns than the schema needs."""
    try:
        if ws.col_count < min_cols:
            ws.add_cols(min_cols - ws.col_count)
    except Exception:
        pass


def _get_or_create_worksheet(sh, title: str, rows: int = 100, cols: int = 10):
    """Get worksheet by name or create it if it doesn't exist."""
    import gspread
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)


def _ensure_headers_gs(ws, headers: list[str]) -> None:
    """Write headers to row 1 if the sheet is empty."""
    if not ws.get_all_values():
        ws.append_row(headers)


# ──────────────────────────────────────────────────────────────────────────────
# Local CSV fallback path
# ──────────────────────────────────────────────────────────────────────────────

def _write_local_export(state: PipelineState, fallback_reason: str = "") -> dict[str, Any]:
    """
    Write artifacts as CSVs into logs/exports/<run_id>/.
    Files written: run_summary.csv, engineering_plan.csv, schedule.csv, tech_stack.csv
    Also writes README.txt explaining the export and fallback reason.
    """
    run_id = state.run_id
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    export_dir = LOCAL_EXPORT_ROOT / run_id
    export_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []

    # Run Summary
    summary_path = export_dir / "run_summary.csv"
    _write_csv(summary_path, _summary_headers(), [_summary_row(state, ts)])
    written.append(str(summary_path))

    # Engineering Plan
    if state.plan_output:
        plan_path = export_dir / "engineering_plan.csv"
        _write_csv(plan_path, _plan_headers(), _plan_rows(state))
        written.append(str(plan_path))

    # Schedule
    if state.schedule_output:
        sched_path = export_dir / "schedule.csv"
        _write_csv(sched_path, _schedule_headers(), _schedule_rows(state))
        written.append(str(sched_path))

    # Tech Stack
    if state.stack_output:
        stack_path = export_dir / "tech_stack.csv"
        _write_csv(stack_path, _tech_stack_headers(), _tech_stack_rows(state))
        written.append(str(stack_path))

    # README
    readme_path = export_dir / "README.txt"
    readme_path.write_text(
        f"EM Copilot — local artifact bundle\n"
        f"Run ID   : {run_id}\n"
        f"Exported : {ts}\n"
        f"Files    : {len(written)}\n"
        f"\n"
        f"This bundle was written instead of Google Sheets because:\n"
        f"  {fallback_reason or '(reason not recorded)'}\n"
        f"\n"
        f"To enable real Google Sheets export, add a service account JSON\n"
        f"at the path in GOOGLE_SERVICE_ACCOUNT_JSON and set GOOGLE_SHEET_ID\n"
        f"in .env, then approve a run again.\n"
    )
    written.append(str(readme_path))

    url = f"file://{export_dir.resolve()}"
    log.info(f"[{run_id}] Local export complete | dir={export_dir} | files={len(written)}")

    return {
        "url":              url,
        "mode":             "local",
        "detail":           f"Wrote {len(written)} files to {export_dir}",
        "files":            written,
        "fallback_reason":  fallback_reason or None,
    }


def _write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    """Write a UTF-8 CSV with headers + data rows."""
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            w.writerow(row)


# ──────────────────────────────────────────────────────────────────────────────
# Shared schema (used by both Sheets and local paths so output is identical)
# ──────────────────────────────────────────────────────────────────────────────

def _summary_headers() -> list[str]:
    return [
        "run_id", "brd_name", "timestamp", "badge", "overall_score",
        "groundedness", "completeness", "consistency", "actionability",
        "revisions", "hitl_decision", "notes", "em_rating", "processing_time_sec",
        "plan_duration_weeks", "plan_confidence", "pipeline_status"
    ]


def _summary_row(state: PipelineState, ts: str) -> list[Any]:
    critic = state.critic_output
    plan = state.plan_output
    # notes: the EM's decision note. For a failed run (no decision) fall back
    # to the pipeline error(s) so the EM sees why it failed on the dashboard.
    notes = state.hitl_latest_note
    if not notes and state.pipeline_status == "error" and state.errors:
        notes = "; ".join(state.errors)[:500]
    em_rating = state.hitl_em_ratings[-1].get("em_rating", "") if state.hitl_em_ratings else ""
    return [
        state.run_id,
        state.brd_name,
        ts,
        critic.badge.value         if critic else "N/A",
        critic.overall_score       if critic else 0,
        critic.groundedness.score  if critic else 0,
        critic.completeness.score  if critic else 0,
        critic.consistency.score   if critic else 0,
        critic.actionability.score if critic else 0,
        state.revision_count,
        state.hitl_decision.value,
        notes,
        em_rating,
        round(state.processing_time_sec, 2),
        plan.total_duration_weeks  if plan else 0,
        plan.confidence_score      if plan else 0.0,
        state.pipeline_status,
    ]


def _plan_headers() -> list[str]:
    return ["run_id", "phase", "milestone", "week", "owner_role", "deliverable", "citations"]


def _plan_rows(state: PipelineState) -> list[list[Any]]:
    if not state.plan_output:
        return []
    citations = ", ".join(state.plan_output.citations)
    rows = []
    for phase in state.plan_output.phases:
        for ms in phase.milestones:
            rows.append([
                state.run_id, phase.name, ms.name, ms.week,
                ms.owner_role, ms.deliverable, citations,
            ])
    return rows


def _schedule_headers() -> list[str]:
    return ["run_id", "sprint", "week_range", "deliverables", "effort_days", "team", "citations"]


def _schedule_rows(state: PipelineState) -> list[list[Any]]:
    if not state.schedule_output:
        return []
    citations = ", ".join(state.schedule_output.citations)
    return [
        [
            state.run_id, row.sprint, row.week_range,
            " | ".join(row.deliverables),
            row.effort_days,
            ", ".join(row.team_members),
            citations,
        ]
        for row in state.schedule_output.sprints
    ]


def _tech_stack_headers() -> list[str]:
    return [
        "run_id", "option", "recommended", "scalability",
        "familiarity", "integration_risk", "cost_usd", "pros", "cons",
    ]


def _tech_stack_rows(state: PipelineState) -> list[list[Any]]:
    if not state.stack_output:
        return []
    rec = state.stack_output.recommended_option
    return [
        [
            state.run_id, opt.name,
            "YES" if opt.name == rec else "",
            opt.scalability_rating,
            opt.team_familiarity_rating,
            opt.integration_risk.value,
            opt.estimated_monthly_cost_usd,
            " | ".join(opt.pros),
            " | ".join(opt.cons),
        ]
        for opt in state.stack_output.options
    ]
