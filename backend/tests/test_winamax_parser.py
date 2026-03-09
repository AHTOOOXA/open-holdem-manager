import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.winamax import parse_hand_history, detect, split_hands, extract_hand_id
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache
from app.stat_flags import compute_stat_flags
from app.api.import_hands import _compute_financials
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "winamax"
REAL_FIXTURES = FIXTURES / "real"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestDetection:
    def test_detect_winamax(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_to_winamax(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "WMX"

    def test_reject_ggpoker(self):
        assert detect("Poker Hand #RC1234: Hold'em") is False

    def test_reject_pokerstars(self):
        assert detect("PokerStars Hand #RC234567890:") is False

    def test_reject_888poker(self):
        assert detect("***** 888poker Hand History") is False


class TestSplitting:
    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "1234-5678-9012"


class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "1234-5678-9012"
        assert parsed.site_id == 5
        assert parsed.game_type == "NLH"
        assert parsed.game_mode == ""
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.stakes == "\u20ac0.25/\u20ac0.50"
        assert parsed.table_name == "Lyon"
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

    def test_euro_amount_parsing(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Verify stacks parsed correctly from euro format
        seat1 = [s for s in parsed.seats if s["seat"] == 1][0]
        assert seat1["stack"] == Decimal("52.35")
        seat5 = [s for s in parsed.seats if s["seat"] == 5][0]
        assert seat5["stack"] == Decimal("51.50")

    def test_raise_to_amount(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Player1 raises 1.50€ to 1.50€ — should store 1.50 (the "to" amount)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) >= 1
        assert raises[0]["amount"] == Decimal("1.50")

    def test_rake_from_summary(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.total_rake == Decimal("1.50")

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
        # Player1 raised preflop
        assert stats["Player1"]["vpip"] is True
        assert stats["Player1"]["pfr"] is True
        # Player5 (BB) called
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
        assert hand_id == "1234-5678-9012"

        # Verify hand exists
        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 5  # site_id
        assert row[1] == "\u20ac0.25/\u20ac0.50"

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


class TestPreflopFold:
    def test_preflop_fold_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2
        parsed = parse_hand_history(hands[1])
        assert parsed.hand_id == "1234-5678-9013"
        assert parsed.in_showdown is False

    def test_preflop_fold_uncalled_returns(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        # Player1 raises to 1.50, everyone folds
        # Uncalled = 1.50 - 0.50 (BB) = 1.00
        assert "Player1" in parsed.uncalled_returns
        assert parsed.uncalled_returns["Player1"] == Decimal("1.00")

    def test_preflop_fold_collected(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.collected["Player1"] == Decimal("1.25")

    def test_preflop_fold_rake(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.total_rake == Decimal("0")

    def test_preflop_fold_net_won(self, db):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        hand_id = insert_parsed_hand(db, parsed)

        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        # Player1: invested 1.50, uncalled 1.00, collected 1.25
        # net = 1.25 - (1.50 - 1.00) = 1.25 - 0.50 = 0.75
        assert float(won) == pytest.approx(0.75, abs=0.01)

    def test_preflop_fold_financials_balance(self):
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


# ─── Real Winamax Fixtures ─────────────────────────────────────────────────


class TestRealGeneral:
    """Test against real Winamax hand: general.txt — 2-max heads-up showdown."""

    def test_detect_real(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_to_winamax(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "WMX"

    def test_parse_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "5281577-471-1382586707"
        assert parsed.site_id == 5
        assert parsed.sb_amount == Decimal("0.50")
        assert parsed.bb_amount == Decimal("1")
        assert parsed.stakes == "\u20ac0.50/\u20ac1"
        assert parsed.table_name == "Gold Coast-Tweed 13"
        assert parsed.table_size == 2
        assert parsed.button_seat == 2
        assert len(parsed.seats) == 2
        assert parsed.sb_player == "titi63000"
        assert parsed.bb_player == "Barthez91"

    def test_seats(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        seat1 = [s for s in parsed.seats if s["seat"] == 1][0]
        assert seat1["username"] == "Barthez91"
        assert seat1["stack"] == Decimal("138.61")
        seat2 = [s for s in parsed.seats if s["seat"] == 2][0]
        assert seat2["username"] == "titi63000"
        assert seat2["stack"] == Decimal("116.40")

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["3c", "7d", "2s"]
        assert parsed.board_cards["turn"] == ["3h"]
        assert parsed.board_cards["river"] == ["4c"]

    def test_preflop_actions(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        # SB, BB, raise, raise, call
        assert len(preflop) == 5
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 2
        assert raises[0]["username"] == "titi63000"
        assert raises[0]["amount"] == Decimal("2.50")
        assert raises[1]["username"] == "Barthez91"
        assert raises[1]["amount"] == Decimal("7.50")

    def test_street_actions_separated(self):
        """Verify turn/river actions are correctly separated from flop."""
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert len(parsed.actions_by_street["flop"]) == 2
        assert len(parsed.actions_by_street["turn"]) == 2
        assert len(parsed.actions_by_street["river"]) == 2

    def test_showdown(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "Barthez91" in parsed.went_to_showdown_players
        assert "titi63000" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["Barthez91"] == ("8s", "Td")
        assert parsed.hero_cards["titi63000"] == ("8d", "Jd")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["titi63000"] == Decimal("14.02")
        assert parsed.total_rake == Decimal("0.98")

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
        # titi63000 raised preflop
        assert stats["titi63000"]["vpip"] is True
        assert stats["titi63000"]["pfr"] is True
        # Barthez91 3-bet preflop
        assert stats["Barthez91"]["vpip"] is True
        assert stats["Barthez91"]["pfr"] is True
        # Both went to showdown
        assert stats["titi63000"]["went_to_showdown"] is True
        assert stats["Barthez91"]["went_to_showdown"] is True
        # titi63000 won at showdown
        assert stats["titi63000"]["won_at_showdown"] is True
        assert stats["Barthez91"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "5281577-471-1382586707"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 5
        assert row[1] == "\u20ac0.50/\u20ac1"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 2


class TestRealAllinShowdown:
    """Test against real Winamax hand: allin_showdown.txt — 5-max with all-in preflop."""

    def test_detect_real(self):
        sample = open(REAL_FIXTURES / "allin_showdown.txt").read()[:500]
        assert detect(sample) is True

    def test_parse_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "5343878-96-1383820687"
        assert parsed.site_id == 5
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.stakes == "\u20ac0.25/\u20ac0.50"
        assert parsed.table_name == "Athens 11"
        assert parsed.table_size == 5
        assert parsed.button_seat == 4
        assert len(parsed.seats) == 5

    def test_seats(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        seat4 = [s for s in parsed.seats if s["seat"] == 4][0]
        assert seat4["username"] == "LEROISALO"
        assert seat4["stack"] == Decimal("22.85")

    def test_blinds(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.sb_player == "Matthieu_59_"
        assert parsed.bb_player == "PornstarX"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["3c", "7c", "Jd"]
        assert parsed.board_cards["turn"] == ["6c"]
        assert parsed.board_cards["river"] == ["5s"]

    def test_allin_action(self):
        """LEROISALO raises all-in preflop."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        allin_actions = [a for a in preflop if a["is_all_in"]]
        assert len(allin_actions) == 1
        assert allin_actions[0]["username"] == "LEROISALO"
        assert allin_actions[0]["action"] == "raise"
        assert allin_actions[0]["amount"] == Decimal("22.85")

    def test_preflop_actions(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) == 2
        assert raises[0]["username"] == "nico86190"
        assert raises[0]["amount"] == Decimal("2.50")
        assert raises[1]["username"] == "LEROISALO"
        assert raises[1]["amount"] == Decimal("22.85")
        calls = [a for a in preflop if a["action"] == "call"]
        assert len(calls) == 1
        assert calls[0]["username"] == "nico86190"
        assert calls[0]["amount"] == Decimal("20.35")

    def test_showdown(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "LEROISALO" in parsed.went_to_showdown_players
        assert "nico86190" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["LEROISALO"] == ("Kh", "Ah")
        assert parsed.hero_cards["nico86190"] == ("Qh", "Qc")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["nico86190"] == Decimal("43.45")
        assert parsed.total_rake == Decimal("3")

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        assert float(player_invested["nico86190"]) == pytest.approx(22.85, abs=0.01)
        assert float(player_invested["LEROISALO"]) == pytest.approx(22.85, abs=0.01)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # nico86190 raised — VPIP and PFR
        assert stats["nico86190"]["vpip"] is True
        assert stats["nico86190"]["pfr"] is True
        # LEROISALO 3-bet all-in — VPIP and PFR
        assert stats["LEROISALO"]["vpip"] is True
        assert stats["LEROISALO"]["pfr"] is True
        # PornstarX folded BB — no VPIP
        assert stats["PornstarX"]["vpip"] is False
        # Both showdown players
        assert stats["nico86190"]["went_to_showdown"] is True
        assert stats["LEROISALO"]["went_to_showdown"] is True
        # nico86190 won
        assert stats["nico86190"]["won_at_showdown"] is True
        assert stats["LEROISALO"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "5343878-96-1383820687"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 5
        assert row[1] == "\u20ac0.25/\u20ac0.50"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 5
