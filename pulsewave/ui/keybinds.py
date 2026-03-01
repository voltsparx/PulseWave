from __future__ import annotations

from dataclasses import dataclass

DEFAULT_KEYBINDS = {
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
}


@dataclass
class KeyBindings:
    mapping: dict[str, str]

    @classmethod
    def from_config(cls, config_mapping: dict[str, str] | None) -> "KeyBindings":
        merged = dict(DEFAULT_KEYBINDS)
        if config_mapping:
            merged.update(config_mapping)
        return cls(mapping=merged)

    def action_for(self, key: str) -> str | None:
        return self.mapping.get(key)
