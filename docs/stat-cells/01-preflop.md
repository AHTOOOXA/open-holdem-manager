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

## Right Grid — KV (single value each)

| # | Label | drillKey | clickable |
|---|-------|----------|-----------|
| 43 | VPIP | `vpip` | yes |
| 44 | PFR | `pfr` | yes |
| 45 | 4-Bet | `four_bet` | yes |
| 46 | Limp | `limp` | yes |
| 47 | 4-Bet Range | `four_bet_range` | yes |
| 48 | Limp-Fold | `limp_fold` | yes |
| 49 | Squeeze | `squeeze` | yes |
| 50 | 4-Bet-Fold | `four_bet_fold` | yes |
| 51 | Fold to 4-Bet | `fold_to_4bet` | yes |
| 52 | Call 4-Bet | `call_4bet` | yes |
| 53 | 5-Bet | `five_bet` | yes |
| — | Win Rate | — | no |
| — | Win Rate EV | — | no |
| — | Hands | — | no |

**Section total: 53 clickable cells** (+ 3 non-clickable)

---

## Detail Subpage Widgets — Top 5 per Stat

### `open_raise` — Open Raise

> Coach question: "What am I opening, and how does the table respond?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | 13x13 combo grid colored by open-raise frequency. The single most important view — shows exactly which hands hero opens from each position. |
| 2 | **Villain response breakdown** | Stacked bar: % fold-through / % called / % 3-bet faced after hero opens. Reveals if hero is opening too wide (high 3-bet faced) or too tight (high fold-through = leaving money on table). |
| 3 | **EV by outcome** | Three bb/100 numbers: when open gets fold-through, when called, when 3-bet faced. Shows which scenarios are profitable and which are the leak. |
| 4 | **Raise sizing distribution** | Histogram of hero's open sizes (2x, 2.5x, 3x, etc.). Sizing leaks are extremely common — opening 3x from EP but 2.5x from BTN tells villains your range. |
| 5 | **Trend sparkline** | Rolling open raise % over time with overall reference line. |

---

### `fold_to_3bet` — Fold to 3-Bet

> Coach question: "Am I defending my opens properly, and with which hands?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Response distribution** | Stacked bar: Fold / Call / 4-bet split when facing a 3-bet. The core view — the ratio between these three responses matters more than any single number. |
| 2 | **Continuing range heatmap** | 13x13 grid showing which combos hero continues with (call = blue, 4-bet = red, fold = gray). Coaches look at what you KEEP, not what you fold. Shows if continuing range is balanced. |
| 3 | **EV by response** | bb/100 for each response: fold, call, 4-bet. Reveals misplayed combos — e.g., "you're folding KQs which is +EV to call." |
| 4 | **By 3-bettor position** | Breakdown of fold % by who 3-bet you (BB vs BTN vs CO). Folding 70% to a BB 3-bet is fine; folding 70% to a BTN 3-bet means you're overfolding to a wide range. |
| 5 | **Trend sparkline** | Rolling fold-to-3bet % over time. |

---

### `call_open_raise` — Call Open Raise

> Coach question: "Am I cold-calling too much instead of 3-betting or folding?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | 13x13 grid of cold-call combos. Cold-calling is the most common leak in lower-stakes play. This immediately reveals over-calling (too many suited connectors, too many offsuit broadways). |
| 2 | **EV impact** | bb/100 for cold-called pots vs all other entries. Cold-calling is often a hidden leak because the losses are small per hand but constant. |
| 3 | **Postflop WWSF** | Win rate when saw flop after cold-calling. If this is below ~40%, hero is calling preflop and then surrendering too often postflop — a classic passive leak. |
| 4 | **By opener position** | Cold-call frequency broken down by opener position. Calling vs UTG open is very different than vs CO open — should show hero adjusts (or doesn't). |
| 5 | **Trend sparkline** | Rolling cold-call % over time. |

---

### `three_bet` — 3-Bet

> Coach question: "Is my 3-bet range balanced and is it printing money?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | 13x13 grid of 3-bet combos. Should show a polarized range (premiums + suited blockers as bluffs) — if it's only AA-QQ/AK, hero is way too tight. |
| 2 | **Fold equity** | Single number: how often villain folds to hero's 3-bet. This is THE key driver of 3-bet profitability. Below 50% = hero's 3-bet bluffs are in trouble. |
| 3 | **EV by action** | bb/100 comparing 3-bet vs call vs fold for the same opportunity pool (hands where hero faced an open). The question: "Would these hands be more profitable as calls?" |
| 4 | **Showdown hand composition** | When 3-bet pots reach showdown, what does hero show up with? Pie chart or list of hand categories. Reveals if hero is only 3-betting value (no bluffs at showdown = opponents can overfold). |
| 5 | **Trend sparkline** | Rolling 3-bet % over time. |

---

### `three_bet_ip` — 3-Bet In Position

> Coach question: "Am I exploiting position by 3-betting wider than OOP?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | IP 3-betting range. Should be visibly wider than OOP — more suited connectors, more broadways. |
| 2 | **Fold equity** | Villain fold % to hero's IP 3-bet. Typically higher than OOP because villains know they'll be OOP in a 3-bet pot. |
| 3 | **EV impact** | bb/100 for IP 3-bet pots vs IP flat-call pots. Quantifies the value of 3-betting in position vs just calling. |
| 4 | **By villain open position** | 3-bet % vs EP opens vs MP opens vs CO opens. Hero should 3-bet wider against later-position opens (wider ranges) and tighter against EP opens. |
| 5 | **Trend sparkline** | Rolling IP 3-bet % over time. |

---

### `three_bet_oop` — 3-Bet Out of Position

> Coach question: "Is my OOP 3-bet range tight and linear enough to compensate for positional disadvantage?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | OOP 3-betting range. Should be tighter and more linear (strong broadways, big pairs) since hero will be OOP postflop. |
| 2 | **Fold equity** | Villain fold % to OOP 3-bet. If low, hero needs a very strong continuing range. |
| 3 | **EV impact** | bb/100 for OOP 3-bet pots. Expected to be lower than IP 3-bet pots — if it's deeply negative, hero may be 3-betting too light OOP. |
| 4 | **IP vs OOP range comparison** | Side-by-side or diff view showing how much tighter the OOP range is vs IP. The gap is a key coaching metric — if they're the same, hero isn't adjusting for position. |
| 5 | **Trend sparkline** | Rolling OOP 3-bet % over time. |

---

### `vpip` — VPIP

> Coach question: "How loose am I, and what's the composition of my entries?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | The master 13x13 range — every combo hero plays voluntarily. The most fundamental view in poker tracking. |
| 2 | **Entry type composition** | Stacked bar or pie: what fraction of VPIP is open raise / cold call / 3-bet / limp / squeeze. The COMPOSITION matters more than the VPIP number itself — 25% VPIP with 22% PFR is great; 25% VPIP with 15% PFR means 10% passive entries. |
| 3 | **Positional breakdown** | Bar chart of VPIP per position. Should show a clear staircase pattern (EP ~15%, MP ~18%, CO ~28%, BTN ~45%, SB ~35%, BB is forced). Flat = not adjusting to position. |
| 4 | **EV by entry type** | bb/100 broken down by how hero entered the pot (open raise vs cold call vs limp vs 3-bet). Immediately reveals which entry types are leaking. |
| 5 | **Trend sparkline** | Rolling VPIP over time. |

---

### `pfr` — PFR

> Coach question: "Am I raising enough preflop, or leaking through passive play?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | All combos hero raises with preflop (open raise + 3-bet + 4-bet + squeeze). |
| 2 | **VPIP-PFR gap indicator** | Single highlighted number showing the gap (VPIP minus PFR). Optimal is 4-6%. Above 8% = too much cold-calling and limping. This is the most actionable insight on this page. |
| 3 | **PFR composition** | Stacked bar: open raise % / 3-bet % / 4-bet % / squeeze % as share of total PFR. Shows WHAT KIND of raises hero makes. |
| 4 | **Positional breakdown** | PFR per position with VPIP overlay. The gap per position reveals where passive entries concentrate (often SB and BB). |
| 5 | **Trend sparkline** | Rolling PFR over time. |

---

### `four_bet` — 4-Bet

> Coach question: "Is my 4-bet range balanced between value and bluffs?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | 13x13 grid of 4-bet combos. Ideal range is ~50% value (QQ+, AKs) and ~50% bluffs (A5s, A4s — suited aces with blockers). |
| 2 | **Fold equity** | How often the 3-bettor folds to hero's 4-bet. If above 60%, hero should 4-bet bluff more. If below 40%, hero should tighten to value-heavy. |
| 3 | **Showdown hand breakdown** | Hands shown at showdown after 4-betting, categorized as premium / strong / bluff. Reveals if hero only 4-bets monsters (exploitable) or has bluffs in range. |
| 4 | **EV impact** | bb/100 for 4-bet pots vs flatting the 3-bet. Large pots magnify mistakes — even a small leak per hand is costly in 4-bet pots. |
| 5 | **Trend sparkline** | Rolling 4-bet % over time. |

---

### `limp` — Limp

> Coach question: "Why am I limping and how much is it costing me?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | Which combos hero limps with. In a good strategy this should be nearly empty — any hand worth playing is worth raising. |
| 2 | **Money lost total** | Cumulative bb lost in limped pots. A single motivational number: "you have lost X bb by limping." Makes the cost concrete. |
| 3 | **Limp-fold rate** | % of limps that end with hero folding to a raise. Pure money burn — every limp-fold is 1bb thrown away. |
| 4 | **EV comparison** | bb/100 for limped hands vs what those same hand categories earn when raised (from other sessions or positions). Shows limping is strictly dominated. |
| 5 | **Trend sparkline** | Rolling limp % over time — ideally trending toward zero. |

---

### `four_bet_range` — 4-Bet Range

> Coach question: "What percentage of all hands end up as 4-bets?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Opportunity context** | "You 4-bet X% of all hands, but had the opportunity Y% of the time. Of those opportunities, you 4-bet Z%." Disentangles frequency from opportunity. |
| 2 | **EV impact** | bb/100 for all hands that became 4-bet pots. |
| 3 | **Fold equity** | How often villain folds to the 4-bet. |
| 4 | **By position** | Where are your 4-bets coming from? Position distribution bar. |
| 5 | **Trend sparkline** | Rolling 4-bet range % over time. |

---

### `limp_fold` — Limp-Fold

> Coach question: "How much money am I literally setting on fire?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Money burned** | Total bb lost to limp-folds. This is pure waste — hero put in 1bb and got nothing back. The single most motivating number on any stat page. |
| 2 | **Which hands** | Combo list or heatmap of what hero limp-folds with. Every single one of these should either be raised or folded pre — never limped. |
| 3 | **By position** | Where are the limp-folds happening? SB limp-folds are the most common. |
| 4 | **Raise size faced** | Distribution of raise sizes hero folds to after limping. If folding to min-raises, the leak is even worse. |
| 5 | **Trend sparkline** | Rolling limp-fold % over time. |

---

### `squeeze` — Squeeze

> Coach question: "Am I squeezing enough in multiway pots where I have great fold equity?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Fold equity** | How often squeeze takes the pot preflop. Squeeze works often because multiple players need to fold — but when it works, it wins a big pot uncontested. |
| 2 | **EV impact** | bb/100 for squeeze pots. Squeezes typically have high EV because of dead money from callers. |
| 3 | **By number of callers** | Squeeze % and success rate vs 1 caller vs 2+ callers. More dead money with more callers, but also harder to get everyone to fold. |
| 4 | **By position** | Where hero squeezes from. SB/BB squeezes vs late-position squeezes have different dynamics. |
| 5 | **Trend sparkline** | Rolling squeeze % over time. |

---

### `four_bet_fold` — 4-Bet-Fold

> Coach question: "Am I throwing away big pots with 4-bet bluffs that can't handle a 5-bet?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Money burned** | Total bb lost to 4-bet-folds. These are big pots — even a few 4-bet-folds cost serious bb. The single most impactful number. |
| 2 | **Which hands** | Combos hero 4-bets then folds. Should be deliberate bluffs (A5s, A4s) not random hands. If hero is 4-bet-folding KK, something is very wrong. |
| 3 | **Rate context** | "X out of Y total 4-bets ended in fold to 5-bet" — if this is above 50%, hero's 4-bet bluffs are getting exploited. |
| 4 | **5-bet size faced** | Sizing distribution of the 5-bet hero folds to. All-in 5-bets leave no choice; small 5-bets might be bluffs worth calling. |
| 5 | **Trend sparkline** | Rolling 4-bet-fold % over time. |

---

### `fold_to_4bet` — Fold to 4-Bet

> Coach question: "Am I defending my 3-bets properly or giving up too easily?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Response distribution** | Stacked bar: Fold / Call / 5-bet split when facing a 4-bet. The full picture of how hero reacts. |
| 2 | **Continuing range heatmap** | Which combos hero continues with vs folds. Coaches check if hero is folding hands with good equity (like AQs) or correctly folding bluffs. |
| 3 | **EV by response** | bb/100 for fold vs call vs 5-bet. Reveals if hero is folding +EV spots or correctly releasing bluffs. |
| 4 | **By original 3-bet position** | Fold % broken down by where hero 3-bet from. SB 3-bet facing 4-bet should fold more (linear range); BTN 3-bet facing 4-bet has more bluffs to release. |
| 5 | **Trend sparkline** | Rolling fold-to-4bet % over time. |

---

### `call_4bet` — Call 4-Bet

> Coach question: "Is flatting 4-bets ever right, or should I always fold or 5-bet jam?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **EV impact** | bb/100 for flatted 4-bet pots. Almost always deeply negative — this number alone often convinces players to stop flatting. |
| 2 | **Showdown results** | WTSD % and W$SD % in flatted 4-bet pots. If WTSD is high but W$SD is low, hero is calling down with the worst hand in a bloated pot. |
| 3 | **Which hands** | Combo list of what hero flats 4-bets with. There's a very narrow set of hands where this is correct (some AA/KK traps, maybe AKs). Everything else should fold or 5-bet. |
| 4 | **Postflop fold-to-cbet** | How often hero folds to a cbet in flatted 4-bet pots. If high, hero is burning a huge preflop call just to fold on the flop. |
| 5 | **Trend sparkline** | Rolling call-4bet frequency over time. |

---

### `five_bet` — 5-Bet

> Coach question: "Is this only AA/KK, or do I have bluffs too?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Showdown hands** | What hero shows up with at showdown after 5-betting. If it's 100% AA/KK, hero is exploitably tight — opponents can fold everything except AA. |
| 2 | **Fold equity** | How often villain folds to the 5-bet. At most stakes, 5-bets get very high fold equity because ranges are so narrow. |
| 3 | **EV impact** | bb/100 for 5-bet pots. Should be very positive given the dead money and fold equity. |
| 4 | **All-in frequency** | % of 5-bets that are all-in vs non-all-in. At typical 100bb depth, almost all 5-bets should be jams — if hero is 5-betting small, sizing is off. |
| 5 | **Trend sparkline** | Rolling 5-bet frequency over time (very low sample — sparkline may be noisy). |
