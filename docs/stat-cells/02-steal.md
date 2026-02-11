# Steal — Clickable Cells & Detail Subpage Widgets

## Left Table — Steal Attempted (Tot / BTN / SB)

| # | Row | Column | drillKey | position param |
|---|-----|--------|----------|----------------|
| 54 | Steal | Tot | `steal` | — |
| 55 | Steal | BTN | `steal` | `btn` |
| 56 | Steal | SB | `steal` | `sb` |
| 57 | Fold to 3-Bet | Tot | `fold_to_3bet` | — |
| 58 | Fold to 3-Bet | BTN | `fold_to_3bet` | `btn` |
| 59 | Fold to 3-Bet | SB | `fold_to_3bet` | `sb` |
| 60 | 4-Bet | Tot | `four_bet` | — |
| 61 | 4-Bet | BTN | `four_bet` | `btn` |
| 62 | 4-Bet | SB | `four_bet` | `sb` |
| 63 | 4-Bet-Fold | Tot | `four_bet_fold_steal` | — |
| 64 | 4-Bet-Fold | BTN | `four_bet_fold_steal` | `btn` |
| 65 | 4-Bet-Fold | SB | `four_bet_fold_steal` | `sb` |

## Right Table — vs Steal (SB / BB)

| # | Row | Column | drillKey | position param |
|---|-----|--------|----------|----------------|
| 66 | Fold | SB | `fold_to_steal` | `sb` |
| 67 | Fold | BB | `fold_to_steal` | `bb` |
| 68 | Call | SB | `call_steal` | `sb` |
| 69 | Call | BB | `call_steal` | `bb` |
| 70 | 3-Bet | SB | `three_bet_vs_steal` | `sb` |
| 71 | 3-Bet | BB | `three_bet_vs_steal` | `bb` |

**Section total: 18 clickable cells**

> **Note:** `fold_to_3bet` (#57-59) and `four_bet` (#60-62) share drillKeys with the Pre-Flop section — their detail subpage widgets are defined in `01-preflop.md`. When clicked from the steal table, the position filter (BTN/SB) contextualizes the data automatically.

---

## Phase Legend

| Phase | Dependency | Description |
|-------|-----------|-------------|
| `NOW` | None | Ships with existing `hand_players` / `actions` data |
| `M5.3` | Pot tracking / bet sizing | Needs `actions.bet_pct_pot`, `pot_before_action` |
| `M5.5` | Decision analysis | EV per action with hand-strength x texture matrix |
| `NOW*` | None (basic) / M5.5 (rich) | Basic version uses `won_bb` averages; rich version after M5.5 |

---

## Detail Subpage Widgets

### `steal` — Steal Attempt

> Coach question: "Am I attacking the blinds enough, and is it working?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of steal-attempt combos. BTN should be visibly wider than SB — 40-50%+ of hands from BTN, 30-40% from SB. If both look the same, hero isn't adjusting for positional advantage postflop. |
| 2 | **Fold equity (success rate)** | `NOW` | Single number: how often the steal takes the blinds uncontested. THE key driver of steal profitability. Above 55% = hero prints money stealing wide. Below 45% = steals are getting played back too often — either hero steals too much or the pool is aggressive. |
| 3 | **EV by outcome** | `NOW*` | Three bb/100 numbers: steal folds through / steal called / steal 3-bet. The fold-through line should be very positive (winning dead blinds). The called/3-bet lines show how well hero handles resistance — negative called line = postflop leak in stolen pots. *Rich version (M5.5): adds hand-strength x texture matrix.* |
| 4 | **BTN vs SB comparison** | `NOW` | Side-by-side bars showing steal %, fold equity, and bb/100 for BTN vs SB separately. BTN steals should be wider (will be IP postflop). SB steals should be more polar (OOP if BB calls). If metrics are identical, hero isn't differentiating the spots. |
| 5 | **Sizing distribution** | `M5.3` | Histogram of steal open-raise sizes as % of pot, bucketed by position (BTN vs SB). Reveals if hero varies sizing by position — BTN steals can be smaller (2-2.2x) while SB steals should be larger (2.5-3x) to deny BB odds. Requires `bet_pct_pot`. |
| 6 | **Trend sparkline** | `NOW` | Rolling steal % over time with overall reference line. |

---

### `four_bet_fold_steal` — 4-Bet-Fold (Steal Context)

> Coach question: "Am I 4-bet bluffing from steal positions and then folding when shoved on?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money burned** | `NOW` | Total bb lost to steal 4-bet-folds. These are huge pots — a single 4-bet-fold costs ~20bb. Even 5-10 of these wipes out hundreds of hands of steal profit. The cumulative number makes the cost visceral. |
| 2 | **Which hands** | `NOW` | Combo list of what hero 4-bets then folds from steal spots. Appropriate bluffs (A5s, A4s — suited aces with blockers to AA/AK) or undisciplined hands that have no business being in a 4-bet pot? If hero is 4-bet-folding QQ+, something is deeply wrong. |
| 3 | **Rate in context** | `NOW` | "X of Y total steal 4-bets ended in fold to 5-bet." If above 40-50%, hero is either 4-betting too many bluffs or picking the wrong bluff candidates. If below 20%, this isn't a meaningful leak. |
| 4 | **BTN vs SB split** | `NOW` | Which position is the problem? SB 4-bet-folds are more common because SB faces more 3-bets from BB. BTN 4-bet-folds might indicate hero is 4-betting too aggressively vs blind 3-bets. |
| 5 | **Trend sparkline** | `NOW` | Rolling 4-bet-fold frequency from steal positions over time. |

---

### `fold_to_steal` — Fold vs Steal

> Coach question: "Am I giving up my blinds too easily and bleeding money passively?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money forfeited** | `NOW` | Cumulative bb lost by folding blinds to steals. Every SB fold costs 0.5bb, every BB fold costs 1bb. Over thousands of hands this becomes the single biggest passive leak. The total makes it tangible — "you've donated X bb by folding blinds." |
| 2 | **By stealer position** | `NOW` | Fold % broken out by who is stealing — BTN, CO, or SB (for BB facing SB steal). Hero should fold LESS vs BTN/CO (wide steal ranges, better pot odds to defend) and MORE vs EP/MP opens. If fold rate is flat across all positions, hero isn't reading ranges. |
| 3 | **Defending range heatmap** | `NOW` | Inverted view: which combos hero KEEPS (call = blue, 3-bet = red) vs folds (gray). Coaches look at what's folded that shouldn't be — suited connectors and suited Ax in BB that have enough equity to defend at the pot odds offered. |
| 4 | **Fold rate by steal sizing** | `NOW` | Hero fold % vs 2x steals, 2.5x steals, 3x steals (raw BB buckets). BB gets 3.5:1 vs a 2x steal — folding more than 30% is overfolding. Vs a 3x steal, folding 50% is reasonable. If hero folds the same rate regardless, they're ignoring pot odds. *Enhanced version (M5.3): uses `bet_pct_pot` for proper relative sizing buckets.* |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-steal % over time. |

---

### `call_steal` — Call Steal

> Coach question: "Am I defending enough by flatting, and do I play well after calling?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of steal-calling combos. BB should call wide — suited hands, connectors, Kxs, Ax — because pot odds are so favorable (3.5:1 vs standard 2.5x open). If the heatmap is sparse (only pocket pairs and suited broadways), hero is massively overfolding. |
| 2 | **EV impact** | `NOW*` | bb/100 for called steal pots. Slightly negative is expected and fine — BB is defending at a discount, so losing a fraction of a bb per defense is acceptable. But if deeply negative (below -20 bb/100), hero is either calling too wide or collapsing postflop. *Rich version (M5.5).* |
| 3 | **Postflop performance** | `NOW` | Three linked numbers: fold-to-cbet %, WWSF, and WTSD in called steal pots. This is where the real leak hides. Many players call steals correctly but then fold to every cbet — making the preflop call worthless. Fold-to-cbet above 55% in single-raised pots = postflop leak. |
| 4 | **By stealer position** | `NOW` | Call frequency vs BTN steal, CO steal, SB steal (for BB). Hero should call wider vs BTN (wider range = more equity for hero's defending hands) and tighter vs CO (stronger range). Flat across positions = not adjusting. |
| 5 | **Trend sparkline** | `NOW` | Rolling call-steal % over time. |

---

### `three_bet_vs_steal` — 3-Bet vs Steal

> Coach question: "Am I fighting back against late-position aggression, and is it profitable?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of 3-bet combos vs steals. Should show a polarized range: value (TT+, AQ+) plus bluffs (suited Ax, suited connectors with good playability). If only premiums light up, hero is massively underbluffing and letting stealers print money. |
| 2 | **Fold equity** | `NOW` | How often the stealer folds to hero's 3-bet. THE key profitability driver. Against weak stealers folding 60%+, hero should 3-bet bluff aggressively. Against stations calling 55%+, hero should shift to value-heavy 3-bets. This single number dictates the entire strategy. |
| 3 | **EV by outcome** | `NOW*` | bb/100 split three ways: 3-bet wins preflop (stealer folds), 3-bet called (goes to flop), 3-bet faces 4-bet. Fold-through should be very positive. Called line depends on postflop play. Facing 4-bet is where bluffs get tested — if hero folds all 4-bets, the stealer can exploit by 4-betting wider. *Rich version (M5.5).* |
| 4 | **SB vs BB split** | `NOW` | Side-by-side comparison: 3-bet frequency, fold equity, and bb/100 from SB vs BB. SB 3-bets should be more polarized (OOP vs BTN, no pot odds discount). BB 3-bets can be wider (closing the action, slightly better relative position vs SB open). If both identical, hero isn't adjusting. |
| 5 | **Trend sparkline** | `NOW` | Rolling 3-bet-vs-steal % over time. |
