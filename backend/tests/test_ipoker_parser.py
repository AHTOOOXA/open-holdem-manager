import pytest
import duckdb
from decimal import Decimal
from pathlib import Path

from app.parsers.ipoker import parse_hand_history, detect, split_hands, extract_hand_id, _convert_card
from app.parsers.common import _ZERO
from app.parsers import detect_parser
from app.api.import_hands import insert_parsed_hand, reset_import_cache, _compute_financials
from app.stat_flags import compute_stat_flags
from app.db import init_schema

FIXTURES = Path(__file__).parent / "fixtures" / "ipoker"
REAL_FIXTURES = FIXTURES / "real"


@pytest.fixture
def db():
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()


class TestDetection:
    def test_detect_ipoker(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes(self):
        sample = open(FIXTURES / "basic.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "IP"

    def test_detect_without_xml_decl(self):
        """Real general.txt has no <?xml> declaration but has <session>."""
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_with_xml_decl(self):
        sample = open(REAL_FIXTURES / "allin_showdown.txt").read()[:500]
        assert detect(sample) is True

    def test_reject_text_format(self):
        assert detect("PokerStars Hand #123") is False

    def test_reject_ggpoker(self):
        assert detect("Poker Hand #RC123: Hold'em No Limit") is False

    def test_reject_888poker(self):
        assert detect("***** 888poker Hand History for Game 123 *****") is False


class TestCardConversion:
    def test_ace_hearts(self):
        assert _convert_card("HA") == "Ah"

    def test_king_diamonds(self):
        assert _convert_card("DK") == "Kd"

    def test_seven_clubs(self):
        assert _convert_card("C7") == "7c"

    def test_five_spades(self):
        assert _convert_card("S5") == "5s"

    def test_ten_hearts_legacy(self):
        assert _convert_card("HT") == "Th"

    def test_ten_hearts_real(self):
        """Real iPoker uses H10 for 10 of Hearts."""
        assert _convert_card("H10") == "Th"

    def test_ten_spades_real(self):
        assert _convert_card("S10") == "Ts"

    def test_queen(self):
        assert _convert_card("HQ") == "Qh"


class TestSplitting:
    def test_split_single_hand(self):
        content = open(FIXTURES / "basic.txt").read()
        hands = split_hands(content)
        assert len(hands) == 1

    def test_split_multi_hand(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 2

    def test_extract_hand_id(self):
        text = open(FIXTURES / "basic.txt").read()
        hid = extract_hand_id(text)
        assert hid == "9876543210"

    def test_extract_hand_id_second(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        hid = extract_hand_id(hands[1])
        assert hid == "9876543211"


class TestBasicHand:
    def test_parse_basic(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "9876543210"
        assert parsed.site_id == 6
        assert parsed.game_type == "NLH"
        assert parsed.sb_amount == Decimal("0.25")
        assert parsed.bb_amount == Decimal("0.50")
        assert parsed.table_size == 6
        assert parsed.button_seat == 3
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Player4"
        assert parsed.bb_player == "Player5"

    def test_board_cards(self):
        text = open(FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
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
        # Total invested: 16.25 + 16.25 + 1.50 + 0.25 = 34.25 (from bet attrs)
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
        assert hand_id == "9876543210"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 6
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
        # Uncalled: $1.00, Collected: $1.25 (the blinds minus nothing taken)
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
        assert parsed.hand_id == "9876543211"

    def test_second_hand_hero_cards(self):
        content = open(FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.hero_cards["Player1"] == ("Td", "9d")


class TestRealGeneral:
    """Tests against real iPoker hand history: general.txt (limit hold'em, fold preflop)."""

    def test_parse_real_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "5383708755"
        assert parsed.site_id == 6
        assert parsed.sb_amount == Decimal("5")
        assert parsed.bb_amount == Decimal("10")
        assert parsed.stakes == "$5/$10"

    def test_real_general_players(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        # DropOfRain has chips=0, bet=0, win=0 — should be excluded (sitting out)
        assert parsed.table_size == 2
        usernames = {s["username"] for s in parsed.seats}
        assert "d0dge" in usernames
        assert "SirPaulGB" in usernames
        assert "DropOfRain" not in usernames

    def test_real_general_button(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.button_seat == 6  # SirPaulGB is dealer

    def test_real_general_blinds(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.sb_player == "SirPaulGB"
        assert parsed.bb_player == "d0dge"

    def test_real_general_actions(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        # SB posts, BB posts, SirPaulGB folds
        assert len(preflop) == 3
        assert preflop[0]["action"] == "bb"  # d0dge BB (action no=2 but round 0)
        assert preflop[1]["action"] == "sb"  # SirPaulGB SB (action no=1)
        assert preflop[2]["action"] == "fold"  # SirPaulGB folds

    def test_real_general_collected(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["d0dge"] == Decimal("7.50")

    def test_real_general_no_showdown(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is False

    def test_real_general_financials_balance(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_collected = sum(parsed.collected.values())
        # iPoker XML "win" includes uncalled returns, so collected already covers them
        # invested = collected + rake (rake is 0 for this hand)
        assert float(total_invested) == pytest.approx(float(total_collected + parsed.total_rake), abs=0.02)

    def test_real_general_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "5383708755"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 6
        assert row[1] == "$5/$10"


class TestRealAllinShowdown:
    """Tests against real iPoker hand history: allin_showdown.txt (NL hold'em, all-in preflop)."""

    def test_parse_real_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "5385476176"
        assert parsed.site_id == 6
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.stakes == "$0.05/$0.10"

    def test_real_allin_euro_currency(self):
        """Real file uses euro currency (€) — amounts must parse correctly."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        # Check stacks parsed correctly
        stacks = {s["username"]: s["stack"] for s in parsed.seats}
        assert stacks["Amalfitano1"] == Decimal("19.25")
        assert stacks["Taras2107"] == Decimal("1.70")

    def test_real_allin_players(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.table_size == 2
        assert parsed.button_seat == 3  # Amalfitano1 is dealer

    def test_real_allin_pocket_cards(self):
        """Pocket cards from <cards type="Pocket"> elements."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["Amalfitano1"] == ("9d", "Kc")
        assert parsed.hero_cards["Taras2107"] == ("Js", "Jd")

    def test_real_allin_board_cards(self):
        """Board cards from <cards type="Flop">, <cards type="Turn">, <cards type="River">."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["7d", "Th", "9s"]
        assert parsed.board_cards["turn"] == ["8c"]
        assert parsed.board_cards["river"] == ["Ts"]

    def test_real_allin_preflop_actions(self):
        """Preflop has blinds + raises + type 7 (call all-in)."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        action_types = [a["action"] for a in preflop]
        # SB, BB, raise, raise, raise, call (type 7)
        assert "sb" in action_types
        assert "bb" in action_types
        assert "raise" in action_types
        assert "call" in action_types

    def test_real_allin_type7_is_call(self):
        """Action type 7 should be mapped to 'call'."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        # Taras2107's last action is type 7 (call all-in)
        taras_actions = [a for a in preflop if a["username"] == "Taras2107"]
        assert taras_actions[-1]["action"] == "call"

    def test_real_allin_all_in_detection(self):
        """Both players go all-in preflop."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        # Check Taras2107 is all-in (stack 1.70, total invested 1.70)
        taras_last = [a for a in preflop if a["username"] == "Taras2107"][-1]
        assert taras_last["is_all_in"] is True

    def test_real_allin_collected(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["Amalfitano1"] == Decimal("17.55")
        assert parsed.collected["Taras2107"] == Decimal("3.18")

    def test_real_allin_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)
        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        # invested - uncalled = collected + rake
        assert float(total_invested - total_uncalled) == pytest.approx(
            float(total_collected + parsed.total_rake), abs=0.01
        )

    def test_real_allin_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "5385476176"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 6
        assert row[1] == "$0.05/$0.10"
