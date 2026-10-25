# 04 — Statistics: dashboards, General screen, stat popup

Scope: `/statistics`. That covers the dashboard tree and header, the GENERAL grid (`GET /api/general`), the Notes tab,
the opponent view, and the stat page opened from a cell: `GET /api/general/cell/{id}/detail`,
`GET /api/general/cell/{id}/hands`, plus the two Reports calls it makes (preflop 13x13 Range and
Next Actions).

All numbers were measured on the 20k fixture (hero "Hero", ws 1, copy in `/tmp/ohm-perf/04`). Where
noted, they were also measured read-only on the 214k-hand DB (`/tmp/ohm-mem/poker.duckdb`, hero id 3796).
Each run held the bench lock. Times are wall / CPU in ms. The machine was swapping, so RSS figures are
noisy. Memory per record was measured with `tracemalloc`. Timings under `tracemalloc` were 10–20x
inflated and are not used.

## 1. Summary

The General grid is cheap. It is one SQL query and one scan: ~35 ms at 20k and ~100 ms of SQL
(~215 ms end to end) at 214k. All of the cost and memory on this screen is in the **stat popup**. It
replays every *opportunity* hand of the cell in Python, keeps the results in a process-global LRU of
300k records, and that LRU is smaller than one big cell at 214k.

Do these first:

1. **Popup LRU: make it fit and make it small** (F1, F2). At 214k, opening VPIP and then PFR fills
   the 300k cache. Reopening VPIP replays 116k hands again (5.0 s). At 1M hands, one VPIP popup
   (~970k opportunities) is bigger than the cache, so it is cold on every open (~35–40 s, estimate). A
   full cache holds **~200–400 MB** that is never freed. Fix: compact `__slots__` records with interned
   keys (~3x less memory), plus a capacity based on the working set rather than a fixed 300k, or a
   persisted record table (F6).
2. **Slim the popup's hand query** (F3). `_query_hands` loads 13 columns and builds a `_Hand` object
   per opportunity: 900 ms of the 1.4 s *warm* VPIP popup at 214k. A query for (id, case) alone takes
   74 ms. Push the summary counts and the strength histogram into SQL. Expected gain: warm popup
   1.4 s → ~0.4 s at 214k.
3. **Postflop popup: decode `h2n_seq` instead of re-parsing `raw_text`** (F4). Every postflop
   opportunity is re-parsed (parse 170 µs + replay 79 µs of ~330 µs/hand). The stored blob decodes in
   39 µs, and the board and hole cards are already in `board_cards`, `card1/card2`, `hv_*` and
   `rit_boards`. Expected gain: ~4x on a cold postflop popup.
4. **Single-query seq fetch** (F5). `_fetch_seqs` sends 42 chunked `IN (UNNEST …)` queries for 208k
   ids: 648 ms wall / 1 961 ms CPU. A join on the same filter takes 172 ms.
5. **Frontend: stop needless popup refetches** (F8). The detail query has `staleTime: 60 s`, while
   the grid has `Infinity`. A tag edit in the hands drawer also invalidates all of `['general']`, which
   refetches the grid and every open detail. A refetch costs 1.4 s warm or 7.7 s cold at 214k.

## 2. Baseline

### Requests on load

When `/statistics` opens with a profile dashboard, it sends:

- `GET /api/statistics/dashboards` (one settings row)
- `GET /api/general`
- `GET /api/heroes`
- `GET /api/reports/filter-options` (5 min stale)
- the day-start setting

The tree, header and grid make no other requests. Changing a filter makes one new `/api/general`
request (the query key is the params; `keepPreviousData`; `staleTime: Infinity`), so switching back
to an earlier filter or dashboard is instant (`DashboardView.tsx:101-108`).

Opening an action cell sends `GET …/detail`. The default tab then sends one more request:
`POST /api/reports/preflop-range` for a preflop stat, or nothing extra for postflop (Range comes from
the detail). Next Actions adds `POST /api/reports/split`, and Hands adds `GET …/hands` pages of 50.

### 20k hands (TestClient, warm process unless "cold")

| Request | wall / CPU ms | payload |
|---|---|---|
| `/api/general` first call (connection open + schema) | 394 / 744 | 17 KB |
| `/api/general` hero, no filter | 38 / 76 | 17 KB |
| `/api/general` stakes / fast-fold / date / chain | 29–40 / 55–77 | 17 KB |
| `/api/general` opponent (73 shared hands, vs-user replay) | 52–59 / 82–97 | 19 KB |
| detail VPIP cold (19 449 opps, seq decode) | 652 / 648 | 3.7 KB |
| detail VPIP warm | 93 / 93 | |
| detail Open Raise cold / warm (11 114 opps) | 328 / 55 | 3.1 KB |
| detail C-Bet Flop cold / warm (941 opps, raw_text re-parse) | 313 / 13 | 28 KB |
| detail Fold to C-Bet Flop cold / warm (220 opps) | 85 / 9 | 20 KB |
| hands page 1 (50 rows, 50 re-parses) | 31–56 | 37–59 KB |
| `POST reports/preflop-range` VPIP / Open Raise (Reports, see 02) | 557 / 283 | 9 KB |
| `POST reports/split` next_actions VPIP | 108 | 7 KB |

The General SQL is ~30 ms of the 38 ms. Python post-processing (`_group_counts`, `_counts_by_ref`)
takes 0.6 ms.

### 214k hands (direct calls on a read-only connection)

| Operation | wall / CPU ms |
|---|---|
| `compute_general` hero, cold / warm | 534 / 2 772 → 213–221 / 246–264 |
| `compute_general` stakes filter / date filter | 101–121 / 60–66 |
| `compute_general` opponent (533 shared hands) | 167–178 |
| aggregate SQL alone (with `hands` join / without) | 100–150 / 44–65 |
| detail VPIP cold (208 232 opps) | **7 760 / 11 033** |
| detail VPIP warm | 1 400 / 1 370 |
| detail PFR cold (208 134 opps; cache now full at 300 000) | 7 672 / 8 798 |
| detail VPIP again after PFR (116 366 re-replayed) | **4 952 / 5 559** |
| hands page 1 VPIP / PFR | 254 / 322 |
| detail C-Bet Flop cold (~10k opps) | not measured (bench lock held by another run); estimate ~3.3–3.5 s from 330 µs/hand |

### Scaling (estimates, linear in the player's hands)

| | 20k | 214k (measured) | 1M (estimate) |
|---|---|---|---|
| General grid | 38 ms | ~215 ms | ~1 s |
| Popup VPIP/PFR cold | 0.65 s | 7.7 s | ~36–40 s, **every time** (opps > LRU capacity) |
| Popup VPIP warm | 93 ms | 1.4 s | never warm |
| Popup C-Bet Flop cold | 0.31 s | ~3.4 s (estimate) | ~16 s |
| LRU retained memory | 13 MB (VPIP) | ~200–300 MB (full) | ~200–400 MB (full, churning) |

### Memory held by Statistics

- `general_popup._RECORDS`: up to 300 000 records. Measured per record: **663–720 B** (preflop) and
  **770–1 330 B** (postflop), key included. Full: ~200–400 MB, for the process lifetime. Nothing
  clears it outside tests (`clear_cache` is only called from tests). Not on DB clear, workspace
  delete or rebuild.
- Transient peak while computing a cold VPIP popup: 33.5 MB at 20k, so ~360 MB at 214k (estimate). The
  observed RSS jump was 200 → 445 MB. Python seldom returns this to the OS.
- The popup's Reports tabs keep a second, separate per-hand cache in `reports/chain.py:765`
  (`_LRU(32, 600_000)`, covered by report 01) for the same hands.
- The General grid keeps nothing on the backend. On the frontend, the TanStack cache holds ~17 KB per
  grid response, ≤28 KB per detail, and ≤60 KB per hands page (gcTime 10 min). This is negligible.

None of this explains an 11 GB process (that is import, report 06). The popup LRU plus the
transient peaks can add 0.5–0.8 GB to a long-running backend at 214k.

## 3. Findings

### F1 — Popup LRU is smaller than one cell's working set at 214k+ (P1)

- **Location:** `backend/app/api/general_popup.py:713` (`_RECORDS = _LRU(300_000)`), `:780-808`.
- **What happens:** records are keyed by (workspace, hand, player, row). One popup inserts one record
  per opportunity hand. VPIP and PFR each have ~208k opportunities at 214k, so two clicks evict most
  of the first cell. Measured: VPIP again after PFR replayed 116 366 hands in 4.95 s. At 1M hands, one
  VPIP popup inserts ~970k records into a 300k LRU and evicts its own earlier records in the same
  request, so the next open is fully cold again. Every open costs ~36–40 s (estimate: 37 µs/hand ×
  970k), plus another 300k evictions.
- **Proposal:** short term, size the capacity in bytes (or in "largest cell × k") and skip caching
  when one cell's opportunity set is larger than the capacity, rather than churning. Long term, F6.
- **Gain:** at 214k, cells you have opened before stay warm (1.4 s, or ~0.4 s with F3, instead of
  5–8 s). At 1M, it avoids pointless churn.
- **Effort:** S. **Parity risk:** none (cache policy only).

### F2 — Popup records are ~0.7–1.3 KB each and are never released (P1, memory)

- **Location:** `general_popup.py:670-679` (`_Rec` frozen dataclass without slots), `:685-713`,
  `:716-718`.
- **What happens:** each record holds:
  - a 4-tuple key whose hand id and username are fresh `str` objects from DuckDB on every row (the
    same "Hero" string is stored 300k times)
  - an `OrderedDict` node
  - a dataclass with a `__dict__`
  - `sizes`, a tuple of `(bucket_id, bool)` tuples
  - `textures` and `cats` tuples

  Measured: 663 B/rec (VPIP) up to 1 330 B/rec (C-Bet Flop). A full cache is ~200–400 MB, and
  `clear_cache()` has no production caller.
- **Proposal:**
  - Use `@dataclass(slots=True)`, or pack a record into a small tuple or int: `sizes` as two bitmasks
    over `_BUCKETS` indexes (cases, opps), `nxt`/`direct` as small ints, textures as a bitmask per
    board.
  - Intern the username and drop it from the key when it equals the cell's player (key = `(ws,
    player_id, hand_id, row)` with `sys.intern(row)`).
  - Call `clear_cache()` on clear-DB, workspace delete and rebuild completion.

  Target: ~200–250 B/rec.
- **Gain:** ~3x less retained memory (300k records: ~250 MB → ~70 MB, estimate). It also lets a larger
  capacity (F1) fit in the same budget.
- **Effort:** S–M. **Parity risk:** low. Encoding only; cover with a test that compares the
  `CellDetail` JSON before and after over the fixture for every action cell.

### F3 — `_query_hands` builds a full Python object per opportunity for the detail view (P1)

- **Location:** `general_popup.py:910-943`, used by `compute_detail` at `:978-991`.
- **What happens:** the detail fetches `h.id, played_at, stakes, site_id, p.username, h2n_pos, case,
  sd, win, hv, won, won_bb, ev` (with a join to `players`) for every opportunity hand. It builds a
  `_Hand` per row, then counts cases, WTSD, W$SD, Won Hand and the strength histogram in Python.
  `played_at/stakes/site/won/ev/username` are only used by the hands list.
- **Evidence (214k, VPIP, 208 232 rows):** `_query_hands` takes 900 ms; `SELECT h.id, case` with the
  same filter takes 74 ms. The warm detail is 1 400 ms, of which ~900 ms is this query (cProfile at
  20k: 70 ms of 105 ms).
- **Proposal:** a detail-only query.
  - Aggregate `COUNT(*), SUM(case), SUM(case*sd), SUM(case*win), SUM(case*sd*win)` and the
    `hv_<street>` histogram in SQL. The General query already does this pattern
    (`general.py:86-109`).
  - Fetch only `(hand_id, case)` for the replay loop. `username` is constant: take it once from
    `players`.
- **Gain:** warm detail at 214k goes from ~1.4 s to ~0.4–0.5 s (estimate). The cold path saves ~0.8 s.
- **Effort:** S. **Parity risk:** low. Same predicates and the same counts; the integer sums are exact.
  Check with `test_stat_parity` and the popup tests.

### F4 — Postflop popups re-parse `raw_text` for every opportunity (P1)

- **Location:** `general_popup.py:852-853` (`else: todo = missing`), `:721-723`, `:726-749`.
- **What happens:** preflop rows decode the stored `h2n_seq` blob. Postflop rows re-parse the hand
  history and rebuild the sequence for every opportunity, because `_compute_record` needs boards
  (`player_boards`) and hole cards (`classify_boards_for_player`).
- **Evidence (per hand CPU, 2 000 hands):** parse 170 µs + replay 79 µs vs `decode_sequence` 39 µs.
  `classify_boards_for_player` takes 12 µs and `player_boards` 1 µs. In the cProfile of a cold C-Bet
  Flop, `_parse` is 494 of 644 ms. Measured cold C-Bet Flop: 313 ms for 941 hands at 20k (~3.4 s
  estimated at 214k).
- **Proposal:** decode `h2n_seq` for postflop rows too. Take boards from `board_cards` (+
  `hands.rit_boards`) and hole cards from `hand_players.card1/card2`, both fetched in the same query.
  For single-board hands, `cats` for the stat street is `hp.hv_<street>` (already stored, the same
  classifier at import), so only RIT hands need `_classify_board`. `_seen_streets` can use
  `seq.fold_street`. Keep the `raw_text` fallback for hands without a blob.
- **Gain:** ~4x on cold postflop popups (estimate: 330 → ~70–80 µs/hand).
- **Effort:** M. **Parity risk:** medium. The record must equal the parse path. Add a test that builds
  records both ways for every postflop action row over the 20k fixture and asserts equality (RIT hands
  included). Then run `test_h2n_parity_r1..r4`.

### F5 — Sequence blobs are fetched in 5 000-id chunks (P2)

- **Location:** `general_popup.py:765-777` (and its twin `reports/chain.py:619-631`), `:752-762`
  (`_fetch_raw`).
- **What happens:** the ids just selected by `_query_hands` are sent back to DuckDB in chunks of
  5 000 (`IN (SELECT UNNEST(?::VARCHAR[]))`): 42 queries at 214k for VPIP.
- **Evidence (214k):** 648 ms wall / 1 961 ms CPU, compared with 172 ms for one query that joins the
  seq carrier row (`JOIN hand_players s ON s.hand_id = hp.hand_id AND s.h2n_seq IS NOT NULL`) under the
  same filter.
- **Proposal:** fetch `(hand_id, case, blob)` in the slim query from F3 with that join, restricted
  to hands that are not cached. Or fetch all and skip the cached ones.
- **Gain:** ~0.5 s per cold big popup at 214k. **Effort:** S. **Parity risk:** none.

### F6 — Every cold popup is O(opportunities) Python work (P2, larger refactor)

- **Location:** `general_popup.py:993-997` (`replay_set = hands if street > 0 or buckets else
  cases`), `:427-496` (`_size_hits`), `:594-617`.
- **What happens:** every preflop cell that has raise buckets (VPIP, PFR, Open Raise, 3-Bet, …)
  replays *all opportunities* for the Bet Sizes tab, even when the user only looks at Range. cProfile
  of a cold VPIP: `decode_sequence` 0.43 s, `_size_hits` + `_street_states` 0.36 s, of 1.03 s
  (profiled). After F3–F5 this is still ~6 s at 214k and ~30 s at 1M.
- **Proposal (pick one):**
  - **(a) Lazy tabs.** Return the summary and Range from SQL at once (F3). Compute Bet Sizes and
    Boards only when their tab is shown (a separate endpoint or `?parts=`). The Next Actions summary
    only needs *cases*.
  - **(b) Persist records.** Write popup records for the workspace hero into a DuckDB table
    (`h2n_popup(hand_id, player_id, row, next, direct, size_cases, size_opps, textures)`), computed at
    import or rebuild, where the matcher has already found `res.hit`. The popup then becomes a
    GROUP BY: <0.3 s at 214k, with no Python memory. Cost: ~70 rows × hero hands at import (sparse,
    only opp rows) and a STAT_VERSION bump.
  - **(c) Cheap tweak.** Cache only cases for preflop cells, and compute the opportunity-only bucket
    counts in a second pass on demand.
- **Gain:** (a) the first paint of a big popup goes from 7.7 s to <0.5 s at 214k. (b) all tabs <0.5 s
  at any scale.
- **Effort:** (a) M, (b) L. **Parity risk:** (a) low; (b) medium (same functions, run at a different
  time; needs the equality test from F4 and the parity suites).

### F7 — Opponent General replays every shared hand from `raw_text`, uncached (P2)

- **Location:** `backend/app/api/general.py:188-236` (`_vs_user_counts`, parse at `:210`).
- **What happens:** for a non-hero `player_id`, every hand he shares with the hero is fetched with
  `raw_text`, re-parsed and evaluated against 70+ rows on every request. Nothing is cached.
- **Evidence:** 73 shared hands add ~20 ms at 20k; 533 shared hands take 167–178 ms at 214k
  (~0.3 ms/hand). This fast-fold pool shares few hands per opponent. A cash regular in a 214k
  non-fast-fold DB can share 10–30k hands, which is ~3–9 s per opponent load (estimate).
- **Proposal:** decode `h2n_seq` (the `active` set can come from `seq.has_seq`/names). Cache per
  (player, filter), or store the vs-hero bits at import next to the h2n masks.
- **Gain:** ~4x without a cache; ~100% on repeats with one. **Effort:** S–M.
  **Parity risk:** low–medium (same equality test approach as F4).

### F8 — Frontend refetches the popup more often than the data changes (P2)

- **Location:** `frontend/src/components/general/StatPopup.tsx:125-129` and `:190-194`
  (`staleTime: 60_000`); `frontend/src/components/general/GeneralHandList.tsx:203`
  (`invalidateQueries({ queryKey: ['general'] })` on a tag change).
- **What happens:**
  - The grid uses `staleTime: Infinity` and relies on import/rebuild invalidation
    (`ImportContext.tsx:143,181`). The detail goes stale after 60 s, so reopening a stat page a minute
    later refetches it: 1.4 s warm, or 5–8 s at 214k if F1 evicted it.
  - Tagging a hand in the drawer invalidates the grid, every open detail and all hands lists, although
    only the hands rows show tags. `TagsSection.tsx:55` and `useMarkHand.ts:40` already use
    `['general', 'hands']`.
- **Proposal:** `staleTime: Infinity` for `cellDetailQueryKey` (it is the same data contract as the
  grid), and `['general', 'hands']` in `GeneralHandList.tsx:203`.
- **Gain:** removes 1.4–8 s backend runs per tag edit or reopen at 214k. **Effort:** XS.
  **Parity risk:** none.

### F9 — General SQL joins `hands` even with no hand-level filter (P3)

- **Location:** `general.py:97-109`, `:259`.
- **What happens:** `hand_players` already has `workspace_id`. With no stakes/mode/date filter, the
  `hands` join is only there for `h.workspace_id`.
- **Evidence (214k):** 100–150 ms with the join and 44–65 ms without, with identical results.
- **Proposal:** use `hp.workspace_id` and add the join only when `fsql` is non-empty.
- **Gain:** ~50–90 ms per grid load at 214k, and ~0.4 s at 1M (estimate). **Effort:** XS.
  **Parity risk:** none (result verified equal).

### F10 — Hands list re-runs the full case query per page (P3)

- **Location:** `general_popup.py:1205-1293`.
- **What happens:** each page of 50 re-selects *all* case hands (full `_Hand` rows), sorts them in
  Python, then re-parses the 50 shown hands from `raw_text` (`:1260-1270`). Board and size filters
  also walk every case record. Infinite scroll can fetch up to 512 rows (11 pages).
- **Evidence:** page 1 is 31–56 ms at 20k and 254–322 ms at 214k (VPIP/PFR), so ~3 s for a full
  scroll at 214k.
- **Proposal:** use SQL `ORDER BY … LIMIT/OFFSET` when there is no board/size filter (sort keys
  `played_at`, `won_bb`, `ev − won_bb` are columns). Fetch the page's `raw_text` in the same query.
- **Gain:** ~5x per page at 214k (estimate). **Effort:** S. **Parity risk:** none (ordering only; keep
  the `hand_id` tiebreak).

### Not a problem

- **General grid computation:** one query with 153 vectorised `SUM`s, grouped by `h2n_pos` (6 groups),
  and one scan of the player's `hand_players` rows. It is not one query per cell. Filters only add
  `hands` predicates. DuckDB still scans the player's rows and filters through the join. Date filters
  are cheaper (60 ms at 214k) thanks to zone maps on `played_at`.
- **Grid render:** ~102 stat cells plus labels in a few CSS grids (`GeneralGrid.tsx:136-160`). Rendering
  is trivial. Arrow-key navigation reads `getBoundingClientRect` of every cell per key press. That is
  fine at ~100 cells.
- **Dashboard tree:** saves are coalesced (`useDashboardsDoc.ts:55-80`), and the tree-width drag
  commits on pointer-up only. The PUT takes `db_lock`, so during an import it waits; the UI is
  optimistic, so this is not user-visible.
- **Notes tab:** one `players.detail` query.

## 4. Quick wins vs. larger refactors

Quick wins (≤ 1 day each, no parity risk or low):

- F8 `staleTime: Infinity` for detail + narrower tag invalidation (XS)
- F9 drop the `hands` join without filters (XS)
- F3 slim detail query + SQL aggregates (S)
- F5 single-query blob fetch (S)
- F1 capacity policy + F2 compact records + `clear_cache` on clear/rebuild/workspace delete (S–M)
- F10 SQL paging for the hands list (S)

Larger:

- F4 postflop from stored seq + board/hole columns (M, needs an equality test)
- F6a lazy Bet Sizes/Boards (M) or F6b persisted popup records (L, STAT_VERSION bump)
- F7 seq-based / cached vs-user counters (S–M)

## 5. Open questions / not measured

- The popup was not measured end to end through HTTP at 214k. The 214k numbers are direct
  `compute_detail` / `compute_general` calls on a read-only connection (no Pydantic response
  serialisation). Payloads are small (≤60 KB), so the difference should be minor.
- No browser profiling: grid render cost is judged by inspection only.
- Vs-user cost for an opponent with tens of thousands of shared hands is extrapolated. The 214k DB is
  mostly fast-fold, and its top opponent shares 533 hands.
- The cost of the Reports-backed popup tabs (preflop-range 557 ms cold at 20k, split next_actions) is
  measured here but analysed in reports 01/02. The popup and the Reports chain cache hold two separate
  per-hand caches for the same hands; merging them is worth a look there.
- RSS figures are unreliable under swap. Per-record memory comes from `tracemalloc` (accurate for
  Python objects; it excludes allocator fragmentation).
- Stale cache content after a STAT_VERSION rebuild: in practice, the code change that bumps it
  requires a restart, which empties the cache, so no wrong numbers were observed. A `clear_cache()`
  call on rebuild completion would make this explicit.
- The postflop popup at 214k (C-Bet Flop) was not measured: the shared bench lock was held by another agent's run for over 20 minutes. The figure is extrapolated from 330 µs/hand at 20k × ~10k opportunities.
