"""
src/api/dependencies.py
═══════════════════════
Authentication and tenancy validation dependencies.
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from src.api.state import _run_owner, _runs
from src.core.config import settings


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
    if allow_voice_agent and settings.voice_webhook_secret:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
            valid_secrets = [s.strip() for s in settings.voice_webhook_secret.split(",") if s.strip()]
            if token in valid_secrets:
                return  # Authorized voice agent bypass

    # 3. Check session user
    current_user = get_current_user_email(request)
    if owner_email != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this run.")
