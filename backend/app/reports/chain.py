"""Reports filter chain: request models, plain-step SQL and per-hand spot resolution.

Contract: frontend/src/lib/reports/types.ts (`Step`, `ReportQuery`).

`resolve(db, workspace_id, player_id, chain)` returns a `Resolution`: every hand of the
player that passes the chain's plain steps and is an opportunity of its last spot step,
with the hit point and the per-hand facts the reports read. Plain chains (no spot step)
have no hit point and every matching hand is a case.

- Plain steps (pos, stakes, mode, tsize, date, hour, stack, game, cells, hv) become one SQL
  WHERE over `hands` / `hand_players`, together with `COALESCE(hp.h2n_valid, TRUE)` (the
  General screen leaves hands H2N would refuse out of every number).
- Spot steps (row, next, faced, betsize) are evaluated in chain order on the hand's stored
  action sequence (`hand_players.h2n_seq`, re-parsed from `raw_text` when missing) by
  `app.reports.spots`. Every spot step but the last must be a case; the last one decides
  case / opportunity. `row` steps also prefilter in SQL on their General bit (case bit, or
  the opportunity bit for the last spot step).

Resolutions are cached (LRU) by workspace, player, the chain without labels and a data
version (hand count, last import time and the highest `hand_players.id`, which a rebuild
moves), so the several requests a Reports page fires share one resolution; split tables
computed from a resolution are cached on it.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.api.general_popup import _BUCKET_BY_ID, _fetch_raw, _size_hits
from app.date_filters import DATE_TO_SQL
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


class RowStep(_Step):
    k: Literal["row"]
    key: str

    @field_validator("key")
    @classmethod
    def _known(cls, v):
        if v not in COMPILED:
            raise ValueError(f"unknown row {v!r}")
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
          CellsStep, HvStep, RowStep, NextStep, FacedStep, BetsizeStep],
    Field(discriminator="k"),
]
CHAIN = TypeAdapter(list[Step])

PLAIN_KINDS = frozenset(("pos", "stakes", "mode", "tsize", "date", "hour", "stack", "game",
                         "cells", "hv"))
SPOT_KINDS = frozenset(("row", "next", "faced", "betsize"))


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


def plain_sql(chain: list[_Step]) -> tuple[str, list]:
    """AND-ed SQL conditions (leading " AND ") and params of the chain's plain steps."""
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
                sql.append("h.played_at >= CAST(? AS DATE)")
                params.append(st.from_[:10])
            if st.to:
                sql.append(DATE_TO_SQL)
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
    return "".join(" AND " + s for s in sql), params


def _row_bits_sql(chain: list[_Step]) -> str:
    """Bit prefilter of the row steps: case bit, or opp bit for the last spot step."""
    moving = [i for i, st in enumerate(chain) if st.k in ("row", "next", "faced")]
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
    for st in chain:
        if st.k == "row":
            ctx = spots.row_ctx(st.key)
        elif st.k == "next":
            ctx = spots.next_spot(ctx, spots.STREET_INDEX[st.street], st.a)
        elif st.k == "faced":
            ctx = spots.faced_spot(ctx, spots.STREET_INDEX[st.street], st.a)
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
    """One hand of a resolution (facts from SQL + the spot result)."""

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
    hv: tuple[int | None, int | None, int | None]
    pre_opp: int
    pre_case: int
    post_opp: int
    post_case: int
    ap: float | None = None      # Action Profit, bb (hero action hits)
    hit_eff: int | None = None   # effective type of the hit action
    hit_hero: bool = False       # the hit action is the player's own


@dataclass
class Resolution:
    workspace_id: int
    player_id: int | None
    username: str | None
    chain: list
    ctx: SpotCtx
    has_spot: bool
    total_hands: int
    hands: list[HandRec] = field(default_factory=list)   # cases and opportunity-only hands
    blobs: dict[str, bytes | None] = field(default_factory=dict)
    replay_failed: int = 0
    tables: dict = field(default_factory=dict)            # cached derived tables
    lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def cases(self) -> list[HandRec]:
        return [h for h in self.hands if h.case]

    @property
    def case_ids(self) -> list[str]:
        return [h.hid for h in self.hands if h.case]


_SELECT = """
    SELECT h.id, COALESCE(hp.won, 0), COALESCE(hp.won_bb, 0),
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0),
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount,
           COALESCE(hp.rake, 0), COALESCE(hp.went_to_showdown, FALSE),
           COALESCE(hp.is_winner, FALSE), hp.h2n_pos, hp.stack_bb, h.played_at, h.stakes,
           h.bb_amount, h.game_mode, h.table_size, hp.card1, hp.card2,
           hp.hv_flop, hp.hv_turn, hp.hv_river,
           COALESCE(hp.h2n_pre_opp, 0), COALESCE(hp.h2n_pre_case, 0),
           COALESCE(hp.h2n_post_opp, 0), COALESCE(hp.h2n_post_case, 0)
    FROM hand_players hp
    JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
"""
_BASE_WHERE = "hp.player_id = ? AND h.workspace_id = ? AND COALESCE(hp.h2n_valid, TRUE)"


def _rec(r, case: bool = True, hit=None) -> HandRec:
    f = lambda x: float(x) if x is not None else 0.0  # noqa: E731
    return HandRec(
        hid=r[0], case=case, hit=hit, won=f(r[1]), won_bb=f(r[2]), ev_bb=f(r[3]), ev=f(r[4]),
        rake=f(r[5]), sd=bool(r[6]), win=bool(r[7]), pos=r[8],
        stack_bb=None if r[9] is None else float(r[9]), played_at=r[10], stakes=r[11],
        bb_amount=f(r[12]), mode=r[13] or "", tsize=r[14], card1=r[15], card2=r[16],
        hv=(r[17], r[18], r[19]), pre_opp=int(r[20]), pre_case=int(r[21]),
        post_opp=int(r[22]), post_case=int(r[23]),
    )


def fetch_seqs(db, workspace_id: int, ids: list[str]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for i in range(0, len(ids), 5000):
        chunk = ids[i:i + 5000]
        for hid, blob in db.execute(
            "SELECT hand_id, h2n_seq FROM hand_players "
            "WHERE workspace_id = ? AND h2n_seq IS NOT NULL "
            "AND hand_id IN (SELECT UNNEST(?::VARCHAR[]))",
            [workspace_id, chunk],
        ).fetchall():
            out[hid] = bytes(blob)
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


def _compute(db, workspace_id: int, player_id: int | None, chain: list[_Step]) -> Resolution:
    ctx = chain_ctx(chain)
    steps = spot_steps(chain)
    res = Resolution(workspace_id, player_id, None, chain, ctx, bool(steps), 0)
    if player_id is None:
        return res
    row = db.execute("SELECT username FROM players WHERE id = ?", [player_id]).fetchone()
    res.username = row[0] if row else None
    res.total_hands = int(db.execute(
        "SELECT COUNT(*) FROM hand_players hp JOIN hands h ON hp.hand_id = h.id "
        f"AND hp.workspace_id = h.workspace_id WHERE {_BASE_WHERE}",
        [player_id, workspace_id]).fetchone()[0])
    psql, pparams = plain_sql(chain)
    where = _BASE_WHERE + psql + _row_bits_sql(chain)
    rows = db.execute(f"{_SELECT} WHERE {where}", [player_id, workspace_id, *pparams]).fetchall()
    if not steps:
        res.hands = [_rec(r) for r in rows]
        return res
    ids = [r[0] for r in rows]
    blobs = fetch_seqs(db, workspace_id, ids)
    res.blobs = {h: blobs.get(h) for h in ids}
    src = SeqSource(db, workspace_id, res.blobs)
    src.prefetch_missing(ids)
    name = res.username
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
    res.hands = out
    res.blobs = {h.hid: res.blobs.get(h.hid) for h in out}
    return res


# ── cache ────────────────────────────────────────────────────────────────


class _LRU:
    """LRU of resolutions, bounded by entry count and by the total number of hand records."""

    def __init__(self, capacity: int, max_hands: int):
        self.capacity = capacity
        self.max_hands = max_hands
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
            while len(self._d) > 1 and (
                    len(self._d) > self.capacity
                    or sum(len(v.hands) for v in self._d.values()) > self.max_hands):
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()


_CACHE = _LRU(32, 600_000)
_inflight: dict = {}
_inflight_lock = threading.Lock()


def clear_cache() -> None:
    _CACHE.clear()


def bump_generation() -> None:
    """Call after any write that changes hands / hand_players (invalidates resolutions)."""
    from app import data_generation
    data_generation.bump()
    _CACHE.clear()


def data_version(db, workspace_id: int) -> tuple:
    n, last = db.execute(
        "SELECT COUNT(*), MAX(imported_at) FROM hands WHERE workspace_id = ?", [workspace_id]
    ).fetchone()
    top = db.execute("SELECT MAX(id) FROM hand_players WHERE workspace_id = ?",
                     [workspace_id]).fetchone()[0]
    from app import data_generation
    return (int(n), str(last), top, data_generation.current())


def resolve(db, workspace_id: int, player_id: int | None, chain: list[_Step]) -> Resolution:
    """Resolution of `chain` for the player (None = the workspace's active hero), cached."""
    target = target_player(db, workspace_id, player_id)
    if get_rebuild_status().get("active"):
        return _compute(db, workspace_id, target, chain)
    key = (workspace_id, target, canonical(chain), data_version(db, workspace_id))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    # One computation per key at a time: parallel requests of one page wait for it.
    with _inflight_lock:
        lock = _inflight.setdefault(key, threading.Lock())
    try:
        with lock:
            hit = _CACHE.get(key)
            if hit is None:
                hit = _compute(db, workspace_id, target, chain)
                _CACHE.put(key, hit)
    finally:
        with _inflight_lock:
            _inflight.pop(key, None)
    return hit


def resolved_ids(db, workspace_id: int, player_id: int | None, chain: list[_Step]) -> list[str]:
    """Case hand ids of the chain (the hands a page lists / graphs)."""
    return resolve(db, workspace_id, player_id, chain).case_ids


__all__ = [
    "Step", "ReportQuery", "CHAIN", "parse_chain", "resolve", "resolved_ids", "Resolution",
    "HandRec", "SeqSource", "plain_sql", "card_class", "card_class_sql", "CLASSES",
    "chain_ctx", "canonical", "clear_cache", "POS_NAMES",
    "stakes_caption", "stack_caption", "target_player", "ROWS",
]
