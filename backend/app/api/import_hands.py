from fastapi import APIRouter, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from decimal import Decimal
from app.models import ImportResult
from app.db import get_db, db_lock, close_db, shutdown_requested, DB_PATH
from app.parsers.common import ParsedHand, _ZERO
from app.parsers import detect_parser, PARSER_BY_SITE_ID
from app.h2n.columns import H2N_COLUMN_NAMES
from app.stat_flags import compute_stat_flags
from app.money import compute_hand_money, net_round2, rake_columns
from app.player_classification import batch_update_player_types

import duckdb
import logging
import traceback
import zipfile
import io
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
import queue
import pyarrow as pa
from typing import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, Future
from contextlib import contextmanager

try:
    from app.equity import calculate_headsup_equity as _calc_equity
except ImportError:
    # Packaged builds have shipped without eval7's deps before; say so loudly
    # instead of silently falling back to actual winnings for all-in EV.
    logging.getLogger(__name__).warning(
        "eval7 unavailable: all-in EV will equal actual winnings", exc_info=True,
    )
    _calc_equity = None

router = APIRouter()

# ── Import session caches (cleared between import runs) ──
_player_cache: dict[tuple[int, str], int] = {}  # (site_id, username) -> player_id
_next_player_id: int | None = None
_next_hp_id: int | None = None

BATCH_SIZE = 2000

# ── Index definitions (dropped during bulk import, recreated after) ──
_BULK_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_hands_played_at ON hands(played_at)",
    "CREATE INDEX IF NOT EXISTS idx_hands_stakes ON hands(stakes)",
    "CREATE INDEX IF NOT EXISTS idx_hands_game_mode ON hands(game_mode)",
    "CREATE INDEX IF NOT EXISTS idx_hp_hand_id ON hand_players(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hp_player_id ON hand_players(player_id)",
    "CREATE INDEX IF NOT EXISTS idx_hp_position ON hand_players(position)",
    "CREATE INDEX IF NOT EXISTS idx_actions_hand_id ON actions(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hand_tags_hand_id ON hand_tags(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hand_tags_tag ON hand_tags(tag)",
    "CREATE INDEX IF NOT EXISTS idx_board_cards_hand_id ON board_cards(hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hp_player_hand ON hand_players(player_id, hand_id)",
    "CREATE INDEX IF NOT EXISTS idx_hp_hand_player ON hand_players(hand_id, player_id)",
    "CREATE INDEX IF NOT EXISTS idx_hp_player_position ON hand_players(player_id, position)",
    "CREATE INDEX IF NOT EXISTS idx_h_played_stakes ON hands(played_at, stakes)",
]

_INDEX_NAMES = [
    "idx_hands_played_at", "idx_hands_stakes", "idx_hands_game_mode",
    "idx_hp_hand_id", "idx_hp_player_id", "idx_hp_position",
    "idx_actions_hand_id", "idx_hand_tags_hand_id", "idx_hand_tags_tag",
    "idx_board_cards_hand_id",
    "idx_hp_player_hand", "idx_hp_hand_player", "idx_hp_player_position",
    "idx_h_played_stakes",
]


def _drop_indexes(db: duckdb.DuckDBPyConnection) -> None:
    """Drop all non-PK indexes for fast bulk loading."""
    for name in _INDEX_NAMES:
        db.execute(f"DROP INDEX IF EXISTS {name}")


def _create_indexes(db: duckdb.DuckDBPyConnection) -> None:
    """Recreate all indexes after bulk loading."""
    for stmt in _BULK_INDEXES:
        db.execute(stmt)

# ── Column keys for column-oriented PyArrow inserts ──
_HANDS_COLS = (
    "id", "site_id", "played_at", "game_type", "game_mode", "stakes",
    "sb_amount", "bb_amount", "table_name", "table_size", "button_seat", "raw_text",
    "cash_drop_received", "workspace_id", "rit_boards", "is_cashout",
)
_HP_BASE_COLS = (
    "id", "hand_id", "player_id", "seat", "position",
    "stack", "stack_bb", "card1", "card2",
    "won", "won_bb", "rake", "rake_bb", "jackpot", "jackpot_bb", "all_in_ev_bb",
    "workspace_id",
)
_STAT_FLAG_KEYS = (
    "vpip", "pfr", "three_bet", "three_bet_opp", "three_bet_opp_ip", "four_bet", "four_bet_opp",
    "fold_to_3bet", "fold_to_4bet",
    "open_raise", "open_raise_opp", "call_open_raise", "call_open_raise_opp", "limp", "squeeze", "five_bet",
    "steal_attempted", "faced_steal", "fold_to_steal", "call_steal", "three_bet_vs_steal",
    "saw_flop", "saw_turn", "saw_river", "went_to_showdown", "won_at_showdown",
    "cbet_flop", "cbet_flop_opp", "cbet_turn", "cbet_turn_opp", "cbet_river", "cbet_river_opp",
    "fold_to_cbet_flop", "fold_to_cbet_turn", "fold_to_cbet_river",
    "missed_cbet_flop", "missed_cbet_turn",
    "donk_bet_flop", "donk_bet_turn", "donk_bet_river",
    "flop_bets", "flop_raises", "flop_calls", "flop_checks", "flop_folds",
    "turn_bets", "turn_raises", "turn_calls", "turn_checks", "turn_folds",
    "river_bets", "river_raises", "river_calls", "river_checks", "river_folds",
    "steal_opp", "donk_bet_flop_opp", "donk_bet_turn_opp", "donk_bet_river_opp",
    "squeeze_opp", "five_bet_opp",
    "limp_fold", "four_bet_fold", "call_4bet", "is_3bet_pot",
    "call_cbet_flop", "raise_cbet_flop", "vs_missed_cbet_flop_opp",
    "preflop_allin_raise", "preflop_allin_call",
    "postflop_ip",
    "bb_defense", "bb_defense_opp", "iso_raise", "iso_raise_opp",
    "faced_squeeze", "fold_to_squeeze",
    "pot_type", "is_multiway",
) + H2N_COLUMN_NAMES  # h2n_pos, h2n_*_opp/case, is_winner, hv_* (app/h2n/CONTRACT.md)
_HP_ALL_COLS = _HP_BASE_COLS + _STAT_FLAG_KEYS
_BOARD_COLS = ("hand_id", "street", "card", "card_order", "workspace_id", "board_number")


def reset_import_cache() -> None:
    """Reset caches. Call before rebuild or when tables are wiped."""
    global _player_cache, _next_player_id, _next_hp_id
    _player_cache.clear()
    _next_player_id = None
    _next_hp_id = None


class ShutdownInProgress(Exception):
    """Raised inside a bulk write when the app is quitting."""


def _check_shutdown() -> None:
    if shutdown_requested():
        raise ShutdownInProgress("App is shutting down")


@contextmanager
def _bulk_write(db: duckdb.DuckDBPyConnection):
    """One transaction for a bulk load, with indexes dropped for speed.

    Any error (or an app shutdown) rolls the whole load back, so the DB is
    never left half-written, and the connection is never left inside an
    aborted transaction. On success the caller recreates the indexes.
    """
    _drop_indexes(db)
    db.execute("BEGIN TRANSACTION")
    db.execute("SET checkpoint_threshold = '10GB'")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        try:
            db.execute("ROLLBACK")
        except Exception:
            logging.getLogger(__name__).exception("ROLLBACK failed")
        # The cache may hold IDs that were just rolled back
        reset_import_cache()
        _create_indexes(db)
        raise
    finally:
        # The setting is per connection: left at 10GB, nothing would be
        # checkpointed for the rest of the session.
        db.execute("RESET checkpoint_threshold")


def _checkpoint_after_bulk(db: duckdb.DuckDBPyConnection) -> None:
    """Move a finished bulk load out of the WAL and into the DB file."""
    try:
        db.execute("CHECKPOINT")
    except Exception:
        logging.getLogger(__name__).exception("CHECKPOINT after bulk write failed")


def _init_counters(db: duckdb.DuckDBPyConnection) -> None:
    """Initialize ID counters from current DB max values (once per session)."""
    global _next_player_id, _next_hp_id
    if _next_player_id is None:
        _next_player_id = db.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM players"
        ).fetchone()[0]
    if _next_hp_id is None:
        _next_hp_id = db.execute(
            "SELECT COALESCE(MAX(id), 0) + 1 FROM hand_players"
        ).fetchone()[0]


def _batch_resolve_players(
    db: duckdb.DuckDBPyConnection,
    prepared: list,
) -> None:
    """Resolve player IDs for all hands in a batch. Creates new players as needed."""
    global _next_player_id

    # Collect (site_id, username) pairs
    all_pairs: set[tuple[int, str]] = set()
    for item in prepared:
        parsed = item[0]
        site_id = parsed.site_id
        for s in parsed.seats:
            all_pairs.add((site_id, s["username"]))

    uncached = [(sid, u) for sid, u in all_pairs if (sid, u) not in _player_cache]
    if not uncached:
        return

    # Existing players: one Arrow join for the whole batch (a 500-name IN list per chunk
    # was a fresh prepared statement each time, and a GIL round trip per chunk while the
    # parse worker runs). players is UNIQUE(site_id, username): at most one row per pair.
    pa_lookup = pa.table({  # noqa: F841 (read by DuckDB's replacement scan)
        "site_id": pa.array([sid for sid, _ in uncached], pa.int32()),
        "username": pa.array([u for _, u in uncached], pa.string()),
    })
    for sid, username, pid in db.execute(
        "SELECT p.site_id, p.username, p.id FROM players p "
        "JOIN pa_lookup n ON p.site_id = n.site_id AND p.username = n.username"
    ).fetchall():
        _player_cache[(sid, username)] = pid

    # Create missing players in bulk
    new_ids = []
    new_site_ids = []
    new_usernames = []
    for sid, u in uncached:
        if (sid, u) not in _player_cache:
            pid = _next_player_id
            _next_player_id += 1
            _player_cache[(sid, u)] = pid
            new_ids.append(pid)
            new_site_ids.append(sid)
            new_usernames.append(u)

    if new_ids:
        pa_new_players = pa.table({
            "id": new_ids, "site_id": new_site_ids, "username": new_usernames,
        })
        db.execute(
            "INSERT INTO players (id, site_id, username) "
            "SELECT id, site_id, username FROM pa_new_players"
        )


def _compute_financials(parsed: ParsedHand):
    """Per-player money for a hand, computed like Hand2Note (app/money.py).

    Returns (player_invested, money): investment by username (uncalled bets
    included) and the HandMoney with each player's won, rake and all-in EV.
    """
    money = compute_hand_money(parsed, with_ev=_calc_equity is not None)
    player_invested = {u: pm.invested for u, pm in money.players.items()}
    return player_invested, money


def _build_batch_arrays(
    db: duckdb.DuckDBPyConnection,
    prepared: list[tuple[ParsedHand, dict, tuple]],
    rebuild: bool = False,
    workspace_id: int = 1,
) -> tuple[pa.Table | None, pa.Table | None, pa.Table | None]:
    """Build PyArrow tables from a batch of (parsed, player_stats, financials) tuples.

    Pure CPU work — no DB writes. Safe to call from a thread.
    Returns (pa_hands, pa_hp, pa_board).  pa_hands is None when rebuild=True.
    """
    global _next_hp_id

    _init_counters(db)
    _batch_resolve_players(db, prepared)

    # Column-oriented building: one list per column
    hands_cols: dict[str, list] = {k: [] for k in _HANDS_COLS} if not rebuild else None
    hp_cols: dict[str, list] = {k: [] for k in _HP_ALL_COLS}
    board_cols: dict[str, list] = {k: [] for k in _BOARD_COLS}

    for parsed, player_stats, financials in prepared:
        bb_amount = parsed.bb_amount
        bb_f = float(bb_amount) if bb_amount else 0.0
        _player_invested, money = financials

        # Append to hands columns (skip during rebuild — hands table is preserved)
        if hands_cols is not None:
            hands_cols["id"].append(parsed.hand_id)
            hands_cols["site_id"].append(parsed.site_id)
            hands_cols["played_at"].append(parsed.played_at)
            hands_cols["game_type"].append(parsed.game_type)
            hands_cols["game_mode"].append(parsed.game_mode)
            hands_cols["stakes"].append(parsed.stakes)
            hands_cols["sb_amount"].append(float(parsed.sb_amount))
            hands_cols["bb_amount"].append(bb_f)
            hands_cols["table_name"].append(parsed.table_name)
            hands_cols["table_size"].append(parsed.table_size)
            hands_cols["button_seat"].append(parsed.button_seat)
            hands_cols["raw_text"].append(parsed.raw_text)
            hands_cols["cash_drop_received"].append(float(parsed.cash_drop_received))
            hands_cols["workspace_id"].append(workspace_id)
            hands_cols["rit_boards"].append(parsed.rit_boards)
            hands_cols["is_cashout"].append(parsed.is_cashout)

        for s in parsed.seats:
            uname = s["username"]
            pid = _player_cache[(parsed.site_id, uname)]
            cards = parsed.hero_cards.get(uname)
            card1 = cards[0] if cards else None
            card2 = cards[1] if cards else None
            # Money as Hand2Note computes it (app/money.py): a GG Cash Drop
            # counts as winnings, rake is split per pot, all-in EV per pot.
            pm = money.players.get(uname)
            if pm is not None:
                net_won = float(pm.won)
                rake, jackpot = rake_columns(parsed, pm)
                won_ev = pm.won_ev
            else:
                net_won = rake = jackpot = won_ev = 0.0
            # H2N reads winnings rounded to cents before dividing by the BB
            won_bb = net_round2(net_won) / bb_f if bb_f else 0.0
            rake_bb = rake / bb_f if bb_f else 0.0
            jackpot_bb = jackpot / bb_f if bb_f else 0.0
            stack_bb = float(s["stack"]) / bb_f if bb_f else 0.0
            ev_bb = won_ev / bb_f if bb_f else 0.0
            ps = player_stats[uname]

            hp_id = _next_hp_id
            _next_hp_id += 1

            # Append base columns
            hp_cols["id"].append(hp_id)
            hp_cols["hand_id"].append(parsed.hand_id)
            hp_cols["player_id"].append(pid)
            hp_cols["seat"].append(s["seat"])
            hp_cols["position"].append(s["position"])
            hp_cols["stack"].append(float(s["stack"]))
            hp_cols["stack_bb"].append(stack_bb)
            hp_cols["card1"].append(card1)
            hp_cols["card2"].append(card2)
            hp_cols["won"].append(net_won)
            hp_cols["won_bb"].append(won_bb)
            hp_cols["rake"].append(rake)
            hp_cols["rake_bb"].append(rake_bb)
            hp_cols["jackpot"].append(jackpot)
            hp_cols["jackpot_bb"].append(jackpot_bb)
            hp_cols["all_in_ev_bb"].append(ev_bb)
            hp_cols["workspace_id"].append(workspace_id)

            # Append stat flags
            for k in _STAT_FLAG_KEYS:
                hp_cols[k].append(ps[k])

        for street, cards in parsed.board_cards.items():
            for i, card in enumerate(cards):
                board_cols["hand_id"].append(parsed.hand_id)
                board_cols["street"].append(street)
                board_cols["card"].append(card)
                board_cols["card_order"].append(i + 1)
                board_cols["workspace_id"].append(workspace_id)
                board_cols["board_number"].append(1)

        for bn, extra_board in enumerate(parsed.extra_boards, start=2):
            for street, cards in extra_board.items():
                for i, card in enumerate(cards):
                    board_cols["hand_id"].append(parsed.hand_id)
                    board_cols["street"].append(street)
                    board_cols["card"].append(card)
                    board_cols["card_order"].append(i + 1)
                    board_cols["workspace_id"].append(workspace_id)
                    board_cols["board_number"].append(bn)

    pa_hands = pa.table(hands_cols) if hands_cols and hands_cols["id"] else None
    pa_hp = pa.table(hp_cols) if hp_cols["id"] else None
    pa_board = pa.table(board_cols) if board_cols["hand_id"] else None
    return pa_hands, pa_hp, pa_board


def _insert_arrays(
    db: duckdb.DuckDBPyConnection,
    pa_hands: pa.Table | None,
    pa_hp: pa.Table | None,
    pa_board: pa.Table | None,
    in_transaction: bool = False,
) -> None:
    """Insert pre-built PyArrow tables into the database.

    When in_transaction=True, caller manages the transaction — no BEGIN/COMMIT here.
    """
    if not in_transaction:
        db.execute("BEGIN TRANSACTION")
    try:
        if pa_hands is not None:
            db.execute("INSERT INTO hands BY NAME SELECT * FROM pa_hands")
        if pa_hp is not None:
            db.execute("INSERT INTO hand_players BY NAME SELECT * FROM pa_hp")
        if pa_board is not None:
            db.execute("INSERT INTO board_cards BY NAME SELECT * FROM pa_board")
        if not in_transaction:
            db.execute("COMMIT")
    except Exception:
        if not in_transaction:
            db.execute("ROLLBACK")
        raise


def _flush_batch(
    db: duckdb.DuckDBPyConnection,
    prepared: list[tuple[ParsedHand, dict, tuple]],
    rebuild: bool = False,
    in_transaction: bool = False,
    workspace_id: int = 1,
) -> tuple[int, int, list[str]]:
    """Bulk-insert a batch of (parsed, player_stats, financials) tuples using PyArrow column-oriented inserts.

    When rebuild=True, skips inserting into the hands table (it already has the data).
    When in_transaction=True, caller manages the transaction — no BEGIN/COMMIT per batch,
    and a failure is re-raised: DuckDB aborts the whole transaction on any error, and a
    later COMMIT then silently rolls everything back instead of failing.
    Returns (imported_count, error_count, error_details).
    """
    if not prepared:
        return 0, 0, []

    try:
        pa_hands, pa_hp, pa_board = _build_batch_arrays(db, prepared, rebuild=rebuild, workspace_id=workspace_id)
        _insert_arrays(db, pa_hands, pa_hp, pa_board, in_transaction=in_transaction)
        return len(prepared), 0, []
    except Exception as e:
        if in_transaction:
            raise
        traceback.print_exc()
        return 0, len(prepared), [f"Batch insert failed: {e}"]


def finalize_import(db: duckdb.DuckDBPyConnection, workspace_id: int | None = None) -> None:
    """Batch-update player first_seen/last_seen and player types. Call once after import.

    When workspace_id is provided, only recomputes player classifications for
    that workspace. When None (full rebuild), recomputes for all workspaces.
    """
    from app import data_generation
    data_generation.bump()  # invalidates cached report resolutions
    # The bulk (Arrow) insert and the composite-key migration leave imported_at NULL.
    db.execute("UPDATE hands SET imported_at = CURRENT_TIMESTAMP WHERE imported_at IS NULL"
               + (" AND workspace_id = ?" if workspace_id is not None else ""),
               [workspace_id] if workspace_id is not None else [])
    db.execute("""
        UPDATE players SET
            first_seen = sub.min_t,
            last_seen = sub.max_t
        FROM (
            SELECT hp.player_id, MIN(h.played_at) AS min_t, MAX(h.played_at) AS max_t
            FROM hand_players hp JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            GROUP BY hp.player_id
        ) sub
        WHERE players.id = sub.player_id
    """)
    batch_update_player_types(db, workspace_id=workspace_id)
    from app.heroes import detect_heroes
    detect_heroes(db, workspace_id)


def light_finalize(db: duckdb.DuckDBPyConnection, workspace_id: int) -> None:
    """The cheap part of finalize_import, for auto-import ticks: new hands become visible at
    once (data generation, imported_at, heroes). The workspace-wide player pass
    (first/last seen, classification) is deferred to finalize_import when the watcher is quiet.
    """
    from app import data_generation
    data_generation.bump()
    db.execute("UPDATE hands SET imported_at = CURRENT_TIMESTAMP WHERE imported_at IS NULL AND workspace_id = ?",
               [workspace_id])
    from app.heroes import detect_heroes
    detect_heroes(db, workspace_id)


def insert_parsed_hand(db: duckdb.DuckDBPyConnection, parsed: ParsedHand, workspace_id: int = 1) -> str:
    """Insert a single parsed hand. Computes stats internally.

    Kept for backward compatibility (used by tests).
    """
    player_stats = compute_stat_flags(parsed)
    financials = _compute_financials(parsed)
    imported, errors, details = _flush_batch(db, [(parsed, player_stats, financials)], workspace_id=workspace_id)
    if errors:
        raise RuntimeError(details[0])
    from app.heroes import detect_heroes
    detect_heroes(db, workspace_id)  # also invalidates the hero cache
    return parsed.hand_id


MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # total uncompressed text per request
MAX_ZIP_RATIO = 200  # per zip entry, uncompressed / compressed


def _read_uploads(files_data: list[tuple[str, bytes]]) -> list[str]:
    """Extract text contents from uploaded file data (handles .txt and .zip).

    Raises HTTPException 413 when the total uncompressed size exceeds MAX_UPLOAD_BYTES or a
    zip entry's compression ratio is implausible (zip bomb)."""
    from fastapi import HTTPException
    text_contents: list[str] = []
    total = 0

    def too_large():
        return HTTPException(status_code=413, detail="Upload too large (limit 500 MB uncompressed)")

    for fname, raw in files_data:
        lname = fname.lower()
        if lname.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for info in zf.infolist():
                        name = info.filename
                        if name.lower().endswith(".txt") and not name.startswith("__MACOSX"):
                            total += info.file_size
                            if total > MAX_UPLOAD_BYTES:
                                raise too_large()
                            if info.file_size > 1024 * 1024 and \
                                    info.file_size > MAX_ZIP_RATIO * max(info.compress_size, 1):
                                raise too_large()
                            text_contents.append(zf.read(info).decode("utf-8", errors="replace"))
            except zipfile.BadZipFile:
                pass
        elif lname.endswith(".txt"):
            total += len(raw)
            if total > MAX_UPLOAD_BYTES:
                raise too_large()
            text_contents.append(raw.decode("utf-8", errors="replace"))
    return text_contents


def _parse_batch(
    hand_texts: list[str],
    ids: list[str | None],
    existing_ids: set[str],
    parser=None,
    in_range=None,
    out_of_range: list[int] | None = None,
) -> tuple[list[tuple[ParsedHand, dict, tuple]], int, int, list[str], float, float, float]:
    """Parse+stats+financials for a chunk of hands. Pure CPU, no DB.

    Args:
        parser: Parser module with parse_hand_history(). If None, uses GGPoker parser.
        in_range: optional predicate on parsed.played_at (date range filter); hands
            outside it are dropped before stats and counted in out_of_range[0].

    Returns (prepared, dup_count, error_count, error_details, t_parse, t_stats, t_equity).
    """
    if parser is None:
        from app.parsers import ggpoker as parser

    prepared: list[tuple[ParsedHand, dict, tuple]] = []
    error_count = 0
    dup_count = 0
    error_details: list[str] = []
    t_parse = 0.0
    t_stats = 0.0
    t_equity = 0.0

    for hand_text, hid in zip(hand_texts, ids):
        if hid is None:
            error_count += 1
            error_details.append("Could not extract hand ID")
            continue
        if hid in existing_ids:
            dup_count += 1
            continue
        existing_ids.add(hid)
        try:
            t0 = time.perf_counter()
            parsed = parser.parse_hand_history(hand_text)
            if in_range is not None and not in_range(parsed.played_at):
                if out_of_range is not None:
                    out_of_range[0] += 1
                continue
            t1 = time.perf_counter()
            stats = compute_stat_flags(parsed)
            t2 = time.perf_counter()
            financials = _compute_financials(parsed)
            t3 = time.perf_counter()
            t_parse += t1 - t0
            t_stats += t2 - t1
            t_equity += t3 - t2
            prepared.append((parsed, stats, financials))
        except Exception as e:
            error_count += 1
            error_details.append(f"Hand parse error: {str(e)}")

    return prepared, dup_count, error_count, error_details, t_parse, t_stats, t_equity


@router.post("/import/files", response_model=ImportResult)
async def import_files(files: list[UploadFile] = File(...), workspace_id: int = 1):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    with db_lock():
        db = get_db()
        result = _process_hands(db, text_contents, workspace_id=workspace_id)
    return result


# ── Import jobs: every streaming import registers one so it can be cancelled ──
_jobs: dict[str, threading.Event] = {}
_jobs_lock = threading.Lock()


def _register_job() -> tuple[str, threading.Event]:
    job_id = uuid.uuid4().hex
    ev = threading.Event()
    with _jobs_lock:
        _jobs[job_id] = ev
    return job_id, ev


def _finish_job(job_id: str) -> None:
    with _jobs_lock:
        _jobs.pop(job_id, None)


def cancel_job(job_id: str) -> bool:
    """Ask a running import to stop after its current batch. False if unknown / finished."""
    with _jobs_lock:
        ev = _jobs.get(job_id)
    if ev is None:
        return False
    ev.set()
    return True


def active_import_jobs() -> int:
    """Streaming imports registered right now (auto-import skips its tick while > 0)."""
    with _jobs_lock:
        return len(_jobs)


@router.post("/import/jobs/{job_id}/cancel", status_code=204)
def cancel_import_job(job_id: str):
    """Cancel a running import. Never touches the DB (no write lock): it only flags the job."""
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail="Unknown or finished import job")
    return Response(status_code=204)


def import_date_filter(date_from: str | None, date_to: str | None):
    """played_at predicate for an import's date range (None = all time), with the
    `day_start_hour` app setting applied. Raises HTTPException 400 on a bad date."""
    if not date_from and not date_to:
        return None
    from app.app_settings import get_app_settings
    from app.date_filters import played_at_filter
    cur = get_db().cursor()
    try:
        day_start = get_app_settings(cur)["day_start_hour"]
    finally:
        cur.close()
    try:
        return played_at_filter(date_from, date_to, day_start)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date range: {e}")


def _acquire_lock_or_cancel(cancel: threading.Event) -> bool:
    """Wait for the write lock; give up (False) when the job is cancelled meanwhile."""
    lock = db_lock()
    while not lock.acquire(timeout=0.25):
        if cancel.is_set():
            return False
    return True


_STREAM_END = object()


def _job_stream(work: "Callable[[str, threading.Event, Callable[[dict], None]], None]") -> StreamingResponse:
    """NDJSON response for an import job that runs in ONE dedicated worker thread.

    work(job_id, cancel, emit) does the whole import in that thread: it takes the write
    lock, writes, and releases the lock itself (db._lock is an RLock: it must be released
    by the thread that acquired it). emit(dict) queues one NDJSON line. The generator handed
    to StreamingResponse only reads the queue: Starlette runs each next() of a sync
    generator in some threadpool thread (a different one each time, possibly), so the
    generator must never own the lock. The job is registered when the stream starts and
    removed when the worker ends. When the generator is closed early (client disconnect),
    its `finally` sets the job's cancel event: the worker stops after its current batch and
    releases the lock in its own thread.
    """
    def generate():
        job_id, cancel = _register_job()
        lines: queue.Queue = queue.Queue()

        def emit(msg: dict) -> None:
            lines.put(json.dumps(msg) + "\n")

        def run() -> None:
            try:
                work(job_id, cancel, emit)
            except Exception as e:
                logging.getLogger(__name__).exception("Import failed, rolled back")
                emit({"type": "error", "message": f"Import failed, nothing was imported: {e}"})
            finally:
                _finish_job(job_id)
                lines.put(_STREAM_END)

        threading.Thread(target=run, name=f"import-{job_id[:8]}", daemon=True).start()
        try:
            while True:
                line = lines.get()
                if line is _STREAM_END:
                    return
                yield line
        finally:
            cancel.set()  # no-op once the worker is done; stops it when the client went away

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _list_batches(all_hands: list[str], hand_parsers: list) -> "Iterator[list[tuple[str, object]]]":
    """Already-split hands as one source batch."""
    if all_hands:
        yield list(zip(all_hands, hand_parsers))


def _chunks(batches, unsupported: list[str]):
    """(hand texts, parser, source items consumed) chunks of <= BATCH_SIZE hands of one parser.

    One parser per chunk: a new chunk starts at BATCH_SIZE, when the site changes (several
    files from different sites in one upload) and at the end of each source batch (a source
    reading from a database: the import checks for cancel before reading the next one).
    Items whose parser is None (no parser knows the site) are reported in `unsupported` and
    counted in the chunk's consumed count.
    """
    for batch in batches:
        texts: list[str] = []
        parser = None
        consumed = 0
        for text, p in batch:
            consumed += 1
            if p is None:
                first = text.splitlines()[0][:80] if text else ""
                unsupported.append(f"Unsupported site: {first}")
                continue
            if texts and (p is not parser or len(texts) >= BATCH_SIZE):
                yield texts, parser, consumed - 1
                texts, consumed = [], 1
            parser = p
            texts.append(text)
        if texts or consumed:
            yield texts, parser, consumed


def _stream_import(
    all_hands: list[str],
    hand_parsers: list,
    file_count: int,
    workspace_id: int,
    pre_errors: list[str] | None = None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> StreamingResponse:
    """Import already-split hands, streaming NDJSON (start / progress / done | error).

    hand_parsers[i] is the parser module for all_hands[i]. See _stream_source.
    """
    return _stream_source(
        lambda: _list_batches(all_hands, hand_parsers), len(all_hands), file_count, workspace_id,
        pre_errors, date_from=date_from, date_to=date_to,
    )


def _stream_source(
    open_batches: "Callable[[], Iterator[list[tuple[str, object]]]]",
    total: int,
    file_count: int,
    workspace_id: int,
    pre_errors: list[str] | None = None,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> StreamingResponse:
    """Import hands from a lazy source, streaming NDJSON (start / progress / done | error).

    Contract: frontend/src/lib/import/types.ts section 1. open_batches() is called in the
    import worker thread (after the start line and once the write lock is held) and yields
    batches of (hand text, parser module or None = unsupported site); it may read from a
    database as it goes (the import checks for cancel between chunks), and is closed in the
    worker thread. total: hands in the source, for progress. pre_errors: problems found
    before parsing (counted as errors). date_from / date_to: inclusive ISO dates (day-start
    hour applied); hands outside are skipped and counted in `out_of_range`. Validated here,
    before streaming (400). The job is registered when the stream starts (first line:
    job_id) and removed when it ends; POST /api/import/jobs/{job_id}/cancel (or a client
    disconnect) stops it after the batch in progress (written hands stay, indexes +
    finalisation still run, done line has cancelled=true).
    """
    pre_errors = list(pre_errors or [])
    in_range = import_date_filter(date_from, date_to)

    def _done(t_start, imported, duplicates, errors, out_of_range, cancelled, error_details, extra):
        elapsed = time.perf_counter() - t_start
        hps = imported / elapsed if elapsed > 0 else 0
        return {
            "type": "done",
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "out_of_range": out_of_range,
            "cancelled": cancelled,
            "error_details": error_details[:20],
            "elapsed_ms": round(elapsed * 1000),
            "hands_per_sec": round(hps),
            **extra,
        }

    def work(job_id: str, cancel: threading.Event, emit) -> None:
        emit({
            "type": "start",
            "job_id": job_id,
            "total": total,
            "total_hands": total,  # pre-M7 field, kept for older clients
            "files": file_count,
        })

        t_start = time.perf_counter()
        if not _acquire_lock_or_cancel(cancel):
            emit(_done(t_start, 0, 0, len(pre_errors), 0, True, list(pre_errors), {}))
            return
        batches = None
        try:
            db = get_db()
            imported = 0
            duplicates = 0
            error_details: list[str] = list(pre_errors)
            errors = len(pre_errors)
            unsupported: list[str] = []
            out_of_range = [0]  # shared with the parse worker
            cancelled = False

            t_parse = 0.0
            t_stats = 0.0
            t_equity = 0.0
            t_db = 0.0

            # Duplicate check per chunk (scoped to workspace), in this thread (the parse
            # worker never touches the DB); ids parsed earlier in this import are added
            # by _parse_batch.
            existing_ids: set[str] = set()
            batches = open_batches()
            chunks = _chunks(batches, unsupported)

            def submit(executor, chunk):
                texts, parser, _ = chunk
                if not texts:
                    return None
                ids = [parser.extract_hand_id(h) for h in texts]
                existing_ids.update(_existing_hand_ids(db, ids, workspace_id))
                return executor.submit(
                    _parse_batch, texts, ids, existing_ids, parser, in_range, out_of_range,
                )

            processed = 0
            with _bulk_write(db), ThreadPoolExecutor(max_workers=1) as executor:
                chunk = next(chunks, None)
                parse_future: Future | None = submit(executor, chunk) if chunk else None

                while chunk is not None:
                    _check_shutdown()
                    if cancel.is_set():
                        cancelled = True
                        break
                    if parse_future is not None:
                        batch_prepared, batch_dups, batch_errs, batch_details, bp, bs, be = parse_future.result()
                    else:
                        batch_prepared, batch_dups, batch_errs, batch_details, bp, bs, be = [], 0, 0, [], 0, 0, 0
                    duplicates += batch_dups
                    errors += batch_errs
                    error_details.extend(batch_details)
                    t_parse += bp
                    t_stats += bs
                    t_equity += be
                    processed += chunk[2]

                    # Read + submit the next chunk for parsing (overlaps with the DB insert), unless cancelled
                    if cancel.is_set():
                        cancelled = True
                        nxt = None
                    else:
                        nxt = next(chunks, None)
                    parse_future = submit(executor, nxt) if nxt else None

                    # Flush current batch to DB
                    if batch_prepared:
                        t0 = time.perf_counter()
                        imp, errs, details = _flush_batch(db, batch_prepared, in_transaction=True, workspace_id=workspace_id)
                        t_db += time.perf_counter() - t0
                        imported += imp
                        errors += errs
                        error_details.extend(details)
                    if unsupported:
                        errors += len(unsupported)
                        error_details.extend(unsupported)
                        unsupported.clear()

                    # Progress update (every batch = BATCH_SIZE hands)
                    elapsed = time.perf_counter() - t_start
                    hps = imported / elapsed if elapsed > 0 else 0
                    emit({
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "imported": imported,
                        "duplicates": duplicates,
                        "errors": errors,
                        "out_of_range": out_of_range[0],
                        "elapsed_ms": round(elapsed * 1000),
                        "hands_per_sec": round(hps),
                    })
                    chunk = nxt

            # Recreate indexes (bulk build is faster than incremental)
            t0_idx = time.perf_counter()
            _create_indexes(db)
            t_idx = time.perf_counter() - t0_idx

            finalize_import(db, workspace_id=workspace_id)
            _checkpoint_after_bulk(db)
        finally:
            try:
                if batches is not None and hasattr(batches, "close"):
                    batches.close()  # e.g. the tracker DB connection, closed in this thread
            finally:
                db_lock().release()

        emit(_done(t_start, imported, duplicates, errors, out_of_range[0], cancelled, error_details, {
            "parse_ms": round(t_parse * 1000),
            "stats_ms": round(t_stats * 1000),
            "equity_ms": round(t_equity * 1000),
            "db_ms": round(t_db * 1000),
            "index_ms": round(t_idx * 1000),
        }))

    return _job_stream(work)


def _existing_hand_ids(db, ids: list[str | None], workspace_id: int) -> set[str]:
    """Which of these hand ids the workspace already has (one Arrow join)."""
    valid = [hid for hid in ids if hid is not None]
    if not valid:
        return set()
    pa_ids = pa.table({"id": pa.array(valid, pa.string())})  # noqa: F841 (replacement scan)
    rows = db.execute(
        "SELECT DISTINCT h.id FROM hands h JOIN pa_ids n ON h.id = n.id WHERE h.workspace_id = ?",
        [workspace_id],
    ).fetchall()
    return {r[0] for r in rows}


@router.post("/import/files/stream")
async def import_files_stream(
    files: list[UploadFile] = File(...),
    workspace_id: int = 1,
    date_from: str | None = None,
    date_to: str | None = None,
):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    # Per-file parser detection + hand splitting
    all_hands: list[str] = []
    hand_parsers: list = []  # parallel list: parser module for each hand
    skipped_files = 0
    for content in text_contents:
        parser = detect_parser(content[:500])
        if parser is None:
            skipped_files += 1
            continue
        for h in parser.split_hands(content):
            h = h.strip()
            if h:
                all_hands.append(h)
                hand_parsers.append(parser)

    return _stream_import(
        all_hands, hand_parsers, len(text_contents), workspace_id,
        date_from=date_from, date_to=date_to,
    )


def import_hand_texts(db, hands: list[tuple[str, object]], workspace_id: int, *,
                      full_finalize: bool = True) -> dict:
    """Import a small set of (hand_text, parser) without streaming and without dropping
    indexes (auto-import: a few hands per tick). Caller holds the write lock.

    Same pipeline as file import: dedup by id within the workspace, parse, stats, money,
    one transaction, then finalize_import (bumps the data generation). Raises on a failed
    insert (rolled back, nothing written). Returns imported / duplicates / errors counts.
    """
    texts = [h for h, _ in hands]
    ids = [p.extract_hand_id(h) for h, p in hands]
    existing_ids = _existing_hand_ids(db, ids, workspace_id)
    prepared: list = []
    duplicates = errors = 0
    error_details: list[str] = []
    # Group consecutive hands by parser (one parser per _parse_batch call)
    start = 0
    for i in range(1, len(hands) + 1):
        if i == len(hands) or hands[i][1] is not hands[start][1]:
            prep, dups, errs, details, *_ = _parse_batch(
                texts[start:i], ids[start:i], existing_ids, hands[start][1],
            )
            prepared.extend(prep)
            duplicates += dups
            errors += errs
            error_details.extend(details)
            start = i
    imported = 0
    if prepared:
        db.execute("BEGIN TRANSACTION")
        try:
            imported, _, _ = _flush_batch(db, prepared, in_transaction=True, workspace_id=workspace_id)
            db.execute("COMMIT")
        except BaseException:
            try:
                db.execute("ROLLBACK")
            except Exception:
                logging.getLogger(__name__).exception("ROLLBACK failed")
            reset_import_cache()
            raise
        if full_finalize:
            finalize_import(db, workspace_id=workspace_id)
        else:
            light_finalize(db, workspace_id)
    return {"imported": imported, "duplicates": duplicates, "errors": errors,
            "error_details": error_details[:20]}


def _process_hands(db, text_contents: list[str], workspace_id: int = 1) -> ImportResult:
    """Process hands from text contents (non-streaming)."""
    total_imported = 0
    total_duplicates = 0
    total_errors = 0
    error_details: list[str] = []

    # Per-file parser detection + hand splitting
    all_hands: list[str] = []
    all_ids: list[str | None] = []
    hand_parsers_list: list = []
    for content in text_contents:
        parser = detect_parser(content[:500])
        if parser is None:
            continue
        for hand_text in parser.split_hands(content):
            hand_text = hand_text.strip()
            if hand_text:
                all_hands.append(hand_text)
                all_ids.append(parser.extract_hand_id(hand_text))
                hand_parsers_list.append(parser)

    existing_ids = _existing_hand_ids(db, all_ids, workspace_id)

    with _bulk_write(db):
        total_imported, total_duplicates, total_errors = _process_hands_in_txn(
            db, all_hands, all_ids, hand_parsers_list, existing_ids,
            error_details, total_duplicates, total_errors, workspace_id,
        )

    _create_indexes(db)
    finalize_import(db, workspace_id=workspace_id)
    _checkpoint_after_bulk(db)

    return ImportResult(
        imported=total_imported,
        duplicates=total_duplicates,
        errors=total_errors,
        error_details=error_details[:20],
    )


def _process_hands_in_txn(
    db, all_hands, all_ids, hand_parsers_list, existing_ids,
    error_details, total_duplicates, total_errors, workspace_id,
) -> tuple[int, int, int]:
    total_imported = 0
    pending: list[tuple[ParsedHand, dict, tuple]] = []

    for i, hand_text in enumerate(all_hands):
        hid = all_ids[i]
        if hid is None:
            total_errors += 1
            error_details.append("Could not extract hand ID from hand")
            continue
        if hid in existing_ids:
            total_duplicates += 1
            continue
        existing_ids.add(hid)
        try:
            parsed = hand_parsers_list[i].parse_hand_history(hand_text)
            stats = compute_stat_flags(parsed)
            financials = _compute_financials(parsed)
            pending.append((parsed, stats, financials))
        except Exception as e:
            total_errors += 1
            error_details.append(f"Hand parse error: {str(e)}")

        if len(pending) >= BATCH_SIZE:
            _check_shutdown()
            imp, errs, details = _flush_batch(db, pending, in_transaction=True, workspace_id=workspace_id)
            total_imported += imp
            total_errors += errs
            error_details.extend(details)
            pending = []

    if pending:
        imp, errs, details = _flush_batch(db, pending, in_transaction=True, workspace_id=workspace_id)
        total_imported += imp
        total_errors += errs
        error_details.extend(details)

    return total_imported, total_duplicates, total_errors


@router.post("/import/rebuild")
async def rebuild_hands():
    """Re-parse all hands from stored raw_text in a background thread.

    Rebuilds ALL workspaces (child rows are deleted globally and recreated
    with the correct workspace_id for each hand).
    Returns immediately. Poll GET /api/health for progress.
    """
    import threading
    from app.db import get_rebuild_status, _rebuild_status, STAT_VERSION

    status = get_rebuild_status()
    if status["active"]:
        return {"status": "already_running"}

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    if total == 0:
        return {"status": "empty"}

    _rebuild_status["active"] = True
    _rebuild_status["processed"] = 0
    _rebuild_status["total"] = total

    def _bg_rebuild():
        try:
            with db_lock():
                conn = get_db()

                def _on_progress(processed: int, t: int):
                    _rebuild_status["processed"] = processed
                    _rebuild_status["total"] = t

                _run_rebuild_sync(conn, on_progress=_on_progress)

                conn.execute(
                    "INSERT OR REPLACE INTO settings VALUES ('stat_version', ?)",
                    [str(STAT_VERSION)],
                )
                from app.config_sections import store_rebuild_fingerprint
                store_rebuild_fingerprint(conn)
                logging.getLogger(__name__).info("User-triggered rebuild complete")
        except Exception:
            logging.getLogger(__name__).exception("Rebuild failed")
        finally:
            from app import data_generation
            data_generation.bump()
            _rebuild_status["active"] = False

    t = threading.Thread(target=_bg_rebuild, daemon=True, name="user-rebuild")
    t.start()

    return {"status": "started", "total": total}


def _run_rebuild_sync(db, on_progress: 'Callable[[int, int], None] | None' = None) -> None:
    """Synchronous rebuild for auto-upgrade. Called from db.py at startup (lock already held)."""
    total = db.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    if total == 0:
        return

    all_rows = db.execute(
        "SELECT id, workspace_id, site_id, raw_text FROM hands ORDER BY played_at ASC, id ASC"
    ).fetchall()

    reset_import_cache()
    with _bulk_write(db):
        # Inside the transaction: if the rebuild fails or the app quits
        # midway, the old rows come back instead of empty stats tables.
        db.execute("DELETE FROM player_classifications")
        db.execute("DELETE FROM actions")
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        # Keep players table intact — player_aliases has FK references, and
        # _batch_resolve_players will look up existing players from the DB.
        imported, errors, t_start = _rebuild_rows(db, all_rows, total, on_progress)

    _create_indexes(db)
    # Full rebuild: recompute classifications for all workspaces
    finalize_import(db, workspace_id=None)
    _checkpoint_after_bulk(db)

    elapsed = time.perf_counter() - t_start
    hps = imported / elapsed if elapsed > 0 else 0
    logging.getLogger(__name__).info(
        "Auto-rebuild complete: %d hands in %.1fs (%.0f h/s, %d errors)",
        imported, elapsed, hps, errors,
    )


def _rebuild_rows(db, all_rows, total, on_progress) -> tuple[int, int, float]:
    imported = 0
    errors = 0
    processed = 0
    t_start = time.perf_counter()

    chunks = [all_rows[ci:ci + BATCH_SIZE] for ci in range(0, total, BATCH_SIZE)]

    for ci, chunk in enumerate(chunks):
        _check_shutdown()
        # Group prepared items by workspace_id so each flush gets the correct one.
        # Within a chunk, hands from different workspaces may be interleaved
        # (e.g. same hand_id existing in ws1 and ws2).
        prepared_by_ws: dict[int, list] = {}
        rit_updates: list[tuple] = []  # (hand_id, rit_boards, is_cashout)
        for hand_id, ws_id, site_id, raw_text in chunk:
            try:
                parser = PARSER_BY_SITE_ID.get(site_id)
                if parser is None:
                    errors += 1
                    continue
                parsed = parser.parse_hand_history(raw_text)
                stats = compute_stat_flags(parsed)
                financials = _compute_financials(parsed)
                prepared_by_ws.setdefault(ws_id, []).append(
                    (parsed, stats, financials)
                )
                rit_updates.append((
                    hand_id, parsed.rit_boards, parsed.is_cashout,
                    parsed.stakes, float(parsed.sb_amount), float(parsed.bb_amount),
                ))
            except Exception:
                errors += 1
                traceback.print_exc()

        for ws_id, ws_prepared in prepared_by_ws.items():
            if ws_prepared:
                imp, errs, _ = _flush_batch(
                    db, ws_prepared, rebuild=True, in_transaction=True,
                    workspace_id=ws_id,
                )
                imported += imp
                errors += errs

        # Update hands table with re-parsed values (stakes may change if
        # corruption detection improved, rit_boards/is_cashout may change too)
        if rit_updates:
            _ids = [r[0] for r in rit_updates]
            _rits = [r[1] for r in rit_updates]
            _cos = [r[2] for r in rit_updates]
            _stakes = [r[3] for r in rit_updates]
            _sbs = [r[4] for r in rit_updates]
            _bbs = [r[5] for r in rit_updates]
            pa_rit = pa.table({
                "hid": _ids, "rit": _rits, "co": _cos,
                "st": _stakes, "sb": _sbs, "bb": _bbs,
            })
            db.execute(
                "UPDATE hands SET rit_boards = pa_rit.rit, is_cashout = pa_rit.co, "
                "stakes = pa_rit.st, sb_amount = pa_rit.sb, bb_amount = pa_rit.bb "
                "FROM pa_rit WHERE hands.id = pa_rit.hid"
            )

        processed += len(chunk)
        if on_progress:
            on_progress(processed, total)

        if (ci + 1) % 5 == 0 or ci == len(chunks) - 1:
            elapsed = time.perf_counter() - t_start
            hps = imported / elapsed if elapsed > 0 else 0
            logging.getLogger(__name__).info(
                "Auto-rebuild: %d/%d hands (%.0f h/s)", imported, total, hps,
            )

    return imported, errors, t_start


@router.post("/import/clear")
async def clear_hands(workspace_id: int = 1):
    with db_lock():
        db = get_db()
        # Delete data scoped to workspace
        db.execute(
            "DELETE FROM hand_tags WHERE hand_id IN (SELECT id FROM hands WHERE workspace_id = ?) AND workspace_id = ?",
            [workspace_id, workspace_id],
        )
        db.execute(
            "DELETE FROM hand_notes WHERE hand_id IN (SELECT id FROM hands WHERE workspace_id = ?) AND workspace_id = ?",
            [workspace_id, workspace_id],
        )
        db.execute(
            "DELETE FROM board_cards WHERE hand_id IN (SELECT id FROM hands WHERE workspace_id = ?) AND workspace_id = ?",
            [workspace_id, workspace_id],
        )
        db.execute(
            "DELETE FROM actions WHERE hand_id IN (SELECT id FROM hands WHERE workspace_id = ?) AND workspace_id = ?",
            [workspace_id, workspace_id],
        )
        db.execute(
            "DELETE FROM hand_players WHERE hand_id IN (SELECT id FROM hands WHERE workspace_id = ?) AND workspace_id = ?",
            [workspace_id, workspace_id],
        )
        db.execute("DELETE FROM hands WHERE workspace_id = ?", [workspace_id])
        from app.marked_hands import delete_workspace_marks
        delete_workspace_marks(db, workspace_id)
        db.execute("DELETE FROM player_classifications WHERE workspace_id = ?", [workspace_id])
        # Manual hero accounts stay; auto-detected ones go with the hands
        db.execute(
            "DELETE FROM hero_accounts WHERE workspace_id = ? AND source = 'auto'",
            [workspace_id],
        )
        from app.heroes import invalidate_hero_cache
        invalidate_hero_cache(workspace_id)
        reset_import_cache()
        # Auto-import forgets how far it read the watched files: they are read again
        from app import auto_import
        auto_import.forget_workspace(db, workspace_id)
        from app import data_generation
        data_generation.bump()
    return {"status": "ok"}


@router.get("/import/export")
async def export_database():
    """Export the database as a downloadable .duckdb file."""
    tmp_dir = tempfile.mkdtemp(prefix="ohm-export-")
    tmp_path = os.path.join(tmp_dir, "export.duckdb")
    with db_lock():
        # Close (and checkpoint) before copying: on Windows the open DB file
        # can't be read through another handle (WinError 32). COPY FROM
        # DATABASE isn't an option: it copies tables in an order that breaks
        # foreign keys. Other requests wait on the lock until we reopen.
        close_db()
        try:
            shutil.copy2(str(DB_PATH), tmp_path)
        finally:
            get_db()

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"ohm-backup-{timestamp}.duckdb"

    def cleanup():
        shutil.rmtree(tmp_dir, ignore_errors=True)

    from starlette.background import BackgroundTask
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=filename,
        background=BackgroundTask(cleanup),
    )


@router.post("/import/database")
async def import_database(file: UploadFile = File(...)):
    """Import/restore a .duckdb database file, replacing the current one."""
    # Save upload to temp file
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".duckdb")
    try:
        with os.fdopen(tmp_fd, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)

        # Validate: open as read-only and check it has a hands table
        try:
            test_conn = duckdb.connect(tmp_path, read_only=True)
            hand_count = test_conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
            test_conn.close()
        except Exception as e:
            raise ValueError(f"Invalid database file: {e}")

        with db_lock():
            close_db()
            # Backup current file
            bak_path = str(DB_PATH) + ".bak"
            if DB_PATH.exists():
                shutil.copy2(str(DB_PATH), bak_path)
            # Replace with uploaded file
            shutil.move(tmp_path, str(DB_PATH))
            tmp_path = None  # prevent cleanup
            # Re-open (triggers init_schema + sequence sync)
            db = get_db()
            reset_import_cache()
            # The restored file positions don't describe the restored hands: start over
            from app import auto_import
            auto_import.forget_all(db)
            from app.heroes import invalidate_hero_cache
            invalidate_hero_cache()
            from app import data_generation
            data_generation.bump()

        return {"status": "ok", "hands": hand_count}
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"Database import failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


