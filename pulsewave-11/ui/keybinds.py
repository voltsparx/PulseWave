from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_KEYBINDS = {
    " ": "play_pause",
    "/": "quick_search",
    "q": "quit",
    "Q": "quit",
    "n": "next_track",
    "N": "next_track",
    "p": "prev_track",
    "P": "prev_track",
    "s": "stop_playback",
    "r": "rescan_library",
    "h": "help",
    "A": "playlist_add_current",
    "+": "volume_up",
    "-": "volume_down",
    "\x1b[A": "volume_up",
    "\x1b[B": "volume_down",
    "\x1b[C": "seek_forward",
    "\x1b[D": "seek_backward",
    "]": "seek_forward",
    "[": "seek_backward",
    "m": "toggle_mute",
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
}


@dataclass
class KeyBindings:
    mapping: dict[str, list[str]]

    @staticmethod
    def _normalize_actions(raw: Any) -> list[str]:
        if isinstance(raw, list):
            out = [str(item).strip() for item in raw if str(item).strip()]
            return out
        text = str(raw or "").strip()
        if not text:
            return []
        # Inspired by ncmpcpp action chains: allow "a|b|c" and "a,b,c".
        chunks = [item.strip() for item in text.replace("|", ",").split(",")]
        return [item for item in chunks if item]

    @classmethod
    def from_config(cls, config_mapping: dict[str, Any] | None) -> "KeyBindings":
        merged: dict[str, list[str]] = {key: cls._normalize_actions(value) for key, value in DEFAULT_KEYBINDS.items()}
        if config_mapping:
            for key, value in config_mapping.items():
                normalized = cls._normalize_actions(value)
                if normalized:
                    merged[str(key)] = normalized
        return cls(mapping=merged)

    def action_for(self, key: str) -> str | None:
        actions = self.mapping.get(key) or []
        return actions[0] if actions else None

    def actions_for(self, key: str) -> list[str]:
        return list(self.mapping.get(key) or [])
