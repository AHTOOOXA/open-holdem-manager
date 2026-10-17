"""Cell registry of the H2N-style General screen (backend mirror of
frontend/src/lib/h2n-layout.ts).

Every grid position of the screen has a cell id `section.stat.column`
(e.g. `preflop.open_raise.EP`). The ids, kinds and `same_as` links here must
equal the frontend's GENERAL_CELLS; tests/test_general_api.py checks that.

A cell is one of:

- `ActionCell`: one matcher row (app.h2n.rows key) restricted to the hero's
  H2N column group (`hand_players.h2n_pos`). Value = cases / opps * 100,
  sample = opps.
- `ExprCell`: arithmetic over other stats (4-Bet Range, Aggression, AFq,
  vs. Missed C-Bet, WTSD, W$SD, WWSF), evaluated server-side by
  `evaluate_expr`. Sample = the largest sample among the referenced stats.
- `SummaryCell`: hands / bb/100 (computed from the hand count and winnings).

Positions: `None` = no hero-position filter. Otherwise a tuple of h2n_pos
values ("SB" already contains the heads-up button, "BB" the heads-up BB, "EP"
contains UTG1-4). `exclude=True` inverts the set (Limp-Fold: everyone but BB).

Definitions: docs/specs/H2N-COMPATIBLE-STATS.md section 4, row keys:
section 2.11.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.h2n.rows import ROWS

Positions = tuple[str, ...] | None


@dataclass(frozen=True)
class StatRef:
    """A row restricted to hero positions: the unit counters are kept for."""

    row: str
    positions: Positions = None
    exclude: bool = False

    def includes(self, pos: str | None) -> bool:
        if self.positions is None:
            return True
        inside = pos in self.positions
        return not inside if self.exclude else inside


@dataclass(frozen=True)
class ActionCell:
    id: str
    ref: StatRef
    same_as: str | None = None
    kind: str = "action"
    # Shown by Hand2Note 4.1's default General layout but blank on the reference
    # screenshot: computed by the API, not part of the screen layout.
    extra: bool = False


@dataclass(frozen=True)
class ExprCell:
    id: str
    expr: str                      # evaluator name, see evaluate_expr
    refs: dict[str, StatRef] = field(default_factory=dict)
    kind: str = "expression"


@dataclass(frozen=True)
class SummaryCell:
    id: str
    what: str                      # "hands" | "bb100"
    kind: str = "expression"


Cell = ActionCell | ExprCell | SummaryCell

_CELLS: list[Cell] = []


def _ref(row: str, positions: Positions = None, exclude: bool = False) -> StatRef:
    if row not in ROWS:
        raise KeyError(f"general_cells: unknown row {row}")
    return StatRef(row, positions, exclude)


def _action(cell_id: str, row: str, positions: Positions = None,
            exclude: bool = False, extra: bool = False) -> str:
    _CELLS.append(ActionCell(cell_id, _ref(row, positions, exclude), extra=extra))
    return cell_id


def _same_as(cell_id: str, target: str) -> str:
    ref = next(c for c in _CELLS if c.id == target)
    assert isinstance(ref, ActionCell)
    _CELLS.append(ActionCell(cell_id, ref.ref, same_as=target))
    return cell_id


def _expr(cell_id: str, expr: str, **refs: StatRef) -> str:
    _CELLS.append(ExprCell(cell_id, expr, dict(refs)))
    return cell_id


def _positional(section: str, stat: str, row_by_col: dict[str, str],
                group_positions: tuple[str, ...] | None = None) -> None:
    """One positional row. `row_by_col[col] = row key`.

    EP..BB columns filter on that h2n_pos; Total uses `group_positions`
    (None = every position).
    """
    for col, row in row_by_col.items():
        positions = group_positions if col == "Total" else (col,)
        _action(f"{section}.{stat}.{col}", row, positions)


BTN_SB = ("BTN", "SB")

# ── Summary (top line) ───────────────────────────────────────────────────
_CELLS.append(SummaryCell("summary.hands.Total", "hands"))
_CELLS.append(SummaryCell("summary.bb100.Total", "bb100"))
_action("summary.vpip.Total", "V01")
_action("summary.pfr.Total", "V02")

# ── PRE-FLOP left block ──────────────────────────────────────────────────
_positional("preflop", "open_raise", {
    "Total": "P01", "EP": "P01", "MP": "P01", "CO": "P01", "BTN": "P01", "SB": "P01",
})
_positional("preflop", "fold_to_3bet", {
    "Total": "P03", "EP": "P03", "MP": "P03", "CO": "P03", "BTN": "P03", "SB": "P03",
})
# Open Raise / BB and Fold to 3Bet / BB: Hand2Note 4.1 shows them, the
# reference screenshot leaves them blank (H2N-COMPATIBLE-STATS.md 4.2).
_action("preflop.open_raise.BB", "P01", ("BB",), extra=True)
_action("preflop.fold_to_3bet.BB", "P03", ("BB",), extra=True)
_positional("preflop", "call_open_raise", {
    "Total": "P06", "EP": "P06", "MP": "P06", "CO": "P06", "BTN": "P06", "SB": "P06", "BB": "P06",
})
# Total = built-in 3-Bet (squeezes in); positions = V:R[fr] -> H:R (squeezes out).
_positional("preflop", "three_bet", {
    "Total": "P07", "EP": "P08", "MP": "P08", "CO": "P08", "BTN": "P08", "SB": "P08", "BB": "P08",
})
_action("preflop.three_bet_ip.Total", "P09")
for _col in ("EP", "MP", "CO", "BTN"):
    _same_as(f"preflop.three_bet_ip.{_col}", f"preflop.three_bet.{_col}")
_action("preflop.three_bet_ip.BB", "P11", ("BB",))
_action("preflop.three_bet_oop.Total", "P10")
_same_as("preflop.three_bet_oop.SB", "preflop.three_bet.SB")
_action("preflop.three_bet_oop.BB", "P12", ("BB",))

# ── PRE-FLOP right list ──────────────────────────────────────────────────
_action("preflop.four_bet.Total", "P13")
_expr("preflop.four_bet_range.Total", "four_bet_range",
      open_raise=_ref("P01"), four_bet=_ref("P13"))
_action("preflop.four_bet_fold.Total", "P16")
_action("preflop.fold_to_4bet.Total", "P19")
_action("preflop.call_4bet.Total", "P20")
_action("preflop.five_bet.Total", "P21")
_action("preflop.limp.Total", "P22")
_action("preflop.limp_fold.Total", "P23", ("BB",), exclude=True)
_action("preflop.squeeze.Total", "P24")

# ── Steal / vs. Steal ────────────────────────────────────────────────────
_positional("steal", "steal", {
    "Total": "P02", "BTN": "P02", "SB": "P02",
}, BTN_SB)
_action("steal.fold_to_3bet.Total", "P05", BTN_SB)
_same_as("steal.fold_to_3bet.BTN", "preflop.fold_to_3bet.BTN")
_action("steal.fold_to_3bet.SB", "P04", ("SB",))
_action("steal.four_bet.Total", "P15", BTN_SB)
_action("steal.four_bet.BTN", "P14", ("BTN",))
_action("steal.four_bet.SB", "P14", ("SB",))
_action("steal.four_bet_fold.Total", "P18", BTN_SB)
_action("steal.four_bet_fold.BTN", "P17", ("BTN",))
_action("steal.four_bet_fold.SB", "P17", ("SB",))
_action("steal.vs_steal_fold.SB", "P25F", ("SB",))
_action("steal.vs_steal_fold.BB", "P26F", ("BB",))
_action("steal.vs_steal_call.SB", "P25C", ("SB",))
_action("steal.vs_steal_call.BB", "P26C", ("BB",))
_action("steal.vs_steal_3bet.SB", "P25R", ("SB",))
_action("steal.vs_steal_3bet.BB", "P26R", ("BB",))

# ── POSTFLOP ─────────────────────────────────────────────────────────────
_STREETS = ("Flop", "Turn", "River")


def _streets(stat: str, rows: tuple[str, str, str]) -> None:
    for col, row in zip(_STREETS, rows):
        _action(f"postflop.{stat}.{col}", row)


_streets("cbet", ("C01", "C02", "C03"))
_streets("fold_to_cbet", ("C04", "C05", "C06"))
for _col in _STREETS:
    _s = _col.upper()
    _expr(f"postflop.af.{_col}", "aggression",
          bet=_ref(f"E_{_s}_B"), raise_=_ref(f"E_{_s}_R"), call=_ref(f"E_{_s}_C"))
for _col in _STREETS:
    _s = _col.upper()
    _expr(f"postflop.afq.{_col}", "aggression_frequency",
          bet_raise=_ref(f"E_{_s}_BR"), any=_ref(f"E_{_s}_ANY"))
_streets("donk", ("C12", "C13", "C14"))
_same_as("postflop.vs_cbet_raised.Fold", "postflop.fold_to_cbet.Flop")
_action("postflop.vs_cbet_raised.Call", "C07")
_action("postflop.vs_cbet_raised.Raise", "C08")
_action("postflop.vs_cbet_3bet.Fold", "C09")
_action("postflop.vs_cbet_3bet.Call", "C10")
_action("postflop.vs_cbet_3bet.Raise", "C11")
_action("postflop.missed_cbet.Flop", "M01")
_action("postflop.missed_cbet_ip.Flop", "M02")
_action("postflop.missed_cbet_ip_fold.Turn", "M04")
_action("postflop.missed_cbet_oop.Flop", "M03")
_action("postflop.missed_cbet_oop_fold.Flop", "M05")
# (cases A + cases B) / (opps A + opps B): A = N06 (turn bet after a
# checked-through flop), B = N05 (flop stab in position); any preflop raise.
_expr("postflop.vs_missed_cbet.Flop", "vs_missed_cbet",
      a=_ref("N06"), b=_ref("N05"))
_action("postflop.vs_missed_cbet_bet_ip.Flop", "N01")
_action("postflop.vs_missed_cbet_check_fold_ip.Turn", "N02")
_action("postflop.vs_missed_cbet_bet_oop.Turn", "N03")
_action("postflop.vs_missed_cbet_check_fold_oop.Turn", "N04")
_expr("postflop.wtsd.Total", "wtsd", base=_ref("E_FLOP_ANY"))
_expr("postflop.wsd.Total", "wsd", base=_ref("V03"))
_expr("postflop.wwsf.Total", "wwsf", base=_ref("E_FLOP_ANY"))

del _col, _s

GENERAL_CELLS: dict[str, Cell] = {c.id: c for c in _CELLS}
assert len(GENERAL_CELLS) == len(_CELLS), "duplicate General cell id"
GENERAL_CELL_IDS: tuple[str, ...] = tuple(GENERAL_CELLS)
# Cells of the screen layout (frontend/src/lib/h2n-layout.ts), extras left out.
LAYOUT_CELL_IDS: tuple[str, ...] = tuple(
    cid for cid, c in GENERAL_CELLS.items() if not getattr(c, "extra", False))


def all_refs() -> list[StatRef]:
    """Every distinct (row, positions) the cells need counters for."""
    seen: dict[StatRef, None] = {}
    for c in _CELLS:
        if isinstance(c, ActionCell):
            seen[c.ref] = None
        elif isinstance(c, ExprCell):
            for r in c.refs.values():
                seen[r] = None
    return list(seen)


# ── Counters and expression evaluation ───────────────────────────────────


@dataclass
class Counts:
    """Counters of one StatRef over the filtered hands.

    `wtsd` / `won` / `won_sd`: how many of the stat's case hands went to
    showdown, were won, and were won at showdown.
    """

    cases: int = 0
    opps: int = 0
    wtsd: int = 0
    won: int = 0
    won_sd: int = 0

    def add(self, other: Counts) -> None:
        self.cases += other.cases
        self.opps += other.opps
        self.wtsd += other.wtsd
        self.won += other.won
        self.won_sd += other.won_sd


def div(a: float, b: float) -> float:
    """IEEE double division (x/0 = +-inf, 0/0 = NaN), like .NET doubles."""
    a = float(a)
    b = float(b)
    if b == 0.0:
        if a == 0.0 or math.isnan(a):
            return math.nan
        return math.copysign(math.inf, a) * math.copysign(1.0, b)
    return a / b


def action_value(cases: int, opps: int) -> float:
    """cases / opps * 100.0 in that order (H2N-COMPATIBLE-STATS.md 3.1)."""
    return div(cases, opps) * 100.0


def sample_of(counts: dict[StatRef, Counts], ref: StatRef) -> int:
    """Sample size of a referenced stat: its opportunity count.

    The per-street E rows carry real opportunity bits too (Bet Flop: hands
    where the player could bet, and so on; Any Action: opps = cases).
    """
    c = counts.get(ref)
    return c.opps if c else 0


def evaluate_expr(cell: ExprCell, counts: dict[StatRef, Counts]) -> tuple[float, int | None, dict]:
    """(value, sample, inputs) of an expression cell.

    Evaluated in double, left to right exactly as the formula is written
    (H2N-COMPATIBLE-STATS.md 2.10, 3.1 and 4).
    """
    r = cell.refs
    c = {k: counts.get(v, Counts()) for k, v in r.items()}
    samples = [sample_of(counts, v) for v in r.values()]
    sample = max(samples) if samples else None
    e = cell.expr
    if e == "four_bet_range":
        o, f = c["open_raise"], c["four_bet"]
        # open-raise cases * 4-bet cases / open-raise opps / 4-bet opps * 100
        value = div(div(float(o.cases) * float(f.cases), o.opps), f.opps) * 100.0
        sample = max(o.opps, f.opps)
        inputs = {"open_raise_cases": o.cases, "open_raise_opps": o.opps,
                  "four_bet_cases": f.cases, "four_bet_opps": f.opps}
    elif e == "aggression":
        b, rz, cl = c["bet"], c["raise_"], c["call"]
        # (bet hands + raise hands) / call hands; sample = the largest of their samples
        value = div(float(b.cases) + float(rz.cases), cl.cases)
        sample = max(sample_of(counts, r["bet"]), sample_of(counts, r["raise_"]),
                     sample_of(counts, r["call"]))
        inputs = {"bet_hands": b.cases, "raise_hands": rz.cases, "call_hands": cl.cases}
    elif e == "aggression_frequency":
        br, an = c["bet_raise"], c["any"]
        value = div(br.cases, an.cases) * 100.0
        inputs = {"bet_or_raise_hands": br.cases, "any_action_hands": an.cases}
    elif e == "vs_missed_cbet":
        a, b = c["a"], c["b"]
        sa, sb = sample_of(counts, r["a"]), sample_of(counts, r["b"])
        value = div(float(a.cases) + float(b.cases), float(sa) + float(sb)) * 100.0
        sample = max(sa, sb)
        inputs = {"a_cases": a.cases, "a_opps": sa, "b_cases": b.cases, "b_opps": sb}
    elif e == "wtsd":
        base = c["base"]
        value = div(base.wtsd, base.cases) * 100.0
        inputs = {"went_to_showdown": base.wtsd, "flop_action_hands": base.cases}
    elif e == "wsd":
        base = c["base"]
        value = div(base.won_sd, base.wtsd) * 100.0
        inputs = {"won_at_showdown": base.won_sd, "went_to_showdown": base.wtsd}
    elif e == "wwsf":
        base = c["base"]
        value = div(base.won, base.cases) * 100.0
        inputs = {"won_hands": base.won, "flop_action_hands": base.cases}
    else:  # pragma: no cover - registry and evaluator are defined together
        raise ValueError(f"unknown expression {e}")
    return value, sample, inputs
