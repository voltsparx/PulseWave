from __future__ import annotations

import math
import time
from typing import Sequence

from ..utils.helpers import clamp

try:
    import pulsewave_11_native as _native_dsp  # type: ignore
except Exception:  # pragma: no cover - optional native extension
    try:
        import pulsewave_native as _native_dsp  # type: ignore
    except Exception:  # pragma: no cover - optional native extension
        _native_dsp = None

DEFAULT_LEVELS = "▁▂▃▄▅▆▇█"
VISUALIZER_MODES = ("bars", "waveform", "centered", "pulse")


class VisualizerEngine:
    def __init__(
        self,
        bars: int = 24,
        smoothing: float = 0.65,
        levels: str = DEFAULT_LEVELS,
        mode: str = "bars",
        sensitivity: float = 1.0,
        fps_limit: int = 24,
        auto_hide_paused: bool = True,
    ) -> None:
        self.bars = max(4, bars)
        self.smoothing = clamp(smoothing, 0.0, 0.99)
        self.levels = levels or DEFAULT_LEVELS
        self.mode = mode if mode in VISUALIZER_MODES else "bars"
        self.sensitivity = clamp(sensitivity, 0.1, 3.0)
        self.fps_limit = max(5, min(int(fps_limit), 120))
        self.auto_hide_paused = bool(auto_hide_paused)
        self._previous: list[float] = [0.0] * self.bars
        self._last_render_at = 0.0
        self._last_bars: list[int] = [0] * self.bars

    def compute_bars(self, samples: Sequence[float], *, playing: bool = True) -> list[int]:
        if not playing and self.auto_hide_paused:
            self._last_bars = [0] * self.bars
            return list(self._last_bars)

        now = time.monotonic()
        interval = 1.0 / max(1, self.fps_limit)
        if now - self._last_render_at < interval and self._last_bars:
            return list(self._last_bars)
        self._last_render_at = now

        if not samples:
            self._last_bars = [0] * self.bars
            return list(self._last_bars)

        values = self._compute_values(samples)

        peak = max(values) or 1.0
        normalized = [value / peak for value in values]

        smoothed: list[float] = []
        for i, value in enumerate(normalized):
            previous = self._previous[i]
            smoothed_value = max(value, previous * self.smoothing)
            smoothed.append(smoothed_value)
        self._previous = smoothed

        scale = len(self.levels) - 1
        output = [int(clamp(v * scale, 0, scale)) for v in smoothed]
        self._last_bars = output
        return list(output)

    def _compute_values(self, samples: Sequence[float]) -> list[float]:
        if self.mode == "bars":
            native = self._compute_values_native(samples)
            if native is not None:
                return native

        chunk_size = max(1, len(samples) // self.bars)
        values: list[float] = []
        for i in range(self.bars):
            segment = samples[i * chunk_size : (i + 1) * chunk_size]
            if not segment:
                values.append(0.0)
                continue
            if self.mode in {"waveform", "centered"}:
                value = sum(abs(value) for value in segment) / len(segment)
            else:
                energy = sum(value * value for value in segment) / len(segment)
                value = math.sqrt(energy)
            values.append(value * self.sensitivity)
        return values

    def _compute_values_native(self, samples: Sequence[float]) -> list[float] | None:
        if _native_dsp is None:
            return None
        try:
            values = _native_dsp.compute_fft_bins(samples, int(self.bars))
        except Exception:
            return None
        if not values or len(values) != self.bars:
            return None
        return [float(value) * self.sensitivity for value in values]

    def compute_signal_stats(self, samples: Sequence[float]) -> tuple[float, float, float]:
        if not samples:
            return (0.0, 0.0, 0.0)
        if _native_dsp is not None:
            try:
                values = _native_dsp.compute_signal_stats(samples)
                if isinstance(values, list) and len(values) >= 3:
                    return (float(values[0]), float(values[1]), float(values[2]))
            except Exception:
                pass
        peak = max(abs(float(value)) for value in samples)
        energy = sum(float(value) * float(value) for value in samples) / max(1, len(samples))
        rms = math.sqrt(energy)
        crest = (peak / rms) if rms > 1e-9 else 0.0
        return (rms, peak, crest)

    def render_line(self, bars: Sequence[int], width: int) -> str:
        if not bars:
            return ""
        clipped = list(bars[: max(1, width)])
        return "".join(self.levels[int(clamp(value, 0, len(self.levels) - 1))] for value in clipped)
