"""Process-wide data generation counter.

Bumped from every write path that changes hands / hand_players (import, clear, restore,
workspace delete, rebuild). Caches keyed on derived data (reports resolutions) include it so
they never serve a stale result, whatever the row counts or ids happen to be.

Keying on the generation makes old entries unreachable but does not free them, so in-process
caches also register a clear callback with `on_bump`: every bump drops their contents.
"""

import logging
import threading
from typing import Callable

_lock = threading.Lock()
_gen = 0
_hooks: list[Callable[[], None]] = []

log = logging.getLogger(__name__)


def on_bump(fn: Callable[[], None]) -> Callable[[], None]:
    """Register `fn` (no arguments) to run after every bump. Usable as a decorator."""
    with _lock:
        if fn not in _hooks:
            _hooks.append(fn)
    return fn


def bump() -> int:
    global _gen
    with _lock:
        _gen += 1
        gen = _gen
        hooks = list(_hooks)
    for fn in hooks:
        try:
            fn()
        except Exception:  # a cache that fails to clear must not fail the write
            log.warning("data generation hook %r failed", fn, exc_info=True)
    return gen


def current() -> int:
    return _gen
