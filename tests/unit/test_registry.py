import pytest

from astra_sentinel.capabilities.mock import MockEcho
from astra_sentinel.core.errors import DuplicateCapabilityError
from astra_sentinel.core.registry import CapabilityRegistry


def test_registry_registers_and_lists_capability():
    registry = CapabilityRegistry()
    registry.register(MockEcho())
    assert registry.get("mock.echo") is not None
    assert registry.list_names() == ("mock.echo",)


def test_unknown_capability_is_not_found():
    assert CapabilityRegistry().get("python.os.system") is None


def test_duplicate_registration_is_rejected():
    registry = CapabilityRegistry()
    registry.register(MockEcho())
    with pytest.raises(DuplicateCapabilityError):
        registry.register(MockEcho())
