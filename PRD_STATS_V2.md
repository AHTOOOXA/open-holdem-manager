# PRD: Stats Page v2 — Master-Detail Layout with Drill-Down

## Overview

Redesign the `/stats` page from a full-width stat summary into a **master-detail layout** inspired by Hand2Note's Statistics page. The left panel keeps the existing stat tables (squeezed to ~40% width), and clicking any stat opens a **context-aware detail panel** on the right with sub-breakdowns, range heatmaps, sizing splits, and filtered hand histories.

Additionally, add **Check-Raise** and **Probe / Float / Delayed C-Bet** stat categories.

---

## Layout

```
┌─────────────────────────────┬──────────────────────────────────────────┐
│  LEFT PANEL (~40%)          │  RIGHT PANEL (~60%)                      │
│                             │                                          │
│  [Filters: Stakes | Dates]  │  ┌──────────────────────────────────────┐ │
│  [Hands: 13,402  WR: 4.2]  │  │  STAT HEADER                        │ │
│                             │  │  "Open Raise — 18.5% (1,247/6,738)" │ │
│  PRE-FLOP                   │  ├──────────────────────────────────────┤ │
│  ┌───┬───┬───┬───┬───┬───┐  │  │                                    │ │
│  │Tot│EP │MP │CO │BTN│SB │  │  │  DETAIL CONTENT                    │ │
│  ├───┼───┼───┼───┼───┼───┤  │  │  (varies by stat type)             │ │
│  │OR ►18 │16 │22 │28 │-- │  │  │                                    │ │
│  │F3B│62 │58 │65 │60 │70 │  │  │  - Range heatmap (preflop)        │ │
│  │3B │ 7 │ 5 │ 8 │ 9 │12 │  │  │  - Size splits (postflop)        │ │
│  │...│   │   │   │   │   │  │  │  - Board texture (postflop)       │ │
│  └───┴───┴───┴───┴───┴───┘  │  │  - Hand strength (postflop)       │ │
│                             │  │                                    │ │
│  STEAL                      │  ├──────────────────────────────────────┤ │
│  ┌───────────────────────┐  │  │                                    │ │
│  │ ...                   │  │  │  HAND HISTORY                      │ │
│  └───────────────────────┘  │  │  (filtered to this stat/line)      │ │
│                             │  │                                    │ │
│  POSTFLOP                   │  │  #RC123  BTN  AKs   +2.5bb  ✓     │ │
│  CHECK-RAISE (new)          │  │  #RC456  CO   QJo   -1.0bb  ✗     │ │
│  PROBE / FLOAT (new)        │  │  #RC789  MP   TT    +4.2bb  ✓     │ │
│  MISSED C-BET               │  │  ...                               │ │
│  SHOWDOWN                   │  │  [Load more]                       │ │
│                             │  └──────────────────────────────────────┘ │
└─────────────────────────────┴──────────────────────────────────────────┘
```

---

## Left Panel — Stat Summary

### Behavior
- **Keep the exact current layout** — all 5 existing sections with their positional tables and key-value grids
- **Squeeze to ~40% width** — tables become more compact (abbreviate headers: `Total→Tot`, reduce cell padding)
- **Add 2 new sections** (see "New Stats" below): Check-Raise, Probe/Float/Delayed C-Bet
- **Every stat value is clickable** — clicking highlights the cell and opens the detail panel on the right
- **Active stat highlight** — the clicked cell gets a visible selected state (e.g. indigo border/background)
- **Keep existing color coding** — green/red/yellow/blue thresholds unchanged
- **Filters stay at top of left panel** — stakes, date range, presets
- **Scrollable independently** — left panel scrolls if content overflows vertically

### Sections (7 total, 5 existing + 2 new)

1. **Pre-Flop** (existing) — VPIP, PFR, Open Raise, 3-Bet, 3-Bet IP/OOP, Fold to 3-Bet, 4-Bet, 5-Bet, Limp, Squeeze, etc.
2. **Steal** (existing) — Steal, Fold to 3-Bet in steal, 4-Bet steal; vs Steal: Fold/Call/3-Bet
3. **Postflop** (existing) — C-Bet per street, Fold to C-Bet, AF, AFq, Donk Bet; vs C-Bet responses
4. **Check-Raise** (NEW) — see below
5. **Probe / Float / Delayed C-Bet** (NEW) — see below
6. **Missed C-Bet** (existing) — Missed cbet IP/OOP, fold after miss, vs missed cbet
7. **Showdown** (existing) — WTSD, WSD, WWSF

---

## Right Panel — Detail View

### Default State
When no stat is selected, show a **welcome/overview state**:
- "Click any stat to see detailed breakdown"
- Maybe show overall session summary or a quick stats overview

### Panel Structure (all detail types)

Every detail panel has 3 zones:

```
┌─────────────────────────────────────┐
│ HEADER                              │
│ Stat name, overall value, sample    │
│ Position selector (if applicable)   │
├─────────────────────────────────────┤
│ ANALYSIS ZONE                       │
│ (stat-type-specific content)        │
│ Range heatmap / size splits / etc.  │
├─────────────────────────────────────┤
│ HAND HISTORY                        │
│ Scrollable list of matching hands   │
│ Paginated, sortable                 │
└─────────────────────────────────────┘
```

### Detail Type 1: Preflop Range Detail

**Used for**: VPIP, PFR, Open Raise, 3-Bet, 4-Bet, 5-Bet, Call Open Raise, Limp, Squeeze, Steal, vs Steal 3-Bet

**Header**:
- Stat name + overall % + sample (e.g. "Open Raise — 18.5% (1,247 / 6,738 opportunities)")
- **Position tabs**: [All] [EP] [MP] [CO] [BTN] [SB] [BB] — selecting a position filters the heatmap and hand list

**Analysis zone**:
- **13x13 Range Heatmap** (reuse existing component from /range page)
  - Shows frequency of each combo for the selected action
  - Color intensity = frequency (0% = empty, 100% = solid)
  - Combo count in each cell
- **Quick stats row below heatmap**:
  - Total combos in range
  - Range % (of all combos)
  - Average raise size (if applicable)

**Hand history**:
- All hands where hero had the **opportunity** for this action
- Columns: Hand ID, Position, Hole Cards, Action Taken (✓/✗), Result (bb), Stakes
- Color: green row if action was taken, muted if not (opportunity but didn't take the action)
- Sortable by date, result
- Paginated (50 per page)

### Detail Type 2: Postflop Action Detail

**Used for**: C-Bet (flop/turn/river), Donk Bet, Check-Raise, Probe Bet, Float, Delayed C-Bet

**Header**:
- Stat name + overall % + sample
- **Street tabs** (if multi-street stat): [Flop] [Turn] [River]
- **Position filter**: [All] [IP] [OOP] or full position set

**Analysis zone** — 3 sub-sections:

#### a) Bet Sizing Distribution
- Horizontal bar chart or table showing sizing buckets:
  - **< 33% pot** — count + %
  - **33–50% pot** — count + %
  - **50–75% pot** — count + %
  - **75–100% pot** — count + %
  - **> 100% pot (overbet)** — count + %
- Average sizing as % of pot

#### b) Board Texture Splits
- Table showing stat frequency broken down by board texture (H2N-style categories):
  - **Rank structure**: ABB, ABx, Axx, BBB, BBx, Bxx, MHC, MHD, LC, LD
  - **Suits**: Monotone / Two-tone / Rainbow
  - **Pairing**: Unpaired / Paired
- Each row: texture category, stat % in that texture, sample size

See "Shared: Board Texture Classification" section below for full category definitions.

#### c) Hand Strength at Action
- Table showing what hands hero had when taking this action:
  - **Strong value**: Overpair+, Top pair top kicker, Top pair
  - **Marginal made**: Middle pair, Bottom pair, Weak pair
  - **Draws**: Flush draw, Straight draw (OESD/gutshot), Combo draw
  - **Air**: No pair no draw, Overcards only
- Each row: category, count, % of total actions, average result (bb)

See "Shared: Hand Strength Evaluation" section below for full category definitions.

**Hand history**:
- All hands where hero had the opportunity (e.g. was PFR and flop checked to = cbet opp)
- Columns: Hand ID, Position, Board, Hole Cards, Action (bet size / check), Result (bb)
- Color: green if action taken, muted if opportunity missed

### Detail Type 3: Defensive / Response Detail

**Used for**: Fold to 3-Bet, Fold to 4-Bet, Fold to C-Bet, Fold to Steal, Call Steal, vs Missed C-Bet actions

**Header**:
- Stat name + % + sample
- Position filter

**Analysis zone**:
- **Response distribution**: Pie chart or horizontal bars showing Fold / Call / Raise split
- **By position**: Small table showing the fold/call/raise % per position
- **Range heatmap** (if preflop): What hands hero folds / calls / raises with

**Hand history**:
- All hands where hero faced this action
- Columns: Hand ID, Position, Hole Cards, Hero Response (Fold/Call/Raise), Result (bb)

### Detail Type 4: Showdown Detail

**Used for**: WTSD, WSD, WWSF

**Header**:
- Stat name + % + sample

**Analysis zone**:
- **Result distribution**: Won/Lost at showdown histogram or summary
- **By position**: Positional breakdown table
- **By street reached**: How often hero got to showdown via different run-outs

**Hand history**:
- WTSD: Hands where hero saw flop (went to SD highlighted)
- WSD: Hands where hero went to showdown (won highlighted)
- WWSF: Hands where hero saw flop (won highlighted)

---

## New Stats

### Check-Raise Section

Stats to add to the left panel summary + detail drill-down:

| Stat | Description | Display |
|------|-------------|---------|
| **Check-Raise Flop** | % hero check-raises on flop (of checks facing a bet) | Street table [Flop, Turn, River] |
| **Check-Raise Turn** | % hero check-raises on turn | |
| **Check-Raise River** | % hero check-raises on river | |
| **Fold to XR Flop** | % hero folds facing a check-raise on flop | Street table [Flop, Turn, River] |
| **Fold to XR Turn** | % hero folds facing a check-raise on turn | |
| **Fold to XR River** | % hero folds facing a check-raise on river | |

**New stat flags needed in `stat_flags.py`**:
- `check_raise_flop`, `check_raise_flop_opp` (checked, then faced bet, then raised)
- `check_raise_turn`, `check_raise_turn_opp`
- `check_raise_river`, `check_raise_river_opp`
- `fold_to_check_raise_flop`, `fold_to_check_raise_flop_opp` (bet, got check-raised, folded)
- `fold_to_check_raise_turn`, `fold_to_check_raise_turn_opp`
- `fold_to_check_raise_river`, `fold_to_check_raise_river_opp`

**Detail panel**: Postflop Action Detail (sizing splits, board texture, hand strength)

### Probe Bet / Float / Delayed C-Bet Section

| Stat | Description | Display |
|------|-------------|---------|
| **Probe Bet Flop** | % hero bets flop when PFR/aggressor checks (OOP or IP) | Street table [Flop, Turn, River] |
| **Probe Bet Turn** | % hero bets turn when PFR checks | |
| **Probe Bet River** | % hero bets river when PFR checks | |
| **Float Flop** | % hero calls flop IP (then can bet turn if checked to) | Single value |
| **Delayed C-Bet Turn** | % hero bets turn after checking flop as PFR | Single value |
| **Delayed C-Bet River** | % hero bets river after checking turn as PFR | Single value |

**New stat flags needed in `stat_flags.py`**:
- `probe_bet_flop`, `probe_bet_flop_opp` (opponent was PFR, checked, hero bets)
- `probe_bet_turn`, `probe_bet_turn_opp`
- `probe_bet_river`, `probe_bet_river_opp`
- `float_flop`, `float_flop_opp` (hero calls flop in position)
- `delayed_cbet_turn`, `delayed_cbet_turn_opp` (hero was PFR, checked flop, bets turn)
- `delayed_cbet_river`, `delayed_cbet_river_opp`

**Detail panel**: Postflop Action Detail (sizing splits, board texture, hand strength)

---

## New Backend Requirements

### New API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats/detail/{stat_key}` | Returns detail data for a specific stat |

**`GET /api/stats/detail/{stat_key}`**

Query params: `position`, `stakes`, `date_from`, `date_to`, `street` (for multi-street stats), `page`, `per_page`

Response structure:
```json
{
  "stat_key": "open_raise",
  "stat_name": "Open Raise",
  "overall": { "value": 18.5, "numerator": 1247, "denominator": 6738 },
  "positional": { "ep": { ... }, "mp": { ... }, ... },

  "range_heatmap": {
    "AA": { "frequency": 95.2, "count": 40, "total": 42 },
    "AKs": { "frequency": 88.1, "count": 37, "total": 42 },
    ...
  },

  "sizing_distribution": {
    "buckets": [
      { "label": "< 33% pot", "count": 45, "pct": 12.3 },
      { "label": "33-50%", "count": 120, "pct": 32.8 },
      ...
    ],
    "avg_sizing_pct": 62.5
  },

  "board_texture": {
    "high_card": [
      { "label": "A-high", "value": 72.3, "sample": 150 },
      { "label": "K-high", "value": 65.1, "sample": 120 },
      ...
    ],
    "suits": [
      { "label": "Monotone", "value": 55.0, "sample": 80 },
      { "label": "Two-tone", "value": 68.2, "sample": 200 },
      { "label": "Rainbow", "value": 70.1, "sample": 180 }
    ],
    "pairing": [
      { "label": "Paired", "value": 60.2, "sample": 90 },
      { "label": "Unpaired", "value": 69.5, "sample": 370 }
    ]
  },

  "hand_strength": {
    "categories": [
      { "label": "Overpair+", "count": 30, "pct": 15.2, "avg_result_bb": 3.4 },
      { "label": "Top pair", "count": 55, "pct": 27.9, "avg_result_bb": 1.2 },
      { "label": "Middle pair", "count": 25, "pct": 12.7, "avg_result_bb": -0.5 },
      { "label": "Flush draw", "count": 18, "pct": 9.1, "avg_result_bb": -1.1 },
      { "label": "OESD", "count": 12, "pct": 6.1, "avg_result_bb": -0.8 },
      { "label": "Air", "count": 57, "pct": 28.9, "avg_result_bb": -2.3 }
    ]
  },

  "response_distribution": {
    "fold": { "pct": 62.5, "count": 250 },
    "call": { "pct": 30.0, "count": 120 },
    "raise": { "pct": 7.5, "count": 30 }
  },

  "hands": {
    "items": [
      {
        "hand_id": "RC1234567890",
        "played_at": "2025-01-15T20:30:00",
        "position": "CO",
        "hole_cards": "AhKs",
        "action_taken": true,
        "action_detail": "raises $0.50 to $1.20",
        "board": "Qh 7d 2c",
        "result_bb": 2.5,
        "stakes": "$0.05/$0.10"
      },
      ...
    ],
    "total": 1247,
    "page": 1,
    "per_page": 50
  }
}
```

### Database Changes

**New columns in `hand_players`**:
```sql
-- Check-raise
check_raise_flop BOOLEAN, check_raise_flop_opp BOOLEAN,
check_raise_turn BOOLEAN, check_raise_turn_opp BOOLEAN,
check_raise_river BOOLEAN, check_raise_river_opp BOOLEAN,
fold_to_check_raise_flop BOOLEAN, fold_to_check_raise_flop_opp BOOLEAN,
fold_to_check_raise_turn BOOLEAN, fold_to_check_raise_turn_opp BOOLEAN,
fold_to_check_raise_river BOOLEAN, fold_to_check_raise_river_opp BOOLEAN,

-- Probe bet
probe_bet_flop BOOLEAN, probe_bet_flop_opp BOOLEAN,
probe_bet_turn BOOLEAN, probe_bet_turn_opp BOOLEAN,
probe_bet_river BOOLEAN, probe_bet_river_opp BOOLEAN,

-- Float
float_flop BOOLEAN, float_flop_opp BOOLEAN,

-- Delayed c-bet
delayed_cbet_turn BOOLEAN, delayed_cbet_turn_opp BOOLEAN,
delayed_cbet_river BOOLEAN, delayed_cbet_river_opp BOOLEAN
```

**New columns shared with Population PRD** (see PRD_POPULATION.md):
```sql
-- On hands table: precomputed board texture
flop_texture_rank VARCHAR,   -- ABB, ABx, Axx, BBB, BBx, Bxx, MHC, MHD, LC, LD
flop_texture_suit VARCHAR,   -- monotone, two_tone, rainbow
flop_paired BOOLEAN,
turn_texture VARCHAR,         -- completed_draw, draw_adding, overcard, paired_board, brick
river_texture VARCHAR,

-- On actions table: pot context at time of action
pot_before_action DECIMAL,
bet_pct_pot DECIMAL,

-- On hand_players table: pot type
pot_type VARCHAR              -- srp, 3bet, 4bet, 5bet
```

After schema migration: run `/api/import/rebuild` to recompute all flags from stored raw hand text.

---

## Shared: Hand Strength Evaluation

New utility needed: given hero's hole cards + board cards, classify hand strength.

Categories:
- **Overpair+**: Overpair, set, two pair+, straight, flush, full house, quads, straight flush
- **Top pair (good kicker)**: Top pair with A-T kicker
- **Top pair (weak kicker)**: Top pair with 9 or lower kicker
- **Middle pair**: Second pair on board
- **Bottom / Weak pair**: Third pair or lower, pocket pair below middle pair
- **Flush draw**: 4 to a flush
- **OESD**: Open-ended straight draw (8 outs)
- **Gutshot**: Inside straight draw (4 outs)
- **Combo draw**: Flush draw + straight draw
- **Overcards**: Two cards above the board, no pair/draw
- **Air**: No pair, no draw, no overcards

This requires a small poker hand evaluator function. Doesn't need full hand ranking — just classification into these buckets based on hole cards vs board.

---

## Shared: Board Texture Classification

Shared utility between Stats v2 detail panels and Population Analysis (see PRD_POPULATION.md). Implemented as a Python utility in the backend.

### Flop Classification

Primary axis — **Rank Structure** (Broadway = T, J, Q, K; Ace treated separately):

| Category | Code | Definition | Example |
|----------|------|------------|---------|
| Ace + Broadway + Broadway | ABB | A + 2 broadways | A♠ K♥ J♦ |
| Ace + Broadway + x | ABx | A + 1 broadway + low | A♠ Q♥ 5♦ |
| Ace + x + x | Axx | A + 2 non-broadway | A♠ 7♥ 3♦ |
| 3 Broadways (no A) | BBB | 3 broadways, no ace | K♠ Q♥ T♦ |
| 2 Broadways + x (no A) | BBx | 2 broadways + low, no ace | K♠ J♥ 6♦ |
| 1 Broadway + x + x (no A) | Bxx | 1 broadway + 2 low, no ace | Q♠ 7♥ 3♦ |
| Mid-High Connected | MHC | T-9 high, connected (≤2 gap) | T♠ 9♥ 7♦ |
| Mid-High Disconnected | MHD | T-9 high, disconnected | T♠ 6♥ 2♦ |
| Low Connected | LC | 8-high or lower, connected | 8♠ 7♥ 5♦ |
| Low Disconnected | LD | 8-high or lower, disconnected | 8♠ 4♥ 2♦ |

Secondary axis — **Suit Structure**: Monotone / Two-tone / Rainbow

Tertiary axis — **Pairing**: Paired / Unpaired

### Turn Classification

Classified by what the turn card brought relative to flop:

| Category | Definition |
|----------|------------|
| **Completed draw** | 3rd flush card, or completes obvious straight |
| **Draw-adding** | 2nd flush card, or adds straight potential |
| **Overcard** | Highest card on board |
| **Paired board** | Pairs one of the flop cards |
| **Brick** | Low, unconnected, doesn't change texture |

### River Classification

Same categories as turn, applied to 4-card → 5-card board transition.

---

## Shared: Bet Sizing Extraction

For postflop detail panels, need to compute bet size as % of pot at time of action.

Requires tracking the **pot size at each action**. Stored as precomputed columns:
- `pot_before_action` on `actions` table
- `bet_pct_pot` = `amount / pot_before_action` for bets/raises

Computed during `insert_parsed_hand` for new hands, backfilled via rebuild for existing.

---

## Frontend Implementation Plan

### Component Structure

```
StatsPage.tsx (v2)
├── StatsFilterBar.tsx (existing, moved to left panel header)
├── StatsSummaryPanel.tsx (left panel — refactored from current page)
│   ├── PreflopSection.tsx (existing)
│   ├── StealSection.tsx (existing)
│   ├── PostflopSection.tsx (existing)
│   ├── CheckRaiseSection.tsx (NEW)
│   ├── ProbeFloatSection.tsx (NEW)
│   ├── MissedCbetSection.tsx (existing)
│   └── ShowdownSection.tsx (existing)
├── StatDetailPanel.tsx (right panel — NEW)
│   ├── DetailHeader.tsx
│   ├── PreflopRangeDetail.tsx (heatmap + quick stats)
│   ├── PostflopActionDetail.tsx (sizing + board + strength)
│   ├── DefensiveDetail.tsx (response distribution + range)
│   ├── ShowdownDetail.tsx
│   └── DetailHandHistory.tsx (shared hand list component)
```

### State Management
- Selected stat stored as `{ key: string, position?: string, street?: string }`
- Detail panel fetches data from `/api/stats/detail/{key}` when selection changes
- Left panel and right panel scroll independently (both `overflow-y: auto`)
- URL reflects selected stat for shareability: `/stats?detail=open_raise&pos=co`

### Responsive Behavior
- Desktop (>1280px): Side-by-side layout
- Tablet/narrow (<1280px): Full-width summary with detail as a slide-over/modal panel
- The detail panel should have a close button (×) to return to summary-only view

---

## Stat Key Registry

Every clickable stat maps to a `stat_key` used for the detail endpoint:

### Preflop (Detail Type: Range)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| VPIP | `vpip` | Range |
| PFR | `pfr` | Range |
| Open Raise | `open_raise` | Range |
| 3-Bet | `three_bet` | Range |
| 3-Bet IP | `three_bet_ip` | Range |
| 3-Bet OOP | `three_bet_oop` | Range |
| 4-Bet | `four_bet` | Range |
| 5-Bet | `five_bet` | Range |
| Limp | `limp` | Range |
| Call Open Raise | `call_open_raise` | Range |
| Squeeze | `squeeze` | Range |

### Preflop Defense (Detail Type: Defensive)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Fold to 3-Bet | `fold_to_3bet` | Defensive |
| Fold to 4-Bet | `fold_to_4bet` | Defensive |
| Limp-Fold | `limp_fold` | Defensive |
| 4-Bet-Fold | `four_bet_fold` | Defensive |

### Steal (Detail Type: Range for attacks, Defensive for defense)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Steal | `steal` | Range |
| Fold to 3-Bet (steal) | `fold_to_3bet_steal` | Defensive |
| 4-Bet (steal) | `four_bet_steal` | Range |
| vs Steal Fold | `vs_steal_fold` | Defensive |
| vs Steal Call | `vs_steal_call` | Defensive |
| vs Steal 3-Bet | `vs_steal_3bet` | Range |

### Postflop (Detail Type: Postflop Action)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| C-Bet Flop | `cbet_flop` | Postflop Action |
| C-Bet Turn | `cbet_turn` | Postflop Action |
| C-Bet River | `cbet_river` | Postflop Action |
| Donk Bet Flop | `donk_bet_flop` | Postflop Action |
| Donk Bet Turn | `donk_bet_turn` | Postflop Action |
| Donk Bet River | `donk_bet_river` | Postflop Action |
| Check-Raise Flop | `check_raise_flop` | Postflop Action |
| Check-Raise Turn | `check_raise_turn` | Postflop Action |
| Check-Raise River | `check_raise_river` | Postflop Action |
| Probe Bet Flop | `probe_bet_flop` | Postflop Action |
| Probe Bet Turn | `probe_bet_turn` | Postflop Action |
| Delayed C-Bet Turn | `delayed_cbet_turn` | Postflop Action |
| Delayed C-Bet River | `delayed_cbet_river` | Postflop Action |
| Float Flop | `float_flop` | Postflop Action |

### Postflop Defense (Detail Type: Defensive)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| Fold to C-Bet Flop | `fold_to_cbet_flop` | Defensive |
| Fold to C-Bet Turn | `fold_to_cbet_turn` | Defensive |
| Fold to C-Bet River | `fold_to_cbet_river` | Defensive |
| Fold to XR Flop | `fold_to_check_raise_flop` | Defensive |
| Fold to XR Turn | `fold_to_check_raise_turn` | Defensive |
| Fold to XR River | `fold_to_check_raise_river` | Defensive |

### Showdown (Detail Type: Showdown)
| Left Panel Label | stat_key | Detail Type |
|-----------------|----------|-------------|
| WTSD | `wtsd` | Showdown |
| WSD | `wsd` | Showdown |
| WWSF | `wwsf` | Showdown |

---

## Implementation Phases

### Phase 1: Layout + Click-Through Foundation
- Refactor `StatsPage.tsx` into master-detail two-panel layout
- Make every stat cell clickable with selected state
- Create `StatDetailPanel.tsx` with header + placeholder content + hand list
- Build the detail hand history endpoint (paginated, filtered by stat_key)
- Wire up URL state (`/stats?detail=...&pos=...`)

### Phase 2: New Stat Flags (Backend)
- Add check-raise flags to `stat_flags.py` and `db.py` schema
- Add probe/float/delayed cbet flags
- Run rebuild to backfill all existing hands
- Add new sections to `stats_engine.py` computations
- Add new sections to left panel UI

### Phase 3: Preflop Range Detail
- Build `PreflopRangeDetail.tsx` — embed 13x13 heatmap (reuse RangeChart component)
- Build backend: query `hand_players` + `hands` to get combo frequencies for a given stat + position
- Position tab filtering

### Phase 4: Postflop Action Detail
- Build `PostflopActionDetail.tsx` with 3 sub-sections
- **Sizing distribution**: Query `actions` table, compute bet/pot ratios, bucket into categories
- **Board texture**: Build board texture classifier, query and group
- **Hand strength**: Build hand strength evaluator, classify hero hands at action point
- Wire sub-sections with data from `/api/stats/detail/{key}`

### Phase 5: Defensive + Showdown Detail
- Build `DefensiveDetail.tsx` — response distribution, positional breakdown, range heatmap for preflop defense
- Build `ShowdownDetail.tsx` — result distribution, positional breakdown
- Polish UX: transitions, loading states, empty states

---

## Color Coding (Unchanged)

Keep all existing H2N-style color thresholds. New stats get similar thresholds:

| Stat | Green | Red | Yellow | Blue |
|------|-------|-----|--------|------|
| Check-Raise Flop | 8-14% | >20% | — | <5% |
| Check-Raise Turn | 8-14% | >20% | — | <5% |
| Probe Bet | 25-40% | >55% | — | <20% |
| Delayed C-Bet | 30-50% | >65% | — | <20% |
| Float | 20-35% | >45% | — | <15% |

---

## Open Questions

1. **Pot size tracking**: Do we compute pot-at-action-time during insert (store it), or reconstruct from actions on-the-fly for detail queries? Storing is faster to query but requires a rebuild. On-the-fly is simpler but slower.
2. **Hand strength evaluation complexity**: Full hand evaluation (detecting straights, flushes, etc.) requires a poker hand evaluator. Should we use an existing Python library (like `treys` or `pokerkit`) or write a minimal one?
3. **Performance**: Detail queries with hand strength + board texture could be slow for 10k+ hands. Should we precompute and store these classifications, or compute on demand with caching?
