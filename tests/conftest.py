import pytest

from astra_sentinel import build_default_runtime
from astra_sentinel.core.models import ActionRequest


@pytest.fixture
def runtime():
    return build_default_runtime()


def request(capability: str, parameters: dict, requester: str = "cli") -> ActionRequest:
    return ActionRequest.create(capability=capability, parameters=parameters, requester=requester)
