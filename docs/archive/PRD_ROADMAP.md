# OHM Unified Roadmap — Coaching-Driven Feature Strategy

> Organized by **user impact milestones**, not feature categories.
> Every feature is justified by how real poker coaches and players actually work.

## Document Structure

This roadmap is the **master strategy document**. Each milestone has a detailed PRD in `prd/`:

| File | Milestone | Description |
|------|-----------|-------------|
| `prd/M1_FIND_LEAKS.md` | M1 | Stat benchmarks, leak summary, drift detection |
| `prd/M2_STUDY_SPOTS.md` | M2 | Stats v2 master-detail, new stats, hand review workflow |
| `prd/M3_TRACK_PROGRESS.md` | M3 | Trends, before/after comparison, session analytics |
| `prd/M4_KNOW_OPPONENTS.md` | M4 | Player lookup, population analysis |
| `prd/M5_GO_DEEP.md` | M5 | Board texture, hand strength, sizing, situational views |
| `prd/M6_PLATFORM.md` | M6 | Auto-import, site parsers, Electron, replayer |

The old PRDs (`PRD.md`, `PRD_STATS_V2.md`, `PRD_POPULATION.md`) are **deprecated** — their content has been redistributed into the milestone files above.

---

## Design Philosophy

### Why This Roadmap Exists

The old PRDs were technically thorough but organized by **feature category** (stats, population, hands), while players and coaches think in **workflows**.

This roadmap reorganizes everything around the three questions every poker player asks:

1. **"What am I doing wrong?"** — Find my leaks
2. **"How do I fix it?"** — Study my spots
3. **"Am I getting better?"** — Track my progress

### Research Foundation

This roadmap is informed by deep research into how professional poker coaches run sessions. The top 10 coaching scenarios and the tools that support them were analyzed across:

- **Coaching session types**: database review, hand history review, live sweat, preflop range construction, postflop deep dive, results/variance analysis, steal/blind defense, mental game/tilt, progress tracking, solver study
- **Tracker features coaches use**: PT4 LeakTracker, HM3 Situational Views, Hand2Note Dynamic HUD + Range Research, Leak Buster 465-point analysis, GTO Wizard GTO Reports
- **Training platform UX**: GTO Wizard (EV loss sorting, traffic-light deviations), Upswing Lab (placement quiz, mastery path), PokerCoaching.com (interactive quizzes)
- **Beginner player needs**: what stats reveal the most common leaks, coaching progression paths, self-diagnosis reports

### Core UX Principles

**1. Traffic-light everything.** Every number green/yellow/red at a glance. Users shouldn't need to know that 72% fold-to-3bet is bad — the color tells them instantly.

**2. Click any number to drill down.** No stat should be a dead end. Every number is a hyperlink to supporting hands and sub-breakdowns. This is the universal pattern across PT4, HM3, Hand2Note, and GTO Wizard.

**3. Answer "so what?" not just "what."** Instead of "Fold to 3-Bet: 72%", show "Fold to 3-Bet: 72% (target: 55-65%, cost: ~1.2 bb/100)". Benchmark + estimated impact turns a number into an actionable insight.

**4. Progressive disclosure.** Dashboard shows 5-7 key stats. Stats page shows 30+. Detail panel shows sub-breakdowns. Hand browser shows individual hands. Each layer adds depth without overwhelming.

**5. Default to "what's wrong" sorting.** Leaks sorted by impact. Hands default to biggest losers. Opponents sorted by hands played. Every default view shows the most actionable information first.

**6. The 13x13 matrix is the universal language.** Every solver, every training platform, every coach uses it. One component, many contexts: "what do you open from CO?", "what does villain 3-bet with?", "what does the population play from BTN?"

---

## Current State

### What's Built

| Page | Route | Status |
|------|-------|--------|
| **Upload** | `/` | Drag & drop files/folders/ZIPs, streaming import, progress bar, clear DB |
| **Stats** | `/stats` | H2N-style stat tables with positional columns (EP/MP/CO/BTN/SB/BB), color-coded values, subscript sample sizes |
| **Range** | `/range` | 13x13 hand matrix with color-by (bb/100, EV, frequency, hands), position filter |
| **Results** | `/graph` | Cumulative graph (BB/$, EV, SD/NSD, rake, jackpot lines), stat cards, breakdowns by stakes/month/position |
| **Hands** | `/hands` | Paginated list with filters (position/stakes/result/tags/date), sortable, action abbreviations, detail drawer, tagging, notes |
| **Cash Drop** | `/cash-drop` | Cash drop tracking |

**Backend**: GGPoker Rush & Cash parser, 60+ stat flags, all-in EV, rake/jackpot tracking, rebuild endpoint.
**Architecture**: Parse → Compute → Insert pipeline with site-independent stat flag module.

### What's Planned but Not Built

From PRD.md: 13 new H2N parity metrics, Phase 1 core gap stats (cold call, check-raise, probe bet, IP/OOP splits).
From PRD_STATS_V2.md: Master-detail layout, stat drill-down panels, hand strength evaluation, board texture classification.
From PRD_POPULATION.md: Full population analysis page with position matrices, board texture splits, player segmentation, sizing tells.

---

## The Three User Journeys

Every feature in this roadmap serves one of three journeys:

### Journey A: "What Am I Doing Wrong?" (Find My Leaks)

The first-session problem. A new player imports 5,000 hands and currently sees 30+ numbers with no context. They need to know instantly: what's good, what's bad, and what to fix first.

**The coaching parallel**: This is the Database Review session — the first thing every coach does with a new student. Coach opens the database, compares stats against benchmarks, identifies the top 2-3 leaks, and prioritizes what to fix.

**What the best tools do**:
- Leak Buster: scans 465 potential leak areas, ranks by severity, estimates financial impact
- PT4 LeakTracker: color-coded bars (green/gray/dark gray zones) per stat
- GTO Wizard GTO Reports: red (over-aggressive) / blue (too passive) deviation from GTO baselines

### Journey B: "How Do I Fix It?" (Study My Spots)

The hand review problem. The player knows they fold to 3-bets too much. Now they need to see the actual hands, understand patterns, and develop better responses.

**The coaching parallel**: Hand History Review + Postflop Deep Dive. Coach filters to hands matching the leak, replays each one, discusses alternative lines, shows what hands the player should be calling/raising with.

**What the best tools do**:
- HM3 Situational Views: purpose-built dashboards for CBet, 3-Bet, River, All-In situations
- GTO Wizard Analyzer: sort by EV loss, action filters ("RFI, called 3-bet, cbet flop"), one-click to study mode
- Hand2Note: drill-down from category to specific situation to individual hands

### Journey C: "Am I Getting Better?" (Track My Progress)

The before/after problem. The player has been working on their 3-bet frequency for a month. Did the work pay off?

**The coaching parallel**: Follow-up Database Review + Results Analysis. Coach compares stats from two periods, checks if the targeted leaks improved, reviews the results graph for trajectory changes.

**What the best tools do**:
- Hand2Note Pin: side-by-side report comparison
- GTO Wizard GTO Reports: absolute vs. relative toggle, date range filtering
- No major tracker does strategy drift detection — this is a unique opportunity for OHM

---

## Milestones

### Milestone 1: "The App That Tells You What's Wrong"

**Goal**: A new player imports hands and immediately understands their leaks.
**Coaching scenario**: Database Review (first coaching session).
**Impact**: Highest. This is the difference between "a wall of numbers" and "a tool that helps me improve."

#### M1.1 — Stat Benchmark Layer

Add benchmark ranges and color-coded health indicators to the existing Stats page. No new pages needed — enhance what's there.

**Benchmark Reference Ranges (6-max cash, researched from coaching sources)**:

| Stat | Optimal Range | Leak if Low | Leak if High |
|------|--------------|-------------|--------------|
| VPIP | 22-27% | Too tight, missing value | >30%, playing junk |
| PFR | 19-23% | Passive, limping | Over-aggressive |
| VPIP-PFR Gap | 3-6pp | — | >8pp = limping too much |
| 3-Bet | 7-10% | <4% predictable, only premiums | >12% spewing |
| Fold to 3-Bet | 55-65% | Calling too wide | >72% exploitable |
| 4-Bet | 2-3% | Never 4-betting light | Spewing with bluffs |
| Attempt to Steal | 30-38% | Missing steal opportunities | >45% too wide |
| Fold to Steal | 65-75% | Defending too wide | >80% bleeding blinds |
| Flop C-Bet | 55-70% | Too passive post-raise | >85% auto-cbet |
| Turn C-Bet | 45-60% | One-and-done pattern | Barreling without equity |
| Fold to Flop C-Bet | 45-60% | Floating/calling too wide | >70% surrendering |
| WTSD | 27-32% | Over-folding postflop | >35% calling station |
| W$SD | 50-55% | Arriving at SD with weak hands | >60% only showing nuts |
| WWSF | 45-53% | Too passive, not bluffing enough | >58% over-bluffing |
| AF (per street) | 2.5-3.5 | <2 passive | >5 maniac |
| Open Raise (EP) | 14-18% | Too tight | >22% too wide |
| Open Raise (CO) | 25-32% | Missing value | >40% too wide |
| Open Raise (BTN) | 40-50% | Missing steals | >55% too wide |

**Implementation**:
- Backend: new `GET /api/stats/benchmarks` endpoint returning benchmark ranges per stat, per position
- Or: hardcode benchmarks in frontend as a config object (simpler, faster)
- Frontend: add a thin colored bar or dot next to each stat value in the existing tables
  - Green: within optimal range
  - Yellow: borderline (within 20% of range boundary)
  - Red: outside optimal range (leak detected)
- Add tooltip on hover showing: "Target: 55-65%. You're at 72%. This may be costing you ~1.0 bb/100."

**Effort**: Small. No new data collection. No schema changes. Pure frontend display logic + a config object of benchmarks.

**Positional benchmarks**: Open Raise, Steal, 3-Bet etc. need position-specific ranges. Store as a nested object: `{ stat: { position: { low, high } } }`.

#### M1.2 — Leak Summary Panel

A new panel (top of Stats page, or a new Dashboard tab) that surfaces the top leaks ranked by estimated impact.

**Display**:
```
YOUR TOP LEAKS                                                    13,402 hands

1. ⚠ Fold to 3-Bet: 72% (target: 55-65%)
   You fold to 3-bets significantly more than optimal.
   Estimated cost: ~1.2 bb/100 — about $156/10k hands at NL50
   → Fix: Widen your 3-bet calling range, especially from BTN/CO
   [View 847 hands where you faced a 3-bet →]

2. ⚠ Attempt to Steal: 22% (target: 30-38%)
   You're not stealing blinds often enough from late position.
   Estimated cost: ~0.8 bb/100
   → Fix: Open wider from CO/BTN when folded to you
   [View steal opportunities →]

3. ⚠ Flop C-Bet: 82% (target: 55-70%)
   You're c-betting too frequently, especially on wet boards.
   Estimated cost: ~0.5 bb/100
   → Fix: Check back more often on coordinated boards and multiway
   [View flop c-bet hands →]

✅ 3-Bet: 8.2% (target: 7-10%) — On track
✅ VPIP: 24% (target: 22-27%) — On track
✅ WTSD: 29% (target: 27-32%) — On track
```

**Impact estimation formula**:
- For frequency stats: `impact_bb100 = abs(actual - midpoint_of_range) * weight_factor`
- Weight factors derived from coaching research: preflop leaks have highest impact (they affect every hand), then flop, then later streets
- Suggested weights: VPIP/PFR: 0.15, 3-Bet/Fold-to-3B: 0.10, Steal/Fold-to-Steal: 0.08, C-Bet: 0.06, WTSD/AF: 0.04
- These are rough proxies, not exact EV calculations — but they're directionally correct and massively better than no ranking

**"View hands" links**: Deep link to the hands page with pre-applied filters matching the leak. This bridges Journey A → Journey B.

**Effort**: Medium. Backend needs a leak computation endpoint (or frontend computes from existing stats). Frontend is a new component.

#### M1.3 — Strategy Drift Detection

Monitor rolling windows of key stats and alert when play deviates from baseline. Currently in PRD.md Phase 5 — moving it here because it's technically simple and uniquely valuable.

**How it works**:
1. Compute lifetime baseline stats (player's "A-game" profile)
2. Compute stats over rolling windows (last 500, 1k, 2k, 5k hands)
3. Compare using z-scores: `z = (rolling_mean - lifetime_mean) / (lifetime_stddev / sqrt(window_size))` — denominator is standard error, not raw stddev
4. Flag when |z| > 2.0 (statistically significant deviation)

**Stats to monitor (and what drift means)**:

| Stat | Drift Up | Drift Down |
|------|----------|------------|
| VPIP | Playing too loose (tilt/boredom) | Playing too tight (scared money) |
| PFR | Over-aggression (tilt) | Passivity (fear/fatigue) |
| AF postflop | Spewing (maniac mode) | Calling station mode |
| WTSD | Can't let go, calling too much | Over-folding postflop |
| Fold to 3-Bet | — | Calling too many 3-bets (ego/tilt) |
| C-Bet Flop | Autopilot c-betting | Missing value / checking too much |
| NSD winnings trend | — | Red line falling = folding too much postflop |

**UI options** (pick one):
- **Option A — Dashboard widget**: Stat health indicators (green/yellow/red dots next to each stat on stats page) with tooltip: "Your VPIP increased from 23% to 31% over the last 2000 hands (+3.2σ)"
- **Option B — Trend arrows**: Small ↑↓ arrows next to stats on the stats page, colored green (improving toward benchmark) or red (drifting away)
- **Option C — "A-Game Score"**: Single composite number 0-100 based on how close current play matches baseline. Big number on dashboard.

**Recommendation**: Start with Option B (trend arrows) — smallest UI footprint, immediately useful, composable with the existing stats table.

**Backend**: `GET /api/reports/drift?window=2000`
- Two queries against `hand_players`: lifetime stats vs. last N hands ordered by `played_at`
- Compute means and standard deviations per stat
- Return per-stat z-scores + direction
- No new schema needed — derived from existing flags

**Effort**: Medium. Pure SQL computation + frontend arrows/badges. No parser changes, no schema changes.

**Why this is unique**: No major tracker (PT4, HM3, Hand2Note) has strategy drift detection as a first-class feature. Coaches identify drift manually by comparing time-period stats. Automating this is a genuine differentiator.

---

### Milestone 2: "The App That Helps You Study"

**Goal**: Replicate the core workflow of a coaching hand review session.
**Coaching scenarios**: Hand History Review, Preflop Range Construction, Postflop Deep Dive, Steal/Blind Defense.
**Impact**: High. This is where players spend 80% of their study time.

#### M2.1 — Stats v2: Master-Detail Layout with Click-Through

Redesign `/stats` from full-width stat summary into a **master-detail layout**. Left panel = existing stat tables (squeezed to ~40%). Right panel = context-aware detail when any stat is clicked.

**This is the single biggest UX upgrade in the roadmap.** It transforms the stats page from a wall of numbers into an interactive coaching tool.

Full spec in PRD_STATS_V2.md. Key points:

**Detail panel types**:
1. **Preflop Range Detail** — 13x13 heatmap showing what hands hero actually plays for the selected action + position. Quick stats + filtered hand list below.
2. **Postflop Action Detail** — Bet sizing distribution, board texture splits, hand strength at action, stat trend sparkline, EV of the line (action vs. no-action comparison).
3. **Defensive/Response Detail** — Response distribution (fold/call/raise split), positional breakdown, range heatmap for preflop defense.
4. **Showdown Detail** — Result distribution, positional breakdown, street-reached analysis.

**Why this matters for coaching**: Every coaching session follows this exact flow — coach clicks a stat, sees the supporting data, then drills into specific hands. The master-detail layout IS the coaching interface.

**Phase M2.1a — Layout + Hand List** (do first):
- Refactor StatsPage.tsx into two-panel layout
- Make every stat cell clickable with selected state
- Right panel shows header (stat name, value, sample) + paginated hand list filtered to matching hands
- URL reflects selection: `/stats?detail=open_raise&pos=co`

**Phase M2.1b — Range Detail**:
- Embed 13x13 heatmap in detail panel for preflop stats (reuse existing RangePage component)
- Position tab filtering
- Quick stats below heatmap (range %, total combos)

**Phase M2.1c — Postflop Action Detail**:
- Sizing distribution (requires `pot_before_action` on actions table — see Shared Infrastructure)
- Board texture splits (requires texture classifier — see Shared Infrastructure)
- Hand strength at action (requires hand evaluator — see Shared Infrastructure)

**Phase M2.1d — EV of the Line + Trend**:
- Action vs. no-action EV comparison, broken down by hand strength and board texture
- Stat trend sparkline (rolling average over time)

**Effort**: Large overall, but Phase M2.1a alone is medium and delivers 70% of the value (the click-through and hand list).

#### M2.2 — New Stat Categories

Add the missing stats that every coaching session requires. Two new sections on the left panel:

**Check-Raise section**:
| Stat | Description |
|------|-------------|
| Check-Raise Flop/Turn/River | % hero check-raises (of checks facing a bet) |
| Fold to XR Flop/Turn/River | % hero folds facing a check-raise |

**Probe / Float / Delayed C-Bet section**:
| Stat | Description |
|------|-------------|
| Probe Bet Flop/Turn/River | % hero bets when PFR/aggressor checks |
| Float Flop | % hero calls flop IP (can bet turn if checked to) |
| Delayed C-Bet Turn/River | % hero bets after checking previous street as PFR |

Plus H2N parity metrics from PRD.md Section 3.2.0 (13 metrics): limp-fold, 4-bet-fold, call-4bet, vs cbet by pot type, missed cbet IP/OOP splits.

Plus Phase 1 core gaps from PRD.md Section 3.2.2: cold call, 3-bet call, fold to squeeze, saw flop/turn/river %, win rate by position.

**Effort**: Medium-Large. Requires parser changes (`stat_flags.py`), DB schema additions, stats engine wiring, rebuild.

Full spec in PRD_STATS_V2.md "New Stats" section and PRD.md Sections 3.2.0-3.2.2.

#### M2.3 — Hand Review Workflow

The core loop of every coaching session: tag hands during review → filter to tagged hands → step through them one by one.

**Features**:
- **Keyboard navigation**: ← → to step through hands in the hand browser (currently missing)
- **"Study Queue"**: filter to tagged hands, auto-advance through them
- **"Biggest Losers" auto-filter**: surface hands where hero lost 10-30 BB (not coolers >50bb, not trivial <5bb) — these are the hands where decisions mattered most
- **Action-sequence filtering**: "show me all hands where I opened CO, faced 3-bet, and called" — this is the #1 feature request in coaching (requires querying the `actions` table with sequence matching)
- **Hand export**: copy hand as formatted text for sharing in Discord/study groups, or export to solver format (PioSolver/GTO Wizard input)

**Effort**: Medium. Keyboard nav and biggest-losers filter are small. Action-sequence filtering is medium (backend query logic). Hand export is small.

#### M2.4 — Range Matrix Integration

The 13x13 matrix on `/range` already exists. Integrate it into the coaching workflow:

- **Link from stats page**: clicking "Open Raise" in the stat detail panel opens the range matrix filtered to open raises from that position
- **Benchmark overlay**: show "your actual range" vs. "recommended range" side-by-side or as an overlay
- **Multi-context usage**: same matrix component usable for hero ranges, villain showdown ranges (Milestone 4), and population ranges (Milestone 4)

**Effort**: Small-Medium. Component exists. Integration is routing + passing filters.

---

### Milestone 3: "The App That Shows Your Progress"

**Goal**: Make coaching measurable. Did the work pay off?
**Coaching scenarios**: Results/Variance Analysis, Before/After Progress Tracking, Mental Game/Tilt Detection.
**Impact**: Medium-High. Essential for long-term engagement and coaching accountability.

#### M3.1 — Stat Trend Charts

Rolling averages of key stats over time. Two views:

**a) Sparklines in stat detail panel** (from PRD_STATS_V2):
- Mini line chart showing stat value over time
- X-axis: time (by week or every N hands, auto-scaled)
- Y-axis: stat percentage
- Horizontal reference line at benchmark center
- Rolling window (e.g., last 500 opportunities) to smooth noise

**b) Standalone "Progress" page**:
- Key stats (VPIP, PFR, 3-Bet, Steal, C-Bet, WTSD) plotted on a shared timeline
- Winrate graph overlaid or adjacent for correlation
- Annotation markers for coaching milestones ("started working on 3-bet ranges")

**Effort**: Medium. Backend: query with time bucketing. Frontend: Recharts line charts (library already used for results graph).

#### M3.2 — Before/After Comparison

Select two date ranges and see stats side-by-side with difference column.

**Display**:
```
Stat              Jan 1-31    Feb 1-28    Change
VPIP               26.1%       24.3%     -1.8pp  ✓ improving
3-Bet                4.2%        7.8%     +3.6pp  ✓ improving
Fold to 3-Bet       71.5%       58.2%    -13.3pp  ✓ improving
Flop C-Bet          83.0%       67.5%    -15.5pp  ✓ improving
Win Rate (bb/100)    1.2         4.8      +3.6    ✓ improving
```

Green arrow = moving toward benchmark. Red arrow = moving away. Gray = no significant change.

**Implementation**: Two separate calls to `/api/stats/hero` with different `date_from`/`date_to`, diff computation in frontend.

**Effort**: Small-Medium. No backend changes needed (the API already supports date filters). Frontend is a new comparison component.

#### M3.3 — Session Analytics

Auto-detect sessions and provide per-session analysis. The key coaching scenario this serves is **mental game / tilt detection**.

**Session detection**: For Rush & Cash (continuous dealing), use time gaps. A session boundary = 30+ minute gap between consecutive hands.

**Session list view**:
| Date | Duration | Hands | Stakes | Won (BB) | Won ($) | bb/100 |
|------|----------|-------|--------|----------|---------|--------|

**Session-level insights**:
- **Time-of-day analysis**: Does winrate deteriorate late at night?
- **Session length vs. winrate**: Does performance drop after 2+ hours?
- **Post-loss patterns**: After losing a 100bb+ pot, what happens in the next 20 hands?
- **Stop-loss tracking**: Did the player respect session limits? (user-configurable)

**Tilt detection signals**:
- Session bb/100 suddenly drops below -20
- Hands-per-minute spikes (rushing, autopilot)
- VPIP spikes within a session (playing too many hands after a bad beat)

**Calendar view** (stretch goal): Month grid, each day color-coded green/red by profit. Click day → sessions. Click session → hands. PT4's most loved feature.

**Effort**: Medium-Large. Backend: session detection logic, per-session stat computation. Frontend: session list, calendar view.

#### M3.4 — Enhanced Results Graph

Upgrade the existing results graph with coaching-relevant features:

- **Date range comparison overlay**: Show two periods on the same graph for visual comparison
- **Session markers**: Vertical lines at session boundaries (helps identify tilt sessions)
- **Confidence interval band**: Visual representation of variance around the winrate
- **Position-filtered graph**: "Show me my results graph only from the BB" — instantly reveals positional leaks
- **Annotation markers**: User-addable markers for coaching milestones ("started widening 3-bet range")

**Effort**: Medium. Extends existing Recharts graph component. Backend: minor query additions for position-filtered graphs.

---

### Milestone 4: "The App That Knows Your Opponents"

**Goal**: Turn the hand history database into an opponent intelligence system.
**Coaching scenarios**: Live Sweat (opponent reads), Population Analysis, Exploit Development.
**Impact**: Medium. Prerequisite for advanced play improvement.

#### M4.1 — Player Lookup & Type Classification

**Player search**: Find any player in the database, see their full stat profile.
- Reuse the stats engine with `player_id` instead of hero — same computation, different target
- Mini-stat cards in search results: VPIP/PFR/3B/Hands

**Auto-classification** based on aggregate VPIP/PFR:

| Type | Code | VPIP | PFR | Color |
|------|------|------|-----|-------|
| Nit | NIT | <18% | <14% | Gray |
| TAG | TAG | 18-27% | 14-22% | Blue |
| LAG | LAG | 27-38% | 20-30% | Orange |
| Recreational | REC | >35% | <VPIP×0.6 | Green |
| Maniac | MAN | >38% | >28% | Red |
| Unknown | UNK | — | — | — |

**Player profile page**:
- All stats (reuse stat tables from stats page, scoped to player)
- Head-to-head stats (hero's results specifically vs. this player)
- Hand history with this player
- Color tag + notes (schema exists, needs UI)
- Player type badge with auto-classification

**Implementation**: `GET /api/players` (list/search), `GET /api/players/{id}` (profile), `GET /api/stats/player/{id}` (full stats).

**Effort**: Medium. Backend: new endpoints reusing existing stats engine. Frontend: new page + components.

#### M4.2 — Population Analysis

Full spec in PRD_POPULATION.md. The "how does the average player at my stake play?" feature.

**Page structure** (funnel: most reliable at top, noisier below):
1. **Preflop** — Position matrices (6x6 heatmaps): Open Raise %, 3-Bet %, Fold to 3-Bet %, Cold Call %. Open raise sizing by position. 4-Bet/5-Bet stats.
2. **Flop** — Line frequencies (C-Bet, Fold-to-CB, XR, Donk) by pot type (SRP/3BP) and position (IP/OOP). Board texture splits. Sizing distribution.
3. **Turn** — Double barrel, fold-to-2nd-barrel, probe, delayed cbet. Coarser texture groups.
4. **River** — Aggregate lines only (sample too small for texture splits).
5. **Pot Type Comparison** — SRP vs 3-Bet vs 4-Bet pot tendencies side-by-side.
6. **Showdown & Aggression** — WTSD/WSD by position, AF by street, aggression as bluff proxy.
7. **Player Segmentation** — NIT/TAG/LAG/REC/MAN comparison table.
8. **HU vs Multiway** — How population plays differently in HU vs. multiway pots.

**Statistical confidence framework**: Every cell shows sample size + confidence badge (green ≥1000, yellow 200-999, red <200, hidden <50).

**Filters**: Stakes, date range, min hands per player, exclude hero, player type, pot players (HU/multiway).

**Sizing Tells at Showdown** (stretch): Bet size vs. hand strength heatmap per street. Answers: "When the pool bets small vs large, what do they actually have?"

**Effort**: Large. Requires shared infrastructure (board texture classifier, pot tracking, player type computation). Multiple new endpoints + complex UI.

**Implementation phases** (P1-P7) detailed in PRD_POPULATION.md.

#### M4.3 — Hero vs. Population Comparison

Overlay hero stats against population averages. "How does my play differ from the field?"

This bridges the Leak Finder (Milestone 1) with Population Analysis (Milestone 4):
- Stat health indicators can compare against **population norms** (not just theoretical benchmarks)
- Show where hero deviates from the pool — sometimes deviation is good (exploiting pool tendencies), sometimes it's a leak

**Display**: Add a "vs. Pool" column to the stats table. Or toggle between "vs. Benchmark" and "vs. Population" coloring modes.

**Effort**: Small (once M4.2 is built — it's a query + comparison).

---

### Milestone 5: "The App That Goes Deep"

**Goal**: Advanced analysis features for serious study and competitive edge.
**Coaching scenarios**: Solver Study / GTO Workshop, Bet Sizing Analysis, Decision Analysis.
**Impact**: Medium for the average player, high for dedicated students.

#### M5.1 — Board Texture Analysis

Classify all flops/turns/rivers and cross-reference with all postflop stats.

**Flop texture** (H2N convention):
- Rank: ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc
- Suit: Monocolor, 2tone, Rainbow
- Pairing: Paired / Unpaired

**Turn texture** (relative to flop): Completed draw, Draw-adding, Overcard, Paired board, Brick.

Used by: Stats v2 detail panels (M2.1c), Population Analysis (M4.2).

Full spec in PRD_STATS_V2.md "Shared: Board Texture Classification" and PRD_POPULATION.md Section 2b.

**Effort**: Medium. Python utility + precomputed columns on `hands` table + rebuild.

#### M5.2 — Hand Strength Evaluation

Classify hero's hand at each action point. Two orthogonal dimensions:

**Made hand** (mutually exclusive): Straight Flush → Quads → Full House → Flush → Straight → Set → Trips → Two Pair → Overpair → TPTK → TPWK → Middle Pair → Weak Pair → Overcards → Ace High → No Made Hand.

**Draw flags** (can co-occur): Flush Draw, OESD, Gutshot, Combo Draw, Backdoor Flush, Backdoor Straight, No Draw.

**Composite groups** (for display): Nuts+, Strong, Top Pair, Marginal Made, Draw Only, Air.

Used by: Stats v2 postflop detail panels (M2.1c), Population sizing tells (M4.2 Phase P6).

Full spec in PRD_STATS_V2.md "Shared: Hand Strength Evaluation".

**Effort**: Medium-Large. Requires a poker hand evaluator (consider `treys` or `pokerkit` library). Precompute on insert or compute on-demand for detail queries.

#### M5.3 — Bet Sizing Analysis

Track bet sizes as % of pot across all actions.

**Sizing buckets**: <33%, 33-50%, 50-66%, 66-100%, >100% pot.
**Analysis**: Average sizing by street, position, pot type. Hero sizing vs. population sizing comparison.

**Requires**: `pot_before_action` and `bet_pct_pot` columns on `actions` table (shared infrastructure).

At modern stakes, sizing tells are among the most exploitable patterns. This feature enables:
- "When you bet small on the flop, what do you actually have?"
- "When the population overbets the river, what do they show up with?"

**Effort**: Large. Pot tracking is complex (need to track running pot through each action).

#### M5.4 — Situational Views

Purpose-built dashboards for common spots (HM3's best feature):

- **C-Bet Situations**: flop/turn/river c-bet %, success rate, sizing, by position, by board texture, HU vs multiway, IP vs OOP
- **3-Bet Pots**: 3-bet %, call 3-bet %, fold to 3-bet, by position, outcomes, range heatmap
- **Steal Situations**: steal %, defense responses, post-steal postflop play
- **River Play**: river bet %, check-raise river %, fold to river bet, sizing vs hand strength

Each view is a self-contained analysis dashboard. Unlike the stats page (which shows everything at once), situational views focus on one spot type with maximum depth.

**Effort**: Large. Each view is a significant frontend component + dedicated backend queries.

#### M5.5 — Decision Analysis (EV per Action)

H2N Pro-level feature. For any situation, show the expected value of each possible action.

- **Action Profit**: "When you c-bet flop IP in 3-bet pots, you win +0.82 bb on average"
- **Spot Frequency**: "This situation occurs 15.2 times per 1000 hands"
- **Next Villain Actions**: "After you c-bet flop, villain folds 45%, calls 38%, raises 17%"

This is the most computationally intensive feature — requires joining actions, hand_players, and board_cards with complex filtering and aggregation.

**Effort**: Very Large. Complex backend queries + new frontend components.

#### M5.6 — Custom Stat Creation (SQL-based)

Power user feature. Users write DuckDB SQL against the database, results displayed as new stat columns.

Simpler than H2N's filter builder. Leverages DuckDB's power. Appeals to the technical open-source audience.

**Effort**: Large. Requires SQL editor UI, result rendering, stat persistence.

---

### Milestone 6: "The App That Just Works"

**Goal**: Platform maturity, additional poker sites, packaging.
**Impact**: Adoption and reach.

#### M6.1 — Auto-Import (Watch Folders)

Monitor hand history directories and auto-import new files in the background. Essential for daily use — currently requires manual upload.

**Effort**: Medium. Backend: file watcher (watchdog library), background task.

#### M6.2 — Additional Site Parsers

In priority order:
1. **PokerStars** — largest player base, most requested
2. **Winamax** — large European pool
3. **888poker** — common in regulated markets
4. **PartyPoker** — WPT network

Parser architecture is already extensible (parse → compute → insert pipeline). Each new parser only needs to produce a `ParsedHand` dataclass.

**Effort**: Medium per parser (text parsing work, edge cases, testing).

#### M6.3 — Electron Packaging

Package as a native desktop app for Windows/macOS/Linux. Currently runs as a local web app.

**Effort**: Medium-Large. Electron setup, build pipeline, OS-specific testing.

#### M6.4 — Visual Hand Replayer

Poker-table-style animated replay with chip stacks, pot size, community cards, player actions. Play/pause, step forward/back, speed slider.

Replaces the current text-based hand detail view. Every competitor has this.

**Effort**: Large. Significant frontend component (canvas or SVG-based table rendering).

#### M6.5 — Variance Calculator

Monte Carlo simulation: input winrate + standard deviation, simulate 10k sample paths. Shows probability of downswing depths, expected duration, bankroll requirements.

Pure frontend math, no DB needed. Helps players separate tilt from reality — "is this downswing normal?"

**Effort**: Medium. Frontend math + visualization.

---

## Shared Infrastructure

Several features across milestones depend on shared backend utilities. Build these as needed:

### Board Texture Classifier

```python
def classify_flop(cards: list[str]) -> FlopTexture
def classify_turn_card(turn: str, flop: list[str]) -> TurnTexture
def classify_river_card(river: str, board: list[str]) -> RiverTexture
```

**Used by**: M2.1c (Stats v2 postflop detail), M4.2 (Population board texture splits), M5.1 (Board texture analysis).

**Storage**: Precomputed columns on `hands` table: `flop_texture_rank`, `flop_texture_suit`, `flop_paired`, `turn_texture`, `river_texture`.

### Pot Size Tracker

Compute pot size at each action point during `insert_parsed_hand`.

**Storage**: `pot_before_action DECIMAL` and `bet_pct_pot DECIMAL` on `actions` table.

**Used by**: M2.1c (sizing distribution in stat detail), M4.2 (population sizing), M5.3 (bet sizing analysis).

### Hand Strength Evaluator

```python
def classify_hand(hole_cards: list[str], board: list[str]) -> HandClassification
```

Returns made hand category + draw flags.

**Used by**: M2.1c (hand strength in stat detail), M4.2 Phase P6 (sizing tells at showdown), M5.2 (hand strength analysis).

### Player Type Classifier

```python
def classify_player(vpip: float, pfr: float, hands: int) -> PlayerType
```

**Storage**: `player_type VARCHAR` on `players` table. Recomputed after import.

**Used by**: M4.1 (player lookup), M4.2 (population segmentation).

### Database Schema Additions

All new columns needed across milestones:

```sql
-- hands table
ALTER TABLE hands ADD COLUMN flop_texture_rank VARCHAR;
ALTER TABLE hands ADD COLUMN flop_texture_suit VARCHAR;
ALTER TABLE hands ADD COLUMN flop_paired BOOLEAN;
ALTER TABLE hands ADD COLUMN turn_texture VARCHAR;
ALTER TABLE hands ADD COLUMN river_texture VARCHAR;

-- actions table
ALTER TABLE actions ADD COLUMN pot_before_action DECIMAL;
ALTER TABLE actions ADD COLUMN bet_pct_pot DECIMAL;

-- hand_players table
ALTER TABLE hand_players ADD COLUMN pot_type VARCHAR;       -- srp, 3bet, 4bet, 5bet
ALTER TABLE hand_players ADD COLUMN is_multiway BOOLEAN;
-- Check-raise flags
ALTER TABLE hand_players ADD COLUMN check_raise_flop BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_raise_flop_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_raise_turn BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_raise_turn_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_raise_river BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_raise_river_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_flop BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_flop_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_turn BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_turn_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_river BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_check_raise_river_opp BOOLEAN;
-- Probe / Float / Delayed C-Bet flags
ALTER TABLE hand_players ADD COLUMN probe_bet_flop BOOLEAN;
ALTER TABLE hand_players ADD COLUMN probe_bet_flop_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN probe_bet_turn BOOLEAN;
ALTER TABLE hand_players ADD COLUMN probe_bet_turn_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN probe_bet_river BOOLEAN;
ALTER TABLE hand_players ADD COLUMN probe_bet_river_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN float_flop BOOLEAN;
ALTER TABLE hand_players ADD COLUMN float_flop_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN delayed_cbet_turn BOOLEAN;
ALTER TABLE hand_players ADD COLUMN delayed_cbet_turn_opp BOOLEAN;
ALTER TABLE hand_players ADD COLUMN delayed_cbet_river BOOLEAN;
ALTER TABLE hand_players ADD COLUMN delayed_cbet_river_opp BOOLEAN;
-- H2N parity flags (from PRD.md Section 3.2.0)
ALTER TABLE hand_players ADD COLUMN limp_fold BOOLEAN;
ALTER TABLE hand_players ADD COLUMN four_bet_fold BOOLEAN;
ALTER TABLE hand_players ADD COLUMN call_4bet BOOLEAN;
ALTER TABLE hand_players ADD COLUMN cold_call BOOLEAN;
ALTER TABLE hand_players ADD COLUMN call_3bet BOOLEAN;
ALTER TABLE hand_players ADD COLUMN fold_to_squeeze BOOLEAN;
ALTER TABLE hand_players ADD COLUMN missed_cbet_then_fold BOOLEAN;
ALTER TABLE hand_players ADD COLUMN bet_vs_missed_cbet BOOLEAN;
ALTER TABLE hand_players ADD COLUMN check_fold_vs_missed_cbet BOOLEAN;

-- players table
ALTER TABLE players ADD COLUMN player_type VARCHAR;     -- NIT, TAG, LAG, REC, MAN, UNK
```

After any schema addition: run `/api/import/rebuild` to recompute all flags.

---

## Priority Matrix

| # | Feature | Milestone | Effort | Impact | Dependencies | Do When |
|---|---------|-----------|--------|--------|--------------|---------|
| 1 | Stat benchmark layer (traffic lights) | M1.1 | Small | Very High | None | **Now** |
| 2 | Leak summary panel | M1.2 | Medium | Very High | M1.1 | **Now** |
| 3 | Strategy drift arrows | M1.3 | Medium | High | None | **Now** |
| 4 | Stats v2: click-through + hand list | M2.1a | Medium | Very High | None | **Next** |
| 5 | Keyboard hand nav + biggest losers | M2.3 (partial) | Small | High | None | **Next** |
| 6 | Before/after comparison | M3.2 | Small | High | None | **Next** |
| 7 | New stat flags (check-raise, probe, etc.) | M2.2 | Medium-Large | High | Rebuild | **Next** |
| 8 | Stats v2: range detail panel | M2.1b | Medium | High | M2.1a | After M2.1a |
| 9 | Action-sequence hand filtering | M2.3 | Medium | High | None | After M2.1a |
| 10 | Stat trend sparklines | M3.1 | Medium | Medium-High | M2.1a | After M2.1a |
| 11 | Session analytics | M3.3 | Medium-Large | Medium-High | None | After M3.1 |
| 12 | Player lookup + type classification | M4.1 | Medium | Medium | None | After M2 |
| 13 | Board texture classifier | Shared | Medium | Medium | None | Before M2.1c |
| 14 | Pot size tracker | Shared | Medium | Medium | None | Before M2.1c |
| 15 | Stats v2: postflop detail (sizing+texture+strength) | M2.1c | Large | Medium-High | #13, #14 | After shared infra |
| 16 | Hand strength evaluator | Shared | Medium-Large | Medium | None | Before M2.1c |
| 17 | Auto-import (watch folders) | M6.1 | Medium | Medium | None | Anytime |
| 18 | Population analysis | M4.2 | Large | Medium-High | #12, #13, #14 | After M4.1 |
| 19 | Enhanced results graph | M3.4 | Medium | Medium | None | Anytime |
| 20 | Calendar view | M3.3 | Medium | Medium | M3.3 | After sessions |
| 21 | Situational views | M5.4 | Large | Medium | M2.1c | After M2 complete |
| 22 | PokerStars parser | M6.2 | Medium | Medium | None | Anytime |
| 23 | Bet sizing analysis | M5.3 | Large | Medium | #14 | After shared infra |
| 24 | Visual hand replayer | M6.4 | Large | Medium | None | Anytime |
| 25 | Decision analysis (EV per action) | M5.5 | Very Large | Medium | #14, #16 | After M5.3 |
| 26 | Custom SQL stats | M5.6 | Large | Low-Medium | None | Late |
| 27 | Variance calculator | M6.5 | Medium | Medium | None | Anytime |
| 28 | Electron packaging | M6.3 | Medium-Large | Medium | None | Late |

---

## Recommended Build Order

### Sprint 1: "Traffic Lights" (M1.1 + M1.3)
- Add benchmark config object with per-stat, per-position ranges
- Add green/yellow/red indicators to existing stat cells
- Add trend arrows (drift detection) next to key stats
- **Result**: Stats page instantly goes from "wall of numbers" to "diagnostic tool"

### Sprint 2: "What To Fix" (M1.2 + M2.3 partial)
- Build leak summary panel (top leaks ranked by impact)
- Add "biggest losers" filter to hand browser
- Add keyboard nav (← →) for hand stepping
- **Result**: Player knows what's wrong AND can find the relevant hands

### Sprint 3: "Click Any Stat" (M2.1a)
- Refactor stats page into master-detail layout
- Every stat cell is clickable → opens detail panel with filtered hand list
- URL state for selected stat
- **Result**: The coaching workflow is live — click a leak → see the hands

### Sprint 4: "Range Detail" (M2.1b + M2.4)
- Embed 13x13 heatmap in stat detail panel for preflop stats
- Link between stats page and range page
- Position tab filtering in detail panel
- **Result**: "What hands am I actually opening from CO?" answered in one click

### Sprint 5: "Am I Getting Better?" (M3.1 + M3.2)
- Stat trend sparklines in detail panel
- Before/after date range comparison
- **Result**: Progress is measurable — coaching becomes accountable

### Sprint 6: "New Stats" (M2.2)
- Add check-raise, probe, float, delayed c-bet flags to parser
- Add H2N parity metrics (limp-fold, 4-bet-fold, call-4bet, etc.)
- Add cold call, 3-bet call, fold to squeeze
- Rebuild all hands
- Wire into stats engine and UI
- **Result**: Stat coverage matches competitors

### Sprint 7: "Action Filters + Sessions" (M2.3 + M3.3)
- Action-sequence filtering in hand browser
- Session detection and session list
- Time-of-day analysis
- **Result**: Deep study workflows and tilt detection unlocked

### Sprint 8: "Know Your Opponents" (M4.1)
- Player search and lookup
- Auto player type classification
- Player profile page with stats
- Head-to-head results
- **Result**: Opponent research system operational

### Sprint 9: "Shared Infrastructure" (Board texture + Pot tracking + Hand evaluation)
- Board texture classifier
- Pot-before-action tracking
- Hand strength evaluator
- Rebuild all hands with new columns
- **Result**: Foundation for advanced analysis features

### Sprint 10: "Deep Analysis" (M2.1c-d + M5.1-M5.3)
- Stats v2 postflop detail panels (sizing, texture, hand strength)
- EV of the line analysis
- Board texture cross-referencing
- Bet sizing analysis
- **Result**: Analysis depth matches or exceeds HM3/H2N

### Sprint 11+: "Population + Power Features" (M4.2 + M5.4-M5.6)
- Full population analysis page
- Situational views
- Decision analysis
- Custom stats
- **Result**: Competitive feature parity with professional tools

---

## Navigation Structure (Proposed)

Current sidebar:
```
♠ OHM
  Upload
  Stats
  Range
  Results
  Hands
  Cash Drop
```

Proposed (after all milestones):
```
♠ OHM

PLAY
  Upload
  Cash Drop

ANALYZE
  Dashboard          ← NEW (M1.2: leak summary + drift + quick stats)
  Stats              ← Enhanced (M1.1: benchmarks, M2.1: master-detail)
  Range              ← Existing (integrated with stats detail)
  Results            ← Enhanced (M3.4: comparison, sessions)
  Hands              ← Enhanced (M2.3: action filters, keyboard nav)

OPPONENTS
  Players            ← NEW (M4.1: search, profiles, classification)
  Population         ← NEW (M4.2: pool tendencies)

PROGRESS
  Trends             ← NEW (M3.1: stat trends over time)
  Sessions           ← NEW (M3.3: session list, calendar)
```

**Note**: Don't add all nav items upfront. Add them as features are built. Start by enhancing existing pages (Stats, Hands, Results) before creating new ones.

---

## Competitive Positioning

| Feature | H2N | HM3 | PT4 | GTO Wizard | OHM (planned) |
|---------|-----|-----|-----|------------|---------------|
| Stat benchmarks / leak finder | ✅ | ✅ LeakTracker | ✅ LeakBuster | ✅ GTO Reports | ✅ M1.1-M1.2 |
| Strategy drift detection | ❌ | ❌ | ❌ | ❌ | ✅ M1.3 (unique!) |
| Click-through stat detail | ✅ | ✅ Situational | ✅ My Reports | ✅ Analyzer | ✅ M2.1 |
| 13x13 range matrix | ✅ (paid) | ❌ | ❌ | ✅ | ✅ Already built |
| Before/after comparison | ✅ Pin | ❌ | ❌ | ✅ Date filter | ✅ M3.2 |
| Session analytics | ❌ | ✅ Basic | ✅ Basic | ❌ | ✅ M3.3 |
| Population analysis | ✅ (paid $49/mo) | ❌ | ❌ | ❌ | ✅ M4.2 (free!) |
| Player classification | ✅ | ✅ NoteCaddy | ✅ | ❌ | ✅ M4.1 |
| Board texture analysis | ✅ | ✅ | ✅ | ✅ | ✅ M5.1 |
| Hand strength at action | ✅ | ✅ | ✅ | ✅ | ✅ M5.2 |
| Bet sizing analysis | ✅ | ✅ | ✅ | ✅ | ✅ M5.3 |
| Decision analysis (EV) | ✅ (paid) | ❌ | ❌ | ✅ | ✅ M5.5 |
| Custom stats | ✅ Complex | ✅ HMQL | ✅ Custom | ❌ | ✅ M5.6 (SQL) |
| Open source | ❌ | ❌ | ❌ | ❌ | ✅ |
| Free | ❌ $15-39/mo | ❌ $100 | ❌ $40-110 | ❌ $50/mo | ✅ |

**OHM's moat**: Free + open source + strategy drift detection (unique) + population analysis (H2N charges $49/mo for this) + coaching-oriented UX (benchmarks, leak ranking, progress tracking).

---

## References

### Coaching Research Sources

- BlackRain79 — Database review methodology, session review, red line analysis
- SplitSuit — Hand review process, weekly study guide, common leaks
- GTO Wizard Blog — GTO Reports, practice mode, fixing leaks, preflop morphology
- Smart Poker Study — Leak finder process, 28-day skill plan, tilt control
- MyPokerCoaching — Database review, essential statistics, bankroll management
- PokerCoaching.com — Learning paths, interactive quizzes, coaching structure
- Upswing Poker — Lab features, exploit strategies, study techniques
- Hand2Note — Reports, Range Research, dynamic HUD, essential postflop stats
- Poker Copilot — VPIP/PFR statistics, beginner stat reference
- Leak Buster — 465-point leak analysis, severity scoring, profit simulation
- BBZ Poker — MTT leak finder, marked hand study methodology
- HoldemManager — Situational Views (CBet, 3-Bet, River), Knowledge Base
- PokerTracker — Custom reports, filters, LeakTracker, EV graphs

### Benchmark Sources

- Run It Once forums — winning reg stat profiles
- FreeBetRange — 6-max preflop opening ranges
- 888poker — opening range charts by position
- Komunitas Poker — leak finder with stat benchmarks
- Hand2Note — essential postflop stat ranges

### Related PRDs

- `PRD.md` — Original product spec, stat inventory, API endpoints, phase checklist
- `PRD_STATS_V2.md` — Stats page master-detail redesign, new stat categories, hand strength evaluation, board texture classification
- `PRD_POPULATION.md` — Population analysis page, position matrices, player segmentation, sizing tells
