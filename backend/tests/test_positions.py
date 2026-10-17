"""Position labels and action order across table sizes (BUGS-FROM-FORK.md #10).

Labels follow Hand2Note's column groups: MP is exactly one seat (the HJ),
every earlier seat is EP, and heads-up the button is SB, the other seat BB.
"""

import pytest

from app.parsers.common import POSITIONS_BY_COUNT, _assign_positions, position_labels
from app.parsers.ggpoker import parse_hand_history
from app.stat_flags import compute_stat_flags

BUCKETS = {"BTN", "SB", "BB", "EP", "MP", "CO"}


@pytest.mark.parametrize("n, expected", [
    (2, ["SB", "BB"]),
    (3, ["BTN", "SB", "BB"]),
    (4, ["BTN", "SB", "BB", "CO"]),
    (5, ["BTN", "SB", "BB", "MP", "CO"]),
    (6, ["BTN", "SB", "BB", "EP", "MP", "CO"]),
    (7, ["BTN", "SB", "BB", "EP", "EP", "MP", "CO"]),
    (8, ["BTN", "SB", "BB", "EP", "EP", "EP", "MP", "CO"]),
    (9, ["BTN", "SB", "BB", "EP", "EP", "EP", "EP", "MP", "CO"]),
    (10, ["BTN", "SB", "BB", "EP", "EP", "EP", "EP", "EP", "MP", "CO"]),
])
def test_labels(n, expected):
    assert position_labels(n) == expected


def test_every_table_size_uses_only_the_six_buckets():
    """Stats, filters and the UI group by these six; anything else (UTG, HJ...)
    used to drop out of every positional breakdown."""
    for n in range(2, 13):
        assert set(position_labels(n)) <= BUCKETS
        assert len(position_labels(n)) == n
    assert POSITIONS_BY_COUNT[6] == position_labels(6)


def test_first_to_act_is_ep_at_every_full_table():
    for n in range(6, 11):
        labels = position_labels(n)
        assert labels[3] == "EP"  # first seat after BB


@pytest.mark.parametrize("n", range(5, 13))
def test_mp_is_exactly_one_seat_right_before_co(n):
    labels = position_labels(n)
    assert labels.count("MP") == 1
    assert labels.count("CO") == 1
    assert labels[-2:] == ["MP", "CO"]


@pytest.mark.parametrize("n", range(3, 13))
def test_one_button_and_one_of_each_blind(n):
    labels = position_labels(n)
    assert labels[:3] == ["BTN", "SB", "BB"]
    assert labels.count("BTN") == labels.count("SB") == labels.count("BB") == 1


def test_heads_up_has_no_button_label():
    """H2N's SB-HU (the button) and BB-HU count in its SB and BB groups."""
    assert position_labels(2) == ["SB", "BB"]
    seats = [{"seat": 2}, {"seat": 5}]
    _assign_positions(seats, button_seat=5, table_size=6)
    assert {s["seat"]: s["position"] for s in seats} == {5: "SB", 2: "BB"}


@pytest.mark.parametrize("n", range(2, 11))
def test_action_order_is_postflop_order(n):
    # Button in seat 3, seats numbered 1..n
    seats = [{"seat": i} for i in range(1, n + 1)]
    _assign_positions(seats, button_seat=3, table_size=n)
    by_order = sorted(seats, key=lambda s: s["action_order"])
    assert sorted(s["action_order"] for s in seats) == list(range(n))
    # Heads-up seat 3 is empty, so the seat before it (2) acts as the button
    button = next(s for s in seats if s["seat"] == min(3, n))
    assert by_order[-1] is button  # the button always acts last postflop
    if n == 2:
        assert [s["position"] for s in by_order] == ["BB", "SB"]
    else:
        assert button["position"] == "BTN"
        assert [s["position"] for s in by_order[:2]] == ["SB", "BB"]


NINE_MAX_HAND = """Poker Hand #HD9900008888: Hold'em No Limit ($0.05/$0.1) - 2026/03/10 18:00:00
Table 'NLHGold9' 9-max Seat #1 is the button
Seat 1: P1 ($10 in chips)
Seat 2: P2 ($10 in chips)
Seat 3: P3 ($10 in chips)
Seat 4: P4 ($10 in chips)
Seat 5: P5 ($10 in chips)
Seat 6: P6 ($10 in chips)
Seat 7: P7 ($10 in chips)
Seat 8: P8 ($10 in chips)
Seat 9: Hero ($10 in chips)
P2: posts small blind $0.05
P3: posts big blind $0.1
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
P4: raises $0.2 to $0.3
P5: calls $0.3
P6: folds
P7: folds
P8: folds
Hero: folds
P1: folds
P2: folds
P3: folds
*** FLOP *** [Kd 7s 2c]
P4: checks
P5: bets $0.4
P4: folds
Uncalled bet ($0.4) returned to P5
*** SHOWDOWN ***
P5 collected $0.72 from pot
*** SUMMARY ***
Total pot $0.75 | Rake $0.03 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Board [Kd 7s 2c]
Seat 1: P1 (button) folded before Flop (didn't bet)
Seat 2: P2 (small blind) folded before Flop
Seat 3: P3 (big blind) folded before Flop
Seat 4: P4 folded on the Flop
Seat 5: P5 collected ($0.72)
Seat 6: P6 folded before Flop (didn't bet)
Seat 7: P7 folded before Flop (didn't bet)
Seat 8: P8 folded before Flop (didn't bet)
Seat 9: Hero folded before Flop (didn't bet)"""


def test_nine_max_positions_and_postflop_ip():
    parsed = parse_hand_history(NINE_MAX_HAND)
    pos = {s["username"]: s["position"] for s in parsed.seats}
    assert pos == {
        "P1": "BTN", "P2": "SB", "P3": "BB",
        "P4": "EP", "P5": "EP", "P6": "EP", "P7": "EP",
        "P8": "MP", "Hero": "CO",
    }
    flags = compute_stat_flags(parsed)
    # Both flop players are labelled EP; P5 acts after P4, so P5 is in position.
    # With label-based order they tied and both counted as IP.
    assert flags["P5"]["postflop_ip"] is True
    assert flags["P4"]["postflop_ip"] is False
    # P5 cold-called P4's open from a later seat: in position for the 3-bet opp
    assert flags["P5"]["three_bet_opp_ip"] is True


SEVEN_MAX_HAND = """Poker Hand #HD9900008889: Hold'em No Limit ($0.05/$0.1) - 2026/03/10 18:05:00
Table 'NLHGold7' 7-max Seat #3 is the button
Seat 1: P1 ($10 in chips)
Seat 2: P2 ($10 in chips)
Seat 3: P3 ($10 in chips)
Seat 4: P4 ($10 in chips)
Seat 5: P5 ($10 in chips)
Seat 6: P6 ($10 in chips)
Seat 7: Hero ($10 in chips)
P4: posts small blind $0.05
P5: posts big blind $0.1
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
P6: folds
Hero: folds
P1: raises $0.2 to $0.3
P2: folds
P3: folds
P4: folds
P5: folds
Uncalled bet ($0.2) returned to P1
*** SHOWDOWN ***
P1 collected $0.25 from pot
*** SUMMARY ***
Total pot $0.25 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 1: P1 collected ($0.25)
Seat 2: P2 (button) folded before Flop (didn't bet)
Seat 3: P3 (button) folded before Flop (didn't bet)
Seat 4: P4 (small blind) folded before Flop
Seat 5: P5 (big blind) folded before Flop
Seat 6: P6 folded before Flop (didn't bet)
Seat 7: Hero folded before Flop (didn't bet)"""


def test_seven_max_lj_is_ep_and_hj_is_mp():
    parsed = parse_hand_history(SEVEN_MAX_HAND)
    pos = {s["username"]: s["position"] for s in parsed.seats}
    assert pos == {
        "P3": "BTN", "P4": "SB", "P5": "BB",
        "P6": "EP", "Hero": "EP", "P1": "MP", "P2": "CO",
    }


HEADS_UP_HAND = """Poker Hand #HD9900008890: Hold'em No Limit ($0.05/$0.1) - 2026/03/10 18:10:00
Table 'NLHGold6' 6-max Seat #4 is the button
Seat 1: Villain ($10 in chips)
Seat 4: Hero ($10 in chips)
Hero: posts small blind $0.05
Villain: posts big blind $0.1
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
Hero: raises $0.15 to $0.25
Villain: folds
Uncalled bet ($0.15) returned to Hero
*** SHOWDOWN ***
Hero collected $0.2 from pot
*** SUMMARY ***
Total pot $0.2 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 1: Villain (big blind) folded before Flop
Seat 4: Hero (small blind) collected ($0.2)"""


def test_heads_up_button_steal_lands_in_sb():
    """H2N-COMPATIBLE-STATS.md section 8 example 4: the HU button's open counts as an SB steal."""
    parsed = parse_hand_history(HEADS_UP_HAND)
    pos = {s["username"]: s["position"] for s in parsed.seats}
    assert pos == {"Hero": "SB", "Villain": "BB"}
    flags = compute_stat_flags(parsed)
    assert flags["Hero"]["steal_opp"] is True
    assert flags["Hero"]["steal_attempted"] is True
    assert flags["Villain"]["faced_steal"] is True
    # The stealer posted the small blind himself; he never faces his own steal
    # (as a "BTN" he used to be marked faced_steal through the SB-defence path).
    assert not flags["Hero"].get("faced_steal")
