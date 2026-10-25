from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import math
import re
from types import SimpleNamespace

from app.app_settings import get_app_settings
from app.date_filters import bound_sql
from app.db import get_db, db_lock, get_read_cursor, get_hero_player_id, get_hero_username
from app.models import (
    HandSummary, HandListResponse, HandDetail, HandPlayerDetail,
    HandAction, BoardCards, ActionItem, TagRef,
)
from app import marked_hands
from app.action_parser import parse_actions_from_raw
from app.stat_registry import STAT_REGISTRY

router = APIRouter()



_SORTS = {
    "played_at": "h.played_at",
    "won_bb": "hp.won_bb",
    "won_usd": "hp.won_bb * h.bb_amount",
    "stakes": "h.bb_amount",
    # Tags column: the first tag's catalogue position, untagged rows -1
    "tags": "COALESCE((SELECT MIN(td.position) FROM marked_hand_tags mt "
            "JOIN tag_defs td ON td.id = mt.tag_id WHERE mt.workspace_id = h.workspace_id "
            "AND mt.hand_id = h.id AND mt.player_id = hp.player_id), -1)",
}

def _list_filters(db, *, position, stakes, result, marked, tag_ids, date_from, date_to, search,
                  stat_flag, stat_key, player_id, workspace_id, chain):
    """WHERE-building of the hand list (shared with the export). `.status` is "ok", or
    "no_subject" / "empty_chain" when the list is empty."""
    # The listed rows are the subject's: player_id when given, else the hero.
    hero_id = player_id if player_id is not None else get_hero_player_id(db, workspace_id)
    # Marked view without a subject: every marked (hand, player) pair of the workspace, each row
    # from the marked player's point of view.
    all_marked = player_id is None and (bool(marked) or bool(marked_hands.parse_id_list(tag_ids)))
    if hero_id is None and not all_marked:
        return SimpleNamespace(status="no_subject")

    # The chain's case hands as a SQL predicate (no id list bound into the query).
    from app.api.reports_lite import chain_scope
    scope = chain_scope(db, workspace_id, player_id, chain)
    if scope is not None and scope.empty:
        return SimpleNamespace(status="empty_chain")

    if player_id is not None:
        urow = db.execute("SELECT username FROM players WHERE id = ?", [player_id]).fetchone()
        hero_username = urow[0] if urow else None
    else:
        hero_username = get_hero_username(db, workspace_id)
    if all_marked:
        # Driven from the (few) marks instead of probing marked_hands for every hand_players
        # row. marked_hands is keyed (workspace, hand, player): one row per marked pair, the
        # same rows as the old `EXISTS (marked_hands …)` join condition.
        from_sql = ("marked_hands mh0 "
                    "JOIN hand_players hp ON hp.workspace_id = mh0.workspace_id "
                    "AND hp.hand_id = mh0.hand_id AND hp.player_id = mh0.player_id "
                    "JOIN hands h ON h.id = hp.hand_id AND h.workspace_id = hp.workspace_id")
        params: list = []
    else:
        from_sql = ("hands h JOIN hand_players hp ON hp.hand_id = h.id "
                    "AND hp.workspace_id = h.workspace_id AND hp.player_id = ?")
        params = [hero_id]
    where_clauses: list[str] = ["h.workspace_id = ?"]
    params.append(workspace_id)

    if position:
        positions = [p.strip().upper() for p in position.split(",") if p.strip()]
        if positions:
            ph = ",".join("?" for _ in positions)
            where_clauses.append(f"hp.position IN ({ph})")
            params.extend(positions)

    if stakes:
        stakes_list = [s.strip() for s in stakes.split(",") if s.strip()]
        if stakes_list:
            ph = ",".join("?" for _ in stakes_list)
            where_clauses.append(f"h.stakes IN ({ph})")
            params.extend(stakes_list)

    if result:
        result_map = {
            "won": "hp.won_bb > 0",
            "lost": "hp.won_bb < 0",
            "big_win": "hp.won_bb > 10",
            "big_loss": "hp.won_bb < -10",
            "breakeven": "hp.won_bb = 0",
        }
        if result in result_map:
            where_clauses.append(result_map[result])

    # In the marked view every row is a mark already (the FROM starts at marked_hands), so a
    # `marked=true` EXISTS would always hold.
    mark_clauses, mark_params = marked_hands.list_filter_sql(
        None if (all_marked and marked) else marked,
        marked_hands.parse_id_list(tag_ids) or None, "h.id", "h.workspace_id", "hp.player_id")
    where_clauses.extend(mark_clauses)
    params.extend(mark_params)

    day_start = int(get_app_settings(db)["day_start_hour"])
    if date_from:
        frag, val = bound_sql("from", date_from, day_start)
        where_clauses.append(frag)
        params.append(val)
    if date_to:
        frag, val = bound_sql("to", date_to, day_start)
        where_clauses.append(frag)
        params.append(val)

    # (With player_id the row join is already `hp.player_id = player_id`, so "the player sat in
    # the hand" holds for every joined row: no extra EXISTS.)

    if scope is not None:
        frag, frag_params = scope.where("h.id")
        where_clauses.append(frag)
        params.extend(frag_params)

    if search:
        where_clauses.append("h.id LIKE ?")
        params.append(f"%{search.strip()}%")

    if stat_flag:
        import re
        for flag in stat_flag:
            negate = flag.startswith('!')
            real_flag = flag[1:] if negate else flag
            if not re.match(r'^[a-z_]+$', real_flag):
                continue
            if negate:
                where_clauses.append(f"hp.{real_flag} IS NOT TRUE")
            else:
                where_clauses.append(f"hp.{real_flag} = true")

    if stat_key:
        entry = STAT_REGISTRY.get(stat_key)
        if entry:
            opp_flag = entry.get("opp_flag")
            opp_sql = entry.get("opp_sql")
            opp_is_not_null = entry.get("opp_is_not_null", False)
            extra_where = entry.get("extra_where")
            if opp_sql:
                where_clauses.append(f"({opp_sql})")
            elif opp_flag:
                if opp_is_not_null:
                    where_clauses.append(f"hp.{opp_flag} IS NOT NULL")
                else:
                    where_clauses.append(f"hp.{opp_flag} = TRUE")
            if extra_where:
                where_clauses.append(extra_where)

    # Only the chain filters the subject's rows: each case hand has exactly one subject row, so
    # the list total is the chain's case count (no COUNT query needed).
    known_total = (scope.count if scope is not None and not all_marked and len(where_clauses) == 2
                   else None)
    where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""
    return SimpleNamespace(status="ok", from_sql=from_sql, where_sql=where_sql,
                           params=params, hero_id=hero_id, hero_username=hero_username,
                           all_marked=all_marked, known_total=known_total)


@router.get("/hands", response_model=HandListResponse)
def list_hands(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("played_at"),
    order: str = Query("desc"),
    position: Optional[str] = None,
    stakes: Optional[str] = None,
    result: Optional[str] = None,
    marked: Optional[bool] = Query(None, description="true: only hands marked for the row's player; false: only unmarked"),
    tag_ids: Optional[str] = Query(None, description="Comma list of tag ids; hands carrying any of them (implies marked)"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    stat_flag: list[str] | None = Query(None),
    stat_key: Optional[str] = Query(None),
    player_id: Optional[int] = Query(None),
    workspace_id: int = Query(1),
    chain: Optional[str] = Query(None, description="Reports filter chain: URL-encoded JSON Step[] "
                                 "(frontend/src/lib/reports/types.ts), resolved for player_id "
                                 "or the hero; combined with the other filters with AND. Any "
                                 "chain, even [], keeps only H2N-valid hands (as the Reports "
                                 "counts do)"),
):
    db = get_read_cursor()
    f = _list_filters(
        db, position=position, stakes=stakes, result=result, marked=marked, tag_ids=tag_ids,
        date_from=date_from, date_to=date_to, search=search, stat_flag=stat_flag,
        stat_key=stat_key, player_id=player_id, workspace_id=workspace_id, chain=chain)
    if f.status == "no_subject":
        return HandListResponse(hands=[], total=0, page=1, per_page=per_page, total_pages=0)
    if f.status == "empty_chain":
        return HandListResponse(hands=[], total=0, page=1, per_page=per_page, total_pages=1)
    from_sql, where_sql, params = f.from_sql, f.where_sql, f.params
    hero_id, hero_username, all_marked = f.hero_id, f.hero_username, f.all_marked

    count_sql = f"""
        SELECT COUNT(*)
        FROM {from_sql}
        WHERE 1=1 {where_sql}
    """
    total = f.known_total
    if total is None:
        total = db.execute(count_sql, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))

    sort_col = _SORTS.get(sort, "h.played_at")
    sort_dir = "DESC" if order.lower() == "desc" else "ASC"

    offset = (page - 1) * per_page
    main_sql = f"""
        SELECT h.id, h.played_at, h.stakes, h.bb_amount,
               hp.position, hp.card1, hp.card2, hp.won_bb,
               hp.all_in_ev_bb, h.rit_boards, h.is_cashout, hp.player_id
        FROM {from_sql}
        WHERE 1=1 {where_sql}
        ORDER BY {sort_col} {sort_dir}, h.played_at DESC, h.id, hp.player_id
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    rows = db.execute(main_sql, params).fetchall()

    if not rows:
        return HandListResponse(hands=[], total=total, page=page, per_page=per_page, total_pages=total_pages)

    hand_ids = [r[0] for r in rows]
    ph = ",".join("?" for _ in hand_ids)

    # Marks + tags of the row player
    pids_by_row = {(r[0], r[11]) for r in rows}
    marked_set: set = set()
    tags_map: dict = {}
    for pid_ in {pid for _, pid in pids_by_row}:
        ms, tm = marked_hands.marks_for(db, workspace_id, pid_, [h for h, p in pids_by_row if p == pid_])
        marked_set |= {(h, pid_) for h in ms}
        tags_map.update({(h, pid_): t for h, t in tm.items()})

    # Batch fetch board cards by street (Board 1 only for list view)
    board_rows = db.execute(
        f"SELECT hand_id, street, card FROM board_cards WHERE hand_id IN ({ph}) AND workspace_id = ? AND board_number = 1 ORDER BY hand_id, card_order",
        hand_ids + [workspace_id],
    ).fetchall()
    board_map: dict[str, dict[str, list[str]]] = {}
    for hid, street, card in board_rows:
        board_map.setdefault(hid, {"flop": [], "turn": [], "river": []})
        board_map[hid][street].append(card)

    _STREETS = ("preflop", "flop", "turn", "river")

    # Try batch fetch actions from DB
    action_rows = db.execute(
        f"SELECT a.hand_id, a.street, a.action_type, a.amount_bb, a.player_id "
        f"FROM actions a WHERE a.hand_id IN ({ph}) AND a.workspace_id = ? ORDER BY a.hand_id, a.action_order",
        hand_ids + [workspace_id],
    ).fetchall()

    actions_map: dict[str, dict[str, dict]] = {}
    action_pid: dict[int, int] = {}
    _ACT_MAP = {"raise": "R", "bet": "B", "call": "C", "check": "X", "fold": "F"}
    _BLIND_TYPES = {"sb", "bb", "ante", "straddle"}

    for hid, street, action_type, amount_bb, pid in action_rows:
        hand_acts = actions_map.setdefault(hid, {
            s: {"actions": [], "pot": 0} for s in _STREETS
        })
        amt_bb_f = float(amount_bb) if amount_bb is not None else 0
        if action_type in _BLIND_TYPES:
            hand_acts["preflop"]["pot"] += amt_bb_f
            continue
        abbr = _ACT_MAP.get(action_type)
        if not abbr or street not in hand_acts:
            continue
        v = round(amt_bb_f, 1) if amt_bb_f else None
        item = ActionItem(a=abbr, v=v, h=(pid == hero_id))
        action_pid[id(item)] = pid
        hand_acts[street]["actions"].append(item)

    # Propagate pot sizes for hands that had DB actions
    for hid, hand_acts in actions_map.items():
        running = 0
        for s in _STREETS:
            sa = hand_acts[s]
            street_total = sum(
                (float(ai.v) if ai.v else 0) for ai in sa["actions"] if ai.a in ("R", "B", "C")
            )
            sa["pot"] = round(running + sa.get("pot", 0))
            running = sa["pot"] + round(street_total)

    # Fallback: parse from raw_text for any hands missing from actions table
    raw_by_hand: dict[str, tuple[str, float]] = {}
    missing_ids = [hid for hid in hand_ids if hid not in actions_map]
    if missing_ids:
        mph = ",".join("?" for _ in missing_ids)
        raw_rows = db.execute(
            f"SELECT id, raw_text, bb_amount FROM hands WHERE id IN ({mph}) AND workspace_id = ?",
            missing_ids + [workspace_id],
        ).fetchall()
        for hid, raw_text, bb_amt in raw_rows:
            if not raw_text:
                continue
            bb = float(bb_amt) if bb_amt else 0
            ss = parse_actions_from_raw(raw_text, hero_username, bb)
            actions_map[hid] = ss
            raw_by_hand[hid] = (raw_text, bb)

    usernames: dict[int, str] = {}
    if all_marked:
        row_pids = sorted({int(r[11]) for r in rows})
        usernames = {int(i): u for i, u in db.execute(
            "SELECT id, username FROM players WHERE id IN (SELECT UNNEST(?::INTEGER[]))", [row_pids]).fetchall()}

    hands = []
    for r in rows:
        hid = r[0]
        bb_amount = float(r[3])

        board = board_map.get(hid, {"flop": [], "turn": [], "river": []})
        row_pid = int(r[11])
        hand_acts = actions_map.get(hid, {s: {"actions": [], "pot": 0} for s in _STREETS})
        if all_marked:
            # Re-express the actions from this row's player (a hand can be marked for several)
            if hid in raw_by_hand:
                raw_text, bb = raw_by_hand[hid]
                uname = usernames.get(row_pid)
                hand_acts = parse_actions_from_raw(raw_text, uname, bb)
            else:
                hand_acts = {s: {"pot": v["pot"], "actions": [
                    ActionItem(a=a.a, v=a.v, h=(action_pid.get(id(a)) == row_pid)) for a in v["actions"]]}
                    for s, v in hand_acts.items()}

        hands.append(HandSummary(
            id=hid,
            player_id=row_pid,
            played_at=r[1],
            stakes=r[2],
            bb_amount=bb_amount,
            position=r[4],
            card1=r[5],
            card2=r[6],
            won_bb=float(r[7]),
            all_in_ev_bb=float(r[8]) if r[8] is not None else float(r[7]),
            rit_boards=int(r[9]) if r[9] is not None else 1,
            is_cashout=bool(r[10]) if r[10] is not None else False,
            marked=(hid, row_pid) in marked_set,
            tags=[TagRef(**t) for t in tags_map.get((hid, row_pid), [])],
            preflop_actions=hand_acts["preflop"]["actions"],
            flop_cards=board["flop"],
            flop_pot=hand_acts["flop"]["pot"],
            flop_actions=hand_acts["flop"]["actions"],
            turn_card=board["turn"][0] if board["turn"] else None,
            turn_pot=hand_acts["turn"]["pot"],
            turn_actions=hand_acts["turn"]["actions"],
            river_card=board["river"][0] if board["river"] else None,
            river_pot=hand_acts["river"]["pot"],
            river_actions=hand_acts["river"]["actions"],
        ))

    return HandListResponse(
        hands=hands,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# ── Hand detail ──────────────────────────────────────────────────────

EXPORT_CAP = 100_000
_EXPORT_BATCH = 500


@router.get("/hands/export")
def export_hands(
    sort: str = Query("played_at"),
    order: str = Query("desc"),
    format: str = Query("txt", pattern="^txt$"),
    position: Optional[str] = None,
    stakes: Optional[str] = None,
    result: Optional[str] = None,
    marked: Optional[bool] = Query(None),
    tag_ids: Optional[str] = Query(None),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    stat_flag: list[str] | None = Query(None),
    stat_key: Optional[str] = Query(None),
    player_id: Optional[int] = Query(None),
    workspace_id: int = Query(1),
    chain: Optional[str] = Query(None),
):
    """The original hand histories of the whole filtered list (same filters and order as
    GET /api/hands, not just a page): text/plain attachment, hands separated by two blank
    lines, each hand once, at most EXPORT_CAP hands (`X-OHM-Truncated: 1` when capped)."""
    db = get_read_cursor()
    f = _list_filters(
        db, position=position, stakes=stakes, result=result, marked=marked, tag_ids=tag_ids,
        date_from=date_from, date_to=date_to, search=search, stat_flag=stat_flag,
        stat_key=stat_key, player_id=player_id, workspace_id=workspace_id, chain=chain)
    ids: list[str] = []
    if f.status == "ok":
        sort_col = _SORTS.get(sort, "h.played_at")
        sort_dir = "DESC" if order.lower() == "desc" else "ASC"
        # A marked list without a subject has one row per marked (hand, player): one per hand.
        ids = [r[0] for r in db.execute(f"""
            SELECT id FROM (
                SELECT h.id, {sort_col} AS sk, h.played_at AS pa,
                       ROW_NUMBER() OVER (PARTITION BY h.id ORDER BY {sort_col} {sort_dir}, hp.player_id) AS rn
                FROM {f.from_sql}
                WHERE h.raw_text IS NOT NULL AND h.raw_text <> '' {f.where_sql}
            ) WHERE rn = 1
            ORDER BY sk {sort_dir}, pa DESC, id
            LIMIT ?
        """, [*f.params, EXPORT_CAP + 1]).fetchall()]
    truncated = len(ids) > EXPORT_CAP
    ids = ids[:EXPORT_CAP]

    def stream():
        # The request's cursors are closed when the endpoint returns; the stream has its own.
        cur = get_db().cursor()
        try:
            yield from _stream_texts(cur)
        finally:
            cur.close()

    def _stream_texts(db):
        first = True
        for i in range(0, len(ids), _EXPORT_BATCH):
            batch = ids[i:i + _EXPORT_BATCH]
            ph = ",".join("?" for _ in batch)
            texts = dict(db.execute(
                f"SELECT id, raw_text FROM hands WHERE workspace_id = ? AND id IN ({ph})",
                [workspace_id, *batch]).fetchall())
            chunk = []
            for hid in batch:
                t = (texts.get(hid) or "").strip()
                if t:
                    chunk.append(t)
            if chunk:
                yield (("" if first else "\n\n\n") + "\n\n\n".join(chunk)).encode("utf-8")
                first = False
        if not first:
            yield b"\n"

    headers = {"Content-Disposition": 'attachment; filename="OHM hands.txt"'}
    if truncated:
        headers["X-OHM-Truncated"] = "1"
    return StreamingResponse(stream(), media_type="text/plain; charset=utf-8", headers=headers)


@router.get("/hands/{hand_id}", response_model=HandDetail)
def get_hand(hand_id: str, workspace_id: int = Query(1),
             player_id: Optional[int] = Query(None, description="Whose mark/tags to return; defaults to the hero")):
    db = get_read_cursor()
    hero_id = get_hero_player_id(db, workspace_id)
    hero_username = get_hero_username(db, workspace_id)

    hand_row = db.execute(
        "SELECT id, played_at, stakes, bb_amount, table_name, table_size, raw_text, "
        "rit_boards, is_cashout "
        "FROM hands WHERE id = ? AND workspace_id = ?",
        [hand_id, workspace_id],
    ).fetchone()
    if not hand_row:
        raise HTTPException(status_code=404, detail="Hand not found")

    bb_amount = float(hand_row[3])
    raw_text = hand_row[6] or ""

    # Players
    player_rows = db.execute(
        "SELECT hp.seat, hp.position, p.username, hp.stack_bb, hp.card1, hp.card2, "
        "hp.won_bb, hp.player_id, COALESCE(pc.player_type, 'UNK') "
        "FROM hand_players hp "
        "JOIN players p ON p.id = hp.player_id "
        "LEFT JOIN player_classifications pc ON pc.player_id = p.id AND pc.workspace_id = hp.workspace_id "
        "WHERE hp.hand_id = ? AND hp.workspace_id = ? "
        "ORDER BY hp.seat",
        [hand_id, workspace_id],
    ).fetchall()

    players = []
    player_name_map: dict[int, tuple[str, str]] = {}
    for pr in player_rows:
        player_name_map[pr[7]] = (pr[2], pr[1])
        players.append(HandPlayerDetail(
            seat=pr[0],
            player_id=pr[7],
            position=pr[1],
            username=pr[2],
            stack_bb=float(pr[3]) if pr[3] is not None else 0.0,
            card1=pr[4],
            card2=pr[5],
            won_bb=float(pr[6]),
            is_hero=(pr[7] == hero_id),
            player_type=pr[8] or "UNK",
        ))

    # Board cards — group by board_number (1=primary, 2+=extra boards)
    board_rows = db.execute(
        "SELECT street, card, board_number FROM board_cards WHERE hand_id = ? AND workspace_id = ? ORDER BY board_number, card_order",
        [hand_id, workspace_id],
    ).fetchall()
    board = BoardCards()
    extra_boards_map: dict[int, BoardCards] = {}
    for street, card, bn in board_rows:
        if bn == 1:
            target = board
        else:
            if bn not in extra_boards_map:
                extra_boards_map[bn] = BoardCards()
            target = extra_boards_map[bn]
        if street == "flop":
            target.flop.append(card)
        elif street == "turn":
            target.turn.append(card)
        elif street == "river":
            target.river.append(card)
    extra_boards_list = [extra_boards_map[k] for k in sorted(extra_boards_map.keys())]
    rit_boards = int(hand_row[7]) if hand_row[7] is not None else 1
    is_cashout = bool(hand_row[8]) if hand_row[8] is not None else False

    # Build username→position map from player rows
    username_to_position: dict[str, str] = {}
    for pr in player_rows:
        username_to_position[pr[2]] = pr[1]  # pr[2]=username, pr[1]=position

    # Extract blind/ante postings from raw text (before *** HOLE CARDS ***)
    _RE_BLIND_POST = re.compile(r'^(.+?): posts (small blind|big blind|ante) \$([0-9.]+)')
    _BLIND_ACTION = {"small blind": "post_sb", "big blind": "post_bb", "ante": "post_ante"}
    blind_actions: list[HandAction] = []
    for line in raw_text.split('\n'):
        line_s = line.strip()
        if '*** HOLE CARDS ***' in line_s:
            break
        m = _RE_BLIND_POST.match(line_s)
        if m:
            pname, btype, amt_str = m.group(1), m.group(2), m.group(3)
            amt_bb = round(float(amt_str) / bb_amount, 2) if bb_amount > 0 else 0
            is_hero = pname == hero_username
            blind_actions.append(HandAction(
                street="preflop",
                player="Hero" if is_hero else pname,
                position=username_to_position.get(pname, ""),
                action=_BLIND_ACTION[btype],
                amount_bb=amt_bb,
                is_all_in=False,
                is_hero=is_hero,
            ))

    # Parse voluntary actions from raw text
    ss = parse_actions_from_raw(raw_text, hero_username, bb_amount)

    abbr_to_action = {"R": "raise", "B": "bet", "C": "call", "X": "check", "F": "fold"}
    actions: list[HandAction] = []
    for street_name in ["preflop", "flop", "turn", "river"]:
        for ai in ss[street_name]["actions"]:
            act_name = abbr_to_action.get(ai.a, ai.a)
            amt_bb = float(ai.v) if ai.v is not None else None
            player_name = ai.p or ("Hero" if ai.h else "")
            position = username_to_position.get(player_name, "")
            actions.append(HandAction(
                street=street_name,
                player="Hero" if ai.h else player_name,
                position=position,
                action=act_name,
                amount_bb=amt_bb,
                is_all_in=bool(ai.ai),
                is_hero=ai.h,
            ))

    # Prepend blind postings before voluntary actions
    actions = blind_actions + actions

    # Mark + tags (the given player, else the hero)
    mark_pid = player_id if player_id is not None else hero_id
    marked_set, tags_map = (marked_hands.marks_for(db, workspace_id, mark_pid, [hand_id])
                            if mark_pid is not None else (set(), {}))

    # Note
    note_row = db.execute(
        "SELECT note FROM hand_notes WHERE hand_id = ? AND workspace_id = ?",
        [hand_id, workspace_id],
    ).fetchone()
    note = note_row[0] if note_row else None

    return HandDetail(
        id=hand_row[0],
        played_at=hand_row[1],
        stakes=hand_row[2],
        bb_amount=bb_amount,
        table_name=hand_row[4],
        table_size=hand_row[5],
        raw_text=raw_text,
        players=players,
        board=board,
        extra_boards=extra_boards_list,
        rit_boards=rit_boards,
        is_cashout=is_cashout,
        actions=actions,
        marked=hand_id in marked_set,
        tags=[TagRef(**t) for t in tags_map.get(hand_id, [])],
        note=note,
    )


# ── Notes ────────────────────────────────────────────────────────────

class NoteBody(BaseModel):
    note: str


@router.put("/hands/{hand_id}/note")
def update_note(hand_id: str, body: NoteBody, workspace_id: int = Query(1)):
    with db_lock():
        db = get_db()
        if not db.execute("SELECT 1 FROM hands WHERE id = ? AND workspace_id = ?", [hand_id, workspace_id]).fetchone():
            raise HTTPException(status_code=404, detail="Hand not found")
        existing = db.execute(
            "SELECT 1 FROM hand_notes WHERE hand_id = ? AND workspace_id = ?", [hand_id, workspace_id]
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE hand_notes SET note = ?, updated_at = CURRENT_TIMESTAMP WHERE hand_id = ? AND workspace_id = ?",
                [body.note, hand_id, workspace_id],
            )
        else:
            db.execute(
                "INSERT INTO hand_notes (hand_id, note, workspace_id) VALUES (?, ?, ?)",
                [hand_id, body.note, workspace_id],
            )
        return {"status": "ok"}


@router.delete("/hands/{hand_id}/note")
def delete_note(hand_id: str, workspace_id: int = Query(1)):
    with db_lock():
        db = get_db()
        db.execute("DELETE FROM hand_notes WHERE hand_id = ? AND workspace_id = ?", [hand_id, workspace_id])
        return {"status": "ok"}
