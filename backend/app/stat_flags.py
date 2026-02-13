"""Site-independent stat flag computation.

Computes boolean stat flags (VPIP, PFR, 3-bet, c-bet, etc.) from parsed hand data.
These flags are stored in hand_players and aggregated by stats_engine.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.parsers.ggpoker import ParsedHand


_POS_ORDER = {"SB": 0, "BB": 1, "EP": 2, "MP": 3, "CO": 4, "BTN": 5}


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
            "three_bet_opp_ip": None,
            "four_bet": False,
            "four_bet_opp": False,
            "fold_to_3bet": None,
            "fold_to_4bet": None,
            "open_raise": False,
            "open_raise_opp": False,
            "call_open_raise": False,
            "call_open_raise_opp": False,
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
            "limp_fold": False,
            "four_bet_fold": None,
            "call_4bet": False,
            "is_3bet_pot": False,
            "call_cbet_flop": None,
            "raise_cbet_flop": None,
            "vs_missed_cbet_flop_opp": False,
            "preflop_allin_raise": False,
            "preflop_allin_call": False,
            "postflop_ip": None,
            "bb_defense": None,
            "bb_defense_opp": False,
            "iso_raise": False,
            "iso_raise_opp": False,
            "faced_squeeze": False,
            "fold_to_squeeze": None,
            "pot_type": "SRP",
            "is_multiway": False,
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
    already_invested = set()  # players who limped (can't cold-call an open raise)

    for a in voluntary_preflop:
        uname = a["username"]
        action = a["action"]
        position = username_to_info[uname]["position"]

        # Mark open raise opportunity: pot is unopened (no raise, no limp = RFI)
        if raise_count == 0 and not has_limper:
            player_stats[uname]["open_raise_opp"] = True

        # Steal opportunity: CO/BTN/SB with no raise and no limper before them
        if raise_count == 0 and not has_limper and position in ("CO", "BTN", "SB"):
            player_stats[uname]["steal_opp"] = True

        # Squeeze opportunity: facing open raise with at least one caller already
        if raise_count == 1 and players_who_called:
            player_stats[uname]["squeeze_opp"] = True

        # Call open raise opportunity: facing open raise and didn't limp
        if raise_count == 1 and uname not in already_invested:
            player_stats[uname]["call_open_raise_opp"] = True

        # BB defense opportunity: BB facing a single raise
        if raise_count == 1 and uname == bb_player:
            player_stats[uname]["bb_defense_opp"] = True

        # Iso-raise opportunity: there are limpers and no raise yet (for non-limpers)
        if raise_count == 0 and has_limper and uname not in already_invested:
            player_stats[uname]["iso_raise_opp"] = True

        if action == "fold":
            folded_preflop.add(uname)

            # Check fold to 3bet
            if raise_count == 2 and uname == first_raiser:
                player_stats[uname]["fold_to_3bet"] = True

            # Check fold to 4bet
            if raise_count == 3 and uname == second_raiser:
                player_stats[uname]["fold_to_4bet"] = True

            # Check fold to 5bet (4-bettor folds)
            if raise_count >= 4 and uname == third_raiser:
                player_stats[uname]["four_bet_fold"] = True

            # BB defense: folded to raise
            if player_stats[uname]["bb_defense_opp"] and raise_count == 1:
                player_stats[uname]["bb_defense"] = False

            # Fold to squeeze: first raiser folds to squeeze (3bet with callers)
            if player_stats[uname]["faced_squeeze"]:
                player_stats[uname]["fold_to_squeeze"] = True

            # Check fold to steal (only if steal is still the last raise)
            if player_stats[uname]["faced_steal"] and raise_count == 1:
                player_stats[uname]["fold_to_steal"] = True
            elif player_stats[uname]["faced_steal"] and raise_count > 1:
                # Folded to a re-raise (e.g., 3-bet over steal), not to the steal itself
                player_stats[uname]["fold_to_steal"] = False
            continue

        if action == "call":
            player_stats[uname]["vpip"] = True
            if a["is_all_in"]:
                player_stats[uname]["preflop_allin_call"] = True

            # BB defense: called a raise
            if player_stats[uname]["bb_defense_opp"] and raise_count >= 1:
                player_stats[uname]["bb_defense"] = True

            if raise_count == 0:
                # Calling the big blind = limp
                player_stats[uname]["limp"] = True
                has_caller_or_limper_before_raise = True
                has_limper = True
                already_invested.add(uname)
            elif raise_count == 1:
                # Calling an open raise
                if uname not in already_invested:
                    # Cold-call (not a limp-call)
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
                # Call a squeeze: first raiser calls instead of folding
                if player_stats[uname]["faced_squeeze"]:
                    player_stats[uname]["fold_to_squeeze"] = False
            elif raise_count == 3:
                if uname == second_raiser:
                    player_stats[uname]["fold_to_4bet"] = False
                    player_stats[uname]["call_4bet"] = True
            elif raise_count >= 4:
                if uname == third_raiser:
                    player_stats[uname]["four_bet_fold"] = False

        elif action == "raise":
            player_stats[uname]["vpip"] = True
            player_stats[uname]["pfr"] = True
            if a["is_all_in"]:
                player_stats[uname]["preflop_allin_raise"] = True
            raise_count += 1

            if raise_count == 1:
                first_raiser = uname

                # Open raise (RFI) — only when no limpers before
                if player_stats[uname]["open_raise_opp"]:
                    player_stats[uname]["open_raise"] = True

                # Iso-raise: raised over limpers
                if player_stats[uname]["iso_raise_opp"]:
                    player_stats[uname]["iso_raise"] = True

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

            elif raise_count == 2:
                # 3-bet
                player_stats[uname]["three_bet"] = True
                second_raiser = uname

                # The opener now faces a 3-bet → 4-bet opportunity
                if first_raiser and first_raiser != uname:
                    player_stats[first_raiser]["four_bet_opp"] = True

                # Check if this is a squeeze (3bet when there are callers of the open)
                if players_who_called:
                    player_stats[uname]["squeeze"] = True
                    # First raiser now faces a squeeze
                    if first_raiser and first_raiser != uname:
                        player_stats[first_raiser]["faced_squeeze"] = True

                # BB defense via 3-bet
                if player_stats[uname]["bb_defense_opp"]:
                    player_stats[uname]["bb_defense"] = True

                # Check 3bet vs steal
                if is_steal and player_stats[uname]["faced_steal"]:
                    player_stats[uname]["three_bet_vs_steal"] = True
                    player_stats[uname]["fold_to_steal"] = False

            elif raise_count == 3:
                # 4-bet
                player_stats[uname]["four_bet"] = True
                third_raiser = uname

                # The 3-bettor now faces a 4-bet → 5-bet opportunity
                if second_raiser:
                    player_stats[second_raiser]["five_bet_opp"] = True

                # Opener didn't fold to 3-bet (they 4-bet or action was superseded)
                if uname == first_raiser:
                    player_stats[uname]["fold_to_3bet"] = False
                    # Also didn't fold to squeeze
                    if player_stats[uname]["faced_squeeze"]:
                        player_stats[uname]["fold_to_squeeze"] = False
                elif first_raiser:
                    player_stats[first_raiser]["fold_to_3bet"] = False

            elif raise_count == 4:
                # 5-bet
                player_stats[uname]["five_bet"] = True

                # 3-bettor didn't fold to 4-bet (they 5-bet)
                if uname == second_raiser:
                    player_stats[uname]["fold_to_4bet"] = False

                # 4-bettor didn't fold to 5-bet (they raised again)
                if uname == third_raiser:
                    player_stats[uname]["four_bet_fold"] = False

        elif action in ("bet", "check"):
            # A bet preflop would be unusual, but handle it
            if action == "bet":
                player_stats[uname]["vpip"] = True

    # ── Limp-fold: limped then folded preflop ──
    for s in seats:
        uname = s["username"]
        if player_stats[uname]["limp"] and uname in folded_preflop:
            player_stats[uname]["limp_fold"] = True

    # ── Is 3-bet pot: raise_count >= 2 means a 3-bet occurred ──
    if raise_count >= 2:
        for s in seats:
            player_stats[s["username"]]["is_3bet_pot"] = True

    # ── Pot type: SRP/3BP/4BP/5BP/limped ──
    limpers_exist = any(player_stats[s["username"]]["limp"] for s in seats)
    if raise_count == 0 and limpers_exist:
        pot_type = "limped"
    elif raise_count >= 4:
        pot_type = "5BP"
    elif raise_count >= 3:
        pot_type = "4BP"
    elif raise_count >= 2:
        pot_type = "3BP"
    else:
        pot_type = "SRP"
    for s in seats:
        player_stats[s["username"]]["pot_type"] = pot_type

    # ── Mark 3-bet opp for players between open raise and 3-bet (inclusive) ──
    if first_raiser:
        first_raise_order = _find_action_order(voluntary_preflop, first_raiser, "raise")
        three_bet_order = None
        if second_raiser:
            three_bet_order = _find_action_order(voluntary_preflop, second_raiser, "raise")

        if first_raise_order is not None:
            raiser_pos_order = _POS_ORDER.get(username_to_info[first_raiser]["position"], 0)
            for a in voluntary_preflop:
                if a["order"] > first_raise_order and a["username"] != first_raiser:
                    # Include the 3-bettor themselves (<=), exclude players after
                    if three_bet_order is None or a["order"] <= three_bet_order:
                        player_stats[a["username"]]["three_bet_opp"] = True
                        player_pos_order = _POS_ORDER.get(username_to_info[a["username"]]["position"], 0)
                        player_stats[a["username"]]["three_bet_opp_ip"] = player_pos_order > raiser_pos_order

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
                flop_survivors = players_in_hand - players_folded
                for uname in flop_survivors:
                    player_stats[uname]["saw_flop"] = True
                # is_multiway: 3+ players saw flop
                multiway = len(flop_survivors) >= 3
                if multiway:
                    for s in seats:
                        player_stats[s["username"]]["is_multiway"] = True
                # Compute postflop IP: player with latest position among flop survivors
                if len(flop_survivors) >= 2:
                    max_order = max(_POS_ORDER.get(username_to_info[u]["position"], 0) for u in flop_survivors)
                    for uname in flop_survivors:
                        pos_order = _POS_ORDER.get(username_to_info[uname]["position"], 0)
                        player_stats[uname]["postflop_ip"] = (pos_order == max_order)
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
        donk_before_aggressor = False  # someone bet before the prev aggressor acted

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

            # Detect donk bet before prev aggressor acts (kills cbet opportunity)
            if prev_aggressor and not aggressor_acted and uname != prev_aggressor:
                if action in ("bet", "raise"):
                    donk_before_aggressor = True

            # Cbet: only a "bet" (first aggression) counts, NOT a raise
            if prev_aggressor and uname == prev_aggressor:
                aggressor_acted = True
                if action == "bet":
                    aggressor_bet = True

        # Set cbet stats — only when action checked to the aggressor (no donk bet)
        # If someone bet before the aggressor, they had no cbet opportunity
        # If the aggressor never acted (all-in from prior street), no cbet opportunity
        if prev_aggressor and player_stats[prev_aggressor][f"saw_{street}"] and not donk_before_aggressor and aggressor_acted:
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

        # Donk bet opportunity: all actors before the prev aggressor
        if prev_aggressor:
            for a in street_actions:
                if a["username"] == prev_aggressor:
                    break  # Aggressor acts, no more donk opp
                if a["action"] in ("bet", "check") and a["username"] != prev_aggressor:
                    player_stats[a["username"]][f"donk_bet_{street}_opp"] = True

        # Donk bet: first bet into the previous street's aggressor
        if first_bet_or_raise and first_bet_or_raise["action"] == "bet":
            bettor = first_bet_or_raise["username"]
            if prev_aggressor and bettor != prev_aggressor:
                player_stats[bettor][f"donk_bet_{street}"] = True

        # Fold to cbet: players who face a cbet and fold/call/raise
        if prev_aggressor and aggressor_bet:
            # The cbet happened — check who faced it and folded
            cbet_order = None
            for a in street_actions:
                if a["username"] == prev_aggressor and a["action"] in ("bet", "raise"):
                    cbet_order = a["order"]
                    break
            if cbet_order is not None:
                responded_to_cbet = set()
                for a in street_actions:
                    if a["order"] > cbet_order and a["username"] != prev_aggressor:
                        # Only count first response per player (ignore later actions
                        # like folding to a raise after calling the cbet)
                        if a["username"] in responded_to_cbet:
                            continue
                        responded_to_cbet.add(a["username"])
                        if a["action"] == "fold":
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = True
                        elif a["action"] == "call":
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = False
                            if street == "flop":
                                player_stats[a["username"]]["call_cbet_flop"] = True
                        elif a["action"] == "raise":
                            player_stats[a["username"]][f"fold_to_cbet_{street}"] = False
                            if street == "flop":
                                player_stats[a["username"]]["raise_cbet_flop"] = True

        # vs Missed cbet: when PFR missed cbet, mark other players
        if street == "flop" and prev_aggressor and not aggressor_bet:
            if player_stats[prev_aggressor]["cbet_flop_opp"]:
                for s in seats:
                    uname_other = s["username"]
                    if uname_other != prev_aggressor and player_stats[uname_other]["saw_flop"]:
                        player_stats[uname_other]["vs_missed_cbet_flop_opp"] = True

    return player_stats
