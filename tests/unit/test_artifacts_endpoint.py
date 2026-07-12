"""
tests/unit/test_artifacts_endpoint.py
══════════════════════════════════════

Regression tests for the /artifacts/{run_id} endpoint after the state.py
Redis migration. These tests exercise the endpoint in the in-memory fallback
mode (no REDIS_URL set), which shares the same proxy code paths as the Redis
mode but avoids needing a live Redis in CI.

Invariants under test:
  1. When _run_export has data, /artifacts embeds it as a JSON-serializable
     plain dict (NOT a proxy object). A bug in the state.py rewrite made
     it embed the RedisSubDictProxy directly, which crashed FastAPI's
     JSON encoder and returned 500.
  2. Setting a full dict via `_run_export[run_id] = {...}` then mutating a
     single field via `_run_export[run_id]["field"] = value` must work
     without a Redis WRONGTYPE-style collision. A separate bug in the
     rewrite left the key STRING-typed on full assignment, which broke
     any subsequent field-level HSET path.
"""

import json

from src.api.state import _run_export


def test_run_export_get_returns_plain_dict(monkeypatch):
    """
    _run_export.get(run_id) must return a plain dict (or None), not a
    RedisSubDictProxy. Callers inline this into API responses; a proxy
    object would blow up FastAPI's json encoder.
    """
    run_id = "test-run-artifacts-serialization"
    payload = {
        "sheet_url": "https://sheets.example/test",
        "mode": "google_sheets",
        "detail": "ok",
        "status": "success",
    }

    _run_export[run_id] = payload
    try:
        result = _run_export.get(run_id)
        # Result must be a plain dict — assert this directly and via json.dumps
        # (which is the actual failure mode the bug produced).
        assert isinstance(result, dict), (
            f"_run_export.get() returned {type(result).__name__}, expected dict. "
            "A proxy object here would crash FastAPI's response encoder."
        )
        # Must round-trip through json without raising.
        serialized = json.dumps(result)
        assert "sheet_url" in serialized
        assert result["sheet_url"] == payload["sheet_url"]
        assert result["status"] == "success"
    finally:
        _run_export.pop(run_id, None)


def test_run_export_full_assign_then_field_mutation(monkeypatch):
    """
    The tasks.py export finalization pattern:
      1. Full assignment: `_run_export[run_id] = {"sheet_url": ..., ...}`
      2. Field mutation: `_run_export[run_id]["finalized"] = True`

    Both must succeed. A bug in the state.py rewrite made step 1 write a
    STRING-typed Redis key, so step 2 (which uses HSET on the same key)
    silently failed with WRONGTYPE. In the in-memory fallback path this
    manifests as the second write being lost or clobbering the whole dict.
    """
    run_id = "test-run-mutation"
    _run_export[run_id] = {
        "sheet_url": "https://sheets.example/test",
        "status": "success",
    }
    try:
        # Step 2: mutate a single field.
        _run_export[run_id]["finalized"] = True
        _run_export[run_id]["jira"] = {"url": "https://jira.example/SCRUM-1", "mode": "mcp"}

        result = _run_export.get(run_id)
        assert result is not None
        assert result.get("sheet_url") == "https://sheets.example/test", (
            f"Original field 'sheet_url' was lost after mutation. Got: {result}"
        )
        assert result.get("finalized") is True, f"Mutated field 'finalized' didn't persist. Got: {result}"
        assert result.get("jira") == {"url": "https://jira.example/SCRUM-1", "mode": "mcp"}
        # Must be JSON-serializable end-to-end.
        json.dumps(result)
    finally:
        _run_export.pop(run_id, None)


def test_run_export_missing_returns_default():
    """
    _run_export.get(nonexistent, default) must return the default.
    Guards against a proxy being incorrectly returned when the key is missing.
    """
    result = _run_export.get("nonexistent-run-id-xyz", {})
    assert result == {}, f"Expected default {{}}, got {result!r}"

    result_none = _run_export.get("nonexistent-run-id-xyz")
    assert result_none is None, f"Expected None, got {result_none!r}"


def test_run_export_truthiness_when_populated():
    """
    `if _run_export.get(run_id):` used to short-circuit incorrectly because
    RedisSubDictProxy had no __bool__. Verify truthiness works both when
    populated (True) and when missing (False via the None/empty-dict return).
    """
    run_id = "test-run-truthy"
    try:
        # Missing → falsy
        assert not _run_export.get(run_id), "Missing key should be falsy"

        # Populated → truthy
        _run_export[run_id] = {"a": 1}
        assert bool(_run_export.get(run_id)), "Populated key should be truthy"
    finally:
        _run_export.pop(run_id, None)
