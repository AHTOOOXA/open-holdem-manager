from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import math

from app.db import get_db, db_lock, get_read_cursor, get_hero_player_id
from app.parsers.common import POSITIONS_BY_COUNT
from app.stats_engine import ResultCache, compute_player_stats
from app.models import HeroStats
from app.config_sections import get_markers

router = APIRouter()

# ── Player list ─────────────────────────────────────────────────────

class PlayerMarker(BaseModel):
    id: int
    name: str
    color: str


def resolve_marker(markers: list[dict], reg: bool | None, color_tag: str | None) -> PlayerMarker | None:
    """Manual marker (players.color_tag = marker id as a string) wins; else the first marker
    whose is_regular matches the reg classification (none when the player has no hands)."""
    if color_tag:
        for m in markers:
            if str(m["id"]) == color_tag.strip():
                return PlayerMarker(id=m["id"], name=m["name"], color=m["color"])
    if reg is not None:
        for m in markers:
            if m["is_regular"] == reg:
                return PlayerMarker(id=m["id"], name=m["name"], color=m["color"])
    return None


class PlayerSummary(BaseModel):
    id: int
    username: str
    player_type: str = "UNK"
    hands: int = 0
    vpip: float | None = None
    pfr: float | None = None
    three_bet: float | None = None
    af: float | None = None
    last_seen: str | None = None
    stakes: list[str] = []
    site: str | None = None  # site name, e.g. "GGPoker"
    reg: bool | None = None  # configured reg rule; null = no hands
    marker: PlayerMarker | None = None


class PlayerListResponse(BaseModel):
    players: list[PlayerSummary]
    total: int
    page: int
    per_page: int
    total_pages: int


@router.get("/players", response_model=PlayerListResponse)
def list_players(
    search: Optional[str] = None,
    player_type: Optional[str] = None,
    min_hands: int = Query(20, ge=0),
    sort_by: str = Query("hands"),
    sort_dir: str = Query("desc"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    sort_key = sort_by if sort_by in _LIST_SORTS else "hands"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    types = [t.strip().upper() for t in player_type.split(",") if t.strip()] if player_type else []
    key = ("list", workspace_id, search.strip() if search else None, tuple(types),
           min_hands, sort_key, direction, page, per_page)
    rows, total, stakes_map = _LIST_CACHE.get_or_compute(
        db, key,
        lambda: _player_list_rows(db, workspace_id, search, types, min_hands, sort_key,
                                  direction, page, per_page),
        heavy=True,
    )
    total_pages = max(1, math.ceil(total / per_page))

    if not rows:
        return PlayerListResponse(
            players=[], total=total, page=page,
            per_page=per_page, total_pages=total_pages,
        )

    # Editable / config parts are read fresh: colour tag (player notes), site, markers
    player_ids = [r[0] for r in rows]
    ph = ",".join("?" for _ in player_ids)
    extra = {
        pid: (color_tag, site)
        for pid, color_tag, site in db.execute(
            f"SELECT p.id, p.color_tag, s.name FROM players p "
            f"LEFT JOIN sites s ON s.id = p.site_id WHERE p.id IN ({ph})",
            player_ids,
        ).fetchall()
    }

    markers = get_markers(db)
    players = []
    for r in rows:
        color_tag, site = extra.get(r[0], (None, None))
        players.append(PlayerSummary(
            id=r[0],
            username=r[1],
            player_type=r[2] or "UNK",
            hands=r[3],
            vpip=round(float(r[4]), 1) if r[4] is not None else None,
            pfr=round(float(r[5]), 1) if r[5] is not None else None,
            three_bet=round(float(r[6]), 1) if r[6] is not None else None,
            af=round(float(r[7]), 2) if r[7] is not None else None,
            last_seen=r[8].isoformat() if r[8] else None,
            stakes=sorted(stakes_map.get(r[0], [])),
            site=site,
            reg=r[9],
            marker=resolve_marker(markers, r[9], color_tag),
        ))

    return PlayerListResponse(
        players=players,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# Allowed sort columns
_LIST_SORTS = {
    "hands": "hands",
    "vpip": "vpip_pct",
    "pfr": "pfr_pct",
    "three_bet": "three_bet_pct",
    "af": "af",
    "last_seen": "last_seen",
    "username": "p.username",
}

# (page rows, total, stakes per listed player) per list request, until the hand data changes.
# Colour tags, sites and markers are not in it (they change without a data bump).
_LIST_CACHE = ResultCache("players.list", capacity=64)


def _player_list_rows(db, workspace_id: int, search: str | None, types: list[str],
                      min_hands: int, sort_key: str, direction: str, page: int,
                      per_page: int) -> tuple[list, int, dict[int, list[str]]]:
    """One page of the players list: group hand_players per player first (only the
    workspace's rows, the search and type filters as semi-joins on the small tables), keep
    the players with min_hands, then join the names and classifications to the survivors.
    The total comes from the same query (COUNT(*) OVER ())."""
    cond = ["hp.workspace_id = ?"]
    params: list = [workspace_id]
    if search:
        cond.append("hp.player_id IN (SELECT id FROM players WHERE username ILIKE ?)")
        params.append(f"%{search.strip()}%")
    if types:
        ph = ",".join("?" for _ in types)
        cond.append("hp.player_id IN (SELECT player_id FROM player_classifications "
                    f"WHERE workspace_id = ? AND player_type IN ({ph}))")
        params += [workspace_id, *types]

    offset = (page - 1) * per_page
    sql = f"""
        WITH agg AS (
            SELECT hp.player_id,
                COUNT(*) as hands,
                SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as vpip_pct,
                SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pfr_pct,
                CASE WHEN SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) > 0
                    THEN SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) * 100.0
                         / SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END)
                    ELSE NULL END as three_bet_pct,
                CASE WHEN SUM(COALESCE(hp.flop_calls, 0) + COALESCE(hp.turn_calls, 0) + COALESCE(hp.river_calls, 0)) > 0
                    THEN CAST(
                        SUM(COALESCE(hp.flop_bets, 0) + COALESCE(hp.flop_raises, 0)
                          + COALESCE(hp.turn_bets, 0) + COALESCE(hp.turn_raises, 0)
                          + COALESCE(hp.river_bets, 0) + COALESCE(hp.river_raises, 0)) AS DOUBLE)
                         / SUM(COALESCE(hp.flop_calls, 0) + COALESCE(hp.turn_calls, 0) + COALESCE(hp.river_calls, 0))
                    ELSE NULL END as af
            FROM hand_players hp
            WHERE {" AND ".join(cond)}
            GROUP BY hp.player_id
            HAVING COUNT(*) >= ?
        )
        SELECT
            p.id,
            p.username,
            COALESCE(pc.player_type, 'UNK'),
            a.hands, a.vpip_pct, a.pfr_pct, a.three_bet_pct, a.af,
            p.last_seen as last_seen,
            pc.is_reg,
            COUNT(*) OVER () AS total
        FROM agg a
        JOIN players p ON p.id = a.player_id
        LEFT JOIN player_classifications pc ON pc.player_id = a.player_id AND pc.workspace_id = ?
        ORDER BY {_LIST_SORTS[sort_key]} {direction} NULLS LAST, p.id
        LIMIT ? OFFSET ?
    """
    rows = db.execute(sql, params + [min_hands, workspace_id, per_page, offset]).fetchall()
    if rows:
        total = int(rows[0][10])
    else:
        total = db.execute(
            f"SELECT COUNT(*) FROM (SELECT hp.player_id FROM hand_players hp "
            f"WHERE {' AND '.join(cond)} AND hp.player_id IN (SELECT id FROM players) "
            f"GROUP BY hp.player_id HAVING COUNT(*) >= ?)",
            params + [min_hands],
        ).fetchone()[0]
    rows = [r[:10] for r in rows]

    stakes_map: dict[int, list[str]] = {}
    if rows:
        player_ids = [r[0] for r in rows]
        ph = ",".join("?" for _ in player_ids)
        for pid, stk in db.execute(f"""
            SELECT hp.player_id, h.stakes
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE hp.player_id IN ({ph}) AND h.workspace_id = ?
            GROUP BY hp.player_id, h.stakes
        """, player_ids + [workspace_id]).fetchall():
            stakes_map.setdefault(pid, []).append(stk)
    return rows, total, stakes_map


# ── Player header ───────────────────────────────────────────────────

class PlayerHeader(BaseModel):
    id: int
    username: str
    player_type: str = "UNK"
    hands: int = 0
    first_seen: str | None = None
    last_seen: str | None = None
    stakes: list[str] = []
    notes: str | None = None
    color_tag: str | None = None
    reg: bool | None = None
    marker: PlayerMarker | None = None


@router.get("/players/{player_id}", response_model=PlayerHeader)
def get_player(player_id: int, workspace_id: int = Query(1)):
    db = get_read_cursor()

    row = db.execute(
        "SELECT p.id, p.username, COALESCE(pc.player_type, 'UNK'), "
        "p.notes, p.color_tag, p.first_seen, p.last_seen, pc.is_reg "
        "FROM players p "
        "LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = ? "
        "WHERE p.id = ?",
        [workspace_id, player_id],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")

    hands = db.execute(
        "SELECT COUNT(*) FROM hand_players hp "
        "JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id "
        "WHERE hp.player_id = ? AND h.workspace_id = ?",
        [player_id, workspace_id],
    ).fetchone()[0]

    stakes_rows = db.execute("""
        SELECT DISTINCT h.stakes
        FROM hand_players hp JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE hp.player_id = ? AND h.workspace_id = ?
        ORDER BY h.stakes
    """, [player_id, workspace_id]).fetchall()

    return PlayerHeader(
        id=row[0],
        username=row[1],
        player_type=row[2] or "UNK",
        hands=hands,
        first_seen=row[5].isoformat() if row[5] else None,
        last_seen=row[6].isoformat() if row[6] else None,
        stakes=[s[0] for s in stakes_rows],
        notes=row[3],
        color_tag=row[4],
        reg=row[7],
        marker=resolve_marker(get_markers(db), row[7], row[4]),
    )


# ── Player notes/color ─────────────────────────────────────────────

class PlayerNotesBody(BaseModel):
    notes: str | None = None
    color_tag: str | None = None


@router.patch("/players/{player_id}/notes")
def update_player_notes(player_id: int, body: PlayerNotesBody):
    with db_lock():
        db = get_db()
        if not db.execute("SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
            raise HTTPException(status_code=404, detail="Player not found")

        if body.color_tag is not None and body.color_tag.strip() != "":
            from app import config_sections as cs
            if body.color_tag.strip() not in {str(m["id"]) for m in cs.get_markers(db)}:
                raise HTTPException(status_code=422, detail="color_tag must be empty or a colour marker id")

        updates = []
        params = []
        if body.notes is not None:
            updates.append("notes = ?")
            params.append(body.notes)
        if body.color_tag is not None:
            updates.append("color_tag = ?")
            params.append(body.color_tag.strip())

        if updates:
            params.append(player_id)
            db.execute(
                f"UPDATE players SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        return {"status": "ok"}


# ── Player stats ────────────────────────────────────────────────────

@router.get("/players/{player_id}/stats", response_model=HeroStats)
def get_player_stats(
    player_id: int,
    position: Optional[str] = None,
    stakes: Optional[str] = None,
    game_mode: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    if not db.execute("SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    return compute_player_stats(
        db, player_id,
        position=position, stakes=stakes, game_mode=game_mode,
        date_from=date_from, date_to=date_to,
        workspace_id=workspace_id,
    )


# ── Head-to-head ────────────────────────────────────────────────────

# Preflop action order (first to act → BB), derived from the full-ring seat list
# so every position label any table size can produce has a rank.
_FULL_RING = POSITIONS_BY_COUNT[max(POSITIONS_BY_COUNT)]
_BB_IDX = _FULL_RING.index("BB")
# dict.fromkeys dedupes repeated labels (EP EP MP MP at full ring), keeping order
_ACTION_RANK = {
    pos: i for i, pos in enumerate(dict.fromkeys(_FULL_RING[_BB_IDX + 1:] + _FULL_RING[:_BB_IDX + 1]))
}


def _action_order_key(position: str | None) -> tuple[int, str]:
    return (_ACTION_RANK.get(position or "", len(_ACTION_RANK)), position or "")


class HeadToHeadRow(BaseModel):
    hero_position: str
    hands: int
    hero_won_bb: float
    bb_per_100: float


class HeadToHeadResponse(BaseModel):
    rows: list[HeadToHeadRow]
    total_hands: int
    total_won_bb: float
    overall_bb_per_100: float


@router.get("/players/{player_id}/head-to-head", response_model=HeadToHeadResponse)
def get_head_to_head(player_id: int, workspace_id: int = Query(1)):
    db = get_read_cursor()
    hero_id = get_hero_player_id(db, workspace_id)
    if hero_id is None:
        return HeadToHeadResponse(rows=[], total_hands=0, total_won_bb=0, overall_bb_per_100=0)

    # Find hands where both hero and this player were present
    rows = db.execute("""
        SELECT
            hero.position as hero_position,
            COUNT(*) as hands,
            SUM(CAST(COALESCE(hero.won_bb, 0) AS DOUBLE)) as hero_won_bb
        FROM hand_players hero
        JOIN hand_players opp ON opp.hand_id = hero.hand_id AND opp.workspace_id = hero.workspace_id AND opp.player_id = ?
        JOIN hands h ON hero.hand_id = h.id AND hero.workspace_id = h.workspace_id
        WHERE hero.player_id = ? AND h.workspace_id = ?
        GROUP BY hero.position
    """, [player_id, hero_id, workspace_id]).fetchall()
    rows.sort(key=lambda r: _action_order_key(r[0]))

    if not rows:
        return HeadToHeadResponse(rows=[], total_hands=0, total_won_bb=0, overall_bb_per_100=0)

    result_rows = []
    total_hands = 0
    total_won_bb = 0.0
    for r in rows:
        h = int(r[1])
        w = float(r[2])
        total_hands += h
        total_won_bb += w
        result_rows.append(HeadToHeadRow(
            hero_position=r[0],
            hands=h,
            hero_won_bb=round(w, 2),
            bb_per_100=round(w / h * 100, 2) if h > 0 else 0,
        ))

    return HeadToHeadResponse(
        rows=result_rows,
        total_hands=total_hands,
        total_won_bb=round(total_won_bb, 2),
        overall_bb_per_100=round(total_won_bb / total_hands * 100, 2) if total_hands > 0 else 0,
    )
