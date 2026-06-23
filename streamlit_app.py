"""
streamlit_app.py
═════════════════
EM Copilot — BRD to Engineering Plan multi-agent system UI.

What this UI does:
    1. BRD upload (PDF / DOCX / TXT) → POST /run-pipeline
    2. Live agent-progress chips (orchestrator → 5 specialists → critic)
       + collapsible raw event log fed by GET /events/{run_id}?since=N
    3. Final artifacts rendering (Plan, Schedule, Architecture+SVG, PoC, Tech Stack)
    4. Critic rubric scores + Green/Amber/Red badge
    5. HITL Gate 1/2 Approve/Reject buttons
    6. On approve → POST /approve triggers Google Sheets export and surfaces sheet URL

Talks to the FastAPI service in src/api/main.py.
Default base URL: http://localhost:8000 (override with API_BASE_URL env var).

Run locally:
    # Terminal 1
    uvicorn src.api.main:app --reload --port 8000
    # Terminal 2
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import requests
import streamlit as st


# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
POLL_INTERVAL_SEC = 1.5
HITL_POLL_INTERVAL_SEC = 8.0
TERMINAL_STATUSES = {"exported", "export_failed", "error", "rejected"}
PAUSE_STATUSES = {"awaiting_hitl"}

SPECIALIST_AGENTS = [
    ("engineering_plan_generator", "Plan Generator"),
    ("schedule_estimator",         "Schedule Estimator"),
    ("solution_architect",         "Solution Architect"),
    ("poc_planner",                "PoC Planner"),
    ("tech_stack_recommender",     "Tech Stack Recommender"),
]

AGENT_OUTPUT_FIELD = {
    "engineering_plan_generator": "plan_output",
    "schedule_estimator":         "schedule_output",
    "solution_architect":         "arch_output",
    "poc_planner":                "poc_output",
    "tech_stack_recommender":     "stack_output",
}

BADGE_STYLE = {
    "green": ("🟢 GREEN", "#16a34a"),
    "amber": ("🟡 AMBER", "#f59e0b"),
    "red":   ("🔴 RED",   "#dc2626"),
    "unknown": ("⚪ N/A", "#6b7280"),
}


def _fmt_duration(seconds: float | None) -> str:
    """Render a duration like '42.3s' or '1m 23s' or '1h 5m 12s'. None → '—'."""
    if seconds is None or seconds < 0:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {secs}s"


def _processing_seconds() -> float | None:
    """
    Wall-clock processing time. Frozen once pipeline reaches a terminal/pause
    state. Also frozen when the API has clearly gone offline — defined as
    elapsed > 10s while pipeline_status is still None / "starting" / "initializing".
    Without this guard, the displayed "Total Processing Time" would tick
    indefinitely if uvicorn was down when the user clicked Generate.
    """
    start = st.session_state.pipeline_start_ts
    end   = st.session_state.pipeline_end_ts
    if start is None:
        return None
    elapsed = (end if end is not None else time.time()) - start
    if end is None:
        status = st.session_state.pipeline_status
        if elapsed > 10 and status in (None, "starting", "initializing"):
            # API hasn't responded with a progressing status in 10s. Cap at 10
            # so the indicator doesn't claim minutes of "work" while nothing
            # is actually happening server-side.
            return 10.0
    return elapsed


# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "run_id":             None,
        "events":             [],
        "next_event_index":   0,
        "artifacts":          None,
        "pipeline_status":    None,
        "approval_result":    None,
        "rejection_count":    0,
        "upload_error":       None,
        "completed_agents":   set(),
        "api_base_url":       API_BASE_URL,
        # Wall-clock timing for the "Total Processing Time" indicator
        "pipeline_start_ts":  None,   # set when Run pipeline is clicked
        "pipeline_end_ts":    None,   # frozen when status hits a terminal/pause state
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_run() -> None:
    st.session_state.run_id            = None
    st.session_state.events            = []
    st.session_state.next_event_index  = 0
    st.session_state.artifacts         = None
    st.session_state.pipeline_status   = None
    st.session_state.approval_result   = None
    st.session_state.rejection_count   = 0
    st.session_state.upload_error      = None
    st.session_state.completed_agents  = set()
    st.session_state.pipeline_start_ts = None
    st.session_state.pipeline_end_ts   = None


# ──────────────────────────────────────────────────────────────────────────────
# API client (thin wrappers around requests)
# ──────────────────────────────────────────────────────────────────────────────

def api_url(path: str) -> str:
    return f"{st.session_state.api_base_url.rstrip('/')}{path}"


def api_health() -> tuple[bool, str]:
    try:
        r = requests.get(api_url("/health"), timeout=2)
        if r.ok:
            data = r.json()
            return True, f"v{data.get('version', '?')}"
        return False, f"HTTP {r.status_code}"
    except requests.RequestException as e:
        return False, str(e)[:80]


def api_run_pipeline(file_bytes: bytes, filename: str, content_type: str) -> dict | None:
    files = {"file": (filename, file_bytes, content_type)}
    try:
        r = requests.post(api_url("/run-pipeline"), files=files, timeout=180)   # 3 min timeout for initial processing
        if r.ok:
            return r.json()
        st.session_state.upload_error = (
            f"HTTP {r.status_code}: {r.json().get('detail', r.text)}"
            if r.headers.get("content-type", "").startswith("application/json")
            else f"HTTP {r.status_code}: {r.text[:240]}"
        )
    except requests.RequestException as e:
        st.session_state.upload_error = f"Connection error: {e}"
    return None


def api_get_events(run_id: str, since: int) -> dict | None:
    try:
        r = requests.get(api_url(f"/events/{run_id}"), params={"since": since}, timeout=5)
        if r.ok:
            return r.json()
    except requests.RequestException:
        return None
    return None


def api_get_artifacts(run_id: str) -> tuple[dict | None, int]:
    """Returns (json_payload, http_status). 202 = pipeline still warming up."""
    try:
        r = requests.get(api_url(f"/artifacts/{run_id}"), timeout=10)
        if r.status_code in (200, 202):
            return r.json(), r.status_code
        return None, r.status_code
    except requests.RequestException:
        return None, 0


def api_approve(run_id: str, decision: str, reviewer: str, notes: str, em_rating: int, email: str = "") -> dict | None:
    payload = {
        "decision":  decision,
        "reviewer":  reviewer,
        "notes":     notes,
        "em_rating": em_rating,
        "email":     email,
    }
    try:
        r = requests.post(api_url(f"/approve/{run_id}"), json=payload, timeout=120)
        if r.ok:
            return r.json()
        st.error(f"Approval failed: HTTP {r.status_code} — {r.text[:240]}")
    except requests.RequestException as e:
        st.error(f"Approval connection error: {e}")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Live polling
# ──────────────────────────────────────────────────────────────────────────────

def consume_new_events() -> None:
    """Pull new events from /events?since=N and merge into session state."""
    rid = st.session_state.run_id
    if not rid:
        return
    payload = api_get_events(rid, st.session_state.next_event_index)
    if not payload:
        return
    new_events: list[dict] = payload.get("events", [])
    if new_events:
        st.session_state.events.extend(new_events)
        st.session_state.next_event_index = payload.get("next_index", st.session_state.next_event_index)
        for ev in new_events:
            if ev.get("type") == "agent_complete" and ev.get("agent"):
                st.session_state.completed_agents.add(ev["agent"])


def refresh_artifacts() -> None:
    rid = st.session_state.run_id
    if not rid:
        return
    payload, status = api_get_artifacts(rid)
    if status == 200 and payload:
        st.session_state.artifacts       = payload
        st.session_state.pipeline_status = payload.get("pipeline_status")
        st.session_state.rejection_count = payload.get("hitl_rejection_count", 0)
        _sync_external_hitl_decision(payload)
        # Freeze processing-time clock the first time we observe a terminal/pause state.
        # Defensive: require >= 3s of elapsed time before freezing. Otherwise we
        # treat the status as stale/cached and let the clock keep ticking until
        # the actual pipeline progresses far enough to be credibly "done".
        if (
            st.session_state.pipeline_end_ts is None
            and st.session_state.pipeline_start_ts is not None
            and st.session_state.pipeline_status in (TERMINAL_STATUSES | PAUSE_STATUSES)
        ):
            elapsed_so_far = time.time() - st.session_state.pipeline_start_ts
            if elapsed_so_far >= 3.0:
                st.session_state.pipeline_end_ts = time.time()
            # else: skip — stale-cached terminal status, will re-check next poll
        # Backfill completed_agents from artifacts if SSE missed events
        for name, field in AGENT_OUTPUT_FIELD.items():
            if payload.get(field):
                st.session_state.completed_agents.add(name)
        if payload.get("critic_output"):
            st.session_state.completed_agents.add("critic")
    elif status == 202 and payload:
        st.session_state.pipeline_status = payload.get("pipeline_status", "initializing")


def _sync_external_hitl_decision(payload: dict) -> None:
    """
    Mirror decisions submitted outside this Streamlit session.

    Voice approval, ngrok calls, and another browser tab all hit FastAPI directly,
    so this tab needs to reconstruct the same result shape that api_approve()
    returns when the local buttons are clicked.
    """
    decision = (payload.get("hitl_decision") or "").lower()
    if decision not in {"approved", "rejected"}:
        return

    export_meta = payload.get("export") or {}
    jira_meta = export_meta.get("jira") or {}
    current = st.session_state.approval_result or {}

    st.session_state.approval_result = {
        **current,
        "run_id": payload.get("run_id") or st.session_state.run_id,
        "decision": decision,
        "message": f"Decision recorded: {decision}",
        "sheet_url": current.get("sheet_url") or export_meta.get("sheet_url"),
        "export_status": current.get("export_status") or export_meta.get("status"),
        "export_mode": current.get("export_mode") or export_meta.get("mode"),
        "export_detail": current.get("export_detail") or export_meta.get("detail"),
        "jira_url": current.get("jira_url") or jira_meta.get("url"),
        "jira_status": current.get("jira_status") or jira_meta.get("mode"),
        "jira_detail": current.get("jira_detail") or jira_meta.get("detail"),
        "jira_issue_key": current.get("jira_issue_key") or jira_meta.get("issue_key"),
        "pipeline_status": payload.get("pipeline_status"),
        "rejection_count": payload.get("hitl_rejection_count", 0),
        "export_finalized": bool(export_meta.get("finalized")),
    }


@st.cache_data(show_spinner=False)
def api_download_pdf(api_base_url: str, run_id: str) -> bytes:
    r = requests.get(f"{api_base_url.rstrip('/')}/download/{run_id}", timeout=60)
    r.raise_for_status()
    return r.content

# ──────────────────────────────────────────────────────────────────────────────
# UI components
# ──────────────────────────────────────────────────────────────────────────────

def render_header() -> None:
    ok, info = api_health()
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.title("BRD → Engineering Plan")
        st.caption("EM Copilot | Multi-Agent BRD-to-Engineering System with HITL")
    with col_b:
        if ok:
            st.success(f"API connected · {info}")
        else:
            st.error(f"API offline · {info}")
            # Show the URL only when the API isn't reachable — useful as a
            # troubleshooting hint, hidden otherwise to keep the header clean.
            st.caption(f"Base URL: {st.session_state.api_base_url}")


def render_sidebar() -> None:
    # Look up auth state once per render
    from src.security.google_auth import (
        is_configured as _g_configured,
        is_authenticated as _g_authed,
        render_signin_required as _g_signin,
        render_signed_in_chip as _g_chip,
    )
    _auth_needed = _g_configured() and not _g_authed()

    with st.sidebar:
        # Show "Signed in / Sign out" chip when authenticated
        _g_chip()

        st.header("Upload BRD")

        if _auth_needed:
            # NOT signed in — replace the file uploader + Generate button with a
            # sign-in CTA. The rest of the page (description, what-it-does copy)
            # is still visible because main() doesn't block.
            _g_signin("Sign in to upload a BRD and generate an engineering plan.")
        else:
            uploaded = st.file_uploader(
                "Drop a PDF, DOCX, or TXT BRD",
                type=["pdf", "docx", "txt"],
                accept_multiple_files=False,
            )
            if uploaded is not None:
                st.info("⚠️ **Demo Purpose Only:** This application is for demo purposes only. The AI can make mistakes.")
                run_in_flight = st.session_state.run_id is not None
                if st.button(
                    "Generate Engineering Plan",
                    type="primary",
                    use_container_width=True,
                    disabled=run_in_flight,
                    help=("Click 'Reset' below to start a new run."
                          if run_in_flight else None),
                ):
                    _reset_run()
                    content_type = uploaded.type or "application/octet-stream"
                    # Capture user-intent time BEFORE the blocking API call. If the
                    # server's /run-pipeline ever blocks on the validator or pipeline,
                    # this still measures the true wall-clock the EM experiences.
                    st.session_state.pipeline_start_ts = time.time()
                    st.session_state.pipeline_end_ts   = None
                    with st.spinner("Validating + dispatching agents…"):
                        resp = api_run_pipeline(uploaded.getvalue(), uploaded.name, content_type)
                    if resp:
                        st.session_state.run_id            = resp["run_id"]
                        st.success(f"Pipeline started · run_id `{resp['run_id']}`")
                        st.rerun()
                    else:
                        st.error(st.session_state.upload_error or "Upload failed")

        # Current run block first — pinned high so Reset is reachable without scroll
        if st.session_state.run_id:
            st.divider()
            st.subheader("Current run")
            st.code(st.session_state.run_id, language=None)
            st.caption(f"Status: `{st.session_state.pipeline_status or 'starting'}`")
            if st.button("Clear Plan & Reset", use_container_width=True):
                _reset_run()
                st.rerun()

        # Dev-time settings — collapsed by default so it never pushes Current run
        # off-screen. Most users (including the HF Space demo) never open it.
        with st.expander("⚙️ Advanced settings", expanded=False):
            new_url = st.text_input("API base URL", value=st.session_state.api_base_url)
            if new_url and new_url != st.session_state.api_base_url:
                st.session_state.api_base_url = new_url


def render_progress_chips() -> None:
    """Per-agent chips: Orchestrator → 5 specialists → Critic."""
    st.subheader("Agents Pipeline progress")
    completed = st.session_state.completed_agents
    artifacts = st.session_state.artifacts or {}
    status    = st.session_state.pipeline_status or ""

    # Orchestrator is "done" once we have brd_sections or status moves past init
    orch_done = bool(artifacts.get("brd_sections")) or status not in ("", "initializing", "starting")
    critic_done = bool(artifacts.get("critic_output"))

    chips: list[tuple[str, bool]] = [("Orchestrator", orch_done)]
    for agent_id, label in SPECIALIST_AGENTS:
        chips.append((label, agent_id in completed or bool(artifacts.get(AGENT_OUTPUT_FIELD[agent_id]))))
    chips.append(("Critic", "critic" in completed or critic_done))

    cols = st.columns(len(chips))
    for col, (label, done) in zip(cols, chips):
        with col:
            if done:
                st.markdown(
                    f"<div style='padding:8px;border-radius:8px;background:#16a34a;color:white;text-align:center;font-size:12px;font-weight:600;'>✓ {label}</div>",
                    unsafe_allow_html=True,
                )
            else:
                in_progress = (
                    status not in ("", "exported", "export_failed", "error", "awaiting_hitl", "rejected")
                )
                bg = "#3b82f6" if in_progress else "#374151"
                icon = "⟳" if in_progress else "○"
                st.markdown(
                    f"<div style='padding:8px;border-radius:8px;background:{bg};color:white;text-align:center;font-size:12px;font-weight:600;'>{icon} {label}</div>",
                    unsafe_allow_html=True,
                )

    # Status banner
    # Map backend pipeline_status values (lowercase, snake_case) to friendly UI text.
    # Keys MUST be lowercase to match what src/agents/pipeline.py writes into PipelineState.
    status_msg = {
        "initializing":  "🔄 Initializing…",
        "starting":      "🔄 Starting…",
        "dispatching":   "🚀 Specialists running in parallel…",
        "critic_review": "🔍 Critic reviewing complete bundle…",
        "revising":      f"♻️ Revision cycle (round {artifacts.get('revision_count', '?')})…",
        "awaiting_hitl": "⏸️ Awaiting your decision. Please review and confirm below.",
        "exported":      "✅ Approved · Added Artifacts to Jira ticket",
        "export_failed": "⚠️ Approved but export failed",
        "rejected":      "❌ Rejected · Audit row logged to Google Sheets",
        "error":         "❌ Pipeline error",
    }.get(status, status or "")
    # Status + processing time on a single horizontal row.
    # Flex layout keeps "Current Status" on the left and "Total Processing Time"
    # right-aligned, on the same line regardless of message length.
    elapsed_str = _fmt_duration(_processing_seconds())

    # Token counts (in / out) — sourced from PipelineState; absent on runs that
    # haven't completed yet. Format with thousands separators for readability.
    arts = st.session_state.artifacts or {}
    _tin  = int(arts.get("total_input_tokens",  0) or 0)
    _tout = int(arts.get("total_output_tokens", 0) or 0)
    tokens_str = f"{_tin:,} in / {_tout:,} out" if (_tin or _tout) else "—"

    st.markdown(
        "<div style='display:flex; justify-content:space-between; align-items:center; "
        "flex-wrap:wrap; gap:12px; margin-top:20px;margin-bottom:20px;'>"
        f"<div><strong>Current Status:</strong> {status_msg or '—'}</div>"
        f"<div><strong>Total Processing Time:</strong> "
        f"<code style='background:#f3f4f6;padding:2px 6px;border-radius:4px;'>{elapsed_str}</code></div>"
        f"<div><strong>Tokens used (in / out):</strong> "
        f"<code style='background:#f3f4f6;padding:2px 6px;border-radius:4px;'>{tokens_str}</code></div>"
        "</div>",
        unsafe_allow_html=True,
    )


def render_event_log() -> None:
    """Collapsible raw event feed."""
    events = st.session_state.events or []
    with st.expander(f"Raw event log ({len(events)} events)", expanded=False):
        if not events:
            st.caption("No events yet.")
            return
        for i, ev in enumerate(reversed(events[-100:])):
            i_idx = len(events) - i
            etype = ev.get("type", "event")
            rest  = {k: v for k, v in ev.items() if k != "type"}
            st.text(f"[{i_idx:>3}] {etype}: {json.dumps(rest, default=str)}")


def _badge_chip(badge_value: str) -> str:
    label, color = BADGE_STYLE.get(badge_value, BADGE_STYLE["unknown"])
    return (
        f"<span style='padding:6px 14px;border-radius:9999px;"
        f"background:{color};color:white;font-weight:700;font-size:14px;'>{label}</span>"
    )


def render_critic_scores() -> None:
    artifacts = st.session_state.artifacts or {}
    critic    = artifacts.get("critic_output")
    if not critic:
        return

    st.subheader("Critic — quality assessment")
    badge  = critic.get("badge", "unknown")
    overall = critic.get("overall_score", 0.0)
    rev_num = critic.get("revision_number", 0)

    head_l, head_r = st.columns([3, 1])
    with head_l:
        st.markdown(_badge_chip(badge), unsafe_allow_html=True)
        st.caption(f"Revision {rev_num} · Overall **{overall:.2f} / 5.0**")
    with head_r:
        if critic.get("requires_revision"):
            st.warning("Critic requested revision")
        else:
            st.success("Quality gate passed")

    dim_cols = st.columns(4)
    for col, key in zip(dim_cols, ["groundedness", "completeness", "consistency", "actionability"]):
        dim = critic.get(key) or {}
        with col:
            score = dim.get("score", 0.0)
            thr   = dim.get("threshold", 0.0)
            passed = dim.get("passed", False)
            delta_str = f"≥ {thr:.2f}"
            st.metric(
                label=key.capitalize(),
                value=f"{score:.2f}",
                delta=delta_str + (" ✓" if passed else " ✗"),
                delta_color="normal" if passed else "inverse",
            )

    # History chart of scores across revisions
    history = artifacts.get("critic_scores_history") or []
    if len(history) > 1:
        try:
            import pandas as pd
            df = pd.DataFrame(history).set_index("revision")[
                ["groundedness", "completeness", "consistency", "actionability", "overall"]
            ]
            st.caption("Score history (per revision)")
            st.line_chart(df)
        except Exception:
            st.caption("(score-history chart skipped — pandas unavailable)")

    # Consistency + hallucination findings
    issues = critic.get("consistency_issues") or []
    halls  = critic.get("hallucination_flags") or []
    if issues or halls:
        with st.expander(
            f"Critic findings · {len(issues)} consistency · {len(halls)} hallucination",
            expanded=False,
        ):
            if issues:
                st.markdown("**Consistency issues**")
                for issue in issues:
                    st.markdown(
                        f"- *{issue.get('severity', '')}* — {issue.get('conflict_description', '')} "
                        f"({', '.join(issue.get('agents_involved', []))})"
                    )
            if halls:
                st.markdown("**Hallucination flags**")
                for h in halls:
                    st.markdown(
                        f"- `{h.get('agent', '')}` — *{h.get('status', '')}* — {h.get('claim', '')}"
                    )


# ─── Artifact renderers ───────────────────────────────────────────────────────

def _render_citations(citations: list[str], label: str = "Citations") -> None:
    if not citations:
        return
    with st.expander(f"{label} ({len(citations)})", expanded=False):
        for c in citations:
            st.code(c, language=None)


def render_plan(plan: dict) -> None:
    st.markdown(f"**Total duration:** {plan.get('total_duration_weeks', '?')} weeks · "
                f"**Confidence:** {plan.get('confidence_score', 0):.2f}")
    team = plan.get("team_composition") or {}
    if team:
        st.caption("Team composition: " + ", ".join(f"{k} × {v}" for k, v in team.items()))

    for phase in plan.get("phases", []):
        st.markdown(f"### 📅 {phase.get('name')} — {phase.get('duration_weeks', '?')} weeks")
        objs = phase.get("objectives") or []
        if objs:
            st.markdown("**Objectives**")
            for o in objs:
                st.markdown(f"- {o}")
        ms = phase.get("milestones") or []
        if ms:
            try:
                import pandas as pd
                st.dataframe(pd.DataFrame(ms), hide_index=True, use_container_width=True)
            except Exception:
                for m in ms:
                    st.markdown(f"- W{m.get('week')} · **{m.get('name')}** ({m.get('owner_role')}) — {m.get('deliverable')}")

    risks = plan.get("risks") or []
    if risks:
        st.markdown("### ⚠️ Risks")
        try:
            import pandas as pd
            st.dataframe(pd.DataFrame(risks), hide_index=True, use_container_width=True)
        except Exception:
            for r in risks:
                st.markdown(f"- **{r.get('description')}** · L={r.get('likelihood')} I={r.get('impact')} — *mitigation:* {r.get('mitigation')}")

    if plan.get("reflection_notes"):
        with st.expander("Reflection notes (self-critique)"):
            st.write(plan["reflection_notes"])

    _render_citations(plan.get("citations") or [])


def render_schedule(sched: dict) -> None:
    st.markdown(
        f"**Total effort:** {sched.get('total_effort_days', 0):.1f} days · "
        f"**Buffer:** {sched.get('buffer_weeks', 0)} weeks · "
        f"**Confidence:** {sched.get('confidence_score', 0):.2f}"
    )
    sprints = sched.get("sprints") or []
    if sprints:
        try:
            import pandas as pd
            df = pd.DataFrame(sprints)
            if "deliverables" in df:
                df["deliverables"] = df["deliverables"].apply(lambda xs: " · ".join(xs) if isinstance(xs, list) else xs)
            if "team_members" in df:
                df["team_members"] = df["team_members"].apply(lambda xs: ", ".join(xs) if isinstance(xs, list) else xs)
            st.dataframe(df, hide_index=True, use_container_width=True)
        except Exception:
            for s in sprints:
                st.markdown(f"- Sprint {s.get('sprint')} ({s.get('week_range')}) · {s.get('effort_days')}d")

    crit_path = sched.get("critical_path") or []
    if crit_path:
        st.markdown("**Critical path:** " + " → ".join(crit_path))
    _render_citations(sched.get("citations") or [])
    _render_citations(sched.get("comparable_projects") or [], "Comparable historical projects")


def render_architecture(arch: dict) -> None:
    st.markdown(f"**Pattern:** {arch.get('pattern', '?')} · **Deployment:** {arch.get('deployment_model', '?')}")
    if arch.get("pattern_justification"):
        st.markdown("**Justification:** " + arch["pattern_justification"])

    svg     = arch.get("diagram_svg")
    mermaid = arch.get("diagram_mermaid")
    if svg or mermaid:
        st.markdown("**Architecture diagram**")

        if svg:
            # Kroki-rendered SVG — fastest path, no client-side JS needed.
            # The SVG is trusted (we made the request, we read the response).
            st.markdown(svg, unsafe_allow_html=True)
        elif mermaid:
            # Kroki failed/skipped → render client-side with mermaid.js via the
            # UMD build (NOT the ES module). UMD avoids the type=module timing
            # issue where the script loads AFTER DOMContentLoaded fires.
            #
            # We also unconditionally show the syntax-highlighted source via
            # st.code BELOW the iframe — so even if the iframe fails for any
            # reason (CDN blocked, browser extension, etc.) the user is never
            # left with a blank rectangle.
            # pyrefly: ignore [missing-import]
            import streamlit.components.v1 as components
            import uuid as _uuid
            _mmd_id = f"mmd-{_uuid.uuid4().hex[:8]}"   # unique per render to bust iframe cache
            # JSON-encode the source so embedded newlines / quotes survive transport
            import json as _json
            _src_js = _json.dumps(mermaid)
            mermaid_html = f"""
<div id="{_mmd_id}" style="background:white;padding:12px;border-radius:8px;min-height:60px;color:#333;">
  <div style="color:#888;font-family:system-ui;font-size:12px;">Loading mermaid.js&hellip;</div>
</div>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
(function() {{
  var host = document.getElementById("{_mmd_id}");
  function fail(msg) {{
    host.innerHTML = '<div style="color:#c00;font-family:monospace;padding:8px;font-size:13px;">'
                   + '⚠ Mermaid client-side render failed: ' + msg
                   + '<br><br>The source code is shown below — use it in any Mermaid-aware tool.'
                   + '</div>';
  }}
  if (typeof mermaid === "undefined") {{ fail("mermaid library did not load (CDN blocked?)"); return; }}
  try {{
    mermaid.initialize({{ startOnLoad: false, theme: "neutral", securityLevel: "loose" }});
    var src = {_src_js};
    mermaid.render("{_mmd_id}-svg", src).then(function(result) {{
      host.innerHTML = result.svg;
    }}).catch(function(e) {{
      fail((e && e.message) || String(e));
    }});
  }} catch (e) {{
    fail((e && e.message) || String(e));
  }}
}})();
</script>
"""
            components.html(mermaid_html, height=520, scrolling=True)

        # Always render the source as fallback — never leave the user stuck
        # if Kroki failed AND mermaid.js failed. They can copy-paste into
        # https://mermaid.live, GitHub, Jira, Confluence, or VSCode.
        if mermaid:
            with st.expander(
                "📋 Mermaid source (copy into Jira / Confluence / GitHub / mermaid.live)",
                expanded=False,
            ):
                st.code(mermaid, language="mermaid")

    components = arch.get("components") or []
    if components:
        st.markdown("**Components**")
        try:
            import pandas as pd
            df = pd.DataFrame(components)
            if "interfaces" in df:
                df["interfaces"] = df["interfaces"].apply(lambda xs: ", ".join(xs) if isinstance(xs, list) else xs)
            st.dataframe(df, hide_index=True, use_container_width=True)
        except Exception:
            for c in components:
                st.markdown(f"- **{c.get('name')}** ({c.get('technology')}) — {c.get('responsibility')}")

    nfrs = arch.get("nfr_mappings") or []
    if nfrs:
        st.markdown("**NFR mappings**")
        for n in nfrs:
            st.markdown(f"- *{n.get('nfr')}* → {n.get('architecture_decision')}")

    data_flow = arch.get("data_flow") or []
    if data_flow:
        st.markdown("**Data flow:** " + " → ".join(data_flow))
    _render_citations(arch.get("citations") or [])


def render_poc(poc: dict) -> None:
    st.markdown(f"**Hypothesis:** {poc.get('poc_hypothesis', '')}")
    st.markdown(
        f"**Duration:** {poc.get('duration_weeks', '?')} weeks · "
        f"**Team size:** {poc.get('team_size', '?')}"
    )
    col_in, col_out = st.columns(2)
    with col_in:
        st.markdown("**In scope**")
        for s in poc.get("scope_in") or []:
            st.markdown(f"- {s}")
    with col_out:
        st.markdown("**Out of scope**")
        for s in poc.get("scope_out") or []:
            st.markdown(f"- {s}")

    crit = poc.get("success_criteria") or []
    if crit:
        st.markdown("**Success criteria**")
        try:
            import pandas as pd
            st.dataframe(pd.DataFrame(crit), hide_index=True, use_container_width=True)
        except Exception:
            for c in crit:
                st.markdown(f"- {c.get('metric')} · target {c.get('target_value')} — *measure:* {c.get('measurement_method')}")

    if poc.get("risk_if_poc_fails"):
        st.markdown(f"**Risk if PoC fails:** {poc['risk_if_poc_fails']}")
    _render_citations(poc.get("citations") or [])


def render_tech_stack(stack: dict) -> None:
    rec = stack.get("recommended_option", "?")
    st.markdown(f"**Recommended:** `{rec}`")
    if stack.get("recommendation_rationale"):
        st.markdown("**Rationale:** " + stack["recommendation_rationale"])

    options = stack.get("options") or []
    if options:
        try:
            import pandas as pd
            rows = []
            for o in options:
                rows.append({
                    "option":            o.get("name"),
                    "recommended":       "★" if o.get("name") == rec else "",
                    "scalability":       o.get("scalability_rating"),
                    "familiarity":       o.get("team_familiarity_rating"),
                    "integration_risk":  o.get("integration_risk"),
                    "monthly_cost_usd":  o.get("estimated_monthly_cost_usd"),
                    "pros":              " · ".join(o.get("pros") or []),
                    "cons":              " · ".join(o.get("cons") or []),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        except Exception:
            for o in options:
                st.markdown(f"- **{o.get('name')}** — scalability {o.get('scalability_rating')} / familiarity {o.get('team_familiarity_rating')}")
    _render_citations(stack.get("citations") or [])


def _log_pdf_download(api_base_url: str, run_id: str, email: str) -> None:
    try:
        requests.post(
            f"{api_base_url.rstrip('/')}/log-download/{run_id}",
            json={"email": email},
            timeout=5
        )
    except Exception:
        pass


def render_artifacts() -> None:
    artifacts = st.session_state.artifacts or {}
    have_any = any(artifacts.get(field) for _, field in AGENT_OUTPUT_FIELD.items())
    if not have_any:
        return

    # Title bar + Download PDF button on the right
    title_col, download_col = st.columns([4, 1], vertical_alignment="center")
    with title_col:
        st.subheader("Artifacts")
    with download_col:
        rid = st.session_state.run_id
        if rid:
            try:
                from src.security.google_auth import get_user_email
                user_email = get_user_email()
                pdf_bytes = api_download_pdf(st.session_state.api_base_url, rid)
                st.download_button(
                    "⬇ Download PDF",
                    data=pdf_bytes,
                    file_name=f"em-copilot-{rid}-artifacts.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    on_click=_log_pdf_download,
                    args=(st.session_state.api_base_url, rid, user_email),
                )
            except Exception:
                st.button("⬇ Download PDF", disabled=True, use_container_width=True,
                          help="PDF not yet available — pipeline still running.")
        else:
            st.button("⬇ Download PDF", disabled=True, use_container_width=True)

    tabs = st.tabs(["Plan", "Schedule", "Architecture", "PoC", "Tech Stack"])
    with tabs[0]:
        plan = artifacts.get("plan_output")
        if plan:
            render_plan(plan)
        else:
            st.caption("Pending…")
    with tabs[1]:
        sched = artifacts.get("schedule_output")
        if sched:
            render_schedule(sched)
        else:
            st.caption("Pending…")
    with tabs[2]:
        arch = artifacts.get("arch_output")
        if arch:
            render_architecture(arch)
        else:
            st.caption("Pending…")
    with tabs[3]:
        poc = artifacts.get("poc_output")
        if poc:
            render_poc(poc)
        else:
            st.caption("Pending…")
    with tabs[4]:
        stack = artifacts.get("stack_output")
        if stack:
            render_tech_stack(stack)
        else:
            st.caption("Pending…")


def _build_voice_briefing(artifacts: dict) -> str:
    """
    Compact plain-text summary of the generated artifacts, handed to the
    ElevenLabs voice agent as the {{artifact_brief}} dynamic variable so it can
    answer the EM's questions about the plan before they approve or reject.
    """
    if not artifacts:
        return "No engineering plan has been generated yet."

    def _clip(text: object, n: int) -> str:
        s = str(text or "").strip()
        return s if len(s) <= n else s[: n - 1] + "\u2026"

    lines: list[str] = []

    crit = artifacts.get("critic_output") or {}
    if crit:
        lines.append(
            f"CRITIC VERDICT: {str(crit.get('badge', '?')).upper()} badge, "
            f"overall quality {crit.get('overall_score', 0):.2f} out of 5 "
            f"(revision {crit.get('revision_number', 0)})."
        )

    plan = artifacts.get("plan_output") or {}
    if plan:
        phases = plan.get("phases") or []
        phase_str = "; ".join(
            f"{p.get('name', '?')} ({p.get('duration_weeks', '?')}w)" for p in phases
        ) or "n/a"
        team = plan.get("team_composition") or {}
        team_str = ", ".join(f"{k} x{v}" for k, v in team.items()) or "n/a"
        lines.append(
            f"PLAN: {plan.get('total_duration_weeks', '?')} weeks total across "
            f"{len(phases)} phases - {phase_str}. Team: {team_str}."
        )
        risks = plan.get("risks") or []
        if risks:
            risk_str = "; ".join(
                f"{_clip(r.get('description'), 90)} "
                f"(likelihood {r.get('likelihood', '?')}, impact {r.get('impact', '?')})"
                for r in risks[:3]
            )
            lines.append(f"TOP RISKS: {risk_str}.")

    sched = artifacts.get("schedule_output") or {}
    if sched:
        cp = sched.get("critical_path") or []
        lines.append(
            f"SCHEDULE: {sched.get('total_effort_days', 0):.0f} effort-days, "
            f"{sched.get('buffer_weeks', '?')} weeks buffer. "
            f"Critical path: {' -> '.join(cp) if cp else 'n/a'}."
        )

    arch = artifacts.get("arch_output") or {}
    if arch:
        citations = arch.get("citations") or []
        is_tavily = any("tavily" in c.lower() or "web_grounding" in c.lower() for c in citations)
        pattern_phrase = "pattern" if not is_tavily else "provisional web-grounded pattern"
        comps = ", ".join(
            c.get("name", "?") for c in (arch.get("components") or [])
        ) or "n/a"
        lines.append(
            f"ARCHITECTURE: {arch.get('pattern', '?')} {pattern_phrase}, deployed on "
            f"{arch.get('deployment_model', '?')}. Components: {comps}."
        )

    poc = artifacts.get("poc_output") or {}
    if poc:
        lines.append(
            f"PROOF OF CONCEPT: {_clip(poc.get('poc_hypothesis'), 200)} "
            f"({poc.get('duration_weeks', '?')} weeks, team of {poc.get('team_size', '?')})."
        )

    stack = artifacts.get("stack_output") or {}
    if stack:
        citations = stack.get("citations") or []
        is_tavily = any("tavily" in c.lower() or "web_grounding" in c.lower() for c in citations)
        rec_phrase = "recommended option is" if not is_tavily else "provisional web-grounded recommendation is"
        lines.append(
            f"TECH STACK: {rec_phrase} {stack.get('recommended_option', '?')}. "
            f"{_clip(stack.get('recommendation_rationale'), 240)}"
        )

    briefing = "\n".join(lines).strip()
    return briefing[:2000] if briefing else "The engineering plan is still being generated."


def render_hitl_alert() -> None:
    status = st.session_state.pipeline_status
    if status != "awaiting_hitl":
        return

    decision_made = bool(st.session_state.get("approval_result"))
    if decision_made:
        return

    st.markdown(
        """
        <div style="background-color: #fff9db; border-left: 5px solid #f59f00; padding: 16px; border-radius: 8px; margin-bottom: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); font-family: system-ui, -apple-system, sans-serif;">
            <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
                <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 250px;">
                    <span style="font-size: 24px;">⏸️</span>
                    <div>
                        <div style="color: #856404; font-weight: bold; font-size: 15px; margin-bottom: 2px;">Action Required: Approval Needed</div>
                        <div style="color: #665014; font-size: 13px;">The multi-agent pipeline is paused. Please review the generated plans and jump down to submit your decision.</div>
                    </div>
                </div>
                <a href="#decision-gate" target="_self" style="background-color: #f59f00; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 600; display: inline-flex; align-items: center; gap: 6px; transition: background-color 0.2s; box-shadow: 0 2px 4px rgba(245, 159, 0, 0.2);">
                    👇 Scroll to Decision Gate
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_hitl_gate() -> None:
    status = st.session_state.pipeline_status
    if status != "awaiting_hitl":
        return

    # Anchor target for dynamic page scrolling
    st.markdown('<div id="decision-gate"></div>', unsafe_allow_html=True)

    rejection_count = st.session_state.rejection_count
    #gate_label = "Gate" if rejection_count == 0 else f"Gate {min(rejection_count + 1, 2)}" # to-do 
    st.subheader(f"Decision Gate")
    st.info("Upon approval, the artifacts will be exported to Jira and this request is logged in EM Dashboard")

    if rejection_count >= 2:
        st.error("Two rejections recorded — pipeline has escalated to audit review.")
        return

    # ── ElevenLabs Voice Integration ──
    from src.integrations.voice import get_voice_agent_config
    voice_cfg = get_voice_agent_config()
    if voice_cfg.get("enabled"):
        st.info("🎙️ **Voice Approval (ElevenLabs)**: Discuss the artifacts with the AI and give verbal approval below.")
        
        agent_id = voice_cfg.get("agent_id")
        rid      = st.session_state.run_id or ""
        # pyrefly: ignore [missing-import]
        import streamlit.components.v1 as components

        # Pass run_id (and optionally api_base_url) to the agent via
        # dynamic-variables. The agent's webhook tool can then call
        #     POST {api_base_url}/approve/{run_id}
        # using these substitutions. The agent's system prompt should reference
        # them as {{run_id}}, {{api_base_url}}, and {{artifact_brief}}.
        import html
        dyn_vars_json = html.escape(json.dumps({
            "run_id":         rid,
            "api_base_url":   st.session_state.api_base_url,
            "artifact_brief": _build_voice_briefing(st.session_state.artifacts or {}),
        }))

        # ElevenLabs Conversational AI Web Component
        # JSON is html-escaped, so the double-quoted attribute stays valid even
        # when the artifact briefing contains quotes or apostrophes.
        html_code = f"""
        <div style="display: flex; justify-content: center; padding: 10px;">
            <elevenlabs-convai
                agent-id="{agent_id}"
                dynamic-variables="{dyn_vars_json}"
            ></elevenlabs-convai>
            <script src="https://elevenlabs.io/convai-widget/index.js" async type="text/javascript"></script>
        </div>
        """
        components.html(html_code, height=150)
        st.caption(
            f"🎙️ Voice agent has run_id `{rid or '(none)'}` — when you approve verbally, "
            "the Agent will record the your decision for this request."
        )
    else:
        st.caption("Voice approval disabled. (Configure ELEVENLABS_AGENT_ID in .env to enable)")

    decision_made = bool(st.session_state.get("approval_result"))
    if decision_made:
        prior = str((st.session_state.approval_result or {}).get("decision", "recorded")).lower()
        st.info(f"Decision already recorded for this run \u2014 **{prior}**. This gate is locked.")

    with st.form("hitl_form"):
        reviewer = st.text_input("Reviewer", value="Engineering Manager", disabled=decision_made)
        em_rating = st.slider(
            "EM rating (1=unusable · 5=excellent)",
            min_value=1, max_value=5, value=4, disabled=decision_made,
        )
        notes = st.text_area("Notes (optional, required for reject)", value="", disabled=decision_made)
        col_a, col_r = st.columns(2)
        with col_a:
            approve_clicked = st.form_submit_button("✅ Approve & export", type="primary", use_container_width=True, disabled=decision_made)
        with col_r:
            reject_clicked  = st.form_submit_button("✖ Reject", use_container_width=True, disabled=decision_made)

    if approve_clicked:
        from src.security.google_auth import get_user_email
        user_email = get_user_email()
        with st.spinner("Recording decision · Pushing to Jira, writing to Google Sheets…"):
            result = api_approve(st.session_state.run_id, "approved", reviewer, notes, em_rating, user_email)
        if result:
            st.session_state.approval_result = result
            refresh_artifacts()
            st.rerun()
    elif reject_clicked:
        if not notes.strip():
            st.warning("Please add notes explaining the rejection.")
        else:
            from src.security.google_auth import get_user_email
            user_email = get_user_email()
            with st.spinner("Recording rejection…"):
                result = api_approve(st.session_state.run_id, "rejected", reviewer, notes, em_rating, user_email)
            if result:
                st.session_state.approval_result = result
                refresh_artifacts()
                st.rerun()


def render_export_result() -> None:
    """
    HITL outcome rendering. Mirrors the backend's two-phase logic:
        Approved → Sheets export + Jira push (both surfaced)
        Rejected → Sheets export ONLY (no Jira). Reject is recorded as an
                   audit-trail row in the same sheet, but artifacts are not
                   pushed to Jira because the EM did not approve them.
        No decision → nothing happens (pipeline waits at awaiting_hitl).

    Until the EM clicks Approve or Reject, this function renders nothing
    related to export — it simply does not run because there's no
    approval_result yet.
    """
    status      = st.session_state.pipeline_status
    result      = st.session_state.approval_result or {}
    artifacts   = st.session_state.artifacts or {}
    export_meta = artifacts.get("export") or {}
    decision    = (result.get("decision") or "").lower()

    def _render_sheets_block(*, on_rejection: bool = False) -> None:
        """Sheets banner — shared between approved and rejected paths."""
        mode      = result.get("export_mode")   or export_meta.get("mode")
        detail    = result.get("export_detail") or export_meta.get("detail")
        sheet_url = result.get("sheet_url")     or export_meta.get("sheet_url")

        if mode == "sheets":
            verb = "Decision logged" if on_rejection else "Artifacts exported"
            st.success(f"{verb} to Google Sheets")
            if detail:
                st.caption(detail)
            if sheet_url:
                btn_label = "Open Google Sheet — view rundown" if on_rejection else "Open Google Sheet"
                st.link_button(btn_label, sheet_url, type="primary")
        elif mode == "local":
            reason = export_meta.get("fallback_reason") or "Google Sheets credentials unavailable"
            st.warning(
                f"Sheets export skipped — wrote local CSV bundle instead. Reason: {reason}"
            )
            if detail:
                st.caption(detail)
            files = export_meta.get("files") or []
            if files:
                with st.expander(f"Files written ({len(files)})", expanded=False):
                    for fp in files:
                        st.code(fp, language=None)
            if sheet_url:
                st.caption(f"Bundle URL: {sheet_url}")
        # else: mode is None or "failed" — handled below in the status branch

    def _render_jira_block() -> None:
        """Jira section — ONLY called on the approval path."""
        jira_meta = export_meta.get("jira") or {}
        jira_url  = result.get("jira_url")     or jira_meta.get("url")
        jira_mode = result.get("jira_status")  or jira_meta.get("mode") or "skipped"
        jira_key  = result.get("jira_issue_key") or jira_meta.get("issue_key")
        jira_det  = result.get("jira_detail")  or jira_meta.get("detail")
        finalized = bool(result.get("export_finalized")) or bool(export_meta.get("finalized"))

        if jira_url:
            st.success(f"Pushed to Jira: {jira_key}")
            if jira_det:
                st.caption(jira_det)
            st.link_button(f"Open Jira issue {jira_key}", jira_url, type="primary")
        elif jira_mode == "failed":
            st.warning("Jira push failed")
            if jira_det:
                st.code(jira_det)
        elif not finalized and not jira_meta:
            st.info("Jira push in progress - creating the Epic via the MCP server...")
        else:
            st.caption(jira_det or "Jira push was skipped")

    # ── Branch 1: Approval succeeded → Sheets + Jira ────────────────────────
    if status == "exported":
        _render_sheets_block(on_rejection=False)
        _render_jira_block()
        return

    # ── Branch 2: Approval attempted but Sheets failed ──────────────────────
    if status == "export_failed":
        st.error("Export failed")
        if export_meta.get("error"):
            st.code(export_meta["error"])
        return

    # ── Branch 3: Rejection — Sheets only, NO Jira (per HITL spec) ──────────
    if decision == "rejected":
        rc = st.session_state.rejection_count
        if rc >= 2:
            st.warning(
                f"Second rejection recorded (count = {rc}) — flagged for audit review. "
                "Pipeline will not retry."
            )
        else:
            st.info(
                f"Rejection recorded (count = {rc}). "
                "Artifacts logged to Google Sheets as a rejected-decision audit row; "
                "Jira push was skipped because EM did not approve."
            )
        _render_sheets_block(on_rejection=True)
        return

    # ── Branch 4: No decision yet (status == awaiting_hitl, no approval_result) ─
    # Nothing to render — the HITL form is shown by render_hitl_gate().
    # Per spec: "EM doesn't give any decision → do nothing. Just wait."
    return


def render_errors() -> None:
    artifacts = st.session_state.artifacts or {}
    errs = artifacts.get("errors") or []
    if errs:
        # Check if it's an OpenAI key or token/rate limit error
        openai_key_or_limit_error = False
        for e in errs:
            e_lower = str(e).lower()
            if any(term in e_lower for term in [
                "archived", "no longer accessible", "not_authorized_invalid_project",
                "authenticationerror", "invalid_request_error", "401", "rate_limit", 
                "quota", "token limit", "expired", "insufficient_quota"
            ]):
                openai_key_or_limit_error = True
                break
        
        if openai_key_or_limit_error:
            st.error("Sorry, your OpenAI API key is expired or OpenAI tokens limit has reached, please try again after some time.")
            with st.expander("Show raw error details", expanded=False):
                for e in errs:
                    st.code(e)
        else:
            st.error("Pipeline errors")
            for e in errs:
                st.code(e)


# ──────────────────────────────────────────────────────────────────────────────
# Main app
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="EM Copilot — BRD → Engineering Plan",
        page_icon="🧭",
        layout="wide",
    )

    # ── Optional Google Sign-In — non-blocking ─────────────────────────────
    # The page (header + description) renders for EVERYONE. The actual file
    # upload and "Generate Engineering Plan" button are gated behind sign-in
    # inside render_sidebar() — so visitors can read what the app does, but
    # only signed-in users can trigger work that costs LLM tokens.
    # No-op when GOOGLE_OAUTH_* env vars are unset (local dev).
    from src.security.google_auth import process_callback as _auth_callback
    _auth_callback()

    _init_state()
    render_header()
    render_sidebar()

    rid = st.session_state.run_id
    if not rid:
        st.info("👈 Upload a BRD and click **Generate Engineering Plan** to begin.")
        st.markdown(
            "**What this does:** Security validation → Orchestrator parses BRD → "
            "5 specialist agents run in parallel (Plan, Schedule, Architecture, PoC, Tech Stack) "
            "→ Critic scores the bundle → Confirmation gate → Push to Jira, export to Google Sheets on approve."
        )
        return

    # Fetch latest state on every render
    consume_new_events()
    refresh_artifacts()

    render_hitl_alert()
    render_progress_chips()
    render_event_log()
    render_critic_scores()
    render_artifacts()
    render_errors()
    render_hitl_gate()
    render_export_result()

    # Auto-rerun while the pipeline is still active. Crucially we keep polling at
    # the HITL gate (awaiting_hitl) too: a decision made outside this browser tab
    # — voice approval, ngrok webhook, another tab — only reaches the UI when
    # refresh_artifacts() -> _sync_external_hitl_decision() runs on a rerun. Poll
    # slowly while paused so the HITL form and voice widget stay responsive.
    status = st.session_state.pipeline_status or ""
    _ar = st.session_state.get("approval_result") or {}
    run_finalized = bool(_ar.get("export_finalized"))
    # Poll until the run hits a hard error OR the EM's decision is fully processed
    # server-side (Sheets + Jira + Pinecone done -> finalized). This lets a voice
    # approval surface its COMPLETE result and stops the UI freezing on a
    # half-finished export (e.g. Jira still pushing the Epic).
    if status not in ("error", "export_failed") and not run_finalized:
        interval = HITL_POLL_INTERVAL_SEC if status in PAUSE_STATUSES else POLL_INTERVAL_SEC
        time.sleep(interval)
        st.rerun()


if __name__ == "__main__":
    main()
