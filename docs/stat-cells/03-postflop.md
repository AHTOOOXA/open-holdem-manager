# Postflop — Clickable Cells & Detail Subpage Widgets

## Left Table — By Street (Flop / Turn / River)

| # | Row | Column | drillKey |
|---|-----|--------|----------|
| 72 | C-Bet | Flop | `cbet_flop` |
| 73 | C-Bet | Turn | `cbet_turn` |
| 74 | C-Bet | River | `cbet_river` |
| 75 | Fold to CBet | Flop | `fold_to_cbet_flop` |
| 76 | Fold to CBet | Turn | `fold_to_cbet_turn` |
| 77 | Fold to CBet | River | `fold_to_cbet_river` |
| 78 | Aggression | Flop | `af_flop` |
| 79 | Aggression | Turn | `af_turn` |
| 80 | Aggression | River | `af_river` |
| 81 | Agg Freq | Flop | `afq_flop` |
| 82 | Agg Freq | Turn | `afq_turn` |
| 83 | Agg Freq | River | `afq_river` |
| 84 | Donk Bet | Flop | `donk_bet_flop` |
| 85 | Donk Bet | Turn | `donk_bet_turn` |
| 86 | Donk Bet | River | `donk_bet_river` |

## Right Table — vs C-Bet Flop (Fold / Call / Raise)

| # | Row | Column | drillKey |
|---|-----|--------|----------|
| 87 | Raised Pot | Fold | `fold_cbet_flop_raised` |
| 88 | Raised Pot | Call | `call_cbet_flop_raised` |
| 89 | Raised Pot | Raise | `raise_cbet_flop_raised` |
| 90 | 3-Bet Pot | Fold | `fold_cbet_flop_3bet` |
| 91 | 3-Bet Pot | Call | `call_cbet_flop_3bet` |
| 92 | 3-Bet Pot | Raise | `raise_cbet_flop_3bet` |

**Section total: 21 clickable cells**

---

## Phase Legend

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

### `cbet_flop` — C-Bet Flop

> Coach question: "Am I c-betting the right boards, and do I adjust for position?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Board texture breakdown** | `M5.1` | C-bet % split by board type: dry (K72r, A83r) vs wet (Ts9s8s, QJT) vs monotone. THE most important postflop insight. A player who c-bets 65% on both dry and wet boards has a massive leak — GTO cbets ~80% on dry boards but ~30-40% on wet. |
| 2 | **IP vs OOP split** | `NOW` | Two numbers side-by-side: c-bet % in position vs out of position. Modern GTO strategy c-bets 65-75% IP but only 25-40% OOP. If these numbers are similar, hero isn't adjusting — one of the most common midstakes leaks. |
| 3 | **Villain response breakdown** | `NOW` | When hero c-bets the flop: % fold / % call / % raise. If villain folds >55%, hero should c-bet more. If villain raises >15%, hero might be c-betting too many weak hands on boards that favor the caller's range. |
| 4 | **Hand strength when betting** | `M5.2` | When hero c-bets, what does hero actually have? Breakdown: Nuts+ / Strong / Top Pair / Marginal / Draw Only / Air with count, % of bets, and avg result per category. Reveals if betting range is balanced or exploitable. |
| 5 | **Sizing distribution** | `M5.3` | Flop c-bet sizes as % of pot: Tiny (<33%) / Small (33-50%) / Medium (50-66%) / Large (66-100%) / Overbet (>100%). Using the same size for all hands is balanced; varying by hand strength is a tell. |
| 6 | **Sizing x hand strength cross-tab** | `M5.2+M5.3` | Matrix: rows = hand strength (Nuts+ through Air), columns = sizing buckets. THE sizing tells detector — if hero bets small with air and big with value, the numbers show it immediately. This single widget is worth more than most others for improving a player's game. |
| 7 | **EV by action** | `NOW*` | bb/100 when hero c-bets vs checks on the flop. Reveals if hero's checks are more profitable in certain spots — high check EV with low cbet EV suggests hero should check more (common in OOP multiway pots). *Rich version (M5.5): full hand-strength x texture decision matrix.* |
| 8 | **Trend sparkline** | `NOW` | Rolling flop c-bet % over time with positional mini-bar. |

---

### `cbet_turn` — C-Bet Turn (Double Barrel)

> Coach question: "Am I following through on the turn or becoming a one-and-done c-bettor?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Continuation rate from flop** | `NOW` | "Of X flop c-bets, hero fired again on the turn Y% of the time." This is the double-barrel rate — the single most important number. Below 40% = hero gives up too easily and villains can float the flop freely knowing hero checks turn. Above 70% = hero is burning money barreling into resistance. |
| 2 | **Turn card impact** | `M5.1` | C-bet % grouped by turn card type: scare card (A, K on low board), blank (2-5 on high board), flush completer, straight completer. Reveals if hero barrels scared (shuts down on any scare card) or mindlessly (barrels blanks and scare cards at same rate). |
| 3 | **IP vs OOP split** | `NOW` | Double-barrel frequency IP vs OOP. IP double-barrels should be significantly more frequent — hero can check back and realize equity. OOP double-barrels need stronger hands since hero can't control the pot. |
| 4 | **Hand strength when betting** | `M5.2` | What hero double-barrels with: Nuts+ / Strong / Top Pair / Marginal / Draw Only / Air. Reveals if hero is only barreling strong hands (face-up) or has bluffs in the turn betting range. |
| 5 | **Sizing distribution** | `M5.3` | Turn c-bet sizes as % of pot. Turn sizing should often be larger than flop (pot is bigger, ranges narrower). |
| 6 | **EV by action** | `NOW*` | bb/100 when hero double-barrels vs checks turn after flop c-bet. Identifies whether hero is value-betting thin enough (should be positive) or overbluffing (negative). *Rich version (M5.5): full decision matrix.* |
| 7 | **Trend sparkline** | `NOW` | Rolling turn c-bet % over time. |

---

### `cbet_river` — C-Bet River (Triple Barrel)

> Coach question: "Am I value-betting thin enough and bluffing rivers with the right hands?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Showdown hand composition** | `M5.2` | When hero triple-barrels and gets called, what does hero show up with? Category breakdown: nuts/strong value / thin value / bluff. If hero NEVER shows a bluff at showdown, opponents can exploit by overfolding rivers. If hero shows mostly bluffs, opponents can exploit by calling down light. |
| 2 | **Sizing distribution** | `M5.3` | Histogram of hero's river bet sizes relative to pot (1/3, 1/2, 2/3, pot, overbet). River sizing encodes strategy: small = thin value/blocking bet, large = polarized (nuts or bluff). Using one size for everything is a leak. |
| 3 | **Sizing x hand strength cross-tab** | `M5.2+M5.3` | Matrix of hand strength by sizing buckets for river bets. Overbets should contain a mix of nuts and bluffs. If overbets are 100% value, opponents should always fold. The cross-tab exposes this. |
| 4 | **Fold equity** | `NOW` | How often villain folds to hero's river bet. River bluffs need to work often enough to break even — at 2/3 pot sizing, need ~40% folds. If villain folds 50%+, hero should bluff more. If below 35%, hero should cut bluffs and value-bet thinner. |
| 5 | **Hand strength when betting** | `M5.2` | Nuts+ / Strong / Top Pair / Marginal / Draw Only / Air distribution for all river bets (not just those that reach showdown). Shows the full betting range composition. |
| 6 | **EV by action** | `NOW*` | bb/100 for river c-bet vs check. The biggest pots, biggest decisions. Even a small EV improvement on river decisions has outsized impact on win rate. *Rich version (M5.5): full decision matrix.* |
| 7 | **Trend sparkline** | `NOW` | Rolling river c-bet % over time. |

---

### `fold_to_cbet_flop` — Fold to C-Bet Flop

> Coach question: "Am I giving up too easily on the flop and letting aggressors print money?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Stacked bar: Fold / Call / Raise when facing a flop c-bet. The full picture of how hero reacts. Fold 40-55% is normal; above 55% = overfolding (villain profits by c-betting any two). Below 35% = hero is calling/raising too light and will bleed money on later streets. |
| 2 | **By board texture** | `M5.1` | Fold % on dry boards vs wet boards vs monotone. Hero SHOULD fold more on dry boards (aggressor's range connects better, hero has fewer draws) and less on wet boards (more equity with draws and pairs). If fold rate is flat across textures, hero isn't reading the board. |
| 3 | **IP vs OOP split** | `NOW` | Fold % when hero defends IP vs OOP. Should fold less IP (positional advantage lets hero realize equity) and more OOP (harder to play postflop). If identical, hero is ignoring position. |
| 4 | **EV by response** | `NOW*` | bb/100 for fold vs call vs raise when facing flop c-bet. Reveals if hero is folding +EV calls or correctly releasing weak hands. The call EV should be slightly positive if hero is selecting the right continuing range. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-flop-cbet % over time with positional mini-bar. |

---

### `fold_to_cbet_turn` — Fold to C-Bet Turn

> Coach question: "Am I giving up on the turn after calling the flop, or defending my range properly?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / Raise vs turn c-bet. Turn decisions are bigger pots and tighter ranges. Fold 40-55% is reasonable; above 55% means hero called the flop just to fold the turn (wasted a street of investment). |
| 2 | **Turn card impact** | `M5.1` | Fold % by turn card type: scare card, blank, flush completer, paired board. Reveals if hero folds to every scare card (exploitable — villain can barrel any A or K) or adjusts based on actual equity change. |
| 3 | **Flop-to-turn attrition** | `NOW` | "Hero called X flop c-bets, then folded to Y% of turn c-bets." This flow-through rate reveals the passive leak: calling flop planning to continue, then folding turn anyway. High attrition = hero is burning flop calls for nothing. |
| 4 | **EV by response** | `NOW*` | bb/100 for fold vs call vs raise facing turn c-bet. Turn calls need to be more equity-justified since pot is bigger and one street remains. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-turn-cbet % over time with positional mini-bar. |

---

### `fold_to_cbet_river` — Fold to C-Bet River

> Coach question: "Am I getting bluffed off winners on the river, or correctly folding?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / Raise vs river c-bet. River decisions are binary: hero either has a bluff-catcher or doesn't. There's no "drawing to improve" — the hand is final. |
| 2 | **By villain bet size** | `M5.3` | Fold % vs small river bets (1/3 pot), medium (1/2-2/3), large (3/4-pot), overbets. Hero needs to call more vs small bets (better pot odds) and can fold more vs overbets. If fold rate is flat across sizes, hero is ignoring pot odds — a major exploit. Requires `pot_before_action`. |
| 3 | **W$SD when calling** | `NOW` | Win rate at showdown when hero calls the river c-bet. If >55%, hero is folding too many winners (only calling with near-nuts). If <45%, hero is calling too light. The target is ~50% — MDF-correct calling frequency. |
| 4 | **EV by response** | `NOW*` | bb/100 for fold vs call vs raise facing river bet. The highest-leverage decision — river mistakes are the costliest because pot is largest. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling fold-to-river-cbet % over time with positional mini-bar. |

---

### `af_flop` — Aggression Factor Flop

> Coach question: "Am I aggressive enough on the flop, or checking and calling too passively?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action composition** | `NOW` | Raw counts: X bets, Y raises, Z calls on the flop. AF = (bets+raises)/calls, so knowing the components reveals where the ratio comes from. Hero with 5 bets, 0 raises, 2 calls (AF=2.5) plays very differently from 2 bets, 3 raises, 2 calls (AF=2.5). |
| 2 | **IP vs OOP split** | `NOW` | AF in position vs out of position. IP play should be more aggressive (better equity realization). OOP checking is often correct — low OOP AF isn't necessarily a leak. |
| 3 | **EV: aggressive vs passive actions** | `NOW*` | bb/100 when hero bets/raises on the flop vs when hero calls/checks. If aggressive actions are much more profitable, hero should shift toward betting more. If similar, hero's passive line is fine. *Rich version (M5.5): by hand strength and texture.* |
| 4 | **By pot type** | `NOW` | AF in single-raised pots vs 3-bet pots vs limped pots. Different pot types demand different aggression levels. 3-bet pots should have lower AF (ranges are strong, less bluffing). |
| 5 | **Trend sparkline** | `NOW` | Rolling flop AF over time. |

---

### `af_turn` — Aggression Factor Turn

> Coach question: "Am I keeping up the pressure on the turn or becoming passive?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action composition** | `NOW` | Raw counts: bets / raises / calls on the turn. Turn aggression is where many players check back instead of value-betting or bluffing. |
| 2 | **Flop-to-turn aggression drop** | `NOW` | AF on flop vs AF on turn side-by-side. A large drop (e.g., AF 4 on flop -> AF 1.5 on turn) reveals hero gives up initiative on the turn — a common midstakes leak. |
| 3 | **EV: aggressive vs passive actions** | `NOW*` | bb/100 for turn bets/raises vs turn calls/checks. Turn is where pot-building happens — passive play here often leads to smaller pots that hero wins, which isn't enough to compensate for bigger pots lost. *Rich version (M5.5): by hand strength and texture.* |
| 4 | **IP vs OOP split** | `NOW` | Turn AF in position vs out of position. |
| 5 | **Trend sparkline** | `NOW` | Rolling turn AF over time. |

---

### `af_river` — Aggression Factor River

> Coach question: "Am I value-betting and bluffing rivers or just showdown-mining?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action composition** | `NOW` | Raw counts: bets / raises / calls on the river. Low river aggression (AF < 2) means hero is rarely betting the river — missing thin value and never bluffing. |
| 2 | **River bet outcomes** | `NOW` | When hero bets the river: % villain folds / % villain calls / % villain raises. Shows how villains react — high fold % means hero should bet more for thin value; high call % means hero should cut bluffs and widen value bets. |
| 3 | **Missed value estimate** | `NOW` | Hands where hero checked back the river and won at showdown. These are potential missed value bets. Count and total bb left on the table — "hero checked back X winning hands, leaving ~Y bb in uncollected value." |
| 4 | **EV: aggressive vs passive actions** | `NOW*` | bb/100 for river bets/raises vs check-backs. If bet EV is significantly higher, hero is under-betting the river. *Rich version (M5.5): by hand strength.* |
| 5 | **Trend sparkline** | `NOW` | Rolling river AF over time. |

---

### `afq_flop` — Aggression Frequency Flop

> Coach question: "What percentage of the time am I the aggressor vs passive on the flop?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action pie chart** | `NOW` | Full breakdown: bet % / raise % / call % / check-fold %. Unlike AF (ratio), AFq shows the entire decision tree including folds. Reveals if hero is check-folding too often (>30% check-fold on flop = probably overfolding). |
| 2 | **IP vs OOP split** | `NOW` | AFq in position vs out of position. IP should be significantly higher — hero should be betting/raising more when they have position. |
| 3 | **By pot type** | `NOW` | AFq in single-raised pots vs 3-bet pots vs multiway pots. Multiway pots should have lower AFq (more players = tighter betting range). Single-raised HU pots should have the highest AFq. |
| 4 | **EV by action type** | `NOW*` | bb/100 for each action category: bet, raise, call, check-fold. Shows which actions are most profitable — usually aggression pays on the flop. *Rich version (M5.5): by hand strength and texture.* |
| 5 | **Trend sparkline** | `NOW` | Rolling flop AFq over time. |

---

### `afq_turn` — Aggression Frequency Turn

> Coach question: "Am I maintaining aggression through the turn or collapsing into check-call mode?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action pie chart** | `NOW` | Bet % / raise % / call % / check-fold % on the turn. Compare to flop AFq — a sharp drop from flop to turn reveals the "one-and-done" pattern where hero bets the flop then shuts down. |
| 2 | **Flop-to-turn AFq comparison** | `NOW` | Side-by-side flop AFq vs turn AFq. Healthy play has a moderate drop (50% -> 40%). A cliff (50% -> 20%) means hero abandons aggression. Flat or rising is unusual and might mean hero is overbetting turns. |
| 3 | **IP vs OOP split** | `NOW` | Turn AFq in position vs out of position. |
| 4 | **By previous street action** | `NOW` | AFq when hero bet the flop vs when hero called the flop. Hero should be more aggressive on the turn when they were the flop aggressor (following through with initiative). |
| 5 | **Trend sparkline** | `NOW` | Rolling turn AFq over time. |

---

### `afq_river` — Aggression Frequency River

> Coach question: "Am I taking the final opportunity to bet for value or bluff, or giving up?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Action pie chart** | `NOW` | Bet % / raise % / call % / check-fold % on the river. River is the last opportunity to extract value or bluff. Low bet % means hero is giving opponents a free showdown too often. |
| 2 | **Flop->Turn->River AFq flow** | `NOW` | Three-street AFq comparison showing the full aggression trajectory. Shows whether hero maintains pressure or bleeds aggression street by street. Ideal: moderate tapering (50% -> 40% -> 30%), not a cliff. |
| 3 | **Check-back analysis** | `NOW` | When hero checks back the river: % of time hero wins at showdown. If hero wins >40% of check-backs, some of those should have been value bets. Shows the opportunity cost of passivity. |
| 4 | **IP vs OOP split** | `NOW` | River AFq in position vs out of position. IP river betting should be significantly higher — hero gets to see villain check and can bet thin value or bluff. |
| 5 | **Trend sparkline** | `NOW` | Rolling river AFq over time. |

---

### `donk_bet_flop` — Donk Bet Flop

> Coach question: "Am I leading into the preflop raiser, and is it a leak or a weapon?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **EV impact** | `NOW*` | bb/100 for hands where hero donk-bets vs checks. At lower stakes, donk-betting is almost always -EV — hero is betting out of turn against the player with the range advantage. This number alone often persuades players to stop. *Rich version (M5.5): by hand strength and texture.* |
| 2 | **Which hands (range heatmap)** | `NOW` | 13x13 grid of donk-bet combos. Reveals if hero is donking strong hands that should check-raise (sets, two pair) or weak draws that should check-call. Either way, the hands are usually played more profitably through checking. |
| 3 | **Board texture breakdown** | `M5.1` | Donk-bet frequency by board type. Some coaches argue selective donking on low, connected boards (765, 543) is defensible because the caller's range connects better. If hero donks on all board types uniformly, it's undisciplined. |
| 4 | **Sizing distribution** | `M5.3` | Flop donk-bet sizes as % of pot. Small donks (1/4-1/3 pot) are blocking bets — larger donks represent real value. Size choices reveal hero's intent. |
| 5 | **Villain response** | `NOW` | How the PFR reacts to hero's donk bet: % fold / % call / % raise. If villains raise frequently (>25%), hero's donk bets are getting punished. If they mostly call, hero might extract thin value, but raising would win more. |
| 6 | **Trend sparkline** | `NOW` | Rolling flop donk-bet % over time. |

---

### `donk_bet_turn` — Donk Bet Turn

> Coach question: "Am I leading the turn into the aggressor — delayed aggression or a leak?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **EV impact** | `NOW*` | bb/100 for turn donk bets vs checks. Turn donk-betting is rarer and more defensible than flop — it can represent a delayed check-raise or a draw that got there. *Rich version (M5.5).* |
| 2 | **Previous street context** | `NOW` | What happened on the flop: did hero check-call the flop then lead turn? Or was the flop checked through? Context determines if the turn lead is a probe bet (fine) or a donk into a flop-caller (questionable). |
| 3 | **Which hands** | `NOW` | Combo distribution of turn donk-bets. Should be either strong made hands (delayed aggression) or draws that improved. If hero donks random medium-strength hands, it's a leak. |
| 4 | **Sizing distribution** | `M5.3` | Turn donk-bet sizes as % of pot. Turn pots are bigger — sizing decisions have more financial impact. |
| 5 | **Villain response** | `NOW` | PFR's reaction: fold / call / raise. Turn pots are bigger — villain raises here are costly. |
| 6 | **Trend sparkline** | `NOW` | Rolling turn donk-bet % over time. |

---

### `donk_bet_river` — Donk Bet River

> Coach question: "Am I value-leading the river or making a costly mistake?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **EV impact** | `NOW*` | bb/100 for river donk-bets vs checks. River leading can be +EV if hero has strong value hands that villain won't bet themselves. But if hero donks thin, villain raises and hero faces a huge decision. *Rich version (M5.5).* |
| 2 | **Showdown hand composition** | `M5.2` | What hero shows up with when river donk bets get called. Should be strong value — if hero is donking bluffs on the river into the PFR, it's almost always a mistake (villain has capped range from checking previous streets). |
| 3 | **Sizing distribution** | `M5.3` | River donk-bet sizes as % of pot. Small donks (1/4-1/3 pot) are blocking bets (often a mistake). Larger donks represent real value. Size choices reveal hero's hand strength. |
| 4 | **Villain response** | `NOW` | Fold / call / raise when facing hero's river donk. High raise frequency means hero is giving villain cheap raises that turn hero's value into a bluff-catcher. |
| 5 | **Trend sparkline** | `NOW` | Rolling river donk-bet % over time. |

---

### `fold_cbet_flop_raised` — Fold to C-Bet Flop (Raised Pot)

> Coach question: "Am I defending single-raised pots correctly on the flop?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / Raise in single-raised pots specifically. Isolates SRP dynamics from 3-bet pots. SRP ranges are wider, SPR is deeper — hero should defend more aggressively than in 3-bet pots. |
| 2 | **Compare to 3-bet pot defense** | `NOW` | Side-by-side fold % in SRP vs 3-bet pot. If hero folds the same rate in both, hero is ignoring that SRP ranges are wider (more weak hands to attack) and SPR is deeper (more room to maneuver postflop). |
| 3 | **By board texture** | `M5.1` | Fold % on dry vs wet boards in SRPs. SRP boards hit the caller's range (wider) more often than 3-bet pot boards — hero should defend more on connected/middling boards. |
| 4 | **EV by response** | `NOW*` | bb/100 for fold vs call vs raise in SRPs. Since SPR is deeper, calling and raising have more room to be profitable compared to 3-bet pots. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling SRP fold-to-cbet % over time. |

---

### `call_cbet_flop_raised` — Call C-Bet Flop (Raised Pot)

> Coach question: "Am I calling flop c-bets in SRPs and then playing the turn well?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Turn behavior after calling** | `NOW` | The key metric: after calling the flop cbet, what happens on the turn? % fold-to-turn-bet / % call-turn-bet / % bet-when-checked-to. If hero folds to >50% of turn bets, the flop call was wasted — hero is "peel-and-fold." |
| 2 | **EV impact** | `NOW*` | bb/100 for hands where hero calls the flop c-bet in SRPs. Slightly negative is acceptable (hero is getting a good price). Deeply negative (<-15 bb/100) = hero is calling too wide or collapsing postflop. *Rich version (M5.5).* |
| 3 | **Showdown results** | `NOW` | W$SD for hands that called flop c-bet in SRP and reached showdown. Shows if hero arrives at showdown with competitive hands or is calling down too light. |
| 4 | **By board texture** | `M5.1` | Which boards hero calls on. Should call more on wet/connected boards (more draws, more equity) and less on dry boards (aggressor's range dominates). |
| 5 | **Trend sparkline** | `NOW` | Rolling SRP call-cbet % over time. |

---

### `raise_cbet_flop_raised` — Raise C-Bet Flop (Raised Pot)

> Coach question: "Am I check-raising the right boards with balanced hands?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Fold equity** | `NOW` | How often villain folds to the check-raise. In SRPs, villain has a wide range and will fold a lot of weak hands. If fold equity >55%, hero can check-raise bluff profitably. If <40%, hero needs mostly value. |
| 2 | **Which hands (range heatmap)** | `NOW` | Combos hero check-raises with. Should be a mix of strong made hands (sets, two pair, top pair top kicker) and semi-bluffs (flush draws, open-enders). If hero only check-raises monsters, villains can overfold. If only draws, villains can call down. |
| 3 | **Board texture breakdown** | `M5.1` | Check-raise frequency by board type. Hero should check-raise more on boards that favor the caller's range (middling, connected) and less on boards that favor the PFR (A-high, K-high dry). |
| 4 | **Hand strength distribution** | `M5.2` | What hand strength categories hero check-raises with: Nuts+ / Strong / Top Pair / Draws / Air. Shows if the check-raising range is balanced between value and bluffs. |
| 5 | **EV impact** | `NOW*` | bb/100 for check-raises vs check-calls on the same boards. Shows whether the aggressive line is more profitable. *Rich version (M5.5): full decision matrix.* |
| 6 | **Trend sparkline** | `NOW` | Rolling SRP raise-cbet % over time. |

---

### `fold_cbet_flop_3bet` — Fold to C-Bet Flop (3-Bet Pot)

> Coach question: "Am I defending 3-bet pots properly where ranges are tight and pots are big?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | Fold / Call / Raise in 3-bet pots. Ranges are much tighter — both players have strong hands. Hero should fold less than in SRPs because the hands hero brings to 3-bet pots have more equity. |
| 2 | **Compare to SRP defense** | `NOW` | Side-by-side fold % in 3-bet pot vs SRP. If hero folds MORE in 3-bet pots, it's likely a leak — hero's 3-bet/call range should be strong enough to continue on most boards. Hero is probably scared of the pot size rather than thinking about equity. |
| 3 | **By hero's role** | `NOW` | Fold % when hero was the 3-bettor (has range advantage) vs when hero called the 3-bet (range disadvantage). Hero should fold far less as the 3-bettor — they have the strongest range. |
| 4 | **EV by response** | `NOW*` | bb/100 for fold vs call vs raise in 3-bet pots. Pot is large, so mistakes are magnified. Even a 5% error in fold frequency is very costly in 3-bet pots. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling 3-bet pot fold-to-cbet % over time. |

---

### `call_cbet_flop_3bet` — Call C-Bet Flop (3-Bet Pot)

> Coach question: "Am I navigating post-flop in big 3-bet pots after calling the c-bet?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Turn play after calling** | `NOW` | After calling flop c-bet in a 3-bet pot: % fold-to-turn-bet / % call / % raise. 3-bet pots have lower SPR — hero is often pot-committed after calling flop and turn. Folding the turn after two calls is rarely correct and means hero shouldn't have called the flop. |
| 2 | **EV impact** | `NOW*` | bb/100 for calling c-bets in 3-bet pots. These are big pots — every mistake is amplified. If deeply negative, hero is either calling too wide on the flop or playing turn/river poorly. *Rich version (M5.5).* |
| 3 | **Stack commitment gauge** | `NOW` | Average % of effective stack already invested after calling the flop c-bet. Often >40% — at which point hero should rarely fold on later streets. If hero is folding later despite 40%+ commitment, the math doesn't support it. |
| 4 | **Showdown results** | `NOW` | W$SD for hands that called c-bet in 3-bet pot and reached showdown. Both players have strong ranges, so W$SD near 50% is healthy. Well below = hero is calling with the bottom of range. |
| 5 | **Trend sparkline** | `NOW` | Rolling 3-bet pot call-cbet % over time. |

---

### `raise_cbet_flop_3bet` — Raise C-Bet Flop (3-Bet Pot)

> Coach question: "Am I check-raising 3-bet pots — a high-commitment, high-stakes play?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Stack commitment after raise** | `NOW` | Average % of effective stack committed after the check-raise. In 3-bet pots, a flop check-raise often puts 60-80% of stacks in — hero is essentially committing to going all-in. This number frames whether the "raise" is really a raise or a disguised all-in. |
| 2 | **Which hands** | `M5.2` | Combo distribution with hand strength categories. In 3-bet pots, check-raise hands should be very strong: sets, top two pair, nut flush draws. Bluffs here need extreme equity (combo draws). If hero check-raises middle pair or weak draws, it's a costly mistake. |
| 3 | **Fold equity** | `NOW` | How often the c-bettor folds to the check-raise in a 3-bet pot. Usually low — both players have strong ranges and the pot is already large. Low fold equity means hero needs mostly value hands. |
| 4 | **EV impact** | `NOW*` | bb/100 for check-raising vs check-calling in 3-bet pots. High variance either way — shows if hero's check-raise targets are correct. *Rich version (M5.5): full decision matrix.* |
| 5 | **Trend sparkline** | `NOW` | Rolling 3-bet pot raise-cbet % over time. |
