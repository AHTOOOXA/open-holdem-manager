"""H2N (Hand2Note 4.1) compatible per-player columns.

`apply_h2n(parsed, player_stats)` is called once at the end of
`app.stat_flags.compute_stat_flags`. It adds the columns listed in
`app.h2n.columns.H2N_COLUMNS` to every player's flag dict, in place:

- `h2n_pos`: H2N column group (sequence.h2n_positions);
- `h2n_{pre,post}_{opp,case}`: one bit per matcher row (rows.py bit layout,
  definitions.py rows, matcher.py rules, sequence.py action annotations);
- `is_winner`: results.winners;
- `hv_*`: hand-value categories from `app.hand_value.apply_hand_values`
  (flop / turn / river category index, -1 = Other, NULL = not classified);
- `h2n_valid`: FALSE when H2N would refuse to import the hand
  (`hand_rejection`); the General screen leaves such hands out;
- `h2n_seq`: the hand's sequence (app.h2n.seqcodec) in one player's row, for
  the stat popup.

Contract: CONTRACT.md in this package.

Do not import app.stat_flags or app.db from this package (circular import).
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.hand_value import apply_hand_values
from app.h2n.columns import H2N_DEFAULTS
from app.h2n.definitions import COMPILED, MATCHED_KEYS
from app.h2n.matcher import (
    AMOUNT_EPS, CASE, evaluate_code, evaluate_rest, first_part_binds, gate,
)
from app.h2n.results import winners
from app.h2n.rows import ROWS
from app.h2n.seqcodec import encode_sequence
from app.h2n.sequence import (
    BET, CALL, CHECK, FR, OPEN, P_BET, P_RAISE, RAISE, HandSeq, build_sequence,
)

if TYPE_CHECKING:
    from app.parsers.common import ParsedHand

__all__ = ["apply_h2n", "compute_h2n", "compute_player_bits", "hand_rejection"]

log = logging.getLogger(__name__)


def _plans(keys):
    return tuple((COMPILED[k], ROWS[k].mask == "pre", ROWS[k].flag) for k in keys)


# Definitions that only look at preflop, and the rest (their first part is preflop).
_PRE_PLANS = _plans(k for k in MATCHED_KEYS if all(pt.street == 0 for pt in COMPILED[k].parts))
_POST_PLANS = _plans(k for k in MATCHED_KEYS if COMPILED[k].street > 0)
assert len(_PRE_PLANS) + len(_POST_PLANS) == len(MATCHED_KEYS)
# Every postflop definition starts with a preflop part; definitions sharing
# that part are grouped so it is matched once per player (see _post_candidates).
assert all(len(d.parts) > 1 and d.parts[0].street == 0 for d, _, _ in _POST_PLANS)
_POST_GROUPS: tuple[tuple[object, tuple], ...] = tuple(
    (d0, tuple(pl for pl in _POST_PLANS if pl[0].parts[0].key == key))
    for key, d0 in {pl[0].parts[0].key: pl[0] for pl in _POST_PLANS}.items()
)

_E_FLAGS = tuple(
    (street, ROWS[f"E_{name}_ANY"].flag, ROWS[f"E_{name}_B"].flag, ROWS[f"E_{name}_R"].flag,
     ROWS[f"E_{name}_C"].flag, ROWS[f"E_{name}_BR"].flag)
    for street, name in ((1, "FLOP"), (2, "TURN"), (3, "RIVER"))
)

# Preflop results only depend on the preflop action list (actors, effective
# types, the flags the definitions test, and on which side of each amount
# filter an amount falls), the column groups and who has a preflop sequence.
# Real hands repeat these shapes a lot (under 1k distinct shapes per 20k 6-max
# hands), so preflop results are memoised per shape: the preflop masks of
# every player, and the preflop parts of the postflop definitions.
_SHAPES: dict[tuple, tuple[tuple[tuple[int, int], ...], list[tuple | None]]] = {}
_SHAPES_LIMIT = 100_000


def _preflop_inputs() -> tuple[int, dict[int, tuple], dict[int, tuple]]:
    """What the preflop parts of the definitions read from an action.

    (flag mask, {effective type: amount ranges}, {effective type: possible
    call ranges}); ranges are the inclusive (lo, hi) bb filters of filter
    actions (amount) and of opportunity alternatives (call amount).
    """
    mask = FR | OPEN   # first_raise_idx / open_idx come from these
    amounts: dict[int, set] = {}
    calls: dict[int, set] = {}
    for d in COMPILED.values():
        mask |= d.anchor_req
        for part in d.parts:
            if part.street != 0:
                continue
            last = part is d.parts[-1]   # alternatives only matter on the last part
            for row, _k, _last, alts, _nh in part.plans:
                for f in row + alts if last else row:
                    mask |= f.req
                    if f.lo is not None:
                        amounts.setdefault(f.typ, set()).add((f.lo, f.hi))
                    if f.call_lo is not None:
                        calls.setdefault(f.typ, set()).add((f.call_lo, f.call_hi))
    return (mask, {t: tuple(sorted(r)) for t, r in amounts.items()},
            {t: tuple(sorted(r)) for t, r in calls.items()})


_PRE_MASK, _PRE_AMOUNTS, _PRE_CALLS = _preflop_inputs()


def _amount_key(a) -> tuple | int:
    """Which amount / call-amount filters the action passes (0: none apply)."""
    eff = a.eff
    ranges = _PRE_AMOUNTS.get(eff)
    calls = _PRE_CALLS.get(eff)
    if ranges is None and calls is None:
        return 0
    key = []
    if ranges:
        amt = a.amt_bb
        key.extend(lo - AMOUNT_EPS <= amt <= hi + AMOUNT_EPS for lo, hi in ranges)
    if calls:
        amt = a.to_call_bb if a.to_call_bb < a.stack_left_bb else a.stack_left_bb
        key.extend(lo - AMOUNT_EPS <= amt <= hi + AMOUNT_EPS for lo, hi in calls)
    return tuple(key)


def preflop_signature(seq: HandSeq) -> tuple:
    mask = _PRE_MASK
    return (
        tuple(seq.pos),
        tuple((a.actor, a.eff, a.flags & mask, _amount_key(a)) for a in seq.streets[0]),
        tuple(h[0] for h in seq.has_seq),
    )


def _pre_bits(seq: HandSeq, p: int) -> tuple[int, int]:
    opp = case = 0
    for d, _is_pre, flag in _PRE_PLANS:
        if gate(d, seq, p):
            code, _ = evaluate_code(d, seq, p)
            if code:
                opp |= flag
                if code & CASE:
                    case |= flag
    return opp, case


def _post_candidates(seq: HandSeq, p: int) -> tuple:
    """Postflop plans whose preflop part matches for player p, each with the
    villain bindings that part leaves: (def, is_pre, flag, binds).

    Depends on the preflop shape only, so compute_h2n memoises it per shape.
    """
    out = []
    for d0, plans in _POST_GROUPS:
        binds = first_part_binds(d0, seq, p)
        if binds:
            out.extend((d, is_pre, flag, binds) for d, is_pre, flag in plans)
    return tuple(out)


def _post_bits(seq: HandSeq, p: int, cands: tuple | None) -> tuple[int, int, int, int]:
    """(pre_opp, pre_case, post_opp, post_case) contributions of the postflop plans.

    `cands`: `_post_candidates(seq, p)` (computed here when None).
    """
    if cands is None:
        cands = _post_candidates(seq, p)
    pre_opp = pre_case = opp = case = 0
    cache: dict = {}
    for d, is_pre, flag, binds in cands:
        if not gate(d, seq, p):
            continue
        code, _ = evaluate_rest(d, seq, p, binds, cache)
        if code:
            if is_pre:
                pre_opp |= flag
                if code & CASE:
                    pre_case |= flag
            else:
                opp |= flag
                if code & CASE:
                    case |= flag
    # Per-street single-action E rows (Bet / Raise / Call / Bet or Raise / Any
    # action X), straight from the player's own actions. Case: an action of
    # that effective type. Opportunity (H2N's single-action rule, as in the
    # matcher): an action where that type was the measured one or one of its
    # alternatives -- bet: bet / check / fold with a bet possible; raise:
    # raise / call / fold with a raise possible; call: call / raise / fold.
    for street, f_any, f_b, f_r, f_c, f_br in _E_FLAGS:
        own = seq.own[p][street]
        if not own:
            continue
        acts = seq.streets[street]
        end = seq.seq_end[p][street]
        hit = 0
        can = 0
        for i in own:
            if i < end:
                a = acts[i]
                e = a.eff
                hit |= f_any
                if e == BET:
                    hit |= f_b | f_br
                elif e == RAISE:
                    hit |= f_r | f_br
                elif e == CALL:
                    hit |= f_c
                if e != CALL and a.flags & P_BET:
                    can |= f_b | f_br
                if e != CHECK and e != BET:
                    can |= f_c
                    if a.flags & P_RAISE:
                        can |= f_r | f_br
        opp |= hit | can
        case |= hit
    return pre_opp, pre_case, opp, case


def compute_player_bits(seq: HandSeq, p: int) -> tuple[int, int, int, int]:
    """(pre_opp, pre_case, post_opp, post_case) for player index p (no caching)."""
    pre_opp, pre_case = _pre_bits(seq, p)
    if seq.has_seq[p][1]:
        a, b, post_opp, post_case = _post_bits(seq, p, None)
        return pre_opp | a, pre_case | b, post_opp, post_case
    return pre_opp, pre_case, 0, 0


_SITE_GG = 1
_RE_GG_UNKNOWN_ACTION = re.compile(r"^[^\n:]+: Bet & Muck", re.M)


_COLLECTED_TOKEN = " collected $"
_AMOUNT_CHARS = frozenset("0123456789.")


def _collected_bound(parsed: ParsedHand) -> float:
    """Cheap upper bound of `app.money.collected_total(parsed)`.

    That total is the sum of the GG body lines "<name> collected $X from pot"
    (or the parser's collected amounts when there are none). Summing every
    " collected $X" between the hole cards and the summary, and taking the
    max with the parser's amounts, can only be larger, so a hand whose bound
    is not above what was paid in needs no money replay. Returns +inf when
    the text cannot be read this way (the exact check then decides).
    """
    parser_total = float(sum(parsed.collected.values()))
    if parsed.site_id != _SITE_GG:
        return parser_total
    text = parsed.raw_text or ""
    i_hole = text.find("*** HOLE CARDS ***")
    if i_hole < 0:
        i_hole = 0
    end = text.find("*** SUMMARY ***")
    if end < 0:
        end = len(text)
    body = 0.0
    tok = _COLLECTED_TOKEN
    chars = _AMOUNT_CHARS
    i = text.find(tok, i_hole, end)
    while i >= 0:
        j = k = i + len(tok)
        while k < end and text[k] in chars:
            k += 1
        try:
            body += float(text[j:k])
        except ValueError:
            return float("inf")
        i = text.find(tok, k, end)
    return body if body > parser_total else parser_total


def hand_rejection(parsed: ParsedHand, seq: HandSeq | None = None) -> str | None:
    """Why H2N would refuse to import this hand, or None.

    H2N rebuilds every hand from its amounts and drops it when they do not
    add up (docs/specs/H2N-COMPATIBLE-STATS.md 2.1). Corrupted GG histories hit three of its
    checks: a raise to an amount that is not above the current bet (preflop:
    not above twice the small blind when the small blind posted more than
    the big blind), a call
    that is neither the amount to call nor the rest of a short stack
    (both found by `build_sequence`), and a pot that pays out more than was
    put into it (negative pot rake). Its GG reader also stops at action
    lines it does not know ("Bet & Muck").

    The amount and action-line checks are verified against Hand2Note's results on GG
    hands only and apply to GG; the pot check applies to every room.
    """
    if parsed.site_id == _SITE_GG:
        if seq is None:
            seq = build_sequence(parsed)
        if seq.reject:
            return seq.reject
        text = parsed.raw_text or ""
        if "Bet & Muck" in text and _RE_GG_UNKNOWN_ACTION.search(text):
            return "unknown GG action line (Bet & Muck)"
    # Cheap necessary condition first: more collected than put in (net of
    # uncalled bets). Rare, so the money rules only run for a few hands.
    if seq is None:
        seq = build_sequence(parsed)
    paid_in = (seq.pot_total + float(parsed.cash_drop_received or 0)
               - float(sum(parsed.uncalled_returns.values())))
    if _collected_bound(parsed) <= paid_in + 0.005 - 1e-9:
        return None
    from app.money import collected_total, compute_hand_money

    if float(collected_total(parsed)) <= paid_in + 0.005:
        return None

    for pot in compute_hand_money(parsed, with_ev=False).pots:
        if pot.collected and pot.after > pot.size:
            return f"pot {pot.num} pays {pot.after} out of {pot.size}"
    return None


def _sequence_copy(parsed: ParsedHand, seq: HandSeq) -> tuple[int, bytes | None]:
    """(player index that carries the hand's h2n_seq blob, blob).

    One copy per hand: the first player (clockwise from the button) whose
    hole cards are known -- the hero in a hero's own history -- else the
    first player. The popup reads it from whichever row has it.
    """
    try:
        blob = encode_sequence(seq)
    except Exception:  # the popup falls back to re-parsing the hand
        log.warning("h2n_seq encoding failed for hand %s", parsed.hand_id, exc_info=True)
        return -1, None
    known = parsed.hero_cards or {}
    for p, name in enumerate(seq.names):
        if name in known:
            return p, blob
    return 0, blob


def compute_h2n(parsed: ParsedHand, use_cache: bool = True) -> dict[str, dict]:
    """H2N columns per username (raises on malformed hands; see apply_h2n)."""
    seq = build_sequence(parsed)
    won = winners(parsed)
    try:
        valid = hand_rejection(parsed, seq) is None
    except Exception:  # money rules failing must not hide the hand
        log.warning("H2N validity check failed for hand %s", parsed.hand_id, exc_info=True)
        valid = True
    n = len(seq.names)
    if use_cache:
        sig = preflop_signature(seq)
        shape = _SHAPES.get(sig)
        if shape is None:
            if len(_SHAPES) >= _SHAPES_LIMIT:
                _SHAPES.clear()
            shape = _SHAPES[sig] = (tuple(_pre_bits(seq, p) for p in range(n)), [None] * n)
        pre, post_cands = shape
    else:
        pre = tuple(_pre_bits(seq, p) for p in range(n))
        post_cands = [None] * n
    carrier, blob = _sequence_copy(parsed, seq)
    out: dict[str, dict] = {}
    for p, name in enumerate(seq.names):
        pre_opp, pre_case = pre[p]
        post_opp = post_case = 0
        if seq.has_seq[p][1]:
            cands = post_cands[p]
            if cands is None:
                cands = _post_candidates(seq, p)
                if use_cache:
                    post_cands[p] = cands
            a, b, post_opp, post_case = _post_bits(seq, p, cands)
            pre_opp |= a
            pre_case |= b
        out[name] = {
            "h2n_pos": seq.pos[p],
            "h2n_pre_opp": pre_opp,
            "h2n_pre_case": pre_case,
            "h2n_post_opp": post_opp,
            "h2n_post_case": post_case,
            "is_winner": name in won,
            "h2n_valid": valid,
            "h2n_seq": blob if p == carrier else None,
            # no hole cards, no hand value; apply_h2n classifies the others
            "hv_flop": None,
            "hv_turn": None,
            "hv_river": None,
        }
    return out


# Columns compute_h2n fills: every column (hand values as None), so apply_h2n
# can skip writing the defaults first (checked, not assumed).
_COMPUTED_KEYS = frozenset((
    "h2n_pos", "h2n_pre_opp", "h2n_pre_case", "h2n_post_opp", "h2n_post_case",
    "is_winner", "h2n_valid", "h2n_seq", "hv_flop", "hv_turn", "hv_river",
))
_COVERS_DEFAULTS = set(H2N_DEFAULTS) == _COMPUTED_KEYS


def apply_h2n(parsed: ParsedHand, player_stats: dict[str, dict]) -> None:
    """Fill the H2N columns for every player in `player_stats` (mutates it).

    The matcher columns and the hand-value columns are computed independently:
    a failure in one keeps that part at its defaults and still fills the other.
    """
    hand_id = getattr(parsed, "hand_id", "?")
    try:
        computed = compute_h2n(parsed)
    except Exception:  # never drop a hand from the import because of this layer
        log.exception("H2N columns failed for hand %s", hand_id)
        computed = {}
    # Computed players get every column (hand values None until classified
    # below); anyone else keeps the defaults.
    for name, flags in player_stats.items():
        cols = computed.get(name)
        if cols and _COVERS_DEFAULTS:
            flags.update(cols)
        else:
            flags.update(H2N_DEFAULTS)
            if cols:
                flags.update(cols)
    try:
        # Only players with known hole cards can have a hand value.
        known = parsed.hero_cards or {}
        apply_hand_values(parsed, {u: f for u, f in player_stats.items() if u in known})
    except Exception:
        for flags in player_stats.values():
            flags.update(hv_flop=None, hv_turn=None, hv_river=None)
        log.exception("hand values failed for hand %s", hand_id)
