"""Split reports (POST /api/reports/split): one row per group of the chain's hands.

Types (frontend types.ts `SplitType`):

- plain types, over the chain's case hands: ``results`` (stakes + fast-fold flag + table
  size), ``positions`` (BB, SB, BTN, CO, MP, EP), ``stack_sizes`` (hero starting stack in bb:
  [0;40], [40;80], [80;120], [120;200], [200;300], > 300), ``hour_of_day`` (local start hour)
  and ``table_size``;
- action types, relative to the chain's hit point: ``next_actions`` (hero's next decision),
  ``faced_next`` (the villains' answer to a hero action) and ``bet_sizing`` (bucket of the
  hit action; only when the chain has one). Rows are evaluated with `app.reports.spots`
  exactly as the step a row's `filter` adds, so a clicked row opens a page with the same
  numbers.

Columns (reduced H2N stat sets; `sample` = the value key holding the column's sample size):

Plain types: Hands, VPIP, PFR, 3Bet (General rows V01 / V02 / P07 over the group's hands),
Ag. ((bets + raises) / calls over flop, turn and river, from the per-street E rows),
WTSD / WWSF% (base: hands with a flop action, E_FLOP_ANY), W%SD (base: any preflop action,
V03; H2N "won" = is_winner), Won ($), Won bb, Win Rate bb/100, Won EV ($, all-in EV),
Win Rate EV bb/100, Rake paid ($), Dispersion bbs (standard deviation of won bb per hand).

Action types: Hands (cases), Opp-s to hit, Hits Per 1000 Hands (cases / `total_hands` x
1000), Stat Value (cases / opps %), Action Profit bbs (per case: all-in-EV won bb plus the
chips hero had put in before the decision, a fold scores 0), Action Profit bb/hand, Won,
Won bb, Win Rate bb/100, WTSD (showdowns / cases, like the stat popup), W%SD and
Dispersion bbs. Faced Next rows are villain actions and have no Action Profit columns.

Sessions types (sessions.md §5.3): ``tables`` (one row per hands.table_name of the case
hands, by name; hands without a table name are left out) with the Table recipe columns:
Hands, Duration, Hands / h (time rules in app/sessions_h2n.py), Won, Won EV, Win Rate EV,
VPIP, PFR, Ag., 3Bet, WTSD, W%SD, WWSF%, Rake paid, Rake Paid bb/100, Won bb; ``players``
(one row per opponent dealt in to the case hands, Hands descending) with the OPPONENT's own
Hands, VPIP, PFR, 3Bet, Ag., WTSD, W%SD, Won, Won bb in those hands ("Won From Hero" is left
out: no exact per-opponent split of multiway pots).

Rows with no case are dropped (Bet Sizing call / fold buckets stay with any sample, like the
stat popup). `summary` (only with more than one row): counts and money add up, percentages
are recomputed from the summed cases and samples, per-hand averages are sample-weighted
(Bet Sizing's Stat Value sample = max(summed cases, largest single sample)); Tables:
Duration and played time add up, Hands / h = summed hands / summed played time.
"""

from __future__ import annotations

import math

from app.app_settings import max_break_seconds
from app.h2n.rows import ROWS
from app.h2n.sequence import BET, CHECK, FOLD, RAISE
from app.reports import spots
from app.reports.chain import (
    _FROM, ORDER, POS_NAMES, TABLE_MAX_BYTES, HandRec, Resolution, SeqSource, case_filter,
    iter_case_seqs, iter_records, stack_caption, stakes_caption,
)
from app.sessions_h2n import TimeStats, time_stats

POSITION_ORDER = ("BB", "SB", "BTN", "CO", "MP", "EP")
STACK_RANGES: tuple[tuple[float, float | None], ...] = (
    (0, 40), (40, 80), (80, 120), (120, 200), (200, 300), (300, None),
)
ENTRY_HEADERS = {
    "results": "Game Type", "positions": "Position", "stack_sizes": "Stack Size",
    "hour_of_day": "Hour of Day", "table_size": "Table Size", "next_actions": "Next Actions",
    "faced_next": "Faced Next", "bet_sizing": "Bet Sizing", "tables": "Tables",
    "players": "Players",
}


_E = {s: {k: f"E_{s}_{k}" for k in ("B", "R", "C", "ANY")} for s in ("FLOP", "TURN", "RIVER")}
# Bit positions (ROWS[key].bit) Acc.add reads, looked up once.
_B_V01, _B_V02, _B_V03, _B_P07, _B_FLOP_ANY = (
    ROWS[k].bit for k in ("V01", "V02", "V03", "P07", "E_FLOP_ANY"))
_E_BITS = tuple(tuple(ROWS[k[x]].bit for x in ("B", "R", "C", "ANY")) for k in _E.values())


def _col(id_, caption, fmt, abbrev=None, winnings=False, sample=None) -> dict:
    c = {"id": id_, "caption": caption, "format": fmt}
    if abbrev:
        c["abbrev"] = abbrev
    if winnings:
        c["winnings"] = True
    if sample:
        c["sample"] = sample
    return c


PLAIN_COLUMNS = [
    _col("hands", "Hands", "count"),
    _col("vpip", "VPIP", "pct", sample="vpip_opps"),
    _col("pfr", "PFR", "pct", sample="pfr_opps"),
    _col("threebet", "3Bet", "pct", sample="threebet_opps"),
    _col("ag", "Aggression", "ratio", abbrev="Ag.", sample="ag_opps"),
    _col("wtsd", "Went to Showdown", "pct", abbrev="WTSD", sample="wtsd_opps"),
    _col("wsd", "Won at Showdown", "pct", abbrev="W%SD", sample="wsd_opps"),
    _col("wwsf", "Won When Saw Flop", "pct", abbrev="WWSF%", sample="wwsf_opps"),
    _col("won", "Won", "money", winnings=True),
    _col("won_bb", "Won, bb", "bb", winnings=True),
    _col("bb100", "Win Rate, bb/100", "bb100", winnings=True, sample="hands"),
    _col("won_ev", "Won EV", "money", winnings=True),
    _col("ev_bb100", "Win Rate EV, bb/100", "bb100", winnings=True, sample="hands"),
    _col("rake", "Rake paid", "money"),
    _col("dispersion", "Dispersion, bbs", "bb", abbrev="Dispersion", sample="hands"),
]

# Sessions lower tabs (sessions.md §5.3): Tables = the Table recipe; Players = the
# opponent's own numbers in the chain's hands.
TABLE_COLUMNS = [
    _col("hands", "Hands", "count"),
    _col("duration", "Duration", "duration"),
    _col("hands_h", "Hands / h", "rate"),
    _col("won", "Won", "money", winnings=True),
    _col("won_ev", "Won EV", "money", winnings=True),
    _col("ev_bb100", "Win Rate EV, bb/100", "bb100", abbrev="Win Rate EV", winnings=True,
         sample="hands"),
    _col("vpip", "VPIP", "pct", sample="vpip_opps"),
    _col("pfr", "PFR", "pct", sample="pfr_opps"),
    _col("ag", "Aggression", "ratio", abbrev="Ag.", sample="ag_opps"),
    _col("threebet", "3Bet", "pct", sample="threebet_opps"),
    _col("wtsd", "Went to Showdown", "pct", abbrev="WTSD", sample="wtsd_opps"),
    _col("wsd", "Won at Showdown", "pct", abbrev="W%SD", sample="wsd_opps"),
    _col("wwsf", "Won When Saw Flop", "pct", abbrev="WWSF%", sample="wwsf_opps"),
    _col("rake", "Rake paid", "money"),
    _col("rake_bb100", "Rake Paid, bb/100", "bb100", abbrev="Rake Paid bb/100",
         sample="hands"),
    _col("won_bb", "Won, bb", "bb", abbrev="Won bb", winnings=True),
]

PLAYER_COLUMNS = [
    _col("hands", "Hands", "count"),
    _col("vpip", "VPIP", "pct", sample="vpip_opps"),
    _col("pfr", "PFR", "pct", sample="pfr_opps"),
    _col("threebet", "3Bet", "pct", sample="threebet_opps"),
    _col("ag", "Aggression", "ratio", abbrev="Ag.", sample="ag_opps"),
    _col("wtsd", "Went to Showdown", "pct", abbrev="WTSD", sample="wtsd_opps"),
    _col("wsd", "Won at Showdown", "pct", abbrev="W%SD", sample="wsd_opps"),
    _col("won", "Won", "money", winnings=True),
    _col("won_bb", "Won, bb", "bb", abbrev="Won bb", winnings=True),
]

_ACTION_HEAD = [
    _col("hands", "Hands", "count"),
    _col("opps", "Opportunities To Hit", "count", abbrev="Opp-s to hit"),
    _col("hits1000", "Hits Per 1000 Hands", "count"),
    _col("stat_value", "Stat Value", "pct", sample="stat_value_opps"),
]
_AP = [
    _col("ap_bbs", "Action Profit, bbs", "bb", winnings=True, sample="hands"),
    _col("ap_bbh", "Action Profit, bb/hand", "bbh", winnings=True, sample="hands"),
]
_ACTION_TAIL = [
    _col("won", "Won", "money", winnings=True),
    _col("won_bb", "Won, bb", "bb", winnings=True),
    _col("bb100", "Win Rate, bb/100", "bb100", winnings=True, sample="hands"),
    _col("wtsd", "Went to Showdown", "pct", abbrev="WTSD", sample="hands"),
    _col("wsd", "Won at Showdown", "pct", abbrev="W%SD", sample="sd_hands"),
    _col("dispersion", "Dispersion, bbs", "bb", abbrev="Dispersion", sample="hands"),
]
ACTION_COLUMNS = _ACTION_HEAD + _AP + _ACTION_TAIL
FACED_COLUMNS = _ACTION_HEAD + _ACTION_TAIL


# ── accumulators ─────────────────────────────────────────────────────────


class Acc:
    """Raw sums of one row (cases only, plus the opportunity count)."""

    __slots__ = ("hands", "opps", "won", "won_bb", "ev", "ev_bb", "rake", "rake_bb", "won_nsd",
                 "sq", "sd", "win_sd",
                 "ap", "ap_n", "vpip_c", "vpip_o", "pfr_c", "pfr_o", "tb_c", "tb_o",
                 "ag_br", "ag_c", "ag_o", "flop", "flop_sd", "flop_win", "v03", "v03_sd",
                 "v03_won_sd", "max_opps")

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, 0)

    def add(self, h: HandRec, ap: float | None = None) -> None:
        self.hands += 1
        self.won += h.won
        self.won_bb += h.won_bb
        self.ev += h.ev
        self.ev_bb += h.ev_bb
        self.rake += h.rake
        self.rake_bb += h.rake_bb
        self.sq += h.won_bb * h.won_bb
        if h.sd:
            self.sd += 1
            if h.win:
                self.win_sd += 1
        else:
            self.won_nsd += h.won
        if ap is not None:
            self.ap += ap
            self.ap_n += 1
        pre_o, pre_c, post_c = h.pre_opp, h.pre_case, h.post_case
        self.vpip_c += (pre_c >> _B_V01) & 1
        self.vpip_o += (pre_o >> _B_V01) & 1
        self.pfr_c += (pre_c >> _B_V02) & 1
        self.pfr_o += (pre_o >> _B_V02) & 1
        self.tb_c += (pre_c >> _B_P07) & 1
        self.tb_o += (pre_o >> _B_P07) & 1
        for b, r, c, any_ in _E_BITS:
            self.ag_br += ((post_c >> b) & 1) + ((post_c >> r) & 1)
            self.ag_c += (post_c >> c) & 1
            self.ag_o += (post_c >> any_) & 1
        if (post_c >> _B_FLOP_ANY) & 1:
            self.flop += 1
            self.flop_sd += h.sd
            self.flop_win += h.win
        if (pre_c >> _B_V03) & 1:
            self.v03 += 1
            if h.sd:
                self.v03_sd += 1
                self.v03_won_sd += h.win

    def merge(self, other: "Acc") -> None:
        _merge(self, other)


def _make_merge():
    """Acc.merge as straight-line code: every slot summed (max_opps: the largest sample)."""
    lines = [f"    a.{s} += b.{s}\n" for s in Acc.__slots__ if s != "max_opps"]
    src = ("def merge(a, b):\n" + "".join(lines)
           + "    a.max_opps = max(a.max_opps, b.max_opps, b.opps)\n")
    ns: dict = {}
    exec(src, ns)  # noqa: S102  (generated from the slot names, no input)
    return ns["merge"]


_merge = _make_merge()


# ── Arrow aggregation (plain chains, Players) ───────────────────────────
#
# The same sums as `Acc.add`, without one Python object per hand. Plain chains fetch one
# narrow row per case hand as Arrow, in hand insertion order (chain.ORDER), and sum each group
# with Arrow's single-threaded hash aggregate: it adds every group's floats one after another
# in row order, so the results are bit-identical to `Acc.add` over the same hands in the same
# order. Counts and bit sums are exact integers either way.


def _b(which: str, key: str) -> str:
    r = ROWS[key]
    col = r.case_column if which == "case" else r.opp_column
    return f"((COALESCE(hp.{col}, 0) >> {r.bit}) & 1)"


_SD = "COALESCE(hp.went_to_showdown, FALSE)"
_WIN = "COALESCE(hp.is_winner, FALSE)"
_DBL = "CAST({} AS DOUBLE)"
_WON = _DBL.format("COALESCE(hp.won, 0)")
_WON_BB = _DBL.format("COALESCE(hp.won_bb, 0)")
_FLOP = _b("case", "E_FLOP_ANY")
_V03 = _b("case", "V03")

# Acc slot -> per-row SQL (summed in row order); NULL rows are not added (won_nsd).
_ROW_FLOATS = {
    "won": _WON,
    "won_bb": _WON_BB,
    "ev": _DBL.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount"),
    "ev_bb": _DBL.format("COALESCE(hp.all_in_ev_bb, hp.won_bb, 0)"),
    "rake": _DBL.format("COALESCE(hp.rake, 0)"),
    "rake_bb": _DBL.format("COALESCE(hp.rake_bb, 0)"),
    "sq": f"{_WON_BB} * {_WON_BB}",
    "won_nsd": f"CASE WHEN NOT {_SD} THEN {_WON} END",
}
_ROW_INTS = {
    "sd": f"CAST({_SD} AS INTEGER)",
    "win_sd": f"CAST({_SD} AND {_WIN} AS INTEGER)",
    "vpip_c": _b("case", "V01"), "vpip_o": _b("opp", "V01"),
    "pfr_c": _b("case", "V02"), "pfr_o": _b("opp", "V02"),
    "tb_c": _b("case", "P07"), "tb_o": _b("opp", "P07"),
    "ag_br": " + ".join(f"{_b('case', k['B'])} + {_b('case', k['R'])}" for k in _E.values()),
    "ag_c": " + ".join(_b("case", k["C"]) for k in _E.values()),
    "ag_o": " + ".join(_b("case", k["ANY"]) for k in _E.values()),
    "flop": _FLOP,
    "flop_sd": f"CASE WHEN {_SD} THEN {_FLOP} ELSE 0 END",
    "flop_win": f"CASE WHEN {_WIN} THEN {_FLOP} ELSE 0 END",
    "v03": _V03,
    "v03_sd": f"CASE WHEN {_SD} THEN {_V03} ELSE 0 END",
    "v03_won_sd": f"CASE WHEN {_SD} AND {_WIN} THEN {_V03} ELSE 0 END",
}
_ROW_SQL = ", ".join([f"{e} AS {c}" for c, e in _ROW_FLOATS.items()]
                     + [f"CAST({e} AS UTINYINT) AS {c}" for c, e in _ROW_INTS.items()])
_ROW_AGGS = [(c, "sum") for c in (*_ROW_FLOATS, *_ROW_INTS)] + [([], "count_all")]


def plain_groups(db, res: Resolution, keys: list[str]) -> list[tuple[tuple, Acc]]:
    """(key values, Acc) per group of a plain resolution's case hands, by SQL key expressions
    (none = one group), in order of the groups' first hand (as `_group_plain` builds them)."""
    if not res.n_cases:
        return []
    return arrow_groups(db, keys, f"{_FROM} WHERE {res.where}", res.params)


def arrow_groups(db, keys: list[str], from_where: str, params: list, order: str = ORDER,
                 sort: list[tuple[str, str]] | None = None) -> list[tuple[tuple, Acc]]:
    """`plain_groups` over any rows (`from_where`: FROM ... WHERE ... with aliases hp, h),
    summed in `order`. `sort`: Arrow sort keys of the groups (key columns k0, k1, ..., the
    hand count `count_all`); default: order of the groups' first row."""
    names = [f"k{i}" for i in range(max(1, len(keys)))]
    kcols = [f"{k} AS k{i}" for i, k in enumerate(keys)] or ["1 AS k0"]
    tbl = db.execute(f"SELECT {', '.join(kcols)}, {_ROW_SQL} {from_where}{order}",
                     params).fetch_arrow_table()
    agg = tbl.group_by(names, use_threads=False).aggregate(_ROW_AGGS)
    del tbl
    vals = ["count_all"] + [c + "_sum" for c in (*_ROW_FLOATS, *_ROW_INTS)]
    agg = agg.select(names + vals)
    if sort:
        agg = agg.sort_by(sort)
    n = len(names)
    build = _build_acc   # slot order of _ACC_COLS
    # A NULL sum (no row added, e.g. won_nsd) stays int 0 like Acc.add; only columns that have
    # one are checked per group.
    nulls = [i for i, c in enumerate(vals) if agg.column(c).null_count]
    # DuckDB converts the aggregate to Python values faster than Arrow's to_pylist.
    rows = db.from_arrow(agg).fetchall()
    if not nulls:
        return [(r[:n], build(r[n:])) for r in rows]
    out = []
    for r in rows:
        v = r[n:]
        if any(v[i] is None for i in nulls):
            v = tuple(0 if x is None else x for x in v)
        out.append((r[:n], build(v)))
    return out


def plain_acc(db, res: Resolution) -> Acc:
    """Acc of all case hands of a plain resolution."""
    groups = plain_groups(db, res, [])
    return groups[0][1] if groups else Acc()


def plain_times(db, res: Resolution, key: str | None = None) -> dict:
    """{key value: (hand starts, table names)} of a plain resolution's case hands, in hand
    order (the inputs of `time_stats`)."""
    out: dict = {}
    if not res.n_cases:
        return out
    k = key or "NULL"
    for kv, t, tab in db.execute(
            f"SELECT {k}, h.played_at, h.table_name {_FROM} WHERE {res.where}{ORDER}",
            res.params).fetchall():
        ent = out.get(kv)
        if ent is None:
            ent = out[kv] = ([], [])
        ent[0].append(t)
        ent[1].append(tab)
    return out


_ACC_COLS = ("hands", *_ROW_FLOATS, *_ROW_INTS)   # order of the aggregate columns


def _make_acc_builder(names: tuple[str, ...]):
    """fn(values in `names` order) -> Acc, every other slot 0 (one tuple assignment)."""
    rest = [s for s in Acc.__slots__ if s not in names]
    src = (f"def build(vals):\n    a = new(Acc)\n"
           f"    {', '.join('a.' + n for n in names)}, = vals\n"
           + "".join(f"    a.{n} = 0\n" for n in rest) + "    return a\n")
    ns = {"Acc": Acc, "new": object.__new__}
    exec(src, ns)  # noqa: S102  (generated from the slot names above, no input)
    return ns["build"]


_build_acc = _make_acc_builder(_ACC_COLS)


def _pct(a, b):
    return a / b * 100.0 if b else None


def _dispersion(acc: Acc) -> float | None:
    n = acc.hands
    if n < 2:
        return None
    mean = acc.won_bb / n
    var = (acc.sq - n * mean * mean) / (n - 1)
    return math.sqrt(var) if var > 0 else 0.0


def plain_values(acc: Acc) -> dict:
    n = acc.hands
    return {
        "hands": n,
        "vpip": _pct(acc.vpip_c, acc.vpip_o), "vpip_opps": acc.vpip_o,
        "pfr": _pct(acc.pfr_c, acc.pfr_o), "pfr_opps": acc.pfr_o,
        "threebet": _pct(acc.tb_c, acc.tb_o), "threebet_opps": acc.tb_o,
        "ag": acc.ag_br / acc.ag_c if acc.ag_c else None, "ag_opps": acc.ag_o,
        "wtsd": _pct(acc.flop_sd, acc.flop), "wtsd_opps": acc.flop,
        "wsd": _pct(acc.v03_won_sd, acc.v03_sd), "wsd_opps": acc.v03_sd,
        "wwsf": _pct(acc.flop_win, acc.flop), "wwsf_opps": acc.flop,
        "won": acc.won, "won_bb": acc.won_bb,
        "bb100": acc.won_bb / n * 100.0 if n else None,
        "won_ev": acc.ev, "ev_bb100": acc.ev_bb / n * 100.0 if n else None,
        "rake": acc.rake, "dispersion": _dispersion(acc),
    }


def session_values(acc: Acc, ts: TimeStats) -> dict:
    """plain_values plus the Sessions stats (time stats of the same hands, rake bb/100,
    won without showdown, EV diff. = Won EV - Won)."""
    v = plain_values(acc)
    n = acc.hands
    v.update(
        duration=ts.duration_s if n else None, hands_h=ts.hands_per_hour,
        avg_tables=ts.avg_tables, rake_bb100=acc.rake_bb / n * 100.0 if n else None,
        won_nsd=acc.won_nsd, ev_diff=acc.ev - acc.won,
    )
    return v


def hand_time(hands, max_break_s: int) -> TimeStats:
    return time_stats([h.played_at for h in hands], [h.table for h in hands], max_break_s)


def action_values(acc: Acc, total: int, with_ap: bool = True, sizing_sample: bool = False
                  ) -> dict:
    n = acc.hands
    sample = acc.opps
    if sizing_sample:
        sample = max(n, acc.max_opps)
    out = {
        "hands": n, "opps": acc.opps,
        "hits1000": n / total * 1000.0 if total else None,
        "stat_value": _pct(n, sample), "stat_value_opps": sample,
        "won": acc.won, "won_bb": acc.won_bb,
        "bb100": acc.won_bb / n * 100.0 if n else None,
        "wtsd": _pct(acc.sd, n), "wsd": _pct(acc.win_sd, acc.sd), "sd_hands": acc.sd,
        "dispersion": _dispersion(acc),
    }
    if with_ap:
        out["ap_bbs"] = acc.ap if acc.ap_n else None
        out["ap_bbh"] = acc.ap / acc.ap_n if acc.ap_n else None
    return out


# ── plain splits ─────────────────────────────────────────────────────────


def _row(key: str, caption: str, filter_step: dict, values: dict, open_tab: str | None = None
         ) -> dict:
    r = {"key": key, "caption": caption, "filter": {**filter_step, "label": caption},
         "values": values}
    if open_tab:
        r["open_tab"] = open_tab
    return r


def _group_plain(res: Resolution, keyfn) -> dict:
    groups: dict = {}
    for h in res.cases:
        k = keyfn(h)
        if k is None:
            continue
        groups.setdefault(k, Acc()).add(h)
    return groups


def _stack_range(h: HandRec):
    if h.stack_bb is None:
        return None
    for lo, hi in STACK_RANGES:
        if h.stack_bb >= lo and (hi is None or h.stack_bb < hi):
            return (lo, hi)
    return None


def _hour(h: HandRec):
    pa = h.played_at
    return getattr(pa, "hour", None)


_STACK_SQL = "CASE " + " ".join(
    f"WHEN CAST(hp.stack_bb AS DOUBLE) >= {lo}"
    + (f" AND CAST(hp.stack_bb AS DOUBLE) < {hi}" if hi is not None else "") + f" THEN {i}"
    for i, (lo, hi) in enumerate(STACK_RANGES)) + " END"

# split type -> (Python key of a HandRec, SQL key expressions, SQL key values -> Python key)
_PLAIN_KEYS = {
    "results": (lambda h: (h.stakes, h.mode == "Fast Fold", h.tsize, h.bb_amount),
                ["h.stakes", "COALESCE(h.game_mode = 'Fast Fold', FALSE)", "h.table_size",
                 "CAST(h.bb_amount AS DOUBLE)"],
                lambda k: k),
    "positions": (lambda h: h.pos, ["hp.h2n_pos"], lambda k: k[0]),
    "stack_sizes": (_stack_range, [_STACK_SQL],
                    lambda k: None if k[0] is None else STACK_RANGES[k[0]]),
    "hour_of_day": (_hour, ["EXTRACT(hour FROM h.played_at)"],
                    lambda k: None if k[0] is None else int(k[0])),
    "table_size": (lambda h: h.tsize, ["h.table_size"], lambda k: k[0]),
}


def plain_split_groups(db, res: Resolution, typ: str) -> dict:
    """{group key: Acc} of a plain split type (SQL for plain chains, records otherwise)."""
    keyfn, keys, conv = _PLAIN_KEYS[typ]
    if not res.plain:
        return _group_plain(res, keyfn)
    groups: dict = {}
    for kv, acc in plain_groups(db, res, keys):
        k = conv(kv)
        if k is not None:
            groups[k] = acc
    return groups


def plain_split(db, res: Resolution, typ: str) -> tuple[list[dict], dict | None]:
    rows: list[dict] = []
    groups = plain_split_groups(db, res, typ) if typ in _PLAIN_KEYS else {}
    if typ == "results":
        for (stakes, fast, tsize, bb) in sorted(groups, key=lambda k: (k[3], not k[1], k[2] or 0)):
            acc = groups[(stakes, fast, tsize, bb)]
            parts = [stakes_caption(bb, stakes)]
            if tsize:
                parts.append(f"{tsize}-max")
            if fast:
                parts.append("Fast Fold")
            mode = "fast" if fast else "regular"
            rows.append(_row(f"{stakes}|{mode}|{tsize}", ", ".join(parts),
                             {"k": "game", "stakes": stakes, "mode": mode, "tsize": tsize},
                             plain_values(acc)))
    elif typ == "positions":
        for pos in POSITION_ORDER:
            if pos in groups:
                rows.append(_row(pos, POS_NAMES[pos], {"k": "pos", "v": [pos]},
                                 plain_values(groups[pos]), open_tab="next_actions"))
    elif typ == "stack_sizes":
        for lo, hi in STACK_RANGES:
            if (lo, hi) in groups:
                rows.append(_row(f"{lo}-{hi if hi is not None else ''}", stack_caption(lo, hi),
                                 {"k": "stack", "lo": lo, "hi": hi},
                                 plain_values(groups[(lo, hi)])))
    elif typ == "hour_of_day":
        for hr in sorted(groups):
            rows.append(_row(str(hr), str(hr), {"k": "hour", "v": [hr]}, plain_values(groups[hr])))
    elif typ == "table_size":
        for n in sorted(groups):
            rows.append(_row(str(n), f"{n}-max", {"k": "tsize", "v": [n]},
                             plain_values(groups[n])))
    summary = None
    if len(rows) > 1:
        total = Acc()
        for acc in groups.values():
            total.merge(acc)
        summary = plain_values(total)
    return rows, summary


# ── Sessions splits ──────────────────────────────────────────────────────


def tables_split(db, res: Resolution) -> tuple[list[dict], dict | None]:
    """One row per hands.table_name of the case hands (hands without a name are left out),
    by name; time stats per table (Duration, Hands / h). Summary: raw values add up."""
    max_break_s = max_break_seconds(db)
    accs: dict[str, Acc] = {}
    times: dict[str, tuple[list, list]] = {}
    if res.plain:
        for (name,), acc in plain_groups(db, res, ["h.table_name"]):
            if name is not None:
                accs[name] = acc
        times = plain_times(db, res, "h.table_name")
    else:
        for h in res.cases:
            if h.table is not None:
                ent = times.get(h.table)
                if ent is None:
                    ent = times[h.table] = ([], [])
                    accs[h.table] = Acc()
                ent[0].append(h.played_at)
                ent[1].append(h.table)
                accs[h.table].add(h)
    rows: list[dict] = []
    total, total_ts = Acc(), TimeStats(0, 0, 0, 0, 0)
    for name in sorted(accs):
        acc = accs[name]
        starts, tables = times[name]
        ts = time_stats(starts, tables, max_break_s)
        rows.append(_row(name, name, {"k": "table", "v": [name]}, session_values(acc, ts)))
        total.merge(acc)
        total_ts = total_ts.merge(ts)
    summary = session_values(total, total_ts) if len(rows) > 1 else None
    return rows, summary


# Resident bytes of one players_table entry (tuple, Acc with its boxed floats, name string),
# measured with tracemalloc on the 20k fixture.
PLAYER_ENTRY_BYTES = 640


def players_table(db, res: Resolution) -> list[tuple[int, str, Acc]]:
    """`_players_table`, kept on the resolution while it fits TABLE_MAX_BYTES: the Players
    response itself is too big to cache (a dict per opponent), rebuilding it from this
    compact table is several times cheaper than recomputing the sums."""
    return res.memo(("players_table",), lambda: _players_table(db, res),
                    size=lambda t: PLAYER_ENTRY_BYTES * len(t) + 1024,
                    max_bytes=TABLE_MAX_BYTES)


def _players_table(db, res: Resolution) -> list[tuple[int, str, Acc]]:
    """(player id, username, Acc of the opponent's own rows) per opponent dealt in to the
    chain's case hands, Hands descending: the opponents' rows summed per player in hand order
    (Arrow, like the plain splits) instead of one HandRec per row. The same arithmetic as
    folding the records hand by hand; the previous fold took the rows in the order of 5000-id
    chunk queries, so sums can differ from it in the last bits (constant results such as a
    dispersion of 0 are exact either way)."""
    if res.player_id is None or not res.n_cases:
        return []
    pred, pparams = case_filter(db, res, "hp.hand_id")
    # Hands descending, then username, then id (Arrow compares the UTF-8 bytes: the same
    # order as Python's str comparison).
    rows = arrow_groups(
        db, ["hp.player_id", "p.username"],
        f"{_FROM} JOIN players p ON p.id = hp.player_id WHERE h.workspace_id = ? "
        f"AND hp.player_id <> ? AND COALESCE(hp.h2n_valid, TRUE) AND {pred}",
        [res.workspace_id, res.player_id, *pparams],
        sort=[("count_all", "descending"), ("k1", "ascending"), ("k0", "ascending")])
    return [(int(pid), name, acc) for (pid, name), acc in rows]


def players_split(db, res: Resolution) -> tuple[list[dict], dict | None]:
    """One row per opponent, Hands descending. Row filter = {k: 'with', player_id: <the
    reporting player>}: the page it opens reports on the opponent (row.player) in hands
    with the reporting player, so it shows the row's numbers when the parent chain has only
    hand-level steps (session, table, date, stakes, ...)."""
    rows: list[dict] = []
    total = Acc()
    for pid, name, acc in players_table(db, res):
        r = _row(str(pid), name, {"k": "with", "player_id": res.player_id}, plain_values(acc))
        r["player"] = {"id": pid, "username": name}
        rows.append(r)
        total.merge(acc)
    return rows, (plain_values(total) if len(rows) > 1 else None)


# ── action tables (computed once per resolution, cached on it) ──────────


def _table_add(table: dict, cands, ev, seq, p: int, h: HandRec) -> None:
    """Add one case hand to a Next / Faced table (opps Acc per (street, key))."""
    hit = h.hit
    for street, key in cands:
        code, nhit = ev(seq, p, hit, street, key)
        if not code:
            continue
        acc = table.get((street, key))
        if acc is None:
            acc = table[(street, key)] = Acc()
        acc.opps += 1
        if code & spots.CASE:
            ap = None
            a = seq.streets[nhit[0]][nhit[1]]
            if a.actor == p:
                ap = 0.0 if a.eff == FOLD else h.ev_bb + spots.committed_bb(seq, p, nhit)
            acc.add(h, ap)


def _candidates(ctx, which: str):
    if which == "next":
        return spots.next_candidates(ctx), spots.eval_next
    return spots.faced_candidates(ctx), spots.eval_faced


def table_fillers(ctx) -> dict:
    """{which: (candidates, evaluator, empty table)} of the Next / Faced tables at `ctx`
    (filled by chain._compute while it has each case's sequence decoded)."""
    out = {}
    for which in ("next", "faced"):
        cands, ev = _candidates(ctx, which)
        if cands:
            out[which] = (cands, ev, {})
    return out


def fill_tables(fill: dict, seq, p: int, h: HandRec) -> None:
    for cands, ev, table in fill.values():
        _table_add(table, cands, ev, seq, p, h)


def _table_bytes(table: dict) -> int:
    return 600 * len(table) + 1024


def _compute_action_table(db, res: Resolution, which: str) -> dict:
    cands, ev = _candidates(res.ctx, which)
    table: dict = {}
    if not cands or not res.username:
        return table
    # Plain chains keep no blobs: each chunk's come with its records and are dropped after it.
    chunks = (iter_case_seqs(db, res) if res.plain
              else ((recs, res.blobs) for recs in iter_records(db, res)))
    for recs, blobs in chunks:
        ids = [h.hid for h in recs]
        src = SeqSource(db, res.workspace_id, blobs)
        src.prefetch_missing([h for h in ids if blobs.get(h) is None])
        for h in recs:
            seq = src.get(h.hid)
            if seq is None:
                continue
            p = seq.index.get(res.username)
            if p is None:
                continue
            _table_add(table, cands, ev, seq, p, h)
    return table


def action_table(db, res: Resolution, which: str) -> dict:
    """{(street, key): (opps Acc with cases)} for "next" or "faced" rows after the hit."""
    return res.memo(("table", which), lambda: _compute_action_table(db, res, which),
                    size=_table_bytes)


def _sizing_types(res: Resolution) -> set[int]:
    if res.ctx.typ is not None:
        return {res.ctx.typ}
    return {h.hit_eff for h in res.cases if h.hit_eff is not None}


def _compute_sizing(db, res: Resolution) -> tuple[list, dict]:
    from app.api.general_popup import _BUCKETS, _size_hits

    out: tuple[list, dict] = ([], {})
    if res.has_spot and res.username and res.hands:
        types = _sizing_types(res)
        pre = res.ctx.street == 0
        buckets = tuple(b for b in _BUCKETS if b.preflop == pre and b.typ in types)
        if buckets:
            ids = [h.hid for h in res.hands]
            src = SeqSource(db, res.workspace_id, res.blobs)
            src.prefetch_missing([h for h in ids if res.blobs.get(h) is None])
            accs = {b.id: Acc() for b in buckets}
            for h in res.hands:
                seq = src.get(h.hid)
                if seq is None or h.hit is None:
                    continue
                for bid, is_case in _size_hits(seq, h.hit, buckets):
                    acc = accs[bid]
                    acc.opps += 1
                    if is_case and h.case:
                        acc.add(h, h.ap)
            out = (list(buckets), accs)
    return out


def sizing_table(db, res: Resolution) -> tuple[list, dict]:
    return res.memo(("sizing",), lambda: _compute_sizing(db, res),
                    size=lambda t: 600 * len(t[1]) + 1024)


def _sort_key(item):
    (street, key) = item
    return (street, spots.ACTION_RANK.get(key, 99))


def action_split(db, res: Resolution, typ: str) -> tuple[list[dict], list[dict], dict | None]:
    """(columns, rows, summary) of next_actions / faced_next / bet_sizing."""
    total = res.total_hands
    rows: list[dict] = []
    accs: list[Acc] = []
    if typ in ("next_actions", "faced_next"):
        which = "next" if typ == "next_actions" else "faced"
        with_ap = which == "next"
        columns = ACTION_COLUMNS if with_ap else FACED_COLUMNS
        table = action_table(db, res, which)
        for street, key in sorted(table, key=_sort_key):
            acc = table[(street, key)]
            if acc.hands == 0:
                continue
            sname = spots.STREETS[street]
            if which == "next":
                ctx = spots.next_spot(res.ctx, street, key)
                step = {"k": "next", "street": sname, "a": key}
                tab = "faced_next"
            else:
                ctx = spots.faced_spot(res.ctx, street, key)
                step = {"k": "faced", "street": sname, "a": key}
                tab = "next_actions"
            rows.append(_row(f"{sname}:{key}", ctx.name or key, step,
                             action_values(acc, total, with_ap), open_tab=tab))
            accs.append(acc)
        summary = None
        if len(rows) > 1:
            t = Acc()
            for a in accs:
                t.merge(a)
            summary = action_values(t, total, with_ap)
            # Opportunities of sibling rows belong to one decision: summing them is meaningless
            summary["opps"] = None
            summary["stat_value"] = None
            summary["stat_value_opps"] = None
        return columns, rows, summary
    # bet sizing
    buckets, baccs = sizing_table(db, res)
    tab = "faced_next" if res.ctx.side == "hero" else "next_actions"
    kept: list[Acc] = []
    for b in buckets:
        acc = baccs[b.id]
        visible = acc.hands > 0 if b.typ in (BET, RAISE, CHECK) else acc.opps > 0
        if not visible:
            continue
        rows.append(_row(b.id, b.label, {"k": "betsize", "bucket": b.id},
                         action_values(acc, total, True), open_tab=tab))
        kept.append(acc)
    summary = None
    if len(rows) > 1:
        t = Acc()
        for a in kept:
            t.merge(a)
        summary = action_values(t, total, True, sizing_sample=True)
    return ACTION_COLUMNS, rows, summary


def _response_bytes(d: dict) -> int:
    """Rough resident size of a split / spot response (dict per row with ~20 values)."""
    return 2500 * (len(d.get("rows") or d.get("stats") or d.get("cells") or ())) + 4096


def split(db, res: Resolution, typ: str) -> dict:
    """The finished response, cached on the resolution (the Tables split also by the
    max-break setting its time stats use)."""
    key = ("split", typ, max_break_seconds(db)) if typ == "tables" else ("split", typ)
    return res.memo(key, lambda: _split(db, res, typ), size=_response_bytes)


def _split(db, res: Resolution, typ: str) -> dict:
    if typ in ("next_actions", "faced_next", "bet_sizing"):
        columns, rows, summary = action_split(db, res, typ)
    elif typ == "tables":
        columns = TABLE_COLUMNS
        rows, summary = tables_split(db, res)
    elif typ == "players":
        columns = PLAYER_COLUMNS
        rows, summary = players_split(db, res)
    else:
        columns = PLAIN_COLUMNS
        rows, summary = plain_split(db, res, typ)
    return {"type": typ, "entry_header": ENTRY_HEADERS[typ], "columns": columns, "rows": rows,
            "summary": summary, "total_hands": res.total_hands}


__all__ = ["split", "action_table", "Acc", "plain_values", "action_values", "session_values",
           "hand_time", "plain_acc", "plain_groups", "plain_times", "PLAIN_COLUMNS",
           "ACTION_COLUMNS", "FACED_COLUMNS", "TABLE_COLUMNS",
           "PLAYER_COLUMNS"]
