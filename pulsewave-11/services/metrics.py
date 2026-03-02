from __future__ import annotations

import os
import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    psutil = None

try:
    import resource  # type: ignore
except Exception:  # pragma: no cover - non-unix fallback
    resource = None


class PerformanceMonitor:
    def __init__(self) -> None:
        self._pid = os.getpid()
        self._proc = psutil.Process(self._pid) if psutil is not None else None
        self._last_cpu_t = time.perf_counter()
        self._last_proc_t = time.process_time()

    def sample(self) -> tuple[float, float]:
        cpu = self._cpu_percent()
        mem = self._memory_mb()
        return cpu, mem

    def _cpu_percent(self) -> float:
        if self._proc is not None:
            try:
                return float(max(0.0, self._proc.cpu_percent(interval=None)))
            except Exception:
                pass
        now = time.perf_counter()
        proc_now = time.process_time()
        dt_wall = max(1e-6, now - self._last_cpu_t)
        dt_cpu = max(0.0, proc_now - self._last_proc_t)
        self._last_cpu_t = now
        self._last_proc_t = proc_now
        return float((dt_cpu / dt_wall) * 100.0)

    def _memory_mb(self) -> float:
        if self._proc is not None:
            try:
                return float(self._proc.memory_info().rss / (1024.0 * 1024.0))
            except Exception:
                pass
        if resource is not None:
            try:
                rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
                if rss > 1024 * 1024:
                    rss = rss / (1024.0 * 1024.0)
                else:
                    rss = rss / 1024.0
                return rss
            except Exception:
                return 0.0
        return 0.0

