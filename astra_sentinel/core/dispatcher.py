"""The execution boundary orchestrator; it contains no OS-specific code."""
import logging
from typing import Any

from astra_sentinel.audit.logger import AuditEvent, AuditLogger, sanitize_parameters
from astra_sentinel.core.errors import ErrorCode, RequestValidationError
from astra_sentinel.core.models import ActionRequest, ActionResult, ResultStatus
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.core.validator import validate_capability_parameters
from astra_sentinel.security.policy import PolicyDecision, PolicyEngine

LOGGER = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, registry: CapabilityRegistry, policy: PolicyEngine, audit: AuditLogger) -> None:
        self._registry, self._policy, self._audit = registry, policy, audit

    def dispatch(self, request: ActionRequest) -> ActionResult:
        capability = self._registry.get(request.capability)
        if capability is None:
            return self._finish(request, None, "DENY", None, ResultStatus.DENIED, "Unknown capability.", ErrorCode.UNKNOWN_CAPABILITY)
        meta = capability.metadata
        try:
            parameters = validate_capability_parameters(capability, request.parameters)
        except RequestValidationError:
            return self._finish(request, capability, "DENY", None, ResultStatus.VALIDATION_ERROR, "Invalid action parameters.", ErrorCode.INVALID_PARAMETERS)
        outcome = self._policy.evaluate(request.requester, capability)
        if outcome.decision is PolicyDecision.DENY:
            return self._finish(request, capability, outcome.decision, None, ResultStatus.DENIED, outcome.reason, outcome.error_code)
        if outcome.decision is PolicyDecision.CONFIRM:
            details = {"capability": meta.name, "risk_level": meta.risk_level.name, "reason": outcome.reason}
            return self._finish(request, capability, outcome.decision, None, ResultStatus.CONFIRMATION_REQUIRED, outcome.reason, outcome.error_code, details)
        try:
            data = capability.execute(parameters)
        except Exception:  # Explicit execution boundary: never leak capability details.
            LOGGER.exception("Capability execution failed request_id=%s", request.request_id)
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.EXECUTION_ERROR, "Action execution failed.", ErrorCode.EXECUTION_FAILED)
        try:
            verified = capability.verify(parameters, data)
        except Exception:
            LOGGER.exception("Capability verification failed request_id=%s", request.request_id)
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.VERIFICATION_ERROR, "Action verification failed.", ErrorCode.VERIFICATION_FAILED)
        if not verified:
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.VERIFICATION_ERROR, "Action verification failed.", ErrorCode.VERIFICATION_FAILED)
        return self._finish(request, capability, outcome.decision, "passed", ResultStatus.SUCCESS, "Action completed.", data=data)

    def _finish(self, request: ActionRequest, capability: Any, decision: Any, verification: str | None,
                status: ResultStatus, message: str, error: ErrorCode | None = None, data: dict[str, Any] | None = None) -> ActionResult:
        meta = capability.metadata if capability else None
        self._audit.record(AuditEvent(
            request.request_id, request.timestamp, request.requester, request.capability,
            sanitize_parameters(request.parameters, meta.sensitive_parameters if meta else frozenset()),
            str(decision), int(meta.risk_level) if meta else None, status.value, verification,
            error.value if error else None,
        ))
        return ActionResult(request.request_id, status, message, error, data or {})
