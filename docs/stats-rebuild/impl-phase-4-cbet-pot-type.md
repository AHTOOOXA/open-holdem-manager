# Phase 4 Implementation Plan -- C-Bet by Pot Type + C-Bet Positional Section

## Goal

Split flop c-bet and fold-to-cbet stats by pot type (SRP vs 3-Bet Pot) and add a positional sub-section for c-bet stats to the Postflop area of StatsPage.

### Why pot type matters for c-bet

C-bet strategy differs fundamentally between single-raised pots and 3-bet pots:

- **Single Raised Pots (SRP)**: Ranges are wide. Board texture matters enormously. Typical c-bet frequency is 45-65% with mixed sizings (1/3 to 3/4 pot). The preflop raiser should check more on wet/connected boards where the caller's range connects well.
- **3-Bet Pots (3BP)**: The 3-bettor holds a concentrated range advantage (AA-TT, AK-AQs). Solvers recommend high-frequency small c-bets (65-80% at 25-33% pot) on most textures. The checking range is much narrower than in SRPs.
- **Why the split matters for coaching**: A player might show a healthy 55% overall flop c-bet, but if they're c-betting 40% in SRPs (too low, missing fold equity) and 90% in 3BPs (too high, c-betting boards that favor the caller), the aggregate number hides two separate leaks. The pot-type split reveals this immediately.

### Note on pot type filtering

The SQL uses `NOT COALESCE(hp.is_3bet_pot, false)` for SRP. Since `is_3bet_pot` is true when `raise_count >= 2` (covering 3BP/4BP/5BP), the "NOT" bucket captures SRP and limped pots. This is fine for c-bet stats because `cbet_flop_opp` already requires being the preflop raiser, so limped pots never appear in c-bet opportunity counts. For fold-to-cbet, limped pots also never appear because `fold_to_cbet_flop` requires facing a c-bet which requires a preflop raiser.

**Scope**: Backend (stats_engine SQL + computation, models, stat_registry) + Frontend (StatsPage layout, api.ts types, stat-registry, benchmarks). Medium effort.

---

## Current State

- `_AGG_SQL` already computes `is_3bet_pot`-filtered counts for the **vs CBet** side (lines 92-100: `faced_cbet_raised`, `fold_cbet_raised`, `call_cbet_raised`, `raise_cbet_raised`, `faced_cbet_3bet`, etc.)
- `_AGG_SQL` does NOT compute c-bet-side pot type splits (hero's c-bet in SRP vs 3BP)
- `HeroStats` has `cbet_flop` as `PositionalStats` (already positional in the backend)
- `HeroStats` has `fold_to_cbet_flop` as `PositionalStats` (already positional in the backend)
- No `cbet_flop_srp`, `cbet_flop_3bp`, `fold_cbet_flop_srp`, `fold_cbet_flop_3bp` fields exist yet
- The postflop by-street grid shows cbet_flop/turn/river but has no pot type breakdown
- The `cbet_flop` and `fold_to_cbet_flop` PositionalStats are never rendered in a positional table -- they only appear as total values in the by-street grid

---

## Files to Modify

### 1. `backend/app/stats_engine.py` -- Add SQL aggregations

Add 8 new lines to `_AGG_SQL`, after the existing CBet section (after line 82, before `-- Fold to CBet`):

```sql
-- CBet Flop by pot type
SUM(CASE WHEN hp.cbet_flop_opp AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as cbet_flop_srp_opp,
SUM(CASE WHEN hp.cbet_flop AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as cbet_flop_srp,
SUM(CASE WHEN hp.cbet_flop_opp AND hp.is_3bet_pot THEN 1 ELSE 0 END) as cbet_flop_3bp_opp,
SUM(CASE WHEN hp.cbet_flop AND hp.is_3bet_pot THEN 1 ELSE 0 END) as cbet_flop_3bp,
```

Add 4 more lines after the existing Fold to CBet section (after line 90, before `-- vs CBet Flop by pot type`):

```sql
-- Fold to CBet Flop by pot type (hero facing cbet)
SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as ftcb_flop_srp_opp,
SUM(CASE WHEN hp.fold_to_cbet_flop AND NOT COALESCE(hp.is_3bet_pot, false) THEN 1 ELSE 0 END) as ftcb_flop_srp,
SUM(CASE WHEN hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot THEN 1 ELSE 0 END) as ftcb_flop_3bp_opp,
SUM(CASE WHEN hp.fold_to_cbet_flop AND hp.is_3bet_pot THEN 1 ELSE 0 END) as ftcb_flop_3bp,
```

### 2. `backend/app/stats_engine.py` -- Add stat computations

Add after the existing cbet stats computation (after line 338, `stats.fold_to_cbet_river`):

```python
# CBet Flop by pot type
stats.cbet_flop_srp = _sv("cbet_flop_srp", "cbet_flop_srp_opp")
stats.cbet_flop_3bp = _sv("cbet_flop_3bp", "cbet_flop_3bp_opp")
stats.fold_cbet_flop_srp = _sv("ftcb_flop_srp", "ftcb_flop_srp_opp")
stats.fold_cbet_flop_3bp = _sv("ftcb_flop_3bp", "ftcb_flop_3bp_opp")
```

These use `_sv()` (simple value) not `_pos_stat()` because pot-type splits are not broken down by position -- the pot type IS the breakdown dimension.

### 3. `backend/app/models.py` -- Add 4 new fields

Add to `HeroStats` in the Postflop section (after `fold_to_cbet_river`, before `donk_bet_flop`):

```python
# C-Bet Flop by pot type
cbet_flop_srp: StatValue = StatValue()
cbet_flop_3bp: StatValue = StatValue()
fold_cbet_flop_srp: StatValue = StatValue()
fold_cbet_flop_3bp: StatValue = StatValue()
```

### 4. `backend/app/stat_registry.py` -- Add STAT_REGISTRY entries

Add to STAT_REGISTRY after the existing `cbet_river` entry:

```python
# ── Postflop: C-Bet Flop by Pot Type ──
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
```

Add after the existing `fold_to_cbet_river` entry:

```python
# ── Postflop: Fold to C-Bet Flop by Pot Type ──
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

### 5. `backend/app/stat_registry.py` -- Add EV_BREAKDOWN_CONFIG entries

Add to `EV_BREAKDOWN_CONFIG`:

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

### 6. `backend/app/stat_registry.py` -- Add `get_key_street` coverage

Verify that the new stat keys are handled by `get_key_street()`. The existing logic checks for `"flop"` in the stat key name:

```python
if "flop" in stat_key or stat_key in (...):
    return "flop"
```

Both `cbet_flop_srp` and `cbet_flop_3bp` contain `"flop"`, and `fold_cbet_flop_srp` and `fold_cbet_flop_3bp` also contain `"flop"`. No change needed -- the existing substring check covers all four new keys.

### 7. `frontend/src/lib/api.ts` -- Add TypeScript fields

Add to the `HeroStats` interface, after `fold_to_cbet_river`:

```typescript
// C-Bet Flop by pot type
cbet_flop_srp: StatValue;
cbet_flop_3bp: StatValue;
fold_cbet_flop_srp: StatValue;
fold_cbet_flop_3bp: StatValue;
```

### 8. `frontend/src/pages/StatsPage.tsx` -- Update postflop by-street grid

#### A. Add pot-type rows to the postflop PosTable

Replace the current postflop PosTable rows block (lines 789-830) with an expanded set. The new row order:

```tsx
<PosTable
  headers={['Flop', 'Turn', 'River']}
  driftMap={driftMap}
  onStatClick={handleStatClick}
  rows={[
    {
      label: 'C-Bet',
      cells: [
        { sv: stats.cbet_flop.total, statKey: 'cbet_flop', drillKey: 'cbet_flop', position: 'total' },
        { sv: stats.cbet_turn.total, statKey: 'cbet_turn', drillKey: 'cbet_turn', position: 'total' },
        { sv: stats.cbet_river.total, statKey: 'cbet_river', drillKey: 'cbet_river', position: 'total' },
      ],
    },
    {
      label: 'Fold to CBet',
      cells: [
        { sv: stats.fold_to_cbet_flop.total, statKey: 'fold_to_cbet_flop', drillKey: 'fold_to_cbet_flop', position: 'total' },
        { sv: stats.fold_to_cbet_turn.total, statKey: 'fold_to_cbet_turn', drillKey: 'fold_to_cbet_turn', position: 'total' },
        { sv: stats.fold_to_cbet_river.total, drillKey: 'fold_to_cbet_river', position: 'total' },
      ],
    },
    {
      label: 'CBet (SRP)',
      cells: [
        { sv: stats.cbet_flop_srp, statKey: 'cbet_flop_srp', drillKey: 'cbet_flop_srp' },
        { sv: undefined },
        { sv: undefined },
      ],
    },
    {
      label: 'CBet (3BP)',
      cells: [
        { sv: stats.cbet_flop_3bp, statKey: 'cbet_flop_3bp', drillKey: 'cbet_flop_3bp' },
        { sv: undefined },
        { sv: undefined },
      ],
    },
    {
      label: 'Fold CBet (SRP)',
      cells: [
        { sv: stats.fold_cbet_flop_srp, statKey: 'fold_cbet_flop_srp', drillKey: 'fold_cbet_flop_srp' },
        { sv: undefined },
        { sv: undefined },
      ],
    },
    {
      label: 'Fold CBet (3BP)',
      cells: [
        { sv: stats.fold_cbet_flop_3bp, statKey: 'fold_cbet_flop_3bp', drillKey: 'fold_cbet_flop_3bp' },
        { sv: undefined },
        { sv: undefined },
      ],
    },
    {
      label: 'Aggression',
      cells: [
        { sv: stats.af_flop, statKey: 'af_flop', drillKey: 'af_flop', decimals: 1 },
        { sv: stats.af_turn, statKey: 'af_turn', drillKey: 'af_turn', decimals: 1 },
        { sv: stats.af_river, statKey: 'af_river', drillKey: 'af_river', decimals: 1 },
      ],
    },
    {
      label: 'Agg Freq',
      cells: [
        { sv: stats.afq_flop, drillKey: 'afq_flop' },
        { sv: stats.afq_turn, drillKey: 'afq_turn' },
        { sv: stats.afq_river, drillKey: 'afq_river' },
      ],
    },
    {
      label: 'Donk Bet',
      cells: [
        { sv: stats.donk_bet_flop, drillKey: 'donk_bet_flop' },
        { sv: stats.donk_bet_turn, drillKey: 'donk_bet_turn' },
        { sv: stats.donk_bet_river, drillKey: 'donk_bet_river' },
      ],
    },
  ]}
/>
```

**What changed vs. current:**

| Action | Row | Detail |
|--------|-----|--------|
| KEEP | C-Bet | Row 1. No change. |
| KEEP | Fold to CBet | Row 2. No change. |
| ADD | CBet (SRP) | Row 3. Flop column only. Turn/River show `--`. |
| ADD | CBet (3BP) | Row 4. Flop column only. Turn/River show `--`. |
| ADD | Fold CBet (SRP) | Row 5. Flop column only. Turn/River show `--`. |
| ADD | Fold CBet (3BP) | Row 6. Flop column only. Turn/River show `--`. |
| KEEP | Aggression | Row 7 (was row 3). No change. |
| KEEP | Agg Freq | Row 8 (was row 4). No change. |
| KEEP | Donk Bet | Row 9 (was row 5). No change. |

Total: 9 rows (was 5). Net: +4 new pot-type rows.

For rows 3-6, `sv: undefined` causes PosTable to render `--` in the Turn and River columns. Verify that PosTable handles `undefined` sv gracefully (it should -- existing code renders `--` when `sv.value` is null/undefined).

#### B. Add C-Bet Positional sub-section

Below the vs CBet Flop PosTable (after the `vs. C-Bet Flop` label div, around line 861), add a new positional mini-table:

```tsx
{/* C-Bet Positional */}
<div className="border-t border-border">
  <PosTable
    headers={fullPosHeaders}
    driftMap={driftMap}
    onStatClick={handleStatClick}
    rows={[
      posRow('C-Bet Flop', stats.cbet_flop, 'cbet_flop', fullPosKeys),
      posRow('Fold to CBet', stats.fold_to_cbet_flop, 'fold_to_cbet_flop', fullPosKeys),
    ]}
  />
  <div className="px-2 py-0.5 text-[10px] text-text-muted uppercase tracking-wide border-t border-border/30">
    C-Bet Positional
  </div>
</div>
```

This reuses the existing `posRow` helper and the `cbet_flop` / `fold_to_cbet_flop` PositionalStats objects that are already computed by the backend. No new backend data needed.

**Placement**: The C-Bet Positional section should go below the vs CBet Flop Response table on the right side of the postflop section. The resulting layout is:

```
POSTFLOP
+----------------------------------+-----------------------------------+
| By-Street Grid (left)            | vs CBet Flop Response (right top) |
|   C-Bet         | F | T | R      |   Raised Pot  | Fold | Call | Rse |
|   Fold to CBet  | F | T | R      |   3-Bet Pot   | Fold | Call | Rse |
|   CBet (SRP)    | F | - | -      |   "vs. C-Bet Flop"                |
|   CBet (3BP)    | F | - | -      +-----------------------------------+
|   Fold CBet(SRP)| F | - | -      | C-Bet Positional (right bottom)   |
|   Fold CBet(3BP)| F | - | -      |   C-Bet Flop     |T|EP|MP|CO|..  |
|   Aggression    | F | T | R      |   Fold to CBet   |T|EP|MP|CO|..  |
|   Agg Freq      | F | T | R      |   "C-Bet Positional"              |
|   Donk Bet      | F | T | R      |                                   |
+----------------------------------+-----------------------------------+
```

**Note**: `fullPosHeaders` and `fullPosKeys` and `posRow` must already be in scope from the preflop section. Verify they are defined at the component level, not inside a conditional block.

---

### 9. `frontend/src/lib/stat-registry.ts` -- Add 4 new entries

Add after the existing `cbet_river` entry:

```typescript
// C-Bet Flop by pot type
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

**Why `isPositional: false`**: These stats are already a dimensional split (by pot type). They are flat `StatValue` objects, not `PositionalStats`. Adding a positional dimension on top of pot type (e.g., "C-Bet Flop SRP from BTN") would require a cross-product in the backend SQL -- this is deferred to Phase 7 (IP/OOP split) where the `postflop_ip` flag provides a more useful split than full positional.

**Widget notes**:
- `sizing_histogram` is included for the c-bet side (SRP/3BP) because bet sizing differs between pot types. SRP c-bets range from 25-75% pot; 3BP c-bets are typically 25-33% pot.
- `sizing_histogram` is NOT included for fold-to-cbet stats (hero is not the one betting).
- `ip_oop_split` is omitted -- no backend aggregation exists for IP/OOP within each pot type yet.

Also update the existing `cbet_flop` entry to add the `by_context` widget:

```typescript
cbet_flop: {
  displayName: 'C-Bet Flop',
  heroStatsField: 'cbet_flop',
  isPositional: true,
  widgets: ['positional_bar', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'trend_sparkline'],
},
```

This enables the "by context" widget on the cbet_flop detail page, which would show c-bet rate broken down by an interesting dimension (number of opponents, board texture category, etc.). The `by_context` widget requires a `BY_CONTEXT_CONFIG` entry in the backend -- if one does not exist for `cbet_flop` yet, add it in `stat_registry.py` (see step 10).

### 10. `backend/app/stat_registry.py` -- Add BY_CONTEXT_CONFIG (optional, if adding `by_context` widget to cbet_flop)

If adding the `by_context` widget to the `cbet_flop` stat-registry entry, add a corresponding backend config:

```python
"cbet_flop": {
    "dimension": "pot_type",
    "action_sql": "hp.cbet_flop = TRUE",
    "opp_sql": "hp.cbet_flop_opp = TRUE",
    "join": "",
    "group_expr": "CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single Raised' END",
},
```

This shows the c-bet rate broken down by pot type within the cbet_flop detail page, complementing the separate SRP/3BP rows in the main grid.

### 11. `frontend/src/lib/benchmarks.ts` -- Add benchmark entries

Add to `BENCHMARKS`:

```typescript
cbet_flop_srp: {
  total: {
    low: 45, high: 65,
    tipLow: 'Checking too much in SRPs -- missing fold equity and value on dry boards',
    tipHigh: 'C-betting too often in SRPs -- opponents will raise and float you on wet boards',
    fix: 'C-bet 50-60% in SRPs. Check more on wet/connected boards (T98, 876), c-bet more on dry/high-card boards (AK2, KQ4).',
    weight: 3,
  },
},
cbet_flop_3bp: {
  total: {
    low: 60, high: 80,
    tipLow: 'Checking too much in 3-bet pots -- you have range advantage as the 3-bettor, use it',
    tipHigh: 'C-betting too wide in 3BP -- even with range advantage, some boards favor the caller (low connected)',
    fix: 'C-bet 65-75% in 3-bet pots. Use small sizing (25-33% pot) on most textures. Check on low/connected boards like 765.',
    weight: 3,
  },
},
fold_cbet_flop_srp: {
  total: {
    low: 35, high: 50,
    tipLow: 'Calling/raising too wide vs SRP c-bets -- you are bleeding chips with weak continues',
    tipHigh: 'Folding too much in SRPs -- villain can c-bet any two cards profitably against you',
    fix: 'Defend 50-65% vs SRP c-bets. Deep SPR means implied odds favor continuing with draws and pairs.',
    weight: 3,
  },
},
fold_cbet_flop_3bp: {
  total: {
    low: 25, high: 40,
    tipLow: 'Defending too wide vs 3BP c-bets -- their range is strong even when betting small',
    tipHigh: 'Folding too much in 3-bet pots -- your range is condensed and strong, defend more',
    fix: 'Defend 60-75% vs 3BP c-bets. Your calling range in a 3BP is already strong -- fold less than in SRPs, especially vs small sizings.',
    weight: 3,
  },
},
```

**Note on the fold-to-cbet asymmetry**: fold rates should be **lower** in 3-bet pots than SRPs because both players have strong ranges. The caller in a 3BP has already shown strength by calling (or the 3-bettor by 3-betting), so the defender's range connects with more boards. The low SPR also means draws have better pot odds to continue.

Add to `STAT_DISPLAY_NAMES`:

```typescript
cbet_flop_srp: 'CBet Flop (SRP)',
cbet_flop_3bp: 'CBet Flop (3BP)',
fold_cbet_flop_srp: 'Fold CBet (SRP)',
fold_cbet_flop_3bp: 'Fold CBet (3BP)',
```

---

## New Postflop Grid Layout (Complete)

```
Row  | Label              | Flop             | Turn             | River            | Source
-----|--------------------|------------------|------------------|------------------|--------
  1  | C-Bet              | cbet_flop.total  | cbet_turn.total  | cbet_river.total | EXISTING
  2  | Fold to CBet       | ftcb_flop.total  | ftcb_turn.total  | ftcb_river.total | EXISTING
  3  | CBet (SRP)         | cbet_flop_srp    | --               | --               | NEW
  4  | CBet (3BP)         | cbet_flop_3bp    | --               | --               | NEW
  5  | Fold CBet (SRP)    | fold_cbet_flop_srp| --              | --               | NEW
  6  | Fold CBet (3BP)    | fold_cbet_flop_3bp| --              | --               | NEW
  7  | Aggression         | af_flop          | af_turn          | af_river         | EXISTING
  8  | Agg Freq           | afq_flop         | afq_turn         | afq_river        | EXISTING
  9  | Donk Bet           | donk_bet_flop    | donk_bet_turn    | donk_bet_river   | EXISTING
```

---

## C-Bet Positional Sub-Section Spec

**Location**: Right side of the Postflop section, below the existing vs CBet Flop Response table.

**Table format**: Standard `PosTable` with full positional columns:

```
Stat              | Tot  | EP  | MP  | CO  | BTN | SB  | BB
C-Bet Flop        | 55%  | 48% | 52% | 58% | 60% | 50% | --
Fold to CBet Flop | 42%  | 38% | 40% | 44% | 46% | 45% | 40%
```

**Data source**: Reuses existing `stats.cbet_flop` and `stats.fold_to_cbet_flop` PositionalStats objects. These are already computed positionally by `_pos_stat()` in the backend. No new backend work needed.

**Label**: Footer text `"C-Bet Positional"` in the same style as the existing `"vs. C-Bet Flop"` label.

**Drill-down**: Each cell links to the appropriate drill-down page (`/stats/cbet_flop?pos=ep`, etc.) via the existing `posRow` helper which wires up `statKey` and `position` per cell.

**BB column note**: C-Bet Flop from BB will typically show very low sample or `--`. The BB rarely has c-bet opportunity (BB is last to act preflop so almost never the preflop raiser in a non-3-bet pot). This is expected behavior.

---

## Backend stat_registry Additions (Summary)

### STAT_REGISTRY (4 entries)

| Key | name | action_flag / action_sql | opp_flag / opp_sql |
|-----|------|--------------------------|---------------------|
| `cbet_flop_srp` | "C-Bet Flop (SRP)" | `action_flag: "cbet_flop"` | `opp_sql: "hp.cbet_flop_opp = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)"` |
| `cbet_flop_3bp` | "C-Bet Flop (3-Bet Pot)" | `action_flag: "cbet_flop"` | `opp_sql: "hp.cbet_flop_opp = TRUE AND hp.is_3bet_pot = TRUE"` |
| `fold_cbet_flop_srp` | "Fold to CBet Flop (SRP)" | `action_sql: "hp.fold_to_cbet_flop = TRUE"` | `opp_sql: "hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)"` |
| `fold_cbet_flop_3bp` | "Fold to CBet Flop (3-Bet Pot)" | `action_sql: "hp.fold_to_cbet_flop = TRUE"` | `opp_sql: "hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE"` |

### EV_BREAKDOWN_CONFIG (2 entries)

| Key | Scenarios |
|-----|-----------|
| `cbet_flop_srp` | "C-bet SRP" vs "Check SRP" |
| `cbet_flop_3bp` | "C-bet 3BP" vs "Check 3BP" |

### BY_CONTEXT_CONFIG (1 entry, optional)

| Key | Dimension | Group expression |
|-----|-----------|------------------|
| `cbet_flop` | `pot_type` | `CASE WHEN hp.is_3bet_pot = TRUE THEN '3-Bet Pot' ELSE 'Single Raised' END` |

---

## Benchmark Values

### C-Bet Flop by pot type

| Stat | Low | High | Healthy range explanation |
|------|-----|------|--------------------------|
| CBet Flop (SRP) | 45% | 65% | SRP has wide ranges. 50-60% is typical. Lower on wet boards, higher on dry. |
| CBet Flop (3BP) | 60% | 80% | 3-bettor has range advantage. 65-75% at small sizing. Lower on low boards. |

### Fold to CBet Flop by pot type

| Stat | Low | High | Healthy range explanation |
|------|-----|------|--------------------------|
| Fold CBet (SRP) | 35% | 50% | Defend 50-65% in SRPs. Deep SPR means good implied odds. |
| Fold CBet (3BP) | 25% | 40% | Defend 60-75% in 3BPs. Strong ranges + low SPR = defend more. |

**Cross-check**: CBet + Fold CBet should feel consistent:
- SRP: Hero c-bets 50% and villain folds to c-bet 40% -> coherent
- 3BP: Hero c-bets 70% and villain folds to c-bet 30% -> coherent (3-bettor fires often, caller defends often)

---

## Test Checklist

### Backend

- [ ] `cd backend && python -m pytest tests/test_parser.py -v` -- all existing tests pass
- [ ] Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
- [ ] `GET /api/stats/hero` returns the four new `StatValue` fields: `cbet_flop_srp`, `cbet_flop_3bp`, `fold_cbet_flop_srp`, `fold_cbet_flop_3bp`
- [ ] Each new field has `value` (float or null) and `sample` (int) properties
- [ ] `cbet_flop_srp.sample + cbet_flop_3bp.sample == cbet_flop.total.sample` (SRP + 3BP opportunities = total c-bet opportunities)
- [ ] `fold_cbet_flop_srp.sample + fold_cbet_flop_3bp.sample == fold_to_cbet_flop.total.sample` (SRP + 3BP faced = total faced)
- [ ] Verify SRP c-bet sample excludes hands where `is_3bet_pot = true` (query `hand_players` directly to cross-check)
- [ ] Verify 3BP c-bet sample includes 4BP and 5BP hands (all `is_3bet_pot = true`)
- [ ] Drill-down: `GET /api/stats/detail/hands?stat_key=cbet_flop_srp&page=1` returns hands correctly
- [ ] Drill-down: `GET /api/stats/detail/hands?stat_key=cbet_flop_3bp&page=1` returns hands correctly
- [ ] EV breakdown: `GET /api/stats/detail/ev-breakdown?stat_key=cbet_flop_srp` returns two scenarios
- [ ] EV breakdown: `GET /api/stats/detail/ev-breakdown?stat_key=cbet_flop_3bp` returns two scenarios

### Frontend

- [ ] `cd frontend && npm run dev` -- page loads without console errors
- [ ] Postflop by-street grid shows exactly 9 rows in the order: C-Bet, Fold to CBet, CBet (SRP), CBet (3BP), Fold CBet (SRP), Fold CBet (3BP), Aggression, Agg Freq, Donk Bet
- [ ] CBet (SRP) and CBet (3BP) rows show values in Flop column, dashes (`--`) in Turn and River columns
- [ ] Fold CBet (SRP) and Fold CBet (3BP) rows show values in Flop column, dashes in Turn and River columns
- [ ] C-Bet Positional sub-section appears below the vs CBet Flop Response table on the right side
- [ ] C-Bet Positional shows 2 rows (C-Bet Flop, Fold to CBet Flop) with all positional columns (Tot/EP/MP/CO/BTN/SB/BB)
- [ ] All new cells are clickable and navigate to the correct drill-down page
- [ ] Click CBet (SRP) -> navigates to `/stats/cbet_flop_srp`
- [ ] Click CBet (3BP) -> navigates to `/stats/cbet_flop_3bp`
- [ ] Click Fold CBet (SRP) -> navigates to `/stats/fold_cbet_flop_srp`
- [ ] Click Fold CBet (3BP) -> navigates to `/stats/fold_cbet_flop_3bp`
- [ ] Click C-Bet Flop in positional table (EP cell) -> navigates to `/stats/cbet_flop?pos=ep`
- [ ] Drill-down detail page loads and shows correct widgets (response_distribution, ev_breakdown, sizing_histogram, trend_sparkline for c-bet stats)
- [ ] `cd frontend && npm run lint` -- no lint errors

### Benchmark coloring

- [ ] CBet (SRP) at 55% shows green. At 30% shows red (too low). At 80% shows red (too high).
- [ ] CBet (3BP) at 70% shows green. At 45% shows red (too low). At 90% shows red (too high).
- [ ] Fold CBet (SRP) at 42% shows green. At 20% shows red (too low). At 65% shows red (too high).
- [ ] Fold CBet (3BP) at 32% shows green. At 15% shows red (too low). At 55% shows red (too high).

### Filters

- [ ] Stakes filter applied -> all new stat values update correctly
- [ ] Date range filter applied -> all new stat values update correctly
- [ ] Last N hands filter applied -> all new stat values update correctly

### Data integrity

- [ ] With no hands imported, all four new fields show `null` value and `0` sample
- [ ] After importing hands, SRP stats show meaningful values (should be larger sample than 3BP since most pots are SRP)
- [ ] The sum of SRP and 3BP c-bet opportunities matches the overall c-bet opportunity count

---

## Future Extensions (Out of Scope)

These are deliberately deferred but should be tracked:

- **Turn/River c-bet by pot type**: Double and triple barrel frequencies differ between SRP and 3BP. In 3BPs the turn c-bet is often higher because the PFR's range advantage persists. Adding `cbet_turn_srp` / `cbet_turn_3bp` follows the same pattern.
- **Multiway c-bet split**: The `is_multiway` flag already exists. C-bet frequency drops to 30-45% multiway. Splitting SRP into HU vs multiway would be high-value for coaching.
- **IP/OOP c-bet by pot type**: The `postflop_ip` flag exists. Combining pot type + position (IP/OOP) gives the most actionable c-bet stats (e.g., "C-Bet Flop SRP IP" vs "C-Bet Flop SRP OOP"). This is the gold standard in Hand2Note and should be a priority follow-up, likely in Phase 7.
- **Fold-to-cbet response decomposition by pot type**: In the fold-cbet-flop-srp drill-down, show fold/call/raise breakdown. The `response_distribution` widget should handle this if the STAT_REGISTRY entry uses `action_sql` / `opp_sql` correctly.
