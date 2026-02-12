# Phase 3 — Promote BB Defense, Iso Raise, and Squeeze to Positional Stats

## Goal

Convert BB Defense, Iso Raise, and Squeeze from flat `StatValue` to `PositionalStats` with full positional breakdowns. BB Defense only has meaningful data in the BB column, but positional rendering keeps the visual layout consistent. Iso Raise has meaningful positional variance (iso from BTN vs MP are different spots). Squeeze has positional variance (SB/BB squeeze more than CO).

Then add these to the Preflop positional grid:
- BB Defense as row 15 in the "Defense" group
- Iso Raise as row 5 in the "Entry" group (after Limp)
- Squeeze as row 10 in the "vs Open" group (after 3-Bet OOP)

**Scope**: Backend (models, stats_engine, stat_registry) + Frontend (StatsPage layout, stat-registry, benchmarks).

## Current State

- `HeroStats.bb_defense`: `StatValue` — flat total only
- `HeroStats.iso_raise`: `StatValue` — flat total only
- `HeroStats.squeeze`: `StatValue` — flat total only
- `stats_engine.py`: uses `_sv()` (simple value) for all three
- Backend SQL `_AGG_SQL` already computes `bb_defense`, `bb_defense_opp`, `iso_raise`, `iso_raise_opp`, `squeeze`, `squeeze_opp` — but not grouped by position (the GROUP BY position is there, but the Python code only sums totals via `_sv()`)

## Files to Modify

### 1. `backend/app/models.py`

Change three fields on `HeroStats`:

```python
# Before:
bb_defense: StatValue = StatValue()
iso_raise: StatValue = StatValue()
squeeze: StatValue = StatValue()

# After:
bb_defense: PositionalStats = PositionalStats()
iso_raise: PositionalStats = PositionalStats()
squeeze: PositionalStats = PositionalStats()
```

### 2. `backend/app/stats_engine.py`

Change from `_sv()` to `_pos_stat()` for these three stats:

```python
# Before:
stats.bb_defense = _sv("bb_defense", "bb_defense_opp")
stats.iso_raise = _sv("iso_raise", "iso_raise_opp")

# After:
stats.bb_defense = _pos_stat("bb_defense", "bb_defense_opp")
stats.iso_raise = _pos_stat("iso_raise", "iso_raise_opp")
```

For squeeze, we need a different approach since the SQL already has `squeeze` and `squeeze_opp` counts:

```python
# Before:
stats.squeeze = _sv("squeeze", "squeeze_opp")

# After:
stats.squeeze = _pos_stat("squeeze", "squeeze_opp")
```

No SQL changes needed — `_AGG_SQL` already has `SUM(CASE WHEN hp.squeeze THEN 1 ELSE 0 END)` and the GROUP BY position means each position's counts are already in `by_pos[pos]`. The `_pos_stat()` helper already handles this.

### 3. `frontend/src/lib/api.ts`

Find the `HeroStats` TypeScript interface. Change these three fields from `StatValue` to `PositionalStats`:

```typescript
// Before:
bb_defense: StatValue;
iso_raise: StatValue;
squeeze: StatValue;

// After:
bb_defense: PositionalStats;
iso_raise: PositionalStats;
squeeze: PositionalStats;
```

### 4. `frontend/src/pages/StatsPage.tsx`

#### Add Iso Raise to PosTable

Add after the Limp row (row 4) in the "Entry" group:

```tsx
{
  label: 'Iso Raise',
  cells: [
    { sv: stats.iso_raise.total, statKey: 'iso_raise' },
    { sv: stats.iso_raise.ep, statKey: 'iso_raise', position: 'ep' },
    { sv: stats.iso_raise.mp, statKey: 'iso_raise', position: 'mp' },
    { sv: stats.iso_raise.co, statKey: 'iso_raise', position: 'co' },
    { sv: stats.iso_raise.btn, statKey: 'iso_raise', position: 'btn' },
    { sv: stats.iso_raise.sb, statKey: 'iso_raise', position: 'sb' },
    { sv: stats.iso_raise.bb, statKey: 'iso_raise', position: 'bb' },
  ]
}
```

#### Add Squeeze to PosTable

Add after 3-Bet OOP (row 9) in the "vs Open" group:

```tsx
{
  label: 'Squeeze',
  cells: [
    { sv: stats.squeeze.total, statKey: 'squeeze' },
    { sv: stats.squeeze.ep, statKey: 'squeeze', position: 'ep' },
    // ... mp, co, btn, sb, bb
  ]
}
```

#### Add BB Defense to PosTable

Add as the last row in the "Defense" group (row 15):

```tsx
{
  label: 'BB Defense',
  cells: [
    { sv: stats.bb_defense.total, statKey: 'bb_defense' },
    { sv: stats.bb_defense.ep, statKey: 'bb_defense', position: 'ep' },
    // ... (ep/mp/co/btn/sb will be empty/null — only bb has data)
    { sv: stats.bb_defense.bb, statKey: 'bb_defense', position: 'bb' },
  ]
}
```

#### Add vs Steal Fold to PosTable

Add Fold to Steal as row 14 in the "Defense" group (before BB Defense):

```tsx
{
  label: 'vs Steal Fold',
  cells: [
    { sv: stats.vs_steal_fold.total, statKey: 'fold_to_steal' },
    // ... positional cells (only SB/BB have data)
  ]
}
```

#### Remove from KV grid

Remove BB Defense, Iso Raise, and Squeeze from the KV grid. The KV grid should retain:
- 5-Bet, Call 4-Bet, 4-Bet-Fold, Limp-Fold, 4-Bet Range, Fold to Squeeze
- Win Rate, Win Rate EV, Hands

#### Update any KV grid references

Anywhere the code accesses `stats.bb_defense.value`, `stats.iso_raise.value`, or `stats.squeeze.value`, change to `stats.bb_defense.total.value`, `stats.iso_raise.total.value`, `stats.squeeze.total.value` (since they're now `PositionalStats`, the total is accessed via `.total`).

### 5. `frontend/src/lib/stat-registry.ts`

Update entries:

```typescript
// Before:
bb_defense: { ..., isPositional: false, ... },
iso_raise: { ..., isPositional: false, ... },
squeeze: { ..., isPositional: false, ... },

// After:
bb_defense: { ..., isPositional: true, ... },
iso_raise: { ..., isPositional: true, ... },
squeeze: { ..., isPositional: true, ... },
```

Add `pvp_matrix` widget to `bb_defense`:
```typescript
bb_defense: {
  displayName: 'BB Defense',
  heroStatsField: 'bb_defense',
  isPositional: true,
  widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'],
},
```

Add `pvp_matrix` widget to `squeeze`:
```typescript
squeeze: {
  displayName: 'Squeeze',
  heroStatsField: 'squeeze',
  isPositional: true,
  widgets: ['fold_equity', 'ev_breakdown', 'by_context', 'trend_sparkline'],
},
```

### 6. `frontend/src/lib/benchmarks.ts`

Add benchmarks for BB Defense and Iso Raise:

**BB Defense** (total only — BB-specific):
```typescript
bb_defense: {
  total: { low: 45, high: 60, tipLow: 'Folding BB too much — bleeding antes', tipHigh: 'Defending too wide — losing postflop', fix: 'Defend 50-55% from BB vs single raise. Call wider vs small opens, tighter vs UTG.', weight: 5 },
}
```

**Iso Raise** (total only):
```typescript
iso_raise: {
  total: { low: 5, high: 15, tipLow: 'Not punishing limpers enough', tipHigh: 'Iso-raising too wide', fix: 'Iso-raise 8-12% when facing limps. Widen from BTN/CO, tighten from EP.', weight: 2 },
}
```

### 7. `backend/app/stat_registry.py`

Add registry entries for BB Defense and Iso Raise drill-down (if not already present):

```python
"bb_defense": {
    "name": "BB Defense",
    "action_flag": "bb_defense",
    "opp_flag": "bb_defense_opp",
},
"iso_raise": {
    "name": "Iso Raise",
    "action_flag": "iso_raise",
    "opp_flag": "iso_raise_opp",
},
```

Also add RESPONSE_DECOMPOSITION for bb_defense:

```python
"bb_defense": {
    "opp_sql": "hp.bb_defense_opp = TRUE",
    "fold_sql": "hp.bb_defense IS NOT TRUE AND hp.position = 'BB'",
    "call_sql": "hp.bb_defense = TRUE AND hp.three_bet IS NOT TRUE",
    "raise_sql": "hp.three_bet = TRUE AND hp.position = 'BB'",
},
```

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. Start backend + frontend
3. `GET /api/stats/hero` returns `bb_defense`, `iso_raise`, `squeeze` as objects with `total`, `ep`, `mp`, etc. fields
4. Preflop PosTable shows 15 rows with all groups
5. BB Defense row shows data only in Tot and BB columns (other positions are `--`)
6. Iso Raise shows positional data (BTN/CO should have higher values than EP)
7. Squeeze shows positional data
8. KV grid no longer shows these three stats
9. Each cell is clickable and navigates to drill-down
10. `cd frontend && npm run lint` — no lint errors
