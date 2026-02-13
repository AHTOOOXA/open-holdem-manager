# Phase 1 — Promote Stats to Positional Grid

## Goal

Move VPIP, PFR, 4-Bet, Fold to 4-Bet, and Limp from the KV grid to the Preflop positional table (`PosTable`). These stats already have `PositionalStats` data from the backend — they're just rendered as flat `StatValue` totals in the KV section. This phase surfaces positional breakdowns that are critical for coaching (EP 15% VPIP vs BTN 45%).

**Coaching note — VPIP-PFR gap**: With VPIP and PFR side by side in the positional grid, the gap between them becomes visible per position. A healthy gap is 4-6%. A gap above 8% signals too much cold-calling or limping. This is one of the first things a coach checks.

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
  9. Fold to 3-Bet (fold_to_3bet)   — already here (REORDERED: was row 2, moves to group)
  10. 4-Bet        (four_bet)        ← NEW in PosTable
Group "vs 4-Bet":
  11. Fold to 4-Bet (fold_to_4bet)   ← NEW in PosTable

**Note on group headers**: The existing `PosTable` component has no group header/divider row mechanism. For Phase 1, just order the rows as shown. Group header rendering (e.g. thin divider rows with labels) can be added in a follow-up.
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
- Squeeze, 5-Bet, Call 4-Bet, 4-Bet-Fold, Limp-Fold, 4-Bet Range, Fold to Squeeze
- Win Rate, Win Rate EV, Hands

**Why Squeeze stays in KV**: Squeeze is inherently positional (almost always from the blinds), but it is not currently backed by `PositionalStats` from the backend — it's a flat `StatValue`. Promoting it would require backend changes, which are out of scope for this phase.

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
  bb: { low: 35, high: 55, ... },
}
```

**VPIP positional benchmarks** (6-max cash):
| Position | Low | High | Notes |
|----------|-----|------|-------|
| EP | 12 | 18 | |
| MP | 15 | 22 | |
| CO | 24 | 32 | |
| BTN | 35 | 50 | |
| SB | 28 | 40 | SB VPIP-PFR gap should be 0-5%. A large gap means too much cold-calling OOP. |
| BB | 35 | 55 | BB defends wide vs steals. Range depends on open-raiser position and sizing. |

**PFR positional benchmarks** (6-max cash):
| Position | Low | High | Notes |
|----------|-----|------|-------|
| EP | 10 | 16 | |
| MP | 13 | 19 | |
| CO | 20 | 28 | |
| BTN | 30 | 45 | |
| SB | 25 | 38 | Modern SB strategy is raise-or-fold. SB PFR should be close to SB VPIP. |
| BB | 8 | 14 | BB PFR = 3-bets + squeezes from BB. |

**4-Bet positional benchmarks** (opportunity-based: 4-bet / faced 3-bet):

The backend computes 4-bet as `four_bet / four_bet_opp`, meaning the percentage of the time a player 4-bets *when they face a 3-bet*. This denominator matters: EP faces fewer 3-bets but 4-bets a large portion of them because EP's opening range is already strong.

| Position | Low | High | Notes |
|----------|-----|------|-------|
| EP | 8 | 18 | EP opens tight, so 4-bets a large % when 3-bet. |
| MP | 6 | 14 | |
| CO | 5 | 12 | |
| BTN | 5 | 11 | |
| SB | 4 | 10 | |
| BB | 5 | 12 | BB 4-bets after 3-betting vs an open. |

**Sample size warning**: 4-bet opportunities accumulate slowly (~3-5% of hands per position). Positional cells will show noisy data for the first few thousand hands. The subscript sample indicator will flag low-confidence cells.

**Fold to 4-Bet positional benchmarks** (opportunity-based: fold to 4-bet / faced 4-bet):

Position matters because your 3-bet range composition varies by position. From EP/MP you 3-bet tighter ranges, so you fold less to 4-bets. From BTN/SB you 3-bet wider (more bluffs), so you fold more.

| Position | Low | High | Notes |
|----------|-----|------|-------|
| EP | 40 | 55 | Tighter 3-bet range = defend more vs 4-bets. |
| MP | 45 | 58 | |
| CO | 50 | 63 | |
| BTN | 55 | 68 | Wider 3-bet range = fold more bluffs to 4-bets. |
| SB | 50 | 65 | |
| BB | 45 | 60 | |

**Sample size warning**: Same caveat as 4-bet — facing a 4-bet is even rarer. Total benchmark of 55-65% is reliable sooner; positional breakdown needs many thousands of hands.

**Limp positional benchmarks**:

Limping from EP through BTN is almost always a leak (benchmark 0-3%). However, **SB limp (completing) is a legitimate strategy**, especially in rake-heavy environments. Many winning regs limp SB 30-60% of the time rather than raising small, because SB raises get 3-bet frequently and play poorly OOP postflop.

| Position | Low | High | Notes |
|----------|-----|------|-------|
| EP-BTN | 0 | 3 | Limping from these positions is nearly always a leak. |
| SB | 20 | 50 | SB complete is a valid strategy. No benchmark coloring — mark as neutral. |
| BB | — | — | BB cannot limp (already has blind posted; checking is not a limp). |

For the implementation: apply the 0-3% benchmark to EP/MP/CO/BTN. Mark SB as `neutral` (no coloring). BB limp should always show 0 or `--`.

## Verification

1. `cd frontend && npm run dev` — page loads without errors
2. Preflop PosTable shows 11 rows in the specified order (group headers are a future follow-up)
3. VPIP/PFR/Limp/4-Bet/Fold-to-4-Bet cells show positional values (not just total)
4. Each cell is clickable → navigates to `/stats/{statKey}` drill-down
5. Benchmark colors apply per-position (EP VPIP green at 15%, red at 30%)
6. BB VPIP shows a benchmark (green in 35-55% range), not a dash
7. SB Limp cell shows neutral coloring (no red/green), not flagged as a leak
8. 4-Bet positional cells show subscript sample counts (opportunities accumulate slowly)
9. KV grid no longer shows the promoted stats (but still shows Squeeze, 5-Bet, etc.)
10. `cd frontend && npm run lint` — no lint errors
