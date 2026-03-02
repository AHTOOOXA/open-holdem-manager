import json

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from app.db import get_read_cursor, get_hero_player_id
from app.models import HeroStats
from app.stats_engine import _AGG_SQL, _compute_stats_from_query

router = APIRouter()

POSITIONS = ["EP", "MP", "CO", "BTN", "SB", "BB"]


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
        clauses.append("h.played_at <= ?")
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

    row = db.execute(f"""
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
    """, params).fetchone()

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

    main_where = f"1=1 {where_sql} AND hp.player_id IN (SELECT player_id FROM eligible)"
    full_sql = eligible_cte + _AGG_SQL.format(where=main_where)
    # params used twice: once for CTE, once for main WHERE
    all_params = params + params

    return _compute_stats_from_query(db, main_where, all_params, sql_override=full_sql)


# ── Preflop ─────────────────────────────────────────────────────────

class PositionStat(BaseModel):
    position: str
    value: float | None = None
    sample: int = 0


class MatrixCell(BaseModel):
    opener: str
    responder: str
    value: float | None = None
    sample: int = 0


class PreflopResponse(BaseModel):
    open_raise: list[PositionStat]
    three_bet_matrix: list[MatrixCell]
    fold_to_3bet_matrix: list[MatrixCell]
    vpip_by_position: list[PositionStat]
    pfr_by_position: list[PositionStat]
    limp_by_position: list[PositionStat]
    squeeze: PositionStat | None = None
    four_bet: list[PositionStat] = []


@router.get("/population/preflop", response_model=PreflopResponse)
def population_preflop(
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

    # Aggregate stats by position for eligible players (single-pass CTE)
    rows = db.execute(f"""
        WITH eligible AS (
            SELECT hp.player_id
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        )
        SELECT
            hp.position,
            COUNT(*) as hands,
            SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) as vpip_count,
            SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) as pfr_count,
            SUM(CASE WHEN hp.open_raise THEN 1 ELSE 0 END) as or_count,
            SUM(CASE WHEN hp.open_raise_opp THEN 1 ELSE 0 END) as or_opp,
            SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) as tb_count,
            SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) as tb_opp,
            SUM(CASE WHEN hp.fold_to_3bet IS NOT NULL THEN 1 ELSE 0 END) as ft3b_opp,
            SUM(CASE WHEN hp.fold_to_3bet THEN 1 ELSE 0 END) as ft3b_count,
            SUM(CASE WHEN hp.limp THEN 1 ELSE 0 END) as limp_count,
            SUM(CASE WHEN hp.four_bet THEN 1 ELSE 0 END) as fb_count,
            SUM(CASE WHEN hp.four_bet_opp THEN 1 ELSE 0 END) as fb_opp,
            SUM(CASE WHEN hp.squeeze THEN 1 ELSE 0 END) as sq_count,
            SUM(CASE WHEN hp.squeeze_opp THEN 1 ELSE 0 END) as sq_opp
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE hp.position IN ('EP','MP','CO','BTN','SB','BB')
          AND h.workspace_id = ?
        GROUP BY hp.position
    """, params + [workspace_id]).fetchall()

    # Build position maps
    pos_data: dict[str, dict] = {}
    for r in rows:
        pos_data[r[0]] = {
            "hands": r[1], "vpip": r[2], "pfr": r[3],
            "or_count": r[4], "or_opp": r[5],
            "tb_count": r[6], "tb_opp": r[7],
            "ft3b_opp": r[8], "ft3b_count": r[9],
            "limp": r[10],
            "fb_count": r[11], "fb_opp": r[12],
            "sq_count": r[13], "sq_opp": r[14],
        }

    def _pct(count, opp):
        if opp and opp > 0:
            return round(float(count) / float(opp) * 100, 1)
        return None

    def _pos_stat(key, opp_key=None) -> list[PositionStat]:
        result = []
        for pos in POSITIONS:
            d = pos_data.get(pos, {})
            c = d.get(key, 0)
            o = d.get(opp_key, d.get("hands", 0)) if opp_key else d.get("hands", 0)
            result.append(PositionStat(position=pos, value=_pct(c, o), sample=int(o or 0)))
        return result

    # 3-bet matrix (simplified: just by responder position since opener position would need join)
    # For full opener x responder matrix, we'd need the opening position stored
    # Simplification: 3-bet % by position (responder position)

    # Squeeze totals
    total_sq = sum(d.get("sq_count", 0) for d in pos_data.values())
    total_sq_opp = sum(d.get("sq_opp", 0) for d in pos_data.values())
    squeeze_stat = PositionStat(
        position="Total",
        value=_pct(total_sq, total_sq_opp),
        sample=int(total_sq_opp),
    )

    return PreflopResponse(
        open_raise=_pos_stat("or_count", "or_opp"),
        three_bet_matrix=[],  # Full matrix requires more complex query; using by-position for now
        fold_to_3bet_matrix=[],
        vpip_by_position=_pos_stat("vpip"),
        pfr_by_position=_pos_stat("pfr"),
        limp_by_position=_pos_stat("limp"),
        squeeze=squeeze_stat,
        four_bet=_pos_stat("fb_count", "fb_opp"),
    )


# ── Segments ────────────────────────────────────────────────────────

class SegmentStats(BaseModel):
    player_type: str
    count: int
    avg_hands: float
    vpip: float | None = None
    pfr: float | None = None
    three_bet: float | None = None
    af: float | None = None
    wtsd: float | None = None
    wwsf: float | None = None


class SegmentsResponse(BaseModel):
    segments: list[SegmentStats]


@router.get("/population/segments", response_model=SegmentsResponse)
def population_segments(
    stakes: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_hands: int = Query(20, ge=0),
    exclude_hero: bool = Query(True),
    workspace_id: int = Query(1),
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
):
    db = get_read_cursor()
    where_sql, params, having_sql = _build_where(stakes, date_from, date_to, min_hands, exclude_hero, None, db, workspace_id, exclude_identity_ids, exclude_tags)

    rows = db.execute(f"""
        WITH player_agg AS (
            SELECT
                hp.player_id,
                COALESCE(pc.player_type, 'UNK') as player_type,
                COUNT(*) as hands,
                SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) as vpip_count,
                SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) as pfr_count,
                SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) as tb_count,
                SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) as tb_opp,
                SUM(COALESCE(hp.flop_bets,0) + COALESCE(hp.flop_raises,0)
                  + COALESCE(hp.turn_bets,0) + COALESCE(hp.turn_raises,0)
                  + COALESCE(hp.river_bets,0) + COALESCE(hp.river_raises,0)) as agg_count,
                SUM(COALESCE(hp.flop_calls,0) + COALESCE(hp.turn_calls,0) + COALESCE(hp.river_calls,0)) as call_count,
                SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as sd_count,
                SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as sf_count,
                SUM(CASE WHEN hp.saw_flop AND CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) > 0 THEN 1 ELSE 0 END) as wwsf_count
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id, COALESCE(pc.player_type, 'UNK')
            {having_sql}
        )
        SELECT
            player_type,
            COUNT(*) as player_count,
            SUM(hands) as total_hands,
            SUM(vpip_count) as vpip_count,
            SUM(pfr_count) as pfr_count,
            SUM(tb_count) as tb_count,
            SUM(tb_opp) as tb_opp,
            SUM(agg_count) as agg_count,
            SUM(call_count) as call_count,
            SUM(sd_count) as sd_count,
            SUM(sf_count) as sf_count,
            SUM(wwsf_count) as wwsf_count
        FROM player_agg
        GROUP BY player_type
        ORDER BY total_hands DESC
    """, params).fetchall()

    segments = []
    for r in rows:
        ptype, pcount, total, vpip_c, pfr_c, tb_c, tb_o, agg_c, call_c, sd_c, sf_c, wwsf_c = r
        if pcount == 0:
            continue

        def pct(c, o):
            return round(float(c) / float(o) * 100, 1) if o and o > 0 else None

        segments.append(SegmentStats(
            player_type=ptype or "UNK",
            count=pcount,
            avg_hands=round(total / pcount, 0),
            vpip=pct(vpip_c, total),
            pfr=pct(pfr_c, total),
            three_bet=pct(tb_c, tb_o),
            af=round(float(agg_c) / float(call_c), 2) if call_c and call_c > 0 else None,
            wtsd=pct(sd_c, sf_c),
            wwsf=pct(wwsf_c, sf_c),
        ))

    return SegmentsResponse(segments=segments)


# ── Postflop ────────────────────────────────────────────────────────

class PostflopLineStat(BaseModel):
    street: str
    stat: str
    pot_type: str = "all"
    value: float | None = None
    sample: int = 0


class PostflopResponse(BaseModel):
    lines: list[PostflopLineStat]


@router.get("/population/postflop", response_model=PostflopResponse)
def population_postflop(
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

    rows = db.execute(f"""
        WITH eligible AS (
            SELECT hp.player_id
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        )
        SELECT
            -- Flop cbet
            SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) as cb_flop_opp,
            SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) as cb_flop,
            -- Fold to flop cbet
            SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL THEN 1 ELSE 0 END) as ftcb_flop_opp,
            SUM(CASE WHEN hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as ftcb_flop,
            -- Turn cbet
            SUM(CASE WHEN hp.cbet_turn_opp THEN 1 ELSE 0 END) as cb_turn_opp,
            SUM(CASE WHEN hp.cbet_turn THEN 1 ELSE 0 END) as cb_turn,
            -- Fold to turn cbet
            SUM(CASE WHEN hp.fold_to_cbet_turn IS NOT NULL THEN 1 ELSE 0 END) as ftcb_turn_opp,
            SUM(CASE WHEN hp.fold_to_cbet_turn THEN 1 ELSE 0 END) as ftcb_turn,
            -- Donk bet flop
            SUM(CASE WHEN hp.donk_bet_flop_opp THEN 1 ELSE 0 END) as donk_opp,
            SUM(CASE WHEN hp.donk_bet_flop THEN 1 ELSE 0 END) as donk_count,
            -- Showdown stats
            SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as saw_flop,
            SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as went_sd,
            SUM(CASE WHEN hp.went_to_showdown AND hp.won_at_showdown THEN 1 ELSE 0 END) as won_sd,
            SUM(CASE WHEN hp.saw_flop AND CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) > 0 THEN 1 ELSE 0 END) as wwsf
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE h.workspace_id = ?
    """, params + [workspace_id]).fetchone()

    if not rows:
        return PostflopResponse(lines=[])

    def _line(street: str, stat: str, count, opp) -> PostflopLineStat:
        c = int(count or 0)
        o = int(opp or 0)
        return PostflopLineStat(
            street=street, stat=stat,
            value=round(c / o * 100, 1) if o > 0 else None,
            sample=o,
        )

    lines = [
        _line("flop", "cbet", rows[1], rows[0]),
        _line("flop", "fold_to_cbet", rows[3], rows[2]),
        _line("turn", "cbet", rows[5], rows[4]),
        _line("turn", "fold_to_cbet", rows[7], rows[6]),
        _line("flop", "donk_bet", rows[9], rows[8]),
        _line("all", "wtsd", rows[11], rows[10]),
        _line("all", "wsd", rows[12], rows[11]),
        _line("all", "wwsf", rows[13], rows[10]),
    ]

    return PostflopResponse(lines=lines)


# ── Pot Types ───────────────────────────────────────────────────────

class PotTypeStat(BaseModel):
    pot_type: str
    hands: int
    cbet_flop: float | None = None
    fold_to_cbet_flop: float | None = None
    wtsd: float | None = None


class PotTypesResponse(BaseModel):
    pot_types: list[PotTypeStat]


@router.get("/population/pot-types", response_model=PotTypesResponse)
def population_pot_types(
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

    rows = db.execute(f"""
        WITH eligible AS (
            SELECT hp.player_id
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        )
        SELECT
            COALESCE(hp.pot_type, 'SRP') as pt,
            COUNT(*) as hands,
            SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) as cb_opp,
            SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) as cb,
            SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL THEN 1 ELSE 0 END) as ftcb_opp,
            SUM(CASE WHEN hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as ftcb,
            SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as sf,
            SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as sd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE h.workspace_id = ?
        GROUP BY COALESCE(hp.pot_type, 'SRP')
        ORDER BY hands DESC
    """, params + [workspace_id]).fetchall()

    def pct(c, o):
        return round(float(c) / float(o) * 100, 1) if o and o > 0 else None

    return PotTypesResponse(pot_types=[
        PotTypeStat(
            pot_type=r[0], hands=r[1],
            cbet_flop=pct(r[3], r[2]),
            fold_to_cbet_flop=pct(r[5], r[4]),
            wtsd=pct(r[7], r[6]),
        ) for r in rows
    ])


# ── Showdown ────────────────────────────────────────────────────────

class ShowdownPositionStat(BaseModel):
    position: str
    wtsd: float | None = None
    wsd: float | None = None
    wwsf: float | None = None
    sample: int = 0


class ShowdownResponse(BaseModel):
    by_position: list[ShowdownPositionStat]
    af_flop: float | None = None
    af_turn: float | None = None
    af_river: float | None = None
    afq_flop: float | None = None
    afq_turn: float | None = None
    afq_river: float | None = None


@router.get("/population/showdown", response_model=ShowdownResponse)
def population_showdown(
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

    eligible_cte = f"""
        WITH eligible AS (
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

    pos_rows = db.execute(f"""
        {eligible_cte}
        SELECT
            hp.position,
            SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as sf,
            SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as sd,
            SUM(CASE WHEN hp.went_to_showdown AND hp.won_at_showdown THEN 1 ELSE 0 END) as wsd,
            SUM(CASE WHEN hp.saw_flop AND CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) > 0 THEN 1 ELSE 0 END) as wwsf
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE hp.position IN ('EP','MP','CO','BTN','SB','BB')
          AND h.workspace_id = ?
        GROUP BY hp.position
    """, params + [workspace_id]).fetchall()

    def pct(c, o):
        return round(float(c) / float(o) * 100, 1) if o and o > 0 else None

    by_pos = []
    for r in pos_rows:
        by_pos.append(ShowdownPositionStat(
            position=r[0],
            wtsd=pct(r[2], r[1]),
            wsd=pct(r[3], r[2]),
            wwsf=pct(r[4], r[1]),
            sample=int(r[1]),
        ))

    # Aggression overall
    agg = db.execute(f"""
        {eligible_cte}
        SELECT
            SUM(COALESCE(hp.flop_bets, 0) + COALESCE(hp.flop_raises, 0)) as f_agg,
            SUM(COALESCE(hp.flop_calls, 0)) as f_call,
            SUM(COALESCE(hp.turn_bets, 0) + COALESCE(hp.turn_raises, 0)) as t_agg,
            SUM(COALESCE(hp.turn_calls, 0)) as t_call,
            SUM(COALESCE(hp.river_bets, 0) + COALESCE(hp.river_raises, 0)) as r_agg,
            SUM(COALESCE(hp.river_calls, 0)) as r_call,
            SUM(COALESCE(hp.flop_bets, 0) + COALESCE(hp.flop_raises, 0)
              + COALESCE(hp.flop_calls, 0) + COALESCE(hp.flop_checks, 0) + COALESCE(hp.flop_folds, 0)) as f_total,
            SUM(COALESCE(hp.turn_bets, 0) + COALESCE(hp.turn_raises, 0)
              + COALESCE(hp.turn_calls, 0) + COALESCE(hp.turn_checks, 0) + COALESCE(hp.turn_folds, 0)) as t_total,
            SUM(COALESCE(hp.river_bets, 0) + COALESCE(hp.river_raises, 0)
              + COALESCE(hp.river_calls, 0) + COALESCE(hp.river_checks, 0) + COALESCE(hp.river_folds, 0)) as r_total
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE h.workspace_id = ?
    """, params + [workspace_id]).fetchone()

    af_f = round(float(agg[0]) / float(agg[1]), 2) if agg and agg[1] and agg[1] > 0 else None
    af_t = round(float(agg[2]) / float(agg[3]), 2) if agg and agg[3] and agg[3] > 0 else None
    af_r = round(float(agg[4]) / float(agg[5]), 2) if agg and agg[5] and agg[5] > 0 else None
    afq_f = pct(agg[0], agg[6]) if agg else None
    afq_t = pct(agg[2], agg[7]) if agg else None
    afq_r = pct(agg[4], agg[8]) if agg else None

    return ShowdownResponse(
        by_position=by_pos,
        af_flop=af_f, af_turn=af_t, af_river=af_r,
        afq_flop=afq_f, afq_turn=afq_t, afq_river=afq_r,
    )


# ── HU vs Multiway ─────────────────────────────────────────────────

class HuMwStat(BaseModel):
    category: str
    hands: int
    vpip: float | None = None
    pfr: float | None = None
    cbet_flop: float | None = None
    fold_to_cbet_flop: float | None = None
    wtsd: float | None = None


class HuMwResponse(BaseModel):
    stats: list[HuMwStat]


@router.get("/population/hu-vs-mw", response_model=HuMwResponse)
def population_hu_vs_mw(
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

    rows = db.execute(f"""
        WITH eligible AS (
            SELECT hp.player_id
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        )
        SELECT
            CASE WHEN COALESCE(hp.is_multiway, false) THEN 'Multiway' ELSE 'Heads-Up' END as cat,
            COUNT(*) as hands,
            SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) as vpip_c,
            SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) as pfr_c,
            SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) as cb_opp,
            SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) as cb,
            SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL THEN 1 ELSE 0 END) as ftcb_opp,
            SUM(CASE WHEN hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as ftcb,
            SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as sf,
            SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as sd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE hp.saw_flop = true
          AND h.workspace_id = ?
        GROUP BY CASE WHEN COALESCE(hp.is_multiway, false) THEN 'Multiway' ELSE 'Heads-Up' END
    """, params + [workspace_id]).fetchall()

    def pct(c, o):
        return round(float(c) / float(o) * 100, 1) if o and o > 0 else None

    return HuMwResponse(stats=[
        HuMwStat(
            category=r[0], hands=r[1],
            vpip=pct(r[2], r[1]),
            pfr=pct(r[3], r[1]),
            cbet_flop=pct(r[5], r[4]),
            fold_to_cbet_flop=pct(r[7], r[6]),
            wtsd=pct(r[9], r[8]),
        ) for r in rows
    ])


# ── Comparison (hero vs pop) ────────────────────────────────────────

class ComparisonStat(BaseModel):
    stat: str
    hero_value: float | None = None
    pop_value: float | None = None
    diff: float | None = None


class ComparisonResponse(BaseModel):
    stats: list[ComparisonStat]


@router.get("/population/comparison", response_model=ComparisonResponse)
def population_comparison(
    stakes: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_hands: int = Query(20, ge=0),
    workspace_id: int = Query(1),
    exclude_identity_ids: Optional[str] = None,
    exclude_tags: Optional[str] = None,
):
    db = get_read_cursor()
    hero_id = get_hero_player_id(db, workspace_id)

    # Get population averages (excluding hero)
    where_sql, params, having_sql = _build_where(stakes, date_from, date_to, min_hands, True, None, db, workspace_id, exclude_identity_ids, exclude_tags)

    pop = db.execute(f"""
        WITH eligible AS (
            SELECT hp.player_id
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            JOIN players p ON p.id = hp.player_id
            LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = h.workspace_id
            WHERE 1=1 {where_sql}
            GROUP BY hp.player_id
            {having_sql}
        )
        SELECT
            COUNT(*) as hands,
            SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as vpip,
            SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pfr,
            CASE WHEN SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END)
                ELSE NULL END as three_bet,
            CASE WHEN SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END)
                ELSE NULL END as cbet_flop,
            CASE WHEN SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) > 0
                THEN SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END)
                ELSE NULL END as wtsd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN eligible e ON e.player_id = hp.player_id
        WHERE h.workspace_id = ?
    """, params + [workspace_id]).fetchone()

    # Get hero stats
    hero = None
    if hero_id:
        hero_where = "hp.player_id = ? AND h.workspace_id = ?"
        hero_params: list = [hero_id, workspace_id]
        if stakes:
            stakes_list = [s.strip() for s in stakes.split(",") if s.strip()]
            if stakes_list:
                ph = ",".join("?" for _ in stakes_list)
                hero_where += f" AND h.stakes IN ({ph})"
                hero_params.extend(stakes_list)
        if date_from:
            hero_where += " AND h.played_at >= ?"
            hero_params.append(date_from)
        if date_to:
            hero_where += " AND h.played_at <= ?"
            hero_params.append(date_to)

        hero = db.execute(f"""
            SELECT
                COUNT(*) as hands,
                SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as vpip,
                SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pfr,
                CASE WHEN SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) > 0
                    THEN SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END)
                    ELSE NULL END as three_bet,
                CASE WHEN SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) > 0
                    THEN SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END)
                    ELSE NULL END as cbet_flop,
                CASE WHEN SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) > 0
                    THEN SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) * 100.0 / SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END)
                    ELSE NULL END as wtsd
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE {hero_where}
        """, hero_params).fetchone()

    stat_names = ["VPIP", "PFR", "3-Bet", "C-Bet Flop", "WTSD"]
    stats = []

    for i, name in enumerate(stat_names):
        idx = i + 1  # skip hands column
        pop_val = round(float(pop[idx]), 1) if pop and pop[idx] is not None else None
        hero_val = round(float(hero[idx]), 1) if hero and hero[idx] is not None else None
        diff = round(hero_val - pop_val, 1) if hero_val is not None and pop_val is not None else None
        stats.append(ComparisonStat(stat=name, hero_value=hero_val, pop_value=pop_val, diff=diff))

    return ComparisonResponse(stats=stats)
