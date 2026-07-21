"""
src/agents/schedule.py
═══════════════════════
Schedule Estimator Agent - Agent 3.

RAG: source_types=["timeline", "plan_template"]

Contract: ScheduleOutput
    sprints[]             - list[SprintRow] with effort_days
    total_effort_days     - MUST equal sum of sprint.effort_days
    critical_path[]       - ordered blocking deliverables
    buffer_weeks          - added beyond phase sum (min 1 for medium/complex)
    comparable_projects[] - chunk IDs of calibration projects (REQUIRED)
    citations[]           - min 1 Pinecone chunk ID
    confidence_score      - 0.0–1.0
    assumptions[]         - calibration decisions documented
    flagged_ambiguities[] - missing timeline data
"""

from __future__ import annotations

import json

from src.agents.base_agent import BaseAgent
from src.core.logger import get_logger
from src.core.models import PipelineState, ScheduleOutput, SprintRow

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior Engineering Manager estimating a project schedule.
You calibrate all estimates against historical project timelines from the knowledge base.

Rules:
1. total_effort_days MUST equal the EXACT sum of all sprint effort_days
2. comparable_projects[] MUST contain at least 1 chunk ID from the context
3. Sprint week_ranges must NOT overlap (W1-W2, W3-W5, W6-W8 etc.)
4. buffer_weeks: 0 for simple (<4 weeks), 1 for medium, 2+ for complex/AI
5. critical_path: list in dependency order - what blocks what
6. AI/LLM workloads: add 15-20% buffer for prompt engineering iteration
7. Output ONLY valid JSON - no markdown, no explanation"""

SCHEMA = """{
  "sprints": [
    {
      "sprint": integer,
      "week_range": "W1-W2",
      "deliverables": ["string"],
      "team_members": ["RoleName"],
      "effort_days": float
    }
  ],
  "total_effort_days": float,
  "critical_path": ["ordered blocking deliverable"],
  "buffer_weeks": integer,
  "comparable_projects": ["chunk_id from context"],
  "confidence_score": float,
  "assumptions": ["string"],
  "flagged_ambiguities": ["string"]
}"""


class ScheduleEstimatorAgent(BaseAgent):
    """
    Estimates sprint schedule calibrated against historical project timelines.
    comparable_projects[] makes calibration auditable.
    Inherits BaseAgent for RAG, retry, timing, logging.
    """

    def run(
        self,
        state: PipelineState,
        plan_output=None,
        feedback: str = "",
    ) -> ScheduleOutput:
        start = self.start_timer()
        log.info(f"[{state.run_id}] ScheduleEstimator start | revision={state.revision_count}")

        # On revision cycles, read plan_output from state if not explicitly passed.
        # This lets the registry dispatcher call cls().run(ps, feedback=feedback)
        # without needing special-case logic in pipeline._run_agent.
        if plan_output is None and state.revision_count > 0:
            plan_output = state.plan_output

        # ── RAG retrieval - timeline source type ──────────────────────────────
        query = self._build_query(state, plan_output)
        context_str, citation_ids = self.retrieve_context(
            query=query,
            source_types=["timeline", "plan_template"],
        )
        log.info(f"[{state.run_id}] ScheduleEstimator RAG | chunks={len(citation_ids)}")

        # ── Generate schedule ─────────────────────────────────────────────────
        raw = self._generate(state, plan_output, context_str, citation_ids, feedback)
        output = self._parse(raw, state.run_id, citation_ids)

        # ── Log ───────────────────────────────────────────────────────────────
        self.log_run(
            run_id=state.run_id,
            agent_name="schedule_estimator",
            citation_ids=citation_ids,
            critic_score=None,
            start_time=start,
            revision_count=state.revision_count,
        )
        log.info(
            f"[{state.run_id}] ScheduleEstimator done | "
            f"sprints={len(output.sprints)} total_days={output.total_effort_days} "
            f"buffer={output.buffer_weeks}w comparable={output.comparable_projects}"
        )
        return output

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_query(self, state: PipelineState, plan_output) -> str:
        parts = ["project timeline schedule sprints velocity effort days"]
        for s in state.brd_sections:
            if s.has_constraints:
                parts.append(s.content[:200])
        if plan_output:
            parts.append(
                f"{plan_output.total_duration_weeks} weeks "
                f"{len(plan_output.phases)} phases "
                f"{list(plan_output.team_composition.keys())}"
            )
        return " ".join(parts)[:400]

    def _plan_summary(self, plan_output) -> str:
        if not plan_output:
            return "No plan available - estimate directly from BRD."
        lines = [
            f"Total: {plan_output.total_duration_weeks} weeks",
            f"Team: {plan_output.team_composition}",
        ]
        for p in plan_output.phases:
            lines.append(f"  - {p.name}: {p.duration_weeks}w, {len(p.milestones)} milestones")
        return "\n".join(lines)

    def _brd_text(self, state: PipelineState) -> str:
        return "\n\n".join(f"## {s.section_name}\n{s.content}" for s in state.brd_sections)

    def _generate(
        self,
        state: PipelineState,
        plan_output,
        context_str: str,
        citation_ids: list[str],
        feedback: str,
    ) -> str:
        feedback_block = f"\nCRITIC FEEDBACK:\n{feedback}\n" if feedback else ""
        cites = "\n".join(f"  - {c}" for c in citation_ids)

        poc_summary = "No PoC planned."
        if state.poc_output:
            poc_summary = (
                f"- Hypothesis: {state.poc_output.poc_hypothesis}\n"
                f"- Duration: {state.poc_output.duration_weeks} weeks\n"
                f"- Team Size: {state.poc_output.team_size} engineer(s)"
            )

        stack_summary = "No stack recommended."
        if state.stack_output:
            stack_summary = (
                f"- Recommended Stack: {state.stack_output.recommended_option}\n"
                f"- Options Considered: {[o.name for o in state.stack_output.options]}"
            )

        return self._call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"{feedback_block}"
                f"PLAN SUMMARY:\n{self._plan_summary(plan_output)}\n\n"
                f"UPSTREAM POC DETAILS:\n{poc_summary}\n\n"
                f"RECOMMENDED TECH STACK:\n{stack_summary}\n\n"
                f"AVAILABLE CHUNK IDs (pick closest for comparable_projects):\n{cites}\n\n"
                f"HISTORICAL TIMELINES (knowledge base):\n{context_str}\n\n"
                f"BRD:\n{self._brd_text(state)}\n\n"
                f"Output ONLY JSON:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _parse(self, raw: str, run_id: str, citation_ids: list[str]) -> ScheduleOutput:
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as e:
            log.error(f"[{run_id}] ScheduleEstimator parse error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

        try:
            sprints = []
            for s in d.get("sprints", []):
                sprints.append(
                    SprintRow(
                        sprint=int(s.get("sprint", len(sprints) + 1)),
                        week_range=s.get("week_range", f"W{len(sprints) * 2 + 1}"),
                        deliverables=s.get("deliverables", ["Sprint deliverable"]),
                        team_members=s.get("team_members", ["Engineer"]),
                        effort_days=float(s.get("effort_days", 10.0)),
                    )
                )

            sprint_sum = sum(s.effort_days for s in sprints)
            total_stated = float(d.get("total_effort_days", sprint_sum))
            if abs(total_stated - sprint_sum) > 0.5:
                log.warning(f"[{run_id}] Fixing total_effort_days {total_stated}→{sprint_sum:.1f}")
                total_stated = sprint_sum

            comparable = d.get("comparable_projects", [])
            if not comparable:
                comparable = citation_ids[:2]

            import math

            sched = ScheduleOutput(
                run_id=run_id,
                citations=citation_ids,
                confidence_score=float(d.get("confidence_score", 0.7)),  # LLM value; overridden below
                assumptions=d.get("assumptions", []),
                flagged_ambiguities=d.get("flagged_ambiguities", []),
                sprints=sprints if sprints else self._default_sprints(),
                total_effort_days=float(math.ceil(total_stated)),
                critical_path=d.get("critical_path", ["Requirements sign-off", "UAT"]),
                buffer_weeks=int(d.get("buffer_weeks", 1)),
                comparable_projects=comparable,
            )
            from src.agents.confidence import compute_schedule_confidence

            sched.llm_confidence_score = sched.confidence_score
            sched.confidence_score, sched.confidence_drivers = compute_schedule_confidence(sched)
            log.info(
                f"[{run_id}] schedule confidence | llm_raw={sched.llm_confidence_score:.2f} "
                f"derived={sched.confidence_score:.2f} drivers={sched.confidence_drivers}"
            )
            return sched
        except Exception as e:
            log.error(f"[{run_id}] ScheduleEstimator build error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

    def _default_sprints(self) -> list[SprintRow]:
        return [
            SprintRow(
                sprint=1,
                week_range="W1-W2",
                deliverables=["Environment setup", "Architecture review"],
                team_members=["Tech Lead", "Engineer"],
                effort_days=10.0,
            ),
            SprintRow(
                sprint=2,
                week_range="W3-W6",
                deliverables=["Core implementation", "Unit tests"],
                team_members=["Engineer x2"],
                effort_days=20.0,
            ),
        ]

    def _fallback(self, run_id: str, citation_ids: list[str], error: str) -> ScheduleOutput:
        log.warning(f"[{run_id}] ScheduleEstimator fallback | {error[:80]}")
        sprints = self._default_sprints()
        return ScheduleOutput(
            run_id=run_id,
            citations=citation_ids or ["project_timelines_chunk_0"],
            confidence_score=0.15,
            confidence_drivers=["parse-failure fallback: agent output could not be built"],
            assumptions=["Fallback schedule - agent parse error"],
            flagged_ambiguities=["Schedule estimate unavailable"],
            sprints=sprints,
            total_effort_days=sum(s.effort_days for s in sprints),
            critical_path=["Requirements sign-off", "Core implementation", "UAT"],
            buffer_weeks=1,
            comparable_projects=citation_ids[:1] if citation_ids else ["project_timelines_chunk_0"],
        )


from src.agents.registry import register_specialist

register_specialist("schedule_estimator", ScheduleEstimatorAgent)
