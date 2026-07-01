"""
src/agents/critic/scope_creep.py
════════════════════════════════
Scope creep and requirements ambiguity validation checks for EM Copilot.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.core.models import HallucinationFlag, PipelineState

log = get_logger(__name__)


def detect_scope_creep(state: PipelineState) -> list[HallucinationFlag]:
    """
    Scope creep detection.
    Cross-checks specialist outputs against the BRD's anchor vocabulary.
    Anything with too many novel (non-BRD, non-stopword) terms is flagged
    as potential scope creep - work the EM did not ask for.
    """
    flags = []
    brd_text = " ".join(s.content for s in state.brd_sections).lower()
    brd_terms = set(brd_text.split())

    # Words that are too common to be evidence of scope creep
    stop = {
        "shall",
        "must",
        "will",
        "implement",
        "develop",
        "build",
        "create",
        "establish",
        "ensure",
        "provide",
        "support",
        "enable",
        "allow",
        "manage",
        "using",
        "based",
        "through",
        "across",
        "within",
        "including",
        "various",
        "system",
        "systems",
        "service",
        "services",
        "layer",
        "module",
        "modules",
    }

    def _novel(text: str) -> set[str]:
        """Tokenize text and return the set of novel >4-char words."""
        tokens = text.lower().replace("-", " ").replace("_", " ").replace("/", " ").split()
        return {w for w in tokens if len(w) > 4 and w not in brd_terms and w not in stop}

    def _flag(agent: str, location: str, snippet: str, novel: set[str]) -> None:
        flags.append(
            HallucinationFlag(
                agent=agent,
                claim=(
                    f"Possible scope creep in {location}: '{snippet[:80]}'. "
                    f"Novel terms not in BRD: {', '.join(sorted(novel))}"
                ),
                status="partially_supported",
                supporting_chunk_id=None,
            )
        )

    # ── 1. Plan phase objectives ────────────────────────────────────────
    if state.plan_output:
        for phase in state.plan_output.phases:
            for objective in phase.objectives:
                novel = _novel(objective)
                if len(novel) > 3:
                    _flag("engineering_plan_generator", "phase objective", objective, novel)

    # ── 2. Architecture component names ─────────────────────────────────
    if state.arch_output:
        for component in state.arch_output.components:
            name = getattr(component, "name", "") or ""
            if not name:
                continue
            novel = _novel(name)
            if len(novel) >= 1:
                _flag("solution_architect", "component name", name, novel)

    # ── 3. Tech stack recommended option ────────────────────────────────
    if state.stack_output and state.stack_output.recommended_option:
        recommended = next(
            (o for o in state.stack_output.options if o.name == state.stack_output.recommended_option),
            None,
        )
        if recommended is not None:
            stack_text = recommended.name
            for tech in (recommended.components or {}).values():
                stack_text += " " + str(tech)
            tokens = stack_text.lower().replace("-", " ").replace("_", " ").split()
            long_tokens = [w for w in tokens if len(w) > 4 and w not in stop]
            novel = [w for w in long_tokens if w not in brd_terms]
            if len(long_tokens) >= 3 and len(novel) / len(long_tokens) >= 0.8:
                _flag(
                    "tech_stack_recommender",
                    "recommended stack",
                    recommended.name,
                    set(novel),
                )

    # ── 4. PoC scope_in items ───────────────────────────────────────────
    if state.poc_output and getattr(state.poc_output, "scope_in", None):
        for item in state.poc_output.scope_in:
            if not isinstance(item, str):
                continue
            novel = _novel(item)
            if len(novel) > 3:
                _flag("poc_planner", "PoC scope_in", item, novel)

    if flags:
        log.warning(f"[{state.run_id}] Scope creep: {len(flags)} items flagged for EM review")
    return flags


def check_ambiguity_handling(state: PipelineState) -> list[str]:
    """
    Verify agents followed ambiguity protocol.
    Returns list of feedback strings for agents that did not populate
    flagged_ambiguities[] or assumptions[] when BRD was ambiguous or short.
    """
    feedback = []
    brd_has_nfrs = any(s.has_nfrs for s in state.brd_sections)
    brd_word_count = sum(s.word_count for s in state.brd_sections)
    brd_is_short = brd_word_count < 200

    for agent_name, output in [
        ("engineering_plan_generator", state.plan_output),
        ("schedule_estimator", state.schedule_output),
        ("solution_architect", state.arch_output),
        ("poc_planner", state.poc_output),
        ("tech_stack_recommender", state.stack_output),
    ]:
        if not output:
            continue
        ambiguities = getattr(output, "flagged_ambiguities", [])
        if brd_is_short and not ambiguities:
            feedback.append(
                f"AMBIGUITY [{agent_name}]: BRD is short ({brd_word_count} words) "
                f"but flagged_ambiguities[] is empty. Per standards: flag, do not guess."
            )
        if not brd_has_nfrs and not ambiguities:
            feedback.append(
                f"AMBIGUITY [{agent_name}]: BRD has no NFRs but flagged_ambiguities[] "
                f"is empty. Must flag: 'No NFRs - used system defaults'."
            )
    return feedback
