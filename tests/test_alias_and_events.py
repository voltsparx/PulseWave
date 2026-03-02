from importlib import import_module
from pathlib import Path

PulseWave11App = import_module("pulsewave-11.app").PulseWave11App


def test_alias_set_and_execute(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("alias set opensettings settings show")
    app.handle_input("opensettings")

    assert app.state.show_settings is True
    assert "shown" in app.state.status_message.lower()


def test_alias_args_and_chain(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("alias set getcfg settings get {args}")
    app.handle_input("getcfg theme")
    assert "theme =" in app.state.status_message

    app.handle_input("alias set panelflip settings show && settings hide")
    app.handle_input("panelflip")
    assert app.state.show_settings is False


def test_alias_loop_detection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("alias set a b")
    app.handle_input("alias set b a")
    app.handle_input("a")

    assert "Alias loop detected" in app.state.last_error


def test_event_log_trim_and_clear(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app._set_cfg("ui.event_log_size", 3)
    app._apply_runtime_key("ui.event_log_size")
    for idx in range(6):
        app._set_status(f"evt-{idx}")

    assert len(app.state.event_log) == 3
    assert "evt-5" in app.state.event_log[-1]

    app.handle_input("events clear")
    assert len(app.state.event_log) == 1
    assert "Event log cleared." in app.state.event_log[-1]
