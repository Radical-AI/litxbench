"""Shared eval/output logic for experiment extraction benchmarks.

Provides the common evaluation loop, reporting, and output-writing that
both ``zero_shot.py`` and ``zero_shot_agentic_cli.py`` use.
"""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from litxbench.core.eval import (
    ExperimentComparisonResult,
    MaterialMatchResult,
    MultiLevelMetrics,
    compare_experiments,
    compute_multi_level_metrics,
)
from litxbench.core.hallucination import count_hallucinations
from litxbench.litxalloy.models import (
    CompMeasurement,
    Experiment,
    Material,
)
from scripts.paper.benchmarks.helpers.diff import print_one_call_diff_view

# ---------------------------------------------------------------------------
# Shared dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractionOutput:
    """Result of a single paper extraction: experiments plus raw artifacts."""

    experiments: list[Experiment]
    prompt_text: str = ""
    raw_response: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    attempts: int = 1
    context_resets: int = 0
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def sanitize_doi(doi: str) -> str:
    """Sanitize a DOI string for use as a filename."""
    return doi.replace("/", "_").replace(":", "_")


def _format_metrics_row(
    *,
    num_target_items: int,
    num_extracted_items: int,
    num_matched_items: float,
    num_target_materials: int,
    num_extracted_materials: int,
    num_matched_materials: int,
    avg_ped: float,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    avg_attempts: float,
    ml: MultiLevelMetrics,
    num_hallucinated: int = 0,
    num_total_numbers: int = 0,
    hallucination_rate: float = 0.0,
) -> dict[str, str | int | float]:
    """Build a formatted metrics row dict for CSV / Google-Sheets output."""
    return {
        "overall_precision": f"{ml.overall_precision:.4f}",
        "overall_recall": f"{ml.overall_recall:.4f}",
        "overall_f1": f"{ml.overall_f1:.4f}",
        "num_target_items": num_target_items,
        "num_extracted_items": num_extracted_items,
        "num_matched_items": f"{num_matched_items:.2f}",
        "num_target_materials": num_target_materials,
        "num_extracted_materials": num_extracted_materials,
        "num_matched_materials": num_matched_materials,
        "avg_process_edit_distance": f"{avg_ped:.4f}",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": f"{cost_usd:.6f}",
        "avg_attempts": f"{avg_attempts:.2f}",
        "num_hallucinated": num_hallucinated,
        "num_total_numbers": num_total_numbers,
        "hallucination_rate": f"{hallucination_rate:.4f}",
        "value_precision": f"{ml.value_precision:.4f}",
        "value_recall": f"{ml.value_recall:.4f}",
        "value_f1": f"{ml.value_f1:.4f}",
        "measurement_precision": f"{ml.measurement_precision:.4f}",
        "measurement_recall": f"{ml.measurement_recall:.4f}",
        "measurement_f1": f"{ml.measurement_f1:.4f}",
        "config_precision": f"{ml.config_precision:.4f}",
        "config_recall": f"{ml.config_recall:.4f}",
        "config_f1": f"{ml.config_f1:.4f}",
        "process_precision": f"{ml.process_precision:.4f}",
        "process_recall": f"{ml.process_recall:.4f}",
        "process_f1": f"{ml.process_f1:.4f}",
        "material_precision": f"{ml.material_precision:.4f}",
        "material_recall": f"{ml.material_recall:.4f}",
        "material_f1": f"{ml.material_f1:.4f}",
    }


def avg_process_edit_distance(result: ExperimentComparisonResult) -> float:
    """Average process edit distance across matched materials, or 0.0 if none."""
    if not result.matched_materials:
        return 0.0
    return sum(m.process_edit_distance for m in result.matched_materials) / len(result.matched_materials)


class HasArtifacts(Protocol):
    prompt_text: str
    raw_response: str


def write_extraction_artifacts(
    output_dir: Path,
    extraction_outputs: dict[str, HasArtifacts],
) -> None:
    """Write prompt and raw response .txt files for each DOI."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for doi, output in extraction_outputs.items():
        safe_doi = sanitize_doi(doi)
        (output_dir / f"{safe_doi}.prompt.txt").write_text(output.prompt_text)
        (output_dir / f"{safe_doi}.response.txt").write_text(output.raw_response)


def write_run_meta(
    output_dir: Path,
    extraction_outputs: dict[str, ExtractionOutput],
) -> None:
    """Save per-DOI token counts and costs so they survive re-evaluation."""
    meta: dict[str, dict[str, Any]] = {}
    for doi, eo in extraction_outputs.items():
        meta[doi] = {
            "input_tokens": eo.input_tokens,
            "output_tokens": eo.output_tokens,
            "cost_usd": eo.cost_usd,
            "attempts": eo.attempts,
            "context_resets": eo.context_resets,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_meta.json").write_text(
        json.dumps(meta, indent=2) + "\n",
        encoding="utf-8",
    )


def load_run_meta(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Load per-DOI metadata saved by write_run_meta, or empty dict."""
    meta_path = run_dir / "run_meta.json"
    if not meta_path.is_file():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def _write_results_csv(
    output_path: Path,
    dois: list[str],
    all_model_results: dict[str, dict[str, ExperimentComparisonResult]],
    all_extraction_outputs: dict[str, dict[str, ExtractionOutput]],
    model_elapsed: dict[str, float] | None = None,
) -> None:
    """Write a combined results CSV with summary metrics for all models.

    One row per DOI per model, plus an OVERALL row per model.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict[str, str | int | float]] = []

    for model_name, results in all_model_results.items():
        all_matched_items = 0.0
        all_target_items = 0
        all_extracted_items = 0
        all_matched_materials = 0
        all_target_materials = 0
        all_extracted_materials = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_cost_usd = 0.0
        all_ped_values: list[float] = []

        extraction_outputs = all_extraction_outputs.get(model_name, {})

        doi_attempts_list: list[int] = []
        agg_hallucinated = 0
        agg_total_numbers = 0

        for doi in dois:
            r = results[doi]
            eo = extraction_outputs.get(doi)
            ped = avg_process_edit_distance(r)
            in_tok = eo.input_tokens if eo else 0
            out_tok = eo.output_tokens if eo else 0
            cost = eo.cost_usd if eo else 0.0
            doi_att = eo.attempts if eo else 1
            ml = compute_multi_level_metrics(r)
            h = count_hallucinations(
                eo.experiments if eo else [],
                eo.prompt_text if eo else "",
            )

            row = _format_metrics_row(
                num_target_items=r.num_total_target_items,
                num_extracted_items=r.num_total_extracted_items,
                num_matched_items=r.num_matched_items,
                num_target_materials=r.num_target_materials,
                num_extracted_materials=r.num_extracted_materials,
                num_matched_materials=r.num_matched_materials,
                avg_ped=ped,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cost_usd=cost,
                avg_attempts=float(doi_att),
                ml=ml,
                num_hallucinated=h.numbers_not_found,
                num_total_numbers=h.total_numbers,
                hallucination_rate=h.hallucination_rate,
            )
            row["model_name"] = model_name
            row["doi"] = doi
            all_rows.append(row)
            all_matched_items += r.num_matched_items
            all_target_items += r.num_total_target_items
            all_extracted_items += r.num_total_extracted_items
            all_matched_materials += r.num_matched_materials
            all_target_materials += r.num_target_materials
            all_extracted_materials += r.num_extracted_materials
            total_input_tokens += in_tok
            total_output_tokens += out_tok
            total_cost_usd += cost
            doi_attempts_list.append(doi_att)
            agg_hallucinated += h.numbers_not_found
            agg_total_numbers += h.total_numbers
            if r.matched_materials:
                all_ped_values.extend(m.process_edit_distance for m in r.matched_materials)

        overall_ped = sum(all_ped_values) / len(all_ped_values) if all_ped_values else 0.0
        csv_avg_attempts = sum(doi_attempts_list) / len(doi_attempts_list) if doi_attempts_list else 0.0
        elapsed = (model_elapsed or {}).get(model_name, 0.0)
        overall_ml = _aggregate_multi_level_metrics(results)
        overall_hallucination_rate = agg_hallucinated / agg_total_numbers if agg_total_numbers else 0.0
        overall_row = _format_metrics_row(
            num_target_items=all_target_items,
            num_extracted_items=all_extracted_items,
            num_matched_items=all_matched_items,
            num_target_materials=all_target_materials,
            num_extracted_materials=all_extracted_materials,
            num_matched_materials=all_matched_materials,
            avg_ped=overall_ped,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=total_cost_usd,
            avg_attempts=csv_avg_attempts,
            ml=overall_ml,
            num_hallucinated=agg_hallucinated,
            num_total_numbers=agg_total_numbers,
            hallucination_rate=overall_hallucination_rate,
        )
        per_paper_times = [
            extraction_outputs[doi].elapsed_seconds
            for doi in dois
            if doi in extraction_outputs and extraction_outputs[doi].elapsed_seconds > 0
        ]
        avg_paper_time = sum(per_paper_times) / len(per_paper_times) if per_paper_times else 0.0
        max_paper_time = max(per_paper_times) if per_paper_times else 0.0
        overall_row["model_name"] = model_name
        overall_row["doi"] = "OVERALL"
        overall_row["elapsed_seconds"] = f"{elapsed:.1f}"
        overall_row["avg_paper_time"] = f"{avg_paper_time:.1f}"
        overall_row["max_paper_time"] = f"{max_paper_time:.1f}"
        all_rows.append(overall_row)

    if all_rows:
        fieldnames = [
            "model_name",
            "doi",
            "overall_precision",
            "overall_recall",
            "overall_f1",
            "num_target_items",
            "num_extracted_items",
            "num_matched_items",
            "num_target_materials",
            "num_extracted_materials",
            "num_matched_materials",
            "avg_process_edit_distance",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "elapsed_seconds",
            "avg_paper_time",
            "max_paper_time",
            "avg_attempts",
            "num_hallucinated",
            "num_total_numbers",
            "hallucination_rate",
            "value_precision",
            "value_recall",
            "value_f1",
            "measurement_precision",
            "measurement_recall",
            "measurement_f1",
            "config_precision",
            "config_recall",
            "config_f1",
            "process_precision",
            "process_recall",
            "process_f1",
            "material_precision",
            "material_recall",
            "material_f1",
        ]
        assert set(fieldnames) == set(all_rows[-1].keys()), (
            f"CSV key mismatch: list has {set(fieldnames) - set(all_rows[-1].keys())} extra, "
            f"dict has {set(all_rows[-1].keys()) - set(fieldnames)} extra"
        )
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_rows)


def _aggregate_multi_level_metrics(
    doi_results: dict[str, ExperimentComparisonResult],
) -> MultiLevelMetrics:
    """Aggregate multi-level metrics across all DOIs."""
    val_tp = 0.0
    val_target = 0
    val_extracted = 0
    meas_tp = 0.0
    meas_target = 0
    meas_extracted = 0
    conf_tp = 0.0
    conf_target = 0
    conf_extracted = 0
    proc_tp = 0
    proc_target = 0
    proc_extracted = 0
    mat_tp = 0
    mat_target = 0
    mat_extracted = 0

    for result in doi_results.values():
        ml = compute_multi_level_metrics(result)
        val_tp += ml.value_tp
        val_target += ml.value_target
        val_extracted += ml.value_extracted
        meas_tp += ml.measurement_tp
        meas_target += ml.measurement_target
        meas_extracted += ml.measurement_extracted
        conf_tp += ml.config_tp
        conf_target += ml.config_target
        conf_extracted += ml.config_extracted
        proc_tp += ml.process_tp
        proc_target += ml.process_target
        proc_extracted += ml.process_extracted
        mat_tp += ml.material_tp
        mat_target += ml.material_target
        mat_extracted += ml.material_extracted

    return MultiLevelMetrics(
        value_tp=val_tp,
        value_target=val_target,
        value_extracted=val_extracted,
        measurement_tp=meas_tp,
        measurement_target=meas_target,
        measurement_extracted=meas_extracted,
        config_tp=conf_tp,
        config_target=conf_target,
        config_extracted=conf_extracted,
        process_tp=proc_tp,
        process_target=proc_target,
        process_extracted=proc_extracted,
        material_tp=mat_tp,
        material_target=mat_target,
        material_extracted=mat_extracted,
    )


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------


def _evaluate_and_report(
    model_name: str,
    dois: list[str],
    ground_truth: dict[str, list[Experiment]],
    extraction_outputs: dict[str, ExtractionOutput],
    output_dir: Path,
    elapsed_seconds: float = 0.0,
) -> tuple[dict[str, ExperimentComparisonResult], dict[str, str | int | float]]:
    """Run comparison, print per-DOI and overall metrics, save artifacts.

    Returns ``(doi_results, sheets_row_dict)`` where *sheets_row_dict* is a
    flat dict suitable for CSV / Google-Sheets output.
    """
    print(f"\n[{model_name}]")

    all_matched_items = 0.0
    all_target_items = 0
    all_extracted_items = 0
    all_matched_materials = 0
    all_target_materials = 0
    all_extracted_materials = 0
    all_input_tokens = 0
    all_output_tokens = 0
    all_cost_usd = 0.0
    all_attempts: list[int] = []
    all_proc_edit_distances: list[float] = []
    all_hallucinated = 0
    all_total_numbers = 0
    doi_results: dict[str, ExperimentComparisonResult] = {}

    for doi in dois:
        target_experiments = ground_truth[doi]
        extraction_output = extraction_outputs.get(doi)
        extracted_experiments = extraction_output.experiments if extraction_output else []
        result = compare_experiments(target_experiments, extracted_experiments)
        doi_results[doi] = result

        # ped = avg_process_edit_distance(result)
        doi_in_tok = extraction_output.input_tokens if extraction_output else 0
        doi_out_tok = extraction_output.output_tokens if extraction_output else 0
        doi_cost = extraction_output.cost_usd if extraction_output else 0.0
        doi_attempts = extraction_output.attempts if extraction_output else 0
        doi_elapsed = extraction_output.elapsed_seconds if extraction_output else 0.0
        ml = compute_multi_level_metrics(result)
        h = count_hallucinations(
            extracted_experiments,
            extraction_output.prompt_text if extraction_output else "",
        )
        print(
            f"  {doi:<40s}  "
            f"P={ml.overall_precision:.0%}  R={ml.overall_recall:.0%}  F1={ml.overall_f1:.0%}  "
            f"val={ml.value_f1:.0%}  meas={ml.measurement_f1:.0%}  "
            f"conf={ml.config_f1:.0%}  proc={ml.process_f1:.0%}  mat={ml.material_f1:.0%}  "
            f"halluc={h.hallucination_rate:.0%}({h.numbers_not_found}/{h.total_numbers})  "
            f"tokens={doi_in_tok}+{doi_out_tok}  ${doi_cost:.4f}  attempts={doi_attempts}  time={doi_elapsed:.1f}s"
        )
        print_one_call_diff_view(result, label=doi)

        all_matched_items += result.num_matched_items
        all_target_items += result.num_total_target_items
        all_extracted_items += result.num_total_extracted_items
        all_matched_materials += result.num_matched_materials
        all_target_materials += result.num_target_materials
        all_extracted_materials += result.num_extracted_materials
        all_input_tokens += doi_in_tok
        all_output_tokens += doi_out_tok
        all_cost_usd += doi_cost
        all_attempts.append(doi_attempts)
        all_hallucinated += h.numbers_not_found
        all_total_numbers += h.total_numbers
        if result.matched_materials:
            all_proc_edit_distances.extend(m.process_edit_distance for m in result.matched_materials)

    overall_ped = sum(all_proc_edit_distances) / len(all_proc_edit_distances) if all_proc_edit_distances else 0.0
    overall_ml = _aggregate_multi_level_metrics(doi_results)
    avg_attempts = sum(all_attempts) / len(all_attempts) if all_attempts else 0.0
    overall_hallucination_rate = all_hallucinated / all_total_numbers if all_total_numbers else 0.0
    per_paper_times = [
        extraction_outputs[doi].elapsed_seconds
        for doi in dois
        if doi in extraction_outputs and extraction_outputs[doi].elapsed_seconds > 0
    ]
    avg_paper_time = sum(per_paper_times) / len(per_paper_times) if per_paper_times else 0.0
    max_paper_time = max(per_paper_times) if per_paper_times else 0.0
    print(
        f"  {'OVERALL':<40s}  "
        f"P={overall_ml.overall_precision:.0%}  R={overall_ml.overall_recall:.0%}  F1={overall_ml.overall_f1:.0%}  "
        f"val={overall_ml.value_f1:.0%}  meas={overall_ml.measurement_f1:.0%}  "
        f"conf={overall_ml.config_f1:.0%}  proc={overall_ml.process_f1:.0%}  mat={overall_ml.material_f1:.0%}  "
        f"halluc={overall_hallucination_rate:.0%}({all_hallucinated}/{all_total_numbers})  "
        f"tokens={all_input_tokens}+{all_output_tokens}  ${all_cost_usd:.4f}  avg_attempts={avg_attempts:.1f}  "
        f"avg_time={avg_paper_time:.1f}s  max_time={max_paper_time:.1f}s"
    )

    # Save eval metrics JSON
    save_eval_metrics(doi_results, output_dir / "eval_metrics.json", extraction_outputs)

    # Save per-DOI token/cost metadata for re-evaluation
    write_run_meta(output_dir, extraction_outputs)

    # Save prompts and raw responses for debugging
    write_extraction_artifacts(output_dir, extraction_outputs)

    sheets_row = _format_metrics_row(
        num_target_items=all_target_items,
        num_extracted_items=all_extracted_items,
        num_matched_items=all_matched_items,
        num_target_materials=all_target_materials,
        num_extracted_materials=all_extracted_materials,
        num_matched_materials=all_matched_materials,
        avg_ped=overall_ped,
        input_tokens=all_input_tokens,
        output_tokens=all_output_tokens,
        cost_usd=all_cost_usd,
        avg_attempts=avg_attempts,
        ml=overall_ml,
        num_hallucinated=all_hallucinated,
        num_total_numbers=all_total_numbers,
        hallucination_rate=overall_hallucination_rate,
    )
    sheets_row["model_name"] = model_name
    sheets_row["elapsed_seconds"] = f"{elapsed_seconds:.1f}"
    sheets_row["avg_paper_time"] = f"{avg_paper_time:.1f}"
    sheets_row["max_paper_time"] = f"{max_paper_time:.1f}"

    # Save summary CSV
    save_summary_csv([sheets_row], output_dir / "summary.csv")
    print(f"  -> {output_dir}/ (prompts, responses & summary)")

    return doi_results, sheets_row


# ---------------------------------------------------------------------------
# Eval Metrics Collection & Saving
# ---------------------------------------------------------------------------


def _normalized_composition(material: Material) -> str | None:
    """Extract the normalized composition string from a material, or None if absent."""
    for measurement in material.measurements:
        if isinstance(measurement, CompMeasurement):
            return measurement.composition.fractional_composition.alphabetical_formula
    return None


def _composition_matches(match: MaterialMatchResult) -> bool:
    """Check if the compositions of a matched material pair are identical."""
    target_comp = _normalized_composition(match.target)
    extracted_comp = _normalized_composition(match.extracted)
    if target_comp is None and extracted_comp is None:
        return True
    if target_comp is None or extracted_comp is None:
        return False
    return target_comp == extracted_comp


def _material_match_metrics(match: MaterialMatchResult) -> dict[str, Any]:
    """Collect metrics for a single matched material pair."""
    metrics: dict[str, Any] = {
        "cost": match.cost,
        "process_edit_distance": match.process_edit_distance,
        "measurement_matches": match.measurement_result.match_score,
        "measurement_total": match.measurement_result.total,
        "composition_correct": _composition_matches(match),
    }
    if match.process_alignment is not None:
        pa = match.process_alignment
        metrics["process_matched"] = len(pa.matched_pairs)
        metrics["process_target"] = len(pa.matched_pairs) + len(pa.unmatched_target)
        metrics["process_extracted"] = len(pa.matched_pairs) + len(pa.unmatched_extracted)
    return metrics


def _multi_level_to_dict(ml: MultiLevelMetrics) -> dict[str, Any]:
    """Serialize a MultiLevelMetrics to a dict."""
    return {
        "value": {
            "tp": ml.value_tp,
            "target": ml.value_target,
            "extracted": ml.value_extracted,
            "precision": ml.value_precision,
            "recall": ml.value_recall,
            "f1": ml.value_f1,
        },
        "measurement": {
            "tp": ml.measurement_tp,
            "target": ml.measurement_target,
            "extracted": ml.measurement_extracted,
            "precision": ml.measurement_precision,
            "recall": ml.measurement_recall,
            "f1": ml.measurement_f1,
        },
        "configuration": {
            "tp": ml.config_tp,
            "target": ml.config_target,
            "extracted": ml.config_extracted,
            "precision": ml.config_precision,
            "recall": ml.config_recall,
            "f1": ml.config_f1,
        },
        "process": {
            "tp": ml.process_tp,
            "target": ml.process_target,
            "extracted": ml.process_extracted,
            "precision": ml.process_precision,
            "recall": ml.process_recall,
            "f1": ml.process_f1,
        },
        "material": {
            "tp": ml.material_tp,
            "target": ml.material_target,
            "extracted": ml.material_extracted,
            "precision": ml.material_precision,
            "recall": ml.material_recall,
            "f1": ml.material_f1,
        },
        "overall": {
            "precision": ml.overall_precision,
            "recall": ml.overall_recall,
            "f1": ml.overall_f1,
        },
    }


def _doi_metrics(result: ExperimentComparisonResult) -> dict[str, Any]:
    """Collect all metrics for a single DOI comparison result."""
    per_material = [_material_match_metrics(m) for m in result.matched_materials]
    num_compositions_correct = sum(1 for m in per_material if m["composition_correct"])
    num_matched = len(result.matched_materials)

    process_edit_distances = [m["process_edit_distance"] for m in per_material]
    avg_process_edit_distance = (
        sum(process_edit_distances) / len(process_edit_distances) if process_edit_distances else 0.0
    )

    ml = compute_multi_level_metrics(result)

    return {
        "num_target_materials": result.num_target_materials,
        "num_extracted_materials": result.num_extracted_materials,
        "num_matched_materials": num_matched,
        "num_unmatched_target": len(result.unmatched_target_materials),
        "num_unmatched_extracted": len(result.unmatched_extracted_materials),
        "total_cost": result.total_cost,
        # Measurement-level (comparable-item) metrics
        "num_matched_items": result.num_matched_items,
        "num_target_items": result.num_total_target_items,
        "num_extracted_items": result.num_total_extracted_items,
        "precision": result.precision,
        "recall": result.recall,
        "f1": result.f1,
        "num_compositions_correct": num_compositions_correct,
        "num_compositions_total": num_matched,
        "avg_process_edit_distance": avg_process_edit_distance,
        "multi_level": _multi_level_to_dict(ml),
        "per_material": per_material,
    }


def collect_eval_metrics(
    doi_results: dict[str, ExperimentComparisonResult],
    extraction_outputs: dict[str, ExtractionOutput] | None = None,
) -> dict[str, Any]:
    """Collect all evaluation metrics across DOIs into a serialisable dict.

    Returns a dict with ``per_doi`` results and ``aggregate`` totals suitable
    for writing to a JSON config file at the end of a run.
    """
    per_doi: dict[str, dict[str, Any]] = {}
    for doi, result in doi_results.items():
        per_doi[doi] = _doi_metrics(result)
        # Hallucination metrics (requires extraction output with prompt text)
        if extraction_outputs is not None:
            eo = extraction_outputs.get(doi)
            if eo is not None:
                h = count_hallucinations(eo.experiments, eo.prompt_text)
                per_doi[doi]["hallucination"] = {
                    "num_hallucinated": h.numbers_not_found,
                    "num_total_numbers": h.total_numbers,
                    "hallucination_rate": h.hallucination_rate,
                }

    # Aggregate across DOIs
    all_per_material: list[dict[str, Any]] = []
    for doi_data in per_doi.values():
        all_per_material.extend(doi_data["per_material"])

    num_dois = len(per_doi)
    total_target = sum(d["num_target_materials"] for d in per_doi.values())
    total_extracted = sum(d["num_extracted_materials"] for d in per_doi.values())
    total_matched = sum(d["num_matched_materials"] for d in per_doi.values())
    total_unmatched_target = sum(d["num_unmatched_target"] for d in per_doi.values())
    total_unmatched_extracted = sum(d["num_unmatched_extracted"] for d in per_doi.values())
    total_cost = sum(d["total_cost"] for d in per_doi.values())

    total_compositions_correct = sum(d["num_compositions_correct"] for d in per_doi.values())
    total_compositions_total = sum(d["num_compositions_total"] for d in per_doi.values())

    total_measurement_matches = sum(m["measurement_matches"] for m in all_per_material)
    total_measurements = sum(m["measurement_total"] for m in all_per_material)

    all_process_edit_distances = [m["process_edit_distance"] for m in all_per_material]
    avg_process_edit_distance = (
        sum(all_process_edit_distances) / len(all_process_edit_distances) if all_process_edit_distances else 0.0
    )

    precisions = [d["precision"] for d in per_doi.values()]
    recalls = [d["recall"] for d in per_doi.values()]
    f1s = [d["f1"] for d in per_doi.values()]

    total_matched_items = sum(d.get("num_matched_items", 0) for d in per_doi.values())
    total_target_items = sum(d.get("num_target_items", 0) for d in per_doi.values())
    total_extracted_items = sum(d.get("num_extracted_items", 0) for d in per_doi.values())

    micro_precision = total_matched_items / total_extracted_items if total_extracted_items else 0.0
    micro_recall = total_matched_items / total_target_items if total_target_items else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if (micro_precision + micro_recall)
        else 0.0
    )

    # Aggregate multi-level metrics across all DOIs
    agg_ml = _aggregate_multi_level_metrics(doi_results)

    # Aggregate hallucination across DOIs
    agg_hallucinated = sum(d.get("hallucination", {}).get("num_hallucinated", 0) for d in per_doi.values())
    agg_total_numbers = sum(d.get("hallucination", {}).get("num_total_numbers", 0) for d in per_doi.values())
    agg_hallucination_rate = agg_hallucinated / agg_total_numbers if agg_total_numbers else 0.0

    aggregate: dict[str, Any] = {
        "num_dois": num_dois,
        "total_target_materials": total_target,
        "total_extracted_materials": total_extracted,
        "total_matched_materials": total_matched,
        "total_unmatched_target": total_unmatched_target,
        "total_unmatched_extracted": total_unmatched_extracted,
        "total_cost": total_cost,
        # Measurement-level (comparable-item) aggregates
        "total_matched_items": total_matched_items,
        "total_target_items": total_target_items,
        "total_extracted_items": total_extracted_items,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "avg_precision": sum(precisions) / num_dois if num_dois else 0.0,
        "avg_recall": sum(recalls) / num_dois if num_dois else 0.0,
        "avg_f1": sum(f1s) / num_dois if num_dois else 0.0,
        "num_compositions_correct": total_compositions_correct,
        "num_compositions_total": total_compositions_total,
        "avg_process_edit_distance": avg_process_edit_distance,
        "total_measurement_matches": total_measurement_matches,
        "total_measurements": total_measurements,
        "multi_level": _multi_level_to_dict(agg_ml),
        "hallucination": {
            "num_hallucinated": agg_hallucinated,
            "num_total_numbers": agg_total_numbers,
            "hallucination_rate": agg_hallucination_rate,
        },
    }

    return {
        "eval_timestamp": datetime.now().isoformat(),
        "per_doi": per_doi,
        "aggregate": aggregate,
    }


SUMMARY_CSV_KEYS = [
    "model_name",
    "overall_precision",
    "overall_recall",
    "overall_f1",
    "num_target_items",
    "num_extracted_items",
    "num_matched_items",
    "num_target_materials",
    "num_extracted_materials",
    "num_matched_materials",
    "avg_process_edit_distance",
    "input_tokens",
    "output_tokens",
    "cost_usd",
    "elapsed_seconds",
    "avg_paper_time",
    "max_paper_time",
    "avg_attempts",
    "num_hallucinated",
    "num_total_numbers",
    "hallucination_rate",
    "value_precision",
    "value_recall",
    "value_f1",
    "measurement_precision",
    "measurement_recall",
    "measurement_f1",
    "config_precision",
    "config_recall",
    "config_f1",
    "process_precision",
    "process_recall",
    "process_f1",
    "material_precision",
    "material_recall",
    "material_f1",
]


def _print_summary_csv(
    sheets_rows: list[dict[str, str | int | float]],
    keys: list[str] | None = None,
) -> None:
    """Print comma-separated summary rows for Google Sheets."""
    from litxbench.core.utils import dict_to_csv_string

    if not sheets_rows:
        return
    cols = keys or SUMMARY_CSV_KEYS
    assert set(cols) == set(sheets_rows[0].keys()), (
        f"CSV key mismatch: list has {set(cols) - set(sheets_rows[0].keys())} extra, "
        f"dict has {set(sheets_rows[0].keys()) - set(cols)} extra"
    )
    print(f"\n{'=' * 60}")
    print(",".join(cols))
    for row in sheets_rows:
        print(dict_to_csv_string(row, cols))


def save_summary_csv(
    sheets_rows: list[dict[str, str | int | float]],
    output_path: Path,
    keys: list[str] | None = None,
) -> None:
    """Write comma-separated summary rows to a file."""
    from litxbench.core.utils import dict_to_csv_string

    if not sheets_rows:
        return
    cols = keys or SUMMARY_CSV_KEYS
    assert set(cols) == set(sheets_rows[0].keys()), (
        f"CSV key mismatch: list has {set(cols) - set(sheets_rows[0].keys())} extra, "
        f"dict has {set(sheets_rows[0].keys()) - set(cols)} extra"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [",".join(cols)]
    for row in sheets_rows:
        lines.append(dict_to_csv_string(row, cols))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate_all_and_summarize(
    model_names: list[str],
    dois: list[str],
    ground_truth: dict[str, list["Experiment"]],
    all_extraction_outputs: dict[str, dict[str, ExtractionOutput]],
    model_output_dirs: dict[str, Path],
    model_elapsed: dict[str, float],
    results_csv_path: Path,
) -> None:
    """Evaluate all models, write combined CSV, and print summary.

    This is the shared post-extraction reporting logic used by both
    ``zero_shot.py`` and ``zero_shot_agentic_cli.py``.
    """
    all_model_results: dict[str, dict[str, ExperimentComparisonResult]] = {}
    sheets_rows: list[dict[str, str | int | float]] = []

    for name in model_names:
        if name not in all_extraction_outputs:
            continue
        extraction_outputs = all_extraction_outputs[name]
        output_dir = model_output_dirs[name]

        elapsed = model_elapsed.get(name, 0.0)
        doi_results, sheets_row = _evaluate_and_report(
            model_name=name,
            dois=dois,
            ground_truth=ground_truth,
            extraction_outputs=extraction_outputs,
            output_dir=output_dir,
            elapsed_seconds=elapsed,
        )
        per_paper_times = [
            extraction_outputs[doi].elapsed_seconds
            for doi in dois
            if doi in extraction_outputs and extraction_outputs[doi].elapsed_seconds > 0
        ]
        avg_paper_time = sum(per_paper_times) / len(per_paper_times) if per_paper_times else 0.0
        max_paper_time = max(per_paper_times) if per_paper_times else 0.0
        print(f"  [{name}] elapsed={elapsed:.1f}s  avg_paper={avg_paper_time:.1f}s  max_paper={max_paper_time:.1f}s")

        all_model_results[name] = doi_results
        sheets_rows.append(sheets_row)

    _write_results_csv(results_csv_path, dois, all_model_results, all_extraction_outputs, model_elapsed)
    print(f"\n  -> {results_csv_path}")

    _print_summary_csv(sheets_rows)


def save_eval_metrics(
    doi_results: dict[str, ExperimentComparisonResult],
    output_path: Path,
    extraction_outputs: dict[str, ExtractionOutput] | None = None,
) -> Path:
    """Collect and save eval metrics to a JSON file.

    Returns the path the file was written to.
    """
    metrics = collect_eval_metrics(doi_results, extraction_outputs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(f"\nEval metrics saved to {output_path}")
    return output_path
