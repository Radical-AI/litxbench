"""Shared helpers for paper-matching benchmarks.

Provides redaction functions (flat / graph), prompt building, response parsing,
and the orchestrator that runs the matching benchmark for a list of models.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
)
from litxbench.core.utils import load_transcribed_paper_text_only, resolve_path
from litxbench.litxalloy import papers
from scripts.paper.benchmarks.helpers.extraction_runner import (
    configure_logfire,
    create_default_agent,
    run_parallel,
)
from scripts.paper.benchmarks.helpers.pricing import compute_cost

# re-export for convenience
__all__ = [
    "MatchingOutput",
    "configure_logfire",
    "redact_experiments_flat",
    "redact_experiments_graph",
    "run_matching_benchmark",
]

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

Experiment = type(list(papers.values())[0][0])  # runtime Experiment type


@dataclass
class MatchingOutput:
    doi: str
    predicted_set: int | None  # 1-indexed, None if parse failed
    correct_set: int  # 1-indexed
    is_correct: bool
    prompt_text: str = ""
    raw_response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Measurement counting helpers (shared by flat and graph)
# ---------------------------------------------------------------------------


def _count_measurements(measurements: list) -> dict[str, int]:
    """Count measurements by type for a single material."""
    counts: dict[str, int] = {
        "composition": 0,
        "property": 0,
        "configuration": 0,
        "nested": 0,
        "lattice": 0,
        "global_lattice": 0,
    }
    for m in measurements:
        if isinstance(m, CompMeasurement):
            counts["composition"] += 1
        elif isinstance(m, Configuration):
            counts["configuration"] += 1
            counts["nested"] += len(m.measurements)
        elif isinstance(m, LatticeMeasurement):
            counts["lattice"] += 1
        elif isinstance(m, GlobalLatticeParam):
            counts["global_lattice"] += 1
        elif isinstance(m, Measurement):
            counts["property"] += 1
    return counts


def _format_measurement_counts(counts: dict[str, int]) -> str:
    parts = [
        f"{counts['composition']} composition",
        f"{counts['property']} property measurements",
        f"{counts['configuration']} configuration ({counts['nested']} nested measurements)"
        if counts["configuration"]
        else "0 configuration",
        f"{counts['lattice']} lattice",
        f"{counts['global_lattice']} global lattice",
    ]
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Synthesis-event counting helpers
# ---------------------------------------------------------------------------


def _count_own_synthesis_events(material, exp) -> int:
    """Count synthesis events from this material's own process steps."""
    if not material.process_steps:
        return 0
    total = 0
    for step in material.process_steps:
        sg = exp.synthesis_group_map.get(step.base_name)
        if sg:
            total += len(sg.process_events)
    return total


# ---------------------------------------------------------------------------
# Raw-material collection (shared by flat and graph)
# ---------------------------------------------------------------------------


def _collect_material_raw_materials(
    material,
    exp,
    raw_mat_ids: dict[str, str],
    parent_raw_mats: list[str] | None = None,
) -> list[str]:
    """Collect all anonymized raw material IDs consumed by a material's synthesis.

    Checks both process-step inputs and synthesis-group event inputs,
    and inherits from parent materials.
    """
    seen: set[str] = set()
    result: list[str] = []

    # Inherit from parent
    if parent_raw_mats:
        for rm in parent_raw_mats:
            if rm not in seen:
                seen.add(rm)
                result.append(rm)

    if not material.process_steps:
        return result

    for step in material.process_steps:
        # Direct process-step inputs that are raw materials
        for inp in step.inputs:
            if inp in raw_mat_ids and raw_mat_ids[inp] not in seen:
                seen.add(raw_mat_ids[inp])
                result.append(raw_mat_ids[inp])

        # Synthesis-group event inputs that are raw materials
        sg = exp.synthesis_group_map.get(step.base_name)
        if sg:
            for event in sg.process_events:
                for inp in event.inputs:
                    if inp in raw_mat_ids and raw_mat_ids[inp] not in seen:
                        seen.add(raw_mat_ids[inp])
                        result.append(raw_mat_ids[inp])

    return result


# ---------------------------------------------------------------------------
# Flat redaction
# ---------------------------------------------------------------------------


def redact_experiments_flat(experiments: list) -> str:
    """Produce a count-only summary (no names, values, kinds, or topology)."""
    lines: list[str] = []
    for exp_idx, exp in enumerate(experiments, 1):
        # Anonymize raw materials
        raw_mat_ids: dict[str, str] = {}
        for r_idx, name in enumerate(sorted(exp.raw_materials.keys()), 1):
            raw_mat_ids[name] = f"raw_material_{r_idx}"

        # Track accumulated synthesis events and raw materials for named materials
        material_accumulated: dict[str, int] = {}
        material_raw_mats: dict[str, list[str]] = {}

        lines.append(f"Experiment {exp_idx}:")
        lines.append(f"  Raw materials: {', '.join(raw_mat_ids.values())}")
        lines.append(f"  Output materials: {len(exp.output_materials)}")
        for s_idx, material in enumerate(exp.output_materials, 1):
            own_events = _count_own_synthesis_events(material, exp)

            # Accumulate from input materials
            accumulated = own_events
            parent_raw_mats: list[str] | None = None
            if material.process_steps and material.process_steps[0].inputs:
                for inp in material.process_steps[0].inputs:
                    if inp in material_accumulated:
                        accumulated += material_accumulated[inp]
                        if inp in material_raw_mats:
                            parent_raw_mats = material_raw_mats[inp]

            # Collect all raw materials (direct + synthesis group events + inherited)
            root_raw_mats = _collect_material_raw_materials(material, exp, raw_mat_ids, parent_raw_mats)

            if material.name:
                material_accumulated[material.name] = accumulated
                material_raw_mats[material.name] = root_raw_mats

            raw_mats_str = ", ".join(root_raw_mats) if root_raw_mats else "raw_material_1"
            counts = _count_measurements(list(material.measurements))
            lines.append(f"  {raw_mats_str} -> ({accumulated} synthesis steps) -> material_{s_idx}:")
            lines.append(f"    {_format_measurement_counts(counts)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graph redaction
# ---------------------------------------------------------------------------


def _build_process_chain(
    material,
    material_ids: dict[str, str],
    own_steps: int,
    material_own_steps: dict[str, int],
    material_parent: dict[str, str | None],
    chain_raw_mats: list[str],
    material_label: str,
) -> str:
    """Build a process chain showing full path from raw materials to output material."""
    if not material.process_steps:
        return ""

    # Find immediate parent material name (raw name, not anonymized)
    parent_name = None
    for step in material.process_steps:
        for inp in step.inputs:
            if inp in material_ids:
                parent_name = inp
                break

    # Build chain segments by walking back through parents
    # Each segment is (anonymized_label, own_steps_count)
    segments: list[tuple[str, int]] = []

    # Add current material (use the caller-provided label so unnamed materials are consistent)
    segments.append((material_label, own_steps))

    # Walk back through ancestors
    current = parent_name
    while current is not None:
        segments.append((material_ids[current], material_own_steps.get(current, 0)))
        current = material_parent.get(current)

    # Reverse to get raw_materials -> ... -> output order
    segments.reverse()

    raw_mats_str = ", ".join(chain_raw_mats) if chain_raw_mats else "raw_material_1"

    # Build the chain string
    parts: list[str] = [raw_mats_str]
    total_steps = 0
    for label, steps in segments:
        total_steps += steps
        parts.append(f"({steps} synthesis steps)")
        if label:
            parts.append(label)

    chain = " -> ".join(parts)

    # Add total if there are intermediate materials
    if parent_name is not None:
        chain += f" ({total_steps} total synthesis steps)"

    return chain


def redact_experiments_graph(experiments: list) -> str:
    """Produce anonymized structural summary preserving topology."""
    lines: list[str] = []
    for exp_idx, exp in enumerate(experiments, 1):
        # Anonymize raw materials
        raw_mat_ids: dict[str, str] = {}
        for r_idx, name in enumerate(sorted(exp.raw_materials.keys()), 1):
            raw_mat_ids[name] = f"raw_material_{r_idx}"

        material_ids: dict[str, str] = {}
        named_idx = 1
        for m in exp.output_materials:
            if m.name:
                material_ids[m.name] = f"material_{named_idx}"
                named_idx += 1

        # Track per-material info for full chain building
        material_own_steps: dict[str, int] = {}
        material_parent: dict[str, str | None] = {}
        material_raw_mats: dict[str, list[str]] = {}

        lines.append(f"Experiment {exp_idx}:")
        lines.append(f"  Raw materials: {', '.join(raw_mat_ids.values())}")
        lines.append(f"  Output materials: {len(exp.output_materials)}")
        for s_idx, material in enumerate(exp.output_materials, 1):
            # Count only this material's own synthesis events (between input and now)
            own_events = _count_own_synthesis_events(material, exp)

            # Find parent material name for ancestry tracking
            parent_name = None
            if material.process_steps:
                for step in material.process_steps:
                    for inp in step.inputs:
                        if inp in material_ids:
                            parent_name = inp
                            break

            # Collect all raw materials (direct + synthesis events + inherited from parent)
            parent_rm = material_raw_mats.get(parent_name) if parent_name else None
            chain_raw_mats = _collect_material_raw_materials(material, exp, raw_mat_ids, parent_rm)

            # Track for downstream chain building
            if material.name:
                material_own_steps[material.name] = own_events
                material_parent[material.name] = parent_name
                material_raw_mats[material.name] = chain_raw_mats

            material_label = (
                material_ids.get(material.name, f"material_{s_idx}") if material.name else f"material_{s_idx}"
            )
            chain = _build_process_chain(
                material, material_ids, own_events, material_own_steps, material_parent, chain_raw_mats, material_label
            )
            lines.append(f"  {chain}:")

            counts = _count_measurements(list(material.measurements))
            lines.append(f"    {_format_measurement_counts(counts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Shuffling / labeling
# ---------------------------------------------------------------------------


def prepare_shuffled_sets(
    papers_dict: dict[str, list],
    redact_fn: Callable[[list], str],
    seed: int = 42,
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Redact each paper's experiments, shuffle, and assign 1-indexed labels.

    Returns:
        (labeled_summaries, ground_truth_map)
        labeled_summaries: list of (label, redacted_text) in shuffled order
        ground_truth_map: doi -> 1-indexed set number
    """
    dois = sorted(papers_dict.keys())
    redacted = [(doi, redact_fn(papers_dict[doi])) for doi in dois]

    rng = random.Random(seed)
    rng.shuffle(redacted)

    labeled: list[tuple[str, str]] = []
    ground_truth: dict[str, int] = {}
    for idx, (doi, text) in enumerate(redacted, 1):
        labeled.append((f"Set {idx}", text))
        ground_truth[doi] = idx

    return labeled, ground_truth


# ---------------------------------------------------------------------------
# Prompt building / response parsing
# ---------------------------------------------------------------------------


def build_matching_prompt(paper_text: str, labeled_summaries: list[tuple[str, str]]) -> str:
    """Assemble the full matching prompt."""
    parts: list[str] = []
    parts.append(
        "You are given a scientific paper and 19 redacted experiment summaries (labeled Set 1 through Set 19). "
        "Each summary describes the structural fingerprint of the experiments extracted from one of 19 papers. "
        "Exactly one summary corresponds to this paper.\n\n"
        "Your task: determine which set matches this paper based on structural clues only "
        "(counts of raw materials, output materials, measurements, process steps, and their relationships).\n\n"
        'Respond with a JSON object: {"reason": "<brief explanation of why you chose this set>", "match": N} where N is the set number (1-19).'
    )

    parts.append("\n\n--- REDACTED EXPERIMENT SUMMARIES ---\n")
    for label, text in labeled_summaries:
        parts.append(f"### {label}\n{text}\n")

    parts.append("\n--- PAPER TEXT ---\n")
    parts.append(paper_text)

    return "\n".join(parts)


def parse_matching_response(response: str, *, max_val: int = 19) -> int | None:
    """Extract the predicted set/paper number from an LLM response.

    Returns an int in [1, max_val] or None if parsing fails.
    """
    # Try JSON parsing first
    try:
        data = json.loads(response.strip())
        if isinstance(data, dict) and "match" in data:
            val = int(data["match"])
            if 1 <= val <= max_val:
                return val
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Try to find JSON object in the response
    json_match = re.search(r'\{[^}]*"match"\s*:\s*(\d+)[^}]*\}', response)
    if json_match:
        val = int(json_match.group(1))
        if 1 <= val <= max_val:
            return val

    # Fallback: look for a bare number after "match"
    bare_match = re.search(r'match["\s:]*(\d+)', response, re.IGNORECASE)
    if bare_match:
        val = int(bare_match.group(1))
        if 1 <= val <= max_val:
            return val

    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


async def _matching_worker(
    doi: str,
    model_name: str,
    labeled_summaries: list[tuple[str, str]],
    ground_truth: dict[str, int],
) -> tuple[str, MatchingOutput]:
    """Worker function for a single DOI: load paper, build prompt, query LLM, parse."""
    agent = create_default_agent(model_name)
    paper_text = load_transcribed_paper_text_only(doi)
    prompt = build_matching_prompt(paper_text, labeled_summaries)

    start = time.monotonic()
    async with agent.run_stream(prompt) as result:
        raw_response = await result.get_output()
    elapsed = time.monotonic() - start

    usage = result.usage()
    predicted = parse_matching_response(raw_response)
    correct_set = ground_truth[doi]

    output = MatchingOutput(
        doi=doi,
        predicted_set=predicted,
        correct_set=correct_set,
        is_correct=(predicted == correct_set),
        prompt_text=prompt,
        raw_response=raw_response,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=compute_cost(model_name, usage.input_tokens, usage.output_tokens),
        elapsed_seconds=elapsed,
    )
    return doi, output


async def _run_single_model(
    model_name: str,
    dois: list[str],
    labeled_summaries: list[tuple[str, str]],
    ground_truth: dict[str, int],
    output_dir: Path,
) -> tuple[dict[str, MatchingOutput], dict[str, str | int | float]]:
    """Run matching benchmark for a single model."""
    max_workers = 5 if model_name.startswith("gemini-3.1-pro") else 25

    results: dict[str, MatchingOutput] = await run_parallel(
        dois,
        max_workers,
        _matching_worker,
        model_name,
        labeled_summaries,
        ground_truth,
    )

    # Write per-DOI artifacts
    model_dir = output_dir / model_name
    model_dir.mkdir(parents=True, exist_ok=True)

    for doi, output in results.items():
        (model_dir / f"{doi}.prompt.txt").write_text(output.prompt_text)
        (model_dir / f"{doi}.response.txt").write_text(output.raw_response)

    # Evaluate and write results
    correct = sum(1 for o in results.values() if o.is_correct)
    total = len(results)
    accuracy = correct / total if total else 0.0

    print(f"\n  [{model_name}] Accuracy: {correct}/{total} ({accuracy:.1%})")
    for doi in sorted(results):
        o = results[doi]
        status = "CORRECT" if o.is_correct else "WRONG"
        print(f"    {doi}: predicted Set {o.predicted_set}, correct Set {o.correct_set} [{status}]")

    total_cost = sum(o.cost_usd for o in results.values())
    total_input = sum(o.input_tokens for o in results.values())
    total_output = sum(o.output_tokens for o in results.values())
    total_elapsed = sum(o.elapsed_seconds for o in results.values())
    print(f"    Cost: ${total_cost:.4f}  Tokens: {total_input} in / {total_output} out  Time: {total_elapsed:.1f}s")

    results_data = {
        "model": model_name,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "total_cost_usd": total_cost,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "per_doi": {
            doi: {
                "predicted_set": o.predicted_set,
                "correct_set": o.correct_set,
                "is_correct": o.is_correct,
                "input_tokens": o.input_tokens,
                "output_tokens": o.output_tokens,
                "cost_usd": o.cost_usd,
                "elapsed_seconds": o.elapsed_seconds,
            }
            for doi, o in sorted(results.items())
        },
    }
    (model_dir / "results.json").write_text(json.dumps(results_data, indent=2))

    summary_row = {
        "model_name": model_name,
        "accuracy": f"{accuracy:.4f}",
        "correct": correct,
        "total": total,
        "input_tokens": total_input,
        "output_tokens": total_output,
        "cost_usd": f"{total_cost:.4f}",
        "elapsed_seconds": f"{total_elapsed:.1f}",
    }
    return results, summary_row


MATCHING_CSV_KEYS = [
    "model_name",
    "accuracy",
    "correct",
    "total",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "elapsed_seconds",
]


def _print_matching_csv(rows: list[dict[str, str | int | float]], output_dir: Path | None = None) -> None:
    """Print comma-separated summary rows for spreadsheet pasting and optionally save to file."""
    from scripts.paper.benchmarks.helpers.reporting import (
        _print_summary_csv,
        save_summary_csv,
    )

    _print_summary_csv(rows, keys=MATCHING_CSV_KEYS)
    if output_dir is not None:
        csv_path = output_dir / "summary.csv"
        save_summary_csv(rows, csv_path, keys=MATCHING_CSV_KEYS)
        print(f"CSV saved to {csv_path}")


def run_matching_benchmark(
    *,
    model_names: list[str],
    redact_fn: Callable[[list], str],
    output_subdir: str,
    benchmark_name: str,
    seed: int = 42,
) -> Path:
    """Main entry point: prepare sets, run all models, write results."""
    labeled_summaries, ground_truth = prepare_shuffled_sets(papers, redact_fn, seed)

    date_epoch = datetime.now().strftime("%Y%m%d_%s")
    output_dir = Path(resolve_path("outputs")) / output_subdir / f"{benchmark_name}_{date_epoch}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write the redacted summaries for inspection
    summary_path = output_dir / "redacted_summaries.txt"
    with summary_path.open("w") as f:
        for label, text in labeled_summaries:
            f.write(f"### {label}\n{text}\n\n")

    # Write ground truth mapping
    gt_path = output_dir / "ground_truth.json"
    gt_path.write_text(json.dumps(ground_truth, indent=2))

    dois = sorted(papers.keys())
    csv_rows: list[dict[str, str | int | float]] = []

    async def _run_all() -> None:
        for model_name in model_names:
            print(f"\nRunning {benchmark_name} for {model_name}...")
            _results, summary_row = await _run_single_model(
                model_name, dois, labeled_summaries, ground_truth, output_dir
            )
            csv_rows.append(summary_row)

    asyncio.run(_run_all())
    _print_matching_csv(csv_rows, output_dir)
    print(f"\nOutputs written to {output_dir}")
    return output_dir


# ---------------------------------------------------------------------------
# Inverse matching: 19 papers + 1 redacted experiment → pick the paper
# ---------------------------------------------------------------------------
