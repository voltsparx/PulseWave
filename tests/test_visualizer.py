from importlib import import_module

VisualizerEngine = import_module("pulsewave-11.ui.visualizer").VisualizerEngine


def test_visualizer_output_range() -> None:
    engine = VisualizerEngine(bars=16, smoothing=0.5)
    samples = [(-1.0 + i * 0.01) for i in range(400)]
    bars = engine.compute_bars(samples)
    assert len(bars) == 16
    assert all(0 <= x <= 7 for x in bars)
