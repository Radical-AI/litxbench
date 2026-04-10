"""Experiment extraction framework models"""

from __future__ import annotations

import re
import types
import uuid
from collections.abc import Sequence
from dataclasses import InitVar, dataclass, field, replace
from enum import Enum
from typing import Any, ClassVar, Generic, TypeAliasType, TypeVar, Union, get_args, get_origin, overload

import pint
from pymatgen.core.composition import Composition
from pymatgen.core.lattice import Lattice as PymatgenLattice

from litxbench.core.enums import (  # noqa: F401
    ConfigTag,
    CrysStruct,
    MeasurementMethod,
    ProcessKind,
    RawMaterialKind,
    ValueQualifier,
)
from litxbench.core.validators import (
    validate_all_raw_materials_used_by_materials,
    validate_all_synthesis_groups_are_used,
    validate_description_groups,
    validate_material_variables_match_group_templates,
    validate_materials_provide_template_values,
    validate_measurement_types,
    validate_melting_followed_by_casting,
    validate_no_duplicate_materials,
    validate_no_name_collisions,
    validate_process_event_inputs,
    validate_raw_materials_not_empty,
    validate_synthesis_groups,
    validate_template_vars_used_in_fields,
)

_QUALIFIER_PATTERN = re.compile(r"^(~|>>|<<|>=|<=|>|<)\s*(.+)$")

_PREFIX_TO_QUALIFIER: dict[str, ValueQualifier] = {
    "~": ValueQualifier.APPROXIMATE,
    ">>": ValueQualifier.MUCH_ABOVE,
    "<<": ValueQualifier.MUCH_BELOW,
    ">=": ValueQualifier.ABOVE_OR_EQUAL,
    "<=": ValueQualifier.BELOW_OR_EQUAL,
    ">": ValueQualifier.ABOVE,
    "<": ValueQualifier.BELOW,
}


class NumericQualifierMixin:
    """Mixin for dataclasses whose ``value`` field may carry a qualifier prefix.

    Expects the host dataclass to have a ``value: float | int | str`` field.
    Adds two computed attributes (``numeric_value`` and ``value_qualifier``)
    that are derived from ``value`` during ``__post_init__``.

    Subclasses should call ``self._parse_qualified_value()`` in their
    ``__post_init__`` (or let dataclass field defaults handle it via the
    provided ``field`` helpers).
    """

    numeric_value: float | int | None
    value_qualifier: ValueQualifier

    def _parse_qualified_value(self) -> None:
        if isinstance(self.value, (int, float)):
            self.numeric_value = self.value
            self.value_qualifier = ValueQualifier.EXACT
        elif isinstance(self.value, str):
            m = _QUALIFIER_PATTERN.match(self.value.strip())
            if m:
                prefix, num_str = m.group(1), m.group(2)
                try:
                    self.numeric_value = float(num_str)
                except ValueError:
                    self.numeric_value = None
                    self.value_qualifier = ValueQualifier.EXACT
                    return
                self.value_qualifier = _PREFIX_TO_QUALIFIER[prefix]
            else:
                try:
                    self.numeric_value = float(self.value)
                    self.value_qualifier = ValueQualifier.EXACT
                except ValueError:
                    self.numeric_value = None
                    self.value_qualifier = ValueQualifier.EXACT
        else:
            self.numeric_value = None
            self.value_qualifier = ValueQualifier.EXACT


@dataclass
class Quantity(NumericQualifierMixin):
    value: float | int | str
    unit: pint.Unit
    description: str | None = None
    source: str | None = None

    # Computed from `value` in __post_init__; not passed to __init__
    numeric_value: float | int | None = field(default=None, init=False)
    value_qualifier: ValueQualifier = field(default=ValueQualifier.EXACT, init=False)

    def __post_init__(self) -> None:
        self._parse_qualified_value()


MeasurementMethodT = TypeVar("MeasurementMethodT")


@dataclass(kw_only=True)
class CoreMeasurementValue:
    statistic: MeasurementStatistic
    value: float | int | str
    uncertainty: float | None = None
    description: str | None = None
    source: str | None = None
    percentile: float | None = None
    # the percentile validation is done on the Measurement class, not here


class MeasurementStatistic(Enum):
    mean = "mean"
    median = "median"
    lower = "lower"
    upper = "upper"
    percentile = "percentile"


@dataclass(kw_only=True)
class Measurement(NumericQualifierMixin, Generic[MeasurementMethodT]):
    kind: str

    value: float | int | str
    unit: pint.Unit
    uncertainty: float | None = None
    measurement_method: MeasurementMethodT | None = None

    description: str | None = None
    source: str | None = None

    # For these, we default to None so we explicitly KNOW when a paper includes this
    temperature: Quantity | None = None
    pressure: Quantity | None = None

    # Computed from `value` in __post_init__; not passed to __init__
    numeric_value: float | int | None = field(default=None, init=False)
    value_qualifier: ValueQualifier = field(default=ValueQualifier.EXACT, init=False)

    measurement_statistic: MeasurementStatistic | None = None
    percentile: float | None = None

    group_name: str | None = None
    group_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        self._parse_qualified_value()
        self._validate_statistic_measurements()

    def _validate_statistic_measurements(self) -> None:
        if self.measurement_statistic is not MeasurementStatistic.percentile and self.percentile is not None:
            raise ValueError("You can only set a percentile when the measurement statistic is a percentile")
        if self.measurement_statistic == MeasurementStatistic.percentile and self.percentile is None:
            raise ValueError("Percentile value must be provided when measurement statistic is percentile")
        if self.percentile is not None and not (0 <= self.percentile <= 100):
            raise ValueError("Percentile must be between 0 and 100")

    @overload
    @staticmethod
    def group_measurements(
        kind: str,
        unit: pint.Unit,
        measurement_method: MeasurementMethodT,
        description: str | None = ...,
        uncertainty: float | None = ...,
        temperature: Quantity | None = ...,
        pressure: Quantity | None = ...,
        source: str | None = ...,
        group_name: str | None = ...,
        values: list[CoreMeasurementValue] = ...,
    ) -> list[Measurement[MeasurementMethodT]]: ...

    @overload
    @staticmethod
    def group_measurements(
        kind: str,
        unit: pint.Unit,
        measurement_method: None = ...,
        description: str | None = ...,
        uncertainty: float | None = ...,
        temperature: Quantity | None = ...,
        pressure: Quantity | None = ...,
        source: str | None = ...,
        group_name: str | None = ...,
        values: list[CoreMeasurementValue] = ...,
    ) -> list[Measurement[Any]]: ...

    @staticmethod
    def group_measurements(
        kind: str,  # all must share the same kind
        unit: pint.Unit,  # all must share the same unit
        measurement_method: MeasurementMethodT | None = None,  # all must share the same measurement method
        description: str | None = None,  # all must share the same description
        uncertainty: float | None = None,  # default uncertainty value
        temperature: Quantity | None = None,  # all must share the same temperature
        pressure: Quantity | None = None,  # all must share the same pressure
        source: str | None = None,
        group_name: str | None = None,  # all must share the same group name
        values: list[CoreMeasurementValue] | None = None,
    ) -> list[Measurement[MeasurementMethodT]] | list[Measurement[Any]]:
        if values is None:
            values = []
        measurements = []
        if len(values) < 2:
            raise ValueError("At least two values must be provided")

        group_id = uuid.uuid4()  # always provide a group_id so we know which measurements were grouped together

        for value in values:
            new_uncertainty = uncertainty
            if value.uncertainty is not None:
                # override the default uncertainty with the value's uncertainty
                new_uncertainty = value.uncertainty

            new_description = description
            if value.description is not None:
                if new_description is None:
                    new_description = value.description
                else:
                    # do not override the default description. just add more to it for this measurement
                    new_description = f"{new_description}\n{value.description}"

            new_source = source
            if value.source is not None:
                if new_source is None:
                    new_source = value.source
                else:
                    # do not override the default source. just add more to it for this measurement
                    new_source = f"{new_source}\n{value.source}"

            measurements.append(
                Measurement(
                    kind=kind,
                    unit=unit,
                    value=value.value,
                    measurement_method=measurement_method,
                    group_name=group_name,
                    uncertainty=new_uncertainty,
                    temperature=temperature,
                    pressure=pressure,
                    description=new_description,
                    source=new_source,
                    measurement_statistic=value.statistic,
                    percentile=value.percentile,
                    group_id=group_id,
                )
            )
        return measurements


@dataclass
class LatticeMeasurement:
    lattice: PymatgenLattice
    description: str | None = None
    source: str | None = None

    def __repr__(self) -> str:
        lat = self.lattice
        parts = [f"Lattice(a={lat.a}, b={lat.b}, c={lat.c}, alpha={lat.alpha}, beta={lat.beta}, gamma={lat.gamma})"]
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        if self.source is not None:
            parts.append(f"source={self.source!r}")
        return f"LatticeMeasurement({', '.join(parts)})"


@dataclass
class GlobalLatticeParam:
    lattice: LatticeMeasurement | None = None
    struct: CrysStruct | None = None
    name: str | None = None
    description: str | None = None
    phase_fraction: Quantity | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if self.phase_fraction is not None and not isinstance(self.phase_fraction, Quantity):
            raise TypeError(
                f"phase_fraction must be a Quantity (e.g. Quantity(value=100, unit=percent)), "
                f"got {type(self.phase_fraction).__name__}: {self.phase_fraction!r}"
            )

    def __repr__(self) -> str:
        parts = []
        if self.lattice is not None:
            parts.append(f"lattice={self.lattice!r}")
        if self.struct is not None:
            parts.append(f"struct={self.struct!r}")
        if self.name is not None:
            parts.append(f"name={self.name!r}")
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        if self.phase_fraction is not None:
            parts.append(f"phase_fraction={self.phase_fraction!r}")
        if self.source is not None:
            parts.append(f"source={self.source!r}")
        return f"GlobalLatticeParam({', '.join(parts)})"


@dataclass(kw_only=True)
class Configuration:
    name: str | None = None
    within: str | None = None  # this must reference the name of another configuration
    struct: CrysStruct | None = None
    tags: set[ConfigTag] | None = None
    description: str | None = None
    source: str | None = None
    # Notice how Configurations cannot be within another Configuration's measurements.
    # Children configurations must use the `within` field to reference the parent configuration. This keeps things organized (and easier to read).
    measurements: list[Measurement[MeasurementMethod] | LatticeMeasurement | CompMeasurement] = field(
        default_factory=list
    )


@dataclass(kw_only=True)
class ProcessEvent:
    kind: ProcessKind
    description: str | None = None
    temperature: Quantity | None = None
    duration: Quantity | None = None
    equipment: str | None = None
    source: str | None = None
    inputs: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class RawMaterial:
    kind: RawMaterialKind
    description: str | None = None
    source: str | None = None


@dataclass
class CompMeasurement:
    composition: Composition  # TODO: we should have a way to record the compositional variance as well
    method: MeasurementMethod
    description: str | None = None
    source: str | None = None
    validate_composition: bool = True  # Disable validation composition if the reported compositions do not sum to 100. This can occur due to rounding or unreported impurities in the spectra

    def __init__(
        self,
        composition: Composition | str | dict[str, float],
        method: MeasurementMethod = MeasurementMethod.Unspecified,
        description: str | None = None,
        source: str | None = None,
        validate_composition: bool = True,
    ) -> None:
        self.composition = composition if isinstance(composition, Composition) else Composition(composition)
        self.method = method
        self.description = description
        self.source = source
        self.validate_composition = validate_composition
        if self.validate_composition:
            self._validate_composition()

    # 0.2 was chosen because composition rounding tends to cause compositions to be off by at most 0.2. 0.2001 was chosen to permit floating point rounding errors.
    def _validate_composition(self, tolerance: float = 0.2001) -> None:
        """
        Verify that a composition is valid.

        - Ratio-based compositions (Fe1Mg3Al1) are valid if non-empty with positive amounts
        - Percentage-based compositions (Fe20Mg60Al20) must sum to 100 within tolerance

        Compositions with num_atoms > 50 are considered percentage-based.

        Args:
            tolerance: Tolerance for percentage-based compositions summing to 100.
        """
        if self.composition.num_atoms == 0:
            raise ValueError(f"Composition is empty or has no atoms: {self}")

        is_percentage_based = self.composition.num_atoms > 50
        atom_sum = self.composition.num_atoms
        error = abs(atom_sum - 100)
        if is_percentage_based and error > tolerance:
            error_message = f"Composition is percentage-based but does not sum to 100: {self} (sums up to {atom_sum}). If the extracted composition is correct, set validate_composition=False. Rounding errors or genuine mistakes in the paper may cause this so it's okay to override this validation."
            raise ValueError(error_message)

    def __repr__(self) -> str:
        composition_str = self.composition.formula
        parts = [f"'{composition_str}'"]
        parts.append(f"composition_measurement_kind={self.method!r}")
        if self.description is not None:
            parts.append(f"description={self.description!r}")
        if self.source is not None:
            parts.append(f"source={self.source!r}")
        return f"CompositionMeasurement({', '.join(parts)})"


CompositionMeasurement = CompMeasurement


type CoreMeasurements = (
    CompMeasurement | Measurement[MeasurementMethod] | LatticeMeasurement | Configuration | GlobalLatticeParam
)

MeasurementClass = TypeVar("MeasurementClass")
MeasurementKind = TypeVar("MeasurementKind")


_MULTIPLE_BRACKETS_PATTERN = re.compile(r"\[[^\]]*\]")


def _check_multiple_bracket_groups(text: str) -> None:
    """Raise if *text* contains more than one ``[...]`` group.

    A common mistake is writing ``step[Temp=950][Time=100]`` instead of
    ``step[Temp=950,Time=100]``.  The regex used by the parsers silently
    discards everything after the first bracket group, so we catch this
    early with a clear error message.
    """
    matches = _MULTIPLE_BRACKETS_PATTERN.findall(text)
    if len(matches) > 1:
        raise ValueError(
            f"Multiple bracket groups found in '{text}': {matches}. "
            f"Use a single bracket group with comma-separated entries instead, "
            f"e.g. 'step[Temp=950,Time=100]'"
        )


@dataclass
class ProcessStep:
    """Structured representation of a process step.

    Replaces string notation with structured dataclass for easier validation and manipulation.
    """

    base_name: str
    """The base name of the process step (e.g., "annealing", "melting")."""
    variables: dict[str, str]
    """Variable assignments - ``{"Temp": "800"}`` for materials, ``{"Temp": ""}`` for event templates."""
    inputs: list[str] = field(default_factory=list)
    """Input names feeding into this step (e.g., raw materials, named materials)."""

    @classmethod
    def parse_material_step(cls, step: str, *, inputs: list[str] | None = None) -> "ProcessStep":
        """Parse a material step like 'annealing[Temp=800]'."""
        _check_multiple_bracket_groups(step)
        pattern = r"^([^\[]+)(?:\[([^\]]*)\])?.*$"
        match = re.match(pattern, step)

        if not match:
            raise ValueError(f"Invalid process step format: {step}")

        base_name = match.group(1)
        bracket_content = match.group(2) or ""

        variables: dict[str, str] = {}
        if bracket_content:
            for assignment in bracket_content.split(","):
                assignment = assignment.strip()
                if "=" in assignment:
                    var_name, var_value = assignment.split("=", 1)
                    variables[var_name.strip()] = var_value.strip()

        return cls(
            base_name=base_name,
            variables=variables,
            inputs=inputs if inputs is not None else [],
        )

    @classmethod
    def parse_process_string(cls, process: str) -> list["ProcessStep"]:
        """Parse a full process string into a list of ProcessSteps.

        Uses a single arrow type "->" to separate segments:
        - First segment = comma-separated input names
        - Remaining segments = steps parsed by parse_material_step

        The first segment must always contain at least one explicit input.
        """
        segments = process.split("->")
        if len(segments) < 2:
            raise ValueError(
                f"Invalid process string '{process}': the first event must have at least one explicit input (e.g., 'input->event')"
            )

        input_names = [name.strip() for name in segments[0].split(",") if name.strip()]
        if not input_names:
            raise ValueError(
                f"Invalid process string '{process}': the first event must have at least one explicit input (e.g., 'input->event')"
            )

        steps: list[ProcessStep] = []
        steps.append(cls.parse_material_step(segments[1], inputs=input_names))
        for segment in segments[2:]:
            steps.append(cls.parse_material_step(segment))
        return steps

    @classmethod
    def parse_event_name(cls, event_name: str) -> "ProcessStep":
        """Parse an event definition like 'annealing[Temp]'."""
        _check_multiple_bracket_groups(event_name)
        pattern = r"^([^\[]+)(?:\[([^\]]*)\])?.*$"
        match = re.match(pattern, event_name)

        if not match:
            raise ValueError(f"Invalid event name format: {event_name}")

        base_name = match.group(1)
        bracket_content = match.group(2) or ""

        variables: dict[str, str] = {}
        if bracket_content:
            for var_name in bracket_content.split(","):
                var_name = var_name.strip()
                if var_name:
                    variables[var_name] = ""

        return cls(base_name=base_name, variables=variables)

    def to_string(self) -> str:
        """Convert back to string notation for serialization/display."""
        result = self.base_name

        if self.variables:
            if all(v == "" for v in self.variables.values()):
                result += f"[{','.join(self.variables.keys())}]"
            else:
                var_strings = [f"{k}={v}" for k, v in self.variables.items()]
                result += f"[{','.join(var_strings)}]"

        return result


@dataclass
class Machine:
    methods: list[MeasurementMethod]
    model: str | None = None
    company: str | None = None
    location: str | None = None
    source: str | None = None


@dataclass(kw_only=True)
class Material(Generic[MeasurementClass]):
    _allowed_measurement_types: ClassVar[tuple[type, ...] | None] = None

    process: InitVar[str | None] = None
    name: str | None = None
    measurements: Sequence[MeasurementClass]
    process_steps: list["ProcessStep"] | None = field(default=None, init=False)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is Material:
                args = get_args(base)
                if args:
                    cls._allowed_measurement_types = _resolve_type_to_classes(args[0])
                break

    def __post_init__(self, process: str | None) -> None:
        if process is not None:
            self.process_steps = ProcessStep.parse_process_string(process)

        self._validate_compositions()
        self._validate_configuration_within()
        if self._allowed_measurement_types is not None:
            validate_measurement_types(self.measurements, self._allowed_measurement_types, self.name)

    def _validate_compositions(self) -> None:
        if not any(isinstance(m, CompMeasurement) for m in self.measurements):
            raise ValueError(f"Material {str(self)} has no composition measurements")

    def _validate_configuration_within(self) -> None:
        config_names: set[str] = set()
        configs_with_within: list[Configuration] = []
        for measurement in self.measurements:
            if isinstance(measurement, Configuration):
                if measurement.name is not None:
                    config_names.add(measurement.name)
                if measurement.within is not None:
                    configs_with_within.append(measurement)
        # Check that `within` references an existing configuration name
        for config in configs_with_within:
            if config.within not in config_names:
                raise ValueError(
                    f"Configuration '{config.name}' has within='{config.within}', "
                    + "but no Configuration with that name exists in the material. "
                    + f"Available configuration names: {config_names}"
                )
        # Check that all Precipitate configurations have a `within` reference
        for measurement in self.measurements:
            if (
                isinstance(measurement, Configuration)
                and measurement.tags is not None
                and ConfigTag.Precipitate in measurement.tags
                and measurement.within is None
            ):
                raise ValueError(
                    f"Configuration '{measurement.name}' is tagged as Precipitate "
                    + "but has no 'within' reference. All precipitates must be within another configuration."
                )
        # Check for circular references in the `within` chain
        within_map: dict[str, str] = {}
        for config in configs_with_within:
            if config.name is not None:
                within_map[config.name] = config.within  # type: ignore[assignment]
        for start_name in within_map:
            path: list[str] = []
            current = start_name
            while current in within_map:
                if current in path:
                    cycle_start = path.index(current)
                    cycle = path[cycle_start:]
                    raise ValueError(
                        "Circular reference detected in Configuration 'within' chain: "
                        + f"{' -> '.join([*cycle, current])}"
                    )
                path.append(current)
                current = within_map[current]


@dataclass
class DescriptionGroup(Generic[MeasurementClass, MeasurementKind]):
    kinds: list[type[MeasurementClass] | MeasurementKind | ProcessKind | MeasurementMethod] = field(
        default_factory=list
    )
    method: MeasurementMethod | None = None
    group_name: str | None = None
    desc: str | None = None
    source: str | None = None


DEFAULT_SYNTHESIS_GROUP_NAME = "default"


@dataclass
class SynthesisGroup:
    """Structured representation of a synthesis group with template variables."""

    name: str
    """The full event name (e.g., "annealing[Temp]")."""
    base_name: str
    """The base name without brackets (e.g., "annealing")."""
    template_vars: set[str]
    """Set of template variable names (e.g., {"Temp"})."""
    process_events: list[ProcessEvent]
    """List of process events that may contain template placeholders."""

    @classmethod
    def from_name_and_events(cls, name: str, process_events: list[ProcessEvent]) -> "SynthesisGroup":
        """Parse event name and create SynthesisGroup."""
        _check_multiple_bracket_groups(name)
        pattern = r"^([^\[]+)(?:\[([^\]]*)\])?.*$"
        match = re.match(pattern, name)

        if not match:
            raise ValueError(f"Invalid event name format: {name}")

        base_name = match.group(1)
        bracket_content = match.group(2) or ""

        template_vars: set[str] = set()
        if bracket_content:
            for var_name in bracket_content.split(","):
                var_name = var_name.strip()
                if var_name:
                    template_vars.add(var_name)

        return cls(name=name, base_name=base_name, template_vars=template_vars, process_events=process_events)

    def substitute_variables(self, variable_values: dict[str, str]) -> list[ProcessEvent]:
        """Substitute template variables in process events."""
        missing_vars = self.template_vars - set(variable_values.keys())
        if missing_vars:
            raise ValueError(f"Missing values for template variables: {missing_vars}")

        substituted_events = []
        for event in self.process_events:
            substituted_event = self._substitute_in_event(event, variable_values)
            substituted_events.append(substituted_event)

        return substituted_events

    def _substitute_in_event(self, event: ProcessEvent, variable_values: dict[str, str]) -> ProcessEvent:
        """Substitute template variables in a single ProcessEvent."""
        updates = {}

        for field_name, field_value in vars(event).items():
            if field_value is None:
                continue

            if hasattr(field_value, "value"):
                value_str = str(field_value.value)
                substituted_value = self._substitute_in_string(value_str, variable_values)

                if substituted_value != value_str:
                    new_quantity = replace(field_value, value=substituted_value)
                    updates[field_name] = new_quantity

            elif isinstance(field_value, str):
                substituted_value = self._substitute_in_string(field_value, variable_values)
                if substituted_value != field_value:
                    updates[field_name] = substituted_value

            elif isinstance(field_value, list) and all(isinstance(item, str) for item in field_value):
                new_list = [self._substitute_in_string(item, variable_values) for item in field_value]
                if new_list != field_value:
                    updates[field_name] = new_list

        if updates:
            return replace(event, **updates)
        else:
            return event

    def _substitute_in_string(self, text: str, variable_values: dict[str, str]) -> str:
        """Substitute template variables in a string."""
        result = text
        for var_name, var_value in variable_values.items():
            placeholder = f"[{var_name}]"
            result = result.replace(placeholder, var_value)
        return result


def _resolve_type_to_classes(tp: Any) -> tuple[type, ...]:
    """Resolve a type annotation to a tuple of concrete classes for isinstance().

    Handles:
    - Plain classes (e.g. CompMeasurement) -> (CompMeasurement,)
    - TypeAliasType (from ``type X = ...``) -> resolves .__value__ recursively
    - Union types (A | B) -> resolves each member
    - Subscripted generics (Measurement[X]) -> extracts origin class (Measurement)
    """
    if isinstance(tp, type):
        return (tp,)

    if isinstance(tp, TypeAliasType):
        return _resolve_type_to_classes(tp.__value__)

    if isinstance(tp, types.UnionType) or get_origin(tp) is Union:
        results: list[type] = []
        for arg in get_args(tp):
            results.extend(_resolve_type_to_classes(arg))
        return tuple(results)

    origin = get_origin(tp)
    if origin is not None and isinstance(origin, type):
        return (origin,)

    raise TypeError(f"Cannot resolve type {tp!r} to concrete classes for isinstance()")


@dataclass
class Experiment(Generic[MeasurementClass, MeasurementKind]):
    raw_materials: dict[str, RawMaterial]
    synthesis_groups: InitVar[dict[str, list[ProcessEvent]] | list[ProcessEvent]]
    output_materials: list[Material[MeasurementClass]]
    descriptions: list[DescriptionGroup[MeasurementClass, MeasurementKind]] = field(default_factory=list)

    # maps synthesis group's base_name -> SynthesisGroup
    synthesis_group_map: dict[str, "SynthesisGroup"] = field(default_factory=dict, init=False)

    def __post_init__(self, synthesis_groups: dict[str, list[ProcessEvent]] | list[ProcessEvent]) -> None:
        validate_raw_materials_not_empty(self.raw_materials)
        validate_synthesis_groups(synthesis_groups, self.output_materials)

        if isinstance(synthesis_groups, list):
            group = SynthesisGroup.from_name_and_events(DEFAULT_SYNTHESIS_GROUP_NAME, synthesis_groups)
            self.synthesis_group_map = {group.base_name: group}
            default_step = ProcessStep(
                base_name=DEFAULT_SYNTHESIS_GROUP_NAME,
                variables={},
                inputs=list(self.raw_materials.keys()),
            )
            for material in self.output_materials:
                if material.process_steps is None:
                    material.process_steps = [default_step]
        else:
            self.synthesis_group_map = {}
            for name, events in synthesis_groups.items():
                group = SynthesisGroup.from_name_and_events(name, events)
                self.synthesis_group_map[group.base_name] = group

        validate_no_name_collisions(self.raw_materials, self.synthesis_group_map, self.output_materials)
        validate_no_duplicate_materials(self.output_materials)
        validate_all_synthesis_groups_are_used(self.synthesis_group_map, self.output_materials)
        validate_template_vars_used_in_fields(self.synthesis_group_map)
        validate_materials_provide_template_values(self.synthesis_group_map, self.output_materials)
        validate_material_variables_match_group_templates(self.synthesis_group_map, self.output_materials)
        validate_process_event_inputs(self.synthesis_group_map, self.raw_materials, self.output_materials)
        validate_all_raw_materials_used_by_materials(
            self.raw_materials, self.synthesis_group_map, self.output_materials
        )
        validate_melting_followed_by_casting(self.synthesis_group_map, self.output_materials)
        validate_description_groups(self.descriptions, self.output_materials, self.synthesis_group_map)
