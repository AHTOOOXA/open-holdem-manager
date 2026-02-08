# Open Holdem Manager (OHM) — Project Handoff

## What This Is

A local poker hand history tracker (like Hand2Note / HoldemManager) for GGPoker Rush & Cash. Parses hand history .txt files, stores in DuckDB, computes H2N-style stats, shows graphs.

## Tech Stack

- **Backend**: Python 3.10+, FastAPI >=0.115, DuckDB >=1.1, Pydantic >=2.0, python-multipart
- **Frontend**: React 19, TypeScript 5.9, Vite 7, TailwindCSS v4 (@theme syntax), Recharts 3, React Router 7
- **DB**: DuckDB file-based at `data/poker.duckdb` — schema auto-created on first startup
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
Tests: `cd backend && python -m pytest tests/test_parser.py -v`
Lint: `cd frontend && npm run lint`
API docs: http://localhost:8000/docs (FastAPI auto-generated Swagger)

## Frontend Config

- Vite proxies `/api` requests to `http://localhost:8000` (see `frontend/vite.config.ts`)
- Path alias: `@/` maps to `./src/` (configured in `tsconfig.app.json`)
- Dark theme defined via Tailwind `@theme` in `frontend/src/index.css` — custom CSS vars: `--color-background`, `--color-surface`, `--color-primary` (indigo #6366f1), `--color-green`, `--color-red`, etc.

## Project Structure

```
backend/
  app/
    main.py                 # FastAPI app, CORS (localhost:5173), startup, health
    db.py                   # DuckDB connection, schema init, sequence sync
    models.py               # Pydantic response models
    stats_engine.py         # Computes H2N-style stats from hand_players table
    parsers/
      ggpoker.py            # GGPoker hand history parser (~1000 lines, the core)
    api/
      import_hands.py       # POST /api/import/files, /import/files/stream, /import/clear
      stats.py              # GET /api/stats/hero?position=&stakes=&date_from=&date_to=
      reports.py            # GET /api/reports/graph
      settings.py           # GET/PATCH /api/settings
  tests/
    test_parser.py          # 10 tests across 4 classes
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
    App.tsx                 # Router: Upload / Stats / Graph tabs
    lib/api.ts              # Typed API client (fetch wrapper, NDJSON streaming)
    pages/
      UploadPage.tsx        # Drag & drop files/folders/ZIPs, progress bar, clear DB
      StatsPage.tsx         # H2N-style stat table with positional columns
      GraphPage.tsx         # Recharts line chart (cumulative BB, rolling BB/100)
  vite.config.ts            # React plugin, Tailwind v4 plugin, API proxy to :8000
  tsconfig.app.json         # Strict mode, ES2022, path alias @/*
```

## Database Schema (DuckDB)

Key tables in `backend/app/db.py`:

- **sites** — poker sites (hardcoded: id=1, name='GGPoker', code='GG')
- **hands** — one row per hand (id=hand_id string like "RC1234567890", played_at, stakes, bb_amount, raw_text)
- **players** — unique players (site_id, username, notes, color_tag, first_seen, last_seen)
- **hand_players** — one row per player per hand. Contains ALL stat flags:
  - `won`, `won_bb`, `rake`, `rake_bb` — net results
  - `vpip`, `pfr`, `three_bet`, `three_bet_opp`, `four_bet`, `four_bet_opp` — preflop
  - `fold_to_3bet`, `fold_to_4bet`, `open_raise`, `call_open_raise`, `limp`, `squeeze`, `five_bet`
  - `steal_attempted`, `faced_steal`, `fold_to_steal`, `call_steal`, `three_bet_vs_steal`
  - `saw_flop/turn/river`, `went_to_showdown`, `won_at_showdown`
  - `cbet_flop/turn/river`, `cbet_flop/turn/river_opp`, `fold_to_cbet_flop/turn/river`
  - `missed_cbet_flop/turn`, `donk_bet_flop/turn/river`
  - `flop/turn/river_bets/raises/calls` — aggression counts
- **actions** — every action (street, action_type, amount, amount_bb, is_all_in)
- **board_cards** — community cards per street per hand
- **settings** — key/value (hero_username, hero_site)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Returns `{status, hands}` |
| POST | `/api/import/files` | Synchronous multipart upload (50MB limit) |
| POST | `/api/import/files/stream` | Streaming upload, returns NDJSON (`start`/`progress`/`done`) |
| POST | `/api/import/clear` | Truncate all hand data |
| GET | `/api/stats/hero` | Hero stats. Optional filters: `position`, `stakes`, `date_from`, `date_to` |
| GET | `/api/reports/graph` | Array of `{hand_number, cumulative_bb, bb_per_100_rolling}` |
| GET | `/api/settings` | Get settings (hero_username, hero_site) |
| PATCH | `/api/settings` | Update settings |

## GGPoker Parser (`backend/app/parsers/ggpoker.py`)

### How It Works

1. Strips null bytes, BOM, zero-width chars (`\x00`, `\ufeff`, `\u200b`, `\u200c`, `\u200d`)
2. Parses header line (hand ID, stakes, timestamp) via regex
3. Parses table info (table name, size, button seat)
4. Parses seat lines (player names, stacks)
5. Assigns positions via `POSITIONS_BY_COUNT` lookup — supports 2-9 max tables, clockwise from button
6. Line-by-line state machine: `preflop` → `flop` → `turn` → `river`, with `in_showdown` and `in_summary` flags
7. `_should_skip()` filters noise lines: disconnected, timed out, joins table, sits out, etc. (12+ patterns)
8. Tracks all voluntary actions, blinds, antes; per-street investment for raise calculations
9. Preflop aggression: tracks raise levels (open/3-bet/4-bet/5-bet), squeeze detection (3bet with callers)
10. Postflop: cbet opportunities/attempts, donk bets, fold-to-cbet, missed cbet — all per street
11. Steal detection: raise from CO/BTN/SB, tracks vs-steal responses (fold/call/3bet)
12. In summary: extracts `won`/`collected` amounts via `re.finditer` (handles multiple amounts on one line for RIT)
13. Computes all stat flags (VPIP, PFR, 3-bet, steal, cbet, aggression, etc.)
14. Calculates net won: `gross_collected + uncalled_returned - total_invested`
15. Inserts everything into DuckDB (hand, players, hand_players, actions, board_cards)

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

## Graph Endpoint (`backend/app/api/reports.py`)

Returns array of `{hand_number, cumulative_bb, bb_per_100_rolling}`. Rolling BB/100 uses a 100-hand window.

**Note**: There is no EV data yet. The parser does not extract or compute expected value. This needs to be added.

## Import Flow

1. Frontend sends files to `POST /api/import/files/stream`
2. Backend extracts .txt from .zip files if needed
3. Splits file content into individual hands at `Poker Hand #` boundaries
4. Checks for duplicate hand IDs before parsing
5. Each hand is wrapped in `BEGIN/COMMIT/ROLLBACK` transaction
6. Streams NDJSON progress updates every 50 hands (message types: `start`, `progress`, `done`)
7. Frontend shows progress bar with live counts

## Tests

10 tests across 4 classes in `backend/tests/test_parser.py`:

- **TestRegularHand** (2): basic hand parsing, showdown with multiple players
- **TestTimeBankCard** (2): time bank reward handling, username extraction with "received" keyword
- **TestSplitPot** (1): split pot with two winners
- **TestRunItTwice** (5): different winners, board card extraction from first board, same winner both boards, board cards same winner, second board lines skipped

Run: `cd backend && python -m pytest tests/test_parser.py -v`

## What's Been Tested

- 13,402 real GGPoker Rush & Cash hands imported successfully (1 had null byte corruption, now fixed)
- All API endpoints verified: health, import, stats, graph, settings, clear

## Reference Repos

Two GGPoker parsers were studied for reference:
- **[GGPoker-Hand-Analyzer](https://github.com/LayorX/GGPoker-Hand-Analyzer)** — Vanilla JS, regex+state machine parser, 40+ stat definitions. Most useful for GGPoker format details and stat computation patterns.
- **[poker-apprentice/hand-history-parser](https://github.com/poker-apprentice/hand-history-parser)** — TypeScript, ANTLR grammar parser. Good architectural reference for extensible multi-site design.
