"""Hero accounts: auto-detection and resolution of the active hero per workspace.

A workspace has a list of hero accounts (`hero_accounts`): manual ones typed
by the user and auto-detected ones. The "active" hero used by every stats
endpoint is the account with the most hands in the workspace (Hand2Note's
"most relevant player"). Unlike Hand2Note, manual accounts with hands win over
detected ones, so typing a nickname is how the user overrides detection, and
detected accounts are ignored while auto-detection is off.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

MAX_AUTO_ACCOUNTS = 127


@dataclass(frozen=True)
class HeroRef:
    player_id: int
    username: str
    site_code: str
    site_name: str
    hand_count: int


_cache: dict[int, HeroRef | None] = {}
_cache_lock = threading.Lock()
# Bumped on every invalidation, so a resolve that raced an import doesn't
# store a result computed before the import finished.
_cache_gen = 0


def invalidate_hero_cache(workspace_id: int | None = None) -> None:
    global _cache_gen
    with _cache_lock:
        _cache_gen += 1
        if workspace_id is None:
            _cache.clear()
        else:
            _cache.pop(workspace_id, None)


def detect_heroes(db, workspace_id: int | None = None) -> int:
    """Add auto-detected hero accounts; returns the number of new accounts.

    Hand2Note's rule: the only player in a hand whose hole cards are known is
    the hero. Parsers store showdown cards in the same columns (card1/card2),
    so hands with a showdown have 2+ known players and are skipped. GG, PS and
    the other sites show dealt cards only for the hero, so every hand where the
    hero did not show down qualifies. Works for every site and for hands
    imported from a Hand2Note database. Each scan replaces the workspace's
    auto accounts, so a rebuild drops stale ones and at most 127 are kept
    (those with the most qualifying hands). Rescans the whole workspace.
    """
    ws_filter = "AND hp.workspace_id = ?" if workspace_id is not None else ""
    params = [workspace_id] if workspace_id is not None else []
    before = db.execute("SELECT COUNT(*) FROM hero_accounts").fetchone()[0]
    db.execute(f"""
        DELETE FROM hero_accounts
        WHERE source = 'auto'
          AND workspace_id IN (SELECT id FROM workspaces WHERE hero_auto_detect)
          {"AND workspace_id = ?" if workspace_id is not None else ""}
    """, params)
    db.execute(f"""
        INSERT OR IGNORE INTO hero_accounts (workspace_id, site_id, username, source)
        SELECT workspace_id, site_id, username, 'auto' FROM (
            SELECT c.workspace_id, p.site_id, p.username,
                   ROW_NUMBER() OVER (
                       PARTITION BY c.workspace_id ORDER BY c.n DESC, p.username
                   ) AS rn
            FROM (
                SELECT workspace_id, player_id, COUNT(*) AS n FROM (
                    SELECT hp.workspace_id, hp.hand_id, MIN(hp.player_id) AS player_id
                    FROM hand_players hp
                    JOIN workspaces w ON w.id = hp.workspace_id
                    WHERE hp.card1 IS NOT NULL AND w.hero_auto_detect {ws_filter}
                    GROUP BY hp.workspace_id, hp.hand_id
                    HAVING COUNT(*) = 1
                ) GROUP BY workspace_id, player_id
            ) c
            JOIN players p ON p.id = c.player_id
        ) WHERE rn <= {MAX_AUTO_ACCOUNTS}
    """, params)
    after = db.execute("SELECT COUNT(*) FROM hero_accounts").fetchone()[0]
    invalidate_hero_cache(workspace_id)
    return after - before


def resolve_hero(db, workspace_id: int) -> HeroRef | None:
    with _cache_lock:
        if workspace_id in _cache:
            return _cache[workspace_id]
        gen = _cache_gen
    ref = _resolve(db, workspace_id)
    with _cache_lock:
        if gen == _cache_gen:
            _cache[workspace_id] = ref
    return ref


def _resolve(db, workspace_id: int) -> HeroRef | None:
    row = db.execute("""
        SELECT p.id, p.username, s.code, s.name, COUNT(hp.id) AS n
        FROM (
            SELECT site_id, username,
                   MIN(CASE WHEN source = 'manual' THEN 0 ELSE 1 END) AS pri
            FROM hero_accounts h
            WHERE workspace_id = ?
              AND (source = 'manual'
                   OR (SELECT hero_auto_detect FROM workspaces WHERE id = h.workspace_id))
            GROUP BY site_id, username
        ) a
        JOIN players p ON p.site_id = a.site_id AND p.username = a.username
        JOIN sites s ON s.id = p.site_id
        JOIN hand_players hp ON hp.player_id = p.id AND hp.workspace_id = ?
        GROUP BY p.id, p.username, s.code, s.name, a.pri
        ORDER BY a.pri, n DESC, p.username
        LIMIT 1
    """, [workspace_id, workspace_id]).fetchone()
    if not row:
        # No account has hands: fall back to the busiest player (as H2N does).
        row = db.execute("""
            SELECT p.id, p.username, s.code, s.name, COUNT(*) AS n
            FROM hand_players hp
            JOIN players p ON p.id = hp.player_id
            JOIN sites s ON s.id = p.site_id
            WHERE hp.workspace_id = ?
            GROUP BY p.id, p.username, s.code, s.name
            ORDER BY n DESC, p.username
            LIMIT 1
        """, [workspace_id]).fetchone()
    if not row:
        return None
    return HeroRef(int(row[0]), row[1], row[2], row[3], int(row[4]))


def list_accounts(db, workspace_id: int) -> list[dict]:
    rows = db.execute("""
        SELECT s.code, s.name, a.username, a.source,
               (SELECT COUNT(*) FROM hand_players hp
                WHERE hp.workspace_id = a.workspace_id AND hp.player_id = p.id) AS n
        FROM hero_accounts a
        JOIN sites s ON s.id = a.site_id
        LEFT JOIN players p ON p.site_id = a.site_id AND p.username = a.username
        WHERE a.workspace_id = ?
        ORDER BY s.id, CASE WHEN a.source = 'manual' THEN 0 ELSE 1 END, a.username
    """, [workspace_id]).fetchall()
    return [
        {"site": r[0], "site_name": r[1], "username": r[2], "source": r[3],
         "hand_count": int(r[4] or 0)}
        for r in rows
    ]


def add_manual_account(db, workspace_id: int, site_code: str, username: str) -> bool:
    """Add one manual account; False if the site code is unknown or name blank."""
    username = (username or "").strip()
    site = db.execute("SELECT id FROM sites WHERE code = ?", [site_code]).fetchone()
    if not site or not username:
        return False
    db.execute(
        "INSERT OR IGNORE INTO hero_accounts (workspace_id, site_id, username, source) "
        "VALUES (?, ?, ?, 'manual')",
        [workspace_id, site[0], username],
    )
    invalidate_hero_cache(workspace_id)
    return True


def migrate_hero_accounts(conn) -> None:
    """One-time migration (settings key hero_accounts_v1): legacy workspace
    hero -> manual account (only if it has hands), then auto-detect for all."""
    if conn.execute("SELECT 1 FROM settings WHERE key = 'hero_accounts_v1'").fetchone():
        return
    conn.execute("""
        INSERT OR IGNORE INTO hero_accounts (workspace_id, site_id, username, source)
        SELECT w.id, s.id, w.hero_username, 'manual'
        FROM workspaces w
        JOIN sites s ON s.code = w.hero_site
        JOIN players p ON p.site_id = s.id AND p.username = w.hero_username
        WHERE EXISTS (
            SELECT 1 FROM hand_players hp
            WHERE hp.player_id = p.id AND hp.workspace_id = w.id
        )
    """)
    detect_heroes(conn, None)
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('hero_accounts_v1', '1')")
