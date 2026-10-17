"""Parity round 4 against Hand2Note 4.1's results on the same hands.

Round 4 compared all 75,849 hands of the reference database: every General
cell, money (won / rake / won_bb) and the hand value categories match. The
only differences left are the all-in EV of 3-way preflop all-ins, where H2N
uses a 20,000-board Monte Carlo that gives a different number on every run
(docs/specs/H2N-COMPATIBLE-STATS.md 7.6).

Fixture: tests/fixtures/ggpoker/h2n_parity_r4.txt, the six hands whose EV
moved across the 0.01 tolerance between Hand2Note runs.

Expected EV = the mean of 20 Hand2Note runs; ``sd`` = the spread of a single
Hand2Note run. The exact equity (full enumeration of all boards) lands within
about 2 standard errors of that mean on every hand, so H2N's Monte Carlo is
unbiased and OHM only has to stay inside H2N's own run-to-run spread.
Winnings and stored rake are deterministic and must match to the cent.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.money import compute_hand_money, stored_rake
from app.parsers.ggpoker import parse_hand_history

FIXTURE = Path(__file__).parent / "fixtures" / "ggpoker" / "h2n_parity_r4.txt"


def _hands() -> dict[str, str]:
    out = {}
    for chunk in re.split(r"\n(?=Poker Hand #)", FIXTURE.read_text(encoding="utf-8")):
        chunk = chunk.strip()
        m = re.match(r"Poker Hand #(\w+)", chunk)
        if m:
            out[m.group(1)] = chunk
    return out


HANDS = _hands()

# hand id: (hero won, hero stored rake, H2N mean won_ev over 20 runs, single-run sd)
H2N_EXPECTED = {
    "RC4197224934": ("-5.30", 0.0, -1.3745, 0.0416),
    "HD2672015959": ("11.31", 0.54, 2.9920, 0.0431),
    "HD2671901254": ("-5.19", 0.0, -3.4615, 0.0070),
    "RC4221185480": ("-10.01", 0.01, -4.9209, 0.0832),
    "RC4221162198": ("-0.22", 0.13, 2.3342, 0.0513),
    "RC4226757313": ("-10.30", 0.0, -4.4846, 0.0737),
}


def test_fixture_has_every_hand():
    assert set(HANDS) == set(H2N_EXPECTED)


@pytest.mark.parametrize("hand_id", sorted(H2N_EXPECTED))
def test_three_way_preflop_allin_money(hand_id):
    won, rake, ev_mean, sd = H2N_EXPECTED[hand_id]
    hm = compute_hand_money(parse_hand_history(HANDS[hand_id]))
    assert hm.ev_state == "done"
    hero = hm.players["Hero"]
    assert hero.won == Decimal(won)
    assert stored_rake(hero.rake) == rake
    assert hero.ev_results > 0
    # inside H2N's own Monte Carlo spread (3 single-run sd, at least 2 cents)
    assert hero.won_ev == pytest.approx(ev_mean, abs=max(3 * sd, 0.02))
