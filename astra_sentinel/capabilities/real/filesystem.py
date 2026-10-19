"""Filesystem capabilities confined to configured canonical roots."""
import os
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable

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

    def resource_paths(self, parameters: dict[str, Any]) -> tuple[Path, ...]:
        return tuple(self._resolve(value, must_exist=False) for value in self._resource_values(parameters))

    @staticmethod
    def _resource_values(parameters: dict[str, Any]) -> tuple[str, ...]:
        return tuple(value for key, value in parameters.items() if key in {"path", "source", "destination", "search_root"} and isinstance(value, str))

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
            if not path.is_file():
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
        os.startfile(path)  # type: ignore[attr-defined]


class CreateDir(_SandboxedFilesystem):
    metadata = CapabilityMetadata("filesystem.create_dir", "Create a sandboxed directory.", "1.0", {"path": str}, frozenset({Permission.FILESYSTEM_WRITE}), RiskLevel.MODIFY, rollback_supported=True)

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        self._resolve(parameters["path"], must_exist=False)
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"], must_exist=False)
        path.mkdir(parents=True, exist_ok=False)
        return {"created_path": str(path)}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(data["created_path"]).is_dir()

    def rollback(self, parameters: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(data["created_path"])
        if any(path.iterdir()):
            raise RequestValidationError("created directory is not empty")
        path.rmdir()
        return {"removed_path": str(path)}


class _WriteFilesystem(_SandboxedFilesystem):
    def _validate_destination(self, destination: str, *, allow_overwrite: bool = False) -> Path:
        path = self._resolve(destination, must_exist=False)
        if path.exists() and not allow_overwrite:
            raise RequestValidationError("destination already exists")
        return path


class MoveFile(_WriteFilesystem):
    metadata = CapabilityMetadata(
        "filesystem.move_file",
        "Move a file within the configured sandbox.",
        "1.0",
        {"source": str, "destination": str},
        frozenset({Permission.FILESYSTEM_MOVE}),
        RiskLevel.MODIFY,
        optional_parameters={"allow_overwrite": bool},
        rollback_supported=True,
    )

    def __init__(self, roots: tuple[Path, ...], allow_overwrite: bool = False) -> None:
        super().__init__(roots)
        self._allow_overwrite = allow_overwrite

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        source = self._resolve(parameters["source"])
        if not source.is_file():
            raise RequestValidationError("source is not a file")
        destination = self._validate_destination(parameters["destination"], allow_overwrite=self._allow_overwrite or parameters.get("allow_overwrite", False))
        if destination == source:
            raise RequestValidationError("source and destination are the same path")
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        source = self._resolve(parameters["source"])
        destination = self._validate_destination(parameters["destination"], allow_overwrite=self._allow_overwrite or parameters.get("allow_overwrite", False))
        source.rename(destination)
        return {"source": str(source), "destination": str(destination)}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        source_exists = Path(data["source"]).exists()
        destination_exists = self._resolve(data["destination"]).exists()
        return destination_exists and not source_exists

    def rollback(self, parameters: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        source = self._resolve(data["source"], must_exist=False)
        destination = self._resolve(data["destination"])
        if source.exists():
            raise RequestValidationError("original move source is no longer safe to restore")
        destination.rename(source)
        return {"restored_path": str(source)}


class CopyFile(_WriteFilesystem):
    metadata = CapabilityMetadata(
        "filesystem.copy_file",
        "Copy a file within the configured sandbox.",
        "1.0",
        {"source": str, "destination": str},
        frozenset({Permission.FILESYSTEM_WRITE}),
        RiskLevel.MODIFY,
        optional_parameters={"allow_overwrite": bool},
    )

    def __init__(self, roots: tuple[Path, ...], allow_overwrite: bool = False) -> None:
        super().__init__(roots)
        self._allow_overwrite = allow_overwrite

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        source = self._resolve(parameters["source"])
        if not source.is_file():
            raise RequestValidationError("source is not a file")
        self._validate_destination(parameters["destination"], allow_overwrite=self._allow_overwrite or parameters.get("allow_overwrite", False))
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        source = self._resolve(parameters["source"])
        destination = self._validate_destination(parameters["destination"], allow_overwrite=self._allow_overwrite or parameters.get("allow_overwrite", False))
        destination.write_bytes(source.read_bytes())
        return {"source": str(source), "destination": str(destination)}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(data["destination"]).exists() and self._resolve(data["source"]).exists()


class RenameFile(_WriteFilesystem):
    metadata = CapabilityMetadata(
        "filesystem.rename_file",
        "Rename a file inside the same allowed resource boundary.",
        "1.0",
        {"path": str, "new_name": str},
        frozenset({Permission.FILESYSTEM_WRITE}),
        RiskLevel.MODIFY,
    )

    def __init__(self, roots: tuple[Path, ...], allow_overwrite: bool = False) -> None:
        super().__init__(roots)
        self._allow_overwrite = allow_overwrite

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        original = self._resolve(parameters["path"])
        if not original.is_file():
            raise RequestValidationError("path is not a file")
        new_name = parameters["new_name"]
        if Path(new_name).name != new_name or new_name in {".", ".."}:
            raise RequestValidationError("new_name must be a filename, not a path")
        destination = original.with_name(new_name)
        if not any(self._is_within(destination.resolve(strict=False), root) for root in self._roots):
            raise RequestValidationError("new file path escapes configured roots")
        if destination.exists() and not self._allow_overwrite:
            raise RequestValidationError("destination already exists")
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        original = self._resolve(parameters["path"])
        destination = original.with_name(parameters["new_name"])
        original.rename(destination)
        return {"original": str(original), "renamed_path": str(destination)}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        original_exists = Path(data["original"]).exists()
        renamed_exists = self._resolve(data["renamed_path"]).exists()
        return renamed_exists and not original_exists


class CreateFile(_WriteFilesystem):
    metadata = CapabilityMetadata(
        "filesystem.create_file",
        "Create an empty file within the configured filesystem roots.",
        "1.0",
        {"path": str},
        frozenset({Permission.FILESYSTEM_WRITE}),
        RiskLevel.MODIFY,
        optional_parameters={"allow_overwrite": bool},
        rollback_supported=True,
    )

    def __init__(self, roots: tuple[Path, ...], allow_overwrite: bool = False) -> None:
        super().__init__(roots)
        self._allow_overwrite = allow_overwrite

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"], must_exist=False)
        if path.exists() and not (self._allow_overwrite or parameters.get("allow_overwrite", False)):
            raise RequestValidationError("destination already exists")
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(parameters["path"], must_exist=False)
        path.touch(exist_ok=self._allow_overwrite or parameters.get("allow_overwrite", False))
        return {"created_path": str(path)}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return self._resolve(data["created_path"]).is_file()

    def rollback(self, parameters: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        path = self._resolve(data["created_path"])
        path.unlink()
        return {"removed_path": str(path)}
