"""
src/api/models.py
═════════════════
Pydantic validation schemas for EM Copilot endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator, model_validator


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class ApprovalRequest(BaseModel):
    """
    Defensive input model for /approve.

    Three pre-validators normalize voice-agent quirks so the endpoint never
    422s on inputs the LLM-driven ElevenLabs agent typically emits:

      1. `_unwrap_params`     - accepts either flat `{decision, …}` or nested
                                `{params: {decision, …}}` (some webhook configs)
      2. `_normalize_decision` - maps verb forms ("approve" → "approved",
                                "reject" → "rejected") to enum values
      3. `_coerce_rating_to_int` - accepts float em_rating (e.g. `5.0`, `4.5`)
                                and rounds to the nearest int
    """

    decision: str  # "approved" | "rejected" (normalized by validator)
    reviewer: str = "Engineering Manager"
    notes: str = ""
    em_rating: int = 0  # 1-5 - EM rating for Method 5 eval tracking
    email: str = ""

    @model_validator(mode="before")
    @classmethod
    def _unwrap_params(cls, values):
        """
        Some ElevenLabs webhook configurations wrap arguments as
        `{"params": {...}}`. Accept that shape transparently by unwrapping.
        Top-level keys outside `params` are preserved (rare but possible).
        """
        if isinstance(values, dict) and isinstance(values.get("params"), dict):
            unwrapped = dict(values["params"])
            for k, v in values.items():
                if k != "params" and k not in unwrapped:
                    unwrapped[k] = v
            return unwrapped
        return values

    @field_validator("decision", mode="before")
    @classmethod
    def _normalize_decision(cls, v):
        """
        Voice agents sometimes emit verb forms ("approve" / "reject") instead
        of the enum values ("approved" / "rejected"). Normalize before the
        endpoint constructs the HITLDecision enum.
        """
        if not isinstance(v, str):
            return v
        s = v.strip().lower()
        if s in ("approve", "approved"):
            return "approved"
        if s in ("reject", "rejected"):
            return "rejected"
        return s

    @field_validator("em_rating", mode="before")
    @classmethod
    def _coerce_rating_to_int(cls, v):
        """
        Voice LLMs frequently emit numeric ratings as floats ("4.5", "5.0").
        Round to nearest int. Non-numeric or None values pass through unchanged
        for the default Pydantic int-coercion / default-value path.
        """
        if isinstance(v, float):
            return int(round(v))
        return v


class ApprovalResponse(BaseModel):
    run_id: str
    decision: str
    message: str
    sheet_url: str | None = None
    export_status: str | None = None  # "ok" | "local_fallback" | "failed"
    export_mode: str | None = None  # "sheets" | "local"
    export_detail: str | None = None  # human-friendly summary
    # ── Jira push (additive - never blocks approval) ─────────────────────────
    jira_url: str | None = None  # browse URL on success
    jira_status: str | None = None  # "jira" | "skipped" | "failed"
    jira_detail: str | None = None
    jira_issue_key: str | None = None  # e.g. "EMCP-42"
    pipeline_status: str | None = None
    rejection_count: int = 0


class ArtifactSummary(BaseModel):
    run_id: str
    badge: str
    overall_score: float
    critic_scores_history: list[dict]
    has_plan: bool
    has_schedule: bool
    has_architecture: bool
    has_poc: bool
    has_tech_stack: bool
    pipeline_status: str


class LogDownloadRequest(BaseModel):
    email: str


class FeedbackRequest(BaseModel):
    area: str
    category: str
    description: str
    include_transcript: bool
    workspace: str
    diagnostic_logs: dict
    sender: str
    run_id: str | None = None
