"""Shared code-block extraction helpers for benchmark scripts."""

import re


def extract_code_block(response: str, language: str = "") -> str:
    """Extract a fenced code block from an LLM response.

    Args:
        response: The raw LLM response text.
        language: Optional language tag to look for (e.g. "python", "json").
                  When given, tries language-specific fences first.
    """
    # Try language-specific fences first (e.g. ```python or ```json)
    if language:
        aliases = {"python": "python|py"}.get(language, language)
        pattern = re.compile(rf"```(?:{aliases})\s*\n(.*?)```", re.DOTALL)
        match = pattern.search(response)
        if match:
            return match.group(1).strip()

    # Try generic ``` fences (no language tag)
    pattern_generic = re.compile(r"```\s*\n(.*?)```", re.DOTALL)
    match_generic = pattern_generic.search(response)
    if match_generic:
        return match_generic.group(1).strip()

    # Try unclosed fence (model started a code block but didn't close it)
    if language:
        aliases = {"python": "python|py"}.get(language, language)
        unclosed = re.compile(rf"```(?:{aliases})?\s*\n(.*)", re.DOTALL)
    else:
        unclosed = re.compile(r"```\s*\n(.*)", re.DOTALL)
    match_unclosed = unclosed.search(response)
    if match_unclosed:
        return match_unclosed.group(1).strip()

    # Last resort: if the response looks like bare code (starts with [)
    stripped = response.strip()
    if stripped.startswith("["):
        return stripped

    return ""


def extract_python_code_block(response: str) -> str:
    """Extract a Python code block from an LLM response."""
    return extract_code_block(response, language="python")


def extract_json_block(response: str) -> str:
    """Extract a JSON code block from an LLM response."""
    return extract_code_block(response, language="json")
