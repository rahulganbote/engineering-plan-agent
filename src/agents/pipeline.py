"""
src/agents/pipeline.py
═══════════════════════
LangGraph StateGraph - central Orchestrator hub-and-spoke pipeline.

Design:
    orchestrator_hub
      → dispatch_specialists   (fan-out from Orchestrator; selected spokes run concurrently)
      → aggregate_outputs      (fan-in; Pydantic outputs collected on PipelineState)
      → critic                 (single Critic reviews complete bundle)
      → decision_router        (Green → HITL; Amber/Red → targeted revision or EM flag)

Hub-and-spoke invariants:
    - Specialist agents never call each other.
    - Critic never calls specialist agents.
    - All revision feedback is mediated by the Orchestrator Decision Router.
    - PipelineState is owned and updated by Orchestrator/pipeline nodes.
"""

from __future__ import annotations

import time
from typing import Literal

from langgraph.graph import END, StateGraph

import src.agents  # noqa: F401 - side-effect: registers all specialists
from src.agents.base_agent import (
    _current_model_family,
    get_cost,
    get_token_counts,
    reset_token_counter,
    set_current_run_id,
)
from src.agents.critic import CriticAgent
from src.agents.orchestrator import OrchestratorAgent
from src.agents.registry import get_specialist
from src.core.config import settings
from src.core.logger import get_logger, log_pipeline_summary
from src.core.models import PipelineState
from src.core.pipeline_status import PipelineStatus

log = get_logger(__name__)
MAX_REVISIONS = settings.max_critic_revisions

AGENT_OUTPUT_FIELDS: dict[str, str] = {
    "engineering_plan_generator": "plan_output",
    "schedule_estimator": "schedule_output",
    "solution_architect": "arch_output",
    "poc_planner": "poc_output",
    "tech_stack_recommender": "stack_output",
}

ALL_SPECIALIST_AGENTS = list(AGENT_OUTPUT_FIELDS.keys())


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ps(state: dict) -> PipelineState:
    """Deserialize dict → PipelineState while preserving private graph keys outside it."""
    return PipelineState(**{k: v for k, v in state.items() if not k.startswith("_")})


def _dump(ps: PipelineState, state: dict) -> dict:
    """Serialize PipelineState → dict, preserving private graph keys."""
    d = ps.model_dump()
    for k, v in state.items():
        if k.startswith("_"):
            d[k] = v
    return d


def _get_other_drafts_summary(ps: PipelineState, target_agent: str) -> str:
    lines = []
    if target_agent != "solution_architect" and ps.draft_arch_output:
        lines.append(
            f"- Solution Architect Draft: Pattern={ps.draft_arch_output.pattern}, Components={[{c.name: c.technology} for c in ps.draft_arch_output.components]}"
        )
    if target_agent != "tech_stack_recommender" and ps.draft_stack_output:
        lines.append(f"- Tech Stack Draft: Recommended={ps.draft_stack_output.recommended_option}")
    if target_agent != "poc_planner" and ps.draft_poc_output:
        lines.append(
            f"- PoC Planner Draft: Duration={ps.draft_poc_output.duration_weeks}w, Requires Stack Revision={ps.draft_poc_output.requires_tech_stack_revision}"
        )
    if target_agent != "engineering_plan_generator" and ps.draft_plan_output:
        lines.append(
            f"- Plan Generator Draft: Duration={sum(p.duration_weeks for p in ps.draft_plan_output.phases)}w, Phases={[{p.name: p.duration_weeks} for p in ps.draft_plan_output.phases]}"
        )
    if target_agent != "schedule_estimator" and ps.draft_schedule_output:
        lines.append(f"- Schedule Estimator Draft: Sprints={len(ps.draft_schedule_output.sprints)}")
    return "\n".join(lines)


def _feedback_for(ps: PipelineState, agent_name: str) -> str:
    parts = []
    # If in Pass 2 and we have an alignment memo, add directives
    if ps.pass_number == 2 and ps.alignment_memo:
        for d in ps.alignment_memo.directives:
            if d.agent_name == agent_name:
                parts.append(
                    f"ORCHESTRATOR EM ALIGNMENT DIRECTIVE (Pass 2):\n"
                    f"You must align your output to satisfy the following directive:\n"
                    f"- Action: {d.directive}\n"
                    f"- Reasoning: {d.reasoning}\n"
                    f"- BRD Evidence: {d.evidence or '(none)'}\n\n"
                    f"Also, review the drafts of the other agents from Pass 1 for coordination:\n"
                    f"{_get_other_drafts_summary(ps, agent_name)}"
                )

    # Standard Critic revision feedback
    if ps.critic_output and ps.critic_output.agent_feedback:
        base = ps.critic_output.agent_feedback.get(agent_name, "")
        if base:
            parts.append(f"CRITIC REVISION FEEDBACK:\n{base}")

    return "\n\n".join(parts)


def _safe_emit(event_type: str, **fields) -> None:
    """Best-effort event emit. Never raises - observability cannot break the pipeline."""
    try:
        from src.core.events import emit

        emit(event_type, **fields)
    except Exception:
        pass


def _set_status(ps: PipelineState, status: PipelineStatus) -> None:
    """Set pipeline_status and emit a status event to the client.

    Idempotent: if the requested status equals the current one, this is a
    no-op. Several graph nodes legitimately set the same status back-to-back
    (e.g. orchestrator hub sets `specialist_executing` at its exit, and
    dispatch_specialists sets it again at its entry). Without this guard,
    every same-status re-set would emit a duplicate pipeline_status SSE event
    and the console log would stutter on every transition.

    Cancellation checkpoint: before mutating status, check the cooperative
    cancel flag. If set, raise RunCanceledError so tasks.py can unwind. This
    means cancellation is observed between LangGraph nodes (in-flight LLM
    calls still complete first). Cheap; the flag lookup is a dict hit.
    """
    _raise_if_canceled(ps)
    if ps.pipeline_status == status.value:
        return  # No change - suppress redundant SSE emit.
    ps.pipeline_status = status.value
    _safe_emit("pipeline_status", status=status.value)


def _raise_if_canceled(ps: PipelineState) -> None:
    """Cooperative cancel probe. Called from _set_status at every transition."""
    try:
        from src.api.state import _run_cancel_flags
        from src.core.exceptions import RunCanceledError

        if _run_cancel_flags.get(ps.run_id):
            raise RunCanceledError("Run canceled by user.")
    except RunCanceledError:
        raise
    except Exception:
        # If the import path is unavailable (unusual test config etc.), don't
        # let cancellation infrastructure break the pipeline.
        return


def _revision_targets(ps: PipelineState) -> list[str]:
    """
    Decide which agents should rerun during a revision cycle.
    Critic feedback targets exact agent names. Cross-agent consistency findings
    add all involved agents so paired contradictions can be repaired together.
    """
    targets: set[str] = set()

    if ps.critic_output:
        targets.update(ps.critic_output.agent_feedback.keys())
        for issue in ps.critic_output.consistency_issues:
            targets.update(issue.agents_involved)

    return [a for a in ALL_SPECIALIST_AGENTS if a in targets]


def _run_agent(agent_name: str, ps: PipelineState):
    """Run one specialist spoke. Called from Orchestrator dispatch worker threads."""
    set_current_run_id(ps.run_id, ps.model_family, ps.enable_fallback)
    _safe_emit("agent_start", agent=agent_name)
    feedback = _feedback_for(ps, agent_name)
    cls = get_specialist(agent_name)
    try:
        res = cls().run(ps, feedback=feedback)
    except Exception:
        # Surface to UI: chip flips from "in progress" → "failed" instead of staying stuck.
        _safe_emit("agent_failed", agent=agent_name)
        raise
    _safe_emit("agent_complete", agent=agent_name)
    return res


# ── Node functions ────────────────────────────────────────────────────────────


def node_orchestrator_hub(state: dict) -> dict:
    """Parse BRD, build routing plan, and initialize hub-owned PipelineState."""
    ps = _ps(state)
    brd_text = state.get("_brd_text", "")
    log.info(f"[{ps.run_id}] NODE orchestrator_hub")
    _safe_emit("agent_start", agent="orchestrator")
    _set_status(ps, PipelineStatus.RUNNING)

    if not brd_text:
        ps.errors.append("No BRD text provided")
        _set_status(ps, PipelineStatus.ERROR)
        return _dump(ps, state)

    output, sections = OrchestratorAgent().run(brd_text, ps.run_id)
    ps.brd_sections = sections
    _set_status(ps, PipelineStatus.SPECIALIST_EXECUTING if output.validation_passed else PipelineStatus.ERROR)
    state["_routing_plan"] = output.routing_plan
    state["_revision_targets"] = ALL_SPECIALIST_AGENTS.copy()

    _safe_emit("agent_complete", agent="orchestrator")

    if not output.validation_passed:
        ps.errors.extend(output.validation_errors)

    return _dump(ps, state)


def _run_specialists_in_parallel(ps: PipelineState, target_agents: list[str]) -> dict:
    # NOTE: specialists must NOT mutate `ps` during parallel execution. They may
    # only READ from state and RETURN their output. The dispatcher writes results
    # back to state after all futures complete.
    from concurrent.futures import ThreadPoolExecutor

    log.info(f"[{ps.run_id}] Dispatching {len(target_agents)} specialists in parallel: {target_agents}")

    with ThreadPoolExecutor(max_workers=len(target_agents)) as executor:
        futures = {executor.submit(_run_agent, agent_name, ps): agent_name for agent_name in target_agents}
        results = {}
        for f in futures:
            agent_name = futures[f]
            try:
                results[agent_name] = f.result()
            except Exception as e:
                log.error(f"[{ps.run_id}] Parallel specialist {agent_name} failed: {e}")
                raise
        return results


def node_pass1_drafting(state: dict) -> dict:
    """Pass 1: Generate initial draft options in parallel."""
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return _dump(ps, state)

    log.info(f"[{ps.run_id}] NODE pass1_drafting starting")
    _set_status(ps, PipelineStatus.SPECIALIST_EXECUTING)

    ps.pass_number = 1

    try:
        # Run all 5 specialists in parallel
        results = _run_specialists_in_parallel(ps, ALL_SPECIALIST_AGENTS)

        # Save drafts to PipelineState
        ps.draft_arch_output = results.get("solution_architect")
        ps.draft_stack_output = results.get("tech_stack_recommender")
        ps.draft_poc_output = results.get("poc_planner")
        ps.draft_plan_output = results.get("engineering_plan_generator")
        ps.draft_schedule_output = results.get("schedule_estimator")

        # Also populate standard outputs so downstream code doesn't crash during drafting.
        # TODO: Pass 1 outputs are placeholder — replaced by Pass 2 unless error occurs.
        ps.arch_output = ps.draft_arch_output
        ps.stack_output = ps.draft_stack_output
        ps.poc_output = ps.draft_poc_output
        ps.plan_output = ps.draft_plan_output
        ps.schedule_output = ps.draft_schedule_output

    except Exception as e:
        log.error(f"[{ps.run_id}] pass1_drafting execution failed: {e}")
        ps.errors.append(f"pass1_drafting: {str(e)[:280]}")
        _set_status(ps, PipelineStatus.ERROR)

    return _dump(ps, state)


def node_arbitrate(state: dict) -> dict:
    """Orchestrator arbitrates the drafts to generate the Alignment Memo."""
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return _dump(ps, state)

    log.info(f"[{ps.run_id}] NODE arbitrate starting")
    _safe_emit("agent_start", agent="orchestrator")

    try:
        memo = OrchestratorAgent().arbitrate_drafts(ps)
        ps.alignment_memo = memo
        _safe_emit("orchestrator_reconciled", directive_count=len(memo.directives))
        log.info(f"[{ps.run_id}] NODE arbitrate complete. Issued {len(memo.directives)} directives.")
    except Exception as e:
        log.error(f"[{ps.run_id}] Orchestrator arbitration failed, falling back: {e}")
        from src.core.models import AlignmentMemo

        ps.alignment_memo = AlignmentMemo()

    _safe_emit("agent_complete", agent="orchestrator")
    return _dump(ps, state)


def node_pass2_alignment(state: dict) -> dict:
    """Pass 2: Specialists refine and align their outputs using the Alignment Memo."""
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return _dump(ps, state)

    log.info(f"[{ps.run_id}] NODE pass2_alignment starting")
    _set_status(ps, PipelineStatus.SPECIALIST_EXECUTING)

    ps.pass_number = 2

    # Rerun targeted revision agents
    targets = state.get("_revision_targets", ALL_SPECIALIST_AGENTS)
    if not targets:
        targets = ALL_SPECIALIST_AGENTS

    try:
        results = _run_specialists_in_parallel(ps, targets)

        # Save or update final outputs
        if "solution_architect" in results:
            ps.arch_output = results.get("solution_architect")
        if "tech_stack_recommender" in results:
            ps.stack_output = results.get("tech_stack_recommender")
        if "poc_planner" in results:
            ps.poc_output = results.get("poc_planner")
        if "engineering_plan_generator" in results:
            ps.plan_output = results.get("engineering_plan_generator")
        if "schedule_estimator" in results:
            ps.schedule_output = results.get("schedule_estimator")

        # Apply Schedule Estimator effort scaling logic on final outputs
        plan_output = ps.plan_output
        output = ps.schedule_output
        if plan_output and output:
            team_size = sum(plan_output.team_composition.values())
            min_effort = plan_output.total_duration_weeks * team_size * 5 * 0.70
            if output.total_effort_days < min_effort:
                log.info(
                    f"[{ps.run_id}] Schedule sanity check: "
                    f"raising total_effort_days from {output.total_effort_days} to {min_effort:.1f}"
                )
                sprints = output.sprints
                sprint_sum = sum(s.effort_days for s in sprints)
                if sprint_sum > 0:
                    scale_factor = min_effort / sprint_sum
                    for s in sprints:
                        s.effort_days = round(s.effort_days * scale_factor, 1)
                else:
                    avg_effort = round(min_effort / len(sprints), 1) if sprints else 0
                    for s in sprints:
                        s.effort_days = avg_effort
                output.total_effort_days = round(sum(s.effort_days for s in sprints), 1)

    except Exception as e:
        log.error(f"[{ps.run_id}] pass2_alignment execution failed: {e}")
        ps.errors.append(f"pass2_alignment: {str(e)[:280]}")
        _set_status(ps, PipelineStatus.ERROR)

    return _dump(ps, state)


def node_critic(state: dict) -> dict:
    """Send complete artifact bundle to the Critic."""
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE critic | rev={ps.revision_count}")

    if ps.pipeline_status == "error":
        return _dump(ps, state)

    _set_status(ps, PipelineStatus.EVALUATING)
    _safe_emit("agent_start", agent="critic")

    try:
        ps.critic_output = CriticAgent().run(ps)
        ps.critic_scores_history.append(
            {
                "revision": ps.revision_count,
                "groundedness": ps.critic_output.groundedness.score,
                "completeness": ps.critic_output.completeness.score,
                "consistency": ps.critic_output.consistency.score,
                "actionability": ps.critic_output.actionability.score,
                "overall": ps.critic_output.overall_score,
                "badge": ps.critic_output.badge.value,
            }
        )
        _safe_emit("agent_complete", agent="critic")
        log.info(
            f"[{ps.run_id}] Critic score | overall={ps.critic_output.overall_score:.2f} "
            f"badge={ps.critic_output.badge.value} "
            f"requires_revision={ps.critic_output.requires_revision}"
        )
    except Exception as e:
        _safe_emit("agent_failed", agent="critic")
        log.error(f"[{ps.run_id}] critic error: {e}")
        ps.errors.append(f"critic: {str(e)[:140]}")
        _set_status(ps, PipelineStatus.ERROR)

    return _dump(ps, state)


def node_decision_router(state: dict) -> dict:
    """
    Orchestrator Decision Router.
    Amber/Red revises targeted agents until max cycles; otherwise routes to HITL.
    """
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE decision_router | rev={ps.revision_count}")

    if ps.errors:
        _set_status(ps, PipelineStatus.ERROR)
        return _dump(ps, state)

    if not ps.critic_output:
        ps.errors.append("Critic output missing")
        _set_status(ps, PipelineStatus.ERROR)
        return _dump(ps, state)

    should_revise = ps.critic_output.requires_revision and ps.revision_count < MAX_REVISIONS

    if should_revise:
        ps.revision_count += 1
        _set_status(ps, PipelineStatus.REVISING)
        state["_reran_upstream"] = False
        log.info(f"[{ps.run_id}] Revision cycle {ps.revision_count}/{MAX_REVISIONS}")
    else:
        reason = "max_revisions" if ps.revision_count >= MAX_REVISIONS else "quality_gate"
        log.info(f"[{ps.run_id}] Routing to HITL | badge={ps.critic_output.badge.value} reason={reason}")

    return _dump(ps, state)


def node_await_hitl(state: dict) -> dict:
    """Pause point for FastAPI/React HITL approval."""
    ps = _ps(state)
    _set_status(ps, PipelineStatus.AWAITING_HITL)
    badge = ps.critic_output.badge.value if ps.critic_output else "unknown"
    log.info(f"[{ps.run_id}] Awaiting HITL | badge={badge}")
    return _dump(ps, state)


def node_error(state: dict) -> dict:
    ps = _ps(state)
    _set_status(ps, PipelineStatus.ERROR)
    log.error(f"[{ps.run_id}] NODE error | errors={ps.errors}")
    return _dump(ps, state)


# ── Edge routing ──────────────────────────────────────────────────────────────


def route_after_orchestrator(
    state: dict,
) -> Literal["node_pass1_drafting", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return "error_node"
    return "node_pass1_drafting"


def route_after_critic(
    state: dict,
) -> Literal["decision_router", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return "error_node"
    return "decision_router"


def route_after_decision(
    state: dict,
) -> Literal[
    "node_pass2_alignment",
    "await_hitl",
    "error_node",
]:
    ps = _ps(state)
    if ps.pipeline_status == "error":
        return "error_node"
    if ps.pipeline_status != "revising":
        return "await_hitl"

    critic = ps.critic_output
    if not critic or not critic.target_agents:
        return "node_pass2_alignment"

    state["_revision_targets"] = critic.target_agents
    return "node_pass2_alignment"


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("orchestrator_hub", node_orchestrator_hub)
    g.add_node("node_pass1_drafting", node_pass1_drafting)
    g.add_node("node_arbitrate", node_arbitrate)
    g.add_node("node_pass2_alignment", node_pass2_alignment)
    g.add_node("critic", node_critic)
    g.add_node("decision_router", node_decision_router)
    g.add_node("await_hitl", node_await_hitl)
    g.add_node("error_node", node_error)

    g.set_entry_point("orchestrator_hub")

    g.add_conditional_edges(
        "orchestrator_hub",
        route_after_orchestrator,
        {
            "node_pass1_drafting": "node_pass1_drafting",
            "error_node": "error_node",
        },
    )
    g.add_edge("node_pass1_drafting", "node_arbitrate")
    g.add_edge("node_arbitrate", "node_pass2_alignment")
    g.add_edge("node_pass2_alignment", "critic")

    g.add_conditional_edges(
        "critic",
        route_after_critic,
        {
            "decision_router": "decision_router",
            "error_node": "error_node",
        },
    )
    g.add_conditional_edges(
        "decision_router",
        route_after_decision,
        {
            "node_pass2_alignment": "node_pass2_alignment",
            "await_hitl": "await_hitl",
            "error_node": "error_node",
        },
    )

    g.add_edge("await_hitl", END)
    g.add_edge("error_node", END)
    return g


_graph = build_graph().compile()


# ── Public API ────────────────────────────────────────────────────────────────


def run_pipeline(
    brd_text: str,
    brd_hash: str,
    run_id: str,
    brd_name: str = "",
    model_family: str = "openai",
    enable_fallback: bool = True,
) -> PipelineState:
    """
    Run the full central Orchestrator hub-and-spoke pipeline synchronously.

    Args:
        brd_text: Validated, PII-redacted BRD text
        brd_hash: SHA256 of original BRD for audit trail
        run_id: First 8 chars of brd_hash

    Returns:
        Final PipelineState with pipeline_status="awaiting_hitl" or "error".
    """
    pipeline_start = time.perf_counter()
    log.info(
        f"[{run_id}] Pipeline starting | words={len(brd_text.split())} | family={model_family} | fallback={enable_fallback}"
    )
    reset_token_counter(run_id)
    set_current_run_id(run_id, model_family, enable_fallback)

    initial = PipelineState(
        run_id=run_id,
        brd_raw_hash=brd_hash,
        brd_name=brd_name,
        model_family=model_family,
        enable_fallback=enable_fallback,
    ).model_dump()
    initial["_brd_text"] = brd_text
    initial["_revision_targets"] = ALL_SPECIALIST_AGENTS.copy()

    final = _graph.invoke(initial)
    clean = {k: v for k, v in final.items() if not k.startswith("_")}
    result = PipelineState(**clean)

    final_family = _current_model_family()
    result.model_family = final_family
    if final_family != model_family:
        result.fallback_occurred = True
        result.fallback_from = model_family
        result.fallback_to = final_family

    total_ms = int((time.perf_counter() - pipeline_start) * 1000)
    result.processing_time_sec = total_ms / 1000.0
    _tin, _tout = get_token_counts(run_id)
    result.total_input_tokens = _tin
    result.total_output_tokens = _tout
    result.total_cost_usd = get_cost(run_id)
    agent_logs = [
        {"agent": agent_name, "success": getattr(result, field_name) is not None}
        for agent_name, field_name in AGENT_OUTPUT_FIELDS.items()
    ]
    agent_logs.append({"agent": "critic", "success": result.critic_output is not None})

    log_pipeline_summary(
        run_id=run_id,
        total_wall_clock_ms=total_ms,
        agent_logs=agent_logs,
        critic_score=result.critic_output.overall_score if result.critic_output else None,
        badge=result.critic_output.badge.value if result.critic_output else "unknown",
        hitl_decision=result.hitl_decision.value,
        pipeline_status=result.pipeline_status,
    )

    log.info(
        f"[{run_id}] Pipeline done | {total_ms}ms | "
        f"status={result.pipeline_status} | "
        f"badge={result.critic_output.badge.value if result.critic_output else 'none'}"
    )
    return result
