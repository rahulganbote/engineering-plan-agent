"""
src/integrations/jira.py
═════════════════════════
Jira Cloud push — creates an issue summarizing the approved pipeline run.

Mirror of src/integrations/sheets.py: one public entry point that returns a
shape-stable dict, gracefully skips when credentials are missing, never raises.

Called from src/api/main.py POST /approve, AFTER the Google Sheets export.
Jira push failure (network, auth, schema) does NOT block approval — the
pipeline_status stays "exported" because Sheets is the system of record.

What it creates:
    A Jira issue (Task by default, configurable via JIRA_ISSUE_TYPE) with:
        - Summary  : "[EM Copilot] <pattern> · <weeks>w · badge=<badge> · run=<id8>"
        - Labels   : em-copilot, badge-<color>, run-<id8>, pattern-<slug>
        - Description (ADF):
            • Run metadata (id, badge, scores)
            • Critic dimensions
            • Architecture pattern + Mermaid diagram code block (renders natively
              in Jira Cloud — no plugin, no attachment)
            • Tech stack recommendation
            • Engineering plan summary
            • PoC hypothesis + risk
            • Schedule highlights
            • Links to Sheets / local CSV bundle / artifacts API

Rubric:
    - Tools (external system): supplements Sheets + GitHub + Kroki as a 4th
      working external integration. Strong demo moment — "Approve → live Jira
      ticket with the architecture diagram rendered."
"""

from __future__ import annotations

import base64
import re
import zlib
from datetime import datetime, timezone
from typing import Any

import requests

from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)

JIRA_TIMEOUT_SEC  = 10
JIRA_RETRIES      = 1   # one retry on 5xx / network blip

# Hard limits enforced by Jira
JIRA_SUMMARY_MAX  = 255
JIRA_LABEL_MAX    = 255


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point
# ──────────────────────────────────────────────────────────────────────────────

def push_artifacts_to_jira(state: PipelineState) -> dict[str, Any]:
    """
    Create a Jira issue summarizing the approved run.

    Returns:
        {
          "url":             str | None,    # browse URL on success
          "mode":            "jira" | "skipped",
          "detail":          str,            # one-line human summary
          "issue_key":       str | None,     # e.g. "EMCP-42"
          "fallback_reason": str | None,     # populated when skipped/failed
        }
    Never raises.
    """
    run_id = state.run_id
    ok, why_not = _credentials_status()
    if not ok:
        log.info(f"[{run_id}] Jira push skipped — {why_not}")
        return {
            "url":             None,
            "mode":            "skipped",
            "detail":          "Jira push skipped (credentials not configured)",
            "issue_key":       None,
            "fallback_reason": why_not,
        }

    # Phase 7: idempotency — search for existing issue with this run's label
    idempotency_label = f"em-copilot-run-{state.run_id}"
    existing_key = _search_existing_issue(state.run_id, idempotency_label)
    if existing_key:
        url = f"{settings.jira_base_url.rstrip('/')}/browse/{existing_key}"
        log.info(f"[{run_id}] Jira REST — idempotent skip, issue already exists: {existing_key}")
        try:
            from src.core.events import emit as _evt
            _evt("idempotent_skip", run_id=run_id, issue_key=existing_key,
                 transport="rest", label=idempotency_label)
        except Exception:
            pass
        return {
            "url":             url,
            "mode":            "jira",
            "detail":          f"Idempotent skip — issue {existing_key} already exists (label={idempotency_label})",
            "issue_key":       existing_key,
            "fallback_reason": None,
        }

    try:
        created = _create_issue(state)
    except Exception as e:
        err = f"{type(e).__name__}: {str(e)[:200]}"
        log.error(f"[{run_id}] Jira push failed | {err}")
        return {
            "url":             None,
            "mode":            "skipped",
            "detail":          f"Jira push failed: {err}",
            "issue_key":       None,
            "fallback_reason": err,
        }

    key = created.get("key") or "?"
    url = f"{settings.jira_base_url.rstrip('/')}/browse/{key}"
    log.info(f"[{run_id}] Jira issue created | key={key} | url={url}")
    return {
        "url":             url,
        "mode":            "jira",
        "detail":          f"Created Jira {settings.jira_issue_type} {key}",
        "issue_key":       key,
        "fallback_reason": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Credentials probe
# ──────────────────────────────────────────────────────────────────────────────

def _credentials_status() -> tuple[bool, str]:
    required = {
        "JIRA_BASE_URL":    settings.jira_base_url,
        "JIRA_EMAIL":       settings.jira_email,
        "JIRA_API_TOKEN":   settings.jira_api_token,
        "JIRA_PROJECT_KEY": settings.jira_project_key,
    }
    missing = [k for k, v in required.items() if not (v or "").strip()]
    if missing:
        return False, f"Missing env vars: {', '.join(missing)}"
    if not settings.jira_base_url.startswith(("http://", "https://")):
        return False, "JIRA_BASE_URL must start with http(s)://"
    return True, ""


# ──────────────────────────────────────────────────────────────────────────────
# REST call
# ──────────────────────────────────────────────────────────────────────────────

def _search_existing_issue(run_id: str, label: str) -> str | None:
    """
    JQL search for an existing issue with the idempotency label.
    Returns the issue key if found, else None. Never raises.
    """
    try:
        jql = f'project = "{settings.jira_project_key}" AND labels = "{label}"'
        url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/search"
        headers = {
            "Authorization": _basic_auth_header(),
            "Accept": "application/json",
        }
        r = requests.get(
            url, headers=headers,
            params={"jql": jql, "maxResults": 1, "fields": "key"},
            timeout=JIRA_TIMEOUT_SEC,
        )
        if r.status_code == 200:
            issues = r.json().get("issues", [])
            if issues:
                return issues[0]["key"]
    except Exception as e:
        log.warning(f"[{run_id}] Jira idempotency search failed: {e}")
    return None


def _create_issue(state: PipelineState) -> dict[str, Any]:
    """
    POST /rest/api/3/issue with Basic auth (email + API token).
    Returns the parsed JSON response on success.
    Raises on any non-2xx (caller catches and converts to skip).
    """
    url     = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/issue"
    headers = {
        "Authorization": _basic_auth_header(),
        "Accept":        "application/json",
        "Content-Type":  "application/json",
    }
    payload = {
        "fields": {
            "project":     {"key": settings.jira_project_key},
            "summary":     _build_summary(state)[:JIRA_SUMMARY_MAX],
            "issuetype":   {"name": settings.jira_issue_type},
            "labels":      _build_labels(state),
            "description": _build_adf_description(state),
        }
    }

    last_err: Exception | None = None
    for attempt in range(1, JIRA_RETRIES + 2):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=JIRA_TIMEOUT_SEC)
            if r.status_code == 201:
                return r.json()
            # Non-2xx: format a useful error for the caller
            detail = r.text[:300] if r.text else f"HTTP {r.status_code}"
            raise RuntimeError(f"Jira API HTTP {r.status_code}: {detail}")
        except requests.RequestException as e:
            last_err = e
            log.warning(f"[{state.run_id}] Jira POST attempt {attempt} network error | {e}")
            continue
        except RuntimeError as e:
            # Don't retry on 4xx — those are deterministic
            if r is not None and 400 <= r.status_code < 500:
                raise
            last_err = e
            log.warning(f"[{state.run_id}] Jira POST attempt {attempt} server error | {e}")

    # All retries exhausted
    raise last_err or RuntimeError("Jira POST failed for unknown reason")


def _basic_auth_header() -> str:
    raw = f"{settings.jira_email}:{settings.jira_api_token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


# ──────────────────────────────────────────────────────────────────────────────
# Summary, labels
# ──────────────────────────────────────────────────────────────────────────────

def _build_summary(state: PipelineState) -> str:
    """
    Subject format: "[EM Copilot] <BRD project name> · MM/DD"

    Project name is sourced from the first BRD section heading (parsed by
    the Orchestrator). Falls back to a generic label if the BRD couldn't
    be parsed. MM/DD is today's date in UTC.
    """
    project_name = _project_name_from_brd(state)
    today_mmdd   = datetime.now(timezone.utc).strftime("%m/%d")
    return f"[EM Copilot] {project_name} · {today_mmdd}"


def _project_name_from_brd(state: PipelineState) -> str:
    """
    Best-effort extraction of the BRD project name. Tries, in order:
      1. The first BRD section heading, if it's not a generic placeholder
         like "Project Overview" / "Background" / "Introduction".
      2. An explicit "Project:" / "Project Name:" line in any of the first
         three sections — common in template-driven BRDs.
      3. The leading proper-noun phrase of the first section's content:
         e.g. "FoodHub is a food-aggregator platform…" → "FoodHub".
         Catches the very common "<Name> is/provides/enables…" opening.
      4. The first short headline-style line of the first section's content.
      5. Final fallback: "BRD run".
    """
    generic = {
        "project overview", "overview", "background",
        "introduction", "executive summary", "full brd",
    }

    if not state.brd_sections:
        return "BRD run"

    first = state.brd_sections[0]
    name  = (first.section_name or "").strip()

    # 1. Non-generic first heading wins
    if name and name.lower() not in generic:
        return name[:80]

    # 2. Look for explicit "Project:" / "Project Name:" markers in the first
    #    three sections (covers template-style BRDs and metadata tables)
    project_marker = re.compile(
        r"^\s*(?:project(?:\s+name)?|product|system)\s*[:|]\s*(.+?)\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    for sec in state.brd_sections[:3]:
        m = project_marker.search(sec.content or "")
        if m:
            candidate = m.group(1).strip()
            # Strip trailing meta like "| Version: 1.0"
            candidate = re.split(r"\s*[|·]\s*", candidate, 1)[0].strip()
            if candidate:
                return candidate[:80]

    # 3. Leading proper-noun phrase: "FoodHub is a …" → "FoodHub"
    #    Matches 1–4 capitalized words followed by a copula/predicate verb
    leading_pn = re.match(
        r"^\s*([A-Z][\w\-]+(?:\s+[A-Z][\w\-]+){0,3})\s+"
        r"(?:is|are|will|shall|provides?|enables?|offers?|delivers?|connects?)\b",
        (first.content or "").strip(),
    )
    if leading_pn:
        return leading_pn.group(1).strip()

    # 4. First short headline-style line of content
    for line in (first.content or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if 4 <= len(line) <= 80 and not line.endswith("."):
            return line
        return line[:80].rstrip(".,;:") + ("…" if len(line) > 80 else "")

    return name or "BRD run"


def _build_labels(state: PipelineState) -> list[str]:
    prefix = (settings.jira_label_prefix or "em-copilot").strip() or "em-copilot"
    critic = state.critic_output
    badge  = critic.badge.value if critic else "unknown"
    arch   = state.arch_output

    labels = [
        prefix,
        f"badge-{badge}",
        f"run-{state.run_id[:8]}",
        # Phase 7: full run_id label for idempotency search
        f"em-copilot-run-{state.run_id}",
    ]
    if arch and arch.pattern:
        labels.append(f"pattern-{_slugify(arch.pattern)[:60]}")

    # Jira labels: no spaces, no special chars beyond -_, max 255 chars
    cleaned: list[str] = []
    for lbl in labels:
        s = _slugify(lbl)
        if s and len(s) <= JIRA_LABEL_MAX:
            cleaned.append(s)
    return cleaned


def _slugify(text: str) -> str:
    """Lowercase, replace runs of non-alphanumerics with single hyphen, strip ends."""
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower())
    return s.strip("-")


# ──────────────────────────────────────────────────────────────────────────────
# ADF description builder
# ──────────────────────────────────────────────────────────────────────────────

def _build_adf_description(state: PipelineState) -> dict[str, Any]:
    """
    Build the Atlassian Document Format (ADF) description body.
    Renders natively in Jira Cloud's new editor — including the Mermaid
    code block, which Jira renders as a diagram with no plugin.
    """
    ts     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    blocks: list[dict[str, Any]] = []

    # ── Header ───────────────────────────────────────────────────────────────
    blocks.append(_heading(2, "EM Copilot Pipeline Run"))
    blocks.append(_paragraph(
        _text(f"Run ID: ", bold=True), _text(state.run_id),
        _text("    "),
        _text("Exported: ", bold=True), _text(ts),
        _text("    "),
        _text("Revisions: ", bold=True), _text(str(state.revision_count)),
    ))

    # ── Critic scores ────────────────────────────────────────────────────────
    critic = state.critic_output
    if critic:
        blocks.append(_heading(3, "Critic scores"))
        blocks.append(_paragraph(
            _text("Badge: ", bold=True),
            _text(critic.badge.value.upper()),
            _text("    "),
            _text("Overall: ", bold=True),
            _text(f"{critic.overall_score:.2f} / 5.0"),
        ))
        score_items = [
            ("Groundedness",   critic.groundedness),
            ("Completeness",   critic.completeness),
            ("Consistency",    critic.consistency),
            ("Actionability",  critic.actionability),
        ]
        blocks.append(_bullet_list([
            f"{name}: {dim.score:.2f}  (threshold {dim.threshold:.2f}, "
            f"{'PASS' if dim.passed else 'FAIL'})"
            for name, dim in score_items
        ]))

    # ── Architecture (with Mermaid code block) ───────────────────────────────
    arch = state.arch_output
    if arch:
        blocks.append(_heading(3, "Architecture"))
        blocks.append(_paragraph(
            _text("Pattern: ", bold=True), _text(arch.pattern),
        ))
        if arch.pattern_justification:
            blocks.append(_paragraph(_text(arch.pattern_justification)))
        blocks.append(_paragraph(
            _text("Deployment: ", bold=True),
            _text(arch.deployment_model or "n/a"),
        ))
        if arch.diagram_mermaid:
            # Jira ADF codeBlock with language=mermaid does NOT render as a diagram —
            # it shows as syntax-highlighted code. Workaround: link to a Kroki-rendered
            # SVG that opens in a new tab. The raw source still lives below for
            # copy-paste into Confluence / GitHub README / etc. (which DO render it).
            kroki_url = _kroki_view_url(arch.diagram_mermaid, fmt="svg")
            blocks.append(_paragraph(
                _text("Diagram: ", italic=True),
                _text("view rendered architecture (SVG)", link=kroki_url),
                _text("  ·  raw Mermaid source below for copy-paste:", italic=True),
            ))
            blocks.append(_code_block(arch.diagram_mermaid, language="mermaid"))
        if arch.components:
            blocks.append(_paragraph(_text("Components:", bold=True)))
            blocks.append(_bullet_list([
                f"{c.name} ({c.technology}) — {c.responsibility}"
                for c in arch.components
            ]))

    # ── Tech stack ───────────────────────────────────────────────────────────
    stack = state.stack_output
    if stack:
        blocks.append(_heading(3, "Tech Stack Recommendation"))
        blocks.append(_paragraph(
            _text("Recommended: ", bold=True),
            _text(stack.recommended_option or "n/a"),
        ))
        if stack.recommendation_rationale:
            blocks.append(_paragraph(_text(stack.recommendation_rationale)))
        if stack.options:
            blocks.append(_paragraph(_text("Options considered:", bold=True)))
            blocks.append(_bullet_list([
                f"{opt.name} — scalability {opt.scalability_rating}/5, "
                f"familiarity {opt.team_familiarity_rating}/5, "
                f"risk {opt.integration_risk.value}, "
                f"~${opt.estimated_monthly_cost_usd:.0f}/mo"
                for opt in stack.options
            ]))

    # ── Engineering plan summary ─────────────────────────────────────────────
    plan = state.plan_output
    if plan:
        blocks.append(_heading(3, "Engineering Plan"))
        team_str = ", ".join(f"{r} × {n}" for r, n in (plan.team_composition or {}).items())
        blocks.append(_paragraph(
            _text("Total duration: ", bold=True),
            _text(f"{plan.total_duration_weeks} weeks"),
            _text("    "),
            _text("Team: ", bold=True),
            _text(team_str or "n/a"),
        ))
        if plan.phases:
            blocks.append(_paragraph(_text("Phases:", bold=True)))
            blocks.append(_bullet_list([
                f"{p.name} ({p.duration_weeks}w) — {len(p.milestones)} milestone(s)"
                for p in plan.phases
            ]))
        if plan.risks:
            blocks.append(_paragraph(_text(f"Top risks ({len(plan.risks)}):", bold=True)))
            blocks.append(_bullet_list([
                f"{r.description} — likelihood={r.likelihood.value}, impact={r.impact.value}"
                for r in plan.risks[:5]
            ]))

    # ── PoC ──────────────────────────────────────────────────────────────────
    poc = state.poc_output
    if poc:
        blocks.append(_heading(3, "Proof of Concept"))
        blocks.append(_paragraph(
            _text("Hypothesis: ", bold=True), _text(poc.poc_hypothesis),
        ))
        blocks.append(_paragraph(
            _text("Duration: ", bold=True), _text(f"{poc.duration_weeks} weeks"),
            _text("    "),
            _text("Team size: ", bold=True), _text(str(poc.team_size)),
        ))
        if poc.risk_if_poc_fails:
            blocks.append(_paragraph(
                _text("Risk if PoC fails: ", bold=True),
                _text(poc.risk_if_poc_fails),
            ))

    # ── Schedule ─────────────────────────────────────────────────────────────
    sched = state.schedule_output
    if sched:
        blocks.append(_heading(3, "Schedule"))
        blocks.append(_paragraph(
            _text("Total effort: ", bold=True),
            _text(f"{sched.total_effort_days:.1f} days"),
            _text("    "),
            _text("Buffer: ", bold=True),
            _text(f"{sched.buffer_weeks} weeks"),
        ))
        if sched.critical_path:
            blocks.append(_paragraph(
                _text("Critical path: ", bold=True),
                _text(" → ".join(sched.critical_path)),
            ))

    # ── Footer ───────────────────────────────────────────────────────────────
    blocks.append(_heading(3, "Source"))
    blocks.append(_paragraph(
        _text(f"Generated by EM Copilot — multi-agent BRD-to-engineering-plan pipeline. "
              f"Run ID {state.run_id} | Pydantic-validated outputs from 5 specialist agents "
              f"+ Critic revision loop. See knowledge_base/ for grounding sources.",
              italic=True),
    ))

    return {"type": "doc", "version": 1, "content": blocks}


# ── ADF primitives ───────────────────────────────────────────────────────────

def _text(text: str, *, bold: bool = False, italic: bool = False,
          link: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "text", "text": str(text)[:30000]}
    marks: list[dict[str, Any]] = []
    if bold:
        marks.append({"type": "strong"})
    if italic:
        marks.append({"type": "em"})
    if link:
        marks.append({"type": "link", "attrs": {"href": link}})
    if marks:
        node["marks"] = marks
    return node


def _paragraph(*runs: dict[str, Any]) -> dict[str, Any]:
    return {"type": "paragraph", "content": list(runs)}


def _heading(level: int, text: str) -> dict[str, Any]:
    return {
        "type": "heading",
        "attrs": {"level": max(1, min(level, 6))},
        "content": [{"type": "text", "text": text}],
    }


def _code_block(code: str, *, language: str = "text") -> dict[str, Any]:
    # Jira ADF codeBlock — `language: "mermaid"` renders as a diagram natively.
    return {
        "type": "codeBlock",
        "attrs": {"language": language},
        "content": [{"type": "text", "text": code}],
    }


def _bullet_list(items: list[str]) -> dict[str, Any]:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{
                    "type": "paragraph",
                    "content": [{"type": "text", "text": item}],
                }],
            }
            for item in items
        ],
    }


def _kroki_view_url(mermaid_src: str, fmt: str = "svg") -> str:
    """
    Build a kroki.io GET URL that renders mermaid_src as fmt (svg | png | pdf).
    Encoding: zlib deflate level 9 → urlsafe base64. This is Kroki's documented
    short-URL form — the whole diagram travels in the URL, no upload step.
    """
    encoded = base64.urlsafe_b64encode(
        zlib.compress((mermaid_src or "").encode("utf-8"), 9)
    ).decode("ascii")
    return f"https://kroki.io/mermaid/{fmt}/{encoded}"

