"""GET/PUT/DELETE /api/config/{section} and GET /api/system/info (contract: frontend/src/lib/config)."""

import json
import os
from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from app import config_sections as cs
from app.db import DB_PATH, db_lock, get_db, get_read_cursor

router = APIRouter()


def _section(name: str) -> str:
    if name not in cs.SECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown config section: {name}")
    return name


@router.get("/config/color_markers/next-id")
def next_marker_id() -> dict:
    """Reserve the next never-used colour marker id (ids are never reused after deletion)."""
    with db_lock():
        return {"id": cs.reserve_marker_id(get_db())}


@router.get("/config/{section}")
def read_config(section: str) -> dict:
    return cs.envelope(get_read_cursor(), _section(section))


@contextmanager
def _watcher_paused(section: str):
    """auto_import: cancel the watcher tick in progress (it holds the write lock) while the
    new config is written; the next tick uses it. Yields a dict to put old/new values in."""
    change: dict = {"old": None, "new": None}
    if section != "auto_import":
        yield change
        return
    from app import auto_import
    auto_import.pause()
    try:
        yield change
    finally:
        auto_import.resume(change["old"], change["new"])


@router.put("/config/{section}")
def write_config(section: str, payload=Body(...)) -> dict:
    _section(section)
    with _watcher_paused(section) as change, db_lock():
        db = get_db()
        change["old"] = cs.get_value(db, section)
        try:
            change["new"] = cs.put_value(db, section, payload)
        except ValidationError as e:
            raise HTTPException(status_code=422, detail=json.loads(e.json(include_url=False, include_context=False)))
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        return cs.envelope(db, section)


@router.delete("/config/{section}")
def reset_config(section: str) -> dict:
    _section(section)
    with _watcher_paused(section) as change, db_lock():
        db = get_db()
        change["old"] = cs.get_value(db, section)
        change["new"] = cs.reset_value(db, section)
        return cs.envelope(db, section)


@router.get("/system/info")
def system_info() -> dict:
    wal = DB_PATH.with_name(DB_PATH.name + ".wal")
    size = 0
    for p in (DB_PATH, wal):
        try:
            size += os.path.getsize(p)
        except OSError:
            pass
    return {"data_dir": str(DB_PATH.parent), "db_path": str(DB_PATH), "db_size_bytes": size}
