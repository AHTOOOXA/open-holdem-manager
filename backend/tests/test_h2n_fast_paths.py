"""Fast paths of the H2N layer give the same answers as the slow ones.

- import: the coarser preflop shape memo, the GG main-blind and pot-overpay
  shortcuts, grouping postflop rows by their preflop part;
- popup: the stored action sequence (`hand_players.h2n_seq`) instead of
  re-parsing the hand history;
- dead / absent small blind positions (checked against H2N's engine on
  synthetic hands);
- position filters, last-N and the drift page on the H2N columns.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api import general_popup as gp
from app.api.import_hands import insert_parsed_hand
from app.h2n import _collected_bound, compute_h2n
from app.h2n.rows import has_bit
from app.h2n.seqcodec import decode_sequence, encode_sequence
from app.h2n.sequence import _main_blind, build_sequence
from app.main import app
from app.money import collected_total, h2n_main_blind
from app.parsers import detect_parser
from app.parsers.ggpoker import parse_hand_history
from app.stat_flags import compute_stat_flags
from app.stats_engine import compute_player_stats
from tests.test_h2n_matcher import hh

FIXTURES = Path(__file__).parent / "fixtures"
SITE_DIRS = ("ggpoker", "pokerstars", "partypoker", "poker888", "winamax", "wpn", "ipoker")
BENCH_HANDS = 1500   # hands of bench_sample_20k.txt used here (the file is large)


def _parsed_fixture_hands() -> list:
    out = []
    files = [f for d in SITE_DIRS for f in sorted((FIXTURES / d).glob("*.txt"))]
    for f in files:
        content = f.read_text(errors="replace")
        parser = detect_parser(content)
        if parser is None:
            continue
        for text in parser.split_hands(content):
            if not text.strip():
                continue
            try:
                p = parser.parse_hand_history(text)
            except Exception:
                continue
            if p is not None and p.seats:
                out.append(p)
    bench = FIXTURES / "bench_sample_20k.txt"
    if bench.exists():
        from app.parsers.ggpoker import split_hands
        for text in split_hands(bench.read_text())[:BENCH_HANDS]:
            if text.strip():
                p = parse_hand_history(text.strip())
                if p is not None:
                    out.append(p)
    return out


HANDS = _parsed_fixture_hands()


def _fingerprint(seq):
    acts = [[(a.street, a.idx, a.actor, a.name, a.raw, a.eff, a.flags, a.pos, a.inc, a.to,
              a.pot, a.to_call, a.stack_left, a.bb, a.amt_bb, bool(a.is_all_in)) for a in st]
            for st in seq.streets]
    return (seq.names, seq.index, seq.pos, seq.bb, seq.fold_street, seq.seq_end, seq.has_seq,
            seq.own, [[list(t) for t in bt] for bt in seq.by_type], seq.first_raise_idx,
            seq.open_idx, seq.pot_total, acts)


def test_enough_fixture_hands():
    assert len(HANDS) > 200
    assert len({p.site_id for p in HANDS}) >= 5


def test_sequence_codec_round_trip():
    for p in HANDS:
        seq = build_sequence(p)
        blob = encode_sequence(seq)
        assert blob is not None, p.hand_id
        assert _fingerprint(decode_sequence(blob)) == _fingerprint(seq), p.hand_id


def test_codec_rejects_other_versions_and_garbage():
    seq = build_sequence(HANDS[0])
    blob = encode_sequence(seq)
    assert decode_sequence(bytes([blob[0] + 1]) + blob[1:]) is None
    assert decode_sequence(blob[:-3]) is None
    assert decode_sequence(None) is None and decode_sequence(b"") is None


def test_main_blind_shortcut_matches_the_money_rules():
    for p in HANDS:
        assert _main_blind(p) == float(h2n_main_blind(p)), p.hand_id


def test_main_blind_shortcut_defers_on_other_post_amounts():
    text = hh(["Hero", "S", "B"], "Hero R2.5, S F, B F", max_seats=3, collected={"Hero": 2.5})
    # a big blind post of 2 against a $1 header: the money rules decide (BB = 2)
    odd = text.replace("B: posts big blind $1", "B: posts big blind $2")
    p = parse_hand_history(odd)
    assert _main_blind(p) == float(h2n_main_blind(p))


def test_collected_bound_is_an_upper_bound():
    for p in HANDS:
        assert _collected_bound(p) >= float(collected_total(p)) - 1e-9, p.hand_id


def test_shape_memo_matches_uncached():
    for p in HANDS:
        assert compute_h2n(p) == compute_h2n(p, use_cache=False), p.hand_id


def test_one_sequence_copy_per_hand_on_the_hero(db):
    for p in HANDS[:300]:
        cols = compute_stat_flags(p)
        carriers = [u for u, f in cols.items() if f["h2n_seq"] is not None]
        assert len(carriers) == 1, p.hand_id
        seated = {s["username"] for s in p.seats}
        if seated & set(p.hero_cards or {}):
            assert carriers[0] in p.hero_cards, p.hand_id
    insert_parsed_hand(db, HANDS[0])
    n = db.execute("SELECT COUNT(h2n_seq) FROM hand_players").fetchone()[0]
    assert n == 1


# ── dead / absent small blind ────────────────────────────────────────────


def _no_sb_hand(num: int, seats: list[int], bb_seat: int, order: list[int], raiser: int,
                hero_seat: int) -> str:
    """GG hand, button seat 1, nobody posts the small blind; everyone folds to `raiser`."""
    names = {s: ("Hero" if s == hero_seat else f"p{s}") for s in seats}
    lines = [f"Poker Hand #RC8{num:09d}: Hold'em No Limit ($0.02/$0.05) - 2026/01/09 21:28:01",
             "Table 'RushAndCash1' 6-max Seat #1 is the button"]
    lines += [f"Seat {s}: {names[s]} ($5 in chips)" for s in seats]
    lines += [f"{names[bb_seat]}: posts big blind $0.05", "*** HOLE CARDS ***"]
    lines += [f"Dealt to {names[s]} " + ("[Ac Kd]" if s == hero_seat else "") for s in seats]
    for s in order:
        lines.append(f"{names[s]}: raises $0.10 to $0.15" if s == raiser else f"{names[s]}: folds")
    lines += [f"Uncalled bet ($0.10) returned to {names[raiser]}", "*** SHOWDOWN ***",
              f"{names[raiser]} collected $0.10 from pot", "*** SUMMARY ***",
              "Total pot $0.10 | Rake $0 | Jackpot $0 | Bingo $0 | Fortune $0 | Tax $0"]
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("hero,expected", [
    (1, "CO"), (2, "BTN"), (3, "BB"), (4, "EP"), (5, "EP"), (6, "MP"),
])
def test_dead_sb_seated_player_before_bb_is_the_button(hero, expected):
    """A seated player between the dealer and the big blind who posts nothing
    is H2N's button; the dealer becomes CO (H2N's engine on this hand)."""
    p = parse_hand_history(_no_sb_hand(hero, [1, 2, 3, 4, 5, 6], 3, [4, 5, 6, 1, 2, 3], 1, hero))
    cols = compute_stat_flags(p)["Hero"]
    assert cols["h2n_pos"] == expected
    if hero == 2:
        # and he is in position to the dealer's open: a 3-bet IP opportunity
        assert has_bit(cols["h2n_pre_opp"], "P09")
        assert not has_bit(cols["h2n_pre_opp"], "P10")


@pytest.mark.parametrize("hero,expected", [(1, "BTN"), (3, "BB"), (4, "EP"), (5, "MP"), (6, "CO")])
def test_empty_sb_seat_keeps_the_dealer_on_the_button(hero, expected):
    p = parse_hand_history(_no_sb_hand(10 + hero, [1, 3, 4, 5, 6], 3, [4, 5, 6, 1, 3], 1, hero))
    assert compute_stat_flags(p)["Hero"]["h2n_pos"] == expected


# ── popup on stored sequences ────────────────────────────────────────────

SIX = ["Hero", "S", "B", "U", "M", "C"]


def _popup_hands() -> list[str]:
    return [
        hh(SIX, "U F, M F, C F, Hero R2.5, S F, B C | B X, Hero B4, B F", hand_no=1,
           cards={"Hero": "7h6h"}, collected={"Hero": 9.5}),
        hh(SIX, "U R3, M F, C F, Hero R9, S F, B F, U C | U X, Hero B8, U F", hand_no=2,
           cards={"Hero": "AhAd"}, collected={"Hero": 30}),
        hh(SIX, "U F, M R2.2, C F, Hero C, S F, B F | M B2, Hero F", hand_no=3,
           cards={"Hero": "9s8s"}, collected={"M": 7.4}),
        hh(SIX, "U F, M F, C F, Hero F, S R3, B C | S B3, B F", hand_no=4,
           cards={"Hero": "2c7d"}, collected={"S": 9}),
        hh(SIX, "U F, M F, C R2.5, Hero R8, S F, B F, C R20, Hero F", hand_no=5,
           cards={"Hero": "KhQh"}, collected={"C": 26.5}),
    ]


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    gp.clear_cache()
    yield TestClient(app)
    gp.clear_cache()


CELLS = ("summary.vpip.Total", "summary.pfr.Total", "preflop.open_raise.Total",
         "preflop.three_bet.Total", "preflop.fold_to_3bet.Total", "postflop.cbet.Flop")


def _all_details(client) -> dict:
    out = {}
    for cell in CELLS:
        r = client.get(f"/api/general/cell/{cell}/detail")
        assert r.status_code == 200, r.text
        d = r.json()
        d.pop("replayed")
        out[cell] = d
        r = client.get(f"/api/general/cell/{cell}/hands")
        assert r.status_code == 200, r.text
        out[cell + "/hands"] = r.json()
    return out


def test_popup_stored_sequences_match_reparsing(client, db, monkeypatch):
    for t in _popup_hands():
        insert_parsed_hand(db, parse_hand_history(t))
    assert db.execute("SELECT COUNT(h2n_seq) FROM hand_players").fetchone()[0] == 5

    # preflop rows never re-parse while the stored copies are there
    real_parse = gp._parse
    calls = []

    def counting_parse(*args):
        calls.append(args)
        return real_parse(*args)

    monkeypatch.setattr(gp, "_parse", counting_parse)
    gp.clear_cache()
    gp.compute_detail(db, gp._resolve("summary.vpip.Total"), _hero_id(db), 1, ("", []))
    assert calls == []

    stored = _all_details(client)
    db.execute("UPDATE hand_players SET h2n_seq = NULL")
    gp.clear_cache()
    reparsed = _all_details(client)
    assert calls  # this time every replay re-parsed
    assert stored == reparsed


def test_popup_falls_back_on_unreadable_copies(client, db):
    for t in _popup_hands():
        insert_parsed_hand(db, parse_hand_history(t))
    good = _all_details(client)
    db.execute("UPDATE hand_players SET h2n_seq = '\\x09\\x00'::BLOB WHERE h2n_seq IS NOT NULL")
    gp.clear_cache()
    assert _all_details(client) == good


def _hero_id(db) -> int:
    return db.execute("SELECT id FROM players WHERE username = 'Hero'").fetchone()[0]


# ── H2N columns in the other stats endpoints ─────────────────────────────


def test_last_n_counts_only_hands_the_stats_count(db):
    texts = [hh(["Hero", "S", "B"], "Hero R2.5, S F, B F", max_seats=3, hand_no=i,
                collected={"Hero": 2.5}) for i in (1, 2, 3)]
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))
    hero = _hero_id(db)
    # the latest hand is one H2N would refuse: last 1 = the newest counted hand
    latest = db.execute("SELECT id FROM hands ORDER BY played_at DESC, id DESC LIMIT 1").fetchone()[0]
    db.execute("UPDATE hand_players SET h2n_valid = FALSE WHERE hand_id = ?", [latest])
    assert compute_player_stats(db, hero, last_n=1).hands == 1
    assert compute_player_stats(db, hero, last_n=2).hands == 2
    assert compute_player_stats(db, hero, last_n=5).hands == 2


def test_drift_fold_to_3bet_uses_the_h2n_row(db):
    from app.api.reports import _F3B_CASE, _F3B_OPP
    from app.stats_engine import compute_player_stats as cps

    texts = [
        # open, 3-bet, fold: a case
        hh(["Hero", "S", "B"], "Hero R2.5, S R9, B F, Hero F", max_seats=3, hand_no=1,
           collected={"S": 12.5}),
        # open, 3-bet, call: an opportunity
        hh(["Hero", "S", "B"], "Hero R2.5, S R9, B F, Hero C | S B10, Hero F", max_seats=3,
           hand_no=2, collected={"S": 19}),
        # limp, raise, fold: not a fold to 3-bet
        hh(["Hero", "S", "B"], "Hero C, S R4, B F, Hero F", max_seats=3, hand_no=3,
           collected={"S": 6}),
    ]
    for t in texts:
        insert_parsed_hand(db, parse_hand_history(t))
    hero = _hero_id(db)
    cases, opps = db.execute(
        f"SELECT SUM({_F3B_CASE}) FILTER (WHERE {_F3B_OPP}), COUNT(*) FILTER (WHERE {_F3B_OPP}) "
        "FROM hand_players hp WHERE hp.player_id = ?", [hero]).fetchone()
    f3b = cps(db, hero).fold_to_3bet.total
    assert (cases, opps) == (1, 2)
    assert f3b.sample == opps and f3b.value == 50.0
