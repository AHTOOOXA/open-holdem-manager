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


# ── 08/F3 + 06/F6: the non-unique indexes on the big tables are dropped ──

_OLD_INDEXES = {
    "idx_hands_played_at": "hands(played_at)", "idx_hands_stakes": "hands(stakes)",
    "idx_hands_game_mode": "hands(game_mode)", "idx_h_played_stakes": "hands(played_at, stakes)",
    "idx_hands_workspace": "hands(workspace_id)", "idx_hands_workspace_played": "hands(workspace_id, played_at)",
    "idx_hp_hand_id": "hand_players(hand_id)", "idx_hp_player_id": "hand_players(player_id)",
    "idx_hp_position": "hand_players(position)", "idx_hp_player_hand": "hand_players(player_id, hand_id)",
    "idx_hp_hand_player": "hand_players(hand_id, player_id)",
    "idx_hp_player_position": "hand_players(player_id, position)",
    "idx_actions_hand_id": "actions(hand_id)", "idx_board_cards_hand_id": "board_cards(hand_id)",
    "idx_hand_tags_hand_id": "hand_tags(hand_id)", "idx_hand_tags_tag": "hand_tags(tag)",
}
_BIG_TABLES = {"hands", "hand_players", "actions", "board_cards", "hand_tags"}


def _indexes(conn) -> dict[str, tuple[str, bool]]:
    return {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT index_name, table_name, is_unique FROM duckdb_indexes()").fetchall()}


def test_schema_has_only_unique_indexes_on_big_tables(db):
    idx = _indexes(db)
    assert {n for n, (t, uniq) in idx.items() if t in _BIG_TABLES and not uniq} == set()
    assert {"uq_hands_workspace_id", "uq_hand_tags", "uq_hand_notes"} <= set(idx)


def test_old_database_indexes_are_dropped_idempotently(db):
    from app.db import init_schema
    for name, target in _OLD_INDEXES.items():
        db.execute(f"CREATE INDEX {name} ON {target}")
    assert set(_OLD_INDEXES) <= set(_indexes(db))
    init_schema(db)
    idx = _indexes(db)
    assert not set(_OLD_INDEXES) & set(idx)
    assert "uq_hands_workspace_id" in idx
    init_schema(db)  # again: nothing left to drop, no error
    assert _indexes(db) == idx


# ── 06/F6: finalize recomputes only the players an import touched, same results ──

def _first_hands(n: int) -> list[str]:
    from app.parsers import ggpoker
    with open(FIXTURE_20K, encoding="utf-8") as f:
        head = f.read(n * 1600)
    return [h.strip() for h in ggpoker.split_hands(head) if h.strip()][:n]


def _player_state(db):
    players = db.execute("SELECT id, first_seen, last_seen FROM players ORDER BY id").fetchall()
    classes = db.execute("SELECT player_id, workspace_id, player_type, is_reg FROM player_classifications "
                         "ORDER BY player_id, workspace_id").fetchall()
    return players, classes


def _import(db, texts, ws):
    from app.parsers import ggpoker
    return ih.import_hand_texts(db, [(t, ggpoker) for t in texts], ws)


@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_scoped_finalize_matches_full_finalize(db, monkeypatch):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Two') ON CONFLICT DO NOTHING")
    db.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) VALUES (2, 1, 'Hero', 'manual')")
    hands = _first_hands(600)
    assert len(hands) == 600
    # Small reg thresholds so is_reg and player_type vary between players
    from app import player_classification
    real_rule = player_classification.get_reg_rule
    monkeypatch.setattr(player_classification, "get_reg_rule",
                        lambda conn: real_rule(conn).model_copy(update={"min_hands": 2, "auto_reg_hands": 6}))

    third = len(hands) // 3
    scoped_calls = []
    real_scoped = ih._update_player_types_scoped
    monkeypatch.setattr(ih, "_update_player_types_scoped",
                        lambda conn, ws: (scoped_calls.append(ws), real_scoped(conn, ws)))
    # Overlapping imports: the same players reappear across batches and workspaces
    assert _import(db, hands[:2 * third], 1)["imported"] == 2 * third
    assert _import(db, hands[third:], 2)["imported"] == len(hands) - third
    assert _import(db, hands[2 * third:], 1)["imported"] == len(hands) - 2 * third
    assert scoped_calls == [1, 2, 1]
    scoped = _player_state(db)

    # Full recompute of every workspace gives the same rows
    ih.finalize_import(db, workspace_id=1)
    ih.finalize_import(db, workspace_id=2)
    assert _player_state(db) == scoped
    assert len({r[2] for r in scoped[1]}) > 1 and len({r[3] for r in scoped[1]}) == 2

    # A workspace clear keeps first/last seen exact for players left in the other workspace
    import asyncio
    import app.db as app_db
    monkeypatch.setattr(app_db, "_conn", db)
    asyncio.run(ih.clear_hands(workspace_id=2))
    after_clear = _player_state(db)
    ih.finalize_import(db, workspace_id=1)
    assert _player_state(db)[0] == after_clear[0]


@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_scoped_finalize_picks_up_players_never_finalised(db):
    _import(db, _first_hands(50), 1)
    # A crash between commit and finalize leaves first_seen NULL and no classification
    db.execute("UPDATE players SET first_seen = NULL, last_seen = NULL")
    db.execute("DELETE FROM player_classifications")
    ih.finalize_import(db, workspace_id=1, player_ids=set())
    scoped = _player_state(db)
    ih.finalize_import(db, workspace_id=1)
    assert _player_state(db) == scoped
    assert all(r[1] is not None for r in scoped[0])


@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_import_with_pending_reg_rule_change_reclassifies_whole_workspace(db, monkeypatch):
    from app import config_sections
    hands = _first_hands(500)
    _import(db, hands[:400], 1)
    config_sections.store_rebuild_fingerprint(db)
    before = _player_state(db)[1]

    # The user edits the reg rule: 'rebuild required' until a rebuild runs
    gt = config_sections.get_value(db, "game_types")
    gt["reg_rule"].update({"min_hands": 2, "auto_reg_hands": 6})
    config_sections.put_value(db, "game_types", gt)
    assert config_sections.rebuild_required(db)

    scoped_calls = []
    monkeypatch.setattr(ih, "_update_player_types_scoped", lambda conn, ws: scoped_calls.append(ws))
    _import(db, hands[400:], 1)
    assert scoped_calls == []  # the pending change forces the whole-workspace path
    after = _player_state(db)
    ih.finalize_import(db, workspace_id=1)
    assert _player_state(db) == after
    # Players the second import did not touch were re-classified with the new rule too
    touched = {r[0] for r in db.execute(
        "SELECT DISTINCT hp.player_id FROM hand_players hp JOIN hands h ON h.id = hp.hand_id "
        "AND h.workspace_id = hp.workspace_id WHERE h.raw_text IN (SELECT UNNEST(?::VARCHAR[]))",
        [[t.replace("\x00", "") for t in hands[400:]]]).fetchall()}
    assert touched
    old = {r[0]: r for r in before if r[0] not in touched}
    assert any(old[r[0]] != r for r in after[1] if r[0] in old)


# ── 06/F10: the player cache is released when an import is done ──

@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_player_cache_released_after_stream_import(db, monkeypatch):
    import json
    import app.db as app_db
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr(app_db, "_conn", db)
    client = TestClient(app)
    hands = _first_hands(300)

    def upload(texts):
        r = client.post("/api/import/files/stream",
                        files=[("files", ("hh.txt", "\n\n".join(texts).encode(), "text/plain"))])
        return [json.loads(line) for line in r.text.splitlines() if line.strip()][-1]

    assert upload(hands[:200])["imported"] == 200
    assert ih._player_cache == {} and ih._next_player_id is None and ih._next_hp_id is None
    players = dict(db.execute("SELECT username, id FROM players").fetchall())
    max_hp = db.execute("SELECT MAX(id) FROM hand_players").fetchone()[0]
    assert upload(hands[100:])["imported"] == 100  # overlaps: 100 duplicates
    assert ih._player_cache == {}
    after = dict(db.execute("SELECT username, id FROM players").fetchall())
    assert {u: after[u] for u in players} == players  # known players keep their ids
    assert len(after) == db.execute("SELECT COUNT(DISTINCT username) FROM players").fetchone()[0]
    assert db.execute("SELECT MIN(id) FROM hand_players WHERE id > ?", [max_hp]).fetchone()[0] == max_hp + 1
    assert db.execute("SELECT COUNT(*) FROM hand_players").fetchone()[0] == \
        db.execute("SELECT COUNT(DISTINCT id) FROM hand_players").fetchone()[0]


# ── 06/F8: rebuild reads raw_text chunk by chunk, same rows as reading it all up front ──

def _rebuild_snapshot(db):
    hp = db.execute("SELECT * FROM hand_players ORDER BY id").fetchall()
    board = db.execute("SELECT * FROM board_cards ORDER BY workspace_id, hand_id, board_number, street, card_order").fetchall()
    hands = db.execute("SELECT id, workspace_id, rit_boards, is_cashout, stakes, sb_amount, bb_amount "
                       "FROM hands ORDER BY workspace_id, id").fetchall()
    return hp, board, hands, _player_state(db)


@pytest.mark.skipif(not FIXTURE_20K.exists(), reason="20k fixture missing")
def test_streamed_rebuild_matches_up_front_read(monkeypatch):
    import duckdb
    from app.db import init_schema
    from app.heroes import invalidate_hero_cache

    hands = _first_hands(2600)  # > one BATCH_SIZE chunk
    monkeypatch.setattr(ih, "BATCH_SIZE", 700)

    def fresh():
        ih.reset_import_cache()
        invalidate_hero_cache()
        conn = duckdb.connect(":memory:")
        init_schema(conn)
        conn.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Two')")
        for ws in (1, 2):
            conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
                         "VALUES (?, 1, 'Hero', 'manual')", [ws])
        # Imported out of played_at order and split over two workspaces
        _import(conn, hands[1300:], 1)
        _import(conn, hands[:1300:2], 2)
        _import(conn, hands[1:1300:2], 1)
        return conn

    def old_chunks(db, order):
        rows = db.execute(
            "SELECT id, workspace_id, site_id, raw_text FROM hands ORDER BY played_at ASC, id ASC").fetchall()
        assert len(rows) == order.num_rows
        for i in range(0, len(rows), ih.BATCH_SIZE):
            yield rows[i:i + ih.BATCH_SIZE]

    ref_db = fresh()
    with monkeypatch.context() as m:
        m.setattr(ih, "_rebuild_chunks", old_chunks)
        ih._run_rebuild_sync(ref_db)
    reference = _rebuild_snapshot(ref_db)

    new_db = fresh()
    seen = []
    real_chunks = ih._rebuild_chunks
    monkeypatch.setattr(ih, "_rebuild_chunks", lambda db, order: (seen.append(len(c)) or c for c in real_chunks(db, order)))
    ih._run_rebuild_sync(new_db)
    assert seen == [700, 700, 700, 500]
    assert _rebuild_snapshot(new_db) == reference
    assert len(reference[0]) > 2600 * 5


# ── 06/F7: uploads are split file by file and the hands released as the import consumes them ──

PS10 = Path(__file__).parent / "fixtures" / "pokerstars" / "10_multiple_hands.txt"


def _flat_chunks(flat):
    """What the pre-change code fed the import: one flat (text, parser) batch."""
    return [(len(t), p, n) for t, p, n in ih._chunks(iter([flat]), [])]


def test_drained_sources_chunk_like_one_flat_batch(monkeypatch):
    from app.parsers import ggpoker, pokerstars
    monkeypatch.setattr(ih, "BATCH_SIZE", 3)
    gg = [f"gg{i}" for i in range(8)]
    ps = [f"ps{i}" for i in range(5)]
    layout = [(ggpoker, gg[:4]), (ggpoker, gg[4:7]), (pokerstars, ps), (ggpoker, gg[7:])]
    flat = [(h, p) for p, hs in layout for h in hs]
    sources = [[p, list(hs)] for p, hs in layout]
    lists = [s[1] for s in sources]
    got = []
    for batch in iter([ih._drain(sources)]):
        for texts, parser, consumed in ih._chunks(iter([batch]), []):
            got.append((list(texts), parser, consumed))
    assert [(len(t), p, n) for t, p, n in got] == _flat_chunks(flat)
    assert [h for t, _, _ in got for h in t] == [h for h, _ in flat]
    assert sources == [None] * 4 and all(lst == [] for lst in lists)  # every reference released


def test_upload_progress_and_rows_match_flat_import(db, monkeypatch):
    import json
    import app.db as app_db
    from fastapi.testclient import TestClient
    from app.main import app
    from app.parsers import ggpoker, pokerstars
    monkeypatch.setattr(app_db, "_conn", db)
    monkeypatch.setattr(ih, "BATCH_SIZE", 4)
    client = TestClient(app)
    gg = _first_hands(9) if FIXTURE_20K.exists() else []
    ps_text = PS10.read_text()
    files = [
        ("files", ("a.txt", "\n\n".join(gg[:5]).encode(), "text/plain")),
        ("files", ("b.TXT", ps_text.encode(), "text/plain")),
        ("files", ("c.txt", b"not a hand history", "text/plain")),
        ("files", ("d.txt", ("\n\n\n".join(gg[5:]) + "\n\n").encode(), "text/plain")),
        ("files", ("e.csv", b"ignored", "text/plain")),
    ]
    r = client.post("/api/import/files/stream", files=files)
    msgs = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    ps = [h.strip() for h in pokerstars.split_hands(ps_text) if h.strip()]
    flat = [(h, ggpoker) for h in gg[:5]] + [(h, pokerstars) for h in ps] + [(h, ggpoker) for h in gg[5:]]
    assert msgs[0]["total"] == len(flat) and msgs[0]["files"] == 4
    processed = [m["processed"] for m in msgs if m["type"] == "progress"]
    sizes = [n for _, _, n in _flat_chunks(flat)]
    assert processed == [sum(sizes[:i + 1]) for i in range(len(sizes))]
    assert msgs[-1]["imported"] == len(flat) and msgs[-1]["errors"] == 0
    # Hands went in in upload order: hand_players ids follow the flat order
    order = [r[0] for r in db.execute(
        "SELECT hand_id FROM hand_players GROUP BY hand_id ORDER BY MIN(id)").fetchall()]
    parsers = {ggpoker: ggpoker, pokerstars: pokerstars}
    assert order == [parsers[p].extract_hand_id(h) for h, p in flat]


def test_stream_upload_zip_entries_and_size_limit(db, monkeypatch):
    import io
    import json
    import zipfile
    import app.db as app_db
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr(app_db, "_conn", db)
    client = TestClient(app)
    gg = _first_hands(6)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("one.txt", "\n\n".join(gg[:3]))
        zf.writestr("__MACOSX/._one.txt", "junk")
        zf.writestr("notes.md", "junk")
        zf.writestr("sub/two.TXT", "\n\n".join(gg[3:]))
    r = client.post("/api/import/files/stream", files=[
        ("files", ("hh.zip", buf.getvalue(), "application/zip")),
        ("files", ("bad.zip", b"PK not a zip", "application/zip")),
    ])
    msgs = [json.loads(line) for line in r.text.splitlines() if line.strip()]
    assert msgs[0]["files"] == 2 and msgs[0]["total"] == 6
    assert msgs[-1]["imported"] == 6
    # Same texts, same order as _read_uploads gives the non-streaming endpoint
    assert ih._read_uploads([("hh.zip", buf.getvalue())]) == ["\n\n".join(gg[:3]), "\n\n".join(gg[3:])]

    monkeypatch.setattr(ih, "MAX_UPLOAD_BYTES", 100)
    r = client.post("/api/import/files/stream", files=[
        ("files", ("a.txt", b"x" * 60, "text/plain")), ("files", ("b.txt", b"y" * 60, "text/plain"))])
    assert r.status_code == 413
