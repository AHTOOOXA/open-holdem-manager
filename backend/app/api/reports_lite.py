"""Reports screen endpoints (contract: frontend/src/lib/reports/types.ts).

    POST /api/reports/split            SplitQuery -> SplitResponse
    POST /api/reports/spot             ReportQuery -> SpotResponse
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

from typing import Literal

from fastapi import APIRouter, HTTPException

from app.db import get_read_cursor
from app.reports import split as split_mod
from app.reports import views
from app.reports.chain import ReportQuery, parse_chain, resolve

router = APIRouter()

SplitType = Literal["results", "positions", "next_actions", "faced_next", "bet_sizing",
                    "stack_sizes", "hour_of_day", "table_size"]


class SplitQuery(ReportQuery):
    type: SplitType


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
def post_spot(q: ReportQuery) -> dict:
    db, res = _resolve(q)
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


__all__ = ["router", "chain_hand_ids"]
