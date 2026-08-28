"""Named permissions and explicit per-requester grants."""
from dataclasses import dataclass
from enum import StrEnum


class Permission(StrEnum):
    SYSTEM_READ = "system.read"
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_DELETE = "filesystem.delete"
    APPLICATION_LAUNCH = "application.launch"
    APPLICATION_CONTROL = "application.control"


@dataclass(frozen=True, slots=True)
class PermissionGrants:
    grants: dict[str, frozenset[Permission]]

    def has_all(self, requester: str, required: frozenset[Permission]) -> bool:
        return required.issubset(self.grants.get(requester, frozenset()))
