from fastapi import APIRouter, Query
from app.db import get_read_cursor, get_hero_username, get_hero_player_id
from app.models import PeriodStats, CompareResponse
from app.stats_engine import compute_hero_stats, compute_population_stats

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


def _get_population_summary(
    db,
    hero_player_id: int | None,
    workspace_id: int,
    min_hands: int,
    stakes: str | None,
    game_mode: str | None,
) -> tuple[int, int]:
    """Return (player_count, total_observations) for population."""
    query = """
        SELECT COUNT(DISTINCT hp.player_id), COUNT(*)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE h.workspace_id = ?
    """
    params: list = [workspace_id]
    if hero_player_id:
        query += " AND hp.player_id != ?"
        params.append(hero_player_id)
    if stakes:
        query += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        query += " AND h.game_mode = ?"
        params.append(game_mode)
    if min_hands > 1:
        query += f"""
            AND hp.player_id IN (
                SELECT hp2.player_id FROM hand_players hp2
                JOIN hands h2 ON hp2.hand_id = h2.id AND hp2.workspace_id = h2.workspace_id
                WHERE h2.workspace_id = ?
                {"AND hp2.player_id != ?" if hero_player_id else ""}
                GROUP BY hp2.player_id HAVING COUNT(*) >= ?
            )
        """
        params.append(workspace_id)
        if hero_player_id:
            params.append(hero_player_id)
        params.append(min_hands)

    row = db.execute(query, params).fetchone()
    return int(row[0]), int(row[1])


@router.get("/compare/stats", response_model=CompareResponse)
def compare_stats(
    workspace_id: int = Query(1),
    mode: str = Query("periods"),
    # Periods mode params
    period_a_from: str = Query("2000-01-01"),
    period_a_to: str = Query(""),
    period_b_from: str = Query("2000-01-01"),
    period_b_to: str | None = Query(None),
    # Workspace mode params
    workspace_id_b: int | None = Query(None),
    # Population mode params
    min_hands: int = Query(0),
    # Shared filters
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
):
    db = get_read_cursor()

    if mode == "workspace":
        return _compare_workspace(db, workspace_id, workspace_id_b or workspace_id, stakes, game_mode)
    elif mode == "population":
        return _compare_population(db, workspace_id, min_hands, stakes, game_mode)
    else:
        return _compare_periods(db, workspace_id, period_a_from, period_a_to, period_b_from, period_b_to, stakes, game_mode)


def _compare_periods(db, workspace_id, period_a_from, period_a_to, period_b_from, period_b_to, stakes, game_mode):
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


def _compare_workspace(db, workspace_id_a, workspace_id_b, stakes, game_mode):
    hero_a = get_hero_username(db, workspace_id_a)
    hero_b = get_hero_username(db, workspace_id_b)
    pid_a = get_hero_player_id(db, workspace_id_a)
    pid_b = get_hero_player_id(db, workspace_id_b)

    stats_a = compute_hero_stats(
        db, hero_a, stakes=stakes, game_mode=game_mode, workspace_id=workspace_id_a,
    )
    stats_b = compute_hero_stats(
        db, hero_b, stakes=stakes, game_mode=game_mode, workspace_id=workspace_id_b,
    )

    if pid_a:
        hands_a, wr_a, ev_a = _get_period_summary(
            db, pid_a, workspace_id_a, "2000-01-01", None, stakes, game_mode,
        )
    else:
        hands_a, wr_a, ev_a = 0, None, None

    if pid_b:
        hands_b, wr_b, ev_b = _get_period_summary(
            db, pid_b, workspace_id_b, "2000-01-01", None, stakes, game_mode,
        )
    else:
        hands_b, wr_b, ev_b = 0, None, None

    return CompareResponse(
        period_a=PeriodStats(
            date_from="2000-01-01",
            date_to=None,
            hands=hands_a,
            win_rate_bb100=wr_a,
            win_rate_ev_bb100=ev_a,
            stats=stats_a,
        ),
        period_b=PeriodStats(
            date_from="2000-01-01",
            date_to=None,
            hands=hands_b,
            win_rate_bb100=wr_b,
            win_rate_ev_bb100=ev_b,
            stats=stats_b,
        ),
    )


def _compare_population(db, workspace_id, min_hands, stakes, game_mode):
    hero_username = get_hero_username(db, workspace_id)
    hero_player_id = get_hero_player_id(db, workspace_id)

    # Side A: hero stats
    stats_a = compute_hero_stats(
        db, hero_username, stakes=stakes, game_mode=game_mode, workspace_id=workspace_id,
    )
    if hero_player_id:
        hands_a, wr_a, ev_a = _get_period_summary(
            db, hero_player_id, workspace_id, "2000-01-01", None, stakes, game_mode,
        )
    else:
        hands_a, wr_a, ev_a = 0, None, None

    # Side B: population averages
    stats_b = compute_population_stats(
        db,
        workspace_id=workspace_id,
        exclude_player_id=hero_player_id,
        min_hands=min_hands,
        stakes=stakes,
        game_mode=game_mode,
    )

    player_count, total_obs = _get_population_summary(
        db, hero_player_id, workspace_id, min_hands, stakes, game_mode,
    )

    return CompareResponse(
        period_a=PeriodStats(
            date_from="2000-01-01",
            date_to=None,
            hands=hands_a,
            win_rate_bb100=wr_a,
            win_rate_ev_bb100=ev_a,
            stats=stats_a,
        ),
        period_b=PeriodStats(
            date_from="2000-01-01",
            date_to=None,
            hands=total_obs,
            win_rate_bb100=stats_b.win_rate_bb100,
            win_rate_ev_bb100=stats_b.win_rate_ev_bb100,
            stats=stats_b,
            player_count=player_count,
        ),
    )
