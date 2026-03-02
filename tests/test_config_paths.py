from importlib import import_module, reload
from pathlib import Path

paths = import_module("pulsewave-11.utils.paths")


def test_config_home_shape() -> None:
    home = paths.config_home()
    assert isinstance(home, Path)
    assert home.exists()
    assert home.is_dir()


def test_paths_resolve_under_config_home() -> None:
    home = paths.config_home()
    assert paths.config_file().parent == home
    assert paths.library_file().parent == home
    assert paths.logs_dir().parent == home


def test_config_home_env_override(monkeypatch, tmp_path) -> None:
    override = tmp_path / "custom-config-home"
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(override))
    module = reload(paths)
    assert module.config_home() == override


def test_initialize_config_home_default_non_interactive(monkeypatch, tmp_path) -> None:
    module = reload(paths)
    default_home = (tmp_path / ".pulsewave-11-config").resolve()
    pointer = tmp_path / ".pulsewave-11-config-location"
    monkeypatch.delenv("PULSEWAVE_11_CONFIG_HOME", raising=False)
    monkeypatch.setattr(module, "CONFIG_LOCATION_FILE", pointer)
    monkeypatch.setattr(module, "default_config_home", lambda: default_home)

    selected = module.initialize_config_home(interactive=False)
    assert selected == default_home
    assert pointer.read_text(encoding="utf-8").strip() == str(default_home)
