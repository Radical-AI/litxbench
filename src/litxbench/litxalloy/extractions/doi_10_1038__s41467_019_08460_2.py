from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CoreMeasurementValue, CrysStruct, MeasurementStatistic, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    GigaPascal,
    Hour,
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

# there are a lot of strength values we should extract from the plots
# synthesis process was multi-pass cold-rolling followed by annealing at diff temps
#  In the present work, the yield strength on the order of 1.5 GPa along with ~16% elongation have rarely been achieved in existing HEAs
experiments: list[Experiment] = [
    # Not sure where to put this: Different lamella domains exhibited varied interlamella spacings (1.5–5 μm)
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Ingot, description="Al,Co,Cr,Fe,Ni elements with purity better than 99.9 wt%")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_tension, AlloyMeasurementKind.fracture_strain_tension],
                method=MeasurementMethod.TensileTest,
                # machines=[Machine(methods=[MeasurementMethod.TensileTest], model="Criterion Model 44", company="MTS")],
                desc="with an initial strain rate of 2.5*10^{-4}s^{-1}. Also: 'Tensile tests were carried out at room temperature'. dimensions of tensile spe-cimens are 15 mm in gage length, 3.2 mm in width, and 600 μm in thickness, which are typically consistent with the frequently reported dimensions in the literature16,18. All tensile tests were conducted, using a 12-mm extensometer to monitor the strain",
            ),
            # AlloyDescriptionGroup(
            #     measurement_kinds=[MeasurementMethod.SEM, MeasurementMethod.EBSD],
            #     # machines=[Machine(methods=[MeasurementMethod.SEM, MeasurementMethod.EBSD], model="Apollo 300", company="CamScan")],
            #     desc="equipped with a HKL-Technology EBSD system.",
            #     source="The EBSD and SEM observations were conducted by the CamScan Apollo 300 SEM equipped with a HKL–Technology EBSD system.",
            # ),
            AlloyDescriptionGroup(
                method=MeasurementMethod.TEM,
                # machines=[Machine(methods=[MeasurementMethod.TEM, MeasurementMethod.STEM], model="JEM-2100F", company="JEOL")],
                desc="operated at 200 kV",
            ),
        ],
        synthesis_groups={
            "creation": [
                ProcessEvent(kind=ProcessKind.ArcMelting, description="Arc melted under a Ti-gettered high-purity argon atmosphere. The melting was repeated at least five times to achieve a good chemical homogeneity of the alloy.", source="Methods"),
                ProcessEvent(kind=ProcessKind.SuctionCasting, description="The molten alloy was suction-cast into a 30 mm (width) x 100 mm (length) × 6 mm (thickness) copper mold.", source="Methods."),
            ],
            "cold_rolling": [
                ProcessEvent(kind=ProcessKind.ColdRolling, description="multi-pass cold-rolling to 84-86% reduction in thickness (the final thickness of ~600 μm) using a laboratory-scale two-high rolling machine.", source="Methods."),
            ],
            "annealing[Temp]": [
                ProcessEvent(kind=ProcessKind.NonIsothermalAnnealing, description="heating_rate is 10 C/min", temperature=Quantity(value="[Temp]", unit=Celsius), source="Methods | Sample Preparation"),
                ProcessEvent(kind=ProcessKind.IsothermalHolding, temperature=Quantity(value="[Temp]", unit=Celsius), duration=Quantity(value=1, unit=Hour), source="Methods | Sample Preparation"),
            ],
            "quenching": [
                ProcessEvent(kind=ProcessKind.WaterQuenching, source="Methods | Sample Preparation"),
            ],
        },
        output_materials=[
            Material(
                process="elements->creation",
                name="as-cast_EHEA",
                measurements=[
                    CompMeasurement("AlCoCrFeNi2.1", method=MeasurementMethod.Balance),
                    Configuration(name="soft FCC lamellae", struct=CrysStruct.FCC, tags={ConfigTag.Lamellar}, source="Similar to the as-cast EHEA (Fig. 1a), the tailored DPHL HEA showed a typical lamella morphology"),
                    Configuration(name="hard B2 lamellae", struct=CrysStruct.B2, tags={ConfigTag.Lamellar}, source="Similar to the as-cast EHEA (Fig. 1a), the tailored DPHL HEA showed a typical lamella morphology"),
                    Configuration(within="hard B2 lamellae", description="rich in Cr", tags={ConfigTag.Precipitate}, source="in the as-cast EHEA, the Cr-rich precipitates are densely dispersed inside the B2 lamellae"),
                ],
            ),
            # More specifically, four samples were, respectively, annealed from room temperature at 660, 700, 740, and 900 °C with the constant heating rate of 10 °C min−1, held at these four temperatures for 1 h and then water quenched immediately
            Material(
                process="as-cast_EHEA->cold_rolling->annealing[Temp=660]->quenching",
                name="DPHL660",
                measurements=[
                    CompMeasurement("AlCoCrFeNi2.1"),
                    Configuration(name="soft FCC lamellae", struct=CrysStruct.FCC, tags={ConfigTag.Lamellar}, source="When talking about DPHL700's structure: This had similar grain structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1)."),
                    Configuration(name="hard B2 lamellae", struct=CrysStruct.B2, tags={ConfigTag.Lamellar}, source="When talking about DPHL700's structure: This had similar grain structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1)."),
                    Configuration(
                        struct=CrysStruct.B2,
                        name="intragranular B2 grains",
                        tags={ConfigTag.Intragranular, ConfigTag.Precipitate},
                        description="NiAl-rich precipitates",
                        # the main materials are the 660, 700, and 740 samples because of this sentence: (so we know when they say other two, they do NOT mean the 900 sample)
                        # In this study, we prepared three EHEAs with the DPHL structure, and denoted them as DPHL660, DPHL700, and DPHL740 as per their different annealing temperatures, to study their mechanical behavior and deformation mechanisms.
                        source="When talking about DPHL700's structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1).",
                        within="soft FCC lamellae",
                    ),
                    Configuration(
                        struct=CrysStruct.B2,
                        name="intergranular B2 grains",
                        description="NiAl-rich precipitates",
                        tags={ConfigTag.Intergranular, ConfigTag.Precipitate},
                        source="When talking about DPHL700's structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1).",
                        within="soft FCC lamellae",
                    ),
                    # NOTE: once we process images from this paper, we can get much more accurate measurements. (since there is the graph we can pull the data from)
                    # I decided to NOT copy over the measurements from the other EHEA paper. Even though our paper says that it's similar,
                    # the paper casts doubt on the accuracy of the other paper's measurements:
                    # "However, it is noted that the tensile data in ref. 23 is not consistent with its stress–strain curve, and the real data ought to be yield strength of ~1.15 GPa and ductility of ~14% from the curve."
                    # this doubt makes me not believe these measurements. so we'll need to wait until we can process images from this paper.
                    # Measurement(
                    #     kind=AlloyMeasurementKind.yield_strength_tension,
                    #     value="~1.437",  # This is from an EHEA from a diff paper. But the paper said that the DPHL660 sample has similar properties
                    #     unit=GigaPascal,
                    #     source="Recently, Bhattacharjee et al. processed a complex and hierarchical microstructure in the same AlCoCrFeNi2.1 EHEAs by heavy cryo-rolling and annealing23, which shows a better strength–ductility balance (yield strength of  ~1.437 GPa and ductility of ~14%) than the ultrafine-grained EHEA7 and a comparable property combination to that of our DPHL660 (Fig. 2a).",
                    # ),
                    # Measurement(
                    #     kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="ductility"),
                    #     value="~14",  # This is from an EHEA from a diff paper. But the paper said that the DPHL660 sample has similar properties
                    #     unit=percent,
                    #     source="Tensile-properties section: 'Recently, Bhattacharjee et al. processed a complex and hierarchical microstructure in the same AlCoCrFeNi2.1 EHEAs by heavy cryo-rolling and annealing23, which shows a better strength–ductility balance (yield strength of  ~1.437 GPa and ductility of ~14%) than the ultrafine-grained EHEA7 and a comparable property combination to that of our DPHL660 (Fig. 2a).'",
                    # ),
                ],
            ),
            Material(
                process="as-cast_EHEA->cold_rolling->annealing[Temp=700]->quenching",
                name="DPHL700",
                measurements=[
                    CompMeasurement("AlCoCrFeNi2.1"),
                    # we infer that this yeild strength and fracture strain is in reference to the 700 and 740 samples since the 900 sample sucks and we have an indication of the yileld strength and ductility for the 600 sample.
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value="~1.5", unit=GigaPascal, temperature=ROOM_TEMPERATURE, source="In the present work, the yield strength on the order of 1.5 GPa along with ~16% elongation have rarely been achieved in existing HEAs"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="elongation"), value="~16", unit=percent, temperature=ROOM_TEMPERATURE),
                    # We know that this structural information is for the 700 sample, because the Results->Microstructure characterization section keeps referencing subfigures from Figure 1.
                    # And the caption of Figure 1 says: "Fig. 1 Microstructures of the as-cast EHEA and the hierarchical DPHL700."
                    # But Note! only subfigure a is for the base as-cast EHEA. All the other subfigures are for the DPHL700 sample. which we know (because of the start of the figure caption says it's for the 700 sample).
                    # annealing twins were occasionally seen in FCC grains (Fig. 1d, g)
                    Configuration(
                        name="soft FCC lamellae",
                        struct=CrysStruct.FCC,
                        tags={ConfigTag.Lamellar, normalize(val=ConfigTag.Twin, val_in_paper="annealing twins")},
                        description="rich in Fe and Cr",
                        source="the enriched Fe and Cr lamellae corresponded to FCC grains",
                        measurements=[Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.71", unit=Micrometer)],
                    ),
                    Configuration(
                        struct=CrysStruct.B2,  # f also exhibited many BCC-phase precipitates in FCC lamellae.
                        name="intragranular B2 grains",
                        tags={ConfigTag.Intragranular, ConfigTag.Precipitate},
                        description="NiAl-rich precipitates",
                        source="They presented two types of NiAl-rich precipitates: the small and scarce P1 (intragranular B2 grains) of size 50–180 nm, and the large and primary P2 (intergranular B2 grains) with an average size of ~350 nm (Fig. 1f).",
                        within="soft FCC lamellae",
                        measurements=[
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.grain_size,
                                unit=Nanometer,
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=50),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=180),
                                ],
                            ),
                        ],
                    ),
                    Configuration(
                        struct=CrysStruct.B2,  # f also exhibited many BCC-phase precipitates in FCC lamellae.
                        name="intergranular B2 grains",
                        description="NiAl-rich precipitates",
                        tags={ConfigTag.Intergranular, ConfigTag.Precipitate},
                        source="They presented two types of NiAl-rich precipitates: the small and scarce P1 (intragranular B2 grains) of size 50–180 nm, and the large and primary P2 (intergranular B2 grains) with an average size of ~350 nm (Fig. 1f).",
                        within="soft FCC lamellae",
                        measurements=[Measurement(kind=PhaseMeasurementKind.grain_size, value="~350", unit=Nanometer, measurement_statistic=MeasurementStatistic.mean)],
                    ),
                    Configuration(
                        name="hard B2 lamellae",
                        struct=CrysStruct.B2,
                        description="rich in Ni and Al.",
                        tags={ConfigTag.Lamellar},
                        source="the NiAl-rich lamellae (thickness of ~1 μm) were B2 grains",
                        measurements=[
                            Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.71", unit=Micrometer),
                            Measurement(kind=PhaseMeasurementKind.length, value="~1", unit=Micrometer, description="thickness of ~1 μm", source="diffraction patterns (SADPs) suggested that the NiAl-rich lamellae (thickness of ~1 μm)"),
                        ],
                    ),
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.volume_fraction,
                        unit=percent,
                        description="directionally aligned along the rolling direction",
                        source="the resultant samples possess massive special lamellae (~82–87 vol.%) with a directionally aligned arrangement along the rolling direction",
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.lower, value="~82"),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value="~87"),
                        ],
                    ),
                    # we know this measurement is for this sample because this sample has the laellae and primary P2 (which the second half of the source text mentions)
                    Measurement(
                        kind=AlloyMeasurementKind.fracture_strain_tension, value=21, unit=percent, source="Fig. 3 caption: b,c STEM images of the microstructure stretched to fracture (ɛ = 21%). The dual-phase lamellae and P2 (indicated by yellow dashed lines and red arrows, respectively) show apparent dislocations."
                    ),
                ],
            ),
            Material(
                process="as-cast_EHEA->cold_rolling->annealing[Temp=740]->quenching",
                name="DPHL740",
                measurements=[
                    CompMeasurement("AlCoCrFeNi2.1"),
                    Configuration(name="soft FCC lamellae", struct=CrysStruct.FCC, tags={ConfigTag.Lamellar}, source="When talking about DPHL740's structure: This had similar grain structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1)."),
                    Configuration(name="hard B2 lamellae", struct=CrysStruct.B2, tags={ConfigTag.Lamellar}, source="When talking about DPHL740's structure: This had similar grain structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1)."),
                    Configuration(
                        struct=CrysStruct.B2,
                        name="intragranular B2 grains",
                        tags={ConfigTag.Intragranular, ConfigTag.Precipitate},
                        description="NiAl-rich precipitates",
                        # the main materials are the 660, 700, and 740 samples because of this sentence: (so we know when they say other two, they do NOT mean the 900 sample)
                        # In this study, we prepared three EHEAs with the DPHL structure, and denoted them as DPHL660, DPHL700, and DPHL740 as per their different annealing temperatures, to study their mechanical behavior and deformation mechanisms.
                        source="When talking about DPHL700's structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1).",
                        within="soft FCC lamellae",
                    ),
                    Configuration(
                        struct=CrysStruct.B2,
                        name="intergranular B2 grains",
                        description="NiAl-rich precipitates",
                        tags={ConfigTag.Intergranular, ConfigTag.Precipitate},
                        source="When talking about DPHL700's structure: Such structural characteristics were also seen in the other two DPHL HEAs (Supplementary Fig. 1).",
                        within="soft FCC lamellae",
                    ),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value="~1.5", unit=GigaPascal, temperature=ROOM_TEMPERATURE, source=" In the present work, the yield strength on the order of 1.5 GPa along with ~16% elongation have rarely been achieved in existing HEAs"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="elongation"), value="~16", unit=percent, temperature=ROOM_TEMPERATURE),
                ],
            ),
            Material(process="as-cast_EHEA->cold_rolling->annealing[Temp=900]->quenching", name="DPHL900", measurements=[CompMeasurement("AlCoCrFeNi2.1")]),  # The paper said that this sample's results were inferior
        ],
    )
]
