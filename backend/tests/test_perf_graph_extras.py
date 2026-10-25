"""Graph track (performance/07 F7-F8): the one-pass drift and filter-options queries must return
exactly what the former multi-query code returned.

Runs on the 20k bench DB of test_reports_lite (same module-scoped fixtures).
"""

from __future__ import annotations

import pytest

import app.api.reports as rep
from app.h2n.rows import sql_case, sql_opp
from app.stat_registry import VALID_SQL
from tests.test_reports_lite import bench_db, client, hero_id  # noqa: F401 (fixtures)


# ── drift (07/F7) ─────────────────────────────────────────────────────────

_F3B_OPP = f"({sql_opp('P03')} = 1 AND {VALID_SQL})"
_LEGACY_WINDOWS = [
    ("", [("vpip", "CAST(hp.vpip AS DOUBLE)"), ("pfr", "CAST(hp.pfr AS DOUBLE)")]),
    ("AND hp.three_bet_opp = true", [("three_bet", "CAST(hp.three_bet AS DOUBLE)")]),
    (f"AND {_F3B_OPP}", [("fold_to_3bet", f"CAST({sql_case('P03')} AS DOUBLE)")]),
    ("AND hp.cbet_flop_opp = true", [("cbet_flop", "CAST(hp.cbet_flop AS DOUBLE)")]),
    ("AND hp.fold_to_cbet_flop IS NOT NULL",
     [("fold_to_cbet_flop", "CAST(hp.fold_to_cbet_flop AS DOUBLE)")]),
    ("AND hp.saw_flop = true", [("went_to_showdown", "CAST(hp.went_to_showdown AS DOUBLE)"),
                                ("wwsf", "CASE WHEN hp.won_bb > 0 THEN 1.0 ELSE 0.0 END")]),
    ("AND hp.went_to_showdown = true", [("won_at_showdown", "CAST(hp.won_at_showdown AS DOUBLE)")]),
    ("AND hp.steal_opp = true", [("steal", "CAST(hp.steal_attempted AS DOUBLE)")]),
    ("AND hp.faced_steal = true", [("fold_to_steal", "CAST(hp.fold_to_steal AS DOUBLE)")]),
]


def _legacy_windows(db, hero, where, params, ws):
    """The former per-group `ORDER BY played_at DESC, id DESC LIMIT ws` window queries."""
    out = {}
    base = ("FROM hand_players hp JOIN hands h ON hp.hand_id = h.id "
            "AND hp.workspace_id = h.workspace_id WHERE hp.player_id = ? AND h.workspace_id = 1 ")
    for opp, stats in _LEGACY_WINDOWS:
        cols = ", ".join(f"{e} AS c{i}" for i, (_, e) in enumerate(stats))
        row = db.execute(
            f"WITH r AS (SELECT {cols} {base} {where} {opp} ORDER BY h.played_at DESC, h.id DESC "
            f"LIMIT ?) SELECT {', '.join(f'AVG(c{i})' for i in range(len(stats)))}, COUNT(*) FROM r",
            [hero, *params, ws]).fetchone()
        for i, (k, _) in enumerate(stats):
            out[k] = (float(row[i]) if row[i] is not None else 0.0, int(row[len(stats)]))
    num, den, cnt = db.execute(
        f"WITH r AS (SELECT hp.flop_bets + hp.flop_raises AS num, hp.flop_bets + hp.flop_raises "
        f"+ hp.flop_calls + hp.flop_checks + hp.flop_folds AS den {base} {where} "
        f"AND hp.saw_flop = true ORDER BY h.played_at DESC, h.id DESC LIMIT ?) "
        f"SELECT SUM(num), SUM(den), COUNT(*) FROM r", [hero, *params, ws]).fetchone()
    return out, (int(num or 0), int(den or 0), int(cnt))


@pytest.mark.parametrize("params, where, wparams", [
    ({}, "", []),
    ({"game_mode": ""}, "AND h.game_mode = ?", [""]),
    ({"date_from": "2026-01-20"}, "AND h.played_at >= ?", ["2026-01-20"]),
    ({"stakes": "$0.05/$0.10", "date_from": "2026-01-10"},
     "AND h.stakes = ? AND h.played_at >= ?", ["$0.05/$0.10", "2026-01-10"]),
])
def test_drift_one_pass_matches_window_queries(client, bench_db, hero_id, monkeypatch,
                                                params, where, wparams):
    monkeypatch.setattr(rep, "DRIFT_MIN_HANDS", 1000)
    seen = {}

    def record(lt, w, n):  # always "drifts", so every stat's numbers come back
        seen.setdefault("calls", []).append((lt, w, n))
        return (0.0, 0.0, 1.0)
    monkeypatch.setattr(rep, "_check_drift", record)
    d = client.get("/api/reports/drift", params=params).json()
    total = d["total_hands"]
    assert total >= 1000
    ws = max(1, int(total * 0.20))
    assert d["window_hands"] == ws
    windows, (num, den, cnt) = _legacy_windows(bench_db, hero_id, where, wparams, ws)
    by_stat = {s["stat"]: s for s in d["stats"]}
    for k, (avg, n) in windows.items():
        if n < 30:
            assert k not in by_stat
            continue
        assert by_stat[k]["window_avg"] == round(avg * 100, 2), k
        assert by_stat[k]["window_n"] == n, k
    if den and cnt >= 30:
        assert by_stat["afq_flop"]["window_n"] == den
        assert by_stat["afq_flop"]["window_avg"] == round(num / den * 100, 2)
    # and the raw (unrounded) window figures fed to the drift test are the same
    expected = [(w, n) for k, (w, n) in windows.items() if n >= 30 and k in by_stat]
    got = [(w, n) for (_, w, n) in seen["calls"]][:len(expected)]
    assert sorted(got) == sorted(expected)


def test_drift_below_threshold(client):
    d = client.get("/api/reports/drift", params={"stakes": "$0.05/$0.10"}).json()
    assert d["stats"] == [] and d["window_hands"] == 0 and 0 < d["total_hands"] < 20000


# ── filter options (07/F8) ───────────────────────────────────────────────

def test_filter_options_one_scan(client, bench_db, hero_id):
    j = ("FROM hand_players hp JOIN hands h ON hp.hand_id = h.id "
         "AND hp.workspace_id = h.workspace_id WHERE hp.player_id = ? AND h.workspace_id = 1")
    stakes = [r[0] for r in bench_db.execute(
        f"SELECT DISTINCT h.stakes {j} ORDER BY h.stakes", [hero_id]).fetchall()]
    modes = [r[0] for r in bench_db.execute(
        f"SELECT DISTINCT h.game_mode {j} ORDER BY h.game_mode", [hero_id]).fetchall()]
    lo, hi = bench_db.execute(f"SELECT MIN(h.played_at), MAX(h.played_at) {j}",
                              [hero_id]).fetchone()
    got = client.get("/api/reports/filter-options").json()
    assert got == {"stakes": stakes, "game_modes": modes,
                   "date_range": {"min": str(lo)[:10], "max": str(hi)[:10]}}
    assert len(stakes) > 1 and len(modes) > 1
