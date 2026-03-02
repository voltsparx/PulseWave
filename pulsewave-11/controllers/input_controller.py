from __future__ import annotations

import os
import queue
import sys
import threading
import time
from typing import Any, Callable

from ..utils.helpers import clamp

InputEvent = tuple[str, str]


class InputController:
    def __init__(
        self,
        *,
        screen_enabled: bool,
        key_mapping_provider: Callable[[], dict[str, Any]],
        command_catalog_provider: Callable[[], dict[str, str]],
        status_callback: Callable[[str], None],
        hints_callback: Callable[[list[str]], None],
    ) -> None:
        self.awaiting_quick_search = False
        self.raw_input_enabled = False

        self._screen_enabled = bool(screen_enabled)
        self._key_mapping_provider = key_mapping_provider
        self._command_catalog_provider = command_catalog_provider
        self._status_callback = status_callback
        self._hints_callback = hints_callback

        self._input_queue: queue.Queue[InputEvent | None] = queue.Queue()
        self._stop_input = threading.Event()
        self._input_thread: threading.Thread | None = None

        self._state_lock = threading.Lock()
        self._command_buffer = ""
        self._command_cursor = 0
        self._command_entry_forced = False
        self._command_history: list[str] = []
        self._history_cursor = 0
        self._history_draft = ""

    @property
    def input_queue(self) -> queue.Queue[InputEvent | None]:
        return self._input_queue

    def start(self) -> None:
        if self._input_thread is not None or not sys.stdin:
            return
        target = self._raw_input_loop if self._raw_input_available() else self._input_reader_loop
        self.raw_input_enabled = target == self._raw_input_loop
        self._input_thread = threading.Thread(target=target, daemon=True, name="pulsewave-11-input")
        self._input_thread.start()

    def stop(self) -> None:
        self._stop_input.set()

    def enter_quick_search(self) -> None:
        with self._state_lock:
            self.awaiting_quick_search = True
            self._command_entry_forced = True
            self._command_buffer = ""
            self._command_cursor = 0
            self._history_cursor = len(self._command_history)

    def consume_quick_search_mode(self) -> bool:
        with self._state_lock:
            if not self.awaiting_quick_search:
                return False
            self.awaiting_quick_search = False
            return True

    def prompt_text(self, prompt_label: str) -> str:
        if not self.raw_input_enabled:
            return prompt_label
        with self._state_lock:
            active = self._is_command_entry_active_unlocked()
            buffer = self._command_buffer
            cursor = self._command_cursor
        if not active:
            return f"{prompt_label}(: for command, hotkeys active)"
        left = buffer[:cursor]
        right = buffer[cursor:]
        return f"{prompt_label}{left}|{right}"

    def drain(
        self,
        *,
        on_line: Callable[[str], None],
        on_eof: Callable[[], None],
        max_items: int = 10,
    ) -> None:
        for _ in range(max(1, max_items)):
            try:
                item = self._input_queue.get_nowait()
            except queue.Empty:
                return
            if item is None:
                on_eof()
                return
            kind, payload = item
            if kind == "key":
                self._handle_raw_key(payload, on_line=on_line, on_eof=on_eof)
                continue
            if kind == "line":
                on_line(payload)

    def _raw_input_available(self) -> bool:
        if not self._screen_enabled:
            return False
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return False
        return True

    def _input_reader_loop(self) -> None:
        while not self._stop_input.is_set():
            try:
                line = sys.stdin.readline()
            except Exception:
                self._input_queue.put(None)
                return
            if line == "":
                self._input_queue.put(None)
                return
            self._enqueue_line_event(line.rstrip("\n"))

    def _raw_input_loop(self) -> None:
        if os.name == "nt":
            self._raw_input_loop_windows()
        else:
            self._raw_input_loop_unix()

    def _raw_input_loop_windows(self) -> None:
        import msvcrt

        while not self._stop_input.is_set():
            if not msvcrt.kbhit():
                time.sleep(0.01)
                continue
            key = msvcrt.getwch()
            if key in ("\x00", "\xe0"):
                ext = msvcrt.getwch()
                key = {
                    "H": "\x1b[A",
                    "P": "\x1b[B",
                    "M": "\x1b[C",
                    "K": "\x1b[D",
                }.get(ext, "")
                if not key:
                    continue
            self._enqueue_key_event(key)

    def _raw_input_loop_unix(self) -> None:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not self._stop_input.is_set():
                readable, _, _ = select.select([sys.stdin], [], [], 0.05)
                if not readable:
                    continue
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    seq = ch
                    readable, _, _ = select.select([sys.stdin], [], [], 0.005)
                    if readable:
                        seq += sys.stdin.read(1)
                        if seq.endswith("["):
                            readable, _, _ = select.select([sys.stdin], [], [], 0.005)
                            if readable:
                                seq += sys.stdin.read(1)
                    ch = seq
                self._enqueue_key_event(ch)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, original)

    def _enqueue_line_event(self, line: str) -> None:
        self._input_queue.put(("line", line))

    def _enqueue_key_event(self, key: str) -> None:
        self._input_queue.put(("key", key))

    def _handle_raw_key(
        self,
        key: str,
        *,
        on_line: Callable[[str], None],
        on_eof: Callable[[], None],
    ) -> None:
        if key == "\x03":
            on_eof()
            return

        if key in {"\r", "\n"}:
            self._submit_buffered_command(on_line=on_line)
            return

        if key == "\t":
            self._autocomplete_buffer()
            return

        if key in {"\x08", "\x7f"}:
            self._buffer_backspace()
            return

        if key == ":" and not self._is_command_entry_active():
            self._activate_command_entry("")
            return

        if key == "\x1b":
            self._cancel_command_entry()
            return

        if key == "\x1b[A":
            if self._is_command_entry_active():
                self._history_up()
            else:
                on_line(key)
            return

        if key == "\x1b[B":
            if self._is_command_entry_active():
                self._history_down()
            else:
                on_line(key)
            return

        if key == "\x1b[C":
            if self._is_command_entry_active():
                self._move_cursor(+1)
            else:
                on_line(key)
            return

        if key == "\x1b[D":
            if self._is_command_entry_active():
                self._move_cursor(-1)
            else:
                on_line(key)
            return

        mapping = self._key_mapping_provider()
        if len(key) == 1 and key.isprintable():
            if self._is_command_entry_active():
                self._insert_at_cursor(key)
                return
            if key in mapping:
                on_line(key)
                return
            self._activate_command_entry(key)
            return

        if key in mapping:
            on_line(key)

    def _is_command_entry_active(self) -> bool:
        with self._state_lock:
            return self._is_command_entry_active_unlocked()

    def _is_command_entry_active_unlocked(self) -> bool:
        return self.awaiting_quick_search or self._command_entry_forced or bool(self._command_buffer)

    def _activate_command_entry(self, initial: str) -> None:
        with self._state_lock:
            self._command_entry_forced = True
            self._history_cursor = len(self._command_history)
            self._history_draft = ""
            self._command_buffer = initial
            self._command_cursor = len(initial)

    def _cancel_command_entry(self) -> None:
        cancelled_search = False
        with self._state_lock:
            if self.awaiting_quick_search:
                self.awaiting_quick_search = False
                cancelled_search = True
            self._command_entry_forced = False
            self._command_buffer = ""
            self._command_cursor = 0
            self._history_cursor = len(self._command_history)
            self._history_draft = ""
        if cancelled_search:
            self._status_callback("Quick search cancelled.")

    def _insert_at_cursor(self, text: str) -> None:
        with self._state_lock:
            left = self._command_buffer[: self._command_cursor]
            right = self._command_buffer[self._command_cursor :]
            self._command_buffer = left + text + right
            self._command_cursor += len(text)
            self._history_cursor = len(self._command_history)

    def _buffer_backspace(self) -> None:
        with self._state_lock:
            if not self._is_command_entry_active_unlocked():
                return
            if self._command_cursor <= 0:
                return
            left = self._command_buffer[: self._command_cursor - 1]
            right = self._command_buffer[self._command_cursor :]
            self._command_buffer = left + right
            self._command_cursor -= 1

    def _move_cursor(self, delta: int) -> None:
        with self._state_lock:
            self._command_cursor = int(clamp(self._command_cursor + delta, 0, len(self._command_buffer)))

    def _submit_buffered_command(self, *, on_line: Callable[[str], None]) -> None:
        with self._state_lock:
            if not self._is_command_entry_active_unlocked():
                return
            command = self._command_buffer.strip()
            was_quick_search = self.awaiting_quick_search
            if command and not was_quick_search:
                if not self._command_history or self._command_history[-1] != command:
                    self._command_history.append(command)
            self._command_entry_forced = False
            self._command_buffer = ""
            self._command_cursor = 0
            self._history_cursor = len(self._command_history)
            self._history_draft = ""
        if command or was_quick_search:
            on_line(command)

    def _history_up(self) -> None:
        with self._state_lock:
            if not self._command_history:
                return
            if self._history_cursor >= len(self._command_history):
                self._history_draft = self._command_buffer
            self._history_cursor = max(0, self._history_cursor - 1)
            self._command_buffer = self._command_history[self._history_cursor]
            self._command_cursor = len(self._command_buffer)
            self._command_entry_forced = True

    def _history_down(self) -> None:
        with self._state_lock:
            if not self._command_history:
                return
            if self._history_cursor < len(self._command_history) - 1:
                self._history_cursor += 1
                self._command_buffer = self._command_history[self._history_cursor]
            else:
                self._history_cursor = len(self._command_history)
                self._command_buffer = self._history_draft
            self._command_cursor = len(self._command_buffer)
            self._command_entry_forced = True

    def _autocomplete_buffer(self) -> None:
        with self._state_lock:
            active = self._is_command_entry_active_unlocked()
            at_end = self._command_cursor == len(self._command_buffer)
            current = self._command_buffer
        if not active:
            self._activate_command_entry("")
            return
        if not at_end:
            return
        match = self._completion_for_buffer(current)
        if match is None:
            return
        with self._state_lock:
            self._command_buffer = match
            self._command_cursor = len(match)

    def _completion_for_buffer(self, text: str) -> str | None:
        raw = text.strip()
        if not raw:
            return None
        parts = raw.split()
        catalog = self._command_catalog_provider()
        if len(parts) == 1 and not text.endswith(" "):
            name = parts[0].lower()
            candidates = sorted([cmd for cmd in catalog if cmd.startswith(name)])
            if len(candidates) == 1:
                return candidates[0] + " "
            if candidates:
                self._hints_callback([catalog[c] for c in candidates[:5] if c in catalog])
            return None

        cmd = parts[0].lower()
        prefix = parts[-1].lower() if not text.endswith(" ") else ""
        values: list[str] = []
        if cmd == "playlist":
            values = ["list", "create", "add", "load", "show", "use", "delete", "rename"]
        elif cmd == "settings":
            values = ["show", "hide", "get", "set"]
        elif cmd == "category":
            values = ["list", "add", "use"]
        elif cmd == "repeat":
            values = ["off", "one", "all"]
        elif cmd == "shuffle":
            values = ["on", "off"]
        elif cmd == "play":
            values = ["current", "next", "prev"]
        if not values:
            return None
        candidates = [item for item in values if item.startswith(prefix)]
        if len(candidates) != 1:
            if candidates:
                self._hints_callback([f"{cmd} {item}" for item in candidates[:5]])
            return None
        if text.endswith(" "):
            return text + candidates[0] + " "
        return text[: len(text) - len(parts[-1])] + candidates[0] + " "
