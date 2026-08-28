"""Structured in-memory audit sink, replaceable with SQLite later."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AuditEvent:
    request_id: str
    timestamp: datetime
    requester: str
    capability: str
    parameters: dict[str, Any]
    policy_decision: str
    risk_level: int | None
    execution_status: str
    verification_status: str | None
    error_code: str | None


class AuditLogger(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class InMemoryAuditLogger:
    """Deliberate Phase 1 choice: deterministic tests, no local data retention."""
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)


def sanitize_parameters(parameters: dict[str, Any], sensitive: frozenset[str]) -> dict[str, Any]:
    return {key: "REDACTED" if key in sensitive else value for key, value in parameters.items()}
