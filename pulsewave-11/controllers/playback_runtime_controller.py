from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from ..core.library import LibraryStore
from ..core.player import PlaybackController
from ..core.queue import QueueManager
from ..core.search import SearchResult
from ..core.state import AppState, RepeatMode, Track
from ..integrations.local_scan import LocalScanner
from ..integrations.ytmusic import YTMusicClient
from ..ui.visualizer import VisualizerEngine
from ..utils.helpers import clamp, safe_float, safe_int


class PlaybackRuntimeController:
    def __init__(
        self,
        *,
        state: AppState,
        queue: QueueManager,
        player: PlaybackController,
        library: LibraryStore,
        local_scanner: LocalScanner,
        ytmusic: YTMusicClient,
        visualizer: VisualizerEngine,
        config: dict[str, Any],
        get_cfg: Callable[[str, Any], Any],
        safe_save_config: Callable[[], None],
        set_status: Callable[[str], None],
        set_error: Callable[[str], None],
        refresh_recently_played: Callable[[], None],
    ) -> None:
        self._state = state
        self._queue = queue
        self._player = player
        self._library = library
        self._local_scanner = local_scanner
        self._ytmusic = ytmusic
        self._visualizer = visualizer
        self._config = config
        self._get_cfg = get_cfg
        self._safe_save_config = safe_save_config
        self._set_status = set_status
        self._set_error = set_error
        self._refresh_recently_played = refresh_recently_played

        self._was_playing = False
        self._sleep_deadline = 0.0

    def refresh_player_state(self) -> None:
        if self._state.current_track is None:
            self._state.position = 0.0
            self._state.duration = 0.0
            self._state.is_playing = False
            self._state.is_paused = False
            return
        try:
            pos = self._player.get_position()
            dur = self._player.get_duration()
            playing = self._player.is_playing()
        except Exception as exc:
            self._set_error(f"Playback update failed: {exc}")
            return
        self._state.position = max(0.0, pos)
        if dur > 0:
            self._state.duration = dur
        elif self._state.current_track.duration > 0 and self._state.duration <= 0:
            self._state.duration = self._state.current_track.duration
        self._state.is_playing = bool(playing) if not self._state.is_paused else False

    def refresh_visualizer(self) -> None:
        if self._state.current_track is None:
            self._state.visualizer_bars = [0] * self._visualizer.bars
            self._state.signal_rms = 0.0
            self._state.signal_peak = 0.0
            self._state.signal_crest = 0.0
            return
        try:
            samples = self._player.get_waveform_chunk(size=max(64, self._visualizer.bars * 4))
        except Exception:
            samples = []
        self._state.visualizer_bars = self._visualizer.compute_bars(
            samples,
            playing=self._state.is_playing and not self._state.is_paused,
        )
        rms, peak, crest = self._visualizer.compute_signal_stats(samples)
        self._state.signal_rms = rms
        self._state.signal_peak = peak
        self._state.signal_crest = crest

    def handle_track_end(self) -> None:
        if self._was_playing and not self._state.is_playing and not self._state.is_paused and self._state.current_track:
            if self._state.duration > 0 and self._state.position >= max(0.0, self._state.duration - 0.25):
                self.play_next(manual=False)
        self._was_playing = self._state.is_playing

    def handle_sleep_timer(self) -> None:
        if self._sleep_deadline <= 0:
            return
        if time.time() < self._sleep_deadline:
            return
        self._sleep_deadline = 0.0
        self.stop_playback()
        self._set_status("Sleep timer reached. Playback stopped.")

    def toggle_pause(self) -> None:
        if self._state.current_track is None:
            current = self._queue.current()
            if current is None:
                self._set_error("No track loaded.")
                return
            self.play_track(current, queue_index=self._queue.index())
            return
        try:
            paused = self._player.toggle_pause()
        except Exception as exc:
            self._set_error(f"Pause failed: {exc}")
            return
        self._state.is_paused = bool(paused)
        self._state.is_playing = not self._state.is_paused
        self._set_status("Paused." if self._state.is_paused else "Resumed.")

    def stop_playback(self) -> None:
        try:
            self._player.stop()
        except Exception:
            pass
        self._state.is_playing = False
        self._state.is_paused = False
        self._state.position = 0.0
        self._set_status("Stopped.")

    def play_next(self, *, manual: bool) -> None:
        track = self._queue.next_track(self._state.repeat_mode, self._state.shuffle_enabled)
        if track is None:
            self.stop_playback()
            if manual:
                self._set_status("Reached end of queue.")
            return
        self.play_track(track, queue_index=self._queue.index())

    def play_previous(self) -> None:
        track = self._queue.previous_track(self._state.repeat_mode, self._state.shuffle_enabled)
        if track is None:
            self._set_status("No previous track.")
            return
        self.play_track(track, queue_index=self._queue.index())

    def play_track(
        self,
        track: Track,
        *,
        queue_index: int | None = None,
        start_position: float = 0.0,
        announce: bool = True,
    ) -> bool:
        source = self.resolve_play_source(track)
        if source is None:
            self._set_error(f"Cannot resolve source: {track.label()}")
            return False
        try:
            self._player.play_source(source)
            if start_position > 0:
                self._player.seek(start_position)
            self._player.set_volume(self._state.volume)
            self._player.set_speed(self._state.playback_speed)
        except Exception as exc:
            self._set_error(f"Play failed: {exc}")
            return False
        if queue_index is None:
            queue_index = self.ensure_track_in_queue(track)
        self._queue.set_index(queue_index)
        self._state.current_track = track
        self._state.is_playing = True
        self._state.is_paused = False
        self._state.position = max(0.0, start_position)
        self._state.duration = track.duration if track.duration > 0 else max(0.0, self._player.get_duration())
        self._library.record_play(track, recent_limit=max(1, safe_int(self._get_cfg("library.recently_played_limit", 50), 50)))
        self._refresh_recently_played()
        if announce:
            self._set_status(f"Playing: {track.label()}")
        return True

    def resolve_play_source(self, track: Track) -> str | None:
        if track.source == "local":
            return str(track.path) if track.path else None
        if track.source == "youtube":
            if track.stream_url:
                return track.stream_url
            stream = self._ytmusic.resolve_stream_url(track.id)
            if stream:
                track.stream_url = stream
                return stream
            return None
        if track.stream_url:
            return track.stream_url
        if track.path:
            return str(track.path)
        return None

    def ensure_track_in_queue(self, track: Track) -> int:
        key = self.track_identity(track)
        snap = self._queue.snapshot()
        for idx, item in enumerate(snap.items):
            if self.track_identity(item) == key:
                return idx
        return self._queue.add(track)

    def track_identity(self, track: Track) -> tuple[str, str, str]:
        return (track.id, track.source, str(track.path) if track.path else "")

    def seek_relative(self, delta_seconds: float) -> None:
        try:
            self._state.position = max(0.0, self._player.seek(delta_seconds))
        except Exception as exc:
            self._set_error(f"Seek failed: {exc}")
            return
        self._set_status(f"Seeked to {int(self._state.position)}s.")

    def adjust_volume(self, delta: int) -> None:
        self.set_volume(self._state.volume + delta)

    def set_volume(self, value: int) -> None:
        volume = int(clamp(value, 0, 100))
        try:
            self._state.volume = int(self._player.set_volume(volume))
        except Exception as exc:
            self._set_error(f"Volume update failed: {exc}")
            return
        self._state.muted = self._state.volume == 0
        self._config["volume"] = self._state.volume
        self._safe_save_config()
        self._set_status(f"Volume: {self._state.volume}%")

    def toggle_mute(self) -> None:
        if self._state.muted:
            self.set_volume(self._state.last_volume_before_mute or 60)
            self._state.muted = False
            self._set_status("Unmuted.")
            return
        self._state.last_volume_before_mute = self._state.volume
        self.set_volume(0)
        self._state.muted = True
        self._set_status("Muted.")

    def set_speed(self, value: float) -> None:
        speed = float(clamp(value, 0.5, 2.0))
        try:
            self._state.playback_speed = float(self._player.set_speed(speed))
        except Exception as exc:
            self._set_error(f"Speed update failed: {exc}")
            return
        self._config["playback_speed"] = self._state.playback_speed
        self._safe_save_config()
        self._set_status(f"Speed: {self._state.playback_speed:.2f}x")

    def nudge_speed(self, direction: int) -> None:
        step = safe_float(self._get_cfg("settings.speed_step", 0.1), 0.1)
        self.set_speed(self._state.playback_speed + (step * direction))

    def cycle_repeat_mode(self) -> None:
        order = [RepeatMode.OFF, RepeatMode.ALL, RepeatMode.ONE]
        current = self._state.repeat_mode
        try:
            idx = order.index(current)
        except ValueError:
            idx = 0
        next_mode = order[(idx + 1) % len(order)]
        self._state.repeat_mode = next_mode
        self._config["repeat_mode"] = next_mode.value
        self._safe_save_config()
        self._set_status(f"Repeat mode: {next_mode.value}")

    def toggle_shuffle_quick(self) -> None:
        self._state.shuffle_enabled = not self._state.shuffle_enabled
        self._config["shuffle_enabled"] = self._state.shuffle_enabled
        self._safe_save_config()
        self._set_status(f"Shuffle: {'on' if self._state.shuffle_enabled else 'off'}")

    def command_play(self, parts: list[str], *, search_results: list[SearchResult]) -> None:
        if len(parts) == 1:
            self.toggle_pause()
            return
        arg = parts[1].lower()
        if arg == "current":
            if self._state.current_track is None:
                self._set_error("No current track.")
                return
            self.play_track(self._state.current_track, queue_index=self._queue.index())
            return
        if arg == "next":
            self.play_next(manual=True)
            return
        if arg == "prev":
            self.play_previous()
            return
        if arg.isdigit():
            idx = int(arg)
            if not (1 <= idx <= len(search_results)):
                self._set_error(f"Search index out of range: {idx}")
                return
            track = search_results[idx - 1].track
            self.play_track(track, queue_index=self.ensure_track_in_queue(track))
            return
        raw_path = " ".join(parts[1:]).strip().strip('"').strip("'")
        path = Path(raw_path).expanduser()
        if path.exists():
            track = self._local_scanner.track_from_path(path)
            if track is None:
                self._set_error("Unsupported audio file.")
                return
            self.play_track(track, queue_index=self.ensure_track_in_queue(track))
            return
        self._set_error("Usage: play <search-index|current|next|prev|path>")

    def command_add(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self._set_error("Usage: add <local-file-path>")
            return
        raw_path = " ".join(parts[1:]).strip().strip('"').strip("'")
        path = Path(raw_path).expanduser()
        track = self._local_scanner.track_from_path(path)
        if track is None:
            self._set_error(f"Not a supported audio file: {path}")
            return
        idx = self.ensure_track_in_queue(track)
        self._set_status(f"Added to queue: {track.label()} (#{idx + 1})")
        if self._state.current_track is None:
            self.play_track(track, queue_index=idx)

    def command_seek(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: seek <seconds-delta>")
            return
        self.seek_relative(safe_float(parts[1], 0.0))

    def command_volume(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: volume <0-100>")
            return
        self.set_volume(safe_int(parts[1], self._state.volume))

    def command_speed(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: speed <0.5-2.0>")
            return
        self.set_speed(safe_float(parts[1], self._state.playback_speed))

    def command_repeat(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: repeat off|one|all")
            return
        value = parts[1].strip().lower()
        if value not in {"off", "one", "all"}:
            self._set_error("Repeat mode must be off, one, or all.")
            return
        self._state.repeat_mode = RepeatMode(value)
        self._config["repeat_mode"] = value
        self._safe_save_config()
        self._set_status(f"Repeat mode: {value}")

    def command_shuffle(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: shuffle on|off")
            return
        value = parts[1].strip().lower()
        if value not in {"on", "off"}:
            self._set_error("Shuffle value must be on or off.")
            return
        enabled = value == "on"
        self._state.shuffle_enabled = enabled
        self._config["shuffle_enabled"] = enabled
        self._safe_save_config()
        self._set_status(f"Shuffle: {'on' if enabled else 'off'}")

    def command_sleep(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: sleep <minutes|off>")
            return
        arg = parts[1].strip().lower()
        if arg == "off":
            self._sleep_deadline = 0.0
            self._set_status("Sleep timer disabled.")
            return
        minutes = safe_float(arg, -1.0)
        if minutes <= 0:
            self._set_error("Sleep minutes must be greater than 0.")
            return
        self._sleep_deadline = time.time() + (minutes * 60.0)
        self._set_status(f"Sleep timer set for {minutes:.1f} minutes.")

    def command_status(self) -> None:
        track = self._state.current_track.label() if self._state.current_track else "None"
        self._set_status(
            f"Track={track} Vol={self._state.volume}% Speed={self._state.playback_speed:.2f}x "
            f"Repeat={self._state.repeat_mode.value} Shuffle={'on' if self._state.shuffle_enabled else 'off'} "
            f"Backend={self._player.backend_name}"
        )

    def command_backends(self) -> None:
        caps = PlaybackController.backend_capabilities()
        self._set_status(
            f"Backends: active={self._player.backend_name}, native={caps['native_available']}, mpv={caps['mpv_available']}"
        )
