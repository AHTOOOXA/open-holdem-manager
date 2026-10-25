"""Limit on CPU-heavy request handlers running at the same time.

Sync endpoints run in anyio's thread pool (40 threads) and share one GIL. Several cold Reports /
Statistics computations at once are slower in total than one after another, and each one holds
its own peak of Python objects, so they also stack memory. Heavy handlers wrap their work in
`heavy_slot()`; at most `MAX_HEAVY` run at once and the rest wait their turn.

The slot is re-entrant per thread: a heavy handler that calls another heavy helper does not
take a second slot (and can't deadlock on itself).
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

MAX_HEAVY = 2

_sem = threading.BoundedSemaphore(MAX_HEAVY)
_local = threading.local()


@contextmanager
def heavy_slot() -> Iterator[None]:
    depth = getattr(_local, "depth", 0)
    if depth:
        _local.depth = depth + 1
        try:
            yield
        finally:
            _local.depth -= 1
        return
    _sem.acquire()
    _local.depth = 1
    try:
        yield
    finally:
        _local.depth = 0
        _sem.release()
