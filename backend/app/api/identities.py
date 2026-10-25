import csv
import io
import json

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from app.date_filters import DATE_TO_SQL
from app.db import get_db, db_lock, get_read_cursor
from app.stat_registry import POS_SQL
from app.models import (
    IdentityResponse, CreateIdentity, UpdateIdentity,
    AliasResponse, AddAlias, HeroStats,
)

router = APIRouter()


def _build_identity(db, identity_id: int) -> IdentityResponse | None:
    """Build a full IdentityResponse with aliases and hand count."""
    row = db.execute(
        "SELECT id, display_name, notes, color, tags, created_at, "
        "COALESCE(is_single_person, FALSE), COALESCE(pinned, FALSE) "
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

    # Total hands across all aliases (deduplicate by hand_id so the same
    # physical hand imported into multiple workspaces is only counted once)
    if aliases:
        player_ids = [a.player_id for a in aliases]
        ph = ",".join("?" for _ in player_ids)
        total = db.execute(
            f"SELECT COUNT(DISTINCT hand_id) FROM hand_players WHERE player_id IN ({ph})",
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
        is_single_person=bool(row[6]),
        pinned=bool(row[7]),
        player_count=len(aliases),
        created_at=row[5],
    )


@router.get("/identities", response_model=list[IdentityResponse])
def list_identities():
    """Every identity, as _build_identity builds one, in three queries in total."""
    db = get_read_cursor()
    rows = db.execute(
        "SELECT id, display_name, notes, color, tags, created_at, "
        "COALESCE(is_single_person, FALSE), COALESCE(pinned, FALSE) "
        "FROM player_identities ORDER BY created_at ASC"
    ).fetchall()
    if not rows:
        return []

    aliases: dict[int, list[AliasResponse]] = {}
    for a in db.execute(
        "SELECT pa.id, pa.identity_id, pa.workspace_id, pa.player_id, "
        "p.username, w.name "
        "FROM player_aliases pa "
        "JOIN players p ON p.id = pa.player_id "
        "JOIN workspaces w ON w.id = pa.workspace_id "
        "ORDER BY pa.identity_id, w.name, p.username"
    ).fetchall():
        aliases.setdefault(a[1], []).append(AliasResponse(
            id=a[0], identity_id=a[1], workspace_id=a[2],
            player_id=a[3], username=a[4], workspace_name=a[5],
        ))

    # Hands across each identity's aliases, a hand counted once (same rule as _build_identity:
    # the aliases that join a player and a workspace)
    totals = dict(db.execute(
        "SELECT m.identity_id, COUNT(DISTINCT hp.hand_id) "
        "FROM (SELECT DISTINCT pa.identity_id, pa.player_id FROM player_aliases pa "
        "      JOIN players p ON p.id = pa.player_id "
        "      JOIN workspaces w ON w.id = pa.workspace_id) m "
        "JOIN hand_players hp ON hp.player_id = m.player_id "
        "GROUP BY m.identity_id"
    ).fetchall())

    out = []
    for row in rows:
        try:
            tags = json.loads(row[4]) if row[4] else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        als = aliases.get(row[0], [])
        out.append(IdentityResponse(
            id=row[0],
            display_name=row[1],
            notes=row[2],
            color=row[3],
            tags=tags,
            aliases=als,
            total_hands=int(totals.get(row[0], 0)) if als else 0,
            is_single_person=bool(row[6]),
            pinned=bool(row[7]),
            player_count=len(als),
            created_at=row[5],
        ))
    return out


def _csv_field(v: str) -> str:
    if any(c in v for c in ',"\n\r') or v != v.strip():
        return '"' + v.replace('"', '""') + '"'
    return v


@router.get("/identities/export.csv")
def export_identities_csv():
    """One line per member, no header: `alias name, nickname, site, True|False`."""
    db = get_read_cursor()
    rows = db.execute(
        "SELECT i.display_name, p.username, s.name, COALESCE(i.is_single_person, FALSE) "
        "FROM player_identities i "
        "JOIN player_aliases pa ON pa.identity_id = i.id "
        "JOIN players p ON p.id = pa.player_id "
        "LEFT JOIN sites s ON s.id = p.site_id "
        "GROUP BY i.id, i.display_name, p.id, p.username, s.name, i.is_single_person "
        "ORDER BY i.id, p.id"
    ).fetchall()
    lines = [
        ", ".join([_csv_field(r[0]), _csv_field(r[1]), _csv_field(r[2] or ""), "True" if r[3] else "False"])
        for r in rows
    ]
    return Response(
        content="\n".join(lines) + ("\n" if lines else ""),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="aliases.csv"'},
    )


@router.post("/identities/import-csv")
async def import_identities_csv(workspace_id: int = Query(...), file: UploadFile = File(...)):
    """Import `alias name, nickname, site[, True|False]` lines into a workspace.

    Lines need >= 3 fields; an unknown site, or a nickname with no hands in this workspace, or
    a player already in another alias there, is skipped. Lines group by alias name; an existing
    alias with that name gets the members added (merge); single person if any line says True.
    Returns { aliases: groups with at least one valid line, players: members newly linked,
    skipped_lines }.
    """
    text = (await file.read()).decode("utf-8-sig", errors="replace")
    with db_lock():
        db = get_db()
        if not db.execute("SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]).fetchone():
            raise HTTPException(status_code=404, detail="Workspace not found")
        site_ids = {name.lower(): sid for sid, name in db.execute("SELECT id, name FROM sites").fetchall()}

        skipped = 0
        groups: dict[str, dict] = {}
        try:
            for fields in csv.reader(io.StringIO(text), skipinitialspace=True):
                if not fields or all(not f.strip() for f in fields):
                    continue
                fields = [f.strip() for f in fields]
                if len(fields) < 3 or not fields[0] or not fields[1]:
                    skipped += 1
                    continue
                site_id = site_ids.get(fields[2].lower())
                player = db.execute(
                    "SELECT p.id FROM players p WHERE p.site_id = ? AND p.username = ? "
                    "AND EXISTS (SELECT 1 FROM hand_players hp WHERE hp.player_id = p.id AND hp.workspace_id = ?)",
                    [site_id, fields[1], workspace_id],
                ).fetchone() if site_id is not None else None
                if player is None:
                    skipped += 1
                    continue
                g = groups.setdefault(fields[0], {"players": [], "single": False})
                g["players"].append(player[0])
                if len(fields) > 3 and fields[3].lower() == "true":
                    g["single"] = True
        except csv.Error as e:
            raise HTTPException(status_code=422, detail=f"Invalid CSV: {e}")

        from app.marked_hands import txn
        with txn(db):
            n_players = 0
            for name, g in groups.items():
                row = db.execute(
                    "SELECT id FROM player_identities WHERE display_name = ? ORDER BY id LIMIT 1", [name]
                ).fetchone()
                if row:
                    identity_id = row[0]
                else:
                    identity_id = db.execute("SELECT nextval('seq_identities')").fetchone()[0]
                    db.execute("INSERT INTO player_identities (id, display_name, tags) VALUES (?, ?, '[]')",
                               [identity_id, name])
                if g["single"]:
                    db.execute("UPDATE player_identities SET is_single_person = TRUE WHERE id = ?", [identity_id])
                for pid in dict.fromkeys(g["players"]):
                    taken = db.execute(
                        "SELECT identity_id FROM player_aliases WHERE workspace_id = ? AND player_id = ?",
                        [workspace_id, pid],
                    ).fetchone()
                    if taken:
                        if taken[0] != identity_id:
                            skipped += 1
                        continue
                    alias_id = db.execute("SELECT nextval('seq_aliases')").fetchone()[0]
                    db.execute(
                        "INSERT INTO player_aliases (id, identity_id, workspace_id, player_id) VALUES (?, ?, ?, ?)",
                        [alias_id, identity_id, workspace_id, pid],
                    )
                    n_players += 1
        return {"aliases": len(groups), "players": n_players, "skipped_lines": skipped}


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
        if body.is_single_person is not None:
            updates.append("is_single_person = ?")
            params.append(body.is_single_person)
        if body.pinned is not None:
            updates.append("pinned = ?")
            params.append(body.pinned)

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
    """Compute aggregated stats across multiple player IDs.

    Deduplicates by (hand_id, player_id) so the same physical hand imported
    into multiple workspaces is only counted once.  We pick one row per
    (hand_id, player_id) via MIN(workspace_id), then run the standard
    aggregation query over those unique rows.
    """
    from app.stats_engine import _compute_stats_from_query, _AGG_SQL

    ph = ",".join("?" for _ in player_ids)

    # Build WHERE parts for the dedup CTE (filter on hand_players + hands)
    where_parts = [f"hp.player_id IN ({ph})"]
    params: list = list(player_ids)

    if position:
        where_parts.append(f"{POS_SQL} = ?")
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
        where_parts.append(DATE_TO_SQL)
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    # CTE picks one workspace per (hand_id, player_id) to deduplicate
    # across workspaces that contain the same physical hand.
    dedup_cte = f"""WITH dedup AS (
        SELECT hp.hand_id, hp.player_id, MIN(hp.workspace_id) AS ws
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {where_sql}
        GROUP BY hp.hand_id, hp.player_id
    )
    """

    # The main aggregation re-joins hand_players using the dedup key
    # so only one row per (hand_id, player_id) is aggregated.
    dedup_where = (
        "EXISTS (SELECT 1 FROM dedup d "
        "WHERE d.hand_id = hp.hand_id AND d.player_id = hp.player_id "
        "AND d.ws = hp.workspace_id)"
    )
    full_sql = dedup_cte + _AGG_SQL.format(where=dedup_where)

    # params are used once (in the CTE); the main query references the CTE
    return _compute_stats_from_query(db, dedup_where, params, sql_override=full_sql)
