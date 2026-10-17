# H2N layer contract

The General screen (H2N 4.1 "General" copy) reads only the columns below. The old OHM flag
columns keep their meaning; nothing here changes them. Behaviour is described in
`docs/specs/H2N-COMPATIBLE-STATS.md`; this file only fixes names, types and layout.

## Columns on `hand_players`

Defined once in `app/h2n/columns.py` (`H2N_COLUMNS`). `db.py` adds them with
`_add_column_if_missing` on startup; `import_hands._STAT_FLAG_KEYS` writes them from each
player's flag dict. Adding a column = one line in `H2N_COLUMNS` + a `STAT_VERSION` bump.

| Column | Type | Meaning | Stub value |
|---|---|---|---|
| `h2n_pos` | VARCHAR | H2N column group: `EP` (EP + UTG1-4), `MP` (exactly one seat, the HJ), `CO`, `BTN`, `SB` (SB + heads-up button), `BB` (BB + heads-up BB). From seat order, independent of OHM's `position` | NULL |
| `h2n_pre_opp` / `h2n_pre_case` | UBIGINT | Preflop rows: bit k set = row k was an opportunity / a case | 0 |
| `h2n_post_opp` / `h2n_post_case` | UBIGINT | Postflop rows (C, M, N, E), same idea | 0 |
| `is_winner` | BOOLEAN | H2N "is winner": with a showdown, among the showdown winners (hand ranking when cards are known, else whoever collected; split = win); without a showdown, the player did not fold | FALSE |
| `hv_flop`, `hv_turn`, `hv_river` | SMALLINT | Hand-value category index inside that street's category list (flop 14, turn 14, river 11). `-1` = Other. NULL = cards unknown or street not dealt | NULL |
| `h2n_valid` | BOOLEAN | FALSE = H2N would refuse to import the hand (`app.h2n.hand_rejection`, H2N-COMPATIBLE-STATS.md 2.1: raise not above the bet, impossible call amount, negative pot rake, unknown GG action line). Same value for every player of the hand. Readers of General numbers filter `COALESCE(h2n_valid, TRUE)` | TRUE |
| `h2n_seq` | BLOB | Compact copy of the hand's annotated action sequence (`app.h2n.seqcodec`, versioned format), for the stat popup. **One row per hand** carries it: the first player clockwise from the button whose hole cards are known (the hero in his own histories), else the first player; NULL elsewhere. Readers take it from any row of the hand (`h2n_seq IS NOT NULL`) and fall back to re-parsing `hands.raw_text` when it is missing or has another format version | NULL |

Rules every writer must keep:
- A case bit implies the opp bit for the same row (`case & ~opp == 0`), E rows included.
- Masks only use bits 0..62. Bit 63 stays clear so values fit int64 on the PyArrow insert path.
- Hero position filters are **not** in the bits. Apply them in SQL with
  `h2n_pos IN (...)`. Villain position conditions inside a row are part of the row.
- H2N "won at showdown" = `is_winner AND went_to_showdown`. Do not use OHM's
  `won_at_showdown` (collected anything) for General cells.

## Bit layout

`app/h2n/rows.py` holds the table: `ROWS[key] -> RowSlot(key, mask, bit, street, notation,
hits_only)`. The bit index is the row's position in its list. Never renumber; append only.

- Preflop mask, bits 0-32: `V01 V02 V03`, `P01`..`P24`, `P25F P25C P25R`, `P26F P26C P26R`.
- Postflop mask, bits 0-24: `C01`..`C14`, `M01`..`M05`, `N01`..`N06`.
- Postflop mask, bits 25-39: per-street single-action rows `E_{FLOP,TURN,RIVER}_{B,R,C,BR,ANY}`
  (per hand, effective action types; `RowSlot.hits_only`). Case = the player made such an
  action; opp = H2N's single-action rule (bet: a bet / check / fold with a bet possible; raise:
  a raise / call / fold with a raise possible; call: any call / raise / fold; ANY: opp = case).
  The Aggression sample is the max of the B / R / C opportunity counts (parity round 1).
- `RowSlot.street` = the street whose decision is measured (the last street of the row); the
  popup uses it to pick `hv_*` and the board.
- `notation` is our shorthand of the row from the spec; the matcher turns it into data.

SQL helpers: `sql_opp(key, alias="hp")` and `sql_case(key, alias="hp")` return a 0/1 INTEGER
expression, e.g. `SUM(((hp.h2n_pre_case >> 3) & 1)::INTEGER)`. Python helpers: `has_bit`,
`set_bits`.

## Hook

`app.stat_flags.compute_stat_flags(parsed)` ends with one call:

```python
apply_h2n(parsed, player_stats)   # from app.h2n, mutates player_stats in place
```

`apply_h2n` sets **every** column in `H2N_COLUMNS` for **every** player in
`player_stats` (the insert path reads them by key). It writes `H2N_DEFAULTS` first, then the
computed values; if the computation raises, the hand keeps the defaults and the error is logged
(an import never loses a hand because of this layer). It must not import `app.stat_flags` or
`app.db` (circular import: `db.py` imports `app.h2n.columns`).

`hv_*` come from `app.hand_value.apply_hand_values(parsed, player_stats)`, which
`apply_h2n` calls when that function exists.

Rebuild: startup rebuilds every hand from `raw_text` when `STAT_VERSION` changes, which reruns
the hook, so changing the matcher only needs a version bump.

## Modules

| Module | What |
|---|---|
| `sequence.py` | `build_sequence(parsed) -> HandSeq`: voluntary actions per street with effective type, flags (first raise, opening, first/last of player, limp, 3-bet, tri-state IP/OOP to players left and to VPIP'd players), what was possible (raise, bet, check, call, limp, first raise, opening, 3-bet), amounts (`amt_bb` = call increment / capped bet / capped raise-to), pot before, `h2n_pos`. `h2n_positions(parsed)` |
| `matcher.py` | Row DSL compiler and the matching / opportunity rules (H2N-COMPATIBLE-STATS.md 2.7-2.8). `evaluate(def, seq, player) -> RowResult(case, opp, hit)` |
| `definitions.py` | `DEFINITIONS[row key]` in the DSL, one per `ROWS` key (E rows too); `COMPILED` |
| `results.py` | `winners(parsed)`: H2N "is winner" (H2N-COMPATIBLE-STATS.md section 5: best known hand among non-folded players on the full board, union over run-it-twice boards; collectors if no cards are known or the board is incomplete; no showdown = whoever did not fold) |
| `replay.py` | Popup support: `replay(raw_text, site_id) -> HandSeq` (site parser + `build_sequence`), `match_row(seq, key, username) -> RowResult` with `hit = (street, action index)` of the measured action (case) or of the player's decision (opportunity only); with OR-ed rows the hit is the earliest action any row hits (H2N-COMPATIBLE-STATS.md 2.9) |
| `__init__.py` | `apply_h2n`, `compute_h2n(parsed)`; per-shape memo of preflop results (see below) |
| `seqcodec.py` | `encode_sequence(seq) -> bytes`, `decode_sequence(blob)` (HandSeq, or None when not decodable) (the `h2n_seq` column; decode equals the built sequence, `reject` excluded) |

Parity round 1 (checked against Hand2Note's results) settled:
- Positions use the **first** SB / BB post (`sequence.regular_blinds`); an out-of-turn BB keeps
  the position of his seat. GG `name: straddle $X` lines (dropped by the parser) are live posts
  whose amount is the player's total; "posts missed blind" is dead money.
- A bound villain (`V1`) is checked after the scan takes the next fitting action: another
  villain's fitting action ends the try instead of being skipped (`matcher._scan`).

Decisions on the spec's UNVERIFIED items (change here and bump `STAT_VERSION` if a parity run
disagrees):
- A raw raise is an effective raise when the actor's effective chips behind exceed the amount to
  call (so an incomplete all-in raise that adds chips beyond the call **is** a raise); otherwise
  call, or check with nothing to call.
- Amount filters are inclusive with a 1e-6 bb tolerance (`matcher.AMOUNT_EPS`).
- Seats with no action, post or known cards are treated as sitting out: no sequence, not used
  for positions, stacks or relative position.
- Players all-in from their posts have no preflop sequence; a player all-in before a street has
  no sequence on it (no rows can match there).

Performance (import; results are identical to the plain path, checked on 95k real hands):
- Preflop results depend only on the preflop action list (actors, effective types, the flag bits
  the definitions test, and on which side of each amount filter an amount falls), the column
  groups and who has a preflop sequence; `compute_h2n` memoises them per such shape (`_SHAPES`,
  bounded), together with the postflop rows whose preflop part matches for each player and the
  villain bindings it leaves (`_post_candidates`; postflop rows sharing a preflop part are matched
  once). About 900 shapes per 20k 6-max hands. `compute_h2n(parsed, use_cache=False)` gives the
  same result without the memo (tested).
- GG main blind: when every small / big blind post before the deal is the header's amount, the
  header's big blind is the answer (`sequence._main_blind`); otherwise `money.h2n_main_blind`.
- Hand rejection: a cheap upper bound of what the pots pay out (`_collected_bound`) skips the
  money replay for hands that cannot overpay; the "Bet & Muck" regex only runs when the text has it.

Dead or absent small blind (checked on synthetic hands): with no small-blind poster H2N counts the
positions back from the big blind -- the player right before the big blind is BTN (a seated
non-posting player between the dealer and the big blind is BTN and the dealer becomes CO; with that
seat empty the dealer stays BTN), then CO, MP, EP. Relative positions (IP / OOP to players left or
to VPIP'd players) follow those positions: H2N's button acts last.
