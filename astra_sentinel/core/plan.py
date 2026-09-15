"""Structured action plans executed through the existing dispatcher security pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.errors import ErrorCode, RequestValidationError
from astra_sentinel.core.models import ActionRequest, ActionResult, ResultStatus
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.core.validator import validate_capability_parameters


class PlanFailurePolicy(StrEnum):
    STOP = "STOP"
    CONTINUE = "CONTINUE"


class RollbackPolicy(StrEnum):
    NEVER = "NEVER"
    ON_FAILURE = "ON_FAILURE"


class ActionState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


@dataclass(frozen=True, slots=True)
class ActionPlanItem:
    action_id: str
    capability: str
    parameters: dict[str, Any] = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "depends_on", tuple(self.depends_on))
        if not isinstance(self.parameters, dict):
            raise RequestValidationError("action parameters must be an object")


@dataclass(frozen=True, slots=True)
class ActionPlan:
    plan_id: str
    description: str
    requester: str
    actions: tuple[ActionPlanItem, ...]
    failure_policy: PlanFailurePolicy = PlanFailurePolicy.STOP
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    rollback_policy: RollbackPolicy = RollbackPolicy.NEVER
    rollback_on_failure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "actions", tuple(self.actions))
        object.__setattr__(self, "failure_policy", PlanFailurePolicy(self.failure_policy))
        object.__setattr__(self, "rollback_policy", RollbackPolicy(self.rollback_policy))


@dataclass(frozen=True, slots=True)
class PlanResult:
    plan_id: str
    final_status: PlanStatus
    action_results: dict[str, ActionResult]
    summary: str
    failed_action_ids: list[str]
    skipped_action_ids: list[str]
    rollback_results: dict[str, ActionResult] = field(default_factory=dict)


def validate_plan_structure(plan: ActionPlan, registry: CapabilityRegistry) -> None:
    """Validate an ActionPlan without authorizing or executing its actions."""
    if not plan.plan_id:
        raise ValueError("plan_id is required")
    if not plan.description:
        raise ValueError("plan description is required")
    if not plan.requester:
        raise ValueError("requester is required")
    if plan.failure_policy not in {PlanFailurePolicy.STOP, PlanFailurePolicy.CONTINUE}:
        raise ValueError("failure_policy must be STOP or CONTINUE")
    if not plan.actions:
        raise ValueError("plan must contain at least one action")

    action_ids: set[str] = set()
    declared_action_ids = {item.action_id for item in plan.actions}
    for index, action in enumerate(plan.actions):
        if not action.action_id:
            raise ValueError(f"action {index} is missing action_id")
        if action.action_id in action_ids:
            raise ValueError(f"duplicate action_id: {action.action_id}")
        action_ids.add(action.action_id)

        registry_entry = registry.get(action.capability)
        if registry_entry is None:
            raise ValueError(f"unknown capability in plan: {action.capability}")
        validate_capability_parameters(registry_entry, action.parameters)

        for dependency in action.depends_on:
            if dependency == action.action_id:
                raise ValueError(f"action {action.action_id} cannot depend on itself")
            if dependency not in declared_action_ids:
                raise ValueError(f"unknown dependency {dependency} for action {action.action_id}")

    _detect_plan_cycle(plan)


def _detect_plan_cycle(plan: ActionPlan) -> None:
    graph = {item.action_id: set(item.depends_on) for item in plan.actions}
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            raise ValueError("circular dependencies are not allowed")
        if node in visited:
            return
        active.add(node)
        for dependency in graph.get(node, set()):
            if dependency not in graph:
                continue
            visit(dependency)
        active.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def plan_execution_order(plan: ActionPlan) -> tuple[str, ...]:
    """Return the dependency-respecting order for an already valid plan."""
    pending = {item.action_id: set(item.depends_on) for item in plan.actions}
    completed: set[str] = set()
    order: list[str] = []
    while pending:
        ready = [action_id for action_id, dependencies in pending.items() if dependencies.issubset(completed)]
        if not ready:
            raise ValueError("circular dependencies are not allowed")
        for action_id in ready:
            order.append(action_id)
            pending.pop(action_id)
            completed.add(action_id)
    return tuple(order)


class PlanExecutor:
    def __init__(self, dispatcher: Dispatcher) -> None:
        self._dispatcher = dispatcher

    def validate_plan(self, plan: ActionPlan) -> None:
        validate_plan_structure(plan, self._dispatcher.registry)

    def execute(self, plan: ActionPlan) -> PlanResult:
        try:
            self.validate_plan(plan)
        except ValueError as error:
            return PlanResult(
                plan_id=plan.plan_id,
                final_status=PlanStatus.FAILED,
                action_results={},
                summary=f"Plan validation failed: {error}",
                failed_action_ids=[],
                skipped_action_ids=[],
            )
        actions_by_id = {item.action_id: item for item in plan.actions}
        order = plan_execution_order(plan)

        states: dict[str, ActionState] = {action_id: ActionState.PENDING for action_id in actions_by_id}
        action_results: dict[str, ActionResult] = {}
        failed: set[str] = set()
        skipped: set[str] = set()
        rollback_results: dict[str, ActionResult] = {}

        for action_id in order:
            action = actions_by_id[action_id]
            dependency_states = [states.get(dep, ActionState.PENDING) for dep in action.depends_on]
            if any(state in {ActionState.FAILED, ActionState.SKIPPED} for state in dependency_states):
                states[action_id] = ActionState.SKIPPED
                skipped.add(action_id)
                action_results[action_id] = ActionResult(
                    request_id=f"plan-{plan.plan_id}-{action_id}",
                    status=ResultStatus.DENIED,
                    message="Skipped because a dependency failed or was skipped.",
                    error_code=ErrorCode.POLICY_DENIED,
                    data={"action_id": action_id, "skipped": True},
                )
                continue

            request = ActionRequest.create(
                capability=action.capability,
                parameters=dict(action.parameters),
                requester=plan.requester,
            )
            states[action_id] = ActionState.RUNNING
            result = self._dispatcher.dispatch(request, plan_id=plan.plan_id, action_id=action_id)
            action_results[action_id] = result

            if result.status is ResultStatus.SUCCESS:
                states[action_id] = ActionState.SUCCESS
            else:
                states[action_id] = ActionState.FAILED
                failed.add(action_id)
                if plan.failure_policy is PlanFailurePolicy.STOP:
                    for later_id in order[order.index(action_id) + 1:]:
                        if later_id not in states or states[later_id] is ActionState.PENDING:
                            states[later_id] = ActionState.SKIPPED
                            skipped.add(later_id)
                            action_results[later_id] = ActionResult(
                                request_id=f"plan-{plan.plan_id}-{later_id}",
                                status=ResultStatus.DENIED,
                                message="Skipped because the plan stopped after a failed action.",
                                error_code=ErrorCode.POLICY_DENIED,
                                data={"action_id": later_id, "skipped": True},
                            )
                    break

        if failed and (plan.rollback_on_failure or plan.rollback_policy is RollbackPolicy.ON_FAILURE):
            for completed_id in reversed(order):
                completed_action = actions_by_id[completed_id]
                original_result = action_results.get(completed_id)
                if states.get(completed_id) is not ActionState.SUCCESS or original_result is None:
                    continue
                capability = self._dispatcher._registry.get(completed_action.capability)
                if capability is None or not capability.metadata.rollback_supported:
                    continue
                rollback_request = ActionRequest.create(
                    capability=completed_action.capability,
                    parameters=dict(completed_action.parameters),
                    requester=plan.requester,
                )
                rollback_results[completed_id] = self._dispatcher.rollback(
                    rollback_request, original_result.data, plan_id=plan.plan_id, action_id=completed_id
                )

        if failed and plan.failure_policy is PlanFailurePolicy.STOP:
            final_status = PlanStatus.FAILED
        elif failed and plan.failure_policy is PlanFailurePolicy.CONTINUE:
            final_status = PlanStatus.PARTIAL_SUCCESS
        elif all(states.get(action_id) is ActionState.SUCCESS for action_id in states):
            final_status = PlanStatus.SUCCESS
        else:
            final_status = PlanStatus.PENDING

        summary = self._build_summary(plan, final_status, action_results)
        return PlanResult(
            plan_id=plan.plan_id,
            final_status=final_status,
            action_results=action_results,
            summary=summary,
            failed_action_ids=sorted(failed),
            skipped_action_ids=sorted(skipped),
            rollback_results=rollback_results,
        )

    @staticmethod
    def _build_summary(plan: ActionPlan, final_status: PlanStatus, action_results: dict[str, ActionResult]) -> str:
        if final_status is PlanStatus.SUCCESS:
            return "Plan completed successfully."
        if final_status is PlanStatus.FAILED:
            return "Plan failed."
        if final_status is PlanStatus.PARTIAL_SUCCESS:
            return "Plan partially completed."
        return "Plan pending."
