# Open Holdem Manager (OHM) — Project Handoff

## What This Is

A local poker hand history tracker (like Hand2Note / HoldemManager) for GGPoker Rush & Cash. Parses hand history .txt files, stores in DuckDB, computes H2N-style stats, shows graphs.

## Tech Stack

- **Backend**: Python 3.12+, FastAPI >=0.115, DuckDB >=1.1, Pydantic >=2.0, python-multipart
- **Frontend**: React 19, TypeScript 5.9, Vite 7, TailwindCSS v4 (@theme syntax), shadcn/ui (Radix), Recharts 3, React Router 7
- **Desktop**: Electron 33, electron-builder 25, electron-updater (auto-updates via GitHub Releases)
- **DB**: DuckDB file-based — `data/poker.duckdb` in dev, `~/Library/Application Support/open-holdem-manager/data/` (macOS) or `%APPDATA%/open-holdem-manager/data/` (Windows) in packaged mode
- **No auth, no cloud** — fully local, single-user

## Running

```bash
make setup        # install deps: pip install -r requirements.txt && npm install
make dev          # starts backend (port 8000) + frontend (port 5173)
make backend      # backend only
make frontend     # frontend only
```

Backend: `cd backend && uvicorn app.main:app --reload --port 8000`
Frontend: `cd frontend && npm run dev`
Electron dev: `make electron-dev` (starts backend + frontend + Electron window)
Electron build: `make electron-build` (builds .dmg/.exe via PyInstaller + electron-builder)
Tests: `cd backend && python -m pytest tests/test_parser.py -v`
Lint: `cd frontend && npm run lint`
API docs: http://localhost:8000/docs (FastAPI auto-generated Swagger)

## Frontend Config

- Vite proxies `/api` requests to `http://localhost:8000` (see `frontend/vite.config.ts`)
- Path alias: `@/` maps to `./src/` (configured in `tsconfig.app.json`)
- Dark theme defined via Tailwind `@theme` in `frontend/src/index.css` — custom CSS vars: `--color-background`, `--color-surface`, `--color-primary` (indigo #6366f1), `--color-green`, `--color-red`, etc.

## shadcn/ui

This project uses [shadcn/ui](https://ui.shadcn.com/) (Radix primitives + Tailwind styling). Components live in `frontend/src/components/ui/`.

- **Install new components**: `cd frontend && npx shadcn@latest add <component>`
- **Always prefer shadcn** over raw HTML inputs, custom dropdowns, or hand-rolled UI. If a shadcn component exists for the pattern, use it.
- Installed components: Button, Card, Input, Textarea, Select, Popover, Checkbox, RadioGroup, Toggle, ToggleGroup, Calendar, DatePicker (custom wrapper), Table, Sheet, Badge, Separator, Tooltip, Skeleton, Progress, Alert, DropdownMenu, Dialog, Sidebar
- Shared cross-page components: `FilterBar` (stakes/date filters), `EmptyState` (no-data/no-match variants with import CTA), `DatePicker` (Popover + Calendar)

## Project Structure

```
backend/
  app/
    main.py                 # FastAPI app, CORS (dev only), startup, health, static file serving (packaged)
    db.py                   # DuckDB connection, schema init, sequence sync, STAT_VERSION auto-rebuild
    models.py               # Pydantic response models
    stats_engine.py         # Computes H2N-style stats from hand_players table
    stat_flags.py           # Site-independent stat flag computation (VPIP, PFR, 3-bet, cbet, etc.)
    parsers/
      ggpoker.py            # GGPoker hand history parser — text → ParsedHand dataclass
    api/
      import_hands.py       # Import endpoints + insert_parsed_hand() DB insertion + player cache
      stats.py              # GET /api/stats/hero?position=&stakes=&date_from=&date_to=
      reports.py            # GET /api/reports/graph, /filter-options, /breakdown
      hands.py              # Hand browser: GET /api/hands, /hands/{id}, tags, notes
      settings.py           # GET/PATCH /api/settings
  run_server.py             # PyInstaller entry point for bundled backend
  tests/
    test_parser.py          # 11 tests across 5 classes
    fixtures/
      ggpoker_sample.txt          # 5 baseline hands
      time_bank_card.txt           # Time bank edge case
      split_pot.txt                # Split pot edge case
      run_it_twice.txt             # RIT, different winners
      run_it_twice_same_winner.txt # RIT, same winner both boards
  requirements.txt          # fastapi, uvicorn, duckdb, pydantic, python-multipart

frontend/
  src/
    index.css               # Tailwind v4 @theme with custom dark color palette
    main.tsx                # React entry point (StrictMode)
    globals.d.ts            # Declares __APP_VERSION__ global (injected by Vite from root package.json)
    App.tsx                 # Router: Upload / Stats / Results / Hands tabs
    lib/api.ts              # Typed API client (fetch wrapper, NDJSON streaming)
    components/
      RebuildBanner.tsx     # Sticky footer showing background stat rebuild progress
      UpdateBanner.tsx      # Sticky footer for auto-update download/install (Electron only)
    pages/
      UploadPage.tsx        # Drag & drop files/folders/ZIPs, progress bar, clear DB
      StatsPage.tsx         # H2N-style stat table with positional columns
      GraphPage.tsx         # Results dashboard: graph (BB/$, EV, SD/NSD, rake lines), stat cards, breakdowns by stakes/month/position
      HandsPage.tsx         # Hand browser: paginated list, filters (position/stakes/result/tags/date), detail drawer, tagging, notes
  vite.config.ts            # React plugin, Tailwind v4 plugin, API proxy to :8000, ELECTRON=1 base path
  tsconfig.app.json         # Strict mode, ES2022, path alias @/*

electron/
  main.js                   # Main process — spawns backend, finds free port, opens window, auto-updater
  preload.js                # Preload — exposes platform, version, auto-update IPC to renderer

package.json                # Root — Electron 33, electron-builder 25, electron-updater, build scripts
electron-builder.yml        # Packages .dmg (macOS), .exe/NSIS (Windows), .AppImage (Linux)
release-workflow.yml        # GitHub Actions: builds on v* tags, publishes to GitHub Releases
.github/workflows/release.yml  # Active copy of release-workflow.yml
```

## Database Schema (DuckDB)

Key tables in `backend/app/db.py`:

- **sites** — poker sites (hardcoded: id=1, name='GGPoker', code='GG')
- **hands** — one row per hand (id=hand_id string like "RC1234567890", played_at, stakes, bb_amount, raw_text)
- **players** — unique players (site_id, username, notes, color_tag, first_seen, last_seen)
- **hand_players** — one row per player per hand. Contains ALL stat flags:
  - `won`, `won_bb`, `rake`, `rake_bb`, `jackpot`, `jackpot_bb` — net results + BBJ
  - `all_in_ev_bb` — all-in expected value
  - `vpip`, `pfr`, `three_bet`, `three_bet_opp`, `four_bet`, `four_bet_opp` — preflop
  - `fold_to_3bet`, `fold_to_4bet`, `open_raise`, `open_raise_opp`, `call_open_raise`, `limp`, `squeeze`, `squeeze_opp`, `five_bet`, `five_bet_opp`
  - `steal_attempted`, `steal_opp`, `faced_steal`, `fold_to_steal`, `call_steal`, `three_bet_vs_steal`
  - `saw_flop/turn/river`, `went_to_showdown`, `won_at_showdown`
  - `cbet_flop/turn/river`, `cbet_flop/turn/river_opp`, `fold_to_cbet_flop/turn/river`
  - `missed_cbet_flop/turn`, `donk_bet_flop/turn/river`, `donk_bet_flop/turn/river_opp`
  - `flop/turn/river_bets/raises/calls/checks/folds` — aggression counts
- **actions** — every action (street, action_type, amount, amount_bb, is_all_in)
- **board_cards** — community cards per street per hand
- **hand_tags** — hand tagging (hand_id, tag, created_at)
- **hand_notes** — per-hand notes (hand_id, note, updated_at)
- **settings** — key/value (hero_username, hero_site, stat_version)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Returns `{status, hands, rebuilding, rebuild_progress?}` |
| POST | `/api/import/files` | Synchronous multipart upload (50MB limit) |
| POST | `/api/import/files/stream` | Streaming upload, returns NDJSON (`start`/`progress`/`done`) |
| POST | `/api/import/clear` | Truncate all hand data |
| POST | `/api/import/rebuild` | Re-parse all hands from stored raw_text |
| GET | `/api/stats/hero` | Hero stats. Optional filters: `position`, `stakes`, `date_from`, `date_to` |
| GET | `/api/reports/graph` | Graph data: cumulative BB/$, EV, SD/NSD, rake, jackpot lines |
| GET | `/api/reports/filter-options` | Available stakes and date ranges for filters |
| GET | `/api/reports/breakdown` | Results breakdown by stakes, month, position |
| GET | `/api/hands` | List hands (paginated, filtered by position/stakes/result/tags/date) |
| GET | `/api/hands/{id}` | Hand detail (all players, actions, board, raw text) |
| POST | `/api/hands/{id}/tags` | Add tag to hand |
| DELETE | `/api/hands/{id}/tags/{tag}` | Remove tag from hand |
| GET | `/api/tags` | List all tags with counts |
| PUT | `/api/hands/{id}/note` | Update hand note |
| DELETE | `/api/hands/{id}/note` | Delete hand note |
| GET | `/api/settings` | Get settings (hero_username, hero_site) |
| PATCH | `/api/settings` | Update settings |

## Architecture: Parse → Compute → Insert Pipeline

The backend uses a three-step pipeline for hand import:

1. **Parse** (`parsers/ggpoker.py`): `parse_hand_history(text) → ParsedHand` — pure text parsing, no DB access
2. **Compute** (`stat_flags.py`): `compute_stat_flags(parsed) → dict[str, dict]` — site-independent stat flag derivation
3. **Insert** (`api/import_hands.py`): `insert_parsed_hand(db, parsed) → hand_id` — calls compute, calculates financials, writes to DB

This separation means:
- New site parsers only need to produce a `ParsedHand` dataclass — stat logic is reused
- Parser is testable without a DB (assert on the returned dataclass)
- Stat flag bugs can be fixed and re-derived via `/import/rebuild` without re-parsing

## GGPoker Parser (`backend/app/parsers/ggpoker.py`)

### Output: `ParsedHand` dataclass

The parser returns a `ParsedHand` containing all extracted data: hand metadata, seats with positions, actions per street, board cards, hole cards, collected amounts, rake, showdown info. Does NOT compute stat flags or touch the DB.

### How It Works

1. Strips null bytes, BOM, zero-width chars (`\x00`, `\ufeff`, `\u200b`, `\u200c`, `\u200d`)
2. Parses header line (hand ID, stakes, timestamp) via regex
3. Parses table info (table name, size, button seat)
4. Parses seat lines (player names, stacks)
5. Assigns positions via `POSITIONS_BY_COUNT` lookup — supports 2-9 max tables, clockwise from button
6. Line-by-line state machine: `preflop` → `flop` → `turn` → `river`, with `in_showdown` and `in_summary` flags
7. `_should_skip()` filters noise lines: disconnected, timed out, joins table, sits out, etc. (12+ patterns)
8. Tracks all voluntary actions, blinds, antes per street
9. In summary: extracts `won`/`collected` amounts via `re.finditer` (handles multiple amounts on one line for RIT)
10. Returns `ParsedHand` dataclass with all extracted data

## Stat Flag Computation (`backend/app/stat_flags.py`)

`compute_stat_flags(parsed: ParsedHand) → dict[str, dict]` — takes parsed hand data, returns per-player stat flags.

Site-independent logic that derives 40+ boolean flags from action sequences:
- **Preflop**: VPIP, PFR, open raise (+ opportunity), 3-bet/4-bet/5-bet, fold-to-3bet/4bet, squeeze, limp, steal detection
- **Postflop**: cbet (opportunity + attempt per street), fold-to-cbet, donk bet, missed cbet, aggression counts
- **Showdown**: saw_flop/turn/river, went_to_showdown, won_at_showdown

### GGPoker Hand History Format

Key markers the parser expects:
- Header: `Poker Hand #RC...: Hold'em No Limit ($SB/$BB) - YYYY/MM/DD HH:MM:SS`
- Table: `Table 'name' N-max Seat #X is the button`
- Seats: `Seat N: player ($X.XX in chips)`
- Streets: `*** HOLE CARDS ***`, `*** FLOP ***`, `*** TURN ***`, `*** RIVER ***`, `*** SHOWDOWN ***`, `*** SUMMARY ***`
- RIT variants: `*** FIRST FLOP ***`, `*** SECOND FLOP ***`, etc.
- Actions: `player: folds | checks | calls $X | bets $X | raises $X to $Y [and is all-in]`
- Summary: `Total pot $X | Rake $Y | ...` then `Seat N: player ... won ($X) ...`

See `backend/tests/fixtures/` for real examples of each format variant.

### Edge Cases Already Handled

- **Run It Twice**: `*** FIRST FLOP ***`, `*** SECOND FLOP ***`, etc. First board is canonical. Summary line has multiple `won ($X)` on same line (same winner both boards) or separate lines (different winners).
- **Time bank cards**: `received ($0.02) from time bank card and won ($X)` in summary — `received` is in `RE_SEAT_USERNAME` alternatives, not counted as winnings.
- **Split pots**: Multiple players with `won ($X)` on separate summary lines.
- **Null byte corruption**: Stripped before parsing (found one real case: `$0\x00.10` instead of `$0.10`).
- **Showdown logic**: Only marks `went_to_showdown` when 2+ players remain at showdown.
- **All-in tracking**: Marks actions with `and is all-in` flag.

### Raise Amount Convention

GGPoker uses "raises $X to $Y" — the parser stores the "to" amount (`Y`). For investment calculation, the increment is `Y - already_in_this_street`.

## Stats Engine (`backend/app/stats_engine.py`)

Queries `hand_players` table for Hero, computes percentages with positional breakdowns (EP/MP/CO/BTN/SB/BB). Returns `HeroStats` Pydantic model.

Key patterns:
- `_positional_pct(data, flag, opp_flag)` — computes `flag_true / opp_flag_true * 100` per position
- `_simple_pct(data, flag)` — flat percentage
- `_aggression_factor` / `_aggression_freq` — (bets+raises)/calls per street

**Important**: DuckDB returns `Decimal` types. The stats engine converts to `float()` where needed to avoid Pydantic serialization issues.

## Reports Endpoints (`backend/app/api/reports.py`)

**`GET /api/reports/graph`** — Returns array of `GraphPoint` with cumulative lines: `cumulative_bb`, `cumulative_ev_bb`, `cumulative_rake_bb`, `cumulative_jackpot_bb`, `cumulative_showdown_bb`, `cumulative_nonshowdown_bb` (plus USD equivalents for each). Supports filters: `stakes`, `date_from`, `date_to`, `last_n_hands`.

**`GET /api/reports/filter-options`** — Returns available stakes and date range for the filter bar.

**`GET /api/reports/breakdown`** — Returns results grouped by stakes, month, and position (hands, won, bb/100, EV bb/100, rake, jackpot).

## Import Flow (`backend/app/api/import_hands.py`)

1. Frontend sends files to `POST /api/import/files/stream`
2. Backend extracts .txt from .zip files if needed
3. Splits file content into individual hands at `Poker Hand #` boundaries
4. Checks for duplicate hand IDs before parsing
5. For each hand: `parse_hand_history(text)` → `insert_parsed_hand(db, parsed)`
6. `insert_parsed_hand` calls `compute_stat_flags`, calculates investment/won/rake/all-in EV, writes all rows
7. Batched in transactions of 200 hands with NDJSON streaming progress
8. `finalize_import(db)` batch-updates player first_seen/last_seen timestamps

Player cache (`_player_cache`, `_next_*_id` counters) lives in `import_hands.py`. Call `reset_import_cache()` when wiping tables.

## Tests

11 tests across 5 classes in `backend/tests/test_parser.py`:

- **TestRegularHand** (2): basic hand parsing, showdown with multiple players
- **TestTimeBankCard** (2): time bank reward handling, username extraction with "received" keyword
- **TestSplitPot** (1): split pot with two winners
- **TestRunItTwice** (5): different winners, board card extraction from first board, same winner both boards, board cards same winner, second board lines skipped
- **TestOpenRaiseOpp** (1): open raise opportunity flag (RFI tracking)

Tests use the two-step API: `parse_hand_history(text)` → `insert_parsed_hand(db, parsed)`, then query DB for assertions.

Run: `cd backend && python -m pytest tests/test_parser.py -v`

## What's Been Tested

- 13,402 real GGPoker Rush & Cash hands imported successfully (1 had null byte corruption, now fixed)
- All API endpoints verified: health, import, stats, graph, settings, clear

## Electron Desktop App

### Architecture

In dev mode (`app.isPackaged === false`):
- Backend runs separately via `make backend` (port 8000)
- Frontend runs separately via `make frontend` (Vite dev server, port 5173)
- Electron opens `http://localhost:5173`, DevTools auto-open
- CORS middleware enabled (frontend ≠ backend origin)

In production (packaged app):
- Electron finds a free port, spawns the PyInstaller-bundled backend on it
- Backend serves the built frontend via `OHM_STATIC_DIR` (FastAPI static files + SPA fallback)
- All on one origin — no CORS needed
- Data stored in `app.getPath('userData')/data/` (`~/Library/Application Support/open-holdem-manager/data/` on macOS, `%APPDATA%/open-holdem-manager/data/` on Windows)

### Key Environment Variables

- `OHM_DATA_DIR` — overrides DuckDB location (set by Electron to `userData/data/`)
- `OHM_STATIC_DIR` — enables static file serving in `main.py` (set by Electron to `resources/frontend/`)
- `ELECTRON=1` — tells Vite to use relative `base: './'` for asset paths in production builds

### Building & Releasing

```bash
make electron-build         # Local: builds frontend + PyInstaller backend + electron-builder
make release v=0.0.3        # Bump version, commit, tag, push → CI builds & auto-publishes
```

`make release v=X.Y.Z` bumps `package.json`, commits, tags `vX.Y.Z`, and pushes. The CI workflow (`.github/workflows/release.yml`) then builds on macOS + Windows in parallel, produces `.dmg` and `.exe`, and auto-publishes to GitHub Releases (electron-builder creates a draft, then a `publish` job promotes it).

After the release is published, add release notes via:
```bash
gh release edit vX.Y.Z --notes "release notes here"
```

**Important**: The git tag version and `package.json` version must match — electron-builder uses `package.json` for the release tag name (`v{version}`). Artifact filenames are version-less (e.g. `Open-Holdem-Manager-arm64.dmg`) so README download links stay stable.

### Auto-Update (electron-updater)

- On launch and every 4 hours, checks GitHub Releases for newer versions via `latest-mac.yml`/`latest.yml` manifests
- Downloads in background, shows progress in `UpdateBanner.tsx` (sticky footer)
- "What's new?" link opens a Dialog with release notes (pulled from GitHub Release body) + "View on GitHub" button (opens release page in system browser via `shell.openExternal`)
- User clicks "Restart to update" → `autoUpdater.quitAndInstall()` (full app restart, not in-place reload)
- IPC channels: `update-available`, `download-progress`, `update-downloaded` (main → renderer)
- IPC handlers: `install-update`, `check-for-updates`, `get-app-version`, `open-external` (renderer → main)
- Preload exposes these via `window.electronAPI`
- Settings dropdown shows current version (`__APP_VERSION__` from Vite define) and "Check for Updates" button

### Auto-Rebuild on Stat Version Bump

When `stat_flags.py` or parser logic changes:
1. Bump `STAT_VERSION` constant in `backend/app/db.py`
2. On next startup, `_check_stat_version()` compares DB's `stat_version` setting vs code constant
3. If outdated, triggers a background thread rebuild (`_bg_rebuild`) of all hands from stored `raw_text`
4. `RebuildBanner.tsx` polls `/api/health` which returns `rebuilding: true` + progress during rebuild
5. App remains usable during rebuild (read queries work, writes blocked by `_lock`)
6. After completion, updates `stat_version` in settings table

### macOS Code Signing

Not configured yet. Users must run `xattr -cr /Applications/Open\ Holdem\ Manager.app` after install. To enable signing, uncomment and configure `identity` and `notarize` in `electron-builder.yml` (requires Apple Developer account).

## Reference Repos

Two GGPoker parsers were studied for reference:
- **[GGPoker-Hand-Analyzer](https://github.com/LayorX/GGPoker-Hand-Analyzer)** — Vanilla JS, regex+state machine parser, 40+ stat definitions. Most useful for GGPoker format details and stat computation patterns.
- **[poker-apprentice/hand-history-parser](https://github.com/poker-apprentice/hand-history-parser)** — TypeScript, ANTLR grammar parser. Good architectural reference for extensible multi-site design.
