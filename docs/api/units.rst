Units
=====

.. module:: litxbench.core.units

Pre-defined units built on `Pint <https://pint.readthedocs.io/>`_. All units are instances of
``pint.Unit`` from a shared ``UnitRegistry``.

Pressure
--------

- ``GigaPascal`` -- GPa
- ``MegaPascal`` -- MPa

Length
------

- ``Millimeter`` -- mm
- ``Micrometer`` -- um
- ``Nanometer`` -- nm

Temperature
-----------

- ``Celsius`` -- degC
- ``Kelvin`` -- K

Time
----

- ``Hour``
- ``Minute``
- ``Second``

Other
-----

- ``gram_per_cm3`` -- density (g/cm3)
- ``HV`` -- Vickers hardness
- ``percent`` -- %
- ``CelsiusPerMinute`` -- heating/cooling rate
- ``RevolutionsPerMinute`` -- RPM
- ``MegaPascalSquareRootMeter`` -- fracture toughness (MPa*m^0.5)

Usage
-----

.. code-block:: python

   from litxbench.core.units import MegaPascal, Celsius, Hour

   Quantity(value=1250, unit=MegaPascal)
   Quantity(value=900, unit=Celsius)
   Quantity(value=2, unit=Hour)
