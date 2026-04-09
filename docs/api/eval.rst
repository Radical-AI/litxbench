Evaluation
==========

.. module:: litxbench.core.eval

Functions and result types for comparing extractions against ground truth.

Comparison
----------

.. autofunction:: compare_experiments

.. autofunction:: compute_multi_level_metrics

Result Types
------------

.. autoclass:: ExperimentComparisonResult
   :members:
   :undoc-members:

.. autoclass:: MaterialMatchResult
   :members:
   :undoc-members:

.. autoclass:: MeasurementMatchResult
   :members:
   :undoc-members:

.. autoclass:: ConfigurationMatchResult
   :members:
   :undoc-members:

.. autoclass:: ComparableItem
   :members:
   :undoc-members:

Hallucination Detection
-----------------------

.. module:: litxbench.core.hallucination

.. autofunction:: count_hallucinations

.. autoclass:: HallucinationResult
   :members:
   :undoc-members:
