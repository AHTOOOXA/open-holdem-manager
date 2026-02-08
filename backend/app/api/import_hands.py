from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from app.models import ImportResult
from app.db import get_db
from app.parsers.ggpoker import parse_hand_history
import traceback
import zipfile
import io
import json

router = APIRouter()


def _read_uploads(files_data: list[tuple[str, bytes]]) -> list[str]:
    """Extract text contents from uploaded file data (handles .txt and .zip)."""
    text_contents: list[str] = []
    for fname, raw in files_data:
        if fname.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for name in zf.namelist():
                        if name.lower().endswith(".txt") and not name.startswith("__MACOSX"):
                            text_contents.append(
                                zf.read(name).decode("utf-8", errors="replace")
                            )
            except zipfile.BadZipFile:
                pass
        elif fname.endswith(".txt"):
            text_contents.append(raw.decode("utf-8", errors="replace"))
    return text_contents


@router.post("/import/files", response_model=ImportResult)
async def import_files(files: list[UploadFile] = File(...)):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    db = get_db()
    result = _process_hands(db, text_contents)
    return result


@router.post("/import/files/stream")
async def import_files_stream(files: list[UploadFile] = File(...)):
    files_data = [(f.filename or "", await f.read()) for f in files]
    text_contents = _read_uploads(files_data)

    # Pre-split all hands for total count
    all_hands: list[str] = []
    for content in text_contents:
        for h in split_hands(content):
            h = h.strip()
            if h:
                all_hands.append(h)

    total = len(all_hands)
    file_count = len(text_contents)

    def generate():
        yield json.dumps({
            "type": "start",
            "total_hands": total,
            "files": file_count,
        }) + "\n"

        db = get_db()
        imported = 0
        duplicates = 0
        errors = 0
        error_details: list[str] = []

        for i, hand_text in enumerate(all_hands):
            try:
                hand_id = extract_hand_id(hand_text)
                if hand_id is None:
                    errors += 1
                    error_details.append("Could not extract hand ID")
                    continue

                existing = db.execute(
                    "SELECT 1 FROM hands WHERE id = ?", [hand_id]
                ).fetchone()
                if existing:
                    duplicates += 1
                    continue

                db.execute("BEGIN TRANSACTION")
                try:
                    parse_hand_history(hand_text, db)
                    db.execute("COMMIT")
                    imported += 1
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            except Exception as e:
                errors += 1
                error_details.append(f"Hand parse error: {str(e)}")
                traceback.print_exc()

            # Send progress every 50 hands or on last hand
            if (i + 1) % 50 == 0 or i == total - 1:
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": duplicates,
                    "errors": errors,
                }) + "\n"

        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details[:20],
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _process_hands(db, text_contents: list[str]) -> ImportResult:
    """Process hands from text contents (non-streaming)."""
    total_imported = 0
    total_duplicates = 0
    total_errors = 0
    error_details: list[str] = []

    for content in text_contents:
        for hand_text in split_hands(content):
            hand_text = hand_text.strip()
            if not hand_text:
                continue
            try:
                hand_id = extract_hand_id(hand_text)
                if hand_id is None:
                    total_errors += 1
                    error_details.append("Could not extract hand ID from hand")
                    continue

                existing = db.execute(
                    "SELECT 1 FROM hands WHERE id = ?", [hand_id]
                ).fetchone()
                if existing:
                    total_duplicates += 1
                    continue

                db.execute("BEGIN TRANSACTION")
                try:
                    parse_hand_history(hand_text, db)
                    db.execute("COMMIT")
                    total_imported += 1
                except Exception:
                    db.execute("ROLLBACK")
                    raise
            except Exception as e:
                total_errors += 1
                error_details.append(f"Hand parse error: {str(e)}")
                traceback.print_exc()

    return ImportResult(
        imported=total_imported,
        duplicates=total_duplicates,
        errors=total_errors,
        error_details=error_details[:20],
    )


@router.post("/import/clear")
async def clear_hands():
    db = get_db()
    db.execute("DELETE FROM actions")
    db.execute("DELETE FROM board_cards")
    db.execute("DELETE FROM hand_players")
    db.execute("DELETE FROM hands")
    db.execute("DELETE FROM players")
    return {"status": "ok"}


def split_hands(content: str) -> list[str]:
    """Split a file with multiple hand histories into individual hands."""
    hands = []
    current: list[str] = []

    for line in content.split("\n"):
        if line.startswith("Poker Hand #") and current:
            hands.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        hands.append("\n".join(current))

    return hands


def extract_hand_id(hand_text: str) -> str | None:
    """Extract hand ID from the first line."""
    import re
    m = re.search(r"Poker Hand #(\w+):", hand_text)
    return m.group(1) if m else None
