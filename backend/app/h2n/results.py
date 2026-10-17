"""H2N "is winner" (docs/specs/H2N-COMPATIBLE-STATS.md section 5).

- Fewer than two players left at the end (everyone else folded): the winner
  is whoever did not fold.
- Two or more players left (showdown): among the players who did not fold and
  whose hole cards are known, the best hand on the full five-card board wins
  (ties all win). With several boards (run it twice) the winners of every
  board are united. Folded players and players with unknown cards never win.
- If no player left has known cards, or the board is not complete, the
  winners are the players who collected anything.

It is a yes/no flag, not "won money": a split pot is a win, a side pot alone
behind a shorter all-in winner is not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parsers.common import ParsedHand

__all__ = ["participants", "winners"]

_STREETS = ("preflop", "flop", "turn", "river")


def participants(parsed: ParsedHand) -> tuple[set[str], set[str]]:
    """(players dealt in, players who folded), from the action log."""
    seated = {s["username"] for s in parsed.seats}
    dealt: set[str] = set()
    folded: set[str] = set()
    for street in _STREETS:
        for a in parsed.actions_by_street.get(street, ()):
            u = a["username"]
            if u not in seated:
                continue
            dealt.add(u)
            if a["action"] == "fold":
                folded.add(u)
    dealt.update(u for u in parsed.hero_cards if u in seated)
    return dealt, folded


def _boards(parsed: ParsedHand) -> list[list[str]]:
    main = parsed.board_cards
    base = list(main.get("flop") or []) + list(main.get("turn") or []) + list(main.get("river") or [])
    boards = [base]
    for extra in parsed.extra_boards or ():
        flop = extra.get("flop") or main.get("flop") or []
        if extra.get("flop"):
            turn = extra.get("turn") or []
        else:
            turn = extra.get("turn") or main.get("turn") or []
        river = extra.get("river") or []
        boards.append(list(flop) + list(turn) + list(river))
    return boards


def _collectors(parsed: ParsedHand, candidates: set[str]) -> set[str]:
    return {u for u, amt in parsed.collected.items() if amt and amt > 0 and u in candidates}


def winners(parsed: ParsedHand) -> set[str]:
    dealt, folded = participants(parsed)
    alive = dealt - folded
    if len(alive) < 2:
        return alive
    known = {u: parsed.hero_cards[u] for u in alive if u in parsed.hero_cards}
    boards = _boards(parsed)
    if not known or any(len(b) != 5 for b in boards):
        return _collectors(parsed, alive)
    try:
        import eval7

        out: set[str] = set()
        for board in boards:
            bcards = [eval7.Card(c) for c in board]
            scores = {u: eval7.evaluate([eval7.Card(c) for c in cards] + bcards)
                      for u, cards in known.items()}
            best = max(scores.values())
            out.update(u for u, sc in scores.items() if sc == best)
        return out
    except (ValueError, KeyError):  # unparseable cards
        return _collectors(parsed, alive)
