from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from app.models import ImportResult
from app.db import get_db, db_lock
from app.parsers.ggpoker import parse_hand_history, reset_parser_cache, finalize_import
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

        # Pre-check duplicates in bulk
        all_ids = []
        for h in all_hands:
            hid = extract_hand_id(h)
            all_ids.append(hid)

        existing_ids: set[str] = set()
        valid_ids = [hid for hid in all_ids if hid is not None]
        if valid_ids:
            batch_size = 500
            for j in range(0, len(valid_ids), batch_size):
                batch = valid_ids[j:j + batch_size]
                placeholders = ",".join(["?"] * len(batch))
                rows = db.execute(
                    f"SELECT id FROM hands WHERE id IN ({placeholders})", batch
                ).fetchall()
                existing_ids.update(r[0] for r in rows)

        # Batch transactions
        BATCH_SIZE = 200
        db.execute("BEGIN TRANSACTION")
        batch_count = 0

        for i, hand_text in enumerate(all_hands):
            hid = all_ids[i]
            if hid is None:
                errors += 1
                error_details.append("Could not extract hand ID")
            elif hid in existing_ids:
                duplicates += 1
            else:
                try:
                    parse_hand_history(hand_text, db)
                    imported += 1
                    batch_count += 1
                    if batch_count >= BATCH_SIZE:
                        db.execute("COMMIT")
                        db.execute("BEGIN TRANSACTION")
                        batch_count = 0
                except Exception as e:
                    # Rollback failed batch, retry remaining individually
                    db.execute("ROLLBACK")
                    db.execute("BEGIN TRANSACTION")
                    batch_count = 0
                    errors += 1
                    error_details.append(f"Hand parse error: {str(e)}")

            if (i + 1) % 200 == 0 or i == total - 1:
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": duplicates,
                    "errors": errors,
                }) + "\n"

        db.execute("COMMIT")
        finalize_import(db)

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

    db.execute("BEGIN TRANSACTION")
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

                parse_hand_history(hand_text, db)
                total_imported += 1
            except Exception as e:
                total_errors += 1
                error_details.append(f"Hand parse error: {str(e)}")
                traceback.print_exc()
    db.execute("COMMIT")
    finalize_import(db)

    return ImportResult(
        imported=total_imported,
        duplicates=total_duplicates,
        errors=total_errors,
        error_details=error_details[:20],
    )


@router.post("/import/rebuild")
async def rebuild_hands():
    """Re-parse all hands from stored raw_text. Useful after parser/schema changes."""

    def generate():
        db = get_db()

        rows = db.execute(
            "SELECT id, raw_text FROM hands ORDER BY played_at ASC, id ASC"
        ).fetchall()
        total = len(rows)

        if total == 0:
            yield json.dumps({"type": "done", "imported": 0, "duplicates": 0, "errors": 0, "error_details": []}) + "\n"
            return

        yield json.dumps({"type": "start", "total_hands": total, "files": 0}) + "\n"

        hand_texts = [(hid, raw) for hid, raw in rows]

        # Wipe everything and reset caches
        db.execute("DELETE FROM actions")
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        db.execute("DELETE FROM hands")
        db.execute("DELETE FROM players")
        reset_parser_cache()

        imported = 0
        errors = 0
        error_details: list[str] = []
        BATCH_SIZE = 200

        db.execute("BEGIN TRANSACTION")
        batch_count = 0

        for i, (hand_id, raw_text) in enumerate(hand_texts):
            try:
                parse_hand_history(raw_text, db)
                imported += 1
                batch_count += 1
                if batch_count >= BATCH_SIZE:
                    db.execute("COMMIT")
                    db.execute("BEGIN TRANSACTION")
                    batch_count = 0
            except Exception as e:
                db.execute("ROLLBACK")
                db.execute("BEGIN TRANSACTION")
                batch_count = 0
                errors += 1
                error_details.append(f"{hand_id}: {str(e)}")
                traceback.print_exc()

            if (i + 1) % 200 == 0 or i == total - 1:
                yield json.dumps({
                    "type": "progress",
                    "processed": i + 1,
                    "total": total,
                    "imported": imported,
                    "duplicates": 0,
                    "errors": errors,
                }) + "\n"

        db.execute("COMMIT")
        finalize_import(db)

        yield json.dumps({
            "type": "done",
            "imported": imported,
            "duplicates": 0,
            "errors": errors,
            "error_details": error_details[:20],
        }) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.post("/import/clear")
async def clear_hands():
    with db_lock():
        db = get_db()
        db.execute("DELETE FROM actions")
        db.execute("DELETE FROM board_cards")
        db.execute("DELETE FROM hand_players")
        db.execute("DELETE FROM hands")
        db.execute("DELETE FROM players")
        reset_parser_cache()
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
