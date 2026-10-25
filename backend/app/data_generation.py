"""Process-wide data generation counter and change log.

Every write path that changes hand data, or data derived from it, reports the change here as
one of three kinds:

- append, `bump_append(workspace_id, hand_ids)`: only these hands (and their hand_players
  rows) were added to one workspace, after their commit; no existing row changed. The import
  paths: files, stream, H2N DB, tracker DB, auto-import.
- derived, `bump_derived(workspace_id)`: only per-player derived data changed
  (classification, first/last seen, hero re-detection that keeps player ids); hand rows are
  unchanged. finalize_import, player classification.
- reset, `bump()`: anything else (delete, clear, restore, rebuild, settings that change stats,
  workspace delete).

All three increment the generation, so `current()` keeps meaning "something changed".

Caches register a callback:
- `on_bump(fn)`: runs after every change of any kind. For caches that can't extend (SQL-backed
  ones that are cheap to recompute: graph, extras, sessions, General).
- `on_reset(fn)`: runs after a reset only. For caches that extend with the appended hands
  (Reports resolutions, stat popup records).

`changes_since(gen, workspace_id)` lists the hands appended to a workspace since generation
`gen` (import order), or None when they can't be known: a reset happened since `gen`, or the
bounded change log no longer reaches back to it. A cache entry records the generation it was
computed at, read *before* computing. When a change lands mid-computation the next lookup
extends from that generation, so nothing is missed; a hand may then be seen twice, so
extensions dedupe by hand id.
"""

import logging
import threading
from collections import deque
from typing import Callable, Iterable

_lock = threading.Lock()
_gen = 0
_hooks: list[Callable[[], None]] = []        # every change
_reset_hooks: list[Callable[[], None]] = []  # resets only

# Append events (generation, workspace id, hand ids), oldest first, bounded by the event count
# and by the ids held. A hand id is ~70 bytes resident, so the id bound is ~35 MB, reached only
# right after a big import (auto-import ticks add a few hands each). Past the bounds, caches
# older than the oldest kept event recompute.
LOG_MAX_EVENTS = 512
LOG_MAX_IDS = 500_000
_log: deque[tuple[int, int, tuple[str, ...]]] = deque()
_log_ids = 0
_reset_gen = 0   # generation of the last reset
_floor = 0       # changes_since(gen) is answerable only for gen >= _floor

log = logging.getLogger(__name__)


def on_bump(fn: Callable[[], None]) -> Callable[[], None]:
    """Register `fn` (no arguments) to run after every change of any kind. Usable as a
    decorator."""
    with _lock:
        if fn not in _hooks:
            _hooks.append(fn)
    return fn


def on_reset(fn: Callable[[], None]) -> Callable[[], None]:
    """Register `fn` (no arguments) to run after a reset (`bump()`) only. Usable as a
    decorator."""
    with _lock:
        if fn not in _reset_hooks:
            _reset_hooks.append(fn)
    return fn


def _run(hooks: list[Callable[[], None]]) -> None:
    for fn in hooks:
        try:
            fn()
        except Exception:  # a cache that fails to clear must not fail the write
            log.warning("data generation hook %r failed", fn, exc_info=True)


def _trim() -> None:
    """Drop the oldest append events beyond the bounds (caller holds _lock)."""
    global _log_ids, _floor
    while _log and (len(_log) > LOG_MAX_EVENTS or _log_ids > LOG_MAX_IDS):
        g, _ws, ids = _log.popleft()
        _log_ids -= len(ids)
        _floor = max(_floor, g)   # a generation before g can no longer see event g


def bump_append(workspace_id: int, hand_ids: Iterable[str]) -> int:
    """Append: only `hand_ids` were added to `workspace_id`. Call after their commit, with the
    hands actually inserted (not the duplicates skipped). Returns the new generation."""
    global _gen, _log_ids
    ids = tuple(hand_ids)
    with _lock:
        _gen += 1
        gen = _gen
        if ids:
            _log.append((gen, int(workspace_id), ids))
            _log_ids += len(ids)
            _trim()
        hooks = list(_hooks)
    _run(hooks)
    return gen


def bump_derived(workspace_id: int | None = None) -> int:
    """Derived: only per-player derived data changed (None: in every workspace). Returns the
    new generation."""
    global _gen
    with _lock:
        _gen += 1
        gen = _gen
        hooks = list(_hooks)
    _run(hooks)
    return gen


def bump() -> int:
    """Reset: any other change. Every registered cache drops its contents."""
    global _gen, _log_ids, _reset_gen, _floor
    with _lock:
        _gen += 1
        gen = _gen
        _reset_gen = gen
        _log.clear()
        _log_ids = 0
        _floor = gen
        hooks = list(_reset_hooks) + [fn for fn in _hooks if fn not in _reset_hooks]
    _run(hooks)
    return gen


def current() -> int:
    return _gen


def reset_since(gen: int) -> bool:
    """True when a reset happened after generation `gen`."""
    return _reset_gen > gen


def changes_since(gen: int, workspace_id: int) -> list[str] | None:
    """Hand ids appended to `workspace_id` after generation `gen`, in import order (may include
    a hand the caller already has: dedupe). None when a reset happened since `gen` or the log
    no longer reaches back to it: recompute."""
    with _lock:
        if gen > _gen or _reset_gen > gen or gen < _floor:
            return None
        out: list[str] = []
        for g, ws, ids in _log:
            if g > gen and ws == workspace_id:
                out.extend(ids)
        return out


def stats() -> dict:
    with _lock:
        return {"generation": _gen, "log_events": len(_log), "log_ids": _log_ids,
                "last_reset": _reset_gen, "floor": _floor}
