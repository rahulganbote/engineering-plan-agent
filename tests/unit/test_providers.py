# tests/unit/test_providers.py
from unittest.mock import MagicMock, patch

import pytest

from src.agents.base_agent import BaseAgent
from src.core.config import settings
from src.core.pricing import calculate_cost
from src.core.providers import AnthropicProvider, OpenAIProvider, get_provider, map_model


def test_calculate_cost():
    # OpenAI gpt-4o: Input $2.50/M, Output $10.00/M
    # 1000 input, 500 output -> (1000 * 2.50 / 1e6) + (500 * 10.00 / 1e6) = 0.0025 + 0.0050 = 0.0075
    cost = calculate_cost("openai", "gpt-4o", 1000, 500)
    assert cost == 0.0075

    # Anthropic Sonnet: Input $3.00/M, Output $15.00/M
    # 1000 input, 500 output -> (1000 * 3.00 / 1e6) + (500 * 15.00 / 1e6) = 0.0030 + 0.0075 = 0.0105
    cost = calculate_cost("anthropic", "claude-3-5-sonnet-20241022", 1000, 500)
    assert cost == 0.0105

    # Fallback default
    cost_fallback = calculate_cost("openai", "invalid-model-name", 1000, 500)
    assert cost_fallback > 0.0


def test_map_model():
    assert map_model("openai", "gpt-4o") == "gpt-4o"
    assert map_model("openai", "mini") == settings.openai_model_mini
    assert map_model("anthropic", "gpt-4o") == settings.anthropic_default_model
    assert map_model("anthropic", "mini") == settings.anthropic_mini_model
    assert map_model("llama", "default") == "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    assert map_model("mistral", "default") == "mistralai/Mistral-Large"


@patch("openai.OpenAI")
def test_openai_provider_complete(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="OpenAI hello"))]
    mock_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=20)
    mock_client.chat.completions.create.return_value = mock_resp

    provider = OpenAIProvider()
    content, prompt, completion = provider.complete(
        messages=[{"role": "user", "content": "hi"}], model="gpt-4o", temperature=0.2
    )

    assert content == "OpenAI hello"
    assert prompt == 10
    assert completion == 20


@patch("anthropic.Anthropic")
def test_anthropic_provider_complete(mock_anthropic_class):
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    mock_resp = MagicMock()
    mock_resp.content = [MagicMock(text="Claude hello")]
    mock_resp.usage = MagicMock(input_tokens=15, output_tokens=25)
    mock_client.messages.create.return_value = mock_resp

    with patch("src.core.config.settings.anthropic_api_key", "mock-key"):
        provider = AnthropicProvider()
        content, prompt, completion = provider.complete(
            messages=[{"role": "user", "content": "hi"}], model="claude-3-5-sonnet-20241022", temperature=0.2
        )

    assert content == "Claude hello"
    assert prompt == 15
    assert completion == 25


def test_get_provider_invalid_family():
    # Test Llama and Mistral which are "Coming soon"
    with pytest.raises(ValueError) as excinfo:
        get_provider("llama")
    assert "coming soon" in str(excinfo.value).lower()

    with pytest.raises(ValueError) as excinfo:
        get_provider("mistral")
    assert "coming soon" in str(excinfo.value).lower()

    # Test an unknown provider
    with pytest.raises(ValueError) as excinfo:
        get_provider("invalid-family")
    assert "unknown model family" in str(excinfo.value).lower()


def test_base_agent_thread_context_and_cost_tracking():
    from src.agents.base_agent import (
        _current_model_family,
        add_cost,
        cleanup_token_counter,
        get_cost,
        get_token_counts,
        reset_token_counter,
        set_current_run_id,
    )

    run_id = "test-cost-run"

    # Reset
    reset_token_counter(run_id)
    assert get_cost(run_id) == 0.0
    assert get_token_counts(run_id) == (0, 0)

    # Set context
    set_current_run_id(run_id, "anthropic")
    assert _current_model_family() == "anthropic"

    # Track cost and tokens
    add_cost(0.015, run_id=run_id)
    assert get_cost(run_id) == 0.015

    # Cleanup
    cleanup_token_counter(run_id)
    assert get_cost(run_id) == 0.0
    assert get_token_counts(run_id) == (0, 0)


class DummyAgentForTesting(BaseAgent):
    pass


@patch("src.core.providers.get_provider")
def test_base_agent_call_llm_with_retry_token_and_cost_accumulation(mock_get_provider):
    from src.agents.base_agent import (
        cleanup_token_counter,
        get_cost,
        get_token_counts,
        reset_token_counter,
        set_current_run_id,
    )

    mock_provider = MagicMock()
    # Mock complete to return (text, input_tokens, output_tokens)
    mock_provider.complete.return_value = ("Dummy response", 120, 80)
    mock_get_provider.return_value = mock_provider

    run_id = "test-call-run"
    reset_token_counter(run_id)
    set_current_run_id(run_id, "anthropic")

    agent = DummyAgentForTesting()

    with patch("src.agents.base_agent.settings") as mock_settings:
        mock_settings.openai_model = "gpt-4o"
        response = agent._call_llm_with_retry(system_prompt="sys", user_prompt="usr", model="gpt-4o")

    assert response == "Dummy response"

    # Verify token accumulation: 120 in, 80 out
    assert get_token_counts(run_id) == (120, 80)

    # Verify cost: Anthropic Sonnet (claude-3-5-sonnet-20241022) price is:
    # input: 3.0 / 1e6, output: 15.0 / 1e6
    # 120 * 3.0 / 1e6 = 0.00036
    # 80 * 15.0 / 1e6 = 0.00120
    # total cost = 0.00156
    cost = get_cost(run_id)
    assert abs(cost - 0.00156) < 1e-6

    cleanup_token_counter(run_id)


def test_complete_with_fallback_success():
    import anthropic

    from src.core.events import set_event_sink
    from src.core.providers import complete_with_fallback

    events = []
    set_event_sink(lambda e: events.append(e))

    with patch("src.core.providers.get_provider") as mock_get_provider:
        mock_primary = MagicMock()
        mock_resp = MagicMock()
        mock_primary.complete.side_effect = anthropic.RateLimitError(
            message="rate limit", response=mock_resp, body=None
        )

        mock_fallback = MagicMock()
        mock_fallback.complete.return_value = ("Success response", 50, 50)

        def side_effect(family):
            if family == "anthropic":
                return mock_primary
            return mock_fallback

        mock_get_provider.side_effect = side_effect

        content, prompt, completion, final_family = complete_with_fallback(
            model_family="anthropic",
            messages=[{"role": "user", "content": "hi"}],
            model="default",
            temperature=0.2,
        )

    assert content == "Success response"
    assert final_family == "openai"
    fallback_events = [e for e in events if e["type"] == "provider_fallback"]
    assert len(fallback_events) == 1
    assert fallback_events[0]["from_family"] == "anthropic"
    assert fallback_events[0]["to_family"] == "openai"

    set_event_sink(None)


def test_complete_with_fallback_both_fail():
    import anthropic
    import openai

    from src.core.providers import complete_with_fallback
    from src.core.resilience import QuotaExceededError

    with patch("src.core.providers.get_provider") as mock_get_provider:
        mock_primary = MagicMock()
        mock_resp1 = MagicMock()
        mock_primary.complete.side_effect = anthropic.RateLimitError(message="limit", response=mock_resp1, body=None)

        mock_fallback = MagicMock()
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 429
        mock_fallback.complete.side_effect = openai.RateLimitError(message="limit", response=mock_resp2, body=None)

        mock_get_provider.side_effect = lambda family: mock_primary if family == "anthropic" else mock_fallback

        with pytest.raises(QuotaExceededError) as excinfo:
            complete_with_fallback(
                model_family="anthropic",
                messages=[{"role": "user", "content": "hi"}],
                model="default",
                temperature=0.2,
            )

    assert "api credits/tokens has expired or reached limit" in str(excinfo.value).lower()


def test_complete_with_fallback_not_found_error():
    import anthropic

    from src.core.events import set_event_sink
    from src.core.providers import complete_with_fallback

    events = []
    set_event_sink(lambda e: events.append(e))

    with patch("src.core.providers.get_provider") as mock_get_provider:
        mock_primary = MagicMock()
        mock_resp = MagicMock()
        # NotFoundError represents HTTP 404
        mock_primary.complete.side_effect = anthropic.NotFoundError(
            message="model not found", response=mock_resp, body=None
        )

        mock_fallback = MagicMock()
        mock_fallback.complete.return_value = ("Success fallback response", 30, 40)

        mock_get_provider.side_effect = lambda family: mock_primary if family == "anthropic" else mock_fallback

        content, prompt, completion, final_family = complete_with_fallback(
            model_family="anthropic",
            messages=[{"role": "user", "content": "hi"}],
            model="default",
            temperature=0.2,
        )

    assert content == "Success fallback response"
    assert final_family == "openai"
    fallback_events = [e for e in events if e["type"] == "provider_fallback"]
    assert len(fallback_events) == 1
    assert "not found" in fallback_events[0]["reason"].lower()

    set_event_sink(None)


def test_complete_with_fallback_disabled_by_settings():
    import anthropic

    from src.core.config import settings
    from src.core.providers import complete_with_fallback

    with patch("src.core.providers.get_provider") as mock_get_provider:
        mock_primary = MagicMock()
        mock_resp = MagicMock()
        mock_primary.complete.side_effect = anthropic.RateLimitError(
            message="rate limit", response=mock_resp, body=None
        )
        mock_get_provider.return_value = mock_primary

        orig_val = settings.enable_provider_fallback
        settings.enable_provider_fallback = False
        try:
            with pytest.raises(anthropic.RateLimitError):
                complete_with_fallback(
                    model_family="anthropic",
                    messages=[{"role": "user", "content": "hi"}],
                    model="default",
                    temperature=0.2,
                )
        finally:
            settings.enable_provider_fallback = orig_val


def test_complete_with_fallback_disabled_by_context():
    import anthropic

    from src.agents.base_agent import cleanup_token_counter, set_current_run_id
    from src.core.config import settings
    from src.core.providers import complete_with_fallback

    with patch("src.core.providers.get_provider") as mock_get_provider:
        mock_primary = MagicMock()
        mock_resp = MagicMock()
        mock_primary.complete.side_effect = anthropic.RateLimitError(
            message="rate limit", response=mock_resp, body=None
        )
        mock_get_provider.return_value = mock_primary

        orig_val = settings.enable_provider_fallback
        settings.enable_provider_fallback = True
        try:
            set_current_run_id("test-run-fallback-disabled", "anthropic", enable_fallback=False)
            try:
                with pytest.raises(anthropic.RateLimitError):
                    complete_with_fallback(
                        model_family="anthropic",
                        messages=[{"role": "user", "content": "hi"}],
                        model="default",
                        temperature=0.2,
                    )
            finally:
                cleanup_token_counter("test-run-fallback-disabled")
        finally:
            settings.enable_provider_fallback = orig_val


def test_api_providers_endpoint():
    import asyncio

    from src.api.main import list_providers

    res = asyncio.run(list_providers())
    assert "openai" in res
    assert "anthropic" in res
    assert "llama" in res
    assert "mistral" in res
    assert res["llama"]["available"] is False
    assert res["mistral"]["available"] is False
    assert "coming soon" in res["llama"]["reason"].lower()
