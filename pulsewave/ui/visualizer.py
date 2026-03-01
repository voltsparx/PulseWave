from __future__ import annotations

import math
from typing import Sequence

from pulsewave.utils.helpers import clamp

DEFAULT_LEVELS = "▁▂▃▄▅▆▇█"


class VisualizerEngine:
    def __init__(self, bars: int = 24, smoothing: float = 0.65, levels: str = DEFAULT_LEVELS) -> None:
        self.bars = max(4, bars)
        self.smoothing = clamp(smoothing, 0.0, 0.99)
        self.levels = levels or DEFAULT_LEVELS
        self._previous: list[float] = [0.0] * self.bars

    def compute_bars(self, samples: Sequence[float]) -> list[int]:
        if not samples:
            return [0] * self.bars

        chunk_size = max(1, len(samples) // self.bars)
        rms_values: list[float] = []
        for i in range(self.bars):
            segment = samples[i * chunk_size : (i + 1) * chunk_size]
            if not segment:
                rms_values.append(0.0)
                continue
            energy = sum(value * value for value in segment) / len(segment)
            rms_values.append(math.sqrt(energy))

        peak = max(rms_values) or 1.0
        normalized = [value / peak for value in rms_values]

        smoothed: list[float] = []
        for i, value in enumerate(normalized):
            previous = self._previous[i]
            smoothed_value = max(value, previous * self.smoothing)
            smoothed.append(smoothed_value)
        self._previous = smoothed

        scale = len(self.levels) - 1
        return [int(clamp(v * scale, 0, scale)) for v in smoothed]

    def render_line(self, bars: Sequence[int], width: int) -> str:
        if not bars:
            return ""
        clipped = list(bars[: max(1, width)])
        return "".join(self.levels[int(clamp(value, 0, len(self.levels) - 1))] for value in clipped)

