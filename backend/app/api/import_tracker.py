"""Import hands from another tracker's PostgreSQL database (PokerTracker 4, Holdem Manager 3).

The connection settings (password included) travel in JSON bodies only, never in a URL,
so they can't end up in an access log.
"""

import threading
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.import_hands import _stream_source, import_date_filter
from app.importers import tracker_db
from app.parsers import detect_parser

router = APIRouter()

# Listing opens a connection per database on the server: at most this many at once
MAX_CONCURRENT_LISTINGS = 2
_listings = threading.BoundedSemaphore(MAX_CONCURRENT_LISTINGS)


class TrackerDatabase(BaseModel):
    name: str
    hands: int


class TrackerDatabasesResponse(BaseModel):
    software: str
    databases: list[TrackerDatabase]
    error: str | None = None


class TrackerConnectionRequest(BaseModel):
    """Blank fields (missing, null or "") mean the stock default."""
    software: str
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None


class TrackerImportRequest(TrackerConnectionRequest):
    database: str


def _conn(req: TrackerConnectionRequest):
    try:
        return tracker_db.make_connection(req.software, req.host, req.port, req.user, req.password)
    except tracker_db.TrackerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/tracker/databases", response_model=TrackerDatabasesResponse)
def list_tracker_databases(req: TrackerConnectionRequest):
    conn = _conn(req)
    if not _listings.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Already looking for databases, try again in a moment")
    try:
        dbs, error = tracker_db.list_databases(req.software, conn)
    finally:
        _listings.release()
    return TrackerDatabasesResponse(software=req.software, databases=[TrackerDatabase(**d) for d in dbs], error=error)


@router.post("/import/tracker")
def import_tracker_database(req: TrackerImportRequest, workspace_id: int = 1,
                            date_from: str | None = None, date_to: str | None = None):
    """Import the hands of one tracker database, streaming NDJSON like file import.

    The connection, the database and the date range are checked first (400 with a readable
    detail); the hands are then read in batches inside the import worker, after the start
    line, so the job can be cancelled while reading."""
    import_date_filter(date_from, date_to)  # 400 on a bad range before touching the source
    # The SQL pre-filter works on calendar days; widen it by a day each side so the exact
    # bounds (with the day-start hour) are applied by the import, which also counts out_of_range.
    sql_from = _shift_day(date_from, -1)
    sql_to = _shift_day(date_to, 1)
    conn = _conn(req)
    try:
        total = tracker_db.count_source(req.software, conn, req.database, sql_from, sql_to)
    except tracker_db.TrackerError as e:
        raise HTTPException(status_code=400, detail=str(e))

    def open_batches():
        texts = tracker_db.iter_hand_batches(req.software, conn, req.database, sql_from, sql_to)
        try:
            for batch in texts:
                yield [(t, detect_parser(t[:500])) for t in batch]
        finally:
            texts.close()  # closes the tracker connection (import worker thread)

    return _stream_source(open_batches, total, 1, workspace_id,
                          date_from=date_from, date_to=date_to)


def _shift_day(day: str | None, delta: int) -> str | None:
    if not day:
        return day
    return (date.fromisoformat(day[:10]) + timedelta(days=delta)).isoformat()
