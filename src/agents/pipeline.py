"""
src/agents/pipeline.py
═══════════════════════
LangGraph StateGraph — central Orchestrator hub-and-spoke pipeline.

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

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Literal

from langgraph.graph import END, StateGraph

from src.agents.architect import SolutionArchitectAgent
from src.agents.critic import CriticAgent
from src.agents.orchestrator import OrchestratorAgent
from src.agents.plan_generator import PlanGeneratorAgent
from src.agents.poc_planner import PoCPlannerAgent
from src.agents.schedule import ScheduleEstimatorAgent
from src.agents.tech_stack import TechStackAgent
from src.core.config import settings
from src.core.logger import get_logger, log_pipeline_summary
from src.core.models import PipelineState

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


def _feedback_for(ps: PipelineState, agent_name: str) -> str:
    if not ps.critic_output or not ps.critic_output.agent_feedback:
        return ""
    return ps.critic_output.agent_feedback.get(agent_name, "")


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
    feedback = _feedback_for(ps, agent_name)
    if agent_name == "engineering_plan_generator":
        return PlanGeneratorAgent().run(ps, feedback=feedback)
    if agent_name == "schedule_estimator":
        # Initial schedule is estimated directly from BRD; on revision it may
        # see existing plan_output from the previous aggregate state.
        return ScheduleEstimatorAgent().run(
            ps,
            plan_output=ps.plan_output if ps.revision_count > 0 else None,
            feedback=feedback,
        )
    if agent_name == "solution_architect":
        return SolutionArchitectAgent().run(ps, feedback=feedback)
    if agent_name == "poc_planner":
        return PoCPlannerAgent().run(ps, feedback=feedback)
    if agent_name == "tech_stack_recommender":
        return TechStackAgent().run(ps, feedback=feedback)
    raise ValueError(f"Unknown specialist agent: {agent_name}")


# ── Node functions ────────────────────────────────────────────────────────────

def node_orchestrator_hub(state: dict) -> dict:
    """Parse BRD, build routing plan, and initialize hub-owned PipelineState."""
    ps = _ps(state)
    brd_text = state.get("_brd_text", "")
    log.info(f"[{ps.run_id}] NODE orchestrator_hub")

    if not brd_text:
        ps.errors.append("No BRD text provided")
        ps.pipeline_status = "error"
        return _dump(ps, state)

    output, sections = OrchestratorAgent().run(brd_text, ps.run_id)
    ps.brd_sections = sections
    ps.pipeline_status = "dispatching" if output.validation_passed else "error"
    state["_routing_plan"] = output.routing_plan
    state["_revision_targets"] = ALL_SPECIALIST_AGENTS.copy()

    if not output.validation_passed:
        ps.errors.extend(output.validation_errors)

    return _dump(ps, state)


def node_dispatch_specialists(state: dict) -> dict:
    """
    Orchestrator fan-out.
    Runs all specialists on first pass; during revisions runs only agents
    selected by Critic feedback and consistency findings.
    """
    ps = _ps(state)
    targets = state.get("_revision_targets") or ALL_SPECIALIST_AGENTS.copy()
    log.info(
        f"[{ps.run_id}] NODE dispatch_specialists | "
        f"rev={ps.revision_count} targets={targets}"
    )

    if ps.pipeline_status == "error":
        return _dump(ps, state)

    ps.pipeline_status = "dispatching"
    max_workers = min(len(targets), len(ALL_SPECIALIST_AGENTS)) or 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_agent, agent_name, ps): agent_name
            for agent_name in targets
        }
        for future in as_completed(futures):
            agent_name = futures[future]
            field_name = AGENT_OUTPUT_FIELDS[agent_name]
            try:
                output = future.result()
                setattr(ps, field_name, output)
                log.info(f"[{ps.run_id}] Orchestrator received {agent_name}")
            except Exception as e:
                log.error(f"[{ps.run_id}] {agent_name} error: {e}")
                ps.errors.append(f"{agent_name}: {str(e)[:140]}")

    state["_last_dispatch_targets"] = targets
    return _dump(ps, state)


def node_aggregate_outputs(state: dict) -> dict:
    """
    Orchestrator fan-in.
    Validates all required specialist outputs are present before Critic review.
    Pydantic contract validation has already happened when each agent returned.
    """
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE aggregate_outputs | rev={ps.revision_count}")

    if ps.errors:
        ps.pipeline_status = "error"
        return _dump(ps, state)

    missing = [
        agent_name
        for agent_name, field_name in AGENT_OUTPUT_FIELDS.items()
        if getattr(ps, field_name) is None
    ]
    if missing:
        ps.pipeline_status = "error"
        ps.errors.append(f"Missing specialist outputs before Critic: {missing}")
        return _dump(ps, state)

    ps.pipeline_status = "critic_review"
    log.info(
        f"[{ps.run_id}] Aggregated outputs | "
        f"plan={ps.plan_output is not None} schedule={ps.schedule_output is not None} "
        f"arch={ps.arch_output is not None} poc={ps.poc_output is not None} "
        f"stack={ps.stack_output is not None}"
    )
    return _dump(ps, state)


def node_critic(state: dict) -> dict:
    """Send complete artifact bundle to the single shared Critic."""
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE critic | rev={ps.revision_count}")

    try:
        ps.critic_output = CriticAgent().run(ps)
        ps.critic_scores_history.append({
            "revision": ps.revision_count,
            "groundedness": ps.critic_output.groundedness.score,
            "completeness": ps.critic_output.completeness.score,
            "consistency": ps.critic_output.consistency.score,
            "actionability": ps.critic_output.actionability.score,
            "overall": ps.critic_output.overall_score,
            "badge": ps.critic_output.badge.value,
        })
        log.info(
            f"[{ps.run_id}] Critic score | overall={ps.critic_output.overall_score:.2f} "
            f"badge={ps.critic_output.badge.value} "
            f"requires_revision={ps.critic_output.requires_revision}"
        )
    except Exception as e:
        log.error(f"[{ps.run_id}] critic error: {e}")
        ps.errors.append(f"critic: {str(e)[:140]}")
        ps.pipeline_status = "error"

    return _dump(ps, state)


def node_decision_router(state: dict) -> dict:
    """
    Orchestrator Decision Router.
    Green goes to HITL. Amber/Red revises targeted agents until max cycles.
    """
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE decision_router | rev={ps.revision_count}")

    if ps.errors:
        ps.pipeline_status = "error"
        return _dump(ps, state)

    if not ps.critic_output:
        ps.errors.append("Critic output missing")
        ps.pipeline_status = "error"
        return _dump(ps, state)

    should_revise = (
        ps.critic_output.requires_revision
        and ps.revision_count < MAX_REVISIONS
    )

    if should_revise:
        targets = _revision_targets(ps)
        if not targets:
            targets = ALL_SPECIALIST_AGENTS.copy()
            log.warning(
                f"[{ps.run_id}] Critic requested revision but gave no targets; "
                "rerunning all specialists"
            )
        ps.revision_count += 1
        ps.pipeline_status = "revising"
        state["_revision_targets"] = targets
        log.info(
            f"[{ps.run_id}] Revision cycle {ps.revision_count}/{MAX_REVISIONS} | "
            f"targets={targets}"
        )
    else:
        ps.pipeline_status = "awaiting_hitl"
        state["_revision_targets"] = []
        reason = "max_revisions" if ps.revision_count >= MAX_REVISIONS else "quality_gate"
        log.info(
            f"[{ps.run_id}] Routing to HITL | badge={ps.critic_output.badge.value} "
            f"reason={reason}"
        )

    return _dump(ps, state)


def node_await_hitl(state: dict) -> dict:
    """Pause point for FastAPI/Streamlit HITL approval."""
    ps = _ps(state)
    ps.pipeline_status = "awaiting_hitl"
    badge = ps.critic_output.badge.value if ps.critic_output else "unknown"
    log.info(f"[{ps.run_id}] Awaiting HITL | badge={badge}")
    return _dump(ps, state)


def node_error(state: dict) -> dict:
    ps = _ps(state)
    ps.pipeline_status = "error"
    log.error(f"[{ps.run_id}] NODE error | errors={ps.errors}")
    return _dump(ps, state)


# ── Edge routing ──────────────────────────────────────────────────────────────

def route_after_orchestrator(
    state: dict,
) -> Literal["dispatch_specialists", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error" or ps.errors:
        return "error_node"
    return "dispatch_specialists"


def route_after_aggregate(
    state: dict,
) -> Literal["critic", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error" or ps.errors:
        return "error_node"
    return "critic"


def route_after_critic(
    state: dict,
) -> Literal["decision_router", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error" or ps.errors:
        return "error_node"
    return "decision_router"


def route_after_decision(
    state: dict,
) -> Literal["dispatch_specialists", "await_hitl", "error_node"]:
    ps = _ps(state)
    if ps.pipeline_status == "error" or ps.errors:
        return "error_node"
    if ps.pipeline_status == "revising":
        return "dispatch_specialists"
    return "await_hitl"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    g = StateGraph(dict)

    g.add_node("orchestrator_hub", node_orchestrator_hub)
    g.add_node("dispatch_specialists", node_dispatch_specialists)
    g.add_node("aggregate_outputs", node_aggregate_outputs)
    g.add_node("critic", node_critic)
    g.add_node("decision_router", node_decision_router)
    g.add_node("await_hitl", node_await_hitl)
    g.add_node("error_node", node_error)

    g.set_entry_point("orchestrator_hub")

    g.add_conditional_edges(
        "orchestrator_hub",
        route_after_orchestrator,
        {
            "dispatch_specialists": "dispatch_specialists",
            "error_node": "error_node",
        },
    )
    g.add_edge("dispatch_specialists", "aggregate_outputs")
    g.add_conditional_edges(
        "aggregate_outputs",
        route_after_aggregate,
        {
            "critic": "critic",
            "error_node": "error_node",
        },
    )
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
            "dispatch_specialists": "dispatch_specialists",
            "await_hitl": "await_hitl",
            "error_node": "error_node",
        },
    )

    g.add_edge("await_hitl", END)
    g.add_edge("error_node", END)
    return g


_graph = build_graph().compile()


# ── Public API ────────────────────────────────────────────────────────────────

def run_pipeline(brd_text: str, brd_hash: str, run_id: str, brd_name: str = "") -> PipelineState:
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
    log.info(f"[{run_id}] Pipeline starting | words={len(brd_text.split())}")

    initial = PipelineState(run_id=run_id, brd_raw_hash=brd_hash, brd_name=brd_name).model_dump()
    initial["_brd_text"] = brd_text
    initial["_revision_targets"] = ALL_SPECIALIST_AGENTS.copy()

    final = _graph.invoke(initial)
    clean = {k: v for k, v in final.items() if not k.startswith("_")}
    result = PipelineState(**clean)

    total_ms = int((time.perf_counter() - pipeline_start) * 1000)
    result.processing_time_sec = total_ms / 1000.0
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
