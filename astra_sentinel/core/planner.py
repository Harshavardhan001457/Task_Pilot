"""Planning-only translation from structured goals to V2 action plans."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from astra_sentinel.audit.logger import sanitize_parameters
from astra_sentinel.core.plan import ActionPlan, ActionPlanItem, plan_execution_order, validate_plan_structure
from astra_sentinel.core.registry import CapabilityRegistry


class PlanningError(ValueError):
    """Raised when a goal cannot be safely translated into a known action plan."""


@dataclass(frozen=True, slots=True)
class Goal:
    """Structured, non-executable intent supplied to :class:`Planner`."""

    goal: str
    parameters: dict[str, Any] = field(default_factory=dict)
    requester: str = "internal"
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.goal, str) or not self.goal:
            raise PlanningError("goal must be a non-empty string")
        if not isinstance(self.parameters, dict):
            raise PlanningError("goal parameters must be an object")
        if not isinstance(self.requester, str) or not self.requester:
            raise PlanningError("goal requester must be a non-empty string")
        if not isinstance(self.context, dict):
            raise PlanningError("goal context must be an object")


class Planner:
    """Builds V2 ``ActionPlan`` objects without dispatching or executing them."""

    supported_goal_types = ("create_directory", "create_project")

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def create_plan(self, goal: Goal) -> ActionPlan:
        if goal.goal == "create_directory":
            path = self._required_path(goal)
            actions = (ActionPlanItem("create_directory", "filesystem.create_dir", {"path": path}),)
            description = f"Create directory at {path}"
        elif goal.goal == "create_project":
            path = self._required_path(goal)
            readme = goal.parameters.get("readme", False)
            if not isinstance(readme, bool):
                raise PlanningError("create_project readme must be a boolean")
            actions = [ActionPlanItem("create_directory", "filesystem.create_dir", {"path": path})]
            if readme:
                actions.append(ActionPlanItem(
                    "create_readme",
                    "filesystem.create_file",
                    {"path": path.rstrip("/\\") + "/README.md"},
                    depends_on=("create_directory",),
                ))
            actions = tuple(actions)
            description = f"Create project at {path}" + (" with README" if readme else "")
        else:
            raise PlanningError(f"unsupported goal: {goal.goal}")

        plan = ActionPlan(
            plan_id=self._plan_id(goal),
            description=description,
            requester=goal.requester,
            actions=actions,
        )
        try:
            validate_plan_structure(plan, self._registry)
        except ValueError as error:
            raise PlanningError(f"invalid generated plan: {error}") from error
        return plan

    def inspect_plan(self, plan: ActionPlan) -> str:
        """Render a plan from registry metadata without dispatching any action."""
        try:
            validate_plan_structure(plan, self._registry)
            order = plan_execution_order(plan)
        except ValueError as error:
            raise PlanningError(f"invalid plan for inspection: {error}") from error

        lines = [f"Plan ID: {plan.plan_id}", f"Description: {plan.description}", "Actions:"]
        for index, action in enumerate(plan.actions, start=1):
            capability = self._registry.get(action.capability)
            if capability is None:  # Covered by validation; protects the display boundary.
                raise PlanningError(f"unknown capability in plan: {action.capability}")
            metadata = capability.metadata
            parameters = sanitize_parameters(action.parameters, metadata.sensitive_parameters)
            permissions = ", ".join(sorted(permission.value for permission in metadata.required_permissions)) or "none"
            dependencies = ", ".join(action.depends_on) or "none"
            lines.extend((
                f"{index}. {action.action_id}",
                f"   capability: {action.capability}",
                f"   parameters: {parameters}",
                f"   dependencies: {dependencies}",
                f"   required permissions: {permissions}",
                f"   risk: L{int(metadata.risk_level)}",
            ))
        lines.append("Execution order: " + " -> ".join(order))
        return "\n".join(lines)

    @staticmethod
    def _required_path(goal: Goal) -> str:
        path = goal.parameters.get("path")
        if not isinstance(path, str) or not path:
            raise PlanningError(f"{goal.goal} requires a non-empty path")
        return path

    @staticmethod
    def _plan_id(goal: Goal) -> str:
        """Derive a stable identifier from the supported, structured goal input."""
        values = tuple(sorted((key, repr(value)) for key, value in goal.parameters.items()))
        return f"plan-{uuid5(NAMESPACE_URL, repr((goal.goal, values, goal.requester)))}"
