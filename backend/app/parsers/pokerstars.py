"""
PokerStars hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import re
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions

SITE_ID = 2
SITE_CODE = "PS"
SITE_NAME = "PokerStars"

# Skip lines that are informational, not actions
RE_SKIP = re.compile(
    r"is disconnected|has timed out|is sitting out|is connected|"
    r"has returned|was removed from the table|said,|"
    r"leaves the table|joins the table|"
    r"doesn't show hand"
)

# Regex patterns
RE_HEADER = re.compile(
    r"PokerStars (?:Zoom )?Hand #(\w+):\s+"
    r"Hold'em No Limit \(\$([0-9.]+)/\$([0-9.]+)(?: USD)?\)"
    r" - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
)
RE_ZOOM = re.compile(r"PokerStars Zoom Hand #")
RE_TABLE = re.compile(
    r"Table '([^']+)' (\d+)-max Seat #(\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \(\$([0-9.]+) in chips\)"
)
RE_ANTE = re.compile(
    r"^(.+?): posts the ante \$([0-9.]+)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?): posts small blind \$([0-9.]+)"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?): posts big blind \$([0-9.]+)"
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
RE_COLLECTED_FROM_POT = re.compile(
    r"^(.+?) collected \$([0-9.]+) from (?:main |side )?pot"
)
RE_FLOP = re.compile(r"\*\*\* FLOP \*\*\* \[(.+?)\]")
RE_TURN = re.compile(r"\*\*\* TURN \*\*\* \[.+?\] \[(\w{2})\]")
RE_RIVER = re.compile(r"\*\*\* RIVER \*\*\* \[.+?\] \[(\w{2})\]")
RE_SHOWDOWN = re.compile(r"\*\*\* SHOW DOWN \*\*\*")
RE_SUMMARY = re.compile(r"\*\*\* SUMMARY \*\*\*")
RE_SHOWS = re.compile(r"^(.+?): shows \[(\w{2}) (\w{2})\]")
RE_SUMMARY_POT_RAKE = re.compile(
    r"Total pot \$([0-9.]+) \| Rake \$([0-9.]+)"
)
RE_BOARD = re.compile(r"Board \[(.+?)\]")
RE_SEAT_USERNAME = re.compile(
    r"Seat \d+: (.+?)(?:\s+\((?:button|small blind|big blind)\))?\s+(?:showed|mucked|folded|collected|won|received)"
)
RE_COLLECTED_WON_AMOUNT = re.compile(r"(?:collected|won) \(\$([0-9.]+)\)")
RE_SHOWED = re.compile(
    r"Seat (\d+): (.+?) (?:.*?)(?:showed|mucked) \[(\w{2}) (\w{2})\]"
)


def _should_skip(line: str) -> bool:
    return RE_SKIP.search(line) is not None


def detect(sample: str) -> bool:
    """Check if this content is a PokerStars hand history."""
    s = sample[:500]
    return "PokerStars Hand #" in s or "PokerStars Zoom Hand #" in s


def split_hands(content: str) -> list[str]:
    """Split a file with multiple PokerStars hand histories into individual hands."""
    return re.split(r'\n(?=PokerStars (?:Zoom )?Hand #)', content)


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the first line."""
    m = re.search(r'PokerStars (?:Zoom )?Hand #(\w+):', hand_text)
    return m.group(1) if m else None


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single PokerStars hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
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

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"

    # Detect Zoom
    game_mode = "Fast Fold" if RE_ZOOM.search(lines[0]) else ""

    # ── Parse table info ──
    m = RE_TABLE.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse table line: {lines[1]}")

    table_name = m.group(1)
    table_size = int(m.group(2))
    button_seat = int(m.group(3))

    # ── Parse seats ──
    seats = []
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

    # Build lookup
    username_to_info = {s["username"]: s for s in seats}

    # ── Parse action lines ──
    hero_cards = {}
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    current_street = "preflop"
    board_cards = {"flop": [], "turn": [], "river": []}
    uncalled_returns = {}
    collected = {}
    total_rake = _ZERO
    total_jackpot = _ZERO
    went_to_showdown_players = set()
    in_showdown = False
    in_summary = False

    sb_player = None
    bb_player = None

    action_order = 0

    for line in lines[line_idx:]:
        if _should_skip(line):
            continue

        # Street markers
        if line.startswith("*** HOLE CARDS ***"):
            current_street = "preflop"
            continue
        m = RE_FLOP.match(line)
        if m:
            current_street = "flop"
            board_cards["flop"] = m.group(1).split()
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

        # Summary section
        if in_summary:
            m = RE_SUMMARY_POT_RAKE.search(line)
            if m:
                total_rake = Decimal(m.group(2))
                continue

            # Board line fallback
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

            # Showed cards in summary
            m = RE_SHOWED.match(line)
            if m:
                uname = m.group(2).strip()
                if uname in username_to_info:
                    hero_cards[uname] = (m.group(3), m.group(4))

            # Collected/won in summary
            seat_m = RE_SEAT_USERNAME.match(line)
            uname_from_seat = seat_m.group(1).strip() if seat_m else None

            found_any = False
            for m_coll in RE_COLLECTED_WON_AMOUNT.finditer(line):
                amt = Decimal(m_coll.group(1))
                uname = uname_from_seat or "unknown"
                collected[uname] = collected.get(uname, _ZERO) + amt
                found_any = True

            if found_any:
                continue
            continue

        # Dealt hole cards
        if line.startswith("Dealt to"):
            m = RE_DEALT.match(line)
            if m:
                hero_cards[m.group(1)] = (m.group(2), m.group(3))
            continue

        # Antes
        m = RE_ANTE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "ante",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Small blind
        m = RE_SMALL_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            sb_player = uname
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "sb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Big blind
        m = RE_BIG_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            bb_player = uname
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "bb",
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
            uncalled_returns[uname] = uncalled_returns.get(uname, _ZERO) + amt
            continue

        # Collected during hand body — skip, we use summary as authoritative
        if not in_summary:
            m = RE_COLLECTED_FROM_POT.match(line)
            if m:
                continue

        # Shows hand (during showdown)
        m = RE_SHOWS.match(line)
        if m:
            uname = m.group(1)
            hero_cards[uname] = (m.group(2), m.group(3))
            went_to_showdown_players.add(uname)
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
                    "amount": _ZERO,
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
                    "amount": _ZERO,
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
            raise_to = Decimal(m.group(3))  # Store the "to" amount
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": raise_to,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

    return ParsedHand(
        hand_id=hand_id,
        site_id=SITE_ID,
        played_at=played_at,
        game_type=game_type,
        game_mode=game_mode,
        stakes=stakes,
        sb_amount=sb_amount,
        bb_amount=bb_amount,
        table_name=table_name,
        table_size=table_size,
        button_seat=button_seat,
        seats=seats,
        actions_by_street=actions_by_street,
        board_cards=board_cards,
        hero_cards=hero_cards,
        uncalled_returns=uncalled_returns,
        collected=collected,
        total_rake=total_rake,
        total_jackpot=total_jackpot,
        went_to_showdown_players=went_to_showdown_players,
        in_showdown=in_showdown,
        sb_player=sb_player,
        bb_player=bb_player,
        raw_text=hand_text,
    )
