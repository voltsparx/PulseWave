from __future__ import annotations

from typing import Any, Callable

from ..core.library import LibraryStore
from ..core.queue import QueueManager
from ..core.state import AppState, Track
from ..utils.helpers import clamp, safe_float, safe_int


class LibrarySettingsController:
    def __init__(
        self,
        *,
        state: AppState,
        settings_items: list[dict[str, Any]],
        library: LibraryStore,
        queue: QueueManager,
        get_cfg: Callable[[str, Any], Any],
        set_cfg: Callable[[str, Any], None],
        coerce_value_for_key: Callable[[str, str], Any],
        apply_runtime_key: Callable[[str], None],
        safe_save_config: Callable[[], None],
        refresh_settings_preview: Callable[[], None],
        refresh_library_state: Callable[[], None],
        resolve_track_ref: Callable[[str], Track | None],
        play_track: Callable[[Track, int], None],
        smart_playlists_enabled: Callable[[], bool],
        set_status: Callable[[str], None],
        set_error: Callable[[str], None],
    ) -> None:
        self._state = state
        self._settings_items = settings_items
        self._library = library
        self._queue = queue
        self._get_cfg = get_cfg
        self._set_cfg = set_cfg
        self._coerce_value_for_key = coerce_value_for_key
        self._apply_runtime_key = apply_runtime_key
        self._safe_save_config = safe_save_config
        self._refresh_settings_preview = refresh_settings_preview
        self._refresh_library_state = refresh_library_state
        self._resolve_track_ref = resolve_track_ref
        self._play_track = play_track
        self._smart_playlists_enabled = smart_playlists_enabled
        self._set_status = set_status
        self._set_error = set_error

    def toggle_settings(self) -> None:
        self._state.show_settings = not self._state.show_settings
        self._refresh_settings_preview()
        self._set_status("Settings panel shown." if self._state.show_settings else "Settings panel hidden.")

    def settings_next(self) -> None:
        self._state.show_settings = True
        self._state.settings_cursor = (self._state.settings_cursor + 1) % len(self._settings_items)
        self._refresh_settings_preview()

    def settings_prev(self) -> None:
        self._state.show_settings = True
        self._state.settings_cursor = (self._state.settings_cursor - 1) % len(self._settings_items)
        self._refresh_settings_preview()

    def settings_adjust(self, direction: int) -> None:
        self._state.show_settings = True
        item = self._settings_items[self._state.settings_cursor]
        key = item["key"]
        current = self._get_cfg(key, None)
        choices = item.get("choices")
        if choices:
            values = list(choices)
            idx = 0
            for i, raw in enumerate(values):
                if str(raw).lower() == str(current).lower():
                    idx = i
                    break
            value = values[(idx + direction) % len(values)]
            self._set_cfg(key, value)
            self._apply_runtime_key(key)
            self._safe_save_config()
            self._refresh_settings_preview()
            self._set_status(f"{item['label']}: {value}")
            return

        kind = item.get("type", "int")
        if kind == "bool":
            value = not bool(current)
            self._set_cfg(key, value)
            self._apply_runtime_key(key)
            self._safe_save_config()
            self._refresh_settings_preview()
            self._set_status(f"{item['label']}: {'on' if value else 'off'}")
            return

        step = safe_float(item.get("step"), 1.0)
        lower = safe_float(item.get("min"), 0.0)
        upper = safe_float(item.get("max"), 100.0)
        if kind == "int":
            value = int(clamp(safe_int(current, int(lower)) + int(step) * direction, int(lower), int(upper)))
        else:
            value = round(clamp(safe_float(current, lower) + step * direction, lower, upper), 2)
        self._set_cfg(key, value)
        self._apply_runtime_key(key)
        self._safe_save_config()
        self._refresh_settings_preview()
        self._set_status(f"{item['label']}: {value}")

    def command_settings(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self._state.show_settings = True
            self._refresh_settings_preview()
            self._set_status("Settings panel opened. Use j/k to navigate and l/u to adjust.")
            return
        sub = parts[1].lower()
        if sub == "show":
            self._state.show_settings = True
            self._refresh_settings_preview()
            self._set_status("Settings panel shown.")
            return
        if sub == "hide":
            self._state.show_settings = False
            self._set_status("Settings panel hidden.")
            return
        if sub == "get":
            if len(parts) != 3:
                self._set_error("Usage: settings get <key.path>")
                return
            key = parts[2]
            self._set_status(f"{key} = {self._get_cfg(key, None)}")
            return
        if sub == "set":
            if len(parts) < 4:
                self._set_error("Usage: settings set <key.path> <value>")
                return
            key = parts[2]
            value = self._coerce_value_for_key(key, " ".join(parts[3:]))
            self._set_cfg(key, value)
            self._apply_runtime_key(key)
            self._safe_save_config()
            self._refresh_settings_preview()
            self._set_status(f"Updated {key} -> {value}")
            return
        self._set_error("Unknown settings subcommand.")

    def command_playlist(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self._set_error("Usage: playlist list|create|add|load|use|delete|rename")
            return
        sub = parts[1].lower()
        if sub == "list":
            category = " ".join(parts[2:]).strip() if len(parts) > 2 else self._state.active_category
            names = [p.name for p in self._library.playlists(category=category if category else None)]
            if self._smart_playlists_enabled():
                for smart in ("Recently Played", "Most Played"):
                    if smart not in names:
                        names.append(smart)
            self._state.playlists = names
            self._set_status(f"Playlists ({category or 'all'}): {', '.join(names) if names else '(none)'}")
            return

        if sub == "create":
            if len(parts) < 3:
                self._set_error("Usage: playlist create <name> [category]")
                return
            name = parts[2]
            category = parts[3] if len(parts) > 3 else self._state.active_category or "General"
            self._library.ensure_playlist(name=name, category=category)
            self._refresh_library_state()
            self._set_status(f"Playlist created: {name}")
            return

        if sub == "use":
            if len(parts) < 3:
                self._set_error("Usage: playlist use <name>")
                return
            self._state.active_playlist = parts[2]
            self._set_status(f"Active playlist: {self._state.active_playlist}")
            return

        if sub == "load":
            if len(parts) < 3:
                self._set_error("Usage: playlist load <name>")
                return
            name = parts[2]
            tracks = self._library.playlist_tracks(name)
            if not tracks:
                self._set_error(f"Playlist empty or missing: {name}")
                return
            self._queue.clear()
            self._queue.extend(tracks)
            self._queue.set_index(0)
            self._state.active_playlist = name
            self._play_track(tracks[0], 0)
            self._set_status(f"Loaded playlist '{name}' ({len(tracks)} tracks).")
            return

        if sub == "show":
            if len(parts) < 3:
                self._set_error("Usage: playlist show <name>")
                return
            name = parts[2]
            tracks = self._library.playlist_tracks(name)
            self._set_status(f"Playlist '{name}' tracks: {len(tracks)}")
            return

        if sub == "delete":
            if len(parts) < 3:
                self._set_error("Usage: playlist delete <name>")
                return
            name = parts[2]
            if not self._library.delete_playlist(name):
                self._set_error(f"Playlist not found: {name}")
                return
            if self._state.active_playlist.lower() == name.lower():
                self._state.active_playlist = str(self._get_cfg("library.default_playlist", "Liked Songs"))
            self._refresh_library_state()
            self._set_status(f"Deleted playlist: {name}")
            return

        if sub == "rename":
            if len(parts) < 4:
                self._set_error("Usage: playlist rename <old> <new>")
                return
            if not self._library.rename_playlist(parts[2], parts[3]):
                self._set_error("Could not rename playlist.")
                return
            if self._state.active_playlist.lower() == parts[2].lower():
                self._state.active_playlist = parts[3]
            self._refresh_library_state()
            self._set_status(f"Renamed playlist: {parts[2]} -> {parts[3]}")
            return

        if sub == "add":
            if len(parts) < 3:
                self._set_error("Usage: playlist add <name> [current|search-index]")
                return
            track = self._resolve_track_ref(parts[3] if len(parts) > 3 else "current")
            if track is None:
                self._set_error("Track reference not found.")
                return
            category = self._state.active_category or "General"
            if not self._library.add_track_to_playlist(parts[2], track, category=category):
                self._set_status("Track already present in playlist.")
                return
            self._refresh_library_state()
            self._set_status(f"Added to playlist '{parts[2]}': {track.label()}")
            return

        self._set_error("Unknown playlist subcommand.")

    def command_category(self, parts: list[str]) -> None:
        if len(parts) < 2:
            self._set_error("Usage: category list|add|use")
            return
        sub = parts[1].lower()
        if sub == "list":
            self._refresh_library_state()
            self._set_status(f"Categories: {', '.join(self._state.categories)}")
            return

        if sub == "add":
            if len(parts) < 3:
                self._set_error("Usage: category add <name>")
                return
            if not self._library.add_category(parts[2]):
                self._set_error(f"Category exists or invalid: {parts[2]}")
                return
            self._refresh_library_state()
            self._set_status(f"Category added: {parts[2]}")
            return

        if sub == "use":
            if len(parts) < 3:
                self._set_error("Usage: category use <name>")
                return
            name = parts[2]
            if name not in self._library.categories():
                self._set_error(f"Unknown category: {name}")
                return
            self._state.active_category = name
            self._set_cfg("library.default_category", name)
            self._refresh_library_state()
            self._safe_save_config()
            self._set_status(f"Active category: {name}")
            return

        self._set_error("Unknown category subcommand.")

    def add_current_to_active_playlist(self) -> None:
        current = self._state.current_track
        if current is None:
            self._set_error("No current track to add.")
            return
        playlist = self._state.active_playlist or str(self._get_cfg("library.default_playlist", "Liked Songs"))
        category = self._state.active_category or str(self._get_cfg("library.default_category", "General"))
        if not self._library.add_track_to_playlist(playlist, current, category=category):
            self._set_status("Track already in playlist.")
            return
        self._refresh_library_state()
        self._set_status(f"Saved to playlist '{playlist}'.")
