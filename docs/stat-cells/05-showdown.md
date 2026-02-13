# Showdown — Clickable Cells & Detail Subpage Widgets

| # | Label | drillKey |
|---|-------|----------|
| 103 | WTSD | `went_to_showdown` |
| 104 | W$SD | `won_at_showdown` |
| 105 | WWSF | `wwsf` |

**Section total: 3 clickable cells**

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

### `went_to_showdown` — WTSD (Went To Showdown)

> Coach question: "Am I a calling station paying people off, or am I folding too much and getting bluffed?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Street-by-street attrition funnel** | `NOW` | Of all hands that saw the flop, what % fold on flop / turn / river before reaching showdown. THE key insight WTSD alone can't show. A 25% WTSD could mean hero folds flop often (tight, efficient) or calls to the river then folds (station bleeding money for two streets). The funnel shape reveals WHERE hero leaks — early fold-off = too tight, late fold-off = calling too long. *Enhanced version (M5.2): add hand strength at each fold point — what categories of hands is hero folding on each street?* |
| 2 | **WTSD by pot type** | `NOW` | WTSD in single-raised pots vs 3-bet pots vs 4-bet+ pots, plus multiway vs heads-up. Hero should typically go to showdown less in big pots (ranges are stronger, mistakes cost more) and less in multiway pots (more opponents = someone more likely to have it). Many players do the opposite — they hero-call in bloated pots hoping villain is bluffing. If 3-bet pot WTSD is higher than SRP, hero is likely a calling station in big pots. Uses `pot_type` and `is_multiway` flags. |
| 3 | **EV when reaching showdown vs folding before showdown** | `NOW` | Two bb/100 numbers side by side: EV for hands where hero reaches showdown vs EV for hands where hero folds before showdown (i.e., `saw_flop=true` and `went_to_showdown=false` and hero folded, not where villain folded). **Important**: this must EXCLUDE hands hero won without showdown (villain folded), because those are a completely different population — hero chose aggression, not passivity. Conflating "hero folded" with "villain folded" into "non-showdown" is a common tracker error that masks the real leak. If hero's fold-before-showdown EV is deeply negative, hero is calling too many streets then dumping — the worst of both worlds. If it's only moderately negative, hero is making disciplined folds. |
| 4 | **IP vs OOP split** | `NOW` | WTSD when hero is in position (`postflop_ip=true`) vs out of position (`postflop_ip=false`). More precise than position-based since it uses actual postflop IP status after the flop is dealt. IP should have higher WTSD (more control, better information, can pot-control more effectively). OOP should be lower (less information, harder to realize equity). If OOP WTSD equals or exceeds IP, hero is almost certainly calling too much out of position. |
| 5 | **Aggressor vs caller WTSD** | `NOW` | WTSD split by whether hero was the preflop aggressor (PFR / 3-bettor) vs the preflop caller. The aggressor should go to showdown at a different rate than the caller — the aggressor c-bets and barrels, so their showdown path is "bet-bet-bet-call" (value), while the caller's path is "call-call-call" (bluff-catching). If hero's caller WTSD is much higher than aggressor WTSD, hero is being a passive calling station rather than an active aggressor. |
| 6 | **Hand strength at showdown** | `M5.2` | What hand strength categories hero arrives at showdown with: Nuts+ / Strong / Top Pair / Marginal / Weak. If hero frequently reaches showdown with Marginal/Weak hands, those are calling-station calls. A healthy distribution has most showdowns in Strong+ categories. |
| 7 | **By position** | `NOW` | WTSD per position. Supplements widget 4 with the full 6-position breakdown (EP/MP/CO/BTN/SB/BB). Useful for identifying position-specific leaks (e.g., hero over-defends from the BB or never reaches showdown from EP). |
| 8 | **Trend sparkline** | `NOW` | Rolling WTSD over time. *Sample-size note: WTSD denominator is `saw_flop`, so sample accumulates reasonably fast. No special warning needed.* |

---

### `won_at_showdown` — W$SD (Won Money at Showdown)

> Coach question: "When I do get to showdown, am I showing up with winners or paying people off?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **W$SD by hand strength** | `M5.2` | Win rate at showdown broken down by hand strength category: Nuts+ / Strong / Top Pair / Marginal / Weak. Shows both the distribution (how often hero arrives with each category) AND the win rate per category. The combined view answers two questions at once: "Am I showing up with junk?" (distribution) and "Am I winning with what I show up with?" (win rate). *Note: this replaces a pure distribution widget — distribution alone is less actionable than distribution + outcome.* |
| 2 | **W$SD by pot type** | `NOW` | Win rate at showdown in SRP / 3-bet / 4-bet+ pots, plus multiway vs heads-up. If W$SD is decent in small pots but tanks in big pots, hero is getting value-owned in the spots that cost the most. Big-pot W$SD is worth 5-10x more in actual dollars than small-pot W$SD. Multiway W$SD should naturally be lower (more opponents); if it's MUCH lower, hero is going to multiway showdowns too light. |
| 3 | **Average pot won vs lost at showdown** | `NOW` | Average pot size (in bb) when hero wins at showdown vs when hero loses at showdown. If hero wins small pots but loses big ones, hero is being value-owned on later streets — winning the cheap hands and paying off the expensive ones. This asymmetry often points to a sizing leak: hero is not raising or reraising for value in big pots, but is calling down facing large bets. *Context needed (M5.3): cross-referencing with villain bet sizing reveals whether hero calls large bets too often or fails to raise for value.* |
| 4 | **IP vs OOP split** | `NOW` | W$SD when hero is in position (`postflop_ip=true`) vs out of position (`postflop_ip=false`). IP should be higher (better hand selection reaching showdown, more pot-control options). If OOP W$SD is notably lower, hero is reaching showdown OOP with dominated hands — a classic calling-too-much-OOP pattern. |
| 5 | **Aggressor vs caller W$SD** | `NOW` | W$SD split by whether hero was the preflop aggressor vs the caller. The aggressor's showdown range should be stronger (they built the pot with perceived strength). If caller W$SD is notably lower, hero is calling down passively with losing hands rather than playing back with raises or folds. |
| 6 | **By position** | `NOW` | W$SD from each position (EP/MP/CO/BTN/SB/BB). Supplements widget 4 with the full positional breakdown. |
| 7 | **Trend sparkline** | `NOW` | Rolling W$SD over time. *Sample-size note: denominator is `went_to_showdown`, which is ~25% of flop-seeing hands. At 10k total hands, expect ~1000-1500 showdowns — enough for overall trend but positional sub-slices may be noisy. Show confidence band on sparkline when sample < 200.* |

---

### `wwsf` — WWSF (Won When Saw Flop)

> Coach question: "After seeing the flop, am I winning my fair share of pots — and how am I winning them?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Win method breakdown** | `NOW` | Of all WWSF wins: what % won at showdown vs won without showdown (villain folded). THE key decomposition of this stat. If nearly all wins come from showdown, hero isn't bluffing or putting enough pressure — villain gets to see every card for free. If nearly all come from folds, hero may be over-bluffing and never getting to showdown with value. Healthy balance is roughly 40-50% showdown / 50-60% non-showdown. |
| 2 | **Heads-up vs multiway WWSF** | `NOW` | WWSF in heads-up pots vs multiway pots (`is_multiway`). THE most important WWSF dimension. WWSF should be dramatically lower multiway (more opponents = harder to win). A typical player wins ~48% heads-up but only ~30% multiway. If hero's multiway WWSF is close to heads-up, hero is either running well or getting to showdown too often in multiway pots. If hero's multiway WWSF is much lower than expected, hero may be over-investing in multiway pots then losing. |
| 3 | **WWSF by pot type** | `NOW` | Win rate in SRP / 3-bet / 4-bet+ pots after seeing the flop. **Important framing**: hero should win more in 3-bet pots ONLY when hero was the 3-bettor (range advantage). When hero CALLED the 3-bet, their WWSF should be lower (range disadvantage). If this widget shows high 3-bet pot WWSF overall, it could mask hero losing badly as the caller while winning as the 3-bettor. Display both sub-splits: hero-as-aggressor vs hero-as-caller within each pot type. |
| 4 | **IP vs OOP split** | `NOW` | WWSF in position (`postflop_ip=true`) vs out of position (`postflop_ip=false`). IP should be meaningfully higher (5-10%+). If the gap is small, hero is either very skilled OOP or running well. If the gap is enormous (15%+), hero's OOP postflop game needs work — they're being outplayed whenever they don't have position. |
| 5 | **Loss analysis: how hero loses pots** | `NOW*` | Of the pots hero DOESN'T win after seeing flop: what % hero folds on flop / turn / river vs loses at showdown. Shows where money goes — if most losses are river folds (called two streets then gave up), hero is bleeding the maximum before surrendering. If most losses are flop folds, hero may be too tight postflop. *Enhanced version (M5.2): add hand strength at each fold point for deeper analysis.* |
| 6 | **WWSF by board texture** | `M5.1` | WWSF grouped by flop texture: dry / wet / monotone / paired. Reveals if hero is winning their share on all board types or if specific textures are problem spots. A player who wins well on dry boards but poorly on wet boards likely struggles with draws and multi-street planning. |
| 7 | **Trend sparkline** | `NOW` | Rolling WWSF over time. *Sample-size note: WWSF denominator is `saw_flop`, so sample accumulates quickly. No special warning needed.* |
