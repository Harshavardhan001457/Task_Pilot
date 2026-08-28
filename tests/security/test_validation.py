import pytest

from astra_sentinel.core.errors import RequestValidationError
from astra_sentinel.core.models import ActionRequest, ResultStatus
from tests.conftest import request


@pytest.mark.parametrize("payload", [
    {},
    {"capability": "mock.echo", "parameters": {}, "requester": "cli", "confirmed": True},
    {"capability": "mock.echo", "parameters": {}, "requester": "cli", "timestamp": "forged"},
    {"capability": None, "parameters": {}, "requester": "cli"},
    {"capability": "mock.echo", "parameters": [], "requester": "cli"},
])
def test_untrusted_request_shape_is_strict(payload):
    with pytest.raises(RequestValidationError):
        ActionRequest.from_untrusted(payload)


def test_missing_and_unexpected_parameters_are_validation_errors(runtime):
    dispatcher, _ = runtime
    assert dispatcher.dispatch(request("mock.echo", {})).status is ResultStatus.VALIDATION_ERROR
    assert dispatcher.dispatch(request("mock.echo", {"message": "x", "confirmed": True})).status is ResultStatus.VALIDATION_ERROR


@pytest.mark.parametrize("parameters", [
    {"message": None}, {"message": 7}, {"message": {"nested": "object"}}, {"message": "x" * 4097},
])
def test_unreasonable_or_wrong_parameter_types_fail(runtime, parameters):
    dispatcher, _ = runtime
    assert dispatcher.dispatch(request("mock.echo", parameters)).status is ResultStatus.VALIDATION_ERROR


def test_unknown_capability_is_denied_and_audited(runtime):
    dispatcher, audit = runtime
    result = dispatcher.dispatch(request("astra_sentinel.capabilities.mock.MockEcho.execute", {"message": "x"}))
    assert result.status is ResultStatus.DENIED
    assert audit.events[-1].error_code == "UNKNOWN_CAPABILITY"
