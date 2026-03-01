from fastapi import APIRouter, Query
from app.db import get_db, db_lock, get_read_cursor
from app.models import Settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
def get_settings(workspace_id: int = Query(1)):
    db = get_read_cursor()
    row = db.execute(
        "SELECT hero_username, hero_site FROM workspaces WHERE id = ?",
        [workspace_id],
    ).fetchone()
    if row:
        return Settings(hero_username=row[0], hero_site=row[1])
    return Settings(hero_username="Hero", hero_site="GG")


@router.patch("/settings", response_model=Settings)
def update_settings(settings: Settings, workspace_id: int = Query(1)):
    with db_lock():
        db = get_db()
        db.execute(
            "UPDATE workspaces SET hero_username = ?, hero_site = ? WHERE id = ?",
            [settings.hero_username, settings.hero_site, workspace_id],
        )
        return settings
