from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from litxbench.core.models import (
    CompMeasurement,
    MeasurementMethod,
)
from litxbench.core.units import HV, MegaPascal, ureg
from litxbench.litxalloy.models import (
    AlloyMeasurementKind,
    Material,
    Measurement,
)
from scripts.paper.benchmarks.helpers.serialization import (
    deserialize,
    hash_anything,
    serialize,
)


@dataclass
class SimpleTestData:
    """A simple dataclass for testing serialization and deserialization."""

    id: int
    name: str
    created_at: datetime
    int_list: list[int]


def test_dataclass_serialization_round_trip() -> None:
    """Tests that a simple dataclass can be serialized and deserialized."""
    original = SimpleTestData(
        id=1,
        name="Test Object",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        int_list=[1, 2, 3],
    )

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized


def test_disregard_datetime_for_hashing() -> None:
    """Tests that disregard_datetime=True makes objects with different datetimes hash the same."""
    obj1 = SimpleTestData(
        id=1,
        name="Test",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        int_list=[1, 2],
    )
    obj2 = SimpleTestData(
        id=1,
        name="Test",
        created_at=datetime(2024, 2, 2, 18, 30, 0),
        int_list=[1, 2],
    )

    # Without disregard_datetime, hashes differ
    json1 = serialize(obj1, disregard_datetime=False)
    json2 = serialize(obj2, disregard_datetime=False)
    assert json1 != json2

    # With disregard_datetime, hashes are the same
    json1_disregard = serialize(obj1, disregard_datetime=True)
    json2_disregard = serialize(obj2, disregard_datetime=True)
    assert json1_disregard == json2_disregard


class SimpleTestModel(BaseModel):
    """A simple Pydantic model for testing."""

    id: int
    name: str
    created_at: datetime
    int_list: list[int]


def test_pydantic_model_serialization_round_trip() -> None:
    """Tests that a Pydantic model can be serialized and deserialized."""
    original = SimpleTestModel(
        id=1,
        name="Test Model",
        created_at=datetime(2023, 1, 1, 12, 0, 0),
        int_list=[1, 2],
    )

    json_string = serialize(original)
    deserialized = cast(SimpleTestModel, deserialize(json_string))

    assert deserialized.model_dump() == original.model_dump()


def test_hash_bytes() -> None:
    """Tests that bytes can be hashed."""
    obj = b"\x00\x01abc"
    result = hash_anything(obj)
    assert isinstance(result, str)
    assert len(result) == 64  # SHA256 hex digest


@dataclass
class BytesData:
    """Dataclass with bytes field."""

    payload: bytes


def test_hash_dataclass_with_bytes_field() -> None:
    """Tests that a dataclass with bytes field can be hashed."""
    obj = BytesData(payload=b"\x00\x01abc")
    result = hash_anything(obj)
    assert isinstance(result, str)


def test_path_serialization_round_trip() -> None:
    """Tests that Path objects can be serialized and deserialized."""
    original = Path("/some/path/to/file.txt")

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized


class Color(str, Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


@dataclass
class DataWithEnum:
    """Dataclass with enum field."""

    name: str
    color: Color


def test_enum_serialization_round_trip() -> None:
    """Tests that enums can be serialized and deserialized."""
    original = DataWithEnum(name="test", color=Color.GREEN)

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized
    assert deserialized.color == Color.GREEN


def test_pint_unit_serialization_round_trip() -> None:
    """Tests that pint Unit objects can be serialized and deserialized."""
    original = ureg.megapascal

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized


def test_pint_quantity_serialization_round_trip() -> None:
    """Tests that pint Quantity objects can be serialized and deserialized."""
    original = ureg.Quantity(100, "megapascal")

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized


def test_composition_measurement_serialization_round_trip() -> None:
    """Tests that CompositionMeasurement preserves formula through serialization."""
    original = CompMeasurement(
        "Nb0.25Ta0.25Ti0.25Zr0.25",
        method=MeasurementMethod.Balance,
        description="test description",
    )

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    # Check formula is preserved
    assert deserialized.composition.formula == original.composition.formula
    assert deserialized.method == original.method
    assert deserialized.description == original.description


def test_measurement_serialization_round_trip() -> None:
    """Tests that Measurement can be serialized and deserialized."""
    original = Measurement(
        kind=AlloyMeasurementKind.vickers_hardness,
        value=450.0,
        unit=HV,
        uncertainty=20.0,
    )

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert deserialized.kind == original.kind
    assert deserialized.value == original.value
    assert deserialized.unit == original.unit
    assert deserialized.uncertainty == original.uncertainty


def test_material_serialization_round_trip() -> None:
    """Tests that Material with mixed measurements can be serialized and deserialized."""
    original = Material(
        measurements=[
            CompMeasurement("Al0.5CoCrFeNi"),
            Measurement(kind=AlloyMeasurementKind.vickers_hardness, value=450.0, unit=HV),
            Measurement(kind=AlloyMeasurementKind.yield_strength_tension, value=1000.0, unit=MegaPascal),
        ]
    )

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    # Check composition is preserved
    comp_original = [m for m in original.measurements if isinstance(m, CompMeasurement)][0]
    comp_deserialized = [m for m in deserialized.measurements if isinstance(m, CompMeasurement)][0]
    assert comp_deserialized.composition.formula == comp_original.composition.formula

    # Check measurements count
    assert len(deserialized.measurements) == len(original.measurements)


@dataclass
class NestedData:
    """Dataclass with nested dataclass."""

    name: str
    inner: SimpleTestData


def test_nested_dataclass_serialization_round_trip() -> None:
    """Tests that nested dataclasses can be serialized and deserialized."""
    original = NestedData(
        name="outer",
        inner=SimpleTestData(
            id=1,
            name="inner",
            created_at=datetime(2023, 1, 1),
            int_list=[1, 2],
        ),
    )

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized


def test_list_of_dataclasses_serialization_round_trip() -> None:
    """Tests that a list of dataclasses can be serialized and deserialized."""
    original = [
        SimpleTestData(id=1, name="first", created_at=datetime(2023, 1, 1), int_list=[1]),
        SimpleTestData(id=2, name="second", created_at=datetime(2023, 2, 2), int_list=[2]),
    ]

    json_string = serialize(original)
    deserialized = deserialize(json_string)

    assert original == deserialized
