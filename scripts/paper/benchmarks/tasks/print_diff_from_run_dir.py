"""Evaluate an existing run directory without re-running extraction.

Supports zero_shot, zero_shot_json, zero_shot_agentic_cli, and knowmat2 run directories.

Usage:
    uv run python src/experiment_extraction_eval/evals/litxalloy/benchmarks/eval_from_run_dir.py <run_dir_path>

Examples:
    # Agentic CLI run:
    uv run python ... outputs/zero_shot_agentic_cli/default/claude_code

    # Zero-shot run:
    uv run python ... outputs/zero_shot/extract_all/claude-opus-4-6

    # Zero-shot JSON run:
    uv run python ... outputs/zero_shot_json/extract_all_json/gemini-3.1-pro

    # KnowMat2 run:
    uv run python ... outputs/knowmat2/std_1/knowmat2
"""

import json
import sys
from pathlib import Path

from litxbench.litxalloy import papers
from scripts.paper.benchmarks.helpers.block_extraction import extract_json_block, extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import execute_experiments_code
from scripts.paper.benchmarks.helpers.json_to_experiments import parse_and_construct
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
    evaluate_all_and_summarize,
    load_run_meta,
)
from scripts.paper.benchmarks.tasks.zero_shot_agentic_cli import (
    _execute_python_file_content,
)


def _load_agentic_cli_run(run_dir: Path) -> tuple[dict[str, ExtractionOutput], list[str], str]:
    """Load extraction outputs from an agentic CLI run directory."""
    config_path = run_dir / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    py_filename = config["output_python_filename"]
    model_name = config.get("cli", run_dir.name)

    env_dir = run_dir / "environment"
    doi_dirs = [d for d in sorted(env_dir.iterdir()) if d.is_dir()]

    extraction_outputs: dict[str, ExtractionOutput] = {}
    dois: list[str] = []
    for doi_dir in doi_dirs:
        safe_doi = doi_dir.name
        if safe_doi not in papers:
            print(f"Warning: {safe_doi} not found in ground truth papers, skipping")
            continue

        py_path = doi_dir / py_filename
        if not py_path.is_file():
            print(f"Warning: {py_filename} not found in {doi_dir}, skipping")
            continue

        try:
            python_content = py_path.read_text(encoding="utf-8")
            experiments = _execute_python_file_content(python_content)
            extraction_outputs[safe_doi] = ExtractionOutput(experiments=experiments)
            dois.append(safe_doi)
        except Exception as exc:
            print(f"Warning: failed to load {safe_doi}: {exc}")

    return extraction_outputs, dois, model_name


def _load_zero_shot_run(run_dir: Path) -> tuple[dict[str, ExtractionOutput], list[str], str]:
    """Load extraction outputs from a zero_shot run directory."""
    model_name = run_dir.name

    response_files = sorted(run_dir.glob("*.response.txt"))

    extraction_outputs: dict[str, ExtractionOutput] = {}
    dois: list[str] = []
    for response_file in response_files:
        safe_doi = response_file.name.removesuffix(".response.txt")
        if safe_doi not in papers:
            print(f"Warning: {safe_doi} not found in ground truth papers, skipping")
            continue

        try:
            raw_response = response_file.read_text(encoding="utf-8")
            code = extract_python_code_block(raw_response)
            if not code:
                print(f"Warning: no code block found in response for {safe_doi}, skipping")
                continue
            experiments = execute_experiments_code(code)
            extraction_outputs[safe_doi] = ExtractionOutput(
                experiments=experiments,
                raw_response=raw_response,
            )
            dois.append(safe_doi)
        except Exception as exc:
            print(f"Warning: failed to load {safe_doi}: {exc}")

    return extraction_outputs, dois, model_name


def _load_zero_shot_json_run(run_dir: Path) -> tuple[dict[str, ExtractionOutput], list[str], str]:
    """Load extraction outputs from a zero_shot_json run directory."""
    model_name = run_dir.name

    response_files = sorted(run_dir.glob("*.response.txt"))

    extraction_outputs: dict[str, ExtractionOutput] = {}
    dois: list[str] = []
    for response_file in response_files:
        safe_doi = response_file.name.removesuffix(".response.txt")
        if safe_doi not in papers:
            print(f"Warning: {safe_doi} not found in ground truth papers, skipping")
            continue

        try:
            raw_response = response_file.read_text(encoding="utf-8")
            json_str = extract_json_block(raw_response)
            if not json_str:
                print(f"Warning: no JSON block found in response for {safe_doi}, skipping")
                continue
            experiments = parse_and_construct(json_str)
            extraction_outputs[safe_doi] = ExtractionOutput(
                experiments=experiments,
                raw_response=raw_response,
            )
            dois.append(safe_doi)
        except Exception as exc:
            print(f"Warning: failed to load {safe_doi}: {exc}")

    return extraction_outputs, dois, model_name


def _load_knowmat2_run(run_dir: Path) -> tuple[dict[str, ExtractionOutput], list[str], str]:
    """Load extraction outputs from a KnowMat2 run directory.

    Expects DOI subdirectories containing {doi}_extraction.json files.
    """
    from scripts.paper.benchmarks.tasks.eval_knowmat2 import convert_knowmat2_entry

    model_name = run_dir.name  # e.g. "knowmat2"

    extraction_outputs: dict[str, ExtractionOutput] = {}
    dois: list[str] = []

    for doi_dir in sorted(run_dir.iterdir()):
        if not doi_dir.is_dir() or not doi_dir.name.startswith("doi_"):
            continue

        extraction_file = doi_dir / f"{doi_dir.name}_extraction.json"
        if not extraction_file.exists():
            continue

        safe_doi = doi_dir.name
        if safe_doi not in papers:
            print(f"Warning: {safe_doi} not found in ground truth papers, skipping")
            continue

        try:
            data = json.loads(extraction_file.read_text(encoding="utf-8"))
            compositions = data.get("compositions", [])
            experiments = []
            seen_formulas: set[str] = set()

            for entry in compositions:
                exp = convert_knowmat2_entry(entry)
                if exp is not None:
                    from litxbench.litxalloy.models import CompMeasurement as CM

                    comp = exp.output_materials[0].measurements[0]
                    if isinstance(comp, CM):
                        formula = comp.composition.reduced_formula
                        if formula in seen_formulas:
                            continue
                        seen_formulas.add(formula)
                    experiments.append(exp)

            if experiments:
                extraction_outputs[safe_doi] = ExtractionOutput(experiments=experiments)
                dois.append(safe_doi)
        except Exception as exc:
            print(f"Warning: failed to load {safe_doi}: {exc}")

    return extraction_outputs, dois, model_name


def _detect_run_type(run_dir: Path) -> str:
    """Detect whether a run directory is agentic_cli, zero_shot, zero_shot_json, or knowmat2."""
    if (run_dir / "environment").is_dir() and (run_dir / "config.json").is_file():
        return "agentic_cli"
    # Check for KnowMat2 format: DOI subdirs with _extraction.json files
    doi_dirs = [d for d in run_dir.iterdir() if d.is_dir() and d.name.startswith("doi_")]
    if doi_dirs:
        sample = doi_dirs[0]
        if (sample / f"{sample.name}_extraction.json").exists():
            return "knowmat2"
    response_files = sorted(run_dir.glob("*.response.txt"))
    if not response_files:
        raise ValueError(
            f"Cannot detect run type for {run_dir}. "
            "Expected either environment/ + config.json (agentic CLI), "
            "DOI subdirs with _extraction.json (KnowMat2), "
            "or *.response.txt files (zero-shot)."
        )
    # Peek at the first response to distinguish Python vs JSON format
    first_response = response_files[0].read_text(encoding="utf-8")
    if extract_json_block(first_response) and not extract_python_code_block(first_response):
        return "zero_shot_json"
    return "zero_shot"


def print_diff_from_run_dir(run_dir: Path) -> None:
    if not run_dir.is_dir():
        print(f"Error: run directory not found: {run_dir}", file=sys.stderr)
        sys.exit(1)

    run_type = _detect_run_type(run_dir)

    if run_type == "agentic_cli":
        extraction_outputs, dois, model_name = _load_agentic_cli_run(run_dir)
    elif run_type == "knowmat2":
        extraction_outputs, dois, model_name = _load_knowmat2_run(run_dir)
    elif run_type == "zero_shot_json":
        extraction_outputs, dois, model_name = _load_zero_shot_json_run(run_dir)
    else:
        extraction_outputs, dois, model_name = _load_zero_shot_run(run_dir)

    if not dois:
        print("Error: no DOIs successfully loaded", file=sys.stderr)
        sys.exit(1)

    # Restore per-DOI token/cost metadata from the original run
    run_meta = load_run_meta(run_dir)
    for doi, meta in run_meta.items():
        if doi in extraction_outputs:
            eo = extraction_outputs[doi]
            eo.input_tokens = meta.get("input_tokens", 0)
            eo.output_tokens = meta.get("output_tokens", 0)
            eo.cost_usd = meta.get("cost_usd", 0.0)
            eo.attempts = meta.get("attempts", 1)

    ground_truth = {doi: papers[doi] for doi in dois}

    evaluate_all_and_summarize(
        model_names=[model_name],
        dois=dois,
        ground_truth=ground_truth,
        all_extraction_outputs={model_name: extraction_outputs},
        model_output_dirs={model_name: run_dir},
        model_elapsed={},
        results_csv_path=run_dir / "results.csv",
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <run_dir_path>", file=sys.stderr)
        sys.exit(1)
    print_diff_from_run_dir(Path(sys.argv[1]).resolve())
