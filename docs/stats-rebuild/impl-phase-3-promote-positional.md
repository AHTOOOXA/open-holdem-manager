# Phase 3 Implementation — Promote BB Defense, Iso Raise, and Squeeze to PositionalStats

## Goal

Convert `bb_defense`, `iso_raise`, and `squeeze` from flat `StatValue` to `PositionalStats` with per-position breakdowns (EP/MP/CO/BTN/SB/BB). Then add all three as rows in the Preflop positional grid and remove them from the KV grid.

The backend SQL (`_AGG_SQL`) already computes the counts grouped by position -- the Python code just needs to switch from `_sv()` (totals only) to `_pos_stat()` (positional breakdown). No SQL changes required.

**Why this matters:**
- **BB Defense** only has meaningful data in the BB column, but promoting to `PositionalStats` gives layout consistency. The real analytical value is in the response decomposition (fold vs call vs 3-bet).
- **Iso Raise** has meaningful positional variance -- iso-raising from BTN vs MP are different spots with different ranges.
- **Squeeze** has positional variance -- BTN and SB squeeze most often because they act after the most potential cold-callers.

**Prerequisite**: Phase 1 (Promote VPIP/PFR/Limp/4-Bet/Fold-to-4-Bet to PosTable) must be done first. This plan assumes the Phase 1 row order is already in place.

## Files to Modify

### 1. `backend/app/models.py` (3 lines changed)

Change three fields on `HeroStats` from `StatValue` to `PositionalStats`:

**Before** (lines 92, 96-97):
```python
squeeze: StatValue = StatValue()
# ...
bb_defense: StatValue = StatValue()
iso_raise: StatValue = StatValue()
```

**After:**
```python
squeeze: PositionalStats = PositionalStats()
# ...
bb_defense: PositionalStats = PositionalStats()
iso_raise: PositionalStats = PositionalStats()
```

### 2. `backend/app/stats_engine.py` (3 lines changed)

Change from `_sv()` to `_pos_stat()` for all three stats. No SQL changes needed -- `_AGG_SQL` already computes `bb_defense`, `bb_defense_opp`, `iso_raise`, `iso_raise_opp`, `squeeze`, `squeeze_opp` counts, and the `GROUP BY hp.position` means each position's counts are already available in `by_pos[pos]`.

**Before** (lines 309, 317-318):
```python
stats.squeeze = _sv("squeeze", "squeeze_opp")
# ...
stats.bb_defense = _sv("bb_defense", "bb_defense_opp")
stats.iso_raise = _sv("iso_raise", "iso_raise_opp")
```

**After:**
```python
stats.squeeze = _pos_stat("squeeze", "squeeze_opp")
# ...
stats.bb_defense = _pos_stat("bb_defense", "bb_defense_opp")
stats.iso_raise = _pos_stat("iso_raise", "iso_raise_opp")
```

### 3. `frontend/src/lib/api.ts` (3 lines changed)

In the `HeroStats` interface, change these three fields from `StatValue` to `PositionalStats`:

**Before** (lines 103, 107-108):
```typescript
squeeze: StatValue;
// ...
bb_defense: StatValue;
iso_raise: StatValue;
```

**After:**
```typescript
squeeze: PositionalStats;
// ...
bb_defense: PositionalStats;
iso_raise: PositionalStats;
```

### 4. `frontend/src/pages/StatsPage.tsx`

#### 4a. Add three rows to Preflop PosTable

Using the `posRow()` helper that already exists (line 351), add new rows. The rows use the same `fullPosKeys` array and pattern as existing rows.

**Iso Raise** -- insert after the Limp row (position 4 in the Phase 1 order, after `posRow('Limp', stats.limp, ...)`):

```tsx
posRow('Iso Raise', stats.iso_raise, 'iso_raise', fullPosKeys),
```

**Squeeze** -- insert after the 3-Bet OOP row (which is `posRow('3-Bet OOP', stats.three_bet_oop, ...)`):

```tsx
posRow('Squeeze', stats.squeeze, 'squeeze', fullPosKeys),
```

**BB Defense** -- insert as the last row in the PosTable (after Fold to 4-Bet):

```tsx
posRow('BB Defense', stats.bb_defense, 'bb_defense', fullPosKeys),
```

#### 4b. Remove from KV grid

Remove the Squeeze line from the KV grid items array:

**Remove this line:**
```tsx
{ label: 'Squeeze', sv: stats.squeeze, drillKey: 'squeeze' },
```

BB Defense and Iso Raise are not currently in the KV grid so nothing else to remove.

**KV grid after this change retains:**
- 4-Bet Range, Limp-Fold, 4-Bet-Fold, Call 4-Bet, Fold to 4-Bet (if Phase 1 hasn't moved it), 5-Bet, Fold to Squeeze
- Win Rate, Win Rate EV, Hands

#### 4c. Fix any `.value` access on promoted stats

Search the codebase for any code accessing `stats.squeeze.value`, `stats.bb_defense.value`, or `stats.iso_raise.value`. These must change to `stats.squeeze.total.value` etc., since `PositionalStats` wraps the total inside a `.total` field.

**Current reference found** (line 685):
```tsx
// Before:
{ label: 'Squeeze', sv: stats.squeeze, drillKey: 'squeeze' },
```

This line passes `stats.squeeze` (which was a `StatValue`) as the `sv` prop. After the type change, `stats.squeeze` becomes a `PositionalStats`. However, since this line is being **removed** (moved to PosTable), no fix is needed -- the removal handles it.

No other direct `.value` accesses on these three stats exist in the frontend codebase.

### 5. `frontend/src/lib/stat-registry.ts` (3 lines changed)

Set `isPositional: true` for all three entries:

**Before** (lines 47, 53-54):
```typescript
squeeze:      { displayName: 'Squeeze',    heroStatsField: 'squeeze',    isPositional: false, widgets: [...] },
// ...
bb_defense:   { displayName: 'BB Defense', heroStatsField: 'bb_defense', isPositional: false, widgets: [...] },
iso_raise:    { displayName: 'Iso Raise',  heroStatsField: 'iso_raise',  isPositional: false, widgets: [...] },
```

**After:**
```typescript
squeeze:      { displayName: 'Squeeze',    heroStatsField: 'squeeze',    isPositional: true, widgets: ['fold_equity', 'ev_breakdown', 'by_context', 'positional_bar', 'trend_sparkline'] },
// ...
bb_defense:   { displayName: 'BB Defense', heroStatsField: 'bb_defense', isPositional: true, widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'by_context', 'positional_bar', 'trend_sparkline'] },
iso_raise:    { displayName: 'Iso Raise',  heroStatsField: 'iso_raise',  isPositional: true, widgets: ['range_heatmap', 'by_context', 'sizing_histogram', 'ev_breakdown', 'positional_bar', 'trend_sparkline'] },
```

Key widget changes:
- All three gain `positional_bar` (since they now have positional data to display).
- Squeeze replaces the old widget list with one focused on fold equity and context.
- BB Defense keeps `response_distribution` and `continuing_range` (the core coaching question: how does Hero continue?).
- Iso Raise keeps `range_heatmap` and `sizing_histogram` (what combos, what sizing?).

### 6. `frontend/src/lib/benchmarks.ts`

Add benchmark entries for the three promoted stats. Add entries to `BENCHMARKS`, `STAT_DISPLAY_NAMES`, and the `BENCHMARKS` object.

#### Add display names

```typescript
// Add to STAT_DISPLAY_NAMES:
bb_defense: 'BB Defense',
iso_raise: 'Iso Raise',
squeeze: 'Squeeze',
```

#### Add benchmarks

**BB Defense** (total only -- BB-specific, other positions will show `--`):
```typescript
bb_defense: {
  total: {
    low: 55, high: 70,
    tipLow: 'Folding BB too much -- surrendering equity you already have invested.',
    tipHigh: 'Defending too wide -- calling with hands that lack equity vs opener\'s range.',
    fix: 'Defend 58-65% from BB vs single raise. Defend wider vs late position opens, tighter vs EP.',
    weight: 5,
    statFlagFilter: 'bb_defense',
    oppFlagFilter: 'bb_defense_opp',
  },
},
```

**Iso Raise** (total only):
```typescript
iso_raise: {
  total: {
    low: 5, high: 15,
    tipLow: 'Not punishing limpers enough -- letting weak ranges see cheap flops.',
    tipHigh: 'Iso-raising too wide -- building pots OOP or multiway with marginal hands.',
    fix: 'Iso-raise 8-12% overall. From BTN/CO iso wider; from EP/MP stick to value.',
    weight: 2,
    statFlagFilter: 'iso_raise',
    oppFlagFilter: 'iso_raise_opp',
  },
},
```

**Squeeze** (total + positional):
```typescript
squeeze: {
  total: {
    low: 5, high: 12,
    tipLow: 'Not squeezing enough -- letting multiway pots develop where your edge shrinks.',
    tipHigh: 'Squeezing too wide -- getting called or 4-bet when ranges are strong.',
    fix: 'Squeeze 7-10% overall. Best from BTN/SB after the most cold-callers.',
    weight: 3,
    statFlagFilter: 'squeeze',
    oppFlagFilter: 'squeeze_opp',
  },
  btn: { low: 7, high: 15, tipLow: 'BTN squeeze too tight.', tipHigh: 'BTN squeeze too wide.', fix: 'BTN should squeeze 7-15%.', weight: 2 },
  sb: { low: 7, high: 14, tipLow: 'SB squeeze too tight.', tipHigh: 'SB squeeze too wide.', fix: 'SB should squeeze 7-14%.', weight: 2 },
  bb: { low: 5, high: 12, tipLow: 'BB squeeze too tight.', tipHigh: 'BB squeeze too wide.', fix: 'BB should squeeze 5-12%.', weight: 2 },
},
```

### 7. `backend/app/stat_registry.py`

#### Verify STAT_REGISTRY entries

Both `bb_defense` and `iso_raise` already exist in `STAT_REGISTRY` (lines 103-112):
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

No changes needed here.

#### Verify RESPONSE_DECOMPOSITION for bb_defense

Already exists (lines 395-399):
```python
"bb_defense": {
    "opp_sql": "hp.bb_defense_opp = TRUE",
    "fold_sql": "hp.bb_defense IS NOT TRUE",
    "raise_sql": "hp.three_bet = TRUE",
},
```

The existing entry is missing `"call_sql"` and the position filter on `fold_sql`. Update it:

**Before:**
```python
"bb_defense": {
    "opp_sql": "hp.bb_defense_opp = TRUE",
    "fold_sql": "hp.bb_defense IS NOT TRUE",
    "raise_sql": "hp.three_bet = TRUE",
},
```

**After:**
```python
"bb_defense": {
    "opp_sql": "hp.bb_defense_opp = TRUE",
    "fold_sql": "hp.bb_defense IS NOT TRUE AND hp.position = 'BB'",
    "call_sql": "hp.bb_defense = TRUE AND hp.three_bet IS NOT TRUE",
    "raise_sql": "hp.three_bet = TRUE AND hp.position = 'BB'",
},
```

The position filter (`hp.position = 'BB'`) on `fold_sql` and `raise_sql` ensures the decomposition only counts BB actions, since `bb_defense_opp` is only set for the BB player anyway but the explicit filter prevents false matches if the data has edge cases.

## New PosTable Row Order (after Phase 1 + Phase 3)

```
 1.  VPIP           (vpip)            ← Phase 1
 2.  PFR            (pfr)             ← Phase 1
 3.  Open Raise     (open_raise)      ← original
 4.  Limp           (limp)            ← Phase 1
 5.  Iso Raise      (iso_raise)       ← NEW Phase 3
 6.  Call Open      (call_open_raise)  ← original
 7.  3-Bet          (three_bet)        ← original
 8.  3-Bet IP       (three_bet_ip)     ← original
 9.  3-Bet OOP      (three_bet_oop)    ← original
10.  Squeeze        (squeeze)          ← NEW Phase 3
11.  Fold to 3-Bet  (fold_to_3bet)     ← original (reordered in Phase 1)
12.  4-Bet          (four_bet)         ← Phase 1
13.  Fold to 4-Bet  (fold_to_4bet)     ← Phase 1
14.  BB Defense     (bb_defense)       ← NEW Phase 3 (last row)
```

## KV Grid After This Phase

The KV grid retains only flat `StatValue` stats plus summary metrics:

| Label | Source | drillKey |
|-------|--------|----------|
| 4-Bet Range | `stats.four_bet_range` | `four_bet_range` |
| Limp-Fold | `stats.limp_fold` | `limp_fold` |
| 4-Bet-Fold | `stats.four_bet_fold` | `four_bet_fold` |
| Call 4-Bet | `stats.call_4bet` | `call_4bet` |
| 5-Bet | `stats.five_bet` | `five_bet` |
| Fold to Squeeze | `stats.fold_to_squeeze` | `fold_to_squeeze` |
| Win Rate | computed from `stats.win_rate_bb100` | -- |
| Win Rate EV | computed from `stats.win_rate_ev_bb100` | -- |
| Hands | `stats.hands` | -- |

**Removed from KV grid:** Squeeze (moved to PosTable).

## Benchmark Reference Values

| Stat | Position | Low | High | Notes |
|------|----------|-----|------|-------|
| BB Defense | total | 55 | 70 | Combined call + 3-bet frequency from BB vs single raise |
| Iso Raise | total | 5 | 15 | Overall frequency when facing a limp |
| Squeeze | total | 5 | 12 | Overall frequency when facing open + cold-call |
| Squeeze | BTN | 7 | 15 | Best squeeze position -- acts after most cold-callers |
| Squeeze | SB | 7 | 14 | Good squeeze position but OOP postflop |
| Squeeze | BB | 5 | 12 | Closing action advantage but OOP |

**Expected positional patterns:**
- BB Defense: only BB column shows data. All other positions show `--`.
- Iso Raise: BTN and CO typically show highest values (10-20%). EP/MP lower (3-8%). SB/BB vary.
- Squeeze: BTN and SB typically show highest values. EP/MP rarely have squeeze opportunities (few players cold-call behind them).

## Test Checklist

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all tests pass (no parser or stat flag changes)
2. `cd frontend && npm run lint` -- no TypeScript or lint errors
3. Start dev (`make dev`) and load the Stats page
4. `GET /api/stats/hero` returns `bb_defense`, `iso_raise`, `squeeze` as objects with `total`, `ep`, `mp`, `co`, `btn`, `sb`, `bb` sub-fields (each containing `value` and `sample`)
5. Preflop PosTable shows 14 rows in the order listed above (assuming Phase 1 is done)
6. **BB Defense row**: Tot column shows a value (55-70% range). BB column shows a value. EP/MP/CO/BTN/SB columns all show `--`
7. **Iso Raise row**: Tot shows a value (5-15%). Positional cells show variance -- BTN/CO higher than EP/MP
8. **Squeeze row**: Tot shows a value (5-12%). BTN/SB should show higher values than EP/MP
9. KV grid no longer shows Squeeze (BB Defense and Iso Raise were never in it)
10. Clicking any of the three new stat cells in PosTable navigates to `/stats/{statKey}` drill-down
11. Drill-down panel for BB Defense shows `response_distribution` widget (fold/call/3-bet breakdown)
12. Drill-down panel for Squeeze shows `fold_equity` widget
13. Drill-down panel for Iso Raise shows `range_heatmap` and `sizing_histogram` widgets
14. Benchmark colors apply: BB Defense shows green at 60%, yellow at 53%, red at 48%
15. Squeeze positional benchmarks apply: BTN squeeze shows green at 10%, red at 18%
