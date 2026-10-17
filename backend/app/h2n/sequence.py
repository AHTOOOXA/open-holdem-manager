"""Per-street action sequence in H2N terms (docs/specs/H2N-COMPATIBLE-STATS.md 2.3-2.6).

`build_sequence(parsed)` walks a `ParsedHand` once and annotates every
voluntary action (fold/check/call/bet/raise; blind and ante posts are not
actions) with what the H2N matcher needs:

- the effective type: a raise only counts as a raise when an effective raise
  was possible (the actor's chips behind, against the biggest other live
  stack, exceed the amount to call); otherwise it is a call, or a check when
  there was nothing to call;
- flags that do not depend on whose stats are computed: first raise of the
  street, opening action, first / last action of the player on the street,
  limp, 3-bet, relative position to the players left / to the players who
  VPIP'd (tri-state: IP, OOP or neither);
- what was possible at that decision (raise, bet, check, limp, first raise,
  opening, 3-bet) and amounts in big blinds.

The matcher (`app.h2n.matcher`) reads these objects for every player of the
hand: actor == player is the "H" side, anyone else the "V" side.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.money import h2n_main_blind

if TYPE_CHECKING:
    from app.parsers.common import ParsedHand

__all__ = [
    "Act", "HandSeq", "build_sequence", "h2n_positions",
    "FOLD", "CHECK", "CALL", "BET", "RAISE", "TYPE_LETTERS", "STREET_NAMES",
]

STREET_NAMES = ("preflop", "flop", "turn", "river")

# Action types (effective and raw). Fold and check are the two lowest so
# "skippable" is simply `type <= CHECK`.
FOLD, CHECK, CALL, BET, RAISE = 0, 1, 2, 3, 4
TYPE_LETTERS = "FXCBR"
_RAW_TYPE = {"fold": FOLD, "check": CHECK, "call": CALL, "bet": BET, "raise": RAISE}
_POSTS = frozenset(("sb", "bb", "straddle"))

# ── action flags (bits of Act.flags) ─────────────────────────────────────
FR = 1 << 0          # first effective raise of the street
OPEN = 1 << 1        # opening action (preflop: first VPIP action; postflop: first non-fold)
FIRST = 1 << 2       # player's first non-fold action on the street
LAST = 1 << 3        # player's last action on the street
LIMP = 1 << 4        # preflop call, nothing in front, no raise yet, raise possible
TB = 1 << 5          # 3-bet: preflop raise facing exactly one effective raise
IPL = 1 << 6         # in position to every other active player
OOPL = 1 << 7        # out of position to every other active player
IPV = 1 << 8         # in position to every other active player who VPIP'd
OOPV = 1 << 9        # out of position to every other active player who VPIP'd
# what was possible at the decision
P_RAISE = 1 << 10    # effective raise possible
P_BET = 1 << 11      # bet possible (postflop, nothing to call)
P_CHECK = 1 << 12    # check possible (nothing to call)
P_LIMP = 1 << 13     # a limp was possible
P_FR = 1 << 14       # first raise of the street was possible
P_OPEN = 1 << 15     # an opening action was possible
P_TB = 1 << 16       # a 3-bet was possible
P_CALL = 1 << 17     # something to call
ALLIN = 1 << 18      # the action put the actor (effectively) all-in
VPIP = 1 << 19       # raw call / bet / raise

FLAG_NAMES = {
    FR: "first_raise", OPEN: "opening", FIRST: "first_of_player", LAST: "last_of_player",
    LIMP: "limp", TB: "type_3bet", IPL: "ip_left", OOPL: "oop_left", IPV: "ip_vpip",
    OOPV: "oop_vpip", P_RAISE: "raise_possible", P_BET: "bet_possible",
    P_CHECK: "check_possible", P_LIMP: "limp_possible", P_FR: "first_raise_possible",
    P_OPEN: "opening_possible", P_TB: "three_bet_possible", P_CALL: "call_possible",
    ALLIN: "all_in", VPIP: "vpip",
}

_EPS = 1e-9
# Tolerance for comparing amounts from the hand text (cents and chips).
_AMT_EPS = 0.005


class Act:
    """One voluntary action, annotated (see module docstring).

    Money fields are in the hand's currency; the `*_bb` properties divide by
    the big blind. `amt_bb` is the effective amount used by H2N amount
    filters: a call's increment, a bet's size, a raise's raise-to amount
    (bet and raise capped by the biggest stack they can be called by).
    """

    __slots__ = (
        "street", "idx", "actor", "name", "raw", "eff", "flags", "pos",
        "inc", "to", "pot", "to_call", "stack_left", "bb", "amt_bb", "is_all_in",
    )

    def __init__(self, street: int, idx: int, actor: int, name: str, raw: int, eff: int,
                 flags: int, pos: str, inc: float, to: float, bb: float, pot: float,
                 to_call: float, stack_left: float, is_all_in: bool):
        self.street = street
        self.idx = idx
        self.actor = actor
        self.name = name
        self.raw = raw
        self.eff = eff
        self.flags = flags
        self.pos = pos
        self.inc = inc                  # chips added by this action
        self.to = to                    # actor's street total after the action
        self.pot = pot                  # whole pot before the action (posts and street bets in)
        self.to_call = to_call          # amount to call before the action
        self.stack_left = stack_left    # effective chips behind before the action
        self.bb = bb
        self.amt_bb = 0.0
        self.is_all_in = is_all_in      # site marked the action all-in

    @property
    def inc_bb(self) -> float:
        return self.inc / self.bb

    @property
    def to_bb(self) -> float:
        return self.to / self.bb

    @property
    def pot_bb(self) -> float:
        return self.pot / self.bb

    @property
    def to_call_bb(self) -> float:
        return self.to_call / self.bb

    @property
    def stack_left_bb(self) -> float:
        return self.stack_left / self.bb

    @property
    def letter(self) -> str:
        return TYPE_LETTERS[self.eff]

    @property
    def raw_letter(self) -> str:
        return TYPE_LETTERS[self.raw]

    def has(self, flag: int) -> bool:
        return bool(self.flags & flag)

    def flag_names(self) -> list[str]:
        return [n for bit, n in FLAG_NAMES.items() if self.flags & bit]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        raw = "" if self.raw == self.eff else f"(raw {TYPE_LETTERS[self.raw]})"
        return (f"<{STREET_NAMES[self.street]}#{self.idx} {self.name}[{self.pos}] "
                f"{self.letter}{raw} {self.amt_bb:g}bb {','.join(self.flag_names())}>")


class HandSeq:
    """Annotated actions of one hand plus per-player bookkeeping."""

    __slots__ = (
        "names", "index", "pos", "bb", "streets", "fold_street", "seq_end",
        "has_seq", "own", "by_type", "first_raise_idx", "open_idx", "reject", "pot_total",
    )

    def __init__(self, names: list[str], pos: list[str], bb: float):
        self.names = names
        self.index = {n: i for i, n in enumerate(names)}
        self.pos = pos                  # h2n_pos per player index
        self.bb = bb
        self.streets: list[list[Act]] = [[], [], [], []]
        self.fold_street: list[int] = [-1] * len(names)    # street of the player's fold, -1 none
        # Per player and street: end of the player's view of the street (the
        # list stops after his fold) and whether he has a sequence there.
        self.seq_end: list[list[int]] = []
        self.has_seq: list[list[bool]] = []
        # Per player and street: indices of his own actions.
        self.own: list[list[list[int]]] = []
        # Per street: effective type -> action indices.
        self.by_type: list[list[list[int]]] = []
        # Per street: index of the first effective raise, -1 if none.
        self.first_raise_idx: list[int] = [-1, -1, -1, -1]
        # Per street: index of the opening action, -1 if none.
        self.open_idx: list[int] = [-1, -1, -1, -1]
        # Why H2N would refuse this hand (inconsistent amounts), None if valid.
        self.reject: str | None = None
        # Everything put into the pot (posts, dead money, bets), before uncalled returns.
        self.pot_total = 0.0

    def acts(self, street: int) -> list[Act]:
        return self.streets[street]

    def player_acts(self, player: int, street: int) -> list[Act]:
        acts = self.streets[street]
        return [acts[i] for i in self.own[player][street]]


def _clockwise_from_button(seats: list[dict], button_seat: int) -> list[dict]:
    ordered = sorted(seats, key=lambda s: s["seat"])
    if not ordered:
        return ordered
    btn = None
    for i, s in enumerate(ordered):
        if s["seat"] == button_seat:
            btn = i
            break
    if btn is None:  # empty button seat: the closest occupied seat before it acts as button
        btn = len(ordered) - 1
        for i in range(len(ordered) - 1, -1, -1):
            if ordered[i]["seat"] < button_seat:
                btn = i
                break
    return ordered[btn:] + ordered[:btn]


_BACKWARD_FROM_BB = ("BTN", "CO", "MP")   # then EP for every seat further back


def _positions_for(names: list[str], sb: str | None, bb: str | None) -> list[str]:
    """H2N column groups for `names` ordered clockwise from the button.

    Without a small-blind poster among them (dead or absent small blind)
    H2N counts the positions back from the big blind: the player right
    before the big blind is BTN -- even when the dealer button is another
    seat -- then CO, MP and EP (checked on synthetic hands: a seated player
    between the button and the big blind who posts nothing is BTN and the
    dealer becomes CO; with that seat empty the dealer stays BTN).
    """
    n = len(names)
    if n == 0:
        return []
    if n == 1:
        return ["BTN"]
    if n == 2:
        return ["SB", "BB"]
    rest = names[1:]
    if sb not in names and bb in rest:
        out = [""] * n
        j = names.index(bb)
        out[j] = "BB"
        for k in range(1, n):
            out[(j - k) % n] = _BACKWARD_FROM_BB[k - 1] if k <= 3 else "EP"
        return out
    out = ["BTN"] + [""] * (n - 1)
    if sb not in rest and bb not in rest:
        sb, bb = rest[0], rest[1]
    k = 0
    for i in range(n - 1, 0, -1):
        name = names[i]
        if name == sb:
            out[i] = "SB"
        elif name == bb:
            out[i] = "BB"
        else:
            out[i] = "CO" if k == 0 else "MP" if k == 1 else "EP"
            k += 1
    return out


def regular_blinds(parsed: ParsedHand) -> tuple[str | None, str | None]:
    """(small blind, big blind) posters in H2N's sense.

    The first "small blind" post is the regular SB and the first "big blind"
    post the regular BB. A later big-blind post is an out-of-turn blind (a
    new player or one who missed his blinds): it is live money, but that
    player keeps the ordinary position of his seat. A later small-blind post
    is dead money (H2N-COMPATIBLE-STATS.md 2.3, 7.1). Falls back to the parser's
    posters when the action list has no posts.
    """
    sb = bb = None
    for a in parsed.actions_by_street.get("preflop", ()):
        kind = a["action"]
        if kind == "sb" and sb is None:
            sb = a["username"]
        elif kind == "bb" and bb is None:
            bb = a["username"]
    if sb is None and bb is None:
        return parsed.sb_player, parsed.bb_player
    return sb, bb


def h2n_positions(parsed: ParsedHand) -> dict[str, str]:
    """H2N General-screen column group per player.

    Heads-up: the button is SB (H2N's SB-HU), the other player BB. Otherwise
    the button is BTN, the regular blind posters SB / BB (`regular_blinds`),
    and the remaining seats get CO, MP (exactly one seat), then EP for
    everything further from the button.
    """
    names = [s["username"] for s in _clockwise_from_button(parsed.seats, parsed.button_seat)]
    sb, bb = regular_blinds(parsed)
    return dict(zip(names, _positions_for(names, sb, bb)))


# GG post lines the site parser does not keep: a straddle written without
# "posts" (live money) and a missed blind (dead money).
_RE_GG_EXTRA_POST = re.compile(r"^(.+?): (straddle|posts missed blind) \$([0-9.]+)", re.M)
_SITE_GG = 1


def _extra_gg_posts(parsed: ParsedHand, kept: list[tuple[str, str, float]]) -> list[tuple[str, str, float]]:
    """GG straddles written without "posts" and missed blinds (not in the action log)."""
    text = parsed.raw_text or ""
    out: list[tuple[str, str, float]] = []
    if parsed.site_id == _SITE_GG and ("straddle $" in text or "missed blind" in text):
        end = text.find("*** HOLE CARDS ***")
        parsed_straddle = any(k == "straddle" for _, k, _ in kept)
        for m in _RE_GG_EXTRA_POST.finditer(text, 0, end if end >= 0 else len(text)):
            if m.group(2) == "straddle":
                if parsed_straddle:
                    continue    # the parser kept the straddles itself
                out.append((m.group(1), "straddle", float(m.group(3))))
            else:
                out.append((m.group(1), "dead", float(m.group(3))))
    return out


def _posts(parsed: ParsedHand) -> list[tuple[str, str, float]]:
    """Blind, straddle, ante and dead posts in hand order: (name, kind, amount).

    kind is "sb" / "bb" / "straddle" (live) or "ante" / "dead" (pot only).
    """
    out = [(a["username"], a["action"], float(a["amount"]))
           for a in parsed.actions_by_street.get("preflop", ())
           if a["action"] in _POSTS or a["action"] == "ante"]
    out.extend(_extra_gg_posts(parsed, out))
    return out


_STREET_INDEX = {name: i for i, name in enumerate(STREET_NAMES)}
_NO_TYPES: tuple[tuple[int, ...], ...] = ((), (), (), (), ())   # by_type of a street without actions


_RE_GG_HEADER_BLINDS = re.compile(r"\(\$([0-9.]+)/\$([0-9.]+)\)")
_AMOUNT_CHARS = frozenset("0123456789.")


def _all_posts_are(text: str, token: str, amount: str, end: int) -> bool:
    """True when every "<token><amount>" before `end` carries exactly `amount`."""
    i = text.find(token, 0, end)
    n = len(token)
    chars = _AMOUNT_CHARS
    while i >= 0:
        j = k = i + n
        while k < len(text) and text[k] in chars:
            k += 1
        if text[j:k] != amount:
            return False
        i = text.find(token, k, end)
    return True


def _main_blind(parsed: ParsedHand) -> float:
    """float(app.money.h2n_main_blind(parsed)), with a fast path for GG.

    h2n_main_blind keeps the header's big blind unless a regular blind
    poster posted something other than the header amounts. When every
    small-blind and big-blind post before the deal is exactly the header's
    amount (the usual case) nothing can override it, so the header BB is the
    answer without the full post analysis.
    """
    text = parsed.raw_text
    if parsed.site_id == _SITE_GG and text:
        nl = text.find("\n")
        m = _RE_GG_HEADER_BLINDS.search(text, 0, nl if nl >= 0 else len(text))
        if m:
            header_sb, header_bb = m.group(1), m.group(2)
            try:
                bb = float(header_bb)
            except ValueError:
                bb = 0.0
            if bb > 0:
                end = text.find("*** HOLE CARDS ***")
                if end < 0:
                    end = len(text)
                if (_all_posts_are(text, ": posts big blind $", header_bb, end)
                        and _all_posts_are(text, ": posts small blind $", header_sb, end)):
                    return bb
    return float(h2n_main_blind(parsed))


_ORDER_MASKS: dict[tuple[int, int], tuple[tuple[int, ...], tuple[int, ...]]] = {}


def _order_masks(n: int, btn: int = 0) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """(acts_before, acts_after) bit masks per player index for n players.

    Postflop order: SB first ... BTN last (heads-up: BB first, button last),
    i.e. order[p] = (p - btn - 1) % n with players clockwise from the dealer
    and `btn` the index of H2N's button (the dealer, except with a dead small
    blind, see _positions_for: H2N's relative positions follow its own
    positions; checked against Hand2Note). acts_before[p]: the players who act before p.
    """
    key = (n, btn)
    masks = _ORDER_MASKS.get(key)
    if masks is None:
        order = [(i - btn - 1) % n for i in range(n)]
        before = [0] * n
        after = [0] * n
        for p in range(n):
            for q in range(n):
                if q != p:
                    if order[q] < order[p]:
                        before[p] |= 1 << q
                    else:
                        after[p] |= 1 << q
        masks = _ORDER_MASKS[key] = (tuple(before), tuple(after))
    return masks


def build_sequence(parsed: ParsedHand) -> HandSeq:
    # H2N's big blind (header + regular blind posts), not the parser's
    # corruption-corrected bb_amount: every "in bb" condition uses it.
    bb = _main_blind(parsed) or float(parsed.bb_amount) or 1.0
    ordered = _clockwise_from_button(parsed.seats, parsed.button_seat)
    names = [s["username"] for s in ordered]
    n = len(names)
    seq = HandSeq(names, [], bb)
    index = seq.index
    actions_by_street = parsed.actions_by_street
    raw_type = _RAW_TYPE

    # One pass over the action log: who is active, the regular blind posters
    # (see regular_blinds), the posts (see _posts) and the voluntary actions
    # per street as (player index, raw type, action).
    active: set[str] = set(parsed.hero_cards)
    street_raw: list[list[tuple]] = [[], [], [], []]
    posts: list[tuple[str, str, float]] = []
    sb_name = bb_name = None
    for street_key, street_acts in actions_by_street.items():
        s = _STREET_INDEX.get(street_key, -1)
        if s < 0:
            active.update(a["username"] for a in street_acts)
            continue
        raw_list = street_raw[s]
        for a in street_acts:
            u = a["username"]
            active.add(u)
            kind = a["action"]
            raw = raw_type.get(kind)
            if raw is not None:
                q = index.get(u)
                if q is not None:
                    raw_list.append((q, raw, a))
            elif s == 0 and (kind in _POSTS or kind == "ante"):
                posts.append((u, kind, float(a["amount"])))
                if kind == "sb":
                    if sb_name is None:
                        sb_name = u
                elif kind == "bb" and bb_name is None:
                    bb_name = u
    if sb_name is None and bb_name is None:
        sb_name, bb_name = parsed.sb_player, parsed.bb_player
    posts.extend(_extra_gg_posts(parsed, posts))

    # Seats without any action, post or known cards are sitting out: H2N drops
    # them before positions and stacks are computed.
    idle = [nm not in active for nm in names]
    positions = _positions_for(names, sb_name, bb_name)
    if True in idle:
        live_names = [nm for nm, i in zip(names, idle) if not i]
        if len(live_names) >= 2 and not idle[0]:
            live_pos = dict(zip(live_names, _positions_for(live_names, sb_name, bb_name)))
            positions = [live_pos.get(nm, positions[i]) for i, nm in enumerate(names)]
    seq.pos = pos = positions
    rng = range(n)
    # H2N's button is the dealer except with a dead small blind (_positions_for);
    # a sitting-out seat may keep a stale label, so prefer a live one.
    btn = 0
    if positions and positions[0] != "BTN":
        btn = next((i for i in rng if positions[i] == "BTN" and not idle[i]),
                   next((i for i in rng if positions[i] == "BTN"), 0))
    acts_before, acts_after = _order_masks(n, btn)

    stack = [float(s.get("stack") or 0) for s in ordered]
    bet = [0.0] * n
    pot = 0.0
    eps = _EPS

    sb_seen = bb_seen = False
    sb_post = bb_post = 0.0
    for name, kind, amt in posts:
        p = index.get(name)
        if p is None:
            continue
        if kind == "straddle":  # "straddle $X" is the player's total (a posted SB included)
            amt = max(0.0, amt - bet[p])
        stack[p] -= amt
        pot += amt
        if kind == "sb":
            if sb_seen:     # a second small-blind post is dead money
                continue
            sb_seen = True
            sb_post = amt
        elif kind == "bb" and not bb_seen:
            bb_seen = True
            bb_post = amt
        if kind in _POSTS:
            bet[p] += amt
    # A (corrupted) small blind above the big blind: H2N then expects the
    # first raise to go above twice the small blind (Hand2Note's results, parity round 1).
    pre_floor = 2.0 * sb_post if sb_post > bb_post + _EPS else 0.0
    allin_mask = 0      # players (effectively) all-in
    for p in rng:
        if bet[p] > eps and stack[p] <= eps:
            allin_mask |= 1 << p
    live_mask = 0              # dealt in and not folded
    for p in rng:
        if not idle[p]:
            live_mask |= 1 << p
    live = [p for p in rng if not idle[p]]   # same players as live_mask, ascending
    vpip_mask = 0              # VPIP'd at some point in the hand

    seq_end = [[0, 0, 0, 0] for _ in rng]
    has_seq = [[False, False, False, False] for _ in rng]
    own = [[[], [], [], []] for _ in rng]
    fold_street = seq.fold_street
    first_raise_idx = seq.first_raise_idx
    open_idx = seq.open_idx
    by_type = seq.by_type
    streets = seq.streets

    for s in range(4):
        if s > 0:
            bet = [0.0] * n
        raw_actions = street_raw[s]
        if not raw_actions:
            by_type.append(_NO_TYPES)
            continue
        idx_by_type = [[], [], [], [], []]
        by_type.append(idx_by_type)
        acts: list[Act] = []
        streets[s] = acts
        # who has a sequence on this street: not folded, chips behind at street start
        for p in rng:
            has_seq[p][s] = bool(live_mask >> p & 1) and stack[p] > eps
        # stack + street bet stays constant during the street
        total = [stack[p] + bet[p] for p in rng]
        # the two biggest totals among the live players (updated on folds)
        top1 = top2 = 0.0
        arg1 = -1
        for q in live:
            t = total[q]
            if t > top1:
                top2, top1, arg1 = top1, t, q
            elif t > top2:
                top2 = t
        last_idx = {p: i for i, (p, _, _) in enumerate(raw_actions)}
        acted_mask = 0
        vpip_on_street = False
        nonfold_on_street = False
        raise_on_street = False
        eff_raises = 0
        top = max(bet)      # highest amount actually put in on the street
        if top < 0.0:
            top = 0.0
        level = bb if s == 0 and bb > top else top
        if s == 0 and pre_floor > top:
            top = pre_floor
        own_s = [own[p][s] for p in rng]
        street_name = STREET_NAMES[s]
        for i, (p, raw, a) in enumerate(raw_actions):
            pbit = 1 << p
            own_bet = bet[p]
            to_call = level - own_bet
            if to_call < eps:
                to_call = 0.0
            own_total = total[p]
            # biggest other live total, capped by his own
            best = top2 if p == arg1 else top1
            if best >= own_total - eps:
                best = own_total
            behind = best - own_bet       # effective chips behind
            facing = to_call > 0.0
            raise_possible = (facing or own_bet > eps) and to_call < behind - eps

            if raw == RAISE:
                amount = float(a["amount"])
                inc = amount - own_bet
                if inc < 0.0:
                    inc = 0.0
                # H2N refuses a raise that does not go above the current bet
                if seq.reject is None and amount <= top + _AMT_EPS:
                    seq.reject = (f"{street_name}: {names[p]} raises to {a['amount']} "
                                  f"facing a bet of {top:g}")
            elif raw == CALL or raw == BET:
                inc = float(a["amount"])
                # ... and a call that is not the amount to call (or the
                # rest of the stack when it is short)
                if raw == CALL and seq.reject is None and (
                        inc > to_call + _AMT_EPS
                        or (inc < to_call - _AMT_EPS and inc < stack[p] - _AMT_EPS
                            and not a.get("is_all_in"))):
                    seq.reject = (f"{street_name}: {names[p]} calls {a['amount']} "
                                  f"with {to_call:g} to call")
            else:
                inc = 0.0

            eff = raw
            if raw == RAISE and not raise_possible:
                eff = CALL if facing else CHECK

            flags = VPIP if raw >= CALL else 0
            if not acted_mask & pbit:
                flags |= FIRST
            if last_idx[p] == i:
                flags |= LAST
            if s == 0:
                if not vpip_on_street:
                    flags |= (OPEN | P_OPEN) if raw >= CALL else P_OPEN
            elif not nonfold_on_street:
                flags |= (OPEN | P_OPEN) if raw != FOLD else P_OPEN
            if raise_possible:
                flags |= P_RAISE
                if not raise_on_street:
                    flags |= (P_FR | FR) if raw == RAISE else P_FR
            if facing:
                flags |= P_CALL
            else:
                flags |= P_CHECK
                if s > 0 and own_bet <= eps and stack[p] > eps:
                    flags |= P_BET
            if s == 0 and raise_possible:
                if not raise_on_street and facing and own_bet <= eps:
                    flags |= (P_LIMP | LIMP) if raw == CALL else P_LIMP
                if eff_raises == 1 and nonfold_on_street:
                    flags |= (P_TB | TB) if eff == RAISE else P_TB
            # Relative position; preflop it is undefined when calling commits the stack.
            if s > 0 or not facing or to_call < behind - eps:
                others = live_mask & ~allin_mask & ~pbit
                after = others & acts_before[p]    # players p acts after
                before = others & acts_after[p]
                if after:
                    if not before:
                        flags |= IPL
                elif before:
                    flags |= OOPL
                others &= vpip_mask
                after = others & acts_before[p]
                before = others & acts_after[p]
                if after:
                    if not before:
                        flags |= IPV
                elif before:
                    flags |= OOPV
            if inc > 0.0 and inc >= behind - eps:
                flags |= ALLIN

            act = Act(s, i, p, names[p], raw, eff, flags, pos[p], inc, own_bet + inc, bb,
                      pot, to_call, behind, a.get("is_all_in", False))
            if eff == CALL:
                act.amt_bb = inc / bb
            elif eff == BET or eff == RAISE:
                cover = 0.0
                if eff == RAISE:
                    for q in live:
                        if q != p:
                            c = stack[q] + bet[q]
                            if c > cover:
                                cover = c
                    amt = own_bet + inc
                else:
                    for q in live:
                        if q != p:
                            c = stack[q]
                            if c > cover:
                                cover = c
                    amt = inc
                act.amt_bb = (amt if amt < cover else cover) / bb
            acts.append(act)
            own_s[p].append(i)
            idx_by_type[eff].append(i)
            if flags & OPEN:
                open_idx[s] = i

            # state update
            if inc > 0.0:
                bet[p] = own_bet + inc
                stack[p] -= inc
                pot += inc
                if bet[p] > level:
                    level = bet[p]
                if bet[p] > top:
                    top = bet[p]
                if inc >= behind - eps:
                    allin_mask |= pbit
                else:
                    allin_mask &= ~pbit
            if raw == FOLD:
                if live_mask & pbit:
                    live.remove(p)
                live_mask &= ~pbit
                fold_street[p] = s
                # a player whose bet already covers every remaining stack is all-in
                top1 = top2 = 0.0
                arg1 = -1
                for q in live:
                    t = total[q]
                    if t > top1:
                        top2, top1, arg1 = top1, t, q
                    elif t > top2:
                        top2 = t
                for q in live:
                    if not allin_mask >> q & 1 and bet[q] > eps:
                        t = total[q]
                        other = top2 if q == arg1 else top1
                        if bet[q] >= (t if t < other else other) - eps:
                            allin_mask |= 1 << q
            else:
                acted_mask |= pbit
                nonfold_on_street = True
                if raw >= CALL:
                    vpip_mask |= pbit
                    vpip_on_street = True
            if raw == RAISE:
                raise_on_street = True
            if eff == RAISE:
                eff_raises += 1
                if first_raise_idx[s] < 0 and flags & FR:
                    first_raise_idx[s] = i
        nacts = len(acts)
        for p in rng:
            mine = own_s[p]
            seq_end[p][s] = mine[-1] + 1 if mine and acts[mine[-1]].raw == FOLD else nacts

    seq.pot_total = pot
    seq.seq_end = seq_end
    seq.has_seq = has_seq
    seq.own = own
    return seq
