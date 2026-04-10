"""Validation functions for Experiment dataclass.

This module contains all validation logic extracted from the Experiment class
to provide clearer separation of concerns between data model and validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from litxbench.core.models import (
        DescriptionGroup,
        Material,
        ProcessEvent,
        RawMaterial,
        SynthesisGroup,
    )


def validate_raw_materials_not_empty(raw_materials: dict[str, "RawMaterial"]) -> None:
    """Raw materials dict must not be empty.

    Args:
        raw_materials: Dictionary of raw materials

    Raises:
        ValueError: If raw_materials dict is empty
    """
    if not raw_materials:
        raise ValueError("Experiment must have at least one raw material")


def validate_synthesis_groups(
    synthesis_groups: dict[str, list["ProcessEvent"]] | list["ProcessEvent"], output_materials: list["Material"]
) -> None:
    """Validate synthesis groups.

    Args:
        synthesis_groups: Synthesis groups (either dict or list)
        output_materials: List of output materials

    Raises:
        ValueError: If synthesis_groups is a list and any material has a process
        ValueError: If synthesis_groups is a dict and it is empty.
    """
    if isinstance(synthesis_groups, dict):
        if not synthesis_groups:
            raise ValueError("Synthesis groups dict must not be empty")
        return

    materials_with_process = [m for m in output_materials if m.process_steps]
    if materials_with_process:
        raise ValueError(
            f"When synthesis_groups is a list, materials should not have a process. This is because it is implied that all materials use the same synthesis groups - so manually specifying a process is likely an error. Found {len(materials_with_process)} material(s) with process set."
        )


def validate_all_synthesis_groups_are_used(
    synthesis: dict[str, SynthesisGroup], output_materials: list["Material"]
) -> None:
    """All synthesis groups must be referenced by at least one material.

    Default groups (created from list input) are implicitly used by all materials
    and are skipped.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects
        output_materials: List of output materials

    Raises:
        ValueError: If a synthesis group is defined but never used by any material
    """
    # Collect all base_names referenced by materials
    referenced_base_names: set[str] = set()
    for material in output_materials:
        if material.process_steps:
            for step in material.process_steps:
                referenced_base_names.add(step.base_name)

    from litxbench.core.models import DEFAULT_SYNTHESIS_GROUP_NAME

    for base_name, group in synthesis.items():
        # Default groups are implicitly used by all materials
        if base_name == DEFAULT_SYNTHESIS_GROUP_NAME:
            continue

        if base_name not in referenced_base_names:
            error_message = f"Synthesis group '{group.name}' is defined but never used by any material. The process events in this group are:\n{group.process_events}"
            raise ValueError(error_message)


def validate_template_vars_used_in_fields(synthesis: dict[str, SynthesisGroup]) -> None:
    """Each template variable declared in a group name must appear in at least one process event field.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects

    Raises:
        ValueError: If a template variable is declared but never used in any field
    """
    for group in synthesis.values():
        if not group.template_vars:
            continue

        # Collect all searchable text from process event fields once per group
        all_text = " ".join(
            _field_text(fv) for pe in group.process_events for fv in vars(pe).values() if fv is not None
        )

        for template_var in group.template_vars:
            if f"[{template_var}]" not in all_text:
                raise ValueError(
                    f"Synthesis group '{group.name}' has template variable [{template_var}] but it's not used in any field of the process events."
                )


def validate_materials_provide_template_values(
    synthesis: dict[str, SynthesisGroup], output_materials: list["Material"]
) -> None:
    """Each material step referencing a templated group must provide variable values.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects
        output_materials: List of output materials

    Raises:
        ValueError: If a material references a templated group but doesn't provide variable values
    """
    from litxbench.core.models import ProcessStep

    templated_groups = {name: g for name, g in synthesis.items() if g.template_vars}
    if not templated_groups:
        return

    for material in output_materials:
        if not material.process_steps:
            continue

        for step in material.process_steps:
            if step.base_name in templated_groups and not step.variables:
                group = templated_groups[step.base_name]
                group_step = ProcessStep.parse_event_name(group.name)
                template_var = sorted(group.template_vars)[0]
                raise ValueError(
                    f"Material process step '{step.to_string()}' references '{group_step.to_string()}' but doesn't provide a value for [{template_var}]. Expected format: '{group_step.base_name}[{template_var}=<value>]'"
                )


def _field_text(field_value: object) -> str:
    """Extract searchable text from a field value (handles Quantity, str, and list[str])."""
    if hasattr(field_value, "value"):
        return str(field_value.value)
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, list):
        return " ".join(str(item) for item in field_value)
    return ""


def validate_material_variables_match_group_templates(
    synthesis: dict[str, SynthesisGroup], output_materials: list["Material"]
) -> None:
    """Check that variable assignments in material process match synthesis group templates.

    For each step in a material's process, if it contains variable assignments,
    verify that the corresponding synthesis group definition declares those template variables.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects
        output_materials: List of output materials

    Raises:
        ValueError: If a material assigns a variable not declared in the group template
    """
    for material in output_materials:
        if not material.process_steps:
            continue

        for step in material.process_steps:
            # Skip steps without variable assignments
            if not step.variables:
                continue

            # Direct lookup by base_name
            matching_group = synthesis.get(step.base_name)

            if not matching_group:
                raise ValueError(
                    f"Material process step '{step.to_string()}' references '{step.base_name}' but no matching synthesis group definition found"
                )

            # Check that each assigned variable is declared in the template
            for var_name in step.variables.keys():
                if var_name not in matching_group.template_vars:
                    raise ValueError(
                        f"Material process step '{step.to_string()}' assigns variable '{var_name}' but synthesis group '{matching_group.name}' does not declare this template variable. Expected template variables: {matching_group.template_vars or 'none'}"
                    )


def validate_no_duplicate_materials(output_materials: list["Material"]) -> None:
    """Check that no two materials are duplicates.

    Two materials are considered duplicates if they have the same composition,
    process steps, and measurements. Uses repr(material) as the fingerprint.

    Args:
        output_materials: List of output materials

    Raises:
        ValueError: If duplicate materials are found
    """
    seen: dict[str, int] = {}

    for i, material in enumerate(output_materials):
        fingerprint = repr(material)
        if fingerprint in seen:
            raise ValueError(
                f"Duplicate materials found: material {i} and material {seen[fingerprint]} are identical: {fingerprint}"
            )
        seen[fingerprint] = i


def validate_description_groups(
    descriptions: "list[DescriptionGroup[Any, Any]]",
    output_materials: "list[Material[Any]]",
    synthesis_group_map: dict[str, SynthesisGroup] | None = None,
) -> None:
    if not descriptions:
        return

    from litxbench.core.models import MeasurementMethod, ProcessKind

    allowed_classes: set[type[object]] = set()
    measurement_kind_names: set[str] = set()
    allowed_measurement_methods: set[object] = set()
    allowed_group_names: set[str] = set()

    for material in output_materials:
        for measurement in material.measurements:
            _collect_measurement(
                measurement, allowed_classes, measurement_kind_names, allowed_measurement_methods, allowed_group_names
            )

    # Collect allowed process kinds from synthesis groups
    allowed_process_kinds: set[ProcessKind] = set()
    if synthesis_group_map is not None:
        for group in synthesis_group_map.values():
            for event in group.process_events:
                if isinstance(event.kind, ProcessKind):
                    allowed_process_kinds.add(event.kind)

    # Validate group_name fields on description groups
    invalid_group_names: list[str] = []
    for desc_group in descriptions:
        if desc_group.group_name is not None:
            if desc_group.group_name not in allowed_group_names:
                invalid_group_names.append(desc_group.group_name)

    if invalid_group_names:
        error_message = (
            "Each descriptions group_name must match a group_name on at least one measurement in the experiment. "
            + f"Invalid group names: {invalid_group_names}."
            + (
                f" Allowed group names: {sorted(allowed_group_names)}."
                if allowed_group_names
                else " No measurements have a group_name set."
            )
        )
        raise ValueError(error_message)

    invalid_kinds: list[object] = []
    for desc_group in descriptions:
        for kind in desc_group.kinds:
            if isinstance(kind, type):
                if kind not in allowed_classes:
                    invalid_kinds.append(kind)
                continue

            if isinstance(kind, ProcessKind):
                if kind not in allowed_process_kinds:
                    invalid_kinds.append(kind)
                continue

            if isinstance(kind, MeasurementMethod):
                if kind not in allowed_measurement_methods:
                    invalid_kinds.append(kind)
                continue

            # Check if kind is a measurement method enum (e.g. MeasurementMethod.XRD)
            if kind in allowed_measurement_methods:
                continue

            key_name = _kind_name_from_key(kind)
            if key_name is not None and key_name in measurement_kind_names:
                continue

            # For plain string keys, also check if they match a group_name from any material
            if isinstance(kind, str) and kind in allowed_group_names:
                continue

            invalid_kinds.append(kind)

    if invalid_kinds:
        allowed_class_names = sorted({klass.__name__ for klass in allowed_classes})
        error_message = (
            "Each descriptions kind must reference a measurement, process, or measurement method that appears in the experiment. "
            + f"Invalid kinds: {invalid_kinds}. "
            + f"Allowed classes: {allowed_class_names}. "
            + f"Allowed measurement kinds: {sorted(measurement_kind_names)}."
            + (
                f" Allowed process kinds: {sorted(pk.value for pk in allowed_process_kinds)}."
                if allowed_process_kinds
                else ""
            )
            + (
                f" Allowed measurement methods: {sorted(str(mk) for mk in allowed_measurement_methods)}."
                if allowed_measurement_methods
                else ""
            )
            + (f" Allowed group names: {sorted(allowed_group_names)}." if allowed_group_names else "")
        )
        raise ValueError(error_message)


def _collect_measurement(
    measurement: object,
    allowed_classes: set[type[object]],
    measurement_kind_names: set[str],
    allowed_measurement_methods: set[object],
    allowed_group_names: set[str],
) -> None:
    from litxbench.core.models import CompMeasurement, Configuration, Measurement

    allowed_classes.add(type(measurement))
    measurement_kind_name = _measurement_kind_name(measurement)
    if measurement_kind_name is not None:
        measurement_kind_names.add(measurement_kind_name)
    if isinstance(measurement, CompMeasurement):
        allowed_measurement_methods.add(measurement.method)
    if isinstance(measurement, Measurement):
        if measurement.measurement_method is not None:
            allowed_measurement_methods.add(measurement.measurement_method)
        if measurement.group_name is not None:
            allowed_group_names.add(measurement.group_name)
    if isinstance(measurement, Configuration):
        for nested in measurement.measurements:
            _collect_measurement(
                nested, allowed_classes, measurement_kind_names, allowed_measurement_methods, allowed_group_names
            )


def _kind_name_from_key(key: object) -> str | None:
    if isinstance(key, str):
        return key
    value = getattr(key, "value", None)
    if isinstance(value, str):
        return value
    return None


def _measurement_kind_name(measurement: object) -> str | None:
    kind = getattr(measurement, "kind", None)
    if kind is not None:
        if isinstance(kind, str):
            return kind
        value = getattr(kind, "value", None)
        if isinstance(value, str):
            return value

    return None


def validate_process_event_inputs(
    synthesis: dict[str, SynthesisGroup],
    raw_materials: dict[str, "RawMaterial"],
    output_materials: list["Material"],
) -> None:
    """Validate that explicit inputs in ProcessEvents reference known names.

    Resolves template variables per-material before checking, so that
    ``inputs=["[Feedstock]"]`` is validated against the concrete substituted value.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects
        raw_materials: Dictionary of raw material name -> RawMaterial
        output_materials: List of output materials

    Raises:
        ValueError: If a resolved input name doesn't reference a known raw material or named material
    """
    from litxbench.core.eval import resolve_process_events

    known_names = set(raw_materials.keys()) | {m.name for m in output_materials if m.name}

    for material in output_materials:
        resolved_events = resolve_process_events(material, synthesis)
        for event in resolved_events:
            for input_name in event.inputs:
                if input_name not in known_names:
                    raise ValueError(
                        f"ProcessEvent input '{input_name}' in material "
                        f"'{material.name or material.process}' "
                        f"does not reference a known raw material or named material. "
                        f"Valid options: {sorted(known_names)}"
                    )


def validate_no_name_collisions(
    raw_materials: dict[str, "RawMaterial"],
    synthesis: dict[str, SynthesisGroup],
    output_materials: list["Material"],
) -> None:
    """Ensure raw material names, synthesis group base names, material names, and measurement group names are all distinct.

    Synthesis groups like "as_extruded[TEMP]" are compared by their base_name ("as_extruded"),
    not the full key string.

    Args:
        raw_materials: Dictionary of raw material name -> RawMaterial
        synthesis: Dictionary of base_name -> SynthesisGroup (already parsed)
        output_materials: List of output materials

    Raises:
        ValueError: If any name appears in more than one category
    """
    from litxbench.core.models import Configuration, Measurement

    # Collect unique group names from all measurements across all materials
    group_names: set[str] = set()

    def _collect_group_names(measurement: object) -> None:
        if isinstance(measurement, Measurement) and measurement.group_name is not None:
            group_names.add(measurement.group_name)
        if isinstance(measurement, Configuration):
            for nested in measurement.measurements:
                _collect_group_names(nested)

    for material in output_materials:
        for measurement in material.measurements:
            _collect_group_names(measurement)

    categories: dict[str, list[str]] = {
        "raw_materials": list(raw_materials.keys()),
        "synthesis_groups": list(synthesis.keys()),
        "materials": [m.name for m in output_materials if m.name is not None],
        "measurement_group_names": list(group_names),
    }
    # TODO: consider adding configuration names to the categories. but since that is material class specific maybe not.

    # Track which categories each name appears in
    name_sources: dict[str, list[str]] = {}
    for category, names in categories.items():
        for name in names:
            name_sources.setdefault(name, []).append(category)

    collisions = {name: sources for name, sources in name_sources.items() if len(sources) > 1}
    if collisions:
        details = ", ".join(f"'{name}' appears in {sources}" for name, sources in collisions.items())
        raise ValueError(
            f"Name collisions found: {details}. Raw materials, synthesis groups, materials, and measurement group names must have distinct names."
        )


def check_melting_followed_by_casting(events: "list[ProcessEvent]", material_label: str) -> None:
    """Check that every melting event in *events* is immediately followed by a casting event.

    Args:
        events: Flat, ordered list of process events for a single material.
        material_label: Human-readable name used in error messages.

    Raises:
        ValueError: If a melting event is not immediately followed by a casting event.
    """
    from litxbench.core.enums import CASTING_KINDS, MELTING_KINDS

    for i, event in enumerate(events):
        if event.kind in MELTING_KINDS:
            if i + 1 >= len(events) or events[i + 1].kind not in CASTING_KINDS:
                casting_names = sorted(k.value for k in CASTING_KINDS)
                raise ValueError(
                    f"Material '{material_label}': ProcessEvent '{getattr(event.kind, 'value', event.kind)}' "
                    f"must be immediately followed by a casting step. "
                    f"Valid casting kinds: {casting_names}"
                )


def validate_melting_followed_by_casting(
    synthesis: dict[str, SynthesisGroup],
    output_materials: list["Material"],
) -> None:
    """Validate that ArcMelting/InductionMelting events are followed by a casting event.

    Resolves each material's full process event sequence by expanding its process
    steps through their synthesis groups, then checks that every melting event
    is immediately followed by a casting step.

    Args:
        synthesis: Dict of base_name -> SynthesisGroup objects
        output_materials: List of output materials

    Raises:
        ValueError: If a melting event is not immediately followed by a casting event
    """
    for material in output_materials:
        if not material.process_steps:
            continue

        # Build the full resolved event sequence for this material
        all_events: list["ProcessEvent"] = []
        for step in material.process_steps:
            group = synthesis.get(step.base_name)
            if group is None:
                continue
            if step.variables:
                all_events.extend(group.substitute_variables(step.variables))
            else:
                all_events.extend(group.process_events)

        material_label = material.name or f"(unnamed material index {output_materials.index(material)})"
        check_melting_followed_by_casting(all_events, material_label)


def validate_measurement_types(
    measurements: "Sequence[Any]",
    allowed_types: tuple[type, ...],
    material_name: str | None = None,
) -> None:
    """Validate that all measurements are instances of the allowed types.

    Args:
        measurements: Sequence of measurement objects from a single material
        allowed_types: Tuple of allowed measurement classes
        material_name: Optional material name for error messages

    Raises:
        ValueError: If a measurement is not an instance of any allowed type
    """
    for measurement in measurements:
        if not isinstance(measurement, allowed_types):
            label = material_name or "(unnamed)"
            raise ValueError(
                f"Material '{label}' contains a measurement of type "
                f"{type(measurement).__name__}, which is not one of the allowed "
                f"measurement types: {[t.__name__ for t in allowed_types]}. "
                f"Offending measurement: {measurement!r}"
            )


def validate_all_raw_materials_used_by_materials(
    raw_materials: dict[str, "RawMaterial"],
    synthesis: dict[str, SynthesisGroup],
    output_materials: list["Material"],
) -> None:
    """Every raw material must appear as an input somewhere in the experiment.

    A raw material counts as "used" if it appears in:
    - A material's ProcessStep inputs, OR
    - A ProcessEvent's explicit inputs within a synthesis group

    A raw material doesn't need to be used by every material -- it just needs
    to be referenced at least once.

    Args:
        raw_materials: Dictionary of raw material name -> RawMaterial
        synthesis: Dict of base_name -> SynthesisGroup objects
        output_materials: List of output materials

    Raises:
        ValueError: If a raw material is never used as an input
    """
    all_inputs: set[str] = set()

    # Collect inputs from material process steps
    for material in output_materials:
        if material.process_steps:
            for step in material.process_steps:
                all_inputs.update(step.inputs)

    # Collect explicit inputs from process events in synthesis groups
    for group in synthesis.values():
        for event in group.process_events:
            all_inputs.update(event.inputs)

    missing = set(raw_materials.keys()) - all_inputs
    if missing:
        raise ValueError(
            f"Raw materials {sorted(missing)} are declared but never used as inputs "
            f"in any material's process steps or synthesis group process events."
        )
