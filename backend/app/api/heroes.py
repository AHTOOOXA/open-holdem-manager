from fastapi import APIRouter, HTTPException

from app.db import get_db, db_lock, get_read_cursor
from app.heroes import (
    detect_heroes, invalidate_hero_cache, list_accounts, resolve_hero,
)
from app.models import HeroesResponse, PatchHeroes, SetManualHeroes, SiteResponse

router = APIRouter()


def _heroes_response(db, workspace_id: int) -> HeroesResponse:
    row = db.execute(
        "SELECT hero_auto_detect FROM workspaces WHERE id = ?", [workspace_id]
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ref = resolve_hero(db, workspace_id)
    return HeroesResponse(
        auto_detect=bool(row[0]) if row[0] is not None else True,
        accounts=list_accounts(db, workspace_id),
        active={
            "site": ref.site_code, "site_name": ref.site_name,
            "username": ref.username, "hand_count": ref.hand_count,
        } if ref else None,
    )


def _require_workspace(db, workspace_id: int) -> None:
    if not db.execute("SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]).fetchone():
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.get("/sites", response_model=list[SiteResponse])
def list_sites():
    db = get_read_cursor()
    rows = db.execute("SELECT code, name FROM sites ORDER BY id").fetchall()
    return [SiteResponse(code=r[0], name=r[1]) for r in rows]


@router.get("/workspaces/{workspace_id}/heroes", response_model=HeroesResponse)
def get_heroes(workspace_id: int):
    return _heroes_response(get_read_cursor(), workspace_id)


@router.put("/workspaces/{workspace_id}/heroes/manual", response_model=HeroesResponse)
def set_manual_heroes(workspace_id: int, body: SetManualHeroes):
    with db_lock():
        db = get_db()
        _require_workspace(db, workspace_id)
        site = db.execute("SELECT id FROM sites WHERE code = ?", [body.site]).fetchone()
        if not site:
            raise HTTPException(status_code=400, detail=f"Unknown site: {body.site}")
        names = list(dict.fromkeys(n.strip() for n in body.usernames if n and n.strip()))
        db.execute(
            "DELETE FROM hero_accounts WHERE workspace_id = ? AND site_id = ? AND source = 'manual'",
            [workspace_id, site[0]],
        )
        for n in names:
            db.execute(
                "INSERT OR IGNORE INTO hero_accounts (workspace_id, site_id, username, source) "
                "VALUES (?, ?, ?, 'manual')",
                [workspace_id, site[0], n],
            )
        invalidate_hero_cache(workspace_id)
        return _heroes_response(db, workspace_id)


@router.patch("/workspaces/{workspace_id}/heroes", response_model=HeroesResponse)
def patch_heroes(workspace_id: int, body: PatchHeroes):
    with db_lock():
        db = get_db()
        _require_workspace(db, workspace_id)
        db.execute(
            "UPDATE workspaces SET hero_auto_detect = ? WHERE id = ?",
            [body.auto_detect, workspace_id],
        )
        if body.auto_detect:
            detect_heroes(db, workspace_id)
        invalidate_hero_cache(workspace_id)
        return _heroes_response(db, workspace_id)
