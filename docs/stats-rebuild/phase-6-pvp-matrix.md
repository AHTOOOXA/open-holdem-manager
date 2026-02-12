# Phase 6 — PvP Matrix Widget

## Goal

Add a Player vs Player positional matrix widget to stat detail pages. This shows Hero Position (rows) x Villain Position (columns) heatmap for interaction stats. For example, the 3-Bet PvP matrix shows how often hero 3-bets from each position against each opener position.

**Scope**: Backend (new endpoint + config) + Frontend (new widget component).

## Weak Dependency

Phase 3 (BB Defense as PositionalStats) is helpful because `bb_defense` PvP matrix shows defense rate by raiser position. But the widget works without Phase 3 — it just won't have `bb_defense` as a target stat until that phase ships.

## Design

### Visual

```
3-Bet % by Matchup
            Villain Open Position →
            EP     MP     CO     BTN    SB
Hero  MP    8.1    —      —      —      —
      CO    5.2    7.4    —      —      —
      BTN   3.8    6.1    10.2   —      —
      SB    3.1    4.9    8.7    12.4   —
      BB    4.0    5.8    9.1    14.2   17.8
```

- Color intensity = stat frequency (light to dark gradient)
- Each cell clickable → filters hand explorer to that hero pos + villain pos matchup
- Cells with <10 sample → muted text + subscript sample size
- Impossible matchups (hero EP can't 3-bet EP opener) → `—`

### Stats That Get PvP Matrix

| Stat | Rows (Hero) | Cols (Villain) | Villain Join |
|------|-------------|----------------|-------------|
| `three_bet` | Hero 3-bet pos | Opener pos | `v.open_raise = TRUE` |
| `three_bet_ip` | Hero pos (IP) | Opener pos | `v.open_raise = TRUE` |
| `fold_to_3bet` | Hero open pos | 3-bettor pos | `v.three_bet = TRUE` |
| `four_bet` | Hero pos | 3-bettor pos | `v.three_bet = TRUE` |
| `call_open_raise` | Hero call pos | Opener pos | `v.open_raise = TRUE` |
| `open_raise` | Hero open pos | 3-bettor pos | `v.three_bet = TRUE` |
| `bb_defense` | BB (1D) | Raiser pos | `v.open_raise = TRUE` |

## Files to Modify

### 1. `backend/app/stat_registry.py` — PVP_MATRIX_CONFIG

Add a new config dict after the existing configs:

```python
PVP_MATRIX_CONFIG = {
    "three_bet": {
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "hero_position",
        "villain_label": "opener_position",
    },
    "three_bet_ip": {
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "hero_position",
        "villain_label": "opener_position",
    },
    "fold_to_3bet": {
        "action_sql": "hp.fold_to_3bet = TRUE",
        "opp_sql": "hp.fold_to_3bet IS NOT NULL",
        "villain_join": "v.three_bet = TRUE",
        "hero_label": "hero_position",
        "villain_label": "3bettor_position",
    },
    "four_bet": {
        "action_sql": "hp.four_bet = TRUE",
        "opp_sql": "hp.four_bet_opp = TRUE",
        "villain_join": "v.three_bet = TRUE",
        "hero_label": "hero_position",
        "villain_label": "3bettor_position",
    },
    "call_open_raise": {
        "action_sql": "hp.call_open_raise = TRUE",
        "opp_sql": "1=1",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "hero_position",
        "villain_label": "opener_position",
    },
    "open_raise": {
        "action_sql": "hp.fold_to_3bet IS NOT NULL",
        "opp_sql": "hp.open_raise = TRUE",
        "villain_join": "v.three_bet = TRUE",
        "hero_label": "hero_position",
        "villain_label": "3bettor_position",
    },
    "bb_defense": {
        "action_sql": "hp.bb_defense = TRUE",
        "opp_sql": "hp.bb_defense_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "hero_label": "hero_position",
        "villain_label": "raiser_position",
    },
}
```

### 2. `backend/app/models.py` — Response model

Add new response model:

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
    cells: list[PvpMatrixCell]
```

### 3. `backend/app/api/stats.py` — New endpoint

Add endpoint:

```python
@router.get("/detail/{stat_key}/pvp-matrix", response_model=PvpMatrixResponse)
async def get_pvp_matrix(
    stat_key: str,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    config = PVP_MATRIX_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(404, f"PvP matrix not available for '{stat_key}'")

    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return PvpMatrixResponse(hero_label=config["hero_label"], villain_label=config["villain_label"], cells=[])

    where, params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

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
        pct = round(actions / opportunities * 100, 1) if opportunities > 0 else None
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
        cells=cells,
    )
```

### 4. `frontend/src/lib/api.ts` — Types + fetch function

Add types:

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
  cells: PvpMatrixCell[];
}
```

Add fetch function:

```typescript
export async function getPvpMatrix(
  statKey: string,
  params?: StatFilterParams,
  signal?: AbortSignal,
): Promise<PvpMatrixResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`/api/stats/detail/${statKey}/pvp-matrix?${sp}`, { signal });
  if (!res.ok) throw new Error(`PvP matrix error: ${res.status}`);
  return res.json();
}
```

### 5. `frontend/src/lib/stat-registry.ts` — Add widget type

Add `'pvp_matrix'` to the `WidgetType` union:

```typescript
export type WidgetType =
  | 'positional_bar'
  | 'response_distribution'
  | 'range_heatmap'
  | 'pvp_matrix'       // ← NEW
  | 'trend_sparkline'
  // ... rest
```

Add `pvp_matrix` to widget lists for relevant stats:

```typescript
three_bet:       { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'pvp_matrix', 'ip_oop_split', 'postflop_bridge', 'trend_sparkline'] },
fold_to_3bet:    { ..., widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'] },
four_bet:        { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'opportunity_context', 'pvp_matrix', 'money_burned', 'trend_sparkline'] },
call_open_raise: { ..., widgets: ['range_heatmap', 'ev_breakdown', 'pvp_matrix', 'postflop_bridge', 'trend_sparkline'] },
open_raise:      { ..., widgets: ['range_heatmap', 'villain_response', 'ev_breakdown', 'sizing_histogram', 'pvp_matrix', 'trend_sparkline'] },
bb_defense:      { ..., widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'] },
three_bet_ip:    { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'] },
```

### 6. `frontend/src/components/stats/PvpMatrixWidget.tsx` — New component

Create a new widget component. Key rendering logic:

```tsx
interface PvpMatrixWidgetProps {
  statKey: string;
  filters: StatFilterParams;
}

export default function PvpMatrixWidget({ statKey, filters }: PvpMatrixWidgetProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['pvp-matrix', statKey, filters],
    queryFn: ({ signal }) => getPvpMatrix(statKey, filters, signal),
  });

  if (isLoading) return <Skeleton />;
  if (!data || data.cells.length === 0) return null;

  // Build matrix: rows = hero positions, cols = villain positions
  const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
  const cellMap = new Map<string, PvpMatrixCell>();
  for (const cell of data.cells) {
    cellMap.set(`${cell.hero_pos}-${cell.villain_pos}`, cell);
  }

  // Determine which positions have data
  const heroPosSet = new Set(data.cells.map(c => c.hero_pos));
  const villainPosSet = new Set(data.cells.map(c => c.villain_pos));
  const heroPositions = POSITIONS.filter(p => heroPosSet.has(p));
  const villainPositions = POSITIONS.filter(p => villainPosSet.has(p));

  // Render grid with color intensity based on pct value
  // Min/max for color scaling
  const pcts = data.cells.map(c => c.pct).filter((p): p is number => p !== null);
  const minPct = Math.min(...pcts);
  const maxPct = Math.max(...pcts);

  return (
    <div>
      <h4>{data.hero_label} vs {data.villain_label}</h4>
      <table>
        <thead>
          <tr>
            <th></th>
            {villainPositions.map(vp => <th key={vp}>{vp}</th>)}
          </tr>
        </thead>
        <tbody>
          {heroPositions.map(hp => (
            <tr key={hp}>
              <td>{hp}</td>
              {villainPositions.map(vp => {
                const cell = cellMap.get(`${hp}-${vp}`);
                if (!cell || cell.opportunities === 0) {
                  return <td key={vp}>—</td>;
                }
                const intensity = (cell.pct! - minPct) / (maxPct - minPct);
                const bgOpacity = 0.1 + intensity * 0.5;
                return (
                  <td
                    key={vp}
                    style={{ backgroundColor: `rgba(99, 102, 241, ${bgOpacity})` }}
                    className={cell.opportunities < 10 ? 'text-text-muted' : ''}
                  >
                    {cell.pct?.toFixed(1)}
                    {cell.opportunities < 10 && (
                      <sub className="text-xs">{cell.opportunities}</sub>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

### 7. `frontend/src/components/stats/StatDetailPanel.tsx` — Wire up widget

In the widget rendering switch/map in `StatDetailPanel`, add a case for `pvp_matrix`:

```tsx
case 'pvp_matrix':
  return <PvpMatrixWidget statKey={statKey} filters={filters} />;
```

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `GET /api/stats/detail/three_bet/pvp-matrix` returns cells with hero_pos, villain_pos, pct
3. Navigate to `/stats/three_bet` → PvP Matrix widget renders with colored grid
4. Cells with <10 sample show muted text with subscript count
5. Impossible matchups show `—`
6. Click a cell → (future: filters hand explorer to that matchup)
7. Try multiple stats: `fold_to_3bet`, `four_bet`, `call_open_raise` → all render
8. Apply filters (stakes, date) → matrix updates
9. `cd frontend && npm run lint` — no lint errors
