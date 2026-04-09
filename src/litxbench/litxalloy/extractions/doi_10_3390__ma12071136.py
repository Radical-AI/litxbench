from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CompMeasurement, ConfigTag, Configuration, CoreMeasurementValue, CrysStruct, GlobalLatticeParam, MeasurementStatistic, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    MegaPascal,
    Micrometer,
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
    PhaseMeasurementKind,
    ProcessEvent,
    ProcessKind,
)

experiments: list[Experiment] = [
    # there are a lot of mechanical properties in figure 7 that I didn't extract.
    Experiment(
        raw_materials={
            "elements": RawMaterial(kind=RawMaterialKind.Unspecified, description="purity > 99.9%", source="2.3 Experiment Process"),
            "master_alloys": RawMaterial(kind=RawMaterialKind.Unspecified, description="Al-Si master alloys with 50 wt.% Si", source="2.3 Experiment Process"),
        },
        synthesis_groups=[
            ProcessEvent(kind=ProcessKind.InductionMelting, description="induction melting in an argon atmosphere and a graphite crucible.", source="2.3 Experiment Process"),
            ProcessEvent(kind=ProcessKind.CastingUnspecified, description="The melted alloys were then cast into a copper mold to form cylindrical rods with a diameter of 10 mm", source="2.3 Experiment Process"),
            ProcessEvent(kind=ProcessKind.Cut, description="The rods were then cut with a diamond saw", source="2.3 Experiment Process"),
            ProcessEvent(kind=ProcessKind.Grinding, source="2.3 Experiment Process"),
            ProcessEvent(kind=ProcessKind.Polishing, source="2.3 Experiment Process"),
            ProcessEvent(kind=ProcessKind.Etching, description="2.5% nitric acid–methanol", source="2.3 Experiment Process"),
        ],
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.fracture_strength_compression],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest])],
                desc="We know it's compression since: 'The compression stress–strain curves of the ULW-CCAs are plotted in Figure 3a'. Strain rate was 1*10^{-4}*s^{-1}. Compression samples were shaped into Φ6 mm × 12 mm.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.density],
                method=MeasurementMethod.ArchimedesMethod,  # machines=[Machine(methods=[MeasurementMethod.ArchimedesMethod])],
                desc="measured by Archimedes' principle in absolute alcohol (purity of 99.9%). No machine was specified.",
            ),
        ],
        # The structures were identified in a Gigaku D\max-2550 X-ray diffractometer (XRD, Rigaku Company, Tokyo, Japan) with a Cu-Kα radiation.
        # The microstructures of the ULW-CCAs were investigated by an Apollo 300 scanning electron microscopy (SEM, CamScan Company, Waterbeach, UK) equipped with the backscattering electron (BSE) detector, and a JEOL 2100 type transmission electron microscope (TEM, JEOL Company, Tokyo, Japan).
        # The compositions of the constituents were analyzed by energy dispersion spectrum (EDS) in the Apollo 300 SEM
        #
        # I think this next sentence is talking about all the samples in general, not just one of them
        # "the BCC solid solution is a Li-rich phase with a low modulus of 10–25 GPa according to the nanoindentation results"
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement(
                        "Al19.9Li30Mg35Si10Ca5Y0.1"
                    ),  # maybe EDS? Note: their EDS cannot detect Li: "Note that Li could not be detected by EDS." So maybe they just did a subtraction and assumed that all remaining elements are Li? (not sure if the machine allows this flexibility if they used EDS to measure composition)
                    Measurement(kind=AlloyMeasurementKind.fracture_strength_compression, value=710, unit=MegaPascal, uncertainty=26),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=556, unit=MegaPascal, uncertainty=20),
                    # NOTE: The body text says region B=Mg2Si and D=CaMgSi, but Table 3 says B=CaMgSi and D=Mg2Si.
                    # "Region B and region C are identified as the Mg2Si phase and the unknown phase, respectively. Furthermore, D is deduced to be the CaMgSi phase comprised of 30.5 at.% Mg, 39.4 at.% Si, and 30.1 at.% Ca. ""
                    # This is a typo, the body text mixed regions B and D up (composition matches the wrong region)
                    # Table 3 is most likely more correct.
                    Configuration(
                        name="Region A: LiMgAl2 phase (al enriched)",
                        measurements=[CompMeasurement({"Al": 86.6, "Mg": 13.4}, method=MeasurementMethod.EDS), Measurement(kind=PhaseMeasurementKind.volume_fraction, value="~31", unit=percent)],
                        source="Table 3. The phase in this region is identified as the LiMgAl2 phase and its volume fraction is approximately 31%.",
                    ),
                    Configuration(name="Region D: Mg2Si", measurements=[CompMeasurement({"Mg": 61.1, "Si": 38.9}, method=MeasurementMethod.EDS)], source="Table 3"),
                    Configuration(name="Region C: unknown phase", measurements=[CompMeasurement({"Al": 51.7, "Mg": 28.9, "Si": 11.9, "Ca": 7.5}, method=MeasurementMethod.EDS)], source="Table 3"),
                    Configuration(name="Region B: CaMgSi phase", measurements=[CompMeasurement({"Mg": 30.5, "Si": 39.4, "Ca": 30.1}, method=MeasurementMethod.EDS)], source="Table 3"),
                    # Not sure if it's compression??? I think it is because the next sentence is "By adjusting the composition of the CCAs, the Al15Li35Mg48Ca1Si1 ULW-CCA with the good compressive plasticity"
                    Measurement(
                        kind=AlloyMeasurementKind.ultimate_strain_compression, value="~2.6", unit=percent
                    ),  # to be fair I don't know if they mean ultimate strain (peak strain) or fracture strain. I think it's ultimate strain since they keep saying plastic, but I can't for sure verify it's not fracture strain (from looking at the graph and the numbers they give me)
                    Measurement(kind=AlloyMeasurementKind.density, value=1.70, unit=gram_per_cm3, uncertainty=0.05, source="Table 2"),
                    GlobalLatticeParam(struct=CrysStruct.HCP, description="from XRD", source="The XRD pattern indicates that the near equiatomic Al19.9Li30Mg35Si10Ca5Y0.1 ULW-CCA contains HCP solid solution and intermetallic (IM) phases (Figure 2a)"),
                    # other global intermetallic phases are present, but they are ambiguous
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al15Li35Mg35Ca10Si5"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strength_compression, value=516, unit=MegaPascal, uncertainty=33),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=418, unit=MegaPascal, uncertainty=29),
                    Configuration(
                        name="Region A: beta-Mg (BCC) phase",
                        struct=CrysStruct.BCC,
                        tags={ConfigTag.Matrix},
                        description="dark grey matrix",
                        measurements=[
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.volume_fraction,
                                unit=percent,
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=45),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=57),
                                ],
                            ),
                            CompMeasurement({"Al": 22.9, "Mg": 77.1}, method=MeasurementMethod.EDS, source="Table 3"),
                        ],
                    ),
                    Configuration(name="Region B: Al2Ca phase", description="region B in figure 4b", measurements=[CompMeasurement({"Al": 57.6, "Mg": 11.2, "Ca": 31.1}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Configuration(name="Region C: HCP phase", struct=CrysStruct.HCP, description="has a bulk shape", measurements=[CompMeasurement({"Al": 45.4, "Mg": 41.3, "Si": 13.3}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Configuration(name="Region D: CaMgSi phase", description="reticulate-like phase", measurements=[CompMeasurement({"Mg": 38.1, "Si": 28.3, "Ca": 33.6}, method=MeasurementMethod.EDS, source="Table 3")]),
                    Measurement(kind=AlloyMeasurementKind.density, value=1.57, unit=gram_per_cm3, uncertainty=0.05, source="Table 2"),
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al15Li35Mg48Ca1Si1"),
                    Measurement(kind=AlloyMeasurementKind.fracture_strength_compression, value=596, unit=MegaPascal, uncertainty=27),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=360, unit=MegaPascal, uncertainty=16),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_strain_compression, val_in_paper="compressive_ductility"), value=9.5, unit=percent, uncertainty=0.8),
                    Configuration(
                        name="Region A: Matrix",
                        tags={ConfigTag.Matrix},
                        # This is BCC structure since Region A is the matrix, and the below text says it's BCC structure:
                        # "In addition, some submicron-sized particles with the HCP structure (Figure 5b,c) are embedded in the BCC structure matrix and are surrounded by the lath-like Al-Li and Li2MgAl phases (Figure 5c)"
                        struct=CrysStruct.BCC,
                        measurements=[CompMeasurement({"Al": 18, "Mg": 82}, method=MeasurementMethod.EDS, source="Table 3")],
                    ),
                    Configuration(
                        name="Region B: AlLi Phase (lath-like light)",
                        tags={ConfigTag.Lath},
                        measurements=[
                            CompMeasurement({"Al": 91.2, "Mg": 8.8}, method=MeasurementMethod.EDS, source="Table 3"),
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.phase_size,
                                unit=Micrometer,
                                source="The size of the AlLi phase is 5–20 µm",
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=20),
                                ],
                            ),
                        ],
                    ),
                    Configuration(
                        name="Region C: submicron-size particles",
                        tags={ConfigTag.Precipitate},
                        within="Region A: Matrix",
                        # This is HCP structure C are submicron-sized particles, and the below text says it's HCPstructure:
                        # "In addition, some submicron-sized particles with the HCP structure (Figure 5b,c) are embedded in the BCC structure matrix and are surrounded by the lath-like Al-Li and Li2MgAl phases (Figure 5c)"
                        struct=CrysStruct.HCP,
                        description="uncertain phase composition",
                        measurements=[CompMeasurement({"Al": 12.4, "Mg": 87.6}, method=MeasurementMethod.EDS, source="Table 3")],
                    ),
                    # I feel like the authors made a mistake with the composition here. it sums to 101.0%
                    Configuration(name="Region D: Li2MgAl Phase (lath-like dark)", tags={ConfigTag.Lath}, description="lath-like dark", measurements=[CompMeasurement({"Al": 55.3, "Mg": 45.7}, method=MeasurementMethod.EDS, validate_composition=False, source="Table 3")]),
                    Measurement(kind=AlloyMeasurementKind.density, value=1.52, unit=gram_per_cm3, uncertainty=0.05, source="Table 2"),
                ],
            ),
            Material(
                # NOTE: The paper has a typo in the XRD section where it says "Al15Li35Mg48Ca0.5Si1.5"
                # instead of "Al15Li38Mg45Ca0.5Si1.5" (the Li/Mg subscripts are swapped with the Ca1Si1 alloy).
                # The correct composition is from Table 2.
                # Full quote: "The phase structures of the Al15Li38Mg45Ca1Si1, Al15Li35Mg48Ca0.5Si1.5,
                # and Al15Li39Mg45Ca0.5Si0.5 ULW-CCAs are almost the same (Figure 2c–e). The dominant phase of
                # these three alloys is a BCC solid solution. Additionally, the AlLi and Li2MgAl phases can also
                # be easily identified in these three ULW-CCAs."
                measurements=[
                    CompMeasurement("Al15Li38Mg45Ca0.5Si1.5"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=342, unit=MegaPascal, uncertainty=19),
                    Measurement(kind=AlloyMeasurementKind.density, value=1.50, unit=gram_per_cm3, uncertainty=0.05, source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_strain_compression, val_in_paper="compressive_ductility"), value=">45", unit=percent, source="and a high compressive ductility of >45%"),
                    Configuration(
                        name="Region A: BCC solid solution (beta-Mg)",  # The paper doesn't say that this is a matrix. It's understandable - looking at the figure, it doens't look like the background phase
                        struct=CrysStruct.BCC,
                        tags={ConfigTag.Dendrite},
                        description="dark region - region A in figure 4c. Displays a dendritic structure divided by net-like interdendritic structure.",
                        measurements=[
                            CompMeasurement({"Al": 12.2, "Mg": 87.8}, method=MeasurementMethod.EDS, source="Table 3"),
                        ],
                        source="The dark region (region A in Figure 4c) corresponds to the β-Mg BCC solid solution phase. Both the Al15Li38Mg45Ca0.5Si1.5 and Al15Li39Mg45Ca0.5Si0.5 ULW-CCAs display a dendritic structure, which is divided by the net-like interdendritic structure.",
                    ),
                    Configuration(
                        name="Region B: AlLi phase",
                        tags={ConfigTag.Lath},
                        description="lath-like morphology - region B in figure 4c",
                        measurements=[
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.phase_size,
                                unit=Micrometer,
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=1),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=15),
                                ],
                            ),
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.volume_fraction,
                                unit=percent,
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=28),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=32),
                                ],
                            ),
                            CompMeasurement({"Al": 94.3, "Mg": 5.7}, method=MeasurementMethod.EDS, source="Table 3"),
                        ],
                        source="The lath-like morphology (region B in Figure 4c) is the AlLi phase with an average size of 1–15 µm, and the volume fraction of 28–32%.",
                    ),
                    Configuration(
                        name="Region C: HCP solid solution (alpha-Mg)",
                        struct=CrysStruct.HCP,
                        measurements=[
                            CompMeasurement({"Al": 11.6, "Mg": 88.4}, method=MeasurementMethod.EDS, source="Table 3"),
                        ],
                        source="Region C in Figure 4c could be the HCP solid solution according to the EDS results (Table 3)",
                    ),
                    # Measurement(kind=AlloyMeasurementKind.plasticity, value=45, unit=percent), # I don't think they give an actual property for plasticity. they just threw this number
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Al15Li39Mg45Ca0.5Si0.5"),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=300, unit=MegaPascal, uncertainty=33),
                    Measurement(kind=AlloyMeasurementKind.density, value=1.46, unit=gram_per_cm3, uncertainty=0.05, source="Table 2"),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.ultimate_strain_compression, val_in_paper="compressive_ductility"), value=">60", unit=percent, source="and a good compressive ductility of >60%"),
                    # note: they do say: The phase structures of the Al15Li38Mg45Ca1Si1, Al15Li35Mg48Ca0.5Si1.5, and Al15Li39Mg45Ca0.5Si0.5 ULW-CCAs are almost the same (Figure 2c–e). The dominant phase of these three alloys is a BCC solid solution.
                    # but I didn't mention it. I think it's just simpler if we just use the table 3 data.
                    # Maybe we need a new Phase type: one to specify the kinds of phase? bc rn, they don't match up the phase they see in EDS with XRD.
                    Configuration(
                        name="Region A: Matrix",
                        tags={ConfigTag.Matrix, ConfigTag.Dendrite},
                        description="It consists of a BCC Solid Solution AND Li2MgAl phase. Displays a dendritic structure divided by net-like interdendritic structure.",
                        source="The matrix, i.e. Region A in figure 4d, consists of the BCC solid solution and the Li2MgAl phase. Both the Al15Li38Mg45Ca0.5Si1.5 and Al15Li39Mg45Ca0.5Si0.5 ULW-CCAs display a dendritic structure, which is divided by the net-like interdendritic structure.",
                        measurements=[CompMeasurement({"Al": 15.7, "Mg": 84.3}, method=MeasurementMethod.EDS, source="Table 3")],
                    ),
                    Configuration(
                        name="Region A: Li2MgAl phase",
                        within="Region A: Matrix",
                        source="The matrix, i.e. Region A in figure 4d, consists of the BCC solid solution and the Li2MgAl phase.",
                        measurements=[CompMeasurement({"Al": 15.7, "Mg": 84.3}, method=MeasurementMethod.EDS, source="Table 3")],
                    ),
                    Configuration(
                        name="Region A: BCC Solid Solution",
                        struct=CrysStruct.BCC,
                        within="Region A: Matrix",
                        source="The matrix, i.e. Region A in figure 4d, consists of the BCC solid solution and the Li2MgAl phase.",
                        measurements=[CompMeasurement({"Al": 15.7, "Mg": 84.3}, method=MeasurementMethod.EDS, source="Table 3")],
                    ),
                    Configuration(
                        name="Region B: AlLi phase",
                        tags={ConfigTag.Lath},
                        description="lath-like phase (region B in Figure 4d)",
                        measurements=[
                            *Measurement.group_measurements(
                                kind=PhaseMeasurementKind.volume_fraction,
                                unit=percent,
                                values=[
                                    CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=25),
                                    CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=28),
                                ],
                            ),
                            CompMeasurement({"Al": 93.2, "Mg": 6.8}, method=MeasurementMethod.EDS, source="Table 3"),
                        ],
                    ),
                    # Measurement(kind=AlloyMeasurementKind.plasticity, value=60, unit=percent), # I don't think they give an actual property for plasticity. they just threw this number
                ],
            ),
        ],
    ),
]
