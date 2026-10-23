"""Process-wide data generation counter.

Bumped from every write path that changes hands / hand_players (import, clear, restore,
workspace delete, rebuild). Caches keyed on derived data (reports resolutions) include it so
they never serve a stale result, whatever the row counts or ids happen to be.
"""

import threading

_lock = threading.Lock()
_gen = 0


def bump() -> int:
    global _gen
    with _lock:
        _gen += 1
        return _gen


def current() -> int:
    return _gen
