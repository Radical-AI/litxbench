# %% [markdown]
# # LitXBench Usage Example
#
# This notebook walks through the core workflow:
# 1. Load ground-truth extractions from the dataset
# 2. Build your own extraction as `Experiment` objects
# 3. Evaluate with precision, recall, and F1

# %% Load ground truth
from litxbench.litxalloy import papers

# The dataset maps DOI strings to list[Experiment]
print(f"Papers in dataset: {len(papers)}")
print(f"Available DOIs: {list(papers.keys())[:5]} ...")

doi = "doi_10_3390__e21020122"
ground_truth = papers[doi]
print(f"\nLoaded {len(ground_truth)} experiment(s) for {doi}")

# %% Inspect the ground truth
for i, exp in enumerate(ground_truth):
    print(f"Experiment {i}:")
    print(f"  Raw materials: {list(exp.raw_materials.keys())}")
    print(f"  Output materials: {len(exp.output_materials)}")
    for j, mat in enumerate(exp.output_materials):
        print(mat)

# %% Perform an extraction. The output is a list of experiments
from pymatgen.core.composition import Composition

from litxbench import (
    CompMeasurement,
    Configuration,
    CrysStruct,
    Experiment,
    Material,
    Measurement,
    ProcessEvent,
    ProcessKind,
    Quantity,
    RawMaterial,
    RawMaterialKind,
)
from litxbench.core.models import GlobalLatticeParam
from litxbench.core.units import HV, Celsius, Hour, MegaPascal, Nanometer, gram_per_cm3, percent
from litxbench.litxalloy.models import AlloyMeasurementKind

# Synthesis groups can use template variables (e.g. [Duration], [Temp])
# that are substituted per-material via process strings.
extracted = [
    Experiment(
        raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Powder)},
        synthesis_groups={
            "Milling[Duration]": [
                ProcessEvent(
                    kind=ProcessKind.PlanetaryMilling,
                    duration=Quantity(value="[Duration]", unit=Hour),
                ),
            ],
            "SPS[Temp]": [
                ProcessEvent(
                    kind=ProcessKind.SparkPlasmaSintering,
                    temperature=Quantity(value="[Temp]", unit=Celsius),
                ),
            ],
        },
        output_materials=[
            # Named materials can be referenced as inputs by later materials
            Material(
                process="elements->Milling[Duration=60]",
                name="base",
                measurements=[
                    CompMeasurement(Composition("CoCrNiCuZn")),
                    GlobalLatticeParam(
                        struct=CrysStruct.BCC,
                        phase_fraction=Quantity(value=100, unit=percent),
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.crystallite_size,
                        value=13,
                        unit=Nanometer,
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.lattice_strain,
                        value=0.7,
                        unit=percent,
                    ),
                    # Configurations represent distinct phases within a material
                    Configuration(
                        name="Phase 1",
                        measurements=[
                            Measurement(
                                kind=AlloyMeasurementKind.solidus,
                                value=1244.8,
                                unit=Celsius,
                            ),
                        ],
                    ),
                ],
            ),
            # This material chains from "base" through the SPS synthesis group
            Material(
                process="base->SPS[Temp=900]",
                measurements=[
                    CompMeasurement(Composition("CoCrNiCuZn")),
                    Measurement(
                        kind=AlloyMeasurementKind.density,
                        value=7.89,
                        unit=gram_per_cm3,
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.ultimate_compressive_strength,
                        value=2121,
                        unit=MegaPascal,
                    ),
                    Measurement(
                        kind=AlloyMeasurementKind.vickers_hardness,
                        value=615,
                        unit=HV,
                    ),
                    GlobalLatticeParam(struct=CrysStruct.FCC, name="FCC1"),
                    GlobalLatticeParam(struct=CrysStruct.FCC, name="FCC2"),
                ],
            ),
        ],
    ),
]

print(f"Built {len(extracted)} extracted experiment(s)")

# %% Evaluate: basic precision / recall / F1
from litxbench import compare_experiments

result = compare_experiments(ground_truth, extracted)

print(f"Matched materials:   {result.num_matched_materials}")
print(f"Target materials:    {result.num_target_materials}")
print(f"Extracted materials: {result.num_extracted_materials}")
print()
print(f"Precision: {result.precision:.2%}")
print(f"Recall:    {result.recall:.2%}")
print(f"F1:        {result.f1:.2%}")

# %% Evaluate: multi-level metrics
from litxbench.core.eval import compute_multi_level_metrics

metrics = compute_multi_level_metrics(result)

print("Multi-level F1 scores:")
print(f"  Value F1:       {metrics.value_f1:.2%}")
print(f"  Measurement F1: {metrics.measurement_f1:.2%}")
print(f"  Config F1:      {metrics.config_f1:.2%}")
print(f"  Process F1:     {metrics.process_f1:.2%}")
print(f"  Material F1:    {metrics.material_f1:.2%}")
print()
print(f"  Overall F1:     {metrics.overall_f1:.2%}")

# %%
