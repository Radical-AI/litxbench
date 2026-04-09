from dataclasses import dataclass

import pytest
from pymatgen.core.composition import Composition

from litxbench.core.eval import resolve_process_events
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
)
from litxbench.litxalloy.models import (
    AlloyMaterial,
    Experiment,
    Material,
    ProcessEvent,
    ProcessKind,
    Quantity,
    RawMaterial,
    RawMaterialKind,
)


# Helper functions to create test fixtures
def create_raw_material(kind: RawMaterialKind = RawMaterialKind.Powder) -> RawMaterial:
    """Create a basic raw material for testing."""
    return RawMaterial(kind=kind, description="Test material")


def create_process_event(
    kind: ProcessKind | str = ProcessKind.Annealing,
    temperature: Quantity | None = None,
    duration: Quantity | None = None,
) -> ProcessEvent:
    """Create a basic process event for testing."""
    return ProcessEvent(kind=kind, temperature=temperature, duration=duration, description="Test process")


def create_material(process: str | None = None, composition_str: str = "Fe50Co50") -> Material:
    """Create a basic material for testing."""
    return Material(
        process=process,
        measurements=[CompMeasurement(Composition(composition_str))],
    )


class TestValidateRawMaterialsNotEmpty:
    """Tests for _validate_raw_materials_not_empty validation."""

    def test_valid_single_raw_material(self):
        """Test that experiment with one raw material is valid."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[create_material()],
        )
        # Should not raise

    def test_multiple_raw_materials_is_valid(self):
        """Test that experiment with multiple raw materials is valid."""
        _experiment = Experiment(
            raw_materials={
                "powder1": create_raw_material(),
                "powder2": create_raw_material(RawMaterialKind.Ingot),
            },
            synthesis_groups=[create_process_event()],
            output_materials=[create_material()],
        )
        # Should not raise

    def test_empty_raw_materials_dict_raises_error(self):
        """Test that empty raw_materials dict raises ValueError."""
        with pytest.raises(ValueError, match="Experiment must have at least one raw material"):
            Experiment(
                raw_materials={},
                synthesis_groups=[create_process_event()],
                output_materials=[create_material()],
            )


class TestValidateSynthesisGroups:
    """Tests for validate_synthesis_groups validation."""

    def test_empty_dict_synthesis_groups_raises_error(self):
        """Test that empty synthesis_groups dict raises ValueError."""
        with pytest.raises(ValueError, match="Synthesis groups dict must not be empty"):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={},
                output_materials=[create_material(process=None)],
            )

    def test_list_synthesis_without_material_processes_is_valid(self):
        """Test that list synthesis with materials having no process is valid."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event(), create_process_event(ProcessKind.Annealing)],
            output_materials=[
                create_material(process=None, composition_str="Fe50Co50"),
                create_material(process=None, composition_str="Fe30Co70"),
            ],
        )
        # Should not raise

    def test_list_synthesis_with_material_process_raises_error(self):
        """Test that list synthesis with material having process raises ValueError."""
        with pytest.raises(
            ValueError,
            match="When synthesis_groups is a list, materials should not have a process",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[create_material(process="powder->melting")],
            )

    def test_list_synthesis_with_multiple_material_processes_raises_error(self):
        """Test that list synthesis with multiple materials having processes raises ValueError."""
        with pytest.raises(
            ValueError,
            match=r"When synthesis_groups is a list, materials should not have a process.*Found 2 material",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material(process="powder->melting"),
                    create_material(process="powder->annealing"),
                ],
            )

    def test_dict_synthesis_with_material_processes_is_valid(self):
        """Test that dict synthesis allows materials to have processes."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event("melting")],
                "annealing": [create_process_event(ProcessKind.Annealing)],
            },
            output_materials=[
                create_material(process="powder->melting"),
                create_material(process="powder->annealing"),
            ],
        )
        # Should not raise

    def test_dict_synthesis_without_material_processes_raises_error(self):
        """Test that dict synthesis with materials having no processes raises error for unused events."""
        with pytest.raises(
            ValueError,
            match="Synthesis group 'melting' is defined but never used by any material",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "melting": [create_process_event("melting")],
                },
                output_materials=[create_material(process=None)],
            )


class TestValidateAllDictSynthesisGroupsAreUsed:
    """Tests for validate_all_synthesis_groups_are_used validation."""

    def test_all_synthesis_groups_used_is_valid(self):
        """Test that all synthesis groups referenced by materials is valid."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event("melting")],
                "annealing": [create_process_event(ProcessKind.Annealing)],
            },
            output_materials=[
                create_material(process="powder->melting"),
                create_material(process="powder->annealing"),
            ],
        )
        # Should not raise

    def test_unused_synthesis_group_raises_error(self):
        """Test that unused synthesis group raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Synthesis group 'unused' is defined but never used by any material",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "melting": [create_process_event("melting")],
                    "unused": [create_process_event(ProcessKind.Annealing)],
                },
                output_materials=[create_material(process="powder->melting")],
            )

    def test_multiple_unused_synthesis_groups_raises_error(self):
        """Test that multiple unused synthesis groups raises error for first one."""
        with pytest.raises(ValueError, match="is defined but never used by any material"):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "melting": [create_process_event("melting")],
                    "unused1": [create_process_event(ProcessKind.Annealing)],
                    "unused2": [create_process_event("sintering")],
                },
                output_materials=[create_material(process="powder->melting")],
            )

    def test_multi_step_process_references_all_events(self):
        """Test that multi-step process can reference multiple events."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event("melting")],
                "annealing": [create_process_event(ProcessKind.Annealing)],
                "sintering": [create_process_event("sintering")],
            },
            output_materials=[
                create_material(process="powder->melting->annealing"),
                create_material(process="powder->melting->sintering"),
            ],
        )
        # Should not raise

    def test_list_synthesis_skips_this_validation(self):
        """Test that list synthesis_groups skips this validation."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[create_material(process=None)],
        )
        # Should not raise - list synthesis doesn't check for unused events


class TestValidateTemplateVariables:
    """Tests for _validate_template_variables validation."""

    def test_template_variable_used_in_temperature_is_valid(self):
        """Test that template variable used in temperature field is valid."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[create_material(process="powder->annealing[Temp=800]")],
        )
        # Should not raise

    def test_template_variable_unused_in_events_raises_error(self):
        """Test that template variable not used in process events raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Synthesis group 'annealing\\[Temp\\]' has template variable \\[Temp\\] but it's not used in any field of the process events",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "annealing[Temp]": [
                        # Temperature field does NOT use the template
                        create_process_event(ProcessKind.Annealing, temperature=Quantity(value="800", unit="degC"))
                    ],
                },
                output_materials=[create_material(process="powder->annealing[Temp=800]")],
            )

    def test_material_without_template_value_raises_error(self):
        """Test that material not providing template value raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Material process step 'annealing' references 'annealing\\[Temp\\]' but doesn't provide a value for \\[Temp\\]",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "annealing[Temp]": [
                        create_process_event(
                            ProcessKind.Annealing,
                            temperature=Quantity(value="[Temp]", unit="degC"),
                        )
                    ],
                },
                output_materials=[create_material(process="powder->annealing")],  # Missing [Temp=value]
            )

    def test_template_variable_in_description_is_valid(self):
        """Test that template variable can be used in description field."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]": [
                    ProcessEvent(
                        kind=ProcessKind.Annealing,
                        description="Annealing at [Temp] degrees",
                    )
                ],
            },
            output_materials=[create_material(process="powder->annealing[Temp=800]")],
        )
        # Should not raise

    def test_multiple_template_variables_all_must_be_used(self):
        """Test that when multiple templates exist, each must be validated."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
                "sintering[Time]": [
                    create_process_event(
                        "sintering",
                        duration=Quantity(value="[Time]", unit="h"),
                    )
                ],
            },
            output_materials=[
                create_material(process="powder->annealing[Temp=800]"),
                create_material(process="powder->sintering[Time=2]"),
            ],
        )
        # Should not raise

    def test_template_with_suffix_requires_matching_suffix(self):
        """Test that template with suffix in name requires matching suffix in material process."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]_v2": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[create_material(process="powder->annealing[Temp=800]_v2")],
        )
        # Should not raise

    def test_non_templated_synthesis_groups_skip_validation(self):
        """Test that synthesis groups without template variables skip this validation."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event("melting")],
                "annealing": [create_process_event(ProcessKind.Annealing)],
            },
            output_materials=[
                create_material(process="powder->melting"),
                create_material(process="powder->annealing"),
            ],
        )
        # Should not raise

    def test_list_synthesis_skips_template_validation(self):
        """Test that list synthesis_groups skips template variable validation."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[
                create_process_event(
                    ProcessKind.Annealing,
                    temperature=Quantity(value="[Temp]", unit="degC"),
                )
            ],
            output_materials=[create_material(process=None)],
        )
        # Should not raise - list synthesis doesn't validate templates

    def test_complex_multi_step_with_templates(self):
        """Test complex scenario with multi-step processes and templates."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event("melting")],
                "annealing[Temp]": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[
                create_material(process="powder->melting->annealing[Temp=800]"),
                create_material(process="powder->melting->annealing[Temp=900]"),
            ],
        )
        # Should not raise


class TestValidateMaterialVariablesMatchEventTemplates:
    """Tests for validate_material_variables_match_group_templates validation."""

    def test_material_with_valid_template_variable(self):
        """Test that material using a variable that matches the event template is valid."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[
                create_material(process="powder->annealing[Temp=800]"),
            ],
        )
        # Should not raise

    def test_material_with_undeclared_variable_raises_error(self):
        """Test that material using a variable not declared in event template raises ValueError."""
        with pytest.raises(
            ValueError,
            match=r"Material process step 'annealing\[Temp=800\]' assigns variable 'Temp' but synthesis group 'annealing' does not declare this template variable",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "annealing": [  # No template variable declared
                        create_process_event(ProcessKind.Annealing)
                    ],
                },
                output_materials=[
                    create_material(process="powder->annealing[Temp=800]"),  # But material tries to assign one
                ],
            )

    def test_material_with_wrong_variable_name_raises_error(self):
        """Test that material using wrong variable name raises ValueError."""
        with pytest.raises(
            ValueError,
            match=r"Material process step 'annealing\[Speed=100\]' assigns variable 'Speed' but synthesis group 'annealing\[Temp\]' does not declare this template variable",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "annealing[Temp]": [  # Template declares "Temp"
                        create_process_event(
                            ProcessKind.Annealing,
                            temperature=Quantity(value="[Temp]", unit="degC"),
                        )
                    ],
                },
                output_materials=[
                    create_material(process="powder->annealing[Speed=100]"),  # Material uses "Speed"
                ],
            )

    def test_material_without_brackets_skips_validation(self):
        """Test that materials without variable assignments skip this validation."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing": [create_process_event(ProcessKind.Annealing)],
            },
            output_materials=[
                create_material(process="powder->annealing"),  # No brackets
            ],
        )
        # Should not raise

    def test_multiple_variables_all_must_be_declared(self):
        """Test that all variables in multi-variable assignment must be declared."""
        with pytest.raises(
            ValueError,
            match=r"assigns variable 'Speed' but synthesis group .* does not declare this template variable",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "process[Temp]": [  # Only Temp declared
                        create_process_event(
                            "melting",
                            temperature=Quantity(value="[Temp]", unit="degC"),
                        )
                    ],
                },
                output_materials=[
                    create_material(process="powder->process[Temp=800,Speed=100]"),  # Speed not declared
                ],
            )

    def test_multi_step_process_validates_all_steps(self):
        """Test that all steps in a multi-step process are validated."""
        with pytest.raises(
            ValueError,
            match=r"Material process step 'annealing\[Speed=100\]' assigns variable 'Speed'",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "melting[Temp]": [
                        create_process_event(
                            "melting",
                            temperature=Quantity(value="[Temp]", unit="degC"),
                        )
                    ],
                    "annealing[Temp]": [
                        create_process_event(
                            ProcessKind.Annealing,
                            temperature=Quantity(value="[Temp]", unit="degC"),
                        )
                    ],
                },
                output_materials=[
                    create_material(
                        process="powder->melting[Temp=1500]->annealing[Speed=100]"
                    ),  # Second step uses wrong variable
                ],
            )

    def test_material_with_suffix_matches_event_with_suffix(self):
        """Test that materials with suffix match events with same suffix."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "annealing[Temp]_1": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[
                create_material(process="powder->annealing[Temp=800]_1"),
            ],
        )
        # Should not raise

    def test_list_synthesis_skips_this_validation(self):
        """Test that list synthesis_groups skips this validation."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[
                create_process_event("melting"),
            ],
            output_materials=[
                create_material(process=None),  # List synthesis, no process
            ],
        )
        # Should not raise


class TestValidationIntegration:
    """Integration tests combining multiple validation rules."""

    def test_complete_valid_experiment_with_dict_synthesis(self):
        """Test a complete valid experiment with dict synthesis."""
        _experiment = Experiment(
            raw_materials={
                "powder1": create_raw_material(RawMaterialKind.Powder),
            },
            synthesis_groups={
                "melting": [create_process_event("melting", temperature=Quantity(value="1500", unit="degC"))],
                "annealing[Temp]": [
                    create_process_event(
                        ProcessKind.Annealing,
                        temperature=Quantity(value="[Temp]", unit="degC"),
                    )
                ],
            },
            output_materials=[
                create_material(process="powder1->melting", composition_str="Fe50Co50"),
                create_material(process="powder1->melting->annealing[Temp=800]", composition_str="Fe30Co70"),
                create_material(process="powder1->annealing[Temp=900]", composition_str="Fe70Co30"),
            ],
        )
        # Should not raise

    def test_complete_valid_experiment_with_list_synthesis(self):
        """Test a complete valid experiment with list synthesis."""
        _experiment = Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[
                create_process_event("melting", temperature=Quantity(value="1500", unit="degC")),
                create_process_event(ProcessKind.Annealing, temperature=Quantity(value="800", unit="degC")),
            ],
            output_materials=[
                create_material(process=None, composition_str="Fe50Co50"),
                create_material(process=None, composition_str="Fe30Co70"),
            ],
        )
        # Should not raise

    def test_multiple_validation_errors_first_one_raised(self):
        """Test that when multiple validation errors exist, the first one is raised."""
        # This will fail on raw_materials validation first
        with pytest.raises(ValueError, match="Experiment must have at least one raw material"):
            Experiment(
                raw_materials={},  # Empty - will fail first
                synthesis_groups={
                    "unused": [create_process_event()],  # Would also fail - unused event
                },
                output_materials=[create_material(process="x->other")],
            )


class TestValidateProcessEventInputs:
    """Tests for validate_process_event_inputs validation."""

    def test_explicit_inputs_referencing_raw_materials(self):
        """Test that explicit inputs referencing raw materials are valid."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [
                    ProcessEvent(kind=ProcessKind.ArcMelting, inputs=["powder"]),
                    ProcessEvent(kind=ProcessKind.AsCast),
                ],
            },
            output_materials=[create_material(process="powder->melting")],
        )
        # Should not raise

    def test_explicit_inputs_referencing_named_materials(self):
        """Test that explicit inputs referencing named materials are valid."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [ProcessEvent(kind=ProcessKind.ArcMelting), ProcessEvent(kind=ProcessKind.AsCast)],
                "annealing": [ProcessEvent(kind=ProcessKind.Annealing, inputs=["ingot"])],
            },
            output_materials=[
                create_material(process="powder->melting", composition_str="Fe50Co50"),
                Material(
                    name="ingot",
                    process="powder->melting",
                    measurements=[CompMeasurement("Fe30Co70")],
                ),
                create_material(process="ingot->annealing", composition_str="Fe70Co30"),
            ],
        )
        # Should not raise

    def test_explicit_inputs_referencing_nonexistent_name_raises(self):
        """Test that explicit inputs referencing nonexistent name raises ValueError."""
        with pytest.raises(ValueError, match="does not reference a known raw material or named material"):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups={
                    "melting": [
                        ProcessEvent(kind=ProcessKind.ArcMelting, inputs=["nonexistent"]),
                        ProcessEvent(kind=ProcessKind.AsCast),
                    ],
                },
                output_materials=[create_material(process="powder->melting")],
            )

    def test_template_variable_inputs_referencing_named_materials(self):
        """Test that template variable inputs resolving to named materials are valid."""
        exp = Experiment(
            raw_materials={
                "powder_a": create_raw_material(),
                "powder_b": create_raw_material(),
            },
            synthesis_groups={
                "melting": [ProcessEvent(kind=ProcessKind.ArcMelting), ProcessEvent(kind=ProcessKind.AsCast)],
                "mixing[Feedstock]": [ProcessEvent(kind=ProcessKind.Mixing, inputs=["[Feedstock]"])],
            },
            output_materials=[
                Material(
                    name="ingot",
                    process="powder_a->melting",
                    measurements=[CompMeasurement("Fe50Co50")],
                ),
                create_material(process="powder_b->mixing[Feedstock=ingot]", composition_str="Fe70Co30"),
            ],
        )
        # Should not raise

        # Verify the resolved process events for the second material contain "ingot" as an input
        mixed_material = exp.output_materials[1]
        resolved_events = resolve_process_events(mixed_material, exp.synthesis_group_map)
        mixing_event = next(e for e in resolved_events if e.kind == ProcessKind.Mixing)
        assert "ingot" in mixing_event.inputs, (
            f"Expected 'ingot' in resolved inputs, got {mixing_event.inputs}"
        )

    def test_empty_inputs_passes_validation(self):
        """Test that empty inputs list passes validation."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups={
                "melting": [create_process_event(ProcessKind.ArcMelting), create_process_event(ProcessKind.AsCast)],
            },
            output_materials=[create_material(process="powder->melting")],
        )
        # Should not raise


class TestValidateMeasurementTypes:
    """Tests for runtime measurement type validation via __init_subclass__ on Material."""

    def test_base_material_skips_validation(self):
        """Base Material has _allowed_measurement_types=None, no validation."""
        assert Material._allowed_measurement_types is None
        # Base Material accepts any measurement types
        _material = create_material()

    def test_subclass_sets_allowed_measurement_types(self):
        """AlloyMaterial._allowed_measurement_types contains the 5 expected types."""
        expected_types = {CompMeasurement, Measurement, LatticeMeasurement, Configuration, GlobalLatticeParam}
        assert set(AlloyMaterial._allowed_measurement_types) == expected_types

    def test_valid_measurements_pass(self):
        """AlloyMaterial with CompMeasurement succeeds."""
        _material = AlloyMaterial(
            measurements=[CompMeasurement(Composition("Fe50Co50"))],
        )

    def test_invalid_measurement_raises(self):
        """A FakeMeasurement dataclass triggers ValueError."""

        @dataclass
        class FakeMeasurement:
            value: str = "fake"

        with pytest.raises(ValueError, match="not one of the allowed measurement types"):
            AlloyMaterial(
                measurements=[CompMeasurement(Composition("Fe50Co50")), FakeMeasurement()],
            )

    def test_invalid_in_named_material_includes_name(self):
        """Error message includes the material name when set."""

        @dataclass
        class FakeMeasurement:
            value: str = "fake"

        with pytest.raises(ValueError, match="Material 'my_alloy'"):
            AlloyMaterial(
                name="my_alloy",
                measurements=[CompMeasurement(Composition("Fe50Co50")), FakeMeasurement()],
            )


class TestGlobalLatticeParamPhaseFraction:
    def test_float_phase_fraction_raises(self):
        with pytest.raises(TypeError, match="phase_fraction must be a Quantity"):
            GlobalLatticeParam(phase_fraction=100.0)
