"""
src/integrations/jira_mcp.py
═════════════════════════════
MCP-client integration for Jira - creates an **Epic** by calling the
`mcp-atlassian` MCP server over stdio, instead of hitting the Jira REST API
directly.

Why this exists
───────────────
The REST integration in src/integrations/jira.py creates a Jira *Task* via a
plain HTTPS POST. This module demonstrates the **Model Context Protocol (MCP)**
architecture: the pipeline acts as an MCP *client*, spawns the `mcp-atlassian`
MCP *server* as a subprocess, performs the MCP handshake, discovers the
server's tools, and invokes `jira_create_issue` with `issue_type="Epic"`.

Architecture
────────────
    FastAPI /approve handler  (MCP client)
            │  stdio (JSON-RPC 2.0)
            ▼
    mcp-atlassian  (MCP server subprocess)
            │  Jira Cloud REST v3 (handled internally by the server)
            ▼
    Atlassian Jira Cloud  →  Epic created

Reliability
───────────
This module NEVER raises. If the `mcp` SDK or the `mcp-atlassian` server is
unavailable, or the tool call fails, it returns a dict with mode="skipped" and
a fallback_reason - the /approve endpoint then falls back to the REST path in
src/integrations/jira.py, so a missing MCP server can never break the demo.

Setup (one-time)
────────────────
    pip install mcp mcp-atlassian
    # OR, if you have `uv`:  uvx mcp-atlassian   (no install needed)

The server reads JIRA_URL / JIRA_USERNAME / JIRA_API_TOKEN from the environment
this module passes it - the SAME credentials the REST path already uses.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import PipelineState

# Reuse the credential probe + summary/label builders from the REST module so
# the two integrations stay consistent.
from src.integrations.jira import (
    _build_labels,
    _build_summary,
    _credentials_status,
    _kroki_view_url,
)

log = get_logger(__name__)

# ── MCP server launch configuration ──────────────────────────────────────────
# How to start the `mcp-atlassian` MCP server as a stdio subprocess.
# `mcp-atlassian` 0.11.x ships no `__main__.py`, so `python -m mcp_atlassian`
# fails. The package exposes a `main()` entry point - launch it with the current
# interpreter (sys.executable) so it runs in the SAME venv where mcp-atlassian
# is installed, with no PATH lookup needed.
MCP_SERVER_COMMAND: str = sys.executable
MCP_SERVER_ARGS: list[str] = ["-c", "from mcp_atlassian import main; main()", "--transport", "stdio"]

# The Jira create-issue tool exposed by mcp-atlassian.
MCP_CREATE_ISSUE_TOOL = "jira_create_issue"

# Hard timeout (seconds) for the whole MCP round-trip (spawn + handshake + call).
MCP_TIMEOUT_SEC = 45


# ──────────────────────────────────────────────────────────────────────────────
# Public entry point (async)
# ──────────────────────────────────────────────────────────────────────────────


async def push_epic_to_jira_via_mcp(state: PipelineState) -> dict[str, Any]:
    """
    Create a Jira **Epic** for this run via the mcp-atlassian MCP server.

    Returns the SAME dict shape as src/integrations/jira.push_artifacts_to_jira:
        {
          "url":             str | None,    # browse URL on success
          "mode":            "jira" | "skipped",
          "detail":          str,
          "issue_key":       str | None,    # e.g. "SCRUM-42"
          "fallback_reason": str | None,    # populated when skipped
          "transport":       "mcp",         # marks which path produced this
        }
    Never raises - caller falls back to the REST path on mode != "jira".
    """
    run_id = state.run_id

    # 1. Credentials present?
    ok, why_not = _credentials_status()
    if not ok:
        return _skip(f"Jira credentials not configured: {why_not}")

    # 2. MCP SDK importable?
    try:
        import asyncio

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:
        return _skip(f"mcp SDK not installed ({e}); run: pip install mcp mcp-atlassian")

    # 3. Build the issue payload
    summary = _build_summary(state)
    description = _build_markdown_description(state)
    labels = _build_labels(state)
    # Phase 7: idempotency - add run-specific label so we can search for it
    idempotency_label = f"em-copilot-run-{state.run_id}"
    if idempotency_label not in labels:
        labels = list(labels) + [idempotency_label]

    server_params = StdioServerParameters(
        command=MCP_SERVER_COMMAND,
        args=MCP_SERVER_ARGS,
        # mcp-atlassian reads these env vars for Jira Cloud basic-auth.
        env={
            # The MCP SDK passes this dict to the subprocess VERBATIM (no merge
            # with the parent env), so inherit PATH / HOME / TLS-cert vars.
            **os.environ,
            "JIRA_URL": settings.jira_base_url,
            "JIRA_USERNAME": settings.jira_email,
            "JIRA_API_TOKEN": settings.jira_api_token,
            # Limit the server to Jira tools only (skip Confluence) for speed.
            "ENABLED_TOOLS": "jira_create_issue,jira_get_issue",
        },
    )

    # Phase 7: idempotency - search for an existing Epic with this run's label
    existing = await _search_existing_epic_mcp(state, idempotency_label)
    if existing:
        log.info(f"[{run_id}] Jira MCP - idempotent skip, Epic already exists: {existing}")
        from src.core.events import emit as _evt

        _evt("idempotent_skip", run_id=run_id, issue_key=existing, transport="mcp", label=idempotency_label)
        base = (settings.jira_base_url or "").rstrip("/")
        return {
            "url": f"{base}/browse/{existing}" if base else None,
            "mode": "jira",
            "detail": f"Idempotent skip - Epic {existing} already exists (label={idempotency_label})",
            "issue_key": existing,
            "fallback_reason": None,
            "transport": "mcp",
        }

    log.info(f"[{run_id}] Jira MCP - spawning mcp-atlassian server via stdio")

    try:
        result_text = await asyncio.wait_for(
            _call_mcp_create_issue(
                stdio_client,
                ClientSession,
                server_params,
                project_key=settings.jira_project_key,
                summary=summary,
                description=description,
                labels=labels,
                run_id=run_id,
            ),
            timeout=MCP_TIMEOUT_SEC,
        )
    except TimeoutError:
        return _skip(f"MCP call timed out after {MCP_TIMEOUT_SEC}s")
    except Exception as e:
        return _skip(f"MCP transport error: {type(e).__name__}: {str(e)[:200]}")

    # 4. Parse the created-issue payload
    key, url = _extract_issue_key_and_url(result_text, settings.jira_base_url)
    if not key:
        return _skip(f"MCP server returned no issue key. Raw: {str(result_text)[:200]}")

    log.info(f"[{run_id}] Jira MCP - Epic created | key={key} | url={url}")
    return {
        "url": url,
        "mode": "jira",
        "detail": f"Created Jira Epic {key} via MCP (mcp-atlassian server)",
        "issue_key": key,
        "fallback_reason": None,
        "transport": "mcp",
    }


# ──────────────────────────────────────────────────────────────────────────────
# MCP round-trip
# ──────────────────────────────────────────────────────────────────────────────


async def _call_mcp_create_issue(
    stdio_client,
    ClientSession,
    server_params,
    *,
    project_key: str,
    summary: str,
    description: str,
    labels: list[str],
    run_id: str,
) -> Any:
    """
    Open an MCP stdio session, initialize, discover tools, and invoke
    jira_create_issue with issue_type='Epic'. Returns the raw tool result text.
    """
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # MCP handshake - exchange protocol version + capabilities.
            await session.initialize()

            # Tool discovery - proves the MCP architecture is live.
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            log.info(f"[{run_id}] Jira MCP - server exposes {len(tool_names)} tool(s): {tool_names[:8]}")
            if MCP_CREATE_ISSUE_TOOL not in tool_names:
                raise RuntimeError(f"MCP server does not expose '{MCP_CREATE_ISSUE_TOOL}'. Available: {tool_names}")

            # Invoke the tool - this is the MCP equivalent of the REST POST.
            call_result = await session.call_tool(
                MCP_CREATE_ISSUE_TOOL,
                arguments={
                    "project_key": project_key,
                    "summary": summary[:255],
                    "issue_type": "Epic",
                    "description": description,
                    # additional_fields must be a dict (dict[str, Any] | None),
                    # not a JSON string - the mcp-atlassian tool validates type.
                    "additional_fields": {"labels": labels},
                },
            )

            if getattr(call_result, "isError", False):
                raise RuntimeError(f"MCP tool returned an error: {call_result}")

            # Extract text content from the CallToolResult.
            return _result_to_text(call_result)


def _result_to_text(call_result: Any) -> str:
    """Flatten an MCP CallToolResult's content blocks into a single string."""
    content = getattr(call_result, "content", None)
    if content is None:
        return str(call_result)
    parts: list[str] = []
    for block in content:
        # TextContent blocks have a .text attribute.
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
        else:
            parts.append(str(block))
    return "\n".join(parts).strip()


def _extract_issue_key_and_url(
    raw_text: Any,
    base_url: str,
) -> tuple[str | None, str | None]:
    """
    Defensively pull the Jira issue key + browse URL out of whatever the
    mcp-atlassian server returned. Handles JSON objects, nested objects,
    and plain-text fallbacks.
    """
    base = (base_url or "").rstrip("/")
    text = raw_text if isinstance(raw_text, str) else str(raw_text)

    # Attempt 1 - parse as JSON and search recursively for a "key".
    try:
        data = json.loads(text)

        def _find_key(obj: Any) -> str | None:
            if isinstance(obj, dict):
                # direct key
                k = obj.get("key")
                if isinstance(k, str) and "-" in k and k[0].isalpha():
                    return k
                for v in obj.values():
                    found = _find_key(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for v in obj:
                    found = _find_key(v)
                    if found:
                        return found
            return None

        def _find_url(obj: Any) -> str | None:
            if isinstance(obj, dict):
                for field in ("url", "self", "browse_url", "link"):
                    v = obj.get(field)
                    if isinstance(v, str) and v.startswith("http"):
                        return v
                for v in obj.values():
                    found = _find_url(v)
                    if found:
                        return found
            elif isinstance(obj, list):
                for v in obj:
                    found = _find_url(v)
                    if found:
                        return found
            return None

        key = _find_key(data)
        url = _find_url(data)
        if key:
            # Prefer a clean browse URL over the API "self" link.
            browse = f"{base}/browse/{key}" if base else url
            return key, browse or url
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt 2 - regex a KEY-123 token straight out of plain text.
    import re

    m = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text)
    if m:
        key = m.group(1)
        return key, (f"{base}/browse/{key}" if base else None)

    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# Markdown description (mcp-atlassian accepts markdown; it converts to ADF)
# ──────────────────────────────────────────────────────────────────────────────


def _build_markdown_description(state: PipelineState) -> str:
    """
    Build a Markdown description for the Epic. mcp-atlassian converts Markdown
    to Jira's ADF internally, so we don't hand-build ADF here (unlike the REST
    path's _build_adf_description).
    """
    lines: list[str] = []
    critic = state.critic_output
    arch = state.arch_output
    plan = state.plan_output
    poc = state.poc_output
    stack = state.stack_output
    sched = state.schedule_output

    lines.append("h2. EM Copilot Pipeline Run")
    lines.append(f"*Run ID:* {state.run_id}  ·  *Revisions:* {state.revision_count}")
    lines.append("")

    if critic:
        lines.append("h3. Critic - Quality Assessment")
        lines.append(f"*Badge:* {critic.badge.value.upper()}  ·  *Overall:* {critic.overall_score:.2f} / 5.0")
        for name, dim in [
            ("Groundedness", critic.groundedness),
            ("Completeness", critic.completeness),
            ("Consistency", critic.consistency),
            ("Actionability", critic.actionability),
        ]:
            verdict = "PASS" if dim.passed else "FAIL"
            lines.append(f"* {name}: {dim.score:.2f} (threshold {dim.threshold:.2f}, {verdict})")
        lines.append("")

    if arch:
        lines.append("h3. Architecture")
        lines.append(f"*Pattern:* {arch.pattern}")
        if arch.pattern_justification:
            lines.append(arch.pattern_justification)
        lines.append(f"*Deployment:* {arch.deployment_model or 'n/a'}")
        if arch.diagram_mermaid:
            kroki = _kroki_view_url(arch.diagram_mermaid, fmt="svg")
            lines.append(f"*Diagram:* [view rendered architecture (SVG)|{kroki}]")
            lines.append("{code:mermaid}")
            lines.append(arch.diagram_mermaid)
            lines.append("{code}")
        if arch.components:
            lines.append("*Components:*")
            for c in arch.components:
                lines.append(f"* {c.name} ({c.technology}) - {c.responsibility}")
        lines.append("")

    if stack:
        lines.append("h3. Tech Stack Recommendation")
        lines.append(f"*Recommended:* {stack.recommended_option}")
        if stack.recommendation_rationale:
            lines.append(stack.recommendation_rationale)
        for opt in stack.options:
            lines.append(
                f"* {opt.name} - scalability {opt.scalability_rating}/5, "
                f"familiarity {opt.team_familiarity_rating}/5, "
                f"risk {opt.integration_risk.value}, "
                f"~${opt.estimated_monthly_cost_usd:.0f}/mo"
            )
        lines.append("")

    if plan:
        lines.append("h3. Engineering Plan")
        team = ", ".join(f"{r} x {n}" for r, n in (plan.team_composition or {}).items())
        lines.append(f"*Total duration:* {plan.total_duration_weeks} weeks  ·  *Team:* {team or 'n/a'}")
        if plan.phases:
            lines.append("*Phases:*")
            for p in plan.phases:
                lines.append(f"* {p.name} ({p.duration_weeks}w) - {len(p.milestones)} milestone(s)")
        lines.append("")

    if poc:
        lines.append("h3. Proof of Concept")
        lines.append(f"*Hypothesis:* {poc.poc_hypothesis}")
        lines.append(f"*Duration:* {poc.duration_weeks} weeks  ·  *Team size:* {poc.team_size}")
        if poc.risk_if_poc_fails:
            lines.append(f"*Risk if PoC fails:* {poc.risk_if_poc_fails}")
        lines.append("")

    if sched:
        lines.append("h3. Schedule")
        lines.append(f"*Total effort:* {sched.total_effort_days:.1f} days  ·  *Buffer:* {sched.buffer_weeks} weeks")
        if sched.critical_path:
            lines.append("*Critical path:* " + " -> ".join(sched.critical_path))
        lines.append("")

    lines.append("----")
    lines.append(
        "_Created by EM Copilot via the mcp-atlassian MCP server "
        "(Model Context Protocol). 7-agent BRD-to-engineering pipeline._"
    )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────────────────


async def _search_existing_epic_mcp(state, label: str) -> str | None:
    """
    Search for an existing Epic with the given idempotency label via REST
    (simpler than MCP for a read-only search). Returns the issue key if found.
    """
    try:
        import requests as _requests

        from src.integrations.jira import _basic_auth_header

        jql = f'project = "{settings.jira_project_key}" AND labels = "{label}"'
        url = f"{settings.jira_base_url.rstrip('/')}/rest/api/3/search"
        headers = {
            "Authorization": _basic_auth_header(),
            "Accept": "application/json",
        }
        r = _requests.get(url, headers=headers, params={"jql": jql, "maxResults": 1, "fields": "key"}, timeout=8)
        if r.status_code == 200:
            issues = r.json().get("issues", [])
            if issues:
                return issues[0]["key"]
    except Exception as e:
        log.warning(f"[{state.run_id}] idempotency search failed: {e}")
    return None


def _skip(reason: str) -> dict[str, Any]:
    """Build a uniform skip result. Logged at INFO since skip is a normal state."""
    log.info(f"Jira MCP push skipped - {reason}")
    return {
        "url": None,
        "mode": "skipped",
        "detail": f"Jira MCP push skipped: {reason}",
        "issue_key": None,
        "fallback_reason": reason,
        "transport": "mcp",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Phase 7: combined Jira handler (MCP → REST fallback) + export registry
# ──────────────────────────────────────────────────────────────────────────────


async def push_epic_to_jira(state) -> dict:
    """
    Combined handler: attempts MCP path first, falls back to REST on any failure.
    Registered in the export registry so /approve iterates it without special-casing.
    """
    jresult = None
    try:
        jresult = await push_epic_to_jira_via_mcp(state)
        if jresult.get("mode") != "jira":
            jresult = None
    except Exception as e:
        from src.core.logger import get_logger as _gl

        _gl(__name__).warning(f"[{state.run_id}] Jira MCP raised in combined handler: {e}")
        jresult = None

    if jresult is None:
        from src.integrations.jira import push_artifacts_to_jira

        jresult = push_artifacts_to_jira(state)

    return jresult


from src.integrations.export_registry import register_export

register_export("jira", push_epic_to_jira, "approve")
