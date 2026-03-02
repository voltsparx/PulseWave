from importlib import import_module
from pathlib import Path

PulseWave11App = import_module("pulsewave-11.app").PulseWave11App


def test_key_events_are_dispatched_via_main_queue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    initial_speed = app.state.playback_speed
    app._input_queue.put(("key", "."))
    app._drain_input_queue()

    assert app.state.playback_speed > initial_speed
