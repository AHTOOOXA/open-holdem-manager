from fastapi import APIRouter, HTTPException
from app.db import get_db, db_lock, get_read_cursor
from app.heroes import resolve_hero, add_manual_account, invalidate_hero_cache
from app.models import WorkspaceResponse, CreateWorkspace, UpdateWorkspace

router = APIRouter()


def _row_to_response(row, db) -> WorkspaceResponse:
    """Convert a workspace query row to WorkspaceResponse."""
    date_range: dict[str, str | None] = {}
    if row[7] is not None:
        date_range["min"] = row[7].isoformat()[:10] if hasattr(row[7], "isoformat") else str(row[7])[:10]
    else:
        date_range["min"] = None
    if row[8] is not None:
        date_range["max"] = row[8].isoformat()[:10] if hasattr(row[8], "isoformat") else str(row[8])[:10]
    else:
        date_range["max"] = None

    hero = resolve_hero(db, row[0])
    return WorkspaceResponse(
        id=row[0],
        name=row[1],
        hero_username=hero.username if hero else "",
        hero_site=hero.site_code if hero else "",
        description=row[4],
        color=row[5],
        hand_count=int(row[6] or 0),
        date_range=date_range,
        created_at=row[9],
    )


_LIST_SQL = """
    SELECT
        w.id, w.name, w.hero_username, w.hero_site,
        w.description, w.color,
        COUNT(h.id) AS hand_count,
        MIN(h.played_at) AS min_played,
        MAX(h.played_at) AS max_played,
        w.created_at
    FROM workspaces w
    LEFT JOIN hands h ON h.workspace_id = w.id
"""


@router.get("/workspaces", response_model=list[WorkspaceResponse])
def list_workspaces():
    db = get_read_cursor()
    rows = db.execute(f"""
        {_LIST_SQL}
        GROUP BY w.id, w.name, w.hero_username, w.hero_site,
                 w.description, w.color, w.created_at
        ORDER BY w.created_at ASC
    """).fetchall()
    return [_row_to_response(r, db) for r in rows]


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
def create_workspace(body: CreateWorkspace):
    with db_lock():
        db = get_db()

        # Check unique name
        existing = db.execute(
            "SELECT 1 FROM workspaces WHERE name = ?", [body.name]
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Workspace name already exists")

        new_id = db.execute("SELECT nextval('seq_workspaces')").fetchone()[0]
        db.execute(
            "INSERT INTO workspaces (id, name, hero_username, hero_site, description, color) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [new_id, body.name, body.hero_username or "Hero", body.hero_site or "GG",
             body.description, body.color],
        )
        if body.hero_username and body.hero_username.strip() and body.hero_site and body.hero_site.strip():
            add_manual_account(db, new_id, body.hero_site.strip(), body.hero_username)

        row = db.execute(f"""
            {_LIST_SQL}
            WHERE w.id = ?
            GROUP BY w.id, w.name, w.hero_username, w.hero_site,
                     w.description, w.color, w.created_at
        """, [new_id]).fetchone()

        return _row_to_response(row, db)


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: int):
    db = get_read_cursor()
    row = db.execute(f"""
        {_LIST_SQL}
        WHERE w.id = ?
        GROUP BY w.id, w.name, w.hero_username, w.hero_site,
                 w.description, w.color, w.created_at
    """, [workspace_id]).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _row_to_response(row, db)


@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: int, body: UpdateWorkspace):
    with db_lock():
        db = get_db()

        existing = db.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Workspace not found")

        updates: list[str] = []
        params: list = []

        if body.name is not None:
            # Check unique name (excluding self)
            dup = db.execute(
                "SELECT 1 FROM workspaces WHERE name = ? AND id != ?",
                [body.name, workspace_id],
            ).fetchone()
            if dup:
                raise HTTPException(status_code=400, detail="Workspace name already exists")
            updates.append("name = ?")
            params.append(body.name)

        if body.hero_username is not None:
            updates.append("hero_username = ?")
            params.append(body.hero_username)
            # Legacy shim: the nickname becomes a manual hero account
            add_manual_account(db, workspace_id, body.hero_site or "GG", body.hero_username)

        if body.hero_site is not None:
            updates.append("hero_site = ?")
            params.append(body.hero_site)

        if body.description is not None:
            updates.append("description = ?")
            params.append(body.description)

        if body.color is not None:
            updates.append("color = ?")
            params.append(body.color)

        if updates:
            params.append(workspace_id)
            db.execute(
                f"UPDATE workspaces SET {', '.join(updates)} WHERE id = ?",
                params,
            )

        row = db.execute(f"""
            {_LIST_SQL}
            WHERE w.id = ?
            GROUP BY w.id, w.name, w.hero_username, w.hero_site,
                     w.description, w.color, w.created_at
        """, [workspace_id]).fetchone()

        return _row_to_response(row, db)


# Every table holding rows of one workspace, children before parents. Child tables carry
# workspace_id themselves (db._migrate_child_workspace_id), so each delete is one predicate
# instead of one bound placeholder per hand.
_WORKSPACE_TABLES = (
    "hand_notes", "hand_tags", "board_cards", "actions", "hand_players", "hands",
    "player_aliases", "checkpoints", "hero_accounts", "player_classifications",
)


@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: int):
    with db_lock():
        db = get_db()

        existing = db.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Prevent deleting the last workspace
        count = db.execute("SELECT COUNT(*) FROM workspaces").fetchone()[0]
        if count <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last workspace")

        from app import auto_import
        from app.marked_hands import delete_workspace_marks

        # The workspace's rows go in one transaction: a failure halfway leaves the workspace
        # whole instead of half-deleted. The workspaces row itself is deleted after the
        # commit, because DuckDB checks foreign keys (checkpoints, player_aliases) against
        # the committed state; should that last statement fail, an empty workspace remains.
        db.execute("BEGIN TRANSACTION")
        try:
            for table in _WORKSPACE_TABLES:
                db.execute(f"DELETE FROM {table} WHERE workspace_id = ?", [workspace_id])
            # Players also seen in other workspaces: first/last seen over the hands left (as
            # /import/clear does). Imports only recompute the players they touch, so a stale
            # last_seen from the deleted hands would otherwise stay until a rebuild.
            from app.api.import_hands import _update_first_last_seen
            _update_first_last_seen(db, "")
            # Marks of this workspace (the tag catalogue is global and stays)
            delete_workspace_marks(db, workspace_id)
            db.execute("DELETE FROM settings WHERE key = ?", [f"statistics_dashboards.{workspace_id}"])
            # auto_import.forget_workspace's rows; its in-memory state is dropped only after
            # COMMIT, so a rollback can't lose the pending player pass of a workspace that stays.
            db.execute("DELETE FROM auto_import_files WHERE workspace_id = ?", [workspace_id])
            db.execute("DELETE FROM settings WHERE key = ?", [auto_import.PENDING_KEY + str(workspace_id)])
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        finally:
            invalidate_hero_cache(workspace_id)
            from app import data_generation
            data_generation.bump()
        auto_import.forget_workspace(db, workspace_id, deleted=True)
        db.execute("DELETE FROM workspaces WHERE id = ?", [workspace_id])

        return {"status": "ok"}
