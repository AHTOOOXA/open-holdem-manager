"""Matcher definitions of every General-screen row
(docs/specs/H2N-COMPATIBLE-STATS.md 2.11).

Keys are the bit keys of `app.h2n.rows`. The DSL is documented in
`app.h2n.matcher`. Hero-position restrictions of a cell (e.g. "Steal: hero on
BTN or SB") are not part of a definition: the General API applies them in SQL
through `hand_players.h2n_pos`. Position conditions on villain actions are.

E rows (hits-only per-street bases) are computed directly in
`app.h2n.compute_player_bits` from effective types; their definitions are here
too so the popup / replay code can use one entry point.
"""

from __future__ import annotations

from app.h2n.matcher import StatDef, compile_def
from app.h2n.rows import ROWS

_C01_PRE = "pre: H:R[fr,last]"
_C04_PRE = "pre: H:C[last,amt=2-]"
_N01_PRE = "pre: V1:R[fr] > H:C[last]"
_N05_PRE = "pre: V1:R > H:C[last]"
_C09_PRE = "pre: H:R[fr] > V:R > H:C[last]"
_C07_PRE = "pre: V:R[fr] > H:C[last]"

DEFINITIONS: dict[str, str] = {
    # VPIP / PFR / any preflop action (W$SD base)
    "V01": "pre: H:R | H:C",
    "V02": "pre: H:R",
    "V03": "pre: H:R | H:C | H:X",
    # Open raise (iso-raises included) and steal attempt (raise into an unopened pot)
    "P01": "pre: H:R[fr]",
    "P02": "pre: H:R[open]",
    # Fold to 3-bet
    "P03": "pre: H:R[fr] > V:R > H:F",
    "P04": "pre: H:R[open] > V:R > H:F",
    "P05": "pre: H:R[open] > V:R[pos=SB+BB] > H:F",
    # Call open raise (overcalls and limp-calls excluded)
    "P06": "pre: V:R[fr] > H:C[first]",
    # 3-bet: total (squeezes in) and positional (squeezes out)
    "P07": "pre: H:R[3b]",
    "P08": "pre: V:R[fr] > H:R",
    "P09": "pre: V:R[fr] > H:R[ipv]",
    "P10": "pre: V:R[fr] > H:R[oopv]",
    "P11": "pre: V:R[fr,pos=SB] > H:R",
    "P12": "pre: V:R[fr,pos=BTN+CO+MP+EP] > H:R",
    # 4-bet
    "P13": "pre: H:R[fr] > V:R > H:R",
    "P14": "pre: H:R[open] > V:R > H:R",
    "P15": "pre: H:R[open] > V:R[pos=SB+BB] > H:R",
    # 4-bet-fold
    "P16": "pre: H:R[fr] > V:R > H:R > V:R > H:F",
    "P17": "pre: H:R[open] > V:R > H:R > V:R > H:F",
    "P18": "pre: H:R[open] > V:R[pos=SB+BB] > H:R > V:R > H:F",
    # fold to 4-bet, call 4-bet, 5-bet
    "P19": "pre: V:R[fr] > H:R > V:R > H:F",
    "P20": "pre: H:R[3b] > V:R > H:C",
    "P21": "pre: V:R[fr] > H:R > V:R > H:R",
    # limp, limp-fold (SB completes count: increment 0.5-1 bb)
    "P22": "pre: H:C[limp]",
    "P23": "pre: H:C[first,amt=0.5-1] > V:R > H:F",
    # squeeze: first raise, 1-4 callers, hero raises
    "P24": "pre: " + " | ".join(
        "V:R[fr] > " + " > ".join(["V:C"] * k) + " > H:R" for k in range(1, 5)
    ),
    # vs steal from the button (hero SB) / from button or SB (hero BB)
    "P25F": "pre: V:R[open,pos=BTN] > H:F",
    "P25C": "pre: V:R[open,pos=BTN] > H:C",
    "P25R": "pre: V:R[open,pos=BTN] > H:R",
    "P26F": "pre: V:R[open,pos=BTN+SB] > H:F",
    "P26C": "pre: V:R[open,pos=BTN+SB] > H:C",
    "P26R": "pre: V:R[open,pos=BTN+SB] > H:R",
    # continuation bet (hero made the first raise and stayed the last aggressor)
    "C01": f"{_C01_PRE}; flop: H:B",
    "C02": f"{_C01_PRE}; flop: H:B[last]; turn: H:B",
    "C03": f"{_C01_PRE}; flop: H:B[last]; turn: H:B[last]; river: H:B",
    # fold to continuation bet (any villain's bet; preflop call increment >= 2 bb)
    "C04": f"{_C04_PRE}; flop: V:B > H:F",
    "C05": f"{_C04_PRE}; flop: V:B > H:C[last]; turn: V:B > H:F",
    "C06": f"{_C04_PRE}; flop: V:B > H:C[last]; turn: V:B > H:C[last]; river: V:B > H:F",
    # vs c-bet in a raised pot (call / raise) and in a 3-bet pot
    "C07": f"{_C07_PRE}; flop: V:B > H:C",
    "C08": f"{_C07_PRE}; flop: V:B > H:R",
    "C09": f"{_C09_PRE}; flop: V:B > H:F",
    "C10": f"{_C09_PRE}; flop: V:B > H:C",
    "C11": f"{_C09_PRE}; flop: V:B > H:R",
    # donk bets: first action, OOP to everyone left
    "C12": f"{_C04_PRE}; flop: H:B[first,oopl]",
    "C13": "pre: H:C[last]; flop: H:C[last]; turn: H:B[first,oopl]",
    "C14": "pre: H:C[last]; turn: H:C[last]; river: H:B[first,oopl]",
    # missed c-bet
    "M01": f"{_C01_PRE}; flop: H:X",
    "M02": f"{_C01_PRE}; flop: H:X[ipl]",
    "M03": f"{_C01_PRE}; flop: H:X[oopl]",
    "M04": f"{_C01_PRE}; flop: H:X[ipl]; turn: V:B > H:F[first]",
    "M05": f"{_C01_PRE}; flop: H:X[oopl] > V:B > H:F",
    # vs missed c-bet
    "N01": f"{_N01_PRE}; flop: V1:X > H:B[ipl]",
    "N02": f"{_N01_PRE}; flop: V1:X > H:X[last,ipl]; turn: V:B > H:F",
    "N03": f"{_N01_PRE}; flop: H:X[last] > V1:X; turn: H:B",
    "N04": f"{_N01_PRE}; flop: H:X[last]; turn: V:B > H:F",
    "N05": f"{_N05_PRE}; flop: V1:X > H:B[ipl]",
    "N06": f"{_N05_PRE}; flop: H:X[last] > V1:X; turn: H:B[first]",
}

_E_KINDS = {
    "B": "H:B",
    "R": "H:R",
    "C": "H:C",
    "BR": "H:B | H:R",
    "ANY": "H:B | H:R | H:C | H:X | H:F",
}
for _street in ("flop", "turn", "river"):
    for _kind, _rows in _E_KINDS.items():
        DEFINITIONS[f"E_{_street.upper()}_{_kind}"] = f"{_street}: {_rows}"

COMPILED: dict[str, StatDef] = {key: compile_def(text) for key, text in DEFINITIONS.items()}

# Matcher rows in bit order (E rows are filled directly, not through the matcher).
MATCHED_KEYS: tuple[str, ...] = tuple(k for k, r in ROWS.items() if not r.hits_only)

missing = set(ROWS) - set(COMPILED)
if missing:  # pragma: no cover - guarded by tests
    raise RuntimeError(f"rows without a matcher definition: {sorted(missing)}")
