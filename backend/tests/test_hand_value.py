"""Hand value categories (stat popup Range tab) and board textures: app.hand_value.

Vectors: docs/specs/H2N-COMPATIBLE-STATS.md sections 6.1, 6.4 and 6.5,
plus vectors labelled with Hand2Note 4.1's results (see H2N_VECTORS).
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.hand_value import (
    BOARD_CATEGORIES,
    HandFacts,
    MADE_FULL_HOUSE,
    MADE_SET,
    MADE_TRIPS,
    MADE_TWO_PAIR,
    OTHER,
    PAIR_LOW,
    PAIR_MIDDLE,
    PAIR_OVER,
    PAIR_TOP,
    STREET_CATEGORIES,
    board_categories,
    categories,
    category,
    category_info,
    classify_boards_for_player,
    classify_for_player,
    hand_facts,
    is_weak,
    parse_card,
    weak_pct,
    apply_hand_values,
)
from app.parsers.common import ParsedHand


def _idx(street: str, label: str) -> int:
    if label == "Other":
        return OTHER
    labels = [c.label for c in STREET_CATEGORIES[street]]
    return labels.index(label)


def _cards(s: str) -> list[str]:
    s = s.replace(" ", "")
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def _cat(hole: str, board: str) -> str:
    b = _cards(board)
    street = {3: "flop", 4: "turn", 5: "river"}[len(b)]
    return category_info(street, category(_cards(hole), b))["label"]


# --- catalog ---------------------------------------------------------------

def test_category_lists_match_spec_order():
    assert [c.label for c in STREET_CATEGORIES["flop"]] == [
        "Trash", "KQ, KJ, QJ", "Ace High", "Overcards AK-J", "Gutshot", "Draw",
        "Low Pockets", "Low Pair", "Middle Pair", "TPWK", "TPGK", "Overpair", "Set",
        "Two Pairs+",
    ]
    assert [c.label for c in STREET_CATEGORIES["turn"]] == [
        "Trash", "KQ, KJ, QJ", "Ace High", "Overcards AK-J", "Gutshot", "Draw",
        "Draw + Pair", "Low Pair", "Middle Pair", "TPWK", "TPGK", "Overpair", "Set",
        "Two Pairs+",
    ]
    assert [c.label for c in STREET_CATEGORIES["river"]] == [
        "Missed Trash", "Missed Overcards", "Ace High", "Missed Draw", "Low Pair",
        "Middle Pair", "TPWK", "TPTK", "Overpair", "Set", "Two Pairs+",
    ]


def test_colours_and_weak_flags():
    flop = STREET_CATEGORIES["flop"]
    assert [c.color for c in flop] == [
        "#9DC397", "#3E8219", "#78AE32", "#78AE32", "#0BA3D7", "#3E5997", "#653D87",
        "#653D87", "#431D63", "#B7A913", "#B76713", "#73524C", "#893A67", "#BC5F65",
    ]
    assert [c.weak for c in flop] == [True] * 7 + [False] * 7
    turn = STREET_CATEGORIES["turn"]
    assert turn[6].label == "Draw + Pair" and turn[6].color == "#222E6B" and turn[6].weak
    assert [c.weak for c in turn] == [True] * 7 + [False] * 7
    river = STREET_CATEGORIES["river"]
    assert [c.weak for c in river] == [True] * 4 + [False] * 7
    assert [c.color for c in river[:4]] == ["#9DC397", "#3E8219", "#78AE32", "#3E5997"]
    assert river[7].label == "TPTK" and river[7].color == "#B76713"
    other = category_info("flop", OTHER)
    assert other["label"] == "Other" and other["color"] == "#A0A0A0" and not other["weak"]
    assert not is_weak("river", OTHER)


def test_tooltips():
    flop = {c.label: c.description for c in STREET_CATEGORIES["flop"]}
    assert flop["Overcards AK-J"] == "Overcards with pocket AK, AQ, or AJ"
    assert flop["KQ, KJ, QJ"] == "Overcards with pocket KQ, KJ, or QJ"  # H2N's "pocker" typo fixed
    assert flop["TPWK"] == "Top pair with weak kicker"
    assert flop["TPGK"] == "Top pair with good kicker"
    assert flop["Two Pairs+"] == "Two pairs or higher"
    assert STREET_CATEGORIES["river"][7].description == "Top pair with top kicker"


def test_weak_pct_matches_screenshot():
    # H2N-COMPATIBLE-STATS.md 6.1: the C-Bet popup histogram -> "48% weak"
    counts = {"Trash": 142, "KQ, KJ, QJ": 41, "Ace High": 89, "Overcards AK-J": 82,
              "Gutshot": 67, "Draw": 155, "Low Pockets": 50, "Low Pair": 98,
              "Middle Pair": 174, "TPWK": 150, "TPGK": 120, "Overpair": 59, "Set": 32,
              "Two Pairs+": 40}
    hist = {_idx("flop", k): v for k, v in counts.items()}
    assert sum(hist.values()) == 1299
    assert round(weak_pct("flop", hist)) == 48
    assert weak_pct("flop", {}) is None
    assert weak_pct("flop", {OTHER: 3}) == 0


def test_parse_card():
    assert parse_card("Ah") == (14, "h")
    assert parse_card("10d") == (10, "d")
    assert parse_card("tS") == (10, "s")
    with pytest.raises(ValueError):
        parse_card("1x")


# --- H2N-COMPATIBLE-STATS.md 6.4 (flop) ---------------------------------------

FLOP_VECTORS = [
    ("Jh9s", "8hKhKd", "Trash", dict(air=True, overcards=2)),
    ("Th8d", "4hKd3h", "Trash", dict(air=True, overcards=0)),
    ("Kh9s", "As2cJd", "Trash", dict(air=True)),
    ("KcTc", "JsJd8s", "Trash", dict(air=True, overcards=2)),
    ("Ts9s", "5s8hKd", "Trash", dict(air=True, backdoor_flush=True)),
    ("AhKd", "Qs7c2h", "Overcards AK-J", dict(ace_high=True, overcards=2)),
    ("Ah5d", "Ks7c2h", "Ace High", dict(ace_high=True, overcards=1)),
    ("AsTd", "9s7c2h", "Ace High", dict(ace_high=True, overcards=2)),
    ("KhQd", "9s7c2h", "KQ, KJ, QJ", dict(air=True, overcards=2)),
    ("Jh9d", "Th7c2s", "Gutshot", dict(air=True, overcards=1, gutshot=True)),
    ("9h8d", "Th7c2s", "Draw", dict(air=True, open_straight_draw=True)),
    ("9h8h", "Kh4h2c", "Draw", dict(air=True, has_flush_draw=True)),
    ("AhJh", "Th7h2c", "Draw", dict(ace_high=True, has_flush_draw=True)),
    ("QhJd", "Th9c2s", "Draw", dict(overcards=2, open_straight_draw=True)),
    ("5h5d", "Kh9c2s", "Low Pockets", dict(pair=PAIR_LOW, pocket_pair=True)),
    ("6h6d", "Kh7c5s", "Low Pockets", dict(pair=PAIR_LOW, pocket_pair=True)),
    ("8h8d", "Kh7c5s", "Middle Pair", dict(pair=PAIR_MIDDLE, pocket_pair=True)),
    ("9h9d", "Kh7c2s", "Middle Pair", dict(pair=PAIR_MIDDLE, pocket_pair=True)),
    ("7d6d", "Kc7c2s", "Middle Pair", dict(pair=PAIR_MIDDLE, pocket_pair=False)),
    ("Ah7d", "KcKs7d", "Middle Pair", dict(pair=PAIR_MIDDLE, pocket_pair=False)),
    ("Ah2d", "KcKs7d", "Ace High", dict(air=True, ace_high=True, overcards=1)),
    ("AhQd", "KcKs7d", "Overcards AK-J", dict(overcards=2)),
    ("Kh9d", "Kc7c2s", "TPWK", dict(pair=PAIR_TOP, kicker=5)),
    ("KhQd", "Kc7c2s", "TPGK", dict(pair=PAIR_TOP, kicker=2)),
    ("KhAd", "Kc7c2s", "TPGK", dict(pair=PAIR_TOP, kicker=1)),
    ("QhQd", "Jc7c2s", "Overpair", dict(pair=PAIR_OVER)),
    ("7h7d", "Kc7c2s", "Set", dict(made=MADE_SET)),
    ("Kh7d", "Kc7c2s", "Two Pairs+", dict(made=MADE_TWO_PAIR)),
    ("Kh2d", "KcKs7d", "Two Pairs+", dict(made=MADE_TRIPS)),
    ("2h3h", "4h5h9c", "Draw", dict(has_flush_draw=True, open_straight_draw=True,
                                    combo_draw=True, pair=None)),
]


def _facts(hole: str, board: str):
    return hand_facts(_cards(hole), _cards(board))


@pytest.mark.parametrize("hole,board,label,expected", FLOP_VECTORS)
def test_flop_vectors(hole, board, label, expected):
    assert _cat(hole, board) == label
    got = _facts(hole, board)
    for name, value in expected.items():
        assert getattr(got, name) == value, f"{got!r}: {name} != {value!r}"


def test_flop_vector_details():
    # K-high on an ace board is not "Ace High"
    assert not _facts("Kh9s", "As2cJd").ace_high
    # Ts9s on 5s8hKd: backdoor only, no straight draw
    assert not _facts("Ts9s", "5s8hKd").any_draw
    # 6h6d on Kh7c5s: 6 <= second board rank 7 -> low, not middle
    assert _facts("6h6d", "Kh7c5s").pair == PAIR_LOW


# --- H2N-COMPATIBLE-STATS.md 6.4 (turn / river) -------------------------------

TURN_RIVER_VECTORS = [
    ("9h8h", "Kh4h2c3d", "Draw"),
    ("Ah5d", "Ks7c2h3d", "Ace High"),
    ("7h6h", "7c8s2d4h", "Draw + Pair"),
    ("5h5d", "Kh9c2s8d", "Low Pair"),
    ("Kh9d", "Kc7c2s3d", "TPWK"),
    ("KhQd", "Kc7c2s3d", "TPGK"),
    ("9h8h", "Kh4h2c3d7s", "Missed Draw"),
    ("AhQd", "Ks7c2h3d5c", "Missed Overcards"),
    ("Ah5d", "Ks7c2h3d9c", "Ace High"),
    ("Jh9d", "Th7c2s5sKd", "Missed Draw"),
    ("Kh9d", "Kc7c2s3dJh", "TPWK"),
    ("KhAd", "Kc7c2s3dJh", "TPTK"),
    ("6h6d", "Kh7c5s2dJd", "Low Pair"),
]


@pytest.mark.parametrize("hole,board,label", TURN_RIVER_VECTORS)
def test_turn_river_vectors(hole, board, label):
    assert _cat(hole, board) == label


# --- H2N-COMPATIBLE-STATS.md 6.4 primitives ----------------------------------

def test_kicker_index_examples():
    assert _facts("AhKd", "Kc7s2d").kicker == 1
    assert _facts("AhQd", "Ac7s2d").kicker == 2
    assert _facts("Kh9d", "Kc7s2d").kicker >= 3


def test_flush_draw_rank_quirk():
    # 5h Ac on Kh 7h 2h: flush draw via the 5h, nut place via the ace of clubs
    assert _facts("5hAc", "Kh7h2h").flush_draw == 1


@pytest.mark.parametrize("hole,board,expected", [
    ("As5s", "Ks8d2c7h", True),   # turn, suited, ace -> rule 2
    ("Ks5s", "Qs8d2c7h", False),  # turn, no ace
    ("Ac9d", "Kh7h2c", False),    # hearts not one of hero's suits
    ("9hAc", "Kh7h2c", True),     # hearts held via 9h, top missing heart (A) held via Ac
    ("Ts9s", "5s8hKd", True),     # flop, suited + one board card -> rule 1
])
def test_backdoor_flush_draw(hole, board, expected):
    assert _facts(hole, board).backdoor_flush is expected


def test_no_draws_on_river():
    f = _facts("9h8h", "Kh4h2c3d7s")
    assert not f.any_draw and not f.backdoor_flush


def test_overpair_on_trips_board_is_not_full_house():
    f = _facts("AhAd", "7c7d7s")
    assert f.pair == PAIR_OVER and f.made is None
    assert _cat("AhAd", "7c7d7s") == "Overpair"
    assert _facts("KhTd", "KcKs7d").made == MADE_TRIPS


def test_full_house_with_both_hole_cards():
    assert _facts("Kh7d", "KcKs7c").made == MADE_FULL_HOUSE
    assert _cat("Kh7d", "KcKs7c") == "Two Pairs+"


# Behaviour pinned with H2N 4.1 itself (black-box), not obvious from the rules.
def test_deuce_of_spades_always_counts_as_in_hand():
    # The 2s doesn't play on the turn, yet H2N uses it as top pair's kicker
    assert _facts("Ks2s", "KcJd8h6c").kicker >= 3
    f = _facts("Ks2h", "KcJd8h6c")
    assert f.pair == PAIR_TOP and f.kicker == 0


def test_board_plays_is_air_without_overcards():
    assert _facts("3s2d", "6s8h7d8c5h") == HandFacts(air=True)
    assert _cat("3s2d", "6s8h7d8c5h") == "Missed Trash"


def test_best_possible_hand_on_board_is_other():
    assert _facts("KhQd", "AsAhAdAcKs") == HandFacts(board_is_nuts=True)
    assert _cat("KhQd", "AsAhAdAcKs") == "Other"


def test_double_paired_board():
    # Board KK77: hero's A3 "pairs" the board's 7s as H2N sees it (middle pair, top kicker)
    f = _facts("Ah3c", "KdKs7c7h")
    assert f.pair == PAIR_MIDDLE and not f.pocket_pair and f.kicker == 1 and f.ace_high
    assert _cat("Ah3c", "KdKs7c7h") == "Ace High"
    # ...but with deuces as the board's second pair there is no pair at all
    f = _facts("Ah3c", "KdKs2c2h9d")
    assert f.pair is None and f.ace_high


@pytest.mark.parametrize("hole,flop", [
    # readable Trash rows of the reference screenshot
    ("Jh9s", "8hKhKd"), ("Ts8d", "4hKd3h"), ("KcTc", "JsJd8s"), ("Ts9s", "5s8hKd"),
    ("Kc6c", "7hJd7d"), ("Jd9d", "4d8h8s"), ("KdTc", "Jh6hJd"), ("QdJs", "6s5cAd"),
    ("Kh4h", "6d2cJc"), ("Kh8s", "4c3hJc"), ("Kh9s", "As2cJd"), ("KhQd", "3s7cAh"),
])
def test_screenshot_trash_rows(hole, flop):
    assert _cat(hole, flop) == "Trash"


# Labelled by H2N 4.1 itself (black-box runs on these cards): street, hole,
# board, expected category index (-1 = Other).
H2N_VECTORS = [
    ("flop", "Td 2d", "Jd 8c Jc", 0),
    ("flop", "3h Jc", "5c Kc Kh", 0),
    ("flop", "4d 9s", "8c 2c Qc", 0),
    ("flop", "Kd Qc", "9c Ad As", 1),
    ("flop", "Qc Kc", "2c 2h 8h", 1),
    ("flop", "Js Kh", "3d Ts 6d", 1),
    ("flop", "Ac 5c", "3c 3d 6h", 2),
    ("flop", "Ah 4c", "Kd Kc 6d", 2),
    ("flop", "Ac 7s", "Qs Qc Tc", 2),
    ("flop", "Ad Qc", "9s 8s 9d", 3),
    ("flop", "Jc Ac", "Kd 8s Kc", 3),
    ("flop", "Ad Qh", "5s Tc 6h", 3),
    ("flop", "4s Kd", "7c 6s 3d", 4),
    ("flop", "8h 9h", "Ts 2s Qh", 4),
    ("flop", "7c 8s", "9s Qs 5c", 4),
    ("flop", "Ts As", "2s 4d 7s", 5),
    ("flop", "4c 9d", "2d 4d 7d", 5),
    ("flop", "Ah 3h", "9h 7h Js", 5),
    ("flop", "3h 3d", "6d 9c Kh", 6),
    ("flop", "4h 4c", "3h 5c Th", 6),
    ("flop", "5h 5d", "2s 4c Jd", 6),
    ("flop", "4h 6c", "8c 4d Tc", 7),
    ("flop", "4h 2h", "9c 2c 3h", 7),
    ("flop", "4s 6d", "Ah 4h 8s", 7),
    ("flop", "8c Tc", "Qs Ts 3c", 8),
    ("flop", "2d Qd", "Ah Qs Ac", 8),
    ("flop", "7c 3c", "Ad 5s 7d", 8),
    ("flop", "Kc Ts", "Ks Qc 6h", 9),
    ("flop", "Js Ac", "Ah 5h 5s", 9),
    ("flop", "Js 9h", "Jd 2c Ts", 9),
    ("flop", "Kh Td", "6h Ts 5h", 10),
    ("flop", "Ad 8s", "8c 5h 3d", 10),
    ("flop", "Kc Ac", "9c Kd Tc", 10),
    ("flop", "Ks Kh", "2h 2c 8s", 11),
    ("flop", "Qc Qs", "6c 5c 5s", 11),
    ("flop", "Qh Qd", "7d 3s 7h", 11),
    ("flop", "7h 7d", "Kh 7c Jc", 12),
    ("flop", "2c 2s", "Tc 2d 8d", 12),
    ("flop", "As Ah", "Qh 3d Ad", 12),
    ("flop", "3h 9s", "9h Kh 3s", 13),
    ("flop", "Kh Qs", "Qc Kd 4h", 13),
    ("flop", "9c 7h", "2c 9s 9h", 13),
    ("river", "8d 4h", "Th Kh 4d 8h Kd", -1),
    ("river", "7s 7d", "Td 5d 6s 4h Jd", -1),
    ("river", "3d 5d", "3c 5c Qd Jd Qc", -1),
    ("river", "Td 2d", "Jd 8c Jc 2c 8d", 0),
    ("river", "4d 9s", "8c 2c Qc 3h Ts", 0),
    ("river", "4d 8d", "9s 9d Ac 4s Ad", 0),
    ("river", "Ad Qc", "9s 8s 9d 9c 8c", 1),
    ("river", "Td Kc", "Qs 8s 8h 9d 7c", 1),
    ("river", "Jh Qd", "5d Ah Kc 3d 2d", 1),
    ("river", "Ah 7s", "5h Tc Qc 3h Kd", 2),
    ("river", "As 8d", "9d 5d 4c 4h 3h", 2),
    ("river", "7c Ac", "4d 5d 8d Tc 4c", 2),
    ("river", "8h 5c", "4d 3d 4s Ad Ac", 3),
    ("river", "2s Js", "7s 9c 5c 9s 7h", 3),
    ("river", "4c Kh", "3c 5c 2h 7h 5h", 3),
    ("river", "4h 6c", "8c 4d Tc 3s Jh", 4),
    ("river", "3h 3d", "6d 9c Kh Qc As", 4),
    ("river", "Jh 6s", "Qs 9s Qh Jd Ah", 4),
    ("river", "8c Tc", "Qs Ts 3c 3s 2c", 5),
    ("river", "3h Jc", "5c Kc Kh 7h Jh", 5),
    ("river", "Js 8h", "4d Qh 6h 7c Jc", 5),
    ("river", "4s Kd", "7c 6s 3d Qd Ks", 6),
    ("river", "Kc Ts", "Ks Qc 6h Qh Td", 6),
    ("river", "Js Ac", "Ah 5h 5s 8d 5c", 6),
    ("river", "Kc Ac", "9c Kd Tc 2h 8h", 7),
    ("river", "Ks As", "Kd 4s 3d 4d 7s", 7),
    ("river", "Ac Tc", "7c 4h 5h Td 2s", 7),
    ("river", "Ks Kh", "2h 2c 8s 8c 2s", 8),
    ("river", "Qc Qs", "6c 5c 5s 2s 6s", 8),
    ("river", "Qh Qd", "7d 3s 7h 6d 5h", 8),
    ("river", "2c 2s", "Tc 2d 8d 4s 5s", 9),
    ("river", "As Ah", "Qh 3d Ad Ks 6c", 9),
    ("river", "2h 2c", "7d Td 2d 5d 4h", 9),
    ("river", "7h 7d", "Kh 7c Jc 9s Jd", 10),
    ("river", "Ts As", "2s 4d 7s Js 2d", 10),
    ("river", "3h 9s", "9h Kh 3s Qc 3c", 10),
    ("turn", "3h Jc", "5c Kc Kh 7h", 0),
    ("turn", "4d 9s", "8c 2c Qc 3h", 0),
    ("turn", "2h 9s", "Jd 4s 6h 6c", 0),
    ("turn", "Kd Qd", "4s 9d 7h 5c", 1),
    ("turn", "Kd Qs", "Ts 7d Td 4s", 1),
    ("turn", "Kc Js", "3s 4h 6d 6s", 1),
    ("turn", "Ac 5c", "3c 3d 6h 6d", 2),
    ("turn", "Ah 4c", "Kd Kc 6d 5d", 2),
    ("turn", "Ac 7s", "Qs Qc Tc Ts", 2),
    ("turn", "Ad Qc", "9s 8s 9d 9c", 3),
    ("turn", "Ks Ac", "9d 9h 5s 4s", 3),
    ("turn", "Qc Ac", "7s 4h 3d Js", 3),
    ("turn", "4s Kd", "7c 6s 3d Qd", 4),
    ("turn", "8h 5c", "4d 3d 4s Ad", 4),
    ("turn", "Js 8h", "4d Qh 6h 7c", 4),
    ("turn", "4h 2h", "9c 2c 3h 9h", 5),
    ("turn", "2s Js", "7s 9c 5c 9s", 5),
    ("turn", "4c Kh", "3c 5c 2h 7h", 5),
    ("turn", "Td Qs", "Qd 9s Kd Ks", 6),
    ("turn", "3d Qc", "Td 3h Ks 9c", 6),
    ("turn", "8d 7d", "8h Jh 9h Jd", 6),
    ("turn", "Td 2d", "Jd 8c Jc 2c", 7),
    ("turn", "4h 6c", "8c 4d Tc 3s", 7),
    ("turn", "3h 3d", "6d 9c Kh Qc", 7),
    ("turn", "8c Tc", "Qs Ts 3c 3s", 8),
    ("turn", "Jh 6s", "Qs 9s Qh Jd", 8),
    ("turn", "2d Qd", "Ah Qs Ac 3d", 8),
    ("turn", "Kc Ts", "Ks Qc 6h Qh", 9),
    ("turn", "Js Ac", "Ah 5h 5s 8d", 9),
    ("turn", "Js 9h", "Jd 2c Ts 4d", 9),
    ("turn", "Kh Td", "6h Ts 5h 9h", 10),
    ("turn", "Ad 8s", "8c 5h 3d 3c", 10),
    ("turn", "Kc Ac", "9c Kd Tc 2h", 10),
    ("turn", "Ks Kh", "2h 2c 8s 8c", 11),
    ("turn", "Qc Qs", "6c 5c 5s 2s", 11),
    ("turn", "Qh Qd", "7d 3s 7h 6d", 11),
    ("turn", "7h 7d", "Kh 7c Jc 9s", 12),
    ("turn", "2c 2s", "Tc 2d 8d 4s", 12),
    ("turn", "As Ah", "Qh 3d Ad Ks", 12),
    ("turn", "Ts As", "2s 4d 7s Js", 13),
    ("turn", "3h 9s", "9h Kh 3s Qc", 13),
    ("turn", "4c 9d", "2d 4d 7d Kd", 13),
]


@pytest.mark.parametrize("street,hole,board,expected", H2N_VECTORS)
def test_h2n_vectors(street, hole, board, expected):
    b = board.split()
    assert len(b) == {"flop": 3, "turn": 4, "river": 5}[street]
    assert category(hole.split(), b) == expected


def test_categories_all_streets():
    got = categories(_cards("KhAd"), _cards("Kc7c2s3dJh"))
    assert got == {"flop": _idx("flop", "TPGK"), "turn": _idx("turn", "TPGK"),
                   "river": _idx("river", "TPTK")}
    assert categories(_cards("KhAd"), _cards("Kc7c2s")) == {"flop": _idx("flop", "TPGK")}
    assert categories(_cards("KhAd"), []) == {}


# --- H2N-COMPATIBLE-STATS.md 6.5 board categories ------------------------------

def _boards(street: str, board: str) -> set[str]:
    return {BOARD_CATEGORIES[street][i].label for i in board_categories(_cards(board), street)}


@pytest.mark.parametrize("board,expected", [
    ("Kh7d2c", {"Rainbow"}),
    ("Kh7h2h", {"Suited"}),
    ("Kh7h2c", set()),                   # two-tone: neither
    ("AhKd2c", {"Rainbow", "Ace High"}),
    ("KhKd7c", {"Rainbow", "Paired"}),
    ("7h7d7c", {"Rainbow"}),             # trips are not "Paired"
    ("AhAd7h", {"Ace High", "Paired"}),
])
def test_flop_board_categories(board, expected):
    assert _boards("flop", board) == expected


@pytest.mark.parametrize("board,expected", [
    ("Kh7d2c3s", {"Rainbow"}),
    ("Kh7h2c3h", {"Third Card to Flush"}),
    ("Kh7h2h3h", set()),                 # 4-flush: turn suit was 3 times on the flop
    ("Ah7d2c3d", {"Ace High"}),
])
def test_turn_board_categories(board, expected):
    assert _boards("turn", board) == expected


@pytest.mark.parametrize("board,expected", [
    ("Kh7d2cQsAd", {"Ace High", "Over Card"}),
    ("Kh7d2cQsKd", set()),               # equal to the top card is not an over card
    ("Kh7d2cQhJh", {"Third Card to Flush"}),
    ("Kh7h2cQhJh", set()),               # river suit already three times
    ("9h7d2s3s4s", {"Third Card to Flush"}),
    ("9h7d2c3sTc", {"Over Card"}),
])
def test_river_board_categories(board, expected):
    assert _boards("river", board) == expected


def test_board_categories_default_street_and_short_board():
    assert board_categories(_cards("Kh7d2c")) == [0]
    assert board_categories(_cards("Kh7d2c"), "turn") == []


# --- classify_for_player ----------------------------------------------------

def _hand(actions: dict[str, list[tuple[str, str]]], board: dict, cards: dict,
          extra_boards=None) -> ParsedHand:
    abs_ = {s: [{"username": u, "action": a, "amount": Decimal("0"), "is_all_in": False,
                 "order": i} for i, (u, a) in enumerate(actions.get(s, []))]
            for s in ("preflop", "flop", "turn", "river")}
    return ParsedHand(
        hand_id="T1", site_id=1, played_at=datetime(2026, 1, 1), game_type="NLHE",
        game_mode="", stakes="0.05/0.10", sb_amount=Decimal("0.05"),
        bb_amount=Decimal("0.10"), table_name="t", table_size=6, button_seat=1,
        seats=[], actions_by_street=abs_, board_cards=board, hero_cards=cards,
        uncalled_returns={}, collected={}, total_rake=Decimal("0"),
        total_jackpot=Decimal("0"), went_to_showdown_players=set(), in_showdown=False,
        sb_player=None, bb_player=None, raw_text="", extra_boards=extra_boards or [],
        rit_boards=1 + len(extra_boards or []),
    )


FULL_BOARD = {"flop": ["Kc", "7c", "2s"], "turn": ["3d"], "river": ["Jh"]}


def test_classify_player_who_saw_every_street():
    p = _hand({"preflop": [("Hero", "raise"), ("V", "call")],
               "flop": [("V", "check"), ("Hero", "bet"), ("V", "call")],
               "turn": [("V", "check"), ("Hero", "check")],
               "river": [("V", "check"), ("Hero", "check")]},
              FULL_BOARD, {"Hero": ("Kh", "Ad"), "V": ("9h", "8h")})
    assert classify_for_player(p, "Hero") == {
        "hv_flop": _idx("flop", "TPGK"), "hv_turn": _idx("turn", "TPGK"),
        "hv_river": _idx("river", "TPTK")}
    assert classify_for_player(p, "V") == {
        "hv_flop": _idx("flop", "Trash"), "hv_turn": _idx("turn", "Trash"),
        "hv_river": _idx("river", "Missed Trash")}


def test_classify_player_who_folded_on_the_turn():
    p = _hand({"preflop": [("Hero", "raise"), ("V", "call")],
               "flop": [("V", "check"), ("Hero", "bet"), ("V", "call")],
               "turn": [("V", "bet"), ("Hero", "fold")]},
              {"flop": ["Kc", "7c", "2s"], "turn": ["3d"], "river": []},
              {"Hero": ("Kh", "9d")})
    assert classify_for_player(p, "Hero") == {
        "hv_flop": _idx("flop", "TPWK"), "hv_turn": _idx("turn", "TPWK"), "hv_river": None}


def test_classify_player_who_folded_on_the_flop():
    p = _hand({"preflop": [("Hero", "raise"), ("V", "call")],
               "flop": [("V", "bet"), ("Hero", "fold")]},
              {"flop": ["Kc", "7c", "2s"], "turn": [], "river": []},
              {"Hero": ("Jh", "9d")})
    assert classify_for_player(p, "Hero") == {
        "hv_flop": _idx("flop", "Trash"), "hv_turn": None, "hv_river": None}


def test_classify_preflop_fold_and_unknown_cards():
    p = _hand({"preflop": [("Hero", "fold"), ("V", "raise")]}, FULL_BOARD,
              {"Hero": ("Kh", "Ad")})
    assert classify_for_player(p, "Hero") == {"hv_flop": None, "hv_turn": None, "hv_river": None}
    assert classify_for_player(p, "V") == {"hv_flop": None, "hv_turn": None, "hv_river": None}


def test_other_needs_an_action_on_the_street():
    # Quads aces with king kicker on board: "Other" (best possible hand on board).
    board = {"flop": ["As", "Ah", "Ad"], "turn": ["Ac"], "river": ["Ks"]}
    acted = _hand({"preflop": [("Hero", "raise"), ("V", "call")],
                   "flop": [("V", "check"), ("Hero", "check")],
                   "turn": [("V", "check"), ("Hero", "check")],
                   "river": [("V", "check"), ("Hero", "check")]},
                  board, {"Hero": ("Qh", "Qd")})
    assert classify_for_player(acted, "Hero")["hv_river"] == OTHER
    # All-in preflop: no river action, so no category instead of "Other"
    allin = _hand({"preflop": [("Hero", "raise"), ("V", "call")]}, board,
                  {"Hero": ("Qh", "Qd")})
    assert classify_for_player(allin, "Hero")["hv_river"] is None
    # H2N stops at the last street on which anyone acted (Hand2Note results, parity
    # round 3): the run-out after a preflop all-in gets no category at all.
    # (This used to expect a flop category; Hand2Note leaves it empty.)
    assert classify_for_player(allin, "Hero") == {"hv_flop": None, "hv_turn": None,
                                                  "hv_river": None}
    # ...but a street where others kept acting is classified without a
    # player action (only "Other" needs one).
    side = _hand({"preflop": [("Hero", "raise"), ("V", "call"), ("W", "call")],
                  "flop": [("V", "bet"), ("W", "call")]},
                 {"flop": ["Ks", "7h", "2d"], "turn": ["4c"], "river": ["9s"]},
                 {"Hero": ("Qh", "Qd")})
    hv = classify_for_player(side, "Hero")
    assert hv["hv_flop"] is not None and hv["hv_turn"] is None and hv["hv_river"] is None


def test_classify_run_it_twice_boards():
    board = {"flop": ["Kc", "7c", "2s"], "turn": ["3d"], "river": ["Jh"]}
    p = _hand({"preflop": [("Hero", "raise"), ("V", "call")],
               "flop": [("V", "bet"), ("Hero", "raise"), ("V", "call")]},
              board, {"Hero": ("Kh", "Ad")},
              extra_boards=[{"flop": [], "turn": ["Ah"], "river": ["9c"]}])
    first, second = classify_boards_for_player(p, "Hero")
    assert first == classify_for_player(p, "Hero")
    assert first["hv_flop"] == _idx("flop", "TPGK")
    assert second["hv_flop"] == first["hv_flop"]       # shared flop
    # The boards split after the last action, and H2N classifies only up to
    # the last street with actions (Hand2Note results, parity round 3), so the run-out
    # streets get no category on any board. (This used to expect turn TPGK /
    # Two Pairs+; Hand2Note leaves both empty.)
    assert first["hv_turn"] is None and second["hv_turn"] is None
    assert first["hv_river"] is None and second["hv_river"] is None


def test_classify_bad_cards_yield_none():
    p = _hand({"preflop": [("Hero", "call")]}, FULL_BOARD, {"Hero": ("Kh", "??")})
    assert classify_for_player(p, "Hero") == {"hv_flop": None, "hv_turn": None, "hv_river": None}
    dup = _hand({"preflop": [("Hero", "call")]}, FULL_BOARD, {"Hero": ("Kc", "Ad")})
    assert classify_for_player(dup, "Hero") == {"hv_flop": None, "hv_turn": None, "hv_river": None}


def test_apply_hand_values_fills_every_player():
    p = _hand({"preflop": [("Hero", "raise"), ("V", "call"), ("X", "fold")],
               "flop": [("V", "check"), ("Hero", "bet"), ("V", "fold")]},
              {"flop": ["Kc", "7c", "2s"], "turn": [], "river": []},
              {"Hero": ("Kh", "Ad")})
    stats = {"Hero": {"vpip": True}, "V": {}, "X": {}}
    apply_hand_values(p, stats)
    assert stats["Hero"] == {"vpip": True, "hv_flop": _idx("flop", "TPGK"),
                             "hv_turn": None, "hv_river": None}
    assert stats["V"] == stats["X"] == {"hv_flop": None, "hv_turn": None, "hv_river": None}


def test_compute_stat_flags_writes_hv_columns():
    from pathlib import Path

    from app.parsers.ggpoker import parse_hand_history
    from app.stat_flags import compute_stat_flags

    text = (Path(__file__).parent / "fixtures" / "ggpoker" / "split_pot.txt").read_text()
    parsed = parse_hand_history(text.split("\n\n\n")[0])
    flags = compute_stat_flags(parsed)
    # Hero AhKd on Ac Kc 9h 2d 5s: two pair on every street
    assert flags["Hero"]["hv_flop"] == _idx("flop", "Two Pairs+")
    assert flags["Hero"]["hv_turn"] == _idx("turn", "Two Pairs+")
    assert flags["Hero"]["hv_river"] == _idx("river", "Two Pairs+")
    assert flags["Player3"]["hv_flop"] is None  # folded preflop, cards unknown
