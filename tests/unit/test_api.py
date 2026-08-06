from unittest.mock import PropertyMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import _run_owner, _runs, app
from src.core.models import HITLDecision, PipelineState
from src.core.pipeline_status import PipelineStatus


@pytest.fixture
def mock_run():
    run_id = "test-run-api-123"
    state = PipelineState(run_id=run_id, brd_raw_hash="hash", brd_name="test.txt")
    state.pipeline_status = PipelineStatus.AWAITING_HITL
    _runs[run_id] = state
    _run_owner[run_id] = "local-dev@example.com"
    yield run_id
    _runs.pop(run_id, None)
    _run_owner.pop(run_id, None)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_run(status: str, decision: HITLDecision | None = None) -> str:
    run_id = f"test-seeded-{status}-{decision.value if decision else 'none'}"
    state = PipelineState(run_id=run_id, brd_raw_hash="seeded_hash", brd_name="seeded_test.txt")
    state.pipeline_status = status
    state.hitl_decision = decision or HITLDecision.PENDING
    _runs[run_id] = state
    _run_owner[run_id] = "local-dev@example.com"
    return run_id


def test_approve_email_from_request_body(mock_run):
    """Scenario 1: email is explicitly provided in the request body."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={
                "decision": "approved",
                "reviewer": "Manager",
                "notes": "looks good",
                "em_rating": 4,
                "email": "body-email@example.com",
            },
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "body-email@example.com")


def test_approve_email_from_session(mock_run):
    """Scenario 2: email is empty in request, but available in session."""
    _run_owner[mock_run] = "session-email@example.com"
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
            mock_session.return_value = {"auth_email": "session-email@example.com"}
            client = TestClient(app)
            response = client.post(
                f"/approve/{mock_run}",
                json={
                    "decision": "approved",
                    "reviewer": "Manager",
                    "notes": "looks good",
                    "em_rating": 4,
                    "email": "",
                },
            )
            assert response.status_code == 200
            mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "session-email@example.com")


def test_approve_email_local_dev_fallback(mock_run):
    """Scenario 3: email empty, session empty, oauth is NOT configured -> local-dev@example.com."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("src.security.google_auth.is_configured", return_value=False):
            client = TestClient(app)
            response = client.post(
                f"/approve/{mock_run}",
                json={
                    "decision": "approved",
                    "reviewer": "Manager",
                    "notes": "looks good",
                    "em_rating": 4,
                    "email": "",
                },
            )
            assert response.status_code == 200
            mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "local-dev@example.com")


def test_approve_email_voice_agent_fallback(mock_run):
    """Scenario 4: email empty, session empty, oauth IS configured, voice reviewer -> voice-agent@example.com."""
    from src.api.state import _run_owner
    from src.core.config import settings

    if mock_run in _run_owner:
        del _run_owner[mock_run]

    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("src.security.google_auth.is_configured", return_value=True):
            with patch.object(settings, "voice_webhook_secret", "test-secret"):
                client = TestClient(app)
                response = client.post(
                    f"/approve/{mock_run}",
                    headers={"Authorization": "Bearer test-secret"},
                    json={
                        "decision": "approved",
                        "reviewer": "ElevenLabs Voice Agent",
                        "notes": "looks good",
                        "em_rating": 4,
                        "email": "",
                    },
                )
                assert response.status_code == 200
                mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice-agent@example.com")


def test_approve_email_voice_agent_resolves_owner(mock_run):
    """Scenario 6: voice reviewer, but run owner is defined -> resolves to run owner's email."""
    from src.api.state import _run_owner
    from src.core.config import settings

    _run_owner[mock_run] = "owner-user@example.com"

    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("src.security.google_auth.is_configured", return_value=True):
            with patch.object(settings, "voice_webhook_secret", "test-secret"):
                client = TestClient(app)
                response = client.post(
                    f"/approve/{mock_run}",
                    headers={"Authorization": "Bearer test-secret"},
                    json={
                        "decision": "approved",
                        "reviewer": "ElevenLabs Voice Agent",
                        "notes": "looks good",
                        "em_rating": 4,
                        "email": "",
                    },
                )
                assert response.status_code == 200
                mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "owner-user@example.com")


def test_approve_email_anonymous_fallback(mock_run):
    """Scenario 5: email empty, session empty, oauth IS configured, standard reviewer -> anonymous@example.com."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("src.security.google_auth.is_configured", return_value=True):
            client = TestClient(app)
            response = client.post(
                f"/approve/{mock_run}",
                json={
                    "decision": "approved",
                    "reviewer": "Engineering Manager",
                    "notes": "looks good",
                    "em_rating": 4,
                    "email": "",
                },
            )
            assert response.status_code == 401
            mock_export.assert_not_called()


def test_approve_idempotent_on_same_approved(client):
    """Voice agent re-fires approve after export → 200 no-op."""
    run_id = _seed_run(status="exported", decision=HITLDecision.APPROVED)
    r = client.post(f"/approve/{run_id}", json={"decision": "approved", "reviewer": "Voice EM", "em_rating": 3})
    assert r.status_code == 200
    assert "idempotent" in r.json()["message"].lower()


def test_reject_idempotent_on_same_rejected(client):
    """Voice agent re-fires reject after rejection → 200 no-op."""
    run_id = _seed_run(status="rejected", decision=HITLDecision.REJECTED)
    r = client.post(f"/approve/{run_id}", json={"decision": "rejected", "reviewer": "Voice EM", "em_rating": 1})
    assert r.status_code == 200
    assert "idempotent" in r.json()["message"].lower()


def test_reject_after_approve_returns_conflict(client):
    """User tries to flip an exported run to rejected → 409 with structured detail."""
    run_id = _seed_run(status="exported", decision=HITLDecision.APPROVED)
    r = client.post(f"/approve/{run_id}", json={"decision": "rejected", "reviewer": "EM", "em_rating": 2})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "decision_immutable"
    assert "already approved" in detail["message"].lower()
    assert "Clear Plan" in detail["next_step"]


def test_approve_after_reject_returns_conflict(client):
    """User tries to flip a rejected run to approved → 409 with structured detail."""
    run_id = _seed_run(status="rejected", decision=HITLDecision.REJECTED)
    r = client.post(f"/approve/{run_id}", json={"decision": "approved", "reviewer": "EM", "em_rating": 4})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "decision_immutable"
    assert "already rejected" in detail["message"].lower()
    assert "Clear Plan" in detail["next_step"]


# ── Defensive input-hardening tests for voice-agent quirks ────────────────────
# These exercise the three pre-validators on ApprovalRequest. They protect
# against regressions if pydantic config or the validator implementations
# change in future refactors.


def test_approve_accepts_nested_params_payload(mock_run):
    """ElevenLabs may post {"params": {...}} instead of flat fields - should unwrap."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={
                "params": {
                    "decision": "approved",
                    "reviewer": "Voice EM",
                    "em_rating": 3,
                    "email": "voice@example.com",
                }
            },
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice@example.com")


def test_approve_normalizes_verb_decision(mock_run):
    """Voice agent emits 'approve' (verb) - validator maps to 'approved'."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approve", "reviewer": "Voice EM", "em_rating": 3, "email": "voice@example.com"},
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice@example.com")


def test_reject_normalizes_verb_decision(mock_run):
    """Voice agent emits 'reject' (verb) - validator maps to 'rejected'."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "Reject", "reviewer": "Voice EM", "em_rating": 1, "email": "voice@example.com"},
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.REJECTED, "voice@example.com")


def test_em_rating_accepts_whole_float(mock_run):
    """em_rating=5.0 (float) is coerced to int 5 by the field validator."""
    with patch("src.api.main._run_export_handlers_background"):
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approved", "reviewer": "EM", "em_rating": 5.0, "email": "em@example.com"},
        )
        assert response.status_code == 200


def test_em_rating_accepts_half_float(mock_run):
    """em_rating=4.5 (float) is rounded to int by the field validator (not 422'd)."""
    with patch("src.api.main._run_export_handlers_background"):
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approved", "reviewer": "EM", "em_rating": 4.5, "email": "em@example.com"},
        )
        assert response.status_code == 200


def test_budget_breached_error_raised():
    """Verify that add_cost raises BudgetBreachedError when cost threshold is exceeded."""
    from src.agents.base_agent import add_cost, get_cost, reset_token_counter
    from src.core.config import settings
    from src.core.exceptions import BudgetBreachedError

    run_id = "test-budget-run"
    reset_token_counter(run_id)

    # Within budget
    add_cost(settings.max_pipeline_run_budget_usd - 0.01, run_id=run_id)
    assert get_cost(run_id) == settings.max_pipeline_run_budget_usd - 0.01

    # Exceed budget
    with pytest.raises(BudgetBreachedError) as exc_info:
        add_cost(0.02, run_id=run_id)

    assert "exceeded the single-run budget limit" in str(exc_info.value)


def test_pipeline_task_catches_budget_breached_error():
    """Verify that _run_pipeline_task catches BudgetBreachedError and updates state and events."""
    import json

    from src.api.main import _run_events, _run_pipeline_task, _runs
    from src.core.exceptions import BudgetBreachedError

    run_id = "test-budget-task-run"
    _runs.pop(run_id, None)
    _run_events.pop(run_id, None)

    from src.security.validator import ValidationResult, ValidationStatus

    mock_val = ValidationResult(
        status=ValidationStatus.PASSED,
        brd_text_clean="mock brd content is sufficiently long and realistic to bypass validation checks.",
        brd_hash="mockhash",
        user_message="Clean",
        technical_detail="Clean",
        pii_types_found=[],
    )
    with patch("src.security.validator.SecurityValidator.validate", return_value=mock_val):
        with patch("src.agents.pipeline.run_pipeline", side_effect=BudgetBreachedError("Budget breached during test")):
            _run_pipeline_task(
                file_bytes=b"mock brd content",
                brd_hash="mockhash",
                run_id=run_id,
                brd_name="test.txt",
                content_type="text/plain",
                model_family="openai",
                enable_fallback=True,
            )

    # Check that the run was registered as error state
    assert run_id in _runs
    state = _runs[run_id]
    assert state.pipeline_status == "error"
    assert any("Pipeline execution aborted" in err for err in state.errors)

    # Check that error event was pushed
    events = _run_events.get(run_id, [])
    assert len(events) > 0
    error_event = next((json.loads(e) for e in events if json.loads(e).get("type") == "error"), None)
    assert error_event is not None
    assert "Pipeline execution aborted" in error_event["message"]


@pytest.mark.parametrize(
    "endpoint,method,json_data",
    [
        ("/status/{run_id}", "GET", None),
        ("/events/{run_id}", "GET", None),
        ("/results/{run_id}", "GET", None),
        ("/artifacts/{run_id}", "GET", None),
        ("/download/{run_id}", "GET", None),
        ("/approve/{run_id}", "POST", {"decision": "approved", "reviewer": "EM", "em_rating": 5}),
    ],
)
def test_user_b_cannot_read_user_a_run(endpoint, method, json_data, mock_run):
    """User A starts a run; User B (different session) gets 403 on every endpoint (Gap 3)."""
    with patch("starlette.requests.Request.session", new_callable=PropertyMock) as mock_session:
        mock_session.return_value = {"auth_email": "b@example.com"}
        client = TestClient(app)
        url = endpoint.format(run_id=mock_run)
        if method == "GET":
            response = client.get(url)
        else:
            response = client.post(url, json=json_data)
        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


def test_local_dev_isolation_via_as_parameter(mock_run):
    """Verify that ?as= query parameter allows local dev user impersonation / isolation (Gap 5)."""
    with patch("src.security.google_auth.is_configured", return_value=False):
        client = TestClient(app)

        # Accessing with no 'as' query param fallback to local-dev@example.com (succeeds since owner is local-dev)
        response = client.get(f"/artifacts/{mock_run}")
        assert response.status_code == 200

        # Accessing with 'as=b@example.com' query param acts as b@example.com (fails with 403)
        response = client.get(f"/artifacts/{mock_run}?as=b@example.com")
        assert response.status_code == 403
        assert "Forbidden" in response.json()["detail"]


def test_voice_agent_secret_rotation(mock_run):
    """Verify that multiple webhook secrets can be accepted for rotation (Gap 4)."""
    from src.core.config import settings

    with patch("src.api.main._run_export_handlers_background"):
        with patch("src.security.google_auth.is_configured", return_value=True):
            # Configure multiple secrets separated by comma
            with patch.object(settings, "voice_webhook_secret", "old-secret,new-secret"):
                client = TestClient(app)

                # Test using old secret
                response = client.post(
                    f"/approve/{mock_run}",
                    headers={"Authorization": "Bearer old-secret"},
                    json={
                        "decision": "approved",
                        "reviewer": "ElevenLabs Voice Agent",
                        "notes": "looks good",
                        "em_rating": 4,
                        "email": "",
                    },
                )
                assert response.status_code == 200

                # Test using new secret
                response = client.post(
                    f"/approve/{mock_run}",
                    headers={"Authorization": "Bearer new-secret"},
                    json={
                        "decision": "approved",
                        "reviewer": "ElevenLabs Voice Agent",
                        "notes": "looks good",
                        "em_rating": 4,
                        "email": "",
                    },
                )
                assert response.status_code == 200

                # Test using an invalid secret
                response = client.post(
                    f"/approve/{mock_run}",
                    headers={"Authorization": "Bearer invalid-secret"},
                    json={
                        "decision": "approved",
                        "reviewer": "ElevenLabs Voice Agent",
                        "notes": "looks good",
                        "em_rating": 4,
                        "email": "",
                    },
                )
                assert response.status_code == 401


@pytest.mark.asyncio
async def test_export_handlers_background_pinecone_ingestion():
    from unittest.mock import MagicMock, patch

    from src.api.main import _runs
    from src.api.tasks import _run_export_handlers_background

    run_id = "test-export-pinecone"
    state = PipelineState(run_id=run_id, brd_raw_hash="brd_hash_val", brd_name="test_brd.txt")
    _runs[run_id] = state

    mock_cache = MagicMock()
    mock_cache.get.return_value = {"text": "Some dummy BRD content"}

    with (
        patch("src.core.cache.get_default_backend", return_value=mock_cache),
        patch(
            "src.integrations.sheets.write_artifacts_to_sheet",
            return_value={"mode": "local", "detail": "dummy", "url": None},
        ),
        patch("src.integrations.jira_mcp.push_epic_to_jira", return_value={"mode": "skipped", "detail": "dummy"}),
        patch("src.integrations.pdf_export._pdf_export_handler", return_value={"mode": "pdf", "detail": "dummy"}),
        patch("src.core.rag.ingest_document", return_value="5 chunks ingested from test_brd") as mock_ingest,
    ):
        await _run_export_handlers_background(run_id, HITLDecision.APPROVED, "test@example.com")

        mock_ingest.assert_called_once_with(
            text="Some dummy BRD content",
            doc_id="test_brd",
            source_type="brd",
        )


def test_submit_feedback(client):
    import json
    from pathlib import Path
    from unittest.mock import patch

    # Ensure any preexisting test feedback file is cleared
    feedback_file = Path("logs/feedback.jsonl")
    if feedback_file.exists():
        try:
            feedback_file.unlink()
        except OSError:
            pass

    payload = {
        "area": "User Interface",
        "category": "Bug",
        "description": "Button hover is not visible",
        "include_transcript": True,
        "workspace": "EM-Copilot Development",
        "diagnostic_logs": {"os": "darwin", "version": "1.0.0"},
        "sender": "test-user@emcopilot.ai",
        "run_id": "test-run-123",
    }

    with patch("src.api.routes.system.send_feedback_email") as mock_email:
        response = client.post("/api/feedback", json=payload)
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Feedback submitted successfully"}

        # Verify file on disk
        assert feedback_file.exists()
        with open(feedback_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["area"] == "User Interface"
            assert data["category"] == "Bug"
            assert data["sender"] == "test-user@emcopilot.ai"
            assert "timestamp_epoch" in data

        mock_email.assert_called_once()

    # Clean up test output
    if feedback_file.exists():
        try:
            feedback_file.unlink()
        except OSError:
            pass


def test_pipeline_task_records_security_block():
    """When SecurityValidator returns BLOCKED, task records error state,
    emits security_blocked SSE event, and skips run_pipeline entirely."""
    import json

    from src.api.main import _run_events, _run_pipeline_task, _runs
    from src.security.validator import ValidationResult, ValidationStatus

    run_id = "test-security-blocked-run"
    _runs.pop(run_id, None)
    _run_events.pop(run_id, None)

    mock_val = ValidationResult(
        status=ValidationStatus.BLOCKED,
        brd_text_clean="",
        brd_hash="mockhash",
        user_message="Your BRD is blocked due to PII/Injection checks.",
        technical_detail="PII details: SSN matched",
        pii_types_found=["SSN"],
    )

    with patch("src.security.validator.SecurityValidator.validate", return_value=mock_val):
        with patch("src.agents.pipeline.run_pipeline") as mock_pipeline:
            _run_pipeline_task(
                file_bytes=b"blocked content",
                brd_hash="mockhash",
                run_id=run_id,
                brd_name="blocked.txt",
                content_type="text/plain",
                model_family="openai",
                enable_fallback=True,
            )
            # Ensure the pipeline execution is skipped
            mock_pipeline.assert_not_called()

    # Assert status and errors
    assert run_id in _runs
    state = _runs[run_id]
    assert state.pipeline_status == "error"
    assert "Your BRD is blocked due to PII/Injection checks." in state.errors

    # Assert security_blocked event was pushed
    events = _run_events.get(run_id, [])
    assert len(events) > 0
    blocked_event = next((json.loads(e) for e in events if json.loads(e).get("type") == "security_blocked"), None)
    assert blocked_event is not None
    assert blocked_event["message"] == "Your BRD is blocked due to PII/Injection checks."


def test_run_pipeline_endpoint_latency_and_background_task(client):
    """Assert POST /run-pipeline returns instantly and queues task in background."""
    import hashlib

    with patch("src.api.routes.runs._run_pipeline_task") as mock_task:
        import time

        start_time = time.time()

        # Send request with mock file and consent accepted
        response = client.post(
            "/run-pipeline",
            data={"model_family": "openai", "enable_fallback": True, "consent_accepted": True},
            files={"file": ("brd.txt", b"Mock BRD contents", "text/plain")},
        )

        latency_ms = (time.time() - start_time) * 1000
        assert latency_ms < 250  # Latency under 250ms

        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data

        # Ensure background task was added
        mock_task.assert_called_once()
        args, kwargs = mock_task.call_args
        assert args[1] == hashlib.sha256(b"Mock BRD contents").hexdigest()
        assert args[2] == data["run_id"]


def test_run_pipeline_without_consent_raises_400(client):
    """Assert POST /run-pipeline fails with 400 Bad Request if consent is not accepted."""
    response = client.post(
        "/run-pipeline",
        data={"model_family": "openai", "enable_fallback": True, "consent_accepted": False},
        files={"file": ("brd.txt", b"Mock BRD contents", "text/plain")},
    )
    assert response.status_code == 400
    assert "accept the Terms of Service and Privacy Policy" in response.json()["detail"]


def test_guest_auth_flow(client):
    """Assert POST /auth/guest successfully authenticates guest and sets session."""
    # 1. Start signed out
    with patch("src.security.google_auth.is_configured", return_value=True):
        resp = client.get("/auth/me")
        assert resp.json() == {"authenticated": False}

        # 2. Login as guest
        resp_guest = client.post("/auth/guest")
        assert resp_guest.status_code == 200
        data = resp_guest.json()
        assert data["authenticated"] is True
        assert data["is_guest"] is True
        assert "guest-" in data["email"]
        assert data["name"] == "Guest"

        # 3. Check /auth/me returns guest state
        resp_me = client.get("/auth/me")
        assert resp_me.status_code == 200
        data_me = resp_me.json()
        assert data_me["authenticated"] is True
        assert data_me["is_guest"] is True
        assert "guest-" in data_me["email"]

        # 4. Sign in as local dev when auth is disabled
        with patch("src.security.google_auth.is_configured", return_value=False):
            resp_login = client.get("/auth/login", follow_redirects=False)
            assert resp_login.status_code in (302, 307)
            assert resp_login.headers["location"] == "/"

            resp_me = client.get("/auth/me")
            data_me = resp_me.json()
            assert data_me["authenticated"] is True
            assert data_me["is_guest"] is False
            assert data_me["email"] == "local-dev@example.com"


def test_guest_pipeline_run_override(client):
    """Assert guest run overrides model family selection to llama."""
    with patch("src.api.routes.runs._run_pipeline_task") as mock_task:
        with patch("src.security.google_auth.is_configured", return_value=True):
            # 1. Login as guest first
            client.post("/auth/guest")

            # 2. Run pipeline selecting openai, but it should be overridden to llama
            response = client.post(
                "/run-pipeline",
                data={"model_family": "openai", "enable_fallback": True, "consent_accepted": True},
                files={"file": ("brd.txt", b"Mock BRD contents", "text/plain")},
            )
            assert response.status_code == 200

            # Verify model_family argument passed to the background task (arg 5) is overridden to llama
            mock_task.assert_called_once()
            args, kwargs = mock_task.call_args
            assert args[5] == "llama"


def test_rate_limit_exemptions():
    from src.api.routes.approval import get_approve_limit
    from src.api.routes.runs import get_daily_limit, get_weekly_limit
    from src.core.config import settings

    orig_exempt = settings.rate_limit_exempt_emails
    settings.rate_limit_exempt_emails = "test-exempt@example.com,test-another@example.com"
    try:
        # 1. Exempt user
        assert get_daily_limit("test-exempt@example.com") is None
        assert get_weekly_limit("test-exempt@example.com") is None
        assert get_approve_limit("test-exempt@example.com") is None

        # 2. Case-insensitivity check
        assert get_daily_limit("TEST-EXEMPT@EXAMPLE.COM") is None

        # 3. Non-exempt user
        assert get_daily_limit("regular-user@example.com") == settings.rate_limit_run_pipeline_per_day
        assert get_weekly_limit("regular-user@example.com") == settings.rate_limit_run_pipeline_per_week
        assert get_approve_limit("regular-user@example.com") == settings.rate_limit_approve_per_hour

        # 4. Guest user
        assert get_daily_limit("guest-ip:1.2.3.4") == settings.rate_limit_guest_run_per_day
        assert get_weekly_limit("guest-ip:1.2.3.4") == "10/week"
    finally:
        settings.rate_limit_exempt_emails = orig_exempt


def test_rate_limiter_integration(client):
    """Verify that SlowAPI rate limiting intercepts /run-pipeline and returns 429 after limits are exceeded."""
    from src.api.limiter import limiter
    from src.core.config import settings

    orig_guest_day = settings.rate_limit_guest_run_per_day
    # Set to a very low daily rate limit for testing
    settings.rate_limit_guest_run_per_day = "1/day"
    # Enable limiter for this specific integration test
    limiter.enabled = True

    try:
        # Reset limiter memory
        limiter._limiter.storage.reset()

        with patch("src.api.routes.runs._run_pipeline_task"):
            with patch("src.security.google_auth.is_configured", return_value=True):
                # Login as guest
                client.post("/auth/guest")

                # First run - should be successful (200)
                response1 = client.post(
                    "/run-pipeline",
                    data={"model_family": "openai", "enable_fallback": True, "consent_accepted": True},
                    files={"file": ("brd.txt", b"Mock BRD contents", "text/plain")},
                )
                assert response1.status_code == 200

                # Second run - should exceed rate limit (429)
                response2 = client.post(
                    "/run-pipeline",
                    data={"model_family": "openai", "enable_fallback": True, "consent_accepted": True},
                    files={"file": ("brd.txt", b"Mock BRD contents", "text/plain")},
                )
                assert response2.status_code == 429
                json_res = response2.json()
                assert json_res["detail"]["code"] == "rate_limited"
    finally:
        settings.rate_limit_guest_run_per_day = orig_guest_day
        limiter.enabled = False
