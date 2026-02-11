# M5 Dependencies & Enhancements for Stat Detail Pages

> Cross-reference: which widgets require M5 infrastructure, what's missing, and build priority.

---

## 1. Widget → M5 Dependency Map

### No M5 dependency (can ship now)

These widgets use only existing `hand_players` / `actions` / `board_cards` data:

| Widget | Used by |
|--------|---------|
| **Range heatmap** (13x13) | open_raise, fold_to_3bet, call_open_raise, three_bet(_ip/_oop), vpip, pfr, four_bet, limp, fold_to_4bet, fold_to_steal, call_steal, three_bet_vs_steal, raise_cbet_flop_raised, donk_bet_flop |
| **Response distribution** (Fold/Call/Raise) | fold_to_3bet, fold_to_4bet, fold_to_cbet_flop/turn/river, fold_to_steal, call_steal, three_bet_vs_steal, fold_cbet_flop_raised, fold_cbet_flop_3bet, missed_cbet_fold_oop |
| **Trend sparkline** | all 105 cells |
| **Positional breakdown** (bar/comparison) | vpip, pfr, steal (BTN vs SB), three_bet_oop (IP vs OOP comparison), all IP vs OOP splits |
| **Fold equity** (simple: count villain folds / count hero bets) | three_bet, three_bet_ip/oop, four_bet, squeeze, five_bet, steal, three_bet_vs_steal, cbet_river, raise_cbet_flop_raised/3bet |
| **Villain response breakdown** (fold/call/raise after hero's action) | open_raise, cbet_flop, cbet_river, donk_bet_flop/turn/river, vs_missed_cbet_bet_ip |
| **Money burned/lost** (cumulative bb lost) | limp, limp_fold, four_bet_fold, four_bet_fold_steal, missed_cbet_fold_ip/oop, vs_missed_cbet_check_fold_ip/oop, fold_to_steal |
| **Entry type / PFR composition** | vpip (entry composition), pfr (raise type composition) |
| **VPIP-PFR gap** | pfr |
| **Opportunity context** | four_bet_range |
| **Street-by-street attrition funnel** | went_to_showdown |
| **Win method breakdown** (showdown vs non-showdown) | wwsf |
| **Continuation rate from flop** | cbet_turn |
| **Turn behavior after calling** | call_cbet_flop_raised, call_cbet_flop_3bet |
| **Flop-to-turn aggression drop** | af_turn, afq_turn |
| **Action composition** (raw bet/raise/call/fold counts) | af_flop/turn/river, afq_flop/turn/river |
| **W$SD when calling** | fold_to_cbet_river |
| **Showdown results** (W$SD in specific pot types) | call_cbet_flop_raised, call_cbet_flop_3bet, won_at_showdown |
| **Stack commitment gauge** | call_cbet_flop_3bet, raise_cbet_flop_3bet |
| **By 3-bettor / opener / stealer position** | fold_to_3bet, call_open_raise, three_bet_ip, fold_to_steal, call_steal |
| **SRP vs 3-bet pot comparison** | fold_cbet_flop_raised, fold_cbet_flop_3bet |

### Requires M5.1 — Board Texture Classification

| Widget | Used by | What it needs |
|--------|---------|---------------|
| **Board texture breakdown** (cbet % by Axx/BBx/T-9 Conn etc.) | cbet_flop, fold_to_cbet_flop, donk_bet_flop, raise_cbet_flop_raised, fold_cbet_flop_raised, fold_cbet_flop_3bet, missed_cbet_flop, missed_cbet_flop_ip/oop, missed_cbet_fold_ip/oop | `hands.flop_texture_rank`, `flop_texture_suit`, `flop_paired` |
| **Turn card impact** (cbet/fold by turn category) | cbet_turn, fold_to_cbet_turn | `hands.turn_texture` |
| **By villain bet size** (fold % by bet size bucket — needs pot context) | fold_to_cbet_river, missed_cbet_fold_ip/oop | `actions.pot_before_action` (technically M5.3) |

### Requires M5.2 — Hand Strength Evaluator

| Widget | Used by | What it needs |
|--------|---------|---------------|
| **Showdown hand composition** (what hero shows at SD) | cbet_river, three_bet, four_bet, five_bet, call_4bet, won_at_showdown | `classify_hand()` on showdown hands |
| **Hand strength in checking range** | missed_cbet_flop_ip, missed_cbet_flop_oop | `classify_hand()` at flop action point |
| **Which hands** (combo distribution for non-preflop) | raise_cbet_flop_raised, raise_cbet_flop_3bet, four_bet_fold, limp_fold | `classify_hand()` for hand categorization |

### Requires M5.3 — Pot Tracking / Bet Sizing

| Widget | Used by | What it needs |
|--------|---------|---------------|
| **Sizing distribution** (histogram of bet sizes as % pot) | cbet_river, donk_bet_river, open_raise | `actions.bet_pct_pot` |
| **Raise size faced** | limp_fold, missed_cbet_fold_ip | `actions.pot_before_action`, `bet_pct_pot` |
| **By villain bet size** (fold % bucketed by sizing) | fold_to_cbet_river, missed_cbet_fold_ip/oop, vs_missed_cbet_check_fold_oop | `actions.pot_before_action` |
| **5-bet size faced** | four_bet_fold | `actions.bet_pct_pot` |
| **Fold rate by steal sizing** | fold_to_steal | `actions.bet_pct_pot` |

### Requires M5.5 — Decision Analysis (EV per Action)

| Widget | Used by | What it needs |
|--------|---------|---------------|
| **EV by action/outcome** | open_raise, cbet_flop/turn/river, fold_to_3bet, call_open_raise, three_bet(_ip/_oop), four_bet, limp, vpip, pfr, squeeze, fold_to_4bet, call_4bet, five_bet, steal, fold_to_steal, call_steal, three_bet_vs_steal, four_bet_fold_steal, fold_to_cbet_flop/turn/river, donk_bet_flop/turn/river, all vs_missed_cbet, af_flop/turn/river, afq_flop/turn/river, fold_cbet_flop_raised/3bet, call_cbet_flop_raised/3bet, raise_cbet_flop_raised/3bet | Average `won_bb` grouped by action taken. Basic version possible now; rich version (by hand strength, by texture) needs M5.2 + M5.1 |

---

## 2. Missing High-Value Widgets (Add to Existing Specs)

### Widget A: Hand Strength When Betting (M5.2)

> "When you c-bet the flop, what do you actually have?"

**Add to:** `cbet_flop`, `cbet_turn`, `cbet_river`, `donk_bet_flop`

| Column | Description |
|--------|-------------|
| Hand Strength | Nuts+ / Strong / Top Pair / Marginal / Draw Only / Air |
| Count | Number of times hero bet with this category |
| % of Bets | What fraction of bets are this category |
| Avg Result | bb/100 when hero bets with this hand strength |
| Win Rate | % of these hands hero ultimately wins |

**Why this matters:** This is the centerpiece of postflop coaching in M5 PRD. A player c-betting 65% of flops is meaningless without knowing they're c-betting 90% of their air and only 40% of their draws. Hand strength breakdown immediately reveals if the betting range is balanced or exploitable.

**Coaching insight:** "You're c-betting 31% air — too much for wet boards. On dry boards that's fine, on wet boards those air bets lose money."

**M5 dependency:** M5.2 `classify_hand()` at the point of the flop/turn/river action.

---

### Widget B: Hand Strength When Checking (M5.2)

> "What do you check behind with? Is your checking range face-up weak?"

**Add to:** `missed_cbet_flop`, `cbet_flop` (as second tab), `af_flop`/`af_turn`/`af_river`

| Column | Description |
|--------|-------------|
| Hand Strength | Nuts+ / Strong / Top Pair / Marginal / Draw Only / Air |
| Count | Number of times hero checked with this category |
| % of Checks | What fraction of checks are this category |
| Avg Result | bb/100 when hero checks with this hand strength |

**Why this matters:** If hero NEVER checks strong hands, their checking range is face-up weak and villain can bet with impunity. A balanced checking range includes some traps.

**Coaching insight:** "Your checking range has 0% strong hands — whenever you check, villain knows you're weak and can probe 100%."

---

### Widget C: Sizing Distribution for All Bets (M5.3)

> "What sizes are you using when you bet?"

**Add to:** `cbet_flop`, `cbet_turn`, `donk_bet_flop`, `donk_bet_turn`, `open_raise`, `steal`

Currently only spec'd for `cbet_river`, `donk_bet_river`, `open_raise`. Every postflop bet stat should show sizing.

| Bucket | Label | Range | Count | % |
|--------|-------|-------|-------|---|
| Tiny | < 33% pot | | | |
| Small | 33-50% pot | | | |
| Medium | 50-66% pot | | | |
| Large | 66-100% pot | | | |
| Overbet | > 100% pot | | | |

**Why this matters:** Sizing is information. Using the same size for all hands is balanced; using different sizes for value and bluffs is a tell. Most players don't know their own sizing patterns.

**M5 dependency:** M5.3 `actions.bet_pct_pot`.

---

### Widget D: Sizing × Hand Strength Cross-Tab (M5.2 + M5.3)

> "When you bet small, what do you have? When you bet big, what do you have?"

**Add to:** `cbet_flop`, `cbet_turn`, `cbet_river` (the most impactful stats)

```
              Tiny   Small   Medium  Large   Overbet
Nuts+          2%     5%      8%     15%     40%
Strong         8%    12%     15%     20%     25%
Top Pair      15%    25%     30%     25%     15%
Marginal      20%    22%     18%     12%      5%
Draw Only     25%    18%     15%     13%     10%
Air           30%    18%     14%     15%      5%
```

**Why this matters:** THIS IS THE SIZING TELLS DETECTOR. If hero bets small with air and big with value, the numbers show it immediately. The M5 PRD calls this "the most exploitable pattern in modern poker." This single widget is worth more than most other widgets combined for improving a player's game.

**Coaching insight:** "Your overbets are 40% Nuts+ and 25% Strong — you only overbet the nuts. Opponents should fold everything to your overbets. Add some bluffs."

**M5 dependency:** M5.2 `classify_hand()` + M5.3 `actions.bet_pct_pot`.

---

## 3. Build Priority

### Phase 1: Ship Now (no M5 needed)

All widgets marked "No M5 dependency" above. This covers:
- Range heatmap, response distribution, trend sparkline
- Fold equity (simple count), villain response breakdown
- Money burned/lost, positional breakdowns
- All composition/comparison widgets
- Street-by-street funnel, win method breakdown

**Coverage:** ~60-70% of all widgets spec'd across all 5 files.

### Phase 2: After M5.1 (Board Texture)

Unlocks board texture breakdowns and turn card impact for 12+ postflop stats. Single biggest upgrade to postflop coaching utility.

**Coverage:** ~10% of widgets, but the highest-impact postflop ones.

### Phase 3: After M5.3 (Pot Tracking)

Unlocks sizing distribution, fold-rate-by-bet-size, and raise-size-faced for 10+ stats.

**Coverage:** ~10% of widgets.

### Phase 4: After M5.2 (Hand Strength)

Unlocks hand strength breakdowns (Widgets A, B, D) and showdown composition. The deepest coaching insights.

**Coverage:** ~10% of widgets, plus the new Widgets A-D.

### Phase 5: After M5.5 (Decision Analysis)

Upgrades all "EV by action" widgets from basic `won_bb` averages to proper decision analysis with hand strength × texture matrix.

**Coverage:** Enriches ~30 existing widgets.

---

## 4. Recommended Stat Detail Panel Layout With M5

Once all M5 infrastructure ships, the stat detail panel for a postflop stat like `cbet_flop` would show:

```
┌─────────────────────────────────────────────────────────┐
│  C-BET FLOP  ·  62.3%  (1,247 / 2,002)   [All | EP...] │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌── Board Texture Breakdown ────────────────────┐       │
│  │ Texture    CBet%  Size  FoldEq  EV    Hands   │ M5.1  │
│  │ Axx Rain    78%   33%   55%   +0.85   312     │       │
│  │ T-9 Conn    42%   58%   36%   +0.10   156     │       │
│  │ ...                                            │       │
│  └────────────────────────────────────────────────┘       │
│                                                           │
│  ┌── IP vs OOP ──┐  ┌── Hand Strength When Betting ──┐  │
│  │ IP:  71.2%    │  │ Nuts+   4%   +5.30 bb          │  │
│  │ OOP: 48.5%    │  │ Strong 12%   +2.85 bb          │  │
│  │               │  │ TP     26%   +1.45 bb          │  │ M5.2
│  └───────────────┘  │ Margin 11%   +0.20 bb          │  │
│                      │ Draw   15%   -0.35 bb          │  │
│  ┌── Sizing ─────┐  │ Air    32%   -0.90 bb          │  │
│  │ <33%:  42%    │  └─────────────────────────────────┘  │
│  │ 33-50: 33%    │                                       │ M5.3
│  │ 50-66: 19%    │  ┌── Villain Response ────────────┐  │
│  │ 66+:    6%    │  │ Fold: 48%  Call: 38%  Raise:14%│  │
│  └───────────────┘  └────────────────────────────────┘  │
│                                                           │
│  ┌── Sizing × Hand Strength ─────────────────────────┐  │
│  │           Tiny  Small  Med   Large  Over           │  │ M5.2
│  │ Nuts+      2%    5%    8%   15%   40%             │  │   +
│  │ Air       30%   18%   14%   15%    5%             │  │ M5.3
│  │ ...                                                │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌── Trend ──────────────────────────────────────────┐  │
│  │  ~~~~~~~~~~~∿∿∿∿∿∿∿∿∿∿∿∿∿~~~~ ---- 62.3%        │  │
│  └────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌── Hand List ──────────────────────────────────────┐  │
│  │  Cards  PF Action  Board  Flop Action  Result Date │  │
│  │  ...                                               │  │
│  └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

This is the full vision. Phase 1 ships with IP vs OOP + Villain Response + Trend + Hand List. Each M5 phase adds a widget block.
