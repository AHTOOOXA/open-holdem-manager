"""GET/PUT /api/statistics/dashboards (app/api/statistics_dashboards.py)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.main import app

URL = "/api/statistics/dashboards"


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def dash(i, name="d", parent=None, filters=None):
    return {"id": i, "kind": "dashboard", "name": name, "parent_id": parent,
            "definition": {"player_id": None, "filters": filters or [], "profile_id": "default"}}


def folder(i, name="f", parent=None):
    return {"id": i, "kind": "folder", "name": name, "parent_id": parent}


def doc(nodes, selected=None, width=300):
    return {"nodes": nodes, "config": {"selected_id": selected, "collapsed": False,
                                       "tree_width": width}}


def put(client, d, ws=1):
    return client.put(URL, params={"workspace_id": ws}, json=d)


def test_seed_when_empty(client):
    d = client.get(URL, params={"workspace_id": 1}).json()
    assert d == doc([dash(1, "new dashboard")], selected=1)


def test_roundtrip_keeps_preset_and_label(client, db):
    f = [{"k": "date", "from": "2026-01-01", "to": "2026-01-31", "preset": "last_30", "label": "L"},
         {"k": "stakes", "v": ["$0.50/$1"]}, {"k": "mode", "v": "fast"}]
    r = put(client, doc([folder(1, "A"), dash(2, "x", 1, f)], selected=2, width=500))
    assert r.status_code == 200, r.text
    got = client.get(URL, params={"workspace_id": 1}).json()
    assert got["nodes"][1]["definition"]["filters"] == f
    assert got["config"] == {"selected_id": 2, "collapsed": False, "tree_width": 500}
    key = db.execute("SELECT key FROM settings WHERE key LIKE 'statistics_dashboards.%'").fetchall()
    assert key == [("statistics_dashboards.1",)]


@pytest.mark.parametrize("nodes,width", [
    ([dash(1), dash(1, "b")], 300),                       # duplicate ids
    ([dash(1, parent=9)], 300),                           # missing parent
    ([dash(1), dash(2, parent=1)], 300),                  # parent is a dashboard
    ([folder(1, parent=2), folder(2, parent=1), dash(3)], 300),   # cycle
    ([folder(1, parent=1), dash(3)], 300),                # self parent
    ([dash(1, "   ")], 300),                              # empty name
    ([dash(1, "x" * 201)], 300),                          # long name
    ([folder(1)], 300),                                   # no dashboards
    ([dash(1)], 279), ([dash(1)], 1001),                  # width
    ([dash(1, filters=[{"k": "pos", "v": ["EP"]}])], 300),        # non-plain step
    ([dash(1, filters=[{"k": "row", "key": "P01"}])], 300),
    ([dash(1, filters=[{"k": "mode", "v": "nope"}])], 300),       # invalid plain step
    ([dash(1, filters=[{"k": "mode", "v": "fast", "zzz": 1}])], 300),  # extra key
])
def test_validation_422(client, nodes, width):
    assert put(client, doc(nodes, width=width)).status_code == 422


def test_boundary_values_and_name_limit(client):
    assert put(client, doc([dash(1, "x" * 200)], selected=1, width=280)).status_code == 200
    assert put(client, doc([dash(1, " a ")], selected=1, width=1000)).json()["nodes"][0]["name"] == "a"


def test_selected_fixed_to_first_in_tree_order(client):
    nodes = [dash(1, "zz"), folder(2, "B"), dash(3, "inB", 2), folder(4, "A"),
             dash(5, "inA2", 4), dash(6, "inA1", 4), dash(7, "aa")]
    # tree order: A(4)[inA1(6), inA2(5)], B(2)[inB(3)], aa(7), zz(1) -> first dashboard is 6
    for sel in (99, 2, None):
        assert put(client, doc(nodes, selected=sel)).json()["config"]["selected_id"] == 6
    assert put(client, doc(nodes, selected=7)).json()["config"]["selected_id"] == 7


def test_workspaces_are_separate_and_deleted_with_workspace(client, db):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Two')")
    assert put(client, doc([dash(1, "two")], selected=1), ws=2).status_code == 200
    assert client.get(URL, params={"workspace_id": 1}).json()["nodes"][0]["name"] == "new dashboard"
    assert client.get(URL, params={"workspace_id": 9}).status_code == 404
    assert client.delete("/api/workspaces/2").status_code == 200
    assert db.execute("SELECT COUNT(*) FROM settings WHERE key = 'statistics_dashboards.2'"
                      ).fetchone()[0] == 0


def test_dangling_ancestor_is_422(client):
    # node 3's parent (2) exists and is a folder, but 2's own parent (9) does not
    nodes = [folder(2, parent=9), dash(3, parent=2), dash(1)]
    assert put(client, doc(nodes)).status_code == 422
    # listed before its dangling ancestor: still 422, never a 500
    assert put(client, doc([dash(3, parent=2), folder(2, parent=9), dash(1)])).status_code == 422
