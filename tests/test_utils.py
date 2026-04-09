import pytest

from litxbench.core.models import CompMeasurement


def test_verify_valid_compositions_percentage_based() -> None:
    CompMeasurement("Fe20Mg60Al20")


def test_verify_valid_compositions_ratio_based() -> None:
    CompMeasurement("Fe1Mg3Al1")


def test_verify_valid_compositions_equiatomic() -> None:
    CompMeasurement("CoCrFeNiMn")


def test_verify_valid_compositions_empty_composition() -> None:
    with pytest.raises(ValueError):
        CompMeasurement("")


def test_composition_not_sum_to_100() -> None:
    with pytest.raises(ValueError):
        CompMeasurement("Al10Co10Cr10Cu10Fe10Ni10")
