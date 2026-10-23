"""Regression tests for API-level bugs reported by the uhayate fork (BUGS-FROM-FORK.md)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.db as app_db
from app.api.import_hands import insert_parsed_hand
from app.api.players import _action_order_key
from app.main import app
from app.parsers.ggpoker import parse_hand_history

FIXTURES = Path(__file__).parent / "fixtures" / "ggpoker"


@pytest.fixture
def client(db, monkeypatch):
    """TestClient wired to the in-memory test DB, loaded with sample.txt hands."""
    text = (FIXTURES / "sample.txt").read_text()
    for hand in [h.strip() for h in text.split("\n\n\n") if h.strip()]:
        insert_parsed_hand(db, parse_hand_history(hand))
    monkeypatch.setattr(app_db, "_conn", db)
    return TestClient(app)


def _hand_count(client, **params) -> int:
    resp = client.get("/api/hands", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()["total"]


# ── #12: date_to includes the whole day ──────────────────────────────

class TestDateTo:
    def test_hand_late_on_date_to_is_included(self, client, db):
        db.execute("UPDATE hands SET played_at = TIMESTAMP '2026-01-15 23:59:30'")
        total = _hand_count(client)
        assert total > 0
        assert _hand_count(client, date_to="2026-01-15") == total
        assert _hand_count(client, date_to="2026-01-14") == 0

    def test_stats_date_to_includes_last_day(self, client, db):
        db.execute("UPDATE hands SET played_at = TIMESTAMP '2026-01-15 23:59:30'")
        all_hands = client.get("/api/stats/hero").json()["hands"]
        assert all_hands > 0
        same_day = client.get("/api/stats/hero", params={"date_to": "2026-01-15"}).json()["hands"]
        assert same_day == all_hands


# ── #14: empty tag filters and blank tags ────────────────────────────

class TestTags:
    @pytest.mark.parametrize("tags", [",", " , ", ""])
    def test_empty_tag_list_is_ignored(self, client, tags):
        assert _hand_count(client, tags=tags) == _hand_count(client)

    @pytest.mark.parametrize("tag", ["", "   "])
    def test_blank_tag_rejected(self, client, db, tag):
        hand_id = db.execute("SELECT id FROM hands LIMIT 1").fetchone()[0]
        resp = client.post(f"/api/hands/{hand_id}/tags", json={"tag": tag})
        assert resp.status_code == 400
        assert db.execute("SELECT COUNT(*) FROM hand_tags").fetchone()[0] == 0

    def test_tag_is_stripped(self, client, db):
        hand_id = db.execute("SELECT id FROM hands LIMIT 1").fetchone()[0]
        resp = client.post(f"/api/hands/{hand_id}/tags", json={"tag": "  bluff  "})
        assert resp.status_code == 200
        assert db.execute("SELECT tag FROM hand_tags").fetchall() == [("bluff",)]

    def test_duplicate_tag_is_ignored(self, client, db):
        hand_id = db.execute("SELECT id FROM hands LIMIT 1").fetchone()[0]
        for _ in range(2):
            resp = client.post(f"/api/hands/{hand_id}/tags", json={"tag": "bluff"})
            assert resp.status_code == 200, resp.text
        assert db.execute("SELECT COUNT(*) FROM hand_tags").fetchone()[0] == 1
        assert _hand_count(client, tags="bluff") == 1

    def test_any_tag_pseudo_value(self, client, db):
        total = _hand_count(client)
        assert total > 1
        assert _hand_count(client, tags="__any__") == 0
        hand_id = db.execute("SELECT id FROM hands LIMIT 1").fetchone()[0]
        client.post(f"/api/hands/{hand_id}/tags", json={"tag": "bluff"})
        client.post(f"/api/hands/{hand_id}/tags", json={"tag": "hero call"})
        assert _hand_count(client, tags="__any__") == 1
        assert _hand_count(client, tags="untagged") == total - 1

    def test_tag_options_are_a_union(self, client, db):
        total = _hand_count(client)
        ids = [r[0] for r in db.execute("SELECT id FROM hands ORDER BY id LIMIT 2").fetchall()]
        client.post(f"/api/hands/{ids[0]}/tags", json={"tag": "bluff"})
        client.post(f"/api/hands/{ids[1]}/tags", json={"tag": "cooler"})
        # a named tag narrows "any tag"
        assert _hand_count(client, tags="__any__,bluff") == 1
        # untagged + a named tag: both sets
        assert _hand_count(client, tags="untagged,bluff") == total - 1
        # untagged + any tag: everything
        assert _hand_count(client, tags="untagged,__any__") == total


# ── #16: head-to-head rows in action order ───────────────────────────

class TestHeadToHeadOrder:
    def test_action_order_key(self):
        shuffled = ["BB", "BTN", "CO", "EP", "MP", "SB", "UNKNOWN"]
        assert sorted(shuffled, key=_action_order_key) == [
            "EP", "MP", "CO", "BTN", "SB", "BB", "UNKNOWN",
        ]

    def test_endpoint_rows_in_action_order(self, client, db):
        opp_id = db.execute(
            "SELECT p.id FROM players p JOIN hand_players hp ON hp.player_id = p.id "
            "WHERE p.username != 'Hero' GROUP BY p.id ORDER BY COUNT(*) DESC LIMIT 1"
        ).fetchone()[0]
        resp = client.get(f"/api/players/{opp_id}/head-to-head")
        assert resp.status_code == 200, resp.text
        positions = [r["hero_position"] for r in resp.json()["rows"]]
        assert len(positions) > 1
        assert positions == sorted(positions, key=_action_order_key)


# ── #19: population full-stats with player_type ──────────────────────

class TestPopulationPlayerType:
    def test_full_stats_with_player_type(self, client, db):
        db.execute(
            "INSERT INTO player_classifications (player_id, workspace_id, player_type) "
            "SELECT id, 1, 'REG' FROM players WHERE username = 'Player2'"
        )
        player2_hands = db.execute(
            "SELECT COUNT(*) FROM hand_players hp JOIN players p ON p.id = hp.player_id "
            "WHERE p.username = 'Player2'"
        ).fetchone()[0]

        resp = client.get(
            "/api/population/full-stats", params={"player_type": "REG", "min_hands": 0},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["hands"] == player2_hands
