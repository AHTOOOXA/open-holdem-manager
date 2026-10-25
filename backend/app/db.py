import atexit
import contextvars
import duckdb
import logging
import os
import re
import time
import threading
from pathlib import Path

from app.h2n.columns import H2N_COLUMNS

logger = logging.getLogger(__name__)

# Bump this when stat_flags.py or parser logic changes to trigger auto-rebuild.
STAT_VERSION = 7

_data_dir = os.environ.get("OHM_DATA_DIR")
if _data_dir:
    DB_PATH = Path(_data_dir) / "poker.duckdb"
else:
    DB_PATH = Path(__file__).parent.parent.parent / "data" / "poker.duckdb"

_conn: duckdb.DuckDBPyConnection | None = None
# Reentrant: write paths hold the lock and then call close_db()/get_db(),
# which take it again.
_lock = threading.RLock()
# Set when the app is quitting. Long write loops (import, rebuild) check it
# between batches and roll back so the DB can be closed cleanly.
_shutdown_event = threading.Event()
# Set if startup had to move a corrupt WAL aside (surfaced via /api/health).
_wal_recovery: dict | None = None
_request_cursors: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    '_request_cursors', default=None
)

# Background rebuild state (shared with health endpoint)
_rebuild_status: dict = {"active": False, "processed": 0, "total": 0}


# DuckDB's buffer pool cap. Measured DuckDB memory (duckdb_memory()) stays far below it:
# ~220 MB peak for the heaviest reads at 214k hands (raw_text scans, window over every
# hand_players row), ~160 MB during a 60k rebuild, and those reads run unchanged at 512 MB.
# The pool is mostly evictable block cache, so 2 GB is ~10x headroom (room for 1M hands)
# while bounding DuckDB's share of a 16 GB machine to half the former 4 GB. Spills go to
# DuckDB's default temp directory next to the database file. Override with
# OHM_DUCKDB_MEMORY_LIMIT (e.g. "4GB") and OHM_DUCKDB_THREADS (default: all cores).
DEFAULT_MEMORY_LIMIT = "2GB"
_SIZE_RE = re.compile(r"^\s*\d+(\.\d+)?\s*(B|KB|MB|GB|TB|KIB|MIB|GIB|TIB)\s*$", re.IGNORECASE)


def duckdb_limits() -> dict[str, str]:
    """The SET values get_db() applies: memory_limit always, threads only if overridden."""
    limits = {"memory_limit": DEFAULT_MEMORY_LIMIT}
    mem = os.environ.get("OHM_DUCKDB_MEMORY_LIMIT", "").strip()
    if mem:
        if _SIZE_RE.match(mem):
            limits["memory_limit"] = mem.replace(" ", "")
        else:
            logger.warning("Ignoring OHM_DUCKDB_MEMORY_LIMIT=%r (expected e.g. 2GB)", mem)
    threads = os.environ.get("OHM_DUCKDB_THREADS", "").strip()
    if threads:
        if threads.isdigit() and int(threads) > 0:
            limits["threads"] = str(int(threads))
        else:
            logger.warning("Ignoring OHM_DUCKDB_THREADS=%r (expected a positive integer)", threads)
    return limits


def _apply_duckdb_limits(conn: duckdb.DuckDBPyConnection) -> None:
    for name, value in duckdb_limits().items():
        conn.execute(f"SET {name} = '{value}'")


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                _conn = _connect_with_recovery()
                _apply_duckdb_limits(_conn)
                init_schema(_conn)
                atexit.register(close_db)
    return _conn


def _wal_path() -> Path:
    return DB_PATH.with_name(DB_PATH.name + ".wal")


def _is_wal_replay_error(e: Exception) -> bool:
    return "WAL" in str(e) and _wal_path().exists()


def _quarantine_wal(e: Exception) -> None:
    """Move a WAL that DuckDB can't replay out of the way (never delete it).

    Changes since the last checkpoint are lost, but the database opens again.
    The file is kept next to the DB so it can be inspected or recovered later.
    """
    global _wal_recovery
    wal = _wal_path()
    dest = wal.with_name(f"{wal.name}.corrupt-{time.strftime('%Y%m%d-%H%M%S')}")
    wal.rename(dest)
    _wal_recovery = {"quarantined_wal": str(dest), "error": str(e)[:500]}
    logger.error("WAL replay failed (%s). Moved WAL to %s and retrying.", e, dest)


def _connect_with_recovery() -> duckdb.DuckDBPyConnection:
    quarantined = False
    lock_retries = 0
    while True:
        try:
            return duckdb.connect(str(DB_PATH))
        except duckdb.Error as e:
            # A crash or kill mid-write can leave a WAL that fails to replay
            # (IOException or InternalException depending on the damage).
            # Without this, every later launch fails the same way.
            if not quarantined and _is_wal_replay_error(e):
                _quarantine_wal(e)
                quarantined = True
                continue
            # Lock held by another process (e.g. previous backend still exiting)
            if isinstance(e, duckdb.IOException) and lock_retries < 9:
                lock_retries += 1
                time.sleep(1)
                continue
            raise


def get_wal_recovery() -> dict | None:
    return _wal_recovery


def request_shutdown() -> None:
    _shutdown_event.set()


def shutdown_requested() -> bool:
    return _shutdown_event.is_set()


def get_read_cursor() -> duckdb.DuckDBPyConnection:
    """Return a new cursor for read-only queries (no lock needed).

    DuckDB supports concurrent reads via separate cursors on the same
    connection, so read-only endpoints can run in parallel.
    Cursors are tracked per-request and closed by cleanup_request_cursors().
    """
    cursor = get_db().cursor()
    cursors = _request_cursors.get(None)
    if cursors is not None:
        cursors.append(cursor)
    return cursor


def init_request_cursors() -> contextvars.Token:
    """Call at the start of a request to enable cursor tracking; pass the returned token to
    cleanup_request_cursors() once the response has been sent completely."""
    return _request_cursors.set([])


def cleanup_request_cursors(token: contextvars.Token | None = None) -> None:
    """Close all read cursors opened during this request."""
    cursors = _request_cursors.get(None)
    if cursors:
        for c in list(cursors):
            try:
                c.close()
            except Exception:
                pass
        cursors.clear()
    if token is not None:
        _request_cursors.reset(token)
    else:
        _request_cursors.set(None)


def db_lock() -> threading.RLock:
    """Return the lock that must be held during write operations."""
    return _lock


def get_hero_player_id(db, workspace_id: int = 1) -> int | None:
    """Active hero player ID of a workspace (see app/heroes.py), used by all endpoints."""
    from app.heroes import resolve_hero
    ref = resolve_hero(db, workspace_id)
    return ref.player_id if ref else None


def get_hero_username(db, workspace_id: int = 1) -> str:
    """Active hero username of a workspace; 'Hero' when there is none."""
    from app.heroes import resolve_hero
    ref = resolve_hero(db, workspace_id)
    return ref.username if ref else "Hero"


def close_db():
    global _conn
    with _lock:
        if _conn is not None:
            try:
                # Flush the WAL into the DB file so a later hard kill
                # can't leave anything to replay.
                _conn.execute("CHECKPOINT")
            except Exception:
                logger.exception("CHECKPOINT on close failed")
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


_COLUMNS_SQL = (
    "SELECT table_name, column_name FROM duckdb_columns() "
    "WHERE database_name = current_database() AND schema_name = current_schema()"
)


class _ColumnCatalog:
    """Column names per table, read with one catalog query.

    Startup used to probe `duckdb_columns()` once per migrated column (~55 probes, ~28 ms at
    20k and 214k alike). A snapshot answers every probe; it is re-read when a table it has
    never seen is asked about (created after the snapshot). Migrations that recreate a table
    keep its columns (CREATE TABLE AS SELECT *), so a known table's column set stays valid.
    """

    def __init__(self, conn) -> None:
        self.conn = conn
        self._cols: dict[str, set[str]] | None = None

    def _load(self) -> None:
        cols: dict[str, set[str]] = {}
        for table, column in self.conn.execute(_COLUMNS_SQL).fetchall():
            cols.setdefault(table, set()).add(column)
        self._cols = cols

    def has(self, table: str, column: str) -> bool:
        if self._cols is None or table not in self._cols:
            self._load()
        return column in self._cols.get(table, ())

    def added(self, table: str, column: str) -> None:
        if self._cols is not None:
            self._cols.setdefault(table, set()).add(column)


# The snapshot of the init_schema() run in progress (None outside it).
_column_catalog: contextvars.ContextVar[_ColumnCatalog | None] = contextvars.ContextVar(
    "_column_catalog", default=None
)


def _add_column_if_missing(
    conn: duckdb.DuckDBPyConnection, table: str, column: str, ddl: str,
) -> None:
    """ALTER TABLE ADD COLUMN only when needed, instead of catching the error
    (a failed statement aborts the surrounding transaction, if there is one).
    `IF NOT EXISTS` keeps it safe even if the snapshot missed a column added meanwhile."""
    catalog = _column_catalog.get()
    if catalog is None or catalog.conn is not conn:
        catalog = _ColumnCatalog(conn)
    if not catalog.has(table, column):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {ddl}")
        catalog.added(table, column)


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the schema and run the idempotent migrations (one catalog read for all
    column checks, see _ColumnCatalog)."""
    token = _column_catalog.set(_ColumnCatalog(conn))
    try:
        _init_schema(conn)
    finally:
        _column_catalog.reset(token)


def _init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            code VARCHAR NOT NULL UNIQUE
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO sites VALUES (1, 'GGPoker', 'GG')
    """)
    conn.execute("INSERT OR IGNORE INTO sites VALUES (2, 'PokerStars', 'PS')")
    conn.execute("INSERT OR IGNORE INTO sites VALUES (3, '888poker', '888')")
    conn.execute("INSERT OR IGNORE INTO sites VALUES (4, 'WPN', 'WPN')")
    conn.execute("INSERT OR IGNORE INTO sites VALUES (5, 'Winamax', 'WMX')")
    conn.execute("INSERT OR IGNORE INTO sites VALUES (6, 'iPoker', 'IP')")
    conn.execute("INSERT OR IGNORE INTO sites VALUES (7, 'partypoker', 'PP')")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY,
            site_id INTEGER REFERENCES sites(id),
            username VARCHAR NOT NULL,
            notes TEXT,
            color_tag VARCHAR,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            UNIQUE(site_id, username)
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_players START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hands (
            id VARCHAR PRIMARY KEY,
            site_id INTEGER REFERENCES sites(id),
            played_at TIMESTAMP NOT NULL,
            game_type VARCHAR NOT NULL,
            game_mode VARCHAR NOT NULL DEFAULT '',
            stakes VARCHAR NOT NULL,
            sb_amount DECIMAL NOT NULL,
            bb_amount DECIMAL NOT NULL,
            table_name VARCHAR,
            table_size INTEGER,
            button_seat INTEGER,
            raw_text TEXT,
            cash_drop_received DECIMAL DEFAULT 0,
            rit_boards INTEGER NOT NULL DEFAULT 1,
            is_cashout BOOLEAN NOT NULL DEFAULT FALSE,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_players (
            id INTEGER PRIMARY KEY,
            hand_id VARCHAR ,
            player_id INTEGER REFERENCES players(id),
            seat INTEGER NOT NULL,
            position VARCHAR NOT NULL,
            stack DECIMAL,
            stack_bb DECIMAL,
            card1 VARCHAR,
            card2 VARCHAR,
            won DECIMAL DEFAULT 0,
            won_bb DECIMAL DEFAULT 0,
            rake DECIMAL DEFAULT 0,
            rake_bb DECIMAL DEFAULT 0,
            jackpot DECIMAL DEFAULT 0,
            jackpot_bb DECIMAL DEFAULT 0,

            vpip BOOLEAN DEFAULT FALSE,
            pfr BOOLEAN DEFAULT FALSE,
            three_bet BOOLEAN DEFAULT FALSE,
            three_bet_opp BOOLEAN DEFAULT FALSE,
            three_bet_opp_ip BOOLEAN,
            four_bet BOOLEAN DEFAULT FALSE,
            four_bet_opp BOOLEAN DEFAULT FALSE,
            fold_to_3bet BOOLEAN,
            fold_to_4bet BOOLEAN,
            open_raise BOOLEAN DEFAULT FALSE,
            open_raise_opp BOOLEAN DEFAULT FALSE,
            call_open_raise BOOLEAN DEFAULT FALSE,
            call_open_raise_opp BOOLEAN DEFAULT FALSE,
            limp BOOLEAN DEFAULT FALSE,
            squeeze BOOLEAN DEFAULT FALSE,
            five_bet BOOLEAN DEFAULT FALSE,

            steal_attempted BOOLEAN DEFAULT FALSE,
            faced_steal BOOLEAN DEFAULT FALSE,
            fold_to_steal BOOLEAN,
            call_steal BOOLEAN,
            three_bet_vs_steal BOOLEAN,

            saw_flop BOOLEAN DEFAULT FALSE,
            saw_turn BOOLEAN DEFAULT FALSE,
            saw_river BOOLEAN DEFAULT FALSE,
            went_to_showdown BOOLEAN DEFAULT FALSE,
            won_at_showdown BOOLEAN,

            cbet_flop BOOLEAN,
            cbet_flop_opp BOOLEAN DEFAULT FALSE,
            cbet_turn BOOLEAN,
            cbet_turn_opp BOOLEAN DEFAULT FALSE,
            cbet_river BOOLEAN,
            cbet_river_opp BOOLEAN DEFAULT FALSE,
            fold_to_cbet_flop BOOLEAN,
            fold_to_cbet_turn BOOLEAN,
            fold_to_cbet_river BOOLEAN,

            missed_cbet_flop BOOLEAN DEFAULT FALSE,
            missed_cbet_turn BOOLEAN DEFAULT FALSE,

            donk_bet_flop BOOLEAN,
            donk_bet_turn BOOLEAN,
            donk_bet_river BOOLEAN,

            -- All-in EV (equals won_bb for non-all-in hands)
            all_in_ev_bb DECIMAL DEFAULT 0,

            -- Aggression counts per street
            flop_bets INTEGER DEFAULT 0,
            flop_raises INTEGER DEFAULT 0,
            flop_calls INTEGER DEFAULT 0,
            flop_checks INTEGER DEFAULT 0,
            flop_folds INTEGER DEFAULT 0,
            turn_bets INTEGER DEFAULT 0,
            turn_raises INTEGER DEFAULT 0,
            turn_calls INTEGER DEFAULT 0,
            turn_checks INTEGER DEFAULT 0,
            turn_folds INTEGER DEFAULT 0,
            river_bets INTEGER DEFAULT 0,
            river_raises INTEGER DEFAULT 0,
            river_calls INTEGER DEFAULT 0,
            river_checks INTEGER DEFAULT 0,
            river_folds INTEGER DEFAULT 0,

            -- Opportunity flags
            steal_opp BOOLEAN DEFAULT FALSE,
            donk_bet_flop_opp BOOLEAN DEFAULT FALSE,
            donk_bet_turn_opp BOOLEAN DEFAULT FALSE,
            donk_bet_river_opp BOOLEAN DEFAULT FALSE,
            squeeze_opp BOOLEAN DEFAULT FALSE,
            five_bet_opp BOOLEAN DEFAULT FALSE,

            -- Extended stats (limp-fold, 4bet-fold, call-4bet, pot type, cbet response, vs missed cbet)
            limp_fold BOOLEAN DEFAULT FALSE,
            four_bet_fold BOOLEAN,
            call_4bet BOOLEAN DEFAULT FALSE,
            is_3bet_pot BOOLEAN DEFAULT FALSE,
            call_cbet_flop BOOLEAN,
            raise_cbet_flop BOOLEAN,
            vs_missed_cbet_flop_opp BOOLEAN DEFAULT FALSE,
            preflop_allin_raise BOOLEAN DEFAULT FALSE,
            preflop_allin_call BOOLEAN DEFAULT FALSE,
            postflop_ip BOOLEAN,

            -- BB Defense / Iso Raise / Fold to Squeeze
            bb_defense BOOLEAN,
            bb_defense_opp BOOLEAN DEFAULT FALSE,
            iso_raise BOOLEAN DEFAULT FALSE,
            iso_raise_opp BOOLEAN DEFAULT FALSE,
            faced_squeeze BOOLEAN DEFAULT FALSE,
            fold_to_squeeze BOOLEAN

            -- H2N columns (h2n_pos, h2n_*_opp/case bitmasks, is_winner, hv_*)
            -- are added below from app.h2n.columns.H2N_COLUMNS
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_hand_players START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY,
            hand_id VARCHAR ,
            player_id INTEGER REFERENCES players(id),
            street VARCHAR NOT NULL,
            action_order INTEGER NOT NULL,
            action_type VARCHAR NOT NULL,
            amount DECIMAL,
            amount_bb DECIMAL,
            is_all_in BOOLEAN DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_actions START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS board_cards (
            hand_id VARCHAR ,
            street VARCHAR NOT NULL,
            card VARCHAR NOT NULL,
            card_order INTEGER NOT NULL,
            board_number INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR PRIMARY KEY,
            value VARCHAR NOT NULL
        )
    """)
    # Auto-import per-file read state (app/auto_import.py): bytes consumed so far, per
    # target workspace (pre-workspace-key tables are migrated in _migrate_auto_import_files)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auto_import_files (
            workspace_id INTEGER NOT NULL,
            path VARCHAR NOT NULL,
            size BIGINT NOT NULL,
            mtime DOUBLE NOT NULL,
            "offset" BIGINT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, path)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_tags (
            hand_id VARCHAR ,
            tag VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (hand_id, tag)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_notes (
            hand_id VARCHAR PRIMARY KEY ,
            note TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_classifications (
            player_id INTEGER NOT NULL,
            workspace_id INTEGER NOT NULL DEFAULT 1,
            player_type VARCHAR NOT NULL DEFAULT 'UNK',
            PRIMARY KEY (player_id, workspace_id)
        )
    """)
    # Seed hero settings only for pre-workspace databases (new DBs get them via workspace)
    migrated = conn.execute(
        "SELECT 1 FROM settings WHERE key = 'workspace_migration'"
    ).fetchone()
    if not migrated:
        conn.execute("""
            INSERT OR IGNORE INTO settings VALUES ('hero_username', 'Hero')
        """)
        conn.execute("""
            INSERT OR IGNORE INTO settings VALUES ('hero_site', 'GG')
        """)

    # Migrations for existing databases
    for col, default in [
        ("all_in_ev_bb", "DECIMAL DEFAULT 0"),
        ("open_raise_opp", "BOOLEAN DEFAULT FALSE"),
        ("flop_checks", "INTEGER DEFAULT 0"),
        ("flop_folds", "INTEGER DEFAULT 0"),
        ("turn_checks", "INTEGER DEFAULT 0"),
        ("turn_folds", "INTEGER DEFAULT 0"),
        ("river_checks", "INTEGER DEFAULT 0"),
        ("river_folds", "INTEGER DEFAULT 0"),
        ("steal_opp", "BOOLEAN DEFAULT FALSE"),
        ("donk_bet_flop_opp", "BOOLEAN DEFAULT FALSE"),
        ("donk_bet_turn_opp", "BOOLEAN DEFAULT FALSE"),
        ("donk_bet_river_opp", "BOOLEAN DEFAULT FALSE"),
        ("squeeze_opp", "BOOLEAN DEFAULT FALSE"),
        ("five_bet_opp", "BOOLEAN DEFAULT FALSE"),
        ("jackpot", "DECIMAL DEFAULT 0"),
        ("jackpot_bb", "DECIMAL DEFAULT 0"),
        ("limp_fold", "BOOLEAN DEFAULT FALSE"),
        ("four_bet_fold", "BOOLEAN"),
        ("call_4bet", "BOOLEAN DEFAULT FALSE"),
        ("is_3bet_pot", "BOOLEAN DEFAULT FALSE"),
        ("call_cbet_flop", "BOOLEAN"),
        ("raise_cbet_flop", "BOOLEAN"),
        ("vs_missed_cbet_flop_opp", "BOOLEAN DEFAULT FALSE"),
        ("preflop_allin_raise", "BOOLEAN DEFAULT FALSE"),
        ("preflop_allin_call", "BOOLEAN DEFAULT FALSE"),
        ("postflop_ip", "BOOLEAN"),
        ("call_open_raise_opp", "BOOLEAN DEFAULT FALSE"),
        ("three_bet_opp_ip", "BOOLEAN"),
        ("bb_defense", "BOOLEAN"),
        ("bb_defense_opp", "BOOLEAN DEFAULT FALSE"),
        ("iso_raise", "BOOLEAN DEFAULT FALSE"),
        ("iso_raise_opp", "BOOLEAN DEFAULT FALSE"),
        ("faced_squeeze", "BOOLEAN DEFAULT FALSE"),
        ("fold_to_squeeze", "BOOLEAN"),
        ("pot_type", "VARCHAR DEFAULT 'SRP'"),
        ("is_multiway", "BOOLEAN DEFAULT FALSE"),
    ]:
        _add_column_if_missing(conn, "hand_players", col, default)

    # H2N-compatible columns (contract: app/h2n/CONTRACT.md)
    for col, ddl, _ in H2N_COLUMNS:
        _add_column_if_missing(conn, "hand_players", col, ddl)

    # Migrations for hands table
    for col, default in [
        ("cash_drop_received", "DECIMAL DEFAULT 0"),
        ("game_mode", "VARCHAR DEFAULT ''"),
        ("rit_boards", "INTEGER DEFAULT 1"),
        ("is_cashout", "BOOLEAN DEFAULT FALSE"),
    ]:
        _add_column_if_missing(conn, "hands", col, default)

    # Migration for board_cards table
    _add_column_if_missing(conn, "board_cards", "board_number", "INTEGER DEFAULT 1")

    # Backfill game_mode: RC* hands → Fast Fold, everything else → ''
    try:
        conn.execute("""
            UPDATE hands SET game_mode = 'Fast Fold'
            WHERE game_mode != 'Fast Fold' AND id LIKE 'RC%'
        """)
        conn.execute("""
            UPDATE hands SET game_mode = ''
            WHERE game_mode NOT IN ('', 'Fast Fold')
        """)
    except Exception:
        pass

    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_played_at ON hands(played_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_stakes ON hands(stakes)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_game_mode ON hands(game_mode)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_hand_id ON hand_players(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_player_id ON hand_players(player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_position ON hand_players(position)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_hand_id ON actions(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hand_tags_hand_id ON hand_tags(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hand_tags_tag ON hand_tags(tag)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_board_cards_hand_id ON board_cards(hand_id)")

    # Composite indexes for common query patterns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_player_hand ON hand_players(player_id, hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_hand_player ON hand_players(hand_id, player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_player_position ON hand_players(player_id, position)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_played_stakes ON hands(played_at, stakes)")

    # Sync sequences to max existing IDs (prevents collisions after restart)
    for table, seq in [
        ("players", "seq_players"),
        ("hand_players", "seq_hand_players"),
        ("actions", "seq_actions"),
    ]:
        max_id = conn.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}").fetchone()[0]
        if max_id > 0:
            conn.execute(f"DROP SEQUENCE IF EXISTS {seq}")
            conn.execute(f"CREATE SEQUENCE {seq} START {max_id + 1}")

    # Workspace migration
    _migrate_to_workspaces(conn)

    # Player identities migration
    _migrate_to_identities(conn)

    # Remove analysis_views (feature removed)
    conn.execute("DROP TABLE IF EXISTS analysis_views")
    conn.execute("DROP SEQUENCE IF EXISTS seq_views")
    conn.execute("DELETE FROM settings WHERE key = 'views_migration'")

    # Allow same hand ID across workspaces (needed for composite key migration)
    _migrate_hands_composite_key(conn)

    # Add workspace_id to child tables for workspace-scoped JOINs
    _migrate_child_workspace_id(conn)

    # Fix duplicated child rows from incorrect workspace_id backfill
    _fix_child_workspace_duplicates(conn)

    # Fix hand_tags and hand_notes missed by the original dedup fix
    _fix_child_workspace_duplicates_v2(conn)

    # Add workspace_id to player_classifications for workspace-scoped classification
    _migrate_player_classifications_workspace(conn)

    # One tag per (workspace, hand, tag), one note per (workspace, hand)
    _ensure_tag_note_keys(conn)

    # Hero accounts (manual + auto-detected); backfills existing databases
    _ensure_hero_accounts(conn)

    # Configuration sections: reg classification, alias flags, rebuild fingerprint
    _migrate_config_sections(conn)
    # Auto-import file states keyed by (workspace, path)
    _migrate_auto_import_files(conn)
    # Tag catalogue + marked hands; one-time migration from hand_tags (needs heroes)
    from app.marked_hands import ensure_schema as _ensure_marked_hands
    _ensure_marked_hands(conn)

    # Check stat version — trigger rebuild if outdated
    _check_stat_version(conn)


def _migrate_to_workspaces(conn: duckdb.DuckDBPyConnection) -> None:
    """Create workspaces + checkpoints tables and migrate existing data.

    Idempotent — checks the 'workspace_migration' setting key before running.
    Moves hero_username/hero_site from settings into the default workspace row.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'workspace_migration'"
    ).fetchone()
    if row is not None:
        # Already migrated — ensure tables exist (e.g. fresh DB that set the flag)
        return

    logger.info("Running workspace migration...")

    # 1. Create workspaces table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            hero_username VARCHAR NOT NULL DEFAULT 'Hero',
            hero_site VARCHAR NOT NULL DEFAULT 'GG',
            description TEXT,
            color VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_workspaces START 2")

    # 2. Read existing hero settings
    hero_row = conn.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = hero_row[0] if hero_row else 'Hero'

    site_row = conn.execute(
        "SELECT value FROM settings WHERE key = 'hero_site'"
    ).fetchone()
    hero_site = site_row[0] if site_row else 'GG'

    # 3. Insert default workspace (id=1)
    conn.execute(
        "INSERT OR IGNORE INTO workspaces (id, name, hero_username, hero_site) "
        "VALUES (1, 'My Game', ?, ?)",
        [hero_username, hero_site],
    )

    # 4. Add workspace_id column to hands table
    _add_column_if_missing(conn, "hands", "workspace_id", "INTEGER DEFAULT 1")

    # 5. Backfill any NULL workspace_id values
    conn.execute("UPDATE hands SET workspace_id = 1 WHERE workspace_id IS NULL")

    # 6. Create indexes on hands.workspace_id
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_hands_workspace_id ON hands(workspace_id, id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hands_workspace ON hands(workspace_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_hands_workspace_played ON hands(workspace_id, played_at)"
    )

    # 7. Create checkpoints table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
            name VARCHAR NOT NULL,
            checkpoint_at TIMESTAMP NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_checkpoints START 1")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_checkpoints_workspace ON checkpoints(workspace_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_checkpoints_at ON checkpoints(workspace_id, checkpoint_at)"
    )

    # 8. Remove hero settings from settings table (now in workspaces)
    conn.execute("DELETE FROM settings WHERE key IN ('hero_username', 'hero_site')")

    # 9. Mark migration as complete
    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('workspace_migration', '1')"
    )

    logger.info("Workspace migration complete.")


def _migrate_to_identities(conn: duckdb.DuckDBPyConnection) -> None:
    """Create player_identities + player_aliases tables.

    Idempotent — checks the 'identities_migration' setting key before running.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'identities_migration'"
    ).fetchone()
    if row is not None:
        return

    logger.info("Running identities migration...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_identities (
            id INTEGER PRIMARY KEY,
            display_name VARCHAR NOT NULL,
            notes TEXT,
            color VARCHAR,
            tags VARCHAR DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_identities START 1")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS player_aliases (
            id INTEGER PRIMARY KEY,
            identity_id INTEGER NOT NULL REFERENCES player_identities(id),
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
            player_id INTEGER NOT NULL REFERENCES players(id),
            UNIQUE(workspace_id, player_id)
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_aliases START 1")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aliases_identity ON player_aliases(identity_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_aliases_player ON player_aliases(player_id)"
    )

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('identities_migration', '1')"
    )
    logger.info("Identities migration complete.")


def _migrate_child_workspace_id(conn: duckdb.DuckDBPyConnection) -> None:
    """Add workspace_id to child tables so JOINs are workspace-scoped.

    Without this, hand_players JOIN hands ON hand_id crosses workspace
    boundaries when the same hand exists in multiple workspaces.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'child_workspace_id'"
    ).fetchone()
    if row is not None:
        return

    logger.info("Adding workspace_id to child tables...")

    for table in ("hand_players", "actions", "board_cards", "hand_tags", "hand_notes"):
        _add_column_if_missing(conn, table, "workspace_id", "INTEGER")

        # Backfill from hands table
        conn.execute(f"""
            UPDATE {table} SET workspace_id = (
                SELECT MIN(h.workspace_id) FROM hands h WHERE h.id = {table}.hand_id
            )
            WHERE workspace_id IS NULL
        """)

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('child_workspace_id', '1')"
    )
    logger.info("Child table workspace_id migration complete.")


def _fix_child_workspace_duplicates(conn: duckdb.DuckDBPyConnection) -> None:
    """Fix child rows that were all assigned to workspace 1 by the backfill.

    The _migrate_child_workspace_id backfill used MIN(h.workspace_id) which
    set ALL child rows to workspace_id=1, even those belonging to workspace 2+.
    For each hand existing in N workspaces, child tables have N× rows all in ws1.

    Fix: use ROW_NUMBER to identify duplicate rows per natural key and reassign
    the Nth copy to the Nth workspace (ordered by row id).
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'fix_child_ws_dups'"
    ).fetchone()
    if row is not None:
        return

    # Find hands that exist in multiple workspaces
    multi_ws = conn.execute("""
        SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1
    """).fetchall()
    if not multi_ws:
        conn.execute(
            "INSERT OR REPLACE INTO settings VALUES ('fix_child_ws_dups', '1')"
        )
        return

    logger.info("Fixing %d hands with duplicated child rows across workspaces...", len(multi_ws))

    # Build ordered workspace list per hand_id
    ws_map = conn.execute("""
        SELECT id, workspace_id FROM hands
        WHERE id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        ORDER BY id, workspace_id
    """).fetchall()
    # hand_id → [ws1, ws2, ...]  (ordered)
    hand_ws: dict[str, list[int]] = {}
    for hid, wid in ws_map:
        hand_ws.setdefault(hid, []).append(wid)

    # Fix hand_players: partition by (hand_id, seat), order by id
    # Row N gets workspace = Nth workspace for that hand
    dup_hp = conn.execute("""
        SELECT hp.id, hp.hand_id,
               ROW_NUMBER() OVER (PARTITION BY hp.hand_id, hp.seat ORDER BY hp.id) as rn
        FROM hand_players hp
        WHERE hp.workspace_id = 1
          AND hp.hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
    """).fetchall()

    hp_updates: dict[int, list[int]] = {}  # workspace_id → [hp.id, ...]
    for hp_id, hid, rn in dup_hp:
        ws_list = hand_ws.get(hid, [1])
        target_ws = ws_list[rn - 1] if rn <= len(ws_list) else ws_list[-1]
        if target_ws != 1:
            hp_updates.setdefault(target_ws, []).append(hp_id)

    for ws_id, ids in hp_updates.items():
        # Batch update in chunks
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            ph = ",".join(str(x) for x in chunk)
            conn.execute(f"UPDATE hand_players SET workspace_id = {ws_id} WHERE id IN ({ph})")
    logger.info("  Fixed %d hand_players rows", sum(len(v) for v in hp_updates.values()))

    # Fix board_cards (no id column — use delete+reinsert approach):
    # 1. Deduplicate: keep one row per natural key in workspace 1
    # 2. Insert copies for each additional workspace
    multi_hand_ids = list(hand_ws.keys())
    if multi_hand_ids:
        # Collect distinct board data for these hands
        bc_data = conn.execute("""
            SELECT DISTINCT hand_id, street, card, card_order, board_number
            FROM board_cards
            WHERE workspace_id = 1
              AND hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
            ORDER BY hand_id, board_number, card_order
        """).fetchall()

        # Delete all board_cards for these hands (both original and duplicates)
        conn.execute("""
            DELETE FROM board_cards
            WHERE hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        """)

        # Re-insert with correct workspace_ids — one copy per workspace
        bc_count = 0
        for hid, street, card, card_order, board_number in bc_data:
            for ws_id in hand_ws.get(hid, [1]):
                conn.execute(
                    "INSERT INTO board_cards (hand_id, street, card, card_order, board_number, workspace_id) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [hid, street, card, card_order, board_number, ws_id],
                )
                if ws_id != 1:
                    bc_count += 1
        logger.info("  Fixed board_cards: reinserted for %d non-ws1 rows", bc_count)

    # Fix actions (has id column, same approach as hand_players)
    dup_act = conn.execute("""
        SELECT a.id, a.hand_id,
               ROW_NUMBER() OVER (
                   PARTITION BY a.hand_id, a.action_order ORDER BY a.id
               ) as rn
        FROM actions a
        WHERE a.workspace_id = 1
          AND a.hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
    """).fetchall()

    act_updates: dict[int, list[int]] = {}
    for act_id, hid, rn in dup_act:
        ws_list = hand_ws.get(hid, [1])
        target_ws = ws_list[rn - 1] if rn <= len(ws_list) else ws_list[-1]
        if target_ws != 1:
            act_updates.setdefault(target_ws, []).append(act_id)

    for ws_id, ids in act_updates.items():
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            ph = ",".join(str(x) for x in chunk)
            conn.execute(f"UPDATE actions SET workspace_id = {ws_id} WHERE id IN ({ph})")
    logger.info("  Fixed %d actions rows", sum(len(v) for v in act_updates.values()))

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('fix_child_ws_dups', '1')"
    )
    logger.info("Child workspace duplicate fix complete.")


def _fix_child_workspace_duplicates_v2(conn: duckdb.DuckDBPyConnection) -> None:
    """Fix hand_tags and hand_notes that were missed by the original dedup fix.

    The original _fix_child_workspace_duplicates only corrected hand_players,
    board_cards, and actions. Tags and notes for hands in workspace 2+ remain
    stranded with workspace_id=1.

    Both hand_tags and hand_notes lack an id column, so we use the
    delete+reinsert approach (same as board_cards in the original fix).
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'fix_child_ws_dups_v2'"
    ).fetchone()
    if row is not None:
        return

    # Find hands that exist in multiple workspaces
    multi_ws = conn.execute("""
        SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1
    """).fetchall()
    if not multi_ws:
        conn.execute(
            "INSERT OR REPLACE INTO settings VALUES ('fix_child_ws_dups_v2', '1')"
        )
        return

    logger.info("Fixing %d hands with duplicated hand_tags/hand_notes across workspaces...", len(multi_ws))

    # Build ordered workspace list per hand_id
    ws_map = conn.execute("""
        SELECT id, workspace_id FROM hands
        WHERE id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        ORDER BY id, workspace_id
    """).fetchall()
    hand_ws: dict[str, list[int]] = {}
    for hid, wid in ws_map:
        hand_ws.setdefault(hid, []).append(wid)

    # Fix hand_tags (no id column — delete+reinsert approach, same as board_cards)
    tag_data = conn.execute("""
        SELECT DISTINCT hand_id, tag, created_at
        FROM hand_tags
        WHERE workspace_id = 1
          AND hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        ORDER BY hand_id, tag
    """).fetchall()

    if tag_data:
        conn.execute("""
            DELETE FROM hand_tags
            WHERE hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        """)

        tag_count = 0
        for hid, tag, created_at in tag_data:
            for ws_id in hand_ws.get(hid, [1]):
                conn.execute(
                    "INSERT INTO hand_tags (hand_id, tag, created_at, workspace_id) "
                    "VALUES (?, ?, ?, ?)",
                    [hid, tag, created_at, ws_id],
                )
                if ws_id != 1:
                    tag_count += 1
        logger.info("  Fixed hand_tags: reinserted for %d non-ws1 rows", tag_count)

    # Fix hand_notes (no id column — delete+reinsert approach)
    note_data = conn.execute("""
        SELECT DISTINCT hand_id, note, updated_at
        FROM hand_notes
        WHERE workspace_id = 1
          AND hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        ORDER BY hand_id
    """).fetchall()

    if note_data:
        conn.execute("""
            DELETE FROM hand_notes
            WHERE hand_id IN (SELECT id FROM hands GROUP BY id HAVING COUNT(DISTINCT workspace_id) > 1)
        """)

        note_count = 0
        for hid, note, updated_at in note_data:
            for ws_id in hand_ws.get(hid, [1]):
                conn.execute(
                    "INSERT INTO hand_notes (hand_id, note, updated_at, workspace_id) "
                    "VALUES (?, ?, ?, ?)",
                    [hid, note, updated_at, ws_id],
                )
                if ws_id != 1:
                    note_count += 1
        logger.info("  Fixed hand_notes: reinserted for %d non-ws1 rows", note_count)

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('fix_child_ws_dups_v2', '1')"
    )
    logger.info("Child workspace duplicate fix v2 (tags+notes) complete.")


def _migrate_player_classifications_workspace(conn: duckdb.DuckDBPyConnection) -> None:
    """Add workspace_id to player_classifications for workspace-scoped classification.

    Recreates the table with (player_id, workspace_id) composite PK.
    Existing rows get workspace_id=1. After migration, batch_update_player_types
    will recompute per-workspace classifications.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'pc_workspace_migration'"
    ).fetchone()
    if row is not None:
        return

    logger.info("Migrating player_classifications to workspace-scoped schema...")

    # Check if old schema (no workspace_id column)
    cols = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'player_classifications'"
    ).fetchall()
    col_names = {c[0] for c in cols}

    if "workspace_id" not in col_names:
        # Recreate table with new schema (DuckDB can't add to PK)
        conn.execute(
            "CREATE TABLE _pc_tmp AS "
            "SELECT player_id, 1 AS workspace_id, player_type "
            "FROM player_classifications"
        )
        conn.execute("DROP TABLE player_classifications")
        conn.execute("""
            CREATE TABLE player_classifications (
                player_id INTEGER NOT NULL,
                workspace_id INTEGER NOT NULL DEFAULT 1,
                player_type VARCHAR NOT NULL DEFAULT 'UNK',
                PRIMARY KEY (player_id, workspace_id)
            )
        """)
        conn.execute(
            "INSERT INTO player_classifications "
            "SELECT player_id, workspace_id, player_type FROM _pc_tmp"
        )
        conn.execute("DROP TABLE _pc_tmp")

        # Duplicate classifications for each workspace that has hands
        workspace_ids = conn.execute(
            "SELECT DISTINCT workspace_id FROM hands WHERE workspace_id != 1"
        ).fetchall()
        for (ws_id,) in workspace_ids:
            conn.execute(
                "INSERT OR IGNORE INTO player_classifications (player_id, workspace_id, player_type) "
                "SELECT player_id, ?, player_type FROM player_classifications WHERE workspace_id = 1",
                [ws_id],
            )

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('pc_workspace_migration', '1')"
    )
    logger.info("Player classifications workspace migration complete.")


def _migrate_hands_composite_key(conn: duckdb.DuckDBPyConnection) -> None:
    """Change hands PK from (id) to unique(workspace_id, id).

    This allows the same hand to exist in multiple workspaces.
    Recreates the table via CREATE TABLE AS SELECT (drops the single-column PK),
    then adds a composite unique index.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'hands_composite_key'"
    ).fetchone()
    if row is not None:
        return

    logger.info("Migrating hands table to composite key (workspace_id, id)...")

    # DuckDB doesn't support ALTER TABLE DROP CONSTRAINT, so we must
    # recreate child tables (without FK) to release the hands PK dependency.
    for child in ("hand_players", "actions", "board_cards", "hand_tags", "hand_notes"):
        conn.execute(f"CREATE TABLE _{child}_tmp AS SELECT * FROM {child}")
        conn.execute(f"DROP TABLE {child}")
        conn.execute(f"ALTER TABLE _{child}_tmp RENAME TO {child}")

    conn.execute("DROP TABLE IF EXISTS _hands_tmp")
    conn.execute("CREATE TABLE _hands_tmp AS SELECT * FROM hands")
    conn.execute("DROP TABLE hands")
    conn.execute("ALTER TABLE _hands_tmp RENAME TO hands")

    # Recreate all indexes (table recreation wiped them)
    conn.execute("CREATE UNIQUE INDEX uq_hands_workspace_id ON hands(workspace_id, id)")
    conn.execute("CREATE INDEX idx_hands_workspace ON hands(workspace_id)")
    conn.execute("CREATE INDEX idx_hands_workspace_played ON hands(workspace_id, played_at)")
    conn.execute("CREATE INDEX idx_hands_played_at ON hands(played_at)")
    conn.execute("CREATE INDEX idx_hands_stakes ON hands(stakes)")
    conn.execute("CREATE INDEX idx_hands_game_mode ON hands(game_mode)")
    conn.execute("CREATE INDEX idx_h_played_stakes ON hands(played_at, stakes)")
    conn.execute("CREATE INDEX idx_hp_hand_id ON hand_players(hand_id)")
    conn.execute("CREATE INDEX idx_hp_player_id ON hand_players(player_id)")
    conn.execute("CREATE INDEX idx_hp_position ON hand_players(position)")
    conn.execute("CREATE INDEX idx_hp_player_hand ON hand_players(player_id, hand_id)")
    conn.execute("CREATE INDEX idx_hp_hand_player ON hand_players(hand_id, player_id)")
    conn.execute("CREATE INDEX idx_hp_player_position ON hand_players(player_id, position)")
    conn.execute("CREATE INDEX idx_actions_hand_id ON actions(hand_id)")
    conn.execute("CREATE INDEX idx_hand_tags_hand_id ON hand_tags(hand_id)")
    conn.execute("CREATE INDEX idx_hand_tags_tag ON hand_tags(tag)")
    conn.execute("CREATE INDEX idx_board_cards_hand_id ON board_cards(hand_id)")

    conn.execute(
        "INSERT OR REPLACE INTO settings VALUES ('hands_composite_key', '1')"
    )
    logger.info("Hands composite key migration complete.")


def _ensure_tag_note_keys(conn: duckdb.DuckDBPyConnection) -> None:
    """Unique keys for hand_tags / hand_notes that include workspace_id.

    The original keys (hand_id, tag) and (hand_id) ignored the workspace, and
    the composite-key migration rebuilt both tables with CREATE TABLE AS,
    which dropped them entirely, so duplicates were possible. Idempotent.
    """
    existing = {
        r[0] for r in conn.execute(
            "SELECT index_name FROM duckdb_indexes() "
            "WHERE index_name IN ('uq_hand_tags', 'uq_hand_notes')"
        ).fetchall()
    }
    if "uq_hand_tags" not in existing:
        dupes = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM hand_tags GROUP BY workspace_id, hand_id, tag HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        if dupes:
            logger.info("Removing duplicate hand_tags for %d (workspace, hand, tag) keys", dupes)
            conn.execute("""
                CREATE OR REPLACE TEMP TABLE _tags_dedup AS
                SELECT hand_id, tag, MIN(created_at) AS created_at, workspace_id
                FROM hand_tags GROUP BY workspace_id, hand_id, tag
            """)
            conn.execute("DELETE FROM hand_tags")
            conn.execute(
                "INSERT INTO hand_tags (hand_id, tag, created_at, workspace_id) "
                "SELECT hand_id, tag, created_at, workspace_id FROM _tags_dedup"
            )
            conn.execute("DROP TABLE _tags_dedup")
        conn.execute("CREATE UNIQUE INDEX uq_hand_tags ON hand_tags(workspace_id, hand_id, tag)")

    if "uq_hand_notes" not in existing:
        dupes = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT 1 FROM hand_notes GROUP BY workspace_id, hand_id HAVING COUNT(*) > 1
            )
        """).fetchone()[0]
        if dupes:
            logger.info("Removing duplicate hand_notes for %d (workspace, hand) keys", dupes)
            # Keep the most recently updated note
            conn.execute("""
                CREATE OR REPLACE TEMP TABLE _notes_dedup AS
                SELECT hand_id, arg_max(note, updated_at) AS note,
                       MAX(updated_at) AS updated_at, workspace_id
                FROM hand_notes GROUP BY workspace_id, hand_id
            """)
            conn.execute("DELETE FROM hand_notes")
            conn.execute(
                "INSERT INTO hand_notes (hand_id, note, updated_at, workspace_id) "
                "SELECT hand_id, note, updated_at, workspace_id FROM _notes_dedup"
            )
            conn.execute("DROP TABLE _notes_dedup")
        conn.execute("CREATE UNIQUE INDEX uq_hand_notes ON hand_notes(workspace_id, hand_id)")


def _ensure_hero_accounts(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hero_accounts (
            workspace_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            username VARCHAR NOT NULL,
            source VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (workspace_id, site_id, username, source)
        )
    """)
    _add_column_if_missing(conn, "workspaces", "hero_auto_detect", "BOOLEAN DEFAULT TRUE")
    conn.execute("UPDATE workspaces SET hero_auto_detect = TRUE WHERE hero_auto_detect IS NULL")
    from app.heroes import migrate_hero_accounts
    migrate_hero_accounts(conn)


def get_rebuild_status() -> dict:
    """Return current background rebuild status."""
    return dict(_rebuild_status)


def _migrate_config_sections(conn: duckdb.DuckDBPyConnection) -> None:
    """Columns + defaults added by the Configuration sections (idempotent)."""
    cols = {c[0] for c in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'player_classifications'"
    ).fetchall()}
    if "is_reg" not in cols:
        conn.execute("ALTER TABLE player_classifications ADD COLUMN is_reg BOOLEAN")
        if conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0] > 0:
            from app.player_classification import batch_update_player_types
            batch_update_player_types(conn)
    for col in ("is_single_person", "pinned"):
        conn.execute(f"ALTER TABLE player_identities ADD COLUMN IF NOT EXISTS {col} BOOLEAN DEFAULT FALSE")
    from app.config_sections import ensure_rebuild_fingerprint
    ensure_rebuild_fingerprint(conn)


def _migrate_auto_import_files(conn: duckdb.DuckDBPyConnection) -> None:
    """auto_import_files was keyed by path alone (M7 first cut): re-key by (workspace, path).
    The old rows belonged to the then configured target workspace (null = the first one)."""
    cols = {r[0] for r in conn.execute(
        "SELECT column_name FROM duckdb_columns() WHERE database_name = current_database() "
        "AND schema_name = current_schema() AND table_name = 'auto_import_files'"
    ).fetchall()}
    if "workspace_id" in cols or not cols:
        return
    import json
    ws = None
    row = conn.execute("SELECT value FROM settings WHERE key = 'config.auto_import'").fetchone()
    if row:
        try:
            ws = json.loads(row[0]).get("workspace_id")
        except (ValueError, AttributeError):
            ws = None
    if ws is None or not conn.execute("SELECT 1 FROM workspaces WHERE id = ?", [ws]).fetchone():
        ws = conn.execute("SELECT MIN(id) FROM workspaces").fetchone()[0] or 1
    conn.execute("BEGIN TRANSACTION")
    try:
        conn.execute("ALTER TABLE auto_import_files RENAME TO auto_import_files_old")
        conn.execute("""
            CREATE TABLE auto_import_files (
                workspace_id INTEGER NOT NULL,
                path VARCHAR NOT NULL,
                size BIGINT NOT NULL,
                mtime DOUBLE NOT NULL,
                "offset" BIGINT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, path)
            )
        """)
        conn.execute(
            'INSERT INTO auto_import_files SELECT ?, path, size, mtime, "offset", updated_at '
            "FROM auto_import_files_old", [ws],
        )
        conn.execute("DROP TABLE auto_import_files_old")
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise


def _check_stat_version(conn: duckdb.DuckDBPyConnection) -> None:
    """Auto-rebuild stats if STAT_VERSION has been bumped since last run.

    Runs in a background thread so the app is usable immediately.
    """
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'stat_version'"
    ).fetchone()
    db_version = int(row[0]) if row else 0

    hand_count = conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    if hand_count == 0 and db_version < STAT_VERSION:
        # Empty DB: everything imported from now on uses the current flags.
        # Without this, the first import is rebuilt again on the next launch.
        conn.execute(
            "INSERT OR REPLACE INTO settings VALUES ('stat_version', ?)",
            [str(STAT_VERSION)],
        )
        return
    if db_version >= STAT_VERSION:
        return

    logger.info(
        "Stat version changed (%d → %d), scheduling background rebuild for %d hands...",
        db_version, STAT_VERSION, hand_count,
    )

    _rebuild_status["active"] = True
    _rebuild_status["processed"] = 0
    _rebuild_status["total"] = hand_count

    def _bg_rebuild():
        try:
            with _lock:
                db = get_db()
                from app.api.import_hands import _run_rebuild_sync

                def _on_progress(processed: int, total: int):
                    _rebuild_status["processed"] = processed
                    _rebuild_status["total"] = total

                _run_rebuild_sync(db, on_progress=_on_progress)

                db.execute(
                    "INSERT OR REPLACE INTO settings VALUES ('stat_version', ?)",
                    [str(STAT_VERSION)],
                )
                from app.config_sections import store_rebuild_fingerprint
                store_rebuild_fingerprint(db)
                logger.info("Background rebuild complete, stat_version set to %d", STAT_VERSION)
        except Exception:
            logger.exception("Background rebuild failed")
        finally:
            from app import data_generation
            data_generation.bump()
            _rebuild_status["active"] = False

    t = threading.Thread(target=_bg_rebuild, daemon=True, name="stat-rebuild")
    t.start()
