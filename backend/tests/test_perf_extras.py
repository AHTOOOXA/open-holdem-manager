"""Extras performance track: the faster queries return what the old ones returned, and the
in-process result cache never serves data that changed (performance/07-extras.md, 05 S5).

The reference queries below are the shipped SQL before the rewrite (perf/fixes 7d5289e)."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import concurrency, data_generation
from app import sessions_h2n as sh
from app.api import compare as compare_api
from app.api import players as players_api
from app.api import population as population_api
from app.api.identities import _build_identity, list_identities
from app.api.import_hands import (
    _compute_financials, _flush_batch, finalize_import, reset_import_cache,
)
from app.db import get_hero_player_id, init_schema
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers.ggpoker import parse_hand_history, split_hands
from app.player_classification import batch_update_player_types
from app.stat_flags import compute_stat_flags
from app.stats_engine import (
    _AGG_SQL, ResultCache, _stats_from_sql, agg_sql, compute_population_stats,
)

BENCH = Path(__file__).parent / "fixtures" / "bench_sample_20k.txt"
N_HANDS = 2500


@pytest.fixture(scope="module")
def sdb():
    """In-memory DB with the first N_HANDS bench hands, finalized (classifications)."""
    if not BENCH.exists():
        pytest.skip("bench_sample_20k.txt not found")
    reset_import_cache()
    invalidate_hero_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
                 "VALUES (1, 1, 'Hero', 'manual')")
    pending = []
    with patch("app.api.import_hands._calc_equity", None):
        for raw in [h.strip() for h in split_hands(BENCH.read_text())[:N_HANDS] if h.strip()]:
            parsed = parse_hand_history(raw)
            pending.append((parsed, compute_stat_flags(parsed), _compute_financials(parsed)))
        _flush_batch(conn, pending)
    finalize_import(conn, workspace_id=1)
    invalidate_hero_cache()
    old = app_db._conn
    app_db._conn = conn
    yield conn
    app_db._conn = old
    conn.close()
    invalidate_hero_cache()


@pytest.fixture(scope="module")
def client(sdb):
    return TestClient(app)


@pytest.fixture(scope="module")
def hero(sdb):
    return get_hero_player_id(sdb, 1)


# ── conditional hands join ───────────────────────────────────────────────


def test_agg_sql_joins_hands_only_for_hands_columns():
    assert "JOIN hands" not in agg_sql("hp.player_id = ? AND h.workspace_id = ?")
    assert "hp.workspace_id = ?" in agg_sql("hp.player_id = ? AND h.workspace_id = ?")
    assert "JOIN hands" in agg_sql("h.workspace_id = ? AND h.stakes = ?")
    assert "JOIN hands" in agg_sql("h.id IN (SELECT id FROM recent_hands)")
    assert "JOIN hands" not in agg_sql("hp.player_id = ? AND COALESCE(hp.h2n_pos, hp.position) = ?")


@pytest.mark.parametrize("where,args", [
    ("hp.player_id = ? AND h.workspace_id = ?", ["HERO", 1]),
    ("hp.player_id = ? AND h.workspace_id = ? AND COALESCE(hp.h2n_pos, hp.position) = ?",
     ["HERO", 1, "BTN"]),
    ("h.workspace_id = ? AND hp.player_id != ?", [1, "HERO"]),
    ("1=1 AND h.workspace_id = ?", [1]),
])
def test_stats_without_hands_join_are_identical(sdb, hero, where, args):
    params = [hero if a == "HERO" else a for a in args]
    assert "JOIN hands" not in agg_sql(where)
    old = _stats_from_sql(sdb, _AGG_SQL.format(where=where), params)
    new = _stats_from_sql(sdb, agg_sql(where), params)
    assert old.hands > 0
    assert new.model_dump() == old.model_dump()


# ── Population ───────────────────────────────────────────────────────────


def _ref_full_stats(db, **kw):
    """population_full_stats as shipped: always the eligible CTE, always the hands join."""
    a = dict(stakes=None, date_from=None, date_to=None, min_hands=20, exclude_hero=True,
             player_type=None, workspace_id=1, exclude_identity_ids=None, exclude_tags=None)
    a.update(kw)
    b = population_api._build_where
    where_sql, params, having_sql = b(a["stakes"], a["date_from"], a["date_to"], a["min_hands"],
                                      a["exclude_hero"], a["player_type"], db, a["workspace_id"],
                                      a["exclude_identity_ids"], a["exclude_tags"])
    cte = f"""WITH eligible AS (
        SELECT hp.player_id FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN players p ON p.id = hp.player_id
        LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
        WHERE 1=1 {where_sql} GROUP BY hp.player_id {having_sql})
    """
    mf, mp, _ = b(a["stakes"], a["date_from"], a["date_to"], a["min_hands"], a["exclude_hero"],
                  None, db, a["workspace_id"], a["exclude_identity_ids"], a["exclude_tags"])
    mw = f"1=1 {mf} AND hp.player_id IN (SELECT player_id FROM eligible)"
    return _stats_from_sql(db, cte + _AGG_SQL.format(where=mw), params + mp)


def _ref_overview(db, **kw):
    a = dict(stakes=None, date_from=None, date_to=None, min_hands=20, exclude_hero=True,
             player_type=None, workspace_id=1, exclude_identity_ids=None, exclude_tags=None)
    a.update(kw)
    where_sql, params, having_sql = population_api._build_where(
        a["stakes"], a["date_from"], a["date_to"], a["min_hands"], a["exclude_hero"],
        a["player_type"], db, a["workspace_id"], a["exclude_identity_ids"], a["exclude_tags"])
    row = db.execute(f"""
        SELECT COUNT(*), SUM(hands), MIN(min_t), MAX(max_t) FROM (
            SELECT hp.player_id, COUNT(*) as hands, MIN(h.played_at) as min_t, MAX(h.played_at) as max_t
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql} GROUP BY hp.player_id {having_sql}) sub
    """, params).fetchone()
    return {"player_count": row[0], "observation_count": row[1] or 0,
            "date_min": row[2].isoformat() if row[2] else None,
            "date_max": row[3].isoformat() if row[3] else None}


POP_CASES = [
    dict(min_hands=0), dict(min_hands=1), dict(min_hands=0, exclude_hero=False),
    dict(min_hands=5), dict(min_hands=20), dict(min_hands=0, player_type="UNK"),
    dict(min_hands=0, date_from="2020-01-01"), dict(min_hands=0, stakes="$0.02/$0.05"),
]


@pytest.mark.parametrize("kw", POP_CASES)
def test_population_full_stats_match_shipped_sql(sdb, client, kw):
    data_generation.bump()
    r = client.get("/api/population/full-stats", params=kw)
    assert r.status_code == 200, r.text
    assert r.json() == _ref_full_stats(sdb, **kw).model_dump(mode="json")


@pytest.mark.parametrize("kw", POP_CASES)
def test_population_overview_matches_shipped_sql(sdb, client, kw):
    data_generation.bump()
    r = client.get("/api/population/overview", params=kw)
    assert r.status_code == 200, r.text
    assert r.json() == _ref_overview(sdb, **kw)


def _ref_population_summary(db, hero, ws, min_hands, stakes, game_mode):
    q = """SELECT COUNT(DISTINCT hp.player_id), COUNT(*) FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE h.workspace_id = ? AND hp.player_id != ?"""
    p = [ws, hero]
    if stakes:
        q += " AND h.stakes = ?"; p.append(stakes)
    if game_mode is not None:
        q += " AND h.game_mode = ?"; p.append(game_mode)
    if min_hands > 1:
        q += """ AND hp.player_id IN (SELECT hp2.player_id FROM hand_players hp2
            JOIN hands h2 ON hp2.hand_id = h2.id AND hp2.workspace_id = h2.workspace_id
            WHERE h2.workspace_id = ? AND hp2.player_id != ? GROUP BY hp2.player_id HAVING COUNT(*) >= ?)"""
        p += [ws, hero, min_hands]
    return tuple(int(x) for x in db.execute(q, p).fetchone())


def _ref_population_stats(db, hero, ws, min_hands, stakes, game_mode):
    cw, cp = "h2.workspace_id = ? AND hp2.player_id != ?", [ws, hero]
    w, mp = "h.workspace_id = ? AND hp.player_id != ?", [ws, hero]
    if stakes:
        cw += " AND h2.stakes = ?"; cp.append(stakes); w += " AND h.stakes = ?"; mp.append(stakes)
    if game_mode is not None:
        cw += " AND h2.game_mode = ?"; cp.append(game_mode)
        w += " AND h.game_mode = ?"; mp.append(game_mode)
    cte = f"""WITH eligible AS (SELECT hp2.player_id FROM hand_players hp2
        JOIN hands h2 ON hp2.hand_id = h2.id AND hp2.workspace_id = h2.workspace_id
        WHERE {cw} GROUP BY hp2.player_id HAVING COUNT(*) >= ?)
    """
    w += " AND hp.player_id IN (SELECT player_id FROM eligible)"
    return _stats_from_sql(db, cte + _AGG_SQL.format(where=w), cp + [min_hands] + mp)


@pytest.mark.parametrize("min_hands,stakes,game_mode", [
    (0, None, None), (1, None, None), (5, None, None), (0, "$0.02/$0.05", None),
    (3, None, "Fast Fold"),
])
def test_compare_population_parts_match_shipped_sql(sdb, hero, min_hands, stakes, game_mode):
    data_generation.bump()
    new = compute_population_stats(sdb, 1, exclude_player_id=hero, min_hands=min_hands,
                                   stakes=stakes, game_mode=game_mode)
    ref = _ref_population_stats(sdb, hero, 1, min_hands, stakes, game_mode)
    assert new.model_dump() == ref.model_dump()
    assert (compare_api._get_population_summary(sdb, hero, 1, min_hands, stakes, game_mode)
            == _ref_population_summary(sdb, hero, 1, min_hands, stakes, game_mode))


# ── Players list ─────────────────────────────────────────────────────────


def _ref_players(db, ws, search, types, min_hands, sort_col, direction):
    wc, params = [], []
    if search:
        wc.append("p.username ILIKE ?"); params.append(f"%{search.strip()}%")
    if types:
        wc.append(f"pc.player_type IN ({','.join('?' for _ in types)})"); params += types
    where_sql = (" AND " + " AND ".join(wc)) if wc else ""
    return db.execute(f"""
        SELECT p.id, p.username, COALESCE(pc.player_type, 'UNK'), COUNT(*) as hands,
            SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as vpip_pct,
            SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pfr_pct,
            CASE WHEN SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) * 100.0
                     / SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) ELSE NULL END as three_bet_pct,
            CASE WHEN SUM(COALESCE(hp.flop_calls, 0) + COALESCE(hp.turn_calls, 0) + COALESCE(hp.river_calls, 0)) > 0
                THEN CAST(SUM(COALESCE(hp.flop_bets, 0) + COALESCE(hp.flop_raises, 0)
                  + COALESCE(hp.turn_bets, 0) + COALESCE(hp.turn_raises, 0)
                  + COALESCE(hp.river_bets, 0) + COALESCE(hp.river_raises, 0)) AS DOUBLE)
                 / SUM(COALESCE(hp.flop_calls, 0) + COALESCE(hp.turn_calls, 0) + COALESCE(hp.river_calls, 0))
                ELSE NULL END as af,
            MAX(p.last_seen) as last_seen, pc.is_reg
        FROM players p JOIN hand_players hp ON hp.player_id = p.id
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
        WHERE h.workspace_id = ? {where_sql}
        GROUP BY p.id, p.username, COALESCE(pc.player_type, 'UNK'), pc.is_reg, p.color_tag
        HAVING COUNT(*) >= ?
        ORDER BY {sort_col} {direction} NULLS LAST""", [ws] + params + [min_hands]).fetchall()


_SORT_IDX = {"hands": 3, "vpip": 4, "pfr": 5, "three_bet": 6, "af": 7, "last_seen": 8,
             "username": 1}


@pytest.mark.parametrize("search,types,min_hands", [
    (None, [], 20), (None, [], 0), ("a", [], 1), (None, ["UNK"], 2), ("zz9", [], 0),
])
def test_players_list_matches_shipped_sql(sdb, search, types, min_hands):
    for sort_key, col in players_api._LIST_SORTS.items():
        for d in ("ASC", "DESC"):
            ref = _ref_players(sdb, 1, search, types, min_hands, col, d)
            rows, total, _ = players_api._player_list_rows(
                sdb, 1, search, types, min_hands, sort_key, d, 1, 10**7)
            assert total == len(ref)
            assert sorted(rows) == sorted(ref)
            i = _SORT_IDX[sort_key]
            assert [r[i] for r in rows] == [r[i] for r in ref]


def test_players_pages_concatenate_and_total_past_the_end(sdb):
    full, total, _ = players_api._player_list_rows(sdb, 1, None, [], 2, "hands", "DESC", 1, 10**7)
    assert total == len(full) > 60
    pages = []
    for page in range(1, 100):
        rows, t, _ = players_api._player_list_rows(sdb, 1, None, [], 2, "hands", "DESC", page, 25)
        assert t == total
        if not rows:
            break
        pages += rows
    assert pages == full
    assert players_api._player_list_rows(sdb, 1, None, [], 2, "hands", "DESC", 999, 25)[:2] == ([], total)


def test_players_list_color_tag_is_fresh_through_the_cache(client):
    params = {"min_hands": 5, "sort_by": "hands", "per_page": 5}
    first = client.get("/api/players", params=params).json()["players"][1]
    marker = client.get("/api/config/color_markers").json()["value"][0]
    assert client.patch(f"/api/players/{first['id']}/notes",
                        json={"color_tag": str(marker["id"])}).status_code == 200
    again = client.get("/api/players", params=params).json()["players"][1]
    assert again["id"] == first["id"] and again["marker"]["id"] == marker["id"]
    client.patch(f"/api/players/{first['id']}/notes", json={"color_tag": ""})
    assert client.get("/api/players", params=params).json()["players"][1]["marker"] == first["marker"]


def test_reclassification_bumps_the_generation(sdb):
    g = data_generation.current()
    batch_update_player_types(sdb, workspace_id=1)
    assert data_generation.current() > g


# ── Identities ───────────────────────────────────────────────────────────


def test_identities_list_matches_per_identity_build(sdb, client):
    top = client.get("/api/players", params={"min_hands": 3, "per_page": 12}).json()["players"]
    made = []
    for k in range(4):
        r = client.post("/api/identities", json={"display_name": f"perf{k}", "tags": ["reg"]})
        assert r.status_code == 201, r.text
        made.append(r.json()["id"])
        for p in top[2 * k: 2 * k + 3]:  # overlapping members between identities
            client.post(f"/api/identities/{made[-1]}/aliases",
                        json={"workspace_id": 1, "player_id": p["id"]})
    try:
        lst = list_identities()
        ref = [_build_identity(sdb, i.id) for i in lst]
        assert [i.model_dump() for i in lst] == [i.model_dump() for i in ref]
        assert any(i.total_hands > 0 for i in lst) and len(lst) >= 4
    finally:
        for i in made:
            client.delete(f"/api/identities/{i}")


# ── Stat detail hands ────────────────────────────────────────────────────


def test_stat_detail_hands_page_has_parsed_actions(client):
    r = client.get("/api/stats/detail/vpip/hands", params={"per_page": 7, "page": 2}).json()
    assert len(r["hands"]) == 7
    assert all(h["preflop_actions"] for h in r["hands"])
    times = [h["played_at"] for h in r["hands"]]
    assert times == sorted(times, reverse=True)


# ── Sessions: LAG(e) == running MAX(e) ───────────────────────────────────


def test_session_lag_window_equals_running_max(sdb, hero):
    lag = sh._HANDS_CTE
    old_m = ("SELECT *, MAX(e) OVER (ORDER BY s, hid ROWS BETWEEN UNBOUNDED PRECEDING AND "
             "1 PRECEDING) AS prev_end")
    assert "LAG(e) OVER (ORDER BY s, hid) AS prev_end" in lag
    ref_cte = lag.replace("SELECT *, LAG(e) OVER (ORDER BY s, hid) AS prev_end", old_m)
    for brk in (60, 300, 600, 3600):
        new = sh.build_sessions(sdb, 1, hero, brk)
        with patch.object(sh, "_HANDS_CTE", ref_cte):
            old = sh.build_sessions(sdb, 1, hero, brk)
        assert new == old and len(new) >= 1


# ── ResultCache ──────────────────────────────────────────────────────────


def test_cache_hits_until_bump(sdb):
    c = ResultCache("t")
    calls = []
    f = lambda: calls.append(1) or len(calls)  # noqa: E731
    assert c.get_or_compute(sdb, "k", f) == 1
    assert c.get_or_compute(sdb, "k", f) == 1
    data_generation.bump()
    assert len(c) == 0
    assert c.get_or_compute(sdb, "k", f) == 2


def test_cache_does_not_store_while_a_writer_holds_the_lock(sdb):
    c = ResultCache("t")
    held, release = threading.Event(), threading.Event()

    def writer():
        with app_db.db_lock():
            held.set()
            release.wait(5)

    t = threading.Thread(target=writer)
    t.start()
    held.wait(5)
    try:
        c.get_or_compute(sdb, "k", lambda: 1)
        assert len(c) == 0
    finally:
        release.set()
        t.join()
    c.get_or_compute(sdb, "k", lambda: 1)
    assert len(c) == 1


def test_cache_does_not_store_when_the_generation_moves_during_compute(sdb):
    c = ResultCache("t")

    def compute():
        data_generation.bump()
        return 1

    c.get_or_compute(sdb, "k", compute)
    assert len(c) == 0


def test_cache_misses_when_hand_rows_change_without_a_bump(sdb):
    c = ResultCache("t")
    assert c.get_or_compute(sdb, "k", lambda: "a") == "a"
    hid = sdb.execute("SELECT MAX(id) FROM hand_players").fetchone()[0]
    row = sdb.execute("SELECT * FROM hand_players WHERE id = ?", [hid]).fetchone()
    sdb.execute("DELETE FROM hand_players WHERE id = ?", [hid])
    try:
        assert c.get_or_compute(sdb, "k", lambda: "b") == "b"
    finally:
        sdb.execute(f"INSERT INTO hand_players VALUES ({','.join('?' for _ in row)})", list(row))
    data_generation.bump()


def test_cache_bounded():
    c = ResultCache("t", capacity=3)
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    for k in range(10):
        c.get_or_compute(conn, k, lambda: k)
    assert len(c) == 3
    conn.close()


def test_heavy_miss_runs_in_a_heavy_slot(sdb):
    c = ResultCache("t")
    seen = []
    c.get_or_compute(sdb, "k", lambda: seen.append(getattr(concurrency._local, "depth", 0)), heavy=True)
    c.get_or_compute(sdb, "j", lambda: seen.append(getattr(concurrency._local, "depth", 0)))
    assert seen == [1, 0]
