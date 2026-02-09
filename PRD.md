# Poker Tracker PRD

> **DEPRECATED** — This document's content has been redistributed into milestone-specific PRDs.
> See `PRD_ROADMAP.md` for the master roadmap and `prd/M1-M6_*.md` for detailed specs.
> This file is kept for historical reference only. Do not update it.

> Open Holdem Manager (OHM) — Open-source alternative to Hand2Note / HoldemManager
> Focus: Database, Analytics, Learning — not HUD

---

## 0. Current Status

### What's Built (MVP-1: Import → Stats + Graph + Hands + Results)

Core loop is functional with verified stats:
- GGPoker Rush & Cash parser (11 unit tests, 13,402 real hands imported without errors)
- Streaming file import (drag & drop files/folders/ZIPs, duplicate detection, progress bar)
- Stats page with H2N-style positional breakdowns (60+ stat flags, 40+ opportunity flags)
- Results dashboard — cumulative BB/$ graph with toggleable lines (EV, showdown/non-showdown, rake), stat cards (hands/won/winrate/EV/rake/SD/NSD), breakdowns by stakes/month/position, date/stakes/last-N-hands filters
- Hand browser — paginated list with filtering (position, stakes, result, tags, date), sortable columns, action abbreviations (R/B/C/X/F with hero underline), detail drawer with full hand history, hand tagging and notes
- All-in EV computation using eval7 library (heads-up, before river, known cards)
- Rake + Jackpot (BBJ) tracking — parser separates Jackpot fee from Rake; stat cards show rake/jackpot totals and rake/100
- Rebuild stats endpoint — re-parses all hands from stored raw_text without needing original files
- Hero settings (username/site config)
- Stakes normalization — cross-references header/posted blind values against standard stakes, fixes GGPoker byte corruption
- Stat flag computation extracted to separate site-independent module (`stat_flags.py`)
- 7 stat calculation bugs fixed for H2N parity (AFq, Steal%, C-Bet, Donk Bet, 3-Bet Opp, Squeeze, 5-Bet)
- Performance: PyArrow batch inserts, eval7 equity calc, Python 3.12 (~1,700 hands/sec)

### Next Steps

1. **Verify stats end-to-end** — compare OHM output against H2N for same hand sample, confirm remaining edge cases
2. **Missing H2N stats** — implement the 13 new metrics from Section 3.2.0 (limp-fold, 4-bet-fold, call-4bet, vs cbet by pot type, missed cbet IP/OOP splits, probe bets)
3. **Phase 1 core gaps** — cold call, 3-bet call, check-raise, probe bet, IP/OOP splits (see Section 3.2.2)
4. **Hand browser polish** — keyboard nav (←/→), biggest losers filter, hand export

### Architectural Decisions (diverged from original PRD)

| PRD Planned | Actual | Reason |
|-------------|--------|--------|
| Electron shell | Plain local web app | Unnecessary for MVP, adds packaging complexity |
| shadcn/ui | Raw TailwindCSS v4 | Lighter, fewer deps, sufficient for current UI |
| Zustand / React Query | Plain React state | App is simple enough, no global state needed yet |
| TanStack Table | Hand-built tables | Only one table (stats), not worth the dep |
| PokerStars parser (P0) | GGPoker only | User plays GGPoker, built what was needed first |
| `parsers/base.py` interface | Single `ggpoker.py` | Only one site, no abstraction needed yet |
| `core/`, `services/`, `models/` dirs | Flat `app/` structure | Simpler for current scope |
| pandas for bulk inserts | PyArrow batch inserts | 12x faster, lower memory |
| treys for equity calc | eval7 | Faster, cleaner API |
| Python 3.10 | Python 3.12 | Faster CPython, modern features |

### What's NOT Built Yet

From Phase 1: PokerStars parser, player lookup, remaining H2N stats (13 new metrics), Phase 1 core gap stats.
From Phase 2+: Population analysis, leak finder, session tracking, calendar view, all other site parsers, Electron packaging.

See **Section 7** for the full phase checklist.

---

## 1. Vision & Goals

### Vision
A modern, open-source poker tracking tool that helps players analyze their game and exploit opponent tendencies through powerful database analytics.

### Goals
1. **Import & Store** — Parse hand histories from major poker sites, store efficiently
2. **Analyze Self** — Find leaks in your own game through reports and filters
3. **Analyze Opponents** — Track opponent stats, identify player types, exploit tendencies
4. **Population Analysis** — Study pool tendencies (H2N's killer feature, democratized)
5. **Learn** — Review hands, tag spots, track improvement over time

### Non-Goals (MVP)
- Tournament support (cash game only)
- Real-time HUD overlay (future consideration)
- Hand replayer with animations (simple text view first)
- Multi-table session management
- Cloud sync / multi-device

---

## 2. Target Users

### Primary: Serious Amateur / Semi-Pro
- Plays 10k-100k hands/month
- Wants to improve, studies the game
- Currently uses free/pirated tools or nothing
- Price-sensitive (why open-source matters)

### Secondary: Recreational Players
- Plays 1k-10k hands/month
- Wants basic stats and hand history
- Doesn't need advanced features

### Tertiary: Coaches / Content Creators
- Reviews student hands
- Creates content from hand histories
- Needs export/sharing features

---

## 3. Core Features (MVP)

### 3.1 Hand History Import

**Supported Sites (MVP):**
| Site | Priority | Format |
|------|----------|--------|
| PokerStars | P0 | Text files |
| GGPoker | P0 | Text files |
| Winamax | P1 | Text files |
| 888poker | P1 | Text files |
| PartyPoker | P2 | Text files |

**Import Methods:**
- Manual folder selection
- Auto-detect common HH locations
- Watch folder for new files (background import)

**Import Features:**
- Duplicate detection (don't re-import same hands)
- Progress indicator for large imports
- Error handling with skip/retry options
- Import summary (hands imported, errors, duplicates)

### 3.2 Stats & Analysis

#### 3.2.0 Stats Page Layout (H2N Clone)

Target: exact clone of Hand2Note's GENERAL stats tab. Reference screenshot: `CleanShot 2026-01-20 at 01.14.10@2x.png`

**Filter Bar (top, sticky):**
```
[Player selector: "Hero, GG Network"] [Date range picker] [Game type: "Texas Hold'em NL Cash"] [View: "default"] [Hand count: "49k hands"] [⚙ Settings]
```
- Player selector: hero name + site (from settings)
- Date range: calendar picker, pre-sets (today, week, month, all)
- Game type: dropdown (NL Hold'em Cash only for now)
- View: stat layout preset selector (only "default" for MVP)

**Tabs:** `GENERAL` (active) | `Notes`

---

**PREFLOP Section** — Two-block horizontal layout

*Left block — Positional table:*
```
PRE-FLOP          Total  EP   MP   CO   BTN  SB   BB
Open Raise          28   16   19   30   51   53   27
Fold to 3Bet        61   58   54   60   66   68    0₁
Call Open Raise    8.9   --  0.4  0.5    1  2.1   29
3-Bet              8.4    0₂  4.9  6.7   10   10  7.7
3-Bet In Position  9.1    0₂  4.9  6.7   10        19
3-Bet Out of Pos   7.6                        10  4.8
```
Columns: Stat | Total | EP | MP | CO | BTN | SB | BB
- Empty cells where stat doesn't apply to that position
- Subscript after value = sample size (shown when small, e.g. `0₂` = 0% from 2 opportunities)
- `--` = zero opportunities

*Right block — Key-value pairs (two-column grid):*
```
VPIP              23     PFR               19
4-Bet             10     Limp             0.1
4-Bet Range      2.8     Limp-Fold        78₉
4-Bet-Fold        42     Squeeze          8.4
Fold to 4-Bet     68     Win Rate (bb/100) 3.8
Call 4-Bet        22     Hands            49k
5-Bet             11
```

Metrics in this block (14 total):
| Metric | Description | OHM Status |
|--------|-------------|------------|
| VPIP | Voluntarily put $ in pot % | Built |
| PFR | Preflop raise % | Built |
| 4-Bet | 4-bet % (when facing 3-bet) | Built |
| Limp | Limp % (open limp) | Built |
| 4-Bet Range | 4-bet range as % of all hands (not of opportunities) | **NEW** — `4bet_count / total_hands * 100` |
| Limp-Fold | Limp then fold to raise % | **NEW** — needs `limp_fold BOOLEAN` in parser |
| 4-Bet-Fold | 4-bet then fold to 5-bet % | **NEW** — needs `four_bet_fold BOOLEAN` in parser |
| Squeeze | Squeeze % | Built |
| Fold to 4-Bet | Fold to 4-bet % | Built |
| Win Rate (bb/100) | Win rate in big blinds per 100 hands | Built |
| Call 4-Bet | Call 4-bet % (when facing 4-bet) | **NEW** — needs `call_4bet BOOLEAN` in parser |
| Hands | Total hand count | Built |
| 5-Bet | 5-bet % | Built |

---

**STEAL Section** — Two sub-tables side by side

*Left sub-table — Steal stats:*
```
Steal         Total  BTN   SB
Steal           53    52   54
Fold to 3Bet    67    66   68
4-Bet          9.2   9.4  8.8
4-Bet-Fold      25₈   29₇   0₁
```
Columns: Stat | Total | BTN | SB (only steal positions, no CO here — H2N groups CO under preflop Open Raise)

| Metric | Description | OHM Status |
|--------|-------------|------------|
| Steal | Open raise from BTN/SB (steal attempt %) | Built |
| Fold to 3Bet (steal) | Fold to 3-bet after steal attempt | Built |
| 4-Bet (steal) | 4-bet after steal was 3-bet | Built |
| 4-Bet-Fold (steal) | 4-bet steal then fold to 5-bet | **NEW** |

*Right sub-table — vs. Steal defense:*
```
vs. Steal    SB   BB
Fold         84   49
Call        0.8   40
3-Bet        15   12
```
Columns: Stat | SB | BB (only defending positions)

| Metric | Description | OHM Status |
|--------|-------------|------------|
| vs Steal Fold | Fold to steal from SB/BB | Built |
| vs Steal Call | Call steal from SB/BB | Built |
| vs Steal 3-Bet | 3-bet vs steal from SB/BB | Built |

---

**POSTFLOP Section** — Two-block horizontal layout

*Left block — Per-street table:*
```
POSTFLOP                     Flop  Turn  River
Continuation Bet               45    59    53
Fold to Continuation Bet       46    46    35
Aggression                    2.8   3.5   5.1
Aggression Frequency           35    36    40
Donk Bet                        0     4    10
```
Columns: Stat | Flop | Turn | River

| Metric | Description | OHM Status |
|--------|-------------|------------|
| Continuation Bet (F/T/R) | C-bet % per street | Built |
| Fold to Continuation Bet (F/T/R) | Fold to c-bet % per street | Built |
| Aggression (F/T/R) | AF = (bets+raises)/calls per street | Built |
| Aggression Frequency (F/T/R) | AFq = (bets+raises)/(bets+raises+calls) % | Built |
| Donk Bet (F/T/R) | Donk bet % per street | Flop built, **Turn/River: wire up** |

*Right block — vs. Continuation Bet Flop breakdown:*
```
vs. ContinuationBet Flop    Fold  Call  Raise
Raised Pot                     46    32    21
3-Bet Pot                      45    45   9.9
```
Columns: Pot Type | Fold | Call | Raise

| Metric | Description | OHM Status |
|--------|-------------|------------|
| vs CBet Flop Fold (raised pot) | Fold to flop c-bet in single-raised pots | **NEW** — needs pot type tracking |
| vs CBet Flop Call (raised pot) | Call flop c-bet in single-raised pots | **NEW** |
| vs CBet Flop Raise (raised pot) | Raise flop c-bet in single-raised pots | **NEW** — this is check-raise |
| vs CBet Flop Fold (3-bet pot) | Fold to flop c-bet in 3-bet pots | **NEW** |
| vs CBet Flop Call (3-bet pot) | Call flop c-bet in 3-bet pots | **NEW** |
| vs CBet Flop Raise (3-bet pot) | Raise flop c-bet in 3-bet pots | **NEW** |

---

**MISSED C-BET Section** — Two-block horizontal layout

*Left block — Hero missed c-bet:*
```
Missed Continuation Bet   55
  In Position             44    → Fold   71
  Out of Position         74    → Fold   52
```

| Metric | Description | OHM Status |
|--------|-------------|------------|
| Missed C-Bet | % of c-bet opportunities where hero checked instead | Built |
| Missed C-Bet IP | Missed c-bet when in position | **NEW** — IP/OOP split |
| Missed C-Bet OOP | Missed c-bet when out of position | **NEW** — IP/OOP split |
| Missed C-Bet → Fold | After missing c-bet, fold to opponent bet | **NEW** — needs `missed_cbet_then_fold` |

*Right block — vs. Opponent missed c-bet:*
```
vs. Missed Continuation Bet   45
  Bet In Position              50    Check | Fold   76
  Bet Out of Position Turn     41    Check-Fold     67
```

| Metric | Description | OHM Status |
|--------|-------------|------------|
| vs Missed C-Bet | When opponent misses c-bet, hero bet % | **NEW** — needs `bet_vs_missed_cbet` |
| Bet vs Missed C-Bet IP | Probe bet when IP and opponent missed c-bet | **NEW** |
| Bet vs Missed C-Bet OOP | Probe bet when OOP and opponent missed c-bet | **NEW** |
| Check-Fold vs Missed C-Bet | Check then fold when opponent missed c-bet but bets later | **NEW** |

---

**SHOWDOWN Section** — Simple key-value list
```
Went to Showdown      24
Won at Showdown       58
Won When Saw Flop     48
```

| Metric | Description | OHM Status |
|--------|-------------|------------|
| WTSD% | Went to Showdown / Saw Flop | Built |
| W$SD% | Won at Showdown / Went to Showdown | Built |
| WWSF% | Won When Saw Flop / Saw Flop | Built |

---

**Color Coding Rules:**
- Green: stat value indicates strong/aggressive play for that position
- Red: stat value indicates weak/passive play (e.g. low open-raise from late position, high fold frequencies)
- Yellow: neutral/middling values
- Blue: used for certain BB-column values
- Gray + subscript: low sample size — value shown with sample count as subscript (e.g. `0₂` means 0% with only 2 samples)
- `--`: zero opportunities (stat not applicable)
- Empty cell: stat doesn't apply to that position (e.g. 3-Bet IP has no SB value)

Color thresholds are per-stat, per-position. Configurable in settings (Phase 3). For MVP, use hardcoded thresholds based on standard 6-max ranges.

---

**Complete Metric Inventory — New Stats Needed for H2N Layout:**

| # | Metric | Section | Parser | DB Column | Engine |
|---|--------|---------|--------|-----------|--------|
| 1 | 4-Bet Range | Preflop right | No | No (derived) | `4bet_count / total * 100` |
| 2 | Limp-Fold | Preflop right | Yes | `limp_fold BOOLEAN` | Yes |
| 3 | 4-Bet-Fold | Preflop right + Steal | Yes | `four_bet_fold BOOLEAN` | Yes |
| 4 | Call 4-Bet | Preflop right | Yes | `call_4bet BOOLEAN` | Yes |
| 5 | 4-Bet-Fold (steal) | Steal | Yes | Reuse `four_bet_fold` + steal context | Yes |
| 6 | Donk Bet Turn/River | Postflop left | No (in DB) | Already exists | Wire up |
| 7 | vs C-Bet Fold/Call/Raise by pot type | Postflop right | Yes | `pot_type VARCHAR` + `vs_cbet_action VARCHAR` | Yes |
| 8 | Missed C-Bet IP/OOP split | Missed C-Bet left | No | No (derive from position) | Yes |
| 9 | Missed C-Bet → Fold | Missed C-Bet left | Yes | `missed_cbet_then_fold BOOLEAN` | Yes |
| 10 | vs Missed C-Bet (probe bet) | Missed C-Bet right | Yes | `bet_vs_missed_cbet BOOLEAN` | Yes |
| 11 | vs Missed C-Bet IP/OOP | Missed C-Bet right | No | Derive from position | Yes |
| 12 | Check-Fold vs Missed C-Bet | Missed C-Bet right | Yes | `check_fold_vs_missed_cbet BOOLEAN` | Yes |
| 13 | Steal positional (SB/BB defense) | Steal right | No | Already computed | Make positional |

**Total: 13 new metrics** (7 need parser changes, 6 are derivable/wiring).

#### 3.2.1 Current Stats (Built)

All stats below are computed from `hand_players` flags via `stats_engine.py`.
Positional = broken down by EP/MP/CO/BTN/SB/BB. Simple = total only.

**Preflop (Positional):**
- VPIP, PFR, Open Raise
- 3-Bet (also IP/OOP split), 4-Bet
- Fold to 3-Bet, Fold to 4-Bet
- Call Open Raise, Limp

**Preflop (Simple):**
- 5-Bet, Squeeze

**Steal (Positional for CO/BTN/SB):**
- Steal Attempt
- Fold to 3-Bet (after steal), 4-Bet (after steal)
- vs Steal: Fold / Call / 3-Bet

**Postflop (Positional):**
- C-Bet Flop / Turn / River
- Fold to C-Bet Flop / Turn / River

**Postflop (Simple):**
- Donk Bet Flop
- Missed C-Bet Flop / Turn

**Aggression (Simple, per street):**
- AF Flop / Turn / River — (bets + raises) / calls
- AFq Flop / Turn / River — (bets + raises) / (bets + raises + calls) %

**Showdown (Simple):**
- WTSD% — Went to Showdown (saw flop → showdown)
- W$SD% — Won $ at Showdown
- WWSF% — Won When Saw Flop

**Results:**
- Hands count, Win Rate (bb/100)

**Filters (API supports):**
- Position, Stakes, Date From/To

#### 3.2.2 Missing Stats — Phase 1 (Core Gaps)

Stats that all three competitors (H2N, HM3, PT4) have and OHM lacks.

**New Preflop Stats:**
| Stat | Description | DB Column Needed | Parser Change |
|------|-------------|------------------|---------------|
| Cold Call | Call a raise without having voluntarily put money in preflop (excludes BB calling) | `cold_call BOOLEAN` | Track calls of raises when player hasn't acted yet |
| RFI (Raise First In) | Alias for open_raise, standard naming used by all 3 tools | Rename `open_raise` → `rfi` or alias | Display change only |
| 3-Bet Call | Called a 3-bet (vs fold/4-bet when facing 3-bet) | `call_3bet BOOLEAN` | Track in preflop aggression state machine |
| Fold to Squeeze | Folded when facing a squeeze | `fold_to_squeeze BOOLEAN`, `squeeze_opp BOOLEAN` | Track squeeze detection + response |

**New Postflop Stats:**
| Stat | Description | DB Column Needed | Parser Change |
|------|-------------|------------------|---------------|
| Check-Raise Flop/Turn/River | Check then raise on same street | `check_raise_flop/turn/river BOOLEAN`, `check_raise_flop/turn/river_opp BOOLEAN` | Track check→raise sequences per street |
| Probe Bet Flop/Turn/River | Bet into preflop raiser when they checked | `probe_bet_flop/turn/river BOOLEAN` | Track when non-PFR bets after PFR checks |
| Bet When Checked To | Bet when action checked to you | `bet_when_checked_to_flop/turn/river BOOLEAN` | Track check→bet by next actor |
| Donk Bet Turn/River | Columns exist in DB but not in stats engine | Already in schema | Wire up in `stats_engine.py` |
| Float Flop | Call flop bet in position, then bet/raise turn when checked to | `float_flop BOOLEAN` | Multi-street tracking |

**New Showdown Stats:**
| Stat | Description | Formula |
|------|-------------|---------|
| Saw Flop % | % of hands that saw the flop | `saw_flop / total_hands` |
| Saw Turn % | % of hands that saw the turn | `saw_turn / total_hands` |
| Saw River % | % of hands that saw the river | `saw_river / total_hands` |

**IP/OOP Breakdowns:**
All postflop stats (C-bet, fold to C-bet, check-raise, aggression) should have IP vs OOP splits, not just positional. Requires grouping CO/BTN/MP as IP and EP/SB/BB as OOP relative to opponent.

**Stats Engine Changes:**
- Add IP/OOP groupings to `_positional_pct`
- Wire donk_bet_turn/river into stats
- Add saw_flop/turn/river percentages
- Add win rate by position (bb/100 per position)

#### 3.2.3 Missing Stats — Phase 2 (Competitive Edge)

Features that differentiate the best tools from basic trackers.

**Bet Sizing Stats:**
| Stat | Description | Notes |
|------|-------------|-------|
| Avg Bet Size (Flop/Turn/River) | Average bet as % of pot per street | Needs pot tracking in `actions` table |
| Sizing Categories | Group bets into buckets: <33%, 33-50%, 50-66%, 66-80%, 80-100%, >100% pot | H2N has up to 256 board categories |
| Open Raise Size | Average open raise sizing by position | From actions table |
| 3-Bet Size | Average 3-bet sizing | From actions table |

**Population Stats (H2N's Killer Feature):**
| Feature | Description |
|---------|-------------|
| Player Type Classification | Auto-classify opponents: Fish (VPIP>40), Reg (VPIP 20-28, PFR 16-24), Nit (VPIP<15), LAG (PFR>25), TAG (PFR 18-24), Whale |
| Pool Tendencies by Spot | "How does the average fish at NL50 play BTN vs 3-bet?" |
| Multi-Player Aggregation | Select players by criteria, merge their stats into one report |
| Reg vs Fish Segmentation | Filter all stats by opponent type |
| Compare to Population | Show hero stats vs pool average |

**Player Lookup:**
| Feature | Description |
|---------|-------------|
| Search by name | Find any player in the DB |
| Full stat profile | All stats computed for any player, not just hero |
| Head-to-head stats | Your results specifically vs this player |
| Player list with mini-stats | Table of all players with VPIP/PFR/3B/hands |
| Color tags + notes UI | Manual labeling (schema exists, no UI yet) |

**Advanced Filtering:**
| Filter | Description | Implementation |
|--------|-------------|----------------|
| Board texture | Dry/Wet/Paired/Monotone/Broadway-heavy | Classify from `board_cards` table |
| Stack depth | Short (<40bb) / Medium (40-100bb) / Deep (>100bb) | From `hand_players.stack_bb` |
| Hand type | Pocket pairs, suited connectors, broadways, suited aces, etc. | From `hand_players.card1/card2` |
| Action sequence | "Faced 3-bet", "C-bet and got raised", etc. | Query `actions` table |
| Table size | 2-max, 6-max, 9-max | From `hands.table_size` |
| Opponent count at flop | How many players saw the flop | Count from `hand_players.saw_flop` |
| Pot type | Single-raised, 3-bet, 4-bet+ pot | From preflop action sequence |

#### 3.2.4 Missing Stats — Phase 3 (Power User)

**Custom Stat Creation:**
- H2N approach: filter-based stat builder (most powerful, steep learning curve)
- HM3 approach: HMQL type-ahead query language
- OHM approach (proposed): SQL-based custom stats — users write DuckDB SQL against `hand_players`/`actions` tables, results displayed as new stat columns. Simpler to implement, leverages DuckDB's power, appeals to technical users.

**Situational Views (HM3-style):**
Purpose-built dashboards for common spots instead of raw stat tables:
- C-Bet Situations: flop/turn/river C-bet %, success rate, sizing, by position, by board texture
- 3-Bet Pots: 3-bet %, call 3-bet %, fold to 3-bet, by position, outcomes
- Steal Situations: steal %, defense responses, by position
- River Play: river bet %, check-raise river %, fold to river bet

**Decision Analysis (H2N-style):**
- Action Profit: EV of each action in a specific spot (e.g., "when you c-bet flop IP in 3-bet pots, you win X bb on average")
- Spot Frequency: how often a situation occurs per 1000 hands
- Next Villain Actions: what opponents do after your action

**Range Diagrams (H2N-style):**
- 13x13 hand grid showing open/call/raise ranges per position
- Color-coded by action type
- Requires known hole cards (showdown data or hero cards)

#### 3.2.5 Stat Priorities Summary

| Priority | What | Why | Effort |
|----------|------|-----|--------|
| P0 | Donk bet turn/river, saw flop/turn/river %, win rate by position | Data exists, just wire up | Small |
| P0 | Check-raise (flop/turn/river) | Every competitor has it, players expect it | Medium (parser + DB + engine) |
| P0 | Cold call, 3-bet call | Core preflop stats missing from all 3 competitors | Medium |
| P1 | Probe bet, float, bet when checked to | Important postflop stats for study | Medium |
| P1 | IP/OOP splits for all postflop stats | Standard in H2N/HM3, critical for analysis | Medium |
| P1 | Player lookup (any player stats, not just hero) | Enables opponent research | Medium (new endpoint + UI) |
| P1 | Advanced filters: stack depth, hand type, table size | Basic analysis requires these | Medium |
| P2 | Bet sizing stats | Differentiating analysis feature | Large (pot tracking needed) |
| P2 | Population stats / player classification | H2N's killer feature, big competitive edge | Large |
| P2 | Board texture filtering | Deep postflop analysis | Large (board classification logic) |
| P2 | Action sequence filtering | "Show me all hands where I faced a check-raise on flop" | Large |
| P3 | Custom stat creation (SQL-based) | Power user feature | Large |
| P3 | Situational views | HM3's best feature, complex UI | Large |
| P3 | Decision analysis / EV per action | H2N Pro feature, hard to compute | Very Large |
| P3 | Range diagrams | Requires sufficient showdown data | Large |

### 3.3 Player Database

**Player Identification:**
- By screen name + site
- Merge aliases (same player, different names)
- Notes system (text + color tags)

> Player lookup, population analysis, and advanced filtering are detailed in Section 3.2 (Phases 2-3).

### 3.4 Reports & Analytics

> Graphs, leak finder, and situational views are detailed in Section 3.2 (Phases 2-3).

**Graph Lines (Built):**
- Cumulative BB won, Cumulative $ won
- All-in EV line (BB and $)
- Cumulative rake (BB and $), Cumulative jackpot/BBJ (BB and $)
- Won at Showdown / Won without Showdown (BB and $)
- BB/$ toggle, toggleable line visibility, stat cards with dual units

**Results Dashboard (Built):**
- Filter bar: stakes selector, date range presets (today/week/month/all), last N hands
- Stat cards: Hands, Won, Winrate, EV Won, EV Winrate, Rake, Rake/100, SD Won, NSD Won, BBJ breakdown
- Breakdown tables: by stakes, by month, by position (with BB/100 and EV BB/100)

**Graph Lines (Planned):**
- Per-session vertical markers
- Confidence interval band
- Dispersion/variance visualization with winrate estimate ranges

**Reports (Planned):**
- Best/worst hands breakdown
- Session-by-session results

### 3.5 Hand Browser

**List View:**
- Sortable columns (date, stake, result, players)
- Quick filters
- Infinite scroll / pagination

**Hand Detail View:**
- Actions at each street
- Pot size at each decision
- Villain stats shown inline
- Notes field per hand
- Tags (bluff, value, cooler, mistake, etc.)

**Search:**
- Find hands by criteria
- "Show me all hands where I 3bet AK from SB and faced 4bet"

### 3.6 Session Tracking

**Session List:**
- Date, duration, hands played
- Stake(s) played
- Result (BB won, $ won)
- Tables played

**Session Detail:**
- Timeline of hands
- Running total graph
- Notable hands flagged

---

## 4. Technical Architecture

### 4.1 Stack

```
┌─────────────────────────────────────────────────────┐
│                 React Frontend                       │
│    (React 19, TypeScript 5.9, Vite 7, Tailwind v4) │
│              localhost:5173 (dev)                    │
├─────────────────────────────────────────────────────┤
│              Python 3.12+ Backend                    │
│   (FastAPI, DuckDB, PyArrow, eval7, Pydantic)       │
│              localhost:8000                          │
├─────────────────────────────────────────────────────┤
│                   DuckDB                             │
│           (single file: data/poker.duckdb)          │
└─────────────────────────────────────────────────────┘
```

> Electron was dropped for MVP — the app runs as a local web app via `make dev`.
> It can be added later when native packaging is needed.

### 4.2 Component Breakdown

**React Frontend:**
- Pages: Upload, Stats, Results, Hands (currently), more planned (Players, Reports, Settings)
- State: Plain React state (Zustand/React Query can be added when complexity warrants it)
- Charts: Recharts 3
- UI: TailwindCSS v4 with custom dark theme (@theme in CSS)

**Python Backend:**
- FastAPI for REST API
- DuckDB for all data storage
- Parsers: one module per poker site
- Stats engine: calculate all stats from raw hands

**File Structure (actual):**

```
holdem-manager/
├── frontend/
│   ├── src/
│   │   ├── main.tsx            # React entry (StrictMode)
│   │   ├── App.tsx             # Router: Upload / Stats / Results / Hands tabs
│   │   ├── index.css           # Tailwind v4 @theme with dark color palette
│   │   ├── components/
│   │   │   └── hands/          # Hand browser components (CardDisplay, etc.)
│   │   ├── lib/
│   │   │   └── api.ts          # Typed API client (fetch wrapper, NDJSON streaming)
│   │   └── pages/
│   │       ├── UploadPage.tsx   # Drag & drop import, progress bar, clear DB
│   │       ├── StatsPage.tsx    # H2N-style stat tables with positional columns
│   │       ├── GraphPage.tsx    # Results dashboard (graph, stat cards, breakdowns)
│   │       └── HandsPage.tsx    # Hand browser with filtering, tagging, detail drawer
│   ├── package.json
│   └── vite.config.ts          # React plugin, Tailwind v4 plugin, API proxy to :8000
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app, CORS, startup, health
│   │   ├── db.py               # DuckDB connection, schema init, migrations
│   │   ├── models.py           # Pydantic response models
│   │   ├── stats_engine.py     # H2N-style stat computation from hand_players
│   │   ├── stat_flags.py       # Site-independent stat flag computation (40+ flags)
│   │   ├── parsers/
│   │   │   └── ggpoker.py      # GGPoker hand history parser → ParsedHand
│   │   └── api/
│   │       ├── import_hands.py  # Import endpoints + insert_parsed_hand + player cache
│   │       ├── stats.py         # GET /api/stats/hero
│   │       ├── reports.py       # GET /api/reports/graph, filter-options, breakdown
│   │       ├── hands.py         # Hand browser: list, detail, tags, notes
│   │       └── settings.py      # GET/PATCH /api/settings
│   ├── tests/
│   │   ├── test_parser.py       # 11 tests across 5 classes
│   │   └── fixtures/            # Sample hand histories
│   └── requirements.txt
├── Makefile
├── CLAUDE.md
└── PRD.md
```

### 4.3 Database Schema (DuckDB)

```sql
-- Core tables

CREATE TABLE sites (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,          -- 'PokerStars', 'GGPoker'
    code VARCHAR NOT NULL UNIQUE    -- 'PS', 'GG'
);

CREATE TABLE players (
    id INTEGER PRIMARY KEY,
    site_id INTEGER REFERENCES sites(id),
    username VARCHAR NOT NULL,
    notes TEXT,
    color_tag VARCHAR,              -- 'fish', 'reg', 'whale', etc.
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    UNIQUE(site_id, username)
);

CREATE TABLE hands (
    id VARCHAR PRIMARY KEY,         -- Site's hand ID
    site_id INTEGER REFERENCES sites(id),
    played_at TIMESTAMP NOT NULL,
    game_type VARCHAR NOT NULL,     -- 'NL Hold''em', 'PLO'
    stakes VARCHAR NOT NULL,        -- '$0.50/$1.00'
    table_name VARCHAR,
    table_size INTEGER,             -- 6, 9
    button_seat INTEGER,

    -- Raw text for debugging
    raw_text TEXT,

    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hand_players (
    id INTEGER PRIMARY KEY,
    hand_id VARCHAR REFERENCES hands(id),
    player_id INTEGER REFERENCES players(id),
    seat INTEGER NOT NULL,
    position VARCHAR NOT NULL,      -- 'BTN', 'SB', 'BB', 'EP', 'MP', 'CO'
    stack_bb DECIMAL,               -- Stack in big blinds

    -- Hole cards (if known)
    card1 VARCHAR,
    card2 VARCHAR,
    card3 VARCHAR,                  -- For PLO
    card4 VARCHAR,

    -- Results
    won_bb DECIMAL,
    rake_bb DECIMAL,

    -- Preflop actions (denormalized for speed)
    vpip BOOLEAN DEFAULT FALSE,
    pfr BOOLEAN DEFAULT FALSE,
    three_bet BOOLEAN DEFAULT FALSE,
    four_bet BOOLEAN DEFAULT FALSE,
    fold_to_3bet BOOLEAN,
    fold_to_4bet BOOLEAN,

    -- Postflop flags
    saw_flop BOOLEAN DEFAULT FALSE,
    saw_turn BOOLEAN DEFAULT FALSE,
    saw_river BOOLEAN DEFAULT FALSE,
    went_to_showdown BOOLEAN DEFAULT FALSE,
    won_at_showdown BOOLEAN,

    -- CBet tracking
    cbet_flop BOOLEAN,
    cbet_turn BOOLEAN,
    cbet_river BOOLEAN,
    fold_to_cbet_flop BOOLEAN,
    fold_to_cbet_turn BOOLEAN,
    fold_to_cbet_river BOOLEAN
);

CREATE TABLE actions (
    id INTEGER PRIMARY KEY,
    hand_id VARCHAR REFERENCES hands(id),
    player_id INTEGER REFERENCES players(id),
    street VARCHAR NOT NULL,        -- 'preflop', 'flop', 'turn', 'river'
    action_order INTEGER NOT NULL,
    action_type VARCHAR NOT NULL,   -- 'fold', 'check', 'call', 'bet', 'raise', 'allin'
    amount_bb DECIMAL,
    pot_before_bb DECIMAL,
    is_all_in BOOLEAN DEFAULT FALSE
);

CREATE TABLE board_cards (
    hand_id VARCHAR REFERENCES hands(id),
    street VARCHAR NOT NULL,        -- 'flop', 'turn', 'river'
    card VARCHAR NOT NULL,
    card_order INTEGER NOT NULL
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    hands_played INTEGER,
    won_bb DECIMAL,
    stakes VARCHAR,
    notes TEXT
);

CREATE TABLE hand_tags (
    hand_id VARCHAR REFERENCES hands(id),
    tag VARCHAR NOT NULL,           -- 'bluff', 'value', 'cooler', 'mistake'
    PRIMARY KEY (hand_id, tag)
);

CREATE TABLE hand_notes (
    hand_id VARCHAR PRIMARY KEY REFERENCES hands(id),
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for common queries
CREATE INDEX idx_hands_played_at ON hands(played_at);
CREATE INDEX idx_hands_stakes ON hands(stakes);
CREATE INDEX idx_hand_players_player_id ON hand_players(player_id);
CREATE INDEX idx_hand_players_position ON hand_players(position);
CREATE INDEX idx_actions_hand_id ON actions(hand_id);
```

### 4.4 API Endpoints

```yaml
# Import (✅ built)
POST   /api/import/files           # Synchronous multipart upload (50MB limit)
POST   /api/import/files/stream    # Streaming upload, NDJSON progress (start/progress/done)
POST   /api/import/clear           # Truncate all hand data
POST   /api/import/rebuild         # Re-parse all hands from stored raw_text

# Hands (✅ built)
GET    /api/hands                  # List hands (paginated, sorted, filtered by position/stakes/result/tags/date)
GET    /api/hands/{id}             # Get hand detail (all players, actions, board, raw text)
POST   /api/hands/{id}/tags        # Add tag
DELETE /api/hands/{id}/tags/{tag}  # Remove tag
GET    /api/tags                   # List all tags with counts
PUT    /api/hands/{id}/note        # Update hand note
DELETE /api/hands/{id}/note        # Delete hand note

# Reports (✅ built)
GET    /api/reports/graph          # Graph data: cumulative BB/$, EV, SD/NSD, rake, jackpot lines
GET    /api/reports/filter-options  # Available stakes and date ranges
GET    /api/reports/breakdown      # Results by stakes, month, position

# Stats (✅ built)
GET    /api/stats/hero             # Hero stats with filters (position, stakes, date_from, date_to)

# Settings (✅ built)
GET    /api/settings               # Get hero_username, hero_site
PATCH  /api/settings               # Update settings

# System (✅ built)
GET    /api/health                 # Returns {status, hands}

# Planned (not built)
GET    /api/players                # List/search players
GET    /api/players/{id}           # Get player detail + stats
GET    /api/players/{id}/hands     # Get hands with player
PATCH  /api/players/{id}/note      # Update player note
PATCH  /api/players/{id}/color     # Update color tag
POST   /api/players/merge          # Merge two player profiles
GET    /api/stats/player/{id}      # Full stats for any player
GET    /api/stats/population       # Pool stats with filters
GET    /api/reports/leaks          # Leak finder
GET    /api/reports/drift          # Strategy drift detection (z-scores)
POST   /api/import/watch           # Start watching folder
```

---

## 5. User Interface

### 5.1 Pages

**Dashboard**
- Quick stats: hands today/week/month, winrate
- Recent sessions
- Quick actions: Import, View Hands, Find Player

**Hands Browser**
- Table with columns: Date, Stakes, Position, Cards, Result, Villain
- Filters sidebar
- Click row → Hand detail modal/drawer

**Hand Detail**
- Street-by-street actions
- Villain stats inline
- Note editor
- Tag selector

**Players**
- Search bar
- Player list with mini stats
- Click → Full player stats page

**Player Detail**
- All stats in sections (Preflop, Postflop, Tendencies)
- Position breakdown
- Hand history with this player
- Notes

**Reports**
- Tab: My Results (graphs, winrate)
- Tab: Leak Finder (negative EV spots)
- Tab: Population (pool analysis)
- Tab: Positional (stats by position)

**Settings**
- HH folder paths
- Hero username(s)
- Display preferences
- Database management (backup, optimize)

### 5.2 Key UI Components

```
HandsTable
├── FiltersSidebar
├── ColumnSelector
├── HandRow
│   └── MiniHandPreview
└── Pagination

PlayerCard
├── Avatar (color-coded by type)
├── MiniStats (VPIP/PFR/3B)
└── QuickActions

StatsGrid
├── StatBox (label, value, delta)
└── StatTooltip (explanation)

WinrateChart
├── TimeRangeSelector
├── LineChart (BB/100 over time)
└── ConfidenceInterval

HandReplay (simple text version)
├── StreetHeader
├── ActionLine
├── PotDisplay
└── BoardCards
```

---

## 6. Non-Functional Requirements

### Performance
- Import: ~1,700 hands/second (current, target 5,000+)
- Query: <100ms for player stats lookup
- UI: 60fps scrolling through hand list
- Startup: <3 seconds to usable state

### Storage
- 1M hands < 500MB disk space
- Efficient compression (DuckDB handles this)

### Reliability
- No data loss on crash (DuckDB ACID)
- Graceful handling of malformed hand histories
- Auto-recovery from corrupted state

### Security
- All data local (no cloud)
- No telemetry without consent
- Safe handling of file paths

### Compatibility
- Windows 10+ (x64)
- macOS 12+ (Intel + Apple Silicon)
- Linux (Ubuntu 20.04+, AppImage)

---

## 7. Roadmap

### Phase 1: Foundation (current)

What's built:
- [x] GGPoker Rush & Cash parser (60+ stat flags, 40+ opportunity flags, all-in EV, rake + jackpot tracking)
- [x] Streaming file import (drag & drop files/folders/ZIPs, duplicate detection, progress bar)
- [x] Stats page — H2N-style layout with positional breakdowns
- [x] Results dashboard — cumulative BB/$ graph with toggleable lines (EV, SD/NSD, rake), stat cards, breakdowns by stakes/month/position, date/stakes/last-N filters
- [x] Hero settings (username/site config)
- [x] Rebuild endpoint (re-parse all hands from stored raw_text)
- [x] Fix stat calculation bugs — 7 fixed for H2N parity (AFq, Steal%, C-Bet, Donk Bet, 3-Bet Opp, Squeeze, 5-Bet)
- [x] Positional winrate report — BB/100 by EP/MP/CO/BTN/SB/BB in results breakdown
- [x] Stat flag extraction — site-independent `stat_flags.py` module (parse/compute/insert pipeline)
- [x] Stakes normalization — cross-reference header/posted blinds, fix GGPoker byte corruption
- [x] Performance — PyArrow batch inserts, eval7 equity, Python 3.12 (~1,700 hands/sec, up from ~138)

What's next (complete the foundation):
- [ ] **Verify stats end-to-end** — compare OHM output against H2N for same hand sample
- [ ] **Missing H2N stats** — 13 new metrics from Section 3.2.0 (limp-fold, 4-bet-fold, call-4bet, vs cbet by pot type, missed cbet IP/OOP, probe bets)
- [ ] **Phase 1 core gaps** — cold call, 3-bet call, check-raise, IP/OOP splits (see Section 3.2.2)

### Phase 2: Hand Review & Study Tools

The features every poker coach recommends. Enables the core study workflow.

- [x] **Hand browser** — paginated list with columns (cards, actions, board, stakes, result, date, tags), sortable, filterable by position/stakes/result/tags/date
- [x] **Hand detail view** — street-by-street actions with amounts in BB, board cards, player stacks, hero actions underlined
- [x] **Hand tagging** — tag hands with custom labels, filter by tag, tag pills in list view
- [x] **Hand notes** — per-hand text notes with create/update/delete
- [ ] **Mark-and-review workflow** — filter by tag, step through tagged hands with keyboard nav (←/→)
- [ ] **"Biggest losers" filter** — auto-surface medium-loss hands (10-30 BB lost, not coolers) for study
- [ ] **Results by starting hand (13x13 heat map)** — aggregate won_bb by hand combo on a color-coded grid. Data exists in `hand_players.card1/card2`. Killer study tool — instantly shows which hands are bleeding money by position
- [ ] **Hand export** — copy hand as formatted text (for sharing in Discord/forums/coaches), export to solver-compatible format (PioSolver/GTO Wizard input)

### Phase 3: Opponent Research & Player Database

Turn your hand history into an opponent intelligence system.

- [ ] **Player search & lookup** — find any player in DB, show full stat profile (reuse stats engine with player_id instead of hero)
- [ ] **Player list** — table of all opponents with mini-stats (hands, VPIP, PFR, 3-Bet, AF), sortable
- [ ] **Head-to-head stats** — your results specifically vs a given player, positional breakdown
- [ ] **Player notes + color tags UI** — manual labeling (schema fields exist on `players` table, no UI yet)
- [ ] **Auto player classification** — auto-tag opponents based on stat thresholds:
  - Fish: VPIP > 40
  - Calling Station: VPIP > 35, AF < 1.5
  - Nit: VPIP < 15
  - TAG: VPIP 20-28, PFR 16-24
  - LAG: VPIP > 28, PFR > 25
  - Whale: VPIP > 50
  Color-code in all player lists and hand browser.
- [ ] **Range research (H2N's crown jewel)** — aggregate all showdown hands for a player in a given spot (e.g., "3-bet from BTN") and display on a 13x13 hand matrix. H2N charges $49/mo for this. With DuckDB: `SELECT card1, card2, COUNT(*) FROM hand_players WHERE player_id=? AND card1 IS NOT NULL AND three_bet=TRUE GROUP BY card1, card2`. Render as a color-coded grid.
- [ ] **Automatic note-taking** — when opponents show down, auto-record: "Villain open-limped 77 from EP", "Villain called 3-bet with T9s OOP". Accumulate over time, show on player profile.

### Phase 4: Advanced Analysis & Reports

Features that differentiate OHM from basic trackers.

- [ ] **Session tracking** — auto-detect sessions (30+ min gap = new session). Session list: date, duration, hands, stakes, result. Per-session graph.
- [ ] **Calendar view** — month grid, each day color-coded green/red by profit. Click day → sessions. Click session → hands. (PT4's most loved feature)
- [ ] **Population analysis** — aggregate all opponent stats by player type, stake, position. "How does the average fish at NL50 play BTN vs 3-bet?" Compare hero stats to pool average.
- [ ] **Leak finder** — compare hero stats against winning player benchmarks. Flag statistical outliers. PT4's LeakTracker approach: check 50+ potential weak areas, score each by impact, suggest what to study.
- [ ] **Bet sizing analysis** — track bet sizes as % of pot. Buckets: <33%, 33-50%, 50-66%, 66-100%, >100%. Average sizing by street, position, pot type. At modern stakes, sizing tells are the most exploitable pattern.
- [ ] **Board texture stats** — classify boards from `board_cards`:
  - Dry: rainbow, unconnected
  - Wet: flush/straight draws present
  - Paired: pair on board
  - Monotone: three suited
  - Broadway-heavy: 2+ cards T+
  Cross-reference all postflop stats (c-bet, fold-to-cbet, aggression) by board texture.
- [ ] **Advanced filters** — filter any report by: board texture, stack depth (<40bb/40-100bb/>100bb), hand type (pairs, suited connectors, broadways), action sequence ("faced c-bet on flop and raised"), pot type (single-raised/3-bet/4-bet+), table size, opponent count at flop
- [ ] **GTO deviation index** — single "exploitability score" per player. Weighted deviation from solver-derived baseline frequencies across key stats. Quick read: "how far from optimal is this opponent?"

### Phase 5: Power User Features

- [ ] **Variance calculator** — Monte Carlo simulation: input winrate + standard deviation, simulate 10k sample paths. Show: probability of downswing depths, expected duration, bankroll requirements. Pure frontend math, no DB needed. Players use this to separate tilt from reality.
- [ ] **Visual hand replayer** — poker-table-style animated replay: chip stacks, pot size, community cards, player actions in sequence. Play/pause, step forward/back, speed slider, BB/$ display mode.
- [ ] **Shareable hand replays** — generate a shareable URL or image of a hand replay for posting in study groups, Discord, social media
- [ ] **Custom stat creation (SQL-based)** — users write DuckDB SQL against `hand_players`/`actions` tables, results displayed as new stat columns. Simpler than H2N's filter builder, leverages DuckDB's power, appeals to technical open-source audience.
- [ ] **Situational views (HM3-style)** — purpose-built dashboards: C-Bet Situations (by position, board texture, pot type), 3-Bet Pots, Steal Situations, River Play
- [ ] **Decision analysis (H2N-style)** — Action Profit: EV of each action in a specific spot. Spot Frequency: how often a situation occurs per 1000 hands. Next Villain Actions: what opponents do after your action.
- [x] **Winrate by stake level** — BB/100 and total profit/loss per stake in results dashboard breakdowns.
- [x] **Rake & rakeback tracking** — total rake + jackpot paid per stake, rake/100, BBJ breakdown. Projected rakeback not yet implemented.
- [ ] **Strategy Drift Detection (unique to OHM)** — no major tracker has this as a first-class feature. Monitors rolling windows of key stats and alerts when your game deviates from your baseline. Detects tilt, fatigue, scared money, and slow strategic drift before they cost significant money.

  **How it works:**
  1. Compute lifetime baseline stats (your "A-game" profile)
  2. Continuously compute stats over rolling windows (last 500, 1k, 2k, 5k, 10k hands)
  3. Compare rolling stats to baseline using z-scores: `z = (rolling_mean - lifetime_mean) / lifetime_stddev`
  4. Flag when |z| > 2.0 (statistically significant deviation)

  **Stats to monitor (and what drift means):**
  | Stat | Drift Up | Drift Down |
  |------|----------|------------|
  | VPIP | Playing too loose (tilt/boredom) | Playing too tight (scared money) |
  | PFR | Over-aggression (tilt) | Passivity (fear/fatigue) |
  | AF postflop | Spewing (maniac mode) | Calling station mode |
  | WTSD | Can't let go, calling too much | Over-folding postflop |
  | Fold to 3-Bet | — | Calling too many 3-bets (ego/tilt) |
  | W$SD | — (running good?) | Bad calls getting to showdown |
  | Non-SD winnings trend | — | Red line plummeting = folding too much postflop |
  | Win rate (bb/100) | — | Losing more than expected |
  | C-Bet Flop | Autopilot c-betting | Missing value / checking too much |

  **UI:**
  - Dashboard widget: stat health indicators (green/yellow/red dots per stat)
  - Specific alert text: "Your VPIP increased from 23% to 31% over the last 2000 hands (+3.2σ)"
  - Trend arrows next to stats on the stats page (↑↓ with color)
  - Configurable windows and thresholds in settings
  - Optional: "A-game score" — single composite number (0-100) based on how close current play matches your baseline

  **Implementation:**
  - Backend: `GET /api/reports/drift?window=2000` — returns per-stat z-scores comparing last N hands to lifetime
  - Pure SQL: two queries against `hand_players` (lifetime WHERE player_id=hero vs last N hands ORDER BY played_at DESC LIMIT N), compute means, compare
  - No new schema needed — derived from existing stat flags
  - Low effort, high impact, completely unique feature

### Phase 6: Platform & Ecosystem

- [ ] **Auto-import (watch folders)** — monitor hand history directories, auto-import new files
- [ ] **PokerStars parser**
- [ ] **More site parsers** (Winamax, 888, PartyPoker)
- [ ] **Electron packaging** for Win/Mac/Linux
- [ ] **Database backup/restore** — export/import full DB as compressed file
- [ ] **Solver integration** — one-click export hand to PioSolver/GTO Wizard format

### Not Planned

- HUD overlay — GGPoker bans them, primary user can't use it
- Tournament / SNG support — cash game focus
- ICM calculator — cash only
- Cloud sync — local-first philosophy
- Plugin marketplace — premature at current stage
- Mobile companion — web app works on mobile already

---

## 8. Success Metrics

### Adoption
- GitHub stars
- Downloads per month
- Active users (opt-in telemetry)

### Quality
- Import success rate (% hands parsed correctly)
- Crash rate
- GitHub issues/bugs reported

### User Satisfaction
- Feature requests vs complaints ratio
- Community contributions (PRs)
- Reddit/forum mentions

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Parser breaks when site updates HH format | High | Version detection, community reports, quick patches |
| Performance degrades at scale (10M+ hands) | Medium | DuckDB handles this well, add indexes as needed |
| Legal issues from poker sites | Low | Open source, local only, no real-time HUD |
| Python bundling issues on different OS | Medium | Extensive CI testing, user bug reports |
| Competition from free tools | Low | Focus on open-source community, better UX |

---

## 10. Open Questions

1. **Licensing**: MIT? GPL? (affects commercial use)
2. **Name**: Need a good project name
3. **Monetization** (optional): Donations? Pro features? Hosted version?
4. **HUD**: Build as separate tool or integrated? (legal gray area)
5. **Tournament support**: How much priority in MVP?

---

## Appendix A: Hand History Format Examples

### PokerStars

```
PokerStars Hand #234567890123: Hold'em No Limit ($0.50/$1.00 USD) - 2025/01/30 12:34:56 ET
Table 'Acamar III' 6-max Seat #3 is the button
Seat 1: Player1 ($100 in chips)
Seat 2: Player2 ($85.50 in chips)
Seat 3: Hero ($120 in chips)
...
```

### GGPoker

```
Poker Hand #RC1234567890: Tournament #12345678, $10+$1 Hold'em No Limit - Level I (25/50) - 2025/01/30 12:34:56
Table '12345678 1' 9-max Seat #5 is the button
Seat 1: Player1 (5000 in chips)
...
```

---

## Appendix B: Stat Formulas

```python
# Core stats

VPIP = (hands_voluntarily_put_money_preflop / total_hands) * 100
PFR = (hands_raised_preflop / total_hands) * 100
3Bet = (times_3bet / opportunities_to_3bet) * 100
Fold_to_3Bet = (times_folded_to_3bet / times_faced_3bet) * 100
AF = (bets + raises) / calls  # Aggression Factor
AFq = ((bets + raises) / (bets + raises + calls + folds)) * 100
WTSD = (hands_went_to_showdown / hands_saw_flop) * 100
W$SD = (hands_won_at_showdown / hands_went_to_showdown) * 100
CBet = (times_cbet / opportunities_to_cbet) * 100
```

---

## Appendix C: Competitor Feature Comparison

| Feature | Hand2Note | HM3 | This Project (current) |
|---------|-----------|-----|----------------------|
| HUD | ✅ Advanced | ✅ Good | ❌ Not planned |
| Hand Import | ✅ Multi-site | ✅ Multi-site | ✅ GGPoker only |
| Player Stats | ✅ | ✅ | ✅ Hero only (opponent lookup planned) |
| Hand Browser | ✅ | ✅ | ✅ With tags, notes, filters |
| Results Dashboard | ✅ | ✅ | ✅ Graph + breakdowns by stakes/month/position |
| Reports | ✅ | ✅ | ⚠️ Basic (no leak finder yet) |
| Population Analysis | ✅ (paid) | ❌ | ❌ Planned |
| Leak Finder | ✅ | ✅ | ❌ Planned |
| Hand Replayer | ✅ | ✅ | ⚠️ Text only (detail drawer) |
| Price | $15-39/mo | $100 once | Free |
| Open Source | ❌ | ❌ | ✅ |
