"""Fail-closed policy decision engine."""
from dataclasses import dataclass
from enum import StrEnum

from astra_sentinel.capabilities.base import Capability
from astra_sentinel.core.errors import ErrorCode
from .permissions import PermissionGrants
from .risk import RiskLevel


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    CONFIRM = "CONFIRM"


@dataclass(frozen=True, slots=True)
class PolicyOutcome:
    decision: PolicyDecision
    reason: str
    error_code: ErrorCode | None = None


@dataclass(frozen=True, slots=True)
class PolicyConfig:
    trusted_requesters: frozenset[str]
    permission_grants: PermissionGrants
    explicitly_denied_capabilities: frozenset[str] = frozenset()
    allow_modify: bool = False


class PolicyEngine:
    def __init__(self, config: PolicyConfig) -> None:
        self._config = config

    def evaluate(self, requester: str, capability: Capability) -> PolicyOutcome:
        meta = capability.metadata
        if requester not in self._config.trusted_requesters:
            return PolicyOutcome(PolicyDecision.DENY, "Requester is not trusted.", ErrorCode.UNKNOWN_REQUESTER)
        if meta.name in self._config.explicitly_denied_capabilities:
            return PolicyOutcome(PolicyDecision.DENY, "Capability is prohibited by policy.", ErrorCode.POLICY_DENIED)
        if not self._config.permission_grants.has_all(requester, meta.required_permissions):
            return PolicyOutcome(PolicyDecision.DENY, "Required permission is not granted.", ErrorCode.PERMISSION_DENIED)
        if meta.risk_level == RiskLevel.RESTRICTED:
            return PolicyOutcome(PolicyDecision.DENY, "Restricted operations are prohibited.", ErrorCode.POLICY_DENIED)
        if meta.risk_level == RiskLevel.DESTRUCTIVE or meta.confirmation_required:
            return PolicyOutcome(PolicyDecision.CONFIRM, "This operation requires trusted confirmation.", ErrorCode.CONFIRMATION_REQUIRED)
        if meta.risk_level == RiskLevel.MODIFY and not self._config.allow_modify:
            return PolicyOutcome(PolicyDecision.DENY, "Modification operations are disabled by policy.", ErrorCode.POLICY_DENIED)
        return PolicyOutcome(PolicyDecision.ALLOW, "Allowed by policy.")
