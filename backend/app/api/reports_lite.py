"""Reports screen endpoints (contract: frontend/src/lib/reports/types.ts).

    POST /api/reports/split            SplitQuery -> SplitResponse
    POST /api/reports/spot             SpotQuery -> SpotResponse (`recipe`: Sessions recipes)
    POST /api/reports/preflop-range    ReportQuery -> PreflopRangeResponse
    POST /api/reports/hand-strength    HandStrengthQuery -> HandStrengthResponse
    GET  /api/reports/quick-filters    -> QuickFilter[]

Every POST takes the full filter chain and the player (default: the workspace's active
hero); `app.reports.chain.resolve` turns it into hands + hit points (cached), the
modules under `app/reports/` compute the answers. An invalid chain is a 422 (request
validation). GET /api/hands and GET /api/reports/graph take the same chain as a
URL-encoded JSON `chain` query parameter (`chain_hand_ids`).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException

from app.db import get_read_cursor
from app.reports import split as split_mod
from app.reports import views
from app.reports.chain import ReportQuery, parse_chain, resolve

router = APIRouter()

SplitType = Literal["results", "positions", "next_actions", "faced_next", "bet_sizing",
                    "stack_sizes", "hour_of_day", "table_size", "tables", "players"]


class SplitQuery(ReportQuery):
    type: SplitType


class SpotQuery(ReportQuery):
    recipe: Optional[Literal["session", "table", "villain"]] = None


class HandStrengthQuery(ReportQuery):
    street: Literal["flop", "turn", "river"]


def _resolve(q: ReportQuery):
    db = get_read_cursor()
    try:
        return db, resolve(db, q.workspace_id, q.player_id, q.chain)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/reports/split")
def post_split(q: SplitQuery) -> dict:
    db, res = _resolve(q)
    return split_mod.split(db, res, q.type)


@router.post("/reports/spot")
def post_spot(q: SpotQuery) -> dict:
    db, res = _resolve(q)
    if q.recipe:
        return views.recipe(db, res, q.recipe)
    return views.spot(db, res)


@router.post("/reports/preflop-range")
def post_preflop_range(q: ReportQuery) -> dict:
    _db, res = _resolve(q)
    return views.preflop_range(res)


@router.post("/reports/hand-strength")
def post_hand_strength(q: HandStrengthQuery) -> dict:
    _db, res = _resolve(q)
    return views.hand_strength(res, q.street)


@router.get("/reports/quick-filters")
def get_quick_filters() -> list[dict]:
    return views.quick_filters()


@dataclass(frozen=True)
class ChainScope:
    """The case hands of a Reports chain for one player, as a SQL predicate on a hand-id column.

    Consumers (hand list, graph, export) use `where("h.id")` in their own WHERE clause instead of
    binding the case ids as a parameter list, and `count` instead of re-counting the case hands.
    The predicate is only valid on the cursor `chain_scope` was called with (it may reference a
    relation registered on that cursor), and only for the request's lifetime.
    """

    count: int                          # number of case hands (0 = the chain selects nothing)
    sql: str                            # predicate with a `{col}` placeholder for the hand-id column
    params: list = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return self.count == 0

    def where(self, col: str) -> tuple[str, list]:
        """(predicate, params) for `col` (e.g. "h.id")."""
        return self.sql.format(col=col), list(self.params)


_scope_names = itertools.count()


def chain_scope(db, workspace_id: int, player_id: int | None, chain: str | None
                ) -> ChainScope | None:
    """Scope of a URL-encoded JSON chain (None: no `chain` param given); 422 if invalid.

    Same hand set as `chain_hand_ids` (any given chain, even `[]`, keeps only H2N-valid hands).
    Contract implementation: registers the resolution's case ids as an Arrow relation on `db`.
    Plain chains (no spot steps) may instead return a pure SQL predicate without materializing
    the ids; consumers must not depend on which form they get.
    """
    if chain is None or not chain.strip():
        return None
    try:
        steps = parse_chain(chain)
        ids = resolve(db, workspace_id, player_id, steps).case_ids
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid chain: {e}")
    if not ids:
        return ChainScope(0, "FALSE")
    import pyarrow as pa
    name = f"_chain_scope_{next(_scope_names)}"
    db.register(name, pa.table({"id": pa.array(ids, pa.string())}))
    return ChainScope(len(ids), f"{{col}} IN (SELECT id FROM {name})")


def chain_hand_ids(db, workspace_id: int, player_id: int | None, chain: str | None
                   ) -> list[str] | None:
    """Case hand ids of a URL-encoded JSON chain (None: no `chain` param given); 422 if invalid.

    Any given chain, even an empty `[]`, resolves to the hands the Reports spot count uses:
    `COALESCE(hp.h2n_valid, TRUE)` is applied, so page 0 (`chain=[]`) shows the same counts
    as the deeper pages. Without a `chain` param the endpoint's own filters apply unchanged.
    """
    if chain is None or not chain.strip():
        return None
    try:
        steps = parse_chain(chain)
        return resolve(db, workspace_id, player_id, steps).case_ids
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid chain: {e}")


__all__ = ["router", "chain_hand_ids", "chain_scope", "ChainScope"]
