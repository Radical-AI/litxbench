"""Find errors in the MPEA dataset by comparing against our verified extractions.

For each overlapping DOI, matches MPEA rows to our materials by composition
and test temperature, then checks for:

1. **Phase errors** – crystal structures (BCC/FCC/other) that MPEA gets wrong
   or phases that are missing/added incorrectly.
2. **Numeric errors** – obviously incorrect numbers for hardness, yield
   strength, UTS, elongation, Young's modulus, density, and grain size.
3. **Composition errors** – MPEA formula has missing/extra elements or
   wrong stoichiometry compared to the paper.
4. **Missing values** – the paper reports a value that maps to an MPEA
   column, but MPEA left that cell blank.

Unit conversions are handled automatically (GPa↔MPa, mm↔μm, MPa↔HV).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from typing import Sequence

import pint
from pymatgen.core.composition import Composition

from litxbench.core.enums import CrysStruct, ValueQualifier
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    Measurement,
)
from litxbench.core.units import ureg
from litxbench.core.utils import doi_to_name
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    PhaseMeasurementKind,
)
from scripts.paper.mpea.mpea_utils import MPEA_DOI_COL, download_mpea_csv

_STRUCT_TO_MPEA_PHASE: dict[CrysStruct, str] = {
    CrysStruct.FCC: "FCC",
    CrysStruct.BCC: "BCC",
    CrysStruct.HCP: "HCP",
    CrysStruct.L12: "FCC",  # ordered FCC
    CrysStruct.L10: "FCC",  # tetragonal ordered FCC
    CrysStruct.B2: "BCC",  # ordered BCC
    CrysStruct.D03: "BCC",  # ordered BCC variant
}


def _struct_to_mpea(s: CrysStruct) -> str:
    return _STRUCT_TO_MPEA_PHASE.get(s, "other")


_MPEA_UNITS: dict[str, pint.Unit] = {
    "hv": ureg.vickers_hardness,  # HV
    "ys": ureg.megapascal,  # MPa
    "uts": ureg.megapascal,  # MPa
    "elongation": ureg.percent,  # %
    "elongation_plastic": ureg.percent,  # %
    "density_exp": ureg.gram / ureg.cm**3,
    "youngs_exp": ureg.gigapascal,  # GPa
    "grain_size": ureg.micrometer,  # μm
}


def _convert_to_mpea_unit(value: float, our_unit: pint.Unit, mpea_key: str) -> float | None:
    """Convert our value+unit to the MPEA target unit. Returns None on failure."""
    target = _MPEA_UNITS.get(mpea_key)
    if target is None:
        return value  # no conversion needed
    try:
        q = ureg.Quantity(value, our_unit)
        return q.to(target).magnitude
    except (pint.DimensionalityError, pint.UndefinedUnitError):
        return None


def _compositions_match(c1: Composition, c2: Composition, tol: float = 0.0001) -> bool:
    """Check if two compositions are equivalent by fractional composition."""
    f1 = c1.fractional_composition.as_dict()
    f2 = c2.fractional_composition.as_dict()
    all_els = set(f1) | set(f2)
    for el in all_els:
        if abs(f1.get(el, 0) - f2.get(el, 0)) > tol:
            return False
    return True


def _composition_distance(c1: Composition, c2: Composition) -> float:
    """Max absolute difference in fractional composition across all elements."""
    f1 = c1.fractional_composition.as_dict()
    f2 = c2.fractional_composition.as_dict()
    all_els = set(f1) | set(f2)
    return max(abs(f1.get(el, 0) - f2.get(el, 0)) for el in all_els) if all_els else 0.0


def _any_composition_matches(compositions: list[Composition], target: Composition, tol: float = 0.0001) -> bool:
    """Check if any composition in the list matches the target."""
    return any(_compositions_match(c, target, tol) for c in compositions)


def _best_matching_composition(compositions: list[Composition], target: Composition) -> Composition:
    """Return the composition from the list closest to target."""
    return min(compositions, key=lambda c: _composition_distance(c, target))


@dataclass
class MeasurementPoint:
    """A single comparable measurement from our data, with unit and temperature."""

    kind_str: str  # e.g. "yield_strength_compression"
    value: float  # numeric value in original unit
    unit: pint.Unit  # original unit
    is_approx: bool
    temp_c: float | None  # test temperature in °C, or None


@dataclass
class MaterialInfo:
    """Flattened view of a single material for comparison."""

    compositions: list[Composition] = field(default_factory=list)
    phases: list[CrysStruct] = field(default_factory=list)
    points: list[MeasurementPoint] = field(default_factory=list)


def _temp_to_celsius(temp_qty) -> float | None:
    """Convert a Quantity temperature to °C."""
    if temp_qty is None or temp_qty.numeric_value is None:
        return None
    val = float(temp_qty.numeric_value)
    unit_str = str(temp_qty.unit).lower()
    if "kelvin" in unit_str:
        return val - 273.15
    return val  # assume Celsius


def _extract_measurements_recursive(
    measurements: Sequence,
    info: MaterialInfo,
) -> None:
    for m in measurements:
        if isinstance(m, CompMeasurement):
            info.compositions.append(m.composition)
        elif isinstance(m, GlobalLatticeParam):
            if m.struct is not None:
                info.phases.append(m.struct)
        elif isinstance(m, Configuration):
            if m.struct is not None:
                info.phases.append(m.struct)
            _extract_measurements_recursive(m.measurements, info)
        elif isinstance(m, Measurement):
            kind = m.kind
            if isinstance(kind, (AlloyMeasurementKind, PhaseMeasurementKind)):
                kind_str = kind.value
            else:
                kind_str = str(kind)

            nv = m.numeric_value
            if nv is None:
                continue

            is_approx = m.value_qualifier == ValueQualifier.APPROXIMATE
            temp_c = _temp_to_celsius(m.temperature)

            info.points.append(
                MeasurementPoint(
                    kind_str=kind_str,
                    value=float(nv),
                    unit=m.unit,
                    is_approx=is_approx,
                    temp_c=temp_c,
                )
            )


def _extract_material_info(measurements: Sequence) -> MaterialInfo:
    info = MaterialInfo()
    _extract_measurements_recursive(measurements, info)
    return info


def _extract_all_material_infos(experiments: list[Experiment]) -> list[MaterialInfo]:
    results = []
    for exp in experiments:
        for material in exp.output_materials:
            info = _extract_material_info(material.measurements)
            if info.compositions:
                results.append(info)
    return results


def _find_col(headers: list[str], substring: str) -> str | None:
    for h in headers:
        if substring in h:
            return h
    return None


@dataclass
class MpeaRowInfo:
    """Parsed MPEA row."""

    formula: str
    composition: Composition | None
    phase_str: str  # "BCC", "FCC", "other", etc.
    microstructure: str  # e.g. "FCC", "BCC+Sec.", "FCC+BCC"
    test_type: str  # "C" or "T"
    values: dict[str, float]  # column_key → value
    row_idx: int


def _parse_float(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_mpea_row(row: dict[str, str], cols: dict[str, str | None], idx: int) -> MpeaRowInfo:
    formula = row.get("FORMULA", "").strip()
    try:
        comp = Composition(formula) if formula else None
    except Exception:
        comp = None

    phase_str = ""
    if cols["bcc_fcc"]:
        phase_str = row.get(cols["bcc_fcc"], "").strip()
    microstructure = ""
    if cols["microstructure"]:
        microstructure = row.get(cols["microstructure"], "").strip()
    test_type = ""
    if cols["test_type"]:
        test_type = row.get(cols["test_type"], "").strip()

    values: dict[str, float] = {}
    for key, col_name in cols.items():
        if key in ("bcc_fcc", "microstructure", "test_type"):
            continue
        if col_name and col_name in row:
            v = _parse_float(row[col_name])
            if v is not None:
                values[key] = v

    return MpeaRowInfo(
        formula=formula,
        composition=comp,
        phase_str=phase_str,
        microstructure=microstructure,
        test_type=test_type,
        values=values,
        row_idx=idx,
    )


@dataclass
class Error:
    doi_key: str
    mpea_formula: str
    category: str  # "phase", "numeric", "composition", "missing", "info"
    field: str
    our_value: str
    mpea_value: str
    detail: str
    severity: str  # "error" or "warning"
    pct_diff: float | None = None  # for numeric/stoichiometry comparisons


# Map our measurement kinds → MPEA column keys
_OUR_TO_MPEA: dict[str, str] = {
    "yield_strength_tension": "ys",
    "yield_strength_compression": "ys",
    "ultimate_tensile_strength": "uts",
    "ultimate_compressive_strength": "uts",
    "fracture_strain_tension": "elongation",
    "fracture_strain_compression": "elongation",
    "ultimate_strain_tension": "elongation_plastic",
    "ultimate_strain_compression": "elongation_plastic",
    "vickers_hardness": "hv",
    "youngs_modulus": "youngs_exp",
    "density": "density_exp",
    "grain_size": "grain_size",
}


def _our_phases_to_mpea_set(phases: list[CrysStruct]) -> set[str]:
    return {_struct_to_mpea(phase) for phase in phases}


_MPEA_PART_TO_PHASE: dict[str, str] = {
    "FCC": "FCC",
    "BCC": "BCC",
    "HCP": "HCP",
    "B2": "BCC",  # ordered BCC
    "L12": "FCC",  # ordered FCC
    "L10": "FCC",  # tetragonal ordered FCC
    "D03": "BCC",  # ordered BCC variant
    "DHCP": "HCP",
}
# Parts we intentionally ignore (not wrong, just not a basic phase):
#   "Laves", "Sec.", "Other", ""


def _parse_mpea_phase_set(phase_str: str, microstructure: str) -> set[str]:
    """Parse MPEA columns into a set of basic phase labels (FCC/BCC/HCP/other).

    Splits on '+' and maps known ordered structures to their parent lattice
    (B2 → BCC, L12 → FCC, etc.).  "Sec." and "Laves" are ignored since they
    don't tell us the parent lattice type.
    """
    result: set[str] = set()
    # Prefer microstructure if available, as it's more detailed
    sources = [microstructure, phase_str] if microstructure.strip() else [phase_str]
    for src in sources:
        src = src.strip()
        if not src:
            continue
        for part in re.split(r"[+,/]", src):
            part = part.strip()
            mapped = _MPEA_PART_TO_PHASE.get(part.upper())
            if mapped:
                result.add(mapped)
        if result:
            break  # microstructure was informative, don't also parse BCC/FCC/other
    return result


def _compare_phases(
    info: MaterialInfo,
    mpea: MpeaRowInfo,
    doi_key: str,
) -> tuple[list[Error], bool]:
    """Returns (errors, was_compared)."""
    errors: list[Error] = []
    if not info.phases:
        return errors, False

    our_phases = _our_phases_to_mpea_set(info.phases)
    mpea_phases = _parse_mpea_phase_set(mpea.phase_str, mpea.microstructure)

    if not mpea_phases and not mpea.phase_str:
        return errors, False

    for phase in our_phases:
        if phase not in mpea_phases and phase != "other":
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea.formula,
                    category="phase",
                    field="missing_phase",
                    our_value=phase,
                    mpea_value=mpea.phase_str,
                    detail=f"Our data has {phase} phase but MPEA lists '{mpea.phase_str}' (microstructure: '{mpea.microstructure}')",
                    severity="error",
                )
            )

    for phase in mpea_phases:
        if phase not in our_phases and our_phases:
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea.formula,
                    category="phase",
                    field="extra_phase",
                    our_value=", ".join(sorted(our_phases)),
                    mpea_value=phase,
                    detail=f"MPEA claims {phase} phase but our data has: {', '.join(sorted(our_phases))}",
                    severity="error",
                )
            )

    if mpea.phase_str.lower() == "other" and len(our_phases) == 1:
        only = next(iter(our_phases))
        if only in ("BCC", "FCC"):
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea.formula,
                    category="phase",
                    field="wrong_bcc_fcc_label",
                    our_value=only,
                    mpea_value="other",
                    detail=f"MPEA labels BCC/FCC/other as 'other' but paper clearly shows single-phase {only}",
                    severity="warning",
                )
            )

    return errors, True


def _compare_composition(
    our_comp: Composition,
    mpea_comp: Composition,
    mpea_formula: str,
    doi_key: str,
) -> list[Error]:
    """Compare element sets and stoichiometry between our data and MPEA."""
    errors: list[Error] = []
    our_els = set(our_comp.as_dict().keys())
    mpea_els = set(mpea_comp.as_dict().keys())

    missing = our_els - mpea_els
    extra = mpea_els - our_els

    if missing:
        # Filter to elements that are non-trivial (>1 at% in our data)
        our_frac = our_comp.fractional_composition.as_dict()
        significant_missing = {el for el in missing if our_frac.get(str(el), 0) > 0.01}
        if significant_missing:
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea_formula,
                    category="composition",
                    field="missing_element",
                    our_value=", ".join(sorted(str(e) for e in our_els)),
                    mpea_value=", ".join(sorted(str(e) for e in mpea_els)),
                    detail=f"MPEA formula missing element(s): {', '.join(sorted(str(e) for e in significant_missing))} (our: {our_comp.reduced_formula}, MPEA: {mpea_formula})",
                    severity="error",
                )
            )

    if extra:
        mpea_frac = mpea_comp.fractional_composition.as_dict()
        significant_extra = {el for el in extra if mpea_frac.get(str(el), 0) > 0.01}
        if significant_extra:
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea_formula,
                    category="composition",
                    field="extra_element",
                    our_value=", ".join(sorted(str(e) for e in our_els)),
                    mpea_value=", ".join(sorted(str(e) for e in mpea_els)),
                    detail=f"MPEA formula has extra element(s): {', '.join(sorted(str(e) for e in significant_extra))} (our: {our_comp.reduced_formula}, MPEA: {mpea_formula})",
                    severity="error",
                )
            )

    # Check stoichiometry for shared elements
    common = our_els & mpea_els
    if common:
        our_frac = our_comp.fractional_composition.as_dict()
        mpea_frac = mpea_comp.fractional_composition.as_dict()
        for el in sorted(common, key=str):
            diff = abs(our_frac.get(str(el), 0) - mpea_frac.get(str(el), 0))
            if diff > 0.01:  # >1 at% difference is notable
                severity = "error" if diff > 0.03 else "warning"
                errors.append(
                    Error(
                        doi_key=doi_key,
                        mpea_formula=mpea_formula,
                        category="composition",
                        field="stoichiometry",
                        our_value=f"{our_comp.reduced_formula}",
                        mpea_value=mpea_formula,
                        detail=f"{el}: ours={our_frac.get(str(el), 0):.3f}, MPEA={mpea_frac.get(str(el), 0):.3f} (diff={diff:.3f} at. frac.)",
                        severity=severity,
                        pct_diff=diff * 100,  # store as percentage of total composition
                    )
                )

    return errors


# Reverse map: mpea_key → list of our measurement kinds
_MPEA_TO_OURS: dict[str, list[str]] = {}
for _our_kind, _mpea_key in _OUR_TO_MPEA.items():
    _MPEA_TO_OURS.setdefault(_mpea_key, []).append(_our_kind)


def _check_missing_values(
    info: MaterialInfo,
    mpea: MpeaRowInfo,
    doi_key: str,
) -> list[Error]:
    """Flag MPEA cells that are blank but our data has a value for."""
    errors: list[Error] = []

    for mpea_key, our_kinds in _MPEA_TO_OURS.items():
        if mpea_key in mpea.values:
            continue  # MPEA has a value, not missing

        # Do we have any matching measurement?
        candidates = [p for p in info.points if p.kind_str in our_kinds]
        if not candidates:
            continue

        # We have a value but MPEA doesn't — that's a missing value
        best = candidates[0]
        converted = _convert_to_mpea_unit(best.value, best.unit, mpea_key)
        if converted is None:
            continue

        errors.append(
            Error(
                doi_key=doi_key,
                mpea_formula=mpea.formula,
                category="missing",
                field=mpea_key,
                our_value=f"{converted:.4g}",
                mpea_value="(blank)",
                detail=f"MPEA has no {mpea_key} but we extracted {best.kind_str}={converted:.4g}",
                severity="warning",
            )
        )

    return errors


def _find_best_point(
    points: list[MeasurementPoint],
    mpea_key: str,
    mpea_val: float,
    our_kinds: list[str],
) -> MeasurementPoint | None:
    """Find the measurement point that best matches the MPEA value.

    Since MPEA's test temperature column is ambiguous about which
    measurement it refers to, we ignore temperature and instead pick the
    point whose converted value is closest to the MPEA value.  This is
    generous — it gives MPEA the best chance of being correct.
    """
    candidates = [p for p in points if p.kind_str in our_kinds]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Pick the candidate whose unit-converted value is closest to MPEA
    def _distance(pt: MeasurementPoint) -> float:
        converted = _convert_to_mpea_unit(pt.value, pt.unit, mpea_key)
        if converted is None:
            return float("inf")
        return abs(converted - mpea_val)

    candidates.sort(key=_distance)
    return candidates[0]


def _compare_numerics(
    info: MaterialInfo,
    mpea: MpeaRowInfo,
    doi_key: str,
) -> tuple[list[Error], int]:
    """Returns (errors, num_value_comparisons_made)."""
    errors: list[Error] = []
    num_compared = 0

    for mpea_key, mpea_val in mpea.values.items():
        our_kinds = _MPEA_TO_OURS.get(mpea_key)
        if not our_kinds:
            continue

        point = _find_best_point(info.points, mpea_key, mpea_val, our_kinds)
        if point is None:
            # MPEA has a value but we don't — not a comparison
            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea.formula,
                    category="numeric",
                    field=mpea_key,
                    our_value="(not extracted)",
                    mpea_value=str(mpea_val),
                    detail=f"MPEA has {mpea_key}={mpea_val} but we have no corresponding measurement",
                    severity="warning",
                )
            )
            continue

        # Convert our value to MPEA units
        our_val_converted = _convert_to_mpea_unit(point.value, point.unit, mpea_key)
        if our_val_converted is None:
            continue

        num_compared += 1

        if our_val_converted == 0 and mpea_val == 0:
            continue

        if our_val_converted != mpea_val:
            if our_val_converted != 0:
                pct_diff = abs(our_val_converted - mpea_val) / abs(our_val_converted) * 100
            else:
                pct_diff = 100.0

            severity = "error" if pct_diff > 20 else "warning"

            approx_note = " (our value is approximate)" if point.is_approx else ""

            errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=mpea.formula,
                    category="numeric",
                    field=point.kind_str,
                    our_value=f"{our_val_converted:.4g}{approx_note}",
                    mpea_value=str(mpea_val),
                    detail=f"{point.kind_str}: ours={our_val_converted:.4g}, MPEA={mpea_val} (diff={pct_diff:.1f}%){approx_note}",
                    severity=severity,
                    pct_diff=pct_diff,
                )
            )

    return errors, num_compared


def main() -> None:
    csv_path = download_mpea_csv()

    # Parse MPEA CSV
    mpea_by_doi: dict[str, list[dict[str, str]]] = {}
    headers: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames is not None
        headers = list(reader.fieldnames)
        for row in reader:
            doi = row.get(MPEA_DOI_COL, "").strip()
            if doi:
                mpea_by_doi.setdefault(doi, []).append(row)

    # Resolve column names
    cols: dict[str, str | None] = {
        "bcc_fcc": _find_col(headers, "BCC/FCC/other"),
        "microstructure": _find_col(headers, "Microstructure"),
        "test_type": _find_col(headers, "Type of test"),
        "hv": _find_col(headers, "HV"),
        "ys": _find_col(headers, "YS"),
        "uts": _find_col(headers, "UTS"),
        "elongation": _find_col(headers, "Elongation (%)"),
        "elongation_plastic": _find_col(headers, "Elongation plastic"),
        "density_exp": _find_col(headers, "Exp. Density"),
        "density_calc": _find_col(headers, "Calculated Density"),
        "youngs_exp": _find_col(headers, "Exp. Young modulus"),
        "youngs_calc": _find_col(headers, "Calculated Young modulus"),
        "grain_size": _find_col(headers, "grain size"),
    }

    # Build mapping from our key → real DOI
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

    all_errors: list[Error] = []
    # Track total comparisons per category for match-rate summary
    stats = {"phase_compared": 0, "numeric_compared": 0, "composition_compared": 0}

    for doi_key in overlap:
        real_doi = mpea_key_to_real[doi_key]
        our_materials = _extract_all_material_infos(papers[doi_key])
        mpea_rows = [_parse_mpea_row(row, cols, i) for i, row in enumerate(mpea_by_doi[real_doi])]

        # Track which MPEA formulas matched and which of our comps matched
        matched_mpea_formulas: set[str] = set()
        matched_our_formulas: set[str] = set()

        for mpea_row in mpea_rows:
            if mpea_row.composition is None:
                continue

            # Find all our materials matching this composition (strict)
            matching_materials = [
                m
                for m in our_materials
                if m.compositions and _any_composition_matches(m.compositions, mpea_row.composition)
            ]

            if not matching_materials:
                continue

            matched_mpea_formulas.add(mpea_row.formula)
            for m in matching_materials:
                best_comp = _best_matching_composition(m.compositions, mpea_row.composition)
                matched_our_formulas.add(best_comp.reduced_formula)

            # Use the best-matching composition for error reporting
            best_comp_for_report = _best_matching_composition(matching_materials[0].compositions, mpea_row.composition)

            # Composition comparison
            comp_errs = _compare_composition(
                best_comp_for_report,
                mpea_row.composition,
                mpea_row.formula,
                doi_key,
            )
            all_errors.extend(comp_errs)
            stats["composition_compared"] += 1

            # Phase comparison
            phase_errs, phase_was_compared = _compare_phases(
                matching_materials[0],
                mpea_row,
                doi_key,
            )
            all_errors.extend(phase_errs)
            if phase_was_compared:
                stats["phase_compared"] += 1

            # Numeric comparison — pool all measurement points from
            # all matching materials so we can find the best data point
            pooled = MaterialInfo(
                compositions=matching_materials[0].compositions,
                phases=matching_materials[0].phases,
            )
            for m in matching_materials:
                pooled.points.extend(m.points)

            numeric_errs, n_numeric = _compare_numerics(pooled, mpea_row, doi_key)
            all_errors.extend(numeric_errs)
            stats["numeric_compared"] += n_numeric

            all_errors.extend(_check_missing_values(pooled, mpea_row, doi_key))

        # Flag MPEA formulas with no match in our data.
        # Also try to find the closest our-material to explain the mismatch.
        seen_mpea: set[str] = set()
        for mpea_row in mpea_rows:
            f = mpea_row.formula
            if not f or f in seen_mpea or f in matched_mpea_formulas:
                continue
            if mpea_row.composition is None:
                continue
            seen_mpea.add(f)

            # Find the closest our-material by element overlap
            best_material: MaterialInfo | None = None
            best_comp: Composition | None = None
            best_overlap = 0
            for m in our_materials:
                if not m.compositions:
                    continue
                for comp in m.compositions:
                    our_els = set(comp.as_dict().keys())
                    mpea_els = set(mpea_row.composition.as_dict().keys())
                    overlap_count = len(our_els & mpea_els)
                    if overlap_count > best_overlap:
                        best_overlap = overlap_count
                        best_material = m
                        best_comp = comp

            detail = f"MPEA has composition {f} not found in our data"
            if best_material is not None and best_comp is not None:
                our_els = set(best_comp.as_dict().keys())
                mpea_els = set(mpea_row.composition.as_dict().keys())
                missing = our_els - mpea_els
                extra = mpea_els - our_els
                parts = []
                if missing:
                    parts.append(f"MPEA missing {', '.join(sorted(str(e) for e in missing))}")
                if extra:
                    parts.append(f"MPEA has extra {', '.join(sorted(str(e) for e in extra))}")
                nearest = best_comp.reduced_formula
                detail += f" (nearest ours: {nearest}; {'; '.join(parts)})" if parts else f" (nearest ours: {nearest})"

            all_errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula=f,
                    category="composition",
                    field="unmatched_mpea",
                    our_value="(no match)",
                    mpea_value=f,
                    detail=detail,
                    severity="warning",
                )
            )

        # Flag our compositions with no match in MPEA
        seen_ours: set[str] = set()
        for m in our_materials:
            if not m.compositions:
                continue
            rf = m.compositions[0].reduced_formula
            if rf in seen_ours or rf in matched_our_formulas:
                continue
            seen_ours.add(rf)
            all_errors.append(
                Error(
                    doi_key=doi_key,
                    mpea_formula="(none)",
                    category="info",
                    field="missing_from_mpea",
                    our_value=rf,
                    mpea_value="(not in MPEA)",
                    detail=f"Our data has composition {rf} but MPEA has no matching row",
                    severity="info",
                )
            )

    # Deduplicate
    def _error_key(e: Error) -> tuple:
        return (e.doi_key, e.mpea_formula, e.category, e.field, e.detail)

    seen: set[tuple] = set()
    deduped: list[Error] = []
    for e in all_errors:
        k = _error_key(e)
        if k not in seen:
            seen.add(k)
            deduped.append(e)
    all_errors = deduped

    errors_only = [e for e in all_errors if e.severity == "error"]
    warnings_only = [e for e in all_errors if e.severity == "warning"]

    print("=" * 90)
    print(f"ERRORS FOUND: {len(errors_only)}   WARNINGS: {len(warnings_only)}")
    print("=" * 90)

    # Separate info items from errors/warnings for display
    actionable = [e for e in all_errors if e.severity != "info"]
    info_items = [e for e in all_errors if e.severity == "info"]

    by_doi: dict[str, list[Error]] = {}
    for e in actionable:
        by_doi.setdefault(e.doi_key, []).append(e)

    for doi_key in sorted(by_doi):
        doi_errors = by_doi[doi_key]
        n_err = sum(1 for e in doi_errors if e.severity == "error")
        n_warn = sum(1 for e in doi_errors if e.severity == "warning")
        print(f"\n{'─' * 90}")
        print(f"DOI: {doi_key}  ({n_err} errors, {n_warn} warnings)")
        print(f"{'─' * 90}")

        for e in doi_errors:
            marker = "ERROR" if e.severity == "error" else "WARN "
            print(f"  [{marker}] {e.mpea_formula:<35} {e.category:>8} | {e.detail}")

    # Summary table
    print(f"\n{'=' * 90}")
    print("SUMMARY BY DOI")
    print(f"{'=' * 90}")
    print(f"{'DOI key':<50} {'Errors':>7} {'Warnings':>9}")
    print("-" * 70)
    total_e = 0
    total_w = 0
    for doi_key in sorted(by_doi):
        doi_errors = by_doi[doi_key]
        n_err = sum(1 for e in doi_errors if e.severity == "error")
        n_warn = sum(1 for e in doi_errors if e.severity == "warning")
        print(f"{doi_key:<50} {n_err:>7} {n_warn:>9}")
        total_e += n_err
        total_w += n_warn
    print("-" * 70)
    print(f"{'TOTAL':<50} {total_e:>7} {total_w:>9}")

    # Phase error breakdown
    phase_errors = [e for e in all_errors if e.category == "phase" and e.severity == "error"]
    if phase_errors:
        print(f"\n{'=' * 90}")
        print("PHASE ERRORS (details)")
        print(f"{'=' * 90}")
        for e in phase_errors:
            print(f"  {e.doi_key}  {e.mpea_formula:<35}")
            print(f"    Our phases:  {e.our_value}")
            print(f"    MPEA column: {e.mpea_value}")
            print(f"    {e.detail}")
            print()

    # Composition error breakdown — list every composition per DOI
    comp_errors = [e for e in all_errors if e.category == "composition"]
    if comp_errors:
        comp_by_doi: dict[str, list[Error]] = {}
        for e in comp_errors:
            comp_by_doi.setdefault(e.doi_key, []).append(e)

        print(f"\n{'=' * 90}")
        print("COMPOSITION ERRORS (details)")
        print(f"{'=' * 90}")
        for doi_key in sorted(comp_by_doi):
            errs = comp_by_doi[doi_key]
            print(f"\n  {doi_key}")

            # Gather all unique MPEA formulas and our formulas mentioned
            unmatched_mpea = [e for e in errs if e.field == "unmatched_mpea"]
            element_errs = [e for e in errs if e.field in ("missing_element", "extra_element")]
            stoich_errs = [e for e in errs if e.field == "stoichiometry"]

            if unmatched_mpea:
                print("    MPEA formulas not in our data:")
                for e in unmatched_mpea:
                    print(f"      - {e.mpea_formula}")
            if element_errs:
                print("    Element mismatches:")
                for e in element_errs:
                    print(f"      - {e.detail}")
            if stoich_errs:
                print("    Stoichiometry differences:")
                for e in stoich_errs:
                    print(f"      - {e.detail}")
            print()

    # Numeric error breakdown
    numeric_errors = [e for e in all_errors if e.category == "numeric" and e.severity == "error"]
    if numeric_errors:
        print(f"{'=' * 90}")
        print("NUMERIC ERRORS (details)")
        print(f"{'=' * 90}")
        for e in numeric_errors:
            print(f"  {e.doi_key}  {e.mpea_formula:<35}")
            print(f"    {e.detail}")
            print()

    # Missing value summary
    missing_errors = [e for e in all_errors if e.category == "missing"]
    if missing_errors:
        print(f"{'=' * 90}")
        print(f"MISSING VALUES ({len(missing_errors)} values we extracted that MPEA left blank)")
        print(f"{'=' * 90}")
        for e in missing_errors:
            print(f"  {e.doi_key}  {e.mpea_formula:<35}  {e.detail}")

    # Coverage differences (informational — not errors or warnings)
    unmatched_mpea = [e for e in actionable if e.field == "unmatched_mpea"]
    if info_items or unmatched_mpea:
        coverage_by_doi: dict[str, dict[str, list[Error]]] = {}
        for e in info_items:
            coverage_by_doi.setdefault(e.doi_key, {"ours": [], "mpea": []})["ours"].append(e)
        for e in unmatched_mpea:
            coverage_by_doi.setdefault(e.doi_key, {"ours": [], "mpea": []})["mpea"].append(e)

        print(f"\n{'=' * 90}")
        print(f"COVERAGE DIFFERENCES ({len(info_items)} ours-only, {len(unmatched_mpea)} MPEA-only)")
        print(f"{'=' * 90}")
        for doi_key in sorted(coverage_by_doi):
            groups = coverage_by_doi[doi_key]
            print(f"  {doi_key}:")
            if groups["ours"]:
                print("    Ours (not in MPEA):")
                for e in groups["ours"]:
                    print(f"      - {e.our_value}")
            if groups["mpea"]:
                print("    MPEA (not in ours):")
                for e in groups["mpea"]:
                    print(f"      - {e.mpea_value}")

    _print_csv_summary(all_errors, stats)


# Fair thresholds for determining match vs mismatch
_NUMERIC_TOLERANCE_PCT = 5.0  # values within 5% = match
_STOICH_TOLERANCE_PCT = 2.0  # stoichiometry within 2 at% = match


def _print_csv_summary(all_errors: list[Error], stats: dict[str, int]) -> None:
    """Print a compact CSV summary table for pasting into Google Sheets.

    Uses fair thresholds: numeric values within 5% and stoichiometry within
    2 at% are counted as matches, not mismatches.
    """
    from litxbench.core.utils import dict_to_csv_string

    # Phase: any phase error = mismatch (phase either matches or doesn't)
    phase_mismatches = len(
        {
            (e.doi_key, e.mpea_formula)
            for e in all_errors
            if e.category == "phase" and e.field in ("missing_phase", "extra_phase", "wrong_bcc_fcc_label")
        }
    )
    phase_compared = stats["phase_compared"]

    # Numeric: only count as mismatch if >5% difference
    numeric_mismatches = sum(
        1
        for e in all_errors
        if e.category == "numeric" and e.pct_diff is not None and e.pct_diff > _NUMERIC_TOLERANCE_PCT
    )
    numeric_compared = stats["numeric_compared"]

    # Composition: element errors always count; stoichiometry only if >2 at%
    comp_element_mismatches = len(
        [e for e in all_errors if e.category == "composition" and e.field in ("missing_element", "extra_element")]
    )
    comp_stoich_mismatches = sum(
        1
        for e in all_errors
        if e.category == "composition"
        and e.field == "stoichiometry"
        and e.pct_diff is not None
        and e.pct_diff > _STOICH_TOLERANCE_PCT
    )
    comp_compared = stats["composition_compared"]

    # Missing values in MPEA (we have data, they left it blank)
    missing_in_mpea = len([e for e in all_errors if e.category == "missing"])

    def _pct(match: int, total: int) -> str:
        return f"{match / total * 100:.1f}%" if total else "N/A"

    phase_match = phase_compared - phase_mismatches
    numeric_match = numeric_compared - numeric_mismatches
    comp_mismatch = comp_element_mismatches + comp_stoich_mismatches
    comp_match = comp_compared - comp_mismatch

    cols = [
        "overlapping_dois",
        "phase_compared",
        "phase_match",
        "phase_mismatch",
        "phase_match%",
        "numeric_compared",
        "numeric_match",
        "numeric_mismatch",
        "numeric_match%",
        "composition_compared",
        "composition_match",
        "composition_mismatch",
        "composition_match%",
        "missing_in_mpea",
    ]
    row: dict[str, str | int | float] = {
        "overlapping_dois": len({e.doi_key for e in all_errors}),
        "phase_compared": phase_compared,
        "phase_match": phase_match,
        "phase_mismatch": phase_mismatches,
        "phase_match%": _pct(phase_match, phase_compared),
        "numeric_compared": numeric_compared,
        "numeric_match": numeric_match,
        "numeric_mismatch": numeric_mismatches,
        "numeric_match%": _pct(numeric_match, numeric_compared),
        "composition_compared": comp_compared,
        "composition_match": comp_match,
        "composition_mismatch": comp_mismatch,
        "composition_match%": _pct(comp_match, comp_compared),
        "missing_in_mpea": missing_in_mpea,
    }

    print(f"\n{'=' * 90}")
    print("CSV SUMMARY (paste into Google Sheets)")
    print(
        f"  Thresholds: numeric ≤{_NUMERIC_TOLERANCE_PCT}% = match, stoichiometry ≤{_STOICH_TOLERANCE_PCT} at% = match"
    )
    print(f"{'=' * 90}")
    print(",".join(cols))
    print(dict_to_csv_string(row, cols))


if __name__ == "__main__":
    main()
