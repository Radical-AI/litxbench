"""Hallucination detection for extracted experiments.

Checks whether numeric values in extracted experiments appear in the
source text (paper content).  Numbers that were extracted but cannot be
found in the original text are counted as potential hallucinations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from litxbench.core.eval import resolve_process_events
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
    Quantity,
)


@dataclass
class HallucinationResult:
    """Result of hallucination detection for a set of experiments."""

    total_numbers: int
    numbers_found: int
    numbers_not_found: int
    hallucination_rate: float  # numbers_not_found / total_numbers (0.0 if no numbers)
    not_found_values: list[float | int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Number-in-text search
# ---------------------------------------------------------------------------


def _format_number_variants(value: float | int) -> list[str]:
    """Generate string variants of a number for text search.

    For integers or whole-valued floats, produces both "450" and "450.0".
    For fractional floats, produces the compact representation (e.g. "33.3").
    """
    variants: list[str] = []

    if isinstance(value, int) or (isinstance(value, float) and value == int(value)):
        int_val = int(value)
        variants.append(str(int_val))
        variants.append(f"{int_val}.0")
    else:
        # Use :g to strip trailing zeros, e.g. 33.300 -> 33.3
        variants.append(f"{value:g}")
        # Also keep the repr form in case :g rounds differently
        plain = str(value)
        if plain not in variants:
            variants.append(plain)

    return variants


def _number_in_text(value: float | int, text: str) -> bool:
    """Check if a number appears in *text* with non-digit boundaries.

    Uses a look-behind/look-ahead so that "450" doesn't match inside
    "4500" or "1450".
    """
    for variant in _format_number_variants(value):
        escaped = re.escape(variant)
        # Not preceded or followed by a digit.
        pattern = rf"(?<!\d){escaped}(?!\d)"
        if re.search(pattern, text):
            return True
    return False


# ---------------------------------------------------------------------------
# Number extraction helpers
# ---------------------------------------------------------------------------


def _nums_from_quantity(q: Quantity | None) -> list[float | int]:
    if q is None or q.numeric_value is None:
        return []
    return [q.numeric_value]


def _nums_from_measurement(m: Measurement[Any]) -> list[float | int]:
    nums: list[float | int] = []
    if m.numeric_value is not None:
        nums.append(m.numeric_value)
    if m.uncertainty is not None:
        nums.append(m.uncertainty)
    nums.extend(_nums_from_quantity(m.temperature))
    nums.extend(_nums_from_quantity(m.pressure))
    return nums


def _nums_from_composition(comp: CompMeasurement) -> list[float | int]:
    return list(comp.composition.get_el_amt_dict().values())


def _nums_from_lattice(lat: LatticeMeasurement) -> list[float | int]:
    return list(lat.lattice.parameters)  # (a, b, c, alpha, beta, gamma)


def _nums_from_material(material: Material[Any]) -> list[float | int]:
    nums: list[float | int] = []
    for m in material.measurements:
        if isinstance(m, Configuration):
            for nested in m.measurements:
                if isinstance(nested, Measurement):
                    nums.extend(_nums_from_measurement(nested))
                elif isinstance(nested, CompMeasurement):
                    nums.extend(_nums_from_composition(nested))
                elif isinstance(nested, LatticeMeasurement):
                    nums.extend(_nums_from_lattice(nested))
        elif isinstance(m, Measurement):
            nums.extend(_nums_from_measurement(m))
        elif isinstance(m, CompMeasurement):
            nums.extend(_nums_from_composition(m))
        elif isinstance(m, LatticeMeasurement):
            nums.extend(_nums_from_lattice(m))
        elif isinstance(m, GlobalLatticeParam):
            if m.lattice is not None:
                nums.extend(_nums_from_lattice(m.lattice))
            if m.phase_fraction is not None:
                nums.extend(_nums_from_quantity(m.phase_fraction))
    return nums


def extract_all_numbers(experiments: list[Experiment[Any, Any]]) -> list[float | int]:
    """Extract all numeric values from a list of experiments.

    Includes values from measurements (value, uncertainty, temperature,
    pressure), composition element amounts, lattice parameters, phase
    fractions, and process-event temperatures/durations (resolved through
    synthesis groups).
    """
    nums: list[float | int] = []
    for exp in experiments:
        for material in exp.output_materials:
            nums.extend(_nums_from_material(material))
            # Resolved process events (with template substitution)
            events = resolve_process_events(material, exp.synthesis_group_map)
            for event in events:
                nums.extend(_nums_from_quantity(event.temperature))
                nums.extend(_nums_from_quantity(event.duration))
    return nums


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def count_hallucinations(
    experiments: list[Experiment[Any, Any]],
    text: str,
) -> HallucinationResult:
    """Count numbers in extracted experiments not found in the source text.

    Args:
        experiments: Extracted experiments to check.
        text: Source text (paper / prompt content) to search for numbers.

    Returns:
        HallucinationResult with counts and rate.
    """
    numbers = extract_all_numbers(experiments)
    total = len(numbers)

    if total == 0 or not text.strip():
        return HallucinationResult(
            total_numbers=total,
            numbers_found=0,
            numbers_not_found=0,
            hallucination_rate=0.0,
        )

    not_found: list[float | int] = []
    found = 0
    for n in numbers:
        if _number_in_text(n, text):
            found += 1
        else:
            not_found.append(n)

    return HallucinationResult(
        total_numbers=total,
        numbers_found=found,
        numbers_not_found=len(not_found),
        hallucination_rate=len(not_found) / total,
        not_found_values=not_found,
    )
