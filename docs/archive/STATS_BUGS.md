# Stats Calculation Bugs — Audit vs H2N Parity

> Audited 2026-02-08. All stats compared against Hand2Note standard definitions.
> After fixing, run rebuild (`POST /api/import/rebuild`) to recompute all flags from stored raw_text.

---

## Critical Bugs

### 1. Aggression Frequency — denominator missing checks and folds

**Symptom:** OHM shows 76/78/84 (flop/turn/river). H2N shows 35/36/40 for similar player profile.

**Current formula** (`stats_engine.py:268`):
```
AFq = (bets + raises) / (bets + raises + calls) × 100
```

**Correct formula (H2N standard):**
```
AFq = (bets + raises) / (bets + raises + calls + checks + folds) × 100
```

**Root cause:** Parser only tracks `{street}_bets`, `{street}_raises`, `{street}_calls`. Does NOT track checks or folds per street. Denominator is ~2x too small.

**Fix:**

1. **Schema** (`db.py`): Add 6 columns to `hand_players`:
   ```sql
   flop_checks INTEGER DEFAULT 0,
   flop_folds INTEGER DEFAULT 0,
   turn_checks INTEGER DEFAULT 0,
   turn_folds INTEGER DEFAULT 0,
   river_checks INTEGER DEFAULT 0,
   river_folds INTEGER DEFAULT 0
   ```

2. **Parser** (`ggpoker.py`): In the postflop action loop (~line 870), add counting for checks and folds:
   ```python
   if action == "check":
       player_stats[uname][f"{street}_checks"] += 1
   elif action == "fold":
       player_stats[uname][f"{street}_folds"] += 1
   ```
   Also add these fields to `player_stats` initialization (~line 633) and the INSERT statement (~line 1061).

3. **Stats engine** (`stats_engine.py:268`): Update `_aggression_freq`:
   ```python
   checks = sum(r.get(f"{street}_checks", 0) or 0 for r in data)
   folds = sum(r.get(f"{street}_folds", 0) or 0 for r in data)
   total = bets + raises + calls + checks + folds
   ```

4. **Migration** (`db.py`): Add ALTER TABLE for existing databases.

---

### 2. Steal % — denominator is all hands instead of steal opportunities

**Symptom:** OHM shows Steal 11/28/19 (total/BTN/SB). H2N shows 53/52/54.

**Current formula** (`stats_engine.py:94`):
```python
stats.steal = _positional_pct(data, "steal_attempted", None, positions=["CO", "BTN", "SB"])
```

`None` opp_flag → denominator = total hands in each position. Should be hands where pot was folded to player.

**Correct formula:**
```
Steal % = steal attempts / hands where pot folded to you in CO/BTN/SB
```

**Also:** Parser marks `steal_attempted = True` even when there are limpers before the raise. H2N definition: steal = open raise from late position when NO limpers and NO raisers before you.

**Fix:**

1. **Schema**: Add `steal_opp BOOLEAN DEFAULT FALSE` to `hand_players`.

2. **Parser** (~line 665): Track whether pot is folded to each player. Before processing each voluntary action, check:
   ```python
   # Before the main loop, track limpers
   has_limper = False

   # Inside the loop, for each player:
   if position in ("CO", "BTN", "SB") and raise_count == 0 and not has_limper:
       player_stats[uname]["steal_opp"] = True

   # When someone limps:
   if action == "call" and raise_count == 0:
       has_limper = True
   ```
   Note: `has_limper` must be tracked PER-ACTION (before the current player acts), not globally at end of loop. Each player only gets `steal_opp` if no one limped before them.

3. **Parser**: Only set `steal_attempted = True` when `steal_opp` is also True:
   ```python
   if raise_count == 1 and player_stats[uname].get("steal_opp"):
       player_stats[uname]["steal_attempted"] = True
   ```

4. **Stats engine**:
   ```python
   stats.steal = _positional_pct(data, "steal_attempted", "steal_opp", positions=["CO", "BTN", "SB"])
   ```

5. **Faced steal**: Update `faced_steal` logic — only mark when the raiser has `steal_opp = True` (true steal, not iso-raise over limpers).

---

### 3. C-Bet counts raises as c-bets

**Symptom:** OHM C-Bet Flop 63. H2N reference 45.

**Root cause** (`ggpoker.py:888`):
```python
if prev_aggressor and uname == prev_aggressor:
    if action in ("bet", "raise"):  # ← "raise" should NOT count
        aggressor_bet = True
```

A continuation bet is the FIRST bet on a street by the previous street's aggressor. GGPoker format: `"bet"` = first aggression on the street, `"raise"` = increasing a prior bet. If someone donks and the aggressor raises, that is NOT a c-bet.

**Fix** (`ggpoker.py:888`): Change condition to only match `"bet"`:
```python
if prev_aggressor and uname == prev_aggressor:
    aggressor_acted = True
    if action == "bet":  # Only first-aggression counts as c-bet
        aggressor_bet = True
```

No schema change needed. Only parser logic.

---

### 4. Donk Bet — wrong denominator

**Symptom:** OHM shows 3/3/3 (all streets identical). H2N shows 0/4/10.

**Current formula** (`stats_engine.py:120`):
```python
stats.donk_bet_flop = _simple_pct([r for r in data if r["saw_flop"]], "donk_bet_flop")
```

Denominator is ALL hands that saw the street. But donk bet opportunity is much rarer: you must be out of position vs the previous street's aggressor and act first.

**Correct formula:**
```
Donk Bet % = donk bets / donk bet opportunities
```

**Fix:**

1. **Schema**: Add `donk_bet_flop_opp`, `donk_bet_turn_opp`, `donk_bet_river_opp` BOOLEAN columns.

2. **Parser**: In the postflop loop, when processing each street, identify players who act before the previous street's aggressor. These players have a donk bet opportunity:
   ```python
   # For each street, find who acts first before the prev aggressor
   if prev_aggressor:
       for a in street_actions:
           if a["username"] == prev_aggressor:
               break  # Aggressor acts, no more donk opp
           if a["action"] in ("bet", "check", "fold"):
               if a["username"] != prev_aggressor:
                   player_stats[a["username"]][f"donk_bet_{street}_opp"] = True
               break  # Only the FIRST actor before aggressor has the opp
   ```

3. **Stats engine**:
   ```python
   stats.donk_bet_flop = _simple_pct(
       [r for r in data if r.get("donk_bet_flop_opp")], "donk_bet_flop"
   )
   ```

---

## Moderate Bugs

### 5. 3-Bet opportunity over-counted

Two issues:

**a) Opener gets `three_bet_opp`** (`ggpoker.py:749`):
```python
elif raise_count == 2:
    if first_raiser:
        player_stats[first_raiser]["three_bet_opp"] = True  # WRONG
```
The opener already raised. They can't 3-bet themselves. Remove this line.

**b) Players acting after the 3-bet get `three_bet_opp`** (`ggpoker.py:791`):
```python
for a in voluntary_preflop:
    if a["order"] > first_raise_order and a["username"] != first_raiser:
        player_stats[a["username"]]["three_bet_opp"] = True
```
This marks ALL players acting after the open, including those acting after the 3-bet. Someone facing a 3-bet has a 4-bet opportunity, not a 3-bet opportunity.

**Fix:** Only mark players between the open raise and the 3-bet:
```python
if first_raiser:
    first_raise_order = _find_action_order(voluntary_preflop, first_raiser, "raise")
    # Find 3-bet order (if any)
    three_bet_order = None
    if second_raiser:
        three_bet_order = _find_action_order(voluntary_preflop, second_raiser, "raise")

    for a in voluntary_preflop:
        if a["order"] > first_raise_order and a["username"] != first_raiser:
            # Only mark if they acted BEFORE the 3-bet (or no 3-bet happened)
            if three_bet_order is None or a["order"] < three_bet_order:
                player_stats[a["username"]]["three_bet_opp"] = True
```

Also remove the `three_bet_opp` assignment at line 749 (inside the `raise_count == 2` block for the first_raiser).

---

### 6. Squeeze % — wrong denominator

**Current:** `_simple_pct(data, "squeeze")` = `squeeze / total_hands`.

**Correct:** `squeeze / squeeze_opportunities`. Opportunity = someone raised, at least one person called, and it's your turn to act.

**Fix:**
1. Add `squeeze_opp BOOLEAN DEFAULT FALSE` to schema.
2. In parser, after someone calls the open raise (raise_count == 1), mark all subsequent players (who haven't acted yet) as having squeeze_opp.
3. Stats engine: `_simple_pct([r for r in data if r.get("squeeze_opp")], "squeeze")`.

---

### 7. 5-Bet % — wrong denominator

**Current:** `_simple_pct(data, "five_bet")` = `five_bet / total_hands`.

**Correct:** `five_bet / five_bet_opportunities`. Opportunity = you face a 4-bet.

**Fix:**
1. Add `five_bet_opp BOOLEAN DEFAULT FALSE` to schema.
2. In parser, when `raise_count == 4`, mark the 4-bettor's target (the 3-bettor) as having `five_bet_opp`.
3. Stats engine: `_simple_pct([r for r in data if r.get("five_bet_opp")], "five_bet")`.

---

## Unimplemented Stats

These stats appear in the H2N layout but have no parser/engine support yet:

| Stat | What It Needs |
|------|---------------|
| Limp-Fold | Parser: `limp_fold BOOLEAN` — set when player limps then folds to a raise |
| 4-Bet-Fold | Parser: `four_bet_fold BOOLEAN` — set when player 4-bets then folds to a 5-bet |
| Call 4-Bet | Parser: `call_4bet BOOLEAN` — set when player calls a 4-bet |
| 4-Bet-Fold (steal) | Reuse `four_bet_fold` filtered to steal hands |
| vs C-Bet Fold/Call/Raise by pot type | Parser: `pot_type VARCHAR` (single_raised / three_bet / four_bet) + split fold_to_cbet into fold/call/raise |
| Missed C-Bet → Fold | Parser: `missed_cbet_then_fold BOOLEAN` — missed c-bet then folded to opponent's bet |
| vs Missed C-Bet (probe) | Parser: `bet_vs_missed_cbet BOOLEAN` — opponent missed c-bet, hero bets |
| Check-Fold vs Missed C-Bet | Parser: `check_fold_vs_missed_cbet BOOLEAN` |

---

## Correct Stats (verified)

These are computed correctly and match H2N definitions:

- VPIP (`vpip / total_hands`)
- PFR (`pfr / total_hands`)
- Open Raise (`open_raise / open_raise_opp`) — correctly uses opportunity denominator
- Fold to 3-Bet (`fold_to_3bet=True / fold_to_3bet!=None`) — tracks opener only
- Fold to 4-Bet (same pattern)
- Call Open Raise (`call_open_raise / total_hands`)
- Limp (`limp / total_hands`)
- 4-Bet Range (`four_bet_count / total_hands`)
- Fold to 3-Bet Steal (correct subset)
- 4-Bet Steal (correct subset)
- vs Steal Fold/Call/3-Bet (`flag / faced_steal` per position)
- Fold to C-Bet F/T/R (correct, but c-bet detection bug #3 may affect which hands qualify)
- Aggression Factor (`(B+R) / C` per street)
- Missed C-Bet (`missed / cbet_opp`)
- Missed C-Bet IP/OOP (correct position subsets)
- WTSD (`went_to_sd / saw_flop`)
- W$SD (`won_at_sd / went_to_sd`)
- WWSF (`won>0 / saw_flop`)
- Win Rate (`sum(won_bb) / hands × 100`)

---

## Execution Order

Recommended fix order (dependencies first):

1. **Schema migration** — add all new columns at once (checks/folds counts, steal_opp, donk_bet_opp, squeeze_opp, five_bet_opp, limp_fold, four_bet_fold, call_4bet, pot_type)
2. **Parser fixes** — all changes to `ggpoker.py` (bugs #1-#5 + new stat flags)
3. **Stats engine fixes** — update formulas in `stats_engine.py`
4. **Rebuild** — `POST /api/import/rebuild` to reparse all hands with corrected logic
5. **Verify** — compare OHM output against H2N for the same hand sample
