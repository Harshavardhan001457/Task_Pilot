"""Capability contract; it deliberately contains no OS access helpers."""
from dataclasses import dataclass, field
from typing import Any, Protocol

from astra_sentinel.security.permissions import Permission
from astra_sentinel.security.risk import RiskLevel


@dataclass(frozen=True, slots=True)
class CapabilityMetadata:
    name: str
    description: str
    version: str
    required_parameters: dict[str, type]
    required_permissions: frozenset[Permission]
    risk_level: RiskLevel
    optional_parameters: dict[str, type] = field(default_factory=dict)
    confirmation_required: bool = False
    sensitive_parameters: frozenset[str] = frozenset()
    rollback_supported: bool = False


class Capability(Protocol):
    metadata: CapabilityMetadata

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]: ...
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]: ...
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool: ...

    def rollback(self, parameters: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]: ...
