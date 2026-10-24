"""Filters of the General screen as either the old query params or a Reports chain.

The old params (stakes / game_mode / date_from / date_to) and the new `chain` (JSON array of
plain Reports steps: date, stakes, mode) both end up as AND-ed SQL over `hands h` /
`hand_players hp`, plus the same filter written as chain steps (`CellDetail.chain`).
The chain SQL is `app.reports.chain.plain_sql`, so a dashboard's numbers equal Reports'.
"""

from __future__ import annotations

import json
import re

from fastapi import HTTPException
from pydantic import ValidationError

from app.date_filters import bound_sql
from app.h2n.columns import H2N_POSITIONS

DASHBOARD_KINDS = ("date", "stakes", "mode")
_PLAIN_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_plain_steps(raw) -> list[dict]:
    """Validate plain date/stakes/mode steps; return the original dicts (extra `preset` kept).

    Raises ValueError. The Reports models forbid extra keys, so a copy without `preset` is
    validated while the stored/echoed steps stay as given.
    """
    from app.reports.chain import CHAIN

    if not isinstance(raw, list):
        raise ValueError("chain must be a list of steps")
    copies = []
    for st in raw:
        if not isinstance(st, dict):
            raise ValueError("a step must be an object")
        if st.get("k") not in DASHBOARD_KINDS:
            raise ValueError(f"step kind {st.get('k')!r} is not allowed here")
        copies.append({k: v for k, v in st.items() if k != "preset"})
    try:
        CHAIN.validate_python(copies)
    except ValidationError as e:
        raise ValueError(str(e)) from e
    return list(raw)


def _models(steps: list[dict]):
    from app.reports.chain import CHAIN

    return CHAIN.validate_python([{k: v for k, v in s.items() if k != "preset"} for s in steps])


def params_to_steps(stakes, game_mode, date_from, date_to) -> list[dict]:
    """Old filter params as plain steps. Regular mode ('') is `mode: regular`
    (`game_mode = ''` and `<> 'Fast Fold'` select the same hands: the column is NOT NULL and
    only holds '' or 'Fast Fold'). A date bound that is not a plain YYYY-MM-DD (checkpoint
    datetimes) cannot be a date step and is left out."""
    out: list[dict] = []
    f = date_from if date_from and _PLAIN_DATE.match(date_from) else None
    t = date_to if date_to and _PLAIN_DATE.match(date_to) else None
    if f or t:
        step: dict = {"k": "date"}
        if f:
            step["from"] = f
        if t:
            step["to"] = t
        out.append(step)
    if stakes:
        out.append({"k": "stakes", "v": [stakes]})
    if game_mode is not None and game_mode in ("", "Fast Fold"):
        out.append({"k": "mode", "v": "fast" if game_mode == "Fast Fold" else "regular"})
    return out


def old_filters(stakes, game_mode, date_from, date_to, day_start: int = 0) -> tuple[str, list]:
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


def resolve_filters(chain: str | None, stakes, game_mode, date_from, date_to,
                    day_start: int = 0) -> tuple[str, list, list[dict]]:
    """(sql, params, steps) of the request's filters. 422 on a bad or conflicting request."""
    if chain is None:
        return (*old_filters(stakes, game_mode, date_from, date_to, day_start),
                params_to_steps(stakes, game_mode, date_from, date_to))
    if stakes or game_mode is not None or date_from or date_to:
        raise HTTPException(status_code=422,
                            detail="chain cannot be combined with stakes/game_mode/date_from/date_to")
    try:
        raw = json.loads(chain) if chain.strip() else []
        steps = validate_plain_steps(raw)
        from app.reports.chain import plain_sql
        sql, params = plain_sql(_models(steps), day_start)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=f"invalid chain: {e}") from e
    return sql, params, steps


def cell_steps(positions, exclude: bool, row: str, label: str) -> list[dict]:
    """pos step (when the cell has a position group) + the row step."""
    out: list[dict] = []
    if positions is not None:
        pos = [p for p in H2N_POSITIONS if (p not in positions) == exclude]
        out.append({"k": "pos", "v": pos})
    out.append({"k": "row", "key": row, "label": label})
    return out
