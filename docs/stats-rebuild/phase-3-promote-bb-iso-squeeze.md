# Phase 3 — Promote BB Defense, Iso Raise, and Squeeze to Positional Stats

## Goal

Convert BB Defense, Iso Raise, and Squeeze from flat `StatValue` to `PositionalStats` with full positional breakdowns. BB Defense only has meaningful data in the BB column — the promotion to `PositionalStats` is purely for layout consistency with the positional grid; the real analytical value lives in the response decomposition (call vs 3-bet). Iso Raise has meaningful positional variance (iso from BTN vs MP are different spots). Squeeze has positional variance — BTN and SB squeeze most often because they act after the most potential cold-callers; CO rarely has squeeze opportunities since few players remain to flat behind.

Then add these to the Preflop positional grid:
- Iso Raise as row 5 in the "Entry" group (after Limp)
- Squeeze as row 10 in the "vs Open" group (after 3-Bet OOP)
- BB Defense as the last row in the "Defense" group

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

Change from `_sv()` to `_pos_stat()` for all three stats. The approach is identical for each — no SQL changes needed since `_AGG_SQL` already computes the counts and the GROUP BY position means each position's counts are already in `by_pos[pos]`.

```python
# Before:
stats.bb_defense = _sv("bb_defense", "bb_defense_opp")
stats.iso_raise = _sv("iso_raise", "iso_raise_opp")
stats.squeeze = _sv("squeeze", "squeeze_opp")

# After:
stats.bb_defense = _pos_stat("bb_defense", "bb_defense_opp")
stats.iso_raise = _pos_stat("iso_raise", "iso_raise_opp")
stats.squeeze = _pos_stat("squeeze", "squeeze_opp")
```

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

#### Do NOT duplicate vs Steal Fold here

The existing StatsPage already has a dedicated "vs Steal" PosTable (SB/BB columns with Fold/Call/3-Bet rows). Do not add a redundant "vs Steal Fold" row to the main positional grid — it would duplicate data that already has its own section with better granularity.

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

Add `pvp_matrix` widget to `bb_defense`. Note: `response_distribution` (call vs 3-bet breakdown) is the key widget here — it shows how Hero continues, which is the core coaching question for BB defense. Removed `continuing_range` as it overlaps with `response_distribution`.
```typescript
bb_defense: {
  displayName: 'BB Defense',
  heroStatsField: 'bb_defense',
  isPositional: true,
  widgets: ['response_distribution', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'],
},
```

Add `pvp_matrix` and `fold_equity` widget to `squeeze`:
```typescript
squeeze: {
  displayName: 'Squeeze',
  heroStatsField: 'squeeze',
  isPositional: true,
  widgets: ['fold_equity', 'ev_breakdown', 'pvp_matrix', 'by_context', 'trend_sparkline'],
},
```

Add `fold_equity` widget to `iso_raise` — iso-raising, like squeezing, is fundamentally about fold equity and denying cheap flops:
```typescript
iso_raise: {
  displayName: 'Iso Raise',
  heroStatsField: 'iso_raise',
  isPositional: true,
  widgets: ['fold_equity', 'ev_breakdown', 'by_context', 'trend_sparkline'],
},
```

### 6. `frontend/src/lib/benchmarks.ts`

Add benchmarks for BB Defense and Iso Raise:

**BB Defense** (total only — BB-specific). Note: BB defense includes both calls and 3-bets from the BB vs a single raise. The benchmark should reflect total continuing frequency, not just calls.
```typescript
bb_defense: {
  total: { low: 55, high: 70, tipLow: 'Folding BB too much — surrendering equity you already have invested', tipHigh: 'Defending too wide — calling with hands that lack equity vs opener\'s range', fix: 'Defend 58-65% from BB vs single raise (combined call + 3-bet). Defend wider vs late position opens and smaller sizes, tighter vs EP opens.', weight: 5 },
}
```

**Iso Raise** (total only):
```typescript
iso_raise: {
  total: { low: 5, high: 15, tipLow: 'Not punishing limpers enough — letting weak ranges see cheap flops', tipHigh: 'Iso-raising too wide — building pots OOP or multiway with marginal hands', fix: 'Iso-raise 8-12% overall. From BTN/CO, iso wider (value + equity denial). From EP/MP, stick to value-heavy iso ranges. Size larger with more limpers behind.', weight: 2 },
}
```

**Squeeze** (total + positional):
```typescript
squeeze: {
  total: { low: 5, high: 12, tipLow: 'Not squeezing enough — letting multiway pots develop where your edge shrinks', tipHigh: 'Squeezing too wide — getting called or 4-bet when ranges are strong', fix: 'Squeeze 7-10% overall. Best from BTN/SB where you act after the most cold-callers. Size 3-4x the open when IP, 4-5x OOP. Tighten vs EP opens with multiple callers.', weight: 3 },
  btn: { low: 7, high: 15 },
  sb: { low: 7, high: 14 },
  bb: { low: 5, high: 12 },
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

## Future Consideration: Postflop Bridges

These stats are preflop-only. From a coaching perspective, the most important follow-up question after BB defense or iso-raise is "what happens postflop?" This phase does NOT add postflop stats, but the following would be high-value additions in a future phase:

- **BB Defense postflop**: Donk-bet frequency after defending, check-raise frequency on flop as BB caller, fold-to-cbet after BB defense. These tell you whether a player defends well preflop but bleeds postflop.
- **Iso Raise postflop**: Cbet frequency after iso-raising (should be high since you're the aggressor), win rate in iso pots vs limpers. The key coaching question is "are you profiting from the pots you iso into?"
- **Squeeze postflop**: Fold equity realized (how often squeeze ends it preflop), cbet frequency after squeeze gets called. Squeezes that get called multiway are disaster scenarios.

These bridge stats would be filtered versions of existing postflop flags (cbet, donk, fold-to-cbet) restricted to hands where the corresponding preflop action occurred. No new stat flags needed — just filtered queries.

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. Start backend + frontend
3. `GET /api/stats/hero` returns `bb_defense`, `iso_raise`, `squeeze` as objects with `total`, `ep`, `mp`, etc. fields
4. Preflop PosTable shows rows with all groups (no duplicate vs Steal Fold row)
5. BB Defense row shows data only in Tot and BB columns (other positions are `--`)
6. Iso Raise shows positional data (BTN/CO should have higher values than EP)
7. Squeeze shows positional data (BTN/SB should have highest frequencies)
8. KV grid no longer shows these three stats
9. Each cell is clickable and navigates to drill-down
10. `cd frontend && npm run lint` — no lint errors
