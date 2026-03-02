from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..utils.helpers import ensure_dir
from ..utils.paths import config_home

_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9._-]+")


class SnapshotStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = ensure_dir(root or (config_home() / "snapshots"))

    def list_names(self) -> list[str]:
        return sorted(path.stem for path in self.root.glob("*.json") if path.is_file())

    def save(self, name: str, payload: dict[str, Any]) -> str:
        clean = _clean_name(name)
        if not clean:
            raise ValueError("snapshot name is empty")
        path = self.root / f"{clean}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return clean

    def load(self, name: str) -> dict[str, Any] | None:
        clean = _clean_name(name)
        if not clean:
            return None
        path = self.root / f"{clean}.json"
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return raw if isinstance(raw, dict) else None

    def delete(self, name: str) -> bool:
        clean = _clean_name(name)
        if not clean:
            return False
        path = self.root / f"{clean}.json"
        if not path.exists():
            return False
        path.unlink()
        return True


def _clean_name(name: str) -> str:
    compact = _SAFE_NAME_RE.sub("_", name.strip())
    compact = compact.strip("._-")
    return compact[:80]

