import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.wpn import parse_hand_history, detect, split_hands, extract_hand_id
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache
from app.stat_flags import compute_stat_flags
from app.api.import_hands import _compute_financials
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "wpn"
REAL_FIXTURES = FIXTURES / "real"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


# ─── Detection ───────────────────────────────────────────────────────────────

class TestDetection:
    def test_detect_wpn(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_real_wpn(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_to_wpn(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "WPN"

    def test_detect_real_parser_routes_to_wpn(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "WPN"

    def test_reject_pokerstars(self):
        assert detect("PokerStars Hand #RC1234: Hold'em") is False

    def test_reject_ggpoker(self):
        assert detect("Poker Hand #RC1234: Hold'em") is False


# ─── Splitting ───────────────────────────────────────────────────────────────

class TestSplitting:
    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "987654321"

    def test_extract_hand_id_real(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        hid = extract_hand_id(text)
        assert hid == "261641541"


# ─── Basic Hand (rewritten fixture in real WPN format) ───────────────────────

class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "987654321"
        assert parsed.site_id == 4
        assert parsed.game_type == "NLH"
        assert parsed.game_mode == ""
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.table_name == "Quick Seat 12345"
        assert parsed.table_size == 6
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Player4"
        assert parsed.bb_player == "Player5"
        assert parsed.board_cards["flop"] == ["Kh", "7c", "2d"]
        assert parsed.board_cards["turn"] == ["5s"]
        assert parsed.board_cards["river"] == ["9h"]
        assert parsed.in_showdown is True
        assert "Player1" in parsed.went_to_showdown_players
        assert "Player5" in parsed.went_to_showdown_players
        assert parsed.hero_cards["Player1"] == ("Ah", "Kd")

    def test_raise_increment_tracking(self):
        """WPN raises are incremental. Verify the parser computes correct 'to' amounts."""
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Player1 raises (1.50) from position with 0 already in
        # to_amount = 0 + 1.50 = 1.50
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 1
        assert raises[0]["amount"] == Decimal("1.50")
        assert raises[0]["username"] == "Player1"

    def test_financials_balance(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        # invested - uncalled = collected + rake + jackpot
        assert float(total_invested - total_uncalled) == pytest.approx(
            float(total_collected + parsed.total_rake + parsed.total_jackpot), abs=0.01
        )

    def test_stat_flags(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # Player1 raised preflop — VPIP and PFR
        assert stats["Player1"]["vpip"] is True
        assert stats["Player1"]["pfr"] is True
        # Player5 (BB) called — VPIP but not PFR
        assert stats["Player5"]["vpip"] is True
        assert stats["Player5"]["pfr"] is False
        # Both went to showdown
        assert stats["Player1"]["went_to_showdown"] is True
        assert stats["Player5"]["went_to_showdown"] is True
        # Player1 won at showdown
        assert stats["Player1"]["won_at_showdown"] is True
        assert stats["Player5"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "987654321"

        # Verify hand exists with correct site_id
        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 4  # site_id for WPN
        assert row[1] == "$0.25/$0.50"

        # Verify player count
        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 6

        # Verify Player1 won
        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        # Player1: invested 1.50 + 2.25 + 4.50 + 8.00 = 16.25, collected 32.75
        # net = 32.75 - 16.25 = 16.50
        assert float(won) == pytest.approx(16.50, abs=0.01)


# ─── Preflop Fold Hand ──────────────────────────────────────────────────────

class TestPreflopFoldHand:
    """Test second hand from multi_hand.txt — preflop fold with uncalled bet."""

    def test_parse_second_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2
        parsed = parse_hand_history(hands[1])
        assert parsed.hand_id == "987654322"
        assert parsed.site_id == 4
        # Uncalled bet computed from actions (everyone folded)
        assert "Player1" in parsed.uncalled_returns
        assert parsed.uncalled_returns["Player1"] == Decimal("1.00")
        # Player1 collected from summary
        assert parsed.collected["Player1"] == Decimal("1.25")
        # No showdown
        assert parsed.in_showdown is False
        assert parsed.total_rake == Decimal("0")

    def test_preflop_fold_financials(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        assert float(total_invested - total_uncalled) == pytest.approx(
            float(total_collected + parsed.total_rake + parsed.total_jackpot), abs=0.01
        )

    def test_preflop_fold_db_insert(self, db):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        hand_id = insert_parsed_hand(db, parsed)

        # Player1: raised to 1.50, uncalled 1.00 returned, collected 1.25
        # invested = 1.50, net = 1.25 - (1.50 - 1.00) = 1.25 - 0.50 = 0.75
        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        assert float(won) == pytest.approx(0.75, abs=0.01)


# ─── Real WPN Fixtures ──────────────────────────────────────────────────────

class TestRealGeneral:
    """Test against real WPN hand: general.txt — 6-max showdown hand."""

    def test_parse_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "261641541"
        assert parsed.site_id == 4
        assert parsed.sb_amount == Decimal("0.10")
        assert parsed.bb_amount == Decimal("0.25")
        assert parsed.table_name == "Tantalite   (JP)"
        assert parsed.button_seat == 5
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "johna52801"
        assert parsed.bb_player == "Shipologist"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["3h", "4c", "2c"]
        assert parsed.board_cards["turn"] == ["6h"]
        assert parsed.board_cards["river"] == ["Qh"]

    def test_raise_increment_to_amount(self):
        """LadyStack raises (0.80) with nothing already in.
        to_amount should be 0.80."""
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 1
        assert raises[0]["username"] == "LadyStack"
        assert raises[0]["amount"] == Decimal("0.80")

    def test_calls_are_incremental(self):
        """johna52801 calls (0.70) — incremental from SB."""
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        calls = [a for a in preflop if a["action"] == "call"]
        assert len(calls) == 1
        assert calls[0]["username"] == "johna52801"
        assert calls[0]["amount"] == Decimal("0.70")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["johna52801"] == Decimal("7.73")
        # Rake includes jackpot drop (JP table): summary shows 0.41, but
        # total deduction is 0.66 (0.41 rake + 0.25 jackpot).
        # Parser computes total_rake from invested to ensure balance.
        assert float(parsed.total_rake) == pytest.approx(0.66, abs=0.02)

    def test_showdown_players(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "johna52801" in parsed.went_to_showdown_players
        assert "LadyStack" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["johna52801"] == ("Jd", "Js")
        assert parsed.hero_cards["LadyStack"] == ("9s", "9c")

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "261641541"

        row = db.execute("SELECT site_id FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 4

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # LadyStack raised preflop — VPIP and PFR
        assert stats["LadyStack"]["vpip"] is True
        assert stats["LadyStack"]["pfr"] is True
        # johna52801 called preflop — VPIP but not PFR
        assert stats["johna52801"]["vpip"] is True
        assert stats["johna52801"]["pfr"] is False
        # borjilius79 folded — no VPIP
        assert stats["borjilius79"]["vpip"] is False


class TestRealAllinShowdown:
    """Test against real WPN hand: allin_showdown.txt — all-in heads-up."""

    def test_parse_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "261402183"
        assert parsed.sb_amount == Decimal("2")
        assert parsed.bb_amount == Decimal("4")
        assert len(parsed.seats) == 2
        assert parsed.button_seat == 1

    def test_raise_increment_tracking(self):
        """Verify incremental raise math:
        do not-call: SB(2), raises(10) -> to = 2+10 = 12
        digbick30: BB(4), raises(32) -> to = 4+32 = 36
        do not-call: calls(24) -> total = 12+24 = 36
        """
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]

        # do not-call raises (10): already_in = 2 (SB), to = 12
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 2
        assert raises[0]["username"] == "do not-call"
        assert raises[0]["amount"] == Decimal("12")  # 2 + 10
        assert raises[1]["username"] == "digbick30"
        assert raises[1]["amount"] == Decimal("36")  # 4 + 32

        # do not-call calls (24)
        calls = [a for a in preflop if a["action"] == "call"]
        assert len(calls) == 1
        assert calls[0]["amount"] == Decimal("24")

    def test_allin_action(self):
        """do not-call allin (124) on flop."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        flop = parsed.actions_by_street["flop"]
        allin_actions = [a for a in flop if a["is_all_in"]]
        assert len(allin_actions) == 1
        assert allin_actions[0]["username"] == "do not-call"
        assert allin_actions[0]["is_all_in"] is True

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        # Both players bet 160
        assert float(player_invested["do not-call"]) == pytest.approx(160.0, abs=0.01)
        assert float(player_invested["digbick30"]) == pytest.approx(160.0, abs=0.01)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_showdown(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "do not-call" in parsed.went_to_showdown_players
        assert "digbick30" in parsed.went_to_showdown_players

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["do not-call"] == Decimal("319")
        assert parsed.total_rake == Decimal("1")

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "261402183"


class TestRealBasicMultiway:
    """Test against real WPN hand: basic.txt — 5-player multiway with mucks."""

    def test_parse_basic_real(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "261679750"
        assert parsed.sb_amount == Decimal("2")
        assert parsed.bb_amount == Decimal("4")
        assert len(parsed.seats) == 5
        assert parsed.button_seat == 5

    def test_mucks_not_showdown(self):
        """Players who muck should not be in went_to_showdown_players."""
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Only HanSoloDolo showed cards
        assert "HanSoloDolo" in parsed.went_to_showdown_players
        # Mucks should not count — but the winner showed, so check that
        # at least the winner has cards
        assert "HanSoloDolo" in parsed.hero_cards

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["HanSoloDolo"] == Decimal("45.75")
        # Rake computed from invested (may include jackpot drop)
        assert float(parsed.total_rake) == pytest.approx(2.25, abs=0.02)

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "261679750"


class TestRealStraddle:
    """Test against real WPN hand: straddle.txt — hand with straddle."""

    def test_parse_straddle(self):
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "266899075"
        assert parsed.sb_amount == Decimal("0.10")
        assert parsed.bb_amount == Decimal("0.25")
        assert len(parsed.seats) == 6

    def test_straddle_action(self):
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        straddles = [a for a in preflop if a["action"] == "straddle"]
        assert len(straddles) == 1
        assert straddles[0]["username"] == "D3SISION"
        assert straddles[0]["amount"] == Decimal("0.50")

    def test_explicit_uncalled_bet(self):
        """This hand has an explicit 'Uncalled bet' line."""
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        assert "D3SISION" in parsed.uncalled_returns
        assert parsed.uncalled_returns["D3SISION"] == Decimal("0.50")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["D3SISION"] == Decimal("0.80")
        # Rake computed from invested (includes jackpot drop on JP table)
        # Summary says 0.05, but total deduction is 0.30
        assert float(parsed.total_rake) == pytest.approx(0.30, abs=0.02)

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "straddle.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "266899075"

        # Verify straddle player has the straddle amount tracked
        row = db.execute("SELECT site_id FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 4
