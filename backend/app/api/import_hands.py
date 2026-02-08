from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from decimal import Decimal
from app.models import ImportResult
from app.db import get_db, db_lock
from app.parsers.ggpoker import parse_hand_history, ParsedHand
from app.stat_flags import compute_stat_flags
import duckdb
import traceback
import zipfile
import io
import json
import re
import time
import pyarrow as pa

try:
    from app.equity import calculate_headsup_equity as _calc_equity
except ImportError:
    _calc_equity = None

router = APIRouter()

# ── Pre-compiled regexes ──
RE_HAND_BOUNDARY = re.compile(r'\n(?=Poker Hand #)')
RE_HAND_ID = re.compile(r'Poker Hand #(\w+):')

# ── Import session caches (cleared between import runs) ──
_player_cache: dict[str, int] = {}  # username -> player_id
_next_player_id: int | None = None
_next_hp_id: int | None = None

BATCH_SIZE = 500

# ── Column keys for column-oriented PyArrow inserts ──
_HANDS_COLS = (
    "id", "site_id", "played_at", "game_type", "stakes",
    "sb_amount", "bb_amount", "table_name", "table_size", "button_seat", "raw_text",
)
_HP_BASE_COLS = (
    "id", "hand_id", "player_id", "seat", "position",
    "stack", "stack_bb", "card1", "card2",
    "won", "won_bb", "rake", "rake_bb", "jackpot", "jackpot_bb", "all_in_ev_bb",
)
_STAT_FLAG_KEYS = (
    "vpip", "pfr", "three_bet", "three_bet_opp", "four_bet", "four_bet_opp",
    "fold_to_3bet", "fold_to_4bet",
    "open_raise", "open_raise_opp", "call_open_raise", "limp", "squeeze", "five_bet",
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
)
_HP_ALL_COLS = _HP_BASE_COLS + _STAT_FLAG_KEYS
_BOARD_COLS = ("hand_id", "street", "card", "card_order")


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
    prepared: list[tuple[ParsedHand, dict]],
) -> None:
    """Resolve player IDs for all hands in a batch. Creates new players as needed."""
    global _next_player_id

    all_usernames = set()
    for parsed, _ in prepared:
        for s in parsed.seats:
            all_usernames.add(s["username"])

    uncached = [u for u in all_usernames if u not in _player_cache]
    if not uncached:
        return

    # Batch lookup existing players
    for i in range(0, len(uncached), 500):
        batch = uncached[i:i + 500]
        placeholders = ",".join(["?"] * len(batch))
        rows = db.execute(
            f"SELECT username, id FROM players WHERE site_id = 1 AND username IN ({placeholders})",
            batch,
        ).fetchall()
        for username, pid in rows:
            _player_cache[username] = pid

    # Create missing players in bulk
    new_ids = []
    new_site_ids = []
    new_usernames = []
    for u in uncached:
        if u not in _player_cache:
            pid = _next_player_id
            _next_player_id += 1
            _player_cache[u] = pid
            new_ids.append(pid)
            new_site_ids.append(1)
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
    """Compute per-player investment and all-in EV for a parsed hand.

    Returns (player_invested, all_in_ev_bb_map).
    """
    player_invested = {s["username"]: Decimal("0") for s in parsed.seats}

    for street in ("preflop", "flop", "turn", "river"):
        street_put_in: dict[str, Decimal] = {}
        for a in parsed.actions_by_street[street]:
            uname = a["username"]
            action = a["action"]
            amt = a["amount"]

            if action in ("sb", "bb", "ante", "straddle", "call", "bet"):
                street_put_in[uname] = street_put_in.get(uname, Decimal("0")) + amt
                player_invested[uname] += amt
            elif action == "raise":
                already_in = street_put_in.get(uname, Decimal("0"))
                increment = amt - already_in
                if increment > 0:
                    player_invested[uname] += increment
                street_put_in[uname] = amt

    # All-in EV calculation
    all_in_ev_bb_map: dict[str, float] = {}

    all_in_street = None
    street_order = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
    for street in ("preflop", "flop", "turn", "river"):
        for a in parsed.actions_by_street[street]:
            if a["is_all_in"]:
                all_in_street = street
                break
        if all_in_street is not None:
            break

    if all_in_street is not None and _calc_equity:
        players_in = set(s["username"] for s in parsed.seats)
        folded = set()
        for st in ("preflop", "flop", "turn", "river"):
            for a in parsed.actions_by_street[st]:
                if a["action"] == "fold":
                    folded.add(a["username"])
        remaining = players_in - folded
        real_showdown = len(remaining) >= 2 and (
            parsed.in_showdown or parsed.went_to_showdown_players
        )

        if real_showdown and len(remaining) == 2:
            board_at = []
            if street_order[all_in_street] >= 1:
                board_at.extend(parsed.board_cards["flop"])
            if street_order[all_in_street] >= 2:
                board_at.extend(parsed.board_cards["turn"])
            if street_order[all_in_street] >= 3:
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
                            parsed.uncalled_returns.get(p1, Decimal("0"))
                        )
                        p2_net = float(player_invested[p2]) - float(
                            parsed.uncalled_returns.get(p2, Decimal("0"))
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


def _flush_batch(
    db: duckdb.DuckDBPyConnection,
    prepared: list[tuple[ParsedHand, dict]],
) -> tuple[int, int, list[str]]:
    """Bulk-insert a batch of (parsed, player_stats) tuples using PyArrow column-oriented inserts.

    Returns (imported_count, error_count, error_details).
    """
    global _next_hp_id

    if not prepared:
        return 0, 0, []

    _init_counters(db)
    _batch_resolve_players(db, prepared)

    # Column-oriented building: one list per column
    hands_cols: dict[str, list] = {k: [] for k in _HANDS_COLS}
    hp_cols: dict[str, list] = {k: [] for k in _HP_ALL_COLS}
    board_cols: dict[str, list] = {k: [] for k in _BOARD_COLS}

    for parsed, player_stats in prepared:
        bb_amount = parsed.bb_amount
        bb_f = float(bb_amount) if bb_amount else 0.0
        num_winners = len(parsed.collected)
        per_player_rake = (
            parsed.total_rake / max(num_winners, 1)
            if parsed.total_rake else Decimal("0")
        )
        per_player_jackpot = (
            parsed.total_jackpot / max(num_winners, 1)
            if parsed.total_jackpot else Decimal("0")
        )
        player_invested, all_in_ev_bb_map = _compute_financials(parsed)

        # Append to hands columns
        hands_cols["id"].append(parsed.hand_id)
        hands_cols["site_id"].append(parsed.site_id)
        hands_cols["played_at"].append(parsed.played_at)
        hands_cols["game_type"].append(parsed.game_type)
        hands_cols["stakes"].append(parsed.stakes)
        hands_cols["sb_amount"].append(float(parsed.sb_amount))
        hands_cols["bb_amount"].append(bb_f)
        hands_cols["table_name"].append(parsed.table_name)
        hands_cols["table_size"].append(parsed.table_size)
        hands_cols["button_seat"].append(parsed.button_seat)
        hands_cols["raw_text"].append(parsed.raw_text)

        for s in parsed.seats:
            uname = s["username"]
            pid = _player_cache[uname]
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

            # Append stat flags
            for k in _STAT_FLAG_KEYS:
                hp_cols[k].append(ps[k])

        for street, cards in parsed.board_cards.items():
            for i, card in enumerate(cards):
                board_cols["hand_id"].append(parsed.hand_id)
                board_cols["street"].append(street)
                board_cols["card"].append(card)
                board_cols["card_order"].append(i + 1)

    # Bulk insert using PyArrow tables
    db.execute("BEGIN TRANSACTION")
    try:
        if hands_cols["id"]:
            pa_hands = pa.table(hands_cols)
            db.execute("INSERT INTO hands BY NAME SELECT * FROM pa_hands")
        if hp_cols["id"]:
            pa_hp = pa.table(hp_cols)
            db.execute("INSERT INTO hand_players BY NAME SELECT * FROM pa_hp")
        if board_cols["hand_id"]:
            pa_board = pa.table(board_cols)
            db.execute("INSERT INTO board_cards BY NAME SELECT * FROM pa_board")
        db.execute("COMMIT")
        return len(prepared), 0, []
    except Exception as e:
        db.execute("ROLLBACK")
        traceback.print_exc()
        return 0, len(prepared), [f"Batch insert failed: {e}"]


def finalize_import(db: duckdb.DuckDBPyConnection) -> None:
    """Batch-update player first_seen/last_seen. Call once after import."""
    db.execute("""
        UPDATE players SET
            first_seen = sub.min_t,
            last_seen = sub.max_t
        FROM (
            SELECT hp.player_id, MIN(h.played_at) AS min_t, MAX(h.played_at) AS max_t
            FROM hand_players hp JOIN hands h ON hp.hand_id = h.id
            GROUP BY hp.player_id
        ) sub
        WHERE players.id = sub.player_id
    """)


def insert_parsed_hand(db: duckdb.DuckDBPyConnection, parsed: ParsedHand) -> str:
    """Insert a single parsed hand. Computes stats internally.

    Kept for backward compatibility (used by tests).
    """
    player_stats = compute_stat_flags(parsed)
    imported, errors, details = _flush_batch(db, [(parsed, player_stats)])
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


@router.post("/import/files", response_model=ImportResult)
async def import_files(files: list[UploadFile] = File(...)):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    db = get_db()
    result = _process_hands(db, text_contents)
    return result


@router.post("/import/files/stream")
async def import_files_stream(files: list[UploadFile] = File(...)):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    # Pre-split all hands for total count
    all_hands: list[str] = []
    for content in text_contents:
        for h in split_hands(content):
            h = h.strip()
            if h:
                all_hands.append(h)

    total = len(all_hands)
    file_count = len(text_contents)

    def generate():
        yield json.dumps({
            "type": "start",
            "total_hands": total,
            "files": file_count,
        }) + "\n"

        db = get_db()
        imported = 0
        duplicates = 0
        errors = 0
        error_details: list[str] = []

        t_start = time.perf_counter()
        t_parse = 0.0
        t_stats = 0.0
        t_db = 0.0

        # Bulk duplicate check
        all_ids = [extract_hand_id(h) for h in all_hands]
        existing_ids: set[str] = set()
        valid_ids = [hid for hid in all_ids if hid is not None]
        if valid_ids:
            for j in range(0, len(valid_ids), 500):
                batch = valid_ids[j:j + 500]
                placeholders = ",".join(["?"] * len(batch))
                rows = db.execute(
                    f"SELECT id FROM hands WHERE id IN ({placeholders})", batch
                ).fetchall()
                existing_ids.update(r[0] for r in rows)

        pending: list[tuple[ParsedHand, dict]] = []

        for i, hand_text in enumerate(all_hands):
            hid = all_ids[i]
            if hid is None:
                errors += 1
                error_details.append("Could not extract hand ID")
            elif hid in existing_ids:
                duplicates += 1
            else:
                existing_ids.add(hid)
                try:
                    t0 = time.perf_counter()
                    parsed = parse_hand_history(hand_text)
                    t1 = time.perf_counter()
                    stats = compute_stat_flags(parsed)
                    t2 = time.perf_counter()
                    t_parse += t1 - t0
                    t_stats += t2 - t1
                    pending.append((parsed, stats))
                except Exception as e:
                    errors += 1
                    error_details.append(f"Hand parse error: {str(e)}")

            # Flush batch to DB
            if len(pending) >= BATCH_SIZE:
                t0 = time.perf_counter()
                imp, errs, details = _flush_batch(db, pending)
                t_db += time.perf_counter() - t0
                imported += imp
                errors += errs
                error_details.extend(details)
                pending = []

            # Progress update
            if (i + 1) % 200 == 0 or i == total - 1:
                elapsed = time.perf_counter() - t_start
                hps = imported / elapsed if elapsed > 0 else 0
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": duplicates,
                    "errors": errors,
                    "elapsed_ms": round(elapsed * 1000),
                    "hands_per_sec": round(hps),
                }) + "\n"

        # Flush remaining
        if pending:
            t0 = time.perf_counter()
            imp, errs, details = _flush_batch(db, pending)
            t_db += time.perf_counter() - t0
            imported += imp
            errors += errs
            error_details.extend(details)

        finalize_import(db)

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
            "db_ms": round(t_db * 1000),
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _process_hands(db, text_contents: list[str]) -> ImportResult:
    """Process hands from text contents (non-streaming)."""
    total_imported = 0
    total_duplicates = 0
    total_errors = 0
    error_details: list[str] = []

    # Split all hands and check duplicates in bulk
    all_hands: list[str] = []
    all_ids: list[str | None] = []
    for content in text_contents:
        for hand_text in split_hands(content):
            hand_text = hand_text.strip()
            if hand_text:
                all_hands.append(hand_text)
                all_ids.append(extract_hand_id(hand_text))

    existing_ids: set[str] = set()
    valid_ids = [hid for hid in all_ids if hid is not None]
    if valid_ids:
        for j in range(0, len(valid_ids), 500):
            batch = valid_ids[j:j + 500]
            placeholders = ",".join(["?"] * len(batch))
            rows = db.execute(
                f"SELECT id FROM hands WHERE id IN ({placeholders})", batch
            ).fetchall()
            existing_ids.update(r[0] for r in rows)

    pending: list[tuple[ParsedHand, dict]] = []

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
            parsed = parse_hand_history(hand_text)
            stats = compute_stat_flags(parsed)
            pending.append((parsed, stats))
        except Exception as e:
            total_errors += 1
            error_details.append(f"Hand parse error: {str(e)}")

        if len(pending) >= BATCH_SIZE:
            imp, errs, details = _flush_batch(db, pending)
            total_imported += imp
            total_errors += errs
            error_details.extend(details)
            pending = []

    if pending:
        imp, errs, details = _flush_batch(db, pending)
        total_imported += imp
        total_errors += errs
        error_details.extend(details)

    finalize_import(db)

    return ImportResult(
        imported=total_imported,
        duplicates=total_duplicates,
        errors=total_errors,
        error_details=error_details[:20],
    )


@router.post("/import/rebuild")
async def rebuild_hands():
    """Re-parse all hands from stored raw_text. Useful after parser/schema changes."""

    def generate():
        db = get_db()

        rows = db.execute(
            "SELECT id, raw_text FROM hands ORDER BY played_at ASC, id ASC"
        ).fetchall()
        total = len(rows)

        if total == 0:
            yield json.dumps({
                "type": "done", "imported": 0, "duplicates": 0,
                "errors": 0, "error_details": [],
            }) + "\n"
            return

        yield json.dumps({"type": "start", "total_hands": total, "files": 0}) + "\n"

        hand_texts = [(hid, raw) for hid, raw in rows]

        # Wipe everything and reset caches
        db.execute("DELETE FROM actions")
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        db.execute("DELETE FROM hands")
        db.execute("DELETE FROM players")
        reset_import_cache()

        imported = 0
        errors = 0
        error_details: list[str] = []
        pending: list[tuple[ParsedHand, dict]] = []

        t_start = time.perf_counter()
        t_parse = 0.0
        t_stats = 0.0
        t_db = 0.0

        for i, (hand_id, raw_text) in enumerate(hand_texts):
            try:
                t0 = time.perf_counter()
                parsed = parse_hand_history(raw_text)
                t1 = time.perf_counter()
                stats = compute_stat_flags(parsed)
                t2 = time.perf_counter()
                t_parse += t1 - t0
                t_stats += t2 - t1
                pending.append((parsed, stats))
            except Exception as e:
                errors += 1
                error_details.append(f"{hand_id}: {str(e)}")
                traceback.print_exc()

            if len(pending) >= BATCH_SIZE:
                t0 = time.perf_counter()
                imp, errs, details = _flush_batch(db, pending)
                t_db += time.perf_counter() - t0
                imported += imp
                errors += errs
                error_details.extend(details)
                pending = []

            if (i + 1) % 200 == 0 or i == total - 1:
                elapsed = time.perf_counter() - t_start
                hps = imported / elapsed if elapsed > 0 else 0
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": 0,
                    "errors": errors,
                    "elapsed_ms": round(elapsed * 1000),
                    "hands_per_sec": round(hps),
                }) + "\n"

        if pending:
            t0 = time.perf_counter()
            imp, errs, details = _flush_batch(db, pending)
            t_db += time.perf_counter() - t0
            imported += imp
            errors += errs
            error_details.extend(details)

        finalize_import(db)

        elapsed = time.perf_counter() - t_start
        hps = imported / elapsed if elapsed > 0 else 0
        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": 0,
            "errors": errors,
            "error_details": error_details[:20],
            "elapsed_ms": round(elapsed * 1000),
            "hands_per_sec": round(hps),
            "parse_ms": round(t_parse * 1000),
            "stats_ms": round(t_stats * 1000),
            "db_ms": round(t_db * 1000),
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/import/clear")
async def clear_hands():
    with db_lock():
        db = get_db()
        db.execute("DELETE FROM actions")
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        db.execute("DELETE FROM hands")
        db.execute("DELETE FROM players")
        reset_import_cache()
    return {"status": "ok"}


def split_hands(content: str) -> list[str]:
    """Split a file with multiple hand histories into individual hands."""
    return RE_HAND_BOUNDARY.split(content)


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the first line."""
    m = RE_HAND_ID.search(hand_text)
    return m.group(1) if m else None
