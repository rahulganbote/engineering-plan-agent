"""
scripts/test_jira_mcp.py
═════════════════════════
Standalone smoke test for the MCP-based Jira Epic integration.

Verifies the full MCP round-trip WITHOUT running the FastAPI pipeline:
    spawn mcp-atlassian server → MCP handshake → list_tools →
    call_tool("jira_create_issue", issue_type="Epic")

Run this BEFORE relying on the MCP path in a demo. If it fails, the /approve
endpoint will silently fall back to the REST integration (src/integrations/jira.py).

Prerequisites
─────────────
    pip install mcp mcp-atlassian
    # secrets/.env must have JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY

Usage
─────
    python scripts/test_jira_mcp.py            # full round-trip - creates a real Epic
    python scripts/test_jira_mcp.py --dry-run  # build payload + check imports, no Jira call

Expected on success
───────────────────
    ✓ Credentials OK
    ✓ mcp SDK importable
    ✓ MCP server handshake complete - N tools discovered
    ✓ Epic created
        key : SCRUM-123
        url : https://yourorg.atlassian.net/browse/SCRUM-123
        via : mcp
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # type: ignore
load_dotenv("secrets/.env")
load_dotenv(".env")

from src.core.config import settings


def _build_fixture_state():
    """Minimal but realistic PipelineState - same shape used by test_jira_push.py."""
    from src.core.models import (
        PipelineState, HITLDecision, QualityBadge, RiskLevel,
        EngineeringPlanOutput, Phase, Milestone, Risk,
        ScheduleOutput, SprintRow,
        ArchitectureOutput, Component, NFRMapping,
        PoCOutput, SuccessCriterion,
        TechStackOutput, StackOption,
        CriticOutput, DimensionScore,
    )

    state = PipelineState(run_id="jira-mcp-smoke", brd_raw_hash="deadbeef" * 8)
    state.hitl_decision = HITLDecision.APPROVED
    state.revision_count = 1
    state.brd_name = "FoodHub"

    state.plan_output = EngineeringPlanOutput(
        run_id="jira-mcp-smoke", citations=["chunk-1"], confidence_score=0.82,
        phases=[Phase(name="Discovery", duration_weeks=2, objectives=["Validate scope"],
                      milestones=[Milestone(name="Kickoff", week=1,
                                            deliverable="Charter signed", owner_role="EM")])],
        risks=[Risk(description="Vendor delay", likelihood=RiskLevel.HIGH,
                    impact=RiskLevel.CRITICAL, mitigation="Order keys week 1",
                    citation="chunk-1")],
        team_composition={"Senior Engineer": 3, "QA": 1},
        total_duration_weeks=14,
        reflection_notes="Compressed discovery after RAG comparison.",
    )
    state.schedule_output = ScheduleOutput(
        run_id="jira-mcp-smoke", citations=["chunk-7"], confidence_score=0.76,
        sprints=[SprintRow(sprint=1, week_range="W1-W2", deliverables=["Kickoff"],
                           team_members=["EM"], effort_days=14.0)],
        total_effort_days=120.0, critical_path=["Discovery", "Build"],
        buffer_weeks=2, comparable_projects=["chunk-9"],
    )
    state.arch_output = ArchitectureOutput(
        run_id="jira-mcp-smoke", citations=["chunk-5"], confidence_score=0.80,
        pattern="Event-driven microservices",
        pattern_justification="Decouples order capture from dispatch at peak load.",
        components=[Component(name="Order Service", responsibility="Take orders",
                              technology="FastAPI", interfaces=["REST"])],
        data_flow=["client -> api -> queue -> worker"],
        nfr_mappings=[NFRMapping(nfr="99.9% availability",
                                 architecture_decision="Multi-AZ + retries",
                                 citation="chunk-5")],
        deployment_model="AWS EKS multi-AZ",
        diagram_mermaid="graph LR\n  Client --> API[API Gateway]\n  API --> DB[(Order DB)]",
        diagram_svg=None,
    )
    state.poc_output = PoCOutput(
        run_id="jira-mcp-smoke", citations=["chunk-3"], confidence_score=0.70,
        poc_hypothesis="Stripe Connect can pay out 200 restaurants daily.",
        scope_in=["Stripe sandbox"], scope_out=["Real money"],
        duration_weeks=3,
        success_criteria=[SuccessCriterion(metric="payout success", target_value=">=99%",
                                           measurement_method="100 sandbox runs")],
        team_size=3, risk_if_poc_fails="Evaluate alternative provider - adds 4w.",
    )
    state.stack_output = TechStackOutput(
        run_id="jira-mcp-smoke", citations=["chunk-13"], confidence_score=0.78,
        options=[
            StackOption(name="Python/FastAPI + AWS",
                        components={"backend": "FastAPI"},
                        scalability_rating=4, team_familiarity_rating=5,
                        integration_risk=RiskLevel.LOW,
                        estimated_monthly_cost_usd=4200.0,
                        pros=["Team knows it"], cons=["Cold start"], citation="chunk-13"),
            StackOption(name="Node/Lambda + AWS",
                        components={"backend": "Node"},
                        scalability_rating=5, team_familiarity_rating=3,
                        integration_risk=RiskLevel.MEDIUM,
                        estimated_monthly_cost_usd=3100.0,
                        pros=["Cheaper"], cons=["Learning curve"], citation="chunk-13"),
        ],
        recommended_option="Python/FastAPI + AWS",
        recommendation_rationale="Team familiarity outweighs Option B savings for release 1.",
    )

    def _dim(s, t):
        return DimensionScore(score=s, threshold=t, passed=s >= t,
                              evidence="ok", improvement_suggestion="-")
    state.critic_output = CriticOutput(
        run_id="jira-mcp-smoke", revision_number=1,
        target_agents=["engineering_plan_generator"],
        groundedness=_dim(4.2, 3.75), completeness=_dim(5.0, 5.0),
        consistency=_dim(5.0, 5.0), actionability=_dim(4.1, 4.0),
        overall_score=4.55, badge=QualityBadge.GREEN, requires_revision=False,
        agent_feedback={}, consistency_issues=[], hallucination_flags=[],
    )
    return state


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="check imports + build payload; do NOT call Jira")
    args = ap.parse_args()

    print("─" * 64)
    print("Jira MCP integration - smoke test")
    print("─" * 64)
    print(f"  JIRA_URL        : {settings.jira_base_url or '(not set)'}")
    print(f"  JIRA_USERNAME   : {settings.jira_email or '(not set)'}")
    print(f"  JIRA_API_TOKEN  : {'***' + settings.jira_api_token[-4:] if settings.jira_api_token else '(not set)'}")
    print(f"  JIRA_PROJECT    : {settings.jira_project_key or '(not set)'}")
    print("─" * 64)

    # 1. Credentials
    from src.integrations.jira import _credentials_status
    ok, why_not = _credentials_status()
    if not ok:
        print(f"✗ Credentials check FAILED: {why_not}")
        return 2
    print("✓ Credentials OK")

    # 2. MCP SDK importable
    try:
        from mcp import ClientSession, StdioServerParameters  # noqa: F401
        from mcp.client.stdio import stdio_client            # noqa: F401
        print("✓ mcp SDK importable")
    except ImportError as e:
        print(f"✗ mcp SDK not installed: {e}")
        print("  Fix: pip install mcp mcp-atlassian")
        return 2

    # 3. Build the fixture + payload
    state = _build_fixture_state()
    from src.integrations.jira_mcp import _build_markdown_description, MCP_SERVER_COMMAND, MCP_SERVER_ARGS
    from src.integrations.jira import _build_summary, _build_labels

    summary = _build_summary(state)
    labels  = _build_labels(state)
    desc    = _build_markdown_description(state)
    print()
    print(f"  Epic summary    : {summary}")
    print(f"  Labels          : {labels}")
    print(f"  Description     : {len(desc)} chars")
    print(f"  MCP server cmd  : {MCP_SERVER_COMMAND} {' '.join(MCP_SERVER_ARGS)}")

    if args.dry_run:
        print()
        print("--- Description preview (first 600 chars) ---")
        print(desc[:600])
        print()
        print("✓ Dry run complete - imports OK, payload built. No Jira call made.")
        return 0

    # 4. Full MCP round-trip
    print()
    print("Calling mcp-atlassian server to create an Epic...")
    from src.integrations.jira_mcp import push_epic_to_jira_via_mcp
    result = await push_epic_to_jira_via_mcp(state)

    print("─" * 64)
    for k in ("mode", "issue_key", "url", "detail", "transport", "fallback_reason"):
        if result.get(k) is not None:
            print(f"  {k:16s}: {result[k]}")
    print("─" * 64)

    if result.get("mode") == "jira":
        print()
        print("✓ Epic created via MCP - open the URL above to verify it's an Epic.")
        return 0
    print()
    print("✗ MCP path did not succeed. The /approve endpoint would fall back to REST.")
    print(f"  Reason: {result.get('fallback_reason')}")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
