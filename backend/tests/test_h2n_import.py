"""Import from a Hand2Note 4 database (app/parsers/h2n_db.py, api/import_h2n.py).

The fixture databases are written by _write_h2n_db() below in the same on-disk
layout, from our own fixture hand histories.
"""

import json
import struct
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.main import app
from app.parsers import ggpoker, h2n_db, pokerstars

FIXTURES = Path(__file__).parent / "fixtures"


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _write_h2n_db(db_dir: Path, texts: list[str], *, version="4.1.226", store_texts=True) -> Path:
    """Write texts as a Hand2Note 4 database: hand ids start at 1, and each
    record has a dummy payload where H2N keeps its own hand structure."""
    hands = db_dir / "hands"
    hands.mkdir(parents=True)
    (hands / "version").write_text(version)
    data = bytearray()
    index = [0]  # hand id 0 is never used
    for hand_id, text in enumerate(texts, start=1):
        index.append(len(data) + 1)
        payload = b"\x01\x02\x03" * hand_id  # varying length
        data += struct.pack("<i", hand_id) + _varint(len(payload)) + payload
        if store_texts:
            raw = text.strip().replace("\n", "\x00").encode("utf-8")
            data += _varint(len(raw)) + raw
    (hands / "hands.data").write_bytes(bytes(data))
    (hands / "hands.data.index").write_bytes(struct.pack(f"<{len(index)}q", *index))
    return db_dir


def _gg_hands() -> list[str]:
    text = (FIXTURES / "ggpoker" / "sample.txt").read_text()
    hands = [h.strip() for h in ggpoker.split_hands(text) if h.strip()]
    return hands + [(FIXTURES / "ggpoker" / "ante_table.txt").read_text().strip()]


def _ps_hands() -> list[str]:
    text = (FIXTURES / "pokerstars" / "zoom.txt").read_text(encoding="utf-8-sig")
    return [h.strip() for h in pokerstars.split_hands(text) if h.strip()]


def test_reads_back_original_texts(tmp_path):
    hands = _gg_hands()
    db = _write_h2n_db(tmp_path / "My DB", hands)
    assert list(h2n_db.iter_hand_texts(db)) == hands
    assert h2n_db.count_hands(db) == len(hands)


def test_list_databases(tmp_path):
    _write_h2n_db(tmp_path / "A", _gg_hands())
    (tmp_path / "not a db").mkdir()
    dbs = h2n_db.list_databases(tmp_path)
    assert [(d["name"], d["hands"], d["version"]) for d in dbs] == [("A", len(_gg_hands()), "4.1.226")]
    assert h2n_db.list_databases(tmp_path / "missing") == []


def test_rejects_other_versions(tmp_path):
    db = _write_h2n_db(tmp_path / "old", _gg_hands(), version="3.2.1")
    with pytest.raises(h2n_db.H2NFormatError, match="version"):
        list(h2n_db.iter_hand_texts(db))


def test_rejects_database_without_texts(tmp_path):
    db = _write_h2n_db(tmp_path / "notext", _gg_hands(), store_texts=False)
    with pytest.raises(h2n_db.H2NFormatError, match="doesn't store"):
        list(h2n_db.iter_hand_texts(db))


def test_rejects_non_database(tmp_path):
    with pytest.raises(h2n_db.H2NFormatError):
        list(h2n_db.iter_hand_texts(tmp_path))


def test_repairs_amount_split_by_nul_corruption():
    """GG files sometimes have NUL instead of '.', which H2N's copy turns into
    a line break in the middle of an amount."""
    raw = "Seat 1: 9dbbeae3 ($15\x0096 in chips)\x00Seat 2: Hero ($10 in chips)\x00Hero: bets $2\x0084f3ce13: calls $2"
    assert h2n_db._to_lines(raw) == (
        "Seat 1: 9dbbeae3 ($15.96 in chips)\nSeat 2: Hero ($10 in chips)\n"
        "Hero: bets $2\n84f3ce13: calls $2"
    )


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _stream(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def test_import_endpoint_mixed_sites(client, db, tmp_path):
    gg, ps = _gg_hands(), _ps_hands()
    # Interleave sites: the endpoint must group them before chunked parsing
    mixed = [h for pair in zip(gg, ps) for h in pair] + gg[len(ps):] + ps[len(gg):]
    mixed.append("Some Other Site Hand #1: not a hand we can parse")
    db_dir = _write_h2n_db(tmp_path / "H2N", mixed)

    msgs = _stream(client.post("/api/import/h2n", json={"path": str(db_dir)}))
    done = msgs[-1]
    assert done["type"] == "done", done
    assert done["imported"] == len(gg) + len(ps)
    assert done["errors"] == 1
    sites = dict(db.execute("SELECT site_id, COUNT(*) FROM hands GROUP BY 1").fetchall())
    assert sites == {ggpoker.SITE_ID: len(gg), pokerstars.SITE_ID: len(ps)}

    # Same hands again: all duplicates
    again = _stream(client.post("/api/import/h2n", json={"path": str(db_dir)}))[-1]
    assert again["imported"] == 0 and again["duplicates"] == len(gg) + len(ps)


def test_import_endpoint_same_result_as_file_import(client, db, tmp_path):
    """A hand imported from H2N ends up exactly like the same hand imported from a file."""
    hands = _gg_hands()
    db_dir = _write_h2n_db(tmp_path / "H2N", hands)
    _stream(client.post("/api/import/h2n", json={"path": str(db_dir)}))
    cols = "hand_id, player_id, position, won, rake, all_in_ev_bb, vpip, pfr, three_bet, cbet_flop"
    from_h2n = db.execute(f"SELECT {cols} FROM hand_players ORDER BY 1, 2").fetchall()

    db.execute("DELETE FROM hand_players"); db.execute("DELETE FROM board_cards"); db.execute("DELETE FROM hands")
    from app.api.import_hands import reset_import_cache
    reset_import_cache()
    files = {"files": ("hands.txt", "\n\n\n".join(hands).encode(), "text/plain")}
    _stream(client.post("/api/import/files/stream", files=files))
    from_file = db.execute(f"SELECT {cols} FROM hand_players ORDER BY 1, 2").fetchall()
    assert from_h2n == from_file


def test_import_endpoint_bad_path(client, tmp_path):
    resp = client.post("/api/import/h2n", json={"path": str(tmp_path / "nope")})
    assert resp.status_code == 400
    assert "Not a Hand2Note database" in resp.json()["detail"]


def test_databases_endpoint(client, tmp_path):
    _write_h2n_db(tmp_path / "Mine", _gg_hands())
    body = client.get("/api/import/h2n/databases", params={"root": str(tmp_path)}).json()
    assert body["root"] == str(tmp_path)
    assert [d["name"] for d in body["databases"]] == ["Mine"]


def test_file_upload_with_two_sites_parses_each_with_its_own_parser(client, db):
    """Chunks used the parser of their first hand, so a small GG file uploaded
    together with a PokerStars file sent the PokerStars hands to the GG parser."""
    gg, ps = _gg_hands(), _ps_hands()
    files = [
        ("files", ("gg.txt", "\n\n\n".join(gg).encode(), "text/plain")),
        ("files", ("ps.txt", "\n\n\n\n".join(ps).encode(), "text/plain")),
    ]
    done = _stream(client.post("/api/import/files/stream", files=files))[-1]
    assert done["errors"] == 0, done["error_details"]
    assert done["imported"] == len(gg) + len(ps)
