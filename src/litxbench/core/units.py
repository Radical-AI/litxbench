from typing import Any, cast

from pint import Unit, UnitRegistry

# was thinking about using pymatgen for units. But I like pint since the variety is larger
ureg = UnitRegistry[Any]()
ureg.define("HV = 9.807 * megapascal = vickers_hardness")
GigaPascal = ureg.gigapascal
MegaPascal = ureg.megapascal
Millimeter = ureg.millimeter
Micrometer = ureg.micrometer
Nanometer = ureg.nanometer
HV = ureg.vickers_hardness
gram_per_cm3 = cast(Unit, ureg.gram / ureg.cm**3)
percent = ureg.percent
dimensionless = ureg.dimensionless
Celsius = ureg.celsius
Kelvin = ureg.kelvin
Atm = ureg.atm
MegaPascalSquareRootMeter = cast(Unit, ureg.megapascal * ureg.meter**0.5)
MegaJoulesPerMeterSquared = cast(Unit, ureg.megajoule / ureg.meter**2)

Volt = ureg.volt
AmpPerCmSquared = cast(Unit, ureg.ampere / ureg.cm**2)
MillimeterPerYear = cast(Unit, ureg.millimeter / ureg.year)

Hour = ureg.hour
Minute = ureg.minute
Second = ureg.second
CelsiusPerMinute = cast(Unit, ureg.celsius / ureg.minute)
RevolutionsPerMinute = ureg.revolutions_per_minute
