"""Composition root; consumers submit ActionRequest instances to Dispatcher."""
from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.capabilities.mock import MockCreateDir, MockEcho, MockOpenApp, MockOpenFile
from astra_sentinel.config import RuntimeConfig, default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.security.policy import PolicyEngine


def build_default_runtime(config: RuntimeConfig | None = None) -> tuple[Dispatcher, InMemoryAuditLogger]:
    config = config or default_config()
    registry = CapabilityRegistry()
    for capability in (MockEcho(), MockOpenApp(), MockOpenFile(), MockCreateDir()):
        if capability.metadata.name in config.enabled_capabilities:
            registry.register(capability)
    audit = InMemoryAuditLogger()
    return Dispatcher(registry, PolicyEngine(config.policy), audit), audit
