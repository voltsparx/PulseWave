from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pulsewave.utils.helpers import ensure_dir
from pulsewave.utils.paths import config_file, config_home

DEFAULT_CONFIG: dict[str, Any] = {
    "music_dirs": [],
    "theme": "default",
    "color_mode": "off",
    "audio_backend": "auto",
    "audio_buffer_size": 4096,
    "youtube_enabled": True,
    "volume": 60,
    "repeat_mode": "off",
    "shuffle_enabled": False,
    "settings": {
        "volume_step": 5,
        "seek_step": 5,
        "settings_step_bars": 4,
        "settings_step_smoothing": 0.05,
    },
    "keybindings": {
        " ": "play_pause",
        "q": "quit",
        "n": "next_track",
        "p": "prev_track",
        "r": "rescan_library",
        "h": "help",
        "+": "volume_up",
        "-": "volume_down",
        "]": "seek_forward",
        "[": "seek_backward",
        "m": "toggle_mute",
        ",": "toggle_settings",
        "j": "settings_next",
        "k": "settings_prev",
        "l": "settings_inc",
        "u": "settings_dec",
    },
    "visualizer": {
        "bars": 24,
        "smoothing": 0.65,
    },
    "library": {
        "default_category": "General",
        "default_playlist": "Liked Songs",
    },
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class ConfigManager:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.home = config_home()
        self.path = path or config_file()
        ensure_dir(self.path.parent)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            self.save(DEFAULT_CONFIG)
            return dict(DEFAULT_CONFIG)

        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        return _merge_dict(DEFAULT_CONFIG, loaded)

    def save(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self.path.write_text(serialized + "\n", encoding="utf-8")
