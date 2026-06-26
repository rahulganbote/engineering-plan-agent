"""
src/api/routes/system.py
════════════════════════
System status, configuration, and diagnostics endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.core.config import settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.1.0"}


@router.get("/api/config")
async def public_config():
    """
    Public runtime config — exposed to frontend at boot. NO secrets.
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
