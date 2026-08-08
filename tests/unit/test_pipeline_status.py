from src.core.pipeline_status import PipelineStatus


def test_pipeline_status_values_are_stable():
    """
    The set of valid pipeline_status strings is a public contract.
    Any addition or rename must update this test intentionally.
    """
    assert set(PipelineStatus) == {
        "initializing",
        "idle",
        "security_check",
        "running",
        "drafting",
        "arbitrating",
        "aligning",
        "orchestrator_routing",
        "evaluating",
        "revising",
        "awaiting_hitl",
        "exporting",
        "exported",
        "rejected",
        "export_failed",
        "error",
        "canceled",
    }
