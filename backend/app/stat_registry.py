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
"""

STAT_REGISTRY: dict[str, dict] = {
    # ── Preflop ──
    "vpip": {
        "name": "VPIP",
        "action_flag": "vpip",
        "opp_flag": None,  # every hand is an opportunity
    },
    "pfr": {
        "name": "PFR",
        "action_flag": "pfr",
        "opp_flag": None,
    },
    "open_raise": {
        "name": "Open Raise",
        "action_flag": "open_raise",
        "opp_flag": "open_raise_opp",
    },
    "call_open_raise": {
        "name": "Call Open Raise",
        "action_flag": "call_open_raise",
        "opp_flag": None,
    },
    "three_bet": {
        "name": "3-Bet",
        "action_flag": "three_bet",
        "opp_flag": "three_bet_opp",
    },
    "three_bet_ip": {
        "name": "3-Bet IP",
        "action_flag": "three_bet",
        "opp_flag": "three_bet_opp",
        "extra_where": "hp.position IN ('CO', 'BTN')",
    },
    "three_bet_oop": {
        "name": "3-Bet OOP",
        "action_flag": "three_bet",
        "opp_flag": "three_bet_opp",
        "extra_where": "hp.position IN ('SB', 'BB', 'EP', 'MP')",
    },
    "four_bet": {
        "name": "4-Bet",
        "action_flag": "four_bet",
        "opp_flag": "four_bet_opp",
    },
    "five_bet": {
        "name": "5-Bet",
        "action_flag": "five_bet",
        "opp_flag": "five_bet_opp",
    },
    "fold_to_3bet": {
        "name": "Fold to 3-Bet",
        "action_flag": "fold_to_3bet",
        "opp_flag": "fold_to_3bet",
        "opp_is_not_null": True,
    },
    "fold_to_4bet": {
        "name": "Fold to 4-Bet",
        "action_flag": "fold_to_4bet",
        "opp_flag": "fold_to_4bet",
        "opp_is_not_null": True,
    },
    "limp": {
        "name": "Limp",
        "action_flag": "limp",
        "opp_flag": None,
    },
    "squeeze": {
        "name": "Squeeze",
        "action_flag": "squeeze",
        "opp_flag": "squeeze_opp",
    },
    "limp_fold": {
        "name": "Limp-Fold",
        "action_sql": "hp.limp = TRUE AND hp.saw_flop IS NOT TRUE",
        "opp_sql": "hp.limp = TRUE",
    },
    "four_bet_fold": {
        "name": "4-Bet-Fold",
        "action_sql": "hp.four_bet = TRUE AND hp.saw_flop IS NOT TRUE",
        "opp_sql": "hp.four_bet = TRUE",
    },
    "call_4bet": {
        "name": "Call 4-Bet",
        "action_sql": "hp.fold_to_4bet = FALSE AND hp.five_bet IS NOT TRUE",
        "opp_sql": "hp.fold_to_4bet IS NOT NULL",
    },
    "four_bet_range": {
        "name": "4-Bet Range",
        "action_flag": "four_bet",
        "opp_flag": None,
    },
    # ── Steal ──
    "steal": {
        "name": "Steal",
        "action_flag": "steal_attempted",
        "opp_flag": "steal_opp",
    },
    "fold_to_steal": {
        "name": "Fold to Steal",
        "action_flag": "fold_to_steal",
        "opp_flag": "faced_steal",
    },
    "call_steal": {
        "name": "Call Steal",
        "action_flag": "call_steal",
        "opp_flag": "faced_steal",
    },
    "three_bet_vs_steal": {
        "name": "3-Bet vs Steal",
        "action_flag": "three_bet_vs_steal",
        "opp_flag": "faced_steal",
    },
    # ── Postflop: C-Bet ──
    "cbet_flop": {
        "name": "C-Bet Flop",
        "action_flag": "cbet_flop",
        "opp_flag": "cbet_flop_opp",
    },
    "cbet_turn": {
        "name": "C-Bet Turn",
        "action_flag": "cbet_turn",
        "opp_flag": "cbet_turn_opp",
    },
    "cbet_river": {
        "name": "C-Bet River",
        "action_flag": "cbet_river",
        "opp_flag": "cbet_river_opp",
    },
    # ── Postflop: Fold to C-Bet ──
    "fold_to_cbet_flop": {
        "name": "Fold to CBet Flop",
        "action_flag": "fold_to_cbet_flop",
        "opp_flag": "fold_to_cbet_flop",
        "opp_is_not_null": True,
    },
    "fold_to_cbet_turn": {
        "name": "Fold to CBet Turn",
        "action_flag": "fold_to_cbet_turn",
        "opp_flag": "fold_to_cbet_turn",
        "opp_is_not_null": True,
    },
    "fold_to_cbet_river": {
        "name": "Fold to CBet River",
        "action_flag": "fold_to_cbet_river",
        "opp_flag": "fold_to_cbet_river",
        "opp_is_not_null": True,
    },
    # ── Postflop: vs C-Bet Flop (Raised Pot) ──
    "fold_cbet_flop_raised": {
        "name": "Fold to CBet (Raised Pot)",
        "action_flag": "fold_to_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)",
    },
    "call_cbet_flop_raised": {
        "name": "Call CBet (Raised Pot)",
        "action_flag": "call_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)",
    },
    "raise_cbet_flop_raised": {
        "name": "Raise CBet (Raised Pot)",
        "action_flag": "raise_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)",
    },
    # ── Postflop: vs C-Bet Flop (3-Bet Pot) ──
    "fold_cbet_flop_3bet": {
        "name": "Fold to CBet (3-Bet Pot)",
        "action_flag": "fold_to_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE",
    },
    "call_cbet_flop_3bet": {
        "name": "Call CBet (3-Bet Pot)",
        "action_flag": "call_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE",
    },
    "raise_cbet_flop_3bet": {
        "name": "Raise CBet (3-Bet Pot)",
        "action_flag": "raise_cbet_flop",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE",
    },
    # ── Steal: 4-Bet-Fold ──
    "four_bet_fold_steal": {
        "name": "4-Bet-Fold (Steal)",
        "action_flag": "four_bet_fold",
        "opp_flag": "four_bet_fold",
        "opp_is_not_null": True,
        "extra_where": "hp.steal_attempted = TRUE",
    },
    # ── Postflop: Donk Bet ──
    "donk_bet_flop": {
        "name": "Donk Bet Flop",
        "action_flag": "donk_bet_flop",
        "opp_flag": "donk_bet_flop_opp",
    },
    "donk_bet_turn": {
        "name": "Donk Bet Turn",
        "action_flag": "donk_bet_turn",
        "opp_flag": "donk_bet_turn_opp",
    },
    "donk_bet_river": {
        "name": "Donk Bet River",
        "action_flag": "donk_bet_river",
        "opp_flag": "donk_bet_river_opp",
    },
    # ── Missed C-Bet ──
    "missed_cbet_flop": {
        "name": "Missed C-Bet Flop",
        "action_flag": "missed_cbet_flop",
        "opp_flag": "cbet_flop_opp",
    },
    "missed_cbet_flop_ip": {
        "name": "Missed C-Bet IP",
        "action_flag": "missed_cbet_flop",
        "opp_flag": "cbet_flop_opp",
        "extra_where": "hp.position IN ('CO', 'BTN')",
    },
    "missed_cbet_flop_oop": {
        "name": "Missed C-Bet OOP",
        "action_flag": "missed_cbet_flop",
        "opp_flag": "cbet_flop_opp",
        "extra_where": "hp.position NOT IN ('CO', 'BTN')",
    },
    "missed_cbet_fold_ip": {
        "name": "Missed C-Bet → Fold IP",
        "action_sql": "hp.flop_folds > 0",
        "opp_sql": "hp.missed_cbet_flop = TRUE AND hp.position IN ('CO', 'BTN')",
    },
    "missed_cbet_fold_oop": {
        "name": "Missed C-Bet → Fold OOP",
        "action_sql": "hp.flop_folds > 0",
        "opp_sql": "hp.missed_cbet_flop = TRUE AND hp.position NOT IN ('CO', 'BTN')",
    },
    # ── vs Missed C-Bet ──
    "vs_missed_cbet": {
        "name": "vs Missed C-Bet",
        "action_sql": "hp.flop_bets > 0",
        "opp_sql": "hp.saw_flop = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL",
    },
    "vs_missed_cbet_bet_ip": {
        "name": "vs Missed C-Bet Bet IP",
        "action_sql": "hp.flop_bets > 0",
        "opp_sql": "hp.saw_flop = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL AND hp.position IN ('CO', 'BTN')",
    },
    "vs_missed_cbet_check_fold_ip": {
        "name": "vs Missed C-Bet Check-Fold IP",
        "action_sql": "hp.flop_folds > 0 AND hp.flop_bets = 0",
        "opp_sql": "hp.saw_flop = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL AND hp.position IN ('CO', 'BTN')",
    },
    "vs_missed_cbet_bet_oop_turn": {
        "name": "vs Missed C-Bet Bet OOP Turn",
        "action_sql": "hp.turn_bets > 0",
        "opp_sql": "hp.saw_turn = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL AND hp.position NOT IN ('CO', 'BTN')",
    },
    "vs_missed_cbet_check_fold_oop": {
        "name": "vs Missed C-Bet Check-Fold OOP",
        "action_sql": "hp.flop_folds > 0 AND hp.flop_bets = 0",
        "opp_sql": "hp.saw_flop = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL AND hp.position NOT IN ('CO', 'BTN')",
    },
    # ── Aggression Factor ──
    "af_flop": {
        "name": "Aggression Flop",
        "action_sql": "(hp.flop_bets + hp.flop_raises) > 0",
        "opp_flag": "saw_flop",
    },
    "af_turn": {
        "name": "Aggression Turn",
        "action_sql": "(hp.turn_bets + hp.turn_raises) > 0",
        "opp_flag": "saw_turn",
    },
    "af_river": {
        "name": "Aggression River",
        "action_sql": "(hp.river_bets + hp.river_raises) > 0",
        "opp_flag": "saw_river",
    },
    # ── Aggression Frequency ──
    "afq_flop": {
        "name": "Agg Freq Flop",
        "action_sql": "(hp.flop_bets + hp.flop_raises) > 0",
        "opp_flag": "saw_flop",
    },
    "afq_turn": {
        "name": "Agg Freq Turn",
        "action_sql": "(hp.turn_bets + hp.turn_raises) > 0",
        "opp_flag": "saw_turn",
    },
    "afq_river": {
        "name": "Agg Freq River",
        "action_sql": "(hp.river_bets + hp.river_raises) > 0",
        "opp_flag": "saw_river",
    },
    # ── Showdown ──
    "saw_flop": {
        "name": "Saw Flop",
        "action_flag": "saw_flop",
        "opp_flag": None,
    },
    "went_to_showdown": {
        "name": "Went to Showdown",
        "action_flag": "went_to_showdown",
        "opp_flag": "saw_flop",
    },
    "won_at_showdown": {
        "name": "Won at Showdown",
        "action_flag": "won_at_showdown",
        "opp_flag": "went_to_showdown",
    },
    "wwsf": {
        "name": "Won When Saw Flop",
        "action_flag": "won",
        "opp_flag": "saw_flop",
    },
}


def get_key_street(stat_key: str) -> str | None:
    """Return the key street for a stat (preflop/flop/turn/river), or None for showdown stats."""
    if stat_key in ("saw_flop", "went_to_showdown", "won_at_showdown", "wwsf"):
        return None
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
