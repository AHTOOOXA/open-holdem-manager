from fastapi import APIRouter, Query
from app.db import get_db
from app.models import HeroStats
from app.stats_engine import compute_hero_stats

router = APIRouter()


@router.get("/stats/hero", response_model=HeroStats)
def get_hero_stats(
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    db = get_db()
    hero_username = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()[0]

    return compute_hero_stats(db, hero_username, position=position, stakes=stakes,
                              date_from=date_from, date_to=date_to)
