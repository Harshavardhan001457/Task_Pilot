"""Strict parameter validation at the boundary before policy evaluation."""
from typing import Any

from astra_sentinel.capabilities.base import Capability
from .errors import RequestValidationError

MAX_STRING_LENGTH = 4096


def validate_capability_parameters(capability: Capability, parameters: dict[str, Any]) -> dict[str, Any]:
    schema = capability.metadata.required_parameters
    if set(parameters) != set(schema):
        raise RequestValidationError("parameters contain missing or unexpected fields")
    for key, value in parameters.items():
        expected = schema[key]
        if type(value) is not expected:
            raise RequestValidationError(f"parameter {key} has an invalid type")
        if isinstance(value, str) and (not value or len(value) > MAX_STRING_LENGTH):
            raise RequestValidationError(f"parameter {key} has an invalid length")
    return capability.validate_parameters(parameters)
