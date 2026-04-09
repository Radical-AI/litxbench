"""Re-display diffs from saved benchmark output.

Supports both zero_shot and zero_shot_agentic_cli output directories.

Usage:
    uv run src/scripts/view_diffs.py outputs/zero_shot/extract_all/claude-haiku-4-5
    uv run src/scripts/view_diffs.py outputs/zero_shot_agentic_cli/codex_20260228_.../
"""

import sys
from pathlib import Path

from litxbench.core.eval import compare_experiments
from litxbench.litxalloy import papers
from scripts.paper.benchmarks.helpers.block_extraction import extract_python_code_block
from scripts.paper.benchmarks.helpers.code_execution import (
    execute_experiments_code,
)
from scripts.paper.benchmarks.helpers.diff import print_one_call_diff_view
from scripts.paper.benchmarks.tasks.zero_shot_agentic_cli import (
    _execute_python_file_content,
)


def _view_diffs_zero_shot(output_dir: Path) -> None:
    """View diffs for zero_shot benchmark output (*.response.txt files)."""
    response_files = sorted(output_dir.glob("*.response.txt"))
    if not response_files:
        print(f"No *.response.txt files found in {output_dir}", file=sys.stderr)
        sys.exit(1)

    for response_file in response_files:
        doi_key = response_file.name.removesuffix(".response.txt")

        if doi_key not in papers:
            print(f"WARNING: {doi_key} not found in papers dataset, skipping")
            continue

        raw_response = response_file.read_text()
        code = extract_python_code_block(raw_response)
        if not code:
            print(f"WARNING: no Python code block found in {response_file.name}, skipping")
            continue

        try:
            extracted_experiments = execute_experiments_code(code)
        except Exception as e:
            print(f"WARNING: code execution failed for {doi_key}: {e}, skipping")
            continue

        target_experiments = papers[doi_key]
        result = compare_experiments(target_experiments, extracted_experiments)
        print_one_call_diff_view(result, label=doi_key)
        print()


def _find_generated_python_file(doi_dir: Path) -> Path | None:
    """Find the generated Python file in an agentic CLI DOI sandbox directory.

    Looks for .py files that aren't __init__.py or part of the sandbox package.
    Falls back to checking config.json for the expected filename.
    """
    # Try reading the output filename from config.json at the run root
    config_path = doi_dir.parent / "config.json"
    if config_path.is_file():
        import json

        try:
            config = json.loads(config_path.read_text())
            expected_name = config.get("output_python_filename")
            if expected_name:
                candidate = doi_dir / expected_name
                if candidate.is_file():
                    return candidate
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: find .py files directly in the doi_dir (not in subdirectories)
    candidates = [f for f in sorted(doi_dir.glob("*.py")) if f.name != "__init__.py" and f.name != "pyproject.toml"]
    return candidates[0] if candidates else None


def _view_diffs_agentic_cli(output_dir: Path) -> None:
    """View diffs for zero_shot_agentic_cli output (per-DOI subdirectories with .py files)."""
    doi_dirs = sorted(d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith("doi_"))
    if not doi_dirs:
        print(f"No doi_* subdirectories found in {output_dir}", file=sys.stderr)
        sys.exit(1)

    for doi_dir in doi_dirs:
        doi_key = doi_dir.name

        if doi_key not in papers:
            print(f"WARNING: {doi_key} not found in papers dataset, skipping")
            continue

        py_file = _find_generated_python_file(doi_dir)
        if py_file is None:
            print(f"WARNING: no generated Python file found in {doi_dir}, skipping")
            continue

        content = py_file.read_text()
        try:
            extracted_experiments = _execute_python_file_content(content)
        except Exception as e:
            print(f"WARNING: execution failed for {doi_key}: {e}, skipping")
            continue

        target_experiments = papers[doi_key]
        result = compare_experiments(target_experiments, extracted_experiments)
        print_one_call_diff_view(result, label=doi_key)
        print()


def _detect_output_type(output_dir: Path) -> str:
    """Detect whether the directory contains zero_shot or agentic_cli output."""
    if list(output_dir.glob("*.response.txt")):
        return "zero_shot"
    if any(d.is_dir() and d.name.startswith("doi_") for d in output_dir.iterdir()):
        return "agentic_cli"
    return "unknown"


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: uv run src/scripts/view_diffs.py <model-output-dir>\n\n"
            "Supports both zero_shot (*.response.txt) and agentic_cli (doi_* subdirs) output.",
            file=sys.stderr,
        )
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    if not output_dir.is_dir():
        print(f"Error: {output_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    output_type = _detect_output_type(output_dir)

    if output_type == "zero_shot":
        _view_diffs_zero_shot(output_dir)
    elif output_type == "agentic_cli":
        _view_diffs_agentic_cli(output_dir)
    else:
        print(
            f"Error: could not detect output type in {output_dir}. "
            "Expected *.response.txt files (zero_shot) or doi_* subdirectories (agentic_cli).",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
