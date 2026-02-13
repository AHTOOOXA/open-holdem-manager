# Phase 6 — PvP Matrix Widget

## Goal

Add a Player vs Player positional matrix widget to stat detail pages. This shows Hero Position (rows) x Villain Position (columns) heatmap for interaction stats. For example, the 3-Bet PvP matrix shows how often hero 3-bets from each position against each villain open-raise position.

**Scope**: Backend (new endpoint + config) + Frontend (new widget component).

**Why this matters**: Aggregate stats hide positional dynamics. A 7% overall 3-bet looks fine, but if it is 2% from SB vs BTN opens and 15% from BTN vs EP opens, the player has a massive blind-defense leak. The PvP matrix exposes these matchup-specific tendencies at a glance.

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
- Cells with <30 sample → muted text + subscript sample size (frequency stats need 30+ hands to be directionally useful; at 10 samples one hand = 10pp of noise)
- Impossible matchups (hero EP can't 3-bet EP opener) → `—`

### Stats That Get PvP Matrix

| Stat | Rows (Hero) | Cols (Villain) | Villain Join | Notes |
|------|-------------|----------------|-------------|-------|
| `three_bet` | Hero 3-bet pos | Opener pos | `v.open_raise = TRUE` | Core matchup stat. Exposes IP/OOP 3-bet tendencies by position pair (no need for a separate "3-bet IP" matrix — that info is already encoded in the row/col positions). |
| `fold_to_3bet` | Hero open pos | 3-bettor pos | `v.three_bet = TRUE` | Exposes which matchups hero overfolds or underfolds after opening. |
| `four_bet` | Hero pos | 3-bettor pos | `v.three_bet = TRUE` | |
| `call_open_raise` | Hero call pos | Opener pos | `v.open_raise = TRUE` | Cold-calling frequency by matchup. |
| `steal` | Hero steal pos (CO/BTN/SB) | Defender pos (SB/BB) | `v.faced_steal = TRUE` | Small matrix (3x2). Shows if hero steals too wide vs specific blinds. |
| `fold_to_steal` | Hero defend pos (SB/BB) | Stealer pos (CO/BTN/SB) | `v.steal_attempted = TRUE` | Inverse of above. Shows blind defense leaks vs each steal position. |
| `cbet_flop` | Hero cbet pos | Villain pos | `v.saw_flop = TRUE AND v.player_id != hp.player_id` | Postflop PvP: how cbet frequency changes by opponent position. |
| `bb_defense` | BB only | Raiser pos | `v.open_raise = TRUE` | Collapses to a single-row strip (hero is always BB). Render as a 1-row bar, not a full matrix. |

**Removed from original list:**
- `three_bet_ip` — Redundant. The PvP matrix inherently encodes IP/OOP: if hero is CO and villain is EP, hero is IP. A separate IP matrix just removes half the cells.
- `open_raise` — Open raise (RFI) is a unilateral decision. There is no villain involved. The original spec defined this as "hero open pos vs 3-bettor pos" which is actually the fold_to_3bet stat repackaged.

## Files to Modify

### 1. `backend/app/stat_registry.py` — PVP_MATRIX_CONFIG

Add a new config dict after the existing configs:

```python
PVP_MATRIX_CONFIG = {
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
        "single_row": True,  # Always BB — render as 1-row strip, not full matrix
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
    single_row: bool = False  # True for bb_defense (hero always BB) — render as 1-row strip
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
        single_row=config.get("single_row", False),
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
  single_row: boolean;
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
three_bet:       { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'pvp_matrix', 'postflop_bridge', 'trend_sparkline'] },
fold_to_3bet:    { ..., widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'pvp_matrix', 'by_context', 'trend_sparkline'] },
four_bet:        { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'opportunity_context', 'pvp_matrix', 'trend_sparkline'] },
call_open_raise: { ..., widgets: ['range_heatmap', 'ev_breakdown', 'pvp_matrix', 'by_context', 'trend_sparkline'] },
steal:           { ..., widgets: ['pvp_matrix', 'trend_sparkline'] },
fold_to_steal:   { ..., widgets: ['response_distribution', 'pvp_matrix', 'trend_sparkline'] },
cbet_flop:       { ..., widgets: ['positional_bar', 'pvp_matrix', 'trend_sparkline'] },
bb_defense:      { ..., widgets: ['response_distribution', 'continuing_range', 'ev_breakdown', 'pvp_matrix', 'trend_sparkline'] },
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
                    className={cell.opportunities < 30 ? 'text-text-muted' : ''}
                  >
                    {cell.pct?.toFixed(1)}
                    {cell.opportunities < 30 && (
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
4. Cells with <30 sample show muted text with subscript count
5. Impossible matchups show `—`
6. Click a cell → (future: filters hand explorer to that matchup)
7. Try multiple stats: `fold_to_3bet`, `four_bet`, `call_open_raise`, `steal`, `fold_to_steal`, `cbet_flop` → all render
8. `bb_defense` renders as a single-row strip (hero is always BB)
9. `steal` renders as a small 3x2 matrix (CO/BTN/SB rows x SB/BB cols)
10. Apply filters (stakes, date) → matrix updates
11. `cd frontend && npm run lint` — no lint errors
