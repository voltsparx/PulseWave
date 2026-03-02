from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from .state import Track
from ..utils.helpers import ensure_dir
from ..utils.paths import library_file


@dataclass
class Playlist:
    name: str
    category: str
    description: str = ""
    tracks: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        if self.tracks is None:
            self.tracks = []


class LibraryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or library_file()
        ensure_dir(self.path.parent)
        self._payload = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            payload = {
                "categories": [{"name": "General"}],
                "playlists": [],
                "stats": {
                    "recently_played": [],
                    "play_counts": {},
                },
            }
            self._save(payload)
            return payload

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {
                "categories": [{"name": "General"}],
                "playlists": [],
                "stats": {"recently_played": [], "play_counts": {}},
            }
            self._save(raw)

        raw.setdefault("categories", [{"name": "General"}])
        raw.setdefault("playlists", [])
        raw.setdefault("stats", {"recently_played": [], "play_counts": {}})
        raw["stats"].setdefault("recently_played", [])
        raw["stats"].setdefault("play_counts", {})
        return raw

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def save(self) -> None:
        self._save(self._payload)

    def categories(self) -> list[str]:
        names = [c.get("name", "") for c in self._payload.get("categories", [])]
        out = sorted({name for name in names if name})
        return out or ["General"]

    def add_category(self, name: str) -> bool:
        clean = name.strip()
        if not clean:
            return False
        if clean in self.categories():
            return False
        self._payload["categories"].append({"name": clean})
        self.save()
        return True

    def playlists(self, category: Optional[str] = None) -> list[Playlist]:
        all_playlists = [Playlist(**p) for p in self._payload.get("playlists", [])]
        if category:
            return [p for p in all_playlists if p.category.lower() == category.lower()]
        return all_playlists

    def ensure_playlist(self, name: str, category: str = "General", description: str = "") -> Playlist:
        for idx, raw in enumerate(self._payload.get("playlists", [])):
            if raw.get("name", "").lower() == name.lower():
                playlist = Playlist(**raw)
                if playlist.category != category and category:
                    playlist.category = category
                    self._payload["playlists"][idx] = asdict(playlist)
                    self.save()
                return playlist

        playlist = Playlist(name=name, category=category, description=description, tracks=[])
        self._payload["playlists"].append(asdict(playlist))
        if category not in self.categories():
            self._payload["categories"].append({"name": category})
        self.save()
        return playlist

    def _get_playlist_index(self, name: str) -> int:
        for idx, raw in enumerate(self._payload.get("playlists", [])):
            if raw.get("name", "").lower() == name.lower():
                return idx
        return -1

    def add_track_to_playlist(self, playlist_name: str, track: Track, category: str = "General") -> bool:
        playlist = self.ensure_playlist(playlist_name, category=category)
        idx = self._get_playlist_index(playlist.name)
        if idx < 0:
            return False

        raw_tracks = self._payload["playlists"][idx].setdefault("tracks", [])
        for existing in raw_tracks:
            if existing.get("id") == track.id and existing.get("source") == track.source:
                return False

        raw_tracks.append(_track_to_record(track))
        self.save()
        return True

    def remove_track_from_playlist(self, playlist_name: str, track_id: str) -> bool:
        idx = self._get_playlist_index(playlist_name)
        if idx < 0:
            return False
        tracks = self._payload["playlists"][idx].get("tracks", [])
        before = len(tracks)
        tracks = [t for t in tracks if str(t.get("id")) != str(track_id)]
        self._payload["playlists"][idx]["tracks"] = tracks
        changed = len(tracks) != before
        if changed:
            self.save()
        return changed

    def playlist_tracks(self, playlist_name: str) -> list[Track]:
        smart = self.smart_playlist_tracks(playlist_name)
        if smart is not None:
            return smart
        idx = self._get_playlist_index(playlist_name)
        if idx < 0:
            return []
        return [_record_to_track(t) for t in self._payload["playlists"][idx].get("tracks", [])]

    def rename_playlist(self, old_name: str, new_name: str) -> bool:
        idx = self._get_playlist_index(old_name)
        if idx < 0:
            return False
        if self._get_playlist_index(new_name) >= 0:
            return False
        self._payload["playlists"][idx]["name"] = new_name
        self.save()
        return True

    def delete_playlist(self, name: str) -> bool:
        before = len(self._payload.get("playlists", []))
        self._payload["playlists"] = [
            p for p in self._payload.get("playlists", []) if p.get("name", "").lower() != name.lower()
        ]
        changed = len(self._payload["playlists"]) != before
        if changed:
            self.save()
        return changed

    def record_play(self, track: Track, *, recent_limit: int = 100) -> None:
        stats = self._payload.setdefault("stats", {"recently_played": [], "play_counts": {}})
        stats.setdefault("recently_played", [])
        stats.setdefault("play_counts", {})

        digest = _track_digest(track)
        stats["play_counts"][digest] = int(stats["play_counts"].get(digest, 0)) + 1
        entry = _track_to_record(track)

        recent = [r for r in stats["recently_played"] if _record_digest(r) != digest]
        recent.insert(0, entry)
        stats["recently_played"] = recent[: max(1, recent_limit)]
        self.save()

    def recently_played(self, limit: int = 20) -> list[Track]:
        stats = self._payload.get("stats", {})
        recent = stats.get("recently_played", [])
        return [_record_to_track(r) for r in recent[: max(1, limit)]]

    def most_played(self, limit: int = 20) -> list[Track]:
        stats = self._payload.get("stats", {})
        play_counts = stats.get("play_counts", {})
        if not play_counts:
            return []

        recent = stats.get("recently_played", [])
        index: dict[str, dict[str, Any]] = {}
        for record in recent:
            digest = _record_digest(record)
            if digest not in index:
                index[digest] = record

        ranked = sorted(play_counts.items(), key=lambda item: int(item[1]), reverse=True)
        out: list[Track] = []
        for digest, _ in ranked:
            record = index.get(str(digest))
            if record is None:
                continue
            out.append(_record_to_track(record))
            if len(out) >= max(1, limit):
                break
        return out

    def smart_playlist_tracks(self, name: str) -> list[Track] | None:
        lowered = name.strip().lower()
        if lowered in {"recent", "recently", "recently played", "recently_played"}:
            return self.recently_played(limit=50)
        if lowered in {"most", "most played", "most_played"}:
            return self.most_played(limit=50)
        return None


def _track_to_record(track: Track) -> dict[str, Any]:
    return {
        "id": track.id,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "duration": track.duration,
        "source": track.source,
        "path": str(track.path) if track.path else None,
        "stream_url": track.stream_url,
        "file_format": track.file_format,
        "bitrate_kbps": track.bitrate_kbps,
    }


def _record_to_track(record: dict[str, Any]) -> Track:
    path_value = record.get("path")
    return Track(
        id=str(record.get("id", "")),
        title=str(record.get("title", "Unknown Title")),
        artist=str(record.get("artist", "Unknown Artist")),
        album=str(record.get("album", "")),
        duration=float(record.get("duration", 0.0) or 0.0),
        source=str(record.get("source", "local")),
        path=None if not path_value else Path(path_value),
        stream_url=record.get("stream_url"),
        file_format=str(record.get("file_format", "")),
        bitrate_kbps=int(record.get("bitrate_kbps", 0) or 0),
    )


def _track_digest(track: Track) -> str:
    raw = f"{track.id}|{track.source}|{track.path or ''}|{track.title}|{track.artist}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _record_digest(record: dict[str, Any]) -> str:
    raw = (
        f"{record.get('id','')}|{record.get('source','')}|"
        f"{record.get('path','')}|{record.get('title','')}|{record.get('artist','')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
