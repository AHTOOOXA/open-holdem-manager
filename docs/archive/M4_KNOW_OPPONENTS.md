# Milestone 4: "The App That Knows Your Opponents"

> **Goal**: Turn the hand history database into an opponent intelligence system.
> **Coaching parallel**: Live Sweat (opponent reads), Population Analysis, Exploit Development.
> **Impact**: Medium. Prerequisite for advanced play improvement.

---

## 1. Research

### What Coaching Sessions This Milestone Serves

This milestone supports three coaching session types that depend on opponent data:

**1. Live Sweat / Opponent Reads**
During a live sweat session, the coach watches the student play in real time and provides guidance on reading opponents. The coach looks at HUD stats (VPIP/PFR/3-Bet/Fold-to-3-Bet/C-Bet/WTSD) and translates them into player profiles and exploit strategies. Without a HUD (GGPoker bans them), the next best thing is a searchable player database where the student can look up any opponent between hands and see their tendencies.

Key coach behaviors during live sweat:
- Glance at opponent stats before making a decision
- Categorize opponents instantly: "This guy is a nit, we can steal his blinds" or "This is a fish, don't bluff him"
- Adjust strategy based on opponent type: value-bet wider vs fish, bluff more vs nits, avoid marginal spots vs LAGs
- Reference head-to-head history: "You've played 200 hands with this guy, he folds to c-bets 70% of the time"

**2. Population Analysis for Exploit Development**
Coaches analyze pool tendencies to develop default strategies. This is how studying populations works in practice:
- "The average NL50 regular folds to 3-bets 62% of the time from CO — you should 3-bet them wider"
- "The pool c-bets the flop 68% IP but only 42% multiway — you should defend wider in HU pots and tighter multiway"
- "On Axx rainbow boards, the population c-bets 72% — you should fold less on these textures"
- "When the pool overbets the river, they have it 65% of the time — make tighter calls"

This is H2N's Range Research feature ($49/mo) that we're democratizing for free. It's one of the most powerful analytical tools in poker because it reveals systematic tendencies across thousands of opponents.

**3. H2N Range Research — The $49/mo Feature We're Democratizing**

Hand2Note Range Research is the gold standard for population analysis in online poker. It provides:
- Aggregate opponent statistics across the entire database
- Position-vs-position breakdowns (how does MP 3-bet vs EP open?)
- Board texture filters (how does the pool play on Axx rainbow vs coordinated boards?)
- Player segmentation (how do fish vs regs differ in key spots?)
- Sizing analysis (what do different bet sizes mean about hand strength?)

H2N charges $49/month for this on top of the base subscription. OHM provides it for free with the same underlying data (hand history database). The advantage: DuckDB's columnar analytics engine is well-suited for the aggregation queries that population analysis requires.

### How Coaches Categorize Opponents

Coaches universally use a VPIP/PFR classification system to quickly categorize opponents. The categories and their strategic implications:

| Type | Shorthand | Profile | Exploit Strategy |
|------|-----------|---------|-----------------|
| **Nit** | NIT | VPIP <18%, PFR <14% | Steal their blinds relentlessly. Fold to their raises/3-bets (they always have it). Never bluff them postflop. |
| **TAG** | TAG | VPIP 18-27%, PFR 14-22% | Standard solid player. Respect their ranges. Look for small edges in 3-bet pots. Exploit positional advantages. |
| **LAG** | LAG | VPIP 27-38%, PFR 20-30% | Tighten up preflop vs their opens. Call down lighter (they bluff more). Trap with strong hands. Avoid light 4-bets. |
| **Recreational / Fish** | REC | VPIP >35%, PFR < VPIP*0.6 | Value bet relentlessly (they call too much). Don't bluff. Bet bigger for value. Isolate them preflop. |
| **Maniac** | MAN | VPIP >38%, PFR >28% | Let them hang themselves. Trap with premiums. Call down lighter. Avoid fancy plays. |

### HUD Stats Coaches Focus On

The stats coaches look at most frequently, in order of importance:

1. **VPIP / PFR** — Instantly reveals player type. The most important two numbers in poker tracking.
2. **3-Bet %** — How aggressively they fight back. Low = only premiums, high = lots of bluffs.
3. **Fold to 3-Bet** — The exploitability stat. Above 65% = print money by 3-betting them.
4. **C-Bet Flop** — Postflop aggression indicator. High = auto-pilot, low = selective.
5. **WTSD / WSD** — Showdown tendencies. High WTSD = calling station. Low = can be bluffed.
6. **AF (Aggression Factor)** — Overall postflop style. <2 = passive, >4 = aggressive.
7. **Fold to Steal** — Blind defense. Above 75% = steal relentlessly.
8. **Hands** — Sample size. Stats from 50 hands mean nothing. 500+ starts to be useful. 2000+ is reliable.

### NoteCaddy-Style Automated Profiling

HM3's NoteCaddy add-on automatically generates notes about opponents based on observed actions. This is a powerful feature we can replicate:

- When an opponent shows down, auto-record: "Open-limped 77 from EP", "Called 3-bet with T9s OOP"
- When patterns emerge, auto-tag: "Limp-calls from EP (seen 5x)", "Never folds to c-bet on A-high boards (0/12)"
- Accumulate over time: the more hands you have with an opponent, the richer their auto-profile becomes

This is planned for future iterations (M4.1 focuses on manual notes + auto-classification, not full auto-note generation).

### Population Analysis for Exploit Development

The core insight behind population analysis: you don't need specific reads on every opponent. If you know how the average player at your stake plays in a given spot, you can develop a default exploit strategy that is profitable against the field.

Examples of population-derived exploits:
- "The pool folds to flop c-bets 52% of the time in SRP IP — we should c-bet any two cards on dry boards"
- "The pool only check-raises the flop 8% of the time — we can discount check-raises and fold less when they do bet"
- "When the pool uses small sizing on the river (<33% pot), they have a value hand 70% of the time — we should fold our bluff catchers"
- "Recreational players fold to steal only 45% — stop blind-stealing against them"
- "The pool c-bets 25% less often in multiway pots — we can float more often HU and fold more multiway"

---

## 2. Product Design

### M4.1: Player Lookup & Search

**What**: Find any player in the database and view their full stat profile with auto player type classification.

**User story**: "As a player preparing for a session, I want to look up frequent opponents and see their tendencies, so I can develop exploit strategies before sitting down."

**User story**: "As a player reviewing a hand, I want to click on a villain's name and see their full stat profile, so I can understand whether their line was standard or unusual for their player type."

#### Player Search & List View

**Search bar**: Type-ahead search by username. Results show as a table with mini-stats:

| Player | Type | Hands | VPIP | PFR | 3-Bet | AF | Last Seen |
|--------|------|-------|------|-----|-------|----|-----------|
| VillainX | TAG | 2,450 | 24.1 | 19.5 | 8.2 | 2.8 | 2 hours ago |
| FishGuy | REC | 890 | 45.2 | 12.0 | 3.1 | 1.2 | 3 days ago |

**Sortable columns**: by hands played (default), VPIP, PFR, last seen, player type.
**Filterable**: by player type (NIT/TAG/LAG/REC/MAN/UNK), by minimum hands.

#### Auto Player Type Classification

Players are auto-classified based on aggregate VPIP and PFR over all observed hands:

| Type | Code | VPIP | PFR | Color | Description |
|------|------|------|-----|-------|-------------|
| **Nit** | NIT | <18% | <14% | Gray | Very tight, only premium hands |
| **TAG** | TAG | 18-27% | 14-22% | Blue | Standard regular, solid range |
| **LAG** | LAG | 27-38% | 20-30% | Orange | Wide range, aggressive |
| **Recreational** | REC | >35% | any, typically PFR < VPIP*0.6 | Green | Loose-passive, calls too much |
| **Maniac** | MAN | >38% | >28% | Red | Very loose and very aggressive |
| **Unknown** | UNK | -- | -- | -- | Not enough hands to classify (<20 hands) |

**Classification logic** (applied in order, first match wins):
1. If hands < 20: UNK
2. If VPIP > 38 and PFR > 28: MAN
3. If VPIP > 35 and PFR < VPIP * 0.6: REC
4. If VPIP > 27 and PFR > 20: LAG
5. If VPIP < 18 and PFR < 14: NIT
6. If VPIP >= 18 and VPIP <= 27 and PFR >= 14 and PFR <= 22: TAG
7. Otherwise: UNK (edge cases that don't fit neatly)

**Storage**: `player_type VARCHAR` column on `players` table. Recomputed after each import batch (after aggregate stats change).

**Badge display**: Colored pill badge next to player name everywhere they appear (hand browser, player list, player profile, search results).

#### Player Profile Page

A dedicated page for any player showing their complete profile. Reuses the stats engine with `player_id` instead of hero.

**Layout**:
```
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back to Players                                                   │
│                                                                      │
│  VillainX                                              [TAG] Blue    │
│  2,450 hands  ·  First seen: 2025-11-15  ·  Last seen: 2 hours ago │
│  Stakes: $0.25/$0.50, $0.50/$1.00                                   │
│                                                                      │
│  [Stats] [Head-to-Head] [Hands] [Notes]                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ Stats Tab ──────────────────────────────────────────────────────┐ │
│  │  Same layout as hero stats page, scoped to this player          │ │
│  │  Preflop / Steal / Postflop / Showdown sections                 │ │
│  │  Positional breakdowns (EP/MP/CO/BTN/SB/BB)                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ Head-to-Head Tab ──────────────────────────────────────────────┐ │
│  │  Your results vs this player:                                    │ │
│  │  Hands: 245  ·  Won: +32.5 BB  ·  bb/100: +13.3                │ │
│  │  By position: EP/MP/CO/BTN/SB/BB breakdown                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ Hands Tab ─────────────────────────────────────────────────────┐ │
│  │  All hands where this player was at the table                    │ │
│  │  Same hand browser component, filtered by player_id             │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌─ Notes Tab ─────────────────────────────────────────────────────┐ │
│  │  Color tag selector: [Gray] [Blue] [Orange] [Green] [Red]       │ │
│  │  Notes textarea: free-form text notes about this player         │ │
│  │  Auto-notes: showdown observations (future)                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### M4.2: Population Analysis Page

A dedicated page for field research -- analyzing the aggregate tendencies of all opponents (the "population" or "pool") across the entire database. This answers the question: "How does the average player at my stake play?"

Unlike hero stats (which track one player's performance), population stats aggregate across all observed player-hand records excluding hero. With N hero hands, we observe ~6N player-hand records (6-max), giving massive sample sizes for aggregate metrics.

The page is organized as a funnel -- broadest/most reliable metrics at the top, progressively more granular (and noisier) sections below, with statistical confidence indicators throughout.

#### Statistical Reliability Framework

Based on a 1M-hand sample in 6-max Zoom:

| Category | Observations | Error Margin | Confidence |
|----------|-------------|--------------|------------|
| Preflop aggregates by position | ~1M per position | < 1% | Excellent |
| Preflop position-vs-position pairs | ~50K-200K per pair | 1-2% | Very good |
| Flop lines in SRP (aggregate) | ~2-2.4M | < 1% | Excellent |
| Flop lines by board texture (5-8 groups) | ~30K-100K per group | 1-3% | Good |
| Flop lines by texture x IP/OOP x pot type | ~5K-20K per cell | 2-5% | Moderate |
| Turn aggregate lines | ~1-1.3M | < 1% | Excellent |
| Turn by board texture (2-3 groups) | ~10K-50K per group | 2-5% | Moderate |
| River aggregate lines | ~600-800K | 1-2% | Good |
| River by texture x line x sizing | Hundreds | 5-15%+ | Noisy |
| 4-bet pots (all postflop) | ~15-25K total | 3-5% | Moderate |
| 4-bet pots by street x texture | Hundreds | Unreliable | Too sparse |
| Showdown-based bluff frequency | Limited to showdown hands | Wide CI | Proxy only |

**Rule**: Every metric cell on the page shows its sample size and a confidence indicator (green/yellow/red dot or background shade based on sample count thresholds).

Sample confidence thresholds:
- **Green** (reliable): >= 1,000 observations
- **Yellow** (directional): 200-999 observations
- **Red** (noisy): < 200 observations
- **Hidden/greyed**: < 50 observations (not shown or greyed out with warning)

#### Page Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  POPULATION ANALYSIS                                                 │
│  [Stakes v] [Date Range < >] [Min Hands/Player: 20 v]              │
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
│  ┌─ PLAYER SEGMENTATION ───────────────────────────────────────┐    │
│  │  NIT / TAG / LAG / REC / MAN side-by-side comparison         │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ SIZING TELLS AT SHOWDOWN ──────────────────────────────────┐    │
│  │  Bet size vs hand strength heatmap per street                 │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ HEADS-UP vs MULTIWAY ─────────────────────────────────────┐    │
│  │  Side-by-side stats for HU vs MW pots                        │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

Each section is collapsible. Sections are ordered top-to-bottom by statistical reliability (most reliable first).

#### Filters

| Filter | Options | Default |
|--------|---------|---------|
| **Stakes** | All / specific stakes | All |
| **Date range** | From/To with presets (Week/Month/3M/6M/Year/All) | All |
| **Min hands per player** | 1 / 10 / 20 / 50 / 100 | 20 |
| **Exclude hero** | Toggle | On (exclude hero by default) |
| **Player type** | All / Recreational / Regular / Nit (see Section 7) | All |
| **Pot players** | All / HU only / Multiway only | All |

**Min hands per player** filters out drive-by players with very few hands -- their stats are noise. At min=20, we filter to regulars + semi-regulars who have played enough to contribute meaningful data.

**Pot players** filters postflop stats to only heads-up pots (2 players saw flop) or multiway pots (3+ players saw flop). Multiway pots play fundamentally differently -- lower cbet%, higher fold-to-cbet%, less bluffing. This filter applies to all postflop sections (Flop/Turn/River/Pot Type).

#### Section 1: Preflop

**1a. Position Matrix -- Open Raise / 3-Bet / Fold-to-3-Bet**

6x6 heatmap grids where rows = opener position, columns = responder position.

Three matrices:

**Open Raise % by Position** (simple 1x6 bar):
```
       EP     MP     CO     BTN    SB     BB
OR%   14.2   18.5   27.3   42.1   38.5    --
       (n)    (n)    (n)    (n)    (n)
```

**3-Bet % Matrix** (position-vs-position):
```
3-Bet %      vs EP   vs MP   vs CO   vs BTN   vs SB
from MP       4.2     --      --      --        --
from CO       5.1     5.8     --      --        --
from BTN      6.3     7.1     8.2     --        --
from SB       7.5     8.0     9.1    10.2       --
from BB       8.1     8.8    10.5    12.3      11.0
```
Color intensity = frequency (darker = higher %). Each cell shows value + sample count.

**Fold to 3-Bet Matrix** (same structure, opener vs 3-bettor position).

**Cold Call % Matrix** (who calls whose opens from which position).

**1b. Open Raise Sizing by Position**

Table showing average open raise sizes and distribution:

```
Position | Avg Size | 2.0x  | 2.2x  | 2.5x  | 3.0x  | Other
---------+----------+-------+-------+-------+-------+------
EP       | 2.42x    |  15%  |  35%  |  40%  |   8%  |  2%
MP       | 2.38x    |  18%  |  38%  |  35%  |   7%  |  2%
CO       | 2.31x    |  22%  |  42%  |  30%  |   4%  |  2%
BTN      | 2.25x    |  30%  |  40%  |  25%  |   3%  |  2%
SB       | 2.55x    |  10%  |  25%  |  45%  |  15%  |  5%
```

**1c. 4-Bet / 5-Bet by Position**

```
           EP    MP    CO    BTN    SB    BB
4-Bet %   1.8   2.1   2.5   3.2   4.1   3.8
F to 4B   62    58    55    52    48    50
5-Bet %   0.3   0.4   0.5   0.6   0.8   0.7
```

**1d. Squeeze / Limp / Cold Call**

Additional preflop population tendencies:
- Squeeze % by position (when facing open + call)
- Limp % by position
- Limp-fold % (limp then fold to raise)
- Cold call vs 3-bet % by position

#### Section 2: Flop

**2a. Main Line Frequencies (Aggregate)**

Split by pot type (SRP vs 3-Bet pot) and position (IP vs OOP):

```
                    SRP              3-Bet Pot
                  IP    OOP        IP     OOP
C-Bet %          68.2  55.1       62.5   48.3
Fold to C-Bet    45.3  52.1       38.2   44.0
Check-Raise %     8.1  10.5        6.2    8.8
Donk Bet %        --    7.3        --     5.1
Probe Bet %       --    --         --     --
```
(Probe = N/A on flop for PFR check scenarios, but included for completeness)

**2b. By Board Texture (H2N-style categories)**

**Flop Texture Classification** (rank structure x suit structure):

Primary axis -- **Rank Structure** (based on card ranks, Broadway = T+):

| Category | Code | Definition | Example |
|----------|------|------------|---------|
| Ace + Broadway + Broadway | ABB | A + 2 broadways | A K J |
| Ace + Broadway + x | ABx | A + 1 broadway + low | A Q 5 |
| Ace + x + x | Axx | A + 2 non-broadway | A 7 3 |
| 3 Broadways (no A) | BBB | 3 broadways, no ace | K Q T |
| 2 Broadways + x (no A) | BBx | 2 broadways + low, no ace | K J 6 |
| 1 Broadway + x + x (no A) | Bxx | 1 broadway + 2 low, no ace | Q 7 3 |
| T-9 High Connected | T-9 Conn | Highest card T or 9, connected (<=2 gap) | T 9 7 |
| T-9 High Disconnected | T-9 Disc | Highest card T or 9, disconnected | T 6 2 |
| 8-2 High Connected | 8-2 Conn | Highest card 8 or lower, connected | 8 7 5 |
| 8-2 High Disconnected | 8-2 Disc | Highest card 8 or lower, disconnected | 8 4 2 |

Secondary axis -- **Suit Structure**:
- **Monocolor** (M): 3 cards same suit
- **2tone** (T): 2 cards same suit (flush draw possible)
- **Rainbow** (R): all different suits

Tertiary axis -- **Pairing** (overlay, cross-cuts rank categories):
- **Paired** (P): 2+ cards same rank
- **Unpaired** (U): all different ranks

**Display**: Table with texture category rows, showing C-Bet %, Fold-to-CBet %, XR %, average sizing for each. Grouped by rank structure with suit/pairing as sub-rows or filterable.

Example:
```
Texture        | C-Bet%| Avg Size| F to CB|  XR% | Sample
---------------+-------+---------+--------+------+-------
Axx Rainbow    |  72.1 |  33%pot |  48.3  |  6.2 | 45,230
Axx 2tone      |  65.3 |  40%pot |  44.1  |  8.5 | 52,100
ABx Rainbow    |  58.2 |  50%pot |  42.0  |  9.1 | 38,400
BBB            |  51.0 |  55%pot |  38.5  | 12.3 | 12,800
8-2 Conn       |  55.8 |  52%pot |  40.2  | 11.5 | 28,900
Monocolor      |  48.5 |  35%pot |  35.0  | 14.2 | 18,600
Paired         |  60.3 |  45%pot |  46.1  |  7.8 | 22,300
...
```

**2c. Sizing Distribution on Flop**

By pot type (SRP / 3-Bet):

```
C-Bet Size     | SRP IP | SRP OOP | 3BP IP | 3BP OOP
---------------+--------+---------+--------+--------
< 33% pot      |  42.1  |  38.5   |  55.2  |  48.0
33-50% pot     |  35.2  |  33.0   |  28.1  |  30.5
50-75% pot     |  18.3  |  22.1   |  12.0  |  16.2
75-100% pot    |   3.5  |   5.0   |   3.8  |   4.5
> 100% (OB)    |   0.9  |   1.4   |   0.9  |   0.8
Avg % pot      |  38.2  |  42.0   |  33.5  |  37.1
```

#### Section 3: Turn

**3a. Main Line Frequencies**

```
                      SRP              3-Bet Pot
                    IP    OOP        IP     OOP
Double Barrel %    58.3  45.2       52.1   40.5
Fold to 2nd Barrel 42.0  48.3       38.5   43.0
Check-Raise %       5.5   7.2        4.8    6.5
Probe Bet %        32.1  28.5       35.2   30.0
Delayed C-Bet %    42.0  35.5       38.0   32.0
```

**3b. By Board Texture (Coarser -- 2-3 Groups)**

Turn texture is classified by what the turn card brought relative to the flop:

| Category | Definition | Example |
|----------|------------|---------|
| **Completed draw** | Turn brings 3rd flush card, or completes obvious straight | Flop: 8 7 2, Turn: 6 |
| **Draw-adding** | Turn brings 2nd flush card, or adds straight potential | Flop: K 7 2, Turn: 8 |
| **Overcard** | Turn is highest card on board | Flop: 9 7 2, Turn: K |
| **Paired board** | Turn pairs one of the flop cards | Flop: K 7 2, Turn: 7 |
| **Brick** | Low, unconnected, doesn't change texture | Flop: A K 7, Turn: 3 |

Show barrel %, fold-to-barrel, XR, probe for each turn category.

**3c. Sizing Distribution on Turn**

Same format as flop sizing, grouped by pot type and position.

#### Section 4: River

**4a. Aggregate Lines Only**

```
                      SRP              3-Bet Pot
                    IP    OOP        IP     OOP
Triple Barrel %    38.5  30.2       35.0   28.1
Fold to 3rd Barrel 48.2  52.0       44.5   48.3
Probe Bet %        28.0  25.1       30.2   26.5
Bet Frequency      42.3  35.5       40.1   33.0
```

**4b. Sizing Distribution on River**

```
River Bet Size   | SRP IP | SRP OOP | 3BP IP | 3BP OOP
-----------------+--------+---------+--------+--------
< 33% pot        |  18.5  |  15.2   |  20.1  |  17.5
33-50% pot       |  28.3  |  25.0   |  25.5  |  23.0
50-75% pot       |  30.1  |  32.5   |  28.0  |  30.2
75-100% pot      |  15.0  |  18.0   |  16.5  |  19.0
> 100% (OB)      |   8.1  |   9.3   |   9.9  |  10.3
Avg % pot        |  55.2  |  60.1   |  53.0  |  58.5
```

**Note**: No board texture breakdown on river -- sample sizes too small to be meaningful.

#### Section 5: Pot Type Comparison

Side-by-side view of how population plays differently in SRP vs 3-Bet pots vs 4-Bet pots:

```
Metric              |   SRP    |  3-Bet   |  4-Bet
--------------------+----------+----------+----------
Flop C-Bet IP       |  68.2%   |  62.5%   |  55.0%*
Flop C-Bet OOP      |  55.1%   |  48.3%   |  42.0%*
Fold to Flop CB     |  45.3%   |  38.2%   |  32.0%*
Flop XR             |   8.1%   |   6.2%   |   --**
Turn Barrel         |  58.3%   |  52.1%   |  48.0%*
WTSD                |  28.5%   |  32.1%   |  40.5%*
WSD                 |  52.3%   |  55.0%   |  58.2%*
Avg Pot (bb)        |   8.5    |  22.3    |  65.0
Hands reaching flop | 1.8M    |  180K    |  18K
```

`*` = yellow confidence (moderate sample)
`**` = hidden (insufficient sample)

#### Section 6: Showdown & Aggression Proxy

**6a. Showdown Stats by Position**

```
           EP    MP    CO    BTN    SB    BB
WTSD %    26.5  28.0  29.5  31.2  30.0  32.5
WSD %     53.0  52.5  54.0  55.2  50.1  48.5
WWSF %    42.0  43.5  46.0  48.2  40.5  38.0
```

**6b. Aggression as Bluff Proxy**

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

Caveat shown in UI: "Bluff % measured at showdown only -- actual bluff frequency is higher since successful bluffs don't reach showdown."

#### Section 7: Player Segmentation

Instead of treating the pool as one homogeneous group, segment players by type based on preflop tendencies. This reveals how different player populations behave differently.

**Player Type Classification**: Same thresholds as M4.1 (NIT/TAG/LAG/REC/MAN/UNK).

**Comparison Table**:

```
Metric         |  All  |  NIT  |  TAG  |  LAG  |  REC  |  MAN
---------------+-------+-------+-------+-------+-------+------
Players        | 8,432 | 1,205 | 3,150 |   890 | 2,800 |   387
VPIP           |  28.5 |  14.2 |  22.0 |  32.5 |  42.1 |  45.0
PFR            |  20.1 |  11.5 |  18.2 |  26.0 |  15.5 |  35.0
3-Bet          |   7.2 |   4.5 |   7.0 |  10.5 |   4.0 |  12.5
Fold to 3-Bet  |  58.0 |  72.0 |  60.0 |  48.0 |  45.0 |  35.0
Flop CBet      |  62.0 |  70.0 |  65.0 |  58.0 |  48.0 |  55.0
WTSD           |  29.5 |  24.0 |  28.0 |  30.5 |  35.0 |  38.0
WSD            |  52.0 |  58.0 |  55.0 |  52.0 |  45.0 |  42.0
```

Each section on the population page can be segmented by player type using the filter dropdown. When a player type is selected, all stats are recalculated for only that segment.

#### Section 8: Sizing Tells at Showdown

Analyzes the relationship between bet sizing and hand strength at showdown. Answers the question: "When the pool bets small vs large, what do they actually have?"

This is inspired by H2N's ProTools Scatter analysis.

**Display**: For each street and pot type, show a sizing vs strength matrix:

```
River Bet Size    | Nuts+ | Strong | Top Pair | Marginal | Draw |  Air  | Sample
------------------+-------+--------+----------+----------+------+-------+-------
< 33% pot         |  12%  |  25%   |   30%    |   18%    |  5%  |  10%  | 2,500
33-50% pot        |  18%  |  28%   |   25%    |   12%    |  8%  |   9%  | 3,800
50-75% pot        |  22%  |  30%   |   22%    |    8%    |  6%  |  12%  | 4,200
75-100% pot       |  30%  |  25%   |   18%    |    5%    |  4%  |  18%  | 1,800
> 100% (overbet)  |  35%  |  20%   |   10%    |    3%    |  2%  |  30%  |   900
```

Hand strength categories use composite groups: Nuts+, Strong, Top Pair, Marginal Made, Draw Only, Air.

**Key Insights This Reveals**:
- **Polarization patterns**: Do overbets correlate with nuts or air (polarized) vs medium sizing with value?
- **Sizing tells**: Does the pool use different sizes for bluffs vs value?
- **Street-specific patterns**: Pool might be balanced on flop but exploitable on river
- **Pot type differences**: SRP sizing tells vs 3-bet pot sizing tells

**Limitations**:
- **Showdown-only data**: Only hands that reached showdown contribute, creating selection bias (folded hands = unknown strength)
- **Sample requirements**: Need meaningful sample per sizing bucket per street -- noisy on river in 3-bet pots
- Show confidence badges; grey out cells with < 100 observations

#### Section 9: Heads-Up vs Multiway Comparison

Side-by-side view showing how the population plays differently when heads-up vs in multiway pots.

**Display**:

```
Metric              |    HU     |  Multiway  |  Difference
--------------------+-----------+------------+------------
% of flop pots      |   72.0%   |   28.0%    |
Flop C-Bet IP       |   68.2%   |   42.5%    |   -25.7%
Flop C-Bet OOP      |   55.1%   |   30.2%    |   -24.9%
Fold to Flop CB     |   45.3%   |   55.8%    |   +10.5%
Flop Check-Raise    |    8.1%   |   10.5%    |    +2.4%
Turn Barrel         |   58.3%   |   38.0%    |   -20.3%
WTSD                |   28.5%   |   25.0%    |    -3.5%
WSD                 |   52.3%   |   48.0%    |    -4.3%
Avg Pot (bb)        |    8.5    |   12.3     |    +3.8
```

### M4.3: Hero vs. Population Comparison

**What**: Overlay hero stats against population averages. "How does my play differ from the field?"

**User story**: "As a player studying my game, I want to see how my stats compare to the population average, so I can identify where I deviate from the field -- either exploitably (a leak) or intentionally (an exploit I'm running)."

This bridges the Leak Finder (Milestone 1) with Population Analysis (Milestone 4):
- Stat health indicators can compare against **population norms** (not just theoretical benchmarks)
- Show where hero deviates from the pool -- sometimes deviation is good (exploiting pool tendencies), sometimes it's a leak

**Display**: Add a "vs. Pool" column to the stats table. Or toggle between "vs. Benchmark" and "vs. Population" coloring modes.

```
Stat              Hero    Pool    Diff     Note
VPIP              24.1    28.5   -4.4pp   Tighter than field (intentional)
PFR               19.5    20.1   -0.6pp   Similar
3-Bet              8.2     7.2   +1.0pp   More aggressive (good)
Fold to 3-Bet     72.1    58.0  +14.1pp   Much higher than field (leak!)
Flop C-Bet        67.5    62.0   +5.5pp   Slightly more frequent
WTSD              29.0    29.5   -0.5pp   Similar
```

---

## 3. UI/UX Design

### Player Search + List View

**Route**: `/players`

```
┌──────────────────────────────────────────────────────────────────────┐
│  PLAYERS                                                             │
│                                                                      │
│  [Search players...________________________] [Type: All v] [Min: 20]│
│                                                                      │
│  8,432 players found                                                │
│                                                                      │
│  Player          Type   Hands   VPIP   PFR   3-Bet   AF    Last    │
│  ─────────────────────────────────────────────────────────────────── │
│  VillainX        [TAG]  2,450   24.1   19.5   8.2   2.8   2h ago  │
│  FishGuy         [REC]    890   45.2   12.0   3.1   1.2   3d ago  │
│  TightNit42      [NIT]  1,200   14.5   11.2   4.0   3.2   1d ago  │
│  AggroManiac     [MAN]    340   48.0   35.2  15.0   4.5   5d ago  │
│  RegularJoe      [TAG]  5,100   22.8   18.0   7.5   2.5   4h ago  │
│  ...                                                                │
│                                                                      │
│  [1] [2] [3] ... [85]                                               │
└──────────────────────────────────────────────────────────────────────┘
```

**Clicking a row** navigates to `/players/{id}` (player profile page).

### Player Profile Page Layout

**Route**: `/players/{id}`

```
┌──────────────────────────────────────────────────────────────────────┐
│  < Back to Players                                                   │
│                                                                      │
│  VillainX                                              [TAG] Blue    │
│  2,450 hands  ·  First: 2025-11-15  ·  Last: 2h ago                │
│  Stakes: $0.25/$0.50, $0.50/$1.00                                   │
│                                                                      │
│  ┌────────┬──────────────┬────────┬────────┐                        │
│  │ Stats  │ Head-to-Head │ Hands  │ Notes  │  <- tabs               │
│  └────────┴──────────────┴────────┴────────┘                        │
│                                                                      │
│  ── Stats Tab ──────────────────────────────────────────────────     │
│                                                                      │
│  PRE-FLOP          Total  EP   MP   CO   BTN  SB   BB               │
│  Open Raise          22   14   17   25   38   35    --               │
│  Fold to 3Bet        60   55   52   58   65   68    --               │
│  3-Bet              7.5    4    5    7    9   10    8                │
│  ...                                                                │
│                                                                      │
│  POSTFLOP                  Flop  Turn  River                        │
│  C-Bet                       62    55     48                        │
│  Fold to C-Bet               48    45     38                        │
│  Aggression                 2.5   2.2    1.8                        │
│  ...                                                                │
│                                                                      │
│  SHOWDOWN                                                           │
│  WTSD  28%  ·  WSD  54%  ·  WWSF  46%                             │
│                                                                      │
│  ── Head-to-Head Tab ───────────────────────────────────────────    │
│                                                                      │
│  Your results vs VillainX:                                          │
│  Hands: 245  ·  Won: +32.5 BB  ·  bb/100: +13.3                   │
│                                                                      │
│  Position    Hands  Won (BB)  bb/100                                │
│  EP            18     -5.2    -28.9                                  │
│  MP            22     +8.0    +36.4                                  │
│  CO            35    +12.5    +35.7                                  │
│  BTN           52    +22.0    +42.3                                  │
│  SB            58     -8.5    -14.7                                  │
│  BB            60     +3.7     +6.2                                  │
│                                                                      │
│  ── Notes Tab ──────────────────────────────────────────────────    │
│                                                                      │
│  Color:  ( ) Gray  (x) Blue  ( ) Orange  ( ) Green  ( ) Red        │
│                                                                      │
│  Notes:                                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ TAG reg, standard lines. Folds to 3-bets too much from CO.  │   │
│  │ Bet small on river for value, large sizes are usually bluff. │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  [Save]                                                              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Population Page Layout

**Route**: `/population`

The full page layout is shown in the M4.2 section above. Key design elements:

- **Filter bar** (sticky at top): Stakes, Date Range, Min Hands/Player, Exclude Hero, Player Type, Pot Players
- **Overview header**: Pool size (unique players) + total observations
- **9 collapsible sections**, ordered by reliability (most reliable at top)
- Each section has a collapse/expand toggle
- Sections default to expanded on first load, remember collapsed state

### Position Matrix Heatmap Design

The 6x6 position matrix is the signature UI component of the population page. Design spec:

```
┌─────────────────────────────────────────────────┐
│  3-BET % MATRIX                                  │
│                                                   │
│           vs EP   vs MP   vs CO   vs BTN  vs SB  │
│  from MP  ┌─────┐                                │
│           │ 4.2 │  --     --      --      --     │
│           │ 12K │                                 │
│           └─────┘                                │
│  from CO  ┌─────┐ ┌─────┐                        │
│           │ 5.1 │ │ 5.8 │  --     --      --     │
│           │ 15K │ │ 18K │                        │
│           └─────┘ └─────┘                        │
│  from BTN ┌─────┐ ┌─────┐ ┌─────┐               │
│           │ 6.3 │ │ 7.1 │ │ 8.2 │  --     --    │
│           │ 20K │ │ 22K │ │ 35K │               │
│           └─────┘ └─────┘ └─────┘               │
│  ...                                              │
│                                                   │
│  Color: lighter = lower %, darker = higher %      │
└─────────────────────────────────────────────────┘
```

- Each cell shows the stat value (top) and sample count (bottom, smaller text)
- Background color intensity scales with the value (heatmap gradient)
- Cells with <50 observations are greyed out
- Cells with <200 observations have yellow background
- Cells with 200-999 observations show normally
- Cells with 1000+ observations have full color intensity

### Confidence Badge Design

Three visual states for sample size indicators:

```
Green (>= 1,000):   ● 68.2%   (solid green dot, full opacity)
Yellow (200-999):    ◐ 55.0%   (half-filled yellow dot, slightly faded)
Red (< 200):         ○ 42.0%   (hollow red dot, faded)
Hidden (< 50):       -- or greyed out cell
```

Alternative: use background tinting on the cell (green tint, yellow tint, red tint at low opacity) rather than dots. Consistent with the benchmark indicator design from M1.1.

### Player Segmentation Comparison Table

The segmentation table shows key stats side-by-side for each player type:

```
┌──────────────────────────────────────────────────────────────────┐
│  PLAYER SEGMENTATION                                              │
│                                                                    │
│  Metric         |  All  |  NIT  |  TAG  |  LAG  |  REC  |  MAN  │
│  ───────────────+───────+───────+───────+───────+───────+──────  │
│  Players        | 8,432 | 1,205 | 3,150 |   890 | 2,800 |   387 │
│  VPIP           |  28.5 |  14.2 |  22.0 |  32.5 |  42.1 |  45.0 │
│  PFR            |  20.1 |  11.5 |  18.2 |  26.0 |  15.5 |  35.0 │
│  3-Bet          |   7.2 |   4.5 |   7.0 |  10.5 |   4.0 |  12.5 │
│  Fold to 3-Bet  |  58.0 |  72.0 |  60.0 |  48.0 |  45.0 |  35.0 │
│  Flop CBet      |  62.0 |  70.0 |  65.0 |  58.0 |  48.0 |  55.0 │
│  WTSD           |  29.5 |  24.0 |  28.0 |  30.5 |  35.0 |  38.0 │
│  WSD            |  52.0 |  58.0 |  55.0 |  52.0 |  45.0 |  42.0 │
│                                                                    │
│  Column headers colored by player type color                      │
│  NIT=Gray  TAG=Blue  LAG=Orange  REC=Green  MAN=Red              │
└──────────────────────────────────────────────────────────────────┘
```

### Sizing Tells Heatmap

The sizing tells section uses a heatmap where color intensity represents frequency:

```
┌──────────────────────────────────────────────────────────────────┐
│  SIZING TELLS — River (SRP)                   [Street v] [Pot v] │
│                                                                    │
│  Bet Size       | Nuts+ | Strong | TP   | Marg | Draw | Air     │
│  ───────────────+───────+────────+──────+──────+──────+───────  │
│  < 33% pot      | ░░12  | ▒▒25   | ▓▓30 | ▒▒18 | ░░ 5 | ░░10  │
│  33-50% pot     | ▒▒18  | ▓▓28   | ▒▒25 | ░░12 | ░░ 8 | ░░ 9  │
│  50-75% pot     | ▒▒22  | ▓▓30   | ▒▒22 | ░░ 8 | ░░ 6 | ░░12  │
│  75-100% pot    | ▓▓30  | ▒▒25   | ▒▒18 | ░░ 5 | ░░ 4 | ▒▒18  │
│  > 100% (OB)    | ▓▓35  | ▒▒20   | ░░10 | ░░ 3 | ░░ 2 | ▓▓30  │
│                                                                    │
│  Color intensity = frequency (darker = more common)               │
│  Cells with <100 observations are greyed out                      │
└──────────────────────────────────────────────────────────────────┘
```

### Navigation Structure Changes

Current sidebar:
```
OHM
  Upload
  Stats
  Range
  Results
  Hands
  Cash Drop
```

After M4:
```
OHM

PLAY
  Upload
  Cash Drop

ANALYZE
  Stats
  Range
  Results
  Hands

OPPONENTS           <- NEW section
  Players           <- NEW (M4.1)
  Population        <- NEW (M4.2)
```

The OPPONENTS section appears only after Milestone 4 features are built. The navigation grouping provides clear separation between self-analysis (ANALYZE) and opponent research (OPPONENTS).

---

## 4. Technical Spec

### New API Endpoints

#### M4.1: Player Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/players` | List/search players with mini-stats |
| GET | `/api/players/{id}` | Get player detail (profile info, stakes, first/last seen) |
| GET | `/api/stats/player/{id}` | Full stats for any player (reuse stats engine) |
| GET | `/api/players/{id}/hands` | Hands involving this player |
| GET | `/api/players/{id}/head-to-head` | Hero's results specifically vs this player |
| PATCH | `/api/players/{id}/note` | Update player note text |
| PATCH | `/api/players/{id}/color` | Update player color tag |

**`GET /api/players`** query params:
- `search` (string): username search (LIKE '%search%')
- `player_type` (string): filter by NIT/TAG/LAG/REC/MAN/UNK
- `min_hands` (int, default 20): minimum hands observed
- `sort_by` (string): hands/vpip/pfr/last_seen (default: hands)
- `sort_dir` (string): asc/desc (default: desc)
- `page` (int, default 1)
- `page_size` (int, default 50)

**`GET /api/stats/player/{id}`** query params:
- Same as `/api/stats/hero` (position, stakes, date_from, date_to)
- Internally calls the same stats engine with `player_id` parameter instead of hero

**`GET /api/players/{id}/head-to-head`** response:
```json
{
  "opponent_id": 42,
  "opponent_name": "VillainX",
  "total_hands": 245,
  "won_bb": 32.5,
  "bb_per_100": 13.3,
  "by_position": [
    { "position": "EP", "hands": 18, "won_bb": -5.2, "bb_per_100": -28.9 },
    { "position": "MP", "hands": 22, "won_bb": 8.0, "bb_per_100": 36.4 }
  ]
}
```

#### M4.2: Population Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/population/overview` | Summary: player count, observation count, date range |
| GET | `/api/population/preflop` | Preflop position matrices, sizing, 4bet/5bet stats |
| GET | `/api/population/postflop` | Flop/turn/river line frequencies, sizing distributions |
| GET | `/api/population/board-textures` | Stats broken down by board texture categories |
| GET | `/api/population/pot-types` | SRP vs 3-bet vs 4-bet pot comparison |
| GET | `/api/population/showdown` | Showdown stats, aggression proxies, bluff frequencies |
| GET | `/api/population/sizing-tells` | Sizing vs hand strength at showdown (scatter analysis) |
| GET | `/api/population/segments` | Player type comparison table |

All population endpoints accept shared query params:
- `stakes` (string): filter by stakes
- `date_from` / `date_to` (string): date range filter
- `min_hands_per_player` (int, default 20): minimum hands per player
- `player_type` (string): filter to specific player type segment
- `multiway` (string): "all" / "hu" / "multiway" -- filter postflop by pot size
- `exclude_hero` (bool, default true): exclude hero from aggregation

**`GET /api/population/preflop`** response structure:
```json
{
  "open_raise_by_position": {
    "EP": { "pct": 14.2, "sample": 1050000 },
    "MP": { "pct": 18.5, "sample": 1050000 }
  },
  "three_bet_matrix": {
    "MP_vs_EP": { "pct": 4.2, "sample": 12000 },
    "CO_vs_EP": { "pct": 5.1, "sample": 15000 }
  },
  "fold_to_3bet_matrix": {},
  "cold_call_matrix": {},
  "open_raise_sizing": {
    "EP": { "avg": 2.42, "distribution": { "2.0x": 15, "2.2x": 35 } }
  },
  "four_bet_by_position": {},
  "five_bet_by_position": {},
  "squeeze_by_position": {},
  "limp_by_position": {}
}
```

**`GET /api/population/postflop`** query params (additional):
- `street` (string): "flop" / "turn" / "river" (required)
- `pot_type` (string): "srp" / "3bet" / "4bet" (optional, default all)

**`GET /api/population/board-textures`** query params (additional):
- `street` (string): "flop" / "turn" (required)
- `texture_rank` (string): filter to specific rank category
- `texture_suit` (string): filter to specific suit structure

**`GET /api/population/sizing-tells`** query params (additional):
- `street` (string): "flop" / "turn" / "river" (required)
- `pot_type` (string): "srp" / "3bet" (optional)

#### M4.3: Hero vs. Population

No new endpoint needed. Frontend queries both `/api/stats/hero` and `/api/population/preflop` + `/api/population/postflop` + `/api/population/showdown`, then computes diffs.

### New Database Columns

```sql
-- On hands table: precomputed board texture
ALTER TABLE hands ADD COLUMN flop_texture_rank VARCHAR;   -- ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc
ALTER TABLE hands ADD COLUMN flop_texture_suit VARCHAR;   -- monocolor, 2tone, rainbow
ALTER TABLE hands ADD COLUMN flop_paired BOOLEAN;
ALTER TABLE hands ADD COLUMN turn_texture VARCHAR;         -- completed_draw, draw_adding, overcard, paired_board, brick
ALTER TABLE hands ADD COLUMN river_texture VARCHAR;        -- same categories

-- On actions table: pot context at time of action
ALTER TABLE actions ADD COLUMN pot_before_action DECIMAL;  -- pot size before this action
ALTER TABLE actions ADD COLUMN bet_pct_pot DECIMAL;        -- amount / pot_before_action (for bets/raises)

-- On hand_players table: pot type and multiway flag
ALTER TABLE hand_players ADD COLUMN pot_type VARCHAR;      -- srp, 3bet, 4bet, 5bet
ALTER TABLE hand_players ADD COLUMN is_multiway BOOLEAN;   -- true if 3+ players saw flop

-- On players table: player type classification
ALTER TABLE players ADD COLUMN player_type VARCHAR;        -- NIT, TAG, LAG, REC, MAN, UNK
```

### Player Type Classification Logic

```python
def classify_player(vpip: float, pfr: float, hands: int, min_hands: int = 20) -> str:
    """Classify a player based on aggregate VPIP/PFR.

    Applied in order -- first match wins.
    Returns one of: NIT, TAG, LAG, REC, MAN, UNK.
    """
    if hands < min_hands:
        return "UNK"
    if vpip > 38 and pfr > 28:
        return "MAN"
    if vpip > 35 and pfr < vpip * 0.6:
        return "REC"
    if vpip > 27 and pfr > 20:
        return "LAG"
    if vpip < 18 and pfr < 14:
        return "NIT"
    if 18 <= vpip <= 27 and 14 <= pfr <= 22:
        return "TAG"
    return "UNK"
```

**When to recompute**: After each import batch, in `finalize_import()`. Query aggregate VPIP/PFR per player from `hand_players`, then batch-update `players.player_type`.

```python
def update_player_types(db):
    """Recompute player_type for all players based on aggregate stats."""
    db.execute("""
        UPDATE players SET player_type = CASE
            WHEN agg.hands < 20 THEN 'UNK'
            WHEN agg.vpip > 38 AND agg.pfr > 28 THEN 'MAN'
            WHEN agg.vpip > 35 AND agg.pfr < agg.vpip * 0.6 THEN 'REC'
            WHEN agg.vpip > 27 AND agg.pfr > 20 THEN 'LAG'
            WHEN agg.vpip < 18 AND agg.pfr < 14 THEN 'NIT'
            WHEN agg.vpip BETWEEN 18 AND 27 AND agg.pfr BETWEEN 14 AND 22 THEN 'TAG'
            ELSE 'UNK'
        END
        FROM (
            SELECT
                player_id,
                COUNT(*) as hands,
                AVG(CASE WHEN vpip THEN 1.0 ELSE 0.0 END) * 100 as vpip,
                AVG(CASE WHEN pfr THEN 1.0 ELSE 0.0 END) * 100 as pfr
            FROM hand_players
            GROUP BY player_id
        ) agg
        WHERE players.id = agg.player_id
    """)
```

### Population Query Architecture

Population queries are fundamentally different from hero stats:

- **Hero stats**: Filter `WHERE player_id = hero_id`, compute per-hand flags
- **Population stats**: Aggregate across `WHERE player_id != hero_id`, group by position/texture/pot-type

Key query patterns:

**Preflop matrices** -- require position-vs-position grouping:
```sql
-- 3-Bet % matrix: for each opener-responder position pair
SELECT
    opener.position as opener_pos,
    responder.position as responder_pos,
    COUNT(*) FILTER (WHERE responder.three_bet = TRUE) as three_bet_count,
    COUNT(*) FILTER (WHERE responder.three_bet_opp = TRUE) as three_bet_opp,
    CASE WHEN COUNT(*) FILTER (WHERE responder.three_bet_opp = TRUE) > 0
         THEN COUNT(*) FILTER (WHERE responder.three_bet = TRUE) * 100.0
              / COUNT(*) FILTER (WHERE responder.three_bet_opp = TRUE)
         ELSE NULL END as three_bet_pct
FROM hand_players opener
JOIN hand_players responder ON opener.hand_id = responder.hand_id
    AND opener.player_id != responder.player_id
JOIN hands h ON opener.hand_id = h.id
WHERE opener.open_raise = TRUE
    AND responder.player_id != ?  -- exclude hero
GROUP BY opener.position, responder.position
```

**Board texture stats** -- join with precomputed texture columns:
```sql
SELECT
    h.flop_texture_rank,
    h.flop_texture_suit,
    COUNT(*) FILTER (WHERE hp.cbet_flop = TRUE) as cbet_count,
    COUNT(*) FILTER (WHERE hp.cbet_flop_opp = TRUE) as cbet_opp,
    -- ... other stats
FROM hand_players hp
JOIN hands h ON hp.hand_id = h.id
WHERE hp.player_id != ?  -- exclude hero
    AND hp.saw_flop = TRUE
GROUP BY h.flop_texture_rank, h.flop_texture_suit
```

**Sizing analysis** -- join with actions table for sizing buckets:
```sql
SELECT
    CASE
        WHEN a.bet_pct_pot < 0.33 THEN '<33%'
        WHEN a.bet_pct_pot < 0.50 THEN '33-50%'
        WHEN a.bet_pct_pot < 0.75 THEN '50-75%'
        WHEN a.bet_pct_pot < 1.00 THEN '75-100%'
        ELSE '>100%'
    END as size_bucket,
    COUNT(*) as count,
    AVG(a.bet_pct_pot) * 100 as avg_pct
FROM actions a
JOIN hand_players hp ON a.hand_id = hp.hand_id AND a.player_id = hp.player_id
WHERE a.street = 'flop'
    AND a.action_type IN ('bet', 'raise')
    AND hp.player_id != ?  -- exclude hero
    AND a.bet_pct_pot IS NOT NULL
GROUP BY size_bucket
```

### Performance Considerations

For 1M+ hero hands (6M+ observations), population queries scan large datasets. Performance strategy:

1. **DuckDB Indexes**: Add indexes on frequently filtered columns:
```sql
CREATE INDEX idx_hp_position_stakes ON hand_players(position);
CREATE INDEX idx_hands_played_at ON hands(played_at);
CREATE INDEX idx_hands_stakes ON hands(stakes);
CREATE INDEX idx_players_type ON players(player_type);
CREATE INDEX idx_hp_pot_type ON hand_players(pot_type);
```

2. **Precomputed columns**: Board texture classification and pot-before-action are computed at insert time and stored as columns, not computed on every query.

3. **Board texture on `hands` table**: Classify once during `insert_parsed_hand`, store as `flop_texture_rank`, `flop_texture_suit`, `flop_paired`, `turn_texture`, `river_texture`. This avoids recomputing board classification on every population query.

4. **`pot_before_action` on `actions` table**: Computed during insert by tracking running pot through each action. Enables sizing analysis without recomputation.

5. **Player type on `players` table**: Batch-computed after import. Population endpoints filter by player_type without per-query VPIP/PFR aggregation.

6. **Consider materialized aggregation**: If DuckDB query speed becomes an issue for the heaviest queries (position-vs-position matrices across 6M records), precompute aggregate tables and refresh on import. DuckDB is columnar and fast, so this may not be necessary.

7. **`is_multiway` on `hand_players` table**: Computed during insert: count how many players have `saw_flop = TRUE` for the same hand_id. If 3+, all players in that hand get `is_multiway = TRUE`.

8. **`pot_type` on `hand_players` table**: Computed during `insert_parsed_hand` based on preflop action sequence: count how many raises occurred preflop. 1 raise = srp, 2 raises = 3bet, 3 raises = 4bet, 4+ = 5bet.

### Shared Utilities (with Stats v2)

#### Board Texture Classification

Shared Python utility used by both Stats v2 detail panels and Population Analysis.

**Flop Classification**:
```python
def classify_flop(cards: list[str]) -> FlopTexture:
    """
    Returns FlopTexture with:
      - rank_structure: ABB|ABx|Axx|BBB|BBx|Bxx|T-9 Conn|T-9 Disc|8-2 Conn|8-2 Disc
      - suit_structure: monocolor|2tone|rainbow
      - paired: bool
    """
```

Definitions:
- **Broadway** = T, J, Q, K (not Ace -- Ace is treated separately as a premium card)
- **Connected** = at least 2 cards within rank gap <= 2 (e.g. 8-7, T-8, 9-7)
- **T-9 High** = highest card is T or 9 (no broadway, no ace)
- **8-2 High** = highest card is 8 or below

**Turn Classification**:
```python
def classify_turn_card(turn_card: str, flop_cards: list[str]) -> TurnTexture:
    """
    Returns TurnTexture with:
      - category: completed_draw|draw_adding|overcard|paired_board|brick
    """
```

**River Classification**:
```python
def classify_river_card(river_card: str, board_cards: list[str]) -> RiverTexture:
    """
    Same categories as turn classification, applied to the 4-card board -> 5-card board transition.
    """
```

#### Bet Sizing Extraction

Precomputed `pot_before_action` and `bet_pct_pot` columns on the `actions` table. Computed during `insert_parsed_hand` by tracking the running pot through each action.

### Frontend Components

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
├── PlayerSegmentation/
│   ├── SegmentComparison.tsx (side-by-side NIT/TAG/LAG/REC/MAN table)
│   └── PlayerTypeFilter.tsx (dropdown, used in filter bar)
├── SizingTells/
│   └── SizingStrengthMatrix.tsx (sizing bucket x hand strength heatmap)
├── HuVsMultiway/
│   └── HuMwComparison.tsx (side-by-side HU vs MW stats table)
└── ShowdownAggression/
    ├── ShowdownByPosition.tsx
    └── AggressionProxy.tsx

PlayersPage.tsx
├── PlayerSearchBar.tsx
├── PlayerList.tsx (sortable table with mini-stats)
├── PlayerTypeBadge.tsx (colored pill: NIT/TAG/LAG/REC/MAN)
└── PlayerRow.tsx

PlayerProfilePage.tsx
├── PlayerHeader.tsx (name, type badge, hands, first/last seen)
├── PlayerStatsTabs.tsx
│   ├── StatsTab.tsx (reuse StatsPage scoped to player)
│   ├── HeadToHeadTab.tsx (hero vs player results)
│   ├── HandsTab.tsx (hand browser filtered to player)
│   └── NotesTab.tsx (color tag selector + notes textarea)
└── PlayerTypeBadge.tsx (shared)
```

**Shared Components** (between Stats v2 and Population):
- `ConfidenceBadge.tsx` -- green/yellow/red dot based on sample size
- `BoardTextureTable.tsx` -- texture breakdown table with sortable columns
- `SizingDistribution.tsx` -- horizontal bar chart for sizing buckets
- `PositionMatrix.tsx` -- 6x6 heatmap grid (used for preflop matrices)
- `HandStrengthTable.tsx` -- made hand category breakdown table

---

## 5. Execution Plan

### M4.1 Phases: Player Search, Profile, Classification

**Phase M4.1a -- Player Search & List (3-4 days)**:
1. Add `player_type VARCHAR` column to `players` table in schema
2. Implement `classify_player()` utility function
3. Add `update_player_types()` call to `finalize_import()`
4. Build `GET /api/players` endpoint (search, filter, paginate)
5. Build `PlayersPage.tsx` with `PlayerSearchBar`, `PlayerList`, `PlayerTypeBadge`
6. Add `/players` route to App.tsx
7. Add OPPONENTS section to sidebar navigation

**Phase M4.1b -- Player Profile (3-4 days)**:
1. Build `GET /api/players/{id}` endpoint (profile info)
2. Build `GET /api/stats/player/{id}` endpoint (reuse stats engine with player_id param)
3. Build `PlayerProfilePage.tsx` with `PlayerHeader`, `StatsTab`
4. Add `/players/{id}` route
5. Refactor `StatsPage` stat table into a reusable component that accepts a player_id prop

**Phase M4.1c -- Head-to-Head + Notes (2-3 days)**:
1. Build `GET /api/players/{id}/head-to-head` endpoint
2. Build `PATCH /api/players/{id}/note` and `PATCH /api/players/{id}/color` endpoints
3. Build `HeadToHeadTab.tsx` and `NotesTab.tsx`
4. Build `HandsTab.tsx` (reuse hand browser with player_id filter)
5. Wire player name clicks in hand browser to player profile page

**Phase M4.1d -- Classification Polish (1-2 days)**:
1. Add player type badge to hand browser (next to villain names)
2. Add player type badge to hand detail drawer
3. Run classification on existing data via rebuild
4. Verify classification accuracy against manual inspection

**Total M4.1 effort: 10-14 days**

### M4.2 Phases: Population Analysis (P1-P7)

#### Phase P1: Infrastructure + Preflop (5-7 days)
- Build board texture classifier utility (Python): `classify_flop()`, `classify_turn_card()`, `classify_river_card()`
- Add precomputed columns to schema: `flop_texture_rank`, `flop_texture_suit`, `flop_paired`, `turn_texture`, `river_texture` on `hands`; `pot_type`, `is_multiway` on `hand_players`; `pot_before_action`, `bet_pct_pot` on `actions`
- Compute `pot_type` during `insert_parsed_hand` (count preflop raises)
- Compute `is_multiway` during `insert_parsed_hand` (count `saw_flop` per hand)
- Compute board textures during `insert_parsed_hand`
- Compute pot_before_action during `insert_parsed_hand` (track running pot)
- Backfill all via `/api/import/rebuild`
- Build `GET /api/population/overview` endpoint
- Build `GET /api/population/preflop` endpoint
- Build `PopulationPage.tsx` with filter bar and overview
- Build `PositionMatrix.tsx` (reusable 6x6 heatmap grid)
- Build `OpenRaiseSizing.tsx` + `FourBetFiveBet.tsx`
- Add `/population` route

#### Phase P2: Flop Analysis (3-4 days)
- Build `GET /api/population/postflop` for flop data
- Build `GET /api/population/board-textures` for flop texture breakdowns
- Build `FlopLineFrequencies.tsx` (SRP/3BP x IP/OOP table)
- Build `FlopBoardTexture.tsx` (texture breakdown table)
- Build `FlopSizing.tsx` (sizing distribution by pot type and position)
- Build `ConfidenceBadge.tsx` (shared component)
- Confidence badges throughout all flop data

#### Phase P3: Turn + River (3-4 days)
- Extend `/api/population/postflop` for turn/river data
- Build turn texture classification queries (relative to flop)
- Build `TurnLineFrequencies.tsx`, `TurnTexture.tsx`, `TurnSizing.tsx`
- Build `RiverLineFrequencies.tsx`, `RiverSizing.tsx`
- Coarser breakdowns on river (aggregate only, no texture splits)

#### Phase P4: Pot Type Comparison + Showdown (2-3 days)
- Build `GET /api/population/pot-types` endpoint
- Build `PotTypeComparison.tsx` (SRP vs 3BP vs 4BP side-by-side table)
- Build `GET /api/population/showdown` endpoint
- Build `ShowdownByPosition.tsx` (WTSD/WSD/WWSF by position)
- Build `AggressionProxy.tsx` (AF/AFq by street and pot type)
- Build showdown bluff % calculation (showdown-only sample with caveat text)

#### Phase P5: Player Segmentation + HU vs MW (3-4 days)
- Verify player_type classification from M4.1 is working
- Build `GET /api/population/segments` endpoint
- Build `SegmentComparison.tsx` (side-by-side NIT/TAG/LAG/REC/MAN table)
- Build `PlayerTypeFilter.tsx` dropdown for filter bar
- Add `is_multiway` filtering to all population endpoints
- Build `HuMwComparison.tsx` (side-by-side HU vs MW stats, queries population endpoints twice)
- Add `multiway` and `player_type` filters to all population endpoints

#### Phase P6: Sizing Tells (4-5 days)
- Build hand strength evaluator utility (shared with Stats v2): classify made hand + draw flags
- Build `GET /api/population/sizing-tells` endpoint (joins actions + hand_players + board_cards)
- Build `SizingStrengthMatrix.tsx` (sizing bucket x hand strength heatmap)
- Show per street, per pot type, with confidence badges
- Only include hands that went to showdown
- Add caveat text about showdown-only sampling bias

#### Phase P7: Polish (2-3 days)
- Loading skeletons for heavy queries
- Collapsible sections with localStorage persistence
- Export to CSV/clipboard for key tables
- Tooltips explaining each metric
- Statistical confidence framework badges (green/yellow/red) everywhere
- Performance testing and query optimization

**Total M4.2 effort: 22-30 days**

### M4.3: Hero vs. Population Comparison (2-3 days)

**Prerequisites**: M4.2 must be complete (population endpoints).

1. Query hero stats and population stats in parallel
2. Compute diffs (hero value - population value) for all comparable stats
3. Build comparison view: either a "vs. Pool" column on stats page or a toggle mode
4. Color-code diffs: large positive deviation in one color, large negative in another
5. Add toggle between "vs. Benchmark" (M1.1) and "vs. Population" (M4.3) coloring modes
6. Add a brief "Deviation Guide" tooltip explaining when deviation from the pool is good (intentional exploit) vs. bad (leak)

**Total M4.3 effort: 2-3 days**

### Dependencies on Shared Infrastructure

Several components required by M4.2 are shared with the Stats v2 milestone (M2.1c). These should be built once and reused:

| Component | Used By | Build When |
|-----------|---------|------------|
| Board texture classifier | M4.2 (Population board textures), M2.1c (Stats v2 postflop detail) | Phase P1 of M4.2 (or earlier if M2.1c comes first) |
| Pot size tracker (pot_before_action) | M4.2 (Population sizing), M2.1c (Stats v2 sizing) | Phase P1 of M4.2 |
| Hand strength evaluator | M4.2 P6 (Sizing tells), M2.1c (Stats v2 hand strength at action) | Phase P6 of M4.2 |
| Player type classifier | M4.1 (Player lookup), M4.2 (Population segmentation) | Phase M4.1a |
| ConfidenceBadge component | M4.2 (all sections), M2.1c (postflop detail) | Phase P2 of M4.2 |
| PositionMatrix component | M4.2 (preflop matrices) | Phase P1 of M4.2 |

If Milestone 2 (Stats v2) is built before Milestone 4, the board texture classifier, pot tracker, and hand strength evaluator may already exist. If Milestone 4 comes first, build them here and Milestone 2 reuses them.

### Task Breakdown Summary

| Phase | Feature | Effort (days) | Dependencies |
|-------|---------|---------------|--------------|
| M4.1a | Player search & list | 3-4 | None |
| M4.1b | Player profile page | 3-4 | M4.1a |
| M4.1c | Head-to-head + notes | 2-3 | M4.1b |
| M4.1d | Classification polish | 1-2 | M4.1a |
| P1 | Infrastructure + preflop | 5-7 | M4.1a (player_type) |
| P2 | Flop analysis | 3-4 | P1 |
| P3 | Turn + river | 3-4 | P1 |
| P4 | Pot type + showdown | 2-3 | P1 |
| P5 | Segmentation + HU/MW | 3-4 | P1, M4.1a |
| P6 | Sizing tells | 4-5 | P1, hand strength evaluator |
| P7 | Polish | 2-3 | P2-P6 |
| M4.3 | Hero vs. population | 2-3 | P1-P5 |
| **Total** | | **35-46 days** | |

---

## 6. Testing

### Player Type Classification Accuracy

**Unit tests** for `classify_player()`:
- NIT: VPIP=14, PFR=11, hands=500 -> NIT
- TAG: VPIP=23, PFR=19, hands=1000 -> TAG
- LAG: VPIP=32, PFR=25, hands=800 -> LAG
- REC: VPIP=45, PFR=12, hands=300 -> REC (PFR < VPIP*0.6)
- MAN: VPIP=42, PFR=32, hands=200 -> MAN
- UNK (low hands): VPIP=30, PFR=22, hands=15 -> UNK
- Edge case: VPIP=27, PFR=22 (TAG/LAG boundary) -> TAG (inclusive range)
- Edge case: VPIP=36, PFR=30 (REC vs MAN) -> MAN (MAN check comes first)
- Edge case: VPIP=35, PFR=25 -> verify correct classification (REC: PFR=25, VPIP*0.6=21, PFR > VPIP*0.6, so not REC; check LAG: VPIP>27, PFR>20 -> LAG)

**Integration test**: Import 1000+ hands, verify player types are assigned and make sense relative to observed play.

### Population Query Performance Benchmarks

Target response times with sample sizes:

| Query | 50K hands | 500K hands | 5M hands | Target |
|-------|-----------|------------|----------|--------|
| `/population/overview` | <50ms | <100ms | <500ms | <1s |
| `/population/preflop` | <100ms | <200ms | <1s | <2s |
| `/population/postflop` (one street) | <100ms | <200ms | <1s | <2s |
| `/population/board-textures` | <200ms | <500ms | <2s | <3s |
| `/population/sizing-tells` | <200ms | <500ms | <2s | <3s |
| `/population/segments` | <100ms | <200ms | <1s | <2s |

**Test approach**: Measure query times at different database sizes. If targets are exceeded, add indexes or consider materialized aggregation tables.

### Confidence Badge Threshold Verification

**Unit tests** for confidence badge logic:
- Sample >= 1000: green badge
- Sample 200-999: yellow badge
- Sample 50-199: red badge
- Sample < 50: hidden/greyed out
- Sample = 0: hidden
- Boundary values: 50, 199, 200, 999, 1000

**Visual QA**: Import a real hand history (13k+ hands) and verify:
- Preflop aggregate stats show green badges (high sample)
- Position-vs-position matrix cells show appropriate mix (green for common pairs, yellow/red for rare pairs)
- River texture stats show red/hidden badges (low sample)
- 4-bet pot stats show yellow/red badges (moderate-low sample)

### Board Texture Classification

**Unit tests** for `classify_flop()`:
- ABB: ["Ah", "Kd", "Jc"] -> rank=ABB, suit=rainbow, paired=false
- Axx: ["As", "7h", "3d"] -> rank=Axx, suit=rainbow, paired=false
- Axx 2tone: ["As", "7s", "3d"] -> rank=Axx, suit=2tone, paired=false
- BBB: ["Kh", "Qd", "Tc"] -> rank=BBB, suit=rainbow, paired=false
- Monocolor: ["8s", "5s", "2s"] -> rank=8-2 Disc, suit=monocolor, paired=false
- Paired: ["9h", "9d", "3c"] -> rank=Bxx (9 is not broadway), suit=rainbow, paired=true
- 8-2 Connected: ["8h", "7d", "5c"] -> rank=8-2 Conn, suit=rainbow, paired=false
- T-9 Connected: ["Th", "9d", "7c"] -> rank=T-9 Conn, suit=rainbow, paired=false

**Unit tests** for `classify_turn_card()`:
- Completed draw: flop=["8h","7d","2c"], turn="6s" -> completed_draw (straight)
- Overcard: flop=["9h","7d","2c"], turn="Ks" -> overcard
- Paired board: flop=["Kh","7d","2c"], turn="7s" -> paired_board
- Brick: flop=["Ah","Kd","7c"], turn="3s" -> brick
- Draw-adding: flop=["Kh","7d","2c"], turn="8s" -> draw_adding

### Acceptance Criteria Checklist

#### M4.1 -- Player Lookup & Classification

- [ ] Player search bar finds players by username (partial match)
- [ ] Player list shows VPIP/PFR/3-Bet/Hands/Type/Last Seen columns
- [ ] Player list is sortable by any column
- [ ] Player list is filterable by player type
- [ ] Player type badge (NIT/TAG/LAG/REC/MAN) is colored and visible
- [ ] Player profile page shows full stat breakdown (same format as hero stats)
- [ ] Head-to-head tab shows hero's results vs this player with positional breakdown
- [ ] Hands tab shows all hands where this player was present
- [ ] Notes tab allows saving free-text notes
- [ ] Color tag selector works (5 colors)
- [ ] Player type classification runs automatically after each import
- [ ] Players with <20 hands are classified as UNK
- [ ] Clicking a villain name in the hand browser navigates to their profile

#### M4.2 -- Population Analysis

- [ ] Population page loads with correct player count and observation count
- [ ] All 6 filter controls work (stakes, date range, min hands, exclude hero, player type, pot players)
- [ ] Preflop: Open Raise by position bar shows correct values
- [ ] Preflop: 3-Bet position matrix shows values with correct heatmap coloring
- [ ] Preflop: Fold-to-3-Bet matrix shows values
- [ ] Preflop: Open raise sizing table shows average sizes and distributions
- [ ] Preflop: 4-Bet/5-Bet table shows values by position
- [ ] Flop: Line frequencies show C-Bet/Fold-to-CB/XR/Donk by pot type and position
- [ ] Flop: Board texture breakdown shows stats by texture category
- [ ] Flop: Sizing distribution shows correct sizing buckets
- [ ] Turn: Line frequencies show double barrel/probe/delayed cbet
- [ ] Turn: Texture breakdown shows stats by turn card category
- [ ] River: Aggregate lines show triple barrel/probe/bet frequency
- [ ] River: Sizing distribution shows correct buckets
- [ ] Pot Type: SRP vs 3-Bet vs 4-Bet comparison table shows all metrics
- [ ] Showdown: WTSD/WSD/WWSF by position table renders correctly
- [ ] Showdown: AF/AFq by street and pot type renders correctly
- [ ] Player Segmentation: NIT/TAG/LAG/REC/MAN comparison table shows correct stats
- [ ] Sizing Tells: Sizing vs strength heatmap renders with correct values
- [ ] HU vs MW: Side-by-side comparison shows correct differences
- [ ] Confidence badges appear on all cells (green >= 1000, yellow 200-999, red < 200)
- [ ] Cells with <50 observations are hidden or greyed out
- [ ] All sections are collapsible with remembered state
- [ ] All queries complete within 3 seconds for a 500K-hand database

#### M4.3 -- Hero vs. Population

- [ ] Hero stats and population stats are displayed side-by-side
- [ ] Difference column shows correct delta
- [ ] Toggle between "vs. Benchmark" and "vs. Population" coloring works
- [ ] Deviations are correctly identified as intentional exploits vs. leaks

---

## Open Questions

1. **Board texture computation timing**: Classify during insert (in `insert_parsed_hand`) or as a separate backfill step? Insert-time is cleaner for new hands, but we need backfill for existing data regardless. Recommendation: compute during insert AND provide a backfill via `/api/import/rebuild`.

2. **Pot size tracking granularity**: Track `pot_before_action` on every action (expensive storage for 6M+ action rows), or only on bet/raise actions (smaller but still covers sizing analysis)? Recommendation: every action -- DuckDB handles the storage efficiently, and having the running pot for all actions enables future features.

3. **Population query caching**: For 6M+ record aggregations, should we precompute aggregate tables (materialized views) on import, or rely on DuckDB's analytical query speed? DuckDB is columnar and fast, but UI responsiveness matters. Recommendation: start without caching, benchmark real query times, add materialized views only if needed.

4. **Min hands per player filter**: Should this filter at query time (flexible but slower) or precompute player-level aggregates and filter (faster but less flexible)? Recommendation: query-time filtering with a subquery: `WHERE player_id IN (SELECT player_id FROM hand_players GROUP BY player_id HAVING COUNT(*) >= ?)`.

5. **Player type recomputation frequency**: After every import batch, or on-demand? Recommendation: after every import batch (in `finalize_import`). The computation is a single aggregate query that runs in <1s even for large databases.

6. **Population page load strategy**: Load all 9 sections at once, or lazy-load as sections are expanded? Recommendation: load preflop section on page load (most important, always visible), lazy-load remaining sections when expanded. This keeps initial page load fast.
