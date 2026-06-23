# src/integrations/github.py
import time
from datetime import datetime, timezone
import requests
from pydantic import BaseModel, Field, ValidationError
from langchain_core.tools import tool
from src.core.config import settings
from src.core.logger import get_logger
from src.core.resilience import resilient, GITHUB_POLICY
from src.core.models import ToolResult
from src.core.events import emit
from src.agents.base_agent import _current_run_id

log = get_logger(__name__)

# Allowlist of approved repositories matching tech_decision_log.txt
GITHUB_ALLOWLIST = {
    ("fastapi", "fastapi"),
    ("pallets", "flask"),
    ("django", "django"),
    ("langchain-ai", "langgraph"),
    ("openai", "openai-python"),
    ("anthropic", "anthropic-sdk-python"),
}


class GitHubRepoResponse(BaseModel):
    stargazers_count: int = Field(default=0)
    open_issues_count: int = Field(default=0)
    created_at: str = Field(default="")
    description: str = Field(default="")

class GitHubSearchResponse(BaseModel):
    total_count: int = Field(default=0)


@resilient(policy=GITHUB_POLICY, name="github.repo_info")
def _do_github_repo_request(owner: str, repo: str) -> dict:
    """Fetches public repository details from GitHub."""
    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"
    else:
        log.warning("GITHUB_TOKEN is not configured. Request will be unauthenticated with low rate limit.")
        
    r = requests.get(repo_url, headers=headers, timeout=3.0)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API repo error for {owner}/{repo}: {r.status_code}")
    return r.json()


@resilient(policy=GITHUB_POLICY, name="github.search_info")
def _do_github_search_request(owner: str, repo: str) -> dict:
    """Fetches total issues count from GitHub search."""
    search_url = f"https://api.github.com/search/issues?q=repo:{owner}/{repo}"
    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"token {settings.github_token}"
    else:
        log.warning("GITHUB_TOKEN is not configured. Request will be unauthenticated with low rate limit.")

    r = requests.get(search_url, headers=headers, timeout=3.0)
    if r.status_code != 200:
        raise RuntimeError(f"GitHub API search error for {owner}/{repo}: {r.status_code}")
    return r.json()


@tool
def get_github_velocity(owner: str, repo: str) -> ToolResult:
    """
    Retrieve repository engineering signals from the public GitHub API.
    Returns stargazers, open issues, stars-per-week velocity, and issue close rate.
    Uses strict schema validation, timeout, retry, allowlist check, and injection scanning.

    Emits SSE observability events:
      • `tool_call_started`   — at entry, with the owner/repo
      • `tool_call_succeeded` — on green path, with latency_ms
      • `tool_call_degraded`  — on any failure mode, with the reason
    """
    run_id = _current_run_id() or "unknown"
    t0 = time.perf_counter()
    emit("tool_call_started", tool="github", run_id=run_id, owner=owner, repo=repo)

    def _emit_degraded(reason: str) -> None:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        emit("tool_call_degraded", tool="github", run_id=run_id, reason=reason, latency_ms=latency_ms)

    owner_clean = owner.strip().lower()
    repo_clean = repo.strip().lower()

    # 0. Allowlist check to guard against LLM hallucination and unapproved endpoints
    if (owner_clean, repo_clean) not in GITHUB_ALLOWLIST:
        log.warning(f"GitHub API tool call rejected: unapproved repository {owner}/{repo}")
        _emit_degraded("repo_not_in_allowlist")
        return ToolResult(
            content=f"unknown repo {owner}/{repo}, no velocity signal",
            used_fallback=True,
            sources=[],
            trust_level="medium"
        )

    try:
        # 1. Fetch and validate repo metadata
        repo_json = _do_github_repo_request(owner, repo)
        repo_data = GitHubRepoResponse.model_validate(repo_json)
        
        stars = repo_data.stargazers_count
        open_issues = repo_data.open_issues_count
        created_at_str = repo_data.created_at
        description = repo_data.description
        
        # Calculate stars per week velocity
        stars_per_week = 0.0
        if created_at_str:
            created_dt = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            elapsed_days = (datetime.now(timezone.utc) - created_dt).days
            elapsed_weeks = elapsed_days / 7.0
            if elapsed_weeks > 0:
                stars_per_week = stars / elapsed_weeks

        # 2. Fetch and validate search total count
        search_json = _do_github_search_request(owner, repo)
        search_data = GitHubSearchResponse.model_validate(search_json)
        total_items = search_data.total_count

        close_rate_str = "unknown"
        if total_items > 0:
            closed_items = max(0, total_items - open_issues)
            close_rate = (closed_items / total_items) * 100.0
            close_rate_str = f"{close_rate:.1f}%"

        # Tool output security: regex-only (Layer 1).
        # We intentionally skip Layer 5 (LLM semantic guard) here because:
        #   - Per-result LLM scan adds latency and cost.
        #   - Tool outputs are bounded (1 GitHub call/run).
        from src.security.validator import check_external_injection

        safe_desc = description
        if description and check_external_injection(description):
            log.warning(
                f"[security] dropped github description injection for run={run_id} | "
                f"first_50_chars={description[:50]!r}"
            )
            emit("security_drop", source="github", run_id=run_id)
            safe_desc = "[Redacted due to security policy]"

        output = (
            f"GitHub public signal for {owner}/{repo}:\n"
            f"  - Description: {safe_desc}\n"
            f"  - Total stars: {stars}\n"
            f"  - Open issues/PRs: {open_issues}\n"
            f"  - Velocity: {stars_per_week:.1f} stars/week\n"
            f"  - Issue/PR close rate: {close_rate_str}"
        )

        # Final check on total output
        if check_external_injection(output):
            log.warning(
                f"[security] dropped github final output for run={run_id} | "
                f"first_50_chars={output[:50]!r}"
            )
            emit("security_drop", source="github", run_id=run_id)
            _emit_degraded("output_injection_detected")
            return ToolResult(
                content=f"GitHub public signal for {owner}/{repo} is currently blocked for security.",
                used_fallback=True,
                sources=[],
                trust_level="medium"
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        emit(
            "tool_call_succeeded",
            tool="github",
            run_id=run_id,
            latency_ms=latency_ms,
            stars=stars,
        )
        return ToolResult(
            content=output,
            used_fallback=False,
            sources=[f"github_api:{owner}/{repo}"],
            trust_level="medium"
        )

    except ValidationError as ve:
        log.error(f"GitHub JSON contract validation failed for {owner}/{repo} | {ve}")
        _emit_degraded("contract_validation_failed")
        return ToolResult(
            content=f"GitHub velocity signal unavailable for {owner}/{repo} (validation failure).",
            used_fallback=True,
            sources=[],
            trust_level="medium"
        )
    except Exception as e:
        log.warning(f"GitHub velocity tool failed (graceful degradation) for {owner}/{repo} | error={e}")
        _emit_degraded(f"exception:{type(e).__name__}")
        return ToolResult(
            content=f"GitHub velocity signal unavailable for {owner}/{repo} (tool offline).",
            used_fallback=True,
            sources=[],
            trust_level="medium"
        )
