"""Tests for hallucination detection module."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from pymatgen.core.lattice import Lattice as PymatgenLattice

from litxbench.core.enums import ConfigTag, CrysStruct, ProcessKind
from litxbench.core.hallucination import (
    _format_number_variants,
    _number_in_text,
    _nums_from_material,
    count_hallucinations,
    extract_all_numbers,
)
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
    ProcessEvent,
    ProcessStep,
    Quantity,
    RawMaterial,
    RawMaterialKind,
)
from litxbench.core.units import Celsius, Hour, MegaPascal, dimensionless, percent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class MockMaterial:
    """Minimal mock that satisfies the interface expected by hallucination helpers."""

    process_steps: list[ProcessStep] | None = None
    measurements: Sequence[Any] = field(default_factory=list)


def _make_experiment(
    *,
    composition: dict[str, float],
    measurements: list | None = None,
    process_events: list[ProcessEvent] | None = None,
) -> Experiment:
    """Helper to build a valid Experiment with minimal boilerplate."""
    all_measurements = [CompMeasurement(composition)] + (measurements or [])
    if process_events is None:
        process_events = [
            ProcessEvent(kind=ProcessKind.ArcMelting),
            ProcessEvent(kind=ProcessKind.AsCast),
        ]
    return Experiment(
        raw_materials={"ingot": RawMaterial(kind=RawMaterialKind.Ingot)},
        synthesis_groups=process_events,
        output_materials=[Material(name="alloy", measurements=all_measurements)],
    )


# =========================================================================
# _format_number_variants / _number_in_text
# =========================================================================


@pytest.mark.parametrize(
    "value, expected_variants",
    [
        (450, ["450", "450.0"]),
        (1200.0, ["1200", "1200.0"]),
        (33.3, ["33.3"]),
        (0.25, ["0.25"]),
        (0, ["0"]),
    ],
)
def test_format_number_variants(value, expected_variants):
    variants = _format_number_variants(value)
    for v in expected_variants:
        assert v in variants


@pytest.mark.parametrize(
    "value, text",
    [
        (450, "The hardness was 450 HV"),
        (450, "measured 450.0 MPa"),
        (450, "450 MPa was measured"),
        (450, "hardness of 450"),
        (450, "values: 300, 450, 600"),
        (450, "hardness (450 HV)"),
        (1200, "annealed at 1200C for 24h"),
        (33.3, "composition of 33.3%"),
        (0, "reduced to 0 after cooling"),
        (1, "ratio of 1 to 3"),
    ],
    ids=lambda x: str(x)[:40],
)
def test_number_in_text_found(value, text):
    assert _number_in_text(value, text)


@pytest.mark.parametrize(
    "value, text",
    [
        (450, "The value was 4500"),
        (450, "measured 1450 MPa"),
        (450, "id=14507 was recorded"),
        (33.3, "value of 333"),
        (0, "temperature 100 K"),
        (1, "only 10 samples"),
        (450, ""),
    ],
    ids=lambda x: str(x)[:40],
)
def test_number_in_text_not_found(value, text):
    assert not _number_in_text(value, text)


# =========================================================================
# _nums_from_material – covers all measurement types via MockMaterial
# =========================================================================


class TestNumsFromMaterial:
    def test_measurement_with_all_fields(self):
        """Extracts value, uncertainty, temperature, and pressure."""
        mat = MockMaterial(measurements=[
            Measurement(
                kind="yield_strength", value=450, unit=MegaPascal,
                uncertainty=10.0,
                temperature=Quantity(value=600, unit=Celsius),
                pressure=Quantity(value=2, unit=dimensionless),
            ),
        ])
        assert set(_nums_from_material(mat)) == {450, 10.0, 600, 2}

    def test_qualified_value(self):
        """Qualified string like '~380' extracts the numeric part."""
        mat = MockMaterial(measurements=[
            Measurement(kind="hardness", value="~380", unit=MegaPascal),
        ])
        assert 380.0 in _nums_from_material(mat)

    def test_composition(self):
        mat = MockMaterial(measurements=[
            CompMeasurement({"Fe": 70, "Cr": 20, "Ni": 10}),
        ])
        assert sorted(_nums_from_material(mat)) == sorted([70.0, 20.0, 10.0])

    def test_lattice(self):
        mat = MockMaterial(measurements=[
            LatticeMeasurement(lattice=PymatgenLattice.cubic(3.56)),
        ])
        nums = _nums_from_material(mat)
        assert len(nums) == 6
        assert nums[0] == pytest.approx(3.56)

    def test_global_lattice_param_with_phase_fraction(self):
        mat = MockMaterial(measurements=[
            GlobalLatticeParam(
                lattice=LatticeMeasurement(lattice=PymatgenLattice.cubic(3.6)),
                phase_fraction=Quantity(value=60, unit=percent),
            ),
        ])
        nums = _nums_from_material(mat)
        assert 60 in nums
        assert any(pytest.approx(n, abs=0.01) == 3.6 for n in nums)

    def test_configuration_nested_measurements(self):
        mat = MockMaterial(measurements=[
            Configuration(
                name="matrix", tags={ConfigTag.Matrix}, struct=CrysStruct.FCC,
                measurements=[
                    Measurement(kind="hardness", value=250, unit=MegaPascal),
                    CompMeasurement({"Fe": 80, "Cr": 20}),
                ],
            ),
        ])
        nums = _nums_from_material(mat)
        assert 250 in nums
        assert 80.0 in nums

    def test_empty_measurements(self):
        assert _nums_from_material(MockMaterial(measurements=[])) == []


# =========================================================================
# extract_all_numbers – full Experiment including process events
# =========================================================================


class TestExtractAllNumbers:
    def test_includes_measurements_and_composition(self):
        exp = _make_experiment(
            composition={"Fe": 70, "Cr": 30},
            measurements=[Measurement(kind="hardness", value=400, unit=MegaPascal)],
        )
        nums = extract_all_numbers([exp])
        assert {400, 70.0, 30.0}.issubset(set(nums))

    def test_includes_process_event_temperature_and_duration(self):
        exp = _make_experiment(
            composition={"Fe": 100},
            process_events=[
                ProcessEvent(kind=ProcessKind.ArcMelting),
                ProcessEvent(kind=ProcessKind.AsCast),
                ProcessEvent(
                    kind=ProcessKind.Annealing,
                    temperature=Quantity(value=1100, unit=Celsius),
                    duration=Quantity(value=48, unit=Hour),
                ),
            ],
        )
        nums = extract_all_numbers([exp])
        assert 1100 in nums
        assert 48 in nums

    def test_empty_experiments(self):
        assert extract_all_numbers([]) == []


# =========================================================================
# count_hallucinations – end-to-end
# =========================================================================


class TestCountHallucinations:
    def test_all_found(self):
        exp = _make_experiment(
            composition={"Fe": 70, "Cr": 30},
            measurements=[Measurement(kind="hardness", value=450, unit=MegaPascal)],
        )
        result = count_hallucinations([exp], "The Fe70Cr30 alloy had a hardness of 450 MPa.")
        assert result.numbers_not_found == 0
        assert result.hallucination_rate == 0.0

    def test_some_hallucinated(self):
        exp = _make_experiment(
            composition={"Fe": 70, "Cr": 30},
            measurements=[Measurement(kind="hardness", value=999, unit=MegaPascal)],
        )
        result = count_hallucinations([exp], "The Fe70Cr30 alloy was tested.")
        assert 999 in result.not_found_values
        assert result.hallucination_rate > 0.0

    def test_all_hallucinated(self):
        exp = _make_experiment(
            composition={"Fe": 50, "Ni": 50},
            measurements=[Measurement(kind="hardness", value=777, unit=MegaPascal)],
        )
        result = count_hallucinations([exp], "This text has no relevant numbers at all.")
        assert result.hallucination_rate == 1.0

    def test_empty_experiments(self):
        result = count_hallucinations([], "some text with 100 numbers")
        assert result.total_numbers == 0
        assert result.hallucination_rate == 0.0

    def test_empty_or_whitespace_text_gives_zero_rate(self):
        exp = _make_experiment(composition={"Fe": 100})
        for text in ["", "   \n\t  "]:
            result = count_hallucinations([exp], text)
            assert result.hallucination_rate == 0.0
            assert result.numbers_not_found == 0

    def test_counts_are_consistent(self):
        exp = _make_experiment(
            composition={"Fe": 60, "Cr": 40},
            measurements=[
                Measurement(kind="hardness", value=500, unit=MegaPascal),
                Measurement(kind="yield_strength", value=888, unit=MegaPascal),
            ],
        )
        result = count_hallucinations([exp], "Fe60Cr40 hardness 500 MPa")
        assert result.total_numbers == result.numbers_found + result.numbers_not_found
        assert result.hallucination_rate == pytest.approx(
            result.numbers_not_found / result.total_numbers
        )

    def test_process_event_numbers_checked(self):
        exp = _make_experiment(
            composition={"Fe": 100},
            process_events=[
                ProcessEvent(kind=ProcessKind.ArcMelting),
                ProcessEvent(kind=ProcessKind.AsCast),
                ProcessEvent(
                    kind=ProcessKind.Annealing,
                    temperature=Quantity(value=1200, unit=Celsius),
                    duration=Quantity(value=24, unit=Hour),
                ),
            ],
        )
        # Text contains 1200 but NOT 24
        result = count_hallucinations([exp], "Fe100 annealed at 1200 degrees")
        assert 1200 not in result.not_found_values
        assert 24 in result.not_found_values

    def test_uncertainty_and_qualified_values(self):
        exp = _make_experiment(
            composition={"Fe": 100},
            measurements=[
                Measurement(kind="hardness", value="~380", unit=MegaPascal, uncertainty=12.5),
            ],
        )
        # Text has 380 but not 12.5
        result = count_hallucinations([exp], "Fe100 approximate hardness of 380 HV")
        assert 380.0 not in result.not_found_values
        assert 12.5 in result.not_found_values
