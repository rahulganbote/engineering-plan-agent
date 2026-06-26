"""
src/agents/critic/hallucination.py
══════════════════════════════════
Hallucination and citation validation checks for EM Copilot.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.core.models import HallucinationFlag, PipelineState

log = get_logger(__name__)


def detect_hallucinations(state: PipelineState) -> list[HallucinationFlag]:
    """
    Named hallucination detection function.

    For each key claim in each agent output, determines whether
    the claim is supported by the BRD text or RAG citations.
    """
    flags: list[HallucinationFlag] = []
    brd_text = " ".join(s.content for s in state.brd_sections).lower()

    # Define claim extractors per agent
    checks = {
        "engineering_plan_generator": (
            state.plan_output,
            lambda o: [r.description for r in (o.risks or [])[:2]],
        ),
        "schedule_estimator": (
            state.schedule_output,
            lambda o: [f"Effort estimate: {o.total_effort_days} days"],
        ),
        "solution_architect": (
            state.arch_output,
            lambda o: [f"Architecture pattern: {o.pattern}"],
        ),
        "tech_stack_recommender": (
            state.stack_output,
            lambda o: [f"Recommended: {o.recommended_option}"],
        ),
    }

    for agent_name, (output, extract_claims_fn) in checks.items():
        if not output:
            continue
        for claim in extract_claims_fn(output):
            status = classify_claim(
                claim,
                brd_text,
                getattr(output, "citations", []),
            )
            flags.append(
                HallucinationFlag(
                    agent=agent_name,
                    claim=claim,
                    status=status,
                    supporting_chunk_id=(
                        output.citations[0] if status != "unsupported" and getattr(output, "citations", []) else None
                    ),
                )
            )

    unsupported_count = sum(1 for f in flags if f.status == "unsupported")
    log.info(f"[{state.run_id}] Hallucination check | total={len(flags)} | unsupported={unsupported_count}")
    return flags


def classify_claim(
    claim: str,
    brd_text: str,
    citations: list[str],
) -> str:
    """Classify a single claim as supported, partially_supported, or unsupported, weighted by citation trust level."""
    # Supported if agent provided citations
    if citations and citations[0] not in ("kb_no_results", "kb_no_results_ungrounded"):
        # Determine the highest trust level among the citations
        highest_trust = "low"
        for cite in citations:
            cite_lower = cite.lower()
            # Low trust: Tavily / web URL search results
            if "tavily" in cite_lower or cite_lower.startswith("http") or "web_grounding" in cite_lower:
                pass  # remains low trust
            # Medium trust: GitHub API
            elif "github" in cite_lower:
                if highest_trust == "low":
                    highest_trust = "medium"
            # High trust: RAG (org-curated knowledge base) or standards
            else:
                highest_trust = "high"

        if highest_trust in ("high", "medium"):
            return "supported"
        else:
            # Tavily search is low-trust, treat as partially_supported
            return "partially_supported"

    # Partially supported if key claim terms appear in BRD
    claim_words = set(claim.lower().split())
    brd_words = set(brd_text.split())
    overlap = claim_words & brd_words
    if len(overlap) >= 2:
        return "partially_supported"

    return "unsupported"


def detect_unciteed_tool_usage(state: PipelineState) -> list[HallucinationFlag]:
    """
    Cross-checks tools_used against agent citations.

    When an agent invokes an external tool (Tavily, GitHub) but the
    downstream output contains no citation traceable to that tool's
    sources, the LLM has implicitly trusted the tool output without
    attribution.
    """
    flags = []

    # Collect all citation IDs across all specialist outputs
    all_citations: set[str] = set()
    for output in (state.plan_output, state.schedule_output, state.arch_output, state.poc_output, state.stack_output):
        if not output:
            continue
        for cite in getattr(output, "citations", []):
            all_citations.add(cite)

    # Helper: does any citation match the prefix?
    def _has_prefix(prefix: str) -> bool:
        return any(c.startswith(prefix) or prefix in c for c in all_citations)

    # Rule 1: tavily_search was invoked but no tavily_web_grounding citation
    if "tavily_search" in (state.tools_used or []):
        if not (_has_prefix("tavily_web_grounding") or _has_prefix("http")):
            flags.append(
                HallucinationFlag(
                    agent="solution_architect",  # primary Tavily caller; tech_stack also
                    claim=(
                        "Tavily web search was invoked but no tavily_web_grounding "
                        "or web URL citation appears in any specialist output — "
                        "web-grounded facts may be cited without attribution."
                    ),
                    status="partially_supported",
                    supporting_chunk_id=None,
                )
            )

    # Rule 2: get_github_velocity was invoked but no github_api:* citation
    if "get_github_velocity" in (state.tools_used or []):
        if not _has_prefix("github_api:"):
            flags.append(
                HallucinationFlag(
                    agent="tech_stack_recommender",
                    claim=(
                        "GitHub velocity tool was invoked but no github_api: "
                        "citation appears in tech stack output — velocity / "
                        "issue close-rate numbers may be reported without source."
                    ),
                    status="partially_supported",
                    supporting_chunk_id=None,
                )
            )

    if flags:
        log.warning(f"[{state.run_id}] Uncited tool usage flags: {len(flags)} | tools_used={state.tools_used}")
    return flags
