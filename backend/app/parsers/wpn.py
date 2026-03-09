"""
WPN (Winning Poker Network / Americas Cardroom) hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.

Real WPN format:
  - Header: "Game started at: YYYY/M/D H:M:S" + "Game ID: NNN SB/BB TableName (Options) (GameType)"
  - No $ currency symbol — amounts are bare: (0.10), (0.25), (44.87)
  - Actions use "Player" prefix: "Player name raises (0.80)"
  - Blinds: "Player name has small blind (0.10)"
  - Card dealing: "Player name received a card."
  - Raises: incremental — "Player name raises (X)" means X additional
  - All-in: "Player name allin (X)" — separate keyword
  - Straddle: "Player name straddle (0.50)"
  - Street markers: "*** FLOP ***: [cards]" (extra colon)
  - Summary: "------ Summary ------" with "Pot: X. Rake Y"
  - Results: "*Player name shows: Hand [cards]. Bets: X. Collects: Y. Wins: Z."
"""

import re
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions

SITE_ID = 4
SITE_CODE = "WPN"
SITE_NAME = "WPN"

# Streets in order for investment/uncalled computation
_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))

# ── Regex patterns ──

RE_GAME_STARTED = re.compile(
    r"Game started at:\s*(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})"
)
RE_GAME_ID = re.compile(
    r"Game ID:\s*(\d+)\s+([0-9.]+)/([0-9.]+)\s+(.+?)\s+\(([^)]*)\)\s*$"
)
RE_BUTTON = re.compile(r"Seat (\d+) is the button")
RE_SEAT = re.compile(r"Seat (\d+):\s+(.+?)\s+\(([0-9.]+)\)\.")
RE_SMALL_BLIND = re.compile(r"^Player (.+?) has small blind \(([0-9.]+)\)$")
RE_BIG_BLIND = re.compile(r"^Player (.+?) has big blind \(([0-9.]+)\)$")
RE_STRADDLE = re.compile(r"^Player (.+?) straddle \(([0-9.]+)\)$")
RE_ANTE = re.compile(r"^Player (.+?) ante \(([0-9.]+)\)$")
RE_RECEIVED_CARD = re.compile(r"^Player .+? received a card\.$")
RE_DEALT = re.compile(r"^Player (.+?) received card: \[(.+?)\]$")

# Action patterns
RE_FOLD = re.compile(r"^Player (.+?) folds$")
RE_CHECK = re.compile(r"^Player (.+?) checks$")
RE_CALL = re.compile(r"^Player (.+?) calls \(([0-9.]+)\)$")
RE_BET = re.compile(r"^Player (.+?) bets \(([0-9.]+)\)$")
RE_RAISE = re.compile(r"^Player (.+?) raises \(([0-9.]+)\)$")
RE_ALLIN = re.compile(r"^Player (.+?) allin \(([0-9.]+)\)$")

# Street markers (note extra colon after ***)
RE_FLOP = re.compile(r"\*\*\* FLOP \*\*\*:\s*\[(.+?)\]")
RE_TURN = re.compile(r"\*\*\* TURN \*\*\*:\s*\[.+?\]\s*\[(.+?)\]")
RE_RIVER = re.compile(r"\*\*\* RIVER \*\*\*:\s*\[.+?\]\s*\[(.+?)\]")

# Summary
RE_SUMMARY_LINE = re.compile(r"^-+ Summary -+$")
RE_POT_RAKE = re.compile(r"Pot:\s*([0-9.]+)\.\s*Rake\s+([0-9.]+)")
RE_BOARD = re.compile(r"Board:\s*\[(.+?)\]")

# Summary player lines
# Winner line starts with *, loser does not
RE_SUMMARY_PLAYER = re.compile(
    r"^\*?Player (.+?)(?:\s+shows:\s+.+?\s+\[(.+?)\]|"
    r"\s+mucks\s+\(does not show cards\)|"
    r"\s+does not show cards)"
    r"\.\s*Bets:\s*([0-9.]+)\.\s*Collects:\s*([0-9.]+)\.\s*(?:Wins|Loses):\s*[0-9.]+\.$"
)

# Uncalled bet (some WPN hands have this explicitly)
RE_UNCALLED = re.compile(r"^Uncalled bet \(([0-9.]+)\) returned to (.+)$")

# Mucks during hand (before summary)
RE_MUCKS = re.compile(r"^Player (.+?) mucks cards$")

# Game ended
RE_GAME_ENDED = re.compile(r"^Game ended at:")


def detect(sample: str) -> bool:
    """Check if this content is a WPN hand history."""
    s = sample.lstrip("\ufeff")[:500]
    return bool(re.search(r"(?:^|\n)Game started at:", s))


def split_hands(content: str) -> list[str]:
    """Split a file with multiple WPN hand histories into individual hands."""
    content = content.lstrip("\ufeff")
    parts = re.split(r'\n(?=Game started at:)', content)
    return [p.strip() for p in parts if p.strip()]


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the Game ID line."""
    m = re.search(r'Game ID:\s*(\d+)', hand_text)
    return m.group(1) if m else None


def _parse_datetime(s: str) -> datetime:
    """Parse WPN datetime format YYYY/M/D H:M:S (fields may not be zero-padded)."""
    # Normalize: split and reconstruct with zero-padding
    date_part, time_part = s.strip().split()
    y, mo, d = date_part.split("/")
    h, mi, sec = time_part.split(":")
    return datetime(int(y), int(mo), int(d), int(h), int(mi), int(sec))


def _compute_uncalled_returns(
    actions_by_street: dict[str, list[dict]],
    collected: dict[str, Decimal],
) -> dict[str, Decimal]:
    """Compute uncalled bet returns from action sequence.

    WPN sometimes shows explicit uncalled bet lines, but not always.
    When a player bets/raises and everyone else folds, their excess
    over the next highest contribution is returned.
    """
    uncalled: dict[str, Decimal] = {}

    # Find the last street that had actions
    last_street = None
    for street in reversed(_STREETS):
        if actions_by_street[street]:
            last_street = street
            break

    if last_street is None:
        return uncalled

    # Track who folded across all streets
    folded: set[str] = set()
    all_players: set[str] = set()
    for street in _STREETS:
        for a in actions_by_street[street]:
            all_players.add(a["username"])
            if a["action"] == "fold":
                folded.add(a["username"])

    remaining = all_players - folded
    if len(remaining) > 1:
        # Multiple players remained — no uncalled bet
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

    amounts = sorted(street_put_in.values(), reverse=True)
    if len(amounts) < 2:
        max_player = max(street_put_in, key=street_put_in.get)  # type: ignore[arg-type]
        if max_player in remaining:
            uncalled[max_player] = amounts[0]
        return uncalled

    max_amount = amounts[0]
    second_max = amounts[1]

    if max_amount > second_max:
        for p, amt in street_put_in.items():
            if amt == max_amount and p in remaining:
                uncalled[p] = max_amount - second_max
                break

    return uncalled


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single WPN hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    # Strip BOM and null bytes
    hand_text = hand_text.replace("\ufeff", "").replace("\x00", "")
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # ── Parse header: Line 1 = "Game started at: ..." ──
    m = RE_GAME_STARTED.match(lines[0])
    if not m:
        raise ValueError(f"Cannot parse WPN header line: {lines[0]}")
    played_at = _parse_datetime(m.group(1))

    # ── Parse Game ID line ──
    m = RE_GAME_ID.match(lines[1])
    if not m:
        raise ValueError(f"Cannot parse WPN Game ID line: {lines[1]}")
    hand_id = m.group(1)
    sb_amount = Decimal(m.group(2))
    bb_amount = Decimal(m.group(3))
    table_name = m.group(4).strip()
    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"  # We only support Hold'em for now
    game_mode = ""

    # ── Parse button ──
    m = RE_BUTTON.match(lines[2])
    if not m:
        raise ValueError(f"Cannot parse button line: {lines[2]}")
    button_seat = int(m.group(1))

    # ── Parse seats ──
    seats: list[dict] = []
    username_to_seat: dict[str, int] = {}
    line_idx = 3

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

    # Determine table_size from seat numbers or default to 6
    max_seat = max(s["seat"] for s in seats)
    # Common WPN table sizes: 2, 6, 9
    if max_seat <= 2:
        table_size = 2
    elif max_seat <= 6:
        table_size = 6
    else:
        table_size = 9

    _assign_positions(seats, button_seat, table_size)
    username_set = {s["username"] for s in seats}

    # ── Parse action lines ──
    hero_cards: dict[str, tuple[str, str]] = {}
    actions_by_street: dict[str, list[dict]] = {
        "preflop": [], "flop": [], "turn": [], "river": []
    }
    current_street = "preflop"
    board_cards: dict[str, list[str]] = {"flop": [], "turn": [], "river": []}
    uncalled_returns: dict[str, Decimal] = {}
    collected: dict[str, Decimal] = {}
    total_rake = _ZERO
    went_to_showdown_players: set[str] = set()
    in_summary = False

    sb_player: str | None = None
    bb_player: str | None = None

    action_order = 0

    # Per-player per-street investment tracking (for computing raise "to" amounts)
    street_put_in: dict[str, Decimal] = {}

    # Track dealt cards per player (WPN shows one card at a time for hero)
    hero_card_buffer: dict[str, list[str]] = {}

    for line in lines[line_idx:]:
        # Skip card dealing lines
        if RE_RECEIVED_CARD.match(line):
            continue

        # Hero card reveal (if WPN shows hero's cards)
        m_dealt = RE_DEALT.match(line)
        if m_dealt:
            uname = m_dealt.group(1)
            card = m_dealt.group(2).strip()
            if uname not in hero_card_buffer:
                hero_card_buffer[uname] = []
            hero_card_buffer[uname].append(card)
            if len(hero_card_buffer[uname]) == 2:
                hero_cards[uname] = (
                    hero_card_buffer[uname][0],
                    hero_card_buffer[uname][1],
                )
            continue

        # Game ended
        if RE_GAME_ENDED.match(line):
            break

        # Summary section
        if RE_SUMMARY_LINE.match(line):
            in_summary = True
            continue

        if in_summary:
            # Pot/Rake line
            m = RE_POT_RAKE.search(line)
            if m:
                total_rake = Decimal(m.group(2))
                continue

            # Board line
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

            # Player summary lines
            m = RE_SUMMARY_PLAYER.match(line)
            if m:
                uname = m.group(1)
                cards_str = m.group(2)  # may be None if mucks/doesn't show
                collects = Decimal(m.group(4))

                if cards_str:
                    card_list = cards_str.split()
                    if len(card_list) >= 2:
                        hero_cards[uname] = (card_list[0], card_list[1])
                    went_to_showdown_players.add(uname)

                if collects > _ZERO:
                    collected[uname] = collected.get(uname, _ZERO) + collects

                continue
            continue

        # Street markers
        m = RE_FLOP.match(line)
        if m:
            current_street = "flop"
            street_put_in = {}  # reset per-street tracking
            board_cards["flop"] = m.group(1).split()
            continue
        m = RE_TURN.match(line)
        if m:
            current_street = "turn"
            street_put_in = {}
            board_cards["turn"] = [m.group(1)]
            continue
        m = RE_RIVER.match(line)
        if m:
            current_street = "river"
            street_put_in = {}
            board_cards["river"] = [m.group(1)]
            continue

        # Small blind
        m = RE_SMALL_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            sb_player = uname
            street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
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
            street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "bb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Straddle
        m = RE_STRADDLE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "straddle",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Ante
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

        # Uncalled bet (explicit in some hands)
        m = RE_UNCALLED.match(line)
        if m:
            amt = Decimal(m.group(1))
            uname = m.group(2).strip()
            uncalled_returns[uname] = uncalled_returns.get(uname, _ZERO) + amt
            continue

        # Mucks cards (before summary)
        if RE_MUCKS.match(line):
            continue

        # ── Voluntary actions ──

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
                street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "call",
                    "amount": amt,
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_BET.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            if uname in username_set:
                street_put_in[uname] = street_put_in.get(uname, _ZERO) + amt
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "bet",
                    "amount": amt,
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_RAISE.match(line)
        if m:
            uname = m.group(1)
            increment = Decimal(m.group(2))
            if uname in username_set:
                already_in = street_put_in.get(uname, _ZERO)
                raise_to = already_in + increment
                street_put_in[uname] = raise_to
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": raise_to,
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_ALLIN.match(line)
        if m:
            uname = m.group(1)
            increment = Decimal(m.group(2))
            if uname in username_set:
                already_in = street_put_in.get(uname, _ZERO)
                allin_to = already_in + increment
                street_put_in[uname] = allin_to

                # Determine if this is a bet or raise based on whether
                # anyone else has bet on this street
                has_bet_this_street = False
                for a in actions_by_street[current_street]:
                    if a["action"] in ("bet", "raise") and a["username"] != uname:
                        has_bet_this_street = True
                        break
                # Also check if there are blinds/straddles that count as bets (preflop)
                if current_street == "preflop":
                    has_bet_this_street = True  # BB counts as a bet

                action_type = "raise" if has_bet_this_street else "bet"

                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": action_type,
                    "amount": allin_to if action_type == "raise" else increment,
                    "is_all_in": True,
                    "order": action_order,
                })
            continue

    # ── Showdown detection ──
    in_showdown = len(went_to_showdown_players) >= 2

    # ── Compute uncalled returns if not explicitly provided ──
    if not uncalled_returns:
        uncalled_returns = _compute_uncalled_returns(actions_by_street, collected)

    # ── Always compute rake from invested vs collected ──
    # WPN summary "Rake" may not include jackpot drop, so compute from actions
    # to ensure financial balance (same approach as 888poker parser).
    if collected:
        total_invested = _ZERO
        for street in _STREETS:
            st_put_in: dict[str, Decimal] = {}
            for a in actions_by_street[street]:
                uname = a["username"]
                action = a["action"]
                amt = a["amount"]
                if action in _INVEST_ACTIONS:
                    st_put_in[uname] = st_put_in.get(uname, _ZERO) + amt
                    total_invested += amt
                elif action == "raise":
                    already = st_put_in.get(uname, _ZERO)
                    inc = amt - already
                    if inc > 0:
                        total_invested += inc
                    st_put_in[uname] = amt

        total_uncalled = sum(uncalled_returns.values())
        total_collected = sum(collected.values())
        computed_rake = total_invested - total_uncalled - total_collected
        if computed_rake > _ZERO:
            total_rake = computed_rake

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
