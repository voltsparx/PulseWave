from __future__ import annotations

from typing import Callable

CommandHandler = Callable[[list[str]], None]
ActionHandler = Callable[[], None]


class CommandController:
    def __init__(
        self,
        *,
        command_handlers_provider: Callable[[], dict[str, CommandHandler]],
        action_handlers_provider: Callable[[], dict[str, ActionHandler]],
        command_catalog_provider: Callable[[], dict[str, str]],
        suggest_commands: Callable[[str], list[str]],
        hints_for_parts: Callable[[list[str]], list[str]],
        set_hints: Callable[[list[str]], None],
        set_error: Callable[[str], None],
    ) -> None:
        self._command_handlers_provider = command_handlers_provider
        self._action_handlers_provider = action_handlers_provider
        self._command_catalog_provider = command_catalog_provider
        self._suggest_commands = suggest_commands
        self._hints_for_parts = hints_for_parts
        self._set_hints = set_hints
        self._set_error = set_error

    def dispatch_command(self, parts: list[str]) -> None:
        if not parts:
            return
        cmd = parts[0].lower()
        handler = self._command_handlers_provider().get(cmd)
        if handler is None:
            suggestions = self._suggest_commands(cmd)
            if suggestions:
                self._set_error(f"Unknown command: {cmd}. Try: {', '.join(suggestions)}")
                catalog = self._command_catalog_provider()
                self._set_hints([catalog[name] for name in suggestions if name in catalog])
            else:
                self._set_error(f"Unknown command: {cmd}. Use `help`.")
            return
        self._set_hints(self._hints_for_parts(parts))
        handler(parts)

    def dispatch_action(self, action: str) -> None:
        fn = self._action_handlers_provider().get(action)
        if fn is None:
            self._set_error(f"Unsupported action: {action}")
            return
        fn()

