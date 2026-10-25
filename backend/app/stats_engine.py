"""Stats page numbers (HeroStats), Hand2Note style.

Every stat with a twin on H2N's General screen is computed from the H2N
matcher bits (hand_players.h2n_pre_* / h2n_post_*, app/h2n/CONTRACT.md) with
the same row, hero-position set and formula as the General cell
(app/general_cells.py, docs/specs/H2N-COMPATIBLE-STATS.md section 4):

- positions are H2N's column groups (`h2n_pos`: the heads-up button is SB);
- an action stat is cases / opportunities of its row;
- the steal table only has BTN and SB (CO is not a steal seat in H2N);
- 3-Bet: the Total is H2N's built-in 3-Bet (squeezes in), the position
  columns are "opener re-raised directly" (squeezes out), as on the General
  screen, so they don't add up to the Total;
- WTSD / WWSF use hands with a flop action as the base, W$SD the showdowns
  of hands with any preflop action, "won" = H2N's is-winner;
- Aggression / AFq count hands, not actions; 4-Bet Range and vs. Missed
  C-Bet are H2N's expressions.

Hands H2N would refuse to import (`h2n_valid` FALSE) are left out of every
number, hands and win rate included. Stats with no H2N twin (BB Defense, Iso
Raise, Fold to Squeeze, Missed C-Bet Turn) keep the classic OHM flags; see
NON_H2N_FIELDS. The drill-down registry (stat_registry.py) uses the same
definitions; tests/test_stat_parity.py keeps them in sync.
"""

import re
import threading
from collections import OrderedDict
from typing import Any, Callable

import duckdb
from app import data_generation
from app.concurrency import heavy_slot
from app.date_filters import DATE_TO_SQL
from app.h2n.rows import ROWS, sql_case, sql_opp
from app.models import HeroStats, PositionalStats, StatValue
from app.stat_registry import BTN_SB, POS_SQL, VALID_SQL

POSITIONS = ["EP", "MP", "CO", "BTN", "SB", "BB"]

# HeroStats fields that have no H2N General twin and stay on OHM's flags.
NON_H2N_FIELDS: tuple[str, ...] = (
    "bb_defense", "iso_raise", "fold_to_squeeze", "missed_cbet_turn",
)


def _row_sums() -> str:
    """SUM of the case and opportunity bit of every H2N row: c_<row>, o_<row>."""
    parts = []
    for key in ROWS:
        name = key.lower()
        parts.append(f"SUM({sql_case(key)}) AS c_{name}")
        parts.append(f"SUM({sql_opp(key)}) AS o_{name}")
    return ",\n    ".join(parts)


_SD = "COALESCE(hp.went_to_showdown, FALSE)::INTEGER"
_WIN = "COALESCE(hp.is_winner, FALSE)::INTEGER"

# SQL aggregation query: all counts in one pass, grouped by H2N position.
# `{where}` is filled by the callers (also api/identities.py, api/population.py);
# `{hands_join}` by agg_sql() (empty when no hands column is needed).
_AGG_SQL_T = f"""
SELECT
    {POS_SQL} AS position,
    COUNT(*) as hands,
    SUM(CAST(COALESCE(hp.won_bb, 0) AS DOUBLE)) as total_won_bb,
    SUM(CAST(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) AS DOUBLE)) as total_ev_bb,

    -- H2N matcher rows
    {_row_sums()},

    -- Showdown results over the case hands of the base rows
    SUM({sql_case('E_FLOP_ANY')} * {_SD}) as flop_any_sd,
    SUM({sql_case('E_FLOP_ANY')} * {_WIN}) as flop_any_won,
    SUM({sql_case('V03')} * {_SD}) as pre_any_sd,
    SUM({sql_case('V03')} * {_SD} * {_WIN}) as pre_any_won_sd,

    -- OHM-only stats (no H2N General twin)
    SUM(CASE WHEN hp.bb_defense_opp THEN 1 ELSE 0 END) as bb_defense_opp,
    SUM(CASE WHEN hp.bb_defense THEN 1 ELSE 0 END) as bb_defense,
    SUM(CASE WHEN hp.iso_raise_opp THEN 1 ELSE 0 END) as iso_raise_opp,
    SUM(CASE WHEN hp.iso_raise THEN 1 ELSE 0 END) as iso_raise,
    SUM(CASE WHEN hp.fold_to_squeeze IS NOT NULL THEN 1 ELSE 0 END) as fold_to_squeeze_opp,
    SUM(CASE WHEN hp.fold_to_squeeze THEN 1 ELSE 0 END) as fold_to_squeeze,
    SUM(CASE WHEN hp.cbet_turn_opp THEN 1 ELSE 0 END) as cbet_turn_opp,
    SUM(CASE WHEN hp.cbet_turn_opp AND hp.missed_cbet_turn THEN 1 ELSE 0 END) as missed_cbet_turn

FROM hand_players hp
{{hands_join}}
WHERE ({{where}}) AND {VALID_SQL}
GROUP BY 1
"""

_HANDS_JOIN = "JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id"
# Kept for callers that format the template themselves (api/identities.py): always joins.
_AGG_SQL = _AGG_SQL_T.replace("{hands_join}", _HANDS_JOIN)

_H_REF = re.compile(r"\bh\.")
_H_WS = re.compile(r"\bh\.workspace_id\b")


def agg_sql(where: str) -> str:
    """_AGG_SQL for `where`, joining `hands` only when `where` reads a hands column.

    The join only matches every hand_players row to its hand (the import invariant: no
    hand_players row without its hand), so when the only hands column used is the workspace,
    `hp.workspace_id` (equal by the join condition) gives the same rows without the join.
    """
    lean = _H_WS.sub("hp.workspace_id", where)
    if _H_REF.search(lean):
        return _AGG_SQL_T.format(hands_join=_HANDS_JOIN, where=where)
    return _AGG_SQL_T.format(hands_join="", where=lean)


# ── in-process result cache ──────────────────────────────────────────


class ResultCache:
    """Small LRU of computed results that only change when hand data changes.

    Entries are keyed on (data generation, caller key) and the whole cache is dropped on every
    `data_generation.bump()`. A result is only stored when nothing could have changed under
    it: no rebuild running, no writer holding the DB lock at the start or the end of the
    computation, the same generation before and after, and the same hand-data fingerprint
    (row counts, top id) on the same connection. The finalize step of an import bumps first and
    rewrites player classifications afterwards under the lock, hence the lock check.

    Cached values are shared: callers must treat them as read-only.
    """

    def __init__(self, name: str, capacity: int = 64):
        self.name = name
        self.capacity = capacity
        self._d: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        data_generation.on_bump(self.clear)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def __len__(self) -> int:
        return len(self._d)

    def get_or_compute(self, db, key: Any, compute: Callable[[], Any], *, heavy: bool = False):
        from app import db as app_db
        if app_db.get_rebuild_status().get("active"):
            return self._run(compute, heavy)
        conn = app_db._conn
        gen = data_generation.current()
        idle = _writer_idle()
        full = (gen, id(conn), _fingerprint(db), key)
        with self._lock:
            hit = self._d.get(full)
            if hit is not None and hit[0] is conn:
                self._d.move_to_end(full)
                self.hits += 1
                return hit[1]
        self.misses += 1
        value = self._run(compute, heavy)
        if idle and _writer_idle() and data_generation.current() == gen:
            with self._lock:
                self._d[full] = (conn, value)
                self._d.move_to_end(full)
                while len(self._d) > self.capacity:
                    self._d.popitem(last=False)
        return value

    @staticmethod
    def _run(compute, heavy: bool):
        if heavy:
            with heavy_slot():
                return compute()
        return compute()


def _writer_idle() -> bool:
    """True when no other thread holds the DB write lock right now."""
    from app.db import db_lock
    lock = db_lock()
    if lock.acquire(blocking=False):
        lock.release()
        return True
    return False


def _fingerprint(db) -> tuple:
    """Cheap hand-data fingerprint (~0.5 ms at 1.3M rows): catches inserts and deletes that
    happen between two generation bumps (e.g. between the batches of a running import)."""
    return tuple(db.execute(
        "SELECT (SELECT COUNT(*) FROM hand_players), (SELECT MAX(id) FROM hand_players), "
        "(SELECT COUNT(*) FROM hands)"
    ).fetchone())


_STATS_CACHE = ResultCache("stats")


def _pct(cases: float, opps: int) -> StatValue:
    return StatValue(value=round(cases / opps * 100, 1) if opps > 0 else None, sample=opps)


def _compute_stats_from_query(
    db: duckdb.DuckDBPyConnection,
    where: str,
    params: list,
    *,
    sql_override: str | None = None,
    heavy: bool = False,
) -> HeroStats:
    """Compute HeroStats from a pre-built WHERE clause (shared core logic).

    If sql_override is provided, it is used as the full SQL instead of
    formatting _AGG_SQL with the where clause (used for CTE queries).

    The result is memoised per (SQL, params) until the hand data changes (ResultCache); the
    returned object is shared, don't mutate it. `heavy` runs a cache miss in a heavy_slot().
    """
    sql = sql_override or agg_sql(where)
    params = list(params)
    return _STATS_CACHE.get_or_compute(
        db, (sql, tuple(params)), lambda: _stats_from_sql(db, sql, params), heavy=heavy)


def _stats_from_sql(db: duckdb.DuckDBPyConnection, sql: str, params: list) -> HeroStats:
    rows = db.execute(sql, params).fetchall()
    if not rows:
        return HeroStats()

    columns = [desc[0] for desc in db.description]

    # Per-position counters and totals
    by_pos: dict[str | None, dict] = {}
    tot: dict[str, int | float] = {}
    for row in rows:
        d = {k: (v if isinstance(v, float) else int(v or 0))
             for k, v in zip(columns, row) if k != "position"}
        by_pos[row[columns.index("position")]] = d
        for k, v in d.items():
            tot[k] = tot.get(k, 0) + (v or 0)

    total_hands = int(tot.get("hands", 0))
    if total_hands == 0:
        return HeroStats()

    stats = HeroStats()
    stats.hands = total_hands
    stats.win_rate_bb100 = round((tot["total_won_bb"] / total_hands) * 100, 2)
    stats.win_rate_ev_bb100 = round((tot["total_ev_bb"] / total_hands) * 100, 2)

    def count(name: str, positions: tuple[str, ...] | None = None, exclude: bool = False) -> int:
        """Sum of a counter over hero positions (None = every position)."""
        if positions is None:
            return int(tot.get(name, 0))
        return sum(int(d.get(name, 0)) for pos, d in by_pos.items()
                   if (pos in positions) != exclude)

    def cases(row: str, positions=None, exclude=False) -> int:
        return count(f"c_{row.lower()}", positions, exclude)

    def opps(row: str, positions=None, exclude=False) -> int:
        return count(f"o_{row.lower()}", positions, exclude)

    def sv(row: str, positions: tuple[str, ...] | None = None, exclude: bool = False) -> StatValue:
        """An H2N action stat: cases / opps of `row` for these hero positions."""
        return _pct(cases(row, positions, exclude), opps(row, positions, exclude))

    def ohm(count_key: str, opp_key: str) -> StatValue:
        return _pct(count(count_key), count(opp_key))

    def by_position(row: str) -> PositionalStats:
        """Total over every position, then one column per hero position."""
        ps = PositionalStats(total=sv(row))
        for pos in POSITIONS:
            setattr(ps, pos.lower(), sv(row, (pos,)))
        return ps

    def cells(total: StatValue, **cols: StatValue) -> PositionalStats:
        """General-screen rows whose columns use different stats."""
        return PositionalStats(total=total, **cols)

    # ── Pre-flop ──
    stats.vpip = by_position("V01")
    stats.pfr = by_position("V02")
    stats.open_raise = by_position("P01")
    stats.fold_to_3bet = by_position("P03")
    stats.call_open_raise = by_position("P06")
    # Total = built-in 3-Bet (squeezes in); positions = V:R[first raise] -> H:R
    stats.three_bet = cells(sv("P07"), **{p.lower(): sv("P08", (p,)) for p in POSITIONS})
    # IP row: EP..BTN repeat the 3-Bet cells, BB = 3-bet vs the SB, no SB cell.
    # OOP row: SB repeats the 3-Bet cell, BB = 3-bet vs BTN/CO/MP/EP.
    stats.three_bet_ip = cells(
        sv("P09"), **{p.lower(): sv("P08", (p,)) for p in ("EP", "MP", "CO", "BTN")},
        bb=sv("P11", ("BB",)),
    )
    stats.three_bet_oop = cells(sv("P10"), sb=sv("P08", ("SB",)), bb=sv("P12", ("BB",)))
    stats.four_bet = by_position("P13")
    stats.fold_to_4bet = by_position("P19")
    stats.limp = by_position("P22")

    stats.five_bet = sv("P21")
    stats.squeeze = sv("P24")
    stats.limp_fold = sv("P23", ("BB",), exclude=True)
    stats.four_bet_fold = sv("P16")
    stats.call_4bet = sv("P20")
    # cases(Open) * cases(4-Bet) / opps(Open) / opps(4-Bet) * 100, in that order
    o_c, o_o, f_c, f_o = cases("P01"), opps("P01"), cases("P13"), opps("P13")
    stats.four_bet_range = StatValue(
        value=round(float(o_c) * float(f_c) / o_o / f_o * 100.0, 1) if o_o and f_o else None,
        sample=max(o_o, f_o),
    )

    # No H2N twin: OHM flags
    stats.bb_defense = ohm("bb_defense", "bb_defense_opp")
    stats.iso_raise = ohm("iso_raise", "iso_raise_opp")
    stats.fold_to_squeeze = ohm("fold_to_squeeze", "fold_to_squeeze_opp")

    # ── Steal (BTN, SB) ──
    stats.steal = cells(sv("P02", BTN_SB), btn=sv("P02", ("BTN",)), sb=sv("P02", ("SB",)))
    # Totals: 3-bet from the blinds only. BTN / SB: any 3-bettor (Fold to 3Bet
    # BTN is the pre-flop Fold to 3Bet BTN stat; SB needs an unopened pot).
    stats.fold_to_3bet_steal = cells(
        sv("P05", BTN_SB), btn=sv("P03", ("BTN",)), sb=sv("P04", ("SB",)))
    stats.four_bet_steal = cells(
        sv("P15", BTN_SB), btn=sv("P14", ("BTN",)), sb=sv("P14", ("SB",)))
    stats.four_bet_fold_steal = cells(
        sv("P18", BTN_SB), btn=sv("P17", ("BTN",)), sb=sv("P17", ("SB",)))

    # ── vs Steal: hero SB vs a BTN steal, hero BB vs a BTN / SB steal ──
    def vs_steal(row_sb: str, row_bb: str) -> PositionalStats:
        c = cases(row_sb, ("SB",)) + cases(row_bb, ("BB",))
        o = opps(row_sb, ("SB",)) + opps(row_bb, ("BB",))
        return cells(_pct(c, o), sb=sv(row_sb, ("SB",)), bb=sv(row_bb, ("BB",)))

    stats.vs_steal_fold = vs_steal("P25F", "P26F")
    stats.vs_steal_call = vs_steal("P25C", "P26C")
    stats.vs_steal_3bet = vs_steal("P25R", "P26R")

    # ── Postflop ──
    stats.cbet_flop = by_position("C01")
    stats.cbet_turn = by_position("C02")
    stats.cbet_river = by_position("C03")
    stats.fold_to_cbet_flop = by_position("C04")
    stats.fold_to_cbet_turn = by_position("C05")
    stats.fold_to_cbet_river = by_position("C06")

    # vs CBet Flop. Raised Pot Fold is the Fold to CBet Flop stat itself.
    stats.fold_cbet_flop_raised = sv("C04")
    stats.call_cbet_flop_raised = sv("C07")
    stats.raise_cbet_flop_raised = sv("C08")
    stats.fold_cbet_flop_3bet = sv("C09")
    stats.call_cbet_flop_3bet = sv("C10")
    stats.raise_cbet_flop_3bet = sv("C11")

    stats.donk_bet_flop = sv("C12")
    stats.donk_bet_turn = sv("C13")
    stats.donk_bet_river = sv("C14")

    # Missed CBet (IP / OOP are tri-state: a middle seat is in neither)
    stats.missed_cbet_flop = sv("M01")
    stats.missed_cbet_flop_ip = sv("M02")
    stats.missed_cbet_flop_oop = sv("M03")
    stats.missed_cbet_fold_ip = sv("M04")
    stats.missed_cbet_fold_oop = sv("M05")
    stats.missed_cbet_turn = ohm("missed_cbet_turn", "cbet_turn_opp")

    # vs Missed CBet: (cases(A) + cases(B)) / (opps(A) + opps(B)) * 100,
    # A = N06, B = N05; sample = the larger of the two
    a_c, a_o, b_c, b_o = cases("N06"), opps("N06"), cases("N05"), opps("N05")
    stats.vs_missed_cbet = StatValue(
        value=round((a_c + b_c) / (a_o + b_o) * 100, 1) if a_o + b_o else None,
        sample=max(a_o, b_o),
    )
    stats.vs_missed_cbet_bet_ip = sv("N01")
    stats.vs_missed_cbet_check_fold_ip = sv("N02")
    stats.vs_missed_cbet_bet_oop_turn = sv("N03")
    stats.vs_missed_cbet_check_fold_oop = sv("N04")

    # Aggression: (cases(Bet) + cases(Raise)) / cases(Call), hands not actions;
    # sample = the largest opportunity count of the three
    for street in ("flop", "turn", "river"):
        s = street.upper()
        b, r, c = cases(f"E_{s}_B"), cases(f"E_{s}_R"), cases(f"E_{s}_C")
        setattr(stats, f"af_{street}", StatValue(
            value=round((b + r) / c, 2) if c else None,
            sample=max(opps(f"E_{s}_B"), opps(f"E_{s}_R"), opps(f"E_{s}_C")),
        ))
        # AFq: hands with a bet or raise / hands with any action on the street
        setattr(stats, f"afq_{street}", _pct(cases(f"E_{s}_BR"), cases(f"E_{s}_ANY")))

    # ── Showdown ──
    flop_hands = cases("E_FLOP_ANY")
    stats.wtsd = _pct(count("flop_any_sd"), flop_hands)
    stats.wsd = _pct(count("pre_any_won_sd"), count("pre_any_sd"))
    stats.wwsf = _pct(count("flop_any_won"), flop_hands)

    return stats


def compute_player_stats(
    db: duckdb.DuckDBPyConnection,
    player_id: int,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    last_n: int | None = None,
    workspace_id: int | None = None,
) -> HeroStats:
    """Compute full stats for any player by player_id."""
    where = "hp.player_id = ?"
    params: list = [player_id]

    if workspace_id is not None:
        where += " AND h.workspace_id = ?"
        params.append(workspace_id)

    if position:
        where += f" AND {POS_SQL} = ?"
        params.append(position)
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if game_mode is not None:
        where += " AND h.game_mode = ?"
        params.append(game_mode)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND " + DATE_TO_SQL
        params.append(date_to)

    if last_n:
        cte_where = where
        cte_params = list(params)
        # Last N hands the stats count: hands H2N would refuse are left out
        # here too, so N means N counted hands.
        cte = f"""WITH recent_hands AS (
            SELECT h.id FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE ({cte_where}) AND {VALID_SQL}
            ORDER BY h.played_at DESC, h.id DESC
            LIMIT {int(last_n)}
        )
        """
        where += " AND h.id IN (SELECT id FROM recent_hands)"
        params = cte_params + params
        full_sql = cte + _AGG_SQL.format(where=where)
        return _compute_stats_from_query(db, where, params, sql_override=full_sql)

    return _compute_stats_from_query(db, where, params)


def compute_hero_stats(
    db: duckdb.DuckDBPyConnection,
    hero_username: str,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    last_n: int | None = None,
    workspace_id: int | None = None,
) -> HeroStats:
    """Compute stats for hero by username. Thin wrapper around compute_player_stats."""
    from app.db import get_hero_player_id
    player_id = get_hero_player_id(db, workspace_id or 1)
    if not player_id:
        return HeroStats()
    return compute_player_stats(
        db, player_id,
        position=position, stakes=stakes, game_mode=game_mode,
        date_from=date_from, date_to=date_to, last_n=last_n,
        workspace_id=workspace_id,
    )


def compute_population_stats(
    db: duckdb.DuckDBPyConnection,
    workspace_id: int,
    exclude_player_id: int | None = None,
    min_hands: int = 100,
    stakes: str | None = None,
    game_mode: str | None = None,
) -> HeroStats:
    """Compute aggregated population stats (all players except hero).

    With min_hands > 1 a CTE first keeps the players with at least min_hands
    hands under the same filters, then the standard aggregation runs over
    their hands. With min_hands <= 1 every player with a matching row passes,
    so the CTE is left out.
    """
    where = "h.workspace_id = ?"
    main_params: list = [workspace_id]
    if exclude_player_id:
        where += " AND hp.player_id != ?"
        main_params.append(exclude_player_id)
    if stakes:
        where += " AND h.stakes = ?"
        main_params.append(stakes)
    if game_mode is not None:
        where += " AND h.game_mode = ?"
        main_params.append(game_mode)

    if min_hands <= 1:
        # every player with a row passes the CTE; only its IN drops rows without a player
        return _compute_stats_from_query(
            db, where + " AND hp.player_id IS NOT NULL", main_params, heavy=True)

    # The eligible-players CTE: same filters as the aggregation
    cte_where = where.replace("h.", "h2.").replace("hp.", "hp2.")
    cte = f"""WITH eligible AS (
        SELECT hp2.player_id FROM hand_players hp2
        JOIN hands h2 ON hp2.hand_id = h2.id AND hp2.workspace_id = h2.workspace_id
        WHERE {cte_where}
        GROUP BY hp2.player_id HAVING COUNT(*) >= ?
    )
    """
    cte_params = main_params + [min_hands]

    where += " AND hp.player_id IN (SELECT player_id FROM eligible)"
    full_sql = cte + agg_sql(where)
    all_params = cte_params + main_params

    return _compute_stats_from_query(db, where, all_params, sql_override=full_sql, heavy=True)
