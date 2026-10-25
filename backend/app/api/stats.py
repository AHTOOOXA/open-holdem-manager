import math

from fastapi import APIRouter, Query, HTTPException, Path
from app.date_filters import DATE_TO_SQL
from app.db import get_read_cursor, get_hero_player_id, get_hero_username
from app.models import (
    HeroStats, StatDetailHand, StatDetailHandsResponse,
)
from app.stats_engine import compute_hero_stats
from app.stat_registry import POS_SQL, STAT_REGISTRY, get_key_street
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
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    hero_username = get_hero_username(db, workspace_id)

    return compute_hero_stats(db, hero_username, position=position, stakes=stakes,
                              game_mode=game_mode, date_from=date_from, date_to=date_to,
                              last_n=last_n, workspace_id=workspace_id)


@router.get("/stats/detail/{stat_key}/hands", response_model=StatDetailHandsResponse)
def get_stat_detail_hands(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=0, le=100),  # 0 = counts only (the detail header)
    workspace_id: int = Query(1),
):
    entry = STAT_REGISTRY.get(stat_key)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Unknown stat key: {stat_key}")

    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
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
    where_parts = ["hp.player_id = ?", "h.workspace_id = ?"]
    params: list = [player_id, workspace_id]

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
        where_parts.append(POS_SQL + " = ?")
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
        where_parts.append(DATE_TO_SQL)
        params.append(date_to)

    where_sql = " AND ".join(where_parts)

    # Count totals: opportunity count + action count
    count_query = f"""
        SELECT COUNT(*),
               SUM(CASE WHEN {action_expr} THEN 1 ELSE 0 END)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {where_sql}
    """
    row = db.execute(count_query, params).fetchone()
    total = int(row[0])
    action_count = int(row[1] or 0)

    # Hand list filters by action (only show hands where stat was triggered).
    # Pagination is based on action_count, not total opportunity count.
    list_where_sql = f"{where_sql} AND ({action_expr})"
    # Compute key street for this stat
    key_street = get_key_street(stat_key)
    if per_page == 0:
        return StatDetailHandsResponse(
            stat_key=stat_key, stat_name=entry["name"],
            action_count=action_count, opportunity_count=total,
            key_street=key_street,
            hands=[], total=action_count, page=page, per_page=0, total_pages=0,
        )
    total_pages = max(1, math.ceil(action_count / per_page))
    offset = (page - 1) * per_page

    # Get hero username for action parsing
    hero_username = get_hero_username(db, workspace_id)

    # Fetch the hands page without raw_text (the sort would otherwise carry every
    # candidate's hand text), then raw_text for the page's hands only.
    hands_query = f"""
        SELECT h.id, h.played_at, {POS_SQL} AS position, hp.card1, hp.card2,
               ({action_expr}) AS action_taken, hp.won_bb, h.stakes,
               hp.all_in_ev_bb, h.bb_amount
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {list_where_sql}
        ORDER BY h.played_at DESC
        LIMIT ? OFFSET ?
    """
    rows = db.execute(hands_query, params + [per_page, offset]).fetchall()
    if rows:
        ph = ",".join("?" for _ in rows)
        texts = dict(db.execute(
            f"SELECT id, raw_text FROM hands WHERE id IN ({ph}) AND workspace_id = ?",
            [r[0] for r in rows] + [workspace_id],
        ).fetchall())
        rows = [(*r, texts.get(r[0])) for r in rows]

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
        f"SELECT hand_id, street, card FROM board_cards WHERE hand_id IN ({ph}) AND workspace_id = ? ORDER BY hand_id, card_order",
        hand_ids + [workspace_id],
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
