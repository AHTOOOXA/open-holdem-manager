"""WP-L: the Stats page (stats_engine.py) counts like Hand2Note.

Hand-level vectors from docs/specs/H2N-COMPATIBLE-STATS.md section 8, run
through the real parser + H2N matcher and read back from /api/stats/hero.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import insert_parsed_hand
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from tests.test_h2n_matcher import hh


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _stats(client, db, *texts: str, **params) -> dict:
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))
    resp = client.get("/api/stats/hero", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _vs(sv: dict) -> tuple[float | None, int]:
    return sv["value"], sv["sample"]


def test_heads_up_button_steals_from_the_sb_column(client, db):
    """T4: H2N puts the heads-up button in SB; CO is never a steal seat."""
    s = _stats(client, db,
               hh(["Hero", "V"], "Hero R2.5, V F", max_seats=2, hand_no=1, collected={"Hero": 2}),
               hh(["B", "S", "BB", "U", "M", "Hero"], "U F, M F, Hero R2.5, B F, S F, BB F",
                  hand_no=2, collected={"Hero": 4}))
    assert _vs(s["steal"]["sb"]) == (100.0, 1)
    assert _vs(s["steal"]["btn"]) == (None, 0)
    assert _vs(s["steal"]["co"]) == (None, 0)  # the CO open is not a steal
    assert _vs(s["steal"]["total"]) == (100.0, 1)
    assert _vs(s["open_raise"]["sb"]) == (100.0, 1)
    assert _vs(s["open_raise"]["co"]) == (100.0, 1)
    assert _vs(s["open_raise"]["total"]) == (100.0, 2)


def test_squeeze_is_in_the_3bet_total_not_in_the_position_column(client, db):
    """T1: UTG opens, MP calls, Hero (CO) squeezes."""
    s = _stats(client, db, hh(["B", "S", "BB", "V1", "V2", "Hero"],
                              "V1 R2.5, V2 C, Hero R11, B F, S F, BB F, V1 F, V2 F",
                              hand_no=1, collected={"Hero": 17.5}))
    assert _vs(s["three_bet"]["total"]) == (100.0, 1)
    assert _vs(s["three_bet"]["co"]) == (None, 0)
    assert _vs(s["squeeze"]) == (100.0, 1)
    assert _vs(s["call_open_raise"]["total"]) == (None, 0)  # overcall spot, not a cold call
    assert _vs(s["three_bet_ip"]["total"]) == (None, 0)


def test_sb_complete_is_not_a_limp_but_a_limp_fold(client, db):
    """T8: BTN limps, Hero (SB) completes, BB raises, Hero folds."""
    s = _stats(client, db, hh(["V1", "Hero", "V2", "U", "M", "C"],
                              "U F, M F, C F, V1 C, Hero C, V2 R4, V1 F, Hero F",
                              hand_no=1, collected={"V2": 6}))
    assert _vs(s["limp"]["total"]) == (None, 0)
    assert _vs(s["limp_fold"]) == (100.0, 1)
    assert s["vpip"]["total"]["value"] == 100.0


def test_cbet_only_for_the_first_raiser(client, db):
    """T9: Hero 3-bets and c-bets: H2N's C-Bet is single-raised pots only;
    the opener's fold is a Fold to C-Bet (3-Bet Pot) case."""
    s = _stats(client, db, hh(["Hero", "S", "BB", "V", "M", "C"],
                              "V R2.5, M F, C F, Hero R8, S F, BB F, V C | V X, Hero B5, V F",
                              board=["Ah", "7c", "2d"], hand_no=1, collected={"Hero": 17.5}))
    assert _vs(s["cbet_flop"]["total"]) == (None, 0)
    assert _vs(s["three_bet"]["btn"]) == (100.0, 1)


def test_vpip_base_excludes_walks(client, db):
    s = _stats(client, db,
               hh(["V", "S", "Hero", "U", "M", "C"], "U F, M F, C F, V F, S F",
                  hand_no=1, collected={"Hero": 1.5}),
               hh(["V", "S", "Hero", "U", "M", "C"], "U F, M F, C F, V R2.5, S F, Hero C | Hero X, V B2, Hero F",
                  board=["Ah", "7c", "2d"], hand_no=2, collected={"V": 7}))
    assert s["hands"] == 2  # walks are hands
    assert _vs(s["vpip"]["total"]) == (100.0, 1)  # but no VPIP decision
    # BB calling a 2.5 bb open adds 1.5 bb: not a Fold to C-Bet spot (>= 2 bb rule)
    assert _vs(s["fold_to_cbet_flop"]["total"]) == (None, 0)
    assert _vs(s["call_open_raise"]["bb"]) == (100.0, 1)


def test_showdown_bases(client, db):
    """WTSD counts hands with a flop action (preflop all-ins left out), W$SD
    every showdown."""
    allin = hh(["V", "S", "Hero", "U", "M", "C"], "U F, M F, C F, V R100, S F, Hero C",
               board=["Ah", "7c", "2d", "9s", "3h"], cards={"Hero": "AsAd", "V": "KcKd"},
               shows=("Hero", "V"), hand_no=1, collected={"Hero": 200.5})
    s = _stats(client, db, allin)
    assert _vs(s["wtsd"]) == (None, 0)
    assert _vs(s["wwsf"]) == (None, 0)
    assert _vs(s["wsd"]) == (100.0, 1)


def test_position_filter_uses_h2n_groups(client, db):
    s = _stats(client, db,
               hh(["Hero", "V"], "Hero R2.5, V F", max_seats=2, hand_no=1, collected={"Hero": 2}),
               position="SB")
    assert s["hands"] == 1
    assert _vs(s["steal"]["sb"]) == (100.0, 1)
