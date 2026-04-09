"""Alloy-specific model types and re-exports of framework types."""

from enum import Enum
from typing import Literal, TypeAlias

from litxbench.core.models import (
    CompMeasurement,
    Configuration,
    CoreMeasurements,
    DescriptionGroup,
    Experiment,
    GlobalLatticeParam,
    LatticeMeasurement,
    Material,
    Measurement,
    MeasurementMethod,
    NumericQualifierMixin,
    ProcessEvent,
    ProcessKind,
    Quantity,
    RawMaterial,
    RawMaterialKind,
    ValueQualifier,
)

AlloyMeasurementMethod: TypeAlias = MeasurementMethod
AlloyMeasurement: TypeAlias = Measurement[AlloyMeasurementMethod]

type PhaseKind = Literal["BCC", "FCC", "amorphous"]


class PhaseMeasurementKind(str, Enum):
    volume_fraction = "volume_fraction"
    length = "length"
    grain_size = "grain_size"
    phase_size = "phase_size"  # (could also mean precipitate size)


class AlloyMeasurementKind(str, Enum):
    vickers_hardness = "vickers_hardness"
    berkovich_hardness = "berkovich_hardness"
    pugh_ductility_ratio = "pugh_ductility_ratio"

    density = "density"

    # Note: we merged total_strain_tension with fracture_strain_tension because they are very similar. (we also did the same with the compression counterpart)

    # Tension Parameters
    yield_strength_tension = "yield_strength_tension"  # aka yield strength, yield point, 0.2% offset yield, elastic limit
    ultimate_strain_tension = "ultimate_strain_tension"  # aka peak strain. This is the strain that aligns with the ultimate tensile strength.
    ultimate_tensile_strength = "ultimate_tensile_strength"  # aka UTS, tensile strength, peak tensile stress
    fracture_strain_tension = "fracture_strain_tension"  # aka elongation at fracture, failure strain, ductility, % elongation, total_strain_tension, engineering strain, nominal strain, ductility, plastic strain, plastic elongation
    fracture_strength_tension = "fracture_strength_tension"  # aka breaking stress, rupture strength, stress at failure, stress at fracture, elongation at break
    strain_hardening_exponent_tension = "strain_hardening_exponent_tension"
    poissons_ratio_tension = "poissons_ratio_tension"
    fracture_energy_tension = "fracture_energy_tension"
    true_stress_tension = "true_stress_tension"

    # Compression Parameters
    yield_strength_compression = "yield_strength_compression"  # aka yield strength, compressive yield point
    ultimate_strain_compression = "ultimate_strain_compression"  # aka peak strain. This is the strain that aligns with the ultimate compressive strength.
    ultimate_compressive_strength = "ultimate_compressive_strength"  # aka UCS, crushing strength, max compressive strength
    fracture_strain_compression = "fracture_strain_compression"  # aka strain at crushing, malleability (compressive ductility), total_strain_compression, compressive strain, height reduction
    fracture_strength_compression = "fracture_strength_compression"  # aka crushing stress, breaking stress in compression
    strain_hardening_exponent_compression = "strain_hardening_exponent_compression"
    poissons_ratio_compression = "poissons_ratio_compression"
    fracture_energy_compression = "fracture_energy_compression"
    true_stress_compression = "true_stress_compression"

    elastic_limit_compression = "elastic_limit_compression"
    elastic_limit_tension = "elastic_limit_tension"

    youngs_modulus = "youngs_modulus"  # aka elastic modulus, stiffness
    fracture_toughness = "fracture_toughness"

    work_of_fracture = "work_of_fracture"

    crystallite_size = "crystallite_size"
    lattice_strain = "lattice_strain"

    melting_point = "melting_point"
    solidus = "solidus"
    liquidus = "liquidus"


type AlloyMeasurements = CompMeasurement | AlloyMeasurement | LatticeMeasurement | Configuration | GlobalLatticeParam
type AlloyMeasurementKindUnion = AlloyMeasurementMethod | AlloyMeasurementKind | PhaseMeasurementKind | str


class AlloyDescriptionGroup(DescriptionGroup[AlloyMeasurements, AlloyMeasurementKindUnion]):
    pass


class AlloyMaterial(Material[AlloyMeasurements]):
    pass


class AlloyExperiment(Experiment[AlloyMeasurements, AlloyMeasurementKindUnion]):
    pass


__all__ = [
    "AlloyDescriptionGroup",
    "AlloyExperiment",
    "AlloyMeasurementMethod",
    "AlloyMeasurement",
    "AlloyMeasurementKind",
    "AlloyMeasurementKindUnion",
    "AlloyMeasurements",
    "AlloyMaterial",
    "CompMeasurement",
    "MeasurementMethod",
    "CoreMeasurements",
    "Experiment",
    "GlobalLatticeParam",
    "LatticeMeasurement",
    "Measurement",
    "NumericQualifierMixin",
    "Configuration",
    "PhaseKind",
    "PhaseMeasurementKind",
    "ProcessEvent",
    "ProcessKind",
    "Quantity",
    "RawMaterial",
    "RawMaterialKind",
    "Material",
    "ValueQualifier",
]
