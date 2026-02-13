"""Board texture classification for flop, turn, and river.

Classifies boards into categories useful for population analysis:
- Flop rank texture: high card composition
- Flop suit texture: monocolor/2tone/rainbow
- Flop paired: whether the flop has a pair
- Turn/River texture: relative to previous streets
"""

_RANK_ORDER = "23456789TJQKA"
_RANK_VALUE = {r: i for i, r in enumerate(_RANK_ORDER)}


def _rank(card: str) -> int:
    """Get numeric rank value from a card string like 'Ah', 'Td'."""
    return _RANK_VALUE.get(card[0], 0)


def _suit(card: str) -> str:
    """Get suit character from a card string."""
    return card[1] if len(card) >= 2 else ''


def _is_broadway(card: str) -> bool:
    return card[0] in "TJQKA"


def classify_flop(cards: list[str]) -> tuple[str, str, bool]:
    """Classify flop texture.

    Returns (rank_texture, suit_texture, is_paired).

    Rank textures:
    - ABB: Two broadway + one broadway (all broadway)
    - ABx: Two broadway + one non-broadway
    - Axx: One broadway + two non-broadway
    - BBB: Three mid-high connected (8-Q range, connected)
    - BBx: Two mid-high + one low
    - Bxx: One mid-high + two low
    - T9Conn: All three connected (gap <= 2 between consecutive), with top card < T
    - T9Disc: Mid-range disconnected
    - 82Conn: Low connected
    - 82Disc: Low disconnected

    Suit textures: monocolor / 2tone / rainbow
    """
    if len(cards) < 3:
        return ("UNK", "UNK", False)

    ranks = sorted([_rank(c) for c in cards], reverse=True)
    suits = [_suit(c) for c in cards]
    bw_count = sum(1 for c in cards if _is_broadway(c))

    # Paired
    is_paired = ranks[0] == ranks[1] or ranks[1] == ranks[2]

    # Suit texture
    unique_suits = len(set(suits))
    if unique_suits == 1:
        suit_tex = "monocolor"
    elif unique_suits == 2:
        suit_tex = "2tone"
    else:
        suit_tex = "rainbow"

    # Rank texture
    gap01 = ranks[0] - ranks[1]
    gap12 = ranks[1] - ranks[2]
    is_conn = gap01 <= 2 and gap12 <= 2

    if bw_count >= 3:
        rank_tex = "ABB"
    elif bw_count == 2:
        rank_tex = "ABx"
    elif bw_count == 1:
        rank_tex = "Axx"
    elif ranks[0] >= 7:  # mid-high range
        if is_conn:
            rank_tex = "BBB"
        elif ranks[0] >= 7 and ranks[1] >= 7:
            rank_tex = "BBx"
        else:
            rank_tex = "Bxx"
    else:  # low board
        if is_conn:
            rank_tex = "82Conn"
        else:
            rank_tex = "82Disc"

    return (rank_tex, suit_tex, is_paired)


def classify_turn(flop: list[str], turn: str) -> str:
    """Classify turn card relative to flop.

    Returns one of:
    - completed_draw: Turn completes a flush draw (3 of same suit) or obvious straight
    - draw_adding: Turn adds a flush draw (2tone becomes 3tone)
    - overcard: Turn card is higher than all flop cards
    - paired_board: Turn pairs one of the flop cards
    - brick: None of the above
    """
    if not flop or not turn:
        return "brick"

    flop_ranks = [_rank(c) for c in flop]
    flop_suits = [_suit(c) for c in flop]
    turn_rank = _rank(turn)
    turn_suit = _suit(turn)

    # Paired board?
    if turn_rank in flop_ranks:
        return "paired_board"

    # Overcard?
    if turn_rank > max(flop_ranks):
        return "overcard"

    # Flush draw completion: 3+ of same suit with turn
    all_suits = flop_suits + [turn_suit]
    from collections import Counter
    suit_counts = Counter(all_suits)
    if suit_counts.most_common(1)[0][1] >= 3:
        return "completed_draw"

    # Draw adding: creates new 2-flush
    flop_suit_counts = Counter(flop_suits)
    if flop_suit_counts.most_common(1)[0][1] == 1 and turn_suit in flop_suits:
        return "draw_adding"

    return "brick"


def classify_river(board: list[str], river: str) -> str:
    """Classify river card relative to the full board.

    Returns one of:
    - completed_draw: completes flush (4 of same suit on board) or pairs the board
    - overcard: river is higher than all previous cards
    - paired_board: river pairs an existing board card
    - brick: none of the above
    """
    if not board or not river:
        return "brick"

    board_ranks = [_rank(c) for c in board]
    board_suits = [_suit(c) for c in board]
    river_rank = _rank(river)
    river_suit = _suit(river)

    if river_rank in board_ranks:
        return "paired_board"

    if river_rank > max(board_ranks):
        return "overcard"

    all_suits = board_suits + [river_suit]
    from collections import Counter
    suit_counts = Counter(all_suits)
    if suit_counts.most_common(1)[0][1] >= 4:
        return "completed_draw"

    return "brick"
