"""
tests/unit/test_caching.py
══════════════════════════

Regression tests for the embedding cache-poisoning fix (see postmortem).

Invariant under test:
  When _embed encounters an OpenAI RateLimitError, it must NOT memoize the
  zero-vector fallback. Subsequent calls must reach the OpenAI client again.
"""

from unittest.mock import MagicMock, patch

import openai
import pytest

from src.core.cache import InMemoryCache, get_default_backend, reset_default_backend
from src.core.config import settings
from src.core.events import set_event_sink
from src.core.rag import _embed


@pytest.fixture
def clean_cache():
    """Fresh in-memory cache for each test; restored on teardown."""
    from src.core.rag import _EMBED_BREAKER

    _EMBED_BREAKER.record_success()
    prior = get_default_backend()
    reset_default_backend(InMemoryCache(max_entries=100))
    yield
    reset_default_backend(prior)
    _EMBED_BREAKER.record_success()


@pytest.fixture
def event_recorder():
    """Capture events emitted during the test; restore default sink on teardown."""
    events: list[dict] = []
    set_event_sink(lambda ev: events.append(ev))
    yield events
    set_event_sink(None)


def _raise_rate_limit():
    """Construct a realistic openai.RateLimitError for mocking."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    return openai.RateLimitError(
        message="Mocked rate limit error",
        response=mock_response,
        body=None,
    )


def test_embed_fallback_not_cached(clean_cache, event_recorder):
    """
    Two successive _embed calls with the same input should BOTH reach the
    OpenAI client — proving the fallback wasn't memoized between calls.
    """
    with patch("openai.resources.embeddings.Embeddings.create") as mock_create:
        mock_create.side_effect = _raise_rate_limit()

        res1 = _embed(["hello"])
        res2 = _embed(["hello"])

    # Both calls returned safe zero-vector fallbacks (didn't crash).
    zero_vec = [0.0] * settings.embedding_dimension
    assert res1 == [zero_vec]
    assert res2 == [zero_vec]

    # Retry policy may vary — assert the invariant (each _embed call must
    # reach mock_create at least once), not an implementation detail (exact
    # retry count).
    assert mock_create.call_count >= 2, (
        "Second _embed call should have hit mock_create — if it was cached, mock_create wouldn't be called again."
    )
    # Even split proves both _embed calls did their own retry cycles.
    assert mock_create.call_count % 2 == 0, (
        f"Expected even call_count (equal work per _embed call); got {mock_create.call_count}"
    )


def test_embed_fallback_emits_event(clean_cache, event_recorder):
    """
    Each fallback should emit an embedding_fallback_used observability event.
    """
    with patch("openai.resources.embeddings.Embeddings.create") as mock_create:
        mock_create.side_effect = _raise_rate_limit()

        _embed(["hello"])
        _embed(["world"])

    fallback_events = [e for e in event_recorder if e.get("type") == "embedding_fallback_used"]
    assert len(fallback_events) == 2, (
        f"Expected 2 embedding_fallback_used events, got {len(fallback_events)}: {event_recorder}"
    )
    assert fallback_events[0]["provider"] == "openai"
    assert "RateLimitError" in fallback_events[0]["reason"]


def test_cache_backend_does_not_memoize_exception(clean_cache):
    """
    Direct verification: after a failure, the cache backend must not return
    a stale value on subsequent lookups for the same input.
    """
    with patch("openai.resources.embeddings.Embeddings.create") as mock_create:
        mock_create.side_effect = _raise_rate_limit()
        _embed(["hello"])
        first_call_count = mock_create.call_count

        # Second identical call — must NOT be served from cache.
        _embed(["hello"])
        second_call_count = mock_create.call_count

    assert second_call_count > first_call_count, (
        "Cache appears to have memoized the failure: second _embed call "
        "did not reach mock_create, meaning the cache served a stale value."
    )
