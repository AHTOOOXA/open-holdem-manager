"""Shared raw-text action parser for hand histories."""

import re
from app.models import ActionItem

# ── Regex patterns ───────────────────────────────────────────────────

RE_FOLD = re.compile(r"^(.+?): folds")
RE_CHECK = re.compile(r"^(.+?): checks")
RE_CALL = re.compile(r"^(.+?): calls \$([0-9.]+)")
RE_BET = re.compile(r"^(.+?): bets \$([0-9.]+)")
RE_RAISE = re.compile(r"^(.+?): raises \$[0-9.]+ to \$([0-9.]+)")
RE_BLIND = re.compile(r"^(.+?): posts (?:small blind|big blind|ante) \$([0-9.]+)")
RE_STREET = re.compile(r"^\*\*\* (HOLE CARDS|FLOP|TURN|RIVER|FIRST FLOP|SHOWDOWN|SUMMARY) \*\*\*")

STREET_MAP = {
    "HOLE CARDS": "preflop",
    "FLOP": "flop",
    "FIRST FLOP": "flop",
    "TURN": "turn",
    "RIVER": "river",
}


def parse_actions_from_raw(raw_text: str, hero_username: str, bb_amount: float):
    """Parse raw hand history text and return per-street action summaries + pot sizes."""
    streets = {
        "preflop": {"actions": [], "pot": 0},
        "flop": {"actions": [], "pot": 0},
        "turn": {"actions": [], "pot": 0},
        "river": {"actions": [], "pot": 0},
    }

    current_street = None
    running_pot = 0.0
    street_investments: dict[str, float] = {}  # player -> total invested this street

    for line in raw_text.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Street markers
        sm = RE_STREET.match(line)
        if sm:
            street_name = STREET_MAP.get(sm.group(1))
            if street_name:
                current_street = street_name
                street_investments = {}
                streets[current_street]["pot"] = round(running_pot / bb_amount) if bb_amount > 0 else 0
            elif sm.group(1) in ("SHOWDOWN", "SUMMARY"):
                current_street = None
            continue

        if current_street is None:
            # Check for blinds before HOLE CARDS
            m = RE_BLIND.match(line)
            if m:
                amt = float(m.group(2))
                running_pot += amt
            continue

        if current_street not in streets:
            continue

        is_hero = False
        action_item = None

        m = RE_RAISE.match(line)
        if m:
            player, to_amt_str = m.group(1), m.group(2)
            is_hero = player == hero_username
            to_amt = float(to_amt_str)
            prev = street_investments.get(player, 0)
            running_pot += to_amt - prev
            street_investments[player] = to_amt
            v = round(to_amt / bb_amount) if bb_amount > 0 else 0
            action_item = ActionItem(a="R", v=v, h=is_hero)
        else:
            m = RE_BET.match(line)
            if m:
                player, amt_str = m.group(1), m.group(2)
                is_hero = player == hero_username
                amt = float(amt_str)
                running_pot += amt
                street_investments[player] = amt
                v = round(amt / bb_amount) if bb_amount > 0 else 0
                action_item = ActionItem(a="B", v=v, h=is_hero)
            else:
                m = RE_CALL.match(line)
                if m:
                    player, amt_str = m.group(1), m.group(2)
                    is_hero = player == hero_username
                    amt = float(amt_str)
                    running_pot += amt
                    street_investments[player] = street_investments.get(player, 0) + amt
                    v = round(amt / bb_amount) if bb_amount > 0 else 0
                    action_item = ActionItem(a="C", v=v, h=is_hero)
                else:
                    m = RE_CHECK.match(line)
                    if m:
                        is_hero = m.group(1) == hero_username
                        action_item = ActionItem(a="X", h=is_hero)
                    else:
                        m = RE_FOLD.match(line)
                        if m:
                            is_hero = m.group(1) == hero_username
                            action_item = ActionItem(a="F", h=is_hero)
                        else:
                            m = RE_BLIND.match(line)
                            if m:
                                amt = float(m.group(2))
                                player = m.group(1)
                                running_pot += amt
                                street_investments[player] = street_investments.get(player, 0) + amt
                                continue

        if action_item:
            streets[current_street]["actions"].append(action_item)

    return streets
