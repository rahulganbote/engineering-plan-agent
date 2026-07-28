"""
src/agents/tech_stack.py
════════════════════════
Tech Stack Recommender Agent - specialist spoke.

RAG: source_types=["tech_log", "standard"]
Contract: TechStackOutput
"""

from __future__ import annotations

import json

from src.agents.base_agent import BaseAgent
from src.core.json_utils import parse_llm_json
from src.core.logger import get_logger
from src.core.models import PipelineState, RiskLevel, StackOption, TechStackOutput

log = get_logger(__name__)

SYSTEM_PROMPT = """You are a senior Engineering Manager recommending technology stack options.
Produce 2-3 grounded options with trade-offs.

Rules:
1. options must contain exactly 2 or 3 options.
2. recommended_option must match one option.name exactly.
3. Each option must include components, scalability_rating, team_familiarity_rating,
   integration_risk, estimated_monthly_cost_usd, pros, cons, and citation.
4. recommendation_rationale must reference team familiarity, cost, and risk.
5. Output ONLY valid JSON - no markdown fences, no explanation."""

SCHEMA = """{
  "options": [
    {
      "name": "string",
      "components": {"api": "FastAPI", "database": "PostgreSQL"},
      "scalability_rating": integer,
      "team_familiarity_rating": integer,
      "integration_risk": "low|medium|high",
      "estimated_monthly_cost_usd": float,
      "pros": ["string"],
      "cons": ["string"],
      "citation": "chunk_id from context"
    }
  ],
  "recommended_option": "string",
  "recommendation_rationale": "string",
  "confidence_score": 0.0,
  "assumptions": ["string"],
  "flagged_ambiguities": ["string"]
}"""


class TechStackAgent(BaseAgent):
    """Creates stack options as an independent specialist spoke."""

    def run(self, state: PipelineState, feedback: str = "", poc_veto_reason: str | None = None) -> TechStackOutput:
        start = self.start_timer()
        log.info(f"[{state.run_id}] TechStack start | revision={state.revision_count}")

        brd_text = self._brd_text(state)
        query = f"technology stack decision tradeoff cost integration platform {brd_text[:300]}"
        context_str, citation_ids = self.retrieve_context(
            query=query,
            source_types=["tech_log", "standard"],
        )

        from src.integrations.github import get_github_velocity

        github_signal = ""
        github_sources = []
        try:
            github_result = get_github_velocity.invoke({"owner": "fastapi", "repo": "fastapi"})
            github_signal = github_result.content
            # Record the tool invocation so the Critic can detect unciteed usage.
            if "get_github_velocity" not in state.tools_used:
                state.tools_used.append("get_github_velocity")
            if not github_result.used_fallback:
                github_sources = github_result.sources
        except Exception as e:
            log.warning(f"Error calling GitHub LangChain tool: {e}")
            github_signal = ""

        guardrail_triggers = ["github_api_signal_used"] if github_signal else []
        if github_sources:
            citation_ids.extend(github_sources)

        if self.has_no_rag_hits(citation_ids):
            log.info(f"[{state.run_id}] No RAG hits for TechStackAgent. Calling Tavily for live web grounding...")
            # ── Privacy boundary ────────────────────────────────────────────────
            # Tavily is third-party. Query MUST be derived metadata (section names
            # + bounded concept keywords), NOT raw BRD content. Use the helper:
            from src.integrations.tavily import build_tavily_query, tavily_search

            safe_query = build_tavily_query("recommended technology stack", state.brd_sections)
            web_results = tavily_search(safe_query)
            context_str = f"ORGANIZATION KNOWLEDGE BASE: (Empty/No matching records found)\n\nWEB GROUNDING (TAVILY SEARCH):\n{web_results.content}"
            guardrail_triggers.append("tavily_web_grounding_used")
            # Record the tool invocation so the Critic can detect unciteed usage.
            if "tavily_search" not in state.tools_used:
                state.tools_used.append("tavily_search")
            if not web_results.used_fallback:
                citation_ids = ["tavily_web_grounding"] + web_results.sources

        arch_context = ""
        if state.arch_output:
            components_str = ", ".join(f"{c.name} ({c.technology})" for c in state.arch_output.components)
            arch_context = (
                f"\nCONFIRMED ARCHITECTURE (Architect just decided):\n"
                f"- Pattern: {state.arch_output.pattern}\n"
                f"- Components: {components_str}\n"
                f"- Deployment Model: {state.arch_output.deployment_model}\n"
                f"Your tech stack recommendations MUST be compatible with these architectural choices.\n"
            )

        veto_block = ""
        if poc_veto_reason:
            veto_block = (
                f"\nPREVIOUS PoC VETO CONSTRAINT:\n{poc_veto_reason}\n"
                f"Your previous tech stack was rejected. Propose a DIFFERENT stack "
                f"that is compatible with the confirmed architecture above.\n"
            )

        raw = self._generate(
            brd_text,
            context_str,
            citation_ids,
            feedback,
            github_signal,
            arch_context=arch_context,
            veto_block=veto_block,
        )
        output = self._parse(raw, state.run_id, citation_ids)

        self.log_run(
            run_id=state.run_id,
            agent_name="tech_stack_recommender",
            citation_ids=citation_ids,
            critic_score=None,
            start_time=start,
            revision_count=state.revision_count,
            guardrail_triggers=guardrail_triggers,
        )
        log.info(
            f"[{state.run_id}] TechStack done | options={len(output.options)} recommended={output.recommended_option}"
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
        github_signal: str,
        arch_context: str = "",
        veto_block: str = "",
    ) -> str:
        feedback_block = f"\nCRITIC FEEDBACK - address all points:\n{feedback}\n" if feedback else ""
        cites = "\n".join(f"  - {c}" for c in citation_ids)
        return self._call_llm_with_retry(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=(
                f"{feedback_block}"
                f"{arch_context}"
                f"{veto_block}"
                f"AVAILABLE CITATION IDs:\n{cites}\n\n"
                f"GITHUB API SIGNAL:\n{github_signal or 'Unavailable - use org standards and BRD constraints.'}\n\n"
                f"KNOWLEDGE BASE:\n{context_str}\n\n"
                f"BRD:\n{brd_text}\n\n"
                f"Output ONLY JSON:\n{SCHEMA}"
            ),
            response_format={"type": "json_object"},
        )

    def _parse(self, raw: str, run_id: str, citation_ids: list[str]) -> TechStackOutput:
        try:
            d = parse_llm_json(raw)
        except json.JSONDecodeError as e:
            log.error(f"[{run_id}] TechStack parse error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

        try:
            first_cite = citation_ids[0] if citation_ids else "tech_decision_log_chunk_0"
            options = []
            for o in d.get("options", [])[:3]:
                cite = o.get("citation", first_cite)
                if cite not in citation_ids:
                    cite = first_cite
                options.append(
                    StackOption(
                        name=o.get("name", f"Option {len(options) + 1}"),
                        components=o.get(
                            "components",
                            {
                                "api": "FastAPI",
                                "database": "PostgreSQL",
                                "frontend": "React",
                            },
                        ),
                        scalability_rating=int(o.get("scalability_rating", 3)),
                        team_familiarity_rating=int(o.get("team_familiarity_rating", 4)),
                        integration_risk=_coerce_risk_level(o.get("integration_risk")),
                        estimated_monthly_cost_usd=float(o.get("estimated_monthly_cost_usd", 500.0)),
                        pros=o.get("pros", ["Familiar, fast to deliver"]),
                        cons=o.get("cons", ["May need refactoring at larger scale"]),
                        citation=cite,
                    )
                )

            while len(options) < 2:
                options.extend(self._default_options(first_cite)[len(options) : len(options) + 1])

            recommended = d.get("recommended_option", options[0].name)
            if recommended not in [o.name for o in options]:
                recommended = options[0].name

            stack = TechStackOutput(
                run_id=run_id,
                citations=citation_ids or [first_cite],
                confidence_score=float(d.get("confidence_score", 0.72)),  # LLM value; overridden below
                assumptions=d.get("assumptions", []),
                flagged_ambiguities=d.get("flagged_ambiguities", []),
                options=options[:3],
                recommended_option=recommended,
                recommendation_rationale=d.get(
                    "recommendation_rationale",
                    "Recommended option balances team familiarity, moderate cost, and manageable integration risk.",
                ),
            )
            from src.agents.confidence import compute_stack_confidence

            stack.llm_confidence_score = stack.confidence_score
            stack.confidence_score, stack.confidence_drivers = compute_stack_confidence(stack)
            log.info(
                f"[{run_id}] stack confidence | llm_raw={stack.llm_confidence_score:.2f} "
                f"derived={stack.confidence_score:.2f} drivers={stack.confidence_drivers}"
            )
            return stack
        except Exception as e:
            log.error(f"[{run_id}] TechStack build error: {e}")
            return self._fallback(run_id, citation_ids, str(e))

    def _default_options(self, citation: str) -> list[StackOption]:
        return [
            StackOption(
                name="Lean Python Web Stack",
                components={
                    "api": "FastAPI",
                    "frontend": "React",
                    "database": "PostgreSQL",
                    "hosting": "Container platform",
                },
                scalability_rating=3,
                team_familiarity_rating=4,
                integration_risk=RiskLevel.LOW,
                estimated_monthly_cost_usd=500.0,
                pros=["Fast delivery", "High team familiarity", "Low operational complexity"],
                cons=["May require later frontend migration for complex UX"],
                citation=citation,
            ),
            StackOption(
                name="Service-Oriented Cloud Stack",
                components={
                    "api": "FastAPI microservices",
                    "frontend": "React",
                    "database": "PostgreSQL",
                    "queue": "Managed message queue",
                },
                scalability_rating=4,
                team_familiarity_rating=3,
                integration_risk=RiskLevel.MEDIUM,
                estimated_monthly_cost_usd=1200.0,
                pros=["Better scalability", "Cleaner service boundaries"],
                cons=["Higher cost", "More DevOps overhead"],
                citation=citation,
            ),
        ]

    def _fallback(self, run_id: str, citation_ids: list[str], error: str) -> TechStackOutput:
        log.warning(f"[{run_id}] TechStack fallback | {error[:80]}")
        cite = citation_ids[0] if citation_ids else "tech_decision_log_chunk_0"
        options = self._default_options(cite)
        return TechStackOutput(
            run_id=run_id,
            citations=citation_ids or [cite],
            confidence_score=0.15,
            confidence_drivers=["parse-failure fallback: agent output could not be built"],
            assumptions=["Fallback tech stack - agent parse error"],
            flagged_ambiguities=["Tech stack output could not be parsed"],
            options=options,
            recommended_option=options[0].name,
            recommendation_rationale=(
                "Fallback recommends the lean stack because it maximizes team familiarity, "
                "keeps cost low, and minimizes integration risk."
            ),
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

register_specialist("tech_stack_recommender", TechStackAgent)
