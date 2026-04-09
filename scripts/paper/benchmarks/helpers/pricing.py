"""Shared pricing helpers for benchmark scripts."""

from genai_prices import calc_price
from pydantic_ai.usage import RunUsage

_GPT_MODEL_REF_MAP: dict[str, str] = {
    "gpt-5-medium": "gpt-5",
    "gpt-5-pro-high": "gpt-5",
    "gpt-5-1-low": "gpt-5-1",
    "gpt-5-1-medium": "gpt-5-1",
    "gpt-5-2-medium": "gpt-5-2",
    "gpt-5-2-high": "gpt-5-2",
    "gpt-5-2-xhigh": "gpt-5-2",
    "gpt-4o": "gpt-4o",
    "gpt-5-mini-minimal": "gpt-5-mini",
    "gpt-5-mini-medium": "gpt-5-mini",
}

_GEMINI_MODEL_REF_MAP: dict[str, str] = {
    "gemini-3-flash": "gemini-3-flash-preview",
    "gemini-3.1-pro": "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite": "gemini-3.1-flash-lite-preview",
}


def resolve_genai_price_params(config_model_name: str) -> tuple[str, str] | None:
    """Map a config model name to ``(model_ref, provider_id)`` for :func:`genai_prices.calc_price`."""
    if config_model_name.startswith("claude-"):
        return config_model_name, "anthropic"
    if config_model_name in _GEMINI_MODEL_REF_MAP:
        return _GEMINI_MODEL_REF_MAP[config_model_name], "google"
    if config_model_name.startswith("gemini-"):
        return config_model_name, "google"
    if config_model_name.startswith("gpt-5"):
        return "gpt-5", "openai"
    if config_model_name in _GPT_MODEL_REF_MAP:
        return _GPT_MODEL_REF_MAP[config_model_name], "openai"
    return None


def compute_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a model invocation. Returns 0.0 on failure."""
    price_params = resolve_genai_price_params(model_name)
    if price_params is None:
        return 0.0
    try:
        usage = RunUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        price = calc_price(usage, price_params[0], provider_id=price_params[1])
        return float(price.total_price)
    except Exception:
        return 0.0
