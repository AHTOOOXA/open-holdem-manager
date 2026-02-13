# Phase 2 Implementation — Add CO Column to Steal Section

## Goal

Add the CO (cutoff) column to all four steal sub-stats so the Steal Attempted table shows `Tot | CO | BTN | SB` instead of `Tot | BTN | SB`. CO steals (opening into 3 remaining players) are a core concept, but the sub-stats currently omit CO from their position lists. The main Steal row already has CO; the three sub-rows (Fold to 3-Bet, 4-Bet, 4-Bet-Fold) do not.

No new SQL, no new model fields, no new stat flags. The SQL already groups steal sub-stats by position and `PositionalStats` already has a `.co` field. This is a 3-line backend fix + frontend column addition.

## Files to Modify

### 1. `backend/app/stats_engine.py` (3 lines changed)

Add `"CO"` to the position lists for the three steal sub-stat calls around line 323-325.

**Before:**
```python
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["BTN", "SB"])
stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["BTN", "SB"])
stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["BTN", "SB"])
```

**After:**
```python
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["CO", "BTN", "SB"])
```

This makes all four steal rows consistent: `["CO", "BTN", "SB"]` everywhere.

### 2. `frontend/src/pages/StatsPage.tsx` (header + 4 cells added)

#### Header change

```tsx
// Before:
headers={['Tot', 'BTN', 'SB']}

// After:
headers={['Tot', 'CO', 'BTN', 'SB']}
```

#### Row 1 — Steal: add CO cell after Tot

```tsx
{ sv: stats.steal.co, statKey: 'steal', drillKey: 'steal', position: 'co' },
```

Insert between the `total` cell and the `btn` cell.

#### Row 2 — Fold to 3Bet: add CO cell after Tot

```tsx
{ sv: stats.fold_to_3bet_steal.co, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'co' },
```

#### Row 3 — 4-Bet: add CO cell after Tot

```tsx
{ sv: stats.four_bet_steal.co, statKey: 'four_bet', drillKey: 'four_bet', position: 'co' },
```

#### Row 4 — 4-Bet-Fold: add CO cell after Tot

```tsx
{ sv: stats.four_bet_fold_steal.co, drillKey: 'four_bet_fold_steal', position: 'co' },
```

Note: 4-Bet-Fold cells have no `statKey` (they are not clickable drill-down stats in the current implementation), only `drillKey`.

#### Full resulting PosTable (for reference)

```tsx
<PosTable
  headers={['Tot', 'CO', 'BTN', 'SB']}
  driftMap={driftMap}
  onStatClick={handleStatClick}
  rows={[
    {
      label: 'Steal',
      cells: [
        { sv: stats.steal.total, statKey: 'steal', drillKey: 'steal', position: 'total' },
        { sv: stats.steal.co, statKey: 'steal', drillKey: 'steal', position: 'co' },
        { sv: stats.steal.btn, statKey: 'steal', drillKey: 'steal', position: 'btn' },
        { sv: stats.steal.sb, statKey: 'steal', drillKey: 'steal', position: 'sb' },
      ],
    },
    {
      label: 'Fold to 3Bet',
      cells: [
        { sv: stats.fold_to_3bet_steal.total, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'total' },
        { sv: stats.fold_to_3bet_steal.co, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'co' },
        { sv: stats.fold_to_3bet_steal.btn, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'btn' },
        { sv: stats.fold_to_3bet_steal.sb, statKey: 'fold_to_3bet', drillKey: 'fold_to_3bet', position: 'sb' },
      ],
    },
    {
      label: '4-Bet',
      cells: [
        { sv: stats.four_bet_steal.total, statKey: 'four_bet', drillKey: 'four_bet', position: 'total' },
        { sv: stats.four_bet_steal.co, statKey: 'four_bet', drillKey: 'four_bet', position: 'co' },
        { sv: stats.four_bet_steal.btn, statKey: 'four_bet', drillKey: 'four_bet', position: 'btn' },
        { sv: stats.four_bet_steal.sb, statKey: 'four_bet', drillKey: 'four_bet', position: 'sb' },
      ],
    },
    {
      label: '4-Bet-Fold',
      cells: [
        { sv: stats.four_bet_fold_steal.total, drillKey: 'four_bet_fold_steal', position: 'total' },
        { sv: stats.four_bet_fold_steal.co, drillKey: 'four_bet_fold_steal', position: 'co' },
        { sv: stats.four_bet_fold_steal.btn, drillKey: 'four_bet_fold_steal', position: 'btn' },
        { sv: stats.four_bet_fold_steal.sb, drillKey: 'four_bet_fold_steal', position: 'sb' },
      ],
    },
  ]}
/>
```

## Expected CO Ranges (sanity check)

| Stat | CO expected | BTN expected | SB expected |
|------|-------------|--------------|-------------|
| Steal | 25-35% | 45-55% | 30-45% |
| Fold to 3-Bet (steal) | 55-65% | 45-55% | 50-60% |
| 4-Bet (steal) | 5-12% | 5-12% | 5-12% |
| 4-Bet-Fold | `--` (too rare) | `--` (too rare) | `--` (too rare) |

CO Fold to 3-Bet is typically higher than BTN because CO faces 3-bets from 3 positions (BTN, SB, BB), and BTN's 3-bet range against CO is strong and credible.

4-Bet-Fold will almost always show `--` or tiny sample subscripts across all positions. The intersection of steal + 4-bet + fold to 5-bet is extremely rare.

## Test Checklist

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all 11 tests pass (no changes to parser or stat flags)
2. `cd frontend && npm run lint` -- no lint errors
3. Start dev (`make dev`) and load the Stats page
4. Steal Attempted section shows 4 columns: `Tot | CO | BTN | SB`
5. CO Steal shows a percentage in the 25-35% range (if wildly outside, investigate)
6. CO Fold to 3-Bet shows a value (55-65%) or `--` if sample is too small
7. CO 4-Bet shows a value (5-12%) or `--` if sample is too small
8. CO 4-Bet-Fold shows `--` with a small sample subscript (expected -- this stat is very rare)
9. vs Steal section (right side) is unchanged: still shows `SB | BB` columns only
10. Clicking any CO cell navigates to the correct drill-down page
11. Backend API response at `GET /api/stats/hero` includes `.co` fields populated in `fold_to_3bet_steal`, `four_bet_steal`, and `four_bet_fold_steal`
