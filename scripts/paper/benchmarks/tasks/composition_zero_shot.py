"""Composition extraction benchmark.

Tests how well LLMs can parse the compositions of alloys/materials
that authors physically synthesized in a paper.  The LLM must write
Python code whose output is a list of pymatgen Composition objects.
"""

import asyncio
import csv
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, cast

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from pymatgen.core import Composition
from scipy.optimize import linear_sum_assignment

from litxbench.core.enums import MeasurementMethod
from litxbench.core.utils import dict_to_csv_string, load_transcribed_paper_text_only, resolve_path
from litxbench.litxalloy import (
    balance_composition,
    composition_with_weight_additions,
    papers,
)
from litxbench.litxalloy.models import (
    CompMeasurement,
    Experiment,
    Material,
)
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution_environment import (
    CodeExecutionToolResult,
    Repl,
    repl_tool,
)
from scripts.paper.benchmarks.helpers.comparison import ComparisonResult
from scripts.paper.benchmarks.helpers.extraction_runner import run_models_parallel, run_parallel
from scripts.paper.benchmarks.helpers.model_provider import (
    ModelProvider,
    get_model_from_name,
)
from scripts.paper.benchmarks.helpers.pricing import compute_cost
from scripts.paper.benchmarks.helpers.prompts import (
    composition_helpers,
)
from scripts.paper.benchmarks.helpers.reporting import (
    write_extraction_artifacts,
)


@dataclass
class CompositionBenchmarkConfig:
    """Configuration for the composition extraction benchmark."""

    dois: list[str] | None = None
    include_helpers: bool = True
    output_mode: Literal["code", "string"] = "code"
    max_workers: int = 25
    model_name: str = ""

    @property
    def run_name(self) -> str:
        helpers_flag = "with-helpers" if self.include_helpers else "no-helpers"
        return f"{self.output_mode}_{helpers_flag}"


@dataclass
class CompositionExtractionOutput:
    """Result of a single paper extraction: compositions plus raw artifacts."""

    compositions: list[Composition]
    prompt_text: str
    raw_response: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Target composition extraction from ground truth
# ---------------------------------------------------------------------------


def _best_composition_for_material(material: Material) -> Composition | None:
    """Return the highest-resolution composition measurement for a material.

    When a material has multiple CompMeasurements (e.g. nominal Balance and
    analytical EDS), return only the one from the most accurate method.
    """
    # Priority: lower index = higher priority (more accurate for bulk composition).
    _METHOD_PRIORITY: list[MeasurementMethod] = [
        MeasurementMethod.ICP_MS,
        MeasurementMethod.ICP_OES,
        MeasurementMethod.WD_XRF,
        MeasurementMethod.ED_XRF,
        MeasurementMethod.Spark_OES,
        MeasurementMethod.EPMA,
        MeasurementMethod.WDS,
        MeasurementMethod.EDS,
        MeasurementMethod.TEM_EDS,
        MeasurementMethod.LIBS,
        MeasurementMethod.Balance,
        MeasurementMethod.Unspecified,
    ]
    _priority_map = {m: i for i, m in enumerate(_METHOD_PRIORITY)}
    _default_priority = len(_METHOD_PRIORITY)

    comp_measurements = [m for m in material.measurements if isinstance(m, CompMeasurement)]
    if not comp_measurements:
        return None
    best = min(comp_measurements, key=lambda m: _priority_map.get(m.method, _default_priority))
    return best.composition


def extract_target_compositions(experiments: list[Experiment]) -> list[Composition]:
    """Extract material-level compositions from ground truth experiments.

    For each material, picks the highest-resolution composition measurement
    (e.g. XRF over EDS, EDS over nominal Balance).
    Does not include phase-level compositions inside Configuration objects.
    """
    compositions: list[Composition] = []
    for exp in experiments:
        for material in exp.output_materials:
            comp = _best_composition_for_material(material)
            if comp is not None:
                compositions.append(comp)
    return list(dict.fromkeys(compositions))


# ---------------------------------------------------------------------------
# Composition comparison
# ---------------------------------------------------------------------------


def _fractional_amounts(comp: Composition) -> dict[str, float]:
    """Get element fractional amounts from a composition."""
    total = comp.num_atoms
    if total == 0:
        return {}
    return {str(el): amt / total for el, amt in comp.items()}


def _composition_distance(a: Composition, b: Composition) -> float:
    """Max absolute difference in element fractions between two compositions.

    Returns 1.0 if either composition is empty.
    """
    fracs_a = _fractional_amounts(a)
    fracs_b = _fractional_amounts(b)
    all_elements = set(fracs_a.keys()) | set(fracs_b.keys())
    if not all_elements:
        return 1.0
    return max(abs(fracs_a.get(el, 0.0) - fracs_b.get(el, 0.0)) for el in all_elements)


CompositionComparisonResult = ComparisonResult[Composition, Composition]


def compare_compositions(
    target: list[Composition],
    extracted: list[Composition],
    tolerance: float = 0.02,
) -> CompositionComparisonResult:
    """Compare two lists of compositions using Hungarian matching.

    Uses max element-fraction difference as cost. Pairs with
    distance >= tolerance are treated as unmatched.
    """
    n_target = len(target)
    n_extracted = len(extracted)

    if n_target == 0 or n_extracted == 0:
        return CompositionComparisonResult(
            matched_pairs=[],
            unmatched_target=list(target),
            unmatched_extracted=list(extracted),
        )

    UNMATCHED_PENALTY = 1.0
    size = max(n_target, n_extracted)
    cost_matrix = [[UNMATCHED_PENALTY] * size for _ in range(size)]

    for i in range(n_target):
        for j in range(n_extracted):
            cost_matrix[i][j] = _composition_distance(target[i], extracted[j])

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    matched_pairs: list[tuple[Composition, Composition]] = []
    matched_target_indices: set[int] = set()
    matched_extracted_indices: set[int] = set()

    for r, c in zip(row_ind, col_ind):
        if r < n_target and c < n_extracted and cost_matrix[r][c] < tolerance:
            matched_pairs.append((target[r], extracted[c]))
            matched_target_indices.add(r)
            matched_extracted_indices.add(c)

    unmatched_target = [target[i] for i in range(n_target) if i not in matched_target_indices]
    unmatched_extracted = [extracted[j] for j in range(n_extracted) if j not in matched_extracted_indices]

    return CompositionComparisonResult(
        matched_pairs=matched_pairs,
        unmatched_target=unmatched_target,
        unmatched_extracted=unmatched_extracted,
    )


# ---------------------------------------------------------------------------
# Code extraction & validation
# ---------------------------------------------------------------------------


def _validate_compositions_code(
    response_text: str,
    execute: Callable[[str], CodeExecutionToolResult],
    namespace: dict[str, object],
) -> str:
    """Extract and validate the Python code block. Returns the validated code string."""
    code = extract_python_code_block(response_text)
    if not code:
        raise ModelRetry(
            "Return exactly one Python fenced code block and nothing else. "
            "The code must set a `result` variable to a list[Composition]."
        )

    execution_result = execute(code)
    if execution_result.stderr_output:
        raise ModelRetry(
            "The generated Python code failed at runtime. Fix it and try again.\n"
            f"Execution error:\n{execution_result.stderr_output}"
        )

    submitted = namespace.get("result")
    if not isinstance(submitted, list):
        raise ModelRetry("Code must set a `result` variable to a list[Composition].")

    for item in cast(list[object], submitted):
        if not isinstance(item, Composition):
            raise ModelRetry(f"Every item in `result` must be a Composition object, found {type(item)}.")
    return code


def _build_code_namespace(include_helpers: bool = True) -> dict[str, object]:
    ns: dict[str, object] = {"Composition": Composition}
    if include_helpers:
        ns["composition_with_weight_additions"] = composition_with_weight_additions
        ns["balance_composition"] = balance_composition
    return ns


def _execute_compositions_code(code: str, include_helpers: bool = True) -> list[Composition]:
    namespace = _build_code_namespace(include_helpers)
    exec(compile(code, "<compositions_code>", "exec"), namespace)
    return cast(list[Composition], namespace["result"])


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------


def _composition_scope_rules() -> str:
    return (
        "We are only interested in the compositions of alloys/materials that the authors physically "
        "made (synthesized) in their lab.\n"
        "Do NOT include:\n"
        "- Compositions mentioned in passing from other studies or references\n"
        "- Compositions from computational/theoretical predictions\n"
        "- Compositions of raw materials or precursors (e.g. pure elements)\n"
        "- Compositions of individual phases within a material (e.g. dendrite vs inter-dendrite regions)\n"
        "Only include the overall composition of each material the authors created.\n\n"
        "IMPORTANT: For each material, report only one composition — the one measured by the "
        "highest-resolution analytical technique available. Prefer analytically measured "
        "compositions over nominal/intended ones. The priority order from best to worst is:\n"
        "ICP-MS > ICP-OES > WD-XRF > EPMA > WDS > ED-XRF > Spark-OES > EDS > LIBS > nominal/Balance\n"
        "For example, if a paper reports both a nominal composition and an EDS-measured composition "
        "for the same material, use the EDS-measured one. If it reports both EDS and XRF for the "
        "same material, use the XRF measurement.\n\n"
        "Note: You only have access to the text of the paper. Images, figures, and tables "
        "rendered as images are not available, so rely solely on the textual content."
    )


def _composition_available_names(include_helpers: bool = True) -> str:
    text = """\
Available names in runtime:
- `Composition` (from `pymatgen.core`) — use to create composition objects
- `Composition("MgFeNi")` — from formula string (atomic ratio style)
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — from weight-percent dictionary"""
    if include_helpers:
        text += "\n- Composition helper functions: `balance_composition`, `composition_with_weight_additions`"
    return text


# ---------------------------------------------------------------------------
# String mode helpers
# ---------------------------------------------------------------------------


def _extract_formula_strings(response_text: str) -> list[str]:
    """Extract formula strings from response text (one per line)."""
    text = response_text
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            block = parts[1]
            # Remove optional language tag on first line
            if "\n" in block:
                first_line, rest = block.split("\n", 1)
                if first_line.strip() in ("", "python", "text"):
                    block = rest
            text = block

    formulas = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for prefix in ("- ", "* "):
            if line.startswith(prefix):
                line = line[len(prefix) :].strip()
        if line:
            formulas.append(line)
    return formulas


def _validate_compositions_string(response_text: str) -> list[Composition]:
    """Parse formula strings from response and return Composition objects."""
    formulas = _extract_formula_strings(response_text)
    if not formulas:
        raise ModelRetry(
            "No composition formulas found. Return one composition formula per line inside a fenced code block."
        )
    compositions: list[Composition] = []
    for formula in formulas:
        try:
            compositions.append(Composition(formula))
        except Exception as e:
            raise ModelRetry(
                f"Could not parse '{formula}' as a composition: {e}\n"
                "Each line must be a valid pymatgen Composition formula string."
            )
    return compositions


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_code_prompt(include_helpers: bool) -> str:
    """Build the prompt for code output mode."""
    example_lines = [
        '    Composition("MgFeNi"),',
        '    Composition("Al0.5CoCrFeNi"),',
        '    Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20}),',
    ]
    if include_helpers:
        example_lines.append('    balance_composition("Ti", {"Al": 6, "V": 4}),')

    parts = [
        "Extract all compositions of alloys/materials that the authors physically synthesized in this paper.\n\n",
        _composition_scope_rules(),
        "\n\n",
        "Return exactly one Python fenced code block and nothing else.\n",
        "The code must set a `result` variable to a `list[Composition]`.\n",
        "Each entry should be a `pymatgen.core.Composition` object representing one alloy the authors made.\n\n",
        "Example:\n",
        "```python\n",
        "result = [\n",
        "\n".join(example_lines),
        "\n]\n",
        "```\n\n",
        _composition_available_names(include_helpers),
    ]
    if include_helpers:
        parts.extend(["\n\n", composition_helpers()])
    return "".join(parts)


def _build_string_prompt() -> str:
    """Build the prompt for string output mode."""
    return (
        "Extract all compositions of alloys/materials that the authors physically "
        "synthesized in this paper.\n\n" + _composition_scope_rules() + "\n\n"
        "Return one composition formula per line inside a fenced code block.\n"
        "Each formula must be a valid chemical formula parseable by pymatgen's "
        "`Composition()` constructor.\n"
        "Use standard chemical formula notation (e.g. atomic ratio style).\n\n"
        "For weight-percent compositions, convert to the equivalent atomic-ratio "
        "formula.\n\n"
        "Example:\n"
        "```\n"
        "Al0.5CoCrFeNi\n"
        "MgFeNi\n"
        "Fe2O3\n"
        "```\n"
    )


# ---------------------------------------------------------------------------
# Agent extraction
# ---------------------------------------------------------------------------


async def _extract_compositions_zero_shot(
    doi: str, extraction_agent: Agent, config: CompositionBenchmarkConfig
) -> CompositionExtractionOutput:
    paper_text = load_transcribed_paper_text_only(doi)
    raw_response: str = ""

    if config.output_mode == "code":
        with Repl(initial_namespace=_build_code_namespace(config.include_helpers)) as repl:
            execute = repl_tool()
            validated_code: str | None = None

            def validate_code_output(response_text: str) -> str:
                nonlocal validated_code, raw_response
                raw_response = response_text
                validated_code = _validate_compositions_code(response_text, execute, repl.namespace)
                return response_text

            _ = extraction_agent.output_validator(validate_code_output)
            system_prompt = _build_code_prompt(config.include_helpers)
            prompt = [system_prompt, paper_text]
            result = await extraction_agent.run(prompt)
            assert validated_code is not None
            usage = result.usage()
            return CompositionExtractionOutput(
                compositions=_execute_compositions_code(validated_code, config.include_helpers),
                prompt_text=f"{system_prompt}\n<paper_text>",
                raw_response=raw_response,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )

    # string mode
    compositions: list[Composition] = []

    def validate_string_output(response_text: str) -> str:
        nonlocal compositions, raw_response
        raw_response = response_text
        compositions = _validate_compositions_string(response_text)
        return response_text

    _ = extraction_agent.output_validator(validate_string_output)
    system_prompt = _build_string_prompt()
    prompt = [system_prompt, paper_text]
    result = await extraction_agent.run(prompt)
    usage = result.usage()
    return CompositionExtractionOutput(
        compositions=compositions,
        prompt_text=f"{system_prompt}\n<paper_text>",
        raw_response=raw_response,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )


async def _extract_compositions_worker(
    doi: str, config: CompositionBenchmarkConfig
) -> tuple[str, CompositionExtractionOutput]:
    model_provider = ModelProvider()
    model = get_model_from_name(model_provider, config.model_name)
    extraction_agent = Agent(model=model, retries=3)
    output = await _extract_compositions_zero_shot(doi, extraction_agent, config)
    output.cost_usd = compute_cost(config.model_name, output.input_tokens, output.output_tokens)
    return doi, output


async def extract_compositions_zero_shot(
    config: CompositionBenchmarkConfig,
) -> dict[str, CompositionExtractionOutput]:
    dois = config.dois if config.dois is not None else list(papers.keys())
    return await run_parallel(dois, config.max_workers, _extract_compositions_worker, config)


# ---------------------------------------------------------------------------
# Display results
# ---------------------------------------------------------------------------


def print_composition_comparison(
    doi: str,
    result: CompositionComparisonResult,
    extraction_output: CompositionExtractionOutput | None = None,
) -> None:
    matched = len(result.matched_pairs)
    missed = [c.reduced_formula for c in result.unmatched_target]
    extra = [c.reduced_formula for c in result.unmatched_extracted]
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
        f"  {doi:<40s}  "
        f"P={result.precision:.0%}  R={result.recall:.0%}  F1={result.f1:.0%}  "
        f"({matched}/{result.num_target} matched, {result.num_extracted} extracted)"
        f"{cost_str}{detail}"
    )


def write_model_results(
    output_path: Path,
    dois: list[str],
    results: dict[str, CompositionComparisonResult],
) -> None:
    """Write a single flat CSV with all detail rows for one model.

    Creates *output_path* (e.g. ``<run_dir>/<model_name>.csv``) with columns:
    ``doi, status, target, extracted``.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["doi", "status", "target", "extracted"])
        writer.writeheader()
        for doi in dois:
            r = results[doi]
            for target_comp, extracted_comp in r.matched_pairs:
                writer.writerow(
                    {
                        "doi": doi,
                        "status": "matched",
                        "target": target_comp.reduced_formula,
                        "extracted": extracted_comp.reduced_formula,
                    }
                )
            for comp in r.unmatched_target:
                writer.writerow({"doi": doi, "status": "missed", "target": comp.reduced_formula, "extracted": ""})
            for comp in r.unmatched_extracted:
                writer.writerow({"doi": doi, "status": "extra", "target": "", "extracted": comp.reduced_formula})


COMPOSITION_CSV_KEYS = [
    "model_name",
    "num_target",
    "num_extracted",
    "num_matched",
    "precision",
    "recall",
    "f1",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "elapsed_seconds",
]


def run_composition_benchmark(
    model_names: list[str],
    config: CompositionBenchmarkConfig | None = None,
    outputs_root: Path | None = None,
) -> Path:
    if config is None:
        config = CompositionBenchmarkConfig()

    dois = config.dois or list(papers.keys())
    configs = {mn: replace(config, model_name=mn, dois=dois) for mn in model_names}

    if outputs_root is None:
        from datetime import datetime

        date_epoch = datetime.now().strftime("%Y%m%d_%s")
        outputs_root = Path(resolve_path("outputs")) / "compositions" / f"{config.run_name}_{date_epoch}"
    print(f"Saving results to: {outputs_root}")

    # Extract target compositions from ground truth (shared across models)
    target_compositions: dict[str, list[Composition]] = {doi: extract_target_compositions(papers[doi]) for doi in dois}

    # Extract compositions for all models in parallel
    all_extraction_outputs, model_elapsed = asyncio.run(run_models_parallel(configs, extract_compositions_zero_shot))

    # Compare results and write output for each model
    csv_rows: list[dict[str, str | int | float]] = []

    for model_name in model_names:
        print(f"\n[{model_name}]")
        extraction_outputs = all_extraction_outputs[model_name]

        all_matched = 0
        all_target = 0
        all_extracted = 0
        all_input_tokens = 0
        all_output_tokens = 0
        all_cost_usd = 0.0
        comparison_results: dict[str, CompositionComparisonResult] = {}

        for doi in dois:
            target = target_compositions[doi]
            extraction_output = extraction_outputs.get(doi)
            extracted = extraction_output.compositions if extraction_output else []
            result = compare_compositions(target, extracted)
            comparison_results[doi] = result
            print_composition_comparison(doi, result, extraction_output)

            in_tok = extraction_output.input_tokens if extraction_output else 0
            out_tok = extraction_output.output_tokens if extraction_output else 0
            cost = extraction_output.cost_usd if extraction_output else 0.0

            csv_rows.append(
                {
                    "model_name": model_name,
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

            all_matched += len(result.matched_pairs)
            all_target += result.num_target
            all_extracted += result.num_extracted
            all_input_tokens += in_tok
            all_output_tokens += out_tok
            all_cost_usd += cost

        elapsed = model_elapsed.get(model_name, 0.0)
        overall_p = all_matched / all_extracted if all_extracted else 0.0
        overall_r = all_matched / all_target if all_target else 0.0
        overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) else 0.0
        print(
            f"  {'OVERALL':<40s}  "
            f"P={overall_p:.0%}  R={overall_r:.0%}  F1={overall_f1:.0%}  "
            f"({all_matched}/{all_target} matched, {all_extracted} extracted)  "
            f"tokens={all_input_tokens}+{all_output_tokens}  ${all_cost_usd:.4f}  "
            f"elapsed={elapsed:.1f}s"
        )
        csv_rows.append(
            {
                "model_name": model_name,
                "doi": "OVERALL",
                "num_target": all_target,
                "num_extracted": all_extracted,
                "num_matched": all_matched,
                "precision": f"{overall_p:.4f}",
                "recall": f"{overall_r:.4f}",
                "f1": f"{overall_f1:.4f}",
                "input_tokens": all_input_tokens,
                "output_tokens": all_output_tokens,
                "cost_usd": f"{all_cost_usd:.6f}",
                "elapsed_seconds": f"{elapsed:.1f}",
            }
        )

        # Save detail file for this model
        model_output_path = outputs_root / f"{model_name}.csv"
        write_model_results(model_output_path, dois, comparison_results)
        print(f"  -> {model_output_path}")

        # Save prompts and raw responses for debugging
        artifacts_dir = outputs_root / model_name
        write_extraction_artifacts(artifacts_dir, extraction_outputs)
        print(f"  -> {artifacts_dir}/ (prompts & responses)")

    # Write combined results CSV
    results_path = outputs_root / "results.csv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["model_name", "doi"] + [k for k in COMPOSITION_CSV_KEYS if k != "model_name"]
    with open(results_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"\n  -> {results_path}")

    # Print CSV for Google Sheets
    sheets_rows = [r for r in csv_rows if r.get("doi") == "OVERALL"]
    print(f"\n{'=' * 60}")
    print(config)
    print(",".join(COMPOSITION_CSV_KEYS))
    for row in sheets_rows:
        print(dict_to_csv_string(row, COMPOSITION_CSV_KEYS))

    return outputs_root


MODELS = [
    # "gemini-2.5-flash",
    # "gemini-2.5-flash-lite",
    # "claude-haiku-4-5",
    # "claude-sonnet-4-5",
    # "gpt-4o",
    # "gpt-5-mini-medium",
    # "gpt-5-2-low",
    # "gemini-3-flash",
    # "claude-opus-4-6",
    # "gpt-5-2-high",
    # "gemini-3.1-pro",
    "gemini-3.1-flash-lite",
]


def run_code_with_helpers():
    run_composition_benchmark(
        model_names=MODELS,
        config=CompositionBenchmarkConfig(output_mode="code", include_helpers=True),
    )


def run_string():
    run_composition_benchmark(
        model_names=MODELS,
        config=CompositionBenchmarkConfig(output_mode="string", include_helpers=False),
    )


if __name__ == "__main__":
    run_code_with_helpers()
    # run_string()
