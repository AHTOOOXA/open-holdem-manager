"""Import hands from another tracker's PostgreSQL database (PokerTracker 4, Holdem Manager 3)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from datetime import date, timedelta

from app.api.import_hands import _stream_import, import_date_filter
from app.importers import tracker_db
from app.parsers import detect_parser

router = APIRouter()


class TrackerDatabase(BaseModel):
    name: str
    hands: int


class TrackerDatabasesResponse(BaseModel):
    software: str
    databases: list[TrackerDatabase]
    error: str | None = None


class TrackerImportRequest(BaseModel):
    software: str
    database: str
    host: str | None = None
    port: int | None = None
    user: str | None = None
    password: str | None = None


def _conn(software, host, port, user, password):
    try:
        return tracker_db.make_connection(software, host, port, user, password)
    except tracker_db.TrackerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/import/tracker/databases", response_model=TrackerDatabasesResponse)
def list_tracker_databases(software: str, host: str | None = None, port: int | None = None,
                           user: str | None = None, password: str | None = None):
    conn = _conn(software, host, port, user, password)
    dbs, error = tracker_db.list_databases(software, conn)
    return TrackerDatabasesResponse(software=software, databases=[TrackerDatabase(**d) for d in dbs], error=error)


@router.post("/import/tracker")
def import_tracker_database(req: TrackerImportRequest, workspace_id: int = 1,
                            date_from: str | None = None, date_to: str | None = None):
    """Import the hands of one tracker database, streaming NDJSON like file import."""
    import_date_filter(date_from, date_to)  # 400 on a bad range before touching the source
    # The SQL pre-filter works on calendar days; widen it by a day each side so the exact
    # bounds (with the day-start hour) are applied by _stream_import, which also counts out_of_range.
    sql_from = _shift_day(date_from, -1)
    sql_to = _shift_day(date_to, 1)
    conn = _conn(req.software, req.host, req.port, req.user, req.password)
    try:
        texts = list(tracker_db.iter_hand_texts(req.software, conn, req.database, sql_from, sql_to))
    except tracker_db.TrackerError as e:
        raise HTTPException(status_code=400, detail=str(e))

    by_parser: dict = {}
    unsupported: list[str] = []
    for text in texts:
        parser = detect_parser(text[:500])
        if parser is None:
            unsupported.append(f"Unsupported site: {text.splitlines()[0][:80]}")
        else:
            by_parser.setdefault(parser, []).append(text)

    all_hands = [t for hands in by_parser.values() for t in hands]
    hand_parsers = [p for p, hands in by_parser.items() for _ in hands]
    return _stream_import(all_hands, hand_parsers, 1, workspace_id, pre_errors=unsupported,
                          date_from=date_from, date_to=date_to)


def _shift_day(day: str | None, delta: int) -> str | None:
    if not day:
        return day
    return (date.fromisoformat(day[:10]) + timedelta(days=delta)).isoformat()
