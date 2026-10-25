"""Import pipeline performance changes keep results identical (performance/06-import-pipeline.md)."""

from types import SimpleNamespace

import app.api.import_hands as ih


def _prepared(site_id: int, names: list[str]):
    parsed = SimpleNamespace(site_id=site_id, seats=[{"username": u} for u in names])
    return (parsed, None, None)


# ── 06/F3: player ids and existing hand ids with one Arrow join ──

def _reference_lookup(db, pairs):
    """The pre-change lookup: 500-name IN lists per site."""
    out = {}
    by_site: dict[int, list[str]] = {}
    for sid, u in pairs:
        by_site.setdefault(sid, []).append(u)
    for sid, names in by_site.items():
        for i in range(0, len(names), 500):
            chunk = names[i:i + 500]
            rows = db.execute(
                f"SELECT username, id FROM players WHERE site_id = ? AND username IN ({','.join('?' * len(chunk))})",
                [sid] + chunk,
            ).fetchall()
            out.update({(sid, u): pid for u, pid in rows})
    return out


def test_resolve_players_matches_in_list_lookup(db):
    # Existing players on two sites, one name present on both sites with different ids
    db.execute("INSERT INTO sites (id, name) VALUES (2, 'Other') ON CONFLICT DO NOTHING")
    existing = [(1, f"p{i}") for i in range(1200)] + [(2, "p5"), (2, "q1"), (1, "Ünïcode ☃"), (1, "with space ")]
    db.execute("INSERT INTO players (id, site_id, username) SELECT * FROM (VALUES "
               + ",".join(f"({100 + i}, {sid}, ?)" for i, (sid, _) in enumerate(existing)) + ")",
               [u for _, u in existing])
    ih.reset_import_cache()
    ih._init_counters(db)
    first_new = ih._next_player_id
    batch = [
        _prepared(1, [f"p{i}" for i in range(0, 1200, 3)] + ["Ünïcode ☃", "with space ", "new1", "new2"]),
        _prepared(1, ["p7", "new1", "with space"]),  # "with space" (no trailing blank) is a new player
        _prepared(2, ["p5", "q1", "new1"]),  # new1 on site 2 is a different player
    ]
    ih._batch_resolve_players(db, batch)

    wanted = {(p[0].site_id, s["username"]) for p in batch for s in p[0].seats}
    ref = _reference_lookup(db, sorted(wanted))
    assert {k: ih._player_cache[k] for k in wanted} == ref
    # Existing players kept their ids; new ones got fresh consecutive ids, inserted once
    for i, pair in enumerate(existing):
        if pair in wanted:
            assert ih._player_cache[pair] == 100 + i
    new = {k: v for k, v in ref.items() if v >= first_new}
    assert set(new) == {(1, "new1"), (1, "new2"), (1, "with space"), (2, "new1")}
    assert sorted(new.values()) == list(range(first_new, first_new + 4))
    assert db.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(existing) + 4

    # A second batch resolves from the cache without touching the DB again
    ih._batch_resolve_players(db, batch)
    assert db.execute("SELECT COUNT(*) FROM players").fetchone()[0] == len(existing) + 4


def test_existing_hand_ids_join(db):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Two') ON CONFLICT DO NOTHING")
    for ws, hid in [(1, "A1"), (1, "A2"), (2, "A3"), (2, "A1")]:
        db.execute("INSERT INTO hands (id, site_id, workspace_id, played_at) VALUES (?, 1, ?, now())", [hid, ws])
    assert ih._existing_hand_ids(db, [], 1) == set()
    assert ih._existing_hand_ids(db, [None, None], 1) == set()
    assert ih._existing_hand_ids(db, ["A1", None, "A2", "A3", "A1", "Z"], 1) == {"A1", "A2"}
    assert ih._existing_hand_ids(db, ["A1", "A2", "A3"], 2) == {"A1", "A3"}


# ── 06/F2: equity memo returns bit-identical results ──

from collections import OrderedDict  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from app import equity  # noqa: E402

FIXTURE_20K = Path(__file__).parent / "fixtures" / "bench_sample_20k.txt"


class _NoMemo(OrderedDict):
    """Stands in for equity._memo: never stores, so every call computes."""

    def __setitem__(self, key, value):
        pass


def _bits(values) -> list[str]:
    return [float(v).hex() for v in values]


def _money_snapshot(parsed_hands):
    from app.money import compute_hand_money
    out = []
    for p in parsed_hands:
        hm = compute_hand_money(p, with_ev=True)
        out.append((p.hand_id, hm.ev_state, sorted(
            (u, pm.ev_results, float(pm.ev_sum).hex(), float(pm.won_ev).hex())
            for u, pm in hm.players.items()
        )))
    return out


@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_equity_memo_bit_identical_on_20k_allins(monkeypatch):
    from app.parsers import ggpoker
    text = FIXTURE_20K.read_text(encoding="utf-8")
    allins = [ggpoker.parse_hand_history(h.strip())
              for h in ggpoker.split_hands(text) if "all-in" in h]

    # Which calls are 3+-way preflop Monte Carlo (the expensive, seeded ones)?
    multiway = []
    real_compute = equity._compute

    def spy(hands, board, samples):
        if len(hands) >= 3 and not board:
            multiway.append(([tuple(h) for h in hands], list(board), samples))
        return real_compute(hands, board, samples)

    # Reference: no memo at all
    monkeypatch.setattr(equity, "_memo", _NoMemo())
    monkeypatch.setattr(equity, "_compute", spy)
    reference = _money_snapshot(allins)
    monkeypatch.setattr(equity, "_compute", real_compute)
    assert len(multiway) >= 4, "the 20k fixture has 4 hands with a 3+-way preflop all-in"

    monkeypatch.setattr(equity, "_memo", OrderedDict())
    cold = _money_snapshot(allins)   # fills the memo
    assert len(equity._memo) > 0
    warm = _money_snapshot(allins)   # every evaluation is a memo hit
    assert cold == reference
    assert warm == reference

    for hands, board, samples in multiway:
        direct = real_compute(hands, board, samples)
        assert _bits(equity.equities(hands, board, samples)) == _bits(direct)
        # A hit hands out a copy: mutating it can't poison the memo
        equity.equities(hands, board, samples)[0] = -1.0
        assert _bits(equity.equities(hands, board, samples)) == _bits(direct)


def test_equity_memo_is_keyed_on_order_board_and_samples(monkeypatch):
    monkeypatch.setattr(equity, "_memo", OrderedDict())
    a, b, c = ("Ah", "Kd"), ("Qs", "Qc"), ("7h", "6h")
    e1 = equity.equities([a, b, c], [], samples=2000)
    e2 = equity.equities([c, a, b], [], samples=2000)
    assert _bits(e1) == _bits(equity._compute([a, b, c], [], 2000))
    assert _bits(e2) == _bits(equity._compute([c, a, b], [], 2000))
    assert _bits(equity.equities([a, b, c], [], samples=1000)) == _bits(equity._compute([a, b, c], [], 1000))
    flop = ["2c", "9d", "Ts"]
    assert _bits(equity.equities([a, b], flop)) == _bits(equity._compute([a, b], flop, equity.MULTIWAY_PREFLOP_SAMPLES))
    assert len(equity._memo) == 4
    monkeypatch.setattr(equity, "_MEMO_MAX", 2)
    equity.equities([a, c], flop)
    assert len(equity._memo) == 2
