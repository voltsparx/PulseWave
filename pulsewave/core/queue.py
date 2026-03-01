from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from .state import RepeatMode, Track


@dataclass(frozen=True)
class QueueSnapshot:
    items: list[Track]
    index: int


class QueueManager:
    def __init__(self, seed: Optional[int] = None) -> None:
        self._items: list[Track] = []
        self._index: int = -1
        self._rng = random.Random(seed)

    def clear(self) -> None:
        self._items.clear()
        self._index = -1

    def add(self, track: Track) -> int:
        self._items.append(track)
        if self._index == -1:
            self._index = 0
        return len(self._items) - 1

    def extend(self, tracks: list[Track]) -> None:
        for track in tracks:
            self.add(track)

    def snapshot(self) -> QueueSnapshot:
        return QueueSnapshot(items=list(self._items), index=self._index)

    def current(self) -> Optional[Track]:
        if 0 <= self._index < len(self._items):
            return self._items[self._index]
        return None

    def index(self) -> int:
        return self._index

    def size(self) -> int:
        return len(self._items)

    def set_index(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self._items):
            self._index = index
            return self._items[index]
        return None

    def next_track(self, repeat_mode: RepeatMode, shuffle_enabled: bool) -> Optional[Track]:
        if not self._items:
            return None

        if repeat_mode == RepeatMode.ONE and self._index != -1:
            return self.current()

        if shuffle_enabled:
            if len(self._items) == 1:
                self._index = 0
            else:
                prev = self._index
                while self._index == prev:
                    self._index = self._rng.randint(0, len(self._items) - 1)
            return self.current()

        if self._index < len(self._items) - 1:
            self._index += 1
            return self.current()

        if repeat_mode == RepeatMode.ALL:
            self._index = 0
            return self.current()

        return None

    def previous_track(self, repeat_mode: RepeatMode, shuffle_enabled: bool) -> Optional[Track]:
        if not self._items:
            return None

        if repeat_mode == RepeatMode.ONE and self._index != -1:
            return self.current()

        if shuffle_enabled:
            if len(self._items) == 1:
                self._index = 0
            else:
                prev = self._index
                while self._index == prev:
                    self._index = self._rng.randint(0, len(self._items) - 1)
            return self.current()

        if self._index > 0:
            self._index -= 1
            return self.current()

        if repeat_mode == RepeatMode.ALL:
            self._index = len(self._items) - 1
            return self.current()

        return None

