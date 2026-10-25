"""Performance work on the Statistics screen (performance/04-statistics-general.md).

The popup cache (04/F1, F2), its invalidation, and that the faster paths answer exactly
what the old ones did.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import data_generation
from app.api import general_popup as gp
from app.api.import_hands import insert_parsed_hand
from app.general_cells import GENERAL_CELLS, ActionCell
from app.h2n.replay import replay_parsed
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from tests.test_general_popup import _cbet_hands


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    gp.clear_cache()
    yield TestClient(app)
    gp.clear_cache()


def _insert(db, *texts: str) -> None:
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))


def _action_rows() -> dict[str, int]:
    out = {}
    for cid, cell in GENERAL_CELLS.items():
        if isinstance(cell, ActionCell):
            out[cell.ref.row] = gp._resolve(cid).street
    return out


# ── packed records (04/F2) ────────────────────────────────────────────────


def test_packed_records_round_trip_for_every_row():
    seen = 0
    for text in _cbet_hands():
        parsed = parse_hand_history(text)
        seq = replay_parsed(parsed)
        for row, street in _action_rows().items():
            rec = gp._compute_record(parsed, seq, "Hero", row, street)
            assert gp._unpack(gp._pack(rec)) == rec
            seen += rec is not None
    assert seen > 20


def test_packed_record_edge_values():
    rec = gp._Rec(True, ((0, 1, 3), (), (2,)), (None, -1, 13), (4, 31), (0, 1),
                  tuple((b.id, i % 2 == 0) for i, b in enumerate(gp._BUCKETS)))
    assert gp._unpack(gp._pack(rec)) == rec
    empty = gp._Rec(False, (), (), None, None, ())
    v = gp._pack(empty)
    assert v != gp._NONE and gp._unpack(v) == empty
    assert gp._pack(None) == gp._NONE and gp._unpack(gp._NONE) is None


# ── byte-bounded cache (04/F1) ────────────────────────────────────────────


def _items(prefix: str, n: int) -> list[tuple[str, int]]:
    return [(f"{prefix}{i:08d}", (1 << 40) + i) for i in range(n)]


def test_cache_eviction_order():
    c = gp._RecordCache(budget=10**9)
    for k in "abc":
        c.add((k,), _items(k, 500))
    per = c.stats()["bytes"] // 3
    c.budget = per * 2 + per // 2           # room for two and a half segments
    c.max_segment = c.budget
    c.segment(("a",))
    c.add(("d",), _items("d", 500))
    assert c.stats()["bytes"] <= c.budget
    assert c.segment(("b",)) == {} and c.segment(("c",)) == {}
    assert len(c.segment(("a",))) == 500 and len(c.segment(("d",))) == 500


def test_cache_skips_a_segment_that_cannot_fit():
    c = gp._RecordCache(budget=200_000)     # max segment = 100 kB
    c.add(("small",), _items("s", 100))
    c.add(("big",), _items("b", 5000))
    assert c.segment(("big",)) == {}
    assert len(c.segment(("small",))) == 100   # the big one did not flush the rest
    c.add(("big",), _items("b", 10))           # not retried until the next clear
    assert c.segment(("big",)) == {} and c.stats()["skipped"] == 1
    c.clear()
    c.add(("big",), _items("b", 10))
    assert len(c.segment(("big",))) == 10


def test_cache_grows_a_segment_incrementally():
    c = gp._RecordCache(budget=10**9)
    c.add(("a",), _items("a", 10))
    b1 = c.stats()["bytes"]
    c.add(("a",), _items("a", 20))          # 10 known, 10 new
    assert len(c.segment(("a",))) == 20 and c.stats()["bytes"] > b1


# ── invalidation (04/F2, 06/F1) ───────────────────────────────────────────


def test_data_generation_bump_clears_the_popup_cache(client, db):
    _insert(db, *_cbet_hands())
    r = client.get("/api/general/cell/postflop.cbet.Flop/detail")
    assert r.status_code == 200 and r.json()["replayed"] == 5
    assert gp.cache_stats()["records"] == 5
    data_generation.bump()
    assert gp.cache_stats() == {"records": 0, "bytes": 0, "segments": 0, "skipped": 0}
    again = client.get("/api/general/cell/postflop.cbet.Flop/detail").json()
    assert again["replayed"] == 5
    assert again["summary"] == r.json()["summary"]


def test_records_replayed_across_a_data_bump_are_not_cached(client, db, monkeypatch):
    _insert(db, *_cbet_hands())
    real = gp._replay_missing

    def bumping(*a, **kw):
        out = real(*a, **kw)
        data_generation.bump()                 # e.g. a rebuild commits mid-replay
        return out

    monkeypatch.setattr(gp, "_replay_missing", bumping)
    r = client.get("/api/general/cell/postflop.cbet.Flop/detail")
    assert r.status_code == 200 and r.json()["replayed"] == 5
    assert gp.cache_stats()["records"] == 0
    monkeypatch.setattr(gp, "_replay_missing", real)
    again = client.get("/api/general/cell/postflop.cbet.Flop/detail").json()
    assert again["replayed"] == 5 and again["summary"] == r.json()["summary"]
    assert gp.cache_stats()["records"] == 5


def test_cache_is_per_player_and_row(client, db):
    _insert(db, *_cbet_hands())
    client.get("/api/general/cell/postflop.cbet.Flop/detail")
    client.get("/api/general/cell/summary.vpip.Total/detail")
    st = gp.cache_stats()
    assert st["segments"] == 2
    # same row, other cell: shares the segment
    d = client.get("/api/general/cell/preflop.open_raise.Total/detail").json()
    d2 = client.get("/api/general/cell/preflop.open_raise.BTN/detail").json()
    assert d2["replayed"] == 0 and d["cases"] == d2["cases"]


# ── slim detail query + joined blob fetch (04/F3, F5) ────────────────────


_CELLS = ("summary.vpip.Total", "summary.pfr.Total", "preflop.open_raise.Total",
          "preflop.three_bet.Total", "postflop.cbet.Flop", "postflop.fold_to_cbet.Flop",
          "postflop.cbet.Turn")


def _details(client, **params) -> dict:
    out = {}
    for cell in _CELLS:
        r = client.get(f"/api/general/cell/{cell}/detail", params=params)
        assert r.status_code == 200, r.text
        out[cell] = r.json()
    return out


def test_joined_fetch_equals_id_list_fetch(client, db, monkeypatch):
    _insert(db, *_cbet_hands())
    by_ids = _details(client)
    gp.clear_cache()
    monkeypatch.setattr(gp, "_JOIN_FETCH_MIN", 0)
    assert _details(client) == by_ids
    gp.clear_cache()
    filtered = _details(client, date_from="2026-01-01")
    assert {k: v["cases"] for k, v in filtered.items()} == {k: v["cases"] for k, v in by_ids.items()}
    # stored sequences missing: the joined history fetch re-parses
    db.execute("UPDATE hand_players SET h2n_seq = NULL")
    gp.clear_cache()
    assert _details(client) == by_ids


def test_detail_of_a_player_without_hands(client, db):
    _insert(db, *_cbet_hands())
    pid = db.execute("SELECT MAX(id) + 1 FROM players").fetchone()[0]
    db.execute("INSERT INTO players (id, username, site_id) VALUES (?, 'nobody', 1)", [pid])
    d = client.get("/api/general/cell/summary.vpip.Total/detail", params={"player_id": pid}).json()
    assert (d["cases"], d["opps"], d["value"], d["replayed"]) == (0, 0, None, 0)
    assert d["player"] == "nobody"


# ── hands list paging in SQL (04/F10) ────────────────────────────────────


@pytest.mark.parametrize("sort", ["date", "won", "ev"])
@pytest.mark.parametrize("order", ["desc", "asc"])
def test_hand_pages_concatenate_to_the_full_list(client, db, sort, order):
    _insert(db, *_cbet_hands())
    url = "/api/general/cell/summary.vpip.Total/hands"
    full = client.get(url, params={"sort": sort, "order": order, "limit": 512}).json()
    assert full["total"] == 5 and len(full["rows"]) == 5
    paged = []
    for off in range(0, 6, 2):
        page = client.get(url, params={"sort": sort, "order": order, "offset": off, "limit": 2}).json()
        assert page["total"] == 5
        paged += page["rows"]
    assert paged == full["rows"]
    key = {"date": lambda r: (r["played_at"], r["hand_id"]),
           "won": lambda r: (r["won_bb"], r["played_at"], r["hand_id"]),
           "ev": lambda r: (r["ev_diff_bb"], r["played_at"], r["hand_id"])}[sort]
    assert full["rows"] == sorted(full["rows"], key=key, reverse=order == "desc")
    past = client.get(url, params={"offset": 5, "limit": 2}).json()
    assert past["total"] == 5 and past["rows"] == []


# ── opponent view cache (04/F7) and the heavy-handler limit ──────────────


def test_opponent_vs_user_counts_are_cached_until_the_data_changes(client, db, monkeypatch):
    from app.api import general as general_api
    _insert(db, *_cbet_hands())
    general_api.clear_vs_cache()
    pid = db.execute("SELECT id FROM players WHERE username = 'B'").fetchone()[0]
    calls = []
    real = general_api._replay_vs_user
    monkeypatch.setattr(general_api, "_replay_vs_user",
                        lambda *a: calls.append(a) or real(*a))
    first = client.get("/api/general", params={"player_id": pid}).json()
    assert not first["is_hero"] and len(calls) == 1
    assert client.get("/api/general", params={"player_id": pid}).json() == first
    assert len(calls) == 1
    client.get("/api/general", params={"player_id": pid, "date_from": "2026-01-01"})
    assert len(calls) == 2                     # another filter is another entry
    data_generation.bump()
    assert client.get("/api/general", params={"player_id": pid}).json() == first
    assert len(calls) == 3


def test_heavy_endpoints_take_a_slot(client, db, monkeypatch):
    import contextlib
    from app.api import general as general_api
    _insert(db, *_cbet_hands())
    taken = []

    @contextlib.contextmanager
    def fake_slot():
        taken.append(1)
        yield

    monkeypatch.setattr(general_api, "heavy_slot", fake_slot)
    monkeypatch.setattr(gp, "heavy_slot", fake_slot)
    assert client.get("/api/general").status_code == 200
    assert client.get("/api/general/cell/summary.vpip.Total/detail").status_code == 200
    assert client.get("/api/general/cell/summary.vpip.Total/hands").status_code == 200
    assert len(taken) == 3


# ── postflop records from stored columns (04/F4) ─────────────────────────


def _postflop_rows() -> dict[str, int]:
    return {row: street for row, street in _action_rows().items() if street > 0}


def test_stored_postflop_records_equal_reparsed_ones_on_every_site(db):
    """Every fixture hand of every site: for each postflop row and each player with the
    opportunity, the record from the stored sequence + board_cards + hv_<street> is the
    record from re-parsing raw_text; run-it-twice hands are left to the re-parse."""
    from pathlib import Path

    from app.api.import_hands import _process_hands
    from app.h2n.rows import sql_opp
    from app.h2n.seqcodec import decode_sequence

    root = Path(__file__).parent / "fixtures"
    texts = [p.read_text(encoding="utf-8", errors="replace")
             for site in sorted(root.iterdir()) if site.is_dir() and site.name != "money"
             for p in sorted(site.glob("*.txt"))]
    _process_hands(db, texts, 1)
    assert db.execute("SELECT COUNT(DISTINCT site_id) FROM hands").fetchone()[0] >= 5
    rit = {r[0] for r in db.execute("SELECT id FROM hands WHERE rit_boards > 1").fetchall()}
    assert rit
    raw = {h: (t, s) for h, t, s in db.execute("SELECT id, raw_text, site_id FROM hands").fetchall()}
    names = dict(db.execute("SELECT id, username FROM players").fetchall())
    stored_n = 0
    for row, street in _postflop_rows().items():
        for (pid,) in db.execute(
                f"SELECT DISTINCT player_id FROM hand_players hp WHERE {sql_opp(row)} = 1").fetchall():
            scope = gp._Scope(["hp.player_id = ?", "hp.workspace_id = ?",
                               "COALESCE(hp.h2n_valid, TRUE)", f"{sql_opp(row)} = 1"],
                              [pid, 1], "", [])
            sql, params = scope.sql("hp.hand_id")
            ids = [r[0] for r in db.execute(sql, params).fetchall()]
            stored = gp._stored_postflop(db, 1, ids, scope, street)
            assert not set(stored) & rit
            for hid in ids:
                parsed, seq = gp._parse(*raw[hid])
                want = gp._compute_record(parsed, seq, names[pid], row, street)
                if hid in stored:
                    blob, board, val = stored[hid]
                    got = gp._compute_record(None, decode_sequence(blob), names[pid], row, street,
                                             (board, val))
                    assert got == want, (row, hid, names[pid])
                    stored_n += 1
    assert stored_n > 100


def test_postflop_detail_same_with_and_without_stored_columns(client, db, monkeypatch):
    _insert(db, *_cbet_hands())
    calls = []
    real_parse = gp._parse
    monkeypatch.setattr(gp, "_parse", lambda *a: calls.append(a) or real_parse(*a))
    stored = _details(client)
    assert not any(c for c in calls)        # no detail re-parsed a history
    db.execute("UPDATE hands SET rit_boards = 2")   # every hand takes the re-parse path
    gp.clear_cache()
    assert _details(client) == stored
    assert calls
