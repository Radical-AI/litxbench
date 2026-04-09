from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CompMeasurement, Configuration, CrysStruct, RawMaterial, RawMaterialKind
from litxbench.core.units import (
    HV,
    Celsius,
    Hour,
    MegaPascal,
    Second,
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
    Experiment(
        # The transverse fracture strength of the samples (size: 12 × 2 × 30 mm3) was determined by an Instron 3369 mechanical testing facility (Instron, Norwood, MA, USA) using the three-point method (span length: 25 mm, test speed: 2 mm/min), and tested twice for each treatment.
        # there are more machines. but I didn't list them
        # figure 9 talks about microhardness distribution (for data across from an edge) but I didn't extract it.
        # Section 3.1 gives σ phase volume fractions at specific positions (30 MPa: ~27% at edge, ~14% at 550 μm depth; 40 MPa: ~19% at edge, ~1% at 550 μm).
        # These describe a spatial gradient (FCC→σ transformation varies continuously from center to surface), not bulk phase fractions.
        # Not our current objective to index position-dependent gradient data like this.
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Powder, description="purity 99.9% from Vilory new materials Co. Ltd, Xuzhou, China. These were already gas atomized. These powders are under 200 mesh in size", source="2 Experimental")},
        descriptions=[
            AlloyDescriptionGroup(
                kinds=[AlloyMeasurementKind.vickers_hardness],
                method=MeasurementMethod.VickersHardnessTest,
                # machines=[Machine(methods=[MeasurementMethod.VickersHardnessTester], model="5104", company="Buehler", location="Lake Bluff, IL, USA")],
                desc="under a 200 g load for 15 s, averaged from three measurements.",
                # The indentation profile was obtained by NanoMap 500 DLS 3D surface profiler (Aep Technology, Santa Clara, CA, USA
            ),
            AlloyDescriptionGroup(
                kinds=["transverse_strength", "fracture_strain_bending"],
                method=MeasurementMethod.UniversalTestingMachine,
                # machines=[Machine(methods=[MeasurementMethod.UniversalTestingMachine], model="3369", company="Instron", location="Norwood, MA, USA")],
                desc="using the three-point method. Sample size: 12 × 2 × 30 mm^3, span length: 25 mm, test speed: 2 mm/min. Tested twice for each treatment.",
            ),
            AlloyDescriptionGroup(
                kinds=["phase_transition_temperature", "sintering_onset_temperature"],
                method=MeasurementMethod.DSC,
                # machines=[Machine(methods=[MeasurementMethod.DSC], model="STA 449C", company="Netzsch", location="Selb, Germany")],
                desc="RT to 1300 °C, heating rate 40 K/min, Ar atmosphere.",
            ),
        ],
        synthesis_groups={
            "milling": [
                ProcessEvent(
                    kind=ProcessKind.PlanetaryMilling,
                    duration=Quantity(value=20, unit=Hour),
                    description="The weight ratio between the powder and the stainless-steel balls was 1:10 and ethanol was added as the milling medium. Milling speed was 300 rev/min",
                    source="2. Experimental",
                ),
            ],
            "SPS[Pressure]": [
                ProcessEvent(
                    kind=ProcessKind.SparkPlasmaSintering,
                    temperature=Quantity(value=1150, unit=Celsius),
                    duration=Quantity(value=480, unit=Second),
                    description="The milled powders were then added into a graphite die 40 mm in diameter and consolidated using an HPD 25/3 SPS equipment under reduced pressure (10^{-3} Pa). The pressure was [Pressure] MPa. After a holding time of 480s, the sintered billets were cooled down to room temperature in the furnace.",
                    source="2. Experimental",
                ),
            ],
            "grind_and_polish": [
                ProcessEvent(
                    kind=ProcessKind.Grinding,
                    description="Samples were prepared by mechanical grinding using 1200 to 4000 grit SiC papers",
                    source="2. Experimental",
                ),
                ProcessEvent(
                    kind=ProcessKind.Polishing,
                    description="final size: ϕ 40 × 2mm^3",
                    source="2. Experimental",
                ),
            ],
        },
        output_materials=[
            Material(
                process="elements->milling->SPS[Pressure=30]->grind_and_polish",
                measurements=[
                    CompMeasurement("Fe24.1Co24.1Cr24.1Ni24.1Mo3.6"),
                    Configuration(
                        name="sigma phase",
                        description="tetragonal structure",
                        # 110,200 planes "However, the peaks corresponding to the {110} and {200} planes could be identified, indicating the formation of the σ phase structure.""
                        measurements=[CompMeasurement({"Cr": 50.8, "Fe": 19.1, "Co": 17.3, "Ni": 10.1, "Mo": 2.6}, method=MeasurementMethod.EDS)],
                        source="Table 1",
                    ),
                    # This composition sums to 97.9. which means they're not reporting impurities I think
                    Configuration(struct=CrysStruct.FCC, measurements=[CompMeasurement({"Cr": 20.0, "Fe": 23.9, "Co": 24.8, "Ni": 22.5, "Mo": 6.7}, method=MeasurementMethod.EDS, validate_composition=False)], source="Table 1"),  # 111 XRD peak
                    # this is transverse (3‑point bending) strength. Use just a string since bending is very misleading. it also depends on the shape of the bar. If your index cares about bars, consider making a new measurementClass for this
                    Measurement(kind=normalize(val="transverse_strength", val_in_paper="bending_strength"), value=779, unit=MegaPascal),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value="~210", unit=HV, description="at the center of the sample"),
                ],
            ),
            Material(
                process="elements->milling->SPS[Pressure=35]->grind_and_polish",
                measurements=[
                    CompMeasurement("Fe24.1Co24.1Cr24.1Ni24.1Mo3.6"),
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value="~210", unit=HV, description="at the center of the sample"),
                ],
            ),
            Material(
                process="elements->milling->SPS[Pressure=40]->grind_and_polish",
                measurements=[
                    CompMeasurement("Fe24.1Co24.1Cr24.1Ni24.1Mo3.6"),
                    Measurement(kind="transverse_strength", value=1004, unit=MegaPascal, source="the sample has the highest transverse strength of 1004 MPa and the highest fracture strain of 2.3%."),
                    Measurement(
                        kind="fracture_strain_bending", value=2.3, unit=percent, source="the sample has the highest transverse strength of 1004 MPa and the highest fracture strain of 2.3%."
                    ),  # this is not fracture_strain tension/compression since it's kinda weird. They really should define a deflection angle or explain this better
                    Measurement(kind=AlloyMeasurementKind.vickers_hardness, value="~210", unit=HV, description="at the center of the sample"),
                ],
            ),
            # We made a new dummy sample without SPS to record the DSC results. This is because when the authors mentioned these values, they didn't mention the SPS pressure - since they thought it was more of
            # a property of the chemical system then the SPS pressure (even though they probably did this analysis on an SPS sample).
            # What the DSC tells us: normally this alloy's FCC phase won't transform into the σ phase until you heat it to 1260°C.
            # But during SPS, the applied pressure effectively lowers that barrier — the same transformation happens at just 1150°C.
            # So pressure makes the phase change easier, letting it kick in at a lower temperature.
            Material(
                name="dsc_characterization",
                process="elements->milling",
                measurements=[
                    CompMeasurement("Fe24.1Co24.1Cr24.1Ni24.1Mo3.6"),
                    Measurement(kind="phase_transition_temperature", value=1260, unit=Celsius, description="FCC to σ phase transition temperature, measured by DSC", source="3.2 Phase Identification"),
                    Measurement(kind="sintering_onset_temperature", value=960, unit=Celsius, description="First exothermic peak from DSC, representing the beginning of the sintering reaction and formation of the FCC phase", source="3.2 Phase Identification"),
                ],
            ),
        ],
    )
]
