# src/core/providers.py
import os
from typing import Protocol, Type, Dict, Tuple, List, Optional
import openai
import anthropic
from src.core.config import settings
from langsmith.wrappers import wrap_openai


class LLMProvider(Protocol):
    def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, int, int]:
        """
        Send a completion request.
        Returns: (response_text, input_tokens, output_tokens)
        """
        ...


class OpenAIProvider:
    def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, int, int]:
        client = wrap_openai(openai.OpenAI(api_key=settings.openai_api_key))
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


class AnthropicProvider:
    def complete(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        response_format: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, int, int]:
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key is not configured. Please set ANTHROPIC_API_KEY.")

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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
            "max_tokens": 8192,
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


_PROVIDERS: Dict[str, LLMProvider] = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
}


def get_provider(model_family: str) -> LLMProvider:
    family = model_family.lower()
    if family in ("llama", "mistral"):
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
        return "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo"
    elif family == "mistral":
        return "mistralai/Mistral-Large"
    return model


def complete_with_fallback(
    model_family: str,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    response_format: Optional[Dict[str, str]] = None,
) -> Tuple[str, int, int, str]:
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
        (a) a Sonner toast ("X quota exceeded — using Y for this run")
        (b) a persistent inline banner above the artifacts

    Cost attribution:
      The (input_tokens, output_tokens) returned reflect the FALLBACK provider's
      counts. base_agent.add_cost() uses the fallback family's pricing too — so
      the per-run cost is accurate for whichever provider actually executed.

    Returns:
        Tuple: (response_content, prompt_tokens, completion_tokens, final_family)
        final_family may differ from input model_family if a fallback happened.
    """
    from src.core.logger import get_logger
    from src.core.events import emit
    from src.core.resilience import QuotaExceededError
    import openai
    import anthropic

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
        anthropic.RateLimitError,
        anthropic.AuthenticationError,
        anthropic.APIStatusError,
        ValueError,  # missing API key configuration
    ) as e:
        log.warning(
            f"Primary provider '{family}' failed with limit/credential error: {e}. "
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
            #   • _CURRENT_RUN (thread-local) — for calls on this same thread
            #   • _RUN_FAMILY[rid] (module-level dict) — for cross-thread visibility
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

