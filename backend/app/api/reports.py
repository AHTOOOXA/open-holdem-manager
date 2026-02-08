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
        SELECT hp.won_bb, h.played_at
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
    window_size = 100

    for i, (won_bb, _) in enumerate(rows):
        cumulative += float(won_bb or 0)
        # Rolling BB/100 over last `window_size` hands
        start = max(0, i - window_size + 1)
        window_sum = sum(float(rows[j][0] or 0) for j in range(start, i + 1))
        window_len = i - start + 1
        rolling = (window_sum / window_len) * 100 if window_len > 0 else None

        points.append(GraphPoint(
            hand_number=i + 1,
            cumulative_bb=round(cumulative, 2),
            bb_per_100_rolling=round(rolling, 2) if rolling is not None else None,
        ))

    return points
