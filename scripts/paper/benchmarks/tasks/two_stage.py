"""Two-stage experiment extraction benchmark.

Stage 1 (Extraction): An LLM reads the paper and produces a detailed
natural-language description of all experiments — no knowledge of our schema.

Stage 2 (Formatting): A second LLM call takes that description (but NOT the
paper) and converts it into structured output via Python code, with retries for
validation errors.
"""

import time
from dataclasses import dataclass, field

import logfire
from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from litxbench.core.utils import load_transcribed_paper_text_only
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import Experiment
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import execute_experiments_code
from scripts.paper.benchmarks.helpers.extraction_runner import (
    BaseBenchmarkConfig,
    configure_logfire,
    create_default_agent,
    finalize_output,
    run_parallel,
    run_standard_benchmark,
)
from scripts.paper.benchmarks.helpers.prompts import (
    PromptConfig,
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
# Config
# ---------------------------------------------------------------------------


@dataclass
class TwoStageExperimentBenchmarkConfig(BaseBenchmarkConfig):
    """Configuration for the two-stage experiment extraction benchmark."""

    stage2_model_name: str = ""  # Optional separate model for stage 2
    name: str = "extract_two_stage"
    prompt_config: PromptConfig = field(default_factory=PromptConfig)


# ---------------------------------------------------------------------------
# Stage 1: Schema-agnostic extraction
# ---------------------------------------------------------------------------


_STAGE1_MAX_RETRIES = 5  # Only for truncation retries


def _stage1_prompt(paper_text: str) -> list[str]:
    """Build the Stage 1 prompt: extract all experiment details in natural language."""
    instructions = f"""\
Extract a comprehensive, detailed description of ALL experiments from the following paper.

{scope_rules()}

Think of the data in this paper as a directed graph:

- An **experiment** is fundamentally: raw materials → processing steps → resulting material → measured \
properties. Each node depends on the ones before it.
- **Materials form derivation chains**: a base alloy is cast, then one piece is annealed at 700°C \
to become Material A, another piece is cold-rolled to become Material B. These are separate experiments \
that share an upstream node (the cast ingot) but diverge at the processing step.
- **Microstructure is also hierarchical/graph-like**: a material may contain a BCC phase, and within \
that BCC phase there are sub-regions (e.g. a Cr-rich matrix and Cu-rich precipitates). Those \
precipitates may themselves have a specific size, morphology, and composition. Think of phases and \
microstructural features as nested nodes — always clarify what contains what.
- **Properties attach to specific nodes**: a hardness value belongs to a specific material in a \
specific condition; a phase fraction belongs to a specific phase within a specific material.

Use this graph-like mental model to organize your extraction. Make the dependencies and containment \
relationships between entities explicit.

Your output should be a thorough natural-language description covering every detail below. \
Do NOT produce any structured format (no JSON, no tables). Write in clear, organized prose \
with numbered sections for each material/experiment.

For each material or experiment, extract:

1. **Material Identity**
   - Material name/label as used in the paper
   - Nominal composition (exact formula with element ratios, and whether atomic % or weight %)
   - Any measured/actual compositions (from EDS, WDS, ICP, etc.) and how they differ from nominal

2. **Raw Materials**
   - Starting materials (elements, powders, ingots, etc.)
   - Form (ingot, powder, wire, foil, etc.)
   - Purity (e.g. 99.9%, 4N, etc.)
   - Supplier if mentioned

3. **Processing Chain** (in exact chronological order)
   - Every processing step: melting method, casting method, homogenization, rolling, forging, \
annealing, quenching, aging, sintering, HIP, SPS, etc.
   - For each step: temperature, duration, heating/cooling rate, atmosphere (vacuum, argon, air), \
pressure, equipment used
   - Number of repetitions (e.g. "re-melted 5 times")
   - Any intermediate steps (cutting, grinding, polishing between major steps)

4. **Material Derivation Chains**
   - How materials relate to each other: "Material B was made by annealing Material A at 700C for 2h"
   - Which materials share the same base alloy but differ in heat treatment
   - Parent-child relationships between materials

5. **Measured Properties** (ALL of them, with full precision)
   - Property name (hardness, yield strength, tensile strength, elongation, etc.)
   - Exact numeric value as reported in the paper
   - Unit
   - Uncertainty/error bars if reported (e.g. "450 +/- 20 MPa")
   - Whether the value is explicitly stated as a mean/average
   - Whether the value is approximate ("~50", "about 50", "around 50")
   - Whether the value is a bound (">50", "<50", "at least 50", "up to 50")
   - Whether the value is a range ("5-50 um", "between 50 and 180 nm")
   - Testing conditions: temperature, strain rate, load, indentation force, specimen dimensions
   - Measurement method/equipment (e.g. "Instron 5982", "Vickers hardness tester at 500 gf")

6. **Microstructural Features**
   - Phases present: name, crystal structure (BCC, FCC, HCP, B2, L12, sigma, etc.)
   - Lattice parameters from XRD (a, b, c values in Angstroms)
   - Phase fractions (volume %, area %, weight %)
   - Microstructural features: dendrites, interdendritic regions, precipitates, matrix, \
lamellae, eutectic, grain boundaries
   - Hierarchy/nesting: which features are found within which (e.g. "B2 precipitates within \
the FCC matrix phase", "nano-precipitates inside the dendrite arms")
   - Feature sizes: grain size, precipitate size, dendrite arm spacing, lamellar spacing
   - Phase compositions from EDS/WDS (element percentages for each phase/region)

7. **Additional Details**
   - Any phase transformations noted
   - Density measurements
   - Elastic constants (Young's modulus, shear modulus, Poisson's ratio, bulk modulus)
   - Thermal properties (Curie temperature, thermal conductivity, CTE, etc.)
   - Magnetic properties
   - Corrosion properties
   - Any other measured physical properties

Be exhaustive. Include every numeric value reported in the paper for physically fabricated materials. \
Quote values exactly as they appear (preserving significant figures, qualifiers like "~", ">", etc.)."""

    return [instructions, paper_text]


async def _stage1_extract_text(
    doi: str,
    stage1_agent: Agent,
) -> tuple[str, RunUsage]:
    """Run Stage 1: extract natural-language description from paper.

    Handles truncation retries (finish_reason=length) but no schema validation.
    Returns (description_text, usage).
    """
    paper_text = load_transcribed_paper_text_only(doi)
    prompt = _stage1_prompt(paper_text)

    message_history = None
    usage = RunUsage()
    user_prompt: str | list[str] = prompt

    with logfire.span("stage1_extract_text {doi}", doi=doi):
        for attempt in range(_STAGE1_MAX_RETRIES):
            logfire.info("stage1 attempt {attempt} for {doi}", attempt=attempt, doi=doi)
            async with stage1_agent.run_stream(user_prompt, message_history=message_history, usage=usage) as result:
                raw_response = await result.get_output()
                finish_reason = result.response.finish_reason
                result_messages = result.all_messages()

            if finish_reason == "length":
                logfire.warn(
                    "stage1 response truncated (finish_reason=length) for {doi} (attempt {attempt})",
                    doi=doi,
                    attempt=attempt,
                )
                user_prompt = (
                    "Your previous response was truncated because it hit the output token limit. "
                    "Please continue from where you left off. Pick up exactly where you stopped."
                )
                message_history = result_messages
                continue

            logfire.info("stage1 succeeded for {doi} on attempt {attempt}", doi=doi, attempt=attempt)

            # If we had continuation retries, concatenate all assistant responses
            if message_history is not None:
                # Collect all text parts from assistant messages
                from pydantic_ai.messages import ModelResponse, TextPart

                full_text_parts: list[str] = []
                for msg in result_messages:
                    if isinstance(msg, ModelResponse):
                        for part in msg.parts:
                            if isinstance(part, TextPart):
                                full_text_parts.append(part.content)
                raw_response = "\n".join(full_text_parts)

            return raw_response, usage

        # If all retries exhausted due to truncation, return what we have
        logfire.warn("stage1 retries exhausted for {doi}, returning truncated response", doi=doi)
        if message_history is not None:
            from pydantic_ai.messages import ModelResponse, TextPart

            full_text_parts = []
            for msg in result_messages:
                if isinstance(msg, ModelResponse):
                    for part in msg.parts:
                        if isinstance(part, TextPart):
                            full_text_parts.append(part.content)
            raw_response = "\n".join(full_text_parts)

        return raw_response, usage


# ---------------------------------------------------------------------------
# Stage 2: Convert to Python code
# ---------------------------------------------------------------------------


async def _stage2_convert_to_code(
    doi: str,
    description: str,
    stage2_agent: Agent,
    config: TwoStageExperimentBenchmarkConfig,
) -> tuple[list[Experiment], str, RunUsage, int]:
    """Run Stage 2: convert natural-language description to structured output via Python code.

    Returns (experiments, raw_response, usage, context_resets).
    """
    pc = config.prompt_config
    sections = [
        "Here is a detailed description of experiments extracted from a scientific paper. "
        "Convert this into the structured format specified below.\n\n"
        "Return a Python fenced code block (```python ... ```) containing a single expression that evaluates to a `list[Experiment]`.\n\n"
        "Use this exact shape:\n\n"
        + example_experiment_shape(
            include_source=pc.include_source,
            include_descriptions=pc.include_descriptions_instructions,
        )
        + "\n\n"
        + field_instructions(
            include_source=pc.include_source,
            include_descriptions=pc.include_descriptions_instructions,
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
    prompt: list[str] = [prompt_suffix, description]

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
        return experiments

    result = await run_extraction_loop(
        agent=stage2_agent,
        initial_prompt=prompt,
        process_response=process_response,
        extract_block=extract_python_code_block,
        retry_messages=PYTHON_RETRY_MESSAGES,
        max_retries=20,
        span_name="stage2_convert_to_code",
        doi=doi,
    )

    return result.value, result.raw_response, result.usage, result.context_resets


# ---------------------------------------------------------------------------
# Combined two-stage extraction
# ---------------------------------------------------------------------------


async def _extract_two_stage(
    doi: str,
    stage1_agent: Agent,
    stage2_agent: Agent,
    config: TwoStageExperimentBenchmarkConfig,
) -> ExtractionOutput:
    """Run both stages and return a combined ExtractionOutput."""

    # Stage 1: Extract text
    description, stage1_usage = await _stage1_extract_text(doi, stage1_agent)

    # Stage 2: Convert to code
    experiments, stage2_raw, stage2_usage, stage2_context_resets = await _stage2_convert_to_code(
        doi, description, stage2_agent, config
    )

    # Combine token counts
    total_input = stage1_usage.input_tokens + stage2_usage.input_tokens
    total_output = stage1_usage.output_tokens + stage2_usage.output_tokens

    # Build combined raw_response showing both stages
    combined_raw = (
        "=== STAGE 1: Natural Language Extraction ===\n\n"
        + description
        + "\n\n=== STAGE 2: Code Conversion ===\n\n"
        + stage2_raw
    )

    paper_text = load_transcribed_paper_text_only(doi)
    prompt_lines = _stage1_prompt(paper_text)

    return ExtractionOutput(
        experiments=experiments,
        prompt_text="\n".join(prompt_lines),
        raw_response=combined_raw,
        input_tokens=total_input,
        output_tokens=total_output,
        context_resets=stage2_context_resets,
    )


# ---------------------------------------------------------------------------
# Worker & parallel runner
# ---------------------------------------------------------------------------


async def _extract_worker(doi: str, config: TwoStageExperimentBenchmarkConfig) -> tuple[str, ExtractionOutput]:
    stage1_agent = create_default_agent(config.model_name)

    # Stage 2 model (same or different)
    stage2_model_name = config.stage2_model_name or config.model_name
    stage2_agent = create_default_agent(stage2_model_name)

    start = time.monotonic()
    output = await _extract_two_stage(doi, stage1_agent, stage2_agent, config)
    finalize_output(output, config.model_name, start)
    return doi, output


async def extract_experiments_two_stage(
    config: TwoStageExperimentBenchmarkConfig,
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
    dois = ["doi_10_1016__j_proeng_2012_03_043"]

    run_standard_benchmark(
        model_names=model_names,
        config=TwoStageExperimentBenchmarkConfig(dois=dois),
        output_subdir="two_stage",
        extract_fn=extract_experiments_two_stage,
    )
