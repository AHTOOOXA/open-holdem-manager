"""WP-H: stat popup + hands list of the General screen (app/api/general_popup.py).

Spec: docs/specs/H2N-COMPATIBLE-STATS.md sections 5 and 6. Hands are
GGPoker histories built by `hh()` from the matcher tests (blinds $0.5/$1, so
money = big blinds).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api import general_popup as gp
from app.api.import_hands import insert_parsed_hand
from app.h2n.replay import match_row, replay_parsed
from app.h2n.sequence import BET, CALL, CHECK, FOLD, RAISE
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from tests.test_h2n_matcher import hh

# Hero on the button. Clockwise from the button.
SIX = ["Hero", "S", "B", "U", "M", "C"]
OPEN = "U F, M F, C F, Hero R2.5, S F, B C"


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    gp.clear_cache()
    yield TestClient(app)
    gp.clear_cache()


def _insert(db, *texts: str) -> None:
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))


def _cbet_hands() -> list[str]:
    """Four c-bets (cases) and one checked flop (opportunity only)."""
    return [
        # 1. c-bet, check-raised, hero folds. KQ on 2-7-9: "KQ, KJ, QJ".
        hh(SIX, f"{OPEN} | B X, Hero B4, B R12, Hero F", hand_no=1,
           cards={"Hero": "KhQd"}, collected={"B": 19}),
        # 2. c-bet called, turn checked through, river checked: set of nines wins at showdown.
        hh(SIX, f"{OPEN} | B X, Hero B4, B C | B X, Hero X | B X, Hero X", hand_no=2,
           cards={"Hero": "9s9d", "B": "AcQc"}, shows=("Hero", "B"), collected={"Hero": 13.5}),
        # 3. c-bet called, turn lead called, river checked: AK loses to a set at showdown.
        hh(SIX, f"{OPEN} | B X, Hero B4, B C | B B6, Hero C | B X, Hero X", hand_no=3,
           cards={"Hero": "AhKd", "B": "9c9h"}, shows=("Hero", "B"), collected={"B": 25.5}),
        # 4. c-bet, villain folds. 76 pairs the middle card: Middle Pair.
        hh(SIX, f"{OPEN} | B X, Hero B4, B F", hand_no=4,
           cards={"Hero": "7h6h"}, collected={"Hero": 9.5}),
        # 5. checked back on a monotone ace-high flop: opportunity, not a case.
        hh(SIX, f"{OPEN} | B X, Hero X | B B3, Hero F", hand_no=5,
           cards={"Hero": "JcTc"}, board=["Ah", "Kh", "5h", "2d", "3s"], collected={"B": 8.5}),
    ]


def _detail(client, cell: str, **params) -> dict:
    r = client.get(f"/api/general/cell/{cell}/detail", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _hands(client, cell: str, **params) -> dict:
    r = client.get(f"/api/general/cell/{cell}/hands", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _ratio(x: dict) -> tuple:
    return x["cases"], x["opps"]


# ── detail ────────────────────────────────────────────────────────────────


def test_cbet_detail(client, db):
    _insert(db, *_cbet_hands())
    d = _detail(client, "postflop.cbet.Flop")
    assert d["row"] == "C01" and d["street"] == "flop" and d["player"] == "Hero"
    assert (d["cases"], d["opps"]) == (4, 5)
    assert d["value"] == pytest.approx(80.0)

    # section 2: over the cases only
    s = d["summary"]
    assert _ratio(s["won_hand"]) == (2, 4)     # hands 2 (showdown) and 4 (fold)
    assert _ratio(s["wtsd"]) == (2, 4)
    assert _ratio(s["wsd"]) == (1, 2)

    # section 3: fold (1), check (2), call (3), nothing after the villain folds (4)
    n = s["next"]
    assert _ratio(n["fold"]) == (1, 2)
    assert _ratio(n["call"]) == (1, 2)
    assert _ratio(n["raise"]) == (0, 2)
    assert _ratio(n["bet"]) == (0, 1)
    assert _ratio(n["check"]) == (1, 1)
    assert n["show_fold_call_raise"] and n["show_bet_check"]

    # section 4: Range histogram over cases, flop categories in display order
    st = d["strength"]
    counts = {b["key"]: b["count"] for b in st["buckets"]}
    assert [b["key"] for b in st["buckets"]][:3] == ["trash", "kq_kj_qj", "ace_high"]
    assert "other" not in counts
    assert counts["kq_kj_qj"] == 1 and counts["set"] == 1
    assert counts["overcards_akj"] == 1 and counts["middle_pair"] == 1
    assert st["total"] == 4 and st["weak"] == 2 and st["weak_pct"] == pytest.approx(50.0)
    kq = next(b for b in st["buckets"] if b["key"] == "kq_kj_qj")
    assert kq["pct"] == pytest.approx(25.0) and kq["color"] == "#3E8219" and kq["weak"]

    # section 5: textures of the flop; rows without opportunities are hidden
    boards = {b["key"]: b for b in d["boards"]}
    assert set(boards) == {"rainbow", "suited", "ace_high"}
    assert _ratio(boards["rainbow"]) == (4, 4)
    assert _ratio(boards["suited"]) == (0, 1) and boards["suited"]["value"] == 0
    assert boards["rainbow"]["strength"]["total"] == 4
    assert _ratio(boards["rainbow"]["next"]["check"]) == (1, 1)

    # section 6: 4 into 5.5 = 0.73 pot; every bucket was possible, only one has cases
    assert [b["key"] for b in d["bet_sizes"]] == ["bet_60_80"]
    size = d["bet_sizes"][0]
    assert size["label"] == "0.6-0.8 pot" and size["action"] == "bet"
    assert _ratio(size) == (4, 5)
    assert size["strength"]["total"] == 4


def test_cache_reuses_replays(client, db):
    _insert(db, *_cbet_hands())
    first = _detail(client, "postflop.cbet.Flop")
    assert first["replayed"] == 5 and first["replay_failed"] == 0
    again = _detail(client, "postflop.cbet.Flop")
    assert again["replayed"] == 0
    assert again["summary"] == first["summary"]


def test_preflop_open_raise_detail(client, db):
    _insert(db, *_cbet_hands())
    d = _detail(client, "preflop.open_raise.Total")
    assert d["street"] == "preflop" and (d["cases"], d["opps"]) == (5, 5)
    assert d["strength"] is None and d["boards"] == []
    n = d["summary"]["next"]
    # after the open and the big blind's call, hero's next decision is his flop action
    assert _ratio(n["bet"]) == (4, 5) and _ratio(n["check"]) == (1, 5)
    assert not n["show_fold_call_raise"] and n["fold"]["value"] is None
    # opening to 2.5bb: "Raise 2.2-2.7bb"; no previous VPIP action, so no "x" buckets
    assert [(b["label"], b["cases"], b["opps"]) for b in d["bet_sizes"]] == [
        ("Raise 2.2-2.7bb", 5, 5)]


def test_position_filter_and_same_as(client, db):
    _insert(db, *_cbet_hands())
    assert (_detail(client, "preflop.open_raise.BTN")["opps"]) == 5
    sb = _detail(client, "preflop.open_raise.SB")
    assert (sb["cases"], sb["opps"], sb["value"]) == (0, 0, None)
    # a same-as cell opens the stat it points to
    d = _detail(client, "postflop.vs_cbet_raised.Fold")
    assert d["row"] == "C04"


def test_filters_apply(client, db):
    _insert(db, *_cbet_hands())
    assert _detail(client, "postflop.cbet.Flop", stakes="nope")["opps"] == 0
    assert _detail(client, "postflop.cbet.Flop", date_to="2026-01-14")["opps"] == 0
    assert _detail(client, "postflop.cbet.Flop", date_from="2026-01-15")["opps"] == 5


def test_errors(client, db):
    assert client.get("/api/general/cell/nope/detail").status_code == 404
    assert client.get("/api/general/cell/postflop.af.Flop/detail").status_code == 400
    assert client.get("/api/general/cell/postflop.cbet.Flop/detail",
                      params={"player_id": 999}).status_code == 404
    _insert(db, *_cbet_hands())
    for params in ({"bucket": "nope"}, {"board": "nope"}, {"size": "pre_raise_2_25x"}):
        r = client.get("/api/general/cell/postflop.cbet.Flop/hands", params=params)
        assert r.status_code == 400, params


def test_empty_database(client):
    d = _detail(client, "postflop.cbet.Flop")
    assert (d["cases"], d["opps"], d["value"]) == (0, 0, None)
    assert _hands(client, "postflop.cbet.Flop")["total"] == 0


# ── hands list ────────────────────────────────────────────────────────────


def test_hands_list_rows(client, db):
    _insert(db, *_cbet_hands())
    data = _hands(client, "postflop.cbet.Flop")
    assert data["total"] == 4
    # newest first (equal timestamps: by hand id)
    assert [r["hand_id"] for r in data["rows"]] == [
        "RC000000004", "RC000000003", "RC000000002", "RC000000001"]
    row = data["rows"][3]
    assert row["hole_cards"] == ["Kh", "Qd"]
    assert [v["label"] for v in row["hand_value"]] == ["KQ, KJ, QJ"]
    pre, flop, turn, river = row["streets"]
    # preflop: non-fold actions only (villain folds hidden), raise = raise-to
    assert [(a["t"], a["amt_bb"], a["pos"], a["hero"]) for a in pre["actions"]] == [
        ("R", 2.5, "BTN", True), ("C", 1.5, "BB", False)]
    assert flop["cards"] == [["2c", "7d", "9h"]] and flop["pot_bb"] == pytest.approx(5.5)
    assert [(a["t"], a["amt_bb"], a["hero"]) for a in flop["actions"]] == [
        ("X", None, False), ("B", 4.0, True), ("R", 12.0, False), ("F", None, True)]
    assert turn is None and river is None          # hero folded on the flop
    assert row["won_bb"] == pytest.approx(-6.5) and row["ev_diff_bb"] == pytest.approx(0.0)

    row2 = next(r for r in data["rows"] if r["hand_id"] == "RC000000002")
    assert row2["hole_cards"] == ["9d", "9s"]      # pair: hearts, diamonds, clubs, spades
    assert row2["streets"][2]["cards"] == [["Ks"]] and row2["streets"][2]["pot_bb"] == 13.5
    assert row2["streets"][3]["pot_bb"] == pytest.approx(13.5)


def test_hands_list_filters_and_paging(client, db):
    _insert(db, *_cbet_hands())
    cell = "postflop.cbet.Flop"
    assert [r["hand_id"] for r in _hands(client, cell, bucket="set")["rows"]] == ["RC000000002"]
    assert _hands(client, cell, bucket="trash")["total"] == 0
    assert _hands(client, cell, bucket="1")["total"] == 1          # index form (KQ)
    assert _hands(client, cell, board="rainbow")["total"] == 4
    assert _hands(client, cell, board="suited")["total"] == 0      # hand 5 is no case
    assert _hands(client, cell, size="bet_60_80")["total"] == 4
    assert _hands(client, cell, size="bet_overbet")["total"] == 0
    assert _hands(client, cell, board="rainbow", bucket="set")["total"] == 1
    page = _hands(client, cell, offset=1, limit=2)
    assert page["total"] == 4 and [r["hand_id"] for r in page["rows"]] == [
        "RC000000003", "RC000000002"]
    won = _hands(client, cell, sort="won")["rows"]
    assert won[0]["hand_id"] == "RC000000002"                      # biggest win first


# ── next decision rules (H2N-COMPATIBLE-STATS.md 6.3) ─────────────────


def _next(text: str, row: str, name: str = "Hero"):
    seq = replay_parsed(parse_hand_history(text))
    res = match_row(seq, row, name)
    assert res is not None and res.case
    f = gp._Flat(seq)
    return gp._hero_next(f, f.gidx[res.hit], seq.index[name])


def _mask(*types: int) -> int:
    m = 0
    for t in types:
        m |= 1 << t
    return m


def test_next_vector_6_oop_check_counts_not_the_fold():
    text = hh(["BTN", "Hero", "B"], "BTN F, Hero R2.5, B C | Hero B4, B C | Hero X, B B6, Hero F")
    assert _next(text, "C01") == (CHECK, _mask(CHECK, BET))


def test_next_vector_7_multiway_raise_behind_caller():
    text = hh(SIX, "U F, M F, C F, Hero R2.5, S C, B C | S X, B X, Hero B4, S C, B R14, Hero C, S F")
    assert _next(text, "C01") == (CALL, _mask(CALL, FOLD, RAISE))


def test_next_vector_1_and_5():
    text = hh(SIX, f"{OPEN} | B X, Hero B4, B R12, Hero F")
    assert _next(text, "C01") == (FOLD, _mask(FOLD, CALL, RAISE))
    assert _next(hh(SIX, f"{OPEN} | B X, Hero B4, B F"), "C01") is None


def test_next_vector_9_call_then_vpip_on_a_later_street():
    # SB completes, BB checks; the next VPIP action is on the flop -> nothing
    text = hh(["BTN", "Hero", "B", "U", "M", "C"],
              "U F, M F, C F, BTN F, Hero C, B X | Hero X, B B1, Hero F")
    seq = replay_parsed(parse_hand_history(text))
    f = gp._Flat(seq)
    hero = seq.index["Hero"]
    g = next(i for i, a in enumerate(f.acts) if a.actor == hero and a.eff == CALL)
    assert gp._hero_next(f, g, hero) is None


def test_next_preflop_check_alternative_is_raise():
    # BB checks the limped pot: preflop check alternatives = {raise}
    text = hh(["BTN", "S", "Hero", "U", "M", "C"], "U F, M F, C F, BTN F, S C, Hero X | S X, Hero X")
    seq = replay_parsed(parse_hand_history(text))
    hero = seq.index["Hero"]
    check = next(a for a in seq.streets[0] if a.actor == hero)
    assert gp._count_mask(check) == (CHECK, _mask(CHECK, RAISE))


# ── helpers ───────────────────────────────────────────────────────────────


def test_sort_hole_cards():
    assert gp.sort_hole_cards(["9s", "Kd"]) == ["Kd", "9s"]
    assert gp.sort_hole_cards(["Ks", "Kh"]) == ["Kh", "Ks"]
    assert gp.sort_hole_cards(["7s", "7c"]) == ["7c", "7s"]
    assert gp.sort_hole_cards(["Qc", "Qd"]) == ["Qd", "Qc"]


def test_run_out_pot_returns_uncalled_bet():
    text = hh(["Hero", "V"], "Hero R100, V C", stacks={"V": 50}, max_seats=2,
              cards={"Hero": "AhAd", "V": "KcKd"}, shows=("Hero", "V"), collected={"Hero": 100})
    parsed = parse_hand_history(text)
    row = gp.build_row(parsed, replay_parsed(parsed), "Hero", 0)
    pre, flop, turn, river = row.streets
    assert [a.allin for a in pre.actions] == [True, True]
    assert flop.pot_bb == pytest.approx(100.0) and river.pot_bb == pytest.approx(100.0)
    assert flop.actions == [] and row.hand_value == []


def test_bet_size_buckets_postflop_raise_and_call():
    # flop: hero bets 4 into 5.5, villain min-raises to 8 -> villain's raise is a "Min Raise"
    text = hh(SIX, f"{OPEN} | B X, Hero B4, B R8, Hero C")
    seq = replay_parsed(parse_hand_history(text))
    b = seq.index["B"]
    raise_idx = next(i for i, a in enumerate(seq.streets[1]) if a.actor == b and a.eff == RAISE)
    hits = dict(gp._size_hits(seq, (1, raise_idx), gp._BUCKETS))
    assert hits.get("raise_min") is True
    # hero's call faces a raise of (8 - 4) / (9.5 + 4) = 0.30 pot -> "Call vs. bet <= 0.6 pot"
    hero = seq.index["Hero"]
    call_idx = next(i for i, a in enumerate(seq.streets[1]) if a.actor == hero and a.eff == CALL)
    hits = dict(gp._size_hits(seq, (1, call_idx), gp._BUCKETS))
    assert hits.get("call_vs_le_60") is True and hits.get("fold_vs_le_60") is False
    assert 8 not in hits and 9 not in hits


def test_bet_bucket_needs_stack_to_pot():
    # 6bb behind into a 5.5bb pot: SPR 1.09 < 1.25 -> no bet bucket at all
    text = hh(SIX, f"{OPEN} | B X, Hero B6", stacks={"Hero": 8.5, "B": 100})
    seq = replay_parsed(parse_hand_history(text))
    res = match_row(seq, "C01", "Hero")
    assert res.case
    assert gp._size_hits(seq, res.hit, gp._BUCKETS) == ()
