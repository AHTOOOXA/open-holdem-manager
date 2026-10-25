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
