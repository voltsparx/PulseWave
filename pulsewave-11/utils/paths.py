from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable

from .helpers import ensure_dir

CONFIG_DIR_NAME = ".pulsewave-11-config"
CONFIG_HOME_ENV = "PULSEWAVE_11_CONFIG_HOME"
CONFIG_LOCATION_FILE = Path.home() / ".pulsewave-11-config-location"


def default_config_home() -> Path:
    return Path.home() / CONFIG_DIR_NAME


def _read_persisted_config_home() -> Path | None:
    try:
        raw = CONFIG_LOCATION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _persist_config_home(path: Path) -> None:
    CONFIG_LOCATION_FILE.write_text(str(path.expanduser().resolve()) + "\n", encoding="utf-8")


def resolved_config_home() -> Path:
    env_override = os.environ.get(CONFIG_HOME_ENV, "").strip()
    if env_override:
        return Path(env_override).expanduser().resolve()

    persisted = _read_persisted_config_home()
    if persisted is not None:
        return persisted
    return default_config_home()


def initialize_config_home(
    *,
    interactive: bool | None = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> Path:
    env_override = os.environ.get(CONFIG_HOME_ENV, "").strip()
    if env_override:
        return ensure_dir(Path(env_override).expanduser().resolve())

    persisted = _read_persisted_config_home()
    if persisted is not None:
        return ensure_dir(persisted)

    default_home = default_config_home()
    if interactive is None:
        interactive = bool(sys.stdin.isatty() and sys.stdout.isatty())

    target = default_home
    if interactive:
        output_fn("First-time setup: choose config directory for PulseWave-11.")
        output_fn(f"Press Enter to use default: {default_home}")
        while True:
            user_raw = input_fn("Config directory: ").strip()
            candidate = default_home if user_raw == "" else Path(user_raw).expanduser().resolve()
            try:
                target = ensure_dir(candidate)
            except OSError as exc:
                output_fn(f"Invalid path ({exc}). Try again.")
                continue
            break
    else:
        target = ensure_dir(default_home)

    _persist_config_home(target)
    return target


def config_home() -> Path:
    return ensure_dir(resolved_config_home())


def config_file() -> Path:
    return config_home() / "config.json"


def library_file() -> Path:
    return config_home() / "library.json"


def logs_dir() -> Path:
    return ensure_dir(config_home() / "logs")


def cache_dir() -> Path:
    return ensure_dir(config_home() / "cache")
