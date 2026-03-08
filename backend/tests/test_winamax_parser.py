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
