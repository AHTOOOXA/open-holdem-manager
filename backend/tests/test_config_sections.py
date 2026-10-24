"""Configuration sections backend: config store, reg classification, rebuild fingerprint,
alias CSV, app-settings reset, system info."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app import config_sections as cs
from app.api.import_hands import insert_parsed_hand
from app.main import app
from app.parsers.ggpoker import parse_hand_history
from app.player_classification import batch_update_player_types, evaluate_reg
from tests.test_h2n_matcher import hh


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


# ── config store ────────────────────────────────────────────────────


def test_defaults_and_roundtrip(client):
    r = client.get("/api/config/stat_appearance").json()
    assert r["is_default"] and r["value"] == r["default"]
    assert r["value"]["show_sample_below"] == 15 and r["value"]["show_99_for_100"] is True
    v = dict(r["value"], leading_zero=True, one_decimal_below=12.5)
    put = client.put("/api/config/stat_appearance", json=v)
    assert put.status_code == 200 and put.json()["value"] == v and not put.json()["is_default"]
    assert client.get("/api/config/stat_appearance").json()["value"] == v
    reset = client.delete("/api/config/stat_appearance").json()
    assert reset["is_default"] and reset["value"] == reset["default"]


def test_markers_default_and_validation(client):
    d = client.get("/api/config/color_markers").json()
    assert [m["name"] for m in d["value"]] == ["Fish", "Reg"]
    ok = [{"id": 5, "name": " Whale ", "color": "tag-1", "is_regular": False}]
    r = client.put("/api/config/color_markers", json=ok)
    assert r.status_code == 200 and r.json()["value"][0]["name"] == "Whale"
    assert client.put("/api/config/color_markers", json=[]).status_code == 200
    bad = [
        [{"id": 1, "name": "a", "color": "tag-1", "is_regular": True}] * 2,
        [{"id": 1, "name": "  ", "color": "tag-1", "is_regular": True}],
        [{"id": 1, "name": "x" * 61, "color": "tag-1", "is_regular": True}],
        [{"id": 1, "name": "a", "color": "tag-10", "is_regular": True}],
        [{"id": 1, "name": "a", "color": "red", "is_regular": True}],
    ]
    for b in bad:
        assert client.put("/api/config/color_markers", json=b).status_code == 422, b


def test_game_types_validation(client):
    rule = client.get("/api/config/game_types").json()["value"]["reg_rule"]
    assert rule["auto_reg_hands"] == 20000 and rule["vpip"] == [0, 35]
    good = {"reg_rule": dict(rule, vpip=[10, 30], min_hands=0)}
    assert client.put("/api/config/game_types", json=good).status_code == 200
    for patch in ({"vpip": [30, 10]}, {"pfr": [0, 101]}, {"limp": [-1, 5]}, {"min_hands": -1}):
        assert client.put("/api/config/game_types", json={"reg_rule": dict(rule, **patch)}).status_code == 422
    assert client.put("/api/config/game_types", json={"reg_rule": dict(rule, extra=1)}).status_code == 422
    assert client.put("/api/config/stat_appearance", json={"dim_below": 0}).status_code == 422


def test_unknown_section_404(client):
    assert client.get("/api/config/nope").status_code == 404
    assert client.put("/api/config/nope", json={}).status_code == 404
    assert client.delete("/api/config/nope").status_code == 404


# ── classification ──────────────────────────────────────────────────


def _hands(db, n, actions="V R2.5, Hero F", start=1, players=("Hero", "V")):
    for i in range(n):
        insert_parsed_hand(db, parse_hand_history(
            hh(list(players), actions, max_seats=2, hand_no=start + i, collected={"V": 2})))
    batch_update_player_types(db)


def _reg(client, name="V"):
    pl = client.get("/api/players", params={"min_hands": 0}).json()["players"]
    return next(p for p in pl if p["username"] == name)


def test_evaluate_reg_rule():
    rule = cs.RegRule()
    assert evaluate_reg(rule, 20000, 90, 90, 90) is True
    assert evaluate_reg(rule, 9, 10, 10, 0) is False
    assert evaluate_reg(rule, 10, 35 + 5e-7, 30, 0) is True  # tolerance
    assert evaluate_reg(rule, 10, 35.1, 30, 0) is False
    assert evaluate_reg(rule, 10, 30, 10, 0) is False  # vpip - pfr = 20


def test_classification_and_markers(client, db):
    _hands(db, 12)  # V opens 12 of 12 hands: VPIP = PFR = 100
    r = _reg(client)
    assert r["reg"] is False and r["marker"] == {"id": 1, "name": "Fish", "color": "tag-3"}
    rule = {"reg_rule": dict(cs.RegRule().model_dump(), vpip=[0, 100], pfr=[0, 100])}
    assert client.put("/api/config/game_types", json=rule).status_code == 200
    batch_update_player_types(db)
    r = _reg(client)
    assert r["reg"] is True and r["marker"]["name"] == "Reg"
    # manual marker overrides
    pid = r["id"]
    db.execute("UPDATE players SET color_tag = '1' WHERE id = ?", [pid])
    assert _reg(client)["marker"]["name"] == "Fish"
    # auto reg by hand count
    rule["reg_rule"].update(auto_reg_hands=5, vpip=[0, 1], pfr=[0, 1])
    client.put("/api/config/game_types", json=rule)
    batch_update_player_types(db, workspace_id=1)
    assert _reg(client)["reg"] is True
    detail = client.get(f"/api/players/{pid}").json()
    assert detail["reg"] is True and detail["marker"]["name"] == "Fish"
    # a player who never had a classification has reg null
    assert client.get("/api/players/999").status_code == 404


def test_limp_range_blocks_reg(client, db):
    _hands(db, 12, "U F, M F, V C, B F, S F, BB X", players=("B", "S", "BB", "U", "M", "V"))  # V limps from the CO
    rule = cs.RegRule().model_dump()
    rule.update(vpip=[0, 100], pfr=[0, 100], vpip_minus_pfr=[0, 100], limp=[0, 20])
    client.put("/api/config/game_types", json={"reg_rule": rule})
    batch_update_player_types(db)
    r = _reg(client)
    assert r["reg"] is False
    rule["limp"] = [0, 100]
    client.put("/api/config/game_types", json={"reg_rule": rule})
    batch_update_player_types(db)
    assert _reg(client)["reg"] is True


# ── fingerprint / health ────────────────────────────────────────────


def test_rebuild_required_flow(client, db):
    # first run: fingerprint adopted, no banner
    assert client.get("/api/health").json()["rebuild_required"] is False
    cs.ensure_rebuild_fingerprint(db)
    assert client.get("/api/health").json()["rebuild_required"] is False
    _hands(db, 1)
    rule = cs.RegRule().model_dump()
    rule["min_hands"] = 99
    client.put("/api/config/game_types", json={"reg_rule": rule})
    assert client.get("/api/health").json()["rebuild_required"] is True
    # import does not store it
    _hands(db, 1, start=50)
    assert client.get("/api/health").json()["rebuild_required"] is True
    cs.store_rebuild_fingerprint(db)
    assert client.get("/api/health").json()["rebuild_required"] is False
    # a reset flips it back (fingerprint differs from the stored one) but only with hands
    client.delete("/api/config/game_types")
    assert client.get("/api/health").json()["rebuild_required"] is True


def test_fingerprint_depends_on_stat_version_and_config(db, monkeypatch):
    a = cs.current_fingerprint(db)
    monkeypatch.setattr(app_db, "STAT_VERSION", app_db.STAT_VERSION + 1)
    assert cs.current_fingerprint(db) != a


def test_no_banner_without_hands(client, db):
    cs.ensure_rebuild_fingerprint(db)
    client.put("/api/config/game_types", json={"reg_rule": dict(cs.RegRule().model_dump(), min_hands=77)})
    assert client.get("/api/health").json()["rebuild_required"] is False


# ── app settings reset ──────────────────────────────────────────────


def test_app_settings_reset_keeps_date_format(client):
    client.patch("/api/app-settings", json={"session_max_break_minutes": 30, "day_start_hour": 5,
                                            "numeric_date_format": True})
    r = client.delete("/api/app-settings")
    assert r.status_code == 200
    assert r.json() == {"session_max_break_minutes": 10, "day_start_hour": 0, "numeric_date_format": True}


# ── system info ─────────────────────────────────────────────────────


def test_system_info(client, tmp_path, monkeypatch):
    p = tmp_path / "poker.duckdb"
    p.write_bytes(b"x" * 100)
    (tmp_path / "poker.duckdb.wal").write_bytes(b"y" * 20)
    import app.api.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", p)
    assert client.get("/api/system/info").json() == {
        "data_dir": str(tmp_path), "db_path": str(p), "db_size_bytes": 120}


# ── aliases ─────────────────────────────────────────────────────────


def _csv(client, text, ws=1):
    return client.post("/api/identities/import-csv", params={"workspace_id": ws},
                       files={"file": ("a.csv", io.BytesIO(text.encode()), "text/csv")})


def test_alias_flags_and_csv_roundtrip(client, db):
    insert_parsed_hand(db, parse_hand_history(hh(["Hero", "Alice", "Bob"], "Alice R2.5, Bob F, Hero F",
                                                 max_seats=3, hand_no=1, collected={"Alice": 2})))
    text = ("Mr X, Alice, GGPoker, True\n"
            "Mr X, Bob, GGPoker, False\n"
            "Mr X, Ghost, GGPoker, False\n"      # unknown nickname
            "Mr Y, Alice, Nowhere, False\n"      # unknown site
            "too,short\n"
            "\n"
            '"Z, the great", Hero, GGPoker\n')
    r = _csv(client, text)
    assert r.status_code == 200
    assert r.json() == {"aliases": 2, "players": 3, "skipped_lines": 3}
    lst = client.get("/api/identities").json()
    mrx = next(i for i in lst if i["display_name"] == "Mr X")
    assert mrx["is_single_person"] is True and mrx["player_count"] == 2 and mrx["pinned"] is False
    # merge: second import into the same alias adds nothing new, other alias with taken player skipped
    r = _csv(client, "Mr X, Alice, GGPoker\nMr W, Alice, GGPoker\n")
    assert r.json() == {"aliases": 2, "players": 0, "skipped_lines": 1}
    # patch flags
    p = client.patch(f"/api/identities/{mrx['id']}", json={"pinned": True, "is_single_person": False})
    assert p.json()["pinned"] is True and p.json()["is_single_person"] is False
    # export, then re-import into a wiped identity set gives the same members
    exp = client.get("/api/identities/export.csv")
    assert exp.headers["content-type"].startswith("text/csv")
    lines = exp.text.splitlines()
    assert 'Mr X, Alice, GGPoker, False' in lines and '"Z, the great", Hero, GGPoker, False' in lines
    assert len(lines) == 3  # Mr X: Alice, Bob; Z: Hero; Mr W has no members
    for i in client.get("/api/identities").json():
        client.delete(f"/api/identities/{i['id']}")
    r = _csv(client, exp.text)
    assert r.json() == {"aliases": 2, "players": 3, "skipped_lines": 0}


def test_marker_next_id_never_reused(client):
    a = client.get("/api/config/color_markers/next-id").json()["id"]
    assert a == 3  # defaults use 1, 2
    b = client.get("/api/config/color_markers/next-id").json()["id"]
    assert b == a + 1
    markers = client.get("/api/config/color_markers").json()["value"]
    markers.append({"id": b, "name": "New", "color": "tag-1", "is_regular": False})
    assert client.put("/api/config/color_markers", json=markers).status_code == 200
    client.put("/api/config/color_markers", json=markers[:2])  # delete it again
    assert client.get("/api/config/color_markers/next-id").json()["id"] == b + 1


def test_identities_csv_malformed_is_422(client):
    r = client.post("/api/identities/import-csv", params={"workspace_id": 1},
                    files={"file": ("a.csv", b'a, b, "unterminated\x00', "text/csv")})
    assert r.status_code in (200, 422)
    import csv as _csv
    import app.api.identities as ident
    orig = ident.csv.reader
    def bad(*a, **k):
        raise _csv.Error("field larger than field limit")
    ident.csv.reader = bad
    try:
        r = client.post("/api/identities/import-csv", params={"workspace_id": 1},
                        files={"file": ("a.csv", b"a,b,c", "text/csv")})
    finally:
        ident.csv.reader = orig
    assert r.status_code == 422 and "Invalid CSV" in r.text


def test_player_color_tag_validation(client, db):
    db.execute("INSERT INTO players (id, site_id, username) VALUES (9001, 1, 'ZZ')")
    ok = client.patch("/api/players/9001/notes", json={"color_tag": "2"})
    assert ok.status_code == 200
    assert client.patch("/api/players/9001/notes", json={"color_tag": "99"}).status_code == 422
    assert client.patch("/api/players/9001/notes", json={"color_tag": "red"}).status_code == 422
    assert client.patch("/api/players/9001/notes", json={"color_tag": ""}).status_code == 200
    # legacy stored value is no manual marker
    from app.api.players import resolve_marker
    from app import config_sections as cs
    assert resolve_marker(cs.get_markers(db), None, "red") is None
