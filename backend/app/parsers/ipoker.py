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

from app.parsers.common import ParsedHand, _ZERO, _assign_positions

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
    "15": "show",
    "23": "raise",
}

# Round id to street name
_ROUND_TO_STREET = {
    "preflop": "preflop",
    "flop": "flop",
    "turn": "turn",
    "river": "river",
    "showdown": "showdown",
}

RE_STAKES = re.compile(r"\$([0-9.]+)/\$([0-9.]+)")


def _convert_card(ipoker_card: str) -> str:
    """Convert iPoker card format (HA, DK, C7) to standard (Ah, Kd, 7c)."""
    suit = ipoker_card[0].lower()  # H->h, D->d, C->c, S->s
    rank = ipoker_card[1:]  # A, K, Q, J, T, 9, 8, etc.
    return f"{rank}{suit}"


def _convert_cards(card_str: str) -> list[str]:
    """Convert space-separated iPoker cards to standard format."""
    if not card_str or not card_str.strip():
        return []
    return [_convert_card(c) for c in card_str.strip().split()]


def _parse_amount(amount_str: str) -> Decimal:
    """Parse dollar amount like '$2.25' or '$0' to Decimal."""
    return Decimal(amount_str.replace("$", "").replace(",", ""))


def detect(sample: str) -> bool:
    """Check if this content is an iPoker XML hand history."""
    s = sample[:500]
    return "<?xml" in s and "<session" in s


def split_hands(content: str) -> list[str]:
    """Split iPoker XML into per-game XML strings."""
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
        root = ET.fromstring(hand_text)
        game = root.find("game")
        if game is not None:
            return game.get("gamecode")
    except ET.ParseError:
        pass
    return None


def _compute_uncalled_returns(
    actions_by_street: dict[str, list[dict]],
) -> dict[str, Decimal]:
    """Compute uncalled bet returns from action sequence.

    iPoker doesn't show explicit uncalled bet lines. When a player bets/raises
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
    all_players = set()
    for street in _STREETS:
        for a in actions_by_street[street]:
            all_players.add(a["username"])
            if a["action"] == "fold":
                folded.add(a["username"])

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

    amounts = sorted(street_put_in.values(), reverse=True)
    if len(amounts) < 2:
        max_player = max(street_put_in, key=street_put_in.get)
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
    """Parse a single iPoker XML hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    root = ET.fromstring(hand_text)
    session_general = root.find("general")
    game = root.find("game")
    if game is None:
        raise ValueError("No <game> element found in iPoker XML")

    # ── Session-level info ──
    table_name_raw = session_general.findtext("tablename", "") if session_general is not None else ""
    hero_nick = session_general.findtext("nickname", "") if session_general is not None else ""

    # Parse stakes from table name
    m = RE_STAKES.search(table_name_raw)
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
        chips = _parse_amount(p.get("chips", "$0"))
        is_dealer = p.get("dealer", "0") == "1"
        win_amt = _parse_amount(p.get("win", "$0"))
        bet_amt = _parse_amount(p.get("bet", "$0"))

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

    for round_el in game.findall("round"):
        round_id = round_el.get("id", "")
        street = _ROUND_TO_STREET.get(round_id)
        if street is None:
            continue

        # Community cards
        for cards_el in round_el.findall("cards"):
            if cards_el.get("type") == "community" and cards_el.text:
                converted = _convert_cards(cards_el.text)
                if street in board_cards:
                    board_cards[street] = converted

        # Actions
        for action_el in round_el.findall("action"):
            player_name = action_el.get("player", "")
            action_type = action_el.get("type", "")
            action_sum = _parse_amount(action_el.get("sum", "$0"))
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

            # Extract hero cards from preflop action cards attribute
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

            action_order += 1
            actions_by_street[street].append({
                "username": player_name,
                "action": action_name,
                "amount": action_sum,
                "is_all_in": False,  # iPoker doesn't explicitly mark all-in
                "order": action_order,
            })

    # ── Showdown detection ──
    in_showdown = len(went_to_showdown_players) >= 2

    # ── Compute uncalled returns ──
    uncalled_returns = _compute_uncalled_returns(actions_by_street)

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
