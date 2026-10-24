"""Spot steps of a Reports chain, evaluated per hand on the H2N action sequence.

A page's *hit point* is the decision the page is about: hand start (no spot step yet), a
hero action or a villain action, given as ``(street, action index)`` in `HandSeq.streets`.
Every spot step maps (hand, current hit) to ``(code, hit)`` with ``code`` = `OPP` | `CASE`
bits (`app.h2n.matcher`), exactly like a General row:

- ``row``: the General row's definition (`app.h2n.definitions.DEFINITIONS[key]`) through the
  matcher (`evaluate_code`), so the numbers are General's by construction. Its hit is the
  matcher's hit (the measured action of a case, the decision of an opportunity).
- ``next`` / ``faced``: one more action after the current hit (Hand2Note's Next Actions /
  Faced Next rows). The extension is a piece of matcher DSL **anchored at the hit**:

  * same street: the DSL tokens after the hit are scanned with the matcher's own `_scan`
    from the hit on (case), the last token's opportunity alternatives come from the
    matcher's `_alternatives` (opportunity). E.g. after ``row P01`` (``pre: H:R[fr]``, hit =
    hero's open raise) "Fold to 3-Bet" scans ``V:R > H:F`` from the open: the same steps the
    matcher takes for P03 = ``pre: H:R[fr] > V:R > H:F``, so cases / opps equal P03's;
    "4-Bet" (``V:R > H:R``) equals P13.
  * next street: the hero must not act again on the hit's street (= the hit action carries
    ``last``), then a one-street definition is evaluated with the matcher on the next street.
    After ``row P01``, "Continuation Bet" = hit has ``last`` + ``flop: H:B``, which is
    C01 = ``pre: H:R[fr,last]; flop: H:B``; "Missed Continuation Bet" = ``flop: H:X`` (M01).
    After ``row C01`` (hit = the flop c-bet) "2nd Barrel" = ``turn: H:B`` with the c-bet
    ``last`` = C02.

  Faced Next rows that count villains (All Villains Fold, One / Two / Three / 4+ Villains
  Call, Villains Check) have no DSL form; they are read from the actions between the hit and
  hero's next action (`_window`).
- ``betsize``: the bet-size bucket of the current hit action, with the stat popup's bucket
  rules (`app.api.general_popup._size_hits`); the hit does not move.

Row generation and naming (`SpotCtx`, `next_caption`, `faced_caption`) follow the Reports
spec's Next Actions / Faced Next rules: hero action hit -> villain raise (Fold / Call /
Raise vs. Raise, Limp Fold / Call / Raise after a limp), villain bet (Fold / Call / Raise
vs. Bet), villain call (Check / Bet vs. Call on the next street), nobody acting (Bet /
Check); villain action hit -> hero's Fold / Call / Raise or Bet / Check. Hand start -> hero's
first preflop decision.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from app.h2n.definitions import COMPILED
from app.h2n.matcher import CASE, OPP, _UNBOUND, _scan, compile_def, evaluate_code
from app.h2n.rows import ROWS
from app.h2n.sequence import (
    BET, CALL, CHECK, FOLD, FR, LIMP, P_BET, P_CALL, P_CHECK, P_RAISE, RAISE, HandSeq,
)

STREETS = ("preflop", "flop", "turn", "river")
STREET_INDEX = {s: i for i, s in enumerate(STREETS)}
STREET_CAPTION = ("Preflop", "Flop", "Turn", "River")
_DSL_STREET = ("pre", "flop", "turn", "river")
_LETTER = "FXCBR"
BOTH = OPP | CASE

# ── action keys (frontend types.ts NextAction / FacedAction) ─────────────

NEXT_CAPTIONS: dict[str, str] = {
    "fold_vs_raise": "Fold vs. Raise", "call_vs_raise": "Call vs. Raise",
    "raise_vs_raise": "Raise vs. Raise",
    "fold_vs_bet": "Fold vs. Bet", "call_vs_bet": "Call vs. Bet", "raise_vs_bet": "Raise vs. Bet",
    "check_vs_call": "Check vs. Call", "bet_vs_call": "Bet vs. Call",
    "check": "Check", "bet": "Bet", "fold": "Fold", "call": "Call", "raise": "Raise",
    "limp_fold": "Limp Fold", "limp_call": "Limp Call", "limp_raise": "Limp Raise",
}
FACED_CAPTIONS: dict[str, str] = {
    "all_fold": "All Villains Fold", "villain_bet": "Villain Bet",
    "villain_raise": "Villain Raise", "villain_squeeze": "Villain Squeeze",
    "one_call": "One Villain Call", "two_calls": "Two Villains Call",
    "three_calls": "Three Villains Call", "four_plus_calls": "At Least Four Villains Call",
    "villains_check": "Villains Check", "villain_3bet": "Villain 3-Bet",
    "villain_open_4bet": "Villain Open 4-Bet", "villain_limp_call": "Villain Limp-Call",
    "villain_limp_raise": "Villain Limp-Raise", "villain_open_call": "Villain Open Call",
}
# Faced actions this backend generates (the others are accepted by the contract but never
# produced; a step with one of them is answered with 422).
FACED_SUPPORTED = frozenset((
    "all_fold", "villain_bet", "villain_raise", "villain_squeeze", "villain_3bet",
    "one_call", "two_calls", "three_calls", "four_plus_calls", "villains_check",
))
# Display order inside one street (Reports spec 5.5).
ACTION_ORDER: tuple[str, ...] = (
    "fold_vs_raise", "call_vs_raise", "raise_vs_raise", "fold_vs_bet", "call_vs_bet",
    "raise_vs_bet", "check_vs_call", "bet_vs_call", "check", "bet", "fold", "call", "raise",
    "limp_fold", "limp_call", "limp_raise", "all_fold", "villain_bet", "villain_raise",
    "villain_squeeze", "one_call", "two_calls", "three_calls", "four_plus_calls",
    "villains_check", "villain_3bet", "villain_open_4bet", "villain_limp_call",
    "villain_limp_raise", "villain_open_call",
)
ACTION_RANK = {k: i for i, k in enumerate(ACTION_ORDER)}

_LAST_TYPE = {  # effective type of the action a key ends with
    "fold_vs_raise": FOLD, "call_vs_raise": CALL, "raise_vs_raise": RAISE,
    "fold_vs_bet": FOLD, "call_vs_bet": CALL, "raise_vs_bet": RAISE,
    "check_vs_call": CHECK, "bet_vs_call": BET, "check": CHECK, "bet": BET,
    "fold": FOLD, "call": CALL, "raise": RAISE,
    "limp_fold": FOLD, "limp_call": CALL, "limp_raise": RAISE,
    "all_fold": FOLD, "villain_bet": BET, "villain_raise": RAISE, "villain_squeeze": RAISE,
    "villain_3bet": RAISE, "one_call": CALL, "two_calls": CALL, "three_calls": CALL,
    "four_plus_calls": CALL, "villains_check": CHECK,
}
_HERO_TOKEN = {FOLD: "H:F", CALL: "H:C", RAISE: "H:R", BET: "H:B", CHECK: "H:X"}
_VS_RAISE = {"fold_vs_raise", "call_vs_raise", "raise_vs_raise"}
_LIMP_KEYS = {"limp_fold", "limp_call", "limp_raise"}
_VS_BET = {"fold_vs_bet", "call_vs_bet", "raise_vs_bet"}
_VS_CALL = {"check_vs_call", "bet_vs_call"}
_PLAIN = {"bet", "check"}
_RESPONSE = {"fold", "call", "raise"}
_RAISE_FACED = {"villain_raise", "villain_squeeze", "villain_3bet"}
_CALL_COUNTS = {"one_call": 1, "two_calls": 2, "three_calls": 3, "four_plus_calls": 4}


# ── compiled DSL pieces ──────────────────────────────────────────────────


@lru_cache(maxsize=None)
def _anchored(street: int, anchor: str, tokens: str):
    """(filter actions after the anchor, opportunity alternatives of the last one) of the
    row ``<anchor> > <tokens>`` on `street` (the anchor is matched by the hit itself)."""
    part = compile_def(f"{_DSL_STREET[street]}: {anchor} > {tokens}").parts[0]
    row, _k, _last, alts, _nh = part.plans[0]
    return row[1:], alts


@lru_cache(maxsize=None)
def _street_def(street: int, tokens: str):
    return compile_def(f"{_DSL_STREET[street]}: {tokens}")


def _anchor_token(seq: HandSeq, p: int, hit: tuple[int, int]) -> str:
    a = seq.streets[hit[0]][hit[1]]
    return ("H:" if a.actor == p else "V:") + _LETTER[a.eff]


def _same_street(seq: HandSeq, p: int, hit: tuple[int, int], tokens: str):
    """Matcher scan of ``tokens`` right after the hit, on the hit's street."""
    s, h = hit
    toks, alts = _anchored(s, _anchor_token(seq, p, hit), tokens)
    acts = seq.streets[s]
    end = seq.seq_end[p][s]
    q, b = h, _UNBOUND
    for f in toks[:-1]:
        q, b = _scan(f, acts, q + 1, end, p, b)
        if q < 0:
            return 0, None
    hq, _ = _scan(toks[-1], acts, q + 1, end, p, b)
    if hq >= 0:
        return BOTH, (s, hq)
    best = -1
    for alt in alts:
        aq, _ = _scan(alt, acts, q + 1, end, p, b)
        if aq >= 0 and (best < 0 or aq < best):
            best = aq
    return (OPP, (s, best)) if best >= 0 else (0, None)


def _closed(seq: HandSeq, p: int, hit: tuple[int, int]) -> bool:
    """Hero does not act again on the hit's street (a hero hit then carries `last`)."""
    s, h = hit
    own = seq.own[p][s]
    return not own or own[-1] <= h


def _next_street(seq: HandSeq, p: int, hit: tuple[int, int], street: int, tokens: str):
    if street != hit[0] + 1 or street > 3 or not _closed(seq, p, hit):
        return 0, None
    return evaluate_code(_street_def(street, tokens), seq, p)


# ── hand start (no spot step yet): hero's first preflop decision ─────────

_START_FAMILY = {
    "vs_raise": {"fold_vs_raise": FOLD, "call_vs_raise": CALL, "raise_vs_raise": RAISE},
    "option": {"check": CHECK, "raise": RAISE},
    "open": {"fold": FOLD, "call": CALL, "raise": RAISE},
}


def _possible(a) -> int:
    m = 1 << FOLD
    if a.flags & P_CHECK:
        m |= 1 << CHECK
    if a.flags & P_CALL:
        m |= 1 << CALL
    if a.flags & P_BET:
        m |= 1 << BET
    if a.flags & P_RAISE:
        m |= 1 << RAISE
    return m


def start_family(seq: HandSeq, p: int) -> tuple[str, int] | None:
    """(family, index of hero's first preflop action): ``vs_raise`` (an effective raise in
    front), ``option`` (nothing to call: the big blind's option) or ``open``."""
    if not seq.has_seq[p][0] or not seq.own[p][0]:
        return None
    i0 = seq.own[p][0][0]
    acts = seq.streets[0]
    if any(acts[j].eff == RAISE for j in range(i0)):
        return "vs_raise", i0
    if acts[i0].flags & P_CHECK:
        return "option", i0
    return "open", i0


def _start_next(seq: HandSeq, p: int, street: int, key: str):
    if street != 0:
        return 0, None
    fam = start_family(seq, p)
    if fam is None:
        return 0, None
    typ = _START_FAMILY[fam[0]].get(key)
    if typ is None:
        return 0, None
    i0 = fam[1]
    a0 = seq.streets[0][i0]
    if a0.eff == typ:
        return BOTH, (0, i0)
    if _possible(a0) >> typ & 1:
        return OPP, (0, i0)
    return 0, None


# ── next / faced from a hit ──────────────────────────────────────────────


def eval_next(seq: HandSeq, p: int, hit: tuple[int, int] | None, street: int, key: str):
    """(code, hit) of Next Actions row (`street`, `key`) after the current hit."""
    if hit is None:
        return _start_next(seq, p, street, key)
    s, h = hit
    a = seq.streets[s][h]
    t = a.eff
    hero = a.actor == p
    last = _HERO_TOKEN[_LAST_TYPE[key]]
    if hero:
        if key in _VS_RAISE or key in _LIMP_KEYS:
            limp = s == 0 and t == CALL and bool(a.flags & LIMP)
            if street != s or t not in (CALL, BET, RAISE) or limp != (key in _LIMP_KEYS):
                return 0, None
            return _same_street(seq, p, hit, f"V:R > {last}")
        if key in _VS_BET:
            if street == s and t == CHECK and s > 0:
                return _same_street(seq, p, hit, f"V:B > {last}")
            if t in (CALL, CHECK):
                return _next_street(seq, p, hit, street, f"V:B > {last}[first]")
            return 0, None
        if key in _VS_CALL:
            if t in (BET, RAISE):
                return _next_street(seq, p, hit, street, last)
            return 0, None
        if key in _PLAIN:
            if t in (CALL, CHECK):
                return _next_street(seq, p, hit, street, last)
            return 0, None
        return 0, None
    # villain hit
    if key in _RESPONSE:
        if street == s and t in (BET, RAISE):
            return _same_street(seq, p, hit, last)
        return 0, None
    if key in _PLAIN:
        if t != CHECK:
            return 0, None
        if street == s:
            return _same_street(seq, p, hit, last)
        return _next_street(seq, p, hit, street, last)
    if key in _VS_CALL:
        if t == CALL:
            return _next_street(seq, p, hit, street, last)
        return 0, None
    if key in _VS_BET:
        if t == CHECK:
            return _next_street(seq, p, hit, street, f"V:B > {last}[first]")
        return 0, None
    return 0, None


def raise_kind(seq: HandSeq, hit: tuple[int, int]) -> str:
    """Which Faced Next raise row a villain raise after this hero action is."""
    s, h = hit
    a = seq.streets[s][h]
    if s == 0:
        if a.eff == RAISE and a.flags & FR:
            return "villain_3bet"
        if a.eff == CALL and not a.flags & LIMP and any(
                x.eff == RAISE for x in seq.streets[0][:h]):
            return "villain_squeeze"
    return "villain_raise"


def _window(seq: HandSeq, p: int, street: int, start: int) -> list[int]:
    """Indices on `street` from `start` up to (excluding) hero's next action."""
    acts = seq.streets[street]
    out = []
    for i in range(start, len(acts)):
        if acts[i].actor == p:
            break
        out.append(i)
    return out


def _villains_check(seq: HandSeq, p: int, hit: tuple[int, int], street: int):
    s, h = hit
    a = seq.streets[s][h]
    if a.eff == CHECK and street == s and s > 0:
        win = _window(seq, p, s, h + 1)
        acts = seq.streets[s]
    elif a.eff in (CALL, CHECK) and street == s + 1 and street <= 3 and _closed(seq, p, hit):
        if not seq.has_seq[p][street] or not seq.own[p][street]:
            return 0, None
        acts = seq.streets[street]
        first = seq.own[p][street][0]
        if first > 0:
            win = list(range(first))
        elif acts[first].eff == CHECK:   # hero acts first and checks: start from that check
            win = _window(seq, p, street, first + 1)
        else:
            return 0, None
    else:
        return 0, None
    if not win:
        return 0, None
    if any(acts[i].eff in (BET, RAISE) for i in win):
        return OPP, (street, win[0])
    checks = [i for i in win if acts[i].eff == CHECK]
    return BOTH, (street, checks[-1] if checks else win[-1])


def _after_bet(seq: HandSeq, p: int, hit: tuple[int, int], key: str):
    """All Villains Fold / N Villains Call after a hero bet or raise (same street)."""
    s, h = hit
    acts = seq.streets[s]
    win = _window(seq, p, s, h + 1)
    if not win:
        return 0, None
    if key == "all_fold":
        if not all(acts[i].eff == FOLD for i in win):
            return OPP, (s, win[0])
        later = any(seq.streets[t] for t in range(s + 1, 4)) or len(acts) > win[-1] + 1
        left = [q for q in range(len(seq.names)) if q != p and seq.fold_street[q] < 0
                and any(seq.own[q][t] for t in range(4))]
        if later or left:
            return OPP, (s, win[0])
        return BOTH, (s, win[-1])
    k = _CALL_COUNTS[key]
    possible = calls = 0
    raised = False
    last_call = -1
    for i in win:
        x = acts[i]
        if x.eff in (BET, RAISE):
            raised = True
            break
        if x.flags & P_CALL:
            possible += 1
        if x.eff == CALL:
            calls += 1
            last_call = i
    if possible < k:
        return 0, None
    if not raised and (calls == k or (k == 4 and calls >= 4)):
        return BOTH, (s, last_call)
    return OPP, (s, win[0])


def eval_faced(seq: HandSeq, p: int, hit: tuple[int, int] | None, street: int, key: str):
    """(code, hit) of Faced Next row (`street`, `key`) after a hero action hit."""
    if hit is None:
        return 0, None
    s, h = hit
    a = seq.streets[s][h]
    if a.actor != p:
        return 0, None
    t = a.eff
    if key in _RAISE_FACED:
        if street != s or t not in (CALL, BET, RAISE) or raise_kind(seq, hit) != key:
            return 0, None
        return _same_street(seq, p, hit, "V:R")
    if key == "villain_bet":
        if street == s and t == CHECK and s > 0:
            return _same_street(seq, p, hit, "V:B")
        if t in (CALL, CHECK):
            return _next_street(seq, p, hit, street, "V:B")
        return 0, None
    if key == "villains_check":
        return _villains_check(seq, p, hit, street)
    if key == "all_fold" or key in _CALL_COUNTS:
        if street != s or t not in (BET, RAISE):
            return 0, None
        return _after_bet(seq, p, hit, key)
    return 0, None


def eval_row(seq: HandSeq, p: int, key: str):
    return evaluate_code(COMPILED[key], seq, p)


# ── hero money before the hit (Action Profit) ────────────────────────────


def committed_bb(seq: HandSeq, p: int, hit: tuple[int, int]) -> float:
    """Chips the player had put in before the hit action, in big blinds (posts included,
    antes / dead money not)."""
    s, h = hit
    total = 0.0
    for t in range(s):
        own = seq.own[p][t]
        if own:
            total += seq.streets[t][own[-1]].to
    a = seq.streets[s][h]
    total += a.to - a.inc
    return total / seq.bb if seq.bb else 0.0


# ── static spot context (names, kinds) ───────────────────────────────────


@dataclass(frozen=True)
class SpotCtx:
    """What is statically known about a page's hit point (for names and the spot kind).

    side: "start" (hand start), "hero" or "villain". typ: effective type of the hit action
    (None = mixed). level: preflop bet level of the hit (2 = open raise, 3 = 3-bet ...;
    for a call, the level called). plevel: postflop raise level on the hit street (1 = bet).
    barrel: hero's continuation-bet count when the hit is one (1 = c-bet); v_barrel the same
    for the villain's bet faced. hero_aggr / villain_aggr: last aggressor before the hit
    street closes.
    """

    side: str = "start"
    typ: int | None = None
    street: int = 0
    name: str | None = None
    level: int | None = None
    plevel: int | None = None
    barrel: int = 0
    v_barrel: int = 0
    hero_aggr: bool = False
    villain_aggr: bool = False
    limp: bool = False
    named: bool = True      # False: `name` is the generic "<action>, <Street>" caption


START = SpotCtx()


def _h(typ, street=0, **kw) -> SpotCtx:
    return SpotCtx(side="hero", typ=typ, street=street, **kw)


# Named General rows usable as quick filters: (label, context of the hit).
ROW_SPOTS: dict[str, tuple[str, SpotCtx]] = {
    "V01": ("VPIP", _h(None)),
    "V02": ("PFR", _h(RAISE, hero_aggr=True)),
    "P01": ("Raise 1st In", _h(RAISE, level=2, hero_aggr=True)),
    "P02": ("Steal", _h(RAISE, level=2, hero_aggr=True)),
    "P03": ("Fold to 3-Bet", _h(FOLD, level=3)),
    "P06": ("Call Open Raise", _h(CALL, level=2, villain_aggr=True)),
    "P07": ("3-Bet", _h(RAISE, level=3, hero_aggr=True)),
    "P13": ("4-Bet", _h(RAISE, level=4, hero_aggr=True)),
    "P16": ("4-Bet Fold", _h(FOLD, level=5)),
    "P19": ("Fold to 4-Bet", _h(FOLD, level=4)),
    "P20": ("Call 4-Bet", _h(CALL, level=4, villain_aggr=True)),
    "P21": ("5-Bet", _h(RAISE, level=5, hero_aggr=True)),
    "P22": ("Limp", _h(CALL, limp=True)),
    "P23": ("Limp Fold", _h(FOLD, level=2)),
    "P24": ("Squeeze", _h(RAISE, level=3, hero_aggr=True)),
    "C01": ("Continuation Bet", _h(BET, 1, plevel=1, barrel=1, hero_aggr=True)),
    "C02": ("2nd Barrel", _h(BET, 2, plevel=1, barrel=2, hero_aggr=True)),
    "C03": ("3rd Barrel", _h(BET, 3, plevel=1, barrel=3, hero_aggr=True)),
    "C04": ("Fold to Continuation Bet", _h(FOLD, 1, plevel=1)),
    "C05": ("Fold to 2nd Barrel", _h(FOLD, 2, plevel=1)),
    "C06": ("Fold to 3rd Barrel", _h(FOLD, 3, plevel=1)),
    "C07": ("Call Continuation Bet", _h(CALL, 1, plevel=1, v_barrel=1, villain_aggr=True)),
    "C08": ("Raise Continuation Bet", _h(RAISE, 1, plevel=2, hero_aggr=True)),
    "C12": ("Donk Bet", _h(BET, 1, plevel=1, hero_aggr=True)),
    "M01": ("Missed Continuation Bet", _h(CHECK, 1)),
    "N01": ("Bet vs. Missed Continuation Bet", _h(BET, 1, plevel=1, hero_aggr=True)),
}


def _def_ctx(d, street: int, name: str) -> SpotCtx:
    last = d.parts[-1]
    types = {r[-1].typ for r in last.rows}
    sides = {r[-1].hero for r in last.rows}
    return SpotCtx(side="hero" if sides == {True} else "villain" if sides == {False} else "hero",
                   typ=types.pop() if len(types) == 1 else None,
                   street=street, name=name, named=False)


def row_ctx(key: str) -> SpotCtx:
    if key in ROW_SPOTS:
        label, ctx = ROW_SPOTS[key]
        return replace(ctx, name=label)
    d = COMPILED[key]
    return _def_ctx(d, STREET_INDEX[ROWS[key].street] if key in ROWS else d.street, key)


@lru_cache(maxsize=512)
def compile_line(dsl: str):
    """Compiled custom action line (cached by notation). ValueError names the bad token."""
    try:
        return compile_def(dsl)
    except ValueError as e:
        raise ValueError(f"invalid action line: {e}") from None
    except Exception as e:  # float() of a bad amt= etc.
        raise ValueError(f"invalid action line {dsl!r}: {e}") from None


def line_ctx(dsl: str) -> SpotCtx:
    d = compile_line(dsl)
    return _def_ctx(d, d.street, "Action line")


def _bet_name(level: int) -> str:
    if level <= 2:
        return "Open Raise"
    return "Raise" if level >= 10 else f"{level}-Bet"


def _barrel_name(n: int, street: int) -> str:
    if n == 1 and street == 1:
        return "Continuation Bet"
    if n == 2:
        return "2nd Barrel" if street == 2 else f"2nd Barrel, {STREET_CAPTION[street]}"
    if n == 3 and street == 3:
        return "3rd Barrel"
    return f"Continuation Bet #{n}, {STREET_CAPTION[street]}"


def _fallback(caption: str, street: int) -> str:
    return f"{caption}, {STREET_CAPTION[street]}"


def _named(ctx: SpotCtx) -> str | None:
    return ctx.name if ctx.named else None


def next_spot(ctx: SpotCtx, street: int, key: str) -> SpotCtx:
    """Static context (with its name) of Next Actions row (`street`, `key`) after `ctx`."""
    typ = _LAST_TYPE[key]
    base = SpotCtx(side="hero", typ=typ, street=street, hero_aggr=typ in (BET, RAISE),
                   villain_aggr=False)
    generic = replace(base, name=_fallback(NEXT_CAPTIONS[key], street), named=False)
    x = _named(ctx)

    if ctx.side == "start":
        names = {"raise": ("Raise 1st In", 2), "call": ("Limp", None),
                 "fold": ("Fold, Preflop", None), "check": ("Check, Preflop", None),
                 "fold_vs_raise": ("Fold to Open Raise", 2),
                 "call_vs_raise": ("Call Open Raise", 2), "raise_vs_raise": ("3-Bet", 3)}
        if key not in names:  # not a hand-start action: generic name
            return generic
        name, lvl = names[key]
        return replace(base, name=name, level=lvl, limp=key == "call",
                       villain_aggr=key == "call_vs_raise", named=key != "fold"
                       and key != "check")

    if key in _LIMP_KEYS:
        return replace(base, name=NEXT_CAPTIONS[key], level=3 if typ == RAISE else 2,
                       villain_aggr=typ == CALL)
    if key in _VS_RAISE:
        if street == 0 and ctx.level is not None:
            faced_level = ctx.level + 1
            faced = ("Squeeze" if ctx.typ == CALL and ctx.level == 2 and not ctx.limp
                     else _bet_name(faced_level))
            name = {FOLD: f"Fold to {faced}", CALL: f"Call {faced}",
                    RAISE: _bet_name(faced_level + 1)}[typ]
            return replace(base, name=name, level=faced_level + (typ == RAISE),
                           villain_aggr=typ == CALL)
        if street > 0 and ctx.typ == BET and ctx.barrel and x:
            name = {FOLD: f"Fold to Raise {x}", CALL: f"Call Raise {x}", RAISE: "3-Bet"}[typ]
            return replace(base, name=name, plevel=2 + (typ == RAISE), villain_aggr=typ == CALL)
        if street > 0 and ctx.plevel:
            faced = f"{ctx.plevel + 1}-Bet"
            name = {FOLD: f"Fold to {faced}", CALL: f"Call {faced}",
                    RAISE: f"{ctx.plevel + 2}-Bet"}[typ]
            return replace(base, name=name, plevel=ctx.plevel + 1 + (typ == RAISE),
                           villain_aggr=typ == CALL)
        return replace(generic, villain_aggr=typ == CALL)

    if key in _VS_BET:
        out = replace(generic, plevel=1 + (typ == RAISE), villain_aggr=typ == CALL)
        if street == ctx.street + 1 and ctx.villain_aggr:
            vb = ctx.v_barrel + 1
            faced = _barrel_name(vb, street)
            name = {FOLD: f"Fold to {faced}", CALL: f"Call {faced}", RAISE: f"Raise {faced}"}[typ]
            return replace(out, name=name, named=True, v_barrel=vb if typ == CALL else 0)
        return out

    if key in _VS_CALL:
        if ctx.hero_aggr and (ctx.street == 0 or ctx.barrel):
            n = 1 if ctx.street == 0 else ctx.barrel + 1
            barrel = _barrel_name(n, street)
            if typ == BET:
                return replace(base, name=barrel, plevel=1, barrel=n)
            return replace(base, name=f"Missed {barrel}")
        return replace(generic, plevel=1 if typ == BET else None)

    if key in _PLAIN:
        if typ == BET:
            return replace(generic, plevel=1)
        return replace(generic, villain_aggr=ctx.villain_aggr, v_barrel=ctx.v_barrel)

    # fold / call / raise after a villain bet or raise
    if x is None:
        return replace(generic, villain_aggr=typ == CALL)
    if typ == FOLD:
        return replace(base, name=f"Fold to {x}")
    if typ == CALL:
        return replace(base, name=f"Call {x}", villain_aggr=True, v_barrel=ctx.v_barrel,
                       level=ctx.level, plevel=ctx.plevel)
    if street == 0 and ctx.level is not None:
        return replace(base, name=_bet_name(ctx.level + 1), level=ctx.level + 1)
    if ctx.plevel and ctx.plevel >= 2:
        return replace(base, name=f"{ctx.plevel + 1}-Bet", plevel=ctx.plevel + 1)
    return replace(base, name=f"Raise {x}", plevel=2)


def faced_spot(ctx: SpotCtx, street: int, key: str) -> SpotCtx:
    """Static context (with its name) of Faced Next row (`street`, `key`) after `ctx`."""
    typ = _LAST_TYPE[key]
    base = SpotCtx(side="villain", typ=typ, street=street)
    generic = replace(base, name=_fallback(FACED_CAPTIONS[key], street), named=False)
    x = _named(ctx)
    if key in _RAISE_FACED:
        if street == 0:
            if key == "villain_squeeze":
                return replace(base, name="Squeeze", level=3, villain_aggr=True)
            lvl = (ctx.level + 1) if ctx.level else (3 if key == "villain_3bet" else None)
            if lvl is None:
                return replace(generic, villain_aggr=True)
            return replace(base, name=_bet_name(lvl), level=lvl, villain_aggr=True)
        if x and ctx.typ == BET:
            return replace(base, name=f"Raise {x}", plevel=2, villain_aggr=True)
        return replace(generic, plevel=(ctx.plevel or 1) + 1, villain_aggr=True)
    if key == "villain_bet":
        if street == ctx.street + 1 and ctx.villain_aggr:
            vb = ctx.v_barrel + 1
            return replace(base, name=_barrel_name(vb, street), plevel=1, v_barrel=vb,
                           villain_aggr=True)
        return replace(generic, plevel=1, villain_aggr=True)
    keep = dict(hero_aggr=ctx.hero_aggr, barrel=ctx.barrel, level=ctx.level)
    if key == "all_fold":
        return replace(base, name=f"Fold to {x}") if x else generic
    if key == "one_call":
        return replace(base, name=f"Call {x}", **keep) if x else replace(generic, **keep)
    if key in _CALL_COUNTS:
        return replace(generic, **keep)
    # villains check
    return replace(generic, villain_aggr=ctx.villain_aggr, v_barrel=ctx.v_barrel)


def kind_of(ctx: SpotCtx | None) -> str:
    if ctx is None or ctx.side == "start":
        return "plain"
    if ctx.side == "villain":
        return "villain"
    return {RAISE: "hero_raise", BET: "hero_bet", CALL: "hero_call", CHECK: "hero_check",
            FOLD: "hero_fold"}.get(ctx.typ, "hero_raise")


def next_candidates(ctx: SpotCtx) -> list[tuple[int, str]]:
    """(street, key) pairs worth evaluating as Next Actions rows after `ctx`."""
    if ctx.side == "start":
        return sorted({(0, k) for fam in _START_FAMILY.values() for k in fam})
    s = ctx.street
    if ctx.side == "hero":
        same, nxt = _VS_RAISE | _LIMP_KEYS | _VS_BET, _VS_BET | _VS_CALL | _PLAIN
    else:
        same, nxt = _RESPONSE | _PLAIN, _VS_BET | _VS_CALL | _PLAIN
    out = [(s, k) for k in sorted(same)]
    if s < 3:
        out += [(s + 1, k) for k in sorted(nxt)]
    return out


def faced_candidates(ctx: SpotCtx) -> list[tuple[int, str]]:
    if ctx.side != "hero":
        return []
    s = ctx.street
    out = [(s, k) for k in ("all_fold", "villain_bet", "villain_raise", "villain_squeeze",
                            "villain_3bet", "one_call", "two_calls", "three_calls",
                            "four_plus_calls", "villains_check")]
    if s < 3:
        out += [(s + 1, "villain_bet"), (s + 1, "villains_check")]
    return out
