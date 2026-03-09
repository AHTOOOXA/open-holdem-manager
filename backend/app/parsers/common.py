"""Shared parser types and utilities.

Contains ParsedHand dataclass, position logic, and constants used by all site parsers.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime

_ZERO = Decimal("0")


@dataclass
class ParsedHand:
    """Output of parsing a single hand history. Contains all extracted data."""
    hand_id: str
    site_id: int
    played_at: datetime
    game_type: str
    game_mode: str  # "Fast Fold" or ""
    stakes: str
    sb_amount: Decimal
    bb_amount: Decimal
    table_name: str
    table_size: int
    button_seat: int
    seats: list[dict]  # [{seat, username, stack, position}]
    actions_by_street: dict[str, list[dict]]
    board_cards: dict[str, list[str]]
    hero_cards: dict[str, tuple[str, str]]
    uncalled_returns: dict[str, Decimal]
    collected: dict[str, Decimal]
    total_rake: Decimal
    total_jackpot: Decimal
    went_to_showdown_players: set[str]
    in_showdown: bool
    sb_player: str | None
    bb_player: str | None
    raw_text: str
    cash_drop_received: Decimal = _ZERO
    extra_boards: list[dict[str, list[str]]] = field(default_factory=list)
    rit_boards: int = 1       # 1=normal, 2=RIT, 3=RIT3
    is_cashout: bool = False


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


STREETS = ("preflop", "flop", "turn", "river")
INVEST_ACTIONS = frozenset(("sb", "bb", "ante", "straddle", "call", "bet"))


def compute_uncalled_returns(
    actions_by_street: dict[str, list[dict]],
) -> dict[str, Decimal]:
    """Compute uncalled bet returns from action sequence.

    When a player bets/raises and everyone else folds, their excess
    over the next highest contribution is returned.
    """
    uncalled: dict[str, Decimal] = {}

    # Find the last street that had actions
    last_street = None
    for street in reversed(STREETS):
        if actions_by_street[street]:
            last_street = street
            break

    if last_street is None:
        return uncalled

    # Track who folded and all players across all streets
    folded: set[str] = set()
    all_players: set[str] = set()
    for street in STREETS:
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

        if action in INVEST_ACTIONS:
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
