"""
iPoker hand history parser.

Parses iPoker XML format hand histories into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import copy
import re
import xml.etree.ElementTree as ET
from decimal import Decimal
from datetime import datetime

from app.parsers.common import ParsedHand, _ZERO, _assign_positions, compute_uncalled_returns

SITE_ID = 6
SITE_CODE = "IP"
SITE_NAME = "iPoker"

# Streets in order for investment/uncalled computation
_STREETS = ("preflop", "flop", "turn", "river")
_INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))

# Action type mapping
_ACTION_TYPES = {
    "0": "fold",
    "1": "sb",
    "2": "bb",
    "3": "call",
    "4": "check",
    "5": "bet",
    "7": "call",   # type 7 = call (often all-in call)
    "15": "show",
    "23": "raise",
}

# Round no to street name
# no=0: blinds (preflop), no=1: preflop (pocket cards + actions)
# no=2: flop, no=3: turn, no=4: river, no=5+: showdown
_ROUND_NO_TO_STREET = {
    "0": "preflop",
    "1": "preflop",
    "2": "flop",
    "3": "turn",
    "4": "river",
}

# Currency symbols to strip from amounts
_CURRENCY_RE = re.compile(r"[€$£]")

# Stakes from gametype element: "Holdem NL €0.05/€0.10" or "Holdem L $5/$10"
RE_GAMETYPE_STAKES = re.compile(r"[€$£]([0-9.]+)\s*/\s*[€$£]([0-9.]+)")


def _convert_card(ipoker_card: str) -> str:
    """Convert iPoker card format (HA, DK, C7, H10) to standard (Ah, Kd, 7c, Th).

    iPoker uses suit-first format: H=hearts, D=diamonds, C=clubs, S=spades.
    Rank "10" is converted to "T".
    """
    suit = ipoker_card[0].lower()  # H->h, D->d, C->c, S->s
    rank = ipoker_card[1:]  # A, K, Q, J, T, 10, 9, 8, etc.
    if rank == "10":
        rank = "T"
    return f"{rank}{suit}"


def _convert_cards(card_str: str) -> list[str]:
    """Convert space-separated iPoker cards to standard format.

    Filters out unknown 'X' cards.
    """
    if not card_str or not card_str.strip():
        return []
    cards = []
    for c in card_str.strip().split():
        if c == "X":
            continue
        cards.append(_convert_card(c))
    return cards


def _parse_amount(amount_str: str) -> Decimal:
    """Parse currency amount like '$2.25', '€0.10', or '$0' to Decimal."""
    cleaned = _CURRENCY_RE.sub("", amount_str).replace(",", "").strip()
    if not cleaned:
        return _ZERO
    return Decimal(cleaned)


def detect(sample: str) -> bool:
    """Check if this content is an iPoker XML hand history."""
    # Strip BOM if present
    s = sample.lstrip("\ufeff")[:500]
    return ("<session" in s) and ("<general>" in s or "<game " in s)


def split_hands(content: str) -> list[str]:
    """Split iPoker XML into per-game XML strings."""
    # Strip BOM
    content = content.lstrip("\ufeff")
    root = ET.fromstring(content)
    general = root.find("general")
    games = root.findall("game")
    if len(games) <= 1:
        return [content]
    result = []
    for game in games:
        session = ET.Element("session", root.attrib)
        if general is not None:
            session.append(copy.deepcopy(general))
        session.append(copy.deepcopy(game))
        result.append(ET.tostring(session, encoding="unicode"))
    return result


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID (gamecode) from iPoker XML."""
    try:
        text = hand_text.lstrip("\ufeff")
        root = ET.fromstring(text)
        game = root.find("game")
        if game is not None:
            return game.get("gamecode")
    except ET.ParseError:
        pass
    return None


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single iPoker XML hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    # Strip BOM
    hand_text_clean = hand_text.lstrip("\ufeff")
    root = ET.fromstring(hand_text_clean)
    session_general = root.find("general")
    game = root.find("game")
    if game is None:
        raise ValueError("No <game> element found in iPoker XML")

    # ── Session-level info ──
    table_name_raw = session_general.findtext("tablename", "") if session_general is not None else ""
    hero_nick = session_general.findtext("nickname", "") if session_general is not None else ""

    # Parse stakes from gametype element first, fall back to tablename
    gametype_str = session_general.findtext("gametype", "") if session_general is not None else ""
    m = RE_GAMETYPE_STAKES.search(gametype_str)
    if not m:
        # Fall back: try to find stakes in table name
        m = RE_GAMETYPE_STAKES.search(table_name_raw)
    if m:
        sb_amount = Decimal(m.group(1))
        bb_amount = Decimal(m.group(2))
    else:
        sb_amount = _ZERO
        bb_amount = _ZERO

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"

    # ── Game-level info ──
    hand_id = game.get("gamecode", "")
    game_general = game.find("general")
    start_date_str = game_general.findtext("startdate", "") if game_general is not None else ""
    played_at = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S") if start_date_str else datetime.now()

    # ── Players ──
    players_el = game_general.find("players") if game_general is not None else None
    player_elements = players_el.findall("player") if players_el is not None else []

    seats = []
    username_to_seat = {}
    button_seat = 1
    collected = {}
    total_bet_from_xml = _ZERO
    total_win_from_xml = _ZERO

    for p in player_elements:
        seat_num = int(p.get("seat", "0"))
        name = p.get("name", "")
        chips = _parse_amount(p.get("chips", "0"))
        is_dealer = p.get("dealer", "0") == "1"
        win_amt = _parse_amount(p.get("win", "0"))
        bet_amt = _parse_amount(p.get("bet", "0"))

        # Skip sitting-out players (chips=0, bet=0, win=0)
        if chips == _ZERO and bet_amt == _ZERO and win_amt == _ZERO:
            continue

        seats.append({"seat": seat_num, "username": name, "stack": chips})
        username_to_seat[name] = seat_num

        if is_dealer:
            button_seat = seat_num

        if win_amt > _ZERO:
            collected[name] = collected.get(name, _ZERO) + win_amt

        total_bet_from_xml += bet_amt
        total_win_from_xml += win_amt

    table_size = len(seats)
    _assign_positions(seats, button_seat, table_size)

    # ── Parse rounds ──
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    board_cards = {"flop": [], "turn": [], "river": []}
    hero_cards = {}
    went_to_showdown_players = set()
    sb_player = None
    bb_player = None
    action_order = 0
    # Track running investment for all-in detection
    player_stacks = {s["username"]: s["stack"] for s in seats}
    player_running_invested: dict[str, Decimal] = {}
    player_street_invested: dict[str, Decimal] = {}  # per street, reset each street

    for round_el in game.findall("round"):
        round_no = round_el.get("no", "")
        street = _ROUND_NO_TO_STREET.get(round_no)
        if street is None:
            # Round 5+ could be showdown — check for show actions
            for action_el in round_el.findall("action"):
                action_type = action_el.get("type", "")
                if action_type == "15":
                    player_name = action_el.get("player", "")
                    went_to_showdown_players.add(player_name)
                    # Try to get cards from cards attribute
                    cards_attr = action_el.get("cards", "")
                    if cards_attr:
                        converted = _convert_cards(cards_attr)
                        if len(converted) == 2:
                            hero_cards[player_name] = (converted[0], converted[1])
            continue

        # ── Community cards: <cards type="Flop">, <cards type="Turn">, <cards type="River"> ──
        for cards_el in round_el.findall("cards"):
            cards_type = cards_el.get("type", "")
            cards_text = cards_el.text or ""

            if cards_type == "Flop" and cards_text.strip():
                board_cards["flop"] = _convert_cards(cards_text)
            elif cards_type == "Turn" and cards_text.strip():
                board_cards["turn"] = _convert_cards(cards_text)
            elif cards_type == "River" and cards_text.strip():
                board_cards["river"] = _convert_cards(cards_text)
            elif cards_type == "community" and cards_text.strip():
                # Legacy format compatibility
                converted = _convert_cards(cards_text)
                if street in board_cards:
                    board_cards[street] = converted
            elif cards_type == "Pocket":
                # Pocket cards: <cards type="Pocket" player="name">D9 CK</cards>
                pocket_player = cards_el.get("player", "")
                if pocket_player and cards_text.strip():
                    converted = _convert_cards(cards_text)
                    if len(converted) == 2:
                        hero_cards[pocket_player] = (converted[0], converted[1])

        # Reset per-street tracking (only on new street, not for round 0->1 which are both preflop)
        if street != "preflop" or round_no == "0":
            player_street_invested = {}

        # Actions
        for action_el in round_el.findall("action"):
            player_name = action_el.get("player", "")
            action_type = action_el.get("type", "")
            action_sum = _parse_amount(action_el.get("sum", "0"))
            cards_attr = action_el.get("cards", "")

            action_name = _ACTION_TYPES.get(action_type)
            if action_name is None:
                continue

            # Showdown: type 15 = show cards
            if action_name == "show":
                went_to_showdown_players.add(player_name)
                if cards_attr:
                    converted = _convert_cards(cards_attr)
                    if len(converted) == 2:
                        hero_cards[player_name] = (converted[0], converted[1])
                continue

            # Extract hero cards from preflop action cards attribute (legacy format)
            if street == "preflop" and cards_attr and player_name not in hero_cards:
                converted = _convert_cards(cards_attr)
                if len(converted) == 2:
                    hero_cards[player_name] = (converted[0], converted[1])

            # Track SB/BB players
            if action_name == "sb":
                sb_player = player_name
            elif action_name == "bb":
                bb_player = player_name

            if street == "showdown":
                continue

            # Track running investment for all-in detection
            prev_running = player_running_invested.get(player_name, _ZERO)
            prev_street = player_street_invested.get(player_name, _ZERO)
            if action_name in ("sb", "bb", "ante", "call", "bet"):
                player_running_invested[player_name] = prev_running + action_sum
                player_street_invested[player_name] = prev_street + action_sum
            elif action_name == "raise":
                # action_sum is "to" amount for this street
                increment = action_sum - prev_street
                if increment > _ZERO:
                    player_running_invested[player_name] = prev_running + increment
                player_street_invested[player_name] = action_sum

            stack = player_stacks.get(player_name, _ZERO)
            invested = player_running_invested.get(player_name, _ZERO)
            is_all_in = invested > _ZERO and invested >= stack

            action_order += 1
            actions_by_street[street].append({
                "username": player_name,
                "action": action_name,
                "amount": action_sum,
                "is_all_in": is_all_in,
                "order": action_order,
            })

    # ── Showdown detection ──
    in_showdown = len(went_to_showdown_players) >= 2

    # ── Compute uncalled returns ──
    uncalled_returns = compute_uncalled_returns(actions_by_street)

    # ── Compute rake ──
    # Use action-based investment calculation for accuracy
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

    game_type = "NLH"
    game_mode = ""

    return ParsedHand(
        hand_id=hand_id,
        site_id=SITE_ID,
        played_at=played_at,
        game_type=game_type,
        game_mode=game_mode,
        stakes=stakes,
        sb_amount=sb_amount,
        bb_amount=bb_amount,
        table_name=table_name_raw,
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
