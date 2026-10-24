"""Tag catalogue + marked hands (contract: frontend/src/lib/marked/types.ts)."""

import io
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import marked_hands as mh
from app.api.import_hands import insert_parsed_hand
from app.heroes import invalidate_hero_cache
from app.main import app
from app.parsers.ggpoker import parse_hand_history

FIXTURES = Path(__file__).parent / "fixtures" / "ggpoker"
SAMPLE = (FIXTURES / "sample.txt").read_text()
HANDS = [h.strip() for h in SAMPLE.split("\n\n\n") if h.strip()]
IDS = [f"HD123456789{i}" for i in range(5)]

DEFAULT_NAMES = ["mistake", "bluff", "cooler", "value", "study", "great play"]


def _load(db, workspace_id=1, hands=HANDS):
    for h in hands:
        insert_parsed_hand(db, parse_hand_history(h), workspace_id=workspace_id)


def _ws2(db):
    db.execute("INSERT INTO workspaces (id, name) VALUES (2, 'Two')")
    db.execute("INSERT INTO hero_accounts (workspace_id, site_id, username, source) "
               "VALUES (2, 1, 'Hero', 'manual')")
    invalidate_hero_cache()


def _pid(db, name):
    return db.execute("SELECT id FROM players WHERE username = ?", [name]).fetchone()[0]


@pytest.fixture
def client(db, monkeypatch):
    _load(db)
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _tags(client):
    r = client.get("/api/tag-defs")
    assert r.status_code == 200, r.text
    return r.json()


def _tid(client, name):
    return next(t["id"] for t in _tags(client) if t["name"] == name)


def _list(client, **params):
    r = client.get("/api/hands", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _ids(client, **params):
    return sorted(h["id"] for h in _list(client, per_page=200, **params)["hands"])


def _mark(client, hid, ws=1, **body):
    r = client.put(f"/api/hands/{hid}/mark", params={"workspace_id": ws}, json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ── migration ──────────────────────────────────────────────────────────────────────────────


def test_fresh_install_defaults(db):
    rows = mh.list_tags(db)
    assert [t["name"] for t in rows] == DEFAULT_NAMES
    assert [t["color"] for t in rows] == ["tag-7", "tag-5", "tag-4", "tag-3", "tag-2", "tag-9"]
    assert [t["position"] for t in rows] == list(range(6))
    # running again changes nothing
    mh.ensure_schema(db)
    assert mh.list_tags(db) == rows


def _reset_migration(db):
    db.execute("DELETE FROM settings WHERE key = ?", [mh.MIGRATION_KEY])
    db.execute("DELETE FROM tag_defs")
    db.execute("DELETE FROM marked_hands")
    db.execute("DELETE FROM marked_hand_tags")


def test_migration_from_hand_tags(db):
    _ws2(db)
    _load(db, 1)
    _load(db, 2)
    hero, p3 = _pid(db, "Hero"), _pid(db, "Player3")
    # ws1 hand 1: hero sits but has no known cards -> still the hero's row
    db.execute("UPDATE hand_players SET card1 = NULL, card2 = NULL "
               "WHERE workspace_id = 1 AND hand_id = ? AND player_id = ?", [IDS[1], hero])
    # ws1 hand 2: hero not in the hand, Player3 the only known cards -> Player3
    db.execute("DELETE FROM hand_players WHERE workspace_id = 1 AND hand_id = ? AND player_id = ?",
               [IDS[2], hero])
    db.execute("UPDATE hand_players SET card1 = 'As', card2 = 'Ad' "
               "WHERE workspace_id = 1 AND hand_id = ? AND player_id = ?", [IDS[2], p3])
    # ws1 hand 3: hero not in the hand, nobody known -> lowest seat
    db.execute("DELETE FROM hand_players WHERE workspace_id = 1 AND hand_id = ? AND player_id = ?",
               [IDS[3], hero])
    db.execute("UPDATE hand_players SET card1 = NULL WHERE workspace_id = 1 AND hand_id = ?", [IDS[3]])
    lowest = db.execute("SELECT player_id FROM hand_players WHERE workspace_id = 1 AND hand_id = ? "
                        "ORDER BY seat LIMIT 1", [IDS[3]]).fetchone()[0]
    for ws, hid, tag, ts in [
        (1, IDS[0], "bluff", "2026-01-01 10:00:02"),
        (1, IDS[0], "Weird spot", "2026-01-01 10:00:01"),
        (1, IDS[0], "Mistake", "2026-01-01 10:00:03"),
        (1, IDS[1], "cooler", "2026-01-02 10:00:00"),
        (1, IDS[2], "value", "2026-01-03 10:00:00"),
        (1, IDS[3], "study", "2026-01-04 10:00:00"),
        (2, IDS[0], "Weird spot", "2026-01-05 10:00:00"),
        (2, IDS[4], "great play", "2026-01-06 10:00:00"),
        (1, "NOPE", "orphan", "2026-01-07 10:00:00"),  # hand does not exist: ignored
    ]:
        db.execute("INSERT INTO hand_tags (hand_id, tag, created_at, workspace_id) VALUES (?, ?, ?, ?)",
                   [hid, tag, ts, ws])
    _reset_migration(db)
    invalidate_hero_cache()
    mh.migrate_hand_tags(db)

    tags = mh.list_tags(db)
    by_name = {t["name"]: t for t in tags}
    # presets first in default order (case-insensitive match keeps the original name)
    assert [t["name"] for t in tags] == ["Mistake", "bluff", "cooler", "value", "study",
                                         "great play", "Weird spot"]
    assert by_name["Mistake"]["color"] == "tag-7"
    assert by_name["great play"]["color"] == "tag-9"
    assert by_name["Weird spot"]["color"] == "tag-1"
    assert "orphan" not in by_name

    marks = db.execute("SELECT workspace_id, hand_id, player_id FROM marked_hands "
                       "ORDER BY 1, 2").fetchall()
    assert marks == [(1, IDS[0], hero), (1, IDS[1], hero), (1, IDS[2], p3), (1, IDS[3], lowest),
                     (2, IDS[0], hero), (2, IDS[4], hero)]
    # tags kept in created_at order
    order = db.execute("SELECT tag_id FROM marked_hand_tags WHERE workspace_id = 1 AND hand_id = ? "
                       "ORDER BY position", [IDS[0]]).fetchall()
    assert [r[0] for r in order] == [by_name[n]["id"] for n in ("Weird spot", "bluff", "Mistake")]
    # hand_tags rows untouched
    assert db.execute("SELECT COUNT(*) FROM hand_tags").fetchone()[0] == 9

    # idempotent: flag set; and even without the flag nothing is duplicated
    snapshot = (mh.list_tags(db), db.execute("SELECT * FROM marked_hand_tags ORDER BY ALL").fetchall())
    mh.migrate_hand_tags(db)
    db.execute("DELETE FROM settings WHERE key = ?", [mh.MIGRATION_KEY])
    mh.migrate_hand_tags(db)
    assert (mh.list_tags(db), db.execute("SELECT * FROM marked_hand_tags ORDER BY ALL").fetchall()) \
        == snapshot
    assert db.execute("SELECT COUNT(*) FROM marked_hands").fetchone()[0] == 6


def test_migration_empty_db(db):
    _reset_migration(db)
    mh.migrate_hand_tags(db)
    mh.migrate_hand_tags(db)
    assert [t["name"] for t in mh.list_tags(db)] == DEFAULT_NAMES


# ── tag catalogue ──────────────────────────────────────────────────────────────────────────


def test_tag_crud_and_order(client):
    r = client.post("/api/tag-defs", json={})
    assert r.status_code == 200
    t = r.json()
    assert (t["name"], t["color"], t["position"]) == ("my tag", "tag-7", 6)
    r = client.post("/api/tag-defs", json={"name": "  river  ", "color": "tag-8"})
    assert (r.json()["name"], r.json()["color"]) == ("river", "tag-8")

    r = client.patch(f"/api/tag-defs/{t['id']}", json={"name": " renamed ", "color": "tag-2"})
    assert r.status_code == 200 and (r.json()["name"], r.json()["color"]) == ("renamed", "tag-2")
    for bad in ({"name": "   "}, {"name": "x" * 61}, {"color": "#ff0000"}, {"color": "tag-10"}):
        assert client.patch(f"/api/tag-defs/{t['id']}", json=bad).status_code == 422
    assert client.post("/api/tag-defs", json={"name": ""}).status_code == 422
    assert client.patch("/api/tag-defs/9999", json={"name": "a"}).status_code == 404

    # move
    first = _tags(client)[0]["id"]
    assert [x["id"] for x in client.post(f"/api/tag-defs/{first}/move", json={"direction": "up"}).json()][0] == first
    after = client.post(f"/api/tag-defs/{first}/move", json={"direction": "down"}).json()
    assert after[1]["id"] == first and [x["position"] for x in after] == list(range(len(after)))
    last = after[-1]["id"]
    assert client.post(f"/api/tag-defs/{last}/move", json={"direction": "down"}).json()[-1]["id"] == last
    assert client.post(f"/api/tag-defs/{last}/move", json={"direction": "left"}).status_code == 422
    assert client.post("/api/tag-defs/9999/move", json={"direction": "up"}).status_code == 404

    # delete renumbers; ids never reused
    assert client.delete(f"/api/tag-defs/{t['id']}").status_code == 204
    assert client.delete(f"/api/tag-defs/{t['id']}").status_code == 404
    rows = _tags(client)
    assert [x["position"] for x in rows] == list(range(len(rows)))
    assert client.post("/api/tag-defs", json={}).json()["id"] > t["id"]


def test_reset_semantics(client):
    bluff = _tid(client, "bluff")
    client.patch(f"/api/tag-defs/{bluff}", json={"name": "BLUFF", "color": "tag-1"})
    custom = client.post("/api/tag-defs", json={"name": "custom"}).json()["id"]
    study = _tid(client, "study")
    client.delete(f"/api/tag-defs/{study}")
    _mark(client, IDS[0], tag_ids=[bluff, custom])

    r = client.post("/api/tag-defs/reset")
    assert r.status_code == 200
    rows = r.json()
    assert [t["name"] for t in rows] == DEFAULT_NAMES
    assert [t["position"] for t in rows] == list(range(6))
    # bluff kept its id (name matched case-insensitively) and default colour; custom deleted
    assert rows[1]["id"] == bluff and rows[1]["color"] == "tag-5"
    assert custom not in {t["id"] for t in rows}
    row = _list(client, marked=True)["hands"][0]
    assert row["marked"] is True and [t["id"] for t in row["tags"]] == [bluff]


# ── marking ────────────────────────────────────────────────────────────────────────────────


def test_mark_unmark_replace(client, db):
    hero = _pid(db, "Hero")
    bluff, value, cooler = (_tid(client, n) for n in ("bluff", "value", "cooler"))
    st = _mark(client, IDS[0])
    assert st == {"hand_id": IDS[0], "player_id": hero, "marked": True, "tags": []}
    # replace tags; result in catalogue order, duplicates dropped
    st = _mark(client, IDS[0], tag_ids=[value, bluff, value])
    assert [t["name"] for t in st["tags"]] == ["bluff", "value"]
    assert st["tags"][0] == {"id": bluff, "name": "bluff", "color": "tag-5"}
    # no tag_ids: no-op on the tags
    assert _mark(client, IDS[0])["tags"] == st["tags"]
    st = _mark(client, IDS[0], tag_ids=[cooler])
    assert [t["name"] for t in st["tags"]] == ["cooler"]
    # empty list keeps the hand marked
    st = _mark(client, IDS[0], tag_ids=[])
    assert st["marked"] is True and st["tags"] == []
    # unknown tag -> 422, nothing changes
    r = client.put(f"/api/hands/{IDS[0]}/mark", json={"tag_ids": [bluff, 9999]})
    assert r.status_code == 422
    # unknown hand / player
    assert client.put("/api/hands/NOPE/mark", json={}).status_code == 404
    other = _pid(db, "Player2")
    assert client.put(f"/api/hands/{IDS[0]}/mark", json={"player_id": 999999}).status_code == 404
    st = _mark(client, IDS[0], player_id=other, tag_ids=[bluff])
    assert st["player_id"] == other
    assert db.execute("SELECT COUNT(*) FROM marked_hands").fetchone()[0] == 2

    # detail carries the hero's mark
    d = client.get(f"/api/hands/{IDS[0]}").json()
    assert d["marked"] is True and d["tags"] == []
    d = client.get(f"/api/hands/{IDS[0]}", params={"player_id": other}).json()
    assert [t["name"] for t in d["tags"]] == ["bluff"]
    assert client.get(f"/api/hands/{IDS[1]}").json()["marked"] is False

    # unmark (default hero), tags go too
    assert client.delete(f"/api/hands/{IDS[0]}/mark").status_code == 204
    assert client.delete(f"/api/hands/{IDS[0]}/mark", params={"player_id": other}).status_code == 204
    assert db.execute("SELECT COUNT(*) FROM marked_hands").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM marked_hand_tags").fetchone()[0] == 0
    assert client.delete("/api/hands/NOPE/mark").status_code == 404


def test_hero_not_in_hand_is_404(client, db):
    db.execute("DELETE FROM hand_players WHERE hand_id = ? AND player_id = ?", [IDS[1], _pid(db, "Hero")])
    assert client.put(f"/api/hands/{IDS[1]}/mark", json={}).status_code == 404


def test_delete_tag_keeps_hand_marked(client):
    bluff = _tid(client, "bluff")
    _mark(client, IDS[2], tag_ids=[bluff])
    assert client.delete(f"/api/tag-defs/{bluff}").status_code == 204
    row = next(h for h in _list(client)["hands"] if h["id"] == IDS[2])
    assert row["marked"] is True and row["tags"] == []
    assert _ids(client, marked=True) == [IDS[2]]


# ── lists ──────────────────────────────────────────────────────────────────────────────────


def test_list_filters(client):
    bluff, value, cooler = (_tid(client, n) for n in ("bluff", "value", "cooler"))
    _mark(client, IDS[0], tag_ids=[bluff])
    _mark(client, IDS[1], tag_ids=[value, bluff])
    _mark(client, IDS[2])
    assert _ids(client, marked=True) == IDS[:3]
    assert _ids(client, marked=False) == IDS[3:]
    assert _ids(client, tag_ids=str(bluff)) == IDS[:2]
    assert _ids(client, tag_ids=f"{value},{cooler}") == [IDS[1]]           # OR
    assert _ids(client, tag_ids=f"{cooler}") == []
    assert _ids(client, tag_ids=str(bluff), marked=False) == []            # implies marked
    for empty in (",", " , ", ""):
        assert _ids(client, tag_ids=empty) == IDS                          # ignored
    rows = {h["id"]: h for h in _list(client)["hands"]}
    assert [t["name"] for t in rows[IDS[1]]["tags"]] == ["bluff", "value"]  # catalogue order
    # sort by Tags: first tag's catalogue position, untagged -1
    _mark(client, IDS[4], tag_ids=[value])
    pos = {t["id"]: t["position"] for t in _tags(client)}
    keys = [min((pos[x["id"]] for x in h["tags"]), default=-1)
            for h in _list(client, sort="tags", order="asc")["hands"]]
    assert keys == [-1, -1, 1, 1, 3]
    assert rows[IDS[2]]["marked"] is True and rows[IDS[2]]["tags"] == []
    assert rows[IDS[3]]["marked"] is False
    # the old params are gone (ignored as unknown query params)
    assert _list(client, tags="bluff")["total"] == 5
    assert client.get("/api/tags").status_code in (404, 405)
    assert client.post(f"/api/hands/{IDS[0]}/tags", json={"tag": "x"}).status_code in (404, 405)


def test_list_rows_are_the_row_players(client, db):
    other = _pid(db, "Player2")
    _mark(client, IDS[0], player_id=other)
    assert _ids(client, marked=True) == []
    assert _ids(client, marked=True, player_id=other) == [IDS[0]]


def test_general_popup_rows_carry_marks(client):
    from app.api import general_popup
    general_popup.clear_cache()
    bluff = _tid(client, "bluff")
    r = client.get("/api/general/cell/preflop.open_raise.Total/hands")
    assert r.status_code == 200, r.text
    [row] = r.json()["rows"]
    assert row["hand_id"] == IDS[3] and row["marked"] is False and row["tags"] == []
    _mark(client, IDS[3], tag_ids=[bluff])
    [row] = client.get("/api/general/cell/preflop.open_raise.Total/hands").json()["rows"]
    assert row["marked"] is True
    assert row["tags"] == [{"id": bluff, "name": "bluff", "color": "tag-5"}]


# ── unmark all ─────────────────────────────────────────────────────────────────────────────


def test_unmark_scoped_by_tags(client):
    bluff, value = _tid(client, "bluff"), _tid(client, "value")
    _mark(client, IDS[0], tag_ids=[bluff])
    _mark(client, IDS[1], tag_ids=[value])
    _mark(client, IDS[2])
    r = client.post("/api/marked-hands/unmark", json={"tag_ids": [bluff]})
    assert r.json() == {"unmarked": 1}
    assert _ids(client, marked=True) == IDS[1:3]
    assert client.post("/api/marked-hands/unmark", json={}).json() == {"unmarked": 2}
    assert _ids(client, marked=True) == []


# ── workspaces ─────────────────────────────────────────────────────────────────────────────


def test_workspace_isolation_and_delete(client, db):
    _ws2(db)
    _load(db, 2)
    bluff = _tid(client, "bluff")
    _mark(client, IDS[0], ws=1, tag_ids=[bluff])
    _mark(client, IDS[1], ws=2, tag_ids=[bluff])
    assert _ids(client, marked=True, workspace_id=1) == [IDS[0]]
    assert _ids(client, marked=True, workspace_id=2) == [IDS[1]]
    assert client.post("/api/marked-hands/unmark", params={"workspace_id": 2}, json={}).json() \
        == {"unmarked": 1}
    assert _ids(client, marked=True, workspace_id=1) == [IDS[0]]

    _mark(client, IDS[1], ws=2, tag_ids=[bluff])
    assert client.delete("/api/workspaces/2").status_code == 200
    assert db.execute("SELECT DISTINCT workspace_id FROM marked_hands").fetchall() == [(1,)]
    assert db.execute("SELECT DISTINCT workspace_id FROM marked_hand_tags").fetchall() == [(1,)]
    # clearing the hands drops the workspace's marks; the catalogue stays
    assert client.post("/api/import/clear", params={"workspace_id": 1}).status_code == 200
    assert db.execute("SELECT COUNT(*) FROM marked_hands").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM marked_hand_tags").fetchone()[0] == 0
    assert len(_tags(client)) == 6


# ── export / import ────────────────────────────────────────────────────────────────────────


def _setup_export(client, db):
    bluff, value = _tid(client, "bluff"), _tid(client, "value")
    custom = client.post("/api/tag-defs", json={"name": "Hero call", "color": "tag-6"}).json()["id"]
    _mark(client, IDS[0], tag_ids=[value, custom])
    _mark(client, IDS[1], player_id=_pid(db, "Player2"), tag_ids=[bluff])
    _mark(client, IDS[3])
    return bluff, value, custom


def test_export_json(client, db):
    bluff, value, custom = _setup_export(client, db)
    r = client.get("/api/marked-hands/export", params={"format": "json"})
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="Marked Hands.json"'
    doc = r.json()
    assert doc["format"] == "ohm-marked-hands" and doc["version"] == 1
    by_id = {e["hand_id"]: e for e in doc["hands"]}
    assert sorted(by_id) == [IDS[0], IDS[1], IDS[3]]
    assert by_id[IDS[0]]["player"] == "Hero" and by_id[IDS[0]]["site"] == "GG"
    assert by_id[IDS[0]]["tags"] == [{"name": "value", "color": "tag-3"},
                                     {"name": "Hero call", "color": "tag-6"}]
    assert by_id[IDS[1]]["player"] == "Player2"
    assert by_id[IDS[0]]["hand_text"].startswith(f"Poker Hand #{IDS[0]}")
    # scoped by tags (OR)
    doc = client.get("/api/marked-hands/export",
                     params={"format": "json", "tag_ids": f"{bluff},{custom}"}).json()
    assert sorted(e["hand_id"] for e in doc["hands"]) == [IDS[0], IDS[1]]


def test_export_txt(client, db):
    _setup_export(client, db)
    r = client.get("/api/marked-hands/export", params={"format": "txt"})
    assert r.status_code == 200
    assert r.headers["content-disposition"] == 'attachment; filename="Marked Hands.txt"'
    assert r.text.count("Poker Hand #") == 3


def test_json_round_trip(client, db):
    _setup_export(client, db)
    exported = client.get("/api/marked-hands/export", params={"format": "json"}).content
    # into an empty workspace whose catalogue lacks "Hero call" and has "value" renamed case
    _ws2(db)
    client.delete(f"/api/tag-defs/{_tid(client, 'Hero call')}")
    client.patch(f"/api/tag-defs/{_tid(client, 'value')}", json={"name": "Value"})
    r = client.post("/api/marked-hands/import", params={"workspace_id": 2},
                    files=[("files", ("Marked Hands.json", exported, "application/json"))])
    assert r.status_code == 200, r.text
    assert r.json() == {"imported": 3, "duplicates": 0, "marked": 3, "errors": 0}
    names = {t["name"]: t for t in _tags(client)}
    assert names["Hero call"]["color"] == "tag-6"          # recreated with the file's colour
    rows = {h["id"]: h for h in _list(client, workspace_id=2, marked=True)["hands"]}
    assert sorted(rows) == [IDS[0], IDS[3]]                  # hero rows
    assert [t["name"] for t in rows[IDS[0]]["tags"]] == ["Value", "Hero call"]
    p2 = _pid(db, "Player2")
    assert _ids(client, workspace_id=2, marked=True, player_id=p2) == [IDS[1]]

    # again: duplicates, nothing newly marked, tags not duplicated
    r = client.post("/api/marked-hands/import", params={"workspace_id": 2},
                    files=[("files", ("x.json", exported, "application/json"))])
    assert r.json() == {"imported": 0, "duplicates": 3, "marked": 0, "errors": 0}
    assert db.execute("SELECT COUNT(*) FROM marked_hand_tags WHERE workspace_id = 2").fetchone()[0] == 3


def test_txt_and_zip_import_marks_hero(client, db):
    _ws2(db)
    txt = "\n\n\n".join(HANDS[:2]).encode()
    r = client.post("/api/marked-hands/import", params={"workspace_id": 2},
                    files=[("files", ("hands.txt", txt, "text/plain"))])
    assert r.json() == {"imported": 2, "duplicates": 0, "marked": 2, "errors": 0}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a/more.txt", "\n\n\n".join(HANDS[1:4]))
    r = client.post("/api/marked-hands/import", params={"workspace_id": 2},
                    files=[("files", ("hands.zip", buf.getvalue(), "application/zip"))])
    assert r.json() == {"imported": 2, "duplicates": 1, "marked": 2, "errors": 0}
    rows = _list(client, workspace_id=2, marked=True)["hands"]
    assert sorted(h["id"] for h in rows) == IDS[:4]
    assert all(h["tags"] == [] for h in rows)
    hero = _pid(db, "Hero")
    assert {r[0] for r in db.execute("SELECT player_id FROM marked_hands WHERE workspace_id = 2").fetchall()} == {hero}
    # duplicates already in the workspace are still marked
    r = client.post("/api/marked-hands/import", params={"workspace_id": 1},
                    files=[("files", ("hands.txt", txt, "text/plain"))])
    assert r.json() == {"imported": 0, "duplicates": 2, "marked": 2, "errors": 0}


def test_import_bad_files(client):
    r = client.post("/api/marked-hands/import", files=[
        ("files", ("bad.json", b"{nope", "application/json")),
        ("files", ("other.json", json.dumps({"format": "x"}).encode(), "application/json")),
        ("files", ("pic.png", b"\x89PNG", "image/png")),
        ("files", ("random.txt", b"hello world", "text/plain")),
    ])
    assert r.status_code == 200
    assert r.json() == {"imported": 0, "duplicates": 0, "marked": 0, "errors": 4}
