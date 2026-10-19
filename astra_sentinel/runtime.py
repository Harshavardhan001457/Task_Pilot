"""Composition root; consumers submit ActionRequest instances to Dispatcher."""
from dataclasses import replace
from astra_sentinel.audit.logger import InMemoryAuditLogger
from astra_sentinel.capabilities.real import (
    CopyFile,
    CreateDir,
    CreateFile,
    FindFile,
    GetFileInfo,
    GetProcessInfo,
    IsAppRunning,
    ListRunningApps,
    MoveFile,
    OpenApp,
    OpenFile,
    RenameFile,
)
from astra_sentinel.capabilities.real.system import (
    GetBatteryStatus,
    GetCpuUsage,
    GetDiskUsage,
    GetMemoryUsage,
    GetSystemInfo,
)
from astra_sentinel.config import RuntimeConfig, default_config
from astra_sentinel.core.dispatcher import Dispatcher
from astra_sentinel.core.registry import CapabilityRegistry
from astra_sentinel.security.policy import PolicyEngine


def build_default_runtime(config: RuntimeConfig | None = None) -> tuple[Dispatcher, InMemoryAuditLogger]:
    config = config or default_config()
    registry = CapabilityRegistry()
    applications = config.registered_applications or {}
    roots = config.allowed_filesystem_roots
    for capability in (
        OpenApp(applications),
        IsAppRunning(applications),
        GetProcessInfo(applications),
        ListRunningApps(applications),
        FindFile(roots),
        GetFileInfo(roots),
        OpenFile(roots),
        CreateDir(roots),
        CreateFile(roots),
        MoveFile(roots),
        CopyFile(roots),
        RenameFile(roots),
        GetCpuUsage(),
        GetMemoryUsage(),
        GetDiskUsage(),
        GetBatteryStatus(),
        GetSystemInfo(),
    ):
        if capability.metadata.name in config.enabled_capabilities:
            registry.register(capability)
    audit = InMemoryAuditLogger()
    policy = replace(config.policy, resource_rules=config.resource_rules)
    return Dispatcher(registry, PolicyEngine(policy), audit, config), audit
