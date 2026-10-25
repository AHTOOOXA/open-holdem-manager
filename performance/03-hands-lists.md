# 03: Hand lists, hand panel, replayer, export

Scope: the Reports **Hands** tab (`HandExplorer` with the Reports `chain`), Marked Hands (`/marked`),
the legacy `HandsPage`, the docked hand panel, drawer replayer, quick replay, Copy/Show Hand History,
`GET /api/hands/export`, the tags column and mark/unmark.

## 1. Summary

The hand list pages with OFFSET and runs a COUNT on every request. That design is fine at 214k hands:
with no chain, a page takes about 50 ms. The cost comes from the **Reports chain**. Every page, sort and
mark refresh resolves the chain to all 214,188 case hand ids. The list then binds those ids **twice** as
a `VARCHAR[]` parameter, once for the COUNT and once for the page query. Binding a 214k-string list costs
about 121 ms of pure CPU per bind. A warm Reports Hands page is therefore about 7x slower than the same
list without a chain. The export is the other real problem. It fetches raw texts in 500-id `IN` batches,
and each batch scans the whole `hands` table: 100k hands take 7 s wall and 12 s CPU, where one ordered
join takes about 0.16 s.

Worth doing first:

| # | Change | Expected gain (214k) | Effort | Parity risk |
|---|---|---|---|---|
| 1 | Stop binding the case ids as a Python list. Register them once as an Arrow table cached on the `Resolution` and use `IN (SELECT id FROM case_ids)`, or push the SQL predicate for chains without spot steps (F1) | warm page 347 → ~40–60 ms (bench: 297 → 39 ms for COUNT+page) | S–M | none (same row set, verified equal) |
| 2 | Export: one ordered streaming query (`fetchmany`) instead of 200 × 500-id `IN` batches (F2) | 100k-hand export 7.1 s / 12 s CPU → ~0.5 s (bench: fetch part 9.7 s → 0.16 s) | S | none (same bytes, same order) |
| 3 | Pass the react-query `AbortSignal` to `getHands`, and skip the COUNT when the total is known (`len(case_ids)` with no extra filters) (F3, F4) | removes the second 214k bind, and superseded page/sort clicks stop burning ~0.45 s of CPU each | XS | none |
| 4 | Mark/unmark: invalidate only marked/tag-filtered lists (rows are already patched in place) (F6) | saves one ~350 ms list refetch per mark at 214k with a chain | XS | none |
| 5 | Drop the dead `actions` query and the redundant `player_id` EXISTS, and slim `ActionItem` in list rows (F5, F7, F8) | ~5–80 ms/page, ~25 % smaller list payload | XS | none |

**Swap versus genuine cost.** In every measurement below CPU time is at or above wall time, so these
costs are genuine and not swap artefacts. On the user's swapping machine wall time can only be worse.
The first Hands-tab load after a chain change is dominated by the **cold chain resolve**: 2.7 s CPU at
214k for `chain=[]`, with peak RSS +420 MB. That resolve is owned by report 01. The list adds about
0.35 s on top and repeats it on every page, sort and mark.

## 2. Baseline

Machine: 16 GB Mac. Each run was serialised with `bench-lock`. Numbers are best of 3–5 runs unless marked
"cold". 20k = the shared benchmark copy (`/tmp/ohm-perf/03`, through TestClient end to end). 214k = the
user-sized copy (`/tmp/ohm-mem/poker.duckdb`, read-only, direct calls into `app.api.hands` with the
request cursor patched to a read-only connection, so there is no HTTP layer; that layer adds about 2–5 ms).
Scripts: `/tmp/ohm-perf/03/bench_list.py`, `bench_stages.py`, `bench_alt.py`, `bench_export.py`.

### Endpoints the screens call

| Call | Trigger | Frontend |
|---|---|---|
| `GET /api/hands?page&per_page&sort&order&chain=…` | mount, page, per-page, sort, filter, chain change, any mark/unmark (invalidate) | `HandExplorer.tsx:337-341` → `api.ts:592-603` |
| `GET /api/hands/{id}?player_id` | row click (panel), double click (drawer), hover ▶ (quick replay), Show/Copy history | `HandPanel.tsx:34`, `QuickReplay.tsx:20`, `HandHistoryDialog.tsx:19`, `HandDrawer.tsx:77` (no cache), `handListActions.ts:9` (no cache) |
| `GET /api/hands/export?…` | Export button / row menu | `handListActions.ts:29-47` (anchor download, streamed to disk) |
| `PUT/DELETE /api/hands/{id}/mark` | mark, tag, unmark | `useMarkHand.ts:44-71` |

### Measurements

| Request | 20k wall / CPU | 214k wall / CPU | Payload |
|---|---|---|---|
| list, no chain, p1 × 50 (legacy HandsPage, embedded lists) | 30 / 30 ms | 51 / 124 ms | 44 KB (870 B/row, 8 actions/row) |
| list, no chain, p1 × 200 | 40 / 40 ms | n/m | 170 KB |
| list, no chain, deep offset (15k / 100k) | 31 / 32 ms | 67 / 180 ms (SQL only) | 43 KB |
| list, `chain=[]`, **cold** (includes resolve) | 258 / 263 ms | **2,660 ms resolve** + 347 ms | 44 KB |
| list, `chain=[]`, warm p1 | 58 / 71 ms | **347 / 448 ms** | 45 KB |
| list, `chain=[]`, sort won_bb | 57 / 58 ms | 395 / 569 ms | |
| list, `chain=[]`, page 2000 | 60 / 77 ms | 402 / 543 ms | |
| list, `chain=[]` + `player_id` (Reports for a chosen player) | 59 / 79 ms | 428 / 599 ms | |
| list, `marked=true` (Marked Hands, 0 marks) | 31 / 45 ms | 93 / 373 ms | |
| list, `sort=tags`, no chain | 31 / 43 ms | 65 / 143 ms | |
| hand detail (`GET /api/hands/{id}`) | 6.5 / 6.8 ms | 6.6 / 12 ms | 3.6 KB |
| export, 20k hands (all) | 535 / 644 ms | — | 23.7 MB |
| export at 214k (capped at 100k) | — | **7,059 / 12,113 ms** | 118.6 MB |

Stage breakdown of one warm `chain=[]` page at 214k (`bench_stages.py`):

| Stage | wall / CPU |
|---|---|
| `resolve()` cache hit (`data_version` + settings) | 1.2 / 2.6 ms |
| `Resolution.case_ids`: rebuilds a 214k list on every access | 11 / 11 ms |
| COUNT with `IN (SELECT UNNEST(?::VARCHAR[]))` | **147 / 171 ms** (vs 10 / 24 ms without the list) |
| page query with the same list | **146 / 201 ms** (vs 22 / 66 ms) |
| of which: binding the list alone (`SELECT len(?::VARCHAR[])`) | **121 / 121 ms** per bind |
| board cards batch (50 ids) | 2.8 / 5 ms |
| `actions` batch (table is empty) | 0.8 / 1 ms |
| `raw_text` fetch for 50 rows + `parse_actions_from_raw` | 11 + 2.4 ms |
| marks/tags (`marks_for`) | 0.4 ms |
| Pydantic `model_dump_json` | 0.2 ms |

### Scaling estimate (linear extrapolation)

| | 20k | 214k (measured) | 1M (estimate) |
|---|---|---|---|
| warm page with chain | 58 ms | 350–400 ms | ~1.5–2 s (2 binds × ~0.57 µs/id plus the joins) |
| warm page without chain / with fix #1 | 30 ms | 40–60 ms | ~150–250 ms |
| export, 100k cap | n/a | 7 s wall / 12 s CPU | ~30 s+ (each of the 200 batches scans a 5x larger table) |
| export with fix #2 | | ~0.5 s | ~1 s |

## 3. Findings

### F1 (P1): the Reports chain is passed back to SQL as a 214k-element bound list, twice per request
- **Location:** `backend/app/api/hands.py:47-50`, `:113-115`, `:192-198`, `:205-216`; `backend/app/api/reports_lite.py:84-98`; `backend/app/reports/chain.py:566-568`.
- **What happens:** `chain_hand_ids()` returns `resolve(...).case_ids`, a fresh Python list of every case
  hand id (214,188 for the default `chain=[]` page). `_list_filters` appends
  `h.id IN (SELECT UNNEST(?::VARCHAR[]))` with that list as a parameter. The same `params` list is
  executed for the COUNT and, after the LIMIT/OFFSET is appended, for the page query. DuckDB converts
  the Python list into a constant LIST value on every execute; `EXPLAIN` shows the ids inlined into the
  plan.
- **Why slow:** O(N) Python → DuckDB value conversion per bind (about 0.57 µs/id), twice per request. It
  holds the GIL during conversion (an estimate based on how the binding works). It runs on every page,
  sort, per-page change and post-mark refetch, even though the resolution, and so the id set, is
  cached and unchanged.
- **Evidence:** 214k: COUNT 10 → 147 ms and page 22 → 146 ms when the list is added. Bind alone is 121 ms.
  The end-to-end warm page is 51 ms without the chain and 347 ms with it.
- **Proposal (pick one, both verified to return the identical count and first page):**
  - **B (general):** build `pa.table({"id": case_ids})` once per `Resolution` and cache it in
    `res.tables`. The build takes 5 ms at 214k. In the request, call
    `cursor.register("case_ids", tbl)` and use `h.id IN (SELECT id FROM case_ids)`. Bench: COUNT+page
    297 → **39 ms**. pyarrow is already in `requirements.txt`. The registration is per cursor, and
    `get_read_cursor()` hands out a new cursor per request, so no names collide.
  - **A (chains without spot steps, including the default `[]`):** `_compute` already selects those
    cases with `_BASE_WHERE + plain_sql(chain) + _row_bits_sql(chain)` (`chain.py:687-692`). The list can
    AND that predicate in directly, with no ids. Bench: **29 ms**. Only valid when `hp` is the
    resolution's subject (not the `all_marked` path). Keep B for spot chains.
- **Gain:** warm Reports Hands page at 214k ~350 → ~40–60 ms. At 1M it stays sub-second.
- **Effort:** S (B) / M (A+B). **Parity risk:** none. The same hand set by construction, and a unit test
  can assert the equal id set. No stat numbers are touched.

### F2 (P1): export fetches texts in 200 × 500-id IN batches, each scanning `hands`
- **Location:** `backend/app/api/hands.py:400-411` (id query, which binds the chain list a third time),
  `:423-440` (batches).
- **What happens:** the endpoint first materialises up to 100,001 sorted ids. The stream then runs one
  `SELECT id, raw_text FROM hands WHERE id IN (?, ?, … ×500)` per batch, which is 200 queries at the cap.
  Each is a sequential scan of `hands` with an IN filter, about 35 ms each at 214k, using several DuckDB
  threads. Starting the download is quick (296 ms until headers), but the stream then takes 7 s.
- **Evidence:** 214k, 100k cap: 7,059 ms wall / 12,113 ms CPU, 118.6 MB. The same 100k texts through one
  ordered join (`exp_ids` Arrow table `JOIN hands … ORDER BY o`, read with `fetchmany(2000)`) take
  **157 ms / 193 ms**. 20k all-hands export: 535 ms, of which 462 ms is batches against 76 ms for one join.
- **Proposal:** fold the dedupe/sort query and the text fetch into one query:
  `SELECT h.raw_text FROM (… rn = 1 …) s JOIN hands h ON … ORDER BY sk, pa, id LIMIT cap`. Run it on the
  stream's own cursor and yield `fetchmany(1000–2000)` chunks. Memory stays bounded (DuckDB streams
  result chunks). Detect the cap with `LIMIT cap+1` on a cheap COUNT, or by peeking one extra row.
  Combine with F1 for the chain filter.
- **Gain:** ~7 s → ~0.5 s for a capped export at 214k. About 11 s less CPU competing with the rest of
  the app while the download runs.
- **Effort:** S. **Parity risk:** none (same bytes; check with a byte-for-byte test on the fixture).

### F3 (P2): COUNT(*) re-run for every page, sort and refetch
- **Location:** `hands.py:192-199`.
- **What happens:** the total is recomputed on every request, although only page and sort changed. With
  a chain and no other filters the total is simply `len(res.case_ids)`, since each case hand has exactly
  one subject row.
- **Why slow:** at 214k it is 147 ms with the bound list. With F1 it is 10–25 ms, so this mostly matters
  until F1 lands.
- **Proposal:** (a) with a chain and no extra filters, use `total = len(case_ids)`. (b) Optionally cache
  the total per (filters, data version) and send it only when the filters change; for example, the
  client keeps the total in its own `['hands','count',filters]` query.
- **Gain:** one fewer full join per request (~10–150 ms at 214k). **Effort:** XS. **Parity risk:** none.

### F4 (P2): superseded list requests are never cancelled
- **Location:** `frontend/src/lib/api.ts:592-603` (`getHands` takes no `signal`), `HandExplorer.tsx:339`.
- **What happens:** `keepPreviousData` keeps the old page on screen, but quick clicks through pages,
  sorts or per-page values each leave a full request running on the server. Each one costs about
  0.45 s CPU at 214k today. Under swap they queue behind each other and the last click arrives last.
- **Proposal:** `queryFn: ({ signal }) => getHands(params, signal)` and `fetch(url, { signal })`. The
  server still finishes the request (Starlette does not cancel a sync endpoint), so the gain is client
  latency plus less JSON parsing. F1 is what removes the server cost.
- **Effort:** XS. **Parity risk:** none.

### F5 (P3): the `actions` table is never written, so every list page runs a dead query and re-parses raw text
- **Location:** `hands.py:245-282` (DB path), `:284-299` (raw-text fallback). Nothing in `backend/app`
  inserts into `actions`, and the table is empty in both benchmark DBs (0 rows in the 214k DB).
- **What happens:** every page queries `actions` (empty), then fetches `raw_text` for all rows (about
  1.2 KB each) and regex-parses each hand (`app/action_parser.py:28-133`). The DB-path code (pot
  propagation, `action_pid`) is unreachable.
- **Cost:** 0.8 ms + 11 ms (fetch) + 2.4 ms (parse) for 50 rows at 214k. That is small, because only
  one page is ever parsed.
- **Proposal:** delete the `actions` query and the dead branch. If the list ever has to be faster, store
  the compact per-street action string and pot on `hand_players` or `hands` at import (an import/STAT
  bump decision, not needed for performance now).
- **Effort:** XS. **Parity risk:** none (the output is the same; the fallback is already the only path).

### F6 (P3): every mark/unmark refetches every hand list
- **Location:** `frontend/src/components/marked/useMarkHand.ts:38-41` (`invalidateQueries(['hands'])`);
  `HandExplorer.tsx:672` does the same from the drawer.
- **What happens:** the rows are already patched in place (`apply`, `:27-37`). The blanket invalidation
  still refetches the visible list, which costs ~350 ms at 214k with a chain (COUNT + page + bind). It
  also marks every cached page and list stale, including other HandExplorer instances, so revisiting
  them refetches.
- **Proposal:** invalidate only lists whose params filter on `marked`/`tag_ids` or sort by `tags`. Rely
  on the patch for the rest.
- **Gain:** one list request per mark action. **Effort:** XS. **Parity risk:** none.

### F7 (P3): redundant EXISTS when `player_id` is given
- **Location:** `hands.py:107-111`.
- **What happens:** when `player_id` is set, `join_player` is already `hp.player_id = ?` with the same
  id, so `EXISTS (… hp2.player_id = ? …)` is always true. Reports sends `player_id` whenever a player
  other than the default hero is chosen (`LowerReports.tsx:137`).
- **Evidence:** 214k: 428 ms against 347 ms with the chain. Without the bind cost the difference is
  about 30–80 ms.
- **Proposal:** drop the clause. **Effort:** XS. **Parity risk:** none.

### F8 (P3): list payload carries detail-only fields
- **Location:** `hands.py:297` (fallback parse output used as is); `models.py:159-164`.
- **What happens:** each `ActionItem` in list rows includes `p` (username) and `ai`. Pot cells and
  `Actions.tsx` use only `a`, `v` and `h`. At 8 actions/row that is about 25–30 % of the 870 B/row.
- **Proposal:** strip `p` and `ai` in the list (`ActionItem(a, v, h)`), or serialise with
  `exclude_none` and set `ai=None` when false. **Gain:** 44 → ~32 KB per page (minor; local app).
  **Parity risk:** none.

### F9 (P3): Marked Hands without a subject probes `marked_hands` for every `hand_players` row
- **Location:** `hands.py:57-60` (`all_marked` join condition), plus `list_filter_sql` adds the same
  EXISTS again (`marked_hands.py:413-418`).
- **Evidence:** 214k, 0 marks: 93 ms wall / **373 ms CPU** (1.29M `hand_players` rows semi-joined, twice
  per request through COUNT and page).
- **Proposal:** drive the query from `marked_hands` (`FROM marked_hands mh JOIN hand_players hp … JOIN
  hands h …`). Marks are few, so this becomes O(marks). **Effort:** S. **Parity risk:** none.

### F10 (P3): the drawer and Copy Hand History bypass the detail cache
- **Location:** `HandDrawer.tsx:74-87` (manual `useState` fetch), `handListActions.ts:9`.
- **What happens:** the panel, quick replay and history dialog share
  `['hands','detail',id,playerId]` (60 s stale time on quick replay). The drawer refetches on every
  open and every j/k step, and Copy always refetches. The server cost is 6–12 ms, so this is a
  consistency cleanup more than a speed fix. Moving to `useQuery` with the same key would make j/k
  through recently hovered hands instant.
- **Effort:** S (the drawer mutates its local `hand` for mark/note; use `setQueryData`).
  **Parity risk:** none.

### Not problems (checked)
- **Pagination strategy:** OFFSET with a deterministic tiebreak (`hands.py:212`). Without a chain, deep
  pages at 214k cost 67 ms against 22 ms for page 1. Keyset pagination is not worth its complexity at
  this scale, and the UI pages at 25/50/100 rows.
- **Per-row work:** no N+1. Boards, marks/tags and raw texts are each one batched query per page, and
  parsing is O(page).
- **Indexes:** the list plans are sequential scans + hash joins + TOP_N (`EXPLAIN` in `out214k.txt`).
  DuckDB does not use the ART indexes on `hand_players(player_id, …)` or `board_cards(hand_id)` for
  these, and zone maps do the pruning. More indexes would not help reads; they only cost on import
  (report 06).
- **Hand detail:** 6–12 ms, 3.6 KB. It parses only one raw text.
- **Frontend rows:** at most 100 rows per page. The grid virtualises only above 200 rows
  (`data-grid/logic.ts:381`), so all rows mount. `GridRow` is memoised (`DataGrid.tsx:1099`) and
  `columns` / `renderRowMenu` are memoised in `HandExplorer`. Each row mounts a Radix `ContextMenu` and a
  `QuickReplay` popover root, which is cheap until opened. Not profiled in a browser (see section 5).
- **Tags sort:** a correlated subquery per row costs 65 ms at 214k with 0 marks. That is acceptable.

## 4. Quick wins vs. larger refactors

**Quick wins (under 1 day total, no parity risk):**
- F1-B: Arrow-registered case ids, cached on the `Resolution` (largest win for the Reports Hands tab).
- F2: single streaming export query.
- F3: `total = len(case_ids)` when only the chain filters.
- F4: AbortSignal in `getHands`.
- F5, F7, F8: delete the dead actions query and the redundant EXISTS, and slim `ActionItem`.
- F6: narrow the mark invalidation.

**Larger / optional:**
- F1-A: push plain-chain predicates into the list SQL. This needs a small API on `app.reports.chain`
  exposing `(where, params)` for a chain without spot steps; coordinate with report 01, which owns
  `resolve()`.
- Serve chain lists straight from the cached `Resolution`. Sort the `HandRec`s once per sort key,
  cache the order in `res.tables`, and fetch only the page's 50 rows. Measured at 12 ms per page warm
  and 68 ms for the first sort. This only helps when the chain is the only filter. Not needed once F1
  lands.
- F9: Marked Hands driven from `marked_hands`.
- Store the per-street action string and pot at import (F5). Only if list latency matters again at 1M.

## 5. Open questions / not measured

- **Cold resolve cost and memory** (2.7 s, +420 MB peak RSS at 214k for `chain=[]`; spot chains are
  more) dominate the first Hands-tab load after any chain change. They belong to report 01. The LRU
  budget of 600k hand records holds only about 2.8 resolutions of 214k hands, so drilling across
  report pages can evict and re-resolve. Worth checking there.
- **Concurrency on the real page:** the Hands tab request runs in parallel with the Stats/Split/Graph
  requests of the same chain. They share one resolve (the in-flight lock), but the 2 × 121 ms GIL-bound
  binds (an estimate) and the export's multi-threaded scans compete with those requests. This was not
  measured under concurrent load.
- **Browser render cost** (React commit per page, Radix per-row roots, card/chip rendering): not
  profiled. The rule was not to start servers or touch the user's app. Expected to be small at
  ≤100 rows, but unverified.
- **HTTP layer at 214k:** the 214k numbers are direct function calls. The JSON (45 KB) and FastAPI
  validation measured 0.2 ms at the model level; TestClient overhead at 20k was about 5 ms.
- **Marked Hands with many marks** (thousands): the benchmark DBs have 0 marks. F9's cost was measured
  only for the empty case.
- **Swap:** all numbers come from runs serialised under `bench-lock` with CPU ≥ wall. The user's "takes
  ages" is consistent with a 2.7 s cold resolve plus about 0.35 s per list request, multiplied by swap
  on a memory-pressured machine. These numbers do not reproduce the swap.
