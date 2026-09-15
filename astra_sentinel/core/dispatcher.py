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
    def __init__(self, registry: CapabilityRegistry, policy: PolicyEngine, audit: AuditLogger, config: Any = None) -> None:
        self._registry, self._policy, self._audit, self._config = registry, policy, audit, config

    def dispatch(self, request: ActionRequest, *, plan_id: str | None = None, action_id: str | None = None) -> ActionResult:
        capability = self._registry.get(request.capability)
        if capability is None:
            return self._finish(request, None, "DENY", None, ResultStatus.DENIED, "Unknown capability.", ErrorCode.UNKNOWN_CAPABILITY, plan_id=plan_id, action_id=action_id)
        meta = capability.metadata
        try:
            parameters = validate_capability_parameters(capability, request.parameters)
        except RequestValidationError:
            return self._finish(request, capability, "DENY", None, ResultStatus.VALIDATION_ERROR, "Invalid action parameters.", ErrorCode.INVALID_PARAMETERS, plan_id=plan_id, action_id=action_id)
        outcome = self._policy.evaluate(request.requester, capability)
        if outcome.decision is PolicyDecision.DENY:
            return self._finish(request, capability, outcome.decision, None, ResultStatus.DENIED, outcome.reason, outcome.error_code, plan_id=plan_id, action_id=action_id)
        if outcome.decision is PolicyDecision.CONFIRM:
            details = {"capability": meta.name, "risk_level": meta.risk_level.name, "reason": outcome.reason}
            return self._finish(request, capability, outcome.decision, None, ResultStatus.CONFIRMATION_REQUIRED, outcome.reason, outcome.error_code, details, plan_id=plan_id, action_id=action_id)
        try:
            resources = getattr(capability, "resource_paths", lambda _parameters: ())(parameters)
        except RequestValidationError:
            return self._finish(request, capability, PolicyDecision.DENY, None, ResultStatus.DENIED, "Resource is not allowed by policy.", ErrorCode.POLICY_DENIED, plan_id=plan_id, action_id=action_id)
        resource_outcome = self._policy.evaluate_resource(request.requester, tuple(resources))
        if resource_outcome.decision is PolicyDecision.DENY:
            return self._finish(request, capability, resource_outcome.decision, None, ResultStatus.DENIED, resource_outcome.reason, resource_outcome.error_code, plan_id=plan_id, action_id=action_id)
        try:
            data = capability.execute(parameters)
        except Exception:  # Explicit execution boundary: never leak capability details.
            LOGGER.exception("Capability execution failed request_id=%s", request.request_id)
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.EXECUTION_ERROR, "Action execution failed.", ErrorCode.EXECUTION_FAILED, plan_id=plan_id, action_id=action_id)
        try:
            verified = capability.verify(parameters, data)
        except Exception:
            LOGGER.exception("Capability verification failed request_id=%s", request.request_id)
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.VERIFICATION_ERROR, "Action verification failed.", ErrorCode.VERIFICATION_FAILED, plan_id=plan_id, action_id=action_id)
        if not verified:
            return self._finish(request, capability, outcome.decision, "failed", ResultStatus.VERIFICATION_ERROR, "Action verification failed.", ErrorCode.VERIFICATION_FAILED, plan_id=plan_id, action_id=action_id)
        return self._finish(request, capability, outcome.decision, "passed", ResultStatus.SUCCESS, "Action completed.", data=data, plan_id=plan_id, action_id=action_id)

    def rollback(self, request: ActionRequest, data: dict[str, Any], *, plan_id: str | None = None, action_id: str | None = None) -> ActionResult:
        capability = self._registry.get(request.capability)
        if capability is None or not capability.metadata.rollback_supported:
            return ActionResult(request.request_id, ResultStatus.DENIED, "Rollback is not supported for this action.", ErrorCode.POLICY_DENIED)
        outcome = self._policy.evaluate(request.requester, capability)
        if outcome.decision is not PolicyDecision.ALLOW:
            return self._finish(request, capability, outcome.decision, None, ResultStatus.DENIED, outcome.reason, outcome.error_code, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}")
        try:
            resources = getattr(capability, "resource_paths", lambda _parameters: ())(request.parameters)
            resource_outcome = self._policy.evaluate_resource(request.requester, tuple(resources))
            if resource_outcome.decision is not PolicyDecision.ALLOW:
                return self._finish(request, capability, resource_outcome.decision, None, ResultStatus.DENIED, resource_outcome.reason, resource_outcome.error_code, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}")
            rollback_data = capability.rollback(dict(request.parameters), dict(data))
        except RequestValidationError:
            return self._finish(request, capability, PolicyDecision.ALLOW, "failed", ResultStatus.VALIDATION_ERROR, "Rollback resource is invalid.", ErrorCode.INVALID_PARAMETERS, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}", rollback_status="FAILED")
        except OSError:
            return self._finish(request, capability, PolicyDecision.ALLOW, "failed", ResultStatus.EXECUTION_ERROR, "Rollback failed.", ErrorCode.EXECUTION_FAILED, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}", rollback_status="FAILED")
        except Exception:
            LOGGER.exception("Capability rollback failed request_id=%s", request.request_id)
            return self._finish(request, capability, PolicyDecision.ALLOW, "failed", ResultStatus.EXECUTION_ERROR, "Rollback failed.", ErrorCode.EXECUTION_FAILED, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}", rollback_status="FAILED")
        return self._finish(request, capability, PolicyDecision.ALLOW, "passed", ResultStatus.SUCCESS, "Rollback completed.", data=rollback_data, plan_id=plan_id, action_id=action_id, event_type="ROLLBACK_ACTION", rollback_action=f"rollback:{request.capability}", rollback_status="ROLLED_BACK")

    def _finish(self, request: ActionRequest, capability: Any, decision: Any, verification: str | None,
                status: ResultStatus, message: str, error: ErrorCode | None = None, data: dict[str, Any] | None = None,
                *, plan_id: str | None = None, action_id: str | None = None, event_type: str = "NORMAL_ACTION",
                rollback_action: str | None = None, rollback_status: str | None = None) -> ActionResult:
        meta = capability.metadata if capability else None
        self._audit.record(AuditEvent(
            request_id=request.request_id, timestamp=request.timestamp, requester=request.requester,
            capability=request.capability,
            parameters=sanitize_parameters(request.parameters, meta.sensitive_parameters if meta else frozenset()),
            policy_decision=str(decision), risk_level=int(meta.risk_level) if meta else None,
            execution_status=status.value, verification_status=verification,
            error_code=error.value if error else None, plan_id=plan_id, action_id=action_id,
            event_type=event_type, rollback_action=rollback_action, rollback_status=rollback_status,
        ))
        return ActionResult(request.request_id, status, message, error, data or {})

    @property
    def registry(self) -> CapabilityRegistry:
        return self._registry

    @property
    def policy(self) -> PolicyEngine:
        return self._policy

    @property
    def config(self) -> Any:
        return self._config
