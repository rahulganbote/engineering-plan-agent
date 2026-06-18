# src/core/pricing.py
"""
Pricing table and helper to calculate total USD cost from token counts.
"""

PRICING_TABLE = {
    "openai": {
        "gpt-4o": {"input": 2.50 / 1e6, "output": 10.00 / 1e6},
        "gpt-4o-mini": {"input": 0.150 / 1e6, "output": 0.600 / 1e6},
    },
    "anthropic": {
        "claude-3-5-sonnet-latest": {"input": 3.00 / 1e6, "output": 15.00 / 1e6},
        "claude-3-5-sonnet-20241022": {"input": 3.00 / 1e6, "output": 15.00 / 1e6},
        "claude-3-5-haiku-latest": {"input": 0.80 / 1e6, "output": 4.00 / 1e6},
        "claude-3-5-haiku-20241022": {"input": 0.80 / 1e6, "output": 4.00 / 1e6},
    },
    "llama": {
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": {"input": 0.60 / 1e6, "output": 0.60 / 1e6},
    },
    "mistral": {
        "mistralai/Mistral-Large": {"input": 2.00 / 1e6, "output": 6.00 / 1e6},
    }
}


def calculate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate the cost of an LLM call in USD.
    """
    p = provider.lower()
    if p not in PRICING_TABLE:
        return 0.0

    models = PRICING_TABLE[p]
    if model in models:
        rates = models[model]
    else:
        # Fallback to the first model's rates for this provider if model is a custom string or mismatch
        rates = next(iter(models.values()))

    cost = (input_tokens * rates["input"]) + (output_tokens * rates["output"])
    return round(cost, 6)
