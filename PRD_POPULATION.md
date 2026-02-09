# PRD: Population Analysis Page (`/population`)

## Overview

A dedicated page for **field research** — analyzing the aggregate tendencies of all opponents (the "population" or "pool") across the entire database. This answers the question: "How does the average player at my stake play?"

Unlike hero stats (which track one player's performance), population stats aggregate across **all observed player-hand records** excluding hero. With N hero hands, we observe ~6N player-hand records (6-max), giving massive sample sizes for aggregate metrics.

The page is organized as a **funnel** — broadest/most reliable metrics at the top, progressively more granular (and noisier) sections below, with statistical confidence indicators throughout.

---

## Statistical Reliability Framework

Based on a 1M-hand sample in 6-max Zoom:

| Category | Observations | Error Margin | Confidence |
|----------|-------------|--------------|------------|
| Preflop aggregates by position | ~1M per position | < 1% | Excellent |
| Preflop position-vs-position pairs | ~50K–200K per pair | 1–2% | Very good |
| Flop lines in SRP (aggregate) | ~2–2.4M | < 1% | Excellent |
| Flop lines by board texture (5-8 groups) | ~30K–100K per group | 1–3% | Good |
| Flop lines by texture × IP/OOP × pot type | ~5K–20K per cell | 2–5% | Moderate |
| Turn aggregate lines | ~1–1.3M | < 1% | Excellent |
| Turn by board texture (2-3 groups) | ~10K–50K per group | 2–5% | Moderate |
| River aggregate lines | ~600–800K | 1–2% | Good |
| River by texture × line × sizing | Hundreds | 5–15%+ | Noisy |
| 4-bet pots (all postflop) | ~15–25K total | 3–5% | Moderate |
| 4-bet pots by street × texture | Hundreds | Unreliable | Too sparse |
| Showdown-based bluff frequency | Limited to showdown hands | Wide CI | Proxy only |

**Rule**: Every metric cell on the page shows its **sample size** and a **confidence indicator** (green/yellow/red dot or background shade based on sample count thresholds).

Sample confidence thresholds:
- **Green** (reliable): >= 1,000 observations
- **Yellow** (directional): 200–999 observations
- **Red** (noisy): < 200 observations
- **Hidden/greyed**: < 50 observations (not shown or greyed out with warning)

---

## Page Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  POPULATION ANALYSIS                                                 │
│  [Stakes ▾] [Date Range ◁ ▷] [Min Hands/Player: 20 ▾]              │
│  Pool: 8,432 unique players  |  6,234,000 observations              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ PREFLOP ────────────────────────────────────────────────────┐    │
│  │  Position Matrix  |  Sizing  |  4-Bet/5-Bet                 │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ FLOP ───────────────────────────────────────────────────────┐    │
│  │  Lines & Frequencies  |  By Board Texture  |  Sizings        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ TURN ───────────────────────────────────────────────────────┐    │
│  │  Lines & Frequencies  |  By Board Texture (coarser)          │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ RIVER ──────────────────────────────────────────────────────┐    │
│  │  Aggregate Lines  |  Aggression Frequency                    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ POT TYPE ANALYSIS ──────────────────────────────────────────┐    │
│  │  SRP vs 3-Bet vs 4-Bet pot tendencies                        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ SHOWDOWN & AGGRESSION ──────────────────────────────────────┐    │
│  │  WTSD, WSD, AF by street, bet frequency as bluff proxy       │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Each section is collapsible. Sections are ordered top-to-bottom by statistical reliability (most reliable first).

---

## Filters

| Filter | Options | Default |
|--------|---------|---------|
| **Stakes** | All / specific stakes | All |
| **Date range** | From/To with presets (Week/Month/3M/6M/Year/All) | All |
| **Min hands per player** | 1 / 10 / 20 / 50 / 100 | 20 |
| **Exclude hero** | Toggle | On (exclude hero by default) |

**Min hands per player** filters out drive-by players with very few hands — their stats are noise. At min=20, we filter to regulars + semi-regulars who have played enough to contribute meaningful data.

---

## Section 1: Preflop

### 1a. Position Matrix — Open Raise / 3-Bet / Fold-to-3-Bet

**6x6 heatmap grids** where rows = opener position, columns = responder position.

Three matrices:

**Open Raise % by Position** (simple 1x6 bar):
```
       EP     MP     CO     BTN    SB     BB
OR%   14.2   18.5   27.3   42.1   38.5    —
       (n)    (n)    (n)    (n)    (n)
```

**3-Bet % Matrix** (position-vs-position):
```
3-Bet %      vs EP   vs MP   vs CO   vs BTN   vs SB
from MP       4.2     —       —       —        —
from CO       5.1     5.8     —       —        —
from BTN      6.3     7.1     8.2     —        —
from SB       7.5     8.0     9.1    10.2      —
from BB       8.1     8.8    10.5    12.3     11.0
```
Color intensity = frequency (darker = higher %). Each cell shows value + sample count.

**Fold to 3-Bet Matrix** (same structure, opener vs 3-bettor position).

**Cold Call % Matrix** (who calls whose opens from which position).

### 1b. Open Raise Sizing by Position

Table showing average open raise sizes and distribution:

```
Position │ Avg Size │ 2.0x  │ 2.2x  │ 2.5x  │ 3.0x  │ Other
─────────┼──────────┼───────┼───────┼───────┼───────┼──────
EP       │ 2.42x    │  15%  │  35%  │  40%  │   8%  │  2%
MP       │ 2.38x    │  18%  │  38%  │  35%  │   7%  │  2%
CO       │ 2.31x    │  22%  │  42%  │  30%  │   4%  │  2%
BTN      │ 2.25x    │  30%  │  40%  │  25%  │   3%  │  2%
SB       │ 2.55x    │  10%  │  25%  │  45%  │  15%  │  5%
```

### 1c. 4-Bet / 5-Bet by Position

```
           EP    MP    CO    BTN    SB    BB
4-Bet %   1.8   2.1   2.5   3.2   4.1   3.8
F to 4B   62    58    55    52    48    50
5-Bet %   0.3   0.4   0.5   0.6   0.8   0.7
```

### 1d. Squeeze / Limp / Cold Call

Additional preflop population tendencies:
- Squeeze % by position (when facing open + call)
- Limp % by position
- Limp-fold % (limp then fold to raise)
- Cold call vs 3-bet % by position

---

## Section 2: Flop

### 2a. Main Line Frequencies (Aggregate)

Split by **pot type** (SRP vs 3-Bet pot) and **position** (IP vs OOP):

```
                    SRP              3-Bet Pot
                  IP    OOP        IP     OOP
C-Bet %          68.2  55.1       62.5   48.3
Fold to C-Bet    45.3  52.1       38.2   44.0
Check-Raise %     8.1  10.5        6.2    8.8
Donk Bet %        —     7.3        —      5.1
Probe Bet %       —     —          —      —
```
(Probe = N/A on flop for PFR check scenarios, but included for completeness)

### 2b. By Board Texture (H2N-style categories)

**Flop Texture Classification** (rank structure x suit structure):

Primary axis — **Rank Structure** (based on card ranks, Broadway = T+):

| Category | Code | Definition | Example |
|----------|------|------------|---------|
| Ace + Broadway + Broadway | ABB | A + 2 broadways | A K J |
| Ace + Broadway + x | ABx | A + 1 broadway + low | A Q 5 |
| Ace + x + x | Axx | A + 2 non-broadway | A 7 3 |
| 3 Broadways (no A) | BBB | 3 broadways, no ace | K Q T |
| 2 Broadways + x (no A) | BBx | 2 broadways + low, no ace | K J 6 |
| 1 Broadway + x + x (no A) | Bxx | 1 broadway + 2 low, no ace | Q 7 3 |
| Mid-High Connected | MHC | T-9 high, connected (<=2 gap) | T 9 7 |
| Mid-High Disconnected | MHD | T-9 high, disconnected | T 6 2 |
| Low Connected | LC | 8-high or lower, connected | 8 7 5 |
| Low Disconnected | LD | 8-high or lower, disconnected | 8 4 2 |

Secondary axis — **Suit Structure**:
- **Monotone** (M): 3 cards same suit
- **Two-tone** (T): 2 cards same suit
- **Rainbow** (R): all different suits

Tertiary axis — **Pairing**:
- **Paired** (P): 2+ cards same rank
- **Unpaired** (U): all different ranks

**Display**: Table with texture category rows, showing C-Bet %, Fold-to-CBet %, XR %, average sizing for each. Grouped by rank structure with suit/pairing as sub-rows or filterable.

Example:
```
Texture        │ C-Bet%│ Avg Size│ F to CB│  XR% │ Sample
───────────────┼───────┼─────────┼────────┼──────┼───────
Axx Rainbow    │  72.1 │  33%pot │  48.3  │  6.2 │ 45,230
Axx Two-tone   │  65.3 │  40%pot │  44.1  │  8.5 │ 52,100
ABx Rainbow    │  58.2 │  50%pot │  42.0  │  9.1 │ 38,400
BBB            │  51.0 │  55%pot │  38.5  │ 12.3 │ 12,800
Low Connected  │  55.8 │  52%pot │  40.2  │ 11.5 │ 28,900
Monotone       │  48.5 │  35%pot │  35.0  │ 14.2 │ 18,600
Paired         │  60.3 │  45%pot │  46.1  │  7.8 │ 22,300
...
```

### 2c. Sizing Distribution on Flop

By pot type (SRP / 3-Bet):

```
C-Bet Size     │ SRP IP │ SRP OOP │ 3BP IP │ 3BP OOP
───────────────┼────────┼─────────┼────────┼────────
< 33% pot      │  42.1  │  38.5   │  55.2  │  48.0
33-50% pot     │  35.2  │  33.0   │  28.1  │  30.5
50-75% pot     │  18.3  │  22.1   │  12.0  │  16.2
75-100% pot    │   3.5  │   5.0   │   3.8  │   4.5
> 100% (OB)    │   0.9  │   1.4   │   0.9  │   0.8
Avg % pot      │  38.2  │  42.0   │  33.5  │  37.1
```

---

## Section 3: Turn

### 3a. Main Line Frequencies

```
                      SRP              3-Bet Pot
                    IP    OOP        IP     OOP
Double Barrel %    58.3  45.2       52.1   40.5
Fold to 2nd Barrel 42.0  48.3       38.5   43.0
Check-Raise %       5.5   7.2        4.8    6.5
Probe Bet %        32.1  28.5       35.2   30.0
Delayed C-Bet %    42.0  35.5       38.0   32.0
```

### 3b. By Board Texture (Coarser — 2-3 Groups)

Turn texture is classified by **what the turn card brought** relative to the flop:

| Category | Definition | Example |
|----------|------------|---------|
| **Completed draw** | Turn brings 3rd flush card, or completes obvious straight | Flop: 8 7 2, Turn: 6 |
| **Draw-adding** | Turn brings 2nd flush card, or adds straight potential | Flop: K 7 2, Turn: 8 |
| **Overcard** | Turn is highest card on board | Flop: 9 7 2, Turn: K |
| **Paired board** | Turn pairs one of the flop cards | Flop: K 7 2, Turn: 7 |
| **Brick** | Low, unconnected, doesn't change texture | Flop: A K 7, Turn: 3 |

Show barrel %, fold-to-barrel, XR, probe for each turn category.

### 3c. Sizing Distribution on Turn

Same format as flop sizing, grouped by pot type and position.

---

## Section 4: River

### 4a. Aggregate Lines Only

```
                      SRP              3-Bet Pot
                    IP    OOP        IP     OOP
Triple Barrel %    38.5  30.2       35.0   28.1
Fold to 3rd Barrel 48.2  52.0       44.5   48.3
Probe Bet %        28.0  25.1       30.2   26.5
Bet Frequency      42.3  35.5       40.1   33.0
```

### 4b. Sizing Distribution on River

```
River Bet Size   │ SRP IP │ SRP OOP │ 3BP IP │ 3BP OOP
─────────────────┼────────┼─────────┼────────┼────────
< 33% pot        │  18.5  │  15.2   │  20.1  │  17.5
33-50% pot       │  28.3  │  25.0   │  25.5  │  23.0
50-75% pot       │  30.1  │  32.5   │  28.0  │  30.2
75-100% pot      │  15.0  │  18.0   │  16.5  │  19.0
> 100% (OB)      │   8.1  │   9.3   │   9.9  │  10.3
Avg % pot        │  55.2  │  60.1   │  53.0  │  58.5
```

**Note**: No board texture breakdown on river — sample sizes too small to be meaningful.

---

## Section 5: Pot Type Comparison

Side-by-side view of how population plays differently in SRP vs 3-Bet pots vs 4-Bet pots:

```
Metric              │   SRP    │  3-Bet   │  4-Bet
────────────────────┼──────────┼──────────┼──────────
Flop C-Bet IP       │  68.2%   │  62.5%   │  55.0%*
Flop C-Bet OOP      │  55.1%   │  48.3%   │  42.0%*
Fold to Flop CB     │  45.3%   │  38.2%   │  32.0%*
Flop XR             │   8.1%   │   6.2%   │   —**
Turn Barrel         │  58.3%   │  52.1%   │  48.0%*
WTSD                │  28.5%   │  32.1%   │  40.5%*
WSD                 │  52.3%   │  55.0%   │  58.2%*
Avg Pot (bb)        │   8.5    │  22.3    │  65.0
Hands reaching flop │ 1.8M    │  180K    │  18K
```

`*` = yellow confidence (moderate sample)
`**` = hidden (insufficient sample)

---

## Section 6: Showdown & Aggression Proxy

### 6a. Showdown Stats by Position

```
           EP    MP    CO    BTN    SB    BB
WTSD %    26.5  28.0  29.5  31.2  30.0  32.5
WSD %     53.0  52.5  54.0  55.2  50.1  48.5
WWSF %    42.0  43.5  46.0  48.2  40.5  38.0
```

### 6b. Aggression as Bluff Proxy

Since we can only see hands at showdown, direct "bluff frequency" cannot be computed. Instead, we use proxy metrics:

| Proxy Metric | Definition | What it tells us |
|-------------|------------|------------------|
| **Bet frequency** | % of actions that are bets/raises (per street) | Higher = more bluffs likely |
| **AF (Aggression Factor)** | (bets + raises) / calls per street | General aggression tendency |
| **AFq (Aggression Frequency)** | (bets + raises) / all actions per street | Normalized aggression |
| **Bet-to-showdown ratio** | % of river bets that go to showdown | Lower = more fold equity / bluffs fold |
| **Showdown bluff %** | % of showdown hands where bettor had < top pair | Direct bluff measurement (showdown-only sample) |

Display per street (flop/turn/river) and by pot type:
```
                   Flop    Turn    River
AF (SRP)           2.1     1.8     1.5
AF (3-Bet pot)     1.9     1.6     1.3
AFq (SRP)          42.0%   38.5%   35.0%
AFq (3-Bet pot)    38.5%   35.0%   32.0%
```

**Showdown bluff % (river only)**:
```
                    SRP     3-Bet
Bluff % at SD       22.5%   18.0%
Value % at SD       77.5%   82.0%
Sample              12,000   3,500
```

Caveat shown in UI: "Bluff % measured at showdown only — actual bluff frequency is higher since successful bluffs don't reach showdown."

---

## Shared Utilities (with Stats v2 — see PRD_STATS_V2.md)

### Board Texture Classification

Shared Python utility used by both Stats v2 detail panels and Population Analysis.

#### Flop Classification

```python
def classify_flop(cards: list[str]) -> FlopTexture:
    """
    Returns FlopTexture with:
      - rank_structure: ABB|ABx|Axx|BBB|BBx|Bxx|MHC|MHD|LC|LD
      - suit_structure: monotone|two_tone|rainbow
      - paired: bool
    """
```

Definitions:
- **Broadway** = T, J, Q, K (not Ace — Ace is treated separately as a premium card)
- **Connected** = at least 2 cards within rank gap <= 2 (e.g. 8-7, T-8, 9-7)
- **Mid-High** = highest card is T or 9 (no broadway, no ace)
- **Low** = highest card is 8 or below

#### Turn Classification

```python
def classify_turn_card(turn_card: str, flop_cards: list[str]) -> TurnTexture:
    """
    Returns TurnTexture with:
      - category: completed_draw|draw_adding|overcard|paired_board|brick
    """
```

#### River Classification

```python
def classify_river_card(river_card: str, board_cards: list[str]) -> RiverTexture:
    """
    Same categories as turn classification, applied to the 4-card board -> 5-card board transition.
    """
```

### Bet Sizing Extraction

Precomputed `pot_before_action` and `bet_pct_pot` columns on the `actions` table. See PRD_STATS_V2.md for details.

---

## Backend API

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/population/preflop` | Preflop position matrices, sizing, 4bet/5bet stats |
| GET | `/api/population/postflop` | Flop/turn/river line frequencies, sizing distributions |
| GET | `/api/population/board-textures` | Stats broken down by board texture categories |
| GET | `/api/population/pot-types` | SRP vs 3-bet vs 4-bet pot comparison |
| GET | `/api/population/showdown` | Showdown stats, aggression proxies, bluff frequencies |
| GET | `/api/population/overview` | Summary: player count, observation count, date range |

All endpoints accept query params: `stakes`, `date_from`, `date_to`, `min_hands_per_player`

### Query Architecture

Population queries are fundamentally different from hero stats:

- **Hero stats**: Filter `WHERE player = hero`, compute per-hand flags
- **Population stats**: Aggregate across `WHERE player != hero`, group by position/texture/pot-type

Key patterns:
- Preflop matrices: `GROUP BY opener_position, responder_position`
- Board texture: JOIN `hand_players` with `board_cards`, classify texture in SQL or app layer
- Sizing: JOIN with `actions` table, compute `amount / pot_at_action` ratios

**Performance consideration**: Population queries scan all player-hand records. For 1M+ hero hands (6M+ observations), need:
- Appropriate DuckDB indexes on `hand_players(position, stakes)` and `hands(played_at)`
- Board texture classification should be **precomputed and stored** (column on `hands` table) rather than computed on every query
- Sizing ratios should be **precomputed on `actions` table** (pot_at_action column)
- Consider materialized aggregation tables for the heaviest queries

### New Database Columns

```sql
-- On hands table: precomputed board texture
ALTER TABLE hands ADD COLUMN flop_texture_rank VARCHAR;   -- ABB, ABx, Axx, BBB, BBx, Bxx, MHC, MHD, LC, LD
ALTER TABLE hands ADD COLUMN flop_texture_suit VARCHAR;   -- monotone, two_tone, rainbow
ALTER TABLE hands ADD COLUMN flop_paired BOOLEAN;
ALTER TABLE hands ADD COLUMN turn_texture VARCHAR;         -- completed_draw, draw_adding, overcard, paired_board, brick
ALTER TABLE hands ADD COLUMN river_texture VARCHAR;        -- same categories

-- On actions table: pot context at time of action
ALTER TABLE actions ADD COLUMN pot_before_action DECIMAL;  -- pot size before this action
ALTER TABLE actions ADD COLUMN bet_pct_pot DECIMAL;        -- amount / pot_before_action (for bets/raises)

-- On hand_players table: pot type flag
ALTER TABLE hand_players ADD COLUMN pot_type VARCHAR;      -- srp, 3bet, 4bet, 5bet
```

---

## Frontend Components

```
PopulationPage.tsx
├── PopulationFilterBar.tsx (stakes, dates, min hands, exclude hero toggle)
├── PopulationOverview.tsx (player count, observation count, date range)
├── PreflopSection/
│   ├── PositionMatrix.tsx (reusable 6x6 heatmap grid)
│   ├── OpenRaiseSizing.tsx
│   └── FourBetFiveBet.tsx
├── FlopSection/
│   ├── FlopLineFrequencies.tsx (SRP/3BP x IP/OOP table)
│   ├── FlopBoardTexture.tsx (texture breakdown table)
│   └── FlopSizing.tsx
├── TurnSection/
│   ├── TurnLineFrequencies.tsx
│   ├── TurnTexture.tsx
│   └── TurnSizing.tsx
├── RiverSection/
│   ├── RiverLineFrequencies.tsx
│   └── RiverSizing.tsx
├── PotTypeComparison.tsx (SRP vs 3BP vs 4BP side-by-side)
└── ShowdownAggression/
    ├── ShowdownByPosition.tsx
    └── AggressionProxy.tsx
```

### Shared Components (between Stats v2 and Population)
- `ConfidenceBadge.tsx` — green/yellow/red dot based on sample size
- `BoardTextureTable.tsx` — texture breakdown table with sortable columns
- `SizingDistribution.tsx` — horizontal bar chart for sizing buckets
- `PositionMatrix.tsx` — 6x6 heatmap grid (used for preflop matrices)

---

## Implementation Phases

### Phase P1: Infrastructure + Preflop
- Build board texture classifier utility (Python)
- Add precomputed columns to schema (flop_texture, turn_texture, pot_type, pot_before_action)
- Backfill via `/api/import/rebuild`
- Build `/api/population/preflop` endpoint
- Build Position Matrix component
- Build Open Raise Sizing + 4-Bet/5-Bet tables

### Phase P2: Flop Analysis
- Build `/api/population/postflop` for flop data
- Build `/api/population/board-textures` for flop texture breakdowns
- Build Flop Line Frequencies, Board Texture, and Sizing components
- Confidence badges throughout

### Phase P3: Turn + River
- Extend postflop endpoint for turn/river data
- Build turn texture classification (relative to flop)
- Build Turn and River sections
- Coarser breakdowns on river (aggregate only)

### Phase P4: Pot Type Comparison + Showdown
- Build `/api/population/pot-types` endpoint
- Build pot type comparison table
- Build showdown stats + aggression proxy metrics
- Showdown bluff % calculation (showdown-only sample with caveat)

### Phase P5: Polish
- Loading skeletons for heavy queries
- Collapsible sections with persistence
- Export to CSV/clipboard for key tables
- Tooltips explaining each metric
- Statistical confidence framework (green/yellow/red badges everywhere)

---

## Open Questions

1. **Board texture computation timing**: Classify during insert (in `insert_parsed_hand`) or as a separate backfill step? Insert-time is cleaner for new hands, but we need backfill for existing data regardless.
2. **Pot size tracking granularity**: Track pot_before_action on every action (expensive storage for 6M+ action rows), or only on bet/raise actions (smaller but still covers sizing analysis)?
3. **Population query caching**: For 6M+ record aggregations, should we precompute aggregate tables (materialized views) on import, or rely on DuckDB's analytical query speed? DuckDB is columnar and fast, but UI responsiveness matters.
4. **Min hands per player filter**: Should this filter at query time (flexible but slower) or precompute player-level aggregates and filter (faster but less flexible)?
