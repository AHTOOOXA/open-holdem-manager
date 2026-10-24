"""Auto-import watcher (contract: frontend/src/lib/import/types.ts section 2).

A daemon thread ticks every TICK_SECONDS. While the `auto_import` config section is enabled
with at least one folder, each tick:

1. lists the hand-history files (.txt / .xml; hidden files and folders and the archive
   folder are skipped) under the folders and sums their sizes per folder. A folder tree is
   walked again only when one of its directories changed (directory mtimes), every
   FULL_SCAN_SECONDS as a safety net, and while a directory changed less than
   RACY_DIR_SECONDS before the last walk (coarse timestamps); otherwise only the known files
   are stat'ed;
2. picks the files that changed since the last tick or still have unread bytes, using the
   per-file state (size, mtime, byte offset) kept in memory and persisted in the
   `auto_import_files` table per (workspace, path), so a restart does not re-read everything;
3. if another import or a rebuild holds the write lock (or a streaming import job is
   registered), skips the tick; otherwise reads what was appended since the offset (a file
   that shrank is re-read from 0) and imports only complete hands: a hand is complete when
   another hand header follows it. The LAST hand of a file counts as complete once the file
   has not changed for IDLE_COMPLETE_SECONDS and the hand ends the way a finished hand of
   its site ends (the parser's hand_complete(), plus a final newline), or once the file has
   not changed for INCOMPLETE_ACCEPT_SECONDS whatever it looks like. The offset stays at
   the start of a held-back hand. iPoker XML files are read whole the same way. Duplicates
   are skipped by the import. A failing batch is retried per file, then per hand: the bad
   hands are named in `last_error` and skipped (positions still advance).
4. new hands get the light finalize at once; the workspace-wide player pass runs once no
   new hands came for FINALIZE_QUIET_SECONDS. "Pass pending" is persisted in settings
   (`auto_import.finalize_pending.<ws>`) so a crash still runs it on the next start.
5. every ARCHIVE_EVERY_SECONDS, when archiving is on: files untouched for
   ARCHIVE_IDLE_SECONDS, fully read, whose newest hand started before the current day's
   start (`day_start_hour`) and whose hands are all in the workspace are copied to
   `<archive_dir>/<Site>/<YYYY>/<MM>/<DD>/<file name>` (appended if that file exists; the
   archive file is always rewritten through a temp file + os.replace, fsync'ed and read
   back), then the source is re-stat'ed (unchanged size / mtime) and removed. Files are
   read outside the write lock; the lock is only taken for the DB check. A file that can't
   be archived is not looked at again until its size / mtime change (or the day turns).

Changing the config (PUT / DELETE /api/config/auto_import) cancels the tick in progress
(pause / resume below); the next tick uses the new config. Switching auto-import on or off
resets the session counters. Clearing a workspace's hands, deleting a workspace and
restoring a DB forget the stored file positions (forget_workspace / forget_all).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import app.db as app_db
from app.config_sections import _path_key, default_archive_dir, get_value

log = logging.getLogger(__name__)

TICK_SECONDS = 0.5
# After auto-imported hands, run the full player pass once no new hands came for this long
FINALIZE_QUIET_SECONDS = 10.0
IDLE_COMPLETE_SECONDS = 1.0
INCOMPLETE_ACCEPT_SECONDS = 60.0  # a last hand that never looks finished is taken after this
ARCHIVE_EVERY_SECONDS = 150.0
ARCHIVE_IDLE_SECONDS = 300.0
LARGE_FOLDER_BYTES = 50 * 1024 * 1024
MAX_TICK_BYTES = 8 * 1024 * 1024  # read budget per tick (keeps the write lock short)
RATE_WINDOW_SECONDS = 3600.0
FULL_SCAN_SECONDS = 30.0
RACY_DIR_SECONDS = 2.0
STOP_LOCK_WAIT_SECONDS = 5.0
HH_EXTENSIONS = (".txt", ".xml")
STAGING_SUFFIX = ".ohm-archiving"  # left by older versions' archiving (recovered at start)
PENDING_KEY = "auto_import.finalize_pending."

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
_files: dict[str, FileState] | None = None  # path -> state of workspace _files_ws (from the DB)
_files_ws: int | None = None
# path -> (size, mtime, looks complete): a held-back last hand already judged at this size/mtime
_held: dict[str, tuple[int, float, bool]] = {}
# path -> (size, mtime, retry at): files the archive pass gave up on
_not_archivable: dict[str, tuple[int, float, float]] = {}
_rows_to_forget: set[str] = set()  # archived paths whose DB rows are still to delete
_recovered: set[str] = set()  # folders already checked for leftover staging files
_last_archive = 0.0
_epoch = 0  # bumped by forget_*: an archive pass in progress drops its in-memory updates

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


_pending_finalize: dict[int, float] = {}  # workspace -> time of the last light-finalized import
_pending_loaded = False


def reset_state() -> None:
    """Forget everything in memory (tests; the persisted file states reload on next tick)."""
    global _files, _files_ws, _last_archive, _pending_loaded, _epoch
    with _state_lock:
        _status.clear()
        _status.update(_initial_status())
        _rate.clear()
    _files = None
    _files_ws = None
    _held.clear()
    _not_archivable.clear()
    _rows_to_forget.clear()
    _recovered.clear()
    _last_archive = 0.0
    _pending_finalize.clear()
    _pending_loaded = False
    _epoch += 1
    _cancel_tick.clear()
    _scanner.trees.clear()


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


# ── Data reset hooks (clear hands, delete workspace, restore DB); caller holds the lock ──


def _forget_memory() -> None:
    global _files, _files_ws, _epoch
    _files = None
    _files_ws = None
    _held.clear()
    _not_archivable.clear()
    _epoch += 1


def forget_workspace(db, workspace_id: int, *, deleted: bool = False) -> None:
    """The workspace's hands were cleared (or it was deleted): read every watched file again."""
    db.execute("DELETE FROM auto_import_files WHERE workspace_id = ?", [workspace_id])
    if deleted:
        db.execute("DELETE FROM settings WHERE key = ?", [PENDING_KEY + str(workspace_id)])
        _pending_finalize.pop(workspace_id, None)
    _forget_memory()


def forget_all(db) -> None:
    """A database was restored: its stored positions don't match its hands; start over."""
    global _pending_loaded
    db.execute("DELETE FROM auto_import_files")
    _pending_finalize.clear()
    _pending_loaded = False  # the restored DB's pending player passes
    _rows_to_forget.clear()
    _forget_memory()


# ── Scanning ──────────────────────────────────────────────────────────────


def _is_under(path_key: str, roots: list[str]) -> bool:
    return any(path_key == r or path_key.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def _walk(folder: str, skip: list[str]) -> tuple[dict[str, float], list[str]]:
    """({directory: mtime}, [file paths]) of a folder tree; directories in `skip` are pruned."""
    dirs: dict[str, float] = {}
    files: list[str] = []
    for root, subdirs, names in os.walk(folder):
        try:
            dirs[root] = os.stat(root).st_mtime
        except OSError:
            continue
        subdirs[:] = [d for d in subdirs if not d.startswith(".")
                      and _path_key(os.path.normpath(os.path.join(root, d))) not in skip]
        for name in names:
            if not name.startswith(".") and name.lower().endswith(HH_EXTENSIONS):
                files.append(os.path.join(root, name))
    return dirs, files


def _folder_problem(folder: str, archive_root: str | None) -> str | None:
    if archive_root and _is_under(_path_key(os.path.normpath(folder)), [_path_key(os.path.normpath(archive_root))]):
        return f"{folder} is inside the archive folder: not watched"
    return None


def scan(folders: list[str], skip_dirs: list[str] = ()) -> tuple[list[tuple[str, int, float]], dict[str, int]]:
    """Hand-history files under the folders: ([(path, size, mtime)], {folder: total bytes}).
    Only the skip_dirs trees themselves are pruned (a folder inside one is not watched)."""
    files, sizes, _ = _scanner.scan(folders, list(skip_dirs), cached=False)
    return files, sizes


@dataclass
class _Tree:
    dirs: dict[str, float]
    files: list[str]
    walked_at: float


class _Scanner:
    def __init__(self):
        self.trees: dict[tuple[str, tuple[str, ...]], _Tree] = {}

    def _stale(self, tree: _Tree, wall: float) -> bool:
        if wall - tree.walked_at >= FULL_SCAN_SECONDS:
            return True
        for d, m in tree.dirs.items():
            if tree.walked_at - m < RACY_DIR_SECONDS:
                return True  # changed right before the walk: a later change may share its mtime
            try:
                if os.stat(d).st_mtime != m:
                    return True
            except OSError:
                return True
        return False

    def scan(self, folders: list[str], skip_dirs: list[str], cached: bool = True):
        """([(path, size, mtime)], {folder: bytes}, [problems])."""
        skip = [_path_key(os.path.normpath(d)) for d in skip_dirs]
        found: dict[str, tuple[str, int, float]] = {}
        sizes: dict[str, int] = {}
        problems: list[str] = []
        wall = time.time()
        live = set()
        for folder in folders:
            total = 0
            sizes[folder] = 0
            problem = next((p for p in (_folder_problem(folder, d) for d in skip_dirs) if p), None)
            if problem:
                problems.append(problem)
                continue
            if not os.path.isdir(folder):
                continue
            key = (folder, tuple(skip))
            live.add(key)
            tree = self.trees.get(key) if cached else None
            if tree is None or self._stale(tree, wall):
                dirs, paths = _walk(folder, skip)
                tree = _Tree(dirs, paths, wall)
                if cached:
                    self.trees[key] = tree
            for path in tree.files:
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                total += st.st_size
                found.setdefault(_path_key(path), (path, st.st_size, st.st_mtime))
            sizes[folder] = total
        if cached:
            for key in list(self.trees):
                if key not in live:
                    del self.trees[key]
        return list(found.values()), sizes, problems


_scanner = _Scanner()
reset_state()


# ── Reading appended hands ────────────────────────────────────────────────


def split_complete(text: str, parser, final: bool, pieces: list[str] | None = None) -> tuple[list[str], int]:
    """(complete hand texts, chars consumed). Without `final` the last hand is held back
    (it may still be written) and the consumed count stops at its first character."""
    if pieces is None:
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


def hand_complete(parser, text: str) -> bool:
    """Does this (last) hand end the way a finished hand of its site ends? Parsers without a
    rule never say so (their last hand waits INCOMPLETE_ACCEPT_SECONDS)."""
    fn = getattr(parser, "hand_complete", None)
    if fn is None:
        return False
    try:
        return bool(fn(text))
    except Exception:
        return False


def _clean(hand: str) -> str:
    # Chunks are decoded with surrogateescape (exact byte offsets); hands get 'replace'
    return hand.encode("utf-8", "surrogateescape").decode("utf-8", "replace").strip()


def _whole_file(path: str, parser) -> bool:
    from app.parsers import ipoker
    return parser is ipoker or path.lower().endswith(".xml")


def read_new_hands(path: str, st: FileState | None, size: int, mtime: float, now: float,
                   budget: int = MAX_TICK_BYTES):
    """Complete hands appended since the state's offset.

    Returns (hands as (text, parser), new state or None = leave unchanged, bytes read,
    held) where held is None, or whether the held-back last hand looks complete.
    """
    from app.parsers import detect_parser
    quiet = now - mtime
    idle = quiet >= IDLE_COMPLETE_SECONDS
    offset = st.offset if st else 0
    if st is not None and (size < st.size or size < st.offset):
        offset = 0  # the file shrank (rewritten): read it again; duplicates are skipped
    with open(path, "rb") as f:
        head = f.read(4096)
        parser = detect_parser(head.decode("utf-8", "replace")[:500])
        if parser is None:
            # Not (yet) a hand history: wait while it is being written, then ignore it
            # until it changes again
            return [], (FileState(size, mtime, size) if idle else None), len(head), None
        if _whole_file(path, parser):
            if not idle:
                return [], None, len(head), None
            f.seek(0)
            data = f.read()
            text = data.decode("utf-8", "replace")
            complete = hand_complete(parser, text)
            if not complete and quiet < INCOMPLETE_ACCEPT_SECONDS:
                return [], None, len(data), False
            try:
                pieces = parser.split_hands(text)
            except Exception as e:  # malformed XML: skip until the file changes
                log.warning("Auto-import: cannot split %s: %s", path, e)
                pieces = []
            hands = [(p.strip(), parser) for p in pieces if p.strip()]
            return hands, FileState(len(data), mtime, len(data)), len(data), None
        f.seek(offset)
        data = f.read(max(0, min(size - offset, budget)))
    if not data:
        return [], FileState(size, mtime, offset), 0, None
    text = data.decode("utf-8", "surrogateescape")
    pieces = parser.split_hands(text)
    at_end = offset + len(data) >= size
    looks_done = at_end and text.endswith("\n") and bool(pieces) and \
        hand_complete(parser, _clean(pieces[-1]))
    final = at_end and idle and (looks_done or quiet >= INCOMPLETE_ACCEPT_SECONDS)
    hands, consumed = split_complete(text, parser, final, pieces)
    used = len(text[:consumed].encode("utf-8", "surrogateescape"))
    held = looks_done if at_end and not final else None
    return [(_clean(p), parser) for p in hands], FileState(size, mtime, offset + used), len(data), held


# ── Tick ──────────────────────────────────────────────────────────────────


def _load_states(cur, workspace_id: int) -> dict[str, FileState]:
    rows = cur.execute('SELECT path, size, mtime, "offset" FROM auto_import_files WHERE workspace_id = ?',
                       [workspace_id]).fetchall()
    return {p: FileState(int(s), float(m), int(o)) for p, s, m, o in rows}


def _resolve_workspace(cur, workspace_id: int | None) -> int | None:
    if workspace_id is not None:
        row = cur.execute("SELECT id FROM workspaces WHERE id = ?", [workspace_id]).fetchone()
    else:
        row = cur.execute("SELECT MIN(id) FROM workspaces").fetchone()
    return row[0] if row and row[0] is not None else None


def _needs_read(path: str, size: int, mtime: float, now: float | None = None) -> bool:
    if size == 0:
        return False
    st = _files.get(path) if _files is not None else None  # None: reset meanwhile, reloaded under the lock
    if st is not None and st.size == size and st.mtime == mtime and st.offset >= size:
        return False  # fully read
    held = _held.get(path)
    if held is not None and held[:2] == (size, mtime) and now is not None:
        # Unchanged since its last hand was held back: due once it may count as complete
        quiet = now - mtime
        return quiet >= INCOMPLETE_ACCEPT_SECONDS or (held[2] and quiet >= IDLE_COMPLETE_SECONDS)
    return True  # new / changed / unread bytes left (read budget)


def _busy() -> bool:
    from app.api.import_hands import active_import_jobs
    return app_db.get_rebuild_status()["active"] or active_import_jobs() > 0


def _load_pending(cur) -> None:
    global _pending_loaded
    if _pending_loaded:
        return
    rows = cur.execute("SELECT key FROM settings WHERE key LIKE ?", [PENDING_KEY + "%"]).fetchall()
    for (key,) in rows:
        try:
            _pending_finalize.setdefault(int(key[len(PENDING_KEY):]), float("-inf"))  # due now
        except ValueError:
            pass
    _pending_loaded = True


def _read_config():
    """(config, workspace id or None); loads the file states of that workspace."""
    global _files, _files_ws
    cur = app_db.get_db().cursor()
    try:
        cfg = get_value(cur, "auto_import")
        _load_pending(cur)
        ws = _resolve_workspace(cur, cfg["workspace_id"]) if cfg["enabled"] else None
        if ws is not None and (_files is None or _files_ws != ws):
            _forget_memory()  # another target workspace: its own positions
            _files = _load_states(cur, ws)
            _files_ws = ws
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
        _finalize_quiet(now)
        return 0
    if ws is None:
        _set_status(last_error=f"Workspace {cfg['workspace_id']} not found")
        return 0

    archive_root = cfg["archive_dir"] or str(default_archive_dir())
    _recover_staging(cfg["folders"])
    files, sizes, problems = _scanner.scan(cfg["folders"], [archive_root] if cfg["archive_enabled"] else [])
    large = sorted(({"path": p, "bytes": b} for p, b in sizes.items() if b > LARGE_FOLDER_BYTES),
                   key=lambda f: -f["bytes"])
    _set_status(watched_files=len(files), large_folders=large)
    if problems:
        _set_status(last_error=problems[0])

    candidates = [f for f in files if _needs_read(*f, now)]
    archive_due = cfg["archive_enabled"] and now - _last_archive >= ARCHIVE_EVERY_SECONDS
    if not candidates and not _cancel_tick.is_set():
        _finalize_quiet(now)
    if (not candidates and not archive_due and not _rows_to_forget) or _cancel_tick.is_set():
        return 0
    imported = 0
    lock = app_db.db_lock()
    if not lock.acquire(blocking=False):
        return 0  # another import / rebuild / write is running: try again next tick
    try:
        # The config (or the workspace) may have changed while we scanned
        if _cancel_tick.is_set() or _busy() or _read_config() != (cfg, ws):
            return 0
        _set_status(running=True)
        _flush_forgotten_rows()
        if candidates:
            imported = _import_files(candidates, ws, now)
    except Exception as e:
        log.exception("Auto-import tick failed")
        _set_status(last_error=str(e) or type(e).__name__)
        return 0
    finally:
        _set_status(running=False)
        lock.release()
    if archive_due and not _cancel_tick.is_set():
        _last_archive = now
        try:
            _archive_pass(files, ws, Path(archive_root), now)
        except Exception as e:
            log.exception("Auto-import: archive pass failed")
            _set_status(last_error=f"Archive failed: {e}")
    return imported


def _finalize_quiet(now: float, wait: float = 0.0) -> None:
    """Run the deferred workspace-wide player pass once auto-import has been quiet a while.
    wait: seconds to wait for the write lock (0 = only if free right now)."""
    from app.api.import_hands import finalize_import
    due = [ws for ws, t in _pending_finalize.items() if now - t >= FINALIZE_QUIET_SECONDS]
    if not due:
        return
    lock = app_db.db_lock()
    if not (lock.acquire(timeout=wait) if wait > 0 else lock.acquire(blocking=False)):
        if wait > 0:
            log.warning("Auto-import: player pass still pending (write lock busy); runs on next start")
        return
    try:
        db = app_db.get_db()
        for ws in due:
            try:
                if db.execute("SELECT 1 FROM workspaces WHERE id = ?", [ws]).fetchone():
                    finalize_import(db, workspace_id=ws)
                db.execute("DELETE FROM settings WHERE key = ?", [PENDING_KEY + str(ws)])
                _pending_finalize.pop(ws, None)
            except Exception:
                log.exception("Auto-import: deferred finalize failed (workspace %s)", ws)
    finally:
        lock.release()


def _flush_forgotten_rows() -> None:
    """Delete the stored states of archived files (lock held)."""
    if not _rows_to_forget:
        return
    paths = list(_rows_to_forget)
    db = app_db.get_db()
    db.executemany("DELETE FROM auto_import_files WHERE path = ?", [[p] for p in paths])
    _rows_to_forget.difference_update(paths)


def _hand_id(text: str, parser) -> str:
    try:
        return parser.extract_hand_id(text) or "?"
    except Exception:
        return "?"


def _import_resilient(db, per_file: list[tuple[str, list]], ws: int) -> tuple[int, list[str], bool]:
    """Import the hands; when the batch fails, retry per file, then per hand, so one bad
    hand doesn't stall everything. Returns (imported, problems naming the skipped hands,
    systemic): systemic = every hand failed and more than one did, which looks like the DB
    (disk full, ...) rather than bad hands; positions must not advance then."""
    from app.api.import_hands import import_hand_texts
    every = [h for _, hands in per_file for h in hands]
    if not every:
        return 0, [], False
    try:
        return import_hand_texts(db, every, ws, full_finalize=False)["imported"], [], False
    except Exception:
        log.exception("Auto-import: batch insert failed, retrying per file")
    imported = 0
    succeeded = 0
    failed = 0
    problems: list[str] = []
    for path, hands in per_file:
        if not hands:
            continue
        try:
            imported += import_hand_texts(db, hands, ws, full_finalize=False)["imported"]
            succeeded += len(hands)
            continue
        except Exception:
            pass
        bad: list[str] = []
        last = ""
        for hand in hands:
            try:
                imported += import_hand_texts(db, [hand], ws, full_finalize=False)["imported"]
                succeeded += 1
            except Exception as e:
                bad.append(_hand_id(*hand))
                failed += 1
                last = str(e) or type(e).__name__
        if bad:
            log.warning("Auto-import: skipped hands %s of %s: %s", bad, path, last)
            problems.append(f"Skipped {len(bad)} hand(s) that could not be imported from {path}: "
                            f"{', '.join(bad[:5])}{' …' if len(bad) > 5 else ''} ({last})")
    if succeeded == 0 and failed > 1:
        return imported, [f"Import failed, will retry: {last}"], True
    return imported, problems, False


def _import_files(candidates: list[tuple[str, int, float]], ws: int, now: float) -> int:
    """Read + import the candidate files (lock held). State advances only after the import."""
    db = app_db.get_db()
    budget = MAX_TICK_BYTES
    per_file: list[tuple[str, list]] = []
    new_states: dict[str, FileState] = {}
    errors: list[str] = []
    for path, size, mtime in candidates:
        if _cancel_tick.is_set() or app_db.shutdown_requested():
            return 0  # cancelled: nothing imported, offsets unchanged
        if budget <= 0:
            break
        try:
            file_hands, state, used, held = read_new_hands(path, _files.get(path), size, mtime, now, budget)
        except OSError as e:
            errors.append(f"{path}: {e}")
            continue
        budget -= used
        per_file.append((path, file_hands))
        if held is None:
            _held.pop(path, None)
        else:
            _held[path] = (size, mtime, held)
        if state is not None and state != _files.get(path):
            new_states[path] = state

    imported, problems, systemic = _import_resilient(db, per_file, ws)
    errors.extend(problems)
    if systemic:
        new_states.clear()  # nothing advances: the same hands are tried again next tick
        for path, _ in per_file:
            _held.pop(path, None)
    if imported:
        _pending_finalize[ws] = now
        db.execute("INSERT OR REPLACE INTO settings VALUES (?, '1')", [PENDING_KEY + str(ws)])
    if new_states:
        stamp = datetime.now()
        db.executemany(
            'INSERT OR REPLACE INTO auto_import_files (workspace_id, path, size, mtime, "offset", updated_at) '
            "VALUES (?, ?, ?, ?, ?, ?)",
            [[ws, p, s.size, s.mtime, s.offset, stamp] for p, s in new_states.items()],
        )
        _files.update(new_states)
    with _state_lock:
        if imported:
            _status["session_hands"] += imported
            _status["last_import_at"] = datetime.fromtimestamp(now, timezone.utc).isoformat(timespec="seconds")
            _rate.append((now, imported))
        if errors:
            _status["last_error"] = errors[-1]
        elif any(h for _, h in per_file) or new_states:
            _status["last_error"] = None
    # light_finalize (inside import_hand_texts) bumped the data generation
    return imported


# ── Archive ───────────────────────────────────────────────────────────────


def _day_start(now: float) -> datetime:
    """Start of the current day (local time, `day_start_hour` applied), naive like played_at."""
    from app.app_settings import get_app_settings
    cur = app_db.get_db().cursor()
    try:
        hour = int(get_app_settings(cur)["day_start_hour"])
    finally:
        cur.close()
    local = datetime.fromtimestamp(now)
    start = local.replace(hour=hour, minute=0, second=0, microsecond=0)
    return start if local >= start else start - timedelta(days=1)


def _archive_pass(files: list[tuple[str, int, float]], ws: int, root: Path, now: float) -> int:
    """Archive the idle, fully imported files of earlier days (write lock NOT held)."""
    moved = 0
    day_start = _day_start(now)
    for path, size, mtime in files:
        if _cancel_tick.is_set() or app_db.shutdown_requested():
            break
        st = _files.get(path) if _files is not None else None
        if st is None or st != FileState(size, mtime, size) or now - mtime < ARCHIVE_IDLE_SECONDS:
            continue
        skip = _not_archivable.get(path)
        if skip is not None and skip[:2] == (size, mtime) and now < skip[2]:
            continue
        epoch = _epoch
        try:
            result = archive_file(path, size, mtime, ws, root, day_start=day_start)
        except Exception as e:
            log.warning("Auto-import: archiving %s failed: %s", path, e)
            _set_status(last_error=f"Archive failed for {path}: {e}")
            continue
        if epoch != _epoch:
            break  # positions were reset meanwhile (clear / restore): stop this pass
        if result is True:
            moved += 1
            if _files is not None:
                _files.pop(path, None)
            _held.pop(path, None)
            _rows_to_forget.add(path)
        elif result is not None:
            _not_archivable[path] = (size, mtime, result)
    if _rows_to_forget:
        lock = app_db.db_lock()
        if lock.acquire(timeout=1.0):
            try:
                _flush_forgotten_rows()
            finally:
                lock.release()
    return moved


def _hands_in_db(ids: list[str], ws: int) -> bool | None:
    """All ids in the workspace? None when the write lock stayed busy (try again later)."""
    from app.api.import_hands import _existing_hand_ids
    lock = app_db.db_lock()
    deadline = time.monotonic() + 2.0
    while not lock.acquire(timeout=0.1):
        if _cancel_tick.is_set() or time.monotonic() > deadline:
            return None
    try:
        return not (set(ids) - _existing_hand_ids(app_db.get_db(), ids, ws))
    finally:
        lock.release()


def archive_file(path: str, size: int, mtime: float, ws: int, root: Path,
                 day_start: datetime | None = None) -> bool | float | None:
    """Move one fully imported file of an earlier day into the archive (write lock not held).

    True = moved. Otherwise the file stays: a float = don't look at it again before that
    time (unless it changes; inf = until it changes), None = try again next pass.
    """
    from app.parsers import detect_parser
    src = Path(path)
    data = src.read_bytes()
    if len(data) != size:
        return None  # changed since the scan: it gets read again first
    text = data.decode("utf-8", "replace")
    parser = detect_parser(text[:500])
    if parser is None:
        return float("inf")
    try:
        pieces = [p.strip() for p in parser.split_hands(text) if p.strip()]
    except Exception:
        return float("inf")
    ids = [parser.extract_hand_id(p) for p in pieces]
    if not ids or any(i is None for i in ids):
        return float("inf")
    # Never a file of the current day: the poker client may still be writing to it
    try:
        newest = parser.parse_hand_history(pieces[-1]).played_at
    except Exception:
        newest = datetime.fromtimestamp(mtime)
    if day_start is not None and newest >= day_start:
        return (day_start + timedelta(days=1)).timestamp()
    in_db = _hands_in_db(ids, ws)
    if in_db is None:
        return None
    if not in_db:
        return float("inf")  # hands not in the DB (failed / deleted): keep the file
    try:
        played = parser.parse_hand_history(pieces[0]).played_at
    except Exception:
        played = datetime.fromtimestamp(mtime)
    target_dir = root / parser.SITE_NAME / f"{played:%Y}" / f"{played:%m}" / f"{played:%d}"
    target_dir.mkdir(parents=True, exist_ok=True)

    undo = _write_to_archive(target_dir / src.name, data, xml=_whole_file(path, parser))
    try:
        st = src.stat()
        if st.st_size != size or st.st_mtime != mtime:
            undo()  # written to meanwhile: keep it here, it is read again first
            return None
        os.remove(src)
    except FileNotFoundError:
        return True  # gone already: its bytes are in the archive
    except BaseException:
        undo()  # e.g. still open in the poker client on Windows: nothing changed
        raise
    return True


def _fsync_dir(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _replace_atomically(target: Path, content: bytes) -> None:
    """Write content to a temp file next to target, fsync, check, os.replace over target.
    A crash leaves either the old target or the new one (plus maybe a hidden temp file)."""
    tmp = target.with_name(f".{target.name}.ohm-tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if tmp.read_bytes() != content:
            raise OSError(f"verification of {tmp} failed")
        os.replace(tmp, target)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    _fsync_dir(target.parent)


def _write_to_archive(target: Path, data: bytes, xml: bool):
    """Append to an existing archive file (XML: a new numbered file instead, two XML
    documents can't share one file) or write a new one. The file is always rewritten
    through a temp file + os.replace, so a crash never leaves a partial copy.
    Returns undo(): puts the archive back the way it was."""
    if xml:
        n = 2
        while target.exists():
            target = target.with_name(f"{target.stem.rsplit(' (', 1)[0]} ({n}){target.suffix}")
            n += 1
    old = target.read_bytes() if target.exists() else None
    if old:
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]  # a BOM mid-file would hide the next hand header
        sep = b"" if old.endswith(b"\n\n") else b"\n" if old.endswith(b"\n") else b"\n\n"
        content = old + sep + data
    else:
        content = data
    _replace_atomically(target, content)
    if target.read_bytes() != content:
        raise OSError(f"verification of {target} failed")

    def undo() -> None:
        if old is None:
            try:
                target.unlink()
            except OSError:
                pass
        else:
            _replace_atomically(target, old)
    return undo


def _recover_staging(folders: list[str]) -> None:
    """Older versions renamed a file to `.<name>.ohm-archiving` while archiving it; a crash
    then left it hidden. Put such files back, never overwriting a file: when the original
    name exists again, append the staged bytes to it unless they are in it already."""
    for folder in folders:
        key = _path_key(folder)
        if key in _recovered or not os.path.isdir(folder):
            continue
        _recovered.add(key)
        for root, _dirs, names in os.walk(folder):
            for name in names:
                if not (name.startswith(".") and name.endswith(STAGING_SUFFIX)):
                    continue
                staged = Path(root) / name
                original = Path(root) / name[1:-len(STAGING_SUFFIX)]
                try:
                    _restore_staged(staged, original)
                    log.info("Auto-import: restored %s from an interrupted archive", original)
                except OSError as e:
                    log.warning("Auto-import: could not restore %s: %s", staged, e)
                    _set_status(last_error=f"Could not restore {original}: {e}")


def _restore_staged(staged: Path, original: Path) -> None:
    if not original.exists():
        os.replace(staged, original)
        return
    data = staged.read_bytes()
    if data and data not in original.read_bytes():
        with open(original, "ab") as f:
            cur = f.tell()
            sep = b"\n\n" if cur else b""
            f.write(sep + (data[3:] if data.startswith(b"\xef\xbb\xbf") else data))
            f.flush()
            os.fsync(f.fileno())
    os.remove(staged)


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
    """Start the watcher thread (app startup). Idempotent. A player pass left pending by a
    crash runs on the first tick."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_run, daemon=True, name="auto-import")
    _thread.start()


def stop(timeout: float = 5.0) -> None:
    """Stop the watcher (app shutdown): cancels the tick in progress and waits for it, then
    runs a pending player pass (waiting up to STOP_LOCK_WAIT_SECONDS for the write lock;
    if it stays busy the pass stays pending in settings and runs on the next start)."""
    global _thread
    _stop.set()
    _cancel_tick.set()
    _wake.set()
    if _thread is not None:
        _thread.join(timeout)
        _thread = None
    _cancel_tick.clear()
    if not app_db.shutdown_requested():
        _finalize_quiet(float("inf"), wait=STOP_LOCK_WAIT_SECONDS)
