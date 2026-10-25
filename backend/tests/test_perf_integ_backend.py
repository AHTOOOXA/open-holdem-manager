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


# ── Workspace delete refreshes first/last seen (import review minor) ─────────────────────────


def test_delete_workspace_refreshes_first_last_seen(db, monkeypatch):
    from pathlib import Path

    from fastapi.testclient import TestClient

    import app.main as app_main
    from app import db as app_db
    from app.api.import_hands import _update_first_last_seen, insert_parsed_hand
    from app.parsers.ggpoker import parse_hand_history

    monkeypatch.setattr(app_db, "_conn", db)
    api = TestClient(app_main.app)
    ws = api.post("/api/workspaces", json={"name": "W2", "hero_username": "Hero",
                                              "hero_site": "GG"}).json()["id"]
    text = (Path(__file__).parent / "fixtures" / "ggpoker" / "sample.txt").read_text()
    hands = [h.strip() for h in text.split("\n\n\n") if h.strip()]
    for w in (1, ws):
        for h in hands:
            insert_parsed_hand(db, parse_hand_history(h), workspace_id=w)
    # The second workspace's copies are played a month later and earlier: they set every
    # shared player's first and last seen.
    db.execute("UPDATE hands SET played_at = played_at + INTERVAL 30 DAY WHERE workspace_id = ? "
               "AND id IN (SELECT id FROM hands WHERE workspace_id = ? ORDER BY played_at DESC "
               "LIMIT 2)", [ws, ws])
    db.execute("UPDATE hands SET played_at = played_at - INTERVAL 30 DAY WHERE workspace_id = ? "
               "AND id IN (SELECT id FROM hands WHERE workspace_id = ? ORDER BY played_at "
               "LIMIT 2)", [ws, ws])
    _update_first_last_seen(db, "")
    want = dict((pid, (lo, hi)) for pid, lo, hi in db.execute(
        "SELECT hp.player_id, MIN(h.played_at), MAX(h.played_at) FROM hand_players hp "
        "JOIN hands h ON h.id = hp.hand_id AND h.workspace_id = hp.workspace_id "
        "WHERE h.workspace_id = 1 GROUP BY 1").fetchall())
    seen = lambda: {pid: (lo, hi) for pid, lo, hi in db.execute(  # noqa: E731
        "SELECT id, first_seen, last_seen FROM players WHERE id IN (SELECT UNNEST(?::INTEGER[]))",
        [list(want)]).fetchall()}
    assert seen() != want          # the shifted copies moved some players' range

    assert api.delete(f"/api/workspaces/{ws}").status_code == 200
    assert seen() == want


# ── batch_update_player_types: optional player filter (import track hand-off) ────────────────


def test_player_filter_recomputes_only_those_players(db):
    from pathlib import Path

    from app.api.import_hands import insert_parsed_hand
    from app.parsers.ggpoker import parse_hand_history
    from app.player_classification import batch_update_player_types

    text = (Path(__file__).parent / "fixtures" / "ggpoker" / "sample.txt").read_text()
    for h in [h.strip() for h in text.split("\n\n\n") if h.strip()]:
        insert_parsed_hand(db, parse_hand_history(h), workspace_id=1)
    state = lambda: db.execute(  # noqa: E731
        "SELECT player_id, workspace_id, player_type, is_reg FROM player_classifications "
        "ORDER BY ALL").fetchall()
    batch_update_player_types(db, workspace_id=1)
    full = state()
    pids = sorted({r[0] for r in full})
    assert len(pids) >= 4
    some = pids[::2]
    db.execute("UPDATE player_classifications SET player_type = 'X', is_reg = NULL")
    db.execute("CREATE TEMP TABLE _some AS SELECT UNNEST(?::INTEGER[]) AS player_id", [some])
    batch_update_player_types(db, workspace_id=1, players_sql="SELECT player_id FROM _some")
    got = state()
    assert [r for r in got if r[0] in some] == [r for r in full if r[0] in some]
    assert all(r[2] == "X" and r[3] is None for r in got if r[0] not in some)
