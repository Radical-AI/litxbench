from pymatgen.core.lattice import Lattice

from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    GigaPascal,
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
    # They made MoNbTaV and compared it to the alredy known alloy MoNbTaW
    # This paper is tricky. they mention lots of values in the abstract (like hardness and yield strength), but the more precise values are in table 1.
    # This paper mentions room temperature a lot. We assume that all of the room temperature values are 23 C since they mentioned it once:
    # "Figure 7a shows the engineering stress-strain curves (RT, 23˝C) for MoNbTaV alloy"
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="with >99.9 wt.% purity")},
        descriptions=[
            AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.yield_strength_compression], method=MeasurementMethod.CompressionTest, desc=f"3 mm diameter × 6 mm height (aspect ratio 1:2). strain rate of 5*10^{-4}*s^{-1}"),
            # machines=[Machine(methods=[MeasurementMethod.CompressionTest])],
            AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], method=MeasurementMethod.VickersHardnessTest, desc="1 kg load, 20 s dwell time, 8 random points averaged"),
            # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester])],
            AlloyDescriptionGroup(kinds=[GlobalLatticeParam], method=MeasurementMethod.XRD, desc="The scanning range was from 20 degrees to 80 degrees in 2θ at a scanning rate of 3˝/min."),
            # machines=[Machine(methods=[MeasurementMethod.XRD], model="DX-2700", company="Haoyuan Instrument Co., Ltd.", location="Dandong, China")],
            AlloyDescriptionGroup(kinds=[MeasurementMethod.EDS], method=MeasurementMethod.EDS, desc="The average bulk composition of the alloys (Caver) was estimated using energy-dispersive X-ray spectroscopy (EDX) on large areas"),
            # machines=[Machine(methods=[MeasurementMethod.SEM], model="MIRA3 LMH", company="Tescan"), Machine(methods=[MeasurementMethod.EDS], model="X-Max^N", company="Oxford Instruments")],
        ],
        synthesis_groups=[
            ProcessEvent(
                kind=normalize(ProcessKind.ArcMelting, "Vacuum Arc Melting"),
                description="Vacuum arc melting on a water-cooled copper hearth in a Ti-gettered, high-purity argon atmosphere. To achieve a homogeneous distribution of elements, the ingot was remelted at least seven times. Between melts, the ingot was flipped in an attempt to better mix the constituent elements. The ingot was about 35 mm in diameter and 15 mm in height.",
                source="Computational Methodologies and Experimental Procedures",
            ),
            ProcessEvent(kind=ProcessKind.AsCast, description="Final as-cast ingot size ≈ 35 mm diameter × 15 mm height.", source="Computational Methodologies and Experimental Procedures"),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("MoNbTaV", method=MeasurementMethod.Balance),
                    CompMeasurement({"Mo": 24.9, "Nb": 25.8, "Ta": 26.6, "V": 22.7}, method=MeasurementMethod.EDS, source="Table 2"),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.208)), struct=CrysStruct.BCC, source="The XRD peaks of the alloy are indexed as a single BCC phase. The experimental lattice parameter is mentioned in Table 1."),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.yield_strength_compression, val_in_paper="yield strength"),
                        value=1525,
                        unit=MegaPascal,
                        temperature=Quantity(value=23, unit=Celsius),
                        description="sigma_{0.2}",
                        source="compression because of: Cylindrical specimens for compression testing were electric-discharged machined from the as-cast ingot.",
                    ),
                    Measurement(kind=AlloyMeasurementKind.fracture_strain_compression, value="~21", unit=percent, temperature=Quantity(value=23, unit=Celsius), source="The alloy exhibits about 21% compression strain before fracture"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=4947, unit=MegaPascal, temperature=Quantity(value=23, unit=Celsius)),
                    Measurement(
                        # this is ultimate compressive strength rather than fracture_strength_compression because of the word "maximum"
                        kind=normalize(val=AlloyMeasurementKind.ultimate_compressive_strength, val_in_paper="maximum compressive fracture strength"),
                        value=2.4,
                        unit=GigaPascal,
                        temperature=Quantity(value=23, unit=Celsius),
                        source="the maximum compressive fracture strength is 2.4 GPa",
                    ),
                    Configuration(name="dendrite (C_{dr})", tags={ConfigTag.Dendrite}, measurements=[CompMeasurement({"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9}, method=MeasurementMethod.EDS, source="Table 2")]),
                    Configuration(name="interdendrite (C_{idr})", tags={ConfigTag.Interdendritic}, measurements=[CompMeasurement({"Mo": 19.6, "Nb": 27.5, "Ta": 19.0, "V": 33.9}, method=MeasurementMethod.EDS, source="Table 2")]),
                ],
            ),
            # They mention other compositions like MoNbTaW, (which was processed for 1400C for 19 hours) and had an average grain size of 200 µm, but this is from a different paper.
        ],
    )
]
