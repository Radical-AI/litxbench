from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CrysStruct, ProcessEvent, ProcessKind, Quantity, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    Hour,
    MegaPascal,
    Micrometer,
    percent,
)
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMaterial as Material,
    AlloyMeasurementKind,
    AlloyMeasurementMethod as MeasurementMethod,
    CompMeasurement,
    Configuration,
    Measurement,
    PhaseMeasurementKind,
)

experiments: list[Experiment] = [
    # Note: The 900°C/3min annealing mentioned in paper is from Li et al.'s prior work (refs 3,4), not this paper's samples.
    Experiment(
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_tension],
                method=MeasurementMethod.TensileTest,
                desc="From Microstructural and mechanical characterization: Dog-bone-shaped mini-tensile specimens (gage length 5mm, width 1.25mm, 1mm thick) tested at room temperature at initial strain rate of 10^-3 s^-1. Three samples tested per condition.",
            ),
            # machines=[Machine(methods=[MeasurementMethod.TensileTest])],
            AlloyDescriptionGroup(kinds=[ProcessKind.FrictionStirProcessing], desc="From table 1: Traverse speed 50.8 mm/min, plunge depth 3.65 mm, tilt angle 2.5°. Tool: shoulder diameter 12mm with tapered pin, root diameter 7.5mm, pin diameter 6mm, pin length 3.5mm."),
        ],
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified)},
        synthesis_groups={
            "cast_sheet": [
                ProcessEvent(kind=normalize(ProcessKind.InductionMelting, "Vacuum Induction Melting"), description="The TRIP HEA was produced by melting and casting in a vacuum induction furnace", source="Methods"),
                ProcessEvent(kind=ProcessKind.GravityCasting, source="The TRIP HEA was produced by melting and casting in a vacuum induction furnace"),
                ProcessEvent(kind=ProcessKind.HotRolling, temperature=Quantity(value=900, unit=Celsius), description="hot-rolled to a thickness reduction of 50% (from 40 to 20mm)", source="Methods->Materials and Processing"),
                ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1200, unit=Celsius), duration=Quantity(value=5, unit=Hour), description="In argon atmosphere", source="Methods"),
                ProcessEvent(kind=ProcessKind.WaterQuenching, description="Used ice water", source="Methods"),
                ProcessEvent(kind=ProcessKind.ElectricalDischargeMachining, description="sheets of 5 mm were machined out of the block by electro-discharge machining", source="Methods"),
            ],
            "FSP[RotationRate]": [
                ProcessEvent(kind=ProcessKind.FrictionStirProcessing, description="rotational rate is [RotationRate] revolutions/min", source="Methods"),
            ],
        },
        output_materials=[
            Material(
                process="elements->cast_sheet",
                name="as-homogenized",
                measurements=[
                    CompMeasurement("Fe50Mn30Co10Cr10", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.true_stress_tension, value=800, unit=MegaPascal, description="with uniform elongation of 35%", source="Stress-strain behavior paragraph"),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_tension,
                        value=198,
                        unit=MegaPascal,
                        temperature=ROOM_TEMPERATURE,
                        source="significant improvement of the 350 RPM treated sample led to a value of 298MPa compared to a value of 198MPa for the as-homogenized sample",
                    ),
                    Configuration(name="h.c.p. epsilon-phase", struct=CrysStruct.HCP),
                    Configuration(
                        name="f.c.c. gamma-phase",
                        struct=CrysStruct.FCC,
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.grain_size,
                                value="~100",
                                unit=Micrometer,
                                source="highlighting the drastic reduction in average grain size from ~100 µm to 6.5 and 5.2 µm, respectively. We know this grain size is on the FCC phase because we know 5.2 µm is on the FCC phase: 'The FSP engineered DP-HEA has a similar f.c.c γ average grain size (6.5μm)'",
                            ),
                        ],
                    ),
                ],
            ),
            # Note: We know the phases between the two samples because of this quote:
            # Figure 1a-c show electron back scattered diffraction (EBSD) maps for the as-homogenized and 350 and 650 rotations per minute (RPM) treated FSP samples, highlighting the drastic reduction in average grain size from ~100μm to 6.5 and 5.2μm, respectively.
            Material(
                process="elements->cast_sheet->FSP[RotationRate=350]",
                measurements=[
                    CompMeasurement("Fe50Mn30Co10Cr10", method=MeasurementMethod.Balance),
                    # CompositionMeasurement("Fe49.58Mn29.57Co10.82Cr10.03", method=MeasurementMethod.EDS),  # TODO: enable when we want to involve images
                    Measurement(kind=AlloyMeasurementKind.true_stress_tension, value=1400, unit=MegaPascal, description="at almost 45% elongation", source="Stress-strain behavior paragraph"),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_tension,
                        value=298,
                        unit=MegaPascal,
                        temperature=ROOM_TEMPERATURE,
                        source="significant improvement of the 350 RPM treated sample led to a value of 298MPa compared to a value of 198MPa for the as-homogenized sample",
                    ),
                    Configuration(
                        name="h.c.p. epsilon-phase",
                        struct=CrysStruct.HCP,
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value="~10",
                                unit=percent,
                                source="After FSP we find that the same alloy showed ~8 and ~10% of h.c.p. at similar grain sizes of ~5.2 and 6.5 μm, respectively.",
                            ),
                        ],
                    ),
                    Configuration(
                        name="f.c.c. gamma-phase",
                        struct=CrysStruct.FCC,
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value="~90", unit=percent, source="This enhanced combination of strength and ductility was partly attributed to ~90% f.c.c. γ-phase"),
                            Measurement(
                                kind=PhaseMeasurementKind.grain_size,
                                value=6.5,
                                unit=Micrometer,
                                source="We know this grain size is on the FCC phase because: 'The FSP engineered DP-HEA has a similar f.c.c γ average grain size (6.5μm)'",
                            ),
                        ],
                    ),
                ],
            ),
            Material(
                process="elements->cast_sheet->FSP[RotationRate=650]",
                measurements=[
                    CompMeasurement("Fe50Mn30Co10Cr10", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.true_stress_tension, value=1200, unit=MegaPascal, description="at almost 42% elongation", source="Stress-strain behavior paragraph"),
                    Configuration(
                        name="h.c.p. epsilon-phase",
                        struct=CrysStruct.HCP,
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value="~8",
                                unit=percent,
                                source="After FSP we find that the same alloy showed ~8 and ~10% of h.c.p. at similar grain sizes of ~5.2 and 6.5 μm, respectively.",
                            ),
                        ],
                    ),
                    Configuration(
                        name="f.c.c. gamma-phase",
                        struct=CrysStruct.FCC,
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value="~90",
                                unit=percent,
                                source="This enhanced combination of strength and ductility was partly attributed to ~90% f.c.c. γ-phase",
                            ),
                            Measurement(
                                kind=PhaseMeasurementKind.grain_size,
                                value=5.2,
                                unit=Micrometer,
                                source="maps for the as-homogenized and 350 and 650 rotations per minute (RPM) treated FSP samples, highlighting the drastic reduction in average grain size from ~100 µm to 6.5 and 5.2 µm, respectively",
                            ),
                        ],
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_tension,
                        value=398,  # Yes. this is calculated from the base yield strength. But I think it's fine since the paper explicitly give us the ~200Mpa increase. a few Mpa difference is not that big of a deal.
                        unit=MegaPascal,
                        temperature=ROOM_TEMPERATURE,
                        source="The 650 RPM treated sample showed ~200 MPa increase in YS (Fig. 2a) compared to the as-homogenized condition.",
                    ),
                ],
            ),
        ],
    )
]
