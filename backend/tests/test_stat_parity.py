"""Stats page = drill-down = H2N General screen.

- Drill-down counts must match the headline stats (BUGS-FROM-FORK.md #17):
  the stat detail page (stat_registry.py) and the stats page
  (stats_engine.py) define each stat separately; this checks every stat both
  of them define.
- Every Stats page number with an H2N twin must equal the General screen
  cell (api/general.py) on the same hands (WP-L).
"""

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import _process_hands
from app.main import app
from app.stat_registry import OHM_ONLY_STATS, STAT_REGISTRY

FIXTURES = Path(__file__).parent / "fixtures"
N_HANDS = 4000

# Expressions: the headline is a ratio the hand list can't reproduce.
# Aggression = bet+raise hands per call hand; 4-Bet Range = Open% x 4-Bet%;
# vs. Missed C-Bet = (cases(A) + cases(B)) / (opps(A) + opps(B)) with
# sample max(opps(A), opps(B)).
NOT_COMPARABLE = {"af_flop", "af_turn", "af_river", "four_bet_range", "vs_missed_cbet"}


@pytest.fixture(scope="module")
def loaded():
    import duckdb
    from app.api.import_hands import reset_import_cache
    from app.db import init_schema

    reset_import_cache()
    db = duckdb.connect(":memory:")
    init_schema(db)
    text = (FIXTURES / "bench_sample_20k.txt").read_text()
    hands = text.split("\n\n\n")[:N_HANDS]
    _process_hands(db, ["\n\n\n".join(hands)])
    original = app_db._conn
    app_db._conn = db
    yield db, TestClient(app)
    app_db._conn = original
    db.close()


@pytest.fixture(scope="module")
def client(loaded):
    return loaded[1]


@pytest.fixture(scope="module")
def hero_stats(client):
    return client.get("/api/stats/hero").json()


def _headline(stats: dict, key: str) -> dict | None:
    """StatValue for key from /stats/hero (the total for positional stats)."""
    v = stats.get(key)
    if isinstance(v, dict) and "total" in v:
        v = v["total"]
    if isinstance(v, dict) and "sample" in v:
        return v
    return None


def _drill(client, key: str, **params) -> dict:
    resp = client.get(f"/api/stats/detail/{key}/hands", params={"per_page": 1, **params})
    assert resp.status_code == 200, (key, resp.text)
    return resp.json()


def test_hands_leave_out_what_h2n_refuses(loaded, hero_stats):
    """H2N doesn't import hands with inconsistent amounts (h2n_valid FALSE);
    the stats page leaves them out like the General screen does."""
    db, _ = loaded
    from app.db import get_hero_player_id

    hero = get_hero_player_id(db, 1)
    valid, invalid = db.execute(
        "SELECT COUNT(*) FILTER (WHERE COALESCE(h2n_valid, TRUE)), "
        "COUNT(*) FILTER (WHERE NOT COALESCE(h2n_valid, TRUE)) "
        "FROM hand_players WHERE player_id = ?", [hero]).fetchone()
    assert valid + invalid == N_HANDS
    assert hero_stats["hands"] == valid


def test_drilldown_matches_headline_stats(client, hero_stats):
    compared, mismatches = [], []
    for key in STAT_REGISTRY:
        if key in NOT_COMPARABLE:
            continue
        head = _headline(hero_stats, key)
        if head is None:
            continue
        d = _drill(client, key)
        compared.append(key)
        pct = round(d["action_count"] / d["opportunity_count"] * 100, 1) if d["opportunity_count"] else None
        if d["opportunity_count"] != head["sample"] or pct != head["value"]:
            mismatches.append((key, f"detail {d['action_count']}/{d['opportunity_count']}",
                               f"stats {head['value']}% of {head['sample']}"))

    assert len(compared) > 30
    assert mismatches == []


def test_bet_after_aggressor_checks_is_not_a_donk():
    """The preflop raiser checks the flop and the caller bets: that's a bet vs a
    missed c-bet, not a donk bet (a donk leads before the aggressor acts)."""
    from app.parsers.ggpoker import parse_hand_history
    from app.stat_flags import compute_stat_flags
    from tests.test_positions import NINE_MAX_HAND

    flags = compute_stat_flags(parse_hand_history(NINE_MAX_HAND))
    assert flags["P4"]["missed_cbet_flop"] is True
    assert flags["P5"]["donk_bet_flop"] is not True
    assert flags["P5"]["donk_bet_flop_opp"] is False


# (HeroStats field, column, drill key) exactly as StatsCard.tsx wires the
# steal table: some columns are a different H2N stat than the Total.
STEAL_CELLS = [
    ("steal", "total", "steal"), ("steal", "btn", "steal"), ("steal", "sb", "steal"),
    ("fold_to_3bet_steal", "total", "fold_to_3bet_steal"),
    ("fold_to_3bet_steal", "btn", "fold_to_3bet"),
    ("fold_to_3bet_steal", "sb", "fold_to_3bet_open"),
    ("four_bet_steal", "total", "four_bet_steal"),
    ("four_bet_steal", "btn", "four_bet_open"),
    ("four_bet_steal", "sb", "four_bet_open"),
    ("four_bet_fold_steal", "total", "four_bet_fold_steal"),
    ("four_bet_fold_steal", "btn", "four_bet_fold_open"),
    ("four_bet_fold_steal", "sb", "four_bet_fold_open"),
    ("vs_steal_fold", "sb", "fold_to_steal"), ("vs_steal_fold", "bb", "fold_to_steal"),
    ("vs_steal_call", "sb", "call_steal"), ("vs_steal_call", "bb", "call_steal"),
    ("vs_steal_3bet", "sb", "three_bet_vs_steal"), ("vs_steal_3bet", "bb", "three_bet_vs_steal"),
    # 3-Bet row: Total = built-in 3-Bet, positions = 3-bet of the opener's raise
    ("three_bet", "total", "three_bet"),
    *[("three_bet", p, "three_bet_vs_open") for p in ("ep", "mp", "co", "btn", "sb", "bb")],
]


@pytest.mark.parametrize("field,col,drill", STEAL_CELLS)
def test_table_cells_match_their_drilldown(client, hero_stats, field, col, drill):
    """Each cell drills into a stat with the same counts."""
    head = hero_stats[field][col]
    params = {} if col == "total" else {"position": col.upper()}
    d = _drill(client, drill, **params)
    assert d["opportunity_count"] == head["sample"]
    if d["opportunity_count"]:
        assert round(d["action_count"] / d["opportunity_count"] * 100, 1) == head["value"]


def test_steal_has_no_co_column(hero_stats):
    """H2N steals are from BTN and SB only."""
    for field in ("steal", "fold_to_3bet_steal", "four_bet_steal", "four_bet_fold_steal"):
        assert hero_stats[field]["co"] == {"value": None, "sample": 0}
        assert hero_stats[field]["ep"]["sample"] == 0
    total = hero_stats["steal"]["total"]["sample"]
    assert total == hero_stats["steal"]["btn"]["sample"] + hero_stats["steal"]["sb"]["sample"]
    assert total > 0


# ── Stats page == General screen ─────────────────────────────────────────

_COLS = {"total": "Total", "ep": "EP", "mp": "MP", "co": "CO", "btn": "BTN", "sb": "SB", "bb": "BB"}
_ALL = tuple(_COLS)

# HeroStats field -> (General stat id prefix, columns on the General screen)
_POSITIONAL = {
    "open_raise": ("preflop.open_raise", _ALL),
    "fold_to_3bet": ("preflop.fold_to_3bet", _ALL),
    "call_open_raise": ("preflop.call_open_raise", _ALL),
    "three_bet": ("preflop.three_bet", _ALL),
    "three_bet_ip": ("preflop.three_bet_ip", ("total", "ep", "mp", "co", "btn", "bb")),
    "three_bet_oop": ("preflop.three_bet_oop", ("total", "sb", "bb")),
    "steal": ("steal.steal", ("total", "btn", "sb")),
    "fold_to_3bet_steal": ("steal.fold_to_3bet", ("total", "btn", "sb")),
    "four_bet_steal": ("steal.four_bet", ("total", "btn", "sb")),
    "four_bet_fold_steal": ("steal.four_bet_fold", ("total", "btn", "sb")),
    "vs_steal_fold": ("steal.vs_steal_fold", ("sb", "bb")),
    "vs_steal_call": ("steal.vs_steal_call", ("sb", "bb")),
    "vs_steal_3bet": ("steal.vs_steal_3bet", ("sb", "bb")),
}

# HeroStats field (total for positional ones) -> General cell id
_SINGLE = {
    "vpip": "summary.vpip.Total",
    "pfr": "summary.pfr.Total",
    "four_bet": "preflop.four_bet.Total",
    "four_bet_range": "preflop.four_bet_range.Total",
    "four_bet_fold": "preflop.four_bet_fold.Total",
    "fold_to_4bet": "preflop.fold_to_4bet.Total",
    "call_4bet": "preflop.call_4bet.Total",
    "five_bet": "preflop.five_bet.Total",
    "limp": "preflop.limp.Total",
    "limp_fold": "preflop.limp_fold.Total",
    "squeeze": "preflop.squeeze.Total",
    "cbet_flop": "postflop.cbet.Flop",
    "cbet_turn": "postflop.cbet.Turn",
    "cbet_river": "postflop.cbet.River",
    "fold_to_cbet_flop": "postflop.fold_to_cbet.Flop",
    "fold_to_cbet_turn": "postflop.fold_to_cbet.Turn",
    "fold_to_cbet_river": "postflop.fold_to_cbet.River",
    "af_flop": "postflop.af.Flop",
    "af_turn": "postflop.af.Turn",
    "af_river": "postflop.af.River",
    "afq_flop": "postflop.afq.Flop",
    "afq_turn": "postflop.afq.Turn",
    "afq_river": "postflop.afq.River",
    "donk_bet_flop": "postflop.donk.Flop",
    "donk_bet_turn": "postflop.donk.Turn",
    "donk_bet_river": "postflop.donk.River",
    "fold_cbet_flop_raised": "postflop.vs_cbet_raised.Fold",
    "call_cbet_flop_raised": "postflop.vs_cbet_raised.Call",
    "raise_cbet_flop_raised": "postflop.vs_cbet_raised.Raise",
    "fold_cbet_flop_3bet": "postflop.vs_cbet_3bet.Fold",
    "call_cbet_flop_3bet": "postflop.vs_cbet_3bet.Call",
    "raise_cbet_flop_3bet": "postflop.vs_cbet_3bet.Raise",
    "missed_cbet_flop": "postflop.missed_cbet.Flop",
    "missed_cbet_flop_ip": "postflop.missed_cbet_ip.Flop",
    "missed_cbet_fold_ip": "postflop.missed_cbet_ip_fold.Turn",
    "missed_cbet_flop_oop": "postflop.missed_cbet_oop.Flop",
    "missed_cbet_fold_oop": "postflop.missed_cbet_oop_fold.Flop",
    "vs_missed_cbet": "postflop.vs_missed_cbet.Flop",
    "vs_missed_cbet_bet_ip": "postflop.vs_missed_cbet_bet_ip.Flop",
    "vs_missed_cbet_check_fold_ip": "postflop.vs_missed_cbet_check_fold_ip.Turn",
    "vs_missed_cbet_bet_oop_turn": "postflop.vs_missed_cbet_bet_oop.Turn",
    "vs_missed_cbet_check_fold_oop": "postflop.vs_missed_cbet_check_fold_oop.Turn",
    "wtsd": "postflop.wtsd.Total",
    "wsd": "postflop.wsd.Total",
    "wwsf": "postflop.wwsf.Total",
}

# The stats page shows the W$SD denominator (showdowns) as its sample; H2N's
# sample of that expression is its base stat's opportunity count.
_SAMPLE_DIFFERS = {"wsd"}
# HeroStats fields that have no General twin and stay on OHM flags.
_NO_TWIN = {"bb_defense", "iso_raise", "fold_to_squeeze", "missed_cbet_turn"}


def _general_value(cell: dict, decimals: int) -> float | None:
    v = cell["value"]
    if v is None or isinstance(v, str) or (isinstance(v, float) and math.isnan(v)):
        return None  # NaN / infinity: the stats page shows nothing
    return round(v, decimals)


def _pairs():
    for field, (prefix, cols) in _POSITIONAL.items():
        for col in cols:
            yield field, col, f"{prefix}.{_COLS[col]}"
    for field, cid in _SINGLE.items():
        yield field, None, cid


def test_every_h2n_stat_is_mapped(hero_stats):
    """Every HeroStats stat either has a General twin above or is listed as OHM-only."""
    from app.stats_engine import NON_H2N_FIELDS

    fields = {k for k, v in hero_stats.items() if isinstance(v, dict)}
    mapped = set(_POSITIONAL) | set(_SINGLE)
    assert set(NON_H2N_FIELDS) == _NO_TWIN
    assert fields - mapped == _NO_TWIN
    assert {"bb_defense", "iso_raise", "fold_to_squeeze"} <= OHM_ONLY_STATS


def test_stats_page_equals_general_screen(loaded, hero_stats):
    db, client = loaded
    general = client.get("/api/general").json()
    assert general["hands"] == hero_stats["hands"]
    assert round(general["bb100"], 2) == hero_stats["win_rate_bb100"]

    compared, mismatches = 0, []
    for field, col, cid in _pairs():
        sv = hero_stats[field]
        if col is not None or "total" in sv:
            sv = sv[col or "total"]
        cell = general["cells"][cid]
        decimals = 2 if field.startswith("af_") else 1
        want_value = _general_value(cell, decimals)
        want_sample = cell["sample"]
        compared += 1
        if sv["value"] != want_value or (field not in _SAMPLE_DIFFERS and sv["sample"] != want_sample):
            mismatches.append((field, col, cid, sv, (want_value, want_sample)))
    assert compared > 80
    assert mismatches == []


def test_positional_cells_equal_general_by_position(hero_stats):
    """Columns of rows that the General screen only shows as a Total (4-Bet,
    Fold to 4-Bet, Limp, C-Bet, ...) are the same row restricted to the hero's
    H2N position, so the columns add up to the Total."""
    for field in ("vpip", "pfr", "four_bet", "fold_to_4bet", "limp", "cbet_flop",
                  "fold_to_cbet_flop", "open_raise", "fold_to_3bet", "call_open_raise"):
        ps = hero_stats[field]
        assert ps["total"]["sample"] == sum(ps[c]["sample"] for c in _ALL if c != "total"), field
