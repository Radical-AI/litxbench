from pymatgen.core import Lattice

from litxbench.core.models import CompMeasurement, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    Celsius,
    Hour,
    MegaPascal,
    Minute,
    Nanometer,
    gram_per_cm3,
    percent,
)
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMaterial as Material,
    AlloyMeasurementKind,
    AlloyMeasurementMethod as MeasurementMethod,
    Measurement,
    ProcessEvent,
    ProcessKind,
    Quantity,
)

experiments: list[Experiment] = [
    # Densities were measured by archimedes principle??? Did they specify a machine?
    # - Do we put "lattice strain" measured? it's a bit weird since they mention lattice strain during only the synthesis. Did they run the mill for x hours, then take it out and characterize them?
    # - The BC lattice param they mention is after milling. but what about after sintering?
    #  - The only specific lattice parameter provided in the document is $2.8831\text{ \AA}$, which refers to the BCC solid solution formed after milling but before the completion of the sintering process.
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Powder, description="Co, Cr, Ni, Cu, and Zn with a purity of more than 99.5 wt.% and a particle size of ~45 µm")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.vickers_hardness],
                method=MeasurementMethod.VickersHardnessTest,  # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester], model="430SV", company="Wolpert", location="Aachen, Germany")],
                desc="The hardness of sectioned and polished specimens was determined by vickers hardness tester.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.ultimate_compressive_strength],
                method=MeasurementMethod.CompressionTest,  # machines=[Machine(methods=[MeasurementMethod.CompressionTest], model="810", company="MTS Systems Corporation", location="Eden Prairie, MN, USA")],
                desc="The compressive properties at room temperature were determined with a loading rate of 1 mm/min.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.density],
                method=MeasurementMethod.ArchimedesMethod,  # machines=[Machine(methods=[MeasurementMethod.ArchimedesMethod])],
                desc="measured by archimedes principle. No machine was specified.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.solidus],
                method=MeasurementMethod.DSC,
                # machines=[Machine(methods=[MeasurementMethod.DSC], model="449C", company="Netzsch", location="Selb, Germany")],
                desc="The thermal analysis of as-milled powder was conducted by a differential scanning calorimeter (DSC) heating the alloy to 1500 °C (5 °C/min) in flowing argon atmosphere.",
            ),
        ],
        synthesis_groups={
            "Milling[Duration]": [
                ProcessEvent(
                    kind=ProcessKind.MechanicalAlloying,
                    duration=Quantity(value="[Duration]", unit=Hour),
                    description="Milled in a planetary ball miller (QM-BP, Nanjing Nanda Instrument Plant, Nanjing, China) (300 rpm, argon atmosphere) with stainless steel vials and balls as milling media (a ball-to-powder mass ratio of 20:1). N-heptane was used as the processing controlling agent (PCA) to avoid cold welding and oxidation.",
                    source="2. Experimental",
                )
            ],
            "SPS[Temp]": [
                ProcessEvent(
                    kind=ProcessKind.SparkPlasmaSintering,
                    temperature=Quantity(value="[Temp]", unit=Celsius),
                    duration=Quantity(value=10, unit=Minute),
                    description="Consolidated by SPS (Dr. Sinter-3.20 MKII, Sumitomo, Osaka, Japan). The pressure was 30 MPa uniaxial during sintering. The dwell time at temperature was 10 min. The atmosphere was argon.",
                    source="2. Experimental",
                )
            ],
        },
        output_materials=[
            Material(
                process="elements->Milling[Duration=6]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.crystallite_size, value=22, unit=Nanometer, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.lattice_strain, value=0.64, unit=percent, source="Table 1"),
                ],
            ),
            Material(
                process="elements->Milling[Duration=18]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.crystallite_size, value=19, unit=Nanometer, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.lattice_strain, value=0.65, unit=percent, source="Table 1"),
                ],
            ),
            Material(
                process="elements->Milling[Duration=30]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        struct=CrysStruct.BCC,
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(2.8831)),
                        description="BCC with (1 1 0), (2 0 0), (2 1 1) peaks",
                        source="After 30-h milling, only 3 peaks of a BCC structure ((1 1 0), (2 0 0), (2 1 1)) could be identified, indicating the formation of a simple solid solution",
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.crystallite_size,
                        value=13,
                        unit=Nanometer,
                        description="calculated by Scherrer's formula from XRD",
                        source="Table 1. also: The crystallite size (CS) and lattice strain (LS) of CoCrNiCuZn HEA obtained after milling for different time were calculated by Scherrer’s formula after eliminating the interferences of instruments and strain [16,17]",
                    ),
                    Measurement(kind=AlloyMeasurementKind.lattice_strain, value=0.67, unit=percent, source="Table 1"),
                    # This below measurement is actually most likely incorrect. This is because the 10 Nm grain size is explicitly mentioned to be measured by brightfield TEM on the 60h sample.
                    # It wasn't mentioned to be measured on the 30h sample. This is probably a typo since it's only mentioned in the conclusion and they mentioned the 10nm crystalline size twice: in the abstract and in this sentence
                    # Measurement(kind=AlloyMeasurementKind.crystallite_size, value=10, unit=Nanometer, source="Conclusion: After 30-h ball milling, a BCC phase structure with a grain size of 10 nm was formed."),
                ],
            ),
            Material(
                process="elements->Milling[Duration=60]",
                name="base",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=100, unit=percent),  # not sure if I should put 100. but they did say that only a sinlge phase was detected.
                        source="The rings in the SAED pattern (Figure 3) indicated that the nanocrystalline HEA powder after 60 h milling only consisted of a BCC phase.",
                    ),
                    Measurement(kind=AlloyMeasurementKind.lattice_strain, value=0.70, unit=percent, source="Table 1"),
                    Measurement(
                        kind=AlloyMeasurementKind.crystallite_size,
                        value=13,
                        unit=Nanometer,
                        description="calculated by Scherrer's formula from XRD",
                        source="Table 1. also: The crystallite size (CS) and lattice strain (LS) of CoCrNiCuZn HEA obtained after milling for different time were calculated by Scherrer’s formula after eliminating the interferences of instruments and strain [16,17]",
                    ),
                    Measurement(kind=AlloyMeasurementKind.crystallite_size, value="~10", unit=Nanometer, description="measured from bright field TEM image", source="The crystal size measured from bright field TEM image was approximately 10 nm"),
                    # note: The DSC peaks are very flat (yes I cheated by looking at figures). But we can guess it's 2 phases because of the composition (and because they said it was 2 phases)
                    Configuration(
                        name="Phase 1",
                        measurements=[
                            Measurement(
                                kind=AlloyMeasurementKind.solidus,
                                value=1244.8,
                                unit=Celsius,
                                source="Two endothermic peaks at 1244.8 ◦C and 1321.8 ◦C were considered as the melting points of different phases. We know it's solidus because they say endothermic.",
                            ),
                        ],
                    ),
                    Configuration(
                        name="Phase 2",
                        measurements=[
                            Measurement(
                                kind=AlloyMeasurementKind.solidus,
                                value=1321.8,
                                unit=Celsius,
                                source="Two endothermic peaks at 1244.8 ◦C and 1321.8 ◦C were considered as the melting points of different phases. We know it's solidus because they say endothermic.",
                            ),
                        ],
                    ),
                ],
            ),
            Material(
                process="base->SPS[Temp=600]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.density, value=5.26, unit=gram_per_cm3, source="3.2.2. Microstructure"),
                ],
            ),
            Material(
                process="base->SPS[Temp=700]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.density, value=6.26, unit=gram_per_cm3, source="3.2.2. Microstructure"),
                ],
            ),
            Material(
                process="base->SPS[Temp=800]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.density, value=7.84, unit=gram_per_cm3, source="3.2.2. Microstructure"),
                ],
            ),
            Material(
                process="base->SPS[Temp=900]",
                measurements=[
                    CompMeasurement("CoCrNiCuZn", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.density, value=7.89, unit=gram_per_cm3, source="3.2.2. Microstructure"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=2121, unit=MegaPascal, source="3.2.3. Mechanical Properties"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=615, unit=HV, source="3.2.3. Mechanical Properties"),
                    # When we include figure analysis in this dataset, we should add the peak information for these FCC phases
                    GlobalLatticeParam(struct=CrysStruct.FCC, name="FCC1", source="Two FCC phases were formed at 900C and respectively recorded as FCC1 and FCC2"),
                    GlobalLatticeParam(struct=CrysStruct.FCC, name="FCC2", source="Two FCC phases were formed at 900C and respectively recorded as FCC1 and FCC2"),
                ],
            ),
        ],
    ),
]
