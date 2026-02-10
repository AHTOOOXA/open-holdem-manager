from fastapi import APIRouter, Query
from app.db import get_read_cursor
from app.models import GraphPoint, GraphResponse, VarianceStats, SessionMarker, FilterOptions, StakeBreakdown, MonthBreakdown, PositionBreakdown, ResultsBreakdown, DriftStat, DriftResponse
import math
from datetime import datetime, timedelta

router = APIRouter()


SESSION_GAP = timedelta(minutes=10)


@router.get("/reports/graph", response_model=GraphResponse)
def get_graph(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
):
    db = get_read_cursor()
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"

    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    if not player:
        return GraphResponse(points=[], sessions=[], variance=None)

    player_id = player[0]

    query = """
        SELECT hp.won_bb, COALESCE(hp.all_in_ev_bb, hp.won_bb),
               COALESCE(hp.rake_bb, 0), h.played_at,
               COALESCE(hp.won, 0),
               COALESCE(hp.rake, 0),
               COALESCE(hp.all_in_ev_bb, hp.won_bb) * h.bb_amount,
               COALESCE(hp.went_to_showdown, FALSE),
               COALESCE(hp.jackpot_bb, 0),
               COALESCE(hp.jackpot, 0)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
    """
    params: list = [player_id]

    if stakes:
        query += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode:
        query += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        query += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND h.played_at <= ?"
        params.append(date_to)

    query += " ORDER BY h.played_at ASC, h.id ASC"

    rows = db.execute(query, params).fetchall()

    if last_n and len(rows) > last_n:
        rows = rows[-last_n:]

    points: list[GraphPoint] = []
    won_bb_values: list[float] = []
    session_starts: list[int] = []
    timestamps: list[str] = []
    prev_played_at: datetime | None = None

    cum_bb = 0.0
    cum_ev_bb = 0.0
    cum_rake_bb = 0.0
    cum_sd_bb = 0.0
    cum_nsd_bb = 0.0
    cum_usd = 0.0
    cum_ev_usd = 0.0
    cum_rake_usd = 0.0
    cum_jackpot_bb = 0.0
    cum_jackpot_usd = 0.0
    cum_sd_usd = 0.0
    cum_nsd_usd = 0.0

    for i, (won_bb, ev_bb, rake_bb, played_at, won_usd, rake_usd, ev_usd, went_sd, jp_bb, jp_usd) in enumerate(rows):
        won_bb_val = float(won_bb or 0)
        won_usd_val = float(won_usd or 0)
        won_bb_values.append(won_bb_val)

        # Session detection
        if isinstance(played_at, str):
            played_at = datetime.fromisoformat(played_at)
        if i == 0:
            session_starts.append(1)
        elif prev_played_at and (played_at - prev_played_at) > SESSION_GAP:
            session_starts.append(i + 1)

        played_at_iso = played_at.isoformat() if isinstance(played_at, datetime) else str(played_at)
        timestamps.append(played_at_iso)
        prev_played_at = played_at

        cum_bb += won_bb_val
        cum_ev_bb += float(ev_bb or 0)
        cum_rake_bb += float(rake_bb or 0)
        cum_usd += won_usd_val
        cum_ev_usd += float(ev_usd or 0)
        cum_rake_usd += float(rake_usd or 0)
        cum_jackpot_bb += float(jp_bb or 0)
        cum_jackpot_usd += float(jp_usd or 0)

        if went_sd:
            cum_sd_bb += won_bb_val
            cum_sd_usd += won_usd_val
        else:
            cum_nsd_bb += won_bb_val
            cum_nsd_usd += won_usd_val

        points.append(GraphPoint(
            hand_number=i + 1,
            played_at=played_at_iso,
            cumulative_bb=round(cum_bb, 2),
            cumulative_ev_bb=round(cum_ev_bb, 2),
            cumulative_rake_bb=round(cum_rake_bb, 2),
            cumulative_jackpot_bb=round(cum_jackpot_bb, 2),
            cumulative_showdown_bb=round(cum_sd_bb, 2),
            cumulative_nonshowdown_bb=round(cum_nsd_bb, 2),
            cumulative_usd=round(cum_usd, 2),
            cumulative_ev_usd=round(cum_ev_usd, 2),
            cumulative_rake_usd=round(cum_rake_usd, 2),
            cumulative_jackpot_usd=round(cum_jackpot_usd, 2),
            cumulative_showdown_usd=round(cum_sd_usd, 2),
            cumulative_nonshowdown_usd=round(cum_nsd_usd, 2),
        ))

    # Compute variance stats
    variance: VarianceStats | None = None
    n = len(won_bb_values)
    if n >= 2:
        mean = sum(won_bb_values) / n
        sq_diffs = sum((x - mean) ** 2 for x in won_bb_values)
        sd_per_hand = math.sqrt(sq_diffs / (n - 1))
        sd_bb100 = round(sd_per_hand * 10, 2)
        winrate_bb100 = round(mean * 100, 2)
        se_bb100 = sd_per_hand * 100 / math.sqrt(n)
        variance = VarianceStats(
            sd_bb=round(sd_per_hand, 4),
            sd_bb100=sd_bb100,
            winrate_bb100=winrate_bb100,
            ci_lower_bb100=round(winrate_bb100 - 1.96 * se_bb100, 2),
            ci_upper_bb100=round(winrate_bb100 + 1.96 * se_bb100, 2),
            n=n,
        )

    # Build session markers from session_starts
    sessions: list[SessionMarker] = []
    for j, start in enumerate(session_starts):
        end = session_starts[j + 1] - 1 if j + 1 < len(session_starts) else len(points)
        sessions.append(SessionMarker(
            start_hand=start,
            end_hand=end,
            start_time=timestamps[start - 1] if start - 1 < len(timestamps) else "",
            end_time=timestamps[end - 1] if end - 1 < len(timestamps) else "",
        ))

    return GraphResponse(points=points, sessions=sessions, variance=variance)


def _get_hero_player_id(db):
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"
    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    return player[0] if player else None


@router.get("/reports/filter-options", response_model=FilterOptions)
def get_filter_options():
    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return FilterOptions()

    stakes_rows = db.execute(
        """
        SELECT DISTINCT h.stakes
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
        ORDER BY h.stakes
        """,
        [player_id],
    ).fetchall()

    game_mode_rows = db.execute(
        """
        SELECT DISTINCT h.game_mode
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
        ORDER BY h.game_mode
        """,
        [player_id],
    ).fetchall()

    date_row = db.execute(
        """
        SELECT MIN(h.played_at), MAX(h.played_at)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
        """,
        [player_id],
    ).fetchone()

    stakes = [r[0] for r in stakes_rows]
    game_modes = [r[0] for r in game_mode_rows]
    date_range = {}
    if date_row and date_row[0]:
        date_range["min"] = str(date_row[0])[:10]
        date_range["max"] = str(date_row[1])[:10]

    return FilterOptions(stakes=stakes, game_modes=game_modes, date_range=date_range)


@router.get("/reports/breakdown", response_model=ResultsBreakdown)
def get_breakdown(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
):
    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return ResultsBreakdown()

    where = "hp.player_id = ?"
    params: list = [player_id]
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode:
        where += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND h.played_at <= ?"
        params.append(date_to)

    # For last_n, restrict to the most recent N hand IDs
    last_n_cte = ""
    if last_n:
        last_n_params = list(params)  # same filters
        last_n_cte = f"""
        WITH recent_hands AS (
            SELECT h.id FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {where}
            ORDER BY h.played_at DESC, h.id DESC
            LIMIT {int(last_n)}
        )
        """
        where += " AND h.id IN (SELECT id FROM recent_hands)"
        # params are used twice: once in CTE, once in main query
        params = last_n_params + params

    # By stakes (grouped by game_mode + stakes)
    stakes_rows = db.execute(
        f"""{last_n_cte}
        SELECT h.game_mode, h.stakes, h.bb_amount,
               COUNT(*) as hands,
               SUM(COALESCE(hp.won_bb, 0)) as won_bb,
               SUM(COALESCE(hp.won, 0)) as won_usd,
               SUM(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)) as ev_bb,
               SUM(COALESCE(hp.rake_bb, 0)) as rake_bb,
               SUM(COALESCE(hp.rake, 0)) as rake_usd,
               SUM(COALESCE(hp.jackpot_bb, 0)) as jackpot_bb,
               SUM(COALESCE(hp.jackpot, 0)) as jackpot_usd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
        GROUP BY h.game_mode, h.stakes, h.bb_amount
        ORDER BY h.bb_amount ASC, h.game_mode ASC
        """,
        params,
    ).fetchall()

    by_stakes = []
    for r in stakes_rows:
        hands_count = int(r[3])
        won_bb_val = float(r[4])
        ev_bb_val = float(r[6])
        by_stakes.append(StakeBreakdown(
            game_mode=r[0],
            stakes=r[1],
            bb_amount=float(r[2]),
            hands=hands_count,
            won_bb=round(won_bb_val, 2),
            won_usd=round(float(r[5]), 2),
            ev_bb=round(ev_bb_val, 2),
            rake_bb=round(float(r[7]), 2),
            rake_usd=round(float(r[8]), 2),
            jackpot_bb=round(float(r[9]), 2),
            jackpot_usd=round(float(r[10]), 2),
            bb_per_100=round((won_bb_val / hands_count) * 100, 2) if hands_count else 0,
            ev_bb_per_100=round((ev_bb_val / hands_count) * 100, 2) if hands_count else 0,
        ))

    # By month
    month_rows = db.execute(
        f"""{last_n_cte}
        SELECT strftime(h.played_at, '%Y-%m') as month,
               COUNT(*) as hands,
               SUM(COALESCE(hp.won_bb, 0)) as won_bb,
               SUM(COALESCE(hp.won, 0)) as won_usd,
               SUM(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)) as ev_bb,
               SUM(COALESCE(hp.rake_bb, 0)) as rake_bb,
               SUM(COALESCE(hp.rake, 0)) as rake_usd,
               SUM(COALESCE(hp.jackpot_bb, 0)) as jackpot_bb,
               SUM(COALESCE(hp.jackpot, 0)) as jackpot_usd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
        GROUP BY strftime(h.played_at, '%Y-%m')
        ORDER BY month DESC
        """,
        params,
    ).fetchall()

    by_month = []
    for r in month_rows:
        hands_count = int(r[1])
        won_bb_val = float(r[2])
        ev_bb_val = float(r[4])
        by_month.append(MonthBreakdown(
            month=r[0],
            hands=hands_count,
            won_bb=round(won_bb_val, 2),
            won_usd=round(float(r[3]), 2),
            ev_bb=round(ev_bb_val, 2),
            rake_bb=round(float(r[5]), 2),
            rake_usd=round(float(r[6]), 2),
            jackpot_bb=round(float(r[7]), 2),
            jackpot_usd=round(float(r[8]), 2),
            bb_per_100=round((won_bb_val / hands_count) * 100, 2) if hands_count else 0,
            ev_bb_per_100=round((ev_bb_val / hands_count) * 100, 2) if hands_count else 0,
        ))

    # By position
    pos_order = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB']
    pos_rows = db.execute(
        f"""{last_n_cte}
        SELECT hp.position,
               COUNT(*) as hands,
               SUM(COALESCE(hp.won_bb, 0)) as won_bb,
               SUM(COALESCE(hp.won, 0)) as won_usd,
               SUM(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)) as ev_bb,
               SUM(COALESCE(hp.rake_bb, 0)) as rake_bb,
               SUM(COALESCE(hp.rake, 0)) as rake_usd,
               SUM(COALESCE(hp.jackpot_bb, 0)) as jackpot_bb,
               SUM(COALESCE(hp.jackpot, 0)) as jackpot_usd
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
        GROUP BY hp.position
        """,
        params,
    ).fetchall()

    pos_map = {}
    for r in pos_rows:
        pos_map[r[0]] = r

    by_position = []
    for pos in pos_order:
        r = pos_map.get(pos)
        if not r:
            continue
        hands_count = int(r[1])
        won_bb_val = float(r[2])
        ev_bb_val = float(r[4])
        by_position.append(PositionBreakdown(
            position=pos,
            hands=hands_count,
            won_bb=round(won_bb_val, 2),
            won_usd=round(float(r[3]), 2),
            ev_bb=round(ev_bb_val, 2),
            rake_bb=round(float(r[5]), 2),
            rake_usd=round(float(r[6]), 2),
            jackpot_bb=round(float(r[7]), 2),
            jackpot_usd=round(float(r[8]), 2),
            bb_per_100=round((won_bb_val / hands_count) * 100, 2) if hands_count else 0,
            ev_bb_per_100=round((ev_bb_val / hands_count) * 100, 2) if hands_count else 0,
        ))

    return ResultsBreakdown(by_stakes=by_stakes, by_month=by_month, by_position=by_position)


# ── Drift Detection ─────────────────────────────────────────────────

# Each stat: (key, value_expr, opp_filter)
# value_expr: SQL expression for the 0/1 value
# opp_filter: SQL WHERE clause fragment for opportunity filtering
_DRIFT_STATS_V2: list[tuple[str, str, str]] = [
    ("vpip",               "CAST(hp.vpip AS DOUBLE)",               ""),
    ("pfr",                "CAST(hp.pfr AS DOUBLE)",                ""),
    ("three_bet",          "CAST(hp.three_bet AS DOUBLE)",          "AND hp.three_bet_opp = true"),
    ("fold_to_3bet",       "CAST(hp.fold_to_3bet AS DOUBLE)",       "AND hp.three_bet_opp = true"),
    ("cbet_flop",          "CAST(hp.cbet_flop AS DOUBLE)",          "AND hp.cbet_flop_opp = true"),
    ("fold_to_cbet_flop",  "CAST(hp.fold_to_cbet_flop AS DOUBLE)",  "AND hp.fold_to_cbet_flop IS NOT NULL"),
    ("went_to_showdown",   "CAST(hp.went_to_showdown AS DOUBLE)",   "AND hp.saw_flop = true"),
    ("won_at_showdown",    "CAST(hp.won_at_showdown AS DOUBLE)",    "AND hp.went_to_showdown = true"),
    ("steal",              "CAST(hp.steal_attempted AS DOUBLE)",    "AND hp.steal_opp = true"),
    ("fold_to_steal",      "CAST(hp.fold_to_steal AS DOUBLE)",      "AND hp.faced_steal = true"),
    ("wwsf",               "CASE WHEN hp.won_bb > 0 THEN 1.0 ELSE 0.0 END", "AND hp.saw_flop = true"),
]

_DRIFT_INTERPRETATIONS: dict[str, dict[str, str]] = {
    "vpip":              {"up": "Playing more hands than usual",        "down": "Playing fewer hands than usual"},
    "pfr":               {"up": "Raising more preflop than usual",      "down": "Raising less preflop than usual"},
    "three_bet":         {"up": "3-betting more than usual",            "down": "3-betting less than usual"},
    "fold_to_3bet":      {"up": "Folding to 3-bets more than usual",   "down": "Defending vs 3-bets more than usual"},
    "cbet_flop":         {"up": "C-betting the flop more than usual",  "down": "Checking the flop more than usual"},
    "fold_to_cbet_flop": {"up": "Folding to flop c-bets more often",   "down": "Defending vs flop c-bets more often"},
    "went_to_showdown":  {"up": "Going to showdown more often",        "down": "Folding before showdown more often"},
    "won_at_showdown":   {"up": "Winning more at showdown",            "down": "Losing more at showdown"},
    "steal":             {"up": "Stealing more than usual",             "down": "Stealing less than usual"},
    "fold_to_steal":     {"up": "Folding to steals more often",        "down": "Defending vs steals more often"},
    "wwsf":              {"up": "Winning more when seeing the flop",   "down": "Winning less when seeing the flop"},
    "afq_flop":          {"up": "Playing more aggressively on flop",   "down": "Playing more passively on flop"},
}


def _check_drift(
    lifetime_avg: float,
    window_avg: float,
    window_n: int,
) -> tuple[float, float, float] | None:
    """Return (drift_pct, ci_lower, ci_upper) if drift detected, else None.

    Detection requires:
    1. |recent - lifetime| > lifetime * 0.10 (practical significance)
    2. lifetime falls outside 95% CI of recent estimate (statistical confidence)
    """
    diff = abs(window_avg - lifetime_avg)

    # Practical significance: at least 10% relative change
    if lifetime_avg > 0 and diff < lifetime_avg * 0.10:
        return None
    # Edge case: lifetime is 0 but window is non-zero
    if lifetime_avg == 0 and window_avg == 0:
        return None

    # 95% CI for window proportion
    se = math.sqrt(window_avg * (1.0 - window_avg) / window_n) if window_n > 0 else 0.0
    ci_lower = max(0.0, window_avg - 1.96 * se)
    ci_upper = min(1.0, window_avg + 1.96 * se)

    # Statistical confidence: lifetime must fall outside CI
    if ci_lower <= lifetime_avg <= ci_upper:
        return None

    drift_pct = ((window_avg - lifetime_avg) / lifetime_avg * 100) if lifetime_avg > 0 else (100.0 if window_avg > 0 else 0.0)
    return (drift_pct, ci_lower, ci_upper)


@router.get("/reports/drift", response_model=DriftResponse)
def get_drift(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return DriftResponse()

    # Build shared WHERE clause
    where = "hp.player_id = ?"
    params: list = [player_id]
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode:
        where += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND h.played_at <= ?"
        params.append(date_to)

    # Get total hand count
    total_count = db.execute(
        f"SELECT COUNT(*) FROM hand_players hp JOIN hands h ON hp.hand_id = h.id WHERE {where}",
        params,
    ).fetchone()[0]

    if total_count < 20000:
        return DriftResponse(total_hands=total_count)

    # Window = last 20% of hands
    window_size = max(1, int(total_count * 0.20))

    results: list[DriftStat] = []

    # Process standard boolean/0-1 stats
    for stat_key, value_expr, opp_filter in _DRIFT_STATS_V2:
        # Lifetime average + count
        lifetime_row = db.execute(
            f"""
            SELECT AVG({value_expr}), COUNT(*)
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {where} {opp_filter}
            """,
            params,
        ).fetchone()

        lifetime_avg = float(lifetime_row[0]) if lifetime_row[0] is not None else 0.0
        lifetime_n = int(lifetime_row[1])

        if lifetime_n == 0:
            continue

        # Window: last N hands (by played_at) where opportunity is met
        window_row = db.execute(
            f"""
            WITH recent AS (
                SELECT {value_expr} AS val
                FROM hand_players hp
                JOIN hands h ON hp.hand_id = h.id
                WHERE {where} {opp_filter}
                ORDER BY h.played_at DESC, h.id DESC
                LIMIT ?
            )
            SELECT AVG(val), COUNT(*) FROM recent
            """,
            params + [window_size],
        ).fetchone()

        window_avg = float(window_row[0]) if window_row[0] is not None else 0.0
        window_n = int(window_row[1])

        if window_n < 30:
            continue

        result = _check_drift(lifetime_avg, window_avg, window_n)
        if result is None:
            continue

        drift_pct, ci_lower, ci_upper = result
        direction = "up" if window_avg > lifetime_avg else "down"
        interp = _DRIFT_INTERPRETATIONS.get(stat_key, {}).get(direction, "")

        results.append(DriftStat(
            stat=stat_key,
            lifetime_avg=round(lifetime_avg * 100, 2),
            window_avg=round(window_avg * 100, 2),
            lifetime_n=lifetime_n,
            window_n=window_n,
            drift_pct=round(drift_pct, 1),
            ci_lower=round(ci_lower * 100, 2),
            ci_upper=round(ci_upper * 100, 2),
            direction=direction,
            interpretation=interp,
        ))

    # AFq Flop: action-ratio stat (not a simple boolean)
    _process_afq_flop(db, where, params, window_size, results)

    return DriftResponse(
        stats=results,
        window_hands=window_size,
        total_hands=total_count,
    )


def _process_afq_flop(
    db, where: str, params: list, window_size: int, results: list[DriftStat],
) -> None:
    """AFq Flop = (bets + raises) / (bets + raises + calls + checks + folds) on flop."""
    # Lifetime
    lifetime_row = db.execute(
        f"""
        SELECT SUM(hp.flop_bets + hp.flop_raises),
               SUM(hp.flop_bets + hp.flop_raises + hp.flop_calls + hp.flop_checks + hp.flop_folds),
               COUNT(*)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where} AND hp.saw_flop = true
        """,
        params,
    ).fetchone()

    agg_num = int(lifetime_row[0]) if lifetime_row[0] is not None else 0
    agg_den = int(lifetime_row[1]) if lifetime_row[1] is not None else 0

    if agg_den == 0:
        return

    lifetime_avg = agg_num / agg_den

    # Window
    window_row = db.execute(
        f"""
        WITH recent AS (
            SELECT hp.flop_bets + hp.flop_raises AS num,
                   hp.flop_bets + hp.flop_raises + hp.flop_calls + hp.flop_checks + hp.flop_folds AS den
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {where} AND hp.saw_flop = true
            ORDER BY h.played_at DESC, h.id DESC
            LIMIT ?
        )
        SELECT SUM(num), SUM(den), COUNT(*) FROM recent
        """,
        params + [window_size],
    ).fetchone()

    w_num = int(window_row[0]) if window_row[0] is not None else 0
    w_den = int(window_row[1]) if window_row[1] is not None else 0
    window_n = int(window_row[2])

    if w_den == 0 or window_n < 30:
        return

    window_avg = w_num / w_den

    result = _check_drift(lifetime_avg, window_avg, w_den)
    if result is None:
        return

    drift_pct, ci_lower, ci_upper = result
    direction = "up" if window_avg > lifetime_avg else "down"
    interp = _DRIFT_INTERPRETATIONS.get("afq_flop", {}).get(direction, "")

    results.append(DriftStat(
        stat="afq_flop",
        lifetime_avg=round(lifetime_avg * 100, 2),
        window_avg=round(window_avg * 100, 2),
        lifetime_n=agg_den,
        window_n=w_den,
        drift_pct=round(drift_pct, 1),
        ci_lower=round(ci_lower * 100, 2),
        ci_upper=round(ci_upper * 100, 2),
        direction=direction,
        interpretation=interp,
    ))
