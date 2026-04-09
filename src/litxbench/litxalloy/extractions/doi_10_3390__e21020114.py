from pymatgen.core import Lattice

from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CompMeasurement, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    GigaPascal,
    MegaPascal,
    Millimeter,
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
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_tension, AlloyMeasurementKind.ultimate_tensile_strength, AlloyMeasurementKind.fracture_strain_tension, AlloyMeasurementKind.youngs_modulus],
                method=MeasurementMethod.TensileTest,  # machines=[Machine(methods=[MeasurementMethod.TensileTest], model="1185", company="Instron")],
                desc="0.2% offset. Tensile test bodies 5 mm in diameter and 25 mm of measured length were strained with the strain rate of 2 × 10^{-4} s^{-1}, equipped with video extensometer.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.vickers_hardness],
                method=MeasurementMethod.VickersHardnessTest,  # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester])],
                desc="30 kgf load",
            ),
            AlloyDescriptionGroup(kinds=[GlobalLatticeParam], desc="The lattice parameter (a) and phase content were obtained using Rietveld refinement fitting"),
        ],
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="Chemical purity of inserted elements was 99.9%")},
        synthesis_groups=[
            ProcessEvent(
                kind=normalize(ProcessKind.ArcMelting, "Vacuum Arc Melting"),
                description="Experimental alloys were prepared by vacuum arc melting in water cooled copper crucible. Casting was performed 8x times and flipped for each melt to mix the elements thoroughly and suppress chemical heterogeneity",
                source="2. Materials and Methods",
            ),
            ProcessEvent(
                kind=ProcessKind.AsCast,
                description="Final cast ingot has approximately 100 mm in length, 30 mm in width, 10 mm in height and 400 g in weight.",
                source="2. Materials and Methods: Experimental alloys were prepared by vacuum arc melting in water cooled copper crucible",
            ),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("HfNbTaTiZr", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=1155, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=1212, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=12.3, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=59, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=359, unit=HV, temperature=ROOM_TEMPERATURE),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.4089), description="uncertainty of last digit: +-1"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=100, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTaTiZr", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=1144, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=1205, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=6.4, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=98, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=358, unit=HV, temperature=ROOM_TEMPERATURE),
                    Configuration(
                        name="Bright",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 17.0, "Zr": 16.0, "Nb": 32.0, "Ta": 35.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(1 std. dev.), Zr(1 std. dev.), Nb(2 std. dev.), Ta(2 std. dev.)",  # There was a typo in the paper. it said 22 std. dev. but it should be 2 std. dev.
                            )
                        ],
                    ),
                    Configuration(
                        name="Dark",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 25.0, "Zr": 35.0, "Nb": 23.0, "Ta": 17.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Zr(2 std. dev.), Nb(2 std. dev.), Ta(1 std. dev.)",
                            )
                        ],
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3509), description="uncertainty of last digit: +-8"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=60.15, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.380), description="uncertainty of last digit: +-2"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=39.85, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTaTi", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=620, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=683, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=18.5, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=143, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=246, unit=HV, temperature=ROOM_TEMPERATURE),
                    Configuration(
                        name="Bright",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 23.0, "Nb": 28.0, "Ta": 49.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Nb(1 std. dev.), Ta(2 std. dev.)",
                            )
                        ],
                    ),
                    Configuration(
                        name="Dark",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 42.0, "Nb": 28.0, "Ta": 30.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Nb(1 std. dev.), Ta(1 std. dev.)",
                            )
                        ],
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.29685), description="uncertainty of last digit: +-7"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=100, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("TaTiZr", method=MeasurementMethod.Balance),
                    # yield strength was too brittle - but I'm not sure how we should represent this?
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=284, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=0, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=157, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=485, unit=HV, temperature=ROOM_TEMPERATURE),
                    Configuration(
                        name="Bright",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 32.0, "Zr": 16.0, "Ta": 52.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Zr(2 std. dev.), Ta(2 std. dev.)",
                            )
                        ],
                    ),
                    Configuration(
                        name="Dark",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 40.0, "Zr": 35.0, "Ta": 25.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(3 std. dev.), Zr(3 std. dev.), Ta(1 std. dev.)",
                            )
                        ],
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.446), description="uncertainty of last digit: +-1"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=29.08, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3184), description="uncertainty of last digit: +-2"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=70.92, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                    Configuration(
                        name="Matrix",
                        source="3.4 Microstructure",
                        measurements=[
                            CompMeasurement({"Ta": 38}, method=MeasurementMethod.Balance, validate_composition=False),  # (38 +- 1) at.%
                        ],
                    ),
                    Configuration(
                        name="submicron precipitates",
                        description="Found on grain boundaries",
                        source="3.4 Microstructure",
                        measurements=[
                            CompMeasurement({"Ta": 52}, method=MeasurementMethod.Balance, validate_composition=False),  # (52 +- 1) at.%
                        ],
                    ),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTiZr", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=956, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=991, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=14.2, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=88, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=295, unit=HV, temperature=ROOM_TEMPERATURE),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3969), description="uncertainty of last digit: +-1"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=100, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Nb1.5TaTiZr0.5", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=822, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=852, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=0.33, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=127, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=294, unit=HV, temperature=ROOM_TEMPERATURE),
                    Configuration(
                        name="Bright",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 13.0, "Zr": 7.0, "Nb": 41.0, "Ta": 39.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(1 std. dev.), Zr(1 std. dev.), Nb(3 std. dev.), Ta(3 std. dev.)",
                            )
                        ],
                    ),
                    Configuration(
                        name="Dark",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 22.0, "Zr": 22.0, "Nb": 36.0, "Ta": 20.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Zr(2 std. dev.), Nb(2 std. dev.), Ta(2 std. dev.)",
                            ),
                        ],
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3220), description="uncertainty of last digit: +-5"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=28.25, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.334), description="uncertainty of last digit: +-2"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=71.22, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3273), description="uncertainty of last digit: +-2"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=0.53, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                    Configuration(name="submicron precipitates", description="Found on grain boundaries. Rich in Ta", source="3.4 Microstructure"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Nb0.5TaTiZr1.5", method=MeasurementMethod.Balance),
                    # yield strength was too brittle - but I'm not sure how we should represent this?
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=843, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="A[%]"), value=0, unit=percent, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=93, unit=GigaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=489, unit=HV, temperature=ROOM_TEMPERATURE),
                    Configuration(
                        name="Bright",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 19.0, "Zr": 28.0, "Nb": 16.0, "Ta": 37.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(1 std. dev.), Zr(1 std. dev.), Nb(1 std. dev.), Ta(2 std. dev.)",
                            )
                        ],
                    ),
                    Configuration(
                        name="Dark",
                        measurements=[
                            CompMeasurement(
                                {"Ti": 22.0, "Zr": 42.0, "Nb": 15.0, "Ta": 21.0},
                                method=MeasurementMethod.WDS,
                                description="uncertainties: Ti(2 std. dev.), Zr(3 std. dev.), Nb(2 std. dev.), Ta(2 std. dev.)",
                            ),
                        ],
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.451), description="uncertainty of last digit: +-5"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=19.64, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.3395), description="uncertainty of last digit: +-3"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=77.97, unit=percent),
                        source="Table 5",
                    ),
                    GlobalLatticeParam(
                        lattice=LatticeMeasurement(lattice=Lattice.cubic(3.4121), description="uncertainty of last digit: +-4"),
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=2.39, unit=percent),
                        source="Table 5",
                    ),
                    Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.5", unit=Millimeter, source="grain size around 0.5 mm which is similar for all alloys."),
                    Configuration(name="submicron precipitates", description="Found on grain boundaries. Rich in Ta", source="3.4 Microstructure"),
                ],
            ),
        ],
    )
]
