"""Read-only system and process information capabilities."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from typing import Any

from astra_sentinel.capabilities.base import CapabilityMetadata
from astra_sentinel.core.errors import RequestValidationError
from astra_sentinel.security.permissions import Permission
from astra_sentinel.security.risk import RiskLevel


def _list_process_names() -> list[str]:
    try:
        import psutil  # type: ignore
    except ImportError:
        if os.name == "nt":
            completed = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], shell=False, capture_output=True, text=True, check=False)
            names: list[str] = []
            for line in completed.stdout.splitlines():
                cleaned = line.strip().strip('"')
                if not cleaned:
                    continue
                if "," in cleaned:
                    candidate = cleaned.split(",", 1)[0].strip('"')
                    if candidate:
                        names.append(candidate)
            return names
        completed = subprocess.run(["ps", "-eo", "comm="], shell=False, capture_output=True, text=True, check=False)
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    try:
        return [proc.name() for proc in psutil.process_iter(attrs=["name"]) if proc.info.get("name")]
    except Exception:
        return []


class GetCpuUsage:
    metadata = CapabilityMetadata(
        "system.get_cpu_usage",
        "Return a safe CPU usage snapshot for the current machine.",
        "1.0",
        {},
        frozenset({Permission.SYSTEM_READ}),
        RiskLevel.READ_ONLY,
    )

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            import psutil  # type: ignore
        except ImportError:
            return {"supported": False, "percent": None, "logic_cores": os.cpu_count(), "note": "psutil is unavailable"}
        try:
            return {
                "supported": True,
                "percent": round(float(psutil.cpu_percent(interval=None)), 2),
                "logical_cores": psutil.cpu_count(logical=True),
                "unit": "%",
            }
        except Exception:
            return {"supported": False, "percent": None, "logical_cores": os.cpu_count(), "note": "CPU usage is unavailable"}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return isinstance(data.get("supported"), bool) and isinstance(data.get("logical_cores"), int | type(None))


class GetMemoryUsage:
    metadata = CapabilityMetadata(
        "system.get_memory_usage",
        "Return a safe memory usage snapshot for the current machine.",
        "1.0",
        {},
        frozenset({Permission.SYSTEM_READ}),
        RiskLevel.READ_ONLY,
    )

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            import psutil  # type: ignore
        except ImportError:
            return {"supported": False, "total_bytes": None, "used_bytes": None, "available_bytes": None, "note": "psutil is unavailable"}
        try:
            mem = psutil.virtual_memory()
            return {
                "supported": True,
                "total_bytes": int(mem.total),
                "used_bytes": int(mem.used),
                "available_bytes": int(mem.available),
                "unit": "bytes",
            }
        except Exception:
            return {"supported": False, "total_bytes": None, "used_bytes": None, "available_bytes": None, "note": "Memory usage is unavailable"}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return isinstance(data.get("supported"), bool)


class GetDiskUsage:
    metadata = CapabilityMetadata(
        "system.get_disk_usage",
        "Return safe disk usage for the current filesystem root.",
        "1.0",
        {},
        frozenset({Permission.SYSTEM_READ}),
        RiskLevel.READ_ONLY,
    )

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        path = os.path.abspath(os.sep)
        try:
            usage = shutil.disk_usage(path)
            return {
                "supported": True,
                "root": path,
                "total_bytes": int(usage.total),
                "used_bytes": int(usage.used),
                "free_bytes": int(usage.free),
                "unit": "bytes",
            }
        except Exception:
            return {"supported": False, "root": path, "total_bytes": None, "used_bytes": None, "free_bytes": None, "note": "Disk usage is unavailable"}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return isinstance(data.get("supported"), bool)


class GetBatteryStatus:
    metadata = CapabilityMetadata(
        "system.get_battery_status",
        "Return safe battery status when available.",
        "1.0",
        {},
        frozenset({Permission.SYSTEM_READ}),
        RiskLevel.READ_ONLY,
    )

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        try:
            import psutil  # type: ignore
        except ImportError:
            return {"supported": False, "status": "unsupported", "note": "psutil is unavailable"}
        try:
            battery = psutil.sensors_battery()
            if battery is None:
                return {"supported": False, "status": "unsupported", "note": "No battery detected"}
            return {
                "supported": True,
                "status": "charging" if battery.power_plugged else "discharging",
                "percent": round(float(battery.percent), 2),
                "seconds_left": int(battery.secsleft) if battery.secsleft != -1 else None,
            }
        except Exception:
            return {"supported": False, "status": "unsupported", "note": "Battery status is unavailable"}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return isinstance(data.get("supported"), bool)


class GetSystemInfo:
    metadata = CapabilityMetadata(
        "system.get_system_info",
        "Return a minimal, non-sensitive system summary.",
        "1.0",
        {},
        frozenset({Permission.SYSTEM_READ}),
        RiskLevel.READ_ONLY,
    )

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        info = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "logical_cores": os.cpu_count(),
        }
        try:
            import psutil  # type: ignore
        except ImportError:
            return {"supported": True, **info, "memory_total_bytes": None, "note": "psutil unavailable; memory not included"}
        try:
            mem = psutil.virtual_memory()
            info["memory_total_bytes"] = int(mem.total)
            return {"supported": True, **info}
        except Exception:
            return {"supported": True, **info, "memory_total_bytes": None, "note": "memory details unavailable"}

    def verify(self, parameters: dict[str, Any], data: dict[str, Any]) -> bool:
        return isinstance(data.get("system"), str) and isinstance(data.get("release"), str)
