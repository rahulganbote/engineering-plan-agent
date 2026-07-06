from src.core.pipeline_status import PipelineStatus


def test_pipeline_status_values_are_stable():
    """
    The set of valid pipeline_status strings is a public contract.
    Any addition or rename must update this test intentionally.
    """
    assert set(PipelineStatus) == {
        "idle",
        "security_check",
        "running",
        "drafting",
        "arbitrating",
        "aligning",
        "specialist_executing",
        "evaluating",
        "revising",
        "awaiting_hitl",
        "exported",
        "rejected",
        "export_failed",
        "error",
        "canceled",
    }
