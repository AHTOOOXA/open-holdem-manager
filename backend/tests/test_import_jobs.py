"""Import jobs (contract: frontend/src/lib/import/types.ts section 1): start line with a
job id, date range filtering with out_of_range, cancel between batches."""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.api.import_hands as ih
import app.db as app_db
from app.main import app
from app.parsers import ggpoker

FIXTURES = Path(__file__).parent / "fixtures"
R1 = FIXTURES / "ggpoker" / "h2n_parity_r1.txt"


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _hands() -> list[str]:
    return [h.strip() for h in ggpoker.split_hands(R1.read_text()) if h.strip()]


def _lines(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def _upload(client, text: str, **params):
    return client.post(
        "/api/import/files/stream", params=params,
        files=[("files", ("hh.txt", text.encode(), "text/plain"))],
    )


def _hand_count(db) -> int:
    return db.execute("SELECT COUNT(*) FROM hands").fetchone()[0]


def test_start_line_and_done_fields(client, db):
    msgs = _lines(_upload(client, R1.read_text()))
    start, done = msgs[0], msgs[-1]
    n = len(_hands())
    assert start["type"] == "start" and start["total"] == n and len(start["job_id"]) == 32
    assert done["type"] == "done" and done["imported"] == n
    assert done["out_of_range"] == 0 and done["cancelled"] is False
    assert all("out_of_range" in m for m in msgs if m["type"] == "progress")
    # The job is gone once the stream ended
    assert ih.active_import_jobs() == 0
    assert client.post(f"/api/import/jobs/{start['job_id']}/cancel").status_code == 404


def _expected_in_range(lo: datetime, hi: datetime) -> int:
    return sum(1 for h in _hands() if lo <= ggpoker.parse_hand_history(h).played_at < hi)


def test_date_range_counts_out_of_range(client, db):
    n = len(_hands())
    done = _lines(_upload(client, R1.read_text(), date_from="2026-01-09", date_to="2026-01-15"))[-1]
    want = _expected_in_range(datetime(2026, 1, 9), datetime(2026, 1, 16))
    assert 0 < want < n
    assert done["imported"] == want == _hand_count(db)
    assert done["out_of_range"] == n - want
    # Only the bound given applies
    db.execute("DELETE FROM hand_players"); db.execute("DELETE FROM board_cards"); db.execute("DELETE FROM hands")
    ih.reset_import_cache()
    done = _lines(_upload(client, R1.read_text(), date_from="2026-01-16"))[-1]
    assert done["imported"] == _expected_in_range(datetime(2026, 1, 16), datetime(2100, 1, 1))


def test_date_range_applies_day_start_hour(client, db):
    db.execute("INSERT OR REPLACE INTO settings VALUES ('day_start_hour', '6')")
    done = _lines(_upload(client, R1.read_text(), date_from="2026-01-09", date_to="2026-01-09"))[-1]
    # Day 2026-01-09 = [01-09 06:00, 01-10 06:00): includes the 01-10 03:02 hand
    want = _expected_in_range(datetime(2026, 1, 9, 6), datetime(2026, 1, 10, 6))
    assert done["imported"] == want
    ids = {r[0] for r in db.execute("SELECT id FROM hands").fetchall()}
    assert "RC4198732175" in ids  # 2026/01/10 03:02:55


def test_duplicates_do_not_count_as_out_of_range(client, db):
    _lines(_upload(client, R1.read_text()))
    done = _lines(_upload(client, R1.read_text(), date_from="2026-01-09", date_to="2026-01-09"))[-1]
    assert done["imported"] == 0 and done["duplicates"] == len(_hands()) and done["out_of_range"] == 0


@pytest.mark.parametrize("params", [{"date_from": "2026-13-01"}, {"date_to": "yesterday"},
                                    {"date_from": "2026-01-10", "date_to": "2026-01-09"}])
def test_bad_date_range_is_400(client, params):
    r = _upload(client, R1.read_text(), **params)
    assert r.status_code == 400 and "date" in r.json()["detail"].lower()
    assert ih.active_import_jobs() == 0


def test_h2n_import_takes_the_date_range(client, db, tmp_path):
    from tests.test_h2n_import import _write_h2n_db
    db_dir = _write_h2n_db(tmp_path / "H2N", _hands())
    r = client.post("/api/import/h2n", params={"date_from": "2026-01-09", "date_to": "2026-01-15"},
                    json={"path": str(db_dir)})
    done = _lines(r)[-1]
    want = _expected_in_range(datetime(2026, 1, 9), datetime(2026, 1, 16))
    assert done["imported"] == want and done["out_of_range"] == len(_hands()) - want
    assert client.post("/api/import/h2n", params={"date_to": "nope"},
                       json={"path": str(db_dir)}).status_code == 400


def _generator(monkeypatch, hands, workspace_id=1):
    """_stream_import's NDJSON generator, consumed in the test thread."""
    monkeypatch.setattr(ih, "StreamingResponse", lambda gen, media_type: gen)
    return ih._stream_import(hands, [ggpoker] * len(hands), 1, workspace_id)


def test_cancel_mid_stream_keeps_written_hands(client, db, monkeypatch):
    monkeypatch.setattr(ih, "BATCH_SIZE", 2)
    hands = _hands()
    gen = _generator(monkeypatch, hands)
    start = json.loads(next(gen))
    assert ih.active_import_jobs() == 1
    first = json.loads(next(gen))
    assert first["type"] == "progress" and first["imported"] == 2
    # The import thread (this one) holds the write lock: cancel must not need it
    assert client.post(f"/api/import/jobs/{start['job_id']}/cancel").status_code == 204
    rest = [json.loads(line) for line in gen]
    done = rest[-1]
    assert done["type"] == "done" and done["cancelled"] is True
    assert done["imported"] == 2 == _hand_count(db) < len(hands)
    assert all(m["type"] != "progress" for m in rest)  # stopped right after the batch
    # Finalisation ran: indexes are back, imported_at stamped
    idx = {r[0] for r in db.execute("SELECT index_name FROM duckdb_indexes()").fetchall()}
    assert "idx_hands_played_at" in idx
    assert db.execute("SELECT COUNT(*) FROM hands WHERE imported_at IS NULL").fetchone()[0] == 0
    assert ih.active_import_jobs() == 0
    assert client.post(f"/api/import/jobs/{start['job_id']}/cancel").status_code == 404


def test_cancel_while_waiting_for_the_lock(client, db, monkeypatch):
    held, release = threading.Event(), threading.Event()

    def hold():
        with app_db.db_lock():
            held.set()
            release.wait(5)

    t = threading.Thread(target=hold)
    t.start()
    held.wait(2)
    try:
        gen = _generator(monkeypatch, _hands())
        start = json.loads(next(gen))
        assert ih.cancel_job(start["job_id"])
        done = json.loads(next(gen))
        assert done["type"] == "done" and done["cancelled"] and done["imported"] == 0
        assert list(gen) == []
    finally:
        release.set()
        t.join()
    assert _hand_count(db) == 0 and ih.active_import_jobs() == 0


def test_cancel_unknown_job_is_404(client):
    assert client.post("/api/import/jobs/nope/cancel").status_code == 404
