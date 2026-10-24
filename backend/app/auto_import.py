"""Auto-import watcher (contract: frontend/src/lib/import/types.ts section 2).

A daemon thread ticks every second. While the `auto_import` config section is enabled with
at least one folder, each tick:

1. scans the folders recursively for hand-history files (.txt / .xml; hidden files and
   folders and the archive folder are skipped) and sums their sizes per folder;
2. picks the files that changed since the last tick or still have unread bytes, using the
   per-file state (size, mtime, byte offset) kept in memory and persisted in the
   `auto_import_files` table, so a restart does not re-read everything;
3. if another import or a rebuild holds the write lock (or a streaming import job is
   registered), skips the tick; otherwise reads what was appended since the offset (a file
   that shrank is re-read from 0) and imports only complete hands: a hand is complete when
   another hand header follows it, or when the file has not changed for
   IDLE_COMPLETE_SECONDS. The offset stays at the start of the last incomplete hand.
   iPoker XML files are read whole once idle. Duplicates are skipped by the import.
4. every ARCHIVE_EVERY_SECONDS, when archiving is on: files untouched for
   ARCHIVE_IDLE_SECONDS whose hands are all in the workspace move to
   `<archive_dir>/<Site>/<YYYY>/<MM>/<DD>/<file name>` (appended if that file exists).
   A file is only removed after its bytes were fully written to the archive.

Changing the config (PUT / DELETE /api/config/auto_import) cancels the tick in progress
(pause / resume below); the next tick uses the new config. Switching auto-import on or off
resets the session counters.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import app.db as app_db
from app.config_sections import _path_key, get_value

log = logging.getLogger(__name__)

TICK_SECONDS = 1.0
IDLE_COMPLETE_SECONDS = 3.0
ARCHIVE_EVERY_SECONDS = 150.0
ARCHIVE_IDLE_SECONDS = 300.0
LARGE_FOLDER_BYTES = 50 * 1024 * 1024
MAX_TICK_BYTES = 8 * 1024 * 1024  # read budget per tick (keeps the write lock short)
RATE_WINDOW_SECONDS = 3600.0
HH_EXTENSIONS = (".txt", ".xml")
STAGING_SUFFIX = ".ohm-archiving"

_now = time.time  # patched in tests


@dataclass(frozen=True)
class FileState:
    size: int
    mtime: float
    offset: int


# ── Module state ──────────────────────────────────────────────────────────

_state_lock = threading.Lock()  # guards _status / _rate (read by the status endpoint)
_status: dict = {}
_rate: deque[tuple[float, int]] = deque()
_files: dict[str, FileState] | None = None  # path -> state; loaded from the DB on first use
_last_archive = 0.0

_cancel_tick = threading.Event()  # set while a config change is being written
_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


def _initial_status() -> dict:
    return {
        "enabled": False, "running": False, "workspace_id": None,
        "session_hands": 0, "last_import_at": None, "watched_files": 0,
        "last_error": None, "large_folders": [],
    }


def reset_state() -> None:
    """Forget everything in memory (tests; the persisted file states reload on next tick)."""
    global _files, _last_archive
    with _state_lock:
        _status.clear()
        _status.update(_initial_status())
        _rate.clear()
    _files = None
    _last_archive = 0.0
    _cancel_tick.clear()


reset_state()


def _set_status(**kw) -> None:
    with _state_lock:
        _status.update(kw)


def _reset_session() -> None:
    with _state_lock:
        _status["session_hands"] = 0
        _status["last_import_at"] = None
        _rate.clear()


def status() -> dict:
    """GET /api/auto-import/status payload (AutoImportStatus)."""
    now = _now()
    with _state_lock:
        while _rate and _rate[0][0] < now - RATE_WINDOW_SECONDS:
            _rate.popleft()
        out = dict(_status)
        out["large_folders"] = [dict(f) for f in _status["large_folders"]]
        out["hands_per_hour"] = sum(n for _, n in _rate)
    return out


def default_archive_dir() -> Path:
    return Path.home() / "Documents" / "OHM Hand Archive"


# ── Config change hooks (api/config.py) ───────────────────────────────────


def pause() -> None:
    """A config change is coming: cancel the tick in progress (it gives up the lock)."""
    _cancel_tick.set()


def resume(old: dict | None, new: dict | None) -> None:
    """The config change is written (new=None: it failed). Switching on/off resets the session."""
    _cancel_tick.clear()
    if old is not None and new is not None and bool(old.get("enabled")) != bool(new.get("enabled")):
        _reset_session()
        _set_status(enabled=bool(new.get("enabled")))
    _wake.set()


# ── Scanning ──────────────────────────────────────────────────────────────


def _is_under(path_key: str, roots: list[str]) -> bool:
    return any(path_key == r or path_key.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def scan(folders: list[str], skip_dirs: list[str] = ()) -> tuple[list[tuple[str, int, float]], dict[str, int]]:
    """Hand-history files under the folders: ([(path, size, mtime)], {folder: total bytes})."""
    skip = [_path_key(os.path.normpath(d)) for d in skip_dirs]
    found: dict[str, tuple[str, int, float]] = {}
    sizes: dict[str, int] = {}
    for folder in folders:
        total = 0
        if not os.path.isdir(folder):
            sizes[folder] = 0
            continue
        for root, dirs, names in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")
                       and not _is_under(_path_key(os.path.join(root, d)), skip)]
            for name in names:
                if name.startswith(".") or not name.lower().endswith(HH_EXTENSIONS):
                    continue
                path = os.path.join(root, name)
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                total += st.st_size
                found.setdefault(_path_key(path), (path, st.st_size, st.st_mtime))
        sizes[folder] = total
    return list(found.values()), sizes


# ── Reading appended hands ────────────────────────────────────────────────


def split_complete(text: str, parser, final: bool) -> tuple[list[str], int]:
    """(complete hand texts, chars consumed). Without `final` the last hand is held back
    (it may still be written) and the consumed count stops at its first character."""
    pieces = parser.split_hands(text)
    if final:
        return [p for p in pieces if p.strip()], len(text)
    if len(pieces) < 2:
        return [], 0
    last = pieces[-1].strip()
    idx = text.rfind(last[:200]) if last else -1
    if idx <= 0:
        return [], 0
    return [p for p in pieces[:-1] if p.strip()], idx


def _clean(hand: str) -> str:
    # Chunks are decoded with surrogateescape (exact byte offsets); hands get 'replace'
    return hand.encode("utf-8", "surrogateescape").decode("utf-8", "replace").strip()


def _whole_file(path: str, parser) -> bool:
    from app.parsers import ipoker
    return parser is ipoker or path.lower().endswith(".xml")


def read_new_hands(path: str, st: FileState | None, size: int, mtime: float, now: float,
                   budget: int = MAX_TICK_BYTES) -> tuple[list[tuple[str, object]], FileState | None, int]:
    """Complete hands appended since the state's offset.

    Returns (hands as (text, parser), new state or None = leave unchanged, bytes read).
    """
    from app.parsers import detect_parser
    idle = now - mtime >= IDLE_COMPLETE_SECONDS
    offset = st.offset if st else 0
    if st is not None and (size < st.size or size < st.offset):
        offset = 0  # the file shrank (rewritten): read it again; duplicates are skipped
    with open(path, "rb") as f:
        head = f.read(4096)
        parser = detect_parser(head.decode("utf-8", "replace")[:500])
        if parser is None:
            # Not (yet) a hand history: wait while it is being written, then ignore it
            # until it changes again
            return [], (FileState(size, mtime, size) if idle else None), len(head)
        if _whole_file(path, parser):
            if not idle:
                return [], None, len(head)
            f.seek(0)
            data = f.read()
            try:
                pieces = parser.split_hands(data.decode("utf-8", "replace"))
            except Exception as e:  # malformed XML: skip until the file changes
                log.warning("Auto-import: cannot split %s: %s", path, e)
                pieces = []
            hands = [(p.strip(), parser) for p in pieces if p.strip()]
            return hands, FileState(len(data), mtime, len(data)), len(data)
        f.seek(offset)
        data = f.read(max(0, min(size - offset, budget)))
    if not data:
        return [], FileState(size, mtime, offset), 0
    final = idle and offset + len(data) >= size
    text = data.decode("utf-8", "surrogateescape")
    pieces, consumed = split_complete(text, parser, final)
    used = len(text[:consumed].encode("utf-8", "surrogateescape"))
    return [(_clean(p), parser) for p in pieces], FileState(size, mtime, offset + used), len(data)


# ── Tick ──────────────────────────────────────────────────────────────────


def _load_states(cur) -> dict[str, FileState]:
    rows = cur.execute('SELECT path, size, mtime, "offset" FROM auto_import_files').fetchall()
    return {p: FileState(int(s), float(m), int(o)) for p, s, m, o in rows}


def _resolve_workspace(cur, workspace_id: int | None) -> int | None:
    if workspace_id is not None:
        row = cur.execute("SELECT id FROM workspaces WHERE id = ?", [workspace_id]).fetchone()
    else:
        row = cur.execute("SELECT MIN(id) FROM workspaces").fetchone()
    return row[0] if row and row[0] is not None else None


def _needs_read(path: str, size: int, mtime: float) -> bool:
    if size == 0:
        return False
    st = _files.get(path)
    return st is None or st.size != size or st.mtime != mtime or st.offset < size


def _busy() -> bool:
    from app.api.import_hands import active_import_jobs
    return app_db.get_rebuild_status()["active"] or active_import_jobs() > 0


def _read_config():
    """(config, workspace id or None, persisted file states loaded)."""
    global _files
    cur = app_db.get_db().cursor()
    try:
        cfg = get_value(cur, "auto_import")
        ws = _resolve_workspace(cur, cfg["workspace_id"]) if cfg["enabled"] else None
        if _files is None:
            _files = _load_states(cur)
    finally:
        cur.close()
    return cfg, ws


def tick(now: float | None = None) -> int:
    """One watcher iteration; returns the number of hands imported."""
    global _last_archive
    now = _now() if now is None else now
    if app_db.shutdown_requested() or _busy():
        return 0  # a rebuild / streaming import runs: don't even read (its turn ends soon)
    cfg, ws = _read_config()
    _set_status(enabled=cfg["enabled"], workspace_id=ws if cfg["enabled"] else cfg["workspace_id"])
    if not cfg["enabled"] or not cfg["folders"]:
        _set_status(watched_files=0, large_folders=[])
        return 0
    if ws is None:
        _set_status(last_error=f"Workspace {cfg['workspace_id']} not found")
        return 0

    archive_root = cfg["archive_dir"] or str(default_archive_dir())
    files, sizes = scan(cfg["folders"], [archive_root] if cfg["archive_enabled"] else [])
    large = sorted(({"path": p, "bytes": b} for p, b in sizes.items() if b > LARGE_FOLDER_BYTES),
                   key=lambda f: -f["bytes"])
    _set_status(watched_files=len(files), large_folders=large)

    candidates = [f for f in files if _needs_read(*f)]
    archive_due = cfg["archive_enabled"] and now - _last_archive >= ARCHIVE_EVERY_SECONDS
    if (not candidates and not archive_due) or _cancel_tick.is_set():
        return 0
    lock = app_db.db_lock()
    if not lock.acquire(blocking=False):
        return 0  # another import / rebuild / write is running: try again next tick
    try:
        # The config may have changed while we scanned
        if _cancel_tick.is_set() or _busy() or _read_config()[0] != cfg:
            return 0
        _set_status(running=True)
        imported = _import_files(candidates, ws, now)
        if archive_due and not _cancel_tick.is_set():
            _last_archive = now
            _archive_pass(files, ws, Path(archive_root), now)
        return imported
    except Exception as e:
        log.exception("Auto-import tick failed")
        _set_status(last_error=str(e) or type(e).__name__)
        return 0
    finally:
        _set_status(running=False)
        lock.release()


def _import_files(candidates: list[tuple[str, int, float]], ws: int, now: float) -> int:
    """Read + import the candidate files (lock held). State advances only after the import."""
    from app.api.import_hands import import_hand_texts
    db = app_db.get_db()
    budget = MAX_TICK_BYTES
    hands: list[tuple[str, object]] = []
    new_states: dict[str, FileState] = {}
    errors: list[str] = []
    for path, size, mtime in candidates:
        if _cancel_tick.is_set() or app_db.shutdown_requested():
            return 0  # cancelled: nothing imported, offsets unchanged
        if budget <= 0:
            break
        try:
            file_hands, state, used = read_new_hands(path, _files.get(path), size, mtime, now, budget)
        except OSError as e:
            errors.append(f"{path}: {e}")
            continue
        budget -= used
        hands.extend(file_hands)
        if state is not None and state != _files.get(path):
            new_states[path] = state

    imported = 0
    if hands:
        result = import_hand_texts(db, hands, ws)
        imported = result["imported"]
    if new_states:
        stamp = datetime.now()
        db.executemany(
            'INSERT OR REPLACE INTO auto_import_files (path, size, mtime, "offset", updated_at) '
            "VALUES (?, ?, ?, ?, ?)",
            [[p, s.size, s.mtime, s.offset, stamp] for p, s in new_states.items()],
        )
        _files.update(new_states)
    with _state_lock:
        if imported:
            _status["session_hands"] += imported
            _status["last_import_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
            _rate.append((now, imported))
        if errors:
            _status["last_error"] = errors[-1]
        elif hands or new_states:
            _status["last_error"] = None
    # finalize_import (inside import_hand_texts) bumped the data generation
    return imported


# ── Archive ───────────────────────────────────────────────────────────────


def _archive_pass(files: list[tuple[str, int, float]], ws: int, root: Path, now: float) -> int:
    moved = 0
    for path, size, mtime in files:
        st = _files.get(path)
        if st is None or st != FileState(size, mtime, size) or now - mtime < ARCHIVE_IDLE_SECONDS:
            continue
        if _cancel_tick.is_set():
            break
        try:
            if archive_file(path, size, mtime, ws, root):
                moved += 1
        except Exception as e:
            log.warning("Auto-import: archiving %s failed: %s", path, e)
            _set_status(last_error=f"Archive failed for {path}: {e}")
    return moved


def archive_file(path: str, size: int, mtime: float, ws: int, root: Path) -> bool:
    """Move one fully imported file into the archive (lock held). False = left in place."""
    from app.api.import_hands import _existing_hand_ids
    from app.parsers import detect_parser
    src = Path(path)
    data = src.read_bytes()
    if len(data) != size:
        return False
    text = data.decode("utf-8", "replace")
    parser = detect_parser(text[:500])
    if parser is None:
        return False
    try:
        pieces = [p.strip() for p in parser.split_hands(text) if p.strip()]
    except Exception:
        return False
    ids = [parser.extract_hand_id(p) for p in pieces]
    if not ids or any(i is None for i in ids):
        return False
    db = app_db.get_db()
    if set(ids) - _existing_hand_ids(db, ids, ws):
        return False  # hands not in the DB yet: keep the file
    try:
        played = parser.parse_hand_history(pieces[0]).played_at
    except Exception:
        played = datetime.fromtimestamp(mtime)
    target_dir = root / parser.SITE_NAME / f"{played:%Y}" / f"{played:%m}" / f"{played:%d}"
    target_dir.mkdir(parents=True, exist_ok=True)

    # Take the file out of the watched folder first (atomic rename, hidden so the scan
    # skips it). Fails while the poker client still holds it open on Windows: nothing
    # was copied yet then.
    staging = src.with_name(f".{src.name}{STAGING_SUFFIX}")
    os.replace(src, staging)
    try:
        st = staging.stat()
        if st.st_size != size or st.st_mtime != mtime:
            raise _Changed()
        _write_to_archive(target_dir / src.name, data, xml=_whole_file(path, parser))
    except BaseException as e:
        os.replace(staging, src)  # put it back untouched
        if isinstance(e, _Changed):
            return False
        raise
    os.remove(staging)
    db.execute("DELETE FROM auto_import_files WHERE path = ?", [path])
    _files.pop(path, None)
    return True


class _Changed(Exception):
    pass


def _write_to_archive(target: Path, data: bytes, xml: bool) -> None:
    """Append to an existing archive file (XML: a new numbered file instead, two XML
    documents can't share one file) or write a new one. Never leaves a partial write."""
    if xml:
        n = 2
        while target.exists():
            target = target.with_name(f"{target.stem.rsplit(' (', 1)[0]} ({n}){target.suffix}")
            n += 1
    if target.exists() and target.stat().st_size > 0:
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]  # a BOM mid-file would hide the next hand header
        with open(target, "r+b") as f:
            orig = f.seek(0, os.SEEK_END)
            f.seek(max(0, orig - 2))
            tail = f.read()
            sep = b"" if tail.endswith(b"\n\n") else b"\n" if tail.endswith(b"\n") else b"\n\n"
            try:
                f.seek(orig)
                f.write(sep + data)
                f.flush()
                os.fsync(f.fileno())
                if f.tell() != orig + len(sep) + len(data):
                    raise OSError(f"short write to {target}")
            except BaseException:
                f.truncate(orig)
                raise
        return
    tmp = target.with_name(f".{target.name}.ohm-tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


# ── Thread ────────────────────────────────────────────────────────────────


def _run() -> None:
    while not _stop.is_set():
        try:
            tick()
        except Exception as e:  # never let the watcher die
            log.exception("Auto-import tick failed")
            _set_status(last_error=str(e) or type(e).__name__, running=False)
        _wake.wait(TICK_SECONDS)
        _wake.clear()


def start() -> None:
    """Start the watcher thread (app startup). Idempotent."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True, name="auto-import")
    _thread.start()


def stop(timeout: float = 5.0) -> None:
    """Stop the watcher (app shutdown): cancels the tick in progress and waits for it."""
    global _thread
    _stop.set()
    _cancel_tick.set()
    _wake.set()
    if _thread is not None:
        _thread.join(timeout)
        _thread = None
    _cancel_tick.clear()
