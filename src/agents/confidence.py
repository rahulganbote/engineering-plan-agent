"""
src/agents/confidence.py
════════════════════════
Verifiable confidence scoring for specialist outputs.

Derives `confidence_score` from Pydantic-validated fields rather than accepting
the LLM's self-reported number. Every deduction traces to a specific missing
field or documented uncertainty in the artifact. Rubric maps to a 4-category
risk framework:

    1. Architectural & Tooling      — unproven stack, integration risk
    2. DevOps & Infrastructure       — missing NFRs, unmeasurable success criteria
    3. Requirements & Scope          — flagged ambiguities, undocumented assumptions
    4. Team & Operational            — thin team, no historical calibration baseline

Score interpretation aligned with industry brackets used in greenfield roadmap
planning:

    0.85 - 1.00   Familiar stack, known infra, standard CRUD flow
    0.60 - 0.84   Clear requirements but one novel technology / complex integration
    < 0.60        Multiple architectural unknowns, no calibration baseline,
                  novel algorithm or distributed system

Each `compute_X_confidence` returns a `(score, drivers)` tuple. `drivers` is a
list of human-readable strings explaining what moved the score - shown to the
reviewing EM alongside the percentage so the number is auditable, not vibes.

Called by each specialist AFTER the Pydantic output object is constructed, so
the derivation can inspect all populated fields at once. The LLM's raw
`confidence_score` (still asked for in the prompt, still parsed) is discarded
and replaced with this derived value.
"""

from __future__ import annotations

from src.core.models import (
    ArchitectureOutput,
    EngineeringPlanOutput,
    PoCOutput,
    RiskLevel,
    ScheduleOutput,
    TechStackOutput,
)

# ── Shared coefficients ──────────────────────────────────────────────────────
# Documented here so tuning happens in one place rather than scattered across
# five functions. Calibrated so a clean CRUD run lands ~0.90 and a run with
# multiple structural unknowns lands below 0.60.

# Contingency buffer: every project starts at 0.90 instead of 1.00 because
# perfect confidence is a lie - there are always unknowns that even a fully
# populated artifact can't capture (team dynamics, third-party outages,
# integration surprises). Mirrors the industry practice of reserving ~10%
# schedule/budget for contingency. Reported as a driver ("contingency buffer
# -10%") so the reader sees why 100% is never possible.
_CONFIDENCE_CEILING = 0.90
_CONTINGENCY_DRIVER = f"contingency buffer (-{int(round((1.0 - _CONFIDENCE_CEILING) * 100))}%)"

_AMBIGUITY_COST = 0.04  # per flagged_ambiguity, cap 0.15
_AMBIGUITY_CAP = 0.15
_ASSUMPTION_COST = 0.02  # per assumption beyond the first 3 (some are healthy), cap 0.08
_ASSUMPTION_CAP = 0.08
_ASSUMPTION_TOLERANCE = 3

# Sprint capacity calibration. Standard PM practice reserves ~20% of team
# workdays for meetings, code review, unplanned work, and interruptions -
# so a sprint should be planned against 80% of nominal capacity, not 100%.
# Effort-days scheduled beyond this bar indicates over-allocation that will
# slip in reality regardless of how good the artifact structure looks.
_SPRINT_TARGET_UTILIZATION = 0.80  # 80% of nominal capacity is the planning bar
_WORKDAYS_PER_WEEK = 5


def _pct(deduction: float) -> str:
    """Format a deduction (fraction) as a signed percentage string for drivers."""
    return f"-{int(round(deduction * 100))}%"


def _apply_shared_ambiguity_signals(
    ambiguities: list[str] | None,
    assumptions: list[str] | None,
    drivers: list[str],
) -> float:
    """Category 3 signals common to every specialist. Returns total deduction."""
    total = 0.0
    n_amb = len(ambiguities or [])
    if n_amb:
        penalty = min(_AMBIGUITY_CAP, _AMBIGUITY_COST * n_amb)
        total += penalty
        noun = "ambiguity" if n_amb == 1 else "ambiguities"
        drivers.append(f"{n_amb} flagged {noun} ({_pct(penalty)})")

    n_asm = len(assumptions or [])
    if n_asm > _ASSUMPTION_TOLERANCE:
        excess = n_asm - _ASSUMPTION_TOLERANCE
        penalty = min(_ASSUMPTION_CAP, _ASSUMPTION_COST * excess)
        total += penalty
        drivers.append(f"{n_asm} documented assumptions ({_pct(penalty)})")

    return total


def _finalize(score: float) -> float:
    """Clamp to [0.0, 1.0] and round to 2 decimals for stable display."""
    return round(max(0.0, min(1.0, score)), 2)


def _parse_sprint_weeks(week_range: str | None) -> int:
    """
    Parse a sprint week range like 'W1-W2' or 'W3-W5' into a week count.
    Falls back to 2 (standard sprint length) if the format is unrecognized.
    Never raises - schedule confidence should degrade gracefully if the
    LLM emits an unusual format.
    """
    if not week_range:
        return 2
    try:
        cleaned = week_range.upper().replace("W", "").replace(" ", "")
        parts = cleaned.split("-")
        if len(parts) == 2:
            start, end = int(parts[0]), int(parts[1])
            return max(1, end - start + 1)
        if len(parts) == 1:
            return 1
    except (ValueError, AttributeError):
        pass
    return 2


# ── Per-specialist scorers ───────────────────────────────────────────────────


def compute_plan_confidence(plan: EngineeringPlanOutput) -> tuple[float, list[str]]:
    """
    Engineering plan confidence.

    Signals:
      Cat 1 - Grounding      : per-risk citation presence
      Cat 3 - Ambiguity      : flagged_ambiguities, excess assumptions (shared)
      Cat 4 - Team & Ops     : team_composition breadth
    """
    score = _CONFIDENCE_CEILING
    drivers: list[str] = [_CONTINGENCY_DRIVER]

    score -= _apply_shared_ambiguity_signals(plan.flagged_ambiguities, plan.assumptions, drivers)

    if not plan.team_composition or len(plan.team_composition) < 2:
        score -= 0.05
        drivers.append(f"thin team composition ({_pct(0.05)})")

    uncited_risks = sum(1 for r in (plan.risks or []) if not r.citation)
    if uncited_risks:
        penalty = min(0.10, 0.03 * uncited_risks)
        score -= penalty
        noun = "risk" if uncited_risks == 1 else "risks"
        drivers.append(f"{uncited_risks} {noun} lack citations ({_pct(penalty)})")

    return _finalize(score), drivers


def compute_schedule_confidence(sched: ScheduleOutput) -> tuple[float, list[str]]:
    """
    Schedule confidence.

    Signals:
      Cat 3 - Ambiguity      : flagged_ambiguities, excess assumptions (shared)
      Cat 4 - Team & Ops     : comparable_projects (calibration anchor),
                               buffer_weeks (uncertainty acknowledgment),
                               critical_path (planning clarity),
                               effort density vs 80% capacity rule
    """
    score = _CONFIDENCE_CEILING
    drivers: list[str] = [_CONTINGENCY_DRIVER]

    score -= _apply_shared_ambiguity_signals(sched.flagged_ambiguities, sched.assumptions, drivers)

    if not sched.comparable_projects:
        score -= 0.10
        drivers.append(f"no comparable projects for calibration ({_pct(0.10)})")
    if (sched.buffer_weeks or 0) < 1:
        score -= 0.05
        drivers.append(f"zero buffer weeks ({_pct(0.05)})")
    if not sched.critical_path:
        score -= 0.08
        drivers.append(f"no critical path identified ({_pct(0.08)})")

    # Effort density check: standard PM planning uses 80% of nominal team
    # capacity as the target (20% reserved for meetings, code review,
    # unplanned work). Compute planned capacity across all sprints at the
    # 80% bar and compare against total_effort_days. Over-allocation is a
    # strong "this schedule will slip" signal that pure field-presence
    # checks cannot detect.
    total_capacity_at_target = 0.0
    for sprint in sched.sprints or []:
        weeks = _parse_sprint_weeks(sprint.week_range)
        team_size = len(sprint.team_members or [])
        total_capacity_at_target += team_size * weeks * _WORKDAYS_PER_WEEK * _SPRINT_TARGET_UTILIZATION

    total_effort = sched.total_effort_days or 0
    if total_capacity_at_target > 0 and total_effort > 0:
        utilization = total_effort / total_capacity_at_target
        utilization_pct = int(round(utilization * 100))
        if utilization > 1.0:
            # Over-allocated: scheduled work exceeds the 80%-capacity bar.
            # Deduction scales with overshoot, capped at 15% so a modestly
            # tight schedule doesn't nuke confidence.
            overshoot = utilization - 1.0
            penalty = min(0.15, overshoot * 0.3)
            score -= penalty
            drivers.append(f"sprint over-allocated at {utilization_pct}% of 80%-capacity target ({_pct(penalty)})")
        elif utilization > 0.9:
            # Tight but not over: still risky, small deduction.
            score -= 0.05
            drivers.append(f"tight sprint allocation at {utilization_pct}% of 80%-capacity target ({_pct(0.05)})")

    return _finalize(score), drivers


def compute_arch_confidence(arch: ArchitectureOutput) -> tuple[float, list[str]]:
    """
    Architecture confidence.

    Signals:
      Cat 1 - Architectural  : components, data_flow, deployment_model, pattern justification
      Cat 2 - Infrastructure : NFR mappings (are non-functional reqs explicit?)
      Cat 3 - Ambiguity      : flagged_ambiguities, excess assumptions (shared)
    """
    score = _CONFIDENCE_CEILING
    drivers: list[str] = [_CONTINGENCY_DRIVER]

    score -= _apply_shared_ambiguity_signals(arch.flagged_ambiguities, arch.assumptions, drivers)

    if not arch.nfr_mappings:
        score -= 0.10
        drivers.append(f"no NFR mappings ({_pct(0.10)})")
    if not arch.components:
        score -= 0.05
        drivers.append(f"no components documented ({_pct(0.05)})")
    if not arch.data_flow:
        score -= 0.05
        drivers.append(f"no data flow specified ({_pct(0.05)})")
    if not arch.deployment_model:
        score -= 0.03
        drivers.append(f"no deployment model ({_pct(0.03)})")
    if not (arch.pattern_justification or "").strip():
        score -= 0.03
        drivers.append(f"no pattern justification ({_pct(0.03)})")

    return _finalize(score), drivers


def compute_poc_confidence(poc: PoCOutput) -> tuple[float, list[str]]:
    """
    PoC confidence.

    Signals:
      Cat 2 - Infrastructure : per-criterion measurement_method presence
      Cat 3 - Ambiguity      : flagged_ambiguities, excess assumptions (shared),
                               scope_out (scope boundary clarity)
      Cat 4 - Team & Ops     : duration_weeks and team_size defined
    """
    score = _CONFIDENCE_CEILING
    drivers: list[str] = [_CONTINGENCY_DRIVER]

    score -= _apply_shared_ambiguity_signals(poc.flagged_ambiguities, poc.assumptions, drivers)

    if not poc.scope_out:
        score -= 0.10
        drivers.append(f"no explicit scope-out ({_pct(0.10)})")

    if not poc.success_criteria:
        score -= 0.10
        drivers.append(f"no success criteria ({_pct(0.10)})")
    else:
        missing = sum(1 for c in poc.success_criteria if not (c.measurement_method or "").strip())
        if missing:
            penalty = min(0.10, 0.03 * missing)
            score -= penalty
            noun = "criterion" if missing == 1 else "criteria"
            drivers.append(f"{missing} {noun} lack measurement method ({_pct(penalty)})")

    if (poc.duration_weeks or 0) <= 0:
        score -= 0.05
        drivers.append(f"PoC duration not defined ({_pct(0.05)})")
    if (poc.team_size or 0) <= 0:
        score -= 0.05
        drivers.append(f"PoC team size not defined ({_pct(0.05)})")

    return _finalize(score), drivers


def compute_stack_confidence(stack: TechStackOutput) -> tuple[float, list[str]]:
    """
    Tech stack confidence.

    Signals:
      Cat 1 - Architectural  : recommended option's team_familiarity_rating (1-5),
                               integration_risk (LOW / MEDIUM / HIGH / CRITICAL),
                               number of options evaluated (2 = thin, 3 = healthy)
      Cat 3 - Ambiguity      : flagged_ambiguities, excess assumptions (shared)
    """
    score = _CONFIDENCE_CEILING
    drivers: list[str] = [_CONTINGENCY_DRIVER]

    score -= _apply_shared_ambiguity_signals(stack.flagged_ambiguities, stack.assumptions, drivers)

    if not stack.options or len(stack.options) < 2:
        score -= 0.10
        drivers.append(f"fewer than 2 stack options evaluated ({_pct(0.10)})")

    rec = next(
        (o for o in (stack.options or []) if o.name == stack.recommended_option),
        None,
    )
    if rec is not None:
        familiarity = getattr(rec, "team_familiarity_rating", 5) or 5
        deficit = max(0, 5 - familiarity)
        if deficit:
            penalty = 0.04 * deficit
            score -= penalty
            drivers.append(f"team familiarity {familiarity}/5 ({_pct(penalty)})")

        risk = getattr(rec, "integration_risk", None)
        if risk in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            score -= 0.15
            drivers.append(f"high integration risk ({_pct(0.15)})")
        elif risk == RiskLevel.MEDIUM:
            score -= 0.08
            drivers.append(f"medium integration risk ({_pct(0.08)})")

    return _finalize(score), drivers
