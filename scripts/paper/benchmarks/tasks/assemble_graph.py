"""Assemble-graph benchmark: reconstruct experiment structure from mixed values.

Given the paper text AND all extracted ground truth values (disconnected from
their original structure), the LLM must reconstruct the relationships —
figure out which measurements belong to which material, which process events
form which synthesis chain, and assemble the full Experiment graph.

This isolates "structural reasoning" from "value extraction".
"""

import hashlib
import random
import time

from pydantic_ai import Agent

from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
    ProcessEvent,
    RawMaterial,
)
from litxbench.core.utils import load_transcribed_paper_text_only
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import Experiment
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import execute_experiments_code
from scripts.paper.benchmarks.helpers.extraction_runner import (
    ExperimentBenchmarkConfig,
    configure_logfire,
    create_default_agent,
    finalize_output,
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
# Ground-truth mixing
# ---------------------------------------------------------------------------


def _format_quantity(q) -> str:  # noqa: ANN001
    """Format a Quantity to a human-readable string."""
    parts = [str(q.value)]
    if hasattr(q, "unit") and q.unit is not None:
        parts.append(str(q.unit))
    return " ".join(parts)


def _format_measurement(m: Measurement) -> str:
    """Format a single Measurement as a bullet string."""
    parts = [f"kind={m.kind}"]
    val_str = str(m.value)
    if m.value_qualifier.name != "EXACT":
        val_str = str(m.value)
    parts.append(f"value={val_str}")
    parts.append(f"unit={m.unit}")
    if m.uncertainty is not None:
        parts.append(f"uncertainty={m.uncertainty}")
    if m.temperature is not None:
        parts.append(f"temperature={_format_quantity(m.temperature)}")
    if m.pressure is not None:
        parts.append(f"pressure={_format_quantity(m.pressure)}")
    if m.measurement_method is not None:
        parts.append(f"method={m.measurement_method}")
    if m.measurement_statistic is not None:
        parts.append(f"statistic={m.measurement_statistic.value}")
    if m.group_name is not None:
        parts.append(f"group_name={m.group_name}")
    return ", ".join(parts)


def _format_comp_measurement(cm: CompMeasurement) -> str:
    """Format a CompMeasurement as a bullet string."""
    return f"composition={cm.composition.formula}, method={cm.method.name}"


def _format_lattice_measurement(lm: LatticeMeasurement) -> str:
    """Format a LatticeMeasurement as a bullet string."""
    lattice = lm.lattice
    return f"a={lattice.a:.4f}, b={lattice.b:.4f}, c={lattice.c:.4f}, alpha={lattice.alpha}, beta={lattice.beta}, gamma={lattice.gamma}"


def _format_global_lattice_param(glp: GlobalLatticeParam) -> str:
    """Format a GlobalLatticeParam as a bullet string."""
    parts: list[str] = []
    if glp.struct is not None:
        parts.append(f"struct={glp.struct.name}")
    if glp.name is not None:
        parts.append(f"name={glp.name}")
    if glp.lattice is not None:
        parts.append(f"lattice=({_format_lattice_measurement(glp.lattice)})")
    if glp.phase_fraction is not None:
        parts.append(f"phase_fraction={_format_quantity(glp.phase_fraction)}")
    return ", ".join(parts)


def _format_process_event(pe: ProcessEvent) -> str:
    """Format a ProcessEvent as a bullet string."""
    parts = [f"kind={pe.kind.name}"]
    if pe.temperature is not None:
        parts.append(f"temperature={_format_quantity(pe.temperature)}")
    if pe.duration is not None:
        parts.append(f"duration={_format_quantity(pe.duration)}")
    if pe.description is not None:
        parts.append(f"description={pe.description}")
    if pe.equipment is not None:
        parts.append(f"equipment={pe.equipment}")
    return ", ".join(parts)


def _format_raw_material(name: str, rm: RawMaterial) -> str:
    """Format a RawMaterial as a bullet string."""
    parts = [f"name={name}", f"kind={rm.kind.name}"]
    if rm.description is not None:
        parts.append(f"description={rm.description}")
    return ", ".join(parts)


def _format_configuration_header(cfg: Configuration) -> str:
    """Format a Configuration's metadata (without its nested measurements)."""
    parts: list[str] = []
    if cfg.name is not None:
        parts.append(f"name={cfg.name}")
    if cfg.struct is not None:
        parts.append(f"struct={cfg.struct.name}")
    if cfg.tags:
        tag_names = ", ".join(sorted(t.name for t in cfg.tags))
        parts.append(f"tags={{{tag_names}}}")
    return ", ".join(parts)


def format_mixed_ground_truth(experiments: list[Experiment], doi: str) -> str:
    """Present all ground truth values grouped by type, disconnected from structure.

    Items within each group are shuffled using a deterministic seed derived
    from the DOI so that results are reproducible within a single run but do
    not leak positional information about the original ordering.
    """
    compositions: list[str] = []
    measurements_by_kind: dict[str, list[str]] = {}
    global_lattice_params: list[str] = []
    lattice_measurements: list[str] = []
    configurations: list[str] = []
    process_events: list[str] = []
    raw_materials: list[str] = []

    def _collect_measurements(meas_list) -> None:  # noqa: ANN001
        """Walk a measurement list and collect into buckets."""
        for m in meas_list:
            if isinstance(m, CompMeasurement):
                compositions.append(_format_comp_measurement(m))
            elif isinstance(m, Measurement):
                kind_str = str(m.kind)
                measurements_by_kind.setdefault(kind_str, []).append(_format_measurement(m))
            elif isinstance(m, GlobalLatticeParam):
                global_lattice_params.append(_format_global_lattice_param(m))
                if m.lattice is not None:
                    lattice_measurements.append(_format_lattice_measurement(m.lattice))
            elif isinstance(m, LatticeMeasurement):
                lattice_measurements.append(_format_lattice_measurement(m))
            elif isinstance(m, Configuration):
                configurations.append(_format_configuration_header(m))
                # Flatten nested measurements into the same top-level pools
                _collect_measurements(m.measurements)

    for exp in experiments:
        # Raw materials
        for name, rm in exp.raw_materials.items():
            raw_materials.append(_format_raw_material(name, rm))

        # Process events — flatten all synthesis groups into one list
        for sg in exp.synthesis_group_map.values():
            for pe in sg.process_events:
                process_events.append(_format_process_event(pe))

        # Material measurements
        for material in exp.output_materials:
            _collect_measurements(material.measurements)

    # Deterministic shuffle per DOI
    seed = int(hashlib.sha256(doi.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    rng.shuffle(compositions)
    for kind_list in measurements_by_kind.values():
        rng.shuffle(kind_list)
    rng.shuffle(global_lattice_params)
    rng.shuffle(lattice_measurements)
    rng.shuffle(configurations)
    rng.shuffle(process_events)
    rng.shuffle(raw_materials)

    # Assemble output
    sections: list[str] = []

    if compositions:
        lines = ["## Compositions"] + [f"- {c}" for c in compositions]
        sections.append("\n".join(lines))

    if measurements_by_kind:
        lines = ["## Numeric Measurements"]
        for kind in sorted(measurements_by_kind):
            lines.append(f"\n### {kind}")
            for item in measurements_by_kind[kind]:
                lines.append(f"- {item}")
        sections.append("\n".join(lines))

    if global_lattice_params:
        lines = ["## Crystal Structures / Phases"] + [f"- {g}" for g in global_lattice_params]
        sections.append("\n".join(lines))

    if lattice_measurements:
        lines = ["## Lattice Measurements"] + [f"- {lm}" for lm in lattice_measurements]
        sections.append("\n".join(lines))

    if configurations:
        lines = ["## Microstructural Features"] + [f"- {c}" for c in configurations]
        sections.append("\n".join(lines))

    if process_events:
        lines = ["## Process Events"] + [f"- {pe}" for pe in process_events]
        sections.append("\n".join(lines))

    if raw_materials:
        lines = ["## Raw Materials"] + [f"- {rm}" for rm in raw_materials]
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Agent extraction
# ---------------------------------------------------------------------------


async def _extract_assemble_graph(
    doi: str, extraction_agent: Agent, config: ExperimentBenchmarkConfig, ground_truth: list[Experiment]
) -> ExtractionOutput:
    paper_text = load_transcribed_paper_text_only(doi)
    mixed_data = format_mixed_ground_truth(ground_truth, doi)
    pc = config.prompt_config

    task_description = (
        "You are given a scientific paper and a set of extracted data values from that paper. "
        "The values are correct but have been separated from their original structure — they are "
        "grouped by type (compositions, measurements, process events, etc.) rather than by material.\n\n"
        "Your task is to reconstruct the full experiment structure:\n"
        "- Figure out which measurements belong to which material\n"
        "- Determine which process events form which synthesis chain\n"
        "- Identify which microstructural features (Configurations) belong to which material, "
        "and which measurements are nested inside each Configuration\n"
        "- Reconstruct the raw materials, synthesis groups, and output materials\n\n"
        "Use the paper text to understand the relationships between the extracted values.\n\n"
        "Return a Python fenced code block (```python ... ```) containing a single expression "
        "that evaluates to a `list[Experiment]`."
    )

    sections = [
        task_description
        + "\n\n"
        + scope_rules()
        + "\n\n"
        + "# Extracted Data\n\n"
        + mixed_data
        + "\n\n"
        + "# Output Format\n\n"
        + "Use this exact shape:\n\n"
        + example_experiment_shape(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions
        )
        + "\n\n"
        + field_instructions(
            include_source=pc.include_source, include_descriptions=pc.include_descriptions_instructions
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
            extracted = execute_experiments_code(code, pc)
        except Exception as exc:
            raise RetryableError(
                f"The generated Python expression failed at runtime. Fix it and try again.\nExecution error:\n{exc}"
            ) from exc
        if not isinstance(extracted, list) or not all(isinstance(e, Experiment) for e in extracted):
            raise RetryableError(
                "Output must evaluate to a list[Experiment]. Every list item must be an Experiment object."
            )
        return extracted

    result = await run_extraction_loop(
        agent=extraction_agent,
        initial_prompt=prompt,
        process_response=process_response,
        extract_block=extract_python_code_block,
        retry_messages=PYTHON_RETRY_MESSAGES,
        max_retries=10,
        span_name="extract_assemble_graph",
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


async def _extract_worker(
    doi: str, config: ExperimentBenchmarkConfig, ground_truth_map: dict[str, list[Experiment]]
) -> tuple[str, ExtractionOutput]:
    extraction_agent = create_default_agent(config.model_name)
    start = time.monotonic()
    output = await _extract_assemble_graph(doi, extraction_agent, config, ground_truth_map[doi])
    finalize_output(output, config.model_name, start)
    return doi, output


async def extract_experiments_assemble_graph(
    config: ExperimentBenchmarkConfig,
    ground_truth_map: dict[str, list[Experiment]],
) -> dict[str, ExtractionOutput]:
    dois = config.dois if config.dois is not None else list(ground_truth_map.keys())
    return await run_parallel(dois, config.max_workers, _extract_worker, config, ground_truth_map)


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
        config=ExperimentBenchmarkConfig(name="assemble_graph"),
        output_subdir="assemble_graph",
        extract_fn=lambda cfg: extract_experiments_assemble_graph(cfg, papers),
    )
