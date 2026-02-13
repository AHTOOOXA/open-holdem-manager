import duckdb
from app.models import HeroStats, PositionalStats, StatValue

POSITIONS = ["EP", "MP", "CO", "BTN", "SB", "BB"]

# SQL aggregation query — computes all needed counts in one pass, grouped by position.
# Returns ~6 rows instead of fetching 13k+ rows into Python.
_AGG_SQL = """
SELECT
    hp.position,
    COUNT(*) as hands,
    SUM(CAST(COALESCE(hp.won_bb, 0) AS DOUBLE)) as total_won_bb,
    SUM(CAST(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) AS DOUBLE)) as total_ev_bb,

    -- VPIP / PFR / Limp
    SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END) as vpip,
    SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END) as pfr,
    SUM(CASE WHEN hp.limp THEN 1 ELSE 0 END) as limp,
    SUM(CASE WHEN hp.limp AND hp.limp_fold THEN 1 ELSE 0 END) as limp_fold,

    -- Open Raise
    SUM(CASE WHEN hp.open_raise THEN 1 ELSE 0 END) as open_raise,
    SUM(CASE WHEN hp.open_raise_opp THEN 1 ELSE 0 END) as open_raise_opp,
    SUM(CASE WHEN hp.call_open_raise THEN 1 ELSE 0 END) as call_open_raise,
    SUM(CASE WHEN hp.call_open_raise_opp THEN 1 ELSE 0 END) as call_open_raise_opp,

    -- 3-Bet
    SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END) as three_bet,
    SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END) as three_bet_opp,
    -- 3-Bet IP
    SUM(CASE WHEN hp.three_bet_opp AND hp.three_bet_opp_ip = true THEN 1 ELSE 0 END) as three_bet_opp_ip,
    SUM(CASE WHEN hp.three_bet_opp AND hp.three_bet_opp_ip = true AND hp.three_bet THEN 1 ELSE 0 END) as three_bet_ip,
    -- 3-Bet OOP
    SUM(CASE WHEN hp.three_bet_opp AND hp.three_bet_opp_ip = false THEN 1 ELSE 0 END) as three_bet_opp_oop,
    SUM(CASE WHEN hp.three_bet_opp AND hp.three_bet_opp_ip = false AND hp.three_bet THEN 1 ELSE 0 END) as three_bet_oop,

    -- 4-Bet
    SUM(CASE WHEN hp.four_bet THEN 1 ELSE 0 END) as four_bet,
    SUM(CASE WHEN hp.four_bet_opp THEN 1 ELSE 0 END) as four_bet_opp,

    -- Fold to 3-Bet (opportunity = fold_to_3bet IS NOT NULL)
    SUM(CASE WHEN hp.fold_to_3bet IS NOT NULL THEN 1 ELSE 0 END) as fold_to_3bet_opp,
    SUM(CASE WHEN hp.fold_to_3bet THEN 1 ELSE 0 END) as fold_to_3bet,
    -- Fold to 4-Bet
    SUM(CASE WHEN hp.fold_to_4bet IS NOT NULL THEN 1 ELSE 0 END) as fold_to_4bet_opp,
    SUM(CASE WHEN hp.fold_to_4bet THEN 1 ELSE 0 END) as fold_to_4bet,

    -- 5-Bet / Squeeze
    SUM(CASE WHEN hp.five_bet_opp THEN 1 ELSE 0 END) as five_bet_opp,
    SUM(CASE WHEN hp.five_bet THEN 1 ELSE 0 END) as five_bet,
    SUM(CASE WHEN hp.squeeze_opp THEN 1 ELSE 0 END) as squeeze_opp,
    SUM(CASE WHEN hp.squeeze THEN 1 ELSE 0 END) as squeeze,

    -- 4-Bet-Fold
    SUM(CASE WHEN hp.four_bet_fold IS NOT NULL THEN 1 ELSE 0 END) as four_bet_fold_opp,
    SUM(CASE WHEN hp.four_bet_fold THEN 1 ELSE 0 END) as four_bet_fold,
    -- Call 4-Bet
    SUM(CASE WHEN hp.five_bet_opp AND hp.call_4bet THEN 1 ELSE 0 END) as call_4bet,

    -- Steal
    SUM(CASE WHEN hp.steal_opp THEN 1 ELSE 0 END) as steal_opp,
    SUM(CASE WHEN hp.steal_attempted THEN 1 ELSE 0 END) as steal,
    -- Steal sub-stats
    SUM(CASE WHEN hp.steal_attempted AND hp.fold_to_3bet IS NOT NULL THEN 1 ELSE 0 END) as steal_faced_3bet,
    SUM(CASE WHEN hp.steal_attempted AND hp.fold_to_3bet THEN 1 ELSE 0 END) as steal_fold_to_3bet,
    SUM(CASE WHEN hp.steal_attempted AND hp.fold_to_3bet IS NOT NULL AND hp.four_bet THEN 1 ELSE 0 END) as steal_four_bet,
    SUM(CASE WHEN hp.steal_attempted AND hp.four_bet_fold IS NOT NULL THEN 1 ELSE 0 END) as steal_4bet_fold_opp,
    SUM(CASE WHEN hp.steal_attempted AND hp.four_bet_fold THEN 1 ELSE 0 END) as steal_4bet_fold,

    -- vs Steal
    SUM(CASE WHEN hp.faced_steal THEN 1 ELSE 0 END) as faced_steal,
    SUM(CASE WHEN hp.faced_steal AND hp.fold_to_steal THEN 1 ELSE 0 END) as fold_to_steal,
    SUM(CASE WHEN hp.faced_steal AND hp.call_steal THEN 1 ELSE 0 END) as call_steal,
    SUM(CASE WHEN hp.faced_steal AND hp.three_bet_vs_steal THEN 1 ELSE 0 END) as three_bet_vs_steal,

    -- CBet
    SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END) as cbet_flop_opp,
    SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END) as cbet_flop,
    SUM(CASE WHEN hp.cbet_turn_opp THEN 1 ELSE 0 END) as cbet_turn_opp,
    SUM(CASE WHEN hp.cbet_turn THEN 1 ELSE 0 END) as cbet_turn,
    SUM(CASE WHEN hp.cbet_river_opp THEN 1 ELSE 0 END) as cbet_river_opp,
    SUM(CASE WHEN hp.cbet_river THEN 1 ELSE 0 END) as cbet_river,

    -- Fold to CBet
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL THEN 1 ELSE 0 END) as ftcb_flop_opp,
    SUM(CASE WHEN hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as ftcb_flop,
    SUM(CASE WHEN hp.fold_to_cbet_turn IS NOT NULL THEN 1 ELSE 0 END) as ftcb_turn_opp,
    SUM(CASE WHEN hp.fold_to_cbet_turn THEN 1 ELSE 0 END) as ftcb_turn,
    SUM(CASE WHEN hp.fold_to_cbet_river IS NOT NULL THEN 1 ELSE 0 END) as ftcb_river_opp,
    SUM(CASE WHEN hp.fold_to_cbet_river THEN 1 ELSE 0 END) as ftcb_river,

    -- vs CBet Flop by pot type
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as faced_cbet_raised,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) AND hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as fold_cbet_raised,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) AND hp.call_cbet_flop THEN 1 ELSE 0 END) as call_cbet_raised,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) AND hp.raise_cbet_flop THEN 1 ELSE 0 END) as raise_cbet_raised,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot THEN 1 ELSE 0 END) as faced_cbet_3bet,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot AND hp.fold_to_cbet_flop THEN 1 ELSE 0 END) as fold_cbet_3bet,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot AND hp.call_cbet_flop THEN 1 ELSE 0 END) as call_cbet_3bet,
    SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot AND hp.raise_cbet_flop THEN 1 ELSE 0 END) as raise_cbet_3bet,

    -- Donk bets
    SUM(CASE WHEN hp.donk_bet_flop_opp THEN 1 ELSE 0 END) as donk_flop_opp,
    SUM(CASE WHEN hp.donk_bet_flop THEN 1 ELSE 0 END) as donk_flop,
    SUM(CASE WHEN hp.donk_bet_turn_opp THEN 1 ELSE 0 END) as donk_turn_opp,
    SUM(CASE WHEN hp.donk_bet_turn THEN 1 ELSE 0 END) as donk_turn,
    SUM(CASE WHEN hp.donk_bet_river_opp THEN 1 ELSE 0 END) as donk_river_opp,
    SUM(CASE WHEN hp.donk_bet_river THEN 1 ELSE 0 END) as donk_river,

    -- Missed CBet
    SUM(CASE WHEN hp.cbet_flop_opp AND hp.missed_cbet_flop THEN 1 ELSE 0 END) as missed_cbet_flop,
    SUM(CASE WHEN hp.cbet_flop_opp AND hp.postflop_ip = true THEN 1 ELSE 0 END) as cbet_opp_ip,
    SUM(CASE WHEN hp.cbet_flop_opp AND hp.postflop_ip = true AND hp.missed_cbet_flop THEN 1 ELSE 0 END) as missed_cbet_ip,
    SUM(CASE WHEN hp.cbet_flop_opp AND hp.postflop_ip = false THEN 1 ELSE 0 END) as cbet_opp_oop,
    SUM(CASE WHEN hp.cbet_flop_opp AND hp.postflop_ip = false AND hp.missed_cbet_flop THEN 1 ELSE 0 END) as missed_cbet_oop,
    SUM(CASE WHEN hp.cbet_turn_opp AND hp.missed_cbet_turn THEN 1 ELSE 0 END) as missed_cbet_turn,

    -- Missed CBet Fold
    SUM(CASE WHEN hp.missed_cbet_flop AND hp.postflop_ip = true THEN 1 ELSE 0 END) as mc_ip_total,
    SUM(CASE WHEN hp.missed_cbet_flop AND hp.postflop_ip = true AND COALESCE(hp.turn_folds, 0) > 0 THEN 1 ELSE 0 END) as mc_fold_ip,
    SUM(CASE WHEN hp.missed_cbet_flop AND hp.postflop_ip = false THEN 1 ELSE 0 END) as mc_oop_total,
    SUM(CASE WHEN hp.missed_cbet_flop AND hp.postflop_ip = false AND (COALESCE(hp.flop_folds, 0) > 0 OR COALESCE(hp.turn_folds, 0) > 0) THEN 1 ELSE 0 END) as mc_fold_oop,

    -- vs Missed CBet
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp THEN 1 ELSE 0 END) as vs_mc,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = true THEN 1 ELSE 0 END) as vs_mc_ip,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = true AND COALESCE(hp.flop_bets, 0) > 0 THEN 1 ELSE 0 END) as vs_mc_ip_bet,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = true AND COALESCE(hp.flop_bets, 0) = 0 THEN 1 ELSE 0 END) as vs_mc_ip_no_bet,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = true AND COALESCE(hp.flop_bets, 0) = 0 AND COALESCE(hp.turn_folds, 0) > 0 THEN 1 ELSE 0 END) as vs_mc_ip_cf,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = false THEN 1 ELSE 0 END) as vs_mc_oop,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = false AND COALESCE(hp.turn_bets, 0) > 0 THEN 1 ELSE 0 END) as vs_mc_oop_bet,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = false AND COALESCE(hp.turn_bets, 0) = 0 THEN 1 ELSE 0 END) as vs_mc_oop_no_bet,
    SUM(CASE WHEN hp.vs_missed_cbet_flop_opp AND hp.postflop_ip = false AND COALESCE(hp.turn_bets, 0) = 0 AND COALESCE(hp.turn_checks, 0) > 0 AND COALESCE(hp.turn_folds, 0) > 0 THEN 1 ELSE 0 END) as vs_mc_oop_cf,

    -- Aggression counts
    SUM(COALESCE(hp.flop_bets, 0)) as flop_bets,
    SUM(COALESCE(hp.flop_raises, 0)) as flop_raises,
    SUM(COALESCE(hp.flop_calls, 0)) as flop_calls,
    SUM(COALESCE(hp.flop_checks, 0)) as flop_checks,
    SUM(COALESCE(hp.flop_folds, 0)) as flop_folds,
    SUM(COALESCE(hp.turn_bets, 0)) as turn_bets,
    SUM(COALESCE(hp.turn_raises, 0)) as turn_raises,
    SUM(COALESCE(hp.turn_calls, 0)) as turn_calls,
    SUM(COALESCE(hp.turn_checks, 0)) as turn_checks,
    SUM(COALESCE(hp.turn_folds, 0)) as turn_folds,
    SUM(COALESCE(hp.river_bets, 0)) as river_bets,
    SUM(COALESCE(hp.river_raises, 0)) as river_raises,
    SUM(COALESCE(hp.river_calls, 0)) as river_calls,
    SUM(COALESCE(hp.river_checks, 0)) as river_checks,
    SUM(COALESCE(hp.river_folds, 0)) as river_folds,

    -- BB Defense / Iso Raise / Fold to Squeeze
    SUM(CASE WHEN hp.bb_defense_opp THEN 1 ELSE 0 END) as bb_defense_opp,
    SUM(CASE WHEN hp.bb_defense THEN 1 ELSE 0 END) as bb_defense,
    SUM(CASE WHEN hp.iso_raise_opp THEN 1 ELSE 0 END) as iso_raise_opp,
    SUM(CASE WHEN hp.iso_raise THEN 1 ELSE 0 END) as iso_raise,
    SUM(CASE WHEN hp.faced_squeeze THEN 1 ELSE 0 END) as faced_squeeze,
    SUM(CASE WHEN hp.fold_to_squeeze IS NOT NULL THEN 1 ELSE 0 END) as fold_to_squeeze_opp,
    SUM(CASE WHEN hp.fold_to_squeeze THEN 1 ELSE 0 END) as fold_to_squeeze,

    -- Showdown
    SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END) as saw_flop,
    SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END) as went_sd,
    SUM(CASE WHEN hp.went_to_showdown AND hp.won_at_showdown THEN 1 ELSE 0 END) as won_sd,
    SUM(CASE WHEN hp.saw_flop AND CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) > 0 THEN 1 ELSE 0 END) as wwsf

FROM hand_players hp
JOIN hands h ON hp.hand_id = h.id
WHERE {where}
GROUP BY hp.position
"""


def compute_player_stats(
    db: duckdb.DuckDBPyConnection,
    player_id: int,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    last_n: int | None = None,
) -> HeroStats:
    """Compute full stats for any player by player_id."""
    where = "hp.player_id = ?"
    params: list = [player_id]

    if position:
        where += " AND hp.position = ?"
        params.append(position)
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        where += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND h.played_at <= ?"
        params.append(date_to)

    if last_n:
        cte_where = where
        cte_params = list(params)
        cte = f"""WITH recent_hands AS (
            SELECT h.id FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {cte_where}
            ORDER BY h.played_at DESC, h.id DESC
            LIMIT {int(last_n)}
        )
        """
        where += " AND h.id IN (SELECT id FROM recent_hands)"
        params = cte_params + params
        sql = cte + _AGG_SQL.format(where=where)
    else:
        sql = _AGG_SQL.format(where=where)

    rows = db.execute(sql, params).fetchall()
    if not rows:
        return HeroStats()

    columns = [desc[0] for desc in db.description]

    # Build per-position dict and totals
    by_pos: dict[str, dict] = {}
    tot: dict[str, int | float] = {}
    for row in rows:
        d = dict(zip(columns, row))
        pos = d["position"]
        by_pos[pos] = d
        for k, v in d.items():
            if k == "position":
                continue
            tot[k] = tot.get(k, 0) + (int(v) if isinstance(v, (int, bool)) else float(v or 0))

    total_hands = int(tot.get("hands", 0))
    if total_hands == 0:
        return HeroStats()

    stats = HeroStats()
    stats.hands = total_hands

    # Win rates
    stats.win_rate_bb100 = round((tot["total_won_bb"] / total_hands) * 100, 2)
    stats.win_rate_ev_bb100 = round((tot["total_ev_bb"] / total_hands) * 100, 2)

    # Helper: build PositionalStats from count/opp keys
    def _pos_stat(count_key: str, opp_key: str | None) -> PositionalStats:
        ps = PositionalStats()
        t_count = int(tot.get(count_key, 0))
        t_opp = int(tot.get(opp_key, 0)) if opp_key else total_hands
        ps.total = StatValue(
            value=round(t_count / t_opp * 100, 1) if t_opp > 0 else None,
            sample=t_opp,
        )
        for pos in POSITIONS:
            pd = by_pos.get(pos)
            if not pd:
                continue
            p_count = int(pd.get(count_key, 0))
            p_opp = int(pd.get(opp_key, 0)) if opp_key else int(pd["hands"])
            setattr(ps, pos.lower(), StatValue(
                value=round(p_count / p_opp * 100, 1) if p_opp > 0 else None,
                sample=p_opp,
            ))
        return ps

    def _sv(count_key: str, opp_key: str) -> StatValue:
        c = int(tot.get(count_key, 0))
        o = int(tot.get(opp_key, 0))
        return StatValue(value=round(c / o * 100, 1) if o > 0 else None, sample=o)

    def _pos_steal(count_key: str, opp_key: str, positions: list[str]) -> PositionalStats:
        ps = PositionalStats()
        t_c = int(tot.get(count_key, 0))
        t_o = int(tot.get(opp_key, 0))
        ps.total = StatValue(value=round(t_c / t_o * 100, 1) if t_o > 0 else None, sample=t_o)
        for pos in positions:
            pd = by_pos.get(pos)
            if not pd:
                continue
            p_c = int(pd.get(count_key, 0))
            p_o = int(pd.get(opp_key, 0))
            setattr(ps, pos.lower(), StatValue(
                value=round(p_c / p_o * 100, 1) if p_o > 0 else None, sample=p_o,
            ))
        return ps

    # Pre-flop
    stats.vpip = _pos_stat("vpip", None)
    stats.pfr = _pos_stat("pfr", None)
    stats.open_raise = _pos_stat("open_raise", "open_raise_opp")
    stats.three_bet = _pos_stat("three_bet", "three_bet_opp")
    stats.four_bet = _pos_stat("four_bet", "four_bet_opp")
    stats.fold_to_3bet = _pos_stat("fold_to_3bet", "fold_to_3bet_opp")
    stats.fold_to_4bet = _pos_stat("fold_to_4bet", "fold_to_4bet_opp")
    stats.call_open_raise = _pos_stat("call_open_raise", "call_open_raise_opp")
    stats.limp = _pos_stat("limp", None)

    # 3-Bet IP/OOP
    stats.three_bet_ip = _pos_stat("three_bet_ip", "three_bet_opp_ip")
    stats.three_bet_oop = _pos_stat("three_bet_oop", "three_bet_opp_oop")

    # Misc pre-flop
    stats.five_bet = _sv("five_bet", "five_bet_opp")
    stats.squeeze = _sv("squeeze", "squeeze_opp")
    stats.four_bet_range = StatValue(
        value=round(int(tot.get("four_bet", 0)) / total_hands * 100, 1),
        sample=total_hands,
    )
    stats.limp_fold = _sv("limp_fold", "limp")
    stats.four_bet_fold = _sv("four_bet_fold", "four_bet_fold_opp")
    stats.call_4bet = _sv("call_4bet", "five_bet_opp")
    stats.bb_defense = _sv("bb_defense", "bb_defense_opp")
    stats.iso_raise = _sv("iso_raise", "iso_raise_opp")
    stats.fold_to_squeeze = _sv("fold_to_squeeze", "fold_to_squeeze_opp")

    # Steal
    stats.steal = _pos_steal("steal", "steal_opp", ["CO", "BTN", "SB"])
    stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["BTN", "SB"])
    stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["BTN", "SB"])
    stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["BTN", "SB"])

    # vs Steal
    stats.vs_steal_fold = _pos_steal("fold_to_steal", "faced_steal", ["SB", "BB"])
    stats.vs_steal_call = _pos_steal("call_steal", "faced_steal", ["SB", "BB"])
    stats.vs_steal_3bet = _pos_steal("three_bet_vs_steal", "faced_steal", ["SB", "BB"])

    # Postflop CBets
    stats.cbet_flop = _pos_stat("cbet_flop", "cbet_flop_opp")
    stats.cbet_turn = _pos_stat("cbet_turn", "cbet_turn_opp")
    stats.cbet_river = _pos_stat("cbet_river", "cbet_river_opp")
    stats.fold_to_cbet_flop = _pos_stat("ftcb_flop", "ftcb_flop_opp")
    stats.fold_to_cbet_turn = _pos_stat("ftcb_turn", "ftcb_turn_opp")
    stats.fold_to_cbet_river = _pos_stat("ftcb_river", "ftcb_river_opp")

    # vs CBet Flop by pot type
    stats.fold_cbet_flop_raised = _sv("fold_cbet_raised", "faced_cbet_raised")
    stats.call_cbet_flop_raised = _sv("call_cbet_raised", "faced_cbet_raised")
    stats.raise_cbet_flop_raised = _sv("raise_cbet_raised", "faced_cbet_raised")
    stats.fold_cbet_flop_3bet = _sv("fold_cbet_3bet", "faced_cbet_3bet")
    stats.call_cbet_flop_3bet = _sv("call_cbet_3bet", "faced_cbet_3bet")
    stats.raise_cbet_flop_3bet = _sv("raise_cbet_3bet", "faced_cbet_3bet")

    # Donk bets
    stats.donk_bet_flop = _sv("donk_flop", "donk_flop_opp")
    stats.donk_bet_turn = _sv("donk_turn", "donk_turn_opp")
    stats.donk_bet_river = _sv("donk_river", "donk_river_opp")

    # Missed CBet
    stats.missed_cbet_flop = _sv("missed_cbet_flop", "cbet_flop_opp")
    stats.missed_cbet_flop_ip = _sv("missed_cbet_ip", "cbet_opp_ip")
    stats.missed_cbet_flop_oop = _sv("missed_cbet_oop", "cbet_opp_oop")
    stats.missed_cbet_turn = _sv("missed_cbet_turn", "cbet_turn_opp")

    # Missed CBet Fold
    mc_ip_t = int(tot.get("mc_ip_total", 0))
    mc_fold_ip = int(tot.get("mc_fold_ip", 0))
    stats.missed_cbet_fold_ip = StatValue(
        value=round(mc_fold_ip / mc_ip_t * 100, 1) if mc_ip_t > 0 else None,
        sample=mc_ip_t,
    )
    mc_oop_t = int(tot.get("mc_oop_total", 0))
    mc_fold_oop = int(tot.get("mc_fold_oop", 0))
    stats.missed_cbet_fold_oop = StatValue(
        value=round(mc_fold_oop / mc_oop_t * 100, 1) if mc_oop_t > 0 else None,
        sample=mc_oop_t,
    )

    # vs Missed CBet
    vs_mc_t = int(tot.get("vs_mc", 0))
    vs_mc_ip_bet = int(tot.get("vs_mc_ip_bet", 0))
    vs_mc_oop_bet = int(tot.get("vs_mc_oop_bet", 0))
    stats.vs_missed_cbet = StatValue(
        value=round((vs_mc_ip_bet + vs_mc_oop_bet) / vs_mc_t * 100, 1) if vs_mc_t > 0 else None,
        sample=vs_mc_t,
    )
    vs_mc_ip_t = int(tot.get("vs_mc_ip", 0))
    stats.vs_missed_cbet_bet_ip = StatValue(
        value=round(vs_mc_ip_bet / vs_mc_ip_t * 100, 1) if vs_mc_ip_t > 0 else None,
        sample=vs_mc_ip_t,
    )
    vs_mc_ip_nb = int(tot.get("vs_mc_ip_no_bet", 0))
    vs_mc_ip_cf = int(tot.get("vs_mc_ip_cf", 0))
    stats.vs_missed_cbet_check_fold_ip = StatValue(
        value=round(vs_mc_ip_cf / vs_mc_ip_nb * 100, 1) if vs_mc_ip_nb > 0 else None,
        sample=vs_mc_ip_nb,
    )
    vs_mc_oop_t = int(tot.get("vs_mc_oop", 0))
    stats.vs_missed_cbet_bet_oop_turn = StatValue(
        value=round(vs_mc_oop_bet / vs_mc_oop_t * 100, 1) if vs_mc_oop_t > 0 else None,
        sample=vs_mc_oop_t,
    )
    vs_mc_oop_nb = int(tot.get("vs_mc_oop_no_bet", 0))
    vs_mc_oop_cf = int(tot.get("vs_mc_oop_cf", 0))
    stats.vs_missed_cbet_check_fold_oop = StatValue(
        value=round(vs_mc_oop_cf / vs_mc_oop_nb * 100, 1) if vs_mc_oop_nb > 0 else None,
        sample=vs_mc_oop_nb,
    )

    # Aggression
    def _af(street: str) -> StatValue:
        b = int(tot.get(f"{street}_bets", 0))
        r = int(tot.get(f"{street}_raises", 0))
        c = int(tot.get(f"{street}_calls", 0))
        if c == 0:
            return StatValue(value=None, sample=b + r)
        return StatValue(value=round((b + r) / c, 2), sample=b + r + c)

    def _afq(street: str) -> StatValue:
        b = int(tot.get(f"{street}_bets", 0))
        r = int(tot.get(f"{street}_raises", 0))
        c = int(tot.get(f"{street}_calls", 0))
        x = int(tot.get(f"{street}_checks", 0))
        f = int(tot.get(f"{street}_folds", 0))
        t = b + r + c + x + f
        if t == 0:
            return StatValue(value=None, sample=0)
        return StatValue(value=round((b + r) / t * 100, 1), sample=t)

    stats.af_flop = _af("flop")
    stats.af_turn = _af("turn")
    stats.af_river = _af("river")
    stats.afq_flop = _afq("flop")
    stats.afq_turn = _afq("turn")
    stats.afq_river = _afq("river")

    # Showdown
    sf = int(tot.get("saw_flop", 0))
    sd = int(tot.get("went_sd", 0))
    wsd = int(tot.get("won_sd", 0))
    wwsf = int(tot.get("wwsf", 0))
    stats.wtsd = StatValue(value=round(sd / sf * 100, 1) if sf > 0 else None, sample=sf)
    stats.wsd = StatValue(value=round(wsd / sd * 100, 1) if sd > 0 else None, sample=sd)
    stats.wwsf = StatValue(value=round(wwsf / sf * 100, 1) if sf > 0 else None, sample=sf)

    return stats


def compute_hero_stats(
    db: duckdb.DuckDBPyConnection,
    hero_username: str,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    last_n: int | None = None,
) -> HeroStats:
    """Compute stats for hero by username. Thin wrapper around compute_player_stats."""
    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    if not player:
        return HeroStats()
    return compute_player_stats(
        db, player[0],
        position=position, stakes=stakes, game_mode=game_mode,
        date_from=date_from, date_to=date_to, last_n=last_n,
    )
