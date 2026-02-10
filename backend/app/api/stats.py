from fastapi import APIRouter, Query
from app.db import get_read_cursor
from app.models import HeroStats, ComboStats, RangeResponse
from app.stats_engine import compute_hero_stats

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
):
    db = get_read_cursor()
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_username = row[0] if row else "Hero"

    return compute_hero_stats(db, hero_username, position=position, stakes=stakes,
                              game_mode=game_mode, date_from=date_from, date_to=date_to)


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
        params.append(position)
    if stakes:
        query += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode:
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
        total_params.append(position)
    if stakes:
        total_query += " AND h.stakes = ?"
        total_params.append(stakes)
    if game_mode:
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
