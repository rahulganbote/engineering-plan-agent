from enum import StrEnum


class PipelineStatus(StrEnum):
    IDLE = "idle"
    SECURITY_CHECK = "security_check"
    RUNNING = "running"
    SPECIALIST_EXECUTING = "specialist_executing"
    EVALUATING = "evaluating"
    REVISING = "revising"
    AWAITING_HITL = "awaiting_hitl"
    EXPORTED = "exported"
    REJECTED = "rejected"
    EXPORT_FAILED = "export_failed"
    ERROR = "error"
