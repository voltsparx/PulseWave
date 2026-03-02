from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable

from ..utils.helpers import ensure_dir
from ..utils.paths import config_home


class PluginManager:
    def __init__(self, plugin_dir: Path | None = None, *, on_error: Callable[[str], None] | None = None) -> None:
        self.plugin_dir = ensure_dir(plugin_dir or (config_home() / "plugins"))
        self._modules: dict[str, ModuleType] = {}
        self._errors: dict[str, str] = {}
        self._on_error = on_error

    def load_all(self, *, enabled: list[str] | None = None) -> None:
        self._modules = {}
        self._errors = {}
        allow = {item.strip().lower() for item in (enabled or []) if str(item).strip()}
        for file in sorted(self.plugin_dir.glob("*.py")):
            name = file.stem.strip().lower()
            if allow and name not in allow:
                continue
            self._load_one(file, plugin_name=name)

    def reload(self, *, enabled: list[str] | None = None) -> None:
        self.load_all(enabled=enabled)

    def names(self) -> list[str]:
        return sorted(self._modules.keys())

    def errors(self) -> dict[str, str]:
        return dict(self._errors)

    def call_hook(self, hook: str, *args: object, **kwargs: object) -> None:
        for name, module in list(self._modules.items()):
            fn = getattr(module, hook, None)
            if not callable(fn):
                continue
            try:
                fn(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - defensive isolation
                self._errors[name] = f"{hook}: {exc}"
                self._emit_error(f"Plugin '{name}' failed in {hook}: {exc}")

    def _load_one(self, file: Path, *, plugin_name: str) -> None:
        module_id = f"pulsewave_11_plugin_{plugin_name}"
        spec = importlib.util.spec_from_file_location(module_id, file)
        if spec is None or spec.loader is None:
            self._errors[plugin_name] = "cannot create import spec"
            return
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            self._errors[plugin_name] = str(exc)
            self._emit_error(f"Plugin '{plugin_name}' failed to load: {exc}")
            return
        self._modules[plugin_name] = module

    def _emit_error(self, message: str) -> None:
        if self._on_error is not None:
            try:
                self._on_error(message)
            except Exception:
                return

