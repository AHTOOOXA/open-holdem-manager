# Stat Click Interface — Per-Stat Reference

> Every stat cell on the Stats page is clickable. This document defines what each stat shows in the detail panel when clicked.

---

## How The Detail Panel Works

When a stat is clicked, the right panel shows:

1. **Header**: Stat name, overall % (action_count / opportunity_count)
2. **Position tabs** (if `isPositional`): All | EP | MP | CO | BTN | SB | BB — filters the hand list
3. **Analysis widgets** (conditional by stat type):
   - `range_heatmap` — 13x13 combo grid showing which hands hero plays for this action
   - `response_distribution` — Fold / Call / Raise stacked bar (defensive stats only)
   - `positional_bar` — Mini horizontal bars per position (postflop stats without positional table)
   - `trend_sparkline` — Rolling stat value over time
4. **Hand explorer**: Condensed table (cards, PF actions, board, key street actions, result, date). Click row → HandDrawer.
5. **"Open in Hand Explorer"** link → `/hands?stat_key=...&pos=...`

**Key street** determines which street's actions are highlighted in the hand table:
- Preflop stats → preflop actions
- Flop stats → flop actions
- Turn stats → turn actions
- River stats → river actions
- Showdown stats → last non-empty street

---

## Section 1: PRE-FLOP

### Left Table (Positional Columns: Tot / EP / MP / CO / BTN / SB / BB)

---

#### `open_raise` — Open Raise

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | `hp.open_raise_opp = TRUE` (folded to hero preflop) |
| **Action** | `hp.open_raise = TRUE` (hero raised) |
| **Benchmark (total)** | 15–30% |
| **Positional benchmarks** | EP: 12–18%, MP: 15–22%, CO: 22–35%, BTN: 38–55%, SB: 30–50% |

**What you see**: Range heatmap showing which combos hero opens from each position. Trend sparkline showing open raise % over time. Hand list of all hands where hero had the opportunity to open and did (or didn't).

---

#### `fold_to_3bet` — Fold to 3-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | response_distribution, range_heatmap, trend_sparkline |
| **Opportunity** | `hp.fold_to_3bet IS NOT NULL` (hero faced a 3-bet) |
| **Action** | `hp.fold_to_3bet = TRUE` (hero folded) |
| **Response decomp** | Fold: `fold_to_3bet = TRUE`, Call: remainder, Raise: `four_bet = TRUE` |
| **Benchmark** | 55–65% |

**What you see**: Response distribution bar (fold / call / 4-bet split). Range heatmap showing which combos hero folds vs. continues with. Trend sparkline. Hand list filtered to hands where hero faced a 3-bet.

---

#### `call_open_raise` — Call Open Raise

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | None (all hands) |
| **Action** | `hp.call_open_raise = TRUE` |
| **Benchmark** | None |

**What you see**: Range heatmap showing which combos hero cold-calls with by position. Useful for identifying over-calling leaks.

---

#### `three_bet` — 3-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | `hp.three_bet_opp = TRUE` (hero faced an open raise) |
| **Action** | `hp.three_bet = TRUE` |
| **Benchmark** | 6–10% |

**What you see**: Range heatmap of hero's 3-betting range by position. Critical for evaluating if 3-bet range is balanced (value + bluffs).

---

#### `three_bet_ip` — 3-Bet IP

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | `hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = TRUE` |
| **Action** | `hp.three_bet = TRUE` |
| **Benchmark** | None |

**What you see**: 3-bet range specifically when hero is in position. Should be wider than OOP.

---

#### `three_bet_oop` — 3-Bet OOP

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | `hp.three_bet_opp = TRUE AND hp.three_bet_opp_ip = FALSE` |
| **Action** | `hp.three_bet = TRUE` |
| **Benchmark** | None |

**What you see**: 3-bet range when hero is out of position. Should be tighter and more linear than IP.

---

### Right KV Grid (Non-Positional Stats)

---

#### `vpip` — VPIP

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | All hands |
| **Action** | `hp.vpip = TRUE` (hero voluntarily put money in) |
| **Benchmark** | 20–28% |

**What you see**: The master range heatmap — every combo hero plays voluntarily. The most fundamental stat. Trend shows if hero is tightening or loosening over time.

---

#### `pfr` — PFR

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | All hands |
| **Action** | `hp.pfr = TRUE` (hero raised preflop) |
| **Benchmark** | 16–24% |

**What you see**: Range heatmap of all combos hero raises with preflop. VPIP minus PFR = passive entries (cold calls, limps). Gap should be 4–6%.

---

#### `four_bet` — 4-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | `hp.four_bet_opp = TRUE` (hero faced a 3-bet after opening) |
| **Action** | `hp.four_bet = TRUE` |
| **Benchmark** | 3–7% |

**What you see**: 4-bet range heatmap. Should be ~50% value (QQ+, AKs) and ~50% bluffs (A5s, A4s).

---

#### `fold_to_4bet` — Fold to 4-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | response_distribution, range_heatmap, trend_sparkline |
| **Opportunity** | `hp.fold_to_4bet IS NOT NULL` |
| **Action** | `hp.fold_to_4bet = TRUE` |
| **Response decomp** | Fold: `fold_to_4bet = TRUE`, Call: remainder, Raise: `five_bet = TRUE` |
| **Benchmark** | 55–65% |

**What you see**: Response distribution (fold / call / 5-bet). Range heatmap of what hero folds vs. continues with facing 4-bet.

---

#### `limp` — Limp

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | range_heatmap, trend_sparkline |
| **Opportunity** | All hands |
| **Action** | `hp.limp = TRUE` |
| **Benchmark** | None |

**What you see**: Range heatmap showing which combos hero open-limps with. Ideally very few — limping is generally a leak.

---

#### `squeeze` — Squeeze

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.squeeze_opp = TRUE` (open + call in front of hero) |
| **Action** | `hp.squeeze = TRUE` |
| **Benchmark** | None |

**What you see**: Trend sparkline only. Hand list of squeeze opportunities.

---

#### `five_bet` — 5-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.five_bet_opp = TRUE` |
| **Action** | `hp.five_bet = TRUE` |
| **Benchmark** | None |

**What you see**: Trend sparkline. Rare stat — very few opportunities. Hand list of 5-bet spots.

---

#### `four_bet_range` — 4-Bet Range

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | All hands |
| **Action** | `hp.four_bet = TRUE` |
| **Benchmark** | None |

**What you see**: % of all hands where hero 4-bet (not % of opportunities). Shows how often 4-bets happen overall.

---

#### `limp_fold` — Limp-Fold

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.limp = TRUE` (hero limped) |
| **Action** | `hp.limp = TRUE AND hp.saw_flop IS NOT TRUE` (limped then folded to raise) |
| **Benchmark** | None |

**What you see**: How often hero limps and folds to a raise. High = burning money with open limps.

---

#### `four_bet_fold` — 4-Bet-Fold

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.four_bet = TRUE` |
| **Action** | `hp.four_bet = TRUE AND hp.saw_flop IS NOT TRUE` (4-bet then folded to 5-bet) |
| **Benchmark** | None |

**What you see**: How often hero 4-bets then folds to a 5-bet. High = 4-bet bluffs getting picked off.

---

#### `call_4bet` — Call 4-Bet

| Property | Value |
|----------|-------|
| **Section** | Pre-Flop (right grid) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.fold_to_4bet IS NOT NULL` (faced a 4-bet) |
| **Action** | `hp.fold_to_4bet = FALSE AND hp.five_bet IS NOT TRUE` (called, didn't fold or 5-bet) |
| **Benchmark** | None |

**What you see**: Hands where hero flatted a 4-bet. Often a questionable play — usually better to fold or 5-bet jam.

---

## Section 2: STEAL

### Left Table (Tot / BTN / SB columns)

---

#### `steal` — Steal

| Property | Value |
|----------|-------|
| **Section** | Steal (left table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.steal_opp = TRUE` (folded to hero in CO/BTN/SB) |
| **Action** | `hp.steal_attempted = TRUE` (hero raised) |
| **Benchmark** | 25–40% |

**What you see**: Steal frequency by position. Trend over time.

---

#### `four_bet_fold_steal` — 4-Bet-Fold (Steal)

| Property | Value |
|----------|-------|
| **Section** | Steal (left table) |
| **Positional** | No |
| **Key street** | preflop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.four_bet_fold IS NOT NULL AND hp.steal_attempted = TRUE` |
| **Action** | `hp.four_bet_fold = TRUE` |
| **Benchmark** | None |

**What you see**: How often hero 4-bets from a steal position and then folds to a 5-bet.

---

### Right Table (SB / BB columns)

---

#### `fold_to_steal` — Fold to Steal

| Property | Value |
|----------|-------|
| **Section** | Steal (right table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | response_distribution, trend_sparkline |
| **Opportunity** | `hp.faced_steal = TRUE` (hero in BB/SB facing CO/BTN/SB open) |
| **Action** | `hp.fold_to_steal = TRUE` |
| **Response decomp** | Fold: `fold_to_steal`, Call: `call_steal`, Raise: `three_bet_vs_steal` |
| **Benchmark** | 40–55% |

**What you see**: Response distribution (fold / call / 3-bet) when facing a steal. Critical blind defense stat.

---

#### `call_steal` — Call Steal

| Property | Value |
|----------|-------|
| **Section** | Steal (right table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | response_distribution, trend_sparkline |
| **Opportunity** | `hp.faced_steal = TRUE` |
| **Action** | `hp.call_steal = TRUE` |
| **Response decomp** | Same as fold_to_steal (shared decomposition) |
| **Benchmark** | None |

**What you see**: Same response distribution as fold_to_steal (they share the same opportunity pool).

---

#### `three_bet_vs_steal` — 3-Bet vs Steal

| Property | Value |
|----------|-------|
| **Section** | Steal (right table) |
| **Positional** | Yes |
| **Key street** | preflop |
| **Widgets** | response_distribution, trend_sparkline |
| **Opportunity** | `hp.faced_steal = TRUE` |
| **Action** | `hp.three_bet_vs_steal = TRUE` |
| **Response decomp** | Same as fold_to_steal |
| **Benchmark** | None |

**What you see**: 3-bet frequency specifically vs steal opens. Shares response distribution with the other steal defense stats.

---

## Section 3: POSTFLOP

### Left Table (Flop / Turn / River columns)

---

#### `cbet_flop` — C-Bet Flop

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | flop |
| **Widgets** | positional_bar, trend_sparkline |
| **Opportunity** | `hp.cbet_flop_opp = TRUE` (hero was PFR and saw flop) |
| **Action** | `hp.cbet_flop = TRUE` (hero bet the flop as PFR) |
| **Benchmark** | 50–70% |

**What you see**: Positional mini-bar showing c-bet % per position. Trend sparkline. Hand list showing flop actions with board cards. Key stat for postflop coaching.

---

#### `cbet_turn` — C-Bet Turn

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | turn |
| **Widgets** | positional_bar, trend_sparkline |
| **Opportunity** | `hp.cbet_turn_opp = TRUE` |
| **Action** | `hp.cbet_turn = TRUE` |
| **Benchmark** | 50–70% |

**What you see**: Double-barrel frequency. Hands highlight turn actions.

---

#### `cbet_river` — C-Bet River

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | river |
| **Widgets** | positional_bar, trend_sparkline |
| **Opportunity** | `hp.cbet_river_opp = TRUE` |
| **Action** | `hp.cbet_river = TRUE` |
| **Benchmark** | 50–70% |

**What you see**: Triple-barrel frequency. Hands highlight river actions.

---

#### `fold_to_cbet_flop` — Fold to CBet Flop

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | flop |
| **Widgets** | positional_bar, response_distribution, trend_sparkline |
| **Opportunity** | `hp.fold_to_cbet_flop IS NOT NULL` (hero faced a flop c-bet) |
| **Action** | `hp.fold_to_cbet_flop = TRUE` |
| **Response decomp** | Fold: `fold_to_cbet_flop`, Call: remainder, Raise: `raise_cbet_flop` |
| **Benchmark** | 40–55% |

**What you see**: Response distribution (fold / call / raise) when facing flop c-bet. Positional breakdown. Board cards in hand list.

---

#### `fold_to_cbet_turn` — Fold to CBet Turn

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | turn |
| **Widgets** | positional_bar, response_distribution, trend_sparkline |
| **Opportunity** | `hp.fold_to_cbet_turn IS NOT NULL` |
| **Action** | `hp.fold_to_cbet_turn = TRUE` |
| **Response decomp** | Fold: `fold_to_cbet_turn`, Call: remainder, Raise: `turn_raises > 0` |
| **Benchmark** | 40–55% |

---

#### `fold_to_cbet_river` — Fold to CBet River

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table) |
| **Positional** | Yes |
| **Key street** | river |
| **Widgets** | positional_bar, response_distribution, trend_sparkline |
| **Opportunity** | `hp.fold_to_cbet_river IS NOT NULL` |
| **Action** | `hp.fold_to_cbet_river = TRUE` |
| **Response decomp** | Fold: `fold_to_cbet_river`, Call: remainder, Raise: `river_raises > 0` |
| **Benchmark** | None |

---

#### `af_flop` / `af_turn` / `af_river` — Aggression Factor

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table, Flop/Turn/River row) |
| **Positional** | No |
| **Key street** | flop / turn / river respectively |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_flop/turn/river = TRUE` |
| **Action** | `(hp.{street}_bets + hp.{street}_raises) > 0` |
| **Benchmark** | 2–4 (all streets) |

**What you see**: Hands where hero was aggressive (bet or raised) on that street. AF = (bets + raises) / calls.

---

#### `afq_flop` / `afq_turn` / `afq_river` — Aggression Frequency

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table, Flop/Turn/River row) |
| **Positional** | No |
| **Key street** | flop / turn / river |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_{street} = TRUE` |
| **Action** | `(hp.{street}_bets + hp.{street}_raises) > 0` |
| **Benchmark** | None |

**What you see**: Same filter as AF but expressed as percentage. AFq = (bets + raises) / (bets + raises + calls + folds).

---

#### `donk_bet_flop` / `donk_bet_turn` / `donk_bet_river` — Donk Bet

| Property | Value |
|----------|-------|
| **Section** | Postflop (left table, Flop/Turn/River row) |
| **Positional** | No |
| **Key street** | flop / turn / river |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.donk_bet_{street}_opp = TRUE` (hero faced PFR aggressor, had option to lead) |
| **Action** | `hp.donk_bet_{street} = TRUE` (hero bet into the aggressor) |
| **Benchmark** | None |

**What you see**: Hands where hero bet into the preflop raiser. Generally considered a weak play at lower stakes.

---

### Right Table: vs C-Bet Flop (Raised Pot)

---

#### `fold_cbet_flop_raised` — Fold to CBet (Raised Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table, Raised Pot row) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | response_distribution, trend_sparkline |
| **Opportunity** | `hp.fold_to_cbet_flop IS NOT NULL AND NOT COALESCE(hp.is_3bet_pot, false)` |
| **Action** | `hp.fold_to_cbet_flop = TRUE` |
| **Response decomp** | Fold / Call / Raise within raised (non-3bet) pots |
| **Benchmark** | None |

**What you see**: Defense frequency specifically in single-raised pots. Response distribution shows fold/call/raise.

---

#### `call_cbet_flop_raised` — Call CBet (Raised Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as fold_cbet_flop_raised |
| **Action** | `hp.call_cbet_flop = TRUE` |

---

#### `raise_cbet_flop_raised` — Raise CBet (Raised Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as fold_cbet_flop_raised |
| **Action** | `hp.raise_cbet_flop = TRUE` |

---

### Right Table: vs C-Bet Flop (3-Bet Pot)

---

#### `fold_cbet_flop_3bet` — Fold to CBet (3-Bet Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table, 3-Bet Pot row) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | response_distribution, trend_sparkline |
| **Opportunity** | `hp.fold_to_cbet_flop IS NOT NULL AND hp.is_3bet_pot = TRUE` |
| **Action** | `hp.fold_to_cbet_flop = TRUE` |
| **Response decomp** | Fold / Call / Raise within 3-bet pots |
| **Benchmark** | None |

**What you see**: Defense in 3-bet pots specifically. Ranges are tighter, pots are larger — different dynamics than SRP.

---

#### `call_cbet_flop_3bet` — Call CBet (3-Bet Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as fold_cbet_flop_3bet |
| **Action** | `hp.call_cbet_flop = TRUE` |

---

#### `raise_cbet_flop_3bet` — Raise CBet (3-Bet Pot)

| Property | Value |
|----------|-------|
| **Section** | Postflop (right table) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as fold_cbet_flop_3bet |
| **Action** | `hp.raise_cbet_flop = TRUE` |

---

## Section 4: MISSED C-BET

### Left Column

---

#### `missed_cbet_flop` — Missed C-Bet Flop

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (left) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.cbet_flop_opp = TRUE` (hero was PFR, saw flop) |
| **Action** | `hp.missed_cbet_flop = TRUE` (hero checked instead of c-betting) |
| **Benchmark** | None |

**What you see**: Inverse of C-Bet Flop. Shows hands where hero checked as PFR. Context: on which boards does hero give up initiative?

---

#### `missed_cbet_flop_ip` — Missed C-Bet IP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (left) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.cbet_flop_opp = TRUE` + `hp.position IN ('CO', 'BTN')` |
| **Action** | `hp.missed_cbet_flop = TRUE` |
| **Benchmark** | None |

**What you see**: Missed c-bets specifically when hero is in position. Lower = better (should c-bet more IP).

---

#### `missed_cbet_flop_oop` — Missed C-Bet OOP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (left) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.cbet_flop_opp = TRUE` + `hp.position NOT IN ('CO', 'BTN')` |
| **Action** | `hp.missed_cbet_flop = TRUE` |
| **Benchmark** | None |

**What you see**: Missed c-bets OOP. Higher is more acceptable — checking OOP as PFR is often correct.

---

#### `missed_cbet_fold_ip` — Missed C-Bet → Fold IP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (left) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.missed_cbet_flop = TRUE AND hp.position IN ('CO', 'BTN')` |
| **Action** | `hp.flop_folds > 0` (hero checked and then folded) |
| **Benchmark** | None |

**What you see**: How often hero gives up completely after missing c-bet IP. High = one-and-done pattern.

---

#### `missed_cbet_fold_oop` — Missed C-Bet → Fold OOP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (left) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.missed_cbet_flop = TRUE AND hp.position NOT IN ('CO', 'BTN')` |
| **Action** | `hp.flop_folds > 0` |
| **Benchmark** | None |

---

### Right Column: vs Missed C-Bet

---

#### `vs_missed_cbet` — vs Missed C-Bet

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (right) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_flop = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL` (hero saw flop, wasn't PFR, didn't face a c-bet) |
| **Action** | `hp.flop_bets > 0` (hero bet when PFR checked) |
| **Benchmark** | None |

**What you see**: How often hero attacks when the PFR misses their c-bet. This is the probe bet scenario.

---

#### `vs_missed_cbet_bet_ip` — vs Missed C-Bet Bet IP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (right) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as vs_missed_cbet + `hp.position IN ('CO', 'BTN')` |
| **Action** | `hp.flop_bets > 0` |

---

#### `vs_missed_cbet_check_fold_ip` — vs Missed C-Bet Check-Fold IP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (right) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as vs_missed_cbet + IP filter |
| **Action** | `hp.flop_folds > 0 AND hp.flop_bets = 0` (checked then folded) |

---

#### `vs_missed_cbet_bet_oop_turn` — vs Missed C-Bet Bet OOP Turn

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (right) |
| **Positional** | No |
| **Key street** | turn |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_turn = TRUE AND hp.cbet_flop_opp IS NOT TRUE AND hp.fold_to_cbet_flop IS NULL AND hp.position NOT IN ('CO', 'BTN')` |
| **Action** | `hp.turn_bets > 0` |

**What you see**: OOP probe bet on the turn when PFR missed c-bet. Delayed aggression line.

---

#### `vs_missed_cbet_check_fold_oop` — vs Missed C-Bet Check-Fold OOP

| Property | Value |
|----------|-------|
| **Section** | Missed C-Bet (right) |
| **Positional** | No |
| **Key street** | flop |
| **Widgets** | trend_sparkline |
| **Opportunity** | Same as vs_missed_cbet + OOP filter |
| **Action** | `hp.flop_folds > 0 AND hp.flop_bets = 0` |

---

## Section 5: SHOWDOWN

---

#### `saw_flop` — Saw Flop

| Property | Value |
|----------|-------|
| **Section** | Showdown |
| **Positional** | No |
| **Key street** | None (last street with actions) |
| **Widgets** | trend_sparkline |
| **Opportunity** | All hands |
| **Action** | `hp.saw_flop = TRUE` |
| **Benchmark** | None |

---

#### `went_to_showdown` — WTSD (Went to Showdown)

| Property | Value |
|----------|-------|
| **Section** | Showdown |
| **Positional** | No |
| **Key street** | None (last street) |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_flop = TRUE` |
| **Action** | `hp.went_to_showdown = TRUE` |
| **Benchmark** | 24–30% |

**What you see**: How often hero goes to showdown (of hands that saw flop). High = calling station. Low = folding too much postflop.

---

#### `won_at_showdown` — W$SD (Won $ at Showdown)

| Property | Value |
|----------|-------|
| **Section** | Showdown |
| **Positional** | No |
| **Key street** | None |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.went_to_showdown = TRUE` |
| **Action** | `hp.won_at_showdown = TRUE` |
| **Benchmark** | 50–55% |

**What you see**: Win rate at showdown. Low = arriving with weak hands. High (>60%) = only showing nuts (not bluffing enough).

---

#### `wwsf` — WWSF (Won When Saw Flop)

| Property | Value |
|----------|-------|
| **Section** | Showdown |
| **Positional** | No |
| **Key street** | None |
| **Widgets** | trend_sparkline |
| **Opportunity** | `hp.saw_flop = TRUE` |
| **Action** | `hp.won = TRUE` (hero won the hand) |
| **Benchmark** | 42–50% |

**What you see**: Overall postflop success rate. Combines both showdown and non-showdown wins. Low = not aggressive enough postflop.

---

## Widget Summary Matrix

| Widget | Stats That Show It |
|--------|--------------------|
| **range_heatmap** | vpip, pfr, open_raise, call_open_raise, three_bet, three_bet_ip, three_bet_oop, four_bet, fold_to_3bet, fold_to_4bet, limp |
| **response_distribution** | fold_to_3bet, fold_to_4bet, fold_to_steal, call_steal, three_bet_vs_steal, fold_to_cbet_flop, fold_to_cbet_turn, fold_to_cbet_river, fold_cbet_flop_raised, fold_cbet_flop_3bet |
| **positional_bar** | cbet_flop, cbet_turn, cbet_river, fold_to_cbet_flop, fold_to_cbet_turn, fold_to_cbet_river |
| **trend_sparkline** | All 79 stats |

---

## Benchmarked Stats (with traffic-light coloring)

| Stat Key | Display | Green Range | Weight |
|----------|---------|-------------|--------|
| vpip | VPIP | 20–28% | 5 |
| pfr | PFR | 16–24% | 5 |
| open_raise | Open Raise | 15–30% (total), positional varies | 4 |
| three_bet | 3-Bet | 6–10% | 4 |
| fold_to_3bet | Fold to 3-Bet | 55–65% | 4 |
| four_bet | 4-Bet | 3–7% | 2 |
| fold_to_4bet | Fold to 4-Bet | 55–65% | 2 |
| steal | Steal | 25–40% | 3 |
| vs_steal_fold | vs Steal Fold | 40–55% | 3 |
| cbet_flop | C-Bet Flop | 50–70% | 4 |
| cbet_turn | C-Bet Turn | 50–70% | 3 |
| cbet_river | C-Bet River | 50–70% | 2 |
| fold_to_cbet_flop | Fold to CBet Flop | 40–55% | 3 |
| fold_to_cbet_turn | Fold to CBet Turn | 40–55% | 2 |
| wtsd | WTSD | 24–30% | 3 |
| wsd | W$SD | 50–55% | 3 |
| wwsf | WWSF | 42–50% | 3 |
| af_flop | AF Flop | 2–4 | 2 |
| af_turn | AF Turn | 2–4 | 2 |
| af_river | AF River | 2–4 | 2 |

Yellow zone = 30% of range width outside each boundary. Red = beyond yellow.

---

## Future Stats (M2.2 — Not Yet Built)

These stats are planned but not yet in the registry:

### Check-Raise Section
- `check_raise_flop` / `check_raise_turn` / `check_raise_river`
- `fold_to_check_raise_flop` / `fold_to_check_raise_turn` / `fold_to_check_raise_river`

### Probe / Float / Delayed C-Bet Section
- `probe_bet_flop` / `probe_bet_turn` / `probe_bet_river`
- `float_flop`
- `delayed_cbet_turn` / `delayed_cbet_river`

### Core Gap Stats
- `cold_call`, `call_3bet`, `fold_to_squeeze`
- `saw_flop_pct`, `saw_turn_pct`, `saw_river_pct`

### H2N Parity Flags (existing in DB, need stats engine wiring)
- `missed_cbet_then_fold`, `bet_vs_missed_cbet`, `check_fold_vs_missed_cbet`

See `prd/M2_STUDY_SPOTS.md` §M2.2 for full spec.
