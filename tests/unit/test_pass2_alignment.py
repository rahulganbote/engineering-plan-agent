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
