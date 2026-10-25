"""Stat popup and hands list of the H2N-style General screen.

    GET /api/general/cell/{cell_id}/detail
    GET /api/general/cell/{cell_id}/hands

Behaviour spec: docs/specs/H2N-COMPATIBLE-STATS.md section 6 (stat popup) and section 5
(winner, showdown). Same filters as
GET /api/general (app/api/general.py).

Data sources:

- Cases / opportunities, Won Hand / WTSD / W%SD and the Range histogram come
  straight from `hand_players` (H2N bitmasks, `is_winner`,
  `went_to_showdown`, `hv_*`), like the General grid.
- Everything that needs individual actions (hero's next decision, Boards,
  Bet Sizes, hand rows) re-parses the hand's `raw_text` with its site parser
  and reruns the matcher (`app.h2n.replay`), because the `actions` table is
  not populated. The per-hand results are packed into one int each and kept
  in an in-memory cache with one segment per (workspace, player, row), bounded
  by bytes (OHM_POPUP_CACHE_MB, default 128) and cleared on every data change
  (`data_generation.on_bump`), so only the first popup over a set of hands
  pays for the replay; later requests (other filters, the hands list) reuse
  them.

Only action cells (one matcher row) have a popup. Expression cells (4-Bet
Range, Aggression, WTSD, ...) are answered with 400.
"""

from __future__ import annotations

import gc
import logging
import math
import os
import sys
import threading
from collections import Counter, OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterable, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.app_settings import get_app_settings
from app.date_filters import bound_sql
from app import data_generation, marked_hands
from app.models import TagRef
from app.db import get_hero_player_id, get_read_cursor
from app.general_cells import GENERAL_CELLS, ActionCell
from app.general_filters import cell_steps, resolve_filters
from app.h2n.definitions import COMPILED
from app.h2n.replay import match_row, parser_for, replay_parsed
from app.h2n.seqcodec import decode_sequence
from app.h2n.rows import ROWS, sql_case, sql_opp
from app.h2n.sequence import (
    BET, CALL, CHECK, FOLD, P_BET, P_CALL, P_CHECK, P_RAISE, RAISE, STREET_NAMES,
    TYPE_LETTERS, Act, HandSeq,
)
from app.hand_value import (
    BOARD_CATEGORIES,
    OTHER,
    STREET_CATEGORIES,
    board_categories,
    category_info,
    classify_boards_for_player,
    parse_card,
    player_boards,
)

router = APIRouter()
log = logging.getLogger(__name__)

_BOARD_LEN = {1: 3, 2: 4, 3: 5}
_TYPE_KEYS = ("fold", "check", "call", "bet", "raise")   # index = action type
_NEXT_ORDER = (FOLD, CALL, RAISE, BET, CHECK)             # display order
_EPS = 1e-6

# ── response models (mirrored by frontend/src/lib/api-general.ts) ─────────


class Ratio(BaseModel):
    """cases / opps * 100; value null when opps == 0."""

    value: Optional[float] = None
    cases: int = 0
    opps: int = 0


class NextActions(BaseModel):
    """Hero's next decision after the stat action (H2N-COMPATIBLE-STATS.md 6.3).

    Display rule: Fold / Call / Raise only when `show_fold_call_raise`
    (fold opportunities > 0), Bet / Check only when `show_bet_check`
    (bet opportunities > 0); order Fold, Call, Raise, Bet, Check.
    """

    model_config = ConfigDict(populate_by_name=True)

    fold: Ratio = Ratio()
    call: Ratio = Ratio()
    raise_: Ratio = Field(default_factory=Ratio, alias="raise")
    bet: Ratio = Ratio()
    check: Ratio = Ratio()
    show_fold_call_raise: bool = False
    show_bet_check: bool = False


class StrengthBucket(BaseModel):
    """One hand-value category of the stat street (H2N-COMPATIBLE-STATS.md 6.4)."""

    index: int            # index in the street's category list, -1 = Other
    key: str
    label: str
    color: str
    weak: bool
    description: str
    count: int = 0
    pct: Optional[float] = None   # count / total * 100 (Range tab "Frequency, %")


class Strength(BaseModel):
    """Strength bar / Range histogram. `buckets` lists every category of the
    street in display order (zero counts included); "Other" only when it has
    hands. `weak_pct` is null when the histogram is empty."""

    street: str
    total: int = 0
    weak: int = 0
    weak_pct: Optional[float] = None
    buckets: list[StrengthBucket] = []


class Summary(BaseModel):
    won_hand: Ratio = Ratio()
    wtsd: Ratio = Ratio()
    wsd: Ratio = Ratio()
    next: NextActions = NextActions()


class SplitRow(BaseModel):
    """One row of the Boards or Bet Sizes tab."""

    key: str
    label: str
    value: Optional[float] = None
    cases: int = 0
    opps: int = 0
    strength: Optional[Strength] = None
    next: NextActions = NextActions()
    action: Optional[str] = None      # bet sizes: measured action type of the bucket


class CellDetail(BaseModel):
    cell_id: str
    row: str
    notation: str
    street: str                        # stat street: preflop / flop / turn / river
    player: Optional[str] = None
    player_id: Optional[int] = None
    value: Optional[float] = None
    cases: int = 0
    opps: int = 0
    strength: Optional[Strength] = None
    summary: Summary = Summary()
    boards: list[SplitRow] = []
    bet_sizes: list[SplitRow] = []
    replayed: int = 0                  # hands whose actions were replayed for this answer
    replay_failed: int = 0
    chain: list[dict] = []             # the cell as a Reports chain: filters + pos + row


class ActionToken(BaseModel):
    """One action in a street cell: letter + amount in bb (H2N-COMPATIBLE-STATS.md 6.7).

    `t`: X check, B bet, C call, R raise, F fold (raw type as written in the
    history). `amt_bb`: chips put in for B / C, the raise-to total for R,
    null for X / F. `allin` adds the apostrophe. `pos` is the actor's H2N
    column group (token colour), `hero` marks the stat owner's actions
    (dashed underline)."""

    t: str
    amt_bb: Optional[float] = None
    allin: bool = False
    pos: str = ""
    hero: bool = False
    player: str = ""


class StreetCell(BaseModel):
    street: str
    cards: list[list[str]] = []       # one group per distinct board (run it twice)
    pot_bb: Optional[float] = None    # initial pot of the street (gross), bb
    pot: Optional[float] = None       # same, money
    actions: list[ActionToken] = []


class HandValueLabel(BaseModel):
    index: int
    key: str
    label: str
    color: str


class HandRow(BaseModel):
    hand_id: str
    played_at: Optional[str] = None
    stakes: Optional[str] = None
    site_id: Optional[int] = None
    position: Optional[str] = None
    hand_value: list[HandValueLabel] = []   # stat street category, one per board
    hole_cards: list[str] = []
    streets: list[Optional[StreetCell]] = []   # preflop, flop, turn, river; null after hero folded
    won: Optional[float] = None
    won_bb: Optional[float] = None
    ev_diff_bb: Optional[float] = None
    marked: bool = False                     # marked for this player (marked hands)
    tags: list[TagRef] = []                  # the mark's tags, catalogue order
    error: Optional[str] = None


class CellHands(BaseModel):
    cell_id: str
    total: int = 0
    offset: int = 0
    limit: int = 50
    rows: list[HandRow] = []


# ── stat metadata ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Stat:
    cell_id: str
    cell: ActionCell
    row: str
    street: int
    types: frozenset[int]         # effective types of the measured (last) filter actions


def _resolve(cell_id: str) -> _Stat:
    cell = GENERAL_CELLS.get(cell_id)
    if cell is None:
        raise HTTPException(status_code=404, detail=f"Unknown cell {cell_id}")
    if not isinstance(cell, ActionCell):
        raise HTTPException(status_code=400,
                            detail=f"Cell {cell_id} is an expression and has no stat popup")
    row = cell.ref.row
    d = COMPILED[row]
    types = frozenset(r[-1].typ for r in d.parts[-1].rows)
    return _Stat(cell_id, cell, row, d.street, types)


# ── bet size buckets (H2N-COMPATIBLE-STATS.md 6.6) ──

_INF = math.inf


@dataclass(frozen=True)
class _Bucket:
    id: str               # our own stable key, used by the API
    label: str
    typ: int
    preflop: bool
    lo: float
    hi: float
    units: str            # "pot" | "prev" | "bb"
    not_allin: bool       # the action must not be (almost) all-in
    min_spr: float        # effective stack in the same units must be >= this


_BUCKETS: tuple[_Bucket, ...] = (
    _Bucket("bet_overbet", "Overbet", BET, False, 1.001, _INF, "pot", False, 1.25),
    _Bucket("bet_80_100", "0.8-1 pot", BET, False, 0.8, 1.0, "pot", False, 1.25),
    _Bucket("bet_60_80", "0.6-0.8 pot", BET, False, 0.6, 0.799, "pot", False, 1.25),
    _Bucket("bet_40_60", "0.4-0.6 pot", BET, False, 0.4, 0.599, "pot", False, 1.25),
    _Bucket("bet_25_40", "0.25-0.4 pot", BET, False, 0.251, 0.399, "pot", False, 1.25),
    _Bucket("bet_le_25", "≤ 0.25 pot", BET, False, 0.0, 0.25, "pot", False, 1.25),
    _Bucket("raise_min", "Min Raise", RAISE, False, 1.0, 2.0, "prev", True, 1.25),
    _Bucket("call_vs_overbet", "Call vs. overbet", CALL, False, 1.001, _INF, "pot", False, 0.0),
    _Bucket("call_vs_75_100", "Call vs. 0.75-1 pot", CALL, False, 0.75, 1.0, "pot", False, 0.0),
    _Bucket("call_vs_le_60", "Call vs. bet ≤ 0.6 pot", CALL, False, 0.0, 0.6, "pot", False, 0.0),
    _Bucket("fold_vs_overbet", "Fold vs. overbet", FOLD, False, 1.001, _INF, "pot", False, 0.0),
    _Bucket("fold_vs_75_100", "Fold vs. 0.75-1 pot", FOLD, False, 0.75, 1.0, "pot", False, 0.0),
    _Bucket("fold_vs_le_60", "Fold vs. bet ≤ 0.6 pot", FOLD, False, 0.0, 0.6, "pot", False, 0.0),
    _Bucket("pre_raise_2_25x", "Raise 2-2.5x", RAISE, True, 2.0, 2.5, "prev", True, 1.25),
    _Bucket("pre_raise_25_3x", "Raise 2.51-3x", RAISE, True, 2.51, 3.0, "prev", True, 1.25),
    _Bucket("pre_raise_lt_22bb", "Raise <2.2bb", RAISE, True, 2.0, 2.2, "bb", True, 1.25),
    _Bucket("pre_raise_22_27bb", "Raise 2.2-2.7bb", RAISE, True, 2.21, 2.7, "bb", True, 1.25),
    _Bucket("pre_raise_27_3bb", "Raise 2.7-3bb", RAISE, True, 2.71, 3.0, "bb", True, 1.25),
    _Bucket("pre_raise_gt_3bb", "Raise > 3bb", RAISE, True, 3.01, _INF, "bb", True, 1.25),
)
_BUCKET_BY_ID = {b.id: b for b in _BUCKETS}


def _stat_buckets(stat: _Stat) -> tuple[_Bucket, ...]:
    """Buckets whose action type and street stage match the measured action."""
    pre = stat.street == 0
    return tuple(b for b in _BUCKETS if b.preflop == pre and b.typ in stat.types)


# Alternatives of an effective type (H2N-COMPATIBLE-STATS.md 6.3), postflop / preflop.
_ALTS_POST = {BET: (CHECK,), CHECK: (BET,), FOLD: (CALL, RAISE), CALL: (FOLD, RAISE),
              RAISE: (FOLD, CALL)}
_ALTS_PRE = {CHECK: (RAISE,), RAISE: (FOLD, CALL, CHECK), FOLD: (CALL, RAISE),
             CALL: (FOLD, RAISE), BET: (CHECK,)}


def _alts(typ: int, street: int) -> tuple[int, ...]:
    return (_ALTS_PRE if street == 0 else _ALTS_POST).get(typ, ())


def _possible(a: Act) -> int:
    """Bit mask (1 << type) of the effective types possible at action a (3.0)."""
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


def _rd(x: float) -> float:
    """Ratios are rounded to 7 decimals before they are compared (Hand2Note does too)."""
    return round(x, 7)


def _contains(lo: float, hi: float, x: float) -> bool:
    return lo - _EPS <= x <= hi + _EPS


def _touches(lo: float, hi: float, a: float, b: float) -> bool:
    return a <= hi + _EPS and lo <= b + _EPS


class _ActState:
    """Street state at one action, for bet sizing (all amounts in bb)."""

    __slots__ = ("own_bet", "eff_pot", "eff_stack", "level", "min_raise_to", "prev")

    def __init__(self, own_bet, eff_pot, eff_stack, level, min_raise_to, prev):
        self.own_bet = own_bet
        self.eff_pot = eff_pot          # pot before the action, minus what he can't cover
        self.eff_stack = eff_stack      # effective stack incl. his street bet
        self.level = level              # highest bet on the street before the action
        self.min_raise_to = min_raise_to
        self.prev = prev                # index of the previous VPIP action on the street, or None


def _street_states(seq: HandSeq, street: int, upto: int | None = None) -> list[_ActState]:
    """Per action of the street: pot net of what the actor can't cover,
    effective stack, bet level, legal minimum raise-to and the previous VPIP
    action. Players who have not acted yet are assumed to have no street bet
    beyond what the pot already holds (their blinds only matter when the
    actor can't cover them). With `upto`, only actions 0..upto (each state
    depends on the earlier actions only)."""
    bb = seq.bb
    acts = seq.streets[street]
    if upto is not None:
        acts = acts[:upto + 1]
    bets: dict[int, float] = {}
    level = 1.0 if street == 0 else 0.0   # preflop the big blind is the bet to call
    min_inc = 1.0                          # minimum raise increment (a big blind, then the last full raise)
    prev: int | None = None
    out: list[_ActState] = []
    for i, a in enumerate(acts):
        own = (a.to - a.inc) / bb
        bets.setdefault(a.actor, own)
        cap = own + a.stack_left / bb
        dead = 0.0
        actor = a.actor
        for q, v in bets.items():
            if v > cap and q != actor:
                dead += v - cap
        lvl = max(level, own + a.to_call / bb)
        out.append(_ActState(own, a.pot / bb - dead, cap, lvl, min(lvl + min_inc, cap), prev))
        to = a.to / bb
        if a.eff in (BET, RAISE) and to > lvl + 1e-9:
            if to - lvl >= min_inc - 1e-9:    # a full bet / raise resets the minimum
                min_inc = to - lvl
            level = to
        elif to > level:
            level = to
        bets[a.actor] = to
        if a.raw >= CALL:
            prev = i
    return out


def _amount_eff(a: Act) -> float:
    """Effective amount in bb (H2N-COMPATIBLE-STATS.md 2.4): raise-to for
    raises, chips put in otherwise."""
    if a.eff in (BET, RAISE):
        return a.amt_bb
    return min(a.inc_bb, a.stack_left_bb) if a.stack_left > 0 else a.inc_bb


def _to_call_eff(a: Act, st: _ActState) -> float:
    return min(a.to_call_bb, st.eff_stack)


def _amount_units(a: Act, st: _ActState, units: str, prev_amt: float | None) -> float | None:
    amt = _amount_eff(a)
    if units == "bb":
        return _rd(amt)
    if units == "prev":
        if not prev_amt:
            return None
        return _rd(amt / prev_amt)
    if st.eff_pot <= 0:
        return None
    if a.eff == RAISE:
        tc = _to_call_eff(a, st)
        return _rd((amt - tc) / (st.eff_pot + tc))
    return _rd(amt / st.eff_pot)


def _stack_units(st: _ActState, units: str, prev_amt: float | None) -> float | None:
    if units == "bb":
        return _rd(st.eff_stack)
    if units == "prev":
        return _rd(st.eff_stack / prev_amt) if prev_amt else None
    return _rd(st.eff_stack / st.eff_pot) if st.eff_pot > 0 else None


def _size_hits(seq: HandSeq, hit: tuple[int, int], buckets: tuple[_Bucket, ...]
               ) -> tuple[tuple[int, bool], ...]:
    """(bucket id, is case) for every bucket the decision at `hit` is a case
    or an opportunity of (H2N-COMPATIBLE-STATS.md 6.6)."""
    if not buckets:
        return ()
    street, idx = hit
    acts = seq.streets[street]
    states = _street_states(seq, street, idx)
    a = acts[idx]
    st = states[idx]
    prev = acts[st.prev] if st.prev is not None else None
    prev_amt = _amount_eff(prev) if prev is not None else None
    allin = min(a.inc_bb, a.stack_left_bb) >= a.stack_left_bb - 1.5 - _EPS if a.inc > 0 else False
    poss = _possible(a)
    alts = _alts(a.eff, street)
    # The per-bucket values only depend on the units (and the bucket type for
    # the possible range): computed once per units.
    prev_amts: dict[str, float | None] = {}
    stacks: dict[str, float | None] = {}
    amts: dict[str, float | None] = {}
    ranges: dict[tuple[bool, str], tuple[float, float] | None] = {}
    out: list[tuple[int, bool]] = []
    for b in buckets:
        if b.preflop != (street == 0):
            continue
        units = b.units
        if units == "prev" and prev is None:
            continue
        if b.typ in (CALL, FOLD):
            # measured on the previous VPIP action of the street (the bet faced)
            if prev is None:
                continue
            if units in prev_amts:
                amt = prev_amts[units]
            else:
                amt = prev_amts[units] = _amount_units(prev, states[st.prev], units, None)
            if amt is None or not _contains(b.lo, b.hi, amt):
                continue
            if a.eff == b.typ:
                out.append((b.id, True))
            elif b.typ in alts:
                out.append((b.id, False))
            continue
        if units in stacks:
            stack = stacks[units]
        else:
            stack = stacks[units] = _stack_units(st, units, prev_amt)
        if stack is None or stack < b.min_spr - _EPS:
            continue
        if a.eff == b.typ:
            if units in amts:
                amt = amts[units]
            else:
                amt = amts[units] = _amount_units(a, st, units, prev_amt)
            if amt is not None and _contains(b.lo, b.hi, amt) and not (b.not_allin and allin):
                out.append((b.id, True))
                continue
        if b.typ != a.eff and b.typ not in alts:
            continue
        if not poss >> b.typ & 1:
            continue
        rkey = (b.typ == BET, units)
        if rkey in ranges:
            rng = ranges[rkey]
        else:
            rng = ranges[rkey] = _possible_range(a, st, b, prev_amt)
        if rng is not None and _touches(b.lo, b.hi, *rng):
            out.append((b.id, False))
    return tuple(out)


def _possible_range(a: Act, st: _ActState, b: _Bucket, prev_amt: float | None
                    ) -> tuple[float, float] | None:
    behind = a.stack_left_bb
    if b.typ == BET:
        if behind <= 0:
            return None
        lo, hi = min(1.0, behind), behind
        if b.units == "pot":
            if st.eff_pot <= 0:
                return None
            return _rd(lo / st.eff_pot), _rd(hi / st.eff_pot)
        if b.units == "bb":
            return _rd(lo), _rd(hi)
        return (_rd(lo / prev_amt), _rd(hi / prev_amt)) if prev_amt else (0.0, 0.0)
    # raise-to range
    lo, hi = st.min_raise_to, st.eff_stack
    if hi <= 0:
        return None
    if b.units == "bb":
        return _rd(lo), _rd(hi)
    if b.units == "prev":
        return (_rd(lo / prev_amt), _rd(hi / prev_amt)) if prev_amt else (0.0, 0.0)
    tc = _to_call_eff(a, st)
    den = st.eff_pot + tc
    if den <= 0:
        return None
    return _rd((lo - tc) / den), _rd((hi - tc) / den)


# ── hero's next decision (H2N-COMPATIBLE-STATS.md 6.3) ──────────────────


class _Flat:
    """All actions of a hand in order (streets concatenated)."""

    __slots__ = ("acts", "gidx", "next_vpip", "next_nonfold")

    def __init__(self, seq: HandSeq):
        acts: list[Act] = []
        gidx: dict[tuple[int, int], int] = {}
        for s in range(4):
            for i, a in enumerate(seq.streets[s]):
                gidx[(s, i)] = len(acts)
                acts.append(a)
        n = len(acts)
        next_vpip: list[int | None] = [None] * n
        next_nonfold: list[int | None] = [None] * n
        nv = nn = None
        for g in range(n - 1, -1, -1):
            next_vpip[g] = nv
            next_nonfold[g] = nn
            a = acts[g]
            if a.raw >= CALL:
                nv = g
            if a.eff != FOLD:
                nn = g
        self.acts = acts
        self.gidx = gidx
        self.next_vpip = next_vpip
        self.next_nonfold = next_nonfold


def _relevant(f: _Flat, g: int, hero: int) -> int | None:
    """The next relevant action after action g (H2N-COMPATIBLE-STATS.md 6.3)."""
    acts = f.acts
    if g + 1 >= len(acts):
        return None
    x = acts[g]
    e = x.eff
    if e == BET or e == RAISE:
        v = f.next_vpip[g]
        return v if v is not None else g + 1
    if e == CHECK:
        v = f.next_vpip[g]
        if v is not None and acts[v].street == x.street:
            return v
        return g + 1
    if e == CALL:
        nn = f.next_nonfold[g]
        if nn is None:
            return g + 1
        n_act = acts[nn]
        if n_act.street > x.street:
            if n_act.eff == CHECK and (x.actor == hero or n_act.actor != hero):
                return _relevant(f, nn, hero)
            return nn
        v = f.next_vpip[g]
        if v is None:
            return nn
        if acts[v].street == x.street:
            return v
        return None
    return None


def _hero_next(f: _Flat, g: int, hero: int) -> tuple[int, int] | None:
    """(effective type, opportunity type mask) of hero's next decision after
    the measured action at global index g, or None (3.1 steps 1-3, 3.2)."""
    acts = f.acts
    if acts[g].eff == FOLD or g + 1 >= len(acts):
        return None
    r = _relevant(f, g, hero)
    if r is None:
        return None
    x = _relevant(f, r, hero)
    while x is not None and acts[x].actor != hero and acts[x].eff == FOLD:
        x = x + 1 if x + 1 < len(acts) else None
    h = None
    while x is not None:
        if acts[x].actor == hero:
            h = x
            break
        x = _relevant(f, x, hero)
    if h is None:
        return None
    ra = acts[r]
    if not _possible(ra) >> ra.raw & 1:     # step 3: R's raw type must have been possible
        return None
    return _count_mask(acts[h])


def _direct_next(f: _Flat, g: int, hero: int) -> tuple[int, int] | None:
    """Hero's very next action after g (Boards / Bet Sizes rows, 5.2)."""
    acts = f.acts
    if acts[g].eff == FOLD:
        return None
    for x in range(g + 1, len(acts)):
        if acts[x].actor == hero:
            return _count_mask(acts[x])
    return None


def _count_mask(h: Act) -> tuple[int, int]:
    poss = _possible(h)
    mask = 1 << h.eff
    for t in _alts(h.eff, h.street):
        if poss >> t & 1:
            mask |= 1 << t
    return h.eff, mask


class _NextCounter:
    __slots__ = ("cases", "opps")

    def __init__(self):
        self.cases = [0] * 5
        self.opps = [0] * 5

    def add(self, nxt: tuple[int, int] | None, n: int = 1) -> None:
        if nxt is None:
            return
        eff, mask = nxt
        self.cases[eff] += n
        for t in range(5):
            if mask >> t & 1:
                self.opps[t] += n

    def model(self) -> NextActions:
        r = {_TYPE_KEYS[t]: _ratio(self.cases[t], self.opps[t]) for t in range(5)}
        return NextActions(fold=r["fold"], call=r["call"], raise_=r["raise"], bet=r["bet"],
                           check=r["check"], show_fold_call_raise=self.opps[FOLD] > 0,
                           show_bet_check=self.opps[BET] > 0)


def _ratio(cases: int, opps: int) -> Ratio:
    return Ratio(value=cases / opps * 100.0 if opps else None, cases=cases, opps=opps)


# ── per-hand replay records + byte-bounded cache ──────────────────────────


@dataclass(frozen=True, slots=True)
class _Rec:
    """What the popup needs from one replayed hand (for one player and row)."""

    case: bool
    textures: tuple[tuple[int, ...], ...]       # per board: stat-street board categories
    cats: tuple[int | None, ...]                # per board: stat-street hand value (cases)
    nxt: tuple[int, int] | None                 # hero's next decision (summary row)
    direct: tuple[int, int] | None              # hero's very next action (Boards / Sizes)
    sizes: tuple[tuple[str, bool], ...]         # (bucket key, case) over every bucket


# Records are cached packed into one int (bit layout below, low bits first); 0 means "replay
# failed or the hand is not an opportunity after all". Ints are ~30-40 bytes, a _Rec with its
# tuples 0.6-1.3 KB; equal ints also let the aggregation count each distinct record once.
#   valid 1 | case 1 | nxt 8 | direct 8 | size cases NB | size opps NB | n textures 4 | n cats 4
#   | textures TEX_W each | cats CAT_W each (hand value index + 2, 0 = None)
_NONE = 0
_NB = len(_BUCKETS)
_BUCKET_INDEX = {b.id: i for i, b in enumerate(_BUCKETS)}
_TEX_W = max(len(v) for v in BOARD_CATEGORIES.values())
_CAT_W = max(len(v) for v in STREET_CATEGORIES.values()).bit_length() + 1
_SH_NXT, _SH_DIRECT, _SH_SC = 2, 10, 18
_SH_SO = _SH_SC + _NB
_SH_NT = _SH_SO + _NB
_SH_NC = _SH_NT + 4
_SH_BOARDS = _SH_NC + 4


def _code_next(n: tuple[int, int] | None) -> int:
    return 0 if n is None else 1 + (n[0] << 5 | n[1])     # type 0..4, mask < 32: 1..160


def _decode_next(c: int) -> tuple[int, int] | None:
    return None if c == 0 else ((c - 1) >> 5, (c - 1) & 31)


def _pack(rec: _Rec | None) -> int:
    if rec is None:
        return _NONE
    if len(rec.textures) > 15 or len(rec.cats) > 15:
        raise ValueError("too many boards")
    v = 1 | rec.case << 1 | _code_next(rec.nxt) << _SH_NXT | _code_next(rec.direct) << _SH_DIRECT
    for bid, is_case in rec.sizes:
        v |= 1 << (_BUCKET_INDEX[bid] + (_SH_SC if is_case else _SH_SO))
    v |= len(rec.textures) << _SH_NT | len(rec.cats) << _SH_NC
    sh = _SH_BOARDS
    for tex in rec.textures:
        for c in tex:
            v |= 1 << (sh + c)
        sh += _TEX_W
    for cat in rec.cats:
        v |= (0 if cat is None else cat + 2) << sh
        sh += _CAT_W
    return v


def _unpack(v: int) -> _Rec | None:
    if not v:
        return None
    sizes = []
    for i, b in enumerate(_BUCKETS):
        if v >> (_SH_SC + i) & 1:
            sizes.append((b.id, True))
        elif v >> (_SH_SO + i) & 1:
            sizes.append((b.id, False))
    n_tex = v >> _SH_NT & 15
    n_cats = v >> _SH_NC & 15
    sh = _SH_BOARDS
    textures = []
    for _ in range(n_tex):
        m = v >> sh
        textures.append(tuple(c for c in range(_TEX_W) if m >> c & 1))
        sh += _TEX_W
    cats = []
    for _ in range(n_cats):
        c = v >> sh & ((1 << _CAT_W) - 1)
        cats.append(None if c == 0 else c - 2)
        sh += _CAT_W
    return _Rec(bool(v >> 1 & 1), tuple(textures), tuple(cats),
                _decode_next(v >> _SH_NXT & 255), _decode_next(v >> _SH_DIRECT & 255), tuple(sizes))


def _pack_case(v: int) -> bool:
    return bool(v >> 1 & 1)


_DEFAULT_BUDGET_MB = 128


class _Segment:
    __slots__ = ("recs", "kv", "bytes")

    def __init__(self):
        self.recs: dict[str, int] = {}
        self.kv = 0          # bytes of the keys and values
        self.bytes = 0       # kv + the dict itself


class _RecordCache:
    """Packed replay records, one segment (hand id -> packed int) per (workspace, player, row).

    Bounded by an estimate of the bytes held (sys.getsizeof of the dicts, keys and values),
    evicting whole segments least recently used. A segment larger than `max_segment` (half
    the budget by default) is dropped and not cached again until the next clear: one
    oversized cell must not flush every other cell just to be evicted by the next one.
    """

    def __init__(self, budget: int, max_segment: int | None = None):
        self.budget = budget
        self.max_segment = budget // 2 if max_segment is None else max_segment
        self._segs: OrderedDict[tuple, _Segment] = OrderedDict()
        self._too_big: set[tuple] = set()
        self._bytes = 0
        self._lock = threading.Lock()

    def segment(self, key: tuple) -> dict[str, int]:
        """The segment's records (read-only for the caller; may be empty)."""
        with self._lock:
            seg = self._segs.get(key)
            if seg is None:
                return {}
            self._segs.move_to_end(key)
            return seg.recs

    def add(self, key: tuple, items: list[tuple[str, int]]) -> None:
        if not items:
            return
        size = sys.getsizeof
        with self._lock:
            if key in self._too_big:
                return
            seg = self._segs.get(key)
            if seg is None:
                seg = self._segs[key] = _Segment()
            else:
                self._segs.move_to_end(key)
            recs = seg.recs
            kv = 0
            for hid, v in items:
                if hid not in recs:
                    recs[hid] = v
                    kv += size(hid) + size(v)
            seg.kv += kv
            new = size(recs) + seg.kv
            self._bytes += new - seg.bytes
            seg.bytes = new
            if new > self.max_segment:
                del self._segs[key]
                self._bytes -= new
                self._too_big.add(key)
                return
            while self._bytes > self.budget and len(self._segs) > 1:
                _, old = self._segs.popitem(last=False)
                self._bytes -= old.bytes

    def clear(self) -> None:
        with self._lock:
            self._segs.clear()
            self._too_big.clear()
            self._bytes = 0

    def stats(self) -> dict:
        with self._lock:
            return {"records": sum(len(s.recs) for s in self._segs.values()),
                    "bytes": self._bytes, "segments": len(self._segs),
                    "skipped": len(self._too_big)}


def _budget_from_env() -> int:
    try:
        mb = float(os.environ.get("OHM_POPUP_CACHE_MB", _DEFAULT_BUDGET_MB))
    except ValueError:
        mb = _DEFAULT_BUDGET_MB
    return int(mb * 1024 * 1024)


_RECORDS = _RecordCache(_budget_from_env())


@data_generation.on_bump
def clear_cache() -> None:
    """Drop every cached replay record (on every data change: import, clear, rebuild,
    workspace delete; and in tests)."""
    _RECORDS.clear()


def cache_stats() -> dict:
    return _RECORDS.stats()


def _parse(raw_text: str, site_id: int):
    parsed = parser_for(int(site_id)).parse_hand_history(raw_text)
    return parsed, replay_parsed(parsed)


def _compute_record(parsed, seq: HandSeq, username: str, row: str, street: int) -> _Rec | None:
    res = match_row(seq, row, username)
    if res is None or not res.opp or res.hit is None:
        return None
    p = seq.index[username]
    textures: tuple[tuple[int, ...], ...] = ()
    cats: tuple[int | None, ...] = ()
    if street > 0:
        sname = STREET_NAMES[street]
        n = _BOARD_LEN[street]
        boards = player_boards(parsed)
        textures = tuple(tuple(board_categories(b[:n], sname)) if len(b) >= n else ()
                         for b in boards)
        if res.case:
            cats = tuple(c.get(f"hv_{sname}") for c in classify_boards_for_player(parsed, username))
    nxt = direct = None
    if res.case:
        flat = _Flat(seq)
        g = flat.gidx[res.hit]
        nxt = _hero_next(flat, g, p)
        direct = _direct_next(flat, g, p)
    pre = street == 0
    sizes = _size_hits(seq, res.hit, tuple(b for b in _BUCKETS if b.preflop == pre))
    return _Rec(res.case, textures, cats, nxt, direct, sizes)


def _fetch_raw(db, workspace_id: int, ids: list[str]) -> dict[str, tuple[str, int]]:
    out: dict[str, tuple[str, int]] = {}
    for i in range(0, len(ids), 5000):
        chunk = ids[i:i + 5000]
        for hid, raw, site in db.execute(
            "SELECT id, raw_text, site_id FROM hands "
            "WHERE workspace_id = ? AND id IN (SELECT UNNEST(?::VARCHAR[]))",
            [workspace_id, chunk],
        ).fetchall():
            out[hid] = (raw, site)
    return out


def _fetch_seqs(db, workspace_id: int, ids: list[str]) -> dict[str, bytes]:
    """Stored H2N sequences (`hand_players.h2n_seq`, one row per hand) by hand id."""
    out: dict[str, bytes] = {}
    for i in range(0, len(ids), 5000):
        chunk = ids[i:i + 5000]
        for hid, blob in db.execute(
            "SELECT hand_id, h2n_seq FROM hand_players "
            "WHERE workspace_id = ? AND h2n_seq IS NOT NULL "
            "AND hand_id IN (SELECT UNNEST(?::VARCHAR[]))",
            [workspace_id, chunk],
        ).fetchall():
            out[hid] = blob
    return out


def _records(db, workspace_id: int, player_id: int, username: str, row: str, street: int,
             hand_ids: Iterable[str]) -> tuple[dict[str, int], int, int]:
    """Packed replay records of the player's hands: (by hand id, replayed, failed).

    The result holds no entry for a hand whose replay failed or that is no opportunity.
    Preflop rows only need the action sequence, which the import stored
    (`hand_players.h2n_seq`): decoding it is ~25x cheaper than re-parsing the
    hand history. Postflop rows also need the boards and hole cards, and
    hands without a usable stored sequence (older imports) are re-parsed.
    """
    key = (workspace_id, player_id, row)
    cached = _RECORDS.segment(key)
    out: dict[str, int] = {}
    missing: list[str] = []
    for hid in hand_ids:
        v = cached.get(hid)
        if v is None:
            missing.append(hid)
        elif v:
            out[hid] = v
    failed = 0
    if missing:
        with _gc_paused():
            done = _replay_missing(db, workspace_id, username, row, street, missing)
        for hid, v in done:
            if v:
                out[hid] = v
            else:
                failed += 1
        _RECORDS.add(key, done)
    return out, len(missing), failed


@contextmanager
def _gc_paused():
    """Pause the cyclic GC while replaying a batch of hands.

    The replay allocates many short-lived objects; with large record caches
    alive, the collections it triggers cost more than the replay itself.
    Nothing it builds is cyclic garbage, so collection can wait.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def _safe_pack(hid: str, rec: _Rec | None) -> int:
    try:
        return _pack(rec)
    except ValueError:
        log.warning("popup record of hand %s cannot be stored", hid)
        return _NONE


def _replay_missing(db, workspace_id: int, username: str, row: str, street: int,
                    missing: list[str]) -> list[tuple[str, int]]:
    """(hand id, packed record) for every hand not in the cache."""
    todo: list[str] = []
    done: list[tuple[str, int]] = []
    if street == 0:
        blobs = _fetch_seqs(db, workspace_id, missing)
        for hid in missing:
            seq = None
            blob = blobs.get(hid)
            if blob is not None:
                try:
                    seq = decode_sequence(blob)
                except Exception:
                    log.warning("stored sequence of hand %s is unreadable", hid, exc_info=True)
            if seq is None:
                todo.append(hid)
                continue
            rec = None
            try:
                rec = _compute_record(None, seq, username, row, street)
            except Exception:
                log.warning("popup replay failed for hand %s", hid, exc_info=True)
            done.append((hid, _safe_pack(hid, rec)))
    else:
        todo = missing
    if todo:
        raw = _fetch_raw(db, workspace_id, todo)
        for hid in todo:
            rec = None
            src = raw.get(hid)
            if src and src[0]:
                try:
                    parsed, seq = _parse(*src)
                    rec = _compute_record(parsed, seq, username, row, street)
                except Exception:
                    log.warning("popup replay failed for hand %s", hid, exc_info=True)
            done.append((hid, _safe_pack(hid, rec)))
    return done


# ── SQL ───────────────────────────────────────────────────────────────────


def _filters(stakes, game_mode, date_from, date_to, day_start: int = 0) -> tuple[str, list]:
    """Same filters as GET /api/general."""
    sql = ""
    params: list = []
    if stakes:
        sql += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        sql += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        frag, val = bound_sql("from", date_from, day_start)
        sql += " AND " + frag
        params.append(val)
    if date_to:
        frag, val = bound_sql("to", date_to, day_start)
        sql += " AND " + frag
        params.append(val)
    return sql, params


@dataclass
class _Hand:
    hand_id: str
    played_at: object
    stakes: str | None
    site_id: int | None
    username: str
    pos: str | None
    case: bool
    sd: bool
    win: bool
    hv: int | None               # stat-street hand value (first board)
    won: float | None
    won_bb: float | None
    ev_bb: float | None


def _query_hands(db, stat: _Stat, player_id: int, workspace_id: int, filters: tuple[str, list],
                 cases_only: bool) -> list[_Hand]:
    ref = stat.cell.ref
    where = ["hp.player_id = ?", "h.workspace_id = ?", "COALESCE(hp.h2n_valid, TRUE)"]
    params: list = [player_id, workspace_id]
    bit = sql_case(stat.row) if cases_only else sql_opp(stat.row)
    where.append(f"{bit} = 1")
    if ref.positions is not None:
        marks = ", ".join("?" for _ in ref.positions)
        if ref.exclude:
            where.append(f"(hp.h2n_pos IS NULL OR hp.h2n_pos NOT IN ({marks}))")
        else:
            where.append(f"hp.h2n_pos IN ({marks})")
        params.extend(ref.positions)
    hv = f"hp.hv_{STREET_NAMES[stat.street]}" if stat.street > 0 else "NULL"
    fsql, fparams = filters
    rows = db.execute(f"""
        SELECT h.id, h.played_at, h.stakes, h.site_id, p.username, hp.h2n_pos,
               {sql_case(stat.row)}, COALESCE(hp.went_to_showdown, FALSE),
               COALESCE(hp.is_winner, FALSE), {hv}, hp.won, hp.won_bb,
               COALESCE(hp.all_in_ev_bb, hp.won_bb)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN players p ON p.id = hp.player_id
        WHERE {" AND ".join(where)}{fsql}
    """, params + fparams).fetchall()
    return [
        _Hand(r[0], r[1], r[2], r[3], r[4], r[5], bool(r[6]), bool(r[7]), bool(r[8]),
              None if r[9] is None else int(r[9]),
              None if r[10] is None else float(r[10]),
              None if r[11] is None else float(r[11]),
              None if r[12] is None else float(r[12]))
        for r in rows
    ]


def _target_player(db, workspace_id: int, player_id: int | None) -> int | None:
    if player_id is not None:
        if not db.execute("SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
            raise HTTPException(status_code=404, detail="Player not found")
        return player_id
    return get_hero_player_id(db, workspace_id)


# ── aggregation ───────────────────────────────────────────────────────────


def _strength(street: int, counts: dict[int, int]) -> Strength:
    sname = STREET_NAMES[street]
    total = sum(counts.values())
    buckets: list[StrengthBucket] = []
    weak = 0
    indices = list(range(len(STREET_CATEGORIES[sname])))
    if counts.get(OTHER):
        indices.append(OTHER)
    for i in indices:
        info = category_info(sname, i)
        n = counts.get(i, 0)
        if info["weak"]:
            weak += n
        buckets.append(StrengthBucket(index=i, count=n, pct=n / total * 100.0 if total else None,
                                      **info))
    return Strength(street=sname, total=total, weak=weak,
                    weak_pct=weak / total * 100.0 if total else None, buckets=buckets)


def _aggregate(stat: _Stat, groups: Counter, buckets: tuple[_Bucket, ...]
               ) -> tuple[_NextCounter, list[SplitRow], list[SplitRow]]:
    """Summary next decision, Boards and Bet Sizes rows from the replayed hands.

    `groups` counts the replayed hands by (packed record << 1 | case bit of the cell): equal
    records add up in one step.
    """
    street = stat.street
    post = street > 0
    summary_next = _NextCounter()
    if post:
        cats = BOARD_CATEGORIES[STREET_NAMES[street]]
        b_opps = [0] * len(cats)
        b_cases = [0] * len(cats)
        b_bars: list[dict[int, int]] = [{} for _ in cats]
        b_next = [_NextCounter() for _ in cats]
    ids = {b.id for b in buckets}
    s_opps = {b.id: 0 for b in buckets}
    s_cases = {b.id: 0 for b in buckets}
    s_bars: dict[str, dict[int, int]] = {b.id: {} for b in buckets}
    s_next = {b.id: _NextCounter() for b in buckets}
    for key, n in groups.items():
        case = key & 1
        rec = _unpack(key >> 1)
        if case:
            summary_next.add(rec.nxt, n)
        if post:
            seen: set[int] = set()
            for tex in rec.textures:
                seen.update(tex)
            for c in seen:
                b_opps[c] += n
                if case:
                    b_cases[c] += n
                    b_next[c].add(rec.direct, n)
            if case:
                for tex, cat in zip(rec.textures, rec.cats):
                    if cat is None:
                        continue
                    for c in tex:
                        b_bars[c][cat] = b_bars[c].get(cat, 0) + n
        if buckets:
            for bid, is_case in rec.sizes:
                if bid not in ids:
                    continue
                s_opps[bid] += n
                if is_case and case:
                    s_cases[bid] += n
                    s_next[bid].add(rec.direct, n)
                    for cat in rec.cats:
                        if cat is not None:
                            s_bars[bid][cat] = s_bars[bid].get(cat, 0) + n

    boards: list[SplitRow] = []
    if post:
        for c, bc in enumerate(cats):
            if not b_opps[c]:
                continue
            boards.append(SplitRow(
                key=bc.key, label=bc.label, cases=b_cases[c], opps=b_opps[c],
                value=b_cases[c] / b_opps[c] * 100.0, strength=_strength(street, b_bars[c]),
                next=b_next[c].model(),
            ))

    sizes: list[SplitRow] = []
    for b in buckets:
        opps = s_opps[b.id]
        # bet / raise buckets need a case; call / fold buckets any sample
        visible = s_cases[b.id] > 0 if b.typ in (BET, RAISE, CHECK) else opps > 0
        if not visible:
            continue
        sizes.append(SplitRow(
            key=b.id, label=b.label, action=_TYPE_KEYS[b.typ], cases=s_cases[b.id],
            opps=opps, value=s_cases[b.id] / opps * 100.0 if opps else None,
            strength=_strength(street, s_bars[b.id]) if post else None,
            next=s_next[b.id].model(),
        ))
    return summary_next, boards, sizes


def compute_detail(db, stat: _Stat, player_id: int, workspace_id: int,
                   filters: tuple[str, list], filter_steps: list[dict] | None = None) -> CellDetail:
    hands = _query_hands(db, stat, player_id, workspace_id, filters, cases_only=False)
    cases = [h for h in hands if h.case]
    n_cases = len(cases)
    sd = sum(1 for h in cases if h.sd)
    won = sum(1 for h in cases if h.win)
    won_sd = sum(1 for h in cases if h.win and h.sd)

    strength = None
    if stat.street > 0:
        counts: dict[int, int] = {}
        for h in cases:
            if h.hv is not None:
                counts[h.hv] = counts.get(h.hv, 0) + 1
        strength = _strength(stat.street, counts)

    buckets = _stat_buckets(stat)
    # Boards and Bet Sizes count opportunities too; otherwise only cases are replayed.
    replay_set = hands if (stat.street > 0 or buckets) else cases
    username = hands[0].username if hands else ""
    recs, replayed, failed = _records(db, workspace_id, player_id, username, stat.row, stat.street,
                                      (h.hand_id for h in replay_set))
    groups: Counter = Counter()
    for h in replay_set:
        v = recs.get(h.hand_id)
        if v:
            groups[v << 1 | h.case] += 1
    summary_next, boards, sizes = _aggregate(stat, groups, buckets)

    player = None
    r = db.execute("SELECT username FROM players WHERE id = ?", [player_id]).fetchone()
    if r:
        player = r[0]
    return CellDetail(
        cell_id=stat.cell_id, row=stat.row,
        notation=ROWS[stat.row].notation, street=STREET_NAMES[stat.street],
        player=player, player_id=player_id,
        value=n_cases / len(hands) * 100.0 if hands else None, cases=n_cases, opps=len(hands),
        strength=strength,
        summary=Summary(won_hand=_ratio(won, n_cases), wtsd=_ratio(sd, n_cases),
                        wsd=_ratio(won_sd, sd), next=summary_next.model()),
        boards=boards, bet_sizes=sizes, replayed=replayed, replay_failed=failed,
        chain=[*(filter_steps or []), *cell_steps(stat.cell.ref.positions, stat.cell.ref.exclude,
                                                  stat.row, ROWS[stat.row].notation)],
    )


# ── hand rows (H2N-COMPATIBLE-STATS.md 6.7) ─────────────────────────────

_SUIT_INDEX = {"h": 0, "d": 1, "c": 2, "s": 3}


def sort_hole_cards(cards: Iterable[str]) -> list[str]:
    """High rank first; a pair in suit order hearts, diamonds, clubs, spades."""
    def key(c: str):
        rank, suit = parse_card(c)
        return -(rank * 100 - _SUIT_INDEX.get(suit, 3))
    return sorted(cards, key=key)


def _token(a: Act, hero: int, bb: float) -> ActionToken:
    t = TYPE_LETTERS[a.raw]
    amt = None
    if a.raw == RAISE:
        amt = a.to / bb
    elif a.raw in (BET, CALL):
        amt = a.inc / bb
    return ActionToken(t=t, amt_bb=amt, allin=bool(a.is_all_in), pos=a.pos,
                       hero=a.actor == hero, player=a.name)


def _street_pots(parsed, seq: HandSeq) -> list[float]:
    """Gross initial pot of each street (money): everything put in on earlier
    streets, after uncalled bets are returned (GG and every room without a
    per-street rake rule; H2N-COMPATIBLE-STATS.md 6.7)."""
    last = max((s for s in range(4) if seq.streets[s]), default=0)
    # Bets can only be left uncalled on the last street with actions (later
    # streets are an all-in run-out): the top street total minus the next one.
    totals: dict[int, float] = {}
    for a in seq.streets[last]:
        totals[a.actor] = a.to
    ranked = sorted(totals.values(), reverse=True)
    uncalled = ranked[0] - ranked[1] if len(ranked) > 1 else 0.0
    if parsed.uncalled_returns:
        uncalled = max(uncalled, float(sum(parsed.uncalled_returns.values())))
    pots = []
    for s in range(4):
        nxt = next((seq.streets[k][0].pot for k in range(s, 4) if seq.streets[k]), None)
        pot = seq.pot_total if nxt is None else nxt
        if s > last:
            pot -= uncalled
        pots.append(pot)
    return pots


def build_row(parsed, seq: HandSeq, username: str, street: int) -> HandRow:
    """Hand-list row for `username` (cards, per-street pots and action tokens)."""
    p = seq.index[username]
    bb = seq.bb
    hole = list((parsed.hero_cards or {}).get(username) or ())
    boards = player_boards(parsed)
    pots = _street_pots(parsed, seq)
    fold_street = seq.fold_street[p]
    streets: list[Optional[StreetCell]] = []
    for s in range(4):
        if 0 <= fold_street < s:
            streets.append(None)
            continue
        cell = StreetCell(street=STREET_NAMES[s])
        if s > 0:
            lo, hi = {1: (0, 3), 2: (3, 4), 3: (4, 5)}[s]
            groups: list[list[str]] = []
            for b in boards:
                g = list(b[lo:hi])
                if len(g) == hi - lo and g not in groups:
                    groups.append(g)
            if not groups:
                streets.append(None)
                continue
            cell.cards = groups
            cell.pot = pots[s]
            cell.pot_bb = pots[s] / bb
        tokens = []
        for a in seq.streets[s]:
            if a.raw == FOLD and s == 0 and a.actor != p:
                continue
            tokens.append(_token(a, p, bb))
            if a.raw == FOLD and a.actor == p:
                break
        cell.actions = tokens
        streets.append(cell)
    values: list[HandValueLabel] = []
    if street > 0 and len(hole) == 2:
        sname = STREET_NAMES[street]
        for c in classify_boards_for_player(parsed, username):
            idx = c.get(f"hv_{sname}")
            if idx is None:
                continue
            info = category_info(sname, idx)
            values.append(HandValueLabel(index=idx, key=info["key"], label=info["label"],
                                         color=info["color"]))
    return HandRow(hand_id=str(parsed.hand_id), hole_cards=sort_hole_cards(hole) if hole else [],
                   streets=streets, hand_value=values, position=seq.pos[p])


def _category_index(street: int, bucket: str) -> int:
    sname = STREET_NAMES[street]
    if bucket.lstrip("-").isdigit():
        idx = int(bucket)
        if idx == OTHER or 0 <= idx < len(STREET_CATEGORIES[sname]):
            return idx
    elif bucket == "other":
        return OTHER
    else:
        for i, c in enumerate(STREET_CATEGORIES[sname]):
            if c.key == bucket:
                return i
    raise HTTPException(status_code=400, detail=f"Unknown hand value {bucket!r} on the {sname}")


def compute_hands(db, stat: _Stat, player_id: int, workspace_id: int, filters: tuple[str, list],
                  *, bucket: str | None = None, board: str | None = None, size: str | None = None,
                  offset: int = 0, limit: int = 50, sort: str = "date",
                  order: str = "desc") -> CellHands:
    hands = _query_hands(db, stat, player_id, workspace_id, filters, cases_only=True)
    cat = None
    if bucket is not None:
        if stat.street == 0:
            raise HTTPException(status_code=400, detail="Preflop stats have no hand values")
        cat = _category_index(stat.street, bucket)
    tex = None
    if board is not None:
        if stat.street == 0:
            raise HTTPException(status_code=400, detail="Preflop stats have no boards")
        keys = [c.key for c in BOARD_CATEGORIES[STREET_NAMES[stat.street]]]
        if board not in keys:
            raise HTTPException(status_code=400, detail=f"Unknown board category {board!r}")
        tex = keys.index(board)
    if size is not None:
        if size not in _BUCKET_BY_ID or _BUCKET_BY_ID[size] not in _stat_buckets(stat):
            raise HTTPException(status_code=400, detail=f"Bet size {size} does not apply")

    if tex is not None or size is not None:
        recs, _, _ = _records(db, workspace_id, player_id, hands[0].username if hands else "",
                              stat.row, stat.street, (h.hand_id for h in hands))
        unpacked: dict[int, _Rec | None] = {}
        kept = []
        for h in hands:
            v = recs.get(h.hand_id)
            rec = None
            if v:
                rec = unpacked.get(v)
                if rec is None:
                    rec = unpacked[v] = _unpack(v)
            if rec is None or not rec.case:
                continue
            if size is not None and (size, True) not in rec.sizes:
                continue
            if tex is not None or cat is not None:
                boards_ok = [
                    (tex is None or tex in t) and (cat is None or c == cat)
                    for t, c in zip(rec.textures, rec.cats or (None,) * len(rec.textures))
                ] if stat.street > 0 else [True]
                if not any(boards_ok):
                    continue
            kept.append(h)
        hands = kept
    elif cat is not None:
        hands = [h for h in hands if h.hv == cat]

    reverse = order != "asc"
    if sort == "won":
        hands.sort(key=lambda h: (h.won_bb or 0.0, str(h.played_at), h.hand_id), reverse=reverse)
    elif sort == "ev":
        hands.sort(key=lambda h: ((h.ev_bb or 0.0) - (h.won_bb or 0.0), str(h.played_at),
                                  h.hand_id), reverse=reverse)
    else:
        hands.sort(key=lambda h: (str(h.played_at), h.hand_id), reverse=reverse)

    total = len(hands)
    page = hands[offset:offset + limit]
    raw = _fetch_raw(db, workspace_id, [h.hand_id for h in page])
    marked_set, tags_map = marked_hands.marks_for(db, workspace_id, player_id,
                                                  [h.hand_id for h in page])
    rows: list[HandRow] = []
    for h in page:
        src = raw.get(h.hand_id)
        row = None
        err = None
        if src and src[0]:
            try:
                parsed, seq = _parse(*src)
                if h.username in seq.index:
                    row = build_row(parsed, seq, h.username, stat.street)
                else:
                    err = "player not in hand"
            except Exception as e:  # keep the row so the list length stays right
                log.warning("hand row replay failed for %s", h.hand_id, exc_info=True)
                err = f"replay failed: {e}"
        else:
            err = "no hand history"
        if row is None:
            row = HandRow(hand_id=h.hand_id, position=h.pos, error=err)
        row.hand_id = h.hand_id
        row.played_at = str(h.played_at) if h.played_at is not None else None
        row.stakes = h.stakes
        row.site_id = h.site_id
        row.won = h.won
        row.won_bb = h.won_bb
        row.ev_diff_bb = (h.ev_bb - h.won_bb) if h.ev_bb is not None and h.won_bb is not None \
            else None
        row.marked = h.hand_id in marked_set
        row.tags = [TagRef(**t) for t in tags_map.get(h.hand_id, [])]
        rows.append(row)
    return CellHands(cell_id=stat.cell_id, total=total, offset=offset, limit=limit, rows=rows)


# ── endpoints ─────────────────────────────────────────────────────────────


@router.get("/general/cell/{cell_id}/detail", response_model=CellDetail)
def get_cell_detail(
    cell_id: str,
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    chain: str | None = Query(None, description="JSON plain Reports steps, instead of the filters above"),
    workspace_id: int = Query(1),
    player_id: int | None = Query(None, description="Defaults to the workspace hero"),
):
    stat = _resolve(cell_id)
    db = get_read_cursor()
    fsql, fparams, fsteps = resolve_filters(chain, stakes, game_mode, date_from, date_to,
                                            int(get_app_settings(db)["day_start_hour"]))
    target = _target_player(db, workspace_id, player_id)
    if target is None:
        return CellDetail(cell_id=cell_id, row=stat.row,
                          notation=ROWS[stat.row].notation, street=STREET_NAMES[stat.street],
                          chain=[*fsteps, *cell_steps(stat.cell.ref.positions, stat.cell.ref.exclude,
                                                      stat.row, ROWS[stat.row].notation)])
    return compute_detail(db, stat, target, workspace_id, (fsql, fparams), fsteps)


@router.get("/general/cell/{cell_id}/hands", response_model=CellHands)
def get_cell_hands(
    cell_id: str,
    bucket: str | None = Query(None, description="Hand value key (e.g. 'trash', 'other') or index"),
    board: str | None = Query(None, description="Board category key (e.g. 'paired')"),
    size: str | None = Query(None, description="Bet size bucket key"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=512),
    sort: Literal["date", "won", "ev"] = Query("date"),
    order: Literal["desc", "asc"] = Query("desc"),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    chain: str | None = Query(None, description="JSON plain Reports steps, instead of the filters above"),
    workspace_id: int = Query(1),
    player_id: int | None = Query(None, description="Defaults to the workspace hero"),
):
    stat = _resolve(cell_id)
    db = get_read_cursor()
    fsql, fparams, fsteps = resolve_filters(chain, stakes, game_mode, date_from, date_to,
                                            int(get_app_settings(db)["day_start_hour"]))
    target = _target_player(db, workspace_id, player_id)
    if target is None:
        return CellHands(cell_id=cell_id, offset=offset, limit=limit)
    return compute_hands(db, stat, target, workspace_id,
                         (fsql, fparams),
                         bucket=bucket, board=board, size=size, offset=offset, limit=limit,
                         sort=sort, order=order)


__all__ = ["router", "compute_detail", "compute_hands", "build_row", "sort_hole_cards",
           "clear_cache"]
