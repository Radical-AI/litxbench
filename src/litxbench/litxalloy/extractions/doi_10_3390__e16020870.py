from pymatgen.core import Lattice

from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
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
)

# be very careful! Table 3 mentions values that are labelled as "fracture strain", but when we look at the image it's actually the part of the strain curve that is under the ultimate compressive strength so it's peak strain/strain.
# but since you need images to understand that it's peak strain (aka plastic strain as this paper calls it), not fracture strain, I'll say this is fracture_strain for now in the eval
# TODO: fix this when we add images. change this part of the eval to be peak strain. Maybe when we change it, we use the normalize function and say that in the paper it's called "fracture_strain" so ppl know it's intentional and not an accident. We also need the above explanation text

experiments: list[Experiment] = [
    Experiment(
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_compression, AlloyMeasurementKind.fracture_strain_compression],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest])],
                desc=f"Their yield strength measurements were under compression because: 'Cylindrical specimens for compressive tests were 3.0 mm in diameter and 6mm in height'. strain rate was 5*10^{-4}*s^{-1}. Note: the caption for table 3 is mislabelled. The caption says 'fracture strain', but we know it's really plastic strain because multiple times elsewhere in the text, we see 'The corresponding yield strength and plastic strain are listed in Table 3'",
            ),
        ],
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="with > 99.5 weight percent (wt.%) purity")},  # I think it's ingots, but I don't think they say. this is safer
        synthesis_groups=[
            ProcessEvent(
                kind=normalize(ProcessKind.ArcMelting, "Vacuum Arc Melting"),
                description="Under an argon atmosphere. In order to decrease the aluminum losses, the other elements, i.e., Nb, Ti, Mo, and V, were re-melted four times first, then Al is added to the pre-melted ingots, and all the constituents were re-melted four times to ensure the chemical homogeneity of the alloys. All the liquid states were held for 5 minutes during each melting event. Used a high-purity molten Ti as a trap for residual oxygen",
                source="Experimental Procedures. The abstract says that it's VacuumArcMelting",
            ),
            ProcessEvent(
                kind=ProcessKind.AsCast,
                source="The microstructures and properties of the alloys were investigated in the as-cast state.",
            ),
            ProcessEvent(
                kind=ProcessKind.Cut,
                description="The prepared alloy buttons with about 11 mm in thickness and 30 mm in diameter were then cut into various shapes to study their microstructures and compressive properties.",
                source="Experimental Procedures",
            ),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("Al0NbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.211)), struct=CrysStruct.BCC, source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1200, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=25.62, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=440.7, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al0.25NbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.206)), struct=CrysStruct.BCC, source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1250, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=12.91, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=460.1, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Configuration(
                        name="DR (Dendrite) - white",
                        tags={ConfigTag.Dendrite},
                        measurements=[
                            CompMeasurement(
                                {"Al": 5.4, "Ti": 22.0, "V": 22.1, "Nb": 25.5, "Mo": 25.0},
                                method=MeasurementMethod.EDS,
                                source="Table 1. We know it's EDS because: The energy dispersive X-ray spectrometry (EDS) phase composition results are given in Table 1.",
                            )
                        ],
                    ),
                    Configuration(name="ID (Interdendrite) - grey", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 6.5, "Ti": 24.6, "V": 24.9, "Nb": 23.6, "Mo": 20.4}, method=MeasurementMethod.EDS, source="Table 1.")]),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al0.5NbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.203)), struct=CrysStruct.BCC, source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1625, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=11.25, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=486.5, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Configuration(name="DR (Dendrite) - white", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Al": 9.8, "Ti": 19.9, "V": 20.4, "Nb": 24.3, "Mo": 25.6}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="ID (Interdendrite) - grey", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 14.6, "Ti": 25.3, "V": 24.1, "Nb": 21.0, "Mo": 15.0}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="ID (Interdendrite) - black", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 10.8, "Ti": 35.7, "V": 20.9, "Nb": 18.9, "Mo": 13.7}, method=MeasurementMethod.EDS, source="Table 1")]),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al0.75NbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.191)), struct=CrysStruct.BCC, source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1260, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=7.5, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=516.6, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Configuration(name="DR (Dendrite) - white", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Al": 14.2, "Ti": 20.7, "V": 20.5, "Nb": 22.5, "Mo": 22.2}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="ID (Interdendrite) - grey", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 15.0, "Ti": 22.3, "V": 21.4, "Nb": 21.6, "Mo": 19.7}, method=MeasurementMethod.EDS, source="Table 1")]),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("AlNbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.201)), struct=CrysStruct.BCC, source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1375, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=2.5, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=536.6, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Configuration(name="DR (Dendrite) - white", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Al": 17.6, "Ti": 16.9, "V": 19.0, "Nb": 21.9, "Mo": 24.6}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="ID (Interdendrite) - grey", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 23.7, "Ti": 21.5, "V": 20.7, "Nb": 20.0, "Mo": 14.1}, method=MeasurementMethod.EDS, source="Table 1")]),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al1.5NbTiMoV", method=MeasurementMethod.Balance),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.186)), struct=CrysStruct.BCC, description="also contains an unknown ordered phase", source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=500, unit=MegaPascal, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value=1.3, unit=percent, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=556.4, unit=HV, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Configuration(name="DR (Dendrite) - white", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Al": 27.7, "Ti": 16.0, "V": 17.8, "Nb": 18.2, "Mo": 20.4}, method=MeasurementMethod.EDS, source="Table 1")]),
                    Configuration(name="ID (Interdendrite) - grey", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Al": 32.8, "Ti": 19.2, "V": 17.0, "Nb": 18.0, "Mo": 13.0}, method=MeasurementMethod.EDS, source="Table 1")]),
                ],
            ),
        ],
    )
]
