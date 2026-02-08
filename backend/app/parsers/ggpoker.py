"""
GGPoker hand history parser.

Parses a single hand history text block into structured data and stores it in DuckDB.
Handles cash game formats with HD/RC/TM prefixes.
"""

import re
from decimal import Decimal
from datetime import datetime
import duckdb

try:
    from app.equity import calculate_headsup_equity as _calc_equity
except ImportError:
    _calc_equity = None

SITE_ID = 1  # GGPoker

# ── Import session caches (cleared between import runs) ──
_player_cache: dict[str, int] = {}  # username -> player_id
_next_player_id: int | None = None
_next_hp_id: int | None = None
_next_action_id: int | None = None


def reset_parser_cache() -> None:
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

# Position labels for 6-max (clockwise from BTN)
POSITIONS_6MAX = ["BTN", "SB", "BB", "EP", "MP", "CO"]
# For fewer players, trim from the middle positions
POSITIONS_BY_COUNT = {
    2: ["BTN", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "MP", "CO"],
    6: ["BTN", "SB", "BB", "EP", "MP", "CO"],
    7: ["BTN", "SB", "BB", "EP", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "EP", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG1", "EP", "MP", "HJ", "CO"],
}

# Lines to skip entirely
SKIP_PATTERNS = [
    re.compile(r"is disconnected"),
    re.compile(r"has timed out"),
    re.compile(r"is sitting out"),
    re.compile(r"is connected"),
    re.compile(r"has returned"),
    re.compile(r"Cashout:"),
    re.compile(r"was removed from the table"),
    re.compile(r"said,"),
    re.compile(r"leaves the table"),
    re.compile(r"joins the table"),
    re.compile(r"\*\*\* FIRST BOARD \*\*\*"),
    re.compile(r"\*\*\* SECOND BOARD \*\*\*"),
    # Run It Twice: skip SECOND/THIRD board variants (we use FIRST as canonical)
    re.compile(r"\*\*\* (?:SECOND|THIRD) (?:FLOP|TURN|RIVER) \*\*\*"),
    re.compile(r"\*\*\* (?:SECOND|THIRD) SHOWDOWN \*\*\*"),
    re.compile(r"^Hand was run"),
]

# Regex patterns for parsing
RE_HEADER = re.compile(
    r"Poker Hand #(\w+): (?:Tournament #\S+, )?"
    r"Hold'em No Limit \(\$([0-9.]+)/\$([0-9.]+)\)"
    r" - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
)
RE_TABLE = re.compile(
    r"Table '([^']+)' (\d+)-max Seat #(\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \(\$([0-9.]+) in chips\)"
)
RE_ANTE = re.compile(
    r"^(.+?): posts ante \$([0-9.]+)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?): posts small blind \$([0-9.]+)"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?): posts big blind \$([0-9.]+)"
)
RE_STRADDLE = re.compile(
    r"^(.+?): posts straddle \$([0-9.]+)"
)
RE_DEALT = re.compile(
    r"Dealt to (.+?) \[(\w{2}) (\w{2})\]"
)
RE_FOLD = re.compile(r"^(.+?): folds")
RE_CHECK = re.compile(r"^(.+?): checks")
RE_CALL = re.compile(
    r"^(.+?): calls \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_BET = re.compile(
    r"^(.+?): bets \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_RAISE = re.compile(
    r"^(.+?): raises \$([0-9.]+) to \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_ALLIN_MARKER = re.compile(r"and is all-in")
RE_UNCALLED = re.compile(
    r"Uncalled bet \(\$([0-9.]+)\) returned to (.+)"
)
RE_COLLECTED = re.compile(
    r"(.+?) collected \(\$([0-9.]+)\)"
)
RE_COLLECTED_FROM_POT = re.compile(
    r"^(.+?) collected \$([0-9.]+) from (?:main |side )?pot"
)
RE_WON = re.compile(
    r"(.+?) won \(\$([0-9.]+)\)"
)
RE_BOARD = re.compile(r"Board \[(.+?)\]")
RE_SUMMARY_POT = re.compile(
    r"Total pot \$([0-9.]+)"
)
RE_SUMMARY_FEE = re.compile(
    r"(?:Rake|Jackpot|Bingo|Fortune|Tax) \$([0-9.]+)"
)
RE_SUMMARY_SEAT = re.compile(
    r"Seat (\d+): (.+?)(?:\s+\(.*?\))* (?:collected|folded|showed|mucked|lost|won)"
)
# Extract username from summary seat lines — stops before position labels and action words
RE_SEAT_USERNAME = re.compile(
    r"Seat \d+: (.+?)(?:\s+\((?:button|small blind|big blind)\))?\s+(?:showed|mucked|folded|collected|won|received|bought)"
)
RE_SHOWED = re.compile(
    r"Seat (\d+): (.+?) (?:.*?)(?:showed|mucked) \[(\w{2}) (\w{2})\]"
)
RE_FLOP = re.compile(r"\*\*\* (?:FIRST )?FLOP \*\*\* \[(.+?)\]")
RE_TURN = re.compile(r"\*\*\* (?:FIRST )?TURN \*\*\* \[.+?\] \[(\w{2})\]")
RE_RIVER = re.compile(r"\*\*\* (?:FIRST )?RIVER \*\*\* \[.+?\] \[(\w{2})\]")
RE_SHOWDOWN = re.compile(r"\*\*\* (?:FIRST )?SHOW\s?DOWN \*\*\*")
RE_SUMMARY = re.compile(r"\*\*\* SUMMARY \*\*\*")
RE_DOES_NOT_SHOW = re.compile(r"^(.+?): does not show hand")
RE_SHOWS = re.compile(r"^(.+?): shows \[(\w{2}) (\w{2})\]")


def _should_skip(line: str) -> bool:
    for pat in SKIP_PATTERNS:
        if pat.search(line):
            return True
    return False


def _get_or_create_player(
    db: duckdb.DuckDBPyConnection, username: str
) -> int:
    """Get existing player or create new one. Returns player_id.
    Uses in-memory cache. first_seen/last_seen updated via finalize_import().
    """
    global _next_player_id
    if username in _player_cache:
        return _player_cache[username]

    row = db.execute(
        "SELECT id FROM players WHERE site_id = ? AND username = ?",
        [SITE_ID, username],
    ).fetchone()
    if row:
        _player_cache[username] = row[0]
        return row[0]

    player_id = _next_player_id
    _next_player_id += 1
    db.execute(
        "INSERT INTO players (id, site_id, username) VALUES (?, ?, ?)",
        [player_id, SITE_ID, username],
    )
    _player_cache[username] = player_id
    return player_id


def _assign_positions(seats: list[dict], button_seat: int, table_size: int) -> None:
    """Assign position labels to seated players based on button seat.

    Sorts players clockwise from button and assigns positions.
    seats is a list of dicts with 'seat' key, mutated to add 'position'.
    """
    if not seats:
        return

    num_players = len(seats)
    pos_labels = POSITIONS_BY_COUNT.get(num_players)
    if pos_labels is None:
        # Fallback for unusual counts
        pos_labels = POSITIONS_BY_COUNT.get(min(num_players, 9), POSITIONS_6MAX)

    # Sort seats clockwise starting from button
    seat_numbers = sorted(s["seat"] for s in seats)
    # Find button index
    btn_idx = None
    for i, sn in enumerate(seat_numbers):
        if sn == button_seat:
            btn_idx = i
            break
    if btn_idx is None:
        # Button seat not occupied — find the closest seat before button going backwards
        # (the seat that would act as button)
        for i in range(len(seat_numbers) - 1, -1, -1):
            if seat_numbers[i] < button_seat:
                btn_idx = i
                break
        if btn_idx is None:
            btn_idx = len(seat_numbers) - 1

    # Reorder clockwise from button
    ordered = seat_numbers[btn_idx:] + seat_numbers[:btn_idx]

    seat_to_pos = {}
    for i, sn in enumerate(ordered):
        if i < len(pos_labels):
            seat_to_pos[sn] = pos_labels[i]
        else:
            seat_to_pos[sn] = f"S{sn}"

    for s in seats:
        s["position"] = seat_to_pos[s["seat"]]


def parse_hand_history(hand_text: str, db: duckdb.DuckDBPyConnection) -> str:
    """Parse a single GGPoker hand history and store in DuckDB.

    Returns the hand_id string.
    """
    # Strip BOM, null bytes, zero-width chars, and other invisible Unicode before parsing
    hand_text = hand_text.replace("\x00", "").replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # ── Parse header ──
    m = RE_HEADER.search(lines[0])
    if not m:
        raise ValueError(f"Cannot parse header line: {lines[0]}")

    hand_id = m.group(1)
    sb_amount = Decimal(m.group(2))
    bb_amount = Decimal(m.group(3))
    played_at = datetime.strptime(m.group(4), "%Y/%m/%d %H:%M:%S")
    stakes = f"${m.group(2)}/${m.group(3)}"
    game_type = "NLH"

    # ── Parse table info ──
    m = RE_TABLE.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse table line: {lines[1]}")

    table_name = m.group(1)
    table_size = int(m.group(2))
    button_seat = int(m.group(3))

    # ── Parse seats ──
    seats = []  # list of {seat, username, stack}
    username_to_seat = {}
    line_idx = 2

    while line_idx < len(lines):
        m = RE_SEAT.match(lines[line_idx])
        if not m:
            break
        seat_num = int(m.group(1))
        username = m.group(2)
        stack = Decimal(m.group(3))
        seats.append({"seat": seat_num, "username": username, "stack": stack})
        username_to_seat[username] = seat_num
        line_idx += 1

    if not seats:
        raise ValueError("No seats found")

    _assign_positions(seats, button_seat, table_size)

    # Build lookup structures
    seat_to_info = {s["seat"]: s for s in seats}
    username_to_info = {s["username"]: s for s in seats}

    # ── Get or create players ──
    _init_counters(db)
    player_ids = {}  # username -> player_id
    for s in seats:
        player_ids[s["username"]] = _get_or_create_player(db, s["username"])

    # ── Parse action lines ──
    # We need to track: hole cards, actions per street, board cards, collected amounts
    hero_cards = {}  # username -> (card1, card2)
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    current_street = "preflop"
    board_cards = {"flop": [], "turn": [], "river": []}
    uncalled_returns = {}  # username -> amount
    collected = {}  # username -> total amount collected
    total_rake = Decimal("0")
    went_to_showdown_players = set()
    in_showdown = False
    in_summary = False

    # Track blinds/antes posted
    blinds_posted = {}  # username -> "sb" | "bb" | "straddle" | "ante"
    sb_player = None
    bb_player = None

    action_order = 0

    for raw_line in lines[line_idx:]:
        line = raw_line.strip()
        if not line:
            continue
        if _should_skip(line):
            continue

        # Street markers
        if line.startswith("*** HOLE CARDS ***"):
            current_street = "preflop"
            continue
        m = RE_FLOP.match(line)
        if m:
            current_street = "flop"
            cards = m.group(1).split()
            board_cards["flop"] = cards
            continue
        m = RE_TURN.match(line)
        if m:
            current_street = "turn"
            board_cards["turn"] = [m.group(1)]
            continue
        m = RE_RIVER.match(line)
        if m:
            current_street = "river"
            board_cards["river"] = [m.group(1)]
            continue
        if RE_SHOWDOWN.match(line):
            in_showdown = True
            continue
        if RE_SUMMARY.match(line):
            in_summary = True
            continue

        # Summary section parsing
        if in_summary:
            m = RE_SUMMARY_POT.search(line)
            if m:
                # Sum all fees: Rake + Jackpot + Bingo + Fortune + Tax
                for fee_m in RE_SUMMARY_FEE.finditer(line):
                    total_rake += Decimal(fee_m.group(1))
                continue

            # Board line fallback — populate board_cards from summary if empty
            m = RE_BOARD.search(line)
            if m:
                cards = m.group(1).split()
                if not board_cards["flop"] and len(cards) >= 3:
                    board_cards["flop"] = cards[:3]
                if not board_cards["turn"] and len(cards) >= 4:
                    board_cards["turn"] = [cards[3]]
                if not board_cards["river"] and len(cards) >= 5:
                    board_cards["river"] = [cards[4]]
                continue

            m = RE_SHOWED.match(line)
            if m:
                uname = m.group(2).strip()
                if uname in username_to_info:
                    hero_cards[uname] = (m.group(3), m.group(4))
                # Don't continue — also check for won/collected on same line (e.g. "showed [As 8h] and won ($11.00)")

            # Collected/won in summary — handle multiple "won ($X)" on same line (Run It Twice)
            seat_m = RE_SEAT_USERNAME.match(line)
            uname_from_seat = seat_m.group(1).strip() if seat_m else None

            # Find ALL won/collected amounts on this line
            found_any = False
            for m_coll in re.finditer(r"(?:collected|won) \(\$([0-9.]+)\)", line):
                amt = Decimal(m_coll.group(1))
                uname = uname_from_seat or "unknown"
                collected[uname] = collected.get(uname, Decimal("0")) + amt
                found_any = True

            if found_any:
                continue
            continue

        # Dealt hole cards (skip lines like "Dealt to Player " with no cards)
        if line.startswith("Dealt to"):
            m = RE_DEALT.match(line)
            if m:
                hero_cards[m.group(1)] = (m.group(2), m.group(3))
            continue

        # Blinds / antes (before action tracking)
        m = RE_ANTE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            blinds_posted[uname] = "ante"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "ante",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_SMALL_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            sb_player = uname
            blinds_posted[uname] = "sb"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "sb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_BIG_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            bb_player = uname
            blinds_posted[uname] = "bb"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "bb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_STRADDLE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            blinds_posted[uname] = "straddle"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "straddle",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Uncalled bet
        m = RE_UNCALLED.match(line)
        if m:
            amt = Decimal(m.group(1))
            uname = m.group(2).strip()
            uncalled_returns[uname] = uncalled_returns.get(uname, Decimal("0")) + amt
            continue

        # Collected during hand body (before summary) — skip these,
        # we use the summary section as the authoritative source to avoid double-counting
        if not in_summary:
            m = RE_COLLECTED_FROM_POT.match(line) or RE_COLLECTED.search(line)
            if m:
                continue

        # Shows hand (during showdown)
        m = RE_SHOWS.match(line)
        if m:
            uname = m.group(1)
            hero_cards[uname] = (m.group(2), m.group(3))
            went_to_showdown_players.add(uname)
            continue

        # "does not show hand" — still went to showdown if in showdown section
        m = RE_DOES_NOT_SHOW.match(line)
        if m and in_showdown:
            went_to_showdown_players.add(m.group(1))
            continue

        # ── Voluntary actions ──
        is_all_in = bool(RE_ALLIN_MARKER.search(line))

        m = RE_FOLD.match(line)
        if m:
            uname = m.group(1)
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "fold",
                    "amount": Decimal("0"),
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_CHECK.match(line)
        if m:
            uname = m.group(1)
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "check",
                    "amount": Decimal("0"),
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_CALL.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "call",
                    "amount": amt,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

        m = RE_BET.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "bet",
                    "amount": amt,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

        m = RE_RAISE.match(line)
        if m:
            uname = m.group(1)
            raise_to = Decimal(m.group(3))  # GGPoker shows raise TO amount
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": raise_to,  # Store the "to" amount
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

    # ── Compute stats ──
    # Build per-player stat dictionaries
    player_stats = {}
    for s in seats:
        uname = s["username"]
        player_stats[uname] = {
            "vpip": False,
            "pfr": False,
            "three_bet": False,
            "three_bet_opp": False,
            "four_bet": False,
            "four_bet_opp": False,
            "fold_to_3bet": None,
            "fold_to_4bet": None,
            "open_raise": False,
            "call_open_raise": False,
            "limp": False,
            "squeeze": False,
            "five_bet": False,
            "steal_attempted": False,
            "faced_steal": False,
            "fold_to_steal": None,
            "call_steal": None,
            "three_bet_vs_steal": None,
            "saw_flop": False,
            "saw_turn": False,
            "saw_river": False,
            "went_to_showdown": False,
            "won_at_showdown": None,
            "cbet_flop": None,
            "cbet_flop_opp": False,
            "cbet_turn": None,
            "cbet_turn_opp": False,
            "cbet_river": None,
            "cbet_river_opp": False,
            "fold_to_cbet_flop": None,
            "fold_to_cbet_turn": None,
            "fold_to_cbet_river": None,
            "missed_cbet_flop": False,
            "missed_cbet_turn": False,
            "donk_bet_flop": None,
            "donk_bet_turn": None,
            "donk_bet_river": None,
            "flop_bets": 0,
            "flop_raises": 0,
            "flop_calls": 0,
            "turn_bets": 0,
            "turn_raises": 0,
            "turn_calls": 0,
            "river_bets": 0,
            "river_raises": 0,
            "river_calls": 0,
        }

    # ── Preflop stat computation ──
    preflop_actions = actions_by_street["preflop"]

    # Filter to voluntary actions only (exclude blinds/antes/straddle)
    voluntary_types = {"fold", "check", "call", "bet", "raise"}
    voluntary_preflop = [a for a in preflop_actions if a["action"] in voluntary_types]

    # Count raises to determine bet levels:
    # posting BB = forced (1-bet), first raise = open raise (2-bet),
    # next raise = 3-bet, etc.
    raise_count = 0  # How many raises have occurred (not counting blinds)
    has_caller_or_limper_before_raise = False
    first_raiser = None
    second_raiser = None  # 3-bettor
    third_raiser = None  # 4-bettor
    is_steal = False

    # Track who has acted voluntarily and who has folded
    folded_preflop = set()
    players_who_called = set()

    for a in voluntary_preflop:
        uname = a["username"]
        action = a["action"]
        position = username_to_info[uname]["position"]

        if action == "fold":
            folded_preflop.add(uname)

            # Check fold to 3bet
            if raise_count == 2 and uname == first_raiser:
                player_stats[uname]["fold_to_3bet"] = True

            # Check fold to 4bet
            if raise_count == 3 and uname == second_raiser:
                player_stats[uname]["fold_to_4bet"] = True

            # Check fold to steal
            if player_stats[uname]["faced_steal"]:
                player_stats[uname]["fold_to_steal"] = True
            continue

        if action == "call":
            player_stats[uname]["vpip"] = True

            if raise_count == 0:
                # Calling the big blind = limp
                player_stats[uname]["limp"] = True
                has_caller_or_limper_before_raise = True
            elif raise_count == 1:
                # Calling an open raise
                player_stats[uname]["call_open_raise"] = True
                players_who_called.add(uname)

                # Check if facing steal
                if player_stats[uname]["faced_steal"]:
                    player_stats[uname]["call_steal"] = True
                    player_stats[uname]["fold_to_steal"] = False
            elif raise_count == 2:
                # Calling a 3bet — if this was the original raiser, not a fold_to_3bet
                if uname == first_raiser:
                    player_stats[uname]["fold_to_3bet"] = False
            elif raise_count == 3:
                if uname == second_raiser:
                    player_stats[uname]["fold_to_4bet"] = False

        elif action == "raise":
            player_stats[uname]["vpip"] = True
            player_stats[uname]["pfr"] = True
            raise_count += 1

            if raise_count == 1:
                # Open raise (2-bet)
                player_stats[uname]["open_raise"] = True
                first_raiser = uname

                # Check if steal attempt (open raise from CO, BTN, or SB)
                if position in ("CO", "BTN", "SB"):
                    player_stats[uname]["steal_attempted"] = True
                    is_steal = True

                    # Mark BB (and SB if steal from CO/BTN) as facing steal
                    if bb_player and bb_player not in folded_preflop:
                        player_stats[bb_player]["faced_steal"] = True
                    if position in ("CO", "BTN"):
                        if sb_player and sb_player not in folded_preflop:
                            player_stats[sb_player]["faced_steal"] = True

                # If there were limpers before, everyone after who raises
                # still gets open_raise = True since it's the first raise.
                # But if there was a limp + raise, the raise is still an open raise.
                # Squeeze: raise when there was already a raise AND at least one caller
                # This is actually the first raise, so no squeeze here.

            elif raise_count == 2:
                # 3-bet
                player_stats[uname]["three_bet"] = True
                second_raiser = uname

                # The first raiser had a 3bet opportunity
                if first_raiser:
                    player_stats[first_raiser]["three_bet_opp"] = True

                # Check if this is a squeeze (3bet when there are callers of the open)
                if players_who_called:
                    player_stats[uname]["squeeze"] = True

                # Check 3bet vs steal
                if is_steal and player_stats[uname]["faced_steal"]:
                    player_stats[uname]["three_bet_vs_steal"] = True
                    player_stats[uname]["fold_to_steal"] = False

            elif raise_count == 3:
                # 4-bet
                player_stats[uname]["four_bet"] = True
                third_raiser = uname

                # The 3-bettor had a 4bet opportunity
                if second_raiser:
                    player_stats[second_raiser]["four_bet_opp"] = True

                # The original raiser also sees this — not a fold_to_3bet
                if first_raiser and first_raiser != uname:
                    player_stats[first_raiser]["fold_to_3bet"] = False

            elif raise_count == 4:
                # 5-bet
                player_stats[uname]["five_bet"] = True

                # The 4-bettor had opportunity
                if third_raiser:
                    player_stats[third_raiser]["four_bet_opp"] = True

        elif action in ("bet", "check"):
            # A bet preflop would be unusual, but handle it
            if action == "bet":
                player_stats[uname]["vpip"] = True

    # ── Mark 3-bet opp for players who haven't been tagged yet ──
    # Everyone who acted after the open raise had a 3-bet opportunity
    if first_raiser:
        first_raise_order = _find_action_order(voluntary_preflop, first_raiser, "raise")
        if first_raise_order is not None:
            for a in voluntary_preflop:
                if a["order"] > first_raise_order and a["username"] != first_raiser:
                    player_stats[a["username"]]["three_bet_opp"] = True

    # ── Mark faced_steal fold defaults ──
    for s in seats:
        uname = s["username"]
        if player_stats[uname]["faced_steal"] and player_stats[uname]["fold_to_steal"] is None:
            # They faced a steal but didn't fold, call, or 3bet — they must have folded
            # (this shouldn't happen if all actions were tracked, but as safety)
            if uname in folded_preflop:
                player_stats[uname]["fold_to_steal"] = True
            else:
                player_stats[uname]["fold_to_steal"] = False

    # ── Determine who saw each street ──
    players_in_hand = set(s["username"] for s in seats)
    players_folded = set()

    for street in ["preflop", "flop", "turn", "river"]:
        for a in actions_by_street[street]:
            if a["action"] == "fold":
                players_folded.add(a["username"])

        if street == "preflop":
            # Players who didn't fold preflop saw the flop (if flop was dealt)
            if board_cards["flop"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_flop"] = True
        elif street == "flop":
            if board_cards["turn"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_turn"] = True
        elif street == "turn":
            if board_cards["river"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_river"] = True

    # ── Showdown stats ──
    # Determine who went to showdown
    # Only a real showdown if 2+ players remain (GGPoker shows *** SHOWDOWN *** even for no-contest pots)
    remaining_players = players_in_hand - players_folded
    real_showdown = len(remaining_players) >= 2 and (in_showdown or went_to_showdown_players)
    if real_showdown:
        for uname in remaining_players:
            player_stats[uname]["went_to_showdown"] = True
            went_to_showdown_players.add(uname)

    for uname in went_to_showdown_players:
        if uname in collected:
            player_stats[uname]["won_at_showdown"] = True
        else:
            player_stats[uname]["won_at_showdown"] = False

    # ── Postflop stats (cbet, donk bet, aggression counts) ──
    # Determine preflop aggressor (last raiser preflop)
    preflop_aggressor = None
    for a in reversed(preflop_actions):
        if a["action"] == "raise":
            preflop_aggressor = a["username"]
            break

    # Track last aggressor per street for cbet continuation
    street_aggressor = {"preflop": preflop_aggressor}

    for street in ["flop", "turn", "river"]:
        street_actions = actions_by_street[street]
        if not street_actions:
            continue

        # Determine who is the previous-street aggressor for cbet
        prev_street = {"flop": "preflop", "turn": "flop", "river": "turn"}[street]
        prev_aggressor = street_aggressor.get(prev_street)

        first_bet_or_raise = None
        aggressor_acted = False
        aggressor_bet = False

        for a in street_actions:
            uname = a["username"]
            action = a["action"]

            # Aggression counts
            if action == "bet":
                player_stats[uname][f"{street}_bets"] += 1
            elif action == "raise":
                player_stats[uname][f"{street}_raises"] += 1
            elif action == "call":
                player_stats[uname][f"{street}_calls"] += 1

            # Track who bet/raised first for cbet and donk
            if action in ("bet", "raise") and first_bet_or_raise is None:
                first_bet_or_raise = a

            # Cbet opportunity: if prev aggressor is in this street's actors
            if prev_aggressor and uname == prev_aggressor:
                aggressor_acted = True
                if action in ("bet", "raise"):
                    aggressor_bet = True

        # Set cbet stats
        if prev_aggressor and prev_aggressor in (players_in_hand - players_folded):
            # Only if the previous aggressor saw this street
            if player_stats[prev_aggressor][f"saw_{street}"]:
                player_stats[prev_aggressor][f"cbet_{street}_opp"] = True
                if aggressor_bet:
                    player_stats[prev_aggressor][f"cbet_{street}"] = True
                    street_aggressor[street] = prev_aggressor
                else:
                    player_stats[prev_aggressor][f"cbet_{street}"] = False
                    if street in ("flop", "turn"):
                        player_stats[prev_aggressor][f"missed_cbet_{street}"] = True

        # Track who the last aggressor was on this street
        for a in reversed(street_actions):
            if a["action"] in ("bet", "raise"):
                street_aggressor[street] = a["username"]
                break

        # Donk bet: first bet into the preflop aggressor
        if first_bet_or_raise and first_bet_or_raise["action"] == "bet":
            bettor = first_bet_or_raise["username"]
            if prev_aggressor and bettor != prev_aggressor:
                player_stats[bettor][f"donk_bet_{street}"] = True

        # Fold to cbet: players who face a cbet and fold
        if prev_aggressor and aggressor_bet:
            # The cbet happened — check who faced it and folded
            cbet_order = None
            for a in street_actions:
                if a["username"] == prev_aggressor and a["action"] in ("bet", "raise"):
                    cbet_order = a["order"]
                    break
            if cbet_order is not None:
                for a in street_actions:
                    if a["order"] > cbet_order and a["username"] != prev_aggressor:
                        if a["action"] == "fold":
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = True
                        elif a["action"] in ("call", "raise"):
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = False

    # ── Calculate per-player investment ──
    player_invested = {s["username"]: Decimal("0") for s in seats}

    for street in ["preflop", "flop", "turn", "river"]:
        street_put_in: dict[str, Decimal] = {}

        for a in actions_by_street[street]:
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
        for a in actions_by_street[street]:
            if a["is_all_in"]:
                if all_in_street is None:
                    all_in_street = street
                break
        if all_in_street is not None:
            break

    # ── Calculate won/rake amounts ──
    num_winners = len(collected)
    per_player_rake = total_rake / max(num_winners, 1) if total_rake else Decimal("0")

    # ── Compute all-in EV ──
    all_in_ev_bb_map = {}  # username -> ev_bb

    if all_in_street is not None and real_showdown and len(remaining_players) == 2:
        # Board at the all-in point
        board_at_all_in = []
        if street_order_map[all_in_street] >= 1:
            board_at_all_in.extend(board_cards["flop"])
        if street_order_map[all_in_street] >= 2:
            board_at_all_in.extend(board_cards["turn"])
        if street_order_map[all_in_street] >= 3:
            board_at_all_in.extend(board_cards["river"])

        cards_to_come = 5 - len(board_at_all_in)

        if cards_to_come > 0:
            # Check we know both players' cards
            players_list = list(remaining_players)
            if players_list[0] in hero_cards and players_list[1] in hero_cards and _calc_equity:
                try:
                    p1, p2 = players_list
                    p1_eq = _calc_equity(
                        hero_cards[p1], hero_cards[p2], board_at_all_in
                    )
                    p2_eq = 1.0 - p1_eq

                    # Subtract uncalled bets — money returned was never at risk
                    p1_net = float(player_invested[p1]) - float(uncalled_returns.get(p1, Decimal("0")))
                    p2_net = float(player_invested[p2]) - float(uncalled_returns.get(p2, Decimal("0")))
                    total_at_risk = sum(float(v) for v in player_invested.values()) \
                                  - sum(float(v) for v in uncalled_returns.values())
                    distributable = total_at_risk - float(total_rake)

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
            hand_id, SITE_ID, played_at, game_type, stakes,
            float(sb_amount), float(bb_amount), table_name, table_size,
            button_seat, hand_text,
        ],
    )

    # 2. Insert board cards (batched)
    board_rows = []
    for street, cards in board_cards.items():
        for i, card in enumerate(cards):
            board_rows.append([hand_id, street, card, i + 1])
    if board_rows:
        db.executemany(
            "INSERT INTO board_cards (hand_id, street, card, card_order) VALUES (?, ?, ?, ?)",
            board_rows,
        )

    # 3. Insert hand_players
    for s in seats:
        uname = s["username"]
        pid = player_ids[uname]
        cards = hero_cards.get(uname)
        card1 = cards[0] if cards else None
        card2 = cards[1] if cards else None
        gross_collected = collected.get(uname, Decimal("0"))
        uncalled = uncalled_returns.get(uname, Decimal("0"))
        invested = player_invested.get(uname, Decimal("0"))
        net_won = float(gross_collected + uncalled - invested)
        rake = float(per_player_rake) if uname in collected else 0.0
        won = net_won
        won_bb = won / float(bb_amount) if bb_amount else 0.0
        rake_bb = rake / float(bb_amount) if bb_amount else 0.0
        stack_bb = float(s["stack"]) / float(bb_amount) if bb_amount else 0.0
        ps = player_stats[uname]
        ev_bb = all_in_ev_bb_map.get(uname, won_bb)

        global _next_hp_id
        hp_id = _next_hp_id
        _next_hp_id += 1
        db.execute(
            """INSERT INTO hand_players (
                id, hand_id, player_id, seat, position, stack, stack_bb,
                card1, card2, won, won_bb, rake, rake_bb, all_in_ev_bb,
                vpip, pfr, three_bet, three_bet_opp, four_bet, four_bet_opp,
                fold_to_3bet, fold_to_4bet,
                open_raise, call_open_raise, limp, squeeze, five_bet,
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
                ?, ?, ?, ?, ?,
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
                hp_id, hand_id, pid, s["seat"], s["position"],
                float(s["stack"]), stack_bb,
                card1, card2, won, won_bb, rake, rake_bb, ev_bb,
                ps["vpip"], ps["pfr"], ps["three_bet"], ps["three_bet_opp"],
                ps["four_bet"], ps["four_bet_opp"],
                ps["fold_to_3bet"], ps["fold_to_4bet"],
                ps["open_raise"], ps["call_open_raise"], ps["limp"],
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
    global _next_action_id
    action_rows = []
    for street, street_actions in actions_by_street.items():
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
                act_id, hand_id, pid, street,
                a["order"], a["action"], amt, amt_bb, a["is_all_in"],
            ])
    if action_rows:
        db.executemany(
            """INSERT INTO actions (id, hand_id, player_id, street,
               action_order, action_type, amount, amount_bb, is_all_in)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            action_rows,
        )

    return hand_id


def _find_action_order(actions: list[dict], username: str, action_type: str) -> int | None:
    """Find the order number of a specific player's action."""
    for a in actions:
        if a["username"] == username and a["action"] == action_type:
            return a["order"]
    return None
