from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

RESET = "\u001b[0m"

ANSI_NAMED_CODES = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "bright_black": "90",
    "bright_red": "91",
    "bright_green": "92",
    "bright_yellow": "93",
    "bright_blue": "94",
    "bright_magenta": "95",
    "bright_cyan": "96",
    "bright_white": "97",
}

ANSI_ATTR_CODES = {
    "bold": "1",
    "dim": "2",
    "italic": "3",
    "underline": "4",
    "reverse": "7",
}

TOKEN_ALIASES = {
    "bold_white": "bold bright_white",
    "amber": "color(214)",
}


@dataclass(frozen=True)
class Theme:
    name: str
    border_style: str
    highlight_style: str
    progress_style: str
    visualizer_style: str
    accent_style: str = "bold bright_white"
    muted_style: str = "dim bright_black"
    error_style: str = "bold bright_red"
    border_type: str = "single"
    progress_fill: str = "█"
    progress_empty: str = "░"
    visualizer_levels: str = "▁▂▃▄▅▆▇█"
    header_left: str = "◈"
    header_right: str = "◈"


BUILTIN_THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        border_style="bright_black",
        highlight_style="bold bright_white",
        progress_style="bold bright_white",
        visualizer_style="bright_white",
        accent_style="bold white",
        muted_style="dim bright_black",
        error_style="bold bright_red",
        border_type="rounded",
        progress_fill="█",
        progress_empty="·",
        visualizer_levels="▁▂▃▄▅▆▇█",
        header_left="◈",
        header_right="◈",
    ),
    "blackwhite": Theme(
        name="blackwhite",
        border_style="white",
        highlight_style="bold white",
        progress_style="bold white",
        visualizer_style="white",
        accent_style="bold white",
        muted_style="dim white",
        error_style="reverse white",
        border_type="double",
        progress_fill="■",
        progress_empty="·",
        visualizer_levels=" ▁▂▃▄▅▆▇█",
        header_left="◆",
        header_right="◆",
    ),
    "amber": Theme(
        name="amber",
        border_style="color(214)",
        highlight_style="bold color(214)",
        progress_style="bold color(220)",
        visualizer_style="color(214)",
        accent_style="bold color(220)",
        muted_style="color(178)",
        error_style="bold color(203)",
        border_type="single",
        progress_fill="▰",
        progress_empty="▱",
        visualizer_levels="▁▂▃▄▅▆▇█",
        header_left="◉",
        header_right="◉",
    ),
    "green": Theme(
        name="green",
        border_style="green",
        highlight_style="bold bright_green",
        progress_style="bold bright_green",
        visualizer_style="green",
        accent_style="bold bright_green",
        muted_style="dim green",
        error_style="bold bright_red",
        border_type="single",
        progress_fill="█",
        progress_empty="·",
        visualizer_levels=" ▁▂▃▄▅▆▇█",
        header_left="◼",
        header_right="◼",
    ),
    "ice": Theme(
        name="ice",
        border_style="color(39)",
        highlight_style="bold color(51)",
        progress_style="bold color(45)",
        visualizer_style="color(39)",
        accent_style="bold color(81)",
        muted_style="color(110)",
        error_style="bold color(196)",
        border_type="rounded",
        progress_fill="▮",
        progress_empty="▯",
        visualizer_levels="▁▂▃▄▅▆▇█",
        header_left="◇",
        header_right="◇",
    ),
    "neon_city": Theme(
        name="neon_city",
        border_style="color(45)",
        highlight_style="bold color(51)",
        progress_style="bold #ff4fd8",
        visualizer_style="color(51)",
        accent_style="bold #ff4fd8",
        muted_style="color(117)",
        error_style="bold color(203)",
        border_type="heavy",
        progress_fill="▰",
        progress_empty="▱",
        visualizer_levels=" ▁▂▃▄▅▆▇█",
        header_left="⬢",
        header_right="⬢",
    ),
}


class ThemeManager:
    def __init__(self, theme_dir: Path | None = None) -> None:
        self.theme_dir = theme_dir

    def available_themes(self) -> list[str]:
        names = set(BUILTIN_THEMES)
        if self.theme_dir and self.theme_dir.exists():
            for path in self.theme_dir.glob("*.yaml"):
                names.add(path.stem)
        return sorted(names)

    def load_theme(self, name: str) -> Theme:
        key = name.lower().strip()
        if key in BUILTIN_THEMES:
            return BUILTIN_THEMES[key]
        if self.theme_dir:
            candidate = self.theme_dir / f"{key}.yaml"
            if candidate.exists():
                parsed = _parse_yaml(candidate)
                return Theme(
                    name=key,
                    border_style=parsed.get("border_style", "bright_black"),
                    highlight_style=parsed.get("highlight_style", "bold bright_white"),
                    progress_style=parsed.get("progress_style", "bold bright_white"),
                    visualizer_style=parsed.get("visualizer_style", "bright_white"),
                    accent_style=parsed.get("accent_style", "bold bright_white"),
                    muted_style=parsed.get("muted_style", "dim bright_black"),
                    error_style=parsed.get("error_style", "bold bright_red"),
                    border_type=parsed.get("border_type", "single"),
                    progress_fill=_single_char(parsed.get("progress_fill"), fallback="█"),
                    progress_empty=_single_char(parsed.get("progress_empty"), fallback="░"),
                    visualizer_levels=parsed.get("visualizer_levels", "▁▂▃▄▅▆▇█"),
                    header_left=_single_char(parsed.get("header_left"), fallback="◈"),
                    header_right=_single_char(parsed.get("header_right"), fallback="◈"),
                )
        return BUILTIN_THEMES["default"]

    def style(self, text: str, style_name: str, color_mode: str) -> str:
        if color_mode == "off" or os.getenv("NO_COLOR"):
            return text
        sgr = _compile_style(style_name, color_mode=color_mode)
        if not sgr:
            return text
        return f"\u001b[{sgr}m{text}{RESET}"


def _compile_style(style_name: str, color_mode: str) -> Optional[str]:
    expanded_tokens: list[str] = []
    for raw in style_name.split():
        alias = TOKEN_ALIASES.get(raw.strip().lower())
        if alias:
            expanded_tokens.extend(alias.split())
        else:
            expanded_tokens.append(raw)

    tokens = [t.strip().lower() for t in expanded_tokens if t.strip()]
    if not tokens:
        return None

    codes: list[str] = []
    fg_set = False
    bg_set = False

    for token in tokens:
        if token in ANSI_ATTR_CODES:
            codes.append(ANSI_ATTR_CODES[token])
            continue

        is_bg = token.startswith("bg:")
        color_token = token[3:] if is_bg else token

        color_code = _color_token_to_sgr(color_token, color_mode=color_mode, background=is_bg)
        if color_code:
            if is_bg:
                if not bg_set:
                    codes.append(color_code)
                    bg_set = True
            else:
                if not fg_set:
                    codes.append(color_code)
                    fg_set = True

    if not codes:
        return None
    return ";".join(codes)


def _color_token_to_sgr(token: str, color_mode: str, background: bool) -> Optional[str]:
    named = ANSI_NAMED_CODES.get(token)
    if named:
        if background:
            if named.startswith("9"):
                return str(100 + (int(named) - 90))
            return str(40 + (int(named) - 30))
        return named

    if color_mode != "full":
        return None

    color_index_match = re.fullmatch(r"color\((\d{1,3})\)", token)
    if color_index_match:
        value = int(color_index_match.group(1))
        value = max(0, min(value, 255))
        return f"{48 if background else 38};5;{value}"

    if re.fullmatch(r"#[0-9a-f]{6}", token):
        r = int(token[1:3], 16)
        g = int(token[3:5], 16)
        b = int(token[5:7], 16)
        return f"{48 if background else 38};2;{r};{g};{b}"

    return None


def _single_char(value: Optional[str], fallback: str) -> str:
    if not value:
        return fallback
    return value[0]


def _parse_yaml(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip("'\"")
    return parsed
