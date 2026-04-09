"""Diff-style visualization for experiment comparisons.

This module provides side-by-side diff views for comparing extracted and target experiments,
including the Myers diff algorithm for line alignment.
"""

from __future__ import annotations

from dataclasses import dataclass

from litxbench.core.eval import (
    ConfigurationMatchResult,
    ExperimentComparisonResult,
    ProcessEventAlignmentResult,
)
from litxbench.core.models import ProcessEvent, Quantity
from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    CompMeasurement,
    Configuration,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
)


@dataclass
class DiffRow:
    """Represents a single row in a side-by-side diff view."""

    marker: str
    extracted_text: str
    target_text: str


# =============================================================================
# Measurement Formatting for Diff Display
# =============================================================================


def _measurement_kind(measurement: Measurement) -> str:
    """Extract the string representation of a measurement kind."""
    if isinstance(measurement.kind, AlloyMeasurementKind):
        return measurement.kind.value
    return str(measurement.kind)


def _normalize_number_text(value: float | int | str) -> str:
    """Normalize number representation for consistent display."""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return f"{value:g}"
    return str(value)


def _format_measurement_line(measurement: Measurement) -> str:
    """Format a measurement as a line for diff display."""
    line = f"{_measurement_kind(measurement)} | {_normalize_number_text(measurement.value)} {measurement.unit}"
    if measurement.uncertainty is not None:
        return f"{line} +/- {_normalize_number_text(measurement.uncertainty)}"
    return line


def _measurement_sort_key(measurement: Measurement) -> tuple[str, str, str, str]:
    """Generate a sort key for consistent measurement ordering."""
    uncertainty = ""
    if measurement.uncertainty is not None:
        uncertainty = _normalize_number_text(measurement.uncertainty)
    return (
        _measurement_kind(measurement),
        _normalize_number_text(measurement.value),
        str(measurement.unit),
        uncertainty,
    )


# =============================================================================
# Material Line Extraction
# =============================================================================


def _format_lattice_line(lm: LatticeMeasurement, prefix: str = "") -> str:
    """Format a LatticeMeasurement as a line for diff display."""
    p = lm.lattice.parameters
    label = f"{prefix}lattice" if prefix else "lattice"
    return f"{label} | a={p[0]:.4f} b={p[1]:.4f} c={p[2]:.4f} alpha={p[3]:.2f} beta={p[4]:.2f} gamma={p[5]:.2f}"


def _extract_config_field_lines(config: Configuration) -> list[str]:
    """Extract field lines from a config WITHOUT the config name prefix.

    Used for Myers alignment so that identical fields match regardless of
    config name differences.
    """
    lines: list[str] = []
    if config.tags:
        tag_str = ", ".join(sorted(t.value for t in config.tags))
        lines.append(f"tags | {tag_str}")
    if config.within is not None:
        lines.append(f"within | {config.within}")
    if config.struct is not None:
        lines.append(f"struct | {config.struct.value}")
    for nested in config.measurements:
        if isinstance(nested, Measurement):
            lines.append(_format_measurement_line(nested))
        elif isinstance(nested, LatticeMeasurement):
            lines.append(_format_lattice_line(nested))
        elif isinstance(nested, CompMeasurement):
            norm = nested.composition.fractional_composition.alphabetical_formula
            lines.append(f"composition | {norm}")
    if not lines and config.name:
        lines.append(f"name | {config.name}")
    return sorted(lines)


def _extract_config_lines(config: Configuration) -> list[str]:
    """Extract display lines from a single Configuration object (with prefix)."""
    config_prefix = f"config({config.name or '?'})/"
    return [f"{config_prefix}{line}" for line in _extract_config_field_lines(config)]


def _extract_measurement_lines(material: Material, *, include_configs: bool = True) -> list[str]:
    """Extract measurement lines from a material for diff display.

    Args:
        material: The material to extract lines from.
        include_configs: If True, include Configuration objects in output.
    """
    typed_measurements: list[Measurement] = []
    extra_lines: list[str] = []
    for measurement in material.measurements:
        if isinstance(measurement, Measurement):
            typed_measurements.append(measurement)
        elif isinstance(measurement, LatticeMeasurement):
            extra_lines.append(_format_lattice_line(measurement))
        elif isinstance(measurement, Configuration) and include_configs:
            extra_lines.extend(_extract_config_lines(measurement))
        elif isinstance(measurement, GlobalLatticeParam):
            glp_prefix = f"glp({measurement.name or '?'})/"
            if measurement.lattice is not None:
                extra_lines.append(_format_lattice_line(measurement.lattice, prefix=glp_prefix))
            if measurement.struct is not None:
                extra_lines.append(f"{glp_prefix}struct | {measurement.struct.value}")
            if measurement.phase_fraction is not None:
                pf = measurement.phase_fraction
                extra_lines.append(f"{glp_prefix}phase_fraction | {_normalize_number_text(pf.value)} {pf.unit}")
    measurement_lines = [
        _format_measurement_line(measurement) for measurement in sorted(typed_measurements, key=_measurement_sort_key)
    ]
    return measurement_lines + sorted(extra_lines)


def _extract_composition_lines(material: Material) -> list[str]:
    """Extract composition lines from a material for diff display."""
    composition_lines: list[str] = []
    for measurement in material.measurements:
        if isinstance(measurement, CompMeasurement):
            normalized_formula = measurement.composition.fractional_composition.alphabetical_formula
            composition_lines.append(f"composition | {normalized_formula}")
    return composition_lines


def _extract_material_diff_lines(material: Material, *, include_configs: bool = True) -> list[str]:
    """Extract all lines from a material for diff display."""
    lines: list[str] = []
    lines.append("[composition]")
    lines.extend(_extract_composition_lines(material))
    lines.append("[measurements]")
    lines.extend(_extract_measurement_lines(material, include_configs=include_configs))
    return lines


def _config_within_depth(cfg: Configuration, name_to_cfg: dict[str, Configuration]) -> int:
    """Compute nesting depth of a config via its `within` chain (0 = root)."""
    depth = 0
    visited: set[str] = set()
    current = cfg
    while current.within is not None and current.within not in visited:
        visited.add(current.within)
        depth += 1
        parent = name_to_cfg.get(current.within)
        if parent is None:
            break
        current = parent
    return depth


def _render_config_diff_rows(
    config_match: ConfigurationMatchResult | None,
    column_width: int,
) -> list[str]:
    """Render config matching results as formatted diff lines."""
    if config_match is None:
        return []

    has_any = config_match.matched_pairs or config_match.unmatched_target or config_match.unmatched_extracted
    if not has_any:
        return []

    # Build name→config map for target configs to compute within depth
    target_name_map: dict[str, Configuration] = {}
    for t_cfg, _, _ in config_match.matched_pairs:
        if t_cfg.name:
            target_name_map[t_cfg.name] = t_cfg
    for t_cfg in config_match.unmatched_target:
        if t_cfg.name:
            target_name_map[t_cfg.name] = t_cfg

    output: list[str] = []
    output.append(_split_columns("[configurations]", " ", "[configurations]", column_width))

    # Sort matched pairs by target within-depth so parents appear before children
    indexed_pairs = list(enumerate(config_match.matched_pairs))
    indexed_pairs.sort(key=lambda x: _config_within_depth(x[1][0], target_name_map))

    for idx, (t_cfg, e_cfg, score) in indexed_pairs:
        # Use prefix-free lines for Myers alignment so identical fields match
        t_field_lines = _extract_config_field_lines(t_cfg)
        e_field_lines = _extract_config_field_lines(e_cfg)
        nested = config_match.nested_measurement_results[idx]
        meas_info = f"{nested.match_score:.0f}/{nested.total}"
        bd = config_match.breakdowns[idx]
        breakdown_str = (
            f"tags={bd.tags:.0%} struct={bd.struct:.0%} name={bd.name:.0%} "
            f"meas={bd.measurement:.0%} within={bd.within:.0%}"
        )
        t_depth = _config_within_depth(t_cfg, target_name_map)
        t_indent = "  " * t_depth
        e_prefix = f"config({e_cfg.name or '?'})/"
        t_prefix = f"config({t_cfg.name or '?'})/"
        output.append(
            _split_columns(
                f"config({e_cfg.name or '?'}) score={score:.2f} [{breakdown_str}] meas={meas_info}",
                "~",
                f"{t_indent}config({t_cfg.name or '?'})",
                column_width,
            )
        )
        # Myers aligns on field content; we re-add per-side prefixes for display
        rows = _align_lines_myers(e_field_lines, t_field_lines)
        for row in rows:
            e_text = f"{e_prefix}{row.extracted_text}" if row.extracted_text else ""
            t_text = f"{t_indent}{t_prefix}{row.target_text}" if row.target_text else ""
            output.append(_split_columns(e_text, row.marker, t_text, column_width))

    for cfg in config_match.unmatched_extracted:
        for line in _extract_config_lines(cfg):
            output.append(_split_columns(line, "-", "", column_width))

    for cfg in config_match.unmatched_target:
        t_depth = _config_within_depth(cfg, target_name_map)
        t_indent = "  " * t_depth
        for line in _extract_config_lines(cfg):
            output.append(_split_columns("", "+", f"{t_indent}{line}", column_width))

    return output


# =============================================================================
# Process Event Formatting
# =============================================================================


def _format_quantity(q: Quantity) -> str:
    """Format a Quantity as a short string."""
    return f"{_normalize_number_text(q.value)} {q.unit}"


def _format_process_event_line(event: ProcessEvent) -> str:
    """Format a ProcessEvent as a line for diff display."""
    kind = event.kind.value if hasattr(event.kind, "value") else str(event.kind)
    parts = [kind]
    if event.temperature is not None:
        parts.append(f"T={_format_quantity(event.temperature)}")
    if event.duration is not None:
        parts.append(f"t={_format_quantity(event.duration)}")
    return " | ".join(parts)


def _render_process_diff_rows(
    alignment: ProcessEventAlignmentResult | None,
    column_width: int,
) -> list[str]:
    """Render process event alignment as formatted diff lines."""
    if alignment is None:
        return []

    has_any = alignment.matched_pairs or alignment.unmatched_target or alignment.unmatched_extracted
    if not has_any:
        return []

    output: list[str] = []
    output.append(_split_columns("[process events]", " ", "[process events]", column_width))

    for t_evt, e_evt in alignment.matched_pairs:
        e_line = _format_process_event_line(e_evt)
        t_line = _format_process_event_line(t_evt)
        marker = " " if e_line == t_line else "~"
        output.append(_split_columns(e_line, marker, t_line, column_width))

    for e_evt in alignment.unmatched_extracted:
        output.append(_split_columns(_format_process_event_line(e_evt), "-", "", column_width))

    for t_evt in alignment.unmatched_target:
        output.append(_split_columns("", "+", _format_process_event_line(t_evt), column_width))

    return output


# =============================================================================
# Myers Diff Algorithm
# =============================================================================


def _align_lines_myers(
    extracted_lines: list[str],
    target_lines: list[str],
) -> list[DiffRow]:
    """Align two lists of lines using a sequence-matching diff.

    Returns DiffRow objects with markers: " " (equal), "-" (only in
    extracted), "+" (only in target).
    """
    from difflib import SequenceMatcher

    rows: list[DiffRow] = []
    sm = SequenceMatcher(None, extracted_lines, target_lines)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for i, j in zip(range(i1, i2), range(j1, j2)):
                rows.append(DiffRow(marker=" ", extracted_text=extracted_lines[i], target_text=target_lines[j]))
        elif tag == "replace":
            # Show deletions then insertions for the replaced block
            for i in range(i1, i2):
                rows.append(DiffRow(marker="-", extracted_text=extracted_lines[i], target_text=""))
            for j in range(j1, j2):
                rows.append(DiffRow(marker="+", extracted_text="", target_text=target_lines[j]))
        elif tag == "delete":
            for i in range(i1, i2):
                rows.append(DiffRow(marker="-", extracted_text=extracted_lines[i], target_text=""))
        elif tag == "insert":
            for j in range(j1, j2):
                rows.append(DiffRow(marker="+", extracted_text="", target_text=target_lines[j]))
    return rows


# =============================================================================
# Text Formatting Utilities
# =============================================================================


def _truncate_text(text: str, width: int) -> str:
    """Truncate text to fit within a given width."""
    if len(text) <= width:
        return text
    if width < 4:
        return text[:width]
    return text[: width - 3] + "..."


def _split_columns(extracted: str, marker: str, target: str, column_width: int) -> str:
    """Format text into side-by-side columns for diff display."""
    left_col = _truncate_text(extracted, column_width).ljust(column_width)
    right_col = _truncate_text(target, column_width).ljust(column_width)
    return f"{left_col} {marker} {right_col}"


# =============================================================================
# Material Collection Utilities
# =============================================================================


def _print_full_material_list(title: str, materials: list[Material], max_lines_per_material: int = 60) -> None:
    """Print a full list of materials with their details."""
    print("")
    print(f"[{title}] count={len(materials)}")
    if not materials:
        print("  (none)")
        return
    for index, material in enumerate(materials):
        print(f"  @@ material {index} @@")
        material_lines = _extract_material_diff_lines(material)
        if not material_lines:
            print("    (no content)")
            continue
        for line in material_lines[:max_lines_per_material]:
            print(f"    {line}")
        if len(material_lines) > max_lines_per_material:
            hidden_line_count = len(material_lines) - max_lines_per_material
            print(f"    ... ({hidden_line_count} more lines)")


# =============================================================================
# Main Diff View Function
# =============================================================================


def print_one_call_diff_view(
    result: ExperimentComparisonResult,
    max_values_per_side: int = 300,
    label: str = "one_call",
) -> None:
    """Print experiment comparison results in a side-by-side diff format.

    This provides a detailed, git-diff-style view showing:
    - Summary statistics (matched/unmatched counts, precision, recall, F1)
    - Full lists of all extracted and target materials
    - Side-by-side comparison of matched pairs using Myers diff algorithm
    - Lists of unmatched materials

    Args:
        result: The comparison result to visualize
        max_values_per_side: Maximum number of lines to show per material in diff
        label: Label to display in the header
    """
    import shutil

    terminal_width = shutil.get_terminal_size((160, 24)).columns
    # 3 chars for " marker " between columns
    column_width = max(40, (terminal_width - 3) // 2)
    print(f"review diff: {label}")
    print(
        f"matched={len(result.matched_materials)} missing_target={len(result.unmatched_target_materials)} "
        + f"extra_extracted={len(result.unmatched_extracted_materials)} cost={result.total_cost:.2f} "
        + f"p={result.precision:.4f} r={result.recall:.4f} f1={result.f1:.4f}"
    )
    print("--- extracted")
    print("+++ target")
    print(_split_columns("EXTRACTED", " ", "TARGET", column_width))
    print(_split_columns("-" * column_width, " ", "-" * column_width, column_width))

    for index, match in enumerate(result.matched_materials):
        # Non-config lines use Myers diff
        rows = _align_lines_myers(
            extracted_lines=_extract_material_diff_lines(match.extracted, include_configs=False)[:max_values_per_side],
            target_lines=_extract_material_diff_lines(match.target, include_configs=False)[:max_values_per_side],
        )
        # Config lines use structured matching
        config_rows = _render_config_diff_rows(match.config_match, column_width)
        # Process event lines use alignment from eval
        process_rows = _render_process_diff_rows(match.process_alignment, column_width)

        print("")
        print(
            f"@@ material {index} @@ match_distance={match.cost:.2f} process_edit_dist={match.process_edit_distance} "
            + f"score={match.measurement_result.match_score:.2f}/{match.measurement_result.total}"
        )
        if not rows and not config_rows and not process_rows:
            print(_split_columns("(no content)", " ", "(no content)", column_width))
            continue
        for line in process_rows:
            print(line)
        for row in rows:
            print(_split_columns(row.extracted_text, row.marker, row.target_text, column_width))
        for line in config_rows:
            print(line)

    if result.unmatched_extracted_materials:
        print("")
        print("[unmatched extracted materials]")
        for material in result.unmatched_extracted_materials:
            print(_split_columns(repr(material), "-", "", column_width))

    if result.unmatched_target_materials:
        print("")
        print("[unmatched target materials]")
        for material in result.unmatched_target_materials:
            print(_split_columns("", "+", repr(material), column_width))
