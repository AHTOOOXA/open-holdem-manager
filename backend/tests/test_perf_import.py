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
