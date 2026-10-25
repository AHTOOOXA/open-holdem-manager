# 01 — Reports: Stats tab, lower split tabs, chain resolution + cache

Scope: `POST /api/reports/spot`, `POST /api/reports/split` (results, positions, next_actions,
faced_next, bet_sizing), the shared `app.reports.chain.resolve()` with its LRU, and the
frontend that fires them (`ReportsDashboard`, `ReportPageView`, `StatsTab`, `SplitReport`).
Graph / Range / Hand Strength tabs are report 02; hand lists are report 03. Both of those
consume the same `resolve()`, so findings F1, F3 and F6 also apply to them.

## 1. Summary — do these first

| # | Change | Gain at 214k hands | Effort | Parity risk |
|---|---|---|---|---|
| F1 | Plain chains (no spot step, incl. the empty chain of page 0) stop materialising one `HandRec` per hand: Stats / plain splits / range / strength become SQL `GROUP BY`, hands list / graph get a SQL predicate in place of an id list | cold page 0: **~2.8 s → ~0.05 s** CPU; **−200 MB** per cached plain resolution | M (2–3 d) | low (money sums: last-ulp float differences only) |
| F2 | Cache `spot()` and plain split results on the `Resolution` (the action tables already are) | every warm Stats / Results / Positions request: **0.45–0.68 s → <1 ms** | XS (1 h) | none |
| F3 | Don't keep every `h2n_seq` blob on a plain resolution after Next Actions | **−116 MB** pinned in the cache (not counted by the LRU bound) | XS | none |
| F4 | Cast DECIMAL columns to DOUBLE in the resolve SELECT (no Python `Decimal` per value) | resolve SQL fetch **1.9 s → 0.4–0.6 s** (all chains) | XS | low (see F4) |
| F5 | Decode each hand's sequence once per resolution: build the Next / Faced tables in the `_compute` loop (spot chains) | P01 page: Stats tab +0.95 s → ~+0.3 s, Next Actions 0.7 s → 0 | S | none (same evaluators, same order) |

F6 (header resolution) is also a one-hour fix worth doing with F2/F3.

## 2. Baseline

Measured on the shared 20k fixture (`/tmp/ohm-perf/01`, hero "Hero", 19,994 H2N-valid hero
hands) through `TestClient`, and on a read-only copy of the user's DB (214,246 hands, 214,188
hero rows, 1,286,048 `hand_players` rows) by calling the backend functions directly. The
machine was swapping; CPU time is the more reliable number. Scripts: `/tmp/ohm-perf/01/*.py`.

### Endpoints, 20k hands (TestClient, wall ≈ CPU)

| Chain | Request | cold | warm (same request again) |
|---|---|---|---|
| `[]` | spot | 240 ms | **46 ms** (re-aggregates) |
| `[]` | split results / positions | 70 / 66 ms | **70 / 72 ms** (not cached) |
| `[]` | split next_actions | **458 ms** | 3 ms |
| `[]` | hands list (`GET /api/hands?chain=[]`, warm resolution) | 68 ms | |
| `[row P01]` | spot | 533 ms (402 CPU) | 15 ms |
| `[row P01]` | split next_actions / bet_sizing | 65 / 212 ms | 4 / 3 ms |
| `[row C01]` | spot | 57 ms | 4 ms |

Payloads are small (1–6 KB for spot / split); response size is not an issue in this area.

### Resolve pieces at 214k hands (real DB, read-only)

| Step | Wall | CPU | Note |
|---|---|---|---|
| `data_version` (3 aggregates) | 1 ms | 2 ms | not a problem |
| `get_app_settings`, `target_player` | <1 ms | | |
| `total_hands` COUNT | 10 ms | 28 ms | |
| resolve SELECT `fetchall` (26 cols, chain `[]`) | 1,231–1,891 ms | 1,300–2,481 ms | Decimal objects; RSS +326 MB for the tuples |
| `_rec()` × 214,188 | 894 ms | 869 ms | RSS +145 MB |
| **`_compute([])` total** | **2,305 ms** | **2,326 ms** | |
| `views.spot` on the cached resolution | 452 ms | 450 ms | Python loop over 214k `HandRec` |
| `plain_split` positions / results | 664 / 679 ms | | Python loop, recomputed per request |
| same numbers as SQL `SUM(...)` / `GROUP BY h2n_pos` (prototype) | **25 / 22 ms** | 66 / 61 ms | |
| split next_actions, chain `[]` | **4,973 ms** | **6,269 ms** | decodes all 214k sequences, keeps 116 MB of blobs |
| `_compute([row P01])` (118,486 opps, 34,702 cases) | 4,218 ms | 6,500 ms | |
| + spot() on it (builds the Faced table) | 945 ms | | 2nd decode of 34.7k cases |
| + split next_actions / bet_sizing | 715 / 2,143 ms | | 3rd / 4th decode |
| `_compute([P01, faced villain_3bet])` (child page) | 989 ms | 1,400 ms | re-decodes hands its parent already decoded |
| filter 214k hands by `IN (SELECT UNNEST(?))` of the resolved ids | 145 ms | 175 ms | vs 12 ms for the equivalent SQL predicate |

### Memory (tracemalloc, 20k)

- Cached plain resolution: **939 B per hand** (`HandRec` 264 B + 8 floats 192 B + 5
  non-interned low-cardinality strings ~220 B (stakes, mode, pos, card1, card2) + hid 53 B +
  table 50 B + datetime 48 B + hv tuple 64 B). 214k hands → **~200 MB** for the empty chain
  alone; transient peak during `_compute` ~470 MB (row tuples plus records).
- Blobs kept on the resolution: 541 B average per hand (+648 B/hand with dict overhead).
- A decoded `HandSeq` is **~8.9 KB per hand**, so caching decoded sequences is not an option
  (214k → 1.9 GB).
- LRU `_LRU(32, 600_000)` (`backend/app/reports/chain.py:765`) bounds *records*, not bytes:
  600k records ≈ 560 MB of `HandRec`s, plus blobs and cached tables that the bound ignores.
  This accounts for a large part of the 1.2 GB the lead saw after restart.

### Scaling (estimate, linear in hero hands)

| | 20k | 214k (measured) | 1M (est.) |
|---|---|---|---|
| cold page 0 (resolve + spot) | 0.24 s | 2.8 s | ~13 s |
| page 0 Next Actions tab | 0.46 s | 5.0 s | ~23 s |
| cached plain resolution | 19 MB | 200 MB | ~940 MB (one entry exceeds the 600k cap; `len > 1` keeps it anyway) |

## 3. Findings

### F1 — Plain chains build one Python object per hand only to aggregate them (P0)

- Where: `backend/app/reports/chain.py:693-696` (`_compute`, `if not steps: res.hands = [_rec(r) for r in rows]`),
  consumers `backend/app/reports/views.py:87-115` (spot, plain kind),
  `backend/app/reports/split.py:307-374` (`_group_plain`, `plain_split`), `views.py:224-270`
  (range, strength), `backend/app/api/reports_lite.py:84-98` (`chain_hand_ids` → `.case_ids`).
- What happens: every hand of the chain is fetched (26 columns), converted to a slotted
  `HandRec`, cached, and then every view loops over the list in Python (`Acc.add`, 20+
  attribute updates and 12 `_bit()` calls per hand). For the hands list and the graph the whole
  list is reduced back to an id list and bound into SQL as `IN (SELECT UNNEST(?::VARCHAR[]))`
  (`backend/app/api/hands.py:113-115`, `backend/app/api/reports.py:73-75`).
- Why it's slow: O(n) Python allocation and attribute work per request where DuckDB does
  the same aggregation vectorised. Page 0 always uses a plain chain (the empty one), so this is
  what every user hits first.
- Evidence: 214k: `_compute([])` 2.3 s + `spot` 0.45 s + each plain split 0.67 s, against
  22–25 ms for the same sums as SQL. The id-list filter costs 145 ms against 12 ms for the
  predicate. ~200 MB per cached plain resolution.
- Proposal: give `Resolution` a "plain" mode that holds no per-hand records:
  `where_sql, params = _BASE_WHERE + plain_sql(chain) + _row_bits_sql(chain)`. Then:
  - `spot`/`plain_split`: one `SELECT <group key>, COUNT(*), SUM(won), SUM(won_bb), SUM(ev),
    SUM(rake), SUM(won_bb*won_bb), SUM((h2n_pre_case >> bit) & 1), ...` with the same `Acc` fields,
    then fill an `Acc` from the row and call the existing `plain_values()` (no formula changes).
    `results` groups by `(stakes, game_mode = 'Fast Fold', table_size, bb_amount)`, `stack_sizes`
    by a `CASE` over `STACK_RANGES`, `hour_of_day` by `EXTRACT(hour ...)`.
  - preflop range: `GROUP BY card_class_sql()` (already exists, `chain.py:314`); hand strength:
    `GROUP BY hv_<street>`.
  - `tables` / Sessions recipes: fetch only `(played_at, table_name)` for `time_stats`.
  - `players`: `opponent_recs` joins on `hand_id IN (<hero subquery>)` in place of 5,000-id chunks.
  - `chain_hand_ids`: return a `(sql, params)` subquery for plain chains so the hands list
    and the graph filter with a join / `EXISTS` (coordinate with reports 02 and 03).
- Expected gain: cold page 0 at 214k ~2.8 s → ~50 ms CPU; warm views ~20 ms; −200 MB per
  cached plain chain; hands/graph −130 ms of id binding.
- Effort: M (2–3 days including tests). Spot chains keep the current path.
- Parity risk: low. Counts and bit sums are exact integers either way. Money sums change from
  sequential Python float addition to an exact DECIMAL `SUM` converted once. The result can
  differ in the last ulp (≈1e-12), never at display precision. Dispersion uses the same
  `_dispersion()` formula on the same sums. Run `test_reports_lite`, `test_stat_parity` and
  `test_h2n_parity_r1..r4`. If a test compares raw floats exactly, sum in SQL as DOUBLE in
  hand-id order, or compare with a tolerance.

### F2 — Warm requests recompute `spot()` and plain splits every time (P0 quick win)

- Where: `backend/app/reports/views.py:87-159` (`spot`), `backend/app/reports/split.py:331-374`
  (`plain_split`), `split.py:380-399` (`tables_split`). Only `action_table`, `sizing_table` and
  `players_table` are memoised in `res.tables`.
- What happens: the resolution is cached, but each `/spot` and `/split?type=results|positions|...`
  call loops over every case again. The frontend refetches these after `staleTime` (2 min,
  `frontend/src/lib/query-client.ts:6`) on every remount (tab switch, page re-open), and on Refresh.
- Evidence: 20k: spot 46 ms warm, results/positions 70 ms warm vs 2–3 ms for cached
  next/faced; 214k: 452 / 664 / 679 ms per warm request.
- Proposal: memoise the finished response dict under `("spot",)`, `("split", typ)` in
  `res.tables` (same pattern and lock as `action_table`). The resolution key already encodes
  chain + data version + day start.
- Gain: warm Stats / Results / Positions at 214k: ~0.5–0.7 s → <1 ms each. Effort XS. Parity: none.
  F1 makes this mostly moot for plain chains but it still helps spot chains (91 ms warm spot at P01).

### F3 — A plain resolution pins all `h2n_seq` blobs after one Next Actions request (P1)

- Where: `backend/app/reports/split.py:441-447` (`_source`: `if not res.blobs: res.blobs = dict(fetch_seqs(...))`).
- What happens: for a plain chain `res.blobs` is empty, so the first Next Actions table copies
  every case's blob onto the cached resolution. The table itself is then cached, faced/sizing
  are empty for the hand-start context (`spots.faced_candidates` returns `[]`, `sizing_table`
  needs `has_spot`), so nothing ever reads those blobs again.
- Evidence: 214k: 214,188 blobs = 116 MB raw (~140 MB with dict/bytes overhead) kept until
  LRU eviction. The LRU bound (`chain.py:755-758`) does not count them.
- Proposal: when `not res.has_spot`, keep the fetched blobs in a local `SeqSource` only.
- Gain: −116…140 MB resident after page 0's Next Actions. Effort XS. Parity: none.

### F4 — DECIMAL columns are fetched as Python `Decimal`, then `float()`-ed (P1)

- Where: `backend/app/reports/chain.py:571-580` (`_COLS`), `_rec` at `chain.py:589-598`;
  same columns in `opponent_recs` (`chain.py:601-616`). `won`, `won_bb`, `rake`, `rake_bb`,
  `all_in_ev_bb`, `stack_bb`, `bb_amount` are `DECIMAL(18,3)`.
- What happens: DuckDB creates ~1.7M `Decimal` objects for 214k rows. `_rec` converts each one to float.
- Evidence: 214k: `fetchall` 1,891 ms wall / 2,481 ms CPU with DECIMALs vs 421–608 ms with
  `CAST(... AS DOUBLE)`; `fetch_arrow_table` of the same 26 columns takes 79 ms.
- Proposal: `CAST(COALESCE(hp.won, 0) AS DOUBLE)` etc. in `_COLS`. For the EV money column, cast
  the DECIMAL product (`CAST(COALESCE(all_in_ev_bb, won_bb, 0) * h.bb_amount AS DOUBLE)`), not
  the factors, so the value is still the exact product rounded once.
- Gain: −1.3…1.9 s CPU per cold resolve at 214k (every chain kind, also the 118k-row P01 resolve).
  Effort XS.
- Parity risk: very low. A check on all 214,188 rows of the real DB, matched by hand id,
  found identical floats in every cast column (won, won_bb, EV bb, EV money product, rake,
  bb_amount, rake_bb). Fetch time there was 1,728 ms (DECIMAL) vs 516 ms (DOUBLE). Still run
  the parity tests.

### F5 — Each hand's sequence is decoded up to four times per page (P1)

- Where: `chain.py:698-726` (`_compute` decodes every opportunity hand), `split.py:450-485`
  (`action_table`, decodes every case again, once per table "next" / "faced"),
  `split.py:494-522` (`sizing_table`, decodes every hand again), `chain.py:658-666`
  (`SeqSource.get` decodes on every call and caches nothing).
- What happens: on a hero-action page (e.g. `row P01`) the Stats tab needs `_compute`
  plus the Faced table (`views.py:141-148`), the Next Actions tab adds a Next table and Bet
  Sizing a fourth pass. A child page (`[P01, faced villain_3bet]`) runs the whole chain again
  from SQL. It re-decodes and re-evaluates step 1 on hands its parent already resolved.
- Evidence: decode ≈ 20–60 µs per hand (≈45% of `action_table` time in cProfile). 214k / P01:
  `_compute` 4.2 s, then spot +0.95 s, next_actions +0.7 s, bet_sizing +2.1 s; child page
  +1.0 s.
- Proposal:
  1. In `_compute`'s loop the sequence is already decoded. For case hands, also run the
     `next_candidates` / `faced_candidates` evaluators there and fill the two `action_table`
     dicts (same `ev()` calls, same order, so the same `Acc`s). Store them in `res.tables`.
     Keep Bet Sizing lazy (its `_size_hits` work is ~35% of its pass), or fold it in too if
     Bet Sizing is a common tab.
  2. Child pages: if `resolve(chain[:-1])` is cached and the last step is a spot step, iterate
     only the parent's case hands. Continue `evaluate_spot` from the parent's
     `(code, hit)` (stored on `HandRec`), so the earlier steps are not run again. The result is
     the same because `evaluate_spot` is a left fold over the steps.
- Gain: P01 page at 214k: Stats tab ~5.2 s → ~4.5 s, Next Actions 0.7 s → 0; child pages
  skip the SQL + step-1 evaluation (estimate 30–50% of their time). Effort S (1) / M (2).
- Parity risk: none for (1), same evaluator calls. (2) needs a test comparing
  incremental vs full resolution on the parity fixtures.

### F6 — The page-0 header resolves the empty chain only to print "N hands" (P1)

- Where: `frontend/src/components/reports/ReportsDashboard.tsx:98-102,195-198`
  (`reportQuery(dashboard, [])` → `getSpot`).
- What happens: with no own filters on page 0 the header and the Stats tab share one query
  key, so they fire one request. As soon as page 0 has a filter chip (stakes, date, …), or a
  stored chain is restored with one, the header fires its own `chain=[]` spot. That is a full
  214k-hand resolution (2.8 s, 200 MB in the LRU) for one number.
- Proposal: add `total_hands` (already computed as `Resolution.total_hands`, `chain.py:687-690`,
  the same `_BASE_WHERE` count) to the spot response and read it from page 0's own Stats
  query. Alternatively add a `COUNT(*)` endpoint (10 ms at 214k).
- Gain: −2.8 s CPU and −200 MB whenever page 0 is filtered. Effort XS (backend 1 line, frontend 5).
  Parity: none (same count).

### F7 — Cache is bounded by record count; records are fat (P1)

- Where: `chain.py:512-545` (`HandRec`), `chain.py:735-765` (`_LRU`).
- What happens: ~939 B per record, of which ~220 B are per-row copies of strings with 2–52
  distinct values (stakes, game mode, position, card1, card2) and 192 B are boxed floats.
  The bound (600k records, `len(self._d) > 1`) ignores blobs (541 B/hand on spot
  resolutions, kept by `chain.py:728`) and derived tables. A single over-budget entry is never
  evicted.
- Evidence: tracemalloc above. At 214k: P01 resolution = 118k records (~110 MB) + 62 MB blobs.
- Proposal: (a) intern the low-cardinality strings in `_rec` (a module-level dict per field)
  and store `hv` as three fields instead of a tuple. That saves ~25%. (b) Budget by estimated
  bytes (`len(hands) * 700 + sum(blob sizes)`), e.g. 300 MB. (c) With F1, plain chains cost
  ~0 bytes, so the budget only covers spot chains.
- Gain: cache RAM ~−25% now, much more with F1; a predictable ceiling. Effort S. Parity: none.

### F8 — Page-0 Next Actions decodes every hand to find hero's first preflop decision (P2)

- Where: `split.py:450-485` with `spots.next_candidates(START)` → `_start_next` /
  `start_family` (`spots.py:196-225`).
- What happens: for the hand-start context, the eight rows (Fold / Call / Raise, vs. Raise,
  Check / Raise in the BB option) only need hero's first preflop action, whether an
  effective raise came before it, and its possible actions. Getting them decodes 214k blobs.
- Evidence: 214k: 4,973 ms wall / 6,269 ms CPU, the slowest single request in this area.
- Proposal: compute these at import (`stat_flags`/`h2n` stage) into one small column, e.g.
  `h2n_start UTINYINT` = family (2 bits) | first effective type (3 bits) | possible mask. The
  table then becomes a SQL `GROUP BY`. Needs a schema column and a `STAT_VERSION` bump
  (one background rebuild). Action Profit needs `committed_bb` at the first preflop action:
  store it, or keep a Python pass only for case hands.
- Gain: 5 s → ~30 ms. Effort M. Parity risk: medium. The encoding must match `start_family` /
  `_possible` exactly; add a test that compares the SQL table with the current Python table
  on the parity fixtures.

### F9 — Concurrency and in-flight dedupe (P3; mostly fine)

- `_inflight` (`chain.py:802-813`) works: 3 parallel cold requests for the same chain → one
  `_compute` (measured: 195 ms total vs 176 ms single). Page 0's spot and hands list share a
  resolution.
- Different chains don't parallelise (GIL): 3 different spot chains took 516 ms total, against
  285 ms for one. The rightmost page of a restored chain waits for all pages to its left.
- During a background rebuild (`chain.py:796-797`) there is neither cache nor dedupe, so every
  request resolves from scratch while the rebuild competes for the GIL.
- `sizing_table` and `players_table` (`split.py:402-420, 494-522`) release `res.lock` while
  they compute, so two racing requests both compute. `action_table` holds it.
- Aborted fetches (tab switch, `signal`) don't stop the sync endpoint. The work is still
  cached, so only chains nobody revisits waste CPU.
- `data_version` (two `MAX`/`COUNT` queries) costs 1 ms at 214k, so per-request version checks
  are not a cost. Every hands-writing path calls `data_generation.bump()` (import, clear, restore,
  workspace delete, rebuild), so the SQL part is a safety net and can stay.
- Proposal: hold `res.lock` around the compute in `sizing_table`/`players_table` (XS). During
  a rebuild, dedupe in-flight work even without caching (XS).

### F10 — Frontend request pattern (P2)

- Fresh page 0 (Stats + Hands): `heroes` + 1 × `/spot` (header and Stats tab share the key)
  + 1 × `/api/hands?chain=[]` → **1 resolution**. Good.
- Each lower tab switch: 1 `/split` per tab (SplitReport keyed by tab,
  `LowerReports.tsx:143-149`). Switching back within 2 min hits the react-query cache. After
  that, the refetch recomputes on the server (F2).
- Restored chain with N pages: `PageChain` mounts every page
  (`frontend/src/components/page-chain/PageChain.tsx:191-216`), each firing Stats + its
  lower tab. That makes 1 + 2N requests and up to N + 1 distinct resolutions on load (the extra
  one is F6), computed one after another because of the GIL.
- Proposal: defer off-screen pages' queries (`enabled` until the page is visible via
  IntersectionObserver), or fetch from right to left so the page the user looks at comes first.
  Effort S. Parity: none.

## 4. Quick wins vs. larger refactors

Quick wins (≤ 1 day total, no number changes): F2 (memoise spot / plain splits), F3 (don't
pin blobs), F6 (`total_hands` in the spot response), F4 (DOUBLE casts, run parity tests), F9
locks, F7(a) string interning.

Larger: F1 (SQL aggregation for plain chains + predicate-based `chain_hand_ids`, shared with
reports 02/03), F5 (single decode pass; incremental child resolution), F8 (import-time
hand-start column + `STAT_VERSION` bump), F10 (deferred off-screen pages), F7(b) byte-budget cache.

## 5. Open questions / not measured

- Wall times are inflated by swap (22 GB swap in use during the runs); CPU times are the
  better guide. The 214k runs were direct function calls on a read-only copy, not HTTP.
- Not measured: Sessions recipes / `tables` / `players` splits at 214k (report 05 covers
  Sessions), and `faced_next` on a villain-action page.
- Not measured: how often users open deep chains or restore multi-page chains. F5(2) and F10
  matter only if they do.
- F1's float-sum difference: checked by reasoning only; confirm against
  `test_reports_lite`, `test_stat_parity`, `test_h2n_parity_r1..r4`.
