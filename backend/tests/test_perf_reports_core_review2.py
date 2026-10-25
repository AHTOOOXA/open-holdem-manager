"""Reports perf track, second review round.

- Plain chains read each case hand's records and its stored sequence blob in one query
  (`chain.iter_case_seqs`, chunked, nothing kept): the same values as the record path, and
  the Next Actions / Faced Next tables equal the previous algorithm (records + a separate
  blob query) bit for bit.
- `Resolution.memo` hands a computed value to the requests already waiting for it even when
  the value is over its cap and not kept (Players at 214k page 0): racing requests compute
  it once. A failed computation lets its waiters try again.
- The Players table is sorted in Arrow (hands descending, username, id) in the order of the
  previous Python sort key.
"""

from __future__ import annotations

import threading

import pytest

from app.reports import chain as chain_mod
from app.reports import split as split_mod

from tests.test_perf_reports_core import (  # noqa: F401  (fixtures)
    _plain_chains, _reference, bench_db, hero_id,
)

_FIELDS = ("hid", "won", "won_bb", "ev_bb", "ev", "rake", "sd", "win", "pre_opp", "pre_case",
           "post_case", "rake_bb")


def test_case_seqs_equal_records_and_stored_blobs(bench_db, hero_id):  # noqa: F811
    db = bench_db.cursor()
    for ch in ([], [{"k": "pos", "v": ["SB", "BB"]}], [{"k": "stakes", "v": ["no such"]}]):
        res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(ch), 0)
        chunks = list(chain_mod.iter_case_seqs(db, res, chunk=997))
        recs = [r for c, _b in chunks for r in c]
        assert len(recs) == res.n_cases
        if not res.n_cases:
            assert not chunks
            continue
        assert len(chunks) > 1
        old = [h for c in chain_mod.iter_records(db, res) for h in c]
        assert [tuple(getattr(r, f) for f in _FIELDS) for r in recs] == [
            tuple(getattr(h, f) for f in _FIELDS) for h in old]
        assert all(type(r.won) is float and type(r.sd) is bool for r in recs)
        stored = chain_mod.fetch_seqs(db, 1, [h.hid for h in old])
        blobs = {k: v for _c, b in chunks for k, v in b.items()}
        assert len(blobs) == res.n_cases
        assert {k: v for k, v in blobs.items() if v is not None} == stored
        assert not res.blobs and not res.tables
    db.close()


def _old_action_table(db, res, which):
    """The previous plain-chain table: records chunk by chunk, blobs by a second query."""
    cands, ev = split_mod._candidates(res.ctx, which)
    table: dict = {}
    for recs in chain_mod.iter_records(db, res):
        ids = [h.hid for h in recs]
        blobs = chain_mod.fetch_seqs(db, res.workspace_id, ids)
        src = chain_mod.SeqSource(db, res.workspace_id, blobs)
        src.prefetch_missing([h for h in ids if blobs.get(h) is None])
        for h in recs:
            seq = src.get(h.hid)
            if seq is None:
                continue
            p = seq.index.get(res.username)
            if p is not None:
                split_mod._table_add(table, cands, ev, seq, p, h)
    return table


def _slots(acc):
    return {s: getattr(acc, s) for s in split_mod.Acc.__slots__}


def test_plain_action_tables_equal_the_previous_algorithm(bench_db, hero_id):  # noqa: F811
    db = bench_db.cursor()
    for ch in _plain_chains(db, hero_id):
        res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(ch), 0)
        for which in ("next", "faced"):
            got = split_mod._compute_action_table(db, res, which)
            ref = _old_action_table(db, res, which)
            assert got.keys() == ref.keys(), (ch, which)
            for k in got:
                assert _slots(got[k]) == _slots(ref[k]), (ch, which, k)
        if ch == []:
            ref_res = _reference(db, res, ordered=True)
            for typ in ("next_actions", "faced_next"):
                assert split_mod._split(db, res, typ) == split_mod._split(db, ref_res, typ)
        assert not res.blobs
    db.close()


def _race(n, fn):
    out, errs = [], []

    def body():
        try:
            out.append(fn())
        except BaseException as e:  # noqa: BLE001  (reported by the test)
            errs.append(e)

    ts = [threading.Thread(target=body, daemon=True) for _ in range(n)]
    for t in ts:
        t.start()
    return ts, out, errs


def _join(ts):
    for t in ts:
        t.join(60)
    assert not any(t.is_alive() for t in ts), "deadlock / hang"


@pytest.mark.parametrize("heavy", [True, False])
def test_over_cap_value_shared_by_racing_waiters(heavy):
    res = chain_mod.Resolution(1, 1, "Hero", [], None, False, 0)
    gate, started = threading.Event(), threading.Event()
    calls = []

    def compute():
        calls.append(1)
        started.set()
        gate.wait(20)
        return object()

    ts, out, errs = _race(1, lambda: res.memo(("k",), compute, max_bytes=0, heavy=heavy))
    assert started.wait(10)
    ts2, out2, errs2 = _race(3, lambda: res.memo(("k",), compute, max_bytes=0, heavy=heavy))
    threading.Event().wait(0.3)   # the waiters reach the flight
    gate.set()
    _join(ts + ts2)
    assert not errs and not errs2
    assert len(calls) == 1 and all(v is out[0] for v in out2)
    assert ("k",) not in res.tables and not res._flights and res.table_bytes == 0
    # Not kept: the next request (after the burst) computes it again.
    assert res.memo(("k",), compute, max_bytes=0) is not out[0] and len(calls) == 2


def test_failed_computation_lets_waiters_retry():
    res = chain_mod.Resolution(1, 1, "Hero", [], None, False, 0)
    gate, started = threading.Event(), threading.Event()
    calls = []

    def compute():
        calls.append(1)
        if len(calls) == 1:
            started.set()
            gate.wait(20)
            raise RuntimeError("boom")
        return "ok"

    ts, out, errs = _race(1, lambda: res.memo(("k",), compute))
    assert started.wait(10)
    ts2, out2, errs2 = _race(2, lambda: res.memo(("k",), compute))
    threading.Event().wait(0.3)
    gate.set()
    _join(ts + ts2)
    assert len(errs) == 1 and not out and not errs2
    assert out2 == ["ok", "ok"] and len(calls) == 2
    assert res.tables[("k",)] == "ok" and not res._flights


def test_racing_players_requests_over_both_caps_compute_once(bench_db, hero_id,  # noqa: F811
                                                              monkeypatch):
    """The reviewer's race: Players table over TABLE_MAX_BYTES and response over
    MEMO_MAX_BYTES (page 0 at 214k); three racing requests compute the table once."""
    db = bench_db.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(
        [{"k": "row", "key": "C01"}]), 0)
    monkeypatch.setattr(split_mod, "TABLE_MAX_BYTES", 0)
    monkeypatch.setattr(split_mod, "_response_bytes", lambda d: 1 << 40)
    real = split_mod._players_table
    gate, started = threading.Event(), threading.Event()
    calls = []

    def slow(db_, res_):
        calls.append(1)
        started.set()
        gate.wait(20)
        return real(db_, res_)

    monkeypatch.setattr(split_mod, "_players_table", slow)
    ts, out, errs = _race(1, lambda: split_mod.split(bench_db.cursor(), res, "players"))
    assert started.wait(10)
    ts2, out2, errs2 = _race(2, lambda: split_mod.split(bench_db.cursor(), res, "players"))
    threading.Event().wait(0.3)
    gate.set()
    _join(ts + ts2)
    assert not errs and not errs2 and len(calls) == 1
    assert out[0]["rows"] and all(o is out[0] for o in out2)
    assert ("players_table",) not in res.tables and ("split", "players") not in res.tables
    db.close()


def test_players_sorted_like_the_python_key(bench_db, hero_id):  # noqa: F811
    """The Players table is sorted in Arrow (hands desc, username, id): the Python order."""
    import pyarrow as pa

    db = bench_db.cursor()
    for ch in ([], [{"k": "row", "key": "P01"}]):
        res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(ch), 0)
        t = split_mod._players_table(db, res)
        assert len(t) > 1000
        assert t == sorted(t, key=lambda x: (-x[2].hands, x[1], x[0]))
    # Arrow string order = Python str order, also outside ASCII.
    names = ["b", "B", "a", "ä", "Ω", "z", "日本", "😀", "aa", "", "Z9", "é", "é"]
    tbl = pa.table({"n": [3] * len(names), "k1": names, "k0": list(range(len(names)))})
    got = tbl.sort_by([("n", "descending"), ("k1", "ascending"), ("k0", "ascending")])
    assert got.column("k1").to_pylist() == sorted(names)
    db.close()
