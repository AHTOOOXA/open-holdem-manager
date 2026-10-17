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
    # Everything the site took from the pot (rake + jackpot + other fees).
    # None means rake + jackpot is the whole of it. GGPoker sets it because
    # its summary also lists Bingo, Fortune and Tax.
    total_fees: Decimal | None = None

    @property
    def fees(self) -> Decimal:
        if self.total_fees is not None:
            return self.total_fees
        return self.total_rake + self.total_jackpot


# Position labels for 6-max (clockwise from BTN)
POSITIONS_6MAX = ["BTN", "SB", "BB", "EP", "MP", "CO"]


def position_labels(num_players: int) -> list[str]:
    """Position labels clockwise from BTN, always from the six buckets
    BTN/SB/BB/EP/MP/CO that every stat and filter is grouped by.

    Matches Hand2Note's column groups: counting back from the button the
    seats are CO, then MP (always exactly one seat, the HJ), then EP for
    every earlier seat (H2N's EP + UTG1..UTG4). So 5-max is MP CO, 6-max
    EP MP CO, 9-max EP EP EP EP MP CO. Heads-up the button posts the small
    blind and is "SB" (H2N's SB-HU), the other player "BB" (BB-HU); there is
    no BTN. Labels repeat at 7+ players; use the seat's "action_order" when
    exact order matters.
    """
    if num_players == 2:
        return ["SB", "BB"]
    if num_players <= 3:
        return ["BTN", "SB", "BB"][:num_players]
    middle = num_players - 4  # seats between BB and CO
    mp = min(middle, 1)
    return ["BTN", "SB", "BB"] + ["EP"] * (middle - mp) + ["MP"] * mp + ["CO"]


POSITIONS_BY_COUNT = {n: position_labels(n) for n in range(2, 11)}


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
    pos_labels = POSITIONS_BY_COUNT.get(num_players) or position_labels(num_players)

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

    # Postflop action order: SB first ... BTN last (heads-up: BB first, the
    # button, labelled SB, last).
    # Needed because position labels repeat at 7+ players.
    seat_to_order = {sn: (i - 1) % num_players for i, sn in enumerate(ordered)}

    for s in seats:
        s["position"] = seat_to_pos[s["seat"]]
        s["action_order"] = seat_to_order[s["seat"]]
