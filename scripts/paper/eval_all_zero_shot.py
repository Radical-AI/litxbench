"""Evaluate all run directories and combine results into CSVs.

Reads experiment_runs.json manifest and evaluates all experiments,
producing per-run combined CSVs and a summary with 95% confidence intervals.

Produces (in paper/combined_results/):
  {experiment}_run{N}.csv          (per-run combined results)
  zero_shot_summary_with_ci.csv    (summary with 95% CIs across runs)

Usage:
  uv run python paper/eval_all_zero_shot.py
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from scipy.stats import t as t_dist

from scripts.paper.benchmarks.tasks.print_diff_from_run_dir import print_diff_from_run_dir

PAPER_DIR = Path(__file__).resolve().parent


def eval_and_combine(run_dirs: list[Path], combined_csv: Path) -> None:
    """Run evaluation on each directory, then merge their results.csv into one."""
    all_rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None

    for run_dir in run_dirs:
        model_name = run_dir.name
        print(f"\n{'=' * 60}")
        print(f"Evaluating: {model_name}")
        print(f"  {run_dir}")
        print(f"{'=' * 60}")

        print_diff_from_run_dir(run_dir)

        results_csv = run_dir / "results.csv"
        if not results_csv.is_file():
            print(f"WARNING: no results.csv produced for {model_name}, skipping")
            continue

        with open(results_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if fieldnames is None:
                fieldnames = reader.fieldnames or []
            for row in reader:
                all_rows.append(row)

    if not all_rows or fieldnames is None:
        print("ERROR: no results collected")
        return

    with open(combined_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nCombined results written to: {combined_csv}")
    print(f"Total rows: {len(all_rows)}")


MODEL_DISPLAY_NAMES = {
    "knowmat2": "KnowMat2",
    "claude-haiku-4-5": "Claude Haiku 4.5",
    "gpt-5-mini-medium": "GPT 5 Mini Medium",
    "gemini-3-flash": "Gemini 3 Flash",
    "claude-opus-4-6": "Claude Opus 4.6",
    "gpt-5-2-high": "GPT 5.2 High",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "claude_code": "Claude Code (Opus 4.6)",
    "codex": "Codex (GPT 5.2 Codex High)",
    "gemini_cli": "Gemini CLI (Gemini-3.1 Pro Preview)",
}

# Canonical order for the comparison table
MODEL_ORDER = [
    "knowmat2",
    "claude-haiku-4-5",
    "gpt-5-mini-medium",
    "gemini-3-flash",
    "claude-opus-4-6",
    "gpt-5-2-high",
    "gemini-3.1-pro",
    "claude_code",
    "codex",
    "gemini_cli",
]


SUMMARY_FIELDS = [
    "method",
    "overall_precision",
    "overall_recall",
    "overall_f1",
    "meas_f1",
    "process_f1",
    "material_f1",
    "config_f1",
    "avg_attempts",
    "cost_usd",
]

# Fields for the JSON vs code output comparison table
JSON_VS_CODE_FIELDS = [
    "model",
    "output_json_f1",
    "output_json_attempts",
    "output_code_f1",
    "output_code_attempts",
]

# Models shared between zero_shot and zero_shot_json experiments
JSON_VS_CODE_MODELS = [
    "claude-haiku-4-5",
    "gpt-5-mini-medium",
    "gemini-3-flash",
    "claude-opus-4-6",
    "gpt-5-2-high",
    "gemini-3.1-pro",
]

# Fields for the assemble_graph summary table
ASSEMBLE_GRAPH_FIELDS = [
    "model_name",
    "overall_precision",
    "overall_recall",
    "overall_f1",
    "avg_attempts",
]

# Models in the assemble_graph experiment
ASSEMBLE_GRAPH_MODELS = [
    "claude-haiku-4-5",
    "gpt-5-mini-medium",
    "gemini-3-flash",
    "claude-opus-4-6",
    "gpt-5-2-high",
    "gemini-3.1-pro",
]

# Fields for the extract single property table
PROPERTY_SUMMARY_FIELDS = [
    "property",
    "precision",
    "recall",
    "f1",
    "cost_usd",
]

# Properties in canonical order
PROPERTY_ORDER = [
    "ultimate_tensile_strength",
    "ultimate_compressive_strength",
    "fracture_strain_tension",
    "fracture_strain_compression",
    "vickers_hardness",
]

# Fields for the composition string-vs-code comparison table
COMPOSITION_FIELDS = [
    "model",
    "string_f1",
    "string_cost_usd",
    "code_helpers_f1",
    "code_helpers_cost_usd",
]

COMPOSITION_MODELS = [
    "claude-haiku-4-5",
    "gpt-5-mini-medium",
    "gemini-3-flash",
    "claude-opus-4-6",
    "gpt-5-2-high",
    "gemini-3.1-pro",
]

# Fields for the process F1 with CI table
PROCESS_F1_FIELDS = [
    "method",
    "process_f1",
]

# Fields from results.csv to average, mapped to output column name
_AVG_COLS = {
    "overall_precision": "overall_precision",
    "overall_recall": "overall_recall",
    "overall_f1": "overall_f1",
    "measurement_f1": "meas_f1",
    "process_f1": "process_f1",
    "material_f1": "material_f1",
    "config_f1": "config_f1",
    "avg_attempts": "avg_attempts",
    "cost_usd": "cost_usd",
}


def _summarize_csv(combined_csv: Path) -> dict[str, dict[str, str]]:
    """Read a combined results CSV and return per-model summary dicts."""
    with open(combined_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    by_model: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("doi") == "OVERALL":
            continue
        by_model[row["model_name"]].append(row)

    summaries: dict[str, dict[str, str]] = {}
    for model_name, model_rows in by_model.items():
        summary: dict[str, str] = {}
        summary["method"] = MODEL_DISPLAY_NAMES.get(model_name, model_name)
        for src_col, dst_col in _AVG_COLS.items():
            vals = []
            for r in model_rows:
                raw = r.get(src_col, "") or ""
                try:
                    vals.append(float(raw))
                except ValueError:
                    pass
            if vals:
                if dst_col == "cost_usd":
                    total = sum(vals)
                    summary[dst_col] = f"{total:.6g}"
                elif dst_col == "avg_attempts":
                    avg = sum(vals) / len(vals)
                    summary[dst_col] = f"{avg:.2f}"
                else:
                    avg = sum(vals) / len(vals)
                    summary[dst_col] = f"{avg:.4f}"
            else:
                summary[dst_col] = "N/A"
        summaries[model_name] = summary
    return summaries


# ---------------------------------------------------------------------------
# Confidence interval helpers
# ---------------------------------------------------------------------------


def confidence_interval_95(values: list[float]) -> tuple[float, float]:
    """Return (mean, ci_half_width) for 95% CI using Student's t-distribution."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    mean = sum(values) / n
    if n == 1:
        return (mean, 0.0)
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_err = math.sqrt(variance / n)
    t_val = t_dist.ppf(1 - 0.05 / 2, df=n - 1)
    return (mean, t_val * std_err)


def load_manifest(path: Path) -> dict:
    """Read experiment_runs.json manifest."""
    return json.loads(path.read_text())


def _get_run_model_dirs(run_root: Path, models: list[str]) -> list[Path]:
    """Given a run root directory, return the model subdirectories."""
    return [run_root / m for m in models if (run_root / m).is_dir()]


def _summarize_csv_with_ci(
    combined_csvs: list[Path],
) -> dict[str, dict[str, str]]:
    """Read N combined CSVs (one per repeat), compute mean +/- 95% CI per model.

    Returns {model_name: {col: "mean +/- ci", ...}} with the same columns
    as _summarize_csv.
    """
    # Collect per-model, per-column values across all runs
    # Each combined CSV has the same structure: rows grouped by model
    per_model_vals: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for csv_path in combined_csvs:
        if not csv_path.is_file():
            continue
        run_summaries = _summarize_csv(csv_path)
        for model_name, summary in run_summaries.items():
            for col, val_str in summary.items():
                if col == "method":
                    continue
                try:
                    per_model_vals[model_name][col].append(float(val_str))
                except (ValueError, TypeError):
                    pass

    summaries: dict[str, dict[str, str]] = {}
    for model_name, col_vals in per_model_vals.items():
        summary: dict[str, str] = {}
        summary["method"] = MODEL_DISPLAY_NAMES.get(model_name, model_name)
        for col, vals in col_vals.items():
            mean, ci = confidence_interval_95(vals)
            show_ci = col == "overall_f1" and ci != 0
            if col == "cost_usd":
                summary[col] = f"{mean:.6g}"
            elif col == "avg_attempts":
                summary[col] = f"{mean:.2f}"
            elif show_ci:
                summary[col] = f"{mean:.4f} +/- {ci:.4f}"
            else:
                summary[col] = f"{mean:.4f}"
        summaries[model_name] = summary
    return summaries


_ZERO_SHOT_SUMMARY_EXPERIMENTS = {"zero_shot", "agentic_cli", "knowmat2"}


def build_zero_shot_summary_with_ci(
    combined_csvs_by_method: dict[str, list[Path]],
    out_csv: Path,
) -> None:
    """Build combined zero-shot summary table with 95% CIs from multiple runs."""
    all_summaries: dict[str, dict[str, str]] = {}

    for method_name, csv_list in combined_csvs_by_method.items():
        if method_name not in _ZERO_SHOT_SUMMARY_EXPERIMENTS:
            continue
        method_summaries = _summarize_csv_with_ci(csv_list)
        all_summaries.update(method_summaries)

    rows = []
    for model_key in MODEL_ORDER:
        if model_key in all_summaries:
            rows.append(all_summaries[model_key])

    if not rows:
        print("WARNING: no summary rows produced")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nZero-shot summary with CI written to: {out_csv}")
    print("\t".join(SUMMARY_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in SUMMARY_FIELDS))


def build_json_vs_code_csv(
    combined_csvs_by_method: dict[str, list[Path]],
    out_csv: Path,
) -> None:
    """Build comparison table of JSON output vs code output zero-shot results."""
    json_csvs = combined_csvs_by_method.get("zero_shot_json", [])
    code_csvs = combined_csvs_by_method.get("zero_shot", [])

    if not json_csvs and not code_csvs:
        print("WARNING: no zero_shot or zero_shot_json CSVs found, skipping JSON vs code table")
        return

    json_summaries = _summarize_csv_with_ci(json_csvs) if json_csvs else {}
    code_summaries = _summarize_csv_with_ci(code_csvs) if code_csvs else {}

    rows = []
    for model_key in JSON_VS_CODE_MODELS:
        row: dict[str, str] = {}
        row["model"] = MODEL_DISPLAY_NAMES.get(model_key, model_key)

        json_s = json_summaries.get(model_key, {})
        code_s = code_summaries.get(model_key, {})

        row["output_json_f1"] = json_s.get("overall_f1", "N/A")
        row["output_json_attempts"] = json_s.get("avg_attempts", "N/A")
        row["output_code_f1"] = code_s.get("overall_f1", "N/A")
        row["output_code_attempts"] = code_s.get("avg_attempts", "N/A")

        rows.append(row)

    if not rows:
        print("WARNING: no rows for JSON vs code comparison")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=JSON_VS_CODE_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nJSON vs Code comparison written to: {out_csv}")
    print("\t".join(JSON_VS_CODE_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in JSON_VS_CODE_FIELDS))


def build_assemble_graph_csv(
    combined_csvs_by_method: dict[str, list[Path]],
    out_csv: Path,
) -> None:
    """Build summary table for assemble_graph experiment results."""
    ag_csvs = combined_csvs_by_method.get("assemble_graph", [])

    if not ag_csvs:
        print("WARNING: no assemble_graph CSVs found, skipping assemble_graph table")
        return

    ag_summaries = _summarize_csv_with_ci(ag_csvs)

    rows = []
    for model_key in ASSEMBLE_GRAPH_MODELS:
        if model_key not in ag_summaries:
            continue
        s = ag_summaries[model_key]
        row: dict[str, str] = {}
        row["model_name"] = model_key
        row["overall_precision"] = s.get("overall_precision", "N/A")
        row["overall_recall"] = s.get("overall_recall", "N/A")
        row["overall_f1"] = s.get("overall_f1", "N/A")
        row["avg_attempts"] = s.get("avg_attempts", "N/A")
        rows.append(row)

    if not rows:
        print("WARNING: no rows for assemble_graph summary")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ASSEMBLE_GRAPH_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nAssemble graph summary written to: {out_csv}")
    print("\t".join(ASSEMBLE_GRAPH_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in ASSEMBLE_GRAPH_FIELDS))


def build_process_f1_csv(
    combined_csvs_by_method: dict[str, list[Path]],
    out_csv: Path,
) -> None:
    """Build table showing process F1 with 95% CIs for all zero-shot models."""
    per_model_vals: dict[str, list[float]] = defaultdict(list)

    for method_name, csv_list in combined_csvs_by_method.items():
        if method_name not in _ZERO_SHOT_SUMMARY_EXPERIMENTS:
            continue
        for csv_path in csv_list:
            if not csv_path.is_file():
                continue
            run_summaries = _summarize_csv(csv_path)
            for model_name, summary in run_summaries.items():
                val_str = summary.get("process_f1", "")
                try:
                    per_model_vals[model_name].append(float(val_str))
                except (ValueError, TypeError):
                    pass

    rows = []
    for model_key in MODEL_ORDER:
        if model_key not in per_model_vals:
            continue
        vals = per_model_vals[model_key]
        mean, ci = confidence_interval_95(vals)
        row: dict[str, str] = {}
        row["method"] = MODEL_DISPLAY_NAMES.get(model_key, model_key)
        if ci != 0:
            row["process_f1"] = f"{mean:.4f} +/- {ci:.4f}"
        else:
            row["process_f1"] = f"{mean:.4f}"
        rows.append(row)

    if not rows:
        print("WARNING: no rows for process F1 summary")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PROCESS_F1_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProcess F1 summary written to: {out_csv}")
    print("\t".join(PROCESS_F1_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in PROCESS_F1_FIELDS))


def build_property_summary_csv(
    property_csvs: list[Path],
    out_csv: Path,
) -> None:
    """Build per-property summary table from multiple property benchmark CSVs.

    Reads OVERALL rows from each CSV (one per run), computes mean values,
    and adds 95% CI on the F1 column.
    """
    # Collect per-property, per-column values across runs
    per_prop_vals: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for property_csv in property_csvs:
        if not property_csv.is_file():
            print(f"WARNING: {property_csv} not found, skipping")
            continue

        with open(property_csv, newline="", encoding="utf-8") as f:
            all_rows = list(csv.DictReader(f))

        for row in all_rows:
            if row.get("doi") == "OVERALL":
                prop = row["property"]
                for col in ("precision", "recall", "f1", "cost_usd"):
                    try:
                        per_prop_vals[prop][col].append(float(row[col]))
                    except (ValueError, KeyError):
                        pass

    rows = []
    for prop_name in PROPERTY_ORDER:
        if prop_name not in per_prop_vals:
            continue
        col_vals = per_prop_vals[prop_name]
        row: dict[str, str] = {"property": prop_name}

        for col in ("precision", "recall", "f1", "cost_usd"):
            vals = col_vals.get(col, [])
            if not vals:
                row[col] = "N/A"
                continue
            mean, ci = confidence_interval_95(vals)
            if col == "cost_usd":
                row[col] = f"{mean:.6g}"
            elif col == "f1":
                row[col] = f"{mean:.4f} +/- {ci:.4f}"
            else:
                row[col] = f"{mean:.4f}"

        rows.append(row)

    if not rows:
        print("WARNING: no OVERALL rows found in property CSVs")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PROPERTY_SUMMARY_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProperty summary written to: {out_csv}")
    print("\t".join(PROPERTY_SUMMARY_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in PROPERTY_SUMMARY_FIELDS))


def _composition_overall_by_model(results_csv: Path) -> dict[str, dict[str, float]]:
    """Read a composition results.csv and return {model: {f1, cost_usd}} from OVERALL rows."""
    with open(results_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        if row.get("doi") == "OVERALL":
            out[row["model_name"]] = {
                "f1": float(row["f1"]),
                "cost_usd": float(row["cost_usd"]),
            }
    return out


def build_composition_summary_csv(
    string_run_dirs: list[Path],
    code_helpers_run_dirs: list[Path],
    out_csv: Path,
) -> None:
    """Build composition string-vs-code comparison table with 95% CIs."""
    # Collect per-model values across runs
    string_vals: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    code_vals: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for run_dir in string_run_dirs:
        results_csv = run_dir / "results.csv"
        if not results_csv.is_file():
            continue
        for model, vals in _composition_overall_by_model(results_csv).items():
            string_vals[model]["f1"].append(vals["f1"])
            string_vals[model]["cost_usd"].append(vals["cost_usd"])

    for run_dir in code_helpers_run_dirs:
        results_csv = run_dir / "results.csv"
        if not results_csv.is_file():
            continue
        for model, vals in _composition_overall_by_model(results_csv).items():
            code_vals[model]["f1"].append(vals["f1"])
            code_vals[model]["cost_usd"].append(vals["cost_usd"])

    rows = []
    for model_key in COMPOSITION_MODELS:
        row: dict[str, str] = {}
        row["model"] = MODEL_DISPLAY_NAMES.get(model_key, model_key)

        # String mode
        s_f1 = string_vals.get(model_key, {}).get("f1", [])
        s_cost = string_vals.get(model_key, {}).get("cost_usd", [])
        if s_f1:
            mean, ci = confidence_interval_95(s_f1)
            row["string_f1"] = f"{mean:.4f} +/- {ci:.4f}" if ci != 0 else f"{mean:.4f}"
        else:
            row["string_f1"] = "N/A"
        if s_cost:
            mean, ci = confidence_interval_95(s_cost)
            row["string_cost_usd"] = f"{mean:.6g}"
        else:
            row["string_cost_usd"] = "N/A"

        # Code with helpers mode
        c_f1 = code_vals.get(model_key, {}).get("f1", [])
        c_cost = code_vals.get(model_key, {}).get("cost_usd", [])
        if c_f1:
            mean, ci = confidence_interval_95(c_f1)
            row["code_helpers_f1"] = f"{mean:.4f} +/- {ci:.4f}" if ci != 0 else f"{mean:.4f}"
        else:
            row["code_helpers_f1"] = "N/A"
        if c_cost:
            mean, ci = confidence_interval_95(c_cost)
            row["code_helpers_cost_usd"] = f"{mean:.6g}"
        else:
            row["code_helpers_cost_usd"] = "N/A"

        rows.append(row)

    if not rows:
        print("WARNING: no rows for composition summary")
        return

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPOSITION_FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nComposition summary written to: {out_csv}")
    print("\t".join(COMPOSITION_FIELDS))
    for row in rows:
        print("\t".join(row.get(f, "") for f in COMPOSITION_FIELDS))


# ---------------------------------------------------------------------------
# Multi-trial evaluation from manifest
# ---------------------------------------------------------------------------


def _eval_manifest(manifest: dict, out_dir: Path) -> None:
    """Evaluate all experiments in the manifest and produce CI summaries.

    Each manifest value is a list of run-group entries (as produced by
    run_experiments.py).  We use only the latest (last) entry per experiment.
    """
    combined_csvs_by_method: dict[str, list[Path]] = defaultdict(list)

    for experiment_name, run_groups in manifest.items():
        # run_groups is a list of {"models": [...], "runs": [...], ...}
        # Use the latest run group.
        info = run_groups[-1]
        if "models" not in info:
            # Composition entries are handled separately
            continue
        models = info["models"]
        runs = [Path(r) for r in info["runs"]]

        print(f"\n{'=' * 60}")
        print(f"EXPERIMENT: {experiment_name} ({len(runs)} runs)")
        print(f"{'=' * 60}")

        for i, run_root in enumerate(runs):
            print(f"\n--- Run {i + 1}: {run_root} ---")
            model_dirs = _get_run_model_dirs(run_root, models)
            if not model_dirs:
                print(f"  WARNING: no model dirs found in {run_root}")
                continue

            combined_csv = out_dir / f"{experiment_name}_run{i + 1}.csv"
            eval_and_combine(model_dirs, combined_csv)
            combined_csvs_by_method[experiment_name].append(combined_csv)

        # Print per-experiment CI summary
        if combined_csvs_by_method[experiment_name]:
            print(
                f"\n--- {experiment_name}: CI summary across {len(combined_csvs_by_method[experiment_name])} runs ---"
            )
            ci_summaries = _summarize_csv_with_ci(combined_csvs_by_method[experiment_name])
            for model_name in MODEL_ORDER:
                if model_name in ci_summaries:
                    s = ci_summaries[model_name]
                    print(
                        f"  {s.get('method', model_name):<24s}  F1={s.get('overall_f1', 'N/A'):<20s}  cost={s.get('cost_usd', 'N/A')}"
                    )

    # Build combined summary with CIs
    if combined_csvs_by_method:
        build_zero_shot_summary_with_ci(
            combined_csvs_by_method,
            out_csv=out_dir / "zero_shot_summary_with_ci.csv",
        )
        build_json_vs_code_csv(
            combined_csvs_by_method,
            out_csv=out_dir / "json_vs_code_comparison.csv",
        )
        build_assemble_graph_csv(
            combined_csvs_by_method,
            out_csv=out_dir / "assemble_graph_summary.csv",
        )
        build_process_f1_csv(
            combined_csvs_by_method,
            out_csv=out_dir / "process_f1_summary.csv",
        )


if __name__ == "__main__":
    out_dir = PAPER_DIR / "combined_results"
    out_dir.mkdir(exist_ok=True)

    manifest_path = PAPER_DIR / "experiment_runs.json"
    manifest = load_manifest(manifest_path)
    _eval_manifest(manifest, out_dir)

    # Property extraction summary from manifest runs
    property_runs = [Path(r) for r in manifest.get("properties", [{}])[-1].get("runs", [])]
    property_csvs = [r / "gemini-3.1-pro.csv" for r in property_runs if (r / "gemini-3.1-pro.csv").is_file()]
    if property_csvs:
        build_property_summary_csv(
            property_csvs=property_csvs,
            out_csv=out_dir / "property_summary_gemini_3.1_pro.csv",
        )

    # Composition extraction: string vs code+helpers comparison
    string_runs = [Path(r) for r in manifest.get("composition_string", [{}])[-1].get("runs", [])]
    code_runs = [Path(r) for r in manifest.get("composition_code_helpers", [{}])[-1].get("runs", [])]
    if string_runs or code_runs:
        build_composition_summary_csv(
            string_run_dirs=string_runs,
            code_helpers_run_dirs=code_runs,
            out_csv=out_dir / "composition_string_vs_code.csv",
        )
