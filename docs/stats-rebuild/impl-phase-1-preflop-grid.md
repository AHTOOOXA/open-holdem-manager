# Phase 1 Implementation Plan -- Preflop Positional Grid Restructure

## Goal

Promote VPIP, PFR, 4-Bet, Fold to 4-Bet, and Limp from the flat KV grid into the Preflop `PosTable`, so each stat renders with EP/MP/CO/BTN/SB/BB positional breakdowns. Deprecate the `3-Bet IP` and `3-Bet OOP` rows (they will be replaced by an IP/OOP filter on the 3-Bet detail page in Phase 7). Merge `4-Bet Range` into `4-Bet` (4-Bet already covers the same concept once promoted to the positional grid).

**Scope**: Frontend only. Zero backend changes. The backend already returns `vpip`, `pfr`, `four_bet`, `fold_to_4bet`, and `limp` as `PositionalStats` objects -- they are just not rendered positionally today.

**Risk**: Low. All data already flows from the backend. This is a layout reorganization with benchmark additions.

---

## Files to Modify

### 1. `frontend/src/pages/StatsPage.tsx`

#### A. PosTable rows -- new order

Replace the existing `PosTable` rows block (lines 662-669) with the following 11 rows:

```tsx
<PosTable
  headers={fullPosHeaders}
  driftMap={driftMap}
  onStatClick={handleStatClick}
  rows={[
    // Group: Entry
    posRow('VPIP',          stats.vpip,           'vpip',          fullPosKeys),
    posRow('PFR',           stats.pfr,            'pfr',           fullPosKeys),
    posRow('Open Raise',    stats.open_raise,     'open_raise',    fullPosKeys),
    posRow('Limp',          stats.limp,           'limp',          fullPosKeys),
    // Group: vs Open
    posRow('Call Open',     stats.call_open_raise, undefined,      fullPosKeys, 'call_open_raise'),
    posRow('3-Bet',         stats.three_bet,      'three_bet',     fullPosKeys),
    // Group: vs 3-Bet
    posRow('Fold to 3-Bet', stats.fold_to_3bet,   'fold_to_3bet',  fullPosKeys),
    posRow('4-Bet',         stats.four_bet,       'four_bet',      fullPosKeys),
    // Group: vs 4-Bet
    posRow('Fold to 4-Bet', stats.fold_to_4bet,   'fold_to_4bet',  fullPosKeys),
  ]}
/>
```

**What changed vs. current:**

| Action | Stat | Detail |
|--------|------|--------|
| ADD row | VPIP | Was in KV grid as `stats.vpip.total`. Now `posRow('VPIP', stats.vpip, 'vpip', fullPosKeys)`. |
| ADD row | PFR | Was in KV grid as `stats.pfr.total`. Now `posRow('PFR', stats.pfr, 'pfr', fullPosKeys)`. |
| ADD row | Limp | Was in KV grid as `stats.limp.total`. Now `posRow('Limp', stats.limp, 'limp', fullPosKeys)`. |
| ADD row | 4-Bet | Was in KV grid as `stats.four_bet.total`. Now `posRow('4-Bet', stats.four_bet, 'four_bet', fullPosKeys)`. |
| ADD row | Fold to 4-Bet | Was in KV grid as `stats.fold_to_4bet.total`. Now `posRow('Fold to 4-Bet', stats.fold_to_4bet, 'fold_to_4bet', fullPosKeys)`. |
| REORDER | Fold to 3-Bet | Was row 2. Now row 7 (grouped with vs-3-Bet context). |
| REMOVE row | 3-Bet IP | Deprecated. Replaced by IP/OOP filter on 3-Bet detail page (Phase 7). |
| REMOVE row | 3-Bet OOP | Deprecated. Same reason. |
| KEEP row | Open Raise | No change. |
| KEEP row | Call Open | No change. |
| KEEP row | 3-Bet | No change. |

No group header divider rows for now. Rows are ordered logically so the grouping is implicit. Group headers can be added as a follow-up.

#### B. KV grid -- remove promoted stats, remove deprecated stats

Replace the KV grid items block (lines 678-693) with:

```tsx
<KVGrid
  driftMap={driftMap}
  onStatClick={handleStatClick}
  items={[
    { label: 'Squeeze', sv: stats.squeeze, drillKey: 'squeeze' },
    { label: 'Limp-Fold', sv: stats.limp_fold, drillKey: 'limp_fold' },
    { label: '5-Bet', sv: stats.five_bet, drillKey: 'five_bet' },
    { label: '4-Bet-Fold', sv: stats.four_bet_fold, drillKey: 'four_bet_fold' },
    { label: 'Call 4-Bet', sv: stats.call_4bet, drillKey: 'call_4bet' },
    { label: 'Win Rate', sv: wr !== null ? { value: wr, sample: stats.hands } : undefined, colorFn: (v: number) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
    { label: 'Win Rate EV', sv: wrEv !== null ? { value: wrEv, sample: stats.hands } : undefined, colorFn: (v: number) => v >= 0 ? 'text-green' : 'text-red', decimals: 2 },
    { label: 'Hands', sv: { value: stats.hands, sample: stats.hands } },
  ]}
/>
```

**What changed vs. current:**

| Action | Item | Reason |
|--------|------|--------|
| REMOVE | VPIP | Promoted to PosTable. |
| REMOVE | PFR | Promoted to PosTable. |
| REMOVE | 4-Bet | Promoted to PosTable. |
| REMOVE | Limp | Promoted to PosTable. |
| REMOVE | Fold to 4-Bet | Promoted to PosTable. |
| REMOVE | 4-Bet Range | Merged into 4-Bet. Redundant once 4-Bet is positional. |
| KEEP | Squeeze | Not a `PositionalStats` on the backend. Stays flat. |
| KEEP | Limp-Fold | Flat stat. |
| KEEP | 5-Bet | Flat stat. |
| KEEP | 4-Bet-Fold | Flat stat. |
| KEEP | Call 4-Bet | Flat stat. |
| KEEP | Win Rate | Not positional. |
| KEEP | Win Rate EV | Not positional. |
| KEEP | Hands | Not positional. |

The grid shrinks from 14 items to 8 items. It should still render fine in the 2-column layout (4 rows).

---

### 2. `frontend/src/lib/benchmarks.ts`

Add positional benchmark entries for the 5 promoted stats. Currently each has only a `total` key. Add `ep`, `mp`, `co`, `btn`, `sb`, `bb` keys.

#### VPIP -- add positional benchmarks

Replace the existing `vpip` entry (lines 61-70) with:

```typescript
vpip: {
  total: {
    low: 20, high: 28,
    tipLow: 'Playing too few hands. Widen your opening range, especially in position.',
    tipHigh: 'Playing too many hands. Tighten preflop -- fold more weak holdings.',
    fix: 'Review your opening ranges by position. Compare to standard GTO charts.',
    weight: 5,
    statFlagFilter: 'vpip',
  },
  ep: { low: 12, high: 18, tipLow: 'EP VPIP too tight. Missing value with playable hands.', tipHigh: 'EP VPIP too loose. Tighten from early position.', fix: 'EP should play ~15% of hands.', weight: 3 },
  mp: { low: 15, high: 22, tipLow: 'MP VPIP too tight.', tipHigh: 'MP VPIP too loose.', fix: 'MP should play ~18% of hands.', weight: 3 },
  co: { low: 24, high: 32, tipLow: 'CO VPIP too tight. Open wider in the cutoff.', tipHigh: 'CO VPIP too loose.', fix: 'CO should play ~28% of hands.', weight: 3 },
  btn: { low: 35, high: 50, tipLow: 'BTN VPIP too tight. You have position -- play wider.', tipHigh: 'BTN VPIP too loose.', fix: 'BTN should play ~42% of hands.', weight: 3 },
  sb: { low: 28, high: 40, tipLow: 'SB VPIP too tight.', tipHigh: 'SB VPIP too loose. Cold-calling OOP is expensive.', fix: 'SB VPIP-PFR gap should be 0-5%. Raise or fold.', weight: 3 },
  bb: { low: 35, high: 55, tipLow: 'BB VPIP too tight. Defend more vs steals.', tipHigh: 'BB VPIP too loose. Overdefending OOP costs money.', fix: 'BB defends wide vs steals. Adjust by raiser position.', weight: 3 },
},
```

#### PFR -- add positional benchmarks

Replace the existing `pfr` entry (lines 71-80) with:

```typescript
pfr: {
  total: {
    low: 16, high: 24,
    tipLow: 'Too passive preflop. Raise more instead of limping or cold-calling.',
    tipHigh: 'Too aggressive preflop. Narrow your raising range.',
    fix: 'Your VPIP-PFR gap should be ~4-6%. Reduce cold-calls and limps.',
    weight: 5,
    statFlagFilter: 'pfr',
  },
  ep: { low: 10, high: 16, tipLow: 'EP PFR too tight.', tipHigh: 'EP PFR too loose.', fix: 'EP should raise ~13%.', weight: 3 },
  mp: { low: 13, high: 19, tipLow: 'MP PFR too tight.', tipHigh: 'MP PFR too loose.', fix: 'MP should raise ~16%.', weight: 3 },
  co: { low: 20, high: 28, tipLow: 'CO PFR too tight.', tipHigh: 'CO PFR too loose.', fix: 'CO should raise ~24%.', weight: 3 },
  btn: { low: 30, high: 45, tipLow: 'BTN PFR too tight. Raise wider on the button.', tipHigh: 'BTN PFR too loose.', fix: 'BTN should raise ~37%.', weight: 3 },
  sb: { low: 25, high: 38, tipLow: 'SB PFR too tight. Modern SB strategy is raise-or-fold.', tipHigh: 'SB PFR too loose.', fix: 'SB PFR should be close to SB VPIP. Raise or fold.', weight: 3 },
  bb: { low: 8, high: 14, tipLow: 'BB PFR too tight. Missing 3-bet and squeeze opportunities.', tipHigh: 'BB PFR too high. Over-3-betting from the big blind.', fix: 'BB PFR = 3-bets + squeezes from BB.', weight: 3 },
},
```

#### 4-Bet -- add positional benchmarks

Replace the existing `four_bet` entry (lines 119-129) with:

```typescript
four_bet: {
  total: {
    low: 3, high: 7,
    tipLow: 'Not 4-betting enough. Only premiums -- too predictable.',
    tipHigh: 'Over 4-betting. Opponents will trap with strong hands.',
    fix: 'Balance 4-bet range: ~50% value (QQ+, AKs), ~50% bluffs (A5s, A4s).',
    weight: 2,
    statFlagFilter: 'four_bet',
    oppFlagFilter: 'four_bet_opp',
  },
  ep: { low: 8, high: 18, tipLow: 'EP 4-bet too low vs 3-bets.', tipHigh: 'EP 4-bet too high.', fix: 'EP opens tight so 4-bets a large % when 3-bet.', weight: 2 },
  mp: { low: 6, high: 14, tipLow: 'MP 4-bet too low.', tipHigh: 'MP 4-bet too high.', fix: 'Target 6-14% 4-bet from MP.', weight: 2 },
  co: { low: 5, high: 12, tipLow: 'CO 4-bet too low.', tipHigh: 'CO 4-bet too high.', fix: 'Target 5-12% 4-bet from CO.', weight: 2 },
  btn: { low: 5, high: 11, tipLow: 'BTN 4-bet too low.', tipHigh: 'BTN 4-bet too high.', fix: 'Target 5-11% 4-bet from BTN.', weight: 2 },
  sb: { low: 4, high: 10, tipLow: 'SB 4-bet too low.', tipHigh: 'SB 4-bet too high.', fix: 'Target 4-10% 4-bet from SB.', weight: 2 },
  bb: { low: 5, high: 12, tipLow: 'BB 4-bet too low.', tipHigh: 'BB 4-bet too high.', fix: 'BB 4-bets after 3-betting vs an open.', weight: 2 },
},
```

#### Fold to 4-Bet -- add positional benchmarks

Replace the existing `fold_to_4bet` entry (lines 130-140) with:

```typescript
fold_to_4bet: {
  total: {
    low: 55, high: 65,
    tipLow: 'Defending too wide vs 4-bets. Only continue with strong hands.',
    tipHigh: 'Folding too much to 4-bets. Your 3-bet bluffs are getting exploited.',
    fix: 'Continue vs 4-bet with premiums + some suited combos with equity.',
    weight: 2,
    statFlagFilter: 'fold_to_4bet',
    oppFlagFilter: 'four_bet_opp',
  },
  ep: { low: 40, high: 55, tipLow: 'EP: defending too wide vs 4-bets.', tipHigh: 'EP: folding too much vs 4-bets.', fix: 'EP 3-bets tight, so defend more vs 4-bets.', weight: 2 },
  mp: { low: 45, high: 58, tipLow: 'MP: defending too wide vs 4-bets.', tipHigh: 'MP: folding too much vs 4-bets.', fix: 'Target 45-58% fold-to-4-bet from MP.', weight: 2 },
  co: { low: 50, high: 63, tipLow: 'CO: defending too wide vs 4-bets.', tipHigh: 'CO: folding too much vs 4-bets.', fix: 'Target 50-63% fold-to-4-bet from CO.', weight: 2 },
  btn: { low: 55, high: 68, tipLow: 'BTN: defending too wide vs 4-bets.', tipHigh: 'BTN: folding too much vs 4-bets.', fix: 'BTN 3-bets wider so folds more to 4-bets.', weight: 2 },
  sb: { low: 50, high: 65, tipLow: 'SB: defending too wide vs 4-bets.', tipHigh: 'SB: folding too much vs 4-bets.', fix: 'Target 50-65% fold-to-4-bet from SB.', weight: 2 },
  bb: { low: 45, high: 60, tipLow: 'BB: defending too wide vs 4-bets.', tipHigh: 'BB: folding too much vs 4-bets.', fix: 'Target 45-60% fold-to-4-bet from BB.', weight: 2 },
},
```

#### Limp -- add positional benchmarks

Currently, `limp` has no entry in `BENCHMARKS` at all (it was a KV-only item with no `statKey`, only a `drillKey`). Add a new entry:

```typescript
limp: {
  total: {
    low: 0, high: 5,
    tipLow: 'N/A',
    tipHigh: 'Limping too much. Open raise or fold instead.',
    fix: 'Eliminate open limps from EP-BTN. Raise or fold.',
    weight: 3,
    statFlagFilter: 'limp',
  },
  ep: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from EP is a major leak.', fix: 'Never limp from EP. Raise or fold.', weight: 3 },
  mp: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from MP is a major leak.', fix: 'Never limp from MP. Raise or fold.', weight: 3 },
  co: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from CO is a major leak.', fix: 'Never limp from CO. Raise or fold.', weight: 3 },
  btn: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from BTN is a major leak.', fix: 'Never limp from BTN. Raise or fold.', weight: 3 },
  sb: { low: 0, high: 100, tipLow: 'N/A', tipHigh: 'N/A', fix: 'SB limp (completing) is a valid strategy.', weight: 0 },
  bb: { low: 0, high: 100, tipLow: 'N/A', tipHigh: 'N/A', fix: 'BB cannot limp.', weight: 0 },
},
```

**Note on SB/BB limp benchmarks**: Setting `low: 0, high: 100` with `weight: 0` means `getStatHealth()` will always return `'green'` for SB and BB limp. This is intentional -- SB completing is a legitimate strategy (20-50% is common), and BB "limping" is not a meaningful concept (checking the big blind is not a limp). The `weight: 0` also ensures these never surface as leaks in `computeLeaks()`.

#### Also add `limp` to `STAT_DISPLAY_NAMES`

Add to the `STAT_DISPLAY_NAMES` record:

```typescript
limp: 'Limp',
```

---

### 3. `frontend/src/lib/stat-registry.ts`

#### Remove `four_bet_range` entry

Delete this line:

```typescript
four_bet_range:    { displayName: '4-Bet Range',       heroStatsField: 'four_bet_range',    isPositional: false, widgets: ['trend_sparkline'] },
```

`4-Bet Range` is redundant with the positional 4-Bet row. The stat is being fully merged into `four_bet`.

#### Deprecate `three_bet_ip` and `three_bet_oop` entries (optional, can keep for now)

These entries power the detail drill-down pages at `/stats/three_bet_ip` and `/stats/three_bet_oop`. Since we are removing the PosTable rows that link to them, there is no in-page navigation path to these detail pages. However, keeping the registry entries is harmless and allows direct URL access to still work. **Recommendation**: keep them for now, remove in Phase 7 when the IP/OOP filter on the 3-Bet detail page replaces them.

#### Verify `limp` entry has `statKey`-compatible setup

The existing entry is:
```typescript
limp: { displayName: 'Limp', heroStatsField: 'limp', isPositional: true, widgets: [...] },
```

This is correct. `isPositional: true` already. No change needed.

#### Verify `fold_to_4bet` entry

The existing entry is:
```typescript
fold_to_4bet: { displayName: 'Fold to 4-Bet', heroStatsField: 'fold_to_4bet', isPositional: true, widgets: [...] },
```

Correct. `isPositional: true`. No change needed.

---

### 4. `frontend/src/lib/api.ts` -- no changes

`HeroStats` already declares:
- `vpip: PositionalStats`
- `pfr: PositionalStats`
- `four_bet: PositionalStats`
- `fold_to_4bet: PositionalStats`
- `limp: PositionalStats`

No API type changes needed.

---

## Summary: Exact New PosTable Row Order

```
Row  | Label           | statKey        | drillKey          | Source
-----|-----------------|----------------|-------------------|------------------
  1  | VPIP            | vpip           | vpip              | NEW (from KV)
  2  | PFR             | pfr            | pfr               | NEW (from KV)
  3  | Open Raise      | open_raise     | open_raise        | EXISTING
  4  | Limp            | limp           | limp              | NEW (from KV)
  5  | Call Open       | (none)         | call_open_raise   | EXISTING
  6  | 3-Bet           | three_bet      | three_bet         | EXISTING
  7  | Fold to 3-Bet   | fold_to_3bet   | fold_to_3bet      | EXISTING (reordered)
  8  | 4-Bet           | four_bet       | four_bet          | NEW (from KV)
  9  | Fold to 4-Bet   | fold_to_4bet   | fold_to_4bet      | NEW (from KV)
```

Total: 9 rows (was 6 rows). Net: +5 promoted, -2 deprecated (3-Bet IP, 3-Bet OOP).

---

## Summary: Exact New KV Grid Items

```
Row  | Label           | sv source                          | statKey   | drillKey        | decimals
-----|-----------------|-------------------------------------|-----------|-----------------|----------
  1  | Squeeze         | stats.squeeze                      | (none)    | squeeze         | 0
  2  | Limp-Fold       | stats.limp_fold                    | (none)    | limp_fold       | 0
  3  | 5-Bet           | stats.five_bet                     | (none)    | five_bet        | 0
  4  | 4-Bet-Fold      | stats.four_bet_fold                | (none)    | four_bet_fold   | 0
  5  | Call 4-Bet      | stats.call_4bet                    | (none)    | call_4bet       | 0
  6  | Win Rate        | { value: wr, sample: stats.hands } | (none)    | (none)          | 2
  7  | Win Rate EV     | { value: wrEv, sample: stats.hands}| (none)    | (none)          | 2
  8  | Hands           | { value: stats.hands, sample: ... }| (none)    | (none)          | 0
```

Total: 8 items (was 14). Removed: VPIP, PFR, 4-Bet, Limp, 4-Bet Range, Fold to 4-Bet.

---

## Benchmark Values to Add to `benchmarks.ts`

### VPIP positional

| Position | Low | High |
|----------|-----|------|
| EP       | 12  | 18   |
| MP       | 15  | 22   |
| CO       | 24  | 32   |
| BTN      | 35  | 50   |
| SB       | 28  | 40   |
| BB       | 35  | 55   |

### PFR positional

| Position | Low | High |
|----------|-----|------|
| EP       | 10  | 16   |
| MP       | 13  | 19   |
| CO       | 20  | 28   |
| BTN      | 30  | 45   |
| SB       | 25  | 38   |
| BB       | 8   | 14   |

### 4-Bet positional (opportunity-based: 4-bet / faced 3-bet)

| Position | Low | High |
|----------|-----|------|
| EP       | 8   | 18   |
| MP       | 6   | 14   |
| CO       | 5   | 12   |
| BTN      | 5   | 11   |
| SB       | 4   | 10   |
| BB       | 5   | 12   |

### Fold to 4-Bet positional (opportunity-based: fold to 4-bet / faced 4-bet)

| Position | Low | High |
|----------|-----|------|
| EP       | 40  | 55   |
| MP       | 45  | 58   |
| CO       | 50  | 63   |
| BTN      | 55  | 68   |
| SB       | 50  | 65   |
| BB       | 45  | 60   |

### Limp positional

| Position | Low | High | Coloring behavior |
|----------|-----|------|-------------------|
| EP       | 0   | 3    | Red if above 3%   |
| MP       | 0   | 3    | Red if above 3%   |
| CO       | 0   | 3    | Red if above 3%   |
| BTN      | 0   | 3    | Red if above 3%   |
| SB       | 0   | 100  | Always green (neutral). SB completing is valid. weight=0. |
| BB       | 0   | 100  | Always green (neutral). BB cannot limp. weight=0. |

---

## `stat-registry.ts` Changes

| Action | Key | Detail |
|--------|-----|--------|
| DELETE | `four_bet_range` | Merged into `four_bet`. Remove entire entry. |
| KEEP | `three_bet_ip` | Keep for now. Entry is harmless. Remove in Phase 7. |
| KEEP | `three_bet_oop` | Keep for now. Entry is harmless. Remove in Phase 7. |
| VERIFY | `vpip` | `isPositional: true` -- already correct. |
| VERIFY | `pfr` | `isPositional: true` -- already correct. |
| VERIFY | `four_bet` | `isPositional: true` -- already correct. |
| VERIFY | `fold_to_4bet` | `isPositional: true` -- already correct. |
| VERIFY | `limp` | `isPositional: true` -- already correct. |

Also add `limp: 'Limp'` to `STAT_DISPLAY_NAMES` in `benchmarks.ts` (it is referenced by the benchmark tooltip system).

---

## Test Checklist

### Functional

- [ ] `cd frontend && npm run dev` -- page loads without console errors
- [ ] Preflop PosTable shows exactly 9 rows in this order: VPIP, PFR, Open Raise, Limp, Call Open, 3-Bet, Fold to 3-Bet, 4-Bet, Fold to 4-Bet
- [ ] 3-Bet IP and 3-Bet OOP rows are gone from the PosTable
- [ ] KV grid shows exactly 8 items: Squeeze, Limp-Fold, 5-Bet, 4-Bet-Fold, Call 4-Bet, Win Rate, Win Rate EV, Hands
- [ ] 4-Bet Range is gone from the KV grid
- [ ] VPIP/PFR/Limp/4-Bet/Fold-to-4-Bet cells show per-position values (not just total)

### Benchmarks and coloring

- [ ] EP VPIP at 15% shows green. EP VPIP at 30% shows red.
- [ ] BTN PFR at 35% shows green. BTN PFR at 10% shows red.
- [ ] SB Limp cell shows neutral coloring regardless of value (no red/green leak flag)
- [ ] BB Limp cell shows neutral coloring (or `--` / `0`)
- [ ] EP Limp at 8% shows red. EP Limp at 1% shows green.
- [ ] 4-Bet positional cells show subscript sample counts when opportunities < 10
- [ ] Fold to 4-Bet positional cells show subscript sample counts when opportunities < 10
- [ ] Tooltips show correct positional benchmark ranges on hover (e.g. "EP VPIP: Target 12-18")

### Drill-down navigation

- [ ] Click any VPIP cell -> navigates to `/stats/vpip`
- [ ] Click any PFR cell -> navigates to `/stats/pfr`
- [ ] Click any Limp cell -> navigates to `/stats/limp`
- [ ] Click any 4-Bet cell -> navigates to `/stats/four_bet`
- [ ] Click any Fold to 4-Bet cell -> navigates to `/stats/fold_to_4bet`
- [ ] Clicking a positional cell (e.g. EP column) passes `?pos=ep` to the detail page
- [ ] Open Raise, Call Open, 3-Bet, Fold to 3-Bet drill-downs still work as before

### Drift arrows

- [ ] VPIP and PFR drift arrows render in the Total column (if drift data available, i.e. 20k+ hands)
- [ ] Drift arrows use benchmark midpoint to determine green/red direction

### Leak summary panel

- [ ] `computeLeaks()` still detects leaks for VPIP, PFR, 4-Bet, Fold to 4-Bet using `total` benchmarks
- [ ] Limp leak detection works: total Limp > 5% flags as red (using total benchmark)
- [ ] SB/BB limp values do not surface as leaks (weight=0)

### Filters

- [ ] Stakes filter applied -> all positional values update
- [ ] Date range filter applied -> all positional values update
- [ ] Last N hands filter applied -> all positional values update

### Lint

- [ ] `cd frontend && npm run lint` -- no errors
