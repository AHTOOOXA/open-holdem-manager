"""Statistics dashboards store: GET/PUT /api/statistics/dashboards?workspace_id=.

One document per workspace (folder/dashboard tree + view config), stored as JSON in the
`settings` table under `statistics_dashboards.<workspace_id>`. Contract:
frontend/src/lib/statistics/types.ts.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal, Optional, Union

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.db import db_lock, get_db, get_read_cursor
from app.general_filters import validate_plain_steps

router = APIRouter()

KEY_PREFIX = "statistics_dashboards."
MAX_NAME = 200


def settings_key(workspace_id: int) -> str:
    return f"{KEY_PREFIX}{workspace_id}"


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    player_id: Optional[int] = None
    filters: list[dict] = []
    profile_id: str = "default"


class Folder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    kind: Literal["folder"]
    name: str
    parent_id: Optional[int] = None


class Dashboard(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    kind: Literal["dashboard"]
    name: str
    parent_id: Optional[int] = None
    definition: Definition


Node = Annotated[Union[Folder, Dashboard], Field(discriminator="kind")]


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_id: Optional[int] = None
    collapsed: bool = False
    tree_width: int = 300


class Doc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[Node]
    config: Config


def seed() -> Doc:
    return Doc(
        nodes=[Dashboard(id=1, kind="dashboard", name="new dashboard", parent_id=None,
                         definition=Definition(player_id=None, filters=[], profile_id="default"))],
        config=Config(selected_id=1, collapsed=False, tree_width=300),
    )


def tree_order(nodes: list) -> list:
    """Depth-first, each level folders first then dashboards, names by code point."""
    by_parent: dict[Optional[int], list] = {}
    for n in nodes:
        by_parent.setdefault(n.parent_id, []).append(n)
    out: list = []

    def walk(parent: Optional[int]) -> None:
        kids = sorted(by_parent.get(parent, []), key=lambda n: (n.kind != "folder", n.name))
        for n in kids:
            out.append(n)
            if n.kind == "folder":
                walk(n.id)

    walk(None)
    return out


def _fail(msg: str):
    raise HTTPException(status_code=422, detail=msg)


def validate(doc: Doc) -> Doc:
    """Check the rules (422) and fix selected_id; returns the document to store."""
    by_id: dict[int, object] = {}
    for n in doc.nodes:
        if n.id in by_id:
            _fail(f"duplicate id {n.id}")
        by_id[n.id] = n
        n.name = n.name.strip()
        if not n.name or len(n.name) > MAX_NAME:
            _fail(f"name must be 1-{MAX_NAME} characters")
    for n in doc.nodes:
        if n.parent_id is not None:
            p = by_id.get(n.parent_id)
            if p is None:
                _fail(f"node {n.id}: parent {n.parent_id} does not exist")
            if p.kind != "folder":
                _fail(f"node {n.id}: parent {n.parent_id} is not a folder")
        seen = {n.id}
        cur = n.parent_id
        while cur is not None:
            if cur in seen:
                _fail(f"node {n.id}: cycle in the tree")
            seen.add(cur)
            cur = by_id[cur].parent_id
        if n.kind == "dashboard":
            try:
                validate_plain_steps(n.definition.filters)
            except ValueError as e:
                _fail(f"dashboard {n.id}: invalid filters: {e}")
    dashboards = [n for n in doc.nodes if n.kind == "dashboard"]
    if not dashboards:
        _fail("at least one dashboard is required")
    if not 280 <= doc.config.tree_width <= 1000:
        _fail("tree_width must be between 280 and 1000")
    sel = by_id.get(doc.config.selected_id) if doc.config.selected_id is not None else None
    if sel is None or sel.kind != "dashboard":
        first = next(n for n in tree_order(doc.nodes) if n.kind == "dashboard")
        doc.config.selected_id = first.id
    return doc


def _load(db, workspace_id: int) -> Doc:
    row = db.execute("SELECT value FROM settings WHERE key = ?",
                     [settings_key(workspace_id)]).fetchone()
    if row:
        try:
            return validate(Doc.model_validate(json.loads(row[0])))
        except Exception:  # unreadable or invalid stored data: start over
            pass
    return seed()


def _check_workspace(db, workspace_id: int) -> None:
    if not db.execute("SELECT 1 FROM workspaces WHERE id = ?", [workspace_id]).fetchone():
        raise HTTPException(status_code=404, detail="Workspace not found")


@router.get("/statistics/dashboards", response_model=Doc)
def get_dashboards(workspace_id: int = Query(1)):
    db = get_read_cursor()
    _check_workspace(db, workspace_id)
    return _load(db, workspace_id)


@router.put("/statistics/dashboards", response_model=Doc)
def put_dashboards(doc: Doc, workspace_id: int = Query(1)):
    doc = validate(doc)
    with db_lock():
        db = get_db()
        _check_workspace(db, workspace_id)
        db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            [settings_key(workspace_id), doc.model_dump_json()],
        )
    return doc
