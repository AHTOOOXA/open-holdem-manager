import pytest
import duckdb

from app.api.import_hands import reset_import_cache
from app.db import init_schema
from app.heroes import invalidate_hero_cache


@pytest.fixture
def db():
    """In-memory DuckDB with full schema, fresh for each test."""
    reset_import_cache()
    invalidate_hero_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    # Synthetic test hands have no dealt cards, so nothing is auto-detected:
    # keep the historical default hero (Hero on GG) as a manual account.
    conn.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) VALUES (1, 1, 'Hero', 'manual')")
    yield conn
    conn.close()
