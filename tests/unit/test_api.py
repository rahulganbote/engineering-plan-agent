# tests/unit/test_api.py
import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient
from src.api.main import app, _runs
from src.core.models import PipelineState, HITLDecision

@pytest.fixture
def mock_run():
    run_id = "test-run-api-123"
    state = PipelineState(run_id=run_id, brd_raw_hash="hash", brd_name="test.txt")
    state.pipeline_status = "awaiting_hitl"
    _runs[run_id] = state
    yield run_id
    _runs.pop(run_id, None)

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
                "email": "body-email@example.com"
            }
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "body-email@example.com")

def test_approve_email_from_session(mock_run):
    """Scenario 2: email is empty in request, but available in session."""
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
                    "email": ""
                }
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
                    "email": ""
                }
            )
            assert response.status_code == 200
            mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "local-dev@example.com")

def test_approve_email_voice_agent_fallback(mock_run):
    """Scenario 4: email empty, session empty, oauth IS configured, voice reviewer -> voice-agent@example.com."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        with patch("src.security.google_auth.is_configured", return_value=True):
            client = TestClient(app)
            response = client.post(
                f"/approve/{mock_run}",
                json={
                    "decision": "approved",
                    "reviewer": "ElevenLabs Voice Agent",
                    "notes": "looks good",
                    "em_rating": 4,
                    "email": ""
                }
            )
            assert response.status_code == 200
            mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice-agent@example.com")

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
                    "email": ""
                }
            )
            assert response.status_code == 200
            mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "anonymous@example.com")
