from pymatgen.core import Composition, Lattice

from litxbench.core.extraction_utils import composition_with_weight_additions, normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CrysStruct, GlobalLatticeParam, LatticeMeasurement, MeasurementStatistic, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    AmpPerCmSquared,
    Hour,
    Micrometer,
    MillimeterPerYear,
    Nanometer,
    Volt,
    dimensionless,
    gram_per_cm3,
)
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMaterial as Material,
    AlloyMeasurementKind,
    AlloyMeasurementKind as MeasurementKind,
    AlloyMeasurementMethod as MeasurementMethod,
    Measurement,
    ProcessEvent,
    ProcessKind,
    Quantity,
)

experiments: list[Experiment] = [
    # This one is quite interesting. Their HEA is a coating ontop of a flat steel plate.
    # Electrochemical corrosion parameters are in table 5
    Experiment(
        descriptions=[
            AlloyDescriptionGroup(kinds=[MeasurementKind.vickers_hardness], method=MeasurementMethod.VickersHardnessTest, desc="The microhardness (HV) of the HEACs was measured with the Vickers hardness tester"),
            # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester])],
            AlloyDescriptionGroup(kinds=[ProcessKind.Grinding], desc="performed on a grinding wheel"),
        ],
        raw_materials={
            "elements": RawMaterial(kind=RawMaterialKind.Powder, description="Co, Cr, Fe, and Ni powders with high purity (99.9 wt.%) with powder size <75 µm"),
            "wc_additions": RawMaterial(kind=normalize(RawMaterialKind.Powder, "WC particles")),
            "Q235 steel substrate": RawMaterial(kind=RawMaterialKind.Plate),
        },
        synthesis_groups={
            "prepare_steel": [
                ProcessEvent(kind=ProcessKind.Grinding, description="400 mesh sandpaper"),
                ProcessEvent(kind=ProcessKind.Grinding, description="800 mesh sandpaper"),
                ProcessEvent(kind=ProcessKind.Grinding, description="1200 mesh sandpaper"),
                ProcessEvent(kind=ProcessKind.Degreased, description="using absolute ethyl alcohol"),
                ProcessEvent(kind=ProcessKind.AirDrying),
            ],
            "creation": [
                ProcessEvent(
                    kind=ProcessKind.MechanicalAlloying,
                    description="mixed at 350 revolutions per minute (rpm) in an argon atmosphere. High-performance stainless-steel vials and balls were utilized, and the ball-to-powder mass ratio was 15:1. The diameters of milling balls used were 10, 6, and 3 mm, and the mass ratio of these three kinds of balls was 1:1:1",
                    source="Experimental Procedure",
                    duration=Quantity(value=200, unit=Hour),
                ),
                ProcessEvent(
                    kind=ProcessKind.Mixing,
                    inputs=["elements", "wc_additions"],
                    description="elements and wc_additions are mixed.",
                    source="Then, the 200 h milled CoCrFeNi HEA powders and different weight ratios of WC particles (10 and 30 wt.%) were uniformly mixed together for the subsequent VHPS process.",
                ),
                ProcessEvent(kind=normalize(ProcessKind.HotPressingSintering, "Vacuum Hot Pressing Sintering"), description="35 mm inner-diameter graphite die at 950◦C for 30 min under a constant axial pressure of 30 MPa.", source="Experimental Procedure"),
            ],
        },
        # "Then, the 200 h milled CoCrFeNi HEA powders and different weight ratios of WC particles (10 and 30 wt.%) were uniformly mixed together for the subsequent VHPS process"
        # Table 5 has ΔEp (passivation region) but we omit it since it's derived: ΔEp = Epit - Ecorr
        output_materials=[
            # consider commenting this out? since this sample is from their previous paper
            # I'll comment it out for now since these values are from their previous paper.
            # Material(
            #     process="prepared_steel->creation",
            #     measurements=[
            #         # The CoCrFeNi grain size/lattice (Table 2) and hardness (450 HV) are from reference 13 (same lab group): https://www.sciencedirect.com/science/article/abs/pii/S2468023017300767?via%3Dihub
            #         # but the corrosion data in Table 5 was measured in this study ("the CoCrFeNi HEAC was selected as the reference object tested in the same corrosion conditions").
            #         # Note: that paper is from the same lab group. so I guess we can trust these numbers. They didn't re-make the standalone CoCrFeNi HEA themselves.
            #         # But we can trust the corrosion numbers reported in table 5 since it's the same lab setup from the same lab group.
            #         CompMeasurement(Composition("CoCrFeNi"), method=MeasurementMethod.Balance),
            #         Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=450, unit=HV, source="the WC additions obviously enhanced the microhardness of CoCrFeNi HEAC (450 HV)"),
            #         Measurement(kind=normalize("corrosion_potential", "Ecorr(V vs. Ag/AgCl)"), value=-1.08, unit=Volt, uncertainty=0.04, source="Table 5"),
            #         Measurement(kind=normalize("pitting_potential", "Epit(V vs. Ag/AgCl)"), value=0.12, unit=Volt, uncertainty=0.01, source="Table 5"),
            #         Measurement(kind=normalize("passivation_current_density", "ipass(A·cm-2)"), value=2.29e-4, unit=AmpPerCmSquared, source="Table 5"),
            #         Measurement(kind=normalize("corrosion_current_density", "icorr(A·cm-2)"), value=2.26e-5, unit=AmpPerCmSquared, source="Table 5"),
            #         Measurement(kind=normalize("corrosion_rate", "rcorr(mm/year)"), value=1.28e-1, unit=MillimeterPerYear, source="Table 5"),
            #         GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.574)), struct=CrysStruct.FCC, source="Table 2"),
            #         Configuration(name="FCC Phase", measurements=[Measurement(kind=MeasurementKind.crystallite_size, value=27.6, unit=Nanometer, source="Table 2", measurement_statistic=MeasurementStatistic.mean)]),
            #         Measurement(kind=normalize("friction_coefficient", "mean friction coefficient"), value=0.38, unit=dimensionless, source="the mean friction coefficient of CoCrFeNi HEAC was 0.38 [13]"),
            #         Measurement(kind=normalize("wear_groove_depth", "wear groove depth"), value=19.8, unit=Micrometer, source="shallower than those of the substrate (25.5 µm) and CoCrFeNi HEAC (19.8 µm)"),
            #     ],
            # ),
            Material(
                name="prepared_steel",
                process="Q235 steel substrate->prepare_steel",
                measurements=[
                    # "the CoCrFeNi HEAC was selected as the reference object tested in the same corrosion conditions."
                    CompMeasurement(Composition.from_weight_dict({"C": 0.15, "Si": 0.2, "Mn": 0.46, "S": 0.022, "P": 0.012, "Fe": 99.156}), source="Table 1", method=MeasurementMethod.Unspecified),  # this is the composition from the supplier so we don't know
                    # I considered adding these corrosion measurements to a raw Q235 steel substrate sample, but I believe they performed corrision on the prepared steel.
                    # This is because grinding is standard preparation for electrochemical testing. (surface roughness might accelerate corrosion)
                    Measurement(kind=normalize("corrosion_potential", "Ecorr(V vs. Ag/AgCl)"), value=-1.14, unit=Volt, uncertainty=0.03, source="Table 5"),
                    Measurement(kind=normalize("pitting_potential", "Epit(V vs. Ag/AgCl)"), value=-0.34, unit=Volt, uncertainty=0.04, source="Table 5"),
                    Measurement(kind=normalize("passivation_current_density", "ipass(A·cm-2)"), value=5.43e-4, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_current_density", "icorr(A·cm-2)"), value=5.89e-5, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_rate", "rcorr(mm/year)"), value=6.85e-1, unit=MillimeterPerYear, source="Table 5"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=160, unit=HV, source="the microhardness was more than 3 times larger than the substrate (160 HV)"),
                    Measurement(kind=normalize("friction_coefficient", "mean friction coefficient"), value=0.87, unit=dimensionless, source="more than 61% lower than that of Q235 substrate (0.87)"),
                    Measurement(kind=normalize("wear_groove_depth", "wear groove depth"), value=25.5, unit=Micrometer, source="the substrate (25.5 µm)"),
                ],
            ),
            Material(
                process="prepared_steel->creation",
                measurements=[
                    CompMeasurement(
                        composition_with_weight_additions(Composition("CoCrFeNi"), Composition("WC"), 0.1),
                        method=MeasurementMethod.Balance,
                    ),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=475, unit=HV, source="The average microhardness values of CoCrFeNi HEACs with 10 and 30 wt.% WC additions HEACs reached 475 and 531 HV respectively"),
                    Measurement(kind=AlloyMeasurementKind.density, value=7.24, unit=gram_per_cm3, uncertainty=0.02, source="Table 4"),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.574)), struct=CrysStruct.FCC, source="Table 2"),
                    # Crystallite sizes (Table 2, XRD Scherrer) and EDS compositions (Table 3, spot analysis) are kept as separate configurations:
                    # crystallite size is a bulk-averaged coherent domain size per phase, not the physical size of the grains/regions probed by EDS.
                    Configuration(name="FCC Phase", measurements=[Measurement(kind=AlloyMeasurementKind.crystallite_size, value=18.9, unit=Nanometer, source="Table 2", measurement_statistic=MeasurementStatistic.mean)]),
                    Configuration(name="WC Phase", measurements=[Measurement(kind=AlloyMeasurementKind.crystallite_size, value=25.3, unit=Nanometer, source="In addition, there was no apparent change of D values (25.3 nm) of the WC phase in both coatings.", measurement_statistic=MeasurementStatistic.mean)]),
                    Configuration(name="WC Grains (bright)", measurements=[CompMeasurement({"Co": 2.3, "Cr": 2.4, "Fe": 2.4, "Ni": 3.0, "W": 45.8, "C": 44.1}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Configuration(name="FCC Matrix (gray)", tags={ConfigTag.Matrix}, measurements=[CompMeasurement({"Co": 23.2, "Cr": 23.9, "Fe": 26.9, "Ni": 24.6, "W": 0.6, "C": 0.8}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Measurement(kind=normalize("corrosion_potential", "Ecorr(V vs. Ag/AgCl)"), value=-0.99, unit=Volt, uncertainty=0.01, source="Table 5"),
                    Measurement(kind=normalize("pitting_potential", "Epit(V vs. Ag/AgCl)"), value=0, unit=Volt, uncertainty=0.02, source="Table 5"),
                    Measurement(kind=normalize("passivation_current_density", "ipass(A·cm-2)"), value=1.78e-4, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_current_density", "icorr(A·cm-2)"), value=1.22e-5, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_rate", "rcorr(mm/year)"), value=1.34e-1, unit=MillimeterPerYear, source="Table 5"),
                    Measurement(kind=normalize("friction_coefficient", "mean friction coefficient"), value=0.34, unit=dimensionless, source="The mean friction coefficients of CoCrFeNi HEACs with 10 and 30 wt.% WC addition were 0.34 and 0.30 respectively"),
                    Measurement(kind=normalize("wear_groove_depth", "wear groove depth"), value=17.7, unit=Micrometer, source="The values of the wear groove depth for HEACs with 10 and 30 wt.% WC additions were 17.7 and 15.1 µm respectively"),
                    Measurement(kind=normalize("coating_thickness", "average coating thickness"), value=860, unit=Micrometer, source="the average thickness values of coatings are of 860 and 900 µm for 10 and 30 wt.% WC HEACs, respectively"),
                ],
            ),
            Material(
                process="prepared_steel->creation",
                measurements=[
                    CompMeasurement(
                        composition_with_weight_additions(Composition("CoCrFeNi"), Composition("WC"), 0.3),
                        method=MeasurementMethod.Balance,
                    ),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=531, unit=HV, source="The average microhardness values of CoCrFeNi HEACs with 10 and 30 wt.% WC additions HEACs reached 475 and 531 HV respectively"),
                    Measurement(kind=AlloyMeasurementKind.density, value=8.39, unit=gram_per_cm3, uncertainty=0.03, source="Table 4"),
                    GlobalLatticeParam(lattice=LatticeMeasurement(Lattice.cubic(3.574)), struct=CrysStruct.FCC, source="Table 2"),
                    # Crystallite sizes (Table 2, XRD Scherrer) and EDS compositions (Table 3, spot analysis) are kept as separate configurations:
                    # crystallite size is a bulk-averaged coherent domain size per phase, not the physical size of the grains/regions probed by EDS.
                    Configuration(name="FCC Phase", measurements=[Measurement(kind=AlloyMeasurementKind.crystallite_size, value=18.2, unit=Nanometer, source="Table 2", measurement_statistic=MeasurementStatistic.mean)]),
                    Configuration(name="WC Phase", measurements=[Measurement(kind=AlloyMeasurementKind.crystallite_size, value=25.3, unit=Nanometer, source="In addition, there was no apparent change of D values (25.3 nm) of the WC phase in both coatings.", measurement_statistic=MeasurementStatistic.mean)]),
                    Configuration(name="WC Grains (bright)", measurements=[CompMeasurement({"Co": 1.2, "Cr": 2.4, "Fe": 1.2, "Ni": 0.6, "W": 48.3, "C": 46.3}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Configuration(name="FCC Matrix (gray)", tags={ConfigTag.Matrix}, measurements=[CompMeasurement({"Co": 23.5, "Cr": 25.9, "Fe": 25.2, "Ni": 24.3, "W": 0.4, "C": 0.7}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Measurement(kind=normalize("corrosion_potential", "Ecorr(V vs. Ag/AgCl)"), value=-0.95, unit=Volt, uncertainty=0.02, source="Table 5"),
                    Measurement(kind=normalize("pitting_potential", "Epit(V vs. Ag/AgCl)"), value=-0.03, unit=Volt, uncertainty=0.03, source="Table 5"),
                    Measurement(kind=normalize("passivation_current_density", "ipass(A·cm-2)"), value=3.89e-4, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_current_density", "icorr(A·cm-2)"), value=2.60e-5, unit=AmpPerCmSquared, source="Table 5"),
                    Measurement(kind=normalize("corrosion_rate", "rcorr(mm/year)"), value=2.34e-1, unit=MillimeterPerYear, source="Table 5"),
                    Measurement(kind=normalize("friction_coefficient", "mean friction coefficient"), value=0.30, unit=dimensionless, source="The mean friction coefficients of CoCrFeNi HEACs with 10 and 30 wt.% WC addition were 0.34 and 0.30 respectively"),
                    Measurement(kind=normalize("wear_groove_depth", "wear groove depth"), value=15.1, unit=Micrometer, source="The values of the wear groove depth for HEACs with 10 and 30 wt.% WC additions were 17.7 and 15.1 µm respectively"),
                    Measurement(kind=normalize("coating_thickness", "average coating thickness"), value=900, unit=Micrometer, source="the average thickness values of coatings are of 860 and 900 µm for 10 and 30 wt.% WC HEACs, respectively"),
                ],
            ),
        ],
    )
]
