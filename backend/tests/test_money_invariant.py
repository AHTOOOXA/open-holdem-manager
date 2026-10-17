"""Money invariants for GGPoker hands (BUGS-FROM-FORK.md #5, #6).

Per hand, the table as a whole loses the fees and wins the Cash Drop, if any:
sum(won) == cash_drop - fees. The drop counts as winnings for whoever wins the
pot, the same way Hand2Note counts it.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.api.import_hands import _compute_financials, insert_parsed_hand
from app.parsers import ggpoker

FIXTURES = Path(__file__).parent / "fixtures"
_Z = Decimal(0)
_TOTAL_POT = re.compile(r"Total pot \$([0-9.]+)")
_CENT = Decimal("0.011")


def _gg_hands() -> list[str]:
    files = sorted((FIXTURES / "ggpoker").rglob("*.txt")) + [FIXTURES / "bench_sample_20k.txt"]
    hands = []
    for f in files:
        hands += [h.strip() for h in ggpoker.split_hands(f.read_text()) if h.strip()]
    return hands


def _won_by_player(parsed, invested) -> dict[str, Decimal]:
    return {
        u: parsed.collected.get(u, _Z)
        + parsed.uncalled_returns.get(u, _Z) - invested[u]
        for u in invested
    }


def _players_money(parsed, invested) -> Decimal:
    return sum(invested.values(), _Z) - sum(parsed.uncalled_returns.values(), _Z)


def test_sum_won_equals_cash_drop_minus_fees():
    checked = skipped = 0
    violations = []
    for text in _gg_hands():
        parsed = ggpoker.parse_hand_history(text)
        invested, _ = _compute_financials(parsed)
        money_in = _players_money(parsed, invested)
        total_pot = money_in + parsed.cash_drop_received
        m = _TOTAL_POT.search(text)
        paid_out = sum(parsed.collected.values(), _Z) + parsed.fees
        # Skip hands whose own summary doesn't add up (corrupt or hand-written
        # source data); the invariant can't hold for those.
        if (
            not m
            or abs(Decimal(m.group(1)) - total_pot) > _CENT
            or abs(Decimal(m.group(1)) - paid_out) > _CENT
        ):
            skipped += 1
            continue
        checked += 1
        expected = parsed.cash_drop_received - parsed.fees
        won = sum(_won_by_player(parsed, invested).values(), _Z)
        if abs(won - expected) > _CENT:
            violations.append((parsed.hand_id, won, expected))

    assert checked > 19_000
    assert skipped < checked * 0.005, f"{skipped} hands with inconsistent summaries"
    assert violations == []


def test_fees_split_from_rake():
    """#6: rake is rake only; fees include jackpot (and bingo/fortune/tax)."""
    text = (FIXTURES / "ggpoker" / "run_it_twice_same_winner.txt").read_text()
    parsed = ggpoker.parse_hand_history(text)
    assert parsed.total_rake == Decimal("1.50")
    assert parsed.total_jackpot == Decimal("0.25")
    assert parsed.fees == Decimal("1.75")


CASH_DROP_HAND = """Poker Hand #RC4207523328: Hold'em No Limit ($0.05/$0.1) - 2026/01/12 20:22:26
Table 'RushAndCash16888588' 6-max Seat #1 is the button
Seat 1: 58a623f0 ($10 in chips)
Seat 2: Hero ($10.48 in chips)
Seat 3: 48cad6e4 ($10.58 in chips)
Seat 4: 9d35895a ($10.31 in chips)
Seat 5: 3cd50427 ($10.63 in chips)
Seat 6: bb0f447e ($28.47 in chips)
Cash Drop to Pot : total $1
Hero: posts small blind $0.05
48cad6e4: posts big blind $0.1
*** HOLE CARDS ***
Dealt to Hero [7d 4h]
9d35895a: calls $0.1
3cd50427: folds
bb0f447e: calls $0.1
58a623f0: calls $0.1
Hero: calls $0.05
48cad6e4: raises $10.48 to $10.58 and is all-in
9d35895a: folds
bb0f447e: folds
58a623f0: folds
Hero: folds
Uncalled bet ($10.48) returned to 48cad6e4
*** SHOWDOWN ***
48cad6e4 collected $1.43 from pot
*** SUMMARY ***
Total pot $1.5 | Rake $0.07 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0
Seat 1: 58a623f0 (button) folded before Flop
Seat 2: Hero (small blind) folded before Flop
Seat 3: 48cad6e4 (big blind) collected ($1.43)
Seat 4: 9d35895a folded before Flop
Seat 5: 3cd50427 folded before Flop (didn't bet)
Seat 6: bb0f447e folded before Flop"""


def test_cash_drop_counts_as_winnings(db):
    """Like Hand2Note: the pot winner's result includes the $1 Cash Drop."""
    parsed = ggpoker.parse_hand_history(CASH_DROP_HAND)
    assert parsed.cash_drop_received == Decimal("1")
    insert_parsed_hand(db, parsed)
    won = dict(db.execute("""
        SELECT p.username, hp.won FROM hand_players hp JOIN players p ON p.id = hp.player_id
    """).fetchall())
    # Collected $1.43, own $0.10 in
    assert float(won["48cad6e4"]) == pytest.approx(1.33)
    assert float(won["Hero"]) == pytest.approx(-0.10)
    # The table wins the $1 drop and pays $0.07 rake
    assert sum(float(v) for v in won.values()) == pytest.approx(1 - 0.07)


def test_rake_and_jackpot_columns_not_double_counted(db):
    text = (FIXTURES / "ggpoker" / "run_it_twice_same_winner.txt").read_text()
    # The fixture is hand-written: the players put $24.25 in but Hero collects
    # $49.25. Rake is now what the site actually kept (pot - collected, like
    # Hand2Note), so make the amounts add up: $24.25 - $22.50 = $1.75 kept.
    text = (text.replace("$24.62", "$11.25").replace("$24.63", "$11.25")
            .replace("Total pot $49.25", "Total pot $24.25"))
    insert_parsed_hand(db, ggpoker.parse_hand_history(text))
    rake, jackpot = db.execute(
        "SELECT SUM(rake), SUM(jackpot) FROM hand_players"
    ).fetchone()
    assert float(rake) == pytest.approx(1.50)
    assert float(jackpot) == pytest.approx(0.25)


def test_ante_table_parses(db):
    """#8: ante tables use '($SB/$BB($ante))' in the header and 'posts the ante'."""
    parsed = ggpoker.parse_hand_history((FIXTURES / "ggpoker" / "ante_table.txt").read_text())
    assert parsed.bb_amount == Decimal("0.05")
    assert parsed.sb_amount == Decimal("0.02")
    assert parsed.stakes == "$0.02/$0.05"
    antes = [a for a in parsed.actions_by_street["preflop"] if a["action"] == "ante"]
    assert len(antes) == 6
    insert_parsed_hand(db, parsed)
    won = dict(db.execute(
        "SELECT p.username, hp.won FROM hand_players hp JOIN players p ON p.id = hp.player_id"
    ).fetchall())
    # Hero: 0.01 ante + 0.55 in, collected 1.14
    assert float(won["Hero"]) == pytest.approx(0.58)
    assert float(won["Player6"]) == pytest.approx(-0.56)
    assert float(won["Player1"]) == pytest.approx(-0.01)
    assert sum(float(v) for v in won.values()) == pytest.approx(-0.04)


@pytest.mark.parametrize("header, sb, bb, stakes", [
    ("($0.1/$0.25)", "0.1", "0.25", "$0.10/$0.25"),
    ("($0.02/$0.05)", "0.02", "0.05", "$0.02/$0.05"),
    ("($0.05/$0.1)", "0.05", "0.1", "$0.05/$0.10"),
])
def test_small_blind_not_assumed_half_of_bb(header, sb, bb, stakes):
    """#9: $0.10/$0.25 used to come out as SB $0.125 ('$0.12/$0.25')."""
    text = (FIXTURES / "ggpoker" / "ante_table.txt").read_text()
    text = text.replace("($0.02/$0.05($0.01))", header)
    text = text.replace("posts small blind $0.02", f"posts small blind ${sb}")
    text = text.replace("posts big blind $0.05", f"posts big blind ${bb}")
    parsed = ggpoker.parse_hand_history(text)
    assert parsed.sb_amount == Decimal(sb)
    assert parsed.bb_amount == Decimal(bb)
    assert parsed.stakes == stakes
