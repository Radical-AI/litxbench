from litxbench.core.extraction_utils import ROOM_TEMPERATURE, normalize
from litxbench.core.models import ConfigTag, CrysStruct, RawMaterial, RawMaterialKind
from litxbench.core.units import MegaPascal, percent
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyExperiment as Experiment,
    AlloyMaterial as Material,
    AlloyMeasurementKind,
    AlloyMeasurementMethod as MeasurementMethod,
    CompMeasurement,
    Configuration,
    Measurement,
    ProcessEvent,
    ProcessKind,
)

experiments: list[Experiment] = [
    # Not sure if they gave us the exact elastic modulus. It's in a figure though
    # There are melting temperatures denoated in a table, but they are calculated, not experimental. So they're not included
    # Global info to include later:
    # Cylindrical samples of 3 mm × 6 mm were prepared for room compressive tests and investigated using MTS 809 materials testing machine at room temperature with a strain rate of 2 × 10 4 s 1.
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Ingot, description="with purity better than 99 wt%", source="Section 2. Experimental procedure")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_compression, AlloyMeasurementKind.fracture_strain_compression],
                method=MeasurementMethod.CompressionTest,
                # machines=[Machine(methods=[MeasurementMethod.CompressionTest], model="809", company="MTS")],
                desc="Cylindrical samples of Φ3mm × 6mm were prepared for room compressive tests at room temperature with a strain rate of 2 × 10^{-4} s^{-1}",
            ),
            AlloyDescriptionGroup(kinds=[Configuration], method=MeasurementMethod.SEM, desc="The morphologies of cross sections and fracture surfaces were examined using scanning electron microscope (SEM) with energy dispersive spectrometry (EDS)"),
            # AlloyDescriptionGroup(kinds=[MeasurementMethod.EDS], method=MeasurementMethod.EDS, desc="The morphologies of cross sections and fracture surfaces were examined using scanning electron microscope (SEM) with energy dispersive spectrometry (EDS)"),
            # machines=[Machine(methods=[MeasurementMethod.SEM, MeasurementMethod.EDS], model="Supra 55", company="Zeiss")],
            # AlloyDescriptionGroup(kinds=[MeasurementMethod.XRD], method=MeasurementMethod.XRD, desc="Microstructure investigations of alloys were carried out by X-ray diffraction (XRD) with Cu Kalpha radiation"),
            # machines=[Machine(methods=[MeasurementMethod.XRD], model="APD-10", company="Philips")],
        ],
        synthesis_groups=[
            ProcessEvent(
                kind=ProcessKind.ArcMelting,
                description="Arc melted under a Ti-gettered high-purity argon atmosphere on a water-cooled Cu hearth. The alloys were remelted several times and flipped each times in order to improve homogeneity. This resulted in alloy buttons with about 11 mm thick and 30 mm in diameter.",
                source="Section 2. Experimental procedure",
            ),
            ProcessEvent(
                kind=ProcessKind.AsCast,
                source="They mentioned that they made buttons. And since it's a water-cooled Cu hearth, it's likely they just left it in the crucible to cool and turn into buttons.",
            ),
        ],
        output_materials=[
            Material(
                measurements=[
                    CompMeasurement("NbTiVTa", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1092, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.fracture_strain_compression, val_in_paper="compressive strain"),  # I verified that this is fracture strain because in figure 4a, you can see that these curves end at around the 50% mark.
                        value=">=50",
                        unit=percent,
                        temperature=ROOM_TEMPERATURE,
                        source="The samples of alloys do not break under about 50% compressive strain.",  # since they say "break" I think this is fracture strain
                    ),
                    Configuration(struct=CrysStruct.BCC, tags={ConfigTag.Dendrite, ConfigTag.Equiaxed}),  # Figure 2 shows the microstructures of NbTiVTaAlx alloys. It can be seen that the microstructure of Al0 alloy consists of equiaxial dendritic-like grains
                ]
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTiVTaAl0.25", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1330, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_compression, val_in_paper="compressive strain"), value=">=50", unit=percent, temperature=ROOM_TEMPERATURE, source="The samples of alloys do not break under about 50% compressive strain."),
                    Configuration(struct=CrysStruct.BCC, tags={ConfigTag.Dendrite}),  # Al0.25, Al0.5, and Al1.0 alloys exhibit typical cast dendritic microstructure.
                ]
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTiVTaAl0.5", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=1012, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_compression, val_in_paper="compressive strain"), value=">=50", unit=percent, temperature=ROOM_TEMPERATURE, source="The samples of alloys do not break under about 50% compressive strain."),
                    Configuration(struct=CrysStruct.BCC, tags={ConfigTag.Dendrite}),  # Al0.25, Al0.5, and Al1.0 alloys exhibit typical cast dendritic microstructure.
                ]
            ),
            Material(
                measurements=[
                    CompMeasurement("NbTiVTaAl1", method=MeasurementMethod.Balance),
                    Measurement(kind=AlloyMeasurementKind.yield_strength_compression, value=991, unit=MegaPascal, temperature=ROOM_TEMPERATURE),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_compression, val_in_paper="compressive strain"), value=">=50", unit=percent, temperature=ROOM_TEMPERATURE, source="The samples of alloys do not break under about 50% compressive strain."),
                    Configuration(struct=CrysStruct.BCC, tags={ConfigTag.Dendrite}),  # Al0.25, Al0.5, and Al1.0 alloys exhibit typical cast dendritic microstructure.
                ]
            ),
        ],
    )
]
