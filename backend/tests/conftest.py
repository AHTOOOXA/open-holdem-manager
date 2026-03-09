import pytest
import duckdb

from app.api.import_hands import reset_import_cache
from app.db import init_schema


@pytest.fixture
def db():
    """In-memory DuckDB with full schema, fresh for each test."""
    reset_import_cache()
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    yield conn
    conn.close()
