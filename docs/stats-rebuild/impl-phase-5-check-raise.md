# Phase 5 Implementation — Check-Raise Stat Flags (Flop / Turn / River)

## Goal

Add check-raise tracking for all three postflop streets (flop, turn, river). Check-raise is one of the most important postflop actions and is currently completely untracked. It is primarily an OOP action: the player checks, an opponent bets, and the player then raises. Since the checker acts first, check-raising is almost exclusively done out of position (typically from the blinds). This means IP/OOP splits are unnecessary for this stat — the opportunity itself implies OOP play.

This is a full-stack change touching 10 files across backend and frontend: DB schema, stat flag detection, import pipeline, stats engine, API models, stat registry (backend + frontend), benchmarks, and frontend display. Requires a data rebuild after deployment.

---

## Detection Logic

For each postflop street (flop, turn, river), for each player:

1. Get the player's actions on that street, ordered by action order
2. If the player's **first action** is a `check`:
   a. Scan subsequent actions on the same street for an opponent `bet` or `raise` after the check
   b. If an opponent bet/raise is found: **check-raise opportunity** (`check_raise_{street}_opp = True`)
   c. Then scan the player's subsequent actions for a `raise` after the opponent bet
   d. If the player raised: **check-raise executed** (`check_raise_{street} = True`)

Key details:
- Only the **first** action matters. If a player bets first, they cannot check-raise on that street.
- The opponent action must come **after** the check (by action order). Multiple opponents checking before a bet is fine — the opportunity triggers when any opponent bets.
- The player's raise must come **after** the opponent's bet (by action order).
- A player who checks, faces a bet, and then calls or folds has the opportunity (`_opp = True`) but did not check-raise (`check_raise_{street}` stays `None`/`False`).

---

## Files to Modify

### 1. `backend/app/db.py` — Add 6 columns + migration

Add 6 new BOOLEAN columns to the `hand_players` CREATE TABLE statement. Insert after the `raise_cbet_flop BOOLEAN,` line (around line 203):

```sql
-- Check-Raise
check_raise_flop BOOLEAN,
check_raise_flop_opp BOOLEAN DEFAULT FALSE,
check_raise_turn BOOLEAN,
check_raise_turn_opp BOOLEAN DEFAULT FALSE,
check_raise_river BOOLEAN,
check_raise_river_opp BOOLEAN DEFAULT FALSE,
```

Add migration logic in the existing migration loop (the `for col, default in [...]` block starting around line 280). Append these 6 entries:

```python
("check_raise_flop", "BOOLEAN"),
("check_raise_flop_opp", "BOOLEAN DEFAULT FALSE"),
("check_raise_turn", "BOOLEAN"),
("check_raise_turn_opp", "BOOLEAN DEFAULT FALSE"),
("check_raise_river", "BOOLEAN"),
("check_raise_river_opp", "BOOLEAN DEFAULT FALSE"),
```

This follows the existing migration pattern: `ALTER TABLE ADD COLUMN` wrapped in `try/except duckdb.CatalogException: pass`.

### 2. `backend/app/stat_flags.py` — Detection logic

Add check-raise flags to the initial per-player stat dictionary (around line 126, after `"is_multiway": False`):

```python
"check_raise_flop": None,
"check_raise_flop_opp": False,
"check_raise_turn": None,
"check_raise_turn_opp": False,
"check_raise_river": None,
"check_raise_river_opp": False,
```

Add the check-raise detection block at the end of `compute_stat_flags()`, after the existing postflop loop (after line 575, before `return player_stats`):

```python
# ── Check-raise detection per street ──
for street in ["flop", "turn", "river"]:
    street_actions = actions_by_street[street]
    if not street_actions:
        continue

    for player_name, flags in player_stats.items():
        player_actions = [a for a in street_actions if a["username"] == player_name]
        if not player_actions:
            continue

        # Player's first action on this street must be a check
        first_action = player_actions[0]
        if first_action["action"] != "check":
            continue

        # Look for a bet/raise by an opponent after the check
        check_order = first_action["order"]
        opponent_bet = None
        for a in street_actions:
            if a["username"] != player_name and a["order"] > check_order and a["action"] in ("bet", "raise"):
                opponent_bet = a
                break

        if opponent_bet is None:
            continue

        # Player had check-raise opportunity
        flags[f"check_raise_{street}_opp"] = True

        # Did player raise after the opponent bet?
        for a in player_actions:
            if a["order"] > opponent_bet["order"] and a["action"] == "raise":
                flags[f"check_raise_{street}"] = True
                break
```

**Important implementation note**: The actions in `stat_flags.py` use the `actions_by_street` dict format with `"username"`, `"action"`, `"order"` keys — NOT the `ParsedAction` dataclass. The pseudocode in the planning doc used `a.player` and `a.action_type` but the actual code uses `a["username"]` and `a["action"]`. The implementation above uses the correct dict-style access.

### 3. `backend/app/api/import_hands.py` — Include in INSERT columns

Add the 6 new keys to the `_STAT_FLAG_KEYS` tuple (around line 49). Insert after `"fold_to_squeeze",` (line 69):

```python
"check_raise_flop", "check_raise_flop_opp",
"check_raise_turn", "check_raise_turn_opp",
"check_raise_river", "check_raise_river_opp",
```

No other changes needed in this file. The existing loop `for k in _STAT_FLAG_KEYS: hp_cols[k].append(ps[k])` (line 351-352) handles the rest automatically.

### 4. `backend/app/stats_engine.py` — SQL aggregation + stat computation

Add to `_AGG_SQL` after the aggression counts section (after line 150, before `-- BB Defense`):

```sql
-- Check-Raise
SUM(CASE WHEN hp.check_raise_flop_opp THEN 1 ELSE 0 END) as cr_flop_opp,
SUM(CASE WHEN hp.check_raise_flop THEN 1 ELSE 0 END) as cr_flop,
SUM(CASE WHEN hp.check_raise_turn_opp THEN 1 ELSE 0 END) as cr_turn_opp,
SUM(CASE WHEN hp.check_raise_turn THEN 1 ELSE 0 END) as cr_turn,
SUM(CASE WHEN hp.check_raise_river_opp THEN 1 ELSE 0 END) as cr_river_opp,
SUM(CASE WHEN hp.check_raise_river THEN 1 ELSE 0 END) as cr_river,
```

Add stat computation after the aggression stats section (after line 429, after `stats.afq_river = _afq("river")`):

```python
# Check-Raise
stats.check_raise_flop = _sv("cr_flop", "cr_flop_opp")
stats.check_raise_turn = _sv("cr_turn", "cr_turn_opp")
stats.check_raise_river = _sv("cr_river", "cr_river_opp")
```

### 5. `backend/app/models.py` — 3 new StatValue fields

Add to `HeroStats` in the Postflop section (after the aggression fields, around line 134, after `afq_river`):

```python
# Check-Raise
check_raise_flop: StatValue = StatValue()
check_raise_turn: StatValue = StatValue()
check_raise_river: StatValue = StatValue()
```

### 6. `backend/app/stat_registry.py` — All registry configs

#### STAT_REGISTRY entries

Add after the donk bet entries (after `"donk_bet_river"`, around line 230):

```python
# ── Postflop: Check-Raise ──
"check_raise_flop": {
    "name": "Check-Raise Flop",
    "action_flag": "check_raise_flop",
    "opp_flag": "check_raise_flop_opp",
},
"check_raise_turn": {
    "name": "Check-Raise Turn",
    "action_flag": "check_raise_turn",
    "opp_flag": "check_raise_turn_opp",
},
"check_raise_river": {
    "name": "Check-Raise River",
    "action_flag": "check_raise_river",
    "opp_flag": "check_raise_river_opp",
},
```

#### RESPONSE_DECOMPOSITION entries

Add after the existing entries (around line 405). This decomposes what hero does when facing a check-raise opportunity (checked, opponent bet into hero). The three responses are: fold, call, or raise (check-raise).

```python
"check_raise_flop": {
    "opp_sql": "hp.check_raise_flop_opp = TRUE",
    "fold_sql": "hp.flop_folds > 0 AND hp.check_raise_flop IS NOT TRUE",
    "raise_sql": "hp.check_raise_flop = TRUE",
},
"check_raise_turn": {
    "opp_sql": "hp.check_raise_turn_opp = TRUE",
    "fold_sql": "hp.turn_folds > 0 AND hp.check_raise_turn IS NOT TRUE",
    "raise_sql": "hp.check_raise_turn = TRUE",
},
"check_raise_river": {
    "opp_sql": "hp.check_raise_river_opp = TRUE",
    "fold_sql": "hp.river_folds > 0 AND hp.check_raise_river IS NOT TRUE",
    "raise_sql": "hp.check_raise_river = TRUE",
},
```

#### EV_BREAKDOWN_CONFIG entries

Add after the existing entries (around line 490). This decomposes what happens *after* hero check-raises — did villain fold (fold-through) or call/continue?

```python
"check_raise_flop": [
    ("Fold-through", "hp.check_raise_flop = TRUE AND hp.saw_turn IS NOT TRUE"),
    ("Called", "hp.check_raise_flop = TRUE AND hp.saw_turn = TRUE"),
],
"check_raise_turn": [
    ("Fold-through", "hp.check_raise_turn = TRUE AND hp.saw_river IS NOT TRUE"),
    ("Called", "hp.check_raise_turn = TRUE AND hp.saw_river = TRUE"),
],
"check_raise_river": [
    ("Fold-through", "hp.check_raise_river = TRUE AND hp.went_to_showdown IS NOT TRUE"),
    ("Called", "hp.check_raise_river = TRUE AND hp.went_to_showdown = TRUE"),
],
```

#### SIZING_CONFIG entries

Add after existing entries (around line 498). This powers the sizing histogram widget showing how large hero's check-raises are.

```python
"check_raise_flop": ("hp.check_raise_flop = TRUE", "a.action_type = 'raise'"),
"check_raise_turn": ("hp.check_raise_turn = TRUE", "a.action_type = 'raise'"),
"check_raise_river": ("hp.check_raise_river = TRUE", "a.action_type = 'raise'"),
```

**Note**: `FOLD_EQUITY_CONFIG` is NOT applicable to check-raise. Fold equity is useful for initiating actions (3-bet, squeeze, open raise) where hero puts in aggression first. Check-raise is a reactive raise against a bet — the "did villain fold?" information is already captured in the EV_BREAKDOWN_CONFIG fold-through scenario.

#### BY_CONTEXT_CONFIG entries

Add after existing entries (around line 592). This shows check-raise frequency broken down by which opponent position bet into hero.

```python
"check_raise_flop": {
    "dimension": "bettor_position",
    "action_sql": "hp.check_raise_flop = TRUE",
    "opp_sql": "hp.check_raise_flop_opp = TRUE",
    "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.flop_bets > 0 AND v.player_id != hp.player_id",
    "group_expr": "v.position",
},
"check_raise_turn": {
    "dimension": "bettor_position",
    "action_sql": "hp.check_raise_turn = TRUE",
    "opp_sql": "hp.check_raise_turn_opp = TRUE",
    "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.turn_bets > 0 AND v.player_id != hp.player_id",
    "group_expr": "v.position",
},
"check_raise_river": {
    "dimension": "bettor_position",
    "action_sql": "hp.check_raise_river = TRUE",
    "opp_sql": "hp.check_raise_river_opp = TRUE",
    "join": "JOIN hand_players v ON v.hand_id = hp.hand_id AND v.river_bets > 0 AND v.player_id != hp.player_id",
    "group_expr": "v.position",
},
```

### 7. `frontend/src/lib/api.ts` — 3 new HeroStats fields

Add to the `HeroStats` interface (after `afq_river`, around line 137):

```typescript
check_raise_flop: StatValue;
check_raise_turn: StatValue;
check_raise_river: StatValue;
```

### 8. `frontend/src/pages/StatsPage.tsx` — Add Check-Raise row

Add a Check-Raise row to the Postflop by-street grid. Insert **before** the Aggression row (before line 807). The resulting ordering in the Aggression group will be:

```
Check-Raise | check_raise_flop | check_raise_turn | check_raise_river   <-- NEW
Aggression  | af_flop          | af_turn          | af_river
Agg Freq    | afq_flop         | afq_turn         | afq_river
Donk Bet    | donk_bet_flop    | donk_bet_turn    | donk_bet_river
```

The new row object:

```tsx
{
  label: 'Check-Raise',
  cells: [
    { sv: stats.check_raise_flop, statKey: 'check_raise_flop', drillKey: 'check_raise_flop' },
    { sv: stats.check_raise_turn, statKey: 'check_raise_turn', drillKey: 'check_raise_turn' },
    { sv: stats.check_raise_river, statKey: 'check_raise_river', drillKey: 'check_raise_river' },
  ],
},
```

Each cell includes `statKey` (for benchmark health coloring) and `drillKey` (for click-through to drill-down detail page).

### 9. `frontend/src/lib/stat-registry.ts` — 3 entries

Add after the donk bet entries (after `donk_bet_river`, around line 81):

```typescript
// Check-Raise
check_raise_flop: {
  displayName: 'Check-Raise Flop',
  heroStatsField: 'check_raise_flop',
  isPositional: false,
  widgets: ['range_heatmap', 'response_distribution', 'ev_breakdown', 'by_context', 'sizing_histogram', 'trend_sparkline'],
},
check_raise_turn: {
  displayName: 'Check-Raise Turn',
  heroStatsField: 'check_raise_turn',
  isPositional: false,
  widgets: ['range_heatmap', 'response_distribution', 'ev_breakdown', 'by_context', 'sizing_histogram', 'trend_sparkline'],
},
check_raise_river: {
  displayName: 'Check-Raise River',
  heroStatsField: 'check_raise_river',
  isPositional: false,
  widgets: ['range_heatmap', 'response_distribution', 'ev_breakdown', 'by_context', 'sizing_histogram', 'trend_sparkline'],
},
```

Widget selection rationale:
- `range_heatmap`: shows which combos hero check-raises with
- `response_distribution`: fold/call/raise breakdown when hero has the opportunity
- `ev_breakdown`: profitability split by fold-through vs called
- `by_context`: check-raise frequency by opponent bettor position
- `sizing_histogram`: distribution of check-raise sizes
- `trend_sparkline`: frequency trend over time

Not included:
- `positional_bar`: not needed since check-raise is inherently an OOP action (opportunity implies OOP)
- `fold_equity`: not applicable (fold equity is for initiating aggression, not reactive raises)
- `composition`/`money_burned`/`postflop_bridge`: not relevant for this stat type

### 10. `frontend/src/lib/benchmarks.ts` — Display names + benchmarks

Add to `STAT_DISPLAY_NAMES`:

```typescript
check_raise_flop: 'Check-Raise Flop',
check_raise_turn: 'Check-Raise Turn',
check_raise_river: 'Check-Raise River',
```

Add to `BENCHMARKS`:

```typescript
check_raise_flop: {
  total: {
    low: 7, high: 12,
    tipLow: 'Not check-raising enough — villain can c-bet freely without punishment.',
    tipHigh: 'Check-raising too often — getting called or re-raised by strong hands.',
    fix: 'Target 8-11% flop check-raise. Balance value (sets, two pair, overpairs) with semi-bluffs (flush draws, OESDs).',
    weight: 4,
    statFlagFilter: 'check_raise_flop',
    oppFlagFilter: 'check_raise_flop_opp',
  },
},
check_raise_turn: {
  total: {
    low: 6, high: 11,
    tipLow: 'Too passive on the turn after checking. Letting villain barrel cheaply.',
    tipHigh: 'Over-check-raising turns. Villain adjusts by checking back more.',
    fix: 'Target 7-10% turn check-raise. Shift toward more value and fewer bluffs than flop.',
    weight: 3,
    statFlagFilter: 'check_raise_turn',
    oppFlagFilter: 'check_raise_turn_opp',
  },
},
check_raise_river: {
  total: {
    low: 5, high: 10,
    tipLow: 'Never check-raising rivers — missing value from strong hands.',
    tipHigh: 'Over-bluffing river check-raises — villain calls with bluff-catchers.',
    fix: 'Target 6-9% river check-raise. Should be polarized: nuts or air. No thin value — villain calls or folds.',
    weight: 2,
    statFlagFilter: 'check_raise_river',
    oppFlagFilter: 'check_raise_river_opp',
  },
},
```

Benchmark ranges rationale:
- **Flop 7-12%**: Most check-raise opportunities occur on the flop. GTO solutions show ~8-12% check-raise frequency depending on board texture and position matchup. Low weight (4) since this is a core leak indicator.
- **Turn 6-11%**: Fewer opportunities. Check-raise range should shift toward more value. Slightly lower floor.
- **River 5-10%**: Fewest opportunities. River check-raises should be highly polarized (nuts or bluffs). Lower weight (2) since sample sizes are smallest.

---

## Data Rebuild

After deploying all changes, a rebuild is required to backfill the 6 new columns for existing hands:

```bash
# Via API
curl -X POST http://localhost:8000/api/import/rebuild

# Or via the Upload page "Rebuild" button in the UI
```

The rebuild re-parses all stored `raw_text` through the updated `compute_stat_flags()` pipeline and rewrites all `hand_players` rows with the new check-raise flags.

**Expected rebuild time**: ~13k hands takes approximately 15-30 seconds depending on hardware.

---

## Test Checklist

### Existing tests

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all existing 11 tests pass (new stat flags are additive, no existing behavior changes)

### New test: `TestCheckRaise` class

Add a new test class to `backend/tests/test_parser.py` with a fixture hand that exercises check-raise detection. Suggested test cases:

#### Test 1: Check-raise executed on flop

Create a fixture where hero (BB) checks flop, villain (BTN) bets, hero raises.

Expected:
- `check_raise_flop_opp = True` (hero had the opportunity)
- `check_raise_flop = True` (hero executed the check-raise)

#### Test 2: Check-raise opportunity but hero calls (no check-raise)

Create a fixture where hero (BB) checks flop, villain bets, hero calls.

Expected:
- `check_raise_flop_opp = True` (hero had the opportunity)
- `check_raise_flop` is `None` or not `True` (hero did not check-raise)

#### Test 3: No check-raise opportunity (checked through)

Create a fixture where hero (BB) checks flop, villain checks behind (no bet).

Expected:
- `check_raise_flop_opp = False` (no opponent bet after hero's check = no opportunity)
- `check_raise_flop` is `None` (no opportunity, so no action possible)

#### Test 4: Check-raise on turn (multi-street)

Create a fixture where hero checks turn, villain bets, hero raises.

Expected:
- `check_raise_turn_opp = True`
- `check_raise_turn = True`
- `check_raise_flop_opp` and `check_raise_flop` are independent (may or may not be set depending on flop action)

#### Implementation approach for test fixtures

Either:
- **Option A**: Create a new fixture file `backend/tests/fixtures/check_raise.txt` with a hand history where BB check-raises the flop. Craft the raw text to include the action sequence: BB checks, BTN bets, BB raises.
- **Option B**: Use an existing fixture and assert that check-raise flags are correctly `False`/`None` where no check-raise occurred (negative test), then add a minimal fixture for the positive case.

Option A is recommended since it directly tests the core detection logic with a positive case.

### Integration verification

2. `cd frontend && npm run lint` -- no lint errors
3. Start dev (`make dev`) and load the Stats page
4. Postflop by-street grid shows a new "Check-Raise" row with Flop / Turn / River columns
5. Check-Raise Flop shows a percentage in the 7-12% range (if data exists)
6. Check-Raise Turn and River show percentages or `--` with small sample subscripts
7. Click any check-raise cell to navigate to the drill-down detail page
8. Drill-down shows these widgets: range heatmap, response distribution, EV breakdown, by-context, sizing histogram, trend sparkline
9. Response distribution shows fold/call/raise breakdown for check-raise opportunities
10. By-context widget shows check-raise frequency grouped by bettor position
11. EV breakdown shows fold-through vs called profitability
12. Sizing histogram shows distribution of check-raise sizes
13. `GET /api/stats/hero` returns `check_raise_flop`, `check_raise_turn`, `check_raise_river` with populated `value` and `sample` fields
14. After rebuild (`POST /api/import/rebuild`), check-raise stats appear for all hands

### Sanity check on values

After rebuild with real data:

| Stat | Expected Range | Notes |
|------|---------------|-------|
| Check-Raise Flop | 7-12% | Most common. Opportunity count should be significant (hero sees flop OOP often in Rush & Cash) |
| Check-Raise Turn | 6-11% | Fewer opportunities than flop |
| Check-Raise River | 5-10% | Fewest opportunities. Should show `--` if sample is too small |

If check-raise flop shows 0% or >20%, investigate the detection logic. Common issues:
- Action order not matching (ensure `order` field is correctly compared)
- Action type mismatch (`"check"` vs `"Check"` -- should be lowercase in parser output)
- Opponent bet not detected (ensure the scan looks at all players, not just one specific opponent)
