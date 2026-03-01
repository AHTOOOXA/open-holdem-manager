from fastapi import APIRouter, Query
from app.db import get_read_cursor, get_hero_username, get_hero_player_id
from app.models import PeriodStats, CompareResponse
from app.stats_engine import compute_hero_stats

router = APIRouter()


def _get_period_summary(
    db,
    player_id: int,
    workspace_id: int,
    date_from: str,
    date_to: str | None,
    stakes: str | None,
    game_mode: str | None,
) -> tuple[int, float | None, float | None]:
    """Return (hand_count, win_rate_bb100, win_rate_ev_bb100) for a date range."""
    query = """
        SELECT COUNT(*),
               SUM(CAST(hp.won_bb AS DOUBLE)) / NULLIF(COUNT(*), 0) * 100,
               SUM(CAST(COALESCE(hp.all_in_ev_bb, hp.won_bb) AS DOUBLE)) / NULLIF(COUNT(*), 0) * 100
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE hp.player_id = ? AND h.workspace_id = ?
          AND h.played_at >= ?
    """
    params: list = [player_id, workspace_id, date_from]

    if date_to:
        query += " AND h.played_at <= ?"
        params.append(date_to)
    if stakes:
        query += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        query += " AND h.game_mode = ?"
        params.append(game_mode)

    row = db.execute(query, params).fetchone()
    hands = int(row[0])
    win_rate = round(float(row[1]), 2) if row[1] is not None else None
    ev_rate = round(float(row[2]), 2) if row[2] is not None else None
    return hands, win_rate, ev_rate


@router.get("/compare/stats", response_model=CompareResponse)
def compare_stats(
    workspace_id: int = Query(1),
    period_a_from: str = Query(...),
    period_a_to: str = Query(...),
    period_b_from: str = Query(...),
    period_b_to: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
):
    db = get_read_cursor()
    hero_username = get_hero_username(db, workspace_id)
    player_id = get_hero_player_id(db, workspace_id)

    # Period A stats
    stats_a = compute_hero_stats(
        db, hero_username,
        stakes=stakes, game_mode=game_mode,
        date_from=period_a_from, date_to=period_a_to,
        workspace_id=workspace_id,
    )
    if player_id:
        hands_a, wr_a, ev_a = _get_period_summary(
            db, player_id, workspace_id,
            period_a_from, period_a_to, stakes, game_mode,
        )
    else:
        hands_a, wr_a, ev_a = 0, None, None

    # Period B stats
    stats_b = compute_hero_stats(
        db, hero_username,
        stakes=stakes, game_mode=game_mode,
        date_from=period_b_from, date_to=period_b_to,
        workspace_id=workspace_id,
    )
    if player_id:
        hands_b, wr_b, ev_b = _get_period_summary(
            db, player_id, workspace_id,
            period_b_from, period_b_to, stakes, game_mode,
        )
    else:
        hands_b, wr_b, ev_b = 0, None, None

    return CompareResponse(
        period_a=PeriodStats(
            date_from=period_a_from,
            date_to=period_a_to,
            hands=hands_a,
            win_rate_bb100=wr_a,
            win_rate_ev_bb100=ev_a,
            stats=stats_a,
        ),
        period_b=PeriodStats(
            date_from=period_b_from,
            date_to=period_b_to,
            hands=hands_b,
            win_rate_bb100=wr_b,
            win_rate_ev_bb100=ev_b,
            stats=stats_b,
        ),
    )
