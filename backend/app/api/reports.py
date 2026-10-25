from fastapi import APIRouter, Query
from app.date_filters import DATE_TO_SQL
from app.db import get_read_cursor, get_hero_player_id
from app.models import GraphPoint, GraphResponse, VarianceStats, SessionMarker, FilterOptions, StakeBreakdown, MonthBreakdown, PositionBreakdown, ResultsBreakdown, DriftStat, DriftResponse
import math
import threading
from collections import OrderedDict
from datetime import timedelta

from app import data_generation
from app.concurrency import heavy_slot

from app.h2n.rows import sql_case, sql_opp
from app.stat_registry import VALID_SQL

# Fold to 3-Bet on the drift page: H2N row P03, as in stats_engine / the General screen
# (hands H2N would refuse to import are left out, like everywhere else it is shown).
_F3B_OPP = f"({sql_opp('P03')} = 1 AND {VALID_SQL})"
_F3B_CASE = sql_case("P03")

router = APIRouter()


SESSION_GAP = timedelta(minutes=10)
_SESSION_GAP_US = int(SESSION_GAP.total_seconds() * 1_000_000)

# Points the Results chart draws (ResultsChart.tsx keeps at most this many, same indices).
GRAPH_MAX_POINTS = 1000

# Per-hand deltas of the 12 cumulative series, in GraphPoint field order. Each is cast to DOUBLE
# in SQL: the value equals Python's float(Decimal) of the stored DECIMAL (01/F4); the EV in $ casts
# the DECIMAL product, not the factors. Summed sequentially in pyarrow, in hand order, exactly as the
# former per-hand Python loop did (a SQL window SUM adds in another order: last-cent differences).
_SD = "COALESCE(hp.went_to_showdown, FALSE)"
_GRAPH_SERIES: list[tuple[str, str]] = [
    ("cumulative_bb", "CAST(COALESCE(hp.won_bb, 0) AS DOUBLE)"),
    ("cumulative_ev_bb", "CAST(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) AS DOUBLE)"),
    ("cumulative_rake_bb", "CAST(COALESCE(hp.rake_bb, 0) AS DOUBLE)"),
    ("cumulative_jackpot_bb", "CAST(COALESCE(hp.jackpot_bb, 0) AS DOUBLE)"),
    ("cumulative_showdown_bb",
     f"CASE WHEN {_SD} THEN CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) ELSE 0.0 END"),
    ("cumulative_nonshowdown_bb",
     f"CASE WHEN {_SD} THEN 0.0 ELSE CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) END"),
    ("cumulative_usd", "CAST(COALESCE(hp.won, 0) AS DOUBLE)"),
    ("cumulative_ev_usd",
     "CAST(COALESCE(COALESCE(hp.all_in_ev_bb, hp.won_bb) * h.bb_amount, 0) AS DOUBLE)"),
    ("cumulative_rake_usd", "CAST(COALESCE(hp.rake, 0) AS DOUBLE)"),
    ("cumulative_jackpot_usd", "CAST(COALESCE(hp.jackpot, 0) AS DOUBLE)"),
    ("cumulative_showdown_usd",
     f"CASE WHEN {_SD} THEN CAST(COALESCE(hp.won, 0) AS DOUBLE) ELSE 0.0 END"),
    ("cumulative_nonshowdown_usd",
     f"CASE WHEN {_SD} THEN 0.0 ELSE CAST(COALESCE(hp.won, 0) AS DOUBLE) END"),
]


def sample_indices(total: int, max_points: int = GRAPH_MAX_POINTS) -> list[int]:
    """0-based indices of the points the chart keeps: every point up to `max_points`, else
    `Math.round(i * step)` for i < max_points - 1 (ResultsChart.tsx) plus the last point."""
    if total <= max_points:
        return list(range(total))
    step = (total - 1) / (max_points - 1)
    out = []
    for i in range(max_points - 1):
        x = i * step
        f = math.floor(x)
        out.append(f + 1 if x - f >= 0.5 else f)   # JS Math.round: halves go up
    out.append(total - 1)
    return out


def graph_series(db, where: str, params: list, last_n: int | None = None,
                 max_points: int = GRAPH_MAX_POINTS) -> GraphResponse:
    """Cumulative results of the hero rows matching `where` (over hand_players hp ⋈ hands h).

    Points are sampled to `max_points` (always including the last hand); session markers and
    variance are computed over every hand."""
    import pyarrow as pa
    import pyarrow.compute as pc

    deltas = ", ".join(f"{expr} AS d{i}" for i, (_, expr) in enumerate(_GRAPH_SERIES))
    base = (f"SELECT {deltas}, h.played_at AS played_at, h.id AS hid "
            "FROM hand_players hp JOIN hands h ON hp.hand_id = h.id "
            f"AND hp.workspace_id = h.workspace_id WHERE {where}")
    if last_n:
        base = f"{base} ORDER BY h.played_at DESC, h.id DESC LIMIT {int(last_n)}"
    cols = ", ".join(f"d{i}" for i in range(len(_GRAPH_SERIES)))
    query = (f"SELECT {cols}, played_at, "
             "COALESCE(epoch_us(played_at) - LAG(epoch_us(played_at)) OVER w "
             f"> {_SESSION_GAP_US}, TRUE) AS sess_start "
             f"FROM ({base}) WINDOW w AS (ORDER BY played_at, hid) ORDER BY played_at, hid")
    t = db.execute(query, params).fetch_arrow_table()
    n = t.num_rows
    if n == 0:
        return GraphResponse(points=[], sessions=[], variance=None, hands=0)

    idx = sample_indices(n, max_points)
    take = pa.array(idx, pa.int64())
    # `+ 0.0`: the loop started from 0.0, so a leading -0.0 delta printed as 0.0 there.
    series = [[v + 0.0 for v in pc.take(pc.cumulative_sum(t.column(i)), take).to_pylist()]
              for i in range(len(_GRAPH_SERIES))]
    played = t.column("played_at")
    when = [p.isoformat() for p in pc.take(played, take).to_pylist()]
    names = [name for name, _ in _GRAPH_SERIES]
    points = [
        GraphPoint(hand_number=i + 1, played_at=when[j],
                   **{name: round(series[k][j], 2) for k, name in enumerate(names)})
        for j, i in enumerate(idx)
    ]

    starts = pc.indices_nonzero(t.column("sess_start")).to_pylist()
    ends = [s - 1 for s in starts[1:]] + [n - 1]
    s_at = pc.take(played, pa.array(starts, pa.int64())).to_pylist()
    e_at = pc.take(played, pa.array(ends, pa.int64())).to_pylist()
    sessions = [SessionMarker(start_hand=s + 1, end_hand=e + 1,
                              start_time=a.isoformat(), end_time=b.isoformat())
                for s, e, a, b in zip(starts, ends, s_at, e_at)]

    # Variance: the same two-pass Python sums over every hand as before (bit-identical).
    variance: VarianceStats | None = None
    if n >= 2:
        won_bb_values = t.column(0).to_pylist()
        mean = sum(won_bb_values) / n
        sq_diffs = sum((x - mean) ** 2 for x in won_bb_values)
        sd_per_hand = math.sqrt(sq_diffs / (n - 1))
        sd_bb100 = round(sd_per_hand * 10, 2)
        winrate_bb100 = round(mean * 100, 2)
        se_bb100 = sd_per_hand * 100 / math.sqrt(n)
        variance = VarianceStats(
            sd_bb=round(sd_per_hand, 4),
            sd_bb100=sd_bb100,
            winrate_bb100=winrate_bb100,
            ci_lower_bb100=round(winrate_bb100 - 1.96 * se_bb100, 2),
            ci_upper_bb100=round(winrate_bb100 + 1.96 * se_bb100, 2),
            n=n,
        )

    return GraphResponse(points=points, sessions=sessions, variance=variance, hands=n)


class _GraphCache:
    """LRU of finished chain graphs, bounded by entries and by the points + sessions they hold.
    Keys carry the data version; every data_generation bump also empties it."""

    def __init__(self, capacity: int = 16, max_items: int = 200_000):
        self.capacity = capacity
        self.max_items = max_items
        self._d: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _size(v: GraphResponse) -> int:
        return len(v.points) + len(v.sessions)

    def get(self, key):
        with self._lock:
            v = self._d.get(key)
            if v is not None:
                self._d.move_to_end(key)
            return v

    def put(self, key, value: GraphResponse) -> None:
        if self._size(value) > self.max_items:
            return
        with self._lock:
            self._d[key] = value
            self._d.move_to_end(key)
            while len(self._d) > self.capacity or (
                    sum(self._size(v) for v in self._d.values()) > self.max_items):
                self._d.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._d.clear()

    def __len__(self) -> int:
        return len(self._d)


_GRAPH_CACHE = _GraphCache()
data_generation.on_bump(_GRAPH_CACHE.clear)


def _graph_cache_key(db, workspace_id: int, player_id: int | None, chain: str, filters: tuple):
    """Cache key of a chain graph (422 / 404 like the chain resolve), None when not cacheable."""
    from fastapi import HTTPException
    from app.app_settings import get_app_settings
    from app.db import get_rebuild_status
    from app.reports.chain import canonical, data_version, parse_chain, target_player

    try:
        steps = parse_chain(chain)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid chain: {e}")
    target = target_player(db, workspace_id, player_id)
    if not target or get_rebuild_status().get("active"):
        return None
    day_start = int(get_app_settings(db)["day_start_hour"])
    return (workspace_id, target, canonical(steps), filters, day_start,
            data_version(db, workspace_id))


@router.get("/reports/graph", response_model=GraphResponse)
def get_graph(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
    workspace_id: int = Query(1),
    player_id: int | None = Query(None, description="Defaults to the workspace hero"),
    chain: str | None = Query(None, description="Reports filter chain: URL-encoded JSON Step[] "
                              "(frontend/src/lib/reports/types.ts); combined with the other "
                              "filters with AND. Any chain, even [], keeps only H2N-valid "
                              "hands (as the Reports counts do)"),
    max_points: int = Query(GRAPH_MAX_POINTS, ge=2, description="Points to return: the chart's "
                            "samples plus the last hand. `hands` is the full hand count; sessions "
                            "and variance always cover every hand"),
):
    from app.api.reports_lite import chain_scope

    db = get_read_cursor()
    key = None
    if chain is not None and chain.strip():
        key = _graph_cache_key(db, workspace_id, player_id, chain,
                               (stakes, game_mode, date_from, date_to, last_n, max_points))
        if key is not None:
            hit = _GRAPH_CACHE.get(key)
            if hit is not None:
                return hit

    with heavy_slot():
        scope = chain_scope(db, workspace_id, player_id, chain)
        if player_id is None:
            player_id = get_hero_player_id(db, workspace_id)
        if not player_id or (scope is not None and scope.empty):
            return GraphResponse(points=[], sessions=[], variance=None, hands=0)

        where = "hp.player_id = ? AND h.workspace_id = ?"
        params: list = [player_id, workspace_id]
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
        if scope is not None:
            pred, pparams = scope.where("h.id")
            where += f" AND {pred}"
            params.extend(pparams)

        out = graph_series(db, where, params, last_n, max_points)
    if key is not None:
        _GRAPH_CACHE.put(key, out)
    return out


@router.get("/reports/filter-options", response_model=FilterOptions)
def get_filter_options(
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
    if not player_id:
        return FilterOptions()

    # One scan: distinct stakes, distinct game modes and the date range as three grouping sets,
    # each set's rows in the order the separate DISTINCT ... ORDER BY queries returned.
    rows = db.execute(
        """
        SELECT GROUPING(h.stakes) AS g_s, GROUPING(h.game_mode) AS g_m, h.stakes, h.game_mode,
               MIN(h.played_at), MAX(h.played_at)
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE hp.player_id = ? AND h.workspace_id = ?
        GROUP BY GROUPING SETS ((h.stakes), (h.game_mode), ())
        ORDER BY g_s, g_m, h.stakes, h.game_mode
        """,
        [player_id, workspace_id],
    ).fetchall()

    stakes = [r[2] for r in rows if (r[0], r[1]) == (0, 1)]
    game_modes = [r[3] for r in rows if (r[0], r[1]) == (1, 0)]
    date_row = next((r[4:] for r in rows if (r[0], r[1]) == (1, 1)), None)
    date_range = {}
    if date_row and date_row[0]:
        date_range["min"] = str(date_row[0])[:10]
        date_range["max"] = str(date_row[1])[:10]

    return FilterOptions(stakes=stakes, game_modes=game_modes, date_range=date_range)


@router.get("/reports/breakdown", response_model=ResultsBreakdown)
def get_breakdown(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    last_n: int | None = Query(None, gt=0),
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
    if not player_id:
        return ResultsBreakdown()

    where = "hp.player_id = ? AND h.workspace_id = ?"
    params: list = [player_id, workspace_id]
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

    # For last_n, restrict to the most recent N hand IDs
    last_n_cte = ""
    if last_n:
        last_n_params = list(params)  # same filters
        last_n_cte = f"""
        WITH recent_hands AS (
            SELECT h.id FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
            WHERE {where}
            ORDER BY h.played_at DESC, h.id DESC
            LIMIT {int(last_n)}
        )
        """
        where += " AND h.id IN (SELECT id FROM recent_hands)"
        # params are used twice: once in CTE, once in main query
        params = last_n_params + params

    # Single CTE materializes the base dataset, then 3 GROUP BYs via GROUPING SETS
    _agg_cols = """
        COUNT(*) as hands,
        SUM(COALESCE(hp.won_bb, 0)) as won_bb,
        SUM(COALESCE(hp.won, 0)) as won_usd,
        SUM(COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)) as ev_bb,
        SUM(COALESCE(hp.rake_bb, 0)) as rake_bb,
        SUM(COALESCE(hp.rake, 0)) as rake_usd,
        SUM(COALESCE(hp.jackpot_bb, 0)) as jackpot_bb,
        SUM(COALESCE(hp.jackpot, 0)) as jackpot_usd
    """

    base_cte = f"""{last_n_cte}
    {',' if last_n_cte else 'WITH'} base AS (
        SELECT h.game_mode, h.stakes, h.bb_amount, hp.position,
               strftime(h.played_at, '%Y-%m') AS month,
               COALESCE(hp.won_bb, 0) AS won_bb_v,
               COALESCE(hp.won, 0) AS won_usd_v,
               COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) AS ev_bb_v,
               COALESCE(hp.rake_bb, 0) AS rake_bb_v,
               COALESCE(hp.rake, 0) AS rake_usd_v,
               COALESCE(hp.jackpot_bb, 0) AS jackpot_bb_v,
               COALESCE(hp.jackpot, 0) AS jackpot_usd_v
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {where}
    )
    """

    # By stakes
    stakes_rows = db.execute(
        f"""{base_cte}
        SELECT game_mode, stakes, bb_amount, COUNT(*),
               SUM(won_bb_v), SUM(won_usd_v), SUM(ev_bb_v),
               SUM(rake_bb_v), SUM(rake_usd_v), SUM(jackpot_bb_v), SUM(jackpot_usd_v)
        FROM base
        GROUP BY game_mode, stakes, bb_amount
        ORDER BY bb_amount ASC, game_mode ASC
        """, params,
    ).fetchall()

    by_stakes = []
    for r in stakes_rows:
        n = int(r[3]); wb = float(r[4]); eb = float(r[6])
        by_stakes.append(StakeBreakdown(
            game_mode=r[0], stakes=r[1], bb_amount=float(r[2]), hands=n,
            won_bb=round(wb, 2), won_usd=round(float(r[5]), 2), ev_bb=round(eb, 2),
            rake_bb=round(float(r[7]), 2), rake_usd=round(float(r[8]), 2),
            jackpot_bb=round(float(r[9]), 2), jackpot_usd=round(float(r[10]), 2),
            bb_per_100=round((wb / n) * 100, 2) if n else 0,
            ev_bb_per_100=round((eb / n) * 100, 2) if n else 0,
        ))

    # By month
    month_rows = db.execute(
        f"""{base_cte}
        SELECT month, COUNT(*), SUM(won_bb_v), SUM(won_usd_v), SUM(ev_bb_v),
               SUM(rake_bb_v), SUM(rake_usd_v), SUM(jackpot_bb_v), SUM(jackpot_usd_v)
        FROM base GROUP BY month ORDER BY month DESC
        """, params,
    ).fetchall()

    by_month = []
    for r in month_rows:
        n = int(r[1]); wb = float(r[2]); eb = float(r[4])
        by_month.append(MonthBreakdown(
            month=r[0], hands=n,
            won_bb=round(wb, 2), won_usd=round(float(r[3]), 2), ev_bb=round(eb, 2),
            rake_bb=round(float(r[5]), 2), rake_usd=round(float(r[6]), 2),
            jackpot_bb=round(float(r[7]), 2), jackpot_usd=round(float(r[8]), 2),
            bb_per_100=round((wb / n) * 100, 2) if n else 0,
            ev_bb_per_100=round((eb / n) * 100, 2) if n else 0,
        ))

    # By position
    pos_order = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB']
    pos_rows = db.execute(
        f"""{base_cte}
        SELECT position, COUNT(*), SUM(won_bb_v), SUM(won_usd_v), SUM(ev_bb_v),
               SUM(rake_bb_v), SUM(rake_usd_v), SUM(jackpot_bb_v), SUM(jackpot_usd_v)
        FROM base GROUP BY position
        """, params,
    ).fetchall()

    pos_map = {r[0]: r for r in pos_rows}
    by_position = []
    for pos in pos_order:
        r = pos_map.get(pos)
        if not r:
            continue
        n = int(r[1]); wb = float(r[2]); eb = float(r[4])
        by_position.append(PositionBreakdown(
            position=pos, hands=n,
            won_bb=round(wb, 2), won_usd=round(float(r[3]), 2), ev_bb=round(eb, 2),
            rake_bb=round(float(r[5]), 2), rake_usd=round(float(r[6]), 2),
            jackpot_bb=round(float(r[7]), 2), jackpot_usd=round(float(r[8]), 2),
            bb_per_100=round((wb / n) * 100, 2) if n else 0,
            ev_bb_per_100=round((eb / n) * 100, 2) if n else 0,
        ))

    return ResultsBreakdown(by_stakes=by_stakes, by_month=by_month, by_position=by_position)


# ── Drift Detection ─────────────────────────────────────────────────

# Each stat: (key, value_expr, opp_filter)
# value_expr: SQL expression for the 0/1 value
# opp_filter: SQL WHERE clause fragment for opportunity filtering
_DRIFT_STATS_V2: list[tuple[str, str, str]] = [
    ("vpip",               "CAST(hp.vpip AS DOUBLE)",               ""),
    ("pfr",                "CAST(hp.pfr AS DOUBLE)",                ""),
    ("three_bet",          "CAST(hp.three_bet AS DOUBLE)",          "AND hp.three_bet_opp = true"),
    ("fold_to_3bet",       "CAST(hp.fold_to_3bet AS DOUBLE)",       "AND hp.fold_to_3bet IS NOT NULL"),
    ("cbet_flop",          "CAST(hp.cbet_flop AS DOUBLE)",          "AND hp.cbet_flop_opp = true"),
    ("fold_to_cbet_flop",  "CAST(hp.fold_to_cbet_flop AS DOUBLE)",  "AND hp.fold_to_cbet_flop IS NOT NULL"),
    ("went_to_showdown",   "CAST(hp.went_to_showdown AS DOUBLE)",   "AND hp.saw_flop = true"),
    ("won_at_showdown",    "CAST(hp.won_at_showdown AS DOUBLE)",    "AND hp.went_to_showdown = true"),
    ("steal",              "CAST(hp.steal_attempted AS DOUBLE)",    "AND hp.steal_opp = true"),
    ("fold_to_steal",      "CAST(hp.fold_to_steal AS DOUBLE)",      "AND hp.faced_steal = true"),
    ("wwsf",               "CASE WHEN hp.won_bb > 0 THEN 1.0 ELSE 0.0 END", "AND hp.saw_flop = true"),
]

_DRIFT_INTERPRETATIONS: dict[str, dict[str, str]] = {
    "vpip":              {"up": "Playing more hands than usual",        "down": "Playing fewer hands than usual"},
    "pfr":               {"up": "Raising more preflop than usual",      "down": "Raising less preflop than usual"},
    "three_bet":         {"up": "3-betting more than usual",            "down": "3-betting less than usual"},
    "fold_to_3bet":      {"up": "Folding to 3-bets more than usual",   "down": "Defending vs 3-bets more than usual"},
    "cbet_flop":         {"up": "C-betting the flop more than usual",  "down": "Checking the flop more than usual"},
    "fold_to_cbet_flop": {"up": "Folding to flop c-bets more often",   "down": "Defending vs flop c-bets more often"},
    "went_to_showdown":  {"up": "Going to showdown more often",        "down": "Folding before showdown more often"},
    "won_at_showdown":   {"up": "Winning more at showdown",            "down": "Losing more at showdown"},
    "steal":             {"up": "Stealing more than usual",             "down": "Stealing less than usual"},
    "fold_to_steal":     {"up": "Folding to steals more often",        "down": "Defending vs steals more often"},
    "wwsf":              {"up": "Winning more when seeing the flop",   "down": "Winning less when seeing the flop"},
    "afq_flop":          {"up": "Playing more aggressively on flop",   "down": "Playing more passively on flop"},
}


def _check_drift(
    lifetime_avg: float,
    window_avg: float,
    window_n: int,
) -> tuple[float, float, float] | None:
    """Return (drift_pct, ci_lower, ci_upper) if drift detected, else None.

    Detection requires:
    1. |recent - lifetime| > lifetime * 0.10 (practical significance)
    2. lifetime falls outside 95% CI of recent estimate (statistical confidence)
    """
    diff = abs(window_avg - lifetime_avg)

    # Practical significance: at least 10% relative change
    if lifetime_avg > 0 and diff < lifetime_avg * 0.10:
        return None
    # Edge case: lifetime is 0 but window is non-zero
    if lifetime_avg == 0 and window_avg == 0:
        return None

    # 95% CI for window proportion
    se = math.sqrt(window_avg * (1.0 - window_avg) / window_n) if window_n > 0 else 0.0
    ci_lower = max(0.0, window_avg - 1.96 * se)
    ci_upper = min(1.0, window_avg + 1.96 * se)

    # Statistical confidence: lifetime must fall outside CI
    if ci_lower <= lifetime_avg <= ci_upper:
        return None

    drift_pct = ((window_avg - lifetime_avg) / lifetime_avg * 100) if lifetime_avg > 0 else (100.0 if window_avg > 0 else 0.0)
    return (drift_pct, ci_lower, ci_upper)


DRIFT_MIN_HANDS = 20000

# Opportunity groups of the recent window: the window of a stat is the last `window_size` hands
# (played_at DESC, id DESC) among the hands where its group predicate holds.
_DRIFT_GROUPS: list[str] = [
    "TRUE",
    "hp.three_bet_opp = true",
    _F3B_OPP,
    "hp.cbet_flop_opp = true",
    "hp.fold_to_cbet_flop IS NOT NULL",
    "hp.saw_flop = true",
    "hp.went_to_showdown = true",
    "hp.steal_opp = true",
    "hp.faced_steal = true",
]

# (group index, stats in it as (key, value expression))
_WINDOW_GROUPS: list[tuple[int, list[tuple[str, str]]]] = [
    (0, [("vpip", "CAST(hp.vpip AS DOUBLE)"), ("pfr", "CAST(hp.pfr AS DOUBLE)")]),
    (1, [("three_bet", "CAST(hp.three_bet AS DOUBLE)")]),
    (2, [("fold_to_3bet", f"CAST({_F3B_CASE} AS DOUBLE)")]),
    (3, [("cbet_flop", "CAST(hp.cbet_flop AS DOUBLE)")]),
    (4, [("fold_to_cbet_flop", "CAST(hp.fold_to_cbet_flop AS DOUBLE)")]),
    (5, [("went_to_showdown", "CAST(hp.went_to_showdown AS DOUBLE)"),
         ("wwsf", "CASE WHEN hp.won_bb > 0 THEN 1.0 ELSE 0.0 END")]),
    (6, [("won_at_showdown", "CAST(hp.won_at_showdown AS DOUBLE)")]),
    (7, [("steal", "CAST(hp.steal_attempted AS DOUBLE)")]),
    (8, [("fold_to_steal", "CAST(hp.fold_to_steal AS DOUBLE)")]),
]
_AFQ_GROUP = 5  # saw_flop


def _drift_windows(db, where: str, params: list, window_size: int
                   ) -> tuple[dict[str, tuple[float, int]], tuple[int, int, int]]:
    """Recent-window figures of every drift stat from one ordered columnar fetch.

    Same numbers as one `ORDER BY played_at DESC, id DESC LIMIT window_size` query per group:
    a row is in group g's window when the group predicate holds and fewer than window_size
    newer rows of the group precede it. The averaged values are 0/1, so their sums are exact
    in any order and float(sum) / count equals SQL AVG."""
    import pyarrow as pa
    import pyarrow.compute as pc

    flags = ", ".join(f"COALESCE({pred}, FALSE) AS g{g}" for g, pred in enumerate(_DRIFT_GROUPS))
    values = ", ".join(f"{expr} AS {sk}" for _, stats in _WINDOW_GROUPS for sk, expr in stats)
    t = db.execute(
        f"""
        SELECT {flags}, {values},
               hp.flop_bets + hp.flop_raises AS afq_num,
               hp.flop_bets + hp.flop_raises + hp.flop_calls + hp.flop_checks + hp.flop_folds AS afq_den
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {where}
        ORDER BY h.played_at DESC, h.id DESC
        """,
        params,
    ).fetch_arrow_table()

    def window(g: int):
        flag = t.column(f"g{g}")
        rank = pc.cumulative_sum(pc.cast(flag, pa.int64()))
        mask = pc.and_(flag, pc.less_equal(rank, window_size))
        return mask, int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)

    def total(col: str, mask) -> tuple[float | int | None, int]:
        v = pc.filter(t.column(col), mask)
        return pc.sum(v).as_py(), int(pc.count(v).as_py())

    data: dict[str, tuple[float, int]] = {}
    for g, stats in _WINDOW_GROUPS:
        mask, cnt = window(g)
        for sk, _ in stats:
            s, c = total(sk, mask)
            # AVG (NULL when no values -> 0.0); wwsf's 1.0/0.0 literals are DECIMAL: float() them
            data[sk] = (float(s) / c if c else 0.0, cnt)
    mask, cnt = window(_AFQ_GROUP)
    num, den = total("afq_num", mask)[0], total("afq_den", mask)[0]
    return data, (int(num or 0), int(den or 0), cnt)


@router.get("/reports/drift", response_model=DriftResponse)
def get_drift(
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    workspace_id: int = Query(1),
):
    db = get_read_cursor()
    player_id = get_hero_player_id(db, workspace_id)
    if not player_id:
        return DriftResponse()

    # Build shared WHERE clause
    where = "hp.player_id = ? AND h.workspace_id = ?"
    params: list = [player_id, workspace_id]
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

    # ── Lifetime stats; COUNT(*) (column 1) is the hand count ──
    lt = db.execute(
        f"""
        SELECT
            AVG(CAST(hp.vpip AS DOUBLE)), COUNT(*),
            AVG(CAST(hp.pfr AS DOUBLE)),
            AVG(CAST(hp.three_bet AS DOUBLE)) FILTER (WHERE hp.three_bet_opp),
            COUNT(*) FILTER (WHERE hp.three_bet_opp),
            AVG(CAST({_F3B_CASE} AS DOUBLE)) FILTER (WHERE {_F3B_OPP}),
            AVG(CAST(hp.cbet_flop AS DOUBLE)) FILTER (WHERE hp.cbet_flop_opp),
            COUNT(*) FILTER (WHERE hp.cbet_flop_opp),
            AVG(CAST(hp.fold_to_cbet_flop AS DOUBLE)) FILTER (WHERE hp.fold_to_cbet_flop IS NOT NULL),
            COUNT(*) FILTER (WHERE hp.fold_to_cbet_flop IS NOT NULL),
            AVG(CAST(hp.went_to_showdown AS DOUBLE)) FILTER (WHERE hp.saw_flop),
            COUNT(*) FILTER (WHERE hp.saw_flop),
            AVG(CAST(hp.won_at_showdown AS DOUBLE)) FILTER (WHERE hp.went_to_showdown),
            COUNT(*) FILTER (WHERE hp.went_to_showdown),
            AVG(CAST(hp.steal_attempted AS DOUBLE)) FILTER (WHERE hp.steal_opp),
            COUNT(*) FILTER (WHERE hp.steal_opp),
            AVG(CAST(hp.fold_to_steal AS DOUBLE)) FILTER (WHERE hp.faced_steal),
            COUNT(*) FILTER (WHERE hp.faced_steal),
            AVG(CASE WHEN hp.won_bb > 0 THEN 1.0 ELSE 0.0 END) FILTER (WHERE hp.saw_flop),
            SUM(hp.flop_bets + hp.flop_raises) FILTER (WHERE hp.saw_flop),
            SUM(hp.flop_bets + hp.flop_raises + hp.flop_calls + hp.flop_checks + hp.flop_folds) FILTER (WHERE hp.saw_flop),
            COUNT(*) FILTER (WHERE {_F3B_OPP})
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
        WHERE {where}
        """,
        params,
    ).fetchone()


    total_count = int(lt[1])
    if total_count < DRIFT_MIN_HANDS:
        return DriftResponse(total_hands=total_count)

    # Window = last 20% of hands
    window_size = max(1, int(total_count * 0.20))

    results: list[DriftStat] = []

    # Map: (stat_key, lt_avg_idx, lt_n_idx)
    # vpip/pfr share count at idx 1
    _LT_MAP = [
        ("vpip",              0,  1),
        ("pfr",               2,  1),
        ("three_bet",         3,  4),
        ("fold_to_3bet",      5,  21),  # H2N row P03, same as stats_engine
        ("cbet_flop",         6,  7),
        ("fold_to_cbet_flop", 8,  9),
        ("went_to_showdown",  10, 11),
        ("won_at_showdown",   12, 13),
        ("steal",             14, 15),
        ("fold_to_steal",     16, 17),
        ("wwsf",              18, 11),  # shares saw_flop count
    ]

    lifetime_data: dict[str, tuple[float, int]] = {}
    for stat_key, avg_idx, n_idx in _LT_MAP:
        avg_val = float(lt[avg_idx]) if lt[avg_idx] is not None else 0.0
        n_val = int(lt[n_idx])
        if n_val > 0:
            lifetime_data[stat_key] = (avg_val, n_val)

    # AFq flop lifetime
    afq_lt_num = int(lt[19]) if lt[19] is not None else 0
    afq_lt_den = int(lt[20]) if lt[20] is not None else 0

    # ── Recent windows ──
    window_data, afq_w = _drift_windows(db, where, params, window_size)

    # ── Build results for boolean stats ──
    for stat_key in [sk for sk, _, _ in _LT_MAP]:
        if stat_key not in lifetime_data or stat_key not in window_data:
            continue
        lt_avg, lt_n = lifetime_data[stat_key]
        w_avg, w_n = window_data[stat_key]
        if w_n < 30:
            continue
        result = _check_drift(lt_avg, w_avg, w_n)
        if result is None:
            continue
        drift_pct, ci_lower, ci_upper = result
        direction = "up" if w_avg > lt_avg else "down"
        interp = _DRIFT_INTERPRETATIONS.get(stat_key, {}).get(direction, "")
        results.append(DriftStat(
            stat=stat_key,
            lifetime_avg=round(lt_avg * 100, 2),
            window_avg=round(w_avg * 100, 2),
            lifetime_n=lt_n, window_n=w_n,
            drift_pct=round(drift_pct, 1),
            ci_lower=round(ci_lower * 100, 2),
            ci_upper=round(ci_upper * 100, 2),
            direction=direction, interpretation=interp,
        ))

    # ── AFq Flop (ratio stat) ──
    if afq_lt_den > 0:
        afq_lt_avg = afq_lt_num / afq_lt_den
        w_num = int(afq_w[0] or 0)
        w_den = int(afq_w[1] or 0)
        if w_den > 0 and int(afq_w[2]) >= 30:
            afq_w_avg = w_num / w_den
            afq_result = _check_drift(afq_lt_avg, afq_w_avg, w_den)
            if afq_result:
                drift_pct, ci_lower, ci_upper = afq_result
                direction = "up" if afq_w_avg > afq_lt_avg else "down"
                interp = _DRIFT_INTERPRETATIONS.get("afq_flop", {}).get(direction, "")
                results.append(DriftStat(
                    stat="afq_flop",
                    lifetime_avg=round(afq_lt_avg * 100, 2),
                    window_avg=round(afq_w_avg * 100, 2),
                    lifetime_n=afq_lt_den, window_n=w_den,
                    drift_pct=round(drift_pct, 1),
                    ci_lower=round(ci_lower * 100, 2),
                    ci_upper=round(ci_upper * 100, 2),
                    direction=direction, interpretation=interp,
                ))

    return DriftResponse(
        stats=results,
        window_hands=window_size,
        total_hands=total_count,
    )


