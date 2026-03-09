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
REAL_FIXTURES = FIXTURES / "real"


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


# ─── Real PokerStars Fixtures ─────────────────────────────────────────────────


class TestRealDetection:
    """Verify detection works on real PokerStars hand histories."""

    def test_detect_real_general(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_real_allin(self):
        sample = open(REAL_FIXTURES / "allin_showdown.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_real_eur(self):
        sample = open(REAL_FIXTURES / "sidepot_eur.txt").read()[:500]
        assert detect(sample) is True

    def test_detect_parser_routes_real(self):
        sample = open(REAL_FIXTURES / "general.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "PS"

    def test_detect_parser_routes_eur(self):
        sample = open(REAL_FIXTURES / "sidepot_eur.txt").read()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == "PS"


class TestRealSplitting:
    """Verify splitting and ID extraction on real fixtures."""

    def test_split_multi_hand_real(self):
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 10

    def test_extract_hand_id_real(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        hid = extract_hand_id(text)
        assert hid == "109681313810"

    def test_extract_hand_id_eur(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        hid = extract_hand_id(text)
        assert hid == "85998509763"


class TestRealGeneral:
    """Test real PokerStars hand: general.txt — 6-max ante hand, no showdown."""

    def test_parse_general(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "109681313810"
        assert parsed.site_id == 2
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Skat III 100-250 bb, Ante"
        assert parsed.table_size == 6
        assert parsed.button_seat == 4
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Nightfox82"
        assert parsed.bb_player == "Asaki1"

    def test_ante_actions(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        antes = [a for a in preflop if a["action"] == "ante"]
        assert len(antes) == 6
        assert all(a["amount"] == Decimal("0.02") for a in antes)

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["Qh", "Jc", "3h"]
        assert parsed.board_cards["turn"] == []
        assert parsed.board_cards["river"] == []

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["LovID"] == Decimal("1.21")
        assert parsed.total_rake == Decimal("0.06")

    def test_uncalled_bet(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.uncalled_returns["LovID"] == Decimal("0.95")

    def test_no_showdown(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is False
        assert len(parsed.went_to_showdown_players) == 0

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.01)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # LovID raised preflop
        assert stats["LovID"]["vpip"] is True
        assert stats["LovID"]["pfr"] is True
        # Player_L called (limped then called raise)
        assert stats["Player_L"]["vpip"] is True
        assert stats["Player_L"]["pfr"] is False
        # Nightfox82 folded
        assert stats["Nightfox82"]["vpip"] is False
        assert stats["Nightfox82"]["pfr"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "general.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "109681313810"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 2
        assert row[1] == "$0.05/$0.10"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 6


class TestRealAllinShowdown:
    """Test real PokerStars hand: allin_showdown.txt — all-in showdown with antes."""

    def test_parse_allin(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "109688230087"
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert len(parsed.seats) == 5
        assert parsed.button_seat == 3
        assert parsed.sb_player == "numbush"
        assert parsed.bb_player == "DonKingKong"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["5c", "4c", "4h"]
        assert parsed.board_cards["turn"] == ["Qs"]
        assert parsed.board_cards["river"] == ["Kc"]

    def test_allin_action(self):
        """matze1987 raises all-in on the flop."""
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        flop = parsed.actions_by_street["flop"]
        allin_actions = [a for a in flop if a["is_all_in"]]
        assert len(allin_actions) == 1
        assert allin_actions[0]["username"] == "matze1987"
        assert allin_actions[0]["action"] == "raise"

    def test_showdown(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "numbush" in parsed.went_to_showdown_players
        assert "matze1987" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["numbush"] == ("Ah", "Ks")
        assert parsed.hero_cards["matze1987"] == ("8h", "8c")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["numbush"] == Decimal("23.57")
        assert parsed.total_rake == Decimal("1.11")

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.01)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # Both matze1987 and numbush raised preflop
        assert stats["matze1987"]["vpip"] is True
        assert stats["matze1987"]["pfr"] is True
        assert stats["numbush"]["vpip"] is True
        assert stats["numbush"]["pfr"] is True
        # Both went to showdown
        assert stats["matze1987"]["went_to_showdown"] is True
        assert stats["numbush"]["went_to_showdown"] is True
        # numbush won
        assert stats["numbush"]["won_at_showdown"] is True
        assert stats["matze1987"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "allin_showdown.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "109688230087"

        row = db.execute("SELECT site_id FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 2

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 5


class TestRealBasic:
    """Test real PokerStars hand: basic.txt — 6-max with antes and showdown."""

    def test_parse_basic_real(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "109681344065"
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert len(parsed.seats) == 6
        assert parsed.button_seat == 6
        assert parsed.sb_player == "Player_L"
        assert parsed.bb_player == "H6U5r"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["Th", "Kh", "Ac"]
        assert parsed.board_cards["turn"] == ["9d"]
        assert parsed.board_cards["river"] == ["8h"]

    def test_showdown(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "H6U5r" in parsed.went_to_showdown_players
        assert "Nightfox82" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["H6U5r"] == ("Js", "Jd")
        assert parsed.hero_cards["Nightfox82"] == ("Ad", "7d")

    def test_collected_and_rake(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["Nightfox82"] == Decimal("1.81")
        assert parsed.total_rake == Decimal("0.08")

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.01)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # Nightfox82 raised preflop
        assert stats["Nightfox82"]["vpip"] is True
        assert stats["Nightfox82"]["pfr"] is True
        # H6U5r called
        assert stats["H6U5r"]["vpip"] is True
        assert stats["H6U5r"]["pfr"] is False
        # Both went to showdown
        assert stats["Nightfox82"]["went_to_showdown"] is True
        assert stats["H6U5r"]["went_to_showdown"] is True
        # Nightfox82 won
        assert stats["Nightfox82"]["won_at_showdown"] is True
        assert stats["H6U5r"]["won_at_showdown"] is False

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "basic.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "109681344065"

        row = db.execute("SELECT site_id FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 2

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 6


class TestRealMultiHand:
    """Test real PokerStars hands: multi_hand.txt — 10 hands from 9-max table."""

    def test_split_count(self):
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        assert len(hands) == 10

    def test_all_hands_parse(self):
        """Every hand in the file should parse without errors."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        for i, h in enumerate(hands):
            parsed = parse_hand_history(h)
            assert parsed.hand_id is not None, f"Hand {i} has no hand_id"
            assert len(parsed.seats) >= 2, f"Hand {i} has fewer than 2 seats"

    def test_all_hands_financials_balance(self):
        """Every hand should have balanced financials."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        for i, h in enumerate(hands):
            parsed = parse_hand_history(h)
            player_invested, _ = _compute_financials(parsed)
            total_invested = sum(player_invested.values())
            total_uncalled = sum(parsed.uncalled_returns.values())
            total_collected = sum(parsed.collected.values())
            balance = total_invested - total_uncalled - total_collected - parsed.total_rake
            assert float(balance) == pytest.approx(0.0, abs=0.01), (
                f"Hand {i} ({parsed.hand_id}) balance off: {float(balance)}"
            )

    def test_first_hand_preflop_fold(self):
        """First hand: ADZ124 raises, everyone folds, no showdown."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[0])
        assert parsed.hand_id == "109673992001"
        assert parsed.sb_amount == Decimal("5")
        assert parsed.bb_amount == Decimal("10")
        assert parsed.table_size == 9
        assert len(parsed.seats) == 7
        assert parsed.in_showdown is False
        assert parsed.uncalled_returns["ADZ124"] == Decimal("16")
        assert parsed.collected["ADZ124"] == Decimal("25")
        assert parsed.total_rake == Decimal("0")

    def test_second_hand_showdown_with_muck(self):
        """Second hand: ValueH shows, BoomDoon mucks."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[1])
        assert parsed.hand_id == "109674128046"
        assert parsed.in_showdown is True
        assert "ValueH" in parsed.went_to_showdown_players
        # BoomDoon mucked — not in went_to_showdown_players
        assert "BoomDoon" not in parsed.went_to_showdown_players
        assert parsed.collected["ValueH"] == Decimal("357")
        assert parsed.total_rake == Decimal("3")
        assert parsed.board_cards["flop"] == ["Qs", "8h", "7d"]
        assert parsed.board_cards["turn"] == ["9d"]
        assert parsed.board_cards["river"] == ["2c"]

    def test_hand_with_leaves_table(self):
        """Hand 6 (109673572373): EASSA leaves the table mid-hand."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[6])
        assert parsed.hand_id == "109673572373"
        assert parsed.collected["jimmyhoo"] == Decimal("172")
        assert parsed.total_rake == Decimal("3")

    def test_hand_with_joins_table(self):
        """Hand 7 (109673589735): friendzdrt joins the table mid-hand."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        parsed = parse_hand_history(hands[7])
        assert parsed.hand_id == "109673589735"
        assert parsed.collected["filushh"] == Decimal("25")

    def test_all_hands_db_insert(self, db):
        """All 10 hands should insert into DB without errors."""
        content = open(REAL_FIXTURES / "multi_hand.txt").read()
        hands = split_hands(content)
        for i, h in enumerate(hands):
            parsed = parse_hand_history(h)
            hand_id = insert_parsed_hand(db, parsed)
            assert hand_id is not None, f"Hand {i} failed to insert"

        # Verify total hand count
        count = db.execute("SELECT COUNT(*) FROM hands WHERE site_id = 2").fetchone()[0]
        assert count == 10


class TestRealSidepotEur:
    """Test real PokerStars hand: sidepot_eur.txt — EUR currency with side pots."""

    def test_parse_eur(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hand_id == "85998509763"
        assert parsed.site_id == 2
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Rarahu IV Fast,40-100 bb"
        assert parsed.table_size == 9
        assert parsed.button_seat == 9
        assert len(parsed.seats) == 8
        assert parsed.sb_player == "mofdis"
        assert parsed.bb_player == "metra1977"

    def test_board_cards(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["8s", "Qh", "Ks"]
        assert parsed.board_cards["turn"] == ["9s"]
        assert parsed.board_cards["river"] == ["Tc"]

    def test_showdown_players(self):
        """All 4 players who showed cards should be in went_to_showdown."""
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.in_showdown is True
        assert "templargio" in parsed.went_to_showdown_players
        assert "mofdis" in parsed.went_to_showdown_players
        assert "Lenorina" in parsed.went_to_showdown_players
        assert "CrSilva.11" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.hero_cards["templargio"] == ("9d", "Jd")
        assert parsed.hero_cards["mofdis"] == ("As", "Kd")
        assert parsed.hero_cards["CrSilva.11"] == ("Jh", "Ad")
        assert parsed.hero_cards["Lenorina"] == ("Qc", "Qd")

    def test_side_pots_collected(self):
        """CrSilva.11 wins main pot, templargio wins side pots."""
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.collected["CrSilva.11"] == Decimal("5.37")
        assert parsed.collected["templargio"] == Decimal("13.58")

    def test_uncalled_bet(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.uncalled_returns["templargio"] == Decimal("9.69")

    def test_rake(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        assert parsed.total_rake == Decimal("0.89")

    def test_allin_actions(self):
        """CrSilva.11 all-in preflop, Lenorina all-in on flop, mofdis all-in on river."""
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        preflop_allin = [a for a in parsed.actions_by_street["preflop"] if a["is_all_in"]]
        assert len(preflop_allin) == 1
        assert preflop_allin[0]["username"] == "CrSilva.11"
        flop_allin = [a for a in parsed.actions_by_street["flop"] if a["is_all_in"]]
        assert len(flop_allin) == 1
        assert flop_allin[0]["username"] == "Lenorina"
        river_allin = [a for a in parsed.actions_by_street["river"] if a["is_all_in"]]
        assert len(river_allin) == 1
        assert river_allin[0]["username"] == "mofdis"

    def test_financials_balance(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        player_invested, _ = _compute_financials(parsed)

        total_invested = sum(player_invested.values())
        total_uncalled = sum(parsed.uncalled_returns.values())
        total_collected = sum(parsed.collected.values())
        balance = total_invested - total_uncalled - total_collected - parsed.total_rake
        assert float(balance) == pytest.approx(0.0, abs=0.01)

    def test_stat_flags(self):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        # CrSilva.11 raised preflop (initial raiser)
        assert stats["CrSilva.11"]["vpip"] is True
        assert stats["CrSilva.11"]["pfr"] is True
        # templargio called — VPIP but not PFR
        assert stats["templargio"]["vpip"] is True
        assert stats["templargio"]["pfr"] is False
        # metra1977 folded
        assert stats["metra1977"]["vpip"] is False
        assert stats["metra1977"]["pfr"] is False
        # CrSilva.11 won at showdown (main pot)
        assert stats["CrSilva.11"]["won_at_showdown"] is True

    def test_db_insert(self, db):
        text = open(REAL_FIXTURES / "sidepot_eur.txt").read()
        parsed = parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "85998509763"

        row = db.execute("SELECT site_id, stakes FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == 2
        assert row[1] == "$0.05/$0.10"

        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 8
