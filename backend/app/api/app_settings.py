"""GET/PATCH /api/app-settings (contract: frontend/src/lib/app-settings.ts)."""

from fastapi import APIRouter

from app.app_settings import AppSettings, AppSettingsPatch, get_app_settings, update_app_settings
from app.db import db_lock, get_db, get_read_cursor

router = APIRouter()


@router.get("/app-settings", response_model=AppSettings)
def read_app_settings() -> dict:
    return get_app_settings(get_read_cursor())


@router.patch("/app-settings", response_model=AppSettings)
def patch_app_settings(patch: AppSettingsPatch) -> dict:
    with db_lock():
        return update_app_settings(get_db(), patch)
