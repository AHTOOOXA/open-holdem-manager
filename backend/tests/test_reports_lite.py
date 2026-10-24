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
    # opportunities of sibling rows are one decision: not summed
    assert summ["opps"] is None and summ["stat_value"] is None
    assert summ["won_bb"] == pytest.approx(sum(r["values"]["won_bb"] for r in rows))
    f = _split(client, P01 + [{"k": "next", "street": "preflop", "a": "raise"}], "faced_next")
    if f["summary"]:
        assert f["summary"]["opps"] is None and f["summary"]["stat_value"] is None
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
                  [{"k": "hv", "street": "flop", "cats": ["nope"]}],
                  [{"k": "session", "start": "2026-01-02T10:00:00", "end": "2026-01-01T10:00:00"}],
                  [{"k": "session", "start": "yesterday", "end": "2026-01-01T10:00:00"}],
                  [{"k": "session", "start": "2026-01-01T10:00:00+02:00",
                    "end": "2026-01-01T11:00:00+02:00"}],
                  [{"k": "session", "start": "2026-01-01T10:00:00"}],
                  [{"k": "table", "v": []}], [{"k": "with", "player_id": "x"}],
                  [{"k": "with"}]):
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


# ── review fixes ─────────────────────────────────────────────────────────


def _fresh_db(raws):
    reset_import_cache()
    invalidate_hero_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
                 "VALUES (1, 1, 'Hero', 'manual')")
    _import(conn, raws)
    return conn


def _import(conn, raws):
    pending = []
    with patch("app.api.import_hands._calc_equity", None):
        for raw in raws:
            parsed = parse_hand_history(raw)
            pending.append((parsed, compute_stat_flags(parsed), _compute_financials(parsed)))
        _flush_batch(conn, pending)
    from app.api.import_hands import finalize_import
    finalize_import(conn, workspace_id=1)
    invalidate_hero_cache()


def test_cache_is_fresh_after_clear_and_reimport(monkeypatch):
    if not BENCH.exists():
        pytest.skip("bench sample missing")
    hands = [h.strip() for h in split_hands(BENCH.read_text()) if h.strip()]
    a, b = hands[:300], hands[300:600]
    conn = _fresh_db(a)
    monkeypatch.setattr(app_db, "_conn", conn)
    c = TestClient(app)
    chain_mod.clear_cache()
    first = _post(c, "spot", [])["hands"]
    first_p01 = _post(c, "spot", P01)
    assert first > 0
    # simulate a stale entry surviving: wipe via the endpoint, which must not rely on clear_cache
    assert c.post("/api/import/clear").status_code == 200
    assert _post(c, "spot", [])["hands"] == 0
    reset_import_cache()
    _import(conn, b)
    again = _post(c, "spot", [])["hands"]
    expected = conn.execute("SELECT COUNT(*) FROM hand_players hp JOIN players p ON p.id = "
                            "hp.player_id WHERE p.username = 'Hero' "
                            "AND COALESCE(hp.h2n_valid, TRUE)").fetchone()[0]
    assert again == expected
    second_p01 = _post(c, "spot", P01)
    assert second_p01 != first_p01 or again != first
    conn.close()
    invalidate_hero_cache()


def test_data_generation_bump_changes_cache_key(client, bench_db):
    from app import data_generation
    k1 = chain_mod.data_version(bench_db, 1)
    data_generation.bump()
    assert chain_mod.data_version(bench_db, 1) != k1


def test_hands_tab_lists_the_requested_player(client, bench_db):
    vid, vname = bench_db.execute(
        "SELECT hp.player_id, p.username FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE p.username <> 'Hero' GROUP BY 1, 2 ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    r = client.get("/api/hands", params={"chain": "[]", "player_id": vid, "per_page": 20})
    assert r.status_code == 200
    j = r.json()
    n = bench_db.execute("SELECT COUNT(*) FROM hand_players WHERE player_id = ? "
                         "AND COALESCE(h2n_valid, TRUE)", [vid]).fetchone()[0]
    assert j["total"] == n > 0
    for h in j["hands"]:
        row = bench_db.execute("SELECT position, card1, card2, won_bb FROM hand_players "
                               "WHERE hand_id = ? AND player_id = ?", [h["id"], vid]).fetchone()
        assert (h["position"], h["card1"], h["card2"]) == row[:3]
        assert h["won_bb"] == pytest.approx(float(row[3]))
    # without player_id the hero's rows come back
    hero = client.get("/api/hands", params={"chain": "[]"}).json()
    assert hero["total"] != j["total"] or hero["hands"][0]["id"] != j["hands"][0]["id"]


def test_crafted_chains_do_not_500(client):
    for chain in ([{"k": "hv", "street": "flop", "cats": ["nope"]}],
                  [{"k": "betsize", "bucket": "nope"}]):
        j = json.dumps(chain)
        for url in ("/api/hands", "/api/reports/graph"):
            assert client.get(url, params={"chain": j}).status_code == 422, (url, chain)
    # spot-step shapes that cannot start a hand fall back to generic names
    for a in ("bet", "limp_fold", "fold_vs_bet", "check_vs_call", "limp_call"):
        step = [{"k": "next", "street": "flop", "a": a}]
        for t in ("next_actions", "faced_next", "bet_sizing"):
            r = client.post("/api/reports/split", json={"workspace_id": 1, "chain": step,
                                                        "type": t})
            assert r.status_code in (200, 422), (a, t, r.text)
        assert client.post("/api/reports/spot", json={"workspace_id": 1,
                                                      "chain": step}).status_code in (200, 422)


def test_chain_fuzz_no_500(client):
    import random
    from app.reports.chain import NextAction, FacedAction
    from typing import get_args
    rng = random.Random(7)
    streets = ["preflop", "flop", "turn", "river"]
    nexts, faceds = list(get_args(NextAction)), list(get_args(FacedAction))
    rows = ["P01", "C01", "P02"]

    tables = [t for (t,) in client_tables(client)]
    starts = ["2026-01-01T18:25:11", "2026-01-15T00:00:00", "2026-02-08T10:00:00"]

    def step():
        k = rng.choice(["pos", "stakes", "mode", "tsize", "hour", "stack", "game", "cells",
                        "hv", "row", "next", "faced", "betsize", "session", "table", "with"])
        if k == "session":
            a, b = sorted(rng.sample(starts, 2))
            return {"k": k, "start": a, "end": rng.choice([b, a, "2025-01-01T00:00:00"])}
        if k == "table":
            return {"k": k, "v": rng.sample(tables, 2) + rng.choice([[], ["nope"]])}
        if k == "with":
            return {"k": k, "player_id": rng.choice([1, 2, 3, 10**6])}
        if k == "pos":
            return {"k": k, "v": [rng.choice(["EP", "MP", "CO", "BTN", "SB", "BB"])]}
        if k == "stakes":
            return {"k": k, "v": ["$0.05/$0.10"]}
        if k == "mode":
            return {"k": k, "v": rng.choice(["fast", "regular"])}
        if k == "tsize":
            return {"k": k, "v": [rng.choice([2, 6, 9])]}
        if k == "hour":
            return {"k": k, "v": [rng.randrange(24)]}
        if k == "stack":
            return {"k": k, "lo": rng.choice([0, 20, 50]), "hi": rng.choice([None, 100])}
        if k == "game":
            return {"k": k, "stakes": "$0.05/$0.10", "mode": rng.choice(["fast", "regular"]),
                    "tsize": rng.choice([None, 6])}
        if k == "cells":
            return {"k": k, "v": ["AA", "AKs", "72o"]}
        if k == "hv":
            return {"k": k, "street": rng.choice(streets[1:]), "cats": ["other"]}
        if k == "row":
            return {"k": k, "key": rng.choice(rows)}
        if k == "next":
            return {"k": k, "street": rng.choice(streets), "a": rng.choice(nexts)}
        if k == "faced":
            return {"k": k, "street": rng.choice(streets), "a": rng.choice(faceds)}
        return {"k": k, "bucket": "nope"}

    types = ["results", "positions", "next_actions", "faced_next", "bet_sizing", "stack_sizes",
             "hour_of_day", "table_size", "tables", "players"]
    for _ in range(80):
        chain = [step() for _ in range(rng.randint(1, 3))]
        r = client.post("/api/reports/split", json={"workspace_id": 1, "chain": chain,
                                                    "type": rng.choice(types)})
        assert r.status_code in (200, 422), (chain, r.text)
        r = client.get("/api/hands", params={"chain": json.dumps(chain), "per_page": 5})
        assert r.status_code in (200, 422), (chain, r.text)
        r = client.get("/api/reports/graph", params={"chain": json.dumps(chain)})
        assert r.status_code in (200, 422), (chain, r.text)
        r = client.post("/api/reports/spot", json={
            "workspace_id": 1, "chain": chain,
            "recipe": rng.choice(["session", "table", "villain"])})
        assert r.status_code in (200, 422), (chain, r.text)


def client_tables(client):
    return app_db._conn.execute(
        "SELECT table_name FROM hands GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT 20").fetchall()


def test_game_row_with_unknown_table_size(client, bench_db):
    step = {"k": "game", "stakes": "$0.05/$0.10", "mode": "regular", "tsize": None}
    n = bench_db.execute(
        "SELECT COUNT(*) FROM hand_players hp JOIN hands h ON h.id = hp.hand_id AND "
        "h.workspace_id = hp.workspace_id JOIN players p ON p.id = hp.player_id WHERE "
        "p.username = 'Hero' AND COALESCE(hp.h2n_valid, TRUE) AND h.stakes = '$0.05/$0.10' "
        "AND h.game_mode <> 'Fast Fold' AND h.table_size IS NULL").fetchone()[0]
    assert _post(client, "spot", [step])["hands"] == n


def test_inflight_entry_released_on_error(client, bench_db, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(chain_mod, "_compute", boom)
    with pytest.raises(RuntimeError):
        chain_mod.resolve(bench_db, 1, None, chain_mod.parse_chain(json.dumps(P01)))
    assert not chain_mod._inflight


def test_empty_chain_param_applies_h2n_valid(client, bench_db, hero_id):
    n = bench_db.execute("SELECT COUNT(*) FROM hand_players WHERE player_id = ? AND "
                         "COALESCE(h2n_valid, TRUE)", [hero_id]).fetchone()[0]
    assert client.get("/api/hands", params={"chain": "[]", "per_page": 1}).json()["total"] == n
    g = client.get("/api/reports/graph", params={"chain": "[]"}).json()
    assert len(g["points"]) == n


# ── M5: Sessions steps, splits and recipes ───────────────────────────────


def _busy_window(bench_db, hero_id):
    """A ~2 h window of hero's hands with its busiest tables."""
    first = bench_db.execute(
        "SELECT MIN(played_at) FROM hand_players hp JOIN hands h ON h.id = hp.hand_id "
        "WHERE hp.player_id = ?", [hero_id]).fetchone()[0]
    import datetime as dt
    end = first + dt.timedelta(hours=2)
    return first.isoformat(), end.isoformat()


@pytest.mark.parametrize("make, where", [
    (lambda w, t, v: {"k": "session", "start": w[0], "end": w[1]},
     lambda w, t, v: ("h.played_at BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)", w)),
    (lambda w, t, v: {"k": "table", "v": t},
     lambda w, t, v: ("h.table_name IN (?, ?, ?)", t)),
    (lambda w, t, v: {"k": "with", "player_id": v},
     lambda w, t, v: ("EXISTS (SELECT 1 FROM hand_players o WHERE o.hand_id = h.id "
                      "AND o.player_id = ?)", [v])),
])
def test_session_steps_narrow(client, bench_db, hero_id, make, where):
    w = _busy_window(bench_db, hero_id)
    t = [r[0] for r in bench_db.execute(
        "SELECT table_name FROM hands GROUP BY 1 ORDER BY COUNT(*) DESC, 1 LIMIT 3").fetchall()]
    v = bench_db.execute(
        "SELECT hp.player_id FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE p.username <> 'Hero' GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    sql, params = where(w, t, v)
    expected = _count(bench_db, hero_id, sql, params)
    assert expected > 0
    chain = [make(w, t, v)]
    assert _post(client, "spot", chain)["hands"] == expected
    assert client.get("/api/hands", params={"chain": json.dumps(chain)}).json()["total"] == expected
    g = client.get("/api/reports/graph", params={"chain": json.dumps(chain)}).json()
    assert len(g["points"]) == expected


def test_tables_split(client, bench_db, hero_id):
    w = _busy_window(bench_db, hero_id)
    chain = [{"k": "session", "start": w[0], "end": w[1]}]
    hands = _post(client, "spot", chain)["hands"]
    s = _split(client, chain, "tables")
    assert s["entry_header"] == "Tables"
    assert [c["id"] for c in s["columns"]] == [
        "hands", "duration", "hands_h", "won", "won_ev", "ev_bb100", "vpip", "pfr", "ag",
        "threebet", "wtsd", "wsd", "wwsf", "rake", "rake_bb100", "won_bb"]
    assert sum(r["values"]["hands"] for r in s["rows"]) == hands == s["summary"]["hands"]
    assert [r["caption"] for r in s["rows"]] == sorted(r["caption"] for r in s["rows"])
    row = max(s["rows"], key=lambda r: r["values"]["hands"])
    assert row["filter"] == {"k": "table", "v": [row["caption"]], "label": row["caption"]}
    page = _post(client, "spot", chain + [row["filter"]], recipe="table")
    stats = {x["id"]: x for x in page["stats"]}
    assert page["hands"] == row["values"]["hands"]
    for k in ("duration", "hands_h", "won", "won_ev", "ev_bb100", "vpip", "pfr", "rake",
              "rake_bb100", "won_bb"):
        assert stats[k]["value"] == pytest.approx(row["values"][k]), k
    assert "avg_tables" not in stats
    for c in s["columns"]:
        if "sample" in c:
            assert c["sample"] in row["values"]


def test_players_split_and_villain_page(client, bench_db, hero_id):
    w = _busy_window(bench_db, hero_id)
    chain = [{"k": "session", "start": w[0], "end": w[1]}]
    s = _split(client, chain, "players")
    assert s["entry_header"] == "Players"
    rows = s["rows"]
    assert rows and all(r["player"]["username"] != "Hero" for r in rows)
    hs = [r["values"]["hands"] for r in rows]
    assert hs == sorted(hs, reverse=True)
    top = rows[0]
    assert top["filter"] == {"k": "with", "player_id": hero_id,
                             "label": top["player"]["username"]}
    assert top["caption"] == top["player"]["username"]
    vid = top["player"]["id"]
    # the opened page = the opponent's numbers in hands with hero, same as the row
    vchain = chain + [top["filter"]]
    plain = client.post("/api/reports/spot", json={"workspace_id": 1, "player_id": vid,
                                                   "chain": vchain}).json()
    pstats = {x["id"]: x["value"] for x in plain["stats"]}
    assert plain["hands"] == top["values"]["hands"]
    for k in ("vpip", "pfr", "threebet", "ag", "wtsd", "wsd", "won"):
        assert pstats[k] == pytest.approx(top["values"][k]) if pstats[k] is not None \
            else top["values"][k] is None, k
    # sum of opponent hands = sum of other seats in hero's hands of the chain
    n_opp = bench_db.execute(
        "SELECT COUNT(*) FROM hand_players o JOIN hands h ON h.id = o.hand_id "
        "WHERE o.player_id <> ? AND COALESCE(o.h2n_valid, TRUE) AND h.played_at BETWEEN "
        "CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP) AND EXISTS (SELECT 1 FROM hand_players "
        "x WHERE x.hand_id = h.id AND x.player_id = ? AND COALESCE(x.h2n_valid, TRUE))",
        [hero_id, w[0], w[1], hero_id]).fetchone()[0]
    assert sum(hs) == n_opp == s["summary"]["hands"]
    vill = client.post("/api/reports/spot", json={"workspace_id": 1, "player_id": vid,
                                                  "chain": vchain, "recipe": "villain"}).json()
    ids = [x["id"] for x in vill["stats"]]
    assert ids == ["hands", "vpip", "pfr", "ev_diff", "ag", "bb100", "won_nsd", "threebet",
                   "wtsd", "wsd", "wwsf", "rake", "rake_bb100"]
    assert vill["hands"] == top["values"]["hands"]


def test_recipe_shapes(client):
    d = _post(client, "spot", [], recipe="session")
    ids = [x["id"] for x in d["stats"]]
    assert ids == ["hands", "duration", "hands_h", "won", "won_ev", "ev_bb100", "avg_tables",
                   "vpip", "pfr", "ag", "threebet", "wtsd", "wsd", "wwsf", "rake", "rake_bb100",
                   "won_bb"]
    groups = [x["group"] for x in d["stats"]]
    assert groups == ["anchor1"] * 3 + ["anchor2"] * 3 + ["grid"] * 11
    assert all("filter" not in x for x in d["stats"])
    fmt = {x["id"]: x["format"] for x in d["stats"]}
    assert (fmt["duration"], fmt["hands_h"], fmt["avg_tables"]) == ("duration", "rate", "ratio")
    plain = {x["id"]: x["value"] for x in _post(client, "spot", [])["stats"]}
    vals = {x["id"]: x["value"] for x in d["stats"]}
    assert vals["ev_bb100"] == pytest.approx(plain["ev_bb100"])
    assert d["hands"] == vals["hands"] == plain["hands"]
    t = _post(client, "spot", [], recipe="table")
    assert [x["id"] for x in t["stats"]] == [i for i in ids if i != "avg_tables"]
    r = client.post("/api/reports/spot", json={"workspace_id": 1, "chain": [], "recipe": "x"})
    assert r.status_code == 422
