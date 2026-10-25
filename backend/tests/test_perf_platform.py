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
