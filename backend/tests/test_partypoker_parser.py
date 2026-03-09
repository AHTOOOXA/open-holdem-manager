import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.partypoker import parse_hand_history, detect, split_hands, extract_hand_id
from app.parsers.common import _ZERO
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache, _compute_financials
from app.stat_flags import compute_stat_flags
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "partypoker"
REAL_FIXTURES = FIXTURES / "real"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestDetection:
    def test_detect_partypoker(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "PP"

    def test_reject_888poker(self):
        """Critical: 888poker must NOT be detected as partypoker."""
        sample = "***** 888poker Hand History for Game 123 *****"
        assert detect(sample) is False

    def test_reject_pokerstars(self):
        assert detect("PokerStars Hand #123") is False

    def test_888poker_not_misdetected_by_registry(self):
        """Ensure detect_parser routes 888poker correctly, not to partypoker."""
        sample = "***** 888poker Hand History for Game 123 *****\n$0.25/$0.50 Blinds"
        parser = detect_parser(sample)
        assert parser is None or parser.SITE_CODE != "PP"


class TestSplitting:
    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "111222333"


class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "111222333"
        assert parsed.site_id == 7
        assert parsed.game_type == "NLH"
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.table_name == "Houston"
        assert parsed.table_size == 6
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Player4"
        assert parsed.bb_player == "Player5"
        assert parsed.board_cards["flop"] == ["Kh", "7c", "2d"]
        assert parsed.board_cards["turn"] == ["5s"]
        assert parsed.board_cards["river"] == ["9h"]

    def test_date_parsing(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.played_at.year == 2024
        assert parsed.played_at.month == 1
        assert parsed.played_at.day == 15
        assert parsed.played_at.hour == 14
        assert parsed.played_at.minute == 30

    def test_hero_cards_with_extra_spaces(self):
        """Dealt to Player1 [  Ah Kd  ] — extra spaces must be handled."""
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["Player1"] == ("Ah", "Kd")

    def test_raise_is_to_amount(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) >= 1
        assert raises[0]["amount"] == Decimal("1.50")

    def test_showdown_detection(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "Player1" in parsed.went_to_showdown_players
        assert "Player5" in parsed.went_to_showdown_players

    def test_financials_balance(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)
        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        # invested - uncalled = collected + rake
        assert float(total_invested - total_uncalled) == pytest.approx(
            float(total_collected + parsed.total_rake), abs=0.01
        )

    def test_rake_computed(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Total invested: SB 0.25, BB 0.50, P1: 1.50+2.25+4.50+8.00=16.25,
        # P3: 1.50, P5: 0.50+1.00+2.25+4.50+8.00=16.25
        # Total = 0.25 + 0.50 + 16.25 + 1.50 + 16.25 = 34.75
        # Wait: P5 BB=0.50, then calls 1.00 (already has 0.50 in), calls 2.25, 4.50, 8.00
        # P5 preflop: sb=0 bb=0.50 call=1.00 → total street = 1.50
        # P4: sb=0.25
        # Total invested = 0.25 + 0.50 + 1.00 + 1.50 + 1.50 + 2.25 + 2.25 + 4.50 + 4.50 + 8.00 + 8.00 = 34.25
        # Collected: 32.75, Uncalled: 0
        # Rake: 34.25 - 0 - 32.75 = 1.50
        assert parsed.total_rake == Decimal("1.50")

    def test_stat_flags(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        assert stats["Player1"]["vpip"] is True
        assert stats["Player1"]["pfr"] is True
        assert stats["Player5"]["vpip"] is True
        assert stats["Player1"]["went_to_showdown"] is True
        assert stats["Player1"]["won_at_showdown"] is True

    def test_db_insert(self, db):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "111222333"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 7
        assert row[1] == "$0.25/$0.50"

        # Player1 won
        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        # Player1: invested 1.50 + 2.25 + 4.50 + 8.00 = 16.25, collected 32.75
        # net = 32.75 - 16.25 = 16.50
        assert float(won) == pytest.approx(16.50, abs=0.01)


class TestPreflopFold:
    def test_preflop_fold_collected(self, db):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        hand_id = insert_parsed_hand(db, parsed)

        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        # Player1 raised to $1.50, everyone folds
        # Uncalled: $1.00, Collected: $1.25 (the blinds)
        # Net: $1.25 + $1.00 - $1.50 = $0.75
        assert float(won) == pytest.approx(0.75, abs=0.01)

    def test_preflop_fold_uncalled_returns(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.uncalled_returns.get("Player1", _ZERO) == Decimal("1.00")

    def test_preflop_fold_rake_zero(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.total_rake == _ZERO

    def test_preflop_fold_no_showdown(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.in_showdown is False
        assert len(parsed.went_to_showdown_players) == 0

    def test_doesnt_show_captures_cards(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.hero_cards["Player1"] == ("Td", "9d")


class TestMultiHand:
    def test_both_hands_parse_and_insert(self, db):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2
        for h in hands:
            parsed = parse_hand_history(h)
            insert_parsed_hand(db, parsed)

        count = db.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
        assert count == 2

    def test_second_hand_id(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.hand_id == "111222334"


# ─── Real Fixtures ─────────────────────────────────────────────────────────────

class TestRealGeneral:
    """Test against real partypoker hand: general.txt — 9-max limped pot, no showdown."""

    def test_detect_real(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_real(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "PP"

    def test_parse_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "13550319286"
        assert parsed.site_id == 7
        assert parsed.game_type == "NLH"
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Cádiz"
        assert parsed.table_size == 9
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 9
        assert parsed.sb_player == "Kruglenya77"
        assert parsed.bb_player == "MasterP002"

    def test_date_parsing(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.played_at.year == 2014
        assert parsed.played_at.month == 1
        assert parsed.played_at.day == 6

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["Qs", "7h", "2s"]
        assert parsed.board_cards["turn"] == ["7s"]
        assert parsed.board_cards["river"] == ["Kc"]

    def test_actions_preflop(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        calls = [a for a in preflop if a["action"] == "call"]
        assert len(calls) == 3
        folds = [a for a in preflop if a["action"] == "fold"]
        assert len(folds) == 4  # Te-ta-tet, Raskolnikov89, DarkSun2011, Kruglenya77

    def test_no_showdown(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is False
        assert len(parsed.went_to_showdown_players) == 0

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["lenstr1"] == Decimal("0.53")
        assert float(parsed.total_rake) == pytest.approx(0.02, abs=0.01)

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # lenstr1 called preflop — VPIP but not PFR
        assert stats["lenstr1"]["vpip"] is True
        assert stats["lenstr1"]["pfr"] is False
        # Bavariared called preflop — VPIP
        assert stats["Bavariared"]["vpip"] is True
        assert stats["Bavariared"]["pfr"] is False
        # DarkSun2011 folded — no VPIP
        assert stats["DarkSun2011"]["vpip"] is False
        # MasterP002 (BB) just checked — no VPIP
        assert stats["MasterP002"]["vpip"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "13550319286"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 7
        assert row[1] == "$0.05/$0.10"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 9

    def test_zero_stack_player_handled(self):
        """rickybobby83 has $0 stack and leaves — should still be in seats."""
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        ricky = [s for s in parsed.seats if s["username"] == "rickybobby83"]
        assert len(ricky) == 1
        assert ricky[0]["stack"] == Decimal("0")


class TestRealAllinShowdown:
    """Test against real partypoker hand: allin_showdown.txt — multiway all-in with side pot."""

    def test_detect_real_with_bom(self):
        """File has BOM — detect should still work."""
        sample = open(REAL_FIXTURES / "allin_showdown.txt").read()[:500]
        assert detect(sample) is True

    def test_parse_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "13549932236"
        assert parsed.site_id == 7
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Aksay"
        assert parsed.table_size == 6
        assert parsed.button_seat == 5
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "kewen"
        assert parsed.bb_player == "xyxyTiltyxyx"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["8s", "5c", "6h"]
        assert parsed.board_cards["turn"] == ["Ac"]
        assert parsed.board_cards["river"] == ["Tc"]

    def test_raise_is_to_amount(self):
        """dr. spaz raises [$0.30 USD] — the total in for this street."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 1
        assert raises[0]["username"] == "dr. spaz"
        assert raises[0]["amount"] == Decimal("0.30")

    def test_allin_actions(self):
        """dr. spaz and TYRANNOMAN1 both go all-in on river."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        river = parsed.actions_by_street["river"]
        allins = [a for a in river if a["is_all_in"]]
        assert len(allins) == 2
        assert allins[0]["username"] == "dr. spaz"
        assert allins[0]["amount"] == Decimal("4.90")
        assert allins[1]["username"] == "TYRANNOMAN1"
        assert allins[1]["amount"] == Decimal("3.03")

    def test_showdown_detection(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "dr. spaz" in parsed.went_to_showdown_players
        assert "TYRANNOMAN1" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["dr. spaz"] == ("8c", "8d")
        assert parsed.hero_cards["TYRANNOMAN1"] == ("Jc", "Jd")

    def test_collected_includes_side_pot(self):
        """dr. spaz wins from both side pot and main pot."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        # $1.87 from side pot + $20.66 from main pot
        assert parsed.collected["dr. spaz"] == Decimal("22.53")

    def test_rake(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert float(parsed.total_rake) == pytest.approx(1.00, abs=0.02)

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_player_investments(self):
        """Verify per-player invested amounts."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)
        assert float(player_invested["dr. spaz"]) == pytest.approx(10.0, abs=0.01)
        assert float(player_invested["TYRANNOMAN1"]) == pytest.approx(8.13, abs=0.01)
        assert float(player_invested["xyxyTiltyxyx"]) == pytest.approx(5.10, abs=0.01)
        assert float(player_invested["kewen"]) == pytest.approx(0.30, abs=0.01)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # dr. spaz raised preflop — VPIP and PFR
        assert stats["dr. spaz"]["vpip"] is True
        assert stats["dr. spaz"]["pfr"] is True
        # TYRANNOMAN1 called — VPIP but not PFR
        assert stats["TYRANNOMAN1"]["vpip"] is True
        assert stats["TYRANNOMAN1"]["pfr"] is False
        # GrindAA folded — no VPIP
        assert stats["GrindAA"]["vpip"] is False
        # Showdown results
        assert stats["dr. spaz"]["went_to_showdown"] is True
        assert stats["dr. spaz"]["won_at_showdown"] is True
        assert stats["TYRANNOMAN1"]["went_to_showdown"] is True
        assert stats["TYRANNOMAN1"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "13549932236"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 7
        assert row[1] == "$0.05/$0.10"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 6
