from enum import StrEnum


class PipelineStatus(StrEnum):
    IDLE = "idle"
    SECURITY_CHECK = "security_check"
    RUNNING = "running"
    DRAFTING = "drafting"
    ARBITRATING = "arbitrating"
    ALIGNING = "aligning"
    ORCHESTRATOR_PARSING = "orchestrator_parsing"
    EVALUATING = "evaluating"
    REVISING = "revising"
    AWAITING_HITL = "awaiting_hitl"
    EXPORTING = "exporting"
    EXPORTED = "exported"
    REJECTED = "rejected"
    EXPORT_FAILED = "export_failed"
    ERROR = "error"
    CANCELED = "canceled"  # user aborted via POST /runs/{run_id}/cancel
