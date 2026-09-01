"""Application capabilities use a trusted identifier-to-executable registry."""
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.config import ApplicationConfig
from astra_sentinel.core.errors import RequestValidationError
from astra_sentinel.security.permissions import Permission
from astra_sentinel.security.risk import RiskLevel


class _RegisteredApplication:
    def __init__(self, applications: dict[str, ApplicationConfig]) -> None:
        self._applications = dict(applications)

    def _application(self, app_id: str) -> ApplicationConfig:
        application = self._applications.get(app_id)
        if application is None:
            raise RequestValidationError("application is not registered")
        if not application.executable.is_file():
            raise RequestValidationError("registered application executable is unavailable")
        return application


class OpenApp(_RegisteredApplication):
    metadata = CapabilityMetadata("application.open_app", "Launch a registered application.", "1.0", {"app": str}, frozenset({Permission.APPLICATION_LAUNCH}), RiskLevel.LOW)
    def __init__(self, applications: dict[str, ApplicationConfig], launcher: Callable[[Path], None] | None = None, running: Callable[[str], bool] | None = None) -> None:
        super().__init__(applications)
        self._launcher = launcher or self._native_launch
        self._running = running or self._native_is_running
        self._last_process: str | None = None
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._application(parameters["app"])
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        app = self._application(parameters["app"])
        self._launcher(app.executable)
        self._last_process = app.process_name
        return {"app": parameters["app"]}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._last_process is not None and self._running(self._last_process)
    @staticmethod
    def _native_launch(executable: Path) -> None:
        subprocess.Popen([str(executable)], shell=False, close_fds=True)
    @staticmethod
    def _native_is_running(process_name: str) -> bool:
        if os.name != "nt":
            return False
        completed = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/NH"], shell=False, check=False, capture_output=True, text=True)
        return process_name.casefold() in completed.stdout.casefold()


class IsAppRunning(_RegisteredApplication):
    metadata = CapabilityMetadata("application.is_app_running", "Check a registered application process.", "1.0", {"app": str}, frozenset({Permission.SYSTEM_READ}), RiskLevel.READ_ONLY)
    def __init__(self, applications: dict[str, ApplicationConfig], running: Callable[[str], bool] | None = None) -> None:
        super().__init__(applications)
        self._running = running or OpenApp._native_is_running
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._application(parameters["app"])
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"app": parameters["app"], "running": self._running(self._application(parameters["app"]).process_name)}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return data["app"] == parameters["app"] and isinstance(data["running"], bool)
