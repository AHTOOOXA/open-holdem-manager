"""Money computed like Hand2Note 4.1 (app/money.py): won, rake, all-in EV.

Expected values were produced by Hand2Note itself on the same hand
histories. Real hands come from bench_sample_20k.txt, synthetic ones from
fixtures/money/gg_vectors.txt (edge cases: side pots, chops, cash-outs,
summary/body mismatches). EV rows whose pot is a 3-way preflop all-in use a
tolerance of 1% of that pot: Hand2Note itself uses a Monte Carlo there.
"""

import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest

from app.api.import_hands import insert_parsed_hand
from app.equity import _preflop_table, equities
from app.money import compute_hand_money, rake_columns, round_rake, stored_rake
from app.parsers import ggpoker, pokerstars

FIXTURES = Path(__file__).parent / "fixtures"
D = Decimal


@lru_cache(maxsize=1)
def _gg_hands() -> dict[str, str]:
    hands = {}
    for f in (FIXTURES / "bench_sample_20k.txt", FIXTURES / "money" / "gg_vectors.txt"):
        for h in ggpoker.split_hands(f.read_text()):
            h = h.strip()
            if h:
                hands[re.match(r"Poker Hand #(\w+)", h).group(1)] = h
    return hands


@lru_cache(maxsize=None)
def _money(hand_id: str):
    if hand_id in ("RC345678901", "109715173634"):
        for f in sorted((FIXTURES / "pokerstars").glob("*.txt")):
            for h in pokerstars.split_hands(f.read_text(encoding="utf-8-sig")):
                if f"#{hand_id}:" in h:
                    return compute_hand_money(pokerstars.parse_hand_history(h.strip()))
        raise KeyError(hand_id)
    return compute_hand_money(ggpoker.parse_hand_history(_gg_hands()[hand_id]))


# hand, player, won, rake (in memory), won EV (None = no EV: equals won), EV tolerance
VECTORS = [
    # Cash Drop walk: the drop counts as winnings
    ("RC4256505253", "6ecb896d", "1.00", "0.05", None, 0),
    ("RC4256505253", "963cd288", "-0.05", "0", None, 0),
    # Chop: rake share rounded per player
    ("HD2670729639", "60a6d272", "0.02", "0.01", None, 0),
    ("HD2670729639", "b9d78f4f", "0.01", "0.01", None, 0),
    # Run it three times: rake in proportion to what each collected
    ("RC4241336604", "f0b934c8", "6.26", "0.33", 15.701909, 1e-5),
    ("RC4241336604", "5034a914", "-5.75", "0.16", -15.191909, 1e-5),
    # GG straddle without "posts", run it twice, flop all-in
    ("HD2670805052", "a2f8afb3", "-5.00", "0", -2.788283, 1e-5),
    ("HD2670805052", "5c729a44", "4.52", "0.55", 2.308283, 1e-5),
    # Missed blind = dead small blind; second big blind is live
    ("HD2708836357", "c169d902", "-0.35", "0", None, 0),
    ("HD2708836357", "e3a2f3e", "1.11", "0.09", None, 0),
    ("HD2672121348", "31ae78a1", "-0.12", "0", None, 0),
    ("HD2672121348", "4b289576", "0.23", "0.01", None, 0),
    # Cash-out, pays risk: won from the cash-out amount, rake * ratio
    ("RC4201635724", "7276c47b", "1.04", "0.1127", 0.997559, 1e-5),
    ("RC4201635724", "5ebcd6bd", "-1.26", "0", -1.067559, 1e-5),
    # Cash-out, receives: both players pay rake
    ("HD2672214235", "38580892", "0.95", "0.2561", -0.139101, 1e-5),
    ("HD2672214235", "3ef7a6bc", "3.04", "0.38", -0.190899, 1e-5),
    # Cash-out with a Cash Drop: body "Receives Cashout ($1)" wins over the summary
    ("RC4269074245", "74fb0fd2", "-9.08", "0.0216", 3.980074, 1e-5),
    ("RC4269074245", "26ed5c98", "10.78", "0.45", -3.280074, 1e-5),
    # 3-way preflop all-in, two pots
    ("RC4202977641", "717f5ff0", "-4.02", "0.03", 1.444209, 0.141),
    ("RC4202977641", "ca41a4ed", "-5.67", "0", 0.451519, 0.141),
    ("RC4202977641", "1f6a0fd3", "9.25", "0.41", -2.335728, 0.141),
    # Side pot; the caller who folded later is not a contender
    ("RC4236344755", "ab07fff", "-0.82", "0", -0.448753, 1e-5),
    ("RC4236344755", "e920caf1", "4.17", "0.44", 3.798753, 1e-5),
    ("RC4236344755", "99bccf74", "-3.74", "0", None, 0),
    # 3-way turn all-in, two pots, exact
    ("RC4226292220", "558d50a5", "8.50", "0.44", 4.833052, 1e-5),
    ("RC4226292220", "6e064f76", "-5.86", "0", -4.727338, 1e-5),
    ("RC4226292220", "ea11b6ad", "-3.03", "0", -0.495714, 1e-5),
    # Wrong "Uncalled bet" line: the returned bet is computed from the actions
    ("RC4204787831", "Hero", "2.58", "0.36", None, 0),
    # Summary disagrees with the body: body collected lines win
    ("RC4270971263", "3507c1b6", "0.05", "0", None, 0),
    # Synthetic: side pot, third player folds the river
    ("RC9000000001", "Short", "3.95", "0.20", 0.749763, 1e-5),
    ("RC9000000001", "Big1", "1.90", "0.10", 5.100237, 1e-5),
    ("RC9000000001", "Big2", "-6.00", "0", None, 0),
    # Synthetic: side pot to a river showdown. Big2 loses pot 2 and gets no
    # result for it (H2N quirk), only for the 3-way pot 1.
    ("RC9000000002", "Short", "3.95", "0.20", 0.40, 0.06),
    ("RC9000000002", "Big1", "4.90", "0.10", 7.35, 0.06),
    ("RC9000000002", "Big2", "-9.00", "0", -0.89, 0.06),
    # Synthetic: 3-way, two all-ins at different streets
    ("RC9000000003", "Short", "3.95", "0.20", 0.38, 0.06),
    ("RC9000000003", "Big1", "5.85", "0.15", 4.68, 0.06),
    ("RC9000000003", "Big2", "-10.00", "0", -5.26, 0.06),
    # Synthetic: flop all-in with a Cash Drop in the pot
    ("RC9000000004", "Hero", "8.65", "0.45", -7.730909, 1e-5),
    ("RC9000000004", "Vil", "-8.00", "0", 8.380909, 1e-5),
    # Synthetic: the all-in loser never shows: no EV for anyone
    ("RC9000000005", "Hero", "7.65", "0.45", None, 0),
    ("RC9000000005", "Vil", "-8.00", "0", None, 0),
    # Synthetic: 3-way chop, each rake share rounded up to a cent
    ("RC9000000006", "Hero", "-0.01", "0.02", None, 0),
    ("RC9000000006", "Vil", "-0.02", "0.02", None, 0),
    ("RC9000000006", "BBp", "-0.02", "0.02", None, 0),
    # Synthetic: collected a cent above the total pot, taken from seat 1
    ("RC9100000001", "Hero", "-0.02", "0.02", None, 0),
    ("RC9100000001", "Vil", "-0.02", "0.02", None, 0),
    # Synthetic: collected includes the uncalled bet
    ("RC9100000002", "Hero", "0.15", "0", None, 0),
    ("RC9100000003", "Hero", "0.15", "0", None, 0),
    # Synthetic: second big blind with an unprinted dead small blind
    ("RC9100000004", "Late", "0.15", "0", None, 0),
    ("RC9100000005", "Late", "0.15", "0", None, 0),
    # Synthetic: second small blind is dead money
    ("RC9100000006", "Late", "-0.15", "0", None, 0),
    ("RC9100000006", "BBp", "0.19", "0.01", None, 0),
    # Synthetic: "Pays Cashout Risk ($0)" is a cash-out at ratio 1
    ("RC9200000001", "7276c47b", "1.19", "0.12", 0.997559, 1e-5),
    # Synthetic: "Chooses to EV Cashout" alone is not a cash-out
    ("RC9200000002", "7276c47b", "1.19", "0.12", 0.997559, 1e-5),
    # Synthetic: "Receives Cashout ($0)" is not a cash-out
    ("HD9200000003", "38580892", "-3.37", "0", -0.139101, 1e-5),
    ("HD9200000003", "3ef7a6bc", "3.04", "0.38", -0.190899, 1e-5),
    # Synthetic: cash-out, the winner's cards unknown: no EV, and a cash-out
    # player then gets EV 0 (not his winnings)
    ("HD9200000004", "38580892", "0.95", "0.2561", 0.0, 1e-9),
    ("HD9200000004", "3ef7a6bc", "3.04", "0.38", None, 0),
    # Synthetic: multi-pot cash-out, the cash-out player wins both pots
    ("RC9300000001", "Mid", "5.25", "0.2383", 3.44, 0.03),
    ("RC9300000001", "Big", "-5.00", "0", -3.14, 0.03),
    ("RC9300000001", "Short", "-1.00", "0", -0.55, 0.03),
    # Synthetic: multi-pot cash-out, the cash-out player loses
    ("RC9300000002", "Big", "5.75", "0.25", -3.13, 0.03),
    ("RC9300000002", "Mid", "1.50", "0.1511", 3.43, 0.03),
    ("RC9300000002", "Short", "-1.00", "0", -0.55, 0.03),
    # PokerStars: rake is what the site kept, not the summary's Rake field
    ("RC345678901", "Player1", "7.25", "0", None, 0),
    ("109715173634", "Captain2323", "0.20", "0.40", None, 0),
]


@pytest.mark.parametrize(
    "hand_id, player, won, rake, won_ev, tol", VECTORS,
    ids=[f"{v[0]}-{v[1]}" for v in VECTORS],
)
def test_h2n_money_vectors(hand_id, player, won, rake, won_ev, tol):
    pm = _money(hand_id).players[player]
    assert pm.won == D(won)
    assert pm.rake == D(rake)
    expected_ev = float(D(won)) if won_ev is None else won_ev
    assert pm.won_ev == pytest.approx(expected_ev, abs=tol or 1e-9)


def test_raise_that_is_a_call_is_not_penalised():
    """H2N subtracts the uncalled part of a final 'raise' a second time when
    GG already returned it (RC9100000007: H2N says -0.95). We don't copy that."""
    m = _money("RC9100000007")
    assert m.players["Big"].won == D("1.05")
    assert m.players["Big"].rake == D("0.05")
    assert m.players["Short"].won == D("-1")


def test_cashout_hand_h2n_cannot_evaluate_keeps_winnings_as_ev():
    """RC9300000003: a showdown pot on a board cut at the cash-out street.
    H2N fails on this hand; we keep actual winnings as EV."""
    m = _money("RC9300000003")
    assert m.ev_state == "off"
    assert m.players["Short"].won == D("1.40")  # receives $2.40, put in $1
    for pm in m.players.values():
        assert pm.won_ev == float(pm.won)


def test_pots_and_total_rake():
    m = _money("RC4202977641")
    assert [p.size for p in m.pots] == [D("14.49"), D("1.68")]
    assert [p.after for p in m.pots] == [D("14.08"), D("1.65")]
    assert m.total_rake == D("0.44")
    # Collected total split over two pots with H2N's rounding
    m = _money("RC4236344755")
    assert [p.after for p in m.pots] == [D("2.38"), D("5.53")]


@pytest.mark.parametrize("value, stored", [
    ("0.1127", 0.11), ("0.2561", 0.26), ("0.2383", 0.24), ("0.1511", 0.15),
    ("0.0216", 0.02), ("0.045", 0.05), ("0.055", 0.05), ("0", 0.0),
    ("0.33", 0.33), ("16.00", 16.0),
])
def test_stored_rake_goes_through_half_float(value, stored):
    assert stored_rake(D(value)) == stored


def test_stored_rake_loses_cents_above_16():
    assert stored_rake(D("16.01")) != 16.01


@pytest.mark.parametrize("pot_rake, c, after, expected", [
    ("0.05", "0.64", "1.90", "0.02"),   # 0.016842 -> 0.0168 -> 0.02
    ("0.05", "0.63", "1.90", "0.02"),   # 0.016578 -> 0.0165 -> 0.02 (half-even)
    ("0.49", "23.87", "35.73", "0.33"),
    ("0.49", "11.86", "35.73", "0.16"),
    ("0.02", "0.31", "0.61", "0.01"),
    ("0.05", "1", "2", "0.02"),         # 0.025 -> 0.02 (half-even)
])
def test_round_rake(pot_rake, c, after, expected):
    assert round_rake(D(pot_rake) * D(c) / D(after)) == D(expected)


def test_rake_columns_split_out_the_jackpot():
    """H2N's rake (everything kept) = OHM's rake + jackpot columns."""
    hand = _gg_hands()["RC9000000004"]  # Rake $0.4 | Jackpot $0.05, all kept
    parsed = ggpoker.parse_hand_history(hand)
    m = compute_hand_money(parsed)
    assert rake_columns(parsed, m.players["Hero"]) == (0.40, 0.05)
    assert rake_columns(parsed, m.players["Vil"]) == (0.0, 0.0)


def test_preflop_table_is_present():
    assert _preflop_table() is not None


@pytest.mark.parametrize("hands, board, expected", [
    ([("Ad", "As"), ("Ac", "Qh")], [], [0.921453, 0.078547]),
    ([("Ac", "Qh"), ("Ad", "As")], [], [0.078547, 0.921453]),
    ([("Ah", "Kh"), ("Qs", "Qd")], [], [0.462145, 0.537855]),
    ([("Ah", "Kd"), ("8d", "8c")], ["Ks", "8h", "3c"], [0.016162, 0.983838]),
    ([("Qs", "Qd"), ("Jc", "Tc")], ["2c", "7d", "9s"], [0.771717, 0.228283]),
    ([("As", "Ks"), ("Ah", "Kh")], [], [0.5, 0.5]),
])
def test_equities(hands, board, expected):
    assert equities(hands, board) == pytest.approx(expected, abs=1e-6)


def test_multiway_preflop_equity_is_reproducible():
    hands = [("Ah", "Kh"), ("Qs", "Qd"), ("Jc", "Tc")]
    a = equities(hands, [], samples=20_000)
    assert a == equities(hands, [], samples=20_000)
    assert sum(a) == pytest.approx(1.0)


def test_cashout_columns_in_db(db):
    insert_parsed_hand(db, ggpoker.parse_hand_history(_gg_hands()["RC4201635724"]))
    rows = dict((r[0], r[1:]) for r in db.execute("""
        SELECT p.username, hp.won, hp.won_bb, hp.rake, hp.jackpot, hp.all_in_ev_bb
        FROM hand_players hp JOIN players p ON p.id = hp.player_id
    """).fetchall())
    won, won_bb, rake, jackpot, ev_bb = (float(x) for x in rows["7276c47b"])
    assert won == pytest.approx(1.04)
    assert won_bb == pytest.approx(10.4)
    assert rake == pytest.approx(0.11)  # 0.1127 stored the H2N way
    assert jackpot == 0
    assert ev_bb == pytest.approx(9.97559, abs=1e-3)


# Sample hands Hand2Note fails to parse (corrupt or unusual action lines)
H2N_REJECTS = {
    "HD2670125044", "RC4191677670", "RC4270655370",
    "RC4221244790", "RC4171501728", "RC4273984333",
}


def test_sample_totals_and_invariant():
    """Over the 20k-hand sample: totals match Hand2Note, and per hand the
    table loses exactly the rake (and wins any Cash Drop) unless someone
    cashed out (insurance money flows in or out then)."""
    total_won = total_rake = Z = D(0)
    hero_bb = 0.0
    bad = []
    hands = [h for k, h in _gg_hands().items()
             if not k.startswith(("RC9", "HD9")) and k not in H2N_REJECTS]
    for text in hands:
        parsed = ggpoker.parse_hand_history(text)
        m = compute_hand_money(parsed, with_ev=False)
        won = sum((pm.won for pm in m.players.values()), Z)
        total_won += won
        total_rake += sum((pm.rake for pm in m.players.values()), Z)
        if "Hero" in m.players:
            hero_bb += float(round(m.players["Hero"].won, 2)) / float(parsed.bb_amount)
        if not any(pm.cashout for pm in m.players.values()):
            if won != parsed.cash_drop_received - m.total_rake:
                bad.append(parsed.hand_id)
    assert bad == []
    # Hand2Note on the same hands
    assert len(hands) == 19_994
    assert total_won == D("-829.56")
    assert total_rake == D("929.648")
    # Hand2Note's total over these hands: -1288.56 (the old -1287.56 came from the
    # GG parser's wrong BB on two deep all-in NL5 hands; parity round 3).
    assert hero_bb == pytest.approx(-1288.56, abs=0.01)


def test_other_sites_agree_with_the_site_totals():
    """On every consistent non-GG fixture hand, the table loses what the site
    says it kept: sum(won) == cash drop - fees. Except where the parser's own
    rake is wrong: 888 349444554 returns $5.28 of an all-in raise that the
    parser counts as rake ($9.28); the site kept $4.00."""
    from app.parsers import ipoker, partypoker, poker888, winamax, wpn
    from tests.test_money_invariant_sites import INCONSISTENT_FIXTURES

    sites = {"pokerstars": pokerstars, "winamax": winamax, "wpn": wpn,
             "ipoker": ipoker, "partypoker": partypoker, "poker888": poker888}
    bad, checked = [], 0
    for site, module in sites.items():
        for f in sorted((FIXTURES / site).glob("*.txt")):
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            for h in module.split_hands(text):
                if not h.strip():
                    continue
                parsed = module.parse_hand_history(h.strip())
                if (site, parsed.hand_id) in INCONSISTENT_FIXTURES:
                    continue
                m = compute_hand_money(parsed, with_ev=False)
                won = sum((pm.won for pm in m.players.values()), D(0))
                fees = D("4.00") if parsed.hand_id == "349444554" else parsed.fees
                if abs(won - (parsed.cash_drop_received - fees)) > D("0.011"):
                    bad.append((site, parsed.hand_id, won, parsed.fees))
                checked += 1
    assert checked > 50
    assert bad == []


def test_partypoker_all_in_excess_not_counted_twice():
    """'wins $1.87 from the side pot 1' is dr. spaz's own unmatched all-in."""
    text = (FIXTURES / "partypoker" / "allin_showdown.txt").read_text(encoding="utf-8-sig")
    from app.parsers import partypoker
    m = compute_hand_money(partypoker.parse_hand_history(partypoker.split_hands(text)[0].strip()))
    pm = m.players["dr. spaz"]
    assert pm.returned == D("1.87")
    assert pm.won == D("12.53")
    assert m.total_rake == D("1.00")
