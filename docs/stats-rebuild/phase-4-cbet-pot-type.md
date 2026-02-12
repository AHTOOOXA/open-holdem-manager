# Phase 4 — C-Bet by Pot Type + C-Bet Positional Section

## Goal

Add four new stat rows to the Postflop by-street grid:
1. **C-Bet Flop (SRP)** — c-bet frequency in single raised pots
2. **C-Bet Flop (3-Bet Pot)** — c-bet frequency in 3-bet pots
3. **Fold to CBet Flop (SRP)** — fold rate when facing c-bet in single raised pots
4. **Fold to CBet Flop (3-Bet Pot)** — fold rate in 3-bet pots

And add a new **C-Bet Positional** sub-section showing C-Bet Flop and Fold to CBet Flop with full positional columns (Tot/EP/MP/CO/BTN/SB/BB).

**Scope**: Backend (models, stats_engine, stat_registry) + Frontend (StatsPage layout, api.ts types, stat-registry).

## Current State

- Backend `_AGG_SQL` already computes `is_3bet_pot`-filtered counts for vs-CBet (lines 92-100: `faced_cbet_raised`, `fold_cbet_raised`, etc.)
- Backend does NOT yet compute c-bet-side pot type splits (hero's c-bet in SRP vs 3BP)
- `HeroStats` has `cbet_flop` as `PositionalStats` (already positional)
- `HeroStats` has `fold_to_cbet_flop` as `PositionalStats` (already positional)
- No `cbet_flop_srp`, `cbet_flop_3bp`, `fold_cbet_flop_srp`, `fold_cbet_flop_3bp` fields exist yet

## Files to Modify

### 1. `backend/app/stats_engine.py` — Add SQL aggregations

Add to `_AGG_SQL` (after the existing CBet section, around line 82):

```sql
-- CBet Flop by pot type
SUM(CASE WHEN hp.cbet_flop_opp AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as cbet_flop_srp_opp,
SUM(CASE WHEN hp.cbet_flop AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as cbet_flop_srp,
SUM(CASE WHEN hp.cbet_flop_opp AND hp.is_3bet_pot THEN 1 ELSE 0 END) as cbet_flop_3bp_opp,
SUM(CASE WHEN hp.cbet_flop AND hp.is_3bet_pot THEN 1 ELSE 0 END) as cbet_flop_3bp,

-- Fold to CBet Flop by pot type (hero facing cbet)
SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as ftcb_flop_srp_opp,
SUM(CASE WHEN hp.fold_to_cbet_flop AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as ftcb_flop_srp,
SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot THEN 1 ELSE 0 END) as ftcb_flop_3bp_opp,
SUM(CASE WHEN hp.fold_to_cbet_flop AND hp.is_3bet_pot THEN 1 ELSE 0 END) as ftcb_flop_3bp,
```

### 2. `backend/app/stats_engine.py` — Compute stats

Add after the existing cbet stats computation (around line 347):

```python
# CBet Flop by pot type
stats.cbet_flop_srp = _sv("cbet_flop_srp", "cbet_flop_srp_opp")
stats.cbet_flop_3bp = _sv("cbet_flop_3bp", "cbet_flop_3bp_opp")
stats.fold_cbet_flop_srp = _sv("ftcb_flop_srp", "ftcb_flop_srp_opp")
stats.fold_cbet_flop_3bp = _sv("ftcb_flop_3bp", "ftcb_flop_3bp_opp")
```

### 3. `backend/app/models.py`

Add four new fields to `HeroStats` in the Postflop section:

```python
# C-Bet Flop by pot type
cbet_flop_srp: StatValue = StatValue()
cbet_flop_3bp: StatValue = StatValue()
fold_cbet_flop_srp: StatValue = StatValue()
fold_cbet_flop_3bp: StatValue = StatValue()
```

### 4. `backend/app/stat_registry.py`

Add STAT_REGISTRY entries for drill-down:

```python
"cbet_flop_srp": {
    "name": "C-Bet Flop (SRP)",
    "action_flag": "cbet_flop",
    "opp_sql": "hp.cbet_flop_opp = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)",
},
"cbet_flop_3bp": {
    "name": "C-Bet Flop (3-Bet Pot)",
    "action_flag": "cbet_flop",
    "opp_sql": "hp.cbet_flop_opp = TRUE AND hp.is_3bet_pot = TRUE",
},
"fold_cbet_flop_srp": {
    "name": "Fold to CBet Flop (SRP)",
    "action_sql": "hp.fold_to_cbet_flop = TRUE",
    "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)",
},
"fold_cbet_flop_3bp": {
    "name": "Fold to CBet Flop (3-Bet Pot)",
    "action_sql": "hp.fold_to_cbet_flop = TRUE",
    "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE",
},
```

Add EV_BREAKDOWN_CONFIG entries:

```python
"cbet_flop_srp": [
    ("C-bet SRP", "hp.cbet_flop = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)"),
    ("Check SRP", "hp.cbet_flop_opp = TRUE AND hp.missed_cbet_flop = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)"),
],
"cbet_flop_3bp": [
    ("C-bet 3BP", "hp.cbet_flop = TRUE AND hp.is_3bet_pot = TRUE"),
    ("Check 3BP", "hp.cbet_flop_opp = TRUE AND hp.missed_cbet_flop = TRUE AND hp.is_3bet_pot = TRUE"),
],
```

### 5. `frontend/src/lib/api.ts`

Add to the `HeroStats` TypeScript interface:

```typescript
cbet_flop_srp: StatValue;
cbet_flop_3bp: StatValue;
fold_cbet_flop_srp: StatValue;
fold_cbet_flop_3bp: StatValue;
```

### 6. `frontend/src/pages/StatsPage.tsx`

#### Add rows to the Postflop by-street grid

The current Postflop grid has columns: `Stat | Flop | Turn | River`. Add a "C-Bet by Pot" group after the existing C-Bet rows:

```
Group "C-Bet":
  Row 1: C-Bet         | cbet_flop     | cbet_turn     | cbet_river
  Row 2: Fold to CBet  | fold_to_cbet_flop | fold_to_cbet_turn | fold_to_cbet_river
Group "C-Bet by Pot":
  Row 3: CBet (SRP)    | cbet_flop_srp | —             | —
  Row 4: CBet (3BP)    | cbet_flop_3bp | —             | —
  Row 5: Fold CBet (SRP)   | fold_cbet_flop_srp  | —   | —
  Row 6: Fold CBet (3BP)   | fold_cbet_flop_3bp  | —   | —
```

For rows 3-6, the Turn and River columns should show `—` (these are flop-only stats).

#### Add C-Bet Positional sub-section

Below the vs CBet Flop Response table (right side of postflop section), add a new mini PosTable:

```
C-Bet Positional
Columns: Stat | Tot | EP | MP | CO | BTN | SB | BB

Row 1: C-Bet Flop      → stats.cbet_flop (already PositionalStats)
Row 2: Fold to CBet Flop → stats.fold_to_cbet_flop (already PositionalStats)
```

This reuses the existing `cbet_flop` and `fold_to_cbet_flop` `PositionalStats` objects — no new backend data needed. These are already computed positionally by `_pos_stat()`.

### 7. `frontend/src/lib/stat-registry.ts`

Add entries for the new stats:

```typescript
cbet_flop_srp: {
  displayName: 'C-Bet Flop (SRP)',
  heroStatsField: 'cbet_flop_srp',
  isPositional: false,
  widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'],
},
cbet_flop_3bp: {
  displayName: 'C-Bet Flop (3-Bet Pot)',
  heroStatsField: 'cbet_flop_3bp',
  isPositional: false,
  widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'],
},
fold_cbet_flop_srp: {
  displayName: 'Fold to CBet (SRP)',
  heroStatsField: 'fold_cbet_flop_srp',
  isPositional: false,
  widgets: ['response_distribution', 'ev_breakdown', 'trend_sparkline'],
},
fold_cbet_flop_3bp: {
  displayName: 'Fold to CBet (3-Bet Pot)',
  heroStatsField: 'fold_cbet_flop_3bp',
  isPositional: false,
  widgets: ['response_distribution', 'ev_breakdown', 'trend_sparkline'],
},
```

Update existing `cbet_flop` entry to add `ip_oop_split` and `by_context` widgets:

```typescript
cbet_flop: {
  displayName: 'C-Bet Flop',
  heroStatsField: 'cbet_flop',
  isPositional: true,
  widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'trend_sparkline'],
},
```

### 8. `frontend/src/lib/benchmarks.ts`

Add benchmarks for the new pot-type stats:

```typescript
cbet_flop_srp: {
  total: { low: 55, high: 75, tipLow: 'C-betting too rarely in SRPs', tipHigh: 'C-betting too often in SRPs — get check-raised', fix: 'C-bet 60-70% in SRPs. Check more on wet boards.', weight: 3 },
},
cbet_flop_3bp: {
  total: { low: 50, high: 75, tipLow: 'Checking too much in 3-bet pots', tipHigh: 'C-betting too wide in 3BP — ranges are narrow', fix: 'C-bet 55-70% in 3-bet pots. Use smaller sizing (1/3 pot).', weight: 3 },
},
fold_cbet_flop_srp: {
  total: { low: 35, high: 50, tipLow: 'Calling/raising too wide vs SRP c-bets', tipHigh: 'Folding too much in SRPs — villain prints money', fix: 'Defend 50-65% vs SRP c-bets. SPR is deep, so call more.', weight: 3 },
},
fold_cbet_flop_3bp: {
  total: { low: 30, high: 45, tipLow: 'Defending too wide in 3BP', tipHigh: 'Folding too much in 3-bet pots', fix: 'Defend 55-70% in 3-bet pots. Your range is already strong.', weight: 3 },
},
```

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `GET /api/stats/hero` returns the four new `StatValue` fields
3. Postflop by-street grid shows 10 rows with "C-Bet by Pot" group
4. CBet (SRP) and CBet (3BP) rows show values in Flop column, dashes in Turn/River
5. C-Bet Positional sub-section shows 2 rows with full positional columns
6. All new cells are clickable → drill-down loads
7. `cd frontend && npm run lint` — no lint errors
