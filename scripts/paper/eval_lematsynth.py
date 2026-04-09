"""Evaluate lematerial-llm-synthesis extraction results against ground truth.

Synthesis-only evaluation: matches lematerial materials to ground truth materials
by composition + process chain, then measures how well lematerial identifies
the correct synthesis conditions (process kinds, temperatures, durations)
for each composition it finds.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from pymatgen.core.composition import Composition
from scipy.optimize import linear_sum_assignment

from litxbench.core.enums import CASTING_KINDS, MELTING_KINDS, ProcessKind, RawMaterialKind
from litxbench.core.eval import (
    MaterialWithContext,
    ProcessEventAlignmentResult,
    _collect_materials,
    align_process_events,
    alignment_kind_metrics,
    normalize_kind,
    process_event_edit_distance,
    resolve_process_events,
)
from litxbench.core.formula_cleaning import LATEX_SUB_RE, UNICODE_SUBSCRIPTS
from litxbench.core.models import (
    CompMeasurement,
    Experiment,
    Material,
    ProcessEvent,
    Quantity,
    RawMaterial,
)
from litxbench.core.units import Celsius, Hour, Kelvin, Minute, Second, ureg
from litxbench.litxalloy import papers

# ---------------------------------------------------------------------------
# Path to lematerial results
# ---------------------------------------------------------------------------

# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-02-28/10-51-14/results"  # gpt4o
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home()
#     / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-02-28/23-05-35/results"  # gemini-3.1-pro-preview
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-02-28/23-51-19/results"  # gpt5.2-high
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-03-01/14-01-06/results"  # opus 4.6
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-04-02/17-25-39/results"  # opus 4.6
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/2026-04-02/17-25-03/results"  # opus 4.6
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/opus_4.6_run_1/results"  # opus 4.6
# )
# LEMATERIAL_RESULTS_DIR = (
#     Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/opus_4.6_run_2/results"  # opus 4.6
# )
LEMATERIAL_RESULTS_DIR = (
    Path.home() / "Documents/dev/lematerial-llm-synthesis/results/single_run/opus_4.6_run_3/results"  # opus 4.6
)


def clean_material_name(name: str) -> str | None:
    """Clean a material name string so pymatgen Composition can parse it.

    Returns None if the name is fundamentally unparseable (e.g. Greek letters,
    trade names).
    """
    # Strip LaTeX subscript braces: Al_{65} -> Al65
    name = LATEX_SUB_RE.sub(r"\1", name)
    # Remove any remaining stray braces or underscores from LaTeX
    name = name.replace("{", "").replace("}", "").replace("_", "")

    # Convert unicode subscript digits
    name = name.translate(UNICODE_SUBSCRIPTS)

    # Quick reject for names that can never be a chemical formula
    skip_patterns = {"σ", "No materials", "DPHL", "Inconel", "phase"}
    for pat in skip_patterns:
        if pat in name:
            return None

    # Strip trailing parenthetical like (WC)
    name = re.sub(r"\(.*?\)$", "", name).strip()

    if not name:
        return None

    return name


def try_parse_composition(name: str) -> Composition | None:
    """Attempt to parse a cleaned material name into a Composition."""
    cleaned = clean_material_name(name)
    if cleaned is None:
        return None
    try:
        return Composition(cleaned)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Action -> ProcessKind mapping
# ---------------------------------------------------------------------------

# Actions to skip entirely (not separate process steps)
_SKIP_ACTIONS = {"add", "flip", "remelt", "stack"}

# Unit maps
_TEMP_UNIT_MAP = {"C": Celsius, "°C": Celsius, "K": Kelvin}
_TIME_UNIT_MAP = {"h": Hour, "min": Minute, "minutes": Minute, "s": Second}


def _is_induction(step: dict) -> bool:
    """Check whether a step's equipment or description suggests induction melting."""
    desc = (step.get("description") or "").lower()
    if "induction" in desc:
        return True
    for eq in step.get("equipment") or []:
        if "induction" in (eq.get("name") or "").lower():
            return True
    return False


def _casting_kind_from_desc(desc: str) -> ProcessKind:
    """Determine casting sub-kind from step description."""
    desc_lower = desc.lower()
    if "suction" in desc_lower:
        return ProcessKind.SuctionCasting
    if "drop" in desc_lower:
        return ProcessKind.DropCasting
    if "gravity" in desc_lower:
        return ProcessKind.GravityCasting
    return ProcessKind.AsCast


def map_action_to_process_kind(step: dict) -> ProcessKind | None:
    """Map a lematerial action string to a ProcessKind enum value.

    Returns None for actions that should be skipped.
    """
    action = step.get("action", "").lower().strip()
    desc = (step.get("description") or "").lower()

    if action in _SKIP_ACTIONS:
        return None

    if action == "arc melt":
        return ProcessKind.ArcMelting

    if action == "melt":
        if _is_induction(step):
            return ProcessKind.InductionMelting
        # Check description for arc
        if "arc" in desc:
            return ProcessKind.ArcMelting
        return ProcessKind.ArcMelting  # default

    if action == "cast":
        return _casting_kind_from_desc(step.get("description") or "")

    if action == "anneal":
        return ProcessKind.Annealing

    if action == "homogenize":
        return ProcessKind.Homogenization

    if action in ("ball milling", "mill"):
        return ProcessKind.MechanicalAlloying

    if action == "mix":
        return ProcessKind.Mixing

    if action == "hot roll":
        return ProcessKind.HotRolling

    if action == "roll":
        return ProcessKind.ColdRolling

    if action == "extrude":
        return ProcessKind.HotExtrusion

    if action == "forge":
        return ProcessKind.ColdForging

    if action in ("quench", "cool"):
        return ProcessKind.WaterQuenching

    if action in ("spark plasma sintering", "sinter"):
        return ProcessKind.SparkPlasmaSintering

    if action == "compress":
        return ProcessKind.Press

    if action == "consolidate":
        # Check description for sintering hints
        if "sinter" in desc or "sps" in desc:
            return ProcessKind.HotPressingSintering
        return ProcessKind.HotPressingSintering

    if action == "atomize":
        return ProcessKind.GasAtomization

    if action == "friction stir process":
        return ProcessKind.FrictionStirProcessing

    if action == "machine":
        return ProcessKind.ElectricalDischargeMachining

    if action == "grind":
        return ProcessKind.Grinding

    if action == "clean":
        return ProcessKind.UltrasonicBath

    if action == "heat":
        # "heat" is a generic action in lematerial; inspect description/equipment
        # to determine the actual process kind.
        equip_names = " ".join((eq.get("name") or "").lower() for eq in (step.get("equipment") or []))
        all_text = desc + " " + equip_names
        if "arc" in all_text:
            return ProcessKind.ArcMelting
        if "induction" in all_text:
            return ProcessKind.InductionMelting
        if "melt" in all_text:
            return ProcessKind.ArcMelting  # default for unspecified melting
        if "sinter" in all_text or "sps" in all_text:
            if "hot press" in all_text:
                return ProcessKind.HotPressingSintering
            return ProcessKind.SparkPlasmaSintering
        if "roll" in all_text:
            if "cold" in all_text:
                return ProcessKind.ColdRolling
            return ProcessKind.HotRolling
        if "bridgman" in all_text or "directional" in all_text:
            return ProcessKind.DirectionalSolidification
        if "homogeniz" in all_text:
            return ProcessKind.Homogenization
        if "extru" in all_text:
            return ProcessKind.HotExtrusion
        return ProcessKind.Annealing

    if action == "pour":
        return ProcessKind.GravityCasting

    if action == "solidify":
        return ProcessKind.AsCast

    # Unknown action — skip
    print(f"  WARNING: unknown action '{action}', skipping")
    return None


# ---------------------------------------------------------------------------
# Conditions -> Quantity helpers
# ---------------------------------------------------------------------------


def _parse_temperature(conditions: dict) -> Quantity | None:
    temp = conditions.get("temperature")
    temp_unit_str = conditions.get("temp_unit")
    if temp is None or temp_unit_str is None:
        return None
    unit = _TEMP_UNIT_MAP.get(temp_unit_str)
    if unit is None:
        return None
    return Quantity(value=temp, unit=unit)


def _parse_duration(conditions: dict) -> Quantity | None:
    dur = conditions.get("duration")
    time_unit_str = conditions.get("time_unit")
    if dur is None or time_unit_str is None:
        return None
    unit = _TIME_UNIT_MAP.get(time_unit_str)
    if unit is None:
        return None
    return Quantity(value=dur, unit=unit)


# ---------------------------------------------------------------------------
# Convert a single lematerial entry to an Experiment
# ---------------------------------------------------------------------------


def _build_purity_description(entry: dict) -> str | None:
    """Build a purity description from starting materials."""
    purities = []
    for mat in entry.get("synthesis", {}).get("starting_materials", []):
        p = mat.get("purity")
        if p:
            purities.append(f"{mat.get('name', '?')}: {p}")
    return "; ".join(purities) if purities else None


def convert_entry_to_experiment(entry: dict) -> Experiment | None:
    """Convert a single lematerial result entry to an Experiment.

    Returns None if the material cannot be parsed.
    """
    composition = try_parse_composition(entry["material"])
    if composition is None:
        print(f"  Skipping unparseable material: {entry['material']!r}")
        return None

    # Build process events from synthesis steps
    raw_events: list[ProcessEvent] = []
    for step in entry.get("synthesis", {}).get("steps", []):
        kind = map_action_to_process_kind(step)
        if kind is None:
            continue

        conditions = step.get("conditions") or {}
        temperature = _parse_temperature(conditions)
        duration = _parse_duration(conditions)

        equipment_names = [eq.get("name", "") for eq in (step.get("equipment") or []) if eq.get("name")]
        equipment_str = "; ".join(equipment_names) if equipment_names else None

        raw_events.append(
            ProcessEvent(
                kind=kind,
                description=step.get("description"),
                temperature=temperature,
                duration=duration,
                equipment=equipment_str,
            )
        )

    # Enforce melting-followed-by-casting rule
    process_events: list[ProcessEvent] = []
    for i, event in enumerate(raw_events):
        process_events.append(event)
        if event.kind in MELTING_KINDS:
            # Check if next event is a casting event
            next_is_casting = i + 1 < len(raw_events) and raw_events[i + 1].kind in CASTING_KINDS
            if not next_is_casting:
                process_events.append(ProcessEvent(kind=ProcessKind.CastingUnspecified))

    # Drop cooling/quenching steps that immediately follow sintering (implied by SPS/HPS)
    _SINTERING_KINDS = {ProcessKind.SparkPlasmaSintering, ProcessKind.HotPressingSintering}
    filtered_events: list[ProcessEvent] = []
    for i, event in enumerate(process_events):
        if event.kind == ProcessKind.WaterQuenching and i > 0 and process_events[i - 1].kind in _SINTERING_KINDS:
            continue
        filtered_events.append(event)
    process_events = filtered_events

    # Build purity description for raw materials
    purity_desc = _build_purity_description(entry)
    raw_materials = {"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description=purity_desc)}

    try:
        material = Material(
            measurements=[CompMeasurement(composition, validate_composition=False)],
        )
        experiment = Experiment(
            raw_materials=raw_materials,
            synthesis_groups=process_events,
            output_materials=[material],
        )
    except ValueError as e:
        print(f"  Validation error for {entry['material']!r}: {e}")
        return None

    return experiment


# ---------------------------------------------------------------------------
# Synthesis-focused matching helpers
# ---------------------------------------------------------------------------


def composition_l1_distance(c1: Composition, c2: Composition) -> float:
    """L1 distance on fractional composition vectors.

    Sum of absolute element-wise differences in fractional composition.
    """
    f1 = c1.fractional_composition.as_dict()
    f2 = c2.fractional_composition.as_dict()
    all_els = set(f1) | set(f2)
    return sum(abs(f1.get(el, 0) - f2.get(el, 0)) for el in all_els)


def get_material_composition(material: Material) -> Composition | None:
    """Extract the first CompMeasurement's composition from a material."""
    for m in material.measurements:
        if isinstance(m, CompMeasurement):
            return m.composition
    return None


def _qty_to_celsius(q: Quantity | None) -> float | None:
    """Convert a Quantity temperature to degrees Celsius."""
    if q is None or q.numeric_value is None:
        return None
    try:
        pint_q = ureg.Quantity(float(q.numeric_value), q.unit)
        return pint_q.to(ureg.celsius).magnitude
    except Exception:
        return None


def _qty_to_hours(q: Quantity | None) -> float | None:
    """Convert a Quantity duration to hours."""
    if q is None or q.numeric_value is None:
        return None
    try:
        pint_q = ureg.Quantity(float(q.numeric_value), q.unit)
        return pint_q.to(ureg.hour).magnitude
    except Exception:
        return None


def compare_aligned_conditions(
    result: ProcessEventAlignmentResult,
) -> dict:
    """Compare temperature and duration on aligned event pairs with matching kinds.

    Returns dict with keys:
      temp_matches, temp_total, dur_matches, dur_total
    """
    temp_matches = 0
    temp_total = 0
    dur_matches = 0
    dur_total = 0

    for ev_a, ev_b in result.alignment:
        if ev_a is None or ev_b is None:
            continue
        if normalize_kind(ev_a.kind) != normalize_kind(ev_b.kind):
            continue

        # Temperature comparison
        t_a = _qty_to_celsius(ev_a.temperature)
        t_b = _qty_to_celsius(ev_b.temperature)
        if t_a is not None and t_b is not None:
            temp_total += 1
            if abs(t_a - t_b) < 5.0:
                temp_matches += 1
        elif t_a is not None or t_b is not None:
            temp_total += 1  # one has it, the other doesn't

        # Duration comparison
        d_a = _qty_to_hours(ev_a.duration)
        d_b = _qty_to_hours(ev_b.duration)
        if d_a is not None and d_b is not None:
            dur_total += 1
            if abs(d_a - d_b) < 0.1:
                dur_matches += 1
        elif d_a is not None or d_b is not None:
            dur_total += 1

    return {
        "temp_matches": temp_matches,
        "temp_total": temp_total,
        "dur_matches": dur_matches,
        "dur_total": dur_total,
    }


# ---------------------------------------------------------------------------
# Diff view helpers
# ---------------------------------------------------------------------------


def _fmt_event(event: ProcessEvent | None, kind_w: int = 28) -> str:
    """Format a single ProcessEvent as a column-aligned string.

    Uses fixed-width columns so kind, temperature, and duration align
    vertically across rows.
    """
    if event is None:
        return ""
    kind = normalize_kind(event.kind)
    t = _qty_to_celsius(event.temperature)
    temp_str = f"{t:.0f}°C" if t is not None else ""
    d = _qty_to_hours(event.duration)
    if d is not None:
        dur_str = f"{d * 60:.0f}min" if d < 1 else f"{d:.1f}h"
    else:
        dur_str = ""
    return f"{kind:<{kind_w}} {temp_str:>8} {dur_str:>8}"


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def print_doi_diff(
    doi: str,
    gt_materials: list[MaterialWithContext],
    ext_materials: list[MaterialWithContext],
    matched_pairs: list[tuple[int, int, dict]],
    matched_gt: set[int],
    matched_ext: set[int],
) -> None:
    """Print a github-diff style view for one DOI."""
    term_width = shutil.get_terminal_size((120, 24)).columns
    col_w = max(35, (term_width - 5) // 2)

    def row(left: str, marker: str, right: str) -> str:
        return f"  {_truncate(left, col_w).ljust(col_w)} {marker} {_truncate(right, col_w)}"

    print(f"\n{'─' * (term_width - 2)}")
    print(
        f"  {doi}  "
        f"({len(matched_pairs)} matched, "
        f"{len(gt_materials) - len(matched_gt)} unmatched GT, "
        f"{len(ext_materials) - len(matched_ext)} unmatched ext)"
    )
    print(row("EXTRACTED", " ", "GROUND TRUTH"))
    print(row("─" * col_w, " ", "─" * col_w))

    for gt_idx, ext_idx, pd in matched_pairs:
        gt_comp = pd["gt_comp"]
        ext_comp = pd["ext_comp"]
        gt_formula = gt_comp.reduced_formula if gt_comp else "?"
        ext_formula = ext_comp.reduced_formula if ext_comp else "?"
        comp_ok = "=" if pd["comp_dist"] < 0.01 else "~"

        proc_result = align_process_events(pd["gt_events"], pd["ext_events"])
        prec, rec, f1 = alignment_kind_metrics(proc_result)
        print(
            f"\n  @@ material {gt_idx} @@ "
            f"comp_L1={pd['comp_dist']:.3f}  PED={pd['ped']}  "
            f"kind P={prec:.0%} R={rec:.0%} F1={f1:.0%}"
        )
        print(row(f"comp: {ext_formula}", comp_ok, f"comp: {gt_formula}"))
        for ev_gt, ev_ext in proc_result.alignment:
            left = _fmt_event(ev_ext)
            right = _fmt_event(ev_gt)
            if ev_gt is None:
                print(row(left, "-", ""))
            elif ev_ext is None:
                print(row("", "+", right))
            elif normalize_kind(ev_gt.kind) == normalize_kind(ev_ext.kind):
                # Kinds match — check conditions
                t_a = _qty_to_celsius(ev_ext.temperature)
                t_b = _qty_to_celsius(ev_gt.temperature)
                d_a = _qty_to_hours(ev_ext.duration)
                d_b = _qty_to_hours(ev_gt.duration)
                cond_ok = True
                if t_a is not None and t_b is not None and abs(t_a - t_b) >= 5.0:
                    cond_ok = False
                if d_a is not None and d_b is not None and abs(d_a - d_b) >= 0.1:
                    cond_ok = False
                print(row(left, " " if cond_ok else "~", right))
            else:
                print(row(left, "!", right))

    # Unmatched extracted materials
    for j in range(len(ext_materials)):
        if j not in matched_ext:
            ext_comp = get_material_composition(ext_materials[j].material)
            ext_events = _ensure_mixing_step(
                resolve_process_events(ext_materials[j].material, ext_materials[j].synthesis_group_map)
            )
            formula = ext_comp.reduced_formula if ext_comp else "?"
            print("\n  @@ unmatched extracted @@")
            print(row(f"comp: {formula}", "-", ""))
            for ev in ext_events:
                print(row(_fmt_event(ev), "-", ""))

    # Unmatched GT materials
    for i in range(len(gt_materials)):
        if i not in matched_gt:
            gt_comp = get_material_composition(gt_materials[i].material)
            gt_events = _ensure_mixing_step(
                resolve_process_events(gt_materials[i].material, gt_materials[i].synthesis_group_map)
            )
            formula = gt_comp.reduced_formula if gt_comp else "?"
            print("\n  @@ unmatched ground truth @@")
            print(row("", "+", f"comp: {formula}"))
            for ev in gt_events:
                print(row("", "+", _fmt_event(ev)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _ensure_mixing_step(events: list[ProcessEvent]) -> list[ProcessEvent]:
    """Always prepend an implicit Mixing step (mixing raw elements) since lematerial always includes one."""
    from litxbench.core.eval import normalize_process_events

    return normalize_process_events(events)


UNMATCHED_PENALTY = 5.0


def main() -> None:
    if not LEMATERIAL_RESULTS_DIR.exists():
        print(f"ERROR: Results directory not found: {LEMATERIAL_RESULTS_DIR}")
        sys.exit(1)

    output_dir = Path("outputs/lematerial")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect DOIs present in both lematerial results and ground truth
    ground_truth_dois = set(papers.keys())
    available_dois: list[str] = []
    for d in sorted(LEMATERIAL_RESULTS_DIR.iterdir()):
        if d.is_dir() and d.name in ground_truth_dois:
            available_dois.append(d.name)

    if not available_dois:
        print("ERROR: No overlapping DOIs found between lematerial results and ground truth")
        sys.exit(1)

    print(f"Found {len(available_dois)} overlapping DOIs out of {len(ground_truth_dois)} ground truth papers")

    # Load lematerial results as list[Experiment] per DOI
    lematerial_experiments: dict[str, list[Experiment]] = {}
    for doi in available_dois:
        result_path = LEMATERIAL_RESULTS_DIR / doi / "result.json"
        if not result_path.exists():
            print(f"  WARNING: {result_path} not found, skipping")
            continue

        with open(result_path) as f:
            entries = json.load(f)

        experiments: list[Experiment] = []
        for entry in entries:
            exp = convert_entry_to_experiment(entry)
            if exp is not None:
                experiments.append(exp)

        if experiments:
            lematerial_experiments[doi] = experiments
        else:
            print(f"  WARNING: No valid experiments for {doi}")

    dois_to_eval = [doi for doi in available_dois if doi in lematerial_experiments]
    if not dois_to_eval:
        print("ERROR: No valid experiments to evaluate")
        sys.exit(1)

    print(f"\nEvaluating {len(dois_to_eval)} DOIs with valid experiments...\n")

    # ---------------------------------------------------------------------------
    # Per-DOI evaluation
    # ---------------------------------------------------------------------------

    all_doi_metrics: list[dict] = []

    # Aggregate accumulators
    agg_comp_exact = 0
    agg_comp_total = 0
    agg_comp_l1_sum = 0.0
    agg_ped_sum = 0.0
    agg_ped_count = 0
    agg_kind_prec_sum = 0.0
    agg_kind_rec_sum = 0.0
    agg_kind_f1_sum = 0.0
    agg_kind_count = 0
    agg_temp_matches = 0
    agg_temp_total = 0
    agg_dur_matches = 0
    agg_dur_total = 0
    agg_matched = 0
    agg_unmatched_gt = 0
    agg_unmatched_ext = 0

    for doi in dois_to_eval:
        gt_experiments = papers[doi]
        ext_experiments = lematerial_experiments[doi]

        gt_materials = _collect_materials(gt_experiments)
        ext_materials = _collect_materials(ext_experiments)

        n_gt = len(gt_materials)
        n_ext = len(ext_materials)

        # Build cost matrix
        size = max(n_gt, n_ext)
        cost_matrix = [[UNMATCHED_PENALTY] * size for _ in range(size)]
        # Cache per-pair data for later metric extraction
        pair_data: dict[tuple[int, int], dict] = {}

        for i in range(n_gt):
            gt_comp = get_material_composition(gt_materials[i].material)
            gt_events = _ensure_mixing_step(
                resolve_process_events(gt_materials[i].material, gt_materials[i].synthesis_group_map)
            )
            for j in range(n_ext):
                ext_comp = get_material_composition(ext_materials[j].material)
                ext_events = _ensure_mixing_step(
                    resolve_process_events(ext_materials[j].material, ext_materials[j].synthesis_group_map)
                )

                # Composition distance
                if gt_comp is not None and ext_comp is not None:
                    comp_dist = composition_l1_distance(gt_comp, ext_comp)
                else:
                    comp_dist = 2.0  # max possible L1 distance

                # Process edit distance
                ped = process_event_edit_distance(gt_events, ext_events)
                max_len = max(len(gt_events), len(ext_events), 1)
                norm_ped = ped / max_len

                # Condition similarity (temperature + duration) on aligned events
                proc_alignment = align_process_events(gt_events, ext_events)
                cond_info = compare_aligned_conditions(proc_alignment)
                cond_mismatches = (cond_info["temp_total"] - cond_info["temp_matches"]) + (
                    cond_info["dur_total"] - cond_info["dur_matches"]
                )
                cond_total = cond_info["temp_total"] + cond_info["dur_total"]
                norm_cond_dist = cond_mismatches / cond_total if cond_total else 0.0

                cost = 10.0 * comp_dist + 1.0 * norm_ped + 0.5 * norm_cond_dist
                cost_matrix[i][j] = cost

                pair_data[(i, j)] = {
                    "gt_comp": gt_comp,
                    "ext_comp": ext_comp,
                    "comp_dist": comp_dist,
                    "ped": ped,
                    "norm_ped": norm_ped,
                    "gt_events": gt_events,
                    "ext_events": ext_events,
                }

        # Hungarian assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)

        doi_comp_exact = 0
        doi_comp_total = 0
        doi_comp_l1_sum = 0.0
        doi_ped_sum = 0.0
        doi_ped_count = 0
        doi_kind_prec_sum = 0.0
        doi_kind_rec_sum = 0.0
        doi_kind_f1_sum = 0.0
        doi_kind_count = 0
        doi_temp_matches = 0
        doi_temp_total = 0
        doi_dur_matches = 0
        doi_dur_total = 0
        doi_matched = 0
        doi_unmatched_gt = 0
        doi_unmatched_ext = 0

        matched_gt: set[int] = set()
        matched_ext: set[int] = set()
        matched_pairs_for_diff: list[tuple[int, int, dict]] = []

        for r, c in zip(row_ind, col_ind):
            if r < n_gt and c < n_ext and cost_matrix[r][c] < UNMATCHED_PENALTY:
                matched_gt.add(r)
                matched_ext.add(c)
                doi_matched += 1

                pd = pair_data[(r, c)]

                # Composition metrics
                doi_comp_total += 1
                doi_comp_l1_sum += pd["comp_dist"]
                comp_exact = False
                if pd["gt_comp"] is not None and pd["ext_comp"] is not None:
                    gt_frac = pd["gt_comp"].fractional_composition.alphabetical_formula
                    ext_frac = pd["ext_comp"].fractional_composition.alphabetical_formula
                    if gt_frac == ext_frac:
                        doi_comp_exact += 1
                        comp_exact = True

                # PED
                doi_ped_sum += pd["ped"]
                doi_ped_count += 1

                # Kind metrics from alignment (matches main benchmark)
                proc_alignment = align_process_events(pd["gt_events"], pd["ext_events"])
                prec, rec, f1 = alignment_kind_metrics(proc_alignment)
                doi_kind_prec_sum += prec
                doi_kind_rec_sum += rec
                doi_kind_f1_sum += f1
                doi_kind_count += 1

                # Aligned conditions
                cond = compare_aligned_conditions(proc_alignment)
                doi_temp_matches += cond["temp_matches"]
                doi_temp_total += cond["temp_total"]
                doi_dur_matches += cond["dur_matches"]
                doi_dur_total += cond["dur_total"]

                pd["comp_exact"] = comp_exact
                pd["kind_prec"] = prec
                pd["kind_rec"] = rec
                pd["kind_f1"] = f1
                pd["cond"] = cond
                matched_pairs_for_diff.append((r, c, pd))

        doi_unmatched_gt = n_gt - len(matched_gt)
        doi_unmatched_ext = n_ext - len(matched_ext)

        # Diff view
        print_doi_diff(doi, gt_materials, ext_materials, matched_pairs_for_diff, matched_gt, matched_ext)

        # Per-DOI summary
        comp_exact_rate = doi_comp_exact / doi_comp_total if doi_comp_total else 0.0
        avg_comp_l1 = doi_comp_l1_sum / doi_comp_total if doi_comp_total else 0.0
        avg_ped = doi_ped_sum / doi_ped_count if doi_ped_count else 0.0
        avg_kind_prec = doi_kind_prec_sum / doi_kind_count if doi_kind_count else 0.0
        avg_kind_rec = doi_kind_rec_sum / doi_kind_count if doi_kind_count else 0.0
        avg_kind_f1 = doi_kind_f1_sum / doi_kind_count if doi_kind_count else 0.0
        temp_rate = doi_temp_matches / doi_temp_total if doi_temp_total else float("nan")
        dur_rate = doi_dur_matches / doi_dur_total if doi_dur_total else float("nan")

        # --- Per-DOI readable summary ---
        print(f"\n  {doi}  ({n_gt} ground-truth, {n_ext} extracted)")
        for _gt_idx, _ext_idx, pd in matched_pairs_for_diff:
            gt_f = pd["gt_comp"].reduced_formula if pd["gt_comp"] else "?"
            ext_f = pd["ext_comp"].reduced_formula if pd["ext_comp"] else "?"
            comp_str = f"{ext_f}" if pd["comp_exact"] else f"{ext_f} (expected {gt_f}, L1={pd['comp_dist']:.3f})"
            cond = pd["cond"]
            temp_str = f"{cond['temp_matches']}/{cond['temp_total']}" if cond["temp_total"] else "-"
            dur_str = f"{cond['dur_matches']}/{cond['dur_total']}" if cond["dur_total"] else "-"
            print(
                f"    matched: {comp_str}  "
                f"edit_dist={pd['ped']}  kind_F1={pd['kind_f1']:.0%}  "
                f"temp={temp_str}  dur={dur_str}"
            )
        if doi_unmatched_gt:
            for i in range(n_gt):
                if i not in matched_gt:
                    gt_comp = get_material_composition(gt_materials[i].material)
                    print(f"    missed:  {gt_comp.reduced_formula if gt_comp else '?'}")
        if doi_unmatched_ext:
            for j in range(n_ext):
                if j not in matched_ext:
                    ext_comp = get_material_composition(ext_materials[j].material)
                    print(f"    extra:   {ext_comp.reduced_formula if ext_comp else '?'}")
        # Overall DOI error: average per-material error across all ground-truth materials.
        # Matched materials contribute their actual error; missed materials get a penalty of 1.0.
        material_errors: list[float] = []
        for _gt_idx, _ext_idx, pd in matched_pairs_for_diff:
            max_len = max(len(pd["gt_events"]), len(pd["ext_events"]), 1)
            norm_ped = pd["ped"] / max_len
            material_err = 0.5 * min(pd["comp_dist"], 1.0) + 0.5 * (1.0 - pd["kind_f1"])
            material_errors.append(material_err)
        for _ in range(doi_unmatched_gt):
            material_errors.append(1.0)
        doi_error = sum(material_errors) / len(material_errors) if material_errors else 1.0
        extra_penalty = doi_unmatched_ext / max(n_gt, 1)
        print(f"    >> error={doi_error:.3f}  (extra_penalty={extra_penalty:.2f})")

        doi_metrics = {
            "doi": doi,
            "n_gt_materials": n_gt,
            "n_ext_materials": n_ext,
            "n_matched": doi_matched,
            "n_unmatched_gt": doi_unmatched_gt,
            "n_unmatched_ext": doi_unmatched_ext,
            "comp_exact_match_rate": comp_exact_rate,
            "avg_comp_l1": avg_comp_l1,
            "avg_process_edit_distance": avg_ped,
            "avg_kind_precision": avg_kind_prec,
            "avg_kind_recall": avg_kind_rec,
            "avg_kind_f1": avg_kind_f1,
            "temp_matches": doi_temp_matches,
            "temp_total": doi_temp_total,
            "temp_match_rate": temp_rate,
            "dur_matches": doi_dur_matches,
            "dur_total": doi_dur_total,
            "dur_match_rate": dur_rate,
        }
        all_doi_metrics.append(doi_metrics)

        # Accumulate aggregates
        agg_comp_exact += doi_comp_exact
        agg_comp_total += doi_comp_total
        agg_comp_l1_sum += doi_comp_l1_sum
        agg_ped_sum += doi_ped_sum
        agg_ped_count += doi_ped_count
        agg_kind_prec_sum += doi_kind_prec_sum
        agg_kind_rec_sum += doi_kind_rec_sum
        agg_kind_f1_sum += doi_kind_f1_sum
        agg_kind_count += doi_kind_count
        agg_temp_matches += doi_temp_matches
        agg_temp_total += doi_temp_total
        agg_dur_matches += doi_dur_matches
        agg_dur_total += doi_dur_total
        agg_matched += doi_matched
        agg_unmatched_gt += doi_unmatched_gt
        agg_unmatched_ext += doi_unmatched_ext

    # ---------------------------------------------------------------------------
    # Aggregate summary
    # ---------------------------------------------------------------------------

    print(f"\n{'=' * 100}")
    print("AGGREGATE SUMMARY")
    print(f"{'=' * 100}")

    total_gt = agg_matched + agg_unmatched_gt
    total_ext = agg_matched + agg_unmatched_ext
    print(f"  Materials: {agg_matched} matched / {total_gt} ground truth / {total_ext} extracted")
    print(f"  Unmatched: {agg_unmatched_gt} GT, {agg_unmatched_ext} extracted")

    o_comp_exact_rate = agg_comp_exact / agg_comp_total if agg_comp_total else 0.0
    o_avg_comp_l1 = agg_comp_l1_sum / agg_comp_total if agg_comp_total else 0.0
    o_avg_ped = agg_ped_sum / agg_ped_count if agg_ped_count else 0.0
    o_avg_kind_prec = agg_kind_prec_sum / agg_kind_count if agg_kind_count else 0.0
    o_avg_kind_rec = agg_kind_rec_sum / agg_kind_count if agg_kind_count else 0.0
    o_avg_kind_f1 = agg_kind_f1_sum / agg_kind_count if agg_kind_count else 0.0
    o_temp_rate = agg_temp_matches / agg_temp_total if agg_temp_total else float("nan")
    o_dur_rate = agg_dur_matches / agg_dur_total if agg_dur_total else float("nan")

    print(f"  Composition exact match rate: {o_comp_exact_rate:.1%}")
    print(f"  Avg composition L1 distance:  {o_avg_comp_l1:.4f}")
    print(f"  Avg process edit distance:    {o_avg_ped:.2f}")
    print(f"  Process kind precision:       {o_avg_kind_prec:.1%}")
    print(f"  Process kind recall:          {o_avg_kind_rec:.1%}")
    print(f"  Process kind F1:              {o_avg_kind_f1:.1%}")
    print(
        f"  Temperature match rate:       {agg_temp_matches}/{agg_temp_total} = {o_temp_rate:.1%}"
        if agg_temp_total
        else "  Temperature match rate:       N/A (no comparable temps)"
    )
    print(
        f"  Duration match rate:          {agg_dur_matches}/{agg_dur_total} = {o_dur_rate:.1%}"
        if agg_dur_total
        else "  Duration match rate:          N/A (no comparable durations)"
    )

    # ---------------------------------------------------------------------------
    # Save detailed JSON
    # ---------------------------------------------------------------------------

    aggregate = {
        "n_dois": len(dois_to_eval),
        "n_matched": agg_matched,
        "n_unmatched_gt": agg_unmatched_gt,
        "n_unmatched_ext": agg_unmatched_ext,
        "comp_exact_match_rate": o_comp_exact_rate,
        "avg_comp_l1": o_avg_comp_l1,
        "avg_process_edit_distance": o_avg_ped,
        "avg_kind_precision": o_avg_kind_prec,
        "avg_kind_recall": o_avg_kind_rec,
        "avg_kind_f1": o_avg_kind_f1,
        "temp_matches": agg_temp_matches,
        "temp_total": agg_temp_total,
        "temp_match_rate": o_temp_rate if agg_temp_total else None,
        "dur_matches": agg_dur_matches,
        "dur_total": agg_dur_total,
        "dur_match_rate": o_dur_rate if agg_dur_total else None,
    }

    output_path = output_dir / "synthesis_eval_metrics.json"
    with open(output_path, "w") as f:
        json.dump({"aggregate": aggregate, "per_doi": all_doi_metrics}, f, indent=2)

    print(f"\n  -> Saved detailed metrics to {output_path}")


if __name__ == "__main__":
    main()
