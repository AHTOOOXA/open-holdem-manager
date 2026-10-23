"""Upper tabs of a Reports page: Stats ("smart report"), Preflop Range, Hand Strength, and
the quick-filter list.

Stats recipes (reduced from Hand2Note's relevant-stats sets, by the kind of the hit point):

- plain (hand start): Hands, VPIP, PFR, 3Bet, Ag., WTSD, W%SD, WWSF%, Won, Win Rate bb/100,
  Win Rate EV bb/100. VPIP / PFR / 3Bet are clickable (`row` steps V01 / V02 / P07).
- hero action: Hands, Opp-s to hit, Hits Per 1000 Hands, Stat Value, the villains' answers
  (bet / raise: All Villains Fold, One Villain Call, Villain Raise; call / check: Villain
  Bet, Villains Check; each a clickable `faced` step with its own sample), Action Profit
  bbs, Action Profit bb/hand, Won, Win Rate bb/100, WTSD, W%SD. A fold has no villain
  answers.
- villain action: Hands, Stat Value, hero's Fold / Call / Raise (or Bet / Check after a
  check) next, as clickable `next` steps, Won, Win Rate bb/100.

Preflop Range: the 169 classes of the case hands with known hero cards; `level` 0-3 is
Hand2Note's 4-level shade of the class's density (hands / combos: pairs 6, suited 4,
offsuit 12) against the mean density of the classes that have hands (ratio <= 0.4 -> 0,
<= 0.8 -> 1, <= 3 -> 2, above -> 3; a class without hands is 0).

Hand Strength: the case hands' hand-value category on one street (`hv_<street>`), every
category of the street in order plus "Other" when it has hands; `pct` is 0-100.
"""

from __future__ import annotations

from app.h2n.rows import ROWS
from app.h2n.sequence import BET, CALL, CHECK, FOLD, RAISE
from app.hand_value import OTHER, STREET_CATEGORIES, category_info
from app.reports import spots
from app.reports.chain import CLASSES, Resolution, card_class
from app.reports.split import Acc, action_table, action_values, plain_values

def _stat(id_, caption, value, fmt, sample=None, winnings=False, filter_=None) -> dict:
    d = {"id": id_, "caption": caption, "value": value, "sample": sample, "format": fmt}
    if winnings:
        d["winnings"] = True
    if filter_:
        d["filter"] = filter_
    return d


def _kind(res: Resolution) -> str:
    kind = spots.kind_of(res.ctx)
    if res.ctx.side == "hero" and res.ctx.typ is None:
        types = [h.hit_eff for h in res.cases if h.hit_eff is not None]
        if types:
            t = max(set(types), key=types.count)
            kind = {RAISE: "hero_raise", BET: "hero_bet", CALL: "hero_call",
                    CHECK: "hero_check", FOLD: "hero_fold"}[t]
    return kind


def _table_stat(res, table, street, key, which) -> dict | None:
    acc = table.get((street, key))
    if acc is None or acc.opps == 0:
        return None
    sname = spots.STREETS[street]
    if which == "faced":
        ctx = spots.faced_spot(res.ctx, street, key)
        caption = spots.FACED_CAPTIONS[key]
        step = {"k": "faced", "street": sname, "a": key, "label": ctx.name}
    else:
        ctx = spots.next_spot(res.ctx, street, key)
        caption = spots.NEXT_CAPTIONS[key]
        step = {"k": "next", "street": sname, "a": key, "label": ctx.name}
    return _stat(f"{which}:{sname}:{key}", caption, acc.hands / acc.opps * 100.0, "pct",
                 sample=acc.opps, filter_=step)


def _best(res, table, keys, which) -> list[dict]:
    """One stat per key: the street with the most opportunities."""
    out = []
    for key in keys:
        best = None
        for (street, k), acc in table.items():
            if k == key and (best is None or acc.opps > table[best].opps):
                best = (street, k)
        if best is not None:
            st = _table_stat(res, table, best[0], key, which)
            if st:
                out.append(st)
    return out


def spot(db, res: Resolution) -> dict:
    cases = res.cases
    kind = _kind(res)
    hit_label = res.ctx.name if res.has_spot else None
    acc = Acc()
    for h in cases:
        acc.add(h, h.ap if h.hit_hero else None)
    acc.opps = len(res.hands)
    stats: list[dict] = []
    if kind == "plain":
        v = plain_values(acc)
        stats = [
            _stat("hands", "Hands", v["hands"], "count"),
            _stat("vpip", "VPIP", v["vpip"], "pct", v["vpip_opps"],
                  filter_={"k": "row", "key": "V01", "label": "VPIP"}),
            _stat("pfr", "PFR", v["pfr"], "pct", v["pfr_opps"],
                  filter_={"k": "row", "key": "V02", "label": "PFR"}),
            _stat("threebet", "3Bet", v["threebet"], "pct", v["threebet_opps"],
                  filter_={"k": "row", "key": "P07", "label": "3-Bet"}),
            _stat("ag", "Ag.", v["ag"], "ratio", v["ag_opps"]),
            _stat("wtsd", "WTSD", v["wtsd"], "pct", v["wtsd_opps"]),
            _stat("wsd", "W%SD", v["wsd"], "pct", v["wsd_opps"]),
            _stat("wwsf", "WWSF%", v["wwsf"], "pct", v["wwsf_opps"]),
            _stat("won", "Won", v["won"], "money", winnings=True),
            _stat("bb100", "Win Rate, bb/100", v["bb100"], "bb100", v["hands"], winnings=True),
            _stat("ev_bb100", "Win Rate EV, bb/100", v["ev_bb100"], "bb100", v["hands"],
                  winnings=True),
        ]
        return {"hands": len(cases), "kind": kind, "hit_label": None, "stats": stats}

    v = action_values(acc, res.total_hands, with_ap=kind != "villain")
    head = [
        _stat("hands", "Hands", v["hands"], "count"),
        _stat("opps", "Opp-s to hit", v["opps"], "count"),
        _stat("hits1000", "Hits Per 1000 Hands", v["hits1000"], "count", res.total_hands),
        _stat("stat_value", "Stat Value", v["stat_value"], "pct", v["opps"]),
    ]
    tail = [
        _stat("won", "Won", v["won"], "money", winnings=True),
        _stat("bb100", "Win Rate, bb/100", v["bb100"], "bb100", v["hands"], winnings=True),
    ]
    if kind == "villain":
        nxt = action_table(db, res, "next")
        keys = ("fold", "call", "raise") if res.ctx.typ != CHECK else ("bet", "check")
        stats = [head[0], head[3], *_best(res, nxt, keys, "next"), *tail]
    else:
        middle: list[dict] = []
        if kind in ("hero_raise", "hero_bet"):
            faced = action_table(db, res, "faced")
            raise_key = next((k for k in ("villain_3bet", "villain_squeeze", "villain_raise")
                              if any(kk == k for (_s, kk) in faced)), "villain_raise")
            middle = _best(res, faced, ("all_fold", "one_call", raise_key), "faced")
        elif kind in ("hero_call", "hero_check"):
            faced = action_table(db, res, "faced")
            middle = _best(res, faced, ("villain_bet", "villains_check"), "faced")
        ap = [
            _stat("ap_bbs", "Action Profit, bbs", v["ap_bbs"], "bb", v["hands"], winnings=True),
            _stat("ap_bbh", "Action Profit, bb/hand", v["ap_bbh"], "bbh", v["hands"],
                  winnings=True),
        ]
        sd = [
            _stat("wtsd", "WTSD", v["wtsd"], "pct", v["hands"]),
            _stat("wsd", "W%SD", v["wsd"], "pct", v["sd_hands"]),
        ]
        stats = [*head, *middle, *ap, *tail, *sd]
    return {"hands": len(cases), "kind": kind, "hit_label": hit_label, "stats": stats}


def _combos(cls: str) -> int:
    return 6 if len(cls) == 2 else 4 if cls.endswith("s") else 12


def preflop_range(res: Resolution) -> dict:
    counts = {c: 0 for c in CLASSES}
    won = {c: 0.0 for c in CLASSES}
    total = 0
    for h in res.cases:
        cls = card_class(h.card1, h.card2)
        if cls is None:
            continue
        counts[cls] += 1
        won[cls] += h.won_bb
        total += 1
    dens = [counts[c] / _combos(c) for c in CLASSES if counts[c]]
    avg = sum(dens) / len(dens) if dens else 0.0
    cells = []
    for c in CLASSES:
        n = counts[c]
        level = 0
        if n and avg:
            ratio = n / _combos(c) / avg
            level = 0 if ratio <= 0.4 else 1 if ratio <= 0.8 else 2 if ratio <= 3 else 3
        cells.append({"cls": c, "hands": n, "won_bb": won[c], "level": level})
    return {"total": total, "cells": cells}


def hand_strength(res: Resolution, street: str) -> dict:
    si = {"flop": 0, "turn": 1, "river": 2}[street]
    counts: dict[int, int] = {}
    won: dict[int, float] = {}
    for h in res.cases:
        idx = h.hv[si]
        if idx is None:
            continue
        idx = int(idx)
        counts[idx] = counts.get(idx, 0) + 1
        won[idx] = won.get(idx, 0.0) + h.won_bb
    known = sum(counts.values())
    indices = list(range(len(STREET_CATEGORIES[street])))
    if counts.get(OTHER):
        indices.append(OTHER)
    rows = []
    for i in indices:
        info = category_info(street, i)
        n = counts.get(i, 0)
        rows.append({"key": info["key"], "label": info["label"], "hands": n,
                     "pct": n / known * 100.0 if known else 0.0, "won_bb": won.get(i, 0.0),
                     "weak": bool(info["weak"])})
    return {"street": street, "known": known, "rows": rows}


QUICK_FILTER_KEYS = (
    "P01", "P02", "P06", "P07", "P03", "P13", "P19", "P20", "P21", "P24", "P22", "P23",
    "C01", "M01", "C04", "C07", "C08", "C12", "N01", "C02", "C05", "C03", "C06",
)


def quick_filters() -> list[dict]:
    return [{"key": k, "label": spots.ROW_SPOTS[k][0], "group": ROWS[k].street}
            for k in QUICK_FILTER_KEYS]


__all__ = ["spot", "preflop_range", "hand_strength", "quick_filters"]
