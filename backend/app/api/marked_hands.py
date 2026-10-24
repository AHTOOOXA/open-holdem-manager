"""Tag catalogue + marked hands endpoints. Contract: frontend/src/lib/marked/types.ts."""

from __future__ import annotations

import json
from typing import Literal, Optional

from fastapi import APIRouter, File, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, field_validator

from app import marked_hands as mh
from app.db import db_lock, get_db, get_read_cursor
from app.models import TagRef

router = APIRouter()

TagColor = Literal["tag-1", "tag-2", "tag-3", "tag-4", "tag-5", "tag-6", "tag-7", "tag-8", "tag-9"]


class TagDef(BaseModel):
    id: int
    name: str
    color: TagColor
    position: int


def _clean_name(v):
    if v is None:
        return v
    v = v.strip()
    if not 1 <= len(v) <= mh.MAX_NAME:
        raise ValueError(f"name must be 1-{mh.MAX_NAME} characters")
    return v


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = None
    color: Optional[TagColor] = None

    @field_validator("name")
    @classmethod
    def _name(cls, v):
        return _clean_name(v)


class TagPatch(TagCreate):
    pass


class MoveBody(BaseModel):
    direction: Literal["up", "down"]


class MarkBody(BaseModel):
    player_id: Optional[int] = None
    tag_ids: Optional[list[int]] = None


class MarkState(BaseModel):
    hand_id: str
    player_id: int
    marked: bool
    tags: list[TagRef] = []


class UnmarkBody(BaseModel):
    tag_ids: Optional[list[int]] = None


class UnmarkResult(BaseModel):
    unmarked: int


class MarkedImportResult(BaseModel):
    imported: int = 0
    duplicates: int = 0
    marked: int = 0
    errors: int = 0


# ── tag catalogue ──────────────────────────────────────────────────────────────────────────


@router.get("/tag-defs", response_model=list[TagDef])
def list_tag_defs():
    return mh.list_tags(get_read_cursor())


@router.post("/tag-defs", response_model=TagDef)
def create_tag_def(body: TagCreate | None = None):
    body = body or TagCreate()
    with db_lock():
        db = get_db()
        with mh.txn(db):
            tid = mh.create_tag(db, body.name or mh.NEW_TAG_NAME, body.color or mh.NEW_TAG_COLOR)
        return mh.get_tag(db, tid)


def _require_tag(db, tag_id: int) -> dict:
    t = mh.get_tag(db, tag_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return t


@router.patch("/tag-defs/{tag_id}", response_model=TagDef)
def update_tag_def(tag_id: int, body: TagPatch):
    with db_lock():
        db = get_db()
        _require_tag(db, tag_id)
        with mh.txn(db):
            if body.name is not None:
                db.execute("UPDATE tag_defs SET name = ? WHERE id = ?", [body.name, tag_id])
            if body.color is not None:
                db.execute("UPDATE tag_defs SET color = ? WHERE id = ?", [body.color, tag_id])
        return mh.get_tag(db, tag_id)


@router.delete("/tag-defs/{tag_id}", status_code=204)
def delete_tag_def(tag_id: int):
    with db_lock():
        db = get_db()
        _require_tag(db, tag_id)
        with mh.txn(db):
            mh.delete_tags(db, [tag_id])
    return Response(status_code=204)


@router.post("/tag-defs/{tag_id}/move", response_model=list[TagDef])
def move_tag_def(tag_id: int, body: MoveBody):
    with db_lock():
        db = get_db()
        _require_tag(db, tag_id)
        with mh.txn(db):
            mh.move_tag(db, tag_id, body.direction)
        return mh.list_tags(db)


@router.post("/tag-defs/reset", response_model=list[TagDef])
def reset_tag_defs():
    with db_lock():
        db = get_db()
        with mh.txn(db):
            mh.reset_tags(db)
        return mh.list_tags(db)


# ── marking ────────────────────────────────────────────────────────────────────────────────


def _resolve_player(db, workspace_id: int, hand_id: str, player_id: int | None) -> int:
    if not db.execute("SELECT 1 FROM hands WHERE id = ? AND workspace_id = ?",
                      [hand_id, workspace_id]).fetchone():
        raise HTTPException(status_code=404, detail="Hand not found")
    if player_id is not None:
        if not db.execute(
            "SELECT 1 FROM hand_players WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
            [workspace_id, hand_id, player_id],
        ).fetchone():
            raise HTTPException(status_code=404, detail="Player not in this hand")
        return player_id
    pid = mh.pick_players(db, workspace_id, [hand_id], fallback=False).get(hand_id)
    if pid is None:
        raise HTTPException(status_code=404, detail="The hero did not play this hand")
    return pid


def _state(db, workspace_id: int, hand_id: str, player_id: int) -> MarkState:
    marked, tags = mh.marks_for(db, workspace_id, player_id, [hand_id])
    return MarkState(hand_id=hand_id, player_id=player_id, marked=hand_id in marked,
                     tags=tags.get(hand_id, []))


@router.put("/hands/{hand_id}/mark", response_model=MarkState)
def put_mark(hand_id: str, body: MarkBody | None = None, workspace_id: int = Query(1)):
    body = body or MarkBody()
    with db_lock():
        db = get_db()
        pid = _resolve_player(db, workspace_id, hand_id, body.player_id)
        tag_ids: list[int] | None = None
        if body.tag_ids is not None:
            tag_ids = list(dict.fromkeys(body.tag_ids))
            if tag_ids:
                known = {r[0] for r in db.execute(
                    "SELECT id FROM tag_defs WHERE id IN (SELECT UNNEST(?::INTEGER[]))", [tag_ids]
                ).fetchall()}
                unknown = [t for t in tag_ids if t not in known]
                if unknown:
                    raise HTTPException(status_code=422, detail=f"Unknown tag ids: {unknown}")
        with mh.txn(db):
            mh.mark(db, workspace_id, hand_id, pid)
            if tag_ids is not None:
                mh.set_tags(db, workspace_id, hand_id, pid, tag_ids)
        return _state(db, workspace_id, hand_id, pid)


@router.delete("/hands/{hand_id}/mark", status_code=204)
def delete_mark(hand_id: str, workspace_id: int = Query(1), player_id: Optional[int] = Query(None)):
    with db_lock():
        db = get_db()
        pid = _resolve_player(db, workspace_id, hand_id, player_id)
        with mh.txn(db):
            mh.unmark(db, workspace_id, hand_id, pid)
    return Response(status_code=204)


@router.post("/marked-hands/unmark", response_model=UnmarkResult)
def unmark_hands(body: UnmarkBody | None = None, workspace_id: int = Query(1)):
    tag_ids = list(dict.fromkeys((body.tag_ids if body else None) or []))
    with db_lock():
        db = get_db()
        with mh.txn(db):
            n = mh.unmark_all(db, workspace_id, tag_ids or None)
    return UnmarkResult(unmarked=n)


# ── export / import ────────────────────────────────────────────────────────────────────────


@router.get("/marked-hands/export")
def export_marked(workspace_id: int = Query(1), format: Literal["json", "txt"] = Query("json"),
                  tag_ids: Optional[str] = Query(None, description="Comma list; any of (OR)")):
    db = get_read_cursor()
    ids = mh.parse_id_list(tag_ids)
    clauses, params = mh.list_filter_sql(None, ids or None, "m.hand_id", "m.workspace_id",
                                         "m.player_id")
    where = "".join(f" AND {c}" for c in clauses)
    rows = db.execute(f"""
        SELECT m.hand_id, m.player_id, p.username, s.code, h.raw_text
        FROM marked_hands m
        JOIN hands h ON h.id = m.hand_id AND h.workspace_id = m.workspace_id
        JOIN players p ON p.id = m.player_id
        LEFT JOIN sites s ON s.id = h.site_id
        WHERE m.workspace_id = ? {where}
        ORDER BY h.played_at, m.hand_id, p.username
    """, [workspace_id, *params]).fetchall()

    if format == "txt":
        seen: set[str] = set()
        texts = []
        for hid, _, _, _, raw in rows:
            if hid in seen or not raw:
                continue
            seen.add(hid)
            texts.append(raw.strip())
        body = "\n\n\n".join(texts) + ("\n" if texts else "")
        return Response(content=body.encode("utf-8"), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="Marked Hands.txt"'})

    by_player: dict[int, list[str]] = {}
    for hid, pid, *_ in rows:
        by_player.setdefault(pid, []).append(hid)
    tag_map: dict[tuple[str, int], list[dict]] = {}
    for pid, hids in by_player.items():
        _, tags = mh.marks_for(db, workspace_id, pid, hids)
        for hid, lst in tags.items():
            tag_map[(hid, pid)] = lst
    out = {
        "format": "ohm-marked-hands",
        "version": 1,
        "hands": [
            {
                "site": site or "",
                "hand_id": hid,
                "player": username,
                "tags": [{"name": t["name"], "color": t["color"]}
                         for t in tag_map.get((hid, pid), [])],
                "hand_text": raw or "",
            }
            for hid, pid, username, site, raw in rows
        ],
    }
    return Response(content=json.dumps(out, ensure_ascii=False, indent=1).encode("utf-8"),
                    media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="Marked Hands.json"'})


def _split_ids(texts: list[str]) -> tuple[list[str | None], int]:
    """Hand ids of every hand in the given file contents (the import pipeline's splitting),
    and the number of contents no parser recognises."""
    from app.parsers import detect_parser
    ids: list[str | None] = []
    unknown = 0
    for content in texts:
        parser = detect_parser(content[:500])
        if parser is None:
            unknown += 1
            continue
        for h in parser.split_hands(content):
            h = h.strip()
            if h:
                ids.append(parser.extract_hand_id(h))
    return ids, unknown


MAX_MARKED_UPLOAD_BYTES = 500 * 1024 * 1024


@router.post("/marked-hands/import", response_model=MarkedImportResult)
async def import_marked(files: list[UploadFile] = File(...), workspace_id: int = Query(1)):
    from app.api.import_hands import _process_hands, _read_uploads

    result = MarkedImportResult()
    plain: list[tuple[str, bytes]] = []
    entries: list[dict] = []
    total_bytes = 0
    for f in files:
        name = (f.filename or "").lower()
        raw = await f.read()
        total_bytes += len(raw)
        if total_bytes > MAX_MARKED_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Upload too large (limit 500 MB)")
        if name.endswith(".json"):
            try:
                doc = json.loads(raw.decode("utf-8-sig"))
                if not isinstance(doc, dict) or doc.get("format") != "ohm-marked-hands" \
                        or not isinstance(doc.get("hands"), list):
                    raise ValueError("not an OHM marked hands file")
            except (ValueError, UnicodeDecodeError, RecursionError):
                result.errors += 1
                continue
            for e in doc["hands"]:
                if isinstance(e, dict) and isinstance(e.get("hand_text"), str) and e["hand_text"].strip():
                    entries.append(e)
                else:
                    result.errors += 1
        elif name.endswith(".txt") or name.endswith(".zip"):
            plain.append((name, raw))
        else:
            result.errors += 1

    plain_texts = _read_uploads(plain)
    json_texts = [e["hand_text"].strip() for e in entries]
    json_ids: list[str | None] = []
    for t in json_texts:  # one hand per entry
        ids, unknown = _split_ids([t])
        json_ids.append(ids[0] if ids and not unknown else None)
    split, unknown = _split_ids(plain_texts)
    plain_ids = list(dict.fromkeys(h for h in split if h is not None))
    result.errors += unknown + sum(1 for h in json_ids if h is None)

    with db_lock():
        db = get_db()
        texts = plain_texts + [t for t, h in zip(json_texts, json_ids) if h is not None]
        if texts:
            r = _process_hands(db, texts, workspace_id=workspace_id)
            result.imported += r.imported
            result.duplicates += r.duplicates
            result.errors += r.errors

        def existing(ids: list[str]) -> set[str]:
            if not ids:
                return set()
            return {row[0] for row in db.execute(
                "SELECT id FROM hands WHERE workspace_id = ? AND id IN (SELECT UNNEST(?::VARCHAR[]))",
                [workspace_id, ids]).fetchall()}

        with mh.txn(db):
            # JSON entries: the named player, tags by name (created when missing)
            valid = [(e, hid) for e, hid in zip(entries, json_ids) if hid is not None]
            have = existing([hid for _, hid in valid])
            hero_pick = mh.pick_players(db, workspace_id, list(have), fallback=True)
            tag_by_name: dict[str, int] = {}
            for t in mh.list_tags(db):
                tag_by_name.setdefault(t["name"].strip().lower(), t["id"])
            for e, hid in valid:
                if hid not in have:
                    continue
                pid = None
                player = e.get("player")
                if isinstance(player, str) and player:
                    row = db.execute(
                        "SELECT hp.player_id FROM hand_players hp JOIN players p ON p.id = hp.player_id "
                        "WHERE hp.workspace_id = ? AND hp.hand_id = ? AND p.username = ? LIMIT 1",
                        [workspace_id, hid, player]).fetchone()
                    pid = row[0] if row else None
                if pid is None:
                    pid = hero_pick.get(hid)
                if pid is None:
                    continue
                tids: list[int] = []
                for t in e.get("tags") or []:
                    if not isinstance(t, dict) or not isinstance(t.get("name"), str):
                        continue
                    tname = t["name"].strip()[:mh.MAX_NAME]
                    if not tname:
                        continue
                    tid = tag_by_name.get(tname.lower())
                    if tid is None:
                        color = t.get("color") if t.get("color") in mh.TAG_COLORS else mh.NEUTRAL_COLOR
                        tid = mh.create_tag(db, tname, color)
                        tag_by_name[tname.lower()] = tid
                    tids.append(tid)
                if mh.mark(db, workspace_id, hid, pid):
                    result.marked += 1
                mh.add_tags(db, workspace_id, hid, pid, tids)

            # Plain hand histories: the hero (fallbacks as in the migration), no tags
            have = existing(plain_ids)
            picks = mh.pick_players(db, workspace_id, [h for h in plain_ids if h in have], fallback=True)
            for hid in plain_ids:
                pid = picks.get(hid)
                if pid is not None and mh.mark(db, workspace_id, hid, pid):
                    result.marked += 1
    return result
