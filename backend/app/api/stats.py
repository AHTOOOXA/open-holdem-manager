import math
import statistics
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Path
from app.db import get_read_cursor, get_hero_player_id
from app.models import (
    HeroStats, ComboStats, RangeResponse, StatDetailHand, StatDetailHandsResponse,
    TrendPoint, StatTrendResponse, ResponseDistribution, StatAnalysisResponse,
    EvBreakdownResponse, EvScenario, SizingResponse, SizingBucket,
    FoldEquityResponse, ByContextResponse, ContextBucket,
    CompositionResponse, CompositionSlice, MoneyResponse,
    PostflopBridgeResponse, ContinuingRangeResponse, ContinuingCombo,
    StatRangeCombo, StatRangeResponse,
)
from app.stats_engine import compute_hero_stats
from app.stat_registry import (
    STAT_REGISTRY, get_key_street, RESPONSE_DECOMPOSITION,
    EV_BREAKDOWN_CONFIG, SIZING_CONFIG, FOLD_EQUITY_CONFIG,
    BY_CONTEXT_CONFIG, COMPOSITION_CONFIG, MONEY_CONFIG, POSTFLOP_BRIDGE_CONFIG,
)
from app.action_parser import parse_actions_from_raw

router = APIRouter()

RANK_ORDER = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
              '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}


def _normalize_combo(card1: str, card2: str) -> str:
    """Convert two cards like 'Ah','Kd' into combo like 'AKo', 'AKs', 'AA'."""
    r1, s1 = card1[0], card1[1]
    r2, s2 = card2[0], card2[1]
    # Order by rank (high card first)
    if RANK_ORDER.get(r1, 0) < RANK_ORDER.get(r2, 0):
        r1, s1, r2, s2 = r2, s2, r1, s1
    if r1 == r2:
        return r1 + r2
    suffix = 's' if s1 == s2 else 'o'
    return r1 + r2 + suffix


@router.get("/stats/hero", response_model=HeroStats)
def get_hero_stats(
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
):
    db = get_read_cursor()
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"

    return compute_hero_stats(db, hero_username, position=position, stakes=stakes,
                              game_mode=game_mode, date_from=date_from, date_to=date_to,
                              last_n=last_n)


@router.get("/stats/range", response_model=RangeResponse)
def get_range_stats(
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    db = get_read_cursor()
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"

    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    if not player:
        return RangeResponse()

    player_id = player[0]

    query = """
        SELECT hp.card1, hp.card2,
               hp.won_bb, COALESCE(hp.all_in_ev_bb, hp.won_bb),
               hp.vpip, hp.pfr, hp.three_bet,
               hp.saw_flop, hp.went_to_showdown, hp.won_at_showdown
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
          AND hp.card1 IS NOT NULL AND hp.card2 IS NOT NULL
    """
    params: list = [player_id]

    if position:
        query += " AND hp.position = ?"
        params.append(position.upper())
    if stakes:
        query += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        query += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        query += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        query += " AND h.played_at <= ?"
        params.append(date_to)

    rows = db.execute(query, params).fetchall()

    # Also get total hands for context (including folded pre without seeing cards)
    total_query = """
        SELECT COUNT(*) FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
    """
    total_params: list = [player_id]
    if position:
        total_query += " AND hp.position = ?"
        total_params.append(position.upper())
    if stakes:
        total_query += " AND h.stakes = ?"
        total_params.append(stakes)
    if game_mode is not None:
        total_query += " AND h.game_mode = ?"
        total_params.append(game_mode)
    if date_from:
        total_query += " AND h.played_at >= ?"
        total_params.append(date_from)
    if date_to:
        total_query += " AND h.played_at <= ?"
        total_params.append(date_to)

    total_hands = db.execute(total_query, total_params).fetchone()[0]

    # Aggregate by combo in Python
    combo_data: dict[str, dict] = {}
    for card1, card2, won_bb, ev_bb, vpip, pfr, three_bet, saw_flop, went_sd, won_sd in rows:
        combo = _normalize_combo(card1, card2)
        if combo not in combo_data:
            combo_data[combo] = {
                'hands': 0, 'vpip': 0, 'pfr': 0, 'three_bet': 0,
                'won_bb': 0.0, 'ev_bb': 0.0,
                'wtsd': 0, 'wtsd_opp': 0, 'wsd': 0, 'wsd_opp': 0,
            }
        d = combo_data[combo]
        d['hands'] += 1
        d['won_bb'] += float(won_bb or 0)
        d['ev_bb'] += float(ev_bb or 0)
        if vpip:
            d['vpip'] += 1
        if pfr:
            d['pfr'] += 1
        if three_bet:
            d['three_bet'] += 1
        if saw_flop:
            d['wtsd_opp'] += 1  # saw flop = eligible for WTSD
            if went_sd:
                d['wtsd'] += 1
                d['wsd_opp'] += 1  # went to SD = eligible for WSD
                if won_sd:
                    d['wsd'] += 1

    combos = []
    for combo, d in combo_data.items():
        h = d['hands']
        combos.append(ComboStats(
            combo=combo,
            hands=h,
            vpip=d['vpip'],
            pfr=d['pfr'],
            three_bet=d['three_bet'],
            won_bb=round(d['won_bb'], 2),
            ev_bb=round(d['ev_bb'], 2),
            bb_per_100=round(d['won_bb'] / h * 100, 2) if h else 0,
            ev_bb_per_100=round(d['ev_bb'] / h * 100, 2) if h else 0,
            wtsd=d['wtsd'],
            wtsd_opp=d['wtsd_opp'],
            wsd=d['wsd'],
            wsd_opp=d['wsd_opp'],
        ))

    return RangeResponse(combos=combos, total_hands=total_hands)


@router.get("/stats/detail/{stat_key}/hands", response_model=StatDetailHandsResponse)
def get_stat_detail_hands(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
):
    entry = STAT_REGISTRY.get(stat_key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown stat key: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return StatDetailHandsResponse(
            stat_key=stat_key, stat_name=entry["name"],
            action_count=0, opportunity_count=0,
            hands=[], total=0, page=page, per_page=per_page, total_pages=0,
        )

    action_flag = entry.get("action_flag")
    action_sql = entry.get("action_sql")  # raw SQL expression overrides action_flag
    opp_flag = entry.get("opp_flag")
    opp_sql = entry.get("opp_sql")  # raw SQL expression overrides opp_flag
    opp_is_not_null = entry.get("opp_is_not_null", False)
    extra_where = entry.get("extra_where")

    # Build the action expression for SELECT and SUM
    if action_sql:
        action_expr = action_sql
    else:
        action_expr = f"hp.{action_flag} = TRUE"

    # Build WHERE clauses
    where_parts = ["hp.player_id = ?"]
    params: list = [player_id]

    # Opportunity filter: which hands are eligible for this stat
    if opp_sql:
        where_parts.append(f"({opp_sql})")
    elif opp_flag:
        if opp_is_not_null:
            where_parts.append(f"hp.{opp_flag} IS NOT NULL")
        else:
            where_parts.append(f"hp.{opp_flag} = TRUE")

    if extra_where:
        where_parts.append(extra_where)

    if position:
        where_parts.append("hp.position = ?")
        params.append(position.upper())
    if stakes:
        where_parts.append("h.stakes = ?")
        params.append(stakes)
    if game_mode is not None:
        where_parts.append("h.game_mode = ?")
        params.append(game_mode)
    if date_from:
        where_parts.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("h.played_at <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    # Count totals: opportunity count + action count
    count_query = f"""
        SELECT COUNT(*),
               SUM(CASE WHEN {action_expr} THEN 1 ELSE 0 END)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where_sql}
    """
    row = db.execute(count_query, params).fetchone()
    total = int(row[0])
    action_count = int(row[1] or 0)

    # Hand list filters by action (only show hands where stat was triggered).
    # Pagination is based on action_count, not total opportunity count.
    list_where_sql = f"{where_sql} AND ({action_expr})"
    total_pages = max(1, math.ceil(action_count / per_page))
    offset = (page - 1) * per_page

    # Get hero username for action parsing
    hero_row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = hero_row[0] if hero_row else "Hero"

    # Compute key street for this stat
    key_street = get_key_street(stat_key)

    # Fetch hands page (include raw_text, bb_amount, all_in_ev_bb)
    hands_query = f"""
        SELECT h.id, h.played_at, hp.position, hp.card1, hp.card2,
               ({action_expr}) AS action_taken, hp.won_bb, h.stakes,
               hp.all_in_ev_bb, h.bb_amount, h.raw_text
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {list_where_sql}
        ORDER BY h.played_at DESC
        LIMIT ? OFFSET ?
    """
    rows = db.execute(hands_query, params + [per_page, offset]).fetchall()

    if not rows:
        return StatDetailHandsResponse(
            stat_key=stat_key, stat_name=entry["name"],
            action_count=action_count, opportunity_count=total,
            key_street=key_street,
            hands=[], total=action_count, page=page, per_page=per_page, total_pages=total_pages,
        )

    # Batch-fetch board cards for all hand IDs on this page
    hand_ids = [r[0] for r in rows]
    ph = ",".join("?" for _ in hand_ids)
    board_rows = db.execute(
        f"SELECT hand_id, street, card FROM board_cards WHERE hand_id IN ({ph}) ORDER BY hand_id, card_order",
        hand_ids,
    ).fetchall()
    board_map: dict[str, dict[str, list[str]]] = {}
    for hid, street, card in board_rows:
        board_map.setdefault(hid, {"flop": [], "turn": [], "river": []})
        board_map[hid][street].append(card)

    hands = []
    for r in rows:
        hid = r[0]
        bb_amount = float(r[9]) if r[9] else 0.0
        raw_text = r[10] or ""
        board = board_map.get(hid, {"flop": [], "turn": [], "river": []})

        # Parse actions from raw text
        ss = parse_actions_from_raw(raw_text, hero_username, bb_amount)
        preflop_actions = ss["preflop"]["actions"]

        # Determine key street actions
        if key_street and key_street in ss:
            key_street_actions = ss[key_street]["actions"]
        else:
            # For showdown stats (key_street is None), use last non-empty street
            key_street_actions = []
            for st in ("river", "turn", "flop"):
                if ss[st]["actions"]:
                    key_street_actions = ss[st]["actions"]
                    break

        hands.append(StatDetailHand(
            hand_id=hid,
            played_at=r[1],
            position=r[2],
            card1=r[3],
            card2=r[4],
            action_taken=bool(r[5]),
            won_bb=float(r[6] or 0),
            stakes=r[7],
            all_in_ev_bb=float(r[8]) if r[8] is not None else float(r[6] or 0),
            bb_amount=bb_amount,
            board_flop=board["flop"],
            board_turn=board["turn"][0] if board["turn"] else None,
            board_river=board["river"][0] if board["river"] else None,
            preflop_actions=preflop_actions,
            flop_actions=ss["flop"]["actions"],
            flop_pot=ss["flop"]["pot"],
            turn_actions=ss["turn"]["actions"],
            turn_pot=ss["turn"]["pot"],
            river_actions=ss["river"]["actions"],
            river_pot=ss["river"]["pot"],
            key_street_actions=key_street_actions,
        ))

    return StatDetailHandsResponse(
        stat_key=stat_key,
        stat_name=entry["name"],
        action_count=action_count,
        opportunity_count=total,
        key_street=key_street,
        hands=hands,
        total=action_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# ── Trend endpoint ───────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/trend", response_model=StatTrendResponse)
def get_stat_trend(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    bucket_size: int | None = Query(None, ge=10, le=5000),
):
    entry = STAT_REGISTRY.get(stat_key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown stat key: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return StatTrendResponse(stat_key=stat_key, overall_pct=0, points=[])

    # Build action expression
    action_sql = entry.get("action_sql")
    action_flag = entry.get("action_flag")
    if action_sql:
        action_expr = action_sql
    else:
        action_expr = f"hp.{action_flag} = TRUE"

    # Build WHERE
    where_parts = ["hp.player_id = ?"]
    params: list = [player_id]

    opp_flag = entry.get("opp_flag")
    opp_sql = entry.get("opp_sql")
    opp_is_not_null = entry.get("opp_is_not_null", False)
    extra_where = entry.get("extra_where")

    if opp_sql:
        where_parts.append(f"({opp_sql})")
    elif opp_flag:
        if opp_is_not_null:
            where_parts.append(f"hp.{opp_flag} IS NOT NULL")
        else:
            where_parts.append(f"hp.{opp_flag} = TRUE")

    if extra_where:
        where_parts.append(extra_where)
    if position:
        where_parts.append("hp.position = ?")
        params.append(position.upper())
    if stakes:
        where_parts.append("h.stakes = ?")
        params.append(stakes)
    if game_mode is not None:
        where_parts.append("h.game_mode = ?")
        params.append(game_mode)
    if date_from:
        where_parts.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("h.played_at <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    # Step 1: Get overall rate to compute adaptive bucket size
    count_query = f"""
        SELECT COUNT(*), SUM(CASE WHEN {action_expr} THEN 1 ELSE 0 END)
        FROM hand_players hp JOIN hands h ON hp.hand_id = h.id
        WHERE {where_sql}
    """
    cnt_row = db.execute(count_query, params).fetchone()
    total_opps = int(cnt_row[0])
    action_count = int(cnt_row[1] or 0)

    if total_opps == 0:
        return StatTrendResponse(stat_key=stat_key, overall_pct=0, points=[])

    overall_pct = action_count / total_opps * 100

    # Step 2: Adaptive bucket using same CI framework as drift detection
    # Target: 95% CI half-width of rolling avg ≤ 20% of stat value
    # 1.96 * sqrt(p*(1-p)/N) ≤ 0.20 * p  →  N ≥ (1.96/0.20)² * (1-p)/p
    if bucket_size is None:
        p = max(action_count / total_opps, 0.005)  # floor to avoid div by zero
        z = 1.96
        target_relative_ci = 0.20
        adaptive = math.ceil((z / target_relative_ci) ** 2 * (1 - p) / p)
        bucket_size = max(100, min(2000, adaptive))

    # Step 3: Rolling average via window function
    query = f"""
        WITH eligible AS (
            SELECT
                ROW_NUMBER() OVER (ORDER BY h.played_at ASC, h.id ASC) AS rn,
                CASE WHEN {action_expr} THEN 1.0 ELSE 0.0 END AS action_taken
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {where_sql}
        ),
        rolled AS (
            SELECT
                rn,
                AVG(action_taken) OVER (
                    ORDER BY rn ROWS BETWEEN {bucket_size - 1} PRECEDING AND CURRENT ROW
                ) AS rolling_avg,
                LEAST(rn, {bucket_size}) AS sample_size
            FROM eligible
        )
        SELECT rn, rolling_avg * 100.0, sample_size FROM rolled
    """
    rows = db.execute(query, params).fetchall()

    if not rows:
        return StatTrendResponse(stat_key=stat_key, overall_pct=0, points=[])

    # Sample down to ~100 points
    total_rows = len(rows)
    max_points = 100
    if total_rows <= max_points:
        points = [
            TrendPoint(hand_number=int(r[0]), rolling_pct=round(float(r[1]), 2), sample=int(r[2]))
            for r in rows
        ]
    else:
        step = total_rows / max_points
        points = []
        for i in range(max_points):
            idx = int(i * step)
            r = rows[idx]
            points.append(TrendPoint(
                hand_number=int(r[0]),
                rolling_pct=round(float(r[1]), 2),
                sample=int(r[2]),
            ))
        # Always include last point
        last = rows[-1]
        if points[-1].hand_number != int(last[0]):
            points.append(TrendPoint(
                hand_number=int(last[0]),
                rolling_pct=round(float(last[1]), 2),
                sample=int(last[2]),
            ))

    return StatTrendResponse(
        stat_key=stat_key,
        overall_pct=round(overall_pct, 2),
        points=points,
    )


# ── Analysis endpoint (response distribution) ────────────────────────

@router.get("/stats/detail/{stat_key}/analysis", response_model=StatAnalysisResponse)
def get_stat_analysis(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    decomp = RESPONSE_DECOMPOSITION.get(stat_key)
    if not decomp:
        return StatAnalysisResponse(stat_key=stat_key)

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return StatAnalysisResponse(stat_key=stat_key)

    where_parts = ["hp.player_id = ?", f"({decomp['opp_sql']})"]
    params: list = [player_id]

    if position:
        where_parts.append("hp.position = ?")
        params.append(position.upper())
    if stakes:
        where_parts.append("h.stakes = ?")
        params.append(stakes)
    if game_mode is not None:
        where_parts.append("h.game_mode = ?")
        params.append(game_mode)
    if date_from:
        where_parts.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        where_parts.append("h.played_at <= ?")
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT
            SUM(CASE WHEN {decomp['fold_sql']} THEN 1 ELSE 0 END) AS fold_count,
            SUM(CASE WHEN {decomp['raise_sql']} THEN 1 ELSE 0 END) AS raise_count,
            COUNT(*) AS total
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where_sql}
    """
    row = db.execute(query, params).fetchone()
    total = int(row[2])
    if total == 0:
        return StatAnalysisResponse(stat_key=stat_key)

    fold_count = int(row[0] or 0)
    raise_count = int(row[1] or 0)
    call_count = total - fold_count - raise_count

    return StatAnalysisResponse(
        stat_key=stat_key,
        response_distribution=ResponseDistribution(
            fold_count=fold_count,
            call_count=call_count,
            raise_count=raise_count,
            fold_pct=round(fold_count / total * 100, 1),
            call_pct=round(call_count / total * 100, 1),
            raise_pct=round(raise_count / total * 100, 1),
            total=total,
        ),
    )


# ── Helper: build WHERE + params from common filters ─────────────────

def _build_filter_where(
    player_id: int,
    position: str | None,
    stakes: str | None,
    game_mode: str | None,
    date_from: str | None,
    date_to: str | None,
) -> tuple[str, list]:
    """Return (where_sql, params) for hero-filtered queries."""
    parts = ["hp.player_id = ?"]
    params: list = [player_id]
    if position:
        parts.append("hp.position = ?")
        params.append(position.upper())
    if stakes:
        parts.append("h.stakes = ?")
        params.append(stakes)
    if game_mode is not None:
        parts.append("h.game_mode = ?")
        params.append(game_mode)
    if date_from:
        parts.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        parts.append("h.played_at <= ?")
        params.append(date_to)
    return " AND ".join(parts), params


# ── EV Breakdown ──────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/ev-breakdown", response_model=EvBreakdownResponse)
def get_ev_breakdown(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = EV_BREAKDOWN_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No EV breakdown config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return EvBreakdownResponse(stat_key=stat_key, scenarios=[], overall_bb_per_100=0, overall_hands=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    scenarios = []
    overall_won = 0.0
    overall_hands = 0

    for label, scenario_sql in config:
        q = f"""
            SELECT AVG(CAST(hp.won_bb AS DOUBLE)) * 100,
                   COUNT(*),
                   SUM(CAST(hp.won_bb AS DOUBLE))
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {base_where} AND ({scenario_sql})
        """
        row = db.execute(q, base_params).fetchone()
        hands = int(row[1])
        bb100 = round(float(row[0] or 0), 2) if hands > 0 else 0.0
        total_won = float(row[2] or 0)
        scenarios.append(EvScenario(label=label, bb_per_100=bb100, hands=hands, total_won_bb=round(total_won, 2)))
        overall_won += total_won
        overall_hands += hands

    overall_bb100 = round(overall_won / overall_hands * 100, 2) if overall_hands > 0 else 0.0

    return EvBreakdownResponse(
        stat_key=stat_key,
        scenarios=scenarios,
        overall_bb_per_100=overall_bb100,
        overall_hands=overall_hands,
    )


# ── Sizing ────────────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/sizing", response_model=SizingResponse)
def get_sizing(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = SIZING_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No sizing config for: {stat_key}")

    flag_filter, action_filter = config
    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return SizingResponse(buckets=[], avg_size_bb=None, median_size_bb=None, total=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    q = f"""
        SELECT a.amount_bb
        FROM actions a
        JOIN hand_players hp ON a.hand_id = hp.hand_id AND a.player_id = hp.player_id
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({flag_filter})
          AND a.street = 'preflop' AND ({action_filter})
          AND a.amount_bb IS NOT NULL
    """
    rows = db.execute(q, base_params).fetchall()
    if not rows:
        return SizingResponse(buckets=[], avg_size_bb=None, median_size_bb=None, total=0)

    values = [float(r[0]) for r in rows]
    total = len(values)

    # Bucket by 0.5 BB increments
    bucket_counts: dict[float, int] = {}
    for v in values:
        bucket = round(round(v * 2) / 2, 1)
        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

    buckets = sorted(
        [SizingBucket(size_bb=k, count=v, pct=round(v / total * 100, 1)) for k, v in bucket_counts.items()],
        key=lambda b: b.size_bb,
    )

    avg_bb = round(sum(values) / total, 2)
    med_bb = round(statistics.median(values), 2)

    return SizingResponse(buckets=buckets, avg_size_bb=avg_bb, median_size_bb=med_bb, total=total)


# ── Fold Equity ───────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/fold-equity", response_model=FoldEquityResponse)
def get_fold_equity(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = FOLD_EQUITY_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No fold equity config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return FoldEquityResponse(fold_pct=0, fold_count=0, total=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    q = f"""
        SELECT
            SUM(CASE WHEN ({config}) AND hp.saw_flop IS NOT TRUE THEN 1 ELSE 0 END),
            SUM(CASE WHEN ({config}) THEN 1 ELSE 0 END)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where}
    """
    row = db.execute(q, base_params).fetchone()
    fold_count = int(row[0] or 0)
    total = int(row[1] or 0)
    fold_pct = round(fold_count / total * 100, 1) if total > 0 else 0.0

    return FoldEquityResponse(fold_pct=fold_pct, fold_count=fold_count, total=total)


# ── By Context ────────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/by-context", response_model=ByContextResponse)
def get_by_context(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = BY_CONTEXT_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No by-context config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return ByContextResponse(dimension=config["dimension"], buckets=[])

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    join_clause = config["join"]
    group_expr = config["group_expr"]
    action_sql = config["action_sql"]
    opp_sql = config["opp_sql"]

    q = f"""
        SELECT
            {group_expr} AS ctx,
            SUM(CASE WHEN {action_sql} THEN 1 ELSE 0 END) AS actions,
            COUNT(*) AS opportunities
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        {join_clause}
        WHERE {base_where} AND ({opp_sql})
        GROUP BY ctx
        ORDER BY ctx
    """
    rows = db.execute(q, base_params).fetchall()

    buckets = []
    for r in rows:
        label = str(r[0]) if r[0] is not None else "?"
        actions = int(r[1])
        opps = int(r[2])
        pct = round(actions / opps * 100, 1) if opps > 0 else None
        buckets.append(ContextBucket(label=label, actions=actions, opportunities=opps, pct=pct))

    return ByContextResponse(dimension=config["dimension"], buckets=buckets)


# ── Composition ───────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/composition", response_model=CompositionResponse)
def get_composition(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = COMPOSITION_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No composition config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return CompositionResponse(slices=[], total=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    # Build one SUM per component
    sums = ", ".join(f"SUM(CASE WHEN {sql} THEN 1 ELSE 0 END)" for _, sql in config)
    meta_flag = f"hp.{stat_key} = TRUE"

    q = f"""
        SELECT {sums}, COUNT(*)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({meta_flag})
    """
    row = db.execute(q, base_params).fetchone()
    total = int(row[-1])
    if total == 0:
        return CompositionResponse(slices=[], total=0)

    slices = []
    for i, (label, _) in enumerate(config):
        count = int(row[i] or 0)
        slices.append(CompositionSlice(label=label, count=count, pct=round(count / total * 100, 1)))

    return CompositionResponse(slices=slices, total=total)


# ── Money ─────────────────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/money", response_model=MoneyResponse)
def get_money(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = MONEY_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No money config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return MoneyResponse(total_bb=0, hands=0, bb_per_100=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    q = f"""
        SELECT SUM(CAST(hp.won_bb AS DOUBLE)), COUNT(*)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({config})
    """
    row = db.execute(q, base_params).fetchone()
    hands = int(row[1])
    total_bb = round(float(row[0] or 0), 2)
    bb100 = round(total_bb / hands * 100, 2) if hands > 0 else 0.0

    return MoneyResponse(total_bb=total_bb, hands=hands, bb_per_100=bb100)


# ── Postflop Bridge ──────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/postflop-bridge", response_model=PostflopBridgeResponse)
def get_postflop_bridge(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = POSTFLOP_BRIDGE_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"No postflop bridge config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return PostflopBridgeResponse(cbet_pct=None, cbet_count=0, cbet_opp=0, avg_spr=None)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    q = f"""
        SELECT
            SUM(CASE WHEN hp.cbet_flop THEN 1 ELSE 0 END),
            SUM(CASE WHEN hp.cbet_flop_opp THEN 1 ELSE 0 END),
            AVG(CAST(hp.stack_bb AS DOUBLE))
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({config})
    """
    row = db.execute(q, base_params).fetchone()
    cbet_count = int(row[0] or 0)
    cbet_opp = int(row[1] or 0)
    avg_stack = float(row[2]) if row[2] is not None else None
    cbet_pct = round(cbet_count / cbet_opp * 100, 1) if cbet_opp > 0 else None
    # Approximate SPR: stack / estimated pot (3-bet pot ~ 6-8 BB average)
    avg_spr = round(avg_stack / 7, 1) if avg_stack else None

    return PostflopBridgeResponse(cbet_pct=cbet_pct, cbet_count=cbet_count, cbet_opp=cbet_opp, avg_spr=avg_spr)


# ── Continuing Range ─────────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/continuing-range", response_model=ContinuingRangeResponse)
def get_continuing_range(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    decomp = RESPONSE_DECOMPOSITION.get(stat_key)
    if not decomp:
        raise HTTPException(status_code=404, detail=f"No continuing range config for: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return ContinuingRangeResponse(combos=[], total_hands=0)

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    q = f"""
        SELECT hp.card1, hp.card2,
               CASE
                   WHEN {decomp['fold_sql']} THEN 'fold'
                   WHEN {decomp['raise_sql']} THEN 'raise'
                   ELSE 'call'
               END AS response
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({decomp['opp_sql']})
          AND hp.card1 IS NOT NULL AND hp.card2 IS NOT NULL
    """
    rows = db.execute(q, base_params).fetchall()
    if not rows:
        return ContinuingRangeResponse(combos=[], total_hands=0)

    # Aggregate per combo
    combo_data: dict[str, dict[str, int]] = {}
    for card1, card2, response in rows:
        combo = _normalize_combo(card1, card2)
        if combo not in combo_data:
            combo_data[combo] = {"fold": 0, "call": 0, "raise": 0}
        combo_data[combo][response] += 1

    combos = []
    for combo, counts in sorted(combo_data.items()):
        f = counts["fold"]
        c = counts["call"]
        r = counts["raise"]
        combos.append(ContinuingCombo(combo=combo, fold=f, call=c, raise_count=r, total=f + c + r))

    return ContinuingRangeResponse(combos=combos, total_hands=len(rows))


# ── Stat Range Heatmap ──────────────────────────────────────────────

@router.get("/stats/detail/{stat_key}/range", response_model=StatRangeResponse)
def get_stat_range(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    entry = STAT_REGISTRY.get(stat_key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown stat key: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db)
    if not player_id:
        return StatRangeResponse()

    action_flag = entry.get("action_flag")
    action_sql = entry.get("action_sql")
    opp_flag = entry.get("opp_flag")
    opp_sql = entry.get("opp_sql")
    opp_is_not_null = entry.get("opp_is_not_null", False)
    extra_where = entry.get("extra_where")

    if action_sql:
        action_expr = action_sql
    else:
        action_expr = f"hp.{action_flag} = TRUE"

    base_where, base_params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    # Add opportunity filter
    opp_parts = [base_where]
    if opp_sql:
        opp_parts.append(f"({opp_sql})")
    elif opp_flag:
        if opp_is_not_null:
            opp_parts.append(f"hp.{opp_flag} IS NOT NULL")
        else:
            opp_parts.append(f"hp.{opp_flag} = TRUE")
    if extra_where:
        opp_parts.append(extra_where)
    opp_parts.append("hp.card1 IS NOT NULL AND hp.card2 IS NOT NULL")
    where = " AND ".join(opp_parts)

    q = f"""
        SELECT hp.card1, hp.card2,
               COUNT(*) AS hands,
               SUM(CASE WHEN {action_expr} THEN 1 ELSE 0 END) AS actions,
               SUM(CASE WHEN {action_expr} THEN hp.won_bb ELSE 0 END) AS won_bb,
               SUM(CASE WHEN {action_expr} THEN COALESCE(hp.all_in_ev_bb, hp.won_bb) ELSE 0 END) AS ev_bb,
               SUM(hp.won_bb) AS total_won_bb
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
        GROUP BY hp.card1, hp.card2
    """
    rows = db.execute(q, base_params).fetchall()
    if not rows:
        return StatRangeResponse()

    # Aggregate per normalized combo
    combo_data: dict[str, dict] = {}
    for card1, card2, hands, actions, won_bb, ev_bb, total_won_bb in rows:
        combo = _normalize_combo(card1, card2)
        if combo not in combo_data:
            combo_data[combo] = {"hands": 0, "actions": 0, "won_bb": 0.0, "ev_bb": 0.0, "total_won_bb": 0.0}
        d = combo_data[combo]
        d["hands"] += int(hands)
        d["actions"] += int(actions)
        d["won_bb"] += float(won_bb or 0)
        d["ev_bb"] += float(ev_bb or 0)
        d["total_won_bb"] += float(total_won_bb or 0)

    total_hands = sum(d["hands"] for d in combo_data.values())
    total_actions = sum(d["actions"] for d in combo_data.values())

    combos = []
    for combo, d in sorted(combo_data.items()):
        a = d["actions"]
        h = d["hands"]
        bb100 = (d["won_bb"] / a * 100) if a > 0 else 0.0
        ev100 = (d["ev_bb"] / a * 100) if a > 0 else 0.0
        total_bb100 = (d["total_won_bb"] / h * 100) if h > 0 else 0.0
        combos.append(StatRangeCombo(
            combo=combo, hands=h, actions=a,
            won_bb=round(d["won_bb"], 2), ev_bb=round(d["ev_bb"], 2),
            bb_per_100=round(bb100, 1), ev_bb_per_100=round(ev100, 1),
            total_won_bb=round(d["total_won_bb"], 2),
            total_bb_per_100=round(total_bb100, 1),
        ))

    return StatRangeResponse(combos=combos, total_hands=total_hands, total_actions=total_actions)
