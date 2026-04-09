"""Property extraction benchmark (zero-shot).

Tests how well LLMs can extract individual mechanical property values
(one LLM call per property per paper) from papers.  The LLM must return
numeric values inside a fenced code block.
"""

import asyncio
import csv
import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from pint import Unit
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from scipy.optimize import linear_sum_assignment

from litxbench.core.units import HV, MegaPascal, percent, ureg
from litxbench.core.utils import dict_to_csv_string, load_transcribed_paper_text_only, resolve_path
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    Configuration,
    Experiment,
    Measurement,
)
from scripts.paper.benchmarks.helpers.comparison import ComparisonResult
from scripts.paper.benchmarks.helpers.extraction_runner import run_models_parallel
from scripts.paper.benchmarks.helpers.model_provider import (
    ModelProvider,
    get_model_from_name,
)
from scripts.paper.benchmarks.helpers.pricing import compute_cost
from scripts.paper.benchmarks.helpers.reporting import (
    write_extraction_artifacts,
)

# ---------------------------------------------------------------------------
# Property definitions
# ---------------------------------------------------------------------------


@dataclass
class PropertyDef:
    """Metadata for a single extractable property."""

    kind: AlloyMeasurementKind
    unit: str
    pint_unit: Unit
    prompt_description: str


PROPERTY_DEFS: dict[str, PropertyDef] = {
    "ultimate_tensile_strength": PropertyDef(
        kind=AlloyMeasurementKind.ultimate_tensile_strength,
        unit="MPa",
        pint_unit=MegaPascal,
        prompt_description="Ultimate tensile strength (UTS)",
    ),
    "ultimate_compressive_strength": PropertyDef(
        kind=AlloyMeasurementKind.ultimate_compressive_strength,
        unit="MPa",
        pint_unit=MegaPascal,
        prompt_description="Ultimate compressive strength (UCS)",
    ),
    "fracture_strain_tension": PropertyDef(
        kind=AlloyMeasurementKind.fracture_strain_tension,
        unit="%",
        pint_unit=percent,
        prompt_description="Fracture strain in tension (elongation at fracture)",
    ),
    "fracture_strain_compression": PropertyDef(
        kind=AlloyMeasurementKind.fracture_strain_compression,
        unit="%",
        pint_unit=percent,
        prompt_description="Fracture strain in compression",
    ),
    "vickers_hardness": PropertyDef(
        kind=AlloyMeasurementKind.vickers_hardness,
        unit="HV",
        pint_unit=HV,
        prompt_description="Vickers hardness",
    ),
}


# ---------------------------------------------------------------------------
# Config & output types
# ---------------------------------------------------------------------------


@dataclass
class PropertyBenchmarkConfig:
    """Configuration for the property extraction benchmark."""

    dois: list[str] | None = None
    model_name: str = ""
    max_workers: int = 25
    properties: list[str] = field(default_factory=lambda: list(PROPERTY_DEFS.keys()))


@dataclass
class PropertyExtractionOutput:
    """Result of a single property extraction for one paper."""

    values: list[float]
    prompt_text: str
    raw_response: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Ground truth extraction
# ---------------------------------------------------------------------------


def extract_target_values(
    experiments: list[Experiment],
    target_kind: AlloyMeasurementKind,
    target_unit: Unit,
) -> list[float]:
    """Extract material-level numeric values for a given measurement kind.

    Walks all output_materials, collects Measurement objects whose kind matches
    target_kind, converts to target_unit, extracts numeric_value. Skips
    measurements nested inside Configuration objects (only material-level
    measurements). Deduplicates values.
    """
    values: list[float] = []
    for exp in experiments:
        for material in exp.output_materials:
            for m in material.measurements:
                if isinstance(m, Configuration):
                    continue
                if isinstance(m, Measurement) and m.kind == target_kind.value:
                    if m.numeric_value is not None:
                        quantity = ureg.Quantity(m.numeric_value, m.unit)
                        converted = quantity.to(target_unit).magnitude
                        values.append(float(converted))
    # Deduplicate while preserving order
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------------------
# Value comparison (Hungarian matching, exact)
# ---------------------------------------------------------------------------


PropertyComparisonResult = ComparisonResult[float, float]


def compare_values(
    target: list[float],
    extracted: list[float],
) -> PropertyComparisonResult:
    """Compare two lists of numeric values using exact matching.

    Uses Hungarian matching to find the optimal assignment, then only
    accepts pairs that are exactly equal.
    """
    n_target = len(target)
    n_extracted = len(extracted)

    if n_target == 0 or n_extracted == 0:
        return PropertyComparisonResult(
            matched_pairs=[],
            unmatched_target=list(target),
            unmatched_extracted=list(extracted),
        )

    UNMATCHED_PENALTY = 1e6
    size = max(n_target, n_extracted)
    cost_matrix = [[UNMATCHED_PENALTY] * size for _ in range(size)]

    for i in range(n_target):
        for j in range(n_extracted):
            cost_matrix[i][j] = abs(extracted[j] - target[i])

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matched_pairs: list[tuple[float, float]] = []
    matched_target_indices: set[int] = set()
    matched_extracted_indices: set[int] = set()

    for r, c in zip(row_ind, col_ind):
        if r < n_target and c < n_extracted:
            if extracted[c] == target[r]:
                matched_pairs.append((target[r], extracted[c]))
                matched_target_indices.add(r)
                matched_extracted_indices.add(c)

    unmatched_target = [target[i] for i in range(n_target) if i not in matched_target_indices]
    unmatched_extracted = [extracted[j] for j in range(n_extracted) if j not in matched_extracted_indices]

    return PropertyComparisonResult(
        matched_pairs=matched_pairs,
        unmatched_target=unmatched_target,
        unmatched_extracted=unmatched_extracted,
    )


# ---------------------------------------------------------------------------
# LLM prompt & parsing
# ---------------------------------------------------------------------------


def _build_property_prompt(prop_def: PropertyDef) -> str:
    return (
        f"Extract all {prop_def.prompt_description} values of alloys/materials that the "
        f"authors physically synthesized in this paper. Return values in {prop_def.unit}.\n\n"
        "We are only interested in measurements of alloys/materials that the authors physically "
        "made (synthesized) in their lab.\n"
        "Do NOT include:\n"
        "- Values mentioned in passing from other studies or references\n"
        "- Values from computational/theoretical predictions\n"
        "- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)\n"
        "Only include the overall material-level values.\n\n"
        "Note: You only have access to the text of the paper. Images, figures, and tables "
        "rendered as images are not available, so rely solely on the textual content.\n\n"
        "Return a JSON array of numeric values. Only include the numeric values, no units or labels.\n"
        "If there are no values for this property, return an empty array.\n"
        "If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0."
    )


def _extract_values_from_response(response_text: str) -> list[float]:
    """Parse numeric values from a JSON array in the response."""
    text = response_text.strip()
    # Extract JSON array from fenced code block if present
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            block = parts[1]
            # Remove optional language tag on first line
            if "\n" in block:
                first_line, rest = block.split("\n", 1)
                if first_line.strip() in ("", "json", "python", "text", "plaintext"):
                    block = rest
            text = block.strip()

    # Find the JSON array in the text
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, list):
                return [float(v) for v in parsed if isinstance(v, (int, float))]
        except (json.JSONDecodeError, ValueError):
            pass
    return []


def _validate_property_output(response_text: str) -> list[float]:
    """Parse and validate property values from LLM response."""
    values = _extract_values_from_response(response_text)
    if not values and "[]" in response_text:
        # Empty array is valid (no values for this property)
        return []
    if not values:
        raise ModelRetry(
            "No numeric values found. Return a JSON array of numeric values. "
            "If there are no values, return an empty array: []"
        )
    # Deduplicate while preserving order
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------------------
# Agent extraction
# ---------------------------------------------------------------------------


async def _extract_property_zero_shot(
    doi: str,
    prop_name: str,
    prop_def: PropertyDef,
    extraction_agent: Agent,
) -> PropertyExtractionOutput:
    paper_text = load_transcribed_paper_text_only(doi)
    raw_response: str = ""
    extracted_values: list[float] = []

    def validate_output(response_text: str) -> str:
        nonlocal raw_response, extracted_values
        raw_response = response_text
        extracted_values = _validate_property_output(response_text)
        return response_text

    _ = extraction_agent.output_validator(validate_output)
    prompt = [_build_property_prompt(prop_def), paper_text]
    result = await extraction_agent.run(prompt)
    usage = result.usage()
    return PropertyExtractionOutput(
        values=extracted_values,
        prompt_text="\n".join(prompt),
        raw_response=raw_response,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


async def extract_properties_zero_shot(
    config: PropertyBenchmarkConfig,
) -> dict[str, dict[str, PropertyExtractionOutput]]:
    """Run property extraction for all DOIs and properties.

    Returns nested dict: {prop_name: {doi: PropertyExtractionOutput}}.
    """
    dois = config.dois if config.dois is not None else list(papers.keys())
    prop_defs = {k: PROPERTY_DEFS[k] for k in config.properties}

    model_provider = ModelProvider()
    model = get_model_from_name(model_provider, config.model_name)

    # Limit concurrency to max_workers (like ThreadPoolExecutor but without
    # separate event loops that cause "Event loop is closed" errors).
    semaphore = asyncio.Semaphore(config.max_workers)

    async def _run_one(doi: str, prop_name: str, prop_def: PropertyDef) -> tuple[str, str, PropertyExtractionOutput]:
        async with semaphore:
            extraction_agent = Agent(model=model, retries=3, model_settings={"timeout": 120})
            output = await _extract_property_zero_shot(doi, prop_name, prop_def, extraction_agent)
            output.cost_usd = compute_cost(config.model_name, output.input_tokens, output.output_tokens)
            return doi, prop_name, output

    tasks = [_run_one(doi, pn, pd) for pn, pd in prop_defs.items() for doi in dois]
    completed = await asyncio.gather(*tasks)

    results: dict[str, dict[str, PropertyExtractionOutput]] = {pn: {} for pn in prop_defs}
    for doi, prop_name, output in completed:
        results[prop_name][doi] = output

    return results


# ---------------------------------------------------------------------------
# Display & CSV output
# ---------------------------------------------------------------------------


def print_property_comparison(
    doi: str,
    prop_name: str,
    result: PropertyComparisonResult,
    extraction_output: PropertyExtractionOutput | None = None,
) -> None:
    matched = len(result.matched_pairs)
    missed = result.unmatched_target
    extra = result.unmatched_extracted
    detail = ""
    if missed:
        detail += f"  missed={missed}"
    if extra:
        detail += f"  extra={extra}"
    cost_str = ""
    if extraction_output is not None:
        cost_str = (
            f"  tokens={extraction_output.input_tokens}+{extraction_output.output_tokens}"
            f"  ${extraction_output.cost_usd:.4f}"
        )
    print(
        f"    {doi:<40s}  "
        f"P={result.precision:.0%}  R={result.recall:.0%}  F1={result.f1:.0%}  "
        f"({matched}/{result.num_target} matched, {result.num_extracted} extracted)"
        f"{cost_str}{detail}"
    )


# ---------------------------------------------------------------------------
# Summary diff
# ---------------------------------------------------------------------------


def write_property_diff_summary(
    output_path: Path,
    dois: list[str],
    prop_names: list[str],
    target_values: dict[str, dict[str, list[float]]],
    all_comparison_results: dict[str, dict[str, PropertyComparisonResult]],
    all_extraction_outputs: dict[str, dict[str, PropertyExtractionOutput]],
) -> None:
    """Write a human-readable diff of expected vs extracted values."""
    lines: list[str] = []

    for prop_name in prop_names:
        prop_def = PROPERTY_DEFS[prop_name]
        lines.append(f"{'=' * 70}")
        lines.append(f"{prop_def.prompt_description} ({prop_def.unit})")
        lines.append(f"{'=' * 70}")

        comparison_results = all_comparison_results.get(prop_name, {})
        extraction_outputs = all_extraction_outputs.get(prop_name, {})

        for doi in dois:
            target = target_values[prop_name][doi]
            r = comparison_results.get(doi)
            eo = extraction_outputs.get(doi)
            extracted = eo.values if eo else []

            if not target and not extracted:
                continue

            lines.append(f"\n  {doi}")
            lines.append(f"    expected:  {target}")
            lines.append(f"    actual:    {extracted}")

            if r is not None:
                if r.matched_pairs:
                    pairs_str = ", ".join(f"{t}->{e}" if t != e else str(t) for t, e in r.matched_pairs)
                    lines.append(f"    matched:   [{pairs_str}]")
                if r.unmatched_target:
                    lines.append(f"    missed:    {r.unmatched_target}")
                if r.unmatched_extracted:
                    lines.append(f"    extra:     {r.unmatched_extracted}")
                lines.append(f"    P={r.precision:.0%}  R={r.recall:.0%}  F1={r.f1:.0%}")

        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Benchmark runner
# ---------------------------------------------------------------------------

PROPERTY_CSV_KEYS = [
    "model_name",
    "property",
    "num_target",
    "num_extracted",
    "num_matched",
    "precision",
    "recall",
    "f1",
    "input_tokens",
    "output_tokens",
    "cost_usd",
]


def run_property_benchmark(
    model_names: list[str],
    config: PropertyBenchmarkConfig | None = None,
    outputs_root: Path | None = None,
) -> Path:
    from datetime import datetime

    if config is None:
        config = PropertyBenchmarkConfig()

    dois = config.dois or list(papers.keys())
    properties_to_test = config.properties

    if outputs_root is None:
        date_epoch = datetime.now().strftime("%Y%m%d_%s")
        outputs_root = Path(resolve_path("outputs")) / "properties" / f"property_zero_shot_{date_epoch}"
    print(f"Saving results to: {outputs_root}")

    # Extract ground truth for all properties
    target_values: dict[str, dict[str, list[float]]] = {}
    for prop_name in properties_to_test:
        prop_def = PROPERTY_DEFS[prop_name]
        target_values[prop_name] = {
            doi: extract_target_values(papers[doi], prop_def.kind, prop_def.pint_unit) for doi in dois
        }

    # Run extraction for all models in parallel
    total_max_workers = 25
    per_model_workers = max(1, total_max_workers // len(model_names))
    configs = {mn: replace(config, model_name=mn, dois=dois, max_workers=per_model_workers) for mn in model_names}

    all_model_extraction_outputs, model_elapsed = asyncio.run(
        run_models_parallel(configs, extract_properties_zero_shot)
    )

    # Report results for each model (sequentially for clean output)
    for model_name in model_names:
        elapsed = model_elapsed[model_name]
        extraction_outputs = all_model_extraction_outputs[model_name]

        print(f"\n{'=' * 70}")
        print(f"Model: {model_name}")
        print(f"{'=' * 70}")

        all_comparison_results: dict[str, dict[str, PropertyComparisonResult]] = {}
        csv_rows: list[dict[str, str | int | float]] = []

        grand_matched = 0
        grand_target = 0
        grand_extracted = 0
        grand_input_tokens = 0
        grand_output_tokens = 0
        grand_cost = 0.0

        for prop_name in properties_to_test:
            print(f"\n  [{prop_name}]")
            prop_outputs = extraction_outputs.get(prop_name, {})
            comparison_results: dict[str, PropertyComparisonResult] = {}

            prop_matched = 0
            prop_target = 0
            prop_extracted = 0
            prop_input_tokens = 0
            prop_output_tokens = 0
            prop_cost = 0.0

            for doi in dois:
                target = target_values[prop_name][doi]
                eo = prop_outputs.get(doi)
                extracted = eo.values if eo else []
                result = compare_values(target, extracted)
                comparison_results[doi] = result

                if target or extracted:
                    print_property_comparison(doi, prop_name, result, eo)

                in_tok = eo.input_tokens if eo else 0
                out_tok = eo.output_tokens if eo else 0
                cost = eo.cost_usd if eo else 0.0

                csv_rows.append(
                    {
                        "model_name": model_name,
                        "property": prop_name,
                        "doi": doi,
                        "num_target": result.num_target,
                        "num_extracted": result.num_extracted,
                        "num_matched": len(result.matched_pairs),
                        "precision": f"{result.precision:.4f}",
                        "recall": f"{result.recall:.4f}",
                        "f1": f"{result.f1:.4f}",
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "cost_usd": f"{cost:.6f}",
                    }
                )

                prop_matched += len(result.matched_pairs)
                prop_target += result.num_target
                prop_extracted += result.num_extracted
                prop_input_tokens += in_tok
                prop_output_tokens += out_tok
                prop_cost += cost

            all_comparison_results[prop_name] = comparison_results

            overall_p = prop_matched / prop_extracted if prop_extracted else 0.0
            overall_r = prop_matched / prop_target if prop_target else 0.0
            overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) else 0.0
            print(
                f"    {'OVERALL':<40s}  "
                f"P={overall_p:.0%}  R={overall_r:.0%}  F1={overall_f1:.0%}  "
                f"({prop_matched}/{prop_target} matched, {prop_extracted} extracted)  "
                f"tokens={prop_input_tokens}+{prop_output_tokens}  ${prop_cost:.4f}"
            )
            csv_rows.append(
                {
                    "model_name": model_name,
                    "property": prop_name,
                    "doi": "OVERALL",
                    "num_target": prop_target,
                    "num_extracted": prop_extracted,
                    "num_matched": prop_matched,
                    "precision": f"{overall_p:.4f}",
                    "recall": f"{overall_r:.4f}",
                    "f1": f"{overall_f1:.4f}",
                    "input_tokens": prop_input_tokens,
                    "output_tokens": prop_output_tokens,
                    "cost_usd": f"{prop_cost:.6f}",
                }
            )

            grand_matched += prop_matched
            grand_target += prop_target
            grand_extracted += prop_extracted
            grand_input_tokens += prop_input_tokens
            grand_output_tokens += prop_output_tokens
            grand_cost += prop_cost

        # Grand totals across all properties
        grand_p = grand_matched / grand_extracted if grand_extracted else 0.0
        grand_r = grand_matched / grand_target if grand_target else 0.0
        grand_f1 = 2 * grand_p * grand_r / (grand_p + grand_r) if (grand_p + grand_r) else 0.0
        print(
            f"\n  GRAND TOTAL  "
            f"P={grand_p:.0%}  R={grand_r:.0%}  F1={grand_f1:.0%}  "
            f"({grand_matched}/{grand_target} matched, {grand_extracted} extracted)  "
            f"tokens={grand_input_tokens}+{grand_output_tokens}  ${grand_cost:.4f}  "
            f"elapsed={elapsed:.1f}s"
        )

        # Write CSV
        model_csv_path = outputs_root / f"{model_name}.csv"
        model_csv_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = ["model_name", "property", "doi"] + [
            k for k in PROPERTY_CSV_KEYS if k not in ("model_name", "property")
        ]
        with open(model_csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"  -> {model_csv_path}")

        # Write prompts & responses for debugging
        for prop_name in properties_to_test:
            artifacts_dir = outputs_root / model_name / prop_name
            prop_outputs = extraction_outputs.get(prop_name, {})
            write_extraction_artifacts(artifacts_dir, prop_outputs)
        print(f"  -> {outputs_root / model_name}/ (prompts & responses)")

        # Write expected vs actual diff summary
        diff_path = outputs_root / model_name / "diff_summary.txt"
        write_property_diff_summary(
            diff_path,
            dois,
            properties_to_test,
            target_values,
            all_comparison_results,
            extraction_outputs,
        )
        print(f"  -> {diff_path}")

        # Print CSV for Google Sheets
        sheets_rows = [r for r in csv_rows if r.get("doi") == "OVERALL"]
        print(f"\n{'=' * 60}")
        print(",".join(PROPERTY_CSV_KEYS))
        for row in sheets_rows:
            print(dict_to_csv_string(row, PROPERTY_CSV_KEYS))

    return outputs_root


if __name__ == "__main__":
    dois = ["doi_10_3390__e18050189"]
    run_property_benchmark(
        model_names=[
            # "claude-haiku-4-5",
            # "gpt-5-mini-medium",
            # "gemini-3-flash",
            # "gpt-5-2-high",
            # "claude-opus-4-6",
            # "gemini-3.1-pro",
            "gemini-3.1-flash-lite",
        ],
        config=PropertyBenchmarkConfig(dois=dois),
    )
