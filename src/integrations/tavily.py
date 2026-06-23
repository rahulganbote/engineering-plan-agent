# src/integrations/tavily.py
import requests
from pydantic import BaseModel, Field, ValidationError
from src.core.config import settings
from src.core.logger import get_logger
from src.core.resilience import resilient, TAVILY_POLICY
from src.core.models import ToolResult

log = get_logger(__name__)


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
    """
    if not settings.tavily_api_key:
        log.warning("Tavily API key is not configured. Web search fallback unavailable.")
        return ToolResult(
            content="Web search unavailable — Tavily key missing.",
            used_fallback=True,
            sources=[],
            trust_level="low"
        )

    try:
        raw_data = _do_tavily_request(query, max_results)
        
        # Enforce JSON contract validation
        response_model = TavilyResponse.model_validate(raw_data)
        
        results = response_model.results
        if not results:
            return ToolResult(
                content="No web search results found.",
                used_fallback=True,
                sources=[],
                trust_level="low"
            )

        from src.security.validator import check_external_injection
        from src.agents.base_agent import _current_run_id
        from src.core.events import emit

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
                run_id = _current_run_id() or "unknown"
                log.warning(
                    f"[security] dropped tavily content for run={run_id} | "
                    f"first_50_chars={combined[:50]!r}"
                )
                emit("security_drop", source="tavily", run_id=run_id)
                continue
            formatted.append(
                f"[{len(formatted)+1}] {r.title} - {r.url}\nSnippet: {r.content}"
            )
            if r.url:
                sources.append(r.url)
            
        if not formatted:
            return ToolResult(
                content="No safe web search results found (flagged by safety guardrails).",
                used_fallback=True,
                sources=[],
                trust_level="low"
            )
            
        return ToolResult(
            content="\n\n".join(formatted),
            used_fallback=False,
            sources=sources,
            trust_level="low"
        )

    except ValidationError as ve:
        log.error(f"Tavily JSON contract validation failed | {ve}")
        return ToolResult(
            content="Web search temporary unavailable — contract validation failed.",
            used_fallback=True,
            sources=[],
            trust_level="low"
        )
    except Exception as e:
        log.warning(f"Tavily search failed (graceful degradation) | error={e}")
        return ToolResult(
            content="Web search temporary unavailable — using RAG and BRD context.",
            used_fallback=True,
            sources=[],
            trust_level="low"
        )
