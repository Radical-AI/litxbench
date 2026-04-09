"""Run each benchmark experiment N times and write an appendable JSON manifest.

Produces (or appends to) ``experiment_runs.json`` in the same directory as this
script.  Each key in the manifest maps to ``{"models": [...], "runs": [...]}``.

Usage:
  uv run python scripts/paper/run_experiments.py
  uv run python scripts/paper/run_experiments.py --dry-run   # first paper, 1 repeat
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

from scripts.paper.benchmarks.helpers.extraction_runner import (
    ExperimentBenchmarkConfig,
    configure_logfire,
    run_standard_benchmark,
)

configure_logfire()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

N_REPEATS = 3

STANDARD_MODELS = [
    "claude-haiku-4-5",
    "gpt-5-mini-medium",
    "gemini-3-flash",
    "claude-opus-4-6",
    "gpt-5-2-high",
    "gemini-3.1-pro",
]

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / "experiment_runs.json"


# ---------------------------------------------------------------------------
# Experiment functions (each returns a Path to the output directory)
# ---------------------------------------------------------------------------


def run_zero_shot(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from scripts.paper.benchmarks.tasks.zero_shot import extract_experiments_zero_shot

    return run_standard_benchmark(
        model_names=models,
        config=ExperimentBenchmarkConfig(name=run_group, dois=dois),
        output_subdir="zero_shot",
        extract_fn=extract_experiments_zero_shot,
    )


def run_zero_shot_json(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from scripts.paper.benchmarks.tasks.zero_shot_json import extract_experiments_zero_shot_json

    return run_standard_benchmark(
        model_names=models,
        config=ExperimentBenchmarkConfig(name=run_group, dois=dois),
        output_subdir="zero_shot_json",
        extract_fn=extract_experiments_zero_shot_json,
    )


def run_zero_shot_linear(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from scripts.paper.benchmarks.tasks.zero_shot_linear import extract_experiments_zero_shot_linear

    return run_standard_benchmark(
        model_names=models,
        config=ExperimentBenchmarkConfig(name=run_group, dois=dois),
        output_subdir="zero_shot_linear",
        extract_fn=extract_experiments_zero_shot_linear,
    )


def run_assemble_graph(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from litxbench.litxalloy import papers
    from scripts.paper.benchmarks.tasks.assemble_graph import extract_experiments_assemble_graph

    return run_standard_benchmark(
        model_names=models,
        config=ExperimentBenchmarkConfig(name=run_group, dois=dois),
        output_subdir="assemble_graph",
        extract_fn=lambda cfg: extract_experiments_assemble_graph(cfg, papers),
    )


# def run_two_stage(models: list[str]) -> Path:
#     from scripts.paper.benchmarks.tasks.two_stage import (
#         TwoStageExperimentBenchmarkConfig,
#         extract_experiments_two_stage,
#     )
#
#     return run_standard_benchmark(
#         model_names=models,
#         config=TwoStageExperimentBenchmarkConfig(),
#         output_subdir="two_stage",
#         extract_fn=extract_experiments_two_stage,
#     )


def run_composition_zero_shot(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from litxbench.core.utils import resolve_path
    from scripts.paper.benchmarks.tasks.composition_zero_shot import (
        CompositionBenchmarkConfig,
        run_composition_benchmark,
    )

    date_epoch = datetime.now().strftime("%Y%m%d_%s")
    outputs_root = Path(resolve_path("outputs")) / "compositions" / f"{run_group}_{date_epoch}"
    return run_composition_benchmark(
        model_names=models,
        config=CompositionBenchmarkConfig(dois=dois),
        outputs_root=outputs_root,
    )


def run_property_zero_shot(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from litxbench.core.utils import resolve_path
    from scripts.paper.benchmarks.tasks.property_zero_shot import (
        PropertyBenchmarkConfig,
        run_property_benchmark,
    )

    date_epoch = datetime.now().strftime("%Y%m%d_%s")
    outputs_root = Path(resolve_path("outputs")) / "properties" / f"{run_group}_{date_epoch}"
    return run_property_benchmark(
        model_names=models,
        config=PropertyBenchmarkConfig(dois=dois),
        outputs_root=outputs_root,
    )


AGENTIC_CLI_MODELS = [
    "claude_code",
    "codex",
    "gemini_cli",
]


def run_agentic_cli(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    """Run agentic CLI benchmark (Claude Code, Codex, Gemini CLI).

    The *models* parameter lists CLI names (matching AgenticCli enum values).
    """
    from litxbench.litxalloy import papers
    from litxbench.litxalloy.models import Material
    from scripts.paper.benchmarks.helpers.material_utils import (
        filter_materials_by_measurement_kinds,
    )
    from scripts.paper.benchmarks.tasks.zero_shot_agentic_cli import (
        AgenticCli,
        AgenticCliConfig,
        BenchmarkConfig,
        run_benchmark,
    )

    if dois is None:
        dois = list(papers.keys())
    selected_papers = {doi: papers[doi] for doi in dois}
    all_materials: dict[str, list[Material]] = {}
    for doi in selected_papers:
        all_materials[doi] = []
        for experiment in selected_papers[doi]:
            all_materials[doi].extend(experiment.output_materials)
    selected_materials = filter_materials_by_measurement_kinds(all_materials, None)

    cli_map = {e.value: e for e in AgenticCli}
    cli_configs = [AgenticCliConfig(cli=cli_map[m]) for m in models if m in cli_map]

    benchmark = BenchmarkConfig(name="default", cli_configs=cli_configs)
    outputs_root = run_benchmark(
        benchmark=benchmark,
        selected_materials=selected_materials,
        ground_truth=selected_papers,
        dois=dois,
    )
    if outputs_root is None:
        raise RuntimeError("Agentic CLI benchmark produced no outputs")
    return outputs_root


def run_match_graph(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from scripts.paper.benchmarks.helpers.matching_helpers import (
        redact_experiments_graph,
        run_matching_benchmark,
    )

    return run_matching_benchmark(
        model_names=models,
        redact_fn=redact_experiments_graph,
        output_subdir="match_graph",
        benchmark_name=run_group,
    )


def run_match_flat(models: list[str], run_group: str, dois: list[str] | None = None) -> Path:
    from scripts.paper.benchmarks.helpers.matching_helpers import (
        redact_experiments_flat,
        run_matching_benchmark,
    )

    return run_matching_benchmark(
        model_names=models,
        redact_fn=redact_experiments_flat,
        output_subdir="match_flat",
        benchmark_name=run_group,
    )


# ---------------------------------------------------------------------------
# Experiment registry — comment out entries to skip
# ---------------------------------------------------------------------------

EXPERIMENTS: dict[str, tuple] = {
    # "zero_shot": (run_zero_shot, STANDARD_MODELS),
    "zero_shot_json": (run_zero_shot_json, STANDARD_MODELS),
    # "zero_shot_linear": (run_zero_shot_linear, STANDARD_MODELS),
    # "assemble_graph": (run_assemble_graph, STANDARD_MODELS),
    # "two_stage": (run_two_stage, STANDARD_MODELS),
    # "agentic_cli": (run_agentic_cli, AGENTIC_CLI_MODELS),
    # "composition_zero_shot": (run_composition_zero_shot, STANDARD_MODELS),
    # "property_zero_shot": (run_property_zero_shot, STANDARD_MODELS),
    # "match_graph": (run_match_graph, STANDARD_MODELS),
    # "match_flat": (run_match_flat, STANDARD_MODELS),
}


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str) + "\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


MAX_WORKERS = int(os.environ.get("BENCH_MAX_WORKERS", 4))


def _run_one(
    name: str,
    run_fn,
    models: list[str],
    repeat: int,
    n_repeats: int,
    run_group: str,
    dois: list[str] | None = None,
) -> tuple[str, int, str]:
    """Execute a single experiment repeat. Returns (name, repeat, output_path)."""
    print(f"[start] {name} repeat {repeat + 1}/{n_repeats}")
    output_path = run_fn(models, run_group, dois=dois)
    print(f"[done]  {name} repeat {repeat + 1}/{n_repeats} -> {output_path}")
    return name, repeat, str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Quick smoke-test: first paper only, 1 repeat",
    )
    args = parser.parse_args()

    if args.dry_run:
        from litxbench.litxalloy import papers

        dry_run_dois = [next(iter(papers.keys()))]
        n_repeats = 1
        print(f"DRY RUN — 1 repeat, DOIs limited to: {dry_run_dois}")
    else:
        dry_run_dois = None
        n_repeats = N_REPEATS

    manifest = _load_manifest()
    run_group = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Build list of all (experiment, repeat) jobs
    jobs: list[tuple[str, object, list[str], int]] = []
    for name, (run_fn, models) in EXPERIMENTS.items():
        for i in range(n_repeats):
            jobs.append((name, run_fn, models, i))

    print(f"Run group: {run_group}")
    print(f"Running {len(jobs)} jobs sequentially\n")

    # Run all jobs sequentially
    results: dict[str, list[str]] = {name: [] for name in EXPERIMENTS}
    for name, run_fn, models, i in jobs:
        name, _repeat, output_path = _run_one(name, run_fn, models, i, n_repeats, run_group, dois=dry_run_dois)
        results[name].append(output_path)

    # Update manifest once all jobs are done
    for name, (_, models) in EXPERIMENTS.items():
        entry = {"models": models, "run_group": run_group, "runs": results[name]}
        manifest.setdefault(name, []).append(entry)

    _save_manifest(manifest)
    print(f"\nManifest updated: {MANIFEST_PATH}")
    for name in EXPERIMENTS:
        latest = manifest[name][-1]
        print(f"  {name}: {len(latest['runs'])} runs in group {run_group}")


if __name__ == "__main__":
    main()
