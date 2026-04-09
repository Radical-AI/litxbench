"""Full experiment extraction benchmark (zero-shot).

Tests how well LLMs can extract complete Experiment objects (compositions,
measurements, processing steps) from a paper.  The LLM must write Python
code whose output is a list[Experiment].
"""

from pydantic_ai import Agent

from litxbench.core.utils import load_transcribed_paper_text_only
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import Experiment
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import execute_experiments_code
from scripts.paper.benchmarks.helpers.extraction_runner import (
    ExperimentBenchmarkConfig,
    configure_logfire,
    make_extract_worker,
    run_parallel,
    run_standard_benchmark,
)
from scripts.paper.benchmarks.helpers.prompts import (
    available_names,
    composition_helpers,
    example_experiment_shape,
    field_instructions,
    normalize_function,
    scope_rules,
)
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
)
from scripts.paper.benchmarks.helpers.retry_loop import (
    PYTHON_RETRY_MESSAGES,
    RetryableError,
    run_extraction_loop,
)

configure_logfire()


# ---------------------------------------------------------------------------
# Agent extraction
# ---------------------------------------------------------------------------


async def _extract_zero_shot(
    doi: str, extraction_agent: Agent, config: ExperimentBenchmarkConfig, *, linear: bool = False
) -> ExtractionOutput:
    paper_text = load_transcribed_paper_text_only(doi)
    pc = config.prompt_config

    sections = [
        "Extract experiments from this paper.\n\n"
        + scope_rules()
        + "\n\n"
        + "Return a Python fenced code block (```python ... ```) containing a single expression that evaluates to a `list[Experiment]`.\n\n"
        + "Use this exact shape:\n\n"
        + example_experiment_shape(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions, linear=linear
        )
        + "\n\n"
        + field_instructions(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions, linear=linear
        )
        + "\n\n"
        + available_names(
            include_composition_helpers=pc.include_composition_helpers,
            include_normalize_function=pc.include_normalize_function,
            include_descriptions=pc.include_descriptions_instructions,
        ),
    ]
    if pc.include_composition_helpers:
        sections.append(composition_helpers())
    if pc.include_normalize_function:
        sections.append(normalize_function())
    prompt_suffix = "\n\n".join(sections)
    prompt: list[str] = [prompt_suffix, paper_text]

    def process_response(code: str) -> list[Experiment]:
        try:
            experiments = execute_experiments_code(code, pc)
        except Exception as exc:
            raise RetryableError(
                f"The generated Python expression failed at runtime. Fix it and try again.\nExecution error:\n{exc}"
            ) from exc
        if not isinstance(experiments, list) or not all(isinstance(e, Experiment) for e in experiments):
            raise RetryableError(
                "Output must evaluate to a list[Experiment]. Every list item must be an Experiment object."
            )
        if linear:
            _validate_linear(experiments)
        return experiments

    result = await run_extraction_loop(
        agent=extraction_agent,
        initial_prompt=prompt,
        process_response=process_response,
        extract_block=extract_python_code_block,
        retry_messages=PYTHON_RETRY_MESSAGES,
        max_retries=10,
        span_name="extract_zero_shot_linear" if linear else "extract_zero_shot",
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


def _validate_linear(experiments: list[Experiment]) -> None:
    """Raise RetryableError if any material references another material instead of raw materials."""
    for exp in experiments:
        raw_mat_names = set(exp.raw_materials.keys())
        material_names = {m.name for m in exp.output_materials if m.name}
        for material in exp.output_materials:
            if material.process_steps is None:
                continue
            first_step = material.process_steps[0]
            for inp in first_step.inputs:
                if inp in material_names and inp not in raw_mat_names:
                    raise RetryableError(
                        f"Linear mode violation: material process input '{inp}' references another material. "
                        f"Each material must describe its complete process chain from raw materials. "
                        f"Replace '{inp}' with the full chain from raw materials (e.g. 'elements->creation->...')."
                    )


_extract_worker = make_extract_worker(_extract_zero_shot)


async def extract_experiments_zero_shot(
    config: ExperimentBenchmarkConfig,
) -> dict[str, ExtractionOutput]:
    dois = config.dois if config.dois is not None else list(papers.keys())
    return await run_parallel(dois, config.max_workers, _extract_worker, config)


if __name__ == "__main__":
    model_names = [
        # "claude-haiku-4-5",
        # "gpt-5-mini-medium",
        # "gemini-3.1-flash-lite",
        # "gemini-3-flash",
        # "claude-opus-4-6",
        # "gpt-5-2-high",
        # "gemini-3.1-pro",
        "gemini-3.1-flash-lite",
    ]
    # dois = list(papers.keys())[:3]
    dois = ["doi_10_3390__ma12071136"]

    run_standard_benchmark(
        model_names=model_names,
        config=ExperimentBenchmarkConfig(name="extract_all", dois=dois),
        output_subdir="zero_shot",
        extract_fn=extract_experiments_zero_shot,
    )
