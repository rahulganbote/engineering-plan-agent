"""
src/agents/poc_planner.py
═════════════════════════
PoC Planner Agent — specialist spoke.

RAG: source_types=["brd", "plan_template"]
Contract: PoCOutput
"""

from __future__ import annotations

import json

from src.agents.base_agent import BaseAgent
from src.core.cache import CachePolicy
from src.core.logger import get_logger
from src.core.models import PipelineState, PoCOutput, SuccessCriterion

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior Engineering Manager planning a proof of concept.
Focus on validating the riskiest assumption before full delivery.

Rules:
1. poc_hypothesis must be one clear, testable hypothesis.
2. scope_in and scope_out must be explicit.
3. success_criteria must be measurable with metric, target_value, and measurement_method.
4. duration_weeks must be realistic and conservative.
5. Flag ambiguous requirements instead of guessing silently.
6. Output ONLY valid JSON — no markdown fences, no explanation."""

SCHEMA = """{
  "poc_hypothesis": "string",
  "scope_in": ["string"],
  "scope_out": ["string"],
  "duration_weeks": integer,
  "success_criteria": [
    {
      "metric": "string",
      "target_value": "string",
      "measurement_method": "string"
    }
  ],
  "team_size": integer,
  "risk_if_poc_fails": "string",
  "confidence_score": 0.0,
  "assumptions": ["string"],
  "flagged_ambiguities": ["string"]
}"""


class PoCPlannerAgent(BaseAgent):
    """Creates a PoC scope artifact as an independent specialist spoke."""

    CACHE_POLICY = CachePolicy(mode="semantic", semantic_threshold=0.95, namespace="llm-cache.poc")

    def run(self, state: PipelineState, feedback: str = "") -> PoCOutput:
        start = self.start_timer()
        log.info(f"[{state.run_id}] PoCPlanner start | revision={state.revision_count}")

        brd_text = self._brd_text(state)
        query = f"proof of concept scope hypothesis success criteria risk {brd_text[:300]}"
        context_str, citation_ids = self.retrieve_context(
            query=query,
            source_types=["brd", "plan_template"],
        )

        raw = self._generate(brd_text, context_str, citation_ids, feedback)
        output = self._parse(raw, state.run_id, citation_ids)

        self.log_run(
            run_id=state.run_id,
            agent_name="poc_planner",
            citation_ids=citation_ids,
            critic_score=None,
            start_time=start,
            revision_count=state.revision_count,
        )
        log.info(
            f"[{state.run_id}] PoCPlanner done | "
            f"duration={output.duration_weeks}w criteria={len(output.success_criteria)}"
        )
        return output

    def _brd_text(self, state: PipelineState) -> str:
        return "\n\n".join(f"## {s.section_name}\n{s.content}" for s in state.brd_sections)

    def _generate(
        self,
        brd_text: str,
        context_str: str,
        citation_ids: list[str],
        feedback: str,
    ) -> str:
        feedback_block = f"\nCRITIC FEEDBACK — address all points:\n{feedback}\n" if feedback else ""
        cites = "\n".join(f"  - {c}" for c in citation_ids)
        return self._call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"{feedback_block}"
                f"AVAILABLE CITATION IDs:\n{cites}\n\n"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                f"BRD:\n{brd_text}\n\n"
                f"Output ONLY JSON:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _parse(self, raw: str, run_id: str, citation_ids: list[str]) -> PoCOutput:
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error(f"[{run_id}] PoCPlanner parse error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

        try:
            criteria = [
                SuccessCriterion(
                    metric=c.get("metric", "PoC success rate"),
                    target_value=c.get("target_value", ">= 80%"),
                    measurement_method=c.get("measurement_method", "Measured through test execution"),
                )
                for c in d.get("success_criteria", [])
            ]
            return PoCOutput(
                run_id=run_id,
                citations=citation_ids or ["poc_plan_chunk_0"],
                confidence_score=float(d.get("confidence_score", 0.72)),
                assumptions=d.get("assumptions", []),
                flagged_ambiguities=d.get("flagged_ambiguities", []),
                poc_hypothesis=d.get(
                    "poc_hypothesis",
                    "The riskiest integration and workflow assumptions can be validated with a narrow PoC.",
                ),
                scope_in=d.get("scope_in", ["Validate core workflow", "Validate highest-risk integration"]),
                scope_out=d.get("scope_out", ["Full production hardening", "All reporting and edge cases"]),
                duration_weeks=int(d.get("duration_weeks", 2)),
                success_criteria=criteria or self._default_criteria(),
                team_size=int(d.get("team_size", 2)),
                risk_if_poc_fails=d.get(
                    "risk_if_poc_fails",
                    "Revisit architecture, timeline, or vendor assumptions before full implementation.",
                ),
            )
        except Exception as e:
            log.error(f"[{run_id}] PoCPlanner build error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

    def _default_criteria(self) -> list[SuccessCriterion]:
        return [
            SuccessCriterion(
                metric="Core workflow completion",
                target_value=">= 80% of scripted scenarios pass",
                measurement_method="Run PoC test scenarios against representative BRD flows",
            ),
            SuccessCriterion(
                metric="Critical integration feasibility",
                target_value="Successful request/response and error handling demonstrated",
                measurement_method="Execute integration spike with logged success and failure cases",
            ),
        ]

    def _fallback(self, run_id: str, citation_ids: list[str], error: str) -> PoCOutput:
        log.warning(f"[{run_id}] PoCPlanner fallback | {error[:80]}")
        cite = citation_ids[0] if citation_ids else "poc_plan_chunk_0"
        return PoCOutput(
            run_id=run_id,
            citations=citation_ids or [cite],
            confidence_score=0.2,
            assumptions=["Fallback PoC plan — agent parse error"],
            flagged_ambiguities=["PoC output could not be parsed"],
            poc_hypothesis="Validate the highest-risk workflow and integration before full build.",
            scope_in=["Core happy path", "Highest-risk integration", "Basic success metrics"],
            scope_out=["Production rollout", "Full observability", "All non-critical edge cases"],
            duration_weeks=2,
            success_criteria=self._default_criteria(),
            team_size=2,
            risk_if_poc_fails="Escalate to EM for rescoping before committing to full delivery.",
        )


from src.agents.registry import register_specialist

register_specialist("poc_planner", PoCPlannerAgent)
