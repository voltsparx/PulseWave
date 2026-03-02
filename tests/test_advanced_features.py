from importlib import import_module
from pathlib import Path

PulseWave11App = import_module("pulsewave-11.app").PulseWave11App
MetadataEnricher = import_module("pulsewave-11.services.metadata").MetadataEnricher
Track = import_module("pulsewave-11.core.state").Track


def test_vizpreset_save_load_and_chars(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("vizpreset chars .:-=+*#%@")
    assert app._get_cfg("visualizer.custom_levels", "") == ".:-=+*#%@"

    app.handle_input("vizpreset save test")
    app.handle_input("settings set visualizer.bars 12")
    assert app._get_cfg("visualizer.bars", 0) == 12

    app.handle_input("vizpreset load test")
    assert app._get_cfg("visualizer.bars", 0) == 24


def test_snapshot_save_and_restore_queue(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    song = tmp_path / "demo.mp3"
    song.write_bytes(b"")

    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()
    app.handle_input(f'add "{song}"')

    app.handle_input("snapshot save quick")
    app.queue.clear()
    assert app.queue.size() == 0

    app.handle_input("snapshot load quick")
    assert app.queue.size() == 1
    assert app.state.current_track is not None


def test_script_runner_command(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    script = tmp_path / "flow.pw11"
    script.write_text("settings show\nperf on\nwait 0.01\nperf off\n", encoding="utf-8")

    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()
    app.handle_input(f'script run "{script}"')

    assert "Script executed:" in app.state.status_message
    assert app.state.show_perf_panel is False


def test_lanstream_start_and_stop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PULSEWAVE_11_CONFIG_HOME", str(tmp_path / ".cfg"))
    app = PulseWave11App(config_path=tmp_path / "config.json")
    app.bootstrap()

    app.handle_input("lanstream start 0")
    assert app.lan_stream.running is True
    assert "running at http://" in app.state.lan_stream_status

    app.handle_input("lanstream stop")
    assert app.lan_stream.running is False
    assert app.state.lan_stream_status == "stopped"


def test_metadata_lyrics_sync(tmp_path: Path) -> None:
    song = tmp_path / "artist - track.mp3"
    song.write_bytes(b"")
    lrc = tmp_path / "artist - track.lrc"
    lrc.write_text("[00:01.00]line one\n[00:05.00]line two\n", encoding="utf-8")

    track = Track(id="t1", title="track", artist="artist", source="local", path=song)

    enricher = MetadataEnricher(root=tmp_path / ".cache")
    lines = enricher.lyrics(track)
    assert len(lines) == 2
    assert enricher.current_lyric_line(track, 5.2) == "line two"
