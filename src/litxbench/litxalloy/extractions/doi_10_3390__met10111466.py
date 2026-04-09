from litxbench.core.extraction_utils import balance_composition, normalize
from litxbench.core.models import CompMeasurement, Configuration, CoreMeasurementValue, MeasurementStatistic, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    Hour,
    Micrometer,
    percent,
)
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMaterial as Material,
    AlloyMeasurementMethod as MeasurementMethod,
    Measurement,
    PhaseMeasurementKind,
    ProcessEvent,
    ProcessKind,
    Quantity,
)

experiments: list[Experiment] = [
    Experiment(
        raw_materials={"workpiece": RawMaterial(kind=RawMaterialKind.Ingot, description="They started with an IN718 alloy with an initial height of 150 mm and a diameter of 100 mm ", source="2 Experimental")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[PhaseMeasurementKind.grain_size, PhaseMeasurementKind.volume_fraction, "CSL sigma 3 boundary fraction", "CSL Σ9 boundary fraction", "average angle misorientation < 1°"],
                method=MeasurementMethod.EBSD,
                # machines=[Machine(methods=[MeasurementMethod.EBSD])],
                desc="Electron backscattered diffraction (EBSD) technique used for microstructural characterization. Grain size measured according to ASTM E-112 comparison method at 100x magnification. CSL boundaries and phase volume fractions identified via orientation imaging microscopy (OIM). Grain boundaries separated at 2° (sub-grains) and 8° (recrystallized from deformed). grain boundaries with disorientations < 15◦ are considered LAGB limits, while boundaries with disorientations > 15◦ are considered random HAGB limits",
            ),
        ],
        synthesis_groups={
            "press": [
                ProcessEvent(
                    kind=ProcessKind.Press,
                    temperature=Quantity(value=980, unit=Celsius),
                    description="Used an industrial hydraulic (FRISA Aerospace, Santa Catarina, Mexico) press to reduce the height by 73%. It was deformed at a strain rate of 0.13s^{-1}",
                    source="2. Materials and Methods",
                ),
                ProcessEvent(kind=ProcessKind.Cut, description="The piece was cut and macro-etched to obtain deformation flow patterns", source="2. Materials and Methods"),
                ProcessEvent(kind=ProcessKind.Etching, description="The piece was cut and macro-etched to obtain deformation flow patterns", source="2. Materials and Methods"),
            ],
            "heat_treatment": [
                ProcessEvent(
                    kind=ProcessKind.SolutionHeatTreatment,
                    temperature=Quantity(value=1100, unit=Celsius),
                    duration=Quantity(value=1, unit=Hour),
                    description="They were subjected to DP718 consisting of a solution treatment at 1100 ◦C for 1 h, ",
                    source="2. Materials and Methods",
                ),
                ProcessEvent(kind=ProcessKind.WaterQuenching, source="2. Materials and Methods"),
                ProcessEvent(
                    kind=normalize(val=ProcessKind.Annealing, val_in_paper="aging treatment"),
                    temperature=Quantity(value=900, unit=Celsius),
                    duration=Quantity(value=24, unit=Hour),
                    source="2. Materials and Methods",
                ),
                ProcessEvent(kind=ProcessKind.WaterQuenching, source="2. Materials and Methods"),
            ],
            "compress_below_delta_solvus": [ProcessEvent(kind=ProcessKind.Press, temperature=Quantity(value=960, unit=Celsius), description=f"tested at 0.001 s^{-1} and compressed to a total strain of 0.6", source="2. Materials and Methods")],
            "compress_above_delta_solvus": [ProcessEvent(kind=ProcessKind.Press, temperature=Quantity(value=1020, unit=Celsius), description=f"tested at 0.01 s^{-1} and compressed to a total strain of 0.6", source="2. Materials and Methods")],
        },
        output_materials=[
            # The paper (section 3.1, Figure 3) describes "a sample with delta-processing treatment
            # but without deformation" with an average grain size of 39.5 µm before compression testing.
            # This is NOT attributed to sample A or B specifically — it's a general characterization of
            # the delta-processed state. We create a separate sample for it rather than adding it to both
            # sample_a_after_heat_treatment and sample_b_after_heat_treatment, because:
            # 1. The paper says "a sample" (singular), not both A and B
            # 2. Samples A and B have different ASTM grain sizes after heat treatment (A: 127 µm, B: 90 µm)
            #    so this 39.5 µm average is from a separate EBSD distribution analysis, not from Table 1
            Material(
                process="workpiece->press->heat_treatment",
                name="delta_processed_before_compression",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value=39.5, unit=Micrometer, source="3.1. Grains and Grain Boundaries Behavior of the γ-Phase with Delta-Processing"),
                    # The paper used EBSD to classify each grain by how deformed it is:
                    # - "recrystallized" = fresh, strain-free grains (formed after heat treatment)
                    # - "sub-structured" = grains with some internal misorientation (partial recovery)
                    # - "deformed" = heavily strained grains with lots of internal misorientation
                    # Before compression, the delta-processing heat treatment left the sample almost
                    # fully recrystallized (95%), which makes sense since it was solution-treated and aged
                    # but not yet mechanically deformed. After compression, the fractions shift dramatically
                    # toward deformed grains.
                    # CSL sigma 3 boundaries are twin boundaries — a specific type of grain boundary where
                    # the two grains are mirror images of each other. They form naturally during
                    # recrystallization and annealing in FCC metals like nickel alloys.
                    Configuration(
                        name="recrystallized grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=95, unit=percent, source="3.1. Grains and Grain Boundaries Behavior of the γ-Phase with Delta-Processing: 95% of the grains are recrystallized, 5% are sub-structured grains"),
                        ],
                    ),
                    Configuration(
                        name="sub-structured grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=5, unit=percent, source="3.1. Grains and Grain Boundaries Behavior of the γ-Phase with Delta-Processing: 95% of the grains are recrystallized, 5% are sub-structured grains"),
                        ],
                    ),
                    Measurement(kind="CSL sigma 3 boundary fraction", value=46, unit=percent, source="3.1: 46% of the CSL boundaries are of the sigma 3 type (in red), i.e., annealing twins"),
                    Measurement(kind="CSL Σ9 boundary fraction", value=2, unit=percent, source="3.1: The second CSL in importance in Figure 7a is the Σ9 boundaries with a presence of approximately 2%"),
                ],
            ),
            Material(
                process="workpiece->press",
                name="sample_a_after_press",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.mean, value=45, description="This is an ASTM grain size of 6"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=127, description="This is an ASTM grain size of 3"),
                        ],
                    ),
                ],
            ),
            Material(
                process="workpiece->press",
                name="sample_b_after_press",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=70, value=31, description="This is an ASTM grain size of 7"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=30, value=45, description="This is an ASTM grain size of 6"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=63, description="This is an ASTM grain size of 5"),
                        ],
                    ),
                ],
            ),
            Material(
                process="sample_a_after_press->heat_treatment",
                name="sample_a_after_heat_treatment",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.mean, value=127, description="This is an ASTM grain size of 3"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=180, description="This is an ASTM grain size of 2"),
                        ],
                    ),
                ],
            ),
            Material(
                process="sample_b_after_press->heat_treatment",
                name="sample_b_after_heat_treatment",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.mean, value=90, description="This is an ASTM grain size of 4"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=127, description="This is an ASTM grain size of 3"),
                        ],
                    ),
                ],
            ),
            Material(
                process="sample_a_after_heat_treatment->compress_below_delta_solvus",
                name="sample_a_after_compress_below_delta_solvus",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    # The microstructure is bimodal after dynamic recrystallization (DRX):
                    # - The ASTM E-112 comparison method (optical, 100x) captures the remaining larger
                    #   un-recrystallized grain population that dominates the visual field
                    # - The EBSD average measures ALL grains including the fine DRX grains that formed
                    #   as "necklaces" around the deformed grains, giving a much smaller average
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        group_name="ASTM E-112 optical comparison",
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=60, value=45, description="ASTM grain size 6 — remaining un-recrystallized grain population"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=40, value=16, description="Remaining un-recrystallized grain population (ASTM number not stated in paper)"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=63, description="ASTM grain size 5 (ALA) — largest grains visible"),
                        ],
                    ),
                    Measurement(
                        kind=PhaseMeasurementKind.grain_size,
                        value=10,
                        unit=Micrometer,
                        group_name="EBSD",
                        measurement_statistic=MeasurementStatistic.mean,
                        description=(
                            "EBSD-measured average grain size. Much smaller than the ASTM values (45 μm) because "
                            "EBSD captures every grain in the scan, including the many fine grains that nucleated "
                            "at original grain boundaries via discontinuous dynamic recrystallization (DRX) during "
                            "hot compression. The ASTM E-112 optical comparison method mainly characterizes the "
                            "larger un-recrystallized grain population. The resulting microstructure is bimodal: "
                            "large remnant grains with a 'necklace' of fine DRX grains around them."
                        ),
                        source=(
                            "3.1: 'after deformation, this average grain size goes down to 10μm. "
                            "...the microstructure switches to 60% deformed grains, 20% recrystallized grains, and 20% sub-structured grains. "
                            "...recrystallized grains (the blue ones) form a sort of necklace around deformed grains. "
                            "Such a topology leads to assuming that the recrystallization mechanisms must be categorized as discontinuous (or classical) dynamic recrystallization...which leads to the nucleation of new grains at the initial grain boundaries'"
                        ),
                    ),
                    Configuration(
                        name="deformed grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=60, unit=percent, source="3.1: the microstructure switches to 60% deformed grains, 20% recrystallized grains, and 20% sub-structured grains"),
                        ],
                    ),
                    Configuration(
                        name="recrystallized grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=20, unit=percent, source="3.1: the microstructure switches to 60% deformed grains, 20% recrystallized grains, and 20% sub-structured grains"),
                        ],
                    ),
                    Configuration(
                        name="sub-structured grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=20, unit=percent, source="3.1: the microstructure switches to 60% deformed grains, 20% recrystallized grains, and 20% sub-structured grains"),
                        ],
                    ),
                    Measurement(kind="CSL sigma 3 boundary fraction", value=3.5, unit=percent, source="3.1: There is a noticeable decrease in the percentage of twins sigma 3 to 3.5%"),
                ],
            ),
            Material(
                process="sample_b_after_heat_treatment->compress_above_delta_solvus",
                name="sample_b_after_compress_above_delta_solvus",
                measurements=[
                    CompMeasurement(balance_composition(main_element="Ni", additions={"Cr": 17.96, "Fe": 18.72, "Nb": 5.41, "Al": 0.51, "Ti": 1.01, "Mo": 2.88})),
                    # The microstructure is bimodal after dynamic recrystallization (DRX):
                    # - The ASTM E-112 comparison method (optical, 100x) captures the remaining larger
                    #   un-recrystallized grain population that dominates the visual field
                    # - The EBSD average measures ALL grains including the fine DRX grains that formed
                    #   around deformed grains, giving a much smaller average (13 μm vs 90 μm)
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        group_name="ASTM E-112 optical comparison",
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=70, value=90, description="ASTM grain size 4 — remaining un-recrystallized grain population"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.percentile, percentile=30, value=63, description="ASTM grain size 5 — remaining un-recrystallized grain population"),
                        ],
                    ),
                    Measurement(
                        kind=PhaseMeasurementKind.grain_size,
                        value=13,
                        unit=Micrometer,
                        group_name="EBSD",
                        measurement_statistic=MeasurementStatistic.mean,
                        description=(
                            "EBSD-measured average grain size. Much smaller than the ASTM values (90 μm) because "
                            "EBSD captures every grain in the scan, including the many fine grains that nucleated "
                            "at original grain boundaries via discontinuous dynamic recrystallization (DRX) during "
                            "hot compression. The ASTM E-112 optical comparison method mainly characterizes the "
                            "larger un-recrystallized grain population. The resulting microstructure is bimodal: "
                            "large remnant grains with a 'necklace' of fine DRX grains around them."
                        ),
                        source=(
                            "3.1: 'The average grain size of deformed Sample B is 13μm. "
                            "...20% of grains are recrystallized, 35% sub-structured, and 45% deformed.' "
                            "The DRX justification comes from Sample A's analysis in the same section: "
                            "'recrystallized grains (the blue ones) form a sort of necklace around deformed grains. "
                            "Such a topology leads to assuming that the recrystallization mechanisms must be categorized as discontinuous (or classical) dynamic recrystallization...which leads to the nucleation of new grains at the initial grain boundaries'"
                        ),
                    ),
                    Configuration(
                        name="deformed grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=45, unit=percent, source="3.1: 20% of grains are recrystallized, 35% sub-structured, and 45% deformed"),
                        ],
                    ),
                    Configuration(
                        name="recrystallized grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=20, unit=percent, source="3.1: 20% of grains are recrystallized, 35% sub-structured, and 45% deformed"),
                        ],
                    ),
                    Configuration(
                        name="sub-structured grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=35, unit=percent, source="3.1: 20% of grains are recrystallized, 35% sub-structured, and 45% deformed"),
                        ],
                    ),
                    # I think this is talking about the gamma phase? Ni3Nb is an ordered and orthorhombic phase, having the space group Pmmn n◦59, and the following lattice constants: a = 5.114 Å, b = 4.244 Å, and c = 4.538 Å
                    Configuration(
                        name="gamma phase",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=91.1, unit=percent),
                        ],
                    ),
                    Configuration(
                        name="delta phase",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=8.95, unit=percent, description="This is a delta phase fraction"),
                        ],
                    ),
                    Configuration(
                        name="gamma phase misorientation",
                        measurements=[
                            Measurement(kind="average angle misorientation < 1°", value=80, unit=percent, source="3.2: The highest percentage of average angle misorientation of the γ-phase of 80% corresponds to angles < 1° (blue), as illustrated in Figure 11b"),
                        ],
                    ),
                    Configuration(
                        name="delta phase misorientation",
                        measurements=[
                            Measurement(kind="average angle misorientation < 1°", value=12, unit=percent, source="3.2: the δ-phase presents a percentage on average of 12% angle misorientation < 1° (red tones), as shown in Figure 11c"),
                        ],
                    ),
                ],
            ),
        ],
    )
]
