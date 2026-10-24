"""Import jobs (contract: frontend/src/lib/import/types.ts section 1): start line with a
job id, date range filtering with out_of_range, cancel between batches."""

import json
import threading
import time
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


def _gate_first_flush(monkeypatch):
    """The import worker waits after its first batch insert (`inside` set) until `go` is set."""
    go, inside = threading.Event(), threading.Event()
    real = ih._flush_batch
    calls = []

    def gated(*a, **k):
        out = real(*a, **k)
        calls.append(1)
        if len(calls) == 1:
            inside.set()
            go.wait(5)
        return out

    monkeypatch.setattr(ih, "_flush_batch", gated)
    return inside, go


def _lock_is_free() -> bool:
    """Acquire + release the write lock from a fresh thread (an RLock held by any other thread fails)."""
    got = []

    def probe():
        ok = app_db.db_lock().acquire(timeout=0.1)
        got.append(ok)
        if ok:
            app_db.db_lock().release()

    t = threading.Thread(target=probe)
    t.start()
    t.join()
    return got[0]


def test_cancel_mid_stream_keeps_written_hands(client, db, monkeypatch):
    monkeypatch.setattr(ih, "BATCH_SIZE", 2)
    inside, go = _gate_first_flush(monkeypatch)
    hands = _hands()
    gen = _generator(monkeypatch, hands)
    start = json.loads(next(gen))
    assert ih.active_import_jobs() == 1
    assert inside.wait(5)
    # The import worker holds the write lock: cancel must not need it
    assert client.post(f"/api/import/jobs/{start['job_id']}/cancel").status_code == 204
    go.set()
    first = json.loads(next(gen))
    assert first["type"] == "progress" and first["imported"] == 2
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
    assert _lock_is_free()


def test_each_next_on_a_different_thread(client, db, monkeypatch):
    """Starlette runs every next() of a sync generator in a threadpool thread, possibly a
    different one each time. The write lock (an RLock) must still be taken and released by
    one thread: the import worker, never the generator."""
    monkeypatch.setattr(ih, "BATCH_SIZE", 3)
    owners: list[tuple[str, str]] = []
    real_lock = app_db._lock

    class Recording:
        def acquire(self, *a, **k):
            ok = real_lock.acquire(*a, **k)
            if ok:
                owners.append(("acquire", threading.current_thread().name))
            return ok

        def release(self):
            owners.append(("release", threading.current_thread().name))
            real_lock.release()

        def __enter__(self):
            self.acquire()
            return self

        def __exit__(self, *exc):
            self.release()

    monkeypatch.setattr(app_db, "_lock", Recording())
    monkeypatch.setattr(ih, "db_lock", lambda: app_db._lock)
    gen = _generator(monkeypatch, _hands())
    lines, consumers = [], set()

    def step():
        consumers.add(threading.current_thread().name)
        try:
            lines.append(json.loads(next(gen)))
        except StopIteration:
            lines.append(None)

    while not lines or lines[-1] is not None:
        t = threading.Thread(target=step, name=f"consumer-{len(lines)}")  # a fresh thread per next()
        t.start()
        t.join(10)
    msgs = lines[:-1]
    assert msgs[0]["type"] == "start" and msgs[-1]["type"] == "done", msgs[-1]
    assert msgs[-1]["imported"] == len(_hands()) == _hand_count(db)
    assert len(consumers) > 1
    assert [o for o, _ in owners] == ["acquire", "release"]
    assert owners[0][1] == owners[1][1] and owners[0][1].startswith("import-")
    monkeypatch.setattr(app_db, "_lock", real_lock)
    assert _lock_is_free()


def test_streaming_through_starlette_releases_the_lock(client, db):
    """The real StreamingResponse path (TestClient): the lock is free right after."""
    msgs = _lines(_upload(client, R1.read_text()))
    assert msgs[-1]["type"] == "done" and msgs[-1]["imported"] == len(_hands())
    assert _lock_is_free()
    # A second import is not blocked by a leaked lock
    again = _lines(_upload(client, R1.read_text()))[-1]
    assert again["type"] == "done" and again["duplicates"] == len(_hands())


def test_client_disconnect_cancels_and_releases(client, db, monkeypatch):
    monkeypatch.setattr(ih, "BATCH_SIZE", 2)
    inside, go = _gate_first_flush(monkeypatch)
    hands = _hands()
    gen = _generator(monkeypatch, hands)
    json.loads(next(gen))  # start line
    assert inside.wait(5)  # the worker is inside its first batch
    gen.close()  # what a client disconnect does to the response generator
    go.set()
    deadline = time.monotonic() + 5
    while ih.active_import_jobs() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert ih.active_import_jobs() == 0
    assert _lock_is_free()
    assert 0 < _hand_count(db) < len(hands)  # stopped after the batch in progress, kept it


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
