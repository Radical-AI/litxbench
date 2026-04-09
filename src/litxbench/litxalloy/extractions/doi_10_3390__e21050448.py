from pymatgen.core import Composition

from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CoreMeasurementValue, CrysStruct, GlobalLatticeParam, MeasurementStatistic, RawMaterial, RawMaterialKind
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
    Measurement,
    PhaseMeasurementKind,
    ProcessEvent,
    ProcessKind,
    Quantity,
)

experiments: list[Experiment] = [
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="of high purity")},
        descriptions=[
            # MeasurementMethod.XRD: "Phase structures were were obtained by image analysis using Imagepro software. Phase structures were identified by an X-ray identified by an X-ray diffractometer (XRD) (Rigaku D/MAX-2250, Tokyo, Japan)"  # TODO: uncomment when we have added XRD to the measurements
            # MeasurementMethod.TEM_EDS: "The standard bright-field images and diﬀraction patterns were obtained using a transmission electron obtained using a transmission electron microscope (Tecnai G2 F20 S-TWIN, FEI, Hillsboro, OR, USA)."  # TODO: uncomment when we have added TEM_EDS to the measurements
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_tension, AlloyMeasurementKind.ultimate_tensile_strength, AlloyMeasurementKind.fracture_strain_tension],
                method=MeasurementMethod.TensileTest,  # machines=[Machine(methods=[MeasurementMethod.TensileTest], model="3369", company="Instron")],
                desc="Tensile tests were performed with a loading strain rate of 10−3/s at room temperature",
            ),
        ],
        synthesis_groups={
            "create_as_extruded": [
                ProcessEvent(kind=ProcessKind.VacuumFurnace, description="Was a vacuum furnace", source="2. Experimental Procedures"),
                ProcessEvent(kind=ProcessKind.GasAtomization, description="After melting, the melt dropped through a ceramic tube and was atomized in high purity Ar with an atomization pressure was 4 MPa.", source="2. Experimental Procedures"),
                ProcessEvent(
                    kind=ProcessKind.HotExtrusion,
                    description="The dimensions of the stainless-steel mold used in the hot extrusion process is d60 × 150 mm^3. The powder is first loaded into a stainless steel can, pre-heated at 1473 K for 60 min, and sealed under vacuum. The enclosed powders were immediately subjected to hot extrusion with an extrusion ratio of 6 and a velocity of ~10 mm/s on a 2500 T hydraulic press.",
                    source="2. Experimental Procedures",
                ),
            ],
            "annealing[Temp]_72hrs": [
                ProcessEvent(kind=ProcessKind.Annealing, temperature=Quantity(value="[Temp]", unit=Celsius), duration=Quantity(value=72, unit=Hour), source="2. Experimental Procedures"),
                ProcessEvent(kind=ProcessKind.WaterQuenching, source="2. Experimental Procedures"),
            ],
        },
        output_materials=[
            Material(
                process="elements->create_as_extruded",
                name="as_extruded",
                measurements=[
                    CompMeasurement("CoCrFeNiMo0.2", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(struct=CrysStruct.FCC, source="Figure 1b shows the XRD patterns of the P/M CoCrFeNiMo0.2 HEA, where the alloy shows clearly a single FCC structure."),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~20", unit=Micrometer, source="the extruded alloy exhibits an equiaxed grain structure with an average grain size of approximately 20 μm", measurement_statistic=MeasurementStatistic.mean),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value="~400", unit=MegaPascal, source="3.2. Mechanical Properties"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value="~781", unit=MegaPascal, source="3.2. Mechanical Properties"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="elongation to failure"), value="~55.6", unit=percent, source="3.2. Mechanical Properties"),
                ],
            ),
            Material(
                process="as_extruded->annealing[Temp=700]_72hrs",
                measurements=[
                    CompMeasurement("CoCrFeNiMo0.2", method=MeasurementMethod.Balance),
                    # they also have volume fractions of the phase, but these are in images
                    Configuration(
                        name="matrix",
                        struct=CrysStruct.FCC,
                        tags={ConfigTag.Matrix},
                        source="We know it's FCC because: 'Figure 1b shows the XRD patterns of the P/M CoCrFeNiMo0.2 HEA, where the alloy shows clearly a single FCC structure.'",
                        measurements=[
                            CompMeasurement(
                                Composition({"Mo": 6.18, "Cr": 22.08, "Fe": 25.71, "Co": 24.51, "Ni": 21.52}),
                                method=MeasurementMethod.EDS,
                                source="Composition from Table 1. We know this is the matrix (EDS spot 2) because it has low Mo (6.18%) and roughly equal Co/Cr/Fe/Ni, which matches the overall alloy rather than a precipitate.",
                            ),
                        ],
                    ),
                    Configuration(
                        name="sigma phase",
                        tags={ConfigTag.Precipitate},
                        within="matrix",
                        measurements=[
                            CompMeasurement(
                                Composition({"Mo": 34.56, "Cr": 18.03, "Fe": 20.38, "Co": 17.53, "Ni": 9.49}),
                                method=MeasurementMethod.EDS,
                                source="Composition from Table 1. We know this is the σ phase (EDS spot 1) because: 'The EDS analysis results in Table 1 clearly indicates that the chemical composition of the precipitates contains a high concentration of Mo, which is very close to the σ phase reported by Shun et al.' and 'The selected electron diffraction pattern ... also confirms that the white precipitates are σ phase.'",
                            ),
                            Measurement(
                                kind=PhaseMeasurementKind.phase_size,
                                value="<0.5",
                                unit=Micrometer,
                                source="the size of the σ phase is less than 0.5 µm as the annealing temperature at 700◦C",
                            ),
                        ],
                    ),
                ],
            ),
            Material(
                process="as_extruded->annealing[Temp=800]_72hrs",
                measurements=[
                    CompMeasurement("CoCrFeNiMo0.2", method=MeasurementMethod.Balance),
                    Configuration(
                        name="sigma phase",
                        measurements=[
                            # you can also see this volume fraction stuff in figure 5 b)
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value="~14",
                                unit=percent,
                                description="At 800 ◦C, the volume fraction of the precipitates gradually increases as the annealing time is prolonged, eventually reaching a saturated stable value about 14%",
                            ),
                            # The paper says "As shown in Figure 2b, white areas generally appear at the grain boundaries
                            # and the size is less than 1 μm." However, we can't confidently attribute this size to σ phase
                            # from text alone. The σ phase is identified via TEM/EDS on the 700°C sample (Table 1, Figure 3),
                            # and "Figure 3 also confirms that the white precipitates are σ phase" refers to a TEM image.
                            # "White" in TEM vs SEM can mean different things depending on imaging mode, so we can't
                            # assume "white areas" in the SEM Figure 2b are the same as "white precipitates" in TEM Figure 3.
                            # Measurement(
                            #     kind=PhaseMeasurementKind.phase_size,
                            #     value="<1",
                            #     unit=Micrometer,
                            #     source="As shown in Figure 2b, white areas generally appear at the grain boundaries and the size is less than 1 μm.",
                            # ),
                        ],
                    ),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value="~850", unit=MegaPascal, source="Abstract"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="elongation"), value="~30", unit=percent, source="Abstract"),
                ],
            ),
            Material(
                process="as_extruded->annealing[Temp=900]_72hrs",
                measurements=[
                    CompMeasurement("CoCrFeNiMo0.2", method=MeasurementMethod.Balance),
                ],
            ),
            Material(
                process="as_extruded->annealing[Temp=1000]_72hrs",
                measurements=[
                    CompMeasurement("CoCrFeNiMo0.2", method=MeasurementMethod.Balance),
                    # they also have volume fractions of the phase, but these are in images
                    Configuration(
                        name="sigma phase",
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.phase_size,
                                value=3.7,
                                unit=Micrometer,
                                source="When the annealing temperature increases to 1000 °C, the size of the σ phase reaches to 3.7 µm.",
                            ),
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.phase_size,
                                unit=Micrometer,
                                source="As the annealing temperature increased up to 1000◦C, the size of these white areas is rapidly coarsened to 3–5 microns.",
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=3),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=5),
                                ],
                            ),
                        ],
                    ),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="plasticity"),
                        value="~65",
                        unit=percent,
                        source="Since the annealing temperature increases up to 1000 ◦C, the yield strength and ultimate tensile strength is significantly decreased, while the plasticity is correspondingly increased to as high as 65%",
                    ),
                ],
            ),
        ],
    )
]
