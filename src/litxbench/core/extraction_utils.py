from typing import TypeVar, cast

from pint import Unit
from pymatgen.core.composition import Composition

from litxbench.core.models import Quantity
from litxbench.core.units import Celsius, ureg


def convert_value_between_units(value: float, input_unit: Unit, output_unit: Unit) -> float:
    converted_value = ureg.Quantity(value, input_unit).to(output_unit).magnitude
    return cast(float, converted_value)


T = TypeVar("T")


def normalize(val: T, val_in_paper: str, source: str | None = None) -> T:  # pyright: ignore[reportUnusedParameter]
    """
    This function to document that the value mentioned in the paper (e.g. a type of meaasurement/process/material/object etc.) is actually a privileged ground-truth value.

    E.g. The paper says they measured the Yield Strength of an alloy via compression testing:
        val_in_paper="Yield Strength"
    When we normalize this, we interpret it as:
        val=AlloyMeasurementKind.yield_strength_compression
    """
    return val


ROOM_TEMPERATURE = Quantity(value="~23", unit=Celsius)


def composition_with_weight_additions(
    base: Composition, additions: Composition, addition_wt_frac: float
) -> Composition:
    """
    How to interpret this:
    1) They weighted out the base composition in the lab
    2) They added additions_comp to the base composition —
       the amount added is addition_wt_frac of the base composition's weight
    """
    original_weight = base.weight
    target_addition_weight = original_weight * addition_wt_frac
    addition_amount = target_addition_weight / additions.weight
    scaled_addition = additions * addition_amount
    return base + scaled_addition


def balance_composition(main_element: str, additions: dict[str, float]) -> Composition:
    """
    A composition written in balance notation is as follows: Ti-6Al-4V
    Where Ti is the main element, and an additional 6% Al and 4% V (by w.t. %)
    are added to the base element to form the alloy..

    This function makes it easy to specify balance compositions.

    Args:
        main_element: The main element in the composition.
        additions: A dictionary of the additions to the main element.
            The keys are the elements, and the values are the percentages of the additions.
            The percentage of the main element is calculated as 100 - the sum of the percentages of the additions.

    Returns:
        A Composition object.
    """
    sum_of_other_elements = sum(additions.values())
    main_element_percentage = 100 - sum_of_other_elements
    return Composition.from_weights({main_element: main_element_percentage, **additions})
