"""Public, strongly typed request and result models."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping
from uuid import uuid4

from .errors import ErrorCode, RequestValidationError


class ResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    CONFIRMATION_REQUIRED = "confirmation_required"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    VERIFICATION_ERROR = "verification_error"


@dataclass(frozen=True, slots=True, init=False)
class ActionRequest:
    request_id: str
    capability: str
    parameters: dict[str, Any]
    requester: str
    timestamp: datetime

    def __init__(self, *, capability: str, parameters: Mapping[str, Any], requester: str) -> None:
        """Only caller data is accepted; request identity and time are trusted metadata."""
        if not isinstance(capability, str) or not capability or len(capability) > 128:
            raise RequestValidationError("capability must be a non-empty string up to 128 characters")
        if not isinstance(requester, str) or not requester or len(requester) > 64:
            raise RequestValidationError("requester must be a non-empty string up to 64 characters")
        if not isinstance(parameters, Mapping):
            raise RequestValidationError("parameters must be an object")
        object.__setattr__(self, "request_id", str(uuid4()))
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "parameters", dict(parameters))
        object.__setattr__(self, "requester", requester)
        object.__setattr__(self, "timestamp", datetime.now(timezone.utc))

    @classmethod
    def create(cls, *, capability: str, parameters: Mapping[str, Any], requester: str) -> "ActionRequest":
        """Build a request, assigning trusted identity and time metadata."""
        return cls(capability=capability, parameters=parameters, requester=requester)

    @classmethod
    def from_untrusted(cls, payload: Mapping[str, Any]) -> "ActionRequest":
        """Accept only caller-controlled action fields; metadata is always regenerated."""
        if not isinstance(payload, Mapping):
            raise RequestValidationError("request must be an object")
        allowed = {"capability", "parameters", "requester"}
        if set(payload) != allowed:
            raise RequestValidationError("request contains missing or unexpected fields")
        return cls.create(
            capability=payload["capability"], parameters=payload["parameters"], requester=payload["requester"]
        )


@dataclass(frozen=True, slots=True)
class ActionResult:
    request_id: str
    status: ResultStatus
    message: str
    error_code: ErrorCode | None = None
    data: dict[str, Any] = field(default_factory=dict)
