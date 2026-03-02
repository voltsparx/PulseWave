from importlib import import_module
from pathlib import Path

KeyBindings = import_module("pulsewave-11.ui.keybinds").KeyBindings
PulseWave11App = import_module("pulsewave-11.app").PulseWave11App


def test_keybinding_chain_parsing() -> None:
    keys = KeyBindings.from_config({"!": "volume_up|seek_forward,help"})
    assert keys.actions_for("!") == ["volume_up", "seek_forward", "help"]
    assert keys.action_for("!") == "volume_up"


def test_action_chain_executes_in_order(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    initial_volume = app.state.volume
    app.keybinds.mapping["!"] = ["volume_up", "volume_up"]
    app.handle_input("!")

    assert app.state.volume == min(100, initial_volume + (2 * app._volume_step()))
