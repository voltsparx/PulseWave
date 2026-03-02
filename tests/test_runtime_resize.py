from importlib import import_module
from pathlib import Path
import os

app_module = import_module("pulsewave-11.app")
PulseWave11App = app_module.PulseWave11App


def test_poll_terminal_resize_forces_render(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    sizes = [os.terminal_size((100, 38)), os.terminal_size((120, 30))]

    def _next_size(_fallback: tuple[int, int]) -> os.terminal_size:
        if sizes:
            return sizes.pop(0)
        return os.terminal_size((120, 30))

    monkeypatch.setattr(app_module.shutil, "get_terminal_size", _next_size)
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app._force_render = False
    app._last_render_payload = "cached"

    app._poll_terminal_resize()

    assert app._force_render is True
    assert app._last_render_payload == ""


def test_poll_terminal_resize_no_change_keeps_cache(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    monkeypatch.setattr(app_module.shutil, "get_terminal_size", lambda _fallback: os.terminal_size((100, 38)))

    app = PulseWave11App(config_path=tmp_path / "config.json")
    app._force_render = False
    app._last_render_payload = "cached"

    app._poll_terminal_resize()

    assert app._force_render is False
    assert app._last_render_payload == "cached"
