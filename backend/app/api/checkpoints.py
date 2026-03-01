from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from app.db import get_db, db_lock, get_read_cursor
from app.models import CheckpointResponse, CreateCheckpoint, UpdateCheckpoint

router = APIRouter()


def _workspace_exists(db, workspace_id: int) -> bool:
    """Check if a workspace exists."""
    row = db.execute(
        "SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]
    ).fetchone()
    return row is not None


def _row_to_response(row) -> CheckpointResponse:
    """Convert a checkpoint query row to CheckpointResponse."""
    return CheckpointResponse(
        id=row[0],
        workspace_id=row[1],
        name=row[2],
        checkpoint_at=row[3],
        note=row[4],
        created_at=row[5],
    )


@router.get(
    "/workspaces/{workspace_id}/checkpoints",
    response_model=list[CheckpointResponse],
)
def list_checkpoints(workspace_id: int):
    db = get_read_cursor()
    if not _workspace_exists(db, workspace_id):
        raise HTTPException(status_code=404, detail="Workspace not found")

    rows = db.execute(
        "SELECT id, workspace_id, name, checkpoint_at, note, created_at "
        "FROM checkpoints WHERE workspace_id = ? "
        "ORDER BY checkpoint_at DESC",
        [workspace_id],
    ).fetchall()
    return [_row_to_response(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/checkpoints",
    response_model=CheckpointResponse,
    status_code=201,
)
def create_checkpoint(workspace_id: int, body: CreateCheckpoint):
    with db_lock():
        db = get_db()
        if not _workspace_exists(db, workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")

        new_id = db.execute("SELECT nextval('seq_checkpoints')").fetchone()[0]
        checkpoint_at = body.checkpoint_at if body.checkpoint_at is not None else datetime.now(timezone.utc)

        db.execute(
            "INSERT INTO checkpoints (id, workspace_id, name, checkpoint_at, note) "
            "VALUES (?, ?, ?, ?, ?)",
            [new_id, workspace_id, body.name, checkpoint_at, body.note],
        )

        row = db.execute(
            "SELECT id, workspace_id, name, checkpoint_at, note, created_at "
            "FROM checkpoints WHERE id = ?",
            [new_id],
        ).fetchone()

        return _row_to_response(row)


@router.patch(
    "/workspaces/{workspace_id}/checkpoints/{checkpoint_id}",
    response_model=CheckpointResponse,
)
def update_checkpoint(workspace_id: int, checkpoint_id: int, body: UpdateCheckpoint):
    with db_lock():
        db = get_db()
        if not _workspace_exists(db, workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")

        existing = db.execute(
            "SELECT 1 FROM checkpoints WHERE id = ? AND workspace_id = ?",
            [checkpoint_id, workspace_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        updates: list[str] = []
        params: list = []

        if body.name is not None:
            updates.append("name = ?")
            params.append(body.name)

        if body.checkpoint_at is not None:
            updates.append("checkpoint_at = ?")
            params.append(body.checkpoint_at)

        if body.note is not None:
            updates.append("note = ?")
            params.append(body.note)

        if updates:
            params.extend([checkpoint_id, workspace_id])
            db.execute(
                f"UPDATE checkpoints SET {', '.join(updates)} "
                f"WHERE id = ? AND workspace_id = ?",
                params,
            )

        row = db.execute(
            "SELECT id, workspace_id, name, checkpoint_at, note, created_at "
            "FROM checkpoints WHERE id = ? AND workspace_id = ?",
            [checkpoint_id, workspace_id],
        ).fetchone()

        return _row_to_response(row)


@router.delete("/workspaces/{workspace_id}/checkpoints/{checkpoint_id}")
def delete_checkpoint(workspace_id: int, checkpoint_id: int):
    with db_lock():
        db = get_db()
        if not _workspace_exists(db, workspace_id):
            raise HTTPException(status_code=404, detail="Workspace not found")

        existing = db.execute(
            "SELECT 1 FROM checkpoints WHERE id = ? AND workspace_id = ?",
            [checkpoint_id, workspace_id],
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Checkpoint not found")

        db.execute(
            "DELETE FROM checkpoints WHERE id = ? AND workspace_id = ?",
            [checkpoint_id, workspace_id],
        )

        return {"status": "ok"}
