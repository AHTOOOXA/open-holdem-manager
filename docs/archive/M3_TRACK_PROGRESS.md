# Milestone 3: "The App That Shows Your Progress"

> **Goal**: Make coaching measurable — did the work pay off?
> **Coaching parallel**: Follow-up Database Review, Results/Variance Analysis, Mental Game/Tilt Detection.
> **Priority**: Medium-High. Essential for long-term engagement and coaching accountability.

---

## 1. Research

### Coaching Scenarios This Serves

**Before/After Progress Tracking (Follow-up Database Review)**

Every structured coaching program includes periodic reviews. The most common cadence:
- CFP (Coaching for Profits) programs: review every 100,000 hands
- Private coaching: review every 2-4 weeks
- Self-study: weekly check-ins recommended

The coach compares stats from two periods: "before we started working on your 3-bet range" vs. "after." If the 3-bet stat moved from 4% to 8%, the coaching worked. If the winrate improved alongside, the coaching paid for itself.

**What coaches look for in progress reviews**:
- Did the targeted leak stats actually change? (stat trend over time)
- Did the changes translate to improved winrate? (results correlation)
- Are there new leaks that emerged while fixing old ones? (regression detection)
- Is the student playing enough volume to measure progress? (sample size awareness)
- Before/after stat comparison with specific date boundaries

**Results & Variance Analysis**

The results graph session is typically the first thing a coach pulls up. Key patterns coaches read:

- **Green line vs. EV line divergence**: When actual results (green) are below expected value (EV/orange), the player is running bad. When EV itself is declining, the problem is strategic.
- **"Alligator mouth" pattern**: Showdown line (blue) rising + non-showdown line (red) falling = wins at showdown but bleeds chips everywhere else = not bluffing enough, not fighting for pots.
- **Session clustering**: Sudden drops within a graph often represent tilt sessions. Identifying these visually is the first step to mental game coaching.
- **Positional P&L**: Filtering the graph by position reveals which seats are profitable. A BB loss rate worse than -25 bb/100 instantly flags blind defense as a major leak.

**Mental Game & Tilt Detection**

Coaches identify these as primary mental game patterns:
- **Bad beat tilt**: Sudden VPIP/PFR spike after losing a big pot
- **Downswing tilt**: Extended losing period → scared money (tighter play) or chasing (looser play)
- **Entitlement tilt**: Expecting to win, getting frustrated when variance hits
- **Session length decay**: Performance drops after 2+ hours (fatigue)
- **Late-night leaks**: Playing worse after midnight (common among recreational players)
- **Post-loss patterns**: After losing 100bb+, what happens in the next 20 hands?

Coaching protocols for mental game:
- Pre-session routine: goal setting, distraction elimination
- Stop-loss rules: quit after losing N buy-ins
- Session length limits: 60-90 min max for focused play
- Post-session journaling: what happened, how you felt, what to change
- Understanding variance: each hand is independent, short-term results are largely luck

**What tools exist for progress tracking**:
- **Hand2Note Pin feature**: Side-by-side report comparison (two date ranges or two players)
- **GTO Wizard GTO Reports**: Date range filtering with absolute/relative toggle
- **PT4 monthly grouping**: Filter last 3 months separately, compare month-over-month
- **Smart Poker Study 4-day cycle**: Study → Play → Review → Analyze → Repeat
- No major tracker has automated stat trend visualization or coaching milestone markers

### The Session Analytics Gap

Most trackers treat sessions as an afterthought. PT4 and HM3 show basic session lists but lack:
- Time-of-day correlation with winrate
- Session-length correlation with performance
- Post-loss behavioral analysis
- Tilt detection signals
- Calendar view with daily P&L (PT4 has this, most loved feature)

For Rush & Cash specifically, "sessions" are continuous (no table starts/stops). Sessions must be detected by time gaps between hands (30+ minutes = new session).

---

## 2. Product Design

### M3.1 — Stat Trend Charts

**What**: Rolling averages of key stats plotted over time, showing how the player's strategy evolves.

**User story**: "As a player working on my 3-bet range, I want to see my 3-bet percentage over time to verify that my study is translating into actual play changes."

**Two views**:

**a) Sparklines in stat detail panel** (integrated with M2.1):
- Mini line chart (200×60px) embedded in the stat detail panel
- X-axis: time (auto-scaled: by day for short ranges, by week for longer)
- Y-axis: stat percentage
- Horizontal reference line at benchmark center (from M1.1 benchmarks)
- Rolling window of 500 opportunities to smooth noise
- Shaded benchmark zone (green band between low-high)

**b) Standalone "Trends" page** (new page):
- Multi-stat chart: select 2-4 stats to plot on shared timeline
- Winrate overlay (bb/100 on secondary Y-axis) for correlation
- Preset stat groups: "Preflop" (VPIP, PFR, 3-Bet), "Aggression" (AF, C-Bet, WWSF), "Showdown" (WTSD, W$SD)
- Time range selector: 1 month, 3 months, 6 months, 1 year, all
- Annotation markers: user-addable milestones ("started working on blind defense", "coaching session #3")

**Data computation**:
- For each stat, compute value over rolling windows of N opportunities
- Window slides by time (one data point per day or per 500 hands, whichever is more granular)
- Store as time-series points: `{ date, value, sample_in_window }`
- Confidence indicator: gray out points where window has <100 opportunities

### M3.2 — Before/After Comparison

**What**: Select two date ranges and see all stats side-by-side with difference column and improvement arrows.

**User story**: "As a player who's been coached for a month, I want to compare my stats from before and after coaching to see what improved and what didn't."

**Requirements**:
- Two date range selectors (Period A and Period B)
- Presets: "Last month vs. previous month", "Last 5k hands vs. previous 5k", "This year vs. last year"
- All stats shown in a comparison table: Stat | Period A | Period B | Change | Direction
- Change column: absolute difference in percentage points
- Direction arrow: green ↑/↓ when moving toward benchmark, red when moving away, gray when insignificant
- Significance threshold: ignore changes <1pp or where either period has <200 sample
- Summary at top: "7 stats improved, 2 regressed, 12 unchanged"
- Winrate comparison row at bottom: bb/100 for each period with confidence intervals

**Implementation**: Two separate calls to existing `GET /api/stats/hero` with different `date_from`/`date_to`. Diff computation in frontend. No new backend endpoint needed.

### M3.3 — Session Analytics

**What**: Auto-detect sessions from hand timestamps, provide per-session analysis, and surface tilt/fatigue patterns.

**User story**: "As a player who sometimes tilts, I want to see my results broken down by session, time of day, and session length, so I can identify when my play deteriorates."

**Session detection**:
- For Rush & Cash: session boundary = 30+ minute gap between consecutive hands
- Algorithm: sort hands by `played_at`, walk linearly, start new session when gap > 30 min
- Store session boundaries as derived data (not in DB — compute on demand or cache)
- Each session has: start_time, end_time, duration, hand_count, stakes, won_bb, won_usd, bb_per_100

**Session list view**:

| Date | Start | Duration | Hands | Stakes | Won (BB) | Won ($) | bb/100 |
|------|-------|----------|-------|--------|----------|---------|--------|
| Feb 8 | 20:15 | 1h 42m | 312 | $0.25/$0.50 | +18.5 | +$9.25 | +5.9 |
| Feb 7 | 22:30 | 2h 15m | 428 | $0.25/$0.50 | -42.0 | -$21.00 | -9.8 |
| Feb 7 | 19:00 | 1h 10m | 215 | $0.25/$0.50 | +8.2 | +$4.10 | +3.8 |

Color coding: green row = winning session, red row = losing session, intensity by magnitude.

**Time-of-day analysis**:
- Group sessions by hour of day (or 2-hour blocks)
- Show: sessions count, total hands, total won, bb/100
- Bar chart visualization
- Highlight: "You play +6.2 bb/100 between 7-10 PM but -3.8 bb/100 after midnight"

**Session length analysis**:
- Group sessions by duration buckets: <30min, 30-60min, 1-2h, 2-3h, 3h+
- Show: sessions count, total hands, bb/100 per bucket
- Scatter plot: x=session duration, y=bb/100
- Highlight: "Your bb/100 drops from +5.1 to -2.3 after the 2-hour mark"

**Post-loss pattern detection**:
- Identify hands where hero lost >50bb
- Compute stats for the next 20 hands after each big loss
- Compare VPIP/PFR/AF in "post-loss" sample vs. overall
- Show: "After losing a big pot, your VPIP spikes from 24% to 33% for the next 20 hands"

**Calendar view** (stretch goal):
- Month grid, each day is a cell
- Cell color: green gradient (winning day) or red gradient (losing day), intensity by magnitude
- Cell content: total won (BB), number of sessions
- Click day → show sessions for that day
- Click session → navigate to hands for that session
- Month summary row: total hands, total won, bb/100, sessions count

### M3.4 — Enhanced Results Graph

**What**: Upgrade the existing results graph with progress-tracking features.

**User story**: "As a player reviewing my results, I want to see session boundaries, compare two time periods, and filter by position, so I can identify patterns and correlate changes with my study work."

**New features for existing graph**:

**a) Date range comparison overlay**:
- Toggle "Compare" mode
- Select two periods
- Overlay both on same axes (different line styles: solid vs. dashed)
- Legend shows which period is which

**b) Session markers**:
- Thin vertical lines at session boundaries
- Optional: color lines by session result (green = winning, red = losing)
- Hover line → tooltip with session summary (duration, hands, won)

**c) Position-filtered graph**:
- Dropdown: "All positions", "BTN only", "BB only", etc.
- Graph shows cumulative results for only hands from selected position
- Instantly reveals: "My BB graph is a steady downslope — I'm losing too much defending blinds"

**d) Annotation markers**:
- User-addable vertical markers with labels
- "Started working on 3-bet ranges" at hand #5000
- "Coaching session #3" at hand #8000
- Stored in settings or a new `annotations` table
- Visual: small flag icon with tooltip text

**e) Confidence interval band**:
- Shaded band around the EV line showing expected variance
- Based on standard deviation of results
- Helps answer: "Is this downswing within normal variance?"
- Computation: ±2 standard deviations of cumulative sum

---

## 3. UI/UX Design

### M3.1 — Stat Trend Sparkline (in Detail Panel)

```
┌──────────────────────────────────────────┐
│  3-Bet — 8.2% (892 / 10,872)            │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │        ╱╲    ╱╲                    │  │
│  │   ╱╲  ╱  ╲╱╱  ╲╱╲   ╱╲  current  │  │
│  │──╱──╲╱───────────────╱──╲─── 8.2% │  │
│  │ ╱    ══════════════════════ 8.5%   │  │ ← benchmark center line (dashed)
│  │╱    ░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  │ ← green zone (benchmark range)
│  │  Jan    Feb    Mar    Apr    May    │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Trend: ↑ +2.1pp over last 3 months     │
└──────────────────────────────────────────┘
```

### M3.1 — Standalone Trends Page

```
┌──────────────────────────────────────────────────────────────────────┐
│  TRENDS                                                               │
│  [Preflop ▾] [3 Months ▾] [+ Add Annotation]                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  VPIP ──── PFR ──── 3-Bet ────                    bb/100 ····│  │
│  │                                                               │  │
│  │  28% ╱╲                                              +10     │  │
│  │  26% ╱  ╲    ╱╲           VPIP                        +5     │  │
│  │  24% ╱    ╲╱╱  ╲──────────                             0     │  │
│  │  22% ─────────────────── PFR ────                     -5     │  │
│  │  10%          3-Bet ─────────────                    -10     │  │
│  │   8% ─────────                                               │  │
│  │       Jan     Feb  ▼  Mar     Apr     May                    │  │
│  │                    │                                          │  │
│  │              "Started 3-bet work"                             │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Summary: VPIP -2.1pp ✅  PFR +0.5pp →  3-Bet +3.8pp ✅            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### M3.2 — Before/After Comparison

```
┌──────────────────────────────────────────────────────────────────────┐
│  COMPARE PERIODS                                                      │
│  Period A: [Jan 1 – Jan 31 ▾]    Period B: [Feb 1 – Feb 28 ▾]       │
│  [Last month vs. previous ▾]                                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Summary: 7 improved · 2 regressed · 12 unchanged                   │
│                                                                      │
│  Stat              │ Jan (A) │ Feb (B) │ Change  │ Status            │
│  ──────────────────┼─────────┼─────────┼─────────┼──────────────     │
│  VPIP              │  26.1%  │  24.3%  │ -1.8pp  │ ✅ improving      │
│  PFR               │  19.8%  │  20.1%  │ +0.3pp  │ → no change       │
│  3-Bet             │   4.2%  │   7.8%  │ +3.6pp  │ ✅ improving      │
│  Fold to 3-Bet     │  71.5%  │  58.2%  │ -13.3pp │ ✅ improving      │
│  Flop C-Bet        │  83.0%  │  67.5%  │ -15.5pp │ ✅ improving      │
│  Attempt to Steal  │  22.0%  │  31.5%  │ +9.5pp  │ ✅ improving      │
│  WTSD              │  34.2%  │  30.1%  │ -4.1pp  │ ✅ improving      │
│  AF                │   2.0   │   2.2   │  +0.2   │ ✅ improving      │
│  W$SD              │  48.5%  │  46.2%  │ -2.3pp  │ ⚠ regressing     │
│  ──────────────────┼─────────┼─────────┼─────────┼──────────────     │
│  Win Rate (bb/100) │   1.2   │   4.8   │  +3.6   │ ✅ improving      │
│  Hands             │  6,200  │  7,202  │ +1,002  │                   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### M3.3 — Session List

```
┌──────────────────────────────────────────────────────────────────────┐
│  SESSIONS                              [This Month ▾] [All Stakes ▾] │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Date      Start  Duration  Hands  Stakes         Won     bb/100     │
│  ─────────────────────────────────────────────────────────────────── │
│  Feb 8     20:15   1h 42m    312   $0.25/$0.50  +18.5bb   +5.9  ██ │
│  Feb 7     22:30   2h 15m    428   $0.25/$0.50  -42.0bb   -9.8  ██ │
│  Feb 7     19:00   1h 10m    215   $0.25/$0.50   +8.2bb   +3.8  ██ │
│  Feb 6     20:45   1h 55m    356   $0.25/$0.50  +22.1bb   +6.2  ██ │
│  Feb 5     21:00   3h 20m    612   $0.25/$0.50  -15.3bb   -2.5  ██ │
│  ─────────────────────────────────────────────────────────────────── │
│  This Month: 12 sessions · 4,180 hands · +45.2bb · +3.2 bb/100     │
│                                                                      │
├──────────────────────────────────────────────────────────────────────┤
│  TIME OF DAY                          SESSION LENGTH                  │
│  ┌──────────────────────────┐        ┌──────────────────────────┐    │
│  │  ██                      │        │        ██                │    │
│  │  ██  ██                  │        │  ██    ██                │    │
│  │  ██  ██  ██              │        │  ██    ██    ██          │    │
│  │  ██  ██  ██  ██          │        │  ██    ██    ██          │    │
│  │  ██  ██  ██  ██  ██      │        │  ██    ██    ██    ██    │    │
│  │  7pm 8pm 9pm 10p 11p 12a│        │  <1h  1-2h  2-3h  3h+   │    │
│  │  +6.2 +5.1 +3.8 -1.2 -3.8│       │  +5.1 +4.2 +1.0  -2.3  │    │
│  └──────────────────────────┘        └──────────────────────────┘    │
│                                                                      │
│  ⚠ Your bb/100 drops from +5.1 to -2.3 after the 2-hour mark       │
│  ⚠ You lose -3.8 bb/100 playing after midnight                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### M3.3 — Calendar View (Stretch)

```
┌──────────────────────────────────────────────────────────────────────┐
│  CALENDAR                                    ◁ January 2026 ▷        │
├──────────────────────────────────────────────────────────────────────┤
│  Mon    Tue    Wed    Thu    Fri    Sat    Sun                        │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                  │
│  │    │ │    │ │ +12 │ │  -8 │ │ +22 │ │    │ │ +15 │                │
│  │    │ │    │ │ ██▓ │ │ ░░░ │ │ ███ │ │    │ │ ██▓ │                │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘                   │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐                  │
│  │ +31 │ │  -5 │ │    │ │ +18 │ │ -42 │ │ +8  │ │    │               │
│  │ ███ │ │ ░░░ │ │    │ │ ██▓ │ │ ▓▓▓ │ │ ██░ │ │    │              │
│  └────┘ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘                   │
│  ...                                                                 │
│                                                                      │
│  January: 22 sessions · 8,450 hands · +92bb · $46 · +2.8 bb/100    │
│  Best day: Jan 5 (+31bb) · Worst day: Jan 12 (-42bb)                │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Green cells = profitable days (intensity = magnitude). Red cells = losing days. Empty cells = no play.

---

## 4. Technical Spec

### M3.1 — Stat Trends Backend

**New endpoint**: `GET /api/reports/trends`

**Query params**:
- `stats` (comma-separated): stat keys to trend (e.g., `vpip,pfr,three_bet`)
- `window` (int, default 500): rolling window size in opportunities
- `stakes` (string, optional)
- `date_from` / `date_to` (string, optional)
- `bucket` (string, default "auto"): "day", "week", "hands_500", "auto"

**Response**:
```json
{
  "stats": {
    "vpip": {
      "points": [
        { "date": "2026-01-01", "hand_number": 0, "value": 25.2, "sample": 500 },
        { "date": "2026-01-08", "value": 24.8, "sample": 500 },
        { "date": "2026-01-15", "value": 23.5, "sample": 500 }
      ],
      "current": 24.1,
      "change_3m": -1.8,
      "benchmark": { "low": 22, "high": 27 }
    },
    "three_bet": {
      "points": [ ... ],
      "current": 8.2,
      "change_3m": 3.8,
      "benchmark": { "low": 7, "high": 10 }
    }
  },
  "annotations": [
    { "date": "2026-01-20", "hand_number": 5200, "text": "Started 3-bet study" }
  ]
}
```

**Backend implementation approach**:

```python
# For each stat, compute rolling average over time
# Option A: Time-bucketed (by day/week)
SELECT
    DATE_TRUNC('week', h.played_at) as week,
    AVG(CASE WHEN hp.vpip THEN 1.0 ELSE 0.0 END) * 100 as vpip,
    COUNT(*) as sample
FROM hand_players hp
JOIN hands h ON hp.hand_id = h.id
WHERE hp.player_id = ? AND h.played_at >= ?
GROUP BY DATE_TRUNC('week', h.played_at)
ORDER BY week

# Option B: Hand-count-bucketed (every N hands)
# Use ROW_NUMBER() to assign sequential numbers, then GROUP BY (row_num / window_size)
```

**Recommendation**: Time-bucketed (by week) for the trends page. Hand-count-bucketed for the sparkline in stat detail (more granular, tied to opportunities not calendar time).

### M3.2 — Before/After Comparison

**No new backend endpoint needed.** Frontend makes two calls to existing `GET /api/stats/hero`:
- Call 1: `?date_from=2026-01-01&date_to=2026-01-31`
- Call 2: `?date_from=2026-02-01&date_to=2026-02-28`

Diff computation in frontend:

```typescript
interface ComparisonRow {
  statKey: string;
  statName: string;
  periodA: { value: number; sample: number };
  periodB: { value: number; sample: number };
  change: number;       // periodB.value - periodA.value
  changePp: string;     // formatted: "+3.6pp" or "-1.8pp"
  status: 'improving' | 'regressing' | 'unchanged';
  significant: boolean; // change > 1pp AND both samples > 200
}
```

Direction logic: compare both periods against benchmarks. If Period B is closer to benchmark center, status = "improving". If further, "regressing". If change < 1pp, "unchanged".

### M3.3 — Session Detection

**New endpoint**: `GET /api/reports/sessions`

**Query params**:
- `stakes` (optional)
- `date_from` / `date_to` (optional)
- `min_hands` (int, default 10): minimum hands for a session to count
- `gap_minutes` (int, default 30): gap threshold for session boundary

**Response**:
```json
{
  "sessions": [
    {
      "id": 1,
      "started_at": "2026-02-08T20:15:00",
      "ended_at": "2026-02-08T21:57:00",
      "duration_minutes": 102,
      "hands": 312,
      "stakes": "$0.25/$0.50",
      "won_bb": 18.5,
      "won_usd": 9.25,
      "bb_per_100": 5.9,
      "ev_bb_per_100": 4.2
    }
  ],
  "summary": {
    "total_sessions": 42,
    "total_hands": 13402,
    "total_won_bb": 142.5,
    "overall_bb_per_100": 3.2
  },
  "time_of_day": [
    { "hour_start": 19, "hour_end": 21, "sessions": 15, "hands": 4200, "bb_per_100": 6.2 },
    { "hour_start": 21, "hour_end": 23, "sessions": 18, "hands": 5800, "bb_per_100": 3.1 },
    { "hour_start": 23, "hour_end": 1,  "sessions": 9,  "hands": 3400, "bb_per_100": -2.8 }
  ],
  "session_length": [
    { "bucket": "<30min", "sessions": 5, "hands": 800, "bb_per_100": 2.1 },
    { "bucket": "30-60min", "sessions": 12, "hands": 2800, "bb_per_100": 5.1 },
    { "bucket": "1-2h", "sessions": 18, "hands": 6200, "bb_per_100": 4.2 },
    { "bucket": "2-3h", "sessions": 5, "hands": 2800, "bb_per_100": 1.0 },
    { "bucket": "3h+", "sessions": 2, "hands": 800, "bb_per_100": -2.3 }
  ]
}
```

**Session detection SQL**:

```sql
-- Step 1: Compute time gaps between consecutive hands
WITH ordered_hands AS (
    SELECT
        h.id, h.played_at, h.stakes,
        hp.won_bb, hp.all_in_ev_bb,
        LAG(h.played_at) OVER (ORDER BY h.played_at) as prev_played_at
    FROM hands h
    JOIN hand_players hp ON h.id = hp.hand_id
    WHERE hp.player_id = ?  -- hero
    ORDER BY h.played_at
),

-- Step 2: Mark session boundaries where gap > 30 minutes
session_boundaries AS (
    SELECT *,
        CASE
            WHEN prev_played_at IS NULL THEN 1
            WHEN EXTRACT(EPOCH FROM (played_at - prev_played_at)) > 1800 THEN 1
            ELSE 0
        END as is_new_session
    FROM ordered_hands
),

-- Step 3: Assign session IDs using cumulative sum of boundaries
session_ids AS (
    SELECT *,
        SUM(is_new_session) OVER (ORDER BY played_at) as session_id
    FROM session_boundaries
)

-- Step 4: Aggregate per session
SELECT
    session_id,
    MIN(played_at) as started_at,
    MAX(played_at) as ended_at,
    COUNT(*) as hands,
    SUM(won_bb) as won_bb,
    SUM(won_bb) / COUNT(*) * 100 as bb_per_100
FROM session_ids
GROUP BY session_id
HAVING COUNT(*) >= ?  -- min_hands threshold
ORDER BY started_at DESC
```

### M3.3 — Calendar View

**New endpoint**: `GET /api/reports/calendar`

**Query params**: `month` (YYYY-MM), `stakes` (optional)

**Response**:
```json
{
  "month": "2026-01",
  "days": [
    { "date": "2026-01-03", "sessions": 2, "hands": 480, "won_bb": 12.5 },
    { "date": "2026-01-04", "sessions": 1, "hands": 215, "won_bb": -8.2 }
  ],
  "summary": {
    "days_played": 22,
    "total_sessions": 38,
    "total_hands": 8450,
    "total_won_bb": 92.0,
    "bb_per_100": 2.8,
    "best_day": { "date": "2026-01-05", "won_bb": 31.0 },
    "worst_day": { "date": "2026-01-12", "won_bb": -42.0 }
  }
}
```

### M3.4 — Annotations Table

**New schema**:

```sql
CREATE TABLE annotations (
    id INTEGER PRIMARY KEY,
    hand_number INTEGER,           -- approximate hand count at annotation time
    created_at TIMESTAMP NOT NULL,
    target_date TIMESTAMP,         -- the date being annotated
    text VARCHAR NOT NULL          -- "Started 3-bet study"
);
```

Small table, no performance concerns. Used by trends page and results graph.

### M3.4 — Position-Filtered Graph

Extend existing `GET /api/reports/graph` with a new query param:
- `position` (string, optional): filter to only hands where hero was in this position

**Implementation**: Add `AND hp.position = ?` to the existing graph query. Minor backend change.

---

## 5. Execution Plan

### Sprint 5 Tasks (M3.1 + M3.2)

**Stat Trend Charts (4-5 days)**:
1. Add `GET /api/reports/trends` endpoint with time-bucketed stat computation
2. Create `TrendChart` component using Recharts (line chart with benchmark zone)
3. Create `StatSparkline` component (mini version for stat detail panel)
4. Create `TrendsPage.tsx` with multi-stat selection and time range picker
5. Add annotation markers (create `annotations` table, CRUD endpoint)
6. Wire sparkline into stat detail panel (depends on M2.1a being done)
7. Add page to sidebar navigation

**Before/After Comparison (2-3 days)**:
1. Create `ComparisonView` component with two date range selectors
2. Create `ComparisonTable` component (stat rows with diff + direction arrows)
3. Add preset period selectors ("Last month vs. previous", etc.)
4. Wire comparison logic (two API calls + frontend diff computation)
5. Add to Trends page as a tab or separate view

### Sprint 7 Tasks (M3.3 + M3.4)

**Session Analytics (5-7 days)**:
1. Add `GET /api/reports/sessions` endpoint with session detection SQL
2. Create `SessionsPage.tsx` with session list table
3. Create time-of-day analysis chart (bar chart)
4. Create session-length analysis chart (bar chart + scatter)
5. Add tilt detection insights (auto-generated text warnings)
6. Add `GET /api/reports/calendar` endpoint
7. Create `CalendarView` component (month grid with colored cells)
8. Add page to sidebar navigation

**Enhanced Results Graph (3-4 days)**:
1. Add position filter to `GET /api/reports/graph`
2. Add position dropdown to graph page
3. Add session boundary markers to graph (vertical lines)
4. Add annotation markers to graph
5. Add date range comparison overlay mode (stretch)
6. Add confidence interval band (stretch)

### Dependencies

- M3.1 sparkline in detail panel depends on M2.1a (stats master-detail layout)
- M3.1 standalone trends page is independent — can be built anytime
- M3.2 is independent — no backend changes needed
- M3.3 is independent — purely new endpoints and pages
- M3.4 enhanced graph extends existing components — can be done incrementally

---

## 6. Testing

### M3.1 — Stat Trends

**Unit tests**:
- Trend computation: verify rolling averages are correct for known data
- Time bucketing: verify weekly/daily grouping produces correct aggregates
- Edge cases: empty periods (gaps in play), single-hand windows, all same value

**Integration tests**:
- Trends endpoint returns data for all requested stats
- Points are chronologically ordered
- Sample counts match expected hand volumes
- Benchmark ranges are included in response

**Visual QA**:
- Chart renders smoothly with real data
- Benchmark zone is clearly visible
- Sparkline is readable at small size (200×60px)
- Annotation markers appear at correct positions

### M3.2 — Comparison

**Unit tests**:
- Diff computation: correct sign and magnitude
- Direction logic: correctly identifies improving vs. regressing vs. unchanged
- Significance threshold: ignores <1pp changes and low-sample stats

**Integration tests**:
- Two API calls return different data for different date ranges
- Summary counts (improved/regressed/unchanged) are correct
- Preset date ranges compute correct boundaries

### M3.3 — Sessions

**Unit tests**:
- Session boundary detection: 30-min gap correctly splits sessions
- Session with gap exactly at threshold (30 min) — test boundary condition
- Single hand "sessions" are filtered out by min_hands
- Time-of-day bucketing handles midnight crossover correctly
- Session length bucketing is correct

**Integration tests**:
- Session list matches expected sessions for known hand data
- Time-of-day analysis shows correct bb/100 per time slot
- Calendar view shows correct daily totals
- Clicking a calendar day shows correct sessions
- Tilt detection insights trigger for known patterns (VPIP spike after big loss)

**Performance tests**:
- Session detection query runs in <1s for 50k hands
- Calendar endpoint is fast (simple daily aggregation)

### Acceptance Criteria

- [ ] Stat trend sparklines appear in stat detail panels (after M2.1a) showing rolling average over time
- [ ] Standalone Trends page shows multi-stat charts with benchmark zones
- [ ] User can add annotation markers to trends chart ("started working on X")
- [ ] Before/After comparison shows two date ranges side-by-side with diff and direction
- [ ] Direction arrows correctly indicate improvement vs. regression relative to benchmarks
- [ ] Session list shows auto-detected sessions with correct duration, hands, and results
- [ ] Time-of-day analysis correctly identifies when the player plays best/worst
- [ ] Session length analysis correctly identifies performance decay in longer sessions
- [ ] Calendar view shows daily results with green/red color coding
- [ ] Results graph supports position filtering
- [ ] Results graph shows session boundary markers
- [ ] All features respect stakes and date range filters
