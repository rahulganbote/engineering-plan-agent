"""
src/api/routes/auth.py
══════════════════════
Google OAuth and Sign-In API routes.
"""

from __future__ import annotations

import os as _os
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from src.api.consent import CURRENT_TERMS_VERSION, has_consented

router = APIRouter(tags=["auth"])


def get_fastapi_redirect_uri(request: Request) -> str:
    env_uri = _os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "")
    if env_uri:
        if not env_uri.endswith("/auth/callback") and not env_uri.endswith("/auth/callback/"):
            env_uri = env_uri.rstrip("/") + "/auth/callback"
        return env_uri

    host = request.headers.get("host", "localhost:8000")
    proto = "https"
    if "localhost" in host or "127.0.0.1" in host or "0.0.0.0" in host:
        proto = "http"
    return f"{proto}://{host}/auth/callback"


def exchange_code_for_user(code: str, redirect_uri: str) -> tuple[bool, dict | str]:
    try:
        from src.security.google_auth import GOOGLE_TOKEN_URL, GOOGLE_USERINFO_URL, _allowed_emails, _env

        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": _env("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": _env("GOOGLE_OAUTH_CLIENT_SECRET"),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if not token_resp.ok:
            return False, f"Google token exchange failed (HTTP {token_resp.status_code})."

        access_token = token_resp.json().get("access_token")
        if not access_token:
            return False, "Google returned no access token."

        user_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not user_resp.ok:
            return False, "Failed to fetch your Google profile."

        info = user_resp.json()
        email = (info.get("email") or "").lower()
        if not email:
            return False, "No email address was returned by Google."

        allowed = _allowed_emails()
        if allowed and email not in allowed:
            return False, f"Sorry - {email} is not on the allowed-users list."

        return True, {"email": email, "name": info.get("name", "")}
    except Exception as e:
        return False, f"Auth callback error: {str(e)}"


@router.post("/auth/guest")
async def continue_as_guest(request: Request):
    import uuid

    request.session.pop("local_logout", None)
    request.session["is_guest"] = True
    request.session["auth_email"] = f"guest-{uuid.uuid4().hex[:12]}@guest.local"
    request.session["auth_name"] = "Guest"
    return {
        "authenticated": True,
        "is_guest": True,
        "email": request.session["auth_email"],
        "name": "Guest",
    }


@router.get("/auth/me")
async def get_current_user(request: Request):
    from src.security.google_auth import is_configured

    is_guest = bool(request.session.get("is_guest"))

    if not is_configured():
        if request.session.get("local_logout"):
            return {"authenticated": False}
        dev_email = request.session.get("auth_email") or "local-dev@example.com"
        return {
            "authenticated": True,
            "is_guest": is_guest,
            "email": dev_email,
            "name": request.session.get("auth_name") or "Local Developer",
            "message": "Auth disabled (local dev mode)",
            "has_consented": (not is_guest) and has_consented(dev_email),
            "terms_version": CURRENT_TERMS_VERSION,
        }

    email = request.session.get("auth_email")
    if email:
        return {
            "authenticated": True,
            "is_guest": is_guest,
            "email": email,
            "name": request.session.get("auth_name", ""),
            "has_consented": (not is_guest) and has_consented(email),
            "terms_version": CURRENT_TERMS_VERSION,
        }
    return {"authenticated": False}


@router.get("/auth/login")
async def login(request: Request):
    from src.security.google_auth import GOOGLE_AUTH_URL, _env, is_configured

    if not is_configured():
        request.session.pop("local_logout", None)
        request.session.pop("is_guest", None)
        request.session["auth_email"] = "local-dev@example.com"
        request.session["auth_name"] = "Local Developer"
        return RedirectResponse(url="/")

    redirect_uri = get_fastapi_redirect_uri(request)
    params = {
        "client_id": _env("GOOGLE_OAUTH_CLIENT_ID"),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = None, error: str = None):
    if error:
        raise HTTPException(status_code=400, detail=f"Google authentication error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    redirect_uri = get_fastapi_redirect_uri(request)
    success, result = exchange_code_for_user(code, redirect_uri)
    if not success:
        raise HTTPException(status_code=400, detail=str(result))

    request.session.pop("is_guest", None)
    request.session["auth_email"] = result["email"]
    request.session["auth_name"] = result["name"]
    return RedirectResponse(url="/")


@router.get("/auth/logout")
async def logout(request: Request):
    request.session.clear()
    from src.security.google_auth import is_configured

    if not is_configured():
        request.session["local_logout"] = True
    return RedirectResponse(url="/")
