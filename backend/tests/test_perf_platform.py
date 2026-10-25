"""Platform perf track: startup catalog probes, workspace delete, request plumbing, limits."""

import duckdb
import pytest

from app import db as app_db
from app.db import init_schema


def _columns(conn) -> dict[str, list[tuple[str, str]]]:
    rows = conn.execute(
        "SELECT table_name, column_name, data_type FROM duckdb_columns() "
        "WHERE database_name = current_database() AND schema_name = current_schema() "
        "ORDER BY table_name, column_index"
    ).fetchall()
    out: dict[str, list[tuple[str, str]]] = {}
    for t, c, ty in rows:
        out.setdefault(t, []).append((c, ty))
    return out


class _Counting:
    """Connection proxy counting catalog reads (the object identity is what init_schema sees)."""

    def __init__(self, conn):
        self._c = conn
        self.catalog_reads = 0
        self.statements = 0

    def execute(self, sql, *args):
        self.statements += 1
        if "duckdb_columns" in sql or "information_schema" in sql:
            self.catalog_reads += 1
        return self._c.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._c, name)


def test_init_schema_reads_the_catalog_once_per_run():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    proxy = _Counting(conn)
    init_schema(proxy)  # a current DB: every column check is answered by one snapshot
    # 1 snapshot + the two config-section migrations that read their own table's columns
    assert proxy.catalog_reads <= 3, proxy.catalog_reads
    conn.close()


# Columns that migrations add to old databases.
_LEGACY = {
    "hand_players": ["all_in_ev_bb", "pot_type", "is_multiway"],
    "hands": ["rit_boards", "is_cashout", "game_mode"],
    "board_cards": ["board_number"],
}


def _strip_columns(conn, table: str, cols: list[str]) -> None:
    """Recreate `table` without `cols`, as an older database would have it."""
    for (name,) in conn.execute(
            "SELECT index_name FROM duckdb_indexes() WHERE table_name = ?", [table]).fetchall():
        conn.execute(f"DROP INDEX {name}")
    conn.execute(f"CREATE TABLE _old AS SELECT * EXCLUDE ({', '.join(cols)}) FROM {table}")
    conn.execute(f"DROP TABLE {table}")
    conn.execute(f"ALTER TABLE _old RENAME TO {table}")


def test_old_database_gets_the_same_columns_as_a_fresh_one():
    from app.h2n.columns import H2N_COLUMNS
    fresh = duckdb.connect(":memory:")
    init_schema(fresh)
    want = _columns(fresh)

    old = duckdb.connect(":memory:")
    init_schema(old)
    legacy = {t: list(c) for t, c in _LEGACY.items()}
    legacy["hand_players"] += [H2N_COLUMNS[0][0], H2N_COLUMNS[-1][0]]
    for table, cols in legacy.items():
        _strip_columns(old, table, cols)
    proxy = _Counting(old)
    init_schema(proxy)
    got = _columns(old)
    # Same column set and types per table (re-added columns go to the end)
    assert {t: sorted(v) for t, v in got.items()} == {t: sorted(v) for t, v in want.items()}
    assert proxy.catalog_reads <= 3
    fresh.close()
    old.close()


def test_fresh_schema_matches_per_column_probing(monkeypatch):
    """The snapshot gives exactly the schema the old one-probe-per-column code gave."""
    snap = duckdb.connect(":memory:")
    init_schema(snap)

    def probe(self, table, column):
        return self.conn.execute(
            "SELECT 1 FROM duckdb_columns() WHERE database_name = current_database() "
            "AND schema_name = current_schema() AND table_name = ? AND column_name = ?",
            [table, column]).fetchone() is not None

    monkeypatch.setattr(app_db._ColumnCatalog, "has", probe)
    probed = duckdb.connect(":memory:")
    init_schema(probed)
    assert _columns(snap) == _columns(probed)
    snap.close()
    probed.close()


def test_add_column_outside_init_schema_still_works():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    app_db._add_column_if_missing(conn, "t", "b", "INTEGER DEFAULT 7")
    app_db._add_column_if_missing(conn, "t", "b", "INTEGER DEFAULT 7")  # idempotent
    conn.execute("INSERT INTO t (a) VALUES (1)")
    assert conn.execute("SELECT a, b FROM t").fetchall() == [(1, 7)]
    conn.close()


def test_catalog_snapshot_sees_tables_created_after_it():
    conn = duckdb.connect(":memory:")
    catalog = app_db._ColumnCatalog(conn)
    assert not catalog.has("later", "x")
    conn.execute("CREATE TABLE later (x INTEGER)")
    assert catalog.has("later", "x")
    conn.close()


# ── Workspace delete (08/F9) ─────────────────────────────────────────────

from pathlib import Path

from fastapi.testclient import TestClient

_GG = Path(__file__).parent / "fixtures" / "ggpoker" / "sample.txt"
_WS_TABLES = ("hands", "hand_players", "board_cards", "actions", "hand_tags", "hand_notes",
              "player_aliases", "checkpoints", "hero_accounts", "player_classifications",
              "marked_hands", "auto_import_files")


def _load(db, workspace_id):
    from app.api.import_hands import insert_parsed_hand
    from app.parsers.ggpoker import parse_hand_history
    text = _GG.read_text()
    for hand in [h.strip() for h in text.split("\n\n\n") if h.strip()]:
        insert_parsed_hand(db, parse_hand_history(hand), workspace_id=workspace_id)


def _ws_counts(db, workspace_id):
    return {t: db.execute(f"SELECT COUNT(*) FROM {t} WHERE workspace_id = ?",
                          [workspace_id]).fetchone()[0] for t in _WS_TABLES}


@pytest.fixture
def ws_client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    client = TestClient(app_main.app)
    ws = client.post("/api/workspaces", json={"name": "W2", "hero_username": "Hero", "hero_site": "GG"}).json()["id"]
    _load(db, 1)
    _load(db, ws)
    hid = db.execute("SELECT id FROM hands WHERE workspace_id = ? LIMIT 1", [ws]).fetchone()[0]
    pid = db.execute("SELECT player_id FROM hand_players WHERE workspace_id = ? LIMIT 1", [ws]).fetchone()[0]
    db.execute("INSERT INTO hand_tags (hand_id, tag, workspace_id) VALUES (?, 'x', ?)", [hid, ws])
    db.execute("INSERT INTO hand_notes (hand_id, note, workspace_id) VALUES (?, 'n', ?)", [hid, ws])
    db.execute("INSERT INTO checkpoints (id, workspace_id, name, checkpoint_at) VALUES (99, ?, 'c', now())", [ws])
    db.execute("INSERT OR IGNORE INTO player_classifications (player_id, workspace_id, player_type) VALUES (?, ?, 'UNK')", [pid, ws])
    db.execute("INSERT INTO marked_hands (workspace_id, player_id, hand_id) VALUES (?, ?, ?)", [ws, pid, hid])
    db.execute("INSERT INTO auto_import_files (workspace_id, path, size, mtime, \"offset\") VALUES (?, '/x', 1, 1, 1)", [ws])
    return client, db, ws


import app.main as app_main  # noqa: E402


def test_delete_workspace_removes_every_row_and_keeps_others(ws_client):
    from app import data_generation
    client, db, ws = ws_client
    before_other = _ws_counts(db, 1)
    assert _ws_counts(db, ws)["hands"] > 0 and _ws_counts(db, ws)["marked_hands"] == 1
    gen = data_generation.current()
    assert client.delete(f"/api/workspaces/{ws}").status_code == 200
    assert all(v == 0 for v in _ws_counts(db, ws).values()), _ws_counts(db, ws)
    assert _ws_counts(db, 1) == before_other
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE id = ?", [ws]).fetchone()[0] == 0
    assert data_generation.current() > gen


def test_delete_workspace_is_atomic(ws_client, monkeypatch):
    client, db, ws = ws_client
    before = _ws_counts(db, ws)

    def boom(conn, workspace_id):
        raise RuntimeError("disk full")

    monkeypatch.setattr("app.marked_hands.delete_workspace_marks", boom)
    with pytest.raises(RuntimeError):
        client.delete(f"/api/workspaces/{ws}")
    assert _ws_counts(db, ws) == before
    assert db.execute("SELECT COUNT(*) FROM workspaces WHERE id = ?", [ws]).fetchone()[0] == 1
    # The connection is usable again (no transaction left open)
    monkeypatch.undo()
    monkeypatch.setattr(app_db, "_conn", db)
    assert client.delete(f"/api/workspaces/{ws}").status_code == 200


# ── Cursor cleanup middleware (08/F10) ───────────────────────────────────

def _closed(cursor) -> bool:
    try:
        cursor.execute("SELECT 1")
        return False
    except duckdb.Error:
        return True


@pytest.fixture
def cursor_app(db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse

    monkeypatch.setattr(app_db, "_conn", db)
    seen: list = []
    test_app = FastAPI()
    test_app.add_middleware(app_main.CursorCleanupMiddleware)

    @test_app.get("/plain")
    def plain():
        cur = app_db.get_read_cursor()
        seen.append(cur)
        return {"n": cur.execute("SELECT 1").fetchone()[0]}

    @test_app.get("/stream")
    def stream():
        first = app_db.get_read_cursor()
        seen.append(first)

        def gen():
            yield b'{"step": 1}\n'
            later = app_db.get_read_cursor()  # opened after the headers went out
            seen.append(later)
            yield (f'{{"n": {later.execute("SELECT 2").fetchone()[0]}}}\n').encode()

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    return TestClient(test_app), seen


def test_plain_response_cursors_are_closed(cursor_app):
    client, seen = cursor_app
    assert client.get("/plain").json() == {"n": 1}
    assert len(seen) == 1 and _closed(seen[0])
    assert app_db._request_cursors.get(None) is None


def test_streaming_response_cursors_are_closed(cursor_app):
    client, seen = cursor_app
    resp = client.get("/stream")
    assert resp.text.splitlines() == ['{"step": 1}', '{"n": 2}']
    assert len(seen) == 2
    assert all(_closed(c) for c in seen), [(_closed(c)) for c in seen]


def test_app_uses_the_pure_asgi_cursor_middleware():
    from starlette.middleware.base import BaseHTTPMiddleware
    classes = [m.cls for m in app_main.app.user_middleware]
    assert app_main.CursorCleanupMiddleware in classes
    assert not any(isinstance(c, type) and issubclass(c, BaseHTTPMiddleware) for c in classes)


# ── DuckDB limits (08/F12) ───────────────────────────────────────────────

def test_duckdb_limits_default_and_overrides(monkeypatch):
    monkeypatch.delenv("OHM_DUCKDB_MEMORY_LIMIT", raising=False)
    monkeypatch.delenv("OHM_DUCKDB_THREADS", raising=False)
    assert app_db.duckdb_limits() == {"memory_limit": "2GB"}
    monkeypatch.setenv("OHM_DUCKDB_MEMORY_LIMIT", "3.5 GiB")
    monkeypatch.setenv("OHM_DUCKDB_THREADS", "4")
    assert app_db.duckdb_limits() == {"memory_limit": "3.5GiB", "threads": "4"}
    monkeypatch.setenv("OHM_DUCKDB_MEMORY_LIMIT", "2GB'; DROP TABLE hands; --")
    monkeypatch.setenv("OHM_DUCKDB_THREADS", "lots")
    assert app_db.duckdb_limits() == {"memory_limit": "2GB"}


def test_duckdb_limits_are_applied(monkeypatch):
    monkeypatch.setenv("OHM_DUCKDB_MEMORY_LIMIT", "768MB")
    monkeypatch.setenv("OHM_DUCKDB_THREADS", "3")
    conn = duckdb.connect(":memory:")
    app_db._apply_duckdb_limits(conn)
    mem, threads = conn.execute(
        "SELECT current_setting('memory_limit'), current_setting('threads')").fetchone()
    assert threads == 3
    assert mem.replace(" ", "") in ("732.4MiB", "768.0MB", "732.4MB")  # DuckDB prints MiB
    conn.close()
