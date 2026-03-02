from __future__ import annotations

import shutil
import sys
from typing import Sequence

from .. import __version__
from ..core.queue import QueueSnapshot
from ..core.search import SearchResult
from ..core.state import AppState
from .components import box, combine_columns, format_time, panelize, render_progress_bar, truncate
from .themes import Theme, ThemeManager
from .visualizer import DEFAULT_LEVELS, VisualizerEngine


class Renderer:
    def __init__(
        self,
        theme_manager: ThemeManager,
        theme: Theme,
        visualizer: VisualizerEngine,
        color_mode: str = "off",
    ) -> None:
        self.theme_manager = theme_manager
        self.theme = theme
        self.visualizer = visualizer
        self.color_mode = color_mode
        self.visualizer_levels_override: str | None = None
        self._sync_visualizer_levels()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._sync_visualizer_levels()

    def set_visualizer_levels_override(self, levels: str | None) -> None:
        cleaned = (levels or "").strip()
        self.visualizer_levels_override = cleaned if len(cleaned) >= 2 else None
        self._sync_visualizer_levels()

    def render(self, state: AppState, queue: QueueSnapshot, search_results: Sequence[SearchResult]) -> str:
        size = shutil.get_terminal_size((100, 38))
        terminal_columns = max(48, size.columns)
        terminal_rows = max(18, size.lines)
        width = max(42, min(terminal_columns - 2, 140))
        inner_width = max(40, width - 2)
        layout = self._layout_mode(columns=terminal_columns, rows=terminal_rows, inner_width=inner_width)
        utf_mode = self._is_utf_terminal()
        use_symbols = utf_mode and state.ui_symbols
        border_type = self.theme.border_type if utf_mode else "ascii"
        fill_char = self.theme.progress_fill if utf_mode else "#"
        empty_char = self.theme.progress_empty if utf_mode else "-"
        header_left = self.theme.header_left if use_symbols else "*"
        header_right = self.theme.header_right if use_symbols else "*"

        if utf_mode:
            self._sync_visualizer_levels()
        else:
            self.visualizer.levels = self.visualizer_levels_override or " .:-=+*#%@"

        current = state.current_track.label() if state.current_track else "Nothing playing"
        album = state.current_track.album if state.current_track and state.current_track.album else "-"
        fmt = state.current_track.file_format.upper() if state.current_track and state.current_track.file_format else "-"
        bitrate = f"{state.current_track.bitrate_kbps}kbps" if state.current_track and state.current_track.bitrate_kbps > 0 else "-"
        if state.is_paused:
            status_icon = self.theme.paused_icon if use_symbols else "||"
            status = f"{status_icon} Paused"
        elif state.is_playing:
            status_icon = self.theme.playing_icon if use_symbols else ">"
            status = f"{status_icon} Playing"
        else:
            status_icon = self.theme.stopped_icon if use_symbols else "[]"
            status = f"{status_icon} Stopped"
        progress_min = 14 if layout == "compact" else 24
        progress = render_progress_bar(
            state.position,
            state.duration,
            width=min(46, max(progress_min, inner_width - (26 if layout == "compact" else 36))),
            fill_char=fill_char,
            empty_char=empty_char,
        )
        time_label = f"{format_time(state.position)} / {format_time(state.duration)}"
        visual_line = self.visualizer.render_line(
            state.visualizer_bars,
            width=min(56, max(12 if layout == "compact" else 18, inner_width - 10)),
        )

        panel_gap = 2
        split_width = inner_width - panel_gap
        queue_panel_width = max(24, split_width // 2 if layout == "split" else inner_width)
        discover_panel_width = max(24, split_width - queue_panel_width if layout == "split" else inner_width)
        list_height = self._list_height(terminal_rows, layout)

        queue_box = box(
            title="Queue",
            lines=self._queue_lines(
                queue,
                max_lines=list_height,
                use_symbols=use_symbols,
                line_width=max(18, queue_panel_width - 8),
            ),
            width=queue_panel_width,
            border_type=border_type,
        )
        discover_box = box(
            title="Discover",
            lines=self._discover_lines(
                state,
                search_results,
                max_lines=list_height + (4 if layout == "compact" else (8 if layout == "split" else 6)),
                use_symbols=use_symbols,
                line_width=max(18, discover_panel_width - 8),
            ),
            width=discover_panel_width,
            border_type=border_type,
        )
        if layout == "split":
            library_section = combine_columns(queue_box, discover_box, total_width=inner_width, gap=panel_gap)
        else:
            library_section = [*queue_box, "", *discover_box]
        divider = self.theme.accent_divider if use_symbols else "|"

        if layout == "compact":
            now_lines = [
                f"Track   : {truncate(current, inner_width - 18)}",
                f"State   : {status:<10}  Vol:{state.volume:>3}%  Spd:{state.playback_speed:>4.2f}x",
                f"Repeat  : {state.repeat_mode.value:<3}  Shuffle:{'on' if state.shuffle_enabled else 'off'}  Viz:{state.visualizer_mode}",
                f"Progress: {progress} {time_label}",
                f"Waveform: {visual_line}",
            ]
            if state.current_lyric_line:
                now_lines.append(f"Lyrics  : {truncate(state.current_lyric_line, inner_width - 18)}")
        else:
            now_lines = [
                f"Track   : {truncate(current, inner_width - 18)}",
                f"Album   : {truncate(album, inner_width - 18)}",
                f"State   : {status:<12}  Volume: {state.volume:>3}%  Speed: {state.playback_speed:>4.2f}x  Repeat: {state.repeat_mode.value:<3}  Shuffle: {'on' if state.shuffle_enabled else 'off'}",
                f"Format  : {fmt:<6}  Bitrate: {bitrate:<8}  Visualizer: {state.visualizer_mode}",
                f"Signal  : RMS={state.signal_rms:>5.3f}  Peak={state.signal_peak:>5.3f}  Crest={state.signal_crest:>4.2f}",
                f"Progress: {progress} {time_label}",
                f"Waveform: {visual_line}",
            ]
            if state.current_lyric_line:
                now_lines.append(f"Lyrics  : {truncate(state.current_lyric_line, inner_width - 18)}")
            if state.ascii_thumbnail:
                now_lines.append("Art:")
                now_lines.extend([f"  {truncate(line, inner_width - 6)}" for line in state.ascii_thumbnail[:4]])
        now_playing_box = box(
            title="Now Playing",
            lines=now_lines,
            width=inner_width,
            border_type=border_type,
        )

        status_text = state.last_error if state.last_error else state.status_message
        if layout == "compact":
            command_lines = [
                f"Status : {truncate(status_text, inner_width - 12)}",
                "Keys   : [Space] [n/p] [s] [m] [+/-] [[]/]] [/] [q]",
                f"Quick  : [.] [;] [x] [z] [t] [g] [f] {divider} [,] [j/k/l/u] [A]",
                "Shell  : search play playlist settings alias events vizpreset script perf quit",
            ]
        else:
            command_lines = [
                f"Status : {truncate(status_text, inner_width - 12)}",
                f"Keys   : [Space] play/pause  [p/n] prev-next  [s] stop  [m] mute  [+/-] volume  [[]/]] seek",
                f"Quick  : [.] speed+  [;] speed-  [x] repeat  [z] shuffle  [t] theme  [g] color  [f] viz {divider} [/] search  [A] like",
                "Shell  : search/play/add/speed/playlist/category/settings/alias/events/vizpreset/lyrics/plugins/snapshot/script/perf/lanstream/theme/keymap/status/backends/config-home/quit",
            ]
        settings_limit = 5 if layout == "compact" else 8
        hints_limit = 3 if layout == "compact" else 5
        events_limit = 2 if layout == "compact" else 4
        if state.show_settings and state.settings_preview:
            command_lines.append("")
            command_lines.append("Settings:")
            command_lines.extend(state.settings_preview[:settings_limit])
        if state.ui_show_hints and state.command_suggestions:
            command_lines.append("")
            command_lines.append("Hints:")
            command_lines.extend(state.command_suggestions[:hints_limit])
        if state.event_log:
            command_lines.append("")
            command_lines.append("Events:")
            for item in state.event_log[-events_limit:]:
                command_lines.append(truncate(item, inner_width - 6))
        if state.show_perf_panel:
            command_lines.append("")
            command_lines.append(
                f"Perf   : CPU={state.perf_cpu_percent:5.1f}%  RAM={state.perf_memory_mb:6.1f} MB  Frame={state.perf_frame_ms:5.1f} ms"
            )
        if state.lan_stream_status:
            command_lines.append("")
            command_lines.append(f"LAN    : {truncate(state.lan_stream_status, inner_width - 10)}")

        command_box = box(
            title="Command Deck",
            lines=command_lines,
            width=inner_width,
            border_type=border_type,
        )

        body: list[str] = [
            f"{header_left} PulseWave-11 v{__version__}  {divider}  Theme: {self.theme.name}  {divider}  Mode: {self.color_mode}  {divider}  Source: {state.current_track.source if state.current_track else '-'} {header_right}",
            "",
            *now_playing_box,
            "",
            *library_section,
            "",
            *command_box,
        ]

        frame = panelize("PulseWave-11 Console", body, width=width, border_type=border_type)
        styled = self._style_lines(frame, state=state, visual_line=visual_line)
        return "\n".join(styled)

    def _sync_visualizer_levels(self) -> None:
        levels = self.visualizer_levels_override or self.theme.visualizer_levels or DEFAULT_LEVELS
        self.visualizer.levels = levels

    def _style_lines(self, lines: list[str], state: AppState, visual_line: str) -> list[str]:
        styled: list[str] = []
        for line in lines:
            style_name = self.theme.border_style
            if "PulseWave-11 v" in line or "PulseWave-11 Console" in line:
                style_name = self.theme.accent_style
            elif "Track   :" in line or "State   :" in line:
                style_name = self.theme.highlight_style
            elif "Progress:" in line:
                style_name = self.theme.progress_style
            elif "Waveform:" in line or visual_line in line:
                style_name = self.theme.visualizer_style
            elif "Status :" in line:
                style_name = self.theme.error_style if state.last_error else self.theme.muted_style
            elif "Keys   :" in line or "Shell  :" in line:
                style_name = self.theme.muted_style

            styled.append(self.theme_manager.style(line, style_name, self.color_mode))
        return styled

    def _is_utf_terminal(self) -> bool:
        encoding = (sys.stdout.encoding or "").lower()
        return "utf" in encoding

    def _layout_mode(self, columns: int, rows: int, inner_width: int) -> str:
        aspect = columns / max(rows, 1)
        if inner_width < 64:
            return "compact"
        if inner_width >= 96 and aspect >= 1.3:
            return "split"
        if inner_width >= 80 and aspect >= 1.55:
            return "split"
        return "stacked"

    def _list_height(self, terminal_rows: int, layout: str) -> int:
        if terminal_rows < 24:
            base = 4
        elif terminal_rows < 32:
            base = 6
        elif terminal_rows < 42:
            base = 8
        else:
            base = 10
        if layout == "compact":
            return max(3, base - 3)
        if layout == "stacked":
            return max(4, base - 1)
        return base

    def _queue_lines(self, queue: QueueSnapshot, max_lines: int, use_symbols: bool, line_width: int = 40) -> list[str]:
        if not queue.items:
            return ["(empty)"]
        lines: list[str] = []
        start = max(0, queue.index - 1)
        end = min(len(queue.items), start + max_lines)
        for i in range(start, end):
            active_marker = self.theme.queue_active_marker if use_symbols else ">"
            idle_marker = self.theme.queue_idle_marker if use_symbols else "-"
            marker = active_marker if i == queue.index else idle_marker
            track = queue.items[i]
            lines.append(f"{marker} {i + 1:02d}. {truncate(track.label(), line_width)}")
        return lines

    def _discover_lines(
        self,
        state: AppState,
        results: Sequence[SearchResult],
        max_lines: int,
        use_symbols: bool,
        line_width: int = 42,
    ) -> list[str]:
        lines: list[str] = []
        lines.append(f"Category: {state.active_category}")
        lines.append(f"Playlist: {state.active_playlist or '-'}")
        if state.playlists:
            compact = ", ".join(state.playlists[:3])
            lines.append(f"Lists   : {truncate(compact, max(12, line_width - 6))}")
        if state.categories:
            cats = ", ".join(state.categories[:3])
            lines.append(f"Cats    : {truncate(cats, max(12, line_width - 6))}")
        lines.append("")
        lines.append("Search:")
        if not results:
            lines.append("(none)")
            if state.ui_show_recent and state.recently_played:
                lines.append("")
                lines.append("Recent:")
                prefix = "•" if use_symbols else "*"
                for item in state.recently_played[:3]:
                    lines.append(f"{prefix} {truncate(item, line_width)}")
            return lines[:max_lines]
        for i, result in enumerate(results[:max_lines], start=1):
            if result.source == "youtube":
                tag = "YT"
            elif result.source == "playlist":
                tag = "PL"
            else:
                tag = "LO"
            lines.append(f"{i:02d}. [{tag}] {truncate(result.track.label(), line_width)}")
        return lines[:max_lines]
