"""GET /api/general: every cell of the H2N-style General screen.

Reads only the H2N columns of `hand_players` (app/h2n/CONTRACT.md): one scan
over the player's filtered hands, grouped by `h2n_pos`, sums the opportunity
and case bit of every matcher row the screen needs. Cells then add up the
position groups they cover (app/general_cells.py) and expression stats are
evaluated here with Hand2Note's rules (docs/specs/H2N-COMPATIBLE-STATS.md
sections 3 and 4). Hands and bb/100 follow its section 7.7. Hands H2N
would refuse to import (`hand_players.h2n_valid` FALSE) are left out.

Vs-user counters (H2N-COMPATIBLE-STATS.md section 3.5) only exist for opponents: when
`player_id` is another player than the workspace hero, the hands he shares with
the hero are replayed and each action cell also gets the counters restricted
to hands whose matched action was against the hero.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from app.date_filters import DATE_TO_SQL
from app.db import get_hero_player_id, get_read_cursor
from app.general_filters import resolve_filters
from app.general_cells import (
    GENERAL_CELLS,
    ActionCell,
    Counts,
    ExprCell,
    StatRef,
    SummaryCell,
    action_value,
    all_refs,
    evaluate_expr,
)
from app.h2n.rows import ROWS, sql_case, sql_opp
from app.models_general import GeneralCell, GeneralResponse, GeneralVsUser

router = APIRouter()
log = logging.getLogger(__name__)

# Rows whose case hands also need showdown / winner counts (WTSD, W$SD, WWSF).
_RESULT_ROWS: tuple[str, ...] = tuple(sorted({
    ref.row
    for c in GENERAL_CELLS.values() if isinstance(c, ExprCell) and c.expr in ("wtsd", "wsd", "wwsf")
    for ref in c.refs.values()
}))

# Every row the screen reads, in a stable order.
_ROW_KEYS: tuple[str, ...] = tuple(sorted({ref.row for ref in all_refs()},
                                          key=lambda k: (ROWS[k].mask, ROWS[k].bit)))

# Action rows (not hits-only) that get vs-user counters for opponents.
_VS_USER_ROWS: tuple[str, ...] = tuple(sorted(
    {c.ref.row for c in GENERAL_CELLS.values() if isinstance(c, ActionCell)},
    key=lambda k: (ROWS[k].mask, ROWS[k].bit),
))

_MASK_COLUMNS = ("h2n_pre_opp", "h2n_pre_case", "h2n_post_opp", "h2n_post_case")


def _filters(stakes, game_mode, date_from, date_to) -> tuple[str, list]:
    sql = ""
    params: list = []
    if stakes:
        sql += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        sql += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        sql += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND " + DATE_TO_SQL
        params.append(date_to)
    return sql, params


def _aggregate_query(where: str) -> str:
    masks = ", ".join(f"COALESCE(hp.{c}, 0) AS {c}" for c in _MASK_COLUMNS)
    sums = []
    for key in _ROW_KEYS:
        sums.append(f"SUM({sql_opp(key, 'b')})")
        sums.append(f"SUM({sql_case(key, 'b')})")
    for key in _RESULT_ROWS:
        case = sql_case(key, "b")
        sums.append(f"SUM({case} * b.sd)")
        sums.append(f"SUM({case} * b.win)")
        sums.append(f"SUM({case} * b.sd * b.win)")
    return f"""
        WITH b AS (
            SELECT hp.h2n_pos, hp.won_bb, {masks},
                   COALESCE(hp.went_to_showdown, FALSE)::INTEGER AS sd,
                   COALESCE(hp.is_winner, FALSE)::INTEGER AS win
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE {where}
        )
        SELECT b.h2n_pos, COUNT(*), SUM(b.won_bb), {", ".join(sums)}
        FROM b
        GROUP BY b.h2n_pos
    """


def _group_counts(rows) -> tuple[int, float, dict[str | None, dict[str, Counts]]]:
    """Parse the grouped query: hands, sum of won_bb, per position per row."""
    hands = 0
    won_bb = 0.0
    groups: dict[str | None, dict[str, Counts]] = {}
    for r in rows:
        pos = r[0]
        hands += int(r[1] or 0)
        won_bb += float(r[2] or 0)
        per_row: dict[str, Counts] = {}
        i = 3
        for key in _ROW_KEYS:
            per_row[key] = Counts(cases=int(r[i + 1] or 0), opps=int(r[i] or 0))
            i += 2
        for key in _RESULT_ROWS:
            c = per_row[key]
            c.wtsd = int(r[i] or 0)
            c.won = int(r[i + 1] or 0)
            c.won_sd = int(r[i + 2] or 0)
            i += 3
        groups[pos] = per_row
    return hands, won_bb, groups


def _counts_by_ref(groups: dict[str | None, dict[str, Counts]]) -> dict[StatRef, Counts]:
    out: dict[StatRef, Counts] = {}
    for ref in all_refs():
        total = Counts()
        for pos, per_row in groups.items():
            if ref.includes(pos):
                total.add(per_row[ref.row])
        out[ref] = total
    return out


def wire(value: float) -> float | str | None:
    """Float for JSON: NaN -> None, +-inf -> "inf" / "-inf"."""
    if math.isnan(value):
        return None
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return value


# ── vs-user counters (opponents only) ────────────────────────────────────


def _is_vs_user(parsed_active: set[str], seq, hit: tuple[int, int], user: int, actor: int) -> bool:
    """H2N-COMPATIBLE-STATS.md 3.5: the hit action is not the user's, the user is
    still in the hand, and either he is the only opponent left or he has
    VPIP'd on this street before the action."""
    from app.h2n.sequence import FOLD, VPIP

    street, idx = hit
    if actor == user:
        return False
    acts = seq.streets[street]
    folded: set[int] = set()
    for p in range(len(seq.names)):
        fs = seq.fold_street[p]
        if 0 <= fs < street:
            folded.add(p)
    for a in acts[:idx]:
        if a.raw == FOLD or a.eff == FOLD:
            folded.add(a.actor)
    if user in folded:
        return False
    left = [p for p, nm in enumerate(seq.names)
            if p != actor and p not in folded and nm in parsed_active]
    if user not in left:
        return False
    if len(left) == 1:
        return True
    return any(a.actor == user and a.flags & VPIP for a in acts[:idx])


def _vs_user_counts(db, where: str, params: list, player_id: int,
                    hero_id: int) -> dict[tuple[str, str | None], Counts]:
    """(row, h2n_pos of the player) -> vs-user Counts over shared hands."""
    from app.h2n.definitions import COMPILED
    from app.h2n.matcher import evaluate, gate
    from app.h2n.replay import parser_for, replay_parsed

    rows = db.execute(f"""
        SELECT h.raw_text, h.site_id, p.username, u.username
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        JOIN players p ON p.id = hp.player_id
        JOIN hand_players hu ON hu.hand_id = h.id AND hu.workspace_id = h.workspace_id
                             AND hu.player_id = ?
        JOIN players u ON u.id = hu.player_id
        WHERE {where}
    """, [hero_id, *params]).fetchall()
    out: dict[tuple[str, str | None], Counts] = defaultdict(Counts)
    for raw_text, site_id, name, user_name in rows:
        if not raw_text:
            continue
        try:
            parsed = parser_for(int(site_id)).parse_hand_history(raw_text)
            seq = replay_parsed(parsed)
        except Exception:
            log.warning("vs-user replay failed", exc_info=True)
            continue
        p = seq.index.get(name)
        u = seq.index.get(user_name)
        if p is None or u is None:
            continue
        active = {a["username"] for street in parsed.actions_by_street.values() for a in street}
        active.update(parsed.hero_cards)
        pos = seq.pos[p]
        cache: dict = {}
        for key in _VS_USER_ROWS:
            d = COMPILED[key]
            if not gate(d, seq, p):
                continue
            res = evaluate(d, seq, p, cache)
            if not res.opp or res.hit is None:
                continue
            if not _is_vs_user(active, seq, res.hit, u, p):
                continue
            c = out[(key, pos)]
            c.opps += 1
            if res.case:
                c.cases += 1
    return out


def _vs_user_cell(ref: StatRef, vs: dict[tuple[str, str | None], Counts]) -> GeneralVsUser:
    total = Counts()
    for (row, pos), c in vs.items():
        if row == ref.row and ref.includes(pos):
            total.add(c)
    return GeneralVsUser(value=wire(action_value(total.cases, total.opps)), sample=total.opps,
                         cases=total.cases, opps=total.opps)


# ── endpoint ─────────────────────────────────────────────────────────────


def compute_general(db, player_id: int, workspace_id: int = 1, *, stakes: str | None = None,
                    game_mode: str | None = None, date_from: str | None = None,
                    date_to: str | None = None, hero_id: int | None = None,
                    filter_sql: tuple[str, list] | None = None) -> GeneralResponse:
    """Every General cell for `player_id` over the filtered hands (`filter_sql` = ready
    AND-ed SQL + params, e.g. from a Reports chain, replaces the stakes/mode/date params)."""
    fsql, fparams = filter_sql or _filters(stakes, game_mode, date_from, date_to)
    # Hands H2N refuses to import (app.h2n.hand_rejection) are in none of its stats.
    where = "hp.player_id = ? AND h.workspace_id = ? AND COALESCE(hp.h2n_valid, TRUE)" + fsql
    params = [player_id, workspace_id, *fparams]
    hands, won_bb, groups = _group_counts(db.execute(_aggregate_query(where), params).fetchall())
    counts = _counts_by_ref(groups)

    is_hero = hero_id is None or hero_id == player_id
    vs: dict | None = None
    if not is_hero and hands:
        vs = _vs_user_counts(db, where, params, player_id, hero_id)

    # Win rate = big blinds won / hands * 100
    bb100 = won_bb / hands * 100.0 if hands else None

    cells: dict[str, GeneralCell] = {}
    for cid, cell in GENERAL_CELLS.items():
        if isinstance(cell, SummaryCell):
            if cell.what == "hands":
                cells[cid] = GeneralCell(kind="expression", value=hands, sample=None)
            else:
                cells[cid] = GeneralCell(kind="expression", value=bb100, sample=hands)
        elif isinstance(cell, ActionCell):
            c = counts[cell.ref]
            cells[cid] = GeneralCell(
                kind="action", row=cell.ref.row, same_as=cell.same_as,
                cases=c.cases, opps=c.opps, sample=c.opps,
                value=wire(action_value(c.cases, c.opps)),
                vs_user=_vs_user_cell(cell.ref, vs) if vs is not None else None,
            )
        else:
            value, sample, inputs = evaluate_expr(cell, counts)
            cells[cid] = GeneralCell(kind="expression", value=wire(value),
                                     sample=sample, inputs=inputs)

    player = site = None
    row = db.execute(
        "SELECT p.username, s.name FROM players p LEFT JOIN sites s ON s.id = p.site_id "
        "WHERE p.id = ?", [player_id],
    ).fetchone()
    if row:
        player, site = row
    return GeneralResponse(hands=hands, bb100=bb100, player=player, player_id=player_id,
                           site=site, is_hero=is_hero, cells=cells)


@router.get("/general", response_model=GeneralResponse)
def get_general(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    chain: str | None = Query(None, description="JSON plain Reports steps, instead of the filters above"),
    workspace_id: int = Query(1),
    player_id: int | None = Query(None, description="Defaults to the workspace hero"),
):
    fsql, fparams, _steps = resolve_filters(chain, stakes, game_mode, date_from, date_to)
    db = get_read_cursor()
    hero_id = get_hero_player_id(db, workspace_id)
    target = player_id if player_id is not None else hero_id
    if target is None:
        return GeneralResponse(
            cells={cid: _empty_cell(c) for cid, c in GENERAL_CELLS.items()},
        )
    if player_id is not None and not db.execute(
            "SELECT 1 FROM players WHERE id = ?", [player_id]).fetchone():
        raise HTTPException(status_code=404, detail="Player not found")
    return compute_general(db, target, workspace_id, hero_id=hero_id, filter_sql=(fsql, fparams))


def _empty_cell(cell) -> GeneralCell:
    if isinstance(cell, ActionCell):
        return GeneralCell(kind="action", row=cell.ref.row, same_as=cell.same_as,
                           cases=0, opps=0, sample=0)
    if isinstance(cell, SummaryCell) and cell.what == "hands":
        return GeneralCell(kind="expression", value=0, sample=None)
    return GeneralCell(kind="expression", value=None, sample=0)


__all__ = ["router", "compute_general"]
