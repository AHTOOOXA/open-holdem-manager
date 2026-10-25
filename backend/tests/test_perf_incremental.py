"""Incremental caches (perf/incremental, INCREMENTAL-CACHES.md step 2).

- data_generation: append / derived / reset kinds, on_bump vs on_reset hooks, changes_since
  with a bounded log, thread safety;
- the import paths announce only the hands they inserted (bump_append), duplicates excluded;
  the player pass is derived;
- Reports resolutions warmed before an import are extended (not recomputed) and every Reports
  response afterwards equals a cold computation on the same data, floats bit for bit;
- stat popup records survive an import and only the new hands are replayed; the popup equals
  a cold one;
- a reset (clear, rebuild-style bump) still drops everything.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import data_generation as dg
from app.api import general_popup as gp
from app.api import import_hands as ih
from app.db import init_schema
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers import ggpoker
from app.reports import chain as chain_mod

BENCH = Path(__file__).parent / "fixtures" / "bench_sample_20k.txt"


# ── data_generation ──────────────────────────────────────────────────────


def test_changes_since_lists_appends_per_workspace_in_order():
    g0 = dg.current()
    g1 = dg.bump_append(1, ["a", "b"])
    dg.bump_append(2, ["c"])
    g3 = dg.bump_derived(1)
    dg.bump_append(1, ["d"])
    assert g1 == g0 + 1 and g3 == g0 + 3 and dg.current() == g0 + 4
    assert dg.changes_since(g0, 1) == ["a", "b", "d"]
    assert dg.changes_since(g0, 2) == ["c"]
    assert dg.changes_since(g1, 1) == ["d"]
    assert dg.changes_since(g3, 1) == ["d"]
    assert dg.changes_since(dg.current(), 1) == []
    assert dg.changes_since(g0, 3) == []
    assert dg.changes_since(dg.current() + 1, 1) is None      # from the future: unknown
    assert not dg.reset_since(g0)
    r = dg.bump()
    assert dg.reset_since(g0) and not dg.reset_since(r)
    assert dg.changes_since(g0, 1) is None                     # a reset since g0
    assert dg.changes_since(r, 1) == []
    dg.bump_append(1, ["e"])
    assert dg.changes_since(r, 1) == ["e"]


def test_changes_since_log_is_bounded(monkeypatch):
    monkeypatch.setattr(dg, "LOG_MAX_IDS", 5)
    monkeypatch.setattr(dg, "LOG_MAX_EVENTS", 3)
    dg.bump()
    g = dg.current()
    g1 = dg.bump_append(1, ["a", "b", "c"])
    dg.bump_append(1, ["d", "e"])
    assert dg.changes_since(g, 1) == ["a", "b", "c", "d", "e"]
    dg.bump_append(1, ["f"])                 # 6 ids: the oldest event goes
    assert dg.changes_since(g, 1) is None
    assert dg.changes_since(g1, 1) == ["d", "e", "f"]
    for x in "ghi":                          # event bound
        dg.bump_append(2, [x])
    assert dg.changes_since(g1, 1) is None
    assert dg.stats()["log_events"] <= 3 and dg.stats()["log_ids"] <= 5
    big = dg.bump_append(1, list("abcdefg"))  # one event over the id bound: kept nowhere
    assert dg.changes_since(big - 1, 1) is None
    assert dg.changes_since(big, 1) == []
    dg.bump()


def test_hooks_on_bump_every_change_on_reset_only_resets():
    calls = {"any": 0, "reset": 0, "both": 0}

    def any_():
        calls["any"] += 1

    def reset():
        calls["reset"] += 1

    def both():
        calls["both"] += 1

    def boom():
        raise RuntimeError("a failing hook must not fail the write")

    dg.on_bump(any_)
    dg.on_reset(reset)
    dg.on_bump(both)
    dg.on_reset(both)
    dg.on_bump(boom)
    try:
        dg.bump_append(1, ["x"])
        dg.bump_derived(1)
        assert calls == {"any": 2, "reset": 0, "both": 2}
        dg.bump()
        assert calls == {"any": 3, "reset": 1, "both": 3}   # registered twice, runs once
    finally:
        for lst, fn in ((dg._hooks, any_), (dg._reset_hooks, reset), (dg._hooks, both),
                        (dg._reset_hooks, both), (dg._hooks, boom)):
            lst.remove(fn)


def test_bumps_are_thread_safe():
    dg.bump()
    g = dg.current()
    n_threads, per = 8, 60   # 480 append events: within LOG_MAX_EVENTS

    def work(t):
        for i in range(per):
            dg.bump_append(1, [f"{t}-{i}"])
            if i % 7 == 0:
                dg.bump_derived(1)

    ts = [threading.Thread(target=work, args=(t,)) for t in range(n_threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    ids = dg.changes_since(g, 1)
    assert sorted(ids) == sorted(f"{t}-{i}" for t in range(n_threads) for i in range(per))
    assert dg.current() == g + n_threads * (per + len(range(0, per, 7)))
    for t in range(n_threads):   # each thread's own appends keep their order
        mine = [x for x in ids if x.startswith(f"{t}-")]
        assert mine == [f"{t}-{i}" for i in range(per)]


# ── fixture: part of the 20k sample, the rest imported through the real path ─


def _bench_hands() -> list[str]:
    if not BENCH.exists():
        pytest.skip("bench_sample_20k.txt not found")
    return [h.strip() for h in ggpoker.split_hands(BENCH.read_text()) if h.strip()]


FIRST = 6000                 # in the DB before the caches are warmed
CHUNKS = (700, 300, 1)       # imported afterwards, warm caches extended between them


def _new_db() -> duckdb.DuckDBPyConnection:
    ih.reset_import_cache()
    invalidate_hero_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
                 "VALUES (1, 1, 'Hero', 'manual')")
    return conn


def _import(conn, texts: list[str], full: bool = True) -> dict:
    with patch("app.api.import_hands._calc_equity", None):
        out = ih.import_hand_texts(conn, [(t, ggpoker) for t in texts], 1, full_finalize=full)
    ih.reset_import_cache()
    return out


@pytest.fixture(scope="module")
def hands():
    return _bench_hands()[:FIRST + sum(CHUNKS)]


@pytest.fixture
def live(hands, monkeypatch):
    """DB with the first FIRST hands; the client reads it."""
    conn = _new_db()
    _import(conn, hands[:FIRST])
    monkeypatch.setattr(app_db, "_conn", conn)
    invalidate_hero_cache()
    dg.bump()
    yield conn, TestClient(app)
    dg.bump()
    conn.close()
    invalidate_hero_cache()


# Plain and spot chains (row / line / next / faced / betsize), each with its responses.
CHAINS = [
    [],
    [{"k": "pos", "v": ["BB", "SB"]}],
    [{"k": "row", "key": "P01"}],
    [{"k": "row", "key": "P01"}, {"k": "faced", "street": "preflop", "a": "villain_3bet"}],
    [{"k": "pos", "v": ["BTN"]}, {"k": "next", "street": "preflop", "a": "raise"}],
    [{"k": "line", "dsl": "pre: H:R[3b]"}],
    [{"k": "row", "key": "C01"}],
]
SPLITS = ("results", "positions", "next_actions", "faced_next", "bet_sizing", "stack_sizes",
          "hour_of_day", "table_size", "tables", "players")
CELLS = ("preflop.open_raise.Total", "postflop.cbet.Flop", "summary.vpip.Total")


def _post(client, path: str, body: dict) -> dict:
    r = client.post(f"/api/reports/{path}", json={"workspace_id": 1, **body})
    assert r.status_code == 200, (path, body, r.text)
    return r.json()


def _reports(client) -> dict:
    out = {}
    for ch in CHAINS:
        k = json.dumps(ch)
        out[k, "spot"] = _post(client, "spot", {"chain": ch})
        for typ in SPLITS:
            out[k, typ] = _post(client, "split", {"chain": ch, "type": typ})
        out[k, "range"] = _post(client, "preflop-range", {"chain": ch})
        out[k, "flop"] = _post(client, "hand-strength", {"chain": ch, "street": "flop"})
    return out


def _popups(client) -> dict:
    out = {}
    for cell in CELLS:
        r = client.get(f"/api/general/cell/{cell}/detail")
        assert r.status_code == 200, r.text
        d = r.json()
        d.pop("replayed", None)
        out[cell] = d
        h = client.get(f"/api/general/cell/{cell}/hands", params={"per_page": 50})
        assert h.status_code == 200, h.text
        out[cell, "hands"] = h.json()
    return out


def _dumps(d: dict) -> dict:
    # repr keeps every float bit (json.dumps would too; this also shows -0.0 vs 0.0)
    return {k: json.dumps(v, sort_keys=True) for k, v in d.items()}


def _cold(client) -> tuple[dict, dict]:
    dg.bump()   # a reset: fresh-process caches
    return _reports(client), _popups(client)


def test_import_announces_only_inserted_hands(live, hands):
    conn, _client = live
    g = dg.current()
    a, b = hands[FIRST:FIRST + 3], hands[FIRST + 3:FIRST + 5]
    out = _import(conn, a + hands[:2], full=False)          # 2 duplicates
    assert out["imported"] == 3 and out["duplicates"] == 2
    ids = dg.changes_since(g, 1)
    assert ids == [ggpoker.extract_hand_id(t) for t in a]
    g2 = dg.current()
    _import(conn, b, full=True)                             # append, then the player pass
    assert dg.changes_since(g2, 1) == [ggpoker.extract_hand_id(t) for t in b]
    assert dg.current() >= g2 + 2                           # bump_append + bump_derived
    assert not dg.reset_since(g)
    g3 = dg.current()
    ih.finalize_import(conn, workspace_id=1)                # deferred auto-import pass: derived
    assert dg.changes_since(g3, 1) == [] and not dg.reset_since(g3)
    ih.finalize_import(conn, workspace_id=None)             # rebuild-wide pass: reset
    assert dg.reset_since(g3)


def test_warm_caches_extend_and_equal_a_cold_computation(live, hands, monkeypatch, caplog):
    conn, client = live
    computes = []
    real = chain_mod._compute

    def spy(db, ws, player, chain, day_start=0):
        computes.append(chain_mod.canonical(chain))
        return real(db, ws, player, chain, day_start)

    monkeypatch.setattr(chain_mod, "_compute", spy)
    from app.reports import split as split_mod
    lazy = []   # tables / sizing recomputed from all hands (should not happen after an import)
    real_table, real_sizing = split_mod._compute_action_table, split_mod._compute_sizing
    monkeypatch.setattr(split_mod, "_compute_action_table",
                        lambda db, res, which: (lazy.append(which), real_table(db, res, which))[1])
    monkeypatch.setattr(split_mod, "_compute_sizing",
                        lambda db, res: (lazy.append("sizing"), real_sizing(db, res))[1])
    extended = []
    real_extend = chain_mod._extend
    monkeypatch.setattr(chain_mod, "_extend",
                        lambda db, base, ids, ds: (extended.append(len(ids)),
                                                   real_extend(db, base, ids, ds))[1])
    _reports(client)
    _popups(client)
    spot_chains = [chain_mod.canonical(chain_mod.CHAIN.validate_python(c))
                   for c in CHAINS if any(s["k"] in chain_mod.SPOT_KINDS for s in c)]
    start = FIRST
    for n in CHUNKS:
        computes.clear()
        lazy.clear()
        extended.clear()
        replays = []
        real_replay = gp._replay_missing

        def counting(db, ws, user, row, street, missing, scope=None):
            replays.append(len(missing))
            return real_replay(db, ws, user, row, street, missing, scope)

        monkeypatch.setattr(gp, "_replay_missing", counting)
        _import(conn, hands[start:start + n], full=n > 1)   # last chunk: auto-import style
        start += n
        warm_reports, warm_popups = _reports(client), _popups(client)
        # spot chains were extended, never recomputed (plain ones recount in SQL)
        assert not set(computes) & set(spot_chains), computes
        assert len(extended) == len(CHAINS) and set(extended) == {n}, extended
        assert lazy == [], lazy   # Next / Faced / Sizing tables were extended, not rebuilt
        assert "extension failed" not in caplog.text
        # popups replayed only the new hands
        assert sum(replays) <= n * len(CELLS), (replays, n)
        monkeypatch.setattr(gp, "_replay_missing", real_replay)
        cold_reports, cold_popups = _cold(client)
        assert _dumps(warm_reports) == _dumps(cold_reports)
        assert _dumps(warm_popups) == _dumps(cold_popups)
        _reports(client)   # warm again for the next chunk (after the cold reset)
        _popups(client)


def test_extension_dedupes_hands_already_seen(live, hands):
    """A resolve that ran between an import's commit and its bump already has the new hands:
    the extension must not add them twice (rowid watermark)."""
    conn, client = live
    ch = [{"k": "row", "key": "P01"}]
    first = _post(client, "spot", {"chain": ch})
    texts = hands[FIRST:FIRST + 400]
    real = dg.bump_append
    seen = {}

    def late(ws, ids):           # a request resolves after the commit, before the bump
        seen["spot"] = _post(client, "spot", {"chain": ch})
        return real(ws, ids)

    with patch.object(dg, "bump_append", late):
        _import(conn, texts)
    after = _post(client, "spot", {"chain": ch})
    assert seen["spot"] != first
    dg.bump()
    cold = _post(client, "spot", {"chain": ch})
    assert json.dumps(after, sort_keys=True) == json.dumps(cold, sort_keys=True)


def test_unreported_write_is_caught_by_the_version(live, hands):
    conn, client = live
    ch = [{"k": "row", "key": "P01"}]
    _post(client, "spot", {"chain": ch})
    pending = []
    with patch("app.api.import_hands._calc_equity", None):
        for raw in hands[FIRST:FIRST + 50]:
            parsed = ggpoker.parse_hand_history(raw)
            pending.append((parsed, ih.compute_stat_flags(parsed), ih._compute_financials(parsed)))
        ih._flush_batch(conn, pending, workspace_id=1)       # no data_generation call at all
    ih.reset_import_cache()
    after = _post(client, "spot", {"chain": ch})
    dg.bump()
    assert json.dumps(after, sort_keys=True) == json.dumps(
        _post(client, "spot", {"chain": ch}), sort_keys=True)


def test_reset_drops_extending_caches(live, hands):
    conn, client = live
    _reports(client)
    _popups(client)
    assert len(chain_mod._CACHE) > 0 and gp.cache_stats()["records"] > 0
    _import(conn, hands[FIRST:FIRST + 20])
    assert len(chain_mod._CACHE) > 0 and gp.cache_stats()["records"] > 0   # kept on append
    r = client.post("/api/import/clear", params={"workspace_id": 1})
    assert r.status_code == 200, r.text
    assert len(chain_mod._CACHE) == 0
    assert gp.cache_stats() == {"records": 0, "bytes": 0, "segments": 0, "skipped": 0}
    spot = _post(client, "spot", {"chain": [{"k": "row", "key": "P01"}]})
    assert spot["hands"] == 0


def test_inflight_extension_is_shared_and_throttled(live, hands, monkeypatch):
    """Racing requests after an import share one extension, run in a heavy slot."""
    conn, client = live
    ch = chain_mod.CHAIN.validate_python([{"k": "row", "key": "P01"}])
    db = conn.cursor()
    base = chain_mod.resolve(db, 1, None, ch)
    _import(conn, hands[FIRST:FIRST + 100])
    calls = []
    gate = threading.Event()
    real = chain_mod._extend

    def slow(*a, **kw):
        calls.append(1)
        gate.wait(5)
        return real(*a, **kw)

    monkeypatch.setattr(chain_mod, "_extend", slow)
    from app import concurrency
    slots = []
    real_slot = concurrency.heavy_slot

    def counting_slot():
        slots.append(1)
        return real_slot()

    monkeypatch.setattr(chain_mod, "heavy_slot", counting_slot)
    out = [None, None]

    def run(i):
        c = conn.cursor()
        out[i] = chain_mod.resolve(c, 1, None, ch)
        c.close()

    ts = [threading.Thread(target=run, args=(i,)) for i in range(2)]
    for t in ts:
        t.start()
    for _ in range(200):
        if calls:
            break
        threading.Event().wait(0.01)
    gate.set()
    for t in ts:
        t.join()
    assert len(calls) == 1 and out[0] is out[1] and out[0] is not base
    assert len(out[0].hands) >= len(base.hands) and slots
    assert out[0].gen == dg.current()
    db.close()
