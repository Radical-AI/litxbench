Introduction
============

LitXBench is a benchmark for evaluating methods that extract experiments from scientific literature.
It ships with **LitXAlloy**, a dense benchmark of 1426 measurements from 19 alloy papers, along
with evaluation tools to measure how well an extraction method captures the materials, processes,
and measurements reported in a paper.

| `GitHub <https://github.com/Radical-AI/litxbench>`_ | `PyPI <https://pypi.org/project/litxbench>`_ | `Paper <https://arxiv.org/pdf/2604.03099>`_ |

Installation
------------

.. code-block:: bash

   uv pip install litxbench

Quick Start
-----------

**Load Ground Truth**

You can load the ground truth experiments for each paper in LitXAlloy by querying the papers dictionary.

.. code-block:: python

   from litxbench.litxalloy import papers

   # papers maps DOI strings to list[Experiment]
   doi = "doi_10_3390__e21020122"
   ground_truth = papers[doi]

**Build an extraction**

Extracted materials are represented as ``Experiment`` objects. Each experiment contains raw materials,
synthesis groups, and the synthesized materials with their measurements.

.. code-block:: python

   from pymatgen.core.composition import Composition
   from litxbench import (
       CompMeasurement, Configuration, CrysStruct, Experiment, Material,
       Measurement, ProcessEvent, ProcessKind, Quantity, RawMaterial, RawMaterialKind,
   )
   from litxbench.core.models import GlobalLatticeParam
   from litxbench.core.units import Celsius, Hour, MegaPascal, Nanometer, gram_per_cm3, percent, HV
   from litxbench.litxalloy.models import AlloyMeasurementKind

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
                   ],
               ),
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
                           kind=AlloyMeasurementKind.vickers_hardness,
                           value=615,
                           unit=HV,
                       ),
                   ],
               ),
           ],
       ),
   ]

**Evaluate**

Compare your extractions against the ground truth to get precision, recall, and F1 scores.

.. code-block:: python

   from litxbench import compare_experiments

   result = compare_experiments(ground_truth, extracted)
   print(f"Precision: {result.precision:.2%}")
   print(f"Recall:    {result.recall:.2%}")
   print(f"F1:        {result.f1:.2%}")

For multi-level metrics (value, measurement, configuration, process, and material levels):

.. code-block:: python

   from litxbench.core.eval import compute_multi_level_metrics

   metrics = compute_multi_level_metrics(result)
   print(f"Overall F1: {metrics.overall_f1:.2%}")
   print(f"Value F1:   {metrics.value_f1:.2%}")
   print(f"Process F1: {metrics.process_f1:.2%}")

A complete end-to-end example is available at
`examples/usage.py <https://github.com/Radical-AI/litxbench/blob/main/examples/usage.py>`_.

.. warning::

   For the evaluation scripts used in the paper, LitXBench instructs LLMs to format extracted
   materials as code. This code is run via Python ``exec``. Do **not** call untrusted LLMs as
   they may generate untrusted code which could be executed on your machine.
