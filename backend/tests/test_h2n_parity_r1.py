"""Regressions from parity round 1 against Hand2Note 4.1's results on the same hands.

Fixture: tests/fixtures/ggpoker/h2n_parity_r1.txt, real GG hands where OHM
and H2N disagreed. Expected states are what Hand2Note reported for the hero
("oc" = opportunity + case, "o" = opportunity only, "-" = neither).

Root causes covered:
1. hands H2N refuses to import (corrupted amounts) are left out of the
   General screen (`h2n_valid`);
2. the regular big blind is the first "posts big blind" line: an
   out-of-turn BB poster keeps the ordinary position of his seat;
3. a bound villain (V1) is checked after the next fitting action is taken
   (flop "H:X > V1:X" fails when another villain checks in between);
4. Bet / Raise / Call X rows carry real opportunity bits (Aggression sample);
5. Open Raise / BB and Fold to 3Bet / BB are served by the API.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import insert_parsed_hand
from app.general_cells import GENERAL_CELLS, Counts, StatRef, evaluate_expr
from app.h2n import compute_h2n, hand_rejection
from app.h2n.rows import ROWS
from app.h2n.sequence import build_sequence, h2n_positions
from app.main import app
from app.parsers.ggpoker import parse_hand_history

FIXTURE = Path(__file__).parent / "fixtures" / "ggpoker" / "h2n_parity_r1.txt"


def _hands() -> dict[str, str]:
    out = {}
    for chunk in re.split(r"\n(?=Poker Hand #)", FIXTURE.read_text(encoding="utf-8")):
        chunk = chunk.strip()
        m = re.match(r"Poker Hand #(\w+)", chunk)
        if m:
            out[m.group(1)] = chunk
    return out


HANDS = _hands()


def _parsed(hand_id: str, text: str | None = None):
    return parse_hand_history(text or HANDS[hand_id])


def _state(cols: dict, key: str) -> str:
    slot = ROWS[key]
    opp = (cols[f"h2n_{slot.mask}_opp"] >> slot.bit) & 1
    case = (cols[f"h2n_{slot.mask}_case"] >> slot.bit) & 1
    return "oc" if case else ("o" if opp else "-")


def _hero(hand_id: str, text: str | None = None) -> dict:
    return compute_h2n(_parsed(hand_id, text), use_cache=False)["Hero"]


def _check(cols: dict, **expected: str) -> None:
    got = {k: _state(cols, k) for k in expected}
    assert got == expected


# ── 1. hands H2N refuses ─────────────────────────────────────────────────


@pytest.mark.parametrize("hand_id, why", [
    ("RC4215962397", "raises to"),    # BB post corrupted to $1.0, then "raises to $0.22"
    ("RC4220004289", "calls"),        # turn "calls $0.47" facing a $1.04 bet
    ("RC4219910075", "calls"),        # "calls $0.52" with $0.12 to call
    ("RC4218835922", "pot"),          # collected $2.1 from a $0.2 pot (negative rake)
    ("RC4273984333", "raises to"),    # SB post $0.15 > BB $0.1: H2N wants a raise above $0.3
    ("HD2670125044", "Bet & Muck"),   # action line H2N's GG reader does not know
])
def test_rejected_hands(hand_id, why):
    reason = hand_rejection(_parsed(hand_id))
    assert reason is not None and why in reason
    assert _hero(hand_id)["h2n_valid"] is False


@pytest.mark.parametrize("hand_id", [
    "HD2672337442",   # SB posts, then "straddle $0.1" (the player's total, not added on top)
    "RC4198732175",   # parser BB $0.25 at $0.02/$0.05: the raise check uses posted amounts
    "HD2672248487",   # out-of-turn BB + missed blind
    "RC4197234644",
])
def test_valid_hands_are_not_rejected(hand_id):
    assert hand_rejection(_parsed(hand_id)) is None
    assert _hero(hand_id)["h2n_valid"] is True


def test_unparsed_straddle_is_live_money():
    seq = build_sequence(_parsed("HD2672337442"))
    call = next(a for a in seq.streets[0] if a.name == "9be0237b")
    assert call.to_call == pytest.approx(0.1)   # he faces the straddle, not the big blind
    assert seq.reject is None


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def test_general_leaves_rejected_hands_out(client, db):
    for hid in ("RC4197234644", "RC4215962397"):
        insert_parsed_hand(db, _parsed(hid))
    db.execute("UPDATE workspaces SET hero_username = 'Hero', hero_site = 'GG' WHERE id = 1")
    flags = dict(db.execute(
        "SELECT h.id, hp.h2n_valid FROM hand_players hp JOIN hands h ON h.id = hp.hand_id "
        "JOIN players p ON p.id = hp.player_id WHERE p.username = 'Hero'").fetchall())
    assert sorted(flags.values()) == [False, True]
    data = client.get("/api/general").json()
    assert data["hands"] == 1
    assert data["cells"]["summary.vpip.Total"]["opps"] == 1  # RC4197234644 only


# ── 2. second big-blind poster ───────────────────────────────────────────


@pytest.mark.parametrize("hand_id, pos", [
    ("HD2671937740", "BB"),   # Hero is the regular BB; seat 3 posts an out-of-turn BB
    ("HD2672254465", "MP"),   # out-of-turn BB in seat 1 is not "the BB"
    ("HD2672248487", "EP"),   # posts big blind + missed blind
    ("HD2671933187", "BB"),
])
def test_out_of_turn_big_blind_keeps_seat_position(hand_id, pos):
    parsed = _parsed(hand_id)
    assert h2n_positions(parsed)["Hero"] == pos
    assert _hero(hand_id)["h2n_pos"] == pos


def test_out_of_turn_big_blind_vs_steal():
    # BTN opens after the out-of-turn poster checked: Hero (BB) faces a steal.
    _check(_hero("HD2671933187"), P26F="oc", P26C="o", P26R="o", P06="o", P08="o", P12="o")
    _check(_hero("HD2671937740"), P01="o")   # Open Raise / BB opportunity


# ── 3. V1 binding vs an intervening check ────────────────────────────────


def test_vs_missed_cbet_oop_needs_heads_up_checks():
    # Flop: Hero X, BB X, raiser X. The BB's check fits "V1:X" except for the
    # binding, so H2N stops there: no opportunity.
    _check(_hero("RC4200589832"), N03="-", N06="-")


def test_vs_missed_cbet_oop_when_other_villain_folds():
    # Same hand with the BB folding instead: a fold is skipped -> case.
    text = HANDS["RC4200589832"].replace(
        "Hero: checks\nd081e429: checks\n5fb066cf: checks",
        "Hero: checks\nd081e429: folds\n5fb066cf: checks",
    ).replace("Hero: bets $0.1\nd081e429: folds\n", "Hero: bets $0.1\n")
    assert text != HANDS["RC4200589832"]
    _check(_hero("RC4200589832", text), N03="oc", N06="oc")


# ── 4. opportunities of Bet / Raise / Call X ─────────────────────────────


def test_bet_raise_call_rows_have_opportunities():
    # Hero BB calls, flop: Hero X, villain B, Hero F (Hand2Note: Bet/Raise/Call Flop all O)
    _check(_hero("RC4197234644"), E_FLOP_B="o", E_FLOP_R="o", E_FLOP_C="o",
           E_FLOP_BR="o", E_FLOP_ANY="oc")
    # River: Hero X, then folds to a bet: bet, raise and call were all possible
    _check(_hero("HD2671937740"), E_FLOP_B="o", E_FLOP_R="-", E_FLOP_C="-",
           E_RIVER_B="o", E_RIVER_R="o", E_RIVER_C="o")
    # Turn bet after a checked-through flop
    _check(_hero("RC4200589832"), E_FLOP_B="o", E_TURN_B="oc", E_TURN_BR="oc")


def test_aggression_sample_is_max_of_bet_raise_call_opportunities():
    # Round 1 flop numbers: Bet 2470/7249, Raise 536/3149, Call 1073/3188, Any 8200
    cell = GENERAL_CELLS["postflop.af.Flop"]
    counts = {StatRef("E_FLOP_B"): Counts(2470, 7249), StatRef("E_FLOP_R"): Counts(536, 3149),
              StatRef("E_FLOP_C"): Counts(1073, 3188), StatRef("E_FLOP_ANY"): Counts(8200, 8200)}
    value, sample, _ = evaluate_expr(cell, counts)
    assert round(value, 1) == 2.8
    assert sample == 7249


# ── 5. BB cells (shown by Hand2Note 4.1, blank on the screenshot) ──────


def test_open_raise_and_fold_to_3bet_bb_cells(client, db):
    insert_parsed_hand(db, _parsed("HD2671937740"))
    db.execute("UPDATE workspaces SET hero_username = 'Hero', hero_site = 'GG' WHERE id = 1")
    cells = client.get("/api/general").json()["cells"]
    assert (cells["preflop.open_raise.BB"]["cases"], cells["preflop.open_raise.BB"]["opps"]) == (0, 1)
    assert cells["preflop.fold_to_3bet.BB"]["opps"] == 0


def test_amount_checks_only_apply_to_gg():
    # iPoker's parsed action order is not GG's; only the pot check runs there.
    from app.parsers import ipoker

    text = (Path(__file__).parent / "fixtures" / "ipoker" / "basic_hand.txt").read_text()
    parsed = ipoker.parse_hand_history(ipoker.split_hands(text)[0])
    assert build_sequence(parsed).reject is not None
    assert hand_rejection(parsed) is None
