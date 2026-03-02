from importlib import import_module
from pathlib import Path
import os

Renderer = import_module("pulsewave-11.ui.renderer").Renderer
ThemeManager = import_module("pulsewave-11.ui.themes").ThemeManager
VisualizerEngine = import_module("pulsewave-11.ui.visualizer").VisualizerEngine
AppState = import_module("pulsewave-11.core.state").AppState
QueueSnapshot = import_module("pulsewave-11.core.queue").QueueSnapshot


def _render_for_size(monkeypatch, columns: int, rows: int) -> str:
    renderer_module = import_module("pulsewave-11.ui.renderer")
    monkeypatch.setattr(renderer_module.shutil, "get_terminal_size", lambda _fallback: os.terminal_size((columns, rows)))

    manager = ThemeManager(Path("themes"))
    renderer = Renderer(
        theme_manager=manager,
        theme=manager.load_theme("default"),
        visualizer=VisualizerEngine(bars=16, smoothing=0.5),
        color_mode="off",
    )
    state = AppState()
    return renderer.render(state, QueueSnapshot(items=[], index=-1), [])


def test_renderer_uses_split_layout_on_wide_terminal(monkeypatch) -> None:
    output = _render_for_size(monkeypatch, columns=132, rows=32)
    lines = output.splitlines()
    assert any("Queue" in line and "Discover" in line for line in lines)


def test_renderer_uses_stacked_layout_on_tall_terminal(monkeypatch) -> None:
    output = _render_for_size(monkeypatch, columns=90, rows=60)
    lines = output.splitlines()
    assert not any("Queue" in line and "Discover" in line for line in lines)
    queue_index = next(i for i, line in enumerate(lines) if "Queue" in line)
    discover_index = next(i for i, line in enumerate(lines) if "Discover" in line)
    assert discover_index > queue_index


def test_renderer_uses_compact_layout_on_narrow_terminal(monkeypatch) -> None:
    output = _render_for_size(monkeypatch, columns=62, rows=28)
    assert "Shell  :" in output
    assert "settings alias events" in output
    assert "[j/k/l/u]" in output
