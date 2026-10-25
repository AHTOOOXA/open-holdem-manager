import json

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from app.date_filters import DATE_TO_SQL
from app.db import get_read_cursor, get_hero_player_id
from app.models import HeroStats
from app.stats_engine import ResultCache, _compute_stats_from_query, agg_sql

router = APIRouter()

# Overview rows by (SQL, params); full-stats go through the stats engine's cache.
_OVERVIEW_CACHE = ResultCache("population.overview", capacity=32)


def _resolve_excluded_player_ids(
    db,
    workspace_id: int,
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
) -> list[int]:
    """Resolve identity IDs and tags to a list of player_ids to exclude."""
    identity_ids: set[int] = set()

    if exclude_identity_ids:
        for s in exclude_identity_ids.split(","):
            s = s.strip()
            if s.isdigit():
                identity_ids.add(int(s))

    if exclude_tags:
        tag_list = [t.strip() for t in exclude_tags.split(",") if t.strip()]
        if tag_list:
            rows = db.execute(
                "SELECT id, tags FROM player_identities"
            ).fetchall()
            for row in rows:
                try:
                    row_tags = json.loads(row[1]) if row[1] else []
                except (json.JSONDecodeError, TypeError):
                    row_tags = []
                if any(t in row_tags for t in tag_list):
                    identity_ids.add(row[0])

    if not identity_ids:
        return []

    ph = ",".join("?" for _ in identity_ids)
    alias_rows = db.execute(
        f"SELECT player_id FROM player_aliases "
        f"WHERE identity_id IN ({ph}) AND workspace_id = ?",
        list(identity_ids) + [workspace_id],
    ).fetchall()

    return [r[0] for r in alias_rows]


def _build_where(
    stakes: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    min_hands: int,
    exclude_hero: bool,
    player_type: Optional[str],
    db,
    workspace_id: int = 1,
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
) -> tuple[str, list, str]:
    """Build WHERE clause for population queries.

    Returns (where_sql, params, having_sql).
    """
    clauses = ["h.workspace_id = ?"]
    params: list = [workspace_id]

    if stakes:
        stakes_list = [s.strip() for s in stakes.split(",") if s.strip()]
        if stakes_list:
            ph = ",".join("?" for _ in stakes_list)
            clauses.append(f"h.stakes IN ({ph})")
            params.extend(stakes_list)

    if date_from:
        clauses.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        clauses.append(DATE_TO_SQL)
        params.append(date_to)

    if exclude_hero:
        hero_id = get_hero_player_id(db, workspace_id)
        if hero_id:
            clauses.append("hp.player_id != ?")
            params.append(hero_id)

    # Exclude players by identity IDs or tags
    excluded_pids = _resolve_excluded_player_ids(
        db, workspace_id, exclude_identity_ids, exclude_tags,
    )
    if excluded_pids:
        ph = ",".join("?" for _ in excluded_pids)
        clauses.append(f"hp.player_id NOT IN ({ph})")
        params.extend(excluded_pids)

    if player_type:
        types = [t.strip().upper() for t in player_type.split(",") if t.strip()]
        if types:
            ph = ",".join("?" for _ in types)
            clauses.append(f"pc.player_type IN ({ph})")
            params.extend(types)

    where_sql = " AND " + " AND ".join(clauses)
    having_sql = f"HAVING COUNT(*) >= {int(min_hands)}" if min_hands > 0 else ""

    return where_sql, params, having_sql


# ── Overview ────────────────────────────────────────────────────────

class PopulationOverview(BaseModel):
    player_count: int
    observation_count: int
    date_min: str | None = None
    date_max: str | None = None


@router.get("/population/overview", response_model=PopulationOverview)
def population_overview(
    stakes: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_hands: int = Query(20, ge=0),
    exclude_hero: bool = Query(True),
    player_type: Optional[str] = None,
    workspace_id: int = Query(1),
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
):
    db = get_read_cursor()
    where_sql, params, having_sql = _build_where(stakes, date_from, date_to, min_hands, exclude_hero, player_type, db, workspace_id, exclude_identity_ids, exclude_tags)

    if min_hands <= 1 and not player_type_filter(player_type):
        # Every player with a matching row is counted: one aggregate instead of a group per
        # player (the players join drops nothing: hand_players.player_id is a foreign key,
        # and player_classifications has one row per (player, workspace)).
        sql = f"""
            SELECT COUNT(DISTINCT hp.player_id), COUNT(*), MIN(h.played_at), MAX(h.played_at)
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE hp.player_id IS NOT NULL {where_sql}
        """
    else:
        sql = f"""
        SELECT COUNT(*), SUM(hands), MIN(min_t), MAX(max_t) FROM (
            SELECT hp.player_id, COUNT(*) as hands,
                   MIN(h.played_at) as min_t, MAX(h.played_at) as max_t
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        ) sub
    """
    row = _OVERVIEW_CACHE.get_or_compute(
        db, (sql, tuple(params)), lambda: db.execute(sql, params).fetchone(), heavy=True)

    pc = row[0] if row else 0
    oc = row[1] if row and row[1] else 0

    return PopulationOverview(
        player_count=pc,
        observation_count=oc,
        date_min=row[2].isoformat() if row and row[2] else None,
        date_max=row[3].isoformat() if row and row[3] else None,
    )


# ── Full Stats (HeroStats-shaped) ──────────────────────────────────


@router.get("/population/full-stats", response_model=HeroStats)
def population_full_stats(
    stakes: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_hands: int = Query(20, ge=0),
    exclude_hero: bool = Query(True),
    player_type: Optional[str] = None,
    workspace_id: int = Query(1),
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
):
    db = get_read_cursor()
    where_sql, params, having_sql = _build_where(
        stakes, date_from, date_to, min_hands, exclude_hero,
        player_type, db, workspace_id, exclude_identity_ids, exclude_tags,
    )

    # _AGG_SQL doesn't join player_classifications, so the main WHERE gets the
    # filters without player_type. The CTE restricts players by type and min_hands.
    main_filter_sql, main_params, _ = _build_where(
        stakes, date_from, date_to, min_hands, exclude_hero,
        None, db, workspace_id, exclude_identity_ids, exclude_tags,
    )
    main_where = f"1=1 {main_filter_sql}"
    if min_hands <= 1 and not player_type_filter(player_type):
        # The CTE would keep every player that has a row under the same filters: skip it.
        # (Its players join and the IN drop only rows without a player.)
        return _compute_stats_from_query(
            db, main_where + " AND hp.player_id IS NOT NULL", main_params, heavy=True)

    # Build eligible-players CTE, then run standard _AGG_SQL
    eligible_cte = f"""WITH eligible AS (
        SELECT hp.player_id
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN players p ON p.id = hp.player_id
        LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
        WHERE 1=1 {where_sql}
        GROUP BY hp.player_id
        {having_sql}
    )
    """
    main_where += " AND hp.player_id IN (SELECT player_id FROM eligible)"
    full_sql = eligible_cte + agg_sql(main_where)
    all_params = params + main_params

    return _compute_stats_from_query(db, main_where, all_params, sql_override=full_sql, heavy=True)


def player_type_filter(player_type: Optional[str]) -> list[str]:
    """The player types a `player_type` param filters on (empty = no filter), as _build_where."""
    if not player_type:
        return []
    return [t.strip().upper() for t in player_type.split(",") if t.strip()]
