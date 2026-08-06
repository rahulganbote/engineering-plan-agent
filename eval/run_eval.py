"""
eval/run_eval.py
════════════════
Automated evaluation runner - all 5 methods for quality verification.

METHOD 1 - Rule-based (structural + schema + BRD coverage):
    Deterministic assertions against expected_output_*.json.
    Checks: badge, phase count, risk count, duration, citations,
            owner_role on ALL milestones, BRD section coverage %,
            Pydantic schema parse rate, risk citations required.

METHOD 2 - LLM-as-Judge (actionability, specificity, grounding, EM-readiness):
    GPT-4o-mini scores 4 dimensions with strengthened EM-readiness prompt.
    Anchored to critic_calibration_set.json.
    Includes: specificity check, sources diversity, EM-readiness criteria.

METHOD 3 - Execution-based (schema parse rates, E2E completion, tool-call success):
    Tracks: Pydantic validation pass rate per agent,
            Kroki SVG generation success/fail,
            GitHub API tool-call success/fail,
            Pipeline completion rate.

METHOD 4 - Reference-based (BERTScore vs golden outputs):
    BERTScore F1 on narrative fields (reflection_notes, pattern_justification,
    poc_hypothesis, recommendation_rationale) vs golden expected text.
    Requires: pip install bert-score

METHOD 5 - Human HITL ratings:
    EM numeric rating (1-5) captured at ApprovalRequest gate.
    Stored in PipelineState.hitl_em_ratings.
    Displayed in results alongside critic scores.

Usage:
    python eval/run_eval.py                          # all methods, all BRDs
    python eval/run_eval.py --brd eval/sample_brd_simple.txt
    python eval/run_eval.py --method rule            # fast, free
    python eval/run_eval.py --method llm             # uses OpenAI
    python eval/run_eval.py --method execution       # schema + tool checks
    python eval/run_eval.py --method reference       # BERTScore (slow)
    python eval/run_eval.py --guardrails             # security layer only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.core.config import settings
from src.core.logger import get_logger

log      = get_logger(__name__)
EVAL_DIR = Path(__file__).parent
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# BRD sections that completeness check verifies are addressed
BRD_REQUIRED_SECTIONS = ["objective", "requirement", "constraint", "risk", "nfr"]

# ── Test registry ──────────────────────────────────────────────────────────────

PIPELINE_TESTS = [
    {
        "test_id":       "EVAL-001",
        "name":          "Simple BRD - Employee Directory App",
        "brd_file":      EVAL_DIR / "sample_brd_simple.txt",
        "expected_file": EVAL_DIR / "expected_output_simple.json",
        "complexity":    "simple",
        "expect_badge":  "green",
    },
    {
        "test_id":       "EVAL-002",
        "name":          "Medium BRD - Customer Analytics Platform",
        "brd_file":      EVAL_DIR / "test_brd_medium.txt",
        "expected_file": EVAL_DIR / "expected_output_medium.json",
        "complexity":    "medium",
        "expect_badge":  "green",
        "acceptable_badge": "amber",
    },
    {
        "test_id":       "EVAL-003",
        "name":          "Complex BRD - Real-Time Risk Compliance Platform",
        "brd_file":      EVAL_DIR / "test_brd_complex.txt",
        "expected_file": EVAL_DIR / "expected_output_complex.json",
        "complexity":    "complex",
        "expect_badge":  "green",
        "acceptable_badge": "amber",
    },
]

EDGE_CASE_TESTS = [
    {
        "test_id":    "EDGE-001",
        "name":       "Missing NFRs - Knowledge Base Search Tool",
        "brd_file":   EVAL_DIR / "test_brd_missing_nfrs.txt",
        "complexity": "simple",
        "expect_badge": "amber",
        "expected_behaviors": {
            "flagged_ambiguities_contains": "Non-Functional Requirements",
            "confidence_score_max": 0.7,
        },
    },
    {
        "test_id":    "EDGE-002",
        "name":       "Contradictions - Inventory Management System",
        "brd_file":   EVAL_DIR / "test_brd_contradictions.txt",
        "complexity": "medium",
        "expect_badge": "amber",
        "expected_behaviors": {
            "flagged_ambiguities_min_count": 2,
            "consistency_max": 4.0,
        },
    },
    {
        "test_id":    "EDGE-003",
        "name":       "Ambiguity - Vague Customer Engagement BRD",
        "brd_file":   EVAL_DIR / "test_brd_ambiguous.txt",
        "complexity": "medium",
        "expect_badge": "amber",
        "expected_behaviors": {
            # Guardrail: org standard 8.1 - all agents must flag ambiguities
            "all_agents_flagged_ambiguities_non_empty": True,
            "flagged_ambiguities_min_count": 3,   # per agent
            "assumptions_min_count":          2,  # conservative choices documented
            "confidence_score_max":           0.65,
        },
    },
]

GUARDRAIL_TESTS = [
    {
        "test_id": "GUARD-001", "name": "Prompt Injection",
        "brd_file": EVAL_DIR / "test_brd_injection.txt",
        "expect_blocked": True, "expect_status": "BLOCKED",
        "expect_no_agents": True, "block_reason_contains": "injection",
    },
    {
        "test_id": "GUARD-002", "name": "PII Detection",
        "brd_file": EVAL_DIR / "test_brd_pii.txt",
        "expect_blocked": False, "expect_status": "WARNING",
        "expect_pii_types": ["EMAIL", "PHONE", "SSN"], "expect_redacted": True,
    },
    {
        "test_id": "GUARD-003", "name": "Broken BRD",
        "brd_file": EVAL_DIR / "test_brd_broken.txt",
        "expect_blocked": True, "expect_status": "BLOCKED",
        "block_reason_contains": "missing",
    },
    {
        "test_id":   "GUARD-004",
        "name":      "Scope Creep - Minimal BRD (agents must not invent features)",
        "brd_file":  EVAL_DIR / "test_brd_scope_creep.txt",
        "expect_blocked": False,
        "expect_status":  "PASSED",
        # Scope creep terms that must NOT appear in any agent output
        "forbidden_scope_terms": [
            "mobile app", "ios", "android", "jira", "slack", "payroll",
            "ai-powered", "machine learning", "real-time notification",
            "leave management", "data visualization", "dashboard",
            "role-based access control", "rbac",
        ],
        "max_phases":         3,  # simple 4-week project = max 3 phases
        "max_duration_weeks": 6,  # BRD says 4 weeks - allow 2-week buffer
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# Trust-boundary helper - strip dev-only markers before any validator sees them
# ══════════════════════════════════════════════════════════════════════════════
# Eval BRDs (e.g. test_brd_niche_tech.txt) may contain inline annotations like
# "EVAL NOTE: ..." used by the test harness for traceability. These are NOT
# user input - they are author-controlled dev metadata.
#
# Trust boundary policy: strip these markers HERE in the harness, before the
# text ever reaches the SecurityValidator. We must NOT teach the validator's
# LLM prompt to recognize them, because doing so creates a published bypass
# vector (anyone uploading a real BRD could prefix `EVAL NOTE:` to evade the
# injection scanner). The validator must treat all incoming text as untrusted.

_EVAL_MARKER_PREFIXES = ("EVAL NOTE:", "# EVAL NOTE:", "// EVAL NOTE:")


def strip_eval_metadata(text: str) -> str:
    """
    Remove any line starting with an EVAL NOTE marker from a BRD text.
    Called ONLY from the eval harness - never from production code paths.
    """
    return "\n".join(
        line for line in text.splitlines()
        if not any(line.lstrip().startswith(p) for p in _EVAL_MARKER_PREFIXES)
    )


# ══════════════════════════════════════════════════════════════════════════════
# METHOD 1 - Rule-based
# ══════════════════════════════════════════════════════════════════════════════

def run_rule_based_checks(agent_output: dict, expected: dict, test_config: dict) -> dict:
    """
    Method 1: Deterministic structural checks.
    Covers: structural checks, schema compliance, BRD section coverage.
    No LLM calls - fast, free, fully repeatable.
    """
    checks = []
    plan   = agent_output.get("plan_output", {}) or {}
    sched  = agent_output.get("schedule_output", {}) or {}
    arch   = agent_output.get("arch_output", {}) or {}
    poc    = agent_output.get("poc_output", {}) or {}
    stack  = agent_output.get("stack_output", {}) or {}
    critic = agent_output.get("critic", {}) or {}
    brd    = test_config.get("brd_text", "")

    exp_eval = expected.get("evaluation_targets", {})
    exp_plan = expected.get("engineering_plan", {})

    # ── Structural checks ──────────────────────────────────────────────────
    # Phase count
    phase_count = len(plan.get("phases", []))
    exp_phases  = exp_eval.get("expected_phases_min", exp_plan.get("min_phases", 2))
    _add(checks, "Phase count", phase_count >= exp_phases, phase_count, f">= {exp_phases}")

    # Risk count
    risk_count = len(plan.get("risks", []))
    exp_risks  = exp_eval.get("expected_risks_min", exp_plan.get("required_risks_min", 1))
    _add(checks, "Risk count", risk_count >= exp_risks, risk_count, f">= {exp_risks}")

    # Total duration
    exp_weeks = exp_plan.get("total_duration_weeks", exp_plan.get("total_duration_weeks_min", 0))
    if exp_weeks:
        actual_weeks = plan.get("total_duration_weeks", 0)
        _add(checks, "Duration weeks", actual_weeks >= exp_weeks, actual_weeks, f">= {exp_weeks}")

    # Tech stack options
    option_count = len(stack.get("options", []))
    exp_options  = exp_eval.get("expected_stack_options_min", 2)
    _add(checks, "Tech stack options", option_count >= exp_options, option_count, f">= {exp_options}")

    # Badge
    actual_badge   = critic.get("badge", "unknown")
    expected_badge = test_config.get("expect_badge", "green")
    acceptable     = test_config.get("acceptable_badge", expected_badge)
    _add(checks, "Quality badge", actual_badge in [expected_badge, acceptable], actual_badge, f"{expected_badge}/{acceptable}")

    # ── Schema compliance: citations on every agent ────────────────────────
    exp_cites = exp_eval.get("expected_citations_per_output_min", 1)
    for agent_key, output in [
        ("plan", plan), ("schedule", sched), ("architect", arch),
        ("poc", poc), ("tech_stack", stack)
    ]:
        if output:
            real_cites = [c for c in output.get("citations", []) if "no_results" not in c]
            _add(checks, f"Citations - {agent_key}", len(real_cites) >= exp_cites,
                 len(real_cites), f">= {exp_cites} real citations")

    # ── Schema compliance: reflection_notes (Agent 2) ─────────────────────
    reflection = plan.get("reflection_notes", "")
    _add(checks, "reflection_notes present", bool(reflection and len(reflection) > 20),
         f"'{reflection[:40]}...'" if reflection else "EMPTY", "non-empty string")

    # ── Schema compliance: owner_role on ALL milestones ───────────────────
    # Actionability rule: EM can act immediately = every milestone has owner
    all_milestones, missing_owner = 0, 0
    for phase in plan.get("phases", []):
        for ms in phase.get("milestones", []):
            all_milestones += 1
            if not ms.get("owner_role", "").strip():
                missing_owner += 1
    if all_milestones > 0:
        _add(checks, "owner_role on all milestones",
             missing_owner == 0,
             f"{all_milestones - missing_owner}/{all_milestones} have owner",
             "100% of milestones")

    # ── Schema compliance: citation on every Risk ──────────────────────────
    risks_with_citation = sum(1 for r in plan.get("risks", []) if r.get("citation", "").strip())
    total_risks = len(plan.get("risks", []))
    if total_risks > 0:
        _add(checks, "citation on every Risk",
             risks_with_citation == total_risks,
             f"{risks_with_citation}/{total_risks} risks cited",
             "100% of risks")

    # ── Schema compliance: go_nogo_criteria in PoC ────────────────────────
    go_nogo = poc.get("go_nogo_criteria", {})
    _add(checks, "go_nogo_criteria present",
         bool(go_nogo and go_nogo.get("go") and go_nogo.get("no_go")),
         "present" if go_nogo else "MISSING", "go + no_go + pivot")

    # ── Schema compliance: risk_if_poc_fails in PoC ───────────────────────
    rif = poc.get("risk_if_poc_fails", "")
    _add(checks, "risk_if_poc_fails present",
         bool(rif and len(rif) > 20), f"'{rif[:40]}...'" if rif else "EMPTY", "non-empty string")

    # ── Schema compliance: recommendation_rationale in Tech Stack ─────────
    rationale = stack.get("recommendation_rationale", "")
    _add(checks, "recommendation_rationale present",
         bool(rationale and len(rationale) > 30),
         f"'{rationale[:40]}...'" if rationale else "EMPTY", "non-empty string")

    # ── Schema compliance: github_velocity_note ───────────────────────────
    gvn = stack.get("github_velocity_note", "")
    _add(checks, "github_velocity_note present",
         bool(gvn and len(gvn) > 10), "present" if gvn else "MISSING", "non-empty string")

    # ── Schema compliance: nfr_mappings in Architecture ───────────────────
    nfr_maps = arch.get("nfr_mappings", [])
    _add(checks, "nfr_mappings min 1",
         len(nfr_maps) >= 1, len(nfr_maps), ">= 1 mapping")

    # ── BRD section coverage % ────────────────────────────────────────────
    # Method 1 required: structural check that all BRD sections were addressed
    brd_lower      = brd.lower()
    section_checks = {
        "objectives_in_brd":   any(w in brd_lower for w in ["objective", "goal"]),
        "frs_in_brd":          any(w in brd_lower for w in ["fr-", "functional req"]),
        "nfrs_in_brd":         any(w in brd_lower for w in ["nfr-", "non-functional"]),
        "constraints_in_brd":  "constraint" in brd_lower,
        "risks_in_brd":        "risk" in brd_lower,
    }
    # Check each present BRD section is addressed in plan phases objectives
    all_phase_text = " ".join(
        " ".join(p.get("objectives", []))
        for p in plan.get("phases", [])
    ).lower()
    sections_present = sum(section_checks.values())
    sections_addressed = 0
    for section_name, is_in_brd in section_checks.items():
        key = section_name.replace("_in_brd", "")
        if is_in_brd:
            if key in all_phase_text or key in str(plan).lower():
                sections_addressed += 1
    coverage_pct = (sections_addressed / sections_present * 100) if sections_present else 0
    _add(checks, "BRD section coverage %",
         coverage_pct >= 80.0, f"{coverage_pct:.0f}%", ">= 80%")

    # ── Sources diversity (Groundedness check: "different sources used") ──
    all_citations = []
    for output in [plan, sched, arch, poc, stack]:
        all_citations.extend(output.get("citations", []))
    unique_source_types = set(c.split("_chunk_")[0] for c in all_citations if "_chunk_" in c)
    _add(checks, "Sources diversity (unique source types)",
         len(unique_source_types) >= 2,
         f"{len(unique_source_types)} types: {list(unique_source_types)[:3]}",
         ">= 2 different source types")

    # ── Ambiguity guardrail: EDGE-003 / org standard 8.1 ─────────────────
    # When BRD is vague, all agents must populate flagged_ambiguities[]
    expected_behaviors = test_config.get("expected_behaviors", {})
    if expected_behaviors.get("all_agents_flagged_ambiguities_non_empty"):
        min_count = expected_behaviors.get("flagged_ambiguities_min_count", 1)
        for agent_key, output in [
            ("plan", plan), ("schedule", sched), ("architect", arch),
            ("poc", poc), ("tech_stack", stack)
        ]:
            if output:
                ambigs = output.get("flagged_ambiguities", [])
                _add(checks, f"flagged_ambiguities non-empty - {agent_key}",
                     len(ambigs) >= min_count,
                     f"{len(ambigs)} items", f">= {min_count} items (org standard 8.1)")

    # ── Conservative default: assumptions must be documented ─────────────
    if expected_behaviors.get("assumptions_min_count"):
        min_assumptions = expected_behaviors["assumptions_min_count"]
        for agent_key, output in [
            ("plan", plan), ("schedule", sched), ("architect", arch),
        ]:
            if output:
                assumptions = output.get("assumptions", [])
                _add(checks, f"assumptions documented - {agent_key}",
                     len(assumptions) >= min_assumptions,
                     f"{len(assumptions)} items", f">= {min_assumptions} (org standard 8.1)")

    # ── Confidence score reflects BRD quality ─────────────────────────────
    if expected_behaviors.get("confidence_score_max"):
        max_conf = expected_behaviors["confidence_score_max"]
        for agent_key, output in [("plan", plan), ("architect", arch)]:
            if output:
                conf = output.get("confidence_score", 1.0)
                _add(checks, f"confidence_score reflects uncertainty - {agent_key}",
                     conf <= max_conf, conf, f"<= {max_conf} for ambiguous BRD")

    passed  = sum(1 for c in checks if c["passed"])
    total   = len(checks)
    return {
        "method":    "rule_based",
        "checks":    checks,
        "passed":    passed,
        "total":     total,
        "score_pct": round(passed / total * 100, 1) if total else 0,
        "pass":      passed == total,
    }


# ══════════════════════════════════════════════════════════════════════════════
# METHOD 2 - LLM-as-Judge (strengthened with EM-readiness + specificity)
# ══════════════════════════════════════════════════════════════════════════════

def run_llm_judge(agent_output: dict, brd_text: str, calibration: dict) -> dict:
    """
    Method 2: LLM-as-Judge with strengthened EM-readiness and specificity criteria.
    Covers: actionability, specificity, grounding quality, EM-readiness.
    """
    from openai import OpenAI
    client    = OpenAI()
    few_shot  = calibration.get("few_shot_prompt_template", "")
    artifacts = _summarize_artifacts(agent_output)

    # Strengthened prompt with explicit EM-readiness and specificity criteria
    prompt = f"""You are an expert Engineering Manager evaluating AI-generated
engineering artifacts for quality. Score each dimension 0.0 to 5.0.

CALIBRATION ANCHORS:
{few_shot}

BRD EXCERPT (first 1200 chars):
{brd_text[:1200]}

ARTIFACTS SUMMARY:
{artifacts}

SCORING DIMENSIONS - use these precise criteria:

1. groundedness (0-5): % of non-trivial claims with RAG chunk_id citation
   5.0 = 100% cited | 3.75 = 75% (passing threshold) | 2.0 = hallucinated data
   ALSO CHECK: Are citations from different source types (BRDs, arch patterns, timelines)?

2. completeness (0-5): ALL BRD sections addressed (Objectives/FRs/NFRs/Constraints/Risks)
   5.0 = every section present in BRD addressed in artifacts
   3.0 = NFRs or constraints section missed entirely
   PENALIZE: generic output that ignores BRD-specific requirements

3. consistency (0-5): Plan/Schedule/Architecture/Tech Stack are internally aligned
   5.0 = total_duration_weeks matches phase sum, arch components consistent with team,
         PoC duration fits Phase 1, tech familiarity reflected in schedule buffer
   2.0 = timeline contradicts BRD constraint, tech stack contradicts team size

4. actionability (0-5): EM-READINESS - can the EM assign work tomorrow with zero rework?
   SPECIFICITY CHECK - penalize: generic phrases, missing owner_roles, no week numbers
   5.0 = every milestone: specific deliverable + owner_role + week number
          risk: specific mitigation with named action + owner
          PoC: specific go/no-go with numeric criteria
          tech stack: specific rationale referencing org decision log
   4.0 = minor gaps (1-2 milestones missing owner or week number)
   2.0 = generic boilerplate - 'build the system', 'resolve the issue', no owners

Respond ONLY with valid JSON:
{{
  "groundedness": 0.0,
  "groundedness_evidence": "specific finding in 1 sentence",
  "sources_diversity": "list the distinct source types cited e.g. arch_pattern, timeline, brd",
  "completeness": 0.0,
  "completeness_evidence": "which BRD sections were missed if any",
  "consistency": 0.0,
  "consistency_evidence": "specific alignment or contradiction found",
  "actionability": 0.0,
  "actionability_evidence": "specific EM-readiness finding - are owner roles and week numbers present?"
}}"""

    try:
        response = client.chat.completions.create(
            model=settings.openai_model_mini,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        scores = json.loads(response.choices[0].message.content)
        overall = sum(scores[d] for d in ["groundedness","completeness","consistency","actionability"]) / 4.0

        badge = (
            "green" if (overall >= 4.0 and scores["groundedness"] >= 3.75
                        and scores["completeness"] >= 5.0
                        and scores["consistency"]  >= 5.0
                        and scores["actionability"] >= 4.0)
            else "amber" if overall >= 3.0 else "red"
        )
        return {
            "method":           "llm_judge",
            "groundedness":     round(scores["groundedness"], 2),
            "completeness":     round(scores["completeness"], 2),
            "consistency":      round(scores["consistency"], 2),
            "actionability":    round(scores["actionability"], 2),
            "overall":          round(overall, 2),
            "badge":            badge,
            "sources_diversity": scores.get("sources_diversity", ""),
            "evidence": {k: v for k, v in scores.items() if k.endswith("_evidence")},
            "pass": badge in ("green", "amber"),
        }
    except Exception as e:
        return {"method": "llm_judge", "error": str(e), "pass": False}


# ══════════════════════════════════════════════════════════════════════════════
# METHOD 3 - Execution-based (schema parse rates, tool-call success)
# ══════════════════════════════════════════════════════════════════════════════

def run_execution_checks(agent_output: dict, pipeline_state=None) -> dict:
    """
    Method 3: Execution-based checks.
    Covers: Pydantic schema parse rates, E2E completion, tool-call success.
    """
    checks = []

    # ── Pydantic schema parse rate ─────────────────────────────────────────
    agents_to_validate = {
        "plan_output":     ("EngineeringPlanOutput", ["agent_name","citations","phases","risks","team_composition","total_duration_weeks","reflection_notes"]),
        "schedule_output": ("ScheduleOutput",         ["agent_name","citations","sprints","total_effort_days","critical_path","buffer_weeks","comparable_projects"]),
        "arch_output":     ("ArchitectureOutput",     ["agent_name","citations","pattern","pattern_justification","components","data_flow","nfr_mappings","deployment_model"]),
        "poc_output":      ("PoCOutput",              ["agent_name","citations","poc_hypothesis","scope_in","scope_out","duration_weeks","success_criteria","team_size","risk_if_poc_fails","go_nogo_criteria"]),
        "stack_output":    ("TechStackOutput",        ["agent_name","citations","options","recommended_option","recommendation_rationale","github_velocity_note"]),
    }
    schema_passed = 0
    for agent_key, (model_name, required_fields) in agents_to_validate.items():
        output = agent_output.get(agent_key, {}) or {}
        if output:
            missing = [f for f in required_fields if f not in output or output[f] is None]
            passed  = len(missing) == 0
            schema_passed += int(passed)
            _add(checks, f"Schema parse - {model_name}",
                 passed,
                 f"missing: {missing}" if missing else "all fields present",
                 "all required fields present")

    total_agents    = len(agents_to_validate)
    schema_pass_rate = schema_passed / total_agents * 100 if total_agents else 0
    _add(checks, "Schema parse rate overall",
         schema_pass_rate == 100.0, f"{schema_pass_rate:.0f}%", "100%")

    # ── E2E pipeline completion ────────────────────────────────────────────
    all_agents_present = all(
        agent_output.get(k) for k in ["plan_output","schedule_output","arch_output","poc_output","stack_output"]
    )
    _add(checks, "E2E pipeline completion",
         all_agents_present, "all 5 agents" if all_agents_present else "partial", "all 5 agents ran")

    # ── Tool-call success: Kroki SVG ──────────────────────────────────────
    arch    = agent_output.get("arch_output", {}) or {}
    has_svg = bool(arch.get("diagram_svg", "").strip())
    _add(checks, "Tool-call - Kroki SVG generated",
         has_svg, "SVG present" if has_svg else "EMPTY", "non-empty SVG string")

    # ── Tool-call success: Mermaid diagram syntax present ─────────────────
    has_mermaid = bool(arch.get("mermaid_diagram", "").strip())
    _add(checks, "Tool-call - Mermaid diagram syntax",
         has_mermaid, "present" if has_mermaid else "EMPTY", "non-empty mermaid syntax")

    # ── Tool-call success: GitHub velocity note ───────────────────────────
    stack   = agent_output.get("stack_output", {}) or {}
    has_ghv = bool(stack.get("github_velocity_note", "").strip())
    _add(checks, "Tool-call - GitHub velocity note",
         has_ghv, "present" if has_ghv else "EMPTY", "non-empty github_velocity_note")

    # ── Duration constraint: PoC <= 4 weeks ───────────────────────────────
    poc       = agent_output.get("poc_output", {}) or {}
    poc_weeks = poc.get("duration_weeks", 0)
    _add(checks, "PoC duration constraint (max 4 weeks)",
         0 < poc_weeks <= 4, poc_weeks, "1-4")

    # ── Options count: 2-3 stack options ─────────────────────────────────
    options_count = len(stack.get("options", []))
    _add(checks, "Tech stack options count (2-3)",
         2 <= options_count <= 3, options_count, "2 or 3")

    passed  = sum(1 for c in checks if c["passed"])
    total   = len(checks)
    return {
        "method":          "execution_based",
        "schema_pass_rate": f"{schema_pass_rate:.0f}%",
        "checks":          checks,
        "passed":          passed,
        "total":           total,
        "score_pct":       round(passed / total * 100, 1) if total else 0,
        "pass":            passed == total,
    }


# ══════════════════════════════════════════════════════════════════════════════
# METHOD 4 - Reference-based (BERTScore)
# ══════════════════════════════════════════════════════════════════════════════

def run_reference_based(agent_output: dict, expected: dict) -> dict:
    """
    Method 4: Reference-based evaluation using BERTScore.
    Compares narrative fields in agent output vs golden expected values.
    Covers: ROUGE/BLEU/BERTScore vs golden outputs.
    Fields evaluated: reflection_notes, pattern_justification, poc_hypothesis,
                      recommendation_rationale.
    Requires: pip install bert-score
    Falls back to simple token overlap if bert-score not installed.
    """
    checks = []

    # Field pairs: (agent_output_path, expected_path, field_label)
    field_pairs = [
        (("plan_output", "reflection_notes"),
         ("engineering_plan", "reflection_notes_example"),
         "reflection_notes"),
        (("arch_output", "pattern_justification"),
         ("architecture", "pattern_justification_example"),
         "pattern_justification"),
        (("poc_output", "poc_hypothesis"),
         ("poc", "hypothesis_must_address"),
         "poc_hypothesis"),
        (("stack_output", "recommendation_rationale"),
         ("tech_stack", "recommended"),
         "recommendation_rationale"),
    ]

    scores = []
    for (agent_path, exp_path, label) in field_pairs:
        # Extract actual text
        actual = agent_output.get(agent_path[0], {}) or {}
        actual_text = actual.get(agent_path[1], "") or ""

        # Extract expected reference text
        exp_section = expected
        for k in exp_path[:-1]:
            exp_section = exp_section.get(k, {}) or {}
        ref_text = str(exp_section.get(exp_path[-1], "") or "")

        if not actual_text or not ref_text:
            _add(checks, f"BERTScore - {label}", False, "empty text", "non-empty actual and reference")
            continue

        # Try BERTScore, fallback to token overlap
        score = _compute_similarity(actual_text, ref_text)
        passed = score >= 0.85   # F1 >= 0.85 is required for paraphrasing
        scores.append(score)
        _add(checks, f"Similarity - {label}", passed,
             f"score={score:.2f}", ">= 0.85")

    avg_score = sum(scores) / len(scores) if scores else 0
    passed    = sum(1 for c in checks if c["passed"])
    total     = len(checks)
    return {
        "method":     "reference_based",
        "avg_score":  round(avg_score, 3),
        "metric":     "BERTScore F1 (or token overlap fallback)",
        "checks":     checks,
        "passed":     passed,
        "total":      total,
        "score_pct":  round(passed / total * 100, 1) if total else 0,
        "pass":       passed == total,
    }


def _compute_similarity(candidate: str, reference: str) -> float:
    """BERTScore F1 with fallback to token overlap ratio."""
    try:
        from bert_score import score as bert_score
        P, R, F1 = bert_score([candidate], [reference], lang="en", verbose=False)
        return float(F1[0])
    except ImportError:
        # Fallback: Jaccard token overlap
        cand_tokens = set(candidate.lower().split())
        ref_tokens  = set(reference.lower().split())
        if not ref_tokens:
            return 0.0
        intersection = cand_tokens & ref_tokens
        union        = cand_tokens | ref_tokens
        return len(intersection) / len(union)


# ══════════════════════════════════════════════════════════════════════════════
# METHOD 5 - Human HITL (read stored em_ratings)
# ══════════════════════════════════════════════════════════════════════════════

def extract_human_ratings(pipeline_state_dict: dict) -> dict:
    """
    Method 5: Human EM ratings captured at HITL gate.
    Reads hitl_em_ratings from PipelineState.
    Rating scale: 1=unusable, 2=poor, 3=acceptable, 4=good, 5=excellent.
    """
    ratings = pipeline_state_dict.get("hitl_em_ratings", [])
    if not ratings:
        return {
            "method": "human_hitl",
            "ratings": [],
            "avg_em_rating": None,
            "pass": None,
            "note": "No EM ratings recorded - EM did not submit a numeric rating at HITL gate",
        }

    avg = sum(r.get("em_rating", 0) for r in ratings) / len(ratings)
    return {
        "method":        "human_hitl",
        "ratings":       ratings,
        "avg_em_rating": round(avg, 2),
        "pass":          avg >= 4.0,   # 4/5 = good threshold for EM approval
        "note":          f"{len(ratings)} HITL gate(s) with EM rating",
    }


# ══════════════════════════════════════════════════════════════════════════════
# Guardrail tests
# ══════════════════════════════════════════════════════════════════════════════

def run_guardrail_test(test_config: dict, agent_output: dict = None) -> dict:
    checks = []

    # Security validator tests (GUARD-001 to 003)
    if test_config.get("expect_status") in ("BLOCKED", "WARNING"):
        from src.security.validator import SecurityValidator, ValidationStatus
        content  = Path(test_config["brd_file"]).read_bytes()
        filename = Path(test_config["brd_file"]).name
        result   = SecurityValidator().validate(content, filename, "text/plain")

        expected_status = test_config.get("expect_status")
        _add(checks, "Validation status",
             result.status.value.upper() == expected_status,
             result.status.value.upper(), expected_status)

        if test_config.get("expect_blocked"):
            _add(checks, "Pipeline blocked",
                 result.status == ValidationStatus.BLOCKED,
                 result.status.value, "BLOCKED")

        if reason := test_config.get("block_reason_contains"):
            _add(checks, f"Block reason contains '{reason}'",
                 reason.lower() in result.user_message.lower(),
                 result.user_message[:60], f"contains '{reason}'")

        for pii_type in test_config.get("expect_pii_types", []):
            _add(checks, f"PII detected: {pii_type}",
                 pii_type in result.pii_types_found,
                 result.pii_types_found, f"{pii_type} in list")

        if test_config.get("expect_no_agents"):
            _add(checks, "No BRD text forwarded to agents",
                 result.brd_text_clean is None,
                 "blocked" if result.brd_text_clean is None else "forwarded", "blocked")

    # Scope creep test (GUARD-004) - requires pipeline to have run
    if forbidden_terms := test_config.get("forbidden_scope_terms"):
        if agent_output:
            all_output_text = json.dumps(agent_output).lower()
            for term in forbidden_terms:
                term_found = term.lower() in all_output_text
                _add(checks, f"Scope creep: '{term}' absent from output",
                     not term_found,
                     "FOUND in output" if term_found else "absent",
                     "must not appear in any agent output")

            # Phase count constraint
            plan = agent_output.get("plan_output", {}) or {}
            if max_phases := test_config.get("max_phases"):
                actual_phases = len(plan.get("phases", []))
                _add(checks, f"Phase count (max {max_phases} for simple BRD)",
                     actual_phases <= max_phases, actual_phases, f"<= {max_phases}")

            # Duration constraint
            if max_weeks := test_config.get("max_duration_weeks"):
                actual_weeks = plan.get("total_duration_weeks", 0)
                _add(checks, f"Duration (max {max_weeks} weeks per BRD constraint)",
                     actual_weeks <= max_weeks, actual_weeks, f"<= {max_weeks}")
        else:
            _add(checks, "Scope creep check requires pipeline output",
                 False, "no agent output", "pipeline must run first")

    passed = sum(1 for c in checks if c["passed"])
    return {
        "method":    "guardrail",
        "checks":    checks,
        "passed":    passed,
        "total":     len(checks),
        "score_pct": round(passed / len(checks) * 100, 1) if checks else 0,
        "pass":      passed == len(checks),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _add(checks: list, check: str, passed: bool, actual, expected) -> None:
    checks.append({"check": check, "passed": passed, "actual": str(actual), "expected": str(expected)})


def _summarize_artifacts(agent_output: dict) -> str:
    lines = []
    if p := agent_output.get("plan_output"):
        lines.append(f"PLAN: {len(p.get('phases',[]))} phases | {len(p.get('risks',[]))} risks | citations={p.get('citations',[])} | reflection_notes={bool(p.get('reflection_notes'))}")
    if s := agent_output.get("schedule_output"):
        lines.append(f"SCHEDULE: {s.get('total_effort_days','?')} days | buffer={s.get('buffer_weeks','?')}w | comparable_projects={s.get('comparable_projects',[])} | citations={s.get('citations',[])}")
    if a := agent_output.get("arch_output"):
        lines.append(f"ARCH: pattern='{a.get('pattern','?')}' | components={len(a.get('components',[]))} | nfr_mappings={len(a.get('nfr_mappings',[]))} | has_mermaid={bool(a.get('mermaid_diagram'))} | citations={a.get('citations',[])}")
    if p := agent_output.get("poc_output"):
        lines.append(f"POC: '{str(p.get('poc_hypothesis','?'))[:80]}' | duration={p.get('duration_weeks','?')}w | has_go_nogo={bool(p.get('go_nogo_criteria'))} | has_rif={bool(p.get('risk_if_poc_fails'))}")
    if s := agent_output.get("stack_output"):
        lines.append(f"STACK: recommended='{s.get('recommended_option','?')}' | options={len(s.get('options',[]))} | has_github_velocity={bool(s.get('github_velocity_note'))} | citations={s.get('citations',[])}")
    if c := agent_output.get("critic"):
        lines.append(f"CRITIC: overall={c.get('overall_score','?')} | badge={c.get('badge','?')} | revision={c.get('revision_number','?')}")
    return "\n".join(lines) if lines else "No agent outputs"


def _write_results(results: dict, timestamp: str):
    path = LOGS_DIR / f"eval_results_{timestamp}.json"
    path.write_text(json.dumps(results, indent=2))

    # ── Run dataset-level operationalization check ─────────────────────────
    ops_report = run_operationalization_check(results)
    results["operationalization"] = ops_report

    # Re-write with ops report included
    path.write_text(json.dumps(results, indent=2))

    total  = len(results["tests"])
    passed = sum(1 for t in results["tests"]
                 if any(t.get(m, {}).get("pass") for m in ["rule_based","llm_judge","execution_based","pass"]))

    print(f"\n{'═'*60}")
    print(f"  Saved: {path}")
    print(f"  Pipeline tests: {passed}/{total} had at least one method pass")
    _print_operationalization_report(ops_report)
    print(f"{'═'*60}\n")


def run_operationalization_check(results: dict) -> dict:
    """
    Dataset-level success criteria measurement.
    Evaluates all 5 SC across the full test dataset - not just per-run.

    SC-1: completeness  ≥ 5.0 on ALL test BRDs
    SC-2: actionability ≥ 4.0 AVERAGE across test dataset
    SC-3: E2E pipeline  < 300s on ALL test BRDs
    SC-4: schema        100% pass rate on ALL agents ALL BRDs
    SC-5: groundedness  ≥ 3.75 on ALL test BRDs
    """
    tests = results.get("tests", [])
    if not tests:
        return {"error": "No test results to evaluate"}

    sc_results = {}

    # SC-1: Completeness >= 5.0 on all BRDs
    completeness_scores = [
        t.get("llm_judge", {}).get("completeness", None)
        for t in tests if "llm_judge" in t
    ]
    completeness_scores = [s for s in completeness_scores if s is not None]
    sc_results["SC-1_completeness"] = {
        "threshold":     5.0,
        "scores":        completeness_scores,
        "avg":           round(sum(completeness_scores)/len(completeness_scores), 2) if completeness_scores else None,
        "all_pass":      all(s >= 5.0 for s in completeness_scores),
        "pass":          all(s >= 5.0 for s in completeness_scores) if completeness_scores else False,
    }

    # SC-2: Actionability avg >= 4.0 across dataset
    actionability_scores = [
        t.get("llm_judge", {}).get("actionability", None)
        for t in tests if "llm_judge" in t
    ]
    actionability_scores = [s for s in actionability_scores if s is not None]
    avg_action = sum(actionability_scores)/len(actionability_scores) if actionability_scores else 0
    sc_results["SC-2_actionability"] = {
        "threshold":  4.0,
        "scores":     actionability_scores,
        "avg":        round(avg_action, 2),
        "pass":       avg_action >= 4.0,
    }

    # SC-3: E2E pipeline time < 300s - read from execution logs
    for t in tests:
        ex = t.get("execution_based", {})
        for check in ex.get("checks", []):
            if "execution" in check.get("check", "").lower() or "wall" in check.get("check", "").lower():
                pass  # would read from actual pipeline timing
    sc_results["SC-3_pipeline_time"] = {
        "threshold_ms": 300_000,
        "note":         "Measured by log_pipeline_summary() in pipeline.py - check logs/pipeline.jsonl",
        "pass":         None,   # None = requires actual pipeline run to measure
    }

    # SC-4: Schema compliance 100%
    schema_passes = []
    for t in tests:
        ex = t.get("execution_based", {})
        rate_check = next(
            (c for c in ex.get("checks", []) if "schema parse rate" in c.get("check", "").lower()),
            None
        )
        if rate_check:
            schema_passes.append(rate_check.get("passed", False))
    sc_results["SC-4_schema_compliance"] = {
        "threshold":  "100%",
        "results":    schema_passes,
        "pass":       all(schema_passes) if schema_passes else None,
    }

    # SC-5: Groundedness >= 3.75 on all BRDs
    groundedness_scores = [
        t.get("llm_judge", {}).get("groundedness", None)
        for t in tests if "llm_judge" in t
    ]
    groundedness_scores = [s for s in groundedness_scores if s is not None]
    sc_results["SC-5_groundedness"] = {
        "threshold":  3.75,
        "scores":     groundedness_scores,
        "avg":        round(sum(groundedness_scores)/len(groundedness_scores), 2) if groundedness_scores else None,
        "all_pass":   all(s >= 3.75 for s in groundedness_scores),
        "pass":       all(s >= 3.75 for s in groundedness_scores) if groundedness_scores else False,
    }

    return sc_results


def _print_operationalization_report(ops: dict) -> None:
    """Print dataset-level success criteria summary table."""
    print(f"\n  {'─'*56}")
    print("  OPERATIONALIZATION - Dataset-level Success Criteria")
    print(f"  {'─'*56}")
    labels = {
        "SC-1_completeness":   "SC-1 Completeness  ≥ 5.0 all BRDs",
        "SC-2_actionability":  "SC-2 Actionability avg ≥ 4.0",
        "SC-3_pipeline_time":  "SC-3 E2E time < 5 min",
        "SC-4_schema_compliance": "SC-4 Schema 100% pass",
        "SC-5_groundedness":   "SC-5 Groundedness  ≥ 3.75 all BRDs",
    }
    for key, label in labels.items():
        data = ops.get(key, {})
        passed = data.get("pass")
        if passed is None:
            icon = "⏳"
            detail = data.get("note", "requires pipeline run")
        elif passed:
            icon = "✅"
            avg = data.get("avg")
            detail = f"avg={avg}" if avg else "pass"
        else:
            icon = "❌"
            avg = data.get("avg")
            detail = f"avg={avg} (below threshold)" if avg else "FAIL"
        print(f"  {icon} {label:<35} {detail}")


# ══════════════════════════════════════════════════════════════════════════════
# Main runner
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brd",        help="Run only this BRD file")
    parser.add_argument("--method",     choices=["rule","llm","execution","reference","all"], default="all")
    parser.add_argument("--guardrails", action="store_true")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results   = {"run_timestamp": timestamp, "methods_run": [], "tests": []}

    calibration = {}
    calib_file  = EVAL_DIR / "critic_calibration_set.json"
    if calib_file.exists():
        calibration = json.loads(calib_file.read_text())

    print(f"\n{'═'*60}")
    print(f"  EM Copilot Eval Runner - {timestamp}")
    print(f"  Methods: {args.method} | Guardrails: {args.guardrails}")
    print(f"{'═'*60}\n")

    # Guardrails
    if args.guardrails or not args.brd:
        print("GUARDRAIL TESTS")
        print("─" * 40)
        for test in GUARDRAIL_TESTS:
            if not Path(test["brd_file"]).exists():
                print(f"  ⚠️  SKIP - file not found: {test['brd_file']}")
                continue
            result = run_guardrail_test(test)
            icon   = "✅" if result["pass"] else "❌"
            print(f"  {icon} {test['test_id']}: {test['name']} - {result['score_pct']}%")
            for c in result["checks"]:
                print(f"    {'✓' if c['passed'] else '✗'} {c['check']}: {c['actual']}")
            results["tests"].append({"test_id": test["test_id"], **result})
        print()

    if args.guardrails:
        _write_results(results, timestamp)
        return

    # Pipeline tests
    tests = PIPELINE_TESTS + EDGE_CASE_TESTS
    if args.brd:
        tests = [t for t in tests if str(t["brd_file"]) == args.brd]

    print("PIPELINE TESTS")
    for test in tests:
        if not Path(test["brd_file"]).exists():
            print(f"  ⚠️  SKIP {test['test_id']} - {test['brd_file']}")
            continue

        brd_text    = strip_eval_metadata(
            Path(test["brd_file"]).read_text(encoding="utf-8")
        )
        test_result = {"test_id": test["test_id"], "name": test["name"]}
        print(f"\n  {test['test_id']}: {test['name']}")

        # Run pipeline (or use mock if not built)
        agent_output = {}
        try:
            import hashlib

            from src.agents.pipeline import run_pipeline
            brd_hash = hashlib.sha256(brd_text.encode()).hexdigest()
            state    = run_pipeline(brd_text, brd_hash, brd_hash[:8])
            agent_output = {
                "plan_output":     state.plan_output.model_dump() if state.plan_output else {},
                "schedule_output": state.schedule_output.model_dump() if state.schedule_output else {},
                "arch_output":     state.arch_output.model_dump() if state.arch_output else {},
                "poc_output":      state.poc_output.model_dump() if state.poc_output else {},
                "stack_output":    state.stack_output.model_dump() if state.stack_output else {},
                "critic":          state.critic_output.model_dump() if state.critic_output else {},
            }
            # Method 5 - Human HITL
            human = extract_human_ratings(state.model_dump())
            test_result["human_hitl"] = human
            if human.get("avg_em_rating"):
                print(f"    👤 EM rating: {human['avg_em_rating']}/5")
        except ImportError:
            print("    ⚠️  Pipeline not built - schema/reference tests only")

        # Method 1 - Rule-based
        if args.method in ("rule", "all") and "expected_file" in test:
            exp_path = test.get("expected_file")
            if exp_path and Path(exp_path).exists():
                expected = json.loads(Path(exp_path).read_text())
                test["brd_text"] = brd_text
                rb = run_rule_based_checks(agent_output, expected, test)
                icon = "✅" if rb["pass"] else "❌"
                print(f"    Rule-based:   {icon} {rb['score_pct']}% ({rb['passed']}/{rb['total']})")
                for c in [c for c in rb["checks"] if not c["passed"]]:
                    print(f"      ✗ {c['check']}: {c['actual']} (expected {c['expected']})")
                test_result["rule_based"] = rb
                results["methods_run"].append("rule_based")

        # Method 2 - LLM-as-Judge
        if args.method in ("llm", "all") and agent_output:
            llm = run_llm_judge(agent_output, brd_text, calibration)
            if "error" not in llm:
                icon = "✅" if llm["pass"] else "❌"
                print(f"    LLM-as-judge: {icon} overall={llm['overall']} badge={llm['badge']}")
                print(f"      G={llm['groundedness']} C={llm['completeness']} Con={llm['consistency']} A={llm['actionability']}")
                print(f"      Sources: {llm.get('sources_diversity','?')}")
            else:
                print(f"    LLM-as-judge: ⚠️ {llm['error']}")
            test_result["llm_judge"] = llm
            results["methods_run"].append("llm_judge")

        # Method 3 - Execution-based
        if args.method in ("execution", "all"):
            ex = run_execution_checks(agent_output)
            icon = "✅" if ex["pass"] else "❌"
            print(f"    Execution:    {icon} schema_rate={ex['schema_pass_rate']} {ex['score_pct']}% ({ex['passed']}/{ex['total']})")
            for c in [c for c in ex["checks"] if not c["passed"]]:
                print(f"      ✗ {c['check']}: {c['actual']}")
            test_result["execution_based"] = ex
            results["methods_run"].append("execution_based")

        # Method 4 - Reference-based
        if args.method in ("reference", "all") and "expected_file" in test:
            exp_path = test.get("expected_file")
            if exp_path and Path(exp_path).exists() and agent_output:
                expected = json.loads(Path(exp_path).read_text())
                ref = run_reference_based(agent_output, expected)
                icon = "✅" if ref["pass"] else "❌"
                print(f"    Reference:    {icon} avg={ref['avg_score']} ({ref['metric']})")
                test_result["reference_based"] = ref
                results["methods_run"].append("reference_based")

        results["tests"].append(test_result)

    _write_results(results, timestamp)


if __name__ == "__main__":
    main()
