from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.formparsers import MultiPartParser

from app.db import get_db
from app.api import import_hands, stats, reports, settings

MultiPartParser.max_part_size = 50 * 1024 * 1024  # 50MB

app = FastAPI(title="Open Holdem Manager", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(import_hands.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(settings.router, prefix="/api")


@app.on_event("startup")
def startup():
    get_db()


@app.get("/api/health")
def health():
    db = get_db()
    hand_count = db.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    return {"status": "ok", "hands": hand_count}
