"""GET/PATCH /api/app-settings (contract: frontend/src/lib/app-settings.ts)."""

from fastapi import APIRouter

from app.app_settings import AppSettings, AppSettingsPatch, DEFAULTS, get_app_settings, update_app_settings
from app.db import db_lock, get_db, get_read_cursor

router = APIRouter()


@router.get("/app-settings", response_model=AppSettings)
def read_app_settings() -> dict:
    return get_app_settings(get_read_cursor())


@router.patch("/app-settings", response_model=AppSettings)
def patch_app_settings(patch: AppSettingsPatch) -> dict:
    with db_lock():
        return update_app_settings(get_db(), patch)


@router.delete("/app-settings", response_model=AppSettings)
def reset_app_settings() -> dict:
    """Restore max break + day start; numeric_date_format is kept."""
    with db_lock():
        db = get_db()
        update_app_settings(db, AppSettingsPatch(
            session_max_break_minutes=DEFAULTS["session_max_break_minutes"],
            day_start_hour=DEFAULTS["day_start_hour"],
        ))
        return get_app_settings(db)
