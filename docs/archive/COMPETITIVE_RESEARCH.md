# Competitive Research: H2N vs HM3 vs PT4

> Research conducted Feb 2026 to inform OHM roadmap priorities.

---

## Feature Comparison

### Import & Data

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Auto-import (watch folders) | Yes | Yes | Yes | No |
| ZIP import | Yes | Yes | Yes | Yes |
| GGPoker support | Native (v4) | Yes | Offline only | Yes |
| DB import from competitors | PT4/HM2 | HM2 | HM | - |
| Mac support | Yes (v4) | No (Parallels) | Yes (native) | Yes (web) |
| No external DB install | Yes | Yes (removed PostgreSQL in v3) | No (PostgreSQL) | Yes (DuckDB) |
| Multi-site parsers | 12+ sites | 12+ sites | 12+ sites | GGPoker only |

### HUD

> Not relevant for GGPoker (bans HUDs). Included for completeness.

| Feature | H2N | HM3 | PT4 |
|---------|-----|-----|-----|
| Static HUD | Yes | Yes | Yes |
| Dynamic/positional HUD | Yes (unique) | No | No |
| Graphical HUD (ring charts) | No | Yes (unique) | No |
| HUD popups with drilldown | Yes | Yes | Yes |
| Auto HUD (AI-selected stats) | Yes (Pro) | No | No |
| HUD marketplace | Yes | Yes (Apps) | Yes (Download Warehouse) |

### Stats & Analysis

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Preflop stats (VPIP/PFR/3B etc.) | Yes | Yes | Yes | Yes (60+ flags) |
| Positional breakdowns | Yes | Yes | Yes | Yes |
| Per-street C-bet/aggression | Yes | Yes | Yes | Yes |
| Steal/defense stats | Yes | Yes | Yes | Yes |
| Custom stat creation | Yes (most powerful) | Yes (HMQL) | Yes | No |
| Total stats available | Hundreds | 2000+ | Hundreds | ~60 flags |

### Reports & Graphs

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Cumulative P&L graph | Yes | Yes | Yes | Yes |
| All-in EV line | Yes | Yes | Yes | Yes (basic) |
| Won at SD / Won w/o SD lines | Yes | Yes | Yes | No |
| BB/$ toggle | Yes | Yes | Yes | Yes |
| Session reports | Yes | Yes | Yes | No |
| Situational views (C-bet, 3bet) | Smart Reports | Yes (unique) | Custom reports | No |
| Calendar view | No | No | Yes (unique) | No |
| Luck bell curve | No | No | Yes (unique) | No |
| Custom report builder | Yes | Yes | Yes | No |

### Leak Finding & Study

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Leak finder | Yes | Via reports | LeakTracker (unique) | No |
| Population analysis | Yes (killer feature) | No | No | No |
| Hand range heatmaps | Yes (range diagrams) | No | Yes (unique) | No |
| Decision analysis (EV per action) | Yes (unique) | No | No | No |
| Equity calculator | No | No | Yes (built-in) | No |
| ICM calculator | No | No | Yes (built-in) | No |

### Hand Review

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Visual hand replayer | Yes | Yes | Yes | No |
| Hand-to-video export | No | No | Yes (unique) | No |
| Hand tagging/notes | Yes | Yes | Yes | No |
| Keyboard nav (arrows) | Yes | Yes | Yes | No |
| Stats at time of play | No | Yes (unique) | No | No |

### Opponent Profiling

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Player search/lookup | Yes | Yes | Yes | No |
| Color-coded player tags | Yes | Yes | Yes | Schema only |
| Auto-notes | Add-on | NoteCaddy (add-on) | NoteTracker (built-in) | No |
| Player type classification | Manual + auto-color | Via NoteCaddy | NoteTracker rules | No |
| Alias merging | Yes | Yes | Yes | No |

### Filtering

| Feature | H2N | HM3 | PT4 | OHM (current) |
|---------|-----|-----|-----|----------------|
| Position filter | Yes | Yes | Yes | Yes |
| Stakes filter | Yes | Yes | Yes | Yes |
| Date range filter | Yes | Yes | Yes | Yes |
| Board texture filter | Yes | Yes | Yes | No |
| Stack depth filter | Yes | Yes | Yes | No |
| Custom filter expressions | Yes (most powerful) | HMQL (type-ahead) | Custom expressions | No |
| Hand type filter (AA, suited connectors) | Yes | Yes | Yes | No |
| Action sequence filter | Yes | Yes | Yes | No |

### Pricing

| | H2N | HM3 | PT4 | OHM |
|--|-----|-----|-----|-----|
| Free tier | 14-day trial | 14-day trial | 14-day trial | Free (open-source) |
| Entry | $15.99/mo (Learner, microstakes only) | $60 one-time (small stakes) | $29.99 one-time (small stakes) | - |
| Full | $49/mo (Pro) | $100 one-time | $49.99 one-time | - |
| Model | Subscription | Lifetime + optional annual maintenance | Lifetime + optional annual maintenance | Free forever |

---

## Per-Tool Summaries

### Hand2Note (H2N)

**Strengths:**
- Dynamic/positional HUD — changes displayed stats based on in-hand context (unique to H2N)
- Population analysis / Multi-Player Reports — aggregate opponent data by archetype (H2N's killer feature)
- Range diagrams — visual 13x13 grids showing open/call/raise ranges per opponent
- Decision analysis — EV of each action in a specific spot, spot frequency per 1000 hands
- Smart Reports — context-aware reports that auto-select relevant stats based on the spot
- Custom filter system — widely considered the most powerful on the market
- Auto HUD — algorithmically picks the most relevant stat for the current situation

**Weaknesses:**
- Steep learning curve, complex UI
- Most powerful features locked behind $49/mo Pro subscription
- HUD features restricted on some sites (PokerStars, Winamax)

**Most-praised by users:** Dynamic HUD, population analysis, filter depth, advanced popups

### Holdem Manager 3 (HM3)

**Strengths:**
- Situational Views — dedicated dashboards for C-bet, 3-bet, river play, tournament all-ins
- HMQL — type-ahead query language for building filters (faster than dropdown menus)
- Graphical HUD — ring/circle charts showing VPIP/PFR/aggression visually
- No PostgreSQL — embedded DB, simple install (fixed HM2's biggest pain point)
- NoteCaddy integration — automated opponent note-taking based on behavioral patterns
- Live Play view — real-time session graph with instant hand replay
- Apps marketplace — plugin ecosystem (TableNinja, NoteCaddy, etc.)

**Weaknesses:**
- Windows only (no native Mac)
- Some features require paid add-ons (NoteCaddy, TableNinja)
- Annual maintenance fees after year 1

**Most-praised by users:** Clean UI, ease of use, graphical HUD, situational views, no PostgreSQL

### PokerTracker 4 (PT4)

**Strengths:**
- LeakTracker — compares your stats to winning benchmarks, flags weaknesses with instructional content
- Native Mac + Windows support (C++ app)
- Built-in equity and ICM calculators (no add-ons needed)
- Hand range heatmaps — visual 13x13 grid mapping any stat to hand matrix
- NoteTracker — automated opponent profiling (built-in, not a paid add-on)
- Hand replayer with video export — export hands as video for coaching/sharing
- Drag-and-drop HUD editor — considered the best visual HUD builder
- Calendar view — month-by-month drill-down into sessions
- Best Omaha/PLO support among all three tools

**Weaknesses:**
- Requires PostgreSQL (installation/maintenance overhead)
- GGPoker: offline analysis only, no live HUD
- UI feels slightly dated compared to HM3
- No population analysis

**Most-praised by users:** LeakTracker, ease of setup, Omaha support, stability, NoteTracker, cross-platform

---

## Features Ranked by User Value

### Tier 1 — Core (users expect these from any tracker)

1. Hand history import with auto-detect + watch folders
2. Comprehensive preflop/postflop stat tracking with positional breakdowns
3. Cumulative graph with EV line
4. Basic filtering (position, stakes, date)
5. Hand browser with search

### Tier 2 — High Value (what serious players use daily)

6. Visual hand replayer (step through actions, keyboard nav)
7. Player lookup with full stat profile
8. Leak finder (compare stats to winning benchmarks)
9. Session tracking (group hands by session, per-session stats/graph)
10. Advanced filtering (board texture, stack depth, hand type, action sequences)
11. Player notes + color tagging
12. Won at Showdown / Won without Showdown graph lines

### Tier 3 — Power User (what differentiates the tools)

13. Population analysis (aggregate opponent data by archetype)
14. Hand range heatmaps / range diagrams
15. Custom stat creation
16. Situational views (C-bet spots, 3-bet spots, steal spots)
17. Decision analysis (EV of specific actions in specific spots)
18. Auto-notes (automated opponent profiling from hand history)
19. Custom report builder

### Tier 4 — Nice to Have

20. Equity / ICM calculators
21. Hand export to video
22. Calendar view
23. Plugin / app marketplace
24. Multi-site parser support (PokerStars, Winamax, 888, etc.)

---

## OHM Competitive Advantages (already)

- **Free & open-source** — H2N Pro is $49/mo, HM3 is $100, PT4 is $50-80
- **No external DB** — DuckDB embedded (HM3 also solved this; PT4 still needs PostgreSQL)
- **Cross-platform via web** — runs on Mac/Windows/Linux without Electron
- **GGPoker Rush & Cash focus** — purpose-built for GG's format and edge cases
- **Streaming import** — real-time NDJSON progress (modern UX pattern)

## OHM Gaps (vs all three competitors)

- No hand browser / hand replayer
- No player lookup / opponent profiling
- No session tracking
- No leak finder
- No population analysis
- No advanced filtering (board texture, stack depth, hand type)
- No player notes / color tagging UI
- No Won at SD / Won w/o SD graph lines
- No watch folder / auto-import
- No custom stats or custom reports
- Single site support (GGPoker only)
