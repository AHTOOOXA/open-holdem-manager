"""Round-2 backend integration items (performance/, round 2 "integ-backend").

On the 20k bench DB of test_reports_lite (same module-scoped fixtures).
"""

from __future__ import annotations

import json

import pytest

import app.api.hands as H
import app.api.reports as rep
import app.api.reports_lite as rl
from app import concurrency
from tests.test_reports_lite import P01, bench_db, client, hero_id  # noqa: F401 (fixtures)


def _depth() -> int:
    return getattr(concurrency._local, "depth", 0)


@pytest.fixture
def slot_probe(monkeypatch):
    """Records the heavy-slot depth at every chain_scope call."""
    seen: list[int] = []
    real = rl.chain_scope

    def probe(*a, **k):
        seen.append(_depth())
        return real(*a, **k)

    monkeypatch.setattr(rl, "chain_scope", probe)
    return seen


@pytest.mark.parametrize("chain", [[], P01])
def test_graph_builds_chain_scope_outside_the_slot(client, slot_probe, monkeypatch, chain):
    rep._GRAPH_CACHE.clear()
    in_slot: list[int] = []
    real = rep.graph_series
    monkeypatch.setattr(rep, "graph_series",
                        lambda *a, **k: in_slot.append(_depth()) or real(*a, **k))
    r = client.get("/api/reports/graph", params={"chain": json.dumps(chain)})
    assert r.status_code == 200, r.text
    assert slot_probe == [0]      # the resolve throttles itself; no idle slot held meanwhile
    assert in_slot == [1]         # the series itself still runs in a slot
    rep._GRAPH_CACHE.clear()


@pytest.mark.parametrize("chain", [[], P01])
def test_export_builds_chain_scope_outside_the_slot(client, slot_probe, monkeypatch, chain):
    in_slot: list[int] = []
    real = H._export_query
    monkeypatch.setattr(H, "_export_query",
                        lambda *a, **k: in_slot.append(_depth()) or real(*a, **k))
    r = client.get("/api/hands/export", params={"chain": json.dumps(chain)})
    assert r.status_code == 200, r.text
    assert r.content.count(b"Poker Hand #") > 0
    assert slot_probe == [0]
    assert in_slot == [1]
