"""Import hands from a Hand2Note 4 database (see app/parsers/h2n_db.py)."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.import_hands import _stream_import, import_date_filter
from app.parsers import detect_parser
from app.parsers import h2n_db

router = APIRouter()


class H2NDatabase(BaseModel):
    name: str
    path: str
    version: str
    hands: int


class H2NDatabasesResponse(BaseModel):
    root: str
    databases: list[H2NDatabase]


class H2NImportRequest(BaseModel):
    path: str


@router.get("/import/h2n/databases", response_model=H2NDatabasesResponse)
def list_h2n_databases(root: str | None = None):
    """Hand2Note databases in H2N's default folder (or under root)."""
    root_dir = Path(root).expanduser() if root else h2n_db.default_databases_dir()
    return H2NDatabasesResponse(
        root=str(root_dir),
        databases=[H2NDatabase(**d) for d in h2n_db.list_databases(root_dir)],
    )


@router.post("/import/h2n")
def import_h2n_database(
    req: H2NImportRequest,
    workspace_id: int = 1,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """Import every hand of a Hand2Note database folder. Streams NDJSON like file import."""
    db_dir = Path(req.path).expanduser()
    import_date_filter(date_from, date_to)  # 400 on a bad range before reading the DB
    try:
        texts = [t.strip() for t in h2n_db.iter_hand_texts(db_dir)]
    except (h2n_db.H2NFormatError, OSError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Group hands by site so parsing runs in as few chunks as possible
    by_parser: dict = {}
    unsupported: list[str] = []
    for text in texts:
        if not text:
            continue
        parser = detect_parser(text[:500])
        if parser is None:
            unsupported.append(f"Unsupported site: {text.splitlines()[0][:80]}")
        else:
            by_parser.setdefault(parser, []).append(text)

    all_hands = [t for hands in by_parser.values() for t in hands]
    hand_parsers = [p for p, hands in by_parser.items() for _ in hands]
    return _stream_import(
        all_hands, hand_parsers, 1, workspace_id, pre_errors=unsupported,
        date_from=date_from, date_to=date_to,
    )
