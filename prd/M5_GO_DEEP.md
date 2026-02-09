# Milestone 5: "The App That Goes Deep"

> **Goal**: Advanced analysis features for serious study and competitive edge.
> **Coaching parallel**: Solver Study / GTO Workshop, advanced postflop analysis, bet sizing exploitation.
> **Priority**: Medium for the average player, high for dedicated students and aspiring professionals.

---

## 1. Research

### What Coaching Sessions This Serves

Milestone 5 targets the most analytically demanding coaching scenarios -- the sessions where a coach and student move beyond "what are your stats?" into "what are you doing on A-high rainbow boards in 3-bet pots when you have top pair weak kicker?" This level of granularity is what separates intermediate study from professional-grade analysis.

**Solver Study / GTO Workshop**: Coach opens a solver output for a specific board texture (e.g., Axx rainbow in SRP), shows the GTO c-bet frequency and sizing, then asks "what are you actually doing here?" The student needs their own stats filtered by that exact board texture to compare against solver recommendations. Without board texture filtering, this comparison is impossible -- the student can only say "my overall c-bet is 65%" which tells the coach nothing about specific textures.

**Advanced Postflop Analysis**: Coach reviews hands where the student c-bet the flop and wants to know: "What were you c-betting with? Show me the hands where you c-bet on monotone boards -- what did you have?" This requires hand strength classification at the moment of action, cross-referenced with board texture. It is the deepest level of poker analysis.

**Bet Sizing Exploitation**: Modern poker coaching increasingly focuses on sizing tells -- the idea that players use different bet sizes with different hand strengths, creating exploitable patterns. Coaches ask: "When you bet 33% pot on the flop, what do you actually have vs. when you bet 75%?" and "When the population overbets the river, how often is it a bluff?" Sizing analysis requires pot tracking, which no other feature in OHM provides.

### How Coaches Use Board Texture Analysis

Board texture is the single most important variable in postflop decision-making. Solvers produce radically different strategies on different textures:

- **Axx rainbow** (dry): Solver c-bets at high frequency (70-80%) with small sizing (25-33% pot) because the preflop raiser's range advantage is massive.
- **8-7-5 two-tone** (wet, connected): Solver c-bets at low frequency (30-40%) with larger sizing (50-75% pot) because ranges are closer and draws are plentiful.
- **K-Q-J monotone**: Solver checks most hands because the board hits both ranges hard and flush draws dominate.

Coaches need to see if the student adjusts strategy by texture. A player who c-bets 65% on all textures has a massive leak -- they are over-cbetting wet boards and possibly under-cbetting dry boards. But without texture-aware stats, this leak is invisible.

H2N and Smart Poker Study use a 10-category rank structure classification (ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc) crossed with suit structure (mono/2tone/rainbow) and pairing. This convention is adopted by OHM for consistency with coaching materials.

### How Hand Strength Classification Is Used in Coaching

The central question in every postflop coaching session: "What are you betting with? What are you checking with?"

**C-Bet hand strength breakdown**: Coach sees that the student c-bets 65% of flops. They drill down to see the hand strength distribution: "You're c-betting 95% of your top pair hands (good), 80% of your middle pair hands (too high), 90% of your air (way too high), but only 40% of your flush draws (too low -- you should be semi-bluffing more)."

**Check-raise hand strength**: "When you check-raise the flop, what do you have?" If the answer is "90% strong hands, 10% bluffs," the student is check-raising too value-heavy and opponents can exploit by folding everything except the nuts.

**EV by hand strength**: The most powerful leak-finding tool. "When you c-bet with air on dry boards, you win +0.3 bb on average (good, profitable bluff). When you c-bet with air on wet boards, you lose -1.2 bb on average (bad, opponents aren't folding enough)."

Hand strength is classified along two orthogonal dimensions: made hand strength (mutually exclusive categories from straight flush down to no made hand) and draw flags (which can co-occur with any made hand -- e.g., top pair + flush draw).

### Bet Sizing Analysis in Modern Poker

Sizing tells are widely considered the most exploitable pattern in modern poker. Most players unconsciously use different sizes with different hand strengths:

- **Small bets with strong hands** (blocking bet / milking) or **small bets with weak hands** (cheap bluff) -- the pattern varies by player, but almost every player has one.
- **Large bets and overbets** correlate with either very strong hands (polarized value) or complete air (polarized bluff) -- the ratio determines whether the player is balanced.
- **Consistent sizing** is the hallmark of a trained player. Deviation from consistent sizing is a tell.

Coaching platforms like GTO Wizard and solvers like PioSolver emphasize that optimal play uses specific sizings on specific textures. A coach needs to see: "What size are you using on Axx dry boards? The solver says 33% pot, but you're averaging 55% pot -- you're sizing too large, which lets opponents make easier decisions."

Population-level sizing tells (from PRD_POPULATION.md) answer: "When the field bets 33% pot on the river vs. 100% pot, what do they actually show up with at showdown?" This data is gold for exploitation.

### HM3 Situational Views as a Coaching Feature

HoldemManager 3's Situational Views are purpose-built dashboards for common poker situations:

- **C-Bet Situations**: All c-bet data in one place -- frequency by street, by position, by pot type, by board texture, success rate (fold equity), sizing distribution, IP vs OOP splits. This replaces the need to cross-reference 6 different stats on the main stats page.
- **3-Bet Pots**: Everything about 3-bet pots -- 3-bet frequency, calling frequency, fold frequency, by position, outcomes in 3-bet pots, postflop play in 3-bet pots.
- **Steal Situations**: Steal attempt rate, defense responses, post-steal postflop play. Answers "how profitable are my steals and how do opponents respond?"
- **River Play**: River bet frequency, sizing, fold-to-river-bet, check-raise river -- the most critical street for large pots.

The advantage over raw stat tables: situational views gather all relevant data for a single concept, eliminating context-switching. A coach reviewing c-bet strategy opens one dashboard instead of navigating between preflop, postflop, and missed c-bet sections.

### Decision Analysis (H2N Pro-level EV per Action)

Hand2Note Pro offers decision analysis: for any specific situation, show the average result (EV) of each possible action the player took.

**Action Profit**: "In spots where you were PFR IP in a single-raised pot on an Axx flop with top pair, when you bet you won +1.8 bb on average, when you checked you won +1.2 bb on average." The delta (+0.6 bb) quantifies the value of betting vs. checking in that spot.

**Spot Frequency**: "This situation (PFR IP, SRP, Axx flop, top pair) occurs 4.2 times per 1000 hands." Combined with Action Profit, this gives total impact: 4.2/1000 * 0.6 bb = 0.0025 bb/hand difference.

**Next Villain Actions**: "After you c-bet the flop, villain folds 45%, calls 38%, raises 17%." This tells you how much fold equity your c-bets have and how often you face resistance.

### GTO Wizard's EV Loss Sorting and Action Frequency Analysis

GTO Wizard's GTO Reports feature computes EV loss -- the difference between the player's chosen action and the solver-optimal action -- and sorts situations by total EV loss. This directly answers "where am I losing the most money relative to perfect play?"

While OHM cannot compute solver-optimal actions (that requires a solver), it can approximate this through:
- **EV comparison within the player's own data**: "When you bet this spot, you average +X. When you check, you average +Y." If Y > X, you're betting when you should be checking -- that's a leak.
- **Frequency comparison against benchmarks**: "Solvers c-bet Axx at 75%. You c-bet at 90%. The excess 15% is likely unprofitable." Combined with hand strength data, this becomes actionable.

---

## 2. Product Design

### M5.1: Board Texture Analysis (Shared Infrastructure)

A Python utility that classifies every flop, turn, and river into standardized texture categories. This is shared infrastructure used by Stats v2 detail panels (M2), Population Analysis (M4), and all M5 analysis features.

#### Flop Classification

Primary axis -- **Rank Structure** (H2N / Smart Research convention. Broadway = T, J, Q, K; Ace is treated separately as a premium card):

| Category | Code | Definition | Example |
|----------|------|------------|---------|
| Ace + Broadway + Broadway | ABB | Ace + 2 broadway cards | A K J |
| Ace + Broadway + x | ABx | Ace + 1 broadway + 1 non-broadway | A Q 5 |
| Ace + x + x | Axx | Ace + 2 non-broadway cards | A 7 3 |
| 3 Broadways (no Ace) | BBB | 3 broadway cards, no ace | K Q T |
| 2 Broadways + x (no Ace) | BBx | 2 broadway cards + 1 non-broadway, no ace | K J 6 |
| 1 Broadway + x + x (no Ace) | Bxx | 1 broadway + 2 non-broadway, no ace | Q 7 3 |
| T-9 High Connected | T-9 Conn | Highest card is T or 9, at least 2 cards within rank gap <= 2 | T 9 7 |
| T-9 High Disconnected | T-9 Disc | Highest card is T or 9, no 2 cards within gap <= 2 | T 6 2 |
| 8-2 High Connected | 8-2 Conn | Highest card is 8 or lower, at least 2 cards within gap <= 2 | 8 7 5 |
| 8-2 High Disconnected | 8-2 Disc | Highest card is 8 or lower, no 2 cards within gap <= 2 | 8 4 2 |

Key definitions:
- **Broadway** = T, J, Q, K (not Ace -- Ace is treated separately)
- **Connected** = at least 2 cards within rank gap <= 2 (e.g., 8-7, T-8, 9-7)
- **T-9 High** = highest card is T or 9 (no broadway above T, no ace)
- **8-2 High** = highest card is 8 or below

Secondary axis -- **Suit Structure**:
- **Monocolor**: All 3 cards are the same suit
- **2tone**: Exactly 2 cards share the same suit (flush draw possible)
- **Rainbow**: All 3 cards are different suits

Tertiary axis -- **Pairing** (overlay, cross-cuts rank categories):
- **Paired**: 2 or more cards share the same rank
- **Unpaired**: All cards have different ranks

The full classification is the combination of all three axes. For example: "Axx Rainbow Unpaired" or "BBx 2tone Paired."

#### Turn Classification

Classified by what the turn card changed relative to the flop texture:

| Category | Code | Definition | Example |
|----------|------|------------|---------|
| Completed draw | completed_draw | Turn brings 3rd flush card, or completes an obvious straight (4 consecutive ranks on board) | Flop: 8h 7d 2c, Turn: 6s (straight possible) |
| Draw-adding | draw_adding | Turn brings 2nd flush card (when flop was rainbow), or adds straight connectivity | Flop: Kh 7d 2c, Turn: 8d (adds flush draw + straight potential) |
| Overcard | overcard | Turn card is the highest card on the board | Flop: 9h 7d 2c, Turn: Ks |
| Paired board | paired_board | Turn pairs one of the flop cards | Flop: Kh 7d 2c, Turn: 7s |
| Brick | brick | Low, unconnected card that does not meaningfully change the board texture | Flop: Ah Kd 7c, Turn: 3s |

Priority order (when multiple categories could apply): completed_draw > paired_board > overcard > draw_adding > brick. A turn card can only be classified into one category.

#### River Classification

Same 5 categories as turn classification, applied to the 4-card board -> 5-card board transition:

| Category | Code | Definition |
|----------|------|------------|
| Completed draw | completed_draw | River brings 3rd or 4th flush card, or completes a straight |
| Draw-adding | draw_adding | River adds flush or straight potential (less relevant on river since no more cards) |
| Overcard | overcard | River is the highest card on the board |
| Paired board | paired_board | River pairs a board card (or makes trips/quads) |
| Brick | brick | Does not change the board texture meaningfully |

Note: On the river, "draw-adding" is less meaningful since there are no more cards to come. Some implementations merge draw_adding into brick on the river. For consistency, we keep the same 5 categories.

#### How Texture Analysis Integrates

Board texture classification is used in three contexts:

1. **Stats v2 Detail Panels (M2)**: When a user clicks a postflop stat like "C-Bet Flop," the detail panel shows a board texture breakdown table -- c-bet frequency, sizing, and fold equity per texture category.
2. **Population Analysis (M4)**: The population page shows aggregate c-bet/fold-to-cbet/check-raise rates per board texture, revealing how the field adjusts (or fails to adjust) by texture.
3. **Situational Views (M5.4)**: Purpose-built dashboards cross-reference texture with position, pot type, and hand strength.

Storage: Precomputed columns on the `hands` table (`flop_texture_rank`, `flop_texture_suit`, `flop_paired`, `turn_texture`, `river_texture`), computed during `insert_parsed_hand` and backfilled via `/api/import/rebuild`.

---

### M5.2: Hand Strength Evaluation (Shared Infrastructure)

A Python utility that classifies hero's hand at any action point given hole cards and the current board. Classification uses two orthogonal dimensions -- a hand can be both a made hand AND a draw simultaneously.

#### Made Hand Categories (14 categories, mutually exclusive, highest match wins)

| ID | Category | Definition | Example |
|----|----------|------------|---------|
| 11 | Straight Flush | 5 cards forming both a straight and a flush | 5h 6h 7h 8h 9h |
| 10 | Quads | Four cards of the same rank | 8 8 8 8 x |
| 9 | Full House | Three of a kind plus a pair | K K K 7 7 |
| 8 | Flush | 5 cards of the same suit, not sequential | Ah 9h 6h 4h 2h |
| 7 | Straight | 5 cards in sequential rank order, not all same suit | 5 6 7 8 9 |
| 6 | Set | Pocket pair in hand matches one board card to make three of a kind. Distinguished from trips because having a pocket pair makes the hand much more disguised. | Hero: 8h 8s, Board: 8d K 5 |
| 5 | Trips | Board pair plus one hole card matching to make three of a kind. Weaker than set because it is less disguised and more likely that an opponent also has trips. | Hero: 8h Kd, Board: 8s 8c 5 |
| 4 | Two Pair | Two distinct pairs. Can be both hole cards paired with board cards, one hole card plus a board two-pair, or a pocket pair plus one board pair. | Hero: Kh 7d, Board: Ks 7c 2h |
| 3 | Overpair | Pocket pair higher than all board cards. A strong hand category because it beats all one-pair hands. | Hero: QQ, Board: T 7 3 |
| 2 | Top Pair Good Kicker (TPTK) | One hole card pairs the highest board card, and the other hole card (kicker) is A, K, Q, J, or T. | Hero: AhTd, Board: Ts 7c 3h (top pair ace kicker) |
| 1 | Top Pair Weak Kicker (TPWK) | One hole card pairs the highest board card, but the kicker is 9 or lower. | Hero: 9h Td, Board: Ts 7c 3h (top pair nine kicker) |
| 0 | Middle Pair | One hole card pairs the second-highest board card. | Hero: 7h Ad, Board: Ts 7c 3h |
| -1 | Weak Pair | Bottom pair (paired with lowest board card), third pair, or underpair (pocket pair below the middle board card). | Hero: 3h Ad, Board: Ts 7c 3s (bottom pair); or Hero: 5h5d, Board: Ts 7c 3s (underpair) |
| -2 | Overcards | Both hole cards are higher than all board cards, but no pair is made. | Hero: AhKd, Board: 9s 7c 3h |
| -3 | Ace High | Ace in hand, no pair made, not both overcards (the other card is below a board card). | Hero: Ah 4d, Board: Ts 7c 3h |
| -4 | No Made Hand | None of the above categories apply. No pair, no overcards, no ace high. | Hero: 5h 4d, Board: Ts 7c 3h |

**Classification rule**: Check categories from ID 11 down to -4. The first match wins. A hand is assigned exactly one made hand category.

**Special cases**:
- Set vs Trips: Both are three of a kind but distinguished by whether the pair is in the hole (set) or on the board (trips). Sets are much stronger because they are disguised.
- Two Pair: Include the case where hero's pocket pair combines with a board pair. Exclude cases where both pairs are on the board (hero has no pair -- classify by kicker strength instead).
- Overpair: Must be a pocket pair. If hero has a pair above all board cards but it is not a pocket pair (e.g., one card pairs the board and the other is higher), classify as top pair.
- TPTK vs TPWK: The kicker threshold is T (10). A-T kickers are "good," 9 and below are "weak." This matches the PokerTracker/H2N convention.

#### Draw Flags (6 flags, orthogonal to made hand categories)

Draw flags are NOT mutually exclusive with made hand categories. A hand like Ah Kh on a board of Qs Jh 7h has both Top Pair (if K pairs) or Overcards (if no pair) AND a Flush Draw. Both dimensions are reported.

| Flag | Code | Definition | Notes |
|------|------|------------|-------|
| Flush Draw | flush_draw | 4 cards of the same suit among hole cards + board cards. Needs exactly 1 more card to complete. | 9 outs. Strongest single draw. |
| Open-Ended Straight Draw | oesd | 4 consecutive ranks among hole cards + board cards, with room to complete on either end. | 8 outs. E.g., Hero: 8 7, Board: 6 5 x -- needs a 4 or 9. |
| Gutshot | gutshot | 4 to a straight but missing one inner card (inside straight draw). | 4 outs. E.g., Hero: 8 6, Board: 7 5 x -- needs a 9 (or Hero: 9 6, Board: 8 5 x -- needs a 7). |
| Combo Draw | combo_draw | Flush draw combined with any straight draw (OESD or gutshot). The combined equity often exceeds a made pair. | Set when flush_draw=true AND (oesd=true OR gutshot=true). |
| Backdoor Flush Draw | backdoor_flush | 3 cards of the same suit among hole cards + board cards. Only relevant on the flop (2 cards to come). | ~1.5% to complete (~4.2% backdoor equity contributes to hand playability). |
| Backdoor Straight Draw | backdoor_straight | 3 cards to a straight with 2 cards to come (flop only). Specifically: 3 cards within a 5-card span. | Marginal equity, but contributes to hand playability decisions. |

**Flag priority**: `combo_draw` is set as a convenience flag whenever both `flush_draw` and a straight draw are present. It does not replace the individual flags -- all applicable flags are set simultaneously.

**No Draw flag**: When none of the above flags are set, the hand has no draw component.

#### Composite Groups (for Display)

For simplified display in detail panels, stats summaries, and the sizing tells heatmap, hands are grouped into 6 composite categories:

| Group | Includes (Made Hand IDs) | Description |
|-------|--------------------------|-------------|
| **Nuts+** | 11, 10, 9, 8, 7 | Straight flush, quads, full house, flush, straight -- premium made hands |
| **Strong** | 6, 5, 4, 3 | Set, trips, two pair, overpair -- strong but not invulnerable |
| **Top Pair** | 2, 1 | Top pair good kicker and top pair weak kicker |
| **Marginal Made** | 0, -1 | Middle pair, weak pair (bottom pair, underpair) |
| **Draw Only** | -2, -3, -4 when any draw flag is set | No meaningful made hand but holding a draw (flush draw, OESD, gutshot, combo draw, or backdoor draws on the flop) |
| **Air** | -2, -3, -4 when no draw flag is set | No made hand and no draw -- complete air |

Note: A hand with a marginal made hand + a draw (e.g., middle pair + flush draw) is classified by its made hand group (Marginal Made), but the draw flag is still reported for detailed analysis.

#### Library Choice

The hand strength evaluator does not need a full hand ranking system (comparing two hands against each other). It needs classification into the above buckets based on hole cards vs. board.

**Options**:
- **treys** (Python): Fast hand evaluation library. Provides hand rank scores. Can detect made hand categories by comparing rank thresholds. Does NOT detect draws -- those require custom code.
- **pokerkit**: Full poker game simulation library. Overpowered for this use case.
- **Custom implementation**: Write classification logic directly. Made hand detection is straightforward with card/rank/suit manipulation. Draw detection requires checking suit counts and rank sequences.

**Recommendation**: Use `treys` for the made hand evaluation (it's fast and handles the complex cases like straights and flushes efficiently), then add custom draw detection on top. The draw detection is simple enough to write from scratch:
- Flush draw: count suits, check if any suit has 4 cards.
- OESD/Gutshot: sort ranks, check for 4-card sequences (OESD) or 4-out-of-5 sequences (gutshot).
- Backdoor flush: count suits on flop, check if any suit has 3 cards.
- Backdoor straight: check 3-card straight potential on flop.

---

### M5.3: Bet Sizing Analysis

Track bet sizes as a percentage of the pot for every action, enabling sizing-based analysis across the entire database.

#### Pot Tracking

The foundation of sizing analysis is knowing the pot size at the moment of every action. This requires a `pot_before_action` column on the `actions` table.

**Computation during insert_parsed_hand**:
1. Initialize pot = sum of all blinds and antes.
2. For each action in order:
   a. Record `pot_before_action` = current pot.
   b. If action is call: pot += call_amount.
   c. If action is bet/raise: pot += amount_put_in (the raise-to amount minus what player already has in this street).
   d. If new street: pot carries forward, per-player street investments reset to 0.
3. For bets and raises, compute `bet_pct_pot = amount / pot_before_action * 100`.

**Edge cases**:
- All-in for less than a full raise: pot_before_action is still the pot before the all-in.
- Multiple raises on a street: each subsequent raiser's investment is cumulative within the street.
- Antes: added to starting pot.

#### Sizing Buckets

Standard buckets used throughout the application:

| Bucket | Label | Range | Poker Meaning |
|--------|-------|-------|---------------|
| 1 | Tiny | < 33% pot | Blocking bet, thin value, cheap probe |
| 2 | Small | 33-50% pot | Small c-bet, common solver sizing on dry boards |
| 3 | Medium | 50-66% pot | Standard sizing, balanced value/bluff ratio |
| 4 | Large | 66-100% pot | Polarizing, protection bet, value-heavy |
| 5 | Overbet | > 100% pot | Highly polarized -- either nuts or air |

These buckets are configurable in the frontend for advanced users, but the defaults match solver conventions and coaching literature.

#### Analysis Views

**Hero Sizing Report**:
- Average bet size (as % pot) by street (flop/turn/river).
- Average bet size by position (EP/MP/CO/BTN/SB/BB).
- Average bet size by pot type (SRP/3-bet pot/4-bet pot).
- Sizing distribution per street: horizontal bar chart showing what % of hero's bets fall in each bucket.
- Sizing vs. hand strength: when hero bets 33% pot, what does hero actually have? Cross-reference with hand strength composite groups.

**Hero vs. Population Sizing Comparison**:
- Side-by-side: hero's average sizing by street vs. population average.
- Highlight significant deviations: "Your flop c-bet averages 55% pot in SRPs. The population averages 38%."
- Requires population data (M4.2) to be available.

**Sizing Consistency Analysis**:
- Standard deviation of hero's sizing within each spot type.
- Low std dev = consistent sizing (harder to exploit).
- High std dev = variable sizing (may contain tells).
- Breakdown by hand strength group: "You bet 33% pot with strong hands and 55% pot with bluffs on the flop. Your sizing correlates with hand strength -- this is a major tell."

---

### M5.4: Situational Views (HM3-style)

Purpose-built dashboards that gather all relevant data for a single concept into one focused view. Each situational view replaces the need to cross-reference multiple stat sections.

#### C-Bet Situations Dashboard

Everything about continuation betting in one place:

**Summary row**: Overall c-bet frequency flop/turn/river, success rate (% villain folds to c-bet), average c-bet sizing.

**Breakdown table**:
| Dimension | C-Bet % | Avg Size | Fold Equity | Avg Result | Hands |
|-----------|---------|----------|-------------|------------|-------|
| **By Street**: Flop / Turn / River | | | | | |
| **By Position**: IP / OOP | | | | | |
| **By Pot Type**: SRP / 3-Bet / 4-Bet | | | | | |
| **By Board Texture**: Each of 10 rank categories | | | | | |
| **By # Opponents**: HU / Multiway | | | | | |
| **By Hand Strength**: Nuts+ / Strong / TP / Marginal / Draw / Air | | | | | |

**Sizing distribution chart**: Horizontal bars showing what % of c-bets are <33%, 33-50%, 50-66%, 66-100%, >100% pot. Broken down by street.

**Missed c-bet analysis**: When hero checks instead of c-betting -- frequency, hand strength at check, board texture at check, result when checking vs. betting.

**Action tree**: What happens after the c-bet? Villain folds X%, calls Y%, raises Z%. When villain calls, hero barrels turn N% of the time.

#### 3-Bet Pots Dashboard

Everything about playing in 3-bet pots:

**Preflop section**: 3-bet frequency by position, call-3-bet frequency, fold-to-3-bet, 3-bet range (13x13 heatmap).

**Postflop section**: C-bet in 3-bet pots (frequency, sizing), fold-to-cbet in 3-bet pots, check-raise in 3-bet pots, donk-bet in 3-bet pots.

**Position breakdown**: 3-bet stats as PFR (aggressor) vs. as defender (caller of 3-bet).

**Results**: Average pot size in 3-bet pots, win rate in 3-bet pots, won at showdown in 3-bet pots.

#### Steal Situations Dashboard

Blind stealing and defense:

**Steal section**: Steal attempt rate by position (CO/BTN/SB), sizing by position, hand range (heatmap).

**Defense section**: Fold-to-steal from SB/BB, call-steal rate, 3-bet-vs-steal rate.

**Post-steal play**: C-bet frequency after stealing, fold-to-3-bet after steal, 4-bet after steal.

**Results**: Win rate for steal pots, average pot size, fold equity per position.

#### River Play Dashboard

The most critical street for large pots:

**Bet frequency**: River bet %, by position, by pot type, by texture.

**Sizing**: Average river bet size, sizing distribution, sizing by hand strength (value sizing vs. bluff sizing).

**Defense**: Fold-to-river-bet, call rate, raise rate, by facing bet size bucket.

**Check-raise**: River check-raise frequency, hand strength when check-raising.

**Showdown**: What does hero show when betting river? What does hero show when calling river? Cross-reference with sizing and board texture.

---

### M5.5: Decision Analysis (EV per Action)

For any specific poker situation, compute the expected value of each possible action the player actually took. This is empirical EV from the database, not solver-computed GTO EV.

#### Action Profit

For a given situation (defined by: street, position, pot type, board texture, hand strength, action), compute the average result (in bb) when the player took each possible action.

**Display**:
```
C-Bet Flop IP in SRP on Axx boards
                Action    No Action
Avg Result      +0.82 bb   +0.31 bb     +0.51 bb better to bet
Hands             650        350

By Hand Strength:
Hand         | EV Bet   | EV Check | Diff   |
Nuts+        | +5.20 bb | +3.10 bb | +2.10  | bet better
Strong       | +2.80 bb | +1.50 bb | +1.30  | bet better
Top Pair     | +1.80 bb | +1.20 bb | +0.60  | bet better
Marginal     | +0.20 bb | +0.45 bb | -0.25  | check better
Draws        | -0.10 bb | -0.35 bb | +0.25  | bet better
Air          | -0.55 bb | -0.18 bb | -0.37  | check better
```

Color coding: green diff = action is more profitable, red = no-action is more profitable. This directly shows where the player is making or losing money with their decisions.

**Caveats** (shown as info tooltip):
- Not causal: Betting with strong hands and checking weak ones naturally makes bet-EV higher. The insight is in the delta within each hand strength category, not the overall numbers.
- Selection bias: Compares outcomes of actual decisions, not hypothetical optimal strategy.
- Variance: Individual hand results are high variance. Cells with < 50 hands are greyed out. Use all-in EV where available.
- Minimum sample: Each row needs 50+ observations in both columns to be meaningful.

#### Spot Frequency

How often each situation occurs, normalized per 1000 hands.

**Display**:
```
Spot                              Frequency    Total EV Impact
C-Bet Flop IP SRP                 42.3 / 1k    +0.51 * 42.3 = +21.6 bb/1k
C-Bet Flop OOP SRP                28.1 / 1k    +0.22 * 28.1 = +6.2 bb/1k
C-Bet Flop IP 3BP                 15.2 / 1k    +0.38 * 15.2 = +5.8 bb/1k
```

Total EV Impact = Action Profit delta * frequency. This ranks situations by their total contribution to win rate. High-frequency, high-delta situations are where study time should be invested.

#### Next Villain Actions

After the player takes an action, what does the villain do?

**Display**:
```
After Hero C-Bets Flop IP SRP:
  Villain Folds:   45.2%  (302 hands)
  Villain Calls:   38.1%  (255 hands)
  Villain Raises:  16.7%  (112 hands)

After Villain Calls, Hero on Turn:
  Hero Bets Turn:   58.3%  (149 hands)
  Hero Checks Turn: 41.7%  (106 hands)
```

This creates a mini decision tree showing the player's actual action frequencies through a hand. Combined with EV data, it reveals which branches are profitable and which are costly.

---

### M5.6: Custom Stat Creation (SQL-based)

Allow power users to define custom stats using DuckDB SQL queries against the database.

**Why SQL**: OHM targets a technical, open-source audience. SQL is a familiar, powerful, well-documented query language. It avoids the complexity of building a custom filter GUI (H2N approach) or a proprietary query language (HM3 HMQL approach) while being more powerful than either.

**DuckDB SQL against hand_players/actions tables**:
Users write queries that return a numerator and denominator (for percentage stats) or a single value (for average/count stats).

**SQL Editor UI**:
- Monaco editor component with SQL syntax highlighting.
- Schema browser sidebar showing table names, column names, and types.
- "Run" button to test the query.
- Result preview showing the computed stat value.
- "Save" to persist the custom stat with a name and optional description.

**Stat rendering**: Custom stats appear as new rows in the stats page. They can be placed in an existing section or in a dedicated "Custom" section. Each custom stat shows its value and sample size.

**Example custom stat -- "Open Limp from SB"**:
```sql
SELECT
  COUNT(*) FILTER (WHERE limp = TRUE AND position = 'SB') as numerator,
  COUNT(*) FILTER (WHERE position = 'SB' AND open_raise_opp = TRUE) as denominator
FROM hand_players hp
JOIN hands h ON hp.hand_id = h.id
WHERE hp.player_id = :hero_id
```

**Example custom stat -- "Average River Bet Size in 3-Bet Pots"**:
```sql
SELECT AVG(a.bet_pct_pot) as value
FROM actions a
JOIN hand_players hp ON a.hand_id = hp.hand_id AND a.player_id = hp.player_id
WHERE hp.player_id = :hero_id
  AND a.street = 'river'
  AND a.action_type IN ('bet', 'raise')
  AND hp.pot_type = '3bet'
  AND a.bet_pct_pot IS NOT NULL
```

**Security**: Queries are read-only (no INSERT/UPDATE/DELETE). The `:hero_id` parameter is injected by the backend. Queries run with a timeout (5 seconds) to prevent resource exhaustion.

**Persistence**: Custom stats stored in a new `custom_stats` table:
```sql
CREATE TABLE custom_stats (
  id INTEGER PRIMARY KEY,
  name VARCHAR NOT NULL,
  description TEXT,
  sql_query TEXT NOT NULL,
  stat_type VARCHAR NOT NULL,  -- 'percentage' or 'value'
  display_section VARCHAR,     -- which stats section to show in
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### User Stories

**M5.1 Board Texture**:
- "As a student preparing for a coaching session on c-betting, I want to see my c-bet frequency broken down by board texture, so I can identify which textures I over- or under-cbet."
- "As a coach reviewing a student's database, I want to filter postflop stats by board texture, so I can find texture-specific leaks."

**M5.2 Hand Strength**:
- "As a player studying my c-bet strategy, I want to see what hands I'm c-betting and checking with, so I can determine if my betting range is balanced."
- "As a player reviewing my check-raises, I want to see the hand strength distribution when I check-raise, so I can assess my value-to-bluff ratio."

**M5.3 Bet Sizing**:
- "As a player who suspects I have sizing tells, I want to see my bet sizing distribution correlated with hand strength, so I can identify if I size differently with value hands vs. bluffs."
- "As a student, I want to compare my average c-bet sizing to solver-recommended sizing per board texture, so I can calibrate my bet sizes."

**M5.4 Situational Views**:
- "As a player preparing for a session review, I want a single dashboard showing everything about my c-bet strategy (frequency, sizing, by texture, by position, results), so I don't have to cross-reference multiple stat sections."
- "As a player studying my blind defense, I want a Steal Situations dashboard that shows my steal rate, fold-to-steal, and post-steal play in one view."

**M5.5 Decision Analysis**:
- "As a player who wants to improve my turn play, I want to see the average EV of betting vs. checking the turn in specific spots, broken down by hand strength, so I can identify which decisions are costing me money."
- "As a coach, I want to show a student the EV impact of their c-bet decisions by board texture, so they can see exactly where they are losing money."

**M5.6 Custom Stats**:
- "As a power user, I want to define custom stats using SQL, so I can track specific situations that aren't covered by the built-in stat set."
- "As a player with an unusual strategy, I want to create a stat that tracks my 'squeeze from BB in 4-way pots' frequency, which no built-in stat covers."

---

## 3. UI/UX Design

### Board Texture Breakdown Tables

Used in Stats v2 detail panels and Situational Views. A table with texture categories as rows and stat metrics as columns.

```
Board Texture      | C-Bet% | Avg Size | Fold Eq | Avg EV  | Hands
-------------------+--------+----------+---------+---------+------
Axx Rainbow        |  75.2  |  33%pot  |  52.1   | +0.85   |   312
Axx 2tone          |  68.1  |  40%pot  |  47.3   | +0.62   |   287
ABx                |  61.5  |  48%pot  |  44.0   | +0.51   |   194
BBB                |  52.0  |  55%pot  |  38.5   | +0.22   |    89
BBx                |  58.3  |  50%pot  |  41.2   | +0.38   |   203
Bxx                |  63.2  |  42%pot  |  45.8   | +0.55   |   268
T-9 Conn           |  48.5  |  58%pot  |  36.2   | +0.10   |   156
T-9 Disc           |  55.0  |  45%pot  |  40.5   | +0.35   |   134
8-2 Conn           |  50.2  |  52%pot  |  38.0   | +0.18   |   112
8-2 Disc           |  60.1  |  40%pot  |  44.5   | +0.48   |    97
---                |        |          |         |         |
Monocolor          |  42.3  |  35%pot  |  32.0   | -0.15   |   145
Paired             |  62.5  |  45%pot  |  48.2   | +0.60   |   178
```

Sortable by any column. Rows with < 50 hands are greyed out with a low-confidence indicator. Clicking a row filters the hand list below to hands with that texture.

### Hand Strength Distribution Displays

A table showing what the player had when they took (or didn't take) the action.

```
When Hero C-Bets Flop:
Strength         | Count | % of CBets | Avg Result | Win Rate
-----------------+-------+------------+------------+---------
Nuts+            |    18 |     4.2%   |   +5.30 bb |   88.9%
Strong           |    52 |    12.1%   |   +2.85 bb |   73.1%
Top Pair         |   110 |    25.6%   |   +1.45 bb |   62.7%
Marginal Made    |    48 |    11.2%   |   +0.20 bb |   47.9%
Draw Only        |    65 |    15.1%   |   -0.35 bb |   38.5%
Air              |   137 |    31.9%   |   -0.90 bb |   28.5%

When Hero Checks Flop (missed c-bet):
Strength         | Count | % of Checks| Avg Result | Win Rate
-----------------+-------+------------+------------+---------
...
```

This table is the centerpiece of postflop analysis. It immediately reveals if the player's betting range is appropriately constructed or if they're betting too much air (or not enough).

### Sizing Distribution Charts

Horizontal bar chart showing the distribution of bet sizes by bucket.

```
Flop C-Bet Sizing Distribution:

< 33% pot    |====================|  42.1%  (180 hands)
33-50% pot   |===============|  32.5%  (139 hands)
50-66% pot   |========|  18.8%  (80 hands)
66-100% pot  |==|  4.7%  (20 hands)
> 100% pot   |=|  1.9%  (8 hands)

Avg: 38.2% pot
```

Optional overlay: population average sizing distribution in a lighter color for comparison.

### Situational View Dashboard Layouts

Each situational view follows a consistent layout:

```
+------------------------------------------------------------------+
|  [Situation Name]                         [Filters: Stakes|Dates] |
+------------------------------------------------------------------+
|                                                                    |
|  SUMMARY CARDS                                                     |
|  [Frequency: 42/1k] [Success: 48%] [Avg Size: 38%] [EV: +0.5]  |
|                                                                    |
+------------------------------------------------------------------+
|  BREAKDOWN TABLE                    |  SIZING DISTRIBUTION         |
|  By position / pot type / texture   |  Horizontal bar chart        |
|  Sortable, clickable               |                              |
+-------------------------------------|                              |
|  HAND STRENGTH DIST                 +------------------------------+
|  Table / pie chart                  |  ACTION TREE                 |
|  What does hero have?               |  What happens after?         |
+-------------------------------------+------------------------------+
|                                                                    |
|  HAND HISTORY (filtered)                                          |
|  Paginated list of matching hands                                 |
|                                                                    |
+------------------------------------------------------------------+
```

### Decision Analysis Display

Two-column comparison (action vs. no-action) with hand strength rows.

```
+------------------------------------------------------------------+
|  C-BET FLOP IP IN SRP                                             |
|  Overall: Bet +0.82 bb  vs  Check +0.31 bb   (Bet is +0.51 bb)  |
+------------------------------------------------------------------+
|                                                                    |
|  EV BY HAND STRENGTH                                              |
|  +-----------------------------------------------------------+   |
|  | Hand Strength  | EV Bet  | N   | EV Check| N   | Delta  |   |
|  +----------------+---------+-----+---------+-----+--------+   |
|  | Nuts+          | +5.20   |  80 | +3.10   |  15 | +2.10  |   |
|  | Strong         | +2.80   | 120 | +1.50   |  35 | +1.30  |   |
|  | Top Pair       | +1.80   | 180 | +1.20   |  60 | +0.60  |   |
|  | Marginal       | +0.20   |  90 | +0.45   |  80 | -0.25  |   |
|  | Draws          | -0.10   | 100 | -0.35   |  65 | +0.25  |   |
|  | Air            | -0.55   | 150 | -0.18   | 120 | -0.37  |   |
|  +-----------------------------------------------------------+   |
|                                                                    |
|  EV BY BOARD TEXTURE            EV BY SIZING                      |
|  +---------------------------+  +---------------------------+     |
|  | Texture | Bet  | Chk | D |  | Size    | Avg EV | Hands |     |
|  +---------+------+-----+---+  +---------+--------+-------+     |
|  | Axx     |+1.20 |+0.50|+.7|  | <33%    | +0.95  |  280  |     |
|  | BBx     |+0.60 |+0.30|+.3|  | 33-50%  | +0.70  |  250  |     |
|  | 8-2 Cn  |-0.30 |+0.10|-.4|  | 50-66%  | +0.55  |   90  |     |
|  | Mono    |-0.15 |+0.20|-.3|  | >66%    | +0.30  |   30  |     |
|  +---------------------------+  +---------------------------+     |
|                                                                    |
+------------------------------------------------------------------+
```

Green/red coloring on the Delta column. Grey out rows with < 50 hands in either column.

### SQL Editor Interface

```
+------------------------------------------------------------------+
|  CUSTOM STATS                                    [+ New Stat]     |
+------------------------------------------------------------------+
|                                                                    |
|  +-- Schema Browser --+  +-- SQL Editor ----------------------+  |
|  | hands              |  | SELECT                             |  |
|  |   id               |  |   COUNT(*) FILTER (WHERE           |  |
|  |   played_at        |  |     limp = TRUE                    |  |
|  |   stakes           |  |     AND position = 'SB'            |  |
|  |   ...              |  |   ) as numerator,                  |  |
|  | hand_players       |  |   COUNT(*) FILTER (WHERE           |  |
|  |   vpip             |  |     position = 'SB'                |  |
|  |   pfr              |  |     AND open_raise_opp = TRUE      |  |
|  |   three_bet        |  |   ) as denominator                 |  |
|  |   ...              |  | FROM hand_players hp               |  |
|  | actions            |  | JOIN hands h ON hp.hand_id = h.id  |  |
|  |   street           |  | WHERE hp.player_id = :hero_id      |  |
|  |   action_type      |  |                                    |  |
|  |   amount_bb        |  | [Run]  [Save as "SB Open Limp"]    |  |
|  |   ...              |  +------------------------------------+  |
|  +--------------------+                                          |
|                                                                    |
|  Result Preview:                                                  |
|  SB Open Limp: 3.2% (14 / 437)                                  |
|                                                                    |
+------------------------------------------------------------------+
|                                                                    |
|  Saved Custom Stats:                                              |
|  +------+------------------+--------+--------+                    |
|  | Name | Value            | Sample | Section|                    |
|  +------+------------------+--------+--------+                    |
|  | SB Open Limp | 3.2%    |    437 | Preflop|                    |
|  | Avg River OB | 142% pot|     23 | Custom |                    |
|  +------+------------------+--------+--------+                    |
|                                                                    |
+------------------------------------------------------------------+
```

---

## 4. Technical Spec

### Board Texture Classifier

Python utility at `backend/app/board_texture.py`.

```python
from dataclasses import dataclass
from enum import Enum

class RankStructure(str, Enum):
    ABB = "ABB"           # Ace + 2 broadways
    ABx = "ABx"           # Ace + 1 broadway + low
    Axx = "Axx"           # Ace + 2 non-broadway
    BBB = "BBB"           # 3 broadways no ace
    BBx = "BBx"           # 2 broadways + low no ace
    Bxx = "Bxx"           # 1 broadway + 2 low no ace
    T9_CONN = "T-9 Conn"  # Highest T or 9, connected
    T9_DISC = "T-9 Disc"  # Highest T or 9, disconnected
    EIGHT2_CONN = "8-2 Conn"  # Highest 8 or lower, connected
    EIGHT2_DISC = "8-2 Disc"  # Highest 8 or lower, disconnected

class SuitStructure(str, Enum):
    MONOCOLOR = "monocolor"
    TWO_TONE = "2tone"
    RAINBOW = "rainbow"

class TurnCategory(str, Enum):
    COMPLETED_DRAW = "completed_draw"
    DRAW_ADDING = "draw_adding"
    OVERCARD = "overcard"
    PAIRED_BOARD = "paired_board"
    BRICK = "brick"

@dataclass
class FlopTexture:
    rank_structure: RankStructure
    suit_structure: SuitStructure
    paired: bool

@dataclass
class TurnTexture:
    category: TurnCategory

@dataclass
class RiverTexture:
    category: TurnCategory  # same categories

RANK_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}

def _parse_card(card: str) -> tuple[int, str]:
    """Returns (rank_value, suit_char) from card string like 'Ah' or 'Ts'."""
    rank = card[0]
    suit = card[1]
    return RANK_VALUES[rank], suit

def _is_broadway(rank_val: int) -> bool:
    """Broadway = T, J, Q, K (10-13). Ace is NOT broadway."""
    return 10 <= rank_val <= 13

def _is_connected(rank_vals: list[int]) -> bool:
    """At least 2 cards within rank gap <= 2."""
    sorted_ranks = sorted(rank_vals)
    for i in range(len(sorted_ranks)):
        for j in range(i + 1, len(sorted_ranks)):
            if sorted_ranks[j] - sorted_ranks[i] <= 2:
                return True
    return False

def classify_flop(cards: list[str]) -> FlopTexture:
    """
    Classify a 3-card flop into rank structure, suit structure, and pairing.
    cards: list of 3 card strings like ['Ah', 'Ks', 'Jd']
    """
    assert len(cards) == 3
    parsed = [_parse_card(c) for c in cards]
    ranks = [r for r, _ in parsed]
    suits = [s for _, s in parsed]

    # Suit structure
    unique_suits = len(set(suits))
    if unique_suits == 1:
        suit_struct = SuitStructure.MONOCOLOR
    elif unique_suits == 2:
        suit_struct = SuitStructure.TWO_TONE
    else:
        suit_struct = SuitStructure.RAINBOW

    # Pairing
    paired = len(set(ranks)) < len(ranks)

    # Rank structure
    has_ace = 14 in ranks
    broadway_count = sum(1 for r in ranks if _is_broadway(r))
    highest = max(ranks)

    if has_ace:
        if broadway_count >= 2:
            rank_struct = RankStructure.ABB
        elif broadway_count == 1:
            rank_struct = RankStructure.ABx
        else:
            rank_struct = RankStructure.Axx
    elif broadway_count == 3:
        rank_struct = RankStructure.BBB
    elif broadway_count == 2:
        rank_struct = RankStructure.BBx
    elif broadway_count == 1:
        rank_struct = RankStructure.Bxx
    elif highest >= 9:  # T=10 is broadway, so 9 is the max for T-9 high
        # T-9 High: highest card is T(10) or 9, but T is broadway so
        # if we reach here, highest is 9
        if _is_connected(ranks):
            rank_struct = RankStructure.T9_CONN
        else:
            rank_struct = RankStructure.T9_DISC
    else:  # highest <= 8
        if _is_connected(ranks):
            rank_struct = RankStructure.EIGHT2_CONN
        else:
            rank_struct = RankStructure.EIGHT2_DISC

    return FlopTexture(
        rank_structure=rank_struct,
        suit_structure=suit_struct,
        paired=paired,
    )

def classify_turn_card(turn_card: str, flop_cards: list[str]) -> TurnTexture:
    """
    Classify the turn card relative to the flop.
    Priority: completed_draw > paired_board > overcard > draw_adding > brick
    """
    turn_rank, turn_suit = _parse_card(turn_card)
    flop_parsed = [_parse_card(c) for c in flop_cards]
    flop_ranks = [r for r, _ in flop_parsed]
    flop_suits = [s for _, s in flop_parsed]

    all_ranks = sorted(flop_ranks + [turn_rank])
    all_suits = flop_suits + [turn_suit]

    # Check paired_board: turn pairs a flop card
    if turn_rank in flop_ranks:
        return TurnTexture(category=TurnCategory.PAIRED_BOARD)

    # Check completed_draw: 3rd flush card or completes straight
    suit_counts = {}
    for s in all_suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    if any(c >= 3 for c in suit_counts.values()):
        return TurnTexture(category=TurnCategory.COMPLETED_DRAW)

    # Check for straight completion: 4 sequential ranks on board
    for i in range(len(all_ranks) - 3):
        if all_ranks[i+3] - all_ranks[i] == 3:
            # 4 consecutive ranks
            return TurnTexture(category=TurnCategory.COMPLETED_DRAW)

    # Check overcard: turn is highest card
    if turn_rank > max(flop_ranks):
        return TurnTexture(category=TurnCategory.OVERCARD)

    # Check draw_adding: 2nd flush card (flop was rainbow, now 2tone)
    # or adds straight connectivity
    flop_suit_counts = {}
    for s in flop_suits:
        flop_suit_counts[s] = flop_suit_counts.get(s, 0) + 1
    if max(flop_suit_counts.values()) == 1 and turn_suit in flop_suits:
        # Flop was rainbow, now 2tone
        return TurnTexture(category=TurnCategory.DRAW_ADDING)

    # Check if turn adds straight potential
    for fr in flop_ranks:
        if abs(turn_rank - fr) <= 2 and turn_rank != fr:
            return TurnTexture(category=TurnCategory.DRAW_ADDING)

    # Default: brick
    return TurnTexture(category=TurnCategory.BRICK)

def classify_river_card(river_card: str, board_cards: list[str]) -> RiverTexture:
    """
    Classify the river card relative to the 4-card board.
    Same categories as turn, applied to 4-card -> 5-card transition.
    """
    river_rank, river_suit = _parse_card(river_card)
    board_parsed = [_parse_card(c) for c in board_cards]
    board_ranks = [r for r, _ in board_parsed]
    board_suits = [s for _, s in board_parsed]

    all_ranks = sorted(board_ranks + [river_rank])
    all_suits = board_suits + [river_suit]

    # Paired board
    if river_rank in board_ranks:
        return RiverTexture(category=TurnCategory.PAIRED_BOARD)

    # Completed draw: flush (3+ same suit)
    suit_counts = {}
    for s in all_suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    if any(c >= 3 for c in suit_counts.values()):
        # Check if the river suit created the 3rd card
        board_suit_counts = {}
        for s in board_suits:
            board_suit_counts[s] = board_suit_counts.get(s, 0) + 1
        if board_suit_counts.get(river_suit, 0) >= 2:
            return RiverTexture(category=TurnCategory.COMPLETED_DRAW)

    # Straight completion: 5 sequential ranks
    for i in range(len(all_ranks) - 4):
        if all_ranks[i+4] - all_ranks[i] == 4:
            return RiverTexture(category=TurnCategory.COMPLETED_DRAW)

    # Overcard
    if river_rank > max(board_ranks):
        return RiverTexture(category=TurnCategory.OVERCARD)

    # Draw adding (less meaningful on river but kept for consistency)
    for br in board_ranks:
        if abs(river_rank - br) <= 2 and river_rank != br:
            return RiverTexture(category=TurnCategory.DRAW_ADDING)

    return RiverTexture(category=TurnCategory.BRICK)
```

### Hand Strength Evaluator

Python utility at `backend/app/hand_strength.py`.

```python
from dataclasses import dataclass, field

@dataclass
class HandClassification:
    # Made hand
    made_hand_id: int          # 11 (straight flush) down to -4 (no made hand)
    made_hand_name: str        # Human-readable name
    composite_group: str       # Nuts+, Strong, Top Pair, Marginal Made, Draw Only, Air

    # Draw flags (orthogonal)
    flush_draw: bool = False
    oesd: bool = False
    gutshot: bool = False
    combo_draw: bool = False
    backdoor_flush: bool = False
    backdoor_straight: bool = False
    has_draw: bool = False     # True if any draw flag is set

MADE_HAND_NAMES = {
    11: "Straight Flush", 10: "Quads", 9: "Full House",
    8: "Flush", 7: "Straight", 6: "Set", 5: "Trips",
    4: "Two Pair", 3: "Overpair",
    2: "Top Pair Good Kicker", 1: "Top Pair Weak Kicker",
    0: "Middle Pair", -1: "Weak Pair",
    -2: "Overcards", -3: "Ace High", -4: "No Made Hand",
}

def _composite_group(made_hand_id: int, has_draw: bool) -> str:
    if made_hand_id >= 7:
        return "Nuts+"
    if made_hand_id >= 3:
        return "Strong"
    if made_hand_id >= 1:
        return "Top Pair"
    if made_hand_id >= -1:
        return "Marginal Made"
    if has_draw:
        return "Draw Only"
    return "Air"

def classify_hand(
    hole_cards: list[str],
    board: list[str]
) -> HandClassification:
    """
    Classify a poker hand into made hand category + draw flags.

    hole_cards: list of 2 cards, e.g. ['Ah', 'Kd']
    board: list of 3-5 cards, e.g. ['Qs', '7h', '2c']

    Returns HandClassification with made_hand_id, draw flags, etc.
    """
    # Implementation uses treys for made hand evaluation,
    # custom logic for draw detection.
    # Full implementation omitted for brevity in PRD -- see
    # technical implementation during build.

    # 1. Parse all cards into rank/suit tuples
    # 2. Detect made hand (top-down from straight flush)
    # 3. Detect draw flags (flush draw, OESD, gutshot, backdoor)
    # 4. Compute composite group
    # 5. Return HandClassification

    ...
```

**Made hand detection logic** (pseudocode):
1. Combine hole_cards + board into 5-7 cards.
2. Check for straight flush, quads, full house, flush, straight using treys evaluator.
3. If three of a kind: distinguish set (pocket pair in hand) vs trips (pair on board).
4. If two pair: check if hero contributes to both pairs.
5. If one pair: classify as overpair, TPTK, TPWK, middle pair, or weak pair based on pair rank vs. board ranks and kicker rank.
6. If no pair: check for overcards, ace high, or no made hand.

**Draw detection logic** (pseudocode):
1. **Flush draw**: Count cards per suit across hole + board. If any suit has exactly 4 cards, flush_draw = True.
2. **OESD**: Sort all rank values. Look for sequences of 4 consecutive ranks where at least one hole card participates. If found, oesd = True.
3. **Gutshot**: Look for sequences of 4 ranks within a 5-rank span (one gap) where at least one hole card participates. If found, gutshot = True.
4. **Combo draw**: combo_draw = flush_draw AND (oesd OR gutshot).
5. **Backdoor flush** (flop only, board has 3 cards): Count suits. If any suit has exactly 3 cards (hole + board), backdoor_flush = True.
6. **Backdoor straight** (flop only): Check if 3 cards (hole + board) are within a 5-rank span. If so, backdoor_straight = True.

### Pot Tracking Implementation

Modifications to `backend/app/api/import_hands.py` inside `insert_parsed_hand()`.

**pot_before_action computation**:

```python
def _compute_pot_context(parsed: ParsedHand) -> list[dict]:
    """
    Walk through all actions in order and compute pot_before_action
    and bet_pct_pot for each action.

    Returns list of dicts with action_id -> {pot_before_action, bet_pct_pot}
    """
    # Initialize pot with blinds + antes
    pot = Decimal(0)
    for seat in parsed.seats:
        if seat.blind:
            pot += seat.blind
        if seat.ante:
            pot += seat.ante

    # Track each player's investment in the current street
    street_investments = {}  # player -> amount already in this street

    results = []
    current_street = 'preflop'

    for action in parsed.all_actions:
        if action.street != current_street:
            # New street: reset street investments, pot carries forward
            street_investments = {}
            current_street = action.street

        pot_before = pot
        player = action.player

        if action.action_type == 'call':
            call_amount = action.amount  # amount put in by calling
            pot += call_amount
            street_investments[player] = street_investments.get(player, Decimal(0)) + call_amount
        elif action.action_type in ('bet', 'raise'):
            # For raises: amount is the total "to" amount
            # The increment is: amount - what player already has in
            already_in = street_investments.get(player, Decimal(0))
            increment = action.amount - already_in
            pot += increment
            street_investments[player] = action.amount
        elif action.action_type in ('fold', 'check'):
            pass  # no money added

        # Compute bet_pct_pot
        bet_pct = None
        if action.action_type in ('bet', 'raise') and pot_before > 0:
            bet_pct = float(action.amount / pot_before * 100)

        results.append({
            'pot_before_action': float(pot_before),
            'bet_pct_pot': bet_pct,
        })

    return results
```

This runs during `insert_parsed_hand` and the values are stored on the `actions` table rows.

### New Database Columns

**On `hands` table** (precomputed board texture):
```sql
flop_texture_rank VARCHAR,   -- ABB, ABx, Axx, BBB, BBx, Bxx, T-9 Conn, T-9 Disc, 8-2 Conn, 8-2 Disc
flop_texture_suit VARCHAR,   -- monocolor, 2tone, rainbow
flop_paired BOOLEAN,         -- true if flop has paired cards
turn_texture VARCHAR,        -- completed_draw, draw_adding, overcard, paired_board, brick
river_texture VARCHAR,       -- same categories as turn
```

**On `actions` table** (pot context at time of action):
```sql
pot_before_action DECIMAL,   -- pot size (in $) before this action
bet_pct_pot DECIMAL,         -- amount / pot_before_action * 100 (for bets/raises only)
```

**On `hand_players` table** (pot type and multiway classification):
```sql
pot_type VARCHAR,            -- srp, 3bet, 4bet, 5bet
is_multiway BOOLEAN,         -- true if 3+ players saw the flop
```

**New table for custom stats**:
```sql
CREATE TABLE custom_stats (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    sql_query TEXT NOT NULL,
    stat_type VARCHAR NOT NULL DEFAULT 'percentage',  -- 'percentage' or 'value'
    display_section VARCHAR DEFAULT 'Custom',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**New API endpoints**:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/analysis/sizing` | Hero sizing analysis: avg size by street/position/pot type, distribution |
| GET | `/api/analysis/ev` | Decision analysis: EV by action, by hand strength, by board texture |
| GET | `/api/analysis/situational/{view}` | Situational view data (cbet/3bet/steal/river) |
| GET | `/api/analysis/spot-frequency` | Spot frequency per 1000 hands |
| GET | `/api/analysis/next-actions` | Next villain actions after hero's action |
| GET | `/api/custom-stats` | List saved custom stats with computed values |
| POST | `/api/custom-stats` | Create new custom stat |
| POST | `/api/custom-stats/run` | Execute SQL and return result (preview) |
| DELETE | `/api/custom-stats/{id}` | Delete custom stat |

### Performance Considerations

**Board texture and hand strength computation**:
- Board texture classification is O(1) per hand (simple if/else logic) and should be precomputed during insert. Cost: negligible.
- Hand strength classification involves more logic but is still O(1) per hand. For detail queries that need hand strength at a specific action point, compute on-demand rather than storing (too many combinations of board states to precompute). Cache results for the current query.
- For population queries that need hand strength (sizing tells at showdown), the computation across 6M+ action rows could be slow. Consider: compute and cache lazily, or limit to showdown hands only (much smaller set).

**Pot tracking**:
- pot_before_action is computed once during insert and stored. No on-the-fly computation needed. Storage cost: one DECIMAL per action row (~30M rows for 5M hands = ~240MB additional).

**Complex decision analysis queries**:
- Decision analysis (EV by action by hand strength by board texture) requires joining actions + hand_players + hands + board_cards with grouping. For 50k+ hands, these queries could take 1-5 seconds in DuckDB.
- Mitigation: Use DuckDB's columnar storage strengths (aggregation is fast). Add indexes on `hand_players(player_id, position)`, `actions(hand_id, street)`, `hands(flop_texture_rank)`.
- Consider: Materialized intermediate tables for the heaviest queries (e.g., a pre-joined table of hero actions with board texture and hand strength classifications).

**Custom SQL stats**:
- User queries run with a 5-second timeout.
- Read-only enforcement: DuckDB connection opened in read-only mode for custom stat execution.
- No indexes needed beyond existing ones -- custom stats are ad-hoc queries.

---

## 5. Execution Plan

### Build Order

The M5 features have clear dependencies. Shared infrastructure must be built first, then analysis features on top.

**Phase 1: Shared Infrastructure (builds on existing pipeline)**

| Task | Description | Effort | Depends On |
|------|-------------|--------|------------|
| Board texture classifier | `classify_flop()`, `classify_turn_card()`, `classify_river_card()` utility | 2-3 days | None |
| Board texture schema | Add columns to `hands` table, compute during insert | 1 day | Classifier |
| Board texture backfill | Run rebuild to populate all existing hands | 0.5 days | Schema |
| Pot tracking | `pot_before_action` and `bet_pct_pot` computation during insert | 3-4 days | None |
| Pot tracking schema | Add columns to `actions` table | 1 day | Pot tracking |
| Pot tracking backfill | Run rebuild to populate all existing actions | 0.5 days | Schema |
| Hand strength evaluator | `classify_hand()` with treys + custom draw detection | 4-5 days | None |
| Pot type + multiway flags | Compute `pot_type` and `is_multiway` during insert | 1-2 days | None |

Total: ~14-17 days for shared infrastructure.

**Phase 2: Bet Sizing Analysis (M5.3)**

| Task | Description | Effort | Depends On |
|------|-------------|--------|------------|
| Sizing analysis backend | `/api/analysis/sizing` endpoint: avg size by street/position/pot type | 2-3 days | Pot tracking |
| Sizing distribution frontend | Horizontal bar chart component | 1-2 days | Backend |
| Sizing vs hand strength | Cross-reference sizing with hand strength at showdown | 2-3 days | Hand evaluator |
| Hero vs population sizing | Side-by-side comparison (requires M4.2 population data) | 1-2 days | M4.2 |

Total: ~7-10 days.

**Phase 3: Situational Views (M5.4)**

| Task | Description | Effort | Depends On |
|------|-------------|--------|------------|
| Situational view backend | `/api/analysis/situational/{view}` endpoint | 3-4 days | All shared infra |
| C-Bet Situations dashboard | Frontend dashboard component | 3-4 days | Backend |
| 3-Bet Pots dashboard | Frontend dashboard component | 2-3 days | Backend |
| Steal Situations dashboard | Frontend dashboard component | 2-3 days | Backend |
| River Play dashboard | Frontend dashboard component | 2-3 days | Backend |

Total: ~13-17 days.

**Phase 4: Decision Analysis (M5.5)**

| Task | Description | Effort | Depends On |
|------|-------------|--------|------------|
| Action Profit backend | EV by action computation, by hand strength, by texture | 4-5 days | All shared infra |
| Action Profit frontend | Two-column comparison display | 2-3 days | Backend |
| Spot Frequency | Occurrence per 1000 hands, total impact ranking | 1-2 days | Backend |
| Next Villain Actions | Action tree after hero's action | 2-3 days | Backend |

Total: ~10-13 days.

**Phase 5: Custom Stat Creation (M5.6)**

| Task | Description | Effort | Depends On |
|------|-------------|--------|------------|
| Custom stats backend | CRUD endpoints, SQL execution with timeout and read-only | 2-3 days | None |
| SQL editor frontend | Monaco editor with schema browser, run/save | 3-4 days | Backend |
| Custom stat rendering | Display custom stats in stats page | 1-2 days | Frontend |
| custom_stats table | Schema + migration | 0.5 days | None |

Total: ~7-10 days.

### Dependencies on Other Milestones

**Dependencies on M2 (Stats v2)**:
- M5.1 (board texture) and M5.2 (hand strength) are shared infrastructure that M2.1c (postflop detail panels) consumes. Build these in M5 first, then M2 detail panels use them.
- M5.3 (sizing) provides the sizing distribution sub-section in Stats v2 postflop detail panels.
- M5.4 (situational views) are standalone dashboards but conceptually extend the Stats v2 master-detail pattern.

**Dependencies on M4 (Population Analysis)**:
- M5.1 (board texture) is required by M4.2's board texture splits.
- M5.2 (hand strength) is required by M4.2's sizing tells at showdown.
- M5.3 (pot tracking) is required by M4.2's sizing distributions.
- These are the same shared infrastructure -- build once, used by both milestones.

**No dependencies on M1 or M3**: M5 features are independent of benchmarks, leak detection, and progress tracking.

### Recommended Build Sequence

1. Board texture classifier + schema + backfill (M5.1)
2. Pot tracking + schema + backfill (M5.3 prerequisite)
3. Hand strength evaluator (M5.2)
4. Pot type + multiway flags (shared)
5. Bet sizing analysis views (M5.3)
6. C-Bet Situational View (M5.4 -- start with one)
7. Decision analysis: Action Profit (M5.5 -- core feature)
8. Remaining situational views (M5.4)
9. Decision analysis: Spot Frequency + Next Actions (M5.5)
10. Custom stat creation (M5.6 -- standalone, can be done anytime)

---

## 6. Testing

### Board Texture Classification Correctness

**Unit tests for `classify_flop()`**:

| Test Case | Input Cards | Expected Rank | Expected Suit | Expected Paired |
|-----------|-------------|---------------|---------------|-----------------|
| Ace-high dry | As Kh Jd | ABB | rainbow | false |
| Ace-high wet | As Qh 5h | ABx | 2tone | false |
| Ace-low dry | As 7h 3d | Axx | rainbow | false |
| Three broadway | Ks Qh Td | BBB | rainbow | false |
| Two broadway low | Ks Jh 6d | BBx | rainbow | false |
| One broadway low | Qs 7h 3d | Bxx | rainbow | false |
| T-9 connected | 9s 8h 6d | T-9 Conn | rainbow | false |
| T-9 disconnected | 9s 5h 2d | T-9 Disc | rainbow | false |
| Low connected | 8s 7h 5d | 8-2 Conn | rainbow | false |
| Low disconnected | 8s 4h 2d | 8-2 Disc | rainbow | false |
| Monotone | As Ks Qs | ABB | monocolor | false |
| Two-tone | As Kh Jh | ABB | 2tone | false |
| Paired board | Ks Kh 7d | BBx | 2tone | true |
| Paired low | 7s 7h 3d | 8-2 Conn | 2tone | true |
| Edge: T is broadway | Ts 7h 3d | Bxx | rainbow | false |
| Edge: 9 high | 9s 4h 2d | T-9 Disc | rainbow | false |

**Unit tests for `classify_turn_card()`**:

| Test Case | Flop | Turn | Expected |
|-----------|------|------|----------|
| Flush completing | 8h 7h 2c | 5h | completed_draw (3 hearts) |
| Straight completing | 8h 7d 6c | 5s | completed_draw (5-6-7-8) |
| Board pairing | Ks 7d 2c | 7h | paired_board |
| Overcard | 9h 7d 2c | Ks | overcard |
| Draw adding (flush) | Kh 7d 2c | 8d | draw_adding (2 diamonds) |
| Draw adding (straight) | Kh 7d 2c | 8s | draw_adding (7-8 connected) |
| Brick | Ah Kd 7c | 3s | brick |

### Hand Strength Evaluation Correctness

**Unit tests for `classify_hand()`**:

| Test Case | Hole Cards | Board | Expected Made Hand | Expected Draws |
|-----------|------------|-------|--------------------|----------------|
| Set | 8h 8s | 8d Ks 5c | Set (ID 6) | None |
| Trips | 8h Kd | 8s 8c 5d | Trips (ID 5) | None |
| Overpair | Qh Qs | Td 7c 3h | Overpair (ID 3) | None |
| TPTK | Ah Td | Ts 7c 3h | TPTK (ID 2) | None |
| TPWK | 9h Td | Ts 7c 3h | TPWK (ID 1) | None |
| Middle pair | 7h Ad | Ts 7c 3h | Middle Pair (ID 0) | None |
| Bottom pair | 3h Ad | Ts 7c 3h | Weak Pair (ID -1) | None |
| Underpair | 5h 5d | Ts 7c 3h | Weak Pair (ID -1) | None |
| Overcards | Ah Kd | 9s 7c 3h | Overcards (ID -2) | None |
| Ace high | Ah 4d | Ts 7c 3h | Ace High (ID -3) | None |
| No made hand | 5h 4d | Ts 7c 3h | No Made Hand (ID -4) | None |
| Flush draw | Ah 5h | Ts 7h 3h | Ace High (ID -3) | flush_draw=true |
| OESD | 9h 6d | 8s 7c 2h | No Made Hand (ID -4) | oesd=true |
| Gutshot | 9h 5d | 8s 7c 2h | No Made Hand (ID -4) | gutshot=true |
| Combo draw | Ah 5h | 8h 7h 6d | Ace High (ID -3) | flush_draw, oesd, combo_draw |
| TP + flush draw | Ah Th | Ts 7h 3h | TPTK (ID 2) | flush_draw=true |
| Straight | 9h 6d | 8s 7c 5h | Straight (ID 7) | None |
| Flush | Ah 5h | 8h 7h 3h | Flush (ID 8) | None |
| Full house | 8h 8s | 8d 5s 5c | Full House (ID 9) | None |
| Two pair | Kh 7d | Ks 7c 2h | Two Pair (ID 4) | None |
| Backdoor flush | Ah 5h | Ts 7h 3d | Ace High (ID -3) | backdoor_flush=true (flop) |

### Pot Tracking Accuracy

**Unit tests for pot computation**:

| Scenario | Actions | Expected pot_before for last action |
|----------|---------|-------------------------------------|
| Simple preflop | SB posts $0.50, BB posts $1.00, BTN raises to $2.50 | pot_before = $1.50 for BTN raise |
| Flop c-bet | Preflop pot = $5.00, hero bets $2.50 on flop | pot_before = $5.00, bet_pct = 50% |
| Multiple callers | SB $0.50, BB $1.00, CO raises $2.50, BTN calls $2.50, SB folds | pot_before for BTN call = $4.00 |
| Raise and re-raise | Pot $10, villain bets $5, hero raises to $15 | pot_before for hero = $15 ($10 + $5), bet_pct = 100% |
| All-in for less | Pot $20, hero all-in for $8 | pot_before = $20, bet_pct = 40% |

### Sizing Bucket Computation

**Unit tests**:

| Bet Amount | Pot Before | Expected Bucket |
|------------|------------|-----------------|
| $1.50 | $10.00 | Tiny (<33%) = 15% |
| $4.00 | $10.00 | Small (33-50%) = 40% |
| $5.50 | $10.00 | Medium (50-66%) = 55% |
| $8.00 | $10.00 | Large (66-100%) = 80% |
| $12.00 | $10.00 | Overbet (>100%) = 120% |
| $3.30 | $10.00 | Small (33-50%) = 33% -- boundary |
| $6.60 | $10.00 | Large (66-100%) = 66% -- boundary |
| $10.00 | $10.00 | Large (66-100%) = 100% -- boundary |

### Performance Benchmarks

| Query | Target | Notes |
|-------|--------|-------|
| Board texture classification (per hand) | < 0.1ms | O(1) computation |
| Hand strength classification (per hand) | < 0.5ms | treys evaluation + draw detection |
| Pot tracking (per hand, all actions) | < 0.2ms | Linear walk through actions |
| Full rebuild with texture + pot tracking (13k hands) | < 30 seconds | Current rebuild is ~8 seconds |
| Sizing analysis query (50k hands) | < 2 seconds | Aggregate query with grouping |
| Decision analysis query (50k hands, by hand strength) | < 5 seconds | Complex join + on-demand hand evaluation |
| Custom SQL stat execution | < 5 seconds (enforced) | Timeout kills query |

### Acceptance Criteria Checklist

**M5.1 Board Texture**:
- [ ] `classify_flop()` correctly classifies all 10 rank categories, 3 suit categories, and paired/unpaired
- [ ] `classify_turn_card()` correctly classifies all 5 turn categories
- [ ] `classify_river_card()` correctly classifies all 5 river categories
- [ ] Board texture columns are populated during `insert_parsed_hand`
- [ ] `/api/import/rebuild` correctly backfills board texture for all existing hands
- [ ] Board texture breakdown appears in Stats v2 postflop detail panels

**M5.2 Hand Strength**:
- [ ] `classify_hand()` correctly identifies all 14 made hand categories
- [ ] `classify_hand()` correctly detects all 6 draw flags
- [ ] Set is distinguished from trips correctly
- [ ] TPTK vs TPWK kicker threshold (T) works correctly
- [ ] Composite groups map correctly (Nuts+, Strong, Top Pair, Marginal Made, Draw Only, Air)
- [ ] Hand strength appears in Stats v2 postflop detail panels

**M5.3 Bet Sizing**:
- [ ] `pot_before_action` is correctly computed for all actions in a hand
- [ ] `bet_pct_pot` is correctly computed for bets and raises
- [ ] Sizing buckets correctly categorize all bet sizes
- [ ] Sizing analysis API returns correct data by street, position, and pot type
- [ ] Sizing distribution chart renders correctly in UI
- [ ] All-in for less than a full bet is handled correctly

**M5.4 Situational Views**:
- [ ] C-Bet Situations dashboard shows all relevant c-bet data in one view
- [ ] 3-Bet Pots dashboard shows preflop + postflop data for 3-bet pots
- [ ] Steal Situations dashboard shows steal + defense + post-steal data
- [ ] River Play dashboard shows river-specific stats with sizing analysis
- [ ] All views support existing filters (stakes, dates)
- [ ] All views show confidence indicators for small samples

**M5.5 Decision Analysis**:
- [ ] Action Profit correctly computes average EV for action vs. no-action
- [ ] EV by hand strength breakdown shows correct values per composite group
- [ ] EV by board texture breakdown shows correct values per texture category
- [ ] Spot Frequency shows occurrences per 1000 hands
- [ ] Next Villain Actions shows fold/call/raise distribution after hero's action
- [ ] Cells with < 50 hands are greyed out
- [ ] Caveats tooltip explains limitations

**M5.6 Custom Stats**:
- [ ] SQL editor supports syntax highlighting and schema browsing
- [ ] Custom stats execute in read-only mode
- [ ] Custom stats timeout after 5 seconds
- [ ] Custom stats persist across sessions
- [ ] Custom stat results render correctly on the stats page
- [ ] `:hero_id` parameter is properly injected
