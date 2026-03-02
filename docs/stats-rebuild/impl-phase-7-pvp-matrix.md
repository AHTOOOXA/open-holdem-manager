# Phase 7 Implementation — PvP Positional Matrix Widget

## Goal

Add a Player vs Player positional matrix widget to stat detail pages. The widget renders a Hero Position (rows) x Villain Position (columns) heatmap showing interaction frequencies for matchup-dependent stats.

**Why this matters**: Aggregate stats hide positional dynamics. A 7% overall 3-bet looks fine, but if it is 2% from SB vs BTN opens and 15% from BTN vs EP opens, the player has a massive blind-defense leak. The PvP matrix exposes these matchup-specific tendencies at a glance -- the kind of insight a coach looks for in the first 30 seconds of a database review.

**Scope**: New backend endpoint + config dict in `stat_registry.py`, new response model, new frontend widget component, wired into the existing widget dispatcher. Medium effort.

**Weak dependency**: Phase 3 (BB Defense as PositionalStats) is helpful because `bb_defense` PvP matrix shows defense rate by raiser position. The widget works without Phase 3 -- it just will not have `bb_defense` as a target stat until that phase ships.

---

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/stat_registry.py` | Add `PVP_MATRIX_CONFIG` dict |
| `backend/app/models.py` | Add `PvpMatrixCell` + `PvpMatrixResponse` models |
| `backend/app/api/stats.py` | Add `GET /api/stats/detail/{stat_key}/pvp-matrix` endpoint |
| `frontend/src/lib/api.ts` | Add `PvpMatrixCell`, `PvpMatrixResponse` types + `getPvpMatrix()` function |
| `frontend/src/lib/query-keys.ts` | Add `pvpMatrix` key factory |
| `frontend/src/lib/stat-registry.ts` | Add `'pvp_matrix'` to `WidgetType` union + widget lists for 8 stats |
| `frontend/src/components/stats/widgets/PvpMatrixWidget.tsx` | New component (heatmap grid) |
| `frontend/src/components/stats/widgets/AnalysisWidgets.tsx` | Add `pvp_matrix` case to `renderWidget` switch |

---

## 1. Backend: `backend/app/stat_registry.py` -- PVP_MATRIX_CONFIG

Add after `POSTFLOP_BRIDGE_CONFIG`:

```python
# -- PvP Matrix Config ---------------------------------------------------
# Maps stat_key -> villain-join query config for Hero Position x Villain Position matrix.
# Each entry defines:
#   - action_sql: SQL expression for "hero did action" (numerator)
#   - opp_sql: SQL expression for "hero had opportunity" (denominator / row filter)
#   - villain_join: SQL filter applied to the villain hand_players row (v alias)
#   - hero_label / villain_label: axis labels for the frontend
#   - single_row: if True, hero is always one position (e.g. BB) -- render as 1-row strip

PVP_MATRIX_CONFIG: dict[str, dict] = {
    "three_bet": {
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "Hero Position",
        "villain_label": "Opener Position",
    },
    "fold_to_3bet": {
        "action_sql": "hp.fold_to_3bet = TRUE",
        "opp_sql": "hp.fold_to_3bet IS NOT NULL",
        "villain_join": "v.three_bet = TRUE",
        "hero_label": "Hero Open Position",
        "villain_label": "3-Bettor Position",
    },
    "four_bet": {
        "action_sql": "hp.four_bet = TRUE",
        "opp_sql": "hp.four_bet_opp = TRUE",
        "villain_join": "v.three_bet = TRUE",
        "hero_label": "Hero Position",
        "villain_label": "3-Bettor Position",
    },
    "call_open_raise": {
        "action_sql": "hp.call_open_raise = TRUE",
        "opp_sql": "hp.call_open_raise_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "Hero Position",
        "villain_label": "Opener Position",
    },
    "steal": {
        "action_sql": "hp.steal_attempted = TRUE",
        "opp_sql": "hp.steal_opp = TRUE",
        "villain_join": "v.faced_steal = TRUE",
        "hero_label": "Hero Steal Position",
        "villain_label": "Defender Position",
    },
    "fold_to_steal": {
        "action_sql": "hp.fold_to_steal = TRUE",
        "opp_sql": "hp.faced_steal = TRUE",
        "villain_join": "v.steal_attempted = TRUE",
        "hero_label": "Hero Defend Position",
        "villain_label": "Stealer Position",
    },
    "cbet_flop": {
        "action_sql": "hp.cbet_flop = TRUE",
        "opp_sql": "hp.cbet_flop_opp = TRUE",
        "villain_join": "v.saw_flop = TRUE",
        "hero_label": "Hero Position",
        "villain_label": "Villain Position",
    },
    "bb_defense": {
        "action_sql": "hp.bb_defense = TRUE",
        "opp_sql": "hp.bb_defense_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "Hero (BB)",
        "villain_label": "Raiser Position",
        "single_row": True,
    },
}
```

### Design notes on villain_join logic

Each stat defines a specific villain condition that identifies the opponent whose position matters:

- **three_bet**: Villain is the open-raiser. `v.open_raise = TRUE` finds the player who opened, so the matrix shows 3-bet frequency from each hero position against each opener position.
- **fold_to_3bet**: Villain is the 3-bettor. `v.three_bet = TRUE` finds who 3-bet hero's open.
- **four_bet**: Villain is the 3-bettor. `v.three_bet = TRUE` -- hero 4-bets in response.
- **call_open_raise**: Villain is the opener. `v.open_raise = TRUE`.
- **steal / fold_to_steal**: These are inverse pairs. Steal looks at hero's attempt vs defender; fold_to_steal looks at hero's defense vs stealer.
- **cbet_flop**: Villain saw the flop. `v.saw_flop = TRUE` -- any opponent at the flop, giving hero's c-bet frequency by opponent position.
- **bb_defense**: Hero is always BB, villain is the open-raiser. Collapses to a single-row strip (1 x N matrix).

---

## 2. Backend: `backend/app/models.py` -- Response Models

Add after the `PostflopBridgeResponse` class:

```python
class PvpMatrixCell(BaseModel):
    hero_pos: str
    villain_pos: str
    actions: int
    opportunities: int
    pct: float | None = None

class PvpMatrixResponse(BaseModel):
    hero_label: str
    villain_label: str
    single_row: bool = False
    cells: list[PvpMatrixCell]
```

---

## 3. Backend: `backend/app/api/stats.py` -- New Endpoint

### Import additions

Add to the import block:

```python
from app.models import PvpMatrixCell, PvpMatrixResponse
from app.stat_registry import PVP_MATRIX_CONFIG
```

### Endpoint

Add after the existing `get_stat_range` endpoint:

```python
@router.get("/stats/detail/{stat_key}/pvp-matrix", response_model=PvpMatrixResponse)
def get_pvp_matrix(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = PVP_MATRIX_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"PvP matrix not available for '{stat_key}'")

    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return PvpMatrixResponse(
            hero_label=config["hero_label"],
            villain_label=config["villain_label"],
            single_row=config.get("single_row", False),
            cells=[],
        )

    where, params = _build_filter_where(
        player_id, position, stakes, game_mode, date_from, date_to,
    )

    sql = f"""
    SELECT
        hp.position AS hero_pos,
        v.position AS villain_pos,
        SUM(CASE WHEN {config['action_sql']} THEN 1 ELSE 0 END) AS actions,
        COUNT(*) AS opportunities
    FROM hand_players hp
    JOIN hands h ON hp.hand_id = h.id
    JOIN hand_players v ON v.hand_id = hp.hand_id
        AND v.player_id != hp.player_id
        AND {config['villain_join']}
    WHERE {where} AND ({config['opp_sql']})
    GROUP BY hp.position, v.position
    """

    rows = db.execute(sql, params).fetchall()
    cells = []
    for hero_pos, villain_pos, actions, opportunities in rows:
        pct = round(float(actions) / float(opportunities) * 100, 1) if opportunities > 0 else None
        cells.append(PvpMatrixCell(
            hero_pos=hero_pos,
            villain_pos=villain_pos,
            actions=int(actions),
            opportunities=int(opportunities),
            pct=pct,
        ))

    return PvpMatrixResponse(
        hero_label=config["hero_label"],
        villain_label=config["villain_label"],
        single_row=config.get("single_row", False),
        cells=cells,
    )
```

### SQL walkthrough

The query joins `hand_players hp` (hero) with `hand_players v` (villain) on the same hand. The critical constraints are:

1. `v.player_id != hp.player_id` -- villain is not hero
2. `{config['villain_join']}` -- villain must satisfy the stat-specific condition (e.g., `v.open_raise = TRUE` for the 3-bet matrix)
3. `{where}` -- standard hero filters (player_id, position, stakes, dates)
4. `{config['opp_sql']}` -- hero must have had the opportunity (e.g., `hp.three_bet_opp = TRUE`)

The `GROUP BY hp.position, v.position` produces one row per (hero_pos, villain_pos) pair. `COUNT(*)` is the opportunity count (denominator) and `SUM(CASE WHEN action THEN 1 ELSE 0 END)` is the action count (numerator).

**Important**: The `position` filter from `_build_filter_where` applies to `hp.position` (hero), not `v.position`. This is correct -- when a user filters to "CO", they see CO as the only hero row, but all villain positions remain as columns.

**DuckDB Decimal note**: The `float()` cast on `actions / opportunities` is necessary because DuckDB may return `Decimal` types, which Pydantic cannot serialize directly.

---

## 4. Frontend: `frontend/src/lib/api.ts` -- Types + Fetch Function

### Types

Add after the existing response type definitions (near the other stat detail types):

```typescript
export interface PvpMatrixCell {
  hero_pos: string;
  villain_pos: string;
  actions: number;
  opportunities: number;
  pct: number | null;
}

export interface PvpMatrixResponse {
  hero_label: string;
  villain_label: string;
  single_row: boolean;
  cells: PvpMatrixCell[];
}
```

### Fetch function

Add after the existing stat detail fetch functions:

```typescript
export async function getPvpMatrix(
  statKey: string,
  params?: StatFilterParams,
  signal?: AbortSignal,
): Promise<PvpMatrixResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(
    `${BASE}/stats/detail/${encodeURIComponent(statKey)}/pvp-matrix?${sp}`,
    { signal },
  );
  if (!res.ok) throw new Error(`PvP matrix failed: ${res.statusText}`);
  return res.json();
}
```

---

## 5. Frontend: `frontend/src/lib/query-keys.ts` -- Add Key Factory

Add inside the `stats` object:

```typescript
pvpMatrix: (statKey: string, filters: Record<string, unknown>) =>
  ['stats', 'pvp-matrix', statKey, filters] as const,
```

Full context (add after the `statRange` line):

```typescript
stats: {
  hero: (filters: Record<string, unknown>) => ['stats', 'hero', filters] as const,
  detail: (statKey: string, filters: Record<string, unknown>) => ['stats', 'detail', statKey, filters] as const,
  trend: (statKey: string, filters: Record<string, unknown>) => ['stats', 'trend', statKey, filters] as const,
  analysis: (statKey: string, filters: Record<string, unknown>) => ['stats', 'analysis', statKey, filters] as const,
  evBreakdown: (statKey: string, filters: Record<string, unknown>) => ['stats', 'ev-breakdown', statKey, filters] as const,
  sizing: (statKey: string, filters: Record<string, unknown>) => ['stats', 'sizing', statKey, filters] as const,
  foldEquity: (statKey: string, filters: Record<string, unknown>) => ['stats', 'fold-equity', statKey, filters] as const,
  byContext: (statKey: string, filters: Record<string, unknown>) => ['stats', 'by-context', statKey, filters] as const,
  composition: (statKey: string, filters: Record<string, unknown>) => ['stats', 'composition', statKey, filters] as const,
  money: (statKey: string, filters: Record<string, unknown>) => ['stats', 'money', statKey, filters] as const,
  postflopBridge: (statKey: string, filters: Record<string, unknown>) => ['stats', 'postflop-bridge', statKey, filters] as const,
  continuingRange: (statKey: string, filters: Record<string, unknown>) => ['stats', 'continuing-range', statKey, filters] as const,
  statRange: (statKey: string, filters: Record<string, unknown>) => ['stats', 'stat-range', statKey, filters] as const,
  pvpMatrix: (statKey: string, filters: Record<string, unknown>) => ['stats', 'pvp-matrix', statKey, filters] as const,  // <-- NEW
},
```

---

## 6. Frontend: `frontend/src/lib/stat-registry.ts` -- Widget Type + Widget Lists

### A. Add to WidgetType union

```typescript
export type WidgetType =
  | 'positional_bar'
  | 'response_distribution'
  | 'range_heatmap'
  | 'trend_sparkline'
  | 'villain_response'
  | 'ev_breakdown'
  | 'sizing_histogram'
  | 'fold_equity'
  | 'by_context'
  | 'composition'
  | 'money_burned'
  | 'continuing_range'
  | 'gap_indicator'
  | 'postflop_bridge'
  | 'contextual_rate'
  | 'opportunity_context'
  | 'range_comparison'
  | 'pvp_matrix';              // <-- NEW
```

### B. Add `'pvp_matrix'` to widget arrays for 8 stats

Append `'pvp_matrix'` to the `widgets` array for each stat. Insert it before `'trend_sparkline'` (which should always be last, as it takes the most vertical space).

| Stat key | Current widgets (last two shown) | After |
|----------|----------------------------------|-------|
| `three_bet` | `..., 'postflop_bridge', 'trend_sparkline'` | `..., 'postflop_bridge', 'pvp_matrix', 'trend_sparkline'` |
| `fold_to_3bet` | `..., 'by_context', 'trend_sparkline'` | `..., 'by_context', 'pvp_matrix', 'trend_sparkline'` |
| `four_bet` | `..., 'opportunity_context', 'trend_sparkline'` | `..., 'opportunity_context', 'pvp_matrix', 'trend_sparkline'` |
| `call_open_raise` | `..., 'by_context', 'trend_sparkline'` | `..., 'by_context', 'pvp_matrix', 'trend_sparkline'` |
| `steal` | `'trend_sparkline'` | `'pvp_matrix', 'trend_sparkline'` |
| `fold_to_steal` | `'response_distribution', 'trend_sparkline'` | `'response_distribution', 'pvp_matrix', 'trend_sparkline'` |
| `cbet_flop` | `'positional_bar', 'trend_sparkline'` | `'positional_bar', 'pvp_matrix', 'trend_sparkline'` |
| `bb_defense` | `..., 'by_context', 'trend_sparkline'` | `..., 'by_context', 'pvp_matrix', 'trend_sparkline'` |

Example for `three_bet`:

```typescript
// Before:
three_bet: { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'postflop_bridge', 'trend_sparkline'] },

// After:
three_bet: { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'postflop_bridge', 'pvp_matrix', 'trend_sparkline'] },
```

---

## 7. Frontend: `frontend/src/components/stats/widgets/PvpMatrixWidget.tsx` -- New Component

Create new file:

```tsx
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getPvpMatrix } from '@/lib/api';
import type { PvpMatrixCell } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];

/** Low-sample threshold: cells below this get muted styling + subscript count */
const LOW_SAMPLE = 30;

interface PvpMatrixWidgetProps {
  statKey: string;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
  position?: string;
}

export default function PvpMatrixWidget({
  statKey,
  filterParams,
  position,
}: PvpMatrixWidgetProps) {
  const params = useMemo(
    () => ({ position, ...filterParams }),
    [position, filterParams],
  );

  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.pvpMatrix(statKey, params),
    queryFn: ({ signal }) => getPvpMatrix(statKey, params, signal),
  });

  // Build cell lookup map and determine which positions have data
  const { cellMap, heroPositions, villainPositions, minPct, maxPct } =
    useMemo(() => {
      if (!data || data.cells.length === 0)
        return {
          cellMap: new Map<string, PvpMatrixCell>(),
          heroPositions: [],
          villainPositions: [],
          minPct: 0,
          maxPct: 0,
        };

      const map = new Map<string, PvpMatrixCell>();
      const heroPosSet = new Set<string>();
      const villainPosSet = new Set<string>();
      const pcts: number[] = [];

      for (const cell of data.cells) {
        map.set(`${cell.hero_pos}-${cell.villain_pos}`, cell);
        heroPosSet.add(cell.hero_pos);
        villainPosSet.add(cell.villain_pos);
        if (cell.pct !== null) pcts.push(cell.pct);
      }

      return {
        cellMap: map,
        heroPositions: POSITIONS.filter((p) => heroPosSet.has(p)),
        villainPositions: POSITIONS.filter((p) => villainPosSet.has(p)),
        minPct: pcts.length > 0 ? Math.min(...pcts) : 0,
        maxPct: pcts.length > 0 ? Math.max(...pcts) : 0,
      };
    }, [data]);

  if (isPending) {
    return (
      <div className="space-y-2">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    );
  }

  if (!data || data.cells.length === 0) return null;

  const range = maxPct - minPct;

  /** Map pct value to a background opacity (0.08 = lightest, 0.55 = darkest) */
  function cellBg(pct: number): string {
    const intensity = range > 0 ? (pct - minPct) / range : 0.5;
    const opacity = 0.08 + intensity * 0.47;
    // primary color rgb(99, 102, 241) = indigo-500
    return `rgba(99, 102, 241, ${opacity.toFixed(2)})`;
  }

  return (
    <div>
      <h4 className="text-xs font-medium text-text-muted mb-2">
        {data.hero_label} vs {data.villain_label}
      </h4>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr>
              <th className="p-1.5 text-left text-text-muted font-normal w-12" />
              {villainPositions.map((vp) => (
                <th
                  key={vp}
                  className="p-1.5 text-center text-text-muted font-normal"
                >
                  {vp}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {heroPositions.map((hp) => (
              <tr key={hp}>
                <td className="p-1.5 text-text-muted font-medium">{hp}</td>
                {villainPositions.map((vp) => {
                  const cell = cellMap.get(`${hp}-${vp}`);

                  // No data or zero opportunities = impossible matchup
                  if (!cell || cell.opportunities === 0) {
                    return (
                      <td
                        key={vp}
                        className="p-1.5 text-center text-text-muted/40"
                      >
                        —
                      </td>
                    );
                  }

                  const isLowSample = cell.opportunities < LOW_SAMPLE;

                  return (
                    <td
                      key={vp}
                      className={`p-1.5 text-center rounded-sm ${
                        isLowSample ? 'text-text-muted' : 'text-text'
                      }`}
                      style={{
                        backgroundColor:
                          cell.pct !== null ? cellBg(cell.pct) : undefined,
                      }}
                      title={`${hp} vs ${vp}: ${cell.pct?.toFixed(1) ?? '—'}% (${cell.actions}/${cell.opportunities})`}
                    >
                      <span>{cell.pct !== null ? cell.pct.toFixed(1) : '—'}</span>
                      {isLowSample && (
                        <sub className="ml-0.5 text-[9px] text-text-muted/60">
                          {cell.opportunities}
                        </sub>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

### Component behavior

- **Data-driven rows/columns**: Only positions with actual data appear. For `steal`, this means rows = `[CO, BTN, SB]`, columns = `[SB, BB]` (3 x 2 matrix). For `bb_defense`, rows = `[BB]` only (1 x N strip).
- **Color intensity**: Maps the percentage value to an opacity range on the primary indigo color. Lowest value gets `opacity: 0.08`, highest gets `opacity: 0.55`. This creates a clear visual gradient without becoming unreadable.
- **Low sample warning**: Cells with fewer than 30 opportunities render with muted text color and a subscript showing the sample size. 30 is the threshold because at smaller samples, a single hand swings the percentage by 3+ points -- enough to mislead.
- **Impossible matchups**: Cells with zero opportunities (e.g., hero EP 3-betting an EP opener -- impossible) render as a dash.
- **Tooltip**: Each cell has a title tooltip showing the full matchup info: `"CO vs EP: 8.1% (12/148)"`.
- **Responsive**: The table wrapper has `overflow-x-auto` for small screens.
- **Loading state**: Uses Skeleton placeholders consistent with other widgets.
- **Empty state**: Returns `null` when no data (widget just does not appear).

---

## 8. Frontend: `frontend/src/components/stats/widgets/AnalysisWidgets.tsx` -- Dispatcher

### Import

Add at the top with the other widget imports:

```typescript
import PvpMatrixWidget from './PvpMatrixWidget';
```

### Switch case

Add inside `renderWidget()`, before the `default` case:

```typescript
case 'pvp_matrix':
  return (
    <PvpMatrixWidget
      statKey={statKey}
      filterParams={filterParams}
      position={position}
    />
  );
```

---

## Visual Spec

### 3-Bet PvP Matrix (5 x 5)

Hero can 3-bet from any position behind the opener. EP cannot 3-bet an EP open (same player). The opener must be in an earlier position for hero to have a 3-bet opportunity.

```
3-Bet % by Matchup
Hero Position vs Opener Position

              EP     MP     CO     BTN    SB
  MP          8.1    —      —      —      —
  CO          5.2    7.4    —      —      —
  BTN         3.8    6.1   10.2    —      —
  SB          3.1    4.9    8.7   12.4    —
  BB          4.0    5.8    9.1   14.2   17.8
```

Visual attributes:
- Cells colored with indigo gradient (lighter = lower %, darker = higher %)
- `14.2` and `17.8` (BB vs BTN/SB) are darkest -- BB defends aggressively vs late position opens
- `3.1` (SB vs EP) is lightest -- SB rarely 3-bets an EP open
- Dashes for impossible matchups (hero cannot 3-bet their own position or positions behind them)

### Steal PvP Matrix (3 x 2)

```
Hero Steal Position vs Defender Position

              SB     BB
  CO         32.1   32.1
  BTN        48.3   48.3
  SB          —     42.7
```

Note: CO and BTN steal frequencies are the same for SB and BB columns because steal opportunity is defined against both blinds simultaneously. SB vs SB is impossible.

### BB Defense Matrix (1 x N strip)

```
Hero (BB) vs Raiser Position

              EP     MP     CO     BTN    SB
  BB         38.2   42.1   51.3   62.8   72.4
```

Single-row strip. BB defends least vs EP opens (strongest range) and most vs SB opens (weakest range).

---

## Test Checklist

### Backend

1. `cd backend && python -m pytest tests/test_parser.py -v` -- all tests pass (no parser/stat_flags changes)
2. Start backend: `cd backend && uvicorn app.main:app --reload --port 4243`
3. `GET /api/stats/detail/three_bet/pvp-matrix` returns `PvpMatrixResponse` with cells containing `hero_pos`, `villain_pos`, `actions`, `opportunities`, `pct`
4. `GET /api/stats/detail/three_bet/pvp-matrix?position=BB` returns cells where `hero_pos` is always `BB`
5. `GET /api/stats/detail/three_bet/pvp-matrix?stakes=$0.05/$0.10` returns filtered results
6. `GET /api/stats/detail/bb_defense/pvp-matrix` returns `single_row: true` and all cells have `hero_pos = "BB"`
7. `GET /api/stats/detail/steal/pvp-matrix` returns cells with hero positions in `[CO, BTN, SB]` and villain positions in `[SB, BB]`
8. `GET /api/stats/detail/vpip/pvp-matrix` returns 404 (VPIP is not a PvP stat)
9. No hero configured: returns `{"hero_label": "...", "villain_label": "...", "cells": []}`
10. Check that `pct` values are `null` for zero-opportunity cells (should not happen in practice since GROUP BY filters them, but verify edge case)

### Frontend

11. `cd frontend && npm run lint` -- no lint errors
12. `cd frontend && npm run dev` -- page loads without console errors
13. Navigate to `/stats/three_bet` -- PvP Matrix widget renders in the widget panel
14. Matrix shows ~5 hero rows x ~5 villain columns with colored cells
15. Cells with <30 opportunities show muted text + subscript sample count
16. Impossible matchups show `—`
17. Hover any cell -- tooltip shows `"CO vs EP: 5.2% (8/154)"`
18. Navigate to `/stats/steal` -- matrix renders as 3 x 2 grid (CO/BTN/SB x SB/BB)
19. Navigate to `/stats/bb_defense` -- matrix renders as single-row strip (BB x EP/MP/CO/BTN/SB)
20. Navigate to `/stats/cbet_flop` -- PvP Matrix widget appears
21. Apply stakes filter -- matrix values update
22. Apply date range filter -- matrix values update
23. Loading state: before data arrives, Skeleton placeholders render
24. Empty state (no hands imported): widget does not appear (returns null)

### Cross-stat verification

25. Verify all 8 stats render the PvP Matrix widget: `three_bet`, `fold_to_3bet`, `four_bet`, `call_open_raise`, `steal`, `fold_to_steal`, `cbet_flop`, `bb_defense`
26. Stats without PvP Matrix config (e.g., `vpip`, `pfr`, `limp`) do NOT show the widget
27. Other widgets on the same stat detail page still render correctly alongside PvP Matrix

### Sanity check on values

28. 3-Bet matrix: BB vs BTN should be highest (12-18% typical at microstakes). SB vs EP should be lowest (2-5%).
29. BB Defense matrix: BB vs SB should be highest (65-80%). BB vs EP should be lowest (30-45%).
30. Steal matrix: BTN steal should show 40-55%. CO steal should show 25-35%.
