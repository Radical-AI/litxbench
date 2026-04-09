# %% [markdown]
# Generate rendered LLM prompts from source code.
#
# Run: uv run paper/generate_prompts.py
#
# Produces paper/prompts_llm_gen.py with the exact text sent to the LLM.
# This is more reliable than maintaining static strings because the prompts
# are computed by calling the actual source functions.

# %%
from pathlib import Path

from scripts.paper.benchmarks.helpers.json_prompts import (
    available_types_json,
    composition_helpers_json,
    example_experiment_shape_json,
    field_instructions_json,
)
from scripts.paper.benchmarks.helpers.matching_helpers import (
    build_matching_prompt,
    prepare_shuffled_sets,
    redact_experiments_flat,
    redact_experiments_graph,
)
from scripts.paper.benchmarks.helpers.prompts import (
    available_names,
    composition_helpers,
    example_experiment_shape,
    field_instructions,
    normalize_function,
    scope_rules,
)
from scripts.paper.benchmarks.tasks.property_zero_shot import (
    PROPERTY_DEFS,
    _build_property_prompt,
)

# ---------------------------------------------------------------------------
# Indent conversion: 4-space -> 2-space
# ---------------------------------------------------------------------------


def _truncate_sections(text: str, header_prefix: str) -> str:
    """Keep only the first and last ### sections, replacing the middle with '...'."""
    import re

    # Split on ### headers matching the prefix (e.g. "### Set " or "### Paper ")
    pattern = rf"(### {header_prefix}\d+)"
    parts = re.split(pattern, text)
    # parts alternates: [before, header1, body1, header2, body2, ...]
    # Collect (header, body) pairs
    sections = []
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((header, body))

    if len(sections) <= 2:
        return text

    before = parts[0]
    first = sections[0][0] + sections[0][1]
    last = sections[-1][0] + sections[-1][1]
    return before + first + "\n...\n\n" + last


def _halve_indent(text: str) -> str:
    """Convert leading whitespace: n spaces -> n//2 spaces."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip(" ")
        n = len(line) - len(stripped)
        result.append(" " * (n // 2) + stripped)
    return "\n".join(result)


# ---------------------------------------------------------------------------
# Composition prompt (inlined to avoid heavy imports from composition_zero_shot)
# ---------------------------------------------------------------------------


def _composition_scope_rules() -> str:
    return (
        "We are only interested in the compositions of alloys/materials that the authors physically "
        "made (synthesized) in their lab.\n"
        "Do NOT include:\n"
        "- Compositions mentioned in passing from other studies or references\n"
        "- Compositions from computational/theoretical predictions\n"
        "- Compositions of raw materials or precursors (e.g. pure elements)\n"
        "- Compositions of individual phases within a material (e.g. dendrite vs inter-dendrite regions)\n"
        "Only include the overall composition of each material the authors created.\n\n"
        "IMPORTANT: For each material, report only one composition — the one measured by the "
        "highest-resolution analytical technique available. Prefer analytically measured "
        "compositions over nominal/intended ones. The priority order from best to worst is:\n"
        "ICP-MS > ICP-OES > WD-XRF > EPMA > WDS > ED-XRF > Spark-OES > EDS > LIBS > nominal/Balance\n"
        "For example, if a paper reports both a nominal composition and an EDS-measured composition "
        "for the same material, use the EDS-measured one. If it reports both EDS and XRF for the "
        "same material, use the XRF measurement.\n\n"
        "Note: You only have access to the text of the paper. Images, figures, and tables "
        "rendered as images are not available, so rely solely on the textual content."
    )


def _composition_available_names(include_helpers: bool = True) -> str:
    text = """\
Available names in runtime:
- `Composition` (from `pymatgen.core`) — use to create composition objects
- `Composition("MgFeNi")` — from formula string (atomic ratio style)
- `Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20})` — from weight-percent dictionary"""
    if include_helpers:
        text += "\n- Composition helper functions: `balance_composition`, `composition_with_weight_additions`"
    return text


def _build_string_prompt() -> str:
    return (
        "Extract all compositions of alloys/materials that the authors physically "
        "synthesized in this paper.\n\n" + _composition_scope_rules() + "\n\n"
        "Return one composition formula per line inside a fenced code block.\n"
        "Each formula must be a valid chemical formula parseable by pymatgen's "
        "`Composition()` constructor.\n"
        "Use standard chemical formula notation (e.g. atomic ratio style).\n\n"
        "For weight-percent compositions, convert to the equivalent atomic-ratio "
        "formula.\n\n"
        "Example:\n"
        "```\n"
        "Al0.5CoCrFeNi\n"
        "MgFeNi\n"
        "Fe2O3\n"
        "```\n"
    )


def _build_code_prompt(include_helpers: bool) -> str:
    example_lines = [
        '    Composition("MgFeNi"),',
        '    Composition("Al0.5CoCrFeNi"),',
        '    Composition.from_weight_dict({"Ni": 60, "Co": 20, "Cr": 20}),',
    ]
    if include_helpers:
        example_lines.append('    balance_composition("Ti", {"Al": 6, "V": 4}),')

    parts = [
        "Extract all compositions of alloys/materials that the authors physically synthesized in this paper.\n\n",
        _composition_scope_rules(),
        "\n\n",
        "Return exactly one Python fenced code block and nothing else.\n",
        "The code must set a `result` variable to a `list[Composition]`.\n",
        "Each entry should be a `pymatgen.core.Composition` object representing one alloy the authors made.\n\n",
        "Example:\n",
        "```python\n",
        "result = [\n",
        "\n".join(example_lines),
        "\n]\n",
        "```\n\n",
        _composition_available_names(include_helpers),
    ]
    if include_helpers:
        parts.extend(["\n\n", composition_helpers()])
    return "".join(parts)


# ---------------------------------------------------------------------------
# Render all prompts
# ---------------------------------------------------------------------------


def _escape_triple_quotes(s: str) -> str:
    """Escape triple quotes so the string can be embedded in triple-quoted literals."""
    return s.replace("\\", "\\\\").replace('"""', '\\"""')


def _make_var(name: str, value: str) -> str:
    """Format a Python variable assignment with a triple-quoted string."""
    escaped = _escape_triple_quotes(value)
    return f'{name} = """\n{escaped}\n"""'


def generate() -> str:
    # --- Render each section ---
    rendered_scope = scope_rules()

    rendered_example = _halve_indent(
        example_experiment_shape(
            include_source=True,
            include_descriptions=True,
            linear=False,
        )
    )

    rendered_field = _halve_indent(
        field_instructions(
            include_source=True,
            include_descriptions=True,
            linear=False,
        )
    )

    rendered_available = available_names(
        include_composition_helpers=True,
        include_normalize_function=False,
        include_descriptions=True,
    )

    rendered_comp_helpers = composition_helpers()

    rendered_normalize = _halve_indent(normalize_function())

    rendered_comp_prompt = _halve_indent(_build_code_prompt(include_helpers=True))

    rendered_comp_string_prompt = _build_string_prompt()

    # --- JSON prompt sections (from zero_shot_json.py) ---
    # JSON source already uses 2-space indent, no halving needed.
    rendered_example_json = example_experiment_shape_json(
        include_source=True,
        include_descriptions=True,
    )

    rendered_field_json = field_instructions_json(
        include_source=True,
        include_descriptions=True,
    )

    rendered_available_json = available_types_json(
        include_composition_helpers=True,
        include_descriptions=True,
    )

    rendered_comp_helpers_json = composition_helpers_json()

    # --- Full JSON extraction prompt (assembled as in zero_shot_json.py) ---
    full_extraction_json = "\n\n".join(
        [
            "Extract experiments from this paper.\n\n"
            + rendered_scope
            + "\n\n"
            + "Return a JSON fenced code block (```json ... ```) "
            + "containing an array of experiment objects.\n\n"
            + "Use this exact shape:\n\n"
            + rendered_example_json
            + "\n\n"
            + rendered_field_json
            + "\n\n"
            + rendered_available_json,
            rendered_comp_helpers_json,
        ]
    )

    # --- Matching prompts (from matching_helpers.py) ---
    # Use actual redacted data from the dataset (same seed as the real benchmark).
    from litxbench.litxalloy import papers as papers_dict

    flat_summaries, flat_gt = prepare_shuffled_sets(papers_dict, redact_experiments_flat)
    graph_summaries, graph_gt = prepare_shuffled_sets(papers_dict, redact_experiments_graph)

    # Pick the first DOI (alphabetically) as the example paper.
    first_doi = sorted(papers_dict.keys())[0]
    first_experiments = papers_dict[first_doi]

    rendered_match_flat = _truncate_sections(
        build_matching_prompt("<paper_text>", flat_summaries),
        "Set ",
    )
    rendered_match_graph = _truncate_sections(
        build_matching_prompt("<paper_text>", graph_summaries),
        "Set ",
    )

    # Show real redaction examples from the first paper.
    rendered_redact_flat_example = redact_experiments_flat(first_experiments)
    rendered_redact_graph_example = redact_experiments_graph(first_experiments)

    # --- Property extraction prompts (from property_zero_shot.py) ---
    rendered_property_prompts = {name: _build_property_prompt(prop_def) for name, prop_def in PROPERTY_DEFS.items()}

    # --- Full extraction prompt (assembled as in zero_shot.py) ---
    full_extraction = "\n\n".join(
        [
            "Extract experiments from this paper.\n\n"
            + rendered_scope
            + "\n\n"
            + "Return a Python fenced code block (```python ... ```) "
            + "containing a single expression that evaluates to a `list[Experiment]`.\n\n"
            + "Use this exact shape:\n\n"
            + rendered_example
            + "\n\n"
            + rendered_field
            + "\n\n"
            + rendered_available,
            rendered_comp_helpers,
        ]
    )

    # --- Build output file ---
    sections = [
        "# %% [markdown]",
        "# Auto-generated rendered prompts from source code.",
        "# Regenerate with: uv run paper/generate_prompts.py",
        "#",
        "# Each section below shows the exact text sent to the LLM at inference time.",
        "# Python code blocks in prompts use 2-space indentation.",
        "",
        "# %% J.0.3 Extraction Scope Prompt",
        _make_var("SCOPE_RULES", rendered_scope),
        "",
        "# %% J.0.1 Example Extraction Prompt",
        "# Configuration: include_source=True, include_descriptions=True, linear=False (with material names)",
        _make_var("EXAMPLE_EXPERIMENT_SHAPE", rendered_example),
        "",
        "# %% J.0.2 Extraction Template Instruction Prompt",
        "# Configuration: include_source=True, include_descriptions=True, linear=False",
        _make_var("FIELD_INSTRUCTIONS", rendered_field),
        "",
        "# %% Available Names in Runtime",
        "# Configuration: include_composition_helpers=True, include_normalize_function=False, include_descriptions=True",
        _make_var("AVAILABLE_NAMES", rendered_available),
        "",
        "# %% Composition Helpers",
        _make_var("COMPOSITION_HELPERS", rendered_comp_helpers),
        "",
        "# %% Normalize Function Prompt",
        _make_var("NORMALIZE_FUNCTION", rendered_normalize),
        "",
        "# %% J.0.4 Composition Extraction Task Prompt",
        "# Full prompt for composition-only extraction (code output mode, with helpers)",
        _make_var("COMPOSITION_PROMPT", rendered_comp_prompt),
        "",
        "# %% Composition Extraction Task Prompt (string output, no helpers)",
        _make_var("COMPOSITION_PROMPT_STRING", rendered_comp_string_prompt),
        "",
        "# %% Full Extraction Prompt (all sections assembled)",
        "# This is the complete prompt sent to the LLM for zero-shot experiment extraction.",
        _make_var("FULL_EXTRACTION_PROMPT", full_extraction),
        "",
        "# %% JSON Example Extraction Prompt",
        "# Configuration: include_source=True, include_descriptions=True",
        _make_var("EXAMPLE_EXPERIMENT_SHAPE_JSON", rendered_example_json),
        "",
        "# %% JSON Extraction Template Instruction Prompt",
        "# Configuration: include_source=True, include_descriptions=True",
        _make_var("FIELD_INSTRUCTIONS_JSON", rendered_field_json),
        "",
        "# %% JSON Available Types",
        "# Configuration: include_composition_helpers=True, include_descriptions=True",
        _make_var("AVAILABLE_TYPES_JSON", rendered_available_json),
        "",
        "# %% JSON Composition Helpers",
        _make_var("COMPOSITION_HELPERS_JSON", rendered_comp_helpers_json),
        "",
        "# %% Full JSON Extraction Prompt (all sections assembled)",
        "# This is the complete prompt sent to the LLM for zero-shot JSON experiment extraction.",
        _make_var("FULL_EXTRACTION_PROMPT_JSON", full_extraction_json),
        "",
        "# %% Match Flat Prompt",
        "# Forward matching: given a paper and 19 redacted flat summaries, pick the matching set.",
        f"# Uses real data from the dataset (first paper: {first_doi}).",
        _make_var("MATCH_FLAT_PROMPT", rendered_match_flat),
        "",
        "# %% Match Graph Prompt",
        "# Same template as match flat — the difference is in the redacted summaries (graph vs flat).",
        f"# Uses real data from the dataset (first paper: {first_doi}).",
        _make_var("MATCH_GRAPH_PROMPT", rendered_match_graph),
        "",
        "# %% Flat Redaction Example",
        f"# Example output of redact_experiments_flat() for the first paper in the dataset ({first_doi}).",
        _make_var("REDACT_FLAT_EXAMPLE", rendered_redact_flat_example),
        "",
        "# %% Graph Redaction Example",
        f"# Example output of redact_experiments_graph() for the first paper in the dataset ({first_doi}).",
        _make_var("REDACT_GRAPH_EXAMPLE", rendered_redact_graph_example),
        "",
    ]

    # --- Property extraction prompts ---
    for name, prompt_text in rendered_property_prompts.items():
        prop_def = PROPERTY_DEFS[name]
        sections.extend(
            [
                f"# %% Property Extraction Prompt: {prop_def.prompt_description}",
                f"# Single-property zero-shot extraction prompt for {name} ({prop_def.unit})",
                _make_var(f"PROPERTY_PROMPT_{name.upper()}", prompt_text),
                "",
            ]
        )

    return "\n".join(sections)


# %%
if __name__ == "__main__":
    output_path = Path(__file__).resolve().parent / "prompts_llm_gen.py"
    content = generate()
    output_path.write_text(content)
    print(f"Wrote {output_path}")
    print(f"  ({len(content)} bytes)")
