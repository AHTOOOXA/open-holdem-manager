# Phase 5 — Check-Raise Stat Flags

## Goal

Add check-raise tracking for all three postflop streets (flop, turn, river). This requires:
1. New DB columns on `hand_players`
2. Detection logic in `stat_flags.py`
3. SQL aggregation in `stats_engine.py`
4. New fields on `HeroStats`
5. Stat registry entries for drill-down
6. Frontend display in the Postflop by-street grid
7. A data rebuild (`/api/import/rebuild`) to backfill existing hands

Check-raise is one of the most important postflop actions and is currently completely untracked.

**Scope**: Full stack — DB schema, stat_flags, stats_engine, models, API, frontend.

## Files to Modify

### 1. `backend/app/db.py` — Add columns

Add 6 new BOOLEAN columns to the `hand_players` table. Add after the existing `raise_cbet_flop BOOLEAN` line (around line 201):

```sql
-- Check-Raise
check_raise_flop BOOLEAN,
check_raise_flop_opp BOOLEAN DEFAULT FALSE,
check_raise_turn BOOLEAN,
check_raise_turn_opp BOOLEAN DEFAULT FALSE,
check_raise_river BOOLEAN,
check_raise_river_opp BOOLEAN DEFAULT FALSE,
```

**Important**: Since DuckDB doesn't support `ALTER TABLE ADD COLUMN IF NOT EXISTS` cleanly, add migration logic in `init_schema()` after the table creation:

```python
# Add check-raise columns if they don't exist
try:
    conn.execute("SELECT check_raise_flop FROM hand_players LIMIT 0")
except duckdb.CatalogException:
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_flop BOOLEAN")
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_flop_opp BOOLEAN DEFAULT FALSE")
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_turn BOOLEAN")
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_turn_opp BOOLEAN DEFAULT FALSE")
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_river BOOLEAN")
    conn.execute("ALTER TABLE hand_players ADD COLUMN check_raise_river_opp BOOLEAN DEFAULT FALSE")
```

### 2. `backend/app/stat_flags.py` — Detection logic

Add check-raise detection to `compute_stat_flags()`. The logic for each street:

```
For each postflop street (flop, turn, river):
  For each player:
    actions_on_street = [a for a in actions if a.street == street and a.player == player]
    other_actions = [a for a in actions if a.street == street and a.player != player]

    # Did this player check first on this street?
    if actions_on_street and actions_on_street[0].type == 'check':
      # Did someone else then bet?
      first_check_order = actions_on_street[0].order
      bet_after_check = any(
        a for a in other_actions
        if a.order > first_check_order and a.type in ('bet', 'raise')
      )
      if bet_after_check:
        check_raise_{street}_opp = True
        # Did this player then raise?
        if len(actions_on_street) > 1 and actions_on_street[1].type == 'raise':
          check_raise_{street} = True
```

**Implementation detail**: In `stat_flags.py`, the `compute_stat_flags()` function receives a `ParsedHand` dataclass. Actions are in `parsed.actions` as a list of `ParsedAction(player, street, action_type, amount, is_all_in, order)`.

Add this after the existing postflop stat computation (after the c-bet/donk-bet section):

```python
# Check-raise detection per street
for street in ['flop', 'turn', 'river']:
    street_actions = [a for a in parsed.actions if a.street == street]
    if not street_actions:
        continue

    for player_name, flags in result.items():
        player_actions = [a for a in street_actions if a.player == player_name]
        if not player_actions:
            continue

        # Player's first action on this street must be a check
        first_action = player_actions[0]
        if first_action.action_type != 'check':
            continue

        # Look for a bet/raise by someone else after the check
        check_order = first_action.order
        opponent_bet = None
        for a in street_actions:
            if a.player != player_name and a.order > check_order and a.action_type in ('bet', 'raise'):
                opponent_bet = a
                break

        if opponent_bet is None:
            continue

        # Player had check-raise opportunity
        flags[f'check_raise_{street}_opp'] = True

        # Did player raise after the opponent bet?
        for a in player_actions:
            if a.order > opponent_bet.order and a.action_type == 'raise':
                flags[f'check_raise_{street}'] = True
                break
```

### 3. `backend/app/api/import_hands.py` — Include in INSERT

In `insert_parsed_hand()`, the stat flags dict is written to `hand_players`. Ensure the new column names are included in the INSERT statement. Find the `INSERT INTO hand_players` SQL and add:

```python
check_raise_flop, check_raise_flop_opp,
check_raise_turn, check_raise_turn_opp,
check_raise_river, check_raise_river_opp,
```

And the corresponding values from the computed flags dict:

```python
flags.get('check_raise_flop'),
flags.get('check_raise_flop_opp', False),
flags.get('check_raise_turn'),
flags.get('check_raise_turn_opp', False),
flags.get('check_raise_river'),
flags.get('check_raise_river_opp', False),
```

### 4. `backend/app/stats_engine.py` — SQL aggregation

Add to `_AGG_SQL` (after the existing aggression counts section):

```sql
-- Check-Raise
SUM(CASE WHEN hp.check_raise_flop_opp THEN 1 ELSE 0 END) as cr_flop_opp,
SUM(CASE WHEN hp.check_raise_flop THEN 1 ELSE 0 END) as cr_flop,
SUM(CASE WHEN hp.check_raise_turn_opp THEN 1 ELSE 0 END) as cr_turn_opp,
SUM(CASE WHEN hp.check_raise_turn THEN 1 ELSE 0 END) as cr_turn,
SUM(CASE WHEN hp.check_raise_river_opp THEN 1 ELSE 0 END) as cr_river_opp,
SUM(CASE WHEN hp.check_raise_river THEN 1 ELSE 0 END) as cr_river,
```

Add computation after aggression stats:

```python
# Check-Raise
stats.check_raise_flop = _sv("cr_flop", "cr_flop_opp")
stats.check_raise_turn = _sv("cr_turn", "cr_turn_opp")
stats.check_raise_river = _sv("cr_river", "cr_river_opp")
```

### 5. `backend/app/models.py` — New fields

Add to `HeroStats` in the Postflop section (after aggression fields):

```python
# Check-Raise
check_raise_flop: StatValue = StatValue()
check_raise_turn: StatValue = StatValue()
check_raise_river: StatValue = StatValue()
```

### 6. `backend/app/stat_registry.py` — Drill-down config

Add STAT_REGISTRY entries:

```python
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

Add EV_BREAKDOWN_CONFIG:

```python
"check_raise_flop": [
    ("Check-Raise", "hp.check_raise_flop = TRUE"),
    ("Check-Call", "hp.check_raise_flop_opp = TRUE AND hp.check_raise_flop IS NOT TRUE AND hp.flop_calls > 0"),
    ("Check-Fold", "hp.check_raise_flop_opp = TRUE AND hp.check_raise_flop IS NOT TRUE AND hp.flop_folds > 0"),
],
"check_raise_turn": [
    ("Check-Raise", "hp.check_raise_turn = TRUE"),
    ("Check-Call", "hp.check_raise_turn_opp = TRUE AND hp.check_raise_turn IS NOT TRUE AND hp.turn_calls > 0"),
    ("Check-Fold", "hp.check_raise_turn_opp = TRUE AND hp.check_raise_turn IS NOT TRUE AND hp.turn_folds > 0"),
],
"check_raise_river": [
    ("Check-Raise", "hp.check_raise_river = TRUE"),
    ("Check-Call", "hp.check_raise_river_opp = TRUE AND hp.check_raise_river IS NOT TRUE AND hp.river_calls > 0"),
    ("Check-Fold", "hp.check_raise_river_opp = TRUE AND hp.check_raise_river IS NOT TRUE AND hp.river_folds > 0"),
],
```

Add FOLD_EQUITY_CONFIG:

```python
"check_raise_flop": {
    "action_sql": "hp.check_raise_flop = TRUE",
    "fold_sql": "...",  # villain folds to the check-raise
},
```

Add SIZING_CONFIG for check-raise sizing:

```python
"check_raise_flop": {
    "filter_sql": "hp.check_raise_flop = TRUE",
    "action_type": "raise",
    "street": "flop",
},
"check_raise_turn": {
    "filter_sql": "hp.check_raise_turn = TRUE",
    "action_type": "raise",
    "street": "turn",
},
```

### 7. `frontend/src/lib/api.ts`

Add to `HeroStats` TypeScript interface:

```typescript
check_raise_flop: StatValue;
check_raise_turn: StatValue;
check_raise_river: StatValue;
```

### 8. `frontend/src/pages/StatsPage.tsx`

Add Check-Raise row to the Postflop by-street grid, in the "Aggression" group (before AF):

```
Group "Aggression":
  Row 7: Check-Raise | check_raise_flop | check_raise_turn | check_raise_river  ← NEW
  Row 8: Aggression  | af_flop          | af_turn          | af_river
  Row 9: Agg Freq    | afq_flop         | afq_turn         | afq_river
  Row 10: Donk Bet   | donk_bet_flop    | donk_bet_turn    | donk_bet_river
```

Each cell in the Check-Raise row:

```tsx
{
  label: 'Check-Raise',
  cells: [
    { sv: stats.check_raise_flop, statKey: 'check_raise_flop' },
    { sv: stats.check_raise_turn, statKey: 'check_raise_turn' },
    { sv: stats.check_raise_river, statKey: 'check_raise_river' },
  ]
}
```

### 9. `frontend/src/lib/stat-registry.ts`

Add entries:

```typescript
check_raise_flop: {
  displayName: 'Check-Raise Flop',
  heroStatsField: 'check_raise_flop',
  isPositional: false,
  widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'ip_oop_split', 'by_context', 'sizing_histogram', 'trend_sparkline'],
},
check_raise_turn: {
  displayName: 'Check-Raise Turn',
  heroStatsField: 'check_raise_turn',
  isPositional: false,
  widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'trend_sparkline'],
},
check_raise_river: {
  displayName: 'Check-Raise River',
  heroStatsField: 'check_raise_river',
  isPositional: false,
  widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'trend_sparkline'],
},
```

### 10. `frontend/src/lib/benchmarks.ts`

Add benchmarks:

```typescript
check_raise_flop: {
  total: { low: 6, high: 12, tipLow: 'Not check-raising enough — villain can bet freely', tipHigh: 'Check-raising too often — getting called by strong hands', fix: 'Check-raise 8-10% on flop. Mix value (sets, two pair) with draws.', weight: 4 },
},
check_raise_turn: {
  total: { low: 5, high: 12, tipLow: 'Passive turn play when checking', tipHigh: 'Over-check-raising turns', fix: 'Check-raise turn 6-10%. Mostly value with some draws.', weight: 3 },
},
check_raise_river: {
  total: { low: 4, high: 10, tipLow: 'Never check-raising rivers — missing value', tipHigh: 'Over-bluffing river check-raises', fix: 'Check-raise river 5-8%. Mostly thin value and polarized bluffs.', weight: 2 },
},
```

## Data Rebuild

After deploying the new columns and stat_flags logic, run a rebuild to backfill:

```
POST /api/import/rebuild
```

This re-parses all stored raw_text through the updated `compute_stat_flags()` pipeline and rewrites all `hand_players` rows with the new check-raise flags.

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all existing tests pass
2. **Add a new test** to `test_parser.py` that verifies check-raise detection:
   - Create a fixture hand where hero checks, villain bets, hero raises on the flop
   - Assert `check_raise_flop = True`, `check_raise_flop_opp = True`
   - Create a hand where hero checks, villain bets, hero calls
   - Assert `check_raise_flop_opp = True`, `check_raise_flop = False` (or NULL)
3. Import existing hands → run rebuild → verify check-raise stats appear
4. `GET /api/stats/hero` returns `check_raise_flop`, `check_raise_turn`, `check_raise_river` with values
5. Postflop grid shows Check-Raise row with data
6. Click check-raise cells → drill-down loads with range heatmap, fold equity widgets
7. `cd frontend && npm run lint` — no lint errors
