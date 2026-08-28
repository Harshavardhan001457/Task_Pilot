from dataclasses import replace

from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.capabilities.mock import MockEcho
from astra_sentinel.config import RuntimeConfig, default_config
from astra_sentinel.core.models import ResultStatus
from astra_sentinel.runtime import build_default_runtime
from astra_sentinel.security.risk import RiskLevel
from tests.conftest import request


def test_unknown_requester_and_missing_permission_are_denied(runtime):
    dispatcher, _ = runtime
    assert dispatcher.dispatch(request("mock.echo", {"message": "x"}, "planner")).status is ResultStatus.DENIED
    assert dispatcher.dispatch(request("mock.create_dir", {"path": "safe"})).status is ResultStatus.DENIED


def test_explicit_denial_precedes_confirmation():
    base = default_config()
    config = RuntimeConfig(replace(base.policy, explicitly_denied_capabilities=frozenset({"mock.echo"})), base.enabled_capabilities)
    dispatcher, _ = build_default_runtime(config)
    assert dispatcher.dispatch(request("mock.echo", {"message": "x"})).status is ResultStatus.DENIED


def test_l0_l1_are_allowed_and_l2_is_configurable(runtime):
    dispatcher, _ = runtime
    assert dispatcher.dispatch(request("mock.echo", {"message": "x"})).status is ResultStatus.SUCCESS
    assert dispatcher.dispatch(request("mock.open_app", {"app": "vscode"})).status is ResultStatus.SUCCESS
    assert dispatcher.dispatch(request("mock.create_dir", {"path": "folder"})).status is ResultStatus.DENIED


class DangerousMock(MockEcho):
    def __init__(self, name: str, risk: RiskLevel):
        self.metadata = CapabilityMetadata(name, "test only", "1", {"message": str}, frozenset(), risk)
        self.executed = False
    def execute(self, parameters):
        self.executed = True
        return super().execute(parameters)


def test_l3_confirms_and_l4_denies_without_execution():
    from astra_sentinel.audit.logger import InMemoryAuditLogger
    from astra_sentinel.core.dispatcher import Dispatcher
    from astra_sentinel.core.registry import CapabilityRegistry
    from astra_sentinel.security.policy import PolicyEngine
    base = default_config()
    registry = CapabilityRegistry()
    destructive, restricted = DangerousMock("test.destroy", RiskLevel.DESTRUCTIVE), DangerousMock("test.restricted", RiskLevel.RESTRICTED)
    registry.register(destructive); registry.register(restricted)
    dispatcher = Dispatcher(registry, PolicyEngine(base.policy), InMemoryAuditLogger())
    assert dispatcher.dispatch(request("test.destroy", {"message": "x"})).status is ResultStatus.CONFIRMATION_REQUIRED
    assert dispatcher.dispatch(request("test.restricted", {"message": "x"})).status is ResultStatus.DENIED
    assert not destructive.executed and not restricted.executed
