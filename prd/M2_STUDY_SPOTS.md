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

**Hand2Note Drill-Down**: Statistics page shows aggregate stats. Clicking any stat opens a detailed breakdown with sub-categories, then clicking further opens the individual hands. Three-level drill-down: category -> situation -> hand. The master-detail layout in this milestone replicates this pattern.

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

### M2.1a -- Stats v2: Master-Detail Layout with Click-Through

**What**: Redesign `/stats` from a full-width stat summary into a master-detail layout. Left panel keeps the existing stat tables (squeezed to ~40% width). Right panel opens a context-aware detail view when any stat is clicked.

**This is the single biggest UX upgrade in the roadmap.** It transforms the stats page from a wall of numbers into an interactive coaching tool.

**User stories**:
- "As a player studying my leaks, I want to click any stat and immediately see the supporting hands and sub-breakdowns, so I can understand the patterns behind the numbers."
- "As a player reviewing my preflop game, I want to click 'Open Raise' from CO and see exactly which hands I open, so I can compare my actual range to my target range."
- "As a coach reviewing a student's database, I want to click through stats quickly and see filtered hand lists for each one, so I can identify specific hands to discuss."

**Requirements**:
- Left panel (~40% width) keeps the exact current stat layout -- all 5 existing sections with their positional tables and key-value grids
- Tables become more compact (abbreviate headers: `Total` to `Tot`, reduce cell padding)
- Add 2 new sections (Check-Raise, Probe/Float/Delayed C-Bet) -- see M2.2
- Every stat value is clickable -- clicking highlights the cell and opens the detail panel on the right
- Active stat gets a visible selected state (e.g., indigo border/background)
- Keep existing color coding (green/red/yellow/blue thresholds) and M1 benchmark indicators
- Filters stay at top of left panel (stakes, date range, presets)
- Left and right panels scroll independently
- URL reflects selected stat for shareability: `/stats?detail=open_raise&pos=co`

**Default state**: When no stat is selected, the right panel shows a welcome/overview: "Click any stat to see detailed breakdown" with optional overall session summary.

**Detail panel structure**: Every detail panel has 3 zones:

1. **Header** -- stat name, overall value, sample size, position selector (if applicable)
2. **Analysis zone** -- stat-type-specific content (range heatmap, sizing splits, board texture, hand strength, EV analysis, trend sparkline)
3. **Hand history** -- scrollable, paginated list of matching hands

### M2.1b -- Range Detail Panel

**What**: For preflop stats, show a 13x13 range heatmap in the detail panel analysis zone.

**Used for**: VPIP, PFR, Open Raise, 3-Bet, 3-Bet IP/OOP, 4-Bet, 5-Bet, Call Open Raise, Limp, Squeeze, Steal, vs Steal 3-Bet.

**User stories**:
- "As a player, I want to click 'Open Raise' from BTN and see a 13x13 grid showing how often I open each hand combo, so I can visually see my actual range."
- "As a player, I want to see my 3-bet range from the BB laid out on a matrix, so I can identify hands I should be adding or removing."

**Header**:
- Stat name + overall % + sample (e.g., "Open Raise -- 18.5% (1,247 / 6,738 opportunities)")
- Position tabs: [All] [EP] [MP] [CO] [BTN] [SB] [BB] -- selecting a position filters the heatmap and hand list

**Analysis zone**:
- 13x13 Range Heatmap (reuse existing RangeChart component from `/range` page)
  - Shows frequency of each combo for the selected action
  - Color intensity = frequency (0% = empty, 100% = solid)
  - Combo count in each cell
- Quick stats row below heatmap:
  - Total combos in range
  - Range % (of all combos)
  - Average raise size (if applicable)

**Hand history**:
- All hands where hero had the opportunity for this action
- Columns: Hand ID, Position, Hole Cards, Action Taken (check/cross), Result (bb), Stakes
- Color: green row if action was taken, muted if not (opportunity but didn't take the action)
- Sortable by date, result
- Paginated (50 per page)

### M2.1c -- Postflop Action Detail Panel (Depends on Shared Infrastructure)

**What**: For postflop stats, show bet sizing distribution, board texture splits, hand strength at action, and EV analysis.

**Used for**: C-Bet (flop/turn/river), Donk Bet, Check-Raise, Probe Bet, Float, Delayed C-Bet.

**User stories**:
- "As a player studying my c-bet game, I want to see how often I c-bet on different board textures, so I can identify boards where I'm over- or under-betting."
- "As a player, I want to see what hand strength I typically have when I check-raise the flop, so I can evaluate if my check-raise range is balanced."
- "As a player, I want to see how profitable my c-bets are compared to checking, broken down by hand strength and board texture, so I know where my decisions are costing me money."

**Header**:
- Stat name + overall % + sample
- Street tabs (if multi-street stat): [Flop] [Turn] [River]
- Position filter: [All] [IP] [OOP] or full position set
- Pot filter: [All] [HU] [Multiway] -- heads-up vs multiway pots (multiway = 3+ players to flop)

**Analysis zone** -- 5 sub-sections:

#### a) Bet Sizing Distribution

Horizontal bar chart or table showing sizing buckets:
- **< 33% pot** -- count + %
- **33-50% pot** -- count + %
- **50-75% pot** -- count + %
- **75-100% pot** -- count + %
- **> 100% pot (overbet)** -- count + %
- Average sizing as % of pot

Requires `pot_before_action` and `bet_pct_pot` columns on the `actions` table (shared infrastructure).

#### b) Board Texture Splits

Table showing stat frequency broken down by board texture (H2N / Smart Research convention):
- **Rank structure**: ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc
- **Suits**: Monocolor / 2tone / Rainbow
- **Pairing overlay**: Paired (cross-cuts rank categories)
- Each row: texture category, stat % in that texture, sample size

See "Shared: Board Texture Classification" in Section 4 for full category definitions.

#### c) Hand Strength at Action

Hand strength is classified along two orthogonal dimensions -- a hand can be both a made hand AND a draw (e.g., top pair + flush draw):

**Made Hand Strength** (mutually exclusive):
- Straight Flush / Quads / Full House / Flush / Straight
- Set (pocket pair hit board) / Trips (board pair + hole card)
- Two Pair
- Overpair
- Top Pair Good Kicker (TPTK -- kicker A-T)
- Top Pair Weak Kicker (kicker 9 or lower)
- Middle Pair (second pair on board)
- Weak Pair (bottom pair, underpair, third pair)
- Overcards (2 cards above board, no pair)
- Ace High (ace in hand, no pair)
- No Made Hand

**Draw Flags** (can co-occur with any made hand, orthogonal):
- Flush Draw (4 to a flush)
- OESD (open-ended straight draw, 8 outs)
- Gutshot (inside straight draw, 4 outs)
- Combo Draw (flush draw + straight draw)
- Backdoor Flush Draw (3 to a flush, flop only)
- Backdoor Straight Draw (3 to a straight, flop only)
- No Draw

**Display**: Table with made hand categories as rows. Each row: category, count, % of total actions, average result (bb). Draw flags shown as a separate summary or as tags on each hand in the hand list.

See "Shared: Hand Strength Evaluation" in Section 4 for full classification definitions.

#### d) Stat Trend Over Time

- Mini line chart showing this stat's value over time
- X-axis: time (by week or by every N hands, auto-scaled)
- Y-axis: stat percentage
- Rolling window (e.g., last 500 opportunities) to smooth noise
- Highlights: overall average as a horizontal reference line
- Helps detect leaks developing or improving over time

#### e) EV of the Line

Compares the average result (bb/hand) when hero took the action vs when hero didn't -- broken down by hand strength and board texture. This is the most powerful leak-finding tool: it reveals not just *what* you do, but *which subsets* of your decisions are profitable or costly.

**Overall EV comparison**:
```
               |   Action    |  No Action  |
---------------+-------------+-------------|
Avg result     |  +0.82 bb   |  +0.31 bb   |
Hands          |     650     |     350     |
```

**EV by Hand Strength** (the most actionable breakdown):
```
Hand         | EV Bet   | EV Check |  Diff  |
-------------+----------+----------+--------|
Nuts+        | +5.20 bb | +3.10 bb | +2.10  | action better
Top Pair     | +1.80 bb | +1.20 bb | +0.60  | action better
Middle Pair  | +0.20 bb | +0.45 bb | -0.25  | no-action better
Draws        | -0.10 bb | -0.35 bb | +0.25  | action better
Air          | -0.55 bb | -0.18 bb | -0.37  | no-action better
```
Color coding: green diff = action is more profitable, red = no-action is more profitable.

**EV by Board Texture**:
```
Texture      | EV Bet   | EV Check |  Diff  |
-------------+----------+----------+--------|
Axx          | +1.20 bb | +0.50 bb | +0.70  | action better
BBx          | +0.60 bb | +0.30 bb | +0.30  | action better
8-2 Conn     | -0.30 bb | +0.10 bb | -0.40  | no-action better
Monocolor    | -0.15 bb | +0.20 bb | -0.35  | no-action better
```

**EV by Sizing** (when action was a bet/raise -- which size is most profitable):
```
Size         | Avg EV   | Hands   |
-------------+----------+---------|
< 33% pot    | +0.95 bb |   280   |
33-50% pot   | +0.70 bb |   250   |
50-75% pot   | +0.55 bb |    90   |
> 75% pot    | +0.30 bb |    30   |
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

**Hand history** (for Postflop Action Detail):
- All hands where hero had the opportunity (e.g., was PFR and flop checked to = cbet opp)
- Columns: Hand ID, Position, Board, Hole Cards, Action (bet size / check), Result (bb)
- Color: green if action taken, muted if opportunity missed

### M2.1d -- EV of the Line + Trend Sparkline

**What**: Add EV analysis (action vs. no-action comparison) and stat trend sparkline to the postflop detail panels.

**User stories**:
- "As a player, I want to see whether my c-bets are more profitable than checking in different situations, so I can adjust my c-bet frequency on specific board textures."
- "As a player, I want to see how my c-bet frequency has changed over the last month, so I can track whether the changes I made are sticking."

This sub-phase adds the two most analytically powerful sections to the postflop detail panel. The EV analysis is the #1 leak-finding tool -- it shows not just what you do, but which subsets of your decisions are profitable vs costly. The trend sparkline enables progress tracking (bridges to Milestone 3).

### Detail Type 3: Defensive / Response Detail

**Used for**: Fold to 3-Bet, Fold to 4-Bet, Fold to C-Bet, Fold to Steal, Call Steal, Fold to Check-Raise, vs Missed C-Bet actions.

**User stories**:
- "As a player, I want to see the fold/call/raise split when I face a 3-bet, so I can evaluate whether I'm folding too much."
- "As a player defending my blinds, I want to see which hands I fold vs. call vs. 3-bet when facing a steal, so I can build a better defending range."

**Header**:
- Stat name + % + sample
- Position filter

**Analysis zone**:

**Response distribution**: Pie chart or horizontal bars showing Fold / Call / Raise split.

**By position**: Small table showing the fold/call/raise % per position.

**Range heatmap** (if preflop): What hands hero folds / calls / raises with.

**EV of each response** (same concept as EV of the Line, applied to multi-way decisions):
```
Response | Avg EV    | Hands | % of total |
---------+-----------+-------+------------|
Fold     | -0.50 bb  |  250  |   62.5%    |  (dead money lost)
Call     | +0.35 bb  |  120  |   30.0%    |
Raise    | +1.80 bb  |   30  |    7.5%    |
```
For defensive stats, fold EV is always negative (the money already in the pot). The question is whether calling/raising recovers enough to justify not folding. Breakdown by hand strength shows which calls are profitable vs which are spewy.

**Hand history**:
- All hands where hero faced this action
- Columns: Hand ID, Position, Hole Cards, Hero Response (Fold/Call/Raise), Result (bb)

### Detail Type 4: Showdown Detail

**Used for**: WTSD, WSD, WWSF.

**User stories**:
- "As a player, I want to see my showdown win rate broken down by position, so I can identify if I'm going to showdown too often from certain seats."
- "As a player, I want to see the distribution of my showdown results (won/lost), so I can evaluate the quality of hands I're taking to showdown."

**Header**:
- Stat name + % + sample

**Analysis zone**:
- **Result distribution**: Won/Lost at showdown histogram or summary
- **By position**: Positional breakdown table
- **By street reached**: How often hero got to showdown via different run-outs

**Hand history**:
- WTSD: Hands where hero saw flop (went to SD highlighted)
- WSD: Hands where hero went to showdown (won highlighted)
- WWSF: Hands where hero saw flop (won highlighted)

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

Detail panel type: Postflop Action Detail (sizing splits, board texture, hand strength).

#### New Left Panel Section: Probe / Float / Delayed C-Bet

| Stat | Description | Display |
|------|-------------|---------|
| **Probe Bet Flop** | % hero bets flop when PFR/aggressor checks (OOP or IP) | Street table [Flop, Turn, River] |
| **Probe Bet Turn** | % hero bets turn when PFR checks | |
| **Probe Bet River** | % hero bets river when PFR checks | |
| **Float Flop** | % hero calls flop IP AND bets/raises turn when checked to (multi-street: requires flop IP call + turn aggression after check) | Single value |
| **Delayed C-Bet Turn** | % hero bets turn after checking flop as PFR | Single value |
| **Delayed C-Bet River** | % hero bets river after checking turn as PFR | Single value |

Detail panel type: Postflop Action Detail (sizing splits, board texture, hand strength).

#### H2N Parity Metrics (from PRD Section 3.2.0)

13 metrics needed for exact H2N layout parity:

| # | Metric | Section | OHM Status | What's Needed |
|---|--------|---------|------------|---------------|
| 1 | 4-Bet Range | Preflop right | **NEW** | `4bet_count / total_hands * 100` (derived, no parser change) |
| 2 | Limp-Fold | Preflop right | **EXISTS** | `limp_fold` already in stat_flags.py — wire into stats engine display |
| 3 | 4-Bet-Fold | Preflop right + Steal | **EXISTS** | `four_bet_fold` already in stat_flags.py — wire into stats engine display |
| 4 | Call 4-Bet | Preflop right | **EXISTS** | `call_4bet` already in stat_flags.py — wire into stats engine display |
| 5 | 4-Bet-Fold (steal) | Steal | **NEW** | Reuse `four_bet_fold` + steal context |
| 6 | Donk Bet Turn/River | Postflop left | Wire up | Columns exist in DB, wire into stats engine |
| 7 | vs C-Bet Fold/Call/Raise by pot type | Postflop right | **PARTIAL** | `call_cbet_flop`, `raise_cbet_flop` already in stat_flags.py — need `pot_type VARCHAR` column + pot-type split in stats engine |
| 8 | Missed C-Bet IP/OOP split | Missed C-Bet left | **NEW** | Derive from position (no parser change) |
| 9 | Missed C-Bet -> Fold | Missed C-Bet left | **NEW** | `missed_cbet_then_fold BOOLEAN` flag |
| 10 | vs Missed C-Bet (probe bet) | Missed C-Bet right | **PARTIAL** | `vs_missed_cbet_flop_opp` already in stat_flags.py — need `bet_vs_missed_cbet BOOLEAN` flag |
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
| Float Flop | Call flop bet in position AND then bet/raise turn when checked to. Both conditions required — just calling IP is not a float. Denominator = IP flop calls where turn checks to hero. | `float_flop BOOLEAN` | Multi-street tracking (flop call IP + turn bet when checked to) |

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

**Keyboard navigation**: Left/right arrow keys step through hands in the hand browser. When a hand is selected in the detail drawer, left/right moves to the previous/next hand in the current filtered list without closing the drawer.

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
|  LEFT PANEL (~40%)          |  RIGHT PANEL (~60%)                      |
|                             |                                          |
|  [Filters: Stakes | Dates]  |  +--------------------------------------+ |
|  [Hands: 13,402  WR: 4.2]  |  |  STAT HEADER                        | |
|                             |  |  "Open Raise -- 18.5% (1,247/6,738)"| |
|  PRE-FLOP                   |  +--------------------------------------+ |
|  +---+---+---+---+---+---+  |  |                                    | |
|  |Tot|EP |MP |CO |BTN|SB |  |  |  DETAIL CONTENT                    | |
|  +---+---+---+---+---+---+  |  |  (varies by stat type)             | |
|  |OR >18 |16 |22 |28 |-- |  |  |                                    | |
|  |F3B|62 |58 |65 |60 |70 |  |  |  - Range heatmap (preflop)        | |
|  |3B | 7 | 5 | 8 | 9 |12 |  |  |  - Size splits (postflop)        | |
|  |...|   |   |   |   |   |  |  |  - Board texture (postflop)       | |
|  +---+---+---+---+---+---+  |  |  - Hand strength (postflop)       | |
|                             |  |                                    | |
|  STEAL                      |  +--------------------------------------+ |
|  +-----------------------+  |  |                                    | |
|  | ...                   |  |  |  HAND HISTORY                      | |
|  +-----------------------+  |  |  (filtered to this stat/line)      | |
|                             |  |                                    | |
|  POSTFLOP                   |  |  #RC123  BTN  AKs   +2.5bb        | |
|  CHECK-RAISE (new)          |  |  #RC456  CO   QJo   -1.0bb        | |
|  PROBE / FLOAT (new)        |  |  #RC789  MP   TT    +4.2bb        | |
|  MISSED C-BET               |  |  ...                               | |
|  SHOWDOWN                   |  |  [Load more]                       | |
|                             |  +--------------------------------------+ |
+-----------------------------+------------------------------------------+
```

### Detail Panel Structure (All Types)

```
+-------------------------------------+
| HEADER                              |
| Stat name, overall value, sample    |
| Position selector (if applicable)   |
+-------------------------------------+
| ANALYSIS ZONE                       |
| (stat-type-specific content)        |
| Range heatmap / size splits / etc.  |
+-------------------------------------+
| HAND HISTORY                        |
| Scrollable list of matching hands   |
| Paginated, sortable                 |
+-------------------------------------+
```

### Left Panel Sections (7 Total)

1. **Pre-Flop** (existing) -- VPIP, PFR, Open Raise, 3-Bet, 3-Bet IP/OOP, Fold to 3-Bet, 4-Bet, 5-Bet, Limp, Squeeze, etc.
2. **Steal** (existing) -- Steal, Fold to 3-Bet in steal, 4-Bet steal; vs Steal: Fold/Call/3-Bet
3. **Postflop** (existing) -- C-Bet per street, Fold to C-Bet, AF, AFq, Donk Bet; vs C-Bet responses
4. **Check-Raise** (NEW) -- Check-Raise F/T/R, Fold to XR F/T/R
5. **Probe / Float / Delayed C-Bet** (NEW) -- Probe Bet F/T/R, Float Flop, Delayed C-Bet T/R
6. **Missed C-Bet** (existing) -- Missed cbet IP/OOP, fold after miss, vs missed cbet
7. **Showdown** (existing) -- WTSD, WSD, WWSF

### Detail Panel Designs by Type

**Type 1: Preflop Range Detail** (for VPIP, PFR, Open Raise, 3-Bet, etc.):
```
+-------------------------------------------+
| Open Raise -- 18.5% (1,247 / 6,738)      |
| [All] [EP] [MP] [CO*] [BTN] [SB] [BB]    |
+-------------------------------------------+
|                                           |
|  +---+---+---+---+---+---+---+---+---+   |
|  |AA |AKs|AQs|AJs|ATs|...|...|...|A2s|   |
|  +---+---+---+---+---+---+---+---+---+   |
|  |AKo|KK |KQs|KJs|KTs|...|...|...|K2s|   |
|  +---+---+---+---+---+---+---+---+---+   |
|  | ... 13x13 heatmap ...              |   |
|  +---+---+---+---+---+---+---+---+---+   |
|                                           |
|  Range: 18.5%  |  Combos: 247  |  Avg: 2.5x |
+-------------------------------------------+
| HANDS (1,247 matching)                    |
| #RC123  CO  AhKs  Raised   +2.5bb  $0.50 |
| #RC456  CO  QJo   Folded   -0.5bb  $0.50 |
| ...                                       |
| [1] [2] [3] ... [25]                      |
+-------------------------------------------+
```

**Type 2: Postflop Action Detail** (for C-Bet, Check-Raise, Probe, etc.):
```
+-------------------------------------------+
| C-Bet Flop -- 65.2% (892 / 1,368)        |
| [Flop*] [Turn] [River]                   |
| [All] [IP] [OOP]  |  [All] [HU] [MW]    |
+-------------------------------------------+
|                                           |
| SIZING DISTRIBUTION                       |
| < 33%  |||||||||||  45 (12.3%)           |
| 33-50% ||||||||||||||||||||  120 (32.8%) |
| 50-75% |||||||||||||||||  105 (28.8%)    |
| 75-100%||||||||||  72 (19.7%)            |
| > 100% ||||  23 (6.3%)                   |
| Avg: 52.5% pot                            |
|                                           |
| BOARD TEXTURE                              |
| Texture     | Stat% | Sample              |
| ABB         | 72.3% | 150                 |
| Axx         | 68.1% | 120                 |
| BBx         | 55.2% | 90                  |
| 8-2 Conn    | 45.0% | 60                  |
| Monocolor   | 42.1% | 38                  |
|                                           |
| HAND STRENGTH                              |
| Category    | Count | %    | Avg Result   |
| Overpair+   |   30  | 15%  | +3.4 bb     |
| Top pair    |   55  | 28%  | +1.2 bb     |
| Middle pair |   25  | 13%  | -0.5 bb     |
| Draws       |   30  | 15%  | -0.8 bb     |
| Air         |   57  | 29%  | -2.3 bb     |
|                                           |
| EV OF THE LINE                             |
|              | Bet     | Check   | Diff   |
| Overall      | +0.82   | +0.31   | +0.51  |
| Top Pair     | +1.80   | +1.20   | +0.60  |
| Air          | -0.55   | -0.18   | -0.37  |
|                                           |
| TREND  ~~~~/\~~~~/\~~~~  avg: 65.2%       |
+-------------------------------------------+
| HANDS (892 matching)                      |
| #RC123  BTN  Qh7d2c  AhKs  Bet 55%  +2.5|
| #RC456  CO   Ts8s3h  JhTh  Check    -1.0 |
| ...                                       |
+-------------------------------------------+
```

**Type 3: Defensive/Response Detail** (for Fold to 3-Bet, Fold to C-Bet, etc.):
```
+-------------------------------------------+
| Fold to 3-Bet -- 62.5% (250 / 400)       |
| [All] [EP] [MP] [CO] [BTN] [SB]          |
+-------------------------------------------+
|                                           |
| RESPONSE DISTRIBUTION                      |
| Fold  ||||||||||||||||||||||  62.5%       |
| Call  ||||||||||||  30.0%                 |
| Raise |||  7.5%                           |
|                                           |
| BY POSITION                                |
| Pos  | Fold | Call | Raise | Avg EV       |
| EP   | 58%  | 35%  | 7%   | -0.50 bb    |
| MP   | 60%  | 32%  | 8%   | -0.45 bb    |
| CO   | 65%  | 28%  | 7%   | -0.42 bb    |
| BTN  | 66%  | 27%  | 7%   | -0.38 bb    |
| SB   | 70%  | 22%  | 8%   | -0.55 bb    |
|                                           |
| EV BY RESPONSE                             |
| Fold  | -0.50 bb | 250 | 62.5%           |
| Call  | +0.35 bb | 120 | 30.0%           |
| Raise | +1.80 bb |  30 |  7.5%           |
|                                           |
| RANGE HEATMAP (what hero folds/calls)     |
|  [13x13 grid]                              |
+-------------------------------------------+
| HANDS (400 matching)                      |
| #RC123  CO  AhKs  Called    +3.5bb        |
| #RC456  BTN QJo   Folded   -0.5bb        |
| ...                                       |
+-------------------------------------------+
```

**Type 4: Showdown Detail** (for WTSD, WSD, WWSF):
```
+-------------------------------------------+
| Won at Showdown -- 55.2% (320 / 580)     |
+-------------------------------------------+
|                                           |
| RESULT DISTRIBUTION                        |
| Won   ||||||||||||||||||||||  55.2%       |
| Lost  ||||||||||||||||  44.8%             |
|                                           |
| BY POSITION                                |
| Pos  | WTSD | WSD  | WWSF                |
| EP   | 22%  | 58%  | 47%                 |
| MP   | 25%  | 55%  | 46%                 |
| CO   | 28%  | 57%  | 49%                 |
| BTN  | 30%  | 54%  | 51%                 |
| SB   | 24%  | 52%  | 45%                 |
| BB   | 26%  | 53%  | 46%                 |
+-------------------------------------------+
| HANDS (580 matching)                      |
| ...                                       |
+-------------------------------------------+
```

### Hand Review Keyboard Navigation UX

When the hand detail drawer is open in the hand browser:
- **Left arrow** (or `j`): Move to previous hand in the current filtered list
- **Right arrow** (or `k`): Move to next hand in the current filtered list
- **Escape**: Close the detail drawer
- **t**: Quick-tag the current hand (opens tag popover)
- **n**: Focus the notes field

Visual indicator in the drawer header: "Hand 23 of 847" with left/right arrow buttons.

### Responsive Behavior

- **Desktop (>1280px)**: Side-by-side layout (left panel 40%, right panel 60%)
- **Tablet/narrow (<1280px)**: Full-width summary with detail as a slide-over/modal panel
- Detail panel has a close button (X) to return to summary-only view
- On narrow screens, clicking a stat opens the detail as a full-width overlay

---

## 4. Technical Spec

### New API Endpoints: Progressive Loading Detail

The detail panel uses **4 separate endpoints** for progressive loading. The frontend calls `/summary` first (instant), renders the header, then calls `/hands`, `/analysis`, and `/trend` in parallel. This avoids a monolithic 3-5 second request and gives the user immediate feedback.

#### 1. `GET /api/stats/detail/{stat_key}/summary` (instant, ~50ms)

Returns stat metadata, overall/positional values, and detail type. Loaded first to render the header and position tabs immediately.

**Query params**: `position`, `stakes`, `date_from`, `date_to`, `street`, `multiway`

```json
{
  "stat_key": "open_raise",
  "stat_name": "Open Raise",
  "detail_type": "range",
  "overall": { "value": 18.5, "numerator": 1247, "denominator": 6738 },
  "positional": { "ep": { "value": 16.0, "numerator": 200, "denominator": 1250 }, "mp": {}, "co": {}, "btn": {}, "sb": {}, "bb": {} },
  "response_distribution": {
    "fold": { "pct": 62.5, "count": 250, "avg_ev_bb": -0.50 },
    "call": { "pct": 30.0, "count": 120, "avg_ev_bb": 0.35 },
    "raise": { "pct": 7.5, "count": 30, "avg_ev_bb": 1.80 }
  }
}
```

Note: `response_distribution` only populated for defensive stats. `detail_type` is one of: `range`, `postflop_action`, `defensive`, `showdown`.

#### 2. `GET /api/stats/detail/{stat_key}/hands` (~100-200ms)

Returns paginated hand list filtered by stat opportunity/action. Called in parallel with `/analysis`.

**Query params**: `position`, `stakes`, `date_from`, `date_to`, `street`, `multiway`, `page`, `per_page`

```json
{
  "items": [
    {
      "hand_id": "RC1234567890",
      "played_at": "2025-01-15T20:30:00",
      "position": "CO",
      "hole_cards": "AhKs",
      "action_taken": true,
      "action_detail": "raises $0.50 to $1.20",
      "board": "Qh 7d 2c",
      "result_bb": 2.5,
      "stakes": "$0.05/$0.10"
    }
  ],
  "total": 1247,
  "page": 1,
  "per_page": 50
}
```

#### 3. `GET /api/stats/detail/{stat_key}/analysis` (~200-500ms)

Returns the heavy analysis data: range heatmap (preflop), sizing/board texture/hand strength/EV (postflop). This is the slowest endpoint but loads in parallel with hands.

**Query params**: `position`, `stakes`, `date_from`, `date_to`, `street`, `multiway`

```json
{
  "range_heatmap": {
    "AA": { "frequency": 95.2, "count": 40, "total": 42 },
    "AKs": { "frequency": 88.1, "count": 37, "total": 42 },
    "AKo": { "frequency": 72.5, "count": 29, "total": 40 }
  },

  "sizing_distribution": {
    "buckets": [
      { "label": "< 33% pot", "count": 45, "pct": 12.3 },
      { "label": "33-50%", "count": 120, "pct": 32.8 },
      { "label": "50-75%", "count": 105, "pct": 28.8 },
      { "label": "75-100%", "count": 72, "pct": 19.7 },
      { "label": "> 100%", "count": 23, "pct": 6.3 }
    ],
    "avg_sizing_pct": 52.5
  },

  "board_texture": {
    "high_card": [
      { "label": "ABB", "value": 72.3, "sample": 150 },
      { "label": "ABx", "value": 68.1, "sample": 120 },
      { "label": "Axx", "value": 65.5, "sample": 110 },
      { "label": "BBB", "value": 60.2, "sample": 80 },
      { "label": "BBx", "value": 55.2, "sample": 90 },
      { "label": "Bxx", "value": 50.1, "sample": 70 },
      { "label": "T-9 Conn", "value": 48.3, "sample": 55 },
      { "label": "T-9 Disc", "value": 52.0, "sample": 65 },
      { "label": "8-2 Conn", "value": 45.0, "sample": 60 },
      { "label": "8-2 Disc", "value": 47.2, "sample": 50 }
    ],
    "suits": [
      { "label": "Monotone", "value": 42.1, "sample": 38 },
      { "label": "Two-tone", "value": 68.2, "sample": 200 },
      { "label": "Rainbow", "value": 70.1, "sample": 180 }
    ],
    "pairing": [
      { "label": "Paired", "value": 60.2, "sample": 90 },
      { "label": "Unpaired", "value": 69.5, "sample": 370 }
    ]
  },

  "hand_strength": {
    "categories": [
      { "label": "Nuts+", "count": 15, "pct": 7.6, "avg_result_bb": 5.2 },
      { "label": "Strong", "count": 30, "pct": 15.2, "avg_result_bb": 3.4 },
      { "label": "Top Pair", "count": 55, "pct": 27.9, "avg_result_bb": 1.2 },
      { "label": "Marginal Made", "count": 25, "pct": 12.7, "avg_result_bb": -0.5 },
      { "label": "Draw Only", "count": 18, "pct": 9.1, "avg_result_bb": -1.1 },
      { "label": "Air", "count": 57, "pct": 28.9, "avg_result_bb": -2.3 }
    ]
  },

  "ev_analysis": {
    "overall": {
      "action_ev": 0.82, "action_count": 650,
      "no_action_ev": 0.31, "no_action_count": 350
    },
    "by_hand_strength": [
      { "label": "Nuts+", "action_ev": 5.20, "action_n": 80,
        "no_action_ev": 3.10, "no_action_n": 15, "diff": 2.10 },
      { "label": "Top Pair", "action_ev": 1.80, "action_n": 180,
        "no_action_ev": 1.20, "no_action_n": 60, "diff": 0.60 },
      { "label": "Middle Pair", "action_ev": 0.20, "action_n": 90,
        "no_action_ev": 0.45, "no_action_n": 80, "diff": -0.25 },
      { "label": "Air", "action_ev": -0.55, "action_n": 150,
        "no_action_ev": -0.18, "no_action_n": 120, "diff": -0.37 }
    ],
    "by_board_texture": [
      { "label": "Axx", "action_ev": 1.20, "action_n": 120,
        "no_action_ev": 0.50, "no_action_n": 55, "diff": 0.70 },
      { "label": "BBx", "action_ev": 0.60, "action_n": 90,
        "no_action_ev": 0.30, "no_action_n": 45, "diff": 0.30 },
      { "label": "8-2 Conn", "action_ev": -0.30, "action_n": 60,
        "no_action_ev": 0.10, "no_action_n": 45, "diff": -0.40 }
    ],
    "by_sizing": [
      { "label": "< 33% pot", "avg_ev": 0.95, "count": 280 },
      { "label": "33-50%", "avg_ev": 0.70, "count": 250 },
      { "label": "50-75%", "avg_ev": 0.55, "count": 90 },
      { "label": "> 75%", "avg_ev": 0.30, "count": 30 }
    ]
  }
}
```

Note: Only relevant fields are populated per detail type. `range_heatmap` for preflop, `sizing_distribution`/`board_texture`/`hand_strength`/`ev_analysis` for postflop action stats.

#### 4. `GET /api/stats/detail/{stat_key}/trend` (~100ms)

Returns rolling stat trend over time. Loaded last (least critical for immediate analysis).

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

#### Frontend Loading Sequence

```
User clicks stat cell
  → fetch /summary (instant)          → render header + position tabs
  → fetch /hands + /analysis (parallel) → render hand list + analysis zone
  → fetch /trend (after above)         → render sparkline
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

#### Board Texture Columns (hands table, shared infrastructure)

```sql
-- Precomputed board texture on hands table
flop_texture_rank VARCHAR,   -- ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc
flop_texture_suit VARCHAR,   -- monocolor, 2tone, rainbow
flop_paired BOOLEAN,
turn_texture VARCHAR,         -- completed_draw, draw_adding, overcard, paired_board, brick
river_texture VARCHAR,
```

#### Hand Strength Columns (hand_players table, precomputed per street)

Hand strength is pre-computed during `insert_parsed_hand` for each street the player saw. This avoids on-demand evaluation of thousands of hands per detail click (which would take 3-5 seconds). Backfilled via `/api/import/rebuild`.

```sql
-- Per-street hand strength (precomputed during insert)
-- Made hand: integer ID from classification table (-4 to 11)
-- Draw flags: bitmask or individual booleans
flop_made_hand TINYINT,         -- classification ID (-4=no made hand ... 11=straight flush)
flop_draw_flags TINYINT,        -- bitmask: 1=flush_draw, 2=oesd, 4=gutshot, 8=backdoor_flush, 16=backdoor_straight
flop_hand_group VARCHAR,        -- composite display group: nuts_plus, strong, top_pair, marginal, draw_only, air
turn_made_hand TINYINT,
turn_draw_flags TINYINT,
turn_hand_group VARCHAR,
river_made_hand TINYINT,
river_draw_flags TINYINT,
river_hand_group VARCHAR,
```

The `/analysis` endpoint then aggregates from precomputed columns with simple `GROUP BY flop_hand_group` queries instead of evaluating hand strength at query time.

#### Pot Size Tracking Columns (actions table, shared infrastructure)

```sql
-- Pot context at time of action
pot_before_action DECIMAL,
bet_pct_pot DECIMAL,
```

After schema migration: run `/api/import/rebuild` to recompute all flags from stored raw hand text.

### Stat Key Registry

Every clickable stat maps to a `stat_key` used for the detail endpoint:

#### Preflop (Detail Type: Range)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| VPIP | `vpip` | Range |
| PFR | `pfr` | Range |
| Open Raise | `open_raise` | Range |
| 3-Bet | `three_bet` | Range |
| 3-Bet IP | `three_bet_ip` | Range |
| 3-Bet OOP | `three_bet_oop` | Range |
| 4-Bet | `four_bet` | Range |
| 5-Bet | `five_bet` | Range |
| Limp | `limp` | Range |
| Call Open Raise | `call_open_raise` | Range |
| Cold Call | `cold_call` | Range |
| Squeeze | `squeeze` | Range |

#### Preflop Defense (Detail Type: Defensive)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Fold to 3-Bet | `fold_to_3bet` | Defensive |
| Fold to 4-Bet | `fold_to_4bet` | Defensive |
| 3-Bet Call | `call_3bet` | Defensive |
| Call 4-Bet | `call_4bet` | Defensive |
| Limp-Fold | `limp_fold` | Defensive |
| 4-Bet-Fold | `four_bet_fold` | Defensive |
| Fold to Squeeze | `fold_to_squeeze` | Defensive |

#### Steal (Detail Type: Range for attacks, Defensive for defense)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Steal | `steal` | Range |
| Fold to 3-Bet (steal) | `fold_to_3bet_steal` | Defensive |
| 4-Bet (steal) | `four_bet_steal` | Range |
| 4-Bet-Fold (steal) | `four_bet_fold_steal` | Defensive |
| vs Steal Fold | `vs_steal_fold` | Defensive |
| vs Steal Call | `vs_steal_call` | Defensive |
| vs Steal 3-Bet | `vs_steal_3bet` | Range |

#### Postflop (Detail Type: Postflop Action)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| C-Bet Flop | `cbet_flop` | Postflop Action |
| C-Bet Turn | `cbet_turn` | Postflop Action |
| C-Bet River | `cbet_river` | Postflop Action |
| Donk Bet Flop | `donk_bet_flop` | Postflop Action |
| Donk Bet Turn | `donk_bet_turn` | Postflop Action |
| Donk Bet River | `donk_bet_river` | Postflop Action |
| Check-Raise Flop | `check_raise_flop` | Postflop Action |
| Check-Raise Turn | `check_raise_turn` | Postflop Action |
| Check-Raise River | `check_raise_river` | Postflop Action |
| Probe Bet Flop | `probe_bet_flop` | Postflop Action |
| Probe Bet Turn | `probe_bet_turn` | Postflop Action |
| Probe Bet River | `probe_bet_river` | Postflop Action |
| Delayed C-Bet Turn | `delayed_cbet_turn` | Postflop Action |
| Delayed C-Bet River | `delayed_cbet_river` | Postflop Action |
| Float Flop | `float_flop` | Postflop Action |

#### Postflop Defense (Detail Type: Defensive)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Fold to C-Bet Flop | `fold_to_cbet_flop` | Defensive |
| Fold to C-Bet Turn | `fold_to_cbet_turn` | Defensive |
| Fold to C-Bet River | `fold_to_cbet_river` | Defensive |
| Fold to XR Flop | `fold_to_check_raise_flop` | Defensive |
| Fold to XR Turn | `fold_to_check_raise_turn` | Defensive |
| Fold to XR River | `fold_to_check_raise_river` | Defensive |

#### Showdown (Detail Type: Showdown)

| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| WTSD | `wtsd` | Showdown |
| WSD | `wsd` | Showdown |
| WWSF | `wwsf` | Showdown |
| Saw Flop % | `saw_flop_pct` | Showdown |
| Saw Turn % | `saw_turn_pct` | Showdown |
| Saw River % | `saw_river_pct` | Showdown |

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

Logic: A float is a **two-street play** — hero calls a flop bet in position, then bets or raises the turn when the opponent checks to them. Just calling IP on the flop is not a float; the follow-through aggression on the turn is what makes it a float.

```python
# float_flop_opp = True if hero called flop bet IP AND turn action checks to hero
#   (i.e., hero has the opportunity to complete the float)
# float_flop = True if hero called flop bet IP AND then bet/raised turn when checked to
#   (both conditions must be met — flop IP call + turn aggression after check)
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

### Shared: Hand Strength Evaluation

New utility: given hero's hole cards + board cards, classify hand strength along two orthogonal dimensions (matching PokerTracker / H2N convention).

#### Made Hand Categories (mutually exclusive, highest match wins)

| ID | Category | Definition |
|----|----------|------------|
| 11 | Straight Flush | 5-card straight flush |
| 10 | Quads | Four of a kind |
| 9 | Full House | Three of a kind + pair |
| 8 | Flush | 5 cards same suit |
| 7 | Straight | 5 sequential ranks |
| 6 | Set | Pocket pair + board match (3 of a kind from pair in hand) |
| 5 | Trips | Board pair + 1 hole card match (3 of a kind from pair on board) |
| 4 | Two Pair | Two pair (both hole cards paired with board, or one hole card + board two-pair) |
| 3 | Overpair | Pocket pair higher than all board cards |
| 2 | Top Pair Good Kicker | Top pair with A, K, Q, J, or T kicker |
| 1 | Top Pair Weak Kicker | Top pair with 9 or lower kicker |
| 0 | Middle Pair | Paired with second-highest board card |
| -1 | Weak Pair | Bottom pair, third pair, underpair (pocket pair below middle card) |
| -2 | Overcards | Two hole cards above all board cards, no pair |
| -3 | Ace High | Ace in hand, no pair, not both overcards |
| -4 | No Made Hand | Nothing above |

#### Draw Flags (orthogonal -- can co-occur with any made hand)

| Flag | Definition |
|------|------------|
| `flush_draw` | 4 cards to a flush (hole + board) |
| `oesd` | Open-ended straight draw (8 outs) |
| `gutshot` | Inside straight draw (4 outs) |
| `combo_draw` | Flush draw + any straight draw (OESD or gutshot) |
| `backdoor_flush` | 3 cards to a flush (flop only, 2 to come) |
| `backdoor_straight` | 3 to a straight with 2 cards to come (flop only) |

#### Composite Categories (for display grouping)

| Group | Includes |
|-------|----------|
| **Nuts+** | Straight flush, quads, full house, flush, straight |
| **Strong** | Set, trips, two pair, overpair |
| **Top Pair** | Top pair good kicker, top pair weak kicker |
| **Marginal Made** | Middle pair, weak pair |
| **Draw Only** | No made hand (or weak made) + any draw flag |
| **Air** | No made hand, no draw |

This requires a poker hand evaluator function. Doesn't need full hand ranking -- just classification into the above buckets based on hole cards vs board. Consider using the `treys` Python library for the made-hand evaluation, with custom draw detection on top.

### Shared: Board Texture Classification

Shared utility between Stats v2 detail panels and Population Analysis. Implemented as a Python utility in the backend.

#### Flop Classification

Primary axis -- **Rank Structure** (H2N / Smart Research convention. Broadway = J, Q, K only; Ace and Ten treated as special categories):

**Priority rule**: Categories are evaluated top-to-bottom. The first match wins. Ten (T) is NOT a Broadway for this classification — it belongs in the T-9 tier. This follows the H2N convention where Broadway = {J, Q, K} and T is grouped with 9 as a mid-high card.

| Priority | Category | Code | Definition | Example |
|----------|----------|------|------------|---------|
| 1 | Ace + Broadway + Broadway | ABB | A + 2 of {J,Q,K} | As Kh Jd |
| 2 | Ace + Broadway + x | ABx | A + 1 of {J,Q,K} + non-broadway | As Qh 5d |
| 3 | Ace + x + x | Axx | A + no {J,Q,K} | As 7h 3d, As Th 5d |
| 4 | 3 Broadways (no A) | BBB | 3 of {J,Q,K}, no ace | Ks Qh Jd |
| 5 | 2 Broadways + x (no A) | BBx | 2 of {J,Q,K} + non-broadway, no ace | Ks Jh 6d, Qs Jh Td |
| 6 | 1 Broadway + x + x (no A) | Bxx | 1 of {J,Q,K} + 2 non-broadway, no ace | Qs 7h 3d, Jh Ts 5d |
| 7 | T-9 High Connected | T-9 Conn | Highest card T or 9, no A/{J,Q,K}, connected (<=2 gap between at least 2 cards) | Ts 9h 7d |
| 8 | T-9 High Disconnected | T-9 Disc | Highest card T or 9, no A/{J,Q,K}, disconnected | Ts 6h 2d, 9s 4h 2d |
| 9 | 8-2 High Connected | 8-2 Conn | Highest card 8 or lower, connected | 8s 7h 5d |
| 10 | 8-2 High Disconnected | 8-2 Disc | Highest card 8 or lower, disconnected | 8s 4h 2d |

**Disambiguation examples**:
- `Ts 6h 2d` → T-9 Disc (T is highest, no Broadway {J,Q,K}, not connected)
- `Qs Th 5d` → Bxx (Q is a Broadway, so this is 1 Broadway + 2 non-broadway)
- `Ks Jh Td` → BBx (K and J are Broadway, T is not — 2 Broadway + 1 non-broadway)
- `As Th 3d` → Axx (A present, T is not Broadway — A + 2 non-broadway)

Secondary axis -- **Suit Structure**:
- **Monocolor**: 3 cards same suit
- **2tone**: 2 cards same suit (flush draw possible)
- **Rainbow**: all different suits

Tertiary axis -- **Pairing** (overlay, cross-cuts rank categories):
- **Paired**: 2+ cards same rank
- **Unpaired**: all different ranks

#### Turn Classification

Classified by what the turn card brought relative to flop:

| Category | Definition |
|----------|------------|
| **Completed draw** | 3rd flush card, or completes obvious straight |
| **Draw-adding** | 2nd flush card, or adds straight potential |
| **Overcard** | Highest card on board |
| **Paired board** | Pairs one of the flop cards |
| **Brick** | Low, unconnected, doesn't change texture |

#### River Classification

Same categories as turn, applied to 4-card to 5-card board transition.

### Shared: Bet Sizing Extraction

For postflop detail panels, need to compute bet size as % of pot at time of action.

Requires tracking the pot size at each action. Stored as precomputed columns:
- `pot_before_action` on `actions` table
- `bet_pct_pot` = `amount / pot_before_action` for bets/raises

Computed during `insert_parsed_hand` for new hands, backfilled via rebuild for existing.

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
|-- StatsFilterBar.tsx (existing, moved to left panel header)
|-- StatsSummaryPanel.tsx (left panel -- refactored from current page)
|   |-- PreflopSection.tsx (existing)
|   |-- StealSection.tsx (existing)
|   |-- PostflopSection.tsx (existing)
|   |-- CheckRaiseSection.tsx (NEW)
|   |-- ProbeFloatSection.tsx (NEW)
|   |-- MissedCbetSection.tsx (existing)
|   +-- ShowdownSection.tsx (existing)
|-- StatDetailPanel.tsx (right panel -- NEW)
|   |-- DetailHeader.tsx
|   |-- PreflopRangeDetail.tsx (heatmap + quick stats)
|   |-- PostflopActionDetail.tsx (sizing + board + strength + EV + trend)
|   |-- DefensiveDetail.tsx (response distribution + range)
|   |-- ShowdownDetail.tsx
|   +-- DetailHandHistory.tsx (shared hand list component)
```

### State Management

- Selected stat stored as `{ key: string, position?: string, street?: string }`
- Detail panel uses progressive loading when selection changes:
  1. Fetch `/api/stats/detail/{key}/summary` (instant) → render header + position tabs
  2. Fetch `/api/stats/detail/{key}/hands` + `/analysis` in parallel → render hand list + analysis zone
  3. Fetch `/api/stats/detail/{key}/trend` → render sparkline
- Each section shows skeleton/spinner independently until data arrives
- In-flight requests aborted via `AbortController` when selection changes
- Left panel and right panel scroll independently (both `overflow-y: auto`)
- URL reflects selected stat for shareability: `/stats?detail=open_raise&pos=co`

---

## 5. Execution Plan

### Phase M2.1a -- Layout + Hand List (Do First)

**Effort**: Medium (5-7 days). **Delivers 70% of the value.**

This phase alone transforms the stats page from read-only to interactive. Every stat becomes clickable, and the detail panel shows the matching hands.

**Tasks**:
1. Refactor `StatsPage.tsx` into master-detail two-panel layout (2 days)
   - Split into left panel (40%) and right panel (60%)
   - Make left panel independently scrollable
   - Squeeze existing stat tables to fit narrower width
2. Make every stat cell clickable with selected state (1 day)
   - Add `onClick` handler to all stat value cells
   - Add indigo border/background for selected state
   - Store selected stat in component state + URL search params
3. Create `StatDetailPanel.tsx` with header + placeholder + hand list (2 days)
   - Header: stat name, overall value, sample size
   - Position selector tabs (if applicable)
   - Paginated hand list filtered by stat_key
4. Build backend: `GET /api/stats/detail/{stat_key}` -- initial version with hands only (1 day)
   - Query hand_players for hands matching the stat's opportunity flag
   - Paginated response with hand details
5. Wire up URL state: `/stats?detail=...&pos=...` (0.5 day)
6. Add responsive behavior for <1280px (0.5 day)

**Dependencies**: None. Can start immediately.

### Phase M2.1b -- Range Detail Panel

**Effort**: Medium (3-5 days).

**Tasks**:
1. Build `PreflopRangeDetail.tsx` (2 days)
   - Embed 13x13 heatmap (reuse existing RangeChart component from `/range`)
   - Position tab filtering
   - Quick stats row (total combos, range %, avg raise size)
2. Build backend: extend detail endpoint with `range_heatmap` data (1.5 days)
   - Query hand_players + hands to get combo frequencies per stat + position
   - Compute frequency per combo (e.g., AKs opened 37 out of 42 opportunities)
3. Wire stat_key to detail type mapping (0.5 day)
   - Preflop stat keys -> PreflopRangeDetail
   - Defensive preflop keys -> include range heatmap in DefensiveDetail

**Dependencies**: M2.1a (layout must exist).

### Phase M2.1c-d -- Postflop Detail + EV Analysis (Depends on Shared Infrastructure)

**Effort**: Large (8-12 days total).

**Tasks**:
1. Build board texture classifier utility (2 days)
   - Python module: `classify_flop(cards)`, `classify_turn_card(turn, flop)`, `classify_river_card(river, board)`
   - Add precomputed columns to hands table
   - Compute during insert, backfill via rebuild
2. Build pot size tracker (2 days)
   - Track running pot through each action during `insert_parsed_hand`
   - Store `pot_before_action` and `bet_pct_pot` on actions table
   - Backfill via rebuild
3. Build hand strength evaluator + pre-compute pipeline (3 days)
   - Python module: `classify_hand(hole_cards, board)` → `(made_hand_id, draw_flags, hand_group)`
   - Returns made hand category + draw flags + composite display group
   - Consider using `treys` library for made hand, custom draw detection
   - Pre-compute during `insert_parsed_hand`: for each street (flop/turn/river), if player has hole cards and board is dealt, classify and store in `hand_players` columns
   - Add `flop_made_hand`, `flop_draw_flags`, `flop_hand_group` (+ turn/river equivalents) to schema
   - Backfill existing hands via `/api/import/rebuild`
   - Detail `/analysis` endpoint aggregates via `GROUP BY flop_hand_group` (fast, no on-demand eval)
4. Build `PostflopActionDetail.tsx` with 5 sub-sections (3 days)
   - Sizing distribution bars
   - Board texture split table
   - Hand strength table
   - Trend sparkline (Recharts mini line chart)
   - EV of the line comparison tables
5. Extend backend detail endpoint with all postflop data (2 days)

**Dependencies**: Requires shared infrastructure (board texture, pot tracking, hand evaluator). Can be parallelized -- infrastructure in backend while M2.1a/b is built in frontend.

### Phase M2.2 -- New Stat Flags (Backend, Can Parallel with M2.1)

**Effort**: Medium-Large (5-7 days).

**Tasks**:
1. Add check-raise flags to `stat_flags.py` (1.5 days)
   - Implement check -> opponent_bet -> raise detection per street
   - Implement fold_to_check_raise (bet -> got_raised -> fold)
   - Add opportunity flags
2. Add probe/float/delayed c-bet flags to `stat_flags.py` (1.5 days)
   - Probe: identify PFR, track their check, detect hero bet
   - Float: track IP calls on flop
   - Delayed c-bet: PFR checked previous street, now bets
3. Add H2N parity flags (0.5 day)
   - limp_fold, four_bet_fold, call_4bet, call_cbet_flop, raise_cbet_flop already in stat_flags.py — wire into stats_engine.py
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

**Dependencies**: None, but most valuable after M2.1a is built (the detail panel provides context).

### Task Summary and Effort

| Phase | Effort | Value Delivered |
|-------|--------|----------------|
| M2.1a: Layout + Hand List | 5-7 days | 70% of milestone value -- interactive drill-down |
| M2.1b: Range Detail | 3-5 days | Preflop range visualization |
| M2.1c-d: Postflop Detail + EV + Hand Strength Pre-compute | 10-14 days | Deep postflop analysis (sizing, texture, strength, EV). Includes shared infra: board texture classifier, pot tracker, hand evaluator + pre-compute pipeline |
| M2.2: New Stat Flags | 4.5-6.5 days | Stat coverage matches competitors (reduced: 5 flags already exist, need wiring only) |
| M2.3: Hand Review Workflow | 4-6 days | Efficient study workflow |
| M2.4: Range Integration | 1-2 days | Cross-page linking |
| **Total** | **27.5-40.5 days** | |

### Dependency Graph

```
M2.2 (stat flags) -----> can start immediately, parallel with everything
                    |
M2.1a (layout) ----+---> M2.1b (range detail)
                    |
                    +---> M2.3 (hand review, best after M2.1a)
                    |
Shared Infra ------+---> M2.1c-d (postflop detail)
  - Board texture        (depends on shared infrastructure)
  - Pot tracking
  - Hand evaluator

M2.4 (range integration) ---> after M2.1b
```

**Recommended parallel tracks**:
- **Track A (Frontend)**: M2.1a -> M2.1b -> M2.1c-d (postflop UI)
- **Track B (Backend)**: M2.2 (new stat flags) + shared infrastructure (board texture, pot tracking, hand evaluator) -> M2.1c-d (postflop backend)
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
- Hand where hero calls flop bet in position: `float_flop = True`
- Hand where hero calls flop bet out of position: `float_flop = False`

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

### Detail Panel Data Correctness

**Range heatmap tests**:
- Import known hands, click "Open Raise" from CO, verify heatmap shows correct frequency for each combo
- Verify filtering by position changes the heatmap data
- Verify combo counts match expected values

**Postflop detail tests**:
- Import hands with known bet sizes, verify sizing distribution buckets are correct
- Import hands with known board textures, verify texture classification is correct
- Import hands with known hole cards + boards, verify hand strength classification is correct

**EV analysis tests**:
- Import hands with known outcomes, verify action vs no-action EV comparison is correct
- Verify minimum sample thresholds (< 50 hands greyed out)

**Response distribution tests**:
- Import hands where hero faces 3-bets, verify fold/call/raise percentages are correct

### Keyboard Navigation Tests

- Arrow keys step through hands in order
- Arrow keys wrap at beginning/end of list (or stop)
- Escape closes the detail drawer
- Navigation works correctly with active filters
- "Hand X of Y" counter updates correctly

### Board Texture Classification Tests

**Flop classification**:
- `As Kh Jd` -> ABB, Rainbow, Unpaired
- `As Qh 5d` -> ABx, Rainbow, Unpaired
- `Ks Qh Td` -> BBB, Rainbow, Unpaired
- `8s 7h 5d` -> 8-2 Conn, Rainbow, Unpaired
- `8s 4h 2d` -> 8-2 Disc, Rainbow, Unpaired
- `As Ks Js` -> ABB, Monocolor, Unpaired
- `Ts 9h Td` -> T-9 Conn (T is highest, no Broadway; T-9 gap=1 so connected), 2tone, Paired

**Turn classification**:
- 3rd flush card -> Completed draw
- Overcard (highest on board) -> Overcard
- Pairs a flop card -> Paired board
- Low unconnected card -> Brick

### Hand Strength Classification Tests

- `AhKh` on `As 7d 3c` -> Top Pair Good Kicker, No Draw
- `TsTc` on `As Td 3c` -> Set, No Draw
- `AhKh` on `Qh Jh 3c` -> Overcards, Flush Draw (combo draw with backdoor straight)
- `7s7d` on `As Kd Qc` -> Weak Pair (underpair), No Draw
- `2h3h` on `Ah 5h Jc` -> No Made Hand, Flush Draw + Gutshot (combo draw)
- `QsQd` on `Js 8d 3c` -> Overpair, No Draw

### Acceptance Criteria

- [ ] Clicking any stat on the Stats page opens a detail panel on the right with header, analysis content, and filtered hand list
- [ ] Left panel (stat tables) and right panel (detail) scroll independently
- [ ] URL reflects selected stat and position: `/stats?detail=open_raise&pos=co`
- [ ] Preflop stats show 13x13 range heatmap with correct frequencies per position
- [ ] Postflop stats show bet sizing distribution, board texture splits, and hand strength breakdown
- [ ] EV of the line shows action vs no-action comparison broken down by hand strength and board texture
- [ ] Stat trend sparkline shows rolling average over time with reference line
- [ ] Defensive stats show fold/call/raise response distribution with per-response EV
- [ ] Showdown stats show win/loss distribution and positional breakdown
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
