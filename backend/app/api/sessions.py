from fastapi import APIRouter, HTTPException
from app.db import get_read_cursor, get_hero_player_id
from app.models import (
    SessionSummary,
    SessionListResponse,
    SessionGraphPoint,
    SessionStats,
    SessionBigHand,
    SessionDetailResponse,
)
from datetime import datetime

router = APIRouter()

# SQL CTE that assigns a session index to each hand based on 10-min gaps
# Parameterized: first ? = player_id, second ? = workspace_id
_SESSION_CTE = """
WITH ordered_hands AS (
    SELECT h.id AS hand_id, h.played_at, h.stakes, h.bb_amount,
           hp.won_bb, hp.won, COALESCE(hp.all_in_ev_bb, hp.won_bb) AS ev_bb,
           hp.rake_bb, hp.rake,
           hp.vpip, hp.pfr, hp.three_bet, hp.three_bet_opp,
           hp.cbet_flop, hp.cbet_flop_opp, hp.saw_flop,
           hp.went_to_showdown, hp.won_at_showdown,
           hp.steal_attempted, hp.steal_opp,
           hp.flop_bets, hp.flop_raises, hp.flop_calls, hp.flop_checks, hp.flop_folds,
           hp.position, hp.card1, hp.card2,
           CASE WHEN h.played_at - LAG(h.played_at)
                OVER (ORDER BY h.played_at, h.id) > INTERVAL '10 minutes'
                THEN 1 ELSE 0 END AS new_session
    FROM hand_players hp
    JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
    WHERE hp.player_id = ? AND h.workspace_id = ?
),
sessioned AS (
    SELECT *, SUM(new_session) OVER (ORDER BY played_at, hand_id) AS session_idx
    FROM ordered_hands
)
"""



def _safe_pct(num, den):
    if den == 0:
        return None
    return round((num / den) * 100, 1)


@router.get("/sessions", response_model=SessionListResponse)
def get_sessions(workspace_id: int = 1):
    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
    if not player_id:
        return SessionListResponse(sessions=[], total=0)

    rows = db.execute(f"""
        {_SESSION_CTE}
        SELECT
            session_idx,
            MIN(played_at) AS start_time,
            MAX(played_at) AS end_time,
            COUNT(*) AS hands,
            ARRAY_AGG(DISTINCT stakes) AS stakes_arr,
            SUM(CAST(won_bb AS DOUBLE)) AS won_bb,
            SUM(CAST(won AS DOUBLE)) AS won_usd,
            SUM(CAST(ev_bb AS DOUBLE)) AS ev_bb,
            SUM(CAST(ev_bb AS DOUBLE) * CAST(bb_amount AS DOUBLE)) AS ev_usd,
            SUM(CAST(rake_bb AS DOUBLE)) AS rake_bb,
            SUM(CAST(rake AS DOUBLE)) AS rake_usd
        FROM sessioned
        GROUP BY session_idx
        ORDER BY session_idx DESC
    """, [player_id, workspace_id]).fetchall()

    summaries = []
    for r in rows:
        idx, start, end, n, stakes_arr, won_bb, won_usd, ev_bb, ev_usd, rake_bb, rake_usd = r
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        duration_min = (end - start).total_seconds() / 60.0
        summaries.append(SessionSummary(
            session_index=int(idx),
            start_time=start.isoformat(),
            end_time=end.isoformat(),
            hands=int(n),
            duration_minutes=round(duration_min, 1),
            stakes=sorted(stakes_arr) if stakes_arr else [],
            won_bb=round(float(won_bb or 0), 2),
            won_usd=round(float(won_usd or 0), 2),
            ev_bb=round(float(ev_bb or 0), 2),
            ev_usd=round(float(ev_usd or 0), 2),
            rake_bb=round(float(rake_bb or 0), 2),
            rake_usd=round(float(rake_usd or 0), 2),
            bb_per_100=round((float(won_bb or 0) / n) * 100, 2) if n else 0,
            ev_bb_per_100=round((float(ev_bb or 0) / n) * 100, 2) if n else 0,
        ))

    return SessionListResponse(sessions=summaries, total=len(summaries))


@router.get("/sessions/{session_index}", response_model=SessionDetailResponse)
def get_session_detail(session_index: int, workspace_id: int = 1):
    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
    if not player_id:
        raise HTTPException(status_code=404, detail="Hero not found")

    # Get aggregated stats for this session in SQL
    agg = db.execute(f"""
        {_SESSION_CTE}
        SELECT
            COUNT(*) AS hands,
            MIN(played_at) AS start_time,
            MAX(played_at) AS end_time,
            ARRAY_AGG(DISTINCT stakes) AS stakes_arr,
            SUM(CAST(won_bb AS DOUBLE)) AS won_bb,
            SUM(CAST(won AS DOUBLE)) AS won_usd,
            SUM(CAST(ev_bb AS DOUBLE)) AS ev_bb,
            SUM(CAST(ev_bb AS DOUBLE) * CAST(bb_amount AS DOUBLE)) AS ev_usd,
            SUM(CAST(rake_bb AS DOUBLE)) AS rake_bb,
            SUM(CAST(rake AS DOUBLE)) AS rake_usd,
            -- Stat counts
            SUM(CASE WHEN vpip THEN 1 ELSE 0 END) AS vpip_c,
            SUM(CASE WHEN pfr THEN 1 ELSE 0 END) AS pfr_c,
            SUM(CASE WHEN three_bet THEN 1 ELSE 0 END) AS tb_c,
            SUM(CASE WHEN three_bet_opp THEN 1 ELSE 0 END) AS tb_opp,
            SUM(CASE WHEN cbet_flop THEN 1 ELSE 0 END) AS cb_c,
            SUM(CASE WHEN cbet_flop_opp THEN 1 ELSE 0 END) AS cb_opp,
            SUM(CASE WHEN saw_flop THEN 1 ELSE 0 END) AS sf_c,
            SUM(CASE WHEN went_to_showdown THEN 1 ELSE 0 END) AS wtsd_c,
            SUM(CASE WHEN won_at_showdown THEN 1 ELSE 0 END) AS wsd_c,
            SUM(CASE WHEN steal_attempted THEN 1 ELSE 0 END) AS steal_c,
            SUM(CASE WHEN steal_opp THEN 1 ELSE 0 END) AS steal_opp_c,
            SUM(CASE WHEN saw_flop AND CAST(COALESCE(won_bb, 0) AS DOUBLE) > 0 THEN 1 ELSE 0 END) AS wwsf_c,
            SUM(COALESCE(flop_bets, 0) + COALESCE(flop_raises, 0)) AS flop_agg,
            SUM(COALESCE(flop_bets, 0) + COALESCE(flop_raises, 0)
              + COALESCE(flop_calls, 0) + COALESCE(flop_checks, 0) + COALESCE(flop_folds, 0)) AS flop_total
        FROM sessioned
        WHERE session_idx = ?
    """, [player_id, workspace_id, session_index]).fetchone()

    if not agg or agg[0] == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    n = int(agg[0])
    start = agg[1] if isinstance(agg[1], datetime) else datetime.fromisoformat(agg[1])
    end = agg[2] if isinstance(agg[2], datetime) else datetime.fromisoformat(agg[2])
    duration_min = (end - start).total_seconds() / 60.0
    duration_hrs = duration_min / 60.0
    won_bb = float(agg[4] or 0)
    won_usd = float(agg[5] or 0)
    ev_bb = float(agg[6] or 0)
    ev_usd = float(agg[7] or 0)
    rake_bb = float(agg[8] or 0)
    rake_usd = float(agg[9] or 0)

    summary_kwargs = dict(
        session_index=session_index,
        start_time=start.isoformat(),
        end_time=end.isoformat(),
        hands=n,
        duration_minutes=round(duration_min, 1),
        stakes=sorted(agg[3]) if agg[3] else [],
        won_bb=round(won_bb, 2),
        won_usd=round(won_usd, 2),
        ev_bb=round(ev_bb, 2),
        ev_usd=round(ev_usd, 2),
        rake_bb=round(rake_bb, 2),
        rake_usd=round(rake_usd, 2),
        bb_per_100=round((won_bb / n) * 100, 2) if n else 0,
        ev_bb_per_100=round((ev_bb / n) * 100, 2) if n else 0,
    )

    stats = SessionStats(
        **summary_kwargs,
        hands_per_hour=round(n / duration_hrs, 1) if duration_hrs > 0 else 0,
        usd_per_hour=round(won_usd / duration_hrs, 2) if duration_hrs > 0 else 0,
        bb_per_hour=round(won_bb / duration_hrs, 1) if duration_hrs > 0 else 0,
        vpip_pct=_safe_pct(int(agg[10] or 0), n),
        pfr_pct=_safe_pct(int(agg[11] or 0), n),
        three_bet_pct=_safe_pct(int(agg[12] or 0), int(agg[13] or 0)),
        cbet_flop_pct=_safe_pct(int(agg[14] or 0), int(agg[15] or 0)),
        wtsd_pct=_safe_pct(int(agg[17] or 0), int(agg[16] or 0)),
        wsd_pct=_safe_pct(int(agg[18] or 0), int(agg[17] or 0)),
        wwsf_pct=_safe_pct(int(agg[21] or 0), int(agg[16] or 0)),
        steal_pct=_safe_pct(int(agg[19] or 0), int(agg[20] or 0)),
        afq_flop_pct=_safe_pct(int(agg[22] or 0), int(agg[23] or 0)),
    )

    # Graph: per-hand cumulative values (only for this session)
    hand_rows = db.execute(f"""
        {_SESSION_CTE}
        SELECT played_at,
               CAST(won_bb AS DOUBLE),
               CAST(ev_bb AS DOUBLE),
               CAST(won AS DOUBLE),
               CAST(ev_bb AS DOUBLE) * CAST(bb_amount AS DOUBLE),
               went_to_showdown
        FROM sessioned
        WHERE session_idx = ?
        ORDER BY played_at, hand_id
    """, [player_id, workspace_id, session_index]).fetchall()

    graph = []
    cum_bb = cum_ev_bb = cum_sd_bb = cum_nsd_bb = 0.0
    cum_usd = cum_ev_usd = cum_sd_usd = cum_nsd_usd = 0.0
    for i, (played_at, h_won_bb, h_ev_bb, h_won_usd, h_ev_usd, went_sd) in enumerate(hand_rows):
        wb = float(h_won_bb or 0)
        eb = float(h_ev_bb or 0)
        wu = float(h_won_usd or 0)
        eu = float(h_ev_usd or 0)
        cum_bb += wb
        cum_ev_bb += eb
        cum_usd += wu
        cum_ev_usd += eu
        if went_sd:
            cum_sd_bb += wb
            cum_sd_usd += wu
        else:
            cum_nsd_bb += wb
            cum_nsd_usd += wu
        pa = played_at.isoformat() if isinstance(played_at, datetime) else str(played_at)
        graph.append(SessionGraphPoint(
            hand_number=i + 1,
            played_at=pa,
            cumulative_bb=round(cum_bb, 2),
            cumulative_ev_bb=round(cum_ev_bb, 2),
            cumulative_showdown_bb=round(cum_sd_bb, 2),
            cumulative_nonshowdown_bb=round(cum_nsd_bb, 2),
            cumulative_usd=round(cum_usd, 2),
            cumulative_ev_usd=round(cum_ev_usd, 2),
            cumulative_showdown_usd=round(cum_sd_usd, 2),
            cumulative_nonshowdown_usd=round(cum_nsd_usd, 2),
        ))

    # Biggest wins/losses via SQL ORDER BY + LIMIT
    def _fetch_big_hands(order_dir: str) -> list[SessionBigHand]:
        bh_rows = db.execute(f"""
            {_SESSION_CTE}
            SELECT hand_id, played_at, stakes,
                   CAST(won_bb AS DOUBLE), CAST(won AS DOUBLE),
                   position, card1, card2
            FROM sessioned
            WHERE session_idx = ?
              AND CAST(won_bb AS DOUBLE) {'> 0' if order_dir == 'DESC' else '< 0'}
            ORDER BY CAST(won_bb AS DOUBLE) {order_dir}
            LIMIT 5
        """, [player_id, workspace_id, session_index]).fetchall()
        result = []
        for r in bh_rows:
            pa = r[1].isoformat() if isinstance(r[1], datetime) else str(r[1])
            result.append(SessionBigHand(
                hand_id=r[0], played_at=pa, stakes=r[2],
                won_bb=round(float(r[3]), 2), won_usd=round(float(r[4] or 0), 2),
                position=r[5] or "", card1=r[6], card2=r[7],
            ))
        return result

    biggest_wins = _fetch_big_hands("DESC")
    biggest_losses = _fetch_big_hands("ASC")

    return SessionDetailResponse(
        session_index=session_index,
        stats=stats,
        graph=graph,
        biggest_wins=biggest_wins,
        biggest_losses=biggest_losses,
    )
