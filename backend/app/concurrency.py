"""Limit on CPU-heavy request handlers running at the same time.

Sync endpoints run in anyio's thread pool (40 threads) and share one GIL. Several cold Reports /
Statistics computations at once are slower in total than one after another, and each one holds
its own peak of Python objects, so they also stack memory. Heavy handlers wrap their work in
`heavy_slot()`; at most `MAX_HEAVY` run at once and the rest wait their turn.

The slot is re-entrant per thread: a heavy handler that calls another heavy helper does not
take a second slot (and can't deadlock on itself).
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from typing import Iterator

# Measured at 20k (3 cold Reports requests at once: Players split ~2.3 s, Next Actions and a
# small Positions split; performance/08 F4): the total is the same at every limit (~2.6-2.8 s,
# the GIL serialises the Python part), so the limit only decides latency and memory.
#   no limit / 3: short requests finish first (0.25-0.3 s), peak RSS +285-309 MB
#   2:            short requests 0.65-0.9 s, peak +259-293 MB
#   1:            short requests wait for the long one (2.2-2.7 s), peak +245-265 MB
# 2 keeps a lane free for short requests while a long one runs and caps the working sets
# in flight at two. OHM_MAX_HEAVY overrides it (e.g. 1 on a machine short of RAM).
def _max_heavy() -> int:
    raw = os.environ.get("OHM_MAX_HEAVY", "").strip()
    return int(raw) if raw.isdigit() and int(raw) > 0 else 2


MAX_HEAVY = _max_heavy()

_sem = threading.BoundedSemaphore(MAX_HEAVY)
_local = threading.local()
_stats_lock = threading.Lock()
_running = 0
_waiting = 0


@contextmanager
def heavy_slot() -> Iterator[None]:
    global _running, _waiting
    depth = getattr(_local, "depth", 0)
    if depth:
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    with _stats_lock:
        _waiting += 1
    try:
        _sem.acquire()
    finally:
        with _stats_lock:
            _waiting -= 1
    with _stats_lock:
        _running += 1
    _local.depth = 1
    try:
        yield
    finally:
        _local.depth = 0
        with _stats_lock:
            _running -= 1
        _sem.release()


def heavy_stats() -> dict[str, int]:
    """Slots in use and handlers queued for one (GET /api/debug/memory)."""
    with _stats_lock:
        return {"max": MAX_HEAVY, "running": _running, "waiting": _waiting}
