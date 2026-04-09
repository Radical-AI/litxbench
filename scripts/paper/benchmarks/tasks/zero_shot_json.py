"""Full experiment extraction benchmark (zero-shot, JSON output).

Mirrors ``zero_shot.py`` but asks the LLM to produce JSON instead of Python
code.  Parse errors and construction failures are reported with JSON-path
annotations so the LLM can locate and fix its mistakes.
"""

from pydantic_ai import Agent

from litxbench.core.utils import load_transcribed_paper_text_only
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import Experiment
from scripts.paper.benchmarks.helpers.block_extraction import extract_json_block
from scripts.paper.benchmarks.helpers.extraction_runner import (
    ExperimentBenchmarkConfig,
    configure_logfire,
    make_extract_worker,
    run_parallel,
    run_standard_benchmark,
)
from scripts.paper.benchmarks.helpers.json_prompts import (
    PromptConfig,
    available_types_json,
    composition_helpers_json,
    example_experiment_shape_json,
    field_instructions_json,
)
from scripts.paper.benchmarks.helpers.json_to_experiments import (
    JsonConversionError,
    parse_and_construct,
)
from scripts.paper.benchmarks.helpers.prompts import scope_rules
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
)
from scripts.paper.benchmarks.helpers.retry_loop import (
    JSON_RETRY_MESSAGES,
    RetryableError,
    run_extraction_loop,
)

configure_logfire()


# ---------------------------------------------------------------------------
# JSON process_response callback
# ---------------------------------------------------------------------------


def _json_process_response(json_str: str, pc: PromptConfig) -> list[Experiment]:
    """Parse JSON and construct Experiment objects, raising RetryableError on failure."""
    try:
        experiments = parse_and_construct(json_str, pc)
    except ValueError as exc:
        raise RetryableError(str(exc)) from exc
    except TypeError as exc:
        raise RetryableError(str(exc)) from exc
    except JsonConversionError as exc:
        raise RetryableError(
            f"Error at {exc.path}: {exc.message}\nFix this location and return the full corrected JSON."
        ) from exc
    except Exception as exc:
        raise RetryableError(
            f"An error occurred while constructing experiments from your JSON:\n{exc}\n"
            f"Fix and return the full corrected JSON."
        ) from exc
    if not isinstance(experiments, list) or not all(isinstance(e, Experiment) for e in experiments):
        raise RetryableError("Output must be a JSON array where every item is a valid experiment object.")
    return experiments


# ---------------------------------------------------------------------------
# Agent extraction
# ---------------------------------------------------------------------------


async def _extract_zero_shot_json(
    doi: str, extraction_agent: Agent, config: ExperimentBenchmarkConfig
) -> ExtractionOutput:
    paper_text = load_transcribed_paper_text_only(doi)
    pc = config.prompt_config
    sections = [
        "Extract experiments from this paper.\n\n"
        + scope_rules()
        + "\n\n"
        + "Return a JSON fenced code block (```json ... ```) containing an array of experiment objects.\n\n"
        + "Use this exact shape:\n\n"
        + example_experiment_shape_json(
            include_source=pc.include_source,
            include_descriptions=pc.include_descriptions_instructions,
        )
        + "\n\n"
        + field_instructions_json(
            include_source=pc.include_source,
            include_descriptions=pc.include_descriptions_instructions,
        )
        + "\n\n"
        + available_types_json(
            include_composition_helpers=pc.include_composition_helpers,
            include_descriptions=pc.include_descriptions_instructions,
        ),
    ]
    if pc.include_composition_helpers:
        sections.append(composition_helpers_json())
    prompt_suffix = "\n\n".join(sections)
    prompt: list[str] = [prompt_suffix, paper_text]

    result = await run_extraction_loop(
        agent=extraction_agent,
        initial_prompt=prompt,
        process_response=lambda json_str: _json_process_response(json_str, pc),
        extract_block=extract_json_block,
        retry_messages=JSON_RETRY_MESSAGES,
        max_retries=20,
        span_name="extract_zero_shot_json",
        doi=doi,
    )

    return ExtractionOutput(
        experiments=result.value,
        prompt_text="\n".join(prompt),
        raw_response=result.raw_response,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        attempts=result.attempts,
        context_resets=result.context_resets,
    )


# ---------------------------------------------------------------------------
# Worker & parallel runner
# ---------------------------------------------------------------------------


_extract_worker = make_extract_worker(_extract_zero_shot_json)


async def extract_experiments_zero_shot_json(
    config: ExperimentBenchmarkConfig,
) -> dict[str, ExtractionOutput]:
    dois = config.dois if config.dois is not None else list(papers.keys())
    return await run_parallel(dois, config.max_workers, _extract_worker, config)


if __name__ == "__main__":
    model_names = [
        # "claude-haiku-4-5",
        # "gpt-5-mini-medium",
        # "gemini-3-flash",
        # "gpt-5-2-high",
        # "claude-opus-4-6",
        # "gemini-3.1-pro",
        "gemini-3.1-flash-lite",
    ]

    run_standard_benchmark(
        model_names=model_names,
        config=ExperimentBenchmarkConfig(name="extract_all_json", dois=["doi_10_1016__j_proeng_2012_03_043"]),
        output_subdir="zero_shot_json",
        extract_fn=extract_experiments_zero_shot_json,
    )
