from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class RepeatMode(str, Enum):
    OFF = "off"
    ONE = "one"
    ALL = "all"


@dataclass
class Track:
    id: str
    title: str
    artist: str = "Unknown Artist"
    duration: float = 0.0
    source: str = "local"
    path: Optional[Path] = None
    stream_url: Optional[str] = None

    def label(self) -> str:
        return f"{self.title} - {self.artist}"


@dataclass
class AppState:
    current_track: Optional[Track] = None
    is_playing: bool = False
    is_paused: bool = False
    position: float = 0.0
    duration: float = 0.0
    volume: int = 60
    shuffle_enabled: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    visualizer_bars: list[int] = field(default_factory=list)
    status_message: str = "Ready"
    last_error: str = ""
    muted: bool = False
    last_volume_before_mute: int = 60
    show_settings: bool = False
    settings_preview: list[str] = field(default_factory=list)
    settings_cursor: int = 0
    active_playlist: str = ""
    active_category: str = "General"
    categories: list[str] = field(default_factory=list)
    playlists: list[str] = field(default_factory=list)
