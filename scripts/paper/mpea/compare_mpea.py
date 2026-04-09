"""Compare our extraction value counts against the MPEA dataset.

Downloads the MPEA CSV from GitHub (cached locally), finds DOIs in common,
and for each overlapping DOI counts how many numeric values each dataset
extracted from the paper.

"Values" from our data:
  - Each Measurement.numeric_value (the primary measurement)
  - Each Measurement.temperature / pressure (if present)
  - Each unique composition (counted once per DOI) + measurement method
  - Each LatticeMeasurement's lattice parameters (a, b, c, alpha, beta, gamma)
  - Each GlobalLatticeParam's lattice + phase_fraction
  - Each ProcessEvent's kind + temperature / duration
  - Configuration measurements (recursed into)

"Values" from MPEA:
  - Every non-empty numeric cell in the property columns for rows sharing
    that DOI (excludes Calculated Density and Calculated Young modulus
    since experimental versions exist; excludes Microstructure free-text)
  - BCC/FCC/other categorical column (comparable to our Configuration)
  - Each unique composition from the FORMULA column (counted once per DOI)
"""

from __future__ import annotations

import csv
import re

from pymatgen.core.composition import Composition
from pymatgen.core.lattice import Lattice as PymatgenLattice

from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
    ProcessEvent,
    Quantity,
)
from litxbench.core.utils import doi_to_name
from litxbench.litxalloy import papers
from scripts.paper.mpea.mpea_utils import MPEA_DOI_COL, download_mpea_csv

# Numeric property columns in the MPEA CSV.  The actual headers carry a
# "PROPERTY: " prefix and LaTeX unit annotations, so we match by substring.
MPEA_NUMERIC_SUBSTRINGS = [
    "grain size",
    "Exp. Density",
    "HV",
    "Test temperature",
    "YS",
    "UTS",
    "Elongation (%)",
    "Elongation plastic",
    "Exp. Young modulus",
    "O content",
    "N content",
    "C content",
]

MPEA_CATEGORICAL_SUBSTRINGS = [
    "BCC/FCC/other",
    "Processing method",
]

MPEA_FORMULA_COL = "FORMULA"


# ---------------------------------------------------------------------------
# Count numeric values from our extractions
# ---------------------------------------------------------------------------

_NUM_RE = re.compile(r"^[~><]=?\s*[-+]?\d")


def _is_numeric(v: object) -> bool:
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        return bool(_NUM_RE.match(v.strip()))
    return False


def _count_quantity(q: Quantity | None) -> int:
    if q is None:
        return 0
    return 1 if _is_numeric(q.value) else 0


def _count_lattice(lat: PymatgenLattice) -> int:
    """Count unique lattice parameters (a, b, c, alpha, beta, gamma)."""
    # For a cubic lattice a=b=c and alpha=beta=gamma=90, but the paper
    # still reported *one* number, so count the unique non-90-degree lengths.
    # params = [lat.a, lat.b, lat.c, lat.alpha, lat.beta, lat.gamma]
    # Count each parameter that isn't a default 90-degree angle
    count = 0
    lengths = {lat.a, lat.b, lat.c}
    count += len(lengths)  # unique axis lengths
    angles = {lat.alpha, lat.beta, lat.gamma}
    angles.discard(90.0)
    count += len(angles)  # non-trivial angles
    return count


def _comp_key(comp: Composition) -> str:
    """Canonical string key for a composition (sorted element fractions)."""
    frac = comp.fractional_composition
    return " ".join(f"{el}{round(amt, 6)}" for el, amt in sorted(frac.as_dict().items()))


def _collect_compositions(item: object) -> list[Composition]:
    """Collect all Composition objects from a measurement-like object."""
    if isinstance(item, CompMeasurement):
        return [item.composition]
    if isinstance(item, Configuration):
        comps: list[Composition] = []
        for m in item.measurements:
            comps.extend(_collect_compositions(m))
        return comps
    return []


def _count_measurement_item(item: object) -> int:
    """Count numeric values from a single measurement-like object.

    Compositions are excluded here and counted separately as unique values.
    """
    total = 0

    if isinstance(item, Measurement):
        if _is_numeric(item.value):
            total += 1
        total += _count_quantity(item.temperature)
        total += _count_quantity(item.pressure)

    elif isinstance(item, CompMeasurement):
        total += 1  # composition measurement method is an extracted value

    elif isinstance(item, LatticeMeasurement):
        total += _count_lattice(item.lattice)

    elif isinstance(item, GlobalLatticeParam):
        if item.lattice is not None:
            total += _count_lattice(item.lattice.lattice)
        if item.phase_fraction is not None:
            total += _count_quantity(item.phase_fraction)

    elif isinstance(item, Configuration):
        for m in item.measurements:
            total += _count_measurement_item(m)

    return total


def _count_process_event(evt: ProcessEvent) -> int:
    total = 1  # the process kind itself is an extracted value
    total += _count_quantity(evt.temperature)
    total += _count_quantity(evt.duration)
    return total


def count_our_values(experiments: list[Experiment]) -> int:  # type: ignore[type-arg]
    total = 0
    comp_keys: set[str] = set()
    for exp in experiments:
        # Synthesis groups (process events)
        for group in exp.synthesis_group_map.values():
            for evt in group.process_events:
                total += _count_process_event(evt)

        # Output materials
        for material in exp.output_materials:
            for m in material.measurements:
                total += _count_measurement_item(m)
                for c in _collect_compositions(m):
                    comp_keys.add(_comp_key(c))
    return total + len(comp_keys)


# ---------------------------------------------------------------------------
# Count ALL extracted fields from our extractions
# ---------------------------------------------------------------------------


def _count_quantity_all(q: Quantity | None) -> int:
    """Count everything in a Quantity: value + unit (always 1 each)."""
    if q is None:
        return 0
    return 1  # the numeric value (unit is implicit/always present, not separately counted)


def _count_measurement_item_all(item: object) -> int:
    """Count every extracted field from a single measurement-like object."""
    total = 0

    if isinstance(item, Measurement):
        if _is_numeric(item.value):
            total += 1
        if item.uncertainty is not None:
            total += 1
        if item.measurement_method is not None:
            total += 1
        total += _count_quantity_all(item.temperature)
        total += _count_quantity_all(item.pressure)
        if item.measurement_statistic is not None:
            total += 1
        if item.percentile is not None:
            total += 1

    elif isinstance(item, CompMeasurement):
        total += 1  # the method

    elif isinstance(item, LatticeMeasurement):
        total += _count_lattice(item.lattice)

    elif isinstance(item, GlobalLatticeParam):
        if item.lattice is not None:
            total += _count_lattice(item.lattice.lattice)
        if item.phase_fraction is not None:
            total += _count_quantity_all(item.phase_fraction)
        if item.struct is not None:
            total += 1

    elif isinstance(item, Configuration):
        if item.struct is not None:
            total += 1
        if item.tags:
            total += len(item.tags)
        for m in item.measurements:
            total += _count_measurement_item_all(m)

    return total


def _count_process_event_all(evt: ProcessEvent) -> int:
    total = 1  # the process kind
    total += _count_quantity_all(evt.temperature)
    total += _count_quantity_all(evt.duration)
    if evt.equipment is not None:
        total += 1
    return total


def count_our_values_all(experiments: list[Experiment]) -> int:  # type: ignore[type-arg]
    """Count every extracted field (not just numeric measurement values)."""
    total = 0
    comp_keys: set[str] = set()
    for exp in experiments:
        # Raw materials
        for rm in exp.raw_materials.values():
            total += 1  # the kind

        # Synthesis groups (process events)
        for group in exp.synthesis_group_map.values():
            for evt in group.process_events:
                total += _count_process_event_all(evt)

        # Output materials
        for material in exp.output_materials:
            for m in material.measurements:
                total += _count_measurement_item_all(m)
                for c in _collect_compositions(m):
                    comp_keys.add(_comp_key(c))
    return total + len(comp_keys)


# ---------------------------------------------------------------------------
# Count numeric values from MPEA rows
# ---------------------------------------------------------------------------


def _is_mpea_numeric(cell: str) -> bool:
    cell = cell.strip()
    if not cell:
        return False
    try:
        float(cell)
        return True
    except ValueError:
        return False


def _resolve_cols(headers: list[str], substrings: list[str]) -> list[str]:
    """Find actual CSV header names that match the given substrings."""
    matched: list[str] = []
    for header in headers:
        for sub in substrings:
            if sub in header:
                matched.append(header)
                break
    return matched


def count_mpea_values(
    rows: list[dict[str, str]],
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> int:
    total = 0
    comp_keys: set[str] = set()
    for row in rows:
        for col in numeric_cols:
            if col in row and _is_mpea_numeric(row[col]):
                total += 1
        for col in categorical_cols:
            if col in row and row[col].strip():
                total += 1
        formula = row.get(MPEA_FORMULA_COL, "").strip()
        if formula:
            try:
                comp = Composition(formula)
                comp_keys.add(_comp_key(comp))
            except Exception:
                pass
    return total + len(comp_keys)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    csv_path = download_mpea_csv()

    # Parse MPEA CSV, group rows by DOI
    mpea_by_doi: dict[str, list[dict[str, str]]] = {}
    numeric_cols: list[str] = []
    categorical_cols: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        headers = list(reader.fieldnames)
        numeric_cols = _resolve_cols(headers, MPEA_NUMERIC_SUBSTRINGS)
        categorical_cols = _resolve_cols(headers, MPEA_CATEGORICAL_SUBSTRINGS)
        for row in reader:
            doi = row.get(MPEA_DOI_COL, "").strip()
            if doi:
                mpea_by_doi.setdefault(doi, []).append(row)

    # Build mapping from our key to real DOI for matching
    our_keys = set(papers.keys())
    mpea_key_to_real: dict[str, str] = {}
    for real_doi in mpea_by_doi:
        key = doi_to_name(real_doi)
        if key in our_keys:
            mpea_key_to_real[key] = real_doi

    overlap = sorted(mpea_key_to_real.keys())
    print(f"DOIs in our dataset: {len(our_keys)}")
    print(f"DOIs in MPEA dataset: {len(mpea_by_doi)}")
    print(f"Overlapping DOIs:     {len(overlap)}")
    print()

    if not overlap:
        print("No overlapping DOIs found.")
        return

    total_ours = 0
    total_ours_all = 0
    total_mpea = 0

    header = f"{'DOI key':<50} {'Ours':>6} {'All':>6} {'MPEA':>6} {'MPEA rows':>10}"
    print(header)
    print("-" * len(header))

    for key in overlap:
        real_doi = mpea_key_to_real[key]
        ours = count_our_values(papers[key])
        ours_all = count_our_values_all(papers[key])
        mpea = count_mpea_values(mpea_by_doi[real_doi], numeric_cols, categorical_cols)
        n_rows = len(mpea_by_doi[real_doi])
        print(f"{key:<50} {ours:>6} {ours_all:>6} {mpea:>6} {n_rows:>10}")
        total_ours += ours
        total_ours_all += ours_all
        total_mpea += mpea

    print("-" * len(header))
    n = len(overlap)
    print(f"{'Average':<50} {total_ours / n:>6.1f} {total_ours_all / n:>6.1f} {total_mpea / n:>6.1f}")
    print(f"{'Total':<50} {total_ours:>6} {total_ours_all:>6} {total_mpea:>6}")

    # ----- All 19 papers (ours only) -----
    print()
    print("=" * 70)
    print("All papers (ours only)")
    print("=" * 70)
    print()

    all_total = 0
    all_total_all = 0

    header2 = f"{'DOI key':<50} {'Ours':>6} {'All':>6}"
    print(header2)
    print("-" * len(header2))

    for key in sorted(papers.keys()):
        ours = count_our_values(papers[key])
        ours_all = count_our_values_all(papers[key])
        print(f"{key:<50} {ours:>6} {ours_all:>6}")
        all_total += ours
        all_total_all += ours_all

    print("-" * len(header2))
    n_all = len(papers)
    print(f"{'Average':<50} {all_total / n_all:>6.1f} {all_total_all / n_all:>6.1f}")
    print(f"{'Total':<50} {all_total:>6} {all_total_all:>6}")


if __name__ == "__main__":
    main()
