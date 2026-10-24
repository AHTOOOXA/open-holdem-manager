"""Sessions list (contract: frontend/src/lib/sessions/types.ts).

    GET /api/sessions?workspace_id=&player_id=&date_from=&date_to=   -> SessionsResponse
    GET /api/sessions/live?workspace_id=                            -> SessionsLive

Sessions are built over all of the player's hands (app/sessions_h2n.py). The date range
(ISO dates, inclusive local days) only picks the listed sessions (any hand in range) and
what a row's Hands / Won count; Duration is always the whole session. A session page is a
Reports chain starting with the row's `filter` step (POST /api/reports/* with
`recipe: 'session'`, GET /api/hands, GET /api/reports/graph), which ignores the date range.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.app_settings import get_app_settings
from app.db import get_read_cursor
from app.heroes import resolve_hero
from app import sessions_h2n as sh

router = APIRouter()


def _player(db, workspace_id: int, player_id: int | None) -> dict | None:
    if player_id is None:
        ref = resolve_hero(db, workspace_id)
        if ref is None:
            return None
        return {"id": ref.player_id, "username": ref.username, "site": ref.site_code}
    row = db.execute(
        "SELECT p.id, p.username, s.code FROM players p JOIN sites s ON s.id = p.site_id "
        "WHERE p.id = ?", [player_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return {"id": int(row[0]), "username": row[1], "site": row[2]}


def _row(s: sh.SessionRow, now: _dt.datetime, max_break_s: int, numeric: bool) -> dict:
    return {
        "id": s.id,
        "number": s.number,
        "start": sh.iso(s.start),
        "last_hand_at": sh.iso(s.last_start),
        "end": sh.iso(s.end),
        "duration_s": s.duration_s,
        "is_live": sh.is_live(s.end, now, max_break_s),
        "hands": s.hands,
        "won": s.won,
        "won_ev": s.won_ev,
        "won_bb": s.won_bb,
        "won_ev_bb": s.won_ev_bb,
        "filter": {"k": "session", "start": sh.iso(s.start), "end": sh.iso(s.last_start),
                   "label": sh.caption(s.start, numeric, now)},
    }


def list_sessions(db, workspace_id: int, player_id: int | None = None,
                  date_from: _dt.date | None = None, date_to: _dt.date | None = None,
                  now: _dt.datetime | None = None) -> dict:
    settings = get_app_settings(db)
    max_break_s = int(settings["session_max_break_minutes"]) * 60
    out = {"player": None, "sessions": [], "summary": None,
           "max_break_minutes": int(settings["session_max_break_minutes"])}
    player = _player(db, workspace_id, player_id)
    if player is None:
        return out
    rows = sh.build_sessions(db, workspace_id, player["id"], max_break_s, date_from, date_to)
    if not rows:
        return out  # no hands: player null (contract)
    out["player"] = player
    # local naive clock, the same clock as hands.played_at (see app/sessions_h2n.py)
    now = now or _dt.datetime.now()
    ranged = date_from is not None or date_to is not None
    listed = [r for r in rows if r.hands > 0 or not ranged]
    listed.sort(key=lambda r: r.start, reverse=True)
    out["sessions"] = [_row(r, now, max_break_s, bool(settings["numeric_date_format"]))
                       for r in listed]
    if len(listed) > 1:
        out["summary"] = {
            "hands": sum(r.hands for r in listed),
            "duration_s": sum(r.duration_s for r in listed),
            "won": sum(r.won for r in listed),
            "won_ev": sum(r.won_ev for r in listed),
            "won_bb": sum(r.won_bb for r in listed),
            "won_ev_bb": sum(r.won_ev_bb for r in listed),
        }
    return out


def live_session(db, workspace_id: int, now: _dt.datetime | None = None) -> dict:
    out = {"live": False, "session_id": None, "start": None}
    ref = resolve_hero(db, workspace_id)
    if ref is None:
        return out
    max_break_s = int(get_app_settings(db)["session_max_break_minutes"]) * 60
    rows = sh.build_sessions(db, workspace_id, ref.player_id, max_break_s)
    if not rows:
        return out
    last = max(rows, key=lambda r: r.end)
    if sh.is_live(last.end, now or _dt.datetime.now(), max_break_s):
        out.update(live=True, session_id=last.id, start=sh.iso(last.start))
    return out


@router.get("/sessions")
def get_sessions(workspace_id: int = Query(1), player_id: Optional[int] = Query(None),
                 date_from: Optional[_dt.date] = Query(None),
                 date_to: Optional[_dt.date] = Query(None)) -> dict:
    return list_sessions(get_read_cursor(), workspace_id, player_id, date_from, date_to)


@router.get("/sessions/live")
def get_sessions_live(workspace_id: int = Query(1)) -> dict:
    return live_session(get_read_cursor(), workspace_id)


__all__ = ["router", "list_sessions", "live_session"]
