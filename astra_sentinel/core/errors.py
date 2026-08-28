"""Stable error codes exposed by the secure runtime."""
from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    UNKNOWN_REQUESTER = "UNKNOWN_REQUESTER"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    POLICY_DENIED = "POLICY_DENIED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class RequestValidationError(ValueError):
    """Raised only for untrusted request-shape validation failures."""


class DuplicateCapabilityError(ValueError):
    """Raised when a registry name is registered more than once."""
