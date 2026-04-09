"""Evaluate KnowMat2 extraction results against ground truth.

Full multi-level evaluation: converts KnowMat2's JSON output into Experiment
objects and runs the same _evaluate_and_report() pipeline that zero_shot.py uses.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pymatgen.core.composition import Composition
from pymatgen.core.lattice import Lattice

from litxbench.core.enums import (
    CASTING_KINDS,
    MELTING_KINDS,
    ConfigTag,
    CrysStruct,
    ProcessKind,
    RawMaterialKind,
)
from litxbench.core.eval import normalize_process_events
from litxbench.core.formula_cleaning import LATEX_SUB_RE, UNICODE_SUBSCRIPTS
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
    ProcessEvent,
    Quantity,
    RawMaterial,
)
from litxbench.core.units import (
    HV,
    Celsius,
    GigaPascal,
    Hour,
    Kelvin,
    MegaJoulesPerMeterSquared,
    MegaPascal,
    MegaPascalSquareRootMeter,
    Micrometer,
    Millimeter,
    Minute,
    Nanometer,
    Second,
    dimensionless,
    gram_per_cm3,
    percent,
)
from litxbench.core.utils import resolve_path
from litxbench.litxalloy import papers
from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    PhaseMeasurementKind,
)
from scripts.paper.benchmarks.helpers.reporting import (
    ExtractionOutput,
    _evaluate_and_report,
    _write_results_csv,
)

# ---------------------------------------------------------------------------
# Path to KnowMat2 data
# ---------------------------------------------------------------------------

KNOWMAT2_DATA_DIR = Path.home() / "Documents/dev/KnowMat2/std_1"


# ---------------------------------------------------------------------------
# Computed/theoretical properties to skip
# ---------------------------------------------------------------------------

_SKIP_PROPERTY_NAMES = {
    "valence electron concentration",
    "mixing enthalpy",
    "mixing entropy",
    "atomic size misfit parameter",
    "omega parameter",
    "electronegativity difference",
    "average melting temperature",
    "theoretical density",
}

_SKIP_PROPERTY_SYMBOLS = {"VEC", "ΔH_mix", "S_mix", "δ", "Ω"}

# ---------------------------------------------------------------------------
# Composition parsing
# ---------------------------------------------------------------------------

# Parenthetical annotations to strip
_PAREN_ANNOTATIONS = re.compile(
    r"\s*\("
    r"(?:equiatomic|at%|at\.%|wt\.%|wt%|nominally equiatomic[^)]*|nominal[^)]*|medium-entropy[^)]*|high-entropy[^)]*|Cantor[^)]*|[A-Z]\d+)"
    r"\)\s*",
    re.IGNORECASE,
)

# Dash annotations to strip: " — as-cast EHEA", " — DPHL660"
_DASH_ANNOTATION = re.compile(r"\s*[—–-]\s+.*$")

# Element-list notation: "Fe 35.1 wt.%, Mn 31.1 wt.%, ..."
_ELEMENT_LIST_PATTERN = re.compile(r"^([A-Z][a-z]?)\s+([\d.]+)\s*(?:wt\.?%|at\.?%)")

# Extract inner composition from phase descriptions like
# "σ phase (Cr50.8Fe19.1... at.%) in FeCoCrNiMo HEA"
_PHASE_INNER_COMP = re.compile(r"\(([A-Z][A-Za-z0-9.]+(?:[A-Z][a-z]?[\d.]*)+)\s*(?:at\.?%|wt\.?%)\)")

# Coating descriptions: "CoCrFeNi + 10 wt.% WC ..."
_COATING_PATTERN = re.compile(r"^([A-Z][A-Za-z0-9.]+)\s*\+")

# Inline wt% in description: "Inconel 718 ... Ni balance; Cr 17.96 wt%; Fe 18.72 wt%; ..."
_INLINE_WT_PATTERN = re.compile(r"([A-Z][a-z]?)\s+([\d.]+)\s*wt%")

# Skip patterns for unparseable names
_SKIP_PATTERNS = {"σ", "Q235", "substrate", "No materials"}


def clean_knowmat2_composition(raw: str) -> str | None:
    """Clean a KnowMat2 composition string for pymatgen parsing.

    Returns None if the string is fundamentally unparseable.
    """
    # Quick reject
    for pat in _SKIP_PATTERNS:
        if pat in raw:
            return None

    # Handle element-list notation: "Fe 35.1 wt.%, Mn 31.1 wt.%, ..."
    if _ELEMENT_LIST_PATTERN.match(raw):
        parts = re.findall(r"([A-Z][a-z]?)\s+([\d.]+)\s*(?:wt\.?%|at\.?%)", raw)
        if parts:
            # Filter out zero-amount elements (e.g. "Ti 0.0 wt.%")
            parts = [(el, amt) for el, amt in parts if float(amt) > 0]
            formula = "".join(f"{el}{amt}" for el, amt in parts)
            return formula

    # Handle Inconel-style compositions with inline wt%: "Inconel 718 ... Cr 17.96 wt%; ..."
    if "Inconel" in raw or ("balance" in raw.lower() and "wt%" in raw):
        parts = _INLINE_WT_PATTERN.findall(raw)
        if parts:
            # Filter out zero amounts
            parts = [(el, amt) for el, amt in parts if float(amt) > 0]
            formula = "".join(f"{el}{amt}" for el, amt in parts)
            return formula

    # Check for phase inner composition: "σ phase (Cr50.8Fe19.1... at.%) in ..."
    inner_match = _PHASE_INNER_COMP.search(raw)
    if inner_match:
        return inner_match.group(1)

    # Try coating pattern: "CoCrFeNi + 10 wt.% WC ..."
    coating_match = _COATING_PATTERN.match(raw)
    has_plus = "+" in raw
    if has_plus and coating_match:
        candidate = coating_match.group(1).strip()
        # Only use the base alloy if the full string is clearly a coating
        if "wt" in raw.lower() or "coating" in raw.lower():
            raw = candidate

    # Strip parenthetical annotations
    name = _PAREN_ANNOTATIONS.sub("", raw).strip()

    # Strip dash annotations
    name = _DASH_ANNOTATION.sub("", name).strip()

    # Strip trailing parenthetical e.g. "(ordered)"
    name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip()

    # Strip LaTeX subscript braces
    name = LATEX_SUB_RE.sub(r"\1", name)
    name = name.replace("{", "").replace("}", "").replace("_", "")

    # Unicode subscripts
    name = name.translate(UNICODE_SUBSCRIPTS)

    # Strip trailing descriptors like "high-entropy alloy coating on Q235 steel"
    name = re.sub(r"\s+(?:high-entropy|HEA|coating|on\s+).*$", "", name, flags=re.IGNORECASE).strip()

    # Strip "FCC matrix", "δ-phase" etc prefixes
    name = re.sub(r"^(?:FCC|BCC|HCP|σ)\s+(?:matrix|phase)\s*", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"^δ-phase\s*", "", name).strip()

    if not name:
        return None

    # Strip trailing condition descriptors: ", DPHL660 condition", ", as-cast", etc.
    name = re.sub(r",\s+\w+.*$", "", name).strip()

    # Final reject for non-formula characters
    if any(c in name for c in [":", ",", ";"]):
        return None

    return name


def try_parse_knowmat2_composition(raw: str) -> Composition | None:
    """Attempt to parse a KnowMat2 composition string.

    For percentage-based compositions (num_atoms > 50), returns the
    fractional composition to avoid validation issues with sums != 100.
    """
    cleaned = clean_knowmat2_composition(raw)
    if cleaned is None:
        return None
    try:
        comp = Composition(cleaned)
        # Normalize percentage-based compositions to fractional form
        if comp.num_atoms > 50:
            comp = comp.fractional_composition
        return comp
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Processing conditions -> ProcessEvent list
# ---------------------------------------------------------------------------

# Keyword -> ProcessKind mapping (checked in order, specific before generic)
_PROCESS_KEYWORD_MAP: list[tuple[list[str], ProcessKind]] = [
    (["arc melt", "arc-melt"], ProcessKind.ArcMelting),
    (["induction melt"], ProcessKind.InductionMelting),
    (["suction-cast", "suction cast"], ProcessKind.SuctionCasting),
    (["drop-cast", "drop cast"], ProcessKind.DropCasting),
    (["gravity cast"], ProcessKind.GravityCasting),
    (["cold-roll", "cold roll"], ProcessKind.ColdRolling),
    (["cold-forg"], ProcessKind.ColdForging),
    (["hot-roll", "hot roll"], ProcessKind.HotRolling),
    (["non-isothermal anneal"], ProcessKind.Annealing),
    (["anneal"], ProcessKind.Annealing),
    (["homogeniz"], ProcessKind.Homogenization),
    (["water quench", "ice water"], ProcessKind.WaterQuenching),
    (["ball mill", "planetary mill", "mechanical alloying"], ProcessKind.MechanicalAlloying),
    (["spark plasma sinter", "sps"], ProcessKind.SparkPlasmaSintering),
    (["gas atomiz"], ProcessKind.GasAtomization),
    (["hot extru"], ProcessKind.HotExtrusion),
    (["hot compress", "hot press"], ProcessKind.HotPressingSintering),
    (["friction stir"], ProcessKind.FrictionStirProcessing),
    (["bridgman", "directional solidif"], ProcessKind.DirectionalSolidification),
    (["edm", "electrical discharge"], ProcessKind.ElectricalDischargeMachining),
    (["sinter"], ProcessKind.SparkPlasmaSintering),
    # Generic cast last (only if not already matched by a specific cast)
    (["cast"], ProcessKind.AsCast),
]

_TEMP_CELSIUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*°C")
_TEMP_KELVIN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*K\b")
_DUR_HOUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*h\b")
_DUR_MIN_RE = re.compile(r"(\d+(?:\.\d+)?)\s*min")
_DUR_SEC_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s\b")


def _extract_temperature(clause: str) -> Quantity | None:
    """Extract a temperature from a processing clause."""
    m = _TEMP_CELSIUS_RE.search(clause)
    if m:
        return Quantity(value=float(m.group(1)), unit=Celsius)
    m = _TEMP_KELVIN_RE.search(clause)
    if m:
        return Quantity(value=float(m.group(1)), unit=Kelvin)
    return None


def _extract_duration(clause: str) -> Quantity | None:
    """Extract a duration from a processing clause."""
    m = _DUR_HOUR_RE.search(clause)
    if m:
        return Quantity(value=float(m.group(1)), unit=Hour)
    m = _DUR_MIN_RE.search(clause)
    if m:
        return Quantity(value=float(m.group(1)), unit=Minute)
    m = _DUR_SEC_RE.search(clause)
    if m:
        return Quantity(value=float(m.group(1)), unit=Second)
    return None


def parse_processing_conditions(text: str) -> list[ProcessEvent]:
    """Parse a KnowMat2 processing_conditions string into ProcessEvents.

    Splits by semicolons, matches each clause against keyword patterns.
    """
    if not text:
        return []

    clauses = [c.strip() for c in text.split(";") if c.strip()]
    raw_events: list[ProcessEvent] = []

    for clause in clauses:
        clause_lower = clause.lower()
        matched_kind: ProcessKind | None = None

        for keywords, kind in _PROCESS_KEYWORD_MAP:
            for kw in keywords:
                if kw.lower() in clause_lower:
                    matched_kind = kind
                    break
            if matched_kind is not None:
                break

        if matched_kind is None:
            continue

        temperature = _extract_temperature(clause)
        duration = _extract_duration(clause)

        raw_events.append(
            ProcessEvent(
                kind=matched_kind,
                description=clause,
                temperature=temperature,
                duration=duration,
            )
        )

    # Post-processing: melting-followed-by-casting rule
    process_events: list[ProcessEvent] = []
    for i, event in enumerate(raw_events):
        process_events.append(event)
        if event.kind in MELTING_KINDS:
            next_is_casting = i + 1 < len(raw_events) and raw_events[i + 1].kind in CASTING_KINDS
            if not next_is_casting:
                process_events.append(ProcessEvent(kind=ProcessKind.CastingUnspecified))

    # Drop cooling after sintering
    _SINTERING_KINDS = {ProcessKind.SparkPlasmaSintering, ProcessKind.HotPressingSintering}
    filtered_events: list[ProcessEvent] = []
    for i, event in enumerate(process_events):
        if event.kind == ProcessKind.WaterQuenching and i > 0 and process_events[i - 1].kind in _SINTERING_KINDS:
            continue
        filtered_events.append(event)

    # Prepend implicit Mixing step
    return normalize_process_events(filtered_events)


# ---------------------------------------------------------------------------
# Properties -> Measurements
# ---------------------------------------------------------------------------

def parse_unit_string(unit_str: str) -> object | None:
    """Convert a raw KnowMat2 unit string to a pint unit.

    Tries pint's parser first (handles most standard strings), then falls
    back to manual matching for the KnowMat2 formatting quirks that pint
    cannot parse (load-qualified HV, fractional exponents, ``g/cm3``, etc.).

    Returns None if the string is empty or unrecognised.
    """
    from litxbench.core.units import ureg

    if not unit_str:
        return None

    s = unit_str.strip()
    if not s:
        return None

    # ---- Fast manual checks for strings pint cannot handle ----

    # Vickers hardness with load: Hv, HV0.1, HV30, etc.
    if re.match(r"^[Hh][Vv][\d.]*$", s):
        return HV

    # Fracture toughness: MPa·m^1/2, MPa m^1/2, MPa√m, etc.
    if "MPa" in s and ("1/2" in s or "0.5" in s or "√" in s):
        return MegaPascalSquareRootMeter

    # g/cm3 (pint misreads "cm3" as a single token)
    if re.match(r"^g\s*/\s*cm3$", s):
        return gram_per_cm3

    # ---- Try pint's parser ----
    try:
        return ureg.parse_units(s)
    except Exception:
        pass

    # ---- Normalise and retry ----
    # middot → space, superscript digits → ascii
    norm = (
        s.replace("·", " ")
        .replace("⋅", " ")
    )
    if norm != s:
        try:
            return ureg.parse_units(norm)
        except Exception:
            pass

    return None

# ---------------------------------------------------------------------------
# standard_property_name → measurement kind (1:1 with properties.json)
# ---------------------------------------------------------------------------

_STD_NAME_TO_KIND: dict[str, str] = {
    "vickers hardness": AlloyMeasurementKind.vickers_hardness,
    "berkovich hardness": AlloyMeasurementKind.berkovich_hardness,
    "density": AlloyMeasurementKind.density,
    "pugh ductility ratio": AlloyMeasurementKind.pugh_ductility_ratio,
    "yield strength in tension": AlloyMeasurementKind.yield_strength_tension,
    "ultimate strain in tension": AlloyMeasurementKind.ultimate_strain_tension,
    "ultimate tensile strength": AlloyMeasurementKind.ultimate_tensile_strength,
    "fracture strain in tension": AlloyMeasurementKind.fracture_strain_tension,
    "fracture strength in tension": AlloyMeasurementKind.fracture_strength_tension,
    "strain hardening exponent in tension": AlloyMeasurementKind.strain_hardening_exponent_tension,
    "poissons ratio in tension": AlloyMeasurementKind.poissons_ratio_tension,
    "fracture energy in tension": AlloyMeasurementKind.fracture_energy_tension,
    "true stress in tension": AlloyMeasurementKind.true_stress_tension,
    "elastic limit in tension": AlloyMeasurementKind.elastic_limit_tension,
    "yield strength in compression": AlloyMeasurementKind.yield_strength_compression,
    "ultimate strain in compression": AlloyMeasurementKind.ultimate_strain_compression,
    "ultimate compressive strength": AlloyMeasurementKind.ultimate_compressive_strength,
    "fracture strain in compression": AlloyMeasurementKind.fracture_strain_compression,
    "fracture strength in compression": AlloyMeasurementKind.fracture_strength_compression,
    "strain hardening exponent in compression": AlloyMeasurementKind.strain_hardening_exponent_compression,
    "poissons ratio in compression": AlloyMeasurementKind.poissons_ratio_compression,
    "fracture energy in compression": AlloyMeasurementKind.fracture_energy_compression,
    "true stress in compression": AlloyMeasurementKind.true_stress_compression,
    "elastic limit in compression": AlloyMeasurementKind.elastic_limit_compression,
    "youngs modulus": AlloyMeasurementKind.youngs_modulus,
    "fracture toughness": AlloyMeasurementKind.fracture_toughness,
    "work of fracture": AlloyMeasurementKind.work_of_fracture,
    "crystallite size": AlloyMeasurementKind.crystallite_size,
    "lattice strain": AlloyMeasurementKind.lattice_strain,
    "volume fraction": PhaseMeasurementKind.volume_fraction,
    "length": PhaseMeasurementKind.length,
    "grain size": PhaseMeasurementKind.grain_size,
    "phase size": PhaseMeasurementKind.phase_size,
    "melting point": AlloyMeasurementKind.melting_point,
    "solidus temperature": AlloyMeasurementKind.solidus,
    "liquidus temperature": AlloyMeasurementKind.liquidus,
}

# Kinds whose unit depends on whether the paper reports GPa or MPa
_STRESS_KINDS = {
    AlloyMeasurementKind.yield_strength_tension,
    AlloyMeasurementKind.yield_strength_compression,
    AlloyMeasurementKind.ultimate_tensile_strength,
    AlloyMeasurementKind.ultimate_compressive_strength,
    AlloyMeasurementKind.fracture_strength_tension,
    AlloyMeasurementKind.fracture_strength_compression,
    AlloyMeasurementKind.true_stress_tension,
    AlloyMeasurementKind.true_stress_compression,
    AlloyMeasurementKind.elastic_limit_tension,
    AlloyMeasurementKind.elastic_limit_compression,
}

# Kinds with a fixed, known unit
_FIXED_UNIT_KINDS: dict[str, object] = {
    AlloyMeasurementKind.vickers_hardness: HV,
    AlloyMeasurementKind.pugh_ductility_ratio: dimensionless,
    AlloyMeasurementKind.poissons_ratio_tension: dimensionless,
    AlloyMeasurementKind.poissons_ratio_compression: dimensionless,
    AlloyMeasurementKind.strain_hardening_exponent_tension: dimensionless,
    AlloyMeasurementKind.strain_hardening_exponent_compression: dimensionless,
    AlloyMeasurementKind.fracture_energy_tension: MegaJoulesPerMeterSquared,
    AlloyMeasurementKind.fracture_energy_compression: MegaJoulesPerMeterSquared,
    AlloyMeasurementKind.work_of_fracture: MegaJoulesPerMeterSquared,
    AlloyMeasurementKind.youngs_modulus: GigaPascal,
    AlloyMeasurementKind.fracture_toughness: MegaPascalSquareRootMeter,
    AlloyMeasurementKind.crystallite_size: Nanometer,
    AlloyMeasurementKind.ultimate_strain_tension: percent,
    AlloyMeasurementKind.ultimate_strain_compression: percent,
    AlloyMeasurementKind.fracture_strain_tension: percent,
    AlloyMeasurementKind.fracture_strain_compression: percent,
    AlloyMeasurementKind.lattice_strain: percent,
    PhaseMeasurementKind.volume_fraction: percent,
}

_SIZE_KINDS = {
    PhaseMeasurementKind.grain_size,
    PhaseMeasurementKind.phase_size,
    PhaseMeasurementKind.length,
}

_TEMP_KINDS = {
    AlloyMeasurementKind.melting_point,
    AlloyMeasurementKind.solidus,
    AlloyMeasurementKind.liquidus,
}

# Default unit per kind — used when the unit string is empty or unparseable.
_DEFAULT_UNIT: dict[str, object] = {
    **{k: MegaPascal for k in _STRESS_KINDS},
    **_FIXED_UNIT_KINDS,
    AlloyMeasurementKind.berkovich_hardness: HV,
    AlloyMeasurementKind.density: gram_per_cm3,
    **{k: Micrometer for k in _SIZE_KINDS},
    **{k: Celsius for k in _TEMP_KINDS},
}


def _resolve_unit(kind: str, unit_str: str) -> object | None:
    """Resolve the pint unit for a measurement kind given the raw unit string.

    Parses the raw unit string via ``parse_unit_string`` first, then falls
    back to a kind-specific default when the string is absent or unparseable.
    """
    parsed = parse_unit_string(unit_str)
    if parsed is not None:
        return parsed
    return _DEFAULT_UNIT.get(kind)


def _is_compression(prop: dict) -> bool:
    """Check if a measurement condition indicates compression."""
    cond = (prop.get("measurement_condition") or "").lower()
    name = (prop.get("property_name") or "").lower()
    return "compress" in cond or "compress" in name


def _map_property_name_to_kind(prop: dict) -> tuple[str, object] | None:
    """Map a KnowMat2 property to (measurement kind, unit).

    Uses ``standard_property_name`` as the primary lookup (1:1 with
    properties.json → litxbench enums).  Falls back to fuzzy
    ``property_name`` matching only when ``standard_property_name`` is
    absent or not recognised.

    Returns None for properties that should be skipped.
    """
    std_name = (prop.get("standard_property_name") or "").strip().lower()
    name = (prop.get("property_name") or "").lower()
    symbol = (prop.get("property_symbol") or "").strip()
    unit_str = prop.get("unit") or ""

    # Skip computed/theoretical properties
    for skip_name in _SKIP_PROPERTY_NAMES:
        if skip_name in name:
            return None
    if symbol in _SKIP_PROPERTY_SYMBOLS:
        return None

    # ------- Primary: standard_property_name lookup -------
    if std_name in _STD_NAME_TO_KIND:
        kind = _STD_NAME_TO_KIND[std_name]
        unit = _resolve_unit(kind, unit_str)
        if unit is not None:
            return (kind, unit)

    # ------- Fallback: fuzzy property_name matching -------
    # (only reached when standard_property_name is missing or unrecognised)

    # Yield strength
    if any(kw in name for kw in ["yield strength", "proof stress", "yield stress"]) or symbol in (
        "Rp0.2",
        "σ_y",
        "σy",
    ):
        kind = (
            AlloyMeasurementKind.yield_strength_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.yield_strength_tension
        )
        return (kind, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Elastic limit
    if "elastic limit" in name:
        kind = (
            AlloyMeasurementKind.elastic_limit_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.elastic_limit_tension
        )
        return (kind, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Ultimate tensile strength
    if any(kw in name for kw in ["ultimate tensile strength", "tensile strength"]) or symbol in ("Rm", "UTS", "σ_UTS"):
        return (AlloyMeasurementKind.ultimate_tensile_strength, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Ultimate compressive strength
    if "ultimate compressive strength" in name or "compressive strength" in name or symbol == "UCS":
        return (AlloyMeasurementKind.ultimate_compressive_strength, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Fracture strength
    if "fracture strength" in name or "breaking stress" in name or "rupture strength" in name:
        kind = (
            AlloyMeasurementKind.fracture_strength_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.fracture_strength_tension
        )
        return (kind, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Fracture strain compression
    if "fracture strain" in name and _is_compression(prop):
        return (AlloyMeasurementKind.fracture_strain_compression, percent)

    # Total elongation / fracture strain (tension)
    if any(
        kw in name
        for kw in [
            "total elongation",
            "elongation to failure",
            "elongation at fracture",
            "fracture strain",
            "elongation to fracture",
            "tensile ductility",
            "strain to failure",
            "strain at failure",
        ]
    ) or (symbol == "A" and unit_str == "%"):
        return (AlloyMeasurementKind.fracture_strain_tension, percent)

    # Standalone "elongation"
    if name.startswith("elongation") and "uniform" not in name:
        return (AlloyMeasurementKind.fracture_strain_tension, percent)

    # Ultimate strain / compressive ductility
    if "ultimate strain" in name or "compressive ductility" in name:
        kind = (
            AlloyMeasurementKind.ultimate_strain_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.ultimate_strain_tension
        )
        return (kind, percent)

    # Strain hardening exponent
    if "strain hardening" in name:
        kind = (
            AlloyMeasurementKind.strain_hardening_exponent_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.strain_hardening_exponent_tension
        )
        return (kind, dimensionless)

    # Poisson's ratio
    if "poisson" in name:
        kind = (
            AlloyMeasurementKind.poissons_ratio_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.poissons_ratio_tension
        )
        return (kind, dimensionless)

    # Fracture energy
    if "fracture energy" in name:
        kind = (
            AlloyMeasurementKind.fracture_energy_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.fracture_energy_tension
        )
        return (kind, MegaJoulesPerMeterSquared)

    # True stress
    if "true stress" in name:
        kind = (
            AlloyMeasurementKind.true_stress_compression
            if _is_compression(prop)
            else AlloyMeasurementKind.true_stress_tension
        )
        return (kind, GigaPascal if unit_str == "GPa" else MegaPascal)

    # Young's modulus
    if any(kw in name for kw in ["young's modulus", "elastic modulus", "youngs modulus"]) or (
        symbol == "E" and unit_str == "GPa"
    ):
        return (AlloyMeasurementKind.youngs_modulus, GigaPascal)

    # Hardness
    if "berkovich" in name:
        return (AlloyMeasurementKind.berkovich_hardness, GigaPascal if unit_str == "GPa" else HV)
    if "vickers" in name or "hardness" in name or symbol.startswith("HV"):
        return (AlloyMeasurementKind.vickers_hardness, HV)

    # Pugh ductility ratio
    if "pugh" in name or "ductility ratio" in name:
        return (AlloyMeasurementKind.pugh_ductility_ratio, dimensionless)

    # Fracture toughness
    if "fracture toughness" in name or symbol in ("KIC", "K_IC"):
        return (AlloyMeasurementKind.fracture_toughness, MegaPascalSquareRootMeter)

    # Work of fracture
    if "work of fracture" in name:
        return (AlloyMeasurementKind.work_of_fracture, MegaJoulesPerMeterSquared)

    # Density
    if name == "density" and parse_unit_string(unit_str) == gram_per_cm3:
        return (AlloyMeasurementKind.density, gram_per_cm3)

    # Grain size
    if ("grain size" in name or "grain diameter" in name) and "crystallite" not in name:
        return (PhaseMeasurementKind.grain_size, parse_unit_string(unit_str) or Micrometer)

    # Phase size / precipitate size
    if "phase size" in name or "precipitate size" in name:
        return (PhaseMeasurementKind.phase_size, parse_unit_string(unit_str) or Micrometer)

    # Length / thickness
    if name == "length" or "thickness" in name:
        return (PhaseMeasurementKind.length, parse_unit_string(unit_str) or Micrometer)

    # Volume fraction
    if "volume fraction" in name:
        return (PhaseMeasurementKind.volume_fraction, percent)

    # Crystallite size
    if "crystallite size" in name:
        return (AlloyMeasurementKind.crystallite_size, Nanometer)

    # Lattice strain
    if "lattice strain" in name:
        return (AlloyMeasurementKind.lattice_strain, percent)

    # Melting point
    if "melting point" in name or "melting temperature" in name:
        return (AlloyMeasurementKind.melting_point, Kelvin if unit_str == "K" else Celsius)

    # Solidus
    if "solidus" in name:
        return (AlloyMeasurementKind.solidus, Kelvin if unit_str == "K" else Celsius)

    # Liquidus
    if "liquidus" in name:
        return (AlloyMeasurementKind.liquidus, Kelvin if unit_str == "K" else Celsius)

    # Not a recognized property
    return None


def _parse_value(prop: dict) -> float | str | None:
    """Extract a numeric value from a KnowMat2 property dict.

    Returns None if the value should be skipped.
    """
    value_type = prop.get("value_type", "")
    value = prop.get("value")
    value_numeric = prop.get("value_numeric")

    # Skip missing values
    if value_type == "missing" or value is None:
        return None

    # Skip qualitative non-numeric values
    if value_type == "qualitative":
        # Check if value is numeric-ish (could have ~ prefix)
        raw = str(value).strip()
        # Strip leading ~ or ≈
        cleaned = re.sub(r"^[~≈]\s*", "", raw)
        try:
            float(cleaned)
        except (ValueError, TypeError):
            return None
        # Qualitative with numeric value -> prepend ~
        return f"~{cleaned}"

    # Approximate values -> preserve ~ qualifier
    if value_type == "approximate":
        if value_numeric is not None and value_numeric != 0.0:
            return f"~{value_numeric}"
        if value is not None:
            raw = str(value).strip()
            cleaned = re.sub(r"^[~≈]\s*", "", raw)
            try:
                return f"~{float(cleaned)}"
            except (ValueError, TypeError):
                pass

    # Exact or other numeric types
    if value_numeric is not None and value_numeric != 0.0:
        return value_numeric

    # Try parsing the string value
    if value is not None:
        raw = str(value).strip()
        # Handle ≈ prefix
        raw = raw.replace("≈", "~")
        try:
            return float(raw)
        except (ValueError, TypeError):
            # Try with ~ prefix
            if raw.startswith("~"):
                return raw
            return None

    return None


def map_properties_to_measurements(
    properties: list[dict],
) -> tuple[list[Measurement], list[GlobalLatticeParam]]:
    """Convert KnowMat2 properties to Measurement and GlobalLatticeParam objects."""
    measurements: list[Measurement] = []
    lattice_params: list[GlobalLatticeParam] = []
    seen_kinds: set[str] = set()

    for prop in properties:
        name = (prop.get("property_name") or "").lower()
        symbol = (prop.get("property_symbol") or "").strip()
        unit_str = prop.get("unit") or ""
        value_type = prop.get("value_type", "")

        # Skip missing
        if value_type == "missing":
            continue

        # Handle lattice parameter
        if (symbol == "a" and unit_str == "Å") or "lattice parameter" in name:
            value_numeric = prop.get("value_numeric")
            if value_numeric and value_numeric > 0:
                # Parse value, stripping parenthetical uncertainty e.g. "3.4089(1)"
                raw_val = str(prop.get("value", ""))
                clean_val = re.sub(r"\(\d+\)", "", raw_val).strip()
                try:
                    a = float(clean_val)
                except (ValueError, TypeError):
                    a = float(value_numeric)

                # Try to detect crystal structure from property name or characterisation context
                struct = None
                if "bcc" in name.lower():
                    struct = CrysStruct.BCC
                elif "fcc" in name.lower():
                    struct = CrysStruct.FCC
                elif "hcp" in name.lower():
                    struct = CrysStruct.HCP

                lattice_params.append(
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(a)),
                        struct=struct,
                    )
                )
            continue

        # Handle phase fraction
        if "phase fraction" in name:
            value = _parse_value(prop)
            if value is not None:
                lattice_params.append(
                    GlobalLatticeParam(
                        phase_fraction=Quantity(value=value, unit=percent),
                    )
                )
            continue

        # Map property to measurement kind
        mapping = _map_property_name_to_kind(prop)
        if mapping is None:
            continue

        kind_str, unit = mapping

        # Get value
        value = _parse_value(prop)
        if value is None:
            continue

        # Deduplicate: skip if we already have this kind+value
        # (KnowMat2 sometimes reports the same measurement multiple times
        # with different conditions; since the eval doesn't compare conditions,
        # keeping duplicates would just create false positives.)
        kind_key = str(kind_str)
        dedup_key = f"{kind_key}:{value}"
        if dedup_key in seen_kinds:
            continue
        seen_kinds.add(dedup_key)

        measurements.append(
            Measurement(
                kind=kind_str,
                value=value,
                unit=unit,
            )
        )

    return measurements, lattice_params


# ---------------------------------------------------------------------------
# Crystal structure parsing from characterisation
# ---------------------------------------------------------------------------

_STRUCT_KEYWORDS: list[tuple[str, CrysStruct]] = [
    ("B2", CrysStruct.B2),
    ("L12", CrysStruct.L12),
    ("L10", CrysStruct.L10),
    ("C14", CrysStruct.C14),
    ("C15", CrysStruct.C15),
    ("D019", CrysStruct.D019),
    ("FCC", CrysStruct.FCC),
    ("BCC", CrysStruct.BCC),
    ("HCP", CrysStruct.HCP),
    ("amorphous", CrysStruct.Amorphous),
]

_CONFIG_KEYWORDS: list[tuple[str, ConfigTag]] = [
    ("dendrit", ConfigTag.Dendrite),
    ("lamellar", ConfigTag.Lamellar),
    ("equiaxed", ConfigTag.Equiaxed),
    ("columnar", ConfigTag.Columnar),
    ("eutectic", ConfigTag.Eutectic),
    # Precipitate requires a 'within' reference that KnowMat2 doesn't provide,
    # so skip it to avoid validation errors.
    ("twin", ConfigTag.Twin),
    ("lath", ConfigTag.Lath),
]


def parse_characterisation(char_dict: dict | None) -> tuple[list[CrysStruct], list[ConfigTag]]:
    """Extract crystal structures and config tags from characterisation text."""
    if not char_dict:
        return [], []

    structs: list[CrysStruct] = []
    tags: list[ConfigTag] = []
    seen_structs: set[CrysStruct] = set()
    seen_tags: set[ConfigTag] = set()

    # Combine all characterisation text
    all_text = " ".join(str(v) for v in char_dict.values() if v)

    for keyword, struct in _STRUCT_KEYWORDS:
        if keyword.lower() in all_text.lower() and struct not in seen_structs:
            structs.append(struct)
            seen_structs.add(struct)

    for keyword, tag in _CONFIG_KEYWORDS:
        if keyword.lower() in all_text.lower() and tag not in seen_tags:
            tags.append(tag)
            seen_tags.add(tag)

    return structs, tags


# ---------------------------------------------------------------------------
# Convert a single KnowMat2 composition entry to an Experiment
# ---------------------------------------------------------------------------


def convert_knowmat2_entry(entry: dict) -> Experiment | None:
    """Convert a single KnowMat2 composition entry to an Experiment.

    Returns None if the composition cannot be parsed.
    """
    raw_comp = entry.get("composition", "")
    composition = try_parse_knowmat2_composition(raw_comp)
    if composition is None:
        print(f"  Skipping unparseable composition: {raw_comp!r}")
        return None

    # Parse processing conditions
    process_events = parse_processing_conditions(entry.get("processing_conditions", ""))

    # Map properties to measurements
    properties = entry.get("properties_of_composition", [])
    measurements_list, lattice_params = map_properties_to_measurements(properties)

    # Parse crystal structures and config tags from characterisation
    structs, config_tags = parse_characterisation(entry.get("characterisation"))

    # Attach crystal structures to lattice params where appropriate
    if structs and lattice_params:
        for lp in lattice_params:
            if lp.lattice is not None and lp.struct is None and structs:
                lp.struct = structs[0]  # Assign primary struct

    # Build configurations from characterisation
    configurations: list[Configuration] = []
    for struct in structs:
        configurations.append(Configuration(struct=struct))

    # Attach config tags to the first configuration, or create a standalone one
    if config_tags:
        if configurations:
            configurations[0].tags = set(config_tags)
        else:
            configurations.append(Configuration(tags=set(config_tags)))

    # Keep GLPs as-is (some ground truth uses standalone GLPs, some puts
    # lattice inside Configuration — keeping both avoids hurting GLP matching)
    attached_structs = {lp.struct for lp in lattice_params if lp.struct is not None}
    for struct in structs:
        if struct not in attached_structs:
            lattice_params.append(GlobalLatticeParam(struct=struct))

    # Build material measurements
    material_measurements: list = [CompMeasurement(composition, validate_composition=False)]
    material_measurements.extend(measurements_list)
    material_measurements.extend(lattice_params)
    material_measurements.extend(configurations)

    raw_materials = {"elements": RawMaterial(kind=RawMaterialKind.Unspecified)}

    try:
        material = Material(measurements=material_measurements)
        experiment = Experiment(
            raw_materials=raw_materials,
            synthesis_groups=process_events,
            output_materials=[material],
        )
    except ValueError as e:
        print(f"  Validation error for {raw_comp!r}: {e}")
        return None

    return experiment


# ---------------------------------------------------------------------------
# Load all KnowMat2 extractions
# ---------------------------------------------------------------------------


def load_all_knowmat2_extractions() -> dict[str, list[Experiment]]:
    """Load all KnowMat2 extraction JSONs and convert to Experiments."""
    result: dict[str, list[Experiment]] = {}

    if not KNOWMAT2_DATA_DIR.exists():
        print(f"ERROR: KnowMat2 data directory not found: {KNOWMAT2_DATA_DIR}")
        sys.exit(1)

    for d in sorted(KNOWMAT2_DATA_DIR.iterdir()):
        if not d.is_dir() or not d.name.startswith("doi_"):
            continue

        extraction_file = d / f"{d.name}_extraction.json"
        if not extraction_file.exists():
            continue

        with open(extraction_file) as f:
            data = json.load(f)

        compositions = data.get("compositions", [])
        experiments: list[Experiment] = []
        seen_formulas: set[str] = set()

        for entry in compositions:
            exp = convert_knowmat2_entry(entry)
            if exp is not None:
                # Deduplicate by composition formula
                comp = exp.output_materials[0].measurements[0]
                if isinstance(comp, CompMeasurement):
                    formula = comp.composition.reduced_formula
                    if formula in seen_formulas:
                        continue
                    seen_formulas.add(formula)
                experiments.append(exp)

        if experiments:
            result[d.name] = experiments

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Load KnowMat2 data
    knowmat2_data = load_all_knowmat2_extractions()
    print(f"Loaded KnowMat2 extractions for {len(knowmat2_data)} DOIs")

    # Find overlapping DOIs with ground truth
    ground_truth_dois = set(papers.keys())
    overlapping_dois = sorted(doi for doi in knowmat2_data if doi in ground_truth_dois)

    print(f"Found {len(overlapping_dois)} overlapping DOIs out of {len(ground_truth_dois)} ground truth papers")

    if not overlapping_dois:
        print("ERROR: No overlapping DOIs found")
        sys.exit(1)

    # Wrap as ExtractionOutput
    extraction_outputs: dict[str, ExtractionOutput] = {}
    for doi in overlapping_dois:
        extraction_outputs[doi] = ExtractionOutput(experiments=knowmat2_data[doi])

    # Evaluate using existing pipeline
    output_dir = Path(resolve_path("outputs/knowmat2"))
    output_dir.mkdir(parents=True, exist_ok=True)

    doi_results, _ = _evaluate_and_report(
        model_name="knowmat2",
        dois=overlapping_dois,
        ground_truth=papers,
        extraction_outputs=extraction_outputs,
        output_dir=output_dir,
    )

    # Write per-DOI results CSV (same format as zero_shot benchmark)
    results_csv_path = output_dir / "results.csv"
    _write_results_csv(
        results_csv_path,
        overlapping_dois,
        {"knowmat2": doi_results},
        {"knowmat2": extraction_outputs},
    )
    print(f"  -> {results_csv_path}")


if __name__ == "__main__":
    main()
