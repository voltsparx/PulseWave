from pathlib import Path

from pulsewave.ui.themes import ThemeManager


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

