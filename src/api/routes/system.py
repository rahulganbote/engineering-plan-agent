"""
src/api/routes/system.py
════════════════════════
System status, configuration, and diagnostics endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from src.api.models import FeedbackRequest
from src.core.config import settings
from src.integrations.email import send_feedback_email

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.1.0"}


@router.get("/debug/config-status")
async def config_status():
    """
    Boolean-only diagnostic for the voice webhook secret. Confirms whether the
    VOICE_WEBHOOK_SECRET env var is populated at runtime in this Cloud Run
    revision. NEVER returns the value itself - only presence and length so a
    misconfigured deploy surfaces immediately without leaking the secret.

    Curl in production after any env-var change:
      curl https://emcopilot.ai/debug/config-status
    A length of 0 means the env var isn't reaching the process (wrong tab,
    revision not rolled forward, or typo in the variable name).
    """
    return {
        "voice_webhook_secret_set": bool(settings.voice_webhook_secret),
        "voice_webhook_secret_len": len(settings.voice_webhook_secret),
        "voice_webhook_secret_count": len([s for s in settings.voice_webhook_secret.split(",") if s.strip()]),
    }


@router.get("/api/config")
async def public_config():
    """
    Public runtime config - exposed to frontend at boot. NO secrets.
    Exposes ElevenLabs voice-assisted review agent ID if configured.
    """
    return {
        "elevenlabs_agent_id": settings.elevenlabs_agent_id or "",
    }


@router.get("/api/providers")
async def list_providers():
    """
    Return the availability of each LLM model family based on which API keys are
    configured on this deployment. Used by the React UI to auto-disable
    unavailable families in the model-selection dropdown.
    """
    return {
        "openai": {
            "available": bool(settings.openai_api_key),
            "reason": "API key not configured" if not settings.openai_api_key else None,
        },
        "anthropic": {
            "available": bool(settings.anthropic_api_key),
            "reason": "ANTHROPIC_API_KEY not set on this deployment" if not settings.anthropic_api_key else None,
        },
        "llama": {
            "available": False,
            "reason": "Coming soon",
        },
        "mistral": {
            "available": False,
            "reason": "Coming soon",
        },
    }


@router.post("/api/feedback")
async def submit_feedback(payload: FeedbackRequest, background_tasks: BackgroundTasks):
    """
    Append user feedback to a local logs/feedback.jsonl file and send an email copy.
    """
    import json
    import time
    from pathlib import Path

    feedback_data = payload.model_dump()
    feedback_data["timestamp_epoch"] = time.time()

    feedback_dir = Path("logs")
    feedback_dir.mkdir(exist_ok=True)
    feedback_file = feedback_dir / "feedback.jsonl"

    with open(feedback_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(feedback_data) + "\n")

    # Send copy via email copy background worker
    background_tasks.add_task(send_feedback_email, feedback_data)

    return {"status": "ok", "message": "Feedback submitted successfully"}
