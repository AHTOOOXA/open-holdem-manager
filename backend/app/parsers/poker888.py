"""
888poker hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import re
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions, compute_uncalled_returns

SITE_ID = 3
SITE_CODE = "888"
SITE_NAME = "888poker"

# Streets in order for investment/uncalled computation
_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))

# ── Regex patterns ──

RE_HEADER = re.compile(
    r"\*{5} 888poker Hand History for Game (\d+) \*{5}"
)
RE_STAKES = re.compile(
    r"\$([0-9.]+)/\$([0-9.]+) Blinds"
)
RE_DATE = re.compile(
    r"\*{3} (\d{2}) (\d{2}) (\d{4}) (\d{2}:\d{2}:\d{2})"
)
RE_TABLE = re.compile(
    r"Table (.+?) (\d+) Max"
)
RE_BUTTON = re.compile(
    r"Seat (\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \( \$([0-9.]+) \)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?) posts small blind \[\$([0-9.]+)\]$"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?) posts big blind \[\$([0-9.]+)\]$"
)
RE_DEALT = re.compile(
    r"^Dealt to (.+?) \[ (.+?) \]$"
)
RE_DEALING_STREET = re.compile(
    r"^\*\* Dealing (down cards|flop|turn|river) \*\*(?:\s*\[ (.+?) \])?"
)
RE_COLLECTED = re.compile(
    r"^(.+?) collected \[ \$([0-9.]+) \]$"
)
RE_SHOWS = re.compile(
    r"^(.+?) shows \[ (.+?) \]$"
)
RE_DID_NOT_SHOW = re.compile(
    r"^(.+?) did not show his hand$"
)
RE_END_OF_HAND = re.compile(
    r"^\*{5} End of hand"
)

# Action patterns (no colon before action keyword)
RE_FOLD = re.compile(r"^(.+?) folds$")
RE_CHECK = re.compile(r"^(.+?) checks$")
RE_CALL = re.compile(r"^(.+?) calls \[\$([0-9.]+)\](?:\s*\[all in\])?$")
RE_BET = re.compile(r"^(.+?) bets \[\$([0-9.]+)\](?:\s*\[all in\])?$")
RE_RAISE = re.compile(r"^(.+?) raises \[\$([0-9.]+)\](?:\s*\[all in\])?$")
RE_ALLIN_MARKER = re.compile(r"\[all in\]")


def detect(sample: str) -> bool:
    """Check if this content is an 888poker hand history."""
    return "888poker Hand History" in sample[:500]


def split_hands(content: str) -> list[str]:
    """Split a file with multiple 888poker hand histories into individual hands.

    Files may have '#Game No : NNNN' lines before each hand header.
    Split on the ***** header, then re-attach any preceding #Game No line.
    """
    # Strip BOM if present
    content = content.lstrip("\ufeff")
    # Split just before the ***** header line
    parts = re.split(r'\n(?=\*{5} 888poker Hand History)', content)
    # Also handle files that start with #Game No before the first hand
    result = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Skip standalone #Game No fragments (no header follows)
        if p.startswith("#Game No") and "888poker Hand History" not in p:
            continue
        result.append(p)
    return result


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the header line."""
    m = RE_HEADER.search(hand_text)
    return m.group(1) if m else None


def _parse_cards(card_str: str) -> list[str]:
    """Parse comma-separated card string like 'Ah, Kd' into ['Ah', 'Kd']."""
    return [c.strip() for c in card_str.split(",")]


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single 888poker hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    # Strip BOM and invisible chars
    hand_text = hand_text.replace("\ufeff", "").replace("\x00", "")
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # Skip "#Game No :" prefix line if present
    while lines and lines[0].startswith("#Game No"):
        lines.pop(0)

    # ── Parse header ──
    m = RE_HEADER.search(lines[0])
    if not m:
        raise ValueError(f"Cannot parse 888poker header: {lines[0]}")
    hand_id = m.group(1)

    # ── Parse stakes and date from second line ──
    m = RE_STAKES.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse stakes: {lines[1]}")
    sb_amount = Decimal(m.group(1))
    bb_amount = Decimal(m.group(2))

    m = RE_DATE.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse date: {lines[1]}")
    day, month, year, time_str = m.group(1), m.group(2), m.group(3), m.group(4)
    played_at = datetime.strptime(f"{year}/{month}/{day} {time_str}", "%Y/%m/%d %H:%M:%S")

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"
    game_mode = ""  # 888poker doesn't have fast-fold in these histories

    # ── Parse table info ──
    m = RE_TABLE.search(lines[2])
    if not m:
        raise ValueError(f"Cannot parse table: {lines[2]}")
    table_name = m.group(1)
    table_size = int(m.group(2))

    # ── Parse button ──
    m = RE_BUTTON.search(lines[3])
    if not m:
        raise ValueError(f"Cannot parse button: {lines[3]}")
    button_seat = int(m.group(1))

    # ── Parse seats ──
    seats = []
    username_to_seat = {}
    line_idx = 4  # Skip "Total number of players" line

    # Skip the "Total number of players" line
    while line_idx < len(lines):
        if lines[line_idx].startswith("Total number of players"):
            line_idx += 1
            break
        line_idx += 1

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
    username_set = {s["username"] for s in seats}

    # ── Parse action lines ──
    hero_cards = {}
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    current_street = "preflop"
    board_cards = {"flop": [], "turn": [], "river": []}
    collected = {}
    went_to_showdown_players = set()
    in_showdown = False

    sb_player = None
    bb_player = None

    action_order = 0

    for line in lines[line_idx:]:
        # End of hand marker
        if RE_END_OF_HAND.match(line):
            break

        # Street markers
        m = RE_DEALING_STREET.match(line)
        if m:
            street_name = m.group(1)
            if street_name == "down cards":
                current_street = "preflop"
            elif street_name == "flop":
                current_street = "flop"
                if m.group(2):
                    board_cards["flop"] = _parse_cards(m.group(2))
            elif street_name == "turn":
                current_street = "turn"
                if m.group(2):
                    board_cards["turn"] = _parse_cards(m.group(2))
            elif street_name == "river":
                current_street = "river"
                if m.group(2):
                    board_cards["river"] = _parse_cards(m.group(2))
            continue

        # Dealt hole cards
        m = RE_DEALT.match(line)
        if m:
            cards = _parse_cards(m.group(2))
            if len(cards) == 2:
                hero_cards[m.group(1)] = (cards[0], cards[1])
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

        # Shows hand
        m = RE_SHOWS.match(line)
        if m:
            uname = m.group(1)
            cards = _parse_cards(m.group(2))
            if len(cards) == 2 and uname in username_set:
                hero_cards[uname] = (cards[0], cards[1])
                went_to_showdown_players.add(uname)
            continue

        # Did not show hand
        m = RE_DID_NOT_SHOW.match(line)
        if m:
            continue

        # Collected
        m = RE_COLLECTED.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            collected[uname] = collected.get(uname, _ZERO) + amt
            continue

        # ── Voluntary actions ──
        is_all_in = bool(RE_ALLIN_MARKER.search(line))

        m = RE_FOLD.match(line)
        if m:
            uname = m.group(1)
            if uname in username_set:
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
            if uname in username_set:
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
            if uname in username_set:
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
            if uname in username_set:
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
            amt = Decimal(m.group(2))  # "to" amount
            if uname in username_set:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": amt,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

    # ── Showdown detection ──
    if len(went_to_showdown_players) >= 2:
        in_showdown = True

    # ── Compute uncalled returns ──
    uncalled_returns = compute_uncalled_returns(actions_by_street)

    # ── Compute rake ──
    # total_invested from actions (same logic as _compute_financials)
    total_invested = _ZERO
    for street in _STREETS:
        street_put_in: dict[str, Decimal] = {}
        for a in actions_by_street[street]:
            uname = a["username"]
            action = a["action"]
            amt = a["amount"]

            if action in _INVEST_ACTIONS:
                street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
                total_invested += amt
            elif action == "raise":
                already_in = street_put_in.get(uname, _ZERO)
                increment = amt - already_in
                if increment > 0:
                    total_invested += increment
                street_put_in[uname] = amt

    total_uncalled = sum(uncalled_returns.values())
    total_collected = sum(collected.values())
    total_rake = total_invested - total_uncalled - total_collected
    if total_rake < _ZERO:
        total_rake = _ZERO

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
        total_jackpot=_ZERO,
        went_to_showdown_players=went_to_showdown_players,
        in_showdown=in_showdown,
        sb_player=sb_player,
        bb_player=bb_player,
        raw_text=hand_text,
    )
