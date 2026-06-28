"""
src/agents/critic/__init__.py
════════════════════════════
Critic Agent orchestrates multidimensional scoring, logical consistency,
grounding validation, and the LangGraph feedback revision loop.
"""

from __future__ import annotations

from src.agents.critic.consistency_rules import check_cross_agent_consistency
from src.agents.critic.feedback import generate_revision_feedback
from src.agents.critic.hallucination import classify_claim, detect_hallucinations, detect_unciteed_tool_usage

# Imports from modular package submodules
from src.agents.critic.llm_judge import build_outputs_summary, llm_judge_scoring
from src.agents.critic.quality_caps import (
    THRESHOLDS,
    assign_badge,
    calibrate_scores,
    has_complete_artifact_bundle,
    is_actionable_bundle,
)
from src.agents.critic.scope_creep import check_ambiguity_handling, detect_scope_creep
from src.core.cache import CachePolicy
from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import (
    ConsistencyIssue,
    CriticOutput,
    DimensionScore,
    HallucinationFlag,
    PipelineState,
    QualityBadge,
    RiskLevel,
)

log = get_logger(__name__)
MAX_REVISIONS = settings.max_critic_revisions


class CriticAgent:
    """
    Evaluates all specialist agent outputs collectively and drives
    the revision loop until quality thresholds are met or max revisions reached.
    """

    CACHE_POLICY = CachePolicy(mode="semantic", semantic_threshold=0.95, namespace="llm-cache.critic")

    def run(self, state: PipelineState) -> CriticOutput:
        """
        Main entry point. Called by the LangGraph critic node after all
        5 specialist agents have completed.
        """
        log.info(f"[{state.run_id}] Critic evaluating | revision={state.revision_count}")

        # Step 1: Build a text summary of all outputs for the LLM judge
        outputs_summary = self._build_outputs_summary(state)

        # Step 2: LLM-as-Judge scoring
        scores = self._llm_judge_scoring(outputs_summary, state)

        # Step 3: Hallucination detection
        hallucination_flags = self._detect_hallucinations(state)

        # Step 3b: Scope creep detection
        scope_creep_flags = self._detect_scope_creep(state)
        hallucination_flags.extend(scope_creep_flags)

        # Step 3c: Tool-citation cross-check
        tool_citation_flags = self._detect_unciteed_tool_usage(state)
        hallucination_flags.extend(tool_citation_flags)

        # Step 4: Cross-agent consistency check
        consistency_issues = self._check_cross_agent_consistency(state)

        # Step 5: Deterministic calibration
        scores = self._calibrate_scores(
            state=state,
            scores=scores,
            hallucination_flags=hallucination_flags,
            consistency_issues=consistency_issues,
        )

        # Step 6: Compute overall score with hallucination penalty
        unsupported = sum(1 for f in hallucination_flags if f.status == "unsupported")
        raw_overall = (
            scores["groundedness"] + scores["completeness"] + scores["consistency"] + scores["actionability"]
        ) / 4.0
        # Penalty: each unsupported claim reduces score by 0.3
        overall = max(0.0, raw_overall - (unsupported * 0.3))

        # FM-2: Force Amber if any agent had no RAG hits (no_rag_hits failure mode)
        no_rag_agents = [
            agent_name
            for agent_name, output in [
                ("plan", state.plan_output),
                ("schedule", state.schedule_output),
                ("architect", state.arch_output),
                ("poc", state.poc_output),
                ("stack", state.stack_output),
            ]
            if output and "kb_no_results_ungrounded" in getattr(output, "citations", [])
        ]
        force_amber = len(no_rag_agents) > 0
        if force_amber:
            log.warning(
                f"[{state.run_id}] no_rag_hits failure mode - forcing Amber badge | agents_without_rag={no_rag_agents}"
            )
            overall = min(overall, 3.9)  # cap at Amber threshold

        # FM-3: Force Amber if any agent self-reported confidence ≤ 0.3.
        low_confidence_agents = []
        for agent_name, agent_output in [
            ("engineering_plan_generator", state.plan_output),
            ("schedule_estimator", state.schedule_output),
            ("solution_architect", state.arch_output),
            ("poc_planner", state.poc_output),
            ("tech_stack_recommender", state.stack_output),
        ]:
            if agent_output is None:
                continue
            conf = getattr(agent_output, "confidence_score", 1.0)
            if conf <= 0.30:
                low_confidence_agents.append((agent_name, conf))

        if low_confidence_agents:
            log.warning(
                f"[{state.run_id}] low confidence - forcing Amber badge | "
                f"agents={[(a, round(c, 2)) for a, c in low_confidence_agents]}"
            )
            overall = min(overall, 3.9)  # cap at Amber threshold
            for agent_name, conf in low_confidence_agents:
                consistency_issues.append(
                    ConsistencyIssue(
                        agents_involved=[agent_name],
                        conflict_description=(
                            f"{agent_name} self-reported confidence_score={conf:.2f} ≤ 0.30 - "
                            "likely fallback / placeholder output. "
                            "Inspect agent output and logs for parse or build errors before approving."
                        ),
                        severity=RiskLevel.HIGH,
                    )
                )

        # Step 7: Assign quality badge
        badge = self._assign_badge(scores, overall)

        # Step 8: Decide if revision is needed
        requires_revision = badge in (QualityBadge.RED, QualityBadge.AMBER) and state.revision_count < MAX_REVISIONS

        # Step 9: Generate actionable per-agent feedback for revision
        agent_feedback: dict[str, str] = {}
        if requires_revision:
            agent_feedback = self._generate_revision_feedback(state, scores, hallucination_flags, consistency_issues)
            log.info(
                f"[{state.run_id}] Critic requesting revision | "
                f"badge={badge} | overall={overall:.2f} | "
                f"agents_with_feedback={list(agent_feedback.keys())}"
            )
        else:
            log.info(
                f"[{state.run_id}] Critic complete | "
                f"badge={badge} | overall={overall:.2f} | "
                f"no_revision={'max_reached' if state.revision_count >= MAX_REVISIONS else 'score_ok'}"
            )

        return CriticOutput(
            run_id=state.run_id,
            revision_number=state.revision_count,
            target_agents=[
                "engineering_plan_generator",
                "schedule_estimator",
                "solution_architect",
                "poc_planner",
                "tech_stack_recommender",
            ],
            groundedness=DimensionScore(
                score=scores["groundedness"],
                threshold=THRESHOLDS["groundedness"],
                passed=scores["groundedness"] >= THRESHOLDS["groundedness"],
                evidence=scores.get("groundedness_evidence", ""),
                improvement_suggestion=scores.get("groundedness_suggestion", ""),
            ),
            completeness=DimensionScore(
                score=scores["completeness"],
                threshold=THRESHOLDS["completeness"],
                passed=scores["completeness"] >= THRESHOLDS["completeness"],
                evidence=scores.get("completeness_evidence", ""),
                improvement_suggestion=scores.get("completeness_suggestion", ""),
            ),
            consistency=DimensionScore(
                score=scores["consistency"],
                threshold=THRESHOLDS["consistency"],
                passed=scores["consistency"] >= THRESHOLDS["consistency"],
                evidence=scores.get("consistency_evidence", ""),
                improvement_suggestion=scores.get("consistency_suggestion", ""),
            ),
            actionability=DimensionScore(
                score=scores["actionability"],
                threshold=THRESHOLDS["actionability"],
                passed=scores["actionability"] >= THRESHOLDS["actionability"],
                evidence=scores.get("actionability_evidence", ""),
                improvement_suggestion=scores.get("actionability_suggestion", ""),
            ),
            overall_score=round(overall, 2),
            badge=badge,
            consistency_issues=consistency_issues,
            hallucination_flags=hallucination_flags,
            agent_feedback=agent_feedback,
            requires_revision=requires_revision,
        )

    # ── Backward Compatibility Method Wrappers ───────────────────────────────────

    def _build_outputs_summary(self, state: PipelineState) -> str:
        return build_outputs_summary(state)

    def _llm_judge_scoring(self, outputs_summary: str, state: PipelineState) -> dict:
        return llm_judge_scoring(outputs_summary, state)

    def _calibrate_scores(
        self,
        state: PipelineState,
        scores: dict,
        hallucination_flags: list[HallucinationFlag],
        consistency_issues: list[ConsistencyIssue],
    ) -> dict:
        return calibrate_scores(state, scores, hallucination_flags, consistency_issues)

    def _has_complete_artifact_bundle(self, state: PipelineState) -> bool:
        return has_complete_artifact_bundle(state)

    def _is_actionable_bundle(self, state: PipelineState) -> bool:
        return is_actionable_bundle(state)

    def _detect_hallucinations(self, state: PipelineState) -> list[HallucinationFlag]:
        return detect_hallucinations(state)

    def _classify_claim(
        self,
        claim: str,
        brd_text: str,
        citations: list[str],
    ) -> str:
        return classify_claim(claim, brd_text, citations)

    def _check_cross_agent_consistency(
        self,
        state: PipelineState,
    ) -> list[ConsistencyIssue]:
        return check_cross_agent_consistency(state)

    def _generate_revision_feedback(
        self,
        state: PipelineState,
        scores: dict,
        hallucination_flags: list[HallucinationFlag],
        consistency_issues: list[ConsistencyIssue],
    ) -> dict[str, str]:
        return generate_revision_feedback(state, scores, hallucination_flags, consistency_issues)

    def _assign_badge(self, scores: dict, overall: float) -> QualityBadge:
        return assign_badge(scores, overall)

    def _detect_unciteed_tool_usage(self, state: PipelineState) -> list[HallucinationFlag]:
        return detect_unciteed_tool_usage(state)

    def _detect_scope_creep(self, state: PipelineState) -> list[HallucinationFlag]:
        return detect_scope_creep(state)

    def _check_ambiguity_handling(self, state: PipelineState) -> list[str]:
        return check_ambiguity_handling(state)
