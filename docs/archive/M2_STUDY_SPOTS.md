# Milestone 2: "The App That Helps You Study"

> **Goal**: Replicate the core workflow of a coaching hand review session.
> **Coaching scenarios**: Hand History Review, Preflop Range Construction, Postflop Deep Dive, Steal/Blind Defense.
> **Impact**: High. This is where players spend 80% of their study time.

---

## 1. Research

### Why This Is Milestone 2

After Milestone 1 ("The App That Tells You What's Wrong"), the player knows their leaks. Now they need to study them. Every poker coaching engagement follows the same progression:

1. **Database Review** (M1) -- identify leaks from aggregate stats
2. **Hand History Review** (M2) -- drill into specific hands matching the leak
3. **Pattern Recognition** (M2) -- see what hands you play, what boards you bet, what sizing you use
4. **Fix Development** (M2) -- build better ranges and strategies

This milestone transforms the Stats page from a read-only summary into an interactive coaching tool with drill-down, and adds the missing stat categories that every coaching session requires.

### Coaching Sessions This Milestone Serves

**Hand History Review**: The most common coaching session type. Coach opens the student's tracker, clicks on a stat (e.g., "Fold to 3-Bet"), sees the supporting hands, and walks through them one by one. The student learns to recognize patterns and develop better responses.

**Preflop Range Construction**: Coach clicks "Open Raise" from a specific position, sees the 13x13 heatmap of what the student actually opens, compares it to a target range, and identifies hands to add or remove.

**Postflop Deep Dive**: Coach clicks "C-Bet Flop", sees the bet sizing distribution, board texture splits, and hand strength breakdown. Identifies patterns like "you always c-bet on monotone boards" or "you never bet with bottom pair and a flush draw."

**Steal/Blind Defense**: Coach clicks "Fold to Steal" from BB, sees the response distribution (fold/call/3-bet split), the range heatmap of what's being defended, and the EV of each response.

### The Hand Explorer Is the Universal Destination

The most important UX pattern from Hand2Note and HM3: **every drill-down leads to the same hand explorer**. When a coach clicks on any stat -- VPIP, C-Bet Flop, Fold to 3-Bet, WTSD -- the destination is always a filtered hand list where you can click into individual hands and step through them. Analysis widgets (range heatmaps, sizing distributions, board texture splits) are compact summaries above the hand list, not separate panel types.

This is the proven pattern because:
1. **Hands are the atomic unit of study.** Stats tell you what's wrong; hands show you why. The hand is always where insight happens.
2. **One destination reduces cognitive load.** The user always knows where they'll end up: a hand list they can click through. The analysis widgets are bonus context, not a different mode.
3. **HandDrawer is already built.** OHM's hand detail drawer (keyboard nav, tagging, notes, full action replay) becomes reusable from any drill-down context.
4. **Analysis grows incrementally.** Start with just the hand list (M2.1b), add widgets above it (M2.1c/d). Every phase delivers a working drill-down experience.

### How Coaches Use Hand Review

The universal coaching workflow:

1. **Tag hands during play or review** -- mark spots for later study (already built in OHM)
2. **Filter to a specific spot** -- "show me all hands where I opened CO and faced a 3-bet" (action-sequence filtering)
3. **Step through hands one by one** -- keyboard navigation (not yet built)
4. **Identify patterns** -- "I always fold ATs here" or "I never check-raise on wet boards"
5. **Develop fixes** -- build a better range or adjust frequencies

### What Competitor Tools Do

**HM3 Situational Views**: Purpose-built dashboards for CBet, 3-Bet, River, All-In situations. Each view shows the stat frequency, sizing distribution, and result breakdown for that specific spot. The click-through from aggregate stat to situational dashboard is the core UX pattern.

**GTO Wizard Analyzer**: Sort hands by EV loss. Action filters like "RFI, called 3-bet, cbet flop" narrow down to exact spots. One-click to study mode. This is the gold standard for action-sequence filtering.

**Hand2Note Drill-Down**: Statistics page shows aggregate stats. Clicking any stat opens a filtered hand list with compact analysis summaries, then clicking a hand opens the full replay. The hand explorer is always the final destination -- not a bespoke panel per stat type. This two-level drill-down (stat -> hand explorer -> hand replay) is the model OHM follows.

### Study Group Formats

Poker study groups follow a consistent format:
- **Hand sharing**: Players share hands in Discord/forums as formatted text or solver input
- **Spot-focused review**: "This week we're reviewing c-bet spots on monotone boards"
- **Range comparison**: "Here's what I actually open from CO" (shown as 13x13 grid)
- **Result review**: "I lost the most money in 3-bet pots OOP"

The hand export feature in M2.3 directly serves this workflow. The master-detail layout makes it possible to gather the data needed for study group discussions.

### Research Sources

Coaching research from: BlackRain79 (database review methodology), SplitSuit (hand review process, weekly study guide), GTO Wizard Blog (action filters, EV loss sorting), Smart Poker Study (leak finder process), Hand2Note (range research, drill-down statistics), HoldemManager (Situational Views knowledge base), PokerTracker (custom reports, filters).

---

## 2. Product Design

### M2.1a -- Stats v2: Master-Detail Layout with Click-Through (DONE)

**What**: Redesign `/stats` from a full-width stat summary into a master-detail layout. Left panel keeps the existing stat tables (squeezed to ~40% width). Right panel opens a context-aware detail view when any stat is clicked.

**This is the single biggest UX upgrade in the roadmap.** It transforms the stats page from a wall of numbers into an interactive coaching tool.

**Status: Implemented.** The master-detail layout is live with:
- Left panel (~42%) with all stat sections, independently scrollable
- Right panel (~58%) with stat header, position tabs, and a basic hand list
- Every stat cell is clickable with selected state (indigo highlight)
- URL reflects selected stat: `/stats?detail=open_raise&pos=co`
- Responsive: side-by-side on wide screens, Sheet slide-over on narrow
- Backend: `GET /api/stats/detail/{stat_key}/hands` with stat registry (60+ stat keys)

**Current detail panel limitations** (addressed in M2.1b/c/d):
- Hand list shows only 6 columns: Hand ID, Position, Cards, Action (check/cross), Result, Stakes
- No board cards, no action sequences, no street-by-street information
- No HandDrawer integration -- can't click into individual hands
- No analysis widgets (no range heatmap, no sizing distribution, no response splits)
- No "Open in Hand Explorer" link

### M2.1b -- Embedded Hand Explorer

**What**: Replace the simplified 6-column hand table in the stat detail panel with a condensed version of the HandsPage table, and integrate HandDrawer for individual hand drill-down. Enrich the backend endpoint to return board cards and action sequences.

**This transforms the detail panel from a list of hand IDs into a real hand explorer.** The user can see preflop cards, board runout, key actions, and result at a glance -- then click into any hand for the full replay.

**User stories**:
- "As a player studying my leaks, I want to see board cards and action sequences when I drill into a stat, so I can spot patterns (e.g., I always c-bet on Ace-high boards)."
- "As a player, I want to click any hand in the stat detail list and see the full hand replay in the drawer, so I can study it without leaving the stats page."
- "As a player, I want to use keyboard arrows to step through filtered hands, so I can efficiently review many hands matching a specific stat."
- "As a player, I want to open the full hand explorer pre-filtered to this stat, so I can use the hand browser's full filtering and sorting."

**Requirements**:

**Condensed hand table** (7 columns for 58% panel width):

| Column | Width | Content |
|--------|-------|---------|
| Action | 24px | Icon: check (green) if action taken, cross (muted) if opportunity missed |
| Cards | 48px | Hero hole cards (CardPair component) |
| PF Actions | flex | Preflop action sequence (same format as HandsPage: R2 C1 etc.) |
| Board | 120px | Flop (3 cards) + turn + river inline, compressed |
| Key Actions | flex | Most relevant street's action sequence (flop for postflop stats, preflop for preflop stats) |
| Result | 56px | Won/lost in BB, green/red colored |
| Date | 56px | Relative date (2h ago, Jan 15) |

- Rows are clickable -- clicking opens HandDrawer with full hand replay
- Selected row gets highlighted background
- Keyboard navigation: up/down arrows move selection, Enter opens drawer
- HandDrawer reused as-is (same component from HandsPage -- pass handId + callbacks)

**"Open in Hand Explorer" link**: At the top of the hand list, a link that opens `/hands?stat_key=open_raise&pos=CO` (pre-filtered to this stat's matching hands). This lets the user switch to the full hand browser with all its filters and sorting.

**Backend enrichment**: Extend `GET /api/stats/detail/{stat_key}/hands` response to include:
- `board_flop`: list of 3 card strings (or empty)
- `board_turn`: card string or null
- `board_river`: card string or null
- `preflop_actions`: list of ActionItem (reuse existing format)
- `key_street_actions`: list of ActionItem for the stat's primary street
- `all_in_ev_bb`: for EV diff display

This requires extracting the `_parse_actions_from_raw` function from `hands.py` to a shared module (`backend/app/action_parser.py`) so both the hand browser and stat detail endpoints can use it.

**"Open in Hand Explorer" backend support**: Add optional `stat_key` query parameter to `GET /api/hands` that applies the stat registry's SQL filters. This lets the hand browser show exactly the same hands as the stat detail panel.

### M2.1c -- Analysis Summary Widgets

**What**: Add compact analysis widgets above the hand explorer in the stat detail panel. Widgets are conditional by stat type -- not separate panel types, but interchangeable components that render based on what's relevant for the selected stat.

**This is informational context, not the main content.** The hand explorer remains the primary interaction. Widgets are compact, collapsible, and positioned above the hand list.

**User stories**:
- "As a player, I want to see a positional mini-bar chart when I click a positional stat, so I can quickly see which positions are leaking."
- "As a player studying my blind defense, I want to see the fold/call/raise response distribution above the hand list, so I can evaluate my overall frequencies before drilling into specific hands."
- "As a player studying my preflop ranges, I want to see a range heatmap showing which combos I play, so I can compare my actual range to my target."
- "As a player, I want to click a widget row (e.g., 'Fold' in the response distribution) to filter the hand list below to only those hands, so I can study a specific subset."

**Widget types** (each renders conditionally based on stat metadata):

#### 1. Positional Mini-Bar

- **Shows for**: All stats with `isPositional: true`
- **Content**: Horizontal bars showing stat % per position (EP/MP/CO/BTN/SB/BB)
- **Height**: ~60px compact
- **Interactive**: Clicking a position bar filters the hand list to that position
- **Data source**: Already available from `/api/stats/hero` positional breakdown

#### 2. Response Distribution

- **Shows for**: Defensive stats (fold_to_3bet, fold_to_cbet_*, fold_to_steal, etc.)
- **Content**: Horizontal stacked bar showing Fold / Call / Raise split with percentages
- **Height**: ~40px
- **Interactive**: Clicking a response segment filters the hand list to that response type
- **Data source**: New field in `/api/stats/detail/{stat_key}/hands` response: `response_distribution`

#### 3. Range Heatmap (Preflop Stats)

- **Shows for**: Preflop action stats (vpip, pfr, open_raise, three_bet, etc.)
- **Content**: Compact 13x13 grid (reuse existing RangeChart from `/range` page)
- **Height**: ~200px, collapsible
- **Quick stats row**: Total combos, range %, avg raise size
- **Interactive**: Clicking a cell filters the hand list to that combo
- **Data source**: Reuse `/api/stats/range` with stat-specific filtering, or add range data to the detail endpoint

#### 4. Trend Sparkline

- **Shows for**: All stats
- **Content**: Mini line chart showing rolling stat value over time
- **Height**: ~50px
- **Reference line**: Overall average as horizontal line
- **Data source**: New endpoint `GET /api/stats/detail/{stat_key}/trend`

**Widget layout**: Widgets stack vertically above the hand list in a collapsible section. Default collapsed for mobile, expanded for desktop. Total widget zone height capped at ~40% of panel height to ensure the hand list is always visible.

**Stat type → widget mapping**:

| Stat Category | Widgets Shown |
|---------------|---------------|
| Preflop action (vpip, pfr, open_raise, 3-bet, etc.) | Positional mini-bar + Range heatmap + Trend sparkline |
| Preflop defense (fold_to_3bet, fold_to_4bet, etc.) | Positional mini-bar + Response distribution + Range heatmap + Trend sparkline |
| Steal (steal, vs_steal_*) | Positional mini-bar + Response distribution (for defense) + Trend sparkline |
| Postflop action (cbet_*, donk_bet_*, etc.) | Positional mini-bar + Trend sparkline |
| Postflop defense (fold_to_cbet_*, etc.) | Positional mini-bar + Response distribution + Trend sparkline |
| Showdown (wtsd, wsd, wwsf) | Positional mini-bar + Trend sparkline |

### M2.1d -- EV & Advanced Analysis Widgets

**What**: Add EV comparison (action vs no-action) and stat trend with confidence intervals. Defer heavy infrastructure (board texture classifier, hand strength evaluator, pot size tracking) to a future milestone.

**User stories**:
- "As a player, I want to see whether my c-bets are more profitable than checking, so I can adjust my c-bet frequency."
- "As a player, I want to see how my c-bet frequency has changed over the last month, so I can track whether the changes I made are sticking."

**New widgets**:

#### 1. EV Comparison (Action vs No-Action)

**Overall EV comparison**:
```
               |   Action    |  No Action  |
---------------+-------------+-------------|
Avg result     |  +0.82 bb   |  +0.31 bb   |
Hands          |     650     |     350     |
```

**How it applies to each stat type**:

| Stat clicked | "Action taken" | "Action not taken" |
|---|---|---|
| C-Bet | Hero bet (cbetting) | Hero checked (missed cbet) |
| 3-Bet | Hero 3-bet | Hero called or folded |
| Open Raise | Hero raised | Hero folded or limped |
| Fold to C-Bet | Hero folded | Hero called or raised |
| Check-Raise | Hero check-raised | Hero check-called or check-folded |
| Steal | Hero attempted steal | Hero folded from steal position |

**Caveats** (shown as info tooltip in UI):
- **Not causal**: Betting with strong hands and checking weak ones naturally makes bet-EV higher. The insight is in the *direction within each hand strength/texture subset*, not the overall numbers.
- **Selection bias**: Compares outcomes of your actual decisions, not a hypothetical optimal strategy.
- **Variance**: Individual hand results are high variance. Cells with < 50 hands are greyed out. Use all-in EV (`all_in_ev_bb`) where available to reduce noise.
- **Minimum sample**: Each row needs 50+ observations in both columns to be meaningful. Show confidence badge per row.

**Data source**: Computable from existing `won_bb` + `action_taken` fields in the stat detail hands response. No new infrastructure needed -- just aggregate in the frontend or add a lightweight summary to the backend response.

#### 2. Enhanced Trend with Confidence Intervals

- Extends the sparkline from M2.1c with rolling confidence bands
- Shows 95% CI for the rolling stat value
- Window size configurable (default: 500 hands)

### Future: Rich Analysis Widgets (Depends on M5 Infrastructure)

The following analysis widgets require shared infrastructure fully specified in **M5_GO_DEEP.md**. They are **not part of M2** -- M2 ships with the widgets that don't require heavy infrastructure (positional bar, response distribution, range heatmap, trend sparkline, EV comparison). When M5 infrastructure lands, these widgets slot into the same universal panel above the hand explorer.

**Board Texture Breakdown** (depends on M5.1: Board Texture Classification):
- Stat frequency broken down by flop texture (ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn/Disc, 8-2 Conn/Disc) + suit structure + pairing
- Shows: stat %, avg sizing, fold equity, avg EV per texture category
- Clicking a texture row filters the hand list below
- Full spec: M5_GO_DEEP.md §M5.1 (classifier code, schema columns, backfill)

**Hand Strength Breakdown** (depends on M5.2: Hand Strength Evaluation):
- What hero had when taking/not-taking the action: Nuts+, Strong, Top Pair, Marginal Made, Draw Only, Air
- Shows: count, % of actions, avg result, win rate per composite group
- Draw flags shown as tags (flush draw, OESD, gutshot, combo draw)
- Clicking a strength row filters the hand list below
- Full spec: M5_GO_DEEP.md §M5.2 (14 made hand categories, 6 draw flags, composite groups, evaluator code)

**Bet Sizing Distribution** (depends on M5.3: Bet Sizing Analysis):
- Horizontal bars showing what % of bets fall in each bucket: <33%, 33-50%, 50-66%, 66-100%, >100% pot
- Average sizing as % of pot
- Full spec: M5_GO_DEEP.md §M5.3 (pot tracking, sizing buckets, computation code)

**EV by Hand Strength & Board Texture** (depends on M5.1 + M5.2 + M5.5):
- Cross-reference EV comparison with hand strength and board texture
- Shows: EV when betting vs checking, broken down by hand strength category and by texture category
- The most powerful leak-finding tool -- answers "which subsets of my decisions are profitable vs costly?"
- Full spec: M5_GO_DEEP.md §M5.5 (Decision Analysis: Action Profit)

**Execution order**: M5.1/5.2/5.3 shared infrastructure can be built in parallel with M2.1b/c/d. Once the infrastructure lands, adding these widgets to M2's universal panel is 3-5 days of frontend work (the widget zone and hand list filtering are already built by M2.1c).

### M2.2 -- New Stat Categories

Add the missing stats that every coaching session requires. This covers three sources: new stat sections from PRD_STATS_V2, H2N parity metrics from PRD Section 3.2.0, and Phase 1 core gap stats from PRD Section 3.2.2.

**User stories**:
- "As a player, I want to see my check-raise frequency per street, so I can evaluate whether I'm check-raising enough or too much."
- "As a player, I want to see my probe bet and delayed c-bet frequencies, so I can evaluate my aggression when the preflop raiser shows weakness."
- "As a player, I want H2N-comparable stats like limp-fold, 4-bet-fold, and cold call, so I can perform the same analysis that coaching content references."

#### New Left Panel Section: Check-Raise

| Stat | Description | Display |
|------|-------------|---------|
| **Check-Raise Flop** | % hero check-raises on flop (of checks facing a bet) | Street table [Flop, Turn, River] |
| **Check-Raise Turn** | % hero check-raises on turn | |
| **Check-Raise River** | % hero check-raises on river | |
| **Fold to XR Flop** | % hero folds facing a check-raise on flop | Street table [Flop, Turn, River] |
| **Fold to XR Turn** | % hero folds facing a check-raise on turn | |
| **Fold to XR River** | % hero folds facing a check-raise on river | |

Detail panel: Universal panel with positional mini-bar + trend sparkline. Fold to XR also shows response distribution.

#### New Left Panel Section: Probe / Float / Delayed C-Bet

| Stat | Description | Display |
|------|-------------|---------|
| **Probe Bet Flop** | % hero bets flop when PFR/aggressor checks (OOP or IP) | Street table [Flop, Turn, River] |
| **Probe Bet Turn** | % hero bets turn when PFR checks | |
| **Probe Bet River** | % hero bets river when PFR checks | |
| **Float Flop** | % hero calls flop IP AND bets/raises turn when checked to (multi-street: requires flop IP call + turn aggression after check) | Single value |
| **Delayed C-Bet Turn** | % hero bets turn after checking flop as PFR | Single value |
| **Delayed C-Bet River** | % hero bets river after checking turn as PFR | Single value |

Detail panel: Universal panel with positional mini-bar + trend sparkline.

#### H2N Parity Metrics (from PRD Section 3.2.0)

13 metrics needed for exact H2N layout parity:

| # | Metric | Section | OHM Status | What's Needed |
|---|--------|---------|------------|---------------|
| 1 | 4-Bet Range | Preflop right | **NEW** | `4bet_count / total_hands * 100` (derived, no parser change) |
| 2 | Limp-Fold | Preflop right | **EXISTS** | `limp_fold` already in stat_flags.py -- wire into stats engine display |
| 3 | 4-Bet-Fold | Preflop right + Steal | **EXISTS** | `four_bet_fold` already in stat_flags.py -- wire into stats engine display |
| 4 | Call 4-Bet | Preflop right | **EXISTS** | `call_4bet` already in stat_flags.py -- wire into stats engine display |
| 5 | 4-Bet-Fold (steal) | Steal | **NEW** | Reuse `four_bet_fold` + steal context |
| 6 | Donk Bet Turn/River | Postflop left | Wire up | Columns exist in DB, wire into stats engine |
| 7 | vs C-Bet Fold/Call/Raise by pot type | Postflop right | **PARTIAL** | `call_cbet_flop`, `raise_cbet_flop` already in stat_flags.py -- need `pot_type VARCHAR` column + pot-type split in stats engine |
| 8 | Missed C-Bet IP/OOP split | Missed C-Bet left | **NEW** | Derive from position (no parser change) |
| 9 | Missed C-Bet -> Fold | Missed C-Bet left | **NEW** | `missed_cbet_then_fold BOOLEAN` flag |
| 10 | vs Missed C-Bet (probe bet) | Missed C-Bet right | **PARTIAL** | `vs_missed_cbet_flop_opp` already in stat_flags.py -- need `bet_vs_missed_cbet BOOLEAN` flag |
| 11 | vs Missed C-Bet IP/OOP | Missed C-Bet right | **NEW** | Derive from position |
| 12 | Check-Fold vs Missed C-Bet | Missed C-Bet right | **NEW** | `check_fold_vs_missed_cbet BOOLEAN` flag |
| 13 | Steal positional (SB/BB defense) | Steal right | Wire up | Already computed, make positional |

#### Phase 1 Core Gap Stats (from PRD Section 3.2.2)

Stats that all three competitors (H2N, HM3, PT4) have and OHM lacks:

**New Preflop Stats**:

| Stat | Description | DB Column Needed | Parser Change |
|------|-------------|------------------|---------------|
| Cold Call | Call a raise without having voluntarily put money in preflop (excludes BB calling) | `cold_call BOOLEAN` | Track calls of raises when player hasn't acted yet |
| RFI (Raise First In) | Alias for open_raise, standard naming used by all 3 tools | Rename `open_raise` to `rfi` or alias | Display change only |
| 3-Bet Call | Called a 3-bet (vs fold/4-bet when facing 3-bet) | `call_3bet BOOLEAN` | Track in preflop aggression state machine |
| Fold to Squeeze | Folded when facing a squeeze | `fold_to_squeeze BOOLEAN` | Track squeeze detection + response |

**New Postflop Stats**:

| Stat | Description | DB Column Needed | Parser Change |
|------|-------------|------------------|---------------|
| Check-Raise Flop/Turn/River | Check then raise on same street | `check_raise_flop/turn/river BOOLEAN`, `check_raise_flop/turn/river_opp BOOLEAN` | Track check-then-raise sequences per street |
| Probe Bet Flop/Turn/River | Bet into preflop raiser when they checked | `probe_bet_flop/turn/river BOOLEAN` | Track when non-PFR bets after PFR checks |
| Bet When Checked To | Bet when action checked to you | `bet_when_checked_to_flop/turn/river BOOLEAN` | Track check-then-bet by next actor |
| Donk Bet Turn/River | Columns exist in DB but not in stats engine | Already in schema | Wire up in `stats_engine.py` |
| Float Flop | Call flop bet in position AND then bet/raise turn when checked to. Both conditions required -- just calling IP is not a float. Denominator = IP flop calls where turn checks to hero. | `float_flop BOOLEAN` | Multi-street tracking (flop call IP + turn bet when checked to) |

**New Showdown Stats**:

| Stat | Description | Formula |
|------|-------------|---------|
| Saw Flop % | % of hands that saw the flop | `saw_flop / total_hands` |
| Saw Turn % | % of hands that saw the turn | `saw_turn / total_hands` |
| Saw River % | % of hands that saw the river | `saw_river / total_hands` |

**IP/OOP Breakdowns**:
All postflop stats (C-bet, fold to C-bet, check-raise, aggression) should have IP vs OOP splits, not just positional. Requires grouping CO/BTN/MP as IP and EP/SB/BB as OOP relative to opponent.

#### Color Coding for New Stats

| Stat | Green | Red | Yellow | Blue |
|------|-------|-----|--------|------|
| Check-Raise Flop | 8-14% | >20% | -- | <5% |
| Check-Raise Turn | 8-14% | >20% | -- | <5% |
| Probe Bet | 25-40% | >55% | -- | <20% |
| Delayed C-Bet | 30-50% | >65% | -- | <20% |
| Float | 20-35% | >45% | -- | <15% |

### M2.3 -- Hand Review Workflow

The core loop of every coaching session: tag hands during review, filter to tagged hands, step through them one by one.

**User stories**:
- "As a player studying my leaks, I want to step through hands using keyboard arrows, so I can efficiently review many hands in sequence."
- "As a player, I want to automatically surface hands where I lost 10-30 BB (not coolers), so I can focus study time on hands where my decisions mattered most."
- "As a player, I want to filter hands by action sequence ('opened CO, faced 3-bet, called'), so I can study specific spot types that my coaching content references."
- "As a player in a study group, I want to export a hand as formatted text, so I can share it in Discord or paste it into a solver."

**Features**:

**Keyboard navigation**: Left/right arrow keys step through hands in the hand browser. When a hand is selected in the detail drawer, left/right moves to the previous/next hand in the current filtered list without closing the drawer. Works in both the HandsPage and the stat detail panel's embedded hand explorer.

**"Study Queue"**: Filter to tagged hands, auto-advance through them. The existing tag system (already built) becomes the foundation for a study workflow.

**"Biggest Losers" auto-filter**: Surface hands where hero lost 10-30 BB. Not coolers (>50bb lost -- those are variance, not decision errors) and not trivial (<5bb -- not worth studying). These are the hands where decisions mattered most. Implementation: add a preset filter button to the hand browser.

**Action-sequence filtering**: "Show me all hands where I opened CO, faced 3-bet, and called." This is the #1 feature request in coaching. Requires querying the `actions` table with sequence matching. UI: a multi-step filter builder in the hand browser sidebar.

**Hand export**: Copy hand as formatted text for sharing in Discord/study groups. Export to solver-compatible format (PioSolver/GTO Wizard input). Implementation: "Copy" and "Export" buttons on the hand detail drawer.

### M2.4 -- Range Matrix Integration

**What**: The 13x13 matrix on `/range` already exists. Integrate it into the coaching workflow.

**User stories**:
- "As a player, I want to click 'Open Raise' in the stat detail panel and see my actual opening range as a 13x13 grid, so I can visually evaluate my range."
- "As a player, I want to see my actual range vs. a recommended range side-by-side, so I can identify specific hands to add or remove."

**Features**:
- **Link from stats page**: Clicking "Open Raise" in the stat detail panel opens the range matrix filtered to open raises from that position
- **Benchmark overlay**: Show "your actual range" vs. "recommended range" side-by-side or as an overlay (future: overlay mode showing differences)
- **Multi-context usage**: Same matrix component usable for hero ranges (this milestone), villain showdown ranges (Milestone 4), and population ranges (Milestone 4)

---

## 3. UI/UX Design

### Master-Detail Layout

```
+-----------------------------+------------------------------------------+
|  LEFT PANEL (~42%)          |  RIGHT PANEL (~58%)                      |
|                             |                                          |
|  [Filters: Stakes | Dates]  |  +--------------------------------------+ |
|  [Hands: 13,402  WR: 4.2]  |  |  STAT HEADER                        | |
|                             |  |  "Open Raise -- 18.5% (1,247/6,738)"| |
|  PRE-FLOP                   |  |  [All] [EP] [MP] [CO*] [BTN] [SB]   | |
|  +---+---+---+---+---+---+  |  +--------------------------------------+ |
|  |Tot|EP |MP |CO |BTN|SB |  |  |  ANALYSIS WIDGETS (conditional)    | |
|  +---+---+---+---+---+---+  |  |  [Positional mini-bar]             | |
|  |OR >18 |16 |22 |28 |-- |  |  |  [Response distribution]           | |
|  |F3B|62 |58 |65 |60 |70 |  |  |  [Range heatmap] (collapsible)    | |
|  |3B | 7 | 5 | 8 | 9 |12 |  |  |  [Trend sparkline]                | |
|  |...|   |   |   |   |   |  |  +--------------------------------------+ |
|  +---+---+---+---+---+---+  |  |  HAND EXPLORER                     | |
|                             |  |  [Open in Hand Explorer ->]          | |
|  STEAL                      |  |                                      | |
|  +-----------------------+  |  | Act|Cards|PF Act|Board  |Act |Res|Dt| |
|  | ...                   |  |  | ✓  |AhKs |R3    |Qh7d2c|B55%|+2 |2h| |
|  +-----------------------+  |  | ✗  |QJo  |C1    |Ts8s3h|X   |-1 |5h| |
|                             |  | ✓  |TT   |R2.5  |9c4h2d|B75%|+4 |1d| |
|  POSTFLOP                   |  |  ...                                | |
|  CHECK-RAISE (new)          |  |  [1] [2] [3] ... [25]               | |
|  PROBE / FLOAT (new)        |  +--------------------------------------+ |
|  MISSED C-BET               |                                          |
|  SHOWDOWN                   |                                          |
+-----------------------------+------------------------------------------+
```

### Universal Detail Panel Structure

Every stat drill-down uses the same panel structure. No separate panel types.

```
+---------------------------------------------+
| HEADER                                       |
| Stat name, overall %, (action/opportunity)   |
| Position tabs: [All] [EP] [MP] [CO] [BTN]   |
+---------------------------------------------+
| ANALYSIS WIDGETS (conditional, collapsible)  |
| Positional mini-bar (if positional stat)     |
| Response distribution (if defensive stat)    |
| Range heatmap (if preflop stat, collapsible) |
| Trend sparkline (all stats)                  |
+---------------------------------------------+
| HAND EXPLORER                                |
| [Open in Hand Explorer ->]                   |
| Condensed hand table (7 columns)             |
| Click row -> HandDrawer opens                |
| Keyboard: ↑↓ navigate, Enter open drawer    |
| Pagination                                   |
+---------------------------------------------+
```

### Condensed Hand Table (7 Columns)

Designed for 58% panel width (~700px on a 1280px screen):

```
+---+------+--------+-------------+--------+------+------+
|Act|Cards | PF Act | Board       |Key Act | Res  | Date |
+---+------+--------+-------------+--------+------+------+
| ✓ |Ah Ks | R3     | Qh 7d 2c   | B 55%  | +2.5 | 2h   |
| ✗ |Qc Jd | C1     | Ts 8s 3h 4d| X      | -1.0 | 5h   |
| ✓ |Td Tc | R2.5   | 9c 4h 2d 8s| B 75%  | +4.2 | 1d   |
+---+------+--------+-------------+--------+------+------+
```

- **Act**: Green checkmark if action taken, muted cross if opportunity missed
- **Cards**: Hero hole cards (CardPair component, same as HandsPage)
- **PF Act**: Preflop action sequence, hero's actions only (R3 = raised to 3bb)
- **Board**: Flop + turn + river cards inline (CardBoxRow, compact)
- **Key Act**: Primary street action for this stat (e.g., flop actions for C-Bet Flop)
- **Res**: Result in BB, green/red colored
- **Date**: Relative date (compact: "2h", "5d", "Jan 15")

Row click opens HandDrawer. Selected row highlighted with `bg-surface-hover`.

### Left Panel Sections (7 Total)

1. **Pre-Flop** (existing) -- VPIP, PFR, Open Raise, 3-Bet, 3-Bet IP/OOP, Fold to 3-Bet, 4-Bet, 5-Bet, Limp, Squeeze, etc.
2. **Steal** (existing) -- Steal, Fold to 3-Bet in steal, 4-Bet steal; vs Steal: Fold/Call/3-Bet
3. **Postflop** (existing) -- C-Bet per street, Fold to C-Bet, AF, AFq, Donk Bet; vs C-Bet responses
4. **Check-Raise** (NEW) -- Check-Raise F/T/R, Fold to XR F/T/R
5. **Probe / Float / Delayed C-Bet** (NEW) -- Probe Bet F/T/R, Float Flop, Delayed C-Bet T/R
6. **Missed C-Bet** (existing) -- Missed cbet IP/OOP, fold after miss, vs missed cbet
7. **Showdown** (existing) -- WTSD, WSD, WWSF

### Hand Review Keyboard Navigation UX

When the hand detail drawer is open (in either HandsPage or stat detail panel):
- **Left arrow** (or `j`): Move to previous hand in the current filtered list
- **Right arrow** (or `k`): Move to next hand in the current filtered list
- **Escape**: Close the detail drawer
- **t**: Quick-tag the current hand (opens tag popover)
- **n**: Focus the notes field

Visual indicator in the drawer header: "Hand 23 of 847" with left/right arrow buttons.

### Responsive Behavior

- **Desktop (>1280px)**: Side-by-side layout (left panel 42%, right panel 58%)
- **Tablet/narrow (<1280px)**: Full-width summary with detail as a slide-over/modal panel
- Detail panel has a close button (X) to return to summary-only view
- On narrow screens, clicking a stat opens the detail as a full-width overlay
- Analysis widgets collapse by default on narrow screens

---

## 4. Technical Spec

### Enriched Stat Detail Endpoint

Extend the existing `GET /api/stats/detail/{stat_key}/hands` to return board cards and action sequences alongside the existing fields.

**Current response** (StatDetailHand):
```json
{
  "hand_id": "RC1234567890",
  "played_at": "2025-01-15T20:30:00",
  "position": "CO",
  "card1": "Ah",
  "card2": "Ks",
  "action_taken": true,
  "won_bb": 2.5,
  "stakes": "$0.05/$0.10"
}
```

**Enriched response** (StatDetailHand v2):
```json
{
  "hand_id": "RC1234567890",
  "played_at": "2025-01-15T20:30:00",
  "position": "CO",
  "card1": "Ah",
  "card2": "Ks",
  "action_taken": true,
  "won_bb": 2.5,
  "all_in_ev_bb": 2.3,
  "stakes": "$0.05/$0.10",
  "bb_amount": 0.10,
  "board_flop": ["Qh", "7d", "2c"],
  "board_turn": "4s",
  "board_river": null,
  "preflop_actions": [{"a": "R", "v": 3, "h": true}],
  "key_street_actions": [{"a": "B", "v": 4, "h": true}, {"a": "F", "v": null, "h": false}]
}
```

New fields:
- `all_in_ev_bb`: All-in expected value (for EV diff display)
- `bb_amount`: Big blind amount (for USD conversion)
- `board_flop`, `board_turn`, `board_river`: Board cards from `board_cards` table
- `preflop_actions`: Parsed from raw text using shared `_parse_actions_from_raw`
- `key_street_actions`: Actions for the stat's primary street (flop for cbet_flop, preflop for open_raise, etc.)

**Implementation**: The endpoint already JOINs `hands` and `hand_players`. Add a JOIN to `board_cards` (aggregated) and call the shared action parser on `h.raw_text`. The action parser is already fast (~1ms per hand) and the query is paginated (25-50 hands), so performance is fine.

### Optional Analysis Summary Endpoint

**`GET /api/stats/detail/{stat_key}/analysis`** (~100-200ms)

Returns lightweight analysis data for the widget zone. Only the fields relevant to the stat type are populated.

**Query params**: `position`, `stakes`, `game_mode`, `date_from`, `date_to`

```json
{
  "positional": {
    "ep": { "value": 16.0, "numerator": 200, "denominator": 1250 },
    "mp": { "value": 18.5, "numerator": 250, "denominator": 1350 },
    "co": { "value": 22.0, "numerator": 350, "denominator": 1590 },
    "btn": { "value": 28.0, "numerator": 400, "denominator": 1428 },
    "sb": { "value": 14.0, "numerator": 150, "denominator": 1070 },
    "bb": { "value": 0, "numerator": 0, "denominator": 1050 }
  },

  "response_distribution": {
    "fold": { "pct": 62.5, "count": 250, "avg_ev_bb": -0.50 },
    "call": { "pct": 30.0, "count": 120, "avg_ev_bb": 0.35 },
    "raise": { "pct": 7.5, "count": 30, "avg_ev_bb": 1.80 }
  },

  "ev_comparison": {
    "action_ev": 0.82, "action_count": 650,
    "no_action_ev": 0.31, "no_action_count": 350
  },

  "range_heatmap": {
    "AA": { "frequency": 95.2, "count": 40, "total": 42 },
    "AKs": { "frequency": 88.1, "count": 37, "total": 42 }
  }
}
```

Note: `positional` is populated for positional stats. `response_distribution` for defensive stats. `range_heatmap` for preflop stats. `ev_comparison` for all stats.

### Trend Endpoint

**`GET /api/stats/detail/{stat_key}/trend`** (~100ms)

Returns rolling stat trend over time.

**Query params**: `position`, `stakes`, `date_from`, `date_to`, `window_size` (default 500)

```json
{
  "points": [
    { "date": "2025-01-01", "value": 17.2, "sample": 500 },
    { "date": "2025-01-08", "value": 19.1, "sample": 500 },
    { "date": "2025-01-15", "value": 18.5, "sample": 500 }
  ],
  "window_size": 500
}
```

### Extract Shared Action Parser

Move `_parse_actions_from_raw` from `backend/app/api/hands.py` to `backend/app/action_parser.py`:

```python
# backend/app/action_parser.py
def parse_actions_from_raw(raw_text: str, hero_username: str, bb_amount: float) -> dict:
    """Parse raw hand history text and return per-street action summaries + pot sizes.

    Returns dict with keys: preflop, flop, turn, river
    Each value: {"actions": list[ActionItem], "pot": int}
    """
    # ... existing logic moved from hands.py
```

Both `hands.py` and `stats.py` import from this shared module. No logic changes, just extraction.

### Add `stat_key` Parameter to Hand Browser

Extend `GET /api/hands` with an optional `stat_key` query parameter:

```python
@router.get("/hands")
def list_hands(
    # ... existing params ...
    stat_key: str | None = Query(None),
):
    if stat_key:
        entry = STAT_REGISTRY.get(stat_key)
        if entry:
            # Apply the same opportunity + action filters as the detail endpoint
            # This makes "Open in Hand Explorer" show exactly the same hands
```

This enables the "Open in Hand Explorer" link in the stat detail panel to deep-link to `/hands?stat_key=cbet_flop&pos=CO`, showing the full hand browser pre-filtered to the same hands.

### Frontend Loading Sequence

```
User clicks stat cell
  → render header + position tabs from stat registry (instant, no fetch)
  → fetch /hands (paginated)        → render condensed hand table
  → fetch /analysis (parallel)      → render analysis widgets
  → fetch /trend (after above)      → render sparkline
```

Each section shows a skeleton/spinner independently until its data arrives. If the user clicks a different stat before loading completes, in-flight requests are aborted (`AbortController`).

### New Database Columns

#### Check-Raise Flags (hand_players table)

```sql
-- Check-raise
check_raise_flop BOOLEAN, check_raise_flop_opp BOOLEAN,
check_raise_turn BOOLEAN, check_raise_turn_opp BOOLEAN,
check_raise_river BOOLEAN, check_raise_river_opp BOOLEAN,
fold_to_check_raise_flop BOOLEAN, fold_to_check_raise_flop_opp BOOLEAN,
fold_to_check_raise_turn BOOLEAN, fold_to_check_raise_turn_opp BOOLEAN,
fold_to_check_raise_river BOOLEAN, fold_to_check_raise_river_opp BOOLEAN,
```

#### Probe / Float / Delayed C-Bet Flags (hand_players table)

```sql
-- Probe bet
probe_bet_flop BOOLEAN, probe_bet_flop_opp BOOLEAN,
probe_bet_turn BOOLEAN, probe_bet_turn_opp BOOLEAN,
probe_bet_river BOOLEAN, probe_bet_river_opp BOOLEAN,

-- Float
float_flop BOOLEAN, float_flop_opp BOOLEAN,

-- Delayed c-bet
delayed_cbet_turn BOOLEAN, delayed_cbet_turn_opp BOOLEAN,
delayed_cbet_river BOOLEAN, delayed_cbet_river_opp BOOLEAN,
```

#### H2N Parity Flags (hand_players table)

```sql
-- H2N parity (from PRD.md Section 3.2.0)
-- NOTE: limp_fold, four_bet_fold, call_4bet, call_cbet_flop, raise_cbet_flop
-- already exist in stat_flags.py and hand_players schema. Only need stats engine wiring.
-- NEW columns needed:
missed_cbet_then_fold BOOLEAN,
bet_vs_missed_cbet BOOLEAN,
check_fold_vs_missed_cbet BOOLEAN,
```

#### Phase 1 Core Gap Flags (hand_players table)

```sql
-- Core gap stats (from PRD.md Section 3.2.2)
cold_call BOOLEAN,
call_3bet BOOLEAN,
fold_to_squeeze BOOLEAN,
```

#### Pot Context Columns (hand_players table, shared with Population PRD)

```sql
-- Pot type and multiway (shared with Population analysis)
pot_type VARCHAR,             -- srp, 3bet, 4bet, 5bet
is_multiway BOOLEAN,          -- true if 3+ players saw the flop
```

After schema migration: run `/api/import/rebuild` to recompute all flags from stored raw hand text.

### Stat Key Registry

Every clickable stat maps to a `stat_key` used for the detail endpoint. The registry already contains 60+ stat keys (see `backend/app/stat_registry.py`). New keys to add for M2.2:

#### New Check-Raise Keys

| stat_key | Detail Widgets |
|----------|----------------|
| `check_raise_flop` | Positional mini-bar, Trend sparkline |
| `check_raise_turn` | Positional mini-bar, Trend sparkline |
| `check_raise_river` | Positional mini-bar, Trend sparkline |
| `fold_to_check_raise_flop` | Positional mini-bar, Response distribution, Trend sparkline |
| `fold_to_check_raise_turn` | Positional mini-bar, Response distribution, Trend sparkline |
| `fold_to_check_raise_river` | Positional mini-bar, Response distribution, Trend sparkline |

#### New Probe / Float / Delayed C-Bet Keys

| stat_key | Detail Widgets |
|----------|----------------|
| `probe_bet_flop` | Positional mini-bar, Trend sparkline |
| `probe_bet_turn` | Positional mini-bar, Trend sparkline |
| `probe_bet_river` | Positional mini-bar, Trend sparkline |
| `float_flop` | Trend sparkline |
| `delayed_cbet_turn` | Trend sparkline |
| `delayed_cbet_river` | Trend sparkline |

#### New Core Gap Keys

| stat_key | Detail Widgets |
|----------|----------------|
| `cold_call` | Positional mini-bar, Range heatmap, Trend sparkline |
| `call_3bet` | Positional mini-bar, Range heatmap, Trend sparkline |
| `fold_to_squeeze` | Positional mini-bar, Trend sparkline |
| `saw_flop_pct` | Trend sparkline |
| `saw_turn_pct` | Trend sparkline |
| `saw_river_pct` | Trend sparkline |

### New Stat Flags in stat_flags.py

#### Check-Raise Detection

Logic: Player checked on a street, then an opponent bet, then the player raised.

```python
# For each street (flop, turn, river):
# check_raise_{street}_opp = True if player checked AND then faced a bet on that street
# check_raise_{street} = True if player checked, faced bet, then raised

# fold_to_check_raise_{street}_opp = True if player bet AND then faced a raise
#   (the raise was a check-raise from opponent's perspective)
# fold_to_check_raise_{street} = True if player bet, got check-raised, and folded
```

Implementation requires tracking the action sequence per street: identify check -> opponent_bet -> raise patterns.

#### Probe Bet Detection

Logic: The PFR (preflop raiser) checked, and the non-PFR player bets.

```python
# probe_bet_{street}_opp = True if opponent was PFR and checked to hero on this street
# probe_bet_{street} = True if hero bet when opponent (PFR) checked
```

Requires knowing who the PFR is and tracking their check action.

#### Float Detection

Logic: A float is a **two-street play** -- hero calls a flop bet in position, then bets or raises the turn when the opponent checks to them. Just calling IP on the flop is not a float; the follow-through aggression on the turn is what makes it a float.

```python
# float_flop_opp = True if hero called flop bet IP AND turn action checks to hero
#   (i.e., hero has the opportunity to complete the float)
# float_flop = True if hero called flop bet IP AND then bet/raised turn when checked to
#   (both conditions must be met -- flop IP call + turn aggression after check)
#
# Note: float_flop_opp denominator is IP flop calls where turn checks to hero,
#   NOT all IP flop bet facings. A hero who calls IP but faces a turn bet
#   has no float opportunity.
```

#### Delayed C-Bet Detection

Logic: Hero was PFR, checked the flop (missed c-bet), then bets the turn.

```python
# delayed_cbet_turn_opp = True if hero was PFR AND checked flop (missed cbet)
#   AND had opportunity to bet turn
# delayed_cbet_turn = True if hero was PFR, checked flop, then bet turn
# Similar for river: checked turn, bet river
```

#### H2N Parity Flag Detection

```python
# ALREADY IMPLEMENTED in stat_flags.py (need stats engine wiring only):
#   limp_fold: Hero limped preflop, then folded to a raise
#   four_bet_fold: Hero 4-bet, then folded to a 5-bet
#   call_4bet: Hero called a 4-bet (facing 4-bet, did not fold or 5-bet)
#   call_cbet_flop: Hero called a flop c-bet
#   raise_cbet_flop: Hero raised a flop c-bet
#   vs_missed_cbet_flop_opp: Hero was in hand when PFR missed flop c-bet
#
# NEW flags to implement:
# missed_cbet_then_fold: Hero missed c-bet (checked as PFR), then folded to opponent bet
# bet_vs_missed_cbet: Opponent missed c-bet, hero bet
# check_fold_vs_missed_cbet: Opponent missed c-bet, hero checked, then folded
```

#### Core Gap Flag Detection

```python
# cold_call: Hero called a raise preflop without having acted yet
#   (excludes BB special case of just calling)
# call_3bet: Hero called a 3-bet (facing 3-bet, did not fold or 4-bet)
# fold_to_squeeze: Hero folded when facing a squeeze
```

### Stats Engine Changes (stats_engine.py)

New sections to add to the stats engine:

1. **Check-Raise stats**: `_positional_pct(data, 'check_raise_flop', 'check_raise_flop_opp')` etc. for each street
2. **Fold to Check-Raise stats**: Same pattern for fold_to_check_raise per street
3. **Probe Bet stats**: Per street with opportunity flags
4. **Float stat**: Simple percentage with opp flag
5. **Delayed C-Bet stats**: Per street
6. **H2N parity stats**: limp_fold, four_bet_fold, call_4bet -- simple percentages
7. **Missed C-Bet IP/OOP splits**: Derive from position grouping (CO/BTN = IP, SB/BB/EP = OOP)
8. **vs Missed C-Bet stats**: bet_vs_missed_cbet, check_fold_vs_missed_cbet
9. **Saw Flop/Turn/River %**: `saw_flop / total_hands * 100`
10. **Cold Call, 3-Bet Call, Fold to Squeeze**: Simple percentages
11. **Donk Bet Turn/River**: Wire existing DB columns into stats output
12. **vs C-Bet by pot type**: Group fold_to_cbet by pot_type column

### Action-Sequence Query Logic

For M2.3 action-sequence filtering, the backend needs to support queries like:
"Show me all hands where hero opened from CO, faced a 3-bet, and called."

**Approach**: Query the `actions` table with ordered sequence matching.

```sql
-- Example: Hero opened CO, faced 3-bet, called
SELECT DISTINCT a1.hand_id
FROM actions a1
JOIN actions a2 ON a1.hand_id = a2.hand_id AND a2.action_order > a1.action_order
JOIN actions a3 ON a1.hand_id = a3.hand_id AND a3.action_order > a2.action_order
JOIN hand_players hp ON a1.hand_id = hp.hand_id AND a1.player_id = hp.player_id
WHERE hp.player_id = ?         -- hero
  AND hp.position = 'CO'
  AND a1.street = 'preflop'
  AND a1.action_type = 'raise' -- hero opens
  AND a2.street = 'preflop'
  AND a2.action_type = 'raise' -- someone 3-bets
  AND a2.player_id != ?        -- not hero
  AND a3.street = 'preflop'
  AND a3.action_type = 'call'  -- hero calls
  AND a3.player_id = ?         -- hero
```

**Frontend UI**: A multi-step filter builder with dropdowns:
1. Position: [Any] [EP] [MP] [CO] [BTN] [SB] [BB]
2. Action 1: [Any] [Open Raise] [Limp] [Call]
3. Opponent Action: [Any] [3-Bet] [Call] [Fold]
4. Hero Response: [Any] [Call] [Raise] [Fold]

New API endpoint: `GET /api/hands` already supports pagination and filtering. Add `action_sequence` parameter that accepts a structured filter definition.

### Frontend Component Structure

```
StatsPage.tsx (v2)
|-- StatsFilterBar.tsx (existing, left panel header)
|-- StatsSummaryPanel.tsx (left panel -- existing)
|   |-- PreflopSection.tsx (existing)
|   |-- StealSection.tsx (existing)
|   |-- PostflopSection.tsx (existing)
|   |-- CheckRaiseSection.tsx (NEW)
|   |-- ProbeFloatSection.tsx (NEW)
|   |-- MissedCbetSection.tsx (existing)
|   +-- ShowdownSection.tsx (existing)
|-- StatDetailPanel.tsx (right panel -- ENHANCED)
|   |-- DetailHeader.tsx (existing, enhanced)
|   |-- AnalysisWidgets.tsx (NEW)
|   |   |-- PositionalMiniBar.tsx
|   |   |-- ResponseDistribution.tsx
|   |   |-- CompactRangeHeatmap.tsx
|   |   |-- TrendSparkline.tsx
|   |   +-- EVComparison.tsx
|   |-- DetailHandExplorer.tsx (NEW -- replaces current basic table)
|   |   |-- CondensedHandTable.tsx (7-column layout)
|   |   +-- HandDrawer integration (reuse from HandsPage)
|   +-- Pagination (existing)
```

### State Management

- Selected stat stored as `{ key: string, position?: string }` in URL search params
- Detail panel uses progressive loading when selection changes:
  1. Render header from stat registry (instant, no fetch)
  2. Fetch `/api/stats/detail/{key}/hands` → render condensed hand table
  3. Fetch `/api/stats/detail/{key}/analysis` → render analysis widgets
  4. Fetch `/api/stats/detail/{key}/trend` → render sparkline
- Each section shows skeleton/spinner independently until data arrives
- In-flight requests aborted via `AbortController` when selection changes
- Left panel and right panel scroll independently (both `overflow-y: auto`)
- URL reflects selected stat for shareability: `/stats?detail=open_raise&pos=co`
- HandDrawer state: `selectedHandId` stored in component state (not URL -- too transient)

---

## 5. Execution Plan

### Phase M2.1a -- Layout + Click-Through (DONE)

**Status: Complete.**

Master-detail layout, clickable stat cells, basic hand list, URL state, responsive behavior. See implementation in `StatsPage.tsx`, `StatDetailPanel.tsx`, `stat_registry.py`.

### Phase M2.1b -- Embedded Hand Explorer (4-5 days)

**Delivers the most important upgrade**: transforms the detail panel from a list of hand IDs into a real hand explorer with board cards, action sequences, and HandDrawer integration.

**Tasks**:
1. Extract `_parse_actions_from_raw` to `backend/app/action_parser.py` (0.5 day)
   - Move function from `hands.py` to shared module
   - Update `hands.py` imports
   - No logic changes
2. Enrich `GET /api/stats/detail/{stat_key}/hands` response (1.5 days)
   - Add board cards JOIN (from `board_cards` table)
   - Add `all_in_ev_bb`, `bb_amount` to response
   - Call shared action parser for `preflop_actions` and `key_street_actions`
   - Update `StatDetailHand` Pydantic model
   - Determine "key street" from stat_key metadata (e.g., cbet_flop → flop actions)
3. Build `CondensedHandTable.tsx` with 7 columns (1.5 days)
   - Reuse `CardPair`, `CardBoxRow` components from HandsPage
   - Action sequence rendering (same format as HandsPage)
   - Row click handler → open HandDrawer
   - Keyboard navigation (arrow keys + Enter)
4. Integrate HandDrawer into StatDetailPanel (0.5 day)
   - Reuse `HandDrawer` component as-is (pass handId + onClose/onPrev/onNext)
   - Wire up prev/next to navigate through stat detail hand list
   - "Hand X of Y" indicator
5. Add `stat_key` parameter to `GET /api/hands` + "Open in Hand Explorer" link (0.5 day)
   - Backend: apply stat registry filters when `stat_key` is provided
   - Frontend: link at top of hand list opens `/hands?stat_key=...&pos=...`

**Dependencies**: None (M2.1a is done).

### Phase M2.1c -- Analysis Summary Widgets (3-4 days)

**Tasks**:
1. Build `AnalysisWidgets.tsx` container with collapsible layout (0.5 day)
   - Conditionally renders widgets based on stat metadata
   - Collapsible section with expand/collapse toggle
   - Max height cap with scroll
2. Build `PositionalMiniBar.tsx` (0.5 day)
   - Horizontal bars for each position
   - Clickable → filters hand list to that position
   - Data from existing positional stats (no new endpoint needed)
3. Build `ResponseDistribution.tsx` (0.5 day)
   - Horizontal stacked bar: Fold / Call / Raise
   - Clickable segments filter hand list
   - Data from new `response_distribution` field
4. Build `CompactRangeHeatmap.tsx` (1 day)
   - Reuse existing RangeChart component from `/range` page
   - Compact mode with smaller cells
   - Quick stats row below
   - Clickable cells filter hand list to that combo
5. Build `TrendSparkline.tsx` + backend trend endpoint (0.5 day)
   - Recharts mini line chart
   - Reference line for overall average
   - Backend: rolling window query on `hand_players`
6. Build backend `/api/stats/detail/{stat_key}/analysis` endpoint (1 day)
   - Positional breakdown (reuse stats engine queries)
   - Response distribution for defensive stats
   - EV comparison (action vs no-action avg result)
   - Range heatmap data for preflop stats

**Dependencies**: M2.1b (hand explorer must exist for widget → hand list filtering).

### Phase M2.1d -- EV & Advanced Widgets (2-3 days)

**Tasks**:
1. Build `EVComparison.tsx` widget (1 day)
   - Action vs no-action table with avg result
   - Color coding (green = action better, red = no-action better)
   - Minimum sample threshold (50 hands, greyed out below)
   - Info tooltip with caveats
2. Enhanced trend with confidence intervals (0.5 day)
   - Add 95% CI bands to sparkline
   - Backend: compute CI from binomial proportion
3. Wire stat type → widget mapping (0.5 day)
   - Stat metadata defines which widgets to show
   - Add `widget_types` to frontend stat registry or derive from stat category

**Dependencies**: M2.1c (widget framework must exist).

### Phase M2.2 -- New Stat Flags (Backend, Can Parallel with M2.1)

**Effort**: Medium-Large (5-7 days).

**Tasks**:
1. Add check-raise flags to `stat_flags.py` (1.5 days)
   - Implement check -> opponent_bet -> raise detection per street
   - Implement fold_to_check_raise (bet -> got_raised -> fold)
   - Add opportunity flags
2. Add probe/float/delayed c-bet flags to `stat_flags.py` (1.5 days)
   - Probe: identify PFR, track their check, detect hero bet
   - Float: track IP calls on flop + turn aggression after check
   - Delayed c-bet: PFR checked previous street, now bets
3. Add H2N parity flags (0.5 day)
   - limp_fold, four_bet_fold, call_4bet, call_cbet_flop, raise_cbet_flop already in stat_flags.py -- wire into stats_engine.py
   - NEW: missed_cbet_then_fold, bet_vs_missed_cbet, check_fold_vs_missed_cbet
4. Add core gap flags (0.5 day)
   - cold_call, call_3bet, fold_to_squeeze
5. Update `db.py` schema with all new columns (0.5 day)
6. Run rebuild to backfill all existing hands (0.5 day -- automated)
7. Add new sections to `stats_engine.py` computations (1 day)
8. Add new sections to left panel UI (CheckRaiseSection, ProbeFloatSection) (0.5 day)

**Dependencies**: None. Can run in parallel with M2.1 frontend work.

### Phase M2.3 -- Hand Review Workflow

**Effort**: Medium (4-6 days).

**Tasks**:
1. Keyboard navigation in hand browser (1 day)
   - Arrow keys step through hands when detail drawer is open
   - "Hand X of Y" indicator in drawer header
   - j/k alternative bindings
   - Works in both HandsPage and stat detail panel
2. "Biggest Losers" filter button (0.5 day)
   - Preset filter: -10 to -30 bb result
   - Add as a button/chip in hand browser filter bar
3. Action-sequence filtering (2-3 days)
   - Backend: extend `/api/hands` with `action_sequence` parameter
   - Build sequence matching SQL query
   - Frontend: multi-step filter builder UI
4. Hand export (1 day)
   - "Copy" button: formatted text to clipboard
   - "Export" button: solver-compatible format (PioSolver/GTO Wizard input)

**Dependencies**: None, but most valuable after M2.1b is built (HandDrawer integration provides context).

### Phase M2.4 -- Range Matrix Integration

**Effort**: Small (1-2 days).

**Dependencies**: M2.1c (range heatmap widget). Links from stats page to `/range` page with filters.

### Task Summary and Effort

| Phase | Effort | Value Delivered |
|-------|--------|----------------|
| M2.1a: Layout + Click-Through | **DONE** | Interactive drill-down |
| M2.1b: Embedded Hand Explorer | 4-5 days | Board cards, actions, HandDrawer in stat detail |
| M2.1c: Analysis Summary Widgets | 3-4 days | Positional bars, response splits, range heatmap, sparkline |
| M2.1d: EV & Advanced Widgets | 2-3 days | EV comparison, confidence intervals |
| M2.2: New Stat Flags | 5-7 days | Stat coverage matches competitors |
| M2.3: Hand Review Workflow | 4-6 days | Efficient study workflow |
| M2.4: Range Integration | 1-2 days | Cross-page linking |
| **Total remaining** | **19.5-27 days** | |

### Dependency Graph

```
M2.2 (stat flags) -----> can start immediately, parallel with everything
                    |
M2.1a (DONE) ------+---> M2.1b (embedded hand explorer)
                    |       |
                    |       +---> M2.1c (analysis widgets)
                    |               |
                    |               +---> M2.1d (EV + advanced)
                    |
                    +---> M2.3 (hand review, best after M2.1b)

M2.4 (range integration) ---> after M2.1c
```

**Recommended parallel tracks**:
- **Track A (Frontend)**: M2.1b -> M2.1c -> M2.1d
- **Track B (Backend)**: M2.2 (new stat flags) in parallel with Track A
- **Track C (independent)**: M2.3 (hand review workflow) -- can be done anytime

---

## 6. Testing

### Stat Flag Accuracy Tests

**New test cases for `test_parser.py`** (or new test file `test_stat_flags_v2.py`):

**Check-Raise tests**:
- Hand where hero checks flop, opponent bets, hero raises: `check_raise_flop = True`, `check_raise_flop_opp = True`
- Hand where hero checks flop, opponent bets, hero calls: `check_raise_flop = False`, `check_raise_flop_opp = True`
- Hand where hero checks flop, no opponent bet: `check_raise_flop_opp = False`
- Same patterns for turn and river
- Fold-to-check-raise: hero bets, gets raised (check-raise), hero folds

**Probe Bet tests**:
- Hand where opponent is PFR, checks flop, hero bets: `probe_bet_flop = True`
- Hand where opponent is PFR, checks flop, hero checks: `probe_bet_flop = False`, `probe_bet_flop_opp = True`
- Hand where hero IS the PFR: `probe_bet_flop_opp = False`

**Float tests**:
- Hand where hero calls flop bet in position, then bets turn when checked to: `float_flop = True`
- Hand where hero calls flop bet out of position: `float_flop = False`
- Hand where hero calls flop bet IP but faces turn bet: `float_flop_opp = False`

**Delayed C-Bet tests**:
- Hand where hero is PFR, checks flop, bets turn: `delayed_cbet_turn = True`
- Hand where hero is PFR, bets flop: `delayed_cbet_turn_opp = False`

**H2N Parity tests**:
- Limp-fold: hero limps, opponent raises, hero folds
- 4-bet-fold: hero 4-bets, opponent 5-bets, hero folds
- Call 4-bet: hero faces 4-bet, calls
- Missed c-bet then fold: hero was PFR, checks flop, opponent bets, hero folds

**Core Gap tests**:
- Cold call: hero calls an open raise (not from BB)
- 3-bet call: hero faces 3-bet, calls
- Fold to squeeze: hero called, opponent squeezes, hero folds

### Embedded Hand Explorer Tests

**Enriched endpoint tests**:
- Import known hands, verify `board_flop`, `board_turn`, `board_river` are correctly populated
- Verify `preflop_actions` matches expected action sequence
- Verify `key_street_actions` returns the correct street for each stat type (flop for cbet_flop, preflop for open_raise)
- Verify `all_in_ev_bb` is populated when available

**HandDrawer integration tests**:
- Click a hand row in stat detail panel → HandDrawer opens with correct hand
- Keyboard: arrow keys navigate through stat detail hand list
- Keyboard: Enter opens HandDrawer for selected row
- Keyboard: Escape closes HandDrawer, returns focus to hand list
- HandDrawer onPrev/onNext navigates within stat-filtered hand list
- "Hand X of Y" counter updates correctly

**"Open in Hand Explorer" tests**:
- Link navigates to `/hands?stat_key=cbet_flop&pos=CO`
- Hand browser shows same hands as stat detail panel
- Hand browser filters include stat_key context

### Analysis Widget Tests

**Positional mini-bar tests**:
- Verify bars show correct percentages per position
- Clicking a position bar filters the hand list

**Response distribution tests**:
- Import hands where hero faces 3-bets, verify fold/call/raise percentages are correct
- Clicking a response segment filters the hand list

**Range heatmap tests**:
- Import known hands, click "Open Raise" from CO, verify heatmap shows correct frequency for each combo
- Verify filtering by position changes the heatmap data
- Verify combo counts match expected values

**EV comparison tests**:
- Import hands with known outcomes, verify action vs no-action EV comparison is correct
- Verify minimum sample thresholds (< 50 hands greyed out)

**Trend sparkline tests**:
- Verify rolling average is computed correctly
- Verify reference line shows overall average

### Keyboard Navigation Tests

- Arrow keys step through hands in order
- Arrow keys wrap at beginning/end of list (or stop)
- Escape closes the detail drawer
- Navigation works correctly with active filters
- "Hand X of Y" counter updates correctly
- Keyboard nav works in both HandsPage and stat detail panel

### Acceptance Criteria

- [ ] Clicking any stat on the Stats page opens a universal detail panel with header, conditional analysis widgets, and a rich hand explorer
- [ ] Hand explorer shows 7 columns: action icon, cards, PF actions, board, key street actions, result, date
- [ ] Clicking a hand row opens HandDrawer with full hand replay
- [ ] Keyboard arrows navigate through hands in the detail panel, Enter opens drawer
- [ ] "Open in Hand Explorer" link navigates to hand browser pre-filtered to stat
- [ ] Positional mini-bar widget shows per-position breakdown for positional stats
- [ ] Response distribution widget shows fold/call/raise split for defensive stats
- [ ] Range heatmap widget shows 13x13 grid for preflop stats
- [ ] Trend sparkline widget shows rolling stat value over time
- [ ] EV comparison widget shows action vs no-action average results
- [ ] Widget clicks filter the hand list below (interactive drill-down)
- [ ] Left panel (stat tables) and right panel (detail) scroll independently
- [ ] URL reflects selected stat and position: `/stats?detail=open_raise&pos=co`
- [ ] Check-Raise section appears on left panel with per-street stats
- [ ] Probe/Float/Delayed C-Bet section appears on left panel
- [ ] All 13 H2N parity metrics are computed and displayed correctly
- [ ] Cold call, 3-bet call, fold to squeeze, saw flop/turn/river stats are available
- [ ] Keyboard left/right arrows step through hands in hand browser detail drawer
- [ ] "Biggest losers" filter surfaces hands with -10 to -30 bb result
- [ ] Action-sequence filter allows filtering by hero action sequence
- [ ] Hand export copies formatted text to clipboard
- [ ] All new stat flags produce correct values when tested against known hand histories
- [ ] Rebuild endpoint recomputes all new flags for existing hands
- [ ] Detail panel works correctly on desktop (>1280px) and tablet (<1280px)
- [ ] Stat cells with fewer than 100 hands show neutral/gray benchmark indicator (no false leak flags)
