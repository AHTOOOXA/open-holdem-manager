from fastapi import APIRouter
from app.db import get_db, db_lock, get_read_cursor
from app.models import Settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
def get_settings():
    db = get_read_cursor()
    rows = db.execute("SELECT key, value FROM settings").fetchall()
    d = {k: v for k, v in rows}
    return Settings(
        hero_username=d.get("hero_username", "Hero"),
        hero_site=d.get("hero_site", "GG"),
    )


@router.patch("/settings", response_model=Settings)
def update_settings(settings: Settings):
    with db_lock():
        db = get_db()
        db.execute(
            "UPDATE settings SET value = ? WHERE key = 'hero_username'",
            [settings.hero_username],
        )
        db.execute(
            "UPDATE settings SET value = ? WHERE key = 'hero_site'",
            [settings.hero_site],
        )
        return settings
