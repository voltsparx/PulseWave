from __future__ import annotations

from pathlib import Path
from typing import TypeVar

Numeric = TypeVar("Numeric", int, float)


def clamp(value: Numeric, lower: Numeric, upper: Numeric) -> Numeric:
    if lower > upper:
        lower, upper = upper, lower
    return max(lower, min(upper, value))


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

