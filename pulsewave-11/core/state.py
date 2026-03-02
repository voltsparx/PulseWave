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
    album: str = ""
    duration: float = 0.0
    source: str = "local"
    path: Optional[Path] = None
    stream_url: Optional[str] = None
    file_format: str = ""
    bitrate_kbps: int = 0

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
    playback_speed: float = 1.0
    shuffle_enabled: bool = False
    repeat_mode: RepeatMode = RepeatMode.OFF
    visualizer_bars: list[int] = field(default_factory=list)
    signal_rms: float = 0.0
    signal_peak: float = 0.0
    signal_crest: float = 0.0
    visualizer_mode: str = "bars"
    ascii_thumbnail: list[str] = field(default_factory=list)
    current_lyric_line: str = ""
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
    search_history: list[str] = field(default_factory=list)
    recently_played: list[str] = field(default_factory=list)
    command_suggestions: list[str] = field(default_factory=list)
    event_log: list[str] = field(default_factory=list)
    ui_symbols: bool = True
    ui_show_recent: bool = True
    ui_show_hints: bool = True
    show_perf_panel: bool = False
    perf_cpu_percent: float = 0.0
    perf_memory_mb: float = 0.0
    perf_frame_ms: float = 0.0
    lan_stream_status: str = ""
