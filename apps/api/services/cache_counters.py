"""Process-wide counters of cache hits by name ("digest", "judge"), so a stage can report how much of its work came from a cache:
read the value before and after (get) and subtract. Thread-safe; a counter never raises."""
import threading

_lock = threading.Lock()
_counts: dict[str, int] = {}


def bump(name: str, n: int = 1) -> None:
    with _lock:
        _counts[name] = _counts.get(name, 0) + n


def get(name: str) -> int:
    with _lock:
        return _counts.get(name, 0)
