from fastapi import APIRouter, HTTPException
from app.db import get_read_cursor
from app.models import (
    SessionSummary,
    SessionListResponse,
    SessionGraphPoint,
    SessionStats,
    SessionBigHand,
    SessionDetailResponse,
)
from datetime import datetime, timedelta

router = APIRouter()

SESSION_GAP = timedelta(minutes=10)


def _get_hero_player_id(db):
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"
    player = db.execute(
        "SELECT id FROM players WHERE username = ? AND site_id = 1",
        [hero_username],
    ).fetchone()
    return player[0] if player else None


def _build_sessions(db, player_id):
    """Fetch all hero hands and split into sessions by 10-min gap."""
    rows = db.execute(
        """
        SELECT h.id, h.played_at, h.stakes, h.bb_amount,
               hp.won_bb, hp.won, hp.all_in_ev_bb, hp.rake_bb, hp.rake,
               hp.vpip, hp.pfr, hp.three_bet, hp.three_bet_opp,
               hp.cbet_flop, hp.cbet_flop_opp, hp.saw_flop,
               hp.went_to_showdown, hp.won_at_showdown,
               hp.steal_attempted, hp.steal_opp,
               hp.flop_bets, hp.flop_raises, hp.flop_calls, hp.flop_checks, hp.flop_folds,
               hp.position, hp.card1, hp.card2
        FROM hand_players hp JOIN hands h ON hp.hand_id = h.id
        WHERE hp.player_id = ?
        ORDER BY h.played_at ASC, h.id ASC
        """,
        [player_id],
    ).fetchall()

    if not rows:
        return []

    sessions = []
    current_session = []
    prev_played_at = None

    for row in rows:
        played_at = row[1]
        if isinstance(played_at, str):
            played_at = datetime.fromisoformat(played_at)

        if prev_played_at and (played_at - prev_played_at) > SESSION_GAP:
            sessions.append(current_session)
            current_session = []

        current_session.append(row)
        prev_played_at = played_at

    if current_session:
        sessions.append(current_session)

    return sessions


def _safe_pct(num, den):
    """Compute percentage from numerator/denominator counts, return None if no data."""
    if den == 0:
        return None
    return round((num / den) * 100, 1)


def _session_summary(session_index: int, hands) -> dict:
    """Build summary dict from a list of hand rows."""
    won_bb = sum(float(h[4] or 0) for h in hands)
    won_usd = sum(float(h[5] or 0) for h in hands)
    ev_bb = sum(float(h[6] or h[4] or 0) for h in hands)
    ev_usd = sum(float(h[6] or h[4] or 0) * float(h[3]) for h in hands)
    rake_bb = sum(float(h[7] or 0) for h in hands)
    rake_usd = sum(float(h[8] or 0) for h in hands)

    first_played = hands[0][1]
    last_played = hands[-1][1]
    if isinstance(first_played, str):
        first_played = datetime.fromisoformat(first_played)
    if isinstance(last_played, str):
        last_played = datetime.fromisoformat(last_played)

    duration_minutes = (last_played - first_played).total_seconds() / 60.0
    n = len(hands)
    stakes = sorted(set(h[2] for h in hands))

    return {
        "session_index": session_index,
        "start_time": first_played.isoformat(),
        "end_time": last_played.isoformat(),
        "hands": n,
        "duration_minutes": round(duration_minutes, 1),
        "stakes": stakes,
        "won_bb": round(won_bb, 2),
        "won_usd": round(won_usd, 2),
        "ev_bb": round(ev_bb, 2),
        "ev_usd": round(ev_usd, 2),
        "rake_bb": round(rake_bb, 2),
        "rake_usd": round(rake_usd, 2),
        "bb_per_100": round((won_bb / n) * 100, 2) if n else 0,
        "ev_bb_per_100": round((ev_bb / n) * 100, 2) if n else 0,
    }


@router.get("/sessions", response_model=SessionListResponse)
def get_sessions():
    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return SessionListResponse(sessions=[], total=0)

    sessions = _build_sessions(db, player_id)

    summaries = []
    for i, hands in enumerate(sessions):
        summaries.append(SessionSummary(**_session_summary(i, hands)))

    # Newest first
    summaries.reverse()

    return SessionListResponse(sessions=summaries, total=len(summaries))


@router.get("/sessions/{session_index}", response_model=SessionDetailResponse)
def get_session_detail(session_index: int):
    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        raise HTTPException(status_code=404, detail="Hero not found")

    sessions = _build_sessions(db, player_id)
    if session_index < 0 or session_index >= len(sessions):
        raise HTTPException(status_code=404, detail="Session not found")

    hands = sessions[session_index]
    summary = _session_summary(session_index, hands)
    n = summary["hands"]
    duration_hrs = summary["duration_minutes"] / 60.0

    # Play stats
    vpip_count = sum(1 for h in hands if h[9])
    pfr_count = sum(1 for h in hands if h[10])
    three_bet_count = sum(1 for h in hands if h[11])
    three_bet_opp_count = sum(1 for h in hands if h[12])
    cbet_flop_count = sum(1 for h in hands if h[13])
    cbet_flop_opp_count = sum(1 for h in hands if h[14])
    saw_flop_count = sum(1 for h in hands if h[15])
    wtsd_count = sum(1 for h in hands if h[16])
    wsd_count = sum(1 for h in hands if h[17])
    steal_count = sum(1 for h in hands if h[18])
    steal_opp_count = sum(1 for h in hands if h[19])

    # WWSF: won when saw flop
    wwsf_count = sum(1 for h in hands if h[15] and float(h[4] or 0) > 0)

    # AFq flop
    flop_agg_num = sum(int(h[20] or 0) + int(h[21] or 0) for h in hands)
    flop_agg_den = sum(
        int(h[20] or 0) + int(h[21] or 0) + int(h[22] or 0) + int(h[23] or 0) + int(h[24] or 0)
        for h in hands
    )

    stats = SessionStats(
        **summary,
        hands_per_hour=round(n / duration_hrs, 1) if duration_hrs > 0 else 0,
        usd_per_hour=round(summary["won_usd"] / duration_hrs, 2) if duration_hrs > 0 else 0,
        bb_per_hour=round(summary["won_bb"] / duration_hrs, 1) if duration_hrs > 0 else 0,
        vpip_pct=_safe_pct(vpip_count, n),
        pfr_pct=_safe_pct(pfr_count, n),
        three_bet_pct=_safe_pct(three_bet_count, three_bet_opp_count),
        cbet_flop_pct=_safe_pct(cbet_flop_count, cbet_flop_opp_count),
        wtsd_pct=_safe_pct(wtsd_count, saw_flop_count),
        wsd_pct=_safe_pct(wsd_count, wtsd_count),
        wwsf_pct=_safe_pct(wwsf_count, saw_flop_count),
        steal_pct=_safe_pct(steal_count, steal_opp_count),
        afq_flop_pct=_safe_pct(flop_agg_num, flop_agg_den),
    )

    # Graph: cumulative within session
    graph = []
    cum_bb = 0.0
    cum_ev_bb = 0.0
    cum_sd_bb = 0.0
    cum_nsd_bb = 0.0
    cum_usd = 0.0
    cum_ev_usd = 0.0
    cum_sd_usd = 0.0
    cum_nsd_usd = 0.0
    for i, h in enumerate(hands):
        won_bb = float(h[4] or 0)
        ev_bb_val = float(h[6] or h[4] or 0)
        won_usd = float(h[5] or 0)
        ev_usd_val = ev_bb_val * float(h[3])
        went_sd = bool(h[16])
        cum_bb += won_bb
        cum_ev_bb += ev_bb_val
        cum_usd += won_usd
        cum_ev_usd += ev_usd_val
        if went_sd:
            cum_sd_bb += won_bb
            cum_sd_usd += won_usd
        else:
            cum_nsd_bb += won_bb
            cum_nsd_usd += won_usd
        played_at = h[1]
        if isinstance(played_at, datetime):
            played_at = played_at.isoformat()
        graph.append(SessionGraphPoint(
            hand_number=i + 1,
            played_at=str(played_at),
            cumulative_bb=round(cum_bb, 2),
            cumulative_ev_bb=round(cum_ev_bb, 2),
            cumulative_showdown_bb=round(cum_sd_bb, 2),
            cumulative_nonshowdown_bb=round(cum_nsd_bb, 2),
            cumulative_usd=round(cum_usd, 2),
            cumulative_ev_usd=round(cum_ev_usd, 2),
            cumulative_showdown_usd=round(cum_sd_usd, 2),
            cumulative_nonshowdown_usd=round(cum_nsd_usd, 2),
        ))

    # Biggest wins/losses
    sorted_by_won = sorted(hands, key=lambda h: float(h[4] or 0), reverse=True)
    biggest_wins = []
    for h in sorted_by_won[:5]:
        won_bb = float(h[4] or 0)
        if won_bb <= 0:
            break
        played_at = h[1]
        if isinstance(played_at, datetime):
            played_at = played_at.isoformat()
        biggest_wins.append(SessionBigHand(
            hand_id=h[0],
            played_at=str(played_at),
            won_bb=round(won_bb, 2),
            won_usd=round(float(h[5] or 0), 2),
            position=h[25] or "",
            card1=h[26],
            card2=h[27],
            stakes=h[2],
        ))

    sorted_by_loss = sorted(hands, key=lambda h: float(h[4] or 0))
    biggest_losses = []
    for h in sorted_by_loss[:5]:
        won_bb = float(h[4] or 0)
        if won_bb >= 0:
            break
        played_at = h[1]
        if isinstance(played_at, datetime):
            played_at = played_at.isoformat()
        biggest_losses.append(SessionBigHand(
            hand_id=h[0],
            played_at=str(played_at),
            won_bb=round(won_bb, 2),
            won_usd=round(float(h[5] or 0), 2),
            position=h[25] or "",
            card1=h[26],
            card2=h[27],
            stakes=h[2],
        ))

    return SessionDetailResponse(
        session_index=session_index,
        stats=stats,
        graph=graph,
        biggest_wins=biggest_wins,
        biggest_losses=biggest_losses,
    )
