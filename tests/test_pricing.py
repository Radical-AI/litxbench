"""Tests for benchmark cost accounting.

These require the ``paper`` extra (genai-prices, pydantic-ai) and are skipped
when it is not installed.
"""

import pytest

pytest.importorskip("genai_prices")
pytest.importorskip("pydantic_ai")

from scripts.paper.benchmarks.helpers.pricing import resolve_genai_price_params  # noqa: E402


@pytest.mark.parametrize(
    ("config_model_name", "expected_ref", "expected_provider"),
    [
        # Exact entries in _GPT_MODEL_REF_MAP must win over the "gpt-5" prefix
        # fallback so each variant is billed at its own rate, not base gpt-5.
        ("gpt-5-mini-medium", "gpt-5-mini", "openai"),
        ("gpt-5-mini-minimal", "gpt-5-mini", "openai"),
        ("gpt-5-2-high", "gpt-5-2", "openai"),
        ("gpt-5-2-medium", "gpt-5-2", "openai"),
        ("gpt-5-2-xhigh", "gpt-5-2", "openai"),
        ("gpt-5-pro-high", "gpt-5-pro", "openai"),
        ("gpt-5-1-low", "gpt-5-1", "openai"),
        # Base gpt-5 reasoning-effort variants all bill at the base gpt-5 rate.
        ("gpt-5-minimal", "gpt-5", "openai"),
        ("gpt-5-low", "gpt-5", "openai"),
        ("gpt-5-medium", "gpt-5", "openai"),
        ("gpt-5-high", "gpt-5", "openai"),
        ("gpt-4o", "gpt-4o", "openai"),
        # Other providers pass through / map as before.
        ("claude-opus-4-6", "claude-opus-4-6", "anthropic"),
        ("gemini-3-flash", "gemini-3-flash-preview", "google"),
    ],
)
def test_model_names_resolve_to_their_own_price_ref(
    config_model_name: str, expected_ref: str, expected_provider: str
) -> None:
    assert resolve_genai_price_params(config_model_name) == (expected_ref, expected_provider)


@pytest.mark.parametrize("unknown_name", ["gpt-5-hypothetical", "gpt-6", "llama-3-70b", ""])
def test_unknown_model_names_raise(unknown_name: str) -> None:
    """Unknown models must raise instead of silently billing at base gpt-5 (or zero) rates."""
    with pytest.raises(ValueError, match="No pricing mapping"):
        resolve_genai_price_params(unknown_name)


def test_gpt5_variants_are_not_all_billed_at_base_rate() -> None:
    """Regression test: the gpt-5 prefix fallback must not shadow the exact-name map."""
    refs = {
        name: resolve_genai_price_params(name)[0]
        for name in ("gpt-5-mini-medium", "gpt-5-2-high", "gpt-5-pro-high")
    }
    assert set(refs.values()) == {"gpt-5-mini", "gpt-5-2", "gpt-5-pro"}
