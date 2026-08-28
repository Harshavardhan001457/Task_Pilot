"""Deterministic capability risk classifications."""
from enum import IntEnum


class RiskLevel(IntEnum):
    READ_ONLY = 0
    LOW = 1
    MODIFY = 2
    DESTRUCTIVE = 3
    RESTRICTED = 4
