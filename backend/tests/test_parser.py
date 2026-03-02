"""Tests for GGPoker hand history parser edge cases."""

import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.ggpoker import parse_hand_history
from app.api.import_hands import insert_parsed_hand, reset_import_cache
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def db():
    """Create an in-memory DuckDB with schema for each test."""
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


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
        text = (FIXTURES / "ggpoker_sample.txt").read_text()
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
        text = (FIXTURES / "ggpoker_sample.txt").read_text()
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


class TestOpenRaiseOpp:
    """Test open_raise_opp flag (RFI opportunity)."""

    def test_open_raise_opp_basic(self, db):
        """Players acting before first raise get open_raise_opp=True."""
        text = (FIXTURES / "ggpoker_sample.txt").read_text()
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
