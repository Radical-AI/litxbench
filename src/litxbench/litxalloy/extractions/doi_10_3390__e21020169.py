from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    Hour,
    MegaPascal,
    Micrometer,
    Nanometer,
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
    # experiment 1 is for the base alloy. Al10Co25Cr8Fe15Ni36Ti6
    Experiment(
        # there are more processing details, but we can add them later (depends on what you care about)
        # rature. Tensile tests were performed deformation rate of 0.01 mm/s (corresponding to 1.3 ×10−3 1/s)
        # There are many plots with mechanical properties. We should probably add them when we add figure support.
        # The annealing step 900◦C/50 h was taken from the initial heat treatment, where γ´-particles precipitate in the fcc-matrix.
        # consider adding this: While the deviation is 50 MPa and 8% respectively in CC-state at the most, the maximum deviation in the DS-state is only 16 MPa and 5%.
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="purity of 99.99%")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.ultimate_tensile_strength, AlloyMeasurementKind.yield_strength_tension, AlloyMeasurementKind.fracture_strain_tension],
                method=MeasurementMethod.TensileTest,
                # machines=[Machine(methods=[MeasurementMethod.TensileTest])],
                desc="Tensile tests performed at deformation rate of 0.01 mm/s (corresponding to 1.3 × 10^{-3} s^{-1}). Flat specimens with square cross section 1.0 × 1.9 mm^2, gauge length 8 mm, total length 25 mm. Type-S thermocouple welded for temperature regulation. A load cell with a high-resolution camera were logging about four pairs of values for stress and strain in one second.",
            ),
            AlloyDescriptionGroup(
                kinds=[PhaseMeasurementKind.grain_size, PhaseMeasurementKind.volume_fraction],
                method=MeasurementMethod.SEM,
                # machines=[Machine(methods=[MeasurementMethod.SEM], model="1540EsB", company="Zeiss")],
                desc="SEM operating at 30 kV with SE2-detector. Precipitate size and volume fraction determined using Weka segmentation method in Fiji/ImageJ. More than 500 particles per state were analyzed.",
            ),
        ],
        synthesis_groups={
            "melt": [
                ProcessEvent(kind=ProcessKind.UltrasonicBath, description="cleaned in ethanol in an ultrasonic bath", source="2.1. Alloy Preparation"),
                ProcessEvent(
                    kind=ProcessKind.InductionMelting,
                    description="The material was distributed randomly in a ceramic crucible in the middle of a water-cooled Cu-coil. After evacuating the chamber twice to a pressure of 5·10^{-4} mbar it was flooded with argon to prevent the evaporation of elements, especially chromium. The ceramic mold was heated up to a temperature of 1400 °C by a second coil and a graphite receptor, thus the material remained in liquid state after casting. So the 1400 C is NOT the actual melting temperature - just the temp of the graphite receptor",
                    temperature=Quantity(value=1400, unit=Celsius),
                    source="2.1. Alloy Preparation",
                ),
            ],
            "conventionally_cast": [
                ProcessEvent(kind=ProcessKind.AsCast, source="3.2. Impact of Bridgman Process on Mechanical Properties: The base alloy was cast twice, conventionally cast"),
            ],
            "directional_solidification": [
                ProcessEvent(
                    kind=ProcessKind.DirectionalSolidification,
                    description="To achieve directionally solidified grains in the [001]-direction, the Bridgman process was used and the mold was withdrawn through a water cooled baffle with a speed of 3 mm/min. The product are cast rods, with a diameter of 20 mm and a length of about 110 mm",
                    source="2.1. Alloy Preparation",
                ),
            ],
            # these homogenization steps were to prevent eutectic formation determined by differential scanning calorimetry.
            # Base alloy and Mo alloy use 1220°C, Hf alloy uses 1140°C
            "homogenization_base": [
                ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1220, unit=Celsius), duration=Quantity(value=20, unit=Hour), source="2.1. Alloy Preparation"),
            ],
            "homogenization_hf": [
                ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1140, unit=Celsius), duration=Quantity(value=20, unit=Hour), source="2.1. Alloy Preparation"),
            ],
            "annealing_900c_50h": [
                ProcessEvent(
                    kind=ProcessKind.Annealing,
                    temperature=Quantity(value=900, unit=Celsius),
                    duration=Quantity(value=50, unit=Hour),
                    description="After heat treatment the rods cooled down to room temperature in the furnace",
                    source="2.1. Alloy Preparation",
                ),
            ],
            "annealing_950c_100h": [
                ProcessEvent(
                    kind=ProcessKind.Annealing,
                    temperature=Quantity(value=950, unit=Celsius),
                    duration=Quantity(value=100, unit=Hour),
                    description="After heat treatment the rods cooled down to room temperature in the furnace",
                    source="2.1. Alloy Preparation",
                ),
            ],
            "preparation": [
                ProcessEvent(kind=ProcessKind.SandBlasting, description="To remove the oxide layer", source="2.1. Alloy Preparation"),
                ProcessEvent(kind=ProcessKind.AquaRegia, source="2.1. Alloy Preparation"),
                ProcessEvent(kind=ProcessKind.ElectricalDischargeMachining, description="The rods were cut to obtain samples for microscopic and mechanical characterization", source="2.1. Alloy Preparation"),
            ],
        },
        output_materials=[
            # They did not make AlCoCrCuFeNi. They just used it as a reference point to make their base alloy:
            # "Much effort was put into optimizing alloys with near equiatomic composition of AlCoCrCuFeNi, investigating changes in composition and finding correct heat treatment parameters [10], resulting in the chemical composition Al10Co25Cr8Fe15Ni36Ti6 (in at.%). This alloy composition is the base alloy for this work,"
            Material(
                # this is not the base sample. this is just stufff they did to analyze the base alloy.
                # this is just data from table 1
                # I'm assuming this is traditionally cast since they don't explicitly mention directional solidification.
                # It also comes before section "3.2. Impact of Bridgman Process on Mechanical Properties." so it should be conventionally cast.
                # Note: This sample is for the base alloy. we know it was homogenized since the text mentions: "The homogenization treatment for the base alloy (1220 °C/20 h) was supposed to work for Al9Co25Cr8Fe15Ni36Ti6Mo1 and the Hf-containing alloy alloy as well"
                process="elements->melt->conventionally_cast->homogenization_base->annealing_900c_50h->preparation",
                measurements=[
                    CompMeasurement("Al10Co25Cr8Fe15Ni36Ti6", method=MeasurementMethod.Balance),
                    Configuration(
                        tags={ConfigTag.Matrix},
                        name="gamma-Matrix",
                        struct=CrysStruct.FCC,
                        measurements=[
                            CompMeasurement({"Al": 6.9, "Co": 29.5, "Cr": 9.3, "Fe": 20.4, "Ni": 30.4, "Ti": 3.5}, method=MeasurementMethod.TEM_EDS),
                        ],
                        source="How we know it's FCC: 3.1 Chemical and Microstructural Analysis of Al10Co25Cr8Fe15Ni36Ti6: 'Subsequent annealing for 50 h at 900 C ... The matrix has a face-centered cubic structure'",
                    ),
                    Configuration(
                        within="gamma-Matrix",
                        name="gamma-prime-particles",
                        struct=CrysStruct.L12,
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            CompMeasurement({"Al": 11.4, "Co": 22.5, "Cr": 3.5, "Fe": 8.8, "Ni": 45.0, "Ti": 8.7}, method=MeasurementMethod.TEM_EDS),
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=200, uncertainty=70, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=38, uncertainty=7, unit=percent, source="Table 3"),
                            Measurement(kind=normalize(val=PhaseMeasurementKind.length, val_in_paper="edge length"), description="edge length of cuboidal gamma prime particles", value="<=400", unit=Nanometer, source="Figure 1b description"),
                            Measurement(
                                kind=PhaseMeasurementKind.grain_size,
                                description="size of secondary gamma prime particles",
                                value="<100",
                                unit=Nanometer,
                                source="Figure 1b description: The authors mention '(some 10 nm)' But since they're using an SEM, it's unlikely that they can see 10 nm particles. What these German authors probably mean is 'tens of nanometers'",
                            ),
                        ],
                        source="Table 1 and This alloy composition is the base alloy for this work, exhibiting L12-ordered, coherently embedded precipitates in a fcc-matrix",
                    ),
                    Configuration(
                        name="Heusler type",
                        struct=CrysStruct.Heusler,
                        description="Needle-shaped",  # Figure 1a) shows the large (several 10 µm), randomly distributed Heusler type phase, with its characteristic needle-like shape
                        measurements=[
                            CompMeasurement({"Al": 24.4, "Co": 21.9, "Cr": 3.6, "Fe": 10.7, "Ni": 33.9, "Ti": 5.6}, method=MeasurementMethod.TEM_EDS),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=3, uncertainty=2, unit=percent, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.length, value="<=50", unit=Micrometer, source="Figure 1a description"),
                        ],
                        source="Table 1",
                    ),
                    # This next data is from table 2
                    # We know the annealing is 900C for 50 Hrs because they said so at the start of "3.2. Impact of Bridgman Process on Mechanical Properties"
                    # "The heat treatment was equal for both conditions (annealing at 900 ◦C for 50 h)."
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=696, unit=MegaPascal, uncertainty=33, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=561, unit=MegaPascal, uncertainty=50, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=560, unit=MegaPascal, uncertainty=27, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=536, unit=MegaPascal, uncertainty=7, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=312, unit=MegaPascal, uncertainty=6, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=520, unit=MegaPascal, uncertainty=19, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=470, unit=MegaPascal, uncertainty=8, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=461, unit=MegaPascal, uncertainty=10, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=445, unit=MegaPascal, uncertainty=2, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=219, unit=MegaPascal, uncertainty=6, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=49, unit=percent, uncertainty=0, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=11, unit=percent, uncertainty=8, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=9, unit=percent, uncertainty=4, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=6, unit=percent, uncertainty=4, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=8, unit=percent, uncertainty=6, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                ],
            ),
            # This next data is also from table 2
            Material(
                process="elements->melt->directional_solidification->homogenization_base->annealing_900c_50h->preparation",
                measurements=[
                    CompMeasurement("Al10Co25Cr8Fe15Ni36Ti6", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=1197, unit=MegaPascal, uncertainty=6, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=1006, unit=MegaPascal, uncertainty=16, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=840, unit=MegaPascal, uncertainty=1, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=575, unit=MegaPascal, uncertainty=7, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=319, unit=MegaPascal, uncertainty=1, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=627, unit=MegaPascal, uncertainty=9, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=594, unit=MegaPascal, uncertainty=3, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=547, unit=MegaPascal, uncertainty=42, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=399, unit=MegaPascal, uncertainty=1, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=243, unit=MegaPascal, uncertainty=2, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=27, unit=percent, uncertainty=1, temperature=Quantity(value="~23", unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=12, unit=percent, uncertainty=2, temperature=Quantity(value=600, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=17, unit=percent, uncertainty=5, temperature=Quantity(value=700, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=20, unit=percent, uncertainty=4, temperature=Quantity(value=800, unit=Celsius), source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value=34, unit=percent, uncertainty=1, temperature=Quantity(value=900, unit=Celsius), source="Table 2"),
                    # Not sure if the "processing techniques" described in the below quote from the paper is talking about directional solidification or conventionally cast:
                    # "The phase-characteristics (content and size) concerning Heusler type phase and γ′-phase were identical for both types of processing techniques"
                ],
            ),
            # This is from Table 3 and Figure 7 (stress-strain curves show this is directionally solidified)
            # This is because the paper says: Directionally solidified samples were produced to neglect the huge factor of grain-structure
            # and grain-size in the mechanical behavior and to investigate the pure microstructure influence independently
            Material(
                process="elements->melt->directional_solidification->homogenization_base->annealing_950c_100h->preparation",
                measurements=[
                    CompMeasurement("Al10Co25Cr8Fe15Ni36Ti6", method=MeasurementMethod.Balance),
                    Configuration(name="gamma-Matrix", tags={ConfigTag.Matrix}),
                    Configuration(
                        name="gamma-prime-particles",
                        within="gamma-Matrix",
                        description="the shape of these particles is cuboidal (round corners)",
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=400, uncertainty=100, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=41, uncertainty=3, unit=percent, source="Table 3"),
                        ],
                    ),
                    Configuration(
                        name="Heusler type phase",
                        description="Needle-shaped",
                        struct=CrysStruct.Heusler,
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=9, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                        source="We know this heusler-type phase is needle-shapped because: 'the needle-shaped Heusler type phase in the case of the base alloy and the Mo-containing alloy is represented in (c) and (i)' and the figure 6 description says: '950◦C/100 h (b,c,e,f,h,i)' so we know it's this sample",
                    ),
                ],
            ),
            # We are now done with analyzing data from the base alloy. Time for the alloys with the additions
            # The conventionally casted and directionally solidified versions of each composition was tested. We know this because Table 2 compares all these alloys.
            Material(
                process="elements->melt->conventionally_cast->homogenization_hf->annealing_900c_50h->preparation",
                measurements=[
                    CompMeasurement("Al9.5Co25Cr8Fe15Ni36Ti6Hf0.5", method=MeasurementMethod.Balance),
                    Configuration(name="gamma-Matrix", tags={ConfigTag.Matrix}),
                    Configuration(
                        name="gamma-prime-particles",
                        within="gamma-Matrix",
                        description="the shape of these particles is cuboidal (sharp corners)",
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=210, uncertainty=70, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=46, uncertainty=2, unit=percent, source="Table 3"),
                        ],
                    ),
                    Configuration(
                        name="Heusler type",
                        struct=CrysStruct.Heusler,
                        description="Spherical",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=6, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                        source="conclusions point 4: An amount of 0.5 at.% hafnium ... lead to a spherical Heusler type phase",
                    ),
                ],
            ),
            Material(
                # Figure 9 shows stress-strain curves for this sample, indicating it is directionally solidified
                # This is because the paper says: Directionally solidified samples were produced to neglect the huge factor of grain-structure
                # and grain-size in the mechanical behavior and to investigate the pure microstructure influence independently
                process="elements->melt->directional_solidification->homogenization_hf->annealing_950c_100h->preparation",
                measurements=[
                    CompMeasurement("Al9.5Co25Cr8Fe15Ni36Ti6Hf0.5", method=MeasurementMethod.Balance),
                    Configuration(name="gamma-Matrix", tags={ConfigTag.Matrix}),
                    Configuration(
                        name="gamma-prime-particles",
                        within="gamma-Matrix",
                        description="the shape of these particles is cuboidal (sharp corners)",
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=420, uncertainty=100, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=38, uncertainty=8, unit=percent, source="Table 3"),
                        ],
                    ),
                    Configuration(
                        name="Heusler type",
                        struct=CrysStruct.Heusler,
                        description="Spherical",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=5, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                        source="conclusions point 4: An amount of 0.5 at.% hafnium ... lead to a spherical Heusler type phase",
                    ),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value="~20", unit=percent, temperature=ROOM_TEMPERATURE, source="3.4: Tests at room temperature reach the highest ultimate tensile strength with a strain to failure of about 20%."),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"), value="~10", unit=percent, temperature=Quantity(value=600, unit=Celsius), source="3.4: Samples deformed at 600°C exhibited only half the strain to failure."),
                ],
            ),
            Material(
                process="elements->melt->conventionally_cast->homogenization_base->annealing_900c_50h->preparation",
                measurements=[
                    CompMeasurement("Al9Co25Cr8Fe15Ni36Ti6Mo1", method=MeasurementMethod.Balance),
                    Configuration(name="gamma-Matrix", tags={ConfigTag.Matrix}),
                    Configuration(
                        name="gamma-prime-particles",
                        within="gamma-Matrix",
                        description="the shape of these particles is round",
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=190, uncertainty=70, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=44, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                    ),
                    Configuration(
                        name="Heusler type",
                        struct=CrysStruct.Heusler,
                        description="Needle-shaped",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=3, uncertainty=3, unit=percent, source="Table 3"),
                        ],
                        source="Conclusion point 3: Addition of 1 at.% molybdenum ... the Heusler type phase remained in its needle-like shape",
                    ),
                ],
            ),
            Material(
                # Figure 8 shows stress-strain curves for this sample, indicating it is directionally solidified
                # This is because the paper says: Directionally solidified samples were produced to neglect the huge factor of grain-structure
                # and grain-size in the mechanical behavior and to investigate the pure microstructure influence independently
                process="elements->melt->directional_solidification->homogenization_base->annealing_950c_100h->preparation",
                measurements=[
                    CompMeasurement("Al9Co25Cr8Fe15Ni36Ti6Mo1", method=MeasurementMethod.Balance),
                    Configuration(name="gamma-Matrix", tags={ConfigTag.Matrix}),
                    Configuration(
                        name="gamma-prime-particles",
                        within="gamma-Matrix",
                        description="the shape of these particles is round",
                        tags={ConfigTag.Precipitate},
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value=360, uncertainty=100, unit=Nanometer, source="Table 3"),
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=37, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                    ),
                    Configuration(
                        name="Heusler type",
                        struct=CrysStruct.Heusler,
                        description="Needle-shaped",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.volume_fraction, value=3, uncertainty=1, unit=percent, source="Table 3"),
                        ],
                        source="Conclusion point 3: Addition of 1 at.% molybdenum ... the Heusler type phase remained in its needle-like shape",
                    ),
                ],
            ),
        ],
    ),
]
