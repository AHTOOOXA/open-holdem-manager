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
    stats.open_raise = _positional_pct(data, "open_raise", None)
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

    stats.five_bet = _simple_pct(data, "five_bet")
    stats.squeeze = _simple_pct(data, "squeeze")

    # 4-Bet Range: 4bet hands / total hands
    four_bet_count = sum(1 for r in data if r.get("four_bet"))
    stats.four_bet_range = StatValue(
        value=round(four_bet_count / len(data) * 100, 1) if data else None,
        sample=len(data),
    )

    # Steal
    stats.steal = _positional_pct(data, "steal_attempted", None,
                                   positions=["CO", "BTN", "SB"])

    # Positional steal stats (BTN, SB)
    steal_hands = [r for r in data if r["steal_attempted"]]
    steal_faced_3bet = [r for r in steal_hands if r.get("three_bet_opp")]
    stats.fold_to_3bet_steal = _positional_steal_stat(steal_faced_3bet, "fold_to_3bet", ["BTN", "SB"])
    stats.four_bet_steal = _positional_steal_stat(steal_faced_3bet, "four_bet", ["BTN", "SB"])

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

    stats.donk_bet_flop = _simple_pct(
        [r for r in data if r["saw_flop"]], "donk_bet_flop"
    )
    stats.donk_bet_turn = _simple_pct(
        [r for r in data if r["saw_turn"]], "donk_bet_turn"
    )
    stats.donk_bet_river = _simple_pct(
        [r for r in data if r["saw_river"]], "donk_bet_river"
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
    total = bets + raises + calls
    if total == 0:
        return StatValue(value=None, sample=0)
    return StatValue(
        value=round((bets + raises) / total * 100, 1),
        sample=total,
    )
