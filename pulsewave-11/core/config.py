from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Optional

from ..utils.helpers import ensure_dir
from ..utils.paths import config_file, config_home

DEFAULT_CONFIG: dict[str, Any] = {
    "music_dirs": [],
    "theme": "default",
    "color_mode": "off",
    "audio_backend": "auto",
    "audio_buffer_size": 4096,
    "playback_speed": 1.0,
    "youtube_enabled": True,
    "volume": 60,
    "repeat_mode": "off",
    "shuffle_enabled": False,
    "search": {
        "history": [],
        "history_limit": 50,
    },
    "command_aliases": {},
    "session": {
        "resume_last_track": True,
        "remember_position": True,
        "auto_resume": False,
        "autosave_interval_seconds": 5,
        "last_track": {},
        "last_position": 0.0,
    },
    "settings": {
        "volume_step": 5,
        "seek_step": 5,
        "speed_step": 0.1,
        "settings_step_bars": 4,
        "settings_step_smoothing": 0.05,
    },
    "ui": {
        "use_symbols": True,
        "show_recently_played": True,
        "show_command_hints": True,
        "event_log_size": 40,
    },
    "performance": {
        "show_panel": False,
    },
    "lyrics": {
        "enabled": True,
    },
    "plugins": {
        "enabled": [],
    },
    "lan_stream": {
        "host": "0.0.0.0",
        "port": 8765,
        "autostart": False,
    },
    "scripting": {
        "max_lines": 2000,
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
        "s": "stop_playback",
        "/": "quick_search",
        "A": "playlist_add_current",
        "Q": "quit",
        "N": "next_track",
        "P": "prev_track",
        "\u001b[C": "seek_forward",
        "\u001b[D": "seek_backward",
        "\u001b[A": "volume_up",
        "\u001b[B": "volume_down",
        ",": "toggle_settings",
        "j": "settings_next",
        "k": "settings_prev",
        "l": "settings_inc",
        "u": "settings_dec",
        ".": "speed_up",
        ";": "speed_down",
        "x": "cycle_repeat",
        "z": "toggle_shuffle",
        "t": "cycle_theme",
        "f": "cycle_visualizer_mode",
        "g": "cycle_color_mode",
        "?": "help",
    },
    "visualizer": {
        "bars": 24,
        "smoothing": 0.65,
        "mode": "bars",
        "sensitivity": 1.0,
        "fps_limit": 24,
        "auto_hide_paused": True,
        "custom_levels": "",
        "presets": {},
    },
    "library": {
        "default_category": "General",
        "default_playlist": "Liked Songs",
        "smart_playlists_enabled": True,
        "recently_played_limit": 50,
    },
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


class ConfigManager:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.home = config_home()
        self.path = path or config_file()
        ensure_dir(self.path.parent)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            defaults = copy.deepcopy(DEFAULT_CONFIG)
            self.save(defaults)
            return defaults

        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        return _merge_dict(DEFAULT_CONFIG, loaded)

    def save(self, payload: dict[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        self.path.write_text(serialized + "\n", encoding="utf-8")
