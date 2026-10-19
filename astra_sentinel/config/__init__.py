"""Safe, explicit runtime configuration."""
from dataclasses import dataclass
from pathlib import Path

from astra_sentinel.config.allowlist import (
    DEFAULT_ALLOWED_APPLICATIONS,
    DEFAULT_ALLOW_MODIFY,
    DEFAULT_ALLOWED_FILESYSTEM_ROOTS,
    DEFAULT_ENABLED_CAPABILITIES,
    DEFAULT_PERMISSION_GRANTS,
)
from astra_sentinel.security.permissions import PermissionGrants
from astra_sentinel.security.policy import PolicyConfig


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    policy: PolicyConfig
    enabled_capabilities: frozenset[str]
    allowed_filesystem_roots: tuple[Path, ...] = ()
    registered_applications: dict[str, "ApplicationConfig"] | None = None
    audit_backend: str = "memory"
    resource_rules: dict[str, tuple[Path, ...]] | None = None


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Trusted application mapping; callers can only supply the mapping key."""
    executable: Path
    process_name: str


def default_config() -> RuntimeConfig:
    grants = PermissionGrants(DEFAULT_PERMISSION_GRANTS)
    valid_roots: list[Path] = []
    for configured_root in DEFAULT_ALLOWED_FILESYSTEM_ROOTS:
        candidate = Path(configured_root)
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_dir() and resolved not in valid_roots:
            valid_roots.append(resolved)

    roots = tuple(valid_roots)

    applications: dict[str, ApplicationConfig] = {}
    for app_id, executable_path in DEFAULT_ALLOWED_APPLICATIONS.items():
        executable = Path(executable_path)
        if executable.is_file():
            applications[app_id] = ApplicationConfig(executable.resolve(), executable.name)

    resource_rules = {requester: roots for requester in ("cli", "internal")}
    return RuntimeConfig(
        PolicyConfig(frozenset({"cli", "internal"}), grants, allow_modify=DEFAULT_ALLOW_MODIFY),
        DEFAULT_ENABLED_CAPABILITIES,
        roots,
        applications,
        resource_rules=resource_rules,
    )
