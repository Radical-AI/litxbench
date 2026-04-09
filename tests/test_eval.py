"""Tests for eval module."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest
from pymatgen.core.lattice import Lattice as PymatgenLattice

from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod, ValueQualifier
from litxbench.core.eval import (
    ComparableItem,
    ConfigurationMatchResult,
    ExperimentComparisonResult,
    MaterialMatchResult,
    ProcessEventAlignmentResult,
    _ancestry_context_string,
    _build_ancestry_chain,
    _build_config_map,
    _check_within_match,
    _collect_ancestry_tags,
    _comparable_item_score,
    _compare_config_field_values,
    _compare_item_values,
    _compare_process_event_values,
    _compositions_matched,
    _config_cost,
    _context_score,
    _count_comparable_items,
    _count_config_field_values,
    _count_item_values,
    _count_process_event_values,
    _extract_comparable_items,
    _extract_config_comparable_items,
    _extract_configurations,
    _kind_match_score,
    _lattice_matched,
    _qualifier_compatibility,
    _quantity_score,
    _split_kind_to_words,
    align_process_events,
    compute_multi_level_metrics,
    match_comparable_items,
    match_configurations,
    measurement_score,
    resolve_process_events,
)
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
    ProcessEvent,
    ProcessStep,
    Quantity,
    SynthesisGroup,
)
from litxbench.core.units import Celsius, MegaPascal, dimensionless, percent


@dataclass
class MockMaterial:
    """Minimal mock that satisfies the interface expected by eval functions."""

    process_steps: list[ProcessStep] | None = None
    measurements: Sequence[Any] = field(default_factory=list)


class TestResolveAutoInject:
    """Tests for auto-inject of step.inputs into the first ProcessEvent."""

    def test_step_inputs_injected_into_first_event(self):
        """Test that step.inputs are injected into the first event's inputs."""
        events = [ProcessEvent(kind="melting")]
        synth = {
            "melting": SynthesisGroup(
                name="melting",
                base_name="melting",
                template_vars=set(),
                process_events=events,
            )
        }
        material = MockMaterial(process_steps=[ProcessStep(base_name="melting", variables={}, inputs=["powder"])])

        result = resolve_process_events(material, synth)

        assert len(result) == 1
        assert result[0].inputs == ["powder"]

    def test_multiple_step_inputs_injected(self):
        """Test that multiple step inputs are all injected."""
        events = [ProcessEvent(kind="mixing")]
        synth = {
            "mixing": SynthesisGroup(
                name="mixing",
                base_name="mixing",
                template_vars=set(),
                process_events=events,
            )
        }
        material = MockMaterial(
            process_steps=[ProcessStep(base_name="mixing", variables={}, inputs=["iron", "nickel"])]
        )

        result = resolve_process_events(material, synth)

        assert len(result) == 1
        assert result[0].inputs == ["iron", "nickel"]

    def test_explicit_inputs_preserved_with_step_inputs_appended(self):
        """Test that explicit event inputs are kept and step inputs are appended."""
        events = [ProcessEvent(kind="melting", inputs=["flux"])]
        synth = {
            "melting": SynthesisGroup(
                name="melting",
                base_name="melting",
                template_vars=set(),
                process_events=events,
            )
        }
        material = MockMaterial(process_steps=[ProcessStep(base_name="melting", variables={}, inputs=["powder"])])

        result = resolve_process_events(material, synth)

        assert len(result) == 1
        assert result[0].inputs == ["flux", "powder"]

    def test_no_step_inputs_leaves_event_unchanged(self):
        """Test that events are unchanged when step has no inputs."""
        events = [ProcessEvent(kind="annealing", inputs=[])]
        synth = {
            "annealing": SynthesisGroup(
                name="annealing",
                base_name="annealing",
                template_vars=set(),
                process_events=events,
            )
        }
        material = MockMaterial(process_steps=[ProcessStep(base_name="annealing", variables={}, inputs=[])])

        result = resolve_process_events(material, synth)

        assert len(result) == 1
        assert result[0].inputs == []

    def test_only_first_event_gets_step_inputs(self):
        """Test that only the first ProcessEvent gets step.inputs injected."""
        events = [
            ProcessEvent(kind="melting"),
            ProcessEvent(kind="casting"),
        ]
        synth = {
            "melt_and_cast": SynthesisGroup(
                name="melt_and_cast",
                base_name="melt_and_cast",
                template_vars=set(),
                process_events=events,
            )
        }
        material = MockMaterial(process_steps=[ProcessStep(base_name="melt_and_cast", variables={}, inputs=["powder"])])

        result = resolve_process_events(material, synth)

        assert len(result) == 2
        assert result[0].inputs == ["powder"]
        assert result[1].inputs == []

    def test_auto_inject_with_template_substitution(self):
        """Test auto-inject works alongside template variable substitution."""
        events = [
            ProcessEvent(
                kind="melting",
                temperature=Quantity(value="[Temp]", unit=Celsius),
            )
        ]
        synth = {
            "melting": SynthesisGroup(
                name="melting[Temp]",
                base_name="melting",
                template_vars={"Temp"},
                process_events=events,
            )
        }
        material = MockMaterial(
            process_steps=[ProcessStep(base_name="melting", variables={"Temp": "1500"}, inputs=["powder"])]
        )

        result = resolve_process_events(material, synth)

        assert len(result) == 1
        assert result[0].inputs == ["powder"]
        assert result[0].temperature.value == "1500"

    def test_non_first_step_gets_inputs_via_variable_substitution(self):
        """Test that a non-first step can receive inputs via [VarName] substitution in event inputs.

        Process: powder->melting->mixing[Feedstock=ingot]
        The mixing synthesis group declares [Feedstock] as a template var
        and uses it in ProcessEvent.inputs. At resolve time the second step
        should end up with inputs=["ingot"].
        """
        process_steps = ProcessStep.parse_process_string("powder->melting->mixing[Feedstock=ingot]")
        assert process_steps[0].inputs == ["powder"]
        assert process_steps[1].inputs == []
        assert process_steps[1].variables == {"Feedstock": "ingot"}

        synth = {
            "melting": SynthesisGroup(
                name="melting",
                base_name="melting",
                template_vars=set(),
                process_events=[ProcessEvent(kind="melting")],
            ),
            "mixing": SynthesisGroup(
                name="mixing[Feedstock]",
                base_name="mixing",
                template_vars={"Feedstock"},
                process_events=[ProcessEvent(kind="mixing", inputs=["[Feedstock]"])],
            ),
        }
        material = MockMaterial(process_steps=process_steps)

        result = resolve_process_events(material, synth)

        assert len(result) == 2
        assert result[0].kind == "melting"
        assert result[0].inputs == ["powder"]
        assert result[1].kind == "mixing"
        assert result[1].inputs == ["ingot"]


# ---------------------------------------------------------------------------
# Helpers for building test objects
# ---------------------------------------------------------------------------


def _make_measurement(kind: str = "vickers_hardness", value: float = 100, unit=MegaPascal) -> Measurement:
    return Measurement(kind=kind, value=value, unit=unit)


def _make_comp(formula: str = "Fe1Ni1") -> CompMeasurement:
    return CompMeasurement(composition=formula, method=MeasurementMethod.Balance, validate_composition=False)


def _make_lattice_measurement(a=3.6, b=3.6, c=3.6, alpha=90, beta=90, gamma=90) -> LatticeMeasurement:
    return LatticeMeasurement(lattice=PymatgenLattice.from_parameters(a, b, c, alpha, beta, gamma))


def _make_global_lattice_param(
    name: str | None = None,
    lattice: LatticeMeasurement | None = None,
    struct: CrysStruct | None = None,
    phase_fraction: Quantity | None = None,
) -> GlobalLatticeParam:
    return GlobalLatticeParam(name=name, lattice=lattice, struct=struct, phase_fraction=phase_fraction)


def _make_config(
    name: str = "delta",
    measurements: list | None = None,
    tags: set | None = None,
    struct: CrysStruct | None = None,
    within: str | None = None,
) -> Configuration:
    return Configuration(name=name, measurements=measurements or [], tags=tags, struct=struct, within=within)


def _make_result(
    matched: list[MaterialMatchResult] | None = None,
    unmatched_target: list | None = None,
    unmatched_extracted: list | None = None,
) -> ExperimentComparisonResult:
    return ExperimentComparisonResult(
        matched_materials=matched or [],
        unmatched_target_materials=unmatched_target or [],
        unmatched_extracted_materials=unmatched_extracted or [],
        total_cost=0.0,
    )


def _make_material_match(
    target_measurements: list,
    extracted_measurements: list,
    num_matches: int = 0,
    process_alignment: ProcessEventAlignmentResult | None = None,
    config_match: ConfigurationMatchResult | None = None,
) -> MaterialMatchResult:
    """Build a MaterialMatchResult with a pre-computed MeasurementMatchResult."""
    target_material = MockMaterial(measurements=target_measurements)
    extracted_material = MockMaterial(measurements=extracted_measurements)

    target_items = _extract_comparable_items(target_material)
    extracted_items = _extract_comparable_items(extracted_material)
    m_result = match_comparable_items(target_items, extracted_items)

    # Auto-build config_match if not provided
    if config_match is None:
        target_configs = _extract_configurations(target_material)
        extracted_configs = _extract_configurations(extracted_material)
        if target_configs or extracted_configs:
            target_config_map = _build_config_map(target_configs)
            extracted_config_map = _build_config_map(extracted_configs)
            config_match = match_configurations(
                target_configs, extracted_configs, target_config_map, extracted_config_map
            )

    if process_alignment is None:
        process_alignment = ProcessEventAlignmentResult(
            matched_pairs=[], unmatched_target=[], unmatched_extracted=[], edit_distance=0
        )

    return MaterialMatchResult(
        target=target_material,
        extracted=extracted_material,
        cost=0.0,
        process_edit_distance=process_alignment.edit_distance,
        measurement_result=m_result,
        process_alignment=process_alignment,
        config_match=config_match,
    )


# ===========================================================================
# Test _extract_comparable_items
# ===========================================================================


class TestExtractComparableItems:
    def test_measurement(self):
        m = _make_measurement()
        material = MockMaterial(measurements=[m])
        items = _extract_comparable_items(material)
        assert len(items) == 1
        assert items[0].type == "measurement"
        assert items[0].context is None

    def test_comp_measurement(self):
        c = _make_comp("Fe1Ni1")
        material = MockMaterial(measurements=[c])
        items = _extract_comparable_items(material)
        assert len(items) == 1
        assert items[0].type == "composition"
        assert items[0].context is None

    def test_lattice_measurement(self):
        lm = _make_lattice_measurement()
        material = MockMaterial(measurements=[lm])
        items = _extract_comparable_items(material)
        assert len(items) == 1
        assert items[0].type == "lattice"

    def test_configuration_not_extracted(self):
        """Configurations are now matched separately, not extracted as comparable items."""
        nested_m = _make_measurement("volume_fraction", 0.3, percent)
        nested_lm = _make_lattice_measurement()
        nested_c = _make_comp("Fe2Ni1")
        config = _make_config(name="delta phase", measurements=[nested_m, nested_lm, nested_c])
        material = MockMaterial(measurements=[config])
        items = _extract_comparable_items(material)
        assert len(items) == 0  # configs excluded from comparable items

    def test_global_lattice_param_all_fields(self):
        lm = _make_lattice_measurement()
        pf = Quantity(value=0.5, unit=percent)
        glp = _make_global_lattice_param(name="FCC", lattice=lm, struct=CrysStruct.FCC, phase_fraction=pf)
        material = MockMaterial(measurements=[glp])
        items = _extract_comparable_items(material)
        assert len(items) == 3
        types = {item.type for item in items}
        assert types == {"lattice", "struct", "phase_fraction"}
        assert all(item.context == "FCC" for item in items)

    def test_global_lattice_param_partial(self):
        glp = _make_global_lattice_param(name="BCC", struct=CrysStruct.BCC)
        material = MockMaterial(measurements=[glp])
        items = _extract_comparable_items(material)
        assert len(items) == 1
        assert items[0].type == "struct"

    def test_mixed_material(self):
        m = _make_measurement()
        c = _make_comp()
        lm = _make_lattice_measurement()
        config = _make_config(name="alpha", measurements=[_make_measurement("grain_size", 5, dimensionless)])
        glp = _make_global_lattice_param(name="BCC", struct=CrysStruct.BCC)
        material = MockMaterial(measurements=[m, c, lm, config, glp])
        items = _extract_comparable_items(material)
        # 4 non-config items: measurement + comp + lattice + GLP struct
        assert len(items) == 4

    def test_empty_material(self):
        material = MockMaterial(measurements=[])
        items = _extract_comparable_items(material)
        assert items == []


# ===========================================================================
# Test individual matching functions
# ===========================================================================


class TestMeasurementsMatched:
    def test_identical(self):
        a = _make_measurement("hardness", 100, MegaPascal)
        b = _make_measurement("hardness", 100, MegaPascal)
        assert measurement_score(a, b) == 1.0

    def test_different_kind(self):
        a = _make_measurement("hardness", 100, MegaPascal)
        b = _make_measurement("yield_strength", 100, MegaPascal)
        assert measurement_score(a, b) == 0.0

    def test_different_value(self):
        a = _make_measurement("hardness", 100, MegaPascal)
        b = _make_measurement("hardness", 200, MegaPascal)
        assert measurement_score(a, b) == 0.0


class TestSplitKindToWords:
    def test_snake_case(self):
        assert _split_kind_to_words("yield_strength_tension") == {"yield", "strength", "tension"}

    def test_camel_case(self):
        assert _split_kind_to_words("yieldStrengthTension") == {"yield", "strength", "tension"}

    def test_mixed(self):
        assert _split_kind_to_words("yield_strengthTension") == {"yield", "strength", "tension"}

    def test_single_word(self):
        assert _split_kind_to_words("hardness") == {"hardness"}

    def test_uppercase_preserved_as_lower(self):
        assert _split_kind_to_words("UTS") == {"uts"}


class TestKindMatchScore:
    def test_exact_match(self):
        assert _kind_match_score("hardness", "hardness", False, False) == 1.0

    def test_exact_match_both_enum(self):
        assert _kind_match_score("hardness", "hardness", True, True) == 1.0

    def test_both_enum_no_match(self):
        assert _kind_match_score("hardness", "density", True, True) == 0.0

    def test_string_vs_enum_no_overlap(self):
        # "phase_transition_temperature" vs "melting_point" → no word overlap
        assert _kind_match_score("phase_transition_temperature", "melting_point", False, True) == 0.0

    def test_string_vs_enum_two_word_overlap(self):
        # "yield_strength" vs "yield_strength_tension" → 2 words overlap
        score = _kind_match_score("yield_strength", "yield_strength_tension", False, True)
        assert score == 0.7

    def test_string_vs_enum_one_word_overlap(self):
        # "hardness" vs "vickers_hardness" → 1 word overlap
        score = _kind_match_score("hardness", "vickers_hardness", False, True)
        assert score >= 0.3
        assert score < 1.0

    def test_two_strings_fuzzy(self):
        # both strings, 2 word overlap
        score = _kind_match_score("tensile_strength", "ultimate_tensile_strength", False, False)
        assert score == 0.7

    def test_two_strings_no_overlap(self):
        assert _kind_match_score("abc_def", "xyz_ghi", False, False) == 0.0


class TestFuzzyKindMeasurementScore:
    """Test that measurement_score uses fuzzy kind matching for string kinds."""

    def test_string_kind_fuzzy_match(self):
        a = _make_measurement("yield_strength", 100, MegaPascal)
        b = _make_measurement("yield_strength_tension", 100, MegaPascal)
        score = measurement_score(a, b)
        assert score > 0.0  # should match fuzzily

    def test_string_kind_no_overlap(self):
        a = _make_measurement("phase_transition_temperature", 100, MegaPascal)
        b = _make_measurement("melting_point", 100, MegaPascal)
        assert measurement_score(a, b) == 0.0

    def test_fuzzy_kind_still_checks_value(self):
        """Even with fuzzy kind match, different values should give 0."""
        a = _make_measurement("yield_strength", 100, MegaPascal)
        b = _make_measurement("yield_strength_tension", 200, MegaPascal)
        assert measurement_score(a, b) == 0.0

    def test_fuzzy_kind_still_checks_unit(self):
        """Even with fuzzy kind match, different units should give 0."""
        a = _make_measurement("yield_strength", 100, MegaPascal)
        b = _make_measurement("yield_strength_tension", 100, percent)
        assert measurement_score(a, b) == 0.0


class TestCompositionsMatched:
    def test_identical(self):
        a = _make_comp("Fe1Ni1")
        b = _make_comp("Fe1Ni1")
        assert _compositions_matched(a, b)

    def test_normalized_match(self):
        """Fe2Ni2 and Fe1Ni1 have the same fractional composition."""
        a = _make_comp("Fe2Ni2")
        b = _make_comp("Fe1Ni1")
        assert _compositions_matched(a, b)

    def test_different(self):
        a = _make_comp("Fe1Ni1")
        b = _make_comp("Fe1Co1")
        assert not _compositions_matched(a, b)


class TestLatticeMatched:
    def test_identical(self):
        la = PymatgenLattice.from_parameters(3.6, 3.6, 3.6, 90, 90, 90)
        lb = PymatgenLattice.from_parameters(3.6, 3.6, 3.6, 90, 90, 90)
        assert _lattice_matched(la, lb)

    def test_within_tolerance(self):
        la = PymatgenLattice.from_parameters(3.6, 3.6, 3.6, 90, 90, 90)
        lb = PymatgenLattice.from_parameters(3.605, 3.6, 3.6, 90, 90, 90)
        assert _lattice_matched(la, lb)

    def test_outside_tolerance(self):
        la = PymatgenLattice.from_parameters(3.6, 3.6, 3.6, 90, 90, 90)
        lb = PymatgenLattice.from_parameters(3.62, 3.6, 3.6, 90, 90, 90)
        assert not _lattice_matched(la, lb)


class TestQuantityMatched:
    def test_identical(self):
        a = Quantity(value=0.5, unit=percent)
        b = Quantity(value=0.5, unit=percent)
        assert _quantity_score(a, b) == 1.0

    def test_different_value(self):
        a = Quantity(value=0.5, unit=percent)
        b = Quantity(value=0.6, unit=percent)
        assert _quantity_score(a, b) == 0.0

    def test_different_unit(self):
        a = Quantity(value=0.5, unit=percent)
        b = Quantity(value=0.5, unit=dimensionless)
        assert _quantity_score(a, b) == 0.0


# ===========================================================================
# Test _comparable_items_matched (dispatch logic)
# ===========================================================================


class TestComparableItemsMatched:
    def test_different_type_never_matches(self):
        a = ComparableItem(type="measurement", item=_make_measurement())
        b = ComparableItem(type="composition", item=_make_comp())
        assert _comparable_item_score(a, b) == 0.0

    def test_different_context_no_overlap(self):
        """Completely different context names → 0.0."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        m2 = _make_measurement("volume_fraction", 0.3, percent)
        a = ComparableItem(type="measurement", item=m1, context="alpha")
        b = ComparableItem(type="measurement", item=m2, context="beta")
        assert _comparable_item_score(a, b) == 0.0

    def test_same_context_matches(self):
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        m2 = _make_measurement("volume_fraction", 0.3, percent)
        a = ComparableItem(type="measurement", item=m1, context="alpha")
        b = ComparableItem(type="measurement", item=m2, context="alpha")
        assert _comparable_item_score(a, b) == 1.0

    def test_struct_match(self):
        a = ComparableItem(type="struct", item=CrysStruct.FCC, context="phase1")
        b = ComparableItem(type="struct", item=CrysStruct.FCC, context="phase1")
        assert _comparable_item_score(a, b) == 1.0

    def test_struct_mismatch(self):
        a = ComparableItem(type="struct", item=CrysStruct.FCC, context="phase1")
        b = ComparableItem(type="struct", item=CrysStruct.BCC, context="phase1")
        assert _comparable_item_score(a, b) == 0.0


# ===========================================================================
# Test match_comparable_items (greedy matching)
# ===========================================================================


class TestMatchComparableItems:
    def test_all_matched(self):
        items_a = [
            ComparableItem(type="measurement", item=_make_measurement("hardness", 100, MegaPascal)),
            ComparableItem(type="composition", item=_make_comp("Fe1Ni1")),
        ]
        items_b = [
            ComparableItem(type="composition", item=_make_comp("Fe1Ni1")),
            ComparableItem(type="measurement", item=_make_measurement("hardness", 100, MegaPascal)),
        ]
        result = match_comparable_items(items_a, items_b)
        assert result.match_score == pytest.approx(2.0)
        assert len(result.unmatched_target) == 0
        assert len(result.unmatched_extracted) == 0

    def test_partial_match(self):
        items_a = [
            ComparableItem(type="measurement", item=_make_measurement("hardness", 100, MegaPascal)),
            ComparableItem(type="measurement", item=_make_measurement("yield_strength", 500, MegaPascal)),
        ]
        items_b = [
            ComparableItem(type="measurement", item=_make_measurement("hardness", 100, MegaPascal)),
        ]
        result = match_comparable_items(items_a, items_b)
        assert result.match_score == pytest.approx(1.0)
        assert len(result.unmatched_target) == 1
        assert len(result.unmatched_extracted) == 0

    def test_no_match(self):
        items_a = [ComparableItem(type="measurement", item=_make_measurement("hardness", 100, MegaPascal))]
        items_b = [ComparableItem(type="measurement", item=_make_measurement("yield_strength", 500, MegaPascal))]
        result = match_comparable_items(items_a, items_b)
        assert result.match_score == pytest.approx(0.0)
        assert len(result.unmatched_target) == 1
        assert len(result.unmatched_extracted) == 1

    def test_empty_lists(self):
        result = match_comparable_items([], [])
        assert result.match_score == pytest.approx(0.0)
        assert result.total == 0


# ===========================================================================
# Test measurement-level P / R / F1 on ExperimentComparisonResult
# ===========================================================================


class TestMeasurementLevelPRF1:
    def test_all_matched_perfect_scores(self):
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
            extracted_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
        )
        result = _make_result(matched=[match])
        assert result.precision == pytest.approx(1.0)
        assert result.recall == pytest.approx(1.0)
        assert result.f1 == pytest.approx(1.0)

    def test_unmatched_extracted_material_penalises_precision_proportionally(self):
        """An unmatched extracted material with 5 items should reduce precision
        more than one with 1 item."""
        # Matched pair: 2 items match perfectly
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
            extracted_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
        )
        # Unmatched extracted material with 1 item
        unmatched_small = MockMaterial(measurements=[_make_comp("Co1")])
        result_small = _make_result(matched=[match], unmatched_extracted=[unmatched_small])
        # TP=2, FP=1 → P = 2/3
        assert result_small.precision == pytest.approx(2.0 / 3.0)

        # Unmatched extracted material with 5 items
        unmatched_large = MockMaterial(
            measurements=[
                _make_comp("Co1"),
                _make_measurement("hardness", 200, MegaPascal),
                _make_measurement("yield_strength", 300, MegaPascal),
                _make_measurement("density", 7.0, MegaPascal),
                _make_measurement("fracture_toughness", 50, MegaPascal),
            ]
        )
        result_large = _make_result(matched=[match], unmatched_extracted=[unmatched_large])
        # TP=2, FP=5 → P = 2/7
        assert result_large.precision == pytest.approx(2.0 / 7.0)

        # Verify larger unmatched material penalises more
        assert result_large.precision < result_small.precision

    def test_unmatched_target_material_penalises_recall_proportionally(self):
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
            extracted_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
        )
        # Unmatched target with 3 items
        unmatched = MockMaterial(
            measurements=[
                _make_comp("Cr1"),
                _make_measurement("hardness", 999, MegaPascal),
                _make_measurement("yield_strength", 888, MegaPascal),
            ]
        )
        result = _make_result(matched=[match], unmatched_target=[unmatched])
        # TP=2, FN=3 → R = 2/5
        assert result.recall == pytest.approx(2.0 / 5.0)

    def test_no_matches_zero_scores(self):
        unmatched_target = MockMaterial(measurements=[_make_comp("Fe1")])
        unmatched_extracted = MockMaterial(measurements=[_make_comp("Ni1")])
        result = _make_result(
            unmatched_target=[unmatched_target],
            unmatched_extracted=[unmatched_extracted],
        )
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_empty_result(self):
        result = _make_result()
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0

    def test_material_counts_still_available(self):
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1")],
            extracted_measurements=[_make_comp("Fe1Ni1")],
        )
        unmatched_t = MockMaterial(measurements=[_make_comp("Cr1")])
        unmatched_e = MockMaterial(measurements=[_make_comp("Co1")])
        result = _make_result(matched=[match], unmatched_target=[unmatched_t], unmatched_extracted=[unmatched_e])
        assert result.num_target_materials == 2
        assert result.num_extracted_materials == 2
        assert result.num_matched_materials == 1


# ===========================================================================
# Test Configuration extraction and matching
# ===========================================================================


class TestExtractConfigurations:
    def test_extracts_configurations(self):
        config = _make_config("alpha", [_make_measurement("grain_size", 10, dimensionless)])
        material = MockMaterial(measurements=[_make_measurement(), config])
        configs = _extract_configurations(material)
        assert len(configs) == 1
        assert configs[0].name == "alpha"

    def test_no_configurations(self):
        material = MockMaterial(measurements=[_make_measurement()])
        configs = _extract_configurations(material)
        assert len(configs) == 0

    def test_extract_config_comparable_items(self):
        m = _make_measurement("volume_fraction", 0.3, percent)
        lm = _make_lattice_measurement()
        c = _make_comp("Fe2Ni1")
        config = _make_config("delta", [m, lm, c])
        items = _extract_config_comparable_items(config)
        assert len(items) == 3
        types = {item.type for item in items}
        assert types == {"measurement", "lattice", "composition"}
        assert all(item.context is None for item in items)


# ===========================================================================
# Test GlobalLatticeParam sub-field independent counting
# ===========================================================================


class TestGlobalLatticeParamSubFields:
    def test_all_three_fields_count_as_three_items(self):
        lm = _make_lattice_measurement()
        pf = Quantity(value=0.5, unit=percent)
        glp = _make_global_lattice_param(name="FCC", lattice=lm, struct=CrysStruct.FCC, phase_fraction=pf)
        material = MockMaterial(measurements=[glp])
        assert _count_comparable_items(material) == 3

    def test_only_struct_counts_as_one(self):
        glp = _make_global_lattice_param(name="BCC", struct=CrysStruct.BCC)
        material = MockMaterial(measurements=[glp])
        assert _count_comparable_items(material) == 1

    def test_matching_all_sub_fields(self):
        lm = _make_lattice_measurement()
        pf = Quantity(value=0.5, unit=percent)
        glp_a = _make_global_lattice_param(name="FCC", lattice=lm, struct=CrysStruct.FCC, phase_fraction=pf)
        glp_b = _make_global_lattice_param(
            name="FCC",
            lattice=_make_lattice_measurement(),
            struct=CrysStruct.FCC,
            phase_fraction=Quantity(value=0.5, unit=percent),
        )

        items_a = _extract_comparable_items(MockMaterial(measurements=[glp_a]))
        items_b = _extract_comparable_items(MockMaterial(measurements=[glp_b]))
        result = match_comparable_items(items_a, items_b)
        assert result.match_score == pytest.approx(3.0)

    def test_partial_match_sub_fields(self):
        lm = _make_lattice_measurement()
        glp_a = _make_global_lattice_param(name="FCC", lattice=lm, struct=CrysStruct.FCC)
        glp_b = _make_global_lattice_param(name="FCC", lattice=_make_lattice_measurement(), struct=CrysStruct.BCC)

        items_a = _extract_comparable_items(MockMaterial(measurements=[glp_a]))
        items_b = _extract_comparable_items(MockMaterial(measurements=[glp_b]))
        result = match_comparable_items(items_a, items_b)
        # lattice matches, struct doesn't
        assert result.match_score == pytest.approx(1.0)
        assert len(result.unmatched_target) == 1
        assert len(result.unmatched_extracted) == 1


# ===========================================================================
# Test _context_score
# ===========================================================================


class TestContextScore:
    def test_both_none(self):
        assert _context_score(None, None) == 1.0

    def test_one_none(self):
        assert _context_score(None, "alpha") == 0.0
        assert _context_score("alpha", None) == 0.0

    def test_exact_match(self):
        assert _context_score("alpha", "alpha") == 1.0

    def test_token_normalized_match(self):
        """Punctuation is stripped, so these should be identical token sets."""
        assert _context_score("Region B (AlLi phase)", "Region B: AlLi phase") == pytest.approx(1.0)

    def test_no_overlap(self):
        assert _context_score("alpha", "beta") == 0.0

    def test_partial_overlap(self):
        # "alpha phase" → {"alpha", "phase"}, "beta phase" → {"beta", "phase"}
        # intersection={"phase"}, union={"alpha", "beta", "phase"} → 1/3
        assert _context_score("alpha phase", "beta phase") == pytest.approx(1.0 / 3.0)

    def test_both_empty_strings(self):
        assert _context_score("", "") == 1.0


# ===========================================================================
# Test _qualifier_compatibility
# ===========================================================================


class TestQualifierCompatibility:
    def test_exact_exact(self):
        assert _qualifier_compatibility(ValueQualifier.EXACT, ValueQualifier.EXACT) == 1.0

    def test_exact_approximate(self):
        assert _qualifier_compatibility(ValueQualifier.EXACT, ValueQualifier.APPROXIMATE) == 0.75

    def test_exact_above(self):
        assert _qualifier_compatibility(ValueQualifier.EXACT, ValueQualifier.ABOVE) == 0.5

    def test_above_below(self):
        assert _qualifier_compatibility(ValueQualifier.ABOVE, ValueQualifier.BELOW) == 0.0

    def test_above_above_or_equal(self):
        assert _qualifier_compatibility(ValueQualifier.ABOVE, ValueQualifier.ABOVE_OR_EQUAL) == 0.75

    def test_much_above_much_below(self):
        assert _qualifier_compatibility(ValueQualifier.MUCH_ABOVE, ValueQualifier.MUCH_BELOW) == 0.0

    def test_much_above_above(self):
        assert _qualifier_compatibility(ValueQualifier.MUCH_ABOVE, ValueQualifier.ABOVE) == 0.5

    def test_symmetric(self):
        """Matrix should be symmetric."""
        for a in ValueQualifier:
            for b in ValueQualifier:
                assert _qualifier_compatibility(a, b) == _qualifier_compatibility(b, a)


# ===========================================================================
# Test ancestry chain and config cost
# ===========================================================================


class TestAncestryChain:
    def test_no_within(self):
        config = _make_config("alpha")
        config_map = _build_config_map([config])
        assert _build_ancestry_chain(config, config_map) == []

    def test_single_parent(self):
        parent = _make_config("gamma-matrix")
        child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        config_map = _build_config_map([parent, child])
        chain = _build_ancestry_chain(child, config_map)
        assert chain == ["gamma-matrix"]

    def test_two_level_chain(self):
        root = _make_config("alloy")
        mid = Configuration(name="gamma-matrix", within="alloy", measurements=[])
        leaf = Configuration(name="delta", within="gamma-matrix", measurements=[])
        config_map = _build_config_map([root, mid, leaf])
        chain = _build_ancestry_chain(leaf, config_map)
        assert chain == ["alloy", "gamma-matrix"]

    def test_missing_parent(self):
        child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        config_map = _build_config_map([child])
        chain = _build_ancestry_chain(child, config_map)
        assert chain == ["gamma-matrix"]

    def test_collect_ancestry_tags(self):
        parent = Configuration(
            name="gamma-matrix",
            measurements=[],
            tags={ConfigTag.Matrix},
        )
        child = Configuration(
            name="delta",
            within="gamma-matrix",
            measurements=[],
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
        )
        config_map = _build_config_map([parent, child])
        tags = _collect_ancestry_tags(child, config_map)
        assert tags == {ConfigTag.Matrix, ConfigTag.Precipitate, ConfigTag.Intragranular}

    def test_ancestry_context_string(self):
        parent = _make_config("gamma-matrix")
        child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        config_map = _build_config_map([parent, child])
        ctx = _ancestry_context_string(child, config_map)
        assert ctx == "gamma-matrix delta"

    def test_ancestry_context_string_no_ancestry(self):
        config = _make_config("alpha")
        config_map = _build_config_map([config])
        ctx = _ancestry_context_string(config, config_map)
        assert ctx == "alpha"


class TestConfigCost:
    def test_identical_configs(self):
        c1 = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        c2 = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        cost, meas, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost == pytest.approx(0.0)

    def test_completely_different_configs(self):
        c1 = Configuration(
            name="alpha",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Matrix},
        )
        c2 = Configuration(
            name="beta",
            struct=CrysStruct.BCC,
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        cost, meas, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost > 0

    def test_same_struct_different_name(self):
        c1 = Configuration(name="alpha", struct=CrysStruct.FCC, measurements=[])
        c2 = Configuration(name="beta", struct=CrysStruct.FCC, measurements=[])
        cost, _, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        # Struct matches (cost=0), name doesn't (cost>0)
        assert cost > 0
        assert cost < 5.0  # below unmatched penalty

    def test_nested_measurement_affects_cost(self):
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        m2 = _make_measurement("volume_fraction", 0.5, percent)  # different value
        c1 = Configuration(name="delta", measurements=[m1])
        c2 = Configuration(name="delta", measurements=[m2])
        cost, meas, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert meas.match_score == pytest.approx(0.0)  # values don't match
        assert cost > 0

    def test_empty_measurements_perfect_sim(self):
        c1 = Configuration(name="delta", measurements=[])
        c2 = Configuration(name="delta", measurements=[])
        cost, meas, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost == pytest.approx(0.0)

    def test_tags_none_vs_none(self):
        c1 = Configuration(name="alpha", measurements=[])
        c2 = Configuration(name="alpha", measurements=[])
        cost, _, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost == pytest.approx(0.0)


class TestMatchConfigurations:
    def test_perfect_match(self):
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[])
        c2 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[])
        result = match_configurations([c1], [c2], _build_config_map([c1]), _build_config_map([c2]))
        assert len(result.matched_pairs) == 1
        assert len(result.unmatched_target) == 0
        assert len(result.unmatched_extracted) == 0

    def test_no_match(self):
        """Two configs with completely different names and struct should still match
        if the cost is below the unmatched penalty."""
        c1 = Configuration(name="alpha", struct=CrysStruct.FCC, measurements=[])
        c2 = Configuration(name="beta", struct=CrysStruct.BCC, measurements=[])
        result = match_configurations([c1], [c2], _build_config_map([c1]), _build_config_map([c2]))
        # They might still match since cost < penalty, depending on exact cost
        assert len(result.matched_pairs) + len(result.unmatched_target) == 1

    def test_empty_both(self):
        result = match_configurations([], [], {}, {})
        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_target) == 0
        assert len(result.unmatched_extracted) == 0

    def test_one_side_empty(self):
        c1 = Configuration(name="delta", measurements=[])
        result = match_configurations([c1], [], _build_config_map([c1]), {})
        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_target) == 1

    def test_multiple_configs_hungarian(self):
        """Hungarian should find optimal assignment."""
        c1a = Configuration(name="alpha", struct=CrysStruct.FCC, measurements=[])
        c1b = Configuration(name="beta", struct=CrysStruct.BCC, measurements=[])
        c2a = Configuration(name="alpha", struct=CrysStruct.FCC, measurements=[])
        c2b = Configuration(name="beta", struct=CrysStruct.BCC, measurements=[])
        result = match_configurations(
            [c1a, c1b],
            [c2a, c2b],
            _build_config_map([c1a, c1b]),
            _build_config_map([c2a, c2b]),
        )
        assert len(result.matched_pairs) == 2
        # Verify optimal pairing: alpha→alpha, beta→beta
        names = [(t.name, e.name) for t, e, _ in result.matched_pairs]
        assert ("alpha", "alpha") in names
        assert ("beta", "beta") in names

    def test_nested_measurement_results_parallel(self):
        """nested_measurement_results should be parallel to matched_pairs."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        c1 = Configuration(name="delta", measurements=[m1])
        c2 = Configuration(name="delta", measurements=[m1])
        result = match_configurations([c1], [c2], _build_config_map([c1]), _build_config_map([c2]))
        assert len(result.nested_measurement_results) == len(result.matched_pairs)


class TestConfigFieldValues:
    def test_count_config_field_values(self):
        config = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
        )
        assert _count_config_field_values(config) == 3  # 2 tags + 1 struct

    def test_count_no_fields(self):
        config = Configuration(name="delta", measurements=[])
        assert _count_config_field_values(config) == 0

    def test_compare_identical_fields(self):
        c1 = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        c2 = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        vcr = _compare_config_field_values(c1, c2)
        assert vcr.tp == pytest.approx(2.0)  # 1 tag + 1 struct
        assert vcr.target_count == 2
        assert vcr.extracted_count == 2

    def test_compare_different_struct(self):
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[])
        c2 = Configuration(name="delta", struct=CrysStruct.BCC, measurements=[])
        vcr = _compare_config_field_values(c1, c2)
        assert vcr.tp == pytest.approx(0.0)
        assert vcr.target_count == 1
        assert vcr.extracted_count == 1

    def test_compare_partial_tags(self):
        c1 = Configuration(
            name="delta",
            measurements=[],
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
        )
        c2 = Configuration(
            name="delta",
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        vcr = _compare_config_field_values(c1, c2)
        assert vcr.tp == pytest.approx(1.0)  # Precipitate matches
        assert vcr.target_count == 2
        assert vcr.extracted_count == 1


# ===========================================================================
# Test fuzzy config matching end-to-end
# ===========================================================================


class TestFuzzyConfigMatching:
    def test_qualifier_mismatch_partial_credit(self):
        """Same value but different qualifier → partial credit via measurement_score."""
        a = Measurement(kind="vickers_hardness", value=">60", unit=percent)
        b = Measurement(kind="vickers_hardness", value="60", unit=percent)
        # a has ABOVE qualifier, b has EXACT → 0.5
        assert measurement_score(a, b) == pytest.approx(0.5)


# ===========================================================================
# Test align_process_events
# ===========================================================================


class TestAlignProcessEvents:
    def test_identical_sequences(self):
        a = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        b = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        result = align_process_events(a, b)
        assert result.edit_distance == 0
        assert len(result.matched_pairs) == 2
        assert len(result.unmatched_target) == 0
        assert len(result.unmatched_extracted) == 0

    def test_empty_sequences(self):
        result = align_process_events([], [])
        assert result.edit_distance == 0
        assert len(result.matched_pairs) == 0

    def test_insertion(self):
        a = [ProcessEvent(kind="melting")]
        b = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        result = align_process_events(a, b)
        assert result.edit_distance == 1
        assert len(result.matched_pairs) == 1
        assert len(result.unmatched_target) == 0
        assert len(result.unmatched_extracted) == 1

    def test_deletion(self):
        a = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        b = [ProcessEvent(kind="melting")]
        result = align_process_events(a, b)
        assert result.edit_distance == 1
        assert len(result.matched_pairs) == 1
        assert len(result.unmatched_target) == 1
        assert len(result.unmatched_extracted) == 0

    def test_substitution(self):
        a = [ProcessEvent(kind="melting")]
        b = [ProcessEvent(kind="casting")]
        result = align_process_events(a, b)
        assert result.edit_distance == 1
        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_target) == 1
        assert len(result.unmatched_extracted) == 1

    def test_one_empty(self):
        a = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        result = align_process_events(a, [])
        assert result.edit_distance == 2
        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_target) == 2

    def test_edit_distance_matches_standalone(self):
        """align_process_events edit_distance should match process_event_edit_distance."""
        from litxbench.core.eval import process_event_edit_distance

        a = [ProcessEvent(kind="melting"), ProcessEvent(kind="annealing"), ProcessEvent(kind="casting")]
        b = [ProcessEvent(kind="melting"), ProcessEvent(kind="casting")]
        result = align_process_events(a, b)
        standalone = process_event_edit_distance(a, b)
        assert result.edit_distance == standalone


# ===========================================================================
# Test value decomposition functions
# ===========================================================================


class TestCountItemValues:
    def test_measurement_no_temp_pressure(self):
        m = _make_measurement("hardness", 100, MegaPascal)
        item = ComparableItem(type="measurement", item=m)
        assert _count_item_values(item) == 1

    def test_measurement_with_temp(self):
        m = Measurement(kind="hardness", value=100, unit=MegaPascal, temperature=Quantity(value=25, unit=Celsius))
        item = ComparableItem(type="measurement", item=m)
        assert _count_item_values(item) == 2

    def test_measurement_with_temp_and_pressure(self):
        m = Measurement(
            kind="hardness",
            value=100,
            unit=MegaPascal,
            temperature=Quantity(value=25, unit=Celsius),
            pressure=Quantity(value=1, unit=MegaPascal),
        )
        item = ComparableItem(type="measurement", item=m)
        assert _count_item_values(item) == 3

    def test_composition(self):
        c = _make_comp("Fe1Ni1Co1")
        item = ComparableItem(type="composition", item=c)
        assert _count_item_values(item) == 3  # 3 elements

    def test_lattice(self):
        lm = _make_lattice_measurement()
        item = ComparableItem(type="lattice", item=lm)
        assert _count_item_values(item) == 6

    def test_struct(self):
        item = ComparableItem(type="struct", item=CrysStruct.FCC)
        assert _count_item_values(item) == 1

    def test_phase_fraction(self):
        pf = Quantity(value=0.5, unit=percent)
        item = ComparableItem(type="phase_fraction", item=pf)
        assert _count_item_values(item) == 1


class TestCompareItemValues:
    def test_matched_measurement_basic(self):
        m1 = _make_measurement("hardness", 100, MegaPascal)
        m2 = _make_measurement("hardness", 100, MegaPascal)
        t = ComparableItem(type="measurement", item=m1)
        e = ComparableItem(type="measurement", item=m2)
        vcr = _compare_item_values(t, e, 1.0)
        assert vcr.tp == pytest.approx(1.0)
        assert vcr.target_count == 1
        assert vcr.extracted_count == 1

    def test_matched_measurement_with_temp(self):
        m1 = Measurement(kind="hardness", value=100, unit=MegaPascal, temperature=Quantity(value=25, unit=Celsius))
        m2 = Measurement(kind="hardness", value=100, unit=MegaPascal, temperature=Quantity(value=25, unit=Celsius))
        t = ComparableItem(type="measurement", item=m1)
        e = ComparableItem(type="measurement", item=m2)
        vcr = _compare_item_values(t, e, 1.0)
        assert vcr.tp == pytest.approx(2.0)  # primary + temp
        assert vcr.target_count == 2
        assert vcr.extracted_count == 2

    def test_matched_composition(self):
        c1 = _make_comp("Fe1Ni1")
        c2 = _make_comp("Fe1Ni1")
        t = ComparableItem(type="composition", item=c1)
        e = ComparableItem(type="composition", item=c2)
        vcr = _compare_item_values(t, e, 1.0)
        assert vcr.tp == pytest.approx(2.0)  # 2 elements
        assert vcr.target_count == 2
        assert vcr.extracted_count == 2

    def test_matched_lattice(self):
        lm1 = _make_lattice_measurement()
        lm2 = _make_lattice_measurement()
        t = ComparableItem(type="lattice", item=lm1)
        e = ComparableItem(type="lattice", item=lm2)
        vcr = _compare_item_values(t, e, 1.0)
        assert vcr.tp == pytest.approx(6.0)
        assert vcr.target_count == 6
        assert vcr.extracted_count == 6


class TestProcessEventValues:
    def test_count_kind_only(self):
        evt = ProcessEvent(kind="melting")
        assert _count_process_event_values(evt) == 1

    def test_count_with_temp_and_duration(self):
        evt = ProcessEvent(
            kind="melting",
            temperature=Quantity(value=1500, unit=Celsius),
            duration=Quantity(value=60, unit=dimensionless),
        )
        assert _count_process_event_values(evt) == 3

    def test_compare_matching_events(self):
        t = ProcessEvent(kind="melting", temperature=Quantity(value=1500, unit=Celsius))
        e = ProcessEvent(kind="melting", temperature=Quantity(value=1500, unit=Celsius))
        vcr = _compare_process_event_values(t, e)
        assert vcr.tp == pytest.approx(2.0)  # kind + temp
        assert vcr.target_count == 2
        assert vcr.extracted_count == 2

    def test_compare_mismatched_temp(self):
        t = ProcessEvent(kind="melting", temperature=Quantity(value=1500, unit=Celsius))
        e = ProcessEvent(kind="melting", temperature=Quantity(value=1600, unit=Celsius))
        vcr = _compare_process_event_values(t, e)
        assert vcr.tp == pytest.approx(1.0)  # only kind matches
        assert vcr.target_count == 2
        assert vcr.extracted_count == 2


# ===========================================================================
# Test MultiLevelMetrics and compute_multi_level_metrics
# ===========================================================================


class TestMultiLevelMetrics:
    def test_perfect_match(self):
        """All materials, measurements, and values match perfectly."""
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
            extracted_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        assert ml.material_f1 == pytest.approx(1.0)
        assert ml.measurement_f1 == pytest.approx(1.0)
        assert ml.value_f1 == pytest.approx(1.0)
        assert ml.overall_f1 == pytest.approx(1.0)

    def test_unmatched_target_material(self):
        """Unmatched target material should reduce material recall."""
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1")],
            extracted_measurements=[_make_comp("Fe1Ni1")],
        )
        unmatched = MockMaterial(measurements=[_make_comp("Cr1")])
        result = _make_result(matched=[match], unmatched_target=[unmatched])
        ml = compute_multi_level_metrics(result)

        assert ml.material_tp == 1
        assert ml.material_target == 2
        assert ml.material_extracted == 1
        assert ml.material_recall == pytest.approx(0.5)
        assert ml.material_precision == pytest.approx(1.0)

    def test_process_events_counted(self):
        """Process events in matched materials are counted at process level."""
        alignment = ProcessEventAlignmentResult(
            matched_pairs=[
                (ProcessEvent(kind="melting"), ProcessEvent(kind="melting")),
                (ProcessEvent(kind="casting"), ProcessEvent(kind="casting")),
            ],
            unmatched_target=[ProcessEvent(kind="annealing")],
            unmatched_extracted=[],
            edit_distance=1,
        )
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1")],
            extracted_measurements=[_make_comp("Fe1Ni1")],
            process_alignment=alignment,
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        assert ml.process_tp == 2
        assert ml.process_target == 3
        assert ml.process_extracted == 2
        assert ml.process_recall == pytest.approx(2.0 / 3.0)
        assert ml.process_precision == pytest.approx(1.0)

    def test_value_level_counts_composition_elements(self):
        """Value level should count individual elements in compositions."""
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1Co1")],
            extracted_measurements=[_make_comp("Fe1Ni1Co1")],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        # 3 elements in the composition
        assert ml.value_tp == pytest.approx(3.0)
        assert ml.value_target == 3
        assert ml.value_extracted == 3

    def test_empty_result(self):
        result = _make_result()
        ml = compute_multi_level_metrics(result)
        assert ml.material_f1 == 0.0
        assert ml.measurement_f1 == 0.0
        assert ml.process_f1 == 0.0
        assert ml.value_f1 == 0.0

    def test_measurement_level_matches_existing_prf1(self):
        """Measurement-level P/R/F1 should match the existing ExperimentComparisonResult P/R/F1."""
        match = _make_material_match(
            target_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
            extracted_measurements=[_make_comp("Fe1Ni1"), _make_measurement("hardness", 100, MegaPascal)],
        )
        unmatched_t = MockMaterial(measurements=[_make_comp("Cr1")])
        result = _make_result(matched=[match], unmatched_target=[unmatched_t])
        ml = compute_multi_level_metrics(result)

        assert ml.measurement_precision == pytest.approx(result.precision)
        assert ml.measurement_recall == pytest.approx(result.recall)
        assert ml.measurement_f1 == pytest.approx(result.f1)


class TestMultiLevelMetricsWithConfigs:
    def test_config_level_perfect_match(self):
        """Matched configs should be counted at config level."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        m2 = _make_measurement("volume_fraction", 0.3, percent)
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[m1], tags={ConfigTag.Precipitate})
        c2 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[m2], tags={ConfigTag.Precipitate})
        match = _make_material_match(
            target_measurements=[c1],
            extracted_measurements=[c2],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        assert ml.config_tp == 1
        assert ml.config_target == 1
        assert ml.config_extracted == 1
        assert ml.config_f1 == pytest.approx(1.0)

    def test_config_values_counted(self):
        """Config field values (tags, struct) should be counted at value level."""
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[], tags={ConfigTag.Precipitate})
        c2 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[], tags={ConfigTag.Precipitate})
        match = _make_material_match(
            target_measurements=[c1],
            extracted_measurements=[c2],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        # 1 tag + 1 struct = 2 values
        assert ml.value_tp == pytest.approx(2.0)
        assert ml.value_target == 2
        assert ml.value_extracted == 2

    def test_config_nested_measurements_in_values(self):
        """Nested config measurements should be counted at value and measurement level."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        m2 = _make_measurement("volume_fraction", 0.3, percent)
        c1 = Configuration(name="delta", measurements=[m1])
        c2 = Configuration(name="delta", measurements=[m2])
        match = _make_material_match(
            target_measurements=[c1],
            extracted_measurements=[c2],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        # Measurement level should include config nested measurements
        assert ml.measurement_tp == pytest.approx(1.0)
        assert ml.measurement_target == 1
        assert ml.measurement_extracted == 1

        # Value level: 1 measurement primary value
        assert ml.value_tp == pytest.approx(1.0)
        assert ml.value_target == 1
        assert ml.value_extracted == 1

    def test_unmatched_config_values_penalized(self):
        """Unmatched config fields and measurements should appear as FN/FP at value level."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[m1], tags={ConfigTag.Precipitate})
        match = _make_material_match(
            target_measurements=[c1],
            extracted_measurements=[],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        assert ml.config_tp == 0
        assert ml.config_target == 1
        assert ml.config_extracted == 0
        # Value level: 1 tag + 1 struct + 1 measurement value = 3 target values
        assert ml.value_target == 3
        assert ml.value_extracted == 0
        assert ml.value_tp == pytest.approx(0.0)

    def test_unmatched_material_with_configs(self):
        """Unmatched material with configs should count config fields and measurements."""
        m1 = _make_measurement("volume_fraction", 0.3, percent)
        c1 = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[m1])
        unmatched = MockMaterial(measurements=[c1])
        result = _make_result(unmatched_target=[unmatched])
        ml = compute_multi_level_metrics(result)

        # Config counted
        assert ml.config_target == 1
        assert ml.config_extracted == 0
        # Value level: 1 struct + 1 measurement value = 2
        assert ml.value_target == 2
        assert ml.value_extracted == 0

    def test_within_counted_in_values(self):
        """Config with within should include within in value counts."""
        parent = Configuration(name="gamma-matrix", measurements=[], tags={ConfigTag.Matrix})
        child = Configuration(
            name="delta",
            within="gamma-matrix",
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        parent_e = Configuration(name="gamma-matrix", measurements=[], tags={ConfigTag.Matrix})
        child_e = Configuration(
            name="delta",
            within="gamma-matrix",
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        match = _make_material_match(
            target_measurements=[parent, child],
            extracted_measurements=[parent_e, child_e],
        )
        result = _make_result(matched=[match])
        ml = compute_multi_level_metrics(result)

        # Parent: 1 tag = 1 value; Child: 1 tag + 1 within = 2 values → 3 total per side
        assert ml.value_target == 3
        assert ml.value_extracted == 3


# ===========================================================================
# Test _check_within_match
# ===========================================================================


class TestCheckWithinMatch:
    def test_both_none(self):
        t = _make_config("alpha")
        e = _make_config("alpha")
        assert _check_within_match(t, e, []) is True

    def test_target_none_extracted_has_within(self):
        t = _make_config("alpha")
        e = _make_config("alpha", within="parent")
        assert _check_within_match(t, e, []) is False

    def test_target_has_within_extracted_none(self):
        t = _make_config("alpha", within="parent")
        e = _make_config("alpha")
        assert _check_within_match(t, e, []) is False

    def test_parents_matched_together(self):
        t_parent = _make_config("gamma-matrix")
        e_parent = _make_config("gamma-matrix")
        t_child = _make_config("delta", within="gamma-matrix")
        e_child = _make_config("delta", within="gamma-matrix")
        matched_pairs = [(t_parent, e_parent, 1.0)]
        assert _check_within_match(t_child, e_child, matched_pairs) is True

    def test_parents_not_matched_together(self):
        t_parent = _make_config("gamma-matrix")
        e_other = _make_config("other-parent")
        t_child = _make_config("delta", within="gamma-matrix")
        e_child = _make_config("delta", within="gamma-matrix")
        # Parents are matched but to wrong configs
        matched_pairs = [(t_parent, e_other, 1.0)]
        assert _check_within_match(t_child, e_child, matched_pairs) is False

    def test_different_parent_names_matched(self):
        """Parents with different names that are matched together should pass."""
        t_parent = _make_config("matrix-A")
        e_parent = _make_config("matrix-B")
        t_child = _make_config("delta", within="matrix-A")
        e_child = _make_config("delta", within="matrix-B")
        matched_pairs = [(t_parent, e_parent, 0.8)]
        assert _check_within_match(t_child, e_child, matched_pairs) is True


# ===========================================================================
# Test within in _config_cost
# ===========================================================================


class TestConfigCostWithin:
    def test_within_match_lowers_cost(self):
        """Configs with matching within should cost less than mismatched within."""
        c1 = Configuration(name="delta", within="gamma-matrix", measurements=[])
        c2_match = Configuration(name="delta", within="gamma-matrix", measurements=[])
        c2_mismatch = Configuration(name="delta", within="other-parent", measurements=[])

        cost_match, _, _ = _config_cost(c1, c2_match, _build_config_map([c1]), _build_config_map([c2_match]))
        cost_mismatch, _, _ = _config_cost(c1, c2_mismatch, _build_config_map([c1]), _build_config_map([c2_mismatch]))
        assert cost_match < cost_mismatch

    def test_both_none_within_no_penalty(self):
        """Both configs with within=None should have no within penalty."""
        c1 = Configuration(name="delta", measurements=[])
        c2 = Configuration(name="delta", measurements=[])
        cost, _, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost == pytest.approx(0.0)

    def test_one_none_within_adds_penalty(self):
        """One config with within=None and the other with within set should add penalty."""
        c1 = Configuration(name="delta", within="gamma-matrix", measurements=[])
        c2 = Configuration(name="delta", measurements=[])
        cost, _, _ = _config_cost(c1, c2, _build_config_map([c1]), _build_config_map([c2]))
        assert cost > 0


# ===========================================================================
# Test within in _count_config_field_values and _compare_config_field_values
# ===========================================================================


class TestConfigFieldValuesWithin:
    def test_count_includes_within(self):
        config = Configuration(
            name="delta",
            struct=CrysStruct.FCC,
            within="gamma-matrix",
            measurements=[],
            tags={ConfigTag.Precipitate},
        )
        # 1 tag + 1 struct + 1 within = 3
        assert _count_config_field_values(config) == 3

    def test_count_no_within(self):
        config = Configuration(name="delta", struct=CrysStruct.FCC, measurements=[])
        # 1 struct, no within
        assert _count_config_field_values(config) == 1

    def test_compare_within_parent_matched(self):
        """When parents are matched together, within should count as TP."""
        t_parent = _make_config("gamma-matrix")
        e_parent = _make_config("gamma-matrix")
        t_child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        e_child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        matched_pairs = [(t_parent, e_parent, 1.0), (t_child, e_child, 1.0)]

        vcr = _compare_config_field_values(t_child, e_child, matched_pairs)
        assert vcr.tp == pytest.approx(1.0)  # within TP
        assert vcr.target_count == 1  # within
        assert vcr.extracted_count == 1  # within

    def test_compare_within_parent_not_matched(self):
        """When parents are NOT matched together, within should not count as TP."""
        t_child = Configuration(name="delta", within="gamma-matrix", measurements=[])
        e_child = Configuration(name="delta", within="other-parent", measurements=[])
        matched_pairs = [(t_child, e_child, 1.0)]  # no parent pair

        vcr = _compare_config_field_values(t_child, e_child, matched_pairs)
        assert vcr.tp == pytest.approx(0.0)
        assert vcr.target_count == 1
        assert vcr.extracted_count == 1

    def test_compare_within_one_none(self):
        """One has within, other doesn't — counts increment but no TP."""
        t = Configuration(name="delta", within="gamma-matrix", measurements=[])
        e = Configuration(name="delta", measurements=[])

        vcr = _compare_config_field_values(t, e, [])
        assert vcr.tp == pytest.approx(0.0)
        assert vcr.target_count == 1
        assert vcr.extracted_count == 0

    def test_compare_within_both_none(self):
        """Both without within — no within items counted."""
        t = Configuration(name="delta", measurements=[])
        e = Configuration(name="delta", measurements=[])

        vcr = _compare_config_field_values(t, e, [])
        assert vcr.tp == pytest.approx(0.0)
        assert vcr.target_count == 0
        assert vcr.extracted_count == 0

    def test_compare_without_matched_pairs_arg(self):
        """Without matched_pairs, within present on both sides should not TP."""
        t = Configuration(name="delta", within="gamma-matrix", measurements=[])
        e = Configuration(name="delta", within="gamma-matrix", measurements=[])

        vcr = _compare_config_field_values(t, e)
        assert vcr.tp == pytest.approx(0.0)  # no matched_pairs → can't verify
        assert vcr.target_count == 1
        assert vcr.extracted_count == 1
