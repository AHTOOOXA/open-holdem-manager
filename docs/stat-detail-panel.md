# Stat Detail Panel — Per-Stat Interface Contents

What appears in the right-side detail panel when each stat is clicked.

Every stat shows: **Header** (name, %, action/opp counts) + **Position tabs** (if positional) + **Hand list** (7-col table) + **Pagination**.

Widgets appear between header and hand list. Legend:
- **Pos Bar** — Positional mini-bar (EP→BB horizontal bars). Only for postflop stats where the left panel doesn't already show a full positional table.
- **Resp Dist** — Response distribution (Fold / Call / Raise stacked bar). For defensive stats.
- **Range** — Collapsible 13×13 range heatmap colored by stat frequency. Preflop stats only.
- **Trend** — Sparkline of rolling average over time with overall reference line. Adaptive window size via CI formula.

---

## Pre-Flop Action

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| VPIP | yes | — | — | yes | yes |
| PFR | yes | — | — | yes | yes |
| Open Raise | yes | — | — | yes | yes |
| Call Open Raise | yes | — | — | yes | yes |
| 3-Bet | yes | — | — | yes | yes |
| 3-Bet IP | yes | — | — | yes | yes |
| 3-Bet OOP | yes | — | — | yes | yes |
| 4-Bet | yes | — | — | yes | yes |
| 5-Bet | — | — | — | — | yes |

## Pre-Flop Defense

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Fold to 3-Bet | yes | — | yes | yes | yes |
| Fold to 4-Bet | yes | — | yes | yes | yes |
| Limp | yes | — | — | yes | yes |
| Squeeze | — | — | — | — | yes |
| Limp-Fold | — | — | — | — | yes |
| 4-Bet-Fold | — | — | — | — | yes |
| Call 4-Bet | — | — | — | — | yes |
| 4-Bet Range | — | — | — | — | yes |

## Steal

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Steal | yes | — | — | — | yes |
| Fold to Steal | yes | — | yes | — | yes |
| Call Steal | yes | — | yes | — | yes |
| 3-Bet vs Steal | yes | — | yes | — | yes |
| 4-Bet-Fold (Steal) | — | — | — | — | yes |

## Postflop Action

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| C-Bet Flop | yes | yes | — | — | yes |
| C-Bet Turn | yes | yes | — | — | yes |
| C-Bet River | yes | yes | — | — | yes |

## Postflop Defense

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Fold to CBet Flop | yes | yes | yes | — | yes |
| Fold to CBet Turn | yes | yes | yes | — | yes |
| Fold to CBet River | yes | yes | yes | — | yes |

## vs C-Bet Flop (Raised Pot)

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Fold to CBet (Raised) | — | — | yes | — | yes |
| Call CBet (Raised) | — | — | — | — | yes |
| Raise CBet (Raised) | — | — | — | — | yes |

## vs C-Bet Flop (3-Bet Pot)

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Fold to CBet (3-Bet) | — | — | yes | — | yes |
| Call CBet (3-Bet) | — | — | — | — | yes |
| Raise CBet (3-Bet) | — | — | — | — | yes |

## Donk Bet

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Donk Bet Flop | — | — | — | — | yes |
| Donk Bet Turn | — | — | — | — | yes |
| Donk Bet River | — | — | — | — | yes |

## Missed C-Bet

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Missed C-Bet Flop | — | — | — | — | yes |
| Missed C-Bet IP | — | — | — | — | yes |
| Missed C-Bet OOP | — | — | — | — | yes |
| Missed C-Bet → Fold IP | — | — | — | — | yes |
| Missed C-Bet → Fold OOP | — | — | — | — | yes |

## vs Missed C-Bet

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| vs Missed C-Bet | — | — | — | — | yes |
| vs MC Bet IP | — | — | — | — | yes |
| vs MC Check-Fold IP | — | — | — | — | yes |
| vs MC Bet OOP Turn | — | — | — | — | yes |
| vs MC Check-Fold OOP | — | — | — | — | yes |

## Aggression

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| AF Flop | — | — | — | — | yes |
| AF Turn | — | — | — | — | yes |
| AF River | — | — | — | — | yes |
| Agg Freq Flop | — | — | — | — | yes |
| Agg Freq Turn | — | — | — | — | yes |
| Agg Freq River | — | — | — | — | yes |

## Showdown

| Stat | Pos Tabs | Pos Bar | Resp Dist | Range | Trend |
|---|---|---|---|---|---|
| Saw Flop | — | — | — | — | yes |
| WTSD | — | — | — | — | yes |
| W$SD | — | — | — | — | yes |
| WWSF | — | — | — | — | yes |

---

## Widget Details

### Trend Sparkline
- Adaptive window size: `N = (1.96/0.20)² × (1-p)/p`, clamped [100, 2000]
- Same CI framework as drift detection
- ~100 sampled points, monotone line, dashed reference at overall avg

### Response Distribution
- Stacked horizontal bar: Fold (gray) / Call (blue) / Raise (red)
- Available for: fold_to_3bet, fold_to_4bet, fold_to_cbet_*, fold_to_steal, call_steal, 3bet_vs_steal, fold_cbet_flop_raised, fold_cbet_flop_3bet

### Range Heatmap
- Collapsible 13×13 grid, default collapsed
- Color = stat frequency per combo (indigo intensity)
- Available for: vpip, pfr, open_raise, call_open_raise, three_bet(_ip/_oop), four_bet, limp, fold_to_3bet, fold_to_4bet

### Positional Mini-Bar
- 6 horizontal bars (EP→BB) with benchmark-based coloring (green/yellow/red)
- Click filters hand list to that position
- Only shown for postflop stats where left panel lacks positional columns
