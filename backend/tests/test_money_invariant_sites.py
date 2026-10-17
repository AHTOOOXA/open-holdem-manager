"""Money invariants for the non-GG parsers, over every fixture hand.

Per hand, the table as a whole loses the fees and wins any Cash Drop
(site money, counted as winnings like Hand2Note does):
    sum(won) == cash_drop - fees
On top of that, where the site prints its own totals we check the parser
against them (summary "Total pot", WPN per-player "Bets:"/"Collects:"),
because sites whose rake is derived as (in - out) satisfy the invariant
trivially even when the parser misreads amounts.

A few fixtures are hand-written and don't add up by themselves; they're
listed in INCONSISTENT_FIXTURES with the reason and skipped.
"""

import re
from decimal import Decimal
from pathlib import Path

import pytest

from app.api.import_hands import _compute_financials
from app.parsers import ipoker, partypoker, poker888, pokerstars, winamax, wpn

FIXTURES = Path(__file__).parent / "fixtures"
Z = Decimal("0")
CENT = Decimal("0.011")

SITES = {
    "pokerstars": pokerstars,
    "winamax": winamax,
    "wpn": wpn,
    "ipoker": ipoker,
    "partypoker": partypoker,
    "poker888": poker888,
}

# Sites with no rake line: the parser derives rake as (in - out)
DERIVED_RAKE = {"ipoker", "partypoker", "poker888"}

INCONSISTENT_FIXTURES = {
    # Hand-written: "raises 1.50 to 1.50" style with a pot that ignores the
    # uncalled bet, unlike the real format of each site.
    ("winamax", "1234-5678-9012"): "Total pot 34.25 is before rake; real Winamax prints it after rake (34.25 - 1.50)",
    ("winamax", "1234-5678-9013"): "Total pot 1.25 excludes the uncalled bet; real Winamax includes it",
    ("ipoker", "9876543211"): "win=1.25 excludes the uncalled bet; real iPoker XML includes it",
    ("partypoker", "111222334"): "wins $1.25 excludes the uncalled bet; real partypoker includes it",
    ("wpn", "987654322"): "Bets 1.50 / Collects 1.25 / Wins 0.75 don't add up",
    ("pokerstars", "RC345678901"): "Total pot $14.75 but players put in $14.25",
    ("pokerstars", "109715173634"): "Total pot $0.50 but blinds + antes + raise put in $0.90",
}


def _hands(site):
    module = SITES[site]
    for f in sorted((FIXTURES / site).glob("*.txt")):
        text = f.read_text(encoding="utf-8-sig", errors="replace")
        for h in module.split_hands(text):
            h = h.strip()
            if h:
                yield f.name, h, module.parse_hand_history(h)


def _money(parsed):
    invested, _ = _compute_financials(parsed)
    won = {
        u: parsed.collected.get(u, Z)
        + parsed.uncalled_returns.get(u, Z) - invested.get(u, Z)
        for u in invested
    }
    put_in = sum(invested.values(), Z) - sum(parsed.uncalled_returns.values(), Z)
    return invested, won, put_in


RE_PS_POT = re.compile(r"^Total pot \S?([0-9.]+)")
RE_WMX_POT = re.compile(r"^Total pot ([0-9.]+)")
RE_WPN_PLAYER = re.compile(
    r"^\*?Player (.+?)(?: shows| mucks| does not show).*?Bets: ([0-9.]+)\. Collects: ([0-9.]+)\."
)


def _summary_problems(site, text, parsed, invested, put_in) -> list[str]:
    problems = []
    lines = [l.strip() for l in text.splitlines()]
    if site == "pokerstars":
        pot = next((Decimal(m.group(1)) for l in lines if (m := RE_PS_POT.match(l))), None)
        if pot is not None and abs(pot - put_in) > CENT:
            problems.append(f"Total pot {pot} != money in {put_in}")
    elif site == "winamax":
        # Winamax's Total pot is after rake and includes the uncalled bet
        pot = next((Decimal(m.group(1)) for l in lines if (m := RE_WMX_POT.match(l))), None)
        if pot is not None:
            expected = put_in - parsed.fees + sum(parsed.uncalled_returns.values(), Z)
            if abs(pot - expected) > CENT:
                problems.append(f"Total pot {pot} != {expected}")
    elif site == "wpn":
        for l in lines:
            m = RE_WPN_PLAYER.match(l)
            if not m:
                continue
            u, bets, collects = m.group(1), Decimal(m.group(2)), Decimal(m.group(3))
            mine = invested.get(u, Z) - parsed.uncalled_returns.get(u, Z)
            if mine != bets or parsed.collected.get(u, Z) != collects:
                problems.append(f"{u}: Bets {bets} / Collects {collects}, parsed {mine} / {parsed.collected.get(u, Z)}")
    if site in DERIVED_RAKE and put_in > 0:
        if not Z <= parsed.fees <= put_in * Decimal("0.10") + CENT:
            problems.append(f"derived rake {parsed.fees} out of range for pot {put_in}")
    return problems


@pytest.mark.parametrize("site", SITES)
def test_money_invariant(site):
    violations = []
    checked = 0
    for fname, text, parsed in _hands(site):
        if (site, parsed.hand_id) in INCONSISTENT_FIXTURES:
            continue
        invested, won, put_in = _money(parsed)
        expected = parsed.cash_drop_received - parsed.fees
        actual = sum(won.values(), Z)
        if abs(actual - expected) > CENT:
            violations.append(f"{fname} {parsed.hand_id}: sum(won) {actual} != {expected}")
        for p in _summary_problems(site, text, parsed, invested, put_in):
            violations.append(f"{fname} {parsed.hand_id}: {p}")
        checked += 1
    assert checked > 0
    assert not violations, "\n".join(violations)


@pytest.mark.parametrize("site,hand_id", sorted(INCONSISTENT_FIXTURES))
def test_inconsistent_fixtures_still_exist(site, hand_id):
    """Keep the skip list honest: every entry must still name a fixture hand."""
    assert any(p.hand_id == hand_id for _, _, p in _hands(site))


def test_actions_only_reference_seated_players():
    """An action by someone not seated crashes _compute_financials on import."""
    for site in SITES:
        for fname, _, parsed in _hands(site):
            seated = {s["username"] for s in parsed.seats}
            for street, actions in parsed.actions_by_street.items():
                for a in actions:
                    assert a["username"] in seated, f"{site} {fname} {parsed.hand_id}: {a['username']!r}"
