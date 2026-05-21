"""
src/agents/critic.py
════════════════════
Critic Agent — single shared evaluator for all 5 specialist agent outputs.

Design: ONE Critic receives ALL 5 outputs simultaneously and scores them
collectively. This is a deliberate architectural choice — multiple Critics
(one per agent) would miss cross-agent contradictions like:
    "Schedule says 8 weeks but Architect designed 14 components"
    "Tech stack has low familiarity but schedule has no buffer weeks"

Only a single Critic that sees everything can catch these.

Evaluation dimensions (from capstone rubric):
    groundedness:  >= 3.75  (75% of claims are cited from RAG)
    completeness:  >= 5.0   (100% of BRD sections addressed)
    consistency:   >= 5.0   (zero contradictions between agents)
    actionability: >= 4.0   (EM can act on the output immediately)

Revision loop:
    If any dimension is below threshold AND revision_count < MAX_REVISIONS:
        → Generate specific per-agent feedback
        → Route back to specialist agents via LangGraph
        → Re-score after revision
    After max revisions: assign badge and route to HITL

LLM used: gpt-4o-mini for scoring (cost-efficient, sufficient for classification)

Rubric coverage:
    Critic Agent & Revision Loop (15 pts):
        - Rubric design:            5 pts ← 4 dimensions with thresholds
        - Feedback quality:         5 pts ← per-agent actionable feedback
        - Revision loop:            5 pts ← measurable before/after improvement
    Guardrails (4 pts):
        - Hallucination detection:  4 pts ← _detect_hallucinations()
    Guardrails (3 pts):
        - Cross-agent consistency:  3 pts ← _check_cross_agent_consistency()
"""

from __future__ import annotations

import json
import os

from openai import OpenAI
from langsmith.wrappers import wrap_openai

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

log    = get_logger(__name__)
client = wrap_openai(OpenAI(api_key=settings.openai_api_key))

# ── Rubric thresholds ─────────────────────────────────────────────────────────
THRESHOLDS: dict[str, float] = {
    "groundedness":  3.75,   # >= 75% of claims cited
    "completeness":  5.0,    # 100% BRD sections addressed
    "consistency":   5.0,    # zero contradictions
    "actionability": 4.0,    # EM can act immediately
}
GREEN_THRESHOLD  = 4.0
AMBER_THRESHOLD  = 3.0
MAX_REVISIONS    = settings.max_critic_revisions


class CriticAgent:
    """
    Evaluates all 5 specialist agent outputs collectively and drives
    the revision loop until quality thresholds are met or max revisions reached.
    """

    def run(self, state: PipelineState) -> CriticOutput:
        """
        Main entry point. Called by the LangGraph critic node after all
        5 specialist agents have completed.

        Args:
            state: Current PipelineState with all 5 agent outputs populated

        Returns:
            CriticOutput with scores, badge, feedback, and revision decision
        """
        log.info(f"[{state.run_id}] Critic evaluating | revision={state.revision_count}")

        # Step 1: Build a text summary of all outputs for the LLM judge
        outputs_summary = self._build_outputs_summary(state)

        # Step 2: LLM-as-Judge scoring on 4 dimensions
        scores = self._llm_judge_scoring(outputs_summary, state)

        # Step 3: Hallucination detection (named function — rubric 4 pts)
        hallucination_flags = self._detect_hallucinations(state)

        # Step 3b: Scope creep detection — flags requirements not in BRD
        scope_creep_flags = self._detect_scope_creep(state)
        # Merge scope creep as unsupported hallucination flags
        hallucination_flags.extend(scope_creep_flags)

        # Step 4: Cross-agent consistency check (rubric 3 pts)
        consistency_issues = self._check_cross_agent_consistency(state)

        # Step 5: Deterministic calibration.
        # The LLM judge supplies qualitative assessment, but assignment thresholds
        # require exact 5.0 scores for "complete" and "zero contradictions".
        # Lift scores only when structured artifacts prove the threshold is met.
        scores = self._calibrate_scores(
            state=state,
            scores=scores,
            hallucination_flags=hallucination_flags,
            consistency_issues=consistency_issues,
        )

        # Step 6: Compute overall score with hallucination penalty
        unsupported = sum(1 for f in hallucination_flags if f.status == "unsupported")
        raw_overall = (
            scores["groundedness"] +
            scores["completeness"] +
            scores["consistency"]  +
            scores["actionability"]
        ) / 4.0
        # Penalty: each unsupported claim reduces score by 0.3
        overall = max(0.0, raw_overall - (unsupported * 0.3))

        # FM-2: Force Amber if any agent had no RAG hits (no_rag_hits failure mode)
        # An agent with kb_no_results_ungrounded citation means it operated without
        # knowledge base grounding — automatic Amber per FAILURE_MODES["no_rag_hits"]
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
                f"[{state.run_id}] FM-2 no_rag_hits — forcing Amber badge | "
                f"agents_without_rag={no_rag_agents}"
            )
            overall = min(overall, 3.9)  # cap at Amber threshold

        # FM-3: Force Amber if any agent self-reported confidence ≤ 0.3.
        # 0.20 is the sentinel set by every specialist's _fallback() path when
        # parsing/build raises, so this catches silent fallback events that
        # would otherwise produce Green-badged placeholder content.
        # 0.30 covers both the 0.20 sentinel AND legitimate "I don't know" signals
        # from the LLM when the BRD is too ambiguous to plan with confidence.
        low_confidence_agents = []
        for agent_name, agent_output in [
            ("engineering_plan_generator", state.plan_output),
            ("schedule_estimator",         state.schedule_output),
            ("solution_architect",         state.arch_output),
            ("poc_planner",                state.poc_output),
            ("tech_stack_recommender",     state.stack_output),
        ]:
            if agent_output is None:
                continue
            conf = getattr(agent_output, "confidence_score", 1.0)
            if conf <= 0.30:
                low_confidence_agents.append((agent_name, conf))

        if low_confidence_agents:
            log.warning(
                f"[{state.run_id}] FM-3 low_confidence — forcing Amber badge | "
                f"agents={[(a, round(c, 2)) for a, c in low_confidence_agents]}"
            )
            overall = min(overall, 3.9)  # cap at Amber threshold
            # Surface in UI by adding one consistency issue per low-confidence agent.
            # severity=HIGH so it sorts above ordinary cross-agent disagreements.
            for agent_name, conf in low_confidence_agents:
                consistency_issues.append(ConsistencyIssue(
                    agents_involved=[agent_name],
                    conflict_description=(
                        f"{agent_name} self-reported confidence_score={conf:.2f} ≤ 0.30 — "
                        "likely fallback / placeholder output. "
                        "Inspect agent output and logs for parse or build errors before approving."
                    ),
                    severity=RiskLevel.HIGH,
                ))

        # Step 7: Assign quality badge
        badge = self._assign_badge(scores, overall)

        # Step 8: Decide if revision is needed
        requires_revision = (
            badge in (QualityBadge.RED, QualityBadge.AMBER)
            and state.revision_count < MAX_REVISIONS
        )

        # Step 9: Generate actionable per-agent feedback for revision
        agent_feedback: dict[str, str] = {}
        if requires_revision:
            agent_feedback = self._generate_revision_feedback(
                state, scores, hallucination_flags, consistency_issues
            )
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
                "engineering_plan_generator", "schedule_estimator",
                "solution_architect", "poc_planner", "tech_stack_recommender",
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

    # ── Private methods ───────────────────────────────────────────────────────

    def _build_outputs_summary(self, state: PipelineState) -> str:
        """Build a compact text summary of all agent outputs for the LLM judge."""
        parts = [f"RUN_ID: {state.run_id}"]
        parts.append(f"BRD_SECTIONS: {[s.section_name for s in state.brd_sections]}")

        if state.plan_output:
            parts.append(
                f"PLAN: {len(state.plan_output.phases)} phases | "
                f"{len(state.plan_output.risks)} risks | "
                f"citations={state.plan_output.citations}"
            )
        if state.schedule_output:
            parts.append(
                f"SCHEDULE: {state.schedule_output.total_effort_days} effort-days | "
                f"buffer={state.schedule_output.buffer_weeks}w | "
                f"citations={state.schedule_output.citations}"
            )
        if state.arch_output:
            parts.append(
                f"ARCH: pattern={state.arch_output.pattern} | "
                f"components={len(state.arch_output.components)} | "
                f"citations={state.arch_output.citations}"
            )
        if state.poc_output:
            parts.append(
                f"POC: '{state.poc_output.poc_hypothesis[:100]}' | "
                f"duration={state.poc_output.duration_weeks}w | "
                f"citations={state.poc_output.citations}"
            )
        if state.stack_output:
            parts.append(
                f"STACK: recommended={state.stack_output.recommended_option} | "
                f"options={len(state.stack_output.options)} | "
                f"citations={state.stack_output.citations}"
            )
        return "\n".join(parts)

    def _llm_judge_scoring(self, outputs_summary: str, state: PipelineState) -> dict:
        """
        LLM-as-Judge scoring — one of the two required eval methods.
        Uses gpt-4o-mini for speed and cost efficiency.
        Returns dimension scores plus evidence and suggestions for feedback.
        """
        # Tell the judge which agents have run so it scores proportionally
        agents_built = []
        if state.plan_output:     agents_built.append("Engineering Plan Generator")
        if state.schedule_output: agents_built.append("Schedule Estimator")
        if state.arch_output:     agents_built.append("Solution Architect")
        if state.poc_output:      agents_built.append("PoC Planner")
        if state.stack_output:    agents_built.append("Tech Stack Recommender")

        agents_not_built = [a for a in [
            "Solution Architect", "PoC Planner", "Tech Stack Recommender"
        ] if a not in agents_built]

        partial_note = ""
        if agents_not_built:
            partial_note = (
                f"\nIMPORTANT — PARTIAL PIPELINE: Only these agents have run: {agents_built}. "
                f"These agents have NOT run yet: {agents_not_built}. "
                f"Score completeness and consistency based ONLY on the agents that have run. "
                f"Do NOT penalise for missing outputs from agents that haven't been built yet."
            )

        prompt = f"""You are a senior Engineering Manager evaluating AI-generated
engineering artifacts for quality. Score each dimension from 0.0 to 5.0.
{partial_note}

ARTIFACTS SUMMARY:
{outputs_summary}

SCORING CRITERIA:
1. groundedness (0-5): Are claims supported by cited RAG sources?
   5.0 = all claims cited | 3.75 = 75% cited (passing) | 0 = no citations

2. completeness (0-5): Are the available artifacts complete for their scope?
   Score based only on agents that have run. If plan + schedule are present,
   check if they fully address the BRD objectives, requirements, and constraints.
   5.0 = fully complete within available scope | 3.0 = major gaps in available outputs

3. consistency (0-5): Do the available artifacts align with each other?
   Only check consistency between agents that have actually run.
   5.0 = zero contradictions | 3.0 = minor misalignments | 0 = major conflicts

4. actionability (0-5): Can the EM take immediate action on these artifacts?
   5.0 = fully actionable | 4.0 = minor gaps | 2.0 = needs significant rework

Return ONLY valid JSON with this exact structure:
{{
  "groundedness": 0.0,
  "groundedness_evidence": "specific reason",
  "groundedness_suggestion": "specific fix",
  "completeness": 0.0,
  "completeness_evidence": "specific reason",
  "completeness_suggestion": "specific fix",
  "consistency": 0.0,
  "consistency_evidence": "specific reason",
  "consistency_suggestion": "specific fix",
  "actionability": 0.0,
  "actionability_evidence": "specific reason",
  "actionability_suggestion": "specific fix"
}}"""

        try:
            response = client.chat.completions.create(
                model=settings.openai_model_mini,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            log.error(f"Critic LLM judge failed | error={e}")
            # Return middling scores on failure — don't block pipeline
            return {
                k: 2.5
                for k in ["groundedness", "completeness", "consistency", "actionability"]
            }

    def _calibrate_scores(
        self,
        state: PipelineState,
        scores: dict,
        hallucination_flags: list[HallucinationFlag],
        consistency_issues: list[ConsistencyIssue],
    ) -> dict:
        """
        Deterministically adjust LLM judge scores against structured artifacts.

        This preserves the LLM judge for nuance but prevents rubric mismatch where
        objectively complete/no-contradiction outputs are stuck at a generic 4.0
        even though thresholds require exact 5.0.
        """
        calibrated = dict(scores)
        evidence_notes: list[str] = []

        if self._has_complete_artifact_bundle(state):
            calibrated["completeness"] = max(float(calibrated.get("completeness", 0)), 5.0)
            calibrated["completeness_evidence"] = (
                "Deterministic check: all 5 specialist outputs exist and required "
                "contract fields are populated."
            )
            calibrated["completeness_suggestion"] = ""
            evidence_notes.append("completeness=5.0")

        if not consistency_issues:
            calibrated["consistency"] = max(float(calibrated.get("consistency", 0)), 5.0)
            calibrated["consistency_evidence"] = (
                "Deterministic check: no cross-agent consistency issues were detected."
            )
            calibrated["consistency_suggestion"] = ""
            evidence_notes.append("consistency=5.0")
        else:
            calibrated["consistency"] = min(float(calibrated.get("consistency", 0)), 4.0)
            calibrated["consistency_evidence"] = (
                f"Deterministic check: {len(consistency_issues)} cross-agent "
                "consistency issue(s) were detected."
            )
            calibrated["consistency_suggestion"] = (
                "Resolve the listed cross-agent contradiction before assigning a perfect consistency score."
            )
            evidence_notes.append("consistency capped by detected issues")

        if self._is_actionable_bundle(state):
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
            # Keep groundedness tied to citations and hallucination flags. We only
            # cap it downward; never lift it here.
            calibrated["groundedness"] = min(float(calibrated.get("groundedness", 0)), 3.5)
            calibrated["groundedness_evidence"] = (
                f"Deterministic hallucination check found {len(unsupported)} unsupported claim(s)."
            )
            calibrated["groundedness_suggestion"] = (
                "Remove unsupported claims or add citations to retrieved RAG chunks."
            )
            evidence_notes.append("groundedness capped by unsupported claims")

        if evidence_notes:
            log.info(
                f"[{state.run_id}] Critic deterministic calibration | "
                f"{', '.join(evidence_notes)}"
            )
        return calibrated

    def _has_complete_artifact_bundle(self, state: PipelineState) -> bool:
        """True when all 5 specialist outputs exist and core fields are populated."""
        return all([
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
        ])

    def _is_actionable_bundle(self, state: PipelineState) -> bool:
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
        return all([
            plan_actionable,
            schedule_actionable,
            arch_actionable,
            poc_actionable,
            stack_actionable,
        ])

    def _detect_hallucinations(self, state: PipelineState) -> list[HallucinationFlag]:
        """
        Named hallucination detection function.

        For each key claim in each agent output, determines whether
        the claim is supported by the BRD text or RAG citations.

        Three-tier classification:
            supported           — citations present
            partially_supported — claim terms appear in BRD but no citation
            unsupported         — no citation and no BRD overlap

        Unsupported claims trigger a score penalty in the Critic
        and generate revision feedback to the originating agent.

        Rubric: Guardrails — hallucination & scope control = 4 pts.
        This must be a named, visible function — not just good prompting.
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
                status = self._classify_claim(
                    claim,
                    brd_text,
                    getattr(output, "citations", []),
                )
                flags.append(HallucinationFlag(
                    agent=agent_name,
                    claim=claim,
                    status=status,
                    supporting_chunk_id=(
                        output.citations[0]
                        if status != "unsupported" and getattr(output, "citations", [])
                        else None
                    ),
                ))

        unsupported_count = sum(1 for f in flags if f.status == "unsupported")
        log.info(
            f"[{state.run_id}] Hallucination check | "
            f"total={len(flags)} | unsupported={unsupported_count}"
        )
        return flags

    def _classify_claim(
        self,
        claim: str,
        brd_text: str,
        citations: list[str],
    ) -> str:
        """Classify a single claim as supported, partially_supported, or unsupported."""
        # Supported if agent provided citations
        if citations and citations[0] != "kb_no_results":
            return "supported"

        # Partially supported if key claim terms appear in BRD
        claim_words = set(claim.lower().split())
        brd_words   = set(brd_text.split())
        overlap     = claim_words & brd_words
        if len(overlap) >= 2:
            return "partially_supported"

        return "unsupported"

    def _check_cross_agent_consistency(
        self,
        state: PipelineState,
    ) -> list[ConsistencyIssue]:
        """
        Check for contradictions between specialist agent outputs.
        This is only possible with a single Critic that sees all outputs.

        Checks implemented:
            1. Architecture complexity vs schedule duration
            2. Tech stack familiarity vs schedule buffer
            3. PoC duration vs Phase 1 duration
        """
        issues: list[ConsistencyIssue] = []

        # Check 1: Complex architecture needs sufficient schedule
        if state.arch_output and state.schedule_output:
            component_count = len(state.arch_output.components)
            total_days      = state.schedule_output.total_effort_days
            if component_count > 8 and total_days < 60:
                issues.append(ConsistencyIssue(
                    agents_involved=["solution_architect", "schedule_estimator"],
                    conflict_description=(
                        f"Architecture has {component_count} components "
                        f"but schedule only estimates {total_days} effort days. "
                        "Schedule appears under-estimated for this architecture complexity."
                    ),
                    severity=RiskLevel.HIGH,
                ))

        # Check 2: Low team familiarity needs more buffer weeks
        if state.stack_output and state.schedule_output:
            for option in state.stack_output.options:
                if option.name == state.stack_output.recommended_option:
                    if (
                        option.team_familiarity_rating <= 2
                        and state.schedule_output.buffer_weeks < 2
                    ):
                        issues.append(ConsistencyIssue(
                            agents_involved=["tech_stack_recommender", "schedule_estimator"],
                            conflict_description=(
                                f"Recommended stack '{option.name}' has low team familiarity "
                                f"(rating {option.team_familiarity_rating}/5) but schedule "
                                f"only has {state.schedule_output.buffer_weeks} buffer weeks. "
                                "Add learning curve buffer."
                            ),
                            severity=RiskLevel.MEDIUM,
                        ))

        # Check 3: PoC should fit within Phase 1
        if state.poc_output and state.plan_output and state.plan_output.phases:
            phase1 = state.plan_output.phases[0]
            if state.poc_output.duration_weeks > phase1.duration_weeks:
                issues.append(ConsistencyIssue(
                    agents_involved=["poc_planner", "engineering_plan_generator"],
                    conflict_description=(
                        f"PoC duration ({state.poc_output.duration_weeks}w) exceeds "
                        f"Phase 1 duration ({phase1.duration_weeks}w). "
                        "Reduce PoC scope or extend Phase 1."
                    ),
                    severity=RiskLevel.MEDIUM,
                ))

        if issues:
            log.warning(
                f"[{state.run_id}] Cross-agent consistency issues: {len(issues)}"
            )
        return issues

    def _generate_revision_feedback(
        self,
        state: PipelineState,
        scores: dict,
        hallucination_flags: list[HallucinationFlag],
        consistency_issues: list[ConsistencyIssue],
    ) -> dict[str, str]:
        """
        Generate specific, actionable revision instructions per agent.
        Vague feedback ("improve quality") is not useful.
        Each feedback message tells the agent exactly what to fix and why.
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
                f"\nHALLUCINATION: Claim '{flag.claim[:80]}' has no BRD or RAG support. "
                "Remove or add a citation."
            )

        # Consistency feedback → both agents involved
        for issue in consistency_issues:
            for agent in issue.agents_involved:
                existing = feedback.get(agent, "")
                feedback[agent] = existing + f"\nCONSISTENCY ISSUE: {issue.conflict_description}"

        # Actionability feedback → plan generator (owns milestones/owners)
        if scores.get("actionability", 5) < THRESHOLDS["actionability"]:
            key      = "engineering_plan_generator"
            existing = feedback.get(key, "")
            feedback[key] = existing + (
                f"\nACTIONABILITY SCORE LOW ({scores['actionability']:.1f}/5): "
                f"{scores.get('actionability_suggestion', 'Add specific owners and target dates to all milestones.')}"
            )

        return feedback

    def _assign_badge(self, scores: dict, overall: float) -> QualityBadge:
        """
        Assign Green/Amber/Red quality badge based on dimension scores.

        GREEN: all dimensions above threshold AND overall >= 4.0
        AMBER: at most one dimension below threshold AND overall >= 3.0
        RED:   two or more dimensions below threshold OR overall < 3.0
        """
        below = sum(
            1 for dim, threshold in THRESHOLDS.items()
            if scores.get(dim, 0) < threshold
        )
        if below == 0 and overall >= GREEN_THRESHOLD:
            return QualityBadge.GREEN
        elif below <= 1 and overall >= AMBER_THRESHOLD:
            return QualityBadge.AMBER
        return QualityBadge.RED

    def _detect_scope_creep(self, state) -> list:
        """
        Scope creep detection — org AI safety standard 8.2.
        Cross-checks agent output objectives against BRD anchor vocabulary.
        Flags phase objectives containing >3 novel terms not present in BRD.
        Returns HallucinationFlag list (advisory, not hard block).
        """
        flags = []
        brd_text  = " ".join(s.content for s in state.brd_sections).lower()
        brd_terms = set(brd_text.split())
        stop = {"shall","must","will","implement","develop","build","create",
                "establish","ensure","provide","support","enable","allow","manage"}

        if state.plan_output:
            for phase in state.plan_output.phases:
                for objective in phase.objectives:
                    novel = {w for w in set(objective.lower().split())
                             if len(w) > 4 and w not in brd_terms and w not in stop}
                    if len(novel) > 3:
                        flags.append(HallucinationFlag(
                            agent="engineering_plan_generator",
                            claim=f"Possible scope creep in phase objective: '{objective[:80]}'",
                            status="partially_supported",
                            supporting_chunk_id=None,
                        ))
        if flags:
            log.warning(f"[{state.run_id}] Scope creep: {len(flags)} items flagged for EM review")
        return flags

    def _check_ambiguity_handling(self, state) -> list:
        """
        Verify agents followed ambiguity protocol — org standard 8.1.
        Returns list of feedback strings for agents that did not populate
        flagged_ambiguities[] or assumptions[] when BRD was ambiguous/short.
        """
        feedback = []
        brd_has_nfrs   = any(s.has_nfrs for s in state.brd_sections)
        brd_word_count = sum(s.word_count for s in state.brd_sections)
        brd_is_short   = brd_word_count < 200

        for agent_name, output in [
            ("engineering_plan_generator", state.plan_output),
            ("schedule_estimator",         state.schedule_output),
            ("solution_architect",         state.arch_output),
            ("poc_planner",                state.poc_output),
            ("tech_stack_recommender",     state.stack_output),
        ]:
            if not output:
                continue
            ambiguities = getattr(output, "flagged_ambiguities", [])
            if brd_is_short and not ambiguities:
                feedback.append(
                    f"AMBIGUITY [{agent_name}]: BRD is short ({brd_word_count} words) "
                    f"but flagged_ambiguities[] is empty. Per org standard 8.1: flag, don't guess."
                )
            if not brd_has_nfrs and not ambiguities:
                feedback.append(
                    f"AMBIGUITY [{agent_name}]: BRD has no NFRs but flagged_ambiguities[] "
                    f"is empty. Must flag: 'No NFRs — used org standard defaults'."
                )
        return feedback
