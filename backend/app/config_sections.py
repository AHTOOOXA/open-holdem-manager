"""Configuration sections stored as JSON in the `settings` table (`config.<section>` keys).

Contract: frontend/src/lib/config/types.ts. Sections: stat_appearance, game_types,
color_markers, auto_import (frontend/src/lib/import/types.ts section 2). Global (not per
workspace). A missing / unreadable row means the default.

Also hosts the rebuild fingerprint: sha256(STAT_VERSION + canonical json of game_types).
It is stored (settings `rebuild_fingerprint`) when a full rebuild completes; GET /api/health
reports `rebuild_required` when the stored value differs from the current one.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, field_validator

FINGERPRINT_KEY = "rebuild_fingerprint"
TagColor = Literal["tag-1", "tag-2", "tag-3", "tag-4", "tag-5", "tag-6", "tag-7", "tag-8", "tag-9"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatAppearance(_Strict):
    one_decimal_below: Annotated[float, Field(ge=0, le=100)] = 10
    show_99_for_100: Annotated[bool, Field(strict=True)] = True
    leading_zero: Annotated[bool, Field(strict=True)] = False
    shorten_amounts: Annotated[bool, Field(strict=True)] = True
    show_sample_below: Annotated[int, Field(ge=1, strict=True)] = 15
    dim_below: Annotated[int, Field(ge=1, strict=True)] = 10
    vs_user_substitute_above: Annotated[int, Field(ge=0, strict=True)] = 50


class RegRule(_Strict):
    min_hands: Annotated[int, Field(ge=0, strict=True)] = 10
    vpip: tuple[float, float] = (0, 35)
    pfr: tuple[float, float] = (0, 30)
    vpip_minus_pfr: tuple[float, float] = (0, 10)
    limp: tuple[float, float] = (0, 20)
    auto_reg_hands: Annotated[int, Field(ge=0, strict=True)] = 20000

    @field_validator("vpip", "pfr", "vpip_minus_pfr", "limp")
    @classmethod
    def _check_range(cls, v: tuple[float, float]):
        lo, hi = v
        if not (0 <= lo <= 100 and 0 <= hi <= 100):
            raise ValueError("range bounds must be within 0-100")
        if lo > hi:
            raise ValueError("range lower bound must not exceed the upper bound")
        return v


class GameTypesConfig(_Strict):
    reg_rule: RegRule = RegRule()


class ColorMarker(_Strict):
    id: Annotated[int, Field(strict=True)]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    color: TagColor
    is_regular: Annotated[bool, Field(strict=True)]


def _validate_markers(markers: list[ColorMarker]) -> list[ColorMarker]:
    ids = [m.id for m in markers]
    if len(set(ids)) != len(ids):
        raise ValueError("marker ids must be unique")
    return markers


DEFAULT_MARKERS = [
    {"id": 1, "name": "Fish", "color": "tag-3", "is_regular": False},
    {"id": 2, "name": "Reg", "color": "tag-7", "is_regular": True},
]


def _path_key(path: str) -> str:
    """Comparison key of a folder path: case-insensitive on macOS / Windows."""
    return path.casefold() if sys.platform in ("darwin", "win32") else path


def _clean_dir(path: str) -> str:
    path = path.strip()
    if not path or not os.path.isabs(path):
        raise ValueError(f"folder must be an absolute path: {path!r}")
    return os.path.normpath(path)


class AutoImportConfig(_Strict):
    enabled: Annotated[bool, Field(strict=True)] = False
    workspace_id: Annotated[int, Field(ge=1, strict=True)] | None = None
    folders: list[str] = []
    archive_enabled: Annotated[bool, Field(strict=True)] = False
    archive_dir: str | None = None

    @field_validator("folders")
    @classmethod
    def _check_folders(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for raw in v:
            path = _clean_dir(raw)
            key = _path_key(path)
            if key not in seen:
                seen.add(key)
                out.append(path)
        return out

    @field_validator("archive_dir")
    @classmethod
    def _check_archive_dir(cls, v: str | None) -> str | None:
        return None if v is None or not v.strip() else _clean_dir(v)


def _check_auto_import_workspace(db, value: AutoImportConfig) -> None:
    if value.workspace_id is not None and db.execute(
        "SELECT 1 FROM workspaces WHERE id = ?", [value.workspace_id]
    ).fetchone() is None:
        raise ValueError(f"workspace {value.workspace_id} does not exist")


class _Section:
    def __init__(self, name: str, adapter: TypeAdapter, default: Any, post=None, db_check=None):
        self.name = name
        self.adapter = adapter
        self.default = default  # JSON-able
        self.post = post
        self.db_check = db_check  # (db, validated value) -> None, raises ValueError; on PUT only

    def parse(self, raw: Any, db=None) -> Any:
        v = self.adapter.validate_python(raw)
        if self.post:
            self.post(v)
        if db is not None and self.db_check:
            self.db_check(db, v)
        return self.adapter.dump_python(v, mode="json")


SECTIONS: dict[str, _Section] = {
    "stat_appearance": _Section("stat_appearance", TypeAdapter(StatAppearance),
                                StatAppearance().model_dump(mode="json")),
    "game_types": _Section("game_types", TypeAdapter(GameTypesConfig),
                           GameTypesConfig().model_dump(mode="json")),
    "color_markers": _Section("color_markers", TypeAdapter(list[ColorMarker]),
                              DEFAULT_MARKERS, post=_validate_markers),
    "auto_import": _Section("auto_import", TypeAdapter(AutoImportConfig),
                            AutoImportConfig().model_dump(mode="json"),
                            db_check=_check_auto_import_workspace),
}


def _key(section: str) -> str:
    return f"config.{section}"


def get_value(db, section: str) -> Any:
    """Effective (validated) value of a section; the default when missing or unreadable."""
    sec = SECTIONS[section]
    row = db.execute("SELECT value FROM settings WHERE key = ?", [_key(section)]).fetchone()
    if row is None:
        return json.loads(json.dumps(sec.default))
    try:
        return sec.parse(json.loads(row[0]))
    except Exception:
        return json.loads(json.dumps(sec.default))


def put_value(db, section: str, raw: Any) -> Any:
    """Validate (raises pydantic.ValidationError / ValueError) and store; caller holds the lock."""
    value = SECTIONS[section].parse(raw, db=db)
    db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [_key(section), json.dumps(value)])
    return value


def reset_value(db, section: str) -> Any:
    db.execute("DELETE FROM settings WHERE key = ?", [_key(section)])
    return json.loads(json.dumps(SECTIONS[section].default))


def envelope(db, section: str) -> dict:
    value = get_value(db, section)
    default = json.loads(json.dumps(SECTIONS[section].default))
    return {"value": value, "default": default, "is_default": value == default}


def get_reg_rule(db) -> RegRule:
    return RegRule.model_validate(get_value(db, "game_types")["reg_rule"])


def get_markers(db) -> list[dict]:
    return get_value(db, "color_markers")


# ── Rebuild fingerprint ──────────────────────────────────────────────


def current_fingerprint(db) -> str:
    from app.db import STAT_VERSION
    canon = json.dumps(get_value(db, "game_types"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((str(STAT_VERSION) + canon).encode()).hexdigest()


def store_rebuild_fingerprint(db) -> None:
    db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [FINGERPRINT_KEY, current_fingerprint(db)])


def ensure_rebuild_fingerprint(db) -> None:
    """First run with nothing stored: adopt the current fingerprint (no banner)."""
    if db.execute("SELECT 1 FROM settings WHERE key = ?", [FINGERPRINT_KEY]).fetchone() is None:
        store_rebuild_fingerprint(db)


def rebuild_required(db) -> bool:
    row = db.execute("SELECT value FROM settings WHERE key = ?", [FINGERPRINT_KEY]).fetchone()
    if row is None or row[0] == current_fingerprint(db):
        return False
    return db.execute("SELECT COUNT(*) FROM hands").fetchone()[0] > 0


# ── Colour marker ids: never reused ─────────────────────────────────────────────────────

NEXT_MARKER_ID_KEY = "config.color_markers.next_id"


def reserve_marker_id(db) -> int:
    """Reserve and return a never-used marker id: counter = max(counter, max id in the stored
    value) + 1, persisted. Caller holds the write lock."""
    row = db.execute("SELECT value FROM settings WHERE key = ?", [NEXT_MARKER_ID_KEY]).fetchone()
    try:
        counter = int(row[0]) if row else 0
    except ValueError:
        counter = 0
    nxt = max(counter, max((m["id"] for m in get_markers(db)), default=0)) + 1
    db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [NEXT_MARKER_ID_KEY, str(nxt)])
    return nxt
