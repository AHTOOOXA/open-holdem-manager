# Stat Cells — Extra Features Brainstorm

Review of stat cell specs from a professional poker coach perspective.
Goal: cut noise, fill real gaps, maximize coaching value per click.

---

## Cut / Merge — Overkill

### 1. 3-Bet IP / 3-Bet OOP Positional Rows (14 cells)

Position already determines IP/OOP in almost every case. "3-Bet IP from BB" is nearly impossible (only vs SB). "3-Bet OOP from BTN" is extremely rare.

**Totals** (IP vs OOP) are useful as a split, but the 7-position breakdown for each is wasted space.

**Action**: Kill 14 positional cells. Add IP/OOP as a toggle or filter on the main 3-Bet detail page. Show IP vs OOP range comparison as a widget there. Saves 14 cells.

### 2. `four_bet_range` vs `four_bet`

The distinction ("4-bet as % of opportunities" vs "4-bet as % of all hands") is confusing even for coaches. Nobody thinks in "4-bet range" separately.

**Action**: Merge its useful widget (#1, opportunity context) into the `four_bet` detail page. Saves 1 cell.

### 3. `call_4bet` Detail Page — Oversized for Sample

The doc itself admits flatting 4-bets is almost always wrong at 100bb. Sample sizes will be 5–15 hands over a typical database. Five widgets for 10 data points is a dashboard of noise.

**Action**: Keep the cell (the % matters as a red flag). Simplify detail page to hand list + results. No 5-widget treatment.

### 4. `five_bet` Detail Page — Same Problem, Worse

~10 instances in 100k hands. A trend sparkline of 10 data points is meaningless.

**Action**: Keep the cell. Simplify detail page to hand list + showdown summary.

### 5. `four_bet_fold` Detail Page — Subset of Rare Event

3–8 instances typically. "Trend sparkline" for 5 data points is cosmetic.

**Action**: Keep cell, simplify detail page.

**Net savings: ~14–15 cells removed, 3 detail pages simplified.**

---

## Add — Real Gaps

### 1. BB Defense Rate ⭐ High Priority

"How often does hero fold the BB to a raise?" — one of the top 3 things every coach looks at. At low-mid stakes, players fold BB 70%+ and bleed money.

**Needs**: Headline KV stat + full detail page.

**Detail page widgets**:
| # | Widget | Description |
|---|--------|-------------|
| 1 | **Response distribution** | Fold / Call / 3-bet split when facing a raise in the BB. The core view. |
| 2 | **Defending range heatmap** | 13x13 grid of hands hero continues with from BB (call = blue, 3-bet = red, fold = gray). |
| 3 | **EV by response** | bb/100 for fold vs call vs 3-bet from BB. Reveals if hero is folding +EV spots. |
| 4 | **By raiser position** | Defense rate broken down by who opened (EP through SB). Folding 80% vs UTG is fine; folding 80% vs BTN is a massive leak. |
| 5 | **Trend sparkline** | Rolling BB defense % over time. |

### 2. Isolation Raise ⭐ High Priority

Raising after one or more limpers — NOT an open raise. Different spot, different ranges, different sizing. In any pool below NL200, limps happen constantly. "Do you iso-raise limpers, and with what?" is a core coaching question.

**Needs**: KV cell + positional breakdown (at minimum).

**Detail page widgets**:
| # | Widget | Description |
|---|--------|-------------|
| 1 | **Range heatmap** | 13x13 grid of iso-raise combos. Should be wider than open-raise range because of dead money from limpers. |
| 2 | **By number of limpers** | Iso-raise frequency vs 1 limper vs 2+ limpers. More dead money but worse equity realization multiway. |
| 3 | **Sizing distribution** | Histogram of iso-raise sizes. Standard is open size + 1bb per limper — deviations are tells. |
| 4 | **EV impact** | bb/100 for iso-raised pots vs limped-along pots vs folded. Quantifies the value of isolating. |
| 5 | **Trend sparkline** | Rolling iso-raise % over time. |

### 3. Fold to Squeeze

Hero opens, gets called, faces a squeeze — what happens? This is a real spot that occurs regularly in 6-max. We track hero's squeeze play but not the defensive side.

**Needs**: KV cell + detail page.

**Detail page widgets**:
| # | Widget | Description |
|---|--------|-------------|
| 1 | **Response distribution** | Fold / Call / 4-bet split when facing a squeeze. |
| 2 | **Continuing range heatmap** | Which combos hero defends with vs folds when squeezed. |
| 3 | **EV by response** | bb/100 for each response. Folding is often correct here — but folding too much lets squeezers print money. |
| 4 | **By squeezer position** | Fold rate by who squeezed. Folding to a BB squeeze is different than folding to a BTN squeeze. |
| 5 | **Trend sparkline** | Rolling fold-to-squeeze % over time. |

---

## Consider — Worth Exploring

### Preflop Sizing Profile

Sizing leaks are mentioned in the `open_raise` detail page (widget #4), but sizing deserves more prominence. A coach immediately looks at: open size by position, 3-bet size (IP vs OOP), whether sizing is consistent (tells).

**Option A**: Dedicated "Sizing Profile" KV cell linking to a detail page with all preflop sizing data in one view.
**Option B**: Promote sizing to a top-2 widget on more detail pages (3-bet, squeeze, iso-raise).

### 3-Bet Pot Postflop Bridge

On the `three_bet` detail page, there's nothing about what happens AFTER hero 3-bets and gets called. "SPR going to flop in 3-bet pots" and "cbet frequency in 3-bet pots" are immediate coaching follow-ups.

**Suggestion**: Add a 6th "bridge widget" on the 3-bet detail page showing cbet rate + SPR in 3-bet pots. Connects preflop decisions to postflop consequences.

### Multiway Pot Frequency

How often does hero end up in 3+ player pots preflop? Usually a sign of too much cold-calling or overlimping. A single number on the VPIP detail page could flag this.

---

## What's Well Done — Keep As-Is

- **Range heatmaps as widget #1 everywhere** — correct default, always the first thing a coach opens.
- **"Coach question" framing** per stat — excellent UX, tells the user WHY they're looking at this.
- **EV-based widgets** — bb/100 by outcome/response turns data into decisions. Separates a tracker from a coaching tool.
- **Villain response breakdown on `open_raise`** — most trackers only show hero's action. Showing table response drives adjustments.
- **"Money burned" on limp/limp-fold** — concrete loss numbers change behavior faster than percentages.
- **Trend sparklines everywhere** — low-cost, high-value pattern.

---

## Summary

| Category | Items | Action |
|----------|-------|--------|
| Cut | 3-Bet IP/OOP positional rows (14 cells) | Replace with filter/toggle on 3-Bet detail page |
| Merge | `four_bet_range` → `four_bet` | Move opportunity widget into 4-bet detail |
| Simplify | `call_4bet`, `five_bet`, `four_bet_fold` detail pages | Keep cells, reduce to hand list + summary |
| **Add** | **BB Defense Rate** | KV cell + full detail page |
| **Add** | **Isolation Raise** | KV cell + detail page with positional breakdown |
| **Add** | **Fold to Squeeze** | KV cell + detail page |
| Consider | Preflop sizing profile | Dedicated view or promote sizing widgets |
| Consider | 3-bet pot postflop bridge | Add cbet/SPR widget to 3-bet detail page |
| Consider | Multiway pot frequency | Single number on VPIP detail page |
