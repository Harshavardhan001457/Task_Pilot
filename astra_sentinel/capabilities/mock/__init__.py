"""Safe simulations: these capabilities deliberately never access the OS."""

from .capabilities import MockCreateDir, MockEcho, MockOpenApp, MockOpenFile

__all__ = ["MockEcho", "MockOpenApp", "MockOpenFile", "MockCreateDir"]
