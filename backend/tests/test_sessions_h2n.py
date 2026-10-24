"""Sessions (app/sessions_h2n.py, GET /api/sessions*, GET/PATCH /api/app-settings).

Rule vectors on the pure reference, the SQL build and the API on small synthetic databases
(exact timestamps), and invariants + session pages on the 20k-hand bench sample.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import sessions_h2n as sh
from app.api.sessions import list_sessions, live_session
from app.heroes import invalidate_hero_cache
from app.main import app
from app.reports import chain as chain_mod
from tests.test_reports_lite import bench_db, hero_id  # noqa: F401  (module fixtures)

T0 = dt.datetime(2026, 10, 17, 20, 10, 5)
MIN = dt.timedelta(minutes=1)
SEC = dt.timedelta(seconds=1)
DEFAULT_BREAK = 600


def _split(starts, max_break_s=DEFAULT_BREAK):
    return sh.split_sessions([(i, t) for i, t in enumerate(starts)], max_break_s)


# ── the rule ─────────────────────────────────────────────────────────────


def test_gap_of_12_59_joins_13_00_splits():
    assert len(_split([T0, T0 + 12 * MIN + 59 * SEC])) == 1
    assert len(_split([T0, T0 + 13 * MIN])) == 2
    # the join test is on the session end (last start + 180 s), not the first start
    chain = [T0 + i * 12 * MIN for i in range(10)]
    assert len(_split(chain)) == 1


def test_multi_table_overlap_merges():
    # two tables interleaved: hands overlap in time, one session
    a = [T0 + i * 2 * MIN for i in range(10)]
    b = [T0 + 30 * SEC + i * 2 * MIN for i in range(10)]
    s = _split(a + b)
    assert len(s) == 1 and len(s[0].members) == 20
    assert s[0].start == T0 and s[0].last_start == b[-1]


def test_max_break_setting_changes_the_split():
    starts = [T0, T0 + 13 * MIN]
    assert len(_split(starts, 600)) == 2
    assert len(_split(starts, 11 * 60)) == 1  # joins: 13:00 < 3:00 + 11:00
    assert len(_split([T0, T0 + 8 * MIN - SEC], 5 * 60)) == 1
    assert len(_split([T0, T0 + 8 * MIN], 5 * 60)) == 2  # 8:00 = 3:00 + 5:00, not less
    assert len(_split([T0, T0 + 4 * MIN], 60)) == 2  # 4:00 = 3:00 + 1:00 -> not less: splits


def test_duration_includes_the_hand_estimate():
    one = _split([T0])[0]
    assert one.end == T0 + 3 * MIN and one.duration_s == 180
    two = _split([T0, T0 + 5 * MIN])[0]
    assert two.duration_s == 8 * 60 and two.last_start == T0 + 5 * MIN


def test_explicit_end_times_and_ties():
    # a longer hand keeps the session open: end = max(end, hand end)
    s = sh.split_sessions([(1, T0, T0 + 10 * MIN), (2, T0 + MIN), (3, T0 + 19 * MIN)], 600)
    assert len(s) == 1 and s[0].end == T0 + 22 * MIN
    s = sh.split_sessions([(2, T0), (1, T0), (3, None)], 600)
    assert len(s) == 1 and s[0].members == [1, 2]  # ties by key, no-start hands skipped


def test_live_and_captions():
    end = T0 + 3 * MIN
    assert sh.is_live(end, end + 10 * MIN, 600)
    assert not sh.is_live(end, end + 10 * MIN + SEC, 600)
    now = dt.datetime(2026, 10, 24, 12, 0)
    assert sh.caption(T0, now=now) == "October 17, Saturday 20:10"
    assert sh.caption(dt.datetime(2025, 3, 7, 9, 5), now=now) == "2025 March 7, Friday 09:05"
    assert sh.caption(T0, numeric=True, now=now) == "17-10-2026, 20:10"
    assert sh.iso(T0) == "2026-10-17T20:10:05"


def test_time_stats_slots():
    aligned = dt.datetime(1970, 1, 1) + dt.timedelta(seconds=90 * 1000)
    ts = sh.time_stats([aligned], ["A"], 600)
    assert (ts.played_slots, ts.duration_s, ts.hands_per_hour) == (2, 180, 1 / (180 / 3600))
    ts = sh.time_stats([aligned + SEC], ["A"], 600)
    assert ts.played_slots == 3
    # two tables, hands every 45 s for 9 min: slots by start get 2 tables each
    starts = [aligned + dt.timedelta(seconds=45 * i) for i in range(12)]
    tables = ["A" if i % 2 else "B" for i in range(12)]
    ts = sh.time_stats(starts, tables, 600)
    assert ts.avg_tables == pytest.approx(2.0)
    assert ts.played_slots == (11 * 45 + 180 - 1) // 90 + 1 == 8  # slots 0..7
    assert ts.duration_s == 11 * 45 + 180
    # a break longer than max break is not played time
    ts = sh.time_stats([aligned, aligned + 60 * MIN], ["A", "A"], 600)
    assert ts.duration_s == 360 and ts.played_slots == 4


# ── SQL build + API on synthetic hands ───────────────────────────────────


def _seed(db, hands):
    """hands: (hand id, played_at, table, hero won $, [opponent ids]). bb = $0.10."""
    db.execute("INSERT INTO players (id, site_id, username) VALUES "
               "(1, 1, 'Hero'), (2, 1, 'Villain'), (3, 1, 'Other')")
    hp = 1
    for hid, t, table, won, opps in hands:
        db.execute("INSERT INTO hands (id, site_id, played_at, game_type, game_mode, stakes, "
                   "sb_amount, bb_amount, table_name, table_size, workspace_id) VALUES "
                   "(?, 1, ?, 'NLHE', '', '$0.05/$0.10', 0.05, 0.1, ?, 6, 1)", [hid, t, table])
        for pid, w in [(1, won)] + [(o, -won / len(opps)) for o in opps]:
            db.execute("INSERT INTO hand_players (id, hand_id, player_id, seat, position, won, "
                       "won_bb, all_in_ev_bb, workspace_id) VALUES (?, ?, ?, ?, 'BTN', ?, ?, ?, 1)",
                       [hp, hid, pid, pid, w, w * 10, w * 10 + 1, ])
            hp += 1
    invalidate_hero_cache()


@pytest.fixture
def synth(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    invalidate_hero_cache()
    chain_mod.clear_cache()
    yield db, TestClient(app)
    chain_mod.clear_cache()
    invalidate_hero_cache()


def _night(db):
    # S1 crosses midnight (16th 23:55 -> 17th 00:07), S2 on the 17th 20:10 (two tables)
    d16 = dt.datetime(2026, 10, 16, 23, 55)
    hands = [("h1", d16, "T1", 1.0, [2]), ("h2", d16 + 6 * MIN, "T1", -0.5, [2, 3]),
             ("h3", d16 + 12 * MIN, "T1", 2.0, [3])]
    hands += [(f"s2a{i}", T0 + i * 2 * MIN, "A", 0.1, [2]) for i in range(5)]
    hands += [(f"s2b{i}", T0 + 40 * SEC + i * 2 * MIN, "B", -0.2, [3]) for i in range(5)]
    _seed(db, hands)
    return d16


def test_sessions_api_shape_and_values(synth):
    db, c = synth
    d16 = _night(db)
    r = c.get("/api/sessions", params={"workspace_id": 1})
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"player", "sessions", "summary", "max_break_minutes"}
    assert j["player"] == {"id": 1, "username": "Hero", "site": "GG"}
    assert j["max_break_minutes"] == 10
    s2, s1 = j["sessions"]  # newest first
    assert set(s1) == {"id", "number", "start", "last_hand_at", "end", "duration_s", "is_live",
                       "hands", "won", "won_ev", "won_bb", "won_ev_bb", "filter"}
    assert (s1["number"], s2["number"]) == (1, 2)
    assert s1["start"] == "2026-10-16T23:55:00" and s1["last_hand_at"] == "2026-10-17T00:07:00"
    assert s1["end"] == "2026-10-17T00:10:00" and s1["duration_s"] == 15 * 60
    assert s1["id"] == sh.session_id(d16)
    assert s1["hands"] == 3 and s1["won"] == pytest.approx(2.5)
    assert s1["won_bb"] == pytest.approx(25) and s1["won_ev_bb"] == pytest.approx(28)
    assert s1["won_ev"] == pytest.approx(2.8)
    assert s1["is_live"] is False
    assert s1["filter"] == {"k": "session", "start": "2026-10-16T23:55:00",
                            "end": "2026-10-17T00:07:00", "label": "October 16, Friday 23:55"}
    assert s2["hands"] == 10 and s2["duration_s"] == 8 * 60 + 40 + 180
    summ = j["summary"]
    assert summ["hands"] == 13 and summ["duration_s"] == s1["duration_s"] + s2["duration_s"]
    assert summ["won"] == pytest.approx(s1["won"] + s2["won"])


def test_date_filter_semantics(synth):
    db, c = synth
    _night(db)
    j = c.get("/api/sessions", params={"date_from": "2026-10-17", "date_to": "2026-10-17"}).json()
    s2, s1 = j["sessions"]
    # S1 is listed (a hand after midnight) but counts only its in-range hands; Duration whole
    assert s1["hands"] == 2 and s1["won"] == pytest.approx(1.5)
    assert s1["duration_s"] == 15 * 60 and s1["number"] == 1
    assert s2["hands"] == 10
    assert j["summary"]["hands"] == 12
    j = c.get("/api/sessions", params={"date_to": "2026-10-16"}).json()
    assert [s["hands"] for s in j["sessions"]] == [1] and j["summary"] is None
    j = c.get("/api/sessions", params={"date_from": "2026-10-18"}).json()
    assert j["sessions"] == [] and j["player"]["username"] == "Hero" and j["summary"] is None
    assert c.get("/api/sessions", params={"date_from": "17-10-2026"}).status_code == 422
    # the session page ignores the date range: the row filter selects the whole session
    page = c.post("/api/reports/spot", json={"workspace_id": 1, "chain": [s1["filter"]],
                                             "recipe": "session"}).json()
    assert page["hands"] == 3


def test_no_hero_and_unknown_player(synth):
    db, c = synth
    j = c.get("/api/sessions").json()
    assert j == {"player": None, "sessions": [], "summary": None, "max_break_minutes": 10}
    assert c.get("/api/sessions/live").json() == {"live": False, "session_id": None,
                                                  "start": None}
    assert c.get("/api/sessions", params={"player_id": 999}).status_code == 404


def test_other_player_sessions(synth):
    db, c = synth
    _night(db)
    j = c.get("/api/sessions", params={"player_id": 2}).json()
    assert j["player"]["username"] == "Villain"
    assert sum(s["hands"] for s in j["sessions"]) == 2 + 5


def test_live(synth):
    db, c = synth
    now = dt.datetime.now().replace(microsecond=0)
    _seed(db, [("old", now - dt.timedelta(days=1), "T", 1.0, [2]),
               ("a", now - 5 * MIN, "T", 1.0, [2]), ("b", now - 2 * MIN, "T", 1.0, [2])])
    live = c.get("/api/sessions/live").json()
    assert live["live"] is True and live["start"] == sh.iso(now - 5 * MIN)
    assert live["session_id"] == sh.session_id(now - 5 * MIN)
    rows = c.get("/api/sessions").json()["sessions"]
    assert [r["is_live"] for r in rows] == [True, False]
    # boundary: now - end <= max break
    last_end = now - 2 * MIN + 3 * MIN
    assert live_session(db, 1, now=last_end + 10 * MIN)["live"] is True
    assert live_session(db, 1, now=last_end + 10 * MIN + SEC)["live"] is False
    rows = list_sessions(db, 1, now=last_end + 11 * MIN)["sessions"]
    assert not any(r["is_live"] for r in rows)


def test_app_settings_and_max_break(synth):
    db, c = synth
    _seed(db, [("a", T0, "T", 1.0, [2]), ("b", T0 + 13 * MIN, "T", 1.0, [2])])
    assert c.get("/api/app-settings").json() == {"session_max_break_minutes": 10,
                                                 "day_start_hour": 0,
                                                 "numeric_date_format": False}
    assert len(c.get("/api/sessions").json()["sessions"]) == 2
    r = c.patch("/api/app-settings", json={"session_max_break_minutes": 11})
    assert r.status_code == 200 and r.json()["session_max_break_minutes"] == 11
    j = c.get("/api/sessions").json()
    assert j["max_break_minutes"] == 11 and len(j["sessions"]) == 1
    r = c.patch("/api/app-settings", json={"numeric_date_format": True, "day_start_hour": 6})
    assert r.json() == {"session_max_break_minutes": 11, "day_start_hour": 6,
                        "numeric_date_format": True}
    assert c.get("/api/sessions").json()["sessions"][0]["filter"]["label"] == "17-10-2026, 20:10"
    for bad in ({"session_max_break_minutes": 0}, {"session_max_break_minutes": 241},
                {"session_max_break_minutes": "5"}, {"session_max_break_minutes": 5.5},
                {"day_start_hour": 24}, {"day_start_hour": -1}, {"numeric_date_format": 1},
                {"nope": 1}):
        assert c.patch("/api/app-settings", json=bad).status_code == 422, bad
    assert c.get("/api/app-settings").json()["session_max_break_minutes"] == 11


def test_session_pages_on_synthetic_hands(synth):
    db, c = synth
    _night(db)
    s2 = c.get("/api/sessions").json()["sessions"][0]
    chain = [s2["filter"]]

    def post(path, **kw):
        r = c.post(f"/api/reports/{path}", json={"workspace_id": 1, "chain": chain, **kw})
        assert r.status_code == 200, r.text
        return r.json()

    page = post("spot", recipe="session")
    stats = {s["id"]: s for s in page["stats"]}
    assert page["hands"] == 10
    assert stats["duration"]["value"] == s2["duration_s"]
    assert 1.0 <= stats["avg_tables"]["value"] <= 2.0
    assert stats["won"]["value"] == pytest.approx(s2["won"])
    tables = post("split", type="tables")
    assert [r["caption"] for r in tables["rows"]] == ["A", "B"]
    a = tables["rows"][0]
    assert a["filter"] == {"k": "table", "v": ["A"], "label": "A"}
    assert a["values"]["hands"] == 5 and a["values"]["duration"] == 8 * 60 + 180
    assert tables["summary"]["hands"] == 10
    players = post("split", type="players")
    assert [(r["player"]["username"], r["values"]["hands"]) for r in players["rows"]] == [
        ("Other", 5), ("Villain", 5)]
    v = players["rows"][1]
    assert v["filter"] == {"k": "with", "player_id": 1, "label": "Villain"}
    assert v["values"]["won"] == pytest.approx(-0.5)
    # the opened villain page shows the row's numbers
    vchain = chain + [v["filter"]]
    vp = c.post("/api/reports/spot", json={"workspace_id": 1, "player_id": v["player"]["id"],
                                           "chain": vchain, "recipe": "villain"}).json()
    assert vp["hands"] == 5
    assert {s["id"]: s["value"] for s in vp["stats"]}["ev_diff"] == pytest.approx(0.5)
    # table page then players
    tchain = chain + [a["filter"]]
    assert c.post("/api/reports/spot", json={"workspace_id": 1, "chain": tchain,
                                             "recipe": "table"}).json()["hands"] == 5
    h = c.get("/api/hands", params={"chain": json.dumps(tchain + [v["filter"]])}).json()
    assert h["total"] == 5


# ── bench sample ─────────────────────────────────────────────────────────


@pytest.fixture
def bench_client(bench_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(app_db, "_conn", bench_db)
    invalidate_hero_cache()
    chain_mod.clear_cache()
    yield TestClient(app)
    chain_mod.clear_cache()


def _hero_valid_hands(db, pid):
    return db.execute(
        "SELECT h.id, h.played_at FROM hand_players hp JOIN hands h ON h.id = hp.hand_id AND "
        "h.workspace_id = hp.workspace_id WHERE hp.player_id = ? AND "
        "COALESCE(hp.h2n_valid, TRUE)", [pid]).fetchall()


def test_bench_invariants(bench_db, hero_id):  # noqa: F811
    hands = _hero_valid_hands(bench_db, hero_id)
    rows = sh.build_sessions(bench_db, 1, hero_id, DEFAULT_BREAK)
    assert len(rows) > 50
    assert sum(r.total_hands for r in rows) == len(hands)
    ref = sh.split_sessions(hands, DEFAULT_BREAK)
    assert [(r.start, r.last_start, r.end, len(r.members)) for r in ref] == [
        (r.start, r.last_start, r.end, r.total_hands) for r in rows]
    for a, b in zip(rows, rows[1:]):
        assert a.end <= b.start  # no overlap
        assert (b.start - a.last_start).total_seconds() >= 13 * 60
        assert b.number == a.number + 1
    for r in rows:
        assert r.end == r.last_start + dt.timedelta(seconds=180)
    # every gap inside a session is < 13 min between starts
    by_start = sorted(t for _, t in hands)
    gaps_inside = [(b - a).total_seconds() for a, b in zip(by_start, by_start[1:])
                   if (b - a).total_seconds() < 13 * 60]
    assert len(gaps_inside) == len(hands) - len(rows)
    # a longer max break never yields more sessions
    assert len(sh.build_sessions(bench_db, 1, hero_id, 30 * 60)) < len(rows)


def test_bench_session_pages(bench_client, bench_db, hero_id):  # noqa: F811
    c = bench_client
    j = c.get("/api/sessions").json()
    rows = j["sessions"]
    assert j["player"]["username"] == "Hero"
    assert sum(r["hands"] for r in rows) == j["summary"]["hands"] == len(
        _hero_valid_hands(bench_db, hero_id))
    assert [r["start"] for r in rows] == sorted((r["start"] for r in rows), reverse=True)
    big = max(rows, key=lambda r: r["hands"])
    chain = [big["filter"]]
    page = c.post("/api/reports/spot", json={"workspace_id": 1, "chain": chain,
                                             "recipe": "session"}).json()
    stats = {s["id"]: s for s in page["stats"]}
    assert page["hands"] == big["hands"]
    assert stats["duration"]["value"] == big["duration_s"]
    assert stats["won"]["value"] == pytest.approx(big["won"])
    assert stats["won_ev"]["value"] == pytest.approx(big["won_ev"])
    assert 0 < stats["hands_h"]["value"] and stats["avg_tables"]["value"] >= 1
    # the plain Reports page of the same chain agrees on the shared stats
    plain = {s["id"]: s for s in c.post("/api/reports/spot", json={
        "workspace_id": 1, "chain": chain}).json()["stats"]}
    for k in ("vpip", "pfr", "threebet", "ag", "wtsd", "wsd", "wwsf"):
        assert stats[k]["value"] == plain[k]["value"], k
    g = c.get("/api/reports/graph", params={"chain": json.dumps(chain)}).json()
    assert len(g["points"]) == big["hands"]
    h = c.get("/api/hands", params={"chain": json.dumps(chain), "per_page": 5}).json()
    assert h["total"] == big["hands"]
