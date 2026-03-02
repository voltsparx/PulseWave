from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Optional

from ..core.state import Track
from ..utils.paths import cache_dir

try:
    import mutagen  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    mutagen = None

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
        self._cache_file = cache_dir() / "library_index.json"

    def set_directories(self, directories: Iterable[str | Path]) -> None:
        self.directories = [Path(p).expanduser() for p in directories]

    def track_from_path(self, path: str | Path) -> Optional[Track]:
        candidate = Path(path).expanduser()
        if not candidate.exists() or candidate.suffix.lower() not in AUDIO_EXTENSIONS:
            return None

        artist = "Unknown Artist"
        album = ""
        title = candidate.stem
        parts = [p.strip() for p in candidate.stem.split(" - ")]
        if len(parts) >= 3:
            artist = parts[0] or artist
            album = parts[1]
            title = " - ".join(parts[2:]) or title
        elif len(parts) == 2:
            artist = parts[0] or artist
            title = parts[1] or title

        duration = 0.0
        bitrate = 0
        if mutagen is not None:
            try:
                meta = mutagen.File(str(candidate), easy=True)
                if meta is not None:
                    artist = (meta.get("artist", [artist]) or [artist])[0] or artist
                    title = (meta.get("title", [title]) or [title])[0] or title
                    album = (meta.get("album", [album]) or [album])[0] or album
                    duration = float(getattr(meta.info, "length", 0.0) or 0.0)
                    bitrate = int((getattr(meta.info, "bitrate", 0) or 0) / 1000)
            except Exception:
                pass

        digest = hashlib.sha1(str(candidate).encode("utf-8")).hexdigest()[:12]
        return Track(
            id=digest,
            title=title,
            artist=artist,
            album=album,
            source="local",
            path=candidate,
            duration=duration,
            file_format=candidate.suffix.lower().lstrip("."),
            bitrate_kbps=bitrate,
        )

    def scan(self, force: bool = False) -> list[Track]:
        if self._cache and not force:
            return list(self._cache)
        if not force:
            cached = self._load_disk_cache()
            if cached:
                self._cache = cached
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
        self._save_disk_cache(found)
        return list(found)

    def _load_disk_cache(self) -> list[Track]:
        try:
            payload = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        dirs = payload.get("directories", [])
        current_dirs = [str(p) for p in self.directories]
        if dirs != current_dirs:
            return []
        tracks = payload.get("tracks", [])
        out: list[Track] = []
        for record in tracks:
            path_value = record.get("path")
            out.append(
                Track(
                    id=str(record.get("id", "")),
                    title=str(record.get("title", "Unknown Title")),
                    artist=str(record.get("artist", "Unknown Artist")),
                    album=str(record.get("album", "")),
                    duration=float(record.get("duration", 0.0) or 0.0),
                    source="local",
                    path=Path(path_value) if path_value else None,
                    file_format=str(record.get("file_format", "")),
                    bitrate_kbps=int(record.get("bitrate_kbps", 0) or 0),
                )
            )
        return out

    def _save_disk_cache(self, tracks: list[Track]) -> None:
        payload = {
            "directories": [str(p) for p in self.directories],
            "tracks": [
                {
                    "id": t.id,
                    "title": t.title,
                    "artist": t.artist,
                    "album": t.album,
                    "duration": t.duration,
                    "path": str(t.path) if t.path else "",
                    "file_format": t.file_format,
                    "bitrate_kbps": t.bitrate_kbps,
                }
                for t in tracks
            ],
        }
        try:
            self._cache_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        except OSError:
            return
