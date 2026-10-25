"""GET /api/debug/memory: where the backend's memory sits (diagnostics for the 11 GB incident).

The question it answers (performance/SUMMARY.md, "The 11 GB"): is a large RSS held by live
Python objects (a cache or a leak) or by freed-but-kept pymalloc arenas (fragmentation)?
Compare `pymalloc.bytes_in_allocated_blocks` (live small objects) with `pymalloc.arena_bytes`
(what pymalloc holds from the OS): close means live objects, far apart means fragmentation.
`caches` says which known in-process cache holds the live objects.

Every probe is defensive: a module refactored by another change (renamed cache, different
container) makes its entry report `null` / an error string, never fails the endpoint.
"""

from __future__ import annotations

import ctypes
import gc
import importlib
import os
import re
import sys
import tempfile
import threading
import time

from fastapi import APIRouter, Query

router = APIRouter()

# (label, module, attribute) of every in-process cache that grows with hand data.
KNOWN_CACHES: tuple[tuple[str, str, str], ...] = (
    ("reports.chain._CACHE", "app.reports.chain", "_CACHE"),
    ("general_popup._RECORDS", "app.api.general_popup", "_RECORDS"),
    ("h2n._SHAPES", "app.h2n", "_SHAPES"),
    ("import_hands._player_cache", "app.api.import_hands", "_player_cache"),
    ("heroes._cache", "app.heroes", "_cache"),
)

_mallocstats_lock = threading.Lock()


# ── Process memory ────────────────────────────────────────────────────────

def _rss_bytes() -> tuple[int | None, int | None]:
    """(current RSS, peak RSS) of this process in bytes; None where the OS won't say."""
    current = peak = None
    try:
        import resource
        maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        peak = int(maxrss) if sys.platform == "darwin" else int(maxrss) * 1024  # Linux: KiB
    except Exception:
        pass
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/self/statm") as f:
                current = int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        elif sys.platform == "darwin":
            current = _darwin_rss()
        elif sys.platform == "win32":
            current, peak = _windows_rss()
    except Exception:
        pass
    return current, peak


def _darwin_rss() -> int | None:
    class TimeValue(ctypes.Structure):
        _fields_ = [("seconds", ctypes.c_int), ("microseconds", ctypes.c_int)]

    class MachTaskBasicInfo(ctypes.Structure):
        _fields_ = [("virtual_size", ctypes.c_uint64), ("resident_size", ctypes.c_uint64),
                    ("resident_size_max", ctypes.c_uint64), ("user_time", TimeValue),
                    ("system_time", TimeValue), ("policy", ctypes.c_int),
                    ("suspend_count", ctypes.c_int)]

    libc = ctypes.CDLL(None)
    task = ctypes.c_uint.in_dll(libc, "mach_task_self_")
    info = MachTaskBasicInfo()
    count = ctypes.c_uint(ctypes.sizeof(info) // ctypes.sizeof(ctypes.c_uint))
    mach_task_basic_info = 20
    if libc.task_info(task, mach_task_basic_info, ctypes.byref(info), ctypes.byref(count)) != 0:
        return None
    return int(info.resident_size)


def _windows_rss() -> tuple[int | None, int | None]:
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

    c = Counters()
    c.cb = ctypes.sizeof(c)
    proc = ctypes.windll.kernel32.GetCurrentProcess()
    if not ctypes.windll.psapi.GetProcessMemoryInfo(proc, ctypes.byref(c), c.cb):
        return None, None
    return int(c.WorkingSetSize), int(c.PeakWorkingSetSize)


# ── pymalloc arenas ───────────────────────────────────────────────────────

_STAT_LINE = re.compile(r"^(#?\s*[^=]+?)\s*=\s*([\d,]+)\s*$")
_ARENA_LINE = re.compile(r"^(\d[\d,]*) arenas \* (\d[\d,]*) bytes/arena\s*=\s*([\d,]+)\s*$")


def _parse_mallocstats(text: str) -> dict:
    """The summary lines of sys._debugmallocstats() as {name: int}."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        m = _ARENA_LINE.match(line)
        if m:
            out["arenas"] = int(m.group(1).replace(",", ""))
            out["arena_bytes"] = int(m.group(3).replace(",", ""))
            continue
        m = _STAT_LINE.match(line)
        if m:
            key = re.sub(r"[^a-z0-9]+", "_", m.group(1).lstrip("#").strip().lower()).strip("_")
            out.setdefault(key, int(m.group(2).replace(",", "")))  # first "Total" = arenas
    return out


def _capture_mallocstats() -> str | None:
    """sys._debugmallocstats() prints to the C-level stderr: point fd 2 at a temp file for
    the call (a few ms). Another thread's stderr output in that window lands in the file
    and is dropped; acceptable for a diagnostics endpoint."""
    fn = getattr(sys, "_debugmallocstats", None)
    if fn is None:
        return None
    with _mallocstats_lock, tempfile.TemporaryFile(mode="w+b") as tmp:
        try:
            sys.stderr.flush()
        except Exception:
            pass
        saved = os.dup(2)
        try:
            os.dup2(tmp.fileno(), 2)
            try:
                fn()
            finally:
                try:
                    ctypes.CDLL(None).fflush(None)
                except Exception:
                    pass
                os.dup2(saved, 2)
        finally:
            os.close(saved)
        tmp.seek(0)
        text = tmp.read().decode("utf-8", "replace")
    return text


def _pymalloc(raw: bool) -> dict | None:
    try:
        text = _capture_mallocstats()
    except Exception as e:  # pragma: no cover - platform specific
        return {"error": f"{type(e).__name__}: {e}"}
    if text is None:
        return None
    stats = _parse_mallocstats(text)
    out: dict = {k: stats.get(k) for k in (
        "arenas_allocated_total", "arenas_reclaimed", "arenas_highwater_mark",
        "arenas_allocated_current", "arenas", "arena_bytes",
        "bytes_in_allocated_blocks", "bytes_in_available_blocks",
        "bytes_lost_to_pool_headers", "bytes_lost_to_quantization",
        "bytes_lost_to_arena_alignment", "total")}
    alloc, arena = out.get("bytes_in_allocated_blocks"), out.get("arena_bytes")
    out["live_fraction"] = round(alloc / arena, 3) if alloc is not None and arena else None
    if raw:
        out["raw"] = text
    return out


# ── Caches ────────────────────────────────────────────────────────────────

def _container(obj):
    """The dict-like that holds a cache's entries (the object itself or a wrapped `_d`)."""
    for attr in (None, "_d", "_data", "data", "_cache"):
        target = obj if attr is None else getattr(obj, attr, None)
        if target is not None and hasattr(target, "__len__") and hasattr(target, "values"):
            return target
    return obj


def _cache_info(module: str, attr: str) -> dict:
    mod = sys.modules.get(module)
    if mod is None:
        try:
            mod = importlib.import_module(module)
        except Exception as e:
            return {"error": f"import failed: {type(e).__name__}"}
    obj = getattr(mod, attr, None)
    if obj is None:
        return {"error": "not found"}
    info: dict = {"type": type(obj).__name__}
    try:
        info["entries"] = len(obj)
    except TypeError:
        try:
            info["entries"] = len(_container(obj))
        except Exception:
            info["entries"] = None
    for name in ("capacity", "max_hands", "max_bytes", "budget_bytes"):
        v = getattr(obj, name, None)
        if isinstance(v, (int, float)):
            info[name] = v
    for name in ("bytes", "nbytes", "total_bytes", "size_bytes"):
        v = getattr(obj, name, None)
        v = v() if callable(v) else v
        if isinstance(v, (int, float)):
            info["bytes"] = v
            break
    values = _snapshot_values(_container(obj))
    if values is not None:
        hands = blobs = 0
        has_hands = has_blobs = False
        for v in values:
            h = getattr(v, "hands", None)
            if h is not None and hasattr(h, "__len__"):
                has_hands = True
                hands += len(h)
            b = getattr(v, "blobs", None)
            if isinstance(b, dict):
                has_blobs = True
                blobs += sum(len(x) for x in b.values() if isinstance(x, (bytes, bytearray, str)))
        if has_hands:
            info["hand_records"] = hands
        if has_blobs:
            info["blob_bytes"] = blobs
    return info


def _snapshot_values(container) -> list | None:
    if not hasattr(container, "values"):
        return None
    for _ in range(3):  # another thread may mutate it mid-copy
        try:
            return list(container.values())
        except RuntimeError:
            continue
        except Exception:
            return None
    return None


# ── Other process state ───────────────────────────────────────────────────

def _gc_info(objects: bool) -> dict:
    out: dict = {
        "enabled": gc.isenabled(),
        "counts": list(gc.get_count()),
        "thresholds": list(gc.get_threshold()),
        "frozen": gc.get_freeze_count(),
        "collections": [s.get("collections") for s in gc.get_stats()],
    }
    if objects:
        # Walks every tracked object: seconds and a big list at multi-GB heaps, so opt-in.
        from collections import Counter
        objs = gc.get_objects()
        out["tracked_objects"] = len(objs)
        out["top_types"] = Counter(type(o).__name__ for o in objs).most_common(25)
        del objs
    return out


def _duckdb_memory() -> dict | None:
    from app.db import get_read_cursor, get_rebuild_status
    if get_rebuild_status().get("active"):
        return None  # the rebuild's write transaction blocks read cursors
    try:
        rows = get_read_cursor().execute(
            "SELECT tag, memory_usage_bytes, temporary_storage_bytes FROM duckdb_memory() "
            "WHERE memory_usage_bytes > 0 OR temporary_storage_bytes > 0 ORDER BY 2 DESC"
        ).fetchall()
        limit = get_read_cursor().execute("SELECT current_setting('memory_limit')").fetchone()[0]
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {
        "memory_limit": limit,
        "total_bytes": sum(int(r[1]) for r in rows),
        "temporary_bytes": sum(int(r[2]) for r in rows),
        "by_tag": {r[0]: int(r[1]) for r in rows},
    }


def _arrow_bytes() -> int | None:
    pa = sys.modules.get("pyarrow")
    try:
        return int(pa.total_allocated_bytes()) if pa is not None else None
    except Exception:
        return None


def _tracemalloc() -> dict | None:
    import tracemalloc
    if not tracemalloc.is_tracing():
        return None
    current, peak = tracemalloc.get_traced_memory()
    return {"current": current, "peak": peak}


@router.get("/debug/memory")
def debug_memory(
    objects: bool = Query(False, description="Count every gc-tracked object by type (slow at large heaps)"),
    raw: bool = Query(False, description="Include the full sys._debugmallocstats() text"),
) -> dict:
    """Process RSS, pymalloc arenas vs live bytes, cache sizes, gc and DuckDB memory."""
    t0 = time.perf_counter()
    rss, max_rss = _rss_bytes()
    from app import concurrency, data_generation
    heavy = getattr(concurrency, "heavy_stats", None)
    out = {
        "pid": os.getpid(),
        "rss_bytes": rss,
        "max_rss_bytes": max_rss,
        "data_generation": data_generation.current(),
        "threads": threading.active_count(),
        "heavy_slots": heavy() if callable(heavy) else None,
        "caches": {label: _cache_info(mod, attr) for label, mod, attr in KNOWN_CACHES},
        "gc": _gc_info(objects),
        "pymalloc": _pymalloc(raw),
        "duckdb": _duckdb_memory(),
        "arrow_allocated_bytes": _arrow_bytes(),
        "tracemalloc": _tracemalloc(),
    }
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out
