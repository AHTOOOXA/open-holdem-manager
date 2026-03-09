"""Unified tests for all non-GGPoker site parsers.

Tier 1: Parametrized bulk tests across all sites (detect, split, parse, financials).
Tier 2: Per-site detailed assertions on real hand histories.
"""

import pytest
from decimal import Decimal
from pathlib import Path

from app.parsers import (
    detect_parser,
    pokerstars, poker888, wpn, winamax, ipoker, partypoker,
)
from app.api.import_hands import insert_parsed_hand, _compute_financials
from app.stat_flags import compute_stat_flags

FIXTURES = Path(__file__).parent / "fixtures"

# ─── Site registry for parametrized tests ────────────────────────────────────

SITES = {
    "PS": {
        "module": pokerstars,
        "dir": FIXTURES / "pokerstars",
        "site_id": 2,
        "basic_hand_id": "RC234567890",
        "multi_count": 2,
    },
    "888": {
        "module": poker888,
        "dir": FIXTURES / "poker888",
        "site_id": 3,
        "basic_hand_id": "1234567890",
        "multi_count": 2,
    },
    "WPN": {
        "module": wpn,
        "dir": FIXTURES / "wpn",
        "site_id": 4,
        "basic_hand_id": "987654321",
        "multi_count": 2,
    },
    "WMX": {
        "module": winamax,
        "dir": FIXTURES / "winamax",
        "site_id": 5,
        "basic_hand_id": "1234-5678-9012",
        "multi_count": 2,
    },
    "IP": {
        "module": ipoker,
        "dir": FIXTURES / "ipoker",
        "site_id": 6,
        "basic_hand_id": "9876543210",
        "multi_count": 2,
    },
    "PP": {
        "module": partypoker,
        "dir": FIXTURES / "partypoker",
        "site_id": 7,
        "basic_hand_id": "111222333",
        "multi_count": 2,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1: Parametrized tests across all sites
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("code", SITES.keys())
class TestDetection:
    def test_detect_own(self, code):
        cfg = SITES[code]
        sample = (cfg["dir"] / "basic.txt").read_text()[:500]
        assert cfg["module"].detect(sample) is True

    def test_detect_parser_routes(self, code):
        cfg = SITES[code]
        sample = (cfg["dir"] / "basic.txt").read_text()[:500]
        parser = detect_parser(sample)
        assert parser is not None
        assert parser.SITE_CODE == code


@pytest.mark.parametrize("code", SITES.keys())
class TestSplitting:
    def test_split_multi_hand(self, code):
        cfg = SITES[code]
        content = (cfg["dir"] / "multi_hand.txt").read_text()
        hands = cfg["module"].split_hands(content)
        assert len(hands) == cfg["multi_count"]

    def test_extract_hand_id(self, code):
        cfg = SITES[code]
        text = (cfg["dir"] / "basic.txt").read_text()
        hid = cfg["module"].extract_hand_id(text)
        assert hid == cfg["basic_hand_id"]


@pytest.mark.parametrize("code", SITES.keys())
class TestBasicParse:
    def test_parse_basic(self, code):
        cfg = SITES[code]
        text = (cfg["dir"] / "basic.txt").read_text()
        parsed = cfg["module"].parse_hand_history(text)
        assert parsed.hand_id == cfg["basic_hand_id"]
        assert parsed.site_id == cfg["site_id"]
        assert len(parsed.seats) >= 2

    def test_financials_balance(self, code):
        cfg = SITES[code]
        text = (cfg["dir"] / "basic.txt").read_text()
        parsed = cfg["module"].parse_hand_history(text)
        _assert_financials_balance(parsed)

    def test_stat_flags(self, code):
        cfg = SITES[code]
        text = (cfg["dir"] / "basic.txt").read_text()
        parsed = cfg["module"].parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        assert len(stats) == len(parsed.seats)

    def test_db_insert(self, db, code):
        cfg = SITES[code]
        text = (cfg["dir"] / "basic.txt").read_text()
        parsed = cfg["module"].parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == cfg["basic_hand_id"]
        row = db.execute("SELECT site_id FROM hands WHERE id = ?", [hand_id]).fetchone()
        assert row[0] == cfg["site_id"]


# ─── Bulk parse: every fixture file for every site ───────────────────────────

def _collect_all_fixtures():
    """Collect (site_code, fixture_path) for every .txt in every site dir."""
    items = []
    for code, cfg in SITES.items():
        site_dir = cfg["dir"]
        for f in sorted(site_dir.glob("*.txt")):
            items.append((code, f))
    return items

ALL_FIXTURES = _collect_all_fixtures()


@pytest.mark.parametrize(
    "code,fpath",
    ALL_FIXTURES,
    ids=[f"{code}-{f.name}" for code, f in ALL_FIXTURES],
)
class TestBulkParse:
    def test_parse_all_hands(self, code, fpath):
        """Every hand in every fixture file should parse without error."""
        cfg = SITES[code]
        content = fpath.read_text(errors="replace")
        hands = cfg["module"].split_hands(content)
        assert len(hands) >= 1, f"split returned 0 hands for {fpath.name}"
        for hand_text in hands:
            parsed = cfg["module"].parse_hand_history(hand_text)
            assert parsed.hand_id is not None
            assert len(parsed.seats) >= 2

    def test_stat_flags_all(self, code, fpath):
        """Every hand should produce valid stat flags."""
        cfg = SITES[code]
        content = fpath.read_text(errors="replace")
        hands = cfg["module"].split_hands(content)
        for hand_text in hands:
            parsed = cfg["module"].parse_hand_history(hand_text)
            stats = compute_stat_flags(parsed)
            assert len(stats) == len(parsed.seats)


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2: Per-site detailed assertions on real hand histories
# ═══════════════════════════════════════════════════════════════════════════════


# ─── PokerStars ──────────────────────────────────────────────────────────────

class TestPokerStarsZoom:
    def test_zoom_game_mode(self):
        text = (FIXTURES / "pokerstars" / "zoom.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.game_mode == "Fast Fold"
        assert parsed.hand_id == "RC345678901"

    def test_zoom_uncalled_bet(self):
        text = (FIXTURES / "pokerstars" / "zoom.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert "Player1" in parsed.uncalled_returns
        assert parsed.uncalled_returns["Player1"] == Decimal("7.50")


class TestPokerStarsRealGeneral:
    """Real PS hand: 6-max ante, no showdown."""

    def test_parse(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.hand_id == "109681313810"
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_name == "Skat III 100-250 bb, Ante"
        assert parsed.table_size == 6
        assert len(parsed.seats) == 6
        assert parsed.sb_player == "Nightfox82"
        assert parsed.bb_player == "Asaki1"

    def test_antes(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        antes = [a for a in parsed.actions_by_street["preflop"] if a["action"] == "ante"]
        assert len(antes) == 6
        assert all(a["amount"] == Decimal("0.02") for a in antes)

    def test_board_cards(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.board_cards["flop"] == ["Qh", "Jc", "3h"]
        assert parsed.board_cards["turn"] == []

    def test_collected_and_rake(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.collected["LovID"] == Decimal("1.21")
        assert parsed.total_rake == Decimal("0.06")

    def test_no_showdown(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.in_showdown is False

    def test_stat_flags(self):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        stats = compute_stat_flags(parsed)
        assert stats["LovID"]["vpip"] is True
        assert stats["LovID"]["pfr"] is True
        assert stats["Nightfox82"]["vpip"] is False

    def test_db_insert(self, db):
        text = (FIXTURES / "pokerstars" / "real_general.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        hand_id = insert_parsed_hand(db, parsed)
        assert hand_id == "109681313810"
        count = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
        assert count == 6


class TestPokerStarsRealAllin:
    """Real PS hand: all-in showdown with antes."""

    def test_parse(self):
        text = (FIXTURES / "pokerstars" / "real_allin_showdown.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.hand_id == "109688230087"
        assert len(parsed.seats) == 5
        assert parsed.in_showdown is True
        assert "numbush" in parsed.went_to_showdown_players

    def test_shown_cards(self):
        text = (FIXTURES / "pokerstars" / "real_allin_showdown.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.hero_cards["numbush"] == ("Ah", "Ks")
        assert parsed.hero_cards["matze1987"] == ("8h", "8c")

    def test_collected_and_rake(self):
        text = (FIXTURES / "pokerstars" / "real_allin_showdown.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.collected["numbush"] == Decimal("23.57")
        assert parsed.total_rake == Decimal("1.11")


class TestPokerStarsRealMultiHand:
    """Real PS: 10-hand file."""

    def test_split_count(self):
        content = (FIXTURES / "pokerstars" / "real_multi_hand.txt").read_text()
        assert len(pokerstars.split_hands(content)) == 10

    def test_all_hands_parse_and_balance(self):
        content = (FIXTURES / "pokerstars" / "real_multi_hand.txt").read_text()
        for h in pokerstars.split_hands(content):
            parsed = pokerstars.parse_hand_history(h)
            _assert_financials_balance(parsed)

    def test_all_hands_db_insert(self, db):
        content = (FIXTURES / "pokerstars" / "real_multi_hand.txt").read_text()
        for h in pokerstars.split_hands(content):
            parsed = pokerstars.parse_hand_history(h)
            insert_parsed_hand(db, parsed)
        count = db.execute("SELECT COUNT(*) FROM hands WHERE site_id = 2").fetchone()[0]
        assert count == 10


class TestPokerStarsRealSidepotEur:
    """Real PS: EUR currency with side pots."""

    def test_parse(self):
        text = (FIXTURES / "pokerstars" / "real_sidepot_eur.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.hand_id == "85998509763"
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.table_size == 9
        assert len(parsed.seats) == 8

    def test_side_pots(self):
        text = (FIXTURES / "pokerstars" / "real_sidepot_eur.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.collected["CrSilva.11"] == Decimal("5.37")
        assert parsed.collected["templargio"] == Decimal("13.58")
        assert parsed.total_rake == Decimal("0.89")

    def test_showdown_players(self):
        text = (FIXTURES / "pokerstars" / "real_sidepot_eur.txt").read_text()
        parsed = pokerstars.parse_hand_history(text)
        assert parsed.in_showdown is True
        for p in ["templargio", "mofdis", "Lenorina", "CrSilva.11"]:
            assert p in parsed.went_to_showdown_players


# ─── 888poker ────────────────────────────────────────────────────────────────

class TestPoker888RealGeneral:
    """Real 888 hand: heads-up, no showdown."""

    def test_parse(self):
        text = (FIXTURES / "poker888" / "real_general.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        assert parsed.hand_id == "349736402"
        assert parsed.site_id == 3
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert len(parsed.seats) == 2

    def test_collected_and_rake(self):
        text = (FIXTURES / "poker888" / "real_general.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        assert parsed.collected["FCSM_1935"] == Decimal("0.19")
        assert parsed.total_rake == Decimal("0.01")

    def test_no_showdown(self):
        text = (FIXTURES / "poker888" / "real_general.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        assert parsed.in_showdown is False


class TestPoker888RealAllin:
    """Real 888 hand: multiway all-in showdown."""

    def test_parse(self):
        text = (FIXTURES / "poker888" / "real_allin_showdown.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        assert parsed.hand_id == "349444554"
        assert parsed.in_showdown is True
        assert len(parsed.seats) == 5

    def test_collected(self):
        text = (FIXTURES / "poker888" / "real_allin_showdown.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        assert parsed.collected["qprcuz"] == Decimal("197.50")

    def test_river_actions(self):
        text = (FIXTURES / "poker888" / "real_allin_showdown.txt").read_text()
        parsed = poker888.parse_hand_history(text)
        river = parsed.actions_by_street["river"]
        assert len(river) >= 3  # bet, raise, call


# ─── WPN ─────────────────────────────────────────────────────────────────────

class TestWpnRealGeneral:
    """Real WPN hand: 6-max with showdown."""

    def test_parse(self):
        text = (FIXTURES / "wpn" / "real_general.txt").read_text()
        parsed = wpn.parse_hand_history(text)
        assert parsed.hand_id == "261641541"
        assert parsed.site_id == 4
        assert parsed.sb_amount == Decimal("0.10")
        assert parsed.bb_amount == Decimal("0.25")

    def test_collected(self):
        text = (FIXTURES / "wpn" / "real_general.txt").read_text()
        parsed = wpn.parse_hand_history(text)
        assert parsed.collected["johna52801"] == Decimal("7.73")


class TestWpnRealStraddle:
    """Real WPN hand: straddle action."""

    def test_straddle_action(self):
        text = (FIXTURES / "wpn" / "real_straddle.txt").read_text()
        parsed = wpn.parse_hand_history(text)
        assert parsed.hand_id == "266899075"
        preflop = parsed.actions_by_street["preflop"]
        straddles = [a for a in preflop if a["action"] == "straddle"]
        assert len(straddles) == 1
        assert straddles[0]["amount"] == Decimal("0.50")

    def test_straddle_financials(self):
        text = (FIXTURES / "wpn" / "real_straddle.txt").read_text()
        parsed = wpn.parse_hand_history(text)
        _assert_financials_balance(parsed)


class TestWpnRealAllin:
    """Real WPN hand: heads-up all-in."""

    def test_parse(self):
        text = (FIXTURES / "wpn" / "real_allin_showdown.txt").read_text()
        parsed = wpn.parse_hand_history(text)
        assert parsed.hand_id == "261402183"
        assert parsed.in_showdown is True


# ─── Winamax ─────────────────────────────────────────────────────────────────

class TestWinamaxRealGeneral:
    """Real Winamax hand: heads-up, EUR currency."""

    def test_parse(self):
        text = (FIXTURES / "winamax" / "real_general.txt").read_text()
        parsed = winamax.parse_hand_history(text)
        assert parsed.hand_id == "5281577-471-1382586707"
        assert parsed.site_id == 5
        assert parsed.sb_amount == Decimal("0.50")
        assert parsed.bb_amount == Decimal("1")
        assert len(parsed.seats) == 2

    def test_3bet(self):
        text = (FIXTURES / "winamax" / "real_general.txt").read_text()
        parsed = winamax.parse_hand_history(text)
        preflop = parsed.actions_by_street["preflop"]
        raises = [a for a in preflop if a["action"] == "raise"]
        assert len(raises) >= 2  # raise + re-raise

    def test_collected(self):
        text = (FIXTURES / "winamax" / "real_general.txt").read_text()
        parsed = winamax.parse_hand_history(text)
        assert parsed.collected["titi63000"] == Decimal("14.02")


class TestWinamaxRealAllin:
    """Real Winamax hand: 5-max all-in showdown."""

    def test_parse(self):
        text = (FIXTURES / "winamax" / "real_allin_showdown.txt").read_text()
        parsed = winamax.parse_hand_history(text)
        assert parsed.hand_id == "5343878-96-1383820687"
        assert parsed.in_showdown is True

    def test_collected(self):
        text = (FIXTURES / "winamax" / "real_allin_showdown.txt").read_text()
        parsed = winamax.parse_hand_history(text)
        assert parsed.collected["nico86190"] == Decimal("43.45")


# ─── iPoker ──────────────────────────────────────────────────────────────────

class TestIPokerCardConversion:
    """iPoker XML uses unique card encoding (HA=Ah, DK=Kd, H10=Th)."""

    def test_convert_cards(self):
        from app.parsers.ipoker import _convert_card
        assert _convert_card("HA") == "Ah"
        assert _convert_card("DK") == "Kd"
        assert _convert_card("S7") == "7s"
        assert _convert_card("CQ") == "Qc"
        assert _convert_card("H10") == "Th"
        assert _convert_card("SA") == "As"
        assert _convert_card("CT") == "Tc"
        assert _convert_card("DJ") == "Jd"


class TestIPokerRealGeneral:
    """Real iPoker hand: limit hold'em, fold preflop."""

    def test_parse(self):
        text = (FIXTURES / "ipoker" / "real_general.txt").read_text()
        parsed = ipoker.parse_hand_history(text)
        assert parsed.hand_id == "5383708755"
        assert parsed.site_id == 6

    def test_collected(self):
        text = (FIXTURES / "ipoker" / "real_general.txt").read_text()
        parsed = ipoker.parse_hand_history(text)
        assert parsed.collected["d0dge"] == Decimal("7.50")
        assert parsed.in_showdown is False


class TestIPokerRealAllin:
    """Real iPoker hand: NL hold'em, all-in, EUR currency."""

    def test_parse(self):
        text = (FIXTURES / "ipoker" / "real_allin_showdown.txt").read_text()
        parsed = ipoker.parse_hand_history(text)
        assert parsed.hand_id == "5385476176"
        assert parsed.site_id == 6

    def test_collected(self):
        text = (FIXTURES / "ipoker" / "real_allin_showdown.txt").read_text()
        parsed = ipoker.parse_hand_history(text)
        assert parsed.collected["Amalfitano1"] == Decimal("17.55")
        assert parsed.collected["Taras2107"] == Decimal("3.18")


# ─── PartyPoker ──────────────────────────────────────────────────────────────

class TestPartyPokerRealGeneral:
    """Real PP hand: 9-max limped pot, no showdown."""

    def test_parse(self):
        text = (FIXTURES / "partypoker" / "real_general.txt").read_text()
        parsed = partypoker.parse_hand_history(text)
        assert parsed.hand_id == "13550319286"
        assert parsed.site_id == 7
        assert parsed.sb_amount == Decimal("0.05")
        assert parsed.bb_amount == Decimal("0.10")
        assert parsed.in_showdown is False

    def test_collected(self):
        text = (FIXTURES / "partypoker" / "real_general.txt").read_text()
        parsed = partypoker.parse_hand_history(text)
        assert parsed.collected["lenstr1"] == Decimal("0.53")

    def test_date_parsing(self):
        text = (FIXTURES / "partypoker" / "real_general.txt").read_text()
        parsed = partypoker.parse_hand_history(text)
        assert parsed.played_at.year == 2014
        assert parsed.played_at.month == 1
        assert parsed.played_at.day == 6


class TestPartyPokerRealAllin:
    """Real PP hand: multiway all-in with side pot, BOM in file."""

    def test_parse(self):
        text = (FIXTURES / "partypoker" / "real_allin_showdown.txt").read_text()
        parsed = partypoker.parse_hand_history(text)
        assert parsed.hand_id == "13549932236"
        assert parsed.in_showdown is True

    def test_side_pot(self):
        text = (FIXTURES / "partypoker" / "real_allin_showdown.txt").read_text()
        parsed = partypoker.parse_hand_history(text)
        assert parsed.collected["dr. spaz"] == Decimal("22.53")

    def test_detection_not_888(self):
        """PartyPoker detection must not trigger on 888poker hands."""
        sample_888 = "***** 888poker Hand History for Game 123 *****"
        assert partypoker.detect(sample_888) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _assert_financials_balance(parsed):
    """Assert that invested - uncalled == collected + rake + jackpot."""
    player_invested, _ = _compute_financials(parsed)
    total_invested = sum(player_invested.values())
    total_uncalled = sum(parsed.uncalled_returns.values())
    total_collected = sum(parsed.collected.values())
    balance = total_invested - total_uncalled - total_collected - parsed.total_rake - parsed.total_jackpot
    assert float(balance) == pytest.approx(0.0, abs=0.01), (
        f"Hand {parsed.hand_id} balance off: {float(balance)}"
    )
