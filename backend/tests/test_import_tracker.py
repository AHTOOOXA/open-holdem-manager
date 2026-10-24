"""Import from another tracker's PostgreSQL database (app/importers/tracker_db.py).

No live PostgreSQL: an in-memory sqlite stands in (ATTACH AS information_schema
emulates information_schema.columns). A live test runs only with OHM_TEST_PG_DSN.
"""

import gzip
import json
import os
import sqlite3
import zlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.importers import tracker_db as td
from app.main import app
from app.parsers import ggpoker

FIXTURES = Path(__file__).parent / "fixtures"
PASSWORD = "s3cret-pw"


def _gg_hands(n=3):
    text = (FIXTURES / "ggpoker" / "sample.txt").read_text()
    return [h.strip() for h in ggpoker.split_hands(text) if h.strip()][:n]


class FakeConn:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def query(self, sql, params=()):
        self.last = (sql, params)
        return self.db.execute(sql.replace("%s", "?").replace('"', '"'), params).fetchall()

    def close(self):
        pass


class FakeServer:
    def __init__(self, dbs: dict[str, sqlite3.Connection]):
        self.dbs = dbs

    def list_databases(self):
        return ["postgres", "template1", *self.dbs]

    def open(self, name):
        return FakeConn(self.dbs[name])

    def close(self):
        pass


def _new_db(columns: dict[str, list[tuple[str, str]]]) -> sqlite3.Connection:
    """sqlite db whose information_schema.columns lists the given tables."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("ATTACH ':memory:' AS information_schema")
    db.execute("CREATE TABLE information_schema.columns (table_name, column_name, data_type)")
    for table, cols in columns.items():
        db.execute(f"CREATE TABLE {table} ({', '.join(c for c, _ in cols)})")
        db.executemany("INSERT INTO information_schema.columns VALUES (?,?,?)", [(table, c, t) for c, t in cols])
    return db


def _pt4_db(hands, dates=None, history_col="history"):
    db = _new_db({
        "cash_hand_histories": [("id_hand", "bigint"), (history_col, "text")],
        "cash_hand_summary": [("id_hand", "bigint"), ("date_played", "timestamp")],
    })
    dates = dates or [f"2024-01-0{i + 1} 12:00:00" for i in range(len(hands))]
    for i, (h, d) in enumerate(zip(hands, dates), 1):
        db.execute(f"INSERT INTO cash_hand_histories VALUES (?, ?)", (i, h))
        db.execute("INSERT INTO cash_hand_summary VALUES (?, ?)", (i, d))
    return db


def _hm3_db(values):
    db = _new_db({"handhistories": [("handhistory_id", "bigint"), ("handhistory", "bytea"), ("handtimestamp", "timestamp")]})
    for i, v in enumerate(values, 1):
        db.execute("INSERT INTO handhistories VALUES (?, ?, ?)", (i, v, f"2024-02-0{i} 10:00:00"))
    return db


@pytest.fixture
def server(monkeypatch):
    holder = {}

    def install(dbs):
        holder["s"] = FakeServer(dbs)
        monkeypatch.setattr(td, "connect_server", lambda conn: holder["s"])
    return install


def test_discovery_pt4_and_fallback_column():
    db = FakeConn(_pt4_db(_gg_hands()))
    src = td.discover(db, "pt4")
    assert (src.table, src.text_col, src.date_col, src.date_table) == (
        "cash_hand_histories", "history", "date_played", "cash_hand_summary")
    alt = FakeConn(_pt4_db(_gg_hands(), history_col="hand_history_text"))
    assert td.discover(alt, "pt4").text_col == "hand_history_text"


def test_discovery_none_when_not_tracker():
    other = FakeConn(_new_db({"foo": [("a", "text")]}))
    assert td.discover(other, "pt4") is None
    assert td.discover(other, "hm3") is None


def test_discovery_hm3():
    src = td.discover(FakeConn(_hm3_db([b"x"])), "hm3")
    assert (src.table, src.text_col, src.date_col) == ("handhistories", "handhistory", "handtimestamp")


def test_listing_hides_system_dbs_and_counts(server):
    hands = _gg_hands()
    server({"mypt4": _pt4_db(hands), "unrelated": _new_db({"users": [("id", "int")]}),
            "emptypt4": _pt4_db([])})
    dbs, err = td.list_databases("pt4", td.make_connection("pt4"))
    assert err is None
    assert dbs == [{"name": "mypt4", "hands": len(hands)}]  # empty fails the probe; unrelated has no table


def test_listing_connection_error_has_no_password(monkeypatch):
    def boom(conn):
        raise Exception(f"connection to server failed, password={conn.password}")
    monkeypatch.setattr(td, "connect_server", boom)
    conn = td.make_connection("pt4", password=PASSWORD)
    dbs, err = td.list_databases("pt4", conn)
    assert dbs == [] and err == "Could not connect to localhost:5432"
    assert PASSWORD not in err


def test_redact():
    conn = td.make_connection("pt4", password=PASSWORD)
    assert PASSWORD not in td.redact(f"bad {PASSWORD} here", conn)


def test_stock_credentials():
    assert td.make_connection("pt4").password == "dbpass"
    assert td.make_connection("hm3").password == "postgrespass"
    c = td.make_connection("pt4", host="h", port=1, user="u", password="p")
    assert (c.host, c.port, c.user, c.password) == ("h", 1, "u", "p")
    with pytest.raises(td.TrackerError):
        td.make_connection("h2n4")


def test_decode_variants():
    t = "Poker Hand #RC1: x\nline"
    assert td.decode_text(t) == t
    assert td.decode_text(t.encode()) == t
    assert td.decode_text(memoryview(t.encode())) == t
    assert td.decode_text(gzip.compress(t.encode())) == t
    assert td.decode_text(zlib.compress(t.encode())) == t
    assert td.decode_text(None) is None


def test_date_filter_sql_and_rows(server):
    hands = _gg_hands()
    db = _pt4_db(hands, dates=["2024-01-01 23:59:00", "2024-01-02 00:00:01", "2024-01-03 08:00:00"])
    src = td.discover(FakeConn(db), "pt4")
    sql, params = td.build_query(src, "2024-01-02", "2024-01-02")
    assert "JOIN" in sql and "s.\"date_played\" >= %s" in sql and "< %s" in sql
    assert params == ("2024-01-02", "2024-01-03")
    assert db.execute(sql.replace("%s", "?"), params).fetchall() == [(hands[1],)]
    sql, params = td.build_query(src, None, None)
    assert "WHERE" not in sql and params == ()

    server({"d": db})
    got = list(td.iter_hand_texts("pt4", td.make_connection("pt4"), "d", date_from="2024-01-02"))
    assert got == hands[1:]
    with pytest.raises(td.TrackerError, match="Invalid date"):
        list(td.iter_hand_texts("pt4", td.make_connection("pt4"), "d", date_from="nope"))


def test_hm3_decodes_mixed_values(server):
    hands = _gg_hands()
    server({"hm": _hm3_db([hands[0].encode(), gzip.compress(hands[1].encode()), zlib.compress(hands[2].encode())])})
    got = list(td.iter_hand_texts("hm3", td.make_connection("hm3"), "hm"))
    assert got == hands


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _stream(resp):
    assert resp.status_code == 200, resp.text
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_databases_endpoint(client, server):
    server({"mypt4": _pt4_db(_gg_hands())})
    body = client.get("/api/import/tracker/databases", params={"software": "pt4"}).json()
    assert body == {"software": "pt4", "databases": [{"name": "mypt4", "hands": 3}], "error": None}
    assert client.get("/api/import/tracker/databases", params={"software": "x"}).status_code == 400


def test_databases_endpoint_connection_error(client, monkeypatch):
    def boom(conn):
        raise td.TrackerError("Could not connect to localhost:5432")
    monkeypatch.setattr(td, "connect_server", boom)
    body = client.get("/api/import/tracker/databases", params={"software": "pt4", "password": PASSWORD}).json()
    assert body["databases"] == [] and body["error"] == "Could not connect to localhost:5432"
    assert PASSWORD not in json.dumps(body)


def test_import_end_to_end(client, db, server):
    hands = _gg_hands()
    other = "Some Other Site Hand #1: not a hand we can parse"
    src = _pt4_db(hands + [other], dates=["2024-01-01 10:00:00", "2024-01-02 10:00:00",
                                           "2024-01-03 10:00:00", "2024-01-03 11:00:00"])
    server({"mypt4": src})
    req = {"software": "pt4", "database": "mypt4"}
    done = _stream(client.post("/api/import/tracker", json=req))[-1]
    assert done["type"] == "done", done
    assert done["imported"] == 3 and done["errors"] == 1
    assert db.execute("SELECT COUNT(*) FROM hands").fetchone()[0] == 3

    again = _stream(client.post("/api/import/tracker", json=req))[-1]
    assert again["imported"] == 0 and again["duplicates"] == 3


def test_import_date_range_limits_hands(client, db, server):
    server({"mypt4": _pt4_db(_gg_hands())})
    done = _stream(client.post("/api/import/tracker", params={"date_from": "2024-01-02", "date_to": "2024-01-02"},
                               json={"software": "pt4", "database": "mypt4"}))[-1]
    assert done["imported"] == 1


def test_import_errors_are_400_without_password(client, server, monkeypatch):
    server({"x": _new_db({"foo": [("a", "text")]})})
    r = client.post("/api/import/tracker", json={"software": "pt4", "database": "x", "password": PASSWORD})
    assert r.status_code == 400 and "not a PokerTracker 4 database" in r.json()["detail"]

    def boom(conn):
        raise Exception(f"fatal {conn.password}")
    monkeypatch.setattr(td, "connect_server", boom)
    r = client.post("/api/import/tracker", json={"software": "pt4", "database": "x", "password": PASSWORD})
    assert r.status_code == 400 and PASSWORD not in r.text


@pytest.mark.skipif(not os.environ.get("OHM_TEST_PG_DSN"), reason="needs OHM_TEST_PG_DSN (live PostgreSQL)")
def test_live_postgres_listing():
    """Read-only listing against a real server; DSN like postgresql://user:pw@host:port/db."""
    from urllib.parse import urlparse
    u = urlparse(os.environ["OHM_TEST_PG_DSN"])
    conn = td.Connection(u.hostname or "localhost", u.port or 5432, u.username or "postgres", u.password or "")
    dbs, err = td.list_databases("pt4", conn)
    assert err is None or isinstance(err, str)
    assert isinstance(dbs, list)
