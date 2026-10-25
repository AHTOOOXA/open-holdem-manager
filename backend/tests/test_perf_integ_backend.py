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


# ── Export: ordered ids, texts fetched per chunk (hands review minor) ───────────────────────


@pytest.mark.parametrize("params", [
    {}, {"sort": "won_bb", "order": "asc"}, {"chain": json.dumps(P01), "sort": "tags"},
])
def test_export_text_chunks_keep_bytes_and_order(client, monkeypatch, params):
    whole = client.get("/api/hands/export", params=params)
    assert whole.status_code == 200 and whole.content
    monkeypatch.setattr(H, "_EXPORT_FETCH", 7)   # many chunks, a short last one
    chunked = client.get("/api/hands/export", params=params)
    assert chunked.content == whole.content
    assert chunked.headers.get("x-ohm-truncated") == whole.headers.get("x-ohm-truncated")


def test_export_query_returns_ids_not_texts(client, bench_db, monkeypatch):
    """The ordered query carries only (id, ord); texts come in chunks of _EXPORT_FETCH."""
    monkeypatch.setattr(H, "EXPORT_CAP", 50)
    f = H._list_filters(bench_db, position=None, stakes=None, result=None, marked=None,
                        tag_ids=None, date_from=None, date_to=None, search=None, stat_flag=None,
                        stat_key=None, player_id=None, workspace_id=1, chain=None)
    ids, truncated = H._export_query(bench_db, f, sort="played_at", order="desc", workspace_id=1)
    assert truncated and ids.column_names == ["id", "ord"] and ids.num_rows == 50
    assert ids.column("ord").to_pylist() == list(range(1, 51))
    texts = H._export_texts(bench_db, ids.slice(10, 5), 1)
    want = [bench_db.execute("SELECT raw_text FROM hands WHERE id = ? AND workspace_id = 1",
                             [i]).fetchone()[0] for i in ids.column("id").to_pylist()[10:15]]
    assert texts == want
