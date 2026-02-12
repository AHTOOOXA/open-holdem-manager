# Phase 1 — Promote Stats to Positional Grid

## Goal

Move VPIP, PFR, 4-Bet, Fold to 4-Bet, and Limp from the KV grid to the Preflop positional table (`PosTable`). These stats already have `PositionalStats` data from the backend — they're just rendered as flat `StatValue` totals in the KV section. This phase surfaces positional breakdowns that are critical for coaching (EP 15% VPIP vs BTN 45%).

**Scope**: Frontend only. No backend changes.

## Current State

In `StatsPage.tsx`, the Preflop section has:
- **PosTable** (left): Open Raise, Fold to 3-Bet, Call Open, 3-Bet, 3-Bet IP, 3-Bet OOP
- **KVGrid** (right): VPIP, PFR, 4-Bet, Fold to 4-Bet, Limp, Squeeze, 5-Bet, Limp-Fold, 4-Bet-Fold, Call 4-Bet, 4-Bet Range, Win Rate, Win Rate EV, Hands

The backend already returns `vpip`, `pfr`, `four_bet`, `fold_to_4bet`, and `limp` as `PositionalStats` objects (with `total`, `ep`, `mp`, `co`, `btn`, `sb`, `bb` fields).

## Files to Modify

### 1. `frontend/src/pages/StatsPage.tsx`

#### Move rows into PosTable

Find the Preflop section's `PosTable` component. Add new rows for the promoted stats. The final row order should be:

```
Group "Entry":
  1. VPIP          (vpip)           ← NEW in PosTable
  2. PFR           (pfr)            ← NEW in PosTable
  3. Open Raise    (open_raise)     — already here
  4. Limp          (limp)           ← NEW in PosTable
Group "vs Open":
  5. Call Open     (call_open_raise) — already here
  6. 3-Bet         (three_bet)      — already here
  7. 3-Bet IP      (three_bet_ip)   — already here
  8. 3-Bet OOP     (three_bet_oop)  — already here
Group "vs 3-Bet":
  9. Fold to 3-Bet (fold_to_3bet)   — already here
  10. 4-Bet        (four_bet)        ← NEW in PosTable
Group "vs 4-Bet":
  11. Fold to 4-Bet (fold_to_4bet)   ← NEW in PosTable
```

Each row in the PosTable is defined as an array of `CellDef` objects (one per column: stat label + Tot + EP + MP + CO + BTN + SB + BB). Follow the existing pattern for `open_raise`:

```tsx
// Example: existing open_raise row
{
  label: 'Open Raise',
  cells: [
    { sv: stats.open_raise.total, statKey: 'open_raise' },
    { sv: stats.open_raise.ep, statKey: 'open_raise', position: 'ep' },
    { sv: stats.open_raise.mp, statKey: 'open_raise', position: 'mp' },
    // ... co, btn, sb, bb
  ]
}
```

Add VPIP, PFR, 4-Bet, Fold to 4-Bet, Limp rows following the same pattern. The `statKey` for each:
- VPIP → `'vpip'`
- PFR → `'pfr'`
- Limp → `'limp'`
- 4-Bet → `'four_bet'`
- Fold to 4-Bet → `'fold_to_4bet'`

#### Remove from KV grid

Remove VPIP, PFR, 4-Bet, Fold to 4-Bet, and Limp from the KV grid section. They should no longer appear in the right-side flat stats.

The KV grid should retain:
- 5-Bet, Call 4-Bet, 4-Bet-Fold, Limp-Fold, 4-Bet Range, Fold to Squeeze
- Win Rate, Win Rate EV, Hands

### 2. `frontend/src/lib/stat-registry.ts`

No changes needed. These stats are already registered with `isPositional: true`:
- `vpip`: `isPositional: true`
- `pfr`: `isPositional: true`
- `four_bet`: `isPositional: true`
- `fold_to_4bet`: `isPositional: true` (verify — if currently false, change to true)
- `limp`: `isPositional: true`

### 3. `frontend/src/lib/benchmarks.ts`

Add positional benchmarks for the promoted stats. Currently these have `total` benchmarks only. Add position-specific ranges:

```typescript
vpip: {
  total: { low: 20, high: 28, ... },
  ep: { low: 12, high: 18, ... },
  mp: { low: 15, high: 22, ... },
  co: { low: 24, high: 32, ... },
  btn: { low: 35, high: 50, ... },
  sb: { low: 28, high: 40, ... },
  bb: { low: 30, high: 45, ... },
}
```

**VPIP positional benchmarks** (6-max cash):
| Position | Low | High |
|----------|-----|------|
| EP | 12 | 18 |
| MP | 15 | 22 |
| CO | 24 | 32 |
| BTN | 35 | 50 |
| SB | 28 | 40 |
| BB | — | — (BB VPIP is misleading — depends on limps/raises) |

**PFR positional benchmarks** (6-max cash):
| Position | Low | High |
|----------|-----|------|
| EP | 10 | 16 |
| MP | 13 | 19 |
| CO | 20 | 28 |
| BTN | 30 | 45 |
| SB | 22 | 35 |
| BB | 8 | 14 |

**4-Bet positional benchmarks**:
| Position | Low | High |
|----------|-----|------|
| EP | 2 | 5 |
| MP | 2 | 6 |
| CO | 3 | 7 |
| BTN | 4 | 9 |
| SB | 3 | 8 |
| BB | 3 | 7 |

**Fold to 4-Bet** — keep total benchmark only (55-65%). Positional variance is less meaningful here since it depends more on 3-bet range composition.

**Limp** — no positional benchmarks. The overall benchmark (0-3%) applies everywhere. Limping is almost always a leak regardless of position.

## Verification

1. `cd frontend && npm run dev` — page loads without errors
2. Preflop PosTable shows 11 rows with group headers (Entry, vs Open, vs 3-Bet, vs 4-Bet)
3. VPIP/PFR/Limp/4-Bet/Fold-to-4-Bet cells show positional values (not just total)
4. Each cell is clickable → navigates to `/stats/{statKey}` drill-down
5. Benchmark colors apply per-position (EP VPIP green at 15%, red at 30%)
6. KV grid no longer shows the promoted stats
7. `cd frontend && npm run lint` — no lint errors
