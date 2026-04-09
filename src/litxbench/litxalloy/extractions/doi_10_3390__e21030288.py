from pymatgen.core import Composition, Lattice

from litxbench.core.extraction_utils import convert_value_between_units, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    GigaPascal,
    MegaPascal,
    Minute,
    Nanometer,
    percent,
    ureg,
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
    # the hardness and elastic modulus of the diff phases are in figure 8. But they didn't provide exact numbers. just an image. Hardness was described elsewhere though.
    # The hardness and elastic modulus of constituent phases in the as-cast alloys were investigated by the Nano-indenter XP® system (MTS Inc., Eden Prairie, MN, United State) at room temperature with a diamond Berkovich indenter at a peak load of 20 mN and a load rate of 0.1 mN·s−1
    # not sure if I should add the yield strength since they say about, and didn't mention it constantly for each of the compositions.
    Experiment(
        # Note: To prevent the mass loss due to evaporation of Mn, a high purity Fe-68.7at.%Mn intermediate alloy was prepared in advance
        # I didn't say this in the Material step since we don't measure the properties of this intermediate alloy.
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="> 99.95 wt.% purity")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.berkovich_hardness],
                method=MeasurementMethod.NanoindentTest,  # machines=[Machine(methods=[MeasurementMethod.Nanoindenter], model="Nano-indenter XP", company="MTS Inc.", location="Eden Prairie, MN, United State")],
                desc="The hardness and elastic modulus of constituent phases in the as-cast alloys were investigated at room temperature",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_compression, AlloyMeasurementKind.fracture_strain_compression],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest], model="3382", company="Instron")],
                desc="strain rate 1 × 10^{-3} s^{-1}, cuboid specimens 6 mm height × 3 mm × 3 mm (aspect ratio 2), room temperature.",
            ),
        ],
        synthesis_groups=[
            ProcessEvent(
                kind=ProcessKind.ArcMelting,
                description="The ingots were prepared by arc melting under a Ti-gettered, high-purity argon atmosphere. Each ingot was re-melted at least five times in the water-chilled copper crucible, held at a liquid state for at least 5 min and flipped before each melting process. electromagnetic stirring was used during the melting process",
                source="2.1 Material Preparation",
                duration=Quantity(5, Minute),  # I was debating adding the 5 min or not since being held at liquid state for 5 min is not the overal melting process. but we probably don't care that much - especially since this is melting not annealing. I've seen llms extract 5min so might as well keep it here.
            ),
            ProcessEvent(kind=ProcessKind.AsCast, description="The prepared button-shaped ingots were approximately 20 mm in diameter and 10 mm in thickness.", source="2.1 Material Preparation"),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("CoCrFeNiPdMn0", method=MeasurementMethod.Balance),
                    Configuration(
                        struct=CrysStruct.FCC,
                        measurements=[
                            LatticeMeasurement(lattice=Lattice.cubic(3.669)),
                        ],
                        source="The Mn0 HEA was of a single FCC phase with a lattice parameter of a=3.669 Å",
                    ),
                    # I don't think this measurement applies to this since the paper doesn't say anything about the yield strength of the Mn0 HEA. But this can only be known for sure by looking that the chart :( - figure 9 doens't have an Mn0 line.
                    # Measurement(kind=AlloyMeasurementKind.yield_strength, value="~650", unit=MegaPascal, source="one can see that with the increase of Mn addition, the yielding strength held constantly at about 650 MPa"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("CoCrFeNiPdMn0.2", method=MeasurementMethod.Balance),
                    Configuration(
                        struct=CrysStruct.FCC,
                        description="rich in Co, Cr, Fe, Ni and Pd but depleted of Mn",
                        tags={normalize(ConfigTag.Twin, "nanotwins")},  # Abundant nanotwins of about 50 nm could be found in the Mn0.2 EHEA
                        measurements=[
                            CompMeasurement(Composition({"Co": 22.32, "Cr": 21.23, "Fe": 19.30, "Ni": 19.79, "Pd": 13.49, "Mn": 2.09}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 1"),
                            Measurement(kind="nanotwin spacing", value="~50", unit=Nanometer, source="4.2: Abundant nanotwins of about 50 nm could be found in the Mn0.2 EHEA"),
                        ],
                        source="We know it's FCC because of table 1 caption: EPMA results of the FCC phase",
                    ),
                    Configuration(
                        name="MnxPdy phase",
                        description="Mn3Pd5 intermetallic compound",
                        measurements=[
                            CompMeasurement({"Mn": 3, "Pd": 5}),
                            CompMeasurement(Composition({"Co": 3.87, "Cr": 7.48, "Fe": 8.55, "Ni": 5.49, "Pd": 47.32, "Mn": 27.29}), method=MeasurementMethod.EPMA, source="Table 2"),
                            LatticeMeasurement(
                                lattice=Lattice.orthorhombic(
                                    convert_value_between_units(0.2285, Nanometer, ureg.angstrom),
                                    convert_value_between_units(0.1998, Nanometer, ureg.angstrom),
                                    convert_value_between_units(0.2278, Nanometer, ureg.angstrom),
                                ),
                                source="the MnxPdy phase was a Mn3Pd5 intermetallic compound with lattice parameters of a=0.2285 nm, b=0.1998 nm, c=0.2278 nm, being consistent with the XRD results in Figure 1.",
                            ),
                            Measurement(
                                kind=AlloyMeasurementKind.berkovich_hardness,
                                value=4.9,
                                unit=GigaPascal,
                                source="the hardness of the Mn3Pd5 intermetallic compound in the Mn0.2 (4.9 GPa) and Mn0.4 (5.3 GPa) EHEAs was much larger than that of the Mn7Pd9 intermetallic compound in the Mn0.6 (3.1 GPa) and Mn0.8 (3.4 GPa) EHEAs.",
                            ),
                            Measurement(kind="primary_twin_spacing", value=242.10, uncertainty=26.63, unit=Nanometer, source="Table 3"),
                            Measurement(kind="secondary_twin_spacing", value=10.02, uncertainty=1.10, unit=Nanometer, source="Table 3"),
                        ],
                    ),
                    # This measurement is hard! Since the text says "yield strength" but close look at the caption (which is elsewhere in the paper), says that it's "compressive yield strength".
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_compression,
                        value="~650",
                        unit=MegaPascal,
                        source="See Figure 9 One can see that with the increase of Mn addition, the yielding strength held constantly at about 650 MPa. The Figure 9 caption is:  Compressive engineering stress-strain curves of as-cast CoCrFeNiPdMnx (x = 0.2–0.8) HEAs",
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.fracture_strain_compression,
                        value="~50",
                        unit=percent,
                        source="The fracture strain (strength) decreased from about 50% (2.4 GPa) for the Mn0.2 HEA. But the source is talking about figure 9 which is a compressive test (not tensile)",
                    ),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Fracture Strength"),
                        value="~2.4",
                        unit=GigaPascal,
                        source="The fracture strain (strength) decreased from about 50% (2.4 GPa) for the Mn0.2 HEA. But the source is talking about figure 9 which is a compressive test (not tensile)",
                    ),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("CoCrFeNiPdMn0.4", method=MeasurementMethod.Balance),
                    Configuration(
                        struct=CrysStruct.FCC,
                        description="rich in Co, Cr, Fe, Ni and Pd but depleted of Mn",
                        measurements=[
                            CompMeasurement(Composition({"Co": 22.61, "Cr": 21.92, "Fe": 20.41, "Ni": 20.02, "Pd": 11.75, "Mn": 3.56}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 1"),
                        ],
                        source="We know it's FCC because of table 1 caption: EPMA results of the FCC phase",
                    ),
                    Configuration(
                        name="MnxPdy phase",
                        description="Mn3Pd5 intermetallic compound",
                        measurements=[
                            CompMeasurement({"Mn": 3, "Pd": 5}),
                            CompMeasurement(Composition({"Co": 4.49, "Cr": 7.32, "Fe": 8.71, "Ni": 5.53, "Pd": 46.01, "Mn": 29.44}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 2"),
                            LatticeMeasurement(
                                lattice=Lattice.orthorhombic(
                                    convert_value_between_units(0.2285, Nanometer, ureg.angstrom),
                                    convert_value_between_units(0.1998, Nanometer, ureg.angstrom),
                                    convert_value_between_units(0.2278, Nanometer, ureg.angstrom),
                                ),
                                source="For the Mn0.4 EHEA, the same result could be found from the SAED patterns, i.e., the matrix was the FCC phase and the MnxPdy phase was the Mn3Pd5 intermetallic compound.",
                            ),
                            Measurement(
                                kind=AlloyMeasurementKind.berkovich_hardness,
                                value=5.3,
                                unit=GigaPascal,
                                source="the hardness of the Mn3Pd5 intermetallic compound in the Mn0.2 (4.9 GPa) and Mn0.4 (5.3 GPa) EHEAs was much larger than that of the Mn7Pd9 intermetallic compound in the Mn0.6 (3.1 GPa) and Mn0.8 (3.4 GPa) EHEAs.",
                            ),
                            Measurement(kind="primary_twin_spacing", value=180.33, uncertainty=19.84, unit=Nanometer, source="Table 3"),
                            Measurement(kind="secondary_twin_spacing", value=9.99, uncertainty=1.22, unit=Nanometer, source="Table 3"),
                        ],
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_compression,
                        value="~650",
                        unit=MegaPascal,
                        source="See Figure 9 One can see that with the increase of Mn addition, the yielding strength held constantly at about 650 MPa. The Figure 9 caption is:  Compressive engineering stress-strain curves of as-cast CoCrFeNiPdMnx (x = 0.2–0.8) HEAs",
                    ),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("CoCrFeNiPdMn0.6", method=MeasurementMethod.Balance),
                    Configuration(
                        struct=CrysStruct.FCC,
                        description="CoCrFeNi-rich",  # the FCC phases became rich in Co, Cr, Fe and Ni for the Mn0.6 and Mn0.8 EHEAs.
                        source="The Mn0.2, Mn0.4, Mn0.6 and Mn0.8 HEAs had a dual FCC phase and MnxPdy intermetallic compound.",
                        measurements=[
                            CompMeasurement(Composition({"Co": 22.29, "Cr": 22.12, "Fe": 21.32, "Ni": 21.22, "Pd": 8.09, "Mn": 4.22}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 1"),
                        ],
                    ),
                    Configuration(
                        name="MnxPdy phase",
                        description="Mn7Pd9 intermetallic compound",
                        source="The Mn0.2, Mn0.4, Mn0.6 and Mn0.8 HEAs had a dual FCC phase and MnxPdy intermetallic compound.",
                        measurements=[
                            CompMeasurement({"Mn": 7, "Pd": 9}),
                            CompMeasurement(Composition({"Co": 1.60, "Cr": 4.78, "Fe": 4.27, "Ni": 3.39, "Pd": 43.66, "Mn": 42.31}), method=MeasurementMethod.EPMA, source="Table 2"),
                            Measurement(
                                kind=AlloyMeasurementKind.berkovich_hardness,
                                value=3.1,
                                unit=GigaPascal,
                                source="the hardness of the Mn3Pd5 intermetallic compound in the Mn0.2 (4.9 GPa) and Mn0.4 (5.3 GPa) EHEAs was much larger than that of the Mn7Pd9 intermetallic compound in the Mn0.6 (3.1 GPa) and Mn0.8 (3.4 GPa) EHEAs.",
                            ),
                            LatticeMeasurement(
                                lattice=Lattice.tetragonal(
                                    a=convert_value_between_units(0.2267, Nanometer, ureg.angstrom),
                                    c=convert_value_between_units(0.203, Nanometer, ureg.angstrom),
                                ),
                                source="The MnxPdy phase could be the Mn7Pd9 or the Mn11Pd21 intermetallic compound with lattice parameters of a = b = 0.2267 nm, c = 0.203 nm or a = b = 0.2235 nm, c = 0.1816 nm. Because the Mn11Pd21 phase was neither confirmed experimentally nor theoretically [46], the MnxPdy phase in the Mn0.6 and Mn0.8 EHEAs was ultimately determined to be the Mn7Pd9 intermetallic compound.",
                            ),
                            Measurement(kind="primary_twin_spacing", value=14.96, uncertainty=16.46, unit=Nanometer, source="Table 3"),
                            Measurement(kind="secondary_twin_spacing", value=2.22, uncertainty=0.24, unit=Nanometer, source="Table 3"),
                        ],
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_compression,
                        value="~650",
                        unit=MegaPascal,
                        source="See Figure 9 One can see that with the increase of Mn addition, the yielding strength held constantly at about 650 MPa. The Figure 9 caption is:  Compressive engineering stress-strain curves of as-cast CoCrFeNiPdMnx (x = 0.2–0.8) HEAs",
                    ),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("CoCrFeNiPdMn0.8", method=MeasurementMethod.Balance),
                    Configuration(
                        struct=CrysStruct.FCC,
                        description="CoCrFeNi-rich",  # the FCC phases became rich in Co, Cr, Fe and Ni for the Mn0.6 and Mn0.8 EHEAs.
                        source="The Mn0.2, Mn0.4, Mn0.6 and Mn0.8 HEAs had a dual FCC phase and MnxPdy intermetallic compound.",
                        measurements=[
                            CompMeasurement(Composition({"Co": 20.83, "Cr": 21.44, "Fe": 20.84, "Ni": 24.46, "Pd": 6.67, "Mn": 5.12}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 1"),
                        ],
                    ),
                    Configuration(
                        name="MnxPdy phase",
                        description="Mn7Pd9 intermetallic compound",
                        source="The Mn0.2, Mn0.4, Mn0.6 and Mn0.8 HEAs had a dual FCC phase and MnxPdy intermetallic compound.",
                        measurements=[
                            CompMeasurement({"Mn": 7, "Pd": 9}),
                            CompMeasurement(Composition({"Co": 2.56, "Cr": 6.28, "Fe": 4.69, "Ni": 3.81, "Pd": 40.35, "Mn": 41.71}), method=MeasurementMethod.EPMA, validate_composition=False, source="Table 2"),
                            Measurement(
                                kind=AlloyMeasurementKind.berkovich_hardness,
                                value=3.4,
                                unit=GigaPascal,
                                source="the hardness of the Mn3Pd5 intermetallic compound in the Mn0.2 (4.9 GPa) and Mn0.4 (5.3 GPa) EHEAs was much larger than that of the Mn7Pd9 intermetallic compound in the Mn0.6 (3.1 GPa) and Mn0.8 (3.4 GPa) EHEAs.",
                            ),
                            LatticeMeasurement(
                                lattice=Lattice.tetragonal(
                                    a=convert_value_between_units(0.2267, Nanometer, ureg.angstrom),
                                    c=convert_value_between_units(0.203, Nanometer, ureg.angstrom),
                                ),
                                source="The MnxPdy phase could be the Mn7Pd9 or the Mn11Pd21 intermetallic compound with lattice parameters of a = b = 0.2267 nm, c = 0.203 nm or a = b = 0.2235 nm, c = 0.1816 nm. Because the Mn11Pd21 phase was neither confirmed experimentally nor theoretically [46], the MnxPdy phase in the Mn0.6 and Mn0.8 EHEAs was ultimately determined to be the Mn7Pd9 intermetallic compound.",
                            ),
                            Measurement(kind="primary_twin_spacing", value=15.02, uncertainty=1.65, unit=Nanometer, source="Table 3"),
                            Measurement(kind="secondary_twin_spacing", value=1.46, uncertainty=0.16, unit=Nanometer, source="Table 3"),
                        ],
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.fracture_strain_compression,
                        value="~35",
                        unit=percent,
                        source="The fracture strain (strength) decreased from about 50% (2.4 GPa) for the Mn0.2 HEA to about 35% (1.9 GPa) for the Mn0.8 HEA. But the source is talking about figure 9 which is a compressive test (not tensile)",
                    ),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Fracture Strength"),
                        value="~1.9",
                        unit=GigaPascal,
                        source="The fracture strain (strength) decreased from about 50% (2.4 GPa) for the Mn0.2 HEA to about 35% (1.9 GPa) for the Mn0.8 HEA. But the source is talking about figure 9 which is a compressive test (not tensile)",
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.yield_strength_compression,
                        value="~650",
                        unit=MegaPascal,
                        source="See Figure 9 One can see that with the increase of Mn addition, the yielding strength held constantly at about 650 MPa. The Figure 9 caption is:  Compressive engineering stress-strain curves of as-cast CoCrFeNiPdMnx (x = 0.2–0.8) HEAs",
                    ),
                ],
            ),
        ],
    )
]
