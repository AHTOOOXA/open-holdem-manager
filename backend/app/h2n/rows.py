"""Fixed bit layout of the H2N matcher rows (placeholder table).

Every distinct action row used by the General screen gets one bit in an
opportunity mask and the same bit in the matching case mask:

    preflop rows  -> hand_players.h2n_pre_opp  / h2n_pre_case
    postflop rows -> hand_players.h2n_post_opp / h2n_post_case

The bit indices below are a contract shared by the matcher (fills the bits),
the General API (reads them in SQL) and the popup API. Never renumber an
existing row. Append new rows at the next free bit and bump STAT_VERSION.

Bit 63 is never used: masks stay below 2**63 so they pass through PyArrow's
int64 inference on insert. A mask that needs a 64th row gets a new column pair.

`notation` is our own shorthand for the row (see the row list in
docs/specs/H2N-COMPATIBLE-STATS.md section 2.11). The matcher package turns it
into real row definitions; this module only fixes keys, masks and bits.

Notation: H = the player the row is computed for, V = any other player,
V#1 = one villain bound across streets. R raise, B bet, C call, X check,
F fold. Flags in brackets. "pre ...; flop ..." = one sub-row per street,
all must match; only the last street is tested for the opportunity.
"""

from __future__ import annotations

from dataclasses import dataclass

PRE = "pre"
POST = "post"

MAX_BITS = 63  # bits 0..62 usable per mask, see module docstring


@dataclass(frozen=True)
class RowSlot:
    key: str
    mask: str          # PRE or POST
    bit: int
    street: str        # street whose decision is measured (last listed street)
    notation: str
    # E rows: per-street single-action rows filled directly from the player's
    # own actions (not through a definition); case = an action of that type,
    # opp = that type was possible (H2N-COMPATIBLE-STATS.md 2.10). Not cell rows.
    hits_only: bool = False

    @property
    def opp_column(self) -> str:
        return f"h2n_{self.mask}_opp"

    @property
    def case_column(self) -> str:
        return f"h2n_{self.mask}_case"

    @property
    def flag(self) -> int:
        return 1 << self.bit


# (key, street, notation) in bit order. Index in the list = bit index.
_PRE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("V01", "preflop", "H:R | H:C"),
    ("V02", "preflop", "H:R"),
    ("V03", "preflop", "H:R | H:C | H:X"),
    ("P01", "preflop", "H:R[first_raise]"),
    ("P02", "preflop", "H:R[opening]"),
    ("P03", "preflop", "H:R[first_raise] -> V:R -> H:F"),
    ("P04", "preflop", "H:R[opening] -> V:R -> H:F"),
    ("P05", "preflop", "H:R[opening] -> V:R[pos SB/BB(+HU)] -> H:F"),
    ("P06", "preflop", "V:R[first_raise] -> H:C[first_of_player]"),
    ("P07", "preflop", "H:R[type_3bet]"),
    ("P08", "preflop", "V:R[first_raise] -> H:R"),
    ("P09", "preflop", "V:R[first_raise] -> H:R[pos_vpip=IP]"),
    ("P10", "preflop", "V:R[first_raise] -> H:R[pos_vpip=OOP]"),
    ("P11", "preflop", "V:R[first_raise, pos SB/SB-HU] -> H:R"),
    ("P12", "preflop", "V:R[first_raise, pos BTN/CO/MP/EP(+UTG1-4)] -> H:R"),
    ("P13", "preflop", "H:R[first_raise] -> V:R -> H:R"),
    ("P14", "preflop", "H:R[opening] -> V:R -> H:R"),
    ("P15", "preflop", "H:R[opening] -> V:R[pos SB/BB(+HU)] -> H:R"),
    ("P16", "preflop", "H:R[first_raise] -> V:R -> H:R -> V:R -> H:F"),
    ("P17", "preflop", "H:R[opening] -> V:R -> H:R -> V:R -> H:F"),
    ("P18", "preflop", "H:R[opening] -> V:R[pos SB/BB(+HU)] -> H:R -> V:R -> H:F"),
    ("P19", "preflop", "V:R[first_raise] -> H:R -> V:R -> H:F"),
    ("P20", "preflop", "H:R[type_3bet] -> V:R -> H:C"),
    ("P21", "preflop", "V:R[first_raise] -> H:R -> V:R -> H:R"),
    ("P22", "preflop", "H:C[limp]"),
    ("P23", "preflop", "H:C[first_of_player, inc 0.5-1.0bb] -> V:R -> H:F"),
    ("P24", "preflop", "V:R[first_raise] -> V:C x k -> H:R, k = 1..4 (OR of 4 rows)"),
    ("P25F", "preflop", "V:R[opening, pos BTN] -> H:F"),
    ("P25C", "preflop", "V:R[opening, pos BTN] -> H:C"),
    ("P25R", "preflop", "V:R[opening, pos BTN] -> H:R"),
    ("P26F", "preflop", "V:R[opening, pos BTN/SB(+HU)] -> H:F"),
    ("P26C", "preflop", "V:R[opening, pos BTN/SB(+HU)] -> H:C"),
    ("P26R", "preflop", "V:R[opening, pos BTN/SB(+HU)] -> H:R"),
)

_C01_PRE = "pre H:R[first_raise, last]"
_C04_PRE = "pre H:C[last, inc>=2bb]"
_N01_PRE = "pre V#1:R[first_raise] -> H:C[last]"
_N05_PRE = "pre V#1:R -> H:C[last]"

_POST_ROWS: tuple[tuple[str, str, str], ...] = (
    ("C01", "flop", f"{_C01_PRE}; flop H:B"),
    ("C02", "turn", f"{_C01_PRE}; flop H:B[last]; turn H:B"),
    ("C03", "river", f"{_C01_PRE}; flop H:B[last]; turn H:B[last]; river H:B"),
    ("C04", "flop", f"{_C04_PRE}; flop V:B -> H:F"),
    ("C05", "turn", f"{_C04_PRE}; flop V:B -> H:C[last]; turn V:B -> H:F"),
    ("C06", "river", f"{_C04_PRE}; flop V:B -> H:C[last]; turn V:B -> H:C[last]; river V:B -> H:F"),
    ("C07", "flop", "pre V:R[first_raise] -> H:C[last]; flop V:B -> H:C"),
    ("C08", "flop", "pre V:R[first_raise] -> H:C[last]; flop V:B -> H:R"),
    ("C09", "flop", "pre H:R[first_raise] -> V:R -> H:C[last]; flop V:B -> H:F"),
    ("C10", "flop", "pre H:R[first_raise] -> V:R -> H:C[last]; flop V:B -> H:C"),
    ("C11", "flop", "pre H:R[first_raise] -> V:R -> H:C[last]; flop V:B -> H:R"),
    ("C12", "flop", f"{_C04_PRE}; flop H:B[first_of_player, pos_left=OOP]"),
    ("C13", "turn", "pre H:C[last]; flop H:C[last]; turn H:B[first_of_player, pos_left=OOP]"),
    ("C14", "river", "pre H:C[last]; turn H:C[last]; river H:B[first_of_player, pos_left=OOP]"),
    ("M01", "flop", f"{_C01_PRE}; flop H:X"),
    ("M02", "flop", f"{_C01_PRE}; flop H:X[pos_left=IP]"),
    ("M03", "flop", f"{_C01_PRE}; flop H:X[pos_left=OOP]"),
    ("M04", "turn", f"{_C01_PRE}; flop H:X[pos_left=IP]; turn V:B -> H:F[first_of_player]"),
    ("M05", "flop", f"{_C01_PRE}; flop H:X[pos_left=OOP] -> V:B -> H:F"),
    ("N01", "flop", f"{_N01_PRE}; flop V#1:X -> H:B[pos_left=IP]"),
    ("N02", "turn", f"{_N01_PRE}; flop V#1:X -> H:X[last, pos_left=IP]; turn V:B -> H:F"),
    ("N03", "turn", f"{_N01_PRE}; flop H:X[last] -> V#1:X; turn H:B"),
    ("N04", "turn", f"{_N01_PRE}; flop H:X[last]; turn V:B -> H:F"),
    ("N05", "flop", f"{_N05_PRE}; flop V#1:X -> H:B[pos_left=IP]"),
    ("N06", "turn", f"{_N05_PRE}; flop H:X[last] -> V#1:X; turn H:B[first_of_player]"),
)

# Per-street single-action rows (Aggression, AFq, WTSD/WWSF bases).
# Effective action types, counted per hand (at most one hit per hand); the
# opportunity bits follow H2N's single-action rule (Aggression sample).
_E_KINDS: tuple[tuple[str, str], ...] = (
    ("B", "H:B"),
    ("R", "H:R"),
    ("C", "H:C"),
    ("BR", "H:B | H:R"),
    ("ANY", "any action by H"),
)
_E_ROWS: tuple[tuple[str, str, str], ...] = tuple(
    (f"E_{street.upper()}_{kind}", street, f"{street} {notation}")
    for street in ("flop", "turn", "river")
    for kind, notation in _E_KINDS
)


def _build() -> dict[str, RowSlot]:
    rows: dict[str, RowSlot] = {}
    for bit, (key, street, notation) in enumerate(_PRE_ROWS):
        rows[key] = RowSlot(key, PRE, bit, street, notation)
    for bit, (key, street, notation) in enumerate(_POST_ROWS + _E_ROWS):
        rows[key] = RowSlot(key, POST, bit, street, notation,
                            hits_only=key.startswith("E_"))
    return rows


ROWS: dict[str, RowSlot] = _build()

PRE_ROW_KEYS: tuple[str, ...] = tuple(k for k, r in ROWS.items() if r.mask == PRE)
POST_ROW_KEYS: tuple[str, ...] = tuple(k for k, r in ROWS.items() if r.mask == POST)


def row(key: str) -> RowSlot:
    return ROWS[key]


def sql_opp(key: str, alias: str = "hp") -> str:
    """SQL expression (0/1 INTEGER) for the row's opportunity bit."""
    r = ROWS[key]
    return f"((({alias}.{r.opp_column} >> {r.bit}) & 1)::INTEGER)"


def sql_case(key: str, alias: str = "hp") -> str:
    """SQL expression (0/1 INTEGER) for the row's case bit."""
    r = ROWS[key]
    return f"((({alias}.{r.case_column} >> {r.bit}) & 1)::INTEGER)"


def has_bit(mask: int | None, key: str) -> bool:
    return bool(mask) and bool((mask >> ROWS[key].bit) & 1)


def set_bits(mask: int, *keys: str) -> int:
    """Return `mask` with the bits of `keys` set. All keys must share one mask."""
    if len({ROWS[k].mask for k in keys}) > 1:
        raise ValueError(f"rows from different masks: {keys}")
    for k in keys:
        mask |= 1 << ROWS[k].bit
    return mask
