from enum import Enum

from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    CompMeasurement,
    Experiment,
    Material,
    Measurement,
)


class MeasurementKind(str, Enum):
    hardness = "hardness"
    ultimate_tensile_strength = "ultimate_tensile_strength"
    yield_strength = "yield_strength"
    composition = "composition"


def filter_materials_by_measurement_kinds(
    materials_by_doi: dict[str, list[Material]],
    measurement_kinds: list[AlloyMeasurementKind] | None,
) -> dict[str, list[Material]]:
    """
    Filter materials to only include those with specific measurement kinds.

    Args:
        materials_by_doi: Map of DOIs to their materials
        measurement_kinds: List of AlloyMeasurementKind to keep, or None to keep all materials

    Returns:
        Map of DOIs to filtered materials, excluding DOIs with no matching materials
    """
    if measurement_kinds is None:
        return {doi: materials for doi, materials in materials_by_doi.items() if materials}

    filtered_results = {}
    for doi, materials in materials_by_doi.items():
        filtered_materials = []
        for material in materials:
            has_measurement = any(
                isinstance(m, Measurement) and m.kind in measurement_kinds for m in material.measurements
            )
            if has_measurement:
                filtered_materials.append(material)

        if filtered_materials:
            filtered_results[doi] = filtered_materials

    return filtered_results


def write_materials_to_file(
    extracted: dict[str, list[Experiment]],
    target: dict[str, list[Material]],
    output_file: str = "extracted_materials_output.txt",
) -> None:
    """Write extracted and target materials to a file for manual verification."""

    def write_material(f, material: Material, index: int) -> None:
        f.write(f"  Material {index}:\n")
        compositions = [m for m in material.measurements if isinstance(m, CompMeasurement)]
        other_measurements = [m for m in material.measurements if isinstance(m, Measurement)]
        f.write(f"    Compositions: {compositions}\n")
        f.write("    Measurements:\n")
        for m in other_measurements:
            f.write(f"      - {m.kind.value}: {m.value} {m.unit}")
            if m.uncertainty:
                f.write(f" ± {m.uncertainty}")
            f.write("\n")

    with open(output_file, "w") as f:
        f.write("=" * 80 + "\n")
        f.write("EXTRACTED MATERIALS\n")
        f.write("=" * 80 + "\n\n")
        for doi, experiments in extracted.items():
            f.write(f"DOI: {doi}\n")
            f.write("-" * 40 + "\n")
            material_index = 1
            for exp in experiments:
                for material in exp.output_materials:
                    write_material(f, material, material_index)
                    material_index += 1
            f.write("\n")

        f.write("=" * 80 + "\n")
        f.write("TARGET MATERIALS (for comparison)\n")
        f.write("=" * 80 + "\n\n")
        for doi, materials in target.items():
            f.write(f"DOI: {doi}\n")
            f.write("-" * 40 + "\n")
            for i, material in enumerate(materials):
                write_material(f, material, i + 1)
            f.write("\n")
    print(f"\nExtracted materials written to: {output_file}")
