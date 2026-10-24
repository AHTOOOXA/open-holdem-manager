"""H2N action-row matcher (docs/specs/H2N-COMPATIBLE-STATS.md 2.7-2.9).

A stat definition is a list of street parts. Each part is one or more rows
(OR-ed); a row is a list of filter actions such as ``V:R[fr] > H:C[first]``.

Matching a row on a street (a *case*):
- the row may start at any action; its first filter action must match that
  action exactly;
- each later filter action takes the next actual action if it matches;
  otherwise that actual action must be an (effective) fold or check, which is
  skipped, and the scan goes on. Any other non-matching action ends the try.
- every street part must match; ``V1`` filter actions must all be the same
  villain, across streets.

Opportunities: earlier street parts must match as cases; on the last part the
row's last filter action is replaced by each alternative action type (see
`_ALTERNATIVES`). The alternative keeps side, positions, first/last-of-player,
relative position and the villain binding; flags that describe what the
measured action *was* (first raise, opening, limp, 3-bet, amount) become
"was possible" requirements, and the measured type adds its own requirement
(raise -> raise possible, bet -> bet possible, check -> check possible).
opp = case or any alternative row matches.

Hit (popup): each row that hits gives the action its last filter action
matched from its first matching start; the result is the earliest of those
(case rows first, alternative rows only without a case).

Row DSL (our own notation):
    "pre: H:R[fr,last]; flop: H:B[last]; turn: H:B"
    street names: pre | flop | turn | river
    side:  H (the player) | V (any other player) | V1 (one bound villain)
    type:  F X C B R  (effective types)
    flags: fr open first last limp 3b ipl oopl ipv oopv
           skipc / skipa  (opt-in, line steps only: other players' calls / any actions may
           be skipped before this action; the matcher otherwise skips only folds / checks)
           pos=SB+BB  (H2N column groups)   amt=2-   amt=0.5-1   (bb, inclusive)
    rows on one street are separated by "|", filter actions by ">".
"""

from __future__ import annotations

from app.h2n.sequence import (
    BET, CALL, CHECK, FIRST, FOLD, FR, IPL, IPV, LAST, LIMP, OOPL, OOPV, OPEN,
    P_BET, P_CHECK, P_FR, P_LIMP, P_OPEN, P_RAISE, P_TB, RAISE, TB, HandSeq,
)

__all__ = [
    "FilterAct", "Part", "StatDef", "compile_def", "evaluate", "evaluate_code", "gate",
    "first_part_binds", "evaluate_rest",
    "RowResult", "AMOUNT_EPS", "OPP", "CASE",
]

AMOUNT_EPS = 1e-6
_NOFIT = -2
_UNBOUND = -1

_STREETS = {"pre": 0, "preflop": 0, "flop": 1, "turn": 2, "river": 3}
_TYPES = {"F": FOLD, "X": CHECK, "C": CALL, "B": BET, "R": RAISE}
_FLAG_WORDS = {
    "fr": FR, "open": OPEN, "first": FIRST, "last": LAST, "limp": LIMP, "3b": TB,
    "ipl": IPL, "oopl": OOPL, "ipv": IPV, "oopv": OOPV,
}
_POSITIONS = frozenset(("EP", "MP", "CO", "BTN", "SB", "BB"))
# Flags an opportunity alternative keeps from the measured action.
_KEEP = FIRST | LAST | IPL | OOPL | IPV | OOPV
# Flags that turn into "was possible" requirements.
_TO_POSSIBLE = ((FR, P_FR), (OPEN, P_OPEN), (LIMP, P_LIMP), (TB, P_TB))


class FilterAct:
    __slots__ = ("hero", "typ", "req", "pos", "lo", "hi", "bound", "call_lo", "call_hi",
                 "skip")

    def __init__(self, hero: bool, typ: int, req: int = 0, pos: frozenset | None = None,
                 lo: float | None = None, hi: float | None = None, bound: bool = False,
                 call_lo: float | None = None, call_hi: float | None = None,
                 skip: int = 0):
        self.hero = hero
        self.typ = typ
        self.req = req
        self.pos = pos
        self.lo = lo
        self.hi = hi
        self.bound = bound
        # "possible call amount" requirement of an opportunity alternative
        self.call_lo = call_lo
        self.call_hi = call_hi
        # opt-in (line steps only): other players' calls (1, flag `skipc`) or any actions
        # (2, flag `skipa`) may be skipped on the way to this action, like folds / checks are
        self.skip = skip

    def __repr__(self) -> str:  # pragma: no cover
        side = "H" if self.hero else ("V1" if self.bound else "V")
        return f"{side}:{'FXCBR'[self.typ]}/{self.req:#x}"


class Part:
    """One street of a stat definition: OR-ed rows, plus per-row opp alternatives."""

    __slots__ = ("street", "rows", "alts", "n_hero", "key", "plans")

    def __init__(self, street: int, rows: list[tuple[FilterAct, ...]], key: str):
        self.street = street
        self.rows = rows
        self.alts = [_alternatives(r, street) for r in rows]
        self.n_hero = [sum(1 for f in r if f.hero) for r in rows]
        self.key = key
        # (row, number of filter actions before the last, last, alternatives, n_hero)
        self.plans = tuple(
            (r, len(r) - 1, r[-1], tuple(al), nh)
            for r, al, nh in zip(self.rows, self.alts, self.n_hero)
        )


class StatDef:
    """Compiled definition plus cheap necessary conditions (the "anchor").

    Every opportunity needs a player action on the last street whose type is
    in `anchor_types` (bit mask) and whose flags contain `anchor_req`, and at
    least `min_hero` player actions on that street.
    """

    __slots__ = ("parts", "text", "street", "anchor_types", "anchor_req", "min_hero", "lead")

    def __init__(self, parts: list[Part], text: str):
        self.parts = parts
        self.text = text
        last = parts[-1]
        self.street = last.street
        types = 0
        req = -1
        hero_last = True
        for (_row, _k, lf, alts, _nh) in last.plans:
            hero_last = hero_last and lf.hero
            for f in (lf,) + alts:
                types |= 1 << f.typ
                req &= f.req | (_implied(f) if f is lf else 0)
        if not hero_last:  # no anchor: the last action may be a villain's
            types, req = 0b11111, 0
        self.anchor_types = types
        self.anchor_req = req & ~(FR | OPEN | LIMP | TB)
        self.min_hero = min(last.n_hero)
        # Every row of the last part starts with a villain's first raise /
        # opening action (unique per street): (flag, positions or None).
        self.lead = None
        firsts = [plan[0][0] for plan in last.plans]
        if all(plan[1] > 0 for plan in last.plans) and all(not f.hero for f in firsts):
            for kind in (FR, OPEN):
                if all(f.req & kind for f in firsts):
                    pos = None
                    if all(f.pos is not None for f in firsts):
                        pos = frozenset().union(*(f.pos for f in firsts))
                    self.lead = (kind, pos)
                    break


def _implied(f: FilterAct) -> int:
    """Possibility flags every action that fits `f` carries."""
    out = 0
    for flag, possible in _TO_POSSIBLE:
        if f.req & flag:
            out |= possible
    if f.typ == RAISE:
        out |= P_RAISE
    elif f.typ == BET:
        out |= P_BET
    elif f.typ == CHECK:
        out |= P_CHECK
    return out


class RowResult:
    """Outcome of one definition for one player.

    `hit` = (street, action index) of the measured action for a case, or of
    the alternative action for an opportunity that is not a case.
    """

    __slots__ = ("case", "opp", "hit")

    def __init__(self, case: bool = False, opp: bool = False, hit: tuple[int, int] | None = None):
        self.case = case
        self.opp = opp
        self.hit = hit

    def __repr__(self) -> str:  # pragma: no cover
        return f"RowResult(case={self.case}, opp={self.opp}, hit={self.hit})"


# ── compiling the DSL ────────────────────────────────────────────────────


def _parse_action(tok: str) -> FilterAct:
    tok = tok.strip()
    head, _, rest = tok.partition("[")
    side, _, typ = head.partition(":")
    side = side.strip()
    if side not in ("H", "V", "V1") or typ.strip() not in _TYPES:
        raise ValueError(f"bad filter action {tok!r}")
    fa = FilterAct(side == "H", _TYPES[typ.strip()], bound=side == "V1")
    if rest:
        if not rest.endswith("]"):
            raise ValueError(f"bad flags in {tok!r}")
        for word in rest[:-1].split(","):
            word = word.strip()
            if not word:
                continue
            if word == "skipc":
                fa.skip = max(fa.skip, 1)
            elif word == "skipa":
                fa.skip = 2
            elif word in _FLAG_WORDS:
                fa.req |= _FLAG_WORDS[word]
            elif word.startswith("pos="):
                ps = frozenset(word[4:].split("+"))
                if not ps <= _POSITIONS:
                    raise ValueError(f"bad positions in {tok!r}")
                fa.pos = ps
            elif word.startswith("amt="):
                lo, _, hi = word[4:].partition("-")
                fa.lo = float(lo)
                fa.hi = float(hi) if hi else float("inf")
            else:
                raise ValueError(f"unknown flag {word!r} in {tok!r}")
    return fa


def compile_def(text: str) -> StatDef:
    parts: list[Part] = []
    last_street = -1
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        sname, _, body = chunk.partition(":")
        street = _STREETS.get(sname.strip())
        if street is None or street <= last_street:
            raise ValueError(f"bad or unordered street in {chunk!r}")
        last_street = street
        rows = []
        for row_text in body.split("|"):
            row = tuple(_parse_action(t) for t in row_text.split(">"))
            if not row:
                raise ValueError(f"empty row in {chunk!r}")
            rows.append(row)
        parts.append(Part(street, rows, f"{street}:{body.strip()}"))
    if not parts:
        raise ValueError("empty definition")
    return StatDef(parts, text)


def _alternatives(row: tuple[FilterAct, ...], street: int) -> list[FilterAct]:
    last = row[-1]
    t = last.typ
    earlier_aggr = any(f.typ in (BET, RAISE) for f in row[:-1])
    if t == RAISE:
        types = [RAISE, CALL, FOLD] + ([CHECK] if street == 0 and not earlier_aggr else [])
    elif t == BET:
        types = [BET, FOLD] + ([] if earlier_aggr else [CHECK])
    elif t == CALL:
        types = [CALL, RAISE, FOLD]
    elif t == CHECK:
        types = [CHECK, BET if street > 0 else RAISE, FOLD]
    else:
        types = [FOLD, CALL, RAISE]
    req = last.req & _KEEP
    for flag, possible in _TO_POSSIBLE:
        if last.req & flag:
            req |= possible
    if t == RAISE:
        req |= P_RAISE
    elif t == BET:
        req |= P_BET
    elif t == CHECK:
        req |= P_CHECK
    call_lo = call_hi = None
    if last.lo is not None:
        if t != CALL:
            raise ValueError("amount filters on a measured bet/raise are not supported")
        call_lo, call_hi = last.lo, last.hi
    return [FilterAct(last.hero, typ, req, last.pos, None, None, last.bound, call_lo, call_hi, last.skip)
            for typ in types]


# ── matching ─────────────────────────────────────────────────────────────

OPP = 1
CASE = 2


def _fit(f: FilterAct, a, p: int, bind: int) -> int:
    """New binding if `a` fits `f` for player p, else _NOFIT."""
    if a.eff != f.typ:
        return _NOFIT
    if f.hero:
        if a.actor != p:
            return _NOFIT
    elif a.actor == p:
        return _NOFIT
    req = f.req
    if req and (a.flags & req) != req:
        return _NOFIT
    if f.pos is not None and a.pos not in f.pos:
        return _NOFIT
    if f.lo is not None:
        amt = a.amt_bb
        if amt < f.lo - AMOUNT_EPS or amt > f.hi + AMOUNT_EPS:
            return _NOFIT
    if f.call_lo is not None:
        amt = a.to_call_bb if a.to_call_bb < a.stack_left_bb else a.stack_left_bb
        if amt < f.call_lo - AMOUNT_EPS or amt > f.call_hi + AMOUNT_EPS:
            return _NOFIT
    if f.bound:
        if bind == _UNBOUND:
            return a.actor
        if a.actor != bind:
            return _NOFIT
    return bind


def _scan(f: FilterAct, acts, q: int, end: int, p: int, bind: int) -> tuple[int, int]:
    """Greedy: first action from q that fits f, skipping only folds/checks.

    A bound villain (V1) is checked after the action is taken: an action that
    fits everything but is made by another villain than the bound one ends
    the try instead of being skipped (H2N: flop "H:X > V1:X" does not match
    "Hero X, BB X, raiser X" when V1 is the raiser; Hand2Note's results confirm it).
    """
    while q < end:
        a = acts[q]
        nb = _fit(f, a, p, bind)
        if nb != _NOFIT:
            return q, nb
        if a.eff > CHECK and not (f.skip and a.actor != p and (f.skip == 2 or a.eff == CALL)):
            return -1, bind
        if f.bound and bind != _UNBOUND and _fit(f, a, p, _UNBOUND) != _NOFIT:
            return -1, bind
        q += 1
    return -1, bind


def _run(row, acts, end: int, p: int, start: int, bind: int, upto: int) -> tuple[int, int]:
    """Match row[:upto] from `start`; returns (index of the last matched action, bind) or (-1, _)."""
    b = _fit(row[0], acts[start], p, bind)
    if b == _NOFIT:
        return -1, bind
    q = start
    for k in range(1, upto):
        q, b = _scan(row[k], acts, q + 1, end, p, b)
        if q < 0:
            return -1, bind
    return q, b


def _starts(f: FilterAct, seq: HandSeq, street: int, p: int, end: int):
    """Candidate start indices for a row whose first filter action is f."""
    req = f.req
    if req & FR:
        i = seq.first_raise_idx[street]
        return (i,) if 0 <= i < end else ()
    if req & OPEN:
        i = seq.open_idx[street]
        return (i,) if 0 <= i < end else ()
    if f.hero:
        acts = seq.streets[street]
        typ = f.typ
        return [i for i in seq.own[p][street] if i < end and acts[i].eff == typ]
    return [i for i in seq.by_type[street][f.typ] if i < end]


def _part_case_binds(part: Part, seq: HandSeq, p: int, binds: tuple[int, ...]) -> tuple[int, ...]:
    street = part.street
    acts = seq.streets[street]
    end = seq.seq_end[p][street]
    n_own = len(seq.own[p][street])
    out: set[int] = set()
    for row, k, _last, _alts, n_hero in part.plans:
        if n_hero > n_own:
            continue
        starts = _starts(row[0], seq, street, p, end)
        for bind in binds:
            for s in starts:
                q, b = _run(row, acts, end, p, s, bind, k + 1)
                if q >= 0:
                    out.add(b)
    if not out:
        return ()
    if len(out) == 1:
        return (out.pop(),)
    return tuple(sorted(out))


def _last_part(part: Part, seq: HandSeq, p: int, binds: tuple[int, ...]):
    """(code, hit): code = OPP | CASE bits; hit = (street, index) or None.

    Each OR-ed row (and, for an opportunity, each alternative row) yields the
    hit of its first matching start; the result's hit is the **earliest** of
    those (H2N picks the earliest hit action among all rows that hit; Hand2Note's results,
    parity round 3: VPIP ``H:R | H:C`` on "Hero calls, then raises" hits the
    call). Case rows win over opportunity rows.
    """
    street = part.street
    acts = seq.streets[street]
    end = seq.seq_end[p][street]
    own = seq.own[p][street]
    n_own = len(own)
    case_hit = -1   # earliest case hit index so far
    opp_hit = -1    # earliest opportunity-only hit index so far
    single = len(part.plans) == 1 and len(binds) == 1
    for row, k, last, alts, n_hero in part.plans:
        if n_hero > n_own:
            continue
        for bind in binds:
            if k == 0:
                cands = own if last.hero else range(end)
                for s in cands:
                    if case_hit >= 0 and s >= case_hit:
                        break
                    if s < end and _fit(last, acts[s], p, bind) != _NOFIT:
                        case_hit = s
                        break
                if case_hit >= 0:
                    if single:
                        return OPP | CASE, (street, case_hit)
                    continue
                for alt in alts:
                    for s in cands:
                        if s >= end or (opp_hit >= 0 and s >= opp_hit):
                            break
                        if _fit(alt, acts[s], p, bind) != _NOFIT:
                            opp_hit = s
                            break
                continue
            # one hit per (row, bind): the first start that matches the row
            for s in _starts(row[0], seq, street, p, end):
                if case_hit >= 0 and s >= case_hit:
                    break
                pe, b = _run(row, acts, end, p, s, bind, k)
                if pe < 0:
                    continue
                q, _ = _scan(last, acts, pe + 1, end, p, b)
                if q >= 0:
                    if case_hit < 0 or q < case_hit:
                        case_hit = q
                    break
            if case_hit >= 0:
                if single:
                    return OPP | CASE, (street, case_hit)
                continue
            # one hit per (alternative row, bind)
            for alt in alts:
                for s in _starts(row[0], seq, street, p, end):
                    if opp_hit >= 0 and s >= opp_hit:
                        break
                    pe, b = _run(row, acts, end, p, s, bind, k)
                    if pe < 0:
                        continue
                    q, _ = _scan(alt, acts, pe + 1, end, p, b)
                    if q >= 0:
                        if opp_hit < 0 or q < opp_hit:
                            opp_hit = q
                        break
    if case_hit >= 0:
        return OPP | CASE, (street, case_hit)
    if opp_hit >= 0:
        return OPP, (street, opp_hit)
    return 0, None


def gate(d: StatDef, seq: HandSeq, p: int) -> bool:
    """Cheap necessary condition for an opportunity (see StatDef)."""
    has = seq.has_seq[p]
    for part in d.parts:
        if not has[part.street]:
            return False
    street = d.street
    own = seq.own[p][street]
    if len(own) < d.min_hero:
        return False
    acts = seq.streets[street]
    end = seq.seq_end[p][street]
    lead = d.lead
    if lead is not None:
        i = (seq.first_raise_idx if lead[0] == FR else seq.open_idx)[street]
        if i < 0 or i >= end:
            return False
        a = acts[i]
        if a.actor == p or (lead[1] is not None and a.pos not in lead[1]):
            return False
    types = d.anchor_types
    req = d.anchor_req
    for i in own:
        if i < end:
            a = acts[i]
            if (types >> a.eff) & 1 and (a.flags & req) == req:
                return True
    return False


def evaluate_code(d: StatDef, seq: HandSeq, p: int, cache: dict | None = None,
                  pre_cache: dict | None = None):
    """(code, hit) of definition `d` for player index `p` (code: OPP | CASE bits).

    `cache` memoises earlier street parts for this hand and player;
    `pre_cache` (optional) does the same for preflop parts and may be shared
    by hands with the same preflop signature.
    """
    parts = d.parts
    binds: tuple[int, ...] = (_UNBOUND,)
    if len(parts) > 1:
        has = seq.has_seq[p]
        for part in parts:
            if not has[part.street]:
                return 0, None
        for part in parts[:-1]:
            c = pre_cache if (part.street == 0 and pre_cache is not None) else cache
            if c is not None:
                key = (part.key, binds)
                nb = c.get(key)
                if nb is None:
                    nb = c[key] = _part_case_binds(part, seq, p, binds)
            else:
                nb = _part_case_binds(part, seq, p, binds)
            if not nb:
                return 0, None
            binds = nb
    elif not seq.has_seq[p][d.street]:
        return 0, None
    return _last_part(parts[-1], seq, p, binds)


def first_part_binds(d: StatDef, seq: HandSeq, p: int) -> tuple[int, ...]:
    """Villain bindings left by the first part of a multi-part definition
    matched as a case for player p (empty: it does not match)."""
    part = d.parts[0]
    if not seq.has_seq[p][part.street]:
        return ()
    return _part_case_binds(part, seq, p, (_UNBOUND,))


def evaluate_rest(d: StatDef, seq: HandSeq, p: int, binds: tuple[int, ...],
                  cache: dict | None = None):
    """`evaluate_code` of a multi-part definition whose first part already
    matched with `binds` (from `first_part_binds`); same result."""
    parts = d.parts
    has = seq.has_seq[p]
    for part in parts:
        if not has[part.street]:
            return 0, None
    for part in parts[1:-1]:
        if cache is not None:
            key = (part.key, binds)
            nb = cache.get(key)
            if nb is None:
                nb = cache[key] = _part_case_binds(part, seq, p, binds)
        else:
            nb = _part_case_binds(part, seq, p, binds)
        if not nb:
            return 0, None
        binds = nb
    return _last_part(parts[-1], seq, p, binds)


def evaluate(d: StatDef, seq: HandSeq, p: int, cache: dict | None = None) -> RowResult:
    """Case / opportunity of definition `d` for player index `p`."""
    code, hit = evaluate_code(d, seq, p, cache)
    return RowResult(bool(code & CASE), bool(code & OPP), hit)
