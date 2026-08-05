# tests/unit/test_pass2_alignment.py
from unittest.mock import MagicMock, patch

from src.agents.orchestrator import OrchestratorAgent
from src.agents.pipeline import _feedback_for, _run_specialists_in_parallel, route_after_decision
from src.core.models import AlignmentDirective, AlignmentMemo, PipelineState


def test_arbitrate_drafts_creation():
    """Verify that arbitrate_drafts correctly queries and parses alignment directives."""
    state = PipelineState(run_id="test-run-123", brd_raw_hash="hash", brd_name="test.txt")

    mock_arch = MagicMock()
    mock_arch.pattern = "microservices"
    mock_arch.components = []
    state.draft_arch_output = mock_arch

    mock_stack = MagicMock()
    mock_stack.recommended_option = "FastAPI"
    mock_stack.options = []
    state.draft_stack_output = mock_stack

    mock_json_response = """
    {
      "directives": [
        {
          "agent_name": "tech_stack_recommender",
          "directive": "Switch Postgres to MySQL",
          "reasoning": "Database alignment with legacy systems",
          "evidence": "BRD page 3"
        }
      ],
      "overall_strategy": "Align database choice"
    }
    """

    with patch("src.core.providers.complete_with_fallback") as mock_complete:
        mock_complete.return_value = (mock_json_response, 100, 50, "openai")

        memo = OrchestratorAgent().arbitrate_drafts(state)

        assert isinstance(memo, AlignmentMemo)
        assert len(memo.directives) == 1
        assert memo.directives[0].agent_name == "tech_stack_recommender"
        assert memo.directives[0].directive == "Switch Postgres to MySQL"
        assert memo.overall_strategy == "Align database choice"


def test_pass2_feedback_injection():
    """Verify that _feedback_for correctly injects the EM Alignment Memo on Pass 2."""
    state = PipelineState(
        run_id="test-run-123",
        brd_raw_hash="hash",
        brd_name="test.txt",
        pass_number=2,
        alignment_memo=AlignmentMemo(
            directives=[
                AlignmentDirective(
                    agent_name="solution_architect",
                    directive="Use AWS SNS instead of Kafka",
                    reasoning="Simpler event broker preferred",
                    evidence="BRD Section 4",
                )
            ]
        ),
    )

    feedback = _feedback_for(state, "solution_architect")

    assert "ORCHESTRATOR EM ALIGNMENT DIRECTIVE" in feedback
    assert "Use AWS SNS instead of Kafka" in feedback
    assert "Simpler event broker preferred" in feedback


def test_route_after_decision_revising():
    """Verify that route_after_decision correctly routes to node_pass2_alignment if revising."""
    state = {
        "run_id": "test",
        "brd_raw_hash": "hash",
        "pipeline_status": "revising",
        "critic_output": {
            "run_id": "test",
            "revision_number": 1,
            "target_agents": ["solution_architect"],
            "groundedness": {
                "score": 4.0,
                "threshold": 3.75,
                "passed": True,
                "evidence": "",
                "improvement_suggestion": "",
            },
            "completeness": {
                "score": 5.0,
                "threshold": 5.0,
                "passed": True,
                "evidence": "",
                "improvement_suggestion": "",
            },
            "consistency": {
                "score": 5.0,
                "threshold": 5.0,
                "passed": True,
                "evidence": "",
                "improvement_suggestion": "",
            },
            "actionability": {
                "score": 4.0,
                "threshold": 4.0,
                "passed": True,
                "evidence": "",
                "improvement_suggestion": "",
            },
            "overall_score": 4.5,
            "badge": "green",
            "requires_revision": True,
        },
    }

    dest = route_after_decision(state)
    assert dest == "node_pass2_alignment"


def test_parallel_executor_threads():
    """Verify that _run_specialists_in_parallel calls specialist run methods and gathers results."""
    state = PipelineState(run_id="test-run-123", brd_raw_hash="hash", brd_name="test.txt")

    mock_arch_out = MagicMock()

    class MockArchitect:
        def run(self, ps, feedback):
            return mock_arch_out

    with patch("src.agents.pipeline.get_specialist") as mock_get:
        mock_get.return_value = MockArchitect

        results = _run_specialists_in_parallel(state, ["solution_architect"])

        assert "solution_architect" in results
        assert results["solution_architect"] == mock_arch_out


def test_arbitration_skipped_on_zero_conflicts():
    """Verify that node_arbitrate skips LLM arbitration when check_cross_agent_consistency finds no issues."""
    from src.agents.pipeline import node_arbitrate
    from src.core.models import PipelineState
    from src.core.pipeline_status import PipelineStatus

    state_obj = PipelineState(
        run_id="test-run-skip", brd_raw_hash="hash", brd_name="test.txt", pipeline_status=PipelineStatus.ARBITRATING
    )
    state_dict = state_obj.model_dump()
    state_dict["_brd_text"] = "Dummy BRD"

    with (
        patch("src.agents.critic.consistency_rules.check_cross_agent_consistency") as mock_check,
        patch("src.agents.orchestrator.OrchestratorAgent.arbitrate_drafts") as mock_arbitrate,
    ):
        # Scenario: 0 conflicts
        mock_check.return_value = []

        res = node_arbitrate(state_dict)

        # Verify arbitrate_drafts LLM call was bypassed
        mock_arbitrate.assert_not_called()

        # Verify alignment memo is set to empty directives list
        memo = res.get("alignment_memo")
        assert memo is not None
        assert memo["directives"] == []
        # Verify revision targets are empty
        assert res.get("_revision_targets") == []
