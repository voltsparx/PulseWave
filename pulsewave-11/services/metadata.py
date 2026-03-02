from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..core.state import Track
from ..utils.helpers import ensure_dir
from ..utils.paths import cache_dir

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    Image = None

_LRC_RE = re.compile(r"\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]")
_ASCII_GRADIENT = " .:-=+*#%@"


class MetadataEnricher:
    def __init__(self, root: Path | None = None) -> None:
        self._root = ensure_dir(root or (cache_dir() / "metadata"))
        self._thumb_root = ensure_dir(self._root / "thumbs")
        self._lyrics_root = ensure_dir(self._root / "lyrics")

    def current_lyric_line(self, track: Track | None, position: float) -> str:
        if track is None:
            return ""
        lines = self.lyrics(track)
        if not lines:
            return ""
        current = ""
        for stamp, text in lines:
            if position + 1e-6 < stamp:
                break
            current = text
        return current

    def lyrics(self, track: Track) -> list[tuple[float, str]]:
        cache_file = self._lyrics_cache_file(track)
        cached = self._read_json(cache_file)
        if isinstance(cached, dict) and isinstance(cached.get("lines"), list):
            parsed = []
            for row in cached["lines"]:
                if not isinstance(row, list) or len(row) != 2:
                    continue
                parsed.append((float(row[0]), str(row[1])))
            if parsed:
                return parsed

        lines = self._extract_lyrics(track)
        self._write_json(cache_file, {"lines": [[t, s] for t, s in lines]})
        return lines

    def ascii_thumbnail(self, track: Track, *, width: int = 18, height: int = 8) -> list[str]:
        cache_file = self._thumb_cache_file(track)
        cached = self._read_json(cache_file)
        if isinstance(cached, dict) and isinstance(cached.get("lines"), list):
            raw_lines = [str(item) for item in cached.get("lines", []) if str(item).strip()]
            if raw_lines:
                return raw_lines[:height]

        lines = self._extract_ascii_thumbnail(track, width=width, height=height)
        self._write_json(cache_file, {"lines": lines})
        return lines

    def refresh(self, track: Track) -> None:
        self._lyrics_cache_file(track).unlink(missing_ok=True)
        self._thumb_cache_file(track).unlink(missing_ok=True)

    def _cache_key(self, track: Track) -> str:
        raw = f"{track.id}|{track.source}|{track.path or ''}|{track.title}|{track.artist}|{track.album}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]

    def _thumb_cache_file(self, track: Track) -> Path:
        return self._thumb_root / f"{self._cache_key(track)}.json"

    def _lyrics_cache_file(self, track: Track) -> Path:
        return self._lyrics_root / f"{self._cache_key(track)}.json"

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return raw if isinstance(raw, dict) else None

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        except Exception:
            return

    def _extract_lyrics(self, track: Track) -> list[tuple[float, str]]:
        if track.source != "local" or track.path is None:
            return []
        candidates = [
            track.path.with_suffix(".lrc"),
            track.path.with_name(f"{track.path.stem}.lyrics.lrc"),
            track.path.with_name("lyrics.lrc"),
        ]
        lrc_file = next((path for path in candidates if path.exists()), None)
        if lrc_file is None:
            return []
        try:
            text = lrc_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []
        return _parse_lrc(text)

    def _extract_ascii_thumbnail(self, track: Track, *, width: int, height: int) -> list[str]:
        cover = self._find_cover_art(track)
        if cover is not None and Image is not None:
            try:
                return _image_to_ascii(cover, width=width, height=height)
            except Exception:
                pass
        return _generated_ascii(track, width=width, height=height)

    def _find_cover_art(self, track: Track) -> Path | None:
        if track.source != "local" or track.path is None:
            return None
        parent = track.path.parent
        names = (
            "cover.jpg",
            "folder.jpg",
            "front.jpg",
            "cover.png",
            "folder.png",
            "front.png",
        )
        for name in names:
            candidate = parent / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None


def _parse_lrc(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for line in text.splitlines():
        matches = list(_LRC_RE.finditer(line))
        if not matches:
            continue
        lyric = line
        for m in matches:
            lyric = lyric.replace(m.group(0), "")
        lyric = lyric.strip()
        if not lyric:
            continue
        for match in matches:
            mm = int(match.group(1))
            ss = int(match.group(2))
            frac = match.group(3) or "0"
            frac_sec = float(f"0.{frac[:3]}") if frac else 0.0
            out.append((mm * 60.0 + ss + frac_sec, lyric))
    out.sort(key=lambda item: item[0])
    dedup: list[tuple[float, str]] = []
    for stamp, lyric in out:
        if dedup and abs(dedup[-1][0] - stamp) < 1e-6 and dedup[-1][1] == lyric:
            continue
        dedup.append((stamp, lyric))
    return dedup


def _generated_ascii(track: Track, *, width: int, height: int) -> list[str]:
    seed = hashlib.sha1(track.label().encode("utf-8")).digest()
    lines: list[str] = []
    for y in range(max(2, height)):
        row_chars = []
        for x in range(max(8, width)):
            idx_seed = seed[(x + y) % len(seed)]
            value = (idx_seed + x * 11 + y * 17) % len(_ASCII_GRADIENT)
            row_chars.append(_ASCII_GRADIENT[value])
        lines.append("".join(row_chars))
    return lines


def _image_to_ascii(path: Path, *, width: int, height: int) -> list[str]:
    if Image is None:
        return []
    img = Image.open(path).convert("L")
    img = img.resize((max(8, width), max(2, height)))
    pixels = list(img.getdata())
    lines: list[str] = []
    stride = img.size[0]
    for y in range(img.size[1]):
        row = pixels[y * stride : (y + 1) * stride]
        chars = []
        for px in row:
            idx = int((px / 255.0) * (len(_ASCII_GRADIENT) - 1))
            chars.append(_ASCII_GRADIENT[idx])
        lines.append("".join(chars))
    return lines

