from pathlib import Path

from importlib import import_module

LibraryStore = import_module("pulsewave-11.core.library").LibraryStore
Track = import_module("pulsewave-11.core.state").Track


def test_library_store_playlist_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "library.json"
    store = LibraryStore(path=path)
    store.add_category("Synthwave")
    track = Track(id="t1", title="Nightcall", artist="Kavinsky", source="local")
    assert store.add_track_to_playlist("Drive Mix", track, category="Synthwave")
    assert not store.add_track_to_playlist("Drive Mix", track, category="Synthwave")

    tracks = store.playlist_tracks("Drive Mix")
    assert len(tracks) == 1
    assert tracks[0].title == "Nightcall"
