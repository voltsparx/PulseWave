from pathlib import Path

from importlib import import_module

ThemeManager = import_module("pulsewave-11.ui.themes").ThemeManager


def test_load_black_white_theme_from_yaml() -> None:
    manager = ThemeManager(Path("themes"))
    theme = manager.load_theme("black_white")
    assert theme.border_type == "double"
    assert theme.progress_fill == "■"


def test_full_mode_supports_256_color() -> None:
    manager = ThemeManager(Path("themes"))
    styled = manager.style("x", "bold color(214)", color_mode="full")
    assert "\u001b[" in styled
    assert "38;5;214" in styled


def test_basic_mode_ignores_256_color_but_keeps_attrs() -> None:
    manager = ThemeManager(Path("themes"))
    styled = manager.style("x", "bold color(214)", color_mode="basic")
    assert "\u001b[" in styled
    assert "38;5;214" not in styled


def test_theme_supports_symbol_overrides() -> None:
    manager = ThemeManager(Path("themes"))
    theme = manager.load_theme("black_white")
    assert theme.playing_icon == ">"
    assert theme.queue_active_marker == ">"


def test_yaml_overrides_builtin_theme_fields() -> None:
    manager = ThemeManager(Path("themes"))
    theme = manager.load_theme("neon_city")
    assert theme.playing_icon == "▷"
    assert theme.accent_divider == "✦"
