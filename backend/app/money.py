"""Per-player money for one hand, computed the way Hand2Note 4.1 does it.

Winnings, rake per player and all-in EV, from a ParsedHand. The rules
(docs/specs/H2N-COMPATIBLE-STATS.md section 7) in short:

- won = collected + returned bet - invested, where the returned bet is
  computed from the actions (not the site's "Uncalled bet" line) and a
  cash-out player's collected amount is replaced by the cash-out amount.
  GG's collected amounts are the body "collected $X from pot" lines, after
  two reconciliation checks against the summary (collected including the
  uncalled bet, collected above the total pot).
- Pots are rebuilt from the street bets (side pots included). Each pot's
  rake = pot before rake - what was collected from it. A player pays each
  pot's rake in proportion to what they collected from it, rounded the H2N
  way; a cash-out player pays it in proportion to the cash-out amount.
- All-in EV: per pot, equity at the street the contenders went all-in times
  the pot after rake, minus what the player put in that pot.

`compute_hand_money()` does it all; `stored_rake()` mimics how H2N stores a
rake value (half float, then rounded to cents).
"""

from __future__ import annotations

import logging
import re
import struct
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from app.parsers.common import ParsedHand

Z = Decimal(0)
CENT = Decimal("0.01")
_Q4 = Decimal("0.0001")
_Q7 = Decimal("0.0000001")
STREETS = ("preflop", "flop", "turn", "river")
_STREET_IDX = {s: i for i, s in enumerate(STREETS)}
_BOARD_LEN = (0, 3, 4, 5)  # board cards known at each street

SITE_GG = 1
SITE_PS = 2
SITE_888 = 3
SITE_WPN = 4
SITE_WINAMAX = 5
SITE_IPOKER = 6
SITE_PARTY = 7
# Rooms whose "collected" may already contain the uncalled bet
_COLLECTED_MAY_INCLUDE_RETURNED = {SITE_GG, SITE_888, SITE_WPN, SITE_WINAMAX, SITE_IPOKER}
# Rooms where a pot winner may show no cards
_NO_CARDS_AT_SHOWDOWN = {SITE_GG}

_POST_KINDS = frozenset(("ante", "sb", "bb", "straddle"))

# GG lines the parser doesn't keep (or keeps differently): blind posts,
# body collected lines, cash-out amounts, the summary totals.
_RE_GG_POST = re.compile(
    r"^(.+?): (posts small & big blinds|posts small blind|posts big blind|"
    r"posts missed blind|posts second straddle|posts button blind|"
    r"posts straddle|straddle|posts the ante|posts ante) \$([0-9.]+)",
    re.M,
)
_RE_GG_COLLECTED = re.compile(r"^(.+?) collected \$([0-9.]+) from (?:main |side )?pot", re.M)
_RE_GG_CASHOUT = re.compile(
    r"^(.+?): (Receives Cashout|Receives All-in Insurance compensation|Pays Cashout Risk)"
    r" \(\$([0-9.]+)\)",
    re.M,
)
_RE_PS_CASHOUT = re.compile(r"^(.+?) cashed out the hand for \D?([0-9.]+)", re.M)
_RE_TOTAL_POT = re.compile(r"^Total pot \D?([0-9.]+)(.*)$", re.M)
_RE_RAKE = re.compile(r"Rake \D?([0-9.]+)")
_RE_JACKPOT = re.compile(r"Jackpot \D?([0-9.]+)")


@dataclass
class PlayerMoney:
    invested: Decimal = Z
    returned: Decimal = Z
    # After the H2N fixes. For a cash-out player this is the "potential
    # collected": used for the pots after rake, not for winnings.
    collected: Decimal = Z
    cashout: Decimal = Z      # non-zero = cash-out player
    won: Decimal = Z
    rake: Decimal = Z         # cents, or 4 decimals for a cash-out player
    ev_results: int = 0       # pots with an all-in EV result
    ev_sum: float = 0.0       # S: sum of the per-pot EV results
    won_ev: float = 0.0       # all-in EV adjusted winnings, as Hand2Note computes them


@dataclass
class Pot:
    num: int
    size: Decimal = Z
    investors: dict[str, Decimal] = field(default_factory=dict)
    pretenders: set[str] = field(default_factory=set)
    after: Decimal = Z
    rake: Decimal = Z
    collected: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class HandMoney:
    players: dict[str, PlayerMoney]
    pots: list[Pot]
    total_rake: Decimal
    # "off": no EV (equity unavailable, or a hand H2N can't evaluate);
    # "done": EV rules applied (possibly with no result for anyone)
    ev_state: str = "off"


def round_half_even(x: Decimal, q: Decimal = CENT) -> Decimal:
    return x.quantize(q, rounding=ROUND_HALF_EVEN)


def _round_away(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def round_rake(x: Decimal) -> Decimal:
    """H2N's rake share rounding: 7 decimals, truncate to 4, banker's to cents."""
    x = x.quantize(_Q7, rounding=ROUND_HALF_EVEN)
    x = x.quantize(_Q4, rounding=ROUND_DOWN)
    return x.quantize(CENT, rounding=ROUND_HALF_EVEN)


def net_round2(x: float) -> float:
    """.NET Math.Round(x, 2): scale, banker's round to integer, unscale."""
    return round(x * 100.0) / 100.0


def stored_rake(rake: Decimal | float) -> float:
    """A rake value as H2N's report store gives it back (half float, cents)."""
    x = float(rake)
    if x == 0:
        return 0.0
    try:
        x = struct.unpack("e", struct.pack("e", x))[0]
    except (OverflowError, struct.error):
        pass
    return net_round2(x)


def rake_columns(parsed: ParsedHand, pm: PlayerMoney) -> tuple[float, float]:
    """(rake, jackpot) for a player's hand_players row.

    H2N's rake is everything the site kept (rake, jackpot, other fees),
    stored the H2N way. OHM shows the jackpot apart, so the jackpot's part of
    it (in the proportion of the site's summary) goes to its own column:
    rake + jackpot = H2N's rake.
    """
    total = stored_rake(pm.rake)
    jackpot = 0.0
    fees = parsed.fees
    if total and parsed.total_jackpot > 0 and fees > 0:
        jackpot = min(total, net_round2(total * float(parsed.total_jackpot) / float(fees)))
    return net_round2(total - jackpot), jackpot


# ── Main blind ───────────────────────────────────────────────────────────

_RE_GG_HEADER_BLINDS = re.compile(r"\(\$([0-9.]+)/\$([0-9.]+)\)")


def h2n_main_blind(parsed: ParsedHand) -> Decimal:
    """The hand's big blind as H2N uses it for every "in bb" value (GG).

    H2N starts from the header's blinds and then lets the regular blind
    posters override them (H2N-COMPATIBLE-STATS.md 2.2): players are taken by the
    amount they posted before the deal, largest first; a regular BB poster
    who is not all-in by posting and posted something other than the header
    BB sets the BB to his post; such a regular SB poster raises the BB to 2x
    his post when the BB is below that. Action amounts are never looked at,
    so a deep all-in can't move the BB.

    The H2N action sequence (`app.h2n.sequence`) uses it for its "in bb"
    conditions. The bb money columns still divide by the parser's
    `bb_amount`, because other views turn them back into dollars with
    `hands.bb_amount`; the two only differ when the GG parser's corruption
    heuristics override the header (parity round 2).

    Checked against Hand2Note's results on GG only; other rooms keep the parser's BB
    (their headers are not corrupted, and limit games use other blinds).
    """
    text = parsed.raw_text or ""
    if parsed.site_id != SITE_GG or not text:
        return parsed.bb_amount
    header_sb, header_bb = parsed.sb_amount, parsed.bb_amount
    m = _RE_GG_HEADER_BLINDS.search(text.split("\n", 1)[0])
    if m:
        header_sb, header_bb = Decimal(m.group(1)), Decimal(m.group(2))
    if header_bb <= 0:
        return parsed.bb_amount

    stacks = {s["username"]: Decimal(str(s["stack"])) for s in parsed.seats}
    seat_no = {s["username"]: s["seat"] for s in parsed.seats}
    in_front: dict[str, Decimal] = {}
    regular: dict[str, tuple[str, Decimal]] = {}  # player -> (kind, amount)
    seen: set[str] = set()
    end = text.find("*** HOLE CARDS ***")
    for m in _RE_GG_POST.finditer(text, 0, end if end >= 0 else len(text)):
        name, kind, amt = m.group(1), m.group(2), Decimal(m.group(3))
        if name not in stacks:
            continue
        in_front[name] = in_front.get(name, Z) + amt
        # Only the first SB and the first BB post are regular blinds; a later
        # one is dead / out-of-turn money ("posts small & big blinds" too).
        if kind in ("posts small blind", "posts big blind") and kind not in seen:
            seen.add(kind)
            regular.setdefault(name, (kind, amt))

    bb = header_bb
    for name in sorted(regular, key=lambda nm: (-in_front[nm], seat_no[nm])):
        kind, amt = regular[name]
        if stacks[name] <= in_front[name]:   # all-in by posting
            continue
        if kind == "posts big blind":
            if amt != header_bb:
                bb = amt
        elif amt != header_sb and bb < 2 * amt:
            bb = 2 * amt
    return bb


# ── Inputs ───────────────────────────────────────────────────────────────


@dataclass
class _Inputs:
    posts: list[tuple[str, str, Decimal]] | None  # GG: (player, "dead"/"live", amt)
    out_of_turn: list[str]
    collected: dict[str, Decimal]
    cashout: dict[str, Decimal]
    total_pot: Decimal | None
    rake_fields: Decimal | None   # Rake + Jackpot from the summary


def _gg_inputs(parsed: ParsedHand, seated: set[str]) -> _Inputs:
    text = parsed.raw_text
    i_hole = text.find("*** HOLE CARDS ***")
    i_summary = text.find("*** SUMMARY ***")
    if i_hole < 0:
        i_hole = 0
    if i_summary < 0:
        i_summary = len(text)

    posts: list[tuple[str, str, Decimal]] = []
    out_of_turn: list[str] = []
    sb = parsed.sb_amount
    sb_seen = bb_seen = False
    i_posts = max(text.rfind("in chips)", 0, i_hole), 0)  # after the seat lines
    for m in _RE_GG_POST.finditer(text, i_posts, i_hole):
        name, kind, amt = m.group(1), m.group(2), Decimal(m.group(3))
        if name not in seated:
            continue
        if kind == "posts small & big blinds":
            posts.append((name, "live", max(Z, amt - sb)))
            posts.append((name, "dead", sb))
            out_of_turn.append(name)
        elif kind == "posts small blind":
            posts.append((name, "dead", sb) if sb_seen else (name, "live", amt))
            sb_seen = True
        elif kind == "posts big blind":
            if bb_seen:
                out_of_turn.append(name)
            posts.append((name, "live", amt))
            bb_seen = True
        elif kind == "posts missed blind":
            posts.append((name, "dead", sb))
        elif kind in ("posts the ante", "posts ante"):
            posts.append((name, "dead", amt))
        else:  # straddles, button blind
            posts.append((name, "live", amt))

    collected: dict[str, Decimal] = {}
    for m in _RE_GG_COLLECTED.finditer(text, i_hole, i_summary):
        name = m.group(1)
        collected[name] = collected.get(name, Z) + Decimal(m.group(2))

    cashout: dict[str, Decimal] = {}
    if "Cashout (" in text or "Cashout Risk (" in text or "Insurance" in text:
        risk: dict[str, Decimal] = {}
        for m in _RE_GG_CASHOUT.finditer(text, i_hole, i_summary):
            if m.group(1) not in seated:
                continue
            if m.group(2) == "Pays Cashout Risk":
                risk[m.group(1)] = Decimal(m.group(3))
            else:
                cashout[m.group(1)] = Decimal(m.group(3))
        for name, r in risk.items():
            cashout[name] = collected.get(name, Z) - r

    total_pot = rake_fields = None
    m = _RE_TOTAL_POT.search(text, i_summary)
    if m:
        total_pot = Decimal(m.group(1))
        rest = m.group(2)
        rm = _RE_RAKE.search(rest)
        if rm:
            jm = _RE_JACKPOT.search(rest)
            rake_fields = Decimal(rm.group(1)) + (Decimal(jm.group(1)) if jm else Z)
    if not collected:
        collected = dict(parsed.collected)
    return _Inputs(posts or None, out_of_turn, collected, cashout, total_pot, rake_fields)


def collected_total(parsed: ParsedHand) -> Decimal:
    """Sum of everything collected from the pot(s), from the lines the money
    rules read (GG: the body "collected" lines; else the parser's amounts)."""
    if parsed.site_id == SITE_GG:
        text = parsed.raw_text or ""
        i_hole = max(text.find("*** HOLE CARDS ***"), 0)
        i_summary = text.find("*** SUMMARY ***")
        body = sum((Decimal(m.group(2)) for m in _RE_GG_COLLECTED.finditer(
            text, i_hole, i_summary if i_summary >= 0 else len(text))), Z)
        if body:
            return body
    return sum(parsed.collected.values(), Z)


def _other_inputs(parsed: ParsedHand) -> _Inputs:
    cashout: dict[str, Decimal] = {}
    total_pot = None
    if parsed.site_id == SITE_PS:
        text = parsed.raw_text
        for m in _RE_PS_CASHOUT.finditer(text):
            cashout[m.group(1)] = Decimal(m.group(2))
        m = _RE_TOTAL_POT.search(text)
        if m:
            total_pot = Decimal(m.group(1))
    return _Inputs(None, [], dict(parsed.collected), cashout, total_pot, None)


# ── Actions → investments, street bets, pots ─────────────────────────────


def _events(parsed: ParsedHand, inputs: _Inputs):
    """Per street: [(player, kind, amount, all_in_flag)].

    kind is "dead" (ante, dead blind: in the pot, not a street bet), "live"
    (a blind: a street bet), or the action itself. A raise's amount is the
    "raise to" amount.
    """
    out = {}
    for street in STREETS:
        evs = []
        if street == "preflop" and inputs.posts is not None:
            evs = [(p, k, a, False) for p, k, a in inputs.posts]
        for a in parsed.actions_by_street.get(street, ()):
            kind = a["action"]
            if kind in _POST_KINDS:
                if inputs.posts is not None:
                    continue  # GG posts come from the raw text
                kind = "dead" if kind == "ante" else "live"
            evs.append((a["username"], kind, a["amount"], a.get("is_all_in", False)))
        out[street] = evs
    return out


def _cut_layers(bets: dict[str, Decimal], allin: set[str]):
    """Split one street's bets into pot layers: [(size, {player: amount})]."""
    bets = {p: b for p, b in bets.items() if b > 0}
    layers = []
    if len(bets) >= 2 and not allin.intersection(bets):
        # Common case, nobody all-in: one layer up to the second-largest bet
        cut = sorted(bets.values())[-2]
        part = {p: min(b, cut) for p, b in bets.items()}
        return [(sum(part.values(), Z), part)]
    while len(bets) >= 2:
        vals = sorted(bets.values())
        top = vals[-1]
        allin_bets = [b for p, b in bets.items() if p in allin]
        cut = min(allin_bets) if allin_bets and min(allin_bets) != top else vals[-2]
        if sum(1 for b in vals if b >= cut) < 2:
            break
        part = {p: min(b, cut) for p, b in bets.items()}
        layers.append((sum(part.values(), Z), part))
        bets = {p: b - part[p] for p, b in bets.items() if b - part[p] > 0}
    return layers


@dataclass
class _Play:
    invested: dict[str, Decimal]
    returned: dict[str, Decimal]
    pots: list[Pot]
    folded: set[str]
    allin_street: dict[str, int]
    last_action: dict[str, str]
    river_last: dict[str, str]
    last_street: int          # last street with any action, -1 if none
    any_voluntary: bool
    all_folds: bool           # every action (blind posts included) is a fold
    top_bettor: str | None    # sole largest bettor on the last street
    top_excess: Decimal


def _play(parsed: ParsedHand, inputs: _Inputs) -> _Play:
    names = [s["username"] for s in parsed.seats]
    stacks = {s["username"]: s["stack"] for s in parsed.seats}
    invested = {u: Z for u in names}
    folded: set[str] = set()
    allin_street: dict[str, int] = {}
    last_action: dict[str, str] = {}
    river_last: dict[str, str] = {}
    pots: list[Pot] = []
    events = _events(parsed, inputs)

    # Pot 1 starts with the dead money and the Cash Drop
    dead_total = parsed.cash_drop_received
    pot1 = Pot(1)
    for p, kind, amt, _ in events["preflop"]:
        if kind == "dead":
            pot1.investors[p] = pot1.investors.get(p, Z) + amt
            dead_total += amt
    if dead_total > 0:
        pot1.size = dead_total
        pots.append(pot1)

    last_street = -1
    last_bets: dict[str, Decimal] = {}
    any_voluntary = False
    all_folds = True
    for si, street in enumerate(STREETS):
        evs = events[street]
        if not evs:
            continue
        last_street = si
        bets: dict[str, Decimal] = {}
        for p, kind, amt, flag in evs:
            invested.setdefault(p, Z)
            if kind == "dead":
                put = amt
            elif kind in ("live", "call", "bet"):
                put = amt
                bets[p] = bets.get(p, Z) + amt
            elif kind == "raise":
                put = max(Z, amt - bets.get(p, Z))
                bets[p] = max(amt, bets.get(p, Z))
            else:
                put = Z
            invested[p] += put
            if kind == "fold":
                folded.add(p)
            if kind != "fold":
                all_folds = False  # blind posts count as actions here
            if kind not in ("dead", "live"):
                any_voluntary = True
                if si == 3:
                    river_last[p] = kind
            last_action[p] = kind
            stack = stacks.get(p, Z)
            if p not in allin_street and (flag or (stack > 0 and invested[p] >= stack)):
                allin_street[p] = si

        # Street bets → pot layers. The first layer joins the last pot,
        # unless someone all-in earlier still contends it.
        allin_now = set(allin_street)
        last_num = pots[-1].num if pots else 1
        new_pot = bool(pots) and any(
            p in allin_now and bets.get(p, Z) == 0 and p not in folded
            for p in pots[-1].investors
        )
        num = last_num + 1 if new_pot else last_num
        for size, part in _cut_layers(bets, allin_now):
            pot = pots[-1] if pots and pots[-1].num == num else None
            if pot is None:
                pot = Pot(num)
                pots.append(pot)
            pot.size += size
            for p, a in part.items():
                pot.investors[p] = pot.investors.get(p, Z) + a
            num += 1
        last_bets = bets

    returned = {u: Z for u in invested}
    top_bettor, top_excess = None, Z
    if last_bets:
        ranked = sorted(last_bets.items(), key=lambda kv: kv[1], reverse=True)
        second = ranked[1][1] if len(ranked) > 1 else Z
        if ranked[0][1] > second:
            top_bettor, top_excess = ranked[0][0], ranked[0][1] - second
            returned[top_bettor] = top_excess

    pots = [p for p in pots if p.size > 0]
    for pot in pots:
        pot.pretenders = {p for p in pot.investors if p not in folded}
    return _Play(invested, returned, pots, folded, allin_street, last_action,
                 river_last, last_street, any_voluntary, all_folds, top_bettor, top_excess)


# ── Parse-time fixes of the collected amounts ────────────────────────────


def _fix_collected(parsed: ParsedHand, inputs: _Inputs, play: _Play) -> dict[str, Decimal]:
    collected = {u: c for u, c in inputs.collected.items() if c}
    drop = parsed.cash_drop_received
    total_pot = inputs.total_pot

    # Collected above the summary's total pot by at most a cent per board:
    # take it from the first collector in seat order.
    total_c = sum(collected.values(), Z)
    if total_c > 0 and total_pot and total_pot > 0:
        x = total_c - total_pot
        if Z < x <= CENT * max(parsed.rit_boards, 1):
            seat_of = {s["username"]: s["seat"] for s in parsed.seats}
            first = min((u for u in collected if collected[u] > 0),
                        key=lambda u: seat_of.get(u, 99))
            collected[first] -= x

    # Collected that already includes the uncalled bet
    site_r = sum(parsed.uncalled_returns.values(), Z)
    recorded_r = site_r
    if parsed.site_id in _COLLECTED_MAY_INCLUDE_RETURNED and play.top_bettor:
        p, r = play.top_bettor, play.top_excess
        inv = sum(play.invested.values(), Z)
        c = sum(collected.values(), Z) - drop
        t = (total_pot or Z) - drop
        rk = inputs.rake_fields
        cashed_out = any(v != 0 for v in inputs.cashout.values())
        subtract = c >= r and (
            (rk is not None and inv == c + rk)
            or t == inv
            or (t == 0 and c > inv - r)
            or (inv != c + r + (rk or Z) and cashed_out and t + (rk or Z) + c == inv)
        )
        no_line = not site_r
        if subtract or (no_line and (
            (t == 0 and c == inv - r) or (t > 0 and t == inv - r) or rk is None
        )):
            recorded_r = recorded_r or r
        if not subtract and c == r and play.all_folds:
            subtract = True
        if subtract:
            collected[p] = collected.get(p, Z) - r

    # WPN: a site-returned bet above the computed one is paid as collected
    if parsed.site_id == SITE_WPN:
        for u, r_site in parsed.uncalled_returns.items():
            extra = r_site - play.returned.get(u, Z)
            if extra > 0:
                collected[u] = collected.get(u, Z) + extra

    # PartyPoker pays the unmatched part of an all-in bet as a "side pot"
    # win; the parser only takes out uncalled bets nobody called at all.
    if parsed.site_id == SITE_PARTY and play.top_bettor:
        p = play.top_bettor
        extra = play.top_excess - parsed.uncalled_returns.get(p, Z)
        if extra > 0 and collected.get(p, Z) >= extra:
            collected[p] -= extra

    # An out-of-turn big blind whose dead small blind wasn't printed
    n = len(inputs.out_of_turn)
    if n:
        v = sum(collected.values(), Z) + recorded_r - sum(play.invested.values(), Z)
        sb = parsed.sb_amount
        if v == sb * n:
            if not play.pots or play.pots[0].num != 1:
                play.pots.insert(0, Pot(1))
            pot1 = play.pots[0]
            for u in inputs.out_of_turn:
                play.invested[u] = play.invested.get(u, Z) + sb
                pot1.size += sb
                pot1.investors[u] = pot1.investors.get(u, Z) + sb
                if u not in play.folded:
                    pot1.pretenders.add(u)
    return collected


# ── Pot winners and the split of each player's collected total ───────────


def _boards(parsed: ParsedHand, upto: int = 3) -> list[list[str]]:
    """The canonical board and any Run It Twice boards, cut at a street."""
    n = _BOARD_LEN[upto]
    first = parsed.board_cards
    base = list(first.get("flop", [])) + list(first.get("turn", [])) + list(first.get("river", []))
    boards = [base[:n]]
    for extra in parsed.extra_boards:
        b = []
        for street, size in (("flop", 3), ("turn", 1), ("river", 1)):
            b += list(extra.get(street) or first.get(street) or [])[:size]
        boards.append(b[:n])
    return boards


def _showdown_shares(parsed: ParsedHand, players: list[str], boards) -> dict[str, float] | None:
    """Share of a pot won by each player at showdown, averaged over boards."""
    try:
        from app.equity import equities
    except ImportError:  # eval7 missing
        return None

    hands = [parsed.hero_cards[p] for p in players]
    shares = {p: 0.0 for p in players}
    for board in boards:
        if len(board) != 5:
            return None
        for p, s in zip(players, equities(hands, board)):
            shares[p] += s / len(boards)
    return shares


def _clockwise(parsed: ParsedHand, players) -> list[str]:
    """Players ordered clockwise from the seat after the button."""
    btn = parsed.button_seat
    seat_of = {s["username"]: s["seat"] for s in parsed.seats}
    return sorted(players, key=lambda u: ((seat_of.get(u, 0) - btn - 1) % 100))


def _before_rake_winners(parsed, pots, collected, cashout) -> dict[int, dict[str, Decimal]]:
    """Per pot (index): what each winner wins of it before rake."""
    known = parsed.hero_cards
    if parsed.site_id in _NO_CARDS_AT_SHOWDOWN:
        winners = [u for u in set(collected) | set(cashout)
                   if collected.get(u, Z) > 0 or cashout.get(u, Z) != 0]
        if len(winners) == 1:
            return {i: {winners[0]: pot.size} for i, pot in enumerate(pots)}
        if 1 < len(winners) == len(pots) and not any(u in known for u in winners):
            match: dict[int, dict[str, Decimal]] = {}
            for u in winners:
                i = next((i for i, pot in enumerate(pots)
                          if i not in match and pot.size == collected.get(u, Z)), None)
                if i is None:
                    break
                match[i] = {u: pots[i].size}
            else:
                return match

    full_boards = _boards(parsed)
    result: dict[int, dict[str, Decimal]] = {}
    for i, pot in enumerate(pots):
        cands = sorted(pot.pretenders)
        shown = [u for u in cands if u in known]
        if len(cands) == 1:
            shares = {cands[0]: 1.0}
        elif len(shown) == 1:
            shares = {shown[0]: 1.0}
        else:
            shares = _showdown_shares(parsed, shown, full_boards) if shown else None
            if shares is None:
                # No usable showdown: split between the pretenders who were paid
                paid = [u for u in cands if collected.get(u, Z) > 0 or cashout.get(u, Z) != 0]
                paid = paid or cands
                shares = {u: 1.0 / len(paid) for u in paid}
        won = [u for u in _clockwise(parsed, shares) if shares[u] > 0]
        amounts: dict[str, Decimal] = {}
        left = pot.size
        for j, u in enumerate(won):
            if j == len(won) - 1:
                amounts[u] = left
            else:
                amounts[u] = _round_away(pot.size * Decimal(repr(shares[u])))
                left -= amounts[u]
        result[i] = amounts
    return result


def _split_collected(parsed, pots, collected, cashout) -> None:
    """Fill pot.collected: each player's collected total spread over pots."""
    if len(pots) == 1:
        pots[0].collected = {u: c for u, c in collected.items() if c > 0}
        return
    bw = _before_rake_winners(parsed, pots, collected, cashout)
    whole_bank = sum((a for w in bw.values() for a in w.values()), Z)
    for u, total in collected.items():
        if total <= 0:
            continue
        won_pots = {i: w[u] for i, w in bw.items() if w.get(u, Z) > 0}
        if not won_pots:
            # Paid from a pot the cards say they lost: use their first pot
            i = next((i for i, pot in enumerate(pots) if u in pot.pretenders), 0)
            pots[i].collected[u] = pots[i].collected.get(u, Z) + total
            continue
        if len(won_pots) == 1:
            i = next(iter(won_pots))
            pots[i].collected[u] = pots[i].collected.get(u, Z) + total
            continue
        own = sum(won_pots.values(), Z)
        if cashout.get(u, Z) != 0 and whole_bank:
            total = own - (whole_bank - total) * own / whole_bank
        for i, a in won_pots.items():
            part = a if own == total else _round_away(total * a / own)
            pots[i].collected[u] = pots[i].collected.get(u, Z) + part


# ── Main entry ───────────────────────────────────────────────────────────


def compute_hand_money(parsed: ParsedHand, with_ev: bool = True) -> HandMoney:
    seated = {s["username"] for s in parsed.seats}
    inputs = _gg_inputs(parsed, seated) if parsed.site_id == SITE_GG else _other_inputs(parsed)
    play = _play(parsed, inputs)
    collected = _fix_collected(parsed, inputs, play)
    cashout = {u: a for u, a in inputs.cashout.items() if a != 0 and u in seated}

    players: dict[str, PlayerMoney] = {}
    for u in play.invested:
        pm = PlayerMoney(
            invested=play.invested[u],
            returned=play.returned.get(u, Z),
            collected=collected.get(u, Z),
            cashout=cashout.get(u, Z),
        )
        paid = pm.cashout if pm.cashout else pm.collected
        pm.won = paid + pm.returned - pm.invested
        players[u] = pm

    pots = play.pots
    if pots:
        _split_collected(parsed, pots, collected, cashout)
    for pot in pots:
        pot.after = sum(pot.collected.values(), Z)
        if not pot.collected:
            pot.after = pot.size  # nobody collected: no rake on it
    if sum((p.size for p in pots), Z) != sum((p.after for p in pots), Z):
        for pot in pots:
            pot.rake = max(Z, pot.size - pot.after)
    total_rake = sum((p.rake for p in pots), Z)

    # Rake paid
    for pot in pots:
        if not pot.rake:
            continue
        for u, c in pot.collected.items():
            if u in cashout or c <= 0:
                continue
            share = pot.rake if c == pot.after else round_rake(pot.rake * c / pot.after)
            players[u].rake += share
    for u, amount in cashout.items():
        mine = [p for p in pots if u in p.pretenders]
        base = sum((p.after for p in mine), Z)
        if base > 0:
            ratio = amount / base
            players[u].rake = sum(
                (round_half_even(p.rake * ratio, _Q4) for p in mine), Z)

    hm = HandMoney(players, pots, total_rake)
    if with_ev:
        try:
            _all_in_ev(parsed, play, hm, cashout)
        except Exception:
            logging.getLogger(__name__).warning(
                "all-in EV failed for hand %s", parsed.hand_id, exc_info=True)
            hm.ev_state = "off"
            for pm in players.values():
                pm.ev_results, pm.ev_sum = 0, 0.0
    for pm in players.values():
        # EV-adjusted won = round2(won) - (won - S); a normal player without an
        # EV result keeps won, a cash-out player always gets S (0 if none)
        if hm.ev_state == "done" and (pm.ev_results or pm.cashout):
            pm.won_ev = float(round_half_even(pm.won)) - (float(pm.won) - pm.ev_sum)
        else:
            pm.won_ev = float(pm.won)
    return hm


# ── All-in EV ────────────────────────────────────────────────────────────


def _ev_gate(parsed: ParsedHand, play: _Play) -> bool:
    board_len = len(_boards(parsed)[0])
    final_street = {0: 0, 3: 1, 4: 2, 5: 3}.get(board_len, 0)
    if not play.any_voluntary:
        return final_street == 3
    if play.last_street < final_street:
        return True
    active = {u for u, k in play.last_action.items() if k != "fold"}
    on_river = {u for u, k in play.river_last.items() if k != "fold"}
    return len(active) >= 2 and on_river != active


def _all_in_ev(parsed: ParsedHand, play: _Play, hm: HandMoney, cashout) -> None:
    from app.equity import equities

    pots = hm.pots
    hm.ev_state = "done"
    if not pots or not _ev_gate(parsed, play):
        return
    known = parsed.hero_cards
    if any(u not in known for pot in pots for u in pot.pretenders):
        return
    cut = 3
    if cashout:
        streets = [play.allin_street[u] for u in cashout if u in play.allin_street]
        if streets:
            cut = min(streets)
    board = _boards(parsed, cut)[0]
    multi = len(pots) > 1
    results: list[tuple[str, float]] = []
    for pot in pots:
        contenders = sorted(pot.pretenders)
        if not contenders or pot.after <= 0:
            continue
        streets = [play.allin_street[u] for u in contenders if u in play.allin_street]
        street = min(streets) if streets else 3
        showdown = len(contenders) == 1 or street >= 3
        if not multi and showdown:
            continue
        if showdown:
            if cut < 3:
                # A showdown on a board cut at the cash-out street: H2N fails
                # on this hand and doesn't import it. Keep actual winnings.
                hm.ev_state = "off"
                return
            if len(contenders) == 1:
                shares = {contenders[0]: 1.0}
            else:
                shares = _showdown_shares(parsed, contenders, _boards(parsed))
                if shares is None:
                    hm.ev_state = "off"
                    return
            eqs = [shares[u] for u in contenders]
        else:
            eqs = equities([known[u] for u in contenders], board[:_BOARD_LEN[street]])
        after = float(pot.after)
        for u, eq in zip(contenders, eqs):
            if showdown and eq <= 0:
                continue
            results.append((u, eq * after - float(pot.investors.get(u, Z))))
    for u, ev in results:
        pm = hm.players[u]
        pm.ev_results += 1
        pm.ev_sum += ev
