# Missed C-Bet — Clickable Cells & Detail Subpage Widgets

## Left — Hero Missed C-Bet

| # | Label | drillKey |
|---|-------|----------|
| 93 | Missed C-Bet | `missed_cbet_flop` |
| 94 | In Position | `missed_cbet_flop_ip` |
| 95 | → Fold (IP) | `missed_cbet_fold_ip` |
| 96 | Out of Position | `missed_cbet_flop_oop` |
| 97 | → Fold (OOP) | `missed_cbet_fold_oop` |

## Right — vs Missed C-Bet

| # | Label | drillKey |
|---|-------|----------|
| 98 | vs Missed C-Bet | `vs_missed_cbet` |
| 99 | Bet In Position | `vs_missed_cbet_bet_ip` |
| 100 | Check-Fold IP | `vs_missed_cbet_check_fold_ip` |
| 101 | Bet OOP Turn | `vs_missed_cbet_bet_oop_turn` |
| 102 | Check-Fold OOP | `vs_missed_cbet_check_fold_oop` |

**Section total: 10 clickable cells**

---

## Detail Subpage Widgets — Top 5 per Stat

### `missed_cbet_flop` — Missed C-Bet (Overall)

> Coach question: "How often am I giving up the initiative after raising preflop, and does it cost me?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Board texture breakdown** | Missed cbet % on dry boards (A72r) vs wet boards (Ts9s8s) vs medium texture. Checking more on wet boards is correct (less range advantage). If hero checks dry boards at the same rate as wet, they're not adjusting to texture — the most common missed-cbet leak. |
| 2 | **What happens after checking** | Flow breakdown: after missing cbet, what % of the time does villain bet → hero folds / hero calls / hero raises, vs villain checks → hero bets turn / hero checks again. Shows if hero has a plan after checking or just surrenders the pot passively. |
| 3 | **EV comparison: check vs bet** | bb/100 for hands where hero checked flop vs hands where hero cbet. If checking is significantly worse overall, hero is leaving money on the table. If similar on certain textures, hero may be correctly range-checking. |
| 4 | **IP vs OOP split** | Side-by-side missed cbet rate in position vs out of position. Checking IP is more often a mistake (wastes positional advantage). Checking OOP is more defensible (can check-raise, range-check strategies). If rates are equal, hero isn't adjusting for position. |
| 5 | **Trend sparkline** | Rolling missed cbet % over time. |

---

### `missed_cbet_flop_ip` — Missed C-Bet In Position

> Coach question: "Am I wasting my positional advantage by checking back the flop too often?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Board texture breakdown** | Which flop textures hero checks back IP. Checking back Axx dry boards IP can be correct (pot control with medium hands). Checking back draw-heavy boards IP is usually a leak — giving free cards to draws while having the initiative and position. |
| 2 | **Turn action after check-back** | What hero does on the turn after IP check-back: delayed cbet % / check again % / face bet %. High delayed cbet = hero had a plan (checking back to bet turn is a valid line). Checking twice IP = total surrender of initiative and position. |
| 3 | **Hand strength in checking range** | Distribution of what hero checks back: sets/top pair (traps), middle pair (pot control), draws (deception), air (giving up). A healthy IP check-back range includes traps — if it's only medium/weak, villain can probe freely knowing hero is capped. |
| 4 | **EV impact** | bb/100 for IP check-backs vs IP cbets across different board textures. Quantifies the cost of not betting by position. |
| 5 | **Trend sparkline** | Rolling IP missed cbet % over time. |

---

### `missed_cbet_fold_ip` — Fold After Missing C-Bet (IP)

> Coach question: "After checking back, am I just giving up when they bet into me?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Money lost** | Cumulative bb lost in the check-back → face bet → fold sequence. Hero invested preflop, saw the flop with position, opted not to bet, then donated when villain attacked. Every one of these is a squandered opportunity — makes the cost concrete. |
| 2 | **Villain bet sizing faced** | Fold rate by villain bet size (1/3 pot, 1/2 pot, 2/3 pot, pot). If hero folds at the same rate to all sizes, they're not considering pot odds. Folding to 1/3 pot bets is especially bad — hero is getting 4:1 and still surrendering. |
| 3 | **Board texture when folding** | Which textures hero check-folds IP. Folding on dry boards where villain is likely bluffing (probing hero's capped range) is a major leak. Folding on completed-draw boards is more defensible. |
| 4 | **Which hands folded** | Hand categories hero folds: if folding middle pairs, gutshots, and backdoor draws that have enough equity to continue, hero is overfolding after check-back. These hands had equity — hero should float or raise. |
| 5 | **Trend sparkline** | Rolling IP check-fold rate over time. |

---

### `missed_cbet_flop_oop` — Missed C-Bet Out of Position

> Coach question: "Am I checking OOP as part of a strategy, or just out of fear?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Board texture breakdown** | Missed cbet % by flop texture OOP. High check rate on Kh7s2d (where hero's open-raising range dominates) is probably a leak. High check rate on Ts9s8c (where ranges are close) is often correct — modern GTO strategies range-check many wet boards OOP. |
| 2 | **Check-raise frequency** | After checking OOP, how often hero check-raises vs check-calls vs check-folds. A healthy OOP checking range includes check-raises with strong hands and draws. If hero NEVER check-raises after missing cbet, the checking range is face-up weak and villain can bet with impunity. |
| 3 | **Hand strength in checking range** | Does the OOP checking range include traps (sets, top pair) or only weak hands? If hero cbets all strong hands and only checks weak ones, villain can blast away whenever hero checks — exploitably unbalanced. |
| 4 | **EV impact** | bb/100 for OOP checks vs OOP cbets by board texture. On some textures, checking performs comparably (validating the strategy). On others, checking is much worse (highlighting where hero should bet). |
| 5 | **Trend sparkline** | Rolling OOP missed cbet % over time. |

---

### `missed_cbet_fold_oop` — Fold After Missing C-Bet (OOP)

> Coach question: "After checking OOP, am I getting run over when they bet?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Full response distribution** | Stacked bar: check-fold % / check-call % / check-raise % when villain bets after hero checks OOP. If check-fold is above 55-60%, hero's checking range is too weak — villain can probe profitably with any two cards. The ratio between all three responses is the key insight. |
| 2 | **Money lost** | Cumulative bb lost in the check → face bet → fold sequence OOP. Hero was the preflop aggressor, had range advantage, but checked and then folded to aggression. |
| 3 | **Villain bet sizing faced** | Fold rate by villain bet size OOP. Small probes (1/4-1/3 pot) should get called/raised frequently (great pot odds). Folding to small bets OOP is a huge leak — villains learn to probe tiny with any two. |
| 4 | **Board texture when folding** | Which boards hero check-folds OOP. Check-folding low disconnected boards (where hero's opening range should have equity advantage) indicates hero isn't defending their checking range properly. |
| 5 | **Trend sparkline** | Rolling OOP check-fold rate over time. |

---

### `vs_missed_cbet` — vs Missed C-Bet (Overall)

> Coach question: "When the aggressor shows weakness by checking, am I punishing them?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Response distribution** | What hero does when villain checks (misses cbet): bet / check-back (when IP) or lead / check (when OOP). The bet ratio is the key metric — villain checked because they're weak, and hero should exploit this a significant fraction of the time. |
| 2 | **EV: bet vs check** | bb/100 when hero bets vs when hero checks in these spots. If betting is significantly more profitable, hero is being too passive and letting villain see free cards. |
| 3 | **Bet success rate (fold equity)** | When hero bets vs missed cbet, how often does villain fold? If fold equity is above 50%, hero should be probing wide — villain's checking range is weak by definition. |
| 4 | **IP vs OOP split** | Hero's exploitation rate (bet %) when IP vs OOP. Should bet more often IP (natural spot to bet after villain checks to you). OOP leading requires more caution but is still profitable against weak ranges. |
| 5 | **Trend sparkline** | Rolling exploitation rate over time. |

---

### `vs_missed_cbet_bet_ip` — Bet In Position vs Missed C-Bet

> Coach question: "When they check to me showing weakness, am I attacking with the right size and frequency?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Fold equity** | How often villain folds to hero's IP probe after missing cbet. High fold equity = hero should probe wider with any two cards. Low fold equity = hero should tighten and use stronger hands or larger sizes. This dictates the entire strategy. |
| 2 | **Bet sizing distribution** | What sizes hero uses when probing IP: 1/4, 1/3, 1/2, 2/3, pot. Small sizes (1/4-1/3 pot) are typically optimal here — villain's range is weak, so hero doesn't need to risk much. If hero pots it every time, they're oversizing against a range that's already surrendering. |
| 3 | **EV impact** | bb/100 for IP probe bets vs checking back when villain misses cbet. Quantifies how much money hero makes (or leaves behind) by choosing to bet. |
| 4 | **Board texture breakdown** | Which textures hero probes on IP. Should probe more on boards that favor hero's range or where villain's check is weakest. Probing less on boards where villain might be trapping with check-raise. |
| 5 | **Trend sparkline** | Rolling IP probe bet % over time. |

---

### `vs_missed_cbet_check_fold_ip` — Check-Fold IP vs Missed C-Bet

> Coach question: "Am I passing up a free stab and then folding anyway when they bet later?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Money lost** | Cumulative bb lost in the sequence: villain checks (weakness), hero checks back (missed opportunity), villain bets later, hero folds. The worst-case passive line — hero had two chances to win the pot (probe bet or call later bet) and took neither. |
| 2 | **Turn card impact** | Which turn cards trigger the villain bet that hero folds to. If hero folds to scare cards (flush/straight completes), that's somewhat defensible. If hero folds to blank run-outs, they should have bet the flop when villain showed weakness. |
| 3 | **Which hands check-folded** | Hand categories hero check-folds with IP. If check-folding hands that had enough equity to bet the flop as a probe (any pair, any draw, any overcards), the leak is that hero should have bet earlier when villain was weakest. |
| 4 | **Proportion context** | "Of all spots where villain missed cbet and you were IP, you bet X%, check-called Y%, and check-folded Z%." Puts the check-fold rate in proportion — if Z is above 30-40%, hero is too passive in a highly profitable spot. |
| 5 | **Trend sparkline** | Rolling IP check-fold frequency over time. |

---

### `vs_missed_cbet_bet_oop_turn` — Bet OOP Turn vs Missed C-Bet

> Coach question: "When they check twice showing extreme weakness, am I taking the pot with a delayed lead?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Fold equity (success rate)** | How often villain folds to hero's OOP turn lead after checking flop and turn. Two checks from the preflop aggressor = extreme weakness. Hero should win this pot at a very high rate — if fold equity is above 60%, hero should be leading wide. |
| 2 | **Bet sizing distribution** | What sizes hero uses for OOP turn leads. Small bets (1/3-1/2 pot) are typically optimal — villain has given up, hero doesn't need to risk much to take the pot. Oversizing is unnecessary and turns a cheap win into a risky proposition. |
| 3 | **EV impact** | bb/100 for OOP turn leads vs checking through. If hero never leads the turn OOP, they're giving villain infinite free equity realization — the most passive possible line when villain has already shown weakness twice. |
| 4 | **Board texture context** | What boards hero leads on OOP turn. Should lead on blanks and bricks where villain's range hasn't improved. Exercise more caution on flush-completing or straight-completing turns where villain might have been trapping. |
| 5 | **Trend sparkline** | Rolling OOP turn lead frequency over time. |

---

### `vs_missed_cbet_check_fold_oop` — Check-Fold OOP vs Missed C-Bet

> Coach question: "After villain shows weakness and I'm OOP, am I still surrendering when they eventually bet?"

| # | Widget | Description |
|---|--------|-------------|
| 1 | **Money lost** | Cumulative bb lost in the full surrender sequence: villain checks flop (weakness), hero checks OOP, villain bets turn/river, hero folds. Complete capitulation — hero gave maximum free cards to a weak range and then folded to delayed aggression. |
| 2 | **On which street** | Where does the fold happen — turn or river? Check-folding turn gives up all remaining equity. Check-folding river after checking three streets means hero never contested the pot despite villain showing weakness — and still lost. |
| 3 | **Villain bet sizing faced** | Fold rate by villain delayed bet size. If villain probes small (1/4-1/3 pot) and hero still folds, villain is exploiting hero's passivity for cheap — they can bluff with any two cards knowing hero gives up. |
| 4 | **Which hands surrendered** | Hand categories hero check-folds OOP. If folding Ace-high, small pairs, or hands with showdown value that could win by checking down, hero is being bullied out of pots they could have won passively or by leading. |
| 5 | **Trend sparkline** | Rolling OOP check-fold rate over time. |
