# pyright: basic
"""Serialization utilities.

Supports serializing and deserializing dataclasses and datetime objects.
The serializer also supports disabling datetime serialization for consistent hashing.

This file was 100% AI generated. But it passes the tests.
"""

import base64
import hashlib
import importlib
import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# --- Helper functions for type conversion ---


def _create_default_encoder(disregard_datetime: bool = False):
    """
    Factory function to create a configurable JSON encoder.
    This allows us to pass configuration (like disabling datetime)
    into the encoder function used by json.dumps.

    Args:
        disregard_datetime: If True, the created encoder will serialize all
                          datetime objects to a default minimum value.

    Returns:
        A configured encoder function.
    """

    def _default_encoder(obj: Any) -> Any:
        """
        A default JSON encoder function that handles special types.
        - Converts dataclass instances to dictionaries with metadata.
        - Conditionally converts datetime objects to ISO 8601 strings.
        """
        if isinstance(obj, BaseModel):
            result = obj.model_dump(mode="json")
            result["__pydantic__"] = obj.__class__.__name__
            result["__module__"] = obj.__class__.__module__
            return result
        if is_dataclass(obj) and not isinstance(obj, type):
            # Convert dataclass to a dictionary and add metadata
            # to identify it during deserialization.
            # We use a shallow dict conversion instead of a deep one (asdict)
            # to allow json.dumps to recursively call our encoder on nested objects.
            result = {}
            for f in fields(obj):
                value = getattr(obj, f.name)
                # Handle StrEnum specially since json.dumps treats them as strings
                if isinstance(value, Enum):
                    value = {
                        "__enum__": True,
                        "value": value.value,
                        "class": value.__class__.__name__,
                        "module": value.__class__.__module__,
                    }
                result[f.name] = value
            result["__dataclass__"] = obj.__class__.__name__
            result["__module__"] = obj.__class__.__module__
            # If the object has as_dict(), include that data for parent class state
            if hasattr(obj, "as_dict") and callable(obj.as_dict):
                result["__parent_state__"] = obj.as_dict()
            return result

        # Handle Enum values
        elif isinstance(obj, Enum):
            return {
                "__enum__": True,
                "value": obj.value,
                "class": obj.__class__.__name__,
                "module": obj.__class__.__module__,
            }

        # Check for datetime and if it's enabled for serialization.
        elif isinstance(obj, datetime):
            if not disregard_datetime:
                # Convert datetime to a dictionary with its ISO string value
                # and metadata for deserialization.
                return {"__datetime__": True, "value": obj.isoformat()}
            else:
                # If datetime handling is disabled, serialize it as the
                # minimum possible datetime for consistent hashing.
                return {"__datetime__": True, "value": datetime.min.isoformat()}

        elif isinstance(obj, bytes):
            return {"__bytes__": True, "value": base64.b64encode(obj).decode("ascii")}

        elif isinstance(obj, Path):
            return {"__path__": True, "value": str(obj)}

        elif isinstance(obj, set):
            return {"__set__": True, "value": list(obj)}

        # Handle pymatgen Composition objects
        try:
            from pymatgen.core.composition import Composition

            if isinstance(obj, Composition):
                return {"__pymatgen_composition__": True, "value": obj.formula}
        except ImportError:
            pass

        # Handle pint Unit and Quantity objects
        try:
            import pint

            if isinstance(obj, pint.Unit):
                return {"__pint_unit__": True, "value": str(obj)}
            elif isinstance(obj, pint.Quantity):
                return {"__pint_quantity__": True, "magnitude": obj.magnitude, "units": str(obj.units)}
        except ImportError:
            pass

        # As a last resort, check for a to_dict method. This is a convention
        # used by some libraries (like google-genai) for serialization.
        if hasattr(obj, "to_dict"):
            try:
                # We don't call obj.to_dict() directly because it might be
                # recursive and prevent our encoder from being called on nested
                # objects. Instead, we get the object's attributes via vars()
                # and let json.dumps handle the recursion.
                result = vars(obj).copy()
                result["__custom_object__"] = type(obj).__name__
                result["__module__"] = type(obj).__module__
                return result
            except TypeError:
                # vars() can fail on objects without a __dict__ (e.g. slots)
                pass

        # For any other type that json.dumps doesn't recognize on its own,
        # this will be raised.
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    return _default_encoder


def _object_hook(dct: dict) -> Any:
    """
    An object hook for json.loads that reconstructs our custom types
    from the metadata we added during serialization.
    """
    if "__pydantic__" in dct:
        module_name = dct.pop("__module__")
        class_name = dct.pop("__pydantic__")

        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            assert issubclass(cls, BaseModel)
            return cls.model_validate(dct)
        except (ImportError, AttributeError) as e:
            raise TypeError(f"Could not deserialize pydantic model {class_name} from module {module_name}") from e
    if "__dataclass__" in dct:
        # If the dictionary has our dataclass metadata, we can rebuild it.
        module_name = dct.pop("__module__")
        class_name = dct.pop("__dataclass__")
        parent_state = dct.pop("__parent_state__", None)

        try:
            # Dynamically import the module where the dataclass is defined.
            module = importlib.import_module(module_name)
            # Get the class from the module.
            cls = getattr(module, class_name)
            # Instantiate the dataclass with the remaining items.
            # The object_hook is called from the inside out, so any nested
            # custom objects in dct will have already been converted.
            if hasattr(cls, "from_dict"):
                # Use from_dict if available (handles InitVar fields and parent state)
                if parent_state is not None:
                    return cls.from_dict({**parent_state, **dct})
                return cls.from_dict(dct)
            init_kwargs = {field.name: dct[field.name] for field in fields(cls) if field.init and field.name in dct}
            return cls(**init_kwargs)
        except (ImportError, AttributeError) as e:
            raise TypeError(f"Could not deserialize dataclass {class_name} from module {module_name}") from e

    elif "__datetime__" in dct:
        # If the dictionary has our datetime metadata, parse the ISO string.
        return datetime.fromisoformat(dct["value"])

    elif "__bytes__" in dct:
        return base64.b64decode(dct["value"])

    elif "__path__" in dct:
        return Path(dct["value"])

    elif "__set__" in dct:
        return set(dct["value"])

    elif "__pymatgen_composition__" in dct:
        from pymatgen.core.composition import Composition

        return Composition(dct["value"])

    elif "__pint_unit__" in dct:
        from litxbench.core.units import ureg

        return ureg.Unit(dct["value"])

    elif "__pint_quantity__" in dct:
        from litxbench.core.units import ureg

        return ureg.Quantity(dct["magnitude"], dct["units"])

    elif "__enum__" in dct:
        module_name = dct["module"]
        class_name = dct["class"]
        value = dct["value"]
        try:
            module = importlib.import_module(module_name)
            enum_cls = getattr(module, class_name)
            return enum_cls(value)
        except (ImportError, AttributeError) as e:
            raise TypeError(f"Could not deserialize enum {class_name} from module {module_name}") from e

    return dct


# --- Main serialization functions ---


def serialize(obj: Any, disregard_datetime: bool = False, **kwargs) -> str:
    """
    Serializes a Python object into a JSON string.

    Args:
        obj: The Python object to serialize.
        disregard_datetime (bool): If True, all datetime objects will be
                                 serialized as the minimum possible datetime
                                 ('0001-01-01T00:00:00'). This is useful for
                                 creating consistent hashes. Defaults to False.
        **kwargs: Additional arguments to pass to json.dumps (e.g., indent=4).

    Returns:
        A JSON string representation of the object.
    """
    # Create the appropriate encoder using our factory
    encoder = _create_default_encoder(disregard_datetime=disregard_datetime)
    return json.dumps(obj, default=encoder, **kwargs)


def deserialize(json_string: str) -> Any:
    """
    Deserializes a JSON string back into a Python object.

    Args:
        json_string: The JSON string to deserialize.

    Returns:
        The reconstructed Python object.
    """
    return json.loads(json_string, object_hook=_object_hook)


def hash_anything(obj: Any, disregard_datetime: bool = True) -> str:
    """
    Hashes any object into a sha256 hex digest.

    If the object is bytes, it is hashed directly. Otherwise, it is
    serialized to a string first.

    Args:
        obj: The object to hash.
        disregard_datetime: Whether to disregard datetimes for consistent hashing.
                            Defaults to True.
    """
    serialized_obj = serialize(obj, disregard_datetime=disregard_datetime)
    return hashlib.sha256(serialized_obj.encode("utf-8")).hexdigest()
