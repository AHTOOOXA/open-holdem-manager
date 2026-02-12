from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
import math

from app.db import get_db, db_lock, get_read_cursor
from app.models import (
    HandSummary, HandListResponse, HandDetail, HandPlayerDetail,
    HandAction, BoardCards, TagCount, ActionItem,
)
from app.action_parser import parse_actions_from_raw
from app.stat_registry import STAT_REGISTRY

router = APIRouter()

# ── Hero username helper ─────────────────────────────────────────────

def _get_hero_player_id(db) -> Optional[int]:
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    if not row:
        return None
    hero_username = row[0]

    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_site'"
    ).fetchone()
    hero_site = row[0] if row else "GG"

    row = db.execute(
        "SELECT p.id FROM players p JOIN sites s ON p.site_id = s.id "
        "WHERE p.username = ? AND s.code = ?",
        [hero_username, hero_site],
    ).fetchone()
    return row[0] if row else None


def _get_hero_username(db) -> str:
    row = db.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    return row[0] if row else "Hero"


# ── List hands ───────────────────────────────────────────────────────

@router.get("/hands", response_model=HandListResponse)
def list_hands(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    sort: str = Query("played_at"),
    order: str = Query("desc"),
    position: Optional[str] = None,
    stakes: Optional[str] = None,
    result: Optional[str] = None,
    tags: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    stat_flag: list[str] | None = Query(None),
    stat_key: Optional[str] = Query(None),
):
    db = get_read_cursor()
    hero_id = _get_hero_player_id(db)
    if hero_id is None:
        return HandListResponse(hands=[], total=0, page=1, per_page=per_page, total_pages=0)

    hero_username = _get_hero_username(db)
    params: list = [hero_id]
    where_clauses: list[str] = []

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

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if "untagged" in [t.lower() for t in tag_list]:
            where_clauses.append(
                "NOT EXISTS (SELECT 1 FROM hand_tags ht2 WHERE ht2.hand_id = h.id)"
            )
        else:
            ph = ",".join("?" for _ in tag_list)
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM hand_tags ht2 WHERE ht2.hand_id = h.id AND ht2.tag IN ({ph}))"
            )
            params.extend(tag_list)

    if date_from:
        where_clauses.append("h.played_at >= ?")
        params.append(date_from)
    if date_to:
        where_clauses.append("h.played_at <= ?")
        params.append(date_to)

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

    where_sql = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

    count_sql = f"""
        SELECT COUNT(*)
        FROM hands h
        JOIN hand_players hp ON hp.hand_id = h.id AND hp.player_id = ?
        WHERE 1=1 {where_sql}
    """
    total = db.execute(count_sql, params).fetchone()[0]
    total_pages = max(1, math.ceil(total / per_page))

    allowed_sorts = {
        "played_at": "h.played_at",
        "won_bb": "hp.won_bb",
        "won_usd": "hp.won_bb * h.bb_amount",
        "stakes": "h.bb_amount",
    }
    sort_col = allowed_sorts.get(sort, "h.played_at")
    sort_dir = "DESC" if order.lower() == "desc" else "ASC"

    offset = (page - 1) * per_page
    main_sql = f"""
        SELECT h.id, h.played_at, h.stakes, h.bb_amount,
               hp.position, hp.card1, hp.card2, hp.won_bb,
               hp.all_in_ev_bb, h.raw_text
        FROM hands h
        JOIN hand_players hp ON hp.hand_id = h.id AND hp.player_id = ?
        WHERE 1=1 {where_sql}
        ORDER BY {sort_col} {sort_dir}, h.played_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([per_page, offset])
    rows = db.execute(main_sql, params).fetchall()

    if not rows:
        return HandListResponse(hands=[], total=total, page=page, per_page=per_page, total_pages=total_pages)

    hand_ids = [r[0] for r in rows]
    ph = ",".join("?" for _ in hand_ids)

    # Batch fetch tags
    tag_rows = db.execute(
        f"SELECT hand_id, tag FROM hand_tags WHERE hand_id IN ({ph})",
        hand_ids,
    ).fetchall()
    tags_map: dict[str, list[str]] = {}
    for hid, tag in tag_rows:
        tags_map.setdefault(hid, []).append(tag)

    # Batch fetch board cards by street
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
        bb_amount = float(r[3])
        raw_text = r[9] or ""

        board = board_map.get(hid, {"flop": [], "turn": [], "river": []})

        # Parse actions from raw text
        ss = parse_actions_from_raw(raw_text, hero_username, bb_amount)
        pf = ss["preflop"]
        fl = ss["flop"]
        tu = ss["turn"]
        ri = ss["river"]

        hands.append(HandSummary(
            id=hid,
            played_at=r[1],
            stakes=r[2],
            bb_amount=bb_amount,
            position=r[4],
            card1=r[5],
            card2=r[6],
            won_bb=float(r[7]),
            all_in_ev_bb=float(r[8]) if r[8] is not None else float(r[7]),
            tags=tags_map.get(hid, []),
            preflop_actions=pf["actions"],
            flop_cards=board["flop"],
            flop_pot=fl["pot"],
            flop_actions=fl["actions"],
            turn_card=board["turn"][0] if board["turn"] else None,
            turn_pot=tu["pot"],
            turn_actions=tu["actions"],
            river_card=board["river"][0] if board["river"] else None,
            river_pot=ri["pot"],
            river_actions=ri["actions"],
        ))

    return HandListResponse(
        hands=hands,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


# ── Hand detail ──────────────────────────────────────────────────────

@router.get("/hands/{hand_id}", response_model=HandDetail)
def get_hand(hand_id: str):
    db = get_read_cursor()
    hero_id = _get_hero_player_id(db)
    hero_username = _get_hero_username(db)

    hand_row = db.execute(
        "SELECT id, played_at, stakes, bb_amount, table_name, table_size, raw_text "
        "FROM hands WHERE id = ?",
        [hand_id],
    ).fetchone()
    if not hand_row:
        raise HTTPException(status_code=404, detail="Hand not found")

    bb_amount = float(hand_row[3])
    raw_text = hand_row[6] or ""

    # Players
    player_rows = db.execute(
        "SELECT hp.seat, hp.position, p.username, hp.stack_bb, hp.card1, hp.card2, "
        "hp.won_bb, hp.player_id "
        "FROM hand_players hp "
        "JOIN players p ON p.id = hp.player_id "
        "WHERE hp.hand_id = ? "
        "ORDER BY hp.seat",
        [hand_id],
    ).fetchall()

    players = []
    player_name_map: dict[int, tuple[str, str]] = {}
    for pr in player_rows:
        player_name_map[pr[7]] = (pr[2], pr[1])
        players.append(HandPlayerDetail(
            seat=pr[0],
            position=pr[1],
            username=pr[2],
            stack_bb=float(pr[3]) if pr[3] is not None else 0.0,
            card1=pr[4],
            card2=pr[5],
            won_bb=float(pr[6]),
            is_hero=(pr[7] == hero_id),
        ))

    # Board cards
    board_rows = db.execute(
        "SELECT street, card FROM board_cards WHERE hand_id = ? ORDER BY card_order",
        [hand_id],
    ).fetchall()
    board = BoardCards()
    for street, card in board_rows:
        if street == "flop":
            board.flop.append(card)
        elif street == "turn":
            board.turn.append(card)
        elif street == "river":
            board.river.append(card)

    # Parse actions from raw text for the detail view
    ss = parse_actions_from_raw(raw_text, hero_username, bb_amount)
    actions: list[HandAction] = []
    for street_name in ["preflop", "flop", "turn", "river"]:
        for ai in ss[street_name]["actions"]:
            abbr_to_action = {"R": "raise", "B": "bet", "C": "call", "X": "check", "F": "fold"}
            act_name = abbr_to_action.get(ai.a, ai.a)
            amt_bb = float(ai.v) if ai.v is not None else None
            actions.append(HandAction(
                street=street_name,
                player="Hero" if ai.h else "",
                position="",
                action=act_name,
                amount_bb=amt_bb,
                is_all_in=False,
                is_hero=ai.h,
            ))

    # Tags
    tag_rows = db.execute(
        "SELECT tag FROM hand_tags WHERE hand_id = ? ORDER BY created_at",
        [hand_id],
    ).fetchall()
    tag_list = [t[0] for t in tag_rows]

    # Note
    note_row = db.execute(
        "SELECT note FROM hand_notes WHERE hand_id = ?",
        [hand_id],
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
        actions=actions,
        tags=tag_list,
        note=note,
    )


# ── Tags ─────────────────────────────────────────────────────────────

class TagBody(BaseModel):
    tag: str


@router.post("/hands/{hand_id}/tags")
def add_tag(hand_id: str, body: TagBody):
    with db_lock():
        db = get_db()
        if not db.execute("SELECT 1 FROM hands WHERE id = ?", [hand_id]).fetchone():
            raise HTTPException(status_code=404, detail="Hand not found")
        db.execute(
            "INSERT OR IGNORE INTO hand_tags (hand_id, tag) VALUES (?, ?)",
            [hand_id, body.tag.strip()],
        )
        return {"status": "ok"}


@router.delete("/hands/{hand_id}/tags/{tag}")
def remove_tag(hand_id: str, tag: str):
    with db_lock():
        db = get_db()
        db.execute(
            "DELETE FROM hand_tags WHERE hand_id = ? AND tag = ?",
            [hand_id, tag],
        )
        return {"status": "ok"}


@router.get("/tags", response_model=list[TagCount])
def list_tags():
    db = get_read_cursor()
    rows = db.execute(
        "SELECT tag, COUNT(*) as cnt FROM hand_tags GROUP BY tag ORDER BY cnt DESC"
    ).fetchall()
    return [TagCount(tag=r[0], count=r[1]) for r in rows]


# ── Notes ────────────────────────────────────────────────────────────

class NoteBody(BaseModel):
    note: str


@router.put("/hands/{hand_id}/note")
def update_note(hand_id: str, body: NoteBody):
    with db_lock():
        db = get_db()
        if not db.execute("SELECT 1 FROM hands WHERE id = ?", [hand_id]).fetchone():
            raise HTTPException(status_code=404, detail="Hand not found")
        existing = db.execute(
            "SELECT 1 FROM hand_notes WHERE hand_id = ?", [hand_id]
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE hand_notes SET note = ?, updated_at = CURRENT_TIMESTAMP WHERE hand_id = ?",
                [body.note, hand_id],
            )
        else:
            db.execute(
                "INSERT INTO hand_notes (hand_id, note) VALUES (?, ?)",
                [hand_id, body.note],
            )
        return {"status": "ok"}


@router.delete("/hands/{hand_id}/note")
def delete_note(hand_id: str):
    with db_lock():
        db = get_db()
        db.execute("DELETE FROM hand_notes WHERE hand_id = ?", [hand_id])
        return {"status": "ok"}
