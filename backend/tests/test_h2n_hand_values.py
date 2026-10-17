"""hv_* columns: apply_h2n calls the hand-value classifier, import writes them."""

from pathlib import Path

import app.h2n as h2n
from app.api.import_hands import insert_parsed_hand
from app.hand_value import OTHER, STREET_CATEGORIES
from app.parsers.ggpoker import parse_hand_history
from app.stat_flags import compute_stat_flags

FIXTURES = Path(__file__).parent / "fixtures" / "ggpoker"

# Hero (BB) calls a BTN open with QQ, calls a flop bet, folds to a turn bet.
TURN_FOLD = """Poker Hand #RC9900007777: Hold'em No Limit ($0.05/$0.10) - 2026/01/21 10:00:00
Table 'RushAndCash9900007' 6-max Seat #1 is the button
Seat 1: Villain ($10.00 in chips)
Seat 2: Player2 ($10.00 in chips)
Seat 3: Hero ($10.00 in chips)
Seat 4: Player4 ($10.00 in chips)
Seat 5: Player5 ($10.00 in chips)
Seat 6: Player6 ($10.00 in chips)
Player2: posts small blind $0.05
Hero: posts big blind $0.10
*** HOLE CARDS ***
Dealt to Hero [Qh Qs]
Player4: folds
Player5: folds
Player6: folds
Villain: raises $0.15 to $0.25
Player2: folds
Hero: calls $0.15
*** FLOP *** [7c 4d 2s]
Hero: checks
Villain: bets $0.30
Hero: calls $0.30
*** TURN *** [7c 4d 2s] [9h]
Hero: checks
Villain: bets $0.80
Hero: folds
Uncalled bet ($0.80) returned to Villain
*** SHOWDOWN ***
Villain collected $1.08 from pot
*** SUMMARY ***
Total pot $1.15 | Rake $0.05 | Jackpot $0.02 | Bingo $0 | Fortune $0 | Tax $0
Board [7c 4d 2s 9h]
Seat 1: Villain (button) won ($1.08)
Seat 2: Player2 (small blind) folded before Flop
Seat 3: Hero (big blind) folded on the Turn
Seat 4: Player4 folded before Flop (didn't bet)
Seat 5: Player5 folded before Flop (didn't bet)
Seat 6: Player6 folded before Flop (didn't bet)
"""

NONE = (None, None, None)


def _idx(street: str, label: str) -> int:
    if label == "Other":
        return OTHER
    return [c.label for c in STREET_CATEGORIES[street]].index(label)


def _hv_rows(db, hand_id: int) -> dict[str, tuple]:
    rows = db.execute(
        "SELECT p.username, hv_flop, hv_turn, hv_river FROM hand_players hp "
        "JOIN players p ON p.id = hp.player_id WHERE hp.hand_id = ?",
        [hand_id],
    ).fetchall()
    return {name: tuple(hv) for name, *hv in rows}


def _split_pot_hand() -> str:
    return (FIXTURES / "split_pot.txt").read_text(encoding="utf-8").split("\n\n\n")[0]


def test_import_writes_hv_for_turn_fold(db):
    hand_id = insert_parsed_hand(db, parse_hand_history(TURN_FOLD))
    hv = _hv_rows(db, hand_id)
    # QQ on 7c 4d 2s / 9h: overpair on both streets; river never dealt.
    assert hv["Hero"] == (_idx("flop", "Overpair"), _idx("turn", "Overpair"), None)
    # Villain's cards were never shown; everyone else folded preflop.
    for name in ("Villain", "Player2", "Player4", "Player5", "Player6"):
        assert hv[name] == NONE, name


def test_import_writes_hv_for_showdown_players(db):
    hand_id = insert_parsed_hand(db, parse_hand_history(_split_pot_hand()))
    hv = _hv_rows(db, hand_id)
    two_pair = (_idx("flop", "Two Pairs+"), _idx("turn", "Two Pairs+"),
                _idx("river", "Two Pairs+"))
    assert hv["Hero"] == two_pair      # AhKd on Ac Kc 9h 2d 5s
    assert hv["Player1"] == two_pair   # AdKs, shown at showdown
    assert hv["Player3"] == NONE       # folded preflop, cards unknown


def test_hv_filled_when_matcher_fails(monkeypatch):
    def boom(parsed, use_cache=True):
        raise RuntimeError("matcher failure")

    monkeypatch.setattr(h2n, "compute_h2n", boom)
    flags = compute_stat_flags(parse_hand_history(TURN_FOLD))
    assert flags["Hero"]["h2n_pos"] == h2n.H2N_DEFAULTS["h2n_pos"]  # matcher defaults
    assert flags["Hero"]["hv_flop"] == _idx("flop", "Overpair")
    assert flags["Hero"]["hv_turn"] == _idx("turn", "Overpair")


def test_matcher_columns_kept_when_hand_values_fail(monkeypatch):
    def boom(parsed, player_stats):
        for ps in player_stats.values():
            ps["hv_flop"] = 99  # partial write before failing
        raise RuntimeError("classifier failure")

    monkeypatch.setattr(h2n, "apply_hand_values", boom)
    flags = compute_stat_flags(parse_hand_history(TURN_FOLD))
    assert flags["Hero"]["h2n_pos"] == "BB"
    assert flags["Villain"]["h2n_pos"] == "BTN"
    for ps in flags.values():
        assert (ps["hv_flop"], ps["hv_turn"], ps["hv_river"]) == NONE
