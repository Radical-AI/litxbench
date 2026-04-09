from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CoreMeasurementValue, CrysStruct, MeasurementStatistic, ProcessEvent, ProcessKind, Quantity, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    Celsius,
    GigaPascal,
    Hour,
    Kelvin,
    MegaJoulesPerMeterSquared,
    MegaPascal,
    MegaPascalSquareRootMeter,
    Micrometer,
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
    # They prepared 12 samples:
    # Groups of four samples were tested at three different temperatures (N ¼ 12); at room temperature (293 K), in a bath of dry ice and ethanol (198 K), and in a bath of liquid nitrogen (77 K)
    # TODO: maybe we should specify the final form factor of the samples? this one are metal sheets
    # TODO: should we mention polishing in synthesis events? Polishing will affect XRF measurements (e.g. here they use silica polishing).
    # I don't think we should because it doesn't affect the main material's properties and if there is sillica impurities, we can not that it came from polishing (and the authors tend to omit the contamination)
    # "To analyse the microstructure of the material after processing, two pieces were cut from the recrystallized sheets perpendicular to the rolling direction, embedded in conductive resin and metallographically polished in stages to a final surface finish of 0.04 mm using colloidal silica.""
    # If we want to put the polishing info we add it to the descriptions. so we don't need to repeat it for each sample.
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Ingot, description="Cr, Co, Ni ingots with purity >99.9%")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.yield_strength_tension, AlloyMeasurementKind.ultimate_tensile_strength, AlloyMeasurementKind.fracture_strain_tension, AlloyMeasurementKind.strain_hardening_exponent_tension],
                method=MeasurementMethod.TensileTest,
                # machines=[Machine(methods=[MeasurementMethod.TensileTest], model="4204", company="Instron")],
                desc="Tensile tests were performed at an engineering strain rate of 10^{-3} s^{-1}. Rectangular dog-bone-shaped tensile specimens with a gauge length of 12.7 mm, final thickness ~1.5 mm and gauge width ~3.0 mm.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.fracture_toughness, AlloyMeasurementKind.work_of_fracture],
                method=MeasurementMethod.FractureToughnessTest,
                # machines=[Machine(methods=[MeasurementMethod.FractureToughnessTest], model="810", company="MTS"), Machine(methods=[MeasurementMethod.FractureToughnessTest], model="8800", company="Instron")],
                desc="Nonlinear-elastic fracture mechanics (J-integral) per ASTM E1820. Compact-tension C(T) specimens (W=18 mm, B=9 mm, side-grooved to B_N ~7 mm). Fatigue pre-cracked and tested at displacement rate of 2 mm/min. Epsilon clip gauges used for crack monitoring.",
            ),
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.youngs_modulus, AlloyMeasurementKind.poissons_ratio_tension],
                method=MeasurementMethod.ResonanceUltrasoundSpectroscopy,
                # machines=[Machine(methods=[MeasurementMethod.ResonanceUltrasoundSpectroscopy])],
                desc="Values of Young's modulus and Poisson's ratio determined at each temperature using resonance ultrasound spectroscopy methods.",
            ),
            AlloyDescriptionGroup(
                method=MeasurementMethod.EBSD,
                # machines=[Machine(methods=[MeasurementMethod.EBSD], model="TEAM EDAX", company="Ametek EDAX")],
            ),
            AlloyDescriptionGroup(
                method=MeasurementMethod.EDS,
                # machines=[Machine(methods=[MeasurementMethod.EDS], model="7426 EDS Ray Detector", company="Oxford Instruments")],
            ),
            # Nikon travelling microscope: measured post‑fracture gauge‑length elongation (for tensile ductility).
            # All the samples were fatigue pre-cracked and tested using an electroservo-hydraulic MTS 810 load frame (MTS Corporation, Eden Prairie, MN, USA) controlled by an Instron 8800 digital controller
        ],
        synthesis_groups=[
            ProcessEvent(kind=ProcessKind.ArcMelting, description="Arc melted under an argon atmosphere", source="Methods"),
            ProcessEvent(kind=ProcessKind.DropCasting, description="drop-cast into rectangular cross-section copper moulds measuring 25.4 × 19.1 × 127 mm", source="Methods"),
            ProcessEvent(kind=ProcessKind.Homogenization, duration=Quantity(value=24, unit=Hour), temperature=Quantity(value=1200, unit=Celsius), description="in vacuum", source="Methods. The ingots were homogenized at 1,200°C for 24 h in vacuum"),
            ProcessEvent(kind=ProcessKind.Cut, description="They were cut in half length-wise", source="Figure 1a. Description"),
            # It's very interesting they do cold forging first then cross rolling. I guess they ARE making sheets.
            ProcessEvent(kind=ProcessKind.ColdForging, source="cold-forged and cross-rolled at room temperature along the side that is 25.4 mm to a final thickness of ~10mm"),
            ProcessEvent(kind=ProcessKind.CrossRolling, source="cold-forged and cross-rolled at room temperature along the side that is 25.4 mm to a final thickness of ~10mm"),
            ProcessEvent(kind=ProcessKind.Annealing, duration=Quantity(value=1, unit=Hour), temperature=Quantity(value=800, unit=Celsius), description="annealed in air", source="Methods -> Materials processing and microstructural characterization"),
        ],
        output_materials=[
            Material(
                # we need to figure out which phases this grain sizes is for
                # grain_sizes=Range(lower=Measurement(kind=PhaseMeasurementKind.grain_size, value=5, unit=Micrometer), upper=Measurement(kind=PhaseMeasurementKind.grain_size, value=50, unit=Micrometer)),
                # for some of these measurements, they have uncertainties in figure 2a, but we don't care for now since it's in an image
                measurements=[
                    CompMeasurement("CrCoNi", method=MeasurementMethod.Balance),
                    # CompositionMeasurement("Cr34.27Co32.59Ni33.14", method=MeasurementMethod.EDS, source="image e figure 1"), # TODO: enable when we want to involve images.
                    Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=657, unit=MegaPascal, temperature=Quantity(value=77, unit=Kelvin), source="with decreasing temperature to values of sy ¼ 657 MPa and sUTS ¼ 1,311 MPa at 77 K."),
                    Measurement(kind=AlloyMeasurementKind.ultimate_tensile_strength, value=1311, unit=MegaPascal, temperature=Quantity(value=77, unit=Kelvin), source="with decreasing temperature to values of sy ¼ 657 MPa and sUTS ¼ 1,311 MPa at 77 K."),
                    Measurement(kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain to failure"), value="~70", unit=percent, temperature=Quantity(value=293, unit=Kelvin), source="abstract"),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=229, unit=GigaPascal, temperature=Quantity(value=293, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=235, unit=GigaPascal, temperature=Quantity(value=198, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.youngs_modulus, value=241, unit=GigaPascal, temperature=Quantity(value=77, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.poissons_ratio_tension, value=0.31, unit=dimensionless, temperature=Quantity(value=293, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.poissons_ratio_tension, value=0.30, unit=dimensionless, temperature=Quantity(value=198, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.poissons_ratio_tension, value=0.30, unit=dimensionless, temperature=Quantity(value=77, unit=Kelvin)),
                    Measurement(kind=AlloyMeasurementKind.fracture_toughness, value=208, unit=MegaPascalSquareRootMeter, temperature=Quantity(value=293, unit=Kelvin), source="Figure 2b caption"),
                    Measurement(kind=AlloyMeasurementKind.fracture_toughness, value=265, unit=MegaPascalSquareRootMeter, temperature=Quantity(value=198, unit=Kelvin), source="Figure 2b caption"),
                    Measurement(kind=AlloyMeasurementKind.fracture_toughness, value=273, unit=MegaPascalSquareRootMeter, temperature=Quantity(value=77, unit=Kelvin), source="Figure 2b caption"),  # the abstract says 275 (but 273 is more accurate and is mentioned in the text - and I cheated - but in the images)
                    *Measurement.group_measurements(
                        kind=PhaseMeasurementKind.grain_size,
                        unit=Micrometer,
                        values=[
                            CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
                            CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
                        ],
                    ),
                    # this measurement is commented out because the paper already mentioned "failure strain" in the abstract which is a duplicate of this.
                    # Be careful, it's 65% here. (since 65% + 25% = 90%)
                    # Measurement(
                    #     kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain_to_failure"),
                    #     value="~65",
                    #     unit=percent,
                    #     temperature=Quantity(value=293, unit=Kelvin),
                    #     source="The tensile ductility (strain to failure, Epsilon_f) similarly increased by ~25% to ~0.9. We know this is the temperature because they mentioned it earlier in the paragraph",
                    # ),
                    Measurement(
                        kind=normalize(val=AlloyMeasurementKind.fracture_strain_tension, val_in_paper="strain to failure"),
                        value="~90",
                        unit=percent,
                        temperature=Quantity(value=77, unit=Kelvin),
                        source="The tensile ductility (strain to failure, Epsilon_f) similarly increased by ~25% to ~0.9. We know this is the temperature because they mentioned it earlier in the paragraph",
                    ),
                    Configuration(struct=CrysStruct.FCC, source="Abstract"),
                    # Note: they don't give exact values for fracture energy tension. The most they mention is "leading to an increase in fracture energy of more than 80%".
                    # So I won't include it. fortunately, the work of fracture basically gives us the same information.
                    Measurement(kind=AlloyMeasurementKind.work_of_fracture, value=3.5, unit=MegaJoulesPerMeterSquared, temperature=Quantity(value=293, unit=Kelvin), source="Figure 2a caption: In the same temperature range, the work of fracture increases from 3.5 MJm^{-2} to 6.4 MJm^{-2}."),
                    Measurement(kind=AlloyMeasurementKind.work_of_fracture, value=6.4, unit=MegaJoulesPerMeterSquared, temperature=Quantity(value=77, unit=Kelvin), source="Figure 2a caption: In the same temperature range, the work of fracture increases from 3.5 MJm^{-2} to 6.4 MJm^{-2}."),
                    # leading to an increase in fracture energy of more than 80%. I don't think we note "fracture energy"
                    Measurement(kind=AlloyMeasurementKind.strain_hardening_exponent_tension, value=0.4, unit=dimensionless, temperature=Quantity(value=77, unit=Kelvin), source="to achieve extremely high strain-hardening exponents on the order of 0.4"),
                ],
            ),
            # we should include failure strain? epsilon f?
            # how about work of fracture?
            #
            # they also prepared 9 separate samples for Fracture Toughness:
            # Nine (N¼ 9) compact-tension C(T) specimens, of nominal width W¼ 18 mm and thickness B¼ 9 mm, were prepared in strict accordance with ASTM standard E1820 (ref. 26) using electrical discharge machining (EDM)
            #
            # other samples:
            # - Resonance Ultrasound Spectroscopy (RUS) Samples for Young's modulus and Poisson's ratio.
            # - Microstructural Characterization Samples (at least 2)
            # - Post-Test "Sliced" Specimens: To investigate the mechanisms behind the alloy's toughness, the researchers took fractured specimens from the 77 K, 198 K, and 293 K tests and sliced them in half along the mid-plane (half-thickness). This allowed them to examine the crack-tip regions in the center of the sample where true "plane strain" conditions occur.
            #   - this last one doesn't really count
        ],
    )
]
