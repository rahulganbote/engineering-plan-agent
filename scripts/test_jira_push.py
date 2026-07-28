"""
scripts/test_jira_push.py
══════════════════════════
Standalone smoke test for the Jira integration - does NOT touch FastAPI
or the LangGraph pipeline. Run it directly to confirm:

    1. JIRA_* env vars are loaded correctly.
    2. Basic auth header is built from your email + API token.
    3. The Atlassian Document Format (ADF) body validates against Jira's schema.
    4. The Mermaid code block renders as a diagram in the created issue.

Usage:
    # From the project root, with your venv activated
    python scripts/test_jira_push.py

    # Or with a synthetic minimal state (no real pipeline run needed)
    python scripts/test_jira_push.py --fixture

What you should see on success:
    ✓ Credentials OK · base=https://yourorg.atlassian.net project=EMCP
    ✓ Posted to Jira
        key     : EMCP-42
        url     : https://yourorg.atlassian.net/browse/EMCP-42
        mode    : jira
        detail  : Created Jira Task EMCP-42

Open the URL - the Mermaid diagram should render inline in the issue body.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `src.*` importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # type: ignore

load_dotenv("secrets/.env")
load_dotenv(".env")  # belt-and-braces, in case of root-level .env

from src.core.config import settings

# ──────────────────────────────────────────────────────────────────────────────
# Fixture: minimal but realistic PipelineState
# ──────────────────────────────────────────────────────────────────────────────

def build_fixture_state():
    """Build a fully-populated PipelineState that exercises every section of
    the ADF builder. Same shape as the Sheets smoke fixture so we don't drift."""
    from src.core.models import (
        ArchitectureOutput,
        Component,
        CriticOutput,
        DimensionScore,
        EngineeringPlanOutput,
        HITLDecision,
        Milestone,
        NFRMapping,
        Phase,
        PipelineState,
        PoCOutput,
        QualityBadge,
        Risk,
        RiskLevel,
        ScheduleOutput,
        SprintRow,
        StackOption,
        SuccessCriterion,
        TechStackOutput,
    )

    state = PipelineState(run_id="jira-smoke", brd_raw_hash="cafef00d" * 8)
    state.hitl_decision = HITLDecision.APPROVED
    state.revision_count = 1

    state.plan_output = EngineeringPlanOutput(
        run_id="jira-smoke", citations=["chunk-1", "chunk-2"], confidence_score=0.82,
        phases=[
            Phase(name="Discovery", duration_weeks=2,
                  objectives=["Validate scope"],
                  milestones=[Milestone(name="Kickoff", week=1,
                                        deliverable="Charter signed",
                                        owner_role="EM")]),
            Phase(name="Build", duration_weeks=8,
                  objectives=["Ship MVP"],
                  milestones=[Milestone(name="Internal beta", week=8,
                                        deliverable="Beta in staging",
                                        owner_role="Tech Lead")]),
        ],
        risks=[Risk(description="Stripe sandbox quota exhaustion",
                    likelihood=RiskLevel.MEDIUM, impact=RiskLevel.HIGH,
                    mitigation="Order extended-quota API key in week 1",
                    citation="chunk-1")],
        team_composition={"Senior Engineer": 4, "QA": 2, "EM": 1},
        total_duration_weeks=12,
        reflection_notes="Compressed Discovery from 3w → 2w after RAG showed similar projects ran 2w.",
    )

    state.schedule_output = ScheduleOutput(
        run_id="jira-smoke", citations=["chunk-7"], confidence_score=0.76,
        sprints=[SprintRow(sprint=1, week_range="W1–W2", deliverables=["Kickoff"],
                           team_members=["EM", "TL"], effort_days=14.0)],
        total_effort_days=120.0,
        critical_path=["Discovery", "Build", "Hardening"],
        buffer_weeks=2, comparable_projects=["chunk-9", "chunk-11"],
    )

    arch_mermaid = (
        "graph LR\n"
        "  Customer[Customer App] --> ApiGateway[API Gateway]\n"
        "  ApiGateway --> OrderSvc[Order Service]\n"
        "  ApiGateway --> DispatchSvc[Dispatch Service]\n"
        "  OrderSvc --> Queue[(Event Bus)]\n"
        "  Queue --> DispatchSvc\n"
        "  DispatchSvc --> CourierApp[Courier App]\n"
        "  OrderSvc --> Db[(Order DB)]\n"
        "  OrderSvc --> Stripe[Stripe Payments]"
    )
    state.arch_output = ArchitectureOutput(
        run_id="jira-smoke", citations=["chunk-5"], confidence_score=0.80,
        pattern="Event-driven microservices",
        pattern_justification=(
            "500 orders/min peak; queue-based decoupling keeps order capture available "
            "even when dispatch is degraded."
        ),
        components=[
            Component(name="Order Service", responsibility="Take and validate orders",
                      technology="FastAPI", interfaces=["REST"]),
            Component(name="Dispatch Service", responsibility="Assign couriers",
                      technology="Python worker", interfaces=["Event consumer"]),
            Component(name="Order DB", responsibility="Persist orders + audit trail",
                      technology="Postgres", interfaces=["SQL"]),
        ],
        data_flow=["customer → api → order svc → queue → dispatch → courier"],
        nfr_mappings=[NFRMapping(
            nfr="99.9% availability for order placement",
            architecture_decision="Multi-AZ, queue buffer, idempotent retries",
            citation="chunk-5",
        )],
        deployment_model="AWS EKS multi-AZ",
        diagram_mermaid=arch_mermaid,
        diagram_svg=None,
    )

    state.poc_output = PoCOutput(
        run_id="jira-smoke", citations=["chunk-3"], confidence_score=0.70,
        poc_hypothesis="Stripe Connect can payout to 200 restaurants on a daily cycle.",
        scope_in=["Stripe sandbox", "Mock dispatcher"],
        scope_out=["Real couriers", "Real money"],
        duration_weeks=3,
        success_criteria=[SuccessCriterion(
            metric="payout success rate", target_value=">=99%",
            measurement_method="100 sandbox runs",
        )],
        team_size=3,
        risk_if_poc_fails="Need to evaluate alternative payouts provider (Adyen) - adds 4w.",
    )

    state.stack_output = TechStackOutput(
        run_id="jira-smoke", citations=["chunk-13"], confidence_score=0.78,
        options=[
            StackOption(
                name="Python/FastAPI + AWS",
                components={"backend": "FastAPI", "db": "Postgres"},
                scalability_rating=4, team_familiarity_rating=5,
                integration_risk=RiskLevel.LOW,
                estimated_monthly_cost_usd=4200.0,
                pros=["Team knows it"], cons=["Cold start latency"],
                citation="chunk-13",
            ),
            StackOption(
                name="Node/Lambda + AWS",
                components={"backend": "Node", "db": "DynamoDB"},
                scalability_rating=5, team_familiarity_rating=3,
                integration_risk=RiskLevel.MEDIUM,
                estimated_monthly_cost_usd=3100.0,
                pros=["Cheaper at scale"], cons=["Team learning curve"],
                citation="chunk-13",
            ),
        ],
        recommended_option="Python/FastAPI + AWS",
        recommendation_rationale=(
            "Team familiarity outweighs Option B cost savings for release 1; "
            "GitHub velocity signal shows 3x faster bug-fix turnaround on Python stack."
        ),
    )

    def _dim(score, thr):
        return DimensionScore(score=score, threshold=thr, passed=score >= thr,
                              evidence="ok", improvement_suggestion="-")
    state.critic_output = CriticOutput(
        run_id="jira-smoke", revision_number=1,
        target_agents=["engineering_plan_generator", "tech_stack_recommender"],
        groundedness=_dim(4.20, 3.75),
        completeness=_dim(5.00, 5.00),
        consistency=_dim(5.00, 5.00),
        actionability=_dim(4.10, 4.00),
        overall_score=4.55, badge=QualityBadge.GREEN, requires_revision=False,
        agent_feedback={}, consistency_issues=[], hallucination_flags=[],
    )

    return state


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", action="store_true",
                    help="(default) use synthetic fixture state - no pipeline needed")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the ADF payload that WOULD be posted; do not POST")
    args = ap.parse_args()

    # 1. Show creds that will be used (mask the token)
    print("─" * 60)
    print("Jira config (sourced from env via src.core.config):")
    print(f"  base_url      : {settings.jira_base_url or '(not set)'}")
    print(f"  email         : {settings.jira_email or '(not set)'}")
    print(f"  api_token     : {'***' + settings.jira_api_token[-4:] if settings.jira_api_token else '(not set)'}")
    print(f"  project_key   : {settings.jira_project_key or '(not set)'}")
    print(f"  issue_type    : {settings.jira_issue_type}")
    print(f"  label_prefix  : {settings.jira_label_prefix}")
    print("─" * 60)

    # 2. Probe credentials before building any payload
    from src.integrations.jira import _build_adf_description, _build_labels, _build_summary, _credentials_status
    ok, why_not = _credentials_status()
    if not ok:
        print(f"✗ Credentials check FAILED: {why_not}")
        return 2
    print(f"✓ Credentials OK · base={settings.jira_base_url} project={settings.jira_project_key}")

    state = build_fixture_state()

    # 3. Show what we'd post
    print()
    print("Summary :", _build_summary(state))
    print("Labels  :", _build_labels(state))
    desc = _build_adf_description(state)
    print(f"ADF top-level blocks: {len(desc['content'])}")
    print(f"  Block types: {sorted({b.get('type') for b in desc['content']})}")
    code_blocks = [b for b in desc['content'] if b.get("type") == "codeBlock"]
    if code_blocks:
        first = code_blocks[0]
        print(f"  Code block language: {first.get('attrs', {}).get('language')} "
              f"(should be 'mermaid')")

    if args.dry_run:
        import json
        print()
        print("--- ADF payload (dry-run) ---")
        print(json.dumps(desc, indent=2)[:2000] + "..." if len(json.dumps(desc)) > 2000 else json.dumps(desc, indent=2))
        return 0

    # 4. Actually POST
    from src.integrations.jira import push_artifacts_to_jira
    print()
    print("Posting to Jira...")
    result = push_artifacts_to_jira(state)
    print()
    print("─" * 60)
    print(f"  url       : {result.get('url')}")
    print(f"  mode      : {result.get('mode')}")
    print(f"  issue_key : {result.get('issue_key')}")
    print(f"  detail    : {result.get('detail')}")
    if result.get('fallback_reason'):
        print(f"  reason    : {result.get('fallback_reason')}")
    print("─" * 60)

    if result.get("mode") == "jira":
        print()
        print("✓ Success - open the URL above to verify the Mermaid diagram renders inline.")
        return 0
    print()
    print("✗ Push did not succeed. See 'detail' / 'reason' above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
