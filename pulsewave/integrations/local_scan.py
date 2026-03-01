from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable, Optional

from pulsewave.core.state import Track

AUDIO_EXTENSIONS = {
    ".mp3",
    ".flac",
    ".wav",
    ".ogg",
    ".opus",
    ".m4a",
    ".aac",
    ".wma",
}


class LocalScanner:
    def __init__(self, directories: Optional[Iterable[str | Path]] = None) -> None:
        self.directories = [Path(p).expanduser() for p in (directories or [])]
        self._cache: list[Track] = []

    def set_directories(self, directories: Iterable[str | Path]) -> None:
        self.directories = [Path(p).expanduser() for p in directories]

    def track_from_path(self, path: str | Path) -> Optional[Track]:
        candidate = Path(path).expanduser()
        if not candidate.exists() or candidate.suffix.lower() not in AUDIO_EXTENSIONS:
            return None

        artist = "Unknown Artist"
        title = candidate.stem
        if " - " in candidate.stem:
            artist_part, title_part = candidate.stem.split(" - ", 1)
            artist = artist_part.strip() or artist
            title = title_part.strip() or title

        digest = hashlib.sha1(str(candidate).encode("utf-8")).hexdigest()[:12]
        return Track(
            id=digest,
            title=title,
            artist=artist,
            source="local",
            path=candidate,
        )

    def scan(self, force: bool = False) -> list[Track]:
        if self._cache and not force:
            return list(self._cache)

        found: list[Track] = []
        for root in self.directories:
            if not root.exists() or not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.suffix.lower() not in AUDIO_EXTENSIONS:
                    continue
                track = self.track_from_path(path)
                if track is not None:
                    found.append(track)

        self._cache = found
        return list(found)

