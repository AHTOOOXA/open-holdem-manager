from fastapi import APIRouter, HTTPException
from app.db import get_db, db_lock, get_read_cursor
from app.models import WorkspaceResponse, CreateWorkspace, UpdateWorkspace

router = APIRouter()


def _row_to_response(row) -> WorkspaceResponse:
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

    return WorkspaceResponse(
        id=row[0],
        name=row[1],
        hero_username=row[2],
        hero_site=row[3],
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
    return [_row_to_response(r) for r in rows]


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
            [new_id, body.name, body.hero_username, body.hero_site, body.description, body.color],
        )

        row = db.execute(f"""
            {_LIST_SQL}
            WHERE w.id = ?
            GROUP BY w.id, w.name, w.hero_username, w.hero_site,
                     w.description, w.color, w.created_at
        """, [new_id]).fetchone()

        return _row_to_response(row)


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
    return _row_to_response(row)


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

        return _row_to_response(row)


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

        # Get all hand IDs in this workspace for cascading deletes
        hand_ids = [
            r[0]
            for r in db.execute(
                "SELECT id FROM hands WHERE workspace_id = ?", [workspace_id]
            ).fetchall()
        ]

        if hand_ids:
            # DuckDB does not support CASCADE — delete related rows manually
            placeholders = ",".join("?" for _ in hand_ids)

            db.execute(
                f"DELETE FROM hand_notes WHERE hand_id IN ({placeholders}) AND workspace_id = ?",
                hand_ids + [workspace_id],
            )
            db.execute(
                f"DELETE FROM hand_tags WHERE hand_id IN ({placeholders}) AND workspace_id = ?",
                hand_ids + [workspace_id],
            )
            db.execute(
                f"DELETE FROM board_cards WHERE hand_id IN ({placeholders}) AND workspace_id = ?",
                hand_ids + [workspace_id],
            )
            db.execute(
                f"DELETE FROM actions WHERE hand_id IN ({placeholders}) AND workspace_id = ?",
                hand_ids + [workspace_id],
            )
            db.execute(
                f"DELETE FROM hand_players WHERE hand_id IN ({placeholders}) AND workspace_id = ?",
                hand_ids + [workspace_id],
            )
            db.execute(
                f"DELETE FROM hands WHERE workspace_id = ?", [workspace_id]
            )

        # Delete aliases for this workspace
        db.execute(
            "DELETE FROM player_aliases WHERE workspace_id = ?", [workspace_id]
        )

        # Delete checkpoints for this workspace
        db.execute(
            "DELETE FROM checkpoints WHERE workspace_id = ?", [workspace_id]
        )

        # Delete the workspace itself
        db.execute(
            "DELETE FROM workspaces WHERE id = ?", [workspace_id]
        )

        return {"status": "ok"}
