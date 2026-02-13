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
| 1 | **Range heatmap** | `NOW` | 13x13 grid of steal-attempt combos. BTN should be visibly wider than SB — 40-50%+ of hands from BTN, 30-40% from SB. If both look the same, hero isn't adjusting for positional advantage postflop. *Needs "vs villain position" filter: stealing into a tight BB is different from stealing into an aggressive BB — the heatmap should be filterable by who is in the blinds (when villain tracking ships).* |
| 2 | **Fold equity (success rate)** | `NOW` | Single number: how often the steal takes the blinds uncontested. THE key driver of steal profitability. Above 55% = hero prints money stealing wide. Below 45% = steals are getting played back too often — either hero steals too much or the pool is aggressive. |
| 3 | **EV by outcome** | `NOW*` | Three bb/100 numbers: steal folds through / steal called / steal 3-bet. The fold-through line should be very positive (winning dead blinds). The called/3-bet lines show how well hero handles resistance — negative called line = postflop leak in stolen pots. *Rich version (M5.5): adds hand-strength x texture matrix.* |
| 4 | **BTN vs SB comparison** | `NOW` | Side-by-side bars showing steal %, fold equity, and bb/100 for BTN vs SB separately. BTN steals should be wider (will be IP postflop). SB steals should be more polar (OOP if BB calls). If metrics are identical, hero isn't differentiating the spots. |
| 5 | **Sizing distribution** | `M5.3` | Histogram of steal open-raise sizes as % of pot, bucketed by position (BTN vs SB). Reveals if hero varies sizing by position — BTN steals can be smaller (2-2.2x) while SB steals should be larger (2.5-3x) to deny BB odds. Requires `bet_pct_pot`. |
| 6 | **Trend sparkline** | `NOW` | Rolling steal % over time with overall reference line. *Steal frequency is high enough for a stable sparkline at 10k+ hands, but BTN/SB sub-splits will be noisy below 20k.* |
| 7 | **Postflop c-bet bridge** | `NOW` | Flop c-bet rate when steal is called, broken down by BTN vs SB. This is the most common steal transition — hero opens from a steal position, gets called, sees a flop in position (BTN) or OOP (SB). The c-bet rate and fold-to-cbet-faced rate together reveal whether hero follows through on steals or gives up postflop. A player who steals 45% but c-bets only 40% of stolen pots is bleeding the equity they built preflop. |

---

### `four_bet_fold_steal` — 4-Bet-Fold (Steal Context)

> Coach question: "Am I 4-bet bluffing from steal positions and then folding when shoved on?"

**Simplified** — this is a subset of an already rare event (4-bet-fold filtered to steal positions only). Typical sample: 3-8 instances in 50k hands. Reduced from 5 widgets to 3.

> **Consolidation candidate:** This page overlaps heavily with the general `four_bet_fold` page in `01-preflop.md`. Consider whether this needs a separate page or could be a "steal context" filter on the main `four_bet_fold` page — the coaching insight is identical ("which hands am I 4-betting then folding?"), the only difference is positional context (BTN/SB), which is already available via position filters.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money burned + rate in context** | `NOW` | Combined view: total bb lost to steal 4-bet-folds AND "X of Y total steal 4-bets ended in fold to 5-bet" with BTN vs SB position split. A single 4-bet-fold costs ~20bb, so even 3-5 instances wipe out hundreds of hands of steal profit. The rate matters: above 40-50% = too many bluffs or wrong bluff candidates; below 20% = not a meaningful leak. Position split shows whether BTN or SB is the problem — SB 4-bet-folds are more common because SB faces more 3-bets from BB. *(Merged from former widgets #1, #3, #4 — sample size is too small to justify separate widgets for each dimension.)* |
| 2 | **Which hands** | `NOW` | Combo list of what hero 4-bets then folds from steal spots. Appropriate bluffs (A5s, A4s — suited aces with blockers to AA/AK) or undisciplined hands that have no business being in a 4-bet pot? If hero is 4-bet-folding QQ+, something is deeply wrong. The key coaching comparison: do these hands have blocker value (block AA/AK/KK) or are they random? |
| 3 | **Trend sparkline** | `NOW` | Rolling 4-bet-fold frequency from steal positions over time. *Very low-frequency stat — sparkline will be pure noise below 50k hands. Gate display behind minimum sample size (e.g., 10+ occurrences).* |

---

### `fold_to_steal` — Fold vs Steal

> Coach question: "Am I giving up my blinds too easily and bleeding money passively?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Fold rate vs expected defense** | `NOW` | Hero's fold-to-steal % vs the equilibrium defense threshold for the pot odds offered. This is NOT "money forfeited" — folding is often correct, and framing every fold as lost money is misleading. The right question is: "Am I folding MORE than pot odds allow?" BB gets ~3.5:1 vs a standard 2.5x steal, so folding more than ~55-60% is overfolding. SB gets ~2.5:1, so folding more than ~65-70% is reasonable. Show the gap between hero's actual fold rate and the break-even defense frequency — that gap is the real leak size. |
| 2 | **By stealer position** | `NOW` | Fold % broken out by who is stealing — BTN, CO, or SB (for BB facing SB steal). Hero should fold LESS vs BTN/CO (wide steal ranges, better pot odds to defend) and MORE vs EP/MP opens. If fold rate is flat across all positions, hero isn't reading ranges. |
| 3 | **Defending range heatmap** | `NOW` | Inverted view: which combos hero KEEPS (call = blue, 3-bet = red) vs folds (gray). Coaches look at what's folded that shouldn't be — suited connectors and suited Ax in BB that have enough equity to defend at the pot odds offered. *Needs "vs stealer position" filter: defending range vs BTN steal (wide range, defend wider) should look very different from defending range vs CO steal (stronger range, defend tighter). Without this filter the heatmap blends two fundamentally different spots.* |
| 4 | **Fold rate by steal sizing** | `M5.3` | Hero fold % vs different steal open sizes, bucketed by `bet_pct_pot`. BB gets 3.5:1 vs a 2x steal — folding more than ~30% is overfolding. Vs a 3x steal, folding ~50% is reasonable. If hero folds the same rate regardless of sizing, they're ignoring pot odds. Requires `bet_pct_pot` to properly bucket sizing — raw BB amounts are misleading across different stake levels. *(Changed from `NOW` to `M5.3`: the raw BB bucketing in the basic version would need action amount parsing that is better deferred to the proper pot-tracking milestone.)* |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-steal % over time. |

---

### `call_steal` — Call Steal

> Coach question: "Am I defending enough by flatting, and do I play well after calling?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of steal-calling combos. BB should call wide — suited hands, connectors, Kxs, Ax — because pot odds are so favorable (3.5:1 vs standard 2.5x open). If the heatmap is sparse (only pocket pairs and suited broadways), hero is massively overfolding. *Needs "vs stealer position" filter: calling range vs BTN steal should be much wider than vs CO steal. Without this filter the heatmap blends fundamentally different spots.* |
| 2 | **EV impact** | `NOW*` | bb/100 for called steal pots. BB call-steal EV should be close to breakeven or slightly positive — BB is getting excellent pot odds (3.5:1 vs 2.5x), so hands that meet the equity threshold should be roughly +EV to defend. If deeply negative (below -15 bb/100), hero is either calling too wide or collapsing postflop. If positive, hero may be underdefending (only calling premiums). *Rich version (M5.5): adds hand-strength x texture matrix.* |
| 3 | **Postflop bridge: flop action after calling steal** | `NOW` | Street-by-street action profile in called steal pots: fold-to-cbet %, check-raise %, and donk-bet % on the flop, plus WTSD. This is where the real leak hides. Many players call steals correctly but then fold to every cbet — making the preflop call worthless. Fold-to-cbet above 55% in single-raised pots = postflop leak. Check-raise frequency below 5% = too passive (letting stealer barrel profitably). Show flop AND turn action, not just flop — a player who calls flop cbets but folds every turn barrel has the same leak, just one street later. *(Replaces old "Postflop performance" widget which used WWSF — a misleading metric here because a passive player who calls down three streets and wins at showdown has high WWSF while playing terribly.)* |
| 4 | **By stealer position** | `NOW` | Call frequency AND bb/100 broken down by stealer position (CO, BTN, SB for BB). Hero should call wider vs BTN (wider steal range = more equity for hero's defending hands) and tighter vs CO (stronger range). Critical distinction: CO steals are much stronger than BTN steals — calling the same range vs both is a clear leak. Flat call rate across positions = not adjusting. |
| 5 | **Trend sparkline** | `NOW` | Rolling call-steal % over time. |

---

### `three_bet_vs_steal` — 3-Bet vs Steal

> Coach question: "Am I fighting back against late-position aggression, and is it profitable?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of 3-bet combos vs steals. Should show a polarized range: value (TT+, AQ+) plus bluffs (suited Ax, suited connectors with good playability). If only premiums light up, hero is massively underbluffing and letting stealers print money. *Needs "vs stealer position" filter: 3-betting vs BTN steal (wide range, more bluffs appropriate) is very different from 3-betting vs CO steal (tighter range, more value-heavy). Without this filter the heatmap blends spots that require different strategies.* |
| 2 | **Fold equity by position** | `NOW` | How often the stealer folds to hero's 3-bet, broken down by SB vs BB AND by stealer position (CO vs BTN vs SB). THE key profitability driver — but a single blended number is misleading. Stealer fold-to-3bet varies enormously: a CO opener folds less (stronger range) than a BTN opener (wider range). And hero's 3-bet from SB faces different dynamics than from BB (SB is OOP to both, BB closes the action). Show the matrix: hero position x stealer position. Against weak stealers folding 60%+, hero should 3-bet bluff aggressively. Against stations calling 55%+, shift to value-heavy. *(Enhanced from single number to position matrix — the blended number hides the most actionable information.)* |
| 3 | **EV by outcome** | `NOW*` | bb/100 split three ways: 3-bet wins preflop (stealer folds), 3-bet called (goes to flop), 3-bet faces 4-bet. Fold-through should be very positive. Called line depends on postflop play. Facing 4-bet is where bluffs get tested — if hero folds all 4-bets, the stealer can exploit by 4-betting wider. *Rich version (M5.5).* |
| 4 | **SB vs BB split** | `NOW` | Side-by-side comparison: 3-bet frequency, fold equity, and bb/100 from SB vs BB. SB 3-bets should be more polarized (OOP vs BTN, no pot odds discount). BB 3-bets can be wider (closing the action, slightly better relative position vs SB open). If both identical, hero isn't adjusting. |
| 5 | **3-bet sizing distribution** | `M5.3` | Histogram of hero's 3-bet sizes vs steals, bucketed by `bet_pct_pot` and split by SB vs BB. 3-bet sizing is a critical coaching topic in steal defense: SB 3-bets should typically be larger (OOP, want to deny equity) while BB 3-bets can be slightly smaller (closing the action). Inconsistent sizing or sizing that doesn't vary by position = exploitable pattern. Requires `bet_pct_pot`. |
| 6 | **Postflop bridge: 3-bet pot played OOP** | `NOW` | When hero 3-bets a steal and gets called: flop c-bet rate, turn barrel rate, and average pot size at showdown. 3-bet pots played OOP (especially SB vs BTN) are one of the hardest spots in poker. The c-bet rate alone doesn't tell the story — show the full flop→turn→river action sequence. A player who c-bets 80% of flops but checks/folds 70% of turns is bleeding money in 3-bet pots. This is the bridge between preflop aggression and postflop follow-through. |
| 7 | **Trend sparkline** | `NOW` | Rolling 3-bet-vs-steal % over time. |
