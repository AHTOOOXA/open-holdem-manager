import json

from fastapi import APIRouter, HTTPException, Query
from app.db import get_db, db_lock, get_read_cursor
from app.models import (
    IdentityResponse, CreateIdentity, UpdateIdentity,
    AliasResponse, AddAlias, HeroStats,
)

router = APIRouter()


def _build_identity(db, identity_id: int) -> IdentityResponse | None:
    """Build a full IdentityResponse with aliases and hand count."""
    row = db.execute(
        "SELECT id, display_name, notes, color, tags, created_at "
        "FROM player_identities WHERE id = ?",
        [identity_id],
    ).fetchone()
    if not row:
        return None

    try:
        tags = json.loads(row[4]) if row[4] else []
    except (json.JSONDecodeError, TypeError):
        tags = []

    aliases_rows = db.execute(
        "SELECT pa.id, pa.identity_id, pa.workspace_id, pa.player_id, "
        "p.username, w.name "
        "FROM player_aliases pa "
        "JOIN players p ON p.id = pa.player_id "
        "JOIN workspaces w ON w.id = pa.workspace_id "
        "WHERE pa.identity_id = ? "
        "ORDER BY w.name, p.username",
        [identity_id],
    ).fetchall()

    aliases = [
        AliasResponse(
            id=a[0], identity_id=a[1], workspace_id=a[2],
            player_id=a[3], username=a[4], workspace_name=a[5],
        )
        for a in aliases_rows
    ]

    # Total hands across all aliases
    if aliases:
        player_ids = [a.player_id for a in aliases]
        ph = ",".join("?" for _ in player_ids)
        total = db.execute(
            f"SELECT COUNT(*) FROM hand_players WHERE player_id IN ({ph})",
            player_ids,
        ).fetchone()[0]
    else:
        total = 0

    return IdentityResponse(
        id=row[0],
        display_name=row[1],
        notes=row[2],
        color=row[3],
        tags=tags,
        aliases=aliases,
        total_hands=total,
        created_at=row[5],
    )


@router.get("/identities", response_model=list[IdentityResponse])
def list_identities():
    db = get_read_cursor()
    ids = [
        r[0] for r in db.execute(
            "SELECT id FROM player_identities ORDER BY created_at ASC"
        ).fetchall()
    ]
    return [_build_identity(db, i) for i in ids]


@router.post("/identities", response_model=IdentityResponse, status_code=201)
def create_identity(body: CreateIdentity):
    with db_lock():
        db = get_db()
        new_id = db.execute("SELECT nextval('seq_identities')").fetchone()[0]
        db.execute(
            "INSERT INTO player_identities (id, display_name, notes, color, tags) "
            "VALUES (?, ?, ?, ?, ?)",
            [new_id, body.display_name, body.notes, body.color, json.dumps(body.tags)],
        )
        return _build_identity(db, new_id)


@router.get("/identities/{identity_id}", response_model=IdentityResponse)
def get_identity(identity_id: int):
    db = get_read_cursor()
    result = _build_identity(db, identity_id)
    if not result:
        raise HTTPException(status_code=404, detail="Identity not found")
    return result


@router.patch("/identities/{identity_id}", response_model=IdentityResponse)
def update_identity(identity_id: int, body: UpdateIdentity):
    with db_lock():
        db = get_db()
        if not db.execute(
            "SELECT 1 FROM player_identities WHERE id = ?", [identity_id]
        ).fetchone():
            raise HTTPException(status_code=404, detail="Identity not found")

        updates: list[str] = []
        params: list = []

        if body.display_name is not None:
            updates.append("display_name = ?")
            params.append(body.display_name)
        if body.notes is not None:
            updates.append("notes = ?")
            params.append(body.notes)
        if body.color is not None:
            updates.append("color = ?")
            params.append(body.color)
        if body.tags is not None:
            updates.append("tags = ?")
            params.append(json.dumps(body.tags))

        if updates:
            params.append(identity_id)
            db.execute(
                f"UPDATE player_identities SET {', '.join(updates)} WHERE id = ?",
                params,
            )

        return _build_identity(db, identity_id)


@router.delete("/identities/{identity_id}")
def delete_identity(identity_id: int):
    with db_lock():
        db = get_db()
        if not db.execute(
            "SELECT 1 FROM player_identities WHERE id = ?", [identity_id]
        ).fetchone():
            raise HTTPException(status_code=404, detail="Identity not found")

        db.execute(
            "DELETE FROM player_aliases WHERE identity_id = ?", [identity_id]
        )
        db.execute(
            "DELETE FROM player_identities WHERE id = ?", [identity_id]
        )
        return {"status": "ok"}


# ── Alias management ────────────────────────────────────────────


@router.post(
    "/identities/{identity_id}/aliases",
    response_model=IdentityResponse,
    status_code=201,
)
def add_alias(identity_id: int, body: AddAlias):
    with db_lock():
        db = get_db()
        if not db.execute(
            "SELECT 1 FROM player_identities WHERE id = ?", [identity_id]
        ).fetchone():
            raise HTTPException(status_code=404, detail="Identity not found")

        if not db.execute(
            "SELECT 1 FROM players WHERE id = ?", [body.player_id]
        ).fetchone():
            raise HTTPException(status_code=404, detail="Player not found")

        if not db.execute(
            "SELECT 1 FROM workspaces WHERE id = ?", [body.workspace_id]
        ).fetchone():
            raise HTTPException(status_code=404, detail="Workspace not found")

        # Check unique constraint: one player can only belong to one identity per workspace
        existing = db.execute(
            "SELECT identity_id FROM player_aliases "
            "WHERE workspace_id = ? AND player_id = ?",
            [body.workspace_id, body.player_id],
        ).fetchone()
        if existing:
            if existing[0] == identity_id:
                raise HTTPException(
                    status_code=400,
                    detail="Player is already linked to this identity",
                )
            raise HTTPException(
                status_code=400,
                detail="Player is already linked to another identity",
            )

        new_id = db.execute("SELECT nextval('seq_aliases')").fetchone()[0]
        db.execute(
            "INSERT INTO player_aliases (id, identity_id, workspace_id, player_id) "
            "VALUES (?, ?, ?, ?)",
            [new_id, identity_id, body.workspace_id, body.player_id],
        )

        return _build_identity(db, identity_id)


@router.delete("/identities/{identity_id}/aliases/{alias_id}")
def remove_alias(identity_id: int, alias_id: int):
    with db_lock():
        db = get_db()
        row = db.execute(
            "SELECT 1 FROM player_aliases WHERE id = ? AND identity_id = ?",
            [alias_id, identity_id],
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alias not found")

        db.execute("DELETE FROM player_aliases WHERE id = ?", [alias_id])
        return {"status": "ok"}


# ── Aggregated cross-workspace stats ────────────────────────────


@router.get("/identities/{identity_id}/stats", response_model=HeroStats)
def get_identity_stats(
    identity_id: int,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    db = get_read_cursor()

    if not db.execute(
        "SELECT 1 FROM player_identities WHERE id = ?", [identity_id]
    ).fetchone():
        raise HTTPException(status_code=404, detail="Identity not found")

    # Get all player_ids for this identity
    alias_rows = db.execute(
        "SELECT player_id FROM player_aliases WHERE identity_id = ?",
        [identity_id],
    ).fetchall()
    player_ids = [r[0] for r in alias_rows]

    if not player_ids:
        return HeroStats()

    return _compute_identity_stats(
        db, player_ids,
        position=position, stakes=stakes, game_mode=game_mode,
        date_from=date_from, date_to=date_to,
    )


def _compute_identity_stats(
    db,
    player_ids: list[int],
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> HeroStats:
    """Compute aggregated stats across multiple player IDs (no workspace filter)."""
    from app.stats_engine import _compute_stats_from_query

    ph = ",".join("?" for _ in player_ids)
    where_parts = [f"hp.player_id IN ({ph})"]
    params: list = list(player_ids)

    if position:
        where_parts.append("hp.position = ?")
        params.append(position.upper())
    if stakes:
        where_parts.append("h.stakes = ?")
        params.append(stakes)
    if game_mode is not None:
        where_parts.append("h.game_mode = ?")
        params.append(game_mode)
    if date_from:
        where_parts.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("h.played_at <= ?")
        params.append(date_to + " 23:59:59")

    where_sql = " AND ".join(where_parts)
    return _compute_stats_from_query(db, where_sql, params)
