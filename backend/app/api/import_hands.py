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

try:
    from app.equity import calculate_headsup_equity as _calc_equity
except ImportError:
    _calc_equity = None

router = APIRouter()

# ── Import session caches (cleared between import runs) ──
_player_cache: dict[str, int] = {}  # username -> player_id
_next_player_id: int | None = None
_next_hp_id: int | None = None
_next_action_id: int | None = None


def reset_import_cache() -> None:
    """Reset caches. Call before rebuild or when tables are wiped."""
    global _player_cache, _next_player_id, _next_hp_id, _next_action_id
    _player_cache.clear()
    _next_player_id = None
    _next_hp_id = None
    _next_action_id = None


def _init_counters(db: duckdb.DuckDBPyConnection) -> None:
    """Initialize ID counters from current DB max values (once per session)."""
    global _next_player_id, _next_hp_id, _next_action_id
    if _next_player_id is None:
        _next_player_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM players").fetchone()[0]
    if _next_hp_id is None:
        _next_hp_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM hand_players").fetchone()[0]
    if _next_action_id is None:
        _next_action_id = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM actions").fetchone()[0]


def _get_or_create_player(
    db: duckdb.DuckDBPyConnection, username: str, site_id: int
) -> int:
    """Get existing player or create new one. Returns player_id.
    Uses in-memory cache. first_seen/last_seen updated via finalize_import().
    """
    global _next_player_id
    if username in _player_cache:
        return _player_cache[username]

    row = db.execute(
        "SELECT id FROM players WHERE site_id = ? AND username = ?",
        [site_id, username],
    ).fetchone()
    if row:
        _player_cache[username] = row[0]
        return row[0]

    player_id = _next_player_id
    _next_player_id += 1
    db.execute(
        "INSERT INTO players (id, site_id, username) VALUES (?, ?, ?)",
        [player_id, site_id, username],
    )
    _player_cache[username] = player_id
    return player_id


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
    """Compute stats, financials, and insert a parsed hand into DuckDB. Returns hand_id."""
    global _next_hp_id, _next_action_id

    _init_counters(db)

    # Get or create players
    player_ids = {}  # username -> player_id
    for s in parsed.seats:
        player_ids[s["username"]] = _get_or_create_player(db, s["username"], parsed.site_id)

    # Compute stat flags
    player_stats = compute_stat_flags(parsed)

    # ── Calculate per-player investment ──
    player_invested = {s["username"]: Decimal("0") for s in parsed.seats}

    for street in ["preflop", "flop", "turn", "river"]:
        street_put_in: dict[str, Decimal] = {}

        for a in parsed.actions_by_street[street]:
            uname = a["username"]
            action = a["action"]
            amt = a["amount"]

            if action in ("sb", "bb", "ante", "straddle"):
                street_put_in[uname] = street_put_in.get(uname, Decimal("0")) + amt
                player_invested[uname] += amt
            elif action in ("call", "bet"):
                street_put_in[uname] = street_put_in.get(uname, Decimal("0")) + amt
                player_invested[uname] += amt
            elif action == "raise":
                # amt is the "to" amount for this street
                already_in = street_put_in.get(uname, Decimal("0"))
                increment = amt - already_in
                if increment > 0:
                    player_invested[uname] += increment
                street_put_in[uname] = amt

    # ── Detect all-in for EV calculation ──
    all_in_street = None
    street_order_map = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
    for street in ["preflop", "flop", "turn", "river"]:
        for a in parsed.actions_by_street[street]:
            if a["is_all_in"]:
                if all_in_street is None:
                    all_in_street = street
                break
        if all_in_street is not None:
            break

    # ── Determine remaining players for EV ──
    players_in_hand = set(s["username"] for s in parsed.seats)
    players_folded = set()
    for street in ["preflop", "flop", "turn", "river"]:
        for a in parsed.actions_by_street[street]:
            if a["action"] == "fold":
                players_folded.add(a["username"])
    remaining_players = players_in_hand - players_folded
    real_showdown = len(remaining_players) >= 2 and (
        parsed.in_showdown or parsed.went_to_showdown_players
    )

    # ── Calculate won/rake amounts ──
    num_winners = len(parsed.collected)
    per_player_rake = parsed.total_rake / max(num_winners, 1) if parsed.total_rake else Decimal("0")

    bb_amount = parsed.bb_amount

    # ── Compute all-in EV ──
    all_in_ev_bb_map = {}  # username -> ev_bb

    if all_in_street is not None and real_showdown and len(remaining_players) == 2:
        # Board at the all-in point
        board_at_all_in = []
        if street_order_map[all_in_street] >= 1:
            board_at_all_in.extend(parsed.board_cards["flop"])
        if street_order_map[all_in_street] >= 2:
            board_at_all_in.extend(parsed.board_cards["turn"])
        if street_order_map[all_in_street] >= 3:
            board_at_all_in.extend(parsed.board_cards["river"])

        cards_to_come = 5 - len(board_at_all_in)

        if cards_to_come > 0:
            # Check we know both players' cards
            players_list = list(remaining_players)
            if players_list[0] in parsed.hero_cards and players_list[1] in parsed.hero_cards and _calc_equity:
                try:
                    p1, p2 = players_list
                    p1_eq = _calc_equity(
                        parsed.hero_cards[p1], parsed.hero_cards[p2], board_at_all_in
                    )
                    p2_eq = 1.0 - p1_eq

                    # Subtract uncalled bets — money returned was never at risk
                    p1_net = float(player_invested[p1]) - float(parsed.uncalled_returns.get(p1, Decimal("0")))
                    p2_net = float(player_invested[p2]) - float(parsed.uncalled_returns.get(p2, Decimal("0")))
                    total_at_risk = sum(float(v) for v in player_invested.values()) \
                                  - sum(float(v) for v in parsed.uncalled_returns.values())
                    distributable = total_at_risk - float(parsed.total_rake)

                    all_in_ev_bb_map[p1] = (
                        p1_eq * distributable - p1_net
                    ) / float(bb_amount)
                    all_in_ev_bb_map[p2] = (
                        p2_eq * distributable - p2_net
                    ) / float(bb_amount)
                except Exception:
                    pass  # Fall back to won_bb

    # ── Insert into database ──
    # 1. Insert hand
    db.execute(
        """INSERT INTO hands (id, site_id, played_at, game_type, stakes,
           sb_amount, bb_amount, table_name, table_size, button_seat, raw_text)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            parsed.hand_id, parsed.site_id, parsed.played_at, parsed.game_type,
            parsed.stakes, float(parsed.sb_amount), float(bb_amount),
            parsed.table_name, parsed.table_size, parsed.button_seat, parsed.raw_text,
        ],
    )

    # 2. Insert board cards (batched)
    board_rows = []
    for street, cards in parsed.board_cards.items():
        for i, card in enumerate(cards):
            board_rows.append([parsed.hand_id, street, card, i + 1])
    if board_rows:
        db.executemany(
            "INSERT INTO board_cards (hand_id, street, card, card_order) VALUES (?, ?, ?, ?)",
            board_rows,
        )

    # 3. Insert hand_players
    for s in parsed.seats:
        uname = s["username"]
        pid = player_ids[uname]
        cards = parsed.hero_cards.get(uname)
        card1 = cards[0] if cards else None
        card2 = cards[1] if cards else None
        gross_collected = parsed.collected.get(uname, Decimal("0"))
        uncalled = parsed.uncalled_returns.get(uname, Decimal("0"))
        invested = player_invested.get(uname, Decimal("0"))
        net_won = float(gross_collected + uncalled - invested)
        rake = float(per_player_rake) if uname in parsed.collected else 0.0
        won = net_won
        won_bb = won / float(bb_amount) if bb_amount else 0.0
        rake_bb = rake / float(bb_amount) if bb_amount else 0.0
        stack_bb = float(s["stack"]) / float(bb_amount) if bb_amount else 0.0
        ps = player_stats[uname]
        ev_bb = all_in_ev_bb_map.get(uname, won_bb)

        hp_id = _next_hp_id
        _next_hp_id += 1
        db.execute(
            """INSERT INTO hand_players (
                id, hand_id, player_id, seat, position, stack, stack_bb,
                card1, card2, won, won_bb, rake, rake_bb, all_in_ev_bb,
                vpip, pfr, three_bet, three_bet_opp, four_bet, four_bet_opp,
                fold_to_3bet, fold_to_4bet,
                open_raise, open_raise_opp, call_open_raise, limp, squeeze, five_bet,
                steal_attempted, faced_steal, fold_to_steal, call_steal, three_bet_vs_steal,
                saw_flop, saw_turn, saw_river, went_to_showdown, won_at_showdown,
                cbet_flop, cbet_flop_opp, cbet_turn, cbet_turn_opp,
                cbet_river, cbet_river_opp,
                fold_to_cbet_flop, fold_to_cbet_turn, fold_to_cbet_river,
                missed_cbet_flop, missed_cbet_turn,
                donk_bet_flop, donk_bet_turn, donk_bet_river,
                flop_bets, flop_raises, flop_calls,
                turn_bets, turn_raises, turn_calls,
                river_bets, river_raises, river_calls
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?
            )""",
            [
                hp_id, parsed.hand_id, pid, s["seat"], s["position"],
                float(s["stack"]), stack_bb,
                card1, card2, won, won_bb, rake, rake_bb, ev_bb,
                ps["vpip"], ps["pfr"], ps["three_bet"], ps["three_bet_opp"],
                ps["four_bet"], ps["four_bet_opp"],
                ps["fold_to_3bet"], ps["fold_to_4bet"],
                ps["open_raise"], ps["open_raise_opp"], ps["call_open_raise"], ps["limp"],
                ps["squeeze"], ps["five_bet"],
                ps["steal_attempted"], ps["faced_steal"],
                ps["fold_to_steal"], ps["call_steal"], ps["three_bet_vs_steal"],
                ps["saw_flop"], ps["saw_turn"], ps["saw_river"],
                ps["went_to_showdown"], ps["won_at_showdown"],
                ps["cbet_flop"], ps["cbet_flop_opp"],
                ps["cbet_turn"], ps["cbet_turn_opp"],
                ps["cbet_river"], ps["cbet_river_opp"],
                ps["fold_to_cbet_flop"], ps["fold_to_cbet_turn"],
                ps["fold_to_cbet_river"],
                ps["missed_cbet_flop"], ps["missed_cbet_turn"],
                ps["donk_bet_flop"], ps["donk_bet_turn"], ps["donk_bet_river"],
                ps["flop_bets"], ps["flop_raises"], ps["flop_calls"],
                ps["turn_bets"], ps["turn_raises"], ps["turn_calls"],
                ps["river_bets"], ps["river_raises"], ps["river_calls"],
            ],
        )

    # 4. Insert actions (batched)
    action_rows = []
    for street, street_actions in parsed.actions_by_street.items():
        for a in street_actions:
            uname = a["username"]
            if uname not in player_ids:
                continue
            pid = player_ids[uname]
            amt = float(a["amount"])
            amt_bb = amt / float(bb_amount) if bb_amount else 0.0
            act_id = _next_action_id
            _next_action_id += 1
            action_rows.append([
                act_id, parsed.hand_id, pid, street,
                a["order"], a["action"], amt, amt_bb, a["is_all_in"],
            ])
    if action_rows:
        db.executemany(
            """INSERT INTO actions (id, hand_id, player_id, street,
               action_order, action_type, amount, amount_bb, is_all_in)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            action_rows,
        )

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

        # Pre-check duplicates in bulk
        all_ids = []
        for h in all_hands:
            hid = extract_hand_id(h)
            all_ids.append(hid)

        existing_ids: set[str] = set()
        valid_ids = [hid for hid in all_ids if hid is not None]
        if valid_ids:
            batch_size = 500
            for j in range(0, len(valid_ids), batch_size):
                batch = valid_ids[j:j + batch_size]
                placeholders = ",".join(["?"] * len(batch))
                rows = db.execute(
                    f"SELECT id FROM hands WHERE id IN ({placeholders})", batch
                ).fetchall()
                existing_ids.update(r[0] for r in rows)

        # Batch transactions
        BATCH_SIZE = 200
        db.execute("BEGIN TRANSACTION")
        batch_count = 0

        for i, hand_text in enumerate(all_hands):
            hid = all_ids[i]
            if hid is None:
                errors += 1
                error_details.append("Could not extract hand ID")
            elif hid in existing_ids:
                duplicates += 1
            else:
                try:
                    parsed = parse_hand_history(hand_text)
                    insert_parsed_hand(db, parsed)
                    imported += 1
                    batch_count += 1
                    if batch_count >= BATCH_SIZE:
                        db.execute("COMMIT")
                        db.execute("BEGIN TRANSACTION")
                        batch_count = 0
                except Exception as e:
                    # Rollback failed batch, retry remaining individually
                    db.execute("ROLLBACK")
                    db.execute("BEGIN TRANSACTION")
                    batch_count = 0
                    errors += 1
                    error_details.append(f"Hand parse error: {str(e)}")

            if (i + 1) % 200 == 0 or i == total - 1:
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": duplicates,
                    "errors": errors,
                }) + "\n"

        db.execute("COMMIT")
        finalize_import(db)

        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details[:20],
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _process_hands(db, text_contents: list[str]) -> ImportResult:
    """Process hands from text contents (non-streaming)."""
    total_imported = 0
    total_duplicates = 0
    total_errors = 0
    error_details: list[str] = []

    db.execute("BEGIN TRANSACTION")
    for content in text_contents:
        for hand_text in split_hands(content):
            hand_text = hand_text.strip()
            if not hand_text:
                continue
            try:
                hand_id = extract_hand_id(hand_text)
                if hand_id is None:
                    total_errors += 1
                    error_details.append("Could not extract hand ID from hand")
                    continue

                existing = db.execute(
                    "SELECT 1 FROM hands WHERE id = ?", [hand_id]
                ).fetchone()
                if existing:
                    total_duplicates += 1
                    continue

                parsed = parse_hand_history(hand_text)
                insert_parsed_hand(db, parsed)
                total_imported += 1
            except Exception as e:
                total_errors += 1
                error_details.append(f"Hand parse error: {str(e)}")
                traceback.print_exc()
    db.execute("COMMIT")
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
            yield json.dumps({"type": "done", "imported": 0, "duplicates": 0, "errors": 0, "error_details": []}) + "\n"
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
        BATCH_SIZE = 200

        db.execute("BEGIN TRANSACTION")
        batch_count = 0

        for i, (hand_id, raw_text) in enumerate(hand_texts):
            try:
                parsed = parse_hand_history(raw_text)
                insert_parsed_hand(db, parsed)
                imported += 1
                batch_count += 1
                if batch_count >= BATCH_SIZE:
                    db.execute("COMMIT")
                    db.execute("BEGIN TRANSACTION")
                    batch_count = 0
            except Exception as e:
                db.execute("ROLLBACK")
                db.execute("BEGIN TRANSACTION")
                batch_count = 0
                errors += 1
                error_details.append(f"{hand_id}: {str(e)}")
                traceback.print_exc()

            if (i + 1) % 200 == 0 or i == total - 1:
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": 0,
                    "errors": errors,
                }) + "\n"

        db.execute("COMMIT")
        finalize_import(db)

        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": 0,
            "errors": errors,
            "error_details": error_details[:20],
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
    hands = []
    current: list[str] = []

    for line in content.split("\n"):
        if line.startswith("Poker Hand #") and current:
            hands.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        hands.append("\n".join(current))

    return hands


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the first line."""
    import re
    m = re.search(r"Poker Hand #(\w+):", hand_text)
    return m.group(1) if m else None
