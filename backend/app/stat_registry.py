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
        "opp_sql": "hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = TRUE",
    },
    "three_bet_oop": {
        "name": "3-Bet OOP",
        "action_flag": "three_bet",
        "opp_sql": "hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = FALSE",
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


# ── Response Decomposition for defensive stats ──────────────────────
# Maps fold_to_* stat keys to SQL for fold/call/raise breakdown

RESPONSE_DECOMPOSITION: dict[str, dict[str, str]] = {
    "fold_to_3bet": {
        "opp_sql": "hp.fold_to_3bet IS NOT NULL",
        "fold_sql": "hp.fold_to_3bet = TRUE",
        "raise_sql": "hp.four_bet = TRUE",
    },
    "fold_to_4bet": {
        "opp_sql": "hp.fold_to_4bet IS NOT NULL",
        "fold_sql": "hp.fold_to_4bet = TRUE",
        "raise_sql": "hp.five_bet = TRUE",
    },
    "fold_to_cbet_flop": {
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL",
        "fold_sql": "hp.fold_to_cbet_flop = TRUE",
        "raise_sql": "hp.raise_cbet_flop = TRUE",
    },
    "fold_to_cbet_turn": {
        "opp_sql": "hp.fold_to_cbet_turn IS NOT NULL",
        "fold_sql": "hp.fold_to_cbet_turn = TRUE",
        "raise_sql": "hp.turn_raises > 0",
    },
    "fold_to_cbet_river": {
        "opp_sql": "hp.fold_to_cbet_river IS NOT NULL",
        "fold_sql": "hp.fold_to_cbet_river = TRUE",
        "raise_sql": "hp.river_raises > 0",
    },
    "fold_to_steal": {
        "opp_sql": "hp.faced_steal = TRUE",
        "fold_sql": "hp.fold_to_steal = TRUE",
        "raise_sql": "hp.three_bet_vs_steal = TRUE",
    },
    "call_steal": {
        "opp_sql": "hp.faced_steal = TRUE",
        "fold_sql": "hp.fold_to_steal = TRUE",
        "raise_sql": "hp.three_bet_vs_steal = TRUE",
    },
    "three_bet_vs_steal": {
        "opp_sql": "hp.faced_steal = TRUE",
        "fold_sql": "hp.fold_to_steal = TRUE",
        "raise_sql": "hp.three_bet_vs_steal = TRUE",
    },
    "fold_cbet_flop_raised": {
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)",
        "fold_sql": "hp.fold_to_cbet_flop = TRUE",
        "raise_sql": "hp.raise_cbet_flop = TRUE",
    },
    "fold_cbet_flop_3bet": {
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE",
        "fold_sql": "hp.fold_to_cbet_flop = TRUE",
        "raise_sql": "hp.raise_cbet_flop = TRUE",
    },
    "bb_defense": {
        "opp_sql": "hp.bb_defense_opp = TRUE",
        "fold_sql": "hp.bb_defense IS NOT TRUE",
        "raise_sql": "hp.three_bet = TRUE",
    },
    "fold_to_squeeze": {
        "opp_sql": "hp.fold_to_squeeze IS NOT NULL",
        "fold_sql": "hp.fold_to_squeeze = TRUE",
        "raise_sql": "hp.four_bet = TRUE",
    },
}


# ── EV Breakdown Scenarios ────────────────────────────────────────────
# Maps stat_key → list of (label, SQL filter on hero's hand_players row)
EV_BREAKDOWN_CONFIG: dict[str, list[tuple[str, str]]] = {
    "open_raise": [
        ("Fold-through", "hp.open_raise = TRUE AND hp.saw_flop IS NOT TRUE"),
        ("Called", "hp.open_raise = TRUE AND hp.saw_flop = TRUE AND hp.is_3bet_pot IS NOT TRUE"),
        ("3-Bet faced", "hp.open_raise = TRUE AND hp.fold_to_3bet IS NOT NULL"),
    ],
    "fold_to_3bet": [
        ("Fold", "hp.fold_to_3bet = TRUE"),
        ("Call", "hp.fold_to_3bet = FALSE AND hp.four_bet IS NOT TRUE"),
        ("4-Bet", "hp.four_bet = TRUE"),
    ],
    "fold_to_4bet": [
        ("Fold", "hp.fold_to_4bet = TRUE"),
        ("Call", "hp.fold_to_4bet = FALSE AND hp.five_bet IS NOT TRUE"),
        ("5-Bet", "hp.five_bet = TRUE"),
    ],
    "three_bet": [
        ("Fold equity win", "hp.three_bet = TRUE AND hp.saw_flop IS NOT TRUE"),
        ("Called", "hp.three_bet = TRUE AND hp.saw_flop = TRUE"),
        ("4-Bet faced", "hp.three_bet = TRUE AND hp.fold_to_4bet IS NOT NULL"),
    ],
    "vpip": [
        ("Open raise", "hp.open_raise = TRUE"),
        ("Cold call", "hp.call_open_raise = TRUE"),
        ("3-Bet", "hp.three_bet = TRUE"),
        ("Limp", "hp.limp = TRUE"),
        ("Squeeze", "hp.squeeze = TRUE"),
    ],
    "pfr": [
        ("Open raise", "hp.open_raise = TRUE"),
        ("3-Bet", "hp.three_bet = TRUE"),
        ("4-Bet", "hp.four_bet = TRUE"),
        ("Squeeze", "hp.squeeze = TRUE"),
    ],
    "call_open_raise": [
        ("All cold-call pots", "hp.call_open_raise = TRUE"),
    ],
    "limp": [
        ("All limped pots", "hp.limp = TRUE"),
    ],
    "four_bet": [
        ("All 4-bet pots", "hp.four_bet = TRUE"),
    ],
    "five_bet": [
        ("All 5-bet pots", "hp.five_bet = TRUE"),
    ],
    "call_4bet": [
        ("All flat-4bet pots", "hp.call_4bet = TRUE"),
    ],
    "squeeze": [
        ("All squeeze pots", "hp.squeeze = TRUE"),
    ],
    "bb_defense": [
        ("Fold", "hp.bb_defense_opp = TRUE AND hp.bb_defense IS NOT TRUE"),
        ("Call", "hp.bb_defense = TRUE AND hp.three_bet IS NOT TRUE"),
        ("3-Bet", "hp.bb_defense_opp = TRUE AND hp.three_bet = TRUE"),
    ],
    "iso_raise": [
        ("Iso-raised pots", "hp.iso_raise = TRUE"),
        ("Limped-along pots", "hp.limp = TRUE"),
    ],
    "fold_to_squeeze": [
        ("Fold", "hp.fold_to_squeeze = TRUE"),
        ("Call", "hp.fold_to_squeeze = FALSE AND hp.four_bet IS NOT TRUE"),
        ("4-Bet", "hp.faced_squeeze = TRUE AND hp.four_bet = TRUE"),
    ],
    "limp_fold": [
        ("All limp-fold pots", "hp.limp_fold = TRUE"),
    ],
    "four_bet_fold": [
        ("All 4-bet-fold pots", "hp.four_bet_fold = TRUE"),
    ],
    "three_bet_ip": [
        ("Fold equity win", "hp.three_bet = TRUE AND hp.three_bet_opp_ip = TRUE AND hp.saw_flop IS NOT TRUE"),
        ("Called", "hp.three_bet = TRUE AND hp.three_bet_opp_ip = TRUE AND hp.saw_flop = TRUE"),
    ],
    "three_bet_oop": [
        ("Fold equity win", "hp.three_bet = TRUE AND hp.three_bet_opp_ip = FALSE AND hp.saw_flop IS NOT TRUE"),
        ("Called", "hp.three_bet = TRUE AND hp.three_bet_opp_ip = FALSE AND hp.saw_flop = TRUE"),
    ],
}


# ── Sizing Config ─────────────────────────────────────────────────────
# Maps stat_key → (flag_filter_on_hp, action_type_filter)
SIZING_CONFIG: dict[str, tuple[str, str]] = {
    "open_raise": ("hp.open_raise = TRUE", "a.action_type = 'raise'"),
    "iso_raise": ("hp.iso_raise = TRUE", "a.action_type = 'raise'"),
}


# ── Fold Equity Config ───────────────────────────────────────────────
# Maps stat_key → SQL filter for "hero did action"
FOLD_EQUITY_CONFIG: dict[str, str] = {
    "three_bet": "hp.three_bet = TRUE",
    "three_bet_ip": "hp.three_bet = TRUE AND hp.three_bet_opp_ip = TRUE",
    "three_bet_oop": "hp.three_bet = TRUE AND hp.three_bet_opp_ip = FALSE",
    "four_bet": "hp.four_bet = TRUE",
    "squeeze": "hp.squeeze = TRUE",
}


# ── By-Context Config ────────────────────────────────────────────────
# Maps stat_key → (dimension_label, action_sql, opp_sql, join_clause, group_expr)
BY_CONTEXT_CONFIG: dict[str, dict] = {
    "fold_to_3bet": {
        "dimension": "villain_position",
        "action_sql": "hp.fold_to_3bet = TRUE",
        "opp_sql": "hp.fold_to_3bet IS NOT NULL",
        "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.three_bet = TRUE AND v.player_id != hp.player_id",
        "group_expr": "v.position",
    },
    "call_open_raise": {
        "dimension": "opener_position",
        "action_sql": "hp.call_open_raise = TRUE",
        "opp_sql": "hp.call_open_raise_opp = TRUE",
        "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.open_raise = TRUE AND v.player_id != hp.player_id",
        "group_expr": "v.position",
    },
    "three_bet_ip": {
        "dimension": "villain_position",
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = TRUE",
        "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.open_raise = TRUE AND v.player_id != hp.player_id",
        "group_expr": "v.position",
    },
    "bb_defense": {
        "dimension": "raiser_position",
        "action_sql": "hp.bb_defense = TRUE",
        "opp_sql": "hp.bb_defense_opp = TRUE",
        "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.open_raise = TRUE AND v.player_id != hp.player_id",
        "group_expr": "v.position",
    },
    "fold_to_4bet": {
        "dimension": "hero_position",
        "action_sql": "hp.fold_to_4bet = TRUE",
        "opp_sql": "hp.fold_to_4bet IS NOT NULL",
        "join": "",
        "group_expr": "hp.position",
    },
    "squeeze": {
        "dimension": "callers",
        "action_sql": "hp.squeeze = TRUE",
        "opp_sql": "hp.squeeze_opp = TRUE",
        "join": "",
        "group_expr": "CASE WHEN (SELECT COUNT(*) FROM hand_players v WHERE v.hand_id = hp.hand_id AND v.call_open_raise = TRUE) >= 2 THEN '2+' ELSE '1' END",
    },
    "iso_raise": {
        "dimension": "limpers",
        "action_sql": "hp.iso_raise = TRUE",
        "opp_sql": "hp.iso_raise_opp = TRUE",
        "join": "",
        "group_expr": "CASE WHEN (SELECT COUNT(*) FROM hand_players v WHERE v.hand_id = hp.hand_id AND v.limp = TRUE) >= 2 THEN '2+' ELSE '1' END",
    },
    "fold_to_squeeze": {
        "dimension": "squeezer_position",
        "action_sql": "hp.fold_to_squeeze = TRUE",
        "opp_sql": "hp.fold_to_squeeze IS NOT NULL",
        "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.squeeze = TRUE AND v.player_id != hp.player_id",
        "group_expr": "v.position",
    },
    "vpip": {
        "dimension": "position",
        "action_sql": "hp.vpip = TRUE",
        "opp_sql": "1=1",
        "join": "",
        "group_expr": "hp.position",
    },
    "pfr": {
        "dimension": "position",
        "action_sql": "hp.pfr = TRUE",
        "opp_sql": "1=1",
        "join": "",
        "group_expr": "hp.position",
    },
    "limp_fold": {
        "dimension": "position",
        "action_sql": "hp.limp_fold = TRUE",
        "opp_sql": "hp.limp = TRUE",
        "join": "",
        "group_expr": "hp.position",
    },
}


# ── Composition Config ───────────────────────────────────────────────
COMPOSITION_CONFIG: dict[str, list[tuple[str, str]]] = {
    "vpip": [
        ("Open Raise", "hp.open_raise = TRUE"),
        ("Cold Call", "hp.call_open_raise = TRUE"),
        ("3-Bet", "hp.three_bet = TRUE"),
        ("Limp", "hp.limp = TRUE"),
        ("Squeeze", "hp.squeeze = TRUE"),
    ],
    "pfr": [
        ("Open Raise", "hp.open_raise = TRUE"),
        ("3-Bet", "hp.three_bet = TRUE"),
        ("4-Bet", "hp.four_bet = TRUE"),
        ("Squeeze", "hp.squeeze = TRUE"),
    ],
}


# ── Money Config ─────────────────────────────────────────────────────
MONEY_CONFIG: dict[str, str] = {
    "limp": "hp.limp = TRUE",
    "limp_fold": "hp.limp_fold = TRUE",
    "four_bet_fold": "hp.four_bet_fold = TRUE",
}


# ── Postflop Bridge Config ──────────────────────────────────────────
POSTFLOP_BRIDGE_CONFIG: dict[str, str] = {
    "three_bet": "hp.three_bet = TRUE AND hp.saw_flop = TRUE",
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
