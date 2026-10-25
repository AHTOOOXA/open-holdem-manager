"""Incremental Reports extension: review fixes (perf/incremental, round 2).

- the extension's `h.rowid > watermark` needs hands.rowid to only grow between resets; DuckDB
  renumbers rows when a checkpoint vacuums deleted row groups, which it skips on tables with
  an index. `hands` keeps uq_hands_workspace_id, and `_rowids_kept` detects a renumbering
  anyway, so the resolve recomputes instead of missing appended hands;
- the extension streams the Bet Sizing hits while each hand is decoded (no sequence kept).
"""

from __future__ import annotations

import json

import duckdb

from app import data_generation as dg
from app.db import init_schema
from app.reports import chain as chain_mod
from app.reports import split as split_mod
from tests.test_perf_incremental import FIRST, _import, _post, hands, live  # noqa: F401


def test_hands_keeps_its_unique_index():
    """Without an index DuckDB may vacuum (renumber) `hands` rows at a checkpoint."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    names = {r[0] for r in conn.execute(
        "SELECT index_name FROM duckdb_indexes() WHERE table_name = 'hands'").fetchall()}
    assert "uq_hands_workspace_id" in names
    conn.close()


def _vacuum_scenario(path, index: bool) -> bool:
    """Snapshot after a big delete, then append and checkpoint: are the rowids kept?"""
    db = duckdb.connect(str(path))
    db.execute("CREATE TABLE hands (id VARCHAR, workspace_id INTEGER)")
    if index:
        db.execute("CREATE UNIQUE INDEX uq_hands_workspace_id ON hands(workspace_id, id)")
    db.execute("INSERT INTO hands SELECT 'w2_' || i, 2 FROM range(130000) t(i)")
    db.execute("INSERT INTO hands SELECT 'w1_' || i, 1 FROM range(6000) t(i)")
    db.execute("CHECKPOINT")
    db.execute("DELETE FROM hands WHERE workspace_id = 2")
    snap = chain_mod._rowid_snapshot(db)
    assert chain_mod._rowids_kept(db, snap)
    db.execute("INSERT INTO hands SELECT 'new_' || i, 1 FROM range(100) t(i)")
    db.execute("CHECKPOINT")
    moved = db.execute("SELECT COUNT(*) FROM hands WHERE id LIKE 'new_%' AND rowid <= ?",
                       [snap[0]]).fetchone()[0]
    kept = chain_mod._rowids_kept(db, snap)
    db.close()
    assert kept == (moved == 0)
    return kept


def test_rowid_guard_detects_a_renumbering_vacuum(tmp_path):
    assert not _vacuum_scenario(tmp_path / "noindex.duckdb", index=False)
    assert _vacuum_scenario(tmp_path / "index.duckdb", index=True)


def test_moved_rowids_recompute_instead_of_extending(live, hands, monkeypatch):
    conn, client = live
    spot = [{"k": "row", "key": "P01"}]
    plain = [{"k": "pos", "v": ["BB", "SB"]}]
    for ch in (spot, plain):
        _post(client, "spot", {"chain": ch})
        _post(client, "split", {"chain": ch, "type": "next_actions"})
    monkeypatch.setattr(chain_mod, "_rowids_kept", lambda db, snap: False)
    computes = []
    real = chain_mod._compute
    monkeypatch.setattr(chain_mod, "_compute", lambda db, ws, p, ch, ds=0: (
        computes.append(chain_mod.canonical(ch)), real(db, ws, p, ch, ds))[1])
    _import(conn, hands[FIRST:FIRST + 200])
    warm = {json.dumps(ch): (_post(client, "spot", {"chain": ch}),
                             _post(client, "split", {"chain": ch, "type": "next_actions"}))
            for ch in (spot, plain)}
    key_spot, key_plain = (chain_mod.canonical(chain_mod.CHAIN.validate_python(c))
                           for c in (spot, plain))
    assert computes.count(key_spot) == 1      # recomputed, not extended
    assert computes.count(key_plain) == 2     # the extension's recount, then a full compute
    dg.bump()
    cold = {json.dumps(ch): (_post(client, "spot", {"chain": ch}),
                             _post(client, "split", {"chain": ch, "type": "next_actions"}))
            for ch in (spot, plain)}
    assert json.dumps(warm, sort_keys=True) == json.dumps(cold, sort_keys=True)


def test_extension_keeps_no_sequences_and_extends_sizing(live, hands, monkeypatch):
    conn, client = live
    ch = [{"k": "row", "key": "C01"}]
    _post(client, "split", {"chain": ch, "type": "bet_sizing"})
    calls = []
    real_eval = chain_mod._evaluate

    def spy(db, res, rows, steps, fill, on_rec=None):
        calls.append(on_rec is not None)
        return real_eval(db, res, rows, steps, fill, on_rec=on_rec)

    monkeypatch.setattr(chain_mod, "_evaluate", spy)
    lazy = []
    real_sizing = split_mod._compute_sizing
    monkeypatch.setattr(split_mod, "_compute_sizing",
                        lambda db, res: (lazy.append(1), real_sizing(db, res))[1])
    _import(conn, hands[FIRST:FIRST + 300])
    warm = _post(client, "split", {"chain": ch, "type": "bet_sizing"})
    assert calls == [True] and lazy == []   # one streamed extension, sizing not rebuilt
    dg.bump()
    cold = _post(client, "split", {"chain": ch, "type": "bet_sizing"})
    assert json.dumps(warm, sort_keys=True) == json.dumps(cold, sort_keys=True)
