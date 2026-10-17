"""Re-derive the H2N action sequence of a stored hand (for the popup API).

The `actions` table is not populated, so the popup (next actions, bet sizes,
hand rows) re-parses `hands.raw_text` with the hand's site parser and runs the
same sequence builder and matcher as the import:

    seq = replay(raw_text, site_id)
    res = match_row(seq, "C01", hero_username)
    if res and res.case:
        street, idx = res.hit           # the measured action
        act = seq.streets[street][idx]  # .letter, .amt_bb, .pot_bb, .flags, ...

`Act` fields (see app.h2n.sequence): actor / name / pos (h2n_pos), raw and
effective type (`raw`, `eff`, `letter`), flags including what was possible at
the decision (`P_RAISE`, `P_BET`, `P_CHECK`, `P_CALL`, ...), chips added
(`inc`, `inc_bb`), street total after the action (`to`, `to_bb`), H2N
effective amount (`amt_bb`), pot before the action (`pot_bb`), amount to
call (`to_call_bb`), effective chips behind (`stack_left_bb`), all-in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.h2n.definitions import COMPILED
from app.h2n.matcher import RowResult, evaluate
from app.h2n.sequence import HandSeq, build_sequence

if TYPE_CHECKING:
    from app.parsers.common import ParsedHand

__all__ = ["replay", "replay_parsed", "match_row", "parser_for"]


def parser_for(site: int | str):
    """Site parser module by site id (hands.site_id) or site code ("GG", ...)."""
    from app.parsers import PARSER_BY_SITE_ID, PARSERS

    if isinstance(site, int):
        parser = PARSER_BY_SITE_ID.get(site)
    else:
        parser = next((p for p in PARSERS if p.SITE_CODE == site), None)
    if parser is None:
        raise KeyError(f"no parser for site {site!r}")
    return parser


def replay_parsed(parsed: ParsedHand) -> HandSeq:
    return build_sequence(parsed)


def replay(raw_text: str, site: int | str) -> HandSeq:
    """Parse `raw_text` with the site's parser and build its H2N sequence."""
    return build_sequence(parser_for(site).parse_hand_history(raw_text))


def match_row(seq: HandSeq, key: str, player: str) -> RowResult | None:
    """Case / opportunity of row `key` (app.h2n.rows) for `player` in this hand.

    `hit` is the measured action for a case, or the action that made the
    opportunity (the player's decision) otherwise. None if the player is not
    in the hand.
    """
    p = seq.index.get(player)
    if p is None:
        return None
    return evaluate(COMPILED[key], seq, p)
