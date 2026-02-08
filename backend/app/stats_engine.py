import duckdb
from app.models import HeroStats, PositionalStats, StatValue

POSITIONS = ["EP", "MP", "CO", "BTN", "SB", "BB"]
IP_POSITIONS = {"CO", "BTN", "MP"}
OOP_POSITIONS = {"EP", "SB", "BB"}


def compute_hero_stats(
    db: duckdb.DuckDBPyConnection,
    hero_username: str,
    position: str | None = None,
    stakes: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> HeroStats:
    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    if not player:
        return HeroStats()

    player_id = player[0]

    where = "hp.player_id = ?"
    params: list = [player_id]

    if position:
        where += " AND hp.position = ?"
        params.append(position)
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND h.played_at <= ?"
        params.append(date_to)

    rows = db.execute(f"""
        SELECT hp.* FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
    """, params).fetchall()

    columns = [desc[0] for desc in db.description]

    if not rows:
        return HeroStats()

    data = [dict(zip(columns, row)) for row in rows]

    stats = HeroStats()
    stats.hands = len(data)

    total_won_bb = sum(float(r["won_bb"] or 0) for r in data)
    stats.win_rate_bb100 = round((total_won_bb / len(data)) * 100, 2) if data else None

    total_ev_bb = sum(float(r["all_in_ev_bb"] or 0) for r in data)
    stats.win_rate_ev_bb100 = round((total_ev_bb / len(data)) * 100, 2) if data else None

    # Positional stats
    stats.vpip = _positional_pct(data, "vpip", None)
    stats.pfr = _positional_pct(data, "pfr", None)
    stats.open_raise = _positional_pct(data, "open_raise", "open_raise_opp")
    stats.three_bet = _positional_pct(data, "three_bet", "three_bet_opp")
    stats.four_bet = _positional_pct(data, "four_bet", "four_bet_opp")
    stats.fold_to_3bet = _positional_pct(data, "fold_to_3bet", "three_bet_opp",
                                          flag_when_opp=True, flag_is_response=True)
    stats.fold_to_4bet = _positional_pct(data, "fold_to_4bet", "four_bet_opp",
                                          flag_when_opp=True, flag_is_response=True)
    stats.call_open_raise = _positional_pct(data, "call_open_raise", None)
    stats.limp = _positional_pct(data, "limp", None)

    # 3-bet IP/OOP
    ip_3b = [r for r in data if r["three_bet_opp"] and r["position"] in IP_POSITIONS]
    stats.three_bet_ip = _simple_pct(ip_3b, "three_bet")
    oop_3b = [r for r in data if r["three_bet_opp"] and r["position"] in OOP_POSITIONS]
    stats.three_bet_oop = _simple_pct(oop_3b, "three_bet")

    stats.five_bet = _simple_pct([r for r in data if r.get("five_bet_opp")], "five_bet")
    stats.squeeze = _simple_pct([r for r in data if r.get("squeeze_opp")], "squeeze")

    # 4-Bet Range: 4bet hands / total hands
    four_bet_count = sum(1 for r in data if r.get("four_bet"))
    stats.four_bet_range = StatValue(
        value=round(four_bet_count / len(data) * 100, 1) if data else None,
        sample=len(data),
    )

    # Limp-Fold: of limp hands, what % folded
    limp_hands = [r for r in data if r.get("limp")]
    stats.limp_fold = _simple_pct(limp_hands, "limp_fold")

    # 4-Bet-Fold: of 4bet hands where faced 5bet, what % folded
    four_bet_faced_5bet = [r for r in data if r.get("four_bet_fold") is not None]
    stats.four_bet_fold = _simple_pct(four_bet_faced_5bet, "four_bet_fold")

    # Call 4-Bet: of hands where faced 4bet (five_bet_opp), what % called
    faced_4bet = [r for r in data if r.get("five_bet_opp")]
    stats.call_4bet = _simple_pct(faced_4bet, "call_4bet")

    # Steal
    stats.steal = _positional_pct(data, "steal_attempted", "steal_opp",
                                   positions=["CO", "BTN", "SB"])

    # Positional steal stats (BTN, SB)
    steal_hands = [r for r in data if r["steal_attempted"]]
    steal_faced_3bet = [r for r in steal_hands if r.get("fold_to_3bet") is not None]
    stats.fold_to_3bet_steal = _positional_steal_stat(steal_faced_3bet, "fold_to_3bet", ["BTN", "SB"])
    stats.four_bet_steal = _positional_steal_stat(steal_faced_3bet, "four_bet", ["BTN", "SB"])

    # 4-Bet-Fold in steal context: of steal 4-bet hands where faced 5-bet, what % folded
    steal_4bet_faced_5bet = [r for r in steal_hands if r.get("four_bet_fold") is not None]
    stats.four_bet_fold_steal = _positional_steal_stat(steal_4bet_faced_5bet, "four_bet_fold", ["BTN", "SB"])

    # vs Steal positional (SB, BB)
    faced_steal = [r for r in data if r["faced_steal"]]
    stats.vs_steal_fold = _positional_steal_stat(faced_steal, "fold_to_steal", ["SB", "BB"])
    stats.vs_steal_call = _positional_steal_stat(faced_steal, "call_steal", ["SB", "BB"])
    stats.vs_steal_3bet = _positional_steal_stat(faced_steal, "three_bet_vs_steal", ["SB", "BB"])

    # Postflop
    stats.cbet_flop = _positional_pct(data, "cbet_flop", "cbet_flop_opp")
    stats.cbet_turn = _positional_pct(data, "cbet_turn", "cbet_turn_opp")
    stats.cbet_river = _positional_pct(data, "cbet_river", "cbet_river_opp")
    stats.fold_to_cbet_flop = _positional_pct(data, "fold_to_cbet_flop", None,
                                               filter_fn=lambda r: r.get("fold_to_cbet_flop") is not None)
    stats.fold_to_cbet_turn = _positional_pct(data, "fold_to_cbet_turn", None,
                                               filter_fn=lambda r: r.get("fold_to_cbet_turn") is not None)
    stats.fold_to_cbet_river = _positional_pct(data, "fold_to_cbet_river", None,
                                                filter_fn=lambda r: r.get("fold_to_cbet_river") is not None)

    # vs CBet Flop by pot type (raised pot = single raise, 3-bet pot = 3-bet+)
    faced_cbet_flop = [r for r in data if r.get("fold_to_cbet_flop") is not None]
    faced_cbet_raised = [r for r in faced_cbet_flop if not r.get("is_3bet_pot")]
    faced_cbet_3bet = [r for r in faced_cbet_flop if r.get("is_3bet_pot")]

    stats.fold_cbet_flop_raised = _simple_pct(faced_cbet_raised, "fold_to_cbet_flop")
    stats.call_cbet_flop_raised = _simple_pct(faced_cbet_raised, "call_cbet_flop")
    stats.raise_cbet_flop_raised = _simple_pct(faced_cbet_raised, "raise_cbet_flop")
    stats.fold_cbet_flop_3bet = _simple_pct(faced_cbet_3bet, "fold_to_cbet_flop")
    stats.call_cbet_flop_3bet = _simple_pct(faced_cbet_3bet, "call_cbet_flop")
    stats.raise_cbet_flop_3bet = _simple_pct(faced_cbet_3bet, "raise_cbet_flop")

    stats.donk_bet_flop = _simple_pct(
        [r for r in data if r.get("donk_bet_flop_opp")], "donk_bet_flop"
    )
    stats.donk_bet_turn = _simple_pct(
        [r for r in data if r.get("donk_bet_turn_opp")], "donk_bet_turn"
    )
    stats.donk_bet_river = _simple_pct(
        [r for r in data if r.get("donk_bet_river_opp")], "donk_bet_river"
    )

    stats.missed_cbet_flop = _simple_pct(
        [r for r in data if r["cbet_flop_opp"]], "missed_cbet_flop"
    )
    # Missed cbet flop by position (IP vs OOP)
    ip_cbet_opp = [r for r in data if r["cbet_flop_opp"] and r["position"] in IP_POSITIONS]
    stats.missed_cbet_flop_ip = _simple_pct(ip_cbet_opp, "missed_cbet_flop")
    oop_cbet_opp = [r for r in data if r["cbet_flop_opp"] and r["position"] in OOP_POSITIONS]
    stats.missed_cbet_flop_oop = _simple_pct(oop_cbet_opp, "missed_cbet_flop")

    stats.missed_cbet_turn = _simple_pct(
        [r for r in data if r["cbet_turn_opp"]], "missed_cbet_turn"
    )

    # Missed cbet fold: after missing cbet, hero folded
    # IP: checked behind on flop, folded on turn
    ip_missed = [r for r in data if r["missed_cbet_flop"] and r["position"] in IP_POSITIONS]
    ip_missed_fold = sum(1 for r in ip_missed if (r.get("turn_folds") or 0) > 0)
    stats.missed_cbet_fold_ip = StatValue(
        value=round(ip_missed_fold / len(ip_missed) * 100, 1) if ip_missed else None,
        sample=len(ip_missed),
    )
    # OOP: checked on flop, folded on flop or turn
    oop_missed = [r for r in data if r["missed_cbet_flop"] and r["position"] in OOP_POSITIONS]
    oop_missed_fold = sum(
        1 for r in oop_missed
        if (r.get("flop_folds") or 0) > 0 or (r.get("turn_folds") or 0) > 0
    )
    stats.missed_cbet_fold_oop = StatValue(
        value=round(oop_missed_fold / len(oop_missed) * 100, 1) if oop_missed else None,
        sample=len(oop_missed),
    )

    # vs Missed cbet: opponent missed cbet, what did hero do
    vs_mc = [r for r in data if r.get("vs_missed_cbet_flop_opp")]
    vs_mc_ip = [r for r in vs_mc if r["position"] in IP_POSITIONS]
    vs_mc_oop = [r for r in vs_mc if r["position"] in OOP_POSITIONS]

    # Total: hero bet (IP: flop bet, OOP: turn bet)
    vs_mc_bet_total = (
        sum(1 for r in vs_mc_ip if (r.get("flop_bets") or 0) > 0) +
        sum(1 for r in vs_mc_oop if (r.get("turn_bets") or 0) > 0)
    )
    stats.vs_missed_cbet = StatValue(
        value=round(vs_mc_bet_total / len(vs_mc) * 100, 1) if vs_mc else None,
        sample=len(vs_mc),
    )

    # Bet IP: hero is IP, bet on flop into missed cbet
    stats.vs_missed_cbet_bet_ip = StatValue(
        value=round(
            sum(1 for r in vs_mc_ip if (r.get("flop_bets") or 0) > 0) / len(vs_mc_ip) * 100, 1
        ) if vs_mc_ip else None,
        sample=len(vs_mc_ip),
    )
    # Check | Fold IP: hero is IP, didn't bet flop, folded on turn
    ip_no_bet = [r for r in vs_mc_ip if (r.get("flop_bets") or 0) == 0]
    stats.vs_missed_cbet_check_fold_ip = StatValue(
        value=round(
            sum(1 for r in ip_no_bet if (r.get("turn_folds") or 0) > 0) / len(ip_no_bet) * 100, 1
        ) if ip_no_bet else None,
        sample=len(ip_no_bet),
    )
    # Bet OOP Turn: hero is OOP, bet on turn after opponent missed cbet
    stats.vs_missed_cbet_bet_oop_turn = StatValue(
        value=round(
            sum(1 for r in vs_mc_oop if (r.get("turn_bets") or 0) > 0) / len(vs_mc_oop) * 100, 1
        ) if vs_mc_oop else None,
        sample=len(vs_mc_oop),
    )
    # Check-Fold OOP: hero is OOP, checked and folded on turn
    oop_no_bet = [r for r in vs_mc_oop if (r.get("turn_bets") or 0) == 0]
    stats.vs_missed_cbet_check_fold_oop = StatValue(
        value=round(
            sum(1 for r in oop_no_bet
                if (r.get("turn_checks") or 0) > 0 and (r.get("turn_folds") or 0) > 0
            ) / len(oop_no_bet) * 100, 1
        ) if oop_no_bet else None,
        sample=len(oop_no_bet),
    )

    # Aggression
    stats.af_flop = _aggression_factor(data, "flop")
    stats.af_turn = _aggression_factor(data, "turn")
    stats.af_river = _aggression_factor(data, "river")
    stats.afq_flop = _aggression_freq(data, "flop")
    stats.afq_turn = _aggression_freq(data, "turn")
    stats.afq_river = _aggression_freq(data, "river")

    # Showdown
    flop_hands = [r for r in data if r["saw_flop"]]
    sd_hands = [r for r in data if r["went_to_showdown"]]
    stats.wtsd = StatValue(
        value=round(len(sd_hands) / len(flop_hands) * 100, 1) if flop_hands else None,
        sample=len(flop_hands),
    )
    stats.wsd = StatValue(
        value=round(
            sum(1 for r in sd_hands if r["won_at_showdown"]) / len(sd_hands) * 100, 1
        ) if sd_hands else None,
        sample=len(sd_hands),
    )
    stats.wwsf = StatValue(
        value=round(
            sum(1 for r in flop_hands if float(r["won_bb"] or 0) > 0) / len(flop_hands) * 100, 1
        ) if flop_hands else None,
        sample=len(flop_hands),
    )

    return stats


def _positional_pct(
    data: list[dict],
    flag: str,
    opp_flag: str | None,
    positions: list[str] | None = None,
    flag_when_opp: bool = False,
    flag_is_response: bool = False,
    filter_fn=None,
) -> PositionalStats:
    ps = PositionalStats()
    all_pos = positions or POSITIONS

    def calc_for(subset: list[dict]) -> StatValue:
        if filter_fn:
            subset = [r for r in subset if filter_fn(r)]
            total = len(subset)
            hits = sum(1 for r in subset if r.get(flag))
        elif opp_flag and not flag_is_response:
            opps = [r for r in subset if r.get(opp_flag)]
            total = len(opps)
            hits = sum(1 for r in opps if r.get(flag))
        elif flag_is_response and opp_flag:
            # fold_to_3bet: opportunity is when someone else 3bet us (we had open_raise)
            opps = [r for r in subset if r.get(flag) is not None]
            total = len(opps)
            hits = sum(1 for r in opps if r.get(flag))
        else:
            total = len(subset)
            hits = sum(1 for r in subset if r.get(flag))

        return StatValue(
            value=round(hits / total * 100, 1) if total > 0 else None,
            sample=total,
        )

    ps.total = calc_for(data)
    for pos in POSITIONS:
        pos_data = [r for r in data if r["position"] == pos]
        if pos in all_pos:
            setattr(ps, pos.lower(), calc_for(pos_data))

    return ps


def _simple_pct(data: list[dict], flag: str) -> StatValue:
    total = len(data)
    if not total:
        return StatValue()
    hits = sum(1 for r in data if r.get(flag))
    return StatValue(
        value=round(hits / total * 100, 1),
        sample=total,
    )


def _positional_steal_stat(
    data: list[dict], flag: str, positions: list[str]
) -> PositionalStats:
    """Compute a stat for steal/vs-steal with specific positional columns."""
    ps = PositionalStats()

    # Total across all data
    total = len(data)
    hits = sum(1 for r in data if r.get(flag))
    ps.total = StatValue(
        value=round(hits / total * 100, 1) if total > 0 else None,
        sample=total,
    )

    # Per position
    for pos in positions:
        pos_data = [r for r in data if r["position"] == pos]
        pos_total = len(pos_data)
        pos_hits = sum(1 for r in pos_data if r.get(flag))
        setattr(ps, pos.lower(), StatValue(
            value=round(pos_hits / pos_total * 100, 1) if pos_total > 0 else None,
            sample=pos_total,
        ))

    return ps


def _aggression_factor(data: list[dict], street: str) -> StatValue:
    bets = sum(r.get(f"{street}_bets", 0) or 0 for r in data)
    raises = sum(r.get(f"{street}_raises", 0) or 0 for r in data)
    calls = sum(r.get(f"{street}_calls", 0) or 0 for r in data)
    if calls == 0:
        return StatValue(value=None, sample=bets + raises + calls)
    return StatValue(
        value=round((bets + raises) / calls, 2),
        sample=bets + raises + calls,
    )


def _aggression_freq(data: list[dict], street: str) -> StatValue:
    bets = sum(r.get(f"{street}_bets", 0) or 0 for r in data)
    raises = sum(r.get(f"{street}_raises", 0) or 0 for r in data)
    calls = sum(r.get(f"{street}_calls", 0) or 0 for r in data)
    checks = sum(r.get(f"{street}_checks", 0) or 0 for r in data)
    folds = sum(r.get(f"{street}_folds", 0) or 0 for r in data)
    total = bets + raises + calls + checks + folds
    if total == 0:
        return StatValue(value=None, sample=0)
    return StatValue(
        value=round((bets + raises) / total * 100, 1),
        sample=total,
    )
