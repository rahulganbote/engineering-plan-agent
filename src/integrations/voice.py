"""
src/integrations/voice.py
═════════════════════════
ElevenLabs voice integration for human-in-the-loop (HITL) approval.
This module provides a basic hook to initialize a conversational voice agent.
"""

from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)

def get_voice_agent_config() -> dict:
    """
    Returns configuration to initialize the ElevenLabs conversational agent.
    If credentials are not set, returns an empty configuration.
    """
    if not settings.elevenlabs_api_key or not settings.elevenlabs_agent_id:
        log.warning("ElevenLabs credentials not configured.")
        return {"enabled": False, "detail": "ElevenLabs credentials missing."}
    
    # In a full implementation, this could return a token or signed URL
    # for the frontend to initialize the conversational AI widget.
    return {
        "enabled": True,
        "agent_id": settings.elevenlabs_agent_id,
        "api_key_snippet": settings.elevenlabs_api_key[:4] + "***",
        "detail": "Voice agent configured."
    }
