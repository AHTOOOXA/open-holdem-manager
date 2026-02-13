# Phase 7 — IP/OOP Split Widget

## Goal

Add an IP/OOP Split widget to stat detail pages. Shows side-by-side comparison of the same stat split by whether hero was in position (IP) or out of position (OOP). Positional advantage is the single biggest edge in postflop play — having last action lets you control pot size, realize equity more efficiently, and bluff more profitably. This widget quantifies how well the hero exploits (or fails to exploit) that advantage across key stats.

For example, C-Bet Flop IP vs OOP exposes whether the hero appropriately adjusts c-bet frequency by position. A player c-betting the same rate IP and OOP is making a fundamental strategic error.

**Scope**: Backend (new endpoint or filter parameter) + Frontend (new widget component).

## Weak Dependency

Phase 5 (Check-Raise) provides `check_raise_flop` flags. However, check-raise is inherently an OOP action (you check, then raise when the IP player bets). IP check-raises are extremely rare edge cases (trapping in multiway pots) and not worth splitting. Check-raise stats are excluded from this widget — they are OOP-only by nature and the IP/OOP split adds noise rather than signal.

## Design

### Visual

```
IP vs OOP
┌───────────────┬───────────────┐
│   In Position │Out of Position│
│    68.2%      │    42.1%      │  ← colored green/yellow/red vs benchmark
│   312 opps    │   278 opps    │
│  target: 55-70│ target: 30-50 │  ← benchmark range shown
│   █████████   │   ██████      │  ← bar colored to match
└───────────────┴───────────────┘
           Δ +26.1pp
```

- Two side-by-side panels with stat value, sample count, benchmark target range, and a colored bar
- Color based on benchmark health: green (within range), yellow (within 5pp of range), red (outside)
- Low sample warning when < 30 opportunities (stat is unreliable at that size)
- Difference indicator: `Δ +26.1pp` between IP and OOP — this is the primary coaching signal

### Stats That Get IP/OOP Split

| Stat | IP Filter | OOP Filter | Why | Expected Gap |
|------|-----------|-----------|-----|--------------|
| `three_bet` | `three_bet_opp_ip = TRUE` | `three_bet_opp_ip = FALSE` | 3-bet IP is wider because you close the action with position. 3-bet OOP is tighter, value-heavy. This is the single biggest preflop IP/OOP distinction. | IP 8-12%, OOP 4-7% |
| `cbet_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | IP c-bets more freely (can check back to control pot, has info advantage). OOP c-bets selectively (vulnerable to raises, no free card option). Exact frequencies depend on SRP vs 3BP and board texture. | IP 55-70%, OOP 30-50% |
| `cbet_turn` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Turn barrels are more polarized OOP (donk-lead or check-raise territory). IP can size bets to deny equity efficiently. | IP 45-60%, OOP 30-45% |
| `cbet_river` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | River is the most polarized street. IP can value-bet thinner because they see the OOP check first. | IP 40-55%, OOP 25-40% |
| `fold_to_cbet_flop` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | OOP folds more to c-bets because continuing without position is expensive. IP defends wider because they realize equity better. A player folding the same rate IP and OOP is overfolding IP or underfolding OOP. | IP 35-45%, OOP 45-55% |
| `fold_to_cbet_turn` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Same dynamic as flop but amplified. OOP facing a turn barrel after calling flop is in a tough spot without position. | IP 40-50%, OOP 50-60% |
| `fold_to_cbet_river` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | River folds should converge more (both are pot-odds decisions), but OOP still folds slightly more due to range disadvantage from earlier streets. | IP 45-55%, OOP 50-60% |
| `went_to_showdown` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | IP goes to showdown less because they can bluff-catch or give up more efficiently. OOP gets to showdown less because they fold more to positional pressure. | IP 28-35%, OOP 22-30% |
| `wwsf` | `postflop_ip = TRUE` | `postflop_ip = FALSE` | Won When Saw Flop is significantly higher IP because position lets you win more pots without showdown (better bluff spots, more fold equity). A large gap here is healthy. | IP 50-58%, OOP 38-46% |

### Stats Excluded from IP/OOP Split

| Stat | Reason |
|------|--------|
| `check_raise_flop/turn/river` | Check-raise is inherently an OOP action (check to the IP player, then raise). IP check-raises only happen in rare multiway spots. The IP side would show near-zero samples and mislead users into thinking they have a meaningful stat. |
| `donk_bet_flop/turn/river` | Donk betting is by definition an OOP action (betting into the preflop aggressor from OOP). There is no IP equivalent. |
| `cbet_flop_srp`, `cbet_flop_3bp` | These already encode a pot-type dimension. Adding IP/OOP creates a 4-way cross (SRP-IP, SRP-OOP, 3BP-IP, 3BP-OOP) with tiny samples per cell. Use pot-type as a separate filter on the main `cbet_flop` IP/OOP split instead. |
| `missed_cbet_flop` | The stats engine already computes `mc_ip_total`/`mc_oop_total` separately. Adding a widget-level split is redundant with existing breakdowns. |

## Files to Modify

### 1. `backend/app/stat_registry.py` — IP_OOP_CONFIG

Add a new config dict. Only stats where the IP/OOP split is strategically meaningful and both sides have sufficient sample sizes are included. Stats that are inherently one-sided (check-raise, donk bet) or already cross-sliced by another dimension (SRP/3BP c-bet) are excluded.

```python
IP_OOP_CONFIG = {
    # Preflop — uses three_bet_opp_ip for relative position to the opener
    "three_bet": {
        "ip_filter": "hp.three_bet_opp_ip = TRUE",
        "oop_filter": "hp.three_bet_opp_ip = FALSE",
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
    },
    # Postflop — uses postflop_ip (player with latest position among flop survivors)
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
}
```

**Excluded from config** (see rationale in "Stats Excluded" table above):
- `check_raise_flop/turn/river` — OOP-only action, IP samples are noise
- `donk_bet_flop/turn/river` — OOP-only by definition
- `cbet_flop_srp`, `cbet_flop_3bp` — already cross-sliced by pot type; use pot-type filter on `cbet_flop` instead
- `missed_cbet_flop` — already broken out in stats engine (`mc_ip_total`/`mc_oop_total`)

### 2. `backend/app/models.py` — Response model

Add:

```python
class IpOopSplitValue(BaseModel):
    value: float | None = None
    sample: int = 0
    actions: int = 0

class IpOopBenchmark(BaseModel):
    ip_low: float    # green threshold low bound for IP
    ip_high: float   # green threshold high bound for IP
    oop_low: float
    oop_high: float

class IpOopSplitResponse(BaseModel):
    ip: IpOopSplitValue
    oop: IpOopSplitValue
    benchmark: IpOopBenchmark | None = None  # populated from IP_OOP_BENCHMARKS
```

Add benchmark constants (used for green/yellow/red coloring):

```python
IP_OOP_BENCHMARKS: dict[str, IpOopBenchmark] = {
    "three_bet":          IpOopBenchmark(ip_low=8, ip_high=12, oop_low=4, oop_high=7),
    "cbet_flop":          IpOopBenchmark(ip_low=55, ip_high=70, oop_low=30, oop_high=50),
    "cbet_turn":          IpOopBenchmark(ip_low=45, ip_high=60, oop_low=30, oop_high=45),
    "cbet_river":         IpOopBenchmark(ip_low=40, ip_high=55, oop_low=25, oop_high=40),
    "fold_to_cbet_flop":  IpOopBenchmark(ip_low=35, ip_high=45, oop_low=45, oop_high=55),
    "fold_to_cbet_turn":  IpOopBenchmark(ip_low=40, ip_high=50, oop_low=50, oop_high=60),
    "fold_to_cbet_river": IpOopBenchmark(ip_low=45, ip_high=55, oop_low=50, oop_high=60),
    "went_to_showdown":   IpOopBenchmark(ip_low=28, ip_high=35, oop_low=22, oop_high=30),
    "wwsf":               IpOopBenchmark(ip_low=50, ip_high=58, oop_low=38, oop_high=46),
}
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

    benchmark = IP_OOP_BENCHMARKS.get(stat_key)
    result = IpOopSplitResponse(ip=IpOopSplitValue(), oop=IpOopSplitValue(), benchmark=benchmark)

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

export interface IpOopBenchmark {
  ip_low: number;
  ip_high: number;
  oop_low: number;
  oop_high: number;
}

export interface IpOopSplitResponse {
  ip: IpOopSplitValue;
  oop: IpOopSplitValue;
  benchmark: IpOopBenchmark | null;
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

Add `ip_oop_split` to widget lists for relevant stats. Place it high in the widget order since IP/OOP is one of the most impactful dimensions for these stats:

```typescript
// ip_oop_split goes FIRST for c-bet stats — it's the most important dimension
cbet_flop:          { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'sizing_histogram', 'by_context', 'trend_sparkline'] },
cbet_turn:          { ..., widgets: ['ip_oop_split', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
cbet_river:         { ..., widgets: ['ip_oop_split', 'ev_breakdown', 'sizing_histogram', 'trend_sparkline'] },
fold_to_cbet_flop:  { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'by_context', 'trend_sparkline'] },
fold_to_cbet_turn:  { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'trend_sparkline'] },
fold_to_cbet_river: { ..., widgets: ['ip_oop_split', 'response_distribution', 'ev_breakdown', 'trend_sparkline'] },
went_to_showdown:   { ..., widgets: ['by_context', 'ev_breakdown', 'ip_oop_split', 'trend_sparkline'] },
wwsf:               { ..., widgets: ['composition', 'ip_oop_split', 'by_context', 'trend_sparkline'] },
three_bet:          { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'pvp_matrix', 'ip_oop_split', 'postflop_bridge', 'trend_sparkline'] },
```

**Not added** (see exclusion rationale above):
- `missed_cbet_flop` — already has IP/OOP breakdown in stats engine
- `cbet_flop_srp`, `cbet_flop_3bp` — pot-type should be a filter, not a cross-dimension
- `check_raise_flop` — OOP-only action, IP panel would be noise

### 6. `frontend/src/components/stats/IpOopSplitWidget.tsx` — New component

Create a new widget. Key design decisions:
- Benchmark coloring: green when value is within the benchmark range, yellow when within 5pp of range, red otherwise
- Minimum sample threshold: show "low sample" warning when < 30 opportunities (stat is unreliable)
- The difference indicator (delta) is the primary coaching signal — it tells you whether you're adjusting enough by position

```tsx
interface IpOopSplitWidgetProps {
  statKey: string;
  filters: StatFilterParams;
}

const MIN_SAMPLE = 30;

function benchmarkColor(value: number | null, low: number, high: number): string {
  if (value === null) return 'text-text-muted';
  if (value >= low && value <= high) return 'text-green';       // in range
  if (value >= low - 5 && value <= high + 5) return 'text-yellow-400'; // borderline
  return 'text-red';                                              // out of range
}

function barColor(value: number | null, low: number, high: number): string {
  if (value === null) return 'bg-surface';
  if (value >= low && value <= high) return 'bg-green';
  if (value >= low - 5 && value <= high + 5) return 'bg-yellow-400';
  return 'bg-red';
}

export default function IpOopSplitWidget({ statKey, filters }: IpOopSplitWidgetProps) {
  const { data, isLoading } = useQuery({
    queryKey: ['ip-oop-split', statKey, filters],
    queryFn: ({ signal }) => getIpOopSplit(statKey, filters, signal),
  });

  if (isLoading) return <Skeleton className="h-24" />;
  if (!data) return null;

  const { ip, oop, benchmark } = data;
  const diff = ip.value !== null && oop.value !== null
    ? (ip.value - oop.value).toFixed(1)
    : null;

  // Default benchmark range if none provided (neutral coloring)
  const bm = benchmark ?? { ip_low: 0, ip_high: 100, oop_low: 0, oop_high: 100 };

  return (
    <Card>
      <CardHeader><CardTitle>IP vs OOP</CardTitle></CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* IP panel */}
          <div className="text-center">
            <div className="text-sm text-text-muted">In Position</div>
            <div className={cn("text-2xl font-bold", benchmarkColor(ip.value, bm.ip_low, bm.ip_high))}>
              {ip.value !== null ? `${ip.value}%` : '—'}
            </div>
            <div className="text-xs text-text-muted">
              {ip.sample} opps{ip.sample < MIN_SAMPLE && ip.sample > 0 ? ' (low sample)' : ''}
            </div>
            {benchmark && (
              <div className="text-xs text-text-muted mt-0.5">
                target: {bm.ip_low}-{bm.ip_high}%
              </div>
            )}
            <div className="mt-2 h-2 rounded bg-surface">
              <div
                className={cn("h-full rounded", barColor(ip.value, bm.ip_low, bm.ip_high))}
                style={{ width: `${Math.min(ip.value ?? 0, 100)}%` }}
              />
            </div>
          </div>

          {/* OOP panel */}
          <div className="text-center">
            <div className="text-sm text-text-muted">Out of Position</div>
            <div className={cn("text-2xl font-bold", benchmarkColor(oop.value, bm.oop_low, bm.oop_high))}>
              {oop.value !== null ? `${oop.value}%` : '—'}
            </div>
            <div className="text-xs text-text-muted">
              {oop.sample} opps{oop.sample < MIN_SAMPLE && oop.sample > 0 ? ' (low sample)' : ''}
            </div>
            {benchmark && (
              <div className="text-xs text-text-muted mt-0.5">
                target: {bm.oop_low}-{bm.oop_high}%
              </div>
            )}
            <div className="mt-2 h-2 rounded bg-surface">
              <div
                className={cn("h-full rounded", barColor(oop.value, bm.oop_low, bm.oop_high))}
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

### Automated
1. `cd backend && python -m pytest tests/test_parser.py -v` — all tests pass
2. `cd frontend && npm run lint` — no lint errors

### API
3. `GET /api/stats/detail/cbet_flop/ip-oop-split` returns `{ ip: { value: ..., sample: ... }, oop: { value: ..., sample: ... }, benchmark: { ip_low: 55, ip_high: 70, ... } }`
4. `GET /api/stats/detail/check_raise_flop/ip-oop-split` returns 404 (correctly excluded)
5. `GET /api/stats/detail/cbet_flop_srp/ip-oop-split` returns 404 (correctly excluded)

### Strategic Sanity Checks (with real data)
6. `cbet_flop` IP value should be meaningfully higher than OOP (15-25pp gap is normal). If the gap is < 10pp, the hero is not adjusting enough by position.
7. `fold_to_cbet_flop` OOP value should be higher than IP. If IP fold rate is higher than OOP, something is wrong with the data or the hero plays backwards.
8. `three_bet` IP value should be higher than OOP. If they are nearly equal, the hero is not exploiting position preflop.
9. `wwsf` IP should be 10-15pp higher than OOP. A gap smaller than 8pp suggests the hero is not leveraging positional advantage postflop.
10. `ip.sample + oop.sample` should roughly equal the total opportunities for that stat (sanity check: no hands are lost or double-counted).

### UI
11. Navigate to `/stats/cbet_flop` → IP/OOP Split widget renders with two panels, benchmark colors, and target ranges
12. Low sample warning appears when opportunities < 30
13. Apply filters (stakes, date range) → widget updates correctly
14. Stats without IP_OOP_CONFIG → widget doesn't render (graceful absence)
