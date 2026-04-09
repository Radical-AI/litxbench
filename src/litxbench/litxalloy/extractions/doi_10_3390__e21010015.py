from pymatgen.core import Lattice

from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    MegaPascal,
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
    # Note: table 7 results are calculated - not experimental
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="Raw elements: Hf, Mo, Nb, Ta, and Zr was 99.9 wt.% purity. Ti was 99.99 wt.% purity.")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_compression, AlloyMeasurementKind.fracture_strain_compression, AlloyMeasurementKind.ultimate_compressive_strength],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest], model="4468", company="Instron", location="Norwood, MA, USA"), Machine(methods=[MeasurementMethod.CompressionTest], model="Gleeble-3500", company="Dynamic Systems Inc", location="Poestenkill, NY, USA")],
                desc="Cylindrical samples 3.6 mm diameter × 6 mm height, crosshead speed 0.36 mm/min (strain rate 10^{-3} s^{-1}).",
            ),
            AlloyDescriptionGroup(
                kinds=[GlobalLatticeParam],
                method=MeasurementMethod.XRD,
                # machines=[Machine(methods=[MeasurementMethod.XRD], model="XRD-6000", company="Shimadzu", location="Kyoto, Japan")],
                desc="Crystal structure examined, operated at 30 kV and 20 mA with a scanning rate of 4°/min from 20° to 100°.",
            ),
            AlloyDescriptionGroup(
                kinds=[MeasurementMethod.EDS],
                method=MeasurementMethod.EDS,
                # machines=[Machine(methods=[MeasurementMethod.SEM], model="JSM-5410", company="JEOL Ltd.", location="Tokyo, Japan"), Machine(methods=[MeasurementMethod.EPMA], model="JXA-8500F", company="JEOL")],
                desc="Chemical compositions confirmed by energy dispersive spectrometry (EDS) in backscattering electron (BSE) mode.",
            ),
        ],
        synthesis_groups=[
            ProcessEvent(
                kind=normalize(ProcessKind.ArcMelting, "Vacuum Arc Melting"),
                description="These pure metals were stacked together in the sequence of low melting point to high melting point from bottom to top. The ingot of each alloy was flipped and re-melted, at least, four times to improve the chemical homogeneity.",
                source="2. Materials and Methods",
            ),
            ProcessEvent(kind=ProcessKind.AsCast, source="2. Materials and Methods: The stacked metals were melted together in a water-cool copper mold and solidified therein."),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("HfMoNbTaTiZr", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(Lattice.cubic(3.345)),
                        struct=CrysStruct.BCC,
                        source='Table 2. It is BCC because of "The main phase of the Hf-Mo-Nb-Ta-Ti-Zr alloy series is a BCC disordered solid solution.',
                    ),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="ultimate strength"), value=1828, unit=MegaPascal, description="at 11% strain", temperature=ROOM_TEMPERATURE),
                    Configuration(name="dendrite (DR)", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Hf": 14.3, "Mo": 18.4, "Nb": 19.5, "Ta": 24.4, "Ti": 12.4, "Zr": 10.8}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="interdendritic (ID)", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Hf": 21.1, "Mo": 13.6, "Nb": 12.3, "Ta": 9.9, "Ti": 18.3, "Zr": 24.7}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1512, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=12, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1489, unit=MegaPascal, temperature=Quantity(800, Celsius), description="at 19% strain"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1007, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=814, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=556, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                ],
                # The compression tests for HfMoNbTaTiZr alloy were also
                # conducted at 800 °C, 1000 °C, and 1200 °C, respectively. At 800 °C, the yield strength of
                # HfMoNbTaTiZr alloy was 1007 MPa and ultimate strength was 1489 MPa when the strain was 19%,
                # which shows obvious work hardening. At 1000 °C and 1200 °C, the results of yield strength were 814
                # obvious work hardening. At 1000 °C and 1200 °C, the results of yield strength were 814 MPa and
                # 556 MPa, respectively, but the strength kept decreasing from the yield point to the end of the test,
                # showing the work softening behavior. No crack was observed at 1000 °C and 1200 °C.
            ),
            Material(
                measurements=[
                    CompMeasurement("HfNbTaTiZr", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.400)), struct=CrysStruct.BCC, source='Table 2. It is BCC because of "The main phase of the Hf-Mo-Nb-Ta-Ti-Zr alloy series is a BCC disordered solid solution.'),
                    Configuration(name="dendrite (DR)", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Hf": 18.5, "Nb": 22.4, "Ta": 27.4, "Ti": 18.2, "Zr": 13.5}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="interdendritic (ID)", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Hf": 22.6, "Nb": 17.5, "Ta": 12.8, "Ti": 20.2, "Zr": 26.9}, method=MeasurementMethod.EDS, source="Table 1")]),
                    # these measurements are from citation [25](the authors didn't make it)
                    # Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=929, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    # Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=">50", unit=percent, source="Table 3"),
                    # Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=535, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    # Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=295, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    # Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=92, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("HfMoTaTiZr", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.364)), struct=CrysStruct.BCC, source="Lattice parameter is from Table 2"),
                    Configuration(name="dendrite (DR)", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Hf": 20.6, "Mo": 21.4, "Ta": 23.9, "Ti": 18.3, "Zr": 15.7}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="interdendritic (ID)", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Hf": 24.4, "Mo": 16.2, "Ta": 11.0, "Ti": 21.2, "Zr": 27.1}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1600, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1743, unit=MegaPascal, description="at 3% strain", temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1446, unit=MegaPascal, description="at 23% strain", temperature=Quantity(800, Celsius)),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=4, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1045, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=855, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=404, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("HfMoNbTiZr", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.369)),
                        struct=CrysStruct.BCC,
                        source='Table 2. It is BCC because of "The main phase of the Hf-Mo-Nb-Ta-Ti-Zr alloy series is a BCC disordered solid solution.',
                    ),
                    Configuration(name="Overall", measurements=[CompMeasurement({"Hf": 20.8, "Mo": 20.6, "Nb": 19.7, "Ti": 19.2, "Zr": 19.7}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1351, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=20, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1698, unit=MegaPascal, description="at 17% strain", temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1244, unit=MegaPascal, description="at 18% strain", temperature=Quantity(800, Celsius)),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=829, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=721, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=301, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("HfMoNbTaZr", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.347)),
                        struct=CrysStruct.BCC,
                        source='Table 2. It is BCC because of "The main phase of the Hf-Mo-Nb-Ta-Ti-Zr alloy series is a BCC disordered solid solution.',
                    ),
                    Configuration(name="dendrite (DR)", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Hf": 18.5, "Mo": 20.8, "Nb": 21.7, "Ta": 24.5, "Zr": 14.5}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="interdendritic (ID)", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Hf": 27.0, "Mo": 15.6, "Nb": 13.5, "Ta": 9.9, "Zr": 34.0}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1524, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=16, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1963, unit=MegaPascal, description="at 13.5% strain", temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1991, unit=MegaPascal, description="at 24% strain", temperature=Quantity(800, Celsius)),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1336, unit=MegaPascal, description="at 11% strain", temperature=Quantity(1000, Celsius)),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1005, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=927, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=694, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=278, unit=MegaPascal, temperature=Quantity(1400, Celsius), source="Table 4"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("HfMoNbTaTi", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.305)),
                        struct=CrysStruct.BCC,
                        source='Table 2. It is BCC because of "The main phase of the Hf-Mo-Nb-Ta-Ti-Zr alloy series is a BCC disordered solid solution.',
                    ),
                    Configuration(name="dendrite (DR)", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Hf": 15.5, "Mo": 22.7, "Nb": 19.5, "Ta": 25.7, "Ti": 16.6}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="interdendritic (ID)", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Hf": 30.7, "Mo": 16.9, "Nb": 17.6, "Ta": 10.7, "Ti": 24.1}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1369, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=27, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=2094, unit=MegaPascal, description="at 25% strain", temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1998, unit=MegaPascal, description="at 29% strain", temperature=Quantity(800, Celsius)),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="Ultimate Strength"), value=1454, unit=MegaPascal, description="at 27.5% strain", temperature=Quantity(1000, Celsius)),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=822, unit=MegaPascal, temperature=Quantity(800, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=778, unit=MegaPascal, temperature=Quantity(1000, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=699, unit=MegaPascal, temperature=Quantity(1200, Celsius), source="Table 4"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=367, unit=MegaPascal, temperature=Quantity(1400, Celsius), source="Table 4"),
                ],
            ),
        ],
    )
]
