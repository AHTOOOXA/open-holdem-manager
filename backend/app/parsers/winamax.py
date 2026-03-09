"""
Winamax hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import re
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions

SITE_ID = 5
SITE_CODE = "WMX"
SITE_NAME = "Winamax"

# Streets in order for investment/uncalled computation
_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))

# ── Regex patterns ──

RE_HEADER = re.compile(
    r"Winamax Poker - CashGame - HandId: #([0-9-]+) - "
    r"Holdem no limit \(([0-9.]+)€/([0-9.]+)€\) - "
    r"(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) UTC"
)
RE_TABLE = re.compile(
    r"Table: '([^']+)' (\d+)-max \(real money\) Seat #(\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \(([0-9.]+)€\)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?) posts small blind ([0-9.]+)€$"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?) posts big blind ([0-9.]+)€$"
)
RE_DEALT = re.compile(
    r"Dealt to (.+?) \[(\w{2}) (\w{2})\]"
)
RE_FLOP = re.compile(r"\*\*\* FLOP \*\*\* \[(.+?)\]")
RE_TURN = re.compile(r"\*\*\* TURN \*\*\* \[.+?\] ?\[(\w{2})\]")
RE_RIVER = re.compile(r"\*\*\* RIVER \*\*\* \[.+?\] ?\[(\w{2})\]")
RE_SHOWDOWN = re.compile(r"\*\*\* SHOW DOWN \*\*\*")
RE_SUMMARY = re.compile(r"\*\*\* SUMMARY \*\*\*")

# Actions — no colon before action keyword
RE_FOLD = re.compile(r"^(.+?) folds$")
RE_CHECK = re.compile(r"^(.+?) checks$")
RE_CALL = re.compile(r"^(.+?) calls ([0-9.]+)€(?:\s+and is all-in)?$")
RE_BET = re.compile(r"^(.+?) bets ([0-9.]+)€(?:\s+and is all-in)?$")
RE_RAISE = re.compile(r"^(.+?) raises ([0-9.]+)€ to ([0-9.]+)€(?:\s+and is all-in)?$")
RE_ALLIN_MARKER = re.compile(r"and is all-in")

# Collected during hand body
RE_COLLECTED = re.compile(r"^(.+?) collected ([0-9.]+)€ from pot$")

# Shows hand
RE_SHOWS = re.compile(r"^(.+?) shows \[(\w{2}) (\w{2})\]")

# Summary section
RE_SUMMARY_POT_RAKE = re.compile(
    r"Total pot ([0-9.]+)€ \| Rake ([0-9.]+)€"
)
RE_BOARD = re.compile(r"Board: \[(.+?)\]")
RE_SUMMARY_WON = re.compile(
    r"Seat \d+: (.+?)(?:\s+\((?:button|small blind|big blind)\))*\s+(?:showed .+? and )?won ([0-9.]+)€"
)
RE_SUMMARY_SHOWED = re.compile(
    r"Seat (\d+): (.+?) (?:.*?)showed \[(\w{2}) (\w{2})\]"
)


def detect(sample: str) -> bool:
    """Check if this content is a Winamax hand history."""
    return "Winamax Poker" in sample[:500]


def split_hands(content: str) -> list[str]:
    """Split a file with multiple Winamax hand histories into individual hands."""
    parts = re.split(r'\n(?=Winamax Poker)', content)
    return [p.strip() for p in parts if p.strip()]


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the header line."""
    m = re.search(r'HandId: #([0-9-]+)', hand_text)
    return m.group(1) if m else None


def _compute_uncalled_returns(
    actions_by_street: dict[str, list[dict]],
    collected: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Compute uncalled bet returns from action sequence.

    Winamax doesn't show explicit uncalled bet lines. When a player bets/raises
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
    """Parse a single Winamax hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    # Strip BOM and invisible chars
    hand_text = hand_text.replace("\ufeff", "").replace("\x00", "")
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # ── Parse header ──
    m = RE_HEADER.search(lines[0])
    if not m:
        raise ValueError(f"Cannot parse Winamax header: {lines[0]}")

    hand_id = m.group(1)
    sb_amount = Decimal(m.group(2))
    bb_amount = Decimal(m.group(3))
    played_at = datetime.strptime(m.group(4), "%Y/%m/%d %H:%M:%S")

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"\u20ac{int(d)}"
        return f"\u20ac{d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"
    game_mode = ""  # Winamax doesn't have fast-fold in these histories

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
    username_set = {s["username"] for s in seats}

    # ── Parse action lines ──
    hero_cards = {}
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    current_street = "preflop"
    board_cards = {"flop": [], "turn": [], "river": []}
    collected = {}
    total_rake = _ZERO
    went_to_showdown_players = set()
    in_showdown = False
    in_summary = False

    sb_player = None
    bb_player = None

    action_order = 0

    for line in lines[line_idx:]:
        # Street markers
        if line == "*** ANTE/BLINDS ***":
            current_street = "preflop"
            continue
        if line.startswith("*** PRE-FLOP ***"):
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
            m = RE_SUMMARY_SHOWED.match(line)
            if m:
                uname = m.group(2).strip()
                if uname in username_set:
                    hero_cards[uname] = (m.group(3), m.group(4))

            # Won amount in summary
            m = RE_SUMMARY_WON.match(line)
            if m:
                uname = m.group(1).strip()
                amt = Decimal(m.group(2))
                collected[uname] = collected.get(uname, _ZERO) + amt
            continue

        # Dealt hole cards
        if line.startswith("Dealt to"):
            m = RE_DEALT.match(line)
            if m:
                hero_cards[m.group(1)] = (m.group(2), m.group(3))
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

        # Collected during hand body — use summary as authoritative for won amounts,
        # but still parse these for the body
        if not in_summary:
            m = RE_COLLECTED.match(line)
            if m:
                # Body collected — skip, summary is authoritative
                continue

        # Shows hand (during showdown)
        m = RE_SHOWS.match(line)
        if m:
            uname = m.group(1)
            if uname in username_set:
                hero_cards[uname] = (m.group(2), m.group(3))
                went_to_showdown_players.add(uname)
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
            raise_to = Decimal(m.group(3))  # Store the "to" amount
            if uname in username_set:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": raise_to,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

    # ── Showdown detection ──
    if len(went_to_showdown_players) >= 2:
        in_showdown = True

    # ── Compute uncalled returns ──
    uncalled_returns = _compute_uncalled_returns(actions_by_street, collected)

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
