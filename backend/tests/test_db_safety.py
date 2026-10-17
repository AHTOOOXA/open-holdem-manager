"""Regression tests for the P0 data-safety bugs from BUGS-FROM-FORK.md (#2, #3, #4)
and the graceful shutdown endpoint (#1)."""

import os
import subprocess
import sys
import threading
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.api.import_hands as ih
import app.db as app_db
from app.api.import_hands import _process_hands, _run_rebuild_sync, insert_parsed_hand
from app.main import app
from app.parsers.ggpoker import parse_hand_history

FIXTURES = Path(__file__).parent / "fixtures" / "ggpoker"


def _sample_hands() -> list[str]:
    text = (FIXTURES / "sample.txt").read_text()
    return [h.strip() for h in text.split("\n\n\n") if h.strip()]


@pytest.fixture
def loaded_db(db):
    for hand in _sample_hands():
        insert_parsed_hand(db, parse_hand_history(hand))
    return db


def _counts(db) -> dict[str, int]:
    return {
        t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("hands", "hand_players", "board_cards", "player_classifications")
    }


# ── #3: the DB lock is reentrant ─────────────────────────────────────

def test_close_db_under_db_lock_does_not_deadlock(monkeypatch):
    monkeypatch.setattr(app_db, "_conn", None)
    done = threading.Event()

    def worker():
        with app_db.db_lock():
            app_db.close_db()
        done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    assert done.wait(5), "close_db() deadlocked while db_lock() was held"


# ── #4: a failed rebuild leaves the stats tables intact ──────────────

def test_failed_rebuild_rolls_back(loaded_db, monkeypatch):
    db = loaded_db
    ih.finalize_import(db)
    before = _counts(db)
    assert before["hand_players"] > 0

    monkeypatch.setattr(ih, "BATCH_SIZE", 1)
    real_flush = ih._flush_batch
    calls = {"n": 0}

    def flaky_flush(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_flush(*args, **kwargs)

    monkeypatch.setattr(ih, "_flush_batch", flaky_flush)
    with pytest.raises(RuntimeError, match="boom"):
        _run_rebuild_sync(db)

    assert _counts(db) == before
    # Connection is usable again (not stuck in an aborted transaction)
    db.execute("BEGIN TRANSACTION")
    db.execute("COMMIT")


def test_rebuild_reproduces_same_rows(loaded_db):
    db = loaded_db
    ih.finalize_import(db)
    before = _counts(db)
    _run_rebuild_sync(db)
    assert _counts(db) == before


def test_rebuild_stops_and_rolls_back_on_shutdown(loaded_db, monkeypatch):
    db = loaded_db
    before = _counts(db)
    monkeypatch.setattr(ih, "shutdown_requested", lambda: True)
    with pytest.raises(ih.ShutdownInProgress):
        _run_rebuild_sync(db)
    assert _counts(db) == before


# ── Insert errors inside the import transaction are not swallowed ───

def test_failed_import_batch_rolls_back_whole_import(db, monkeypatch):
    """DuckDB silently turns COMMIT into ROLLBACK after an error, so a swallowed
    batch error used to report success while discarding the whole import."""
    monkeypatch.setattr(ih, "BATCH_SIZE", 1)
    real_insert = ih._insert_arrays
    calls = {"n": 0}

    def flaky_insert(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise duckdb.ConstraintException("boom")
        return real_insert(*args, **kwargs)

    monkeypatch.setattr(ih, "_insert_arrays", flaky_insert)
    text = "\n\n\n".join(_sample_hands())
    with pytest.raises(duckdb.ConstraintException):
        _process_hands(db, [text])

    assert _counts(db)["hands"] == 0
    # Retry works: no stale player IDs left in the import cache
    monkeypatch.setattr(ih, "_insert_arrays", real_insert)
    result = _process_hands(db, [text])
    assert result.imported == len(_sample_hands())


def test_bulk_write_restores_auto_checkpoint(db):
    query = "SELECT current_setting('checkpoint_threshold')"
    default = db.execute(query).fetchone()[0]
    with ih._bulk_write(db):
        assert db.execute(query).fetchone()[0] != default
    assert db.execute(query).fetchone()[0] == default


# ── #2: a WAL that can't be replayed is moved aside ──────────────────

_WRITE_AND_CRASH = r'''
import duckdb, os, sys
c = duckdb.connect(sys.argv[1])
c.execute("SET checkpoint_threshold='10GB'")
c.execute("CREATE TABLE t AS SELECT range i, 'x' || range s FROM range(50000)")
c.execute("INSERT INTO t SELECT range, 'y' FROM range(1000)")
os._exit(0)  # no close, no checkpoint: leaves a WAL
'''


def test_corrupt_wal_is_quarantined(tmp_path, monkeypatch):
    db_path = tmp_path / "poker.duckdb"
    subprocess.run([sys.executable, "-c", _WRITE_AND_CRASH, str(db_path)], check=True)
    wal = tmp_path / "poker.duckdb.wal"
    assert wal.exists()
    size = wal.stat().st_size
    with open(wal, "r+b") as f:
        f.seek(size // 2)
        f.write(os.urandom(256))

    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    monkeypatch.setattr(app_db, "_wal_recovery", None)
    conn = app_db._connect_with_recovery()
    try:
        conn.execute("SELECT 1").fetchone()
    finally:
        conn.close()

    quarantined = list(tmp_path.glob("poker.duckdb.wal.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].stat().st_size == size
    assert app_db.get_wal_recovery()["quarantined_wal"] == str(quarantined[0])


# ── #1: shutdown endpoint ────────────────────────────────────────────

class _FakeServer:
    should_exit = False


@pytest.fixture
def shutdown_client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    monkeypatch.setattr(app_db, "_shutdown_event", threading.Event())
    server = _FakeServer()
    monkeypatch.setattr(app.state, "server", server, raising=False)
    return TestClient(app), server


def test_shutdown_requires_token(shutdown_client, monkeypatch):
    client, server = shutdown_client
    monkeypatch.delenv("OHM_SHUTDOWN_TOKEN", raising=False)
    assert client.post("/api/shutdown", headers={"X-OHM-Shutdown-Token": ""}).status_code == 403

    monkeypatch.setenv("OHM_SHUTDOWN_TOKEN", "secret")
    assert client.post("/api/shutdown").status_code == 403
    assert client.post("/api/shutdown", headers={"X-OHM-Shutdown-Token": "wrong"}).status_code == 403
    assert not server.should_exit
    assert not app_db.shutdown_requested()


def test_shutdown_with_token_stops_server(shutdown_client, monkeypatch):
    client, server = shutdown_client
    monkeypatch.setenv("OHM_SHUTDOWN_TOKEN", "secret")
    resp = client.post("/api/shutdown", headers={"X-OHM-Shutdown-Token": "secret"})
    assert resp.status_code == 200
    assert server.should_exit
    assert app_db.shutdown_requested()


# ── #20: export goes through DuckDB, not a file copy ─────────────────

def test_export_produces_a_complete_database(monkeypatch, tmp_path):
    db_path = tmp_path / "poker.duckdb"
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    monkeypatch.setattr(ih, "DB_PATH", db_path)
    monkeypatch.setattr(app_db, "_conn", None)
    ih.reset_import_cache()
    db = app_db.get_db()
    try:
        for hand in _sample_hands():
            insert_parsed_hand(db, parse_hand_history(hand))
        before = _counts(db)

        resp = TestClient(app).get("/api/import/export")
        assert resp.status_code == 200
        out = tmp_path / "backup.duckdb"
        out.write_bytes(resp.content)
        conn = duckdb.connect(str(out), read_only=True)
        try:
            assert _counts(conn) == before
        finally:
            conn.close()
        # The app's connection was reopened and still works
        assert _counts(app_db.get_db()) == before
    finally:
        app_db.close_db()


# ── #21: tag/note keys include the workspace ─────────────────────────

def test_tag_and_note_keys_are_per_workspace(db):
    db.execute("INSERT INTO hand_tags (hand_id, tag, workspace_id) VALUES ('H1', 'bluff', 1)")
    # Same hand and tag in another workspace is fine
    db.execute("INSERT INTO hand_tags (hand_id, tag, workspace_id) VALUES ('H1', 'bluff', 2)")
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO hand_tags (hand_id, tag, workspace_id) VALUES ('H1', 'bluff', 1)")

    db.execute("INSERT INTO hand_notes (hand_id, note, workspace_id) VALUES ('H1', 'a', 1)")
    db.execute("INSERT INTO hand_notes (hand_id, note, workspace_id) VALUES ('H1', 'b', 2)")
    with pytest.raises(duckdb.ConstraintException):
        db.execute("INSERT INTO hand_notes (hand_id, note, workspace_id) VALUES ('H1', 'c', 1)")


def test_tag_note_key_migration_dedupes_existing_rows(db):
    db.execute("DROP INDEX uq_hand_tags")
    db.execute("DROP INDEX uq_hand_notes")
    db.execute("""INSERT INTO hand_tags (hand_id, tag, created_at, workspace_id) VALUES
        ('H1', 'bluff', TIMESTAMP '2026-01-01', 1), ('H1', 'bluff', TIMESTAMP '2026-01-02', 1),
        ('H1', 'bluff', TIMESTAMP '2026-01-03', 2)""")
    db.execute("""INSERT INTO hand_notes (hand_id, note, updated_at, workspace_id) VALUES
        ('H1', 'old', TIMESTAMP '2026-01-01', 1), ('H1', 'new', TIMESTAMP '2026-01-02', 1)""")
    app_db._ensure_tag_note_keys(db)
    assert db.execute("SELECT COUNT(*) FROM hand_tags").fetchone()[0] == 2
    assert db.execute("SELECT note FROM hand_notes").fetchall() == [("new",)]
    app_db._ensure_tag_note_keys(db)  # idempotent
