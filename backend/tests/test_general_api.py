"""WP-G: GET /api/general (H2N-style General screen aggregation).

Spec: docs/specs/H2N-COMPATIBLE-STATS.md (sections 3 and 4: cells, sample and
evaluation rules; section 7.7: hands, bb/100).
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import insert_parsed_hand
from app.general_cells import (
    GENERAL_CELL_IDS,
    GENERAL_CELLS,
    LAYOUT_CELL_IDS,
    ActionCell,
    Counts,
    ExprCell,
    StatRef,
    action_value,
    evaluate_expr,
)
from app.h2n.columns import H2N_POSITIONS
from app.h2n.rows import ROWS
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from tests.test_h2n_matcher import hh

REPO = Path(__file__).resolve().parents[2]
LAYOUT_TS = REPO / "frontend" / "src" / "lib" / "h2n-layout.ts"
TSX = REPO / "frontend" / "node_modules" / ".bin" / "tsx"

# Hero = workspace hero ("Hero" on GG). Clockwise from the button.
SIX_HERO_BB = ["V", "S", "Hero", "U", "M", "C"]


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _insert(db, *texts: str) -> None:
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))


def _general(client, **params) -> dict:
    resp = client.get("/api/general", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _cell(data: dict, cid: str) -> tuple[int | None, int | None]:
    c = data["cells"][cid]
    return c["cases"], c["opps"]


def _player_id(db, name: str) -> int:
    return db.execute("SELECT id FROM players WHERE username = ?", [name]).fetchone()[0]


# ── registry / frontend contract ─────────────────────────────────────────


def test_registry_shape():
    # 100 layout cells + Open Raise / BB and Fold to 3Bet / BB (shown by Hand2Note 4.1, blank on screen)
    assert len(GENERAL_CELL_IDS) == 102
    assert len(LAYOUT_CELL_IDS) == 100
    assert set(GENERAL_CELL_IDS) - set(LAYOUT_CELL_IDS) == {
        "preflop.open_raise.BB", "preflop.fold_to_3bet.BB"}
    for cid, cell in GENERAL_CELLS.items():
        section, _stat, _col = cid.split(".")
        assert section in ("summary", "preflop", "steal", "postflop")
        refs = [cell.ref] if isinstance(cell, ActionCell) else (
            list(cell.refs.values()) if isinstance(cell, ExprCell) else [])
        for ref in refs:
            assert ref.row in ROWS
            assert ref.positions is None or set(ref.positions) <= set(H2N_POSITIONS)
        if isinstance(cell, ActionCell):
            assert not ROWS[cell.ref.row].hits_only, cid


def test_cell_ids_match_frontend_layout(tmp_path):
    """Ids, kinds and sameAs equal frontend/src/lib/h2n-layout.ts."""
    if not LAYOUT_TS.exists() or not TSX.exists() or shutil.which("node") is None:
        pytest.skip("frontend toolchain not installed")
    script = tmp_path / "ids.ts"
    script.write_text(
        f"import {{ GENERAL_CELLS }} from {json.dumps(str(LAYOUT_TS))};\n"
        "console.log(JSON.stringify(Object.values(GENERAL_CELLS).map((c) => "
        "[c.id, c.kind, c.sameAs ?? null])));\n"
    )
    out = subprocess.run([str(TSX), str(script)], capture_output=True, text=True, timeout=120,
                         cwd=REPO / "frontend")
    assert out.returncode == 0, out.stderr
    front = [tuple(x) for x in json.loads(out.stdout.strip().splitlines()[-1])]
    back = [(c.id, c.kind, getattr(c, "same_as", None))
            for c in GENERAL_CELLS.values() if c.id in LAYOUT_CELL_IDS]
    assert back == front


# ── value rules (no DB) ──────────────────────────────────────────────────


def test_action_value_evaluation_order():
    # divide first, then multiply by 100 (H2N-COMPATIBLE-STATS.md 3.1)
    assert action_value(23, 40) == 23 / 40 * 100 == 57.49999999999999
    assert action_value(109, 200) == 54.50000000000001
    assert math.isnan(action_value(0, 0))
    assert action_value(0, 7) == 0.0


def _counts(**by_row: tuple) -> dict[StatRef, Counts]:
    return {StatRef(k): Counts(*v) for k, v in by_row.items()}


def test_four_bet_range_expression():
    cell = GENERAL_CELLS["preflop.four_bet_range.Total"]
    counts = _counts(P01=(26, 100), P13=(18, 100))
    value, sample, inputs = evaluate_expr(cell, counts)
    assert value == 26.0 * 18.0 / 100 / 100 * 100.0  # left to right, in double
    assert round(value, 2) == 4.68
    assert sample == 100
    counts = _counts(P01=(30, 400), P13=(0, 0))
    value, sample, _ = evaluate_expr(cell, counts)
    assert math.isnan(value) and sample == 400


def test_aggression_counts_hands_and_handles_zero_calls():
    cell = GENERAL_CELLS["postflop.af.Flop"]
    counts = _counts(E_FLOP_B=(7, 18), E_FLOP_R=(2, 9), E_FLOP_C=(3, 10), E_FLOP_ANY=(20, 20))
    value, sample, inputs = evaluate_expr(cell, counts)
    assert value == 3.0
    # sample = the largest opportunity count of bet, raise and call (not Any Action)
    assert sample == 18
    assert inputs == {"bet_hands": 7, "raise_hands": 2, "call_hands": 3}
    counts = _counts(E_FLOP_B=(7, 7), E_FLOP_R=(0, 0), E_FLOP_C=(0, 0), E_FLOP_ANY=(9, 9))
    assert evaluate_expr(cell, counts)[0] == math.inf
    counts = _counts(E_FLOP_B=(0, 0), E_FLOP_R=(0, 0), E_FLOP_C=(0, 0), E_FLOP_ANY=(0, 0))
    value, sample, _ = evaluate_expr(cell, counts)
    assert math.isnan(value) and sample == 0


def test_aggression_frequency_and_vs_missed_cbet():
    afq = GENERAL_CELLS["postflop.afq.River"]
    value, sample, _ = evaluate_expr(afq, _counts(E_RIVER_BR=(3, 3), E_RIVER_ANY=(8, 8)))
    assert value == 3 / 8 * 100 and sample == 8
    vmc = GENERAL_CELLS["postflop.vs_missed_cbet.Flop"]
    value, sample, inputs = evaluate_expr(vmc, _counts(N06=(5, 10), N05=(9, 30)))
    assert value == (5.0 + 9.0) / (10.0 + 30.0) * 100.0
    assert sample == 30
    assert inputs == {"a_cases": 5, "a_opps": 10, "b_cases": 9, "b_opps": 30}


def test_showdown_expressions():
    # Counts(cases, opps, wtsd, won, won_sd)
    counts = {StatRef("E_FLOP_ANY"): Counts(50, 50, 13, 21, 0),
              StatRef("V03"): Counts(80, 95, 16, 30, 9)}
    wtsd, s1, _ = evaluate_expr(GENERAL_CELLS["postflop.wtsd.Total"], counts)
    wsd, s2, _ = evaluate_expr(GENERAL_CELLS["postflop.wsd.Total"], counts)
    wwsf, s3, _ = evaluate_expr(GENERAL_CELLS["postflop.wwsf.Total"], counts)
    assert (wtsd, s1) == (13 / 50 * 100, 50)
    assert (wsd, s2) == (9 / 16 * 100, 95)  # W$SD base: any preflop action (V03), sample = its opps
    assert (wwsf, s3) == (21 / 50 * 100, 50)


# ── endpoint ─────────────────────────────────────────────────────────────


def test_empty_database(client):
    data = _general(client)
    assert data["hands"] == 0 and data["bb100"] is None
    assert set(data["cells"]) == set(GENERAL_CELL_IDS)
    assert _cell(data, "preflop.open_raise.Total") == (0, 0)
    assert data["cells"]["preflop.open_raise.Total"]["value"] is None


def _set_hero_bits(db, hand_id: str, pos: str, pre_opp=0, pre_case=0, post_opp=0, post_case=0,
                   sd=False, win=False):
    db.execute(
        "UPDATE hand_players SET h2n_pos = ?, h2n_pre_opp = ?, h2n_pre_case = ?, "
        "h2n_post_opp = ?, h2n_post_case = ?, went_to_showdown = ?, is_winner = ? "
        "WHERE hand_id = ? AND player_id = (SELECT id FROM players WHERE username = 'Hero')",
        [pos, pre_opp, pre_case, post_opp, post_case, sd, win, hand_id],
    )


def _bits(*keys: str) -> int:
    m = 0
    for k in keys:
        m |= ROWS[k].flag
    return m


def test_position_groups_and_same_as(client, db):
    """Cells add up the h2n_pos groups they cover (bits set directly)."""
    texts = [hh(SIX_HERO_BB, "U F, M F, C F, V F, S F", hand_no=i) for i in range(1, 7)]
    _insert(db, *texts)
    ids = [r[0] for r in db.execute("SELECT id FROM hands ORDER BY id").fetchall()]
    # hand: (h2n_pos, opp rows, case rows)
    plan = [
        ("EP", ("P01", "P08", "P23"), ("P01", "P08", "P23")),
        ("BTN", ("P01", "P02", "P23"), ("P02", "P23")),
        ("SB", ("P01", "P02", "P04", "P23"), ("P01", "P02", "P04")),
        ("BB", ("P01", "P23", "P11"), ("P23", "P11")),
        ("CO", ("P01", "P02"), ("P01",)),
        ("MP", ("P08",), ()),
    ]
    for hid, (pos, opps, cases) in zip(ids, plan):
        _set_hero_bits(db, hid, pos, pre_opp=_bits(*opps), pre_case=_bits(*cases))
    data = _general(client)
    assert data["hands"] == 6
    assert _cell(data, "preflop.open_raise.Total") == (3, 5)
    assert _cell(data, "preflop.open_raise.EP") == (1, 1)
    assert _cell(data, "preflop.open_raise.SB") == (1, 1)
    assert _cell(data, "preflop.open_raise.BTN") == (0, 1)
    # Steal = hero on BTN or SB only (the CO raise is not a steal)
    assert _cell(data, "steal.steal.Total") == (2, 2)
    assert _cell(data, "steal.steal.BTN") == (1, 1)
    assert _cell(data, "steal.fold_to_3bet.SB") == (1, 1)
    # Limp-Fold: every position except BB
    assert _cell(data, "preflop.limp_fold.Total") == (2, 3)
    # 3-Bet IP EP repeats the positional 3-Bet cell; BB IP = raiser in the SB, hero BB
    assert _cell(data, "preflop.three_bet_ip.EP") == _cell(data, "preflop.three_bet.EP") == (1, 1)
    assert data["cells"]["preflop.three_bet_ip.EP"]["same_as"] == "preflop.three_bet.EP"
    assert _cell(data, "preflop.three_bet.MP") == (0, 1)
    assert _cell(data, "preflop.three_bet_ip.BB") == (1, 1)
    c = data["cells"]["preflop.open_raise.Total"]
    assert c["kind"] == "action" and c["row"] == "P01"
    assert c["sample"] == 5 and c["value"] == 3 / 5 * 100


def test_showdown_and_aggression_from_bits(client, db):
    texts = [hh(SIX_HERO_BB, "U F, M F, C F, V F, S F", hand_no=i) for i in range(1, 5)]
    _insert(db, *texts)
    ids = [r[0] for r in db.execute("SELECT id FROM hands ORDER BY id").fetchall()]
    flop_any = _bits("E_FLOP_ANY")
    plan = [  # (post rows, pre rows, went to showdown, is winner)
        (("E_FLOP_ANY", "E_FLOP_B"), ("V03",), True, True),
        (("E_FLOP_ANY", "E_FLOP_C"), ("V03",), True, False),
        (("E_FLOP_ANY", "E_FLOP_B", "E_FLOP_R", "E_FLOP_BR"), ("V03",), False, True),
        ((), ("V03",), True, True),  # preflop all-in showdown: W$SD only
    ]
    for hid, (post, pre, sd, win) in zip(ids, plan):
        _set_hero_bits(db, hid, "BB", pre_opp=_bits(*pre), pre_case=_bits(*pre),
                       post_opp=_bits(*post) if post else 0,
                       post_case=_bits(*post) if post else 0, sd=sd, win=win)
    assert flop_any
    data = _general(client)
    cells = data["cells"]
    assert cells["postflop.wtsd.Total"]["value"] == 2 / 3 * 100
    assert cells["postflop.wtsd.Total"]["sample"] == 3
    assert cells["postflop.wsd.Total"]["value"] == 2 / 3 * 100  # 2 won of 3 showdowns
    assert cells["postflop.wsd.Total"]["sample"] == 4
    assert cells["postflop.wwsf.Total"]["value"] == 2 / 3 * 100
    assert cells["postflop.af.Flop"]["value"] == 3.0  # (2 bet hands + 1 raise hand) / 1 call hand
    assert cells["postflop.af.Turn"]["value"] is None  # 0 / 0
    assert cells["postflop.afq.Flop"]["value"] == 1 / 3 * 100
    assert cells["postflop.afq.Flop"]["inputs"] == {"bet_or_raise_hands": 1, "any_action_hands": 3}


def test_infinity_travels_as_string(client, db):
    _insert(db, hh(SIX_HERO_BB, "U F, M F, C F, V F, S F", hand_no=1))
    hid = db.execute("SELECT id FROM hands").fetchone()[0]
    post = _bits("E_FLOP_ANY", "E_FLOP_B", "E_FLOP_BR")
    _set_hero_bits(db, hid, "BB", post_opp=post, post_case=post)
    assert _general(client)["cells"]["postflop.af.Flop"]["value"] == "inf"


def test_hands_and_bb100(client, db):
    _insert(
        db,
        hh(SIX_HERO_BB, "U F, M F, C F, V F, S F", hand_no=1, collected={"Hero": 1.5}),  # walk
        hh(SIX_HERO_BB, "U F, M F, C F, V R2.5, S F, Hero F", hand_no=2, collected={"V": 4}),
        hh(SIX_HERO_BB, "U R3, M F, C F, V F, S F, Hero C | Hero X, U B4, Hero F", hand_no=3,
           collected={"U": 10.5}),
    )
    data = _general(client)
    assert data["hands"] == 3  # walks count
    total = float(db.execute(
        "SELECT SUM(won_bb) FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "WHERE p.username = 'Hero'").fetchone()[0])
    assert data["bb100"] == pytest.approx(total / 3 * 100.0)
    assert data["cells"]["summary.hands.Total"]["value"] == 3
    assert data["cells"]["summary.hands.Total"]["sample"] is None
    assert data["cells"]["summary.bb100.Total"]["sample"] == 3
    assert data["player"] == "Hero" and data["is_hero"] is True
    # VPIP excludes the walk (no hero decision), the fold and the call are opportunities
    assert _cell(data, "summary.vpip.Total") == (1, 2)


def test_filters(client, db):
    _insert(db, *[hh(SIX_HERO_BB, "U F, M F, C F, V R2.5, S F, Hero F", hand_no=i)
                  for i in range(1, 4)])
    db.execute("UPDATE hands SET played_at = TIMESTAMP '2026-01-15 23:59:00'")
    db.execute("UPDATE hands SET played_at = TIMESTAMP '2026-01-20 10:00:00' "
               "WHERE id = (SELECT MAX(id) FROM hands)")
    assert _general(client)["hands"] == 3
    assert _general(client, date_to="2026-01-15")["hands"] == 2
    assert _general(client, date_from="2026-01-16")["hands"] == 1
    stakes = db.execute("SELECT stakes FROM hands LIMIT 1").fetchone()[0]
    assert _general(client, stakes=stakes)["hands"] == 3
    assert _general(client, stakes="nope")["hands"] == 0
    assert _general(client, workspace_id=99)["hands"] == 0


# ── end to end through the real matcher ──────────────────────────────────


def test_heads_up_button_is_sb_column(client, db):
    """H2N-COMPATIBLE-STATS.md section 8, example 4: the heads-up button
    steals from the SB column."""
    _insert(db, hh(["Hero", "V"], "Hero R2.5, V F", max_seats=2, hand_no=1,
                   collected={"Hero": 2}))
    data = _general(client)
    assert _cell(data, "steal.steal.SB") == (1, 1)
    assert _cell(data, "steal.steal.BTN") == (0, 0)
    assert _cell(data, "steal.steal.Total") == (1, 1)
    assert _cell(data, "preflop.open_raise.SB") == (1, 1)
    assert _cell(data, "preflop.open_raise.BTN") == (0, 0)


def test_limp_fold_counts_sb_complete(client, db):
    """H2N-COMPATIBLE-STATS.md section 8, example 8: SB complete is not a
    limp, but is a Limp-Fold case."""
    _insert(db, hh(["V1", "Hero", "V2", "U", "M", "C"],
                   "U F, M F, C F, V1 C, Hero C, V2 R4, V1 F, Hero F", hand_no=1,
                   collected={"V2": 6}))
    data = _general(client)
    assert _cell(data, "preflop.limp.Total") == (0, 0)
    assert _cell(data, "preflop.limp_fold.Total") == (1, 1)


def test_vs_user_counters_for_opponents(client, db):
    _insert(
        db,
        # heads-up: V's steal is against the hero only -> vs-user
        hh(["V", "Hero"], "V R2.5, Hero F", max_seats=2, hand_no=1, collected={"V": 2}),
        # 6-max: at V's steal the SB is still in and the hero has not VPIP'd -> not vs-user
        hh(SIX_HERO_BB, "U F, M F, C F, V R2.5, S F, Hero F", hand_no=2, collected={"V": 4}),
    )
    hero = _general(client)
    assert hero["is_hero"] is True
    assert hero["cells"]["steal.steal.Total"]["vs_user"] is None

    data = _general(client, player_id=_player_id(db, "V"))
    assert data["is_hero"] is False and data["player"] == "V"
    assert data["hands"] == 2
    cell = data["cells"]["steal.steal.Total"]
    assert (cell["cases"], cell["opps"]) == (2, 2)
    assert cell["vs_user"] == {"value": 100.0, "sample": 1, "cases": 1, "opps": 1}
    assert data["cells"]["steal.steal.SB"]["vs_user"]["opps"] == 1
    assert data["cells"]["steal.steal.BTN"]["vs_user"]["opps"] == 0
    assert data["cells"]["steal.steal.BTN"]["vs_user"]["value"] is None
    # expression cells never have vs-user counters
    assert data["cells"]["postflop.wtsd.Total"]["vs_user"] is None


def test_unknown_player_404(client, db):
    _insert(db, hh(SIX_HERO_BB, "U F, M F, C F, V F, S F", hand_no=1))
    resp = client.get("/api/general", params={"player_id": 999_999})
    assert resp.status_code == 404
