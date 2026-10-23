"""Reports backend (app/reports/, app/api/reports_lite.py) on 20k real GG hands.

The bench sample (tests/fixtures/bench_sample_20k.txt, hero "Hero") is imported once per
module into an in-memory database. Spot numbers are checked against the General screen
(same matcher rows), plain steps against direct SQL counts.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.general import compute_general
from app.api.import_hands import BATCH_SIZE, _compute_financials, _flush_batch, reset_import_cache
from app.db import init_schema
from app.h2n.rows import sql_case
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers.ggpoker import parse_hand_history, split_hands
from app.reports import chain as chain_mod
from app.stat_flags import compute_stat_flags

BENCH = Path(__file__).parent / "fixtures" / "bench_sample_20k.txt"

P01 = [{"k": "row", "key": "P01"}]
C01 = [{"k": "row", "key": "C01"}]


@pytest.fixture(scope="module")
def bench_db():
    if not BENCH.exists():
        pytest.skip("bench_sample_20k.txt not found")
    reset_import_cache()
    invalidate_hero_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
                 "VALUES (1, 1, 'Hero', 'manual')")
    hands = [h.strip() for h in split_hands(BENCH.read_text()) if h.strip()]
    pending = []
    with patch("app.api.import_hands._calc_equity", None):
        for raw in hands:
            parsed = parse_hand_history(raw)
            pending.append((parsed, compute_stat_flags(parsed), _compute_financials(parsed)))
            if len(pending) >= BATCH_SIZE:
                _flush_batch(conn, pending)
                pending = []
        if pending:
            _flush_batch(conn, pending)
    invalidate_hero_cache()
    yield conn
    conn.close()
    invalidate_hero_cache()


@pytest.fixture
def client(bench_db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", bench_db)
    invalidate_hero_cache()
    chain_mod.clear_cache()
    yield TestClient(app)
    chain_mod.clear_cache()


@pytest.fixture(scope="module")
def hero_id(bench_db):
    return bench_db.execute("SELECT id FROM players WHERE username = 'Hero'").fetchone()[0]


@pytest.fixture(scope="module")
def general(bench_db, hero_id):
    g = compute_general(bench_db, hero_id, 1)
    return {cid: (c.cases, c.opps) for cid, c in g.cells.items() if c.kind == "action"}


def _post(client, path: str, chain: list, **extra) -> dict:
    r = client.post(f"/api/reports/{path}", json={"workspace_id": 1, "chain": chain, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def _split(client, chain: list, typ: str) -> dict:
    return _post(client, "split", chain, type=typ)


def _rows(split: dict) -> dict[str, dict]:
    return {r["caption"]: r for r in split["rows"]}


def _co(row: dict) -> tuple[int, int]:
    return row["values"]["hands"], row["values"]["opps"]


def _spot_numbers(client, chain: list) -> tuple[int, int]:
    d = _post(client, "spot", chain)
    sv = next(s for s in d["stats"] if s["id"] == "stat_value")
    return d["hands"], sv["sample"]


# ── (a) row step = General ───────────────────────────────────────────────


def test_row_spot_equals_general(client, general):
    assert _spot_numbers(client, P01) == general["preflop.open_raise.Total"]
    assert _spot_numbers(client, C01) == general["postflop.cbet.Flop"]
    assert _spot_numbers(client, [{"k": "row", "key": "P03"}]) == general["preflop.fold_to_3bet.Total"]
    d = _post(client, "spot", P01)
    assert d["kind"] == "hero_raise" and d["hit_label"] == "Raise 1st In"


def test_hand_start_raise_equals_open_raise(client, general):
    chain = [{"k": "next", "street": "preflop", "a": "raise"}]
    assert _spot_numbers(client, chain) == general["preflop.open_raise.Total"]


# ── (b) Next Actions rows = General rows ─────────────────────────────────


def test_next_actions_after_open_raise(client, general):
    s = _split(client, P01, "next_actions")
    rows = _rows(s)
    assert [r["caption"] for r in s["rows"]] == [
        "Fold to 3-Bet", "Call 3-Bet", "4-Bet", "Missed Continuation Bet", "Continuation Bet"]
    assert _co(rows["Continuation Bet"]) == general["postflop.cbet.Flop"]
    assert _co(rows["Missed Continuation Bet"]) == general["postflop.missed_cbet.Flop"]
    assert _co(rows["Fold to 3-Bet"]) == general["preflop.fold_to_3bet.Total"]
    assert _co(rows["4-Bet"]) == general["preflop.four_bet.Total"]
    # fold / call share the 3-bet decision
    assert rows["Call 3-Bet"]["values"]["opps"] == rows["Fold to 3-Bet"]["values"]["opps"]
    cb = rows["Continuation Bet"]
    assert cb["filter"] == {"k": "next", "street": "flop", "a": "bet_vs_call",
                            "label": "Continuation Bet"}
    assert cb["open_tab"] == "faced_next"
    # a fold scores 0 Action Profit
    assert rows["Fold to 3-Bet"]["values"]["ap_bbs"] == 0
    assert s["total_hands"] == 19994


def test_barrels(client, general):
    rows = _rows(_split(client, C01, "next_actions"))
    assert _co(rows["2nd Barrel"]) == general["postflop.cbet.Turn"]
    assert {"Missed 2nd Barrel", "Fold to Raise Continuation Bet", "Call Raise Continuation Bet",
            "3-Bet"} <= set(rows)
    chain = C01 + [rows["2nd Barrel"]["filter"]]
    assert _spot_numbers(client, chain) == general["postflop.cbet.Turn"]
    rows3 = _rows(_split(client, chain, "next_actions"))
    assert _co(rows3["3rd Barrel"]) == general["postflop.cbet.River"]
    assert "Missed 3rd Barrel" in rows3


def test_clicked_rows_open_the_same_numbers(client):
    for typ in ("next_actions", "faced_next", "bet_sizing"):
        for row in _split(client, C01, typ)["rows"]:
            assert _spot_numbers(client, C01 + [row["filter"]]) == _co(row), (typ, row["caption"])


def test_faced_raise_then_fold_equals_fold_vs_raise(client):
    a = _spot_numbers(client, C01 + [{"k": "faced", "street": "flop", "a": "villain_raise"},
                                     {"k": "next", "street": "flop", "a": "fold"}])
    b = _spot_numbers(client, C01 + [{"k": "next", "street": "flop", "a": "fold_vs_raise"}])
    assert a == b


# ── (c) positions and summaries ──────────────────────────────────────────


def test_positions_add_up(client):
    spot = _post(client, "spot", P01)
    s = _split(client, P01, "positions")
    assert [r["key"] for r in s["rows"]] == ["BB", "SB", "BTN", "CO", "MP", "EP"]
    assert sum(r["values"]["hands"] for r in s["rows"]) == spot["hands"]
    assert s["summary"]["hands"] == spot["hands"]
    assert s["summary"]["won"] == pytest.approx(sum(r["values"]["won"] for r in s["rows"]))
    btn = _rows(s)["Button"]
    assert btn["filter"] == {"k": "pos", "v": ["BTN"], "label": "Button"}
    assert btn["open_tab"] == "next_actions"
    one = _split(client, P01 + [{"k": "pos", "v": ["BTN"]}], "positions")
    assert len(one["rows"]) == 1 and one["summary"] is None
    assert one["rows"][0]["values"]["hands"] == btn["values"]["hands"]


def test_action_summary_rules(client):
    s = _split(client, P01, "next_actions")
    rows = s["rows"]
    summ = s["summary"]
    assert summ["hands"] == sum(r["values"]["hands"] for r in rows)
    assert summ["opps"] == sum(r["values"]["opps"] for r in rows)
    assert summ["stat_value"] == pytest.approx(summ["hands"] / summ["opps"] * 100)
    assert summ["hits1000"] == pytest.approx(sum(r["values"]["hits1000"] for r in rows))
    assert summ["ap_bbs"] == pytest.approx(sum(r["values"]["ap_bbs"] for r in rows))
    assert summ["ap_bbh"] == pytest.approx(summ["ap_bbs"] / summ["hands"])


def test_results_and_plain_columns(client, bench_db, hero_id):
    s = _split(client, [], "results")
    total = bench_db.execute(
        "SELECT COUNT(*) FROM hand_players WHERE player_id = ? AND COALESCE(h2n_valid, TRUE)",
        [hero_id]).fetchone()[0]
    assert sum(r["values"]["hands"] for r in s["rows"]) == total == s["summary"]["hands"]
    row = _rows(s)["NL10, 6-max, Fast Fold"]
    assert row["filter"]["k"] == "game" and row["filter"]["mode"] == "fast"
    sub = _post(client, "spot", [row["filter"]])
    assert sub["hands"] == row["values"]["hands"]
    ids = {c["id"] for c in s["columns"]}
    assert {"hands", "vpip", "pfr", "threebet", "ag", "wtsd", "wsd", "wwsf", "won", "won_bb",
            "bb100", "won_ev", "ev_bb100", "rake", "dispersion"} == ids
    for c in s["columns"]:
        if "sample" in c:
            assert c["sample"] in row["values"]


# ── (d) plain steps ──────────────────────────────────────────────────────


def _count(db, hero_id, where: str, params=()) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM hand_players hp JOIN hands h ON h.id = hp.hand_id "
        "AND h.workspace_id = hp.workspace_id "
        f"WHERE hp.player_id = ? AND COALESCE(hp.h2n_valid, TRUE) AND {where}",
        [hero_id, *params]).fetchone()[0]


@pytest.mark.parametrize("step, where, params", [
    ({"k": "pos", "v": ["BTN", "CO"]}, "hp.h2n_pos IN ('BTN', 'CO')", ()),
    ({"k": "stakes", "v": ["$0.05/$0.10"]}, "h.stakes = '$0.05/$0.10'", ()),
    ({"k": "mode", "v": "fast"}, "h.game_mode = 'Fast Fold'", ()),
    ({"k": "mode", "v": "regular"}, "h.game_mode <> 'Fast Fold'", ()),
    ({"k": "tsize", "v": [6]}, "h.table_size = 6", ()),
    ({"k": "hour", "v": [20, 21]}, "EXTRACT(hour FROM h.played_at) IN (20, 21)", ()),
    ({"k": "stack", "lo": 80, "hi": 120}, "hp.stack_bb >= 80 AND hp.stack_bb < 120", ()),
    ({"k": "stack", "lo": 300, "hi": None}, "hp.stack_bb >= 300", ()),
    ({"k": "game", "stakes": "$0.02/$0.05", "mode": "regular", "tsize": 6},
     "h.stakes = '$0.02/$0.05' AND h.game_mode = '' AND h.table_size = 6", ()),
    ({"k": "hv", "street": "flop", "cats": ["trash", "set"]}, "hp.hv_flop IN (?, ?)",
     (chain_mod.hv_index("flop", "trash"), chain_mod.hv_index("flop", "set"))),
    ({"k": "cells", "v": ["AA", "AKs"]},
     "((hp.card1 LIKE 'A%' AND hp.card2 LIKE 'A%') OR (substr(hp.card1, 1, 1) IN ('A', 'K') "
     "AND substr(hp.card2, 1, 1) IN ('A', 'K') AND substr(hp.card1, 1, 1) <> substr(hp.card2, 1, 1) "
     "AND right(hp.card1, 1) = right(hp.card2, 1)))", ()),
])
def test_plain_steps_narrow(client, bench_db, hero_id, step, where, params):
    expected = _count(bench_db, hero_id, where, params)
    assert expected > 0
    assert _post(client, "spot", [step])["hands"] == expected


def test_date_step_is_inclusive(client, bench_db, hero_id):
    day = bench_db.execute("SELECT CAST(MIN(played_at) AS DATE) FROM hands").fetchone()[0]
    expected = _count(bench_db, hero_id, "CAST(h.played_at AS DATE) = ?", (day,))
    chain = [{"k": "date", "from": str(day), "to": str(day)}]
    assert _post(client, "spot", chain)["hands"] == expected > 0


def test_bad_chains_are_422(client):
    for chain in ([{"k": "nope"}], [{"k": "row", "key": "XX"}], [{"k": "pos", "v": ["UTG"]}],
                  [{"k": "faced", "street": "flop", "a": "villain_open_call"}],
                  [{"k": "hv", "street": "flop", "cats": ["nope"]}]):
        r = client.post("/api/reports/spot", json={"workspace_id": 1, "chain": chain})
        assert r.status_code == 422, chain


# ── (e) chain on GET /api/hands and /api/reports/graph ──────────────────


def test_hands_endpoint_takes_the_chain(client, general):
    cases = general["preflop.open_raise.Total"][0]
    r = client.get("/api/hands", params={"chain": json.dumps(P01), "per_page": 10})
    assert r.status_code == 200 and r.json()["total"] == cases
    chain = P01 + [{"k": "pos", "v": ["BTN"]}]
    btn = _post(client, "spot", chain)["hands"]
    assert client.get("/api/hands", params={"chain": json.dumps(chain)}).json()["total"] == btn
    both = client.get("/api/hands", params={"chain": json.dumps(P01),
                                            "stakes": "$0.05/$0.10"}).json()["total"]
    only = _post(client, "spot", P01 + [{"k": "stakes", "v": ["$0.05/$0.10"]}])["hands"]
    assert both == only
    assert client.get("/api/hands", params={"chain": "[{\"k\": 1}]"}).status_code == 422
    assert client.get("/api/hands", params={"chain": "not json"}).status_code == 422


def test_graph_takes_the_chain_and_player(client, general, hero_id):
    r = client.get("/api/reports/graph", params={"chain": json.dumps(C01)})
    assert r.status_code == 200
    assert len(r.json()["points"]) == general["postflop.cbet.Flop"][0]
    r2 = client.get("/api/reports/graph", params={"chain": json.dumps(C01), "player_id": hero_id})
    assert len(r2.json()["points"]) == len(r.json()["points"])
    assert client.get("/api/reports/graph", params={"chain": "[{}]"}).status_code == 422


def test_opponent_chain(client, bench_db):
    vid, n = bench_db.execute(
        "SELECT hp.player_id, COUNT(*) FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE p.username <> 'Hero' GROUP BY 1 ORDER BY 2 DESC LIMIT 1").fetchone()
    d = client.post("/api/reports/spot", json={"workspace_id": 1, "player_id": vid,
                                               "chain": []}).json()
    assert d["hands"] == n
    opens = client.post("/api/reports/spot", json={"workspace_id": 1, "player_id": vid,
                                                   "chain": P01}).json()["hands"]
    r = client.get("/api/hands", params={"chain": json.dumps(P01), "player_id": vid})
    assert r.json()["total"] <= opens
    g = client.get("/api/reports/graph", params={"chain": json.dumps(P01), "player_id": vid})
    assert len(g.json()["points"]) == opens


# ── (f) Faced Next ───────────────────────────────────────────────────────


def test_faced_next_after_cbet(client):
    hands = _post(client, "spot", C01)["hands"]
    s = _split(client, C01, "faced_next")
    by_key = {r["filter"]["a"]: r["values"] for r in s["rows"] if r["filter"]["street"] == "flop"}
    assert {"all_fold", "one_call", "villain_raise"} <= set(by_key)
    assert sum(by_key[k]["hands"] for k in ("all_fold", "one_call", "villain_raise")) <= hands
    for v in by_key.values():
        assert v["hands"] <= v["opps"] <= hands
    assert _rows(s)["Fold to Continuation Bet"]["open_tab"] == "next_actions"
    assert "ap_bbs" not in {c["id"] for c in s["columns"]}


def test_spot_stats_of_a_cbet(client):
    d = _post(client, "spot", C01)
    ids = [s["id"] for s in d["stats"]]
    assert ids[:4] == ["hands", "opps", "hits1000", "stat_value"]
    faced = [s for s in d["stats"] if s["id"].startswith("faced:")]
    assert [s["caption"] for s in faced] == ["All Villains Fold", "One Villain Call",
                                            "Villain Raise"]
    for s in faced:
        assert s["filter"]["k"] == "faced" and s["sample"] > 0
    vs = _post(client, "spot", C01 + [faced[2]["filter"]])
    assert vs["kind"] == "villain" and vs["hit_label"] == "Raise Continuation Bet"
    nxt = [s for s in vs["stats"] if s["id"].startswith("next:")]
    assert [s["filter"]["label"] for s in nxt] == [
        "Fold to Raise Continuation Bet", "Call Raise Continuation Bet", "3-Bet"]


# ── (g) preflop range, hand strength ─────────────────────────────────────


def test_preflop_range(client, bench_db, hero_id):
    d = _post(client, "preflop-range", P01)
    cells = d["cells"]
    assert len(cells) == 169
    assert [c["cls"] for c in cells[:3]] == ["AA", "AKs", "AQs"]
    assert cells[13]["cls"] == "AKo" and cells[14]["cls"] == "KK"
    assert sum(c["hands"] for c in cells) == d["total"] == _post(client, "spot", P01)["hands"]
    assert all(c["level"] in (0, 1, 2, 3) for c in cells)
    assert {c["level"] for c in cells if c["hands"]} >= {1, 2}
    aa = cells[0]
    assert aa["won_bb"] == pytest.approx(float(bench_db.execute(
        "SELECT SUM(won_bb) FROM hand_players WHERE player_id = ? AND card1 LIKE 'A%' "
        f"AND card2 LIKE 'A%' AND {sql_case('P01', 'hand_players')} = 1",
        [hero_id]).fetchone()[0]))


def test_hand_strength(client):
    d = _post(client, "hand-strength", C01, street="flop")
    assert d["street"] == "flop"
    assert d["known"] == sum(r["hands"] for r in d["rows"]) > 0
    assert sum(r["pct"] for r in d["rows"]) == pytest.approx(100.0)
    assert d["rows"][0]["key"] == "trash" and d["rows"][0]["weak"] is True


# ── (h) quick filters ────────────────────────────────────────────────────


def test_quick_filters(client):
    q = client.get("/api/reports/quick-filters").json()
    by_key = {f["key"]: f for f in q}
    for key, label in (("P01", "Raise 1st In"), ("P02", "Steal"), ("P06", "Call Open Raise"),
                       ("P07", "3-Bet"), ("P03", "Fold to 3-Bet"), ("P13", "4-Bet"),
                       ("P24", "Squeeze"), ("P22", "Limp"), ("C01", "Continuation Bet"),
                       ("C04", "Fold to Continuation Bet"), ("C02", "2nd Barrel")):
        assert by_key[key]["label"] == label
    assert by_key["C02"]["group"] == "turn" and by_key["P01"]["group"] == "preflop"
    assert all(f["group"] in ("preflop", "flop", "turn", "river") for f in q)


# ── (i) timing ───────────────────────────────────────────────────────────


def test_next_actions_timing(client):
    t0 = time.perf_counter()
    plain = _split(client, [], "next_actions")
    cold = time.perf_counter() - t0
    t0 = time.perf_counter()
    _split(client, [], "next_actions")
    warm = time.perf_counter() - t0
    assert plain["rows"]
    assert cold < 5.0, cold
    assert warm < 0.25, warm
    t0 = time.perf_counter()
    _split(client, P01, "next_actions")
    _split(client, P01, "faced_next")
    _post(client, "spot", P01)
    assert time.perf_counter() - t0 < 5.0
