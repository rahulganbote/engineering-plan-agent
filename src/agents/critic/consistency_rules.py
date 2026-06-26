"""
src/agents/critic/consistency_rules.py
══════════════════════════════════════
Cross-agent consistency validation checks for EM Copilot.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.core.models import ConsistencyIssue, PipelineState, RiskLevel

log = get_logger(__name__)


def check_cross_agent_consistency(state: PipelineState) -> list[ConsistencyIssue]:
    """
    Check for contradictions between specialist agent outputs.
    This is only possible with a single Critic that sees all outputs.
    """
    issues: list[ConsistencyIssue] = []

    # Check 1: Complex architecture needs sufficient schedule
    if state.arch_output and state.schedule_output:
        component_count = len(state.arch_output.components)
        total_days = state.schedule_output.total_effort_days
        if component_count > 8 and total_days < 60:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["solution_architect", "schedule_estimator"],
                    conflict_description=(
                        f"Architecture has {component_count} components "
                        f"but schedule only estimates {total_days} effort days. "
                        "Schedule appears under-estimated for this architecture complexity."
                    ),
                    severity=RiskLevel.HIGH,
                )
            )

    # Check 2: Low team familiarity needs more buffer weeks
    if state.stack_output and state.schedule_output:
        for option in state.stack_output.options:
            if option.name == state.stack_output.recommended_option:
                if option.team_familiarity_rating <= 2 and state.schedule_output.buffer_weeks < 2:
                    issues.append(
                        ConsistencyIssue(
                            agents_involved=["tech_stack_recommender", "schedule_estimator"],
                            conflict_description=(
                                f"Recommended stack '{option.name}' has low team familiarity "
                                f"(rating {option.team_familiarity_rating}/5) but schedule "
                                f"only has {state.schedule_output.buffer_weeks} buffer weeks. "
                                "Add learning curve buffer."
                            ),
                            severity=RiskLevel.MEDIUM,
                        )
                    )

    # Check 3: PoC should fit within Phase 1
    if state.poc_output and state.plan_output and state.plan_output.phases:
        phase1 = state.plan_output.phases[0]
        if state.poc_output.duration_weeks > phase1.duration_weeks:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["poc_planner", "engineering_plan_generator"],
                    conflict_description=(
                        f"PoC duration ({state.poc_output.duration_weeks}w) exceeds "
                        f"Phase 1 duration ({phase1.duration_weeks}w). "
                        "Reduce PoC scope or extend Phase 1."
                    ),
                    severity=RiskLevel.MEDIUM,
                )
            )

    # Check 4: Architecture complexity vs team size (over-engineering signal)
    if state.arch_output and state.plan_output and state.plan_output.team_composition:
        component_count = len(state.arch_output.components)
        team_size = sum(state.plan_output.team_composition.values())
        if team_size > 0 and component_count > team_size * 3 and team_size < 8:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["solution_architect", "engineering_plan_generator"],
                    conflict_description=(
                        f"Architecture has {component_count} components but team is only "
                        f"{team_size} engineers ({component_count / team_size:.1f} per person). "
                        "Architecture likely over-engineered for team capacity — consolidate components "
                        "or expand team."
                    ),
                    severity=RiskLevel.HIGH,
                )
            )

    # Check 5: Critical/high risks vs schedule buffer (no risk margin)
    if state.plan_output and state.schedule_output:
        severe_risks = [
            r
            for r in (state.plan_output.risks or [])
            if r.impact in (RiskLevel.HIGH, RiskLevel.CRITICAL) or r.likelihood in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
        buffer = getattr(state.schedule_output, "buffer_weeks", 0) or 0
        if len(severe_risks) >= 2 and buffer < 2:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["engineering_plan_generator", "schedule_estimator"],
                    conflict_description=(
                        f"{len(severe_risks)} high or critical risks identified, but schedule "
                        f"only allocates {buffer} buffer weeks. Add risk-mitigation buffer or "
                        "downgrade risks if they're over-stated."
                    ),
                    severity=RiskLevel.HIGH,
                )
            )

    # Check 6: Plan duration vs schedule effort (math sanity)
    if (
        state.plan_output
        and state.schedule_output
        and state.plan_output.team_composition
        and state.plan_output.total_duration_weeks
    ):
        team_size = sum(state.plan_output.team_composition.values())
        implied_effort = state.plan_output.total_duration_weeks * team_size * 5
        actual_effort = state.schedule_output.total_effort_days or 0
        if implied_effort > 0 and actual_effort > 0:
            ratio = abs(actual_effort - implied_effort) / implied_effort
            if ratio > 0.5:
                direction = "exceeds" if actual_effort > implied_effort else "is under"
                issues.append(
                    ConsistencyIssue(
                        agents_involved=["engineering_plan_generator", "schedule_estimator"],
                        conflict_description=(
                            f"Schedule effort ({actual_effort} days) {direction} "
                            f"plan implied effort ({implied_effort} days for "
                            f"{state.plan_output.total_duration_weeks}w × {team_size} engineers). "
                            f"Discrepancy is {ratio * 100:.0f}% — agents disagree on workload."
                        ),
                        severity=RiskLevel.MEDIUM,
                    )
                )

    # Check 7: Architecture pattern vs component count (pattern fit)
    if state.arch_output and state.arch_output.pattern:
        pattern_lower = state.arch_output.pattern.lower()
        component_count = len(state.arch_output.components)
        is_microservices = "microservice" in pattern_lower
        is_monolith = "monolith" in pattern_lower or "monolithic" in pattern_lower
        if is_microservices and component_count < 4:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["solution_architect"],
                    conflict_description=(
                        f"Pattern '{state.arch_output.pattern}' chosen but only "
                        f"{component_count} components. Microservices add operational "
                        "complexity that isn't justified below ~4 services — consider "
                        "modular monolith."
                    ),
                    severity=RiskLevel.MEDIUM,
                )
            )
        elif is_monolith and component_count > 12:
            issues.append(
                ConsistencyIssue(
                    agents_involved=["solution_architect"],
                    conflict_description=(
                        f"Pattern '{state.arch_output.pattern}' chosen but "
                        f"{component_count} components. Monolith pattern struggles with "
                        "this many internal modules — consider modular decomposition."
                    ),
                    severity=RiskLevel.MEDIUM,
                )
            )

    if issues:
        log.warning(f"[{state.run_id}] Cross-agent consistency issues: {len(issues)}")
    return issues
