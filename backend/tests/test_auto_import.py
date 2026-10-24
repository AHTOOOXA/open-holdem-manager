"""Auto-import watcher (app/auto_import.py, contract: frontend/src/lib/import/types.ts §2).

Most tests call tick() directly with an explicit `now`: a file whose mtime is less than
IDLE_COMPLETE_SECONDS before `now` is still being written (its last hand is held back).
"""

import os
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.import_hands as ih
import app.db as app_db
from app import auto_import as ai
from app import data_generation
from app import config_sections as cs
from app.main import app
from app.parsers import ggpoker, ipoker

FIXTURES = Path(__file__).parent / "fixtures"
HANDS = [h.strip() for h in ggpoker.split_hands((FIXTURES / "ggpoker" / "h2n_parity_r1.txt").read_text())
         if h.strip()]


def _join(hands: list[str]) -> str:
    return "".join(h + "\n\n\n" for h in hands)


@pytest.fixture
def folder(db, monkeypatch, tmp_path):
    monkeypatch.setattr(app_db, "_conn", db)
    ai.reset_state()
    d = tmp_path / "GG HH"
    d.mkdir()
    yield d
    ai.stop()
    ai.reset_state()


def _enable(db, folder, **kw):
    cfg = {"enabled": True, "workspace_id": None, "folders": [str(folder)],
           "archive_enabled": False, "archive_dir": None, **kw}
    cs.put_value(db, "auto_import", cfg)


def _ids(db) -> set[str]:
    return {r[0] for r in db.execute("SELECT id FROM hands").fetchall()}


def _idle(path: Path) -> float:
    """A `now` at which the file counts as idle (unchanged for > 3 s)."""
    return path.stat().st_mtime + ai.IDLE_COMPLETE_SECONDS + 0.5


def _busy(path: Path) -> float:
    return path.stat().st_mtime + 0.1


def _state(db, path: Path):
    return db.execute('SELECT size, "offset" FROM auto_import_files WHERE path = ?', [str(path)]).fetchone()


@pytest.fixture
def spy(monkeypatch):
    """Records how many hand texts each import call got."""
    calls: list[int] = []
    real = ih.import_hand_texts

    def wrapped(db, hands, ws, **kw):
        calls.append(len(hands))
        return real(db, hands, ws, **kw)

    monkeypatch.setattr(ih, "import_hand_texts", wrapped)
    return calls


def test_new_file_imported_within_two_ticks(db, folder):
    _enable(db, folder)
    f = folder / "table1.txt"
    f.write_text(_join(HANDS[:3]))
    gen = data_generation.current()
    assert ai.tick(now=_busy(f)) == 2  # the last hand may still be written
    assert data_generation.current() > gen
    assert _ids(db) == {ggpoker.extract_hand_id(h) for h in HANDS[:2]}
    assert ai.tick(now=_idle(f)) == 1  # unchanged for 3 s: complete
    assert _ids(db) == {ggpoker.extract_hand_id(h) for h in HANDS[:3]}
    assert _state(db, f) == (f.stat().st_size, f.stat().st_size)
    assert ai.tick(now=_idle(f) + 1) == 0


def test_append_imports_only_the_new_hands(db, folder, spy):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    ai.tick(now=_idle(f))
    with f.open("a") as fh:
        fh.write(_join(HANDS[3:5]))
    assert ai.tick(now=_idle(f)) == 2
    assert spy == [3, 2]  # the second read started at the stored offset
    # Restart: state comes back from the table, nothing is re-read
    ai.reset_state()
    assert ai.tick(now=_idle(f) + 5) == 0 and spy == [3, 2]
    assert len(_ids(db)) == 5


def test_partial_hand_waits_for_the_rest(db, folder):
    _enable(db, folder)
    f = folder / "t.txt"
    third = HANDS[2]
    cut = len(third) // 2
    f.write_text(_join(HANDS[:2]) + third[:cut])
    assert ai.tick(now=_busy(f)) == 2
    size, offset = _state(db, f)
    assert offset == len(_join(HANDS[:2]).encode())  # offset at the start of the cut hand
    with f.open("a") as fh:
        fh.write(third[cut:] + "\n\n\n")
    assert ai.tick(now=_busy(f)) == 0  # still the last hand
    assert ai.tick(now=_idle(f)) == 1
    hid = ggpoker.extract_hand_id(third)
    seats = len(ggpoker.parse_hand_history(third).seats)
    assert db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hid]).fetchone()[0] == seats


def test_header_cut_mid_line_keeps_previous_hand_back(db, folder):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:1]) + HANDS[1][:8])  # "Poker Ha"
    assert ai.tick(now=_busy(f)) == 0
    with f.open("a") as fh:
        fh.write(HANDS[1][8:] + "\n\n\n" + HANDS[2][:20])
    assert ai.tick(now=_busy(f)) == 2
    assert _ids(db) == {ggpoker.extract_hand_id(h) for h in HANDS[:2]}


def test_truncated_hand_that_never_completes(db, folder, spy):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]) + HANDS[2][:200])
    assert ai.tick(now=_idle(f)) == 2  # quiet, but the last hand doesn't look finished: held back
    assert _state(db, f)[1] == len(_join(HANDS[:2]).encode())
    assert ai.tick(now=f.stat().st_mtime + 30) == 0
    assert spy == [2]  # unchanged and judged incomplete: not even read again
    # Quiet for a minute: taken as it is (imports what parses, never raises)
    ai.tick(now=f.stat().st_mtime + ai.INCOMPLETE_ACCEPT_SECONDS + 1)
    assert {ggpoker.extract_hand_id(h) for h in HANDS[:2]} <= _ids(db)
    assert _state(db, f)[1] == f.stat().st_size
    assert ai.status()["last_error"] is None


def test_quiet_last_hand_waits_until_it_looks_finished(db, folder):
    """A hand cut after a complete line (e.g. mid-summary) is not imported at 1 s quiet."""
    _enable(db, folder)
    f = folder / "t.txt"
    third = HANDS[2]
    cut = third.index("*** SUMMARY ***") + len("*** SUMMARY ***\n")
    f.write_text(_join(HANDS[:2]) + third[:cut])
    assert ai.tick(now=_idle(f)) == 2
    hid = ggpoker.extract_hand_id(third)
    assert hid not in _ids(db)
    with f.open("a") as fh:
        fh.write(third[cut:] + "\n\n\n")
    assert ai.tick(now=_idle(f)) == 1  # summary complete + final newline, quiet 1 s
    seats = len(ggpoker.parse_hand_history(third).seats)
    assert db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hid]).fetchone()[0] == seats


def test_hand_complete_rules_per_site():
    from app.parsers import partypoker, poker888, pokerstars, winamax, wpn
    for mod, folder_name in [(ggpoker, "ggpoker"), (pokerstars, "pokerstars"), (winamax, "winamax"),
                             (poker888, "poker888"), (wpn, "wpn"), (partypoker, "partypoker")]:
        for path in sorted((FIXTURES / folder_name).glob("*.txt"))[:6]:
            for hand in mod.split_hands(path.read_text(encoding="utf-8", errors="replace")):
                hand = hand.strip()
                if not hand:
                    continue
                assert ai.hand_complete(mod, hand), (folder_name, path.name)
                assert not ai.hand_complete(mod, hand[: len(hand) // 3]), (folder_name, path.name)
    xml = (FIXTURES / "ipoker" / "multi_hand.txt").read_text()
    assert ai.hand_complete(ipoker, xml) and not ai.hand_complete(ipoker, xml[:-20])


def test_shrunk_file_is_read_again(db, folder, spy):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:4]))
    ai.tick(now=_idle(f))
    f.write_text(_join([HANDS[0], HANDS[5]]))  # rewritten, smaller
    os.utime(f, (time.time() + 1, time.time() + 1))
    assert ai.tick(now=_idle(f)) == 1  # HANDS[0] is a duplicate
    assert spy[-1] == 2
    assert ggpoker.extract_hand_id(HANDS[5]) in _ids(db)


def test_disabled_or_no_folders_does_nothing(db, folder):
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    _enable(db, folder, enabled=False)
    assert ai.tick(now=_idle(f)) == 0
    _enable(db, folder, folders=[])
    assert ai.tick(now=_idle(f)) == 0
    assert _ids(db) == set() and ai.status()["enabled"] is True and ai.status()["watched_files"] == 0
    cs.reset_value(db, "auto_import")
    assert ai.tick(now=_idle(f)) == 0 and ai.status()["enabled"] is False


def test_recursive_scan_skips_hidden_and_other_files(db, folder):
    _enable(db, folder)
    (folder / "2026" / "01").mkdir(parents=True)
    (folder / ".hidden").mkdir()
    deep = folder / "2026" / "01" / "a.txt"
    deep.write_text(_join(HANDS[:2]))
    (folder / ".hidden" / "b.txt").write_text(_join(HANDS[2:4]))
    (folder / ".c.txt").write_text(_join(HANDS[4:6]))
    (folder / "notes.md").write_text(_join(HANDS[6:8]))
    (folder / "readme.txt").write_text("not a hand history\n")
    ai.tick(now=_idle(deep) + 1)
    assert _ids(db) == {ggpoker.extract_hand_id(h) for h in HANDS[:2]}
    assert ai.status()["watched_files"] == 2  # a.txt, readme.txt


def test_xml_file_read_whole_once_idle(db, folder):
    _enable(db, folder)
    f = folder / "ipoker.xml"
    f.write_bytes((FIXTURES / "ipoker" / "multi_hand.txt").read_bytes())
    assert ai.tick(now=_busy(f)) == 0
    n = ai.tick(now=_idle(f))
    assert n > 1 and db.execute("SELECT COUNT(*) FROM hands WHERE site_id = ?", [ipoker.SITE_ID]).fetchone()[0] == n
    assert ai.tick(now=_idle(f) + 1) == 0


def test_tick_skips_while_the_write_lock_is_held(db, folder):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    held, release = threading.Event(), threading.Event()

    def hold():
        with app_db.db_lock():
            held.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(2)
    try:
        assert ai.tick(now=_idle(f)) == 0  # does not wait for the lock
    finally:
        release.set()
        t.join()
    assert ai.tick(now=_idle(f)) == 2


def test_tick_skips_while_an_import_job_or_rebuild_runs(db, folder, monkeypatch):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    job_id, _ = ih._register_job()
    try:
        assert ai.tick(now=_idle(f)) == 0
    finally:
        ih._finish_job(job_id)
    monkeypatch.setitem(app_db._rebuild_status, "active", True)
    assert ai.tick(now=_idle(f)) == 0
    monkeypatch.setitem(app_db._rebuild_status, "active", False)
    assert ai.tick(now=_idle(f)) == 2


def test_imports_into_the_configured_workspace(db, folder):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Second')")
    _enable(db, folder, workspace_id=2)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    ai.tick(now=_idle(f))
    assert db.execute("SELECT DISTINCT workspace_id FROM hands").fetchall() == [(2,)]
    assert ai.status()["workspace_id"] == 2


# ── archive ─────────────────────────────────────────────────────────


def _archived(root: Path, name: str, day: str = "15") -> Path:
    return root / "GGPoker" / "2026" / "01" / day / name  # HANDS[0] was played 2026/01/15


def test_archive_moves_idle_imported_file_and_appends(db, folder, tmp_path):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[5:7]))  # HANDS[5:9] were all played on 2026/01/09
    other = folder / "sub" / "t.txt"  # same file name and day: appended to the same archive file
    other.parent.mkdir()
    other.write_text(_join(HANDS[7:9]))
    t_idle = max(_idle(f), _idle(other))
    ai.tick(now=t_idle)  # imports; archive pass ran but the files are too recent
    assert f.exists() and other.exists()
    later = t_idle + ai.ARCHIVE_IDLE_SECONDS + ai.ARCHIVE_EVERY_SECONDS
    ai.tick(now=later)
    assert not f.exists() and not other.exists()
    target = _archived(root, "t.txt", day="09")
    archived = [h.strip() for h in ggpoker.split_hands(target.read_text()) if h.strip()]
    assert sorted(archived) == sorted(HANDS[5:9])
    assert db.execute("SELECT COUNT(*) FROM auto_import_files").fetchone()[0] == 0
    assert not list(folder.rglob(".*"))  # no staging leftovers


def test_archive_every_150_seconds_only(db, folder, tmp_path):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "a.txt"
    f.write_text(_join(HANDS[:2]))
    t1 = _idle(f)
    ai.tick(now=t1)  # archive pass at this time (nothing old enough)
    g = folder / "b.txt"
    g.write_text(_join(HANDS[2:4]))
    os.utime(f, (f.stat().st_mtime - 1000, f.stat().st_mtime - 1000))
    ai.tick(now=_idle(g))  # new hands imported; next archive pass not due yet
    assert f.exists()
    ai.tick(now=t1 + ai.ARCHIVE_EVERY_SECONDS)
    assert not f.exists() and g.exists()  # g: touched less than 5 minutes ago


def test_archive_keeps_file_with_hands_not_in_db(db, folder, tmp_path):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    ai.tick(now=_idle(f))
    db.execute("DELETE FROM hand_players WHERE hand_id = ?", [ggpoker.extract_hand_id(HANDS[1])])
    db.execute("DELETE FROM board_cards WHERE hand_id = ?", [ggpoker.extract_hand_id(HANDS[1])])
    db.execute("DELETE FROM hands WHERE id = ?", [ggpoker.extract_hand_id(HANDS[1])])
    ai.tick(now=_idle(f) + 10_000)
    assert f.exists() and not root.exists()


def test_archive_failure_leaves_the_source(db, folder, tmp_path, monkeypatch):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    before = f.read_bytes()
    ai.tick(now=_idle(f))

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(ai, "_write_to_archive", boom)
    ai.tick(now=_idle(f) + 10_000)
    assert f.read_bytes() == before
    assert "disk full" in ai.status()["last_error"]
    assert not list(folder.glob(".*"))


def test_failed_append_is_rolled_back(tmp_path, monkeypatch):
    target = tmp_path / "t.txt"
    target.write_bytes(b"old hands\n")

    def boom(fd):
        raise OSError("io error")

    monkeypatch.setattr(ai.os, "fsync", boom)
    with pytest.raises(OSError):
        ai._write_to_archive(target, b"\xef\xbb\xbfnew hands\n", xml=False)
    assert target.read_bytes() == b"old hands\n"
    monkeypatch.undo()
    ai._write_to_archive(target, b"\xef\xbb\xbfnew hands\n", xml=False)
    assert target.read_bytes() == b"old hands\n\nnew hands\n"  # BOM dropped mid-file


def test_archive_folder_inside_a_watched_folder_is_not_scanned(db, folder):
    root = folder / "Archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    t = _idle(f)
    ai.tick(now=t)
    ai.tick(now=t + 10_000)
    assert _archived(root, "t.txt").exists()
    ai.tick(now=t + 10_001)
    assert ai.status()["watched_files"] == 0  # the archived copy is not watched


# ── status ──────────────────────────────────────────────────────────


def test_status_numbers(db, folder, monkeypatch):
    client = TestClient(app)
    _enable(db, folder)
    monkeypatch.setattr(ai, "LARGE_FOLDER_BYTES", 1000)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:4]))
    t0 = _idle(f)
    ai.tick(now=t0)
    g = folder / "u.txt"
    g.write_text(_join(HANDS[4:6]))
    ai.tick(now=t0 + 1800)  # 30 min later
    monkeypatch.setattr(ai, "_now", lambda: t0 + 3700)  # the first import left the window
    s = client.get("/api/auto-import/status").json()
    assert s["enabled"] is True and s["running"] is False and s["workspace_id"] == 1
    assert s["session_hands"] == 6 and s["hands_per_hour"] == 2
    assert s["watched_files"] == 2 and s["last_error"] is None
    assert s["last_import_at"].startswith("20") and s["last_import_at"].endswith("+00:00")
    size = f.stat().st_size + g.stat().st_size
    assert s["large_folders"] == [{"path": str(folder), "bytes": size}]
    assert set(s) == {"enabled", "running", "workspace_id", "session_hands", "hands_per_hour",
                      "last_import_at", "watched_files", "last_error", "large_folders"}


# ── config ──────────────────────────────────────────────────────────


def test_config_validation(db, folder, monkeypatch, tmp_path):
    client = TestClient(app)
    d = client.get("/api/config/auto_import").json()
    assert d["value"] == {"enabled": False, "workspace_id": None, "folders": [],
                          "archive_enabled": False, "archive_dir": None}
    base = dict(d["value"], enabled=True)
    assert client.put("/api/config/auto_import", json=dict(base, folders=["relative/hh"])).status_code == 422
    assert client.put("/api/config/auto_import", json=dict(base, archive_dir="x")).status_code == 422
    assert client.put("/api/config/auto_import", json=dict(base, workspace_id=99)).status_code == 422
    assert client.put("/api/config/auto_import", json=dict(base, extra=1)).status_code == 422
    monkeypatch.setattr("sys.platform", "darwin")
    r = client.put("/api/config/auto_import", json=dict(base, folders=[
        str(tmp_path / "HH"), str(tmp_path / "hh") + os.sep, str(tmp_path / "Other")]))
    assert r.status_code == 200
    assert r.json()["value"]["folders"] == [str(tmp_path / "HH"), str(tmp_path / "Other")]
    monkeypatch.setattr("sys.platform", "linux")
    r = client.put("/api/config/auto_import", json=dict(base, folders=[str(tmp_path / "HH"), str(tmp_path / "hh")]))
    assert len(r.json()["value"]["folders"]) == 2


def test_reenabling_resets_session_and_applies_next_tick(db, folder):
    client = TestClient(app)
    cfg = {"enabled": True, "workspace_id": None, "folders": [str(folder)],
           "archive_enabled": False, "archive_dir": None}
    assert client.put("/api/config/auto_import", json=cfg).status_code == 200
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    ai.tick(now=_idle(f))
    assert ai.status()["session_hands"] == 2
    client.put("/api/config/auto_import", json=dict(cfg, folders=[str(folder), "/nonexistent/x"]))
    assert ai.status()["session_hands"] == 2  # still enabled: the session continues
    client.put("/api/config/auto_import", json=dict(cfg, enabled=False))
    g = folder / "u.txt"
    g.write_text(_join(HANDS[2:4]))
    assert ai.tick(now=_idle(g)) == 0
    assert ai.status()["enabled"] is False
    client.put("/api/config/auto_import", json=cfg)
    assert ai.status()["session_hands"] == 0
    assert ai.tick(now=_idle(g)) == 2 and ai.status()["session_hands"] == 2
    assert client.delete("/api/config/auto_import").json()["is_default"]
    assert ai.status()["session_hands"] == 0 and ai.status()["enabled"] is False


def test_config_change_cancels_the_tick_in_progress(db, folder):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    ai.pause()
    try:
        assert ai.tick(now=_idle(f)) == 0
    finally:
        ai.resume(None, None)
    assert ai.tick(now=_idle(f)) == 3


# ── the real thread ─────────────────────────────────────────────────


def test_watcher_thread_picks_up_a_new_file_within_two_seconds(db, folder):
    _enable(db, folder)
    ai.start()
    time.sleep(0.2)
    f = folder / "live.txt"
    t0 = time.monotonic()
    f.write_text(_join(HANDS[:3]))
    while ai.status()["session_hands"] < 2 and time.monotonic() - t0 < 5:
        time.sleep(0.05)
    elapsed = time.monotonic() - t0
    ai.stop()
    assert ai.status()["session_hands"] >= 2
    assert elapsed < 2.0, elapsed


def test_app_startup_starts_and_shutdown_stops_the_watcher(db, folder, monkeypatch):
    import app.main as main
    monkeypatch.setattr(app_db, "_shutdown_event", threading.Event())
    monkeypatch.setattr(main, "close_db", lambda: None)
    with TestClient(app):
        assert ai._thread is not None and ai._thread.is_alive()
        thread = ai._thread
    assert ai._thread is None and not thread.is_alive()


def test_player_pass_is_deferred_until_quiet(db, folder, monkeypatch):
    """Ticks import with the light finalize; the workspace-wide pass runs once quiet."""
    calls = []
    real = ih.finalize_import
    monkeypatch.setattr(ih, "finalize_import", lambda d, workspace_id=None: (calls.append(workspace_id), real(d, workspace_id=workspace_id)))
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    t = _idle(f)
    assert ai.tick(now=t) == 3
    assert calls == []
    ai.tick(now=t + 1)
    assert calls == []
    ai.tick(now=t + ai.FINALIZE_QUIET_SECONDS + 1)
    assert calls == [1] or len(calls) == 1


# ── review fixes (M7) ─────────────────────────────────────────────────


def _hid(h: str) -> str:
    return ggpoker.extract_hand_id(h)


def _old(path: Path, seconds: float = 3 * 86400) -> float:
    """Backdate a file's mtime; returns a `now` well past ARCHIVE_IDLE_SECONDS for it."""
    t = time.time() - seconds
    os.utime(path, (t, t))
    return time.time()


def _imported_then_old(path: Path) -> float:
    """Import the file (the first archive pass finds it too recent), then backdate it.
    Returns a `now` at which the next archive pass is due and the file is old."""
    ai.tick(now=_idle(path))
    _old(path)
    return time.time() + ai.ARCHIVE_EVERY_SECONDS + 5


def test_archive_never_takes_a_file_of_the_current_day(db, folder, tmp_path, monkeypatch):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    now = _imported_then_old(f)
    # Pretend the newest hand was played right now: the poker client may still write the file
    real = ggpoker.parse_hand_history
    from datetime import datetime as _dt

    def recent(text):
        p = real(text)
        p.played_at = _dt.fromtimestamp(now)
        return p

    monkeypatch.setattr(ggpoker, "parse_hand_history", recent)
    ai.tick(now=now)
    assert f.exists() and not root.exists()
    monkeypatch.setattr(ggpoker, "parse_hand_history", real)
    ai.tick(now=now + ai.ARCHIVE_EVERY_SECONDS)  # remembered until the day turns
    assert f.exists()
    ai.tick(now=now + 86400 + ai.ARCHIVE_EVERY_SECONDS)
    assert not f.exists() and _archived(root, "t.txt").exists()


def test_archive_keeps_a_source_that_changed_while_copying(db, folder, tmp_path, monkeypatch):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    now = _imported_then_old(f)
    real = ai._write_to_archive

    def and_client_writes(target, data, xml):
        undo = real(target, data, xml)
        with f.open("a") as fh:  # the poker client appends a hand meanwhile
            fh.write(_join(HANDS[2:3]))
        return undo

    monkeypatch.setattr(ai, "_write_to_archive", and_client_writes)
    ai.tick(now=now)
    assert f.read_text() == _join(HANDS[:3])  # never removed
    assert not _archived(root, "t.txt").exists()  # the copy was taken back
    assert not list(folder.rglob(".*")) and not list(root.rglob(".*"))  # no hidden staging / temp files


def test_archive_reads_files_outside_the_write_lock(db, folder, tmp_path, monkeypatch):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    now = _imported_then_old(f)
    owned = []
    real = ai._write_to_archive
    monkeypatch.setattr(ai, "_write_to_archive",
                        lambda *a, **k: (owned.append(app_db._lock._is_owned()), real(*a, **k))[1])
    ai.tick(now=now)
    assert owned == [False] and not f.exists()


def test_non_archivable_file_is_not_read_again_until_it_changes(db, folder, tmp_path, monkeypatch):
    root = tmp_path / "archive"
    _enable(db, folder, archive_enabled=True, archive_dir=str(root))
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    now = _imported_then_old(f)
    hid = _hid(HANDS[1])
    for table in ("hand_players", "board_cards"):
        db.execute(f"DELETE FROM {table} WHERE hand_id = ?", [hid])
    db.execute("DELETE FROM hands WHERE id = ?", [hid])
    calls = []
    real = ai.archive_file
    monkeypatch.setattr(ai, "archive_file", lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1])
    ai.tick(now=now)
    ai.tick(now=now + ai.ARCHIVE_EVERY_SECONDS)
    assert calls == [str(f)] and f.exists()  # remembered: the second pass skipped it
    with f.open("a") as fh:
        fh.write(_join(HANDS[3:4]))
    _old(f)
    ai.tick(now=now + 2 * ai.ARCHIVE_EVERY_SECONDS)  # reads the new hand, then the archive pass
    assert calls == [str(f), str(f)]  # changed: looked at again


def test_leftover_staging_files_are_restored(db, folder):
    _enable(db, folder)
    # 1) original gone: renamed back
    (folder / ".a.txt.ohm-archiving").write_text(_join(HANDS[:1]))
    # 2) original exists without those bytes: appended
    (folder / "b.txt").write_text(_join(HANDS[1:2]))
    (folder / ".b.txt.ohm-archiving").write_text(_join(HANDS[2:3]))
    # 3) original already has them: staged copy dropped, original untouched
    (folder / "c.txt").write_text(_join(HANDS[3:5]))
    (folder / ".c.txt.ohm-archiving").write_text(_join(HANDS[4:5]))
    ai.tick(now=time.time() + 5)
    assert not list(folder.glob(".*"))
    assert (folder / "a.txt").read_text() == _join(HANDS[:1])
    assert _hid(HANDS[2]) in (folder / "b.txt").read_text()
    assert (folder / "c.txt").read_text() == _join(HANDS[3:5])
    assert {_hid(h) for h in HANDS[:5]} <= _ids(db)


def test_archive_append_crash_leaves_the_old_archive_file(tmp_path, monkeypatch):
    target = tmp_path / "t.txt"
    target.write_bytes(b"old hands\n")

    def crash(src, dst):
        raise OSError("power cut")

    monkeypatch.setattr(ai.os, "replace", crash)
    with pytest.raises(OSError):
        ai._write_to_archive(target, b"new hands\n", xml=False)
    assert target.read_bytes() == b"old hands\n"  # never a partial append
    assert [p.name for p in tmp_path.iterdir()] == ["t.txt"]


def test_file_positions_are_per_workspace_and_reset(db, folder):
    client = TestClient(app)
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Second')")
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))
    assert ai.tick(now=_idle(f)) == 3
    # Another target workspace reads the files from the start (its own positions)
    _enable(db, folder, workspace_id=2)
    assert ai.tick(now=_idle(f) + 1) == 3
    rows = db.execute("SELECT workspace_id, \"offset\" FROM auto_import_files ORDER BY 1").fetchall()
    assert rows == [(1, f.stat().st_size), (2, f.stat().st_size)]
    # Clearing the hands forgets the positions: the files come back
    assert client.post("/api/import/clear", params={"workspace_id": 2}).status_code == 200
    assert db.execute("SELECT COUNT(*) FROM auto_import_files WHERE workspace_id = 2").fetchone()[0] == 0
    assert ai.tick(now=_idle(f) + 2) == 3
    # Deleting a workspace drops its rows
    _enable(db, folder)
    ai.tick(now=_idle(f) + 3)
    assert client.delete("/api/workspaces/2").status_code == 200
    assert db.execute("SELECT DISTINCT workspace_id FROM auto_import_files").fetchall() == [(1,)]
    # A restored DB starts over
    ai.forget_all(db)
    assert db.execute("SELECT COUNT(*) FROM auto_import_files").fetchone()[0] == 0
    assert ai.tick(now=_idle(f) + 4) == 0  # all duplicates now, but read again
    assert _state(db, f) is not None


def test_one_bad_hand_does_not_stall_the_rest(db, folder, monkeypatch):
    _enable(db, folder)
    f = folder / "t.txt"
    g = folder / "u.txt"
    f.write_text(_join(HANDS[:3]))
    g.write_text(_join(HANDS[3:5]))
    bad = _hid(HANDS[1])
    real = ih.import_hand_texts

    def flaky(db_, hands, ws, **kw):
        if any(_hid(t) == bad for t, _ in hands):
            raise RuntimeError("constraint violated")
        return real(db_, hands, ws, **kw)

    monkeypatch.setattr(ih, "import_hand_texts", flaky)
    assert ai.tick(now=max(_idle(f), _idle(g))) == 4
    assert _ids(db) == {_hid(h) for h in HANDS[:5]} - {bad}
    err = ai.status()["last_error"]
    assert bad in err and str(f) in err
    assert _state(db, f)[1] == f.stat().st_size  # advanced past it
    assert ai.tick(now=max(_idle(f), _idle(g)) + 1) == 0


def test_systemic_insert_failure_keeps_positions(db, folder, monkeypatch):
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:3]))

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(ih, "import_hand_texts", broken)
    assert ai.tick(now=_idle(f)) == 0
    assert "disk full" in ai.status()["last_error"]
    assert _state(db, f) is None  # nothing advanced: retried next tick
    monkeypatch.undo()


def test_workspace_deleted_during_the_tick_gets_nothing(db, folder, monkeypatch):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Second')")
    _enable(db, folder, workspace_id=2)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    real = ai._resolve_workspace
    calls = []

    def resolve(cur, ws):
        calls.append(ws)
        if len(calls) == 2:  # the check inside the lock: the workspace is gone now
            db.execute("DELETE FROM workspaces WHERE id = 2")
        return real(cur, ws)

    monkeypatch.setattr(ai, "_resolve_workspace", resolve)
    assert ai.tick(now=_idle(f)) == 0
    assert _ids(db) == set()


def test_config_rejects_archive_that_is_or_contains_a_watched_folder(db, folder, tmp_path):
    client = TestClient(app)
    base = {"enabled": True, "workspace_id": None, "archive_enabled": True}
    put = lambda **kw: client.put("/api/config/auto_import", json={**base, **kw}).status_code
    assert put(folders=[str(folder)], archive_dir=str(folder)) == 422
    assert put(folders=[str(folder)], archive_dir=str(folder.parent)) == 422
    assert put(folders=[str(folder / "a" / "b")], archive_dir=str(folder)) == 422
    assert put(folders=[str(folder)], archive_dir=str(folder / "Archive")) == 200  # inside is fine


def test_scan_skips_only_the_archive_tree(db, folder, tmp_path):
    (folder / "sub").mkdir()
    (folder / "sub" / "a.txt").write_text(_join(HANDS[:1]))
    (folder / "Archive" / "x").mkdir(parents=True)
    (folder / "Archive" / "x" / "b.txt").write_text(_join(HANDS[1:2]))
    files, _ = ai.scan([str(folder)], [str(folder / "Archive")])
    assert [Path(p).name for p, _, _ in files] == ["a.txt"]
    # A (legacy, stored before this was rejected) watched folder inside the archive is not
    # watched at all, and says so
    import json
    db.execute("INSERT OR REPLACE INTO settings VALUES ('config.auto_import', ?)", [json.dumps({
        "enabled": True, "workspace_id": None, "folders": [str(folder / "Archive")],
        "archive_enabled": True, "archive_dir": str(folder)})])
    ai.tick(now=time.time() + 5)
    assert ai.status()["watched_files"] == 0 and "inside the archive" in ai.status()["last_error"]


def test_pending_player_pass_survives_a_crash(db, folder, monkeypatch):
    calls = []
    real = ih.finalize_import
    monkeypatch.setattr(ih, "finalize_import", lambda d, workspace_id=None: (calls.append(workspace_id), real(d, workspace_id=workspace_id)))
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    t = _idle(f)
    assert ai.tick(now=t) == 2
    key = ai.PENDING_KEY + "1"
    assert db.execute("SELECT 1 FROM settings WHERE key = ?", [key]).fetchone()
    ai.reset_state()  # the app crashed: memory is gone
    _enable(db, folder, enabled=False)  # even with auto-import switched off since
    ai.tick(now=t + 1)
    assert calls == [1]
    assert db.execute("SELECT 1 FROM settings WHERE key = ?", [key]).fetchone() is None


def test_stop_waits_for_the_lock_to_run_the_pending_pass(db, folder, monkeypatch):
    calls = []
    real = ih.finalize_import
    monkeypatch.setattr(ih, "finalize_import", lambda d, workspace_id=None: (calls.append(workspace_id), real(d, workspace_id=workspace_id)))
    _enable(db, folder)
    f = folder / "t.txt"
    f.write_text(_join(HANDS[:2]))
    ai.tick(now=_idle(f))
    held = threading.Event()

    def hold():
        with app_db.db_lock():
            held.set()
            time.sleep(0.5)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(2)
    ai.stop()
    t.join()
    assert calls == [1]


def test_unchanged_folders_are_not_walked_every_tick(db, folder, monkeypatch):
    _enable(db, folder)
    (folder / "2026").mkdir()
    f = folder / "2026" / "t.txt"
    f.write_text(_join(HANDS[:2]))
    _old(f, 10)
    for d in (folder, folder / "2026"):
        os.utime(d, (time.time() - 10, time.time() - 10))
    walks = []
    real = ai._walk
    monkeypatch.setattr(ai, "_walk", lambda *a: (walks.append(1), real(*a))[1])
    for i in range(5):
        ai.tick(now=time.time() + i)
    assert len(walks) == 1
    with f.open("a") as fh:  # appending: no walk, the known file is stat'ed
        fh.write(_join(HANDS[2:3]))
    ai.tick(now=time.time() + 10)
    assert len(walks) == 1 and _hid(HANDS[2]) in _ids(db)
    (folder / "2026" / "new.txt").write_text(_join(HANDS[3:4]))  # a new file: its folder changed
    ai.tick(now=time.time() + 12)
    assert len(walks) == 2 and _hid(HANDS[3]) in _ids(db)
