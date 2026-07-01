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
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def _safe_emit(event_type: str, **fields) -> None:
    """Best-effort event emit. Never raises - observability cannot break the pipeline."""
    try:
        from src.core.events import emit

        emit(event_type, **fields)
    except Exception:
        pass


def _set_status(ps: PipelineState, status: str) -> None:
    """Set pipeline_status and emit a status event to the client."""
    ps.pipeline_status = status
    _safe_emit("pipeline_status", status=status)


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
    _set_status(ps, "running")

    if not brd_text:
        ps.errors.append("No BRD text provided")
        _set_status(ps, "error")
        return _dump(ps, state)

    output, sections = OrchestratorAgent().run(brd_text, ps.run_id)
    ps.brd_sections = sections
    _set_status(ps, "dispatching" if output.validation_passed else "error")
    state["_routing_plan"] = output.routing_plan
    state["_revision_targets"] = ALL_SPECIALIST_AGENTS.copy()

    _safe_emit("agent_complete", agent="orchestrator")

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
    log.info(f"[{ps.run_id}] NODE dispatch_specialists | rev={ps.revision_count} targets={targets}")

    if ps.pipeline_status == "error":
        return _dump(ps, state)

    _set_status(ps, "dispatching")
    max_workers = min(len(targets), len(ALL_SPECIALIST_AGENTS)) or 1

    # ── Phase 9 - Bulkhead: per-agent timeout at the executor ───────────────
    # One stuck specialist cannot block the whole pipeline. Any future that
    # doesn't return within settings.agent_timeout_sec is cancelled; its agent
    # output stays None, which the Critic's FM-3 cap catches downstream.
    from concurrent.futures import TimeoutError as _BulkheadTimeout

    # Per-family bulkhead budget. Anthropic's Claude is genuinely slower than
    # GPT-4o for the same verbose JSON outputs (~3-5× in observed runs), so we
    # give it a bigger budget when the run is configured for anthropic. OpenAI
    # keeps the tighter 90s budget because retries that exceed that almost
    # always indicate genuine quota/network problems, not slow generation.
    _family = (getattr(ps, "model_family", "openai") or "openai").lower()
    _default_budget = float(getattr(settings, "agent_timeout_sec", 120))
    if _family == "anthropic":
        _bulkhead_budget = max(_default_budget, float(getattr(settings, "anthropic_agent_timeout_sec", 240)))
    else:
        _bulkhead_budget = _default_budget

    # Explicit executor lifecycle (NOT `with`) so we can return immediately on
    # bulkhead trip. A `with` block would call shutdown(wait=True) on __exit__,
    # which joins all running threads - defeating the point of the bulkhead.
    executor = ThreadPoolExecutor(max_workers=max_workers)
    bulkhead_tripped = False
    try:
        futures = {executor.submit(_run_agent, agent_name, ps): agent_name for agent_name in targets}
        try:
            for future in as_completed(futures, timeout=_bulkhead_budget):
                agent_name = futures[future]
                field_name = AGENT_OUTPUT_FIELDS[agent_name]
                try:
                    output = future.result(timeout=0)
                    setattr(ps, field_name, output)
                    log.info(f"[{ps.run_id}] Orchestrator received {agent_name}")
                except Exception as e:
                    log.error(f"[{ps.run_id}] {agent_name} error: {e}")
                    # Surface the real cause to ps.errors so the UI / aggregate
                    # phase sees it instead of just "Missing specialist outputs".
                    err_msg = str(e).strip() or type(e).__name__
                    ps.errors.append(f"{agent_name}: {err_msg[:280]}")
        except _BulkheadTimeout:
            # Bulkhead trip: at least one specialist exceeded the budget.
            # Cancel everything still pending and proceed with what we have.
            bulkhead_tripped = True
            for fut, agent_name in futures.items():
                if not fut.done():
                    fut.cancel()
                    log.warning(
                        f"[{ps.run_id}] {agent_name} bulkhead timeout after {_bulkhead_budget}s - proceeding without it"
                    )
                    ps.errors.append(f"{agent_name}: bulkhead timeout ({_bulkhead_budget}s)")
                    try:
                        from src.core.events import emit as _evt

                        _evt("bulkhead_timeout", agent=agent_name, timeout_sec=_bulkhead_budget)
                    except Exception:
                        pass
    finally:
        # On bulkhead trip → return immediately; orphan threads finish in the
        # background but do NOT block this function's return.
        # On normal completion → wait for any stragglers (there shouldn't be any).
        # Trade-off: orphan thread keeps consuming any in-flight OpenAI/Pinecone
        # request until it completes. Acceptable because (a) the SDK timeout still
        # caps it via @resilient, (b) its result is discarded, (c) wall-clock
        # containment is the bulkhead's primary contract.
        executor.shutdown(wait=not bulkhead_tripped, cancel_futures=True)

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
        _set_status(ps, "error")
        return _dump(ps, state)

    missing = [agent_name for agent_name, field_name in AGENT_OUTPUT_FIELDS.items() if getattr(ps, field_name) is None]
    if missing:
        _set_status(ps, "error")
        ps.errors.append(f"Missing specialist outputs before Critic: {missing}")
        return _dump(ps, state)

    _set_status(ps, "critic_review")
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
        _set_status(ps, "error")

    return _dump(ps, state)


def node_decision_router(state: dict) -> dict:
    """
    Orchestrator Decision Router.
    Green goes to HITL. Amber/Red revises targeted agents until max cycles.
    """
    ps = _ps(state)
    log.info(f"[{ps.run_id}] NODE decision_router | rev={ps.revision_count}")

    if ps.errors:
        _set_status(ps, "error")
        return _dump(ps, state)

    if not ps.critic_output:
        ps.errors.append("Critic output missing")
        _set_status(ps, "error")
        return _dump(ps, state)

    should_revise = ps.critic_output.requires_revision and ps.revision_count < MAX_REVISIONS

    if should_revise:
        targets = _revision_targets(ps)
        if not targets:
            targets = ALL_SPECIALIST_AGENTS.copy()
            log.warning(f"[{ps.run_id}] Critic requested revision but gave no targets; rerunning all specialists")
        ps.revision_count += 1
        _set_status(ps, "revising")
        state["_revision_targets"] = targets
        log.info(f"[{ps.run_id}] Revision cycle {ps.revision_count}/{MAX_REVISIONS} | targets={targets}")
    else:
        _set_status(ps, "awaiting_hitl")
        state["_revision_targets"] = []
        reason = "max_revisions" if ps.revision_count >= MAX_REVISIONS else "quality_gate"
        log.info(f"[{ps.run_id}] Routing to HITL | badge={ps.critic_output.badge.value} reason={reason}")

    return _dump(ps, state)


def node_await_hitl(state: dict) -> dict:
    """Pause point for FastAPI/React HITL approval."""
    ps = _ps(state)
    _set_status(ps, "awaiting_hitl")
    badge = ps.critic_output.badge.value if ps.critic_output else "unknown"
    log.info(f"[{ps.run_id}] Awaiting HITL | badge={badge}")
    return _dump(ps, state)


def node_error(state: dict) -> dict:
    ps = _ps(state)
    _set_status(ps, "error")
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
