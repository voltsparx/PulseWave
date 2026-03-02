from importlib import import_module

QueueManager = import_module("pulsewave-11.core.queue").QueueManager
RepeatMode = import_module("pulsewave-11.core.state").RepeatMode
Track = import_module("pulsewave-11.core.state").Track


def _track(i: int) -> Track:
    return Track(id=str(i), title=f"Song {i}")


def test_next_repeat_all_wraps() -> None:
    queue = QueueManager(seed=1)
    queue.extend([_track(1), _track(2)])
    queue.set_index(1)
    nxt = queue.next_track(RepeatMode.ALL, shuffle_enabled=False)
    assert nxt is not None
    assert nxt.id == "1"


def test_repeat_one_stays_on_track() -> None:
    queue = QueueManager(seed=1)
    queue.extend([_track(1), _track(2)])
    queue.set_index(0)
    nxt = queue.next_track(RepeatMode.ONE, shuffle_enabled=False)
    assert nxt is not None
    assert nxt.id == "1"


def test_previous_without_repeat_can_end() -> None:
    queue = QueueManager(seed=1)
    queue.extend([_track(1), _track(2)])
    queue.set_index(0)
    prev = queue.previous_track(RepeatMode.OFF, shuffle_enabled=False)
    assert prev is None
