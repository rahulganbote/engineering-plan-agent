"""
src/agents/critic/quality_caps.py
═════════════════════════════════
Deterministic score calibration and quality badge rules.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.core.models import (
    ConsistencyIssue,
    HallucinationFlag,
    PipelineState,
    QualityBadge,
)

log = get_logger(__name__)

# ── Quality thresholds ────────────────────────────────────────────────────────
THRESHOLDS: dict[str, float] = {
    "groundedness": 3.75,  # >= 75% of claims cited
    "completeness": 5.0,  # 100% BRD sections addressed
    "consistency": 5.0,  # zero contradictions
    "actionability": 4.0,  # EM can act immediately
}
# Badge thresholds. Kept aligned with QualityBadge docstring in core/models.py.
#   GREEN : overall >= 4.0  AND  all 4 dimensions passing their per-dim threshold
#   AMBER : overall >= 3.5  OR   one dimension below its per-dim threshold
#   RED   : overall <  3.5  OR   two+ dimensions below their per-dim thresholds
# FM-2 and FM-3 caps in critic/__init__.py must sit below GREEN_THRESHOLD so a
# failure-mode trip guarantees Amber. Any change here needs a matching update
# to those caps and to the IngestionLanding "Critic Reviewer" card copy.
GREEN_THRESHOLD = 4.0
AMBER_THRESHOLD = 3.5
RED_THRESHOLD = 3.5


def calibrate_scores(
    state: PipelineState,
    scores: dict,
    hallucination_flags: list[HallucinationFlag],
    consistency_issues: list[ConsistencyIssue],
) -> dict:
    """
    Deterministically adjust LLM judge scores against structured artifacts.
    This preserves the LLM judge for nuance but prevents mismatch where
    objectively complete/no-contradiction outputs are stuck at a generic 4.0
    even though thresholds require exact 5.0.
    """
    calibrated = dict(scores)
    evidence_notes: list[str] = []

    if has_complete_artifact_bundle(state):
        calibrated["completeness"] = max(float(calibrated.get("completeness", 0)), 5.0)
        calibrated["completeness_evidence"] = (
            "Deterministic check: all 5 specialist outputs exist and required contract fields are populated."
        )
        calibrated["completeness_suggestion"] = ""
        evidence_notes.append("completeness=5.0")

    if not consistency_issues:
        calibrated["consistency"] = max(float(calibrated.get("consistency", 0)), 5.0)
        calibrated["consistency_evidence"] = "Deterministic check: no cross-agent consistency issues were detected."
        calibrated["consistency_suggestion"] = ""
        evidence_notes.append("consistency=5.0")
    else:
        calibrated["consistency"] = min(float(calibrated.get("consistency", 0)), 4.0)
        calibrated["consistency_evidence"] = (
            f"Deterministic check: {len(consistency_issues)} cross-agent consistency issue(s) were detected."
        )
        calibrated["consistency_suggestion"] = (
            "Resolve the listed cross-agent contradiction before assigning a perfect consistency score."
        )
        evidence_notes.append("consistency capped by detected issues")

    if is_actionable_bundle(state):
        calibrated["actionability"] = max(float(calibrated.get("actionability", 0)), 4.0)
        calibrated["actionability_evidence"] = (
            "Deterministic check: milestones have owners, schedule has critical path, "
            "architecture maps NFRs, PoC has measurable success criteria, and stack "
            "contains 2-3 options."
        )
        calibrated.setdefault("actionability_suggestion", "")
        evidence_notes.append("actionability>=4.0")

    unsupported = [f for f in hallucination_flags if f.status == "unsupported"]
    if unsupported:
        calibrated["groundedness"] = min(float(calibrated.get("groundedness", 0)), 3.5)
        calibrated["groundedness_evidence"] = (
            f"Deterministic hallucination check found {len(unsupported)} unsupported claim(s)."
        )
        calibrated["groundedness_suggestion"] = "Remove unsupported claims or add citations to retrieved chunks."
        evidence_notes.append("groundedness capped by unsupported claims")

    # Check citation trust tiers across all outputs to apply groundedness penalty for low-trust dominance
    citations: list[str] = []
    for output in [
        state.plan_output,
        state.schedule_output,
        state.arch_output,
        state.poc_output,
        state.stack_output,
    ]:
        if output and hasattr(output, "citations") and output.citations:
            for cite in output.citations:
                if cite not in ("kb_no_results", "kb_no_results_ungrounded"):
                    citations.append(cite)

    if citations:
        low_trust_count = 0
        for cite in citations:
            if (
                cite.startswith("tavily_web_grounding")
                or cite.startswith("http://")
                or cite.startswith("https://")
                or "tavily" in cite.lower()
            ):
                low_trust_count += 1

        ratio = low_trust_count / len(citations)
        if ratio > 0.5:
            calibrated["groundedness"] = max(0.0, float(calibrated.get("groundedness", 0.0)) - 0.5)
            evidence_notes.append(
                f"groundedness penalised by 0.5 for low-trust dominance ({low_trust_count}/{len(citations)} low trust)"
            )

            orig_suggestion = calibrated.get("groundedness_suggestion", "")
            add_msg = " Reduce reliance on web searches and add more citations to retrieved RAG chunks."
            if add_msg not in orig_suggestion:
                calibrated["groundedness_suggestion"] = (orig_suggestion + add_msg).strip()

    if evidence_notes:
        log.info(f"[{state.run_id}] Critic deterministic calibration | {', '.join(evidence_notes)}")
    return calibrated


def has_complete_artifact_bundle(state: PipelineState) -> bool:
    """True when all 5 specialist outputs exist and core fields are populated."""
    return all(
        [
            state.plan_output
            and state.plan_output.phases
            and state.plan_output.risks
            and state.plan_output.team_composition
            and state.plan_output.total_duration_weeks > 0,
            state.schedule_output
            and state.schedule_output.sprints
            and state.schedule_output.total_effort_days > 0
            and state.schedule_output.comparable_projects,
            state.arch_output
            and state.arch_output.pattern
            and state.arch_output.components
            and state.arch_output.nfr_mappings
            and state.arch_output.deployment_model,
            state.poc_output
            and state.poc_output.poc_hypothesis
            and state.poc_output.scope_in
            and state.poc_output.scope_out
            and state.poc_output.success_criteria,
            state.stack_output
            and 2 <= len(state.stack_output.options) <= 3
            and state.stack_output.recommended_option in [o.name for o in state.stack_output.options],
        ]
    )


def is_actionable_bundle(state: PipelineState) -> bool:
    """True when artifacts contain the fields an EM needs to act immediately."""
    plan_actionable = bool(
        state.plan_output
        and state.plan_output.phases
        and all(
            milestone.owner_role and milestone.deliverable
            for phase in state.plan_output.phases
            for milestone in phase.milestones
        )
    )
    schedule_actionable = bool(
        state.schedule_output
        and state.schedule_output.sprints
        and state.schedule_output.critical_path
        and state.schedule_output.total_effort_days > 0
    )
    arch_actionable = bool(
        state.arch_output
        and state.arch_output.components
        and state.arch_output.data_flow
        and state.arch_output.nfr_mappings
    )
    poc_actionable = bool(
        state.poc_output
        and state.poc_output.duration_weeks > 0
        and state.poc_output.team_size > 0
        and state.poc_output.success_criteria
        and all(c.metric and c.target_value and c.measurement_method for c in state.poc_output.success_criteria)
    )
    stack_actionable = bool(
        state.stack_output
        and 2 <= len(state.stack_output.options) <= 3
        and state.stack_output.recommended_option in [o.name for o in state.stack_output.options]
        and all(o.components and o.pros and o.cons and o.citation for o in state.stack_output.options)
    )
    return all(
        [
            plan_actionable,
            schedule_actionable,
            arch_actionable,
            poc_actionable,
            stack_actionable,
        ]
    )


def assign_badge(scores: dict, overall: float, warnings: list[str] | None = None) -> QualityBadge:
    """
    Assign Green/Amber/Red quality badge based on dimension scores.
    """
    below = sum(1 for dim, threshold in THRESHOLDS.items() if scores.get(dim, 0) < threshold)
    if warnings:
        # Unresolved warnings/advisories force at least Amber regardless of overall score
        if overall <= RED_THRESHOLD or below >= 2:
            return QualityBadge.RED
        return QualityBadge.AMBER

    if below >= 2 or overall <= RED_THRESHOLD:
        return QualityBadge.RED
    if below == 0 and overall >= GREEN_THRESHOLD:
        return QualityBadge.GREEN
    if below == 1 or (AMBER_THRESHOLD <= overall < GREEN_THRESHOLD):
        return QualityBadge.AMBER
    return QualityBadge.RED
