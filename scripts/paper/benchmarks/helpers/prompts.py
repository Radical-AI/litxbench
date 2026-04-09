"""Shared prompt sections for alloy experiment extraction benchmarks."""

import re
from dataclasses import dataclass

from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod, ProcessKind
from litxbench.core.extraction_utils import ROOM_TEMPERATURE
from litxbench.litxalloy.models import AlloyMeasurementKind, PhaseMeasurementKind

_COMPOSITION_HELPERS_AVAILABLE_LINE = (
    "- Composition helper functions: `composition_with_weight_additions`, `balance_composition`\n"
)
_NORMALIZE_AVAILABLE_LINE = "- Normalization helper: `normalize(val, val_in_paper, source=None)` — documents that a paper's terminology was interpreted as a standardized value\n"


@dataclass(frozen=True)
class PromptConfig:
    """Shared flags controlling which prompt sections to include."""

    include_composition_helpers: bool = True
    include_normalize_function: bool = False
    include_source: bool = False
    include_descriptions_instructions: bool = False


def scope_rules() -> str:
    """Rules limiting extraction to physical materials and measurements."""
    return (
        "We are only interested in materials the authors physically made in their lab.\n"
        "Extract ALL properties reported for those materials — mechanical, thermal, physical, microstructural, etc.\n"
        "Include properties derived from measurements (e.g. strain hardening exponent from a stress-strain curve, "
        "fracture toughness from a fracture test, Pugh ductility ratio from measured elastic constants).\n"
        "Exclude properties that are purely computed from composition or thermodynamic databases "
        "(e.g. CALPHAD/ThermoCalc predictions, DFT-computed values, rule-of-mixtures estimates with no experimental validation)."
    )


def example_experiment_shape(
    include_source: bool = True, include_descriptions: bool = False, *, linear: bool = False
) -> str:
    """Example Experiment(...) code block showing the required output shape.

    When *linear* is True the example omits material names and shows each material's
    process chain starting from raw materials (no inter-material references).
    """
    if linear:
        material_a_name = ""
        material_b_process = 'process="elements->creation->annealing[Temp=10]",'
        material_b_name = ""
    else:
        material_a_name = '\n                name="materialA",'
        material_b_process = 'process="materialA->annealing[Temp=10]",'
        material_b_name = '\n                name="materialB",'

    raw = f"""\
```python
[
    Experiment(
        raw_materials={{
            "elements": RawMaterial(
                kind=RawMaterialKind.Ingot,
                description="...",
                source="...",
            )
        }},
        synthesis_groups={{
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
        }},
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
                process="elements->creation",{material_a_name}
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
                        tags={{ConfigTag.Dendrite}},
                        measurements=[
                            CompMeasurement(
                                {{"Mo": 27.6, "Nb": 25.0, "Ta": 31.5, "V": 15.9}},
                                method=MeasurementMethod.EDS,
                                source="...",
                            ),
                        ],
                    ),
                    # Nested configuration (precipitate within a phase):
                    Configuration(
                        name="FCC matrix",
                        struct=CrysStruct.FCC,
                        tags={{ConfigTag.Matrix}},
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
                        tags={{ConfigTag.Precipitate, ConfigTag.Intragranular}},
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
                {material_b_process}{material_b_name}
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
```"""
    if not include_source:
        # Remove standalone source="...", lines
        raw = re.sub(r'\n\s*source="\.\.\."\s*,', "", raw)
        # Remove inline , source="..." within a line
        raw = re.sub(r',\s*source="\.\.\."\s*', "", raw)
    if not include_descriptions:
        # Remove the descriptions=[...], block from the example.
        # Match 'descriptions=[' at 8-space indent through '],\n' at same indent level.
        raw = re.sub(r"\n {8}descriptions=\[.*?\n {8}\],\n", "\n", raw, flags=re.DOTALL)
    return raw


def field_instructions(include_source: bool = True, include_descriptions: bool = False, *, linear: bool = False) -> str:
    """Field-by-field instructions for writing each Experiment, including value qualifier rules.

    When *linear* is True, instructions require each material to describe its
    complete process chain from raw materials (no inter-material references).
    """
    _raw_material_detail = (
        "Populate `description` and `source` whenever the paper states purity, supplier, or precursor details."
        if include_source
        else "Populate `description` whenever the paper states purity, supplier, or precursor details."
    )
    _process_event_fields = (
        "Each `ProcessEvent` should include `kind` (a `ProcessKind` enum member), and include `temperature` (as `Quantity`, e.g. `Quantity(value=1200, unit=Celsius)`), `duration` (as `Quantity`, e.g. `Quantity(value=24, unit=ureg.hour)`), `description`, `source` when available."
        if include_source
        else "Each `ProcessEvent` should include `kind` (a `ProcessKind` enum member), and include `temperature` (as `Quantity`, e.g. `Quantity(value=1200, unit=Celsius)`), `duration` (as `Quantity`, e.g. `Quantity(value=24, unit=ureg.hour)`), `description` when available."
    )
    _inputs_feed = "raw materials" if linear else "raw materials or named materials"
    _process_examples = (
        '`"elements->creation"` or `"elements->creation->annealing[Temp=700]->quenching"`'
        if linear
        else '`"elements->creation"` or `"base->annealing[Temp=700]->quenching"`'
    )
    _first_segment = (
        "The first segment (before the first `->`) is a comma-separated list of input raw materials.\n"
        '     Use commas to combine multiple inputs: `"elements,reinforcement->mixing->sintering"`.\n'
        "   - Each material must describe its complete process chain starting from raw materials. Do not reference other materials by name."
        if linear
        else "The first segment (before the first `->`) is a comma-separated list of input raw materials\n"
        '     or named materials. Use commas to combine multiple inputs: `"elements,reinforcement->mixing->sintering"`.'
    )
    base = f"""\
How to write each Experiment and fields to populate:
1) `raw_materials` (required): map each initial input name (for example `"elements"` or `"powders"`) to `RawMaterial`.
   - Populate `kind` with `RawMaterialKind` (usually `Ingot`, `Powder`, or `Unspecified`).
   - {_raw_material_detail}
2) `synthesis_groups` (required): a dict of named synthesis stages to lists of `ProcessEvent`.
   - Use reusable stages and process variables when appropriate (for example `"annealing[Temp]"`).
   - {_process_event_fields}
   - Use `ProcessEvent.inputs` to declare which {_inputs_feed} feed into a specific
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
     {_process_examples}.
   - {_first_segment}
   - Include `Material.name` only if the paper names that material.
   - `Material.measurements` must include at least one `CompositionMeasurement`.
   - Add ALL reported property measurements with `Measurement(...)` using `AlloyMeasurementKind` members.
4) Measurements:
   - Use `Measurement(kind=AlloyMeasurementKind.<kind>, value=<number>, unit=<unit>)`.
   - If uncertainty is reported (e.g. "450 +- 20"), set `value=450.0` and `uncertainty=20.0`.
   - If temperature or pressure is tied to a measurement, set `temperature=Quantity(...)` or `pressure=Measurement(...)`.
   - Assume room temperature is {ROOM_TEMPERATURE.value} C when the paper says "room temperature" without a number.
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
{"   - Include `source` noting where in the paper the data appears.\n" if include_source else ""}\
6) Configuration (for microstructural features):
   - Use `Configuration` to describe microstructural features like dendrites, precipitates, phases, lamellae,
     or regions of interest with distinct microstructure (e.g. a Cr-rich region, an interdendritic zone).
   - Do NOT use Configuration merely to record where on the bulk material a measurement was taken.
     If the paper says "hardness at the center region was 210 HV", that is a material-level measurement —
     put it in `Material.measurements`, not inside a Configuration named "center region".
   - `name`: identifies the feature (e.g. `"dendrite"`, `"FCC matrix"`, `"B2 precipitates"`).
   - `struct`: crystal structure if known (e.g. `CrysStruct.BCC`, `CrysStruct.FCC`, `CrysStruct.B2`).
   - `tags`: categorize the feature using `ConfigTag` members (e.g. `{ConfigTag.Dendrite}`, `{ConfigTag.Precipitate, ConfigTag.Intragranular}`).
   - `within`: reference the `name` of another Configuration in the same material to indicate nesting
     (e.g. precipitates within a matrix phase). The referenced Configuration must exist in the same material.
     All precipitates MUST have a `within` field referencing the configuration they are contained in.
   - `measurements`: list of measurements specific to this feature — typically `CompMeasurement` (EDS composition),
     `Measurement` (grain size, phase fraction, etc. using `PhaseMeasurementKind`), or `LatticeMeasurement`."""
    if include_descriptions:
        base += """
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
     ```"""
    return base


def available_names(
    include_composition_helpers: bool = True,
    include_normalize_function: bool = False,
    include_descriptions: bool = False,
) -> str:
    """Runtime names available in the code execution environment."""
    kind_names = ", ".join(f"`{m.name}`" for m in AlloyMeasurementKind)
    phase_kind_names = ", ".join(f"`{m.name}`" for m in PhaseMeasurementKind)
    process_kind_names = ", ".join(f"`{m.name}`" for m in ProcessKind)
    crys_struct_names = ", ".join(f"`{m.name}`" for m in CrysStruct)
    config_tag_names = ", ".join(f"`{m.name}`" for m in ConfigTag)
    measurement_method_names = ", ".join(f"`{m.name}`" for m in MeasurementMethod)
    _description_line = "- Description group: `AlloyDescriptionGroup`\n" if include_descriptions else ""
    _measurement_method_line = f"- `MeasurementMethod` members: {measurement_method_names}\n"
    return f"""\
Available names in runtime:
- Core classes: `Experiment`, `Material`, `RawMaterial`, `RawMaterialKind`, `ProcessEvent`, `ProcessKind`, `Measurement`, `CompositionMeasurement`
- Microstructure classes: `GlobalLatticeParam`, `LatticeMeasurement`, `Configuration`
- Lattice constructor: `Lattice` (from `pymatgen.core.lattice`) — e.g. `Lattice.cubic(a)`, `Lattice.hexagonal(a, c)`
- Measurement statistics: `MeasurementStatistic`, `CoreMeasurementValue`
- Enums: `AlloyMeasurementKind`, `PhaseMeasurementKind`, `ProcessKind`, `CrysStruct`, `ConfigTag`, `MeasurementMethod`, `ValueQualifier`
- `AlloyMeasurementKind` members: {kind_names}
- `PhaseMeasurementKind` members (for Configuration/GlobalLatticeParam measurements): {phase_kind_names}
- `ProcessKind` members: {process_kind_names}
- `CrysStruct` members: {crys_struct_names}
- `ConfigTag` members: {config_tag_names}
- `MeasurementStatistic` members: `mean`, `median`, `lower`, `upper`, `percentile`
- Units registry: `ureg` (a pint `UnitRegistry` instance)
- Pre-defined units: `HV`, `GigaPascal`, `MegaPascal`, `Micrometer`, `Nanometer`, `gram_per_cm3`, `percent`, `dimensionless`, `Celsius`, `Kelvin`, `Atm`
- `ureg` supports accessing any standard pint unit as an attribute (e.g. `ureg.angstrom`, `ureg.joule`, `ureg.meter`).
- You can compose new units with arithmetic: `ureg.megapascal * ureg.meter ** 0.5`, `ureg.gram / ureg.cm ** 3`, `ureg.ampere / ureg.cm ** 2`.
- You can define entirely new units with `ureg.define("HV = 9.807 * megapascal = vickers_hardness")` if a unit is not already available.
- Composition parser: `Composition` (from `pymatgen`)
{_description_line}\
{_measurement_method_line}\
{_COMPOSITION_HELPERS_AVAILABLE_LINE if include_composition_helpers else ""}\
{_NORMALIZE_AVAILABLE_LINE if include_normalize_function else ""}\
{"- For weight-percent composition dictionaries, prefer `Composition.from_weight_dict(...)` when available in your environment" if include_composition_helpers else ""}"""


def composition_helpers() -> str:
    """Composition helper examples and formatting guidance."""
    return """\
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
- Never append text like `(at.%)` or `(wt.%)` inside composition formula strings."""


def normalize_function() -> str:
    """Explanation and examples for the normalize() helper."""
    return """\
Normalize function:
- `normalize(val, val_in_paper, source=None)` is a documentation wrapper that records when a paper's \
terminology differs from our standardized value. It returns `val` unchanged.
- Use it whenever the paper uses different terminology than our standardized enum values or process kind strings.
- `val`: the standardized/ground-truth value you want to use.
- `val_in_paper`: the exact term the paper used (as a string).
- `source`: optional string noting where in the paper the term appears.

When to use `normalize`:
- A measurement kind in the paper doesn't exactly match an `AlloyMeasurementKind` member name \
(e.g. the paper says "Yield Strength" but the measurement was done via compression, \
so the correct kind is `AlloyMeasurementKind.yield_strength_compression`).
- A process description in the paper is more specific than a `ProcessKind` member \
(e.g. the paper says "Vacuum Arc Melting" but the correct kind is `ProcessKind.ArcMelting`).

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
- If the paper's terminology already matches the standardized value exactly, just use the value directly \
(e.g. `kind=AlloyMeasurementKind.vickers_hardness` when the paper says "Vickers hardness")."""
