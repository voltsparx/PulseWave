from __future__ import annotations

import math
import time
from abc import ABC, abstractmethod
from typing import Any

from ..utils.helpers import clamp

try:
    import mpv  # type: ignore
except Exception:  # pragma: no cover - optional dependency or missing runtime DLL
    mpv = None

try:
    import pulsewave_11_native as pulsewave_native  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    try:
        import pulsewave_native  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        pulsewave_native = None


class AudioBackend(ABC):
    name = "base"

    @abstractmethod
    def play_source(self, source: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def toggle_pause(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def seek(self, seconds: float) -> float:
        raise NotImplementedError

    @abstractmethod
    def set_volume(self, volume: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_position(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_duration(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def is_playing(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_waveform_chunk(self, size: int = 128) -> list[float]:
        raise NotImplementedError

    @abstractmethod
    def set_speed(self, speed: float) -> float:
        raise NotImplementedError

    @abstractmethod
    def get_speed(self) -> float:
        raise NotImplementedError

    def info(self) -> dict[str, Any]:
        return {"name": self.name}


class SimulatedBackend(AudioBackend):
    name = "simulated"

    def __init__(self) -> None:
        self._source: str | None = None
        self._playing = False
        self._paused = False
        self._volume = 60
        self._duration = 240.0
        self._start_time = 0.0
        self._position_offset = 0.0
        self._speed = 1.0

    def play_source(self, source: str) -> None:
        self._source = source
        self._playing = True
        self._paused = False
        self._start_time = time.monotonic()
        self._position_offset = 0.0

    def stop(self) -> None:
        self._playing = False
        self._paused = False
        self._position_offset = 0.0

    def toggle_pause(self) -> bool:
        if not self._playing:
            return False
        if self._paused:
            self._start_time = time.monotonic() - self._position_offset
            self._paused = False
        else:
            self._position_offset = self.get_position()
            self._paused = True
        return self._paused

    def seek(self, seconds: float) -> float:
        self._position_offset = clamp(self.get_position() + seconds, 0.0, self._duration)
        if not self._paused:
            self._start_time = time.monotonic() - self._position_offset
        return self._position_offset

    def set_volume(self, volume: int) -> None:
        self._volume = clamp(volume, 0, 100)

    def get_position(self) -> float:
        if not self._playing:
            return 0.0
        if self._paused:
            return self._position_offset
        elapsed = (time.monotonic() - self._start_time) * self._speed
        return clamp(elapsed, 0.0, self._duration)

    def get_duration(self) -> float:
        return self._duration

    def is_playing(self) -> bool:
        if not self._playing:
            return False
        if self.get_position() >= self._duration:
            self._playing = False
            self._paused = False
            return False
        return not self._paused

    def get_waveform_chunk(self, size: int = 128) -> list[float]:
        pos = self.get_position()
        chunk: list[float] = []
        for i in range(size):
            x = pos + (i / max(1, size))
            base = math.sin(2 * math.pi * 0.8 * x)
            overtone = 0.4 * math.sin(2 * math.pi * 2.3 * x)
            chunk.append((base + overtone) * (0.3 + (self._volume / 120.0)))
        return chunk

    def set_speed(self, speed: float) -> float:
        current_pos = self.get_position()
        self._speed = clamp(speed, 0.5, 2.0)
        if not self._paused:
            self._start_time = time.monotonic() - (current_pos / self._speed)
        return self._speed

    def get_speed(self) -> float:
        return self._speed


class NativeBackend(AudioBackend):
    name = "native"

    def __init__(self) -> None:
        if pulsewave_native is None:  # pragma: no cover - dependency guard
            raise RuntimeError("pulsewave_11_native is not available")
        ok = bool(pulsewave_native.init_audio())
        if not ok:
            raise RuntimeError("native engine failed to initialize")
        self._playing = False
        self._paused = False
        self._volume = 60
        self._speed = 1.0

    def play_source(self, source: str) -> None:
        ok = bool(pulsewave_native.play_file(source))
        if not ok:
            raise RuntimeError("native engine failed to load source")
        self._playing = True
        self._paused = False

    def stop(self) -> None:
        # Current native bridge has no dedicated stop API.
        self._playing = False
        self._paused = False

    def toggle_pause(self) -> bool:
        paused = bool(pulsewave_native.pause())
        self._paused = paused
        self._playing = not paused
        return paused

    def seek(self, seconds: float) -> float:
        pulsewave_native.seek(seconds)
        return self.get_position()

    def set_volume(self, volume: int) -> None:
        # Volume hook will be added when native API exposes it.
        self._volume = clamp(volume, 0, 100)

    def get_position(self) -> float:
        try:
            return float(pulsewave_native.get_position())
        except Exception:
            return 0.0

    def get_duration(self) -> float:
        # Native bridge currently does not expose duration yet.
        return 0.0

    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def get_waveform_chunk(self, size: int = 128) -> list[float]:
        try:
            raw = pulsewave_native.get_visualizer_data(size)
            return [float(x) for x in raw]
        except Exception:
            return [0.0] * size

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "bridge": "pulsewave_11_native"}

    def set_speed(self, speed: float) -> float:
        # Placeholder until bridge exposes speed adjustment.
        self._speed = clamp(speed, 0.5, 2.0)
        return self._speed

    def get_speed(self) -> float:
        return self._speed


class MpvBackend(AudioBackend):
    name = "mpv"

    def __init__(self) -> None:
        if mpv is None:  # pragma: no cover - dependency guard
            raise RuntimeError("python-mpv is not installed")
        self._player = mpv.MPV(video=False, ytdl=True)

    def play_source(self, source: str) -> None:
        self._player.command("loadfile", source, "replace")
        self._player.pause = False

    def stop(self) -> None:
        self._player.command("stop")

    def toggle_pause(self) -> bool:
        self._player.pause = not bool(self._player.pause)
        return bool(self._player.pause)

    def seek(self, seconds: float) -> float:
        self._player.command("seek", str(seconds), "relative")
        return self.get_position()

    def set_volume(self, volume: int) -> None:
        self._player.volume = clamp(volume, 0, 100)

    def get_position(self) -> float:
        try:
            return float(self._player.time_pos or 0.0)
        except Exception:
            return 0.0

    def get_duration(self) -> float:
        try:
            return float(self._player.duration or 0.0)
        except Exception:
            return 0.0

    def is_playing(self) -> bool:
        try:
            idle = bool(getattr(self._player, "idle_active", True))
            return not idle and not bool(self._player.pause)
        except Exception:
            return False

    def get_waveform_chunk(self, size: int = 128) -> list[float]:
        # MPV does not expose PCM samples through this API.
        pos = self.get_position()
        return [math.sin(pos * 1.3 + i / 6.0) for i in range(size)]

    def set_speed(self, speed: float) -> float:
        value = float(clamp(speed, 0.5, 2.0))
        self._player.speed = value
        return value

    def get_speed(self) -> float:
        try:
            return float(self._player.speed or 1.0)
        except Exception:
            return 1.0


class PlaybackController:
    def __init__(self, backend: str = "auto") -> None:
        self.backend = self._select_backend(backend)
        self._volume = 60
        self.backend.set_volume(self._volume)
        self._speed = 1.0

    @staticmethod
    def available_backends() -> list[str]:
        return ["auto", "native", "mpv", "simulated"]

    @staticmethod
    def backend_capabilities() -> dict[str, bool]:
        native_ready = pulsewave_native is not None
        mpv_ready = mpv is not None
        return {
            "native_available": native_ready,
            "mpv_available": mpv_ready,
        }

    def _select_backend(self, backend: str) -> AudioBackend:
        order = {
            "auto": ["native", "mpv", "simulated"],
            "native": ["native", "simulated"],
            "mpv": ["mpv", "simulated"],
            "simulated": ["simulated"],
        }.get(backend, ["native", "mpv", "simulated"])

        for name in order:
            try:
                if name == "native":
                    return NativeBackend()
                if name == "mpv":
                    return MpvBackend()
                if name == "simulated":
                    return SimulatedBackend()
            except Exception:
                continue
        return SimulatedBackend()

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def info(self) -> dict[str, Any]:
        return self.backend.info()

    def play_source(self, source: str) -> None:
        self.backend.play_source(source)

    def stop(self) -> None:
        self.backend.stop()

    def toggle_pause(self) -> bool:
        return self.backend.toggle_pause()

    def seek(self, seconds: float) -> float:
        return self.backend.seek(seconds)

    def set_volume(self, volume: int) -> int:
        self._volume = clamp(volume, 0, 100)
        self.backend.set_volume(self._volume)
        return self._volume

    def get_position(self) -> float:
        return self.backend.get_position()

    def get_duration(self) -> float:
        return self.backend.get_duration()

    def is_playing(self) -> bool:
        return self.backend.is_playing()

    def get_waveform_chunk(self, size: int = 128) -> list[float]:
        return self.backend.get_waveform_chunk(size=size)

    def set_speed(self, speed: float) -> float:
        self._speed = float(clamp(speed, 0.5, 2.0))
        try:
            self._speed = float(self.backend.set_speed(self._speed))
        except Exception:
            pass
        return self._speed

    def get_speed(self) -> float:
        try:
            self._speed = float(self.backend.get_speed())
        except Exception:
            pass
        return self._speed
