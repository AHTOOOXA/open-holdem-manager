# Poker Tracker PRD

> Open-source alternative to Hand2Note / Holdem Manager
> Focus: Database, Analytics, Learning — not HUD

---

## 0. Current Status

### What's Built (MVP-0: Import → Stats + Graph)

First pass of the core loop exists but needs verification:
- GGPoker Rush & Cash parser (10 unit tests, 13,402 real hands imported without errors)
- Streaming file import (drag & drop files/folders/ZIPs, duplicate detection, progress bar)
- Stats page with positional breakdowns (60+ stat flags)
- Cumulative BB graph with rolling BB/100 + all-in EV line (yellow dashed)
- All-in EV computation using treys library (heads-up, before river, known cards)
- Rake tracking — parser sums all fees (Rake + Jackpot + Bingo + Fortune + Tax); graph shows total rake (BB) and rake/100
- Rebuild stats endpoint — re-parses all hands from stored raw_text without needing original files
- Hero settings (username/site config)
- Performance: player cache, in-memory ID counters, batch transactions, executemany for bulk inserts (~138 hands/sec)

### Next Steps

1. **Verify parsing** — spot-check parsed hands against raw text, confirm edge cases are correct
2. **Verify insertion engine** — confirm data lands in DuckDB correctly (no dropped fields, correct types)
3. **Verify stat calculations** — compare computed stats against known-correct values (e.g. manual count or H2N export)
4. **Stats layout like H2N** — match Hand2Note's stat page layout/grouping more closely

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

### What's NOT Built Yet

From Phase 1: PokerStars parser, hand browser, player lookup, Electron packaging.
From Phase 2+: Population analysis, leak finder, hand tagging, session tracking, all other site parsers.

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

### 3.2 Player Database

**Core Stats Tracked:**

```
Basic:
- VPIP (Voluntarily Put $ In Pot)
- PFR (Pre-Flop Raise)
- 3Bet %
- Fold to 3Bet %
- AF (Aggression Factor)
- AFq (Aggression Frequency)
- WTSD (Went to Showdown)
- W$SD (Won $ at Showdown)

Positional:
- All above stats broken down by position (EP, MP, CO, BTN, SB, BB)

Situational:
- CBet Flop/Turn/River %
- Fold to CBet %
- Check-Raise %
- Donk Bet %
- Probe Bet %
- Float %

```

**Player Identification:**
- By screen name + site
- Merge aliases (same player, different names)
- Notes system (text + color tags)

### 3.3 Reports & Analytics

**My Results:**
- Winrate by stake/position/date range
- Graph: BB/100 over time
- Graph: $ won over time
- Best/worst hands breakdown
- Leak finder: spots with negative EV

**Opponent Lookup:**
- Search by name
- Full stat breakdown
- Hand history with this player
- Player type classification (Fish/Reg/Nit/LAG/TAG)

**Population Analysis:**
- Group players by criteria (VPIP ranges, stake, etc.)
- Pool tendencies by spot
- "How does the average fish play BTN vs 3bet?"
- Compare your stats to population

**Filters (apply to any report):**
- Date range
- Stakes
- Position
- Hand type (pocket pairs, suited connectors, etc.)
- Action sequences (faced 3bet, saw flop, etc.)
- Board texture (dry, wet, paired, etc.)
- Stack depth (short/medium/deep)
- Player count at table

### 3.4 Hand Browser

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

### 3.5 Session Tracking

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
│                 Python Backend                       │
│     (FastAPI, DuckDB, Pydantic, uvicorn)            │
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
- Pages: Upload, Stats, Graph (currently), more planned (Dashboard, Hands, Players, Reports, Settings)
- State: Plain React state (Zustand/React Query can be added when complexity warrants it)
- Charts: Recharts 3
- UI: TailwindCSS v4 with custom dark theme (@theme in CSS)

**Python Backend:**
- FastAPI for REST API
- DuckDB for all data storage
- Parsers: one module per poker site
- Stats engine: calculate all stats from raw hands

**File Structure:**

```
poker-tracker/
├── electron/
│   ├── main.ts                 # Electron main process
│   ├── preload.ts              # Context bridge
│   └── utils/
│       └── backend.ts          # Python process management
├── frontend/
│   ├── src/
│   │   ├── app/                # React app
│   │   ├── components/
│   │   │   ├── ui/             # shadcn components
│   │   │   ├── hands/          # Hand browser components
│   │   │   ├── players/        # Player lookup components
│   │   │   └── reports/        # Charts, tables
│   │   ├── lib/
│   │   │   ├── api/            # Generated API client
│   │   │   └── utils/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app
│   │   ├── api/
│   │   │   ├── hands.py
│   │   │   ├── players.py
│   │   │   ├── reports.py
│   │   │   ├── import.py
│   │   │   └── settings.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── db.py           # DuckDB connection
│   │   │   └── stats.py        # Stat calculations
│   │   ├── parsers/
│   │   │   ├── base.py         # Parser interface
│   │   │   ├── pokerstars.py
│   │   │   ├── ggpoker.py
│   │   │   └── detector.py     # Auto-detect site
│   │   ├── models/
│   │   │   ├── hand.py
│   │   │   ├── player.py
│   │   │   └── action.py
│   │   └── services/
│   │       ├── import_service.py
│   │       ├── stats_service.py
│   │       └── report_service.py
│   ├── tests/
│   ├── pyproject.toml
│   └── requirements.txt
├── shared/
│   └── types/                  # Shared TypeScript types
├── scripts/
│   ├── build-backend.sh        # PyInstaller
│   └── build-all.sh
├── package.json                # Electron + workspace root
├── Makefile
└── README.md
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
# Import
POST   /api/import/folder          # Import from folder path
POST   /api/import/files           # Import specific files
GET    /api/import/status/{job_id} # Check import progress
POST   /api/import/rebuild         # Re-parse all hands from stored raw_text
POST   /api/import/watch           # Start watching folder

# Hands
GET    /api/hands                  # List hands (paginated, filtered)
GET    /api/hands/{id}             # Get hand detail
PATCH  /api/hands/{id}/note        # Update hand note
POST   /api/hands/{id}/tags        # Add tag
DELETE /api/hands/{id}/tags/{tag}  # Remove tag

# Players
GET    /api/players                # List/search players
GET    /api/players/{id}           # Get player detail + stats
GET    /api/players/{id}/hands     # Get hands with player
PATCH  /api/players/{id}/note      # Update player note
PATCH  /api/players/{id}/color     # Update color tag
POST   /api/players/merge          # Merge two player profiles

# Reports
GET    /api/reports/my-results     # My winrate, graphs
GET    /api/reports/leaks          # Leak finder
GET    /api/reports/population     # Population analysis
GET    /api/reports/positional     # Stats by position

# Stats (raw stat queries)
GET    /api/stats/player/{id}      # Full stats for player
GET    /api/stats/population       # Pool stats with filters

# Settings
GET    /api/settings               # Get all settings
PATCH  /api/settings               # Update settings
GET    /api/settings/hh-paths      # Get HH folder paths
POST   /api/settings/hh-paths      # Add HH folder path

# System
GET    /api/health                 # Health check
GET    /api/db/stats               # DB size, hand count, etc.
POST   /api/db/vacuum              # Optimize database
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
- Import: 5,000+ hands/second
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

## 7. MVP Scope

### Phase 1: Foundation (MVP)
- [~] GGPoker parser — first pass done, needs verification against real hands
- [~] Hand import — streaming/ZIP/folder works, insertion correctness needs verification
- [~] Player stats — 60+ flags computed, calculations need verification against H2N
- [~] Stats page — works, layout needs rework to match H2N
- [x] Graph — cumulative BB + rolling BB/100 + all-in EV line + rake tracking
- [x] Hero settings (username/site config)
- [ ] PokerStars parser
- [ ] Hand browser with filters
- [ ] Player lookup
- [ ] Electron packaging for Win/Mac/Linux

### Phase 2: Analytics
- [ ] Population analysis
- [ ] Leak finder
- [ ] Advanced filters (board texture, stack depth)
- [ ] Hand tagging & notes
- [ ] Session tracking

### Phase 3: Polish
- [ ] Auto-import (watch folders)
- [ ] More site parsers (Winamax, 888, Party)
- [ ] Hand replayer (visual)
- [ ] Player type auto-classification
- [ ] Export features (CSV, share hands)

### Phase 4: Advanced (Future)
- [ ] HUD overlay (separate app/process)
- [ ] Tournament support
- [ ] Web version (upload HH, analyze online)
- [ ] Mobile companion (view stats)

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

| Feature | Hand2Note | HM3 | This Project (MVP) |
|---------|-----------|-----|-------------------|
| HUD | ✅ Advanced | ✅ Good | ❌ Not in MVP |
| Hand Import | ✅ | ✅ | ✅ |
| Player Stats | ✅ | ✅ | ✅ |
| Reports | ✅ | ✅ | ✅ Basic |
| Population Analysis | ✅ (paid) | ❌ | ✅ |
| Leak Finder | ✅ | ✅ | ✅ |
| Hand Replayer | ✅ | ✅ | ⚠️ Text only |
| Price | $15-39/mo | $100 once | Free |
| Open Source | ❌ | ❌ | ✅ |
