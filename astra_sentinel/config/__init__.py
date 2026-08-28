"""Safe, explicit runtime configuration."""
from dataclasses import dataclass

from astra_sentinel.security.permissions import Permission, PermissionGrants
from astra_sentinel.security.policy import PolicyConfig


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    policy: PolicyConfig
    enabled_capabilities: frozenset[str]
    audit_backend: str = "memory"


def default_config() -> RuntimeConfig:
    grants = PermissionGrants({
        "cli": frozenset({Permission.APPLICATION_LAUNCH, Permission.FILESYSTEM_READ}),
        "internal": frozenset({Permission.APPLICATION_LAUNCH, Permission.FILESYSTEM_READ}),
    })
    return RuntimeConfig(
        PolicyConfig(frozenset({"cli", "internal"}), grants, allow_modify=False),
        frozenset({"mock.echo", "mock.open_app", "mock.open_file", "mock.create_dir"}),
    )
