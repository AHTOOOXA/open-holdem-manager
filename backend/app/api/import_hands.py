from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from decimal import Decimal
from app.models import ImportResult
from app.db import get_db, db_lock, close_db, DB_PATH
from app.parsers.common import ParsedHand, _ZERO
from app.parsers import detect_parser, PARSER_BY_SITE_ID
from app.stat_flags import compute_stat_flags
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
import time
import pyarrow as pa
from concurrent.futures import ThreadPoolExecutor, Future

try:
    from app.equity import calculate_headsup_equity as _calc_equity
except ImportError:
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
)
_HP_ALL_COLS = _HP_BASE_COLS + _STAT_FLAG_KEYS
_BOARD_COLS = ("hand_id", "street", "card", "card_order", "workspace_id", "board_number")


def reset_import_cache() -> None:
    """Reset caches. Call before rebuild or when tables are wiped."""
    global _player_cache, _next_player_id, _next_hp_id
    _player_cache.clear()
    _next_player_id = None
    _next_hp_id = None


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

    # Batch lookup existing players, grouped by site_id
    by_site: dict[int, list[str]] = {}
    for sid, u in uncached:
        by_site.setdefault(sid, []).append(u)

    for sid, usernames in by_site.items():
        for i in range(0, len(usernames), 500):
            batch = usernames[i:i + 500]
            placeholders = ",".join(["?"] * len(batch))
            rows = db.execute(
                f"SELECT username, id FROM players WHERE site_id = ? AND username IN ({placeholders})",
                [sid] + batch,
            ).fetchall()
            for username, pid in rows:
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


_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))
_STREET_ORDER = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}


def _compute_financials(parsed: ParsedHand):
    """Compute per-player investment and all-in EV for a parsed hand.

    Returns (player_invested, all_in_ev_bb_map).
    """
    player_invested = {s["username"]: _ZERO for s in parsed.seats}

    for street in _STREETS:
        street_put_in: dict[str, Decimal] = {}
        for a in parsed.actions_by_street[street]:
            uname = a["username"]
            action = a["action"]
            amt = a["amount"]

            if action in _INVEST_ACTIONS:
                street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
                player_invested[uname] += amt
            elif action == "raise":
                already_in = street_put_in.get(uname, _ZERO)
                increment = amt - already_in
                if increment > 0:
                    player_invested[uname] += increment
                street_put_in[uname] = amt

    # All-in EV calculation
    all_in_ev_bb_map: dict[str, float] = {}

    all_in_street = None
    for street in _STREETS:
        for a in parsed.actions_by_street[street]:
            if a["is_all_in"]:
                all_in_street = street
                break
        if all_in_street is not None:
            break

    if all_in_street is not None and _calc_equity:
        players_in = set(s["username"] for s in parsed.seats)
        folded = set()
        for st in _STREETS:
            for a in parsed.actions_by_street[st]:
                if a["action"] == "fold":
                    folded.add(a["username"])
        remaining = players_in - folded
        real_showdown = len(remaining) >= 2 and (
            parsed.in_showdown or parsed.went_to_showdown_players
        )

        if real_showdown and len(remaining) == 2:
            board_at = []
            if _STREET_ORDER[all_in_street] >= 1:
                board_at.extend(parsed.board_cards["flop"])
            if _STREET_ORDER[all_in_street] >= 2:
                board_at.extend(parsed.board_cards["turn"])
            if _STREET_ORDER[all_in_street] >= 3:
                board_at.extend(parsed.board_cards["river"])

            if 5 - len(board_at) > 0:
                pl = list(remaining)
                if pl[0] in parsed.hero_cards and pl[1] in parsed.hero_cards:
                    try:
                        p1, p2 = pl
                        p1_eq = _calc_equity(
                            parsed.hero_cards[p1], parsed.hero_cards[p2], board_at
                        )
                        p2_eq = 1.0 - p1_eq
                        p1_net = float(player_invested[p1]) - float(
                            parsed.uncalled_returns.get(p1, _ZERO)
                        )
                        p2_net = float(player_invested[p2]) - float(
                            parsed.uncalled_returns.get(p2, _ZERO)
                        )
                        total_risk = (
                            sum(float(v) for v in player_invested.values())
                            - sum(float(v) for v in parsed.uncalled_returns.values())
                        )
                        dist = total_risk - float(parsed.total_rake)
                        bb = float(parsed.bb_amount)
                        all_in_ev_bb_map[p1] = (p1_eq * dist - p1_net) / bb
                        all_in_ev_bb_map[p2] = (p2_eq * dist - p2_net) / bb
                    except Exception:
                        pass

    return player_invested, all_in_ev_bb_map


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
        num_winners = len(parsed.collected)
        per_player_rake = (
            parsed.total_rake / max(num_winners, 1)
            if parsed.total_rake else _ZERO
        )
        per_player_jackpot = (
            parsed.total_jackpot / max(num_winners, 1)
            if parsed.total_jackpot else _ZERO
        )
        player_invested, all_in_ev_bb_map = financials

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
            gross = parsed.collected.get(uname, Decimal("0"))
            uncalled = parsed.uncalled_returns.get(uname, Decimal("0"))
            invested = player_invested.get(uname, Decimal("0"))
            net_won = float(gross + uncalled - invested)
            rake = float(per_player_rake) if uname in parsed.collected else 0.0
            jackpot = float(per_player_jackpot) if uname in parsed.collected else 0.0
            won_bb = net_won / bb_f if bb_f else 0.0
            rake_bb = rake / bb_f if bb_f else 0.0
            jackpot_bb = jackpot / bb_f if bb_f else 0.0
            stack_bb = float(s["stack"]) / bb_f if bb_f else 0.0
            ev_bb = all_in_ev_bb_map.get(uname, won_bb)
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
    When in_transaction=True, caller manages the transaction — no BEGIN/COMMIT per batch.
    Returns (imported_count, error_count, error_details).
    """
    if not prepared:
        return 0, 0, []

    try:
        pa_hands, pa_hp, pa_board = _build_batch_arrays(db, prepared, rebuild=rebuild, workspace_id=workspace_id)
        _insert_arrays(db, pa_hands, pa_hp, pa_board, in_transaction=in_transaction)
        return len(prepared), 0, []
    except Exception as e:
        traceback.print_exc()
        return 0, len(prepared), [f"Batch insert failed: {e}"]


def finalize_import(db: duckdb.DuckDBPyConnection, workspace_id: int | None = None) -> None:
    """Batch-update player first_seen/last_seen and player types. Call once after import.

    When workspace_id is provided, only recomputes player classifications for
    that workspace. When None (full rebuild), recomputes for all workspaces.
    """
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


def insert_parsed_hand(db: duckdb.DuckDBPyConnection, parsed: ParsedHand, workspace_id: int = 1) -> str:
    """Insert a single parsed hand. Computes stats internally.

    Kept for backward compatibility (used by tests).
    """
    player_stats = compute_stat_flags(parsed)
    financials = _compute_financials(parsed)
    imported, errors, details = _flush_batch(db, [(parsed, player_stats, financials)], workspace_id=workspace_id)
    if errors:
        raise RuntimeError(details[0])
    return parsed.hand_id


def _read_uploads(files_data: list[tuple[str, bytes]]) -> list[str]:
    """Extract text contents from uploaded file data (handles .txt and .zip)."""
    text_contents: list[str] = []
    for fname, raw in files_data:
        if fname.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".txt") and not name.startswith("__MACOSX"):
                            text_contents.append(
                                zf.read(name).decode("utf-8", errors="replace")
                            )
            except zipfile.BadZipFile:
                pass
        elif fname.endswith(".txt"):
            text_contents.append(raw.decode("utf-8", errors="replace"))
    return text_contents


def _parse_batch(
    hand_texts: list[str],
    ids: list[str | None],
    existing_ids: set[str],
    parser=None,
) -> tuple[list[tuple[ParsedHand, dict, tuple]], int, int, list[str], float, float, float]:
    """Parse+stats+financials for a chunk of hands. Pure CPU, no DB.

    Args:
        parser: Parser module with parse_hand_history(). If None, uses GGPoker parser.

    Returns (prepared, new_count, error_count, error_details, t_parse, t_stats, t_equity).
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


@router.post("/import/files/stream")
async def import_files_stream(files: list[UploadFile] = File(...), workspace_id: int = 1):
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

    total = len(all_hands)
    file_count = len(text_contents)

    def generate():
        yield json.dumps({
            "type": "start",
            "total_hands": total,
            "files": file_count,
        }) + "\n"

        with db_lock():
            db = get_db()
            imported = 0
            duplicates = 0
            errors = 0
            error_details: list[str] = []

            t_start = time.perf_counter()
            t_parse = 0.0
            t_stats = 0.0
            t_equity = 0.0
            t_db = 0.0

            # Bulk duplicate check (scoped to workspace)
            all_ids = [hand_parsers[i].extract_hand_id(h) for i, h in enumerate(all_hands)]
            existing_ids: set[str] = set()
            valid_ids = [hid for hid in all_ids if hid is not None]
            if valid_ids:
                for j in range(0, len(valid_ids), 500):
                    batch = valid_ids[j:j + 500]
                    placeholders = ",".join(["?"] * len(batch))
                    rows = db.execute(
                        f"SELECT id FROM hands WHERE workspace_id = ? AND id IN ({placeholders})",
                        [workspace_id] + batch,
                    ).fetchall()
                    existing_ids.update(r[0] for r in rows)

            # Drop indexes for fast bulk loading
            _drop_indexes(db)

            # Single transaction + suppress auto-checkpoint for bulk load
            db.execute("BEGIN TRANSACTION")
            db.execute("SET checkpoint_threshold = '10GB'")

            # Split hands into BATCH_SIZE chunks for pipeline parallelism
            chunks: list[tuple[list[str], list[str | None], object]] = []
            for ci in range(0, total, BATCH_SIZE):
                chunk_texts = all_hands[ci:ci + BATCH_SIZE]
                chunk_ids = all_ids[ci:ci + BATCH_SIZE]
                # Use the parser of the first hand in the chunk (all hands from
                # one file share a parser, and chunks rarely span file boundaries)
                chunk_parser = hand_parsers[ci] if ci < len(hand_parsers) else None
                chunks.append((chunk_texts, chunk_ids, chunk_parser))

            processed = 0
            with ThreadPoolExecutor(max_workers=1) as executor:
                # Start parsing first batch
                parse_future: Future | None = None
                if chunks:
                    parse_future = executor.submit(
                        _parse_batch, chunks[0][0], chunks[0][1], existing_ids, chunks[0][2]
                    )

                for ci in range(len(chunks)):
                    # Wait for current parse result
                    batch_prepared, batch_dups, batch_errs, batch_details, bp, bs, be = parse_future.result()
                    duplicates += batch_dups
                    errors += batch_errs
                    error_details.extend(batch_details)
                    t_parse += bp
                    t_stats += bs
                    t_equity += be

                    # Submit next batch for parsing (overlaps with DB insert)
                    if ci + 1 < len(chunks):
                        parse_future = executor.submit(
                            _parse_batch, chunks[ci + 1][0], chunks[ci + 1][1], existing_ids, chunks[ci + 1][2]
                        )
                    else:
                        parse_future = None

                    # Flush current batch to DB
                    if batch_prepared:
                        t0 = time.perf_counter()
                        imp, errs, details = _flush_batch(db, batch_prepared, in_transaction=True, workspace_id=workspace_id)
                        t_db += time.perf_counter() - t0
                        imported += imp
                        errors += errs
                        error_details.extend(details)

                    # Progress update (every batch = BATCH_SIZE hands)
                    processed += len(chunks[ci][0])
                    elapsed = time.perf_counter() - t_start
                    hps = imported / elapsed if elapsed > 0 else 0
                    yield json.dumps({
                        "type": "progress",
                        "processed": processed,
                        "total": total,
                        "imported": imported,
                        "duplicates": duplicates,
                        "errors": errors,
                        "elapsed_ms": round(elapsed * 1000),
                        "hands_per_sec": round(hps),
                    }) + "\n"

            db.execute("COMMIT")

            # Recreate indexes (bulk build is faster than incremental)
            t0_idx = time.perf_counter()
            _create_indexes(db)
            t_idx = time.perf_counter() - t0_idx

            finalize_import(db, workspace_id=workspace_id)

        elapsed = time.perf_counter() - t_start
        hps = imported / elapsed if elapsed > 0 else 0
        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details[:20],
            "elapsed_ms": round(elapsed * 1000),
            "hands_per_sec": round(hps),
            "parse_ms": round(t_parse * 1000),
            "stats_ms": round(t_stats * 1000),
            "equity_ms": round(t_equity * 1000),
            "db_ms": round(t_db * 1000),
            "index_ms": round(t_idx * 1000),
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


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

    existing_ids: set[str] = set()
    valid_ids = [hid for hid in all_ids if hid is not None]
    if valid_ids:
        for j in range(0, len(valid_ids), 500):
            batch = valid_ids[j:j + 500]
            placeholders = ",".join(["?"] * len(batch))
            rows = db.execute(
                f"SELECT id FROM hands WHERE workspace_id = ? AND id IN ({placeholders})",
                [workspace_id] + batch,
            ).fetchall()
            existing_ids.update(r[0] for r in rows)

    # Drop indexes for fast bulk loading
    _drop_indexes(db)

    # Single transaction + suppress auto-checkpoint for bulk load
    db.execute("BEGIN TRANSACTION")
    db.execute("SET checkpoint_threshold = '10GB'")

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

    db.execute("COMMIT")
    _create_indexes(db)
    finalize_import(db, workspace_id=workspace_id)

    return ImportResult(
        imported=total_imported,
        duplicates=total_duplicates,
        errors=total_errors,
        error_details=error_details[:20],
    )


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
                logging.getLogger(__name__).info("User-triggered rebuild complete")
        except Exception:
            logging.getLogger(__name__).exception("Rebuild failed")
        finally:
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

    _drop_indexes(db)
    db.execute("DELETE FROM player_classifications")
    db.execute("DELETE FROM actions")
    db.execute("DELETE FROM board_cards")
    db.execute("DELETE FROM hand_players")
    # Keep players table intact — player_aliases has FK references, and
    # _batch_resolve_players will look up existing players from the DB.
    reset_import_cache()

    db.execute("BEGIN TRANSACTION")
    db.execute("SET checkpoint_threshold = '10GB'")

    imported = 0
    errors = 0
    processed = 0
    t_start = time.perf_counter()

    chunks = [all_rows[ci:ci + BATCH_SIZE] for ci in range(0, total, BATCH_SIZE)]

    for ci, chunk in enumerate(chunks):
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

    db.execute("COMMIT")
    _create_indexes(db)
    # Full rebuild: recompute classifications for all workspaces
    finalize_import(db, workspace_id=None)

    elapsed = time.perf_counter() - t_start
    hps = imported / elapsed if elapsed > 0 else 0
    logging.getLogger(__name__).info(
        "Auto-rebuild complete: %d hands in %.1fs (%.0f h/s, %d errors)",
        imported, elapsed, hps, errors,
    )


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
        db.execute("DELETE FROM player_classifications WHERE workspace_id = ?", [workspace_id])
        reset_import_cache()
    return {"status": "ok"}


@router.get("/import/export")
async def export_database():
    """Export the database as a downloadable .duckdb file."""
    with db_lock():
        db = get_db()
        db.execute("CHECKPOINT")
        # Copy to a temp file while we hold the lock
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".duckdb")
        tmp.close()
        shutil.copy2(str(DB_PATH), tmp.name)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"ohm-backup-{timestamp}.duckdb"

    def cleanup():
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    from starlette.background import BackgroundTask
    return FileResponse(
        tmp.name,
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
            get_db()
            reset_import_cache()

        return {"status": "ok", "hands": hand_count}
    except ValueError as e:
        raise e
    except Exception as e:
        raise RuntimeError(f"Database import failed: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


