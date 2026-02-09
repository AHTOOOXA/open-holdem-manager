from fastapi import APIRouter, Query
from app.db import get_db, db_lock
from collections import defaultdict
from app.models import (
    CashDropResponse, CashDropSummary, CashDropTypeBreakdown,
    CashDropRangeCategory, ComboStats,
)
from app.api.stats import _normalize_combo

router = APIRouter()


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
        empty_summary = CashDropSummary(
            total_hands=0, eligible_hands=0, pots_won=0, cash_drop_hands=0,
            total_paid_bb=0, total_paid_usd=0,
            total_received_bb=0, total_received_usd=0,
            net_bb=0, net_usd=0, frequency=0, avg_drop_bb=0,
            win_pct=None, win_rate_bb100=None,
            vpip_pct=None, pfr_pct=None, three_bet_pct=None,
            wtsd_pct=None, wsd_pct=None,
        )
        if not player:
            return CashDropResponse(
                summary=empty_summary, by_type=[], ranges=[],
            )

        player_id = player[0]

        # Build WHERE clause for filters
        filters = " AND hp.player_id = ?"
        params: list = [player_id]
        if stakes:
            filters += " AND h.stakes = ?"
            params.append(stakes)
        if date_from:
            filters += " AND h.played_at >= ?"
            params.append(date_from)
        if date_to:
            filters += " AND h.played_at <= ?"
            params.append(date_to)

        # Hero stats in eligible pots (pots with jackpot fee = pot >= 30BB)
        # jackpot_hands CTE finds all hands that had any jackpot
        summary_row = db.execute(f"""
            WITH jackpot_hands AS (
                SELECT hand_id
                FROM hand_players
                GROUP BY hand_id
                HAVING SUM(jackpot) > 0
            )
            SELECT
                COUNT(*) as total_hands,
                SUM(CASE WHEN jh.hand_id IS NOT NULL THEN 1 ELSE 0 END) as eligible_hands,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.won > 0 THEN 1 ELSE 0 END) as pots_won,
                SUM(CASE WHEN h.cash_drop_received > 0 THEN 1 ELSE 0 END) as cash_drop_hands,
                -- Received: hero's 1/table_size share of cash drops at table
                SUM(CASE WHEN h.cash_drop_received > 0
                    THEN h.cash_drop_received / h.bb_amount / h.table_size ELSE 0 END) as received_bb,
                SUM(CASE WHEN h.cash_drop_received > 0
                    THEN h.cash_drop_received / h.table_size ELSE 0 END) as received_usd,
                -- Stats in eligible pots
                SUM(CASE WHEN jh.hand_id IS NOT NULL THEN hp.won_bb ELSE 0 END) as elig_won_bb,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.vpip THEN 1 ELSE 0 END) as elig_vpip,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.pfr THEN 1 ELSE 0 END) as elig_pfr,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.three_bet THEN 1 ELSE 0 END) as elig_3bet,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.three_bet_opp THEN 1 ELSE 0 END) as elig_3bet_opp,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.saw_flop THEN 1 ELSE 0 END) as elig_saw_flop,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.went_to_showdown THEN 1 ELSE 0 END) as elig_wtsd,
                SUM(CASE WHEN jh.hand_id IS NOT NULL AND hp.won_at_showdown THEN 1 ELSE 0 END) as elig_wsd
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            LEFT JOIN jackpot_hands jh ON jh.hand_id = hp.hand_id
            WHERE 1=1 {filters}
        """, params).fetchone()

        total_hands = int(summary_row[0] or 0)
        eligible_hands = int(summary_row[1] or 0)
        pots_won = int(summary_row[2] or 0)
        cash_drop_hands = int(summary_row[3] or 0)
        received_bb = float(summary_row[4] or 0)
        received_usd = float(summary_row[5] or 0)
        elig_won_bb = float(summary_row[6] or 0)
        elig_vpip = int(summary_row[7] or 0)
        elig_pfr = int(summary_row[8] or 0)
        elig_3bet = int(summary_row[9] or 0)
        elig_3bet_opp = int(summary_row[10] or 0)
        elig_saw_flop = int(summary_row[11] or 0)
        elig_wtsd = int(summary_row[12] or 0)
        elig_wsd = int(summary_row[13] or 0)

        # Paid: hero pays 0.5BB each time they win an eligible pot
        paid_bb = pots_won * 0.5
        # For USD, get average bb_amount of pots hero won
        if pots_won > 0:
            avg_bb_row = db.execute(f"""
                SELECT AVG(h.bb_amount)
                FROM hand_players hp
                JOIN hands h ON hp.hand_id = h.id
                WHERE hp.jackpot > 0 AND hp.won > 0 {filters}
            """, params).fetchone()
            paid_usd = paid_bb * float(avg_bb_row[0] or 0)
        else:
            paid_usd = 0.0

        net_bb = received_bb - paid_bb
        net_usd = received_usd - paid_usd
        frequency = total_hands / cash_drop_hands if cash_drop_hands > 0 else 0
        avg_drop_bb = received_bb / cash_drop_hands * 6 if cash_drop_hands > 0 else 0

        def _pct(num: int, den: int) -> float | None:
            return round(num / den * 100, 1) if den > 0 else None

        summary = CashDropSummary(
            total_hands=total_hands,
            eligible_hands=eligible_hands,
            pots_won=pots_won,
            cash_drop_hands=cash_drop_hands,
            total_paid_bb=round(paid_bb, 1),
            total_paid_usd=round(paid_usd, 2),
            total_received_bb=round(received_bb, 1),
            total_received_usd=round(received_usd, 2),
            net_bb=round(net_bb, 1),
            net_usd=round(net_usd, 2),
            frequency=round(frequency, 0),
            avg_drop_bb=round(avg_drop_bb, 1),
            win_pct=_pct(pots_won, eligible_hands),
            win_rate_bb100=round(elig_won_bb / eligible_hands * 100, 1) if eligible_hands else None,
            vpip_pct=_pct(elig_vpip, eligible_hands),
            pfr_pct=_pct(elig_pfr, eligible_hands),
            three_bet_pct=_pct(elig_3bet, elig_3bet_opp),
            wtsd_pct=_pct(elig_wtsd, elig_saw_flop),
            wsd_pct=_pct(elig_wsd, elig_wtsd),
        )

        # Type breakdown (10BB vs 20BB drops)
        type_rows = db.execute(f"""
            SELECT
                ROUND(h.cash_drop_received / h.bb_amount) as drop_bb,
                COUNT(*) as cnt,
                SUM(h.cash_drop_received) as total_usd
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE h.cash_drop_received > 0 {filters}
            GROUP BY ROUND(h.cash_drop_received / h.bb_amount)
            ORDER BY drop_bb
        """, params).fetchall()

        by_type = [
            CashDropTypeBreakdown(
                drop_bb=float(r[0]),
                count=int(r[1]),
                total_usd=round(float(r[2]), 2),
            )
            for r in type_rows
        ]

        # Range heatmaps by preflop action type
        range_rows = db.execute(f"""
            SELECT hp2.card1, hp2.card2,
                   hp2.limp, hp2.pfr, hp2.three_bet,
                   hp2.call_open_raise,
                   hp2.preflop_allin_raise, hp2.preflop_allin_call
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            JOIN hand_players hp2 ON hp2.hand_id = h.id
            WHERE h.cash_drop_received > 0
              AND hp2.card1 IS NOT NULL AND hp2.card2 IS NOT NULL
              AND hp2.vpip = TRUE
              {filters}
        """, params).fetchall()

        # Categorize each player-hand into action type
        # All-in flags take priority (open jam, 3bet shove, 4bet shove, call shove)
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

        # Build response categories in display order
        category_order = ["Limp", "Raise", "Call", "3-Bet", "All-in", "All-in Call"]
        ranges = []
        for cat_label in category_order:
            combos_map = category_combos.get(cat_label)
            if not combos_map:
                continue
            total = sum(combos_map.values())
            combo_list = [
                ComboStats(
                    combo=combo,
                    hands=count,
                    bb_per_100=0, ev_bb_per_100=0,
                )
                for combo, count in combos_map.items()
            ]
            ranges.append(CashDropRangeCategory(
                label=cat_label,
                combos=combo_list,
                total_hands=total,
            ))

    return CashDropResponse(
        summary=summary,
        by_type=by_type,
        ranges=ranges,
    )
