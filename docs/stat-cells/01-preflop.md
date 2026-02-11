# Pre-Flop — Clickable Cells & Detail Subpage Widgets

## Left Table — Positional (Tot / EP / MP / CO / BTN / SB / BB)

| # | Row | Column | drillKey | position param |
|---|-----|--------|----------|----------------|
| 1 | Open Raise | Tot | `open_raise` | — |
| 2 | Open Raise | EP | `open_raise` | `ep` |
| 3 | Open Raise | MP | `open_raise` | `mp` |
| 4 | Open Raise | CO | `open_raise` | `co` |
| 5 | Open Raise | BTN | `open_raise` | `btn` |
| 6 | Open Raise | SB | `open_raise` | `sb` |
| 7 | Open Raise | BB | `open_raise` | `bb` |
| 8 | Fold to 3-Bet | Tot | `fold_to_3bet` | — |
| 9 | Fold to 3-Bet | EP | `fold_to_3bet` | `ep` |
| 10 | Fold to 3-Bet | MP | `fold_to_3bet` | `mp` |
| 11 | Fold to 3-Bet | CO | `fold_to_3bet` | `co` |
| 12 | Fold to 3-Bet | BTN | `fold_to_3bet` | `btn` |
| 13 | Fold to 3-Bet | SB | `fold_to_3bet` | `sb` |
| 14 | Fold to 3-Bet | BB | `fold_to_3bet` | `bb` |
| 15 | Call Open | Tot | `call_open_raise` | — |
| 16 | Call Open | EP | `call_open_raise` | `ep` |
| 17 | Call Open | MP | `call_open_raise` | `mp` |
| 18 | Call Open | CO | `call_open_raise` | `co` |
| 19 | Call Open | BTN | `call_open_raise` | `btn` |
| 20 | Call Open | SB | `call_open_raise` | `sb` |
| 21 | Call Open | BB | `call_open_raise` | `bb` |
| 22 | 3-Bet | Tot | `three_bet` | — |
| 23 | 3-Bet | EP | `three_bet` | `ep` |
| 24 | 3-Bet | MP | `three_bet` | `mp` |
| 25 | 3-Bet | CO | `three_bet` | `co` |
| 26 | 3-Bet | BTN | `three_bet` | `btn` |
| 27 | 3-Bet | SB | `three_bet` | `sb` |
| 28 | 3-Bet | BB | `three_bet` | `bb` |
| 29 | 3-Bet IP | Tot | `three_bet_ip` | — |
| 30 | 3-Bet IP | EP | `three_bet_ip` | `ep` |
| 31 | 3-Bet IP | MP | `three_bet_ip` | `mp` |
| 32 | 3-Bet IP | CO | `three_bet_ip` | `co` |
| 33 | 3-Bet IP | BTN | `three_bet_ip` | `btn` |
| 34 | 3-Bet IP | SB | `three_bet_ip` | `sb` |
| 35 | 3-Bet IP | BB | `three_bet_ip` | `bb` |
| 36 | 3-Bet OOP | Tot | `three_bet_oop` | — |
| 37 | 3-Bet OOP | EP | `three_bet_oop` | `ep` |
| 38 | 3-Bet OOP | MP | `three_bet_oop` | `mp` |
| 39 | 3-Bet OOP | CO | `three_bet_oop` | `co` |
| 40 | 3-Bet OOP | BTN | `three_bet_oop` | `btn` |
| 41 | 3-Bet OOP | SB | `three_bet_oop` | `sb` |
| 42 | 3-Bet OOP | BB | `three_bet_oop` | `bb` |

> **Future simplification note:** The 14 positional cells for 3-Bet IP (#29-35) and 3-Bet OOP (#36-42) are candidates for consolidation into a single IP/OOP toggle on the main 3-Bet detail page. Position already determines IP/OOP in almost every case ("3-Bet IP from BB" is nearly impossible). The Tot rows are valuable; the 7-position breakdown for each is low signal. Flag for future UI refactor — don't delete cells yet, but plan to replace with a filter.

## Right Grid — KV (single value each)

| # | Label | drillKey | clickable |
|---|-------|----------|-----------|
| 43 | VPIP | `vpip` | yes |
| 44 | PFR | `pfr` | yes |
| 45 | 4-Bet | `four_bet` | yes |
| 46 | Limp | `limp` | yes |
| ~~47~~ | ~~4-Bet Range~~ | ~~`four_bet_range`~~ | ~~yes~~ |
| 47 | BB Defense | `bb_defense` | yes |
| 48 | Limp-Fold | `limp_fold` | yes |
| 49 | Squeeze | `squeeze` | yes |
| 50 | 4-Bet-Fold | `four_bet_fold` | yes |
| 51 | Fold to 4-Bet | `fold_to_4bet` | yes |
| 52 | Call 4-Bet | `call_4bet` | yes |
| 53 | 5-Bet | `five_bet` | yes |
| 54 | Iso Raise | `iso_raise` | yes |
| 55 | Fold to Squeeze | `fold_to_squeeze` | yes |
| — | Win Rate | — | no |
| — | Win Rate EV | — | no |
| — | Hands | — | no |

> **Merged:** `four_bet_range` absorbed into `four_bet` — its opportunity context widget (#1) is now widget #6 on the `four_bet` detail page.

**Section total: 55 clickable cells** (+ 3 non-clickable)

---

## Phase Legend

Every widget is tagged with a build phase:

| Phase | Dependency | Description |
|-------|-----------|-------------|
| `NOW` | None | Ships with existing `hand_players` / `actions` data |
| `M5.1` | Board texture classification | Needs `flop_texture_rank`, `flop_texture_suit`, `flop_paired` |
| `M5.2` | Hand strength evaluator | Needs `classify_hand()` at action point |
| `M5.3` | Pot tracking / bet sizing | Needs `actions.bet_pct_pot`, `pot_before_action` |
| `M5.2+M5.3` | Both hand strength + sizing | Cross-tab of hand strength by bet size |
| `M5.5` | Decision analysis | EV per action with hand-strength x texture matrix |
| `NOW*` | None (basic) / M5.5 (rich) | Basic version uses `won_bb` averages; rich version after M5.5 |

---

## Detail Subpage Widgets

### `open_raise` — Open Raise

> Coach question: "What am I opening, and how does the table respond?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 combo grid colored by open-raise frequency. The single most important view — shows exactly which hands hero opens from each position. |
| 2 | **Villain response breakdown** | `NOW` | Stacked bar: % fold-through / % called / % 3-bet faced after hero opens. Reveals if hero is opening too wide (high 3-bet faced) or too tight (high fold-through = leaving money on table). |
| 3 | **EV by outcome** | `NOW*` | Three bb/100 numbers: when open gets fold-through, when called, when 3-bet faced. Shows which scenarios are profitable and which are the leak. *Rich version (M5.5): adds hand-strength x texture matrix.* |
| 4 | **Raise sizing distribution** | `NOW` | Histogram of hero's open sizes (2x, 2.5x, 3x, etc.) as raw BB amounts. Sizing leaks are extremely common — opening 3x from EP but 2.5x from BTN tells villains your range. |
| 5 | **Sizing as % pot** | `M5.3` | Upgrade of widget #4: buckets open sizes as % of pot (requires `bet_pct_pot`). Shows whether hero's sizing is consistent relative to pot geometry. |
| 6 | **Trend sparkline** | `NOW` | Rolling open raise % over time with overall reference line. |

---

### `fold_to_3bet` — Fold to 3-Bet

> Coach question: "Am I defending my opens properly, and with which hands?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Stacked bar: Fold / Call / 4-bet split when facing a 3-bet. The core view — the ratio between these three responses matters more than any single number. |
| 2 | **Continuing range heatmap** | `NOW` | 13x13 grid showing which combos hero continues with (call = blue, 4-bet = red, fold = gray). Coaches look at what you KEEP, not what you fold. Shows if continuing range is balanced. |
| 3 | **EV by response** | `NOW*` | bb/100 for each response: fold, call, 4-bet. Reveals misplayed combos — e.g., "you're folding KQs which is +EV to call." *Basic version uses `won_bb` averages. Rich version (M5.5): adds hand-strength x texture decision matrix.* |
| 4 | **By 3-bettor position** | `NOW` | Breakdown of fold % by who 3-bet you (BB vs BTN vs CO). Folding 70% to a BB 3-bet is fine; folding 70% to a BTN 3-bet means you're overfolding to a wide range. |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-3bet % over time. |

---

### `call_open_raise` — Call Open Raise

> Coach question: "Am I cold-calling too much instead of 3-betting or folding?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of cold-call combos. Cold-calling is the most common leak in lower-stakes play. This immediately reveals over-calling (too many suited connectors, too many offsuit broadways). |
| 2 | **EV impact** | `NOW*` | bb/100 for cold-called pots vs all other entries. Cold-calling is often a hidden leak because the losses are small per hand but constant. *Rich version (M5.5): EV by hand strength category.* |
| 3 | **Postflop WWSF** | `NOW` | Win rate when saw flop after cold-calling. If this is below ~40%, hero is calling preflop and then surrendering too often postflop — a classic passive leak. |
| 4 | **By opener position** | `NOW` | Cold-call frequency broken down by opener position. Calling vs UTG open is very different than vs CO open — should show hero adjusts (or doesn't). |
| 5 | **Trend sparkline** | `NOW` | Rolling cold-call % over time. |

---

### `three_bet` — 3-Bet

> Coach question: "Is my 3-bet range balanced and is it printing money?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of 3-bet combos. Should show a polarized range (premiums + suited blockers as bluffs) — if it's only AA-QQ/AK, hero is way too tight. |
| 2 | **Fold equity** | `NOW` | Single number: how often villain folds to hero's 3-bet. This is THE key driver of 3-bet profitability. Below 50% = hero's 3-bet bluffs are in trouble. |
| 3 | **EV by action** | `NOW*` | bb/100 comparing 3-bet vs call vs fold for the same opportunity pool (hands where hero faced an open). The question: "Would these hands be more profitable as calls?" *Rich version (M5.5): full decision analysis.* |
| 4 | **Showdown hand composition** | `M5.2` | When 3-bet pots reach showdown, what does hero show up with? Pie chart or list of hand categories. Reveals if hero is only 3-betting value (no bluffs at showdown = opponents can overfold). |
| 5 | **3-bet pot postflop bridge** | `NOW` | When hero 3-bets and gets called: c-bet rate + average SPR going to flop. Connects preflop 3-bet decisions to postflop consequences — "you 3-bet and then cbet only 40% of the time" reveals a preflop/postflop disconnect. |
| 6 | **Trend sparkline** | `NOW` | Rolling 3-bet % over time. |

---

### `three_bet_ip` — 3-Bet In Position

> Coach question: "Am I exploiting position by 3-betting wider than OOP?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | IP 3-betting range. Should be visibly wider than OOP — more suited connectors, more broadways. |
| 2 | **Fold equity** | `NOW` | Villain fold % to hero's IP 3-bet. Typically higher than OOP because villains know they'll be OOP in a 3-bet pot. |
| 3 | **EV impact** | `NOW*` | bb/100 for IP 3-bet pots vs IP flat-call pots. Quantifies the value of 3-betting in position vs just calling. *Rich version (M5.5).* |
| 4 | **By villain open position** | `NOW` | 3-bet % vs EP opens vs MP opens vs CO opens. Hero should 3-bet wider against later-position opens (wider ranges) and tighter against EP opens. |
| 5 | **Trend sparkline** | `NOW` | Rolling IP 3-bet % over time. |

---

### `three_bet_oop` — 3-Bet Out of Position

> Coach question: "Is my OOP 3-bet range tight and linear enough to compensate for positional disadvantage?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | OOP 3-betting range. Should be tighter and more linear (strong broadways, big pairs) since hero will be OOP postflop. |
| 2 | **Fold equity** | `NOW` | Villain fold % to OOP 3-bet. If low, hero needs a very strong continuing range. |
| 3 | **EV impact** | `NOW*` | bb/100 for OOP 3-bet pots. Expected to be lower than IP 3-bet pots — if it's deeply negative, hero may be 3-betting too light OOP. *Rich version (M5.5).* |
| 4 | **IP vs OOP range comparison** | `NOW` | Side-by-side or diff view showing how much tighter the OOP range is vs IP. The gap is a key coaching metric — if they're the same, hero isn't adjusting for position. |
| 5 | **Trend sparkline** | `NOW` | Rolling OOP 3-bet % over time. |

---

### `vpip` — VPIP

> Coach question: "How loose am I, and what's the composition of my entries?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | The master 13x13 range — every combo hero plays voluntarily. The most fundamental view in poker tracking. |
| 2 | **Entry type composition** | `NOW` | Stacked bar or pie: what fraction of VPIP is open raise / cold call / 3-bet / limp / squeeze. The COMPOSITION matters more than the VPIP number itself — 25% VPIP with 22% PFR is great; 25% VPIP with 15% PFR means 10% passive entries. Sub-metric: **Multiway pot frequency** — how often hero ends up in 3+ player pots. Usually a sign of too much cold-calling or overlimping. |
| 3 | **Positional breakdown** | `NOW` | Bar chart of VPIP per position. Should show a clear staircase pattern (EP ~15%, MP ~18%, CO ~28%, BTN ~45%, SB ~35%, BB is forced). Flat = not adjusting to position. |
| 4 | **EV by entry type** | `NOW*` | bb/100 broken down by how hero entered the pot (open raise vs cold call vs limp vs 3-bet). Immediately reveals which entry types are leaking. *Rich version (M5.5): adds hand-strength dimension.* |
| 5 | **Trend sparkline** | `NOW` | Rolling VPIP over time. |

---

### `pfr` — PFR

> Coach question: "Am I raising enough preflop, or leaking through passive play?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | All combos hero raises with preflop (open raise + 3-bet + 4-bet + squeeze). |
| 2 | **VPIP-PFR gap indicator** | `NOW` | Single highlighted number showing the gap (VPIP minus PFR). Optimal is 4-6%. Above 8% = too much cold-calling and limping. This is the most actionable insight on this page. |
| 3 | **PFR composition** | `NOW` | Stacked bar: open raise % / 3-bet % / 4-bet % / squeeze % as share of total PFR. Shows WHAT KIND of raises hero makes. |
| 4 | **Positional breakdown** | `NOW` | PFR per position with VPIP overlay. The gap per position reveals where passive entries concentrate (often SB and BB). |
| 5 | **Trend sparkline** | `NOW` | Rolling PFR over time. |

---

### `four_bet` — 4-Bet

> Coach question: "Is my 4-bet range balanced between value and bluffs?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of 4-bet combos. Ideal range is ~50% value (QQ+, AKs) and ~50% bluffs (A5s, A4s — suited aces with blockers). |
| 2 | **Fold equity** | `NOW` | How often the 3-bettor folds to hero's 4-bet. If above 60%, hero should 4-bet bluff more. If below 40%, hero should tighten to value-heavy. |
| 3 | **Showdown hand breakdown** | `M5.2` | Hands shown at showdown after 4-betting, categorized as premium / strong / bluff. Reveals if hero only 4-bets monsters (exploitable) or has bluffs in range. |
| 4 | **EV impact** | `NOW*` | bb/100 for 4-bet pots vs flatting the 3-bet. Large pots magnify mistakes — even a small leak per hand is costly in 4-bet pots. *Rich version (M5.5).* |
| 5 | **Trend sparkline** | `NOW` | Rolling 4-bet % over time. |
| 6 | **Opportunity context** | `NOW` | *(Merged from `four_bet_range`.)* "You 4-bet X% of all hands, but had the opportunity Y% of the time. Of those opportunities, you 4-bet Z%." Disentangles frequency from opportunity. By-position distribution bar. |

---

### `limp` — Limp

> Coach question: "Why am I limping and how much is it costing me?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | Which combos hero limps with. In a good strategy this should be nearly empty — any hand worth playing is worth raising. |
| 2 | **Money lost total** | `NOW` | Cumulative bb lost in limped pots. A single motivational number: "you have lost X bb by limping." Makes the cost concrete. |
| 3 | **Limp-fold rate** | `NOW` | % of limps that end with hero folding to a raise. Pure money burn — every limp-fold is 1bb thrown away. |
| 4 | **EV comparison** | `NOW*` | bb/100 for limped hands vs what those same hand categories earn when raised (from other sessions or positions). Shows limping is strictly dominated. *Rich version (M5.5).* |
| 5 | **Trend sparkline** | `NOW` | Rolling limp % over time — ideally trending toward zero. |

---

### ~~`four_bet_range`~~ — DEPRECATED → merged into `four_bet`

> **Merged:** The `four_bet_range` stat is absorbed into `four_bet`. Its useful widget (opportunity context — "4-bet as % of all hands vs % of opportunities") is now widget #6 on the `four_bet` detail page. This cell is removed from the grid and replaced by `bb_defense`.

---

### `limp_fold` — Limp-Fold

> Coach question: "How much money am I literally setting on fire?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money burned** | `NOW` | Total bb lost to limp-folds. This is pure waste — hero put in 1bb and got nothing back. The single most motivating number on any stat page. |
| 2 | **Which hands** | `NOW` | Combo list or heatmap of what hero limp-folds with. Every single one of these should either be raised or folded pre — never limped. |
| 3 | **By position** | `NOW` | Where are the limp-folds happening? SB limp-folds are the most common. |
| 4 | **Raise size faced** | `NOW` | Distribution of raise sizes hero folds to after limping (raw BB amounts). If folding to min-raises, the leak is even worse. *Enhanced version (M5.3): buckets by `bet_pct_pot` for proper relative sizing display.* |
| 5 | **Trend sparkline** | `NOW` | Rolling limp-fold % over time. |

---

### `squeeze` — Squeeze

> Coach question: "Am I squeezing enough in multiway pots where I have great fold equity?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Fold equity** | `NOW` | How often squeeze takes the pot preflop. Squeeze works often because multiple players need to fold — but when it works, it wins a big pot uncontested. |
| 2 | **EV impact** | `NOW*` | bb/100 for squeeze pots. Squeezes typically have high EV because of dead money from callers. *Rich version (M5.5).* |
| 3 | **By number of callers** | `NOW` | Squeeze % and success rate vs 1 caller vs 2+ callers. More dead money with more callers, but also harder to get everyone to fold. |
| 4 | **By position** | `NOW` | Where hero squeezes from. SB/BB squeezes vs late-position squeezes have different dynamics. |
| 5 | **Trend sparkline** | `NOW` | Rolling squeeze % over time. |

---

### `four_bet_fold` — 4-Bet-Fold

> Coach question: "Am I throwing away big pots with 4-bet bluffs that can't handle a 5-bet?"

**Simplified** — sample sizes are tiny (3-8 instances typically). Reduced from 5 widgets to 3.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money burned** | `NOW` | Total bb lost to 4-bet-folds. These are big pots — even a few 4-bet-folds cost serious bb. The single most impactful number. |
| 2 | **Which hands** | `NOW` | Combos hero 4-bets then folds. Should be deliberate bluffs (A5s, A4s) not random hands. If hero is 4-bet-folding KK, something is very wrong. |
| 3 | **Trend sparkline** | `NOW` | Rolling 4-bet-fold % over time. |

---

### `fold_to_4bet` — Fold to 4-Bet

> Coach question: "Am I defending my 3-bets properly or giving up too easily?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Stacked bar: Fold / Call / 5-bet split when facing a 4-bet. The full picture of how hero reacts. |
| 2 | **Continuing range heatmap** | `NOW` | Which combos hero continues with vs folds. Coaches check if hero is folding hands with good equity (like AQs) or correctly folding bluffs. |
| 3 | **EV by response** | `NOW*` | bb/100 for fold vs call vs 5-bet. Reveals if hero is folding +EV spots or correctly releasing bluffs. *Rich version (M5.5).* |
| 4 | **By original 3-bet position** | `NOW` | Fold % broken down by where hero 3-bet from. SB 3-bet facing 4-bet should fold more (linear range); BTN 3-bet facing 4-bet has more bluffs to release. |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-4bet % over time. |

---

### `call_4bet` — Call 4-Bet

> Coach question: "Is flatting 4-bets ever right, or should I always fold or 5-bet jam?"

**Simplified** — sample sizes are 5-15 hands. Reduced from 5 widgets to 3.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **EV impact** | `NOW` | bb/100 for flatted 4-bet pots. Almost always deeply negative — this number alone often convinces players to stop flatting. |
| 2 | **Which hands** | `NOW` | Combo list of what hero flats 4-bets with. There's a very narrow set of hands where this is correct (some AA/KK traps, maybe AKs). Everything else should fold or 5-bet. |
| 3 | **Trend sparkline** | `NOW` | Rolling call-4bet frequency over time. |

---

### `five_bet` — 5-Bet

> Coach question: "Is this only AA/KK, or do I have bluffs too?"

**Simplified** — ~10 instances in 100k hands. Reduced from 5 widgets to 3.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Showdown hands** | `NOW` | What hero shows up with at showdown after 5-betting. If it's 100% AA/KK, hero is exploitably tight — opponents can fold everything except AA. |
| 2 | **EV impact** | `NOW` | bb/100 for 5-bet pots. Should be very positive given the dead money and fold equity. |
| 3 | **Trend sparkline** | `NOW` | Rolling 5-bet frequency over time (very low sample — sparkline may be noisy). |

---

## New Stats

### `bb_defense` — BB Defense Rate

> Coach question: "How often do I fold the BB to a raise, and am I bleeding money passively?"

One of the top 3 things every coach looks at. At low-mid stakes, players fold BB 70%+ and bleed money.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / 3-bet split when facing a raise in the BB. The core view — these three ratios determine whether hero is a profitable or losing BB player. |
| 2 | **Defending range heatmap** | `NOW` | 13x13 grid of hands hero continues with from BB (call = blue, 3-bet = red, fold = gray). BB gets 2.5-3.5:1 pot odds — the range should be wide. If only pocket pairs and suited broadways light up, hero is massively overfolding. |
| 3 | **EV by response** | `NOW*` | bb/100 for fold vs call vs 3-bet from BB. Reveals if hero is folding +EV spots. At pot odds of 3.5:1, many hands that "feel weak" have enough equity to defend. *Rich version (M5.5): by hand strength and board texture.* |
| 4 | **By raiser position** | `NOW` | Defense rate broken down by who opened (EP through SB). Folding 80% vs UTG is fine (strong range). Folding 80% vs BTN is a massive leak (wide range, great pot odds). If flat across positions, hero isn't reading ranges. |
| 5 | **Trend sparkline** | `NOW` | Rolling BB defense % over time. |

---

### `iso_raise` — Isolation Raise

> Coach question: "Am I iso-raising limpers, and with what?"

Raising after one or more limpers — NOT an open raise. Different spot, different ranges, different sizing. In any pool below NL200, limps happen constantly.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Range heatmap** | `NOW` | 13x13 grid of iso-raise combos. Should be wider than open-raise range because of dead money from limpers. |
| 2 | **By number of limpers** | `NOW` | Iso-raise frequency vs 1 limper vs 2+ limpers. More dead money but worse equity realization multiway. |
| 3 | **Sizing distribution** | `NOW` | Histogram of iso-raise sizes (raw BB amounts). Standard is open size + 1bb per limper — deviations are tells. *Enhanced version (M5.3): buckets by `bet_pct_pot`.* |
| 4 | **EV impact** | `NOW*` | bb/100 for iso-raised pots vs limped-along pots vs folded. Quantifies the value of isolating. *Rich version (M5.5).* |
| 5 | **Trend sparkline** | `NOW` | Rolling iso-raise % over time. |

---

### `fold_to_squeeze` — Fold to Squeeze

> Coach question: "When I open and get squeezed, am I defending properly or surrendering my dead money?"

Hero opens, gets called, faces a squeeze — what happens? This is a real spot that occurs regularly in 6-max. We track hero's squeeze play but not the defensive side.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / 4-bet split when facing a squeeze. The core defensive view. |
| 2 | **Continuing range heatmap** | `NOW` | Which combos hero defends with vs folds when squeezed. Should include more of hero's open-raising range than fold-to-3bet since there's more dead money in the pot. |
| 3 | **EV by response** | `NOW*` | bb/100 for each response. Folding is often correct — but folding too much lets squeezers print money. *Rich version (M5.5).* |
| 4 | **By squeezer position** | `NOW` | Fold rate by who squeezed. Folding to a BB squeeze (likely wide) is different than folding to a UTG cold 4-bet (very strong). |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-squeeze % over time. |
