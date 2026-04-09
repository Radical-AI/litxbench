Evaluation
==========

LitXBench evaluates extractions by comparing them against expert-annotated ground truth.
The evaluation produces precision, recall, and F1 metrics at multiple levels of granularity.

Basic Evaluation
----------------

Use ``compare_experiments`` to compare a list of target (ground-truth) experiments against
a list of extracted experiments:

.. code-block:: python

   from litxbench import compare_experiments

   result = compare_experiments(ground_truth, extracted)
   print(f"Precision: {result.precision:.2%}")
   print(f"Recall:    {result.recall:.2%}")
   print(f"F1:        {result.f1:.2%}")

The result is an ``ExperimentComparisonResult`` containing:

- ``num_matched_items`` -- true positives (correctly matched measurements)
- ``num_total_target_items`` -- TP + FN (all ground-truth measurements)
- ``num_total_extracted_items`` -- TP + FP (all extracted measurements)

How Matching Works
------------------

The evaluation pipeline uses the `Hungarian algorithm <https://en.wikipedia.org/wiki/Hungarian_algorithm>`_
to find optimal assignments at each level.

**1. Material matching**

Target and extracted materials are paired using the Hungarian algorithm. The cost function
is based on the Levenshtein edit distance over resolved process events, which must be
extracted in the correct order. The resulting pairwise matchings determine the precision
and recall for the Material score.

**2. Measurement matching**

Within each material pair, measurements are compared. Measurements are first checked to be
of the same kind. Then the value and unit are compared. Finally, uncertainty qualifiers
(weight=1), temperature (weight=2), and pressure (weight=2) are taken into account.

**3. Configuration matching**

Configurations (phases) within a material form a tree structure (e.g. "Spot A" and "Spot B"
are sub-configurations of the BCC phase). The Hungarian algorithm first matches configurations
by their internal measurements. Then graph Markov equivalence is computed to check whether
parent nodes in extracted configurations match the parent nodes of target configurations,
prioritizing measurement accuracy over graph isomorphism.

Scoring Scheme
--------------

The overall F1 score is a weighted sum of four category scores:

.. list-table::
   :header-rows: 1
   :widths: 30 50 20

   * - Category
     - Description
     - Weight
   * - Measurements
     - Measurement values (kind, value, unit, uncertainty)
     - 0.50
   * - Process
     - Process conditions (ordered synthesis steps)
     - 0.20
   * - Material
     - Set of materials (correct count and pairing)
     - 0.15
   * - Configuration
     - Set of microstructure (phases, dendrites, precipitates)
     - 0.15

Extracting measurements is weighted most heavily because it is the primary goal of the task.
Configuration and material scores primarily ensure that the correct number of materials and
microstructure configurations are identified.

Multi-Level Metrics
-------------------

For finer-grained analysis, use ``compute_multi_level_metrics``:

.. code-block:: python

   from litxbench.core.eval import compute_multi_level_metrics

   metrics = compute_multi_level_metrics(result)

This returns F1 scores at five levels:

- **Value F1** -- Are the numeric values correct?
- **Measurement F1** -- Are the right properties measured with the right values?
- **Config F1** -- Are configurations (phases) correctly identified and measured?
- **Process F1** -- Is the synthesis process accurately captured?
- **Material F1** -- Are complete materials (process + all measurements) correct?

The ``overall_f1`` is a combined score across all levels.

.. code-block:: python

   print(f"Value F1:       {metrics.value_f1:.2%}")
   print(f"Measurement F1: {metrics.measurement_f1:.2%}")
   print(f"Config F1:      {metrics.config_f1:.2%}")
   print(f"Process F1:     {metrics.process_f1:.2%}")
   print(f"Material F1:    {metrics.material_f1:.2%}")
   print(f"Overall F1:     {metrics.overall_f1:.2%}")

Hallucination Detection
-----------------------

LitXBench includes a hallucination detector that checks whether numeric values in an
extraction actually appear in the source text:

.. code-block:: python

   from litxbench.core.hallucination import count_hallucinations

   result = count_hallucinations(extracted_experiments, source_text)
   print(f"Hallucination rate: {result.hallucination_rate:.1%}")

This is useful for catching cases where an LLM fabricates measurement values that
do not exist in the paper.
