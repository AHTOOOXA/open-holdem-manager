# Phase 8 Implementation -- IP/OOP Split Widget

## Goal

Add an IP/OOP (In Position / Out of Position) split widget to stat detail pages. Shows a side-by-side comparison of the same stat split by whether hero was in position or out of position postflop.

**Why this matters:** Positional advantage is the single biggest edge in postflop play. Having last action lets you control pot size, realize equity more efficiently, and bluff more profitably. A player c-betting the same rate IP and OOP is making a fundamental strategic error -- they should be c-betting significantly more often IP (55-70%) than OOP (30-50%). This widget quantifies how well the hero exploits (or fails to exploit) that advantage across 9 key stats.

**Scope:** New backend endpoint + new frontend widget component. Medium effort.

**DB columns used (already exist):**
- `hand_players.postflop_ip` (BOOLEAN) -- whether hero had position postflop
- `hand_players.three_bet_opp_ip` (BOOLEAN) -- whether hero had position relative to opener when 3-bet opportunity arose

## Files to Modify

### 1. `backend/app/stat_registry.py` -- Add IP_OOP_CONFIG + IP_OOP_BENCHMARKS

Add two new config dicts at the end of the file (before `get_key_street`).

The config uses either `action_flag`/`opp_flag` (simple boolean columns) or `action_sql`/`opp_sql` (complex expressions). The endpoint handler resolves both forms.

```python
# ── IP/OOP Split Config ─────────────────────────────────────────────
# Maps stat_key -> filters for IP vs OOP split.
# Each entry has ip_filter, oop_filter (WHERE clause for position side),
# plus action/opp columns (using either flag or sql form).

from app.models import IpOopBenchmark

IP_OOP_CONFIG: dict[str, dict] = {
    # Preflop -- uses three_bet_opp_ip for relative position to the opener
    "three_bet": {
        "ip_filter": "hp.three_bet_opp_ip = TRUE",
        "oop_filter": "hp.three_bet_opp_ip = FALSE",
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
    },
    # Postflop -- uses postflop_ip (player with latest position among flop survivors)
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

Also add `IP_OOP_CONFIG` and `IP_OOP_BENCHMARKS` to the existing imports in `api/stats.py` (step 3 below).

### 2. `backend/app/models.py` -- Add response models (~15 lines)

Add three new models after the existing `PostflopBridgeResponse` (around line 585):

```python
class IpOopSplitValue(BaseModel):
    value: float | None = None
    sample: int = 0
    actions: int = 0

class IpOopBenchmark(BaseModel):
    ip_low: float
    ip_high: float
    oop_low: float
    oop_high: float

class IpOopSplitResponse(BaseModel):
    ip: IpOopSplitValue
    oop: IpOopSplitValue
    benchmark: IpOopBenchmark | None = None
```

Note: `IpOopBenchmark` is both a response model (returned to frontend) and used in `stat_registry.py` for the benchmark constants. The import in `stat_registry.py` (`from app.models import IpOopBenchmark`) creates this shared dependency.

### 3. `backend/app/api/stats.py` -- New endpoint (~45 lines)

Add the endpoint at the end of the file. Uses the existing `_get_hero_player_id()` and `_build_filter_where()` helpers already defined in this file.

**Add to imports** (line 17-21):

```python
from app.stat_registry import (
    STAT_REGISTRY, get_key_street, RESPONSE_DECOMPOSITION,
    EV_BREAKDOWN_CONFIG, SIZING_CONFIG, FOLD_EQUITY_CONFIG,
    BY_CONTEXT_CONFIG, COMPOSITION_CONFIG, MONEY_CONFIG, POSTFLOP_BRIDGE_CONFIG,
    IP_OOP_CONFIG, IP_OOP_BENCHMARKS,  # ← NEW
)
```

**Add to model imports** (line 7-14):

```python
from app.models import (
    ...,
    IpOopSplitResponse, IpOopSplitValue,  # ← NEW
)
```

**Add endpoint:**

```python
@router.get("/stats/detail/{stat_key}/ip-oop-split", response_model=IpOopSplitResponse)
def get_ip_oop_split(
    stat_key: str = Path(...),
    position: str | None = Query(None),
    stakes: str | None = Query(None),
    game_mode: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    config = IP_OOP_CONFIG.get(stat_key)
    if not config:
        raise HTTPException(status_code=404, detail=f"IP/OOP split not available for '{stat_key}'")

    db = get_read_cursor()
    player_id = _get_hero_player_id(db)
    if not player_id:
        return IpOopSplitResponse(ip=IpOopSplitValue(), oop=IpOopSplitValue())

    base_where, base_params = _build_filter_where(
        player_id, position, stakes, game_mode, date_from, date_to,
    )

    # Resolve action/opp expressions from config
    if "action_flag" in config:
        action_sql = f"hp.{config['action_flag']} = TRUE"
    else:
        action_sql = config["action_sql"]

    if "opp_flag" in config:
        opp_sql = f"hp.{config['opp_flag']} = TRUE"
    else:
        opp_sql = config["opp_sql"]

    benchmark = IP_OOP_BENCHMARKS.get(stat_key)
    result = IpOopSplitResponse(
        ip=IpOopSplitValue(), oop=IpOopSplitValue(), benchmark=benchmark,
    )

    for label, pos_filter in [("ip", config["ip_filter"]), ("oop", config["oop_filter"])]:
        sql = f"""
        SELECT
            SUM(CASE WHEN {action_sql} THEN 1 ELSE 0 END) AS actions,
            COUNT(*) AS opportunities
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {base_where} AND ({opp_sql}) AND ({pos_filter})
        """
        row = db.execute(sql, base_params).fetchone()
        if row:
            actions = int(row[0] or 0)
            opportunities = int(row[1] or 0)
            target = result.ip if label == "ip" else result.oop
            target.actions = actions
            target.sample = opportunities
            target.value = round(actions / opportunities * 100, 1) if opportunities > 0 else None

    return result
```

**Endpoint behavior:**
- Returns 404 if `stat_key` not in `IP_OOP_CONFIG` (e.g., `check_raise_flop`, `donk_bet_flop`, `cbet_flop_srp`)
- Returns empty `IpOopSplitValue` objects (value=None, sample=0) if no hero player found
- Runs two queries: one for IP-filtered hands, one for OOP-filtered hands
- Includes benchmark ranges for frontend coloring

### 4. `frontend/src/lib/api.ts` -- Types + fetch function (~25 lines)

**Add types** after the existing `ContinuingRangeResponse` (around line 1348):

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

**Add fetch function** after `getStatRange` (around line 1449):

```typescript
export async function getIpOopSplit(statKey: string, params?: StatFilterParams, signal?: AbortSignal): Promise<IpOopSplitResponse> {
  const sp = _buildStatParams(params);
  const res = await fetch(`${BASE}/stats/detail/${encodeURIComponent(statKey)}/ip-oop-split?${sp}`, { signal });
  if (!res.ok) throw new Error(`IP/OOP split failed: ${res.statusText}`);
  return res.json();
}
```

### 5. `frontend/src/lib/query-keys.ts` -- Add query key (1 line)

Add inside the `stats` object (after `statRange`):

```typescript
ipOopSplit: (statKey: string, filters: Record<string, unknown>) => ['stats', 'ip-oop-split', statKey, filters] as const,
```

### 6. `frontend/src/components/stats/widgets/IpOopSplitWidget.tsx` -- New component (~100 lines)

Create a new widget component. Visual spec:

```
IP vs OOP
+-----------------+-----------------+
|   In Position   | Out of Position |
|    68.2%        |    42.1%        |  <- colored green/yellow/red vs benchmark
|   312 opps      |   278 opps      |
|  target: 55-70  |  target: 30-50  |  <- benchmark range shown
|   =========     |   ======        |  <- bar colored to match
+-----------------+-----------------+
           delta +26.1pp
```

Key design decisions:
- **Benchmark coloring:** green when value is within the benchmark range, yellow when within 5pp of range, red otherwise
- **Minimum sample threshold:** show "(low sample)" warning when < 30 opportunities
- **Delta indicator:** the difference between IP and OOP values is the primary coaching signal -- it tells you whether you're adjusting enough by position
- **Props:** receives `statKey`, `filterParams`, and `position` (same interface as other widgets via `stdProps`)

```tsx
import { useQuery } from '@tanstack/react-query';
import { getIpOopSplit } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

const MIN_SAMPLE = 30;

function benchmarkColor(value: number | null, low: number, high: number): string {
  if (value === null) return 'text-muted-foreground';
  if (value >= low && value <= high) return 'text-green';
  if (value >= low - 5 && value <= high + 5) return 'text-yellow-400';
  return 'text-red';
}

function barBg(value: number | null, low: number, high: number): string {
  if (value === null) return 'bg-muted';
  if (value >= low && value <= high) return 'bg-green';
  if (value >= low - 5 && value <= high + 5) return 'bg-yellow-400';
  return 'bg-red';
}

export default function IpOopSplitWidget({ statKey, filterParams, position }: Props) {
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.ipOopSplit(statKey, params),
    queryFn: ({ signal }) => getIpOopSplit(statKey, params, signal),
  });

  if (isPending) return <Skeleton className="h-20 w-full" />;
  if (!data) return null;

  const { ip, oop, benchmark } = data;
  // Neutral benchmark when none provided (everything shows green)
  const bm = benchmark ?? { ip_low: 0, ip_high: 100, oop_low: 0, oop_high: 100 };

  const diff = ip.value !== null && oop.value !== null
    ? ip.value - oop.value
    : null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">IP vs OOP</div>
      <div className="grid grid-cols-2 gap-3">
        {/* IP panel */}
        <div className="text-center">
          <div className="text-[10px] text-muted-foreground">In Position</div>
          <div className={cn("text-lg font-bold", benchmarkColor(ip.value, bm.ip_low, bm.ip_high))}>
            {ip.value !== null ? `${ip.value}%` : '--'}
          </div>
          <div className="text-[10px] text-muted-foreground">
            {ip.sample} opps{ip.sample > 0 && ip.sample < MIN_SAMPLE ? ' (low sample)' : ''}
          </div>
          {benchmark && (
            <div className="text-[9px] text-muted-foreground">
              target: {bm.ip_low}-{bm.ip_high}%
            </div>
          )}
          <div className="mt-1 h-1.5 rounded bg-muted">
            <div
              className={cn("h-full rounded", barBg(ip.value, bm.ip_low, bm.ip_high))}
              style={{ width: `${Math.min(ip.value ?? 0, 100)}%` }}
            />
          </div>
        </div>

        {/* OOP panel */}
        <div className="text-center">
          <div className="text-[10px] text-muted-foreground">Out of Position</div>
          <div className={cn("text-lg font-bold", benchmarkColor(oop.value, bm.oop_low, bm.oop_high))}>
            {oop.value !== null ? `${oop.value}%` : '--'}
          </div>
          <div className="text-[10px] text-muted-foreground">
            {oop.sample} opps{oop.sample > 0 && oop.sample < MIN_SAMPLE ? ' (low sample)' : ''}
          </div>
          {benchmark && (
            <div className="text-[9px] text-muted-foreground">
              target: {bm.oop_low}-{bm.oop_high}%
            </div>
          )}
          <div className="mt-1 h-1.5 rounded bg-muted">
            <div
              className={cn("h-full rounded", barBg(oop.value, bm.oop_low, bm.oop_high))}
              style={{ width: `${Math.min(oop.value ?? 0, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Delta indicator */}
      {diff !== null && (
        <div className="mt-1.5 text-center text-[10px] text-muted-foreground">
          {'\u0394'} {diff >= 0 ? '+' : ''}{diff.toFixed(1)}pp
        </div>
      )}
    </div>
  );
}
```

### 7. `frontend/src/components/stats/widgets/AnalysisWidgets.tsx` -- Wire up widget

**Add import** (after existing widget imports, around line 22):

```typescript
import IpOopSplitWidget from './IpOopSplitWidget';
```

**Add case** in the `renderWidget` switch (around line 84), before the `default` case:

```typescript
case 'ip_oop_split':
  return <IpOopSplitWidget {...stdProps} />;
```

### 8. `frontend/src/lib/stat-registry.ts` -- Add widget type + update widget lists

**Add `'ip_oop_split'` to the `WidgetType` union** (line 3-20):

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
  | 'ip_oop_split';     // ← NEW
```

**Update widget lists** for 9 stats. `ip_oop_split` goes FIRST for c-bet and fold-to-cbet stats (the most important dimension), and in a strategic position for others:

```typescript
// C-Bet: ip_oop_split FIRST -- most important dimension for c-bet
cbet_flop:         { ..., widgets: ['ip_oop_split', 'positional_bar', 'trend_sparkline'] },
cbet_turn:         { ..., widgets: ['ip_oop_split', 'positional_bar', 'trend_sparkline'] },
cbet_river:        { ..., widgets: ['ip_oop_split', 'positional_bar', 'trend_sparkline'] },

// Fold to C-Bet: ip_oop_split FIRST
fold_to_cbet_flop: { ..., widgets: ['ip_oop_split', 'positional_bar', 'response_distribution', 'trend_sparkline'] },
fold_to_cbet_turn: { ..., widgets: ['ip_oop_split', 'positional_bar', 'response_distribution', 'trend_sparkline'] },
fold_to_cbet_river:{ ..., widgets: ['ip_oop_split', 'positional_bar', 'response_distribution', 'trend_sparkline'] },

// 3-Bet: after postflop_bridge (IP/OOP is secondary to range analysis for preflop)
three_bet:         { ..., widgets: ['range_heatmap', 'fold_equity', 'ev_breakdown', 'postflop_bridge', 'ip_oop_split', 'trend_sparkline'] },

// Showdown: middle position
went_to_showdown:  { ..., widgets: ['ip_oop_split', 'trend_sparkline'] },
wwsf:              { ..., widgets: ['ip_oop_split', 'trend_sparkline'] },
```

**Not added** (see exclusion rationale below):
- `check_raise_flop/turn/river` -- OOP-only action, IP panel would be noise
- `donk_bet_flop/turn/river` -- OOP-only by definition
- `cbet_flop_srp`, `cbet_flop_3bp` -- already cross-sliced by pot type; adding IP/OOP creates tiny samples
- `missed_cbet_flop` -- stats engine already has `mc_ip_total`/`mc_oop_total` separately

## Stats Excluded from IP/OOP Split (and why)

| Stat | Reason |
|------|--------|
| `check_raise_flop/turn/river` | Check-raise is inherently an OOP action (check to the IP player, then raise). IP check-raises only happen in rare multiway spots. The IP side would show near-zero samples and mislead users into thinking they have a meaningful stat. |
| `donk_bet_flop/turn/river` | Donk betting is by definition an OOP action (betting into the preflop aggressor from OOP). There is no IP equivalent. |
| `cbet_flop_srp`, `cbet_flop_3bp` | These already encode a pot-type dimension. Adding IP/OOP creates a 4-way cross (SRP-IP, SRP-OOP, 3BP-IP, 3BP-OOP) with tiny samples per cell. Use pot-type as a separate filter on the main `cbet_flop` IP/OOP split instead. |
| `missed_cbet_flop` | The stats engine already computes `mc_ip_total`/`mc_oop_total` separately. Adding a widget-level split is redundant with existing breakdowns. |

## Strategic Sanity Checks

These directional checks validate that the data pipeline (parser -> stat_flags -> DB -> endpoint -> widget) is working correctly. If any of these are violated, there is a bug somewhere.

| Check | Expected Direction | Why |
|-------|-------------------|-----|
| `cbet_flop` IP > OOP | IP 15-25pp higher | IP c-bets more freely (can check back to control pot). OOP c-bets selectively (vulnerable to raises). |
| `cbet_turn` IP > OOP | IP 10-20pp higher | Turn barrels are more polarized OOP. IP can size bets to deny equity. |
| `cbet_river` IP > OOP | IP 10-20pp higher | River is the most polarized street. IP can value-bet thinner. |
| `fold_to_cbet_flop` OOP > IP | OOP 5-15pp higher | OOP folds more because continuing without position is expensive. IP defends wider. |
| `fold_to_cbet_turn` OOP > IP | OOP 5-15pp higher | Same dynamic amplified. OOP facing a turn barrel is in a tough spot. |
| `fold_to_cbet_river` OOP > IP | OOP 3-10pp higher | River folds converge more (pot-odds decisions), but OOP still folds slightly more. |
| `three_bet` IP > OOP | IP 3-6pp higher | 3-bet IP is wider (you close the action with position). 3-bet OOP is tighter. |
| `wwsf` IP > OOP | IP 10-15pp higher | Position lets you win more pots without showdown (better bluff spots, more fold equity). |
| `went_to_showdown` IP > OOP | IP 4-8pp higher | IP gets to showdown more because they can bluff-catch efficiently. OOP folds more to positional pressure. |
| IP sample + OOP sample ~ total | Samples should add up | No hands are lost or double-counted by the position filter. |

If `cbet_flop` IP < OOP (gap < 0pp), the hero is c-betting backwards -- this is a major leak and the widget is doing its job by exposing it.

## Benchmark Reference Values

| Stat | IP Range | OOP Range | Green/Yellow/Red Coloring |
|------|----------|-----------|--------------------------|
| three_bet | 8-12% | 4-7% | Green: in range. Yellow: within 5pp. Red: outside. |
| cbet_flop | 55-70% | 30-50% | Same coloring rules. |
| cbet_turn | 45-60% | 30-45% | Same. |
| cbet_river | 40-55% | 25-40% | Same. |
| fold_to_cbet_flop | 35-45% | 45-55% | Same. |
| fold_to_cbet_turn | 40-50% | 50-60% | Same. |
| fold_to_cbet_river | 45-55% | 50-60% | Same. |
| went_to_showdown | 28-35% | 22-30% | Same. |
| wwsf | 50-58% | 38-46% | Same. |

## Test Checklist

### Automated
1. `cd backend && python -m pytest tests/test_parser.py -v` -- all tests pass (no parser or stat flag changes)
2. `cd frontend && npm run lint` -- no TypeScript or lint errors

### API Verification
3. `GET /api/stats/detail/cbet_flop/ip-oop-split` returns `{ ip: { value: ..., sample: ..., actions: ... }, oop: { value: ..., sample: ..., actions: ... }, benchmark: { ip_low: 55, ip_high: 70, oop_low: 30, oop_high: 50 } }`
4. `GET /api/stats/detail/cbet_flop/ip-oop-split?position=BTN` returns filtered data (only BTN hands)
5. `GET /api/stats/detail/cbet_flop/ip-oop-split?stakes=$0.05/$0.10` returns filtered by stakes
6. `GET /api/stats/detail/check_raise_flop/ip-oop-split` returns 404 with message "IP/OOP split not available for 'check_raise_flop'" (correctly excluded)
7. `GET /api/stats/detail/donk_bet_flop/ip-oop-split` returns 404 (correctly excluded)
8. `GET /api/stats/detail/cbet_flop_srp/ip-oop-split` returns 404 (correctly excluded)
9. `GET /api/stats/detail/three_bet/ip-oop-split` returns data using `three_bet_opp_ip` filter (not `postflop_ip`)

### Strategic Sanity Checks (with real data)
10. `cbet_flop` IP value should be meaningfully higher than OOP (15-25pp gap is normal). If the gap is < 10pp, the hero is not adjusting enough by position.
11. `fold_to_cbet_flop` OOP value should be higher than IP. If IP fold rate is higher than OOP, something is wrong with the data or the hero plays backwards.
12. `three_bet` IP value should be higher than OOP. If they are nearly equal, the hero is not exploiting position preflop.
13. `wwsf` IP should be 10-15pp higher than OOP. A gap smaller than 8pp suggests the hero is not leveraging positional advantage postflop.
14. For each stat: `ip.sample + oop.sample` should roughly equal the total opportunities for that stat (sanity check: no hands are lost or double-counted).

### UI Verification
15. Navigate to C-Bet Flop detail page -- IP/OOP Split widget renders FIRST (before positional bar), with two panels, benchmark colors, and target ranges
16. Low sample warning appears when opportunities < 30 (visible as "(low sample)" text)
17. Apply filters (stakes, date range, position) -- widget updates correctly
18. Delta indicator shows correct gap (e.g., "+26.1pp" for cbet_flop)
19. Benchmark coloring works: green for values in range, yellow for borderline, red for out of range
20. Stats without `IP_OOP_CONFIG` (e.g., `vpip`, `open_raise`, `donk_bet_flop`) -- widget does not render (graceful absence, no error)
21. Navigate to `went_to_showdown` detail -- IP/OOP Split widget renders with appropriate values
22. Navigate to `wwsf` detail -- IP/OOP Split widget renders with appropriate values
