from fastapi import APIRouter, Query
from app.db import get_db, db_lock
from collections import defaultdict
from app.models import (
    CashDropResponse, CashDropSummary, CashDropTypeBreakdown,
    CashDropRangeCategory, CashDropFieldStats, ComboStats,
)
from app.api.stats import _normalize_combo

router = APIRouter()


def _pct(num: int, den: int) -> float | None:
    return round(num / den * 100, 1) if den > 0 else None


def _build_filters(stakes, date_from, date_to):
    """Build hand-level filter clauses and params."""
    clauses = ""
    params: list = []
    if stakes:
        clauses += " AND h.stakes = ?"
        params.append(stakes)
    if date_from:
        clauses += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        clauses += " AND h.played_at <= ?"
        params.append(date_to)
    return clauses, params


@router.get("/reports/cash-drop", response_model=CashDropResponse)
def get_cash_drop_stats(
    stakes: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    with db_lock():
        db = get_db()
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'hero_username'"
        ).fetchone()
        hero_username = row[0] if row else "Hero"

        player = db.execute(
            "SELECT id FROM players WHERE username = ? AND site_id = 1",
            [hero_username],
        ).fetchone()
        empty = CashDropResponse(
            summary=CashDropSummary(
                total_hands=0, cash_drop_hands=0,
                eligible_hands=0, pots_won=0,
                total_paid_bb=0, total_paid_usd=0,
                total_received_bb=0, total_received_usd=0,
                net_bb=0, net_usd=0, frequency=0, avg_drop_bb=0,
                hero_vpip_pct=None, hero_pfr_pct=None,
                hero_three_bet_pct=None, hero_limp_pct=None,
                hero_allin_raise_pct=None, hero_allin_call_pct=None,
                hero_wtsd_pct=None, hero_wsd_pct=None,
                hero_won_bb=None, hero_bb100=None,
            ),
            field=None, by_type=[], hero_ranges=[], hero_ranges_total=0,
            ranges=[],
        )
        if not player:
            return empty

        player_id = player[0]
        hand_filters, hand_params = _build_filters(stakes, date_from, date_to)

        # ── 1. Financial summary ──────────────────────────────────────
        # Paid: hero pays 0.5BB into cash drop fund each time they win
        # an eligible pot (pot with jackpot fee).
        # Received: hero's 1/table_size EV share of each cash drop.
        fin_row = db.execute(f"""
            SELECT
                COUNT(*) as total_hands,
                SUM(CASE WHEN h.cash_drop_received > 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.jackpot > 0 THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.jackpot > 0 AND hp.won > 0 THEN 1 ELSE 0 END),
                -- Received EV: hero's 1/table_size share
                SUM(CASE WHEN h.cash_drop_received > 0
                    THEN h.cash_drop_received / h.bb_amount / h.table_size ELSE 0 END),
                SUM(CASE WHEN h.cash_drop_received > 0
                    THEN h.cash_drop_received / h.table_size ELSE 0 END)
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE hp.player_id = ? {hand_filters}
        """, [player_id] + hand_params).fetchone()

        total_hands = int(fin_row[0] or 0)
        cash_drop_hands = int(fin_row[1] or 0)
        eligible_hands = int(fin_row[2] or 0)
        pots_won = int(fin_row[3] or 0)
        received_bb = float(fin_row[4] or 0)
        received_usd = float(fin_row[5] or 0)

        # Paid to fund: 0.5BB per eligible pot won
        paid_bb = pots_won * 0.5
        if pots_won > 0:
            avg_bb_row = db.execute(f"""
                SELECT AVG(h.bb_amount)
                FROM hand_players hp
                JOIN hands h ON hp.hand_id = h.id
                WHERE hp.jackpot > 0 AND hp.won > 0
                  AND hp.player_id = ? {hand_filters}
            """, [player_id] + hand_params).fetchone()
            paid_usd = paid_bb * float(avg_bb_row[0] or 0)
        else:
            paid_usd = 0.0

        net_bb = received_bb - paid_bb
        net_usd = received_usd - paid_usd
        frequency = total_hands / cash_drop_hands if cash_drop_hands > 0 else 0
        avg_drop_bb = received_bb / cash_drop_hands * 6 if cash_drop_hands > 0 else 0

        # ── 2. Hero stats in cash drop pots ───────────────────────────
        hero_cd_row = db.execute(f"""
            SELECT
                COUNT(*),
                SUM(hp.won_bb),
                SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.pfr THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.three_bet THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.three_bet_opp THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.limp THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.preflop_allin_raise THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.preflop_allin_call THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.saw_flop THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.went_to_showdown THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp.won_at_showdown THEN 1 ELSE 0 END)
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE hp.player_id = ?
              AND h.cash_drop_received > 0
              {hand_filters}
        """, [player_id] + hand_params).fetchone()

        cd_hands = int(hero_cd_row[0] or 0)
        cd_won_bb = float(hero_cd_row[1] or 0)
        cd_vpip = int(hero_cd_row[2] or 0)
        cd_pfr = int(hero_cd_row[3] or 0)
        cd_3bet = int(hero_cd_row[4] or 0)
        cd_3bet_opp = int(hero_cd_row[5] or 0)
        cd_limp = int(hero_cd_row[6] or 0)
        cd_allin_raise = int(hero_cd_row[7] or 0)
        cd_allin_call = int(hero_cd_row[8] or 0)
        cd_saw_flop = int(hero_cd_row[9] or 0)
        cd_wtsd = int(hero_cd_row[10] or 0)
        cd_wsd = int(hero_cd_row[11] or 0)

        summary = CashDropSummary(
            total_hands=total_hands,
            cash_drop_hands=cash_drop_hands,
            eligible_hands=eligible_hands,
            pots_won=pots_won,
            total_paid_bb=round(paid_bb, 1),
            total_paid_usd=round(paid_usd, 2),
            total_received_bb=round(received_bb, 1),
            total_received_usd=round(received_usd, 2),
            net_bb=round(net_bb, 1),
            net_usd=round(net_usd, 2),
            frequency=round(frequency, 0),
            avg_drop_bb=round(avg_drop_bb, 1),
            hero_vpip_pct=_pct(cd_vpip, cd_hands),
            hero_pfr_pct=_pct(cd_pfr, cd_hands),
            hero_three_bet_pct=_pct(cd_3bet, cd_3bet_opp),
            hero_limp_pct=_pct(cd_limp, cd_hands),
            hero_allin_raise_pct=_pct(cd_allin_raise, cd_hands),
            hero_allin_call_pct=_pct(cd_allin_call, cd_hands),
            hero_wtsd_pct=_pct(cd_wtsd, cd_saw_flop),
            hero_wsd_pct=_pct(cd_wsd, cd_wtsd),
            hero_won_bb=round(cd_won_bb, 1) if cd_hands else None,
            hero_bb100=round(cd_won_bb / cd_hands * 100, 1) if cd_hands else None,
        )

        # ── 3. Type breakdown ─────────────────────────────────────────
        type_rows = db.execute(f"""
            SELECT
                ROUND(h.cash_drop_received / h.bb_amount) as drop_bb,
                COUNT(*) as cnt,
                SUM(h.cash_drop_received) as total_usd
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE hp.player_id = ?
              AND h.cash_drop_received > 0
              {hand_filters}
            GROUP BY ROUND(h.cash_drop_received / h.bb_amount)
            ORDER BY drop_bb
        """, [player_id] + hand_params).fetchall()

        by_type = [
            CashDropTypeBreakdown(
                drop_bb=float(r[0]),
                count=int(r[1]),
                total_usd=round(float(r[2]), 2),
            )
            for r in type_rows
        ]

        # ── 4. Field stats in cash drop pots (exclude hero) ───────────
        field_row = db.execute(f"""
            SELECT
                COUNT(*) as total_entries,
                COUNT(DISTINCT hp2.hand_id) as distinct_hands,
                SUM(CASE WHEN hp2.vpip THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.pfr THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.three_bet THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.three_bet_opp THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.limp THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.preflop_allin_raise THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.preflop_allin_call THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.saw_flop THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.went_to_showdown THEN 1 ELSE 0 END),
                SUM(CASE WHEN hp2.won_at_showdown THEN 1 ELSE 0 END),
                AVG(hp2.won_bb)
            FROM hand_players hp2
            JOIN hands h ON hp2.hand_id = h.id
            WHERE hp2.player_id != ?
              AND h.cash_drop_received > 0
              {hand_filters}
        """, [player_id] + hand_params).fetchone()

        field_total = int(field_row[0] or 0)
        field_distinct = int(field_row[1] or 0)
        if field_total > 0:
            f_vpip = int(field_row[2] or 0)
            f_pfr = int(field_row[3] or 0)
            f_3bet = int(field_row[4] or 0)
            f_3bet_opp = int(field_row[5] or 0)
            f_limp = int(field_row[6] or 0)
            f_allin_raise = int(field_row[7] or 0)
            f_allin_call = int(field_row[8] or 0)
            f_saw_flop = int(field_row[9] or 0)
            f_wtsd = int(field_row[10] or 0)
            f_wsd = int(field_row[11] or 0)
            f_avg_won = float(field_row[12] or 0)

            field = CashDropFieldStats(
                total_players=field_total,
                avg_players_per_pot=round(field_total / field_distinct, 1) if field_distinct else None,
                vpip_pct=_pct(f_vpip, field_total),
                pfr_pct=_pct(f_pfr, field_total),
                three_bet_pct=_pct(f_3bet, f_3bet_opp),
                limp_pct=_pct(f_limp, field_total),
                allin_raise_pct=_pct(f_allin_raise, field_total),
                allin_call_pct=_pct(f_allin_call, field_total),
                wtsd_pct=_pct(f_wtsd, f_saw_flop),
                wsd_pct=_pct(f_wsd, f_wtsd),
                avg_won_bb=round(f_avg_won, 2),
            )
        else:
            field = None

        # ── 5. Field ranges by action type in cash drop pots ──────────
        range_rows = db.execute(f"""
            SELECT hp2.card1, hp2.card2,
                   hp2.limp, hp2.pfr, hp2.three_bet,
                   hp2.call_open_raise,
                   hp2.preflop_allin_raise, hp2.preflop_allin_call
            FROM hands h
            JOIN hand_players hp2 ON hp2.hand_id = h.id
            WHERE h.cash_drop_received > 0
              AND hp2.player_id != ?
              AND hp2.card1 IS NOT NULL AND hp2.card2 IS NOT NULL
              AND hp2.vpip = TRUE
              {hand_filters}
        """, [player_id] + hand_params).fetchall()

        category_combos: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for (card1, card2, limp, pfr, three_bet,
             call_open, allin_raise, allin_call) in range_rows:
            combo = _normalize_combo(card1, card2)

            if allin_raise:
                category_combos["All-in"][combo] += 1
            elif allin_call:
                category_combos["All-in Call"][combo] += 1
            elif three_bet:
                category_combos["3-Bet"][combo] += 1
            elif pfr and not three_bet:
                category_combos["Raise"][combo] += 1
            elif call_open:
                category_combos["Call"][combo] += 1
            elif limp:
                category_combos["Limp"][combo] += 1

        category_order = ["Limp", "Raise", "Call", "3-Bet", "All-in", "All-in Call"]
        ranges = []
        for cat_label in category_order:
            combos_map = category_combos.get(cat_label)
            if not combos_map:
                continue
            total = sum(combos_map.values())
            combo_list = [
                ComboStats(
                    combo=combo, hands=count,
                    bb_per_100=0, ev_bb_per_100=0,
                )
                for combo, count in combos_map.items()
            ]
            ranges.append(CashDropRangeCategory(
                label=cat_label, combos=combo_list, total_hands=total,
            ))

    return CashDropResponse(
        summary=summary,
        field=field,
        by_type=by_type,
        ranges=ranges,
    )
