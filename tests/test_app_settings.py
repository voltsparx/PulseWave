from importlib import import_module
from pathlib import Path

PulseWave11App = import_module("pulsewave-11.app").PulseWave11App


def test_settings_command_opens_panel(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("settings")

    assert app.state.show_settings is True
    assert "Settings panel opened" in app.state.status_message
