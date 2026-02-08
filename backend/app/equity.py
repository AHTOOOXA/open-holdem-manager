"""Poker equity calculator for all-in EV computation.

Uses treys library for hand evaluation.
Handles heads-up all-in equity with enumeration (≤2 cards to come)
or Monte Carlo sampling (preflop all-ins).
"""

import random
from itertools import combinations

from treys import Card, Evaluator

_evaluator = Evaluator()

# Full deck as treys Card integers
_FULL_DECK = [Card.new(r + s) for r in "23456789TJQKA" for s in "shdc"]


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
        num_samples: Monte Carlo sample count for preflop all-ins

    Returns:
        Hero equity as float 0.0-1.0
    """
    hero = [Card.new(c) for c in hero_cards]
    villain = [Card.new(c) for c in villain_cards]
    board_int = [Card.new(c) for c in board]

    dead = set(hero + villain + board_int)
    remaining = [c for c in _FULL_DECK if c not in dead]

    cards_to_come = 5 - len(board_int)

    if cards_to_come == 0:
        # River — direct comparison
        hero_rank = _evaluator.evaluate(board_int, hero)
        villain_rank = _evaluator.evaluate(board_int, villain)
        if hero_rank < villain_rank:
            return 1.0
        elif hero_rank > villain_rank:
            return 0.0
        return 0.5

    wins = 0
    ties = 0
    total = 0

    if cards_to_come <= 2:
        # Enumerate (flop all-in: ~990 combos, turn all-in: ~44 cards)
        for combo in combinations(remaining, cards_to_come):
            full_board = board_int + list(combo)
            hero_rank = _evaluator.evaluate(full_board, hero)
            villain_rank = _evaluator.evaluate(full_board, villain)
            if hero_rank < villain_rank:
                wins += 1
            elif hero_rank == villain_rank:
                ties += 1
            total += 1
    else:
        # Monte Carlo for preflop all-ins (C(48,5) = 1.7M combos)
        for _ in range(num_samples):
            sample = random.sample(remaining, cards_to_come)
            full_board = board_int + sample
            hero_rank = _evaluator.evaluate(full_board, hero)
            villain_rank = _evaluator.evaluate(full_board, villain)
            if hero_rank < villain_rank:
                wins += 1
            elif hero_rank == villain_rank:
                ties += 1
            total += 1

    return (wins + ties * 0.5) / total if total > 0 else 0.5
