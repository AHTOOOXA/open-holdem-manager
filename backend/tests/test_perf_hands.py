"""Hand list / export performance changes (performance/03-hands-lists.md) keep the same output.

Every check compares the endpoint against a reference built the old way: the chain's case ids
bound as a list, the `player_id` EXISTS, the marked view joined through `EXISTS (marked_hands)`,
and the export fetched in id batches. On the 20k bench fixture of the Reports tests.
"""

from __future__ import annotations

import json

import pytest

from app.api import hands as H
from app.api.reports_lite import chain_hand_ids
from app.db import get_hero_player_id
from app.action_parser import parse_actions_from_raw

# Reuse the module-scoped bench database and fixtures of the Reports tests.
from tests.test_reports_lite import bench_db, client, hero_id  # noqa: F401

CHAINS = [
    [],
    [{"k": "row", "key": "P01"}],
    [{"k": "pos", "v": ["BTN", "CO"]}],
    [{"k": "line", "dsl": "pre: H:R[3b]"}],
    [{"k": "stakes", "v": ["$0.05/$0.10"]}, {"k": "row", "key": "C01"}],
]
SORTS = {k: v for k, v in H._SORTS.items()}
NO_FILTERS = dict(position=None, stakes=None, result=None, marked=None, tag_ids=None,
                  date_from=None, date_to=None, search=None, stat_flag=None, stat_key=None)


@pytest.fixture(scope="module")
def villain_id(bench_db, hero_id):
    return bench_db.execute(
        "SELECT player_id FROM hand_players WHERE player_id <> ? GROUP BY 1 "
        "ORDER BY COUNT(*) DESC, 1 LIMIT 1", [hero_id]).fetchone()[0]


@pytest.fixture(scope="module")
def marks(bench_db, hero_id, villain_id):
    """A few marks (hero, a villain, and another player in hero-marked hands) with tags."""
    db = bench_db
    hero_hands = [r[0] for r in db.execute(
        "SELECT hand_id FROM hand_players WHERE player_id = ? ORDER BY hash(hand_id) LIMIT 40",
        [hero_id]).fetchall()]
    vil_hands = [r[0] for r in db.execute(
        "SELECT hand_id FROM hand_players WHERE player_id = ? ORDER BY hand_id LIMIT 10",
        [villain_id]).fetchall()]
    pairs = [(h, hero_id) for h in hero_hands] + [(h, villain_id) for h in vil_hands]
    pairs += [(h, p) for h, p in db.execute(
        "SELECT hand_id, MIN(player_id) FROM hand_players WHERE player_id NOT IN (?, ?) "
        "AND hand_id IN (SELECT UNNEST(?::VARCHAR[])) GROUP BY 1", [hero_id, villain_id, hero_hands[:8]]
    ).fetchall()]
    tags = [r[0] for r in db.execute("SELECT id FROM tag_defs ORDER BY position LIMIT 3").fetchall()]
    for i, (h, p) in enumerate(pairs):
        db.execute("INSERT OR IGNORE INTO marked_hands (workspace_id, hand_id, player_id) VALUES (1, ?, ?)",
                   [h, p])
        for pos, t in enumerate(tags[: i % 3]):
            db.execute("INSERT OR IGNORE INTO marked_hand_tags VALUES (1, ?, ?, ?, ?)", [h, p, t, pos])
    yield tags
    db.execute("DELETE FROM marked_hand_tags")
    db.execute("DELETE FROM marked_hands")


# ── the old way ─────────────────────────────────────────────────────────────────────────────


def _old_where(db, *, player_id=None, chain=None, marked=None, tag_ids=None, position=None,
               workspace_id=1):
    """FROM + WHERE of the hand list before 03/F1, F7, F9 (subset of the filters)."""
    hero = player_id if player_id is not None else get_hero_player_id(db, workspace_id)
    all_marked = player_id is None and (bool(marked) or bool(tag_ids))
    ids = chain_hand_ids(db, workspace_id, player_id, json.dumps(chain) if chain is not None else None)
    if all_marked:
        join = ("EXISTS (SELECT 1 FROM marked_hands mh0 WHERE mh0.workspace_id = hp.workspace_id "
                "AND mh0.hand_id = hp.hand_id AND mh0.player_id = hp.player_id)")
        params: list = []
    else:
        join, params = "hp.player_id = ?", [hero]
    where = ["h.workspace_id = ?"]
    params.append(workspace_id)
    if position:
        where.append("hp.position = ?")
        params.append(position)
    if marked is not None:
        where.append(("" if marked else "NOT ") + "EXISTS (SELECT 1 FROM marked_hands mh WHERE "
                     "mh.workspace_id = h.workspace_id AND mh.hand_id = h.id AND mh.player_id = hp.player_id)")
    if tag_ids:
        where.append("EXISTS (SELECT 1 FROM marked_hand_tags mt WHERE mt.workspace_id = h.workspace_id "
                     "AND mt.hand_id = h.id AND mt.player_id = hp.player_id "
                     "AND mt.tag_id IN (SELECT UNNEST(?::INTEGER[])))")
        params.append(tag_ids)
    if player_id is not None:
        where.append("EXISTS (SELECT 1 FROM hand_players hp2 WHERE hp2.hand_id = h.id "
                     "AND hp2.workspace_id = h.workspace_id AND hp2.player_id = ?)")
        params.append(player_id)
    if ids is not None:
        where.append("h.id IN (SELECT UNNEST(?::VARCHAR[]))")
        params.append(ids)
    frm = ("hands h JOIN hand_players hp ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id "
           f"AND {join}")
    return frm, " AND " + " AND ".join(where), params, ids


def _old_rows(db, sort="played_at", order="desc", **kw):
    frm, where, params, ids = _old_where(db, **kw)
    if ids is not None and not ids:
        return []
    col, d = SORTS.get(sort, "h.played_at"), "DESC" if order == "desc" else "ASC"
    return [tuple(r) for r in db.execute(
        f"SELECT h.id, hp.player_id FROM {frm} WHERE 1=1 {where} "
        f"ORDER BY {col} {d}, h.played_at DESC, h.id, hp.player_id", params).fetchall()]


def _old_export(db, sort="played_at", order="desc", cap=H.EXPORT_CAP, **kw):
    """(bytes, truncated) of the export before 03/F2: sorted ids, then texts in 500-id batches."""
    frm, where, params, ids = _old_where(db, **kw)
    if ids is not None and not ids:
        return b"", False
    col, d = SORTS.get(sort, "h.played_at"), "DESC" if order == "desc" else "ASC"
    ids = [r[0] for r in db.execute(f"""
        SELECT id FROM (
            SELECT h.id, {col} AS sk, h.played_at AS pa,
                   ROW_NUMBER() OVER (PARTITION BY h.id ORDER BY {col} {d}, hp.player_id) AS rn
            FROM {frm}
            WHERE h.raw_text IS NOT NULL AND h.raw_text <> '' {where}
        ) WHERE rn = 1 ORDER BY sk {d}, pa DESC, id LIMIT ?""", [*params, cap + 1]).fetchall()]
    truncated = len(ids) > cap
    out, first = [], True
    ids = ids[:cap]
    for i in range(0, len(ids), 500):
        batch = ids[i:i + 500]
        texts = dict(db.execute("SELECT id, raw_text FROM hands WHERE workspace_id = 1 "
                                "AND id IN (SELECT UNNEST(?::VARCHAR[]))", [batch]).fetchall())
        chunk = [t for t in ((texts.get(h) or "").strip() for h in batch) if t]
        if chunk:
            out.append((("" if first else "\n\n\n") + "\n\n\n".join(chunk)).encode())
            first = False
    if not first:
        out.append(b"\n")
    return b"".join(out), truncated


def _api_params(chain=None, tag_ids=None, marked=None, **kw):
    p = {k: v for k, v in kw.items() if v is not None}
    if chain is not None:
        p["chain"] = json.dumps(chain)
    if tag_ids:
        p["tag_ids"] = ",".join(str(t) for t in tag_ids)
    if marked is not None:
        p["marked"] = "true" if marked else "false"
    return p


def _all_rows(client, **kw):
    out, page = [], 1
    while True:
        d = client.get("/api/hands", params={**_api_params(**kw), "per_page": 200, "page": page}).json()
        out += [(h["id"], h["player_id"]) for h in d["hands"]]
        if page >= d["total_pages"]:
            return out, d["total"]
        page += 1


# ── list ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("ci", range(len(CHAINS)))
def test_known_total_is_the_count(bench_db, client, hero_id, villain_id, ci):
    """03/F3: with only the chain filtering, the chain's case count is the list total."""
    for pid in (None, villain_id):
        cur = bench_db.cursor()
        f = H._list_filters(cur, **NO_FILTERS, player_id=pid, workspace_id=1,
                            chain=json.dumps(CHAINS[ci]))
        if f.status != "ok":
            continue
        assert f.known_total is not None
        n = cur.execute(f"SELECT COUNT(*) FROM {f.from_sql} WHERE 1=1 {f.where_sql}",
                        f.params).fetchone()[0]
        assert f.known_total == n
        # any other filter: counted
        g = H._list_filters(cur, **{**NO_FILTERS, "position": "BTN"}, player_id=pid,
                            workspace_id=1, chain=json.dumps(CHAINS[ci]))
        assert g.known_total is None


@pytest.mark.parametrize("ci", range(len(CHAINS)))
def test_chain_list_same_rows(bench_db, client, villain_id, ci):
    """03/F1, F7: chain predicate instead of a bound id list, and no player_id EXISTS."""
    for pid in (None, villain_id):
        for sort, order in (("played_at", "desc"), ("won_usd", "asc")):
            rows, total = _all_rows(client, chain=CHAINS[ci], player_id=pid, sort=sort, order=order)
            assert rows == _old_rows(bench_db, sort=sort, order=order, chain=CHAINS[ci], player_id=pid)
            assert total == len(rows)


def test_player_id_without_chain_same_rows(bench_db, client, villain_id, hero_id):
    for pid in (villain_id, hero_id):
        rows, total = _all_rows(client, player_id=pid, sort="won_bb")
        assert rows == _old_rows(bench_db, sort="won_bb", player_id=pid)
        assert total == len(rows) > 0


def test_marked_view_same_rows(bench_db, client, marks, villain_id, hero_id):
    """03/F9: the marked view without a subject starts from marked_hands."""
    cases = [dict(marked=True), dict(tag_ids=marks[:1]), dict(tag_ids=marks, marked=True),
             dict(tag_ids=marks[1:2], marked=False), dict(marked=True, chain=[]),
             dict(marked=True, chain=CHAINS[1]), dict(marked=True, position="BTN"),
             dict(marked=True, player_id=villain_id), dict(marked=False, player_id=hero_id),
             dict(tag_ids=marks[:2], player_id=hero_id)]
    seen_multi = False
    for kw in cases:
        for sort in ("played_at", "tags"):
            rows, total = _all_rows(client, sort=sort, **kw)
            assert rows == _old_rows(bench_db, sort=sort, **kw), (kw, sort)
            assert total == len(rows)
            seen_multi |= len({h for h, _ in rows}) < len(rows)
    assert seen_multi  # some hand is listed for two players


# ── export ──────────────────────────────────────────────────────────────────────────────────


def _export(client, **kw):
    r = client.get("/api/hands/export", params=_api_params(**kw))
    assert r.status_code == 200, r.text
    return r.content, r.headers.get("x-ohm-truncated") == "1"


@pytest.mark.parametrize("kw", [
    {}, {"chain": []}, {"chain": CHAINS[3], "sort": "won_bb", "order": "asc"},
    {"chain": CHAINS[2], "player_id": "VIL"}, {"sort": "tags"}, {"sort": "stakes", "order": "asc"},
    {"marked": True}, {"marked": True, "sort": "tags", "order": "asc"}, {"tag_ids": "TAGS"},
    {"marked": False, "position": "SB"}, {"chain": [{"k": "stakes", "v": ["$9/$18"]}]},
])
def test_export_same_bytes(bench_db, client, marks, villain_id, kw):
    """03/F2: one ordered streaming query gives the bytes and order of the old batches."""
    kw = dict(kw)
    if kw.get("player_id") == "VIL":
        kw["player_id"] = villain_id
    if kw.get("tag_ids") == "TAGS":
        kw["tag_ids"] = marks
    body, truncated = _export(client, **kw)
    old, old_truncated = _old_export(bench_db, **kw)
    assert body == old
    assert truncated is old_truncated is False


@pytest.mark.parametrize("cap", [1, 999, 1000, 1001, 2500])
def test_export_cap(bench_db, client, monkeypatch, cap):
    monkeypatch.setattr(H, "EXPORT_CAP", cap)
    body, truncated = _export(client, chain=[], sort="won_bb")
    old, old_truncated = _old_export(bench_db, cap=cap, chain=[], sort="won_bb")
    assert truncated and old_truncated
    assert body == old
    assert body.count(b"Poker Hand #") == cap


def test_export_empty(client):
    body, truncated = _export(client, chain=[{"k": "stakes", "v": ["$9/$18"]}])
    assert body == b"" and not truncated


# ── row payload ─────────────────────────────────────────────────────────────────────────────


def test_list_actions_from_raw_text(bench_db, client, marks):
    """03/F5: actions come from the raw text only (the `actions` table is never written).
    03/F8: without the detail-only `p` / `ai`."""
    assert bench_db.execute("SELECT COUNT(*) FROM actions").fetchone()[0] == 0
    for params in ({"per_page": 50}, {"marked": "true", "per_page": 100}):
        d = client.get("/api/hands", params=params).json()
        unames = dict(bench_db.execute("SELECT id, username FROM players").fetchall())
        for h in d["hands"]:
            raw, bb = bench_db.execute("SELECT raw_text, bb_amount FROM hands WHERE id = ?",
                                       [h["id"]]).fetchone()
            ss = parse_actions_from_raw(raw, unames[h["player_id"]], float(bb))
            for st in ("preflop", "flop", "turn", "river"):
                want = [{"a": a.a, "v": a.v, "h": a.h} for a in ss[st]["actions"]]
                got = h[f"{st}_actions"]
                assert got == want  # 03/F8: list rows carry only a, v, h
                if st != "preflop":
                    assert h[f"{st}_pot"] == ss[st]["pot"]


def test_export_invalid_chain(client):
    assert client.get("/api/hands/export", params={"chain": "not json"}).status_code == 422
