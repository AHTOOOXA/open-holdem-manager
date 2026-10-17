"""Shared SQL fragments for date range filters.

`date_to` arrives as a calendar date ("YYYY-MM-DD"). Comparing a TIMESTAMP
column with `<= '2026-10-15'` means `<= 2026-10-15 00:00:00`, which drops
every hand played later that day. Compare against the start of the next day.
"""

# Inclusive end-of-day bound for hands.played_at. Takes one `?` param (date_to).
DATE_TO_SQL = "h.played_at < CAST(? AS DATE) + INTERVAL 1 DAY"
