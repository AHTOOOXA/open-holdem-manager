"""Hand value categories per street (the stat popup's "Range" tab) and board textures.

Pure functions over (hole cards, board cards). Behaviour spec:
docs/specs/H2N-COMPATIBLE-STATS.md sections 6.4 (hand values) and 6.5 (boards).

Pipeline for one hand on one street:

1. ``_evaluate`` gives the best hand of hole + board and of the board alone,
   as a fixed-width tuple ``(type, r1, r2, r3, r4, r5)``. Missing kickers on a
   3- or 4-card board are padded with 2 (deuces), so a board value compares
   like a 5-card value.
2. ``hand_facts`` reads that as a :class:`HandFacts` record: is the hand air
   (and with how many overcards), which pair it holds against the board and
   with what kicker, which better hand it makes, and which draws it has.
3. ``category`` walks the street's category list in display order and returns
   the index of the first rule that matches, or ``OTHER`` (-1). The rules are
   written over the facts.

Cards are strings like ``"Ah"`` / ``"Td"`` (``"10d"`` is accepted). Ranks are
ints 2..14, suits one of ``h d c s``. Ties between suits are broken in the
order hearts, diamonds, clubs, spades (the reference tracker's order).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

if TYPE_CHECKING:
    from app.parsers.common import ParsedHand

__all__ = [
    "HandFacts",
    "Category",
    "BoardCategory",
    "OTHER",
    "OTHER_LABEL",
    "OTHER_COLOR",
    "STREET_CATEGORIES",
    "BOARD_CATEGORIES",
    "parse_card",
    "hand_facts",
    "category",
    "categories",
    "board_categories",
    "is_weak",
    "weak_pct",
    "category_info",
    "player_boards",
    "classify_for_player",
    "classify_boards_for_player",
    "apply_hand_values",
]

Card = tuple[int, str]  # (rank 2..14, suit)

_RANK_CHARS = {c: i + 2 for i, c in enumerate("23456789TJQKA")}
_SUIT_ORDER = "hdcs"  # suit order used whenever a suit tie must be broken
_STREETS = ("flop", "turn", "river")
_BOARD_LEN = {"flop": 3, "turn": 4, "river": 5}

# Hand types (higher beats lower)
HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


def parse_card(card: str) -> Card:
    """'Ah' -> (14, 'h'). Accepts '10h' and either letter case."""
    s = card.strip()
    if len(s) == 3 and s[:2] == "10":
        s = "T" + s[2]
    if len(s) != 2:
        raise ValueError(f"bad card: {card!r}")
    rank = _RANK_CHARS.get(s[0].upper())
    suit = s[1].lower()
    if rank is None or suit not in _SUIT_ORDER:
        raise ValueError(f"bad card: {card!r}")
    return rank, suit


def _cards(cards: Iterable[str | Card]) -> list[Card]:
    return [c if isinstance(c, tuple) else parse_card(c) for c in cards]


# ---------------------------------------------------------------------------
# Hand evaluation
# ---------------------------------------------------------------------------

def _mask(ranks: Iterable[int]) -> int:
    m = 0
    for r in ranks:
        m |= 1 << r
    return m


# (top rank, rank bitmask) of every straight, best first; the wheel uses the ace
_STRAIGHTS = tuple(
    (top, _mask(range(top - 4, top + 1)) if top > 5 else _mask((14, 2, 3, 4, 5)))
    for top in range(14, 4, -1)
)


@lru_cache(maxsize=None)
def _straight_top_m(m: int) -> int | None:
    for top, sm in _STRAIGHTS:
        if m & sm == sm:
            return top
    return None


def _straight_top(ranks: Iterable[int]) -> int | None:
    """Top rank of the best straight in a set of ranks (wheel -> 5), else None."""
    return _straight_top_m(_mask(ranks))


def _pad(*ranks: int) -> tuple[int, ...]:
    return ranks + (2,) * (5 - len(ranks))


def _evaluate(cards: Sequence[Card]) -> tuple[int, ...]:
    """Best poker hand of 3..7 cards as (type, r1..r5); missing ranks = 2."""
    by_rank: dict[int, int] = {}
    by_suit: dict[str, list[int]] = {}
    for r, s in cards:
        by_rank[r] = by_rank.get(r, 0) + 1
        by_suit.setdefault(s, []).append(r)

    flush_ranks = next((sorted(rs, reverse=True) for rs in by_suit.values() if len(rs) >= 5), None)
    if flush_ranks:
        top = _straight_top(set(flush_ranks))
        if top:
            return (STRAIGHT_FLUSH, *_pad(top))

    quads = [r for r, n in by_rank.items() if n == 4]
    trips = sorted((r for r, n in by_rank.items() if n == 3), reverse=True)
    pairs = sorted((r for r, n in by_rank.items() if n == 2), reverse=True)
    singles = sorted((r for r, n in by_rank.items() if n == 1), reverse=True)

    if quads:
        q = quads[0]
        rest = [r for r in by_rank if r != q]
        return (QUADS, *_pad(q, *([max(rest)] if rest else [])))
    if trips and (len(trips) > 1 or pairs):
        t = trips[0]
        p = max(trips[1:] + pairs)
        return (FULL_HOUSE, *_pad(t, p))
    if flush_ranks:
        return (FLUSH, *flush_ranks[:5])
    top = _straight_top(set(by_rank))
    if top:
        return (STRAIGHT, *_pad(top))
    if trips:
        return (TRIPS, *_pad(trips[0], *singles[:2]))
    if len(pairs) >= 2:
        rest = sorted(pairs[2:] + singles, reverse=True)
        return (TWO_PAIR, *_pad(pairs[0], pairs[1], *rest[:1]))
    if pairs:
        return (PAIR, *_pad(pairs[0], *singles[:3]))
    return (HIGH, *_pad(*singles[:5]))


def _kickers(hv: tuple[int, ...]) -> tuple[int, ...]:
    """The value's kicker ranks (5 slots, unused = 2), by hand type."""
    t = hv[0]
    if t in (HIGH, FLUSH):
        return hv[1:6]
    if t == PAIR:
        return _pad(*hv[2:5])
    if t == TWO_PAIR:
        return _pad(hv[3])
    if t == TRIPS:
        return _pad(*hv[2:4])
    if t == QUADS:
        return _pad(hv[2])
    return _pad()


_DEUCE_OF_SPADES: Card = (2, "s")


def _hole_in_hand(hv: tuple[int, ...], hole: list[Card], board: list[Card]) -> set[Card]:
    """Hole cards that are part of the best five.

    Group ranks (pair, trips, quads) take every card of the rank in suit
    order until the five slots are full. A kicker or straight rank takes the
    board card when the board has that rank. H2N always counts the deuce of
    spades as part of the hand (observed black-box), so the 2s is kept when
    hero holds it.
    """
    allc = hole + board
    board_ranks = {r for r, _ in board}
    used: set[Card] = set()

    def group(rank: int, slots: int) -> None:
        cs = sorted((c for c in allc if c[0] == rank), key=lambda c: _SUIT_ORDER.index(c[1]))
        used.update(cs[:slots])

    def single(rank: int) -> None:
        if rank == 1:
            rank = 14
        if rank in board_ranks:
            return  # the board card plays
        cs = [c for c in hole if c[0] == rank]
        if cs:  # H2N keeps the last match in suit order
            used.add(max(cs, key=lambda c: _SUIT_ORDER.index(c[1])))

    t = hv[0]
    if t == HIGH:
        for r in hv[1:6]:
            single(r)
    elif t == PAIR:
        group(hv[1], 2)
        for r in hv[2:5]:
            single(r)
    elif t == TWO_PAIR:
        group(hv[1], 2)
        group(hv[2], 2)
        single(hv[3])
    elif t == TRIPS:
        group(hv[1], 3)
        single(hv[2])
        single(hv[3])
    elif t == STRAIGHT:
        for r in range(hv[1], hv[1] - 5, -1):
            single(r)
    elif t == FULL_HOUSE:
        group(hv[1], 3)
        group(hv[2], 2)
    elif t == QUADS:
        group(hv[1], 4)
        single(hv[2])
    else:  # flush / straight flush: cards of the flush suit
        suit = next(s for s in _SUIT_ORDER if sum(1 for c in allc if c[1] == s) >= 5)
        if t == FLUSH:
            ranks = set(hv[1:6])
        else:
            ranks = {14 if r == 1 else r for r in range(hv[1], hv[1] - 5, -1)}
        used.update(c for c in allc if c[1] == suit and c[0] in ranks)

    in_hand = {c for c in hole if c in used}
    if _DEUCE_OF_SPADES in hole:
        in_hand.add(_DEUCE_OF_SPADES)
    return in_hand


# ---------------------------------------------------------------------------
# Hand facts
# ---------------------------------------------------------------------------

# Where hero's one pair ranks against the board (HandFacts.pair)
PAIR_OVER = "over"        # pocket pair above every board card
PAIR_TOP = "top"
PAIR_MIDDLE = "middle"
PAIR_LOW = "low"

# Hands better than one pair that hero makes with a hole card (HandFacts.made)
MADE_TWO_PAIR = "two_pair"
MADE_TRIPS = "trips"      # one hole card matching a paired board
MADE_SET = "set"          # pocket pair matching an unpaired board card
MADE_STRAIGHT = "straight"
MADE_FLUSH = "flush"
MADE_FULL_HOUSE = "full_house"
MADE_QUADS = "quads"
MADE_STRAIGHT_FLUSH = "straight_flush"

_MADE_BY_TYPE = {QUADS: MADE_QUADS, FULL_HOUSE: MADE_FULL_HOUSE,
                 STRAIGHT_FLUSH: MADE_STRAIGHT_FLUSH}


@dataclass(frozen=True, slots=True)
class HandFacts:
    """What one hand has on one street, as the Range categories read it.

    No hole card helps (air):
      ``air``         neither hole card makes a pair or better, or the board
                      plays. A hand can be air and still hold a pair the
                      categories ignore (an ace kicker on a double-paired
                      board, for example).
      ``high_card``   rank of the hand's best unpaired card when it plays as
                      a high-card hand, else None.
      ``overcards``   0-2 cards above the board's best card (air hands only).

    One pair:
      ``pair``        PAIR_* or None.
      ``pocket_pair`` the pair is a pocket pair.
      ``kicker``      for a pair made with one hole card: the kicker's place
                      among the ranks not on the board, counted from the ace
                      (1 = best possible kicker); 0 when no kicker counts.

    Better than one pair:
      ``made``        MADE_* or None.
      ``board_is_nuts`` the board alone is the best possible hand (nothing
                      else is filled in then).

    Draws (flop and turn only, and only below the made hand they'd give):
      ``flush_draw``  0 = none, 1 = nut, 2 = second nut, 3 = third nut,
                      4 = weaker; the best of hero's flush cards counts.
      ``backdoor_flush`` a runner-runner flush draw.
      ``straight_draw`` number of ranks that complete a straight for hero
                      (0 none, 1 gutshot, 2+ open-ended or double gutshot).
      ``combo_draw``  a flush or straight draw combined with a pair, or a
                      flush draw combined with a straight draw.
    """

    air: bool = False
    high_card: int | None = None
    overcards: int = 0
    pair: str | None = None
    pocket_pair: bool = False
    kicker: int = 0
    made: str | None = None
    board_is_nuts: bool = False
    flush_draw: int = 0
    backdoor_flush: bool = False
    straight_draw: int = 0
    combo_draw: bool = False

    # -- derived facts the categories are written in --------------------------

    @property
    def ace_high(self) -> bool:
        return self.high_card == 14

    @property
    def two_overcards(self) -> bool:
        return self.overcards == 2

    @property
    def has_flush_draw(self) -> bool:
        return self.flush_draw > 0

    @property
    def gutshot(self) -> bool:
        return self.straight_draw == 1

    @property
    def open_straight_draw(self) -> bool:
        return self.straight_draw >= 2

    @property
    def strong_draw(self) -> bool:
        """A flush draw or a straight draw with two or more outs."""
        return self.flush_draw > 0 or self.straight_draw >= 2

    @property
    def any_draw(self) -> bool:
        """A flush draw or any straight draw (gutshots included)."""
        return self.flush_draw > 0 or self.straight_draw > 0

    @property
    def two_pair_plus(self) -> bool:
        return self.made is not None

    @property
    def top_pair(self) -> bool:
        return self.pair == PAIR_TOP

    @property
    def low_pair(self) -> bool:
        """Low pair, pocket or not."""
        return self.pair == PAIR_LOW

    @property
    def weak_made(self) -> bool:
        """Air or a low pair: the hands a draw is the main asset of."""
        return self.air or self.pair == PAIR_LOW


_NO_FACTS = HandFacts()


@dataclass(frozen=True)
class _HighCard:
    plays: bool = False   # the hand plays as high card (for the air facts)
    rank: int = 2
    overcards: int = 0


def _high_card(hv, board_hv, hole: list[Card], board_plays: bool) -> _HighCard:
    """Does the hand play as high card for the air facts, and with how many
    overcards. A hand whose hole cards don't play has none."""
    t, bt = hv[0], board_hv[0]
    if board_plays or t in (STRAIGHT, FLUSH, STRAIGHT_FLUSH, FULL_HOUSE):
        return _HighCard()
    if t != HIGH and t != bt:
        return _HighCard()
    k, bk = _kickers(hv), _kickers(board_hv)

    def count() -> int:
        if k[1] > bk[0]:
            return 2
        if k[0] > bk[0]:
            return 1
        return 0

    if t == HIGH:
        return _HighCard(True, max(r for r, _ in hole), count())
    if t == TWO_PAIR and hv[1:3] != board_hv[1:3]:
        return _HighCard()
    if bt == QUADS:
        if bk[0] == 14:
            return _HighCard()
        return _HighCard(True, k[0], 0)
    rank = next((a for a, b in zip(k, bk) if a > b), 2)
    return _HighCard(True, rank, count())


def _paired_rank(hv, board_hv) -> int | None:
    """The rank hero pairs (P in the spec), or None."""
    t, bt = hv[0], board_hv[0]
    if bt == HIGH:
        return hv[1] if t == PAIR else None
    if bt == PAIR:
        if t != TWO_PAIR:
            return None
        if hv[1] == board_hv[1]:
            return hv[2]
        if hv[2] == board_hv[1]:
            return hv[1]
        return None
    if bt == TWO_PAIR:
        if t == FULL_HOUSE:
            return None
        if hv[1] == board_hv[1]:
            # The board's second pair is compared with the hand's unused
            # (deuce-padded) second kicker: deuces up means no pair.
            return None if board_hv[2] == 2 else hv[2]
        return hv[1]
    if bt == TRIPS:
        return hv[2] if t == FULL_HOUSE and hv[1] == board_hv[1] else None
    if bt == FULL_HOUSE:
        if t == FULL_HOUSE and hv[1] == board_hv[1] and hv[2] != board_hv[2]:
            return hv[2]
        return None
    return None


def _missing_desc(present: set[int]) -> list[int]:
    return [r for r in range(14, 1, -1) if r not in present]


@dataclass(frozen=True)
class _Draws:
    flush: int = 0                    # 0 / nut place of the flush draw (1..4)
    two_hole_backdoor: bool = False   # suited hole cards + one board card
    top_backdoor: bool = False        # holds the best missing card of a two-card suit
    straight_ranks: int = 0           # ranks that complete a straight


@lru_cache(maxsize=None)
def _straight_outs_m(m: int) -> frozenset[int]:
    if _straight_top_m(m):
        return frozenset()
    return frozenset(
        r for r in range(2, 15) if not m >> r & 1 and _straight_top_m(m | 1 << r)
    )


def _straight_outs(ranks: set[int]) -> frozenset[int]:
    """Ranks that complete a straight; empty if the ranks already hold one."""
    return _straight_outs_m(_mask(ranks))


def _flush_draw_place(board_suit_ranks: set[int], hole_ranks: set[int]) -> int:
    """1 when hero holds the best missing card of the suit, 2 the second, 3
    the third, else 4. Any hole card's rank counts, whatever its suit."""
    for place, rank in enumerate(_missing_desc(board_suit_ranks)[:3], start=1):
        if rank in hole_ranks:
            return place
    return 4


def _compute_draws(hole: list[Card], board: list[Card]) -> _Draws:
    hole_ranks = {r for r, _ in hole}
    board_ranks = {r for r, _ in board}
    suit_ranks = {s: {r for r, x in board if x == s} for s in _SUIT_ORDER}

    flush = 0
    two_hole_bd = top_bd = False
    if hole[0][1] == hole[1][1]:
        on_board = suit_ranks[hole[0][1]]
        if len(on_board) == 2:
            flush = _flush_draw_place(on_board, hole_ranks)
        elif len(on_board) == 1:
            two_hole_bd, top_bd = True, 14 in hole_ranks
    else:
        for s in _SUIT_ORDER:
            if not any(x == s for _, x in hole):
                continue
            on_board = suit_ranks[s]
            if len(on_board) == 3:
                flush = _flush_draw_place(on_board, hole_ranks)
            elif len(on_board) == 2 and _missing_desc(on_board)[0] in hole_ranks:
                top_bd = True

    n_outs = 0
    shared = board_ranks & hole_ranks
    pocket_pair = len(hole_ranks) == 1
    if len(shared) < 2 and not (pocket_pair and len(shared) == 1):
        all_ranks = board_ranks | hole_ranks
        outs = _straight_outs(all_ranks)
        if outs:
            top_out = max(outs)
            # Only a draw when hero's straight beats the one the board would make
            if _straight_top(all_ranks | {top_out}) != _straight_top(board_ranks | {top_out}):
                n_outs = len(outs)
    return _Draws(flush, two_hole_bd, top_bd, n_outs)


def hand_facts(hole: Sequence[str | Card], board: Sequence[str | Card]) -> HandFacts:
    """Facts about `hole` on a 3-, 4- or 5-card `board`."""
    h, b = _cards(hole), _cards(board)
    if len(h) != 2 or not 3 <= len(b) <= 5:
        raise ValueError("need 2 hole cards and a 3-5 card board")
    return _facts(h, b)


def _facts(h: list[Card], b: list[Card]) -> HandFacts:
    hv = _evaluate(h + b)
    board_hv = _evaluate(b)
    board_plays = hv == board_hv

    if board_plays and (
        (board_hv[0] == STRAIGHT_FLUSH and board_hv[1] == 14)
        or (board_hv[0] == QUADS and (board_hv[2] == 14 or board_hv[1:3] == (14, 13)))
    ):
        return HandFacts(board_is_nuts=True)

    t = hv[0]
    in_hand = _hole_in_hand(hv, h, b)
    n_in = len(in_hand)
    hc = _high_card(hv, board_hv, h, board_plays)
    air = hc.plays or n_in == 0 or board_plays

    # One pair
    pair: str | None = None
    pocket = h[0][0] == h[1][0]
    kicker = 0
    p = None
    if t not in (HIGH, TRIPS, STRAIGHT, FLUSH, QUADS, STRAIGHT_FLUSH) and n_in and not board_plays:
        p = _paired_rank(hv, board_hv)
    if p is not None:
        distinct = sorted({r for r, _ in b}, reverse=True)
        t1 = distinct[0]
        t2 = distinct[1] if len(distinct) > 1 else 2
        if pocket:
            if p > t1:
                pair = PAIR_OVER
            elif p <= t2 or p < 6:
                pair = PAIR_LOW
            else:
                pair = PAIR_MIDDLE
        else:
            if p == t1:
                pair = PAIR_TOP
            elif p == t2 and p >= 6:
                pair = PAIR_MIDDLE
            else:
                pair = PAIR_LOW
            # Kicker: hero's best in-hand rank other than P (a P that comes
            # from the board counts as a kicker too), placed among the
            # ranks that are not on the board.
            others = {r for r, _ in in_hand} ^ {p}
            if others:
                best = max(others)
                board_ranks = {r for r, _ in b}
                free = [r for r in range(14, 1, -1) if r not in board_ranks]
                kicker = free.index(best) + 1 if best in free else 0

    # Better than one pair
    made: str | None = None
    if t == TWO_PAIR and not air and p is None:
        made = MADE_TWO_PAIR
    elif t == TRIPS:
        if len({r for r, _ in b}) == len(b):
            made = MADE_SET
        elif not air and p is None:
            made = MADE_TRIPS

    draws = _compute_draws(h, b) if len(b) < 5 else _Draws()
    open_sd, gutshot = draws.straight_ranks >= 2, draws.straight_ranks == 1
    combo = False
    if t == STRAIGHT and n_in:
        made = MADE_STRAIGHT
    elif t == FLUSH and n_in:
        made = MADE_FLUSH
    elif n_in and not air and p is None:
        made = _MADE_BY_TYPE.get(t, made)
    elif p is not None:
        combo = bool(draws.flush) or open_sd
    else:
        combo = bool(draws.flush) and (gutshot or open_sd)

    # Draws only count below the hand they would make
    flush_draw = draws.flush if t < FLUSH else 0
    backdoor = (
        t < FLUSH and not draws.flush
        and ((len(b) == 3 and draws.two_hole_backdoor) or draws.top_backdoor)
    )
    straight_draw = draws.straight_ranks if t < STRAIGHT else 0

    return HandFacts(
        air=air,
        high_card=hc.rank if hc.plays else None,
        overcards=hc.overcards,
        pair=pair,
        pocket_pair=pocket and pair is not None,
        kicker=kicker,
        made=made,
        flush_draw=flush_draw,
        backdoor_flush=backdoor,
        straight_draw=straight_draw,
        combo_draw=combo,
    )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

def _range(*combos: str) -> frozenset[frozenset[int]]:
    """Rank combos like 'KQ' (any suits) as a set of rank sets."""
    return frozenset(frozenset(_RANK_CHARS[c] for c in combo) for combo in combos)


def _in_range(hole: Sequence[Card], combos: frozenset[frozenset[int]]) -> bool:
    return frozenset((hole[0][0], hole[1][0])) in combos


_KQJ = _range("KQ", "KJ", "QJ")
_AKJ = _range("AK", "AQ", "AJ")
_BROADWAYS = _range("AK", "AQ", "AJ", "AT", "KQ", "KJ", "QJ", "KT", "QT", "JT")

# Rule signature: (facts on the street, facts on the turn (river rules only), hole) -> bool
Rule = Callable[[HandFacts, HandFacts, Sequence[Card]], bool]


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    color: str
    weak: bool
    description: str
    rule: Rule


def _trash(f: HandFacts, _t, hole):
    return (
        f.air
        and not (f.two_overcards and _in_range(hole, _KQJ))
        and not (f.any_draw or f.ace_high)
    )


def _kqj(f: HandFacts, _t, hole):
    return f.two_overcards and not f.any_draw and _in_range(hole, _KQJ)


def _ace_high(blocking_draw: Callable[[HandFacts], bool]) -> Rule:
    def rule(f: HandFacts, _t, hole):
        return f.ace_high and not (
            blocking_draw(f) or (f.two_overcards and _in_range(hole, _AKJ))
        )
    return rule


def _overcards_akj(f: HandFacts, _t, hole):
    return f.ace_high and _in_range(hole, _AKJ) and f.two_overcards and not f.any_draw


def _gutshot(f: HandFacts, _t, _h):
    return f.gutshot and f.air and not (f.two_overcards or f.strong_draw)


def _draw(f: HandFacts, _t, _h):
    return (f.weak_made and f.strong_draw) or (f.two_overcards and f.gutshot)


def _draw_pair_turn(f: HandFacts, _t, _h):
    weak_pair = f.pair in (PAIR_MIDDLE, PAIR_LOW)
    if f.pocket_pair:
        return weak_pair and f.open_straight_draw
    return weak_pair and f.any_draw


def _low_pockets(f: HandFacts, _t, _h):
    return f.low_pair and f.pocket_pair and not f.strong_draw


def _low_pair_flop(f: HandFacts, _t, _h):
    return f.low_pair and not f.pocket_pair and not f.strong_draw


def _low_pair_turn(f: HandFacts, _t, _h):
    return f.low_pair and not f.strong_draw


def _middle_pair(f: HandFacts, _t, _h):
    return f.pair == PAIR_MIDDLE


def _tpwk_flop(f: HandFacts, _t, _h):
    return f.top_pair and f.kicker >= 3


def _tpgk(f: HandFacts, _t, _h):
    return f.top_pair and f.kicker in (1, 2)


def _overpair(f: HandFacts, _t, _h):
    return f.pair == PAIR_OVER


def _set(f: HandFacts, _t, _h):
    return f.made == MADE_SET


def _tpwk_turn(f: HandFacts, _t, _h):
    return f.top_pair and f.kicker not in (1, 2)


def _two_pairs_plus(f: HandFacts, _t, _h):
    return f.two_pair_plus and f.made != MADE_SET


# River rules see the river facts (f) and the same hand's turn facts (t).
def _missed_trash(f: HandFacts, t: HandFacts, _h):
    return f.air and (
        not (t.any_draw or t.ace_high) or t.two_pair_plus or t.pair is not None
    )


def _missed_overcards(f: HandFacts, t: HandFacts, hole):
    return t.air and not t.strong_draw and f.air and _in_range(hole, _BROADWAYS)


def _missed_draw(f: HandFacts, t: HandFacts, _h):
    return t.weak_made and t.any_draw and f.weak_made


def _ace_high_river(f: HandFacts, _t, _h):
    return f.ace_high


def _low_pair_river(f: HandFacts, t: HandFacts, _h):
    return f.low_pair and not t.strong_draw


def _tpwk_river(f: HandFacts, _t, _h):
    return f.top_pair and f.kicker != 1


def _tptk(f: HandFacts, _t, _h):
    return f.top_pair and f.kicker == 1


_D_OVERCARDS = "Overcards with pocket AK, AQ, or AJ"
_D_KQJ = "Overcards with pocket KQ, KJ, or QJ"


def _c(key, label, color, weak, description, rule) -> Category:
    return Category(key, label, color, weak, description, rule)


_FLOP = (
    _c("trash", "Trash", "#9DC397", True, "No pair and no draw", _trash),
    _c("kq_kj_qj", "KQ, KJ, QJ", "#3E8219", True, _D_KQJ, _kqj),
    _c("ace_high", "Ace High", "#78AE32", True, "Ace high without a draw",
       _ace_high(lambda f: f.any_draw)),
    _c("overcards_akj", "Overcards AK-J", "#78AE32", True, _D_OVERCARDS, _overcards_akj),
    _c("gutshot", "Gutshot", "#0BA3D7", True, "Gutshot without a pair", _gutshot),
    _c("draw", "Draw", "#3E5997", True, "Flush or straight draw", _draw),
    _c("low_pockets", "Low Pockets", "#653D87", True, "Low pocket pair", _low_pockets),
    _c("low_pair", "Low Pair", "#653D87", False, "Low pair", _low_pair_flop),
    _c("middle_pair", "Middle Pair", "#431D63", False, "Middle pair", _middle_pair),
    _c("tpwk", "TPWK", "#B7A913", False, "Top pair with weak kicker", _tpwk_flop),
    _c("tpgk", "TPGK", "#B76713", False, "Top pair with good kicker", _tpgk),
    _c("overpair", "Overpair", "#73524C", False, "Overpair", _overpair),
    _c("set", "Set", "#893A67", False, "Set", _set),
    _c("two_pairs_plus", "Two Pairs+", "#BC5F65", False, "Two pairs or higher", _two_pairs_plus),
)

_TURN = (
    _FLOP[0],
    _FLOP[1],
    _c("ace_high", "Ace High", "#78AE32", True, "Ace high without a flush or straight draw",
       _ace_high(lambda f: f.strong_draw)),
    _FLOP[3],
    _FLOP[4],
    _FLOP[5],
    _c("draw_pair", "Draw + Pair", "#222E6B", True, "Draw with a weak pair", _draw_pair_turn),
    _c("low_pair", "Low Pair", "#653D87", False, "Low pair or low pocket pair", _low_pair_turn),
    _FLOP[8],
    _c("tpwk", "TPWK", "#B7A913", False, "Top pair with weak kicker", _tpwk_turn),
    _FLOP[10],
    _FLOP[11],
    _FLOP[12],
    _FLOP[13],
)

_RIVER = (
    _c("missed_trash", "Missed Trash", "#9DC397", True, "No pair, no draw on the turn",
       _missed_trash),
    _c("missed_overcards", "Missed Overcards", "#3E8219", True, "Broadway overcards that missed",
       _missed_overcards),
    _c("ace_high", "Ace High", "#78AE32", True, "Ace high", _ace_high_river),
    _c("missed_draw", "Missed Draw", "#3E5997", True, "Turn draw that missed", _missed_draw),
    _c("low_pair", "Low Pair", "#653D87", False, "Low pair or low pocket pair", _low_pair_river),
    _FLOP[8],
    _c("tpwk", "TPWK", "#B7A913", False, "Top pair with weak kicker", _tpwk_river),
    _c("tptk", "TPTK", "#B76713", False, "Top pair with top kicker", _tptk),
    _FLOP[11],
    _FLOP[12],
    _FLOP[13],
)

STREET_CATEGORIES: dict[str, tuple[Category, ...]] = {
    "flop": _FLOP,
    "turn": _TURN,
    "river": _RIVER,
}

OTHER = -1
OTHER_LABEL = "Other"
OTHER_COLOR = "#A0A0A0"


def _first_match(street: str, f: HandFacts, t: HandFacts, hole: list[Card]) -> int:
    for i, cat in enumerate(STREET_CATEGORIES[street]):
        if cat.rule(f, t, hole):
            return i
    return OTHER


def _street_categories(h: list[Card], b: list[Card], upto: int = 3) -> dict[str, int]:
    """Categories for flop..river (as far as the board and `upto` reach),
    computing each street's facts once."""
    out: dict[str, int] = {}
    prev = _NO_FACTS
    for i, street in enumerate(_STREETS, start=1):
        n = _BOARD_LEN[street]
        if i > upto or len(b) < n:
            break
        f = _facts(h, b[:n])
        out[street] = _first_match(street, f, prev, h)
        prev = f  # the river rules look at the turn facts
    return out


def category(hole: Sequence[str | Card], board: Sequence[str | Card]) -> int:
    """Category index of `hole` on `board` in the board's street list.

    The street follows from the board length (3 flop, 4 turn, 5 river).
    Returns ``OTHER`` (-1) when no rule matches.
    """
    h, b = _cards(hole), _cards(board)
    if len(h) != 2 or not 3 <= len(b) <= 5:
        raise ValueError("need 2 hole cards and a 3-5 card board")
    street = _STREETS[len(b) - 3]
    t = _facts(h, b[:4]) if street == "river" else _NO_FACTS
    return _first_match(street, _facts(h, b), t, h)


def categories(hole: Sequence[str | Card], board: Sequence[str | Card]) -> dict[str, int]:
    """Category index for every street the board reaches: {'flop': i, ...}."""
    h, b = _cards(hole), _cards(board)
    if len(h) != 2 or len(b) > 5:
        raise ValueError("need 2 hole cards and at most 5 board cards")
    return _street_categories(h, b)


def category_info(street: str, index: int) -> dict:
    """Label, colour, weak flag and description of a category index."""
    if index == OTHER:
        return {"key": "other", "label": OTHER_LABEL, "color": OTHER_COLOR, "weak": False,
                "description": OTHER_LABEL}
    c = STREET_CATEGORIES[street][index]
    return {"key": c.key, "label": c.label, "color": c.color, "weak": c.weak,
            "description": c.description}


def is_weak(street: str, index: int) -> bool:
    """Weak flag of a category ("Other" is not weak)."""
    return index != OTHER and STREET_CATEGORIES[street][index].weak


def weak_pct(street: str, counts: dict[int, int]) -> float | None:
    """Share of weak hands in a {category index: hand count} histogram, in %.

    This is the "NN% weak" label of the strength bar; None when empty.
    """
    total = sum(counts.values())
    if not total:
        return None
    weak = sum(n for i, n in counts.items() if is_weak(street, i))
    return weak / total * 100


# ---------------------------------------------------------------------------
# Board categories (Boards tab). Not exclusive: a board can be in several.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoardCategory:
    key: str
    label: str
    test: Callable[[list[Card]], bool]


def _suits(cards: list[Card]) -> list[str]:
    return [s for _, s in cards]


def _flop_paired(b: list[Card]) -> bool:
    return len({r for r, _ in b[:3]}) == 2


def _third_to_flush(b: list[Card]) -> bool:
    last = b[-1][1]
    return _suits(b[:-1]).count(last) == 2


BOARD_CATEGORIES: dict[str, tuple[BoardCategory, ...]] = {
    "flop": (
        BoardCategory("rainbow", "Rainbow", lambda b: len(set(_suits(b[:3]))) == 3),
        BoardCategory("suited", "Suited", lambda b: len(set(_suits(b[:3]))) == 1),
        BoardCategory("ace_high", "Ace High", lambda b: any(r == 14 for r, _ in b[:3])),
        BoardCategory("paired", "Paired", _flop_paired),
    ),
    "turn": (
        BoardCategory("rainbow", "Rainbow", lambda b: len(set(_suits(b[:4]))) == 4),
        BoardCategory("ace_high", "Ace High", lambda b: any(r == 14 for r, _ in b[:4])),
        BoardCategory("third_card_to_flush", "Third Card to Flush",
                      lambda b: _third_to_flush(b[:4])),
    ),
    "river": (
        BoardCategory("ace_high", "Ace High", lambda b: any(r == 14 for r, _ in b[:5])),
        BoardCategory("third_card_to_flush", "Third Card to Flush",
                      lambda b: _third_to_flush(b[:5])),
        BoardCategory("over_card", "Over Card",
                      lambda b: all(b[4][0] > r for r, _ in b[:4])),
    ),
}


def board_categories(board: Sequence[str | Card], street: str | None = None) -> list[int]:
    """Indices of the street's board categories the board belongs to.

    `street` defaults to the board's own street (3/4/5 cards).
    """
    b = _cards(board)
    street = street or _STREETS[len(b) - 3]
    if len(b) < _BOARD_LEN[street]:
        return []
    return [i for i, c in enumerate(BOARD_CATEGORIES[street]) if c.test(b)]


# ---------------------------------------------------------------------------
# ParsedHand helpers
# ---------------------------------------------------------------------------

def player_boards(parsed: ParsedHand) -> list[list[str]]:
    """Every board of the hand as a flat card list (run-it-twice boards are
    completed with the shared streets of the first board)."""
    first = parsed.board_cards or {}
    boards = [[c for s in _STREETS for c in (first.get(s) or [])]]
    for extra in parsed.extra_boards or []:
        cards: list[str] = []
        for s in _STREETS:
            cards.extend(extra.get(s) or first.get(s) or [])
        boards.append(cards)
    return boards


def _seen_streets(parsed: ParsedHand, username: str, board_len: int) -> tuple[int, int]:
    """(last street index seen, last street index acted on), with preflop = 0,
    flop = 1, turn = 2, river = 3. A player who folded saw the street he
    folded on; anyone else saw every dealt street **on which someone acted**
    (H2N's "last street in hand" is the last street with actions, so the
    run-out after an all-in gets no hand value; Hand2Note results, parity round 3: KK
    all-in preflop has no flop category)."""
    order = ("preflop",) + _STREETS
    dealt = {3: 1, 4: 2, 5: 3}.get(board_len, 0)
    by_street = [parsed.actions_by_street.get(street) or [] for street in order]
    last_any = max((i for i, acts in enumerate(by_street) if acts), default=0)
    last_action = 0
    last_seen = min(dealt, last_any)
    for i, street_acts in enumerate(by_street):
        acts = [a for a in street_acts if a.get("username") == username]
        if acts:
            last_action = i
            if acts[-1].get("action") == "fold":
                last_seen = min(i, dealt)
    return last_seen, last_action


def _classify_board(hole, board: list[str], last_seen: int, last_action: int) -> dict[str, int | None]:
    out: dict[str, int | None] = {"hv_flop": None, "hv_turn": None, "hv_river": None}
    try:
        h = _cards(hole)
        b = _cards(board)
    except ValueError:
        return out
    if len(h) != 2 or not 3 <= len(b) <= 5 or len(set(h + b)) != len(h) + len(b):
        return out
    for i, (street, idx) in enumerate(_street_categories(h, b, last_seen).items(), start=1):
        if idx == OTHER and last_action < i:
            # H2N only files a hand under "Other" when the player acted on
            # the street; an unmatched all-in runout gets no category.
            continue
        out[f"hv_{street}"] = idx
    return out


def classify_for_player(parsed: ParsedHand, username: str) -> dict[str, int | None]:
    """hv_flop / hv_turn / hv_river for one player (first board).

    Index into the street's category list, -1 = Other, None when the hole
    cards are unknown, the street wasn't dealt, or the player had folded
    before it (or, for "Other", never acted on it).
    """
    hole = (parsed.hero_cards or {}).get(username)
    if not hole:
        return {"hv_flop": None, "hv_turn": None, "hv_river": None}
    board = player_boards(parsed)[0]
    last_seen, last_action = _seen_streets(parsed, username, len(board))
    return _classify_board(hole, board, last_seen, last_action)


def classify_boards_for_player(parsed: ParsedHand, username: str) -> list[dict[str, int | None]]:
    """Like classify_for_player, once per board (run it twice: one per run).

    The Boards / Bet Sizes mini bars count every board of a multi-board hand.
    """
    hole = (parsed.hero_cards or {}).get(username)
    boards = player_boards(parsed)
    if not hole:
        return [{"hv_flop": None, "hv_turn": None, "hv_river": None} for _ in boards]
    out = []
    for board in boards:
        last_seen, last_action = _seen_streets(parsed, username, len(board))
        out.append(_classify_board(hole, board, last_seen, last_action))
    return out


def apply_hand_values(parsed: ParsedHand, player_stats: dict[str, dict]) -> None:
    """Write hv_flop / hv_turn / hv_river into every player's flag dict.

    Called from ``app.h2n.apply_h2n`` (the H2N columns hook).
    """
    for username, flags in player_stats.items():
        flags.update(classify_for_player(parsed, username))
