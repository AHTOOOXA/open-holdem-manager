from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import math

from app.db import get_db, db_lock, get_read_cursor
from app.stats_engine import compute_player_stats
from app.models import HeroStats

router = APIRouter()


# ── Helper ──────────────────────────────────────────────────────────

def _get_hero_player_id(db) -> Optional[int]:
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    if not row:
        return None
    hero_username = row[0]
    row = db.execute(
        "SELECT p.id FROM players p WHERE p.username = ? AND p.site_id = 1",
        [hero_username],
    ).fetchone()
    return row[0] if row else None


# ── Player list ─────────────────────────────────────────────────────

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
):
    db = get_read_cursor()

    where_clauses: list[str] = []
    params: list = []

    if search:
        where_clauses.append("p.username ILIKE ?")
        params.append(f"%{search.strip()}%")

    if player_type:
        types = [t.strip().upper() for t in player_type.split(",") if t.strip()]
        if types:
            ph = ",".join("?" for _ in types)
            where_clauses.append(f"pc.player_type IN ({ph})")
            params.extend(types)

    where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

    # Count total matching players with min_hands filter
    count_sql = f"""
        SELECT COUNT(*) FROM (
            SELECT p.id
            FROM players p
            JOIN hand_players hp ON hp.player_id = p.id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id
            WHERE 1=1 {where_sql}
            GROUP BY p.id
            HAVING COUNT(*) >= ?
        ) t
    """
    count_params = list(params) + [min_hands]
    total = db.execute(count_sql, count_params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))

    # Allowed sort columns
    allowed_sorts = {
        "hands": "hands",
        "vpip": "vpip_pct",
        "pfr": "pfr_pct",
        "three_bet": "three_bet_pct",
        "af": "af",
        "last_seen": "last_seen",
        "username": "p.username",
    }
    sort_col = allowed_sorts.get(sort_by, "hands")
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"

    offset = (page - 1) * per_page
    main_sql = f"""
        SELECT
            p.id,
            p.username,
            COALESCE(pc.player_type, 'UNK'),
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
                ELSE NULL END as af,
            MAX(p.last_seen) as last_seen
        FROM players p
        JOIN hand_players hp ON hp.player_id = p.id
        LEFT JOIN player_classifications pc ON pc.player_id = p.id
        WHERE 1=1 {where_sql}
        GROUP BY p.id, p.username, COALESCE(pc.player_type, 'UNK')
        HAVING COUNT(*) >= ?
        ORDER BY {sort_col} {direction} NULLS LAST
        LIMIT ? OFFSET ?
    """
    main_params = list(params) + [min_hands, per_page, offset]
    rows = db.execute(main_sql, main_params).fetchall()

    if not rows:
        return PlayerListResponse(
            players=[], total=total, page=page,
            per_page=per_page, total_pages=total_pages,
        )

    # Batch fetch stakes per player
    player_ids = [r[0] for r in rows]
    ph = ",".join("?" for _ in player_ids)
    stakes_rows = db.execute(f"""
        SELECT hp.player_id, h.stakes
        FROM hand_players hp
        JOIN hands h ON h.id = hp.hand_id
        WHERE hp.player_id IN ({ph})
        GROUP BY hp.player_id, h.stakes
    """, player_ids).fetchall()

    stakes_map: dict[int, list[str]] = {}
    for pid, stk in stakes_rows:
        stakes_map.setdefault(pid, []).append(stk)

    players = []
    for r in rows:
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
        ))

    return PlayerListResponse(
        players=players,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


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


@router.get("/players/{player_id}", response_model=PlayerHeader)
def get_player(player_id: int):
    db = get_read_cursor()

    row = db.execute(
        "SELECT p.id, p.username, COALESCE(pc.player_type, 'UNK'), "
        "p.notes, p.color_tag, p.first_seen, p.last_seen "
        "FROM players p "
        "LEFT JOIN player_classifications pc ON pc.player_id = p.id "
        "WHERE p.id = ?",
        [player_id],
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")

    hands = db.execute(
        "SELECT COUNT(*) FROM hand_players WHERE player_id = ?",
        [player_id],
    ).fetchone()[0]

    stakes_rows = db.execute("""
        SELECT DISTINCT h.stakes
        FROM hand_players hp JOIN hands h ON h.id = hp.hand_id
        WHERE hp.player_id = ?
        ORDER BY h.stakes
    """, [player_id]).fetchall()

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

        updates = []
        params = []
        if body.notes is not None:
            updates.append("notes = ?")
            params.append(body.notes)
        if body.color_tag is not None:
            updates.append("color_tag = ?")
            params.append(body.color_tag)

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
):
    db = get_read_cursor()
    if not db.execute("SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    return compute_player_stats(
        db, player_id,
        position=position, stakes=stakes, game_mode=game_mode,
        date_from=date_from, date_to=date_to,
    )


# ── Head-to-head ────────────────────────────────────────────────────

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
def get_head_to_head(player_id: int):
    db = get_read_cursor()
    hero_id = _get_hero_player_id(db)
    if hero_id is None:
        return HeadToHeadResponse(rows=[], total_hands=0, total_won_bb=0, overall_bb_per_100=0)

    # Find hands where both hero and this player were present
    rows = db.execute("""
        SELECT
            hero.position as hero_position,
            COUNT(*) as hands,
            SUM(CAST(COALESCE(hero.won_bb, 0) AS DOUBLE)) as hero_won_bb
        FROM hand_players hero
        JOIN hand_players opp ON opp.hand_id = hero.hand_id AND opp.player_id = ?
        WHERE hero.player_id = ?
        GROUP BY hero.position
        ORDER BY hero.position
    """, [player_id, hero_id]).fetchall()

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
