from importlib import import_module
from pathlib import Path

ConfigManager = import_module("pulsewave-11.core.config").ConfigManager


def test_default_config_includes_ui_controls(tmp_path: Path) -> None:
    manager = ConfigManager(path=tmp_path / "config.json")
    cfg = manager.load()

    assert cfg["ui"]["use_symbols"] is True
    assert cfg["ui"]["show_recently_played"] is True
    assert cfg["ui"]["show_command_hints"] is True
    assert cfg["ui"]["event_log_size"] == 40
    assert cfg["command_aliases"] == {}
    assert cfg["performance"]["show_panel"] is False
    assert cfg["lyrics"]["enabled"] is True
    assert cfg["plugins"]["enabled"] == []
    assert cfg["lan_stream"]["port"] == 8765
    assert cfg["visualizer"]["custom_levels"] == ""
    assert cfg["visualizer"]["presets"] == {}


def test_default_keybindings_include_quick_polish_actions(tmp_path: Path) -> None:
    manager = ConfigManager(path=tmp_path / "config.json")
    cfg = manager.load()
    keys = cfg["keybindings"]

    assert keys["."] == "speed_up"
    assert keys[";"] == "speed_down"
    assert keys["x"] == "cycle_repeat"
    assert keys["z"] == "toggle_shuffle"
    assert keys["t"] == "cycle_theme"
    assert keys["g"] == "cycle_color_mode"
    assert keys["f"] == "cycle_visualizer_mode"
