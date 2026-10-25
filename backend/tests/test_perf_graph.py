"""Graph track (performance/02 G1-G4): the sampled graph and the chain graph cache must return
exactly what the former per-hand loop returned.

Runs on the 20k bench DB of test_reports_lite (same module-scoped fixtures).
"""

from __future__ import annotations

import json
import math
from datetime import timedelta

import pytest

import app.api.reports as rep
from app import data_generation
from tests.test_reports_lite import C01, P01, bench_db, client, hero_id  # noqa: F401 (fixtures)

FIELDS = ["cumulative_bb", "cumulative_ev_bb", "cumulative_rake_bb", "cumulative_jackpot_bb",
          "cumulative_showdown_bb", "cumulative_nonshowdown_bb", "cumulative_usd",
          "cumulative_ev_usd", "cumulative_rake_usd", "cumulative_jackpot_usd",
          "cumulative_showdown_usd", "cumulative_nonshowdown_usd"]


def _legacy_graph(db, player_id, where="", params=(), last_n=None):
    """The former get_graph loop: DECIMAL rows, float() per value, one point per hand."""
    rows = db.execute(f"""
        SELECT hp.won_bb, COALESCE(hp.all_in_ev_bb, hp.won_bb), COALESCE(hp.rake_bb, 0),
               h.played_at, COALESCE(hp.won, 0), COALESCE(hp.rake, 0),
               COALESCE(hp.all_in_ev_bb, hp.won_bb) * h.bb_amount,
               COALESCE(hp.went_to_showdown, FALSE), COALESCE(hp.jackpot_bb, 0),
               COALESCE(hp.jackpot, 0)
        FROM hand_players hp JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE hp.player_id = ? AND h.workspace_id = 1 {where}
        ORDER BY h.played_at ASC, h.id ASC""", [player_id, *params]).fetchall()
    if last_n and len(rows) > last_n:
        rows = rows[-last_n:]
    cum = [0.0] * 12
    points, won, starts, ts, prev = [], [], [], [], None
    for i, (wb, eb, rb, at, wu, ru, eu, sd, jb, ju) in enumerate(rows):
        wb, wu = float(wb or 0), float(wu or 0)
        won.append(wb)
        if i == 0:
            starts.append(1)
        elif prev and (at - prev) > timedelta(minutes=10):
            starts.append(i + 1)
        ts.append(at.isoformat())
        prev = at
        deltas = [wb, float(eb or 0), float(rb or 0), float(jb or 0),
                  wb if sd else 0.0, 0.0 if sd else wb, wu, float(eu or 0), float(ru or 0),
                  float(ju or 0), wu if sd else 0.0, 0.0 if sd else wu]
        for k, d in enumerate(deltas):
            cum[k] += d       # += 0.0 on the branch not taken is a no-op (cum is never -0.0)
        points.append({"hand_number": i + 1, "played_at": ts[-1],
                       **{f: round(cum[k], 2) for k, f in enumerate(FIELDS)}})
    sessions = []
    for j, s in enumerate(starts):
        e = starts[j + 1] - 1 if j + 1 < len(starts) else len(points)
        sessions.append({"start_hand": s, "end_hand": e, "start_time": ts[s - 1],
                         "end_time": ts[e - 1]})
    variance = None
    n = len(won)
    if n >= 2:
        mean = sum(won) / n
        sd_h = math.sqrt(sum((x - mean) ** 2 for x in won) / (n - 1))
        wr = round(mean * 100, 2)
        se = sd_h * 100 / math.sqrt(n)
        variance = {"sd_bb": round(sd_h, 4), "sd_bb100": round(sd_h * 10, 2), "winrate_bb100": wr,
                    "ci_lower_bb100": round(wr - 1.96 * se, 2),
                    "ci_upper_bb100": round(wr + 1.96 * se, 2), "n": n}
    return {"points": points, "sessions": sessions, "variance": variance}


def _graph(client, **params):
    r = client.get("/api/reports/graph", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _js_sample(n, max_points=1000):
    """ResultsChart.tsx sampling (Math.round(i * step), last point appended)."""
    if n <= max_points:
        return list(range(n))
    step = (n - 1) / (max_points - 1)
    return [math.floor(i * step + 0.5) for i in range(max_points - 1)] + [n - 1]


@pytest.fixture
def fresh(client):
    rep._GRAPH_CACHE.clear()
    yield client
    rep._GRAPH_CACHE.clear()


def test_sample_indices_match_the_chart():
    for n in [0, 1, 2, 999, 1000, 1001, 1002, 1999, 3092, 19994, 20000, 214188, 1_000_003]:
        assert rep.sample_indices(n) == _js_sample(n), n
    assert rep.sample_indices(10, 2) == [0, 9]


@pytest.mark.parametrize("params, where, wparams, last_n", [
    ({}, "", [], None),                                                   # legacy, no chain
    ({"last_n": 1700}, "", [], 1700),
    ({"chain": "[]"}, "AND COALESCE(hp.h2n_valid, TRUE)", [], None),
    ({"stakes": "$0.05/$0.10"}, "AND h.stakes = ?", ["$0.05/$0.10"], None),
    ({"game_mode": ""}, "AND h.game_mode = ?", [""], None),
])
def test_graph_matches_the_per_hand_loop(fresh, bench_db, hero_id, params, where, wparams, last_n):
    ref = _legacy_graph(bench_db, hero_id, where, wparams, last_n)
    n = len(ref["points"])
    assert n > 1000          # the response really is sampled
    full = _graph(fresh, max_points=10**9, **params)
    assert full["hands"] == n
    assert full["points"] == ref["points"]
    assert full["sessions"] == ref["sessions"]
    assert full["variance"] == ref["variance"]
    got = _graph(fresh, **params)
    assert got["hands"] == n and len(got["points"]) == 1000
    assert got["points"] == [ref["points"][i] for i in _js_sample(n)]
    assert got["points"][-1] == ref["points"][-1]
    assert got["sessions"] == ref["sessions"] and got["variance"] == ref["variance"]


def test_spot_chain_graph_sampled_points_equal_full_series(fresh, bench_db):
    for chain in (P01, C01):
        full = _graph(fresh, chain=json.dumps(chain), max_points=10**9)
        got = _graph(fresh, chain=json.dumps(chain))
        n = full["hands"]
        assert n == len(full["points"]) and n > 0
        by_hand = {p["hand_number"]: p for p in full["points"]}
        assert got["hands"] == n
        assert [by_hand[p["hand_number"]] for p in got["points"]] == got["points"]
        assert [p["hand_number"] for p in got["points"]] == [i + 1 for i in _js_sample(n)]
        assert got["sessions"] == full["sessions"] and got["variance"] == full["variance"]
        small = _graph(fresh, chain=json.dumps(chain), max_points=50)
        assert len(small["points"]) == min(n, 50) and small["points"][-1] == full["points"][-1]
        assert small["sessions"] == full["sessions"] and small["variance"] == full["variance"]


def test_graph_empty_and_errors(fresh):
    e = _graph(fresh, chain="[]", stakes="no such stakes")
    assert e == {"points": [], "sessions": [], "variance": None, "hands": 0}
    assert fresh.get("/api/reports/graph", params={"chain": "[{}]"}).status_code == 422
    assert fresh.get("/api/reports/graph", params={"chain": "[]", "player_id": 10**9}
                     ).status_code == 404
    assert fresh.get("/api/reports/graph", params={"max_points": 1}).status_code == 422


def test_chain_graph_cache(fresh, monkeypatch):
    params = {"chain": json.dumps(P01)}
    first = _graph(fresh, **params)
    assert len(rep._GRAPH_CACHE) == 1
    calls = []
    real = rep.graph_series
    monkeypatch.setattr(rep, "graph_series", lambda *a, **k: calls.append(1) or real(*a, **k))
    assert _graph(fresh, **params) == first and not calls            # served from the cache
    # every filter is part of the key
    _graph(fresh, stakes="$0.05/$0.10", **params)
    _graph(fresh, max_points=10, **params)
    assert len(calls) == 2 and len(rep._GRAPH_CACHE) == 3
    # a data change empties it
    data_generation.bump()
    assert len(rep._GRAPH_CACHE) == 0
    assert _graph(fresh, **params) == first and len(calls) == 3
    # the legacy (no chain) graph is not cached
    _graph(fresh)
    assert len(rep._GRAPH_CACHE) == 1


def test_graph_cache_is_bounded():
    c = rep._GraphCache(capacity=3, max_items=10)
    mk = lambda k: rep.GraphResponse(points=[rep.GraphPoint(hand_number=i + 1, cumulative_bb=0)
                                             for i in range(k)])
    for i in range(5):
        c.put(i, mk(1))
    assert len(c) == 3 and c.get(0) is None and c.get(4) is not None
    c.put("big", mk(11))                      # larger than the whole budget: not kept
    assert c.get("big") is None
    c.put("a", mk(6)); c.put("b", mk(6))      # 12 > 10 items: the older one goes
    assert c.get("a") is None and c.get("b") is not None
