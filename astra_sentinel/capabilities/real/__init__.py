"""Controlled operating-system capabilities registered by trusted configuration."""

from .applications import GetProcessInfo, IsAppRunning, ListRunningApps, OpenApp
from .filesystem import CopyFile, CreateDir, CreateFile, FindFile, GetFileInfo, MoveFile, OpenFile, RenameFile
from .system import GetBatteryStatus, GetCpuUsage, GetDiskUsage, GetMemoryUsage, GetSystemInfo

__all__ = [
    "OpenApp",
    "IsAppRunning",
    "GetProcessInfo",
    "ListRunningApps",
    "FindFile",
    "GetFileInfo",
    "OpenFile",
    "CreateDir",
    "CreateFile",
    "MoveFile",
    "CopyFile",
    "RenameFile",
    "GetCpuUsage",
    "GetMemoryUsage",
    "GetDiskUsage",
    "GetBatteryStatus",
    "GetSystemInfo",
]
