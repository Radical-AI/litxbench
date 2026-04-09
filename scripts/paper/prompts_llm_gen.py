# %% [markdown]
# Auto-generated rendered prompts from source code.
# Regenerate with: uv run paper/generate_prompts.py
#
# Each section below shows the exact text sent to the LLM at inference time.
# Python code blocks in prompts use 2-space indentation.

# %% J.0.3 Extraction Scope Prompt
SCOPE_RULES = """
We are only interested in materials the authors physically made in their lab.
Extract ALL properties reported for those materials — mechanical, thermal, physical, microstructural, etc.
Include properties derived from measurements (e.g. strain hardening exponent from a stress-strain curve, fracture toughness from a fracture test, Pugh ductility ratio from measured elastic constants).
Exclude properties that are purely computed from composition or thermodynamic databases (e.g. CALPHAD/ThermoCalc predictions, DFT-computed values, rule-of-mixtures estimates with no experimental validation).
"""

# %% J.0.1 Example Extraction Prompt
# Configuration: include_source=True, include_descriptions=True, linear=False (with material names)
EXAMPLE_EXPERIMENT_SHAPE = """
```python
[
  Experiment(
    raw_materials={
      "elements": RawMaterial(
        kind=RawMaterialKind.Ingot,
        description="...",
        source="...",
      )
    },
    synthesis_groups={
      "creation": [
        ProcessEvent(kind=ProcessKind.ArcMelting, description="Remelted 5 times to promote homogeneity, flipped pellet between each remelt", source="..."),
        ProcessEvent(kind=ProcessKind.AsCast, description="...", source="..."),
        ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1200, unit=Celsius), duration=Quantity(value=24, unit=ureg.hour), source="..."),
        ProcessEvent(kind=ProcessKind.WaterQuenching, source="..."),
      ],
      "annealing[Temp]": [
        ProcessEvent(
          kind=ProcessKind.Annealing,
          temperature=Quantity(value="[Temp]", unit=Celsius),
          source="...",
        ),
      ],
    },
    descriptions=[
      AlloyDescriptionGroup(
        kinds=[AlloyMeasurementKind.vickers_hardness],
        method=MeasurementMethod.VickersHardnessTest,
        desc="The microhardness (HV) of the alloys was measured with a Vickers hardness tester under a load of 500 gf",
      ),
      AlloyDescriptionGroup(
        kinds=[ProcessKind.Grinding],
        desc="performed on a grinding wheel",
      ),
    ],
    output_materials=[
      Material(
        process="elements->creation",
        name="materialA",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=321.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
          # When a value is explicitly a mean/average:
          Measurement(
            kind=AlloyMeasurementKind.yield_strength_tension,
            value=450.0,
            unit=MegaPascal,
            measurement_statistic=MeasurementStatistic.mean,
            source="...",
          ),
          # When a value is reported as a range (e.g. "5–50 μm"):
          *Measurement.group_measurements(
            kind=PhaseMeasurementKind.grain_size,
            unit=Micrometer,
            values=[
              CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
              CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
            ],
          ),
          # XRD-determined lattice parameter and crystal structure:
          GlobalLatticeParam(
            lattice=LatticeMeasurement(Lattice.cubic(3.208)),
            struct=CrysStruct.BCC,
            source="...",
          ),
          # Microstructural feature (e.g. dendrite with EDS composition):
          Configuration(
            name="dendrite",
            tags={ConfigTag.Dendrite},
            measurements=[
              CompMeasurement(
                {"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9},
                method=MeasurementMethod.EDS,
                source="...",
              ),
            ],
          ),
          # Nested configuration (precipitate within a phase):
          Configuration(
            name="FCC matrix",
            struct=CrysStruct.FCC,
            tags={ConfigTag.Matrix},
            measurements=[
              Measurement(
                kind=PhaseMeasurementKind.grain_size,
                value="~0.71",
                unit=Micrometer,
              ),
            ],
          ),
          Configuration(
            name="B2 precipitates",
            struct=CrysStruct.B2,
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
            within="FCC matrix",
            measurements=[
              *Measurement.group_measurements(
                kind=PhaseMeasurementKind.grain_size,
                unit=Nanometer,
                values=[
                  CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=50),
                  CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=180),
                ],
              ),
            ],
          ),
        ],
      ),
      Material(
        process="materialA->annealing[Temp=10]",
        name="materialB",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=350.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
        ],
      ),
    ],
  ),
]
```
"""

# %% J.0.2 Extraction Template Instruction Prompt
# Configuration: include_source=True, include_descriptions=True, linear=False
FIELD_INSTRUCTIONS = """
How to write each Experiment and fields to populate:
1) `raw_materials` (required): map each initial input name (for example `"elements"` or `"powders"`) to `RawMaterial`.
 - Populate `kind` with `RawMaterialKind` (usually `Ingot`, `Powder`, or `Unspecified`).
 - Populate `description` and `source` whenever the paper states purity, supplier, or precursor details.
2) `synthesis_groups` (required): a dict of named synthesis stages to lists of `ProcessEvent`.
 - Use reusable stages and process variables when appropriate (for example `"annealing[Temp]"`).
 - Each `ProcessEvent` should include `kind` (a `ProcessKind` enum member), and include `temperature` (as `Quantity`, e.g. `Quantity(value=1200, unit=Celsius)`), `duration` (as `Quantity`, e.g. `Quantity(value=24, unit=ureg.hour)`), `description`, `source` when available.
 - Use `ProcessEvent.inputs` to declare which raw materials or named materials feed into a specific
  process event. This is useful when a raw material is introduced at a particular synthesis step
  rather than at the very start of the process. `inputs` can contain literal names or template
  variables. Examples:
  ```python
  # Literal: two raw materials are mixed together
  ProcessEvent(kind=ProcessKind.Mixing, inputs=["elements", "secondary_input_metal"], description="...")
  # Variable: the feedstock is parameterized so the group can be reused
  # synthesis group key: "mixing[Feedstock]"
  ProcessEvent(kind=ProcessKind.Mixing, inputs=["[Feedstock]"], description="...")
  # then in material process: "powder->milling->mixing[Feedstock=secondary_input_metal]"
  ```
 - Every raw material declared in `raw_materials` must be referenced somewhere — either as a
  comma-separated input in a `Material.process` string or via `ProcessEvent.inputs`.
 - `ProcessKind.ArcMelting` and `ProcessKind.InductionMelting` must always be immediately followed by a casting step (e.g. `ProcessKind.AsCast`, `ProcessKind.SuctionCasting`, `ProcessKind.DropCasting`, `ProcessKind.GravityCasting`, `ProcessKind.DirectionalSolidification`, or `ProcessKind.CastingUnspecified`).
 - IMPORTANT: Every synthesis group you define MUST be referenced by at least one material's `process` string.
  Do not define groups that are not used.
 - IMPORTANT: If a group name contains a template variable like `[Temp]` (e.g. `"annealing[Temp]"`),
  that exact placeholder string `"[Temp]"` MUST appear as a value in at least one `ProcessEvent` field
  within that group. For example: `temperature=Quantity(value="[Temp]", unit=Celsius)`.
  Do NOT put the actual number in the group definition — the actual value goes in the material's
  `process` string (e.g. `process="elements->annealing[Temp=700]"`).
 - Only include actual fabrication/processing steps in `synthesis_groups`.
  Do NOT put measurement methods, characterization techniques, or testing procedures here.
3) `output_materials` (required): list of `Material`.
 - Populate `Material.process` using dataset process notation such as
  `"elements->creation"` or `"base->annealing[Temp=700]->quenching"`.
 - The first segment (before the first `->`) is a comma-separated list of input raw materials
  or named materials. Use commas to combine multiple inputs: `"elements,reinforcement->mixing->sintering"`.
 - Include `Material.name` only if the paper names that material.
 - `Material.measurements` must include at least one `CompositionMeasurement`.
 - Add ALL reported property measurements with `Measurement(...)` using `AlloyMeasurementKind` members.
4) Measurements:
 - Use `Measurement(kind=AlloyMeasurementKind.<kind>, value=<number>, unit=<unit>)`.
 - If uncertainty is reported (e.g. "450 +- 20"), set `value=450.0` and `uncertainty=20.0`.
 - If temperature or pressure is tied to a measurement, set `temperature=Quantity(...)` or `pressure=Measurement(...)`.
 - Assume room temperature is ~23 C when the paper says "room temperature" without a number.
 - Pay attention to how the paper qualifies numeric values. Use the value field as follows:
  - Exact value: `value=50.0` (paper states "50 HV")
  - Approximate value: `value="~50"` (paper says "around 50 HV", "approximately 50 HV", "about 50 HV")
  - Greater than: `value=">50"` (paper says "above 50 HV", "greater than 50 HV", "exceeding 50 HV")
  - Less than: `value="<50"` (paper says "below 50 HV", "less than 50 HV", "under 50 HV")
  - Greater than or equal to: `value=">=50"` (paper says "at least 50 HV", "50 HV or more", "no less than 50 HV")
  - Less than or equal to: `value="<=50"` (paper says "at most 50 HV", "up to 50 HV", "no more than 50 HV")
  - Much greater than: `value=">>50"` (paper says "much greater than 50 HV", "far above 50 HV", "well above 50 HV")
  - Much less than: `value="<<50"` (paper says "much less than 50 HV", "far below 50 HV", "well below 50 HV")
 - When the paper explicitly states a value is a mean or average, set `measurement_statistic=MeasurementStatistic.mean`.
  Leave `measurement_statistic` as `None` (default) when the paper does not specify.
 - When a measurement is reported as a range (e.g. "5–50 μm", "between 50 and 180 nm"), use `Measurement.group_measurements(...)`:
  ```python
  *Measurement.group_measurements(
    kind=PhaseMeasurementKind.grain_size,
    unit=Micrometer,
    values=[
      CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
      CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
    ],
  )
  ```
  This creates two linked Measurement objects (one lower, one upper) that share the same `group_id`.
  Note the `*` spread operator — use it inside a list to unpack the group into individual measurements.
5) GlobalLatticeParam (for XRD lattice parameters and crystal structure):
 - Use `GlobalLatticeParam` when the paper reports lattice parameters from XRD for the overall material.
 - `lattice`: wrap a pymatgen `Lattice` in `LatticeMeasurement(...)`. Required parameters depend on type:
  - `Lattice.cubic(a)` — requires `a`
  - `Lattice.hexagonal(a, c)` — requires `a` and `c`
  - `Lattice.tetragonal(a, c)` — requires `a` and `c`
  - `Lattice.orthorhombic(a, b, c)` — requires `a`, `b`, and `c`
 - `struct`: the crystal structure enum, e.g. `CrysStruct.BCC`, `CrysStruct.FCC`.
 - `phase_fraction`: optionally attach a `Quantity` for the phase fraction if reported.
 - `name`: optional name for the phase (e.g. `"BCC phase"`, `"σ phase"`).
 - Include `source` noting where in the paper the data appears.
6) Configuration (for microstructural features):
 - Use `Configuration` to describe microstructural features like dendrites, precipitates, phases, lamellae,
  or regions of interest with distinct microstructure (e.g. a Cr-rich region, an interdendritic zone).
 - Do NOT use Configuration merely to record where on the bulk material a measurement was taken.
  If the paper says "hardness at the center region was 210 HV", that is a material-level measurement —
  put it in `Material.measurements`, not inside a Configuration named "center region".
 - `name`: identifies the feature (e.g. `"dendrite"`, `"FCC matrix"`, `"B2 precipitates"`).
 - `struct`: crystal structure if known (e.g. `CrysStruct.BCC`, `CrysStruct.FCC`, `CrysStruct.B2`).
 - `tags`: categorize the feature using `ConfigTag` members (e.g. `ConfigTag.Dendrite`, `(<ConfigTag.Precipitate: 'precipitate'>, <ConfigTag.Intragranular: 'intragranular'>)`).
 - `within`: reference the `name` of another Configuration in the same material to indicate nesting
  (e.g. precipitates within a matrix phase). The referenced Configuration must exist in the same material.
  All precipitates MUST have a `within` field referencing the configuration they are contained in.
 - `measurements`: list of measurements specific to this feature — typically `CompMeasurement` (EDS composition),
  `Measurement` (grain size, phase fraction, etc. using `PhaseMeasurementKind`), or `LatticeMeasurement`.
7) `descriptions` (optional): list of `AlloyDescriptionGroup` for recording contextual information about
 measurement methods and equipment, or process-related descriptions that apply to all materials.
 - Use this field for information about HOW measurements were performed (instruments, testing conditions,
  specimen dimensions, strain rates) and general descriptions of process steps (equipment details).
 - Do NOT put this information in `synthesis_groups` — synthesis groups are for the actual fabrication
  process chain, not for characterization or testing procedures.
 - `kinds`: list of `AlloyMeasurementKind`, `PhaseMeasurementKind`, `ProcessKind`, or `MeasurementMethod`
  members that this description applies to.
 - `method`: optional `MeasurementMethod` enum member (e.g. `MeasurementMethod.VickersHardnessTest`,
  `MeasurementMethod.CompressionTest`).
 - `desc`: free-text description of the method, equipment, or conditions.
 - Examples:
  ```python
  descriptions=[
    # Describes how hardness was measured
    AlloyDescriptionGroup(
      kinds=[AlloyMeasurementKind.vickers_hardness],
      method=MeasurementMethod.VickersHardnessTest,
      desc="Microhardness measured with Vickers hardness tester at 500 gf load for 15 s",
    ),
    # Describes compression testing conditions
    AlloyDescriptionGroup(
      kinds=[AlloyMeasurementKind.yield_strength_compression,
          AlloyMeasurementKind.fracture_strength_compression],
      method=MeasurementMethod.CompressionTest,
      desc="Compressive testing on MTS 809 machine at room temperature. Specimens: 3 mm x 6 mm.",
    ),
    # Describes a process step's equipment
    AlloyDescriptionGroup(
      kinds=[ProcessKind.Grinding],
      desc="performed on a grinding wheel",
    ),
  ]
  ```
"""

# %% Available Names in Runtime
# Configuration: include_composition_helpers=True, include_normalize_function=False, include_descriptions=True
AVAILABLE_NAMES = """
Available names in runtime:
- Core classes: `Experiment`, `Material`, `RawMaterial`, `RawMaterialKind`, `ProcessEvent`, `ProcessKind`, `Measurement`, `CompositionMeasurement`
- Microstructure classes: `GlobalLatticeParam`, `LatticeMeasurement`, `Configuration`
- Lattice constructor: `Lattice` (from `pymatgen.core.lattice`) — e.g. `Lattice.cubic(a)`, `Lattice.hexagonal(a, c)`
- Measurement statistics: `MeasurementStatistic`, `CoreMeasurementValue`
- Enums: `AlloyMeasurementKind`, `PhaseMeasurementKind`, `ProcessKind`, `CrysStruct`, `ConfigTag`, `MeasurementMethod`, `ValueQualifier`
- `AlloyMeasurementKind` members: `vickers_hardness`, `berkovich_hardness`, `pugh_ductility_ratio`, `density`, `yield_strength_tension`, `ultimate_strain_tension`, `ultimate_tensile_strength`, `fracture_strain_tension`, `fracture_strength_tension`, `strain_hardening_exponent_tension`, `poissons_ratio_tension`, `fracture_energy_tension`, `true_stress_tension`, `yield_strength_compression`, `ultimate_strain_compression`, `ultimate_compressive_strength`, `fracture_strain_compression`, `fracture_strength_compression`, `strain_hardening_exponent_compression`, `poissons_ratio_compression`, `fracture_energy_compression`, `true_stress_compression`, `elastic_limit_compression`, `elastic_limit_tension`, `youngs_modulus`, `fracture_toughness`, `work_of_fracture`, `crystallite_size`, `lattice_strain`, `melting_point`, `solidus`, `liquidus`
- `PhaseMeasurementKind` members (for Configuration/GlobalLatticeParam measurements): `volume_fraction`, `length`, `grain_size`, `phase_size`
- `ProcessKind` members: `Mixing`, `MechanicalAlloying`, `PlanetaryMilling`, `GasAtomization`, `ArcMelting`, `InductionMelting`, `CastingUnspecified`, `AsCast`, `GravityCasting`, `DropCasting`, `SuctionCasting`, `DirectionalSolidification`, `SparkPlasmaSintering`, `HotPressingSintering`, `VacuumFurnace`, `Homogenization`, `Annealing`, `NonIsothermalAnnealing`, `IsothermalHolding`, `WaterQuenching`, `SolutionHeatTreatment`, `HotExtrusion`, `HotRolling`, `ColdRolling`, `CrossRolling`, `ColdForging`, `Press`, `FrictionStirProcessing`, `ElectricalDischargeMachining`, `Cut`, `Grinding`, `Polishing`, `Etching`, `AquaRegia`, `SandBlasting`, `Degreased`, `UltrasonicBath`, `AirDrying`
- `CrysStruct` members: `FCC`, `BCC`, `HCP`, `DHCP`, `Diamond`, `L12`, `L10`, `B2`, `D019`, `D03`, `Heusler`, `Rocksalt`, `Zincblende`, `C14`, `C15`, `Perovskite`, `Amorphous`, `Unknown`
- `ConfigTag` members: `Dendrite`, `Interdendritic`, `Equiaxed`, `Columnar`, `Eutectic`, `Coring`, `Lath`, `Martensite`, `Acicular`, `Lamellar`, `Widmanstatten`, `Matrix`, `Precipitate`, `Intragranular`, `Intergranular`, `Segregation`, `Twin`, `Subgrain`, `Structure`, `Unknown`
- `MeasurementStatistic` members: `mean`, `median`, `lower`, `upper`, `percentile`
- Units registry: `ureg` (a pint `UnitRegistry` instance)
- Pre-defined units: `HV`, `GigaPascal`, `MegaPascal`, `Micrometer`, `Nanometer`, `gram_per_cm3`, `percent`, `dimensionless`, `Celsius`, `Kelvin`, `Atm`
- `ureg` supports accessing any standard pint unit as an attribute (e.g. `ureg.angstrom`, `ureg.joule`, `ureg.meter`).
- You can compose new units with arithmetic: `ureg.megapascal * ureg.meter ** 0.5`, `ureg.gram / ureg.cm ** 3`, `ureg.ampere / ureg.cm ** 2`.
- You can define entirely new units with `ureg.define("HV = 9.807 * megapascal = vickers_hardness")` if a unit is not already available.
- Composition parser: `Composition` (from `pymatgen`)
- Description group: `AlloyDescriptionGroup`
- `MeasurementMethod` members: `XRD`, `DSC`, `TensileTest`, `CompressionTest`, `VickersHardnessTest`, `NanoindentTest`, `ArchimedesMethod`, `OpticalMicroscope`, `SEM`, `TEM`, `STEM`, `EBSD`, `UniversalTestingMachine`, `ResonanceUltrasoundSpectroscopy`, `FractureToughnessTest`, `Balance`, `EDS`, `TEM_EDS`, `WDS`, `EPMA`, `LIBS`, `ED_XRF`, `WD_XRF`, `Spark_OES`, `ICP_OES`, `ICP_MS`, `Unspecified`
- Composition helper functions: `composition_with_weight_additions`, `balance_composition`
- For weight-percent composition dictionaries, prefer `Composition.from_weight_dict(...)` when available in your environment
"""

# %% Composition Helpers
COMPOSITION_HELPERS = """
Composition helper functions:

1. `balance_composition(main_element, additions)` — for "balance notation" compositions.
   Use when the paper writes compositions like Ti-6Al-4V, meaning the main element (Ti) makes up
   the balance (remainder to 100 wt%) after accounting for the other additions (6 wt% Al, 4 wt% V).
   - `main_element`: string name of the balance element (e.g. `"Ti"`).
   - `additions`: dict mapping element names to their weight percentages (e.g. `{"Al": 6, "V": 4}`).
   - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
   - Example: `balance_composition("Ti", {"Al": 6, "V": 4})` — Ti-6Al-4V (Ti is 90 wt% balance).
   - Example: `balance_composition("Fe", {"C": 0.4, "Mn": 1.5})` — Fe balance with 0.4 wt% C and 1.5 wt% Mn.

2. `composition_with_weight_additions(base, additions, addition_wt_frac)` —
   for when the paper says "add X wt% of Y to base alloy".
   - `base`: the original alloy composition before additions (usually atomic-fraction style).
   - `additions`: the additive recipe expressed by weight ratio; use `Composition.from_weight_dict(...)` for this.
   - `addition_wt_frac`: decimal fraction of additive mass relative to base mass (`5 wt% -> 0.05`, `2.5 wt% -> 0.025`).
     Do not pass percent values like `5`; pass decimal fractions like `0.05`.
   - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
   - Example: `composition_with_weight_additions(Composition("NbTaTiZr"), Composition.from_weight_dict({"Mo": 50, "W": 50}), 0.05)` — 5 wt% (Mo/W mix) added to NbTaTiZr.

Also available:
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — create a Composition directly from weight-percent values.

Composition formatting guidance:
- Use plain formulas for atomic-fraction style entries (e.g. `Composition("Nb0.25Ta0.25Ti0.25Zr0.25")`).
- Never append text like `(at.%)` or `(wt.%)` inside composition formula strings.
"""

# %% Normalize Function Prompt
NORMALIZE_FUNCTION = """
Normalize function:
- `normalize(val, val_in_paper, source=None)` is a documentation wrapper that records when a paper's terminology differs from our standardized value. It returns `val` unchanged.
- Use it whenever the paper uses different terminology than our standardized enum values or process kind strings.
- `val`: the standardized/ground-truth value you want to use.
- `val_in_paper`: the exact term the paper used (as a string).
- `source`: optional string noting where in the paper the term appears.

When to use `normalize`:
- A measurement kind in the paper doesn't exactly match an `AlloyMeasurementKind` member name (e.g. the paper says "Yield Strength" but the measurement was done via compression, so the correct kind is `AlloyMeasurementKind.yield_strength_compression`).
- A process description in the paper is more specific than a `ProcessKind` member (e.g. the paper says "Vacuum Arc Melting" but the correct kind is `ProcessKind.ArcMelting`).

Examples:
```python
# Paper says "Yield Strength" but the test was compressive
Measurement(
  kind=normalize(AlloyMeasurementKind.yield_strength_compression, val_in_paper="Yield Strength"),
  value=1200.0,
  unit=MegaPascal,
)

# Paper says "Fracture Strain" but it is ultimate strain in compression
Measurement(
  kind=normalize(AlloyMeasurementKind.ultimate_strain_compression, val_in_paper="Fracture Strain"),
  value=25.0,
  unit=percent,
)

# Paper says "Vacuum Arc Melting"; the correct ProcessKind is ArcMelting
ProcessEvent(
  kind=normalize(ProcessKind.ArcMelting, val_in_paper="Vacuum Arc Melting"),
  description="Melted under vacuum",
)
```

When NOT to use `normalize`:
- If the paper's terminology already matches the standardized value exactly, just use the value directly (e.g. `kind=AlloyMeasurementKind.vickers_hardness` when the paper says "Vickers hardness").
"""

# %% J.0.4 Composition Extraction Task Prompt
# Full prompt for composition-only extraction (code output mode, with helpers)
COMPOSITION_PROMPT = """
Extract all compositions of alloys/materials that the authors physically synthesized in this paper.

We are only interested in the compositions of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Compositions mentioned in passing from other studies or references
- Compositions from computational/theoretical predictions
- Compositions of raw materials or precursors (e.g. pure elements)
- Compositions of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall composition of each material the authors created.

IMPORTANT: For each material, report only one composition — the one measured by the highest-resolution analytical technique available. Prefer analytically measured compositions over nominal/intended ones. The priority order from best to worst is:
ICP-MS > ICP-OES > WD-XRF > EPMA > WDS > ED-XRF > Spark-OES > EDS > LIBS > nominal/Balance
For example, if a paper reports both a nominal composition and an EDS-measured composition for the same material, use the EDS-measured one. If it reports both EDS and XRF for the same material, use the XRF measurement.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return exactly one Python fenced code block and nothing else.
The code must set a `result` variable to a `list[Composition]`.
Each entry should be a `pymatgen.core.Composition` object representing one alloy the authors made.

Example:
```python
result = [
  Composition("MgFeNi"),
  Composition("Al0.5CoCrFeNi"),
  Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20}),
  balance_composition("Ti", {"Al": 6, "V": 4}),
]
```

Available names in runtime:
- `Composition` (from `pymatgen.core`) — use to create composition objects
- `Composition("MgFeNi")` — from formula string (atomic ratio style)
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — from weight-percent dictionary
- Composition helper functions: `balance_composition`, `composition_with_weight_additions`

Composition helper functions:

1. `balance_composition(main_element, additions)` — for "balance notation" compositions.
 Use when the paper writes compositions like Ti-6Al-4V, meaning the main element (Ti) makes up
 the balance (remainder to 100 wt%) after accounting for the other additions (6 wt% Al, 4 wt% V).
 - `main_element`: string name of the balance element (e.g. `"Ti"`).
 - `additions`: dict mapping element names to their weight percentages (e.g. `{"Al": 6, "V": 4}`).
 - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
 - Example: `balance_composition("Ti", {"Al": 6, "V": 4})` — Ti-6Al-4V (Ti is 90 wt% balance).
 - Example: `balance_composition("Fe", {"C": 0.4, "Mn": 1.5})` — Fe balance with 0.4 wt% C and 1.5 wt% Mn.

2. `composition_with_weight_additions(base, additions, addition_wt_frac)` —
 for when the paper says "add X wt% of Y to base alloy".
 - `base`: the original alloy composition before additions (usually atomic-fraction style).
 - `additions`: the additive recipe expressed by weight ratio; use `Composition.from_weight_dict(...)` for this.
 - `addition_wt_frac`: decimal fraction of additive mass relative to base mass (`5 wt% -> 0.05`, `2.5 wt% -> 0.025`).
  Do not pass percent values like `5`; pass decimal fractions like `0.05`.
 - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
 - Example: `composition_with_weight_additions(Composition("NbTaTiZr"), Composition.from_weight_dict({"Mo": 50, "W": 50}), 0.05)` — 5 wt% (Mo/W mix) added to NbTaTiZr.

Also available:
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — create a Composition directly from weight-percent values.

Composition formatting guidance:
- Use plain formulas for atomic-fraction style entries (e.g. `Composition("Nb0.25Ta0.25Ti0.25Zr0.25")`).
- Never append text like `(at.%)` or `(wt.%)` inside composition formula strings.
"""

# %% Composition Extraction Task Prompt (string output, no helpers)
COMPOSITION_PROMPT_STRING = """
Extract all compositions of alloys/materials that the authors physically synthesized in this paper.

We are only interested in the compositions of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Compositions mentioned in passing from other studies or references
- Compositions from computational/theoretical predictions
- Compositions of raw materials or precursors (e.g. pure elements)
- Compositions of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall composition of each material the authors created.

IMPORTANT: For each material, report only one composition — the one measured by the highest-resolution analytical technique available. Prefer analytically measured compositions over nominal/intended ones. The priority order from best to worst is:
ICP-MS > ICP-OES > WD-XRF > EPMA > WDS > ED-XRF > Spark-OES > EDS > LIBS > nominal/Balance
For example, if a paper reports both a nominal composition and an EDS-measured composition for the same material, use the EDS-measured one. If it reports both EDS and XRF for the same material, use the XRF measurement.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return one composition formula per line inside a fenced code block.
Each formula must be a valid chemical formula parseable by pymatgen's `Composition()` constructor.
Use standard chemical formula notation (e.g. atomic ratio style).

For weight-percent compositions, convert to the equivalent atomic-ratio formula.

Example:
```
Al0.5CoCrFeNi
MgFeNi
Fe2O3
```

"""

# %% Full Extraction Prompt (all sections assembled)
# This is the complete prompt sent to the LLM for zero-shot experiment extraction.
FULL_EXTRACTION_PROMPT = """
Extract experiments from this paper.

We are only interested in materials the authors physically made in their lab.
Extract ALL properties reported for those materials — mechanical, thermal, physical, microstructural, etc.
Include properties derived from measurements (e.g. strain hardening exponent from a stress-strain curve, fracture toughness from a fracture test, Pugh ductility ratio from measured elastic constants).
Exclude properties that are purely computed from composition or thermodynamic databases (e.g. CALPHAD/ThermoCalc predictions, DFT-computed values, rule-of-mixtures estimates with no experimental validation).

Return a Python fenced code block (```python ... ```) containing a single expression that evaluates to a `list[Experiment]`.

Use this exact shape:

```python
[
  Experiment(
    raw_materials={
      "elements": RawMaterial(
        kind=RawMaterialKind.Ingot,
        description="...",
        source="...",
      )
    },
    synthesis_groups={
      "creation": [
        ProcessEvent(kind=ProcessKind.ArcMelting, description="Remelted 5 times to promote homogeneity, flipped pellet between each remelt", source="..."),
        ProcessEvent(kind=ProcessKind.AsCast, description="...", source="..."),
        ProcessEvent(kind=ProcessKind.Homogenization, temperature=Quantity(value=1200, unit=Celsius), duration=Quantity(value=24, unit=ureg.hour), source="..."),
        ProcessEvent(kind=ProcessKind.WaterQuenching, source="..."),
      ],
      "annealing[Temp]": [
        ProcessEvent(
          kind=ProcessKind.Annealing,
          temperature=Quantity(value="[Temp]", unit=Celsius),
          source="...",
        ),
      ],
    },
    descriptions=[
      AlloyDescriptionGroup(
        kinds=[AlloyMeasurementKind.vickers_hardness],
        method=MeasurementMethod.VickersHardnessTest,
        desc="The microhardness (HV) of the alloys was measured with a Vickers hardness tester under a load of 500 gf",
      ),
      AlloyDescriptionGroup(
        kinds=[ProcessKind.Grinding],
        desc="performed on a grinding wheel",
      ),
    ],
    output_materials=[
      Material(
        process="elements->creation",
        name="materialA",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=321.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
          # When a value is explicitly a mean/average:
          Measurement(
            kind=AlloyMeasurementKind.yield_strength_tension,
            value=450.0,
            unit=MegaPascal,
            measurement_statistic=MeasurementStatistic.mean,
            source="...",
          ),
          # When a value is reported as a range (e.g. "5–50 μm"):
          *Measurement.group_measurements(
            kind=PhaseMeasurementKind.grain_size,
            unit=Micrometer,
            values=[
              CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
              CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
            ],
          ),
          # XRD-determined lattice parameter and crystal structure:
          GlobalLatticeParam(
            lattice=LatticeMeasurement(Lattice.cubic(3.208)),
            struct=CrysStruct.BCC,
            source="...",
          ),
          # Microstructural feature (e.g. dendrite with EDS composition):
          Configuration(
            name="dendrite",
            tags={ConfigTag.Dendrite},
            measurements=[
              CompMeasurement(
                {"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9},
                method=MeasurementMethod.EDS,
                source="...",
              ),
            ],
          ),
          # Nested configuration (precipitate within a phase):
          Configuration(
            name="FCC matrix",
            struct=CrysStruct.FCC,
            tags={ConfigTag.Matrix},
            measurements=[
              Measurement(
                kind=PhaseMeasurementKind.grain_size,
                value="~0.71",
                unit=Micrometer,
              ),
            ],
          ),
          Configuration(
            name="B2 precipitates",
            struct=CrysStruct.B2,
            tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
            within="FCC matrix",
            measurements=[
              *Measurement.group_measurements(
                kind=PhaseMeasurementKind.grain_size,
                unit=Nanometer,
                values=[
                  CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=50),
                  CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=180),
                ],
              ),
            ],
          ),
        ],
      ),
      Material(
        process="materialA->annealing[Temp=10]",
        name="materialB",
        measurements=[
          CompositionMeasurement("MgFeNi"),
          Measurement(
            kind=AlloyMeasurementKind.vickers_hardness,
            value=350.0,
            unit=HV,
            uncertainty=7.0,
            source="...",
          ),
        ],
      ),
    ],
  ),
]
```

How to write each Experiment and fields to populate:
1) `raw_materials` (required): map each initial input name (for example `"elements"` or `"powders"`) to `RawMaterial`.
 - Populate `kind` with `RawMaterialKind` (usually `Ingot`, `Powder`, or `Unspecified`).
 - Populate `description` and `source` whenever the paper states purity, supplier, or precursor details.
2) `synthesis_groups` (required): a dict of named synthesis stages to lists of `ProcessEvent`.
 - Use reusable stages and process variables when appropriate (for example `"annealing[Temp]"`).
 - Each `ProcessEvent` should include `kind` (a `ProcessKind` enum member), and include `temperature` (as `Quantity`, e.g. `Quantity(value=1200, unit=Celsius)`), `duration` (as `Quantity`, e.g. `Quantity(value=24, unit=ureg.hour)`), `description`, `source` when available.
 - Use `ProcessEvent.inputs` to declare which raw materials or named materials feed into a specific
  process event. This is useful when a raw material is introduced at a particular synthesis step
  rather than at the very start of the process. `inputs` can contain literal names or template
  variables. Examples:
  ```python
  # Literal: two raw materials are mixed together
  ProcessEvent(kind=ProcessKind.Mixing, inputs=["elements", "secondary_input_metal"], description="...")
  # Variable: the feedstock is parameterized so the group can be reused
  # synthesis group key: "mixing[Feedstock]"
  ProcessEvent(kind=ProcessKind.Mixing, inputs=["[Feedstock]"], description="...")
  # then in material process: "powder->milling->mixing[Feedstock=secondary_input_metal]"
  ```
 - Every raw material declared in `raw_materials` must be referenced somewhere — either as a
  comma-separated input in a `Material.process` string or via `ProcessEvent.inputs`.
 - `ProcessKind.ArcMelting` and `ProcessKind.InductionMelting` must always be immediately followed by a casting step (e.g. `ProcessKind.AsCast`, `ProcessKind.SuctionCasting`, `ProcessKind.DropCasting`, `ProcessKind.GravityCasting`, `ProcessKind.DirectionalSolidification`, or `ProcessKind.CastingUnspecified`).
 - IMPORTANT: Every synthesis group you define MUST be referenced by at least one material's `process` string.
  Do not define groups that are not used.
 - IMPORTANT: If a group name contains a template variable like `[Temp]` (e.g. `"annealing[Temp]"`),
  that exact placeholder string `"[Temp]"` MUST appear as a value in at least one `ProcessEvent` field
  within that group. For example: `temperature=Quantity(value="[Temp]", unit=Celsius)`.
  Do NOT put the actual number in the group definition — the actual value goes in the material's
  `process` string (e.g. `process="elements->annealing[Temp=700]"`).
 - Only include actual fabrication/processing steps in `synthesis_groups`.
  Do NOT put measurement methods, characterization techniques, or testing procedures here.
3) `output_materials` (required): list of `Material`.
 - Populate `Material.process` using dataset process notation such as
  `"elements->creation"` or `"base->annealing[Temp=700]->quenching"`.
 - The first segment (before the first `->`) is a comma-separated list of input raw materials
  or named materials. Use commas to combine multiple inputs: `"elements,reinforcement->mixing->sintering"`.
 - Include `Material.name` only if the paper names that material.
 - `Material.measurements` must include at least one `CompositionMeasurement`.
 - Add ALL reported property measurements with `Measurement(...)` using `AlloyMeasurementKind` members.
4) Measurements:
 - Use `Measurement(kind=AlloyMeasurementKind.<kind>, value=<number>, unit=<unit>)`.
 - If uncertainty is reported (e.g. "450 +- 20"), set `value=450.0` and `uncertainty=20.0`.
 - If temperature or pressure is tied to a measurement, set `temperature=Quantity(...)` or `pressure=Measurement(...)`.
 - Assume room temperature is ~23 C when the paper says "room temperature" without a number.
 - Pay attention to how the paper qualifies numeric values. Use the value field as follows:
  - Exact value: `value=50.0` (paper states "50 HV")
  - Approximate value: `value="~50"` (paper says "around 50 HV", "approximately 50 HV", "about 50 HV")
  - Greater than: `value=">50"` (paper says "above 50 HV", "greater than 50 HV", "exceeding 50 HV")
  - Less than: `value="<50"` (paper says "below 50 HV", "less than 50 HV", "under 50 HV")
  - Greater than or equal to: `value=">=50"` (paper says "at least 50 HV", "50 HV or more", "no less than 50 HV")
  - Less than or equal to: `value="<=50"` (paper says "at most 50 HV", "up to 50 HV", "no more than 50 HV")
  - Much greater than: `value=">>50"` (paper says "much greater than 50 HV", "far above 50 HV", "well above 50 HV")
  - Much less than: `value="<<50"` (paper says "much less than 50 HV", "far below 50 HV", "well below 50 HV")
 - When the paper explicitly states a value is a mean or average, set `measurement_statistic=MeasurementStatistic.mean`.
  Leave `measurement_statistic` as `None` (default) when the paper does not specify.
 - When a measurement is reported as a range (e.g. "5–50 μm", "between 50 and 180 nm"), use `Measurement.group_measurements(...)`:
  ```python
  *Measurement.group_measurements(
    kind=PhaseMeasurementKind.grain_size,
    unit=Micrometer,
    values=[
      CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=5),
      CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=50),
    ],
  )
  ```
  This creates two linked Measurement objects (one lower, one upper) that share the same `group_id`.
  Note the `*` spread operator — use it inside a list to unpack the group into individual measurements.
5) GlobalLatticeParam (for XRD lattice parameters and crystal structure):
 - Use `GlobalLatticeParam` when the paper reports lattice parameters from XRD for the overall material.
 - `lattice`: wrap a pymatgen `Lattice` in `LatticeMeasurement(...)`. Required parameters depend on type:
  - `Lattice.cubic(a)` — requires `a`
  - `Lattice.hexagonal(a, c)` — requires `a` and `c`
  - `Lattice.tetragonal(a, c)` — requires `a` and `c`
  - `Lattice.orthorhombic(a, b, c)` — requires `a`, `b`, and `c`
 - `struct`: the crystal structure enum, e.g. `CrysStruct.BCC`, `CrysStruct.FCC`.
 - `phase_fraction`: optionally attach a `Quantity` for the phase fraction if reported.
 - `name`: optional name for the phase (e.g. `"BCC phase"`, `"σ phase"`).
 - Include `source` noting where in the paper the data appears.
6) Configuration (for microstructural features):
 - Use `Configuration` to describe microstructural features like dendrites, precipitates, phases, lamellae,
  or regions of interest with distinct microstructure (e.g. a Cr-rich region, an interdendritic zone).
 - Do NOT use Configuration merely to record where on the bulk material a measurement was taken.
  If the paper says "hardness at the center region was 210 HV", that is a material-level measurement —
  put it in `Material.measurements`, not inside a Configuration named "center region".
 - `name`: identifies the feature (e.g. `"dendrite"`, `"FCC matrix"`, `"B2 precipitates"`).
 - `struct`: crystal structure if known (e.g. `CrysStruct.BCC`, `CrysStruct.FCC`, `CrysStruct.B2`).
 - `tags`: categorize the feature using `ConfigTag` members (e.g. `ConfigTag.Dendrite`, `(<ConfigTag.Precipitate: 'precipitate'>, <ConfigTag.Intragranular: 'intragranular'>)`).
 - `within`: reference the `name` of another Configuration in the same material to indicate nesting
  (e.g. precipitates within a matrix phase). The referenced Configuration must exist in the same material.
  All precipitates MUST have a `within` field referencing the configuration they are contained in.
 - `measurements`: list of measurements specific to this feature — typically `CompMeasurement` (EDS composition),
  `Measurement` (grain size, phase fraction, etc. using `PhaseMeasurementKind`), or `LatticeMeasurement`.
7) `descriptions` (optional): list of `AlloyDescriptionGroup` for recording contextual information about
 measurement methods and equipment, or process-related descriptions that apply to all materials.
 - Use this field for information about HOW measurements were performed (instruments, testing conditions,
  specimen dimensions, strain rates) and general descriptions of process steps (equipment details).
 - Do NOT put this information in `synthesis_groups` — synthesis groups are for the actual fabrication
  process chain, not for characterization or testing procedures.
 - `kinds`: list of `AlloyMeasurementKind`, `PhaseMeasurementKind`, `ProcessKind`, or `MeasurementMethod`
  members that this description applies to.
 - `method`: optional `MeasurementMethod` enum member (e.g. `MeasurementMethod.VickersHardnessTest`,
  `MeasurementMethod.CompressionTest`).
 - `desc`: free-text description of the method, equipment, or conditions.
 - Examples:
  ```python
  descriptions=[
    # Describes how hardness was measured
    AlloyDescriptionGroup(
      kinds=[AlloyMeasurementKind.vickers_hardness],
      method=MeasurementMethod.VickersHardnessTest,
      desc="Microhardness measured with Vickers hardness tester at 500 gf load for 15 s",
    ),
    # Describes compression testing conditions
    AlloyDescriptionGroup(
      kinds=[AlloyMeasurementKind.yield_strength_compression,
          AlloyMeasurementKind.fracture_strength_compression],
      method=MeasurementMethod.CompressionTest,
      desc="Compressive testing on MTS 809 machine at room temperature. Specimens: 3 mm x 6 mm.",
    ),
    # Describes a process step's equipment
    AlloyDescriptionGroup(
      kinds=[ProcessKind.Grinding],
      desc="performed on a grinding wheel",
    ),
  ]
  ```

Available names in runtime:
- Core classes: `Experiment`, `Material`, `RawMaterial`, `RawMaterialKind`, `ProcessEvent`, `ProcessKind`, `Measurement`, `CompositionMeasurement`
- Microstructure classes: `GlobalLatticeParam`, `LatticeMeasurement`, `Configuration`
- Lattice constructor: `Lattice` (from `pymatgen.core.lattice`) — e.g. `Lattice.cubic(a)`, `Lattice.hexagonal(a, c)`
- Measurement statistics: `MeasurementStatistic`, `CoreMeasurementValue`
- Enums: `AlloyMeasurementKind`, `PhaseMeasurementKind`, `ProcessKind`, `CrysStruct`, `ConfigTag`, `MeasurementMethod`, `ValueQualifier`
- `AlloyMeasurementKind` members: `vickers_hardness`, `berkovich_hardness`, `pugh_ductility_ratio`, `density`, `yield_strength_tension`, `ultimate_strain_tension`, `ultimate_tensile_strength`, `fracture_strain_tension`, `fracture_strength_tension`, `strain_hardening_exponent_tension`, `poissons_ratio_tension`, `fracture_energy_tension`, `true_stress_tension`, `yield_strength_compression`, `ultimate_strain_compression`, `ultimate_compressive_strength`, `fracture_strain_compression`, `fracture_strength_compression`, `strain_hardening_exponent_compression`, `poissons_ratio_compression`, `fracture_energy_compression`, `true_stress_compression`, `elastic_limit_compression`, `elastic_limit_tension`, `youngs_modulus`, `fracture_toughness`, `work_of_fracture`, `crystallite_size`, `lattice_strain`, `melting_point`, `solidus`, `liquidus`
- `PhaseMeasurementKind` members (for Configuration/GlobalLatticeParam measurements): `volume_fraction`, `length`, `grain_size`, `phase_size`
- `ProcessKind` members: `Mixing`, `MechanicalAlloying`, `PlanetaryMilling`, `GasAtomization`, `ArcMelting`, `InductionMelting`, `CastingUnspecified`, `AsCast`, `GravityCasting`, `DropCasting`, `SuctionCasting`, `DirectionalSolidification`, `SparkPlasmaSintering`, `HotPressingSintering`, `VacuumFurnace`, `Homogenization`, `Annealing`, `NonIsothermalAnnealing`, `IsothermalHolding`, `WaterQuenching`, `SolutionHeatTreatment`, `HotExtrusion`, `HotRolling`, `ColdRolling`, `CrossRolling`, `ColdForging`, `Press`, `FrictionStirProcessing`, `ElectricalDischargeMachining`, `Cut`, `Grinding`, `Polishing`, `Etching`, `AquaRegia`, `SandBlasting`, `Degreased`, `UltrasonicBath`, `AirDrying`
- `CrysStruct` members: `FCC`, `BCC`, `HCP`, `DHCP`, `Diamond`, `L12`, `L10`, `B2`, `D019`, `D03`, `Heusler`, `Rocksalt`, `Zincblende`, `C14`, `C15`, `Perovskite`, `Amorphous`, `Unknown`
- `ConfigTag` members: `Dendrite`, `Interdendritic`, `Equiaxed`, `Columnar`, `Eutectic`, `Coring`, `Lath`, `Martensite`, `Acicular`, `Lamellar`, `Widmanstatten`, `Matrix`, `Precipitate`, `Intragranular`, `Intergranular`, `Segregation`, `Twin`, `Subgrain`, `Structure`, `Unknown`
- `MeasurementStatistic` members: `mean`, `median`, `lower`, `upper`, `percentile`
- Units registry: `ureg` (a pint `UnitRegistry` instance)
- Pre-defined units: `HV`, `GigaPascal`, `MegaPascal`, `Micrometer`, `Nanometer`, `gram_per_cm3`, `percent`, `dimensionless`, `Celsius`, `Kelvin`, `Atm`
- `ureg` supports accessing any standard pint unit as an attribute (e.g. `ureg.angstrom`, `ureg.joule`, `ureg.meter`).
- You can compose new units with arithmetic: `ureg.megapascal * ureg.meter ** 0.5`, `ureg.gram / ureg.cm ** 3`, `ureg.ampere / ureg.cm ** 2`.
- You can define entirely new units with `ureg.define("HV = 9.807 * megapascal = vickers_hardness")` if a unit is not already available.
- Composition parser: `Composition` (from `pymatgen`)
- Description group: `AlloyDescriptionGroup`
- `MeasurementMethod` members: `XRD`, `DSC`, `TensileTest`, `CompressionTest`, `VickersHardnessTest`, `NanoindentTest`, `ArchimedesMethod`, `OpticalMicroscope`, `SEM`, `TEM`, `STEM`, `EBSD`, `UniversalTestingMachine`, `ResonanceUltrasoundSpectroscopy`, `FractureToughnessTest`, `Balance`, `EDS`, `TEM_EDS`, `WDS`, `EPMA`, `LIBS`, `ED_XRF`, `WD_XRF`, `Spark_OES`, `ICP_OES`, `ICP_MS`, `Unspecified`
- Composition helper functions: `composition_with_weight_additions`, `balance_composition`
- For weight-percent composition dictionaries, prefer `Composition.from_weight_dict(...)` when available in your environment

Composition helper functions:

1. `balance_composition(main_element, additions)` — for "balance notation" compositions.
   Use when the paper writes compositions like Ti-6Al-4V, meaning the main element (Ti) makes up
   the balance (remainder to 100 wt%) after accounting for the other additions (6 wt% Al, 4 wt% V).
   - `main_element`: string name of the balance element (e.g. `"Ti"`).
   - `additions`: dict mapping element names to their weight percentages (e.g. `{"Al": 6, "V": 4}`).
   - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
   - Example: `balance_composition("Ti", {"Al": 6, "V": 4})` — Ti-6Al-4V (Ti is 90 wt% balance).
   - Example: `balance_composition("Fe", {"C": 0.4, "Mn": 1.5})` — Fe balance with 0.4 wt% C and 1.5 wt% Mn.

2. `composition_with_weight_additions(base, additions, addition_wt_frac)` —
   for when the paper says "add X wt% of Y to base alloy".
   - `base`: the original alloy composition before additions (usually atomic-fraction style).
   - `additions`: the additive recipe expressed by weight ratio; use `Composition.from_weight_dict(...)` for this.
   - `addition_wt_frac`: decimal fraction of additive mass relative to base mass (`5 wt% -> 0.05`, `2.5 wt% -> 0.025`).
     Do not pass percent values like `5`; pass decimal fractions like `0.05`.
   - Returns a `Composition` object. Wrap the result in `CompositionMeasurement(...)` before adding to `Material.measurements`.
   - Example: `composition_with_weight_additions(Composition("NbTaTiZr"), Composition.from_weight_dict({"Mo": 50, "W": 50}), 0.05)` — 5 wt% (Mo/W mix) added to NbTaTiZr.

Also available:
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — create a Composition directly from weight-percent values.

Composition formatting guidance:
- Use plain formulas for atomic-fraction style entries (e.g. `Composition("Nb0.25Ta0.25Ti0.25Zr0.25")`).
- Never append text like `(at.%)` or `(wt.%)` inside composition formula strings.
"""

# %% JSON Example Extraction Prompt
# Configuration: include_source=True, include_descriptions=True
EXAMPLE_EXPERIMENT_SHAPE_JSON = """
```json
[
  {
    "raw_materials": {
      "elements": {
        "kind": "Ingot",
        "description": "...",
        "source": "..."
      }
    },
    "synthesis_groups": {
      "creation": [
        {"kind": "ArcMelting", "description": "...", "source": "..."},
        {"kind": "AsCast", "description": "...", "source": "..."}
      ],
      "annealing[Temp]": [
        {
          "kind": "Annealing",
          "temperature": {"value": "[Temp]", "unit": "celsius"},
          "source": "..."
        }
      ]
    },
    "descriptions": [
      {
        "kinds": ["vickers_hardness"],
        "method": "VickersHardnessTest",
        "desc": "The microhardness (HV) of the alloys was measured with a Vickers hardness tester under a load of 500 gf"
      },
      {
        "kinds": ["Grinding"],
        "desc": "performed on a grinding wheel"
      }
    ],
    "output_materials": [
      {
        "process": "elements->creation",
        "name": "materialA",
        "measurements": [
          {"_type": "composition", "composition": "MgFeNi"},
          {
            "_type": "measurement",
            "kind": "vickers_hardness",
            "value": 321.0,
            "unit": "HV",
            "uncertainty": 7.0,
            "source": "..."
          },
          {
            "_type": "measurement",
            "kind": "yield_strength_tension",
            "value": 450.0,
            "unit": "MegaPascal",
            "measurement_statistic": "mean",
            "source": "..."
          },
          {
            "_type": "group_measurements",
            "kind": "grain_size",
            "unit": "micrometer",
            "values": [
              {"statistic": "lower", "value": 5},
              {"statistic": "upper", "value": 50}
            ]
          },
          {
            "_type": "lattice_param",
            "lattice": {"type": "cubic", "a": 3.208},
            "struct": "BCC",
            "source": "..."
          },
          {
            "_type": "configuration",
            "name": "dendrite",
            "tags": ["Dendrite"],
            "measurements": [
              {
                "_type": "composition",
                "composition": {"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9},
                "method": "EDS",
                "source": "..."
              }
            ]
          },
          {
            "_type": "configuration",
            "name": "FCC matrix",
            "struct": "FCC",
            "tags": ["Matrix"],
            "measurements": [
              {
                "_type": "measurement",
                "kind": "grain_size",
                "value": "~0.71",
                "unit": "micrometer"
              }
            ]
          },
          {
            "_type": "configuration",
            "name": "B2 precipitates",
            "struct": "B2",
            "tags": ["Precipitate", "Intragranular"],
            "within": "FCC matrix",
            "measurements": [
              {
                "_type": "group_measurements",
                "kind": "grain_size",
                "unit": "nanometer",
                "values": [
                  {"statistic": "lower", "value": 50},
                  {"statistic": "upper", "value": 180}
                ]
              }
            ]
          }
        ]
      },
      {
        "process": "materialA->annealing[Temp=10]",
        "name": "materialB",
        "measurements": [
          {"_type": "composition", "composition": "MgFeNi"},
          {
            "_type": "measurement",
            "kind": "vickers_hardness",
            "value": 350.0,
            "unit": "HV",
            "uncertainty": 7.0,
            "source": "..."
          }
        ]
      }
    ]
  }
]
```
"""

# %% JSON Extraction Template Instruction Prompt
# Configuration: include_source=True, include_descriptions=True
FIELD_INSTRUCTIONS_JSON = """
How to write each experiment object and fields to populate:
1) "raw_materials" (required): map each initial input name (e.g. "elements" or "powders") to a raw material object.
   - "kind": one of the RawMaterialKind values (usually "Ingot", "Powder", or "Unspecified").
   - Populate "description" and "source" whenever the paper states purity, supplier, or precursor details.
2) "synthesis_groups" (required): an object mapping named synthesis stages to arrays of process event objects.
   - Use reusable stages and process variables when appropriate (e.g. "annealing[Temp]").
   - Each process event MUST include "kind" (a ProcessKind member name). Optionally include "temperature", "duration", "description", "source" when available. If you include temperature or duration, each MUST be a quantity object with BOTH "value" and "unit" (e.g. {"value": 700, "unit": "celsius"}). Omit the field entirely if unknown — never provide only "value" or only "unit".
   - Use "inputs" to declare which raw materials or named materials feed into a specific
     process event. Example: {"kind": "Mixing", "inputs": ["elements", "wc_additions"]}
   - Every raw material declared in "raw_materials" must be referenced somewhere — either as a
     comma-separated input in a material's "process" string or via a process event's "inputs".
   - "ArcMelting" and "InductionMelting" must always be immediately followed by a casting step
     (e.g. "AsCast", "SuctionCasting", "DropCasting", "GravityCasting", "DirectionalSolidification", or "CastingUnspecified").
   - IMPORTANT: Every synthesis group you define MUST be referenced by at least one material's "process" string.
     Do not define groups that are not used.
   - IMPORTANT: If a group name contains a template variable like [Temp] (e.g. "annealing[Temp]"),
     that exact placeholder string "[Temp]" MUST appear as a value in at least one process event field
     within that group. For example: "temperature": {"value": "[Temp]", "unit": "celsius"}.
     Do NOT put the actual number in the group definition — the actual value goes in the material's
     process string (e.g. "process": "elements->annealing[Temp=700]").
   - Only include actual fabrication/processing steps in synthesis_groups.
     Do NOT put measurement methods, characterization techniques, or testing procedures here.
3) "output_materials" (required): array of material objects.
   - "process": use process notation such as "elements->creation" or "base->annealing[Temp=700]->quenching".
   - The first segment (before the first "->") is a comma-separated list of input raw materials
     or named materials. Use commas to combine multiple inputs: "elements,reinforcement->mixing->sintering".
   - Include "name" only if the paper names that material.
   - "measurements" must include at least one composition measurement ({"_type": "composition", "composition": "..."}).
   - Add ALL reported property measurements.
4) Measurements — each item in the "measurements" array must have a "_type" field:
   - "_type": "composition" — for composition. Include "composition" (formula string or element dict) and optionally "method".
   - "_type": "measurement" — for a single measurement. REQUIRED: "kind", "value", "unit" (all three must be present). Optional: "uncertainty", "measurement_method", "temperature", "pressure", "measurement_statistic".
   - "_type": "group_measurements" — for ranges (e.g. "5–50 μm"). REQUIRED: "kind", "unit", "values" (array of {"statistic": "lower"/"upper", "value": ...}). All three must be present.
   - "_type": "lattice_param" — for XRD lattice parameters. Include "lattice" ({"type": "cubic", "a": 3.208}), "struct" (e.g. "BCC").
   - "_type": "configuration" — for microstructural features. Include "name", "tags", and nested "measurements".
   - If uncertainty is reported (e.g. "450 +- 20"), set "value": 450.0 and "uncertainty": 20.0.
   - If temperature or pressure is tied to a measurement, set "temperature": {"value": ..., "unit": "celsius"}. Both "value" and "unit" are REQUIRED in any quantity object.
   - Assume room temperature is ~23 C when the paper says "room temperature".
   - Pay attention to how the paper qualifies numeric values:
     - Exact value: "value": 50.0
     - Approximate value: "value": "~50"
     - Greater than: "value": ">50"
     - Less than: "value": "<50"
     - Greater than or equal: "value": ">=50"
     - Less than or equal: "value": "<=50"
     - Much greater than: "value": ">>50"
     - Much less than: "value": "<<50"
   - When the paper explicitly states a value is a mean or average, set "measurement_statistic": "mean".
     Leave it out when the paper does not specify.
5) Lattice parameters (for XRD-determined crystal structure):
   - Use "_type": "lattice_param" with a "lattice" object. Required parameters depend on type:
     - "cubic": {"type": "cubic", "a": ...} (requires "a")
     - "hexagonal": {"type": "hexagonal", "a": ..., "c": ...} (requires "a" and "c")
     - "tetragonal": {"type": "tetragonal", "a": ..., "c": ...} (requires "a" and "c")
     - "orthorhombic": {"type": "orthorhombic", "a": ..., "b": ..., "c": ...} (requires "a", "b", and "c")
   - "struct": the crystal structure (e.g. "BCC", "FCC").
   - "phase_fraction": optionally a quantity object (with both "value" and "unit") for the phase fraction if reported.
   - "name": optional name for the phase (e.g. "BCC phase", "σ phase").
   - Include "source" noting where in the paper the data appears.
6) Configuration (for microstructural features):
   - Use "_type": "configuration" to describe dendrites, precipitates, phases, lamellae, or regions with distinct microstructure.
   - Do NOT use configuration merely to record where on the bulk material a measurement was taken.
   - "name": identifies the feature (e.g. "dendrite", "FCC matrix", "B2 precipitates").
   - "struct": crystal structure if known (e.g. "BCC", "FCC", "B2").
   - "tags": array of ConfigTag values (e.g. ["Dendrite"], ["Precipitate", "Intragranular"]).
   - "within": reference the "name" of another configuration in the same material for nesting.
     All precipitates MUST have a "within" field referencing the configuration they are contained in.
   - "measurements": array of measurements specific to this feature.
7) "descriptions" (optional): array of description group objects for recording contextual information about
   measurement methods and equipment, or process-related descriptions.
   - Use this for information about HOW measurements were performed (instruments, testing conditions).
   - "kinds": array of AlloyMeasurementKind, PhaseMeasurementKind, ProcessKind, or MeasurementMethod values.
   - "method": optional MeasurementMethod value (string).
   - "desc": free-text description.
   - Example:
     ```json
     {"kinds": ["vickers_hardness"], "method": "VickersHardnessTest",
      "desc": "Microhardness measured with Vickers hardness tester at 500 gf load"}
     ```
"""

# %% JSON Available Types
# Configuration: include_composition_helpers=True, include_descriptions=True
AVAILABLE_TYPES_JSON = """
Available string values for JSON fields:
- Measurement "_type" values: "composition", "measurement", "group_measurements", "lattice_param", "configuration"
- AlloyMeasurementKind values (for "kind" field): "vickers_hardness", "berkovich_hardness", "pugh_ductility_ratio", "density", "yield_strength_tension", "ultimate_strain_tension", "ultimate_tensile_strength", "fracture_strain_tension", "fracture_strength_tension", "strain_hardening_exponent_tension", "poissons_ratio_tension", "fracture_energy_tension", "true_stress_tension", "yield_strength_compression", "ultimate_strain_compression", "ultimate_compressive_strength", "fracture_strain_compression", "fracture_strength_compression", "strain_hardening_exponent_compression", "poissons_ratio_compression", "fracture_energy_compression", "true_stress_compression", "elastic_limit_compression", "elastic_limit_tension", "youngs_modulus", "fracture_toughness", "work_of_fracture", "crystallite_size", "lattice_strain", "melting_point", "solidus", "liquidus"
- PhaseMeasurementKind values (for Configuration/GlobalLatticeParam measurements): "volume_fraction", "length", "grain_size", "phase_size"
- ProcessKind values: "Mixing", "MechanicalAlloying", "PlanetaryMilling", "GasAtomization", "ArcMelting", "InductionMelting", "CastingUnspecified", "AsCast", "GravityCasting", "DropCasting", "SuctionCasting", "DirectionalSolidification", "SparkPlasmaSintering", "HotPressingSintering", "VacuumFurnace", "Homogenization", "Annealing", "NonIsothermalAnnealing", "IsothermalHolding", "WaterQuenching", "SolutionHeatTreatment", "HotExtrusion", "HotRolling", "ColdRolling", "CrossRolling", "ColdForging", "Press", "FrictionStirProcessing", "ElectricalDischargeMachining", "Cut", "Grinding", "Polishing", "Etching", "AquaRegia", "SandBlasting", "Degreased", "UltrasonicBath", "AirDrying"
- RawMaterialKind values: "Ingot", "Powder", "Plate", "Unspecified", "Other"
- CrysStruct values: "FCC", "BCC", "HCP", "DHCP", "Diamond", "L12", "L10", "B2", "D019", "D03", "Heusler", "Rocksalt", "Zincblende", "C14", "C15", "Perovskite", "Amorphous", "Unknown"
- ConfigTag values: "Dendrite", "Interdendritic", "Equiaxed", "Columnar", "Eutectic", "Coring", "Lath", "Martensite", "Acicular", "Lamellar", "Widmanstatten", "Matrix", "Precipitate", "Intragranular", "Intergranular", "Segregation", "Twin", "Subgrain", "Structure", "Unknown"
- MeasurementStatistic values: "mean", "median", "lower", "upper", "percentile"
- Unit strings: "HV", "GigaPascal", "MegaPascal", "micrometer", "nanometer", "gram_per_cm3", "percent", "dimensionless", "celsius", "kelvin", "atm"
  - You can also use standard unit abbreviations: "GPa", "MPa", "um", "nm", "mm", etc.
- Composition: use a formula string (e.g. "CoCrFeNi") or an element dict (e.g. {"Co": 25, "Cr": 25, "Fe": 25, "Ni": 25})
- Lattice types: "cubic", "hexagonal", "tetragonal", "orthorhombic"
- Description group: object with "kinds", "method", "desc"
- MeasurementMethod values (for "measurement_method" field): "XRD", "DSC", "TensileTest", "CompressionTest", "VickersHardnessTest", "NanoindentTest", "ArchimedesMethod", "OpticalMicroscope", "SEM", "TEM", "STEM", "EBSD", "UniversalTestingMachine", "ResonanceUltrasoundSpectroscopy", "FractureToughnessTest", "Balance", "EDS", "TEM_EDS", "WDS", "EPMA", "LIBS", "ED_XRF", "WD_XRF", "Spark_OES", "ICP_OES", "ICP_MS", "Unspecified"
- Composition helpers: use "_helper" objects (see below) instead of formula strings when needed
- Omit fields that are null/not applicable — do not include them with null values.
"""

# %% JSON Composition Helpers
COMPOSITION_HELPERS_JSON = """
Composition helper objects (use these instead of formula strings when needed):

1. Balance composition — for "balance notation" (e.g. Ti-6Al-4V):
   ```json
   {"_helper": "balance_composition", "main_element": "Ti", "additions": {"Al": 6, "V": 4}}
   ```
   Ti is the balance element (90 wt%), Al is 6 wt%, V is 4 wt%.

2. From weight dict — create composition from weight percentages:
   ```json
   {"_helper": "from_weight_dict", "weights": {"Ni": 60, "Co": 20, "Cr": 20}}
   ```

3. Weight additions — add X wt% of a mix to a base alloy:
   ```json
   {"_helper": "weight_additions", "base": "NbTaTiZr", "additions_weights": {"Mo": 50, "W": 50}, "fraction": 0.05}
   ```
   Adds 5 wt% of a 50/50 Mo/W mix to equiatomic NbTaTiZr.
   "fraction" is a decimal: 5 wt% = 0.05, 2.5 wt% = 0.025.

Use these helpers inside the "composition" field of a composition measurement:
```json
{"_type": "composition", "composition": {"_helper": "balance_composition", "main_element": "Fe", "additions": {"Cr": 20}}}
```

Composition formatting guidance:
- Use plain formulas for atomic-fraction style entries (e.g. "Nb0.25Ta0.25Ti0.25Zr0.25").
- Never append text like "(at.%)" or "(wt.%)" inside composition formula strings.
"""

# %% Full JSON Extraction Prompt (all sections assembled)
# This is the complete prompt sent to the LLM for zero-shot JSON experiment extraction.
FULL_EXTRACTION_PROMPT_JSON = """
Extract experiments from this paper.

We are only interested in materials the authors physically made in their lab.
Extract ALL properties reported for those materials — mechanical, thermal, physical, microstructural, etc.
Include properties derived from measurements (e.g. strain hardening exponent from a stress-strain curve, fracture toughness from a fracture test, Pugh ductility ratio from measured elastic constants).
Exclude properties that are purely computed from composition or thermodynamic databases (e.g. CALPHAD/ThermoCalc predictions, DFT-computed values, rule-of-mixtures estimates with no experimental validation).

Return a JSON fenced code block (```json ... ```) containing an array of experiment objects.

Use this exact shape:

```json
[
  {
    "raw_materials": {
      "elements": {
        "kind": "Ingot",
        "description": "...",
        "source": "..."
      }
    },
    "synthesis_groups": {
      "creation": [
        {"kind": "ArcMelting", "description": "...", "source": "..."},
        {"kind": "AsCast", "description": "...", "source": "..."}
      ],
      "annealing[Temp]": [
        {
          "kind": "Annealing",
          "temperature": {"value": "[Temp]", "unit": "celsius"},
          "source": "..."
        }
      ]
    },
    "descriptions": [
      {
        "kinds": ["vickers_hardness"],
        "method": "VickersHardnessTest",
        "desc": "The microhardness (HV) of the alloys was measured with a Vickers hardness tester under a load of 500 gf"
      },
      {
        "kinds": ["Grinding"],
        "desc": "performed on a grinding wheel"
      }
    ],
    "output_materials": [
      {
        "process": "elements->creation",
        "name": "materialA",
        "measurements": [
          {"_type": "composition", "composition": "MgFeNi"},
          {
            "_type": "measurement",
            "kind": "vickers_hardness",
            "value": 321.0,
            "unit": "HV",
            "uncertainty": 7.0,
            "source": "..."
          },
          {
            "_type": "measurement",
            "kind": "yield_strength_tension",
            "value": 450.0,
            "unit": "MegaPascal",
            "measurement_statistic": "mean",
            "source": "..."
          },
          {
            "_type": "group_measurements",
            "kind": "grain_size",
            "unit": "micrometer",
            "values": [
              {"statistic": "lower", "value": 5},
              {"statistic": "upper", "value": 50}
            ]
          },
          {
            "_type": "lattice_param",
            "lattice": {"type": "cubic", "a": 3.208},
            "struct": "BCC",
            "source": "..."
          },
          {
            "_type": "configuration",
            "name": "dendrite",
            "tags": ["Dendrite"],
            "measurements": [
              {
                "_type": "composition",
                "composition": {"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9},
                "method": "EDS",
                "source": "..."
              }
            ]
          },
          {
            "_type": "configuration",
            "name": "FCC matrix",
            "struct": "FCC",
            "tags": ["Matrix"],
            "measurements": [
              {
                "_type": "measurement",
                "kind": "grain_size",
                "value": "~0.71",
                "unit": "micrometer"
              }
            ]
          },
          {
            "_type": "configuration",
            "name": "B2 precipitates",
            "struct": "B2",
            "tags": ["Precipitate", "Intragranular"],
            "within": "FCC matrix",
            "measurements": [
              {
                "_type": "group_measurements",
                "kind": "grain_size",
                "unit": "nanometer",
                "values": [
                  {"statistic": "lower", "value": 50},
                  {"statistic": "upper", "value": 180}
                ]
              }
            ]
          }
        ]
      },
      {
        "process": "materialA->annealing[Temp=10]",
        "name": "materialB",
        "measurements": [
          {"_type": "composition", "composition": "MgFeNi"},
          {
            "_type": "measurement",
            "kind": "vickers_hardness",
            "value": 350.0,
            "unit": "HV",
            "uncertainty": 7.0,
            "source": "..."
          }
        ]
      }
    ]
  }
]
```

How to write each experiment object and fields to populate:
1) "raw_materials" (required): map each initial input name (e.g. "elements" or "powders") to a raw material object.
   - "kind": one of the RawMaterialKind values (usually "Ingot", "Powder", or "Unspecified").
   - Populate "description" and "source" whenever the paper states purity, supplier, or precursor details.
2) "synthesis_groups" (required): an object mapping named synthesis stages to arrays of process event objects.
   - Use reusable stages and process variables when appropriate (e.g. "annealing[Temp]").
   - Each process event MUST include "kind" (a ProcessKind member name). Optionally include "temperature", "duration", "description", "source" when available. If you include temperature or duration, each MUST be a quantity object with BOTH "value" and "unit" (e.g. {"value": 700, "unit": "celsius"}). Omit the field entirely if unknown — never provide only "value" or only "unit".
   - Use "inputs" to declare which raw materials or named materials feed into a specific
     process event. Example: {"kind": "Mixing", "inputs": ["elements", "wc_additions"]}
   - Every raw material declared in "raw_materials" must be referenced somewhere — either as a
     comma-separated input in a material's "process" string or via a process event's "inputs".
   - "ArcMelting" and "InductionMelting" must always be immediately followed by a casting step
     (e.g. "AsCast", "SuctionCasting", "DropCasting", "GravityCasting", "DirectionalSolidification", or "CastingUnspecified").
   - IMPORTANT: Every synthesis group you define MUST be referenced by at least one material's "process" string.
     Do not define groups that are not used.
   - IMPORTANT: If a group name contains a template variable like [Temp] (e.g. "annealing[Temp]"),
     that exact placeholder string "[Temp]" MUST appear as a value in at least one process event field
     within that group. For example: "temperature": {"value": "[Temp]", "unit": "celsius"}.
     Do NOT put the actual number in the group definition — the actual value goes in the material's
     process string (e.g. "process": "elements->annealing[Temp=700]").
   - Only include actual fabrication/processing steps in synthesis_groups.
     Do NOT put measurement methods, characterization techniques, or testing procedures here.
3) "output_materials" (required): array of material objects.
   - "process": use process notation such as "elements->creation" or "base->annealing[Temp=700]->quenching".
   - The first segment (before the first "->") is a comma-separated list of input raw materials
     or named materials. Use commas to combine multiple inputs: "elements,reinforcement->mixing->sintering".
   - Include "name" only if the paper names that material.
   - "measurements" must include at least one composition measurement ({"_type": "composition", "composition": "..."}).
   - Add ALL reported property measurements.
4) Measurements — each item in the "measurements" array must have a "_type" field:
   - "_type": "composition" — for composition. Include "composition" (formula string or element dict) and optionally "method".
   - "_type": "measurement" — for a single measurement. REQUIRED: "kind", "value", "unit" (all three must be present). Optional: "uncertainty", "measurement_method", "temperature", "pressure", "measurement_statistic".
   - "_type": "group_measurements" — for ranges (e.g. "5–50 μm"). REQUIRED: "kind", "unit", "values" (array of {"statistic": "lower"/"upper", "value": ...}). All three must be present.
   - "_type": "lattice_param" — for XRD lattice parameters. Include "lattice" ({"type": "cubic", "a": 3.208}), "struct" (e.g. "BCC").
   - "_type": "configuration" — for microstructural features. Include "name", "tags", and nested "measurements".
   - If uncertainty is reported (e.g. "450 +- 20"), set "value": 450.0 and "uncertainty": 20.0.
   - If temperature or pressure is tied to a measurement, set "temperature": {"value": ..., "unit": "celsius"}. Both "value" and "unit" are REQUIRED in any quantity object.
   - Assume room temperature is ~23 C when the paper says "room temperature".
   - Pay attention to how the paper qualifies numeric values:
     - Exact value: "value": 50.0
     - Approximate value: "value": "~50"
     - Greater than: "value": ">50"
     - Less than: "value": "<50"
     - Greater than or equal: "value": ">=50"
     - Less than or equal: "value": "<=50"
     - Much greater than: "value": ">>50"
     - Much less than: "value": "<<50"
   - When the paper explicitly states a value is a mean or average, set "measurement_statistic": "mean".
     Leave it out when the paper does not specify.
5) Lattice parameters (for XRD-determined crystal structure):
   - Use "_type": "lattice_param" with a "lattice" object. Required parameters depend on type:
     - "cubic": {"type": "cubic", "a": ...} (requires "a")
     - "hexagonal": {"type": "hexagonal", "a": ..., "c": ...} (requires "a" and "c")
     - "tetragonal": {"type": "tetragonal", "a": ..., "c": ...} (requires "a" and "c")
     - "orthorhombic": {"type": "orthorhombic", "a": ..., "b": ..., "c": ...} (requires "a", "b", and "c")
   - "struct": the crystal structure (e.g. "BCC", "FCC").
   - "phase_fraction": optionally a quantity object (with both "value" and "unit") for the phase fraction if reported.
   - "name": optional name for the phase (e.g. "BCC phase", "σ phase").
   - Include "source" noting where in the paper the data appears.
6) Configuration (for microstructural features):
   - Use "_type": "configuration" to describe dendrites, precipitates, phases, lamellae, or regions with distinct microstructure.
   - Do NOT use configuration merely to record where on the bulk material a measurement was taken.
   - "name": identifies the feature (e.g. "dendrite", "FCC matrix", "B2 precipitates").
   - "struct": crystal structure if known (e.g. "BCC", "FCC", "B2").
   - "tags": array of ConfigTag values (e.g. ["Dendrite"], ["Precipitate", "Intragranular"]).
   - "within": reference the "name" of another configuration in the same material for nesting.
     All precipitates MUST have a "within" field referencing the configuration they are contained in.
   - "measurements": array of measurements specific to this feature.
7) "descriptions" (optional): array of description group objects for recording contextual information about
   measurement methods and equipment, or process-related descriptions.
   - Use this for information about HOW measurements were performed (instruments, testing conditions).
   - "kinds": array of AlloyMeasurementKind, PhaseMeasurementKind, ProcessKind, or MeasurementMethod values.
   - "method": optional MeasurementMethod value (string).
   - "desc": free-text description.
   - Example:
     ```json
     {"kinds": ["vickers_hardness"], "method": "VickersHardnessTest",
      "desc": "Microhardness measured with Vickers hardness tester at 500 gf load"}
     ```

Available string values for JSON fields:
- Measurement "_type" values: "composition", "measurement", "group_measurements", "lattice_param", "configuration"
- AlloyMeasurementKind values (for "kind" field): "vickers_hardness", "berkovich_hardness", "pugh_ductility_ratio", "density", "yield_strength_tension", "ultimate_strain_tension", "ultimate_tensile_strength", "fracture_strain_tension", "fracture_strength_tension", "strain_hardening_exponent_tension", "poissons_ratio_tension", "fracture_energy_tension", "true_stress_tension", "yield_strength_compression", "ultimate_strain_compression", "ultimate_compressive_strength", "fracture_strain_compression", "fracture_strength_compression", "strain_hardening_exponent_compression", "poissons_ratio_compression", "fracture_energy_compression", "true_stress_compression", "elastic_limit_compression", "elastic_limit_tension", "youngs_modulus", "fracture_toughness", "work_of_fracture", "crystallite_size", "lattice_strain", "melting_point", "solidus", "liquidus"
- PhaseMeasurementKind values (for Configuration/GlobalLatticeParam measurements): "volume_fraction", "length", "grain_size", "phase_size"
- ProcessKind values: "Mixing", "MechanicalAlloying", "PlanetaryMilling", "GasAtomization", "ArcMelting", "InductionMelting", "CastingUnspecified", "AsCast", "GravityCasting", "DropCasting", "SuctionCasting", "DirectionalSolidification", "SparkPlasmaSintering", "HotPressingSintering", "VacuumFurnace", "Homogenization", "Annealing", "NonIsothermalAnnealing", "IsothermalHolding", "WaterQuenching", "SolutionHeatTreatment", "HotExtrusion", "HotRolling", "ColdRolling", "CrossRolling", "ColdForging", "Press", "FrictionStirProcessing", "ElectricalDischargeMachining", "Cut", "Grinding", "Polishing", "Etching", "AquaRegia", "SandBlasting", "Degreased", "UltrasonicBath", "AirDrying"
- RawMaterialKind values: "Ingot", "Powder", "Plate", "Unspecified", "Other"
- CrysStruct values: "FCC", "BCC", "HCP", "DHCP", "Diamond", "L12", "L10", "B2", "D019", "D03", "Heusler", "Rocksalt", "Zincblende", "C14", "C15", "Perovskite", "Amorphous", "Unknown"
- ConfigTag values: "Dendrite", "Interdendritic", "Equiaxed", "Columnar", "Eutectic", "Coring", "Lath", "Martensite", "Acicular", "Lamellar", "Widmanstatten", "Matrix", "Precipitate", "Intragranular", "Intergranular", "Segregation", "Twin", "Subgrain", "Structure", "Unknown"
- MeasurementStatistic values: "mean", "median", "lower", "upper", "percentile"
- Unit strings: "HV", "GigaPascal", "MegaPascal", "micrometer", "nanometer", "gram_per_cm3", "percent", "dimensionless", "celsius", "kelvin", "atm"
  - You can also use standard unit abbreviations: "GPa", "MPa", "um", "nm", "mm", etc.
- Composition: use a formula string (e.g. "CoCrFeNi") or an element dict (e.g. {"Co": 25, "Cr": 25, "Fe": 25, "Ni": 25})
- Lattice types: "cubic", "hexagonal", "tetragonal", "orthorhombic"
- Description group: object with "kinds", "method", "desc"
- MeasurementMethod values (for "measurement_method" field): "XRD", "DSC", "TensileTest", "CompressionTest", "VickersHardnessTest", "NanoindentTest", "ArchimedesMethod", "OpticalMicroscope", "SEM", "TEM", "STEM", "EBSD", "UniversalTestingMachine", "ResonanceUltrasoundSpectroscopy", "FractureToughnessTest", "Balance", "EDS", "TEM_EDS", "WDS", "EPMA", "LIBS", "ED_XRF", "WD_XRF", "Spark_OES", "ICP_OES", "ICP_MS", "Unspecified"
- Composition helpers: use "_helper" objects (see below) instead of formula strings when needed
- Omit fields that are null/not applicable — do not include them with null values.

Composition helper objects (use these instead of formula strings when needed):

1. Balance composition — for "balance notation" (e.g. Ti-6Al-4V):
   ```json
   {"_helper": "balance_composition", "main_element": "Ti", "additions": {"Al": 6, "V": 4}}
   ```
   Ti is the balance element (90 wt%), Al is 6 wt%, V is 4 wt%.

2. From weight dict — create composition from weight percentages:
   ```json
   {"_helper": "from_weight_dict", "weights": {"Ni": 60, "Co": 20, "Cr": 20}}
   ```

3. Weight additions — add X wt% of a mix to a base alloy:
   ```json
   {"_helper": "weight_additions", "base": "NbTaTiZr", "additions_weights": {"Mo": 50, "W": 50}, "fraction": 0.05}
   ```
   Adds 5 wt% of a 50/50 Mo/W mix to equiatomic NbTaTiZr.
   "fraction" is a decimal: 5 wt% = 0.05, 2.5 wt% = 0.025.

Use these helpers inside the "composition" field of a composition measurement:
```json
{"_type": "composition", "composition": {"_helper": "balance_composition", "main_element": "Fe", "additions": {"Cr": 20}}}
```

Composition formatting guidance:
- Use plain formulas for atomic-fraction style entries (e.g. "Nb0.25Ta0.25Ti0.25Zr0.25").
- Never append text like "(at.%)" or "(wt.%)" inside composition formula strings.
"""

# %% Match Flat Prompt
# Forward matching: given a paper and 19 redacted flat summaries, pick the matching set.
# Uses real data from the dataset (first paper: doi_10_1016__j_proeng_2012_03_043).
MATCH_FLAT_PROMPT = """
You are given a scientific paper and 19 redacted experiment summaries (labeled Set 1 through Set 19). Each summary describes the structural fingerprint of the experiments extracted from one of 19 papers. Exactly one summary corresponds to this paper.

Your task: determine which set matches this paper based on structural clues only (counts of raw materials, output materials, measurements, process steps, and their relationships).

Respond with a JSON object: {"reason": "<brief explanation of why you chose this set>", "match": N} where N is the set number (1-19).


--- REDACTED EXPERIMENT SUMMARIES ---

### Set 1
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 5
  raw_material_1 -> (2 synthesis steps) -> material_1:
    1 composition, 0 property measurements, 1 configuration (1 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_2:
    1 composition, 3 property measurements, 2 configuration (8 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_3:
    1 composition, 1 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_4:
    1 composition, 1 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_5:
    1 composition, 3 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice


...

### Set 19
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 7
  raw_material_1 -> (3 synthesis steps) -> material_1:
    1 composition, 2 property measurements, 4 configuration (1 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_2:
    1 composition, 2 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_3:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_4:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_5:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_6:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_7:
    1 composition, 1 property measurements, 2 configuration (1 nested measurements), 0 lattice, 0 global lattice


--- PAPER TEXT ---

<paper_text>
"""

# %% Match Graph Prompt
# Same template as match flat — the difference is in the redacted summaries (graph vs flat).
# Uses real data from the dataset (first paper: doi_10_1016__j_proeng_2012_03_043).
MATCH_GRAPH_PROMPT = """
You are given a scientific paper and 19 redacted experiment summaries (labeled Set 1 through Set 19). Each summary describes the structural fingerprint of the experiments extracted from one of 19 papers. Exactly one summary corresponds to this paper.

Your task: determine which set matches this paper based on structural clues only (counts of raw materials, output materials, measurements, process steps, and their relationships).

Respond with a JSON object: {"reason": "<brief explanation of why you chose this set>", "match": N} where N is the set number (1-19).


--- REDACTED EXPERIMENT SUMMARIES ---

### Set 1
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 5
  raw_material_1 -> (2 synthesis steps) -> material_1:
    1 composition, 0 property measurements, 1 configuration (1 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_2:
    1 composition, 3 property measurements, 2 configuration (8 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_3:
    1 composition, 1 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_4:
    1 composition, 1 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_5:
    1 composition, 3 property measurements, 2 configuration (7 nested measurements), 0 lattice, 0 global lattice


...

### Set 19
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 7
  raw_material_1 -> (3 synthesis steps) -> material_1:
    1 composition, 2 property measurements, 4 configuration (1 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_2:
    1 composition, 2 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_3:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_4:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_5:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_6:
    1 composition, 1 property measurements, 0 configuration, 0 lattice, 0 global lattice
  raw_material_1 -> (3 synthesis steps) -> material_7:
    1 composition, 1 property measurements, 2 configuration (1 nested measurements), 0 lattice, 0 global lattice


--- PAPER TEXT ---

<paper_text>
"""

# %% Flat Redaction Example
# Example output of redact_experiments_flat() for the first paper in the dataset (doi_10_1016__j_proeng_2012_03_043).
REDACT_FLAT_EXAMPLE = """
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 4
  raw_material_1 -> (2 synthesis steps) -> material_1:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_2:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_3:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_4:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
"""

# %% Graph Redaction Example
# Example output of redact_experiments_graph() for the first paper in the dataset (doi_10_1016__j_proeng_2012_03_043).
REDACT_GRAPH_EXAMPLE = """
Experiment 1:
  Raw materials: raw_material_1
  Output materials: 4
  raw_material_1 -> (2 synthesis steps) -> material_1:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_2:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_3:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
  raw_material_1 -> (2 synthesis steps) -> material_4:
    1 composition, 2 property measurements, 1 configuration (0 nested measurements), 0 lattice, 0 global lattice
"""

# %% Property Extraction Prompt: Ultimate tensile strength (UTS)
# Single-property zero-shot extraction prompt for ultimate_tensile_strength (MPa)
PROPERTY_PROMPT_ULTIMATE_TENSILE_STRENGTH = """
Extract all Ultimate tensile strength (UTS) values of alloys/materials that the authors physically synthesized in this paper. Return values in MPa.

We are only interested in measurements of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Values mentioned in passing from other studies or references
- Values from computational/theoretical predictions
- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall material-level values.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return a JSON array of numeric values. Only include the numeric values, no units or labels.
If there are no values for this property, return an empty array.
If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0.
"""

# %% Property Extraction Prompt: Ultimate compressive strength (UCS)
# Single-property zero-shot extraction prompt for ultimate_compressive_strength (MPa)
PROPERTY_PROMPT_ULTIMATE_COMPRESSIVE_STRENGTH = """
Extract all Ultimate compressive strength (UCS) values of alloys/materials that the authors physically synthesized in this paper. Return values in MPa.

We are only interested in measurements of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Values mentioned in passing from other studies or references
- Values from computational/theoretical predictions
- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall material-level values.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return a JSON array of numeric values. Only include the numeric values, no units or labels.
If there are no values for this property, return an empty array.
If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0.
"""

# %% Property Extraction Prompt: Fracture strain in tension (elongation at fracture)
# Single-property zero-shot extraction prompt for fracture_strain_tension (%)
PROPERTY_PROMPT_FRACTURE_STRAIN_TENSION = """
Extract all Fracture strain in tension (elongation at fracture) values of alloys/materials that the authors physically synthesized in this paper. Return values in %.

We are only interested in measurements of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Values mentioned in passing from other studies or references
- Values from computational/theoretical predictions
- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall material-level values.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return a JSON array of numeric values. Only include the numeric values, no units or labels.
If there are no values for this property, return an empty array.
If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0.
"""

# %% Property Extraction Prompt: Fracture strain in compression
# Single-property zero-shot extraction prompt for fracture_strain_compression (%)
PROPERTY_PROMPT_FRACTURE_STRAIN_COMPRESSION = """
Extract all Fracture strain in compression values of alloys/materials that the authors physically synthesized in this paper. Return values in %.

We are only interested in measurements of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Values mentioned in passing from other studies or references
- Values from computational/theoretical predictions
- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall material-level values.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return a JSON array of numeric values. Only include the numeric values, no units or labels.
If there are no values for this property, return an empty array.
If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0.
"""

# %% Property Extraction Prompt: Vickers hardness
# Single-property zero-shot extraction prompt for vickers_hardness (HV)
PROPERTY_PROMPT_VICKERS_HARDNESS = """
Extract all Vickers hardness values of alloys/materials that the authors physically synthesized in this paper. Return values in HV.

We are only interested in measurements of alloys/materials that the authors physically made (synthesized) in their lab.
Do NOT include:
- Values mentioned in passing from other studies or references
- Values from computational/theoretical predictions
- Values of individual phases within a material (e.g. dendrite vs inter-dendrite regions)
Only include the overall material-level values.

Note: You only have access to the text of the paper. Images, figures, and tables rendered as images are not available, so rely solely on the textual content.

Return a JSON array of numeric values. Only include the numeric values, no units or labels.
If there are no values for this property, return an empty array.
If a value exists for some materials, but is missing from others, just include the ones that exist, don't use filler values like -1 or 0.
"""
