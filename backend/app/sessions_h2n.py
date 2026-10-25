"""Sessions as Hand2Note builds them (contract: frontend/src/lib/sessions/types.ts).

Rule (own words of Hand2Note's behaviour):

- every hand covers [start, start + 180 s] (GG histories have no end time, so every OHM
  site gets the 180 s estimate);
- hands sorted by start (ties by hand id) are walked keeping the current session's
  [start, end]; a hand **joins** when its start is strictly less than end + max break, and
  the end becomes max(end, hand end); otherwise it opens a new session;
- max break = app setting ``session_max_break_minutes`` (default 10). With the 180 s
  estimate a gap of >= 13 min between consecutive starts opens a new session;
- session end = last start + 180 s, duration = end - start.

Sessions are built over ALL of the player's hands in the workspace (every stake, site,
table) that the Reports / General screens count (``COALESCE(hp.h2n_valid, TRUE)``), so a
session page (chain ``[{k: 'session', start, end: last_hand_at}]``) shows exactly the
session's hands.

Clock: ``hands.played_at`` is the naive wall-clock time written in the hand history (GG
writes no zone; OHM treats it as local time everywhere: date filters, the hour step, the
hands list). "Live" therefore compares against the naive local ``datetime.now()``.

Time stats of a hand set (Reports recipes and the Tables split, sessions.md §4.9-10):

- Duration = the hands grouped by the session rule above, summed spans (one session's
  hands: exactly the session's duration; a table's hands: its played spans without the
  breaks between them);
- Hands / h = hands / played hours, played time = distinct 90 s slots marked by the hands'
  [start, start + 180 s) intervals x 90 s (slots aligned on the epoch of the naive time);
- Avg. Tables = mean over the 90 s slots in which some hand started of the number of
  distinct table names that started a hand in that slot.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.date_filters import day_from_sql, day_to_sql

HAND_SECONDS = 180
SLOT_SECONDS = 90
_EPOCH = _dt.datetime(1970, 1, 1)

MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


@dataclass
class Session:
    start: _dt.datetime
    end: _dt.datetime
    last_start: _dt.datetime
    members: list = field(default_factory=list)  # keys of the session's hands, in order

    @property
    def duration_s(self) -> int:
        return int((self.end - self.start).total_seconds())


def split_sessions(hands: Iterable[tuple], max_break_s: int) -> list[Session]:
    """Reference rule. `hands` = (key, start[, end]) tuples; end defaults to start + 180 s.

    Hands without a start are skipped. Returns sessions in chronological order.
    """
    rows = [h for h in hands if h[1] is not None]
    rows.sort(key=lambda h: (h[1], h[0]))
    brk = _dt.timedelta(seconds=max_break_s)
    out: list[Session] = []
    cur: Session | None = None
    for h in rows:
        key, start = h[0], h[1]
        end = h[2] if len(h) > 2 and h[2] is not None else start + _dt.timedelta(seconds=HAND_SECONDS)
        if cur is not None and start < cur.end + brk:
            cur.end = max(cur.end, end)
            cur.last_start = start
            cur.members.append(key)
        else:
            cur = Session(start, end, start, [key])
            out.append(cur)
    return out


def epoch_s(t: _dt.datetime) -> int:
    """Seconds since 1970-01-01 of a naive datetime (calendar arithmetic, no zone)."""
    return int((t - _EPOCH).total_seconds())


def session_id(start: _dt.datetime) -> int:
    """Stable numeric session key: the start as epoch seconds (unique per player, since a
    player's sessions never overlap; unchanged by rebuilds and by later imports unless an
    earlier hand joins the session)."""
    return epoch_s(start)


def is_live(end: _dt.datetime, now: _dt.datetime, max_break_s: int,
            start: _dt.datetime | None = None) -> bool:
    """A session is live when it ended at most the max break ago. A session being played has
    end = last start + 180 s, so `end` may be up to 180 s ahead of `now`; anything further
    ahead (or a session starting after `now`) is not live (future-dated hands)."""
    if start is not None and start > now:
        return False
    ahead = (end - now).total_seconds()
    return ahead <= HAND_SECONDS and (now - end).total_seconds() <= max_break_s


def iso(t: _dt.datetime) -> str:
    return t.replace(microsecond=0).isoformat(timespec="seconds")


def caption(start: _dt.datetime, numeric: bool = False, now: _dt.datetime | None = None) -> str:
    """Row caption: "October 17, Friday 20:10" (year prefixed when not the current year),
    or "17-10-2026, 20:10" with the numeric date format."""
    hm = f"{start.hour:02d}:{start.minute:02d}"
    if numeric:
        return f"{start.day:02d}-{start.month:02d}-{start.year}, {hm}"
    text = f"{MONTHS[start.month - 1]} {start.day}, {WEEKDAYS[start.weekday()]} {hm}"
    now = now or _dt.datetime.now()
    return text if start.year == now.year else f"{start.year} {text}"


# ── time stats of a hand set ─────────────────────────────────────────────


@dataclass
class TimeStats:
    hands: int
    duration_s: int
    played_slots: int
    start_slots: int      # slots with at least one hand start
    table_slots: int      # sum over those slots of distinct tables started in them

    @property
    def played_s(self) -> int:
        return self.played_slots * SLOT_SECONDS

    @property
    def hands_per_hour(self) -> float | None:
        return self.hands / (self.played_s / 3600.0) if self.played_slots else None

    @property
    def avg_tables(self) -> float | None:
        return self.table_slots / self.start_slots if self.start_slots else None

    def merge(self, o: "TimeStats") -> "TimeStats":
        """Summary-row merge: raw values add up (Hands / h = summed hands / summed time)."""
        return TimeStats(self.hands + o.hands, self.duration_s + o.duration_s,
                         self.played_slots + o.played_slots, self.start_slots + o.start_slots,
                         self.table_slots + o.table_slots)


EMPTY_TIME = TimeStats(0, 0, 0, 0, 0)


def time_stats(starts: Sequence[_dt.datetime], tables: Sequence[str | None] | None,
               max_break_s: int) -> TimeStats:
    pts = [s for s in starts if s is not None]
    if not pts:
        return TimeStats(0, 0, 0, 0, 0)
    duration = sum(s.duration_s for s in split_sessions(((i, t) for i, t in enumerate(pts)),
                                                        max_break_s))
    played: set[int] = set()
    by_slot: dict[int, set] = {}
    for i, t in enumerate(starts):
        if t is None:
            continue
        e = epoch_s(t)
        # [e, e + 180) marks every slot it touches: 2 slots when aligned, else 3
        played.update(range(e // SLOT_SECONDS, (e + HAND_SECONDS - 1) // SLOT_SECONDS + 1))
        by_slot.setdefault(e // SLOT_SECONDS, set()).add(tables[i] if tables else None)
    return TimeStats(len(pts), duration, len(played), len(by_slot),
                     sum(len(v) for v in by_slot.values()))


# ── SQL build over a player's hands ──────────────────────────────────────

_HANDS_CTE = """
WITH hh AS (
    SELECT h.id AS hid, h.played_at AS s, h.played_at + INTERVAL 180 SECOND AS e,
           COALESCE(hp.won, 0) AS won, COALESCE(hp.won_bb, 0) AS won_bb,
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) AS ev_bb,
           COALESCE(hp.all_in_ev_bb, hp.won_bb, 0) * h.bb_amount AS ev,
           ({in_range}) AS inr
    FROM hand_players hp
    JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
    WHERE hp.player_id = ? AND h.workspace_id = ? AND COALESCE(hp.h2n_valid, TRUE)
      AND h.played_at IS NOT NULL
),
m AS (
    -- The running MAX(e) over the earlier rows is the previous row's e: every hand ends at
    -- its start + 180 s (above) and the rows are in start order. This relies on that fixed
    -- end; split_sessions() accepts explicit ends, this SQL does not.
    SELECT *, LAG(e) OVER (ORDER BY s, hid) AS prev_end
    FROM hh
),
g AS (
    SELECT *, SUM(CASE WHEN prev_end IS NULL OR s >= prev_end + to_seconds(?) THEN 1 ELSE 0 END)
              OVER (ORDER BY s, hid ROWS UNBOUNDED PRECEDING) AS sn
    FROM m
)
"""


@dataclass
class SessionRow:
    number: int
    start: _dt.datetime
    last_start: _dt.datetime
    end: _dt.datetime
    total_hands: int
    hands: int          # in-range hands
    won: float
    won_ev: float
    won_bb: float
    won_ev_bb: float

    @property
    def id(self) -> int:
        return session_id(self.start)

    @property
    def duration_s(self) -> int:
        return int((self.end - self.start).total_seconds())


def build_sessions(db, workspace_id: int, player_id: int, max_break_s: int,
                   date_from: _dt.date | None = None, date_to: _dt.date | None = None,
                   day_start: int = 0) -> list[SessionRow]:
    """Every session of the player, chronological, with in-range sums (all hands without a
    date range). Sessions without in-range hands are kept (hands = 0); callers drop them."""
    cond: list[str] = []
    params: list = []
    if date_from is not None:
        cond.append(day_from_sql(day_start))
        params.append(date_from.isoformat())
    if date_to is not None:
        cond.append(day_to_sql(day_start))
        params.append(date_to.isoformat())
    sql = _HANDS_CTE.format(in_range=" AND ".join(cond) or "TRUE") + """
        SELECT sn, MIN(s), MAX(s), MAX(e), COUNT(*),
               COUNT(*) FILTER (WHERE inr),
               COALESCE(SUM(won) FILTER (WHERE inr), 0),
               COALESCE(SUM(ev) FILTER (WHERE inr), 0),
               COALESCE(SUM(won_bb) FILTER (WHERE inr), 0),
               COALESCE(SUM(ev_bb) FILTER (WHERE inr), 0)
        FROM g GROUP BY sn ORDER BY sn
    """
    rows = db.execute(sql, [*params, player_id, workspace_id, max_break_s]).fetchall()
    return [SessionRow(int(r[0]), r[1], r[2], r[3], int(r[4]), int(r[5]), float(r[6]),
                       float(r[7]), float(r[8]), float(r[9])) for r in rows]


__all__ = ["HAND_SECONDS", "SLOT_SECONDS", "Session", "SessionRow", "split_sessions",
           "build_sessions", "is_live", "caption", "iso", "session_id", "time_stats",
           "TimeStats", "EMPTY_TIME", "epoch_s"]
