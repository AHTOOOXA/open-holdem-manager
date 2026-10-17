"""hand_players columns owned by the H2N layer (single source of truth).

db.py adds these columns (migration), import_hands.py writes them, and
apply_h2n() fills them per player. See CONTRACT.md in this package.
"""

from __future__ import annotations

# (column name, DuckDB DDL, value the apply_h2n stub writes)
H2N_COLUMNS: tuple[tuple[str, str, object], ...] = (
    # H2N column group: EP / MP / CO / BTN / SB / BB (HU button -> SB, HU BB -> BB)
    ("h2n_pos", "VARCHAR", None),
    # Per-row bitmasks; bit indices live in app.h2n.rows
    ("h2n_pre_opp", "UBIGINT DEFAULT 0", 0),
    ("h2n_pre_case", "UBIGINT DEFAULT 0", 0),
    ("h2n_post_opp", "UBIGINT DEFAULT 0", 0),
    ("h2n_post_case", "UBIGINT DEFAULT 0", 0),
    # H2N "is winner" (showdown winner, or did not fold when there was no showdown)
    ("is_winner", "BOOLEAN DEFAULT FALSE", False),
    # Hand-value category index within the street's set; -1 = Other; NULL = unknown/not dealt
    ("hv_flop", "SMALLINT", None),
    ("hv_turn", "SMALLINT", None),
    ("hv_river", "SMALLINT", None),
    # FALSE = H2N would refuse the hand (inconsistent amounts): left out of the General screen
    ("h2n_valid", "BOOLEAN DEFAULT TRUE", True),
    # Compact copy of the hand's H2N action sequence (app.h2n.seqcodec) for the stat popup.
    # Stored once per hand, in one player's row (first player with known hole cards, else the
    # first seat); NULL in every other row.
    ("h2n_seq", "BLOB", None),
)

H2N_COLUMN_NAMES: tuple[str, ...] = tuple(c[0] for c in H2N_COLUMNS)

H2N_DEFAULTS: dict[str, object] = {c[0]: c[2] for c in H2N_COLUMNS}

# Allowed h2n_pos values, in General-screen column order.
H2N_POSITIONS: tuple[str, ...] = ("EP", "MP", "CO", "BTN", "SB", "BB")
