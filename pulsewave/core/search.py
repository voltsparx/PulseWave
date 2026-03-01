from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from pulsewave.core.state import Track
from pulsewave.integrations.local_scan import LocalScanner
from pulsewave.integrations.ytmusic import YTMusicClient


@dataclass(frozen=True)
class SearchResult:
    track: Track
    score: float
    source: str


class SearchService:
    def __init__(self, local_scanner: LocalScanner, ytmusic: YTMusicClient) -> None:
        self.local_scanner = local_scanner
        self.ytmusic = ytmusic

    def refresh_local_library(self) -> list[Track]:
        return self.local_scanner.scan(force=True)

    def search_local(self, query: str, limit: int = 25) -> list[SearchResult]:
        query_norm = query.strip().lower()
        if not query_norm:
            return []

        candidates = self.local_scanner.scan()
        scored: list[SearchResult] = []
        for track in candidates:
            haystack = f"{track.title} {track.artist} {track.path or ''}".lower()
            if query_norm in haystack:
                score = 1.0
            else:
                score = SequenceMatcher(None, query_norm, haystack).ratio()
            if score >= 0.18:
                scored.append(SearchResult(track=track, score=score, source="local"))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]

    def search_online(self, query: str, limit: int = 20) -> list[SearchResult]:
        tracks = self.ytmusic.search_songs(query, limit=limit)
        return [SearchResult(track=t, score=0.65, source="youtube") for t in tracks]

    def search_all(self, query: str, local_limit: int = 15, online_limit: int = 15) -> list[SearchResult]:
        local = self.search_local(query, limit=local_limit)
        online = self.search_online(query, limit=online_limit)
        merged = local + online
        merged.sort(key=lambda item: item.score + (0.05 if item.source == "local" else 0.0), reverse=True)
        return merged

