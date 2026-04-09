"""Shared code-namespace and execution helpers for alloy benchmarks."""

from typing import cast

from pymatgen.core import Composition
from pymatgen.core.lattice import Lattice

from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod, ProcessKind
from litxbench.core.models import (
    Configuration,
    CoreMeasurementValue,
    GlobalLatticeParam,
    LatticeMeasurement,
    MeasurementStatistic,
)
from litxbench.core.units import (
    HV,
    Atm,
    Celsius,
    GigaPascal,
    Kelvin,
    MegaPascal,
    Micrometer,
    Nanometer,
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
    CompMeasurement,
    Experiment,
    Material,
    Measurement,
    PhaseMeasurementKind,
    ProcessEvent,
    Quantity,
    RawMaterial,
    RawMaterialKind,
    ValueQualifier,
)
from scripts.paper.benchmarks.helpers.prompts import PromptConfig


def build_code_namespace(prompt_config: PromptConfig | None = None) -> dict[str, object]:
    """Build the namespace dict used to execute LLM-generated Experiment code."""
    ns: dict[str, object] = {
        "AlloyDescriptionGroup": AlloyDescriptionGroup,
        "Measurement": Measurement,
        "AlloyMeasurementKind": AlloyMeasurementKind,
        "PhaseMeasurementKind": PhaseMeasurementKind,
        "Composition": Composition,
        "CompositionMeasurement": CompMeasurement,
        "CompMeasurement": CompMeasurement,
        "ProcessEvent": ProcessEvent,
        "ProcessKind": ProcessKind,
        "Experiment": Experiment,
        "Material": Material,
        "Quantity": Quantity,
        "RawMaterial": RawMaterial,
        "RawMaterialKind": RawMaterialKind,
        "ValueQualifier": ValueQualifier,
        "MeasurementStatistic": MeasurementStatistic,
        "CoreMeasurementValue": CoreMeasurementValue,
        "GlobalLatticeParam": GlobalLatticeParam,
        "LatticeMeasurement": LatticeMeasurement,
        "Lattice": Lattice,
        "Configuration": Configuration,
        "CrysStruct": CrysStruct,
        "ConfigTag": ConfigTag,
        "MeasurementMethod": MeasurementMethod,
        "ureg": ureg,
        "HV": HV,
        "GigaPascal": GigaPascal,
        "MegaPascal": MegaPascal,
        "Micrometer": Micrometer,
        "Nanometer": Nanometer,
        "gram_per_cm3": gram_per_cm3,
        "percent": percent,
        "dimensionless": dimensionless,
        "Celsius": Celsius,
        "Kelvin": Kelvin,
        "Atm": Atm,
    }
    cfg = prompt_config or PromptConfig()
    if cfg.include_composition_helpers:
        ns["composition_with_weight_additions"] = composition_with_weight_additions
        ns["balance_composition"] = balance_composition
    if cfg.include_normalize_function:
        from litxbench.core.extraction_utils import normalize

        ns["normalize"] = normalize
    return ns


def execute_experiments_code(code: str, prompt_config: PromptConfig | None = None) -> list[Experiment]:
    """Compile and execute LLM-generated code, returning a list[Experiment]."""
    namespace = build_code_namespace(prompt_config)
    exec(compile(f"_result = {code}", "<experiments_code>", "exec"), namespace)
    return cast(list[Experiment], namespace["_result"])
