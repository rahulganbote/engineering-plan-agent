from enum import StrEnum


class PipelineStatus(StrEnum):
    # Transient pre-run state - set as PipelineState's default at construction,
    # immediately overwritten by SECURITY_CHECK before the state is ever
    # persisted or transmitted (see src/api/tasks.py:_run_pipeline_task).
    # Never actually observed by a client; kept as a real member (rather than
    # a bare string default) so pipeline_status's type is enforceable.
    INITIALIZING = "initializing"
    IDLE = "idle"
    SECURITY_CHECK = "security_check"
    RUNNING = "running"
    DRAFTING = "drafting"
    ARBITRATING = "arbitrating"
    ALIGNING = "aligning"
    ORCHESTRATOR_ROUTING = "orchestrator_routing"
    EVALUATING = "evaluating"
    REVISING = "revising"
    AWAITING_HITL = "awaiting_hitl"
    EXPORTING = "exporting"
    EXPORTED = "exported"
    REJECTED = "rejected"
    EXPORT_FAILED = "export_failed"
    ERROR = "error"
    CANCELED = "canceled"  # user aborted via POST /runs/{run_id}/cancel
