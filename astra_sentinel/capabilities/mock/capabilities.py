"""Pure mock capabilities for Phase 1 boundary testing."""
from typing import Any

from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.security.permissions import Permission
from astra_sentinel.security.risk import RiskLevel


class _MockCapability:
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return data.get("simulated") is True


class MockEcho(_MockCapability):
    metadata = CapabilityMetadata("mock.echo", "Return a supplied message.", "1.0", {"message": str}, frozenset(), RiskLevel.READ_ONLY)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"simulated": True, "message": parameters["message"]}


class MockOpenApp(_MockCapability):
    metadata = CapabilityMetadata("mock.open_app", "Simulate opening an application.", "1.0", {"app": str}, frozenset({Permission.APPLICATION_LAUNCH}), RiskLevel.LOW)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"simulated": True, "opened_app": parameters["app"]}


class MockOpenFile(_MockCapability):
    metadata = CapabilityMetadata("mock.open_file", "Simulate opening a file.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_READ}), RiskLevel.LOW)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"simulated": True, "opened_file": parameters["path"]}


class MockCreateDir(_MockCapability):
    metadata = CapabilityMetadata("mock.create_dir", "Simulate creating a directory.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_WRITE}), RiskLevel.MODIFY)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return {"simulated": True, "created_directory": parameters["path"]}
