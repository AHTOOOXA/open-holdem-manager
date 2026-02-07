# Headstart Guide for AI Agent

> You're building an open-source poker tracker. Read PRD.md for the full vision.
> This file tells you what to build FIRST and how to avoid common pitfalls.

---

## Immediate Goal (MVP-0)

Build a local web app where the user can:
1. Upload GGPoker hand history files
2. See a game graph (BB/100 over time, $ won over time)
3. See an H2N-style stats page with positional breakdowns

That's it. No Electron, no PokerStars, no hand browser, no player lookup. Just import → stats + graph.

---

## Stack

```
Python Backend:  FastAPI + DuckDB + uvicorn
Frontend:        React + TypeScript + Vite + TailwindCSS + shadcn/ui
Charts:          Recharts
Tables:          TanStack Table (later, not needed for MVP-0)
```

Run with `make dev` → backend on :8000, frontend on :5173.

---

## Build Order

### Step 1: Backend scaffold
- FastAPI app with CORS enabled for localhost:5173
- DuckDB connection (single file: `data/poker.duckdb`)
- Schema init on startup (see PRD.md section 4.3 for full schema)
- Health check endpoint

### Step 2: GGPoker parser
- This is the hardest part. See format details below.
- Parse into structured data: hand metadata, players, actions, board cards
- One parser module: `backend/app/parsers/ggpoker.py`
- Write tests against the sample hands in `tests/fixtures/`

### Step 3: Import endpoint
- `POST /api/import/files` — accepts uploaded .txt files
- Parse each file, split into individual hands, parse each hand
- Store in DuckDB with duplicate detection (by hand ID)
- Return summary: {imported, duplicates, errors}

### Step 4: Stats engine
- Calculate stats from denormalized `hand_players` flags
- Key stats for the H2N-style page:

```
PRE-FLOP (Total + by position EP/MP/CO/BTN/SB/BB):
  VPIP, PFR, Open Raise, Fold to 3Bet, Call Open Raise,
  3-Bet, 3-Bet IP, 3-Bet OOP, 4-Bet, Limp, Squeeze,
  Fold to 4-Bet, Call 4-Bet, 5-Bet

STEAL section:
  Steal, Fold to 3Bet (steal), 4-Bet (steal), 4-Bet-Fold
  vs. Steal: Fold, Call, 3-Bet (from SB, BB)

POSTFLOP (by street: Flop/Turn/River):
  Continuation Bet, Fold to Continuation Bet,
  Aggression (AF), Aggression Frequency,
  Donk Bet

Missed CBet section:
  Missed CBet, IP → Fold, OOP → Fold
  vs. Missed CBet: Bet IP, Check|Fold, Bet OOP Turn, Check-Fold

SHOWDOWN:
  Went to Showdown, Won at Showdown, Won When Saw Flop

SUMMARY:
  Win Rate (bb/100), Hands count
```

- `GET /api/stats/hero` — returns all the above for configured hero username
- `GET /api/stats/hero?position=BTN` — filter by position

### Step 5: Graph data endpoint
- `GET /api/reports/graph` — returns array of {hand_number, cumulative_bb, bb_per_100_rolling}
- Support query params: date range, stakes filter

### Step 6: Frontend — Upload page
- Drag & drop zone for .txt files
- Upload to backend, show progress
- Display import summary

### Step 7: Frontend — Stats page
- Dense table layout matching H2N (see screenshot reference)
- Two main sections: PRE-FLOP and POSTFLOP
- Positional breakdown columns: Total, EP, MP, CO, BTN, SB, BB
- Color-coded values (green = good, red = bad, yellow = neutral)
- Filters: date range picker, stakes selector

### Step 8: Frontend — Graph page
- Line chart: cumulative BB won over hands played
- Second chart or toggle: BB/100 rolling average
- Date range filter

---

## GGPoker Hand History Format

GGPoker exports hand histories as .txt files. Each file contains multiple hands separated by blank lines. Here's the real format for **cash game** hands (NL Hold'em):

```
Poker Hand #HD1234567890: Tournament #-, Hold'em No Limit ($0.25/$0.50) - 2026/01/15 20:31:42
Table 'NLHGold25050' 6-max Seat #1 is the button
Seat 1: Hero ($52.75 in chips)
Seat 2: Player2 ($50.00 in chips)
Seat 3: Player3 ($58.30 in chips)
Seat 4: Player4 ($50.00 in chips)
Seat 5: Player5 ($87.25 in chips)
Seat 6: Player6 ($50.00 in chips)
Player2: posts small blind $0.25
Player3: posts big blind $0.50
*** HOLE CARDS ***
Dealt to Hero [Ah Kd]
Player4: folds
Player5: raises $1.25 to $1.25
Player6: folds
Hero: raises $3.75 to $3.75
Player2: folds
Player3: folds
Player5: calls $2.50
*** FLOP *** [Ks 7d 2c]
Player5: checks
Hero: bets $2.50
Player5: calls $2.50
*** TURN *** [Ks 7d 2c] [Jh]
Player5: checks
Hero: bets $7.50
Player5: folds
Uncalled bet ($7.50) returned to Hero
Hero: does not show hand
*** SUMMARY ***
Total pot $13.25 | Rake $0.62 | Jackpot $0.13 | Bingo $0 | Fortune $0 | Tax $0
Board [Ks 7d 2c Jh]
Seat 1: Hero (button) collected ($12.50)
Seat 2: Player2 (small blind) folded before Flop
Seat 3: Player3 (big blind) folded before Flop
Seat 4: Player4 folded before Flop (didn't bet)
Seat 5: Player5 folded on the Turn
Seat 6: Player6 folded before Flop (didn't bet)
```

### GGPoker Format Gotchas

1. **Hand ID prefix**: Can be `HD`, `RC`, `TM` — cash games are usually `HD`
2. **Tournament line**: Cash games show `Tournament #-` (dash means no tournament)
3. **Currency**: Stakes shown as `($0.25/$0.50)` — parse SB/BB from here
4. **Raise amounts**: GGPoker shows raise TO amount, not raise BY. `raises $3.75 to $3.75` means total is $3.75
5. **All-in**: Shows as `raises $50.00 to $50.00 and is all-in` or `calls $25.00 and is all-in`
6. **Run It Twice**: After showdown you may see `*** FIRST BOARD ***` and `*** SECOND BOARD ***`
7. **Ante**: Some games have ante, shown as `Player: posts ante $0.05`
8. **Straddle**: `Player: posts straddle $1.00`
9. **Summary section**: Contains rake breakdown (Rake, Jackpot, Bingo, Fortune, Tax)
10. **Position labels in summary**: `(button)`, `(small blind)`, `(big blind)` — other positions not labeled, derive from seat order
11. **Mucked cards**: Sometimes `showed [Ah Kd]` or `mucked [Qh Jh]` in summary
12. **Side pots**: `Main pot $X | Side pot $Y`
13. **Disconnection**: Lines like `Player is disconnected` or `Player has timed out` — skip these
14. **Bounty/Cashout**: Some formats include `Cashout: ...` lines — skip these

### Position Derivation

GGPoker doesn't always label positions explicitly. Derive from:
- Button seat number is given in the header
- SB is next active seat after button
- BB is next active seat after SB
- Then EP, MP, CO going clockwise from BB to button

For 6-max:
- BTN, SB, BB, UTG (EP), MP (HJ), CO

### Key Edge Cases to Handle Early

1. **Hero not in hand** — Hand history might include hands where hero sat out
2. **Uncalled bets** — `Uncalled bet ($X) returned to Player` — don't count as won
3. **Split pots** — Multiple winners
4. **Missing hole cards** — Only hero's cards are shown unless showdown
5. **BB amounts for stats** — Convert all $ amounts to BB using the stakes from the header

---

## Stat Calculation Notes

### What counts as what

- **VPIP**: Player voluntarily put money in preflop (call or raise, NOT posting blinds)
- **PFR**: Player raised preflop (open raise, 3bet, 4bet all count)
- **3-Bet**: Player made the third raise preflop. Open raise = 1st raise, next raise = 3bet
  - Wait, in modern poker: open raise = 2bet (BB is 1bet), next raise = 3bet
  - So BB post = forced, open raise = the first voluntary raise but called "open raise" or "2bet", next raise = 3bet
- **3-Bet Opportunity**: Player faced an open raise and had the chance to 3bet (was not yet invested beyond blinds)
- **Fold to 3-Bet**: Player open raised and then folded to a 3bet
- **CBet**: Player was the last preflop aggressor AND bet on the flop/turn/river
- **CBet Opportunity**: Player was last preflop aggressor AND it was checked to them
- **Aggression Factor**: (bets + raises) / calls on that street
- **WTSD**: Went to showdown / saw flop (only counts hands where player saw flop)
- **W$SD**: Won money at showdown / went to showdown

### Steal positions
- Steal = open raise from CO, BTN, or SB (late position open)
- vs. Steal = action from SB or BB when facing a steal

---

## File Structure (MVP-0)

```
holdem-manager/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, CORS, startup
│   │   ├── db.py                # DuckDB connection + schema init
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── import_hands.py  # POST /api/import/files
│   │   │   ├── stats.py         # GET /api/stats/hero
│   │   │   └── reports.py       # GET /api/reports/graph
│   │   ├── parsers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py          # Parser interface
│   │   │   └── ggpoker.py       # GGPoker hand history parser
│   │   ├── models.py            # Pydantic models
│   │   └── stats_engine.py      # Stat calculation queries
│   ├── tests/
│   │   ├── fixtures/
│   │   │   └── ggpoker_sample.txt  # Real hand history samples
│   │   ├── test_parser.py
│   │   └── test_stats.py
│   ├── pyproject.toml
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── pages/
│   │   │   ├── UploadPage.tsx
│   │   │   ├── StatsPage.tsx
│   │   │   └── GraphPage.tsx
│   │   ├── components/
│   │   │   ├── ui/              # shadcn components
│   │   │   ├── StatsTable.tsx   # H2N-style stats grid
│   │   │   ├── WinrateChart.tsx
│   │   │   └── FileUpload.tsx
│   │   └── lib/
│   │       └── api.ts           # API client
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── data/                        # DuckDB file lives here (gitignored)
├── PRD.md
├── HEADSTART.md
├── Makefile
└── .gitignore
```

---

## Makefile

```makefile
.PHONY: dev backend frontend setup

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

dev:
	make backend & make frontend
```

---

## Settings

The app needs to know the hero's username to calculate "my stats". Store in a simple config:
- `GET /api/settings` → `{hero_username: "Hero", hero_site: "GG"}`
- `PATCH /api/settings` → update hero username
- On first launch, prompt user to enter their GGPoker screen name

---

## What NOT to Build Yet

- Electron packaging
- PokerStars parser
- Hand browser / hand detail view
- Player lookup / opponent stats
- Population analysis
- Session tracking
- Watch folder / auto-import
- Hand tagging / notes

These all come later. First: upload → stats + graph. Ship that, then iterate.
