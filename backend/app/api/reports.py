from fastapi import APIRouter, Query
from app.db import get_db
from app.models import GraphPoint

router = APIRouter()


@router.get("/reports/graph", response_model=list[GraphPoint])
def get_graph(
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    db = get_db()
    hero_username = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()[0]

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
               COALESCE(hp.all_in_ev_bb, hp.won_bb) * h.bb_amount
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

    points: list[GraphPoint] = []
    cumulative = 0.0
    cumulative_ev = 0.0
    cumulative_rake = 0.0
    cumulative_usd = 0.0
    cumulative_ev_usd = 0.0
    cumulative_rake_usd = 0.0
    window_size = 100

    for i, (won_bb, ev_bb, rake_bb, _, won_usd, rake_usd, ev_usd) in enumerate(rows):
        won_val = float(won_bb or 0)
        ev_val = float(ev_bb or 0)
        cumulative += won_val
        cumulative_ev += ev_val
        cumulative_rake += float(rake_bb or 0)

        won_usd_val = float(won_usd or 0)
        ev_usd_val = float(ev_usd or 0)
        cumulative_usd += won_usd_val
        cumulative_ev_usd += ev_usd_val
        cumulative_rake_usd += float(rake_usd or 0)

        # Rolling over last `window_size` hands
        start = max(0, i - window_size + 1)
        window_len = i - start + 1

        window_sum = sum(float(rows[j][0] or 0) for j in range(start, i + 1))
        window_ev_sum = sum(float(rows[j][1] or 0) for j in range(start, i + 1))
        rolling = (window_sum / window_len) * 100 if window_len > 0 else None
        rolling_ev = (window_ev_sum / window_len) * 100 if window_len > 0 else None

        window_usd_sum = sum(float(rows[j][4] or 0) for j in range(start, i + 1))
        window_ev_usd_sum = sum(float(rows[j][6] or 0) for j in range(start, i + 1))
        rolling_usd = (window_usd_sum / window_len) * 100 if window_len > 0 else None
        rolling_ev_usd = (window_ev_usd_sum / window_len) * 100 if window_len > 0 else None

        points.append(GraphPoint(
            hand_number=i + 1,
            cumulative_bb=round(cumulative, 2),
            bb_per_100_rolling=round(rolling, 2) if rolling is not None else None,
            cumulative_ev_bb=round(cumulative_ev, 2),
            ev_bb_per_100_rolling=round(rolling_ev, 2) if rolling_ev is not None else None,
            cumulative_rake_bb=round(cumulative_rake, 2),
            cumulative_usd=round(cumulative_usd, 2),
            cumulative_ev_usd=round(cumulative_ev_usd, 2),
            cumulative_rake_usd=round(cumulative_rake_usd, 2),
            usd_per_100_rolling=round(rolling_usd, 2) if rolling_usd is not None else None,
            ev_usd_per_100_rolling=round(rolling_ev_usd, 2) if rolling_ev_usd is not None else None,
        ))

    return points
