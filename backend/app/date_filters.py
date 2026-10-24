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
