from __future__ import annotations

import re
from dataclasses import dataclass

from ..utils.helpers import clamp

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class BorderChars:
    tl: str
    tr: str
    bl: str
    br: str
    h: str
    v: str


BORDER_PRESETS: dict[str, BorderChars] = {
    "single": BorderChars("┌", "┐", "└", "┘", "─", "│"),
    "double": BorderChars("╔", "╗", "╚", "╝", "═", "║"),
    "rounded": BorderChars("╭", "╮", "╰", "╯", "─", "│"),
    "heavy": BorderChars("┏", "┓", "┗", "┛", "━", "┃"),
    "ascii": BorderChars("+", "+", "+", "+", "-", "|"),
}


def format_time(seconds: float) -> str:
    total = int(max(0.0, seconds))
    minutes, sec = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"
    return f"{minutes:02d}:{sec:02d}"


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    return len(strip_ansi(text))


def truncate(text: str, width: int) -> str:
    width = max(1, width)
    if visible_len(text) <= width:
        return text
    plain = strip_ansi(text)
    if width <= 3:
        return plain[:width]
    return plain[: width - 3] + "..."


def pad_visible(text: str, width: int) -> str:
    clean = truncate(text, width)
    remaining = width - visible_len(clean)
    if remaining <= 0:
        return clean
    return clean + (" " * remaining)


def render_progress_bar(
    position: float,
    duration: float,
    width: int,
    fill_char: str = "█",
    empty_char: str = "░",
) -> str:
    width = max(10, width)
    if duration <= 0:
        ratio = 0.0
    else:
        ratio = clamp(position / duration, 0.0, 1.0)
    filled = int(width * ratio)
    return "[" + (fill_char * filled) + (empty_char * (width - filled)) + "]"


def box(title: str, lines: list[str], width: int, border_type: str = "single") -> list[str]:
    width = max(24, width)
    border = BORDER_PRESETS.get(border_type, BORDER_PRESETS["single"])
    inner_width = width - 2

    title_trimmed = truncate(title, max(1, inner_width - 2))
    title_block = f" {title_trimmed} "
    top = border.tl + title_block + (border.h * max(0, inner_width - len(title_block))) + border.tr
    body = [f"{border.v}{pad_visible(line, inner_width)}{border.v}" for line in lines]
    bottom = border.bl + (border.h * inner_width) + border.br
    return [top, *body, bottom]


def combine_columns(left: list[str], right: list[str], total_width: int, gap: int = 2) -> list[str]:
    total_width = max(40, total_width)
    gap = max(1, gap)
    left_width = (total_width - gap) // 2
    right_width = total_width - gap - left_width

    rows = max(len(left), len(right))
    lines: list[str] = []
    for i in range(rows):
        left_line = left[i] if i < len(left) else ""
        right_line = right[i] if i < len(right) else ""
        lines.append(f"{pad_visible(left_line, left_width)}{' ' * gap}{pad_visible(right_line, right_width)}")
    return lines


def panelize(title: str, lines: list[str], width: int, border_type: str = "single") -> list[str]:
    return box(title=title, lines=lines, width=width, border_type=border_type)
