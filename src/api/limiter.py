"""
src/api/limiter.py
══════════════════
Rate limiting configuration and Limiter instance.
"""

from __future__ import annotations

import os

from fastapi import Request
from slowapi import Limiter

from src.core.config import settings


# Centralized exemption helper
def is_rate_limit_exempt(email: str | None) -> bool:
    if not email:
        return False
    if not settings.rate_limit_exempt_emails:
        return False
    exempt_list = [e.strip().lower() for e in settings.rate_limit_exempt_emails.split(",") if e.strip()]
    return email.lower() in exempt_list


# Sentinel identity for verified voice-agent calls. Every call that presents a
# valid VOICE_WEBHOOK_SECRET Bearer token maps to this single key, so voice
# calls share one bucket instead of competing with per-user session limits.
# This is effective exemption for the demo: a single trusted webhook secret
# authenticates all voice traffic, and 20/hour of shared bucket is well over
# any legitimate demo volume.
_VOICE_AGENT_KEY = "voice-agent-verified"


def _is_verified_voice_agent(request: Request) -> bool:
    """Reuses the same Bearer-token check that verify_run_ownership does, but
    at rate-limiter time (before the route handler runs). Mirrors dependencies.py
    exactly to avoid split-brain: any change to auth logic must update both."""
    if not settings.voice_webhook_secret:
        return False
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ", 1)[1].strip()
    valid_secrets = [s.strip() for s in settings.voice_webhook_secret.split(",") if s.strip()]
    return token in valid_secrets


def get_user_identifier(request: Request) -> str:
    """
    Ties rate limits to the authenticated user's email if available, falling
    back to a proxy-safe remote IP resolution. Verified voice-webhook callers
    map to a distinct shared bucket so they don't compete with human users.
    """
    if _is_verified_voice_agent(request):
        return _VOICE_AGENT_KEY

    if request.session.get("is_guest"):
        ip = request.client.host if request.client else (request.headers.get("x-forwarded-for") or "unknown-client-ip")
        return f"guest-ip:{ip}"

    email = request.session.get("auth_email")
    if email:
        return email

    # Safe check in case request.client is None behind GCP Load Balancer
    if request.client:
        return request.client.host
    return request.headers.get("x-forwarded-for") or "unknown-client-ip"


REDIS_URL = (os.environ.get("REDIS_URL") or "").strip()
if REDIS_URL:
    # in_memory_fallback_enabled: if the shared Redis backend becomes
    # unreachable (outage, DNS blip, etc.), slowapi catches the storage
    # exception and transparently retries against local in-memory storage
    # instead of letting the exception propagate as a 500. This trades away
    # cross-instance quota sync during the outage (each Cloud Run instance
    # reverts to its own local counter) in exchange for /run-pipeline and
    # /approve staying up - degraded rate-limit accuracy beats a hard outage.
    limiter = Limiter(key_func=get_user_identifier, storage_uri=REDIS_URL, in_memory_fallback_enabled=True)
else:
    limiter = Limiter(key_func=get_user_identifier)
