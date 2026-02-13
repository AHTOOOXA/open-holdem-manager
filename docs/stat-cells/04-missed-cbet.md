# Missed C-Bet — Clickable Cells & Detail Subpage Widgets

## Left — Hero Missed C-Bet

| # | Label | drillKey |
|---|-------|----------|
| 93 | Missed C-Bet | `missed_cbet_flop` |
| 94 | In Position | `missed_cbet_flop_ip` |
| 95 | -> Fold (IP) | `missed_cbet_fold_ip` |
| 96 | Out of Position | `missed_cbet_flop_oop` |
| 97 | -> Fold (OOP) | `missed_cbet_fold_oop` |

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

## Phase Legend

| Phase | Dependency | Description |
|-------|-----------|-------------|
| `NOW` | None | Ships with existing `hand_players` / `actions` data |
| `M5.1` | Board texture classification | Needs `flop_texture_rank`, `flop_texture_suit`, `flop_paired` |
| `M5.2` | Hand strength evaluator | Needs `classify_hand()` at action point |
| `M5.3` | Pot tracking / bet sizing | Needs `actions.bet_pct_pot`, `pot_before_action` |
| `M5.5` | Decision analysis | EV per action with hand-strength x texture matrix |
| `NOW*` | None (basic) / M5.5 (rich) | Basic version uses `won_bb` averages; rich version after M5.5 |

---

## Detail Subpage Widgets

### `missed_cbet_flop` — Missed C-Bet (Overall)

> Coach question: "How often am I giving up the initiative after raising preflop, and does it cost me?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Board texture breakdown** | `M5.1` | Missed cbet % on dry boards (A72r) vs wet boards (Ts9s8s) vs medium texture. Checking more on wet boards is correct (less range advantage). If hero checks dry boards at the same rate as wet, they're not adjusting to texture — the most common missed-cbet leak. **This is the single most important widget on this page — board texture is the primary driver of correct check frequency.** |
| 2 | **What happens after checking** | `NOW` | Flow breakdown: after missing cbet, what % of the time does villain bet -> hero folds / hero calls / hero raises, vs villain checks -> hero bets turn / hero checks again. Shows if hero has a plan after checking or just surrenders the pot passively. |
| 3 | **EV comparison: check vs bet** | `NOW*` | bb/100 for hands where hero checked flop vs hands where hero cbet, **split by pot type (SRP vs 3BP)**. In 3-bet pots, checking is much more common and correct (ranges are tighter, SPR is lower). In single-raised pots, high check rates are more likely a leak. Conflating the two produces misleading EV numbers. *Rich version (M5.5): by hand strength and texture.* |
| 4 | **Pot type breakdown** | `NOW` | Missed cbet % in single-raised pots vs 3-bet pots vs 4-bet+ pots. This is a critical dimension — GTO missed cbet rates differ dramatically by pot type. In SRPs, hero should cbet ~55-65% overall. In 3BPs, hero might check 50-70% of boards OOP. If hero checks at the same rate in both, they aren't adjusting to pot type. `pot_type` column already exists in `hand_players`. |
| 5 | **Trend sparkline** | `NOW` | Rolling missed cbet % over time. |

> **Removed**: IP vs OOP split widget was redundant — dedicated subpages `missed_cbet_flop_ip` and `missed_cbet_flop_oop` cover this in full detail. Clicking the cell table rows is the intended navigation path.

---

### `missed_cbet_flop_ip` — Missed C-Bet In Position

> Coach question: "Am I wasting my positional advantage by checking back the flop too often?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Board texture breakdown** | `M5.1` | Which flop textures hero checks back IP. Checking back Axx dry boards IP can be correct (pot control with medium hands). Checking back draw-heavy boards IP is usually a leak — giving free cards to draws while having the initiative and position. **Board texture filtering is critical here (M5.1) — without it, this page's coaching value is limited. Prioritize this dependency.** |
| 2 | **Turn action after check-back** | `NOW` | What hero does on the turn after IP check-back: delayed cbet % / check again % / face bet %. High delayed cbet = hero had a plan (checking back to bet turn is a valid line). Checking twice IP = total surrender of initiative and position. |
| 3 | **Hand strength in checking range** | `M5.2` | Distribution of what hero checks back: sets/top pair (traps), middle pair (pot control), draws (deception), air (giving up). A healthy IP check-back range includes traps — if it's only medium/weak, villain can probe freely knowing hero is capped. |
| 4 | **Pot type breakdown** | `NOW` | IP missed cbet % in single-raised pots vs 3-bet pots. In SRPs, IP check-backs are more common (wider ranges, more medium-strength hands to pot-control). In 3BPs, ranges are narrow enough that checking back IP is often a bigger mistake — hero has a strong range and should leverage it. Different pot types demand different check-back strategies. |
| 5 | **Trend sparkline** | `NOW` | Rolling IP missed cbet % over time. |

> **Replaced**: EV impact widget was a near-duplicate of the overall page's EV comparison (widget 3 on `missed_cbet_flop`) just filtered to IP. The pot type breakdown provides a more actionable dimension that the overall page doesn't cover at this granularity.

---

### `missed_cbet_fold_ip` — Fold After Missing C-Bet (IP)

> Coach question: "After checking back, am I just giving up when they bet into me?"
>
> **Sample size warning**: This is a subset of a subset (missed cbet IP, then faced bet, then folded). Expect low sample counts. Sparkline omitted — rolling averages on rare events produce misleading noise.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money lost + proportion context** | `NOW` | Cumulative bb lost in the check-back -> face bet -> fold sequence, with proportion context: "Of all IP check-backs, hero faced a bet X% and folded Y% of those." Hero invested preflop, saw the flop with position, opted not to bet, then donated when villain attacked. The proportion tells hero whether this is a frequent leak or an edge case. |
| 2 | **Villain bet sizing faced** | `M5.3` | Fold rate by villain bet size as % of pot (1/3, 1/2, 2/3, pot). If hero folds at the same rate to all sizes, they're not considering pot odds. Folding to 1/3 pot bets is especially bad — hero is getting 4:1 and still surrendering. **Bet sizing context is essential here (M5.3) — without it, hero can't evaluate whether folds are pot-odds justified.** Requires `pot_before_action`. |
| 3 | **Board texture when folding** | `M5.1` | Which textures hero check-folds IP. Folding on dry boards where villain is likely bluffing (probing hero's capped range) is a major leak. Folding on completed-draw boards is more defensible. |
| 4 | **Which hands folded** | `M5.2` | Hand categories hero folds: if folding middle pairs, gutshots, and backdoor draws that have enough equity to continue, hero is overfolding after check-back. These hands had equity — hero should float or raise. |

> **Reduced from 5 to 4 widgets.** Merged money-lost and proportion-context into one widget. Removed trend sparkline — this stat is too low-frequency for meaningful rolling averages. Fixed "Which hands folded" phase from `NOW` to `M5.2` (requires hand strength classification).

---

### `missed_cbet_flop_oop` — Missed C-Bet Out of Position

> Coach question: "Am I checking OOP as part of a strategy, or just out of fear?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Board texture breakdown** | `M5.1` | Missed cbet % by flop texture OOP. High check rate on Kh7s2d (where hero's open-raising range dominates) is probably a leak. High check rate on Ts9s8c (where ranges are close) is often correct — modern GTO strategies range-check many wet boards OOP. **Board texture is the most critical filter for OOP missed cbet coaching — this widget is the page's anchor.** |
| 2 | **Check-raise frequency** | `NOW` | After checking OOP, how often hero check-raises vs check-calls vs check-folds. A healthy OOP checking range includes check-raises with strong hands and draws. If hero NEVER check-raises after missing cbet, the checking range is face-up weak and villain can bet with impunity. |
| 3 | **Hand strength in checking range** | `M5.2` | Does the OOP checking range include traps (sets, top pair) or only weak hands? If hero cbets all strong hands and only checks weak ones, villain can blast away whenever hero checks — exploitably unbalanced. |
| 4 | **Pot type breakdown** | `NOW` | Missed cbet % OOP in single-raised pots vs 3-bet pots. In 3BPs as the OOP 3-bettor, hero has a range advantage on most boards and should cbet more often (high card boards especially). In SRPs as the OOP raiser, range-checking wet/neutral boards is standard. If hero checks at the same rate in both pot types, that's a major strategic error — 3BP ranges are fundamentally different. |
| 5 | **Trend sparkline** | `NOW` | Rolling OOP missed cbet % over time. |

> **Replaced**: EV impact widget duplicated the overall page's EV comparison (widget 3 on `missed_cbet_flop`) just filtered to OOP. The pot type breakdown is more actionable here because OOP missed cbet strategy diverges drastically between SRP and 3BP — this is arguably the most important dimension for OOP checking decisions.

---

### `missed_cbet_fold_oop` — Fold After Missing C-Bet (OOP)

> Coach question: "After checking OOP, am I getting run over when they bet?"
>
> **Sample size warning**: This is a subset of a subset (missed cbet OOP, then faced bet, then folded). Expect low sample counts. Sparkline omitted — rolling averages on rare events produce misleading noise.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Full response distribution + money lost** | `NOW` | Stacked bar: check-fold % / check-call % / check-raise % when villain bets after hero checks OOP, plus cumulative bb lost in the check -> face bet -> fold sequence. If check-fold is above 55-60%, hero's checking range is too weak — villain can probe profitably with any two cards. The bb-lost figure makes the cost concrete. The ratio between all three responses is the key insight. |
| 2 | **Villain bet sizing faced** | `M5.3` | Fold rate by villain bet size as % of pot OOP. Small probes (1/4-1/3 pot) should get called/raised frequently (great pot odds). Folding to small bets OOP is a huge leak — villains learn to probe tiny with any two. **Bet sizing context is essential here (M5.3) — without it, hero can't evaluate whether folds are pot-odds justified.** Requires `pot_before_action`. |
| 3 | **Board texture when folding** | `M5.1` | Which boards hero check-folds OOP. Check-folding low disconnected boards (where hero's opening range should have equity advantage) indicates hero isn't defending their checking range properly. |

> **Reduced from 5 to 3 widgets.** Merged response distribution and money-lost into one widget (they tell the same story). Removed trend sparkline — this stat is too low-frequency for meaningful rolling averages. This is a rare-event page; fewer widgets with larger sample context is better than many noisy widgets.

---

### `vs_missed_cbet` — vs Missed C-Bet (Overall)

> Coach question: "When the aggressor shows weakness by checking, am I punishing them?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Response distribution** | `NOW` | What hero does when villain checks (misses cbet): bet / check-back (when IP) or lead / check (when OOP). The bet ratio is the key metric — villain checked because they're weak, and hero should exploit this a significant fraction of the time. |
| 2 | **EV: bet vs check** | `NOW*` | bb/100 when hero bets vs when hero checks in these spots, **split by pot type (SRP vs 3BP)**. In 3-bet pots, villain's check may represent a trap (ranges are stronger), so probing blindly is riskier. In SRPs, villain's check is more likely genuine weakness. Conflating pot types produces misleading EV numbers. *Rich version (M5.5): by hand strength and texture.* |
| 3 | **Bet success rate (fold equity)** | `NOW` | When hero bets vs missed cbet, how often does villain fold? If fold equity is above 50%, hero should be probing wide — villain's checking range is weak by definition. |
| 4 | **Pot type breakdown** | `NOW` | Hero's probe/lead rate in single-raised pots vs 3-bet pots. In SRPs, villain's checking range is wide and weak — hero should exploit aggressively. In 3BPs, villain may be check-trapping with strong hands, so hero should be more selective. This dimension replaces a simple IP/OOP split because pot type changes the fundamental meaning of a missed cbet. |
| 5 | **Trend sparkline** | `NOW` | Rolling exploitation rate over time. |

> **Replaced**: IP vs OOP split widget was redundant — dedicated subpages `vs_missed_cbet_bet_ip` and `vs_missed_cbet_bet_oop_turn` cover positional exploitation in full detail. Pot type breakdown is a more actionable replacement because the meaning of "villain missed cbet" differs fundamentally between SRP (wide weak range) and 3BP (possible trap).

---

### `vs_missed_cbet_bet_ip` — Bet In Position vs Missed C-Bet

> Coach question: "When they check to me showing weakness, am I attacking with the right size and frequency?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Fold equity** | `NOW` | How often villain folds to hero's IP probe after missing cbet. High fold equity = hero should probe wider with any two cards. Low fold equity = hero should tighten and use stronger hands or larger sizes. This dictates the entire strategy. |
| 2 | **Bet sizing distribution** | `M5.3` | What sizes hero uses when probing IP as % of pot: 1/4, 1/3, 1/2, 2/3, pot. Small sizes (1/4-1/3 pot) are typically optimal here — villain's range is weak, so hero doesn't need to risk much. If hero pots it every time, they're oversizing. **Bet sizing is critical for probe bet coaching — without M5.3, hero can't evaluate whether they're sizing correctly.** Requires `bet_pct_pot`. |
| 3 | **EV impact** | `NOW*` | bb/100 for IP probe bets vs checking back when villain misses cbet. Quantifies how much money hero makes (or leaves behind) by choosing to bet. *Rich version (M5.5): by hand strength and texture.* |
| 4 | **Board texture breakdown** | `M5.1` | Which textures hero probes on IP. Should probe more on boards that favor hero's range or where villain's check is weakest. Probing less on boards where villain might be trapping with check-raise. |
| 5 | **Trend sparkline** | `NOW` | Rolling IP probe bet % over time. |

> **Phase fix**: Board texture breakdown was incorrectly marked `NOW` — it requires `M5.1` (board texture classification) to categorize flops.

---

### `vs_missed_cbet_check_fold_ip` — Check-Fold IP vs Missed C-Bet

> Coach question: "Am I passing up a free stab and then folding anyway when they bet later?"
>
> **Sample size warning**: This is a rare sequence (villain misses cbet, hero checks back IP, villain bets later, hero folds). Expect very low sample counts. Sparkline omitted.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money lost + proportion context** | `NOW` | Cumulative bb lost in the sequence: villain checks (weakness), hero checks back (missed opportunity), villain bets later, hero folds. Includes proportion: "Of all IP vs-missed-cbet spots, hero bet X%, check-called Y%, and check-folded Z%." If Z is above 30-40%, hero is too passive in a highly profitable spot. The worst-case passive line — hero had two chances to win the pot and took neither. |
| 2 | **Turn card impact** | `M5.1` | Which turn cards trigger the villain bet that hero folds to. If hero folds to scare cards (flush/straight completes), that's somewhat defensible. If hero folds to blank run-outs, they should have bet the flop when villain showed weakness. |
| 3 | **Which hands check-folded** | `M5.2` | Hand categories hero check-folds with IP. If check-folding hands that had enough equity to bet the flop as a probe (any pair, any draw, any overcards), the leak is that hero should have bet earlier when villain was weakest. |

> **Reduced from 5 to 3 widgets.** Merged money-lost and proportion-context into one widget (they provide complementary framing of the same data). Removed trend sparkline — too low-frequency for meaningful rolling averages. Fixed "Turn card impact" phase from `NOW` to `M5.1` (classifying turn cards as scare/blank/completing requires board texture). Fixed "Which hands check-folded" phase from `NOW` to `M5.2` (requires hand strength evaluator).

---

### `vs_missed_cbet_bet_oop_turn` — Bet OOP Turn vs Missed C-Bet

> Coach question: "When they check twice showing extreme weakness, am I taking the pot with a delayed lead?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Fold equity (success rate)** | `NOW` | How often villain folds to hero's OOP turn lead after checking flop and turn. Two checks from the preflop aggressor = extreme weakness. Hero should win this pot at a very high rate — if fold equity is above 60%, hero should be leading wide. |
| 2 | **Bet sizing distribution** | `M5.3` | What sizes hero uses for OOP turn leads as % of pot. Small bets (1/3-1/2 pot) are typically optimal — villain has given up, hero doesn't need to risk much to take the pot. Oversizing is unnecessary and turns a cheap win into a risky proposition. **Bet sizing matters here — probing too large against a weak range risks unnecessary chips.** Requires `bet_pct_pot`. |
| 3 | **EV impact** | `NOW*` | bb/100 for OOP turn leads vs checking through. If hero never leads the turn OOP, they're giving villain infinite free equity realization — the most passive possible line when villain has already shown weakness twice. *Rich version (M5.5).* |
| 4 | **Board texture context** | `M5.1` | What boards hero leads on OOP turn. Should lead on blanks and bricks where villain's range hasn't improved. Exercise more caution on flush-completing or straight-completing turns where villain might have been trapping. |
| 5 | **Trend sparkline** | `NOW` | Rolling OOP turn lead frequency over time. **Sample size note**: this is a moderately low-frequency stat. Display hand count prominently; suppress sparkline below 30 data points. |

> **Phase fix**: Board texture context was incorrectly marked `NOW` — classifying turn cards as blanks/bricks vs completing cards requires `M5.1` (board texture classification).

---

### `vs_missed_cbet_check_fold_oop` — Check-Fold OOP vs Missed C-Bet

> Coach question: "After villain shows weakness and I'm OOP, am I still surrendering when they eventually bet?"
>
> **Sample size warning**: This is the rarest spot in the missed cbet section (villain misses cbet, hero is OOP, both check, villain bets later, hero folds). Expect very low sample counts. Sparkline omitted.

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Money lost + street breakdown** | `NOW` | Cumulative bb lost in the full surrender sequence: villain checks flop (weakness), hero checks OOP, villain bets turn/river, hero folds. Includes street breakdown: turn fold vs river fold. Check-folding turn gives up all remaining equity. Check-folding river after checking three streets means hero never contested the pot despite villain showing weakness — and still lost. Complete capitulation either way. |
| 2 | **Villain bet sizing faced** | `M5.3` | Fold rate by villain delayed bet size as % of pot. If villain probes small (1/4-1/3 pot) and hero still folds, villain is exploiting hero's passivity for cheap — they can bluff with any two cards knowing hero gives up. **Bet sizing context is essential (M5.3) — without it, hero can't distinguish between correct folds to large bets and exploitable folds to min-probes.** Requires `pot_before_action`. |
| 3 | **Which hands surrendered** | `M5.2` | Hand categories hero check-folds OOP. If folding Ace-high, small pairs, or hands with showdown value that could win by checking down, hero is being bullied out of pots they could have won passively or by leading. |

> **Reduced from 5 to 3 widgets.** Merged money-lost and street-breakdown into one widget (the street where hero folds is a detail of the money-lost story, not a separate analysis). Removed trend sparkline — too low-frequency for meaningful rolling averages. Fixed "Which hands surrendered" phase from `NOW` to `M5.2` (requires hand strength classification to categorize what hero folded).
