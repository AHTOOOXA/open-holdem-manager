# Milestone 1: "The App That Tells You What's Wrong"

> **Goal**: A new player imports hands and immediately understands their leaks.
> **Coaching parallel**: The Database Review — the first thing every coach does with a new student.
> **Priority**: Highest. This is the difference between "a wall of numbers" and "a tool that helps me improve."

---

## 1. Research

### Why This Is #1

Every poker coaching engagement starts the same way: the coach opens the student's database, compares stats against benchmarks, and identifies the top 2-3 leaks. This is universally the highest-impact session — small changes to the biggest leaks produce outsized winrate improvements.

The tools that do this well:

- **Leak Buster**: Scans 465 potential leak areas using 55+ custom filters. Compares stats against benchmarks from tens of millions of winning player hands. Ranks leaks by severity. Estimates financial impact. Identifies 10-25 significant leaks per player on average. Has a scoring algorithm that weighs impact of each deviation.
- **PT4 LeakTracker**: Built into PokerTracker 4. Horizontal bar for each stat with color-coded zones (green = profitable, light gray = needs improvement, dark gray = major leak). Black marker shows where player falls. Breaks down by position. Includes instructional videos.
- **GTO Wizard GTO Reports**: Compares aggregate stats against GTO frequencies. Red = too aggressive (exceeding GTO), blue = too passive (falling short). Toggle between absolute and relative display. Position-vs-position drill-down. Low-sample indicators.

**Current OHM experience**: User imports hands → sees stats page with 30+ numbers → has no idea what's good or bad → no guidance on what to fix first.

**Target OHM experience**: User imports hands → every stat is color-coded green/yellow/red → top 3 leaks are highlighted with severity ranking and estimated cost → clicking a leak opens relevant hands.

### Benchmark Sources

Benchmarks compiled from multiple coaching sources (BlackRain79, MyPokerCoaching, Smart Poker Study, SplitSuit, Hand2Note, Poker Copilot, Run It Once forums, FreeBetRange, GTO Wizard):

**6-max NL Hold'em Cash optimal ranges**:

| Stat | Optimal Low | Optimal High | Leak if Below | Leak if Above |
|------|------------|-------------|---------------|---------------|
| VPIP | 22% | 27% | Too tight, missing value spots | Too loose, playing junk hands |
| PFR | 19% | 23% | Passive — limping instead of raising | Over-aggressive opens |
| VPIP-PFR Gap | 3pp | 6pp | — | >8pp means excessive limping/cold-calling |
| 3-Bet | 7% | 10% | <4% = predictable, only premiums | >12% = 3-betting too light |
| Fold to 3-Bet | 55% | 65% | <50% = calling too wide vs 3-bets | >72% = folding exploitably often |
| 4-Bet | 2% | 3% | Never 4-betting light, predictable | Spewing with 4-bet bluffs |
| Fold to 4-Bet | 55% | 68% | Calling 4-bets too wide | Folding too much to 4-bets |
| Attempt to Steal | 30% | 38% | Missing steal opportunities | >45% = stealing too wide |
| Fold to Steal | 65% | 75% | <60% = defending blinds too wide | >80% = bleeding blinds |
| Flop C-Bet | 55% | 70% | Too passive after raising preflop | >85% = auto-cbetting, exploitable |
| Turn C-Bet | 45% | 60% | "One-and-done" — bet flop, give up turn | Barreling without equity |
| River C-Bet | 40% | 55% | Missing thin value on river | Over-bluffing rivers |
| Fold to Flop C-Bet | 45% | 60% | <40% = floating/calling too wide | >70% = surrendering pots |
| Fold to Turn C-Bet | 35% | 50% | Calling station on turns | Too fit-or-fold |
| WTSD | 27% | 32% | <25% = over-folding postflop | >35% = calling station |
| W$SD | 50% | 55% | Arriving at showdown with weak hands | >60% = only showing nuts (too tight) |
| WWSF | 45% | 53% | Too passive, not bluffing enough | >58% = over-aggression |
| AF (per street) | 2.5 | 3.5 | <2 = passive, check-calling too much | >5 = maniac aggression |

**Positional Open Raise benchmarks**:

| Position | Optimal Low | Optimal High |
|----------|------------|-------------|
| EP | 14% | 18% |
| MP | 18% | 23% |
| CO | 25% | 32% |
| BTN | 40% | 50% |
| SB | 35% | 48% |

**Positional bb/100 expectations** (6-max):

| Position | Expected Range | Major Leak Threshold |
|----------|---------------|---------------------|
| BTN | +15 to +25 bb/100 | Below +10 |
| CO | +5 to +15 bb/100 | Below 0 |
| MP | +0 to +8 bb/100 | Below -5 |
| EP | +0 to +8 bb/100 | Below -5 |
| SB | -8 to -15 bb/100 | Worse than -20 |
| BB | -15 to -25 bb/100 | Worse than -30 |

### Strategy Drift — Why No Competitor Has This

No major tracker (PT4, HM3, Hand2Note, GTO Wizard) has strategy drift detection as a first-class feature. Coaches identify drift manually by comparing time-period stats — a tedious process most players never do.

Drift detection serves the mental game / tilt coaching scenario:
- **Tilt**: VPIP/PFR spike upward (playing too loose/aggressive after bad beats)
- **Scared money**: VPIP/PFR drop (playing too tight at higher stakes or during downswings)
- **Fatigue**: AF drops, WTSD rises (stop making aggressive plays, start calling too much)
- **Autopilot**: C-Bet flop spikes to 90%+ (mindlessly betting without board texture awareness)
- **Slow drift**: Gradual changes over weeks that are invisible without measurement

The mental game coaching session typically looks at:
- Session-by-session results (sudden drops = tilt indicator)
- Time-of-day analysis (worse play late at night)
- Session length analysis (performance deterioration after 2+ hours)
- Results after big losses (chasing behavior)
- Hands-per-hour anomalies (spike = rushing/autopilot)

Drift detection automates ALL of this with a simple statistical computation.

---

## 2. Product Design

### M1.1 — Stat Benchmark Layer

**What**: Add green/yellow/red health indicators to every stat on the existing Stats page.

**User story**: "As a player looking at my stats, I want to instantly see which stats are within optimal ranges and which are leaks, so I know where to focus my study time."

**Requirements**:
- Every stat cell on the Stats page gets a colored indicator (dot, background tint, or border)
- Green = within optimal range
- Yellow = borderline (within 20% of range boundary)
- Red = outside optimal range
- Tooltip on hover shows: benchmark range, player's value, and a one-line coaching tip
- Benchmarks are per-stat AND per-position where applicable (Open Raise from EP has different range than BTN)
- Works with existing filters (stakes, date range) — benchmarks don't change, but the stat values being compared do
- Minimum sample size threshold: don't color stats with <100 hands (show as gray/neutral)

**Benchmark storage**: Frontend config object. No backend changes needed. Benchmarks are static coaching knowledge, not computed from data.

```typescript
interface BenchmarkRange {
  low: number;
  high: number;
  tip_low: string;   // coaching tip when stat is below range
  tip_high: string;  // coaching tip when stat is above range
}

interface StatBenchmarks {
  [statKey: string]: BenchmarkRange | {
    [position: string]: BenchmarkRange;
  };
}
```

**Yellow zone calculation**: 20% band outside the optimal range. E.g., if optimal is 55-65%, yellow is 51-55% (low side) and 65-69% (high side). Below 51% or above 69% = red.

### M1.2 — Leak Summary Panel

**What**: A panel that surfaces the top leaks ranked by estimated impact, with actionable coaching tips and deep links to relevant hands.

**User story**: "As a player who just imported my hands, I want to see my biggest leaks ranked by importance, with advice on how to fix each one, so I have a clear study plan."

**Where it lives**: Two options (decide during implementation):
- **Option A**: New "Dashboard" page that becomes the landing page after first import (replace Upload as default when hands exist)
- **Option B**: Collapsible panel at the top of the existing Stats page

**Recommendation**: Option B initially (less routing changes), migrate to Option A when Dashboard has enough content.

**Requirements**:
- Shows top 5 leaks, sorted by estimated impact (bb/100)
- Each leak shows: stat name, current value, target range, estimated cost, one-line fix suggestion
- "View hands" link deep-links to hand browser with pre-applied filters
- Below leaks: list of "on-track" stats (green checkmarks) for positive reinforcement
- Minimum sample: only show leaks from stats with 200+ opportunities
- Refresh when filters change (different stakes may reveal different leaks)

**Impact estimation**:
- `deviation = abs(actual_value - midpoint_of_optimal_range)`
- `impact_bb100 = deviation * weight_factor`
- Weight factors (relative importance of each stat category):

| Category | Weight | Rationale |
|----------|--------|-----------|
| VPIP / PFR | 0.15 | Affects every single hand |
| 3-Bet / Fold to 3-Bet | 0.10 | High-frequency preflop decision |
| Steal / Fold to Steal | 0.08 | Occurs every orbit in late position |
| Open Raise (positional) | 0.08 | Foundation of preflop strategy |
| C-Bet Flop | 0.06 | Most common postflop decision |
| C-Bet Turn / River | 0.04 | Lower frequency, still impactful |
| WTSD / W$SD / WWSF | 0.04 | Showdown tendencies |
| AF | 0.03 | Aggression balance |

These weights are coaching heuristics, not exact EV computations. They're directionally correct and massively better than no ranking.

**Coaching tips database**: Hardcoded map of `statKey → { tip_low, tip_high, fix_suggestion }`. Examples:

```
fold_to_3bet:
  tip_high: "You fold to 3-bets significantly more than optimal."
  fix: "Widen your 3-bet calling range, especially from BTN and CO. Add suited broadways (KJs, QTs) and medium pocket pairs."

attempt_to_steal:
  tip_low: "You're not stealing blinds often enough from late position."
  fix: "Open wider from CO/BTN when folded to you. At 6-max, you should be opening 25-32% from CO and 40-50% from BTN."

cbet_flop:
  tip_high: "You're c-betting too frequently, especially on wet boards."
  fix: "Check back more often on coordinated flops (connected, suited) and in multiway pots. Reserve c-bets for dry boards and heads-up."
```

### M1.3 — Strategy Drift Detection

**What**: Monitor rolling windows of key stats and show trend arrows next to stats, alerting when play deviates from the player's own baseline.

**User story**: "As a player in the middle of a session or over a week of play, I want to know if my play style is drifting from my baseline, so I can catch tilt, fatigue, or bad habits early."

**How it works**:
1. Compute **lifetime baseline** stats (the player's overall "A-game" profile)
2. Compute stats over **rolling windows** (configurable: last 500, 1k, 2k, 5k, 10k hands)
3. Compare using z-scores: `z = (rolling_mean - lifetime_mean) / lifetime_stddev`
4. Flag when |z| > 2.0 (statistically significant deviation at ~95% confidence)

**Stats to monitor**:

| Stat | Drift Up Means | Drift Down Means |
|------|---------------|-----------------|
| VPIP | Tilt/boredom — playing too loose | Scared money — playing too tight |
| PFR | Over-aggression (tilt) | Passivity (fear/fatigue) |
| AF (postflop) | Spewing — maniac mode | Calling station mode |
| WTSD | Can't let go — calling too much | Over-folding postflop |
| Fold to 3-Bet | Getting tighter (possibly OK) | Ego/tilt — calling 3-bets too wide |
| W$SD | Running good (or value betting better) | Bad calls getting to showdown |
| C-Bet Flop | Autopilot c-betting | Missing value, checking too much |
| WWSF (non-SD proxy) | — | Red line falling — folding too much postflop |

**UI (Option B — trend arrows, recommended for Sprint 1)**:
- Small ↑↓→ arrow next to each stat value on the Stats page
- Arrow color: green (improving toward benchmark), red (drifting away from benchmark), gray (no significant change)
- Tooltip on hover: "Your VPIP changed from 24.1% (lifetime) to 29.3% (last 2000 hands). This is +2.8σ — a statistically significant increase. Possible tilt or boredom."
- Only show arrows for stats with sufficient sample (lifetime 1000+ hands, rolling window 200+ hands)

**Future UI expansions** (not Sprint 1):
- "A-Game Score" — single composite number 0-100
- Dashboard widget with stat health dots
- Alert notifications when drift exceeds threshold

---

## 3. UI/UX Design

### M1.1 — Benchmark Indicators on Stats Page

**Current stat cell** (example: Open Raise from CO = 30%):
```
┌──────┐
│  30  │  ← plain number, no context
└──────┘
```

**Enhanced stat cell with benchmark** — three design options:

**Option A — Colored dot** (minimal, cleanest):
```
┌────────┐
│ 🟢 30  │  ← green dot = within range
└────────┘

┌────────┐
│ 🔴 72  │  ← red dot = outside range
└────────┘
```

**Option B — Background tint** (more visible, H2N-like):
```
┌──────────┐
│░░░ 30 ░░░│  ← green-tinted background
└──────────┘

┌──────────┐
│▓▓▓ 72 ▓▓▓│  ← red-tinted background
└──────────┘
```

**Option C — Side bar** (compact, works in dense tables):
```
┌─┬──────┐
│▌│  30  │  ← thin green bar on left edge
└─┴──────┘

┌─┬──────┐
│▌│  72  │  ← thin red bar on left edge
└─┴──────┘
```

**Recommendation**: Option B (background tint) at very low opacity (5-10%). It's the most visible without cluttering the table. The existing color coding (green/red text for good/bad play) stays — the background tint is an additional layer for benchmark comparison.

**Tooltip design**:
```
┌──────────────────────────────────────────┐
│  Fold to 3-Bet                           │
│  Your value: 72.1%                       │
│  Target range: 55% – 65%                 │
│  Status: ⚠ Above optimal range           │
│                                          │
│  You fold to 3-bets more often than      │
│  optimal. This makes you exploitable —   │
│  opponents can 3-bet you profitably      │
│  with any two cards.                     │
│                                          │
│  Fix: Widen your calling range vs        │
│  3-bets, especially from BTN and CO.     │
└──────────────────────────────────────────┘
```

### M1.2 — Leak Summary Panel

**Location**: Top of Stats page, collapsible.

```
┌──────────────────────────────────────────────────────────────────────┐
│  YOUR TOP LEAKS                     13,402 hands  │  ▼ Collapse     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. ⚠ Fold to 3-Bet: 72.1%                        Cost: ~1.2 bb/100 │
│     Target: 55-65%  ·  847 opportunities                             │
│     Widen your calling range vs 3-bets from BTN/CO                   │
│     [View 847 hands →]                                               │
│  ─────────────────────────────────────────────────────────────────── │
│  2. ⚠ Attempt to Steal: 22.0%                     Cost: ~0.8 bb/100 │
│     Target: 30-38%  ·  2,130 opportunities                          │
│     Open wider from CO/BTN when folded to you                        │
│     [View steal opportunities →]                                     │
│  ─────────────────────────────────────────────────────────────────── │
│  3. ⚠ Flop C-Bet: 82.4%                           Cost: ~0.5 bb/100 │
│     Target: 55-70%  ·  1,892 opportunities                          │
│     Check back more on coordinated boards and multiway               │
│     [View flop c-bet hands →]                                        │
│                                                                      │
│  ✅ On Track                                                         │
│  3-Bet 8.2% (7-10%)  ·  VPIP 24% (22-27%)  ·  WTSD 29% (27-32%)  │
│  PFR 20% (19-23%)  ·  AF 2.9 (2.5-3.5)                            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### M1.3 — Drift Arrows

**Placement**: Inline with stat values, after the number.

```
PRE-FLOP          Total  EP   MP   CO   BTN  SB   BB
Open Raise          28↑   16   19   30   51   53   27
Fold to 3Bet        61↓   58   54   60   66   68    0₁
```

Arrow is small, colored:
- `↑` green = stat moving toward benchmark (good)
- `↑` red = stat moving away from benchmark (bad)
- `↓` green = stat moving toward benchmark (good)
- `↓` red = stat moving away from benchmark (bad)
- No arrow = no significant drift (|z| < 1.5)

The direction of the arrow (up/down) shows what's happening. The color (green/red) shows whether it's good or bad. A stat can go up and be bad (VPIP rising above range) or go up and be good (3-Bet rising toward range).

---

## 4. Technical Spec

### M1.1 — Benchmark Config

**Frontend-only change. No backend needed.**

```typescript
// src/lib/benchmarks.ts

export interface BenchmarkRange {
  low: number;
  high: number;
  tipLow: string;
  tipHigh: string;
  fix: string;
  weight: number;  // for leak impact estimation
}

export type PositionalBenchmarks = {
  total: BenchmarkRange;
  ep?: BenchmarkRange;
  mp?: BenchmarkRange;
  co?: BenchmarkRange;
  btn?: BenchmarkRange;
  sb?: BenchmarkRange;
  bb?: BenchmarkRange;
};

export const BENCHMARKS: Record<string, BenchmarkRange | PositionalBenchmarks> = {
  vpip: {
    total: { low: 22, high: 27, weight: 0.15,
      tipLow: "You're playing too tight — missing profitable spots.",
      tipHigh: "You're playing too many hands — entering pots with weak holdings.",
      fix: "Focus on position-aware hand selection. Open wider from BTN/CO, tighter from EP."
    }
  },
  fold_to_3bet: {
    total: { low: 55, high: 65, weight: 0.10,
      tipLow: "You're calling 3-bets too wide — probably losing money postflop with marginal hands.",
      tipHigh: "You fold to 3-bets too often — opponents can 3-bet you profitably with any two cards.",
      fix: "Widen your 3-bet calling range. Add suited broadways (KJs, QTs) and medium pairs (77-99)."
    }
  },
  open_raise: {
    total: { low: 18, high: 24, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
    ep:    { low: 14, high: 18, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
    mp:    { low: 18, high: 23, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
    co:    { low: 25, high: 32, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
    btn:   { low: 40, high: 50, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
    sb:    { low: 35, high: 48, weight: 0.08, tipLow: "...", tipHigh: "...", fix: "..." },
  },
  // ... all other stats
};
```

**Color computation helper**:

```typescript
export type HealthStatus = 'green' | 'yellow' | 'red' | 'neutral';

export function getStatHealth(
  value: number,
  benchmark: BenchmarkRange,
  sample: number,
  minSample = 100
): { status: HealthStatus; direction?: 'low' | 'high' } {
  if (sample < minSample) return { status: 'neutral' };

  const range = benchmark.high - benchmark.low;
  const yellowBand = range * 0.3; // 30% of range width as yellow zone

  if (value >= benchmark.low && value <= benchmark.high) {
    return { status: 'green' };
  }
  if (value < benchmark.low) {
    if (value >= benchmark.low - yellowBand) return { status: 'yellow', direction: 'low' };
    return { status: 'red', direction: 'low' };
  }
  // value > benchmark.high
  if (value <= benchmark.high + yellowBand) return { status: 'yellow', direction: 'high' };
  return { status: 'red', direction: 'high' };
}
```

### M1.2 — Leak Computation

**Frontend computation from existing stats API response. No new backend endpoint needed initially.**

```typescript
export interface Leak {
  statKey: string;
  statName: string;
  position?: string;
  value: number;
  sample: number;
  benchmark: BenchmarkRange;
  direction: 'low' | 'high';
  estimatedImpact: number;  // bb/100 estimate
  tip: string;
  fix: string;
  handFilterUrl: string;    // deep link to hands page
}

export function computeLeaks(stats: HeroStats): Leak[] {
  const leaks: Leak[] = [];

  for (const [key, benchmark] of Object.entries(BENCHMARKS)) {
    const statValue = extractStatValue(stats, key); // helper to get value + sample
    if (!statValue || statValue.sample < 200) continue;

    const health = getStatHealth(statValue.value, benchmark, statValue.sample);
    if (health.status !== 'red') continue;

    const midpoint = (benchmark.low + benchmark.high) / 2;
    const deviation = Math.abs(statValue.value - midpoint);
    const impact = deviation * benchmark.weight;

    leaks.push({
      statKey: key,
      statName: STAT_DISPLAY_NAMES[key],
      value: statValue.value,
      sample: statValue.sample,
      benchmark,
      direction: health.direction!,
      estimatedImpact: Math.round(impact * 10) / 10,
      tip: health.direction === 'low' ? benchmark.tipLow : benchmark.tipHigh,
      fix: benchmark.fix,
      handFilterUrl: buildHandFilterUrl(key, health.direction),
    });
  }

  return leaks.sort((a, b) => b.estimatedImpact - a.estimatedImpact);
}
```

### M1.3 — Drift Detection Backend

**New endpoint**: `GET /api/reports/drift`

**Query params**:
- `window` (int, default 2000): number of recent hands for the rolling window
- `stakes` (string, optional): filter by stakes
- `date_from` / `date_to` (string, optional): date filters apply to BOTH baseline and window

**Response**:
```json
{
  "window_size": 2000,
  "lifetime_hands": 13402,
  "window_hands": 2000,
  "stats": [
    {
      "key": "vpip",
      "name": "VPIP",
      "lifetime_value": 24.1,
      "window_value": 29.3,
      "lifetime_stddev": 1.8,
      "z_score": 2.89,
      "direction": "up",
      "significant": true,
      "interpretation": "Playing looser than baseline — possible tilt or boredom"
    },
    {
      "key": "pfr",
      "name": "PFR",
      "lifetime_value": 19.5,
      "window_value": 20.1,
      "lifetime_stddev": 1.5,
      "z_score": 0.40,
      "direction": "up",
      "significant": false,
      "interpretation": null
    }
  ]
}
```

**Backend implementation** (`backend/app/api/reports.py`):

```python
@router.get("/api/reports/drift")
def get_drift(
    window: int = 2000,
    stakes: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    db = get_db()
    hero_id = get_hero_player_id(db)

    # Base WHERE clause
    where = "hp.player_id = ?"
    params = [hero_id]
    if stakes:
        where += " AND h.stakes = ?"
        params.append(stakes)
    if date_from:
        where += " AND h.played_at >= ?"
        params.append(date_from)
    if date_to:
        where += " AND h.played_at <= ?"
        params.append(date_to)

    # Query 1: Lifetime stats
    lifetime_sql = f"""
        SELECT
            COUNT(*) as hands,
            AVG(CASE WHEN vpip THEN 1.0 ELSE 0.0 END) * 100 as vpip_avg,
            STDDEV(CASE WHEN vpip THEN 1.0 ELSE 0.0 END) * 100 as vpip_std,
            -- ... repeat for each stat
        FROM hand_players hp
        JOIN hands h ON hp.hand_id = h.id
        WHERE {where}
    """

    # Query 2: Rolling window stats (last N hands)
    window_sql = f"""
        SELECT
            COUNT(*) as hands,
            AVG(CASE WHEN vpip THEN 1.0 ELSE 0.0 END) * 100 as vpip_avg,
            -- ... repeat for each stat
        FROM (
            SELECT hp.*
            FROM hand_players hp
            JOIN hands h ON hp.hand_id = h.id
            WHERE {where}
            ORDER BY h.played_at DESC
            LIMIT ?
        ) sub
    """

    lifetime = db.execute(lifetime_sql, params).fetchone()
    window_result = db.execute(window_sql, params + [window]).fetchone()

    # Compute z-scores
    results = []
    for stat_key, stat_name in DRIFT_STATS:
        lifetime_avg = getattr(lifetime, f"{stat_key}_avg")
        lifetime_std = getattr(lifetime, f"{stat_key}_std")
        window_avg = getattr(window_result, f"{stat_key}_avg")

        if lifetime_std and lifetime_std > 0:
            z = (window_avg - lifetime_avg) / lifetime_std
        else:
            z = 0

        results.append({
            "key": stat_key,
            "name": stat_name,
            "lifetime_value": round(lifetime_avg, 1),
            "window_value": round(window_avg, 1),
            "lifetime_stddev": round(lifetime_std, 1) if lifetime_std else 0,
            "z_score": round(z, 2),
            "direction": "up" if z > 0 else "down",
            "significant": abs(z) > 2.0,
            "interpretation": get_drift_interpretation(stat_key, z)
        })

    return {"window_size": window, "lifetime_hands": lifetime.hands,
            "window_hands": window_result.hands, "stats": results}
```

**Drift interpretation helper**:

```python
DRIFT_INTERPRETATIONS = {
    "vpip": {
        "up": "Playing looser than baseline — possible tilt or boredom",
        "down": "Playing tighter than baseline — possible scared money or fatigue"
    },
    "pfr": {
        "up": "More aggressive preflop — possible over-aggression",
        "down": "More passive preflop — possible fear or fatigue"
    },
    # ... etc
}

def get_drift_interpretation(stat_key: str, z_score: float) -> str | None:
    if abs(z_score) < 2.0:
        return None
    direction = "up" if z_score > 0 else "down"
    return DRIFT_INTERPRETATIONS.get(stat_key, {}).get(direction)
```

---

## 5. Execution Plan

### Sprint 1 Tasks

**M1.1 — Benchmarks (3-4 days)**:
1. Create `src/lib/benchmarks.ts` with all benchmark ranges and coaching tips
2. Create `getStatHealth()` utility function
3. Add background tint (or dot) to `StatCell` component in `StatsPage.tsx`
4. Add tooltip component with benchmark info on hover
5. Test: verify all stats get correct coloring across different stat profiles

**M1.2 — Leak Summary (3-4 days)**:
1. Create `computeLeaks()` function in `src/lib/benchmarks.ts`
2. Create `LeakSummaryPanel` component
3. Create `LeakCard` sub-component (stat name, value, benchmark, tip, fix, hand link)
4. Create `OnTrackList` sub-component (green checkmarks for good stats)
5. Add panel to top of `StatsPage.tsx` (collapsible)
6. Wire "View hands" links to hand browser with pre-applied filters
7. Test: verify leak ranking, impact estimation, deep links

**M1.3 — Drift Detection (3-4 days)**:
1. Add `GET /api/reports/drift` endpoint to `backend/app/api/reports.py`
2. Add drift SQL queries (lifetime vs. rolling window)
3. Add interpretation helper
4. Create `useDrift()` hook in frontend
5. Add trend arrows to `StatCell` component
6. Add drift tooltip on arrow hover
7. Test: verify z-score computation, arrow direction/color logic

### Sprint 1 Dependencies

- None. All three features can be built on top of the existing Stats page without any schema changes, parser changes, or data migrations.
- M1.1 and M1.3 can be built in parallel (independent).
- M1.2 depends on M1.1 (uses the same benchmark config).

---

## 6. Testing

### M1.1 — Benchmark Indicators

**Unit tests**:
- `getStatHealth()` returns correct status for values inside range, in yellow zone, and in red zone
- `getStatHealth()` returns `neutral` when sample < minSample
- Positional benchmarks correctly resolve per-position ranges
- Edge cases: exactly on boundary values, zero sample, null values

**Visual QA**:
- Import a real hand history (13k+ hands)
- Verify: stats within range are green, borderline are yellow, leaks are red
- Verify: tooltip shows correct benchmark range and coaching tip
- Verify: positional stats use position-specific benchmarks (not just total)
- Test with different stakes filters — same benchmark ranges, different stat values

### M1.2 — Leak Summary

**Unit tests**:
- `computeLeaks()` returns leaks sorted by descending impact
- `computeLeaks()` excludes stats with <200 sample
- `computeLeaks()` excludes stats within optimal range
- Impact estimation: verify `deviation * weight` formula
- Deep link URLs are correctly constructed

**Integration tests**:
- Panel shows correct number of leaks for a known stat profile
- "On Track" section shows stats within range
- "View hands" links navigate to hand browser with correct filters
- Panel collapses and expands correctly
- Panel updates when stats filters change

### M1.3 — Drift Detection

**Unit tests**:
- Z-score computation: `z = (rolling - lifetime) / stddev`
- Significant flag: true when |z| > 2.0, false otherwise
- Direction: "up" when z > 0, "down" when z < 0
- Handle edge cases: zero stddev, insufficient sample, identical values

**Integration tests**:
- Endpoint returns correct drift data for a known hand sample
- Arrows appear only when drift is significant (|z| > 1.5 for arrows, > 2.0 for significant flag)
- Arrow color is green when drifting toward benchmark, red when away
- Tooltip shows correct values and interpretation
- Works correctly with stakes/date filters

**Performance test**:
- Drift endpoint responds in <500ms for 50k hands
- Two SQL queries should be fast with existing indexes

### Acceptance Criteria

- [ ] Every stat on the Stats page has a visible benchmark indicator (colored background or dot)
- [ ] Hovering any stat shows its benchmark range and coaching tip
- [ ] Leak summary panel shows top 5 leaks ranked by impact with estimates
- [ ] Each leak has a "View hands" link that navigates to the correct filtered hand browser view
- [ ] Stats within optimal range show as "On Track" with green checkmarks
- [ ] Trend arrows appear next to stats when recent play deviates from lifetime baseline
- [ ] Arrow color correctly indicates whether drift is toward or away from optimal
- [ ] All indicators respect minimum sample size thresholds
- [ ] All indicators update when stats page filters (stakes, date range) change
