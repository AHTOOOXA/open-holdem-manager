# Hand2Note-compatible stats (General screen, stat popup, money)

OHM's **General** page shows the same numbers Hand2Note 4.1 shows on its General statistics
screen, computed from the same hand histories. This document describes, in poker terms, what
every number counts and how it is displayed, so the code in `backend/app/h2n/`,
`backend/app/general_cells.py`, `backend/app/hand_value.py`, `backend/app/money.py`,
`backend/app/api/general.py`, `backend/app/api/general_popup.py` and the frontend
`pages/GeneralPage.tsx`, `components/general/*`, `lib/h2n-*.ts` can be checked against it.

It describes behaviour only. It contains no Hand2Note code, identifiers or data files. The
numbers were checked by comparing OHM against Hand2Note's own output on real hands (section 9).

Notation used throughout:

- **H** = the player the stat is computed for (the hero on his own stats), **V** = any other
  player, **V#1** = one particular villain who must be the same person everywhere the tag
  appears (across streets).
- Action letters: **R** raise, **B** bet, **C** call, **X** check, **F** fold. Flags are in
  brackets, e.g. `H:R[first raise]`.
- `A → B` = action B is the next relevant action after A: only folds and checks may sit in
  between (section 2.7).
- `pre ...; flop ...` = one part per street; every listed street must match.
- **Case** = the hand where the measured action happened. **Opportunity** (opp) = the hand
  where it could have happened. A hand counts at most once as a case and once as an opp.
- Row keys such as `P01` or `C04` are OHM's own names for the rows (`backend/app/h2n/rows.py`).

---

## 1. Scope

- The General screen: the top line (hands, bb/100, VPIP, PFR), the PRE-FLOP table, the Steal /
  vs. Steal table and the POSTFLOP table, 102 values in total.
- The stat popup opened by clicking a cell: stat value, hand-strength bar, Won Hand / WTSD /
  W%SD, the hero's next decision, the Range / Boards / Bet Sizes / Hands tabs and the hand list.
- Money: winnings, rake, all-in EV and bb/100, as Hand2Note computes them.

The rest of OHM (Stats page, Results, Sessions, ...) keeps its own definitions.

---

## 2. Building blocks

### 2.1 Which hands count

- Every hand in which the selected player has a seat, inside the selected date range and
  filters. Walks and hands the player folded without investing count.
- Players who are sitting out are not part of the hand: marked as sitting out by the site, or
  posted nothing and had no action, or had no chips left after posting but still show actions.
- **Hands Hand2Note refuses to import** are left out of every General number (hand count,
  bb/100 and every cell). Hand2Note rebuilds each hand from its amounts and drops it when they
  do not add up. OHM keeps such hands for its other pages but flags them
  (`hand_players.h2n_valid = FALSE`). The checks, applied to GGPoker hands:
  1. a raise that is not above the current bet (the raise-to amount does not exceed what the
     player already had in plus the amount to call). When the small blind posted more than the
     big blind, the amount to call preflop is twice the small-blind post;
  2. a call whose amount is neither the amount to call nor a short all-in;
  3. a pot that pays out more than was put into it (negative pot rake, section 7.5);
  4. an action line the reader does not understand (e.g. "Bet & Muck").
  On the parity corpus 16 of 75,865 hands were refused, all with corrupted amounts.

### 2.2 The big blind behind "in bb" values

Every amount in big blinds (call increments, bet sizes, stacks, winnings in bb) uses the
hand's **main blind**:

1. start from the blinds in the header;
2. look at the regular blind posters only (the first "posts small blind" and the first "posts
   big blind" line; later blind lines, missed blinds, antes and straddles are never regular),
   largest post first, skipping a poster who is all-in by posting;
3. a regular big-blind post that differs from the header big blind replaces it; a regular
   small-blind post that differs from the header small blind raises the big blind to twice
   that post when the big blind is below it.

Action amounts are never looked at, so a deep all-in cannot move the big blind. Straddles are
ignored. (Checked on GGPoker; other rooms use the parser's big blind.)

### 2.3 Positions and column groups

Seats are labelled from the button backwards: BTN, CO, MP (exactly one seat, the hijack), EP,
and further seats as UTG+1 ... UTG+4. The blinds are SB and BB. The regular blinds are the
**first** small-blind and big-blind posts, so a player posting a big blind out of turn keeps the
ordinary position of his seat. Heads-up, the button (who posts the small blind) is the
heads-up SB and the other player the heads-up BB. With no small-blind poster, positions count
back from the big blind (the seat right before the big blind is BTN).

| Column | Positions in it |
|---|---|
| EP | EP and UTG+1 ... UTG+4 |
| MP | MP |
| CO | CO |
| BTN | BTN only (never the heads-up button) |
| SB | SB and the heads-up button |
| BB | BB and the heads-up BB |

At 6-max the columns are UTG, HJ, CO, BTN, SB, BB. The Steal table's hero filter is BTN + SB
(heads-up button included); CO is **not** a steal position. Positional variants of a cell share
one row; the hero's column is applied as a filter (`hand_players.h2n_pos`).

### 2.4 Action sequence and effective action types

For each street, the stat engine lists every voluntary action in order (blind, ante and
straddle posts are not actions). The hero's list stops after his fold. Seats with no action,
no post and no known cards are treated as sitting out.

Every action has its written type and an **effective type**. Only raises can change:

- a written raise is an effective **raise** when an effective raise was possible: the actor's
  effective stack (the smaller of his stack and the largest stack of the other players still
  in, minus what he already has in on this street) is larger than the amount to call. An
  incomplete all-in raise that adds chips beyond the call counts as a raise;
- otherwise it is an effective **call** when there was something to call (e.g. shoving over a
  bet when every opponent is already covered by the call);
- otherwise an effective **check** (e.g. the BB "raising" when every limper is already all-in
  for the big blind).

What was possible at each decision is also recorded: raise, bet, check, call, limp, opening,
first raise, and the possible amount ranges.

Effective amounts, in big blinds: for a **call**, the call **increment** (the chips added now,
not the "to" amount); for a **bet**, the bet capped at the largest other stack; for a
**raise**, the raise-to amount capped at the largest other stack plus that player's bet.

A player all-in from his posts has no preflop decisions, and a player who is all-in before a
street has no decisions on it.

### 2.5 Action flags

| Flag | Meaning |
|---|---|
| first raise | the first effective raise of the street; limps before it are fine (so an isolation raise is a first raise) |
| opening | preflop: the action is itself voluntary (call, bet or raise) and nobody limped or raised before it. Postflop: no non-fold action earlier on the street (a check counts as an action, so a bet after a check is not opening) and the action is not a fold |
| first of player | the actor had no earlier non-fold action on this street (posting a blind does not count) |
| last of player | the actor has no later action on this street |
| limp | a preflop call before any raise, while a raise was possible, by a player with nothing posted. An SB completion (and the heads-up button's completion) is **not** a limp |
| 3-bet type | a preflop raise facing exactly one earlier raise (squeezes and limp-reraises included) |
| IP / OOP to players left | section 2.6 |
| IP / OOP to VPIP players | section 2.6, reduced to players who put money in voluntarily |
| amount ≥ X bb, amount in [X, Y] bb | the effective amount (section 2.4), inclusive, with a 1e-6 bb tolerance |
| villain position | the acting villain sits in the listed positions |

### 2.6 Relative position (in position / out of position)

Relative position is **three-valued**: in position, out of position, or undefined. Out of
position is never just "not in position".

- **To players left**: compare the actor with every other seat that is still active at that
  moment: not folded, not all-in (or effectively all-in) and not sitting out. He is in position
  if he acts after all of them in postflop order, out of position if he acts before all of them,
  and undefined if he sits between them or if nobody else is active.
- **To VPIP players**: the same, but only against active players who have put money in
  voluntarily at any point of the hand so far.
- **Preflop only**: both are undefined when calling would commit the actor's whole effective
  stack.

Example: hero opens CO, BTN calls all-in, BB calls; on the flop BB checks and hero checks. BTN is
all-in and left out of the comparison, so hero's check is in position (to BB).

### 2.7 Row matching (cases)

A stat is defined by an action **row** per street, such as `V:R[first raise] → H:R`. A row
matches a street when:

1. its first action matches some action anywhere on the street (every start is tried);
2. each later action of the row matches the next actual action, except that actual **folds and
   checks** (by anyone, hero included) may be skipped in between. Any other unmatched action (a
   call, bet or raise) breaks the match.
3. A `V#1` action must be the same villain everywhere. The identity is checked after the action
   is taken: when the next action fits everything except the villain identity, the try ends;
   it is not skipped like an ordinary check. A row's first action is not affected.

Several rows on one street are combined with OR. A stat that lists several streets needs every
street to match. This skip rule is why "Fold to 3Bet" excludes squeezes (a call sits between the
open and the 3-bet) and why "Call Open Raise" excludes overcalls.

### 2.8 Opportunities

The opportunity is tested on the **last** street the stat lists; earlier streets must match as
cases. On that street the row's last action is replaced by each alternative:

| Measured action | Alternatives that make an opportunity (the action itself included) |
|---|---|
| raise | call, fold; also check preflop when the row has no earlier bet or raise |
| bet | check (only when the row has no earlier bet or raise), fold |
| call | raise, fold |
| check | bet (postflop) or raise (preflop), fold |
| fold | call, raise |

The replacement keeps the actor, positions, first/last of player, relative-position flags,
the villain binding and stack conditions. It drops "opening" and "first raise", which become
"opening was possible" / "a first raise was possible", and it drops the amount filter, which
becomes "such an amount was possible" for the measured action. In addition the measured action
must have been possible at that decision, whatever alternative the player chose:

- measured raise → an effective raise was possible;
- measured bet → a bet was possible (so folding to a donk bet is not a c-bet opportunity);
- measured check → a check was possible;
- measured limp → a limp was possible;
- measured call or fold → nothing, except a possible call amount when the call had an amount
  filter.

When a stat has several OR-ed rows, an alternative that is the same as or looser than another
one replaces it, and a stricter one is dropped. Opportunities = hands that match any surviving
alternative. This is why VPIP and PFR have different opportunity sets (section 4.1).

Consequences: 4-Bet and 5-Bet are not opportunities when the 3-bet or 4-bet left no effective
raise; Fold-to and Call stats have no such requirement, so Fold to 4-Bet + Call 4-Bet + 5-Bet
need not add up to 100.

### 2.9 The measured action ("hit")

The stat popup needs the action a case is about. Every OR-ed row that matches contributes the
action matched by its last element, taken from that row's first matching start. The measured
action is the **earliest** of these in the hand, not the one from the first row in definition
order. Example: VPIP (raise OR call) on "hero cold-calls, then raises over a 3-bet" measures the
call, so the popup's next decision is the raise. For a hand that is only an opportunity, the
decision is the earliest action that fits any alternative row. Case rows are tried first.

### 2.10 Expression cells and their samples

Some cells are arithmetic over other stats, using their case counts, opportunity counts and
the showdown/winner counts over their case hands (section 5). Operations are evaluated in IEEE
double, left to right exactly as written below. The **sample** of an expression is the largest
opportunity count among the stats it uses. Expression cells do not open a popup.

The single-action stats used by the expressions, per street (rows `E_<street>_<kind>`):

| Stat | Case | Opportunity |
|---|---|---|
| Bet | a hero bet on the street | an action where a bet was possible (bet, check or fold) |
| Raise | a hero raise | an action where a raise was possible (raise, call or fold) |
| Call | a hero call | any call, raise or fold |
| Bet or Raise | a hero bet or raise | same as cases of Any |
| Any Action | any hero action on the street (fold, check, call included) | equal to its cases |

All count **hands**, not actions.

### 2.11 Row list

| Key | Row | Used by |
|---|---|---|
| V01 | pre `H:R` OR `H:C` | VPIP |
| V02 | pre `H:R` | PFR |
| V03 | pre `H:R` OR `H:C` OR `H:X` | base of Won at Showdown |
| P01 | `H:R[first raise]` | Open Raise |
| P02 | `H:R[opening]` | Steal |
| P03 | `H:R[first raise] → V:R → H:F` | Fold to 3Bet (preflop table, Steal BTN) |
| P04 | `H:R[opening] → V:R → H:F` | Steal Fold to 3Bet SB |
| P05 | `H:R[opening] → V:R[villain SB/BB] → H:F` | Steal Fold to 3Bet Total |
| P06 | `V:R[first raise] → H:C[first of player]` | Call Open Raise |
| P07 | `H:R[3-bet type]` | 3-Bet Total |
| P08 | `V:R[first raise] → H:R` | 3-Bet by position |
| P09 / P10 | `V:R[first raise] → H:R[IP / OOP to VPIP players]` | 3-Bet In / Out of Position Total |
| P11 | `V:R[first raise, villain SB] → H:R` | 3-Bet In Position BB |
| P12 | `V:R[first raise, villain BTN/CO/MP/EP] → H:R` | 3-Bet Out of Position BB |
| P13 | `H:R[first raise] → V:R → H:R` | 4-Bet |
| P14 | `H:R[opening] → V:R → H:R` | Steal 4-Bet BTN / SB |
| P15 | `H:R[opening] → V:R[villain SB/BB] → H:R` | Steal 4-Bet Total |
| P16 | `H:R[first raise] → V:R → H:R → V:R → H:F` | 4-Bet-Fold |
| P17 | `H:R[opening] → V:R → H:R → V:R → H:F` | Steal 4-Bet-Fold BTN / SB |
| P18 | `H:R[opening] → V:R[villain SB/BB] → H:R → V:R → H:F` | Steal 4-Bet-Fold Total |
| P19 | `V:R[first raise] → H:R → V:R → H:F` | Fold to 4-Bet |
| P20 | `H:R[3-bet type] → V:R → H:C` | Call 4-Bet |
| P21 | `V:R[first raise] → H:R → V:R → H:R` | 5-Bet |
| P22 | `H:C[limp]` | Limp |
| P23 | `H:C[first of player, amount 0.5-1.0 bb] → V:R → H:F` | Limp-Fold |
| P24 | `V:R[first raise]`, then 1 to 4 `V:C`, then `H:R` | Squeeze |
| P25F/C/R | `V:R[opening, villain BTN] → H:F / H:C / H:R` | vs. Steal SB |
| P26F/C/R | `V:R[opening, villain BTN or SB] → H:F / H:C / H:R` | vs. Steal BB |
| C01 | pre `H:R[first raise, last of player]`; flop `H:B` | Continuation Bet Flop |
| C02 | C01 pre; flop `H:B[last of player]`; turn `H:B` | Continuation Bet Turn |
| C03 | C02 pre and flop; turn `H:B[last of player]`; river `H:B` | Continuation Bet River |
| C04 | pre `H:C[last of player, amount ≥ 2 bb]`; flop `V:B → H:F` | Fold to Continuation Bet Flop, vs. CBet Raised Pot Fold |
| C05 | C04 pre; flop `V:B → H:C[last]`; turn `V:B → H:F` | Fold to Continuation Bet Turn |
| C06 | C05 pre and flop; turn `V:B → H:C[last]`; river `V:B → H:F` | Fold to Continuation Bet River |
| C07 / C08 | pre `V:R[first raise] → H:C[last]`; flop `V:B → H:C` / `V:B → H:R` | vs. CBet Raised Pot Call / Raise |
| C09 / C10 / C11 | pre `H:R[first raise] → V:R → H:C[last]`; flop `V:B → H:F / H:C / H:R` | vs. CBet 3-Bet Pot |
| C12 | pre `H:C[last, amount ≥ 2 bb]`; flop `H:B[first of player, OOP to players left]` | Donk Bet Flop |
| C13 | pre `H:C[last]`; flop `H:C[last]`; turn `H:B[first, OOP to players left]` | Donk Bet Turn |
| C14 | pre `H:C[last]`; turn `H:C[last]`; river `H:B[first, OOP to players left]` | Donk Bet River |
| M01 | C01 pre; flop `H:X` | Missed Continuation Bet |
| M02 / M03 | C01 pre; flop `H:X[IP / OOP to players left]` | Missed CBet In / Out of Position |
| M04 | C01 pre; flop `H:X[IP]`; turn `V:B → H:F[first of player]` | Missed CBet IP → Fold |
| M05 | C01 pre; flop `H:X[OOP] → V:B → H:F` | Missed CBet OOP → Fold |
| N01 | pre `V#1:R[first raise] → H:C[last]`; flop `V#1:X → H:B[IP to players left]` | Bet In Position |
| N02 | N01 pre; flop `V#1:X → H:X[last, IP]`; turn `V:B → H:F` | Check \| Fold |
| N03 | N01 pre; flop `H:X[last] → V#1:X`; turn `H:B` | Bet Out of Position Turn |
| N04 | N01 pre; flop `H:X[last]`; turn `V:B → H:F` | Check-Fold |
| N05 | pre `V#1:R → H:C[last]` (any raise); flop `V#1:X → H:B[IP]` | part of vs. Missed Continuation Bet |
| N06 | N05 pre; flop `H:X[last] → V#1:X`; turn `H:B[first of player]` | part of vs. Missed Continuation Bet |
| E rows | per street: Bet, Raise, Call, Bet or Raise, Any Action (section 2.10) | Aggression, Aggression Frequency, showdown cells |

---

## 3. Display rules

### 3.1 Percent cells

All action stats, Aggression and 4-Bet Range use these rules for a value `v`:

1. sample 0 (no opportunities) → `--`;
2. `v` is NaN (0/0) → `--`; +infinity → `∞`; −infinity → `-∞`;
3. |v| > 100 (only Aggression can get there) → integer part, truncated toward zero, then
   shortened like counts (`1.2k`);
4. `v` exactly 100 (within 1e-6) → `99`. This is checked before rounding, so 5/5 shows `99`,
   while 199/200 = 99.5 rounds to `100`;
5. −10 < v < 10 (1e-6 tolerance) → one decimal;
6. otherwise → an integer.

Rounding is **half to even** on the double (2.5 → 2, 0.25 → 0.2), and a trailing `.0` is
dropped (2.0 → `2`, 9.96 → `10`). Do not use JavaScript's `toFixed`.

**Evaluation order matters.** An action stat's value is `cases / opps * 100` in double: divide
first, then multiply. `cases * 100 / opps` gives different doubles near .5 and different text.
Examples: 23/40 → 57.49999999999999 → `57` (not 58); 109/200 → 54.50000000000001 → `55` (not
54); 11/2000 → `0.5`; 29/2000 → `1.5`. Other vectors: 1/8 → `12`, 3/8 → `38`, 1/400 → `0.2`,
3/400 → `0.8`, 249/250 → `100`, 0/7 → `0`.

### 3.2 bb/100

1. infinite → `∞` / `-∞`; NaN (no hands) → `--`;
2. −1 < v < 1 → two decimals (0.456 → `0.46`);
3. −10 < v < 10 → one decimal (9.83 → `9.8`);
4. otherwise round to an integer (half to even), then shorten: below 100 as is; 1,000-9,999
   becomes `x.yk` only when the integer is a multiple of 100 (1200 → `1.2k`, 1234 → `1234`);
   10,000-99,999 → one-decimal thousands (`12.3k`); larger values as thousands or millions.

### 3.3 Hand counts

Below 1,000 as is; 1,000-9,999 → one-decimal thousands (`1.2k`); 10,000-999,999 → whole
thousands (`44k`; 44,500 → `44k`, 45,500 → `46k`, half to even); then `x.ym` and `Nm`.

### 3.4 Small samples and dimming

- The sample of an action stat is its opportunity count; of an expression, the largest
  opportunity count among its inputs; of bb/100, the hand count. The hand count has no sample.
- `0 < sample < 15`: the sample is shown after the value as a small grey number, bottom-aligned.
- `sample < 10`: the value and its sample are drawn at half opacity (the sample ends up at about
  a quarter). This includes sample 0, so `--` is always dimmed.
- Fewer than 10 hands: the hand count is dimmed.
- Blank cells in the layout are empty text cells, not zero-sample stats: render nothing, never
  `--`.

### 3.5 Vs-hero values for opponents

When the selected player is an **opponent**, each action cell also keeps counts over hands
where the measured action was made against the hero: the actor is not the hero, the hero is
still in the hand, and the hero is either the only remaining opponent or has put money in
voluntarily on that street. When that vs-hero opportunity count is **above 50**, the cell shows
the vs-hero value instead of the overall value, underlined. Expression cells, the hand count and
bb/100 are never substituted. On the hero's own stats this never applies.

### 3.6 Layout

The screen is built from data (`frontend/src/lib/h2n-layout.ts`): three tables (PRE-FLOP,
Steal, POSTFLOP) under a one-line summary, CSS grids with auto-sized tracks, 4px cell padding
(so empty rows and columns are 8px spacers), an 8px gap between tables and a 16px left inset.
Colours are fixed per column (one colour per position and per street); there is no
value-based colouring.

---

## 4. General-screen cells

### 4.1 Top line

| Cell | What it counts |
|---|---|
| Player name | the selected player |
| hands | hands in the filtered set (section 2.1) |
| bb/100 | sum over hands of (winnings rounded to cents / big blind), divided by the hand count, times 100 (section 7.7) |
| VPIP | case: a preflop call or raise (effective types). Opportunity: any preflop call, raise or fold, plus a preflop check when a raise was possible. Walks have no decision and are not opportunities |
| PFR | case: a preflop raise. Opportunity: any preflop decision **where an effective raise was possible**. A player facing a covering all-in (only call or fold) is a VPIP opportunity but not a PFR opportunity, so PFR's denominator can be smaller |

### 4.2 PRE-FLOP table (Total, EP, MP, CO, BTN, SB, BB)

| Row | What it counts |
|---|---|
| Open Raise | the hero makes the first raise preflop: raise-first-in **or an isolation raise over limpers**. Opportunity: the hero acted before any raise with a raise available. Column = hero position. The BB cell is blank on the screen; the API still serves it as `preflop.open_raise.BB` (BB iso-raises), and the Total includes them |
| Fold to 3Bet | the first raiser (isolation raisers included) faces a 3-bet from anyone and folds. Excluded: squeezes (someone called the open before the 3-bet) and spots where someone called the 3-bet before the hero acts. Opportunity: the same spot answered with a call or raise. BB cell blank on screen, served as `preflop.fold_to_3bet.BB` |
| Call Open Raise | the hero flat-calls the first raise as his first voluntary action. Overcalls (someone called before him) and limp-calls are excluded, so at 6-max EP has no opportunities (`--`) |
| 3-Bet, Total | a raise facing exactly one raise, **squeezes included**. Opportunity: facing exactly one raise with a re-raise possible |
| 3-Bet, by position | `V:R[first raise] → H:R` with the hero in that position: **squeezes excluded**, no position test despite the names, and no first-action requirement, so limp → face a raise → re-raise is a case. The positional cells therefore do not add up to the Total |
| 3-Bet In Position, Total | as the positional 3-bet, with the hero in position to every active VPIP player at the moment of his raise. If that is undefined, the hand is in neither IP nor OOP but still in the 3-Bet Total |
| 3-Bet In Position, EP-BTN | the same numbers as the 3-Bet row (same stats). SB is blank |
| 3-Bet In Position, BB | hero BB re-raising a first raise made from the SB |
| 3-Bet Out of Position, Total | as above with the hero out of position to the VPIP players |
| 3-Bet Out of Position, SB / BB | SB: the same stat as 3-Bet SB. BB: hero BB re-raising a first raise from BTN, CO, MP or EP. EP-BTN are blank |

### 4.3 PRE-FLOP right list

| Row | What it counts |
|---|---|
| 4-Bet | the first raiser (iso included) re-raises a 3-bet. Excluded when anyone calls between the open and the 3-bet, or between the 3-bet and the hero. Opportunity needs an effective raise to be possible |
| 4-Bet Range | `cases(Open Raise) * cases(4-Bet) / opps(Open Raise) / opps(4-Bet) * 100`, in that order (Open Raise % × 4-Bet % / 100). Sample = the larger of the two opportunity counts. With either sample 0 the result is 0/0 → `--` |
| 4-Bet-Fold | the first raiser 4-bets and folds to a 5-bet |
| Fold to 4-Bet | the hero 3-bet the first raiser directly (no squeeze) and folds to a 4-bet from anyone (cold 4-bets included); excluded when someone calls the 4-bet before the hero acts |
| Call 4-Bet | after any 3-bet (**squeezes included**) the hero calls a 4-bet |
| 5-Bet | the hero 3-bet the first raiser directly and re-raises the 4-bet. Opportunity needs an effective raise to be possible, so a 4-bet all-in that covers the hero is not an opportunity |
| Limp | a non-blind hero calls before any raise (open-limp or over-limp). SB completions and the heads-up button are never limps. Opportunity needs a limp to be possible |
| Limp-Fold | hero not in the BB: his first preflop action is a call adding 0.5-1.0 bb (so **SB completions count**), then he folds to a raise. Another call between his call and the raise breaks it, and so does a call of the raise before he folds |
| Squeeze | a first raise, then one to four callers, then a hero raise |

### 4.4 Steal and vs. Steal

| Row | Total (hero BTN or SB) | BTN | SB |
|---|---|---|---|
| Steal | raise into an unopened pot (limped pots are not opportunities) | same, hero BTN | same, hero SB or heads-up button |
| Fold to 3Bet | open, a 3-bet **from the blinds**, fold | the preflop Fold to 3Bet / BTN (iso-raises and any 3-bettor count) | open into an unopened pot, any 3-bettor, fold (differs from the preflop SB cell, which counts iso-raises) |
| 4-Bet | open, 3-bet from the blinds, hero re-raises | open, any 3-bet, re-raise | same, hero SB |
| 4-Bet-Fold | open, 3-bet from the blinds, 4-bet, fold to a 5-bet | open, any 3-bet, 4-bet, fold | same, hero SB |

| vs. Steal | SB (steal from the BTN) | BB (steal from the BTN or SB) |
|---|---|---|
| Fold / Call / 3-Bet | the hero answers an opening raise from the BTN | the hero answers an opening raise from the BTN or the SB |

Folds and checks may sit between the steal and the hero (the SB folding before the BB acts is
fine); a cold call in between breaks the match. Fold + Call + 3-Bet is about 100 per column.

### 4.5 POSTFLOP table

| Row | What it counts |
|---|---|
| Continuation Bet, Flop | preflop the hero made the first raise and it stayed his last preflop action (a single-raised pot with the hero as raiser; isolation raises count; callers and multiway are fine); on the flop he bets. Opportunity: a flop decision where a bet was possible |
| Continuation Bet, Turn / River | as above, plus a flop bet (and for the river a turn bet) that stayed the hero's last action on that street, then a bet on the turn (river). Delayed c-bets do not count |
| Fold to Continuation Bet, Flop | preflop the hero's last action was a call adding **at least 2 bb**; on the flop any villain bets and the hero folds. The bettor need not be the preflop raiser, 3-bet pots and multiway pots count. Excluded when someone calls or raises the bet before the hero acts. A BB calling a 2.5 bb open adds only 1.5 bb and is not counted; an SB calling it adds 2 bb and is |
| Fold to Continuation Bet, Turn / River | the same preflop call, the hero calls a flop bet (and a turn bet for the river) as his last action on that street, then folds to a bet |
| Aggression, per street | `(cases(Bet) + cases(Raise)) / cases(Call)` of the single-action stats: **hands, not actions**, so a hand with a bet and a raise counts twice in the numerator. Bets with no calls → `∞` |
| Aggression Frequency, per street | `cases(Bet or Raise) / cases(Any Action) * 100`: hands with a hero bet or raise over hands with any hero action on that street, folds included |
| Donk Bet, Flop | preflop the hero's last action was a call adding at least 2 bb; on the flop he bets as his first action while **out of position to every remaining player**. There is no check that the raiser is still in. Opportunity: a check, bet or fold with the same flags |
| Donk Bet, Turn | preflop last action a call (no amount), flop last action a call, turn first action a bet out of position to all |
| Donk Bet, River | preflop last action a call, turn last action a call, river first action a bet out of position to all. There is no flop condition |
| vs. CBet Flop, Raised Pot: Fold | the same stat as Fold to Continuation Bet Flop |
| vs. CBet Flop, Raised Pot: Call / Raise | preflop the hero called the first raise directly as his last preflop action (no overcalls, no amount limit); on the flop he calls / raises a villain bet. Because the Fold cell has a different preflop condition, Fold + Call + Raise need not be 100 |
| vs. CBet Flop, 3-Bet Pot: Fold / Call / Raise | the hero opened, faced a 3-bet and called it as his last preflop action; on the flop he folds / calls / raises a villain bet. Cold-called 3-bets and 4-bet pots are excluded |

### 4.6 Missed continuation bet and vs. missed continuation bet

| Cell | What it counts |
|---|---|
| Missed Continuation Bet | the c-bet preflop condition, then a flop check. Opportunity: a flop decision where a check was possible. C-Bet + Missed is about 100; they differ when the hero folds while a check was available |
| In Position / Out of Position | the flop check is in position / out of position to the players left. A multiway middle seat is in neither, but is in the total |
| In Position → Fold | after the in-position check, a villain bets the turn and the hero folds as his first turn action |
| Out of Position → Fold | check out of position, a villain bets, the hero folds on the same flop |
| vs. Missed Continuation Bet | `(cases(A) + cases(B)) / (opps(A) + opps(B)) * 100`, sample = the larger of opps(A) and opps(B). Both parts: the hero called a raise from V#1 (any raise, so 3-bet pots count) as his last preflop action. B: V#1 checks the flop and the hero bets in position. A: the hero checks the flop, V#1 checks behind, the hero bets the turn as his first action. These parts are not the cells shown below it |
| Bet In Position | the hero called the first raise from V#1 (single-raised pots only); V#1 checks the flop and the hero bets in position |
| Check \| Fold | same preflop; V#1 checks, the hero checks back in position; on the turn any villain bets and the hero folds |
| Bet Out of Position Turn | same preflop; the hero checks the flop, V#1 checks behind; the hero bets the turn |
| Check-Fold | same preflop; the hero's last flop action is a check; on the turn a villain bets and the hero folds. There is **no** position condition despite the label, so in-position hands are included |

### 4.7 Showdown cells

| Cell | What it counts |
|---|---|
| Went to Showdown | went to showdown / hands with any hero **flop** action. Preflop all-ins are excluded |
| Won at Showdown | won at showdown / went to showdown, over hands with any hero preflop call, raise or check. Preflop all-in showdowns are included |
| Won When Saw Flop | hands the hero is a winner of / hands with any hero flop action. Split pots count as won |

"Went to showdown" and "winner" are defined in section 5.

---

## 5. Hand results

- **Went to showdown**: at the end of the hand at least two players have not folded and the
  player is one of them.
- **Winner** (a yes/no flag per hand, not "net won > 0" and not per pot):
  - without a showdown: the player did not fold;
  - with a showdown: among the non-folded players whose cards are known, the ones with the best
    hand on the full board. With several boards (run it twice), the union of each board's
    winners. If no non-folded player has known cards, or the board is incomplete, whoever
    collected.
  - So a split pot is a win even when the player lost money, and a player who wins only a side
    pot (a shorter all-in had the best hand) is **not** a winner.
- **Won at showdown** = winner and went to showdown. OHM's older `won_at_showdown` column
  (collected anything) is not used here.

---

## 6. Stat popup

### 6.1 Header, stat value and strength bar

- The title is the stat's full name with `->` shown as `→`.
- Stat value: `cases / opps * 100`, formatted as in section 3.1, with the same sample and
  dimming rules.
- Strength bar: one segment per hand-value category of the stat street (section 6.4), sized by
  the number of **cases** in it, with a label `NN% weak` (weak categories / all cases, rounded to
  an integer). Clicking a segment selects that category.

### 6.2 Won Hand, WTSD, W%SD

Computed over the stat's **cases** only:

| Item | Numerator | Denominator |
|---|---|---|
| Won Hand | cases where the hero is a winner | cases |
| WTSD | cases where the hero went to showdown | cases |
| W%SD | cases where the hero went to showdown and is a winner | cases that went to showdown |

### 6.3 The hero's next decision (Fold, Call, Raise, Bet, Check)

These describe what the hero did **next** after the measured action, over the cases where that
action is not a fold.

1. The **next relevant action** after an action X:
   - after a bet or raise: the next voluntary action (call, bet or raise) by anyone, on any
     street; if there is none, the action right after X;
   - after a check: the next voluntary action if it is on the same street, else the action
     right after X;
   - after a call: take N = the next non-fold action. With no N, the action right after X. If N
     is on a later street and is a check, apply the rule again from N, except when X is a
     villain's call and N is the hero's own check (then N itself). If N is on a later street and
     not a check, N. If N is on the same street: the next voluntary action if it is on the same
     street, N if there is no voluntary action left in the hand, and nothing if the next
     voluntary action is only on a later street;
   - after a fold: nothing.
2. Let R be the next relevant action after the measured action. Starting from the next relevant
   action after R, skip villain folds and keep following next relevant actions until an action
   by the hero is found: that is the hero's next decision.
3. The decision counts only if R's written type was effectively possible for R (a villain's
   written all-in "raise" that could only be a call blocks the hand).
4. The decision's effective type gets a case and an opportunity; each alternative that was
   possible at that decision gets an opportunity. Alternatives postflop: bet ↔ check; fold →
   call, raise; call → fold, raise; raise → fold, call. Preflop, check → raise and raise → fold,
   call, check.
5. Fold / Call / Raise are shown when there is at least one fold opportunity; Bet / Check when
   there is at least one bet opportunity. The three need not add up to 100 because raise
   opportunities need an effective raise.

In the Boards and Bet Sizes rows the next decision is simply the hero's very next action.

### 6.4 Hand value categories (Range tab)

Each case is put into exactly **one** category, computed from the hero's hole cards and the
board of the stat street (the last street the stat lists): the first category in list order
whose rule matches, else **Other**. Streets get a value up to the player's last seen street:
the street of his final fold, or else the last street anyone acted on, so a run-out after an
all-in is not classified. With several boards, the first board is used.

The rules use these per-street properties (our own terms):

- **Air**: the hand is no better than high card for the hero (high card, or the same made hand
  as the board without improving it, or no hole card plays, or the board plays). The
  **high-card rank** is then the hero's highest card that matters (on a paired board, his first
  kicker above the board's kicker).
- **Ace high**: air with an ace as the high-card rank.
- **Overcards**: two overcards when the hero's second kicker beats the board's best unpaired
  card, one overcard when only his best does.
- **Pairs** (none when air, trips or better). With P the rank the hero pairs, t1 the top board
  rank and t2 the second distinct board rank: a pocket pair is an **overpair** above t1, a
  **pocket low pair** when P ≤ t2 or P < 6, else a **pocket middle pair**. Otherwise **top pair**
  (P = t1), **middle pair** (P = t2 and P ≥ 6) or **low pair**. Top-pair kicker strength is the
  position of the hero's kicker in A-to-2 order with board ranks skipped (1 = top kicker, 2 =
  second, 3 or more = weak; no playing kicker = no kicker class).
- **Two pair or better**: two pair from both hole cards, trips (paired board), set (pocket pair
  hitting an unpaired board), straight, flush, full house, quads, straight flush, each with at
  least one hole card playing. A pocket pair on a trips board (AA on 777) is an overpair.
- **Draws** (flop and turn, only when the hand is weaker than what the draw makes): flush draw
  (suited hole cards with two board cards of the suit, or one hole card with three board cards
  of its suit); straight draws from the number of ranks that complete a straight using a hole
  card (one rank = **gutshot**, two or more = **straight draw**). "Any draw" = flush draw,
  straight draw or gutshot.

Flop categories (in order; weak ones marked *):

1. Trash* — air without a draw and not ace high (KQ/KJ/QJ with two overcards excluded)
2. KQ, KJ, QJ* — two overcards with KQ, KJ or QJ, no draw
3. Ace High* — ace high, no draw, not AK/AQ/AJ with two overcards
4. Overcards AK-J* — AK, AQ or AJ with two overcards, no draw
5. Gutshot* — air with only a gutshot (not two overcards)
6. Draw* — air, low pair or pocket low pair with a flush or straight draw; or two overcards
   with a gutshot
7. Low Pockets* — pocket low pair without a flush or straight draw
8. Low Pair — low pair (not pocket) without a flush or straight draw
9. Middle Pair — middle pair or pocket middle pair
10. TPWK — top pair, weak kicker
11. TPGK — top pair, top or second kicker
12. Overpair
13. Set
14. Two Pairs+ — two pair or better except a set

Turn: as the flop, with these changes: a gutshot no longer stops Ace High; row 7 is **Draw +
Pair*** (a straight draw with a pocket middle/low pair, or any draw with a middle/low pair);
Low Pair includes pocket low pairs; TPWK is any top pair without a top/second kicker
(including a kicker that does not play).

River (no draws; uses the turn and river properties of the same hand):

1. Missed Trash* — air on the river after air without draw or ace high on the turn, or after a
   pair or better on the turn
2. Missed Overcards* — air on turn and river without a flush/straight draw on the turn, with
   two broadway cards (AK-AJ, AT, KQ, KJ, QJ, KT, QT, JT)
3. Ace High* — ace high on the river
4. Missed Draw* — air/low pair/pocket low pair with a draw on the turn, still air or a low pair
   on the river
5. Low Pair — low pair or pocket low pair, no flush/straight draw on the turn
6. Middle Pair
7. TPWK — top pair without the top kicker
8. TPTK — top pair, top kicker
9. Overpair, 10. Set, 11. Two Pairs+

Frequency in the Range tab = category count / all cases, as a whole percent (half to even).
Bars are as wide as count / largest count, inside a row of at least 200px whose label cannot
shrink, so the longest bars clamp to the same length. Empty categories are shown dimmed and
cannot be selected; Other appears only when it has hands.

Examples (hole | board → category): Jh9s | 8h Kh Kd → Trash; AhKd | Qs 7c 2h → Overcards AK-J;
Ah5d | Ks 7c 2h → Ace High; Jh9d | Th 7c 2s → Gutshot; 9h8h | Kh 4h 2c → Draw; 6h6d | Kh 7c 5s →
Low Pockets; 7d6d | Kc 7c 2s → Middle Pair; Kh9d | Kc 7c 2s → TPWK; KhQd | Kc 7c 2s → TPGK;
Kh2d | Kc Ks 7d → Two Pairs+; turn 7h6h | 7c 8s 2d 4h → Draw + Pair; river 9h8h | Kh 4h 2c 3d 7s
→ Missed Draw; river AhQd | Ks 7c 2h 3d 5c → Missed Overcards. More in
`backend/tests/test_hand_value.py`.

### 6.5 Board categories (Boards tab)

Not exclusive: a board can be in several rows or none.

| Street | Rows |
|---|---|
| Flop | Rainbow (three suits), Suited (monotone), Ace High (an ace on the flop), Paired (exactly one pair; trips are not "paired") |
| Turn | Rainbow (four suits), Ace High, Third Card to Flush (the turn is the third card of a suit that appeared exactly twice on the flop) |
| River | Ace High, Third Card to Flush (same idea on the first four cards), Over Card (the river is strictly higher than every earlier card) |

Per row: opportunities and cases of the stat on such boards, the frequency, a mini strength bar
over the cases and the next-decision split. With several boards, each board's category adds
to its own textures' bars. Rows with no opportunities are hidden; rows with no cases are
dimmed.

### 6.6 Bet-size buckets (Bet Sizes tab)

Only the buckets of the measured action's type and stage are shown.

| Measured action | Buckets |
|---|---|
| postflop bet (size = bet / pot before the bet) | Overbet (above 1.001), 0.8-1 pot, 0.6-0.8 pot (0.6-0.799), 0.4-0.6 pot (0.4-0.599), 0.25-0.4 pot (0.251-0.399), ≤ 0.25 pot. Effective stack / pot must be at least 1.25 |
| postflop raise | Min Raise: raise-to / previous bet between 1.0 and 2.0, not all-in, stack-to-pot ≥ 1.25 |
| postflop call / fold (size of the villain's bet) | vs. overbet (above 1.001), vs. 0.75-1 pot, vs. bet ≤ 0.6 pot; no stack condition |
| preflop raise | 2-2.5x and 2.51-3x the previous raise; < 2.2 bb (2.0-2.2), 2.2-2.7 bb (2.21-2.7), 2.7-3 bb (2.71-3.0), > 3 bb (3.01 and up); not all-in, stack-to-pot ≥ 1.25 |
| check | no buckets |

Ratios are rounded to 7 decimals and bucket ends compared with a 1e-6 tolerance, so sizes in the
small gaps between buckets fall in none. "Pot before the bet" includes earlier bets on the
street, minus any part of other bets the hero could not cover. A case lands in the bucket of
its size; an opportunity counts for a bucket when the hero could have acted with a size in it
(for call/fold buckets: when the villain's bet is in it). Bet, raise and check buckets are
shown when they have a case, call and fold buckets when they have any sample.

### 6.7 Hands list

- The stat's cases matching the selection (category, board row, bet size or bar segment);
  newest first, loaded in pages.
- Columns: hand value on the stat street, hole cards (high card first; pairs in the suit order
  hearts, diamonds, clubs, spades), preflop actions, then per street the board cards in dealt
  order, the pot and the actions.
- Pot cell: the street's starting pot in big blinds (under 5 → one decimal, else an integer).
  Rooms that take rake only at the end of the hand (GGPoker among them) show the gross pot.
- Actions: one token per action, a letter plus the amount in big blinds (under 5 → one
  decimal). B and C show the chips added, R the raise-to total; X and F have no amount; an
  all-in adds an apostrophe. Preflop shows non-fold actions (the hero's fold ends the list);
  postflop shows every action up to the hero's fold. At most three tokens per street, then a
  `+N` that expands the street. Tokens are coloured by the actor's position; the hero's are
  underlined.

---

## 7. Money

### 7.1 Investment and blind posts

A player's investment = antes + every blind posted + every chip put in by an action (the call
amount, the bet, or the raise increment = raise-to − what he already had in on the street).
Uncalled money is included here and given back as the returned bet (7.3).

GGPoker blind lines:

| Line | Meaning |
|---|---|
| first "posts small blind" | the regular small blind (live) |
| a later "posts small blind", "posts missed blind" | a dead small blind of the table's small blind |
| first "posts big blind" | the regular big blind (live) |
| a later "posts big blind" | an out-of-turn live big blind |
| "posts small & big blinds $a" | a live big blind of a − SB plus a dead small blind |
| "straddle $X" / "posts straddle $X" | a live straddle; $X is the player's total for the round |
| "posts the ante" | dead money |

Dead money (antes, dead blinds) is in the pot but not part of the player's street bet; live
blinds are.

### 7.2 Pots

Pots are rebuilt from the actions; the site's pot lines are ignored.

- Pot 1 starts with antes, dead blinds and the **Cash Drop** (which has no investor).
- At the end of each street the street bets are cut into layers at each all-in level; every
  layer's investors are all who put chips in it (folded players included), and its contenders
  are those who have not folded. The first layer of a street merges into the last pot, unless a
  player who was already all-in is one of that pot's contenders; further layers are new side
  pots. What only one player put in is not in any pot (the returned bet).

### 7.3 Returned bet and collected amounts

- Returned bet = the player's last-street bet minus the largest bet of anyone else (when
  positive), computed from the actions. The site's "Uncalled bet" amount is not used for money.
- Collected (GGPoker) = the sum of the body lines "collected $X from pot" (all boards); the
  summary's amounts are not used.
- Two checks against the summary's total pot and rake + jackpot can change collected amounts:
  - on rooms where the collected amount may already contain the uncalled bet (GGPoker, 888,
    iPoker, WPN, Winamax), when the totals show that it does, the uncalled part is taken out of
    that player's collected amount so it is not counted twice;
  - when the collected amounts exceed the summary's total pot by at most one cent per board, the
    excess is taken from the first collecting player in seat order.

### 7.4 Winnings

```
won = collected + returned bet − investment
```

- The **Cash Drop** is in pot 1, so whoever collects it has it in his winnings (a walk with a
  $1 Cash Drop wins the big blind +$1.00).
- Run it twice / three times: the collected amounts of every board are summed.
- Split pots: each player's own collected amount.
- **EV cash-out** (GGPoker): a player is a cash-out player when he received a cash-out or
  insurance payment, or paid cash-out risk (then the amount is his collected amount minus the
  risk, even with a risk of $0). "Chooses to EV Cashout" alone does not make him one. For a
  cash-out player, `won = cash-out amount + returned bet − investment`; his collected amount
  still counts for the pots after rake.
- Reports round each hand's winnings to cents (half to even) before summing.

### 7.5 Rake

- Rake is **everything the site kept** (rake, jackpot and other fees), computed per pot:
  `pot rake = pot before rake − what was collected from it` (0 when negative).
- Each player's collected total is split over the pots he won. With side pots, the before-rake
  winners come from the hands at showdown (GGPoker hands where the winner shows no cards are
  matched by amounts); a player who won several pots spreads his collected amount over them in
  proportion to his before-rake winnings, rounding each pot's share to cents.
- A player pays each pot's rake in proportion to what he collected from it:
  `pot rake × his collected / pot after rake`, rounded by first rounding to 7 decimals,
  truncating to 4 decimals and then rounding to cents half to even. A player who collected the
  whole pot pays its whole rake. Because every share is rounded, the players' rake can add up
  to a cent more than the pot's.
- A cash-out player pays `pot rake × (cash-out amount / pots after rake he contests)` per pot,
  rounded to 4 decimals. When he lost the run-out, the real winner also pays the full pot rake
  through the normal rule.
- Stored rake values go through a half-precision float and are rounded to cents on read, as
  Hand2Note's report store does (exact up to $16.00).
- A pot that nobody collected from is an error unless a cash-out player contests it (then its
  rake is 0). A pot paying out more than it holds makes the hand one Hand2Note refuses (2.1).
- Without a cash-out, the players' winnings add up to minus the total rake.

### 7.6 All-in EV

All-in EV adjusted winnings (`won_ev`), as Hand2Note computes them:

- **When**: only when cards were dealt after the last action (an all-in run-out), or someone
  still in the hand could not act on the river because he was already all-in. A river all-in
  and call is not EV-adjusted. When any all-in player who has not folded, or any contender of
  any pot, has unknown cards, nobody gets EV.
- **Per pot** (pots after rake, section 7.5): contenders = the pot's players who had not folded
  by the end of the hand (a player who folds after the all-in leaves his chips as dead money).
  The equity street is the earliest street where a contender went all-in.
  `EV(pot) = equity × pot after rake − what the player put in that pot`.
  - One pot: computed when it has two or more contenders and the all-in came before the river.
  - Two or more pots: every pot is computed. A pot with one contender, or decided on the river,
    uses the actual showdown share (1.0 for a lone contender, split on ties, averaged over
    boards). Only contenders with a share above 0 get an entry for such a pot, so a player who
    loses it gets nothing from it and his chips in it are left out.
  - With several boards, equity is computed once on the board shared up to the all-in.
  - Cash Drop is in pot 1, so its contenders get their equity share of it.
  - In hands with a cash-out player, the board is cut at the earliest all-in street of the
    cash-out players.
- **Equity**: preflop heads-up is exact (full enumeration, ties count half). Preflop with three
  or more contenders Hand2Note uses a random 20,000-board sample, so its own value changes from
  run to run; OHM uses a reproducible 100,000-board sample. Flop and turn are enumerated exactly.
- **Result**: S = the sum of the player's pot EVs. A player with at least one pot entry gets
  `won_ev = won rounded to cents − (won − S)`, i.e. S; a player without entries keeps
  `won_ev = won`. A cash-out player always gets S, which is 0 when the hand has no EV.

### 7.7 bb/100 and the hand count

- Hand count = the hands in section 2.1.
- bb/100 = `sum(won rounded to cents / big blind) / hands * 100`, with the big blind of
  section 2.2. Hand2Note sums in single precision; the difference is invisible at the displayed
  precision, so OHM sums in double.

---

## 8. Worked examples

6-max, blinds 0.5/1 bb, 100 bb stacks unless stated; unmentioned seats fold.
(`backend/tests/test_h2n_matcher.py`, `test_stats_engine_h2n.py` and `test_general_api.py`
implement these.)

1. **Squeeze.** UTG raises 2.5, MP calls, hero CO raises to 11, all fold. Hero: 3-Bet Total and
   Squeeze case; 3-Bet CO, 3-Bet IP/OOP and Call Open Raise nothing (the call breaks the rows).
   UTG: no Fold to 3Bet or 4-Bet opportunity. MP: Call Open Raise case.
2. **3-bet called before the opener acts.** UTG raises, hero CO 3-bets, BTN calls, UTG folds.
   UTG: no Fold to 3Bet (BTN's call sits in between).
3. **4-bet all-in leaves no 5-bet.** Hero CO opens, BTN 3-bets to 8, hero shoves 100, BTN folds.
   BTN: Fold to 4-Bet case, Call 4-Bet opportunity, 5-Bet nothing. Hero: 4-Bet case, 4-Bet-Fold
   nothing. If hero 4-bets to 20 and BTN shoves, BTN has a 5-Bet case and hero a 4-Bet-Fold
   case when he folds.
4. **Heads-up button steal.** Hero is the button (posts the small blind) and raises; BB folds.
   Hero sits in the SB column: Steal Total, Steal SB and Open Raise SB cases, nothing in BTN.
   BB: vs. Steal BB Fold case. If the hero completes instead, it is not a Limp, but it can be a
   Limp-Fold case.
5. **Fold to c-bet amount filter.** CO opens 2, hero BB calls (+1), checks and folds to a flop
   bet. Fold to CBet Flop nothing (increment 1 < 2); Raised Pot Call and Raise opportunities;
   Donk Flop nothing. With a 3 bb open (+2) Fold to CBet Flop is a case.
6. **Multiway middle seat.** Hero UTG opens, CO and BB call; flop BB checks, hero checks, CO
   checks. Hero: Missed CBet case, but neither IP nor OOP (between BB and CO). CO: Bet In
   Position opportunity. BB: no N rows (CO's call sits between the raise and BB's call).
7. **Undefined 3-bet position.** UTG limps, SB raises to 4, hero BB re-raises to 12. Hero: 3-Bet
   Total, 3-Bet BB and 3-Bet IP BB cases; neither the IP nor the OOP Total (UTG acts after the
   BB postflop, SB before). SB: Open Raise case (iso-raise).
8. **Limp vs. complete.** BTN limps, hero SB completes, BB raises to 4, BTN folds, hero folds.
   Hero: no Limp; Limp-Fold case. BTN: Limp case; no Limp-Fold (the hero's call sits between).
9. **C-bet in a 3-bet pot.** UTG opens, hero BTN 3-bets to 8, UTG calls; UTG checks, hero bets,
   UTG folds. Hero: no CBet Flop (his raise was not the first). UTG: vs. CBet 3-Bet Pot Fold and
   Fold to CBet Flop cases.
10. **Delayed barrels.** Hero BTN opens, BB calls; flop checked through; turn BB checks, hero
    bets, BB calls; river BB checks, hero bets, BB folds. Hero: no CBet Turn/River; Missed CBet
    and Missed CBet IP cases. BB: Bet Out of Position Turn and Check-Fold opportunities.
11. **Check-Fold has no position flag.** CO opens, hero BTN calls; flop checked through; turn
    CO bets, hero folds. Hero: Check-Fold case and Check | Fold case.
12. **Donk vs. in-position stab.** CO opens 3, hero BTN calls; CO checks, hero bets. Hero: no
    Donk Flop (in position), Bet In Position case. From the BB (+2) leading first: Donk Flop case.
13. **Call 4-Bet counts squeezes.** UTG opens, MP calls, hero CO 3-bets, UTG 4-bets, MP folds,
    hero calls. Hero: Call 4-Bet case; Fold to 4-Bet and 5-Bet nothing.
14. **Effective raise typing.** Hero UTG opens 2.5, CO shoves 6 bb total, hero calls. CO's shove
    is a raise; hero: Fold to 3Bet opportunity, no 4-Bet opportunity (no effective raise left).
15. **VPIP vs. PFR opportunity.** Hero BB, SB shoves covering him, hero calls: VPIP case, no PFR
    opportunity. Hero BB checks behind limpers: VPIP and PFR opportunities, no case.
16. **Preflop all-in showdown.** Hero shoves preflop, is called and wins: not in the Went to
    Showdown or Won When Saw Flop base; Won at Showdown base and case.
17. **4-Bet Range.** Open Raise 26 % and 4-Bet 18 % → 4-Bet Range `4.7`.

---

## 9. Parity with Hand2Note

OHM was compared with Hand2Note 4.1's results on the
maintainer's database of **75,865 GGPoker Rush & Cash hands**:

- Hand2Note refuses 16 hands (corrupted amounts); OHM flags the same 16 and leaves them out.
- On the remaining **75,849 hands**, all **102 of 102** General-screen values are identical:
  displayed text, sample, case and opportunity counts, the per-hand case/opportunity state of
  every action cell, and all 20 inputs of the expression cells.
- Per hand, the position column, went to showdown, winner flag, hand value per street,
  winnings, winnings in bb and rake match on every hand. The popup's measured action and next
  decision matched on 97,502 hits over 84 cells.
- All-in EV differs by more than $0.01 on **5 hands**, all three-way preflop all-ins. Hand2Note
  estimates three-way preflop equity from a random sample, so its own value changes between runs
  (a standard deviation of $0.04-$0.10 per hand), and which hands cross the $0.01 tolerance
  changes from run to run. OHM stays within that noise
  (`backend/tests/test_h2n_parity_r4.py`).

Regression fixtures from the parity rounds are in `backend/tests/fixtures/ggpoker/h2n_parity_r*.txt`
with tests `backend/tests/test_h2n_parity_r*.py`.
