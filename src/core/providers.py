# src/core/providers.py
from typing import Protocol, cast

import anthropic
import openai
from langsmith import traceable
from langsmith.wrappers import wrap_openai

try:
    from langsmith.wrappers import wrap_anthropic
except ImportError:
    # Fallback for environments running older langsmith SDK versions (e.g. CI runner)
    def wrap_anthropic(client):
        return client


from src.core.config import settings


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> tuple[str, int, int]:
        """
        Send a completion request.
        Returns: (response_text, input_tokens, output_tokens)
        """
        ...


class OpenAIProvider:
    @traceable(run_type="llm", name="OpenAI Completion")
    def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> tuple[str, int, int]:
        # SDK-level timeout: 90s matches OPENAI_POLICY's 270s wall-clock
        # budget (leaves headroom for retries).
        client = wrap_openai(openai.OpenAI(api_key=settings.openai_api_key, timeout=90.0, max_retries=0))
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = client.chat.completions.create(**kwargs)
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        return resp.choices[0].message.content, input_tokens, output_tokens


class OpenRouterProvider:
    @traceable(run_type="llm", name="OpenRouter Completion")
    def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> tuple[str, int, int]:
        if not settings.openrouter_api_key:
            raise ValueError("OpenRouter API key is not configured. Please set OPENROUTER_API_KEY.")
        client = wrap_openai(
            openai.OpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                timeout=90.0,
                max_retries=0,
            )
        )
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            # Hard price ceiling in USD per million tokens: prevents guest-mode run
            # cost exposure from skyrocketing in case of unexpected routing.
            # sort="throughput" picks the fastest provider that still respects the
            # price ceiling (OpenRouter's documented pattern for latency-sensitive
            # + budget-capped traffic) - mitigates multi-minute latency outliers
            # observed on some free/cheap routed endpoints.
            "extra_body": {
                "provider": {
                    "sort": "throughput",
                    "max_price": {"prompt": 0.2, "completion": 0.5},
                }
            },
        }
        if response_format:
            kwargs["response_format"] = response_format

        resp = client.chat.completions.create(**kwargs)
        usage = getattr(resp, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        return resp.choices[0].message.content, input_tokens, output_tokens


class AnthropicProvider:
    @traceable(run_type="llm", name="Anthropic Completion")
    def complete(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        response_format: dict[str, str] | None = None,
    ) -> tuple[str, int, int]:
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key is not configured. Please set ANTHROPIC_API_KEY.")

        # SDK-level timeout: 120s matches ANTHROPIC_POLICY's 240s wall-clock
        # budget (leaves headroom for retries). Anthropic Sonnet is slower
        # than GPT-4o on high-token payloads, so this is set higher than
        # the OpenAI equivalent (60s).
        client = wrap_anthropic(anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=120.0, max_retries=0))

        # Extract system message if present
        system_msg = ""
        user_msgs = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            else:
                # Anthropic expects roles 'user' or 'assistant'
                role = m["role"]
                if role not in ("user", "assistant"):
                    role = "user"
                user_msgs.append({"role": role, "content": m["content"]})

        # ── JSON prefill technique (Anthropic's official pattern) ────────────
        # Anthropic's messages.create() doesn't accept response_format. When OpenAI
        # code paths pass response_format={"type": "json_object"}, simply ignoring
        # it lets Claude return prose like 'Here is the JSON: { ... }', which then
        # fails json.loads() in the calling agent.
        #
        # Anthropic's recommended fix is to PREFILL the assistant turn with `{`.
        # The model continues from there, output starts with `{` guaranteed, no
        # preamble. We then prepend `{` back to the response text.
        # Refs: https://docs.anthropic.com/en/docs/build-with-claude/prefill-claudes-response
        want_json = (
            response_format is not None
            and isinstance(response_format, dict)
            and response_format.get("type") == "json_object"
        )
        if want_json:
            user_msgs.append({"role": "assistant", "content": "{"})

        kwargs = {
            "model": model,
            "messages": user_msgs,
            "max_tokens": 16384,  # 16384 default. Sonnet 4.5 supports up to 64K output tokens.
            "temperature": temperature,
        }
        if system_msg:
            kwargs["system"] = system_msg

        resp = client.messages.create(**kwargs)
        text = resp.content[0].text

        # Re-attach the prefilled `{` so the caller sees a complete JSON object.
        # Guard against the rare case where Claude already emitted its own `{`.
        if want_json and not text.lstrip().startswith("{"):
            text = "{" + text

        input_tokens = resp.usage.input_tokens or 0
        output_tokens = resp.usage.output_tokens or 0
        return text, input_tokens, output_tokens


_PROVIDERS: dict[str, LLMProvider] = {
    "openai": cast(LLMProvider, OpenAIProvider()),
    "anthropic": cast(LLMProvider, AnthropicProvider()),
    "llama": cast(LLMProvider, OpenRouterProvider()),
}


def get_provider(model_family: str) -> LLMProvider:
    family = model_family.lower()
    if family in ("mistral",):
        raise ValueError(
            f"Model family '{model_family}' is coming soon. Please configure TOGETHER_API_KEY in the future."
        )
    if family not in _PROVIDERS:
        raise ValueError(f"Unknown model family: {model_family}")
    return _PROVIDERS[family]


def map_model(model_family: str, model: str) -> str:
    """
    Map generic model names to provider-specific model strings.
    """
    family = model_family.lower()
    if family == "openai":
        if "gpt" in model:
            return model
        if "mini" in model:
            return settings.openai_model_mini
        return settings.openai_model
    elif family == "anthropic":
        if "claude" in model:
            return model
        if "mini" in model:
            return settings.anthropic_mini_model
        return settings.anthropic_default_model
    elif family == "llama":
        if "mini" in model:
            return settings.openrouter_model_mini
        return settings.openrouter_model
    elif family == "mistral":
        return "mistralai/Mistral-Large"
    return model


def complete_with_fallback(
    model_family: str,
    messages: list[dict[str, str]],
    model: str,
    temperature: float,
    response_format: dict[str, str] | None = None,
) -> tuple[str, int, int, str]:
    """
    Execute an LLM completion against the user-selected family. On rate-limit /
    auth / quota errors, silently swap to the other supported provider so the
    pipeline can complete instead of failing mid-run.

    Behavior contract:
      • Primary provider call succeeds       → return (content, p_tokens, c_tokens, family)
      • Primary fails with retryable error   → emit "provider_fallback" SSE event,
                                                try the other family, update the
                                                thread-local run-family context so
                                                subsequent agents in the same run
                                                use the fallback too
      • Both providers fail                  → raise QuotaExceededError
      • Non-retryable error (e.g. malformed  → propagate the original exception
        request)                               unchanged (no fallback)

    UI handling (frontend responsibility):
      The "provider_fallback" event is consumed by the React frontend's useSSE
      hook, which surfaces:
        (a) a Sonner toast ("X quota exceeded - using Y for this run")
        (b) a persistent inline banner above the artifacts

    Cost attribution:
      The (input_tokens, output_tokens) returned reflect the FALLBACK provider's
      counts. base_agent.add_cost() uses the fallback family's pricing too - so
      the per-run cost is accurate for whichever provider actually executed.

    Returns:
        Tuple: (response_content, prompt_tokens, completion_tokens, final_family)
        final_family may differ from input model_family if a fallback happened.
    """
    import anthropic
    import httpx
    import openai

    from src.core.events import emit
    from src.core.logger import get_logger
    from src.core.resilience import QuotaExceededError

    log = get_logger(__name__)

    family = model_family.lower()

    from src.core.config import settings

    enable_fallback = settings.enable_provider_fallback
    try:
        from src.agents.base_agent import _current_enable_fallback

        enable_fallback = _current_enable_fallback()
    except Exception:
        pass

    if not enable_fallback or family not in ("openai", "anthropic"):
        # Just call the chosen provider; let exceptions surface
        provider = get_provider(family)
        mapped_model = map_model(family, model)
        if family == "llama":
            import time

            try:
                content, p, c = provider.complete(messages, mapped_model, temperature, response_format)
                return content, p, c, family
            except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError) as e:
                log.warning(f"OpenRouter primary call failed: {e}. Sleeping 1.5s and retrying once...")
                time.sleep(1.5)
                try:
                    content, p, c = provider.complete(messages, mapped_model, temperature, response_format)
                    return content, p, c, family
                except Exception as retry_exc:
                    log.error(f"OpenRouter retry also failed: {retry_exc}")
                    raise QuotaExceededError(
                        "Your API Credits/Tokens has expired or reached limit. Please try again later. Sorry."
                    ) from retry_exc
        else:
            content, p, c = provider.complete(messages, mapped_model, temperature, response_format)
            return content, p, c, family

    fallback_family = "anthropic" if family == "openai" else "openai"

    try:
        provider = get_provider(family)
        mapped_model = map_model(family, model)
        content, p, c = provider.complete(messages, mapped_model, temperature, response_format)
        return content, p, c, family

    except (
        openai.RateLimitError,
        openai.AuthenticationError,
        openai.APIStatusError,
        openai.APITimeoutError,
        openai.APIConnectionError,
        anthropic.RateLimitError,
        anthropic.AuthenticationError,
        anthropic.APIStatusError,
        anthropic.APITimeoutError,
        anthropic.APIConnectionError,
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ConnectTimeout,
        TimeoutError,
        ValueError,  # missing API key configuration
    ) as e:
        log.warning(
            f"Primary provider '{family}' failed with limit/credential/timeout error: {e}. "
            f"Attempting automatic fallback to '{fallback_family}'..."
        )
        # Emit event to the UI
        emit("provider_fallback", from_family=family, to_family=fallback_family, reason=str(e))

        try:
            fallback_provider = get_provider(fallback_family)
            fallback_model = map_model(fallback_family, model)
            content, p, c = fallback_provider.complete(messages, fallback_model, temperature, response_format)

            # Propagate the fallback decision so SUBSEQUENT LLM calls in this same
            # run (e.g. the Critic that runs after the specialists, or a revision
            # cycle) also use the fallback provider. Without this update the next
            # call would re-try the original failing family and hit the same error.
            #
            # We update BOTH:
            #   • _CURRENT_RUN (thread-local) - for calls on this same thread
            #   • _RUN_FAMILY[rid] (module-level dict) - for cross-thread visibility
            #     since LangGraph dispatches specialists via ThreadPoolExecutor
            #
            # Wrapped in try/except because observability MUST NOT cascade failures:
            # if base_agent's exports change, this stays silent rather than masking
            # the original LLM error we just recovered from.
            try:
                from src.agents.base_agent import _CURRENT_RUN, _RUN_FAMILY, _TOKEN_LOCK

                if hasattr(_CURRENT_RUN, "model_family"):
                    _CURRENT_RUN.model_family = fallback_family
                rid = getattr(_CURRENT_RUN, "run_id", None)
                if rid:
                    with _TOKEN_LOCK:
                        _RUN_FAMILY[rid] = fallback_family
            except Exception:
                pass

            return content, p, c, fallback_family
        except Exception as fallback_exc:
            log.error(f"Fallback provider '{fallback_family}' also failed: {fallback_exc}")
            raise QuotaExceededError(
                "Your API Credits/Tokens has expired or reached limit. Please try again later. Sorry."
            ) from fallback_exc
