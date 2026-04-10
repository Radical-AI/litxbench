Core Concepts
=============

LitXBench represents material extractions as structured Python objects. This page explains
the data model and the design principles behind it.


Data Model Overview
-------------------

The data model forms a hierarchy:

.. code-block:: text

   Experiment
   ├── raw_materials: dict[str, RawMaterial]
   ├── synthesis_groups: dict[str, list[ProcessEvent]]
   └── output_materials: list[Material]
       ├── process: str              # e.g. "elements->Milling[Duration=60]->SPS[Temp=900]"
       ├── name: str | None          # optional, for referencing by later materials
       └── measurements: list[...]
           ├── CompMeasurement        # chemical composition
           ├── Measurement            # numeric property (hardness, strength, etc.)
           ├── GlobalLatticeParam     # crystal structure + lattice parameters
           └── Configuration          # distinct phase with its own measurements

We highly encourage you to read some of the experiments in the `ground truth dataset <https://github.com/Radical-AI/litxbench/tree/main/src/litxbench/litxalloy/extractions>`_ to familiarize yourself with the schema!


Experiment
^^^^^^^^^^

The top-level container. An ``Experiment`` groups:

- **Raw materials** -- starting feedstocks (powder, ingot, plate, etc.)
- **Synthesis groups** -- reusable process templates with optional template variables
- **Output materials** -- the materials produced, each with process history and measurements

.. code-block:: python

   Experiment(
       raw_materials={"elements": RawMaterial(kind=RawMaterialKind.Powder)},
       synthesis_groups={
           "Milling[Duration]": [
               ProcessEvent(kind=ProcessKind.PlanetaryMilling,
                            duration=Quantity(value="[Duration]", unit=Hour)),
           ],
       },
       output_materials=[...],
   )

Material
^^^^^^^^

A ``Material`` represents a specific material with its process history and measurements.

- The ``process`` string encodes the full synthesis lineage, e.g.
  ``"elements->Milling[Duration=60]->SPS[Temp=900]"``.
- ``->`` chains steps; ``[Key=Value]`` substitutes template variables defined in synthesis groups.
- Named materials (``name="base"``) can be referenced as inputs by later materials,
  forming a directed acyclic graph (DAG).

Since multiple base materials can be combined to form downstream materials, experiments are
conceptualized as a DAG. Child materials specify their parents, which is more flexible than
having parents specify children, since child materials can have multiple parents.

.. code-block:: python

   Material(
       process="elements->Milling[Duration=60]",
       name="base",
       measurements=[
           CompMeasurement(Composition("CoCrNiCuZn")),
           Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=615, unit=HV),
       ],
   )

Synthesis Groups & Template Variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Synthesis groups define reusable process sequences. Template variables in brackets
(e.g. ``[Duration]``, ``[Temp]``) are substituted per-material via the process string.
This reduces annotator error by maximizing code reuse across materials that differ only
by slight experimental parameters.

.. code-block:: python

   # Define once
   synthesis_groups = {
       "SPS[Temp]": [
           ProcessEvent(
               kind=ProcessKind.SparkPlasmaSintering,
               temperature=Quantity(value="[Temp]", unit=Celsius),
           ),
       ],
   }

   # Use per-material with different values
   Material(process="base->SPS[Temp=900]", ...)
   Material(process="base->SPS[Temp=1000]", ...)

Measurements
^^^^^^^^^^^^

Measurements capture numeric properties of a material.

- **Measurement** -- a generic numeric measurement with a ``MeasurementKind``, value, optional
  `Pint <https://pint.readthedocs.io/>`_ unit, optional uncertainty, and optional
  ``MeasurementMethod`` (the instrument/technique used).
- **CompMeasurement** -- chemical composition via pymatgen's ``Composition``
- **GlobalLatticeParam** -- crystal structure and lattice parameters from XRD
- **Configuration** -- a distinct phase within a material, containing its own measurements

The ``Quantity`` class represents values with units and optional qualifiers
(``~`` approximate, ``>`` above, ``<`` below, ``>=``, ``<=``, ``>>`` much above, ``<<`` much below).

.. code-block:: python

   Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=1250, unit=MegaPascal)
   Measurement(kind=AlloyMeasurementKind.density, value="~7.8", unit=gram_per_cm3)

Configuration
^^^^^^^^^^^^^

A ``Configuration`` represents a distinct phase or microstructural region within a material
(e.g. dendrites, precipitates, matrix phases). Configurations contain their own measurements
and can be nested via the ``within`` field to represent hierarchical microstructure
(e.g. precipitates within a matrix phase).

.. code-block:: python

   Configuration(
       name="FCC matrix",
       struct=CrysStruct.FCC,
       tags={ConfigTag.Matrix},
       measurements=[
           Measurement(kind=PhaseMeasurementKind.grain_size, value="~0.71", unit=Micrometer),
       ],
   )
   Configuration(
       name="B2 precipitates",
       struct=CrysStruct.B2,
       tags={ConfigTag.Precipitate, ConfigTag.Intragranular},
       within="FCC matrix",
       measurements=[...],
   )

Enumerations
^^^^^^^^^^^^

LitXBench uses canonical values (represented by enums) to ensure consistency.

- ``ProcessKind`` -- 38 synthesis and processing steps (milling, melting, sintering, annealing, etc.)
- ``MeasurementMethod`` -- instruments and techniques (XRD, SEM, TEM, EDS, etc.)
- ``CrysStruct`` -- crystal structures (FCC, BCC, HCP, L12, B2, etc.)
- ``ConfigTag`` -- microstructural features (dendrite, matrix, precipitate, twin, etc.)
- ``RawMaterialKind`` -- feedstock forms (powder, ingot, plate)
- ``AlloyMeasurementKind`` -- 32 alloy-specific properties (hardness, yield strength, density, etc.)

See :doc:`/api/enums` for the full listing.

The ``normalize()`` Function
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``normalize()`` function documents when a paper's terminology differs from the standardized
canonical value. It returns the canonical value unchanged but records the mapping for auditability.

.. code-block:: python

   # Paper says "Yield Strength" but the test was compressive
   Measurement(
       kind=normalize(AlloyMeasurementKind.yield_strength_compression,
                      val_in_paper="Yield Strength"),
       value=1200.0,
       unit=MegaPascal,
   )
