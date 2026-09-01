"""Default allowlists used by the ASTRA Sentinel runtime.

Add, remove, or edit entries here to adjust the runtime's policy without changing
execution logic in the config factory.
"""

from __future__ import annotations

from pathlib import Path

from astra_sentinel.security.permissions import Permission

DEFAULT_PERMISSION_GRANTS = {
    "cli": frozenset({
        Permission.SYSTEM_READ,
        Permission.APPLICATION_LAUNCH,
        Permission.FILESYSTEM_READ,
    }),
    "internal": frozenset({
        Permission.SYSTEM_READ,
        Permission.APPLICATION_LAUNCH,
        Permission.FILESYSTEM_READ,
    }),
}

DEFAULT_ENABLED_CAPABILITIES = frozenset({
    "application.open_app",
    "application.is_app_running",
    "filesystem.find_file",
    "filesystem.get_file_info",
    "filesystem.open_file",
    "filesystem.create_dir",
})

DEFAULT_ALLOWED_APPLICATIONS: dict[str, str] = {
    "notepad": r"C:\Windows\System32\notepad.exe",
    "vscode": r"C:\Users\harsh\AppData\Local\Programs\Microsoft VS Code\Code.exe",
}

DEFAULT_ALLOWED_APPLICATION_IDS = frozenset(DEFAULT_ALLOWED_APPLICATIONS)

DEFAULT_ALLOWED_FILESYSTEM_ROOTS: tuple[str, ...] = (
    r"C:\Users\harsh\OneDrive\Documents\course plan\Sem 5",
)
