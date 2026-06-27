"""
src/integrations/slack.py
═════════════════════════
Sends a Slack alert when a pipeline run ends in error.

One-way notifications via a Slack **Incoming Webhook** — no bot token, no OAuth
scopes, no Slack SDK dependency (just `requests`, already in requirements).

Setup (one-time)
────────────────
    1. Create an Incoming Webhook for the target channel:
       https://api.slack.com/messaging/webhooks
    2. Add the URL to secrets/.env:
       SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000/B00000/XXXXXXXX

If SLACK_WEBHOOK_URL is unset the alert is skipped gracefully — a missing or
broken Slack webhook must never affect the pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)

_SLACK_TIMEOUT_SEC = 10


def _slack_status() -> tuple[bool, str]:
    """Check whether a usable Slack webhook is configured."""
    url = (settings.slack_webhook_url or "").strip()
    if not url:
        return False, "SLACK_WEBHOOK_URL not set"
    if not url.startswith("https://hooks.slack.com/"):
        return False, "SLACK_WEBHOOK_URL is not a Slack incoming-webhook URL"
    return True, ""


def _post_to_slack(payload: dict[str, Any]) -> tuple[bool, str]:
    """POST a message payload to the configured webhook. Never raises."""
    try:
        resp = requests.post(
            settings.slack_webhook_url.strip(),
            json=payload,
            timeout=_SLACK_TIMEOUT_SEC,
        )
    except requests.RequestException as e:
        return False, f"Slack request error: {type(e).__name__}: {str(e)[:160]}"
    if resp.status_code == 200 and resp.text.strip() == "ok":
        return True, "delivered"
    return False, f"Slack returned HTTP {resp.status_code}: {resp.text[:160]}"


def _error_alert_payload(state: PipelineState) -> dict[str, Any]:
    """Build the Slack message for a failed pipeline run."""
    run_id = getattr(state, "run_id", "unknown")
    brd_name = getattr(state, "brd_name", "") or "(unnamed BRD)"
    status = getattr(state, "pipeline_status", "error")
    errors = list(getattr(state, "errors", []) or [])
    error_text = "\n".join(f"• {e}" for e in errors[:5]) or "• No error detail captured."
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return {
        # `text` is the notification fallback shown in the Slack sidebar / push.
        "text": f":rotating_light: EM Copilot pipeline failed — run {run_id}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "EM Copilot — Pipeline Failed"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Run ID:*\n`{run_id}`"},
                    {"type": "mrkdwn", "text": f"*BRD:*\n{brd_name}"},
                    {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                    {"type": "mrkdwn", "text": f"*Time:*\n{ts}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Errors*\n{error_text}"}},
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "Run halted before the HITL gate — no artifacts were exported."}
                ],
            },
        ],
    }


def send_pipeline_error_alert(state: PipelineState) -> dict[str, Any]:
    """
    Post a failure alert to Slack when a pipeline run ends in error.

    Returns {"status": "sent" | "skipped" | "failed", "detail": str}.
    Never raises — the caller treats Slack as strictly best-effort.
    """
    run_id = getattr(state, "run_id", "unknown")

    ok, why_not = _slack_status()
    if not ok:
        log.info(f"[{run_id}] Slack alert skipped — {why_not}")
        return {"status": "skipped", "detail": why_not}

    sent, detail = _post_to_slack(_error_alert_payload(state))
    if sent:
        log.info(f"[{run_id}] Slack failure alert delivered")
        return {"status": "sent", "detail": "Slack alert delivered"}
    log.warning(f"[{run_id}] Slack alert failed — {detail}")
    return {"status": "failed", "detail": detail}


# Phase 7: export-handler registry
from src.integrations.export_registry import register_export

register_export("slack", send_pipeline_error_alert, "error")
