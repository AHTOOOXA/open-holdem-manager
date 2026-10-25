"""Reports filter chain: request models, plain-step SQL and per-hand spot resolution.

Contract: frontend/src/lib/reports/types.ts (`Step`, `ReportQuery`).

`resolve(db, workspace_id, player_id, chain)` returns a `Resolution`: every hand of the
player that passes the chain's plain steps and is an opportunity of its last spot step,
with the hit point and the per-hand facts the reports read. Plain chains (no spot step)
have no hit point and every matching hand is a case.

- Plain steps (pos, stakes, mode, tsize, date, hour, stack, game, cells, hv, and the Sessions
  steps session / table / with) become one SQL WHERE over `hands` / `hand_players`,
  together with `COALESCE(hp.h2n_valid, TRUE)` (the General screen leaves hands H2N would
  refuse out of every number). `pos`, `stack`, `cells`, `hv` and the spot steps are about
  the reporting player's own seat; the others are about the hand.
- Spot steps (row, line, next, faced, betsize) are evaluated in chain order on the hand's stored
  action sequence (`hand_players.h2n_seq`, re-parsed from `raw_text` when missing) by
  `app.reports.spots`. Every spot step but the last must be a case; the last one decides
  case / opportunity. `row` steps also prefilter in SQL on their General bit (case bit, or
  the opportunity bit for the last spot step).

Plain chains are not materialized: their Resolution carries the SQL WHERE of the case rows
and the views aggregate in SQL / Arrow (split.plain_groups); hand lists and the graph filter
with `case_filter` (a subquery, or the spot cases as a registered Arrow relation).

Resolutions are cached (LRU bounded by estimated bytes) by workspace, player, the chain
without labels and a data version (hand count, last import time, the highest
`hand_players.id`, which a rebuild moves, and `data_generation`, whose bump also clears the
cache), so the several requests a Reports page fires share one resolution; split tables and
finished responses computed from a resolution are cached on it (`Resolution.memo`). Cold
spot-chain resolves and memoized computations run in `app.concurrency.heavy_slot()`; requests
waiting for one of them hold no slot.
"""

from __future__ import annotations

import datetime as _dt
import itertools
import json
import logging
import sys
import threading
from collections import OrderedDict
from contextlib import nullcontext
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app import data_generation
from app.concurrency import heavy_slot
from app.api.general_popup import _BUCKET_BY_ID, _fetch_raw, _size_hits
from app.date_filters import day_from_sql, day_to_sql
from app.db import get_hero_player_id, get_rebuild_status
from app.h2n.definitions import COMPILED
from app.h2n.matcher import CASE, OPP
from app.h2n.rows import ROWS, sql_case, sql_opp
from app.h2n.seqcodec import decode_sequence
from app.hand_value import OTHER, STREET_CATEGORIES
from app.reports import spots
from app.reports.spots import FACED_SUPPORTED, START, SpotCtx

log = logging.getLogger(__name__)

# ── request models (types.ts Step / ReportQuery) ─────────────────────────

StreetName = Literal["preflop", "flop", "turn", "river"]
PosName = Literal["EP", "MP", "CO", "BTN", "SB", "BB"]
NextAction = Literal[
    "fold_vs_raise", "call_vs_raise", "raise_vs_raise", "fold_vs_bet", "call_vs_bet",
    "raise_vs_bet", "check_vs_call", "bet_vs_call", "check", "bet", "fold", "call", "raise",
    "limp_fold", "limp_call", "limp_raise",
]
FacedAction = Literal[
    "all_fold", "villain_bet", "villain_raise", "villain_squeeze", "villains_check",
    "one_call", "two_calls", "three_calls", "four_plus_calls", "villain_3bet",
    "villain_open_4bet", "villain_limp_call", "villain_limp_raise", "villain_open_call",
]
ModeName = Literal["fast", "regular"]

RANKS = "AKQJT98765432"


def _all_classes() -> list[str]:
    """The 169 preflop classes in 13x13 order: pairs on the diagonal, suited above."""
    out = []
    for i, a in enumerate(RANKS):
        for j, b in enumerate(RANKS):
            if i == j:
                out.append(a + b)
            elif j > i:
                out.append(a + b + "s")
            else:
                out.append(b + a + "o")
    return out


CLASSES: list[str] = _all_classes()
_CLASS_SET = frozenset(CLASSES)


class _Step(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    label: Optional[str] = None


class PosStep(_Step):
    k: Literal["pos"]
    v: list[PosName] = Field(min_length=1)


class StakesStep(_Step):
    k: Literal["stakes"]
    v: list[str] = Field(min_length=1)


class ModeStep(_Step):
    k: Literal["mode"]
    v: ModeName


class TsizeStep(_Step):
    k: Literal["tsize"]
    v: list[int] = Field(min_length=1)


class DateStep(_Step):
    k: Literal["date"]
    from_: Optional[str] = Field(None, alias="from")
    to: Optional[str] = None

    @field_validator("from_", "to")
    @classmethod
    def _iso(cls, v):
        if v is not None:
            _dt.date.fromisoformat(v[:10])
        return v


class HourStep(_Step):
    k: Literal["hour"]
    v: list[Annotated[int, Field(ge=0, le=23)]] = Field(min_length=1)


class StackStep(_Step):
    k: Literal["stack"]
    lo: float
    hi: Optional[float] = None


class GameStep(_Step):
    k: Literal["game"]
    stakes: str
    mode: ModeName
    tsize: Optional[int] = None  # None = unknown table size (SQL IS NULL)


class CellsStep(_Step):
    k: Literal["cells"]
    v: list[str] = Field(min_length=1)

    @field_validator("v")
    @classmethod
    def _classes(cls, v):
        bad = [c for c in v if c not in _CLASS_SET]
        if bad:
            raise ValueError(f"unknown hand classes {bad}")
        return v


class HvStep(_Step):
    k: Literal["hv"]
    street: StreetName
    cats: list[str] = Field(min_length=1)

    @field_validator("street")
    @classmethod
    def _postflop(cls, v):
        if v == "preflop":
            raise ValueError("hand values exist on the flop, turn and river only")
        return v

    @model_validator(mode="after")
    def _known_cats(self):
        for c in self.cats:
            hv_index(self.street, c)
        return self


def _naive_iso(v: str) -> _dt.datetime:
    t = _dt.datetime.fromisoformat(v)
    if t.tzinfo is not None:
        raise ValueError("session bounds are naive local datetimes (no zone)")
    return t


class SessionStep(_Step):
    """A Sessions list row: played_at in [start, end] (end = the session's last hand start)."""

    k: Literal["session"]
    start: str
    end: str

    @model_validator(mode="after")
    def _bounds(self):
        if _naive_iso(self.end) < _naive_iso(self.start):
            raise ValueError("session end is before its start")
        return self


class TableStep(_Step):
    k: Literal["table"]
    v: list[str] = Field(min_length=1)


class WithStep(_Step):
    """Hands where this player was dealt in (any seat of the hand)."""

    k: Literal["with"]
    player_id: int


class RowStep(_Step):
    k: Literal["row"]
    key: str

    @field_validator("key")
    @classmethod
    def _known(cls, v):
        if v not in COMPILED:
            raise ValueError(f"unknown row {v!r}")
        return v


LINE_MAX_LEN = 2000


class LineStep(_Step):
    """A custom action line: H2N matcher row notation (`app.h2n.matcher` docstring)."""

    k: Literal["line"]
    dsl: str = Field(max_length=LINE_MAX_LEN)

    @field_validator("dsl")
    @classmethod
    def _compiles(cls, v):
        spots.compile_line(v)  # ValueError -> 422 with the bad token in the message
        return v


class NextStep(_Step):
    k: Literal["next"]
    street: StreetName
    a: NextAction


class FacedStep(_Step):
    k: Literal["faced"]
    street: StreetName
    a: FacedAction

    @field_validator("a")
    @classmethod
    def _supported(cls, v):
        if v not in FACED_SUPPORTED:
            raise ValueError(f"faced action {v!r} is not supported")
        return v


class BetsizeStep(_Step):
    k: Literal["betsize"]
    bucket: str

    @field_validator("bucket")
    @classmethod
    def _known(cls, v):
        if v not in _BUCKET_BY_ID:
            raise ValueError(f"unknown bet size bucket {v!r}")
        return v


Step = Annotated[
    Union[PosStep, StakesStep, ModeStep, TsizeStep, DateStep, HourStep, StackStep, GameStep,
          CellsStep, HvStep, SessionStep, TableStep, WithStep, RowStep, LineStep, NextStep, FacedStep,
          BetsizeStep],
    Field(discriminator="k"),
]
CHAIN = TypeAdapter(list[Step])

PLAIN_KINDS = frozenset(("pos", "stakes", "mode", "tsize", "date", "hour", "stack", "game",
                         "cells", "hv", "session", "table", "with"))
SPOT_KINDS = frozenset(("row", "line", "next", "faced", "betsize"))


class ReportQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workspace_id: int = 1
    player_id: Optional[int] = None
    chain: list[Step] = []


def canonical(chain: list[_Step]) -> str:
    return json.dumps([s.model_dump(by_alias=True, exclude={"label"}, exclude_none=True)
                       for s in chain], sort_keys=True, separators=(",", ":"))


def parse_chain(text: str | None) -> list[_Step]:
    """Chain from a query-string JSON value (ValueError when invalid)."""
    if not text:
        return []
    return CHAIN.validate_json(text)


# ── plain steps -> SQL ───────────────────────────────────────────────────

FAST_FOLD = "Fast Fold"


def _card_rank(col: str) -> str:
    return (f"replace(upper(substr({col}, 1, length({col}) - 1)), '10', 'T')")


def _card_suit(col: str) -> str:
    return f"lower(right({col}, 1))"


def card_class_sql(alias: str = "hp") -> str:
    """SQL expression: preflop class ("AKs", "QQ", "T9o") of card1/card2, NULL if unknown."""
    r1, r2 = _card_rank(f"{alias}.card1"), _card_rank(f"{alias}.card2")
    s1, s2 = _card_suit(f"{alias}.card1"), _card_suit(f"{alias}.card2")
    sfx = f"(CASE WHEN {s1} = {s2} THEN 's' ELSE 'o' END)"
    return (f"(CASE WHEN {alias}.card1 IS NULL OR {alias}.card2 IS NULL THEN NULL "
            f"WHEN {r1} = {r2} THEN {r1} || {r2} "
            f"WHEN strpos('{RANKS}', {r1}) < strpos('{RANKS}', {r2}) THEN {r1} || {r2} || {sfx} "
            f"ELSE {r2} || {r1} || {sfx} END)")


def card_class(c1: str | None, c2: str | None) -> str | None:
    if not c1 or not c2:
        return None
    r1, r2 = c1[:-1].upper().replace("10", "T"), c2[:-1].upper().replace("10", "T")
    if r1 not in RANKS or r2 not in RANKS:
        return None
    if r1 == r2:
        return r1 + r2
    sfx = "s" if c1[-1].lower() == c2[-1].lower() else "o"
    if RANKS.index(r1) > RANKS.index(r2):
        r1, r2 = r2, r1
    return r1 + r2 + sfx


def hv_index(street: str, key: str) -> int:
    if key == "other":
        return OTHER
    for i, c in enumerate(STREET_CATEGORIES[street]):
        if c.key == key:
            return i
    raise ValueError(f"unknown hand value {key!r} on the {street}")


def _marks(n: int) -> str:
    return ", ".join("?" for _ in range(n))


def _mode_sql(mode: str) -> str:
    return "h.game_mode = 'Fast Fold'" if mode == "fast" else "h.game_mode <> 'Fast Fold'"


def plain_sql(chain: list[_Step], day_start: int = 0) -> tuple[str, list]:
    """AND-ed SQL conditions (leading " AND ") and params of the chain's plain steps.
    `day_start` = app setting day_start_hour: a date step's day D is [D h:00, D+1 h:00)."""
    sql: list[str] = []
    params: list = []
    for st in chain:
        k = st.k
        if k == "pos":
            sql.append(f"hp.h2n_pos IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "stakes":
            sql.append(f"h.stakes IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "mode":
            sql.append(_mode_sql(st.v))
        elif k == "tsize":
            sql.append(f"h.table_size IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "date":
            if st.from_:
                sql.append(day_from_sql(day_start))
                params.append(st.from_[:10])
            if st.to:
                sql.append(day_to_sql(day_start))
                params.append(st.to[:10])
        elif k == "hour":
            sql.append(f"EXTRACT(hour FROM h.played_at) IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "stack":
            sql.append("hp.stack_bb >= ?")
            params.append(st.lo)
            if st.hi is not None:
                sql.append("hp.stack_bb < ?")
                params.append(st.hi)
        elif k == "game":
            sql.append("h.stakes = ?")
            params.append(st.stakes)
            sql.append(_mode_sql(st.mode))
            if st.tsize is None:
                sql.append("h.table_size IS NULL")
            else:
                sql.append("h.table_size = ?")
                params.append(st.tsize)
        elif k == "cells":
            sql.append(f"{card_class_sql()} IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "hv":
            idx = [hv_index(st.street, c) for c in st.cats]
            sql.append(f"hp.hv_{st.street} IN ({_marks(len(idx))})")
            params += idx
        elif k == "session":
            sql.append("h.played_at BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)")
            params += [_naive_iso(st.start).isoformat(sep=" "),
                       _naive_iso(st.end).isoformat(sep=" ")]
        elif k == "table":
            sql.append(f"h.table_name IN ({_marks(len(st.v))})")
            params += list(st.v)
        elif k == "with":
            sql.append("EXISTS (SELECT 1 FROM hand_players wp WHERE wp.hand_id = h.id "
                       "AND wp.workspace_id = h.workspace_id AND wp.player_id = ?)")
            params.append(st.player_id)
    return "".join(" AND " + s for s in sql), params


def _row_bits_sql(chain: list[_Step]) -> str:
    """Bit prefilter of the row steps: case bit, or opp bit for the last spot step."""
    moving = [i for i, st in enumerate(chain) if st.k in ("row", "line", "next", "faced")]
    out = []
    for i in moving:
        st = chain[i]
        if st.k != "row":
            continue
        last = i == moving[-1]
        out.append(f"{sql_opp(st.key) if last else sql_case(st.key)} = 1")
    return "".join(" AND " + s for s in out)


# ── spot evaluation ──────────────────────────────────────────────────────


def spot_steps(chain: list[_Step]) -> list[_Step]:
    return [s for s in chain if s.k in SPOT_KINDS]


def evaluate_spot(seq, p: int, steps: list[_Step]) -> tuple[int, tuple[int, int] | None]:
    """(code, hit) of the chain's spot steps for player index p (code 0 = not in the set)."""
    code, hit = OPP | CASE, None
    for st in steps:
        if st.k == "betsize":
            if hit is None or not code:
                return 0, None
            b = _BUCKET_BY_ID[st.bucket]
            sizes = _size_hits(seq, hit, (b,))
            if not sizes:
                return 0, None
            code = (OPP | CASE) if (sizes[0][1] and code & CASE) else OPP
            continue
        if not code & CASE:
            return 0, None
        if st.k == "row":
            code, hit = spots.eval_row(seq, p, st.key)
        elif st.k == "line":
            lcode, lhit = spots.evaluate_code(spots.compile_line(st.dsl), seq, p)
            if hit is None:
                code, hit = lcode, lhit
            elif lcode & CASE:   # after a hit-moving step the line only filters; the hit stays
                continue
            else:
                return 0, None
        elif st.k == "next":
            code, hit = spots.eval_next(seq, p, hit, spots.STREET_INDEX[st.street], st.a)
        else:
            code, hit = spots.eval_faced(seq, p, hit, spots.STREET_INDEX[st.street], st.a)
        if not code or hit is None:
            return 0, None
    return code, hit


def chain_ctx(chain: list[_Step]) -> SpotCtx:
    """Static context of the chain's final hit point (hand start for plain chains)."""
    ctx = START
    moved = False
    for st in chain:
        if st.k == "row":
            ctx = spots.row_ctx(st.key)
        elif st.k == "line":
            if not moved:   # a later line only filters, the hit point stays
                ctx = spots.line_ctx(st.dsl)
        elif st.k == "next":
            ctx = spots.next_spot(ctx, spots.STREET_INDEX[st.street], st.a)
        elif st.k == "faced":
            ctx = spots.faced_spot(ctx, spots.STREET_INDEX[st.street], st.a)
        else:
            continue
        moved = True
    return ctx


POS_NAMES = {"BB": "Big Blind", "SB": "Small Blind", "BTN": "Button", "CO": "Cutoff",
             "MP": "Middle Position", "EP": "Early Position"}


def stakes_caption(bb: float | None, stakes: str) -> str:
    if bb:
        cents = round(float(bb) * 100, 2)
        return f"NL{cents:g}"
    return stakes


def stack_caption(lo: float, hi: float | None) -> str:
    return f"> {lo:g}" if hi is None else f"[{lo:g}; {hi:g}]"


# ── resolution ───────────────────────────────────────────────────────────


@dataclass(slots=True)
class HandRec:
    """One hand of a spot resolution (facts from SQL + the spot result).

    Low-cardinality strings (stakes, mode, position, cards, table) are interned: a cached
    resolution holds one copy of each value instead of one per hand."""

    hid: str
    case: bool
    hit: tuple[int, int] | None
    won: float
    won_bb: float
    ev_bb: float
    ev: float               # won EV in money
    rake: float
    sd: bool
    win: bool
    pos: str | None
    stack_bb: float | None
    played_at: Any
    stakes: str
    bb_amount: float
    mode: str
    tsize: int | None
    card1: str | None
    card2: str | None
    hv_flop: int | None
    hv_turn: int | None
    hv_river: int | None
    pre_opp: int
    pre_case: int
    post_opp: int
    post_case: int
    rake_bb: float = 0.0
    table: str | None = None
    ap: float | None = None      # Action Profit, bb (hero action hits)
    hit_eff: int | None = None   # effective type of the hit action
    hit_hero: bool = False       # the hit action is the player's own

    @property
    def hv(self) -> tuple[int | None, int | None, int | None]:
        return (self.hv_flop, self.hv_turn, self.hv_river)


# Approximate resident bytes of one HandRec (slots, boxed floats, id string, datetime, the
# 4 bitmask ints, hit tuple; interned strings excluded). Measured ~700-800 B with tracemalloc.
REC_BYTES = 760
# A derived table / response bigger than this (estimate) is not kept on the resolution.
MEMO_MAX_BYTES = 16 << 20
# Compact per-row tables (one Acc per row, no response dicts) may be kept up to this size:
# rebuilding the response from them is ~5x cheaper than recomputing (e.g. the Players split).
TABLE_MAX_BYTES = 96 << 20


class PlainResolutionError(RuntimeError):
    """A plain resolution has no per-hand records: aggregate in SQL (`case_filter`,
    `iter_records`, `case_ids`) instead of reading `.cases` / `.case_ids`."""


class PlainCases:
    """`Resolution.hands` of a plain chain: only its length (the case count) is known."""

    __slots__ = ("n",)

    def __init__(self, n: int):
        self.n = n

    def __len__(self) -> int:
        return self.n

    def __iter__(self):
        raise PlainResolutionError("plain resolution: no per-hand records")

    def __getitem__(self, i):
        raise PlainResolutionError("plain resolution: no per-hand records")


@dataclass
class Resolution:
    """The hands of a chain for one player.

    Plain chains (no spot step) hold no per-hand records: the cases are the rows of
    `SELECT ... _FROM WHERE {where}` (`params`), counted in `n_cases` (`hands` is a
    length-only `PlainCases`); views aggregate them in SQL. Spot chains hold one `HandRec`
    per opportunity hand (`hands`) and their blobs."""

    workspace_id: int
    player_id: int | None
    username: str | None
    chain: list
    ctx: SpotCtx
    has_spot: bool
    total_hands: int
    hands: list[HandRec] | PlainCases = field(default_factory=list)  # cases + opportunity-only hands
    blobs: dict[str, bytes | None] = field(default_factory=dict)
    replay_failed: int = 0
    tables: dict = field(default_factory=dict)            # cached derived tables / responses
    lock: threading.Lock = field(default_factory=threading.Lock)
    n_cases: int = 0
    where: str = "FALSE"                                  # case rows (aliases hp, h of _FROM)
    params: list = field(default_factory=list)
    blob_bytes: int = 0
    table_bytes: int = 0
    _flights: dict = field(default_factory=dict, repr=False)   # memo key -> _Flight

    @property
    def plain(self) -> bool:
        return not self.has_spot

    @property
    def cases(self) -> list[HandRec]:
        if self.plain:
            raise PlainResolutionError("plain resolution: no per-hand records")
        return [h for h in self.hands if h.case]

    @property
    def case_ids(self) -> list[str]:
        if self.plain:
            raise PlainResolutionError("plain resolution: use chain.case_ids(db, res)")
        return [h.hid for h in self.hands if h.case]

    def memo(self, key, fn, size=None, max_bytes: int = MEMO_MAX_BYTES, heavy: bool = True):
        """`fn()` computed once per key (racing requests wait for the first one) and kept in
        `tables` unless its estimated size (`size(value)`, default 1 KB) is over `max_bytes`
        (MEMO_MAX_BYTES by default).

        Requests that arrive while a key is being computed take that computation's value (a
        per-key `_Flight`, as in `resolve`), also when it is too big to keep: an over-cap value
        is computed once per burst of racing requests, not once per waiter. When the
        computation fails, its waiters try again.

        `heavy`: the computation runs in a `heavy_slot()`; all CPU work of the Reports
        endpoints happens in memoized computations, so this is where they are throttled. A
        cached value is returned without a slot, and a request waiting for another request's
        computation of the same key holds no slot (the endpoints call this outside any slot).
        As in `resolve`, the computing request takes its slot *before* it registers the
        flight, so a flight always belongs to a request that is already running. Nested keys
        (Next / Faced / Sizing / Players tables) are only computed inside a heavy computation,
        whose slot is re-entrant. `case_ids_arrow` is also built outside any slot (hand list,
        graph) and is cheap: it takes none."""
        slot = heavy_slot if heavy else nullcontext
        while True:
            with self.lock:
                if key in self.tables:
                    return self.tables[key]
                flight = self._flights.get(key)
            if flight is not None:          # someone is computing it: wait without a slot
                flight.done.wait()
                if flight.ok:
                    return flight.result
                continue                    # that computation failed: try again
            with slot():
                with self.lock:
                    if key in self.tables:
                        return self.tables[key]
                    flight = self._flights.get(key)
                    owner = flight is None
                    if owner:
                        flight = self._flights[key] = _Flight()
                if not owner:
                    continue                # lost the race while taking the slot: wait
                try:
                    value = fn()
                    nbytes = size(value) if size is not None else 1024
                    if nbytes <= max_bytes:
                        with self.lock:
                            self.tables[key] = value
                            self.table_bytes += nbytes
                        if nbytes > (1 << 20):
                            _CACHE.trim()
                    flight.result, flight.ok = value, True
                    return value
                finally:
                    with self.lock:
                        if self._flights.get(key) is flight:
                            del self._flights[key]
                    flight.done.set()

    def approx_bytes(self) -> int:
        recs = 0 if self.plain else len(self.hands)
        return recs * REC_BYTES + self.blob_bytes + self.table_bytes + 4096


_D = "CAST({} AS DOUBLE)"
_COLS = f"""h.id, {_D.format("COALESCE(hp.won, 0)")}, {_D.format("COALESCE(hp.won_bb, 0)")},
           {_D.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)")},
           {_D.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount")},
           {_D.format("COALESCE(hp.rake, 0)")}, COALESCE(hp.went_to_showdown, FALSE),
           COALESCE(hp.is_winner, FALSE), hp.h2n_pos, {_D.format("hp.stack_bb")}, h.played_at,
           h.stakes, {_D.format("h.bb_amount")}, h.game_mode, h.table_size, hp.card1, hp.card2,
           hp.hv_flop, hp.hv_turn, hp.hv_river,
           COALESCE(hp.h2n_pre_opp, 0), COALESCE(hp.h2n_pre_case, 0),
           COALESCE(hp.h2n_post_opp, 0), COALESCE(hp.h2n_post_case, 0),
           {_D.format("COALESCE(hp.rake_bb, 0)")}, h.table_name"""
# Money columns are DECIMAL: CAST(... AS DOUBLE) is the same float as Python's float(Decimal)
# (exact int64 / power of ten, rounded once; the EV product is cast after the exact DECIMAL
# product), without one Decimal object per value.
_FROM = """
    FROM hand_players hp
    JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
"""
_SELECT = f"SELECT {_COLS} {_FROM}"
_BASE_WHERE = "hp.player_id = ? AND h.workspace_id = ? AND COALESCE(hp.h2n_valid, TRUE)"
# Hands in insertion order: the per-hand float sums are sequential in this order, so they are
# the same on every request (a parallel scan without ORDER BY may return rows in any order).
ORDER = " ORDER BY h.rowid"

_intern = sys.intern


def _istr(s):
    return None if s is None else _intern(s)


def _rec(r, case: bool = True, hit=None) -> HandRec:
    return HandRec(
        hid=r[0], case=case, hit=hit, won=r[1], won_bb=r[2], ev_bb=r[3], ev=r[4],
        rake=r[5], sd=bool(r[6]), win=bool(r[7]), pos=_istr(r[8]),
        stack_bb=r[9], played_at=r[10], stakes=_istr(r[11]),
        bb_amount=r[12] if r[12] is not None else 0.0, mode=_istr(r[13] or ""), tsize=r[14],
        card1=_istr(r[15]), card2=_istr(r[16]), hv_flop=r[17], hv_turn=r[18], hv_river=r[19],
        pre_opp=int(r[20]), pre_case=int(r[21]), post_opp=int(r[22]), post_case=int(r[23]),
        rake_bb=r[24], table=_istr(r[25]),
    )


_reg_names = itertools.count()


def register_ids(db, ids) -> str:
    """Register `ids` (list or Arrow string array) as a one-column (`id`) relation on `db`;
    returns its name. Valid on that cursor only."""
    import pyarrow as pa
    arr = ids if isinstance(ids, pa.Array) else pa.array(ids, pa.string())
    name = f"_ohm_ids_{next(_reg_names)}"
    db.register(name, pa.table({"id": arr}))
    return name


def case_ids(db, res: Resolution) -> list[str]:
    """Case hand ids of a resolution (plain chains: from SQL, in hand insertion order)."""
    if not res.plain:
        return [h.hid for h in res.hands if h.case]
    if not res.n_cases:
        return []
    return db.execute(f"SELECT h.id {_FROM} WHERE {res.where}{ORDER}",
                      res.params).fetch_arrow_table().column(0).to_pylist()


def case_filter(db, res: Resolution, col: str) -> tuple[str, list]:
    """(SQL predicate, params) selecting the case hands by the hand-id column `col`.

    Plain chains: a subquery with the chain's own WHERE (no ids leave DuckDB). Spot chains:
    the case ids as an Arrow relation registered on `db` (built once per resolution)."""
    if res.plain:
        if not res.n_cases:
            return "FALSE", []
        return f"{col} IN (SELECT h.id {_FROM} WHERE {res.where})", list(res.params)
    import pyarrow as pa
    arr = res.memo(("case_ids_arrow",),
                   lambda: pa.array([h.hid for h in res.hands if h.case], pa.string()),
                   size=lambda a: a.nbytes + 1024, heavy=False)
    if not len(arr):
        return "FALSE", []
    return f"{col} IN (SELECT id FROM {register_ids(db, arr)})", []


def iter_records(db, res: Resolution, chunk: int = 20_000):
    """The case hands as HandRec lists (plain chains: fetched in chunks, never kept)."""
    if not res.plain:
        yield [h for h in res.hands if h.case]
        return
    if not res.n_cases:
        return
    cur = db.cursor()   # own cursor: callers run other queries on `db` between chunks
    try:
        cur.execute(f"{_SELECT} WHERE {res.where}{ORDER}", res.params)
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            yield [_rec(r) for r in rows]
    finally:
        cur.close()


class CaseRec:
    """The facts of one case hand that `split.Acc.add` and the Next / Faced tables read (plain
    chains: built per chunk, never kept). Same values as the matching HandRec fields."""

    __slots__ = ("hid", "won", "won_bb", "ev_bb", "ev", "rake", "sd", "win", "pre_opp",
                 "pre_case", "post_case", "rake_bb")
    hit = None   # plain chains have no hit point

    def __init__(self, hid, won, won_bb, ev_bb, ev, rake, sd, win, pre_opp, pre_case,
                 post_case, rake_bb):
        self.hid = hid
        self.won = won
        self.won_bb = won_bb
        self.ev_bb = ev_bb
        self.ev = ev
        self.rake = rake
        self.sd = sd
        self.win = win
        self.pre_opp = pre_opp
        self.pre_case = pre_case
        self.post_case = post_case
        self.rake_bb = rake_bb


# CaseRec fields, then the hand's stored sequence blob (the one hand_players row carrying it,
# app/h2n/CONTRACT.md), in one query.
_SEQ_SELECT = f"""SELECT h.id, {_D.format("COALESCE(hp.won, 0)")},
           {_D.format("COALESCE(hp.won_bb, 0)")},
           {_D.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)")},
           {_D.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount")},
           {_D.format("COALESCE(hp.rake, 0)")}, COALESCE(hp.went_to_showdown, FALSE),
           COALESCE(hp.is_winner, FALSE), COALESCE(hp.h2n_pre_opp, 0),
           COALESCE(hp.h2n_pre_case, 0), COALESCE(hp.h2n_post_case, 0),
           {_D.format("COALESCE(hp.rake_bb, 0)")}, sq.h2n_seq {_FROM}
    LEFT JOIN hand_players sq ON sq.hand_id = hp.hand_id AND sq.workspace_id = hp.workspace_id
        AND sq.h2n_seq IS NOT NULL"""


def iter_case_seqs(db, res: Resolution, chunk: int = 8192):
    """Plain chains: the case hands as (CaseRec list, {hand id: stored blob or None}) chunks in
    hand order, from one query (nothing is kept on the resolution)."""
    if not res.plain:
        raise PlainResolutionError("iter_case_seqs is for plain resolutions")
    if not res.n_cases:
        return
    cur = db.cursor()   # own cursor: callers run other queries on `db` between chunks
    try:
        cur.execute(f"{_SEQ_SELECT} WHERE {res.where}{ORDER}", res.params)
        while True:
            rows = cur.fetchmany(chunk)
            if not rows:
                break
            yield [CaseRec(*r[:12]) for r in rows], {r[0]: r[12] for r in rows}
    finally:
        cur.close()


def opponent_recs(db, workspace_id: int, ids: list[str], player_id: int
                  ) -> list[tuple[int, str, HandRec]]:
    """(player id, username, record) of every other player dealt in to the given hands
    (H2N-valid rows only, as the opponent's own Reports page would count them)."""
    out: list[tuple[int, str, HandRec]] = []
    for i in range(0, len(ids), 5000):
        chunk = ids[i:i + 5000]
        for r in db.execute(
            f"SELECT hp.player_id, p.username, {_COLS} {_FROM} "
            "JOIN players p ON p.id = hp.player_id "
            "WHERE h.workspace_id = ? AND hp.player_id <> ? AND COALESCE(hp.h2n_valid, TRUE) "
            "AND hp.hand_id IN (SELECT UNNEST(?::VARCHAR[]))",
            [workspace_id, player_id, chunk],
        ).fetchall():
            out.append((int(r[0]), r[1], _rec(r[2:])))
    return out


def fetch_seqs(db, workspace_id: int, ids: list[str]) -> dict[str, bytes]:
    """Stored sequence blobs of the given hands (one row per hand carries it)."""
    out: dict[str, bytes] = {}
    if not ids:
        return out
    name = register_ids(db, ids)
    try:
        for hid, blob in db.execute(
            "SELECT hand_id, h2n_seq FROM hand_players "
            f"WHERE workspace_id = ? AND h2n_seq IS NOT NULL AND hand_id IN (SELECT id FROM {name})",
            [workspace_id],
        ).fetchall():
            out[hid] = bytes(blob)
    finally:
        db.unregister(name)
    return out


class SeqSource:
    """Decoded sequences of a resolution's hands (stored blob, else raw_text replay)."""

    def __init__(self, db, workspace_id: int, blobs: dict[str, bytes | None]):
        self.db = db
        self.workspace_id = workspace_id
        self.blobs = blobs
        self._replayed: dict[str, Any] = {}

    def prefetch_missing(self, ids: list[str]) -> None:
        missing = [h for h in ids if self.blobs.get(h) is None and h not in self._replayed]
        if not missing:
            return
        from app.h2n.replay import replay
        raw = _fetch_raw(self.db, self.workspace_id, missing)
        for hid in missing:
            seq = None
            src = raw.get(hid)
            if src and src[0]:
                try:
                    seq = replay(src[0], int(src[1]))
                except Exception:
                    log.warning("reports replay failed for hand %s", hid, exc_info=True)
            self._replayed[hid] = seq

    def get(self, hid: str):
        blob = self.blobs.get(hid)
        if blob is not None:
            seq = decode_sequence(blob)
            if seq is not None:
                return seq
        if hid not in self._replayed:
            self.prefetch_missing([hid])
        return self._replayed.get(hid)


def target_player(db, workspace_id: int, player_id: int | None) -> int | None:
    if player_id is not None:
        if not db.execute("SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Player not found")
        return player_id
    return get_hero_player_id(db, workspace_id)


def _compute(db, workspace_id: int, player_id: int | None, chain: list[_Step],
             day_start: int = 0) -> Resolution:
    ctx = chain_ctx(chain)
    steps = spot_steps(chain)
    res = Resolution(workspace_id, player_id, None, chain, ctx, bool(steps), 0)
    if player_id is None:
        return res
    row = db.execute("SELECT username FROM players WHERE id = ?", [player_id]).fetchone()
    res.username = row[0] if row else None
    base = [player_id, workspace_id]
    res.total_hands = int(db.execute(f"SELECT COUNT(*) {_FROM} WHERE {_BASE_WHERE}",
                                     base).fetchone()[0])
    psql, pparams = plain_sql(chain, day_start)
    res.where = _BASE_WHERE + psql + _row_bits_sql(chain)
    res.params = [*base, *pparams]
    if not steps:
        res.n_cases = res.total_hands if res.where == _BASE_WHERE else int(db.execute(
            f"SELECT COUNT(*) {_FROM} WHERE {res.where}", res.params).fetchone()[0])
        res.hands = PlainCases(res.n_cases)
        return res
    rows = db.execute(f"{_SELECT} WHERE {res.where}{ORDER}", res.params).fetchall()
    ids = [r[0] for r in rows]
    blobs = fetch_seqs(db, workspace_id, ids)
    res.blobs = {h: blobs.get(h) for h in ids}
    src = SeqSource(db, workspace_id, res.blobs)
    src.prefetch_missing(ids)
    name = res.username
    # Next / Faced tables are filled here from the sequence decoded for the spot step
    # (same evaluators, same hand order as split.action_table), so no tab decodes it again.
    from app.reports import split as split_mod
    fill = split_mod.table_fillers(ctx) if name else {}
    out: list[HandRec] = []
    for r in rows:
        seq = src.get(r[0])
        if seq is None:
            res.replay_failed += 1
            continue
        p = seq.index.get(name)
        if p is None:
            continue
        try:
            code, hit = evaluate_spot(seq, p, steps)
        except Exception:
            log.warning("reports spot evaluation failed for hand %s", r[0], exc_info=True)
            res.replay_failed += 1
            continue
        if not code:
            continue
        rec = _rec(r, bool(code & CASE), hit)
        a = seq.streets[hit[0]][hit[1]]
        rec.hit_eff = a.eff
        rec.hit_hero = a.actor == p
        if a.actor == p:
            rec.ap = 0.0 if a.eff == spots.FOLD else rec.ev_bb + spots.committed_bb(seq, p, hit)
        out.append(rec)
        if fill and rec.case:
            try:
                split_mod.fill_tables(fill, seq, p, rec)
            except Exception:  # the lazy path recomputes (and reports) it
                log.warning("reports table fill failed for hand %s", r[0], exc_info=True)
                fill = {}
    res.hands = out
    res.n_cases = sum(1 for h in out if h.case)
    res.blobs = {h.hid: res.blobs.get(h.hid) for h in out}
    res.blob_bytes = sum(len(b) + 120 if b is not None else 120 for b in res.blobs.values())
    for which, (_cands, _ev, table) in fill.items():
        res.tables[("table", which)] = table
        res.table_bytes += 600 * len(table) + 1024
    return res


# ── cache ────────────────────────────────────────────────────────────────


class _LRU:
    """LRU of resolutions, bounded by entry count and by their estimated resident bytes
    (`Resolution.approx_bytes`: records, blobs and cached tables). An entry over the whole
    budget is not kept (callers waiting on the same computation still get it)."""

    def __init__(self, capacity: int, max_bytes: int):
        self.capacity = capacity
        self.max_bytes = max_bytes
        self._d: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            v = self._d.get(key)
            if v is not None:
                self._d.move_to_end(key)
            return v

    def put(self, key, value) -> None:
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            self._trim()

    def trim(self) -> None:
        with self._lock:
            self._trim()

    def _trim(self) -> None:
        total = sum(v.approx_bytes() for v in self._d.values())
        while self._d and (len(self._d) > self.capacity or total > self.max_bytes):
            _k, v = self._d.popitem(last=False)
            total -= v.approx_bytes()

    def nbytes(self) -> int:
        with self._lock:
            return sum(v.approx_bytes() for v in self._d.values())

    def __len__(self) -> int:
        return len(self._d)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


CACHE_MAX_BYTES = 384 << 20
_CACHE = _LRU(32, CACHE_MAX_BYTES)
_inflight: dict = {}
_inflight_lock = threading.Lock()


def clear_cache() -> None:
    _CACHE.clear()


# Every write that changes hands / hand_players bumps the generation: drop the resolutions
# (keying on the generation alone would leave them in memory until LRU eviction).
data_generation.on_bump(clear_cache)


def bump_generation() -> None:
    """Call after any write that changes hands / hand_players (invalidates resolutions)."""
    data_generation.bump()
    _CACHE.clear()


def data_version(db, workspace_id: int) -> tuple:
    n, last = db.execute(
        "SELECT COUNT(*), MAX(imported_at) FROM hands WHERE workspace_id = ?", [workspace_id]
    ).fetchone()
    top = db.execute("SELECT MAX(id) FROM hand_players WHERE workspace_id = ?",
                     [workspace_id]).fetchone()[0]
    return (int(n), str(last), top, data_generation.current())


class _Flight:
    """One in-progress computation of a cache key; waiters take its result (`resolve`: None
    when the computation failed; `Resolution.memo`: `ok` False). On failure they try again."""

    __slots__ = ("done", "result", "ok")

    def __init__(self):
        self.done = threading.Event()
        self.result = None
        self.ok = False


def resolve(db, workspace_id: int, player_id: int | None, chain: list[_Step]) -> Resolution:
    """Resolution of `chain` for the player (None = the workspace's active hero), cached.

    Parallel requests for one key share one computation, also during a background rebuild
    (when nothing is cached because the data is changing).

    A cold spot-chain resolve (per-hand sequence decoding and evaluation) runs in a
    `heavy_slot()`: every caller (Reports endpoints, hand list, graph, export) is throttled
    here. The computing request takes the slot *before* it registers the in-flight entry, so
    an entry always belongs to a request that is already running; requests waiting for it
    hold no slot of their own (unless their caller already had one, which then can't
    deadlock: the entry's owner never waits for a slot). Plain chains resolve with two
    COUNT queries and take no slot."""
    target = target_player(db, workspace_id, player_id)
    from app.app_settings import get_app_settings
    day_start = int(get_app_settings(db)["day_start_hour"])
    cacheable = not get_rebuild_status().get("active")
    key = (workspace_id, target, canonical(chain), data_version(db, workspace_id), day_start)
    if cacheable:
        hit = _CACHE.get(key)
        if hit is not None:
            return hit
    slot = heavy_slot if spot_steps(chain) else nullcontext
    while True:
        with _inflight_lock:
            flight = _inflight.get(key)
        if flight is not None:            # someone is computing it: wait without a slot
            flight.done.wait()
            if flight.result is not None:
                return flight.result
            continue                      # that computation failed: try again
        with slot():
            with _inflight_lock:
                flight = _inflight.get(key)
                owner = flight is None
                if owner:
                    flight = _inflight[key] = _Flight()
            if not owner:
                continue                  # lost the race while taking the slot: leave it, wait
            try:
                hit = _CACHE.get(key) if cacheable else None
                if hit is None:
                    hit = _compute(db, workspace_id, target, chain, day_start)
                    if cacheable:
                        _CACHE.put(key, hit)
                flight.result = hit
                return hit
            finally:
                with _inflight_lock:
                    if _inflight.get(key) is flight:
                        del _inflight[key]
                flight.done.set()


def resolved_ids(db, workspace_id: int, player_id: int | None, chain: list[_Step]) -> list[str]:
    """Case hand ids of the chain (the hands a page lists / graphs)."""
    return case_ids(db, resolve(db, workspace_id, player_id, chain))


__all__ = [
    "Step", "ReportQuery", "CHAIN", "parse_chain", "resolve", "resolved_ids", "Resolution",
    "HandRec", "SeqSource", "plain_sql", "opponent_recs", "card_class", "card_class_sql", "CLASSES",
    "chain_ctx", "canonical", "clear_cache", "POS_NAMES", "case_ids", "case_filter",
    "iter_records", "iter_case_seqs", "CaseRec", "register_ids", "stakes_caption",
    "stack_caption", "target_player", "ROWS",
]
