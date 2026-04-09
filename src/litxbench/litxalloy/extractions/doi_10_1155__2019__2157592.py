from pymatgen.core.composition import Composition

from litxbench.core.models import ProcessEvent, ProcessKind, Quantity, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    Celsius,
    Hour,
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
    # hardness values are provided in figure 11 but they don't give us the exact numbers in a table
    # - Note: figure 11 also plots heat-treated samples.
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="Ti and Mn were added as ferroalloys, while Ni and Al were added as pure metals.")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[PhaseMeasurementKind.volume_fraction],
                method=MeasurementMethod.OpticalMicroscope,
                # machines=[Machine(methods=[MeasurementMethod.OpticalMicroscope])],
                desc="Image analysis software 'Zeiss' attached to the optical microscope was used for quantitative analysis of the microstructure constituents at 100X magnification.",
            ),
        ],
        synthesis_groups={
            "creation[Thickness]": [
                ProcessEvent(kind=ProcessKind.InductionMelting, source="Experimental Work"),
                ProcessEvent(kind=ProcessKind.GravityCasting, description="samples were poured in a mold shaped as Y blocks of [Thickness]mm thickness.", source="Experimental Work"),
            ],
            "annealing[Hours]": [ProcessEvent(kind=ProcessKind.Annealing, temperature=Quantity(value=900, unit=Celsius), duration=Quantity(value="[Hours]", unit=Hour), source="Experimental Work")],
        },
        output_materials=[
            Material(
                # from table 1
                process="elements->creation[Thickness=30]",
                name="C1",
                measurements=[
                    CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0})),
                    Configuration(name="white phase", measurements=[Measurement(kind=PhaseMeasurementKind.volume_fraction, value=33.5, unit=percent, source="Figure 2 (a)")]),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=300, unit=HV, source="Abstract"),
                    Measurement(
                        kind=AlloyMeasurementKind.vickers_hardness,
                        value="~310",
                        unit=HV,
                        source="3.3. Mechanical Properties Evaluation: addition of Ti up to 3.0 wt.% increased significantly the hardness of the alloy from ∼310 to 500 (Hv).",  # I think this is the more accurate value than the abstract. The paper is itself inconsistent
                    ),
                ],
            ),
            Material(process="C1->annealing[Hours=10]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0}))]),
            Material(process="C1->annealing[Hours=20]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0}))]),
            # this is a special sample:
            # This sample is from: Another Y block of 5mm thickness was used to prepare a 0.0 wt.% Ti sample at higher cooling rate.
            # Increasing the cooling rate by decreasing the section size down to 5 mm showed little improvement in the hardness
            # we know it's composition  because figure 8 mentions this 5mm sample: Figure 8: Optical micrographs of the 10 h heat-treated samples: (a) C1, (b) C2, and (c) C3 at 30 mm and (d) C1 at 5 mm.
            # the lamellar spacing decreased when the cooling rate increased due to the change in the thickness from 30 to 5 mm at the same Ti content (0.0%).
            Material(
                process="elements->creation[Thickness=5]",
                name="C1 5mm",
                measurements=[
                    CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0})),
                ],
            ),
            Material(process="C1 5mm->annealing[Hours=10]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0}))]),  # we know this sample exists because of figure 8:
            Material(process="C1 5mm->annealing[Hours=20]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.1, "Mn": 31.1, "Ni": 18.1, "Al": 13.6, "Si": 1.5, "Ti": 0}))]),  # we know this sample exists because of figure 9:
            Material(
                # from table 1
                process="elements->creation[Thickness=30]",
                name="C2",
                measurements=[
                    CompMeasurement(Composition.from_weight_dict({"Fe": 35.6, "Mn": 31.3, "Ni": 18.3, "Al": 13.6, "Si": 1.5, "Ti": 0.8})),
                    Configuration(name="white phase", measurements=[Measurement(kind=PhaseMeasurementKind.volume_fraction, value=45, unit=percent, source="Figure 2 (b)")]),
                ],
            ),
            Material(process="C2->annealing[Hours=10]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.6, "Mn": 31.3, "Ni": 18.3, "Al": 13.6, "Si": 1.5, "Ti": 0.8}))]),
            Material(process="C2->annealing[Hours=20]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 35.6, "Mn": 31.3, "Ni": 18.3, "Al": 13.6, "Si": 1.5, "Ti": 0.8}))]),
            Material(
                # from table 1
                process="elements->creation[Thickness=30]",
                name="C3",
                measurements=[
                    CompMeasurement(Composition.from_weight_dict({"Fe": 36.9, "Mn": 28.7, "Ni": 15.8, "Al": 12.6, "Si": 2.3, "Ti": 3.3})),
                    Configuration(name="white phase", measurements=[Measurement(kind=PhaseMeasurementKind.volume_fraction, value=65, unit=percent, source="Figure 2 (c)")]),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=500, unit=HV, source="3.3. Mechanical Properties Evaluation: addition of Ti up to 3.0 wt.% increased significantly the hardness of the alloy from ∼310 to 500 (Hv)."),
                ],
            ),
            Material(process="C3->annealing[Hours=10]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 36.9, "Mn": 28.7, "Ni": 15.8, "Al": 12.6, "Si": 2.3, "Ti": 3.3}))]),
            Material(process="C3->annealing[Hours=20]", measurements=[CompMeasurement(Composition.from_weight_dict({"Fe": 36.9, "Mn": 28.7, "Ni": 15.8, "Al": 12.6, "Si": 2.3, "Ti": 3.3}))]),
        ],
    )
]
