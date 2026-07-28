"""
src/agents/plan_generator.py
═════════════════════════════
Engineering Plan Generator Agent - Agent 2.

Pattern: Reflection (draft → self-critique → final JSON)
RAG:     source_types=["brd", "plan_template"]

Contract: EngineeringPlanOutput
    phases[]              - list[Phase] with milestones[{owner_role required}]
    risks[]               - list[Risk] with citation on EVERY item
    team_composition      - dict role → headcount
    total_duration_weeks  - MUST equal sum of phase.duration_weeks
    reflection_notes      - self-critique output (Reflection pattern)
    citations[]           - min 1 Pinecone chunk ID (AgentOutputBase)
    confidence_score      - 0.0–1.0
    assumptions[]         - conservative choices documented
    flagged_ambiguities[] - ambiguous/missing BRD elements
"""

from __future__ import annotations

import json

from src.agents.base_agent import BaseAgent
from src.core.json_utils import parse_llm_json
from src.core.logger import get_logger
from src.core.models import (
    EngineeringPlanOutput,
    Milestone,
    Phase,
    PipelineState,
    Risk,
    RiskLevel,
)

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior Engineering Manager generating a structured
engineering plan from a BRD. You follow the Reflection pattern:
  Step 1 - Draft an initial plan
  Step 2 - Critique your own draft for gaps
  Step 3 - Output improved JSON

Rules:
1. Every milestone MUST have owner_role (e.g. "Tech Lead", "EM", "QA Engineer", "DevOps")
2. Every risk MUST have a citation field - use a chunk ID from the context below
3. total_duration_weeks MUST equal the exact sum of all phase.duration_weeks
4. reflection_notes MUST document what you improved between draft and final
5. When BRD is ambiguous, choose the CONSERVATIVE interpretation and document it
6. Output ONLY valid JSON - no markdown fences, no explanation"""

SCHEMA = """{
  "phases": [
    {
      "name": "string",
      "duration_weeks": integer,
      "objectives": ["string"],
      "milestones": [
        {
          "name": "string",
          "week": integer,
          "deliverable": "string - specific and testable",
          "owner_role": "string - e.g. Tech Lead, EM, QA Engineer"
        }
      ]
    }
  ],
  "risks": [
    {
      "description": "string",
      "likelihood": "low|medium|high",
      "impact": "low|medium|high",
      "mitigation": "string - specific action",
      "citation": "string - chunk_id from context"
    }
  ],
  "team_composition": {"RoleName": integer},
  "total_duration_weeks": integer,
  "reflection_notes": "string - what you improved from draft to final",
  "confidence_score": float,
  "assumptions": ["string"],
  "flagged_ambiguities": ["string"]
}"""


class PlanGeneratorAgent(BaseAgent):
    """
    Generates phased engineering plan using Reflection pattern.
    Inherits BaseAgent for RAG retrieval, LLM retry, timing, and JSONL logging.
    """

    def run(self, state: PipelineState, feedback: str = "") -> EngineeringPlanOutput:
        start = self.start_timer()
        log.info(f"[{state.run_id}] PlanGenerator start | revision={state.revision_count}")

        # ── RAG retrieval ─────────────────────────────────────────────────────
        brd_text = self._brd_text(state)
        query = f"engineering plan phases milestones risks team {brd_text[:300]}"
        context_str, citation_ids = self.retrieve_context(
            query=query,
            source_types=["brd", "plan_template"],
        )
        log.info(f"[{state.run_id}] PlanGenerator RAG | chunks={len(citation_ids)}")

        # Construct PoC context constraint if it exists
        poc_context = ""
        if state.poc_output:
            poc_context = (
                f"\n\nPLANNING CONSTRAINT (Upstream PoC committed):\n"
                f"- PoC Duration: {state.poc_output.duration_weeks} weeks\n"
                f"- PoC Team Size: {state.poc_output.team_size} engineer(s)\n"
                f"- PoC Hypothesis & Scope: {state.poc_output.poc_hypothesis}\n"
                f"CRITICAL RULE: The duration of the first phase (e.g. Discovery/PoC Phase) in your plan MUST be at least equal to the PoC duration ({state.poc_output.duration_weeks} weeks) because the PoC must run first.\n"
            )

        from src.agents.base_agent import _current_model_family

        _family = (_current_model_family() or "openai").lower()

        if _family == "anthropic":
            log.info(f"[{state.run_id}] PlanGenerator using optimized single-turn generation for Anthropic")
            raw = self._generate_direct(brd_text, context_str, feedback, citation_ids, poc_context)
        else:
            # ── Reflection Step 1: Draft ──────────────────────────────────────────
            draft = self._draft(brd_text, context_str, feedback, poc_context)

            # ── Reflection Step 2+3: Critique + Final JSON ────────────────────────
            raw = self._reflect_and_finalize(brd_text, draft, context_str, citation_ids, poc_context)

        # ── Parse + validate ──────────────────────────────────────────────────
        output = self._parse(raw, state.run_id, citation_ids)

        # ── Log execution ─────────────────────────────────────────────────────
        self.log_run(
            run_id=state.run_id,
            agent_name="engineering_plan_generator",
            citation_ids=citation_ids,
            critic_score=None,
            start_time=start,
            revision_count=state.revision_count,
        )
        log.info(
            f"[{state.run_id}] PlanGenerator done | "
            f"phases={len(output.phases)} risks={len(output.risks)} "
            f"weeks={output.total_duration_weeks}"
        )
        return output

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _brd_text(self, state: PipelineState) -> str:
        return "\n\n".join(f"## {s.section_name}\n{s.content}" for s in state.brd_sections)

    def _draft(self, brd_text: str, context_str: str, feedback: str, poc_context: str = "") -> str:
        feedback_block = f"\nCRITIC FEEDBACK - address all points:\n{feedback}\n" if feedback else ""
        return self._call_llm_with_retry(
            system_prompt="You are a senior Engineering Manager. Draft an engineering plan.",
            user_prompt=(
                f"{feedback_block}"
                f"{poc_context}"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                f"BRD:\n{brd_text}\n\n"
                "Write a draft engineering plan - phases, milestones with owners, risks, team."
            ),
        )

    def _reflect_and_finalize(
        self,
        brd_text: str,
        draft: str,
        context_str: str,
        citation_ids: list[str],
        poc_context: str = "",
    ) -> str:
        cites = "\n".join(f"  - {c}" for c in citation_ids)
        return self._call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"DRAFT:\n{draft}\n\n"
                f"AVAILABLE CITATION IDs (use for risk.citation):\n{cites}\n\n"
                f"{poc_context}"
                f"BRD:\n{brd_text}\n\n"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                "Review the draft. Fix: missing owner_role, vague deliverables, "
                "risk citations, total_duration_weeks arithmetic. "
                f"Output ONLY JSON:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _generate_direct(
        self, brd_text: str, context_str: str, feedback: str, citation_ids: list[str], poc_context: str = ""
    ) -> str:
        feedback_block = f"\nCRITIC FEEDBACK - address all points:\n{feedback}\n" if feedback else ""
        cites = "\n".join(f"  - {c}" for c in citation_ids)
        return self._call_llm_with_retry(
            system_prompt="""You are a senior Engineering Manager generating a structured
engineering plan from a BRD.

Rules:
1. Every milestone MUST have owner_role (e.g. "Tech Lead", "EM", "QA Engineer", "DevOps")
2. Every risk MUST have a citation field - use a chunk ID from the context below
3. total_duration_weeks MUST equal the exact sum of all phase.duration_weeks
4. reflection_notes MUST document how you optimized the plan structure and risks
5. When BRD is ambiguous, choose the CONSERVATIVE interpretation and document it
6. Output ONLY valid JSON - no markdown fences, no explanation""",
            user_prompt=(
                f"{feedback_block}"
                f"{poc_context}"
                f"AVAILABLE CITATION IDs (use for risk.citation):\n{cites}\n\n"
                f"BRD:\n{brd_text}\n\n"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                f"Generate an engineering plan based on the BRD and knowledge base. "
                f"Output ONLY JSON matching the schema below:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _parse(self, raw: str, run_id: str, citation_ids: list[str]) -> EngineeringPlanOutput:
        try:
            d = parse_llm_json(raw)
        except json.JSONDecodeError as e:
            log.error(f"[{run_id}] PlanGenerator parse error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

        try:
            phases = []
            for p in d.get("phases", []):
                milestones = [
                    Milestone(
                        name=m.get("name", "Milestone"),
                        week=int(m.get("week", 1)),
                        deliverable=m.get("deliverable", "TBD"),
                        owner_role=m.get("owner_role", "Tech Lead"),
                    )
                    for m in p.get("milestones", [])
                ]
                phases.append(
                    Phase(
                        name=p.get("name", "Phase"),
                        duration_weeks=int(p.get("duration_weeks", 2)),
                        objectives=p.get("objectives", ["Deliver phase"]),
                        milestones=milestones,
                    )
                )

            first_cite = citation_ids[0] if citation_ids else "plan_templates_chunk_0"
            risks = []
            for r in d.get("risks", []):
                cite = r.get("citation", first_cite)
                if cite not in citation_ids:
                    cite = first_cite
                risks.append(
                    Risk(
                        description=r.get("description", "Risk identified"),
                        likelihood=_coerce_risk_level(r.get("likelihood")),
                        impact=_coerce_risk_level(r.get("impact")),
                        mitigation=r.get("mitigation", "Monitor and address proactively"),
                        citation=cite,
                    )
                )

            # Enforce total_duration_weeks == sum of phases
            phase_sum = sum(p.duration_weeks for p in phases)
            total_weeks = d.get("total_duration_weeks", phase_sum)
            if int(total_weeks) != phase_sum:
                log.warning(f"[{run_id}] Fixing total_duration_weeks {total_weeks}→{phase_sum}")
                total_weeks = phase_sum

            plan = EngineeringPlanOutput(
                run_id=run_id,
                citations=citation_ids,
                confidence_score=float(d.get("confidence_score", 0.72)),  # LLM value; overridden below
                assumptions=d.get("assumptions", []),
                flagged_ambiguities=d.get("flagged_ambiguities", []),
                phases=phases,
                risks=risks if risks else [self._default_risk(first_cite)],
                team_composition=d.get("team_composition", {"Engineer": 2}),
                total_duration_weeks=int(total_weeks),
                reflection_notes=d.get(
                    "reflection_notes", "Milestones clarified with owner_role. Risks cited to KB chunks."
                ),
            )
            # Derive confidence from verifiable signals; discards LLM self-report
            # for the primary confidence_score but preserves it on the object as
            # llm_confidence_score so the HITL gate can surface a review flag
            # when the two disagree by more than 0.20.
            from src.agents.confidence import compute_plan_confidence

            plan.llm_confidence_score = plan.confidence_score
            plan.confidence_score, plan.confidence_drivers = compute_plan_confidence(plan)
            log.info(
                f"[{run_id}] plan confidence | llm_raw={plan.llm_confidence_score:.2f} "
                f"derived={plan.confidence_score:.2f} drivers={plan.confidence_drivers}"
            )
            return plan
        except Exception as e:
            log.error(f"[{run_id}] PlanGenerator build error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

    def _default_risk(self, citation: str) -> Risk:
        return Risk(
            description="Timeline slippage due to scope ambiguity",
            likelihood=RiskLevel.MEDIUM,
            impact=RiskLevel.MEDIUM,
            mitigation="Weekly stakeholder alignment to resolve open questions",
            citation=citation,
        )

    def _fallback(self, run_id: str, citation_ids: list[str], error: str) -> EngineeringPlanOutput:
        log.warning(f"[{run_id}] PlanGenerator fallback | {error[:80]}")
        cite = citation_ids[0] if citation_ids else "plan_templates_chunk_0"
        return EngineeringPlanOutput(
            run_id=run_id,
            citations=citation_ids or [cite],
            confidence_score=0.15,  # sentinel - distinct from any legitimate derived low score
            confidence_drivers=["parse-failure fallback: agent output could not be built"],
            assumptions=["Fallback output - agent parse error"],
            flagged_ambiguities=["Agent output could not be parsed"],
            phases=[
                Phase(
                    name="Discovery",
                    duration_weeks=2,
                    objectives=["Clarify requirements", "Technical spike"],
                    milestones=[
                        Milestone(
                            name="Requirements sign-off",
                            week=2,
                            deliverable="Signed requirements document",
                            owner_role="EM",
                        )
                    ],
                )
            ],
            risks=[self._default_risk(cite)],
            team_composition={"Engineer": 2},
            total_duration_weeks=2,
            reflection_notes=f"Fallback output due to parse error: {error[:100]}",
        )


# ── RiskLevel coercion ────────────────────────────────────────────────────────
# LLMs sometimes emit risk levels outside the enum's exact values
# (e.g. "very high", "severe", "minimal", "extreme"). This helper normalizes
# any string to the closest valid RiskLevel rather than raising ValidationError.

_RISK_LEVEL_ALIASES = {
    "low": "low",
    "minimal": "low",
    "minor": "low",
    "negligible": "low",
    "medium": "medium",
    "moderate": "medium",
    "mid": "medium",
    "normal": "medium",
    "high": "high",
    "elevated": "high",
    "severe": "high",
    "major": "high",
    "critical": "critical",
    "extreme": "critical",
    "very high": "critical",
    "veryhigh": "critical",
    "blocker": "critical",
}


def _coerce_risk_level(value, default: str = "medium") -> RiskLevel:
    """Best-effort map ANY input to a valid RiskLevel. Never raises."""
    if isinstance(value, RiskLevel):
        return value
    if value is None:
        return RiskLevel(default)
    key = str(value).strip().lower()
    mapped = _RISK_LEVEL_ALIASES.get(key)
    if mapped:
        return RiskLevel(mapped)
    # Fallback: if the LLM emitted something we haven't mapped, log + use default
    log.warning(f"Unknown RiskLevel value {value!r} - coercing to {default!r}")
    return RiskLevel(default)


from src.agents.registry import register_specialist

register_specialist("engineering_plan_generator", PlanGeneratorAgent)
