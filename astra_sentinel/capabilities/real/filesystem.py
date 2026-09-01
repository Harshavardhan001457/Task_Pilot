"""Filesystem capabilities confined to configured canonical roots."""
import os
from pathlib import Path
from typing import Any, Callable
from fnmatch import fnmatch

from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.core.errors import RequestValidationError
from astra_sentinel.security.permissions import Permission
from astra_sentinel.security.risk import RiskLevel

MAX_MATCHES = 100
OPEN_FILE_EXTENSIONS = frozenset({
    ".avi", ".bmp", ".csv", ".doc", ".docx", ".gif", ".jpeg", ".jpg", ".json",
    ".md", ".mp3", ".mp4", ".pdf", ".png", ".ppt", ".pptx", ".txt", ".wav",
    ".webp", ".xls", ".xlsx", ".xml",
})


class _SandboxedFilesystem:
    def __init__(self, roots: tuple[Path, ...]) -> None:
        self._roots = tuple(root.resolve(strict=True) for root in roots if root.is_dir())

    def _resolve(self, raw_path: str, *, must_exist: bool = True) -> Path:
        if not self._roots:
            raise RequestValidationError("filesystem sandbox is not configured")
        candidate = Path(raw_path)
        candidate = candidate if candidate.is_absolute() else self._roots[0] / candidate
        try:
            resolved = candidate.resolve(strict=must_exist)
        except (OSError, RuntimeError) as error:
            raise RequestValidationError("path is invalid or inaccessible") from error
        if not any(self._is_within(resolved, root) for root in self._roots):
            raise RequestValidationError("path is outside configured filesystem roots")
        return resolved

    @staticmethod
    def _is_within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False


class FindFile(_SandboxedFilesystem):
    metadata = CapabilityMetadata(
        "filesystem.find_file", "Find a filename only in configured roots.", "1.0",
        {"name": str}, frozenset({Permission.FILESYSTEM_READ}), RiskLevel.READ_ONLY,
        optional_parameters={"search_root": str},
    )
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        name = parameters["name"]
        if Path(name).name != name or name in {".", ".."}:
            raise RequestValidationError("name must be a filename, not a path")
        if "search_root" in parameters:
            if not self._resolve(parameters["search_root"]).is_dir():
                raise RequestValidationError("search root is not a directory")
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        if not self._roots:
            raise RequestValidationError("filesystem sandbox is not configured")

        if "search_root" in parameters:
            root = self._resolve(parameters["search_root"])
        else:
            root = self._resolve(str(self._roots[0]))

        if not root.is_dir():
            raise RequestValidationError("search root is not a directory")
        matches: list[str] = []
        pattern = parameters["name"]
        for path in root.rglob("*"):
            if not path.is_file:
                continue
            if not fnmatch(path.name.lower(), pattern.lower()):
                continue
            try:
                safe_path = self._resolve(str(path))
            except RequestValidationError:
                continue
            matches.append(str(safe_path))
            if len(matches) >= MAX_MATCHES:
                break
        return {"matches": matches}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        try:
            return all(any(self._is_within(self._resolve(path), root) for root in self._roots) for path in data["matches"])
        except RequestValidationError:
            return False


class GetFileInfo(_SandboxedFilesystem):
    metadata = CapabilityMetadata("filesystem.get_file_info", "Read safe file metadata.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_READ}), RiskLevel.READ_ONLY)
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._resolve(parameters["path"])
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"])
        stat = path.stat()
        return {"name": path.name, "size": stat.st_size, "extension": path.suffix, "modified_time": stat.st_mtime, "type": "directory" if path.is_dir() else "file"}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(parameters["path"]).exists() and data["type"] in {"file", "directory"}


class OpenFile(_SandboxedFilesystem):
    metadata = CapabilityMetadata("filesystem.open_file", "Open a sandboxed file with its associated application.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_READ}), RiskLevel.LOW)
    def __init__(self, roots: tuple[Path, ...], opener: Callable[[str], None] | None = None) -> None:
        super().__init__(roots)
        self._opener = opener or self._native_open
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"])
        if not path.is_file():
            raise RequestValidationError("path is not a file")
        if path.suffix.casefold() not in OPEN_FILE_EXTENSIONS:
            raise RequestValidationError("file extension is not approved for opening")
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"])
        self._opener(str(path))
        return {"opened_path": str(path)}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(data["opened_path"]).is_file()
    @staticmethod
    def _native_open(path: str) -> None:
        if os.name != "nt" or not hasattr(os, "startfile"):
            raise OSError("native associated-file opening is unavailable on this platform")
        os.startfile(path)  # type: ignore[attr-defined]  # Windows ShellExecute, no command construction.


class CreateDir(_SandboxedFilesystem):
    metadata = CapabilityMetadata("filesystem.create_dir", "Create a sandboxed directory.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_WRITE}), RiskLevel.MODIFY)
    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._resolve(parameters["path"], must_exist=False)
        return dict(parameters)
    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"], must_exist=False)
        path.mkdir(parents=True, exist_ok=False)
        return {"created_path": str(path)}
    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(data["created_path"]).is_dir()
