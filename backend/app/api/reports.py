from fastapi import APIRouter, Query
from app.db import get_db, db_lock
from app.models import GraphPoint, FilterOptions, StakeBreakdown, MonthBreakdown, PositionBreakdown, ResultsBreakdown

router = APIRouter()


@router.get("/reports/graph", response_model=list[GraphPoint])
def get_graph(
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
):
    with db_lock():
        db = get_db()
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'hero_username'"
        ).fetchone()
        hero_username = row[0] if row else "Hero"

        player = db.execute(
            "SELECT id FROM players WHERE username = ? AND site_id = 1",
            [hero_username],
        ).fetchone()
        if not player:
            return []

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

    for i, (won_bb, ev_bb, rake_bb, _, won_usd, rake_usd, ev_usd, went_sd, jp_bb, jp_usd) in enumerate(rows):
        won_bb_val = float(won_bb or 0)
        won_usd_val = float(won_usd or 0)

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

    return points


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
    with db_lock():
        db = get_db()
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
    date_range = {}
    if date_row and date_row[0]:
        date_range["min"] = str(date_row[0])[:10]
        date_range["max"] = str(date_row[1])[:10]

    return FilterOptions(stakes=stakes, date_range=date_range)


@router.get("/reports/breakdown", response_model=ResultsBreakdown)
def get_breakdown(
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
):
    with db_lock():
        db = get_db()
        player_id = _get_hero_player_id(db)
        if not player_id:
            return ResultsBreakdown()

        where = "hp.player_id = ?"
        params: list = [player_id]
        if stakes:
            where += " AND h.stakes = ?"
            params.append(stakes)
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

        # By stakes
        stakes_rows = db.execute(
            f"""{last_n_cte}
            SELECT h.stakes, h.bb_amount,
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
            GROUP BY h.stakes, h.bb_amount
            ORDER BY h.bb_amount ASC
            """,
            params,
        ).fetchall()

        by_stakes = []
        for r in stakes_rows:
            hands_count = int(r[2])
            won_bb_val = float(r[3])
            ev_bb_val = float(r[5])
            by_stakes.append(StakeBreakdown(
                stakes=r[0],
                bb_amount=float(r[1]),
                hands=hands_count,
                won_bb=round(won_bb_val, 2),
                won_usd=round(float(r[4]), 2),
                ev_bb=round(ev_bb_val, 2),
                rake_bb=round(float(r[6]), 2),
                rake_usd=round(float(r[7]), 2),
                jackpot_bb=round(float(r[8]), 2),
                jackpot_usd=round(float(r[9]), 2),
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
