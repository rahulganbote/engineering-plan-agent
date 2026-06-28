# src/integrations/tavily.py
import time

import requests
from pydantic import BaseModel, Field, ValidationError

from src.agents.base_agent import _current_run_id
from src.core.config import settings
from src.core.events import emit
from src.core.logger import get_logger
from src.core.models import ToolResult
from src.core.resilience import TAVILY_POLICY, resilient

log = get_logger(__name__)


# ─── Monthly budget tracker (Tavily free tier = 1000 queries/month) ────────────
# Module-level counter, thread-safe via a single threading.Lock. Resets when the
# calendar month changes. When the budget is exhausted, tavily_search() returns
# a degraded ToolResult without hitting the API - avoiding the 429 we'd
# otherwise see and burning the rate-limit window on the next deploy.
#
# Production note: this counter is per-process (the same multi-instance state
# loss problem as _runs). For Cloud Run with --max-instances=1 the counter is
# accurate. For true multi-instance, this should move to Upstash atomic counters.
import threading
from datetime import datetime, timezone

_BUDGET_LOCK = threading.Lock()
_BUDGET_STATE = {"month": "", "count": 0}


def _current_month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _check_and_increment_budget() -> tuple[bool, int, int]:
    """
    Atomically check whether the monthly budget allows another request and
    increment the counter if so. Returns (allowed, count_after, budget).
    Resets the counter when the month rolls over.
    """
    budget = int(settings.tavily_monthly_budget or 0)
    with _BUDGET_LOCK:
        now_month = _current_month_key()
        if _BUDGET_STATE["month"] != now_month:
            _BUDGET_STATE["month"] = now_month
            _BUDGET_STATE["count"] = 0
        # 0 = unlimited; only check when budget > 0
        if budget > 0 and _BUDGET_STATE["count"] >= budget:
            return (False, _BUDGET_STATE["count"], budget)
        _BUDGET_STATE["count"] += 1
        return (True, _BUDGET_STATE["count"], budget)


def get_tavily_budget_status() -> dict:
    """
    Read-only snapshot for /api/tavily-budget or test introspection.
    """
    with _BUDGET_LOCK:
        return {
            "month": _BUDGET_STATE["month"] or _current_month_key(),
            "used": _BUDGET_STATE["count"],
            "budget": int(settings.tavily_monthly_budget or 0),
        }


# ─── Privacy boundary helpers ──────────────────────────────────────────────────
# Tavily is a third-party service. Sending raw BRD content there = potential
# data exposure (PII, org-internal IP, customer names, financial details, etc.).
#
# Policy: queries sent to Tavily MUST be derived metadata only.
#   ✓ Section names: "Objectives, NFRs, Constraints"
#   ✓ Generic concept hints: "high-availability, low-latency"
#   ✓ Architecture-class keywords: "microservices, event-driven, REST"
#   ✗ Raw BRD content (paragraphs, requirements text)
#   ✗ PII (names, emails, phone numbers)
#   ✗ Org names, product names, internal codenames
#
# This helper enforces that policy at the source - callers MUST pass through
# `build_tavily_query()` rather than constructing query strings inline.

# Allowlist of architecture / engineering concept keywords that we'll surface
# to Tavily verbatim. Anything NOT in this list is dropped from the query.
_SAFE_CONCEPT_KEYWORDS = {
    # NFR concepts
    "availability",
    "latency",
    "throughput",
    "scalability",
    "reliability",
    "security",
    "compliance",
    "consistency",
    "durability",
    "concurrency",
    # Architecture patterns
    "microservices",
    "monolith",
    "event-driven",
    "serverless",
    "rest",
    "graphql",
    "grpc",
    "websocket",
    "streaming",
    "batch",
    # Data concerns
    "transactional",
    "analytical",
    "real-time",
    "offline",
    "sync",
    "async",
    # Industry verticals (generic, non-customer-specific)
    "payments",
    "healthcare",
    "saas",
    "fintech",
    "edtech",
    "iot",
}


def build_tavily_query(agent_role: str, brd_sections: list, max_keywords: int = 5) -> str:
    """
    Build a Tavily query from DERIVED metadata only - never from raw BRD content.

    Inputs:
      • agent_role: descriptive role string ("architecture pattern", "tech stack")
      • brd_sections: list of BRDSection objects (we use section names only)
      • max_keywords: cap on how many concept keywords appear in the query

    The output is a string that contains: agent role + section names + matched
    safe-concept keywords drawn from the BRD. Raw BRD text never appears.

    Example query: "best architecture pattern for payments, availability, scalability"
    """
    # Build a lowercase corpus of just the section names + first 60 chars per section
    # for keyword matching. 60 chars is short enough that a recognizable PII fragment
    # (full name, email) cannot survive - and the keyword filter drops anything not
    # in _SAFE_CONCEPT_KEYWORDS.
    section_names = [getattr(s, "section_name", "") for s in (brd_sections or [])]
    section_blobs = [(getattr(s, "content", "") or "")[:60] for s in (brd_sections or [])]
    corpus = " ".join(section_names + section_blobs).lower()

    # Extract only the safe keywords that appear in the corpus
    matched = [w for w in _SAFE_CONCEPT_KEYWORDS if w in corpus][:max_keywords]

    # Always include the section names - they're structure labels, not content
    # (e.g., "Objectives", "Requirements", "Risks") - bounded vocabulary.
    structural_terms = [s for s in section_names if s][:3]

    parts = [agent_role, "for"] + structural_terms + matched
    return " ".join(p for p in parts if p).strip()


class TavilySearchResult(BaseModel):
    title: str = Field(default="")
    url: str = Field(default="")
    content: str = Field(default="")
    score: float = Field(default=0.0)


class TavilyResponse(BaseModel):
    results: list[TavilySearchResult] = Field(default_factory=list)


@resilient(policy=TAVILY_POLICY, name="tavily.search")
def _do_tavily_request(query: str, max_results: int) -> dict:
    """
    Executes the HTTP POST request to Tavily.
    Enforces timeout, retries, and circuit breaker.
    """
    response = requests.post(
        "https://api.tavily.com/search",
        json={
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
        },
        timeout=5.0,  # Enforce client timeout matching policy
    )
    if response.status_code != 200:
        raise RuntimeError(f"Tavily search failed with status {response.status_code}: {response.text}")
    return response.json()


def tavily_search(query: str, max_results: int = 3) -> ToolResult:
    """
    Search the web using Tavily.
    Validates output structure via Pydantic contract, filters out potential prompt injections,
    and returns a ToolResult. Degrades gracefully on any exception.

    Emits SSE observability events:
      • `tool_call_started`   - at entry, with the bounded query length
      • `tool_call_succeeded` - on green path, with latency_ms + result count
      • `tool_call_degraded`  - on any failure mode, with the reason
    """
    run_id = _current_run_id() or "unknown"
    t0 = time.perf_counter()
    emit("tool_call_started", tool="tavily", run_id=run_id, query_len=len(query))

    def _emit_degraded(reason: str) -> None:
        latency_ms = int((time.perf_counter() - t0) * 1000)
        emit("tool_call_degraded", tool="tavily", run_id=run_id, reason=reason, latency_ms=latency_ms)

    if not settings.tavily_api_key:
        log.warning("Tavily API key is not configured. Web search fallback unavailable.")
        _emit_degraded("api_key_missing")
        return ToolResult(
            content="Web search unavailable - Tavily key missing.", used_fallback=True, sources=[], trust_level="low"
        )

    # Budget check BEFORE the network call. If we're at the cap, return degraded
    # without burning a request - the next month's budget refresh restores us.
    allowed, used, budget = _check_and_increment_budget()
    if not allowed:
        log.warning(f"Tavily monthly budget exhausted | used={used} budget={budget} month={_BUDGET_STATE['month']}")
        emit(
            "tavily_budget_exhausted",
            run_id=run_id,
            used=used,
            budget=budget,
            month=_BUDGET_STATE["month"],
        )
        _emit_degraded("monthly_budget_exhausted")
        return ToolResult(
            content=(f"Web search unavailable - Tavily monthly budget reached ({used}/{budget}). Resets next month."),
            used_fallback=True,
            sources=[],
            trust_level="low",
        )

    try:
        raw_data = _do_tavily_request(query, max_results)

        # Enforce JSON contract validation
        response_model = TavilyResponse.model_validate(raw_data)

        results = response_model.results
        if not results:
            _emit_degraded("empty_results")
            return ToolResult(content="No web search results found.", used_fallback=True, sources=[], trust_level="low")

        from src.security.validator import check_external_injection

        formatted = []
        sources = []

        # Tool output security: regex-only (Layer 1).
        # We intentionally skip Layer 5 (LLM semantic guard) here because:
        #   - Per-result LLM scan adds 200-500ms x N results = unacceptable latency
        #   - Per-result LLM cost adds $0.002 x N x runs = unacceptable cost
        #   - Tool outputs are bounded (3 Tavily results); regex catches ~85% of known
        #     injection patterns; remaining ~15% have lower blast radius (single agent context)
        for r in results:
            combined = f"{r.title}\n{r.content}"
            if check_external_injection(combined):
                log.warning(f"[security] dropped tavily content for run={run_id} | first_50_chars={combined[:50]!r}")
                emit("security_drop", source="tavily", run_id=run_id)
                continue
            formatted.append(f"[{len(formatted) + 1}] {r.title} - {r.url}\nSnippet: {r.content}")
            if r.url:
                sources.append(r.url)

        if not formatted:
            _emit_degraded("all_results_dropped_by_security")
            return ToolResult(
                content="No safe web search results found (flagged by safety guardrails).",
                used_fallback=True,
                sources=[],
                trust_level="low",
            )

        latency_ms = int((time.perf_counter() - t0) * 1000)
        emit(
            "tool_call_succeeded",
            tool="tavily",
            run_id=run_id,
            latency_ms=latency_ms,
            result_count=len(formatted),
        )
        return ToolResult(content="\n\n".join(formatted), used_fallback=False, sources=sources, trust_level="low")

    except ValidationError as ve:
        log.error(f"Tavily JSON contract validation failed | {ve}")
        _emit_degraded("contract_validation_failed")
        return ToolResult(
            content="Web search temporary unavailable - contract validation failed.",
            used_fallback=True,
            sources=[],
            trust_level="low",
        )
    except Exception as e:
        log.warning(f"Tavily search failed (graceful degradation) | error={e}")
        _emit_degraded(f"exception:{type(e).__name__}")
        return ToolResult(
            content="Web search temporary unavailable - using RAG and BRD context.",
            used_fallback=True,
            sources=[],
            trust_level="low",
        )
