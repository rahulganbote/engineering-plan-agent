"""
src/security/google_auth.py
═══════════════════════════
Optional Google Sign-In gate for the Streamlit UI.

Purpose
───────
Block bots and random visitors from running the (LLM-costly) pipeline on the
public HuggingFace Space, while keeping local development friction-free.

Behaviour
─────────
• If GOOGLE_OAUTH_CLIENT_ID / SECRET / REDIRECT_URI are ALL set, the UI is gated
  behind a "Continue with Google" button. Users must sign in before they can
  upload a BRD or run the pipeline.
• If any of those env vars are unset (e.g. local dev), the gate is a no-op.

Setup
─────
Add as HuggingFace Space *Secrets* (Settings → Variables and secrets):

    GOOGLE_OAUTH_CLIENT_ID       <Google Cloud OAuth Client ID — ends in .apps.googleusercontent.com>
    GOOGLE_OAUTH_CLIENT_SECRET   <Google Cloud OAuth Client Secret>
    GOOGLE_OAUTH_REDIRECT_URI    https://<owner>-<space>.hf.space/
    GOOGLE_OAUTH_ALLOWED_EMAILS  (optional) comma-separated allowlist; empty = any Google account

Google Cloud Console one-time setup:
    1. https://console.cloud.google.com/  →  APIs & Services  →  Credentials
    2. Create OAuth client ID (Application type: Web application)
    3. Authorized redirect URIs: add EXACTLY the HF Space URL with trailing slash,
       e.g. https://rganbote-em-copilot.hf.space/
    4. Copy Client ID + Client Secret into the HF Space Secrets above.
"""

from __future__ import annotations

import os
from typing import Tuple
from urllib.parse import urlencode

import requests
import streamlit as st


GOOGLE_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL    = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


# ── Config helpers ────────────────────────────────────────────────────────────

def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def is_configured() -> bool:
    """True only when all 3 required OAuth env vars are present."""
    return bool(
        _env("GOOGLE_OAUTH_CLIENT_ID")
        and _env("GOOGLE_OAUTH_CLIENT_SECRET")
        and _env("GOOGLE_OAUTH_REDIRECT_URI")
    )


def _allowed_emails() -> list[str]:
    raw = _env("GOOGLE_OAUTH_ALLOWED_EMAILS")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]


# ── Session helpers ───────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_email"))


def get_user_email() -> str:
    return st.session_state.get("auth_email", "")


def get_user_name() -> str:
    return st.session_state.get("auth_name", "")


def sign_out() -> None:
    for k in ("auth_email", "auth_name"):
        st.session_state.pop(k, None)


# ── OAuth URL builders ────────────────────────────────────────────────────────

def get_login_url(state: str = "same_tab") -> str:
    """Build the Google OAuth consent URL."""
    params = {
        "client_id":     _env("GOOGLE_OAUTH_CLIENT_ID"),
        "redirect_uri":  _env("GOOGLE_OAUTH_REDIRECT_URI"),
        "response_type": "code",
        "scope":         "openid email profile",
        "access_type":   "online",
        "prompt":        "select_account",
        "state":         state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def get_auth_target() -> str:
    """
    Determine the anchor redirect target context.
    HuggingFace Spaces embed Streamlit in a sandboxed iframe without allow-top-navigation.
    Hence, target="_top" or "_self" is blocked (nothing happens on click).
    We MUST use target="_blank" (new tab) inside HuggingFace Spaces.
    On local or Google Cloud Run (no iframe), target="_top" is used for same-tab redirect.
    """
    if os.environ.get("SPACE_ID"):
        return "_blank"
    return "_top"


def _get_auth_button_html(target: str) -> str:
    state_param = "popup" if target == "_blank" else "same_tab"
    url = get_login_url(state=state_param)
    
    # We use window.parent.open for popup target to escape iframe sandbox and ensure script-closeable window
    onclick_js = ""
    if target == "_blank":
        onclick_js = f"onclick=\"try {{ window.parent.open('{url}', '_blank'); }} catch(e) {{ window.open('{url}', '_blank'); }} return false;\""
        
    return f"""
    <style>
    body {{
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        background-color: transparent !important;
    }}
    .g-signin-btn {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: #ffffff !important;
        color: #3c4043 !important;
        padding: 8px 16px !important;
        border-radius: 4px !important;
        font-weight: 500 !important;
        text-decoration: none !important;
        font-size: 14px !important;
        border: 1px solid #dadce0 !important;
        line-height: 1.5 !important;
        font-family: 'Roboto', sans-serif !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08) !important;
        transition: background-color 0.2s !important;
        cursor: pointer !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}
    .g-signin-btn:hover {{
        background-color: #f8f9fa !important;
        border-color: #c6c6c6 !important;
    }}
    .g-signin-btn span {{
        color: #3c4043 !important;
        text-decoration: none !important;
        font-weight: 500 !important;
    }}
    </style>
    <a href="{url}" target="{target}" rel="opener" {onclick_js} class="g-signin-btn">
        <svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="18px" height="18px" viewBox="0 0 48 48" style="margin-right: 10px; vertical-align: middle;">
          <g>
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"></path>
            <path fill="#4285F4" d="M46.5 24c0-1.55-.15-3.24-.47-4.77H24v9.03h12.75c-.55 2.87-2.22 5.37-4.72 7.03l7.3 5.66c4.27-3.92 6.72-9.74 6.72-16.92z"></path>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.3-5.66c-2.11 1.41-4.8 2.32-8.59 2.32-6.26 0-11.57-4.22-13.46-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
            <path fill="none" d="M0 0h48v48H0z"></path>
          </g>
        </svg>
        <span>Continue with Google</span>
    </a>
    """


# ── OAuth callback handler ────────────────────────────────────────────────────

def _process_callback(code: str) -> Tuple[bool, str]:
    """
    Exchange auth code for tokens, fetch user info, validate allowlist.
    Sets st.session_state on success. Returns (ok, error_message).
    """
    try:
        # Exchange auth code for tokens
        token_resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     _env("GOOGLE_OAUTH_CLIENT_ID"),
                "client_secret": _env("GOOGLE_OAUTH_CLIENT_SECRET"),
                "redirect_uri":  _env("GOOGLE_OAUTH_REDIRECT_URI"),
                "grant_type":    "authorization_code",
            },
            timeout=10,
        )
        if not token_resp.ok:
            return False, f"Google token exchange failed (HTTP {token_resp.status_code})."

        access_token = token_resp.json().get("access_token")
        if not access_token:
            return False, "Google returned no access token."

        # Fetch user info
        user_resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not user_resp.ok:
            return False, "Failed to fetch your Google profile."

        info  = user_resp.json()
        email = (info.get("email") or "").lower()
        if not email:
            return False, "No email address was returned by Google."

        # Optional allowlist
        allowed = _allowed_emails()
        if allowed and email not in allowed:
            return False, f"Sorry — {email} is not on the allowed-users list for this Space."

        st.session_state["auth_email"] = email
        st.session_state["auth_name"]  = info.get("name", "")
        return True, ""

    except requests.RequestException as e:
        return False, f"Network error talking to Google: {type(e).__name__}"
    except Exception as e:
        return False, f"Unexpected sign-in error: {type(e).__name__}"


# ── Login page ────────────────────────────────────────────────────────────────

def _render_login_page() -> None:
    st.markdown("# 🔒 Sign in — EM Copilot")
    st.markdown(
        "This Space requires sign-in to keep usage costs predictable and "
        "block automated traffic."
    )
    st.markdown("")  # spacer
    # Render Google Sign-in button inside iframe to support window.parent.open
    # pyrefly: ignore [missing-import]
    import streamlit.components.v1 as components
    components.html(_get_auth_button_html(get_auth_target()), height=55)
    st.caption(
        "By continuing you agree to fair use of this demo Space. "
        "Your email is used only to authorise access; nothing else is stored."
    )


# ── Public entry points ───────────────────────────────────────────────────────
#
# Auth pattern (lighter-touch than a hard gate):
#
#   1. Call process_callback() at the TOP of main() — handles the return-from-
#      Google flow but never blocks the page.
#   2. Render the rest of the page (description, layout) for everyone.
#   3. At each cost-incurring action (file upload, pipeline start), call
#      render_signin_required() *in place of* the action's UI when the user
#      is not signed in. The page renders, but they cannot trigger work.
#   4. Call render_signed_in_chip() inside st.sidebar to show "Signed in / Sign
#      out" when the user IS authenticated.


def _render_oauth_listener() -> None:
    """
    Render a hidden iframe component in the first tab to listen for the OAuth code
    broadcasted by the popup tab, then reload the parent page to complete login.
    """
    # pyrefly: ignore [missing-import]
    import streamlit.components.v1 as components
    js_listener = """
    <script>
    (function() {
        console.log("OAuth Listener: setting up BroadcastChannel & storage listeners...");
        
        // 1. BroadcastChannel listener (primary)
        try {
            const bc = new BroadcastChannel("oauth_channel");
            bc.onmessage = function(event) {
                console.log("OAuth Listener: received BroadcastChannel message", event.data);
                if (event.data && event.data.code) {
                    window.parent.location.href = window.parent.location.origin + window.parent.location.pathname + "?code=" + event.data.code + "&state=opener";
                }
            };
        } catch(e) {
            console.warn("OAuth Listener: BroadcastChannel setup failed", e);
        }
        
        // 2. Storage listener (cross-browser fallback)
        window.addEventListener("storage", function(event) {
            if (event.key === "oauth_code" && event.newValue) {
                console.log("OAuth Listener: received storage event for code");
                window.parent.location.href = window.parent.location.origin + window.parent.location.pathname + "?code=" + event.newValue + "&state=opener";
                try {
                    localStorage.removeItem("oauth_code");
                } catch(err) {}
            }
        });
    })();
    </script>
    """
    components.html(js_listener, height=0, width=0)


def process_callback() -> None:
    """
    Handle the return-from-Google flow if the URL has ?code=…  Sets session
    state on success. Never blocks page rendering — call at the very top of
    main(). No-op when not configured or no callback in progress.
    """
    if not is_configured():
        return

    # Set up cross-tab listener on the primary tab so it receives code from popup
    if not is_authenticated():
        _render_oauth_listener()

    qp = st.query_params
    if "code" not in qp or is_authenticated():
        return
    code = qp.get("code")
    if isinstance(code, list):
        code = code[0] if code else ""
    if not code:
        return

    # On HF (target=_blank), Google redirects back to a popup tab with state=popup.
    # The popup must forward the code to the listener in the original tab via BroadcastChannel.
    state_val = qp.get("state")
    if isinstance(state_val, list):
        state_val = state_val[0] if state_val else ""

    if state_val == "popup":
        # pyrefly: ignore [missing-import]
        import streamlit.components.v1 as components
        
        # Render a premium styled success card to the user in the popup tab
        st.markdown(
            """
            <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
                <div style="background: white; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center; max-width: 400px; width: 100%; border: 1px solid #eaeaea;">
                    <div style="font-size: 56px; margin-bottom: 20px;">🧭</div>
                    <h2 style="color: #111827; margin-bottom: 12px; font-weight: 600; font-size: 24px; line-height: 1.2;">Sign-in Successful!</h2>
                    <p style="color: #6b7280; font-size: 14px; line-height: 1.6; margin-bottom: 28px;">
                        Your session has been authorized. You can close this window now and return to the main EM Copilot tab.
                    </p>
                    <button onclick="try { window.parent.close(); } catch(e) {} window.close();" style="background-color: #ff4b4b; color: white; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 14px; transition: background-color 0.2s; width: 100%;">
                        Close Window
                    </button>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        js_code = """
        <script>
        (function() {
            try {
                console.log("Iframe: injecting redirection script into parent window...");
                const parentDoc = window.parent.document;
                const script = parentDoc.createElement("script");
                script.textContent = `
                    (function() {
                        try {
                            const urlParams = new URLSearchParams(window.location.search);
                            const code = urlParams.get("code");
                            if (code) {
                                if (window.opener) {
                                    console.log("Top-level: Redirecting original window...");
                                    window.opener.location.href = window.opener.location.origin + window.opener.location.pathname + "?code=" + code + "&state=opener";
                                    
                                    // Auto-close the popup tab after a small delay
                                    setTimeout(function() {
                                        console.log("Top-level: closing popup window...");
                                        window.close();
                                    }, 400);
                                } else {
                                    console.warn("Top-level: window.opener is null. Falling back to same tab redirect.");
                                    window.location.href = window.location.origin + window.location.pathname + "?code=" + code + "&state=same_tab";
                                }
                            }
                        } catch(e) {
                            console.error("Top-level OAuth script failed:", e);
                        }
                    })();
                `;
                parentDoc.body.appendChild(script);
            } catch(e) {
                console.error("Iframe script injection failed:", e);
                
                // Fallback inside iframe using postMessage/BroadcastChannel just in case DOM injection is blocked
                try {
                    const urlParams = new URLSearchParams(window.location.search);
                    const code = urlParams.get("code");
                    if (code) {
                        const bc = new BroadcastChannel("oauth_channel");
                        bc.postMessage({ type: "oauth", code: code });
                        localStorage.setItem("oauth_code", code);
                    }
                } catch(err) {}
            }
        })();
        </script>
        """
        components.html(js_code, height=0, width=0)
        st.stop()

    ok, err = _process_callback(code)
    if ok:
        # Strip ?code=… so a refresh doesn't replay (Google codes are one-shot)
        st.query_params.clear()
        st.rerun()
    elif err:
        # Non-blocking: surface the error but let the page render
        st.toast(err, icon="🚫")


def render_signin_required(message: str = "") -> None:
    """
    Inline sign-in prompt. Use this anywhere you want to gate an action
    (file upload, pipeline run, etc.) without blocking the rest of the page.
    Renders nothing when auth isn't configured (local dev).
    """
    if not is_configured() or is_authenticated():
        return
    st.info("🔒 " + (message or "Sign in with Google to continue."))
    # Render Google Sign-in button inside iframe to support window.parent.open
    # pyrefly: ignore [missing-import]
    import streamlit.components.v1 as components
    components.html(_get_auth_button_html(get_auth_target()), height=55)
    st.caption(
        "Sign-in keeps LLM-token costs predictable on this public Space. "
        "Your email is used only to authorise access."
    )


def render_signed_in_chip() -> None:
    """
    Show a 'Signed in as <email> / Sign out' chip in the current container
    (call inside `with st.sidebar:`). No-op unless signed in.
    """
    if not is_configured() or not is_authenticated():
        return
    st.caption(f"✓ Signed in: {get_user_email()}")
    if st.button("Sign out", use_container_width=True, key="auth_signout"):
        sign_out()
        st.rerun()
