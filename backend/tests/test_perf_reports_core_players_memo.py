"""Reports perf track (review fix): the Players split keeps its compact per-opponent table.

The finished Players response of a big chain (one dict per opponent) is over MEMO_MAX_BYTES
and not cached; the (player id, name, Acc) table it is built from is kept on the resolution
(counted in its bytes), so a repeated request only rebuilds the rows."""

from __future__ import annotations

import pytest

from app.reports import chain as chain_mod
from app.reports import split as split_mod

from tests.test_perf_reports_core import bench_db, hero_id  # noqa: F401  (fixtures)


@pytest.mark.parametrize("chain", [[], [{"k": "row", "key": "P01"}]], ids=["page0", "P01"])
def test_players_table_kept_and_response_rebuilt(bench_db, hero_id, chain, monkeypatch):  # noqa: F811
    db = bench_db.cursor()
    res = chain_mod._compute(db, 1, hero_id, chain_mod.CHAIN.validate_python(chain), 0)
    calls = []
    real = split_mod._players_table

    def counted(db_, res_):
        calls.append(1)
        return real(db_, res_)

    monkeypatch.setattr(split_mod, "_players_table", counted)
    before = res.table_bytes
    first = split_mod.split(db, res, "players")
    n = len(first["rows"])
    assert n > 1000
    assert ("players_table",) in res.tables
    assert res.table_bytes - before >= split_mod.PLAYER_ENTRY_BYTES * n
    # A response this big is not kept; the table is.
    assert (("split", "players") in res.tables) == (
        split_mod._response_bytes(first) <= chain_mod.MEMO_MAX_BYTES)
    second = split_mod.split(db, res, "players")
    assert len(calls) == 1
    assert second == first
    db.close()


def test_oversized_players_table_not_kept(bench_db, hero_id, monkeypatch):  # noqa: F811
    db = bench_db.cursor()
    res = chain_mod._compute(db, 1, hero_id, [], 0)
    monkeypatch.setattr(split_mod, "TABLE_MAX_BYTES", 1024)
    t = split_mod.players_table(db, res)
    assert t and ("players_table",) not in res.tables
    db.close()
