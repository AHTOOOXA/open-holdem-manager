# Phase 2 — Add CO Column to Steal Section

## Goal

Add the CO (cutoff) column to the Steal Attempted section. CO steals are a core strategy concept (the widest open from a non-button position). The backend already computes steal stats for CO via `_pos_steal("steal", "steal_opp", ["CO", "BTN", "SB"])` — the frontend just doesn't render the CO column.

**Scope**: Frontend only. No backend changes.

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
{ sv: stats.steal.co, statKey: 'steal', position: 'co' }
```

**Row 2: Fold to 3-Bet (steal context)**
```tsx
{ sv: stats.fold_to_3bet_steal.co, statKey: 'fold_to_3bet_steal', position: 'co' }
```

**Row 3: 4-Bet (steal context)**
```tsx
{ sv: stats.four_bet_steal.co, statKey: 'four_bet_steal', position: 'co' }
```

**Row 4: 4-Bet-Fold (steal context)**
```tsx
{ sv: stats.four_bet_fold_steal.co, statKey: 'four_bet_fold_steal', position: 'co' }
```

Note: The backend currently computes steal for CO/BTN/SB but the steal sub-stats (fold_to_3bet_steal, four_bet_steal, four_bet_fold_steal) only compute for BTN/SB. Check `stats_engine.py` line ~332:

```python
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["BTN", "SB"])
```

**Backend fix needed**: Change these three `_pos_steal` calls to include `"CO"`:

```python
stats.fold_to_3bet_steal = _pos_steal("steal_fold_to_3bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_steal = _pos_steal("steal_four_bet", "steal_faced_3bet", ["CO", "BTN", "SB"])
stats.four_bet_fold_steal = _pos_steal("steal_4bet_fold", "steal_4bet_fold_opp", ["CO", "BTN", "SB"])
```

This is a one-line change per stat in `stats_engine.py` — no new SQL or model changes needed since `PositionalStats` already has a `.co` field.

### 2. `backend/app/stats_engine.py`

Change the position lists in three `_pos_steal` calls (around line 332-334):

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

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `cd frontend && npm run dev` — page loads
3. Steal Attempted section shows 4 columns: Tot | CO | BTN | SB
4. CO column has data for Steal row (should show a value — CO steal is common)
5. CO column for sub-stats (Fold to 3-Bet, 4-Bet, 4-Bet-Fold) shows values (or `--` if sample too small)
6. vs Steal section is unchanged (SB | BB columns)
7. Clicking CO steal cells navigates to drill-down correctly
