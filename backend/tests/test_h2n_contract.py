"""WP-A: H2N columns, bit layout and the apply_h2n hook (app/h2n/CONTRACT.md)."""

from pathlib import Path

import duckdb
import pytest

import app.stat_flags as stat_flags
from app.api.import_hands import _STAT_FLAG_KEYS, insert_parsed_hand
import app.db as app_db
from app.db import init_schema
from app.h2n import rows as h2n_rows
from app.h2n.columns import H2N_COLUMN_NAMES, H2N_COLUMNS, H2N_DEFAULTS
from app.parsers.ggpoker import parse_hand_history

FIXTURE = Path(__file__).parent / "fixtures" / "ggpoker" / "sample.txt"

EXPECTED_TYPES = {
    "h2n_pos": "VARCHAR",
    "h2n_pre_opp": "UBIGINT",
    "h2n_pre_case": "UBIGINT",
    "h2n_post_opp": "UBIGINT",
    "h2n_post_case": "UBIGINT",
    "is_winner": "BOOLEAN",
    "hv_flop": "SMALLINT",
    "hv_turn": "SMALLINT",
    "hv_river": "SMALLINT",
    "h2n_valid": "BOOLEAN",
    "h2n_seq": "BLOB",
}


def _first_hand() -> str:
    text = FIXTURE.read_text(encoding="utf-8")
    return "Poker Hand #" + text.split("Poker Hand #")[1]


def _hp_types(conn) -> dict[str, str]:
    return dict(conn.execute(
        "SELECT column_name, data_type FROM duckdb_columns() "
        "WHERE table_name = 'hand_players'"
    ).fetchall())


# ── schema ───────────────────────────────────────────────────────────────


def test_columns_exist_with_types(db):
    types = _hp_types(db)
    for col, typ in EXPECTED_TYPES.items():
        assert types.get(col) == typ, col
    assert set(H2N_COLUMN_NAMES) == set(EXPECTED_TYPES)


def test_migration_adds_columns_to_old_db(monkeypatch):
    conn = duckdb.connect(":memory:")
    with monkeypatch.context() as m:  # a pre-v6 database: schema without the H2N columns
        m.setattr(app_db, "H2N_COLUMNS", ())
        init_schema(conn)
    assert not set(H2N_COLUMN_NAMES) & set(_hp_types(conn))
    init_schema(conn)  # next startup migrates it
    types = _hp_types(conn)
    for col, typ in EXPECTED_TYPES.items():
        assert types.get(col) == typ, col
    conn.close()


def test_import_writes_every_h2n_column():
    assert set(H2N_COLUMN_NAMES) <= set(_STAT_FLAG_KEYS)


# ── hook ─────────────────────────────────────────────────────────────────


def test_compute_stat_flags_fills_every_column():
    # Was a stub-defaults check (WP-A); the matcher (WP-M) now fills real values.
    parsed = parse_hand_history(_first_hand())
    flags = stat_flags.compute_stat_flags(parsed)
    assert len(flags) == len(parsed.seats)
    for ps in flags.values():
        for col in H2N_DEFAULTS:
            assert col in ps
        assert ps["h2n_pos"] in ("EP", "MP", "CO", "BTN", "SB", "BB")
        for kind in ("pre", "post"):
            assert ps[f"h2n_{kind}_case"] & ~ps[f"h2n_{kind}_opp"] == 0
        assert isinstance(ps["is_winner"], bool)


def test_insert_writes_h2n_columns(db):
    parsed = parse_hand_history(_first_hand())
    flags = stat_flags.compute_stat_flags(parsed)
    hand_id = insert_parsed_hand(db, parsed)
    rows = db.execute(
        "SELECT p.username, h2n_pos, h2n_pre_opp, h2n_pre_case, h2n_post_opp, h2n_post_case, "
        "is_winner FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE hand_id = ?",
        [hand_id],
    ).fetchall()
    assert len(rows) == len(parsed.seats)
    for name, *cols in rows:
        f = flags[name]
        assert tuple(cols) == (f["h2n_pos"], f["h2n_pre_opp"], f["h2n_pre_case"],
                               f["h2n_post_opp"], f["h2n_post_case"], f["is_winner"])


def test_full_masks_round_trip_and_sql_helpers(db, monkeypatch):
    """Every usable bit survives the PyArrow insert and the SQL bit helpers."""
    full = (1 << h2n_rows.MAX_BITS) - 1

    def fake_apply(parsed, player_stats):
        for i, ps in enumerate(player_stats.values()):
            ps.update(H2N_DEFAULTS)
            if i == 0:
                ps.update(h2n_pos="SB", h2n_pre_opp=full, h2n_pre_case=full,
                          h2n_post_opp=full, h2n_post_case=full,
                          is_winner=True, hv_flop=3, hv_turn=-1, hv_river=10)
            else:
                ps.update(h2n_pos="BB",
                          h2n_pre_opp=h2n_rows.set_bits(0, "P01", "P26R"),
                          h2n_pre_case=h2n_rows.set_bits(0, "P26R"))

    monkeypatch.setattr(stat_flags, "apply_h2n", fake_apply)
    hand_id = insert_parsed_hand(db, parse_hand_history(_first_hand()))

    got = db.execute(
        "SELECT h2n_pos, h2n_pre_case, h2n_post_case, is_winner, hv_flop, hv_turn, hv_river "
        "FROM hand_players WHERE h2n_pos = 'SB' AND hand_id = ?", [hand_id],
    ).fetchone()
    assert got == ("SB", full, full, True, 3, -1, 10)

    exprs = ", ".join(
        f"SUM({h2n_rows.sql_opp(k)}), SUM({h2n_rows.sql_case(k)})"
        for k in ("V01", "P01", "P26R", "C01", "N06", "E_RIVER_ANY")
    )
    sums = db.execute(
        f"SELECT {exprs} FROM hand_players hp WHERE hand_id = ?", [hand_id]
    ).fetchone()
    n = db.execute("SELECT COUNT(*) FROM hand_players WHERE hand_id = ?", [hand_id]).fetchone()[0]
    assert n >= 2
    # opp/case sums: V01, P01, P26R, C01, N06, E_RIVER_ANY
    assert sums == (1, 1, n, 1, n, n, 1, 1, 1, 1, 1, 1)


# ── bit layout ───────────────────────────────────────────────────────────

SPEC_PRE_KEYS = (
    ["V01", "V02", "V03"]
    + [f"P{i:02d}" for i in range(1, 25)]
    + ["P25F", "P25C", "P25R", "P26F", "P26C", "P26R"]
)
SPEC_POST_KEYS = (
    [f"C{i:02d}" for i in range(1, 15)]
    + [f"M{i:02d}" for i in range(1, 6)]
    + [f"N{i:02d}" for i in range(1, 7)]
)


def test_every_spec_row_has_a_slot():
    assert list(h2n_rows.PRE_ROW_KEYS) == SPEC_PRE_KEYS
    assert list(h2n_rows.POST_ROW_KEYS[:len(SPEC_POST_KEYS)]) == SPEC_POST_KEYS
    assert len(SPEC_PRE_KEYS) + len(SPEC_POST_KEYS) == 58
    e_rows = [k for k in h2n_rows.POST_ROW_KEYS if k.startswith("E_")]
    assert len(e_rows) == 15
    assert all(h2n_rows.row(k).hits_only for k in e_rows)


@pytest.mark.parametrize("mask", [h2n_rows.PRE, h2n_rows.POST])
def test_bits_are_contiguous_and_below_63(mask):
    bits = [r.bit for r in h2n_rows.ROWS.values() if r.mask == mask]
    assert bits == list(range(len(bits)))
    assert max(bits) < h2n_rows.MAX_BITS == 63


def test_row_columns_and_streets():
    r = h2n_rows.row("C02")
    assert (r.opp_column, r.case_column, r.street) == ("h2n_post_opp", "h2n_post_case", "turn")
    assert h2n_rows.row("P07").case_column == "h2n_pre_case"
    assert all(h2n_rows.row(k).street == "preflop" for k in h2n_rows.PRE_ROW_KEYS)
    assert {h2n_rows.row(k).street for k in h2n_rows.POST_ROW_KEYS} == {"flop", "turn", "river"}
    valid_columns = {c[0] for c in H2N_COLUMNS}
    for r in h2n_rows.ROWS.values():
        assert r.opp_column in valid_columns and r.case_column in valid_columns


def test_bit_helpers():
    m = h2n_rows.set_bits(0, "V01", "P26R")
    assert m == 1 | (1 << 32)
    assert h2n_rows.has_bit(m, "P26R") and not h2n_rows.has_bit(m, "V02")
    assert not h2n_rows.has_bit(None, "V01")
    with pytest.raises(ValueError):
        h2n_rows.set_bits(0, "V01", "C01")
