# Phase 4 — C-Bet by Pot Type + C-Bet Positional Section

## Goal

Add four new stat rows to the Postflop by-street grid:
1. **C-Bet Flop (SRP)** — c-bet frequency in single raised pots (heads-up and multiway)
2. **C-Bet Flop (3-Bet Pot)** — c-bet frequency in 3-bet+ pots
3. **Fold to CBet Flop (SRP)** — fold rate when facing c-bet in single raised pots
4. **Fold to CBet Flop (3-Bet Pot)** — fold rate when facing c-bet in 3-bet+ pots

And add a new **C-Bet Positional** sub-section showing C-Bet Flop and Fold to CBet Flop with full positional columns (Tot/EP/MP/CO/BTN/SB/BB).

**Scope**: Backend (models, stats_engine, stat_registry) + Frontend (StatsPage layout, api.ts types, stat-registry).

### Why pot type matters for c-bet

C-bet strategy differs fundamentally between SRPs and 3-bet pots:
- **SRPs**: Ranges are wide, board texture matters a lot. Typical c-bet frequency 45-65% with mixed sizings (1/3 to 3/4 pot). Check more on wet/connected boards.
- **3-Bet pots**: The 3-bettor has a significant range advantage (AA-TT, AK-AQs concentrated). Solvers recommend high-frequency small c-bets (65-80% at 1/3 pot) on most textures. Checking range is narrower.
- **Multiway**: C-bet frequency drops sharply (30-45%) because at least one opponent likely connected. The `is_multiway` flag exists but is not split out here -- consider as a future extension.

### Note on pot type filtering

The SQL uses `NOT COALESCE(hp.is_3bet_pot, false)` for SRP. Since `is_3bet_pot` is true when `raise_count >= 2` (covering 3BP/4BP/5BP), the "NOT" bucket captures SRP and limped pots. This is fine for c-bet stats because `cbet_flop_opp` already requires being the preflop raiser, so limped pots never appear in c-bet opportunity counts.

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

Add EV_BREAKDOWN_CONFIG entries (compare EV when c-betting vs checking in each pot type):

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

These EV breakdowns are the most actionable part of this feature. If the user sees that their "Check SRP" EV is significantly worse than "C-bet SRP" EV, they are checking hands they should be betting (and vice versa). The same logic applies for 3BP but the gap should typically be smaller since small c-bets in 3BP are closer to break-even.

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
  widgets: ['response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'],
},
cbet_flop_3bp: {
  displayName: 'C-Bet Flop (3-Bet Pot)',
  heroStatsField: 'cbet_flop_3bp',
  isPositional: false,
  widgets: ['response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'],
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

Note: `ip_oop_split` is omitted from these pot-type stats because there is no backend aggregation for IP/OOP within each pot type yet. The existing `postflop_ip` flag could be combined with `is_3bet_pot` in a future phase to enable this. Add `ip_oop_split` to the widgets list only after the backend SQL supports it.

Update existing `cbet_flop` entry to add `by_context` widget:

```typescript
cbet_flop: {
  displayName: 'C-Bet Flop',
  heroStatsField: 'cbet_flop',
  isPositional: true,
  widgets: ['response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'trend_sparkline'],
},
```

### 8. `frontend/src/lib/benchmarks.ts`

Add benchmarks for the new pot-type stats:

```typescript
cbet_flop_srp: {
  total: { low: 45, high: 65, tipLow: 'Checking too much in SRPs — missing fold equity and value', tipHigh: 'C-betting too often in SRPs — opponents will raise and float you', fix: 'C-bet 50-60% in SRPs. Check more on wet/connected boards, c-bet more on dry/high-card boards.', weight: 3 },
},
cbet_flop_3bp: {
  total: { low: 60, high: 80, tipLow: 'Checking too much in 3-bet pots — you have range advantage, use it', tipHigh: 'C-betting too wide in 3BP — even with range advantage, some boards favor the caller', fix: 'C-bet 65-75% in 3-bet pots. Use small sizing (25-33% pot) on most textures.', weight: 3 },
},
fold_cbet_flop_srp: {
  total: { low: 35, high: 50, tipLow: 'Calling/raising too wide vs SRP c-bets — you are bleeding chips', tipHigh: 'Folding too much in SRPs — villain can c-bet any two cards profitably', fix: 'Defend 50-65% vs SRP c-bets. Deep SPR means implied odds favor continuing with draws and pairs.', weight: 3 },
},
fold_cbet_flop_3bp: {
  total: { low: 25, high: 40, tipLow: 'Defending too wide vs 3BP c-bets — their range is strong even when betting small', tipHigh: 'Folding too much in 3-bet pots — your range is condensed and strong, defend more', fix: 'Defend 60-75% vs 3BP c-bets. Your calling range in a 3BP is already strong — fold less than in SRPs, especially vs small sizings.', weight: 3 },
},
```

Note on the fold-to-cbet asymmetry: fold rates should be **lower** in 3-bet pots than SRPs because both players have strong ranges. The caller in a 3BP has already shown strength by calling (or the 3-bettor by 3-betting), so the defender's range connects with more boards. The low SPR also means draws have better pot odds.

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all tests pass
2. `GET /api/stats/hero` returns the four new `StatValue` fields
3. Postflop by-street grid shows 10 rows with "C-Bet by Pot" group
4. CBet (SRP) and CBet (3BP) rows show values in Flop column, dashes in Turn/River
5. C-Bet Positional sub-section shows 2 rows with full positional columns
6. All new cells are clickable -> drill-down loads
7. `cd frontend && npm run lint` -- no lint errors
8. Verify SRP c-bet sample excludes hands where `is_3bet_pot = true` (no leakage from 3BP/4BP/5BP into SRP bucket)
9. Verify 3BP c-bet sample includes 4BP and 5BP hands (all `is_3bet_pot = true`)

## Future Extensions

These are deliberately out of scope for Phase 4 but should be considered:

- **Turn/River c-bet by pot type**: Double and triple barrel frequencies differ between SRP and 3BP. In 3BPs the turn c-bet is often higher because the PFR's range advantage persists.
- **Multiway c-bet split**: The `is_multiway` flag already exists. C-bet frequency drops to 30-45% multiway. Splitting SRP into HU vs multiway would be high-value.
- **IP/OOP c-bet by pot type**: The `postflop_ip` flag exists. Combining pot type + position (IP/OOP) gives the most actionable c-bet stats (e.g., "C-Bet Flop SRP IP" vs "C-Bet Flop SRP OOP"). This is the gold standard in Hand2Note and should be a priority follow-up.
