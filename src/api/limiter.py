"""
src/api/limiter.py
══════════════════
Rate limiting configuration and Limiter instance.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter


def get_user_identifier(request: Request) -> str:
    """
    Ties rate limits to the authenticated user's email if available,
    falling back to a proxy-safe remote IP resolution.
    """
    email = request.session.get("auth_email")
    if email:
        return email

    # Safe check in case request.client is None behind GCP Load Balancer
    if request.client:
        return request.client.host
    return request.headers.get("x-forwarded-for") or "unknown-client-ip"


limiter = Limiter(key_func=get_user_identifier)
