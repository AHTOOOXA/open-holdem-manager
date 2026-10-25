"""
Registry mapping stat keys to their DB column names for detail drill-down.

Each entry defines:
  - name: Display name
  - action_flag: column that must be true for "action taken"
  - action_sql: raw SQL expression for action (overrides action_flag if present)
  - opp_flag: column that must be true for "had opportunity" (denominator)
  - opp_sql: raw SQL expression for opportunity (overrides opp_flag if present)
  - opp_is_not_null: if True, opportunity = opp_flag IS NOT NULL (for fold_to_* stats
    where NULL means no opportunity, True/False means had opportunity)
  - extra_where: extra SQL condition on the opportunity hands
  - h2n_row: the H2N matcher row (app.h2n.rows) the stat counts, if any

Every stat with a twin on Hand2Note's General screen reads the H2N matcher
bits (hand_players.h2n_pre_* / h2n_post_*, app/h2n/CONTRACT.md) with the same
row and hero-position set as the General cell (app/general_cells.py), so the
Stats page, its drill-downs and the General screen count the same hands.
Stats without an H2N twin (OHM_ONLY_STATS) keep the classic OHM flag columns.
Hands H2N refuses to import (hand_players.h2n_valid FALSE) are left out of
every stat, like in H2N.
"""

from app.h2n.rows import ROWS, sql_case, sql_opp

# H2N column group of the player (EP / MP / CO / BTN / SB / BB, heads-up
# button = SB). Falls back to OHM's label for rows written before the H2N layer.
POS_SQL = "COALESCE(hp.h2n_pos, hp.position)"
# FALSE = H2N would refuse to import the hand: it is in none of its stats.
VALID_SQL = "COALESCE(hp.h2n_valid, TRUE)"

# H2N steal positions (the heads-up button is in SB). CO is not a steal seat.
BTN_SB = ("BTN", "SB")


def case_sql(row: str, alias: str = "hp") -> str:
    """Boolean SQL: the player-hand is a case of H2N row `row`."""
    return f"({sql_case(row, alias)} = 1)"


def opp_sql(row: str, alias: str = "hp") -> str:
    """Boolean SQL: the player-hand is an opportunity of H2N row `row`."""
    return f"({sql_opp(row, alias)} = 1)"


def pos_in_sql(positions: tuple[str, ...], exclude: bool = False) -> str:
    """Boolean SQL: the player's H2N column group is (not) in `positions`."""
    vals = ", ".join(f"'{p}'" for p in positions)
    if exclude:
        return f"COALESCE({POS_SQL}, '') NOT IN ({vals})"
    return f"{POS_SQL} IN ({vals})"


def _h2n(name: str, row: str, positions: tuple[str, ...] | None = None,
         exclude: bool = False) -> dict:
    """Entry for an H2N action stat: cases / opps of one row, optionally
    restricted to a hero position set (the General cell's hero positions)."""
    entry = {"name": name, "action_sql": case_sql(row), "opp_sql": opp_sql(row), "h2n_row": row}
    if positions is not None:
        entry["opp_sql"] += f" AND {pos_in_sql(positions, exclude)}"
    return entry


def _vs_steal_sql(fn, row_sb: str, row_bb: str) -> str:
    """vs. Steal: hero SB uses the BTN-steal row, hero BB the BTN/SB-steal row."""
    return f"(({fn(row_sb)} AND {POS_SQL} = 'SB') OR ({fn(row_bb)} AND {POS_SQL} = 'BB'))"


def _vs_steal(name: str, row_sb: str, row_bb: str) -> dict:
    return {
        "name": name,
        "action_sql": _vs_steal_sql(case_sql, row_sb, row_bb),
        "opp_sql": _vs_steal_sql(opp_sql, row_sb, row_bb),
    }


def _hits(name: str, action_row: str, base_row: str) -> dict:
    """Hands with a hit of `action_row` among the hits of `base_row` (per-street
    single-action rows: Aggression, AFq)."""
    return {"name": name, "action_sql": case_sql(action_row), "opp_sql": case_sql(base_row)}


STAT_REGISTRY: dict[str, dict] = {
    # ── Preflop ──
    "vpip": _h2n("VPIP", "V01"),
    "pfr": _h2n("PFR", "V02"),
    "open_raise": _h2n("Open Raise", "P01"),
    "call_open_raise": _h2n("Call Open Raise", "P06"),
    # Total column: H2N's built-in 3-Bet (any raise facing one raise, squeezes in)
    "three_bet": _h2n("3-Bet", "P07"),
    # Position columns of the 3-Bet row: the opener's raise re-raised directly
    # (squeezes out), so they don't add up to the Total
    "three_bet_vs_open": _h2n("3-Bet vs Open Raise", "P08"),
    "three_bet_ip": _h2n("3-Bet IP", "P09"),
    "three_bet_oop": _h2n("3-Bet OOP", "P10"),
    "four_bet": _h2n("4-Bet", "P13"),
    "five_bet": _h2n("5-Bet", "P21"),
    "fold_to_3bet": _h2n("Fold to 3-Bet", "P03"),
    "fold_to_4bet": _h2n("Fold to 4-Bet", "P19"),
    "limp": _h2n("Limp", "P22"),
    "squeeze": _h2n("Squeeze", "P24"),
    "limp_fold": _h2n("Limp-Fold", "P23", ("BB",), exclude=True),
    "four_bet_fold": _h2n("4-Bet-Fold", "P16"),
    "call_4bet": _h2n("Call 4-Bet", "P20"),
    # Expression cases(Open) * cases(4-Bet) / opps(Open) / opps(4-Bet): the
    # drill-down lists the 4-bet hands among the open-raise opportunities.
    "four_bet_range": {
        "name": "4-Bet Range",
        "action_sql": case_sql("P13"),
        "opp_sql": opp_sql("P01"),
    },
    "bb_defense": {
        "name": "BB Defense",
        "action_flag": "bb_defense",
        "opp_flag": "bb_defense_opp",
    },
    "iso_raise": {
        "name": "Iso Raise",
        "action_flag": "iso_raise",
        "opp_flag": "iso_raise_opp",
    },
    "fold_to_squeeze": {
        "name": "Fold to Squeeze",
        "action_flag": "fold_to_squeeze",
        "opp_flag": "fold_to_squeeze",
        "opp_is_not_null": True,
    },
    # ── Steal (hero BTN or SB; the heads-up button is SB) ──
    "steal": _h2n("Steal", "P02", BTN_SB),
    # Total columns of the steal table
    "fold_to_3bet_steal": _h2n("Fold to 3-Bet (Steal)", "P05", BTN_SB),
    "four_bet_steal": _h2n("4-Bet (Steal)", "P15", BTN_SB),
    "four_bet_fold_steal": _h2n("4-Bet-Fold (Steal)", "P18", BTN_SB),
    # BTN / SB columns: any 3-bettor. (Fold to 3-Bet BTN is "fold_to_3bet".)
    "fold_to_3bet_open": _h2n("Fold to 3-Bet (Open)", "P04", BTN_SB),
    "four_bet_open": _h2n("4-Bet (Open)", "P14", BTN_SB),
    "four_bet_fold_open": _h2n("4-Bet-Fold (Open)", "P17", BTN_SB),
    # ── vs Steal (hero SB vs a BTN steal, hero BB vs a BTN/SB steal) ──
    "fold_to_steal": _vs_steal("Fold to Steal", "P25F", "P26F"),
    "call_steal": _vs_steal("Call Steal", "P25C", "P26C"),
    "three_bet_vs_steal": _vs_steal("3-Bet vs Steal", "P25R", "P26R"),
    # ── Postflop: C-Bet ──
    "cbet_flop": _h2n("C-Bet Flop", "C01"),
    "cbet_turn": _h2n("C-Bet Turn", "C02"),
    "cbet_river": _h2n("C-Bet River", "C03"),
    # ── Postflop: Fold to C-Bet ──
    "fold_to_cbet_flop": _h2n("Fold to CBet Flop", "C04"),
    "fold_to_cbet_turn": _h2n("Fold to CBet Turn", "C05"),
    "fold_to_cbet_river": _h2n("Fold to CBet River", "C06"),
    # ── Postflop: vs C-Bet Flop (Raised Pot) ──
    # Fold is H2N's Fold to CBet Flop stat itself (its own preflop condition)
    "fold_cbet_flop_raised": _h2n("Fold to CBet (Raised Pot)", "C04"),
    "call_cbet_flop_raised": _h2n("Call CBet (Raised Pot)", "C07"),
    "raise_cbet_flop_raised": _h2n("Raise CBet (Raised Pot)", "C08"),
    # ── Postflop: vs C-Bet Flop (3-Bet Pot: hero opened and called a 3-bet) ──
    "fold_cbet_flop_3bet": _h2n("Fold to CBet (3-Bet Pot)", "C09"),
    "call_cbet_flop_3bet": _h2n("Call CBet (3-Bet Pot)", "C10"),
    "raise_cbet_flop_3bet": _h2n("Raise CBet (3-Bet Pot)", "C11"),
    # ── Postflop: Donk Bet ──
    "donk_bet_flop": _h2n("Donk Bet Flop", "C12"),
    "donk_bet_turn": _h2n("Donk Bet Turn", "C13"),
    "donk_bet_river": _h2n("Donk Bet River", "C14"),
    # ── Missed C-Bet ──
    "missed_cbet_flop": _h2n("Missed C-Bet Flop", "M01"),
    "missed_cbet_flop_ip": _h2n("Missed C-Bet IP", "M02"),
    "missed_cbet_flop_oop": _h2n("Missed C-Bet OOP", "M03"),
    "missed_cbet_fold_ip": _h2n("Missed C-Bet → Fold IP", "M04"),
    "missed_cbet_fold_oop": _h2n("Missed C-Bet → Fold OOP", "M05"),
    # ── vs Missed C-Bet ──
    # Expression (cases(A) + cases(B)) / (opps(A) + opps(B)), A = N06 (turn
    # bet after a checked-through flop), B = N05 (flop stab IP), any preflop raise
    "vs_missed_cbet": {
        "name": "vs Missed C-Bet",
        "action_sql": f"({case_sql('N05')} OR {case_sql('N06')})",
        "opp_sql": f"({opp_sql('N05')} OR {opp_sql('N06')})",
    },
    "vs_missed_cbet_bet_ip": _h2n("vs Missed C-Bet Bet IP", "N01"),
    "vs_missed_cbet_check_fold_ip": _h2n("vs Missed C-Bet Check-Fold IP", "N02"),
    "vs_missed_cbet_bet_oop_turn": _h2n("vs Missed C-Bet Bet OOP Turn", "N03"),
    "vs_missed_cbet_check_fold_oop": _h2n("vs Missed C-Bet Check-Fold OOP", "N04"),
    # ── Aggression (per hand: hands with a bet or raise among hands with any
    # action on the street; the Aggression value itself is a ratio of hands) ──
    "af_flop": _hits("Aggression Flop", "E_FLOP_BR", "E_FLOP_ANY"),
    "af_turn": _hits("Aggression Turn", "E_TURN_BR", "E_TURN_ANY"),
    "af_river": _hits("Aggression River", "E_RIVER_BR", "E_RIVER_ANY"),
    "afq_flop": _hits("Agg Freq Flop", "E_FLOP_BR", "E_FLOP_ANY"),
    "afq_turn": _hits("Agg Freq Turn", "E_TURN_BR", "E_TURN_ANY"),
    "afq_river": _hits("Agg Freq River", "E_RIVER_BR", "E_RIVER_ANY"),
    # ── Showdown ──
    "saw_flop": {
        "name": "Saw Flop",
        "action_flag": "saw_flop",
        "opp_flag": None,
    },
    # Base = hands with a flop action (preflop all-ins left out)
    "went_to_showdown": {
        "name": "Went to Showdown",
        "action_flag": "went_to_showdown",
        "opp_sql": case_sql("E_FLOP_ANY"),
    },
    # Showdowns of hands with any preflop raise/call/check (preflop all-ins in);
    # "won" = H2N's is-winner (split pots count)
    "won_at_showdown": {
        "name": "Won at Showdown",
        "action_flag": "is_winner",
        "opp_sql": f"{case_sql('V03')} AND hp.went_to_showdown = TRUE",
    },
    "wwsf": {
        "name": "Won When Saw Flop",
        "action_flag": "is_winner",
        "opp_sql": case_sql("E_FLOP_ANY"),
    },
}

# Stats kept on classic OHM flags: no twin on H2N's General screen.
OHM_ONLY_STATS: frozenset[str] = frozenset({
    "bb_defense", "iso_raise", "fold_to_squeeze", "saw_flop",
})

# H2N would not have imported these hands: leave them out of every stat.
for _entry in STAT_REGISTRY.values():
    _extra = _entry.get("extra_where")
    _entry["extra_where"] = f"{VALID_SQL} AND ({_extra})" if _extra else VALID_SQL
del _entry, _extra


def get_key_street(stat_key: str) -> str | None:
    """Return the key street for a stat (preflop/flop/turn/river), or None for showdown stats."""
    if stat_key in ("saw_flop", "went_to_showdown", "won_at_showdown", "wwsf"):
        return None
    row = STAT_REGISTRY.get(stat_key, {}).get("h2n_row")
    if row:
        return ROWS[row].street  # the street of the measured decision
    if "flop" in stat_key or stat_key in (
        "vs_missed_cbet", "vs_missed_cbet_bet_ip",
        "vs_missed_cbet_check_fold_ip", "vs_missed_cbet_check_fold_oop",
    ):
        return "flop"
    if "turn" in stat_key:
        return "turn"
    if "river" in stat_key:
        return "river"
    return "preflop"
