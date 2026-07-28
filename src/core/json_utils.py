# src/core/json_utils.py
"""
Defensive JSON extraction for LLM completions.

OpenAI's `response_format={"type": "json_object"}` is enforced server-side, and
the Anthropic provider uses a documented assistant-turn prefill (`{`) to force
JSON-first output. Neither guarantee exists for the `llama` family: OpenRouter
forwards `response_format` to whichever underlying provider it routes to, and
that provider may ignore it - returning prose, or JSON wrapped in a markdown
code fence (```json ... ```), instead of a raw JSON object.

`json.loads()` on that kind of response fails immediately with
`Expecting value: line 1 column 1 (char 0)` - the classic signature of a
string that doesn't start with `{` or `[`. Every agent previously called
`json.loads(raw)` directly, so any non-compliant response silently triggered
that agent's degraded fallback path.

`parse_llm_json()` is a drop-in replacement: try strict parsing first (cheap,
correct for well-behaved providers), then fall back to stripping markdown
fences and extracting the first top-level `{...}` object before parsing again.
"""

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_llm_json(raw: str) -> dict:
    """
    Parse an LLM completion as JSON, tolerating common non-compliant formats
    (markdown-fenced JSON, leading/trailing prose around a JSON object).

    Raises json.JSONDecodeError (same as json.loads) if no valid JSON object
    can be recovered, so existing except-json.JSONDecodeError fallback paths
    in callers keep working unchanged.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    text = raw.strip()

    # Strip a ```json ... ``` or ``` ... ``` fence if present.
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

    # Last resort: grab the first top-level {...} object out of surrounding
    # prose (e.g. "Here is the plan:\n\n{...}\n\nLet me know if...").
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        return json.loads(candidate)

    # Nothing recoverable - raise the original error shape so callers'
    # `except json.JSONDecodeError` fallback paths trigger as before.
    return json.loads(raw)
