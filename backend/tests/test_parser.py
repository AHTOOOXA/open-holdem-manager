"""Tests for GGPoker hand history parser edge cases."""

import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.ggpoker import parse_hand_history
from app.api.import_hands import insert_parsed_hand, reset_import_cache
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "ggpoker"


def _get_hero_won(db, hand_id: str) -> float:
    """Get Hero's net won amount for a hand."""
    row = db.execute(
        """SELECT hp.won FROM hand_players hp
           JOIN players p ON hp.player_id = p.id
           WHERE hp.hand_id = ? AND p.username = 'Hero'""",
        [hand_id],
    ).fetchone()
    return float(row[0]) if row else None


def _get_player_won(db, hand_id: str, username: str) -> float:
    """Get a player's net won amount for a hand."""
    row = db.execute(
        """SELECT hp.won FROM hand_players hp
           JOIN players p ON hp.player_id = p.id
           WHERE hp.hand_id = ? AND p.username = ?""",
        [hand_id, username],
    ).fetchone()
    return float(row[0]) if row else None


def _get_board_cards(db, hand_id: str, board_number: int = 1) -> dict:
    """Get board cards grouped by street for a specific board number."""
    rows = db.execute(
        "SELECT street, card FROM board_cards WHERE hand_id = ? AND board_number = ? ORDER BY street, card_order",
        [hand_id, board_number],
    ).fetchall()
    result = {"flop": [], "turn": [], "river": []}
    for street, card in rows:
        result[street].append(card)
    return result


def _get_player_stats(db, hand_id: str, username: str) -> dict:
    """Get all stat columns for a player in a hand."""
    row = db.execute(
        """SELECT hp.* FROM hand_players hp
           JOIN players p ON hp.player_id = p.id
           WHERE hp.hand_id = ? AND p.username = ?""",
        [hand_id, username],
    ).fetchone()
    if not row:
        return None
    cols = [desc[0] for desc in db.description]
    return dict(zip(cols, row))


class TestRegularHand:
    """Test parsing of a standard hand (baseline)."""

    def test_basic_hand(self, db):
        text = (FIXTURES / "sample.txt").read_text()
        # Parse just the first hand
        first_hand = text.split("\n\n\n")[0]
        parsed = parse_hand_history(first_hand)
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "HD1234567890"
        hero_won = _get_hero_won(db, hand_id)
        # Hero invested: 3.75 (raise). Collected 12.50 + uncalled 7.50 returned.
        # net = 12.50 + 7.50 - (3.75) = 16.25 - wait, need to trace more carefully.
        # Hero raises to 3.75, bets 2.50 on flop, bets 7.50 on turn (returned).
        # Invested: 3.75 + 2.50 = 6.25 (turn bet was uncalled, returned)
        # Collected: 12.50, Uncalled: 7.50
        # Net = 12.50 + 7.50 - 6.25 = 13.75 ... hmm let me think.
        # Actually: raise to 3.75 (invested 3.75), bet 2.50 (invested 6.25),
        # bet 7.50 (invested 13.75), uncalled 7.50 returned.
        # Net = 12.50 + 7.50 - 13.75 = 6.25
        assert hero_won == pytest.approx(6.25, abs=0.01)

    def test_showdown_hand(self, db):
        text = (FIXTURES / "sample.txt").read_text()
        # Fifth hand has a showdown
        hands = [h.strip() for h in text.split("\n\n\n") if h.strip()]
        parsed = parse_hand_history(hands[4])
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "HD1234567894"
        # Hero folded preflop, net = 0
        hero_won = _get_hero_won(db, hand_id)
        assert hero_won == pytest.approx(0.0, abs=0.01)

        # Player5 won $11.00, invested: bb $0.50 + call $0.75 + call $1.50 + bet $3.00 = $5.75
        p5_won = _get_player_won(db, hand_id, "Player5")
        assert p5_won == pytest.approx(11.00 - 5.75, abs=0.01)


class TestTimeBankCard:
    """Test parsing of hands with time bank card rewards in summary."""

    def test_time_bank_card_hero_wins(self, db):
        text = (FIXTURES / "time_bank_card.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "RC9900001111"

        # Hero invested: raise to 0.25 (preflop) + bet 0.30 (flop) = 0.55
        # Uncalled: 0.30 returned, Collected: 0.53
        # Net = 0.53 + 0.30 - 0.55 = 0.28
        hero_won = _get_hero_won(db, hand_id)
        assert hero_won == pytest.approx(0.28, abs=0.01)

        # The $0.02 time bank card should NOT be counted as winnings
        stats = _get_player_stats(db, hand_id, "Hero")
        assert stats is not None
        assert stats["position"] == "BTN"

    def test_time_bank_card_username_extraction(self, db):
        """Ensure the username is extracted correctly despite 'received' text."""
        text = (FIXTURES / "time_bank_card.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        # Verify Hero is found as a player (not "Hero (button) received...")
        row = db.execute(
            "SELECT username FROM players WHERE username = 'Hero'"
        ).fetchone()
        assert row is not None


class TestSplitPot:
    """Test parsing of split pot hands."""

    def test_split_pot_two_winners(self, db):
        text = (FIXTURES / "split_pot.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "RC9900002222"

        # Hero invested: sb 0.05 + raise to 0.80 + bet 0.80 + bet 1.60 = 3.20
        # Wait, raise to 0.80: already in 0.05 (sb), so increment = 0.80 - 0.05 = 0.75
        # preflop: sb=0.05, raise to 0.80 (already in 0.05, increment=0.75). Street total: 0.80
        # flop: bet 0.80. Street total: 0.80
        # turn: bet 1.60. Street total: 1.60
        # Total invested: 0.80 + 0.80 + 1.60 = 3.20
        # Collected: 3.07
        # Net = 3.07 - 3.20 = -0.13
        hero_won = _get_hero_won(db, hand_id)
        assert hero_won == pytest.approx(-0.13, abs=0.01)

        # Player1 invested: call 0.25, call 0.55 (raise to 0.80 by hero, called 0.55 more)
        # Wait, Player1 raises to 0.25, then Hero 3bets to 0.80, Player1 calls 0.55 more.
        # preflop: raise to 0.25, call 0.55 -> street total 0.80
        # Wait no: Player1 raises $0.25 to $0.25 (open raise), Hero raises $0.80 to $0.80.
        # Player1 calls $0.55.
        # Player1 preflop: raise to 0.25 (invested 0.25), call 0.55 (invested 0.80)
        # But wait, raise "to" means the total is 0.25. Then call 0.55 means total is 0.80.
        # preflop street_put_in for raise: 0.25. Then call 0.55: 0.25 + 0.55 = 0.80.
        # flop: call 0.80. turn: call 1.60.
        # Total invested: 0.80 + 0.80 + 1.60 = 3.20
        # Collected: 3.08
        # Net = 3.08 - 3.20 = -0.12
        p1_won = _get_player_won(db, hand_id, "Player1")
        assert p1_won == pytest.approx(-0.12, abs=0.01)

        # Verify showdown stats
        hero_stats = _get_player_stats(db, hand_id, "Hero")
        assert hero_stats["went_to_showdown"] is True
        assert hero_stats["won_at_showdown"] is True

        p1_stats = _get_player_stats(db, hand_id, "Player1")
        assert p1_stats["went_to_showdown"] is True
        assert p1_stats["won_at_showdown"] is True


class TestRunItTwice:
    """Test parsing of Run It Twice hands."""

    def test_rit_different_winners(self, db):
        """Each player wins one board."""
        text = (FIXTURES / "run_it_twice.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "RC9900003333"

        # Hero invested: raise to 1.25, then raise to 12.00, then call 28.00
        # preflop: raise to 1.25 (invested 1.25), raise to 12.00 (increment 10.75),
        # call 28.00 (invested 40.00 + 0.25 from earlier? No...)
        # Wait: Hero raises $1.25 to $1.25, Player4 raises $4.00 to $4.00,
        # Hero raises $12.00 to $12.00, Player4 raises $40.00 to $40.00 all-in,
        # Hero calls $28.00.
        # Hero's preflop: raise to 1.25 (street=1.25), raise to 12.00 (street=12.00),
        # call 28.00 (street=12.00+28.00=40.00)
        # Total invested: 40.00
        # Collected: 40.12 (from summary won)
        # Net = 40.12 - 40.00 = 0.12
        hero_won = _get_hero_won(db, hand_id)
        assert hero_won == pytest.approx(0.12, abs=0.01)

        # Player4 invested: bb 0.50, raise to 4.00 (street=4.00),
        # raise to 40.00 all-in (street=40.00)
        # Total invested: 40.00
        # Collected: 40.13
        # Net = 40.13 - 40.00 = 0.13
        p4_won = _get_player_won(db, hand_id, "Player4")
        assert p4_won == pytest.approx(0.13, abs=0.01)

    def test_rit_board_cards_from_first_board(self, db):
        """Board cards should come from the first board."""
        text = (FIXTURES / "run_it_twice.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        board = _get_board_cards(db, hand_id)
        assert board["flop"] == ["Qh", "9d", "3c"]
        assert board["turn"] == ["7s"]
        assert board["river"] == ["2h"]

    def test_rit_same_winner_both_boards(self, db):
        """One player wins both boards — two won amounts on one summary line."""
        text = (FIXTURES / "run_it_twice_same_winner.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        assert hand_id == "RC9900004444"

        # Hero invested: raise to 1.25, raise to 12.00 (increment 10.75) = 12.00
        # Player6 invested: bb 0.50, raise to 4.00 (street=4.00),
        # call $8.00 all-in -> but wait, "calls $8.00 and is all-in"
        # Player6: bb 0.50, raise to 4.00 (street=4.00), call 8.00 (street=4.00+8.00=12.00)
        # Hero: raise to 1.25 (street=1.25), raise to 12.00 (street=12.00)
        # Hero total invested: 12.00
        # Collected: 24.62 + 24.63 = 49.25
        # But uncalled bet... Hero had 12.00 in, Player6 had 12.00 in (10.00 all-in... wait)
        # Player6 has $50.00 stack. bb $0.50, raise to $4.00, call $8.00 all-in.
        # Player6 total: 0.50 + 3.50 + 8.00 = 12.00. OK so both invested 12.00.
        # Wait but there's also the SB ($0.25 from Player5). So pot = 12.00 + 12.00 + 0.25 = 24.25
        # Rake $1.50, so after rake pot = 24.25 - 1.50 - 0.25 (jackpot) = 22.50... hmm no.
        # Total pot $49.25 means that's the gross pot before rake.
        # Hero collected: 24.62 + 24.63 = 49.25
        # Net = 49.25 - 12.00 = 37.25
        hero_won = _get_hero_won(db, hand_id)
        assert hero_won == pytest.approx(49.25 - 12.00, abs=0.01)

        # Player6 lost everything invested: net = 0 + 0 - 12.00 = -12.00
        p6_won = _get_player_won(db, hand_id, "Player6")
        assert p6_won == pytest.approx(-12.00, abs=0.01)

    def test_rit_board_cards_same_winner(self, db):
        """Board cards from first board even when same winner."""
        text = (FIXTURES / "run_it_twice_same_winner.txt").read_text()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        board = _get_board_cards(db, hand_id)
        assert board["flop"] == ["Kh", "9d", "3c"]
        assert board["turn"] == ["7s"]
        assert board["river"] == ["2h"]

    def test_rit_second_board_lines_parsed(self, db):
        """SECOND board lines should be parsed into extra_boards."""
        text = (FIXTURES / "run_it_twice.txt").read_text()
        parsed = parse_hand_history(text)

        # Parser detects RIT
        assert parsed.rit_boards == 2
        assert len(parsed.extra_boards) == 1
        assert parsed.extra_boards[0]["flop"] == ["Jh", "8c", "4d"]
        assert parsed.extra_boards[0]["turn"] == ["Ts"]
        assert parsed.extra_boards[0]["river"] == ["Ah"]
        assert parsed.is_cashout is False

        hand_id = insert_parsed_hand(db, parsed)

        # DB has board_number=2 rows
        board2_rows = db.execute(
            "SELECT street, card FROM board_cards WHERE hand_id = ? AND board_number = 2 ORDER BY card_order",
            [hand_id],
        ).fetchall()
        assert len(board2_rows) == 5
        assert [r[1] for r in board2_rows if r[0] == "flop"] == ["Jh", "8c", "4d"]
        assert [r[1] for r in board2_rows if r[0] == "turn"] == ["Ts"]
        assert [r[1] for r in board2_rows if r[0] == "river"] == ["Ah"]

        # hands table has rit_boards=2
        row = db.execute(
            "SELECT rit_boards, is_cashout FROM hands WHERE id = ?", [hand_id]
        ).fetchone()
        assert row[0] == 2
        assert row[1] is False


class TestEVCashout:
    """Test parsing of EV Cashout hands."""

    CASHOUT_HAND = """\
Poker Hand #RC9900009999: Hold'em No Limit ($0.25/$0.50) - 2026/01/25 12:00:00
Table 'RushAndCash9900009' 6-max Seat #1 is the button
Seat 1: Hero ($50.00 in chips)
Seat 2: Player2 ($48.00 in chips)
Seat 3: Player3 ($52.00 in chips)
Seat 4: Player4 ($50.00 in chips)
Seat 5: Player5 ($50.00 in chips)
Seat 6: Player6 ($50.00 in chips)
Player2: posts small blind $0.25
Player3: posts big blind $0.50
*** HOLE CARDS ***
Dealt to Hero [As Kd]
Player4: folds
Player5: folds
Player6: folds
Hero: raises $1.25 to $1.25
Player2: folds
Player3: calls $0.75
*** FLOP *** [Qs 8d 3h]
Player3: checks
Hero: bets $1.50
Player3: calls $1.50
*** TURN *** [Qs 8d 3h] [Ah]
Player3: checks
Hero: bets $3.00
Player3: raises $10.00 to $10.00 and is all-in
Hero: calls $7.00
Hero Chooses to EV Cashout
Hero Receives Cashout of $25.50
*** RIVER *** [Qs 8d 3h Ah] [2c]
*** SHOWDOWN ***
Player3: shows [Qh Qd]
*** SUMMARY ***
Total pot $25.50 | Rake $1.25 | Jackpot $0.25 | Bingo $0 | Fortune $0 | Tax $0
Board [Qs 8d 3h Ah 2c]
Seat 1: Hero (button) showed [As Kd] and won ($25.50) with a pair of Aces
Seat 2: Player2 (small blind) folded before Flop
Seat 3: Player3 (big blind) showed [Qh Qd] and lost
Seat 4: Player4 folded before Flop (didn't bet)
Seat 5: Player5 folded before Flop (didn't bet)
Seat 6: Player6 folded before Flop (didn't bet)
"""

    def test_cashout_detected(self, db):
        """is_cashout=True when hand has EV Cashout lines."""
        parsed = parse_hand_history(self.CASHOUT_HAND)
        assert parsed.is_cashout is True
        assert parsed.rit_boards == 1
        assert parsed.extra_boards == []

        hand_id = insert_parsed_hand(db, parsed)

        row = db.execute(
            "SELECT rit_boards, is_cashout FROM hands WHERE id = ?", [hand_id]
        ).fetchone()
        assert row[0] == 1
        assert row[1] is True

    def test_cashout_financials(self, db):
        """Cashout hand financials are correct."""
        parsed = parse_hand_history(self.CASHOUT_HAND)
        hand_id = insert_parsed_hand(db, parsed)

        hero_won = _get_hero_won(db, hand_id)
        # Hero invested: raise to 1.25 + bet 1.50 + call 7.00 = already in street
        # preflop: raise to 1.25 (invested 1.25)
        # flop: bet 1.50 (invested 2.75)
        # turn: bet 3.00, call 7.00 → raise 10.00 by P3, hero calls 7.00 (total turn 10.00)
        # Total invested: 1.25 + 1.50 + 10.00 = 12.75
        # Collected: 25.50
        # Net = 25.50 - 12.75 = 12.75
        assert hero_won == pytest.approx(12.75, abs=0.01)


class TestCorruptedStakes:
    """Test BB detection with byte-corrupted hand histories."""

    # Template: 6-max NL2 Rush & Cash hand. Placeholders for header stakes,
    # posted blinds, and preflop action.
    _TEMPLATE = """\
Poker Hand #RC9900100001: Hold'em No Limit ({header}) - 2026/01/15 10:00:00
Table 'RushAndCash99001' 6-max Seat #1 is the button
Seat 1: Player1 ($2.50 in chips)
Seat 2: Player2 ($2.00 in chips)
Seat 3: Player3 ($2.30 in chips)
Seat 4: Hero ($2.10 in chips)
Seat 5: Player5 ($3.00 in chips)
Seat 6: Player6 ($2.00 in chips)
Player2: posts small blind ${sb}
Player3: posts big blind ${bb}
*** HOLE CARDS ***
Dealt to Hero [Ah Jc]
{preflop}*** SHOWDOWN ***
Hero collected $0.05 from pot
*** SUMMARY ***
Total pot $0.05 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 4: Hero collected ($0.05)
"""

    def _make_hand(self, header="$0.01/$0.02", sb="0.01", bb="0.02",
                   preflop="Hero: raises $0.03 to $0.05\nPlayer5: folds\nPlayer6: folds\nPlayer1: folds\nPlayer2: folds\nPlayer3: folds\nUncalled bet ($0.03) returned to Hero\n"):
        return self._TEMPLATE.format(header=header, sb=sb, bb=bb, preflop=preflop)

    def test_clean_nl2(self):
        """Baseline: no corruption, NL2 detected correctly."""
        p = parse_hand_history(self._make_hand())
        assert p.bb_amount == Decimal("0.02")
        assert p.stakes == "$0.01/$0.02"

    def test_header_bb_corrupted_to_052(self):
        """Header $0.52 instead of $0.02 — actions resolve to NL2."""
        p = parse_hand_history(self._make_hand(header="$0.01/$0.52", bb="0.52"))
        assert p.bb_amount == Decimal("0.02")

    def test_header_bb_dot_dropped_002(self):
        """Header $002 (dot dropped) = $2.00 — posted BB $0.02 is correct."""
        p = parse_hand_history(self._make_hand(header="$0.01/$002", bb="0.02"))
        assert p.bb_amount == Decimal("0.02")

    def test_nl5_dot_dropped_005(self):
        """Header $005 = $5.00, real stake is NL5 ($0.05 BB)."""
        hand = """\
Poker Hand #RC9900100001: Hold'em No Limit ($0.02/$005) - 2026/01/15 10:00:00
Table 'RushAndCash99001' 6-max Seat #1 is the button
Seat 1: Player1 ($6.50 in chips)
Seat 2: Player2 ($5.00 in chips)
Seat 3: Player3 ($5.30 in chips)
Seat 4: Hero ($6.10 in chips)
Seat 5: Player5 ($7.00 in chips)
Seat 6: Player6 ($5.00 in chips)
Player2: posts small blind $0.02
Player3: posts big blind $0.05
*** HOLE CARDS ***
Dealt to Hero [Ah Jc]
Hero: raises $0.05 to $0.1
Player5: folds
Player6: folds
Player1: folds
Player2: folds
Player3: calls $0.05
*** SHOWDOWN ***
Hero collected $0.22 from pot
*** SUMMARY ***
Total pot $0.22 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 4: Hero collected ($0.22)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.05")

    def test_header_only_corrupted(self):
        """Header says $0.74/$0.10, posted BB is $0.10 — NL10."""
        hand = """\
Poker Hand #RC9900100001: Hold'em No Limit ($0.74/$0.10) - 2026/01/15 10:00:00
Table 'RushAndCash99001' 6-max Seat #1 is the button
Seat 1: Player1 ($12.50 in chips)
Seat 2: Player2 ($10.00 in chips)
Seat 3: Player3 ($10.30 in chips)
Seat 4: Hero ($11.10 in chips)
Seat 5: Player5 ($13.00 in chips)
Seat 6: Player6 ($10.00 in chips)
Player2: posts small blind $0.05
Player3: posts big blind $0.10
*** HOLE CARDS ***
Dealt to Hero [Ah Jc]
Hero: raises $0.15 to $0.25
Player5: folds
Player6: folds
Player1: folds
Player2: folds
Player3: folds
Uncalled bet ($0.15) returned to Hero
*** SHOWDOWN ***
Hero collected $0.15 from pot
*** SUMMARY ***
Total pot $0.15 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 4: Hero collected ($0.15)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.10")

    def test_no_actions_fold_to_bb(self):
        """Everyone folds to BB — no preflop actions, uses fallback."""
        p = parse_hand_history(self._make_hand(
            header="$0.01/$0.02", sb="0.01", bb="0.02",
            preflop="Hero: folds\nPlayer5: folds\nPlayer6: folds\nPlayer1: folds\nPlayer2: folds\nUncalled bet ($0.01) returned to Player3\n",
        ))
        assert p.bb_amount == Decimal("0.02")

    def test_no_actions_header_corrupted(self):
        """No preflop actions + header corrupted — SB tiebreaker resolves."""
        p = parse_hand_history(self._make_hand(
            header="$0.01/$002", sb="0.01", bb="0.02",
            preflop="Hero: folds\nPlayer5: folds\nPlayer6: folds\nPlayer1: folds\nPlayer2: folds\nUncalled bet ($0.01) returned to Player3\n",
        ))
        assert p.bb_amount == Decimal("0.02")

    def test_header_bb_becomes_different_standard_stake(self):
        """Header BB corrupted from $0.02 to $0.05 (both standard). Actions resolve NL2.

        Real hand RC4327823011: header says $0.01/$0.05 but posted BB is $0.02
        and raise to $0.06 = 3x at NL2 (typical), 1.2x at NL5 (atypical).
        """
        hand = """\
Poker Hand #RC4327823011: Hold'em No Limit ($0.01/$0.05) - 2026/02/27 02:31:43
Table 'RushAndCash19646929' 6-max Seat #1 is the button
Seat 1: 7b230231 ($2.36 in chips)
Seat 2: d8a99f6b ($2.37 in chips)
Seat 3: 41e80c6a ($2.04 in chips)
Seat 4: Hero ($4.42 in chips)
Seat 5: a5ba07eb ($2.64 in chips)
Seat 6: 17fa6957 ($1.93 in chips)
d8a99f6b: posts small blind $0.01
41e80c6a: posts big blind $0.02
*** HOLE CARDS ***
Dealt to Hero [5c Ks]
Hero: folds
a5ba07eb: folds
17fa6957: raises $0.04 to $0.06
7b230231: folds
d8a99f6b: calls $0.05
41e80c6a: folds
*** FLOP *** [Qs 4h 5h]
d8a99f6b: checks
17fa6957: bets $0.06
d8a99f6b: raises $0.08 to $0.14
17fa6957: raises $0.22 to $0.36
d8a99f6b: calls $0.22
*** TURN *** [Qs 4h 5h] [2d]
d8a99f6b: checks
17fa6957: bets $0.31
d8a99f6b: calls $0.31
*** RIVER *** [Qs 4h 5h 2d] [3d]
d8a99f6b: checks
17fa6957: bets $0.62
d8a99f6b: calls $0.62
17fa6957: shows [Tc Ah] (a straight, Ace to Five)
d8a99f6b: shows [Qh Ac] (a straight, Ace to Five)
*** SHOWDOWN ***
d8a99f6b collected $1.32 from pot
17fa6957 collected $1.31 from pot
*** SUMMARY ***
Total pot $2.72 | Rake $0.06 | Jackpot $0.03 | Bingo $0 | Fortune $0 | Tax $0
Board [Qs 4h 5h 2d 3d]
Seat 1: 7b230231 (button) folded before Flop (didn't bet)
Seat 2: d8a99f6b (small blind) showed [Qh Ac] and won ($1.32) with a straight, Ace to Five
Seat 3: 41e80c6a (big blind) folded before Flop
Seat 4: Hero folded before Flop (didn't bet)
Seat 5: a5ba07eb folded before Flop (didn't bet)
Seat 6: 17fa6957 showed [Tc Ah] and won ($1.31) with a straight, Ace to Five
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.02")

    def test_real_hand_nl52_corruption(self):
        """Real hand RC4314742506: header+posted BB both corrupted to $0.52."""
        hand = """\
Poker Hand #RC4314742506: Hold'em No Limit ($0.01/$0.52) - 2026/02/21 22:30:11
Table 'RushAndCash16036662' 6-max Seat #1 is the button
Seat 1: f3c4555d ($2.03 in chips)
Seat 2: fcfb870b ($2.03 in chips)
Seat 3: ef907299 ($2.27 in chips)
Seat 4: Hero ($2.04 in chips)
Seat 5: dc065eff ($4.36 in chips)
Seat 6: 93cd4d24 ($2 in chips)
fcfb870b: posts small blind $0.01
ef907299: posts big blind $0.52
*** HOLE CARDS ***
Dealt to Hero [Ah Jc]
Hero: raises $0.03 to $0.05
dc065eff: folds
93cd4d24: folds
f3c4555d: folds
fcfb870b: folds
ef907299: folds
Uncalled bet ($0.03) returned to Hero
*** SHOWDOWN ***
Hero collected $0.05 from pot
*** SUMMARY ***
Total pot $0.05 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 4: Hero collected ($0.05)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.02")
        assert p.stakes == "$0.01/$0.02"

    def test_real_hand_nl200_dot_dropped(self):
        """Real hand RC4337993519: header BB $002 (dot dropped from $0.02)."""
        hand = """\
Poker Hand #RC4337993519: Hold'em No Limit ($0.01/$002) - 2026/03/03 03:32:34
Table 'RushAndCash22477396' 6-max Seat #1 is the button
Seat 1: 6252ce9e ($2.98 in chips)
Seat 2: ad0138a2 ($1.14 in chips)
Seat 3: 62de0394 ($6.9 in chips)
Seat 4: c1d74a26 ($9.58 in chips)
Seat 5: Hero ($2.38 in chips)
Seat 6: 37d192bf ($3.48 in chips)
ad0138a2: posts small blind $0.01
62de0394: posts big blind $0.02
*** HOLE CARDS ***
Dealt to Hero [6h Tc]
c1d74a26: folds
Hero: folds
37d192bf: folds
6252ce9e: folds
ad0138a2: folds
Uncalled bet ($0.01) returned to 62de0394
*** SHOWDOWN ***
62de0394 collected $0.02 from pot
*** SUMMARY ***
Total pot $0.02 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 5: Hero folded before Flop (didn't bet)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.02")

    def test_real_hand_nl200_dot_dropped_with_action(self):
        """Real hand RC4327478084: header BB $002 with preflop action."""
        hand = """\
Poker Hand #RC4327478084: Hold'em No Limit ($0.01/$002) - 2026/02/26 22:36:58
Table 'RushAndCash19542002' 6-max Seat #1 is the button
Seat 1: 5d886d28 ($3.12 in chips)
Seat 2: f87af489 ($2 in chips)
Seat 3: b2416d31 ($2.16 in chips)
Seat 4: Hero ($3.28 in chips)
Seat 5: dfbbb6a ($3.39 in chips)
Seat 6: 6383d678 ($2 in chips)
f87af489: posts small blind $0.01
b2416d31: posts big blind $0.02
*** HOLE CARDS ***
Dealt to Hero [3d Kc]
Hero: folds
dfbbb6a: folds
6383d678: raises $0.03 to $0.05
5d886d28: folds
f87af489: folds
b2416d31: calls $0.03
*** FLOP *** [9c 3h 5s]
b2416d31: checks
6383d678: checks
*** TURN *** [9c 3h 5s] [As]
b2416d31: checks
6383d678: bets $0.04
b2416d31: folds
Uncalled bet ($0.04) returned to 6383d678
*** SHOWDOWN ***
6383d678 collected $0.11 from pot
*** SUMMARY ***
Total pot $0.11 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Board [9c 3h 5s As]
Seat 6: 6383d678 won ($0.11)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.02")

    def test_real_hand_nl500_dot_dropped(self):
        """Real hand RC4306586133: header BB $005 (dot dropped from $0.05)."""
        hand = """\
Poker Hand #RC4306586133: Hold'em No Limit ($0.02/$005) - 2026/02/18 18:34:20
Table 'RushAndCash9101393' 6-max Seat #1 is the button
Seat 1: e74d6ef3 ($13.57 in chips)
Seat 2: cbd910e8 ($4.71 in chips)
Seat 3: 888f3558 ($6.02 in chips)
Seat 4: Hero ($6.98 in chips)
Seat 5: 25de2030 ($7.68 in chips)
Seat 6: 730be48e ($10.99 in chips)
cbd910e8: posts small blind $0.02
888f3558: posts big blind $0.05
*** HOLE CARDS ***
Dealt to Hero [Qd 8h]
Hero: folds
25de2030: folds
730be48e: raises $0.05 to $0.1
e74d6ef3: folds
cbd910e8: folds
888f3558: calls $0.05
*** FLOP *** [5s 8c Qh]
888f3558: checks
730be48e: checks
*** TURN *** [5s 8c Qh] [2s]
888f3558: checks
730be48e: bets $0.1
888f3558: folds
Uncalled bet ($0.1) returned to 730be48e
*** SHOWDOWN ***
730be48e collected $0.21 from pot
*** SUMMARY ***
Total pot $0.22 | Rake $0.01 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Board [5s 8c Qh 2s]
Seat 6: 730be48e won ($0.21)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.05")

    def test_both_corrupted_same_value(self):
        """Header and posted BB both say $0.52 — actions + snap resolve to NL50."""
        # Stacks ~$50 = 100 BB at NL50
        hand = """\
Poker Hand #RC9900100002: Hold'em No Limit ($0.26/$0.52) - 2026/01/15 10:00:00
Table 'RushAndCash99002' 6-max Seat #1 is the button
Seat 1: Player1 ($50.00 in chips)
Seat 2: Player2 ($48.00 in chips)
Seat 3: Player3 ($52.00 in chips)
Seat 4: Hero ($50.00 in chips)
Seat 5: Player5 ($55.00 in chips)
Seat 6: Player6 ($50.00 in chips)
Player2: posts small blind $0.26
Player3: posts big blind $0.52
*** HOLE CARDS ***
Dealt to Hero [Ah Kd]
Hero: raises $1.25 to $1.25
Player5: folds
Player6: folds
Player1: folds
Player2: folds
Player3: folds
Uncalled bet ($0.73) returned to Hero
*** SHOWDOWN ***
Hero collected $1.30 from pot
*** SUMMARY ***
Total pot $1.30 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 4: Hero collected ($1.30)
"""
        p = parse_hand_history(hand)
        assert p.bb_amount == Decimal("0.50")


class TestOpenRaiseOpp:
    """Test open_raise_opp flag (RFI opportunity)."""

    def test_open_raise_opp_basic(self, db):
        """Players acting before first raise get open_raise_opp=True."""
        text = (FIXTURES / "sample.txt").read_text()
        first_hand = text.split("\n\n\n")[0]
        parsed = parse_hand_history(first_hand)
        hand_id = insert_parsed_hand(db, parsed)

        # Hand: 6-max, Hero is BTN (seat 1)
        # Preflop action order: Player4 (EP) folds, Player5 (MP) raises,
        # Player6 (CO) folds, Hero (BTN) raises, Player2 (SB) folds, Player3 (BB) folds
        #
        # Before first raise (raise_count=0): Player4 acts → opp=True
        # Player5 raises (raise_count still 0 when they act) → opp=True, open_raise=True
        # After first raise (raise_count=1): Player6, Hero, Player2, Player3 → opp=False

        p4 = _get_player_stats(db, hand_id, "Player4")
        assert p4["open_raise_opp"] is True
        assert p4["open_raise"] is False

        p5 = _get_player_stats(db, hand_id, "Player5")
        assert p5["open_raise_opp"] is True
        assert p5["open_raise"] is True

        p6 = _get_player_stats(db, hand_id, "Player6")
        assert p6["open_raise_opp"] is False

        hero = _get_player_stats(db, hand_id, "Hero")
        assert hero["open_raise_opp"] is False
        # Hero 3-bet, not an open raise
        assert hero["open_raise"] is False
