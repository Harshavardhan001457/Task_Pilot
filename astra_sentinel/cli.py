"""Small terminal interface for the approved V1 actions."""
import shlex
import json
import logging
from collections.abc import Callable

from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.models import ActionRequest, ActionResult, ResultStatus
from astra_sentinel.core.plan import ActionPlan, ActionPlanItem, PlanExecutor, PlanResult
from astra_sentinel.core.planner import Goal, Planner, PlanningError

INVALID_COMMAND = "cli.invalid_command"
LOGGER = logging.getLogger(__name__)

COMMANDS: dict[tuple[str, ...], tuple[str, str]] = {
    ("open", "app"): ("application.open_app", "app"),
    ("is", "app", "running"): ("application.is_app_running", "app"),
    ("process", "info"): ("application.get_process_info", "app"),
    ("find", "file"): ("filesystem.find_file", "name"),
    ("get", "file", "info"): ("filesystem.get_file_info", "path"),
    ("open", "file"): ("filesystem.open_file", "path"),
    ("create", "dir"): ("filesystem.create_dir", "path"),
    ("create", "file"): ("filesystem.create_file", "path"),
    ("move", "file"): ("filesystem.move_file", "source"),
    ("copy", "file"): ("filesystem.copy_file", "source"),
    ("rename", "file"): ("filesystem.rename_file", "path"),
    ("list", "running", "apps"): ("system.list_running_apps", ""),
    ("cpu", "usage"): ("system.get_cpu_usage", ""),
    ("memory", "usage"): ("system.get_memory_usage", ""),
    ("disk", "usage"): ("system.get_disk_usage", ""),
    ("battery", "status"): ("system.get_battery_status", ""),
    ("system", "info"): ("system.get_system_info", ""),
}


def request_from_command(command: str) -> ActionRequest | None:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return _invalid_request()
    if not tokens:
        return None

    words = tuple(token.casefold() for token in tokens)
    for prefix, (capability, parameter) in COMMANDS.items():
        if words[:len(prefix)] != prefix:
            continue
        if parameter == "":
            if len(tokens) == len(prefix):
                return ActionRequest.from_untrusted({"capability": capability, "parameters": {}})
            continue
        if capability == "filesystem.move_file" and prefix == ("move", "file"):
            if len(tokens) == len(prefix) + 2:
                return ActionRequest.from_untrusted({
                    "capability": capability,
                    "parameters": {"source": tokens[-2], "destination": tokens[-1]},
                })
        elif capability == "filesystem.copy_file" and prefix == ("copy", "file"):
            if len(tokens) == len(prefix) + 2:
                return ActionRequest.from_untrusted({
                    "capability": capability,
                    "parameters": {"source": tokens[-2], "destination": tokens[-1]},
                })
        elif capability == "filesystem.rename_file" and prefix == ("rename", "file"):
            if len(tokens) == len(prefix) + 2:
                return ActionRequest.from_untrusted({
                    "capability": capability,
                    "parameters": {"path": tokens[-2], "new_name": tokens[-1]},
                })
        elif len(tokens) == len(prefix) + 1:
            return ActionRequest.from_untrusted({
                "capability": capability,
                "parameters": {parameter: tokens[-1]},
            })
    return _invalid_request()


def _invalid_request() -> ActionRequest:
    return ActionRequest.from_untrusted({"capability": INVALID_COMMAND, "parameters": {}})


def format_result(request: ActionRequest, result: ActionResult) -> str:
    if result.status is ResultStatus.SUCCESS:
        if request.capability == "filesystem.find_file":
            matches = result.data.get("matches", [])
            return "[OK] Found:\n" + ("\n".join(matches) if matches else "No matching files found.")
        if request.capability == "filesystem.get_file_info":
            return "[OK] File information retrieved.\n" + str(result)
        if request.capability == "application.is_app_running":
            state = "running" if result.data.get("running") else "not running"
            return f"[OK] Application is {state}."
        if request.capability == "application.open_app":
            return "[OK] Application opened successfully."
        if request.capability == "application.get_process_info":
            return "[OK] Process information retrieved.\n" + str(result.data)
        if request.capability == "filesystem.open_file":
            return "[OK] File opened successfully."
        if request.capability == "filesystem.create_dir":
            return "[OK] Directory created successfully."
        if request.capability == "filesystem.create_file":
            return "[OK] File created successfully."
        if request.capability == "filesystem.move_file":
            return "[OK] File moved successfully."
        if request.capability == "filesystem.copy_file":
            return "[OK] File copied successfully."
        if request.capability == "filesystem.rename_file":
            return "[OK] File renamed successfully."
        if request.capability.startswith("system."):
            return "[OK] " + str(result.data)
        return "[OK] Action completed."

    if request.capability == INVALID_COMMAND:
        return "[ERROR] Unknown command.\nType: help"
    if result.status is ResultStatus.DENIED:
        return "[ERROR] Access denied."
    if result.status is ResultStatus.VALIDATION_ERROR:
        return "[ERROR] File or path is invalid, unavailable, or outside the allowed workspace."
    if result.status is ResultStatus.CONFIRMATION_REQUIRED:
        return "[ERROR] This action requires confirmation and is unavailable in V1."
    return "[ERROR] Action failed."


def _format_inspection(command: str, dispatcher: Dispatcher) -> str:
    config = dispatcher.config
    if command == "help":
        return "Available commands:\n  help\n  plan <json>\n  goal <json>\n  inspect\n  execute\n  show config\n  show resources\n  show permissions\n  show capabilities\n  show apps\n  exit / quit\n\nUse goal to create a pending plan, inspect to review it, and execute to submit it through Sentinel."
    if command == "show capabilities":
        lines = []
        for name in dispatcher.registry.list_names():
            metadata = dispatcher.registry.get(name).metadata
            category = name.split(".", 1)[0]
            permissions = ", ".join(sorted(permission.value for permission in metadata.required_permissions)) or "none"
            rollback = "Supported" if metadata.rollback_supported else "Not supported"
            lines.append(f"{name}\n  Category: {category}\n  Permission: {permissions}\n  Risk: L{int(metadata.risk_level)}\n  Rollback: {rollback}")
        return "Capabilities\n\n" + ("\n\n".join(lines) or "No capabilities enabled.")
    if command == "show permissions":
        grants = dispatcher.policy.config.permission_grants.grants
        lines = [f"{requester}: " + (", ".join(sorted(permission.value for permission in permissions)) or "none") for requester, permissions in sorted(grants.items())]
        return "Permissions\n\n" + ("\n".join(lines) or "No permissions configured.")
    if command == "show resources":
        rules = getattr(config, "resource_rules", None) or {}
        lines = [f"{requester}: " + (", ".join(sorted(root.name for root in roots)) or "none") for requester, roots in sorted(rules.items())]
        return "Allowed resources\n\n" + ("\n".join(lines) or "No resources configured.")
    if command == "show apps":
        apps = getattr(config, "registered_applications", None) or {}
        return "Registered applications\n\n" + ("\n".join(sorted(apps)) or "No applications registered.")
    if command == "show config":
        roots = getattr(config, "allowed_filesystem_roots", ()) if config else ()
        return "Configuration\n\n" + "\n".join((
            f"Enabled capabilities: {len(dispatcher.registry.list_names())}",
            f"Workspace configured: {'yes' if roots else 'no'}",
            f"Resource policy: {'configured' if getattr(config, 'resource_rules', None) is not None else 'sandbox'}",
            f"Modify actions: {'enabled' if dispatcher.policy.config.allow_modify else 'disabled'}",
            f"Registered applications: {len(getattr(config, 'registered_applications', None) or {})}",
        ))
    return ""


def execute_plan_command(payload: str, executor: PlanExecutor) -> str:
    try:
        document = json.loads(payload)
        actions = tuple(
            ActionPlanItem(
                action_id=item["action_id"],
                capability=item["capability"],
                parameters=item.get("parameters", {}),
                depends_on=tuple(item.get("depends_on", ())),
            )
            for item in document["actions"]
        )
        plan = ActionPlan(
            plan_id=document["plan_id"],
            description=document["description"],
            requester="cli",
            actions=actions,
            failure_policy=document.get("failure_policy", "STOP"),
            rollback_on_failure=document.get("rollback_on_failure", False),
        )
        return format_plan_result(executor.execute(plan))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return f"[ERROR] Invalid plan: {error}"


def format_plan_result(result: PlanResult) -> str:
    lines = [f"[PLAN] {result.final_status}: {result.summary}"]
    if result.failed_action_ids:
        lines.append("Failed: " + ", ".join(result.failed_action_ids))
        for action_id in result.failed_action_ids:
            action_result = result.action_results.get(action_id)
            if action_result is not None:
                lines.append(f"  {action_id}: {action_result.message}")
    if result.skipped_action_ids:
        lines.append("Skipped: " + ", ".join(result.skipped_action_ids))
    if result.rollback_results:
        lines.append("Rollback:")
        lines.extend(f"  {action_id}: {rollback.status.value}" for action_id, rollback in result.rollback_results.items())
    return "\n".join(lines)


def run_cli(
    dispatcher: Dispatcher,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    planner = Planner(dispatcher.registry)
    executor = PlanExecutor(dispatcher)
    pending_plan: ActionPlan | None = None
    while True:
        try:
            command = input_fn("ASTRA > ")
        except EOFError:
            output_fn("")
            return
        if command.strip().casefold() in {"exit", "quit"}:
            return
        if command.casefold().startswith("plan "):
            output_fn(execute_plan_command(command[5:].strip(), executor))
            continue
        if command.casefold().startswith("goal "):
            try:
                document = json.loads(command[5:].strip())
                pending_plan = planner.create_plan(Goal(
                    goal=document["goal"],
                    parameters=document.get("parameters", {}),
                    requester="cli",
                    context=document.get("context", {}),
                ))
                output_fn(planner.inspect_plan(pending_plan))
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, PlanningError) as error:
                output_fn(f"[ERROR] Invalid goal: {error}")
            continue
        if command.strip().casefold() == "inspect":
            output_fn(planner.inspect_plan(pending_plan) if pending_plan else "[ERROR] No pending plan.")
            continue
        if command.strip().casefold() == "execute":
            output_fn(format_plan_result(executor.execute(pending_plan)) if pending_plan else "[ERROR] No pending plan.")
            continue
        inspection_command = command.strip().casefold()
        if inspection_command == "help" or inspection_command.startswith("show "):
            output_fn(_format_inspection(inspection_command, dispatcher) or "[ERROR] Unknown command.\nType: help")
            continue
        request = request_from_command(command)
        if request is None:
            continue
        try:
            output_fn(format_result(request, dispatcher.dispatch(request)))
        except Exception:
            LOGGER.exception("CLI command failed")
            output_fn("[ERROR] Action failed safely. Type: help")
