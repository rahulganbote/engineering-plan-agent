"""
src/api/limiter.py
══════════════════
Rate limiting configuration and Limiter instance.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_identifier(request: Request) -> str:
    """
    Ties rate limits to the authenticated user's email if available,
    falling back to the client's remote IP address.
    """
    return request.session.get("auth_email") or get_remote_address(request)


limiter = Limiter(key_func=get_user_identifier)
