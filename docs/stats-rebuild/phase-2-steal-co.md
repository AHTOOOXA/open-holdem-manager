# Phase 2 — Add CO Column to Steal Section

## Goal

Add the CO (cutoff) column to the Steal Attempted section. CO steals are a core steal concept because you open into only 3 remaining players (BTN, SB, BB), yet unlike BTN steals, the BTN can flat to play in position against you — creating unique postflop dynamics that require a separate column to track. The backend already computes the main steal stat for CO via `_pos_steal("steal", "steal_opp", ["CO", "BTN", "SB"])`, but the steal sub-stats (Fold to 3-Bet, 4-Bet, 4-Bet-Fold) are missing CO, and the frontend doesn't render any CO column.

**Scope**: Frontend + small backend fix (3 lines in `stats_engine.py`).

## Current State

In `StatsPage.tsx`, the Steal section has:
- **Left (Steal Attempted)**: Columns `Stat | Tot | BTN | SB` — rows: Steal, Fold to 3-Bet, 4-Bet, 4-Bet-Fold
- **Right (vs Steal)**: Columns `Stat | SB | BB` — rows: Fold, Call, 3-Bet

The backend `HeroStats.steal` is a `PositionalStats` with `.co`, `.btn`, `.sb` populated. Same for `fold_to_3bet_steal`, `four_bet_steal`, `four_bet_fold_steal`.

## Files to Modify

### 1. `frontend/src/pages/StatsPage.tsx`

#### Steal Attempted table — add CO column

Find the Steal Attempted section. It renders a custom table with columns. Change the column headers from:

```
Stat | Tot | BTN | SB
```

to:

```
Stat | Tot | CO | BTN | SB
```

For each row, add a CO cell that reads from the `.co` field of the corresponding `PositionalStats`:

**Row 1: Steal**
```tsx
{ sv: stats.steal.co, statKey: 'steal', drillKey: 'steal', position: 'co' }
```

**Row 2: Fold to 3-Bet (steal context)**
```tsx
{ sv: stats.fold_to_3bet_steal.co, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'co' }
```

**Row 3: 4-Bet (steal context)**
```tsx
{ sv: stats.four_bet_steal.co, statKey: 'four_bet', drillKey: 'four_bet', position: 'co' }
```

**Row 4: 4-Bet-Fold (steal context)**

Note: the 4-Bet-Fold row in steal context will have very small sample sizes, especially for CO. Expect `--` or subscript sample counts most of the time. This is inherent to the stat (the intersection of steal + 4-bet + fold is rare), not a bug.

```tsx
{ sv: stats.four_bet_fold_steal.co, drillKey: 'four_bet_fold_steal', position: 'co' }
```

### 2. `backend/app/stats_engine.py`

The main steal stat already includes CO, but the three steal sub-stats are missing it. Change the position lists in these three `_pos_steal` calls (around line 323-325):

```python
# Before:
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["BTN", "SB"])
stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["BTN", "SB"])
stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["BTN", "SB"])

# After:
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["CO", "BTN", "SB"])
```

No new SQL or model changes needed — the SQL already computes steal sub-stats for all positions and `PositionalStats` already has a `.co` field.

## Coaching context: expected ranges for CO steal stats

Use these rough benchmarks to sanity-check the data after implementation. If the numbers fall wildly outside these ranges, something is likely wrong with the computation.

| Stat | CO expected | BTN expected | SB expected |
|------|-----------|------------|-----------|
| Steal | 25-35% | 45-55% | 30-45% |
| Fold to 3-Bet (steal) | 55-65% | 45-55% | 50-60% |
| 4-Bet (steal) | 5-12% | 5-12% | 5-12% |

CO Fold to 3-Bet in steal context is typically higher than BTN because CO faces 3-bets from 3 positions (BTN, SB, BB) and the BTN's 3-bet range against CO is often strong and credible, making folds correct more often.

The 4-Bet-Fold row will almost always show `--` or tiny sample subscripts for CO and SB. That is expected — the intersection of steal + 4-bet + fold to 5-bet is extremely rare.

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `cd frontend && npm run dev` — page loads
3. Steal Attempted section shows 4 columns: Tot | CO | BTN | SB
4. CO Steal shows a value in the 25-35% range (sanity check — if 60%+ or <15%, investigate)
5. CO Fold to 3-Bet shows a value (typically 55-65%) or `--` if sample < 10
6. CO 4-Bet and 4-Bet-Fold will likely show `--` with small sample subscripts — this is correct behavior
7. vs Steal section is unchanged (SB | BB columns) — note that vs Steal stats already include defense against CO opens since `faced_steal` is set for any steal attempt
8. Clicking CO steal cells navigates to drill-down correctly
