"""Small terminal interface for the approved V1 actions."""
import shlex
from collections.abc import Callable

from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.models import ActionRequest, ActionResult, ResultStatus

INVALID_COMMAND = "cli.invalid_command"

COMMANDS: dict[tuple[str, ...], tuple[str, str]] = {
    ("open", "app"): ("application.open_app", "app"),
    ("is", "app", "running"): ("application.is_app_running", "app"),
    ("find", "file"): ("filesystem.find_file", "name"),
    ("get", "file", "info"): ("filesystem.get_file_info", "path"),
    ("open", "file"): ("filesystem.open_file", "path"),
    ("create", "dir"): ("filesystem.create_dir", "path"),
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
        if words[:len(prefix)] == prefix and len(tokens) == len(prefix) + 1:
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
        if request.capability == "filesystem.open_file":
            return "[OK] File opened successfully."
        if request.capability == "filesystem.create_dir":
            return "[OK] Directory created successfully."
        return "[OK] Action completed."

    if request.capability == INVALID_COMMAND:
        return "[ERROR] Unknown command or invalid arguments."
    if result.status is ResultStatus.DENIED:
        return "[ERROR] Access denied."
    if result.status is ResultStatus.VALIDATION_ERROR:
        return "[ERROR] File or path is invalid, unavailable, or outside the allowed workspace."
    if result.status is ResultStatus.CONFIRMATION_REQUIRED:
        return "[ERROR] This action requires confirmation and is unavailable in V1."
    return "[ERROR] Action failed."


def run_cli(
    dispatcher: Dispatcher,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    while True:
        try:
            command = input_fn("ASTRA > ")
        except EOFError:
            output_fn("")
            return
        if command.strip().casefold() in {"exit", "quit"}:
            return
        request = request_from_command(command)
        if request is None:
            continue
        output_fn(format_result(request, dispatcher.dispatch(request)))