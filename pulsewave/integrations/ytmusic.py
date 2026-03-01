from __future__ import annotations

from typing import Optional

from pulsewave.core.state import Track

try:
    from ytmusicapi import YTMusic
except ImportError:  # pragma: no cover - optional dependency
    YTMusic = None

try:
    import yt_dlp
except ImportError:  # pragma: no cover - optional dependency
    yt_dlp = None


class YTMusicClient:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._ytmusic = YTMusic() if enabled and YTMusic is not None else None
        self._stream_cache: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return self.enabled and self._ytmusic is not None

    def search_songs(self, query: str, limit: int = 20) -> list[Track]:
        if not self.available:
            return []
        try:
            results = self._ytmusic.search(query, filter="songs", limit=limit)
        except Exception:
            return []

        tracks: list[Track] = []
        for item in results:
            video_id = item.get("videoId")
            title = item.get("title")
            if not video_id or not title:
                continue
            artists = item.get("artists", [])
            artist = ", ".join(a.get("name", "") for a in artists if a.get("name")) or "Unknown Artist"
            duration_text = item.get("duration", "0:00")
            tracks.append(
                Track(
                    id=video_id,
                    title=title,
                    artist=artist,
                    source="youtube",
                    duration=_parse_duration(duration_text),
                )
            )
        return tracks

    def resolve_stream_url(self, video_id: str) -> Optional[str]:
        if video_id in self._stream_cache:
            return self._stream_cache[video_id]
        if yt_dlp is None:
            return None

        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "extract_flat": False,
        }
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(watch_url, download=False)
        except Exception:
            return None

        stream_url = info.get("url")
        if isinstance(stream_url, str) and stream_url:
            self._stream_cache[video_id] = stream_url
            return stream_url
        return None


def _parse_duration(text: str) -> float:
    if not text:
        return 0.0
    parts = text.split(":")
    if not all(p.isdigit() for p in parts):
        return 0.0
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return float(seconds)

