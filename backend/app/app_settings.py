"""App-wide settings (not per workspace), stored in the `settings` key/value table.

Contract: frontend/src/lib/app-settings.ts (`AppSettings`). Values are stored as strings
under the keys below; a missing or unreadable value falls back to its default.

- ``session_max_break_minutes`` (int 1-240, default 10): a hand that starts less than this
  after the current session's end joins the session (app/sessions_h2n.py).
- ``day_start_hour`` (int 0-23, default 0): date presets only, not session splitting.
- ``numeric_date_format`` (bool, default False): session captions as "17-10-2026, 20:10".
"""

from __future__ import annotations

from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

DEFAULTS: dict = {
    "session_max_break_minutes": 10,
    "day_start_hour": 0,
    "numeric_date_format": False,
}

_RANGES = {"session_max_break_minutes": (1, 240), "day_start_hour": (0, 23)}


class AppSettings(BaseModel):
    session_max_break_minutes: int
    day_start_hour: int
    numeric_date_format: bool


class AppSettingsPatch(BaseModel):
    """Partial update; unknown keys and out-of-range / mistyped values are rejected (422)."""

    model_config = ConfigDict(extra="forbid")
    session_max_break_minutes: Optional[Annotated[int, Field(ge=1, le=240, strict=True)]] = None
    day_start_hour: Optional[Annotated[int, Field(ge=0, le=23, strict=True)]] = None
    numeric_date_format: Optional[Annotated[bool, Field(strict=True)]] = None


def _decode(key: str, raw: str | None):
    default = DEFAULTS[key]
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in ("1", "true", "yes")
    try:
        v = int(raw)
    except ValueError:
        return default
    lo, hi = _RANGES[key]
    return v if lo <= v <= hi else default


def _encode(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(int(value))


def get_app_settings(db) -> dict:
    """All app settings with defaults filled in."""
    keys = list(DEFAULTS)
    rows = dict(db.execute(
        f"SELECT key, value FROM settings WHERE key IN ({', '.join('?' for _ in keys)})", keys
    ).fetchall())
    return {k: _decode(k, rows.get(k)) for k in keys}


def max_break_seconds(db) -> int:
    return int(get_app_settings(db)["session_max_break_minutes"]) * 60


def update_app_settings(db, patch: AppSettingsPatch) -> dict:
    """Write the given keys (caller holds the write lock); returns the full settings."""
    for key, value in patch.model_dump(exclude_none=True).items():
        db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [key, _encode(value)])
    return get_app_settings(db)


__all__ = ["AppSettings", "AppSettingsPatch", "DEFAULTS", "get_app_settings",
           "update_app_settings", "max_break_seconds"]
