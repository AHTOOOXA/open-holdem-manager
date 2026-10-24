import hmac
import os
from pathlib import Path as _Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.formparsers import MultiPartParser
from starlette.middleware.base import BaseHTTPMiddleware

from app.db import (
    get_db, close_db, get_read_cursor, get_rebuild_status, get_wal_recovery,
    init_request_cursors, cleanup_request_cursors, request_shutdown,
)
from app.api import import_hands, import_h2n, stats, reports, settings, hands, cash_drop, sessions, players, population, workspaces, checkpoints, compare, identities
from app.api import general
from app.api import general_popup
from app.api import reports_lite
from app.api import statistics_dashboards
from app.api import heroes as heroes_api
from app.api import app_settings as app_settings_api
from app.api import config as config_api
from app.api import marked_hands as marked_hands_api

MultiPartParser.max_part_size = 50 * 1024 * 1024  # 50MB

app = FastAPI(title="Open Holdem Manager", version="0.1.0")

if not os.environ.get("OHM_STATIC_DIR"):
    # Dev mode: frontend on :4242, API on :4243 — need CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4242"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

class CursorCleanupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        init_request_cursors()
        try:
            response = await call_next(request)
            return response
        finally:
            cleanup_request_cursors()


app.add_middleware(CursorCleanupMiddleware)

app.include_router(import_hands.router, prefix="/api")
app.include_router(import_h2n.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(hands.router, prefix="/api")
app.include_router(cash_drop.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(players.router, prefix="/api")
app.include_router(population.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api", tags=["workspaces"])
app.include_router(checkpoints.router, prefix="/api", tags=["checkpoints"])
app.include_router(compare.router, prefix="/api", tags=["compare"])
app.include_router(identities.router, prefix="/api", tags=["identities"])
app.include_router(general.router, prefix="/api", tags=["general"])
app.include_router(general_popup.router, prefix="/api", tags=["general"])
app.include_router(reports_lite.router, prefix="/api", tags=["reports"])
app.include_router(statistics_dashboards.router, prefix="/api", tags=["statistics"])
app.include_router(heroes_api.router, prefix="/api", tags=["heroes"])
app.include_router(app_settings_api.router, prefix="/api", tags=["settings"])
app.include_router(config_api.router, prefix="/api", tags=["config"])
app.include_router(marked_hands_api.router, prefix="/api", tags=["marked-hands"])


@app.on_event("startup")
def startup():
    get_db()


@app.on_event("shutdown")
def shutdown():
    # Stop any running import/rebuild (it rolls back) so the lock frees up,
    # then checkpoint and close.
    request_shutdown()
    close_db()


@app.post("/api/shutdown")
def shutdown_server(x_ohm_shutdown_token: str | None = Header(default=None)):
    """Graceful exit for the packaged app.

    Electron calls this on quit instead of killing the process: a hard kill
    (TerminateProcess on Windows) skips close_db() and can leave a WAL that
    fails to replay. The token comes from Electron via OHM_SHUTDOWN_TOKEN;
    the custom header also means a web page can't trigger this cross-origin.
    """
    expected = os.environ.get("OHM_SHUTDOWN_TOKEN")
    if not expected or not x_ohm_shutdown_token or not hmac.compare_digest(
        expected, x_ohm_shutdown_token
    ):
        raise HTTPException(status_code=403, detail="Forbidden")
    request_shutdown()
    server = getattr(app.state, "server", None)
    if server is not None:
        server.should_exit = True
    return {"status": "shutting_down"}


@app.get("/api/health")
def health(workspace_id: int = 1):
    rebuild = get_rebuild_status()
    if rebuild["active"]:
        # Skip DB query during rebuild — the write transaction blocks read cursors
        return {
            "status": "ok",
            "hands": rebuild["total"],
            "rebuilding": True,
            "rebuild_required": False,
            "rebuild_progress": {
                "processed": rebuild["processed"],
                "total": rebuild["total"],
            },
        }
    try:
        row = get_read_cursor().execute(
            "SELECT COUNT(*) FROM hands WHERE workspace_id = ?", [workspace_id]
        ).fetchone()
        hand_count = row[0] if row else 0
    except Exception:
        hand_count = 0
    try:
        from app.config_sections import rebuild_required
        needs_rebuild = rebuild_required(get_read_cursor())
    except Exception:
        needs_rebuild = False
    resp = {"status": "ok", "hands": hand_count, "rebuilding": False, "rebuild_required": needs_rebuild}
    wal_recovery = get_wal_recovery()
    if wal_recovery:
        resp["wal_recovery"] = wal_recovery
    return resp


# Serve built frontend in packaged mode (OHM_STATIC_DIR set by Electron)
_static_dir = os.environ.get("OHM_STATIC_DIR")
if _static_dir and _Path(_static_dir).is_dir():
    _static_path = _Path(_static_dir)
    _assets_path = _static_path / "assets"
    if _assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_path)), name="static-assets")

    @app.get("/{full_path:path}")
    async def _serve_spa(full_path: str):
        """SPA fallback: serve the file if it exists, otherwise index.html."""
        if full_path and ".." not in full_path:
            file_path = _static_path / full_path
            if file_path.is_file():
                return FileResponse(str(file_path))
        return FileResponse(str(_static_path / "index.html"))
