"""
src/security/google_auth.py
═══════════════════════════
Google Sign-In configuration for the API backend.

Provides environment validation and URL helpers for the OAuth flow.
"""

from __future__ import annotations

import os

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def is_configured() -> bool:
    """True only when all 3 required OAuth env vars are present."""
    return bool(
        _env("GOOGLE_OAUTH_CLIENT_ID") and _env("GOOGLE_OAUTH_CLIENT_SECRET") and _env("GOOGLE_OAUTH_REDIRECT_URI")
    )


def _allowed_emails() -> list[str]:
    raw = _env("GOOGLE_OAUTH_ALLOWED_EMAILS")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]
