"""
src/api/dependencies.py
═══════════════════════
Authentication and tenancy validation dependencies.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from src.api.state import _run_owner, _runs
from src.core.config import settings
from src.core.logger import get_logger

log = get_logger(__name__)


def get_current_user_email(request: Request) -> str:
    email = request.session.get("auth_email")
    if email:
        return email

    from src.security.google_auth import is_configured

    if not is_configured():
        as_user = request.query_params.get("as")
        if as_user:
            return as_user.strip().lower()
        return "local-dev@example.com"

    raise HTTPException(status_code=401, detail="Not authenticated")


def verify_run_ownership(run_id: str, request: Request, allow_voice_agent: bool = False) -> None:
    # 1. Look up run owner
    owner_email = _run_owner.get(run_id)
    if not owner_email:
        # Fallback to check if run is registered
        state = _runs.get(run_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        owner_email = "local-dev@example.com"

    # 2. Check if voice agent is authorized (via Bearer token webhook secret)
    #
    # Emits structured audit lines so the ElevenLabs webhook path is debuggable
    # from Cloud Run logs alone. Only lengths and counts are logged - never the
    # token or the configured secret. If auth fails we still fall through to the
    # session check below, so this only observes; it never changes behavior.
    if allow_voice_agent and settings.voice_webhook_secret:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            valid_secrets = [s.strip() for s in settings.voice_webhook_secret.split(",") if s.strip()]
            if token in valid_secrets:
                log.info(f"[{run_id}] voice-agent auth OK (token_len={len(token)})")
                return  # Authorized voice agent bypass
            log.warning(f"[{run_id}] voice-agent auth FAILED: token_len={len(token)} valid_count={len(valid_secrets)}")
        else:
            log.warning(f"[{run_id}] voice call missing Bearer header (got: {auth_header[:20]!r})")

    # 3. Check session user
    current_user = get_current_user_email(request)
    if owner_email != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this run.")
