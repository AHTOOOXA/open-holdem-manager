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
Landing page: `make landing` (dev server) or `cd frontend && npm run build:landing` (build to `dist-landing/`)
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
    main.py              # FastAPI app, CORS, health, static serving (packaged)
    db.py                # DuckDB connection, schema, STAT_VERSION auto-rebuild
    models.py            # Pydantic response models
    stats_engine.py      # H2N-style stats from hand_players
    stat_flags.py        # Site-independent stat flag computation
    parsers/ggpoker.py   # GGPoker parser — text → ParsedHand
    api/
      import_hands.py    # Import endpoints + insert_parsed_hand() + player cache
      stats.py           # GET /api/stats/hero
      reports.py         # GET /api/reports/graph, /filter-options, /breakdown
      hands.py           # Hand browser: list, detail, tags, notes
      settings.py        # GET/PATCH /api/settings
  run_server.py          # PyInstaller entry point
  tests/test_parser.py   # Parser + DB insertion tests
  requirements.txt

frontend/
  src/
    index.css            # Tailwind v4 @theme with custom dark palette
    App.tsx              # Router: Upload / Stats / Results / Hands tabs
    lib/api.ts           # Typed API client (fetch wrapper, NDJSON streaming)
    components/          # RebuildBanner, UpdateBanner
    components/ui/       # shadcn/ui primitives
    pages/               # UploadPage, StatsPage, GraphPage, HandsPage
  vite.config.ts         # React, Tailwind v4, API proxy, ELECTRON=1 base path
  vite.config.landing.ts # Landing page config (root: landing/, output: dist-landing/)
  landing/               # Static landing site — see Landing Page section

electron/
  main.js                # Spawns backend, finds free port, opens window, auto-updater
  preload.js             # Exposes platform, version, auto-update IPC to renderer

package.json             # Root — Electron, electron-builder, build scripts
electron-builder.yml     # Packages .dmg (macOS), .exe/NSIS (Windows), .AppImage (Linux)
```

## Database Schema (DuckDB)

Tables in `backend/app/db.py`: **sites**, **hands** (one per hand, stores `raw_text`), **players**, **hand_players** (one per player per hand — all stat flags), **actions** (every action), **board_cards**, **hand_tags**, **hand_notes**, **settings** (key/value: hero_username, hero_site, stat_version).

`hand_players` flag groups: financials (won/rake/jackpot in $ and BB, all_in_ev_bb), preflop (vpip/pfr/3bet/4bet/5bet + opportunities, steal, squeeze, limp), postflop (cbet/donk per street + opportunities, fold-to-cbet, aggression counts), showdown (saw_flop/turn/river, went_to_showdown, won_at_showdown).

## Architecture: Parse → Compute → Insert Pipeline

1. **Parse** (`parsers/ggpoker.py`): `parse_hand_history(text) → ParsedHand` — pure text parsing, no DB
2. **Compute** (`stat_flags.py`): `compute_stat_flags(parsed) → dict[str, dict]` — site-independent flags
3. **Insert** (`api/import_hands.py`): `insert_parsed_hand(db, parsed)` — calls compute, calculates financials, writes to DB

New site parsers only need to produce `ParsedHand`. Stat bugs can be fixed and re-derived via `/import/rebuild` without re-parsing.

## GGPoker Parser

Returns `ParsedHand` dataclass (metadata, seats, actions, board, hole cards, collected, rake, showdown). Does NOT compute stat flags.

### Hand History Format Markers

- Header: `Poker Hand #RC...: Hold'em No Limit ($SB/$BB) - YYYY/MM/DD HH:MM:SS`
- Table: `Table 'name' N-max Seat #X is the button`
- Streets: `*** HOLE CARDS ***`, `*** FLOP ***`, `*** TURN ***`, `*** RIVER ***`, `*** SHOWDOWN ***`, `*** SUMMARY ***`
- RIT variants: `*** FIRST FLOP ***`, `*** SECOND FLOP ***`, etc.
- Actions: `player: folds | checks | calls $X | bets $X | raises $X to $Y [and is all-in]`

### Edge Cases Handled

- **Run It Twice**: First board is canonical. Summary has multiple `won ($X)` on same/separate lines.
- **Time bank cards**: `received ($0.02) from time bank card` — `received` is in `RE_SEAT_USERNAME` alternatives, not counted as winnings.
- **Split pots**, **null byte corruption** (stripped), **showdown** (2+ players required), **all-in tracking**.

### Raise Amount Convention

GGPoker "raises $X to $Y" — parser stores the "to" amount (`Y`). Investment increment = `Y - already_in_this_street`.

## Stats Engine (`backend/app/stats_engine.py`)

Computes percentages with positional breakdowns (EP/MP/CO/BTN/SB/BB) from `hand_players`. **Gotcha**: DuckDB returns `Decimal` types — convert to `float()` to avoid Pydantic serialization issues.

## Import Flow

Frontend sends files to `POST /api/import/files/stream` → backend extracts .txt from .zip → splits at `Poker Hand #` → deduplicates → parse → compute → insert (batched 200 hands, NDJSON progress).

Player cache (`_player_cache`, `_next_*_id`) lives in `import_hands.py`. Call `reset_import_cache()` when wiping tables.

## Electron Desktop App

### Architecture

**Dev**: backend (port 8000) + frontend (port 5173) run separately, Electron opens `localhost:5173`, CORS enabled.
**Prod**: Electron finds free port, spawns PyInstaller backend, backend serves built frontend via `OHM_STATIC_DIR`, single origin.

### Environment Variables

- `OHM_DATA_DIR` — overrides DuckDB location (Electron sets to `userData/data/`)
- `OHM_STATIC_DIR` — enables static file serving (Electron sets to `resources/frontend/`)
- `ELECTRON=1` — Vite uses relative `base: './'` for production builds

### Building & Releasing

```bash
make electron-build         # Local build
make release v=0.0.3        # Bump version, commit, tag, push → CI auto-publishes
gh release edit vX.Y.Z --notes "release notes here"
```

**Important**: git tag and `package.json` version must match — electron-builder uses `package.json` for the tag. Artifact filenames are version-less so download links stay stable.

### Auto-Rebuild on Stat Version Bump

Bump `STAT_VERSION` in `backend/app/db.py` → on startup, `_check_stat_version()` detects mismatch → background thread rebuilds all hands from `raw_text`. `RebuildBanner.tsx` shows progress via `/api/health`. App stays usable during rebuild (reads work, writes blocked by `_lock`).

### macOS Code Signing

Not configured. Users must run `xattr -cr /Applications/Open\ Holdem\ Manager.app` after install. To enable: uncomment `identity`/`notarize` in `electron-builder.yml` (requires Apple Developer account).

## Landing Page (ohm.antonchaynik.ru)

Static site in `frontend/landing/` deployed via GitHub Pages (`.github/workflows/landing.yml`). Reuses real app components in `MemoryRouter` with a global fetch interceptor (`mock/api-interceptor.ts`) returning mock data.

### Key Details

- **Separate Vite config**: `vite.config.landing.ts` with `root: landing/`, output to `dist-landing/`
- **CSS**: `landing/index.css` must have `@source "../src"` — without this, Tailwind v4 doesn't scan `src/` and most utility classes are missing
- **Fonts**: GeistMono woff2 copied to `landing/public/fonts/` (node_modules paths don't resolve in static deploy)
- **Deploy**: Auto-deploys on push to `main` when `frontend/landing/**`, `frontend/src/**`, or `vite.config.landing.ts` change
