# Stat Tooltips — Definitions & Benchmark Ranges

Tooltip text for every stat label in the app. Each entry has:
- **Tooltip**: the 1-2 sentence definition shown on hover
- **Formula**: how it's calculated
- **6-max range**: what a winning player's value typically looks like

> **Global notes:**
> - Aggregated "Total" stats blend all positions. Always interpret alongside positional breakdowns — a stat can look "normal" in aggregate while hiding positional leaks.
> - Multiway pots significantly affect optimal frequencies (c-bet, fold-to-cbet, etc.) but stats do not separate heads-up vs multiway. Interpret with caution.
> - Benchmark ranges reflect modern (2024-2025) online 6-max cash game norms. Pool-dependent — softer games may shift optimal ranges.
> - OHM stat formulas match H2N/PT4 conventions (AF, AFq, Call Open Raise, 3-Bet IP/OOP).

---

## Pre-Flop Stats

### VPIP
- **Tooltip**: Percentage of hands you voluntarily put money into the pot preflop (calls, raises — excludes posting blinds).
- **Formula**: `hands voluntarily invested / total hands dealt × 100`
- **6-max range**: 20–28% (green), <15% too tight (blue), >35% too loose (red)

### PFR
- **Tooltip**: Percentage of hands you raised preflop. A subset of VPIP — the gap between VPIP and PFR shows how often you cold-call.
- **Formula**: `hands raised preflop / total hands dealt × 100`
- **6-max range**: 16–24% (green), <12% passive (blue), >30% too aggressive (red)

### Open Raise (RFI)
- **Tooltip**: How often you raise when folded to you preflop (Raise First In). Measures your opening range by position.
- **Formula**: `times raised as first in / opportunities where folded to you × 100`
- **6-max range**: 15–30% (green), <10% too tight (blue), >40% too wide (red)

### 3-Bet
- **Tooltip**: How often you re-raise a preflop raiser. Key aggression stat — low values signal a tight/passive approach.
- **Formula**: `times 3-bet / 3-bet opportunities × 100`
- **6-max range**: 7–12% (green), <5% tight (blue), >16% too aggressive (red)

### 3-Bet IP
- **Tooltip**: 3-bet frequency when you have position on the raiser (your seat acts later postflop). Wider ranges are standard here due to positional advantage. IP/OOP is relative to the specific raiser, not fixed position groups.
- **Formula**: `times 3-bet when IP vs raiser / 3-bet opportunities when IP vs raiser × 100`
- **6-max range**: 8–14% (green)

### 3-Bet OOP
- **Tooltip**: 3-bet frequency when you're out of position vs the raiser (your seat acts earlier postflop). Tighter, more linear ranges are standard. IP/OOP is relative to the specific raiser, not fixed position groups.
- **Formula**: `times 3-bet when OOP vs raiser / 3-bet opportunities when OOP vs raiser × 100`
- **6-max range**: 5–8% (green)

### Fold to 3-Bet
- **Tooltip**: How often you fold when your open raise gets 3-bet. Too high = exploitable by light 3-bettors; too low = calling too wide.
- **Formula**: `times folded to 3-bet / times faced 3-bet × 100`
- **6-max range**: 55–65% (green), <45% loose (yellow), >70% too tight (red)

### Call Open Raise
- **Tooltip**: How often you cold-call (flat-call) a preflop raise without 3-betting. Opportunity-based — only counts hands where you faced an open raise without having already limped. Limp-calls are excluded.
- **Formula**: `times cold-called a raise / cold-call opportunities × 100` (excludes limp-calls)
- **6-max range**: 10–20% (green), >30% too passive (red)

### 4-Bet
- **Tooltip**: How often you re-raise a 3-bet preflop. Narrow ranges (premium hands + bluffs). Requires large samples for reliability.
- **Formula**: `times 4-bet / 4-bet opportunities × 100`
- **6-max range**: 3–7% (green), <2% tight (blue), >10% too aggressive (red)

### 4-Bet Range
- **Tooltip**: Approximate share of all hands you 4-bet, as a frequency (not opportunity-based). Compare with PFR to gauge how much of your raising range becomes a 4-bet.
- **Formula**: `total 4-bet hands / total hands dealt × 100` (frequency stat)
- **6-max range**: 1.5–4% (green)

### Fold to 4-Bet
- **Tooltip**: How often you fold when your 3-bet gets 4-bet. Too high = your 3-bet bluffs are too easily exploited.
- **Formula**: `times folded to 4-bet / times faced 4-bet × 100`
- **6-max range**: 55–65% (green), <45% loose (yellow), >70% too tight (red)

### 4-Bet-Fold
- **Tooltip**: How often you 4-bet then fold to a 5-bet. High values indicate many bluff 4-bets; low values indicate value-heavy 4-betting.
- **Formula**: `times 4-bet then folded to 5-bet / times 4-bet and faced 5-bet × 100`
- **6-max range**: 55–65% (green)

### 5-Bet
- **Tooltip**: How often you re-raise a 4-bet preflop. Almost always AA/KK and results in an all-in. Requires very large samples.
- **Formula**: `times 5-bet / 5-bet opportunities × 100`
- **6-max range**: 0.5–2% (green)

### Limp
- **Tooltip**: How often you enter the pot by just calling the big blind instead of raising. Includes SB completions, which inflate this stat. Strong players rarely limp in 6-max (except SB complete in some strategies).
- **Formula**: `times limped / total hands dealt × 100`
- **6-max range**: 0–5% (green, often SB completes), >8% leak (yellow), >15% major leak (red)

### Limp-Fold
- **Tooltip**: How often you limp preflop then fold when someone raises. High values indicate weak/passive tendencies.
- **Formula**: `times limped then folded to raise / total limps × 100`
- **6-max range**: lower is better (stat mainly identifies weak opponents)

### Squeeze
- **Tooltip**: How often you 3-bet when facing a raise and one or more callers. "Squeezes" out callers with dead money in the pot.
- **Formula**: `times squeezed / squeeze opportunities × 100`
- **6-max range**: 5–10% (green), <3% passive (blue), >14% too aggressive (red)

### Call 4-Bet
- **Tooltip**: How often you call (rather than fold or 5-bet) when facing a 4-bet after you 3-bet. Indicates your flatting range vs 4-bets.
- **Formula**: `times called 4-bet / times faced 4-bet × 100`
- **6-max range**: context-dependent; balanced players call ~25–40% of the time

### Win Rate
- **Tooltip**: Big blinds won per 100 hands. The fundamental measure of your profitability. Positive = winning player.
- **Formula**: `total BB won / total hands × 100`
- **6-max range**: 1–4 bb/100 solid, 5–9 very strong, 10+ elite

### Win Rate EV
- **Tooltip**: Win rate adjusted for all-in luck. Replaces actual outcomes on all-in hands with expected value based on equity. More accurate over small samples.
- **Formula**: `(EV-adjusted total BB won) / total hands × 100`
- **6-max range**: same as Win Rate; divergence from actual shows run-good/bad

---

## Steal Stats

### Steal
- **Tooltip**: How often you raise from CO, BTN, or SB when folded to you, attempting to win the blinds uncontested. Total blends all steal positions — interpret alongside positional breakdown (BTN is typically much higher).
- **Formula**: `times raised unopened from steal positions / steal opportunities × 100`
- **6-max range**: 28–42% total (green), <20% too tight (blue), >55% too wide (red). BTN alone can be 45–60%+ for winning regs.

### Fold to 3-Bet (Steal)
- **Tooltip**: How often you fold when your steal raise gets 3-bet by the blinds.
- **Formula**: `times folded to 3-bet after steal / times 3-bet after steal × 100`
- **6-max range**: 55–65% (green), >70% exploitable (red)

### 4-Bet (Steal)
- **Tooltip**: How often you 4-bet when your steal raise gets 3-bet. Shows willingness to fight back against blind defenders.
- **Formula**: `times 4-bet after steal 3-bet / times faced 3-bet after steal × 100`
- **6-max range**: 3–7% (green)

### 4-Bet-Fold (Steal)
- **Tooltip**: How often you 4-bet a steal then fold to a 5-bet. Indicates your bluff-to-value ratio in steal 4-bets.
- **Formula**: `times folded to 5-bet after steal 4-bet / total steal 4-bets × 100`
- **6-max range**: 55–65% (green)

### vs Steal: Fold
- **Tooltip**: How often you fold from the blinds when facing a steal raise from CO/BTN/SB. Too high = you're giving up too many blinds.
- **Formula**: `times folded to steal / times faced steal × 100`
- **6-max range**: 40–55% balanced; >70% exploitable (red)

### vs Steal: Call
- **Tooltip**: How often you flat-call a steal raise from the blinds. Part of your overall blind defense frequency.
- **Formula**: `times called steal / times faced steal × 100`
- **6-max range**: 20–35%

### vs Steal: 3-Bet
- **Tooltip**: How often you 3-bet from the blinds vs a steal raise. Higher values pressure wide stealers but require strong postflop play.
- **Formula**: `times 3-bet vs steal / times faced steal × 100`
- **6-max range**: 8–14% (green), <5% passive (blue), >18% too aggressive (red)

---

## Postflop Stats

### Continuation Bet (Flop)
- **Tooltip**: How often you bet the flop after being the preflop raiser. The classic "c-bet" — betting to continue representing strength.
- **Formula**: `times c-bet flop / flop c-bet opportunities × 100`
- **6-max range**: 50–70% (green), <40% too passive (blue), >80% too aggressive (red)

### Continuation Bet (Turn)
- **Tooltip**: How often you fire a second barrel on the turn after c-betting the flop. Shows follow-through aggression.
- **Formula**: `times c-bet turn / turn c-bet opportunities × 100`
- **6-max range**: 40–60% (green), <30% passive (blue), >70% too aggressive (red)

### Continuation Bet (River)
- **Tooltip**: How often you fire a third barrel on the river. Ranges are polarized by the river — this is typically lower than flop/turn c-bet.
- **Formula**: `times c-bet river / river c-bet opportunities × 100`
- **6-max range**: 35–55% (green), <25% passive (blue), >65% overbluffing (red)

### Fold to C-Bet (Flop)
- **Tooltip**: How often you fold when facing a flop c-bet. Too high = giving up too easily; too low = calling too wide.
- **Formula**: `times folded to flop c-bet / times faced flop c-bet × 100`
- **6-max range**: 40–55% (green), <30% stubborn (blue), >65% folding too much (red)

### Fold to C-Bet (Turn)
- **Tooltip**: How often you fold when facing a turn c-bet (second barrel).
- **Formula**: `times folded to turn c-bet / times faced turn c-bet × 100`
- **6-max range**: 40–55% (green), <30% stubborn (blue), >65% folding too much (red)

### Fold to C-Bet (River)
- **Tooltip**: How often you fold when facing a river c-bet (third barrel).
- **Formula**: `times folded to river c-bet / times faced river c-bet × 100`
- **6-max range**: 40–55% (green), <30% stubborn (blue), >65% folding too much (red)

### Aggression Factor (AF)
- **Tooltip**: Ratio of aggressive actions (bets + raises) to calls on a given street. Higher = more aggressive. Does not count folds. Returns blank (None) when calls = 0 (undefined ratio).
- **Formula**: `(bets + raises) / calls` (None when calls = 0)
- **6-max range**: 2–4 (green), <1.5 passive (blue), >5 hyper-aggressive (red)

### Aggression Frequency (AFq)
- **Tooltip**: Percentage of postflop actions that are aggressive (bets or raises) out of all actions including checks. Matches H2N/PT4 convention.
- **Formula**: `(bets + raises) / (bets + raises + calls + checks + folds) × 100`
- **6-max range**: 30–50% (green), <20% passive (blue), >60% too aggressive (red)

### Donk Bet (Flop/Turn/River)
- **Tooltip**: How often you lead out betting into the preflop aggressor instead of checking. Named because it's traditionally considered a weak play.
- **Formula**: `times donk bet / donk bet opportunities × 100`
- **6-max range**: 0–5% (green), >5% elevated (yellow), >15% leak (red)

### Missed C-Bet
- **Tooltip**: How often you check instead of c-betting when you had the opportunity as the preflop aggressor. The complement of your c-bet frequency.
- **Formula**: `times checked as PF aggressor / c-bet opportunities × 100`
- **6-max range**: 30–50% is balanced; >50% may indicate passivity (red)

### Missed C-Bet IP
- **Tooltip**: How often you miss the c-bet when in position. Checking back IP is a valid strategic choice to protect checking range.
- **Formula**: `times checked flop IP as PFR / flop c-bet opportunities IP × 100`
- **6-max range**: 30–50%

### Missed C-Bet OOP
- **Tooltip**: How often you miss the c-bet when out of position. Checking OOP is common in modern strategy to avoid bloating pots without position.
- **Formula**: `times checked flop OOP as PFR / flop c-bet opportunities OOP × 100`
- **6-max range**: 30–50%

### Missed C-Bet → Fold
- **Tooltip**: How often you give up after missing your c-bet. IP: fold on the turn after checking back the flop. OOP: fold on the flop or turn after checking. Note: IP and OOP versions measure different fold timings by design.
- **Formula**: IP: `times folded on turn after flop check-back / missed c-bet IP hands × 100`. OOP: `times folded on flop or turn after check / missed c-bet OOP hands × 100`
- **6-max range**: 30–50%

### vs Missed C-Bet: Bet IP
- **Tooltip**: How often you bet when the preflop raiser checks to you (probing their missed c-bet when you have position).
- **Formula**: `times bet after opponent missed c-bet IP / opportunities × 100`
- **6-max range**: 40–65%

### vs Missed C-Bet: Check-Fold IP
- **Tooltip**: How often you check back then fold after opponent's missed c-bet. Low values indicate strong play; high values indicate passivity.
- **Formula**: `times check-folded IP after missed c-bet / opportunities × 100`
- **6-max range**: 5–25%

### vs Missed C-Bet: Bet OOP Turn
- **Tooltip**: How often you probe bet the turn when out of position after the preflop aggressor checked the flop (delayed stab).
- **Formula**: `times probe bet turn OOP / probe opportunities OOP × 100`
- **6-max range**: 25–50%

### vs Missed C-Bet: Check-Fold OOP
- **Tooltip**: How often you check-fold out of position when the preflop aggressor missed their c-bet. High values indicate exploitable passivity.
- **Formula**: `times check-folded OOP / opportunities × 100`
- **6-max range**: 15–40%

### vs C-Bet Flop — Raised Pot (Fold / Call / Raise)
- **Tooltip**: How you respond to flop c-bets in single-raised pots. Split into fold, call, and raise frequencies.
- **Formula**: `action count / times faced c-bet in raised pot × 100`
- **6-max range**: Fold 40–55%, Call 25–40%, Raise 5–15%

### vs C-Bet Flop — 3-Bet Pot (Fold / Call / Raise)
- **Tooltip**: How you respond to flop c-bets in 3-bet pots. Wider defense expected due to pot odds and committed ranges.
- **Formula**: `action count / times faced c-bet in 3-bet pot × 100`
- **6-max range**: Fold 30–45%, Call 35–50%, Raise 10–25%

---

## Showdown Stats

### WTSD (Went to Showdown)
- **Tooltip**: Percentage of hands where you reached showdown after seeing the flop. Too high = calling too many streets; too low = folding too much postflop.
- **Formula**: `times went to showdown / times saw flop × 100`
- **6-max range**: 24–30% (green), <20% tight (blue), >35% calling station (red)

### W$SD (Won $ at Showdown)
- **Tooltip**: Percentage of showdowns you won. Measures how well you select hands to take to showdown.
- **Formula**: `showdowns won / total showdowns × 100`
- **6-max range**: 50–55% (green), >60% very selective (yellow), <45% poor hand reading (red)

### WWSF (Won When Saw Flop)
- **Tooltip**: Percentage of hands you won (by any means) after seeing the flop. Combines showdown and non-showdown wins.
- **Formula**: `hands won after seeing flop / hands that saw flop × 100`
- **6-max range**: 42–52% (green), >56% very aggressive or strong table selection — review with WTSD and W$SD (yellow), <38% losing too often (red)

---

## Results / Graph Stats

### Won (BB / USD)
- **Tooltip**: Total amount won or lost in big blinds (or dollars). Your bottom-line result over the filtered sample.
- **Formula**: `sum of all hand results`

### Winrate (bb/100 or $/100)
- **Tooltip**: Average profit per 100 hands. The standard measure of poker profitability over time.
- **Formula**: `total won / total hands × 100`

### $/hr
- **Tooltip**: Hourly earn rate based on your winrate and volume. Calculated from session timestamps.
- **Formula**: `total won / total hours played`

### EV Won
- **Tooltip**: How much you "should have" won based on equity when all-in. Removes luck from all-in situations.
- **Formula**: `sum of EV-adjusted results for all hands`

### EV Winrate
- **Tooltip**: All-in adjusted win rate. More stable than actual winrate over small samples — shows your true edge.
- **Formula**: `EV won / total hands × 100`

### Rake
- **Tooltip**: Total rake paid to the poker room. Taken as a percentage of each pot (capped per hand).
- **Formula**: `sum of rake across all hands`

### Rake/100
- **Tooltip**: Rake paid per 100 hands in big blinds. Your "cost of playing" — must be overcome by your edge to profit.
- **Formula**: `total rake BB / total hands × 100`
- **6-max range**: typically 2–5 bb/100 depending on stakes and site

### BBJ (Bad Beat Jackpot)
- **Tooltip**: Amount received from GGPoker's jackpot fund. Awarded when qualifying strong hands lose (e.g. quads beaten).
- **Formula**: `sum of jackpot payouts received`

### SD Won (Showdown Winnings)
- **Tooltip**: Profit from hands that went to showdown. Positive = your value hands are getting paid. Negative = poor hand selection or reads.
- **Formula**: `sum of results in hands that reached showdown`

### NSD Won (Non-Showdown Winnings)
- **Tooltip**: Profit from hands won without showdown (opponent folded). Positive = your aggression and bluffs are effective.
- **Formula**: `sum of results in hands won via fold`

### All-in EV
- **Tooltip**: Expected value of your all-in situations based on equity. Compares what you "should have" won vs what you actually won.
- **Formula**: `equity % × pot size − amount invested` (per all-in hand)

### Std Dev bb/100
- **Tooltip**: How "swingy" your results are. Lower = more consistent. Cash game average is ~80 bb/100.
- **Formula**: `standard deviation of per-hand results, scaled to per-100-hands`
- **6-max range**: 60–80 low variance, 80–120 normal, 120+ high variance

### 95% Confidence Interval
- **Tooltip**: Statistical range where your true win rate likely falls. Narrow = large sample and high certainty. If it includes 0, you may not be a proven winner yet.
- **Formula**: `winrate ± 1.96 × (std_dev / √(hands / 100))`

### Sessions
- **Tooltip**: Number of distinct playing sessions detected (gaps of 30+ minutes between hands).
- **Formula**: `count of session boundaries`

### Std Dev per hand
- **Tooltip**: Standard deviation of results per individual hand in big blinds. Used to calculate confidence intervals.
- **Formula**: `standard deviation of per-hand BB results`

### Hands/hr
- **Tooltip**: Average number of hands played per hour based on session timestamps. Rush & Cash typically runs 200-300+ hands/hr.
- **Formula**: `total hands / total session hours`

---

## Range Page Stats (per combo)

### bb/100 (combo)
- **Tooltip**: Win rate with this specific starting hand combo in big blinds per 100 hands dealt this combo.
- **Formula**: `BB won with combo / hands dealt combo × 100`

### EV bb/100 (combo)
- **Tooltip**: All-in adjusted win rate for this starting hand combo.
- **Formula**: `EV BB won with combo / hands dealt combo × 100`

### Total BB (combo)
- **Tooltip**: Total big blinds won or lost with this combo over your entire sample.
- **Formula**: `sum of BB results for all hands with this combo`

### VPIP % (combo)
- **Tooltip**: How often you voluntarily put money in the pot when dealt this combo. Shows which hands are in your playing range.
- **Formula**: `times VPIP'd with combo / times dealt combo × 100`

### Hands (combo)
- **Tooltip**: Total number of times you were dealt this starting hand combo. Small samples (<30) make stats unreliable.
- **Formula**: `count of hands dealt this combo`

---

## Cash Drop Stats

### Paid to Fund
- **Tooltip**: Total big blinds contributed to the Cash Drop pot fund by winning eligible pots. This is your "cost" of the Cash Drop feature.
- **Formula**: `sum of Cash Drop contributions from your won pots`

### Received (EV)
- **Tooltip**: Total big blinds received from Cash Drop payouts. The expected return from the Cash Drop jackpot system.
- **Formula**: `sum of Cash Drop payouts received`

### Net
- **Tooltip**: Your net profit or loss from Cash Drops (Received minus Paid). Positive = Cash Drops are profitable for you.
- **Formula**: `received − paid`

### Frequency
- **Tooltip**: How often a Cash Drop occurs, expressed as "1 in N hands." Shows the rarity of Cash Drop events.
- **Formula**: `total hands / cash drop hands`

---
---

# Corner Cases & Computation Nuances

Detailed notes on how each play stat is actually computed in OHM, edge cases that affect accuracy, and subtleties users should understand. Only covers behavioral/play stats — not results stats (Won, Rake, etc.) which are straightforward sums.

---

## Pre-Flop Stats

### VPIP
- **What counts**: Any voluntary call, raise, or bet preflop. Limping counts. Posting blinds does NOT count.
- **BB special case**: If BB checks their option (no raise came), that's NOT VPIP — they didn't voluntarily invest. If BB calls a raise or raises, that IS VPIP.
- **Straddle**: Currently not parsed as a separate concept. If a straddle appears as a "bet" action it would incorrectly count as VPIP.
- **Walk**: When everyone folds to the BB, BB has no voluntary action. Hand counts toward total but BB gets no VPIP flag. This slightly deflates BB's VPIP relative to other positions.

### PFR
- **Definition quirk**: PFR counts ALL raises preflop — open raises, 3-bets, 4-bets, 5-bets. It's not just "first raise." A player who only 3-bets (never opens) will have PFR > 0 but Open Raise = 0.
- **VPIP gap**: `VPIP - PFR` = cold-call + limp frequency. A gap > 10 points generally signals too much passive preflop play. Gap near 0 means the player rarely cold-calls.

### Open Raise (RFI)
- **Opportunity definition**: Player is dealt in and it's folded to them preflop (no raise AND no limp before them). If someone limps first, the player no longer has an open-raise opportunity — any raise would be an "iso-raise," which is tracked as a regular raise but NOT as an open raise in OHM.
- **Position matters enormously**: EP open raise of 15% and BTN open raise of 50% are both fine. The "Total" column blends all positions and is hard to interpret alone.
- **Heads-up edge case**: In 2-player pots (BTN vs BB), BTN always has an open-raise opportunity (SB posts but folds or acts first). Position labels are BTN and BB.

### 3-Bet
- **Opportunity**: Only players who act AFTER the first raiser AND before any subsequent raiser (or themselves being the 3-bettor) get a 3-bet opportunity. Players who folded before the open raise have no 3-bet opportunity.
- **Squeeze vs 3-bet**: If there's an open raise + a caller, then a re-raise, that counts as BOTH a 3-bet AND a squeeze. These are overlapping categories.
- **BB facing minraise**: BB facing a single raise has a 3-bet opportunity, but they also have a "call" option. Whether BB's raise is a "3-bet" depends on the raise count — if the open raise is the first raise, BB re-raising IS a 3-bet.
- **All-in preflop**: If a short stack shoves preflop as a 3-bet, it counts. The size doesn't matter for the flag.

### 3-Bet IP / OOP
- **Relative to raiser**: IP/OOP is determined by comparing your position to the open raiser's position using seat order (BTN > CO > MP > EP > BB > SB). If your position order is higher than the raiser's, you're IP; otherwise OOP.
- **Example**: CO 3-betting a BTN open → OOP (CO < BTN). BTN 3-betting a CO open → IP (BTN > CO). BB 3-betting any position → always OOP.
- **All 6 positions shown**: Both IP and OOP rows show all positions, since any position can be IP or OOP depending on who opened.
- **SB 3-bet**: Always OOP (SB has the lowest position order).

### Fold to 3-Bet
- **Who gets this stat**: ONLY the original open raiser. If CO opens and BTN calls, and SB 3-bets, only CO gets a fold-to-3bet opportunity. BTN facing the 3-bet is "cold 4-bet opportunity" territory, not fold-to-3bet.
- **4-bet resets it**: If CO opens, BTN 3-bets, and CO 4-bets, CO's fold_to_3bet = False (they didn't fold — they 4-bet). If CO calls the 3-bet, fold_to_3bet = False (they called).
- **Calling is not folding**: Both calling and raising set fold_to_3bet = False. Only actually folding sets it to True.

### Call Open Raise
- **Denominator**: Opportunity-based. Only hands where you faced an open raise and hadn't already limped count as opportunities. Matches H2N/PT4 convention.
- **Limp-call excluded**: If you limp and then call a raise, that's a limp-call, not a cold-call. It does NOT count as call_open_raise. The limp-call is tracked under the Limp stat instead.
- **Does NOT include**: Calling a 3-bet, calling a limp, calling anything other than the first open raise. This is specifically cold-calling an open.
- **Multiple callers**: If UTG opens and both MP and CO cold-call, both get call_open_raise = True and call_open_raise_opp = True.

### 4-Bet
- **Opportunity**: Only the original open raiser gets a 4-bet opportunity (when they face a 3-bet). Cold 4-betting (someone who wasn't the original raiser 4-bets the 3-bettor) is tracked as a regular raise/four_bet flag but the opportunity tracking is specific.
- **Sample size warning**: 4-bet situations are rare (~3-5% of hands have a 3-bet, and only the opener can 4-bet). Expect 50-100x fewer data points than VPIP. Unreliable below 500+ hands.

### 4-Bet Range
- **Frequency stat, not opportunity-based**: This is `number of times you 4-bet / total hands × 100`. NOT `4-bet / 4-bet opportunities` (that's the "4-Bet" stat). This shows what % of ALL hands you 4-bet, which gives a sense of absolute range width.
- **Naming caution**: "4-Bet Range" is non-standard terminology. Most trackers call this "4-bet ratio" or "4-bet frequency." It is NOT the same as your true combinatorial 4-bet range — it's an overall frequency approximation.
- **Relationship to PFR**: If your 4-Bet Range is 2% and PFR is 20%, you 4-bet ~10% of the hands you raise preflop.

### Fold to 4-Bet
- **Who gets this**: Only the 3-bettor when they face a 4-bet. If you 3-bet and opponent 4-bets, your options are fold/call/5-bet.
- **Null when no opportunity**: If you 3-bet and it gets called (no 4-bet), fold_to_4bet stays `None` for that hand — it doesn't count as "didn't fold."

### 4-Bet-Fold
- **What it actually measures**: Of the times you 4-bet AND subsequently faced a 5-bet, how often did you fold? This is NOT "of all 4-bets, how often did you fold" — it excludes 4-bets that got called or folded to.
- **Very small sample**: Requires the sequence open → 3-bet → 4-bet → 5-bet → fold. Extremely rare. Likely unreliable below 2000+ hands.

### 5-Bet
- **Opportunity**: Only the 3-bettor gets a 5-bet opportunity (when facing a 4-bet). The denominator is hands where you 3-bet and then faced a 4-bet.
- **Almost always all-in**: At typical 100bb stacks, a 5-bet commits most/all of your stack. This stat mostly tracks premium hand frequency.
- **Minimum viable sample**: ~5000+ hands before this stat stabilizes.

### Limp
- **Definition**: Calling the big blind when no one has raised. This is denominated against ALL hands (like VPIP), not against opportunities.
- **Limp from SB**: SB completing (calling the remaining half-blind) counts as a limp. This is the most common limp spot even for winning players.
- **BB can't limp**: BB has already posted — checking their option is NOT a limp.
- **Over-limp**: If one player limps and another calls, the second player's call of the BB also counts as a limp (both called the BB with no raise).

### Limp-Fold
- **Denominator**: Total number of hands where you limped. Of those, how many did you fold when someone raised?
- **Nuance**: If you limp, someone raises, and a third person 3-bets, and THEN you fold — that's still limp-fold (you limped, then folded preflop to subsequent aggression).

### Squeeze
- **Opportunity definition**: There must be an open raise AND at least one caller of that raise BEFORE your action. Only then is a raise from you classified as a squeeze.
- **Timing matters**: If CO opens, BTN calls, and SB raises — that's a squeeze by SB. But if CO opens and SB raises immediately (no callers yet), that's just a 3-bet, not a squeeze.
- **Overlap with 3-bet**: Every squeeze IS also a 3-bet (raise_count goes from 1 to 2). The squeeze flag is an additional tag, not a replacement.

### Call 4-Bet
- **Who it applies to**: The 3-bettor facing a 4-bet. Denominator is hands where you had a 5-bet opportunity (you 3-bet, got 4-bet).
- **Relationship to Fold to 4-Bet and 5-Bet**: `Fold to 4-Bet + Call 4-Bet + 5-Bet` should approximately sum to 100% of your responses to 4-bets. (Some rounding and edge cases may cause slight discrepancy.)

---

## Steal Stats

### Steal (ATS)
- **Steal positions**: CO, BTN, SB only. A raise from EP or MP is never considered a steal, regardless of table dynamics.
- **Requires unopened pot**: If anyone limps or raises before you, there's no steal opportunity — even if everyone folds to you afterward.
- **SB steal = SB open**: When folded to SB, their raise is both an "open raise" and a "steal attempt." These categories overlap.
- **CO steal in 6-max**: CO is the first late position. Some players argue CO opens aren't true "steals" since 3 players remain. OHM counts them per industry standard (PT4, H2N).

### Fold to 3-Bet (Steal context)
- **Subset of general Fold to 3-Bet**: This only counts hands where you steal-raised AND got 3-bet. Regular Fold to 3-Bet includes all opens, not just steals.
- **Positional columns**: BTN and SB only (CO steal → 3-bet is lumped into BTN/SB in the steal section since CO is the "other" steal position counted in Total only).

### 4-Bet (Steal context)
- **Same mechanic as general 4-Bet** but filtered to steal hands only. Your steal-raise got 3-bet, and you 4-bet back. Useful for analyzing how aggressively you defend your steals.

### vs Steal: Fold / Call / 3-Bet
- **faced_steal flag**: Only set for BB and SB when a late-position player (CO/BTN/SB) open-raises. If BTN opens, both SB and BB face a steal. If SB opens, only BB faces a steal.
- **3-bet over a steal cancels fold_to_steal**: If SB faces a BTN steal and 3-bets, fold_to_steal = False and three_bet_vs_steal = True.
- **Subsequent aggression**: If SB faces a steal, calls, and a 3-bet then happens from BB — SB's fold_to_steal is set based on whether they folded to the original steal raise specifically. If the 3-bet came later and SB folds to THAT, fold_to_steal is set to False (they didn't fold to the steal; they folded to the 3-bet).
- **SB vs BB asymmetry**: SB faces steals from CO and BTN. BB faces steals from CO, BTN, and SB. BB sees more steal opportunities and typically defends wider (better pot odds).

---

## Postflop Stats

### Continuation Bet (C-Bet)
- **Who is the "preflop aggressor"**: The LAST person to raise preflop. In a 3-bet pot, the 3-bettor is the preflop aggressor, not the original opener.
- **C-bet vs bet**: Only a "bet" (first aggressive action on the street) counts as a c-bet. If someone else bets first (donk bet) and the preflop aggressor raises, that raise is NOT a c-bet.
- **Opportunity killed by donk bet**: If any player bets INTO the preflop aggressor before they act, the c-bet opportunity is removed. The aggressor was donked into, not checked to.
- **All-in on prior street**: If the preflop aggressor is all-in from preflop, they have no flop c-bet opportunity (they can't act). Same for turn/river if all-in earlier.
- **Multiway pots**: C-bet opportunity exists regardless of how many players see the flop. C-betting into 4 players is still a c-bet. But multiway c-bet % is typically lower than heads-up — the stat doesn't distinguish.
- **Turn c-bet**: Requires that the same player c-bet the flop AND is now the "street aggressor" on the turn. If they c-bet flop, got raised, and called — they're no longer the aggressor. Turn c-bet opportunity would go to whoever raised the flop.
- **River c-bet**: Same chain — requires continuous aggression through the streets. In practice, very few hands have three consecutive c-bet opportunities.

### Fold to C-Bet
- **Only first response counted**: If you call a c-bet and then face a raise and fold, your fold-to-cbet is False (you called). OHM tracks only your FIRST response to the c-bet.
- **Multiple players**: In multiway pots, each player who faces the c-bet gets their own fold-to-cbet tracked independently.
- **Not facing a c-bet**: If the preflop aggressor checks (missed c-bet), other players don't get a fold-to-cbet entry for that street — the event didn't happen.

### Aggression Factor (AF)
- **Denominator issue**: AF = (bets + raises) / calls. When calls = 0, the formula is undefined. OHM returns None (displayed as "--") when calls = 0, matching H2N behavior.
- **Does NOT include folds or checks**: A player who bets once and folds twice has AF = undefined (1 bet / 0 calls). This is why AFq is generally more useful.
- **Per-street**: Each street has its own AF. A player might be aggressive on the flop (AF=4) but passive on the river (AF=1).
- **Check-raise counts as both**: A check-raise adds 1 to raises but the check is not counted in AF (AF doesn't track checks). However, if they check-call on another hand, that call IS counted.

### Aggression Frequency (AFq)
- **Formula**: `(bets + raises) / (bets + raises + calls + checks + folds)`. Checks are included in the denominator, matching H2N/PT4 convention.
- **Cross-tool parity**: OHM's AFq now matches PT4 and H2N. Values will be lower than the previous OHM formula (which excluded checks) by ~5-15 percentage points.

### Donk Bet
- **Definition**: Betting INTO the previous-street aggressor before they act. If BTN raised preflop and BB bets the flop before BTN acts, that's a donk bet by BB.
- **Opportunity**: Only players who act BEFORE the preflop aggressor on a given street have a donk bet opportunity. The preflop aggressor themselves can never donk bet (you can't donk bet into yourself).
- **Only the first bet counts**: If BB bets (donk) and then EP also bets... EP's action would be a raise at that point, not a donk.
- **GTO context**: Modern GTO theory has somewhat rehabilitated donk betting on specific board textures. The "always bad" reputation is outdated, but high frequencies (>15%) still usually indicate a leak.

### Missed C-Bet
- **Complement of C-Bet**: `Missed C-Bet % + C-Bet % = 100%` (for the same street, same subset of hands). If your flop c-bet is 60%, your missed c-bet is 40%.
- **Not the same as "checked"**: You can only "miss" a c-bet if you had the opportunity (you were the preflop aggressor and it was checked to you). Checking as a non-aggressor is not a "missed c-bet."
- **IP vs OOP distinction**: OHM tracks missed c-bet separately for in-position and out-of-position using the `postflop_ip` flag. IP is determined by having the highest position order among surviving players on the flop (BTN > CO > MP > EP > BB > SB).

### Missed C-Bet → Fold
- **IP version**: You checked back the flop in position (missed c-bet IP), then folded on the turn. The "fold" is on the NEXT street, not the same street.
- **OOP version**: You checked the flop out of position (missed c-bet OOP), then folded on either the flop (if opponent bet after your check) or the turn.
- **Key difference from other trackers**: Some trackers measure "fold on same street after check." OHM's IP version specifically measures "folded on turn after checking back flop," which is a slightly different (and arguably more meaningful) stat.

### vs Missed C-Bet
- **Trigger**: The preflop aggressor had a c-bet opportunity on the flop AND checked (missed_cbet_flop = True AND cbet_flop_opp = True). Only then do other players get the vs_missed_cbet_flop_opp flag.
- **Bet IP**: You're in position, opponent (PF aggressor) checked — you bet the flop. Measures probe betting frequency.
- **Check-Fold IP**: You're in position, opponent checked, you ALSO checked back — then folded on the turn when opponent bet. Measures how often you give up after both players show weakness.
- **Bet OOP Turn**: You're out of position, opponent (PF aggressor in position) checked back the flop — you bet the TURN (delayed probe). Note: this is a turn action triggered by a flop event.
- **Check-Fold OOP**: You're out of position, opponent checked back flop, you check the turn AND fold to their turn bet.

### vs C-Bet Flop — Raised Pot vs 3-Bet Pot
- **Raised pot**: Preflop saw exactly one raise (open raise, no 3-bet). Indicated by `is_3bet_pot = False`.
- **3-Bet pot**: Preflop saw a 3-bet or higher (raise_count >= 2). Indicated by `is_3bet_pot = True`.
- **Why split matters**: In 3-bet pots, ranges are narrower and the pot is larger relative to stacks, so defenders should fold less and raise more. Lumping them together masks important strategic differences.
- **Only tracks flop responses**: Turn and river responses to c-bets are not split by pot type in the current implementation.
- **Three actions should sum to ~100%**: `Fold + Call + Raise ≈ 100%` for each pot type. Some rounding and edge cases with all-ins may cause slight discrepancy.

---

## Showdown Stats

### WTSD (Went to Showdown)
- **Denominator is "saw flop"**, NOT total hands. A player who folds preflop 80% of the time but goes to showdown with all their remaining hands has WTSD = 100%, not 20%.
- **Showdown requires 2+ players**: GGPoker sometimes shows a `*** SHOWDOWN ***` section even when everyone else folded (last player standing). OHM only counts it as a real showdown when 2 or more players remain after all streets.
- **Run It Twice**: When running it twice, showdown is still counted once (not twice). The first board's results are used.

### W$SD (Won $ at Showdown)
- **Denominator is WTSD hands**: Of all hands where you went to showdown, what % did you win? A player who rarely goes to showdown but wins when they do will have high W$SD.
- **Split pots**: If two players split, BOTH get won_at_showdown = True (they collected money). This slightly inflates W$SD since split pots count as wins for both.
- **Expected baseline**: In heads-up showdowns, random chance gives 50%. In multiway showdowns, expected W$SD is lower (~33-40%). Since most showdowns are heads-up, 50% is roughly breakeven.

### WWSF (Won When Saw Flop)
- **Includes ALL wins**: Showdown wins, folds by opponents, anything that results in you having positive won_bb after seeing the flop.
- **"Won" definition**: `won_bb > 0`. Breakeven hands (won_bb = 0, e.g., you bet and everyone folds so you win your own bet back minus rake) may or may not count depending on rake.
- **Most comprehensive postflop stat**: Combines aggression (making opponents fold = NSD wins) with hand selection (winning at showdown). High WWSF requires both skills.

---

## Position & Opportunity Tracking Nuances

### Position assignment
- OHM uses fixed position labels based on table size: `POSITIONS_BY_COUNT[6] = ["BTN", "SB", "BB", "EP", "MP", "CO"]`. Assigned clockwise from the button.
- **EP in 6-max = UTG**: Early Position in 6-max is the first to act preflop (UTG). Some trackers call this "UTG" instead. OHM labels it "EP."
- **7-9 player tables**: OHM supports them with position labels like HJ (Hijack), UTG, UTG1. But GGPoker Rush & Cash is always 6-max, so these are rarely seen.
- **Heads-up (2 players)**: BTN = SB (posts small blind, acts first preflop but last postflop). BB posts big blind.

### Postflop IP (In Position)
- Determined AFTER preflop folds — only among players who see the flop. The player with the highest position order (BTN > CO > MP > EP > BB > SB) among flop survivors is tagged `postflop_ip = True`. All others get `postflop_ip = False`.
- **Changes with folds**: If BTN folds preflop, CO becomes the IP player postflop. The IP flag is per-hand, not per-position.
- **Multiway nuance**: In a 3+ player pot, only ONE player is marked as IP (the one closest to the button). The others are all OOP. This is a simplification — in reality, "middle position" players are IP relative to earlier positions but OOP relative to later ones.

### Opportunity flags (three_bet_opp, steal_opp, etc.)
- **Only set when the situation arises**: If no one open-raises, nobody gets three_bet_opp. If UTG raises and BTN immediately 3-bets, only players between UTG and BTN (inclusive) get three_bet_opp.
- **Order matters**: Players who acted and folded BEFORE the open raise don't get a 3-bet opportunity (they already folded). Only players who act AFTER the open get the opportunity.
- **None vs False**: OHM uses `None` for "no opportunity" and `True`/`False` for "had opportunity, did/didn't take it." This distinction is critical for accurate percentage calculations — `None` values are excluded from denominators.

### Sample size concerns by stat
| Stat | Minimum reliable sample | Why |
|------|------------------------|-----|
| VPIP, PFR | 100 hands | Every hand is an opportunity |
| Open Raise | 200 hands | ~60-70% of hands have an RFI opportunity |
| 3-Bet | 500 hands | Only ~25-30% of hands have a 3-bet opportunity |
| Fold to 3-Bet | 500 hands | Only when you open and get 3-bet (~5-10% of hands) |
| 4-Bet | 1000 hands | ~3-5% of hands have a 4-bet opportunity |
| C-Bet | 300 hands | ~25-30% of hands you're the PF aggressor on the flop |
| Steal | 300 hands | ~30-40% of hands you're in a steal position |
| WTSD, W$SD | 500 hands | ~25% of hands see a flop |
| Fold to 4-Bet | 2000 hands | Very rare situation |
| 5-Bet | 5000+ hands | Almost never comes up |
| 4-Bet-Fold | 5000+ hands | Requires open → 3-bet → 4-bet → 5-bet → fold |
| Squeeze | 1000 hands | Requires open + caller before your action |

### Rush & Cash specifics
- **No table selection**: Rush & Cash moves you to a new table each hand. Position stats are true random — no "always playing the same table" bias.
- **Anonymous opponents**: Opponent stats (if ever added) would need to handle players being anonymous or rotating. Currently OHM only tracks hero stats.
- **Faster session accumulation**: 200-300+ hands/hr means stats stabilize faster than regular cash games (~30 hands/hr per table).
