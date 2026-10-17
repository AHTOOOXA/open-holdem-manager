# Query Engine PRD — "PostHog for Poker"

*March 2026 · OHM v0.1.0 → v0.2.0*

---

## 1. Problem Statement

### What existing tools do well — and where they stop

Hand2Note's action-sequence builder handles multi-street conditional filtering well: "3bet BTN, got called, cbet flop, villain raised" is a drag-and-drop workflow. PT4's custom reports cover many situational breakdowns. These tools are powerful for *filtering within the domain of poker actions*.

But there's a category of questions that **no visual builder can express** — questions that cross tables, mix aggregation levels, or require ad-hoc computation:

> "Compare my winrate in 3bet pots when I'm IP vs OOP, broken down by stake level, but only for sessions where I played more than 200 hands"

> "Which of my opponents has the widest gap between their VPIP and PFR? Show me the top 10 with at least 100 hands."

> "Plot my c-bet frequency week by week for the last 3 months — am I trending up or down?"

> "What's my average loss in big blinds when I cold-call from the SB vs when I 3-bet from the SB?"

These require multi-table joins, time-series aggregation, cross-player comparisons, or conditional grouping that no action-builder UI can express. In PT4, the answer is "open pgAdmin and write SQL against an undocumented schema." In H2N, the answer is "you can't — export to Excel."

**The real gap**: Existing tools are powerful *within their UI paradigms* but have a hard ceiling. When a player hits that ceiling — and serious study players hit it constantly — they're stuck. OHM's query engine removes the ceiling entirely: any question that can be answered by SQL can be asked in English.

### Competitive analysis: How H2N handles filtering

Hand2Note is the industry leader in filtering. Understanding what it does well — and where it stops — defines exactly what OHM needs to build.

#### H2N's three filtering layers

**Layer 1 — Popup on Stat** (click any stat to drill down):
- Sub-breakdowns by **board texture** (user-configurable: 2-tone unpaired, monotone, paired, rainbow, etc.)
- Sub-breakdowns by **bet sizing** (configurable buckets: % of pot, bb amounts, effective stack ratios)
- **Hand strength histograms** (combo draws, flush draws, made hands, air)
- **vs-Hero** frequency (how villain plays specifically against you)
- **Next Actions** (fold/call/raise frequencies after this action)

**Layer 2 — Smart Reports** (interactive action-tree navigation):
- **"Faced Next"** — after you act, what did villain do? (fold / call / raise / squeeze). Click to drill into that subset.
- **"Next Actions"** — after filtering, what did YOU do next? Click to continue the tree.
- Chains together: Open BTN → Faced 3-bet → Called → Faced C-bet Flop → Called → Faced Barrel Turn → ...
- Stats auto-populate contextually ("smart") — the report shows relevant stats for the current spot.

**Layer 3 — Custom Filter Builder** (the power tool):
| Tab | What it filters |
|-----|----------------|
| **General** | Table size, big blind, straddle, poker room, effective stack depth |
| **Actions** | Street-by-street action line: preflop facing (unopened/raised/3bet), your action (raise/call/fold), postflop actions per street, last action on street |
| **Hand Strength** | Made hand categories, draws, board texture conditions |
| **Bet Sizing** | Bet size relative to pot, bb, or opponent's previous bet (configurable ranges like 0.45-0.55x pot) |
| **Player Type** | Reg vs fish, color label, custom player tags |

#### Capability comparison

| Capability | H2N | OHM Query Engine |
|-----------|-----|-----------------|
| Action-sequence filtering ("hero raises, villain calls, hero cbets") | Yes — stacked action blocks | Yes — action line builder generating SQL |
| Bet sizing qualifiers on actions | Yes — ratio to pot/BB/previous bet | Yes — amount_bb ranges and % pot ranges |
| Pre-built quick filter presets | Yes — ~32 preflop/postflop/outcome | Yes — ~20 preflop/postflop/scenario presets |
| Board texture categories | Yes — user-configurable (256 categories) | Yes — computed from board_cards at query time. Defaults: monotone/two-tone/rainbow, paired/unpaired, A-high through 9-high. Custom categories Phase 2. |
| Hand strength filtering (top pair, set, etc.) | Yes — postflop histogram, 5+ categories | Yes — evaluated from hero cards + board_cards at query time. Categories: overpair, top pair, mid/bottom pair, two pair, set, straight/flush draws, made straights/flushes, full house+. Custom tiers Phase 2. |
| Cross-player aggregation ("winrate vs fish vs regs") | **No** | **Yes** (builder + NL) |
| Time-series trending ("3bet% weekly for 6 months") | **No** | **Yes** (group by week/month) |
| Opponent comparison ("who do I lose most to?") | **No** | **Yes** (NL) |
| Combine action lines WITH analytical measures + GROUP BY | **No** — filters and stats are separate | **Yes** — action line is just a WHERE clause, compose freely |
| Ad-hoc computed metrics | **No** — formula language limited to `Cases/Opps*100` | **Yes** (SQL, NL) |
| Export results to JSON/CSV | **No** | **Yes** (API) |
| Natural language queries | **No** | **Yes** |
| Custom SQL against your data | **No** — proprietary database | **Yes** — DuckDB, documented schema |
| Smart Reports (auto-populated stats per spot) | Yes — stats swap based on filter context | Phase 2 |
| Faced Next / Next Actions drill-down | Yes — click-through navigation | Phase 2 (builder shows results, not drill-down yet) |

**Where OHM is stronger**: analytical composition. H2N treats filters and stats as separate systems — you filter to a spot, then look at pre-defined stats for that spot. OHM composes them: an action line narrows the hand set, then any measure/group-by/aggregation runs on that narrowed set. "My winrate when I cbet flop and get raised, grouped by month, against regs only" — one query.

**Where H2N is stronger (for now)**: user-configurable category definitions (custom AND/OR/NOT logic for board textures and hand strength tiers — OHM ships sensible defaults, custom categories in Phase 2), and the interactive Faced Next / Next Actions drill-down (Phase 2 for OHM).

### Why this is the headline feature

The query engine transforms OHM from "another free poker tracker" (competes with PT4/HM3/H2N on their terms and loses) to "poker analytics engine" (creates a new category). It's the difference between:

- **Tracker**: "Here are your stats" → commodity
- **Analytics engine**: "Ask any question about your game" → new category, no competitors

This is the screenshot that sells the product. The GIF that gets upvoted on Reddit. The feature that makes the Hacker News headline work.

### The two-layer architecture

The query engine is **two features, not one**:

1. **Visual Query Builder** (Layer 1 — the foundation) — dropdown-based: pick measure, add filters, group by, see results. No API key needed. Deterministic SQL generation. The daily-driver tool that 80% of users will use. Inspired by Metabase's pipeline builder, scoped to poker's domain.

2. **Natural Language Query** (Layer 2 — on top) — type a question in English, get SQL + results. Requires API key. Handles the long tail of questions the builder can't express. The marketing headline.

The NL engine sits on top of the visual builder. Both produce SQL. Both execute via the same `POST /api/query/sql` endpoint. The semantic layer (`poker_glossary.yaml`) powers both: metrics become builder dropdowns AND LLM context.

```
                    ┌─────────────────────┐
                    │  Natural Language    │  ← "Ask anything" (requires API key)
                    │  (long-tail queries) │
                    └─────────┬───────────┘
                              │ generates SQL
                    ┌─────────▼───────────┐
                    │  Visual Builder      │  ← Dropdowns (no API key needed)
                    │  (daily-driver)      │
                    └─────────┬───────────┘
                              │ generates SQL
                    ┌─────────▼───────────┐
                    │  POST /api/query/sql │  ← Shared execution layer
                    │  (DuckDB read cursor)│
                    └─────────────────────┘
```

### References

- [PRODUCT-VISION.md](../vision/PRODUCT-VISION.md) — full "PostHog for Poker" concept
- [EXTENSIBILITY.md](../vision/EXTENSIBILITY.md) — Layer 1 (API + SQL endpoint)
- [ROADMAP.md](../../ROADMAP.md) — Phase 0, Weeks 2-4

---

## 2. Goals & Non-Goals

### Goals

1. **Visual query builder that works out of the box.** Pick a measure, add filters, group by a dimension, see results. No API key, no typing, no SQL knowledge. This is the daily-driver feature.
2. **Natural language queries for the long tail.** Type any question in English, get SQL + results. Handles questions the builder can't express. This is the marketing headline.
3. **Trust through transparency.** Both builder and NL show the generated SQL. Users can verify, edit, and re-run. No black box.
4. **Zero cost to us.** BYOK (Bring Your Own Key) for NL queries. The visual builder needs no API key at all.
5. **Power user escape hatch.** Direct SQL execution endpoint for Jupyter, scripts, and "Edit & Re-run" flows.
6. **Foundation for future features.** The semantic layer and SQL endpoint become the base for saved views, AI leak detection, and the plugin system's stat registration.

### Non-Goals (deferred)

- **Saved queries / views.** Phase 2.
- **Auto-generated charts from query results.** Phase 2. V1 shows tables only.
- **Local model fallback** (Ollama / DuckDB-NSQL). Phase 3.
- **Prompt caching optimization.** Post-launch, based on usage patterns.
- **Query accuracy telemetry.** Post-launch.
- **Streaming NL responses.** V1 waits for full completion. Streaming is a polish item.
- **User-configurable category definitions** (custom board texture groups, custom hand strength tiers, custom sizing buckets with AND/OR/NOT logic like H2N). V1 ships with sensible defaults. User customization is Phase 2.

---

## 3. User Stories

### P0 — Must have for launch

| # | As a... | I want to... | So that... | Acceptance |
|---|---------|-------------|-----------|------------|
| U1 | Player | Pick a stat from a dropdown, add filters, and see results | I can explore my data without typing anything | Measure + filter + group by → table of results |
| U2 | Player | Filter by position, stakes, date, pot type, IP/OOP | I can analyze specific spots I care about | All common poker filters available as dropdowns |
| U3 | Player | Group results by position, time period, pot type, opponent type | I can compare my play across dimensions | GROUP BY dropdown with common dimensions |
| U4 | Player | See the generated SQL for any visual query | I can trust, verify, and learn from the results | Collapsible "Show SQL" under every result |
| U5 | Player | Type a question in English and get results | I can ask any question the builder can't express | NL question → SQL → table of results in <5s |
| U6 | Player | Click a suggested question to get started with NL | I don't face a blank input with no idea what to ask | 8 suggested questions visible on NL tab |
| U7 | Player | Edit any generated SQL and re-run it | I can refine queries from the builder or NL engine | Textarea with "Run" button, results update |
| U8 | Player | Add my Anthropic API key in Settings | I can use the NL query engine | Settings field, masked display, persisted in DuckDB |
| U9 | Player | See a clear error when my query fails | I know what went wrong and can adjust | Error message + failed SQL + hint |
| U10 | Power user | Execute raw SQL via API | I can query my data from Jupyter, scripts, or external tools | `POST /api/query/sql` endpoint |

### P1 — Should have for launch

| # | As a... | I want to... | So that... | Acceptance |
|---|---------|-------------|-----------|------------|
| U11 | Player | See my query history in the current session | I can revisit previous results without re-typing | Scrollable list of past queries |
| U12 | Player | See how long the query took | I have feedback that the system is working | "Query took 42ms" footer |
| U13 | Player | Choose between Haiku (fast/cheap) and Sonnet (smart/expensive) | I can trade off cost vs accuracy for complex questions | Model selector in Settings |
| U14 | Player | Copy the generated SQL | I can paste it into a notebook or share it | "Copy SQL" button, clipboard feedback |

### P2 — Deferred

| # | As a... | I want to... | Deferred to... |
|---|---------|-------------|---------------|
| U15 | Player | Save a query and re-run it later | Phase 2 — Saved Views |
| U16 | Player | See a chart auto-generated from results | Phase 2 — Auto-visualization |
| U17 | Player | Use NL queries without an API key | Phase 3 — Local model via Ollama |

---

## 4. Architecture Overview

### System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (React)                                                │
│                                                                 │
│  QueryPage  ←── two tabs: [Builder] [Ask]                       │
│  │                                                              │
│  ├── BuilderTab (visual query construction)                     │
│  │   ├── MeasurePicker (dropdown: VPIP, Winrate, 3-Bet, ...)   │
│  │   ├── FilterBar (+ button → position, stakes, date, ...)    │
│  │   ├── GroupByPicker (dropdown: position, month, pot type)    │
│  │   ├── SqlPreview (live-updating, collapsible)                │
│  │   └── RunButton → POST /api/query/sql                       │
│  │                                                              │
│  ├── AskTab (natural language)                                  │
│  │   ├── QueryBar (input + submit)                              │
│  │   ├── SuggestedQuestions (clickable cards)                   │
│  │   └── → POST /api/query/ask                                  │
│  │                                                              │
│  ├── ResultsPanel (shared by both tabs)                         │
│  │   ├── Summary (NL only — plain English)                      │
│  │   ├── DataTable (shadcn Table)                               │
│  │   ├── SqlBlock (collapsible, shows generated SQL)            │
│  │   └── Actions (Copy SQL, Edit & Re-run)                      │
│  │                                                              │
│  └── QueryHistory (session-only)                                │
│                                                                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│ Backend (FastAPI)                                               │
│                                                                 │
│  app/api/query.py                                               │
│  ├── POST /api/query/ask          (NL → SQL → execute)          │
│  ├── POST /api/query/sql          (direct SQL execution)        │
│  ├── GET  /api/query/schema       (schema documentation)        │
│  └── GET  /api/query/measures     (available metrics+filters    │
│                                    for builder dropdowns)       │
│                                                                 │
│  app/query/                                                     │
│  ├── semantic_layer.py    (load + merge glossary YAML)          │
│  ├── prompt_builder.py    (assemble system prompt for NL)       │
│  ├── sql_builder.py       (generate SQL from builder params)    │
│  ├── sql_validator.py     (read-only enforcement)               │
│  └── poker_glossary.yaml  (metrics, filters, concepts, examples)│
│                                                                 │
│  DuckDB (read-only cursor via get_read_cursor())                │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│ Anthropic API (user's key — only for NL queries)                │
│  Claude Haiku 4.5  — default, ~$0.001-0.005/query              │
│  Claude Sonnet 4.6 — optional, ~$0.015/query                   │
└─────────────────────────────────────────────────────────────────┘
```

### Data flow: Natural Language query

```
User: "What is my winrate by position this month?"
  │
  ▼
POST /api/query/ask { question: "...", workspace_id: 1 }
  │
  ├─ 1. Load poker_glossary.yaml
  ├─ 2. Look up hero_id from workspaces table (workspace_id=1)
  ├─ 3. Build system prompt:
  │     ┌──────────────────────────────────────────┐
  │     │ SYSTEM PROMPT                            │
  │     │ • Full DDL (10 tables, ~80 columns)      │
  │     │ • Semantic layer (40 metrics, filters)   │
  │     │ • 30 example Q&A pairs                   │
  │     │ • Context: hero_id=42, workspace_id=1    │
  │     │ • Rules: JOIN patterns, DuckDB syntax    │
  │     └──────────────────────────────────────────┘
  ├─ 4. USER message: the question
  ├─ 5. Call Anthropic API → get SQL response
  ├─ 6. Validate SQL (read-only? row limit?)
  ├─ 7. Execute SQL on DuckDB read cursor
  │     ├─ Success → columns + rows
  │     └─ Error → send error back to LLM → retry once
  ├─ 8. Second LLM call: "Summarize these results in 1-2 sentences"
  │     (or: structured output in step 5 with sql + summary fields)
  └─ 9. Return response
        {
          question: "What is my winrate by position this month?",
          sql: "SELECT hp.position, ...",
          columns: ["position", "winrate_bb100", "hands"],
          rows: [["BTN", 8.2, 1204], ...],
          row_count: 6,
          summary: "Your best position is BTN at +8.2 bb/100...",
          execution_time_ms: 42,
          retried: false
        }
```

### Data flow: Direct SQL execution

```
POST /api/query/sql { sql: "SELECT ...", workspace_id: 1 }
  │
  ├─ 1. Validate SQL (read-only? no dangerous statements?)
  ├─ 2. Inject workspace_id guard (optional — see §5.6)
  ├─ 3. Execute on DuckDB read cursor (LIMIT 500 enforced)
  └─ 4. Return { columns, rows, row_count, execution_time_ms }
```

---

## 5. Backend Design

### 5.1 New files

```
backend/
  app/
    api/
      query.py              # FastAPI router: /api/query/ask, /sql, /schema
    query/
      __init__.py
      semantic_layer.py      # Load & merge poker_glossary.yaml
      prompt_builder.py      # Assemble the full system prompt
      sql_validator.py       # Read-only enforcement, row limit injection
      poker_glossary.yaml    # The semantic layer definition
```

### 5.2 Semantic Layer (`poker_glossary.yaml`)

This is the single highest-impact artifact. It serves three purposes:
1. **LLM context** — tells the model what poker terms mean in SQL
2. **Visual builder dropdowns** (Phase 2) — metrics and filters become UI controls
3. **Public documentation** — published as part of schema docs

#### Structure

```yaml
# poker_glossary.yaml — OHM Semantic Layer
# Maps poker concepts to DuckDB SQL patterns.
# Used by the NL query engine, visual builder, and schema docs.

# ─── TABLES ──────────────────────────────────────────────────────
# Brief descriptions so the LLM knows what each table contains.
tables:
  hands:
    description: >
      One row per poker hand played. Contains metadata: timestamp,
      stakes, game type, table info, and the raw hand history text.
    key_columns:
      - id: "Unique hand ID (string, e.g. 'RC1234567890')"
      - workspace_id: "Workspace this hand belongs to (always filter by this)"
      - played_at: "Timestamp when the hand was played"
      - stakes: "Stakes string, e.g. '$0.25/$0.50'"
      - sb_amount: "Small blind amount in dollars"
      - bb_amount: "Big blind amount in dollars"
      - game_type: "Always 'Hold''em No Limit' for now"
      - game_mode: "'Fast Fold' for Rush/Zoom, '' for regular"
      - table_size: "Number of seats (usually 6)"
      - is_cashout: "Whether someone used the cashout insurance feature"
      - rit_boards: "Number of Run It Twice boards (1 = normal, 2 = RIT)"

  hand_players:
    description: >
      One row per player per hand. Contains all stat flags (VPIP, PFR,
      3-bet, c-bet, etc.), financial results (won_bb, rake), position,
      and hole cards. This is the main table for stat queries.
    key_columns:
      - hand_id: "FK to hands.id"
      - workspace_id: "FK to hands.workspace_id (always join on BOTH hand_id AND workspace_id)"
      - player_id: "FK to players.id"
      - position: "One of: EP, MP, CO, BTN, SB, BB"
      - stack_bb: "Starting stack in big blinds"
      - won_bb: "Net result for this hand in big blinds (positive = won, negative = lost)"
      - all_in_ev_bb: "Expected value in BB for all-in hands (equals won_bb for non-all-in)"
      - card1: "First hole card (e.g. 'Ah', 'Ks')"
      - card2: "Second hole card"
      - is_3bet_pot: "Whether this hand was played in a 3-bet pot"
      - pot_type: "'SRP' (single raised pot), '3BP' (3-bet pot), 'LMP' (limped pot), etc."
      - is_multiway: "Whether more than 2 players saw the flop"
      - postflop_ip: "Whether this player was in position postflop (true/false/null)"

  players:
    description: >
      One row per unique player per site. Contains username and metadata.
    key_columns:
      - id: "Unique player ID (integer)"
      - username: "Player's screen name"
      - site_id: "FK to sites.id"

  actions:
    description: >
      Every action in every hand: fold, check, call, bet, raise.
      Use this for bet sizing analysis, action sequences, and
      street-by-street breakdowns.
    key_columns:
      - hand_id: "FK to hands.id"
      - workspace_id: "FK to hands.workspace_id"
      - player_id: "FK to players.id"
      - street: "One of: preflop, flop, turn, river"
      - action_order: "Sequential order within the hand"
      - action_type: "One of: fold, check, call, bet, raise, post_sb, post_bb"
      - amount: "Dollar amount of the action"
      - amount_bb: "Amount in big blinds"
      - is_all_in: "Whether this action put the player all-in"

  board_cards:
    description: >
      Community cards dealt on flop/turn/river. Each card is a separate
      row. Use for board texture analysis.
    key_columns:
      - hand_id: "FK to hands.id"
      - street: "flop, turn, or river"
      - card: "Card string (e.g. 'Ah', 'Ks', '2c')"
      - card_order: "1-5 (flop=1-3, turn=4, river=5)"
      - board_number: "1 for normal, 1 or 2 for Run It Twice"

  sites:
    description: "Poker sites: GGPoker (GG), PokerStars (PS), 888poker (888), WPN, Winamax (WMX), iPoker (IP), partypoker (PP)."
    key_columns:
      - id: "Integer site ID"
      - code: "Short code: GG, PS, 888, WPN, WMX, IP, PP"
      - name: "Full name"

  hand_tags:
    description: "User-created tags on hands (e.g. 'bluff', 'cooler', 'review')."
    key_columns:
      - hand_id: "FK to hands.id"
      - tag: "Tag string"

  hand_notes:
    description: "User-created notes on individual hands."
    key_columns:
      - hand_id: "FK to hands.id"
      - note: "Free-text note"

  workspaces:
    description: "Workspaces for separating data (e.g., different stakes, sites, or game types)."
    key_columns:
      - id: "Workspace ID"
      - hero_username: "Hero's username in this workspace"
      - hero_site: "Hero's site code in this workspace"

  player_classifications:
    description: "Player type labels: UNK (unknown), TAG (tight-aggressive), LAG (loose-aggressive), NIT, REC (recreational), MAN (maniac)."
    key_columns:
      - player_id: "FK to players.id"
      - workspace_id: "FK to workspaces.id"
      - player_type: "One of: UNK, TAG, LAG, NIT, REC, MAN"


# ─── METRICS ─────────────────────────────────────────────────────
# Poker stats with their SQL formulas. Each metric operates on
# the hand_players table (aliased as hp) joined to hands (aliased as h).
#
# Convention:
#   - Boolean flags: COUNT(*) FILTER (WHERE flag) / COUNT(*) or NULLIF(opps, 0)
#   - Some stats use NULLIF on opportunities to return NULL when denominator is 0
#   - Percentages are multiplied by 100.0

metrics:
  # ── Preflop Core ──
  vpip:
    name: "VPIP"
    description: "Voluntarily Put $ In Pot — percentage of hands where player voluntarily put chips in preflop (excludes posting blinds)"
    sql: "COUNT(*) FILTER (WHERE hp.vpip) * 100.0 / COUNT(*)"
    category: preflop

  pfr:
    name: "PFR"
    description: "Pre-Flop Raise — percentage of hands where player raised preflop"
    sql: "COUNT(*) FILTER (WHERE hp.pfr) * 100.0 / COUNT(*)"
    category: preflop

  open_raise:
    name: "Open Raise"
    description: "Percentage of time player open-raises when given the opportunity (no prior raise)"
    sql: "COUNT(*) FILTER (WHERE hp.open_raise) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.open_raise_opp), 0)"
    category: preflop

  three_bet:
    name: "3-Bet"
    description: "3-bet percentage — how often player re-raises a raiser preflop"
    sql: "COUNT(*) FILTER (WHERE hp.three_bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.three_bet_opp), 0)"
    category: preflop

  four_bet:
    name: "4-Bet"
    description: "4-bet percentage — how often player re-raises a 3-bet"
    sql: "COUNT(*) FILTER (WHERE hp.four_bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.four_bet_opp), 0)"
    category: preflop

  five_bet:
    name: "5-Bet"
    description: "5-bet percentage — how often player re-raises a 4-bet"
    sql: "COUNT(*) FILTER (WHERE hp.five_bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.five_bet_opp), 0)"
    category: preflop

  fold_to_3bet:
    name: "Fold to 3-Bet"
    description: "How often player folds when facing a 3-bet after opening"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_3bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.fold_to_3bet IS NOT NULL), 0)"
    category: preflop

  fold_to_4bet:
    name: "Fold to 4-Bet"
    description: "How often player folds when facing a 4-bet"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_4bet) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.fold_to_4bet IS NOT NULL), 0)"
    category: preflop

  call_open_raise:
    name: "Call Open Raise"
    description: "How often player cold-calls an open raise"
    sql: "COUNT(*) FILTER (WHERE hp.call_open_raise) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.call_open_raise_opp), 0)"
    category: preflop

  limp:
    name: "Limp"
    description: "Percentage of hands where player limped preflop (called the big blind without a raise)"
    sql: "COUNT(*) FILTER (WHERE hp.limp) * 100.0 / COUNT(*)"
    category: preflop

  limp_fold:
    name: "Limp-Fold"
    description: "How often player folds after limping when facing a raise"
    sql: "COUNT(*) FILTER (WHERE hp.limp AND hp.limp_fold) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.limp), 0)"
    category: preflop

  squeeze:
    name: "Squeeze"
    description: "How often player squeezes (3-bets after a raise and one or more callers)"
    sql: "COUNT(*) FILTER (WHERE hp.squeeze) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.squeeze_opp), 0)"
    category: preflop

  # ── Steal / Blind Defense ──
  steal:
    name: "Steal"
    description: "How often player attempts to steal blinds from CO/BTN/SB"
    sql: "COUNT(*) FILTER (WHERE hp.steal_attempted) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.steal_opp), 0)"
    category: steal

  fold_to_steal:
    name: "Fold to Steal"
    description: "How often player folds when facing a steal attempt from CO/BTN/SB"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_steal) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.faced_steal), 0)"
    category: steal

  bb_defense:
    name: "BB Defense"
    description: "How often BB defends (calls or raises) vs a single raise"
    sql: "COUNT(*) FILTER (WHERE hp.bb_defense) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.bb_defense_opp), 0)"
    category: steal

  # ── Postflop C-Bet ──
  cbet_flop:
    name: "C-Bet Flop"
    description: "Continuation bet on flop — how often player bets the flop after being the preflop aggressor"
    sql: "COUNT(*) FILTER (WHERE hp.cbet_flop) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_flop_opp), 0)"
    category: postflop

  cbet_turn:
    name: "C-Bet Turn"
    description: "Continuation bet on turn — second barrel frequency"
    sql: "COUNT(*) FILTER (WHERE hp.cbet_turn) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_turn_opp), 0)"
    category: postflop

  cbet_river:
    name: "C-Bet River"
    description: "Continuation bet on river — third barrel frequency"
    sql: "COUNT(*) FILTER (WHERE hp.cbet_river) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_river_opp), 0)"
    category: postflop

  fold_to_cbet_flop:
    name: "Fold to C-Bet Flop"
    description: "How often player folds when facing a flop continuation bet"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_cbet_flop) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.fold_to_cbet_flop IS NOT NULL), 0)"
    category: postflop

  fold_to_cbet_turn:
    name: "Fold to C-Bet Turn"
    description: "How often player folds when facing a turn continuation bet"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_cbet_turn) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.fold_to_cbet_turn IS NOT NULL), 0)"
    category: postflop

  fold_to_cbet_river:
    name: "Fold to C-Bet River"
    description: "How often player folds when facing a river continuation bet"
    sql: "COUNT(*) FILTER (WHERE hp.fold_to_cbet_river) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.fold_to_cbet_river IS NOT NULL), 0)"
    category: postflop

  donk_bet_flop:
    name: "Donk Bet Flop"
    description: "How often player leads into the preflop aggressor on the flop"
    sql: "COUNT(*) FILTER (WHERE hp.donk_bet_flop) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.donk_bet_flop_opp), 0)"
    category: postflop

  # ── Aggression ──
  af_flop:
    name: "Aggression Factor Flop"
    description: "Flop aggression factor: (bets + raises) / calls. Higher = more aggressive."
    sql: "(SUM(hp.flop_bets) + SUM(hp.flop_raises)) * 1.0 / NULLIF(SUM(hp.flop_calls), 0)"
    category: aggression

  af_turn:
    name: "Aggression Factor Turn"
    description: "Turn aggression factor: (bets + raises) / calls"
    sql: "(SUM(hp.turn_bets) + SUM(hp.turn_raises)) * 1.0 / NULLIF(SUM(hp.turn_calls), 0)"
    category: aggression

  af_river:
    name: "Aggression Factor River"
    description: "River aggression factor: (bets + raises) / calls"
    sql: "(SUM(hp.river_bets) + SUM(hp.river_raises)) * 1.0 / NULLIF(SUM(hp.river_calls), 0)"
    category: aggression

  afq_flop:
    name: "Aggression Frequency Flop"
    description: "Flop aggression frequency: (bets + raises) / total actions * 100"
    sql: "(SUM(hp.flop_bets) + SUM(hp.flop_raises)) * 100.0 / NULLIF(SUM(hp.flop_bets) + SUM(hp.flop_raises) + SUM(hp.flop_calls) + SUM(hp.flop_checks) + SUM(hp.flop_folds), 0)"
    category: aggression

  # ── Showdown ──
  wtsd:
    name: "WTSD"
    description: "Went to Showdown — how often player goes to showdown after seeing the flop"
    sql: "COUNT(*) FILTER (WHERE hp.went_to_showdown) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.saw_flop), 0)"
    category: showdown

  wsd:
    name: "W$SD"
    description: "Won $ at Showdown — how often player wins when reaching showdown"
    sql: "COUNT(*) FILTER (WHERE hp.won_at_showdown) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.went_to_showdown), 0)"
    category: showdown

  wwsf:
    name: "WWSF"
    description: "Won When Saw Flop — percentage of hands won (any amount > 0) after seeing the flop"
    sql: "COUNT(*) FILTER (WHERE hp.saw_flop AND hp.won_bb > 0) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE hp.saw_flop), 0)"
    category: showdown

  # ── Financial ──
  winrate:
    name: "Win Rate"
    description: "Win rate in big blinds per 100 hands (bb/100). The primary measure of how much a player wins."
    sql: "SUM(hp.won_bb) * 100.0 / COUNT(*)"
    category: financial

  ev_winrate:
    name: "EV Win Rate"
    description: "All-in equity-adjusted win rate in bb/100. Removes all-in luck."
    sql: "SUM(hp.all_in_ev_bb) * 100.0 / COUNT(*)"
    category: financial

  total_won_bb:
    name: "Total Won (BB)"
    description: "Total net result in big blinds"
    sql: "SUM(hp.won_bb)"
    category: financial

  total_rake_bb:
    name: "Total Rake (BB)"
    description: "Total rake paid in big blinds"
    sql: "SUM(hp.rake_bb)"
    category: financial

  hands_played:
    name: "Hands Played"
    description: "Total number of hands in the sample"
    sql: "COUNT(*)"
    category: financial


# ─── FILTERS ─────────────────────────────────────────────────────
# Available filter dimensions with their column mappings and allowed values.

filters:
  position:
    description: "Player's seat position"
    column: hp.position
    values: [EP, MP, CO, BTN, SB, BB]

  stakes:
    description: "Table stakes (blind levels)"
    column: h.stakes
    examples: ["$0.01/$0.02", "$0.02/$0.05", "$0.05/$0.10", "$0.10/$0.25", "$0.25/$0.50", "$0.50/$1.00"]
    note: "Use exact string match including the $ signs"

  date:
    description: "When the hand was played"
    column: h.played_at
    note: "Use h.played_at >= '2026-03-01' AND h.played_at < '2026-04-01' for date ranges. DuckDB supports TIMESTAMP comparisons with string literals."

  game_mode:
    description: "Regular tables vs fast-fold (Rush & Cash, Zoom)"
    column: h.game_mode
    values: ["", "Fast Fold"]
    note: "Empty string '' = regular tables. 'Fast Fold' = Rush/Zoom."

  pot_type:
    description: "The type of pot preflop action created"
    column: hp.pot_type
    values: [SRP, 3BP, LMP]
    note: "SRP = single raised pot, 3BP = 3-bet pot, LMP = limped pot"

  is_3bet_pot:
    description: "Whether the hand was played in a 3-bet pot"
    column: hp.is_3bet_pot
    values: [true, false]

  is_multiway:
    description: "Whether more than 2 players saw the flop"
    column: hp.is_multiway
    values: [true, false]

  postflop_ip:
    description: "Whether the player was in position (acted last) postflop"
    column: hp.postflop_ip
    values: [true, false]
    note: "NULL when player didn't see a flop"

  player_type:
    description: "Opponent classification"
    table: player_classifications
    column: pc.player_type
    values: [UNK, TAG, LAG, NIT, REC, MAN]
    note: "JOIN player_classifications pc ON pc.player_id = hp.player_id AND pc.workspace_id = h.workspace_id"

  hole_cards:
    description: "Player's hole cards"
    columns: [hp.card1, hp.card2]
    note: >
      Cards are stored as two-character strings: rank + suit.
      Ranks: 2-9, T, J, Q, K, A. Suits: h, d, c, s.
      Example: 'Ah' = Ace of hearts, 'Ts' = Ten of spades.
      To query a hand like AKs (Ace-King suited): WHERE
      ((hp.card1[1] = 'A' AND hp.card2[1] = 'K') OR (hp.card1[1] = 'K' AND hp.card2[1] = 'A'))
      AND hp.card1[2] = hp.card2[2]


# ─── CONCEPTS ────────────────────────────────────────────────────
# Domain concepts the LLM should understand.

concepts:
  hero:
    description: "The player identified as the hero (the user). Use player_id = {hero_id} to filter for hero's hands."
    sql_hint: "hp.player_id = {hero_id}"

  villain:
    description: "Any non-hero player. When the user says 'villain' without a name, it means all opponents."
    sql_hint: "hp.player_id != {hero_id}"

  reg:
    description: "Regular player — a skilled player who grinds. Classified as TAG, LAG, or NIT."
    sql_hint: "pc.player_type IN ('TAG', 'LAG', 'NIT')"

  fish:
    description: "Recreational player — a weaker player. Classified as REC or MAN."
    sql_hint: "pc.player_type IN ('REC', 'MAN')"

  session:
    description: >
      A continuous period of play. OHM detects sessions by gaps of 30+ minutes between hands.
      Sessions are computed on-the-fly, not stored. For session-level analysis, group by
      date_trunc('day', h.played_at) or use the /api/sessions endpoints.

  bb:
    description: "Big blind — the standard unit for measuring poker results. 'bb/100' means big blinds won per 100 hands."

  suited:
    description: "Two hole cards of the same suit. Check hp.card1[2] = hp.card2[2]."

  offsuit:
    description: "Two hole cards of different suits. Check hp.card1[2] != hp.card2[2]."

  pocket_pair:
    description: "Two hole cards of the same rank. Check hp.card1[1] = hp.card2[1]."

  ip:
    description: "In Position — acting last postflop. hp.postflop_ip = true."

  oop:
    description: "Out of Position — acting first postflop. hp.postflop_ip = false."


# ─── EXAMPLES ────────────────────────────────────────────────────
# Example question → SQL pairs. This is the most impactful accuracy lever.
# The LLM uses these as few-shot examples.
#
# IMPORTANT: All examples must use {hero_id} and {workspace_id} placeholders.
# These are replaced at runtime with actual values before sending to the LLM.

examples:
  - question: "What is my VPIP?"
    sql: |
      SELECT
        COUNT(*) FILTER (WHERE hp.vpip) * 100.0 / COUNT(*) AS vpip_pct,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}

  - question: "What is my winrate by position?"
    sql: |
      SELECT
        hp.position,
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
      GROUP BY hp.position
      ORDER BY CASE hp.position
        WHEN 'EP' THEN 1 WHEN 'MP' THEN 2 WHEN 'CO' THEN 3
        WHEN 'BTN' THEN 4 WHEN 'SB' THEN 5 WHEN 'BB' THEN 6 END

  - question: "What is my 3bet% from the button?"
    sql: |
      SELECT
        COUNT(*) FILTER (WHERE hp.three_bet) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.three_bet_opp), 0) AS three_bet_pct,
        COUNT(*) FILTER (WHERE hp.three_bet_opp) AS opportunities
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND hp.position = 'BTN'
        AND h.workspace_id = {workspace_id}

  - question: "Which opponent have I lost the most to?"
    sql: |
      SELECT
        p.username,
        ROUND(SUM(hero_hp.won_bb), 2) AS hero_total_bb,
        COUNT(*) AS hands_together
      FROM hand_players hero_hp
      JOIN hands h ON hero_hp.hand_id = h.id AND hero_hp.workspace_id = h.workspace_id
      JOIN hand_players opp_hp ON opp_hp.hand_id = h.id AND opp_hp.workspace_id = h.workspace_id
        AND opp_hp.player_id != hero_hp.player_id
      JOIN players p ON opp_hp.player_id = p.id
      WHERE hero_hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
      GROUP BY p.username
      HAVING COUNT(*) >= 20
      ORDER BY hero_total_bb ASC
      LIMIT 10

  - question: "Compare my winrate in 3bet pots vs single raised pots"
    sql: |
      SELECT
        hp.pot_type,
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.pot_type IN ('SRP', '3BP')
      GROUP BY hp.pot_type

  - question: "Show me my most profitable hand combos"
    sql: |
      SELECT
        CASE WHEN hp.card1 > hp.card2 THEN hp.card1 || hp.card2
             ELSE hp.card2 || hp.card1 END AS hand_combo,
        COUNT(*) AS times_dealt,
        ROUND(SUM(hp.won_bb), 1) AS total_won_bb,
        ROUND(SUM(hp.won_bb) / COUNT(*), 2) AS bb_per_hand
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.card1 IS NOT NULL
      GROUP BY hand_combo
      HAVING COUNT(*) >= 5
      ORDER BY total_won_bb DESC
      LIMIT 20

  - question: "How does my VPIP change over time?"
    sql: |
      SELECT
        DATE_TRUNC('week', h.played_at) AS week,
        COUNT(*) FILTER (WHERE hp.vpip) * 100.0 / COUNT(*) AS vpip_pct,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
      GROUP BY week
      ORDER BY week

  - question: "What is my winrate when I cbet the flop and get called?"
    sql: |
      SELECT
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.cbet_flop = true
        AND hp.saw_turn = true

  - question: "Show me hands where I lost more than 50bb"
    sql: |
      SELECT
        h.id AS hand_id,
        h.played_at,
        h.stakes,
        hp.position,
        hp.card1 || hp.card2 AS cards,
        ROUND(hp.won_bb, 1) AS won_bb
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.won_bb < -50
      ORDER BY hp.won_bb ASC
      LIMIT 50

  - question: "What is my winrate against fish vs regs?"
    sql: |
      SELECT
        CASE
          WHEN pc.player_type IN ('REC', 'MAN') THEN 'Fish'
          WHEN pc.player_type IN ('TAG', 'LAG', 'NIT') THEN 'Reg'
          ELSE 'Unknown'
        END AS opponent_type,
        ROUND(SUM(hero_hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        COUNT(*) AS hands
      FROM hand_players hero_hp
      JOIN hands h ON hero_hp.hand_id = h.id AND hero_hp.workspace_id = h.workspace_id
      JOIN hand_players opp_hp ON opp_hp.hand_id = h.id AND opp_hp.workspace_id = h.workspace_id
        AND opp_hp.player_id != hero_hp.player_id
      JOIN player_classifications pc ON pc.player_id = opp_hp.player_id
        AND pc.workspace_id = h.workspace_id
      WHERE hero_hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
      GROUP BY opponent_type
      ORDER BY opponent_type

  - question: "How often do I cbet the flop in position vs out of position?"
    sql: |
      SELECT
        CASE WHEN hp.postflop_ip = true THEN 'In Position'
             WHEN hp.postflop_ip = false THEN 'Out of Position'
             ELSE 'N/A' END AS position_type,
        COUNT(*) FILTER (WHERE hp.cbet_flop) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_flop_opp), 0) AS cbet_pct,
        COUNT(*) FILTER (WHERE hp.cbet_flop_opp) AS opportunities
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.cbet_flop_opp = true
      GROUP BY position_type

  - question: "Show me my steal and blind defense stats"
    sql: |
      SELECT
        'Steal Attempt' AS stat,
        COUNT(*) FILTER (WHERE hp.steal_attempted) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.steal_opp), 0) AS percentage,
        COUNT(*) FILTER (WHERE hp.steal_opp) AS opportunities
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}
      UNION ALL
      SELECT
        'Fold to Steal',
        COUNT(*) FILTER (WHERE hp.fold_to_steal) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.faced_steal), 0),
        COUNT(*) FILTER (WHERE hp.faced_steal)
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}
      UNION ALL
      SELECT
        'BB Defense',
        COUNT(*) FILTER (WHERE hp.bb_defense) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.bb_defense_opp), 0),
        COUNT(*) FILTER (WHERE hp.bb_defense_opp)
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}

  - question: "What are villain RegShark99's stats?"
    sql: |
      SELECT
        COUNT(*) AS hands,
        ROUND(COUNT(*) FILTER (WHERE hp.vpip) * 100.0 / COUNT(*), 1) AS vpip,
        ROUND(COUNT(*) FILTER (WHERE hp.pfr) * 100.0 / COUNT(*), 1) AS pfr,
        ROUND(COUNT(*) FILTER (WHERE hp.three_bet) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.three_bet_opp), 0), 1) AS three_bet,
        ROUND(COUNT(*) FILTER (WHERE hp.cbet_flop) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_flop_opp), 0), 1) AS cbet_flop,
        ROUND(COUNT(*) FILTER (WHERE hp.went_to_showdown) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.saw_flop), 0), 1) AS wtsd,
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      JOIN players p ON hp.player_id = p.id
      WHERE p.username = 'RegShark99'
        AND h.workspace_id = {workspace_id}

  - question: "Show my flop cbet funnel: cbet → barrel turn → barrel river"
    sql: |
      SELECT
        'Flop C-Bet' AS stage,
        COUNT(*) FILTER (WHERE hp.cbet_flop) AS did_it,
        COUNT(*) FILTER (WHERE hp.cbet_flop_opp) AS opportunities,
        ROUND(COUNT(*) FILTER (WHERE hp.cbet_flop) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_flop_opp), 0), 1) AS pct
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}
      UNION ALL
      SELECT 'Turn Barrel', COUNT(*) FILTER (WHERE hp.cbet_turn),
        COUNT(*) FILTER (WHERE hp.cbet_turn_opp),
        ROUND(COUNT(*) FILTER (WHERE hp.cbet_turn) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_turn_opp), 0), 1)
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}
      UNION ALL
      SELECT 'River Barrel', COUNT(*) FILTER (WHERE hp.cbet_river),
        COUNT(*) FILTER (WHERE hp.cbet_river_opp),
        ROUND(COUNT(*) FILTER (WHERE hp.cbet_river) * 100.0
          / NULLIF(COUNT(*) FILTER (WHERE hp.cbet_river_opp), 0), 1)
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id} AND h.workspace_id = {workspace_id}

  - question: "What's my winrate per day this month?"
    sql: |
      SELECT
        CAST(h.played_at AS DATE) AS day,
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        ROUND(SUM(hp.won_bb), 1) AS total_bb,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND h.played_at >= DATE_TRUNC('month', CURRENT_DATE)
      GROUP BY day
      ORDER BY day

  - question: "Show hands where I went all-in preflop"
    sql: |
      SELECT
        h.id AS hand_id,
        h.played_at,
        h.stakes,
        hp.position,
        hp.card1 || hp.card2 AS cards,
        ROUND(hp.won_bb, 1) AS won_bb,
        ROUND(hp.all_in_ev_bb, 1) AS ev_bb
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND (hp.preflop_allin_raise = true OR hp.preflop_allin_call = true)
      ORDER BY h.played_at DESC
      LIMIT 50

  - question: "How often do I see a flop?"
    sql: |
      SELECT
        hp.position,
        COUNT(*) FILTER (WHERE hp.saw_flop) * 100.0 / COUNT(*) AS saw_flop_pct,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
      GROUP BY hp.position
      ORDER BY CASE hp.position
        WHEN 'EP' THEN 1 WHEN 'MP' THEN 2 WHEN 'CO' THEN 3
        WHEN 'BTN' THEN 4 WHEN 'SB' THEN 5 WHEN 'BB' THEN 6 END

  - question: "What's the average pot size at each stake level?"
    sql: |
      SELECT
        h.stakes,
        ROUND(AVG(ABS(hp.won_bb)) * 2, 1) AS avg_pot_bb,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE h.workspace_id = {workspace_id}
      GROUP BY h.stakes
      ORDER BY h.bb_amount

  - question: "Show bet sizing analysis on the flop"
    sql: |
      SELECT
        CASE
          WHEN a.amount_bb < 2 THEN 'Small (<2bb)'
          WHEN a.amount_bb < 5 THEN 'Medium (2-5bb)'
          WHEN a.amount_bb < 10 THEN 'Large (5-10bb)'
          ELSE 'Overbet (10bb+)'
        END AS sizing_bucket,
        COUNT(*) AS count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct
      FROM actions a
      JOIN hands h ON a.hand_id = h.id AND a.workspace_id = h.workspace_id
      WHERE a.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND a.street = 'flop'
        AND a.action_type = 'bet'
      GROUP BY sizing_bucket
      ORDER BY MIN(a.amount_bb)

  - question: "What's my winrate in multiway pots vs heads-up?"
    sql: |
      SELECT
        CASE WHEN hp.is_multiway THEN 'Multiway' ELSE 'Heads-up' END AS pot_type,
        ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100,
        COUNT(*) AS hands
      FROM hand_players hp
      JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id
      WHERE hp.player_id = {hero_id}
        AND h.workspace_id = {workspace_id}
        AND hp.saw_flop = true
      GROUP BY pot_type


# ─── JOIN RULES ──────────────────────────────────────────────────
# Critical instructions for the LLM about how to join tables correctly.

join_rules:
  - rule: "ALWAYS join hand_players to hands using BOTH hand_id AND workspace_id"
    correct: "JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id"
    wrong: "JOIN hands h ON hp.hand_id = h.id"
    why: "Without workspace_id, queries cross workspace boundaries and return wrong results"

  - rule: "ALWAYS filter by workspace_id = {workspace_id}"
    correct: "WHERE h.workspace_id = {workspace_id}"
    why: "Users may have multiple workspaces. Queries must be scoped to the active one."

  - rule: "Use {hero_id} for hero queries, not username string matching"
    correct: "WHERE hp.player_id = {hero_id}"
    wrong: "WHERE p.username = 'Hero'"
    why: "hero_id is a resolved integer. Username matching requires a JOIN to players."

  - rule: "When querying opponent stats, join player_classifications for player type"
    correct: "JOIN player_classifications pc ON pc.player_id = hp.player_id AND pc.workspace_id = h.workspace_id"

  - rule: "Boolean columns use = true, not just WHERE col"
    correct: "WHERE hp.vpip = true"
    note: "DuckDB booleans are nullable. WHERE hp.vpip would skip NULLs, which is usually correct, but = true is explicit and safer."

  - rule: "Use FILTER (WHERE ...) for conditional aggregates"
    correct: "COUNT(*) FILTER (WHERE hp.vpip)"
    wrong: "SUM(CASE WHEN hp.vpip THEN 1 ELSE 0 END)"
    why: "DuckDB FILTER syntax is cleaner. Both work but FILTER is idiomatic DuckDB."
```

### 5.3 System Prompt Construction (`prompt_builder.py`)

The system prompt is assembled at query time from three sources:

1. **DDL** — the actual `CREATE TABLE` statements from `db.py`, extracted at startup
2. **Semantic layer** — `poker_glossary.yaml` loaded and rendered
3. **Runtime context** — `hero_id`, `hero_username`, `workspace_id`

```python
# prompt_builder.py — pseudocode

def build_system_prompt(hero_id: int, hero_username: str, workspace_id: int) -> str:
    """Assemble the full system prompt for the NL query engine."""
    glossary = load_glossary()  # poker_glossary.yaml

    return f"""You are a poker analytics SQL assistant for DuckDB.
Your job is to translate natural language poker questions into DuckDB SQL queries.

## Database Schema

{_render_tables(glossary['tables'])}

## Poker Metrics (stat definitions with SQL formulas)

{_render_metrics(glossary['metrics'])}

## Available Filters

{_render_filters(glossary['filters'])}

## Poker Concepts

{_render_concepts(glossary['concepts'])}

## Critical JOIN Rules

{_render_join_rules(glossary['join_rules'])}

## Context for this query
- Hero player_id: {hero_id}
- Hero username: "{hero_username}"
- Workspace ID: {workspace_id}

## Output Rules
1. Return a JSON object with two fields:
   - "sql": the DuckDB SQL query (string)
   - "summary_hint": a 5-10 word hint about what the query computes (string)
2. Do NOT include any explanation outside the JSON.
3. The SQL must be read-only (SELECT only — no INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY, EXPORT).
4. Limit results to 500 rows maximum (add LIMIT 500 if not already limited).
5. Use ROUND() for decimal results to keep output clean.
6. Use the DuckDB FILTER (WHERE ...) syntax for conditional aggregates.
7. Always scope queries to workspace_id = {workspace_id}.
8. For hero queries, use player_id = {hero_id}.
9. For date filtering, use DuckDB functions: CURRENT_DATE, DATE_TRUNC, INTERVAL.
10. When grouping by position, order EP→MP→CO→BTN→SB→BB.
11. Column aliases should be human-readable (e.g., winrate_bb100 not wr).

## Example Queries

{_render_examples(glossary['examples'], hero_id, workspace_id)}
"""
```

**Token budget estimate**: ~3,000-4,000 tokens for the system prompt. With Haiku 4.5's 200K context window, this leaves ample room.

### 5.4 SQL Validator (`sql_validator.py`)

Defense-in-depth: even though the LLM is instructed to generate read-only SQL, we validate before execution.

```python
# sql_validator.py

import re

# Statements that modify data or schema
_DANGEROUS_PATTERNS = [
    r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b',
    r'\bALTER\b', r'\bCREATE\b', r'\bTRUNCATE\b', r'\bREPLACE\b',
    r'\bMERGE\b', r'\bGRANT\b', r'\bREVOKE\b',
    r'\bCOPY\b', r'\bEXPORT\b', r'\bIMPORT\b',
    r'\bATTACH\b', r'\bDETACH\b',
    r'\bCALL\b', r'\bEXECUTE\b', r'\bEXEC\b',
    r'\bSET\b\s', r'\bPRAGMA\b',
    r'\bLOAD\b', r'\bINSTALL\b',
]

_DANGEROUS_RE = re.compile(
    '|'.join(_DANGEROUS_PATTERNS),
    re.IGNORECASE,
)

MAX_ROWS = 500

class SQLValidationError(Exception):
    pass

def validate_read_only(sql: str) -> str:
    """Validate SQL is read-only and inject row limit if needed.

    Returns the (possibly modified) SQL.
    Raises SQLValidationError if the SQL is not safe to execute.
    """
    # Strip comments (-- and /* */)
    stripped = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    stripped = re.sub(r'/\*.*?\*/', '', stripped, flags=re.DOTALL)

    # Check for dangerous statements
    match = _DANGEROUS_RE.search(stripped)
    if match:
        raise SQLValidationError(
            f"Query contains disallowed statement: {match.group()}"
        )

    # Must start with SELECT or WITH (after stripping whitespace)
    first_word = stripped.strip().split()[0].upper() if stripped.strip() else ''
    if first_word not in ('SELECT', 'WITH'):
        raise SQLValidationError(
            f"Query must start with SELECT or WITH, got: {first_word}"
        )

    # Inject LIMIT if not present
    if not re.search(r'\bLIMIT\s+\d+', stripped, re.IGNORECASE):
        sql = sql.rstrip().rstrip(';') + f'\nLIMIT {MAX_ROWS}'

    return sql
```

### 5.5 API Endpoints (`app/api/query.py`)

#### `POST /api/query/ask` — Natural Language Query

**Request:**
```json
{
  "question": "What is my winrate by position?",
  "workspace_id": 1,
  "model": "haiku"  // optional, default "haiku". Options: "haiku", "sonnet"
}
```

**Response (success):**
```json
{
  "question": "What is my winrate by position?",
  "sql": "SELECT hp.position, ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2) AS winrate_bb100, COUNT(*) AS hands FROM hand_players hp JOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id WHERE hp.player_id = 42 AND h.workspace_id = 1 GROUP BY hp.position ORDER BY ...",
  "columns": ["position", "winrate_bb100", "hands"],
  "rows": [
    ["EP", -4.2, 1089],
    ["MP", -1.4, 1156],
    ["CO", 3.1, 1198],
    ["BTN", 8.2, 1204],
    ["SB", -12.1, 1210],
    ["BB", -5.8, 1243]
  ],
  "row_count": 6,
  "summary": "Your best position is BTN at +8.2 bb/100 over 1,204 hands. Your worst is SB at -12.1 bb/100. This is typical — position is the strongest predictor of win rate in poker.",
  "execution_time_ms": 42,
  "retried": false
}
```

**Response (error after retry):**
```json
{
  "question": "What is my winrate by position?",
  "sql": "SELECT ...",
  "error": "Column 'xyz' not found in table 'hand_players'",
  "retried": true
}
```

**Response (no API key):**
```json
{
  "error": "no_api_key",
  "message": "Add your Anthropic API key in Settings to use the query engine."
}
```

#### Implementation flow:

```python
@router.post("/query/ask")
async def ask_question(req: AskRequest):
    # 1. Get API key from settings
    api_key = get_setting(db, "anthropic_api_key")
    if not api_key:
        raise HTTPException(400, detail={"error": "no_api_key", ...})

    # 2. Resolve hero context
    hero_id = get_hero_player_id(db, req.workspace_id)
    hero_username = get_hero_username(db, req.workspace_id)

    # 3. Build system prompt
    system_prompt = build_system_prompt(hero_id, hero_username, req.workspace_id)

    # 4. Call Anthropic API
    model = "claude-haiku-4-5-20251001" if req.model == "haiku" else "claude-sonnet-4-6"
    response = call_anthropic(api_key, model, system_prompt, req.question)

    # 5. Extract SQL from response
    sql = extract_sql(response)

    # 6. Validate
    sql = validate_read_only(sql)

    # 7. Execute
    try:
        columns, rows = execute_query(db, sql)
    except DuckDBError as e:
        # 8. Retry once: send error back to LLM
        retry_response = call_anthropic(api_key, model, system_prompt,
            f"Original question: {req.question}\n\n"
            f"Generated SQL:\n{sql}\n\n"
            f"DuckDB error: {e}\n\n"
            f"Fix the SQL and try again.")
        sql = extract_sql(retry_response)
        sql = validate_read_only(sql)
        columns, rows = execute_query(db, sql)  # if this fails, return error
        retried = True

    # 9. Generate summary
    summary = generate_summary(api_key, model, req.question, columns, rows)

    # 10. Return
    return AskResponse(question=req.question, sql=sql, columns=columns,
                       rows=rows, row_count=len(rows), summary=summary, ...)
```

#### Summary generation strategy:

**Option A — Second LLM call** (simpler, more flexible):
After getting query results, make a second call: "Given this question and these results, write a 1-2 sentence summary." Cost: ~$0.001 extra per query.

**Option B — Single structured output** (faster, cheaper):
Ask the LLM to return JSON with both `sql` and `summary_hint` fields. The summary_hint is a template like "winrate by position, best is {column with highest value}". We fill in the actual values after execution. Less flexible but one fewer API call.

**Decision: Option A.** The summary is the "wow" moment. It's worth the extra $0.001 and 200ms. The second call is tiny — just the question, column names, and first 20 rows as context.

#### `POST /api/query/sql` — Direct SQL Execution

```python
@router.post("/query/sql")
async def execute_sql(req: SqlRequest):
    # 1. Validate read-only
    sql = validate_read_only(req.sql)

    # 2. Execute on read cursor
    cursor = get_read_cursor()
    t0 = time.monotonic()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    elapsed = int((time.monotonic() - t0) * 1000)

    # 3. Convert Decimal/datetime to JSON-serializable types
    rows = [[_serialize(v) for v in row] for row in rows]

    return SqlResponse(columns=columns, rows=rows,
                       row_count=len(rows), execution_time_ms=elapsed)
```

No API key needed. No LLM involved. Just SQL → DuckDB → results.

#### `GET /api/query/schema` — Schema Documentation

Returns a human-readable description of the database schema, pulled from the semantic layer. For API docs and the future "schema explorer" UI.

```python
@router.get("/query/schema")
async def get_schema():
    glossary = load_glossary()
    return {
        "tables": glossary["tables"],
        "metrics": glossary["metrics"],
        "filters": glossary["filters"],
        "concepts": glossary["concepts"],
    }
```

### 5.6 Workspace Scoping for Direct SQL

For `POST /api/query/sql`, we do NOT auto-inject workspace filtering. The user is writing raw SQL — they are responsible for including `WHERE h.workspace_id = X`. This is intentional:

- Power users may want to query across workspaces
- Auto-injection would break CTEs and subqueries unpredictably
- The NL endpoint handles scoping via the LLM prompt

If this proves problematic (users accidentally querying wrong workspace), we can add an optional `auto_scope: true` parameter later.

### 5.7 API Key Storage

Stored in the existing `settings` table:

```sql
INSERT INTO settings VALUES ('anthropic_api_key', 'sk-ant-...')
```

- **GET /api/settings** — returns masked key: `sk-ant-...****1234` (first 7 + last 4 chars)
- **PATCH /api/settings** — accepts `anthropic_api_key` field, stores raw
- **Backend only** — the key is read server-side for API calls. Never sent to the frontend except masked.

The settings endpoint already exists (`app/api/settings.py`). We extend the `Settings` model:

```python
class Settings(BaseModel):
    hero_username: str
    hero_site: str
    anthropic_api_key: str | None = None      # masked on read, raw on write
    query_model: str = "haiku"                 # "haiku" or "sonnet"
```

### 5.8 Dependencies

New Python dependencies to add to `requirements.txt`:

```
anthropic>=0.42.0    # Anthropic Python SDK
pyyaml>=6.0          # YAML parsing for semantic layer
```

No other dependencies. We use DuckDB's existing read cursor infrastructure and FastAPI's existing router pattern.

### 5.9 Error Handling

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| No API key configured | 400 | `{"error": "no_api_key", "message": "..."}` |
| Invalid API key | 401 | `{"error": "invalid_api_key", "message": "..."}` |
| Anthropic API rate limit | 429 | `{"error": "rate_limited", "message": "..."}` |
| Anthropic API error | 502 | `{"error": "api_error", "message": "..."}` |
| SQL validation failed | 422 | `{"error": "unsafe_sql", "message": "Query contains disallowed statement: DROP"}` |
| DuckDB error (after retry) | 422 | `{"error": "query_failed", "sql": "...", "message": "Column 'xyz' not found"}` |
| Empty results | 200 | Normal response with `rows: [], row_count: 0` |
| No hero configured | 400 | `{"error": "no_hero", "message": "Set your hero username in Settings first."}` |

---

## 6. Frontend Design

### 6.1 New Page: `/query`

Added to the sidebar under "Tools" group (alongside "Compare"):

```typescript
// AppSidebar.tsx — addition
const toolItems = [
  { to: '/compare', label: 'Compare', icon: ArrowLeftRight },
  { to: '/query', label: 'Query', icon: MessageSquare },  // new
];
```

```typescript
// App.tsx — addition
import QueryPage from './pages/QueryPage';

// Inside <Routes>:
<Route path="/query" element={<QueryPage />} />
```

```typescript
// PAGE_LABELS addition:
'/query': 'Query',
```

### 6.2 Page Layout

The page has **two tabs**: **Builder** (default) and **Ask** (NL). Both share the same ResultsPanel below.

#### Builder Tab

```
┌─────────────────────────────────────────────────────────────────┐
│  [Builder]  [Ask]                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Measure   [Winrate (bb/100) ▼]  [VPIP % ▼]       [+ Measure] │
│                                                                 │
│  Filter    [Position ▼] [= ▼] [BTN ▼]              [+ Filter] │
│            [Pot type ▼] [= ▼] [3-bet pot ▼]        [× remove] │
│                                                                 │
│  Group by  [Position ▼]                             [+ Group]  │
│                                                                 │
│  Player    ○ Hero only   ○ All players   ○ Specific: [____]    │
│                                                                 │
│  [Run Query]                              ▸ Preview SQL         │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─ Results ─────────────────────────────────────────────────┐  │
│  │  ┌──────────┬──────────────┬───────┬───────┐              │  │
│  │  │ Position │ Winrate (bb) │ VPIP% │ Hands │              │  │
│  │  ├──────────┼──────────────┼───────┼───────┤              │  │
│  │  │ BTN      │ +8.2         │ 24.1  │ 1,204 │              │  │
│  │  │ CO       │ +3.1         │ 22.8  │ 1,198 │              │  │
│  │  │ ...      │ ...          │ ...   │ ...   │              │  │
│  │  └──────────┴──────────────┴───────┴───────┘              │  │
│  │                                                           │  │
│  │  ▸ Show SQL                                               │  │
│  │  [Copy SQL]  [Edit & Re-run]                              │  │
│  │  6 rows · 42ms                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### Builder — Available Measures (from `poker_glossary.yaml` metrics)

Organized by category in the dropdown:

| Category | Measures |
|----------|----------|
| **Financial** | Winrate (bb/100), EV Winrate, Total Won (BB), Total Rake, Hands Played |
| **Preflop** | VPIP, PFR, Open Raise, 3-Bet, 4-Bet, 5-Bet, Fold to 3-Bet, Fold to 4-Bet, Call Open Raise, Limp, Limp-Fold, Squeeze |
| **Steal** | Steal, Fold to Steal, BB Defense |
| **Postflop** | C-Bet Flop, C-Bet Turn, C-Bet River, Fold to C-Bet Flop/Turn/River, Donk Bet Flop |
| **Aggression** | AF Flop, AF Turn, AF River, AFq Flop |
| **Showdown** | WTSD, W$SD, WWSF |

#### Builder — Available Filters

Two filter sections: **Situation Filters** (dropdowns) and **Action Line** (sequence builder).

##### Situation Filters

| Filter | Type | Options |
|--------|------|---------|
| **Position** | Multi-select | EP, MP, CO, BTN, SB, BB |
| **Stakes** | Dropdown | Auto-populated from user's data |
| **Date range** | Date picker | From / To (shadcn Calendar) |
| **Game mode** | Dropdown | Regular, Fast Fold |
| **Pot type** | Dropdown | Single Raised, 3-Bet Pot, Limped |
| **IP/OOP** | Dropdown | In Position, Out of Position |
| **Multiway** | Toggle | Heads-up only, Multiway only |
| **3-Bet pot** | Toggle | Yes, No |
| **Opponent type** | Multi-select | TAG, LAG, NIT, REC, MAN |
| **Board texture** | Multi-select | Monotone, Two-tone, Rainbow, Paired, Unpaired, A-high, K-high, Q-high, J-high or lower, Connected, Disconnected |
| **Hand strength** | Multi-select | Overpair, Top Pair, Middle/Bottom Pair, Two Pair, Set, Flush Draw, OESD, Gutshot, Overcards, No Made Hand |
| **Min hands** | Number input | Minimum sample size (for player queries) |

##### Board Texture Filter

Computed at query time from `board_cards` table (no schema changes needed). Available as a multi-select dropdown in the builder.

**Default categories:**

| Category | SQL condition (flop cards) |
|----------|---------------------------|
| **Monotone** | All 3 cards same suit |
| **Two-tone** | Exactly 2 cards same suit |
| **Rainbow** | All 3 different suits |
| **Paired** | Two cards share a rank |
| **Unpaired** | No cards share a rank |
| **A-high** | Highest card is an Ace |
| **K-high** | Highest card is a King (no Ace) |
| **Q-high** | Highest card is a Queen |
| **J-high or lower** | Highest card is J, T, or below |
| **Connected** | At least 2 cards within 2 ranks of each other |
| **Disconnected** | No two cards within 2 ranks |

**SQL generation**: CTE that joins `board_cards` for the flop street, computes suit counts and rank properties, then categorizes. Example:

```sql
WITH flop_texture AS (
  SELECT
    bc.hand_id, bc.workspace_id,
    COUNT(DISTINCT bc.card[2]) AS suit_count,
    MAX(CASE bc.card[1]
      WHEN 'A' THEN 14 WHEN 'K' THEN 13 WHEN 'Q' THEN 12
      WHEN 'J' THEN 11 WHEN 'T' THEN 10
      ELSE CAST(bc.card[1] AS INTEGER) END) AS high_rank,
    COUNT(*) - COUNT(DISTINCT CASE bc.card[1]
      WHEN 'A' THEN 14 WHEN 'K' THEN 13 WHEN 'Q' THEN 12
      WHEN 'J' THEN 11 WHEN 'T' THEN 10
      ELSE CAST(bc.card[1] AS INTEGER) END) AS pair_count
  FROM board_cards bc
  WHERE bc.street = 'flop' AND bc.board_number = 1
  GROUP BY bc.hand_id, bc.workspace_id
)
-- suit_count=1 → Monotone, =2 → Two-tone, =3 → Rainbow
-- pair_count>0 → Paired
-- high_rank: 14=A-high, 13=K-high, etc.
```

##### Hand Strength Filter

Evaluated at query time from hero's `card1`/`card2` + `board_cards`. Available as a multi-select dropdown.

**Default categories (flop):**

| Category | How it's determined |
|----------|-------------------|
| **Overpair** | Pocket pair with rank above highest board card |
| **Top pair** | One hole card rank matches highest board card |
| **Middle pair** | One hole card rank matches second board card |
| **Bottom pair** | One hole card rank matches lowest board card |
| **Two pair** | Both hole card ranks match board card ranks |
| **Set** | Pocket pair matches a board card rank |
| **Trips** | One hole card matches a paired board card |
| **Straight** | 5-card straight using both hole cards and 3 board cards |
| **Flush** | 5 cards of same suit (both hole cards + 3 board cards) |
| **Full house+** | Full house, quads, straight flush |
| **Flush draw** | 2 hole cards same suit as 2 board cards (not already flush) |
| **OESD** | Open-ended straight draw (8 outs) |
| **Gutshot** | Inside straight draw (4 outs) |
| **Overcards** | Both hole cards above highest board card, no pair |
| **No made hand** | None of the above (air) |

**SQL generation**: CTE that joins hero's cards with flop board_cards, computes rank comparisons and suit matches. This is the most complex filter but each category is a deterministic SQL condition. For the builder, we generate the CTE once and filter on the category column.

**Implementation note**: Hand strength evaluation is inherently complex (especially straights). We implement the 6-8 most common categories first (overpair, top pair, mid/bottom pair, two pair, set, flush draw, OESD) and add the rest iteratively. Even the initial set covers the vast majority of study scenarios.

##### Bet Sizing Filter (% of pot)

The action line builder's sizing qualifier needs bet amounts relative to pot. Two approaches:

**Option A — Compute pot from actions at query time** (no schema change):
```sql
-- Pot before an action = sum of all prior actions in this hand
WITH pot_at_action AS (
  SELECT a.*,
    SUM(a.amount) OVER (
      PARTITION BY a.hand_id, a.workspace_id
      ORDER BY a.action_order
      ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS pot_before
  FROM actions a
)
-- Then: a.amount / pot_before = bet as fraction of pot
```

**Option B — Add `pot_before_action` column during import** (schema change, faster queries):
Compute pot size at each action during the insert pipeline. Stored once, queried many times.

**Decision: Option B for v1.** The running-sum window function works but is slow on large databases. Adding `pot_before_action` to the `actions` table during `insert_parsed_hand()` is straightforward — we already track cumulative investments. This requires a STAT_VERSION bump to rebuild existing data.

**Sizing presets in the action line builder:**

| Preset | Range (% of pot) |
|--------|-----------------|
| Tiny | <25% |
| Small | 25-40% |
| Half pot | 40-60% |
| Two-thirds | 60-80% |
| Pot | 80-120% |
| Overbet | 120-200% |
| Large overbet | 200%+ |
| All-in | `is_all_in = true` |
| Custom | User enters min/max % |

##### Action Line Builder

Construct a multi-street action sequence to find exact lines/spots. Users stack action steps, each specifying who acts, what they do, and optional sizing qualifiers.

**UI layout:**

```
┌─ Action Line ──────────────────────────────────────────────────┐
│                                                                │
│  PREFLOP                                                       │
│  ┌──────────┐ ┌────────┐                                      │
│  │ Hero   ▼ │ │Raises ▼│                              [× del] │
│  └──────────┘ └────────┘                                      │
│  ┌──────────┐ ┌────────┐                                      │
│  │ Villain▼ │ │Calls  ▼│                              [× del] │
│  └──────────┘ └────────┘                                      │
│  [+ Add action]                                                │
│                                                                │
│  FLOP                                                          │
│  ┌──────────┐ ┌────────┐  ┌───────────────────┐               │
│  │ Hero   ▼ │ │Bets   ▼│  │ 50-75% pot     ▼ │       [× del] │
│  └──────────┘ └────────┘  └───────────────────┘               │
│  ┌──────────┐ ┌────────┐                                      │
│  │ Villain▼ │ │Raises ▼│                              [× del] │
│  └──────────┘ └────────┘                                      │
│  [+ Add action]                                                │
│                                                                │
│  [+ Add street: Turn / River]                                  │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Each action step has:**

| Field | Options |
|-------|---------|
| **Who** | Hero, Villain (any opponent), or specific player |
| **Action** | Folds, Checks, Calls, Bets, Raises, Goes All-in |
| **Sizing** (optional) | Preset ranges: <33% pot, 33-50%, 50-75%, 75-100%, 100-150% (overbet), 150%+ · Or custom min/max in BB |
| **Street** | Preflop, Flop, Turn, River (sections, not per-action) |

**How it generates SQL:**

The action line translates into an `EXISTS` subquery against the `actions` table. Each action step becomes a condition matching `action_type`, `player_id` (hero or non-hero), `street`, and optionally `amount_bb` ranges. Steps within a street are ordered by `action_order`.

```sql
-- Example: Hero raises preflop, villain calls, hero bets 50-75% pot on flop, villain raises
WHERE EXISTS (
  SELECT 1 FROM actions a1
  WHERE a1.hand_id = h.id AND a1.workspace_id = h.workspace_id
    AND a1.player_id = {hero_id}
    AND a1.street = 'preflop' AND a1.action_type = 'raise'
)
AND EXISTS (
  SELECT 1 FROM actions a2
  WHERE a2.hand_id = h.id AND a2.workspace_id = h.workspace_id
    AND a2.player_id != {hero_id}
    AND a2.street = 'preflop' AND a2.action_type = 'call'
)
AND EXISTS (
  SELECT 1 FROM actions a3
  WHERE a3.hand_id = h.id AND a3.workspace_id = h.workspace_id
    AND a3.player_id = {hero_id}
    AND a3.street = 'flop' AND a3.action_type = 'bet'
    -- sizing: 50-75% pot requires joining pot calculation or using amount_bb heuristic
)
AND EXISTS (
  SELECT 1 FROM actions a4
  WHERE a4.hand_id = h.id AND a4.workspace_id = h.workspace_id
    AND a4.player_id != {hero_id}
    AND a4.street = 'flop' AND a4.action_type = 'raise'
    AND a4.action_order > (SELECT MAX(action_order) FROM actions
        WHERE hand_id = h.id AND workspace_id = h.workspace_id
        AND player_id = {hero_id} AND street = 'flop' AND action_type = 'bet')
)
```

**What this enables that H2N also does:**
- "Hero open-raises BTN, villain calls BB, hero cbets flop, villain raises" → exact spot isolation
- Bet sizing qualifiers on any action
- Any preflop/postflop action combination

**What this enables that H2N cannot do:**
- Combine action lines WITH analytical measures (winrate, VPIP, etc.) and GROUP BY dimensions
- "Show my winrate in spots where I cbet flop and get called, grouped by turn card rank"
- "Compare my fold-to-raise frequency after cbetting on dry vs wet boards"
- Time-series analysis of a specific line ("how has my flop check-raise frequency changed monthly?")
- Cross-player analysis ("which villain raises my flop cbet most often?")

The action line is a filter — it narrows the hand set. The measures and group-by dimensions then analyze that narrowed set. This is the architectural advantage of building on SQL: filters compose with analytics freely.

##### Quick Filter Presets

Pre-built action lines for common spots, selectable via a dropdown or tag-click UI:

**Preflop Presets:**
| Preset | What it filters |
|--------|----------------|
| Open Raise | Hero raises, no prior raise |
| Called Open Raise | Villain raises, hero calls |
| 3-Bet | Hero raises after villain's raise |
| Called 3-Bet | Hero raises, villain 3-bets, hero calls |
| 4-Bet | Hero raises, villain 3-bets, hero raises |
| Squeeze | Villain raises, one+ callers, hero raises |
| Steal (CO/BTN/SB) | Hero open-raises from CO, BTN, or SB |
| Blind vs Blind | SB vs BB, all others fold |
| Limp | Hero calls BB preflop, no raise |

**Postflop Presets:**
| Preset | What it filters |
|--------|----------------|
| C-Bet Flop | Hero was PF aggressor, hero bets flop |
| Missed C-Bet | Hero was PF aggressor, hero checks flop |
| Facing C-Bet | Villain was PF aggressor, villain bets flop |
| Check-Raise Flop | Villain bets flop, hero raises |
| Float Flop | Villain cbets flop, hero calls, hero bets turn |
| Donk Bet | Villain was PF aggressor, hero bets flop first |
| 2nd Barrel | Hero cbets flop, hero bets turn |
| 3rd Barrel | Hero cbets flop, bets turn, bets river |
| Probe Bet | Villain was PF aggressor, villain checks flop/turn, hero bets |

**Combined Presets (Scenario Presets):**
| Preset | What it filters |
|--------|----------------|
| SRP IP as PFR | Hero open-raises, gets called, is in position postflop |
| SRP OOP as PFR | Hero open-raises from blinds, gets called |
| 3-Bet Pot IP as 3-Bettor | Hero 3-bets, villain calls, hero is IP |
| 3-Bet Pot OOP as Caller | Villain 3-bets, hero calls, hero is OOP |
| Blind Defense vs Steal | Villain steals from CO/BTN/SB, hero defends from BB |

Presets populate the action line (users can see and modify the generated steps) and also set relevant situation filters (position, pot type). Clicking a preset is a starting point, not a black box.

#### Builder — Available Group By dimensions

| Dimension | SQL |
|-----------|-----|
| Position | `hp.position` |
| Month | `DATE_TRUNC('month', h.played_at)` |
| Week | `DATE_TRUNC('week', h.played_at)` |
| Day | `CAST(h.played_at AS DATE)` |
| Stakes | `h.stakes` |
| Pot type | `hp.pot_type` |
| IP/OOP | `hp.postflop_ip` |
| Multiway/HU | `hp.is_multiway` |
| Opponent type | `pc.player_type` (requires player_classifications JOIN) |
| Board texture | `flop_texture.category` (requires flop_texture CTE) |
| Hand strength | `hand_eval.category` (requires hand evaluation CTE) |

#### Builder — SQL Generation (`sql_builder.py`)

The builder generates SQL deterministically from the selected measures, filters, and group-by dimensions. No LLM involved.

```python
def build_query(
    measures: list[str],        # metric keys from glossary
    filters: list[FilterSpec],  # [{column, op, value}, ...]
    group_by: list[str],        # dimension keys
    player_scope: str,          # "hero" | "all" | specific player_id
    hero_id: int,
    workspace_id: int,
) -> str:
    """Generate deterministic SQL from builder parameters."""
    glossary = load_glossary()

    # SELECT clause: group-by columns + measure SQL expressions
    select_parts = []
    for dim in group_by:
        select_parts.append(f"{DIMENSION_SQL[dim]} AS {dim}")
    for m in measures:
        metric = glossary['metrics'][m]
        select_parts.append(f"{metric['sql']} AS {m}")
    # Always include hand count
    select_parts.append("COUNT(*) AS hands")

    # FROM + JOINs
    from_clause = "FROM hand_players hp"
    from_clause += "\nJOIN hands h ON hp.hand_id = h.id AND hp.workspace_id = h.workspace_id"
    if any needs player_classifications:
        from_clause += "\nJOIN player_classifications pc ON pc.player_id = hp.player_id AND pc.workspace_id = h.workspace_id"

    # WHERE clause
    where_parts = [f"h.workspace_id = {workspace_id}"]
    if player_scope == "hero":
        where_parts.append(f"hp.player_id = {hero_id}")
    elif player_scope != "all":
        where_parts.append(f"hp.player_id = {player_scope}")
    for f in filters:
        where_parts.append(f.to_sql())

    # GROUP BY + ORDER BY
    ...

    return assembled_sql
```

The builder always produces valid SQL. No error-retry loop needed. This is why it's the foundation — deterministic, instant, zero cost.

#### Ask Tab (NL)

```
┌─────────────────────────────────────────────────────────────────┐
│  [Builder]  [Ask]                                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐ [->] │
│  │ e.g., "What is my winrate by position this month?"    │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  Try these:                                                     │
│                                                                 │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ Winrate by           │  │ My biggest leak      │             │
│  │ position             │  │ by position          │             │
│  └──────────────────────┘  └──────────────────────┘             │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ Most profitable      │  │ Most losing           │             │
│  │ hand combos          │  │ opponent              │             │
│  └──────────────────────┘  └──────────────────────┘             │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ 3-Bet trend          │  │ Winrate vs fish      │             │
│  │ over time            │  │ vs regs              │             │
│  └──────────────────────┘  └──────────────────────┘             │
│  ┌──────────────────────┐  ┌──────────────────────┐             │
│  │ C-Bet funnel:        │  │ Hands where I        │             │
│  │ flop->turn->river    │  │ lost 50+ bb          │             │
│  └──────────────────────┘  └──────────────────────┘             │
│                                                                 │
│  ┌─ No API key? ─────────────────────────────────────────────┐  │
│  │ Add your Anthropic API key in Settings to get started.    │  │
│  │ Queries cost ~$0.001 each with Claude Haiku.   [Settings] │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  (results appear here, same ResultsPanel as Builder tab)        │
│  NL results also include a Summary line above the table         │
└─────────────────────────────────────────────────────────────────┘
```

#### Results State

```
┌─────────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────┐ [⏎] │
│  │ What is my winrate by position?                       │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌─ Result ──────────────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  Your best position is BTN at +8.2 bb/100 over 1,204     │  │
│  │  hands. Your worst is SB at -12.1 bb/100.                │  │
│  │                                                           │  │
│  │  ┌──────────┬──────────────┬───────┐                      │  │
│  │  │ Position │ Winrate (bb) │ Hands │                      │  │
│  │  ├──────────┼──────────────┼───────┤                      │  │
│  │  │ EP       │ -4.2         │ 1,089 │                      │  │
│  │  │ MP       │ -1.4         │ 1,156 │                      │  │
│  │  │ CO       │ +3.1         │ 1,198 │                      │  │
│  │  │ BTN      │ +8.2         │ 1,204 │                      │  │
│  │  │ SB       │ -12.1        │ 1,210 │                      │  │
│  │  │ BB       │ -5.8         │ 1,243 │                      │  │
│  │  └──────────┴──────────────┴───────┘                      │  │
│  │                                                           │  │
│  │  ▸ Show SQL                                               │  │
│  │  ┌────────────────────────────────────────────────────┐   │  │
│  │  │ SELECT hp.position,                                │   │  │
│  │  │   ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2)     │   │  │
│  │  │     AS winrate_bb100,                              │   │  │
│  │  │   COUNT(*) AS hands                                │   │  │
│  │  │ FROM hand_players hp ...                           │   │  │
│  │  └────────────────────────────────────────────────────┘   │  │
│  │  [Copy SQL]  [Edit & Re-run]                              │  │
│  │                                                           │  │
│  │  Query took 42ms                                          │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ── Previous queries ──────────────────────────────────────────  │
│  ▸ What is my VPIP?                                             │
│  ▸ Which opponent have I lost the most to?                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Edit & Re-run State

When user clicks "Edit & Re-run", the SQL block transforms into an editable textarea with a "Run" button:

```
│  ┌────────────────────────────────────────────────────┐   │
│  │ SELECT hp.position,                                │   │
│  │   ROUND(SUM(hp.won_bb) * 100.0 / COUNT(*), 2)     │   │ ← editable
│  │     AS winrate_bb100,                              │   │
│  │   COUNT(*) AS hands                                │   │
│  │ FROM hand_players hp ...                           │   │
│  └────────────────────────────────────────────────────┘   │
│  [Run SQL]  [Cancel]                                      │
```

This calls `POST /api/query/sql` (no LLM, just direct SQL execution). Results replace the current results panel. The summary disappears since this is a manual SQL execution.

### 6.3 Components

#### `QueryBar`

```typescript
interface QueryBarProps {
  onSubmit: (question: string) => void;
  loading: boolean;
  placeholder?: string;
}
```

- Single-line input (shadcn Input), expands to textarea on focus if text is long
- Submit on Enter (Shift+Enter for newline when expanded)
- Loading spinner replaces submit button during query
- Up/Down arrow cycles through query history (session state, not persisted)

#### `SuggestedQuestions`

```typescript
const SUGGESTED_QUESTIONS = [
  { label: "Winrate by position", question: "What is my winrate by position?", icon: "BarChart3" },
  { label: "My biggest leak by position", question: "Which position am I losing the most at and why?", icon: "TrendingDown" },
  { label: "Most profitable hand combos", question: "Show me my most profitable hand combos", icon: "Spade" },
  { label: "Most losing opponent", question: "Which opponent have I lost the most money to?", icon: "User" },
  { label: "3-Bet trend over time", question: "How has my 3bet% changed week by week?", icon: "TrendingUp" },
  { label: "Winrate vs fish vs regs", question: "Compare my winrate against fish vs regs by position", icon: "Swords" },
  { label: "C-Bet funnel", question: "Show my flop cbet funnel: cbet → barrel turn → barrel river", icon: "Filter" },
  { label: "Hands where I lost 50+ bb", question: "Show me hands where I lost more than 50 big blinds", icon: "Search" },
];
```

- Grid of clickable cards (2 columns on desktop, 1 on mobile)
- Clicking a card fills the QueryBar and auto-submits
- Visible on empty state, hidden when results are showing
- "Show suggestions" link to bring them back

#### `ResultsPanel`

```typescript
interface ResultsPanelProps {
  result: QueryResult;
  onEditAndRerun: (sql: string) => void;
  onCopySQL: () => void;
}
```

- **Summary** — styled as a subtle callout/alert above the table
- **DataTable** — shadcn Table component with:
  - Number formatting: bb values get +/- prefix and color (green/red)
  - Percentage formatting: values ending in `_pct` get `%` suffix
  - Sortable columns (client-side)
  - "Showing X of Y rows" footer if truncated
- **SQL block** — collapsible (collapsed by default), monospace font, read-only
- **Actions** — "Copy SQL" (copies to clipboard, toast feedback), "Edit & Re-run" (opens editor)
- **Footer** — "Query took Xms" + "Retried" badge if the query was retried

#### `QueryHistory`

Session-only (React state, not persisted). Shows as a list below results:

```typescript
interface HistoryEntry {
  question: string;
  result: QueryResult;
  timestamp: Date;
}
```

- Clickable entries expand to show the result
- Most recent on top
- Cleared on page reload (session-only)

### 6.4 API Client additions (`lib/api.ts`)

```typescript
// ── Query Engine ──

export interface QueryResult {
  question: string;
  sql: string;
  columns: string[];
  rows: any[][];
  row_count: number;
  summary: string;
  execution_time_ms: number;
  retried: boolean;
}

export interface SqlResult {
  columns: string[];
  rows: any[][];
  row_count: number;
  execution_time_ms: number;
}

export interface QueryError {
  error: string;
  message: string;
  sql?: string;
}

export async function askQuestion(
  question: string,
  model?: 'haiku' | 'sonnet',
): Promise<QueryResult> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/query/ask?${sp}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, model }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw err;
  }
  return res.json();
}

export async function executeSql(sql: string): Promise<SqlResult> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);
  const res = await fetch(`${BASE}/query/sql?${sp}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw err;
  }
  return res.json();
}
```

### 6.5 Settings Page Additions

Add a new section to the settings UI (currently only has hero username/site):

```
┌─ Query Engine ──────────────────────────────────────────────────┐
│                                                                 │
│  Anthropic API Key                                              │
│  ┌──────────────────────────────────────────┐                   │
│  │ sk-ant-api03-****************************│  [Save]           │
│  └──────────────────────────────────────────┘                   │
│  Used for natural language queries. Get a key at                │
│  console.anthropic.com. Stored locally, never sent to OHM.     │
│                                                                 │
│  Model                                                          │
│  ○ Claude Haiku 4.5 (fast, ~$0.001/query) — recommended        │
│  ● Claude Sonnet 4.6 (smarter, ~$0.015/query)                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

The Settings model (`Settings` Pydantic model + `Settings` TypeScript interface) gets two new optional fields. Existing settings page component gets a new card/section. Separate `PATCH` for API key vs hero settings to avoid accidental overwrites.

---

## 7. Suggested Questions Design

The 8 suggested questions are chosen to showcase different query capabilities:

| # | Question | Demonstrates |
|---|----------|-------------|
| 1 | "What is my winrate by position?" | Basic aggregation + GROUP BY |
| 2 | "Which position am I losing the most at and why?" | Aggregation + LLM analysis |
| 3 | "Show me my most profitable hand combos" | Hole card analysis, multi-column |
| 4 | "Which opponent have I lost the most money to?" | Cross-player JOIN |
| 5 | "How has my 3bet% changed week by week?" | Time series, DATE_TRUNC |
| 6 | "Compare my winrate against fish vs regs by position" | Player classification JOIN |
| 7 | "Show my flop cbet funnel: cbet → barrel turn → river" | Multi-stat funnel |
| 8 | "Show me hands where I lost more than 50 big blinds" | Hand-level detail query |

These are hardcoded in v1. Phase 2 could generate them based on the user's actual data (e.g., "You haven't looked at your SB stats yet — your fold-to-steal is 85%").

---

## 8. Security

### 8.1 SQL Injection Prevention

- **Read-only enforcement**: Regex blocklist + first-word whitelist (SELECT/WITH only)
- **DuckDB cursor**: Uses `get_read_cursor()` which creates a new cursor on the shared connection. DuckDB doesn't support connection-level read-only mode, but our validator blocks all write statements.
- **No user input interpolation**: The SQL comes from the LLM, not from string concatenation with user input. The user's question goes to the LLM; the LLM generates complete SQL.

### 8.2 API Key Security

- Stored in DuckDB `settings` table (local file, same security as all user data)
- Returned masked from GET endpoint (first 7 + last 4 chars)
- Never sent to frontend in full — only the masked version
- Used server-side only for Anthropic API calls
- If the DuckDB file is compromised, all data (hands, stats) is already exposed — the API key adds no additional risk surface

### 8.3 Resource Limits

- **Row limit**: 500 rows max (injected if missing)
- **Timeout**: DuckDB queries have a soft timeout of 10 seconds. If a query hasn't returned after 10s, we cancel the cursor and return an error.
- **No concurrent LLM calls per user**: The endpoint is synchronous — one query at a time. FastAPI's thread pool handles concurrency at the server level.

---

## 9. Performance

### 9.1 Latency Budget

| Step | Target | Notes |
|------|--------|-------|
| Build system prompt | <5ms | Cached after first load |
| Anthropic API call (Haiku) | 500-1500ms | Depends on output length, network |
| SQL validation | <1ms | Regex matching |
| DuckDB execution | 10-200ms | Most queries are fast on <1M hands |
| Summary generation (2nd call) | 300-800ms | Small prompt, short output |
| **Total** | **~1-3 seconds** | Acceptable for an interactive query |

### 9.2 Caching

**V1: No caching.** Each query makes 2 LLM calls (SQL + summary). At $0.002-0.006 per query, caching is not a priority.

**V2 consideration**: Anthropic prompt caching could reduce the system prompt cost by ~90% (3000 tokens cached). Worth doing when we see usage patterns.

### 9.3 Large Databases

DuckDB is a columnar OLAP database — it handles aggregation queries on millions of rows efficiently. The main risk is full-table scans without filters (e.g., "show me all hands"). The LIMIT 500 injection prevents result set bloat, and most queries will have WHERE clauses that leverage indexes.

For databases with 1M+ hands, complex multi-JOIN queries (hand_players + actions + board_cards) may take 1-5 seconds. This is acceptable for an interactive query tool.

---

## 10. Testing Strategy

### 10.1 Semantic Layer Tests

```python
# test_semantic_layer.py
def test_glossary_loads():
    """Verify poker_glossary.yaml parses without errors."""
    glossary = load_glossary()
    assert "metrics" in glossary
    assert "filters" in glossary
    assert "examples" in glossary
    assert len(glossary["examples"]) >= 15

def test_all_example_queries_valid_sql():
    """Every example query in the glossary should be valid DuckDB SQL."""
    glossary = load_glossary()
    db = get_test_db()
    for ex in glossary["examples"]:
        sql = ex["sql"].replace("{hero_id}", "1").replace("{workspace_id}", "1")
        # Should not throw — may return empty results on empty DB
        db.execute(sql)

def test_all_example_queries_pass_validator():
    """Every example query should pass the read-only validator."""
    glossary = load_glossary()
    for ex in glossary["examples"]:
        sql = ex["sql"].replace("{hero_id}", "1").replace("{workspace_id}", "1")
        validate_read_only(sql)  # should not raise
```

### 10.2 SQL Validator Tests

```python
# test_sql_validator.py
def test_select_allowed():
    assert validate_read_only("SELECT 1") == "SELECT 1\nLIMIT 500"

def test_with_allowed():
    sql = "WITH cte AS (SELECT 1) SELECT * FROM cte"
    validate_read_only(sql)  # should not raise

def test_insert_blocked():
    with pytest.raises(SQLValidationError, match="INSERT"):
        validate_read_only("INSERT INTO hands VALUES (...)")

def test_drop_blocked():
    with pytest.raises(SQLValidationError, match="DROP"):
        validate_read_only("DROP TABLE hands")

def test_limit_injected():
    result = validate_read_only("SELECT * FROM hands")
    assert "LIMIT 500" in result

def test_existing_limit_preserved():
    result = validate_read_only("SELECT * FROM hands LIMIT 10")
    assert "LIMIT 500" not in result
    assert "LIMIT 10" in result

def test_comment_stripping():
    """Dangerous statements in comments should be ignored."""
    validate_read_only("SELECT 1 -- DROP TABLE hands")  # should not raise

def test_semicolon_injection():
    with pytest.raises(SQLValidationError):
        validate_read_only("SELECT 1; DROP TABLE hands")
```

### 10.3 Endpoint Tests

```python
# test_query_api.py (integration tests, require API key or mock)

def test_ask_no_api_key(client):
    """Should return 400 with no_api_key error."""
    resp = client.post("/api/query/ask", json={"question": "test"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "no_api_key"

def test_sql_endpoint_read_only(client, db_with_data):
    """Should execute valid SELECT queries."""
    resp = client.post("/api/query/sql", json={
        "sql": "SELECT COUNT(*) FROM hands WHERE workspace_id = 1"
    })
    assert resp.status_code == 200
    assert resp.json()["row_count"] == 1

def test_sql_endpoint_blocks_write(client):
    """Should reject INSERT/UPDATE/DELETE."""
    resp = client.post("/api/query/sql", json={
        "sql": "DELETE FROM hands"
    })
    assert resp.status_code == 422
    assert "unsafe_sql" in resp.json()["error"]

def test_schema_endpoint(client):
    """Should return schema documentation."""
    resp = client.get("/api/query/schema")
    assert resp.status_code == 200
    assert "tables" in resp.json()
    assert "metrics" in resp.json()
```

### 10.4 Frontend Tests

Manual testing checklist (no automated frontend tests for v1):

- [ ] Empty state shows suggested questions
- [ ] Clicking suggested question submits and shows results
- [ ] Typing question + Enter submits
- [ ] Loading spinner shows during query
- [ ] Results table renders with correct data
- [ ] Summary text appears above table
- [ ] "Show SQL" expands to show generated SQL
- [ ] "Copy SQL" copies to clipboard
- [ ] "Edit & Re-run" opens editable textarea
- [ ] Running edited SQL updates results (no summary)
- [ ] Previous queries appear in history
- [ ] Clicking history entry shows previous result
- [ ] No API key shows setup prompt
- [ ] Error state shows error message + failed SQL
- [ ] Settings page shows API key field (masked)
- [ ] Settings page shows model selector

---

## 11. Rollout Plan

### Sprint 1: Semantic layer + SQL execution backbone (5h)

```
1. Create backend/app/query/ directory                        [1h]
   - __init__.py
   - poker_glossary.yaml (full semantic layer from §5.2)
   - semantic_layer.py (YAML loader, glossary → measures/filters for API)
   - sql_validator.py (read-only enforcement)

2. Create backend/app/api/query.py                            [1.5h]
   - POST /api/query/sql (direct SQL execution — shared by builder + NL + edit)
   - GET /api/query/schema (schema documentation from glossary)
   - GET /api/query/measures (metrics + filters + dimensions for builder dropdowns)

3. sql_builder.py (deterministic SQL from builder params)      [2h]
   - build_query(measures, filters, group_by, player_scope) → SQL string
   - Action-line → EXISTS subqueries against actions table
   - Uses glossary metrics SQL and filter column mappings
   - Quick filter presets → pre-built action line + situation filter combos

4. Add pyyaml to requirements.txt                              [0.1h]
   Tests for validator + glossary loading + sql_builder         [0.5h]
```

### Sprint 2: Board texture, hand strength, bet sizing (6h)

```
5. Board texture CTE generator                                 [2h]
   - SQL CTE that joins board_cards, computes suit counts, rank
     properties, pairing, and categorizes each flop
   - 11 default categories (monotone, two-tone, rainbow, paired,
     unpaired, A-high through J-low, connected, disconnected)
   - Integrates as a CTE in sql_builder when board texture filter
     or group-by is used

6. Hand strength evaluator CTE generator                       [3h]
   - SQL CTE that joins hero card1/card2 with board_cards
   - Rank comparisons for pair categories (overpair, top, mid, bottom)
   - Set detection (pocket pair matching board rank)
   - Draw detection (flush draw = 2 suited with 2 board suited,
     OESD = 8-out straight draws)
   - Start with 8 core categories: overpair, top pair, mid/bottom
     pair, two pair, set, flush draw, OESD, no made hand
   - Add remaining (gutshot, straights, flushes, full house+)
     iteratively

7. Bet sizing: add pot_before_action column                    [1h]
   - Add pot_before_action DECIMAL to actions table
   - Compute during insert_parsed_hand() from cumulative actions
   - STAT_VERSION bump → auto-rebuild existing data
   - Action line sizing filter: a.amount / a.pot_before_action
     for % of pot presets
   - Tests for all three CTE generators
```

### Sprint 3: Visual Builder frontend (10h)

```
8. Create QueryPage with Builder tab                           [4h]
   - MeasurePicker (grouped dropdown from /api/query/measures)
   - SituationFilters (dynamic filter rows: position, stakes,
     pot type, board texture, hand strength, IP/OOP, etc.)
   - GroupByPicker (dimension dropdown including board texture
     and hand strength)
   - PlayerScope selector (hero / all / specific)
   - RunButton → calls sql_builder on server, then /api/query/sql
   - Live SQL preview (collapsible, updates as dropdowns change)

9. Action Line Builder component                               [3h]
   - Street sections (Preflop / Flop / Turn / River — added on demand)
   - Action steps within each street:
     Who (Hero/Villain) + Action type dropdown
   - Sizing qualifier (preset ranges: tiny/small/half/2-3/pot/
     overbet/all-in, or custom min/max %)
   - Add/remove action steps, add/remove streets
   - Quick Filter Presets: dropdown/tags that populate the
     action line + situation filters

10. ResultsPanel (shared by Builder + Ask tabs)                [1.5h]
    - DataTable (shadcn Table, sortable columns, number formatting)
    - SqlBlock (collapsible, read-only or editable)
    - Actions: Copy SQL, Edit & Re-run
    - Row count + execution time footer

11. Routing + sidebar + API client                             [0.5h]
    - Add /query route, sidebar Tools item
    - API client: executeSql(), getBuilderMeasures()

12. Polish: number formatting (+/- colors), responsive layout  [1h]
```

### Sprint 4: NL query layer (6h)

```
13. Backend: POST /api/query/ask                               [3h]
    - prompt_builder.py (assemble system prompt from glossary)
    - Anthropic SDK integration (BYOK, user's API key)
    - SQL extraction + validation + execution + retry on error
    - Summary generation (second LLM call)

14. Extend settings for API key + model selector               [0.5h]
    - anthropic_api_key (masked read, raw write)
    - query_model (haiku / sonnet)

15. Frontend: Ask tab                                          [1.5h]
    - QueryBar (text input + submit)
    - SuggestedQuestions (8 clickable cards)
    - NL results use same ResultsPanel + Summary line above table
    - No API key → setup prompt with link to Settings

16. Settings page: API key input + model radio                 [0.5h]

17. Add anthropic to requirements.txt                          [0.1h]
    Tests for NL endpoint (mock LLM), prompt builder            [0.5h]
```

### Sprint 5: Integration testing & polish (5h)

```
18. End-to-end testing                                         [2.5h]
    - Builder: test all measure/filter/group-by combinations
    - Action line: test presets, multi-street sequences, sizing filters
    - Board texture: verify categorization against known hands
    - Hand strength: verify evaluation against known holdings
    - Bet sizing: verify % pot calculation accuracy
    - NL: test 20+ questions, tune glossary examples for failures
    - Edit & Re-run flow: builder → see SQL → edit → run

19. Edge cases                                                 [2h]
    - Empty database (no hands imported yet)
    - Very large result sets (LIMIT enforcement)
    - Action line with no matching hands
    - Complex action lines (4+ steps across 3 streets)
    - Board texture on RIT hands (board_number=1 only)
    - Hand strength when hero cards are unknown (folded preflop)
    - Hands with no flop (all fold preflop) — board texture N/A
    - Unicode in player names

20. Docs update                                                [0.5h]
    - Add query engine to CLAUDE.md project structure
    - Screenshots for marketing prep
```

### Total: ~32h (Backend+SQL ~11h + Builder frontend ~10h + NL ~6h + Testing ~5h)

**Shipping order:**
1. Sprint 1-3 ship together → builder with full filtering (board texture, hand strength, bet sizing, action lines, all situation filters). Works without API key.
2. Sprint 4 ships on top → NL queries for users who add their Anthropic key.
3. Sprint 5 runs in parallel with user testing.

This gives OHM parity with H2N's filtering power at launch, plus analytical capabilities H2N doesn't have (cross-player, time-series, composable action lines + measures).

---

## 12. Success Metrics

### Quantitative (post-launch)

| Metric | Target | How to measure |
|--------|--------|----------------|
| Query success rate | >80% of NL queries return useful results | Manual testing of 50 questions |
| Retry rate | <20% of queries need the error-retry loop | `retried: true` in responses |
| Execution time | <3 seconds p95 for NL queries | `execution_time_ms` in responses |
| SQL endpoint latency | <500ms p95 | `execution_time_ms` in responses |

### Qualitative (launch readiness gate)

- [ ] A fresh install with 1000+ hands can answer all 8 suggested questions correctly
- [ ] The "Edit & Re-run" flow works smoothly (NL → see SQL → edit → run)
- [ ] Error messages are actionable (user knows what to do next)
- [ ] The Settings API key flow works first try
- [ ] The page looks good in screenshots (this is the marketing feature)

---

## 13. Future: Saved Views (Phase 2)

A saved view is a query (SQL string) + metadata (name, description, creator). Stored in a new `saved_queries` table:

```sql
CREATE TABLE saved_queries (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    sql TEXT NOT NULL,
    source VARCHAR DEFAULT 'manual',  -- 'nl' | 'builder' | 'manual'
    original_question TEXT,           -- the NL question that generated this SQL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Users save queries from:
- The "Save" button on NL query results
- The visual builder "Save as View" button
- The SQL editor

Saved views appear on the Query page as a secondary tab or section.

---

## 14. Open Questions

| # | Question | Current stance | Needs decision by |
|---|----------|---------------|-------------------|
| 1 | **Builder SQL generation: client or server?** | Server (`sql_builder.py`) — keeps SQL logic in Python, consistent with NL path. Client-side would be faster (no round trip) but duplicates logic. | Before implementation |
| 2 | **Builder: auto-run on change or manual Run button?** | Manual "Run Query" button. Auto-run risks expensive queries on large DBs. Can add auto-run toggle later. | Before implementation |
| 3 | **Single vs two LLM calls** for SQL + summary | Two calls (§5.5). Summary quality is worth $0.001. | Before implementation |
| 4 | **Streaming** NL responses | No streaming in v1. The total latency (~2s) is tolerable. | Phase 2 |
| 5 | **Workspace scoping for /sql** | No auto-injection (§5.6). Power users are responsible. | Before implementation |
| 6 | **Model selection per-query vs global** | Global setting in v1 (Settings page). Per-query is a Phase 2 refinement. | Before implementation |
| 7 | **Query history persistence** | Session-only (React state) in v1. Database persistence in Phase 2. | Before implementation |
| 8 | **Rate limiting** | None in v1. Users pay their own API costs. | Phase 2 if abuse is observed |
