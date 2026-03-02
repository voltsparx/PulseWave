from importlib import import_module
from pathlib import Path

cli = import_module("pulsewave-11.cli")


def test_cli_non_interactive_command_execution(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    config_path = tmp_path / "config.json"

    code = cli.main(["--config", str(config_path), "-C", "settings", "--print-status"])
    out = capsys.readouterr().out

    assert code == 0
    assert "Settings panel opened" in out
