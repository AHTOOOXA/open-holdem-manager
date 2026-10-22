from fastapi import APIRouter, Query
from app.db import get_db, db_lock, get_read_cursor
from app.heroes import add_manual_account, resolve_hero
from app.models import Settings

router = APIRouter()


@router.get("/settings", response_model=Settings)
def get_settings(workspace_id: int = Query(1)):
    ref = resolve_hero(get_read_cursor(), workspace_id)
    if ref:
        return Settings(hero_username=ref.username, hero_site=ref.site_code)
    return Settings(hero_username="Hero", hero_site="GG")


@router.patch("/settings", response_model=Settings)
def update_settings(settings: Settings, workspace_id: int = Query(1)):
    """Legacy shim: the given nickname is added as a manual hero account."""
    with db_lock():
        db = get_db()
        db.execute(
            "UPDATE workspaces SET hero_username = ?, hero_site = ? WHERE id = ?",
            [settings.hero_username, settings.hero_site, workspace_id],
        )
        add_manual_account(db, workspace_id, settings.hero_site or "GG", settings.hero_username)
        return settings
