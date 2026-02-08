import atexit
import duckdb
import os
import time
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "poker.duckdb"

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()


def get_db() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        with _lock:
            if _conn is None:
                DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                for attempt in range(10):
                    try:
                        _conn = duckdb.connect(str(DB_PATH))
                        break
                    except duckdb.IOException:
                        if attempt < 9:
                            time.sleep(1)
                        else:
                            raise
                init_schema(_conn)
                atexit.register(close_db)
    return _conn


def db_lock() -> threading.Lock:
    """Return the lock that must be held during any DB operation."""
    return _lock


def close_db():
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
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
            stakes VARCHAR NOT NULL,
            sb_amount DECIMAL NOT NULL,
            bb_amount DECIMAL NOT NULL,
            table_name VARCHAR,
            table_size INTEGER,
            button_seat INTEGER,
            raw_text TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_players (
            id INTEGER PRIMARY KEY,
            hand_id VARCHAR REFERENCES hands(id),
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
            four_bet BOOLEAN DEFAULT FALSE,
            four_bet_opp BOOLEAN DEFAULT FALSE,
            fold_to_3bet BOOLEAN,
            fold_to_4bet BOOLEAN,
            open_raise BOOLEAN DEFAULT FALSE,
            open_raise_opp BOOLEAN DEFAULT FALSE,
            call_open_raise BOOLEAN DEFAULT FALSE,
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
            vs_missed_cbet_flop_opp BOOLEAN DEFAULT FALSE
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_hand_players START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id INTEGER PRIMARY KEY,
            hand_id VARCHAR REFERENCES hands(id),
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
            hand_id VARCHAR REFERENCES hands(id),
            street VARCHAR NOT NULL,
            card VARCHAR NOT NULL,
            card_order INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR PRIMARY KEY,
            value VARCHAR NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_tags (
            hand_id VARCHAR REFERENCES hands(id),
            tag VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (hand_id, tag)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS hand_notes (
            hand_id VARCHAR PRIMARY KEY REFERENCES hands(id),
            note TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
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
    ]:
        try:
            conn.execute(f"ALTER TABLE hand_players ADD COLUMN {col} {default}")
        except duckdb.CatalogException:
            pass

    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_played_at ON hands(played_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_stakes ON hands(stakes)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_hand_id ON hand_players(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_player_id ON hand_players(player_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hp_position ON hand_players(position)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_actions_hand_id ON actions(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hand_tags_hand_id ON hand_tags(hand_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hand_tags_tag ON hand_tags(tag)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_board_cards_hand_id ON board_cards(hand_id)")

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
