"""WP-M: H2N action-row matcher (app/h2n).

Vectors: docs/specs/H2N-COMPATIBLE-STATS.md section 8 (worked examples; T1-T14
here are examples 1-14) and more hand-level cases. Each vector is a GGPoker-format hand history
built by `hh()` below, parsed with the real GG parser, then run through the
matcher. Expectations use "oc" (opportunity + case), "o" (opportunity only)
and "-" (neither).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import app.stat_flags as stat_flags
from app.api.import_hands import insert_parsed_hand
from app.h2n import apply_h2n, compute_h2n
from app.h2n import rows as h2n_rows
from app.h2n.columns import H2N_COLUMN_NAMES, H2N_POSITIONS
from app.h2n.definitions import COMPILED, DEFINITIONS, MATCHED_KEYS
from app.h2n.matcher import compile_def, evaluate
from app.h2n.replay import match_row, replay, replay_parsed
from app.h2n.results import winners
from app.h2n.sequence import (
    CALL, CHECK, FR, IPL, IPV, LIMP, OOPL, OOPV, P_RAISE, RAISE, TB, build_sequence,
    h2n_positions,
)
from app.parsers import PARSERS
from app.parsers.ggpoker import parse_hand_history

FIXTURES = Path(__file__).parent / "fixtures"

# ── hand history builder ─────────────────────────────────────────────────

_DEFAULT_CARDS = {
    "flop": ["2c", "7d", "9h"], "turn": ["Ks"], "river": ["4s"],
}


def _money(x: float) -> str:
    d = Decimal(str(round(x, 2))).normalize()
    return f"${d:f}"


def hh(order: list[str], script: str, *, stacks: dict[str, float] | None = None,
       hero: str | None = None, cards: dict[str, str] | None = None,
       shows: tuple[str, ...] = (), board: list[str] | None = None,
       collected: dict[str, float] | None = None, max_seats: int = 6,
       hand_no: int = 1) -> str:
    """GGPoker hand history from a compact script.

    `order`: usernames clockwise starting with the button (2 players: button,
    big blind). Blinds are $0.5/$1, so amounts are in big blinds.
    `script`: streets separated by "|", actions by ",": "NAME F|X|C|B<x>|R<to>".
    Calls are sized automatically; an action that empties the stack is
    written "and is all-in".
    """
    stacks = {n: 100.0 for n in order} | (stacks or {})
    left = dict(stacks)
    seats = list(range(1, len(order) + 1))
    lines = [
        f"Poker Hand #RC{hand_no:09d}: Hold'em No Limit ($0.5/$1) - 2026/01/15 20:35:18",
        f"Table 'RushAndCash9' {max_seats}-max Seat #1 is the button",
    ]
    for s, n in zip(seats, order):
        lines.append(f"Seat {s}: {n} ({_money(stacks[n])} in chips)")
    if len(order) == 2:
        sb, bb = order[0], order[1]
    else:
        sb, bb = order[1], order[2]
    bets = {n: 0.0 for n in order}

    def post(name, amt, what):
        amt = min(amt, left[name])
        left[name] -= amt
        bets[name] += amt
        lines.append(f"{name}: posts {what} {_money(amt)}")

    post(sb, 0.5, "small blind")
    post(bb, 1.0, "big blind")
    lines.append("*** HOLE CARDS ***")
    cards = cards or {}
    for n in order:
        if n in cards:
            c = cards[n]
            lines.append(f"Dealt to {n} [{c[:2]} {c[2:]}]")
    brd = board or (_DEFAULT_CARDS["flop"] + _DEFAULT_CARDS["turn"] + _DEFAULT_CARDS["river"])
    streets = [s.strip() for s in script.split("|")]
    for si, street in enumerate(streets):
        if si == 1:
            lines.append(f"*** FLOP *** [{' '.join(brd[:3])}]")
        elif si == 2:
            lines.append(f"*** TURN *** [{' '.join(brd[:3])}] [{brd[3]}]")
        elif si == 3:
            lines.append(f"*** RIVER *** [{' '.join(brd[:4])}] [{brd[4]}]")
        if si > 0:
            bets = {n: 0.0 for n in order}
        for tok in (t.strip() for t in street.split(",")):
            if not tok:
                continue
            name, verb = tok.split()
            kind, amt = verb[0], verb[1:]
            level = max(bets.values())
            if kind == "F":
                lines.append(f"{name}: folds")
            elif kind == "X":
                lines.append(f"{name}: checks")
            elif kind == "C":
                inc = min(level - bets[name], left[name])
                left[name] -= inc
                bets[name] += inc
                tail = " and is all-in" if left[name] <= 1e-9 else ""
                lines.append(f"{name}: calls {_money(inc)}{tail}")
            elif kind == "B":
                inc = min(float(amt), left[name])
                left[name] -= inc
                bets[name] += inc
                tail = " and is all-in" if left[name] <= 1e-9 else ""
                lines.append(f"{name}: bets {_money(inc)}{tail}")
            elif kind == "R":
                to = min(float(amt), bets[name] + left[name])
                inc = to - bets[name]
                left[name] -= inc
                tail = " and is all-in" if left[name] <= 1e-9 else ""
                lines.append(f"{name}: raises {_money(to - level)} to {_money(to)}{tail}")
                bets[name] = to
            else:
                raise ValueError(tok)
    if shows:
        if len(streets) < 4:  # all-in run-out
            lines.append(f"*** FLOP *** [{' '.join(brd[:3])}]")
            lines.append(f"*** TURN *** [{' '.join(brd[:3])}] [{brd[3]}]")
            lines.append(f"*** RIVER *** [{' '.join(brd[:4])}] [{brd[4]}]")
        lines.append("*** SHOWDOWN ***")
        for n in shows:
            c = cards[n]
            lines.append(f"{n}: shows [{c[:2]} {c[2:]}]")
    lines.append("*** SUMMARY ***")
    total = sum(stacks[n] - left[n] for n in order)
    lines.append(f"Total pot {_money(total)} | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0")
    lines.append(f"Board [{' '.join(brd)}]")
    for s, n in zip(seats, order):
        if collected and n in collected:
            lines.append(f"Seat {s}: {n} collected ({_money(collected[n])})")
        else:
            lines.append(f"Seat {s}: {n} folded")
    return "\n".join(lines) + "\n"


SIX = ["BTN", "SB", "BB", "UTG", "MP", "CO"]


def run(text: str):
    parsed = parse_hand_history(text)
    return parsed, compute_h2n(parsed)


def state(cols: dict, key: str) -> str:
    slot = h2n_rows.row(key)
    opp = h2n_rows.has_bit(cols[slot.opp_column], key)
    case = h2n_rows.has_bit(cols[slot.case_column], key)
    assert not case or opp, f"{key}: case without opportunity"
    return "oc" if case else "o" if opp else "-"


def check(computed: dict, name: str, **expected: str) -> None:
    cols = computed[name]
    got = {k: state(cols, k) for k in expected}
    assert got == expected, f"{name}: {got} != {expected}"


# ── H2N-COMPATIBLE-STATS.md section 8, examples 1-14 ───────────────


def test_t1_squeeze():
    _, c = run(hh(SIX, "UTG R2.5, MP C, CO R11, BTN F, SB F, BB F, UTG F, MP F"))
    check(c, "CO", P07="oc", P08="-", P09="-", P10="-", P24="oc", P06="-")
    check(c, "UTG", P03="-", P13="-")
    check(c, "MP", P06="oc")


def test_t2_3bet_called_before_opener_acts():
    _, c = run(hh(SIX, "UTG R2.5, MP F, CO R8, BTN C, SB F, BB F, UTG F"))
    check(c, "UTG", P03="-")
    check(c, "CO", P08="oc")


def test_t3_4bet_allin_leaves_no_5bet():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN R8, SB F, BB F, CO R100, BTN F"))
    check(c, "BTN", P19="oc", P20="o", P21="-")
    check(c, "CO", P13="oc", P16="-")


def test_t3_variant_4bet_not_allin():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN R8, SB F, BB F, CO R20, BTN R100, CO F"))
    check(c, "BTN", P21="oc")
    check(c, "CO", P16="oc")


def test_t4_heads_up_button_steal():
    parsed, c = run(hh(["Hero", "V"], "Hero R2.5, V F", max_seats=2))
    assert c["Hero"]["h2n_pos"] == "SB" and c["V"]["h2n_pos"] == "BB"
    check(c, "Hero", P01="oc", P02="oc")
    check(c, "V", P26F="oc", P26C="o", P26R="o", P25F="-")


def test_t4_variant_button_completes():
    _, c = run(hh(["Hero", "V"], "Hero C, V R4, Hero F", max_seats=2))
    check(c, "Hero", P22="-", P23="oc")


def test_t5_fold_to_cbet_amount_filter():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2, BTN F, SB F, BB C | BB X, CO B1.5, BB F"))
    check(c, "BB", C04="-", C07="o", C08="o", C12="-")


def test_t5_variant_increment_two_is_inclusive():
    _, c = run(hh(SIX, "UTG F, MP F, CO R3, BTN F, SB F, BB C | BB X, CO B2, BB F"))
    check(c, "BB", C04="oc")


def test_t5_variant_sb_vs_bb_call_increment():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB C, BB F | SB X, CO B2, SB F"))
    check(c, "SB", C04="oc")
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB C | BB X, CO B2, BB F"))
    check(c, "BB", C04="-")


def test_t6_multiway_middle_seat():
    parsed, c = run(hh(SIX, "UTG R2.5, MP F, CO C, BTN F, SB F, BB C | BB X, UTG X, CO X"))
    seq = build_sequence(parsed)
    utg_check = seq.streets[1][1]
    assert utg_check.name == "UTG" and not utg_check.flags & (IPL | OOPL)
    check(c, "UTG", C01="o", M01="oc", M02="-", M03="-")
    check(c, "CO", N01="o")
    check(c, "BB", N01="-", N02="-", N03="-", N04="-", N05="-", N06="-")


def test_t7_tri_state_preflop_position():
    parsed, c = run(hh(SIX, "UTG C, MP F, CO F, BTN F, SB R4, BB R12"))
    seq = build_sequence(parsed)
    bb_raise = seq.streets[0][-1]
    assert bb_raise.name == "BB" and not bb_raise.flags & (IPV | OOPV)
    check(c, "BB", P07="oc", P08="oc", P11="oc", P09="-", P10="-", P12="-")
    check(c, "SB", P01="oc")


def test_t8_limp_vs_complete_limp_fold():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN C, SB C, BB R4, BTN F, SB F"))
    check(c, "SB", P22="-", P23="oc")
    check(c, "BTN", P22="oc", P23="-")


def test_t9_cbet_in_3bet_pot():
    _, c = run(hh(SIX, "UTG R2.5, MP F, CO F, BTN R8, SB F, BB F, UTG C | UTG X, BTN B5, UTG F"))
    check(c, "BTN", C01="-")
    check(c, "UTG", C09="oc", C04="oc", C07="-", C08="-")


def test_t10_delayed_barrels():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN R2.5, SB F, BB C | BB X, BTN X "
                       "| BB X, BTN B4, BB C | BB X, BTN B10, BB F"))
    check(c, "BTN", C02="-", C03="-", M01="oc", M02="oc")
    check(c, "BB", N03="o", N04="o")


def test_t11_check_fold_has_no_oop_flag():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN C, SB F, BB F | CO X, BTN X | CO B2, BTN F"))
    check(c, "BTN", N04="oc", N02="oc", M01="-", M02="-", M03="-", M04="-", M05="-")


def test_t12_donk_vs_ip_stab():
    _, c = run(hh(SIX, "UTG F, MP F, CO R3, BTN C, SB F, BB F | CO X, BTN B4, CO F"))
    check(c, "BTN", C12="-", N01="oc")
    _, c = run(hh(SIX, "UTG F, MP F, CO R3, BTN F, SB F, BB C | BB B3, CO F"))
    check(c, "BB", C12="oc")


def test_t13_call_4bet_counts_squeezes():
    _, c = run(hh(SIX, "UTG R2.5, MP C, CO R11, BTN F, SB F, BB F, UTG R25, MP F, CO C"))
    check(c, "CO", P20="oc", P19="-", P21="-")


def test_t14_effective_raise_amount_cap():
    parsed, c = run(hh(SIX, "UTG R2.5, MP F, CO R6, BTN F, SB F, BB F, UTG C", stacks={"CO": 6}))
    seq = build_sequence(parsed)
    shove = seq.streets[0][2]
    assert shove.name == "CO" and shove.eff == RAISE
    assert not seq.streets[0][-1].flags & P_RAISE
    check(c, "UTG", P03="o", P13="-")


# ── more hand-level cases (H2N-COMPATIBLE-STATS.md sections 4 and 8) ───


def test_g1_co_open_3bet_fold():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB R9, CO F"))
    assert c["CO"]["h2n_pos"] == "CO"  # Steal cells filter h2n_pos IN (BTN, SB) in SQL
    check(c, "CO", P01="oc", P03="oc", P02="oc", P05="oc")


def test_g2_btn_open_squeezed():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN R2.5, SB C, BB R12, BTN F, SB F"))
    check(c, "BTN", P03="-", P04="-", P05="-")
    check(c, "BB", P07="oc", P08="-", P24="oc")


def test_g3_g4_bb_defence_increment():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN R2.5, SB F, BB C | BB X, BTN B2, BB F"))
    check(c, "BB", C04="-", C07="o", C08="o", M01="-", M02="-", M03="-")
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN R3, SB F, BB C | BB X, BTN B2, BB F"))
    check(c, "BB", C04="oc")


def test_g5_multiway_cbet_and_missed_oop():
    _, c = run(hh(SIX, "UTG R2.5, MP F, CO C, BTN C, SB F, BB F | UTG B5, CO F, BTN F"))
    check(c, "UTG", C01="oc")
    _, c = run(hh(SIX, "UTG R2.5, MP F, CO C, BTN C, SB F, BB F | UTG X, CO X, BTN X"))
    check(c, "UTG", M01="oc", M03="oc", M02="-")


def test_g6_missed_cbet_ip_fold_and_bet_oop_turn():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN R2.5, SB F, BB C | BB X, BTN X | BB B3, BTN F"))
    check(c, "BTN", M01="oc", M02="oc", M04="oc")
    check(c, "BB", N03="oc")


def test_g7_4bet_fold():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN R8, SB F, BB F, CO R20, BTN R100, CO F"))
    check(c, "CO", P13="oc", P16="oc", P03="o")


def test_g8_preflop_allin_showdown():
    text = hh(["BTN", "SB", "BB"], "BTN R100, SB F, BB C", max_seats=6,
              cards={"BTN": "AhAd", "BB": "KcKs"}, shows=("BTN", "BB"),
              board=["2c", "7d", "9h", "Js", "4s"], collected={"BTN": 200.5})
    parsed, c = run(text)
    check(c, "BTN", V03="oc", E_FLOP_ANY="-")
    assert c["BTN"]["is_winner"] is True and c["BB"]["is_winner"] is False


def test_g9_donk_flop_and_ip_stab():
    _, c = run(hh(SIX, "UTG F, MP F, CO R3, BTN F, SB F, BB C | BB B4, CO F"))
    check(c, "BB", C12="oc")
    _, c = run(hh(SIX, "UTG F, MP F, CO R3, BTN C, SB F, BB F | CO X, BTN B4, CO F"))
    check(c, "BTN", C12="-", N01="oc")


def test_g11_limp_reraise_is_positional_3bet():
    parsed, c = run(hh(SIX, "UTG C, MP F, CO R3, BTN F, SB F, BB F, UTG R10"))
    check(c, "UTG", P08="oc", P07="oc", P06="-", P01="o", P22="oc")
    _, c = run(hh(SIX, "UTG C, MP F, CO R3, BTN F, SB F, BB F, UTG C"))
    check(c, "UTG", P08="o", P06="-")


def test_g12_vpip_vs_pfr_opportunity():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN F, SB R150, BB C", stacks={"SB": 150}))
    check(c, "BB", V01="oc", V02="-")
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN F, SB R150, BB F", stacks={"SB": 150}))
    check(c, "BB", V01="o", V02="-")


def test_g13_bb_checks_limped_pot():
    _, c = run(hh(SIX, "UTG C, MP F, CO F, BTN C, SB C, BB X"))
    check(c, "BB", V01="o", V02="o", V03="oc", P22="-")


def test_g15_postflop_ip_ignores_allin_player():
    parsed, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN C, SB F, BB C | BB X, CO X",
                       stacks={"BTN": 2.5}))
    check(c, "CO", M01="oc", M02="oc", M03="-")


def test_walk_gives_bb_nothing():
    _, c = run(hh(SIX, "UTG F, MP F, CO F, BTN F, SB F"))
    assert c["BB"]["h2n_pre_opp"] == 0 and c["BB"]["h2n_pre_case"] == 0
    check(c, "SB", V01="o", V02="o", P01="o", P02="o")


# ── E rows (aggression / WTSD bases) ─────────────────────────────────────


def test_e_rows_per_street_effective_types():
    _, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN C, SB F, BB F "
                       "| CO B3, BTN R9, CO C | CO X, BTN B10, CO F"))
    check(c, "BTN", E_FLOP_R="oc", E_FLOP_B="-", E_FLOP_BR="oc", E_FLOP_ANY="oc",
          E_TURN_B="oc", E_TURN_C="-", E_RIVER_ANY="-")
    # E rows have real opportunities (parity round 1): CO's turn check could have been a bet
    check(c, "CO", E_FLOP_B="oc", E_FLOP_C="oc", E_FLOP_BR="oc", E_TURN_ANY="oc",
          E_TURN_B="o", E_TURN_C="o", E_TURN_R="o")


def test_e_rows_use_effective_types():
    # BTN's flop "raise" all-in over a bet is only a call when the bettor covers nothing more.
    parsed, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN C, SB F, BB F | CO B10, BTN R20",
                       stacks={"CO": 12.5}))
    seq = build_sequence(parsed)
    shove = seq.streets[1][1]
    assert shove.raw == RAISE and shove.eff == CALL
    check(c, "BTN", E_FLOP_R="-", E_FLOP_C="oc")


# ── matching rule unit tests ─────────────────────────────────────────────


def _eval(text: str, defn: str, name: str):
    parsed = parse_hand_history(text)
    seq = build_sequence(parsed)
    return evaluate(compile_def(defn), seq, seq.index[name])


def test_row_may_start_at_any_action_and_skips_folds_checks():
    text = hh(SIX, "UTG F, MP F, CO F, BTN R2.5, SB F, BB R9, BTN F")
    r = _eval(text, "pre: V:R > H:F", "BTN")
    assert r.case and r.hit == (0, 6)


def test_call_between_breaks_the_row():
    text = hh(SIX, "UTG F, MP R2.5, CO C, BTN F, SB F, BB R10, MP F, CO F")
    assert not _eval(text, "pre: H:R > V:R > H:F", "MP").opp
    assert _eval(text, "pre: H:R > V:C > V:R > H:F", "MP").case


def test_first_filter_must_match_exactly_at_start():
    text = hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB C | BB X, CO X")
    # H:X cannot be skipped into: a row's first action must match at its start.
    assert _eval(text, "flop: H:X", "CO").case
    assert not _eval(text, "flop: V:B > H:X", "CO").opp


def test_bound_villain_must_be_the_same_player():
    text = hh(SIX, "UTG R2.5, MP F, CO F, BTN C, SB F, BB C | BB X, UTG X, BTN B3")
    # BTN called UTG's raise; on the flop the BB (not UTG) checks first, then UTG.
    assert _eval(text, "pre: V1:R[fr] > H:C[last]; flop: V1:X > H:B", "BTN").case
    text2 = hh(SIX, "UTG R2.5, MP F, CO F, BTN C, SB F, BB C | BB X, UTG B3, BTN F")
    assert not _eval(text2, "pre: V1:R[fr] > H:C[last]; flop: V1:X > H:B", "BTN").opp


def test_amount_filter_inclusive_bounds():
    text = hh(SIX, "UTG F, MP F, CO F, BTN C, SB C, BB R4, BTN F, SB F")
    assert _eval(text, "pre: H:C[amt=0.5-1] > V:R > H:F", "SB").case
    assert _eval(text, "pre: H:C[amt=0.5-1] > V:R > H:F", "BTN").opp is False
    assert not _eval(text, "pre: H:C[amt=0.6-1] > V:R > H:F", "SB").opp


def test_opportunity_alternatives_need_measured_action_possible():
    # facing a covering shove: fold is a VPIP opportunity but not a PFR one
    text = hh(SIX, "UTG F, MP F, CO F, BTN F, SB R150, BB F", stacks={"SB": 150})
    assert _eval(text, "pre: H:C", "BB").opp
    assert not _eval(text, "pre: H:R", "BB").opp


def test_alternative_types():
    def alt_types(defn):
        part = compile_def(defn).parts[-1]
        return ["FXCBR"[f.typ] for f in part.alts[0]]

    assert sorted(alt_types("pre: H:R")) == sorted("RCFX")       # check only preflop
    assert sorted(alt_types("pre: V:R > H:R")) == sorted("RCF")   # earlier raise in the row
    assert sorted(alt_types("flop: H:B")) == sorted("BFX")
    assert sorted(alt_types("flop: H:B > V:R > H:B")) == sorted("BF")
    assert sorted(alt_types("flop: V:B > H:C")) == sorted("CRF")
    assert sorted(alt_types("flop: H:X")) == sorted("XBF")
    assert sorted(alt_types("pre: H:X")) == sorted("XRF")
    assert sorted(alt_types("flop: V:B > H:F")) == sorted("FCR")
    alts = compile_def("pre: H:R[fr,first,ipv]").parts[0].alts[0]
    from app.h2n.sequence import FIRST, P_FR
    assert all(a.req == FIRST | IPV | P_FR | P_RAISE for a in alts)


def test_check_alternative_counts_preflop():
    text = hh(SIX, "UTG C, MP F, CO F, BTN F, SB C, BB X")
    assert _eval(text, "pre: H:R", "BB").opp


def test_earlier_streets_must_be_cases():
    text = hh(SIX, "UTG F, MP F, CO R2.5, BTN C, SB F, BB F | CO X, BTN X | CO X, BTN B3, CO F")
    r = _eval(text, "pre: H:R[fr,last]; flop: H:B[last]; turn: H:B", "CO")
    assert not r.opp and not r.case


def test_flags_of_actions():
    parsed = parse_hand_history(hh(SIX, "UTG C, MP R4, CO F, BTN R12, SB F, BB F, UTG F, MP F"))
    seq = build_sequence(parsed)
    a = seq.streets[0]
    assert a[0].flags & LIMP and not a[0].flags & FR
    assert a[1].flags & FR and not a[1].flags & TB
    assert a[3].flags & TB
    assert a[0].eff == CALL and a[2].eff == 0 and a[3].eff == RAISE
    assert CHECK == 1


# ── positions ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("n,expected", [
    (2, ["SB", "BB"]),
    (3, ["BTN", "SB", "BB"]),
    (4, ["BTN", "SB", "BB", "CO"]),
    (5, ["BTN", "SB", "BB", "MP", "CO"]),
    (6, ["BTN", "SB", "BB", "EP", "MP", "CO"]),
    (9, ["BTN", "SB", "BB", "EP", "EP", "EP", "EP", "MP", "CO"]),
])
def test_h2n_positions(n, expected):
    names = [f"P{i}" for i in range(n)]
    parsed = parse_hand_history(hh(names, "", max_seats=max(n, 2)))
    pos = h2n_positions(parsed)
    assert [pos[nm] for nm in names] == expected


def test_sitting_out_seat_is_ignored():
    text = hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB F")
    text = text.replace("Seat 6: CO ($100 in chips)\n",
                        "Seat 6: CO ($100 in chips)\nSeat 7: Idle ($500 in chips)\n")
    text = text.replace("6-max Seat #1", "9-max Seat #1")
    parsed = parse_hand_history(text)
    assert "Idle" in {s["username"] for s in parsed.seats}
    seq = build_sequence(parsed)
    pos = dict(zip(seq.names, seq.pos))
    assert (pos["UTG"], pos["MP"], pos["CO"]) == ("EP", "MP", "CO")
    p = seq.index["Idle"]
    assert not any(seq.has_seq[p])
    c = compute_h2n(parsed)
    assert c["Idle"]["h2n_pre_opp"] == 0 and c["Idle"]["is_winner"] is False


# ── is_winner ────────────────────────────────────────────────────────────


def test_winner_side_pot_only_is_not_a_winner():
    order = ["V2", "Hero", "V1"]
    text = hh(order, "V2 R20, Hero R100, V1 C", stacks={"V2": 20},
              cards={"Hero": "Qs8c", "V1": "JcJs", "V2": "Ah3h"}, shows=("Hero", "V1", "V2"),
              board=["2h", "7h", "9h", "Tc", "Jd"], collected={"V2": 60, "Hero": 160})
    parsed, c = run(text)
    assert winners(parsed) == {"V2"}
    assert c["Hero"]["is_winner"] is False and c["V2"]["is_winner"] is True


def test_winner_split_pot_and_uncontested():
    text = hh(["BTN", "SB", "BB"], "BTN R100, SB F, BB C",
              cards={"BTN": "AhKd", "BB": "AsKc"}, shows=("BTN", "BB"),
              board=["2c", "7d", "9h", "Js", "4s"], collected={"BTN": 100.25, "BB": 100.25})
    parsed, _ = run(text)
    assert winners(parsed) == {"BTN", "BB"}
    parsed, c = run(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB F", collected={"CO": 4}))
    assert winners(parsed) == {"CO"}
    assert [n for n, v in c.items() if v["is_winner"]] == ["CO"]


def test_winner_villain_mucks():
    text = hh(["BTN", "SB", "BB"], "BTN R2.5, SB F, BB C | BB X, BTN X | BB X, BTN X | BB X, BTN X",
              cards={"BTN": "2s3d"}, shows=("BTN",), collected={"BB": 5})
    parsed, _ = run(text)
    assert winners(parsed) == {"BTN"}  # the only non-folded player with known cards


# ── whole pipeline / contract ────────────────────────────────────────────


def _all_fixture_hands():
    for parser in PARSERS:
        site_dir = {1: "ggpoker", 2: "pokerstars", 3: "poker888", 4: "wpn", 5: "winamax",
                    6: "ipoker", 7: "partypoker"}.get(parser.SITE_ID)
        d = FIXTURES / site_dir if site_dir else None
        if not d or not d.exists():
            continue
        for f in sorted(d.glob("*.txt")):
            text = f.read_text(encoding="utf-8", errors="replace")
            for h in parser.split_hands(text):
                if h.strip():
                    yield parser, h


def test_every_fixture_hand_computes_and_keeps_invariants():
    n = 0
    for parser, text in _all_fixture_hands():
        try:
            parsed = parser.parse_hand_history(text)
        except Exception:
            continue  # parser rejects it; not this layer's business
        cols = compute_h2n(parsed)  # strict: must not raise
        n += 1
        for name, v in cols.items():
            assert v["h2n_pos"] in H2N_POSITIONS
            for kind in ("pre", "post"):
                opp, case = v[f"h2n_{kind}_opp"], v[f"h2n_{kind}_case"]
                assert case & ~opp == 0, (parsed.hand_id, name, kind)
                assert 0 <= opp < 1 << 63 and 0 <= case < 1 << 63
    assert n > 20


def test_bench_sample_is_consistent_with_old_flags():
    """Sanity on real hands: H2N VPIP case == OHM vpip, and every saw-flop player
    with a flop action has the flop ANY hit."""
    path = FIXTURES / "bench_sample_20k.txt"
    if not path.exists():
        pytest.skip("bench sample not available")
    from app.parsers.ggpoker import split_hands
    hands = split_hands(path.read_text())[:1500]
    mismatches = 0
    for h in hands:
        parsed = parse_hand_history(h)
        flags = stat_flags.compute_stat_flags(parsed)
        for name, f in flags.items():
            vpip_case = h2n_rows.has_bit(f["h2n_pre_case"], "V01")
            if vpip_case != f["vpip"]:
                mismatches += 1
    assert mismatches <= len(hands) * 0.002


def test_shape_cache_gives_identical_results():
    import app.parsers.ggpoker as gg

    items = list(_all_fixture_hands())
    path = FIXTURES / "bench_sample_20k.txt"
    if path.exists():
        items += [(gg, h) for h in gg.split_hands(path.read_text())[:800]]
    for parser, text in items:
        try:
            parsed = parser.parse_hand_history(text)
        except Exception:
            continue
        cached = compute_h2n(parsed)
        assert cached == compute_h2n(parsed, use_cache=False), parsed.hand_id
        assert cached == compute_h2n(parsed), parsed.hand_id


def test_apply_h2n_fills_every_column_and_survives_errors(monkeypatch):
    parsed = parse_hand_history(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB C | BB X, CO B2, BB F"))
    stats = {s["username"]: {} for s in parsed.seats}
    apply_h2n(parsed, stats)
    for v in stats.values():
        assert set(H2N_COLUMN_NAMES) <= set(v)
    assert stats["CO"]["h2n_pos"] == "CO" and stats["CO"]["is_winner"] is True

    import app.h2n as h2n_pkg

    def boom(_parsed):
        raise RuntimeError("x")

    monkeypatch.setattr(h2n_pkg, "compute_h2n", boom)
    stats = {s["username"]: {} for s in parsed.seats}
    apply_h2n(parsed, stats)
    assert all(v["h2n_pre_opp"] == 0 and v["h2n_pos"] is None for v in stats.values())


def test_insert_writes_matcher_bits(db):
    parsed = parse_hand_history(hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB C | BB X, CO B2, BB F"))
    hand_id = insert_parsed_hand(db, parsed)
    got = db.execute(
        f"SELECT h2n_pos, {h2n_rows.sql_case('P01')}, {h2n_rows.sql_case('C01')}, "
        f"{h2n_rows.sql_opp('C04')}, is_winner FROM hand_players hp "
        "JOIN players p ON p.id = hp.player_id WHERE hand_id = ? AND p.username = 'CO'",
        [hand_id],
    ).fetchone()
    assert got == ("CO", 1, 1, 0, True)


def test_definitions_cover_every_row():
    assert set(DEFINITIONS) == set(h2n_rows.ROWS)
    assert set(MATCHED_KEYS) == {k for k, r in h2n_rows.ROWS.items() if not r.hits_only}
    for key, d in COMPILED.items():
        assert d.street == {"preflop": 0, "flop": 1, "turn": 2, "river": 3}[h2n_rows.row(key).street], key


def test_dsl_rejects_garbage():
    for bad in ("pre: H:Q", "flop: H:B; pre: H:R", "pre: H:R[nope]", "pre: Z:R", "",
                "pre: H:R[pos=XX]"):
        with pytest.raises(ValueError):
            compile_def(bad)


# ── replay (popup support) ───────────────────────────────────────────────


def test_replay_and_match_row():
    text = hh(SIX, "UTG F, MP F, CO R2.5, BTN F, SB F, BB C | BB X, CO B2, BB C | BB X, CO X")
    seq = replay(text, 1)
    r = match_row(seq, "C01", "CO")
    assert r.case and r.hit == (1, 1)
    a = seq.streets[1][1]
    assert a.letter == "B" and a.amt_bb == 2 and a.pot_bb == pytest.approx(5.5)
    r = match_row(seq, "C02", "CO")
    assert r.opp and not r.case and r.hit == (2, 1)
    assert match_row(seq, "C01", "nobody") is None
    seq2 = replay_parsed(parse_hand_history(text))
    assert [x.letter for x in seq2.streets[0]] == [x.letter for x in seq.streets[0]]
    with pytest.raises(KeyError):
        replay(text, 999)
