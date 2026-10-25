"""Reports perf track: the SQL / Arrow paths of plain chains equal the per-record Python paths.

On the 20k bench sample (tests/fixtures/bench_sample_20k.txt, hero "Hero"):

- plain chains (no spot step) aggregate in SQL / Arrow instead of building one HandRec per
  hand: every Stats / plain split / Tables / recipe / range / strength response is compared
  with the previous algorithm (records fetched with the old DECIMAL query, folded with
  `Acc.add`) and must be equal, floats bit for bit;
- the Players split is one SQL GROUP BY: counts exact, money within float rounding of the
  per-record sums (exact DECIMAL sums vs sequential float sums) and equal at display precision;
- spot chains fill the Next / Faced tables while resolving: equal to the lazy tables;
- cache: byte-bounded LRU, cleared by data_generation.bump, oversized entries not kept;
  racing table requests compute once; plain resolutions keep no records or blobs.
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
from app.api.import_hands import BATCH_SIZE, _compute_financials, _flush_batch, reset_import_cache
from app.db import init_schema
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers.ggpoker import parse_hand_history, split_hands
from app.reports import chain as chain_mod
from app.reports import split as split_mod
from app.reports import views
from app.reports.spots import START
from app.stat_flags import compute_stat_flags

BENCH = Path(__file__).parent / "fixtures" / "bench_sample_20k.txt"

# The resolve SELECT before the DOUBLE casts (Python Decimal per money value).
_OLD_COLS = """h.id, COALESCE(hp.won, 0), COALESCE(hp.won_bb, 0),
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0),
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount,
           COALESCE(hp.rake, 0), COALESCE(hp.went_to_showdown, FALSE),
           COALESCE(hp.is_winner, FALSE), hp.h2n_pos, hp.stack_bb, h.played_at, h.stakes,
           h.bb_amount, h.game_mode, h.table_size, hp.card1, hp.card2,
           hp.hv_flop, hp.hv_turn, hp.hv_river,
           COALESCE(hp.h2n_pre_opp, 0), COALESCE(hp.h2n_pre_case, 0),
           COALESCE(hp.h2n_post_opp, 0), COALESCE(hp.h2n_post_case, 0),
           COALESCE(hp.rake_bb, 0), h.table_name"""


def _old_rec(r) -> chain_mod.HandRec:
    f = lambda x: float(x) if x is not None else 0.0  # noqa: E731
    return chain_mod.HandRec(
        hid=r[0], case=True, hit=None, won=f(r[1]), won_bb=f(r[2]), ev_bb=f(r[3]), ev=f(r[4]),
        rake=f(r[5]), sd=bool(r[6]), win=bool(r[7]), pos=r[8],
        stack_bb=None if r[9] is None else float(r[9]), played_at=r[10], stakes=r[11],
        bb_amount=f(r[12]), mode=r[13] or "", tsize=r[14], card1=r[15], card2=r[16],
        hv_flop=r[17], hv_turn=r[18], hv_river=r[19], pre_opp=int(r[20]), pre_case=int(r[21]),
        post_opp=int(r[22]), post_case=int(r[23]), rake_bb=f(r[24]), table=r[25],
    )


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


def _plain_chains(db, hero_id) -> list[list[dict]]:
    stakes = [r[0] for r in db.execute(
        "SELECT stakes FROM hands GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 2").fetchall()]
    day = db.execute("SELECT CAST(MIN(played_at) AS DATE) + 3 FROM hands").fetchone()[0].isoformat()
    t0, t1 = db.execute("SELECT MIN(played_at), MIN(played_at) + INTERVAL 3 HOUR FROM hands"
                        ).fetchone()
    table = db.execute("SELECT table_name FROM hands WHERE table_name IS NOT NULL "
                       "GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    vid = db.execute("SELECT hp.player_id FROM hand_players hp WHERE hp.player_id <> ? "
                     "GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1", [hero_id]).fetchone()[0]
    return [
        [],
        [{"k": "stakes", "v": [stakes[0]]}],
        [{"k": "stakes", "v": stakes}, {"k": "pos", "v": ["BTN", "CO"]}],
        [{"k": "pos", "v": ["BB"]}],
        [{"k": "mode", "v": "fast"}],
        [{"k": "mode", "v": "regular"}],
        [{"k": "tsize", "v": [6]}],
        [{"k": "date", "from": day}],
        [{"k": "date", "to": day}],
        [{"k": "hour", "v": [10, 11, 12, 22]}],
        [{"k": "stack", "lo": 40, "hi": 120}],
        [{"k": "stack", "lo": 200}],
        [{"k": "cells", "v": ["AA", "AKs", "T9o", "72o"]}],
        [{"k": "hv", "street": "flop", "cats": ["other"]}],
        [{"k": "session", "start": t0.isoformat(), "end": t1.isoformat()}],
        [{"k": "table", "v": [table]}],
        [{"k": "with", "player_id": vid}],
        [{"k": "game", "stakes": stakes[0], "mode": "fast", "tsize": 6}],
        [{"k": "stakes", "v": ["no such stakes"]}],   # empty
    ]


def _reference(db, res: chain_mod.Resolution, *, ordered: bool) -> chain_mod.Resolution:
    """The previous resolution of a plain chain: one HandRec per case hand from the DECIMAL
    query, as a records-backed Resolution so the views run their per-record loops."""
    sql = f"SELECT {_OLD_COLS} {chain_mod._FROM} WHERE {res.where}"
    if ordered:
        sql += chain_mod.ORDER
    recs = [_old_rec(r) for r in db.execute(sql, res.params).fetchall()]
    ref = chain_mod.Resolution(res.workspace_id, res.player_id, res.username, res.chain, START,
                               True, res.total_hands, hands=recs, n_cases=len(recs))
    ref.blobs = chain_mod.fetch_seqs(db, res.workspace_id, [h.hid for h in recs])
    return ref


PLAIN_SPLITS = ("results", "positions", "stack_sizes", "hour_of_day", "table_size", "tables")


def _responses(db, res) -> dict:
    mb = 1800
    out = {"spot": views._spot(db, res)}
    for typ in PLAIN_SPLITS:
        out[typ] = split_mod._split(db, res, typ)
    for name in ("session", "table", "villain"):
        out["recipe " + name] = views._recipe(db, res, name, mb)
    out["range"] = views._preflop_range(db, res)
    for street in ("flop", "turn", "river"):
        out["strength " + street] = views._hand_strength(db, res, street)
    return out


def _compare(a, b, path="") -> tuple[int, int]:
    """Structure and integers equal; floats: (bit-different, different at 2 decimals)."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        tot = (0, 0)
        for k in a:
            d = _compare(a[k], b[k], f"{path}.{k}")
            tot = (tot[0] + d[0], tot[1] + d[1])
        return tot
    if isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        tot = (0, 0)
        for i, (x, y) in enumerate(zip(a, b)):
            d = _compare(x, y, f"{path}[{i}]")
            tot = (tot[0] + d[0], tot[1] + d[1])
        return tot
    if isinstance(a, float) and isinstance(b, float):
        assert a == pytest.approx(b, rel=1e-12, abs=1e-9), path
        return int(a != b), int(_disp(a) != _disp(b))
    assert a == b and type(a) is type(b), path
    return 0, 0


def _disp(x) -> int:
    return round(x * 100)   # half-even on the scaled double, like lib/format fixed(x, 2)


def test_plain_chains_equal_the_record_path(bench_db, hero_id):
    """Stats, plain splits, Tables, recipes, range and strength over the same hands in the
    same order: identical responses, floats bit for bit."""
    db = bench_db.cursor()
    for ch in _plain_chains(bench_db, hero_id):
        steps = chain_mod.CHAIN.validate_python(ch)
        res = chain_mod._compute(db, 1, hero_id, steps, 0)
        assert res.plain and isinstance(res.hands, chain_mod.PlainCases)
        ref = _reference(db, res, ordered=True)
        assert res.n_cases == len(ref.hands) == len(res.hands), ch
        if not ch:
            assert res.n_cases == res.total_hands
        assert chain_mod.case_ids(db, res) == [h.hid for h in ref.hands]
        assert _responses(db, res) == _responses(db, ref), ch
    db.close()


def test_plain_chains_match_the_previous_unordered_sums(bench_db, hero_id):
    """Against the previous query (no ORDER BY): bit-identical where its plan returned the
    hands in insertion order (most chains); otherwise only the summation order differs, so
    floats agree to ~1e-15 relative and at display precision."""
    db = bench_db.cursor()
    identical = 0
    chains = _plain_chains(bench_db, hero_id)
    for ch in chains:
        steps = chain_mod.CHAIN.validate_python(ch)
        res = chain_mod._compute(db, 1, hero_id, steps, 0)
        ref = _reference(db, res, ordered=False)
        bits, shown = _compare(_responses(db, res), _responses(db, ref), json.dumps(ch))
        assert shown == 0, ch
        identical += bits == 0
    assert identical >= len(chains) - 3
    db.close()


def test_plain_next_actions_equal_the_record_path(bench_db, hero_id):
    """Page-0 Next Actions streams the cases in chunks without keeping their blobs."""
    db = bench_db.cursor()
    for ch in ([], [{"k": "pos", "v": ["SB", "BB"]}]):
        steps = chain_mod.CHAIN.validate_python(ch)
        res = chain_mod._compute(db, 1, hero_id, steps, 0)
        ref = _reference(db, res, ordered=True)
        got = split_mod._split(db, res, "next_actions")
        assert got["rows"]
        assert got == split_mod._split(db, ref, "next_actions"), ch
        assert not res.blobs   # F3: nothing pinned on the plain resolution
        small = chain_mod._compute(db, 1, hero_id, steps, 0)
        chunks = list(chain_mod.iter_records(db, small, chunk=997))
        assert sum(len(c) for c in chunks) == res.n_cases and len(chunks) > 1
    db.close()


def test_double_casts_equal_float_of_decimal(bench_db, hero_id):
    """01/F4: every per-row money value fetched as DOUBLE is Python's float(Decimal)."""
    db = bench_db.cursor()
    where, params = chain_mod._BASE_WHERE, [hero_id, 1]
    old = {r[0]: _old_rec(r) for r in db.execute(
        f"SELECT {_OLD_COLS} {chain_mod._FROM} WHERE {where}", params).fetchall()}
    new = {r[0]: chain_mod._rec(r) for r in db.execute(
        f"{chain_mod._SELECT} WHERE {where}", params).fetchall()}
    assert old.keys() == new.keys() and len(old) > 19_000
    for hid, o in old.items():
        n = new[hid]
        for f in ("won", "won_bb", "ev_bb", "ev", "rake", "rake_bb", "bb_amount", "stack_bb",
                  "pos", "stakes", "mode", "card1", "card2", "table", "hv", "pre_opp",
                  "pre_case", "post_opp", "post_case", "sd", "win", "tsize", "played_at"):
            assert getattr(n, f) == getattr(o, f), (hid, f)
            if isinstance(getattr(o, f), float):
                assert type(getattr(n, f)) is float
    db.close()


@pytest.mark.parametrize("chain", [[], [{"k": "pos", "v": ["BTN"]}], [{"k": "row", "key": "P01"}]])
def test_players_split_equals_the_record_path(bench_db, hero_id, chain):
    """05/S2: the SQL GROUP BY per opponent equals folding the opponents' records."""
    db = bench_db.cursor()
    steps = chain_mod.CHAIN.validate_python(chain)
    res = chain_mod._compute(db, 1, hero_id, steps, 0)
    ids = chain_mod.case_ids(db, res)
    accs: dict[int, tuple[str, split_mod.Acc]] = {}
    for pid, name, rec in chain_mod.opponent_recs(db, 1, ids, hero_id):
        ent = accs.get(pid)
        if ent is None:
            ent = accs[pid] = (name, split_mod.Acc())
        ent[1].add(rec)
    ref = sorted(((pid, name, acc) for pid, (name, acc) in accs.items()),
                 key=lambda t: (-t[2].hands, t[1], t[0]))
    got = split_mod.players_table(db, res)
    assert [(p, n) for p, n, _ in got] == [(p, n) for p, n, _ in ref]
    flips = 0
    for (_p, _n, a), (_p2, _n2, b) in zip(got, ref):
        for s in split_mod.Acc.__slots__:
            x, y = getattr(a, s), getattr(b, s)
            if isinstance(y, float) or isinstance(x, float):
                assert x == pytest.approx(y, rel=1e-12, abs=1e-9), s
                flips += _disp(x) != _disp(y)
            else:
                assert x == y, s
    # Exact DECIMAL sums vs sequential float sums differ only in the last bits; a displayed
    # cent can only move when the exact sum ends in .xx5 (then the old value was arbitrary).
    assert flips <= len(got) // 1000
    db.close()


@pytest.mark.parametrize("chain", [
    [{"k": "row", "key": "P01"}], [{"k": "row", "key": "C01"}],
    [{"k": "row", "key": "P01"}, {"k": "faced", "street": "preflop", "a": "villain_3bet"}],
    [{"k": "pos", "v": ["BTN"]}, {"k": "next", "street": "preflop", "a": "raise"}],
])
def test_tables_filled_while_resolving_equal_lazy_tables(bench_db, hero_id, chain):
    """01/F5: Next / Faced tables built in the resolve loop = computed afterwards."""
    db = bench_db.cursor()
    steps = chain_mod.CHAIN.validate_python(chain)
    res = chain_mod._compute(db, 1, hero_id, steps, 0)
    filled = [w for w in ("next", "faced") if ("table", w) in res.tables]
    assert filled
    for which in filled:
        pre = res.tables[("table", which)]
        lazy = split_mod._compute_action_table(db, res, which)
        assert pre.keys() == lazy.keys()
        for k in pre:
            assert [getattr(pre[k], s) for s in split_mod.Acc.__slots__] == \
                   [getattr(lazy[k], s) for s in split_mod.Acc.__slots__], (which, k)
    db.close()


def test_chain_scope_plain_is_sql_and_matches_ids(bench_db, hero_id):
    from app.api.reports_lite import chain_hand_ids, chain_scope
    cur = bench_db.cursor()
    for ch in _plain_chains(bench_db, hero_id)[:8] + [[{"k": "row", "key": "P01"}]]:
        chain_mod.clear_cache()
        text = json.dumps(ch)
        ids = chain_hand_ids(cur, 1, None, text)
        scope = chain_scope(cur, 1, None, text)
        assert scope.count == len(ids)
        if ch and ch[0]["k"] != "row":
            assert "UNNEST" not in scope.sql and "_ohm_ids_" not in scope.sql   # pure SQL
        pred, params = scope.where("h.id")
        got = [r[0] for r in cur.execute(
            f"SELECT h.id FROM hands h WHERE h.workspace_id = 1 AND {pred}", params).fetchall()]
        assert sorted(got) == sorted(ids)
    cur.close()


def test_spot_response_carries_total_hands_and_is_cached(client, bench_db, hero_id):
    q = {"workspace_id": 1, "chain": [{"k": "pos", "v": ["BTN"]}]}
    first = client.post("/api/reports/spot", json=q).json()
    total = bench_db.execute(
        "SELECT COUNT(*) FROM hand_players WHERE player_id = ? AND COALESCE(h2n_valid, TRUE)",
        [hero_id]).fetchone()[0]
    assert first["total_hands"] == total and first["hands"] < total
    p01 = client.post("/api/reports/spot", json={**q, "chain": [{"k": "row", "key": "P01"}]}).json()
    assert p01["total_hands"] == total
    steps = chain_mod.CHAIN.validate_python(q["chain"])
    res = chain_mod.resolve(bench_db.cursor(), 1, None, steps)
    assert ("spot",) in res.tables
    assert client.post("/api/reports/spot", json=q).json() == first
    split = client.post("/api/reports/split", json={**q, "type": "positions"}).json()
    assert ("split", "positions") in res.tables
    assert client.post("/api/reports/split", json={**q, "type": "positions"}).json() == split


def test_racing_requests_compute_a_table_once(bench_db, hero_id, monkeypatch):
    """01/F9: two threads asking for Bet Sizing of one resolution compute it once."""
    db = bench_db.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(
        [{"k": "row", "key": "P01"}]), 0)
    calls = []
    real = split_mod._compute_sizing
    gate = threading.Event()

    def slow(db_, res_):
        calls.append(1)
        gate.wait(2)
        return real(db_, res_)

    monkeypatch.setattr(split_mod, "_compute_sizing", slow)
    out = []
    ts = [threading.Thread(target=lambda: out.append(split_mod.sizing_table(bench_db.cursor(), res)))
          for _ in range(2)]
    for t in ts:
        t.start()
    threading.Event().wait(0.3)   # let the second one reach the table's lock
    gate.set()
    for t in ts:
        t.join()
    assert len(calls) == 1 and out[0] is out[1]
    db.close()


def test_cache_bounded_by_bytes_and_cleared_on_bump(bench_db, hero_id, monkeypatch):
    from app import data_generation
    db = bench_db.cursor()
    plain = chain_mod._compute(db, 1, hero_id, [], 0)
    spot = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(
        [{"k": "row", "key": "P01"}]), 0)
    assert plain.approx_bytes() < 64 * 1024            # no records, no blobs
    assert spot.approx_bytes() > len(spot.hands) * chain_mod.REC_BYTES
    lru = chain_mod._LRU(32, spot.approx_bytes() + plain.approx_bytes() + 1)
    lru.put("a", spot)
    lru.put("b", plain)
    assert len(lru) == 2
    lru.put("c", spot)                                 # over budget: oldest goes
    assert lru.get("a") is None and lru.get("b") is plain and lru.get("c") is spot
    tiny = chain_mod._LRU(32, 1024)
    tiny.put("x", spot)                                # one entry over the whole budget
    assert len(tiny) == 0
    monkeypatch.setattr(app_db, "_conn", bench_db)
    chain_mod.resolve(db, 1, None, [])
    assert len(chain_mod._CACHE) >= 1
    data_generation.bump()
    assert len(chain_mod._CACHE) == 0
    db.close()


def test_strings_interned_in_records(bench_db, hero_id):
    db = bench_db.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(
        [{"k": "row", "key": "P01"}]), 0)
    by_stakes = {}
    for h in res.hands:
        prev = by_stakes.setdefault(h.stakes, h.stakes)
        assert prev is h.stakes
    db.close()


def test_reports_endpoints_take_a_heavy_slot(client, monkeypatch):
    from contextlib import contextmanager
    from app.api import reports_lite
    entered = []

    @contextmanager
    def slot():
        entered.append(1)
        yield

    monkeypatch.setattr(reports_lite, "heavy_slot", slot)
    q = {"workspace_id": 1, "chain": []}
    assert client.post("/api/reports/spot", json=q).status_code == 200
    assert client.post("/api/reports/split", json={**q, "type": "positions"}).status_code == 200
    assert client.post("/api/reports/preflop-range", json=q).status_code == 200
    assert client.post("/api/reports/hand-strength", json={**q, "street": "flop"}).status_code == 200
    assert len(entered) == 4


def test_waiters_share_an_uncacheable_result(bench_db, monkeypatch):
    """An entry over the whole cache budget is not kept, but requests waiting on its
    computation get it instead of recomputing."""
    monkeypatch.setattr(app_db, "_conn", bench_db)
    monkeypatch.setattr(chain_mod, "_CACHE", chain_mod._LRU(32, 1))
    calls = []
    real = chain_mod._compute
    gate = threading.Event()

    def slow(*a, **k):
        calls.append(1)
        gate.wait(2)
        return real(*a, **k)

    monkeypatch.setattr(chain_mod, "_compute", slow)
    steps = chain_mod.CHAIN.validate_python([{"k": "row", "key": "C01"}])
    out = []
    ts = [threading.Thread(target=lambda: out.append(chain_mod.resolve(bench_db.cursor(), 1, None, steps)))
          for _ in range(3)]
    for t in ts:
        t.start()
    threading.Event().wait(0.3)   # let the other two reach the in-flight lock
    gate.set()
    for t in ts:
        t.join()
    assert len(calls) == 1 and out[0] is out[1] is out[2]
    assert not chain_mod._inflight and len(chain_mod._CACHE) == 0
