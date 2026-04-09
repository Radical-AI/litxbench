"""Convert parsed JSON dicts into Experiment objects with JSON-path-annotated errors.

Every ``_convert_*`` function takes a ``path: str`` parameter (e.g.
``"experiments[0].output_materials[1]"``) so that when construction fails the
resulting :class:`JsonConversionError` points at the offending location in
the LLM's JSON output.
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any

import pint
from pymatgen.core import Composition
from pymatgen.core.lattice import Lattice

from litxbench.core.enums import (
    ConfigTag,
    CrysStruct,
    MeasurementMethod,
    ProcessKind,
    RawMaterialKind,
)
from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    CoreMeasurementValue,
    GlobalLatticeParam,
    LatticeMeasurement,
    MeasurementStatistic,
)
from litxbench.core.units import (
    HV,
    AmpPerCmSquared,
    Atm,
    Celsius,
    CelsiusPerMinute,
    GigaPascal,
    Hour,
    Kelvin,
    MegaJoulesPerMeterSquared,
    MegaPascal,
    MegaPascalSquareRootMeter,
    Micrometer,
    Millimeter,
    MillimeterPerYear,
    Minute,
    Nanometer,
    RevolutionsPerMinute,
    Second,
    Volt,
    dimensionless,
    gram_per_cm3,
    percent,
    ureg,
)
from litxbench.litxalloy import (
    balance_composition,
    composition_with_weight_additions,
)
from litxbench.litxalloy.models import (
    AlloyDescriptionGroup,
    AlloyMeasurementKind,
    Experiment,
    Material,
    Measurement,
    PhaseMeasurementKind,
    ProcessEvent,
    Quantity,
    RawMaterial,
)
from scripts.paper.benchmarks.helpers.prompts import PromptConfig

# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


class JsonConversionError(Exception):
    """An error that occurred while converting JSON to Experiment objects."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path
        self.message = message
        super().__init__(f"Error at {path}: {message}")


# ---------------------------------------------------------------------------
# Unit resolution
# ---------------------------------------------------------------------------

# Case-insensitive alias map: lowercase key -> pint.Unit
_UNIT_ALIAS_MAP: dict[str, pint.Unit] = {
    "hv": HV,
    "vickers_hardness": HV,
    "gigapascal": GigaPascal,
    "gpa": GigaPascal,
    "megapascal": MegaPascal,
    "mpa": MegaPascal,
    "micrometer": Micrometer,
    "um": Micrometer,
    "μm": Micrometer,
    "millimeter": Millimeter,
    "mm": Millimeter,
    "nanometer": Nanometer,
    "nm": Nanometer,
    "gram_per_cm3": gram_per_cm3,
    "g/cm3": gram_per_cm3,
    "g/cm^3": gram_per_cm3,
    "percent": percent,
    "%": percent,
    "dimensionless": dimensionless,
    "celsius": Celsius,
    "°c": Celsius,
    "c": Celsius,
    "kelvin": Kelvin,
    "k": Kelvin,
    "atm": Atm,
    "megapascal_sqrt_meter": MegaPascalSquareRootMeter,
    "mpa·m^0.5": MegaPascalSquareRootMeter,
    "mpa*m^0.5": MegaPascalSquareRootMeter,
    "mpa√m": MegaPascalSquareRootMeter,
    "megajoules_per_meter_squared": MegaJoulesPerMeterSquared,
    "mj/m2": MegaJoulesPerMeterSquared,
    "mj/m^2": MegaJoulesPerMeterSquared,
    "volt": Volt,
    "v": Volt,
    "amp_per_cm_squared": AmpPerCmSquared,
    "a/cm2": AmpPerCmSquared,
    "a/cm^2": AmpPerCmSquared,
    "millimeter_per_year": MillimeterPerYear,
    "mm/year": MillimeterPerYear,
    "mm/yr": MillimeterPerYear,
    "hour": Hour,
    "h": Hour,
    "minute": Minute,
    "min": Minute,
    "second": Second,
    "s": Second,
    "celsius_per_minute": CelsiusPerMinute,
    "°c/min": CelsiusPerMinute,
    "c/min": CelsiusPerMinute,
    "revolutions_per_minute": RevolutionsPerMinute,
    "rpm": RevolutionsPerMinute,
}


def _resolve_unit(unit_str: str, path: str) -> pint.Unit:
    """Resolve a unit string to a pint.Unit, with permissive alias matching."""
    key = unit_str.strip().lower()
    if key in _UNIT_ALIAS_MAP:
        return _UNIT_ALIAS_MAP[key]
    # Try the original string as-is (pint may accept it)
    try:
        return ureg.Unit(unit_str)
    except Exception:
        pass
    # Try lowercase
    try:
        return ureg.Unit(key)
    except Exception:
        pass
    predefined = ", ".join(sorted(set(_UNIT_ALIAS_MAP.keys())))
    raise JsonConversionError(
        path,
        f"Unknown unit '{unit_str}'. Predefined unit aliases: {predefined}. "
        f"You can also use any standard pint unit name.",
    )


# ---------------------------------------------------------------------------
# Enum resolution
# ---------------------------------------------------------------------------


def _resolve_enum(value: str, enum_class: type[Enum], path: str) -> Any:
    """Resolve a string to an enum member (by name, then value, then case-insensitive)."""
    # Try exact name match
    try:
        return enum_class[value]
    except KeyError:
        pass
    # Try exact value match
    for member in enum_class:
        if member.value == value:
            return member
    # Case-insensitive name match
    lower = value.lower()
    for member in enum_class:
        if member.name.lower() == lower:
            return member
    # Case-insensitive value match
    for member in enum_class:
        if isinstance(member.value, str) and member.value.lower() == lower:
            return member
    valid = ", ".join(f"'{m.name}'" for m in enum_class)
    raise JsonConversionError(
        path,
        f"Unknown {enum_class.__name__} value '{value}'. Valid members: {valid}",
    )


def _resolve_measurement_kind(value: str, path: str) -> str:
    """Resolve a measurement kind string to a valid AlloyMeasurementKind or PhaseMeasurementKind name."""
    # Try AlloyMeasurementKind first
    try:
        return _resolve_enum(value, AlloyMeasurementKind, path).value
    except JsonConversionError:
        pass
    # Try PhaseMeasurementKind
    try:
        return _resolve_enum(value, PhaseMeasurementKind, path).value
    except JsonConversionError:
        pass
    alloy_names = ", ".join(f"'{m.name}'" for m in AlloyMeasurementKind)
    phase_names = ", ".join(f"'{m.name}'" for m in PhaseMeasurementKind)
    raise JsonConversionError(
        path,
        f"Unknown measurement kind '{value}'. "
        f"Valid AlloyMeasurementKind members: {alloy_names}. "
        f"Valid PhaseMeasurementKind members: {phase_names}.",
    )


# ---------------------------------------------------------------------------
# Quantity conversion
# ---------------------------------------------------------------------------


def _convert_quantity(data: dict, path: str) -> Quantity:
    """Convert a JSON quantity dict to a Quantity object."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for Quantity, got {type(data).__name__}")
    value = data.get("value")
    if value is None:
        raise JsonConversionError(path, "Quantity must have a 'value' field")
    unit_str = data.get("unit")
    if unit_str is None:
        raise JsonConversionError(path, "Quantity must have a 'unit' field")
    unit = _resolve_unit(str(unit_str), f"{path}.unit")
    try:
        return Quantity(
            value=value,
            unit=unit,
            description=data.get("description"),
            source=data.get("source"),
        )
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Composition conversion
# ---------------------------------------------------------------------------


def _convert_composition(data: str | dict, path: str, prompt_config: PromptConfig | None = None) -> Composition:
    """Convert a composition value (string, dict, or helper invocation) to a pymatgen Composition."""
    if isinstance(data, str):
        try:
            return Composition(data)
        except Exception as exc:
            raise JsonConversionError(path, f"Invalid composition formula '{data}': {exc}") from exc
    if isinstance(data, dict):
        # Check for helper invocations
        helper = data.get("_helper")
        if helper is not None:
            cfg = prompt_config or PromptConfig()
            if not cfg.include_composition_helpers:
                raise JsonConversionError(
                    path,
                    f"Composition helper '{helper}' used but composition helpers are not enabled.",
                )
            return _invoke_composition_helper(data, path)
        # Element dict like {"Co": 25, "Cr": 25}
        try:
            return Composition(data)
        except Exception as exc:
            raise JsonConversionError(path, f"Invalid composition dict: {exc}") from exc
    raise JsonConversionError(path, f"Expected a string or object for composition, got {type(data).__name__}")


def _invoke_composition_helper(data: dict, path: str) -> Composition:
    """Dispatch a composition helper invocation."""
    helper = data["_helper"]
    if helper == "balance_composition":
        main_element = data.get("main_element")
        additions = data.get("additions")
        if main_element is None or additions is None:
            raise JsonConversionError(
                path,
                "balance_composition requires 'main_element' (str) and 'additions' (dict) fields.",
            )
        try:
            return balance_composition(main_element, additions)
        except Exception as exc:
            raise JsonConversionError(path, f"balance_composition failed: {exc}") from exc
    elif helper == "from_weight_dict":
        weights = data.get("weights")
        if weights is None:
            raise JsonConversionError(path, "from_weight_dict requires a 'weights' (dict) field.")
        try:
            return Composition.from_weight_dict(weights)
        except Exception as exc:
            raise JsonConversionError(path, f"Composition.from_weight_dict failed: {exc}") from exc
    elif helper == "weight_additions":
        base = data.get("base")
        additions_weights = data.get("additions_weights")
        fraction = data.get("fraction")
        if base is None or additions_weights is None or fraction is None:
            raise JsonConversionError(
                path,
                "weight_additions requires 'base' (str), 'additions_weights' (dict), and 'fraction' (float) fields.",
            )
        try:
            base_comp = Composition(base) if isinstance(base, str) else Composition(base)
            add_comp = Composition.from_weight_dict(additions_weights)
            return composition_with_weight_additions(base_comp, add_comp, fraction)
        except Exception as exc:
            raise JsonConversionError(path, f"composition_with_weight_additions failed: {exc}") from exc
    else:
        raise JsonConversionError(
            path,
            f"Unknown composition helper '{helper}'. Valid: balance_composition, from_weight_dict, weight_additions",
        )


# ---------------------------------------------------------------------------
# Lattice conversion
# ---------------------------------------------------------------------------


def _convert_lattice(data: dict, path: str) -> Lattice:
    """Convert a JSON lattice dict to a pymatgen Lattice."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for lattice, got {type(data).__name__}")
    lattice_type = data.get("type", "").lower()
    a = data.get("a")
    if a is None:
        raise JsonConversionError(path, "Lattice must have an 'a' parameter")
    try:
        if lattice_type == "cubic":
            return Lattice.cubic(a)
        elif lattice_type == "hexagonal":
            c = data.get("c")
            if c is None:
                raise JsonConversionError(path, "Hexagonal lattice must have a 'c' parameter")
            return Lattice.hexagonal(a, c)
        elif lattice_type == "tetragonal":
            c = data.get("c")
            if c is None:
                raise JsonConversionError(path, "Tetragonal lattice must have a 'c' parameter")
            return Lattice.tetragonal(a, c)
        elif lattice_type == "orthorhombic":
            b = data.get("b")
            c = data.get("c")
            if b is None or c is None:
                raise JsonConversionError(path, "Orthorhombic lattice must have 'b' and 'c' parameters")
            return Lattice.orthorhombic(a, b, c)
        else:
            raise JsonConversionError(
                path,
                f"Unknown lattice type '{lattice_type}'. Valid types: cubic, hexagonal, tetragonal, orthorhombic",
            )
    except JsonConversionError:
        raise
    except Exception as exc:
        raise JsonConversionError(path, f"Lattice construction failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Measurement conversion
# ---------------------------------------------------------------------------


def _convert_measurement(data: dict, path: str, prompt_config: PromptConfig | None = None) -> list:
    """Convert a single measurement JSON object into one or more measurement objects.

    Returns a list because ``group_measurements`` can expand into multiple items.
    """
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for measurement, got {type(data).__name__}")

    mtype = data.get("_type", "measurement")

    if mtype == "composition":
        return [_convert_comp_measurement(data, path, prompt_config)]
    elif mtype == "measurement":
        return [_convert_single_measurement(data, path)]
    elif mtype == "group_measurements":
        return _convert_group_measurements(data, path)
    elif mtype == "lattice_param":
        return [_convert_global_lattice_param(data, path)]
    elif mtype == "configuration":
        return [_convert_configuration(data, path, prompt_config)]
    else:
        raise JsonConversionError(
            path,
            f"Unknown measurement _type '{mtype}'. "
            "Valid types: composition, measurement, group_measurements, lattice_param, configuration",
        )


def _convert_comp_measurement(data: dict, path: str, prompt_config: PromptConfig | None = None) -> CompMeasurement:
    """Convert a composition measurement JSON to CompMeasurement."""
    comp_data = data.get("composition")
    if comp_data is None:
        raise JsonConversionError(path, "Composition measurement must have a 'composition' field")
    comp = _convert_composition(comp_data, f"{path}.composition", prompt_config)
    method = MeasurementMethod.Unspecified
    if "method" in data and data["method"] is not None:
        method = _resolve_enum(str(data["method"]), MeasurementMethod, f"{path}.method")
    try:
        return CompMeasurement(
            composition=comp,
            method=method,
            description=data.get("description"),
            source=data.get("source"),
        )
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


def _convert_single_measurement(data: dict, path: str) -> Measurement:
    """Convert a single measurement JSON to a Measurement object."""
    kind = data.get("kind")
    if kind is None:
        raise JsonConversionError(path, "Measurement must have a 'kind' field")
    resolved_kind = _resolve_measurement_kind(str(kind), f"{path}.kind")

    value = data.get("value")
    if value is None:
        raise JsonConversionError(path, "Measurement must have a 'value' field")

    unit_str = data.get("unit")
    if unit_str is None:
        raise JsonConversionError(path, "Measurement must have a 'unit' field")
    unit = _resolve_unit(str(unit_str), f"{path}.unit")

    kwargs: dict[str, Any] = {
        "kind": resolved_kind,
        "value": value,
        "unit": unit,
    }
    if "uncertainty" in data and data["uncertainty"] is not None:
        kwargs["uncertainty"] = data["uncertainty"]
    if "measurement_method" in data and data["measurement_method"] is not None:
        kwargs["measurement_method"] = _resolve_enum(
            str(data["measurement_method"]), MeasurementMethod, f"{path}.measurement_method"
        )
    if "description" in data and data["description"] is not None:
        kwargs["description"] = data["description"]
    if "source" in data and data["source"] is not None:
        kwargs["source"] = data["source"]
    if "temperature" in data and data["temperature"] is not None:
        kwargs["temperature"] = _convert_quantity(data["temperature"], f"{path}.temperature")
    if "pressure" in data and data["pressure"] is not None:
        kwargs["pressure"] = _convert_quantity(data["pressure"], f"{path}.pressure")
    if "measurement_statistic" in data and data["measurement_statistic"] is not None:
        kwargs["measurement_statistic"] = _resolve_enum(
            str(data["measurement_statistic"]), MeasurementStatistic, f"{path}.measurement_statistic"
        )
    if "percentile" in data and data["percentile"] is not None:
        kwargs["percentile"] = data["percentile"]
    if "group_name" in data and data["group_name"] is not None:
        kwargs["group_name"] = data["group_name"]

    try:
        return Measurement(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


def _convert_group_measurements(data: dict, path: str) -> list[Measurement]:
    """Convert a group_measurements JSON to a list of Measurement objects."""
    kind = data.get("kind")
    if kind is None:
        raise JsonConversionError(path, "group_measurements must have a 'kind' field")
    resolved_kind = _resolve_measurement_kind(str(kind), f"{path}.kind")

    unit_str = data.get("unit")
    if unit_str is None:
        raise JsonConversionError(path, "group_measurements must have a 'unit' field")
    unit = _resolve_unit(str(unit_str), f"{path}.unit")

    values_data = data.get("values")
    if not isinstance(values_data, list) or len(values_data) < 2:
        raise JsonConversionError(path, "group_measurements 'values' must be a list with at least 2 items")

    core_values: list[CoreMeasurementValue] = []
    for i, vd in enumerate(values_data):
        vpath = f"{path}.values[{i}]"
        if not isinstance(vd, dict):
            raise JsonConversionError(vpath, f"Expected an object, got {type(vd).__name__}")
        stat = vd.get("statistic")
        if stat is None:
            raise JsonConversionError(vpath, "Each value must have a 'statistic' field")
        val = vd.get("value")
        if val is None:
            raise JsonConversionError(vpath, "Each value must have a 'value' field")
        try:
            core_values.append(
                CoreMeasurementValue(
                    statistic=_resolve_enum(str(stat), MeasurementStatistic, f"{vpath}.statistic"),
                    value=val,
                    uncertainty=vd.get("uncertainty"),
                    description=vd.get("description"),
                    source=vd.get("source"),
                    percentile=vd.get("percentile"),
                )
            )
        except JsonConversionError:
            raise
        except Exception as exc:
            raise JsonConversionError(vpath, str(exc)) from exc

    kwargs: dict[str, Any] = {
        "kind": resolved_kind,
        "unit": unit,
        "values": core_values,
    }
    if "measurement_method" in data and data["measurement_method"] is not None:
        kwargs["measurement_method"] = _resolve_enum(
            str(data["measurement_method"]), MeasurementMethod, f"{path}.measurement_method"
        )
    if "description" in data and data["description"] is not None:
        kwargs["description"] = data["description"]
    if "uncertainty" in data and data["uncertainty"] is not None:
        kwargs["uncertainty"] = data["uncertainty"]
    if "source" in data and data["source"] is not None:
        kwargs["source"] = data["source"]
    if "temperature" in data and data["temperature"] is not None:
        kwargs["temperature"] = _convert_quantity(data["temperature"], f"{path}.temperature")
    if "pressure" in data and data["pressure"] is not None:
        kwargs["pressure"] = _convert_quantity(data["pressure"], f"{path}.pressure")
    if "group_name" in data and data["group_name"] is not None:
        kwargs["group_name"] = data["group_name"]

    try:
        return Measurement.group_measurements(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


def _convert_global_lattice_param(data: dict, path: str) -> GlobalLatticeParam:
    """Convert a lattice_param JSON to a GlobalLatticeParam object."""
    kwargs: dict[str, Any] = {}

    if "lattice" in data and data["lattice"] is not None:
        lattice = _convert_lattice(data["lattice"], f"{path}.lattice")
        kwargs["lattice"] = LatticeMeasurement(
            lattice=lattice,
            description=data.get("lattice", {}).get("description") if isinstance(data.get("lattice"), dict) else None,
            source=data.get("lattice", {}).get("source") if isinstance(data.get("lattice"), dict) else None,
        )
    if "struct" in data and data["struct"] is not None:
        kwargs["struct"] = _resolve_enum(str(data["struct"]), CrysStruct, f"{path}.struct")
    if "name" in data and data["name"] is not None:
        kwargs["name"] = data["name"]
    if "description" in data and data["description"] is not None:
        kwargs["description"] = data["description"]
    if "source" in data and data["source"] is not None:
        kwargs["source"] = data["source"]
    if "phase_fraction" in data and data["phase_fraction"] is not None:
        kwargs["phase_fraction"] = _convert_quantity(data["phase_fraction"], f"{path}.phase_fraction")

    try:
        return GlobalLatticeParam(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


def _convert_configuration(data: dict, path: str, prompt_config: PromptConfig | None = None) -> Configuration:
    """Convert a configuration JSON to a Configuration object."""
    kwargs: dict[str, Any] = {}
    if "name" in data and data["name"] is not None:
        kwargs["name"] = data["name"]
    if "within" in data and data["within"] is not None:
        kwargs["within"] = data["within"]
    if "struct" in data and data["struct"] is not None:
        kwargs["struct"] = _resolve_enum(str(data["struct"]), CrysStruct, f"{path}.struct")
    if "tags" in data and data["tags"] is not None:
        tags_data = data["tags"]
        if not isinstance(tags_data, list):
            raise JsonConversionError(f"{path}.tags", f"Expected a list, got {type(tags_data).__name__}")
        kwargs["tags"] = {_resolve_enum(str(t), ConfigTag, f"{path}.tags[{i}]") for i, t in enumerate(tags_data)}
    if "description" in data and data["description"] is not None:
        kwargs["description"] = data["description"]
    if "source" in data and data["source"] is not None:
        kwargs["source"] = data["source"]

    # Convert nested measurements
    measurements_data = data.get("measurements", [])
    measurements = []
    for i, md in enumerate(measurements_data):
        mpath = f"{path}.measurements[{i}]"
        measurements.extend(_convert_measurement(md, mpath, prompt_config))
    kwargs["measurements"] = measurements

    try:
        return Configuration(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Material conversion
# ---------------------------------------------------------------------------


def _convert_material(data: dict, path: str, prompt_config: PromptConfig | None = None) -> Material:
    """Convert a JSON material dict to a Material object."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for material, got {type(data).__name__}")

    kwargs: dict[str, Any] = {}
    if "process" in data and data["process"] is not None:
        kwargs["process"] = data["process"]
    if "name" in data and data["name"] is not None:
        kwargs["name"] = data["name"]

    measurements_data = data.get("measurements", [])
    if not isinstance(measurements_data, list):
        raise JsonConversionError(f"{path}.measurements", f"Expected a list, got {type(measurements_data).__name__}")

    measurements = []
    for i, md in enumerate(measurements_data):
        mpath = f"{path}.measurements[{i}]"
        measurements.extend(_convert_measurement(md, mpath, prompt_config))
    kwargs["measurements"] = measurements

    try:
        return Material(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Process event conversion
# ---------------------------------------------------------------------------


def _convert_process_event(data: dict, path: str) -> ProcessEvent:
    """Convert a JSON process event dict to a ProcessEvent object."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for process event, got {type(data).__name__}")

    kind_str = data.get("kind")
    if kind_str is None:
        raise JsonConversionError(path, "ProcessEvent must have a 'kind' field")
    kind = _resolve_enum(str(kind_str), ProcessKind, f"{path}.kind")

    kwargs: dict[str, Any] = {"kind": kind}
    if "description" in data and data["description"] is not None:
        kwargs["description"] = data["description"]
    if "source" in data and data["source"] is not None:
        kwargs["source"] = data["source"]
    if "equipment" in data and data["equipment"] is not None:
        kwargs["equipment"] = data["equipment"]
    if "temperature" in data and data["temperature"] is not None:
        kwargs["temperature"] = _convert_quantity(data["temperature"], f"{path}.temperature")
    if "duration" in data and data["duration"] is not None:
        kwargs["duration"] = _convert_quantity(data["duration"], f"{path}.duration")
    if "inputs" in data and data["inputs"] is not None:
        inputs = data["inputs"]
        if not isinstance(inputs, list):
            raise JsonConversionError(f"{path}.inputs", f"Expected a list, got {type(inputs).__name__}")
        kwargs["inputs"] = inputs

    try:
        return ProcessEvent(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Raw materials conversion
# ---------------------------------------------------------------------------


def _convert_raw_materials(data: dict, path: str) -> dict[str, RawMaterial]:
    """Convert a JSON raw_materials dict to a dict of RawMaterial objects."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for raw_materials, got {type(data).__name__}")

    result: dict[str, RawMaterial] = {}
    for name, rm_data in data.items():
        rm_path = f"{path}.{name}"
        if not isinstance(rm_data, dict):
            raise JsonConversionError(rm_path, f"Expected an object for raw material, got {type(rm_data).__name__}")

        kind_str = rm_data.get("kind")
        if kind_str is None:
            raise JsonConversionError(rm_path, "RawMaterial must have a 'kind' field")
        kind = _resolve_enum(str(kind_str), RawMaterialKind, f"{rm_path}.kind")

        try:
            result[name] = RawMaterial(
                kind=kind,
                description=rm_data.get("description"),
                source=rm_data.get("source"),
            )
        except Exception as exc:
            raise JsonConversionError(rm_path, str(exc)) from exc

    return result


# ---------------------------------------------------------------------------
# Description group conversion
# ---------------------------------------------------------------------------


def _convert_description_group(data: dict, path: str) -> AlloyDescriptionGroup:
    """Convert a JSON description group dict to an AlloyDescriptionGroup."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for description group, got {type(data).__name__}")

    kinds_data = data.get("kinds", [])
    if not isinstance(kinds_data, list):
        raise JsonConversionError(f"{path}.kinds", f"Expected a list, got {type(kinds_data).__name__}")

    kinds: list = []
    for i, k in enumerate(kinds_data):
        kpath = f"{path}.kinds[{i}]"
        k_str = str(k)
        # Try AlloyMeasurementKind
        try:
            kinds.append(_resolve_enum(k_str, AlloyMeasurementKind, kpath))
            continue
        except JsonConversionError:
            pass
        # Try PhaseMeasurementKind
        try:
            kinds.append(_resolve_enum(k_str, PhaseMeasurementKind, kpath))
            continue
        except JsonConversionError:
            pass
        # Try ProcessKind
        try:
            kinds.append(_resolve_enum(k_str, ProcessKind, kpath))
            continue
        except JsonConversionError:
            pass
        # Try MeasurementMethod
        try:
            kinds.append(_resolve_enum(k_str, MeasurementMethod, kpath))
            continue
        except JsonConversionError:
            pass
        raise JsonConversionError(
            kpath,
            f"'{k_str}' is not a valid AlloyMeasurementKind, PhaseMeasurementKind, ProcessKind, or MeasurementMethod.",
        )

    kwargs: dict[str, Any] = {"kinds": kinds}
    # Resolve "method" field (singular MeasurementMethod | None).
    # Also accept legacy "measurement_methods" (list) or "measurement_method" (singular) keys.
    method_val: MeasurementMethod | None = None
    if "method" in data and data["method"] is not None:
        method_val = _resolve_enum(str(data["method"]), MeasurementMethod, f"{path}.method")
    elif "measurement_methods" in data and data["measurement_methods"] is not None:
        mm_data = data["measurement_methods"]
        if isinstance(mm_data, list) and mm_data:
            method_val = _resolve_enum(str(mm_data[0]), MeasurementMethod, f"{path}.measurement_methods[0]")
        elif isinstance(mm_data, str):
            method_val = _resolve_enum(mm_data, MeasurementMethod, f"{path}.measurement_methods")
    elif "measurement_method" in data and data["measurement_method"] is not None:
        method_val = _resolve_enum(str(data["measurement_method"]), MeasurementMethod, f"{path}.measurement_method")
    if method_val is not None:
        kwargs["method"] = method_val
    if "group_name" in data and data["group_name"] is not None:
        kwargs["group_name"] = data["group_name"]
    if "desc" in data and data["desc"] is not None:
        kwargs["desc"] = data["desc"]

    try:
        return AlloyDescriptionGroup(**kwargs)
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Experiment conversion
# ---------------------------------------------------------------------------


def _convert_experiment(data: dict, path: str, prompt_config: PromptConfig | None = None) -> Experiment:
    """Convert a single experiment JSON dict to an Experiment object."""
    if not isinstance(data, dict):
        raise JsonConversionError(path, f"Expected an object for experiment, got {type(data).__name__}")

    # raw_materials
    rm_data = data.get("raw_materials")
    if rm_data is None:
        raise JsonConversionError(path, "Experiment must have a 'raw_materials' field")
    raw_materials = _convert_raw_materials(rm_data, f"{path}.raw_materials")

    # synthesis_groups
    sg_data = data.get("synthesis_groups")
    if sg_data is None:
        raise JsonConversionError(path, "Experiment must have a 'synthesis_groups' field")
    if not isinstance(sg_data, dict):
        raise JsonConversionError(
            f"{path}.synthesis_groups",
            f"Expected an object mapping group names to lists of process events, got {type(sg_data).__name__}",
        )
    synthesis_groups: dict[str, list[ProcessEvent]] = {}
    for sg_name, events_data in sg_data.items():
        sg_path = f"{path}.synthesis_groups.{sg_name}"
        if not isinstance(events_data, list):
            raise JsonConversionError(sg_path, f"Expected a list of process events, got {type(events_data).__name__}")
        events = []
        for j, ev_data in enumerate(events_data):
            events.append(_convert_process_event(ev_data, f"{sg_path}[{j}]"))
        synthesis_groups[sg_name] = events

    # output_materials
    os_data = data.get("output_materials")
    if os_data is None:
        raise JsonConversionError(path, "Experiment must have an 'output_materials' field")
    if not isinstance(os_data, list):
        raise JsonConversionError(
            f"{path}.output_materials",
            f"Expected a list of materials, got {type(os_data).__name__}",
        )
    output_materials = []
    for i, s_data in enumerate(os_data):
        output_materials.append(_convert_material(s_data, f"{path}.output_materials[{i}]", prompt_config))

    # descriptions (optional)
    descriptions = []
    desc_data = data.get("descriptions", [])
    if isinstance(desc_data, list):
        for i, d_data in enumerate(desc_data):
            descriptions.append(_convert_description_group(d_data, f"{path}.descriptions[{i}]"))

    try:
        return Experiment(
            raw_materials=raw_materials,
            synthesis_groups=synthesis_groups,
            output_materials=output_materials,
            descriptions=descriptions,
        )
    except Exception as exc:
        raise JsonConversionError(path, str(exc)) from exc


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def json_to_experiments(data: list[dict], prompt_config: PromptConfig | None = None) -> list[Experiment]:
    """Convert a list of JSON experiment dicts to a list of Experiment objects.

    Raises :class:`JsonConversionError` on the first error encountered.
    """
    if not isinstance(data, list):
        raise JsonConversionError("(root)", f"Top-level JSON must be an array, got {type(data).__name__}")

    experiments: list[Experiment] = []
    for i, exp_data in enumerate(data):
        experiments.append(_convert_experiment(exp_data, f"experiments[{i}]", prompt_config))
    return experiments


def parse_and_construct(json_str: str, prompt_config: PromptConfig | None = None) -> list[Experiment]:
    """Parse a JSON string and construct Experiment objects.

    Raises ``ValueError`` for JSON parse errors, ``TypeError`` for wrong
    top-level type, and :class:`JsonConversionError` for construction errors.
    """
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON parse error at line {exc.lineno}, col {exc.colno}: {exc.msg}. "
            f"Fix the JSON syntax and return corrected JSON."
        ) from exc

    if not isinstance(data, list):
        raise TypeError(f"Top-level JSON must be an array of experiment objects, got {type(data).__name__}.")

    return json_to_experiments(data, prompt_config)
