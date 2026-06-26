import pytest
from unittest.mock import patch, PropertyMock
from fastapi.testclient import TestClient
from src.api.main import app, _runs, _run_owner
from src.core.models import PipelineState, HITLDecision

@pytest.fixture
def mock_run():
    run_id = "test-run-api-123"
    state = PipelineState(run_id=run_id, brd_raw_hash="hash", brd_name="test.txt")
    state.pipeline_status = "awaiting_hitl"
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
    state.hitl_decision = decision
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
                "email": "body-email@example.com"
            }
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
    from src.core.config import settings
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
            assert response.status_code == 401
            mock_export.assert_not_called()

def test_approve_idempotent_on_same_approved(client):
    """Voice agent re-fires approve after export → 200 no-op."""
    run_id = _seed_run(status="exported", decision=HITLDecision.APPROVED)
    r = client.post(f"/approve/{run_id}",
                    json={"decision": "approved", "reviewer": "Voice EM", "em_rating": 3})
    assert r.status_code == 200
    assert "idempotent" in r.json()["message"].lower()


def test_reject_idempotent_on_same_rejected(client):
    """Voice agent re-fires reject after rejection → 200 no-op."""
    run_id = _seed_run(status="rejected", decision=HITLDecision.REJECTED)
    r = client.post(f"/approve/{run_id}",
                    json={"decision": "rejected", "reviewer": "Voice EM", "em_rating": 1})
    assert r.status_code == 200
    assert "idempotent" in r.json()["message"].lower()


def test_reject_after_approve_returns_conflict(client):
    """User tries to flip an exported run to rejected → 409 with structured detail."""
    run_id = _seed_run(status="exported", decision=HITLDecision.APPROVED)
    r = client.post(f"/approve/{run_id}",
                    json={"decision": "rejected", "reviewer": "EM", "em_rating": 2})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "decision_immutable"
    assert "already approved" in detail["message"].lower()
    assert "Clear Plan" in detail["next_step"]


def test_approve_after_reject_returns_conflict(client):
    """User tries to flip a rejected run to approved → 409 with structured detail."""
    run_id = _seed_run(status="rejected", decision=HITLDecision.REJECTED)
    r = client.post(f"/approve/{run_id}",
                    json={"decision": "approved", "reviewer": "EM", "em_rating": 4})
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
    """ElevenLabs may post {"params": {...}} instead of flat fields — should unwrap."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"params": {
                "decision": "approved",
                "reviewer": "Voice EM",
                "em_rating": 3,
                "email": "voice@example.com",
            }},
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice@example.com")


def test_approve_normalizes_verb_decision(mock_run):
    """Voice agent emits 'approve' (verb) — validator maps to 'approved'."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approve", "reviewer": "Voice EM", "em_rating": 3,
                  "email": "voice@example.com"},
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.APPROVED, "voice@example.com")


def test_reject_normalizes_verb_decision(mock_run):
    """Voice agent emits 'reject' (verb) — validator maps to 'rejected'."""
    with patch("src.api.main._run_export_handlers_background") as mock_export:
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "Reject", "reviewer": "Voice EM", "em_rating": 1,
                  "email": "voice@example.com"},
        )
        assert response.status_code == 200
        mock_export.assert_called_once_with(mock_run, HITLDecision.REJECTED, "voice@example.com")


def test_em_rating_accepts_whole_float(mock_run):
    """em_rating=5.0 (float) is coerced to int 5 by the field validator."""
    with patch("src.api.main._run_export_handlers_background"):
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approved", "reviewer": "EM", "em_rating": 5.0,
                  "email": "em@example.com"},
        )
        assert response.status_code == 200


def test_em_rating_accepts_half_float(mock_run):
    """em_rating=4.5 (float) is rounded to int by the field validator (not 422'd)."""
    with patch("src.api.main._run_export_handlers_background"):
        client = TestClient(app)
        response = client.post(
            f"/approve/{mock_run}",
            json={"decision": "approved", "reviewer": "EM", "em_rating": 4.5,
                  "email": "em@example.com"},
        )
        assert response.status_code == 200


def test_budget_breached_error_raised():
    """Verify that add_cost raises BudgetBreachedError when cost threshold is exceeded."""
    from src.agents.base_agent import add_cost, reset_token_counter, get_cost
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
    from src.api.main import _run_pipeline_task, _runs, _run_events
    from src.core.exceptions import BudgetBreachedError

    run_id = "test-budget-task-run"
    _runs.pop(run_id, None)
    _run_events.pop(run_id, None)

    # We mock run_pipeline to raise BudgetBreachedError
    with patch("src.agents.pipeline.run_pipeline", side_effect=BudgetBreachedError("Budget breached during test")):
        _run_pipeline_task(
            brd_text="mock brd content",
            brd_hash="mockhash",
            run_id=run_id,
            brd_name="test.txt",
            model_family="openai",
            enable_fallback=True
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


@pytest.mark.parametrize("endpoint,method,json_data", [
    ("/status/{run_id}", "GET", None),
    ("/events/{run_id}", "GET", None),
    ("/results/{run_id}", "GET", None),
    ("/artifacts/{run_id}", "GET", None),
    ("/download/{run_id}", "GET", None),
    ("/approve/{run_id}", "POST", {"decision": "approved", "reviewer": "EM", "em_rating": 5}),
])
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
    with patch("src.api.main._run_export_handlers_background") as mock_export:
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
                        "email": ""
                    }
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
                        "email": ""
                    }
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
                        "email": ""
                    }
                )
                assert response.status_code == 401