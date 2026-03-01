from __future__ import annotations

import shutil
import sys
from typing import Sequence

from pulsewave.core.queue import QueueSnapshot
from pulsewave.core.search import SearchResult
from pulsewave.core.state import AppState
from pulsewave.ui.components import box, combine_columns, format_time, panelize, render_progress_bar, truncate
from pulsewave.ui.themes import Theme, ThemeManager
from pulsewave.ui.visualizer import DEFAULT_LEVELS, VisualizerEngine


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
        self._sync_visualizer_levels()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._sync_visualizer_levels()

    def render(self, state: AppState, queue: QueueSnapshot, search_results: Sequence[SearchResult]) -> str:
        size = shutil.get_terminal_size((100, 38))
        width = max(80, min(size.columns - 2, 140))
        inner_width = width - 2
        utf_mode = self._is_utf_terminal()
        border_type = self.theme.border_type if utf_mode else "ascii"
        fill_char = self.theme.progress_fill if utf_mode else "#"
        empty_char = self.theme.progress_empty if utf_mode else "-"
        header_left = self.theme.header_left if utf_mode else "*"
        header_right = self.theme.header_right if utf_mode else "*"

        if utf_mode:
            self._sync_visualizer_levels()
        else:
            self.visualizer.levels = " .:-=+*#%@"

        current = state.current_track.label() if state.current_track else "Nothing playing"
        status = "Paused" if state.is_paused else ("Playing" if state.is_playing else "Stopped")
        progress = render_progress_bar(
            state.position,
            state.duration,
            width=min(46, max(24, inner_width - 36)),
            fill_char=fill_char,
            empty_char=empty_char,
        )
        time_label = f"{format_time(state.position)} / {format_time(state.duration)}"
        visual_line = self.visualizer.render_line(state.visualizer_bars, width=min(56, max(18, inner_width - 10)))

        queue_box = box(
            title="Queue",
            lines=self._queue_lines(queue, max_lines=self._list_height(size.lines)),
            width=(inner_width - 2) // 2,
            border_type=border_type,
        )
        discover_box = box(
            title="Discover",
            lines=self._search_lines(search_results, max_lines=self._list_height(size.lines)),
            width=inner_width - 2 - ((inner_width - 2) // 2),
            border_type=border_type,
        )
        side_by_side = combine_columns(queue_box, discover_box, total_width=inner_width, gap=2)

        now_playing_box = box(
            title="Now Playing",
            lines=[
                f"Track   : {truncate(current, inner_width - 18)}",
                f"State   : {status:<8}  Volume: {state.volume:>3}%  Repeat: {state.repeat_mode.value:<3}  Shuffle: {'on' if state.shuffle_enabled else 'off'}",
                f"Progress: {progress} {time_label}",
                f"Waveform: {visual_line}",
            ],
            width=inner_width,
            border_type=border_type,
        )

        status_text = state.last_error if state.last_error else state.status_message
        command_box = box(
            title="Command Deck",
            lines=[
                f"Status : {truncate(status_text, inner_width - 12)}",
                "Keys   : [Space]=Play/Pause  n=Next  p=Prev  q=Quit",
                "Shell  : search <q> | play <index> | add <path> | seek <sec> | volume <0-100> | theme <name>",
            ],
            width=inner_width,
            border_type=border_type,
        )

        body: list[str] = [
            f"{header_left} PulseWave v0.1  •  Theme: {self.theme.name}  •  Mode: {self.color_mode}  •  Source: {state.current_track.source if state.current_track else '-'} {header_right}",
            "",
            *now_playing_box,
            "",
            *side_by_side,
            "",
            *command_box,
        ]

        frame = panelize("PulseWave Console", body, width=width, border_type=border_type)
        styled = self._style_lines(frame, state=state, visual_line=visual_line)
        return "\u001b[2J\u001b[H" + "\n".join(styled)

    def _sync_visualizer_levels(self) -> None:
        levels = self.theme.visualizer_levels or DEFAULT_LEVELS
        self.visualizer.levels = levels

    def _style_lines(self, lines: list[str], state: AppState, visual_line: str) -> list[str]:
        styled: list[str] = []
        for line in lines:
            style_name = self.theme.border_style
            if "PulseWave v0.1" in line or "PulseWave Console" in line:
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

    def _list_height(self, terminal_rows: int) -> int:
        if terminal_rows < 30:
            return 4
        if terminal_rows < 40:
            return 6
        return 8

    def _queue_lines(self, queue: QueueSnapshot, max_lines: int) -> list[str]:
        if not queue.items:
            return ["(empty)"]
        lines: list[str] = []
        start = max(0, queue.index - 1)
        end = min(len(queue.items), start + max_lines)
        for i in range(start, end):
            marker = "▶" if i == queue.index else " "
            track = queue.items[i]
            lines.append(f"{marker} {i + 1:02d}. {truncate(track.label(), 40)}")
        return lines

    def _search_lines(self, results: Sequence[SearchResult], max_lines: int) -> list[str]:
        if not results:
            return ["(none)"]
        lines: list[str] = []
        for i, result in enumerate(results[:max_lines], start=1):
            tag = "YT" if result.source == "youtube" else "LO"
            lines.append(f"{i:02d}. [{tag}] {truncate(result.track.label(), 42)}")
        return lines

