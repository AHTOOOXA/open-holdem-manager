"""Hero accounts: auto-detection, resolution, API, migration."""

from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import insert_parsed_hand
from app.db import get_hero_player_id, get_hero_username, init_schema
from app.heroes import detect_heroes, invalidate_hero_cache, resolve_hero
from app.main import app
from app.parsers import pokerstars, wpn
from app.parsers.ggpoker import parse_hand_history as parse_gg

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_default_hero(db):
    """The shared db fixture seeds Hero/GG; these tests start with no accounts."""
    db.execute("DELETE FROM hero_accounts")
    invalidate_hero_cache()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _insert_all(db, parser, text, workspace_id=1):
    for h in parser.split_hands(text):
        insert_parsed_hand(db, parser.parse_hand_history(h), workspace_id=workspace_id)


def _gg(db):
    text = (FIXTURES / "ggpoker" / "sample.txt").read_text()
    for hand in [h.strip() for h in text.split("\n\n\n") if h.strip()]:
        insert_parsed_hand(db, parse_gg(hand))


def _accounts(db, source=None):
    q = "SELECT username, source FROM hero_accounts"
    if source:
        q += f" WHERE source = '{source}'"
    return sorted(db.execute(q).fetchall())


def _pid(db, name):
    return db.execute("SELECT id FROM players WHERE username = ?", [name]).fetchone()[0]


def test_pokerstars_hero_detected(db):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    assert _accounts(db) == [("Player1", "auto")]
    assert get_hero_player_id(db, 1) == _pid(db, "Player1")
    assert get_hero_username(db, 1) == "Player1"
    ref = resolve_hero(db, 1)
    assert ref.site_code == "PS" and ref.hand_count == 2


def test_wpn_hero_detected(db):
    text = (FIXTURES / "wpn" / "basic.txt").read_text()
    text = text.replace(
        "Player Player1 received a card.\nPlayer Player1 received a card.",
        "Player Player1 received card: [Ah]\nPlayer Player1 received card: [Kd]",
    )
    # no showdown: only the hero's cards are known
    text = text.replace("Player Player5 shows: High card King [Qh Jh].",
                        "Player Player5 does not show cards.")
    text = text.replace("*Player Player1 shows: Pair of Kings [Ah Kd].",
                        "Player Player1 does not show cards.")
    _insert_all(db, wpn, text)
    assert len(db.execute("SELECT 1 FROM hand_players WHERE card1 IS NOT NULL").fetchall()) == 1
    assert _accounts(db) == [("Player1", "auto")]
    assert resolve_hero(db, 1).site_code == "WPN"


def test_gg_hero_detected(db):
    _gg(db)
    assert ("Hero", "auto") in _accounts(db)
    assert get_hero_username(db, 1) == "Hero"


def test_showdown_does_not_add_villain(db):
    # real_allin_showdown: both players' cards are known, none dealt to hero
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "allin_showdown.txt").read_text())
    known = db.execute("SELECT COUNT(*) FROM hand_players WHERE card1 IS NOT NULL").fetchone()[0]
    assert known >= 2
    assert _accounts(db) == []


def test_auto_detect_off_adds_nothing(db):
    db.execute("UPDATE workspaces SET hero_auto_detect = FALSE WHERE id = 1")
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    assert _accounts(db) == []
    # fallback: busiest player
    assert resolve_hero(db, 1) is not None


def test_resolution_most_hands_wins_and_manual_wins_ties(db, client):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    players = [r[0] for r in db.execute(
        "SELECT DISTINCT p.username FROM players p JOIN hand_players hp ON hp.player_id = p.id"
    ).fetchall()]
    other = next(p for p in players if p != "Player1")
    # all players in these 2 hands have the same count: auto Player1 vs manual other
    # tie -> manual first
    r = client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": [other]})
    assert r.status_code == 200
    assert get_hero_username(db, 1) == other
    assert r.json()["active"]["username"] == other


def test_fallback_to_busiest_player(db):
    _gg(db)
    db.execute("DELETE FROM hero_accounts")
    invalidate_hero_cache()
    busiest = db.execute(
        "SELECT p.username FROM hand_players hp JOIN players p ON p.id = hp.player_id "
        "GROUP BY p.username ORDER BY COUNT(*) DESC, p.username LIMIT 1"
    ).fetchone()[0]
    assert get_hero_username(db, 1) == busiest


def test_empty_workspace_has_no_hero(db):
    assert resolve_hero(db, 1) is None
    assert get_hero_username(db, 1) == "Hero"
    assert get_hero_player_id(db, 1) is None


def test_manual_put_semantics(db, client):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    r = client.put("/api/workspaces/1/heroes/manual",
                   json={"site": "PS", "usernames": [" a ", "", "a", "b", "   "]})
    assert r.status_code == 200
    manual = [a["username"] for a in r.json()["accounts"] if a["source"] == "manual"]
    assert manual == ["a", "b"]
    r = client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": ["c"]})
    assert [a["username"] for a in r.json()["accounts"] if a["source"] == "manual"] == ["c"]
    r = client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": []})
    assert all(a["source"] == "auto" for a in r.json()["accounts"])
    assert client.put("/api/workspaces/1/heroes/manual",
                      json={"site": "XX", "usernames": ["a"]}).status_code == 400
    assert client.put("/api/workspaces/99/heroes/manual",
                      json={"site": "PS", "usernames": ["a"]}).status_code == 404


def test_get_heroes_shape_and_cache_invalidation(db, client):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    body = client.get("/api/workspaces/1/heroes").json()
    assert body["auto_detect"] is True
    assert body["accounts"] == [{"site": "PS", "site_name": "PokerStars",
                                 "username": "Player1", "source": "auto", "hand_count": 2}]
    assert body["active"] == {"site": "PS", "site_name": "PokerStars",
                              "username": "Player1", "hand_count": 2}
    assert client.get("/api/workspaces/99/heroes").status_code == 404
    assert client.get("/api/sites").json()[:2] == [
        {"code": "GG", "name": "GGPoker"}, {"code": "PS", "name": "PokerStars"}]
    # manual change invalidates the cache
    assert get_hero_username(db, 1) == "Player1"
    client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": ["zzz"]})
    other = db.execute("SELECT username FROM players WHERE username != 'Player1' LIMIT 1").fetchone()[0]
    client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": [other]})
    assert get_hero_username(db, 1) in (other, "Player1")


def test_patch_auto_detect(db, client):
    db.execute("UPDATE workspaces SET hero_auto_detect = FALSE WHERE id = 1")
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    assert _accounts(db) == []
    r = client.patch("/api/workspaces/1/heroes", json={"auto_detect": True})
    assert r.status_code == 200
    assert r.json()["auto_detect"] is True
    assert [a["username"] for a in r.json()["accounts"]] == ["Player1"]
    r = client.patch("/api/workspaces/1/heroes", json={"auto_detect": False})
    assert r.json()["auto_detect"] is False


def test_workspaces_response_uses_resolved_hero(db, client):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    ws = client.get("/api/workspaces").json()[0]
    assert ws["hero_username"] == "Player1" and ws["hero_site"] == "PS"
    created = client.post("/api/workspaces", json={"name": "Empty"}).json()
    assert created["hero_username"] == "" and created["hero_site"] == ""
    c2 = client.post("/api/workspaces", json={"name": "W2", "hero_username": "me", "hero_site": "WPN"})
    assert c2.status_code == 201
    assert client.get(f"/api/workspaces/{c2.json()['id']}/heroes").json()["accounts"][0]["username"] == "me"
    assert client.get("/api/settings").json()["hero_username"] == "Player1"
    client.patch("/api/settings", json={"hero_username": "x", "hero_site": "PS"})
    assert ("x", "manual") in _accounts(db)


def test_delete_workspace_removes_accounts(db, client):
    c = client.post("/api/workspaces", json={"name": "W2", "hero_username": "me", "hero_site": "PS"}).json()
    assert client.delete(f"/api/workspaces/{c['id']}").status_code == 200
    assert db.execute("SELECT COUNT(*) FROM hero_accounts WHERE workspace_id = ?", [c["id"]]).fetchone()[0] == 0


def test_clear_keeps_manual_removes_auto(db, client):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": ["m"]})
    assert client.post("/api/import/clear").status_code == 200
    assert _accounts(db) == [("m", "manual")]


def test_migration_backfills_legacy_db():
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    # build a "legacy" DB: hands in, no hero_accounts, marker absent
    _insert_all(conn, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    conn.execute("DELETE FROM hero_accounts")
    conn.execute("DELETE FROM settings WHERE key = 'hero_accounts_v1'")
    conn.execute("UPDATE workspaces SET hero_username = 'Player2', hero_site = 'PS'")
    init_schema(conn)
    assert _accounts(conn) == [("Player1", "auto"), ("Player2", "manual")]
    # idempotent
    init_schema(conn)
    assert len(_accounts(conn)) == 2
    conn.close()


def test_detect_heroes_all_workspaces(db):
    _insert_all(db, pokerstars, (FIXTURES / "pokerstars" / "multi_hand.txt").read_text())
    db.execute("DELETE FROM hero_accounts")
    assert detect_heroes(db, None) == 1


def test_resolve_does_not_cache_a_result_that_raced_an_invalidation(monkeypatch):
    from app import heroes

    heroes.invalidate_hero_cache()
    stale = heroes.HeroRef(1, "old", "GG", "GGPoker", 1)

    def racing_resolve(db, workspace_id):
        heroes.invalidate_hero_cache(workspace_id)  # an import finishes mid-resolve
        return stale

    monkeypatch.setattr(heroes, "_resolve", racing_resolve)
    assert heroes.resolve_hero(None, 99) is stale
    assert 99 not in heroes._cache


def test_manual_put_rejects_oversized_nicknames(client):
    r = client.put("/api/workspaces/1/heroes/manual", json={"site": "PS", "usernames": ["x" * 65]})
    assert r.status_code == 422
