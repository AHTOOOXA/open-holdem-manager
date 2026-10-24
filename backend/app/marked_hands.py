"""Marked hands: a global, ordered tag catalogue plus per-workspace marks.

Contract: frontend/src/lib/marked/types.ts. A hand is marked for one player
(workspace, hand, player); a marked hand carries zero or more tags from the catalogue.

Tables (created by ensure_schema, called from db.init_schema):
  tag_defs(id, name, color, position)                          global, position 0-based
  marked_hands(workspace_id, hand_id, player_id, marked_at)    PK (workspace_id, hand_id, player_id)
  marked_hand_tags(workspace_id, hand_id, player_id, tag_id, position)

Tag rows of a mark are removed together with the mark, and a deleted tag is removed from
every mark (the hands stay marked), so no stale ids are ever stored.

The old free-text `hand_tags` table is migrated once (settings key `marked_hands_v1`) and
then left alone.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

TAG_COLORS = tuple(f"tag-{i}" for i in range(1, 10))
NEUTRAL_COLOR = "tag-1"
NEW_TAG_NAME = "my tag"
NEW_TAG_COLOR = "tag-7"
MAX_NAME = 60

# OHM's own default catalogue (fresh install and "Reset"), in display order.
DEFAULT_TAGS: tuple[tuple[str, str], ...] = (
    ("mistake", "tag-7"),     # red
    ("bluff", "tag-5"),       # orange
    ("cooler", "tag-4"),      # purple
    ("value", "tag-3"),       # green
    ("study", "tag-2"),       # blue
    ("great play", "tag-9"),  # cyan
)
_PRESET_COLOR = {name: color for name, color in DEFAULT_TAGS}

MIGRATION_KEY = "marked_hands_v1"
UNMIGRATED_KEY = "marked_hands_v1_unmigrated"  # JSON list of tagged hand ids with no player rows
_NEXT_ID_KEY = "tag_defs_next_id"


# ── schema + migration ─────────────────────────────────────────────────────────────────────


def ensure_schema(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tag_defs (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            color VARCHAR NOT NULL,
            position INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marked_hands (
            workspace_id INTEGER NOT NULL,
            hand_id VARCHAR NOT NULL,
            player_id INTEGER NOT NULL,
            marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, hand_id, player_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marked_hand_tags (
            workspace_id INTEGER NOT NULL,
            hand_id VARCHAR NOT NULL,
            player_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (workspace_id, hand_id, player_id, tag_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_marked_hand_tags_tag ON marked_hand_tags(tag_id)")
    migrate_hand_tags(conn)


def migrate_hand_tags(conn) -> None:
    """One-time: old free-text hand_tags → tag_defs + marks. Idempotent (settings flag, and
    every insert skips existing rows). Fresh databases get the default catalogue."""
    if conn.execute("SELECT 1 FROM settings WHERE key = ?", [MIGRATION_KEY]).fetchone():
        return
    rows = conn.execute("""
        SELECT ht.workspace_id, ht.hand_id, TRIM(ht.tag) AS tag, ht.created_at
        FROM hand_tags ht
        JOIN hands h ON h.id = ht.hand_id AND h.workspace_id = ht.workspace_id
        WHERE TRIM(ht.tag) <> ''
        ORDER BY ht.workspace_id, ht.hand_id, ht.created_at NULLS LAST, ht.tag
    """).fetchall()

    if not rows:
        if not conn.execute("SELECT 1 FROM tag_defs LIMIT 1").fetchone():
            _insert_defaults(conn)
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?, '1')", [MIGRATION_KEY])
        return

    logger.info("Migrating %d hand tags to marked hands...", len(rows))
    # Catalogue: preset names first (default order), then the others by first use.
    first_use: dict[str, tuple] = {}
    for ws, hid, tag, created in rows:
        name = tag[:MAX_NAME]
        key = name.lower()
        if key not in first_use:
            first_use[key] = (str(created) if created is not None else "~", name)
    preset_order = {n: i for i, (n, _) in enumerate(DEFAULT_TAGS)}
    ordered = sorted(first_use.items(),
                     key=lambda kv: (preset_order.get(kv[0], len(preset_order)), kv[1][0], kv[0]))
    tag_id_by_key: dict[str, int] = {}
    existing = conn.execute("SELECT id, name FROM tag_defs ORDER BY position, id").fetchall()
    for tid, name in existing:
        tag_id_by_key.setdefault(name.lower(), tid)
    for key, (_, name) in ordered:
        if key in tag_id_by_key:
            continue
        tag_id_by_key[key] = create_tag(conn, name, _PRESET_COLOR.get(key, NEUTRAL_COLOR))

    # Marks: one per (workspace, hand), for the hero's row (fallbacks in pick_player).
    by_hand: dict[tuple[int, str], list[tuple[int, object]]] = {}
    for ws, hid, tag, created in rows:
        lst = by_hand.setdefault((ws, hid), [])
        tid = tag_id_by_key[tag[:MAX_NAME].lower()]
        if all(t != tid for t, _ in lst):
            lst.append((tid, created))
    unmigrated: list[str] = []
    conn.execute("BEGIN")
    try:
        for ws in sorted({ws for ws, _ in by_hand}):
            hids = [hid for w, hid in by_hand if w == ws]
            players = pick_players(conn, ws, hids, fallback=True, use_cache=False)
            for hid in hids:
                pid = players.get(hid)
                if pid is None:
                    unmigrated.append(hid)
                    continue
                tags = by_hand[(ws, hid)]
                stamps = [c for _, c in tags if c is not None]
                conn.execute(
                    "INSERT OR IGNORE INTO marked_hands (workspace_id, hand_id, player_id, marked_at) "
                    "VALUES (?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
                    [ws, hid, pid, min(stamps) if stamps else None],
                )
                for pos, (tid, _) in enumerate(tags):
                    conn.execute(
                        "INSERT OR IGNORE INTO marked_hand_tags "
                        "(workspace_id, hand_id, player_id, tag_id, position) VALUES (?, ?, ?, ?, ?)",
                        [ws, hid, pid, tid, pos],
                    )
        if unmigrated:
            logger.warning("%d tagged hands have no player rows and were not migrated: %s",
                           len(unmigrated), ", ".join(unmigrated[:20]))
            conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                         [UNMIGRATED_KEY, json.dumps(unmigrated)])
        conn.execute("INSERT OR REPLACE INTO settings VALUES (?, '1')", [MIGRATION_KEY])
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    logger.info("Hand tag migration complete: %d marked hands.", len(by_hand))


@contextmanager
def txn(conn):
    """One transaction around a multi-statement write (caller holds the write lock)."""
    conn.execute("BEGIN")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


# ── player choice ──────────────────────────────────────────────────────────────────────────


def _hero_ids(conn, workspace_id: int, use_cache: bool = True) -> tuple[int | None, set[int]]:
    """(active hero player id, all hero-account player ids) of a workspace."""
    from app import heroes
    ref = heroes.resolve_hero(conn, workspace_id) if use_cache else heroes._resolve(conn, workspace_id)
    accounts = {int(r[0]) for r in conn.execute("""
        SELECT p.id FROM hero_accounts a
        JOIN players p ON p.site_id = a.site_id AND p.username = a.username
        WHERE a.workspace_id = ?
          AND (a.source = 'manual'
               OR (SELECT hero_auto_detect FROM workspaces WHERE id = a.workspace_id))
    """, [workspace_id]).fetchall()}
    return (ref.player_id if ref else None), accounts


def pick_players(conn, workspace_id: int, hand_ids: list[str], *, fallback: bool,
                 use_cache: bool = True) -> dict[str, int]:
    """The player to mark in each hand: the active hero's row, else another hero account's
    row. With `fallback`, else the only player with known hole cards, else the lowest seat.
    Hands without such a player (or without players) are missing from the result."""
    if not hand_ids:
        return {}
    active, accounts = _hero_ids(conn, workspace_id, use_cache)
    out: dict[str, int] = {}
    seats: dict[str, list[tuple[int, int, bool]]] = {}
    for i in range(0, len(hand_ids), 1000):
        chunk = hand_ids[i:i + 1000]
        for hid, pid, seat, card in conn.execute(
            "SELECT hand_id, player_id, seat, card1 FROM hand_players "
            "WHERE workspace_id = ? AND hand_id IN (SELECT UNNEST(?::VARCHAR[]))",
            [workspace_id, chunk],
        ).fetchall():
            seats.setdefault(hid, []).append((int(seat), int(pid), card is not None))
    for hid, lst in seats.items():
        lst.sort()
        pids = [p for _, p, _ in lst]
        if active is not None and active in pids:
            out[hid] = active
            continue
        acc = [p for p in pids if p in accounts]
        if acc:
            out[hid] = acc[0]
            continue
        if not fallback:
            continue
        known = [p for _, p, k in lst if k]
        out[hid] = known[0] if len(known) == 1 else lst[0][1]
    return out


# ── tag catalogue ──────────────────────────────────────────────────────────────────────────


def tag_row(r) -> dict:
    return {"id": int(r[0]), "name": r[1], "color": r[2], "position": int(r[3])}


def list_tags(conn) -> list[dict]:
    return [tag_row(r) for r in conn.execute(
        "SELECT id, name, color, position FROM tag_defs ORDER BY position, id").fetchall()]


def get_tag(conn, tag_id: int) -> dict | None:
    r = conn.execute("SELECT id, name, color, position FROM tag_defs WHERE id = ?", [tag_id]).fetchone()
    return tag_row(r) if r else None


def _next_id(conn) -> int:
    """Ids are never reused (a client may still hold a deleted id in a filter)."""
    stored = conn.execute("SELECT value FROM settings WHERE key = ?", [_NEXT_ID_KEY]).fetchone()
    mx = conn.execute("SELECT COALESCE(MAX(id), 0) FROM tag_defs").fetchone()[0]
    nid = max(int(stored[0]) if stored and str(stored[0]).isdigit() else 1, int(mx) + 1)
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", [_NEXT_ID_KEY, str(nid + 1)])
    return nid


def create_tag(conn, name: str, color: str) -> int:
    tid = _next_id(conn)
    pos = conn.execute("SELECT COALESCE(MAX(position) + 1, 0) FROM tag_defs").fetchone()[0]
    conn.execute("INSERT INTO tag_defs (id, name, color, position) VALUES (?, ?, ?, ?)",
                 [tid, name, color, int(pos)])
    return tid


def _insert_defaults(conn) -> None:
    for name, color in DEFAULT_TAGS:
        create_tag(conn, name, color)


def _renumber(conn) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM tag_defs ORDER BY position, id").fetchall()]
    for pos, tid in enumerate(ids):
        conn.execute("UPDATE tag_defs SET position = ? WHERE id = ? AND position <> ?", [pos, tid, pos])


def delete_tags(conn, tag_ids: list[int]) -> None:
    if not tag_ids:
        return
    conn.execute("DELETE FROM marked_hand_tags WHERE tag_id IN (SELECT UNNEST(?::INTEGER[]))", [tag_ids])
    conn.execute("DELETE FROM tag_defs WHERE id IN (SELECT UNNEST(?::INTEGER[]))", [tag_ids])
    _renumber(conn)


def move_tag(conn, tag_id: int, direction: str) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM tag_defs ORDER BY position, id").fetchall()]
    i = ids.index(tag_id)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
    for pos, tid in enumerate(ids):
        conn.execute("UPDATE tag_defs SET position = ? WHERE id = ?", [pos, tid])


def reset_tags(conn) -> None:
    """Restore the default catalogue. A tag whose name matches a default (case-insensitive)
    keeps its id, so marked hands keep it; every other tag is deleted."""
    current = conn.execute("SELECT id, name FROM tag_defs ORDER BY position, id").fetchall()
    keep: dict[str, int] = {}
    for tid, name in current:
        keep.setdefault(name.strip().lower(), int(tid))
    kept_ids = set()
    for pos, (name, color) in enumerate(DEFAULT_TAGS):
        tid = keep.get(name)
        if tid is None:
            tid = create_tag(conn, name, color)
        conn.execute("UPDATE tag_defs SET name = ?, color = ?, position = ? WHERE id = ?",
                     [name, color, pos, tid])
        kept_ids.add(tid)
    delete_tags(conn, [int(t) for t, _ in current if int(t) not in kept_ids])


# ── marks ──────────────────────────────────────────────────────────────────────────────────


def mark(conn, workspace_id: int, hand_id: str, player_id: int) -> bool:
    """Mark a (hand, player); True when newly marked."""
    if conn.execute(
        "SELECT 1 FROM marked_hands WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
        [workspace_id, hand_id, player_id],
    ).fetchone():
        return False
    conn.execute("INSERT INTO marked_hands (workspace_id, hand_id, player_id) VALUES (?, ?, ?)",
                 [workspace_id, hand_id, player_id])
    return True


def set_tags(conn, workspace_id: int, hand_id: str, player_id: int, tag_ids: list[int]) -> None:
    conn.execute(
        "DELETE FROM marked_hand_tags WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
        [workspace_id, hand_id, player_id],
    )
    for pos, tid in enumerate(tag_ids):
        conn.execute(
            "INSERT INTO marked_hand_tags (workspace_id, hand_id, player_id, tag_id, position) "
            "VALUES (?, ?, ?, ?, ?)",
            [workspace_id, hand_id, player_id, tid, pos],
        )


def add_tags(conn, workspace_id: int, hand_id: str, player_id: int, tag_ids: list[int]) -> None:
    have = {r[0] for r in conn.execute(
        "SELECT tag_id FROM marked_hand_tags WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
        [workspace_id, hand_id, player_id]).fetchall()}
    pos = conn.execute(
        "SELECT COALESCE(MAX(position) + 1, 0) FROM marked_hand_tags "
        "WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
        [workspace_id, hand_id, player_id]).fetchone()[0]
    for tid in tag_ids:
        if tid in have:
            continue
        have.add(tid)
        conn.execute(
            "INSERT INTO marked_hand_tags (workspace_id, hand_id, player_id, tag_id, position) "
            "VALUES (?, ?, ?, ?, ?)", [workspace_id, hand_id, player_id, tid, int(pos)])
        pos += 1


def unmark(conn, workspace_id: int, hand_id: str, player_id: int) -> None:
    for t in ("marked_hand_tags", "marked_hands"):
        conn.execute(f"DELETE FROM {t} WHERE workspace_id = ? AND hand_id = ? AND player_id = ?",
                     [workspace_id, hand_id, player_id])


def unmark_all(conn, workspace_id: int, tag_ids: list[int] | None) -> int:
    """Unmark every mark of the workspace, or the marks carrying any of `tag_ids`."""
    where = "m.workspace_id = ?"
    params: list = [workspace_id]
    if tag_ids:
        where += (" AND EXISTS (SELECT 1 FROM marked_hand_tags t WHERE t.workspace_id = m.workspace_id"
                  " AND t.hand_id = m.hand_id AND t.player_id = m.player_id"
                  " AND t.tag_id IN (SELECT UNNEST(?::INTEGER[])))")
        params.append(tag_ids)
    conn.execute(f"CREATE OR REPLACE TEMP TABLE _unmark AS "
                 f"SELECT m.hand_id, m.player_id FROM marked_hands m WHERE {where}", params)
    n = conn.execute("SELECT COUNT(*) FROM _unmark").fetchone()[0]
    for t in ("marked_hand_tags", "marked_hands"):
        conn.execute(f"DELETE FROM {t} WHERE workspace_id = ? AND EXISTS (SELECT 1 FROM _unmark u "
                     f"WHERE u.hand_id = {t}.hand_id AND u.player_id = {t}.player_id)", [workspace_id])
    conn.execute("DROP TABLE _unmark")
    return int(n)


def delete_workspace_marks(conn, workspace_id: int) -> None:
    for t in ("marked_hand_tags", "marked_hands"):
        conn.execute(f"DELETE FROM {t} WHERE workspace_id = ?", [workspace_id])


def marks_for(conn, workspace_id: int, player_id: int, hand_ids: list[str]
              ) -> tuple[set[str], dict[str, list[dict]]]:
    """(marked hand ids, hand id → tags in catalogue order) for one player's rows."""
    if not hand_ids:
        return set(), {}
    marked = {r[0] for r in conn.execute(
        "SELECT hand_id FROM marked_hands WHERE workspace_id = ? AND player_id = ? "
        "AND hand_id IN (SELECT UNNEST(?::VARCHAR[]))",
        [workspace_id, player_id, hand_ids]).fetchall()}
    tags: dict[str, list[dict]] = {}
    if marked:
        for hid, tid, name, color in conn.execute(
            "SELECT t.hand_id, d.id, d.name, d.color FROM marked_hand_tags t "
            "JOIN tag_defs d ON d.id = t.tag_id "
            "WHERE t.workspace_id = ? AND t.player_id = ? "
            "AND t.hand_id IN (SELECT UNNEST(?::VARCHAR[])) ORDER BY d.position, d.id",
            [workspace_id, player_id, list(marked)]).fetchall():
            tags.setdefault(hid, []).append({"id": int(tid), "name": name, "color": color})
    return marked, tags


def list_filter_sql(marked: bool | None, tag_ids: list[int] | None, hand_col: str, ws_col: str,
                    player_col: str) -> tuple[list[str], list]:
    """WHERE fragments for hand lists: `marked` true/false, `tag_ids` = any of (implies marked)."""
    clauses: list[str] = []
    params: list = []
    if marked is not None:
        clauses.append(
            ("" if marked else "NOT ")
            + f"EXISTS (SELECT 1 FROM marked_hands mh WHERE mh.workspace_id = {ws_col} "
              f"AND mh.hand_id = {hand_col} AND mh.player_id = {player_col})"
        )
    if tag_ids:
        clauses.append(
            f"EXISTS (SELECT 1 FROM marked_hand_tags mt WHERE mt.workspace_id = {ws_col} "
            f"AND mt.hand_id = {hand_col} AND mt.player_id = {player_col} "
            f"AND mt.tag_id IN (SELECT UNNEST(?::INTEGER[])))"
        )
        params.append(tag_ids)
    return clauses, params


def parse_id_list(s: str | None) -> list[int]:
    if not s:
        return []
    out: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if part.lstrip("-").isdigit() and int(part) not in out:
            out.append(int(part))
    return out
