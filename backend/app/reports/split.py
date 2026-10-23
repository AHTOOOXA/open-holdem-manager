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

Rows with no case are dropped (Bet Sizing call / fold buckets stay with any sample, like the
stat popup). `summary` (only with more than one row): counts and money add up, percentages
are recomputed from the summed cases and samples, per-hand averages are sample-weighted
(Bet Sizing's Stat Value sample = max(summed cases, largest single sample)).
"""

from __future__ import annotations

import math

from app.h2n.rows import ROWS
from app.h2n.sequence import BET, CHECK, FOLD, RAISE
from app.reports import spots
from app.reports.chain import (
    POS_NAMES, HandRec, Resolution, SeqSource, fetch_seqs, stack_caption, stakes_caption,
)

POSITION_ORDER = ("BB", "SB", "BTN", "CO", "MP", "EP")
STACK_RANGES: tuple[tuple[float, float | None], ...] = (
    (0, 40), (40, 80), (80, 120), (120, 200), (200, 300), (300, None),
)
ENTRY_HEADERS = {
    "results": "Game Type", "positions": "Position", "stack_sizes": "Stack Size",
    "hour_of_day": "Hour of Day", "table_size": "Table Size", "next_actions": "Next Actions",
    "faced_next": "Faced Next", "bet_sizing": "Bet Sizing",
}


def _bit(mask: int, key: str) -> int:
    return (mask >> ROWS[key].bit) & 1


_E = {s: {k: f"E_{s}_{k}" for k in ("B", "R", "C", "ANY")} for s in ("FLOP", "TURN", "RIVER")}


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

    __slots__ = ("hands", "opps", "won", "won_bb", "ev", "ev_bb", "rake", "sq", "sd", "win_sd",
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
        self.sq += h.won_bb * h.won_bb
        if h.sd:
            self.sd += 1
            if h.win:
                self.win_sd += 1
        if ap is not None:
            self.ap += ap
            self.ap_n += 1
        pre_o, pre_c, post_c = h.pre_opp, h.pre_case, h.post_case
        self.vpip_c += _bit(pre_c, "V01")
        self.vpip_o += _bit(pre_o, "V01")
        self.pfr_c += _bit(pre_c, "V02")
        self.pfr_o += _bit(pre_o, "V02")
        self.tb_c += _bit(pre_c, "P07")
        self.tb_o += _bit(pre_o, "P07")
        for keys in _E.values():
            self.ag_br += _bit(post_c, keys["B"]) + _bit(post_c, keys["R"])
            self.ag_c += _bit(post_c, keys["C"])
            self.ag_o += _bit(post_c, keys["ANY"])
        if _bit(post_c, "E_FLOP_ANY"):
            self.flop += 1
            self.flop_sd += h.sd
            self.flop_win += h.win
        if _bit(pre_c, "V03"):
            self.v03 += 1
            if h.sd:
                self.v03_sd += 1
                self.v03_won_sd += h.win

    def merge(self, other: "Acc") -> None:
        for s in self.__slots__:
            if s == "max_opps":
                self.max_opps = max(self.max_opps, other.max_opps, other.opps)
            else:
                setattr(self, s, getattr(self, s) + getattr(other, s))


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


def plain_split(res: Resolution, typ: str) -> tuple[list[dict], dict | None]:
    rows: list[dict] = []
    if typ == "results":
        groups = _group_plain(res, lambda h: (h.stakes, h.mode == "Fast Fold", h.tsize, h.bb_amount))
        for (stakes, fast, tsize, bb) in sorted(groups, key=lambda k: (k[3], not k[1], k[2] or 0)):
            acc = groups[(stakes, fast, tsize, bb)]
            parts = [stakes_caption(bb, stakes)]
            if tsize:
                parts.append(f"{tsize}-max")
            if fast:
                parts.append("Fast Fold")
            mode = "fast" if fast else "regular"
            rows.append(_row(f"{stakes}|{mode}|{tsize}", ", ".join(parts),
                             {"k": "game", "stakes": stakes, "mode": mode, "tsize": tsize or 0},
                             plain_values(acc)))
    elif typ == "positions":
        groups = _group_plain(res, lambda h: h.pos)
        for pos in POSITION_ORDER:
            if pos in groups:
                rows.append(_row(pos, POS_NAMES[pos], {"k": "pos", "v": [pos]},
                                 plain_values(groups[pos]), open_tab="next_actions"))
    elif typ == "stack_sizes":
        groups = _group_plain(res, _stack_range)
        for lo, hi in STACK_RANGES:
            if (lo, hi) in groups:
                rows.append(_row(f"{lo}-{hi if hi is not None else ''}", stack_caption(lo, hi),
                                 {"k": "stack", "lo": lo, "hi": hi},
                                 plain_values(groups[(lo, hi)])))
    elif typ == "hour_of_day":
        groups = _group_plain(res, _hour)
        for hr in sorted(groups):
            rows.append(_row(str(hr), str(hr), {"k": "hour", "v": [hr]}, plain_values(groups[hr])))
    elif typ == "table_size":
        groups = _group_plain(res, lambda h: h.tsize)
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


# ── action tables (computed once per resolution, cached on it) ──────────


def _source(db, res: Resolution) -> SeqSource:
    ids = [h.hid for h in res.cases]
    if not res.blobs:
        res.blobs = dict(fetch_seqs(db, res.workspace_id, ids))
    src = SeqSource(db, res.workspace_id, res.blobs)
    src.prefetch_missing([h for h in ids if res.blobs.get(h) is None])
    return src


def action_table(db, res: Resolution, which: str) -> dict:
    """{(street, key): (opps Acc with cases)} for "next" or "faced" rows after the hit."""
    cache_key = ("table", which)
    with res.lock:
        if cache_key in res.tables:
            return res.tables[cache_key]
        cands = (spots.next_candidates(res.ctx) if which == "next"
                 else spots.faced_candidates(res.ctx))
        table: dict = {}
        if cands and res.username:
            src = _source(db, res)
            ev = spots.eval_next if which == "next" else spots.eval_faced
            for h in res.cases:
                seq = src.get(h.hid)
                if seq is None:
                    continue
                p = seq.index.get(res.username)
                if p is None:
                    continue
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
        res.tables[cache_key] = table
        return table


def _sizing_types(res: Resolution) -> set[int]:
    if res.ctx.typ is not None:
        return {res.ctx.typ}
    return {h.hit_eff for h in res.cases if h.hit_eff is not None}


def sizing_table(db, res: Resolution) -> tuple[list, dict]:
    from app.api.general_popup import _BUCKETS, _size_hits

    with res.lock:
        if ("sizing",) in res.tables:
            return res.tables[("sizing",)]
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
    with res.lock:
        res.tables[("sizing",)] = out
    return out


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


def split(db, res: Resolution, typ: str) -> dict:
    if typ in ("next_actions", "faced_next", "bet_sizing"):
        columns, rows, summary = action_split(db, res, typ)
    else:
        columns = PLAIN_COLUMNS
        rows, summary = plain_split(res, typ)
    return {"type": typ, "entry_header": ENTRY_HEADERS[typ], "columns": columns, "rows": rows,
            "summary": summary, "total_hands": res.total_hands}


__all__ = ["split", "action_table", "Acc", "plain_values", "action_values", "PLAIN_COLUMNS",
           "ACTION_COLUMNS", "FACED_COLUMNS"]
