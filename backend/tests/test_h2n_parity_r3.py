"""Regressions from parity round 3 against Hand2Note 4.1's results on the same hands.

Fixture: tests/fixtures/ggpoker/h2n_parity_r3.txt, real GG hands where OHM
and H2N disagreed. Expected values are what Hand2Note reported for the hero.

Root causes covered:
1. Hit action of a definition with OR-ed rows: H2N takes the **earliest**
   hit among all rows that hit (cases first, then opportunity rows), not the
   first row in definition order. VPIP (``H:R | H:C``) on "Hero cold-calls,
   then raises" hits the call.
2. GG parser BB: header and posted BB agree, but a deep all-in is above
   500 bb (NL5, $33 stacks). `_detect_bb` dropped the agreed BB; H2N keeps
   it, so hands.bb_amount / won_bb / the stakes bucket were wrong.
3. Hand value per street: H2N only classifies streets up to the last street
   on which anyone acted (unless the player folded earlier). The run-out
   after an all-in gets no category.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.api.import_hands import insert_parsed_hand
from app.hand_value import STREET_CATEGORIES, classify_boards_for_player, classify_for_player
from app.h2n.replay import match_row, replay_parsed
from app.h2n.sequence import TYPE_LETTERS
from app.parsers.ggpoker import parse_hand_history

FIXTURE = Path(__file__).parent / "fixtures" / "ggpoker" / "h2n_parity_r3.txt"


def _hands() -> dict[str, str]:
    out = {}
    for chunk in re.split(r"\n(?=Poker Hand #)", FIXTURE.read_text(encoding="utf-8")):
        chunk = chunk.strip()
        m = re.match(r"Poker Hand #(\w+)", chunk)
        if m:
            out[m.group(1)] = chunk
    return out


HANDS = _hands()
_STREET_NAMES = ("Preflop", "Flop", "Turn", "River")


def _hit(hand_id: str, row: str) -> tuple[str, str]:
    seq = replay_parsed(parse_hand_history(HANDS[hand_id]))
    res = match_row(seq, row, "Hero")
    assert res is not None and res.case and res.hit is not None
    street, idx = res.hit
    a = seq.streets[street][idx]
    assert seq.names[a.actor] == "Hero"
    return _STREET_NAMES[street], TYPE_LETTERS[a.eff]


# ── 1. earliest hit across OR-ed rows ────────────────────────────────────

# hand -> {row: (street, type)} from Hand2Note's reported hit (V01 = VPIP, V02 = PFR)
HITS = {
    # Hero cold-calls an open, then raises all-in over a 3-bet: VPIP = the call
    "RC4221162198": {"V01": ("Preflop", "C"), "V02": ("Preflop", "R")},
    "RC4228053192": {"V01": ("Preflop", "C"), "V02": ("Preflop", "R")},
    # Hero 3-bets first: VPIP = that raise (unchanged)
    "RC4197224934": {"V01": ("Preflop", "R"), "V02": ("Preflop", "R")},
    # Hero calls and never raises preflop
    "RC4197967279": {"V01": ("Preflop", "C")},
}


@pytest.mark.parametrize("hand_id,row", [(h, r) for h in HITS for r in HITS[h]])
def test_hit_is_earliest_matching_action(hand_id, row):
    assert _hit(hand_id, row) == HITS[hand_id][row]


def test_hit_order_independent_of_row_order():
    from app.h2n.matcher import compile_def, evaluate
    seq = replay_parsed(parse_hand_history(HANDS["RC4221162198"]))
    p = seq.index["Hero"]
    a = evaluate(compile_def("pre: H:R | H:C"), seq, p)
    b = evaluate(compile_def("pre: H:C | H:R"), seq, p)
    assert a.case and b.case and a.hit == b.hit
    assert TYPE_LETTERS[seq.streets[0][a.hit[1]].eff] == "C"


def test_opportunity_hit_is_earliest_alternative():
    # Not a case (Hero never folds preflop here): the opportunity's decision
    # is Hero's first action that fits any alternative row (the cold call).
    from app.h2n.matcher import compile_def, evaluate
    seq = replay_parsed(parse_hand_history(HANDS["RC4221162198"]))
    p = seq.index["Hero"]
    # row 1 alone reaches Hero's raise (after the villain's call), row 2
    # alone reaches Hero's cold call; the earlier one wins, in either order.
    for text in ("pre: V:C > H:F | V:R > H:F", "pre: V:R > H:F | V:C > H:F"):
        r = evaluate(compile_def(text), seq, p)
        assert r.opp and not r.case
        assert TYPE_LETTERS[seq.streets[0][r.hit[1]].eff] == "C"
    r = evaluate(compile_def("pre: V:C > H:F"), seq, p)
    assert r.opp and TYPE_LETTERS[seq.streets[0][r.hit[1]].eff] == "R"


# ── 2. BB after a deep all-in ────────────────────────────────────────────

# hand -> (bb, stakes, hero won_bb) from Hand2Note's results
DEEP_ALLIN_BB = {
    "RC4197232820": ("0.05", "$0.02/$0.05", -1.0),
    "RC4198732175": ("0.05", "$0.02/$0.05", -1.0),
    "RC4200966634": ("0.05", "$0.02/$0.05", -0.4),
}


@pytest.mark.parametrize("hand_id", sorted(DEEP_ALLIN_BB))
def test_parser_keeps_agreed_bb_after_deep_all_in(hand_id):
    parsed = parse_hand_history(HANDS[hand_id])
    bb, stakes, _ = DEEP_ALLIN_BB[hand_id]
    assert parsed.bb_amount == Decimal(bb)
    assert parsed.stakes == stakes


@pytest.mark.parametrize("hand_id", sorted(DEEP_ALLIN_BB))
def test_won_bb_after_deep_all_in(db, hand_id):
    insert_parsed_hand(db, parse_hand_history(HANDS[hand_id]))
    won_bb, bb = db.execute(
        "SELECT CAST(hp.won_bb AS DOUBLE), CAST(h.bb_amount AS DOUBLE) "
        "FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "JOIN hands h ON h.id = hp.hand_id WHERE p.username = 'Hero'").fetchone()
    assert bb == pytest.approx(0.05)
    assert won_bb == pytest.approx(DEEP_ALLIN_BB[hand_id][2], abs=1e-6)


# ── 3. hand value only up to the last street with actions ────────────────

def _names(parsed, d: dict) -> dict:
    out = {}
    for street in ("flop", "turn", "river"):
        idx = d[f"hv_{street}"]
        if idx is not None:
            out[street] = "other" if idx == -1 else STREET_CATEGORIES[street][idx].key
    return out


# hand -> categories Hand2Note fills (keys of STREET_CATEGORIES)
HAND_VALUES = {
    "RC4197224934": {},                                        # AK all-in preflop
    "HD2671933728": {},                                        # KK all-in preflop, run twice
    "RC4197967279": {"flop": "two_pairs_plus", "turn": "two_pairs_plus"},  # turn all-in
}


@pytest.mark.parametrize("hand_id", sorted(HAND_VALUES))
def test_hand_value_stops_at_last_street_with_actions(hand_id):
    parsed = parse_hand_history(HANDS[hand_id])
    assert _names(parsed, classify_for_player(parsed, "Hero")) == HAND_VALUES[hand_id]
    for d in classify_boards_for_player(parsed, "Hero"):
        assert _names(parsed, d) == HAND_VALUES[hand_id]
