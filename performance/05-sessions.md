# 05: Sessions page

Scope: `/sessions`. Covers the session list (`GET /api/sessions`), the LIVE badge
(`GET /api/sessions/live`, polled every 60 s), the session, table and villain drill-down pages
(Stats recipe through `POST /api/reports/spot` with `recipe`, the graph, the hands list, and the
Tables / Players splits), and `day_start_hour`.

## 1. Summary

At 214k hands the Sessions page is not slow by itself. The list takes 50 ms, a session page fills
in 100–250 ms, and the live poll takes 11–33 ms. Sessions are already built in SQL with window
functions, not with a Python loop over every hand. The real costs show up in two places: while
auto-import runs during play, and when the user opens a large session.

Changes worth doing first:

1. **Stop the double refetch on every auto-import tick (S1, P1).** While the user plays, the
   global "invalidate everything" runs at most every 5 s. It first refetches the open live
   session's page queries with the old chain. The list response then moves `filter.end`
   (`last_hand_at`), so the same queries run a second time with the new chain. Estimated waste
   at 214k: about 0.4–0.6 s CPU per tick for a 2k-hand live session, out of about 1.2 s total.
   That is roughly 10% of a core for the whole time the user plays. Effort S, no parity risk.
2. **Aggregate the Players split in SQL (S2, P2).** This split has one row per opponent. On the
   largest session (5,934 hands, 4,624 opponents) it takes 533 ms wall / 693 ms CPU and returns
   2.1 MB. Most of that time is the Python step: building 28k `HandRec` objects and adding them
   up in `Acc`. A `GROUP BY player_id` with bit extraction should bring it to roughly 50 ms
   (estimate). Effort M, low–medium parity risk (needs an equality test).
3. **Shrink the session graph payload (S3, P2; the fix belongs to report 02).** The graph for a
   5,934-hand session is 2.35 MB; at the 90th-percentile session size (2k hands) it is 788 KB.
   That is about 395 B per point, because the response carries 14 cumulative series.
4. **Round floats and drop redundant fields in split rows (S4, P3).** The Tables and Players
   rows for a large Rush & Cash session are 1.2 MB and 2.1 MB. Values are sent at full float
   precision, and every row repeats a `filter` object that the client could build itself.
5. **Small backend wins on the list (S5, P3).** Replace the `MAX(e)` running-frame window with
   `LAG(e)`. The output was checked and is identical on all 250 sessions at 214k; it saves about
   12%. Optionally cache the list in process, keyed by the data generation.

What was checked and is fine: no per-session request fan-out from the list (stats are loaded only
for the selected session); the list grid is virtualised; `day_start_hour` costs nothing extra; the
LIVE poll is negligible.

## 2. Baseline

Machine: 16 GB Mac, swapping during the review. Every run was serialized with `bench-lock`. Wall
and CPU are process wall / process CPU in ms, median of 3–9 runs. CPU above wall means DuckDB ran
on several threads. 20k = shared benchmark DB through `TestClient(app)`. 214k = the user's DB
copy, opened `read_only=True` with `get_read_cursor` patched, routers mounted on a bare FastAPI app.

### Session list and live

| Call | 20k wall / CPU | 214k wall / CPU | Payload 20k / 214k |
|---|---|---|---|
| `GET /api/sessions` (all time) | 17 / 31 | 59 / 173 | 57 KB (162 sessions) / 89 KB (250 sessions) |
| `GET /api/sessions` with a date range | 17 / 28 | 48 / 153 (SQL only) | 13 KB / – |
| `build_sessions()` SQL alone | 14 / 27 | 50 / 157 | – |
| Reference: fetch ids + Python `split_sessions()` | 30 / 30 | 244 / 261 | – |
| `GET /api/sessions/live`, not live | 4.7 / 5.3 | 11.5 / 27.8 | 45 B |
| `live_session()`, live path (now = latest + 60 s) | 8.1 / 9.3 | 33 / 83 | 45 B |

214k session sizes: min 5, median 595, p90 2,017, max 5,934 hands.

### Session page fan-out at 214k

Opening page 0 fires three requests, plus one split when the Tables or Players tab is active.

"Cold" means the resolution cache was cleared before the run. This is what the first open, or any
open after new data, costs.

| Request | median (595 hands) | p90 (2,017) | largest (5,934) |
|---|---|---|---|
| `POST /reports/spot` `recipe=session`, cold | 36 / 106, 1.9 KB | 66 / 139, 1.9 KB | 109 / 191, 1.9 KB |
| `GET /reports/graph?chain=`, cold | 57 / 159, 231 KB | 99 / 206, 788 KB | 188 / 300, **2.35 MB** |
| `GET /hands?chain=&per_page=50`, warm | 75 / 168, 44 KB | 73 / 159, 43 KB | 98 / 201, 47 KB |
| `POST /reports/split` `tables`, warm | 12 / 14, 328 KB | 46 / 47, 1.1 MB | 50 / 51, **1.2 MB** (2,215 rows) |
| `POST /reports/split` `players`, cold | 98 / 206, 557 KB | 196 / 296, 1.1 MB | **533 / 693, 2.1 MB** (4,624 rows) |

At 20k (largest session: 836 hands), a cold page 0 (spot + graph + hands, sequential) takes
77 ms wall / 83 ms CPU. The table-page and villain-page recipes each take about 12 ms cold.

### Scaling

- **List.** Linear scan + sort over all of the player's hands: 14 ms at 20k, 50 ms at 214k.
  Estimate: about 250 ms wall / 0.8 s CPU at 1M hands. The payload is about 355 B per session
  (about 1,200 sessions, 430 KB, at 1M, estimate).
- **Session page.** Cost follows the session's size, not the database size. The exception is the
  fixed per-resolve overhead: `total_hands` COUNT at 10 ms and `data_version` at 0.7 ms (214k).
- **Live poll.** Uses `MAX(played_at)` over the hero's join (10 ms at 214k, about 50 ms at 1M,
  estimate), once a minute.

Swap versus genuine cost: no Sessions endpoint costs more than 0.2 s at 214k, except the Players
split on large sessions and the multi-MB graph and split payloads. Slowness the user saw on this
page was most likely swap plus the auto-import refetch load (S1), not list computation.

## 3. Findings

### S1 (P1): every auto-import tick refetches the live session page twice

- **Location:** `frontend/src/components/shell/AutoImportIndicator.tsx:51` (invalidates every
  query except auto-import's own); `frontend/src/lib/import/auto-import.ts:5-7` (status poll
  every 2 s, refresh at most every 5 s); `backend/app/api/sessions.py:56` (the row `filter.end` is
  `last_start`); `frontend/src/components/sessions/SessionPages.tsx:92-93`;
  `frontend/src/components/sessions/SessionPage.tsx:31-34` (page query = chain);
  `SessionStats.tsx:34-37`; `components/reports/tabs/GraphTab.tsx:16-17`;
  `components/hands/HandExplorer.tsx:338`.
- **What happens.** While the hero plays, the live session is selected and new hands arrive.
  - The global invalidation refetches every active query: the list, live, spot, graph, hands, and
    the active split.
  - The page-0 queries still carry the old chain `[{k:'session', start, end: <old last_hand_at>}]`.
    New hands changed `data_version`, so each one is a resolution cache miss on the server
    (`backend/app/reports/chain.py:791-814`) and is computed in full.
  - When the list returns, `session.filter.end` has moved. `scope0` changes, every page-0 query
    key changes, and all of them are fetched and computed again for the new chain. The
    old-chain results are never shown.
  - `getGraphData` and `getHands` take no AbortSignal (`frontend/src/lib/api.ts:396`, `:600`).
    Even with one, FastAPI sync handlers run to completion, so the wasted server work happens
    either way.
  - Side effect: the hands grid scrolls to the top on every key change
    (`HandExplorer.tsx:450`), so the user loses their scroll position every tick.
- **Evidence.** Per-tick server cost at 214k for a p90 (2k-hand) live session on the Hands tab,
  using the measured numbers above:

  | Part | Wall | CPU |
  |---|---|---|
  | List | 58 ms | 173 ms |
  | Live | 33 ms | 83 ms |
  | Spot, cold | 66 ms | 139 ms |
  | Graph, cold | 99 ms | 206 ms |
  | Hands | 73 ms | 159 ms |
  | **First pass total** | | **about 760 ms** |
  | Second page-0 pass (spot + graph + hands) | | **+ about 500 ms** |

  Total: about 1.26 s CPU per tick. At up to one tick per 5 s that is about 25% of one core while
  playing (estimate). On the Players tab, add 2 × 0.3 s.

  This adds up on top of the import tick itself (`light_finalize` → `detect_heroes`,
  `backend/app/api/import_hands.py:468-478`, see report 06), on the same machine that runs the
  poker client.
- **Proposal.**
  - Mark the Sessions page-0 queries (spot, graph, hands, split) with
    `meta: { followsSessionList: true }`.
  - Have the auto-import predicate skip them: `q.meta?.followsSessionList !== true`.
  - Put a cheap fingerprint of the row into their keys, e.g. `session.hands` and
    `session.last_hand_at` (or `won`). When the list refetches, a changed session changes its
    keys and refetches exactly once. An unchanged session keeps its cache. A hand inserted inside
    an unchanged `[start, end]` window still changes `hands`, so the page stays correct.
  - Deeper pages (table, villain) inherit the chain from page 0 and need the same treatment, or a
    plain invalidation, since they rarely sit on a live session.
  - Pass `signal` to `getGraphData` / `getHands` so a stale fetch at least stops the client-side
    JSON parse.
- **Expected gain.** About 40% less server CPU per auto-import tick on the Sessions page (about
  0.5 s per tick at a 2k-hand live session, more on larger ones; estimate). No scroll-to-top
  every 5 s.
- **Effort:** S (frontend only). **Parity risk:** none (same queries, fewer of them).

### S2 (P2): Players split folds each opponent's rows in Python

- **Location:** `backend/app/reports/split.py:402-420` (`players_table`);
  `backend/app/reports/chain.py:597-613` (`opponent_recs`); `split.py:179-216` (`Acc.add`).
- **What happens.**
  - Every other player's row in the case hands is fetched with 28 columns:
    `hand_id IN UNNEST(ids)` in chunks of 5,000.
  - Each row is turned into a `HandRec` and added to a per-opponent `Acc`. That is about 20
    attribute updates and about 12 `_bit` calls per row.
  - The result is cached on the resolution, so the cache helps only while `data_version` is
    unchanged.
- **Evidence** (214k, largest session, 5,934 hands → 28,070 opponent rows):

  | Step | Wall | CPU |
  |---|---|---|
  | SQL fetch only | 188 ms | 224 ms |
  | `_rec()` over the rows | 91 ms | 91 ms |
  | `players_table` total | 411 ms | 475 ms |
  | Row dicts (`players_split`) | 25 ms | 25 ms |
  | HTTP cold, including the resolve | 533 ms | 693 ms |

  Replacing `UNNEST(ids)` with `played_at BETWEEN` plus a hero semi-join barely helps
  (174 ms vs 188 ms). The cost is in materialising the Python tuples, not in the join.
- **Proposal.** One aggregate query per split:

  ```sql
  SELECT hp.player_id, p.username, COUNT(*), SUM(won), SUM(won_bb), SUM(won_bb*won_bb), ...,
         SUM((h2n_pre_case >> b_V01) & 1), ...
  ...
  GROUP BY 1, 2
  ```

  Take the bit positions from `app.h2n.rows` (the same source `_bit` and `_E` use). Build each
  `Acc` from the summed row, so `plain_values` and the summary stay unchanged.
- **Expected gain.** About 400 ms → about 40–60 ms for the largest session; about 150 ms → about
  20 ms at p90 (estimates: 28k rows grouped in DuckDB).
- **Effort:** M. **Parity risk:** low–medium. Integer counts are exact if the bit mapping matches.
  Float sums are added in a different order (sub-cent differences in `won`; `dispersion` uses
  `SUM(x²)`, same as `Acc.sq`). Guard it with a test that compares the SQL path to the `Acc` path
  on the 20k fixture, every session, every opponent. Splits are not covered by the parity suites
  `test_h2n_parity_*` / `test_stat_parity`, so they are not at risk from this change.

### S3 (P2): the session graph is multi-MB for long sessions

- **Location:** `backend/app/api/reports.py:72-74` (chain ids through `UNNEST`), `:133-148` (one
  `GraphPoint` with 14 cumulative fields per hand); `GraphTab.tsx:16-17`.
- **Evidence.** 2.35 MB for 5,934 hands (cold 188 ms, warm 97 ms server side), 788 KB at p90.
  About 395 B per point. The browser cost (JSON parse plus a Recharts render of about 6k points)
  comes on top and was not measured here.
- **Proposal.** Covered by report 02 (downsampled or columnar points). For the Sessions page, also
  consider sending only the series the session graph draws.
- **Effort:** see 02. **Parity risk:** none, if the endpoints and totals stay exact.

### S4 (P3): split payloads, Rush & Cash table names, full-precision floats

- **Location:** `split.py:380-399` (`tables_split`), `:423-438` (`players_split`), `:298-305`
  (`_row`).
- **What happens.**
  - Rush & Cash puts a few hands on each table name: 184k distinct names for 214k hands. The
    Tables tab of a big session therefore has 2,215 rows (1.2 MB). On the Players tab, 4,624 rows
    is 2.1 MB.
  - Values go out unrounded, for example `"pfr": 15.277777777777779`.
  - Every row repeats `filter` (about 10% of the bytes at 20k: 79 KB of 768 KB) and `player`.
  - Table rows also carry `session_values` keys that the table columns don't show.
  - Both grids are virtualised (`components/ui/data-grid/DataGrid.tsx:453-457`), so rendering is
    fine; the cost is transfer and JSON parse.
- **Proposal.** Round floats at serialisation, to about 6 significant digits. This is
  platform-wide; see report 08. Optionally let the client build `filter` for `players` (always
  `{k:'with', player_id}`) and `tables` (`{k:'table', v:[key]}`).
- **Expected gain.** About 35–45% fewer bytes (estimate, from the row shape).
- **Effort:** S–M (contract change for `filter`). **Parity risk:** none for counts; rounding must
  stay below what the formatter shows.

### S5 (P3): list recomputed per request; window shape

- **Location:** `backend/app/sessions_h2n.py:179-201` (CTE), `:226-250`;
  `backend/app/api/sessions.py:61-92`.
- **What happens.** `GET /api/sessions` rebuilds every session of the player on each call. The
  plan is a scan and hash join (214k rows, 0.03 s), then two WINDOW operators over the same
  `ORDER BY s, hid`, 0.07 s each: the `MAX(e)` frame "unbounded preceding .. 1 preceding", then
  the running `SUM` that numbers the sessions. Nothing is persisted. The frontend cache
  (`staleTime` 2 min, `frontend/src/lib/query-client.ts:6`) means it runs about once per visit or
  data change.
- **Evidence.**
  - SQL: 50 ms wall / 157 ms CPU at 214k.
  - A Python loop over the same hands would be 5× slower (244 ms), so the current design is
    already the right one.
  - `LAG(e) OVER (ORDER BY s, hid)` instead of the `MAX(e)` frame: 45.5 vs 51.9 ms wall (139 vs
    155 ms CPU), identical output on all 250 sessions. The two are equivalent because every hand
    ends at start + 180 s and the rows are sorted by start, so the running maximum of the earlier
    ends is the previous row's end.
- **Proposal.**
  - Switch to `LAG`. Keep a comment noting that it relies on the fixed 180 s end;
    `split_sessions` accepts an explicit end, the SQL does not.
  - Optionally memoise `list_sessions` in process, keyed by (workspace, player, max break,
    day_start, date range, `data_generation`, now-minute for `is_live`). This mostly helps the
    Refresh button and S1-style refetches when nothing changed.
  - Do not persist sessions in a table yet. The incremental bookkeeping (out-of-order imports,
    deletes, a max-break change, rebuilds) is not worth 50 ms; reconsider past about 1M hands.
- **Expected gain.** About 12% on the list now; about 50 ms → 0 on repeat hits with the memo.
- **Effort:** S. **Parity risk:** none (verified identical; run `tests/test_sessions_h2n.py`).

### S6 (P3): the live poll is cheap; two micro-redundancies

- **Location:** `backend/app/api/sessions.py:102-134`;
  `frontend/src/hooks/useSessionsLive.ts:12-17` (60 s, not in the background);
  `frontend/src/components/AppSidebar.tsx:136` (polls on every page).
- **Evidence.**
  - Not live: one `MAX(played_at)` over the hero join, 11 ms at 214k (the same query on `hands`
    alone is 0.5 ms).
  - Live: one extra `MIN(played_at)` full join (about 10 ms) plus a 24 h window fetch with a
    Python split, 33 ms in total.
  - Once a minute, that is under 0.1% of a core.
  - On the Sessions page the hook is mounted twice (sidebar and page) with the same query key,
    so it is still one request.
- **Proposal.** No action needed. If touched anyway: compute `MIN(played_at)` only when the window
  must double; return early when the workspace's `MAX(hands.played_at)` is older than now minus
  (max break + 180 s). That bound is safe because the hero's hands are a subset of the
  workspace's.
- **Effort:** S. **Parity risk:** none.

### Non-findings (checked)

- **No N+1 from the list.** `SessionNav` renders only list fields
  (`frontend/src/components/sessions/SessionNav.tsx:35-41`). Stats, graph and hands load only for
  the selected session (`SessionPages` is keyed by session id). Arrow keys move the active row,
  not the selection, so there is no request burst while scrolling the list.
- **List rendering.** Virtualised DataGrid; 250 rows at 214k, about 1,200 at 1M (estimate). Fine.
- **One resolution per page.** Spot, graph, hands and split of one page share a resolution
  through the resolve LRU and in-flight dedupe (`backend/app/reports/chain.py:791-814`). The
  session step is a plain `played_at BETWEEN` SQL filter (`chain.py:406-409`).
- **`day_start_hour`.** Handled in SQL (`backend/app/date_filters.py:12-21`, inside the CTE's
  `inr` flag). Frontend presets resolve to date strings, so query keys are stable. The session
  chain ignores the date range by design.
- **Recipe compute is small.** The `recipe(session)` Python pass (`Acc` plus `time_stats`) takes
  21 ms for 5,934 hands (`backend/app/reports/views.py:162-217`,
  `backend/app/sessions_h2n.py:157-174`).

## 4. Quick wins vs. larger refactors

**Quick wins (S)**
- S1: `meta.followsSessionList`, row-fingerprint keys, AbortSignal on graph/hands.
- S5: `LAG` window; optional list memo.
- S6: live-poll micro-trims, only if the file is touched anyway.

**Larger (M)**
- S2: SQL aggregation of the Players split, with an equality test against `Acc`.
- S3 / S4: graph and split payload shape. Coordinate with reports 02 and 08 (one serialisation
  policy).

**Not recommended now**
- A persisted `sessions` table: 50 ms today, with complex invalidation.

## 5. Open questions / not measured

- **Browser side.** No browser profiling was done: JSON parse and the Recharts render of a 2.35 MB
  graph, DataGrid with 4.6k rows. The figures here are server-side only.
- **Real tick rate.** The auto-import tick rate and the actual double fetch (S1) were derived
  from code reading, not observed in a running app (the rules forbid starting the user's app).
  The per-tick cost uses the measured per-endpoint numbers, summed.
- **Concurrency.** Concurrent execution was not measured. Page-0 requests run in parallel in the
  FastAPI threadpool on cursors of one DuckDB connection. Wall times above are sequential, single
  request.
- **1M hands.** Numbers at 1M are linear extrapolations, not measured.
- **Cold DB cache.** The first query after opening the 214k DB took 335 ms wall / 2.7 s CPU
  (`resolve_hero`, with DuckDB pages cold). Warm, `resolve_hero` takes 7.6 ms, and 5 parallel
  uncached calls take 18 ms wall / 115 ms CPU. Startup / cold cache belongs to report 08.
- **Not a performance issue: two session rules.** The Graph's session markers use a separate
  "gap between consecutive hands > 10 min" rule (`backend/app/api/reports.py:19`), which is why
  the lead counted 282 graph sessions. The Sessions page's Hand2Note rule gives 250 at 214k.
- **Unmeasured deeper pages.** The `with` step uses an `EXISTS` subquery
  (`backend/app/reports/chain.py:413-416`). Villain pages measured about 12 ms at 20k; they were
  not measured at 214k.
