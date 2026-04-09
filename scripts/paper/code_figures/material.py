from litxbench.core.enums import ConfigTag, CrysStruct, MeasurementMethod, ProcessKind
from litxbench.core.extraction_utils import normalize
from litxbench.core.models import CompMeasurement, Configuration, Material, Measurement, ProcessEvent, Quantity
from litxbench.core.units import Celsius, GigaPascal, Hour, MegaPascal, percent
from litxbench.litxalloy.models import AlloyMeasurementKind as MeasurementKind
from pymatgen.core.composition import Composition

# To screenshot these materials for the paper, you just screenshot it but edit the photo to hide the pyright calls
# make sure to change the cursor theme to default light modern


Material(  # pyright: ignore[reportUnusedCallResult]
  process="Base Alloy->melting[Temp=850]->casting",
  name="MEA-5",
  measurements=[  # pyright: ignore[reportUnknownArgumentType]
    CompMeasurement("Al70Cu5Mg5Si10Zn5Zr5", method=MeasurementMethod.Balance),
    CompMeasurement("Al66Mg7Si9Zn6Cu7Zr3O2", method=MeasurementMethod.EDS, source="Table 1"),
    Measurement(
      kind=normalize(MeasurementKind.fracture_strain_compression, "plastic strain"),
      value=4,
      unit=percent,
      temperature=Quantity(21, Celsius),
    ),
    Measurement(kind=MeasurementKind.yield_strength_compression, value=565, unit=MegaPascal, uncertainty=79),
    Measurement(kind=MeasurementKind.youngs_modulus, value="<=120", unit=GigaPascal, source="Table 3"),
    Configuration(name="FCC lamellae", struct=CrysStruct.FCC),
    Configuration(tags={ConfigTag.Precipitate}, within="FCC lamellae", measurements=[CompMeasurement("Mg55Si30O15")]),
  ],
)


synthesis_groups = {
  "melting": [
    ProcessEvent(kind=ProcessKind.InductionMelting, source="Experimental Work"),
    ProcessEvent(kind=ProcessKind.GravityCasting, source="Experimental Work"),
  ],
  "annealing[Hours]": [
    ProcessEvent(
      kind=ProcessKind.Annealing,
      temperature=Quantity(value=900, unit=Celsius),
      duration=Quantity(value="[Hours]", unit=Hour),
    )
  ],
}


Material(  # pyright: ignore[reportCallIssue, reportUnusedCallResult]
  name="Base",
  process="Pellets->melting",
  # ...
)
Material(  # pyright: ignore[reportCallIssue, reportUnusedCallResult]
  name="HEA1",
  process="Base->annealing[Hours=20]",
  # ...
)


def composition_with_weight_additions(
  base: Composition, additions: Composition, addition_wt_frac: float
) -> Composition:
  """
  How to interpret this:
  1) They weighted out the base composition in the lab
  2) They added additions_comp to the base composition
    The amount added is addition_wt_frac of the base composition's weight
  """
  original_weight = base.weight
  target_addition_weight = original_weight * addition_wt_frac
  addition_amount = target_addition_weight / additions.weight
  scaled_addition = additions * addition_amount
  return base + scaled_addition


# usage
composition_with_weight_additions(
  base=Composition("CoCrFeNi"),
  additions=Composition("WC"),
  addition_wt_frac=0.1,
)


# returns Co1 Cr1 Fe1 Ni1 W0.11512223 C0.11512223


# print(
#   composition_with_weight_additions(
#     base=Composition("CoCrFeNi"),
#     additions=Composition("WC"),
#     addition_wt_frac=0.1,
#   )
# )
