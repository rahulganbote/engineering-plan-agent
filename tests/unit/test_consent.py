import json

from src.api.consent import CURRENT_TERMS_VERSION, _consent_index, has_consented, record_consent


def _reset_consent_index():
    """Test isolation: consent state lives in a module-level Redis/in-memory
    proxy, so clear any leftover entries from earlier tests before each check."""
    _consent_index.local_dict.clear()


def test_has_consented_false_by_default():
    _reset_consent_index()
    assert has_consented("new-user@example.com") is False


def test_record_consent_marks_signed_in_user_consented():
    _reset_consent_index()
    email = "returning-user@example.com"
    assert has_consented(email) is False

    record_consent(email=email, is_guest=False, brd_hash="abc123")

    assert has_consented(email) is True


def test_record_consent_does_not_persist_for_guests():
    """Guests are anonymous/one-off - the fast per-email index must never be
    updated for guest sessions, so a guest's synthetic email is never marked
    consented (matching the always-re-prompt guest behavior)."""
    _reset_consent_index()
    guest_email = "guest-abc123@guest.local"

    record_consent(email=guest_email, is_guest=True, brd_hash="abc123")

    assert has_consented(guest_email) is False


def test_record_consent_appends_audit_trail(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _reset_consent_index()

    record_consent(email="audit-user@example.com", is_guest=False, brd_hash="deadbeef")

    consent_file = tmp_path / "logs" / "consent.jsonl"
    assert consent_file.exists()
    lines = consent_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["email"] == "audit-user@example.com"
    assert record["is_guest"] is False
    assert record["brd_hash"] == "deadbeef"
    assert record["terms_version"] == CURRENT_TERMS_VERSION
