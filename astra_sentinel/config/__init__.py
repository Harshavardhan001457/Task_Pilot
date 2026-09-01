"""Safe, explicit runtime configuration."""
import os
from dataclasses import dataclass
from pathlib import Path

from astra_sentinel.config.allowlist import (
    DEFAULT_ALLOWED_APPLICATIONS,
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


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Trusted application mapping; callers can only supply the mapping key."""
    executable: Path
    process_name: str


def default_config() -> RuntimeConfig:
    grants = PermissionGrants(DEFAULT_PERMISSION_GRANTS)
    roots: tuple[Path, ...] = ()

    workspace = os.environ.get("ASTRA_WORKSPACE")
    candidate_roots = [Path(workspace)] if workspace else []
    candidate_roots.extend(Path(root) for root in DEFAULT_ALLOWED_FILESYSTEM_ROOTS)

    valid_roots: list[Path] = []
    for candidate in candidate_roots:
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_dir() and resolved not in valid_roots:
            valid_roots.append(resolved)

    if valid_roots:
        roots = tuple(valid_roots)

    applications: dict[str, ApplicationConfig] = {}
    for app_id, executable_path in DEFAULT_ALLOWED_APPLICATIONS.items():
        executable = Path(executable_path)
        if executable.is_file():
            applications[app_id] = ApplicationConfig(executable.resolve(), executable.name)

    return RuntimeConfig(
        PolicyConfig(frozenset({"cli", "internal"}), grants, allow_modify=False),
        DEFAULT_ENABLED_CAPABILITIES,
        roots,
        applications,
    )
