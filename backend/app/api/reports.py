from fastapi import APIRouter, Query
from app.db import get_db, db_lock
from app.models import GraphPoint

router = APIRouter()


@router.get("/reports/graph", response_model=list[GraphPoint])
def get_graph(
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
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
                   COALESCE(hp.went_to_showdown, FALSE)
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
    cum_bb = 0.0
    cum_ev_bb = 0.0
    cum_rake_bb = 0.0
    cum_sd_bb = 0.0
    cum_nsd_bb = 0.0
    cum_usd = 0.0
    cum_ev_usd = 0.0
    cum_rake_usd = 0.0
    cum_sd_usd = 0.0
    cum_nsd_usd = 0.0

    for i, (won_bb, ev_bb, rake_bb, _, won_usd, rake_usd, ev_usd, went_sd) in enumerate(rows):
        won_bb_val = float(won_bb or 0)
        won_usd_val = float(won_usd or 0)

        cum_bb += won_bb_val
        cum_ev_bb += float(ev_bb or 0)
        cum_rake_bb += float(rake_bb or 0)
        cum_usd += won_usd_val
        cum_ev_usd += float(ev_usd or 0)
        cum_rake_usd += float(rake_usd or 0)

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
            cumulative_showdown_bb=round(cum_sd_bb, 2),
            cumulative_nonshowdown_bb=round(cum_nsd_bb, 2),
            cumulative_usd=round(cum_usd, 2),
            cumulative_ev_usd=round(cum_ev_usd, 2),
            cumulative_rake_usd=round(cum_rake_usd, 2),
            cumulative_showdown_usd=round(cum_sd_usd, 2),
            cumulative_nonshowdown_usd=round(cum_nsd_usd, 2),
        ))

    return points
