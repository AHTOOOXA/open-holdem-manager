# "PostHog for Poker" — Product Vision

*March 2026*

---

## The Core Idea

Reposition OHM from "poker tracker" (competes with HM3/PT4/H2N on their terms) to **"poker analytics platform"** (creates a new category). The difference:

| Poker Tracker | Poker Analytics Platform |
|---------------|------------------------|
| Pre-defined stats in a GUI | Query anything you want |
| HUD overlay | Post-session analysis engine |
| "Here are your numbers" | "Ask any question about your game" |
| Fixed views | Composable insights |
| Proprietary schema | Open, documented, queryable data |
| Vendor lock-in | Your data, your queries |

PostHog did this to product analytics: took the Mixpanel/Amplitude paradigm ("pre-built dashboards for PMs") and turned it into an engineer-first platform ("SQL access to your own data, build anything"). OHM can do the same to poker tracking.

---

## Why the Analogy Works

### Data Model Mapping

| PostHog | OHM | Notes |
|---------|-----|-------|
| **Event** | **Action** (fold/call/bet/raise) | The atomic unit. Something happened at a point in time. |
| **Person** | **Player** | The actor. Has properties that evolve. |
| **Session** | **Hand** | A bounded sequence of events with a start and end. |
| **Group** | **Player Identity** | Multi-account grouping (already in OHM). |
| **Event Properties** | **Stat Flags + Amounts** | Context on each action: position, street, bet size, stack depth. |
| **Person Properties** | **Player Classifications** | Aggregate player traits: NIT/TAG/LAG/REC/MAN, VPIP range, player type. |
| **Cohort** | **Player Segment** | Dynamic groups: "regs with VPIP 20-25 and 3bet > 8%". |
| **Insight** | **Analysis View** | Reusable analytical pattern: graph, breakdown, comparison. |
| **Dashboard** | **Stats Page** | Pre-built monitoring view. |
| **Notebook** | **Study Session** (doesn't exist yet) | Ad-hoc investigation mixing queries, replays, notes. |
| **Session Replay** | **Hand Replayer** | Watch what actually happened. |
| **HogQL** | **PokerQL** (or natural language) | Domain-specific query interface. |

### Architecture Mapping

| PostHog Pattern | OHM Equivalent |
|----------------|----------------|
| **Immutable event store** -> computed views | **Raw hand histories** (`raw_text`) -> computed stat flags |
| **ClickHouse** (columnar OLAP) | **DuckDB** (columnar OLAP, but embedded) |
| **Denormalized properties on events** | **Stat flags on `hand_players`** (VPIP, PFR, etc. pre-computed per hand) |
| **HogQL** (SQL + domain sugar) | **Natural language -> DuckDB SQL** via LLM |
| **Insight types** (Trends, Funnels, Retention, Paths) | **Poker analysis patterns** (see showcase examples below) |
| **Autocapture** (no instrumentation needed) | **Auto-import** (watch folder, parse automatically) |
| **Usage-based pricing** | **Freemium** (free core, paid AI queries/cloud sync) |

### PostHog's Insight Types -> Poker Analysis Patterns

| PostHog Insight | Poker Equivalent | What It Answers |
|-----------------|-----------------|-----------------|
| **Trends** | Stat trends over time | "Is my 3bet% increasing this month?" |
| **Funnels** | Street progression | "Of hands where I cbet flop, how often do I barrel turn? River? Win at showdown?" |
| **Retention** | Session consistency | "Am I playing regularly? When do I take breaks?" |
| **Paths** | Action sequences | "What's my most common line with top pair on wet boards?" |
| **Stickiness** | Session depth | "How many hands do I play per session? Is it increasing?" |
| **Lifecycle** | Player engagement | "Am I a new, returning, or dormant player at each stake level?" |
| **SQL / HogQL** | Natural language queries | "Show me all hands where I flatted a 3bet OOP with suited connectors and lost more than 50bb" |

---

## The Gap Nobody Fills

### Current Tools vs. What Players Actually Want to Query

Based on research across Reddit, TwoPlusTwo, and PT4/H2N forums, these are the questions players ask that **no tool answers well today**:

**Multi-condition cross-player queries:**
> "How often does villain X open-raise from CO when a specific player is on the button?"
> -- Required raw SQL subqueries in PT4. Impossible in H2N.

**Conditional multi-street lines:**
> "What's their turn barrel frequency given they used a small flop cbet sizing?"
> -- Bet-size-conditional stats. No tool handles this in the UI.

**Solver-vs-reality bridge:**
> "GTO Wizard says cbet 67% on K-high dry boards. How often do I actually cbet on K-high dry flops?"
> -- No tool connects solver output to your actual play data. This is a massive unserved need.

**Population segmentation:**
> "Show me all regs whose WTSD is above 30% and who also have a high river aggression factor"
> -- H2N's Range Research does a version of this, but only for PRO/EDGE subscribers ($49-62/mo).

**Sample-size-aware stats:**
> "Show me this stat, but only if we have 50+ observations. Otherwise show a warning."
> -- Users hack this in PT4 with `if(cnt < 10, 'X', value)`. No first-class support.

### The Competitor Custom Stat Landscape

| Tool | Query Power | Limitation |
|------|------------|------------|
| **PT4** | SQL via PostgreSQL (hidden, undocumented schema) | Schema deliberately undocumented for 9+ years. Users reverse-engineer column names. |
| **H2N** | Visual action-sequence builder + formula language | Can't nest expressions. Limited to `Value/Cases/Opps` functions. No raw SQL. |
| **DriveHUD** | Basic expression language | Limited power |
| **GTO Wizard** | Filter + group + visualize solver output | Queries solver solutions, not your actual play |
| **Jupyter projects** | Full Python/SQL | Developer-only, no UI, no parser integration |
| **OHM (today)** | Pre-built stats pages | No custom queries yet |
| **OHM (proposed)** | **Natural language -> DuckDB SQL + documented schema** | The gap |

### The Key Insight

**PokerTracker's PostgreSQL database is the most powerful query tool in poker -- and they deliberately hide it.** The schema is undocumented. Users must ask forum moderators to write SQL for them. This is like Amplitude charging extra for SQL access while PostHog gives it away free.

OHM's opportunity: **be the PostHog**. Document the schema. Expose it. Make it queryable. Then put a natural language interface on top so you don't even need to know SQL.

---

## Natural Language Query Interface

### Why It Works for Poker

Text-to-SQL accuracy depends heavily on schema complexity and domain specificity. OHM's situation is unusually favorable:

| Factor | OHM's Advantage |
|--------|----------------|
| Schema size | ~10 tables, ~80 columns. Fits in any model's context window. |
| Domain clarity | Poker terminology is well-defined. "VPIP" has one meaning. |
| Query patterns | Most queries are filter + aggregate + group by. No complex graph traversals. |
| Column naming | Clear: `vpip`, `three_bet`, `position`, `won_bb`. Not `flg_p_3bet_opp_ip_vs_hero`. |
| Database | DuckDB has clean SQL syntax. A fine-tuned model (DuckDB-NSQL-7B) exists. |

### Expected Accuracy

| Query Complexity | Example | Expected Accuracy |
|-----------------|---------|-------------------|
| Simple stat lookup | "What is my VPIP?" | 95%+ |
| Filtered stat | "What is my 3bet% from the button?" | 90%+ |
| Comparative | "Compare my winrate in 3bet pots vs single raised pots" | 85%+ |
| Multi-condition | "Hands where I opened CO, got 3bet, and called -- how often did I win?" | 80%+ |
| Cross-table complex | "Show villain's bet sizing distribution on the river when they had a flush draw on the flop" | 65-75% |

With a **semantic layer** (glossary mapping poker terms to SQL), the first three categories should hit 90%+. The semantic layer is the single highest-impact investment.

### Semantic Layer Example

```yaml
# poker_glossary.yaml -- maps poker concepts to SQL
metrics:
  vpip:
    description: "Voluntarily Put money In Pot -- percentage of hands where player voluntarily put chips in preflop"
    sql: "COUNT(*) FILTER (WHERE vpip) * 100.0 / COUNT(*)"
    table: hand_players

  winrate:
    description: "Win rate in big blinds per 100 hands (bb/100)"
    sql: "SUM(won_bb) / COUNT(*) * 100"
    table: hand_players

  three_bet_pct:
    description: "3-bet percentage -- how often player 3-bets when given the opportunity"
    sql: "COUNT(*) FILTER (WHERE three_bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE three_bet_opp), 0)"
    table: hand_players

  cbet_flop:
    description: "Continuation bet on flop -- how often player bets the flop after being the preflop aggressor"
    sql: "COUNT(*) FILTER (WHERE cbet_flop) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE cbet_flop_opp), 0)"
    table: hand_players

filters:
  position:
    values: [EP, MP, CO, BTN, SB, BB]
    column: hand_players.position

  stakes:
    column: hands.stakes
    examples: ["$0.05/$0.10", "$0.10/$0.25", "$0.25/$0.50"]

  street:
    values: [preflop, flop, turn, river]
    column: actions.street

concepts:
  hero: "The player identified as hero in the current workspace"
  villain: "Any non-hero player"
  reg: "Regular player -- classified as TAG, LAG, or NIT"
  fish: "Recreational player -- classified as REC or MAN"
  wet_board: "Flop with flush draw and/or straight draw possibilities"
  dry_board: "Flop with few draw possibilities (e.g., K72 rainbow)"
```

### Cost Per Query

| Model | Cost/Query | 1000 Queries | Notes |
|-------|-----------|-------------|-------|
| Claude Haiku 4.5 | ~$0.005 | $5 | Sufficient for this schema |
| Claude Haiku (cached) | ~$0.001 | $1 | With prompt caching (system prompt reuse) |
| Claude Sonnet 4.6 | ~$0.015 | $15 | For complex queries |
| DuckDB-NSQL-7B (local) | $0 | $0 | Runs via Ollama, lower accuracy |

At $1-5 per 1,000 queries, this is viable even for free-tier users. A typical session might be 5-20 queries. Monthly cost per active user: $0.15-$1.00.

### Implementation Path

**Phase 1 -- Direct prompting (1-2 days of work):**
- `POST /api/query/ask` endpoint
- System prompt: full DDL + semantic layer + 20-30 example Q&A pairs
- Claude Haiku via API
- Execute on read-only DuckDB cursor
- Return: answer + generated SQL + results table
- Agent retry: if DuckDB throws error, send error to LLM for one retry

**Phase 2 -- Vanna AI integration (if Phase 1 accuracy insufficient):**
- [Vanna AI](https://github.com/vanna-ai/vanna) (14.6K GitHub stars) has first-class DuckDB support
- RAG-based: learns from successful queries
- Train with DDL + poker glossary + successful Q&A pairs
- Auto-generates Plotly visualizations from results

**Phase 3 -- Hybrid local + cloud (optional):**
- DuckDB-NSQL-7B via Ollama for simple queries (zero cost)
- Fall back to Claude API for complex queries
- Best of both: free for simple, API quality for hard

---

## The Platform Vision

### Level 1: Poker Tracker (Today)
Pre-built stats, graphs, hand browser. Competes with PT4/HM3/H2N on features.

### Level 2: Poker Analytics (Next)
Queryable database with natural language interface. "Ask anything about your game." No competitor does this.

### Level 3: Poker Analytics Platform (Future)
Composable insights, notebooks, solver integration, shared analysis. The PostHog play.

```
Level 1: Tracker          Level 2: Analytics        Level 3: Platform
+--------------+          +--------------+          +--------------+
| Fixed Stats  |          | Ask Anything |          | Notebooks    |
| Fixed Graphs |    ->    | Custom Views |    ->    | Solver Bridge|
| Hand Browser |          | NL Queries   |          | Shared Decks |
| Replayer     |          | Semantic SQL |          | Plugin System|
+--------------+          +--------------+          | Community    |
                                                    +--------------+
Competitors here          Nobody here               Nobody here
(PT4, HM3, H2N)
```

### Level 2 Features

**1. Natural Language Query Bar**
An "Ask" input bar on every page. Type a question, get an answer with a chart and the SQL that produced it.

```
+-----------------------------------------------------------+
| Ask: "What is my winrate by position this month?"          |
+-----------------------------------------------------------+

+-----------------------------------------------------------+
| Your winrate by position (March 2026):                     |
|                                                            |
|  BTN   +8.2 bb/100  (1,204 hands)                         |
|  CO    +3.1 bb/100  (1,198 hands)                         |
|  MP    -1.4 bb/100  (1,156 hands)                         |
|  EP    -4.2 bb/100  (1,089 hands)                         |
|  SB    -12.1 bb/100 (1,210 hands)                         |
|  BB    -5.8 bb/100  (1,243 hands)                         |
|                                                            |
|  > Show SQL                                                |
|  [Copy SQL] [Edit & Re-run] [Save as View]                 |
+-----------------------------------------------------------+
```

**2. Suggested Questions**
Pre-built prompts that showcase the query engine's power:

- "What's my biggest leak by position?"
- "Compare my preflop stats this week vs last month"
- "Which opponent have I lost the most to?"
- "How does my cbet frequency change on wet vs dry boards?"
- "Show me hands where I lost more than 50bb with top pair"
- "What's my winrate in 3bet pots vs single raised pots?"

**3. Documented Schema**
Unlike PT4 (deliberately undocumented), publish the full schema with descriptions. Make it a feature, not a secret.

**4. Saved Views**
Save any query as a reusable view. Share views with the community. This is the "custom reports" equivalent but powered by SQL instead of a proprietary formula language.

**5. Solver Bridge (Level 3)**
The killer feature nobody has: compare solver output with your actual play.

```
Ask: "How does my cbet frequency on K-high dry flops compare to GTO?"

+-----------------------------------------------------------+
| K-high dry flops (K72r, K83r, K92r, etc.)                  |
|                                                            |
|  Your cbet frequency:  52% (234 hands)                     |
|  GTO optimal:          71%                                 |
|  Gap:                  -19% (you're checking too much)     |
|                                                            |
|  When you do cbet:                                         |
|    Your avg sizing:    33% pot                             |
|    GTO avg sizing:     33% pot  (checkmark)                |
|                                                            |
|  Recommendation: You're missing value by checking back     |
|  too often. On K-high dry boards, the preflop raiser       |
|  has a significant range advantage.                        |
+-----------------------------------------------------------+
```

---

## What PostHog Got Right That OHM Should Copy

### 1. "Your Data, Your Queries"

PostHog's #1 differentiator against Amplitude/Mixpanel is HogQL -- SQL access to your own data. This is what developers love. The poker equivalent:

> "Your hands, your queries. Every hand you've ever played, in a fast analytical database, queryable in plain English or SQL. No hidden schema. No proprietary format. No lock-in."

### 2. Open Schema as a Feature

PT4 hides its schema. H2N has a proprietary formula language. OHM should **publish the schema as documentation** and make it a selling point. "Here are your 10 tables. Here's what every column means. Query them however you want."

### 3. Generous Free Tier

PostHog: 90%+ of customers use it for free. 1M events/month free. The free tier drives adoption; the platform stickiness drives conversion.

OHM equivalent: Free for all pre-built stats + hand browser + replayer + graphs. The natural language query engine could be:
- Free: 50 queries/day (enough for a study session)
- Pro: Unlimited queries + saved views + solver bridge ($8-15/mo)

### 4. Usage-Based, Not Seat-Based

PostHog charges per event, not per seat. This removes friction for team adoption.

OHM equivalent: If monetizing, charge per query volume or feature tier, not per device or user.

### 5. Radical Transparency

PostHog publishes everything: handbook, compensation, roadmap, revenue numbers. This builds extraordinary trust with developers.

OHM equivalent: Open-source code, public roadmap, documented schema, published stats methodology. "Here's exactly how we calculate VPIP. Here's the SQL. Verify it yourself."

---

## What Makes This Different from "Just Adding a Chat Box"

The "PostHog for poker" framing isn't just about natural language queries. It's about a **philosophical shift** in how the product thinks about poker data:

### Traditional Tracker Mentality
- Stats are pre-defined by the developer
- Users consume fixed reports
- The schema is an implementation detail
- Value is in the HUD overlay
- Customization = choose which pre-built stats to display

### Analytics Platform Mentality
- The database is the product
- Users compose their own analysis
- The schema is documented and queryable
- Value is in the analytical engine
- Customization = write any query you can imagine

This matters because **the poker meta evolves faster than any developer can add stats**. When a new strategic concept emerges (e.g., "probe betting" or "geometric sizing"), traditional trackers need months to add support. An analytics platform user just writes a query.

---

## Risks and Counterarguments

### "Poker players aren't developers. They won't write SQL."

True -- which is why the natural language interface is essential, not optional. But:
- PostHog proved that even non-technical users benefit from SQL access when the schema is well-documented
- The suggested questions / saved views pattern means most users never write a query -- they click one
- Power users (poker coaches, study group leaders) will write SQL and share saved views with their students
- The LLM handles the translation for everyone else

### "Text-to-SQL isn't reliable enough"

For poker's well-defined domain with a small schema:
- Simple queries (80% of what people ask): 90%+ accuracy
- The agent retry loop (run SQL -> error -> retry) handles syntax issues
- Showing the SQL builds trust -- users can verify and edit
- Accuracy improves with every query you add to the training set
- Even 80% accuracy is infinitely better than the 0% of tools that don't offer this at all

### "The addressable market is too small"

The poker tracking market is small (~200-500K users). But the "analytics platform" framing opens adjacent markets:
- **Poker coaches** who need custom analysis for students
- **Poker study groups** who want to share insights
- **Poker content creators** who need data for YouTube/Twitch content
- **Poker schools** (RunItOnce, Pokercoaching.com) who need white-label analytics
- **Sports betting analysts** (the data model generalizes)

### "LLM API costs will eat margins"

At $0.001-0.005 per query (Haiku with caching), a user doing 20 queries/day costs $0.60-$3.00/month. If they're paying $8-15/month for Pro, that's 60-80%+ gross margin. And the local model option (DuckDB-NSQL-7B) costs $0.

### "Isn't this just a fancy filter?"

No. Filters are pre-defined dimensions. This is ad-hoc analysis. The difference:

**Filter**: Show me hands at NL25 from the button this month -> {stake} x {position} x {date}

**Query**: "Show me hands where I opened from the button, villain 3-bet from the blinds, I called, I check-raised the flop, and villain folded -- how much did I win on average and what were my cards?"

No filter system in any tracker can express that. This requires multi-table joins across `hands`, `hand_players`, `actions`, and `board_cards`. It's a fundamentally different capability.

---

## Showcase: 10 "PostHog for Poker" Examples

Each example below shows a question that **no existing poker tracker can answer without raw SQL**, but OHM answers in plain English.

### 1. Street-by-Street Funnel (PostHog: Funnels)

**The question:**
> "When I open-raise from the CO and get called, how often do I cbet the flop? Of those, how often do I barrel the turn? River? And what's my winrate at each decision point?"

**What makes this hard:** This is a multi-step funnel across streets with conversion rates at each step. PT4/H2N show individual stats (cbet flop %, cbet turn %) but not the connected funnel -- they can't show "of the hands where I cbetted flop AND got called, what happened next?"

**OHM query:**
```
Ask: "Show me my CO open-raise funnel: open -> cbet flop -> barrel turn -> barrel river.
      How many hands at each step, and what's my winrate?"
```

**Result:**
```
CO Open-Raise Funnel (last 30 days)

  Open-raise CO         1,204 hands
    | called (72%)
  Cbet flop               867 hands     +2.1 bb/100
    | called (58%)
  Barrel turn              503 hands     +4.8 bb/100
    | called (41%)
  Barrel river             206 hands     +8.2 bb/100
    | showdown (65%)
  Won at showdown          134 hands     +12.1 bb/100

  Drop-off: 32% of your opens never see a flop bet.
  Biggest leak: You barrel turn only 58% -- population average is 64%.
```

### 2. Stat Drift Over Time (PostHog: Trends)

**The question:**
> "How has my 3bet% from the blinds changed over the last 6 months? Plot it week by week."

**What makes this hard:** Trackers show your lifetime 3bet%. Some show last N hands. None plot the trend over time as a time series you can visually inspect for drift.

**OHM query:**
```
Ask: "Plot my 3bet% from SB and BB, weekly, for the last 6 months"
```

**Result:**
```
3-Bet % from Blinds (Weekly Rolling Average)

12% |                                          /--
11% |                               /----------/
10% |              /-------\/------/
 9% |    /--------/        \/
 8% |----/
 7% |
    +----------------------------------------------
    Sep     Oct     Nov     Dec     Jan     Feb

    -- SB (current: 11.2%)    -- BB (current: 9.8%)

  Drift: Your SB 3-bet increased +2.4% since December.
  This coincides with moving from NL25 to NL50.
```

### 3. Player Segment Comparison (PostHog: Cohorts)

**The question:**
> "Compare my winrate against fish (VPIP > 40%) vs regs (VPIP 18-28%) by position."

**What makes this hard:** H2N's Range Research does population segmentation but only for PRO subscribers ($49-62/mo). PT4 can't segment by opponent type without manual SQL. No tool overlays hero performance against different opponent segments.

**OHM query:**
```
Ask: "What's my winrate by position against fish vs regs?"
```

**Result:**
```
Winrate by Position vs Opponent Type (bb/100)

Position | vs Fish (VPIP>40)   | vs Regs (VPIP 18-28)  | Delta
---------+---------------------+------------------------+--------
BTN      | +18.4  (2,104 h)    | +2.1  (3,892 h)       | +16.3
CO       | +12.7  (1,876 h)    | -0.8  (3,441 h)       | +13.5
MP       | +8.2   (1,654 h)    | -2.4  (3,210 h)       | +10.6
EP       | +5.1   (1,203 h)    | -3.8  (2,890 h)       |  +8.9
SB       | +2.3   (1,445 h)    | -8.2  (2,780 h)       | +10.5
BB       | -1.4   (1,678 h)    | -6.1  (3,120 h)       |  +4.7

  Insight: You're losing 8.2 bb/100 from the SB against regs.
  This is your biggest positional leak against competent players.
```

### 4. Session Lifecycle (PostHog: Lifecycle)

**The question:**
> "Am I playing more or less over time? Show me new sessions, returning days, and gaps."

**What makes this hard:** No tracker shows engagement patterns. They show session count but not the lifecycle -- when you took breaks, when you ramped up, seasonal patterns.

### 5. Action Path Analysis (PostHog: Paths)

**The question:**
> "What are my most common lines with top pair on the flop? Show the decision tree."

**What makes this hard:** No tracker shows decision trees. They show individual stats but not the connected sequence of decisions.

**Result:**
```
Top Pair Decision Tree (542 hands)

  Flop Top Pair
  +-- Bet (68%) --- 369 hands --- +6.2 bb/100
  |   +-- Called -> Bet turn (54%) -- +8.1 bb/100
  |   |   +-- Called -> Bet river (41%) -- +11.4 bb/100
  |   |   +-- Called -> Check river (59%) -- +3.2 bb/100  !!
  |   +-- Called -> Check turn (31%) -- +2.8 bb/100
  |   +-- Raised -> Call (10%) -- -4.2 bb/100
  |   +-- Folded (5%) -- immediate win
  +-- Check (28%) --- 152 hands --- +1.4 bb/100
  +-- Check-raise (4%) --- 21 hands --- +14.2 bb/100

  !! Leak: When you bet flop, get called, barrel turn, get called again --
  you check river 59% of the time. Your winrate drops from +8.1 to +3.2.
  You might be missing value on the river.
```

### 6. Revenue Attribution by Spot (PostHog: Revenue Analytics)

**The question:**
> "Where is my money actually coming from? Break down my profit by spot type."

**Result:**
```
Profit Attribution (Last 50K hands, in BB)

                    Single Raised Pots       3-Bet Pots
Position     |  Profit    bb/100   |  Profit    bb/100
-------------+---------------------+---------------------
BTN          |  +842      +8.4     |  +234      +12.1
CO           |  +312      +3.8     |  +89       +6.2
MP           |  -87       -1.2     |  -145      -8.4
EP           |  -234      -4.1     |  -67       -5.8
SB           |  -567      -9.2     |  -312      -18.4
BB           |  -412      -5.8     |  -178      -11.2

  Best spot: BTN in 3-bet pots (+12.1 bb/100)
  Worst spot: SB in 3-bet pots (-18.4 bb/100)
  67% of your profit comes from BTN+CO single raised pots.
```

### 7. A/B Testing Your Own Game (PostHog: Experiments)

**The question:**
> "I changed my SB strategy last month. Did it actually improve my results?"

**What makes this hard:** No tool lets you compare period A to period B for a specific stat/position with statistical significance.

### 8. Opponent Scouting Report (PostHog: User Profiles)

**The question:**
> "Give me a complete scouting report on villain_xyz."

The LLM synthesizes raw stats into an actionable game plan. This is what poker coaches charge $100/hour to do.

### 9. Correlation Discovery (PostHog: SQL Insights)

**The question:**
> "Is there a relationship between my session length and my winrate? Am I tilting in long sessions?"

**Result:**
```
Session Length vs Winrate

Duration        | Sessions | Avg Hands | bb/100    | Trend
----------------+----------+-----------+-----------+------
< 30 min        |    42    |     85    |  +6.8     | good
30-60 min       |    38    |    210    |  +4.2     | good
1-2 hours       |    31    |    450    |  +2.1     | ok
2-3 hours       |    18    |    780    |  -1.4     | bad
3+ hours        |    11    |   1,200   |  -8.7     | bad

  Correlation: -0.72 (strong negative)

  Your winrate drops sharply after 2 hours.
  Sessions over 3 hours cost you an average of -$43.50 each.

  Recommendation: Set a 2-hour session limit. Your total profit
  would be ~$1,200 higher over this sample if you'd stopped at 2h.
```

### 10. The "Ask Anything" Showcase (PostHog: HogQL)

**The question:**
> "Show me my most profitable and most costly specific hand combos."

**Result:**
```
Top 5 Most Profitable Hands

Hand    | Times Dealt | Won (BB)   | bb/hand  | Best Spot
--------+-------------+------------+----------+----------
AA      |     52      |  +284.2    |  +5.47   | 3-bet pot BTN
KK      |     48      |  +201.8    |  +4.20   | 4-bet pot CO
AKs     |     64      |  +156.4    |  +2.44   | 3-bet pot IP
JTs     |     89      |  +142.1    |  +1.60   | Single raised BTN
99      |     78      |  +98.7     |  +1.27   | Set mining

Top 5 Least Profitable Hands

Hand    | Times Dealt | Won (BB)   | bb/hand  | Worst Spot
--------+-------------+------------+----------+----------
KJo     |    112      |  -187.4    |  -1.67   | Cold call SB  !!
ATo     |     98      |  -145.2    |  -1.48   | Open EP
QJo     |    105      |  -132.8    |  -1.26   | Cold call BB
KQo     |     94      |  -98.4     |  -1.05   | Call 3-bet OOP
A9o     |     88      |  -87.2     |  -0.99   | Open MP

  !! KJo is your single biggest losing hand. You've cold-called it
  from the SB 34 times and lost an average of 3.2 BB per hand in
  that spot. Consider folding KJo to SB cold calls entirely.
```

---

## The Pitch

> **OHM is not a poker tracker. It's a poker analytics engine.**
>
> Import your hands. Ask any question about your game in plain English. Get answers backed by SQL you can verify. No subscription. No hidden schema. No lock-in.
>
> Your data. Your queries. Open source.

This is the "PostHog for poker" in one paragraph. It positions OHM in a category of one, rather than as a free alternative to PT4/HM3/H2N.
