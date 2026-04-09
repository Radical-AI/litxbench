import pytest
from pymatgen.core import Lattice
from pymatgen.core.composition import Composition

from litxbench.core.models import (
    CompMeasurement,
    CoreMeasurements,
    CoreMeasurementValue,
    GlobalLatticeParam,
    LatticeMeasurement,
    Measurement,
    MeasurementMethod,
    MeasurementStatistic,
)
from litxbench.core.units import ureg
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMeasurementKind,
    Material,
    PhaseMeasurementKind,
    ProcessEvent,
    ProcessKind,
    RawMaterial,
    RawMaterialKind,
)


# Helper functions to create test fixtures
def create_raw_material(kind: RawMaterialKind = RawMaterialKind.Powder) -> RawMaterial:
    """Create a basic raw material for testing."""
    return RawMaterial(kind=kind, description="Test material")


def create_process_event(kind: ProcessKind | str = ProcessKind.Annealing) -> ProcessEvent:
    """Create a basic process event for testing."""
    return ProcessEvent(kind=kind, description="Test process")


def create_material_with_measurements(measurements: list[CoreMeasurements]) -> Material[CoreMeasurements]:
    """Create a material with specified measurements."""
    # Ensure we always have a composition measurement
    if not any(isinstance(m, CompMeasurement) for m in measurements):
        measurements = [CompMeasurement(Composition("Fe50Co50"))] + measurements
    return Material(process=None, measurements=measurements)


class TestValidateDescriptionGroups:
    """Tests for validate_description_groups validation."""

    def test_valid_kinds_and_classes(self):
        """Test that valid measurement kinds and classes are accepted."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa),
                        GlobalLatticeParam(lattice=LatticeMeasurement(lattice=Lattice.cubic(3.5))),
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], desc="Hardness description"),
                AlloyDescriptionGroup(kinds=[GlobalLatticeParam], desc="Lattice param description"),
            ],
        )
        # Should not raise

    def test_invalid_kinds_raise_error(self):
        """Test that invalid measurement kinds raise ValueError."""
        with pytest.raises(
            ValueError,
            match="Each descriptions kind must reference a measurement, process, or measurement method that appears in the experiment",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], desc="Valid description"),
                    AlloyDescriptionGroup(
                        kinds=[AlloyMeasurementKind.yield_strength_tension], desc="Invalid - doesn't exist"
                    ),
                ],
            )

    def test_group_measurements_validated_by_inner_kind(self):
        """Test that group measurements are validated by their inner measurement kind."""
        # Valid group measurements
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        *Measurement.group_measurements(
                            kind=PhaseMeasurementKind.grain_size,
                            unit=ureg.micrometer,
                            values=[
                                CoreMeasurementValue(statistic=MeasurementStatistic.mean, value=50),
                                CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=60),
                            ],
                        ),
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(kinds=[PhaseMeasurementKind.grain_size], desc="Grain size measured via XRD"),
            ],
        )
        # Should not raise

        # Invalid kind in descriptions
        with pytest.raises(
            ValueError, match="Each descriptions kind must reference a measurement, process, or measurement method"
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [
                            Measurement(
                                kind=PhaseMeasurementKind.grain_size,
                                value=50,
                                unit=ureg.micrometer,
                                measurement_statistic=MeasurementStatistic.mean,
                            )
                        ]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], desc="Wrong kind"),
                ],
            )

    def test_valid_process_kind(self):
        """Test that a ProcessKind is accepted when it appears in synthesis groups."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[
                ProcessEvent(kind=ProcessKind.Grinding, description="400 mesh sandpaper"),
                ProcessEvent(kind=ProcessKind.Annealing, description="Heat treatment"),
            ],
            output_materials=[
                create_material_with_measurements(
                    [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(kinds=[ProcessKind.Grinding], desc="performed on a grinding wheel"),
            ],
        )
        # Should not raise

    def test_invalid_process_kind_raises_error(self):
        """Test that a ProcessKind raises ValueError when it doesn't appear in synthesis groups."""
        with pytest.raises(
            ValueError,
            match="Each descriptions kind must reference a measurement, process, or measurement method that appears in the experiment",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],  # Only has Annealing
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(kinds=[ProcessKind.Grinding], desc="performed on a grinding wheel"),
                ],
            )

    def test_mixed_process_kind_and_measurement_kinds(self):
        """Test that ProcessKind and measurement kinds can be mixed in descriptions."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[ProcessEvent(kind=ProcessKind.Grinding, description="sandpaper")],
            output_materials=[
                create_material_with_measurements(
                    [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(
                    kinds=[ProcessKind.Grinding, AlloyMeasurementKind.vickers_hardness], desc="Mixed description"
                ),
            ],
        )
        # Should not raise

    def test_empty_descriptions_are_valid(self):
        """Test that empty descriptions list is valid."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                )
            ],
            descriptions=[],
        )

    def test_valid_measurement_method(self):
        """Test that a MeasurementMethod enum is accepted when a measurement uses that measurement_method."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(
                            kind=AlloyMeasurementKind.vickers_hardness,
                            value=100,
                            unit=ureg.GPa,
                            measurement_method=MeasurementMethod.XRD,
                        )
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(kinds=[MeasurementMethod.XRD], desc="Bruker D8 Advance diffractometer"),
            ],
        )
        # Should not raise

    def test_invalid_measurement_method_raises_error(self):
        """Test that a MeasurementMethod enum raises ValueError when no measurement uses that measurement_method."""
        with pytest.raises(
            ValueError,
            match="Each descriptions kind must reference a measurement, process, or measurement method that appears in the experiment",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(kinds=[MeasurementMethod.XRD], desc="Bruker D8 Advance diffractometer"),
                ],
            )

    def test_valid_group_name_string_key(self):
        """Test that a string key matching a group_name is accepted."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(
                            kind=AlloyMeasurementKind.vickers_hardness,
                            value=100,
                            unit=ureg.GPa,
                            group_name="Bruker D8",
                        )
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(
                    kinds=["Bruker D8"], desc="Bruker D8 Advance diffractometer with Cu K-alpha radiation"
                ),
            ],
        )
        # Should not raise

    def test_invalid_group_name_string_key_raises_error(self):
        """Test that a string key not matching any group_name or measurement kind raises ValueError."""
        with pytest.raises(
            ValueError,
            match="Each descriptions kind must reference a measurement, process, or measurement method that appears in the experiment",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(kinds=["Nonexistent Machine"], desc="Some description"),
                ],
            )

    def test_mixed_measurement_method_and_group_name_keys(self):
        """Test that measurement_method enums and group_name strings can be mixed with other key types."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[
                ProcessEvent(kind=ProcessKind.Grinding, description="sandpaper"),
            ],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(
                            kind=AlloyMeasurementKind.vickers_hardness,
                            value=100,
                            unit=ureg.GPa,
                            measurement_method=MeasurementMethod.XRD,
                            group_name="Bruker D8",
                        ),
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], desc="Hardness description"),
                AlloyDescriptionGroup(kinds=[MeasurementMethod.XRD], desc="XRD machine description"),
                AlloyDescriptionGroup(kinds=["Bruker D8"], desc="Specific machine description"),
                AlloyDescriptionGroup(kinds=[ProcessKind.Grinding], desc="Grinding description"),
            ],
        )
        # Should not raise

    def test_valid_group_name_field(self):
        """Test that group_name field on DescriptionGroup is accepted when a measurement has that group_name."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(
                            kind=AlloyMeasurementKind.vickers_hardness,
                            value=100,
                            unit=ureg.GPa,
                            group_name="XRD measurements",
                        )
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(group_name="XRD measurements", desc="Measured using Bruker D8 Advance"),
            ],
        )
        # Should not raise

    def test_invalid_group_name_field_raises_error(self):
        """Test that group_name field raises ValueError when no measurement has that group_name."""
        with pytest.raises(
            ValueError,
            match="Each descriptions group_name must match a group_name on at least one measurement",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(group_name="Nonexistent group", desc="Some description"),
                ],
            )

    def test_group_name_field_with_no_group_names_in_measurements(self):
        """Test helpful error message when no measurements have group_name set."""
        with pytest.raises(
            ValueError,
            match="No measurements have a group_name set",
        ):
            Experiment(
                raw_materials={"powder": create_raw_material()},
                synthesis_groups=[create_process_event()],
                output_materials=[
                    create_material_with_measurements(
                        [Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=100, unit=ureg.GPa)]
                    )
                ],
                descriptions=[
                    AlloyDescriptionGroup(group_name="some group", desc="Some description"),
                ],
            )

    def test_group_name_field_combined_with_kinds(self):
        """Test that group_name field works alongside kinds."""
        Experiment(
            raw_materials={"powder": create_raw_material()},
            synthesis_groups=[create_process_event()],
            output_materials=[
                create_material_with_measurements(
                    [
                        Measurement(
                            kind=AlloyMeasurementKind.vickers_hardness,
                            value=100,
                            unit=ureg.GPa,
                            group_name="hardness group",
                        )
                    ]
                )
            ],
            descriptions=[
                AlloyDescriptionGroup(
                    kinds=[AlloyMeasurementKind.vickers_hardness],
                    group_name="hardness group",
                    desc="Hardness measured with specific setup",
                ),
            ],
        )
        # Should not raise
