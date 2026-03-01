from __future__ import annotations

from pathlib import Path

from pulsewave.utils.helpers import ensure_dir


def config_home() -> Path:
    # Cross-platform, explicit project home requested by user.
    return ensure_dir(Path.home() / ".pulsewave-config")


def config_file() -> Path:
    return config_home() / "config.json"


def library_file() -> Path:
    return config_home() / "library.json"


def logs_dir() -> Path:
    return ensure_dir(config_home() / "logs")


def cache_dir() -> Path:
    return ensure_dir(config_home() / "cache")

