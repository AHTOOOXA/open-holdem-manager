import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.pokerstars import parse_hand_history, detect, split_hands, extract_hand_id
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache
from app.stat_flags import compute_stat_flags
from app.api.import_hands import _compute_financials
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "pokerstars"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestDetection:
    def test_detect_pokerstars(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_zoom(self):
        sample = open(FIXTURES / "zoom.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_to_pokerstars(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "PS"

    def test_reject_ggpoker(self):
        assert detect("Poker Hand #RC1234: Hold'em") is False


class TestSplitting:
    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "RC234567890"


class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "RC234567890"
        assert parsed.site_id == 2
        assert parsed.game_type == "NLH"
        assert parsed.game_mode == ""
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.table_name == "Antlia IV"
        assert parsed.table_size == 6
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Player5"
        assert parsed.bb_player == "Player6"
        assert parsed.board_cards["flop"] == ["Kh", "7c", "2d"]
        assert parsed.board_cards["turn"] == ["5s"]
        assert parsed.board_cards["river"] == ["9h"]
        assert parsed.in_showdown is True
        assert "Player1" in parsed.went_to_showdown_players
        assert "Player6" in parsed.went_to_showdown_players
        assert parsed.hero_cards["Player1"] == ("Ah", "Kd")

    def test_raise_to_amount(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        # Player1: raises $1.00 to $1.50 — should store 1.50
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) >= 1
        assert raises[0]["amount"] == Decimal("1.50")

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
        # Player6 (BB) called
        assert stats["Player6"]["vpip"] is True
        assert stats["Player6"]["pfr"] is False
        # Both went to showdown
        assert stats["Player1"]["went_to_showdown"] is True
        assert stats["Player6"]["went_to_showdown"] is True
        # Player1 won at showdown
        assert stats["Player1"]["won_at_showdown"] is True
        assert stats["Player6"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "RC234567890"

        # Verify hand exists
        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 2  # site_id
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


class TestZoomHand:
    def test_zoom_game_mode(self):
        text = open(FIXTURES / "zoom.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.game_mode == "Fast Fold"
        assert parsed.hand_id == "RC345678901"

    def test_zoom_uncalled_bet(self):
        text = open(FIXTURES / "zoom.txt").read()
        parsed = parse_hand_history(text)
        assert "Player1" in parsed.uncalled_returns
        assert parsed.uncalled_returns["Player1"] == Decimal("7.50")

    def test_zoom_financials(self, db):
        text = open(FIXTURES / "zoom.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)

        # Player1: preflop raise to 4.00, flop bet 3.00, turn bet 7.50 (returned)
        # invested: 4.00 + 3.00 + 7.50 = 14.50, uncalled: 7.50
        # collected: 14.25
        # net = 14.25 - (14.50 - 7.50) = 14.25 - 7.00 = 7.25
        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'Player1'",
            [hand_id]
        ).fetchone()[0]
        assert float(won) == pytest.approx(7.25, abs=0.01)
