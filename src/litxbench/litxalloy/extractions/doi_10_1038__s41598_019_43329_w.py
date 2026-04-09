from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import CrysStruct, ProcessEvent, ProcessKind, Quantity, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    Celsius,
    GigaPascal,
    MegaPascal,
    gram_per_cm3,
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
)

# TODO: we should consider adding specific strength values from table 3
experiments: list[Experiment] = [
    # Liquidus measurements are from Thermo-Calc. so they are not specified as measurements
    Experiment(
        descriptions=[
            AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], method=MeasurementMethod.VickersHardnessTest, desc="Used a load of 0.1kg (for 10 seconds)"),
            # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester], model="FM-700", company="Future-Tech", location="Kawasaki, Japan")],
            AlloyDescriptionGroup(
                kinds=[
                    AlloyMeasurementKind.youngs_modulus,
                    normalize(
                        AlloyMeasurementKind.fracture_strain_compression,
                        "plastic strain",
                        source="They say: 'In this study, the fracture strength and the plastic strain were defined as the maximum stress and the maximum deformation in the stress-strain curve'. The maximum point is the end of the curve, so it really is the fracture strain. I looked at the graph and verified that these strain percents are the entire length of the line - so fracture strain",
                    ),
                    AlloyMeasurementKind.yield_strength_compression,
                    AlloyMeasurementKind.ultimate_compressive_strength,
                ],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest], model="Insight 100 kN", company="MTS")],
                desc=f"Compression testing was performed at RT with a strain rate of 0.001 s^{-1}",
            ),
            AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.density], method=MeasurementMethod.ArchimedesMethod, desc="density measurement was conducted using the Archimedes method. No machine was specified."),
            # machines=[Machine(methods=[MeasurementMethod.ArchimedesMethod])],
        ],
        raw_materials={
            "elements": RawMaterial(
                kind=RawMaterialKind.Ingot,
                description="99.95% pure Al, Cu, Fe, Mg, Si and Zn. Tablets of Al-Cr, Al-Mn, Al-Ni and Al-Zr containing 75 wt.% of Cr, 80 wt., 80 wt.% of Mn, 80 wt.% of Ni and 75 wt.% of Zr respectively were used.",
            )
        },
        synthesis_groups={
            "melting[Temp]": [
                ProcessEvent(
                    kind=ProcessKind.InductionMelting,
                    description="Firstly, Al and Si were placed at the bottom of the crucible to guarantee a bath base where the other elements were dissolved from highest to lowest melting point. In the second stage, the variable element of each alloy (Fe, Ni, Cr, Mn or Zr) was added to the molten alloy. The maximum temperature was reached at this stage. Finally, Cu, Zn and Mg were added respectively and held around 750 °C, at least 10 minutes to reach complete dissolution.",
                    temperature=Quantity(value="[Temp]", unit=Celsius),
                    source="Methods->Materials preparation and table 4 for the actual maximum furnace temperatures",
                ),
            ],
            "casting[Temp]": [
                ProcessEvent(kind=ProcessKind.GravityCasting, description="casting temp is [Temp]. The melt was poured manually into a steel mould", source="Methods->Materials preparation. The casting temp was from Table 4"),
            ],
        },
        output_materials=[
            Material(
                name="MEA-1",  # labelled by figure 5
                process="elements->melting[Temp=790]->casting[Temp=760]",
                measurements=[
                    CompMeasurement("Al65Cu5Fe5Mg5Si15Zn5", method=MeasurementMethod.Balance),
                    CompMeasurement({"Al": 64, "Mg": 6, "Si": 13, "Zn": 6, "Cu": 5, "Fe": 4, "O": 2}, method=MeasurementMethod.EDS, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.density, value=3.08, unit=gram_per_cm3, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=422, unit=MegaPascal, uncertainty=75, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=235, unit=HV, uncertainty=85),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=482, unit=MegaPascal, uncertainty=98, temperature=ROOM_TEMPERATURE, source="Table 3"),  # in the paper it's Maximum Compressive Strength
                    Measurement(kind=normalize(AlloyMeasurementKind.fracture_strain_compression, "plastic strain"), value=1, unit=percent, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=88.7, unit=GigaPascal, uncertainty=4, source="Table 3"),  # uncertainty is 04 but we don't have sig figs support here
                    Configuration(name="FCC solid solution", struct=CrysStruct.FCC, description="S.G. = 225", source="Figure 3(a): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Si", struct=CrysStruct.Diamond, description="S.G. = 227", source="Figure 3(a): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="V-Mg2Zn11", description="S.G. = 218", source="Figure 3(a): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Al2Cu", description="S.G. = 140", source="Figure 3(a): 'The XRD pattern in Fig. 3(a) also showed the formation of Al2Cu (S.G. = 140), AlxCu2Mg6Si7 (S.G. = 174) and Al9Fe2Si2 phase (S.G. = 14) in Al65Cu5Fe5Mg5Si15Zn5 alloy.'"),
                    Configuration(name="AlxCu2Mg6Si7", description="S.G. = 174", source="Figure 3(a): 'The XRD pattern in Fig. 3(a) also showed the formation of Al2Cu (S.G. = 140), AlxCu2Mg6Si7 (S.G. = 174) and Al9Fe2Si2 phase (S.G. = 14) in Al65Cu5Fe5Mg5Si15Zn5 alloy.'"),  # Q-phase
                    Configuration(name="Al9Fe2Si2", description="S.G. = 14", source="Figure 3(a): 'The XRD pattern in Fig. 3(a) also showed the formation of Al2Cu (S.G. = 140), AlxCu2Mg6Si7 (S.G. = 174) and Al9Fe2Si2 phase (S.G. = 14) in Al65Cu5Fe5Mg5Si15Zn5 alloy.'"),
                ],
            ),
            Material(
                process="elements->melting[Temp=785]->casting[Temp=759]",
                name="MEA-2",
                measurements=[
                    CompMeasurement("Al65Cu5Mg5Ni5Si15Zn5", method=MeasurementMethod.Balance),
                    CompMeasurement({"Al": 64, "Mg": 7, "Si": 12, "Zn": 5, "Cu": 4, "Ni": 5, "O": 3}, method=MeasurementMethod.EDS, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.density, value=3.15, unit=gram_per_cm3, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=534, unit=MegaPascal, uncertainty=4, source="Table 3"),  # uncertainty is 04 but we don't have sig figs support here
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=260, unit=HV, uncertainty=32),
                    Configuration(name="Mg-Si-rich", measurements=[CompMeasurement({"Mg": 54, "Si": 28, "O": 18}, source="Table 2")]),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=574, unit=MegaPascal, uncertainty=32, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(AlloyMeasurementKind.fracture_strain_compression, "plastic strain"), value=1, unit=percent, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=107.8, unit=GigaPascal, uncertainty=17, source="Table 3"),
                    Configuration(name="FCC solid solution", struct=CrysStruct.FCC, description="S.G. = 225", source="Figure 3(b): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Si", struct=CrysStruct.Diamond, description="S.G. = 227", source="Figure 3(b): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="V-Mg2Zn11", description="S.G. = 218", source="Figure 3(b): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Al3Ni", description="S.G. = 62", source="Figure 3(b): 'Figure 3(b) detailed the XRD pattern of Al65Cu5Mg5Ni5Si15Zn5 alloy. The pattern also showed the formation of Al3Ni (S.G. = 62), Al3Ni2 (S.G. = 164) and Mg2Si (S.G. = 225).'"),
                    Configuration(name="Al3Ni2", description="S.G. = 164", source="Figure 3(b): 'Figure 3(b) detailed the XRD pattern of Al65Cu5Mg5Ni5Si15Zn5 alloy. The pattern also showed the formation of Al3Ni (S.G. = 62), Al3Ni2 (S.G. = 164) and Mg2Si (S.G. = 225).'"),
                    Configuration(name="Mg2Si", description="S.G. = 225", source="Figure 3(b): 'Figure 3(b) detailed the XRD pattern of Al65Cu5Mg5Ni5Si15Zn5 alloy. The pattern also showed the formation of Al3Ni (S.G. = 62), Al3Ni2 (S.G. = 164) and Mg2Si (S.G. = 225).'"),
                ],
            ),
            Material(
                process="elements->melting[Temp=780]->casting[Temp=744]",
                name="MEA-3",
                measurements=[
                    CompMeasurement("Al70Cr5Cu5Mg5Si10Zn5", method=MeasurementMethod.Balance),
                    CompMeasurement({"Al": 73, "Mg": 5, "Si": 7, "Zn": 6, "Cu": 3, "Cr": 4, "O": 2}, method=MeasurementMethod.EDS, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.density, value=3.06, unit=gram_per_cm3, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=490, unit=MegaPascal, uncertainty=18, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=200, unit=HV, uncertainty=18),
                    Configuration(name="Mg-Si-rich", measurements=[CompMeasurement({"Mg": 41, "Si": 23, "O": 24, "Al": 12}, source="Table 2")], source="Table 2"),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=608, unit=MegaPascal, uncertainty=30, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(AlloyMeasurementKind.fracture_strain_compression, "plastic strain"), value=6, unit=percent, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=78.4, unit=GigaPascal, uncertainty=3, source="Table 3"),  # uncertainty is 03 but we don't have sig figs support here
                    Configuration(name="FCC solid solution", struct=CrysStruct.FCC, description="S.G. = 225", source="Figure 3(c): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Si", struct=CrysStruct.Diamond, description="S.G. = 227", source="Figure 3(c): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="V-Mg2Zn11", description="S.G. = 218", source="Figure 3(c): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Mg2Si", description="S.G. = 225", source="Figure 3(c): 'The XRD pattern also showed the formation of Mg2Si and Al13Cr4Si4 (S.G. = 216) phases. The other indexed phases showed good agreement with CALPHAD calculations in Fig. 2(c).'"),
                    Configuration(name="Al13Cr4Si4", description="S.G. = 216", source="Figure 3(c): 'The XRD pattern also showed the formation of Mg2Si and Al13Cr4Si4 (S.G. = 216) phases. The other indexed phases showed good agreement with CALPHAD calculations in Fig. 2(c).'"),
                ],
            ),
            Material(
                process="elements->melting[Temp=830]->casting[Temp=750]",
                name="MEA-4",
                measurements=[
                    CompMeasurement("Al70Cu5Mg5Mn5Si10Zn5", method=MeasurementMethod.Balance),
                    CompMeasurement({"Al": 66, "Mg": 6, "Si": 11, "Zn": 6, "Cu": 4, "Mn": 4, "O": 3}, method=MeasurementMethod.EDS, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.density, value=2.98, unit=gram_per_cm3, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=622, unit=MegaPascal, uncertainty=15, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=264, unit=HV, uncertainty=57),
                    Configuration(name="Mg-Si-rich", measurements=[CompMeasurement({"Mg": 55, "Si": 29, "O": 16}, source="Table 2")]),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=644, unit=MegaPascal, uncertainty=13, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(AlloyMeasurementKind.fracture_strain_compression, "plastic strain"), value=2, unit=percent, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=114.1, unit=GigaPascal, uncertainty=2, source="Table 3"),  # uncertainty is 02 but we don't have sig figs support here
                    Configuration(name="FCC solid solution", struct=CrysStruct.FCC, description="S.G. = 225", source="Figure 3(d): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Si", struct=CrysStruct.Diamond, description="S.G. = 227", source="Figure 3(d): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="V-Mg2Zn11", description="S.G. = 218", source="Figure 3(d): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Mg2Si", description="S.G. = 225", source="Figure 3(d): 'Figure 3(d) detailed the XRD pattern of Al70Cu5Mg5Mn5Si10Zn5 alloy. The diagram is very similar to the diagram represented in Fig. 3(c)... In this case, the formation of the Mg2Si phase mentioned above was also observed.'"),
                    Configuration(
                        name="Al4MnSi", description="S.G. = 194", source="Figure 3(d): 'Figure 3(d) detailed the XRD pattern of Al70Cu5Mg5Mn5Si10Zn5 alloy. The diagram is very similar to the diagram represented in Fig. 3(c), but Al4MnSi (S.G. = 194) phase was observed instead of Al13Cr4Si4 indexed in Fig. 3(c).'"
                    ),
                ],
            ),
            Material(
                process="elements->melting[Temp=850]->casting[Temp=742]",
                name="MEA-5",
                measurements=[
                    CompMeasurement("Al70Cu5Mg5Si10Zn5Zr5", method=MeasurementMethod.Balance),
                    CompMeasurement({"Al": 66, "Mg": 7, "Si": 9, "Zn": 6, "Cu": 7, "Zr": 3, "O": 2}, method=MeasurementMethod.EDS, source="Table 1"),
                    Measurement(kind=AlloyMeasurementKind.density, value=3.06, unit=gram_per_cm3, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=565, unit=MegaPascal, uncertainty=79, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=220, unit=HV, uncertainty=37),
                    Configuration(name="Mg-Si-rich", measurements=[CompMeasurement({"Mg": 55, "Si": 30, "O": 15}, source="Table 2")]),
                    Measurement(kind=AlloyMeasurementKind.ultimate_compressive_strength, value=633, unit=MegaPascal, uncertainty=42, temperature=ROOM_TEMPERATURE, source="Table 3"),
                    Measurement(kind=normalize(AlloyMeasurementKind.fracture_strain_compression, "plastic strain"), value=4, unit=percent, source="Table 3"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=105.1, unit=GigaPascal, uncertainty=27, source="Table 3"),
                    Configuration(name="FCC solid solution", struct=CrysStruct.FCC, description="S.G. = 225", source="Figure 3(e): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="Si", struct=CrysStruct.Diamond, description="S.G. = 227", source="Figure 3(e): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(name="V-Mg2Zn11", description="S.G. = 218", source="Figure 3(e): 'The XRD patterns in Fig. 3 showed at least the formation of FCC solid solution (Space Group = 225), Si (S.G. = 227) and V-Mg2Zn11 (S.G. = 218) in all the alloys.'"),
                    Configuration(
                        name="Mg2Si",
                        description="S.G. = 225",
                        source="Figure 3(e): 'The diagram showed similar diffraction peaks to those observed in Fig. 3(c,d).' Fig. 3(c) text states 'Figure 3(c) detailed the XRD pattern of Al65Cu5Mg5Ni5Si15Zn5 alloy. The XRD pattern also showed the formation of Mg2Si and Al13Cr4Si4 (S.G. = 216) phases.' Fig. 3(d) text states 'In this case, the formation of the Mg2Si phase mentioned above was also observed.'",
                    ),
                    Configuration(
                        name="τ1-(Al,Zr,Si)",
                        description="S.G. = 194",
                        source="Figure 3(e): 'Figure 3(e) detailed the XRD pattern of Al70Cu5Mg5Si10Zn5Zr5 alloy. The diagram showed similar diffraction peaks to those observed in Fig. 3(c,d). But, τ1-(Al,Zr,Si) (S.G. = 194) phase was indexed instead of Al13Cr4Si4 and Al4MnSi phases.'",
                    ),
                ],
            ),
            # Be careful. the liquidus temperatures in table 4 are from thermocalc. But the other 2 are derived from experiments
            # Table 4. Nominal compositions (at.%), nominal liquidus temperatures (°C) obtained by Thermo-Calc,
            # experimental maximum temperatures (°C) of the process and experimental casting temperatures (°C) of the
            # manufactured alloys
        ],
    ),
]
