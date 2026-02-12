# Phase 7 — IP/OOP Split Widget

## Goal

Add an IP/OOP Split widget to stat detail pages. Shows side-by-side comparison of the same stat split by whether hero was in position (IP) or out of position (OOP). For example, C-Bet Flop IP vs OOP shows the significant strategic difference between these spots.

**Scope**: Backend (new endpoint or filter parameter) + Frontend (new widget component).

## Weak Dependency

Phase 5 (Check-Raise) provides `check_raise_flop` flags for the IP/OOP split. The widget works without Phase 5 — it just won't have check-raise as a target stat until those flags exist.

## Design

### Visual

```
IP vs OOP
┌─────────────┬─────────────┐
│     IP      │     OOP     │
│   68.2%     │   42.1%     │
│  (312 opps) │  (278 opps) │
│   ████████  │   █████     │
└─────────────┴─────────────┘
```

- Two side-by-side panels with stat value, sample count, and a simple bar
- Color intensity based on benchmark health (green/yellow/red)
- Difference indicator: `Δ +26.1pp` between IP and OOP

### Stats That Get IP/OOP Split

| Stat | IP Filter | OOP Filter | Why |
|------|-----------|-----------|-----|
| `three_bet` | `three_bet_opp_ip = TRUE` | `three_bet_opp_ip = FALSE` | 3-bet ranges differ by relative position |
| `cbet_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | GTO c-bets ~70% IP, ~35% OOP |
| `cbet_turn` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Turn barrels differ by position |
| `cbet_river` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | River bets differ by position |
| `fold_to_cbet_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Defend more IP, fold more OOP |
| `fold_to_cbet_turn` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Same pattern |
| `fold_to_cbet_river` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Same pattern |
| `missed_cbet_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Already tracked separately |
| `went_to_showdown` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | WTSD differs by position |
| `wwsf` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | 5-10% gap expected |
| `check_raise_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Mostly OOP but IP traps exist |
| `check_raise_turn` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Same |
| `check_raise_river` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Same |
| `cbet_flop_srp` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | SRP c-bet by position |
| `cbet_flop_3bp` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | 3BP c-bet by position |

## Files to Modify

### 1. `backend/app/stat_registry.py` — IP_OOP_CONFIG

Add a new config dict:

```python
IP_OOP_CONFIG = {
    # Preflop — uses three_bet_opp_ip for relative position
    "three_bet": {
        "ip_filter": "hp.three_bet_opp_ip = TRUE",
        "oop_filter": "hp.three_bet_opp_ip = FALSE",
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
    },
    # Postflop — uses postflop_ip
    "cbet_flop": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "cbet_flop",
        "opp_flag": "cbet_flop_opp",
    },
    "cbet_turn": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "cbet_turn",
        "opp_flag": "cbet_turn_opp",
    },
    "cbet_river": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "cbet_river",
        "opp_flag": "cbet_river_opp",
    },
    "fold_to_cbet_flop": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_sql": "hp.fold_to_cbet_flop = TRUE",
        "opp_sql": "hp.fold_to_cbet_flop IS NOT NULL",
    },
    "fold_to_cbet_turn": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_sql": "hp.fold_to_cbet_turn = TRUE",
        "opp_sql": "hp.fold_to_cbet_turn IS NOT NULL",
    },
    "fold_to_cbet_river": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_sql": "hp.fold_to_cbet_river = TRUE",
        "opp_sql": "hp.fold_to_cbet_river IS NOT NULL",
    },
    "missed_cbet_flop": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "missed_cbet_flop",
        "opp_flag": "cbet_flop_opp",
    },
    "went_to_showdown": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "went_to_showdown",
        "opp_flag": "saw_flop",
    },
    "wwsf": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_sql": "CAST(COALESCE(hp.won_bb, 0) AS DOUBLE) > 0",
        "opp_sql": "hp.saw_flop = TRUE",
    },
    "check_raise_flop": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "check_raise_flop",
        "opp_flag": "check_raise_flop_opp",
    },
    "check_raise_turn": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "check_raise_turn",
        "opp_flag": "check_raise_turn_opp",
    },
    "check_raise_river": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "check_raise_river",
        "opp_flag": "check_raise_river_opp",
    },
    "cbet_flop_srp": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "cbet_flop",
        "opp_sql": "hp.cbet_flop_opp = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)",
    },
    "cbet_flop_3bp": {
        "ip_filter": "hp.postflop_ip = TRUE",
        "oop_filter": "hp.postflop_ip = FALSE",
        "action_flag": "cbet_flop",
        "opp_sql": "hp.cbet_flop_opp = TRUE AND hp.is_3bet_pot = TRUE",
    },
}
```

### 2. `backend/app/models.py` — Response model

Add:

```python
class IpOopSplitValue(BaseModel):
    value: float | None = None
    sample: int = 0
    actions: int = 0

class IpOopSplitResponse(BaseModel):
    ip: IpOopSplitValue
    oop: IpOopSplitValue
```

### 3. `backend/app/api/stats.py` — New endpoint

Add endpoint:

```python
@router.get("/detail/{stat_key}/ip-oop-split", response_model=IpOopSplitResponse)
async def get_ip_oop_split(
    stat_key: str,
    position: str | None = None,
    stakes: str | None = None,
    game_mode: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    config = IP_OOP_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(404, f"IP/OOP split not available for '{stat_key}'")

    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return IpOopSplitResponse(ip=IpOopSplitValue(), oop=IpOopSplitValue())

    where, params = _build_filter_where(player_id, position, stakes, game_mode, date_from, date_to)

    # Build action and opp SQL from config
    if "action_flag" in config:
        action_sql = f"hp.{config['action_flag']} = TRUE"
    else:
        action_sql = config["action_sql"]

    if "opp_flag" in config:
        opp_sql = f"hp.{config['opp_flag']} = TRUE"
    else:
        opp_sql = config["opp_sql"]

    result = IpOopSplitResponse(ip=IpOopSplitValue(), oop=IpOopSplitValue())

    for label, pos_filter, target in [
        ("ip", config["ip_filter"], result.ip),
        ("oop", config["oop_filter"], result.oop),
    ]:
        sql = f"""
        SELECT
            SUM(CASE WHEN {action_sql} THEN 1 ELSE 0 END) AS actions,
            COUNT(*) AS opportunities
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where} AND ({opp_sql}) AND ({pos_filter})
        """
        row = db.execute(sql, params).fetchone()
        if row:
            actions, opportunities = int(row[0] or 0), int(row[1] or 0)
            target.actions = actions
            target.sample = opportunities
            target.value = round(actions / opportunities * 100, 1) if opportunities > 0 else None

    return result
```

### 4. `frontend/src/lib/api.ts` — Types + fetch function

Add types:

```typescript
export interface IpOopSplitValue {
  value: number | null;
  sample: number;
  actions: number;
}

export interface IpOopSplitResponse {
  ip: IpOopSplitValue;
  oop: IpOopSplitValue;
}
```

Add fetch function:

```typescript
export async function getIpOopSplit(
  statKey: string,
  params?: StatFilterParams,
  signal?: AbortSignal,
): Promise<IpOopSplitResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`/api/stats/detail/${statKey}/ip-oop-split?${sp}`, { signal });
  if (!res.ok) throw new Error(`IP/OOP split error: ${res.status}`);
  return res.json();
}
```

### 5. `frontend/src/lib/stat-registry.ts` — Add widget type

Add `'ip_oop_split'` to the `WidgetType` union:

```typescript
export type WidgetType =
  | 'positional_bar'
  | 'response_distribution'
  | 'range_heatmap'
  | 'pvp_matrix'
  | 'ip_oop_split'     // ← NEW
  | 'trend_sparkline'
  // ... rest
```

Add `ip_oop_split` to widget lists for relevant stats:

```typescript
cbet_flop:          { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'trend_sparkline'] },
cbet_turn:          { ..., widgets: ['ip_oop_split', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
cbet_river:         { ..., widgets: ['ip_oop_split', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
fold_to_cbet_flop:  { ..., widgets: ['response_distribution', 'ip_oop_split', 'ev_breakdown', 'by_context', 'trend_sparkline'] },
fold_to_cbet_turn:  { ..., widgets: ['response_distribution', 'ip_oop_split', 'ev_breakdown', 'trend_sparkline'] },
fold_to_cbet_river: { ..., widgets: ['response_distribution', 'ip_oop_split', 'ev_breakdown', 'trend_sparkline'] },
went_to_showdown:   { ..., widgets: ['by_context', 'ev_breakdown', 'ip_oop_split', 'trend_sparkline'] },
wwsf:               { ..., widgets: ['composition', 'by_context', 'ip_oop_split', 'trend_sparkline'] },
three_bet:          { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'pvp_matrix', 'ip_oop_split', 'postflop_bridge', 'trend_sparkline'] },
missed_cbet_flop:   { ..., widgets: ['ip_oop_split', 'ev_breakdown', 'by_context', 'trend_sparkline'] },
// Phase 4 stats
cbet_flop_srp:      { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
cbet_flop_3bp:      { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
// Phase 5 stats (if available)
check_raise_flop:   { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'ip_oop_split', 'by_context', 'sizing_histogram', 'trend_sparkline'] },
```

### 6. `frontend/src/components/stats/IpOopSplitWidget.tsx` — New component

Create a new widget:

```tsx
interface IpOopSplitWidgetProps {
  statKey: string;
  filters: StatFilterParams;
}

export default function IpOopSplitWidget({ statKey, filters }: IpOopSplitWidgetProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['ip-oop-split', statKey, filters],
    queryFn: ({ signal }) => getIpOopSplit(statKey, filters, signal),
  });

  if (isLoading) return <Skeleton className="h-24" />;
  if (!data) return null;

  const { ip, oop } = data;
  const diff = ip.value !== null && oop.value !== null
    ? (ip.value - oop.value).toFixed(1)
    : null;

  return (
    <Card>
      <CardHeader><CardTitle>IP vs OOP</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* IP panel */}
          <div className="text-center">
            <div className="text-sm text-text-muted">In Position</div>
            <div className="text-2xl font-bold">
              {ip.value !== null ? `${ip.value}%` : '—'}
            </div>
            <div className="text-xs text-text-muted">{ip.sample} opps</div>
            {/* Progress bar */}
            <div className="mt-2 h-2 rounded bg-surface">
              <div
                className="h-full rounded bg-primary"
                style={{ width: `${Math.min(ip.value ?? 0, 100)}%` }}
              />
            </div>
          </div>

          {/* OOP panel */}
          <div className="text-center">
            <div className="text-sm text-text-muted">Out of Position</div>
            <div className="text-2xl font-bold">
              {oop.value !== null ? `${oop.value}%` : '—'}
            </div>
            <div className="text-xs text-text-muted">{oop.sample} opps</div>
            <div className="mt-2 h-2 rounded bg-surface">
              <div
                className="h-full rounded bg-primary"
                style={{ width: `${Math.min(oop.value ?? 0, 100)}%` }}
              />
            </div>
          </div>
        </div>

        {/* Difference indicator */}
        {diff !== null && (
          <div className="mt-3 text-center text-sm text-text-muted">
            Δ {parseFloat(diff) >= 0 ? '+' : ''}{diff}pp
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

### 7. `frontend/src/components/stats/StatDetailPanel.tsx` — Wire up widget

In the widget rendering switch, add:

```tsx
case 'ip_oop_split':
  return <IpOopSplitWidget statKey={statKey} filters={filters} />;
```

## Verification

1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `GET /api/stats/detail/cbet_flop/ip-oop-split` returns `{ ip: { value: ..., sample: ... }, oop: { value: ..., sample: ... } }`
3. Navigate to `/stats/cbet_flop` → IP/OOP Split widget renders with two panels
4. IP value should be higher than OOP for c-bet stats
5. Difference indicator shows the gap in pp
6. Try multiple stats: `fold_to_cbet_flop`, `went_to_showdown`, `wwsf`, `three_bet` → all render
7. Apply filters → widget updates
8. Stats without IP_OOP_CONFIG → widget doesn't render (graceful absence)
9. `cd frontend && npm run lint` — no lint errors
