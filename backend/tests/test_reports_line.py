"""Custom action lines (`line` chain step) and the hand export, on the 20k bench fixture."""

from __future__ import annotations

import json

import pytest

# Reuse the module-scoped bench database and fixtures of the Reports tests.
from tests.test_reports_lite import (  # noqa: F401
    bench_db, client, hero_id, _post, _split, _rows, _co, _spot_numbers,
)

GATE = "pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R"
GATE_CHAIN = [{"k": "line", "dsl": GATE}]


def _line(dsl: str) -> list:
    return [{"k": "line", "dsl": dsl}]


def _case_ids(client, chain, **extra) -> list[str]:
    ids, page = [], 1
    while True:
        d = client.get("/api/hands", params={"chain": json.dumps(chain), "per_page": 200,
                                             "page": page, **extra}).json()
        ids += [h["id"] for h in d["hands"]]
        if page >= d["total_pages"]:
            return ids
        page += 1


def test_line_equals_row_p07(client):
    row = _post(client, "spot", [{"k": "row", "key": "P07"}])
    line = _post(client, "spot", _line("pre: H:R[3b]"))
    assert row["hands"] > 20
    assert line["hands"] == row["hands"]
    assert _case_ids(client, _line("pre: H:R[3b]")) == _case_ids(client, [{"k": "row", "key": "P07"}])
    sv = lambda d: next(s for s in d["stats"] if s["id"] == "stat_value")["sample"]  # noqa: E731
    assert sv(line) == sv(row)
    a = _split(client, _line("pre: H:R[3b]"), "next_actions")
    b = _split(client, [{"k": "row", "key": "P07"}], "next_actions")
    assert [_co(r) for r in a["rows"]] == [_co(r) for r in b["rows"]]


def test_gate_line_everywhere(client, hero_id):
    spot = _post(client, "spot", GATE_CHAIN)
    n = spot["hands"]
    assert 0 < n < 200, n
    # superset sanity: every hit hand is a hero BTN 3-bet hand
    three_btn = _post(client, "spot", _line("pre: H:R[3b,pos=BTN]"))["hands"]
    assert n <= three_btn
    assert n <= _post(client, "spot", _line("pre: H:R[3b,pos=BTN] > V1:C"))["hands"] <= three_btn
    res = _split(client, GATE_CHAIN, "results")
    assert sum(r["values"]["hands"] for r in res["rows"]) == n or res["summary"]["values"]["hands"] == n
    pos = _split(client, GATE_CHAIN, "positions")
    assert sum(r["values"]["hands"] for r in pos["rows"]) == n
    nxt = _split(client, GATE_CHAIN, "next_actions")
    assert nxt["rows"] and all(r["values"]["hands"] <= n for r in nxt["rows"])
    assert len(_case_ids(client, GATE_CHAIN)) == n
    g = client.get("/api/reports/graph", params={"chain": json.dumps(GATE_CHAIN)}).json()
    assert len(g["points"]) == n
    assert client.get("/api/hands", params={"chain": json.dumps(GATE_CHAIN)}).json()["total"] == n
    # the other chain consumers accept it
    assert client.post("/api/reports/preflop-range",
                       json={"workspace_id": 1, "chain": GATE_CHAIN}).status_code == 200
    # a plain step after the line narrows consistently with positions
    btn = _post(client, "spot", GATE_CHAIN + [{"k": "pos", "v": ["BTN"]}])["hands"]
    assert btn == n


def test_line_matcher_flags(client):
    base = _post(client, "spot", _line("pre: H:R[3b]"))["hands"]
    by_pos = sum(_post(client, "spot", _line(f"pre: H:R[3b,pos={p}]"))["hands"]
                 for p in ("EP", "MP", "CO", "BTN", "SB", "BB"))
    assert by_pos == base
    # open raise, villain position on a villain action, unbound vs bound villain, last
    assert _post(client, "spot", _line("pre: H:R[fr]"))["hands"] == \
        _post(client, "spot", [{"k": "row", "key": "P01"}])["hands"]
    vp = sum(_post(client, "spot", _line(f"pre: V:R[fr,pos={p}] > H:R[3b]"))["hands"]
             for p in ("EP", "MP", "CO", "BTN", "SB"))
    assert vp == base or vp <= base
    assert 0 < vp
    unb = _post(client, "spot", _line("pre: H:R[fr] > V:R > H:C"))["hands"]
    bnd = _post(client, "spot", _line("pre: H:R[fr] > V1:R > H:C"))["hands"]
    assert 0 < bnd <= unb
    last = _post(client, "spot", _line("pre: H:R[fr,last]"))["hands"]
    assert 0 < last <= _post(client, "spot", _line("pre: H:R[fr]"))["hands"]
    mid = _post(client, "spot", _line("pre: H:R[last] > V:R"))["hands"]
    assert mid >= 0


@pytest.mark.parametrize("dsl", ["garbage", "pre: H:Z", "pre: Q:R", "flop: H:B; pre: H:R",
                                 "pre: H:R[pos=XX]", "pre: H:R[nope]", "pre: H:R[amt=x-]", "",
                                 "pre: H:B[amt=2-]", "pre: H:R >", "x" * 2001])
def test_bad_dsl_is_422(client, dsl):
    r = client.post("/api/reports/spot", json={"workspace_id": 1, "chain": _line(dsl)})
    assert r.status_code == 422, r.text
    r = client.get("/api/hands", params={"chain": json.dumps(_line(dsl))})
    assert r.status_code == 422


def test_bad_dsl_message_names_token(client):
    r = client.post("/api/reports/spot", json={"workspace_id": 1, "chain": _line("pre: H:Z")})
    assert "H:Z" in json.dumps(r.json())
    r = client.post("/api/reports/spot", json={"workspace_id": 1, "chain": _line("pre: H:R[wat]")})
    assert "wat" in json.dumps(r.json())


def test_cache_key_includes_dsl(client):
    a = _post(client, "spot", _line("pre: H:R[3b]"))["hands"]
    b = _post(client, "spot", _line("pre: H:R[fr]"))["hands"]
    assert a != b


def test_fuzz_with_lines(client):
    import random
    rng = random.Random(11)
    acts = ["H:R[fr]", "H:R[3b]", "H:C", "H:F", "H:B", "H:X", "V:R", "V1:C", "V1:R[pos=BTN]",
            "V:B[pos=BB+SB]", "H:B[last]", "H:R[3b,pos=BTN]", "V1:X"]
    for _ in range(40):
        parts, streets = [], ["pre", "flop", "turn", "river"]
        for s in sorted(rng.sample(range(4), rng.randint(1, 3))):
            parts.append(f"{streets[s]}: " + " > ".join(rng.choice(acts) for _ in range(rng.randint(1, 3))))
        chain = [{"k": "line", "dsl": "; ".join(parts)}]
        if rng.random() < 0.5:
            chain.append({"k": "next", "street": rng.choice(streets), "a": "bet"})
        typ = rng.choice(["results", "positions", "next_actions", "faced_next", "bet_sizing"])
        r = client.post("/api/reports/split", json={"workspace_id": 1, "chain": chain, "type": typ})
        assert r.status_code in (200, 422), (chain, r.text)
        r = client.get("/api/hands", params={"chain": json.dumps(chain), "per_page": 5})
        assert r.status_code in (200, 422), (chain, r.text)


# ── hand export ──────────────────────────────────────────────────────────


def _export(client, **params):
    return client.get("/api/hands/export", params=params)


def test_export_matches_list(client, bench_db):
    r = _export(client, stakes="$0.05/$0.10", sort="won_bb", order="asc")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "utf-8" in r.headers["content-type"]
    assert r.headers["content-disposition"] == 'attachment; filename="OHM hands.txt"'
    assert "x-ohm-truncated" not in r.headers
    ids = []
    page = 1
    while True:
        d = client.get("/api/hands", params={"stakes": "$0.05/$0.10", "sort": "won_bb",
                                             "order": "asc", "per_page": 200, "page": page}).json()
        ids += [h["id"] for h in d["hands"]]
        if page >= d["total_pages"]:
            break
        page += 1
    assert len(ids) > 100
    texts = r.text.rstrip("\n").split("\n\n\n")
    assert len(texts) == len(ids)
    for hid, t in list(zip(ids, texts))[:50] + list(zip(ids, texts))[-50:]:
        raw = bench_db.execute("SELECT raw_text FROM hands WHERE id = ?", [hid]).fetchone()[0]
        assert t.strip() == raw.strip()


def test_export_chain_and_empty(client):
    r = _export(client, chain=json.dumps(GATE_CHAIN))
    n = _post(client, "spot", GATE_CHAIN)["hands"]
    assert r.text.count("Poker Hand #") == n
    assert _export(client, chain="[]", stakes="nope").text == ""
    assert _export(client, format="csv").status_code == 422


def test_export_skips_missing_raw_text_and_caps(client, bench_db, monkeypatch):
    import app.api.hands as hands_mod
    full = client.get("/api/hands", params={"per_page": 1}).json()["total"]
    hid = client.get("/api/hands", params={"per_page": 1}).json()["hands"][0]["id"]
    raw = bench_db.execute("SELECT raw_text FROM hands WHERE id = ?", [hid]).fetchone()[0]
    bench_db.execute("UPDATE hands SET raw_text = NULL WHERE id = ?", [hid])
    try:
        assert _export(client).text.count("Poker Hand #") == full - 1
        monkeypatch.setattr(hands_mod, "EXPORT_CAP", 5)
        r = _export(client)
        assert r.headers["x-ohm-truncated"] == "1"
        assert r.text.count("Poker Hand #") == 5
    finally:
        bench_db.execute("UPDATE hands SET raw_text = ? WHERE id = ?", [raw, hid])


def test_export_marked_spans_players_once_per_hand(client, bench_db, hero_id):
    ids = [h["id"] for h in client.get("/api/hands", params={"per_page": 3}).json()["hands"]]
    other = bench_db.execute("SELECT player_id FROM hand_players WHERE hand_id = ? AND player_id <> ? "
                             "LIMIT 1", [ids[0], hero_id]).fetchone()[0]
    bench_db.execute("DELETE FROM marked_hands")
    try:
        for hid, pid in ((ids[0], hero_id), (ids[0], other), (ids[1], hero_id)):
            bench_db.execute("INSERT INTO marked_hands (workspace_id, hand_id, player_id) "
                             "VALUES (1, ?, ?)", [hid, pid])
        r = _export(client, marked="true", sort="played_at", order="desc")
        assert r.text.count("Poker Hand #") == 2
        hero_only = _export(client, marked="true", player_id=hero_id)
        assert hero_only.text.count("Poker Hand #") == 2
        assert _export(client, marked="true", player_id=other).text.count("Poker Hand #") == 1
    finally:
        bench_db.execute("DELETE FROM marked_hands")


# ── review fixes (M8 fix B) ──────────────────────────────────────────────

from app.h2n.sequence import BET, CALL, CHECK, FOLD, RAISE  # noqa: E402

_TYPE = {"F": FOLD, "X": CHECK, "C": CALL, "B": BET, "R": RAISE}


def _hero_seqs(bench_db, hero_id):
    """[(hand id, seq, hero index)] of every bench hand with a decodable sequence."""
    from app.reports.chain import fetch_seqs
    from app.h2n.seqcodec import decode_sequence
    ids = [r[0] for r in bench_db.execute(
        "SELECT hand_id FROM hand_players WHERE player_id = ?", [hero_id]).fetchall()]
    out = []
    blobs = fetch_seqs(bench_db, 1, ids)
    for hid in ids:
        seq = decode_sequence(blobs.get(hid))
        if seq is None:
            continue
        p = seq.index.get("Hero")
        if p is not None:
            out.append((hid, seq, p))
    return out


def _street_types(seq, p, street):
    end = seq.seq_end[p][street]
    return [seq.streets[street][i].eff for i in seq.own[p][street] if i < end]


def test_line_after_hit_step_is_filter(client):
    base = [{"k": "row", "key": "P01"}, {"k": "next", "street": "flop", "a": "bet_vs_call"}]
    d0 = _post(client, "spot", base)
    assert d0["hit_label"] == "Continuation Bet"
    chain = base + _line("pre: H:R[fr,pos=BTN]")
    d1 = _post(client, "spot", chain)
    assert d1["hit_label"] == "Continuation Bet"
    assert 0 < d1["hands"] < d0["hands"]
    # the hands are those of the c-bet that also contain the line, hit stays on the flop
    plain = set(_case_ids(client, base))
    line = set(_case_ids(client, _line("pre: H:R[fr,pos=BTN]")))
    assert set(_case_ids(client, chain)) == plain & line
    assert _spot_numbers(client, chain)[0] == len(plain & line)
    # a line as the first spot step still moves the hit
    assert _post(client, "spot", _line("pre: H:R[fr,pos=BTN]"))["hit_label"] == "Action line"
    # a never-matching line empties the set
    assert _post(client, "spot", base + _line("pre: H:R[fr] > H:R[fr]"))["hands"] == 0


def test_list_and_export_order_is_stable(client, bench_db):
    # same-second hands: collapse all timestamps of a slice onto one second
    ids = [h["id"] for h in client.get("/api/hands", params={"per_page": 40}).json()["hands"]]
    ph = ",".join("?" for _ in ids)
    saved = bench_db.execute(f"SELECT id, played_at FROM hands WHERE id IN ({ph})", ids).fetchall()
    bench_db.execute(f"UPDATE hands SET played_at = TIMESTAMP '2024-01-01 12:00:00' WHERE id IN ({ph})", ids)
    try:
        for sort, order in (("played_at", "desc"), ("played_at", "asc")):
            seen, page = [], 1
            while True:
                d = client.get("/api/hands", params={"per_page": 7, "page": page, "sort": sort,
                                                     "order": order, "date_from": "2024-01-01",
                                                     "date_to": "2024-01-01"}).json()
                seen += [h["id"] for h in d["hands"]]
                if page >= d["total_pages"]:
                    break
                page += 1
            assert len(seen) == len(set(seen)) == d["total"] == len(ids)
            r = _export(client, sort=sort, order=order, date_from="2024-01-01", date_to="2024-01-01")
            ex = [x.split(":")[0].replace("Poker Hand #", "") for x in r.text.split("\n")
                  if x.startswith("Poker Hand #")]
            assert ex == [i.replace("Poker Hand #", "") for i in seen]
    finally:
        for hid, ts in saved:
            bench_db.execute("UPDATE hands SET played_at = ? WHERE id = ?", [ts, hid])


def test_hand_detail_has_player_id(client, hero_id):
    hid = client.get("/api/hands", params={"per_page": 1}).json()["hands"][0]["id"]
    d = client.get(f"/api/hands/{hid}").json()
    assert all(isinstance(p["player_id"], int) for p in d["players"])
    assert len({p["player_id"] for p in d["players"]}) == len(d["players"])
    assert [p["player_id"] for p in d["players"] if p["is_hero"]] == [hero_id]


def test_villain_call_line_shows_next_action_stats(client):
    chain = _line("pre: H:R[fr] > V:C")
    d = _post(client, "spot", chain)
    assert d["kind"] == "villain"
    ids = {s["id"]: s for s in d["stats"]}
    nxt = _split(client, chain, "next_actions")
    rows = {(r["caption"]): _co(r) for r in nxt["rows"]}
    assert "Bet vs. Call, Flop" in rows and "Check vs. Call, Flop" in rows
    for key, cap in (("bet_vs_call", "Bet vs. Call, Flop"),
                     ("check_vs_call", "Check vs. Call, Flop")):
        st = next(s for k, s in ids.items() if k.endswith(f":{key}"))
        assert st["filter"] == {"k": "next", "street": "flop", "a": key, "label": st["filter"]["label"]}
        assert st["sample"] == rows[cap][1] and st["sample"] > 0
        assert st["value"] == pytest.approx(rows[cap][0] / rows[cap][1] * 100)


def test_villain_fold_line_has_no_next_stats(client):
    d = _post(client, "spot", _line("pre: H:R[fr] > V:F"))
    if d["hands"]:
        assert not any(s["id"].startswith("next:") for s in d["stats"])
