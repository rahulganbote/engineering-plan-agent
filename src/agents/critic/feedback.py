"""
src/agents/critic/feedback.py
═════════════════════════════
Actionable feedback generation for specialist agent revision cycles.
"""

from __future__ import annotations

from src.agents.critic.quality_caps import THRESHOLDS
from src.core.models import ConsistencyIssue, HallucinationFlag, PipelineState


def generate_revision_feedback(
    state: PipelineState,
    scores: dict,
    hallucination_flags: list[HallucinationFlag],
    consistency_issues: list[ConsistencyIssue],
) -> dict[str, str]:
    """
    Generate specific, actionable revision instructions per agent.
    """
    feedback: dict[str, str] = {}

    # Groundedness feedback → plan generator (primary citation agent)
    if scores.get("groundedness", 5) < THRESHOLDS["groundedness"]:
        feedback["engineering_plan_generator"] = (
            f"GROUNDEDNESS SCORE LOW ({scores['groundedness']:.1f}/5, threshold={THRESHOLDS['groundedness']}): "
            f"{scores.get('groundedness_evidence', '')} "
            f"FIX: {scores.get('groundedness_suggestion', 'Add Pinecone chunk IDs to every risk and milestone.')}"
        )

    # Hallucination feedback → originating agent
    for flag in [f for f in hallucination_flags if f.status == "unsupported"]:
        existing = feedback.get(flag.agent, "")
        feedback[flag.agent] = existing + (
            f"\nHALLUCINATION: Claim '{flag.claim[:80]}' has no BRD or RAG support. Remove or add a citation."
        )

    # Consistency feedback → both agents involved
    for issue in consistency_issues:
        for agent in issue.agents_involved:
            existing = feedback.get(agent, "")
            feedback[agent] = existing + f"\nCONSISTENCY ISSUE: {issue.conflict_description}"

    # Actionability feedback → plan generator (owns milestones/owners)
    if scores.get("actionability", 5) < THRESHOLDS["actionability"]:
        key = "engineering_plan_generator"
        existing = feedback.get(key, "")
        feedback[key] = existing + (
            f"\nACTIONABILITY SCORE LOW ({scores['actionability']:.1f}/5): "
            f"{scores.get('actionability_suggestion', 'Add specific owners and target dates to all milestones.')}"
        )

    return feedback
