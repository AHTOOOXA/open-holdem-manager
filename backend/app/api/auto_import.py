"""GET /api/auto-import/status (contract: frontend/src/lib/import/types.ts section 2).

The config lives in the generic config store (GET/PUT/DELETE /api/config/auto_import)."""

from fastapi import APIRouter

from app import auto_import

router = APIRouter()


@router.get("/auto-import/status")
def auto_import_status() -> dict:
    """In-memory watcher status: no DB access, cheap to poll."""
    return auto_import.status()
