"""Controlled, explicit capability registration and lookup."""
from astra_sentinel.capabilities.base import Capability
from .errors import DuplicateCapabilityError


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        name = capability.metadata.name
        if name in self._capabilities:
            raise DuplicateCapabilityError(f"capability already registered: {name}")
        self._capabilities[name] = capability

    def get(self, name: str) -> Capability | None:
        return self._capabilities.get(name)

    def list_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))
