"""Generic streaming retry loop for LLM extraction benchmarks.

Extracts the shared retry pattern used by zero_shot, zero_shot_json,
two_stage, assemble_graph, and process_zero_shot benchmarks.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

import logfire
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

T = TypeVar("T")


class RetryableError(Exception):
    """Raised by a ``process_response`` callback to trigger a retry.

    The exception message is sent back to the LLM as the next user prompt.
    """


@dataclass(frozen=True)
class RetryMessages:
    """Canned messages for the two non-callback retry paths."""

    truncation_message: str
    missing_block_message: str


PYTHON_RETRY_MESSAGES = RetryMessages(
    truncation_message=(
        "Your previous response was truncated because it hit the output token limit. "
        "You MUST produce a shorter response. Strategies:\n"
        "- Remove ALL comments and docstrings from the code\n"
        "- Use compact formatting (single-line constructor calls where possible)\n"
        "- Omit optional/None fields entirely\n"
        "- If there are many experiments, still include ALL of them but make each one as terse as possible\n\n"
        "Return ONLY the ```python ... ``` code block, nothing else."
    ),
    missing_block_message=(
        "Could not find a Python code block in your response. "
        "Your ENTIRE response must be a single fenced code block like:\n\n"
        "```python\n[\n    Experiment(...),\n]\n```\n\n"
        "Do NOT include any text, explanation, or markdown outside the code fence."
    ),
)

JSON_RETRY_MESSAGES = RetryMessages(
    truncation_message=(
        "Your previous response was truncated because it hit the output token limit. "
        "You MUST produce a shorter response. Strategies:\n"
        "- Remove null fields — omit any field that would be null\n"
        "- Use compact JSON (no unnecessary whitespace)\n"
        "- Omit optional fields entirely\n"
        "- If there are many experiments, still include ALL of them but make each one as terse as possible\n\n"
        "Return ONLY the ```json ... ``` code block, nothing else."
    ),
    missing_block_message=(
        "Could not find a JSON code block in your response. "
        "Wrap your output in ```json ... ```. "
        "Your ENTIRE response must be a single fenced code block like:\n\n"
        '```json\n[\n  {"raw_materials": {...}, ...}\n]\n```\n\n'
        "Do NOT include any text, explanation, or markdown outside the code fence."
    ),
)


@dataclass
class RetryLoopResult(Generic[T]):
    """Result returned by :func:`run_extraction_loop` on success."""

    value: T
    raw_response: str
    usage: RunUsage
    attempts: int
    context_resets: int = 0


async def run_extraction_loop(
    *,
    agent: Agent,
    initial_prompt: str | list[str],
    process_response: Callable[[str], T],
    extract_block: Callable[[str], str],
    retry_messages: RetryMessages,
    max_retries: int = 10,
    max_context_resets: int = 1,
    span_name: str = "extraction",
    doi: str = "",
) -> RetryLoopResult[T]:
    """Run a streaming LLM call with automatic retries.

    Parameters
    ----------
    agent:
        The pydantic-ai Agent to call.
    initial_prompt:
        First user prompt (typically instructions + paper text).
    process_response:
        Callback ``(block_str) -> T``.  Must raise :class:`RetryableError`
        for any recoverable failure; its message becomes the next user prompt.
    extract_block:
        Callable that pulls the relevant code/JSON block out of the raw
        response text (e.g. ``extract_python_code_block``).
    retry_messages:
        Canned messages for truncation and missing-block retries.
    max_retries:
        Maximum number of LLM round-trips before giving up.
    max_context_resets:
        After exhausting all retries, reset the context (clear chat history)
        and start fresh, up to this many times.  Useful when accumulated
        error messages poison the conversation.
    span_name:
        Logfire span name for tracing.
    doi:
        DOI string used in log messages.
    """
    total_attempts = 0
    usage = RunUsage()

    with logfire.span("{span_name} {doi}", span_name=span_name, doi=doi):
        for context_reset in range(max_context_resets + 1):
            if context_reset > 0:
                logfire.warn(
                    "resetting context for {doi} (context reset {context_reset}/{max_context_resets})",
                    doi=doi,
                    context_reset=context_reset,
                    max_context_resets=max_context_resets,
                )

            message_history = None
            user_prompt: str | list[str] = initial_prompt

            for attempt in range(max_retries):
                total_attempts += 1
                logfire.info("attempt {attempt} for {doi}", attempt=total_attempts - 1, doi=doi)
                # On retries with message history, Gemini thinking models need
                # thinking_config set explicitly so the API accepts thought
                # parts in the conversation history.
                retry_settings = (
                    {"google_thinking_config": {"include_thoughts": True}} if message_history is not None else None
                )
                async with agent.run_stream(
                    user_prompt,
                    message_history=message_history,
                    usage=usage,
                    model_settings=retry_settings,
                ) as result:
                    raw_response = await result.get_output()
                    finish_reason = result.response.finish_reason
                    result_messages = result.all_messages()

                if finish_reason == "length":
                    logfire.warn(
                        "response truncated (finish_reason=length) for {doi} (attempt {attempt})",
                        doi=doi,
                        attempt=total_attempts - 1,
                    )
                    user_prompt = retry_messages.truncation_message
                    message_history = result_messages
                    continue

                block = extract_block(raw_response)
                if not block:
                    logfire.warn(
                        "no block found in response for {doi} (attempt {attempt})",
                        doi=doi,
                        attempt=total_attempts - 1,
                    )
                    user_prompt = retry_messages.missing_block_message
                    message_history = result_messages
                    continue

                try:
                    value = process_response(block)
                except RetryableError as exc:
                    logfire.warn(
                        "processing failed for {doi} (attempt {attempt}): {error}",
                        doi=doi,
                        attempt=total_attempts - 1,
                        error=str(exc),
                    )
                    user_prompt = str(exc)
                    message_history = result_messages
                    continue

                logfire.info(
                    "extraction succeeded for {doi} on attempt {attempt}",
                    doi=doi,
                    attempt=total_attempts - 1,
                )
                return RetryLoopResult(
                    value=value,
                    raw_response=raw_response,
                    usage=usage,
                    attempts=total_attempts,
                    context_resets=context_reset,
                )

            logfire.error(
                "all {max_retries} retries exhausted for {doi}",
                max_retries=max_retries,
                doi=doi,
            )

        raise RuntimeError(f"Failed after {total_attempts} attempts ({max_context_resets} context resets) for {doi}")
