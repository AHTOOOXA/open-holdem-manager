"""Poker equity calculator for all-in EV computation.

Uses eval7 library (C-backed) for fast hand evaluation.
Handles heads-up all-in equity with enumeration (≤2 cards to come)
or Monte Carlo sampling (preflop all-ins).
"""

import random
from itertools import combinations

import eval7

# Full deck as eval7 Card objects
_FULL_DECK = [eval7.Card(r + s) for r in "23456789TJQKA" for s in "shdc"]


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
    hero = [eval7.Card(c) for c in hero_cards]
    villain = [eval7.Card(c) for c in villain_cards]
    board_cards = [eval7.Card(c) for c in board]

    dead = set(hero + villain + board_cards)
    remaining = [c for c in _FULL_DECK if c not in dead]

    cards_to_come = 5 - len(board_cards)

    if cards_to_come == 0:
        # River — direct comparison (eval7: higher score = better hand)
        hero_rank = eval7.evaluate(hero + board_cards)
        villain_rank = eval7.evaluate(villain + board_cards)
        if hero_rank > villain_rank:
            return 1.0
        elif hero_rank < villain_rank:
            return 0.0
        return 0.5

    wins = 0
    ties = 0
    total = 0

    if cards_to_come <= 2:
        # Enumerate (flop all-in: ~990 combos, turn all-in: ~44 cards)
        for combo in combinations(remaining, cards_to_come):
            full_board = board_cards + list(combo)
            hero_rank = eval7.evaluate(hero + full_board)
            villain_rank = eval7.evaluate(villain + full_board)
            if hero_rank > villain_rank:
                wins += 1
            elif hero_rank == villain_rank:
                ties += 1
            total += 1
    else:
        # Monte Carlo for preflop all-ins (C(48,5) = 1.7M combos)
        for _ in range(num_samples):
            sample = random.sample(remaining, cards_to_come)
            full_board = board_cards + sample
            hero_rank = eval7.evaluate(hero + full_board)
            villain_rank = eval7.evaluate(villain + full_board)
            if hero_rank > villain_rank:
                wins += 1
            elif hero_rank == villain_rank:
                ties += 1
            total += 1

    return (wins + ties * 0.5) / total if total > 0 else 0.5
