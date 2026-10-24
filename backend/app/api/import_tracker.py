"""Import hands from another tracker's PostgreSQL database (PokerTracker 4, Holdem Manager 3)."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.import_hands import _stream_import
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
    conn = _conn(req.software, req.host, req.port, req.user, req.password)
    try:
        texts = list(tracker_db.iter_hand_texts(req.software, conn, req.database, date_from, date_to))
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
    return _stream_import(all_hands, hand_parsers, 1, workspace_id, pre_errors=unsupported)
