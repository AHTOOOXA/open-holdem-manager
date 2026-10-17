"""Regressions from parity round 2 against Hand2Note 4.1's results on the same hands.

Fixture: tests/fixtures/ggpoker/h2n_parity_r2.txt, real GG hands where OHM
and H2N disagreed. Expected values are what Hand2Note reported for the hero.

Root cause covered: the big blind behind every "in bb" number. H2N takes the
header BB and lets the regular blind posters override it (never the action
amounts). OHM's GG parser drops an agreed header + posted BB when a preflop
amount is above 500 bb (a deep all-in at NL5), so won_bb / EV bb used the
wrong BB. `money.h2n_main_blind` reproduces H2N's value and feeds the H2N
action sequence; the parser itself was fixed in round 3.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.api.import_hands import insert_parsed_hand
from app.h2n.sequence import build_sequence
from app.money import h2n_main_blind
from app.parsers.ggpoker import parse_hand_history

FIXTURE = Path(__file__).parent / "fixtures" / "ggpoker" / "h2n_parity_r2.txt"


def _hands() -> dict[str, str]:
    out = {}
    for chunk in re.split(r"\n(?=Poker Hand #)", FIXTURE.read_text(encoding="utf-8")):
        chunk = chunk.strip()
        m = re.match(r"Poker Hand #(\w+)", chunk)
        if m:
            out[m.group(1)] = chunk
    return out


HANDS = _hands()

# hand id -> (H2N bb, hero won_bb, hero won_ev_bb), from Hand2Note's results
H2N_EXPECTED = {
    # header and posted BB agree on $0.05; a 705 bb all-in made the parser
    # pick $0.25 (the other two: $0.10)
    "RC4198732175": ("0.05", -1.0, -1.0),
    "RC4197232820": ("0.05", -1.0, -1.0),
    "RC4200966634": ("0.05", -0.4, -0.4),   # hero is the SB
    # corrupted BB post ($2.1 at $0.05/$0.1): H2N trusts the post
    "RC4218503592": ("2.1", 0.0, 0.0),
    # SB posts $0.15, BB $0.2 at $0.05/$0.1: BB = post, then 2x SB
    "RC4275410588": ("0.3", 0.0, 0.0),
}


@pytest.mark.parametrize("hand_id", sorted(H2N_EXPECTED))
def test_main_blind_matches_h2n(hand_id):
    parsed = parse_hand_history(HANDS[hand_id])
    assert h2n_main_blind(parsed) == Decimal(H2N_EXPECTED[hand_id][0])


@pytest.mark.parametrize("hand_id", sorted(H2N_EXPECTED))
def test_sequence_uses_main_blind(hand_id):
    seq = build_sequence(parse_hand_history(HANDS[hand_id]))
    assert seq.bb == pytest.approx(float(H2N_EXPECTED[hand_id][0]))


# The bb money columns divide by the parser's bb_amount (other views turn
# them back into dollars with hands.bb_amount). For the three deep all-in
# hands the GG parser used to drop the agreed header + posted BB; fixed in
# parity round 3 (see test_h2n_parity_r3.py).
@pytest.mark.parametrize("hand_id", sorted(H2N_EXPECTED))
def test_won_bb_uses_main_blind(db, hand_id):
    insert_parsed_hand(db, parse_hand_history(HANDS[hand_id]))
    won_bb, ev_bb = db.execute(
        "SELECT CAST(hp.won_bb AS DOUBLE), CAST(hp.all_in_ev_bb AS DOUBLE) "
        "FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE p.username = 'Hero'").fetchone()
    _, exp_won, exp_ev = H2N_EXPECTED[hand_id]
    assert won_bb == pytest.approx(exp_won, abs=1e-6)
    assert (ev_bb if ev_bb is not None else won_bb) == pytest.approx(exp_ev, abs=1e-6)


def test_blind_posted_all_in_does_not_override():
    # Both blind posters all-in by posting: the header BB stays.
    text = (HANDS["RC4275410588"]
            .replace("Seat 2: c441a5bf ($9.82 in chips)", "Seat 2: c441a5bf ($0.15 in chips)")
            .replace("Seat 3: 843fe12e ($16.56 in chips)", "Seat 3: 843fe12e ($0.2 in chips)"))
    assert h2n_main_blind(parse_hand_history(text)) == Decimal("0.1")


def test_sb_post_alone_doubles_into_bb():
    # BB post matches the header, SB post is above half of it: BB = 2x SB.
    text = HANDS["RC4275410588"].replace("843fe12e: posts big blind $0.2",
                                         "843fe12e: posts big blind $0.1")
    assert h2n_main_blind(parse_hand_history(text)) == Decimal("0.3")


def test_other_rooms_keep_parser_bb():
    from app.parsers import pokerstars
    path = Path(__file__).parent / "fixtures" / "pokerstars" / "basic_hand.txt"
    for hand in pokerstars.split_hands(path.read_text(errors="replace")):
        parsed = pokerstars.parse_hand_history(hand)
        assert h2n_main_blind(parsed) == parsed.bb_amount


@pytest.mark.parametrize("hand_id", sorted(H2N_EXPECTED))
def test_bb_columns_convert_back_to_dollars(db, hand_id):
    # Hands list / graph / sessions compute dollars as won_bb * hands.bb_amount.
    insert_parsed_hand(db, parse_hand_history(HANDS[hand_id]))
    rows = db.execute(
        "SELECT CAST(hp.won AS DOUBLE), CAST(hp.won_bb AS DOUBLE) * h.bb_amount "
        "FROM hand_players hp JOIN hands h ON h.id = hp.hand_id").fetchall()
    for won, back in rows:
        assert back == pytest.approx(won, abs=0.005)
