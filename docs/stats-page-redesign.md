# /stats Page Redesign

> Current stat set is the minimum. This redesign EXTENDS it — nothing is removed.

## What Changes

### Promoted to Positional Grid (from KV flat → full 7-position columns)

These stats have meaningful positional variance and the backend already computes them by position. Showing them as flat KV numbers hides the most important dimension.

| Stat | Why positional matters |
|------|----------------------|
| VPIP | EP 15% vs BTN 45% — the staircase pattern is the first thing a coach checks |
| PFR | Same — and the VPIP-PFR gap per position reveals where passive entries hide |
| 4-Bet | BTN 4-bets wider than EP. Flat number hides range construction |
| Fold to 4-Bet | Position determines whether hero 3-bet light (BTN) or linear (EP), so fold rate should differ |
| Limp | Tells you WHERE the limps happen (SB? EP? everywhere?) |
| BB Defense | Only BB column has data, but it belongs in the grid visually with other defensive stats |
| Iso Raise | Position determines range — iso from BTN vs MP are different spots |

### New Stats Added to Main Page

| Stat | Section | Why it matters |
|------|---------|---------------|
| BB Defense | Preflop positional grid | Top 3 coaching stat. Players fold BB 70%+ at low stakes and bleed money. |
| Iso Raise | Preflop positional grid | Limps are constant below NL200. How hero responds = key. |
| Fold to Squeeze | Preflop KV | Completes the squeeze interaction. Hero opens, gets squeezed — what happens? |
| C-Bet Flop (SRP) | Postflop | C-bet frequency in single raised pots. Different strategy than 3-bet pots. |
| C-Bet Flop (3-Bet Pot) | Postflop | C-bet frequency in 3-bet pots. SPR is lower, ranges are narrower — should c-bet differently. |
| Fold to CBet Flop (SRP) | Postflop | Defense rate differs by pot type. |
| Fold to CBet Flop (3-Bet Pot) | Postflop | Narrower ranges → different fold strategy. |
| Check-Raise Flop | Postflop | One of the most important postflop actions. Currently untracked. |
| Check-Raise Turn | Postflop | |
| Check-Raise River | Postflop | |
| C-Bet positional columns | Postflop | C-Bet and Fold-to-CBet get full positional breakdown (Tot/EP/MP/CO/BTN/SB/BB). Position is huge for postflop. |

### New Subpage Widget: PvP Matrix

Hero Position (rows) x Villain Position (cols) heatmap for interaction stats. See full spec at the end.

### New Subpage Widget: IP/OOP Split

Side-by-side comparison for stats where position relative to opponent matters. Replaces nothing — it's added alongside existing widgets.

---

## Full Page Layout

### Summary Bar (top)

```
[Stakes ▼] [Game Mode ▼] [Date ▼] [Last ___ hands]    13,402 hands   +4.2 bb/100   EV +5.1
```

### Preflop Section

**Left: Positional Grid**

Columns: `Stat | Tot | EP | MP | CO | BTN | SB | BB`

| # | Group | Row | drillKey |
|---|-------|-----|----------|
| 1 | Entry | VPIP | `vpip` |
| 2 | Entry | PFR | `pfr` |
| 3 | Entry | Open Raise (RFI) | `open_raise` |
| 4 | Entry | Limp | `limp` |
| 5 | Entry | Iso Raise | `iso_raise` |
| 6 | vs Open | Call Open | `call_open_raise` |
| 7 | vs Open | 3-Bet | `three_bet` |
| 8 | vs Open | 3-Bet IP | `three_bet_ip` |
| 9 | vs Open | 3-Bet OOP | `three_bet_oop` |
| 10 | vs Open | Squeeze | `squeeze` |
| 11 | vs 3-Bet | Fold to 3-Bet | `fold_to_3bet` |
| 12 | vs 3-Bet | 4-Bet | `four_bet` |
| 13 | vs 4-Bet | Fold to 4-Bet | `fold_to_4bet` |
| 14 | Defense | vs Steal Fold | `fold_to_steal` |
| 15 | Defense | BB Defense | `bb_defense` |

15 rows x 8 columns. Group headers are thin separators, not full rows.

**Right: KV Grid (rare/flat stats)**

| Label | drillKey | Notes |
|-------|----------|-------|
| 5-Bet | `five_bet` | ~10 instances per 100k |
| Call 4-Bet | `call_4bet` | ~15 instances |
| 4-Bet-Fold | `four_bet_fold` | ~5 instances |
| Limp-Fold | `limp_fold` | Derivative of limp |
| 4-Bet Range | `four_bet_range` | % of all hands |
| Fold to Squeeze | `fold_to_squeeze` | |
| Win Rate | — | bb/100, not clickable |
| Win Rate EV | — | bb/100, not clickable |
| Hands | — | Count, not clickable |

### Steal Section (unchanged + CO column added)

**Left: Steal Attempted**

Columns: `Stat | Tot | CO | BTN | SB`

| Row | drillKey |
|-----|----------|
| Steal | `steal` |
| Fold to 3-Bet | `fold_to_3bet` (steal context) |
| 4-Bet | `four_bet` (steal context) |
| 4-Bet-Fold | `four_bet_fold_steal` |

**Right: vs Steal**

Columns: `Stat | SB | BB`

| Row | drillKey |
|-----|----------|
| Fold | `fold_to_steal` |
| Call | `call_steal` |
| 3-Bet | `three_bet_vs_steal` |

### Postflop Section

**Left: By-Street Grid**

Columns: `Stat | Flop | Turn | River`

| # | Group | Row | Flop drillKey | Turn drillKey | River drillKey |
|---|-------|-----|---------------|---------------|----------------|
| 1 | C-Bet | C-Bet | `cbet_flop` | `cbet_turn` | `cbet_river` |
| 2 | C-Bet | Fold to CBet | `fold_to_cbet_flop` | `fold_to_cbet_turn` | `fold_to_cbet_river` |
| 3 | C-Bet by Pot | CBet (SRP) | `cbet_flop_srp` | — | — |
| 4 | C-Bet by Pot | CBet (3-Bet Pot) | `cbet_flop_3bp` | — | — |
| 5 | C-Bet by Pot | Fold CBet (SRP) | `fold_cbet_flop_raised` | — | — |
| 6 | C-Bet by Pot | Fold CBet (3BP) | `fold_cbet_flop_3bet` | — | — |
| 7 | Aggression | Check-Raise | `check_raise_flop` | `check_raise_turn` | `check_raise_river` |
| 8 | Aggression | Aggression | `af_flop` | `af_turn` | `af_river` |
| 9 | Aggression | Agg Freq | `afq_flop` | `afq_turn` | `afq_river` |
| 10 | Aggression | Donk Bet | `donk_bet_flop` | `donk_bet_turn` | `donk_bet_river` |

**Right: vs CBet Flop Response**

Columns: `Pot Type | Fold | Call | Raise`

| Row | F drillKey | C drillKey | R drillKey |
|-----|-----------|-----------|-----------|
| Single Raise | `fold_cbet_flop_raised` | `call_cbet_flop_raised` | `raise_cbet_flop_raised` |
| 3-Bet Pot | `fold_cbet_flop_3bet` | `call_cbet_flop_3bet` | `raise_cbet_flop_3bet` |

**Right (below): C-Bet Positional** (NEW)

Columns: `Stat | Tot | EP | MP | CO | BTN | SB | BB`

| Row | drillKey |
|-----|----------|
| C-Bet Flop | `cbet_flop` |
| Fold to CBet Flop | `fold_to_cbet_flop` |

### Missed C-Bet Section (unchanged)

**Left: Hero Missed C-Bet**

| Stat | drillKey |
|------|----------|
| Missed C-Bet | `missed_cbet_flop` |
| → In Position | `missed_cbet_flop_ip` |
| → → Fold | `missed_cbet_fold_ip` |
| → Out of Position | `missed_cbet_flop_oop` |
| → → Fold | `missed_cbet_fold_oop` |

**Right: vs Missed C-Bet**

| Stat | drillKey |
|------|----------|
| vs Missed C-Bet | `vs_missed_cbet` |
| → Bet IP | `vs_missed_cbet_bet_ip` |
| → Check-Fold IP | `vs_missed_cbet_check_fold_ip` |
| → Bet OOP Turn | `vs_missed_cbet_bet_oop_turn` |
| → Check-Fold OOP | `vs_missed_cbet_check_fold_oop` |

### Missed C-Bet Turn (NEW)

| Stat | drillKey |
|------|----------|
| Missed C-Bet Turn | `missed_cbet_turn` |

### Showdown Section (unchanged)

`WTSD` | `W$SD` | `WWSF` — inline row.

---

## Backend Work Required

### New Stat Registry Entries (filter existing data, no new DB columns)

```python
# C-Bet by pot type
"cbet_flop_srp": {
    "name": "C-Bet Flop (SRP)",
    "action_flag": "cbet_flop",
    "opp_sql": "hp.cbet_flop_opp = TRUE AND NOT COALESCE(hp.is_3bet_pot, false)",
},
"cbet_flop_3bp": {
    "name": "C-Bet Flop (3-Bet Pot)",
    "action_flag": "cbet_flop",
    "opp_sql": "hp.cbet_flop_opp = TRUE AND hp.is_3bet_pot = TRUE",
},
```

### New Stat Flags (need DB columns + computation in stat_flags.py)

**Check-Raise** — hero checks, opponent bets, hero raises on the same street.

New columns on `hand_players`:
- `check_raise_flop` (BOOLEAN)
- `check_raise_flop_opp` (BOOLEAN) — hero checked and faced a bet
- `check_raise_turn` (BOOLEAN)
- `check_raise_turn_opp` (BOOLEAN)
- `check_raise_river` (BOOLEAN)
- `check_raise_river_opp` (BOOLEAN)

Detection logic in `compute_stat_flags`:
```
For each street:
  If hero checks, then another player bets:
    check_raise_opp = True
    If hero then raises:
      check_raise = True
```

### New Stats Engine Aggregation

Add to `_AGG_SQL` in `stats_engine.py`:
- `check_raise_flop` / `check_raise_flop_opp` counts
- `cbet_flop` filtered by `is_3bet_pot` for per-pot-type aggregation

Add to `HeroStats` model:
- `check_raise_flop`, `check_raise_turn`, `check_raise_river` as `StatValue`
- `cbet_flop_srp`, `cbet_flop_3bp` as `StatValue`
- `fold_cbet_flop_srp` as `StatValue` (already partially exists as `fold_cbet_flop_raised`)
- `cbet_flop_positional` — positional breakdown for c-bet flop (PositionalStats, already available via `cbet_flop`)
- `fold_to_cbet_flop_positional` — same

---

## Stat Subpages — Widget Assignments

Every stat cell on the main page navigates to `/stats/{drillKey}`.

Each subpage has:
1. **Header** — stat name, value (action/opportunity), position filter tabs
2. **Analysis Widgets** — custom per stat (defined below)
3. **Hand Explorer** — paginated table of triggered hands, at the bottom

### Reusable Widget Types

| Widget | Key | Description |
|--------|-----|-------------|
| Range Heatmap | `range_heatmap` | 13x13 combo grid colored by stat frequency |
| PvP Matrix | `pvp_matrix` | **NEW.** Hero Position x Villain Position heatmap |
| Response Distribution | `response_distribution` | Fold / Call / Raise stacked bar |
| Continuing Range | `continuing_range` | 13x13 grid: fold=gray, call=blue, raise=red |
| EV Breakdown | `ev_breakdown` | bb/100 by scenario |
| Fold Equity | `fold_equity` | Single %: how often action wins pot uncontested |
| Sizing Histogram | `sizing_histogram` | Distribution of bet/raise sizes |
| By Context | `by_context` | Breakdown by dimension (villain pos, callers, etc.) |
| Trend Sparkline | `trend_sparkline` | Rolling % over time |
| Money Burned | `money_burned` | Cumulative bb lost |
| Composition | `composition` | Sub-component stacked bar |
| Gap Indicator | `gap_indicator` | VPIP-PFR gap number |
| Postflop Bridge | `postflop_bridge` | C-bet rate + SPR connecting preflop → postflop |
| Opportunity Context | `opportunity_context` | "Did X% of hands, opportunity Y%, took Z%" |
| IP/OOP Split | `ip_oop_split` | **NEW.** Side-by-side IP vs OOP comparison |

### Preflop Subpage Widgets

#### `vpip`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | Master range — every combo hero plays voluntarily |
| 2 | `composition` | Open / cold-call / 3-bet / limp / squeeze split. Composition > number. |
| 3 | `by_context` | Positional bar chart (staircase check) |
| 4 | `ev_breakdown` | bb/100 by entry type |
| 5 | `trend_sparkline` | |

#### `pfr`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | All raised combos |
| 2 | `gap_indicator` | VPIP-PFR gap. 4-6% optimal, >8% = passive leak. |
| 3 | `composition` | Open / 3-bet / 4-bet / squeeze share |
| 4 | `by_context` | Positional bar with VPIP overlay |
| 5 | `trend_sparkline` | |

#### `open_raise`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | Open-raise combos by position |
| 2 | `response_distribution` | Fold-through / called / 3-bet faced after opening |
| 3 | `ev_breakdown` | bb/100 by outcome |
| 4 | `sizing_histogram` | Open sizes (2x, 2.5x, 3x) |
| 5 | `pvp_matrix` | Hero open position x villain 3-bet response position |
| 6 | `trend_sparkline` | |

#### `call_open_raise`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | Cold-call combos |
| 2 | `ev_breakdown` | bb/100 for cold-call pots |
| 3 | `pvp_matrix` | Hero position x opener position |
| 4 | `postflop_bridge` | WWSF in cold-call pots |
| 5 | `trend_sparkline` | |

#### `three_bet`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | 3-bet combos |
| 2 | `fold_equity` | How often villain folds. Below 50% = trouble. |
| 3 | `ev_breakdown` | bb/100: fold-through / called / 4-bet faced |
| 4 | `pvp_matrix` | **KEY widget.** Hero 3-bet position x opener position. |
| 5 | `ip_oop_split` | Side-by-side IP vs OOP range |
| 6 | `postflop_bridge` | C-bet rate + SPR in 3-bet pots |
| 7 | `trend_sparkline` | |

#### `three_bet_ip`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | IP 3-bet range (should be wider than OOP) |
| 2 | `fold_equity` | |
| 3 | `ev_breakdown` | |
| 4 | `pvp_matrix` | IP 3-bet position x opener position |
| 5 | `trend_sparkline` | |

#### `three_bet_oop`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | OOP range (tighter, more linear) |
| 2 | `fold_equity` | |
| 3 | `ev_breakdown` | |
| 4 | `ip_oop_split` | IP vs OOP range comparison (gap = adjustment quality) |
| 5 | `trend_sparkline` | |

#### `squeeze`
| # | Widget | Why |
|---|--------|-----|
| 1 | `fold_equity` | Squeeze fold rate |
| 2 | `ev_breakdown` | bb/100 |
| 3 | `by_context` | By number of callers |
| 4 | `by_context` | By hero position |
| 5 | `trend_sparkline` | |

#### `fold_to_3bet`
| # | Widget | Why |
|---|--------|-----|
| 1 | `response_distribution` | Fold / Call / 4-bet |
| 2 | `continuing_range` | Combos hero continues with |
| 3 | `ev_breakdown` | bb/100 by response |
| 4 | `pvp_matrix` | Hero open position x 3-bettor position |
| 5 | `trend_sparkline` | |

#### `four_bet`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | 4-bet combos |
| 2 | `fold_equity` | |
| 3 | `ev_breakdown` | |
| 4 | `opportunity_context` | "4-bet X% of hands, opportunity Y%, took Z%" |
| 5 | `money_burned` | bb lost to 4-bet-folds (subsumes old `four_bet_fold` detail) |
| 6 | `pvp_matrix` | Hero position x 3-bettor position |
| 7 | `trend_sparkline` | |

#### `fold_to_4bet`
| # | Widget | Why |
|---|--------|-----|
| 1 | `response_distribution` | Fold / Call / 5-bet |
| 2 | `continuing_range` | |
| 3 | `ev_breakdown` | |
| 4 | `by_context` | By hero 3-bet position |
| 5 | `trend_sparkline` | |

#### `limp`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | Limp combos (should be ~empty) |
| 2 | `money_burned` | Cumulative bb lost in limped pots |
| 3 | `by_context` | Limp-fold rate by position |
| 4 | `ev_breakdown` | bb/100 limped vs raised pots |
| 5 | `trend_sparkline` | |

#### `iso_raise`
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | |
| 2 | `by_context` | By number of limpers |
| 3 | `sizing_histogram` | Standard = open + 1bb per limper |
| 4 | `ev_breakdown` | |
| 5 | `trend_sparkline` | |

#### `fold_to_steal`
| # | Widget | Why |
|---|--------|-----|
| 1 | `response_distribution` | Fold / Call / 3-bet vs steal |
| 2 | `continuing_range` | |
| 3 | `ev_breakdown` | |
| 4 | `by_context` | By stealer position (CO/BTN/SB) |
| 5 | `trend_sparkline` | |

#### `bb_defense`
| # | Widget | Why |
|---|--------|-----|
| 1 | `response_distribution` | Fold / Call / 3-bet from BB |
| 2 | `continuing_range` | BB gets 2.5-3.5:1 odds — range should be wide |
| 3 | `ev_breakdown` | bb/100 by response |
| 4 | `pvp_matrix` | 1D: defense rate by raiser position |
| 5 | `trend_sparkline` | |

#### `fold_to_squeeze`
| # | Widget | Why |
|---|--------|-----|
| 1 | `response_distribution` | Fold / Call / 4-bet vs squeeze |
| 2 | `continuing_range` | |
| 3 | `ev_breakdown` | |
| 4 | `by_context` | By squeezer position |
| 5 | `trend_sparkline` | |

#### KV-only stats (5-bet, call_4bet, four_bet_fold, limp_fold)

All get the same minimal set (low sample):

| # | Widget |
|---|--------|
| 1 | `range_heatmap` (if applicable) or `money_burned` |
| 2 | `ev_breakdown` |
| 3 | `trend_sparkline` |

### Postflop Subpage Widgets

#### `cbet_flop`
| # | Widget | Why |
|---|--------|-----|
| 1 | `ip_oop_split` | C-bet rate IP vs OOP |
| 2 | `response_distribution` | Villain fold / call / raise after c-bet |
| 3 | `ev_breakdown` | bb/100: c-bet vs check |
| 4 | `sizing_histogram` | C-bet size distribution |
| 5 | `by_context` | By pot type (SRP vs 3-bet pot) |
| 6 | `trend_sparkline` | |

#### `cbet_turn`, `cbet_river`
| # | Widget |
|---|--------|
| 1 | `ip_oop_split` |
| 2 | `ev_breakdown` |
| 3 | `sizing_histogram` |
| 4 | `trend_sparkline` |

#### `cbet_flop_srp`, `cbet_flop_3bp`
| # | Widget |
|---|--------|
| 1 | `ip_oop_split` |
| 2 | `response_distribution` |
| 3 | `ev_breakdown` |
| 4 | `sizing_histogram` |
| 5 | `trend_sparkline` |

#### `fold_to_cbet_flop`
| # | Widget |
|---|--------|
| 1 | `response_distribution` |
| 2 | `ip_oop_split` |
| 3 | `ev_breakdown` |
| 4 | `by_context` | By pot type (SRP vs 3-bet) |
| 5 | `trend_sparkline` |

#### `fold_to_cbet_turn`, `fold_to_cbet_river`
Same pattern as flop.

#### `check_raise_flop` (NEW)
| # | Widget | Why |
|---|--------|-----|
| 1 | `range_heatmap` | Which combos hero check-raises |
| 2 | `fold_equity` | How often villain folds to check-raise |
| 3 | `ev_breakdown` | bb/100: check-raise vs check-call vs check-fold |
| 4 | `ip_oop_split` | (mostly OOP action but IP traps exist) |
| 5 | `by_context` | By pot type (SRP vs 3-bet) |
| 6 | `sizing_histogram` | Check-raise size distribution |
| 7 | `trend_sparkline` | |

#### `check_raise_turn`, `check_raise_river`
| # | Widget |
|---|--------|
| 1 | `range_heatmap` |
| 2 | `fold_equity` |
| 3 | `ev_breakdown` |
| 4 | `trend_sparkline` |

#### `afq_flop`, `afq_turn`, `afq_river`
| # | Widget |
|---|--------|
| 1 | `composition` | Bet / raise / call / check-fold pie |
| 2 | `ip_oop_split` |
| 3 | `ev_breakdown` |
| 4 | `trend_sparkline` |

#### `af_flop`, `af_turn`, `af_river`
| # | Widget |
|---|--------|
| 1 | `composition` | Bets / raises / calls raw counts |
| 2 | `ip_oop_split` |
| 3 | `trend_sparkline` |

#### `donk_bet_flop`, `donk_bet_turn`, `donk_bet_river`
| # | Widget |
|---|--------|
| 1 | `range_heatmap` |
| 2 | `ev_breakdown` |
| 3 | `sizing_histogram` |
| 4 | `trend_sparkline` |

#### vs C-Bet response stats (fold/call/raise in raised/3bet pots)
| # | Widget |
|---|--------|
| 1 | `response_distribution` |
| 2 | `ev_breakdown` |
| 3 | `trend_sparkline` |

#### Missed C-Bet stats (all variants)
| # | Widget |
|---|--------|
| 1 | `ip_oop_split` (for main missed_cbet_flop) |
| 2 | `ev_breakdown` |
| 3 | `by_context` | What happens after check |
| 4 | `money_burned` (for fold variants) |
| 5 | `trend_sparkline` |

### Showdown Subpage Widgets

#### `went_to_showdown` (WTSD)
| # | Widget |
|---|--------|
| 1 | `by_context` | By pot type (SRP / 3-bet / 4-bet) |
| 2 | `ev_breakdown` | Showdown vs non-showdown bb/100 |
| 3 | `ip_oop_split` |
| 4 | `trend_sparkline` |

#### `won_at_showdown` (W$SD)
| # | Widget |
|---|--------|
| 1 | `by_context` | By pot type |
| 2 | `ip_oop_split` |
| 3 | `trend_sparkline` |

#### `wwsf` (WWSF)
| # | Widget |
|---|--------|
| 1 | `composition` | Showdown win % vs fold-equity win % |
| 2 | `by_context` | By pot type |
| 3 | `ip_oop_split` |
| 4 | `trend_sparkline` |

---

## PvP Matrix Widget — Specification

Hero Position (rows) x Villain Position (cols) heatmap for interaction stats.

### Visual

```
3-Bet % by Matchup
            Villain Open Position →
            EP     MP     CO     BTN    SB
Hero  MP    8.1    —      —      —      —
      CO    5.2    7.4    —      —      —
      BTN   3.8    6.1    10.2   —      —
      SB    3.1    4.9    8.7    12.4   —
      BB    4.0    5.8    9.1    14.2   17.8
```

- Color intensity = stat frequency (light → dark)
- Each cell clickable → filters hand explorer to that matchup
- Cells with <10 sample → muted text + subscript sample size
- Impossible matchups → `—`

### Stats that get PvP Matrix

| Stat | Rows (Hero) | Cols (Villain) | Join condition |
|------|-------------|----------------|----------------|
| `three_bet` | Hero 3-bet pos | Opener pos | `v.open_raise = TRUE` |
| `fold_to_3bet` | Hero open pos | 3-bettor pos | `v.three_bet = TRUE` |
| `four_bet` | Hero pos | 3-bettor pos | `v.three_bet = TRUE` |
| `call_open_raise` | Hero call pos | Opener pos | `v.open_raise = TRUE` |
| `open_raise` | Hero open pos | 3-bettor pos | `v.three_bet = TRUE` |
| `bb_defense` | BB (1D) | Raiser pos | `v.open_raise = TRUE` |
| `three_bet_ip` | Hero pos | Opener pos | `v.open_raise = TRUE` |

### Backend

New endpoint: `GET /api/stats/detail/{stat_key}/pvp-matrix`

```python
PVP_MATRIX_CONFIG = {
    "three_bet": {
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "villain_label": "opener_position",
    },
    "fold_to_3bet": {
        "action_sql": "hp.fold_to_3bet = TRUE",
        "opp_sql": "hp.fold_to_3bet IS NOT NULL",
        "villain_join": "v.three_bet = TRUE",
        "villain_label": "3bettor_position",
    },
    "four_bet": {
        "action_sql": "hp.four_bet = TRUE",
        "opp_sql": "hp.four_bet_opp = TRUE",
        "villain_join": "v.three_bet = TRUE",
        "villain_label": "3bettor_position",
    },
    "call_open_raise": {
        "action_sql": "hp.call_open_raise = TRUE",
        "opp_sql": "hp.call_open_raise_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "villain_label": "opener_position",
    },
    "open_raise": {
        "action_sql": "hp.fold_to_3bet IS NOT NULL",
        "opp_sql": "hp.open_raise = TRUE",
        "villain_join": "v.three_bet = TRUE",
        "villain_label": "3bettor_position",
    },
    "bb_defense": {
        "action_sql": "hp.bb_defense = TRUE",
        "opp_sql": "hp.bb_defense_opp = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "villain_label": "raiser_position",
    },
    "three_bet_ip": {
        "action_sql": "hp.three_bet = TRUE",
        "opp_sql": "hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = TRUE",
        "villain_join": "v.open_raise = TRUE",
        "villain_label": "opener_position",
    },
}
```

SQL:
```sql
SELECT
    hp.position AS hero_pos,
    v.position AS villain_pos,
    SUM(CASE WHEN {action_sql} THEN 1 ELSE 0 END) AS actions,
    COUNT(*) AS opportunities
FROM hand_players hp
JOIN hands h ON hp.hand_id = h.id
JOIN hand_players v ON v.hand_id = hp.hand_id
    AND v.player_id != hp.player_id
    AND {villain_join}
WHERE {base_where} AND ({opp_sql})
GROUP BY hp.position, v.position
```

Response:
```json
{
  "hero_label": "hero_position",
  "villain_label": "opener_position",
  "cells": [
    {"hero": "BB", "villain": "BTN", "actions": 42, "opportunities": 295, "pct": 14.2},
    ...
  ]
}
```

---

## IP/OOP Split Widget — Specification

Side-by-side comparison showing the same stat split by whether hero was IP or OOP.

### Where it appears

| Stat | What it shows |
|------|--------------|
| `three_bet` | IP vs OOP 3-bet range heatmaps |
| `cbet_flop` | C-bet rate IP vs OOP |
| `fold_to_cbet_flop` | Fold rate IP vs OOP |
| `missed_cbet_flop` | Check-back rate IP vs OOP |
| `went_to_showdown` | WTSD IP vs OOP |
| `wwsf` | WWSF IP vs OOP (5-10% gap expected) |
| `check_raise_flop` | CR rate IP vs OOP |

### Backend

For preflop: uses `three_bet_opp_ip` flag (already exists).
For postflop: uses `postflop_ip` flag (already exists).

Call existing stat detail endpoint with `ip=true` / `ip=false` filter parameter (or new dedicated endpoint returning both in one response).

---

## Stat Count Summary

| Section | Stats on Main Page |
|---------|--------------------|
| Preflop positional grid | 15 rows x 8 cols |
| Preflop KV grid | 9 items |
| Steal | 4 rows x 4 cols + 3 rows x 2 cols |
| Postflop by-street | 10 rows x 3 cols |
| Postflop vs CBet | 2 rows x 3 cols |
| Postflop C-Bet positional | 2 rows x 8 cols |
| Missed C-Bet | 10 inline stats |
| Showdown | 3 inline stats |
| **Total unique stats** | **~60 clickable** (up from ~55 preflop + postflop combined) |

New stats added: BB Defense, Iso Raise, Fold to Squeeze, C-Bet by pot type (SRP/3BP), Check-Raise (flop/turn/river), C-Bet positional, Fold to CBet positional.

All existing stats preserved. Layout reorganized to surface positional data that was hidden in flat KV grid.
