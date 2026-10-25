"""Reports perf track: the CPU throttle (app.concurrency.heavy_slot) lives in one place.

- A cold spot-chain resolve runs in a slot, inside `chain.resolve`, whoever calls it (Reports
  endpoints, hand list, graph); a plain resolve (two COUNT queries) takes none.
- Requests waiting for another request's resolve, or for its computation of the same
  response / table (`Resolution.memo`), hold no slot while they wait.
- Slot holders (e.g. a graph handler that resolves inside its own slot) and slot-less callers
  racing on one cold chain don't deadlock: the in-flight owner always holds its slot.
- A cached response is served even while every slot is busy.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager

import pytest

import app.db as app_db
from app import concurrency
from app.reports import chain as chain_mod
from app.reports import split as split_mod
from app.reports import views

from tests.test_perf_reports_core import bench_db, hero_id  # noqa: F401  (fixtures)

P01 = [{"k": "row", "key": "P01"}]
C01 = [{"k": "row", "key": "C01"}]


@pytest.fixture
def ohm(bench_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(app_db, "_conn", bench_db)
    chain_mod.clear_cache()
    yield bench_db
    chain_mod.clear_cache()


def _free_slots() -> int:
    return concurrency._sem._value


def _wait_until(cond, timeout=10.0):
    ev = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if cond():
            return True
        ev.wait(0.01)
    return cond()


def _run(fn, n=1):
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


def _join(ts, timeout=60.0):
    for t in ts:
        t.join(timeout)
    assert not any(t.is_alive() for t in ts), "deadlock / hang"


def test_spot_resolve_takes_a_slot_plain_does_not(ohm, monkeypatch):
    depth = []

    @contextmanager
    def slot():
        depth.append(1)
        yield

    real = chain_mod._compute
    inside = []

    def spy(*a, **k):
        inside.append(len(depth))
        return real(*a, **k)

    monkeypatch.setattr(chain_mod, "heavy_slot", slot)
    monkeypatch.setattr(chain_mod, "_compute", spy)
    steps = chain_mod.CHAIN.validate_python(P01)
    chain_mod.resolve(ohm.cursor(), 1, None, steps)
    assert inside == [1]
    chain_mod.resolve(ohm.cursor(), 1, None, steps)          # cached: no slot, no compute
    assert inside == [1] and len(depth) == 1
    chain_mod.resolve(ohm.cursor(), 1, None, chain_mod.CHAIN.validate_python([]))
    assert inside == [1, 1] and len(depth) == 1              # plain: computed without a slot


def test_resolve_waiters_hold_no_slot(ohm, monkeypatch):
    """One request computes a cold spot chain (one slot); three more wait for it without a
    slot, so another heavy request can still run meanwhile."""
    gate, started = threading.Event(), threading.Event()
    real = chain_mod._compute
    calls = []

    def slow(*a, **k):
        calls.append(1)
        started.set()
        gate.wait(20)
        return real(*a, **k)

    monkeypatch.setattr(chain_mod, "_compute", slow)
    steps = chain_mod.CHAIN.validate_python(C01)
    free = _free_slots()
    owner, out, errs = _run(lambda: chain_mod.resolve(ohm.cursor(), 1, None, steps))
    assert started.wait(10)
    waiters, out2, errs2 = _run(lambda: chain_mod.resolve(ohm.cursor(), 1, None, steps), 3)
    assert _wait_until(lambda: len(chain_mod._inflight) == 1)
    threading.Event().wait(0.3)          # the waiters reach flight.done.wait()
    assert _free_slots() == free - 1     # only the owner holds one
    with concurrency.heavy_slot():       # another heavy request is not blocked
        pass
    gate.set()
    _join(owner + waiters)
    assert not errs and not errs2
    assert len(calls) == 1 and all(r is out[0] for r in out2)
    assert _free_slots() == free and not chain_mod._inflight


def test_slot_holders_and_slotless_callers_racing_do_not_deadlock(ohm, monkeypatch):
    """Both slots held by handlers that resolve inside their own slot (like the graph
    endpoint), plus a slot-less caller (hand list) asking for the same cold chain: the
    slot-less one waits for a slot without registering the in-flight entry, a slot holder
    computes, everyone gets the one result."""
    assert concurrency.MAX_HEAVY == 2
    real = chain_mod._compute
    calls = []

    def slow(*a, **k):
        calls.append(1)
        threading.Event().wait(0.2)
        return real(*a, **k)

    monkeypatch.setattr(chain_mod, "_compute", slow)
    steps = chain_mod.CHAIN.validate_python(P01)
    holding, go = threading.Barrier(3), threading.Event()

    def holder():
        with concurrency.heavy_slot():
            holding.wait(10)
            go.wait(10)
            return chain_mod.resolve(ohm.cursor(), 1, None, steps)

    holders, out, errs = _run(holder, 2)
    holding.wait(10)                     # both slots are taken
    assert _free_slots() == 0
    free_caller, out2, errs2 = _run(lambda: chain_mod.resolve(ohm.cursor(), 1, None, steps))
    threading.Event().wait(0.3)          # it is blocked on the semaphore, no entry registered
    assert not chain_mod._inflight
    go.set()
    _join(holders + free_caller)
    assert not errs and not errs2
    assert len(calls) == 1
    assert out[0] is out[1] is out2[0]


def test_memo_waiters_hold_no_slot_and_compute_once(ohm, hero_id, monkeypatch):  # noqa: F811
    db = ohm.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(P01), 0)
    gate, started = threading.Event(), threading.Event()
    real = split_mod._compute_sizing
    calls = []

    def slow(db_, res_):
        calls.append(1)
        started.set()
        gate.wait(20)
        return real(db_, res_)

    monkeypatch.setattr(split_mod, "_compute_sizing", slow)
    free = _free_slots()
    ts, out, errs = _run(lambda: split_mod.split(ohm.cursor(), res, "bet_sizing"))
    assert started.wait(10)
    ts2, out2, errs2 = _run(lambda: split_mod.split(ohm.cursor(), res, "bet_sizing"), 2)
    threading.Event().wait(0.3)
    assert _free_slots() == free - 1
    gate.set()
    _join(ts + ts2)
    assert not errs and not errs2 and len(calls) == 1
    assert out2[0] is out[0] and out2[1] is out[0]
    db.close()


def test_cached_response_served_while_all_slots_are_busy(ohm, hero_id):  # noqa: F811
    db = ohm.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(P01), 0)
    first = views.spot(db, res)
    holding, release = threading.Barrier(3), threading.Event()

    def holder():
        with concurrency.heavy_slot():
            holding.wait(10)
            release.wait(20)

    holders, _o, _e = _run(holder, 2)
    holding.wait(10)
    try:
        ts, out, errs = _run(lambda: views.spot(ohm.cursor(), res))
        for t in ts:
            t.join(5)
        assert out and out[0] is first, "a cached response waited for a slot"
    finally:
        release.set()
        _join(holders)
    db.close()
