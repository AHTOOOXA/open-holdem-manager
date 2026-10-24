"""General screen with a Reports chain: `chain` filter param, CellDetail.chain parity."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api import general_popup as gp
from app.api.import_hands import insert_parsed_hand
from app.general_filters import params_to_steps
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from app.reports import chain as chain_mod
from tests.test_general_popup import SIX, _cbet_hands
from tests.test_h2n_matcher import hh


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    invalidate_hero_cache()
    gp.clear_cache()
    chain_mod.clear_cache()
    yield TestClient(app)
    gp.clear_cache()
    chain_mod.clear_cache()


CARDS = {"Hero": "AhKd"}
UTG = ["X", "S", "B", "Hero", "M", "C"]   # hero under the gun


def _hands() -> list[str]:
    n = iter(range(100, 200))
    h = [
        # open raise EP (case) and a fold (opportunity only)
        hh(UTG, "Hero R2.5, M F, C F, X F, S F, B F", hand_no=next(n), cards=CARDS),
        hh(UTG, "Hero F, M F, C F, X F, S F, B F", hand_no=next(n), cards=CARDS),
        # 3-bet by hero on the button
        hh(SIX, "U F, M F, C R2.5, Hero R8, S F, B F, C F", hand_no=next(n), cards=CARDS),
        hh(SIX, "U F, M R2.5, C F, Hero R8, S F, B F, M F", hand_no=next(n), cards=CARDS),
        # limp-fold: hero limps, big blind raises, hero folds
        hh(SIX, "U F, M F, C F, Hero C, S F, B R4, Hero F", hand_no=next(n), cards=CARDS),
        hh(SIX, "U F, M F, C F, Hero C, S F, B C", hand_no=next(n), cards=CARDS),
    ]
    return h + _cbet_hands()


def _insert(db):
    for t in _hands():
        insert_parsed_hand(db, parse_hand_history(t))


def _detail(client, cell, **params):
    r = client.get(f"/api/general/cell/{cell}/detail", params=params)
    assert r.status_code == 200, r.text
    return r.json()


CELLS = ["preflop.open_raise.EP", "preflop.three_bet.BTN", "postflop.cbet.Flop",
         "preflop.limp_fold.Total", "preflop.open_raise.Total", "preflop.three_bet.Total"]


@pytest.mark.parametrize("cell", CELLS)
def test_cell_chain_parity(client, db, cell):
    _insert(db)
    d = _detail(client, cell)
    steps = d["chain"]
    assert steps[-1]["k"] == "row" and steps[-1]["key"] == d["row"] and steps[-1]["label"]
    r = client.post("/api/reports/preflop-range", json={"workspace_id": 1, "chain": steps})
    assert r.status_code == 200, r.text
    assert r.json()["total"] == d["cases"], (cell, d["cases"], r.json()["total"])
    s = client.post("/api/reports/split", json={"workspace_id": 1, "chain": steps,
                                                "type": "next_actions"})
    assert s.status_code == 200, s.text
    # the same chain with the filters as a dashboard chain
    d2 = _detail(client, cell, chain="[]")
    assert d2["cases"] == d["cases"] and d2["chain"] == steps


def test_cases_are_nonzero_somewhere(client, db):
    _insert(db)
    got = {c: _detail(client, c)["cases"] for c in CELLS}
    assert got["preflop.limp_fold.Total"] >= 1 and got["postflop.cbet.Flop"] >= 4, got
    assert got["preflop.open_raise.EP"] >= 1, got


def test_limp_fold_chain_excludes_bb(client, db):
    _insert(db)
    steps = _detail(client, "preflop.limp_fold.Total")["chain"]
    assert steps[0] == {"k": "pos", "v": ["EP", "MP", "CO", "BTN", "SB"]}


def test_param_filters_become_steps(client, db):
    _insert(db)
    d = _detail(client, "preflop.open_raise.EP", stakes="$0.50/$1", game_mode="Fast Fold",
                date_from="2026-01-01", date_to="2026-12-31")
    assert d["chain"][:3] == [
        {"k": "date", "from": "2026-01-01", "to": "2026-12-31"},
        {"k": "stakes", "v": ["$0.50/$1"]},
        {"k": "mode", "v": "fast"},
    ]
    assert params_to_steps(None, "", None, None) == [{"k": "mode", "v": "regular"}]
    # a checkpoint datetime is not a plain date: omitted
    assert params_to_steps(None, None, "2026-01-01 10:00:00", None) == []


def test_chain_param_equals_old_params(client, db):
    _insert(db)
    old = client.get("/api/general", params={"stakes": "$0.50/$1", "game_mode": "Fast Fold",
                                              "date_from": "2026-01-15"}).json()
    ch = json.dumps([{"k": "date", "from": "2026-01-15"}, {"k": "stakes", "v": ["$0.50/$1"]},
                     {"k": "mode", "v": "fast"}])
    new = client.get("/api/general", params={"chain": ch}).json()
    assert new == old and new["hands"] > 0
    reg_old = client.get("/api/general", params={"game_mode": ""}).json()
    reg_new = client.get("/api/general", params={"chain": json.dumps([{"k": "mode", "v": "regular"}])}).json()
    assert reg_new == reg_old
    assert client.get("/api/general", params={"chain": ch, "date_from": "2026-01-01"}).status_code == 422
    assert client.get("/api/general", params={"chain": ch, "game_mode": ""}).status_code == 422


def test_chain_param_rejects_other_steps(client, db):
    _insert(db)
    for bad in ('[{"k":"pos","v":["EP"]}]', '[{"k":"tsize","v":[6]}]', "not json",
                '[{"k":"mode","v":"nope"}]', '{"k":"mode"}'):
        assert client.get("/api/general", params={"chain": bad}).status_code == 422, bad
        assert client.get("/api/general/cell/preflop.open_raise.EP/detail",
                          params={"chain": bad}).status_code == 422, bad
        assert client.get("/api/general/cell/preflop.open_raise.EP/hands",
                          params={"chain": bad}).status_code == 422, bad


def test_chain_filters_detail_and_hands(client, db):
    _insert(db)
    ch = json.dumps([{"k": "stakes", "v": ["$9/$18"]}])
    assert _detail(client, "postflop.cbet.Flop", chain=ch)["opps"] == 0
    h = client.get("/api/general/cell/postflop.cbet.Flop/hands", params={"chain": "[]"})
    assert h.status_code == 200, h.text
