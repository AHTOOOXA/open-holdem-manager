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
| `M5.2` | Hand strength evaluator | Needs `classify_hand()` at action point |
| `M5.5` | Decision analysis | EV per action with hand-strength x texture matrix |
| `NOW*` | None (basic) / M5.5 (rich) | Basic version uses `won_bb` averages; rich version after M5.5 |

---

## Detail Subpage Widgets

### `went_to_showdown` — WTSD (Went To Showdown)

> Coach question: "Am I a calling station paying people off, or am I folding too much and getting bluffed?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Street-by-street attrition funnel** | `NOW` | Of all hands that saw the flop, what % fold on flop / turn / river before reaching showdown. THE key insight WTSD alone can't show. A 25% WTSD could mean hero folds flop often (tight, efficient) or calls to the river then folds (station bleeding money for two streets). The funnel shape reveals WHERE hero leaks — early fold-off = too tight, late fold-off = calling too long. *Enhanced version (M5.2): add hand strength at each fold point — what categories of hands is hero folding on each street?* |
| 2 | **WTSD by pot type** | `NOW` | WTSD in single-raised pots vs 3-bet pots vs 4-bet pots. Hero should typically go to showdown less in big pots (mistakes cost more, ranges are stronger). Many players do the opposite — they hero-call in bloated pots hoping villain is bluffing. If 3-bet pot WTSD is higher than single-raise, hero is likely a calling station in big pots. |
| 3 | **Showdown vs non-showdown EV** | `NOW` | Two bb/100 numbers side by side: EV for hands that reach showdown vs EV for hands that don't (hero folds or villain folds earlier). If showdown EV is deeply negative, hero is calling down with too many losers. If non-showdown EV is very negative, hero is folding too much and donating money when giving up. The balance between these two numbers is the core WTSD insight. |
| 4 | **Hand strength at showdown** | `M5.2` | What hand strength categories hero arrives at showdown with: Nuts+ / Strong / Top Pair / Marginal / Weak. If hero frequently reaches showdown with Marginal/Weak hands, those are calling-station calls. A healthy distribution has most showdowns in Strong+ categories. |
| 5 | **By position** | `NOW` | WTSD per position. IP should have higher WTSD (more control, better information, can pot-control more effectively). OOP should be lower (less information, harder to realize equity). If OOP WTSD equals or exceeds IP, hero is almost certainly calling too much out of position. |
| 6 | **Trend sparkline** | `NOW` | Rolling WTSD over time. |

---

### `won_at_showdown` — W$SD (Won Money at Showdown)

> Coach question: "When I do get to showdown, am I showing up with winners or paying people off?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Showdown hand strength distribution** | `M5.2` | Categorize what hero shows down: premium (sets+), strong (top pair top kicker+), medium (middle pair, weak top pair), weak (bottom pair, Ace-high, worse). If hero reaches showdown with bottom pair and Ace-high too often, those are the calling-station hands. A healthy distribution has most showdowns in strong+ categories. |
| 2 | **W$SD by pot type** | `NOW` | Win rate at showdown in single-raised / 3-bet / 4-bet pots. If W$SD is decent in small pots but tanks in big pots, hero is getting value-owned in the spots that cost the most. Big-pot W$SD is worth 5-10x more in actual dollars than small-pot W$SD. |
| 3 | **Average pot won vs lost** | `NOW` | Average pot size (in bb) when hero wins at showdown vs when hero loses at showdown. If hero wins small pots but loses big ones, they're being reverse-implied-odds'd — calling down where villain has it and only reaching showdown cheaply when ahead. The asymmetry reveals sizing-related leaks. |
| 4 | **By position** | `NOW` | W$SD from each position. IP should be higher (better hand selection reaching showdown, more pot-control options). If OOP W$SD is notably lower, hero is reaching showdown OOP with dominated hands — a classic calling-too-much-OOP pattern. |
| 5 | **Trend sparkline** | `NOW` | Rolling W$SD over time. |

---

### `wwsf` — WWSF (Won When Saw Flop)

> Coach question: "After seeing the flop, am I winning my fair share of pots — and how am I winning them?"

| # | Widget | Phase | Description |
|---|--------|-------|-------------|
| 1 | **Win method breakdown** | `NOW` | Of all WWSF wins: what % won at showdown vs won without showdown (villain folded). THE key decomposition of this stat. If nearly all wins come from showdown, hero isn't bluffing or putting enough pressure — villain gets to see every card for free. If nearly all come from folds, hero may be over-bluffing and never getting to showdown with value. Healthy balance is roughly 40-50% showdown / 50-60% non-showdown. |
| 2 | **WWSF by pot type** | `NOW` | Win rate in single-raised / 3-bet / 4-bet pots after seeing the flop. Hero should win more in 3-bet pots (has range advantage as the aggressor). If WWSF drops in 3-bet pots, hero is losing the initiative in the exact spots where their range is strongest — a major postflop leak. |
| 3 | **IP vs OOP split** | `NOW` | WWSF in position vs out of position. IP should be meaningfully higher (5-10%+). If the gap is small, hero is either very skilled OOP or running well. If the gap is enormous (15%+), hero's OOP postflop game needs work — they're being outplayed whenever they don't have position. |
| 4 | **Loss analysis: how hero loses pots** | `NOW*` | Of the pots hero DOESN'T win after seeing flop: what % hero folds on flop / turn / river vs loses at showdown. Shows where money goes — if most losses are river folds (called two streets then gave up), hero is bleeding the maximum before surrendering. If most losses are flop folds, hero may be too tight postflop. *Enhanced version (M5.2): add hand strength at each fold point for deeper analysis.* |
| 5 | **Trend sparkline** | `NOW` | Rolling WWSF over time. |
