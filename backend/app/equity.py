"""Poker equity calculator for all-in EV computation.

Uses eval7 library (C-backed) for fast hand evaluation.

- `equities()`: all-in equity of 2+ hands at any street, the way Hand2Note
  computes it: heads-up preflop exact (from a precomputed table), flop and
  turn exact (every runout), 3+ hands preflop by Monte Carlo, river is the
  showdown result. Ties are split equally. No dead cards.
- `calculate_headsup_equity()`: the older heads-up helper (kept for callers
  and the packaged-build self check).
"""

import base64
import itertools
import random
import zlib
from array import array
from bisect import bisect_left
from functools import lru_cache
from itertools import combinations

import eval7

# Full deck as eval7 Card objects
_FULL_DECK = [eval7.Card(r + s) for r in "23456789TJQKA" for s in "shdc"]

# Card ids for the preflop table: rank * 4 + suit
_RANKS = "23456789TJQKA"
_SUITS = "shdc"
_PERMS = list(itertools.permutations(range(4)))
PREFLOP_BOARDS = 1_712_304  # C(48, 5)
MULTIWAY_PREFLOP_SAMPLES = 100_000


def card_id(card: str) -> int:
    return _RANKS.index(card[0].upper()) * 4 + _SUITS.index(card[1].lower())


def canonical_matchup(a: tuple[int, int], b: tuple[int, int]):
    """Suit-canonical form of a heads-up matchup.

    Returns ((hand1, hand2), swapped): the smallest form over all suit
    permutations and both hand orders, and whether hand1 is `b`.
    """
    best = None
    swapped = False
    for p in _PERMS:
        h1 = tuple(sorted((c - c % 4 + p[c % 4] for c in a), reverse=True))
        h2 = tuple(sorted((c - c % 4 + p[c % 4] for c in b), reverse=True))
        key, sw = ((h1, h2), False) if h1 >= h2 else ((h2, h1), True)
        if best is None or key < best:
            best, swapped = key, sw
    return best, swapped


def _encode_key(matchup) -> int:
    (a1, a2), (b1, b2) = matchup
    return a1 << 18 | a2 << 12 | b1 << 6 | b2


@lru_cache(maxsize=1)
def _preflop_table():
    try:
        from app.preflop_equity_data import COUNT, DATA
    except ImportError:
        return None
    raw = zlib.decompress(base64.b64decode("".join(DATA)))
    keys, vals = array("I"), array("I")
    keys.frombytes(raw[:4 * COUNT])
    vals.frombytes(raw[4 * COUNT:])
    return keys, vals


def _ranks(hands, board_cards):
    return [eval7.evaluate(h + board_cards) for h in hands]


def _add_shares(shares: list[float], values: list[int]) -> None:
    best = max(values)
    winners = [i for i, v in enumerate(values) if v == best]
    part = 1.0 / len(winners)
    for i in winners:
        shares[i] += part


def _enumerate(hands, board, remaining, k) -> list[float]:
    shares = [0.0] * len(hands)
    n = 0
    for combo in combinations(remaining, k):
        _add_shares(shares, _ranks(hands, board + list(combo)))
        n += 1
    return [s / n for s in shares]


def _headsup_preflop(h1: tuple[str, str], h2: tuple[str, str]) -> float | None:
    table = _preflop_table()
    if table is None:
        return None
    a = tuple(card_id(c) for c in h1)
    b = tuple(card_id(c) for c in h2)
    matchup, swapped = canonical_matchup(a, b)
    keys, vals = table
    key = _encode_key(matchup)
    i = bisect_left(keys, key)
    if i == len(keys) or keys[i] != key:
        return None
    eq = vals[i] / (2 * PREFLOP_BOARDS)
    return 1.0 - eq if swapped else eq


def equities(
    hands: list[tuple[str, str]],
    board: list[str],
    samples: int = MULTIWAY_PREFLOP_SAMPLES,
) -> list[float]:
    """All-in equity of each hand with `board` (0, 3, 4 or 5 cards) known.

    Folded players' cards are not removed from the deck (as in Hand2Note).
    Ties are split equally between the tied hands.
    """
    if len(hands) < 2:
        return [1.0] * len(hands)
    k = 5 - len(board)
    if len(hands) == 2 and k == 5:
        eq = _headsup_preflop(hands[0], hands[1])
        if eq is not None:
            return [eq, 1.0 - eq]
    hs = [[eval7.Card(c) for c in h] for h in hands]
    bc = [eval7.Card(c) for c in board]
    dead = {c for h in hs for c in h} | set(bc)
    remaining = [c for c in _FULL_DECK if c not in dead]
    if k <= 0:
        shares = [0.0] * len(hs)
        _add_shares(shares, _ranks(hs, bc))
        return shares
    if k <= 2:
        return _enumerate(hs, bc, remaining, k)
    # 3+ hands preflop (or a missing table): Monte Carlo, seeded by the
    # cards so the same hand always gets the same numbers
    rng = random.Random("|".join(sorted("".join(h) for h in hands)) + "/" + "".join(board))
    shares = [0.0] * len(hs)
    for _ in range(samples):
        _add_shares(shares, _ranks(hs, bc + rng.sample(remaining, k)))
    return [s / samples for s in shares]


def calculate_headsup_equity(
    hero_cards: tuple[str, str],
    villain_cards: tuple[str, str],
    board: list[str],
    num_samples: int = 10000,
) -> float:
    """Calculate hero's equity in a heads-up all-in.

    Args:
        hero_cards: Hero's hole cards, e.g. ('Ah', 'Kd')
        villain_cards: Villain's hole cards, e.g. ('Qs', 'Ts')
        board: Board cards at the all-in point, e.g. ['Qh', '9d', '3c']
        num_samples: Monte Carlo sample count for preflop all-ins when the
            exact preflop table is unavailable

    Returns:
        Hero equity as float 0.0-1.0
    """
    return equities([hero_cards, villain_cards], board, samples=num_samples)[0]
