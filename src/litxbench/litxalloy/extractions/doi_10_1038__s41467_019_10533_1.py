from litxbench.core.models import ConfigTag, CrysStruct, ProcessEvent, ProcessKind, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    dimensionless,
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
    # their definition of ductility is weird. They use number of indentations without cracks (expressed as a percentage)
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Powder, description="Compressed powder pellets of high purity (>= 99.9%) Sigma-Aldrich powders", source="synthesized by arc-melting compressed pellets of elemental, high-purity powders (Sigma-Aldrich, purity ≥99.9%)")},
        synthesis_groups=[
            ProcessEvent(kind=ProcessKind.ArcMelting, description="Also, arc-melted pellets were remelted four times to ensure homogeneity", source="Methods"),  # arc melt is mentioned in the abstract. No atmosphere is specified
            ProcessEvent(kind=ProcessKind.AsCast, source="Dendritic microstructure 'consistent with a cast alloy' (Figure 7). We also guess that they solidified in place after arc melting cause they made pellets."),
            ProcessEvent(kind=ProcessKind.Polishing, source="We know they have a polishing step because: 'Each indent was performed on a polished surface'"),
        ],
        descriptions=[
            AlloyDescriptionGroup(kinds=[AlloyMeasurementKind.vickers_hardness], method=MeasurementMethod.VickersHardnessTest, desc="100g load for 10s, at least 20 indents per alloy in 2x10 array, error reflects 95% certainty via Student's t distribution"),
            # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester], model="LM 248AT", company="LECO")],
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("Co33 W07 Al33 Nb24 Cr03", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=1084, unit=HV, uncertainty=37),
                    Configuration(
                        # How do we know this is a BCC phase? The paper says this:
                        # "Given that there is no obvious partitioning of the Nb and W, it is assumed that they form a solid solution. This behavior would not be unexpected given that both Nb and W are bcc and exhibit complete solid solubility"
                        # This sentence is when the paragraph is talking about the hardest alloy. There is a chance that it's referencing the softest alloy as well. But we know that's not the case because the next paragraph
                        # starts with: "The corresponding images for the softest alloy are shown in Figs 7 and 8." So it's talking about the hardest alloy
                        struct=CrysStruct.BCC,
                        tags={ConfigTag.Dendrite},
                        description="Rich in Nb and W",
                        source="Figure 6 caption. BCC is known because 'both Nb and W are bcc and exhibit complete solid solubility'",
                        measurements=[
                            # I decided to not add this inference since we cannot 100% assume it's 87%. Also it's not explicitly mentioned in the text.
                            # Measurement(
                            #     kind=PhaseMeasurementKind.volume_fraction,
                            #     value=87,  # we can assume that this volume fraction is 87% since the interdendritic phase is 13%
                            #     unit=percent,
                            #     source="It can be seen that the microstructure is dendritic (which is consistent with a cast alloy), with a relatively small volume fraction (13 vol. %) of inter- dendritic phase.",
                            # ),
                        ],
                    ),
                    Configuration(
                        name="interdendritic",
                        tags={ConfigTag.Interdendritic, ConfigTag.Eutectic},
                        source="Figure 6 caption",
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value=13,
                                unit=percent,
                                source="It can be seen that the microstructure is dendritic (which is consistent with a cast alloy), with a relatively small volume fraction (13 vol. %) of inter- dendritic phase.",
                            ),
                        ],
                    ),
                    Configuration(name="interdendritic phase 1", within="interdendritic", description="Rich in Nb", source="Figure 6 caption"),  # they don't tell us the volume fraction of these interdendritic phases :(
                    Configuration(name="interdendritic phase 2", within="interdendritic", description="Rich in Al, Co, and Cr", source="Figure 6 caption"),
                    Measurement(kind=AlloyMeasurementKind.pugh_ductility_ratio, value=0.38, unit=dimensionless),  # commented since this is a calculated property
                ],
            ),
            Material(
                measurements=[
                    CompMeasurement("Ti18 Ni24 Ta12 Cr22 Co24", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=1011, unit=HV, uncertainty=20),
                    Measurement(kind=AlloyMeasurementKind.pugh_ductility_ratio, value=0.47, unit=dimensionless),  # commented since this is a calculated property
                ],
            ),
            Material(measurements=[CompMeasurement("Co6 W9 Al36 Mo38 Ni11", method=MeasurementMethod.Balance), Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=725, unit=HV, uncertainty=47)]),
            Material(measurements=[CompMeasurement("Ni47 Co02 Ta12 Ti9 Nb30", method=MeasurementMethod.Balance), Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=815, unit=HV, uncertainty=43)]),
            Material(measurements=[CompMeasurement("Ti44 Ni02 Nb21 Cr21 Co12", method=MeasurementMethod.Balance), Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=422, unit=HV, uncertainty=13)]),
            Material(measurements=[CompMeasurement("Ti32 Nb9 Ta01 Cr19 Co39", method=MeasurementMethod.Balance), Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=856, unit=HV, uncertainty=29)]),
            Material(
                measurements=[
                    CompMeasurement("Ti39 W04 Nb31 Ta04 Co22", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=277, unit=HV, uncertainty=12),
                    Configuration(
                        tags={
                            ConfigTag.Dendrite,
                            ConfigTag.Coring,
                        },  # How we know coring is likely to exist: "the slight differences in contrast at the edges of the dendrites suggest the possibility of coring. This observation is confirmed by the compositional maps where it can be seen that, for a given dendrite structure, the spatial extent of Nb and Ta enrichment is the greatest while W is confined to the dendrite inner core"
                        description="Rich in Nb, Ta, and W",
                        source="Figure 7 caption: The figure shows a dendritic microstructure similar to that of traditionally cast alloys. the dendrites are enriched in Nb, Ta, and W, whereas the inter-dendritic regions contain a greater proportion of Co and Ti",
                    ),
                    Configuration(
                        tags={ConfigTag.Interdendritic},
                        description="Rich in Co and Ti",  # the dendrites are enriched in Nb, Ta, and W, whereas the inter-dendritic regions contain a greater proportion of Co and Ti
                        measurements=[
                            Measurement(
                                kind=PhaseMeasurementKind.volume_fraction,
                                value=53,
                                unit=percent,
                                source="This microstructure of Ti39 W04 Nb31 Ta04 Co22 is also dendritic, but the volume fraction of inter-dentritic material is much higher here (53 vol. %)",
                            ),
                        ],
                        source="Figure 7 caption: The figure shows a dendritic microstructure similar to that of traditionally cast alloys",
                    ),
                ]
            ),
        ],
    )
]
