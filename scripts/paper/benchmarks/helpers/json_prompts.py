"""JSON-specific prompt sections for alloy experiment extraction benchmarks.

Parallels the Python-code prompts in ``prompts.py`` but asks the LLM to
produce JSON output instead.  Imports shared helpers (``PromptConfig``,
``scope_rules``) from ``prompts.py`` to avoid duplication.
"""

import re

from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod, ProcessKind, RawMaterialKind
from litxbench.core.extraction_utils import ROOM_TEMPERATURE
from litxbench.litxalloy.models import AlloyMeasurementKind, PhaseMeasurementKind
from scripts.paper.benchmarks.helpers.prompts import PromptConfig  # noqa: F401 — re-export


def example_experiment_shape_json(include_source: bool = True, include_descriptions: bool = False) -> str:
    """Example JSON block showing the required output shape."""
    raw = """\
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
```"""
    if not include_source:
        # Remove lines that are just "source": "..." (with optional leading comma)
        raw = re.sub(r',\n(\s*)"source":\s*"\.\.\."\n', "\n", raw)
        # Remove "source": "..." when it's the last field before a closing brace (no trailing comma)
        raw = re.sub(r',\n(\s*)"source":\s*"\.\.\."\s*(?=\n\s*[}\]])', "", raw)
        # Remove inline , "source": "..." in same-line objects
        raw = re.sub(r',\s*"source":\s*"\.\.\."\s*', "", raw)
    if not include_descriptions:
        # Remove the descriptions block. It sits between synthesis_groups and output_materials.
        # We need to preserve the comma between the surrounding fields.
        # Match: ,\n    "descriptions": [...],\n  —  replace with just ,\n
        raw = re.sub(r',\n(\s*)"descriptions":\s*\[.*?\n\1\],?\n', ",\n", raw, flags=re.DOTALL)
    return raw


def field_instructions_json(include_source: bool = True, include_descriptions: bool = False) -> str:
    """Field-by-field instructions for writing each experiment as JSON."""
    _raw_material_detail = (
        'Populate "description" and "source" whenever the paper states purity, supplier, or precursor details.'
        if include_source
        else 'Populate "description" whenever the paper states purity, supplier, or precursor details.'
    )
    _process_event_fields = (
        'Each process event MUST include "kind" (a ProcessKind member name). Optionally include "temperature", "duration", "description", "source" when available. '
        'If you include temperature or duration, each MUST be a quantity object with BOTH "value" and "unit" (e.g. {"value": 700, "unit": "celsius"}). '
        'Omit the field entirely if unknown — never provide only "value" or only "unit".'
        if include_source
        else 'Each process event MUST include "kind" (a ProcessKind member name). Optionally include "temperature", "duration", "description" when available. '
        'If you include temperature or duration, each MUST be a quantity object with BOTH "value" and "unit" (e.g. {"value": 700, "unit": "celsius"}). '
        'Omit the field entirely if unknown — never provide only "value" or only "unit".'
    )
    base = f"""\
How to write each experiment object and fields to populate:
1) "raw_materials" (required): map each initial input name (e.g. "elements" or "powders") to a raw material object.
   - "kind": one of the RawMaterialKind values (usually "Ingot", "Powder", or "Unspecified").
   - {_raw_material_detail}
2) "synthesis_groups" (required): an object mapping named synthesis stages to arrays of process event objects.
   - Use reusable stages and process variables when appropriate (e.g. "annealing[Temp]").
   - {_process_event_fields}
   - Use "inputs" to declare which raw materials or named materials feed into a specific
     process event. Example: {{"kind": "Mixing", "inputs": ["elements", "wc_additions"]}}
   - Every raw material declared in "raw_materials" must be referenced somewhere — either as a
     comma-separated input in a material's "process" string or via a process event's "inputs".
   - "ArcMelting" and "InductionMelting" must always be immediately followed by a casting step
     (e.g. "AsCast", "SuctionCasting", "DropCasting", "GravityCasting", "DirectionalSolidification", or "CastingUnspecified").
   - IMPORTANT: Every synthesis group you define MUST be referenced by at least one material's "process" string.
     Do not define groups that are not used.
   - IMPORTANT: If a group name contains a template variable like [Temp] (e.g. "annealing[Temp]"),
     that exact placeholder string "[Temp]" MUST appear as a value in at least one process event field
     within that group. For example: "temperature": {{"value": "[Temp]", "unit": "celsius"}}.
     Do NOT put the actual number in the group definition — the actual value goes in the material's
     process string (e.g. "process": "elements->annealing[Temp=700]").
   - Only include actual fabrication/processing steps in synthesis_groups.
     Do NOT put measurement methods, characterization techniques, or testing procedures here.
3) "output_materials" (required): array of material objects.
   - "process": use process notation such as "elements->creation" or "base->annealing[Temp=700]->quenching".
   - The first segment (before the first "->") is a comma-separated list of input raw materials
     or named materials. Use commas to combine multiple inputs: "elements,reinforcement->mixing->sintering".
   - Include "name" only if the paper names that material.
   - "measurements" must include at least one composition measurement ({{"_type": "composition", "composition": "..."}}).
   - Add ALL reported property measurements.
4) Measurements — each item in the "measurements" array must have a "_type" field:
   - "_type": "composition" — for composition. Include "composition" (formula string or element dict) and optionally "method".
   - "_type": "measurement" — for a single measurement. REQUIRED: "kind", "value", "unit" (all three must be present). Optional: "uncertainty", "measurement_method", "temperature", "pressure", "measurement_statistic".
   - "_type": "group_measurements" — for ranges (e.g. "5–50 μm"). REQUIRED: "kind", "unit", "values" (array of {{"statistic": "lower"/"upper", "value": ...}}). All three must be present.
   - "_type": "lattice_param" — for XRD lattice parameters. Include "lattice" ({{"type": "cubic", "a": 3.208}}), "struct" (e.g. "BCC").
   - "_type": "configuration" — for microstructural features. Include "name", "tags", and nested "measurements".
   - If uncertainty is reported (e.g. "450 +- 20"), set "value": 450.0 and "uncertainty": 20.0.
   - If temperature or pressure is tied to a measurement, set "temperature": {{"value": ..., "unit": "celsius"}}. Both "value" and "unit" are REQUIRED in any quantity object.
   - Assume room temperature is {ROOM_TEMPERATURE.value} C when the paper says "room temperature".
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
     - "cubic": {{"type": "cubic", "a": ...}} (requires "a")
     - "hexagonal": {{"type": "hexagonal", "a": ..., "c": ...}} (requires "a" and "c")
     - "tetragonal": {{"type": "tetragonal", "a": ..., "c": ...}} (requires "a" and "c")
     - "orthorhombic": {{"type": "orthorhombic", "a": ..., "b": ..., "c": ...}} (requires "a", "b", and "c")
   - "struct": the crystal structure (e.g. "BCC", "FCC").
   - "phase_fraction": optionally a quantity object (with both "value" and "unit") for the phase fraction if reported.
   - "name": optional name for the phase (e.g. "BCC phase", "σ phase").
{'   - Include "source" noting where in the paper the data appears.\n' if include_source else ""}\
6) Configuration (for microstructural features):
   - Use "_type": "configuration" to describe dendrites, precipitates, phases, lamellae, or regions with distinct microstructure.
   - Do NOT use configuration merely to record where on the bulk material a measurement was taken.
   - "name": identifies the feature (e.g. "dendrite", "FCC matrix", "B2 precipitates").
   - "struct": crystal structure if known (e.g. "BCC", "FCC", "B2").
   - "tags": array of ConfigTag values (e.g. ["Dendrite"], ["Precipitate", "Intragranular"]).
   - "within": reference the "name" of another configuration in the same material for nesting.
     All precipitates MUST have a "within" field referencing the configuration they are contained in.
   - "measurements": array of measurements specific to this feature."""
    if include_descriptions:
        base += """
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
     ```"""
    return base


def available_types_json(
    include_composition_helpers: bool = True,
    include_descriptions: bool = False,
) -> str:
    """Lists valid string values for each enum and type used in the JSON schema."""
    kind_names = ", ".join(f'"{m.name}"' for m in AlloyMeasurementKind)
    phase_kind_names = ", ".join(f'"{m.name}"' for m in PhaseMeasurementKind)
    process_kind_names = ", ".join(f'"{m.name}"' for m in ProcessKind)
    crys_struct_names = ", ".join(f'"{m.name}"' for m in CrysStruct)
    config_tag_names = ", ".join(f'"{m.name}"' for m in ConfigTag)
    measurement_method_names = ", ".join(f'"{m.name}"' for m in MeasurementMethod)
    raw_material_kind_names = ", ".join(f'"{m.name}"' for m in RawMaterialKind)
    measurement_statistic_names = '"mean", "median", "lower", "upper", "percentile"'
    _description_line = '- Description group: object with "kinds", "method", "desc"\n' if include_descriptions else ""
    _measurement_method_line = (
        f'- MeasurementMethod values (for "measurement_method" field): {measurement_method_names}\n'
    )
    _comp_helpers_line = (
        '- Composition helpers: use "_helper" objects (see below) instead of formula strings when needed\n'
        if include_composition_helpers
        else ""
    )
    return f"""\
Available string values for JSON fields:
- Measurement "_type" values: "composition", "measurement", "group_measurements", "lattice_param", "configuration"
- AlloyMeasurementKind values (for "kind" field): {kind_names}
- PhaseMeasurementKind values (for Configuration/GlobalLatticeParam measurements): {phase_kind_names}
- ProcessKind values: {process_kind_names}
- RawMaterialKind values: {raw_material_kind_names}
- CrysStruct values: {crys_struct_names}
- ConfigTag values: {config_tag_names}
- MeasurementStatistic values: {measurement_statistic_names}
- Unit strings: "HV", "GigaPascal", "MegaPascal", "micrometer", "nanometer", "gram_per_cm3", "percent", "dimensionless", "celsius", "kelvin", "atm"
  - You can also use standard unit abbreviations: "GPa", "MPa", "um", "nm", "mm", etc.
- Composition: use a formula string (e.g. "CoCrFeNi") or an element dict (e.g. {{"Co": 25, "Cr": 25, "Fe": 25, "Ni": 25}})
- Lattice types: "cubic", "hexagonal", "tetragonal", "orthorhombic"
{_description_line}\
{_measurement_method_line}\
{_comp_helpers_line}\
- Omit fields that are null/not applicable — do not include them with null values."""


def composition_helpers_json() -> str:
    """Explains the _helper tagged objects for composition helpers in JSON."""
    return """\
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
- Never append text like "(at.%)" or "(wt.%)" inside composition formula strings."""
