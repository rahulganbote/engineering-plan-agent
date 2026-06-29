"""
src/integrations/email.py
═════════════════════════
Handles sending audit emails when a pipeline run is rejected at the HITL gate.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.core.config import settings
from src.core.logger import get_logger
from src.core.models import PipelineState

log = get_logger(__name__)


def send_audit_email(state: PipelineState) -> dict:
    """
    Sends an audit email containing the rejection notes and critic scores.
    Returns a dictionary with the status of the operation.
    """
    if not settings.smtp_host or not settings.audit_email:
        msg = f"SMTP configuration missing. Audit email for {state.run_id} would have been sent to {settings.audit_email or '<not-configured>'}."
        log.warning(msg)
        return {"status": "skipped", "detail": msg}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"EM Copilot Audit Alert: Pipeline {state.run_id} Rejected"
        msg["From"] = settings.smtp_user or "em-copilot@localhost"
        msg["To"] = settings.audit_email

        rejections = state.hitl_rejection_notes
        notes = rejections[-1] if rejections else "No notes provided."

        critic = state.critic_output
        scores_summary = "N/A"
        if critic:
            scores_summary = (
                f"Overall: {critic.overall_score}/5.0\\n"
                f"Groundedness: {critic.groundedness.score}/5.0\\n"
                f"Completeness: {critic.completeness.score}/5.0\\n"
                f"Consistency: {critic.consistency.score}/5.0\\n"
                f"Actionability: {critic.actionability.score}/5.0"
            )

        text = f"""
EM Copilot Pipeline Rejected

Run ID: {state.run_id}
Rejection Count: {state.hitl_rejection_count}

Latest Rejection Notes:
{notes}

Critic Scores:
{scores_summary}

Please review the artifacts in the UI.
"""
        part1 = MIMEText(text, "plain")
        msg.attach(part1)

        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(msg["From"], msg["To"], msg.as_string())
        server.quit()

        log.info(f"[{state.run_id}] Audit email sent to {settings.audit_email}")
        return {"status": "sent", "detail": f"Audit email sent to {settings.audit_email}"}
    except Exception as e:
        err_msg = f"Failed to send audit email: {e}"
        log.error(f"[{state.run_id}] {err_msg}")
        return {"status": "error", "detail": err_msg}


def send_feedback_email(feedback: dict) -> dict:
    """
    Sends a feedback email containing user feedback to contact@emcopilot.ai.
    """
    to_email = "contact@emcopilot.ai"
    subject = f"EM Copilot User Feedback: [{feedback.get('category', 'General').upper()}] {feedback.get('area', '')}"
    body = f"""
EM Copilot Feedback Received

Sender: {feedback.get('sender', 'Anonymous')}
Area: {feedback.get('area', 'N/A')}
Category: {feedback.get('category', 'N/A')}
Workspace: {feedback.get('workspace', 'N/A')}
Run ID: {feedback.get('run_id') or 'N/A'}

Description:
{feedback.get('description', '')}

Diagnostic Logs:
{feedback.get('diagnostic_logs', {})}
"""

    if not settings.smtp_host:
        import time
        from pathlib import Path
        
        email_dir = Path("logs/emails")
        email_dir.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time())
        email_file = email_dir / f"feedback_{timestamp}.txt"
        
        try:
            with open(email_file, "w", encoding="utf-8") as f:
                f.write(f"Subject: {subject}\n")
                f.write(f"To: {to_email}\n")
                f.write("From: em-copilot@localhost\n")
                f.write("="*80 + "\n")
                f.write(body)
            log.info(f"SMTP configuration missing. Saved mock email to {email_file}")
            return {"status": "saved_mock", "detail": f"Saved mock email to {email_file}"}
        except Exception as e:
            log.error(f"Failed to save mock email: {e}")
            return {"status": "skipped", "detail": f"SMTP missing, and failed to save mock: {e}"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_user or "em-copilot@localhost"
        msg["To"] = to_email

        part1 = MIMEText(body, "plain")
        msg.attach(part1)

        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
        if settings.smtp_user and settings.smtp_pass:
            server.login(settings.smtp_user, settings.smtp_pass)
        server.sendmail(msg["From"], msg["To"], msg.as_string())
        server.quit()

        log.info(f"Feedback email sent to {to_email}")
        return {"status": "sent", "detail": f"Feedback email sent to {to_email}"}
    except Exception as e:
        err_msg = f"Failed to send feedback email: {e}"
        log.error(err_msg)
        return {"status": "error", "detail": err_msg}
