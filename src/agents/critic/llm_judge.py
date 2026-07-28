"""
src/agents/critic/llm_judge.py
══════════════════════════════
LLM-as-Judge scoring for EM Copilot artifacts.
"""

from __future__ import annotations

from src.core.json_utils import parse_llm_json
from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)


def build_outputs_summary(state: PipelineState) -> str:
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


def llm_judge_scoring(outputs_summary: str, state: PipelineState) -> dict:
    """
    LLM-as-Judge scoring - one of the two required eval methods.
    Uses gpt-4o-mini for speed and cost efficiency.
    Returns dimension scores plus evidence and suggestions for feedback.
    """
    # Tell the judge which agents have run so it scores proportionally
    agents_built = []
    if state.plan_output:
        agents_built.append("Engineering Plan Generator")
    if state.schedule_output:
        agents_built.append("Schedule Estimator")
    if state.arch_output:
        agents_built.append("Solution Architect")
    if state.poc_output:
        agents_built.append("PoC Planner")
    if state.stack_output:
        agents_built.append("Tech Stack Recommender")

    agents_not_built = [
        a for a in ["Solution Architect", "PoC Planner", "Tech Stack Recommender"] if a not in agents_built
    ]

    partial_note = ""
    if agents_not_built:
        partial_note = (
            f"\nIMPORTANT - PARTIAL PIPELINE: Only these agents have run: {agents_built}. "
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

    family = state.model_family or "openai"
    from src.core.pricing import calculate_cost
    from src.core.providers import complete_with_fallback, map_model

    try:
        content, prompt_tokens, completion_tokens, final_family = complete_with_fallback(
            model_family=family,
            messages=[{"role": "user", "content": prompt}],
            model="mini",
            # 0.3 (not 0.1) introduces small run-to-run variance in the LLM judge's
            # groundedness / actionability scores. At 0.1, mini models lock onto
            # round-number priors and every run converged on overall = 4.25 exactly.
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        mapped_model = map_model(final_family, "mini")

        from src.agents.base_agent import add_cost as _add_cost
        from src.agents.base_agent import add_tokens as _add_tokens

        _add_tokens(prompt_tokens, completion_tokens, run_id=state.run_id)
        cost = calculate_cost(final_family, mapped_model, prompt_tokens, completion_tokens)
        _add_cost(cost, run_id=state.run_id)

        if final_family != family:
            state.model_family = final_family

        return parse_llm_json(content)
    except Exception as e:
        log.error(f"Critic LLM judge failed | error={e}")
        # Return middling scores on failure - don't block pipeline
        return dict.fromkeys(["groundedness", "completeness", "consistency", "actionability"], 2.5)
