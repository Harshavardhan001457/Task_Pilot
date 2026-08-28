from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.capabilities.mock import MockEcho
from astra_sentinel.config import default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.models import ResultStatus
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.security.policy import PolicyEngine
from astra_sentinel.security.risk import RiskLevel
from tests.conftest import request


class TrackingMock(MockEcho):
    metadata = CapabilityMetadata("test.track", "test", "1", {"message": str}, frozenset(), RiskLevel.READ_ONLY)
    def __init__(self, execute_error=False, verify_error=False, verify_value=True):
        self.executed = self.verified = False
        self.execute_error, self.verify_error, self.verify_value = execute_error, verify_error, verify_value
    def execute(self, parameters):
        self.executed = True
        if self.execute_error: raise RuntimeError("internal")
        return super().execute(parameters)
    def verify(self, parameters, data):
        self.verified = True
        if self.verify_error: raise RuntimeError("internal")
        return self.verify_value


def dispatcher_for(capability):
    registry = CapabilityRegistry(); registry.register(capability)
    audit = InMemoryAuditLogger()
    return Dispatcher(registry, PolicyEngine(default_config().policy), audit), audit


def test_execution_and_verification_flow():
    capability = TrackingMock()
    dispatcher, audit = dispatcher_for(capability)
    result = dispatcher.dispatch(request("test.track", {"message": "x"}))
    assert result.status is ResultStatus.SUCCESS
    assert capability.executed and capability.verified
    assert audit.events[-1].verification_status == "passed"


def test_execution_and_verifier_errors_are_safe_results():
    for capability, expected in [(TrackingMock(execute_error=True), ResultStatus.EXECUTION_ERROR), (TrackingMock(verify_error=True), ResultStatus.VERIFICATION_ERROR), (TrackingMock(verify_value=False), ResultStatus.VERIFICATION_ERROR)]:
        dispatcher, _ = dispatcher_for(capability)
        assert dispatcher.dispatch(request("test.track", {"message": "x"})).status is expected
