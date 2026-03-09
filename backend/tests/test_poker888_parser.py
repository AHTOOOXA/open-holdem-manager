import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.poker888 import parse_hand_history, detect, split_hands, extract_hand_id
from app.parsers.common import _ZERO
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache, _compute_financials
from app.stat_flags import compute_stat_flags
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "poker888"
REAL_FIXTURES = FIXTURES / "real"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestDetection:
    def test_detect_888poker(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "888"

    def test_reject_pokerstars(self):
        assert detect("PokerStars Hand #123") is False

    def test_reject_partypoker(self):
        # Must not false-positive on partypoker
        assert detect("***** Hand History for Game 123 *****") is False


class TestSplitting:
    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "1234567890"


class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "1234567890"
        assert parsed.site_id == 3
        assert parsed.game_type == "NLH"
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.table_name == "Portland"
        assert parsed.table_size == 6
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Player4"
        assert parsed.bb_player == "Player5"
        assert parsed.board_cards["flop"] == ["Kh", "7c", "2d"]
        assert parsed.board_cards["turn"] == ["5s"]
        assert parsed.board_cards["river"] == ["9h"]

    def test_raise_is_to_amount(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) >= 1
        assert raises[0]["amount"] == Decimal("1.50")

    def test_hero_cards_parsed(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["Player1"] == ("Ah", "Kd")

    def test_showdown_detection(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
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
        # Total invested: 16.25 + 16.25 + 1.50 + 0.25 = 34.25
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
        assert hand_id == "1234567890"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 3
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
        assert parsed.hand_id == "1234567891"


# ─── Real 888poker Fixtures ──────────────────────────────────────────────────


class TestRealDetection:
    def test_detect_real_general(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_real_allin(self):
        sample = open(REAL_FIXTURES / "allin_showdown.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_real(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "888"

    def test_extract_hand_id_real(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        hid = extract_hand_id(text)
        assert hid == "349736402"


class TestRealGeneral:
    """Test against real 888poker hand: general.txt — heads-up, no showdown."""

    def test_parse_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "349736402"
        assert parsed.site_id == 3
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Abbotsford"
        assert parsed.table_size == 6
        assert parsed.button_seat == 9
        assert len(parsed.seats) == 2
        assert parsed.sb_player == "FCSM_1935"
        assert parsed.bb_player == "silas_tomkyn"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["Jc", "Kc", "3c"]
        assert parsed.board_cards["turn"] == []
        assert parsed.board_cards["river"] == []

    def test_actions(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        # SB posts, BB posts, SB calls, BB checks
        assert len(preflop) == 4
        assert preflop[0]["action"] == "sb"
        assert preflop[1]["action"] == "bb"
        assert preflop[2]["action"] == "call"
        assert preflop[2]["username"] == "FCSM_1935"
        assert preflop[2]["amount"] == Decimal("0.05")
        assert preflop[3]["action"] == "check"

        flop = parsed.actions_by_street["flop"]
        assert len(flop) == 3
        assert flop[1]["action"] == "bet"
        assert flop[1]["username"] == "FCSM_1935"
        assert flop[1]["amount"] == Decimal("0.10")
        assert flop[2]["action"] == "fold"

    def test_no_showdown(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is False
        assert len(parsed.went_to_showdown_players) == 0

    def test_collected_and_uncalled(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["FCSM_1935"] == Decimal("0.19")
        # FCSM_1935 bet 0.10 on flop, silas_tomkyn folded -> 0.10 uncalled
        assert parsed.uncalled_returns["FCSM_1935"] == Decimal("0.10")

    def test_rake(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        # Invested: SB 0.05+0.05=0.10, BB 0.10, flop bet 0.10 = total 0.30
        # Uncalled: 0.10, Collected: 0.19, Rake: 0.30 - 0.10 - 0.19 = 0.01
        assert parsed.total_rake == Decimal("0.01")

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
        # FCSM_1935 (SB) called — VPIP but not PFR
        assert stats["FCSM_1935"]["vpip"] is True
        assert stats["FCSM_1935"]["pfr"] is False
        # silas_tomkyn (BB) checked — no VPIP
        assert stats["silas_tomkyn"]["vpip"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "349736402"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 3
        assert row[1] == "$0.05/$0.10"

        # Verify player count
        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 2


class TestRealAllinShowdown:
    """Test against real 888poker hand: allin_showdown.txt — 5-player, all-in on river."""

    def test_parse_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "349444554"
        assert parsed.site_id == 3
        assert parsed.sb_amount == Decimal("0.50")
        assert parsed.bb_amount == Decimal("1")
        assert parsed.table_name == "Valledupar"
        assert parsed.table_size == 6
        assert parsed.button_seat == 6
        assert len(parsed.seats) == 5

    def test_blinds(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.sb_player == "zvony_tango7"
        # First BB poster is the bb_player
        assert parsed.bb_player is not None

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["4h", "Kc", "3s"]
        assert parsed.board_cards["turn"] == ["Kh"]
        assert parsed.board_cards["river"] == ["6c"]

    def test_showdown(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "qprcuz" in parsed.went_to_showdown_players
        assert "kiss014" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["qprcuz"] == ("3d", "3c")
        assert parsed.hero_cards["kiss014"] == ("5h", "2h")

    def test_collected(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["qprcuz"] == Decimal("197.50")

    def test_river_actions(self):
        """kiss014 bets, qprcuz raises all-in, kiss014 calls all-in."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        river = parsed.actions_by_street["river"]
        assert len(river) == 3
        assert river[0]["action"] == "bet"
        assert river[0]["username"] == "kiss014"
        assert river[0]["amount"] == Decimal("6.55")
        assert river[1]["action"] == "raise"
        assert river[1]["username"] == "qprcuz"
        assert river[1]["amount"] == Decimal("101.66")
        assert river[2]["action"] == "call"
        assert river[2]["username"] == "kiss014"
        assert river[2]["amount"] == Decimal("89.83")

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.02)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # qprcuz called preflop — VPIP but not PFR
        assert stats["qprcuz"]["vpip"] is True
        assert stats["qprcuz"]["pfr"] is False
        # qprcuz and kiss014 went to showdown
        assert stats["qprcuz"]["went_to_showdown"] is True
        assert stats["kiss014"]["went_to_showdown"] is True
        # qprcuz won at showdown
        assert stats["qprcuz"]["won_at_showdown"] is True
        assert stats["kiss014"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "349444554"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 3
        assert row[1] == "$0.50/$1"

        # Verify player count
        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 5

        # qprcuz won: collected 197.50, invested 105.28 -> net 92.22
        won = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'qprcuz'",
            [hand_id]
        ).fetchone()[0]
        assert float(won) == pytest.approx(92.22, abs=0.01)

        # kiss014 lost full stack
        won_kiss = db.execute(
            "SELECT hp.won FROM hand_players hp JOIN players p ON hp.player_id = p.id WHERE hp.hand_id = ? AND p.username = 'kiss014'",
            [hand_id]
        ).fetchone()[0]
        assert float(won_kiss) == pytest.approx(-100.0, abs=0.01)
