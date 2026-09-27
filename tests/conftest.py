import pytest
import astra_sentinel.config as config_module

from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.capabilities.mock import MockCreateDir, MockEcho, MockOpenApp, MockOpenFile
from astra_sentinel.config import RuntimeConfig, default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.core.models import ActionRequest
from astra_sentinel.security.policy import PolicyEngine


@pytest.fixture
def runtime():
    return mock_runtime()


@pytest.fixture(autouse=True)
def temporary_allowlisted_root(request, monkeypatch):
    """Tests with temporary roots exercise the standard allowlist configuration."""
    if "tmp_path" in request.fixturenames:
        root = request.getfixturevalue("tmp_path")
        monkeypatch.setattr(config_module, "DEFAULT_ALLOWED_FILESYSTEM_ROOTS", (str(root),))
        monkeypatch.setattr(config_module, "DEFAULT_ALLOW_MODIFY", True)


def mock_runtime(config: RuntimeConfig | None = None):
    config = config or default_config()
    registry = CapabilityRegistry()
    for capability in (MockEcho(), MockOpenApp(), MockOpenFile(), MockCreateDir()):
        registry.register(capability)
    audit = InMemoryAuditLogger()
    return Dispatcher(registry, PolicyEngine(config.policy), audit), audit


def request(capability: str, parameters: dict, requester: str = "cli") -> ActionRequest:
    return ActionRequest.create(capability=capability, parameters=parameters, requester=requester)
