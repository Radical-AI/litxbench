Building Extractions
====================

This page covers the details of building ``Experiment`` objects, including how to
specify inputs to synthesis groups (mixing materials together) and how to use
``group_measurements`` for reporting related measurement values.

Specifying Inputs
-----------------

When a synthesis step combines multiple raw materials or intermediate products, you
need to specify what feeds into it. There are three ways to do this.

Via the process string
^^^^^^^^^^^^^^^^^^^^^^

The first segment of a process string (before the first ``->``) lists the inputs to
the first step. Multiple inputs are comma-separated:

.. code-block:: python

   # Single input: "elements" feeds into "melting"
   Material(process="elements->melting", ...)

   # Multiple inputs: "sample1" and "sample2" both feed into "mix"
   Material(process="sample1,sample2->mix->anneal", ...)

These inputs are automatically injected into the first ``ProcessEvent`` of the
referenced synthesis group at evaluation time.

Via ``ProcessEvent.inputs``
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can declare inputs directly on a ``ProcessEvent`` within a synthesis group.
This is useful when a step *within* the group introduces a new material
(e.g. mixing in an additive partway through a multi-step group):

.. code-block:: python

   Experiment(
       raw_materials={
           "elements": RawMaterial(kind=RawMaterialKind.Powder),
           "wc_additions": RawMaterial(kind=RawMaterialKind.Powder),
       },
       synthesis_groups={
           "creation": [
               ProcessEvent(
                   kind=ProcessKind.MechanicalAlloying,
                   duration=Quantity(value=200, unit=Hour),
               ),
               # The second event explicitly mixes in "wc_additions"
               ProcessEvent(
                   kind=ProcessKind.Mixing,
                   inputs=["elements", "wc_additions"],
               ),
               ProcessEvent(kind=ProcessKind.HotPressingSintering),
           ],
       },
       output_materials=[
           Material(process="elements->creation", ...),
       ],
   )

Input names must reference either a key in ``raw_materials`` or the ``name`` of a
previously defined output material.

Via template variables in inputs
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Inputs can use template variables, allowing the same synthesis group to mix in
different materials depending on the output material:

.. code-block:: python

   Experiment(
       raw_materials={
           "powder_a": RawMaterial(kind=RawMaterialKind.Powder),
           "powder_b": RawMaterial(kind=RawMaterialKind.Powder),
       },
       synthesis_groups={
           "melting": [ProcessEvent(kind=ProcessKind.ArcMelting)],
           "mixing[Feedstock]": [
               ProcessEvent(kind=ProcessKind.Mixing, inputs=["[Feedstock]"]),
           ],
       },
       output_materials=[
           # A named intermediate material
           Material(
               process="powder_a->melting",
               name="ingot",
               measurements=[...],
           ),
           # At evaluation, [Feedstock] is substituted with "ingot",
           # referencing the named material above
           Material(process="powder_b->mixing[Feedstock=ingot]", ...),
       ],
   )


Grouped Measurements
--------------------

When a paper reports multiple related values for the same property (e.g. a range
like "3--5 microns" or lower/upper bounds), use ``Measurement.group_measurements``
to create them as a group. This produces multiple ``Measurement`` objects that share
the same ``kind``, ``unit``, and a common ``group_id``, ensuring they are evaluated
as a single logical measurement.

.. code-block:: python

   from litxbench import Measurement, CoreMeasurementValue, MeasurementStatistic

   *Measurement.group_measurements(
       kind=PhaseMeasurementKind.phase_size,
       unit=Micrometer,
       source="the size of these white areas is rapidly coarsened to 3-5 microns",
       values=[
           CoreMeasurementValue(statistic=MeasurementStatistic.lower, value=3),
           CoreMeasurementValue(statistic=MeasurementStatistic.upper, value=5),
       ],
   ),

The ``*`` unpacks the returned list into the surrounding ``measurements`` list.

Parameters
^^^^^^^^^^

The shared parameters (``kind``, ``unit``, ``measurement_method``, ``description``,
``temperature``, ``pressure``, ``source``, ``group_name``) are applied to every
generated ``Measurement``. The ``uncertainty`` parameter provides a default that can
be overridden per-value.

Each ``CoreMeasurementValue`` specifies:

- ``statistic`` -- a ``MeasurementStatistic`` (``mean``, ``median``, ``lower``, ``upper``, ``percentile``)
- ``value`` -- the numeric value
- ``uncertainty`` (optional) -- overrides the group default for this value
- ``description`` (optional) -- appended to the group description for this value
- ``source`` (optional) -- appended to the group source for this value

At least two values must be provided.
