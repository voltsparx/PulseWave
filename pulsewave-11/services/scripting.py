from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from ..utils.helpers import safe_float


class ScriptRunner:
    def run_file(
        self,
        path: Path,
        *,
        run_command: Callable[[str], None],
        set_status: Callable[[str], None],
        set_error: Callable[[str], None],
        max_lines: int = 2000,
    ) -> int:
        if not path.exists() or not path.is_file():
            set_error(f"Script file not found: {path}")
            return 0
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            set_error(f"Failed to read script: {exc}")
            return 0
        if len(lines) > max_lines:
            set_error(f"Script too large ({len(lines)} lines). Max is {max_lines}.")
            return 0

        executed = 0
        for lineno, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("sleep ") or line.lower().startswith("wait "):
                _, _, value = line.partition(" ")
                seconds = max(0.0, safe_float(value.strip(), 0.0))
                if seconds > 0:
                    time.sleep(seconds)
                continue
            try:
                run_command(line)
            except Exception as exc:
                set_error(f"Script failed at line {lineno}: {exc}")
                return executed
            executed += 1
        set_status(f"Script executed: {executed} command(s).")
        return executed

