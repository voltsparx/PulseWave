from __future__ import annotations

import os
import shlex
import shutil
import sys
import time
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Callable

from .controllers.command_controller import CommandController
from .controllers.input_controller import InputController
from .controllers.library_settings_controller import LibrarySettingsController
from .controllers.playback_runtime_controller import PlaybackRuntimeController
from .core.config import ConfigManager
from .core.library import LibraryStore
from .core.player import PlaybackController
from .core.queue import QueueManager
from .core.search import SearchResult, SearchService
from .core.state import AppState, RepeatMode, Track
from .integrations.lan_stream import LanStreamServer
from .integrations.local_scan import LocalScanner
from .integrations.ytmusic import YTMusicClient
from .services.metadata import MetadataEnricher
from .services.metrics import PerformanceMonitor
from .services.plugins import PluginManager
from .services.scripting import ScriptRunner
from .services.snapshots import SnapshotStore
from .ui.keybinds import KeyBindings
from .ui.renderer import Renderer
from .ui.themes import ThemeManager
from .ui.visualizer import VISUALIZER_MODES, VisualizerEngine
from .utils.helpers import clamp, safe_float, safe_int
from .utils.logger import get_logger
from .utils.paths import config_home


class PulseWave11App:
    RENDER_INTERVAL = 0.12
    TICK_INTERVAL = 0.06

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        theme_override: str | None = None,
        color_mode_override: str | None = None,
        backend_override: str | None = None,
    ) -> None:
        self.logger = get_logger("pulsewave-11")
        self.config_manager = ConfigManager(path=config_path)
        self.config = self.config_manager.load()
        if theme_override:
            self.config["theme"] = theme_override
        if color_mode_override:
            self.config["color_mode"] = color_mode_override
        if backend_override:
            self.config["audio_backend"] = backend_override

        self.state = AppState()
        self.queue = QueueManager()
        self.library = LibraryStore()
        self.metadata = MetadataEnricher()
        self.plugins = PluginManager(on_error=self._set_error)
        self.snapshots = SnapshotStore()
        self.scripting = ScriptRunner()
        self.perf = PerformanceMonitor()
        self.local_scanner = LocalScanner(self._music_dirs())
        self.ytmusic = YTMusicClient(enabled=bool(self.config.get("youtube_enabled", True)))
        self.search = SearchService(self.local_scanner, self.ytmusic, self.library)
        self.search_results: list[SearchResult] = []
        self.lan_stream = LanStreamServer(tracks_provider=lambda: self.queue.snapshot().items)

        self.player = PlaybackController(backend=str(self.config.get("audio_backend", "auto")))
        self.theme_manager = ThemeManager(Path.cwd() / "themes")
        self.theme = self.theme_manager.load_theme(str(self.config.get("theme", "default")))
        visualizer_cfg = self.config.get("visualizer", {})
        self.visualizer = VisualizerEngine(
            bars=safe_int(visualizer_cfg.get("bars"), 24),
            smoothing=safe_float(visualizer_cfg.get("smoothing"), 0.65),
            mode=str(visualizer_cfg.get("mode", "bars")),
            sensitivity=safe_float(visualizer_cfg.get("sensitivity"), 1.0),
            fps_limit=safe_int(visualizer_cfg.get("fps_limit"), 24),
            auto_hide_paused=bool(visualizer_cfg.get("auto_hide_paused", True)),
        )
        self.renderer = Renderer(
            theme_manager=self.theme_manager,
            theme=self.theme,
            visualizer=self.visualizer,
            color_mode=str(self.config.get("color_mode", "off")),
        )
        self.keybinds = KeyBindings.from_config(self.config.get("keybindings"))

        self._bootstrapped = False
        self._shutdown = False
        self._should_quit = False
        self._last_render = 0.0
        self._last_tick = 0.0
        self._last_session_save = 0.0
        self._screen_enabled = self._supports_ansi_ui()
        self._entered_alt_screen = False
        self._last_render_payload = ""
        self._last_terminal_size = shutil.get_terminal_size((100, 38))
        self._force_render = True
        self._last_metadata_track_key = ""
        self._last_plugin_track_key = ""

        self._settings_items = [
            {"key": "settings.volume_step", "label": "Volume Step", "type": "int", "min": 1, "max": 20, "step": 1},
            {"key": "settings.seek_step", "label": "Seek Step", "type": "int", "min": 1, "max": 60, "step": 1},
            {"key": "settings.speed_step", "label": "Speed Step", "type": "float", "min": 0.05, "max": 0.5, "step": 0.05},
            {"key": "playback_speed", "label": "Playback Speed", "type": "float", "min": 0.5, "max": 2.0, "step": 0.1},
            {"key": "visualizer.mode", "label": "Visualizer Mode", "choices": list(VISUALIZER_MODES)},
            {"key": "visualizer.bars", "label": "Visualizer Bars", "type": "int", "min": 8, "max": 64, "step": 2},
            {"key": "visualizer.smoothing", "label": "Visualizer Smooth", "type": "float", "min": 0.0, "max": 0.95, "step": 0.05},
            {"key": "visualizer.sensitivity", "label": "Visualizer Gain", "type": "float", "min": 0.1, "max": 3.0, "step": 0.1},
            {"key": "visualizer.fps_limit", "label": "Visualizer FPS", "type": "int", "min": 5, "max": 120, "step": 1},
            {"key": "theme", "label": "Theme", "choices": self.theme_manager.available_themes()},
            {"key": "color_mode", "label": "Color Mode", "choices": ["off", "basic", "full"]},
            {"key": "ui.use_symbols", "label": "UI Symbols", "type": "bool"},
            {"key": "ui.show_recently_played", "label": "Show Recent", "type": "bool"},
            {"key": "ui.show_command_hints", "label": "Show Hints", "type": "bool"},
            {"key": "ui.event_log_size", "label": "Event Log Size", "type": "int", "min": 5, "max": 200, "step": 5},
            {"key": "performance.show_panel", "label": "Show Perf", "type": "bool"},
        ]
        self._command_catalog: dict[str, str] = {
            "help": "help                         show command cheatsheet",
            "keymap": "keymap                       show quick keyboard controls",
            "search": "search <query>               search local/playlists/YouTube",
            "play": "play <idx|path|current>      play search result or file",
            "add": "add <path>                   add local file to queue",
            "playlist": "playlist <subcmd>            manage playlists",
            "category": "category <subcmd>            manage categories",
            "settings": "settings <subcmd>            runtime settings control",
            "alias": "alias <subcmd>               manage command aliases",
            "events": "events <subcmd>              show or clear event log",
            "vizpreset": "vizpreset <subcmd>           visualizer preset editor",
            "lyrics": "lyrics <subcmd>              lyrics sync controls",
            "metadata": "metadata <subcmd>            art/metadata cache controls",
            "plugins": "plugins <subcmd>             plugin manager",
            "snapshot": "snapshot <subcmd>            save/restore session state",
            "script": "script <subcmd>              run automation scripts",
            "perf": "perf <subcmd>                performance panel controls",
            "lanstream": "lanstream <subcmd>           LAN HTTP playlist stream",
            "volume": "volume <0-100>               set playback volume",
            "speed": "speed <0.5-2.0>              set playback speed",
            "seek": "seek <seconds>               relative seek",
            "repeat": "repeat off|one|all           repeat mode",
            "shuffle": "shuffle on|off               queue shuffle",
            "sleep": "sleep <minutes|off>          auto-stop timer",
            "status": "status                       show runtime status",
            "backends": "backends                     backend diagnostics",
            "config-home": "config-home                  print active config home",
            "scan": "scan                         rescan local library",
            "like": "like                         save current track to playlist",
            "next": "next                         play next track",
            "prev": "prev                         play previous track",
            "stop": "stop                         stop playback",
            "quit": "quit                         exit PulseWave-11",
        }

        self.input_controller = InputController(
            screen_enabled=self._screen_enabled,
            key_mapping_provider=lambda: self.keybinds.mapping,
            command_catalog_provider=lambda: self._command_catalog,
            status_callback=self._set_status,
            hints_callback=self._set_command_hints,
        )
        self.command_controller = CommandController(
            command_handlers_provider=self._command_handlers,
            action_handlers_provider=self._action_handlers,
            command_catalog_provider=lambda: self._command_catalog,
            suggest_commands=self._suggest_commands,
            hints_for_parts=self._hints_for_parts,
            set_hints=self._set_command_hints,
            set_error=self._set_error,
        )
        self.library_settings_controller = LibrarySettingsController(
            state=self.state,
            settings_items=self._settings_items,
            library=self.library,
            queue=self.queue,
            get_cfg=self._get_cfg,
            set_cfg=self._set_cfg,
            coerce_value_for_key=self._coerce_value_for_key,
            apply_runtime_key=self._apply_runtime_key,
            safe_save_config=self._safe_save_config,
            refresh_settings_preview=self._refresh_settings_preview,
            refresh_library_state=self._refresh_library_state,
            resolve_track_ref=self._resolve_track_ref,
            play_track=lambda track, queue_index: self._play_track(track, queue_index=queue_index),
            smart_playlists_enabled=self._smart_playlists_enabled,
            set_status=self._set_status,
            set_error=self._set_error,
        )
        self.playback_runtime_controller = PlaybackRuntimeController(
            state=self.state,
            queue=self.queue,
            player=self.player,
            library=self.library,
            local_scanner=self.local_scanner,
            ytmusic=self.ytmusic,
            visualizer=self.visualizer,
            config=self.config,
            get_cfg=self._get_cfg,
            safe_save_config=self._safe_save_config,
            set_status=self._set_status,
            set_error=self._set_error,
            refresh_recently_played=self._refresh_recently_played,
        )
        # Backward-compatible alias used by tests/tools.
        self._input_queue = self.input_controller.input_queue

        self._apply_runtime_config()
        self._refresh_settings_preview()
        self._set_command_hints(self._default_command_hints())

    def bootstrap(self) -> None:
        if self._bootstrapped:
            return
        category = str(self._get_cfg("library.default_category", "General"))
        playlist = str(self._get_cfg("library.default_playlist", "Liked Songs"))
        self.library.add_category(category)
        self.library.ensure_playlist(playlist, category=category, description="Default playlist")
        self._refresh_library_state()
        self._refresh_recently_played()
        self.state.search_history = list(self._search_history())
        self._restore_session_if_possible()
        if self._music_dirs():
            self._set_status(f"Indexed {len(self.local_scanner.scan(force=False))} local tracks.")
        else:
            self._set_status("No music directories configured. Use `settings set music_dirs <dir1,dir2>`.")
        self.plugins.load_all(enabled=self._enabled_plugins())
        self.plugins.call_hook("on_app_start", self)
        if bool(self._get_cfg("lan_stream.autostart", False)):
            port = safe_int(self._get_cfg("lan_stream.port", 8765), 8765)
            host = str(self._get_cfg("lan_stream.host", "0.0.0.0"))
            try:
                url = self.lan_stream.start(host=host, port=port)
                self.state.lan_stream_status = f"running at {url}"
            except Exception as exc:
                self.state.lan_stream_status = f"failed: {exc}"
        self._bootstrapped = True

    def run(self) -> None:
        self.bootstrap()
        self._start_input_thread()
        self._last_session_save = time.monotonic()
        self._enter_screen_mode()
        try:
            while not self._should_quit:
                now = time.monotonic()
                self._poll_terminal_resize()
                if now - self._last_tick >= self.TICK_INTERVAL:
                    self._tick()
                    self._last_tick = now
                if self._force_render or now - self._last_render >= self.RENDER_INTERVAL:
                    self._render()
                    self._last_render = now
                    self._force_render = False
                self._drain_input_queue()
                time.sleep(0.02)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True
        self._should_quit = True
        self.input_controller.stop()
        self._save_session(force=True)
        try:
            self.player.stop()
        except Exception:
            pass
        self.lan_stream.stop()
        self._leave_screen_mode()

    def handle_input(self, raw: str) -> None:
        text = raw.rstrip("\r\n")
        if self.input_controller.consume_quick_search_mode():
            if text.strip():
                self._command_search(["search", text.strip()])
            else:
                self._set_status("Quick search cancelled.")
            return

        actions = self.keybinds.actions_for(text)
        if actions:
            for action in actions:
                self._dispatch_action(action)
                if self._should_quit:
                    break
            return

        text = text.strip()
        if not text:
            return

        parts = self._parse_command(text)
        if not parts:
            return
        expanded = self._expand_command_alias(parts)
        if not expanded:
            return
        for command_parts in expanded:
            self._dispatch_command(command_parts)
            if self._should_quit:
                break

    def _start_input_thread(self) -> None:
        self.input_controller.start()

    def _drain_input_queue(self) -> None:
        self.input_controller.drain(on_line=self.handle_input, on_eof=self._quit, max_items=10)

    def _poll_terminal_resize(self) -> None:
        size = shutil.get_terminal_size((100, 38))
        if size == self._last_terminal_size:
            return
        self._last_terminal_size = size
        self._last_render_payload = ""
        self._force_render = True

    def _tick(self) -> None:
        self._refresh_player_state()
        self._refresh_visualizer()
        self._refresh_metadata()
        self._maybe_emit_track_change()
        self._sample_performance()
        self._handle_track_end()
        self._handle_sleep_timer()
        self._save_session(force=False)
        self._refresh_settings_preview()
        self.plugins.call_hook("on_tick", self)

    def _render(self) -> None:
        start = time.perf_counter()
        frame = self.renderer.render(self.state, self.queue.snapshot(), self.search_results)
        self.state.perf_frame_ms = (time.perf_counter() - start) * 1000.0
        payload = f"{frame}\n\n{self._prompt_text()}"
        if payload == self._last_render_payload:
            return
        self._last_render_payload = payload
        if self._screen_enabled:
            sys.stdout.write("\u001b[H\u001b[J")
            sys.stdout.write(payload)
        else:
            sys.stdout.write(payload + "\n")
        sys.stdout.flush()

    def _dispatch_command(self, parts: list[str]) -> None:
        self.plugins.call_hook("on_command", self, parts)
        self.command_controller.dispatch_command(parts)

    def _dispatch_action(self, action: str) -> None:
        self.command_controller.dispatch_action(action)

    def _command_handlers(self) -> dict[str, Callable[[list[str]], None]]:
        return {
            "help": self._command_help,
            "?": self._command_help,
            "keymap": self._command_keymap,
            "search": self._command_search,
            "play": self._command_play,
            "add": self._command_add,
            "seek": self._command_seek,
            "volume": self._command_volume,
            "speed": self._command_speed,
            "repeat": self._command_repeat,
            "shuffle": self._command_shuffle,
            "theme": self._command_theme,
            "settings": self._command_settings,
            "playlist": self._command_playlist,
            "category": self._command_category,
            "sleep": self._command_sleep,
            "status": self._command_status,
            "backends": self._command_backends,
            "config-home": self._command_config_home,
            "scan": self._command_scan,
            "rescan": self._command_scan,
            "like": self._command_like,
            "alias": self._command_alias,
            "events": self._command_events,
            "vizpreset": self._command_vizpreset,
            "lyrics": self._command_lyrics,
            "metadata": self._command_metadata,
            "plugins": self._command_plugins,
            "snapshot": self._command_snapshot,
            "script": self._command_script,
            "perf": self._command_perf,
            "lanstream": self._command_lanstream,
            "next": lambda _: self._play_next(manual=True),
            "prev": lambda _: self._play_previous(),
            "stop": lambda _: self._stop_playback(),
            "pause": lambda _: self._toggle_pause(),
            "quit": lambda _: self._quit(),
            "exit": lambda _: self._quit(),
        }

    def _action_handlers(self) -> dict[str, Callable[[], None]]:
        return {
            "play_pause": self._toggle_pause,
            "quit": self._quit,
            "next_track": lambda: self._play_next(manual=True),
            "prev_track": self._play_previous,
            "rescan_library": self._rescan_library,
            "help": lambda: self._command_help(["help"]),
            "volume_up": lambda: self._adjust_volume(self._volume_step()),
            "volume_down": lambda: self._adjust_volume(-self._volume_step()),
            "seek_forward": lambda: self._seek_relative(self._seek_step()),
            "seek_backward": lambda: self._seek_relative(-self._seek_step()),
            "toggle_mute": self._toggle_mute,
            "stop_playback": self._stop_playback,
            "quick_search": self._enter_quick_search,
            "toggle_settings": self._toggle_settings,
            "settings_next": self._settings_next,
            "settings_prev": self._settings_prev,
            "settings_inc": lambda: self._settings_adjust(+1),
            "settings_dec": lambda: self._settings_adjust(-1),
            "playlist_add_current": self._add_current_to_active_playlist,
            "speed_up": lambda: self._nudge_speed(+1),
            "speed_down": lambda: self._nudge_speed(-1),
            "cycle_repeat": self._cycle_repeat_mode,
            "toggle_shuffle": self._toggle_shuffle_quick,
            "cycle_theme": self._cycle_theme,
            "cycle_visualizer_mode": self._cycle_visualizer_mode,
            "cycle_color_mode": self._cycle_color_mode,
        }

    def _refresh_player_state(self) -> None:
        self.playback_runtime_controller.refresh_player_state()

    def _refresh_visualizer(self) -> None:
        self.playback_runtime_controller.refresh_visualizer()

    def _refresh_metadata(self) -> None:
        track = self.state.current_track
        if track is None:
            self.state.current_lyric_line = ""
            self.state.ascii_thumbnail = []
            self._last_metadata_track_key = ""
            return
        key = "|".join(self._track_identity(track))
        if key != self._last_metadata_track_key:
            self._last_metadata_track_key = key
            self.state.ascii_thumbnail = self.metadata.ascii_thumbnail(track, width=18, height=6)
        if bool(self._get_cfg("lyrics.enabled", True)):
            self.state.current_lyric_line = self.metadata.current_lyric_line(track, self.state.position)
        else:
            self.state.current_lyric_line = ""

    def _sample_performance(self) -> None:
        cpu, memory = self.perf.sample()
        self.state.perf_cpu_percent = cpu
        self.state.perf_memory_mb = memory

    def _maybe_emit_track_change(self) -> None:
        track = self.state.current_track
        key = "|".join(self._track_identity(track)) if track else ""
        if key == self._last_plugin_track_key:
            return
        self._last_plugin_track_key = key
        self.plugins.call_hook("on_track_change", self, track)

    def _handle_track_end(self) -> None:
        self.playback_runtime_controller.handle_track_end()

    def _handle_sleep_timer(self) -> None:
        self.playback_runtime_controller.handle_sleep_timer()

    def _toggle_pause(self) -> None:
        self.playback_runtime_controller.toggle_pause()

    def _stop_playback(self) -> None:
        self.playback_runtime_controller.stop_playback()

    def _play_next(self, *, manual: bool) -> None:
        self.playback_runtime_controller.play_next(manual=manual)

    def _play_previous(self) -> None:
        self.playback_runtime_controller.play_previous()

    def _play_track(
        self,
        track: Track,
        *,
        queue_index: int | None = None,
        start_position: float = 0.0,
        announce: bool = True,
    ) -> bool:
        return self.playback_runtime_controller.play_track(
            track,
            queue_index=queue_index,
            start_position=start_position,
            announce=announce,
        )

    def _resolve_play_source(self, track: Track) -> str | None:
        return self.playback_runtime_controller.resolve_play_source(track)

    def _ensure_track_in_queue(self, track: Track) -> int:
        return self.playback_runtime_controller.ensure_track_in_queue(track)

    def _track_identity(self, track: Track) -> tuple[str, str, str]:
        return self.playback_runtime_controller.track_identity(track)

    def _seek_relative(self, delta_seconds: float) -> None:
        self.playback_runtime_controller.seek_relative(delta_seconds)

    def _adjust_volume(self, delta: int) -> None:
        self.playback_runtime_controller.adjust_volume(delta)

    def _set_volume(self, value: int) -> None:
        self.playback_runtime_controller.set_volume(value)

    def _toggle_mute(self) -> None:
        self.playback_runtime_controller.toggle_mute()

    def _set_speed(self, value: float) -> None:
        self.playback_runtime_controller.set_speed(value)

    def _nudge_speed(self, direction: int) -> None:
        self.playback_runtime_controller.nudge_speed(direction)

    def _cycle_repeat_mode(self) -> None:
        self.playback_runtime_controller.cycle_repeat_mode()

    def _toggle_shuffle_quick(self) -> None:
        self.playback_runtime_controller.toggle_shuffle_quick()

    def _cycle_theme(self) -> None:
        names = self.theme_manager.available_themes()
        if not names:
            return
        current = str(self._get_cfg("theme", "default"))
        try:
            idx = names.index(current)
        except ValueError:
            idx = -1
        next_name = names[(idx + 1) % len(names)]
        self._set_cfg("theme", next_name)
        self._apply_runtime_key("theme")
        self._safe_save_config()
        self._set_status(f"Theme: {next_name}")

    def _cycle_visualizer_mode(self) -> None:
        current = str(self._get_cfg("visualizer.mode", "bars"))
        modes = list(VISUALIZER_MODES)
        try:
            idx = modes.index(current)
        except ValueError:
            idx = -1
        next_mode = modes[(idx + 1) % len(modes)]
        self._set_cfg("visualizer.mode", next_mode)
        self._apply_runtime_key("visualizer.mode")
        self._safe_save_config()
        self._set_status(f"Visualizer mode: {next_mode}")

    def _cycle_color_mode(self) -> None:
        modes = ["off", "basic", "full"]
        current = str(self._get_cfg("color_mode", "off"))
        try:
            idx = modes.index(current)
        except ValueError:
            idx = -1
        next_mode = modes[(idx + 1) % len(modes)]
        self._set_cfg("color_mode", next_mode)
        self._apply_runtime_key("color_mode")
        self._safe_save_config()
        self._set_status(f"Color mode: {next_mode}")

    def _toggle_settings(self) -> None:
        self.library_settings_controller.toggle_settings()

    def _settings_next(self) -> None:
        self.library_settings_controller.settings_next()

    def _settings_prev(self) -> None:
        self.library_settings_controller.settings_prev()

    def _settings_adjust(self, direction: int) -> None:
        self.library_settings_controller.settings_adjust(direction)

    def _refresh_settings_preview(self) -> None:
        preview: list[str] = []
        for idx, item in enumerate(self._settings_items):
            marker = ">" if idx == self.state.settings_cursor else " "
            value = self._get_cfg(item["key"])
            if isinstance(value, float):
                display = f"{value:.2f}"
            elif isinstance(value, bool):
                display = "on" if value else "off"
            else:
                display = str(value)
            preview.append(f"{marker} {item['label']:<18} {display}")
        self.state.settings_preview = preview

    def _command_help(self, _: list[str]) -> None:
        self._set_command_hints(self._default_command_hints())
        self._set_status(
            "Commands: search/play/add/playlist/category/settings/alias/events/vizpreset/lyrics/plugins/snapshot/script/perf/lanstream/speed/theme/volume/seek/repeat/shuffle/sleep/status/quit | Extra keys: . ; x z t g f | Raw mode: ':' + TAB + history"
        )

    def _command_keymap(self, _: list[str]) -> None:
        self._set_command_hints(
            [
                "[Space] play/pause  [p]/[n] prev/next  [s] stop  [+/-] volume  [[]]/[]] seek",
                "[.] speed+  [;] speed-  [x] cycle repeat  [z] toggle shuffle",
                "[t] cycle theme  [g] cycle colors  [f] cycle visualizer mode",
                "[/] quick search  [A] add current to playlist",
                "[,] settings panel  [j/k/l/u] navigate and adjust settings",
            ]
        )
        self._set_status("Keymap loaded in Hints panel.")

    def _command_search(self, parts: list[str]) -> None:
        self._set_command_hints(self._hints_for_parts(["search"]))
        query = " ".join(parts[1:]).strip()
        if not query:
            self._set_error("Usage: search <query>")
            return
        self.search_results = self.search.search_all(query=query, local_limit=15, online_limit=15)
        self._remember_search(query)
        self._set_status(f"Search: {len(self.search_results)} results for '{query}'. Use `play <index>`.")

    def _command_play(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_play(parts, search_results=self.search_results)

    def _command_add(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_add(parts)

    def _command_seek(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_seek(parts)

    def _command_volume(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_volume(parts)

    def _command_speed(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_speed(parts)

    def _command_repeat(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_repeat(parts)

    def _command_shuffle(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_shuffle(parts)

    def _command_theme(self, parts: list[str]) -> None:
        if len(parts) != 2:
            self._set_error("Usage: theme <name>")
            return
        self._set_cfg("theme", parts[1].strip())
        self._apply_runtime_key("theme")
        self._safe_save_config()
        self._set_status(f"Theme set: {self.theme.name}")

    def _command_settings(self, parts: list[str]) -> None:
        self.library_settings_controller.command_settings(parts)

    def _command_playlist(self, parts: list[str]) -> None:
        self.library_settings_controller.command_playlist(parts)

    def _command_category(self, parts: list[str]) -> None:
        self.library_settings_controller.command_category(parts)

    def _command_sleep(self, parts: list[str]) -> None:
        self.playback_runtime_controller.command_sleep(parts)

    def _command_status(self, _: list[str]) -> None:
        self.playback_runtime_controller.command_status()

    def _command_backends(self, _: list[str]) -> None:
        self.playback_runtime_controller.command_backends()

    def _command_config_home(self, _: list[str]) -> None:
        self._set_status(f"Config home: {config_home()}")

    def _command_scan(self, _: list[str]) -> None:
        self._rescan_library()

    def _command_like(self, _: list[str]) -> None:
        self._add_current_to_active_playlist()

    def _command_alias(self, parts: list[str]) -> None:
        aliases = self._command_aliases()
        if len(parts) < 2 or parts[1].lower() == "list":
            if not aliases:
                self._set_status("No command aliases configured.")
                return
            lines = [f"{name} => {target}" for name, target in sorted(aliases.items())]
            self._set_command_hints(lines[:5])
            self._set_status(f"Aliases: {len(aliases)} configured.")
            return

        sub = parts[1].lower()
        if sub == "set":
            if len(parts) < 4:
                self._set_error("Usage: alias set <name> <command[ && command]...>")
                return
            name = parts[2].strip().lower()
            if not name:
                self._set_error("Alias name cannot be empty.")
                return
            if name in {"alias"}:
                self._set_error("Cannot alias reserved command: alias")
                return
            target = " ".join(parts[3:]).strip()
            if not target:
                self._set_error("Alias target cannot be empty.")
                return
            aliases[name] = target
            self._set_cfg("command_aliases", aliases)
            self._safe_save_config()
            self._set_status(f"Alias set: {name} => {target}")
            return

        if sub in {"del", "delete", "rm"}:
            if len(parts) != 3:
                self._set_error("Usage: alias delete <name>")
                return
            name = parts[2].strip().lower()
            if name not in aliases:
                self._set_error(f"Alias not found: {name}")
                return
            aliases.pop(name, None)
            self._set_cfg("command_aliases", aliases)
            self._safe_save_config()
            self._set_status(f"Alias deleted: {name}")
            return

        self._set_error("Unknown alias subcommand.")

    def _command_events(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() in {"show", "tail"}:
            count = 5
            if len(parts) >= 3:
                count = max(1, min(20, safe_int(parts[2], 5)))
            events = self.state.event_log[-count:]
            if not events:
                self._set_status("Event log is empty.")
                return
            self._set_command_hints(events)
            self._set_status(f"Showing latest {len(events)} events in Hints panel.")
            return
        if parts[1].lower() == "clear":
            self.state.event_log = []
            self._set_status("Event log cleared.")
            return
        self._set_error("Usage: events show [count] | events clear")

    def _command_vizpreset(self, parts: list[str]) -> None:
        presets = self._visualizer_presets()
        if len(parts) < 2 or parts[1].lower() == "list":
            if not presets:
                self._set_status("No visualizer presets saved.")
                return
            names = sorted(presets.keys())
            self._set_command_hints([f"vizpreset load {name}" for name in names[:5]])
            self._set_status(f"Visualizer presets: {', '.join(names)}")
            return

        sub = parts[1].lower()
        if sub == "save":
            if len(parts) != 3:
                self._set_error("Usage: vizpreset save <name>")
                return
            name = parts[2].strip().lower()
            if not name:
                self._set_error("Preset name cannot be empty.")
                return
            presets[name] = self._current_visualizer_preset_payload()
            self._set_cfg("visualizer.presets", presets)
            self._safe_save_config()
            self._set_status(f"Visualizer preset saved: {name}")
            return
        if sub == "load":
            if len(parts) != 3:
                self._set_error("Usage: vizpreset load <name>")
                return
            name = parts[2].strip().lower()
            payload = presets.get(name)
            if not isinstance(payload, dict):
                self._set_error(f"Visualizer preset not found: {name}")
                return
            for key, value in payload.items():
                self._set_cfg(f"visualizer.{key}", value)
            for key in payload.keys():
                self._apply_runtime_key(f"visualizer.{key}")
            self._safe_save_config()
            self._set_status(f"Visualizer preset loaded: {name}")
            return
        if sub in {"delete", "del", "rm"}:
            if len(parts) != 3:
                self._set_error("Usage: vizpreset delete <name>")
                return
            name = parts[2].strip().lower()
            if name not in presets:
                self._set_error(f"Visualizer preset not found: {name}")
                return
            presets.pop(name, None)
            self._set_cfg("visualizer.presets", presets)
            self._safe_save_config()
            self._set_status(f"Visualizer preset deleted: {name}")
            return
        if sub == "chars":
            if len(parts) < 3:
                self._set_error("Usage: vizpreset chars <levels|default>")
                return
            chars = " ".join(parts[2:]).strip()
            if chars.lower() in {"default", "off", "none"}:
                self._set_cfg("visualizer.custom_levels", "")
                self._apply_runtime_key("visualizer.custom_levels")
                self._safe_save_config()
                self._set_status("Visualizer custom chars reset to default.")
                return
            if len(chars) < 2:
                self._set_error("Visualizer chars must be at least 2 characters.")
                return
            self._set_cfg("visualizer.custom_levels", chars)
            self._apply_runtime_key("visualizer.custom_levels")
            self._safe_save_config()
            self._set_status(f"Visualizer chars updated: {chars}")
            return

        self._set_error("Usage: vizpreset list|save|load|delete|chars")

    def _command_lyrics(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() == "show":
            track = self.state.current_track
            if track is None:
                self._set_error("No track loaded.")
                return
            lines = self.metadata.lyrics(track)
            if not lines:
                self._set_status("No synced lyrics found for current track.")
                return
            preview = [f"{int(t // 60):02d}:{int(t % 60):02d} {s}" for t, s in lines[:5]]
            self._set_command_hints(preview)
            self._set_status(f"Lyrics lines loaded: {len(lines)}")
            return
        if parts[1].lower() == "on":
            self._set_cfg("lyrics.enabled", True)
            self._apply_runtime_key("lyrics.enabled")
            self._safe_save_config()
            self._set_status("Lyrics sync enabled.")
            return
        if parts[1].lower() == "off":
            self._set_cfg("lyrics.enabled", False)
            self._apply_runtime_key("lyrics.enabled")
            self._safe_save_config()
            self._set_status("Lyrics sync disabled.")
            return
        self._set_error("Usage: lyrics show|on|off")

    def _command_metadata(self, parts: list[str]) -> None:
        track = self.state.current_track
        if len(parts) < 2 or parts[1].lower() == "show":
            if track is None:
                self._set_error("No track loaded.")
                return
            art = self.metadata.ascii_thumbnail(track, width=18, height=6)
            self.state.ascii_thumbnail = art
            self._set_command_hints(art[:5] if art else ["No art available"])
            self._set_status("Metadata preview loaded.")
            return
        if parts[1].lower() == "refresh":
            if track is None:
                self._set_error("No track loaded.")
                return
            self.metadata.refresh(track)
            self._last_metadata_track_key = ""
            self._refresh_metadata()
            self._set_status("Metadata cache refreshed for current track.")
            return
        self._set_error("Usage: metadata show|refresh")

    def _command_plugins(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() == "list":
            names = self.plugins.names()
            errs = self.plugins.errors()
            if not names and not errs:
                self._set_status("No plugins loaded.")
                return
            lines = [f"loaded: {name}" for name in names[:3]]
            lines.extend([f"error: {name}: {msg}" for name, msg in list(errs.items())[:2]])
            self._set_command_hints(lines)
            self._set_status(f"Plugins loaded: {len(names)}, errors: {len(errs)}")
            return
        if parts[1].lower() == "reload":
            self.plugins.reload(enabled=self._enabled_plugins())
            self._set_status(f"Plugins reloaded ({len(self.plugins.names())} loaded).")
            return
        self._set_error("Usage: plugins list|reload")

    def _command_snapshot(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() == "list":
            names = self.snapshots.list_names()
            if not names:
                self._set_status("No snapshots found.")
                return
            self._set_command_hints([f"snapshot load {name}" for name in names[:5]])
            self._set_status(f"Snapshots: {', '.join(names)}")
            return
        sub = parts[1].lower()
        if sub == "save":
            if len(parts) != 3:
                self._set_error("Usage: snapshot save <name>")
                return
            try:
                name = self.snapshots.save(parts[2], self._snapshot_payload())
            except ValueError as exc:
                self._set_error(str(exc))
                return
            self._set_status(f"Snapshot saved: {name}")
            return
        if sub == "load":
            if len(parts) != 3:
                self._set_error("Usage: snapshot load <name>")
                return
            payload = self.snapshots.load(parts[2])
            if payload is None:
                self._set_error(f"Snapshot not found: {parts[2]}")
                return
            self._restore_snapshot_payload(payload)
            self._set_status(f"Snapshot loaded: {parts[2]}")
            return
        if sub in {"delete", "del", "rm"}:
            if len(parts) != 3:
                self._set_error("Usage: snapshot delete <name>")
                return
            if not self.snapshots.delete(parts[2]):
                self._set_error(f"Snapshot not found: {parts[2]}")
                return
            self._set_status(f"Snapshot deleted: {parts[2]}")
            return
        self._set_error("Usage: snapshot list|save|load|delete")

    def _command_script(self, parts: list[str]) -> None:
        if len(parts) < 3 or parts[1].lower() != "run":
            self._set_error("Usage: script run <path>")
            return
        raw_path = " ".join(parts[2:]).strip().strip('"').strip("'")
        path = Path(raw_path).expanduser()
        max_lines = max(10, safe_int(self._get_cfg("scripting.max_lines", 2000), 2000))
        self.scripting.run_file(
            path,
            run_command=self.handle_input,
            set_status=self._set_status,
            set_error=self._set_error,
            max_lines=max_lines,
        )

    def _command_perf(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() == "status":
            self._set_status(
                f"Perf panel={'on' if self.state.show_perf_panel else 'off'} "
                f"CPU={self.state.perf_cpu_percent:.1f}% RAM={self.state.perf_memory_mb:.1f}MB"
            )
            return
        sub = parts[1].lower()
        if sub not in {"on", "off"}:
            self._set_error("Usage: perf on|off|status")
            return
        enabled = sub == "on"
        self._set_cfg("performance.show_panel", enabled)
        self._apply_runtime_key("performance.show_panel")
        self._safe_save_config()
        self._set_status(f"Perf panel {'enabled' if enabled else 'disabled'}.")

    def _command_lanstream(self, parts: list[str]) -> None:
        if len(parts) < 2 or parts[1].lower() == "status":
            stat = self.lan_stream.status()
            if bool(stat["running"]):
                self.state.lan_stream_status = f"running at {stat['playlist_url']}"
            else:
                self.state.lan_stream_status = "stopped"
            self._set_status(f"LAN stream: {self.state.lan_stream_status}")
            return
        sub = parts[1].lower()
        if sub == "start":
            if self.lan_stream.running:
                self._set_status(f"LAN stream already running: {self.lan_stream.playlist_url}")
                return
            port = safe_int(parts[2], safe_int(self._get_cfg("lan_stream.port", 8765), 8765)) if len(parts) >= 3 else safe_int(self._get_cfg("lan_stream.port", 8765), 8765)
            host = str(self._get_cfg("lan_stream.host", "0.0.0.0"))
            try:
                url = self.lan_stream.start(host=host, port=port)
            except Exception as exc:
                self._set_error(f"LAN stream start failed: {exc}")
                return
            stat = self.lan_stream.status()
            self._set_cfg("lan_stream.port", safe_int(stat.get("port"), port))
            self._safe_save_config()
            self.state.lan_stream_status = f"running at {url}"
            self._set_status(f"LAN stream started: {url}")
            return
        if sub == "stop":
            self.lan_stream.stop()
            self.state.lan_stream_status = "stopped"
            self._set_status("LAN stream stopped.")
            return
        self._set_error("Usage: lanstream start [port]|stop|status")

    def _rescan_library(self) -> None:
        self._set_status(f"Rescanned library: {len(self.search.refresh_local_library())} tracks.")

    def _enter_quick_search(self) -> None:
        self.input_controller.enter_quick_search()
        self._set_command_hints(
            [
                "search <query>               enter a title, artist, or album",
                "play <index>                 play a result from Discover panel",
                "playlist add <name> <index>  save a search result to playlist",
            ]
        )
        self._set_status("Quick search: type query and press Enter.")

    def _add_current_to_active_playlist(self) -> None:
        self.library_settings_controller.add_current_to_active_playlist()

    def _resolve_track_ref(self, ref: str) -> Track | None:
        if ref.lower() == "current":
            return self.state.current_track
        if ref.isdigit():
            idx = int(ref)
            if 1 <= idx <= len(self.search_results):
                return self.search_results[idx - 1].track
        return None

    def _quit(self) -> None:
        self._should_quit = True
        self._set_status("Shutting down...")

    def _prompt_label(self) -> str:
        return "Search> " if self.input_controller.awaiting_quick_search else "Command> "

    def _prompt_text(self) -> str:
        return self.input_controller.prompt_text(self._prompt_label())

    def _supports_ansi_ui(self) -> bool:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        term = os.environ.get("TERM", "").lower()
        if term == "dumb":
            return False
        return True

    def _enter_screen_mode(self) -> None:
        if not self._screen_enabled or self._entered_alt_screen:
            return
        sys.stdout.write("\u001b[?1049h\u001b[?25l\u001b[H\u001b[2J")
        sys.stdout.flush()
        self._entered_alt_screen = True

    def _leave_screen_mode(self) -> None:
        if not self._screen_enabled:
            return
        if self._entered_alt_screen:
            sys.stdout.write("\u001b[?25h\u001b[?1049l")
            sys.stdout.flush()
            self._entered_alt_screen = False
        self._last_render_payload = ""

    def _default_command_hints(self) -> list[str]:
        return [
            self._command_catalog["search"],
            self._command_catalog["play"],
            self._command_catalog["playlist"],
            self._command_catalog["settings"],
            self._command_catalog["vizpreset"],
        ]

    def _set_command_hints(self, lines: list[str]) -> None:
        if not self.state.ui_show_hints:
            self.state.command_suggestions = []
            return
        cleaned = [line.rstrip() for line in lines if line.strip()]
        self.state.command_suggestions = cleaned[:5]

    def _hints_for_parts(self, parts: list[str]) -> list[str]:
        cmd = parts[0].lower()
        if cmd == "playlist":
            return [
                "playlist list [category]      list playlists",
                "playlist load <name>          load playlist into queue",
                "playlist add <name> <index>   add current/result to playlist",
                "playlist rename <old> <new>   rename playlist",
                "playlist delete <name>        remove playlist",
            ]
        if cmd == "settings":
            return [
                "settings show                 open settings panel",
                "settings hide                 hide settings panel",
                "settings get <key.path>       read a config key",
                "settings set <key.path> <v>   update a config key",
                "Use j/k/l/u keys for quick panel adjustments.",
            ]
        if cmd == "alias":
            return [
                "alias list                    list configured aliases",
                "alias set <n> <cmd...>        create/update alias",
                "alias delete <name>           remove alias",
                "Alias chains support: cmd1 && cmd2",
            ]
        if cmd == "events":
            return [
                "events show [count]           show latest events in hints",
                "events clear                  clear event history",
                "settings set ui.event_log_size <n>   change log size",
            ]
        if cmd == "vizpreset":
            return [
                "vizpreset list                list visualizer presets",
                "vizpreset save <name>         save current visualizer config",
                "vizpreset load <name>         load a preset",
                "vizpreset chars <levels>      set custom ASCII levels",
                "vizpreset chars default       reset to theme levels",
            ]
        if cmd == "lyrics":
            return [
                "lyrics show                   show parsed lyrics preview",
                "lyrics on                     enable synced lyrics",
                "lyrics off                    disable synced lyrics",
            ]
        if cmd == "plugins":
            return [
                "plugins list                  show loaded plugins/errors",
                "plugins reload                reload plugin directory",
                f"Plugin dir: {self.plugins.plugin_dir}",
            ]
        if cmd == "snapshot":
            return [
                "snapshot list                 list saved snapshots",
                "snapshot save <name>          save queue/playback snapshot",
                "snapshot load <name>          restore snapshot",
                "snapshot delete <name>        delete snapshot",
            ]
        if cmd == "script":
            return [
                "script run <path>             run automation script",
                "Script comments: # ...",
                "Script delay line: sleep <seconds> or wait <seconds>",
            ]
        if cmd == "perf":
            return [
                "perf status                   show perf metrics status",
                "perf on                       show perf panel in UI",
                "perf off                      hide perf panel in UI",
            ]
        if cmd == "lanstream":
            return [
                "lanstream status              show LAN stream status",
                "lanstream start [port]        start HTTP playlist stream",
                "lanstream stop                stop stream server",
            ]
        if cmd == "keymap":
            return [
                "keymap                        load keyboard control cheat sheet",
                "speed keys: . / ;            quick speed up/down",
                "style keys: t / g / f        cycle theme, colors, visualizer",
                "playback keys: x / z         repeat cycle and shuffle toggle",
            ]
        if cmd == "category":
            return [
                "category list                 list categories",
                "category add <name>           create category",
                "category use <name>           set active category",
            ]
        if cmd == "search":
            return [
                "search <query>                find tracks",
                "play <index>                  play a search result",
                "playlist add <name> <index>   save result to playlist",
            ]
        if cmd in self._command_catalog:
            return [self._command_catalog[cmd]] + self._default_command_hints()[:4]
        return self._default_command_hints()

    def _suggest_commands(self, raw: str) -> list[str]:
        names = sorted(self._command_catalog.keys())
        if not raw:
            return names[:3]
        prefix = [name for name in names if name.startswith(raw)]
        if prefix:
            return prefix[:3]
        return get_close_matches(raw, names, n=3, cutoff=0.45)

    def _set_status(self, message: str) -> None:
        self.state.status_message = message
        self.state.last_error = ""
        self._append_event("INFO", message)

    def _set_error(self, message: str) -> None:
        self.state.last_error = message
        self.state.status_message = message
        self._append_event("ERROR", message)

    def _parse_command(self, raw: str) -> list[str]:
        try:
            return shlex.split(raw, posix=(os.name != "nt"))
        except ValueError as exc:
            self._set_error(f"Invalid command syntax: {exc}")
            return []

    def _command_aliases(self) -> dict[str, str]:
        raw = self.config.get("command_aliases", {})
        if not isinstance(raw, dict):
            return {}
        aliases: dict[str, str] = {}
        for name, target in raw.items():
            key = str(name).strip().lower()
            if not key:
                continue
            if isinstance(target, str) and target.strip():
                aliases[key] = target.strip()
        return aliases

    def _enabled_plugins(self) -> list[str]:
        raw = self._get_cfg("plugins.enabled", [])
        if not isinstance(raw, list):
            return []
        return [str(item).strip().lower() for item in raw if str(item).strip()]

    def _visualizer_presets(self) -> dict[str, dict[str, Any]]:
        raw = self._get_cfg("visualizer.presets", {})
        if not isinstance(raw, dict):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for key, value in raw.items():
            name = str(key).strip().lower()
            if not name or not isinstance(value, dict):
                continue
            out[name] = dict(value)
        return out

    def _current_visualizer_preset_payload(self) -> dict[str, Any]:
        return {
            "mode": str(self._get_cfg("visualizer.mode", "bars")),
            "bars": safe_int(self._get_cfg("visualizer.bars", 24), 24),
            "smoothing": safe_float(self._get_cfg("visualizer.smoothing", 0.65), 0.65),
            "sensitivity": safe_float(self._get_cfg("visualizer.sensitivity", 1.0), 1.0),
            "fps_limit": safe_int(self._get_cfg("visualizer.fps_limit", 24), 24),
            "custom_levels": str(self._get_cfg("visualizer.custom_levels", "")),
        }

    def _snapshot_payload(self) -> dict[str, Any]:
        snap = self.queue.snapshot()
        return {
            "queue": [self._track_to_record(track) for track in snap.items],
            "queue_index": snap.index,
            "position": float(self.state.position),
            "active_playlist": self.state.active_playlist,
            "active_category": self.state.active_category,
            "visualizer": self._current_visualizer_preset_payload(),
        }

    def _restore_snapshot_payload(self, payload: dict[str, Any]) -> None:
        queue_raw = payload.get("queue", [])
        tracks: list[Track] = []
        if isinstance(queue_raw, list):
            for row in queue_raw:
                if isinstance(row, dict):
                    track = self._record_to_track(row)
                    if track is not None:
                        tracks.append(track)
        self.queue.clear()
        self.queue.extend(tracks)
        idx = safe_int(payload.get("queue_index"), -1)
        if tracks and 0 <= idx < len(tracks):
            self.queue.set_index(idx)
        elif tracks:
            self.queue.set_index(0)
        self.state.current_track = self.queue.current()
        self.state.position = max(0.0, safe_float(payload.get("position"), 0.0))
        self.state.duration = self.state.current_track.duration if self.state.current_track else 0.0
        self.state.is_playing = False
        self.state.is_paused = False
        self.state.active_playlist = str(payload.get("active_playlist", self.state.active_playlist))
        self.state.active_category = str(payload.get("active_category", self.state.active_category))
        viz_raw = payload.get("visualizer", {})
        if isinstance(viz_raw, dict):
            for key, value in viz_raw.items():
                self._set_cfg(f"visualizer.{key}", value)
            for key in viz_raw.keys():
                self._apply_runtime_key(f"visualizer.{key}")
        self._refresh_library_state()

    def _split_alias_chain(self, target: str) -> list[str]:
        text = target.strip()
        if not text:
            return []
        if "&&" in text:
            return [chunk.strip() for chunk in text.split("&&") if chunk.strip()]
        if ";" in text:
            return [chunk.strip() for chunk in text.split(";") if chunk.strip()]
        return [text]

    def _expand_command_alias(
        self,
        parts: list[str],
        *,
        depth: int = 0,
        seen: set[str] | None = None,
    ) -> list[list[str]]:
        if not parts:
            return []
        if depth > 6:
            self._set_error("Alias expansion exceeded max depth (6).")
            return []

        aliases = self._command_aliases()
        name = parts[0].lower()
        target = aliases.get(name)
        if target is None:
            return [parts]

        visited = set(seen or set())
        if name in visited:
            self._set_error(f"Alias loop detected: {' -> '.join(sorted(visited | {name}))}")
            return []
        visited.add(name)

        tail = " ".join(parts[1:]).strip()
        expanded_parts: list[list[str]] = []
        for chunk in self._split_alias_chain(target):
            rendered = chunk.replace("{args}", tail).strip() if "{args}" in chunk else chunk
            if "{args}" not in chunk and tail:
                rendered = f"{rendered} {tail}".strip()
            parsed = self._parse_command(rendered)
            if not parsed:
                return []
            nested = self._expand_command_alias(parsed, depth=depth + 1, seen=visited)
            if not nested:
                return []
            expanded_parts.extend(nested)
        return expanded_parts

    def _event_log_limit(self) -> int:
        raw = self._get_cfg("ui.event_log_size", 40)
        return int(clamp(safe_int(raw, 40), 1, 200))

    def _trim_event_log(self) -> None:
        limit = self._event_log_limit()
        if len(self.state.event_log) > limit:
            self.state.event_log = self.state.event_log[-limit:]

    def _append_event(self, level: str, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.state.event_log.append(f"[{stamp}] {level}: {message}")
        self._trim_event_log()

    def _save_session(self, *, force: bool) -> None:
        session = self.config.setdefault("session", {})
        interval = max(1, safe_int(session.get("autosave_interval_seconds", 5), 5))
        now = time.monotonic()
        if not force and now - self._last_session_save < interval:
            return
        self._last_session_save = now
        if self.state.current_track is not None:
            session["last_track"] = self._track_to_record(self.state.current_track)
            session["last_position"] = float(max(0.0, self.state.position))
        else:
            session["last_track"] = {}
            session["last_position"] = 0.0
        self._safe_save_config()

    def _restore_session_if_possible(self) -> None:
        session = self.config.get("session", {})
        if not bool(session.get("resume_last_track", True)):
            return
        record = session.get("last_track") or {}
        if not isinstance(record, dict) or not record:
            return
        track = self._record_to_track(record)
        if track is None:
            return
        idx = self._ensure_track_in_queue(track)
        self.queue.set_index(idx)
        self.state.current_track = track
        self.state.duration = max(track.duration, 0.0)
        self.state.position = max(0.0, safe_float(session.get("last_position"), 0.0))
        self.state.is_playing = False
        self.state.is_paused = False
        if bool(session.get("auto_resume", False)):
            self._play_track(track, queue_index=idx, start_position=self.state.position, announce=False)
            self._set_status(f"Auto-resumed: {track.label()}")
        else:
            self._set_status(f"Restored session track: {track.label()}")

    def _search_history(self) -> list[str]:
        raw = self.config.get("search", {}).get("history", [])
        if not isinstance(raw, list):
            return []
        return [str(item) for item in raw if str(item).strip()]

    def _remember_search(self, query: str) -> None:
        entry = query.strip()
        if not entry:
            return
        search_cfg = self.config.setdefault("search", {})
        limit = max(1, safe_int(search_cfg.get("history_limit", 50), 50))
        history = [item for item in self._search_history() if item.lower() != entry.lower()]
        history.insert(0, entry)
        search_cfg["history"] = history[:limit]
        self.state.search_history = list(search_cfg["history"])
        self._safe_save_config()

    def _refresh_library_state(self) -> None:
        categories = self.library.categories() or ["General"]
        self.state.categories = categories
        if self.state.active_category not in categories:
            self.state.active_category = categories[0]
        names = [p.name for p in self.library.playlists(category=self.state.active_category)]
        if self._smart_playlists_enabled():
            for smart in ("Recently Played", "Most Played"):
                if smart not in names:
                    names.append(smart)
        self.state.playlists = names
        if self.state.active_playlist and self.state.active_playlist not in names:
            self.state.active_playlist = ""
        if not self.state.active_playlist and names:
            self.state.active_playlist = names[0]

    def _refresh_recently_played(self) -> None:
        self.state.recently_played = [track.label() for track in self.library.recently_played(limit=20)]

    def _coerce_value_for_key(self, key: str, raw_value: str) -> Any:
        current = self._get_cfg(key, None)
        text = raw_value.strip()
        if isinstance(current, bool):
            lowered = text.lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
            return current
        if isinstance(current, int) and not isinstance(current, bool):
            return safe_int(text, current)
        if isinstance(current, float):
            return safe_float(text, current)
        if isinstance(current, list):
            return [item.strip() for item in text.split(",") if item.strip()]
        lowered = text.lower()
        if lowered in {"true", "false"}:
            return lowered == "true"
        return text

    def _music_dirs(self) -> list[str]:
        raw = self.config.get("music_dirs", [])
        return [str(item) for item in raw] if isinstance(raw, list) else []

    def _safe_save_config(self) -> None:
        try:
            self.config_manager.save(self.config)
        except Exception as exc:
            self.logger.error("Failed to save config: %s", exc)
            self._set_error(f"Failed to save config: {exc}")

    def _apply_runtime_config(self) -> None:
        for key in (
            "theme",
            "color_mode",
            "music_dirs",
            "volume",
            "repeat_mode",
            "shuffle_enabled",
            "playback_speed",
            "visualizer.mode",
            "visualizer.bars",
            "visualizer.smoothing",
            "visualizer.sensitivity",
            "visualizer.fps_limit",
            "visualizer.auto_hide_paused",
            "visualizer.custom_levels",
            "ui.use_symbols",
            "ui.show_recently_played",
            "ui.show_command_hints",
            "ui.event_log_size",
            "performance.show_panel",
            "lyrics.enabled",
            "keybindings",
        ):
            self._apply_runtime_key(key)
        self.state.active_category = str(self._get_cfg("library.default_category", "General"))
        self.state.active_playlist = str(self._get_cfg("library.default_playlist", "Liked Songs"))
        self._refresh_library_state()

    def _apply_runtime_key(self, key: str) -> None:
        if key == "theme":
            self.theme = self.theme_manager.load_theme(str(self._get_cfg("theme", "default")))
            self.renderer.set_theme(self.theme)
            self._update_setting_choices("theme", self.theme_manager.available_themes())
            return
        if key == "color_mode":
            mode = str(self._get_cfg("color_mode", "off"))
            if mode not in {"off", "basic", "full"}:
                mode = "off"
                self._set_cfg("color_mode", mode)
            self.renderer.color_mode = mode
            return
        if key == "music_dirs":
            self.local_scanner.set_directories(self._music_dirs())
            return
        if key == "volume":
            self.state.volume = self.player.set_volume(safe_int(self._get_cfg("volume", 60), 60))
            return
        if key == "repeat_mode":
            value = str(self._get_cfg("repeat_mode", "off")).lower()
            if value not in {"off", "one", "all"}:
                value = "off"
                self._set_cfg("repeat_mode", value)
            self.state.repeat_mode = RepeatMode(value)
            return
        if key == "shuffle_enabled":
            self.state.shuffle_enabled = bool(self._get_cfg("shuffle_enabled", False))
            return
        if key == "playback_speed":
            self.state.playback_speed = self.player.set_speed(safe_float(self._get_cfg("playback_speed", 1.0), 1.0))
            return
        if key == "keybindings":
            self.keybinds = KeyBindings.from_config(self.config.get("keybindings"))
            return
        if key == "performance.show_panel":
            self.state.show_perf_panel = bool(self._get_cfg("performance.show_panel", False))
            return
        if key == "lyrics.enabled":
            if not bool(self._get_cfg("lyrics.enabled", True)):
                self.state.current_lyric_line = ""
            return
        if key.startswith("ui."):
            self.state.ui_symbols = bool(self._get_cfg("ui.use_symbols", True))
            self.state.ui_show_recent = bool(self._get_cfg("ui.show_recently_played", True))
            self.state.ui_show_hints = bool(self._get_cfg("ui.show_command_hints", True))
            self._trim_event_log()
            if not self.state.ui_show_hints:
                self.state.command_suggestions = []
            elif not self.state.command_suggestions:
                self._set_command_hints(self._default_command_hints())
            return
        if key.startswith("visualizer."):
            mode = str(self._get_cfg("visualizer.mode", "bars"))
            self.visualizer.mode = mode if mode in VISUALIZER_MODES else "bars"
            self.state.visualizer_mode = self.visualizer.mode
            bars = int(clamp(safe_int(self._get_cfg("visualizer.bars", 24), 24), 8, 64))
            if bars != self.visualizer.bars:
                self.visualizer.bars = bars
                self.visualizer._previous = [0.0] * bars
                self.visualizer._last_bars = [0] * bars
            self.visualizer.smoothing = clamp(safe_float(self._get_cfg("visualizer.smoothing", 0.65), 0.65), 0.0, 0.99)
            self.visualizer.sensitivity = clamp(safe_float(self._get_cfg("visualizer.sensitivity", 1.0), 1.0), 0.1, 3.0)
            self.visualizer.fps_limit = int(clamp(safe_int(self._get_cfg("visualizer.fps_limit", 24), 24), 5, 120))
            self.visualizer.auto_hide_paused = bool(self._get_cfg("visualizer.auto_hide_paused", True))
            levels = str(self._get_cfg("visualizer.custom_levels", "")).strip()
            self.renderer.set_visualizer_levels_override(levels if len(levels) >= 2 else None)

    def _update_setting_choices(self, key: str, choices: list[str]) -> None:
        for item in self._settings_items:
            if item.get("key") == key:
                item["choices"] = list(choices)
                return

    def _volume_step(self) -> int:
        return max(1, safe_int(self._get_cfg("settings.volume_step", 5), 5))

    def _seek_step(self) -> int:
        return max(1, safe_int(self._get_cfg("settings.seek_step", 5), 5))

    def _smart_playlists_enabled(self) -> bool:
        return bool(self._get_cfg("library.smart_playlists_enabled", True))

    def _get_cfg(self, path: str, default: Any = None) -> Any:
        current: Any = self.config
        for segment in path.split("."):
            if not isinstance(current, dict) or segment not in current:
                return default
            current = current[segment]
        return current

    def _set_cfg(self, path: str, value: Any) -> None:
        current: Any = self.config
        parts = path.split(".")
        for segment in parts[:-1]:
            if not isinstance(current, dict):
                return
            current = current.setdefault(segment, {})
        if isinstance(current, dict):
            current[parts[-1]] = value

    def _track_to_record(self, track: Track) -> dict[str, Any]:
        return {
            "id": track.id,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "duration": track.duration,
            "source": track.source,
            "path": str(track.path) if track.path else "",
            "stream_url": track.stream_url or "",
            "file_format": track.file_format,
            "bitrate_kbps": track.bitrate_kbps,
        }

    def _record_to_track(self, record: dict[str, Any]) -> Track | None:
        track_id = str(record.get("id", "")).strip()
        title = str(record.get("title", "")).strip()
        if not track_id or not title:
            return None
        path_value = str(record.get("path", "")).strip()
        return Track(
            id=track_id,
            title=title,
            artist=str(record.get("artist", "Unknown Artist")),
            album=str(record.get("album", "")),
            duration=safe_float(record.get("duration"), 0.0),
            source=str(record.get("source", "local")),
            path=Path(path_value).expanduser() if path_value else None,
            stream_url=str(record.get("stream_url", "")) or None,
            file_format=str(record.get("file_format", "")),
            bitrate_kbps=safe_int(record.get("bitrate_kbps"), 0),
        )
