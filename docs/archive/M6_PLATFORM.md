# Milestone 6: "The App That Just Works"

> **Goal**: Platform maturity — auto-import, additional poker sites, packaging, visual replayer.
> **Coaching parallel**: Infrastructure that makes daily use frictionless.
> **Priority**: Medium. Adoption and reach features. Can be interleaved with other milestones.

---

## 1. Research

### Why Platform Features Matter

The biggest barrier to poker tracking adoption isn't features — it's friction. Players who have to manually drag-and-drop files every session will stop using the tool within weeks. The tools with the highest daily-active-user retention all share one feature: **auto-import**.

**Auto-import patterns across competitors**:
- **HoldemManager 3**: Watches configured folders, auto-imports new .txt files as they appear. Runs as a background process. The single most important UX feature for daily engagement.
- **PokerTracker 4**: Same pattern — "Auto-Import Folders" configured in settings. Monitors multiple directories for multiple sites.
- **Hand2Note**: Auto-detects common HH locations per site (e.g., GGPoker saves to `AppData/Local/GGPoker/...`). Zero-config for most users.

**Site parser priorities from community demand**:
1. **PokerStars** — largest player base globally, most hand history samples available, most requested parser in every open-source tracker
2. **Winamax** — dominant in France, growing in Europe
3. **888poker** — common in UK-regulated markets
4. **PartyPoker** — WPT network, solid player base

**Visual hand replayer value**:
- Every competitor has a graphical hand replayer (table view with chip stacks, pot, cards)
- Coaches use replayers in every hand review session
- Current OHM shows raw text + action list — functional but not visually engaging
- A replayer makes hand review sessions more intuitive and shareable
- Shareable hand replays (images/links) are essential for study groups and coaching Discord channels

**Variance calculator value**:
- Players constantly ask "is this downswing normal?"
- Monte Carlo simulation answers this definitively with probability distributions
- Helps players maintain mental equilibrium during natural variance
- Pure frontend math — no backend needed, quick to implement
- Every serious poker training resource recommends understanding variance

---

## 2. Product Design

### M6.1 — Auto-Import (Watch Folders)

**User story**: "As a daily player, I want my hand histories to be imported automatically when I finish a session, so I don't have to manually upload files every time."

**Requirements**:
- Configure one or more directories to watch for new .txt files
- Polling interval: check every 30 seconds (configurable)
- Auto-detect GGPoker's default HH location on the current OS
- Process new files: parse, import, skip duplicates (same as manual import)
- Background task — doesn't block the UI
- Status indicator in the sidebar: "Auto-import: watching 2 folders" with last import time
- Import log: show what was auto-imported and when
- Error handling: if a file fails to parse, log the error, don't stop watching
- File tracking: remember which files have been processed (don't re-scan entire directory on restart)

**Auto-detect locations**:
- GGPoker (Windows): `%LOCALAPPDATA%\GGPoker\data\hand_history\`
- GGPoker (macOS): `~/Library/Application Support/GGPoker/data/hand_history/`
- PokerStars (Windows): `%LOCALAPPDATA%\PokerStars\HandHistory\{username}\`
- PokerStars (macOS): `~/Library/Application Support/PokerStars/HandHistory/{username}/`

**Settings UI**:
```
Auto-Import Settings
────────────────────
☑ Enable auto-import

Watch Folders:
  📁 /Users/anton/GGPoker/hand_history/     [Remove]
  📁 /Users/anton/PokerStars/HandHistory/   [Remove]
  [+ Add Folder]   [Auto-Detect]

Scan interval: [30 seconds ▾]
Import on startup: ☑
```

### M6.2 — Additional Site Parsers

**User story**: "As a PokerStars player, I want to import my PokerStars hand histories so I can track my game on that site too."

**Architecture**: The existing parse → compute → insert pipeline is already site-independent. Each new parser only needs to produce a `ParsedHand` dataclass. `stat_flags.py` and `insert_parsed_hand()` handle everything else.

**Parser priority and effort**:

| Site | Priority | Format Complexity | Estimated Effort | Notes |
|------|----------|------------------|------------------|-------|
| PokerStars | P0 | Medium | 3-5 days | Largest site, well-documented format, many reference parsers |
| Winamax | P1 | Medium | 3-5 days | French format, some unicode edge cases |
| 888poker | P1 | Medium-High | 4-6 days | Multiple format versions, tournament/cash differences |
| PartyPoker | P2 | Medium | 3-5 days | WPT network format |

**Parser development checklist** (per site):
1. Collect 500+ sample hands covering all edge cases
2. Document the format (header, seats, actions, summary patterns)
3. Build parser producing `ParsedHand`
4. Write 10+ unit tests covering: regular hand, split pot, all-in, showdown variants, disconnection, run-it-twice (if applicable)
5. Import real hands and cross-validate stats against the site's built-in stats
6. Add site to `sites` table and auto-detect logic

**PokerStars format overview** (most requested):
```
PokerStars Hand #234567890123: Hold'em No Limit ($0.50/$1.00 USD) - 2025/01/30 12:34:56 ET
Table 'Acamar III' 6-max Seat #3 is the button
Seat 1: Player1 ($100 in chips)
Seat 2: Player2 ($85.50 in chips)
Seat 3: Hero ($120 in chips)
...
*** HOLE CARDS ***
Dealt to Hero [Ah Ks]
Player1: folds
Player2: raises $2.50 to $3.50
Hero: raises $8 to $11.50
...
*** FLOP *** [Qh 7d 2c]
...
*** SUMMARY ***
Total pot $25.50 | Rake $1.10
...
```

Key differences from GGPoker format:
- Hand ID is numeric (not `RC...`)
- Currency in header (`USD`, `EUR`)
- `Dealt to Hero [cards]` instead of seat-based card assignment
- No jackpot/BBJ fee (PokerStars doesn't have this)
- Different timezone handling (ET vs. UTC)
- No time bank card rewards
- Ante format differences in some games

### M6.3 — Electron Packaging

**User story**: "As a non-technical user, I want to download and install OHM like a normal desktop app, without having to run terminal commands."

**Requirements**:
- Single installer for Windows (.exe), macOS (.dmg), Linux (.AppImage)
- Bundles Python backend + Node frontend + DuckDB database
- Auto-starts backend on app launch
- Tray icon with quick actions (open app, check import status)
- Auto-update mechanism
- Data stored in user's app data directory (not project directory)

**Architecture decisions**:
- **Electron** wraps the React frontend as a desktop window
- **Python backend** runs as a subprocess managed by Electron's main process
- **DuckDB** file stored in OS-appropriate location:
  - Windows: `%APPDATA%/OHM/data/poker.duckdb`
  - macOS: `~/Library/Application Support/OHM/data/poker.duckdb`
  - Linux: `~/.local/share/OHM/data/poker.duckdb`
- **PyInstaller** or **cx_Freeze** to bundle Python + dependencies into a standalone executable
- Frontend served from local files (no dev server in production)

**Build pipeline**:
1. Build frontend: `npm run build` → static files in `dist/`
2. Bundle backend: PyInstaller → single executable
3. Package with electron-builder → platform-specific installers
4. CI/CD: GitHub Actions for all 3 platforms

**Effort**: Medium-Large. The bundling complexity is the main challenge — Python + Node + native DuckDB bindings across platforms.

### M6.4 — Visual Hand Replayer

**User story**: "As a player reviewing a hand, I want to see a visual poker table with chip stacks, pot size, cards, and actions animated step-by-step, instead of reading raw text."

**Requirements**:
- Poker table visualization (oval table with 2-9 seats)
- Player boxes: name, stack size, cards (if known), action taken
- Community cards displayed in center
- Pot size shown and updated per action
- Street-by-street progression: click to advance through preflop → flop → turn → river
- Play/pause, step forward/back buttons
- Speed slider (0.5x, 1x, 2x, 3x)
- BB/$ display toggle
- Hero seat highlighted
- Winning player(s) highlighted at showdown
- Current action highlighted with bet amount

**Technology options**:
1. **SVG-based** (React components): Easier to style with Tailwind, good for static/stepped views, simpler to implement
2. **Canvas-based** (HTML5 Canvas): Better for smooth animations, more complex
3. **CSS-only** (divs + positioning): Simplest, works for basic table layout, no animation library needed

**Recommendation**: SVG-based for the table layout + CSS transitions for action animations. Balances visual quality with implementation complexity.

**Component structure**:
```
HandReplayer.tsx
├── PokerTable.tsx          (oval table SVG with seat positions)
├── PlayerSeat.tsx          (name, stack, cards, action, dealer button)
├── CommunityCards.tsx      (flop, turn, river cards in center)
├── PotDisplay.tsx          (current pot size)
├── ActionOverlay.tsx       (bet/raise amounts appearing near player)
├── ReplayerControls.tsx    (play/pause, step, speed, display toggle)
└── StreetIndicator.tsx     (preflop/flop/turn/river progress bar)
```

**Integration**: Replace or augment the current text-based hand detail in the HandDrawer component. Users can toggle between "Text View" and "Visual Replay" mode.

### M6.5 — Variance Calculator

**User story**: "As a player on a 15 buy-in downswing, I want to know whether this is normal variance or whether something is wrong with my game."

**Requirements**:
- Input: winrate (bb/100), standard deviation (bb/100, or auto-calculate from DB), sample size (hands)
- Output: Monte Carlo simulation of 10,000 sample paths
- Visualizations:
  - Spaghetti plot: 50-100 sample paths overlaid to show variance range
  - Confidence bands: 5th/25th/50th/75th/95th percentile bands
  - Downswing probability: "Probability of a 10+ buy-in downswing over 50k hands: 32%"
  - Expected downswing duration: "Median longest downswing: 8,200 hands"
  - Bankroll requirement: "For a 95% chance of not going broke, you need 28 buy-ins"
- Auto-fill from hero's actual stats when available (winrate + stddev from DB)
- Preset stake levels to auto-calculate $ amounts
- Pure frontend computation — no backend needed

**Implementation**: Web Worker for Monte Carlo simulation (don't block UI). Standard normal distribution sampling. Cumulative sum for each path.

```typescript
function simulatePaths(
  winrateBbPer100: number,
  stddevBbPer100: number,
  handsToSimulate: number,
  numPaths: number = 10000,
  stepSize: number = 100  // compute cumulative every 100 hands
): SimulationResult {
  const paths: number[][] = [];
  for (let p = 0; p < numPaths; p++) {
    const path: number[] = [0];
    let cumulative = 0;
    for (let h = 0; h < handsToSimulate; h += stepSize) {
      // Each step: mean = winrate * (stepSize/100), stddev = stddev * sqrt(stepSize/100)
      const mean = winrateBbPer100 * (stepSize / 100);
      const std = stddevBbPer100 * Math.sqrt(stepSize / 100);
      cumulative += normalRandom(mean, std);
      path.push(cumulative);
    }
    paths.push(path);
  }
  return computeStatistics(paths);
}
```

---

## 3. UI/UX Design

### M6.1 — Auto-Import Status

Sidebar indicator:
```
♠ OHM
  Upload
  Stats
  ...
  ─────────────
  📂 Auto-import: Active
     Last: 2 min ago · 312 hands
```

### M6.4 — Visual Hand Replayer

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                    ┌─────────────────────┐                       │
│                    │     Pot: 12.5 BB     │                      │
│                    └─────────────────────┘                       │
│                                                                  │
│        ┌──────────┐              ┌──────────┐                   │
│        │ Player3  │              │ Player4  │                    │
│        │ 98.5 BB  │              │ 102.0 BB │                    │
│        │ [??][??] │              │ [??][??] │                    │
│        │ calls 3  │              │          │                    │
│        └──────────┘              └──────────┘                    │
│                                                                  │
│   ┌──────────┐    [Qh] [7d] [2c]     ┌──────────┐              │
│   │ Player2  │                        │ Player5  │              │
│   │ 85.0 BB  │                        │ 110.0 BB │              │
│   │ [??][??] │                        │ [??][??] │              │
│   │ folds    │                        │          │              │
│   └──────────┘                        └──────────┘              │
│                                                                  │
│        ┌──────────┐              ┌──────────┐                   │
│        │ Player1  │              │ ★ Hero   │                   │
│        │ 100.0 BB │              │ 120.0 BB │                   │
│        │ [??][??] │              │ [Ah][Ks] │                   │
│        │          │              │ raises 11│                   │
│        └──────────┘    [D]       └──────────┘                   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  ◁◁  ◁  ▐▐  ▷  ▷▷     Preflop ● ● ○ ○     Speed: [1x ▾]      │
│                         Flop   Turn River                        │
│  [Text View]  [BB ▾]                                            │
└──────────────────────────────────────────────────────────────────┘
```

### M6.5 — Variance Calculator

```
┌──────────────────────────────────────────────────────────────────┐
│  VARIANCE CALCULATOR                                              │
│                                                                  │
│  Win Rate:  [3.5] bb/100    Std Dev: [75] bb/100                │
│  Hands:     [50,000]        [Auto-fill from my stats]            │
│  Stakes:    [$0.25/$0.50 ▾]                                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    ╱╲                                      │  │
│  │              ╱╲  ╱╱  ╲╲                                   │  │
│  │         ╱╲╱╱╱  ╲╱      ╲╲╱╲                              │  │
│  │    ╱╲╱╱╱                   ╲╲                             │  │
│  │  ╱╱░░░░░░░░░░░░░░░░░░░░░░░░░░╲╲                         │  │
│  │ ╱░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░╲╲╱╲                     │  │
│  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░╲──── 95th: +42 BI   │  │
│  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓──── median: +17 BI │  │
│  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░──── 5th: -8 BI      │  │
│  │  0        10k       20k       30k      40k      50k      │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  At 50,000 hands with 3.5 bb/100:                               │
│  • 95% chance of being profitable                                │
│  • 32% chance of a 10+ buy-in downswing                         │
│  • Median longest downswing: 8,200 hands                        │
│  • Recommended bankroll: 28 buy-ins ($1,400 at NL50)            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Technical Spec

### M6.1 — Auto-Import Backend

**Technology**: Python `watchdog` library for filesystem monitoring.

**New endpoint**: `POST /api/import/watch`

```json
{
  "folders": ["/Users/anton/GGPoker/hand_history/"],
  "interval_seconds": 30,
  "enabled": true
}
```

**New endpoint**: `GET /api/import/watch/status`

```json
{
  "enabled": true,
  "folders": [
    { "path": "/Users/anton/GGPoker/hand_history/", "exists": true, "last_scan": "2026-02-08T20:30:00" }
  ],
  "last_import": { "at": "2026-02-08T20:28:00", "hands_imported": 312, "files_processed": 3 },
  "total_files_tracked": 142
}
```

**File tracking**: Store processed file hashes in a `watched_files` table:

```sql
CREATE TABLE watched_files (
    file_path VARCHAR PRIMARY KEY,
    file_hash VARCHAR NOT NULL,    -- MD5 or SHA256 of file content
    processed_at TIMESTAMP NOT NULL,
    hands_imported INTEGER
);
```

On each scan:
1. List .txt files in watched directories
2. For each file: compute hash, check if already in `watched_files`
3. If new: import file (same as manual import flow), record in `watched_files`
4. If hash changed (file was appended to): re-import (skip duplicate hand IDs)

**Background task**: Use `asyncio` task or `threading.Timer` for periodic scanning. Start on backend startup if enabled in settings.

### M6.2 — Parser Architecture

Each parser module exports:

```python
# backend/app/parsers/{site}.py

def parse_hand_history(raw_text: str) -> list[ParsedHand]:
    """Parse a full hand history file into individual hands."""
    ...

def detect_site(raw_text: str) -> bool:
    """Returns True if this parser can handle this file format."""
    ...
```

**Auto-detection**: When importing a file, try each parser's `detect_site()`:
```python
PARSERS = [ggpoker, pokerstars, winamax, eighteighteight, partypoker]

def parse_file(raw_text: str) -> list[ParsedHand]:
    for parser in PARSERS:
        if parser.detect_site(raw_text):
            return parser.parse_hand_history(raw_text)
    raise ValueError("Unknown hand history format")
```

### M6.4 — Replayer Data

The hand detail endpoint (`GET /api/hands/{id}`) already returns all data needed for the replayer:
- Players with seats, stacks, positions, hole cards
- Actions per street with amounts
- Board cards per street
- Results (who won, how much)

No new backend endpoint needed. Frontend transforms existing data into replayer state.

### M6.5 — Variance Calculator

Pure frontend. No backend needed.

**Dependencies**: None. Can be built anytime as a standalone page.

**Web Worker** for Monte Carlo simulation:

```typescript
// variance-worker.ts
self.onmessage = (e: MessageEvent<SimulationParams>) => {
  const { winrate, stddev, hands, paths } = e.data;
  const result = runSimulation(winrate, stddev, hands, paths);
  self.postMessage(result);
};
```

---

## 5. Execution Plan

### Task Breakdown

**M6.1 — Auto-Import (5-7 days)**:
1. Add `watchdog` to requirements.txt
2. Create `watched_files` table in schema
3. Implement file scanning + hash tracking logic
4. Implement background task (periodic scanning)
5. Add settings endpoints for watch folder configuration
6. Add auto-detect logic for common HH locations
7. Create settings UI for watch folder management
8. Add sidebar status indicator
9. Test: file creation, file update, duplicate handling, error recovery

**M6.2 — PokerStars Parser (5-7 days)**:
1. Collect 500+ sample hands (community sources, own play)
2. Document format differences from GGPoker
3. Build header/seat/action parsers
4. Handle PokerStars-specific edge cases (bounty tournaments ignored, cash only)
5. Write 10+ unit tests
6. Cross-validate stats against PokerStars built-in stats
7. Add auto-detection logic
8. Add to sites table

**M6.3 — Electron Packaging (7-10 days)**:
1. Set up Electron project wrapping frontend
2. Configure PyInstaller to bundle backend
3. Implement subprocess management (start/stop backend from Electron)
4. Configure data directory (OS-appropriate paths)
5. Build for macOS (DMG)
6. Build for Windows (NSIS installer)
7. Build for Linux (AppImage)
8. Set up GitHub Actions CI for all platforms
9. Test installation, startup, data persistence on all platforms

**M6.4 — Visual Hand Replayer (7-10 days)**:
1. Create PokerTable SVG component (oval table, seat positions)
2. Create PlayerSeat component (name, stack, cards, action)
3. Create CommunityCards component
4. Create PotDisplay component
5. Implement step-through logic (preflop → flop → turn → river, action by action)
6. Implement play/pause with speed control
7. Create ReplayerControls component
8. Integrate into HandDrawer (toggle between text and visual mode)
9. Test with various hand types (HU, 6-max, split pot, RIT)

**M6.5 — Variance Calculator (3-4 days)**:
1. Implement Monte Carlo simulation in Web Worker
2. Create VarianceCalculatorPage with input form
3. Create spaghetti plot / confidence band chart
4. Compute and display statistics (downswing probability, bankroll requirement)
5. Add auto-fill from hero's actual stats
6. Add to sidebar navigation

### Interleaving with Other Milestones

M6 features are mostly independent and can be built alongside other milestones:

| Feature | Can Build After | Good Time to Build |
|---------|----------------|-------------------|
| Auto-Import | Anytime | Sprint 4-5 (quality of life while using the app daily) |
| PokerStars Parser | Anytime | Sprint 6-7 (after stat flags are stabilized) |
| Electron | After all features are stable | Sprint 11+ (final packaging step) |
| Visual Replayer | After hand detail exists | Sprint 8-9 (enhances hand review in M2) |
| Variance Calculator | Anytime | Sprint 5-6 (quick win, standalone page) |

---

## 6. Testing

### M6.1 — Auto-Import

**Unit tests**:
- File hash computation is deterministic
- New files are detected and imported
- Already-processed files are skipped
- Modified files are re-imported (new hands only, duplicates skipped)
- Error in one file doesn't stop processing of other files

**Integration tests**:
- Watch folder detects new file creation in real time
- Settings persist across restart
- Status endpoint shows correct last-import info
- Auto-detect finds GGPoker HH directory on the current OS

### M6.2 — PokerStars Parser

**Unit tests** (minimum 10):
- Regular hand parsing (header, seats, positions, actions, summary)
- Showdown with multiple players
- All-in before river
- Split pot
- Hand with antes
- Different stake formats ($, EUR)
- Hand with disconnection/timeout messages
- Heads-up hand
- Multi-way pot
- BB defense (checking option)

**Cross-validation**:
- Import 1000+ real PokerStars hands
- Compare VPIP, PFR, 3-Bet, C-Bet against PokerStars built-in statistics
- All should match within 0.5%

### M6.4 — Visual Replayer

**Visual QA**:
- 2-player through 9-player tables render correctly
- Cards display with correct suits and ranks
- Pot updates correctly at each action
- Dealer button is on the correct seat
- Hero seat is visually highlighted
- Step-through advances one action at a time
- All action types render: fold, check, call, bet, raise, all-in
- Split pot shows both winners
- Run-it-twice shows both boards

### M6.5 — Variance Calculator

**Unit tests**:
- Monte Carlo simulation produces results within expected statistical bounds
- Mean of 10,000 paths is within 5% of expected winrate × hands
- Standard deviation of paths matches theoretical expectation
- Downswing calculation correctly identifies max drawdown per path

### Acceptance Criteria

- [ ] Auto-import watches configured folders and imports new files automatically
- [ ] Auto-import detects GGPoker's default HH location
- [ ] Auto-import status is visible in the sidebar
- [ ] PokerStars parser correctly imports hands and produces stats matching PokerStars built-in stats
- [ ] Site auto-detection correctly identifies GGPoker vs. PokerStars files
- [ ] Electron app installs and runs on macOS, Windows, and Linux
- [ ] Electron app bundles Python backend and starts it automatically
- [ ] Visual replayer shows a poker table with correct player positions, cards, and actions
- [ ] Replayer supports step-through, play/pause, and speed control
- [ ] Variance calculator simulates 10,000 paths and shows confidence bands
- [ ] Variance calculator auto-fills from hero's actual database stats
