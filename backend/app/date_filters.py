"""Shared SQL fragments for date range filters.

`date_to` arrives as a calendar date ("YYYY-MM-DD"). Comparing a TIMESTAMP
column with `<= '2026-10-15'` means `<= 2026-10-15 00:00:00`, which drops
every hand played later that day. Compare against the start of the next day.
"""

# Inclusive end-of-day bound for hands.played_at. Takes one `?` param (date_to).
DATE_TO_SQL = "h.played_at < CAST(? AS DATE) + INTERVAL 1 DAY"


def day_from_sql(day_start: int = 0) -> str:
    """Lower bound of a calendar day D = [D day_start:00, D+1 day_start:00). One `?` (date)."""
    h = int(day_start)
    return "h.played_at >= CAST(? AS DATE)" + (f" + INTERVAL {h} HOUR" if h else "")


def day_to_sql(day_start: int = 0) -> str:
    """Exclusive upper bound of the day `date_to` (inclusive local day). One `?` (date)."""
    h = int(day_start)
    return "h.played_at < CAST(? AS DATE) + INTERVAL 1 DAY" + (f" + INTERVAL {h} HOUR" if h else "")


def bound_sql(kind: str, value: str, day_start: int = 0) -> tuple[str, str]:
    """(sql, param) of a `date_from` / `date_to` request bound on hands.played_at.

    A plain date (YYYY-MM-DD) is a calendar day shifted by `day_start` (see day_from_sql);
    a value with a time part (checkpoint) is used as-is: from = `>=`, to = `<=`.
    """
    if len(value) <= 10:
        return (day_from_sql(day_start) if kind == "from" else day_to_sql(day_start)), value
    op = ">=" if kind == "from" else "<="
    return f"h.played_at {op} CAST(? AS TIMESTAMP)", value


def bound_datetime(kind: str, value: str, day_start: int = 0):
    """Python twin of bound_sql: (bound, inclusive) for a `date_from` / `date_to` value.

    A plain date D gives from = D day_start:00 (inclusive) and to = D+1 day_start:00
    (exclusive); a value with a time part is used as-is and is inclusive both ways.
    Raises ValueError on a malformed value.
    """
    from datetime import date, datetime, timedelta
    value = value.strip()
    if len(value) <= 10:
        d = date.fromisoformat(value)
        start = datetime(d.year, d.month, d.day) + timedelta(hours=int(day_start))
        return (start, True) if kind == "from" else (start + timedelta(days=1), False)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=None), True


def played_at_filter(date_from: str | None, date_to: str | None, day_start: int = 0):
    """Predicate on a hand's played_at for an inclusive date range (None = no bound).

    Same day semantics as day_from_sql / day_to_sql. Returns None when both bounds are
    empty (every hand passes). Raises ValueError on a malformed date or from > to.
    """
    lo = bound_datetime("from", date_from, day_start) if date_from else None
    hi = bound_datetime("to", date_to, day_start) if date_to else None
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None and (hi[0] < lo[0] or (hi[0] == lo[0] and not hi[1])):
        raise ValueError("date_from is after date_to")

    def in_range(played_at) -> bool:
        if played_at is None:
            return True
        if played_at.tzinfo is not None:
            played_at = played_at.replace(tzinfo=None)
        if lo is not None and played_at < lo[0]:
            return False
        if hi is not None and (played_at > hi[0] or (played_at == hi[0] and not hi[1])):
            return False
        return True

    return in_range
