"""Site-independent stat flag computation.

Computes boolean stat flags (VPIP, PFR, 3-bet, c-bet, etc.) from parsed hand data.
These flags are stored in hand_players and aggregated by stats_engine.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parsers.ggpoker import ParsedHand


def _find_action_order(actions: list[dict], username: str, action_type: str) -> int | None:
    """Find the order number of a specific player's action."""
    for a in actions:
        if a["username"] == username and a["action"] == action_type:
            return a["order"]
    return None


def compute_stat_flags(parsed: ParsedHand) -> dict[str, dict]:
    """Compute stat flags for each player from parsed hand data.

    Returns dict of username -> stat flags dict. Each dict contains
    boolean flags and integer counts that get stored in hand_players.
    """
    seats = parsed.seats
    actions_by_street = parsed.actions_by_street
    board_cards = parsed.board_cards
    went_to_showdown_players = set(parsed.went_to_showdown_players)  # copy
    in_showdown = parsed.in_showdown
    collected = parsed.collected
    sb_player = parsed.sb_player
    bb_player = parsed.bb_player

    username_to_info = {s["username"]: s for s in seats}

    # Build per-player stat dictionaries
    player_stats = {}
    for s in seats:
        uname = s["username"]
        player_stats[uname] = {
            "vpip": False,
            "pfr": False,
            "three_bet": False,
            "three_bet_opp": False,
            "four_bet": False,
            "four_bet_opp": False,
            "fold_to_3bet": None,
            "fold_to_4bet": None,
            "open_raise": False,
            "open_raise_opp": False,
            "call_open_raise": False,
            "limp": False,
            "squeeze": False,
            "five_bet": False,
            "steal_attempted": False,
            "faced_steal": False,
            "fold_to_steal": None,
            "call_steal": None,
            "three_bet_vs_steal": None,
            "saw_flop": False,
            "saw_turn": False,
            "saw_river": False,
            "went_to_showdown": False,
            "won_at_showdown": None,
            "cbet_flop": None,
            "cbet_flop_opp": False,
            "cbet_turn": None,
            "cbet_turn_opp": False,
            "cbet_river": None,
            "cbet_river_opp": False,
            "fold_to_cbet_flop": None,
            "fold_to_cbet_turn": None,
            "fold_to_cbet_river": None,
            "missed_cbet_flop": False,
            "missed_cbet_turn": False,
            "donk_bet_flop": None,
            "donk_bet_turn": None,
            "donk_bet_river": None,
            "flop_bets": 0,
            "flop_raises": 0,
            "flop_calls": 0,
            "flop_checks": 0,
            "flop_folds": 0,
            "turn_bets": 0,
            "turn_raises": 0,
            "turn_calls": 0,
            "turn_checks": 0,
            "turn_folds": 0,
            "river_bets": 0,
            "river_raises": 0,
            "river_calls": 0,
            "river_checks": 0,
            "river_folds": 0,
            "steal_opp": False,
            "donk_bet_flop_opp": False,
            "donk_bet_turn_opp": False,
            "donk_bet_river_opp": False,
            "squeeze_opp": False,
            "five_bet_opp": False,
        }

    # ── Preflop stat computation ──
    preflop_actions = actions_by_street["preflop"]

    # Filter to voluntary actions only (exclude blinds/antes/straddle)
    voluntary_types = {"fold", "check", "call", "bet", "raise"}
    voluntary_preflop = [a for a in preflop_actions if a["action"] in voluntary_types]

    # Count raises to determine bet levels:
    # posting BB = forced (1-bet), first raise = open raise (2-bet),
    # next raise = 3-bet, etc.
    raise_count = 0  # How many raises have occurred (not counting blinds)
    has_caller_or_limper_before_raise = False
    first_raiser = None
    second_raiser = None  # 3-bettor
    third_raiser = None  # 4-bettor
    is_steal = False

    # Track who has acted voluntarily and who has folded
    folded_preflop = set()
    players_who_called = set()
    has_limper = False

    for a in voluntary_preflop:
        uname = a["username"]
        action = a["action"]
        position = username_to_info[uname]["position"]

        # Mark open raise opportunity: pot is unopened (no raise yet)
        if raise_count == 0:
            player_stats[uname]["open_raise_opp"] = True

        # Steal opportunity: CO/BTN/SB with no raise and no limper before them
        if raise_count == 0 and not has_limper and position in ("CO", "BTN", "SB"):
            player_stats[uname]["steal_opp"] = True

        # Squeeze opportunity: facing open raise with at least one caller already
        if raise_count == 1 and players_who_called:
            player_stats[uname]["squeeze_opp"] = True

        if action == "fold":
            folded_preflop.add(uname)

            # Check fold to 3bet
            if raise_count == 2 and uname == first_raiser:
                player_stats[uname]["fold_to_3bet"] = True

            # Check fold to 4bet
            if raise_count == 3 and uname == second_raiser:
                player_stats[uname]["fold_to_4bet"] = True

            # Check fold to steal
            if player_stats[uname]["faced_steal"]:
                player_stats[uname]["fold_to_steal"] = True
            continue

        if action == "call":
            player_stats[uname]["vpip"] = True

            if raise_count == 0:
                # Calling the big blind = limp
                player_stats[uname]["limp"] = True
                has_caller_or_limper_before_raise = True
                has_limper = True
            elif raise_count == 1:
                # Calling an open raise
                player_stats[uname]["call_open_raise"] = True
                players_who_called.add(uname)

                # After at least one caller of the open, subsequent players have squeeze_opp
                # (set below after this action processes — callers themselves don't have squeeze_opp
                #  since squeeze = raising after a raise + call, which happens on later actions)

                # Check if facing steal
                if player_stats[uname]["faced_steal"]:
                    player_stats[uname]["call_steal"] = True
                    player_stats[uname]["fold_to_steal"] = False
            elif raise_count == 2:
                # Calling a 3bet — if this was the original raiser, not a fold_to_3bet
                if uname == first_raiser:
                    player_stats[uname]["fold_to_3bet"] = False
            elif raise_count == 3:
                if uname == second_raiser:
                    player_stats[uname]["fold_to_4bet"] = False

        elif action == "raise":
            player_stats[uname]["vpip"] = True
            player_stats[uname]["pfr"] = True
            raise_count += 1

            if raise_count == 1:
                # Open raise (2-bet)
                player_stats[uname]["open_raise"] = True
                first_raiser = uname

                # Check if steal attempt (open raise from CO, BTN, or SB with no limpers)
                if player_stats[uname]["steal_opp"]:
                    player_stats[uname]["steal_attempted"] = True
                    is_steal = True

                    # Mark BB (and SB if steal from CO/BTN) as facing steal
                    if bb_player and bb_player not in folded_preflop:
                        player_stats[bb_player]["faced_steal"] = True
                    if position in ("CO", "BTN"):
                        if sb_player and sb_player not in folded_preflop:
                            player_stats[sb_player]["faced_steal"] = True

                # If there were limpers before, everyone after who raises
                # still gets open_raise = True since it's the first raise.
                # But if there was a limp + raise, the raise is still an open raise.
                # Squeeze: raise when there was already a raise AND at least one caller
                # This is actually the first raise, so no squeeze here.

            elif raise_count == 2:
                # 3-bet
                player_stats[uname]["three_bet"] = True
                second_raiser = uname

                # Check if this is a squeeze (3bet when there are callers of the open)
                if players_who_called:
                    player_stats[uname]["squeeze"] = True

                # Check 3bet vs steal
                if is_steal and player_stats[uname]["faced_steal"]:
                    player_stats[uname]["three_bet_vs_steal"] = True
                    player_stats[uname]["fold_to_steal"] = False

            elif raise_count == 3:
                # 4-bet
                player_stats[uname]["four_bet"] = True
                third_raiser = uname

                # The 3-bettor had a 4bet opportunity
                if second_raiser:
                    player_stats[second_raiser]["four_bet_opp"] = True

                # The 3-bettor now faces a 4-bet → 5-bet opportunity
                if second_raiser:
                    player_stats[second_raiser]["five_bet_opp"] = True

                # The original raiser also sees this — not a fold_to_3bet
                if first_raiser and first_raiser != uname:
                    player_stats[first_raiser]["fold_to_3bet"] = False

            elif raise_count == 4:
                # 5-bet
                player_stats[uname]["five_bet"] = True

        elif action in ("bet", "check"):
            # A bet preflop would be unusual, but handle it
            if action == "bet":
                player_stats[uname]["vpip"] = True

    # ── Mark 3-bet opp for players between open raise and 3-bet ──
    if first_raiser:
        first_raise_order = _find_action_order(voluntary_preflop, first_raiser, "raise")
        three_bet_order = None
        if second_raiser:
            three_bet_order = _find_action_order(voluntary_preflop, second_raiser, "raise")

        if first_raise_order is not None:
            for a in voluntary_preflop:
                if a["order"] > first_raise_order and a["username"] != first_raiser:
                    # Only mark if they acted BEFORE the 3-bet (or no 3-bet happened)
                    if three_bet_order is None or a["order"] < three_bet_order:
                        player_stats[a["username"]]["three_bet_opp"] = True

    # ── Mark faced_steal fold defaults ──
    for s in seats:
        uname = s["username"]
        if player_stats[uname]["faced_steal"] and player_stats[uname]["fold_to_steal"] is None:
            # They faced a steal but didn't fold, call, or 3bet — they must have folded
            # (this shouldn't happen if all actions were tracked, but as safety)
            if uname in folded_preflop:
                player_stats[uname]["fold_to_steal"] = True
            else:
                player_stats[uname]["fold_to_steal"] = False

    # ── Determine who saw each street ──
    players_in_hand = set(s["username"] for s in seats)
    players_folded = set()

    for street in ["preflop", "flop", "turn", "river"]:
        for a in actions_by_street[street]:
            if a["action"] == "fold":
                players_folded.add(a["username"])

        if street == "preflop":
            # Players who didn't fold preflop saw the flop (if flop was dealt)
            if board_cards["flop"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_flop"] = True
        elif street == "flop":
            if board_cards["turn"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_turn"] = True
        elif street == "turn":
            if board_cards["river"]:
                for uname in players_in_hand - players_folded:
                    player_stats[uname]["saw_river"] = True

    # ── Showdown stats ──
    # Determine who went to showdown
    # Only a real showdown if 2+ players remain (GGPoker shows *** SHOWDOWN *** even for no-contest pots)
    remaining_players = players_in_hand - players_folded
    real_showdown = len(remaining_players) >= 2 and (in_showdown or went_to_showdown_players)
    if real_showdown:
        for uname in remaining_players:
            player_stats[uname]["went_to_showdown"] = True
            went_to_showdown_players.add(uname)

    for uname in went_to_showdown_players:
        if uname in collected:
            player_stats[uname]["won_at_showdown"] = True
        else:
            player_stats[uname]["won_at_showdown"] = False

    # ── Postflop stats (cbet, donk bet, aggression counts) ──
    # Determine preflop aggressor (last raiser preflop)
    preflop_aggressor = None
    for a in reversed(preflop_actions):
        if a["action"] == "raise":
            preflop_aggressor = a["username"]
            break

    # Track last aggressor per street for cbet continuation
    street_aggressor = {"preflop": preflop_aggressor}

    for street in ["flop", "turn", "river"]:
        street_actions = actions_by_street[street]
        if not street_actions:
            continue

        # Determine who is the previous-street aggressor for cbet
        prev_street = {"flop": "preflop", "turn": "flop", "river": "turn"}[street]
        prev_aggressor = street_aggressor.get(prev_street)

        first_bet_or_raise = None
        aggressor_acted = False
        aggressor_bet = False

        for a in street_actions:
            uname = a["username"]
            action = a["action"]

            # Aggression counts (including checks and folds for AFq)
            if action == "bet":
                player_stats[uname][f"{street}_bets"] += 1
            elif action == "raise":
                player_stats[uname][f"{street}_raises"] += 1
            elif action == "call":
                player_stats[uname][f"{street}_calls"] += 1
            elif action == "check":
                player_stats[uname][f"{street}_checks"] += 1
            elif action == "fold":
                player_stats[uname][f"{street}_folds"] += 1

            # Track who bet/raised first for cbet and donk
            if action in ("bet", "raise") and first_bet_or_raise is None:
                first_bet_or_raise = a

            # Cbet: only a "bet" (first aggression) counts, NOT a raise (Bug #3)
            if prev_aggressor and uname == prev_aggressor:
                aggressor_acted = True
                if action == "bet":
                    aggressor_bet = True

        # Set cbet stats
        if prev_aggressor and prev_aggressor in (players_in_hand - players_folded):
            # Only if the previous aggressor saw this street
            if player_stats[prev_aggressor][f"saw_{street}"]:
                player_stats[prev_aggressor][f"cbet_{street}_opp"] = True
                if aggressor_bet:
                    player_stats[prev_aggressor][f"cbet_{street}"] = True
                    street_aggressor[street] = prev_aggressor
                else:
                    player_stats[prev_aggressor][f"cbet_{street}"] = False
                    if street in ("flop", "turn"):
                        player_stats[prev_aggressor][f"missed_cbet_{street}"] = True

        # Track who the last aggressor was on this street
        for a in reversed(street_actions):
            if a["action"] in ("bet", "raise"):
                street_aggressor[street] = a["username"]
                break

        # Donk bet opportunity: first actor before the prev aggressor
        if prev_aggressor:
            for a in street_actions:
                if a["username"] == prev_aggressor:
                    break  # Aggressor acts, no more donk opp
                if a["action"] in ("bet", "check", "fold") and a["username"] != prev_aggressor:
                    player_stats[a["username"]][f"donk_bet_{street}_opp"] = True
                    break  # Only the FIRST actor before aggressor has the opp

        # Donk bet: first bet into the previous street's aggressor
        if first_bet_or_raise and first_bet_or_raise["action"] == "bet":
            bettor = first_bet_or_raise["username"]
            if prev_aggressor and bettor != prev_aggressor:
                player_stats[bettor][f"donk_bet_{street}"] = True

        # Fold to cbet: players who face a cbet and fold
        if prev_aggressor and aggressor_bet:
            # The cbet happened — check who faced it and folded
            cbet_order = None
            for a in street_actions:
                if a["username"] == prev_aggressor and a["action"] in ("bet", "raise"):
                    cbet_order = a["order"]
                    break
            if cbet_order is not None:
                for a in street_actions:
                    if a["order"] > cbet_order and a["username"] != prev_aggressor:
                        if a["action"] == "fold":
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = True
                        elif a["action"] in ("call", "raise"):
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = False

    return player_stats
