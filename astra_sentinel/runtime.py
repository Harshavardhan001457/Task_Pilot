"""Composition root; consumers submit ActionRequest instances to Dispatcher."""
from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.capabilities.real import CreateDir, FindFile, GetFileInfo, IsAppRunning, OpenApp, OpenFile
from astra_sentinel.config import RuntimeConfig, default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.security.policy import PolicyEngine


def build_default_runtime(config: RuntimeConfig | None = None) -> tuple[Dispatcher, InMemoryAuditLogger]:
    config = config or default_config()
    registry = CapabilityRegistry()
    applications = config.registered_applications or {}
    for capability in (
        OpenApp(applications), IsAppRunning(applications), FindFile(config.allowed_filesystem_roots),
        GetFileInfo(config.allowed_filesystem_roots), OpenFile(config.allowed_filesystem_roots),
        CreateDir(config.allowed_filesystem_roots),
    ):
        if capability.metadata.name in config.enabled_capabilities:
            registry.register(capability)
    audit = InMemoryAuditLogger()
    return Dispatcher(registry, PolicyEngine(config.policy), audit), audit
