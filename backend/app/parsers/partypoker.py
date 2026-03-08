"""
partypoker hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import re
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions

SITE_ID = 7
SITE_CODE = "PP"
SITE_NAME = "partypoker"

# Streets in order for investment/uncalled computation
_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))

# ── Regex patterns ──

RE_HEADER = re.compile(
    r"\*{5} Hand History For Game (\d+) \*{5}"
)
RE_STAKES = re.compile(
    r"\$([0-9.]+)/\$([0-9.]+) USD"
)
RE_DATE = re.compile(
    r"\w+, (\w+) (\d+), (\d{2}:\d{2}:\d{2}) \w+ (\d{4})"
)
RE_TABLE = re.compile(
    r"Table (.+?) (\d+) Max"
)
RE_BUTTON = re.compile(
    r"Seat (\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \( \$([0-9.]+) USD \)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?) posts small blind \[\$([0-9.]+) USD\]\.$"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?) posts big blind \[\$([0-9.]+) USD\]\.$"
)
RE_DEALT = re.compile(
    r"^Dealt to (.+?) \[\s+(.+?)\s+\]$"
)
RE_DEALING_STREET = re.compile(
    r"^\*\* Dealing (down cards|Flop|Turn|River) \*\*(?:\s*\[ (.+?) \])?"
)
RE_WINS = re.compile(
    r"^(.+?) wins \$([0-9.]+) USD(?:\s+from .+)?$"
)
RE_SHOWS = re.compile(
    r"^(.+?) shows \[ (.+?) \]$"
)
RE_DOESNT_SHOW = re.compile(
    r"^(.+?) doesn't show \[ (.+?) \]$"
)
RE_FOOTER = re.compile(
    r"^\*{5} Hand History For Game \d+ \*{5}$"
)

# Action patterns — amounts have [$X USD] format
RE_FOLD = re.compile(r"^(.+?) folds$")
RE_CHECK = re.compile(r"^(.+?) checks$")
RE_CALL = re.compile(r"^(.+?) calls \[\$([0-9.]+) USD\]$")
RE_BET = re.compile(r"^(.+?) bets \[\$([0-9.]+) USD\]$")
RE_RAISE = re.compile(r"^(.+?) raises \[\$([0-9.]+) USD\]$")
RE_ALLIN = re.compile(r"(?:is all-[Ii]n|\[all in\])")


def detect(sample: str) -> bool:
    """Check if this content is a partypoker hand history."""
    if "888poker" in sample[:500]:
        return False
    return "Hand History For Game" in sample[:500]


def split_hands(content: str) -> list[str]:
    """Split a file with multiple partypoker hand histories into individual hands.

    Each hand starts and ends with ***** Hand History For Game NNNN *****.
    Split on blank lines between hands, then strip footer lines.
    """
    parts = re.split(r'\n\n+(?=\*{5} Hand History For Game)', content)
    return [p.strip() for p in parts if p.strip()]


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the header line."""
    m = RE_HEADER.search(hand_text)
    return m.group(1) if m else None


def _parse_cards(card_str: str) -> list[str]:
    """Parse card string — handles both comma-separated 'Ah, Kd' and space-separated 'Ah Kd'."""
    if "," in card_str:
        return [c.strip() for c in card_str.split(",")]
    return card_str.strip().split()


def _compute_uncalled_returns(
    actions_by_street: dict[str, list[dict]],
    collected: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Compute uncalled bet returns from action sequence.

    partypoker doesn't show explicit uncalled bet lines. When a player bets/raises
    and everyone folds, their excess over the next highest contribution is returned.
    """
    uncalled = {}

    # Find the last street that had actions
    last_street = None
    for street in reversed(_STREETS):
        if actions_by_street[street]:
            last_street = street
            break

    if last_street is None:
        return uncalled

    # Track who folded across all streets
    folded = set()
    for street in _STREETS:
        for a in actions_by_street[street]:
            if a["action"] == "fold":
                folded.add(a["username"])

    # Check if only one player remains (everyone else folded)
    all_players = set()
    for street in _STREETS:
        for a in actions_by_street[street]:
            all_players.add(a["username"])

    remaining = all_players - folded
    if len(remaining) > 1:
        # Multiple players remained — no uncalled bet (went to showdown)
        return uncalled

    # One player left — compute their excess on the last active street
    street_put_in: dict[str, Decimal] = {}
    for a in actions_by_street[last_street]:
        uname = a["username"]
        action = a["action"]
        amt = a["amount"]

        if action in _INVEST_ACTIONS:
            street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
        elif action == "raise":
            street_put_in[uname] = amt  # "to" amount

    if not street_put_in:
        return uncalled

    # Find max and second-max contributions on this street
    amounts = sorted(street_put_in.values(), reverse=True)
    if len(amounts) < 2:
        # Only one player acted on this street (e.g. bet then fold)
        max_player = max(street_put_in, key=street_put_in.get)
        if max_player in remaining:
            uncalled[max_player] = amounts[0]
        return uncalled

    max_amount = amounts[0]
    second_max = amounts[1]

    if max_amount > second_max:
        max_player = None
        for p, amt in street_put_in.items():
            if amt == max_amount and p in remaining:
                max_player = p
                break

        if max_player:
            uncalled[max_player] = max_amount - second_max

    return uncalled


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single partypoker hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # ── Parse header ──
    m = RE_HEADER.search(lines[0])
    if not m:
        raise ValueError(f"Cannot parse partypoker header: {lines[0]}")
    hand_id = m.group(1)

    # ── Parse stakes and date from second line ──
    # "$0.25/$0.50 USD NL Texas Hold'em - Monday, January 15, 14:30:00 UTC 2024"
    m = RE_STAKES.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse stakes: {lines[1]}")
    sb_amount = Decimal(m.group(1))
    bb_amount = Decimal(m.group(2))

    m = RE_DATE.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse date: {lines[1]}")
    month_name, day, time_str, year = m.group(1), m.group(2), m.group(3), m.group(4)
    played_at = datetime.strptime(f"{year}/{month_name}/{day} {time_str}", "%Y/%B/%d %H:%M:%S")

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"
    game_mode = ""

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
    line_idx = 4

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
        # Footer line — end of hand
        if RE_FOOTER.match(line) and lines.index(line) > 0:
            break

        # Street markers
        m = RE_DEALING_STREET.match(line)
        if m:
            street_name = m.group(1)
            if street_name == "down cards":
                current_street = "preflop"
            elif street_name == "Flop":
                current_street = "flop"
                if m.group(2):
                    board_cards["flop"] = _parse_cards(m.group(2))
            elif street_name == "Turn":
                current_street = "turn"
                if m.group(2):
                    board_cards["turn"] = _parse_cards(m.group(2))
            elif street_name == "River":
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

        # Doesn't show hand
        m = RE_DOESNT_SHOW.match(line)
        if m:
            uname = m.group(1)
            cards = _parse_cards(m.group(2))
            if len(cards) == 2 and uname in username_set:
                hero_cards[uname] = (cards[0], cards[1])
            continue

        # Wins
        m = RE_WINS.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            collected[uname] = collected.get(uname, _ZERO) + amt
            continue

        # ── Voluntary actions ──
        is_all_in = bool(RE_ALLIN.search(line))

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
    uncalled_returns = _compute_uncalled_returns(actions_by_street, collected)

    # ── Compute rake ──
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
