# 08 — Platform and infrastructure

Scope: the layers every page sits on. That covers the DuckDB layer (`backend/app/db.py`), the API layer
(`backend/app/main.py`, FastAPI serialization, threadpool), the caches, the frontend platform (React
Query defaults, polling, bundle), Electron startup, and the Databases and Configuration endpoints.
Page-specific hot paths (Graph, chain resolve, popup replays, import) belong to reports 01–07. This
report only covers the systemic causes behind them.

Setup: 20k-hand benchmark DB (a copy of the 20k DB, hero "Hero", workspace 1), DuckDB
1.4.4, FastAPI 0.162, Pydantic 2.14, Python 3.12.12, 10-core / 16 GB Mac that was swapping. SQL
checks at 214k ran against a copy of the 214k DB opened `read_only=True`. All runs were taken
under `bench-lock`. Each timing is the best of 3–20 runs and shows wall and CPU time.

## 1. Summary — do these first

| # | Change | Expected gain | Effort | Parity risk |
|---|---|---|---|---|
| 1 | **Stop the auto-import "refresh everything" storm** (F1). Today every auto-import tick bumps a global data generation, which drops every cached resolution in every workspace. The frontend also invalidates every query. Fix: scope the invalidation to the workspace, refresh only cheap queries automatically, and offer "new hands, refresh" for the heavy report queries. | Removes a repeat of every open report's full compute (Graph at 214k: 43 s) every ≥5 s while playing. At 214k this alone can keep one core busy all the time. | S–M | None |
| 2 | **Fetch DECIMAL columns as DOUBLE (or columnar) on hot per-hand paths** (F2). Python `Decimal` objects cost about 5× the fetch time and about 4× the memory of floats. | Graph-like fetch at 214k: 777 ms → 124 ms (measured). The same factor applies to chain `_COLS`, sessions and stats row fetches. | S (mechanical) | Low: the code already calls `float()` on each value. Keep `SUM()` in SQL on DECIMAL. |
| 3 | **Drop the 14 non-unique ART indexes** (F3). They take 46% of the DB's used blocks, no measured query uses them, inserts get 2.5× slower and deletes 26× slower. | 20k DB: 259 → 139 used blocks. Estimated ~300–450 MB less file at 214k. Faster auto-import ticks and workspace deletes. CHECKPOINT no longer re-serializes the ARTs. | S | None (no query result changes) |
| 4 | **Bound the CPU-heavy endpoints with a small limiter and make them cancellable** (F4). Three parallel Graph requests take 1.70 s, while the same three run back to back take 1.09 s. Aborted requests keep computing. | No more GIL thrash or stacked computations from fast filter clicking. Peak RAM drops (at most 1–2 resolutions in flight). | M | None |
| 5 | **Account for the caches in bytes, not entries, with one global budget** (F5). The chain cache allows 600k hand records at about 0.94–1.6 KB each, plus 300k popup records. Worst case is about 1 GB+ of small Python objects, and pymalloc keeps that RSS after eviction. | Estimate: caps steady-state cache RSS at a chosen budget (e.g. 256 MB), instead of 1+ GB at 214k. | M | None |

Smaller items (F6–F12): startup column probes, the Electron health-wait budget, DB file bloat, the
workspace-delete SQL, `BaseHTTPMiddleware`, bundle splitting, React Query `gcTime` for large
payloads, and the 4 GB `memory_limit`.

## 2. Baseline (20k hands unless noted)

| Item | Wall | CPU | Payload / size | Note |
|---|---|---|---|---|
| `import app.main` (cold) | 0.65–0.77 s | 2.0–2.8 s | — | Each backend start pays this. PyInstaller adds unpacking (not measured). |
| `get_db()` = connect + `init_schema` | 0.39–0.45 s | 0.37–0.41 s | 125 statements | 0.37–0.42 s of it is 53 `duckdb_columns()` probes (F6). |
| `GET /api/health` | 1.4 ms | 1.4 ms | 73 B | Cheap. Polled only during a rebuild (1 s). |
| `GET /api/workspaces` | 3.6 ms | 6.9 ms | 213 B | Refetched on every auto-import refresh. |
| `GET /api/system/info`, `/api/config/*`, `/api/app-settings`, `/api/tag-defs`, `/api/identities`, checkpoints, sites | 1.0–1.6 ms | ≈ same | <0.4 KB | Databases and Configuration pages: no problem. |
| `GET /api/workspaces/1/heroes` | 5.8 ms | 8.4 ms | 204 B | |
| `GET /api/players?min_hands=1&per_page=30` (AliasDialog) | 49–71 ms | 68–94 ms | 7.5 KB | Grows with player count (62k players here, 262k at 214k). See report 07. |
| `GET /api/auto-import/status` | 1.1 ms | 1.0 ms | 167 B | Polled every 2 s. |
| `GET /api/sessions/live` | 4.5 ms | 4.5 ms | 45 B | Polled every 60 s. |
| `GET /api/reports/graph` | 261–340 ms | 266–333 ms | 8.1 MB | Handler 247 ms. Serialization through FastAPI's `dump_json` path only 24.5 ms. |
| Graph handler serialization alternatives | — | — | 8.1 MB | pydantic `model_dump_json` 24.5 ms; `model_dump`+`json.dumps` 97 ms; `jsonable_encoder`+`dumps` 462 ms; orjson(dict) 9.6 ms |
| 3× Graph sequential vs 3 threads in parallel | 1085 ms vs **1703 ms** | — | — | Parallel is slower: GIL contention (F4). |
| Empty-chain resolve (`reports/chain.py` `resolve`, `[]`) | 1.08 s* | 1.04 s* | **940 B / hand retained** | *tracemalloc on. P01 spot chain: 1.6 KB per hand incl. `h2n_seq` blobs. |
| DB file | — | — | 66 MB; 259 used blocks, of which ~120 are indexes | F3 |
| Frontend bundle | build 6.5 s | — | 1 JS chunk 1,616 KB (475 KB gzip), CSS 127 KB | F11 |

214k (read-only SQL):

| Item | Value |
|---|---|
| Hero hand rows | 214,246 of 1,286,048 `hand_players` rows. 216,754 hands. |
| Graph-like join: SQL only (`count(*)`) | 19.5 ms |
| Same, `fetchall()` with DECIMAL → Python `Decimal` | **777 ms** wall / 789 ms CPU |
| Same, `::DOUBLE` + `epoch()` in SQL | **124 ms** / 166 ms |
| Same, `fetchnumpy()` / `fetch_arrow_table()` | 69 ms / 141 ms |
| 10 narrow cols `fetchall` / 107 cols (`hp.*`) | 358 ms / 2,336 ms |
| Binding a 214k-element `?::VARCHAR[]` list | 421 ms wall / 194 ms CPU (bind only) |
| `EXPLAIN ANALYZE` hero join | HASH_JOIN over two sequential scans. No index used. 18.5 ms. |
| DB file | **2.9 GiB**: 12,098 blocks, of which **9,382 are free (77%)**. Used ≈ 680 MB. Of the used blocks, ~910 are table data (hands 471, hand_players 428). The rest is mostly indexes and the players tables. |
| `raw_text` / `h2n_seq` bytes | 256 MB / 117 MB |
| DuckDB buffer memory after scanning raw_text + hand_players + a join | 192 MB (`duckdb_memory()`) |

Scaling (estimates): SQL scans grow linearly and stay small (≈20 ms at 214k, ≈100 ms at 1M). The
Python per-hand materialization grows linearly too, but with a big constant: about 3.6 µs per hand
per `Decimal` row fetch, and ~1 KB of retained heap per cached `HandRec`. At 1M hands one empty-chain
resolution would hold ~0.9 GB (estimate). The 11 GB dev process is consistent with this: several
cached resolutions, popup records and import leftovers, all in pymalloc arenas that never return to
the OS.

## 3. Findings

### F1 — Auto-import refresh invalidates every cache and every query (P0)

- **Where:** `frontend/src/components/shell/AutoImportIndicator.tsx:48-53`
  (`qc.invalidateQueries({ predicate: q => q.queryKey[0] !== 'auto-import' })` plus
  `refetchWorkspaces()`), `frontend/src/lib/import/auto-import.ts:5-7` (poll every 2 s, refresh
  gap 5 s), `backend/app/api/import_hands.py:468-478` (`light_finalize` → `data_generation.bump()`),
  `backend/app/data_generation.py:14-22` (one process-wide counter),
  `backend/app/reports/chain.py:781-788` (the counter is part of every resolution key).
- **What happens:** while the user plays with auto-import on, new hands arrive every few seconds.
  Each import tick bumps the single global generation, so every cached resolution of every
  workspace and player becomes unreachable (it then sits in the LRU until evicted). At most every
  5 s the frontend marks all queries stale. Every mounted query refetches right away and every
  unmounted one refetches on its next mount. Reports Graph, Split, Preflop Range, the General
  popup and so on then recompute from scratch.
- **Why it is slow:** this is a full recompute (at 214k: Graph 43 s per report 02, resolutions
  1–3 s at 20k → ~10–35 s at 214k, estimate), triggered more often than it can finish. Together
  with F4 (no cancellation), computations stack up behind the GIL. A modest DB can saturate a core
  for the whole session, and memory grows with each orphaned resolution until LRU eviction.
- **Evidence:** code path above. `refreshDelay` returns 0–5000 ms whenever `session_hands`
  increases. Each tick also calls `detect_heroes`, which clears the hero cache.
- **Proposal:**
  1. Frontend: on auto-import growth, invalidate only cheap, live-relevant keys: workspaces,
     sessions live and list, the health/hand count, the hand list page 0. Show a passive "N new
     hands — refresh" chip on heavy report screens (Reports tabs, General popup, Population). If an
     automatic refresh is wanted, use a much longer gap (e.g. 60 s) and only for the visible
     screen (`refetchType: 'active'`). Never refetch inactive heavy queries.
  2. Backend: make the generation per workspace (`bump(workspace_id)`), so importing into
     workspace 2 does not drop workspace 1's caches. `workspaces.py:243` and the rebuild keep a
     global bump.
  3. Later: an append-only generation. Auto-import only appends hands, so a cached resolution can
     be extended with the delta (`hand_players.id > top`, which `data_version` already reads at
     `chain.py:785`) instead of being recomputed. The delta needs a per-hand compute plus a merge
     in `played_at` order.
- **Expected gain:** removes a repeat of every open report's compute every ≥5 s during play. Light
  screens stay live.
- **Effort:** S for steps 1 and 2, M for step 3.
- **Parity risk:** none for 1 and 2. For 3, low: per-hand records are independent. Test that a
  merged resolution equals a fresh one.

### F2 — DECIMAL columns are materialized as Python `Decimal` on every per-hand fetch (P1)

- **Where:** schema `backend/app/db.py:232-233, 250-260, 320` (`stack`, `won`, `won_bb`, `rake`,
  `rake_bb`, `jackpot*`, `all_in_ev_bb`, `sb_amount`, `bb_amount` are `DECIMAL` = DECIMAL(18,3)).
  Hot readers: `backend/app/reports/chain.py:571-602` (`_COLS` has 8 DECIMAL expressions, then
  `float()` per value in `_rec`), `backend/app/api/reports.py:45-110` (Graph), and the sessions,
  stats and population row fetches (95 `fetchall()` sites).
- **What happens:** DuckDB converts each DECIMAL value into a `decimal.Decimal` object (~104 B, slow
  constructor). The code then turns it into a `float` straight away.
- **Evidence (214k, graph-like 7-column fetch, 214k rows):** `fetchall()` takes 777 ms. With
  `::DOUBLE` casts in SQL plus `epoch(played_at)` it takes 124 ms. `fetchnumpy()` takes 69 ms. The
  same ratio holds at 20k (69 ms vs 13 ms). The SQL itself takes 19.5 ms. So >95% of the fetch is
  Python object creation.
- **Proposal:** (a) for per-row fetches feeding Python math, cast in SQL
  (`COALESCE(hp.won_bb,0)::DOUBLE`). Keep the conversions in a shared helper in `chain.py`, so
  `_COLS` and the Graph query pick it up. (b) For pure numeric pipelines (Graph cumulative sums,
  variance, session splits), fetch columnar with `fetchnumpy()` and compute vectorised (numpy is
  already a dependency through pyarrow). (c) Never select more columns than needed: 107-column
  rows cost 6.5× more than 10-column rows (2.3 s vs 0.36 s at 214k).
- **Expected gain:** 5–6× on the fetch part of every per-hand endpoint. About 80 B less per value
  while rows are alive (peak RAM).
- **Effort:** S for (a) and (c), M for (b).
- **Parity risk:** low. Values are already converted with `float()`, and DOUBLE from DECIMAL(18,3)
  gives the same float. Keep every `SUM`/`AVG` over money in SQL on DECIMAL, then cast the result.
  Changing the stored type to DOUBLE is **not** proposed: it would change summed money and the money
  invariants.

### F3 — 14 non-unique ART indexes cost space and write time and buy nothing (P1)

- **Where:** `backend/app/db.py:482-497` and `1074-1088` (rebuilt by `_create_indexes`,
  `backend/app/api/import_hands.py:78-87`, after each bulk load). `hand_players` has 6 indexes,
  `hands` 6, plus `actions` (the table is empty) and `board_cards`.
- **What happens:** DuckDB uses ART indexes only for highly selective point lookups. Analytical
  joins and filters use hash joins and zonemaps. `EXPLAIN ANALYZE` of the hero join at 214k shows
  sequential scans and a hash join (18.5 ms).
- **Evidence (20k copy, all 14 non-unique indexes dropped and checkpointed):**
  - Used blocks: 259 → 139 (−46%).
  - Point lookups do not change: hand_players by hand_id 1.66 → 1.57 ms, hands by id 0.76 → 0.77,
    50-id IN list 1.46 → 1.47, hero last 100 hands 2.27 → 2.53. Only board_cards by hand_id got
    slower, 0.12 → 0.45 ms.
  - Insert 20k `hand_players` rows plus checkpoint: 262 → 104 ms.
  - Delete 20k rows plus checkpoint: **213 → 8 ms**.
  - Every write commit and CHECKPOINT must also keep the ARTs in memory and serialize them.
- **Proposal:** drop the non-unique indexes (`idx_hp_*`, `idx_hands_*`, `idx_h_played_stakes`,
  `idx_actions_hand_id`, `idx_board_cards_hand_id`, `idx_hand_tags_*`). Keep the unique ones
  (`uq_hands_workspace_id`, `uq_hand_tags`, `uq_hand_notes`), which enforce correctness. Do it as a
  one-time migration flag in `init_schema`, and remove them from `_BULK_INDEXES`. If board_cards
  lookups matter, keep `idx_board_cards_hand_id` alone (0.3 ms). Optional: write hands in
  `(workspace_id, played_at)` order during the bulk load, so zonemaps prune date filters.
- **Expected gain:** estimated 300–450 MB less file at 214k. Auto-import ticks and deletes are
  2.5–26× cheaper on the index part. The bulk import skips the index rebuild (report 06 measures
  `index_ms`).
- **Effort:** S.
- **Parity risk:** none.

### F4 — CPU-heavy sync handlers share a 40-thread pool, fight over the GIL, and are never cancelled (P1)

- **Where:** every report and stat endpoint is a sync `def` (no `async` in `api/reports*.py`,
  `general*.py`, `sessions.py`, `stats.py`). Starlette runs them in anyio's default 40-token
  threadpool. Aborts happen client-side only: `frontend/src/lib/api.ts` passes `signal` in only ~8
  of ~70 `queryFn`s. Even where it does, the backend thread keeps running. `chain.py:799-812`
  deduplicates identical in-flight keys, but different keys (filter clicks) all run.
- **What happens:** DuckDB releases the GIL during `execute`, but row materialization and all
  per-hand Python (spots, replays, graph points) hold it. N concurrent heavy requests therefore
  take ≥N× as long each, plus switching overhead, and each holds its own working set.
- **Evidence:** 3 Graph requests at 20k: 1,085 ms back to back, **1,703 ms** when started in
  parallel (10 cores). The lead's profile showed 3 Python threads competing for the GIL on Reports.
- **Proposal:**
  1. A process-wide `anyio.CapacityLimiter(2)` (or a `threading.BoundedSemaphore`) around the heavy
     handlers. Light endpoints (health, config, workspaces, hand detail) keep the normal pool, so
     the UI stays responsive.
  2. Superseding: the frontend sends a stable "slot" header per screen (e.g. `X-OHM-Slot:
     reports-graph`). The backend keeps `slot → cancel Event`, a new request sets the old event,
     and the long loops (resolve batches, replay chunks, graph loop) check it every few thousand
     hands. This is the same pattern the import already uses (`cancel.is_set()` in
     `import_hands.py:668-674`).
  3. Pass `signal` in every heavy `queryFn`, so the browser drops superseded responses and does
     not parse them.
- **Expected gain:** at most 2 heavy computations at once. Superseded work stops within one batch.
  Peak memory falls with concurrency (each resolution needs ~40 MB peak per 20k hands under
  tracemalloc).
- **Effort:** M.
- **Parity risk:** none.

### F5 — Caches are bounded by entries, not bytes, and their combined worst case is ~1 GB+ (P1)

- **Where / bounds:**
  - `backend/app/reports/chain.py:765`: `_CACHE = _LRU(32, 600_000)`, ≤32 resolutions and ≤600k
    `HandRec`s in total. Measured retained size: 940 B per hand (empty chain), 1.6–1.9 KB with spot
    plus `blobs` (`h2n_seq` bytes kept per resolution, `chain.py:557`). Worst case ≈ 0.55–1.1 GB
    (estimate), plus `Resolution.tables` derived tables (unbounded per entry, not measured).
  - `backend/app/api/general_popup.py:713`: `_RECORDS = _LRU(300_000)`, keyed
    `(ws, hid, username, row)`, holding a frozen `_Rec` with nested tuples. Estimated 300–600 B
    each, so 90–180 MB (not measured: the measurement script was stopped, see §5). The key has no
    data generation, so a rebuild that changes parser output does not invalidate it. Only
    `clear_cache()` does.
  - `backend/app/h2n/__init__.py:78-79`: `_SHAPES` ≤100k entries (import time, cleared all at
    once). Size per entry not measured.
  - `hand_value.py:103,450` and `reports/spots.py:120,129` `lru_cache(maxsize=None)`: keys are
    13-bit rank masks or the DSL vocabulary, so they are naturally bounded (≤8,192 entries). Fine.
    `heroes.py:28`: one entry per workspace. Fine.
- **Why it matters:** CPython's small-object allocator rarely returns arenas once they are
  fragmented. Each eviction keeps the RSS at its high-water mark, and swapping starts on a 16 GB
  machine. Under F1 every generation bump orphans whole resolutions, which stay until they are
  pushed out.
- **Proposal:** one byte budget shared by all three caches. Use `len(hands) × measured bytes per
  record` plus `sum(len(blob))`, default e.g. 256 MB, configurable in `app_settings`. Purge entries
  with a stale generation proactively on bump, instead of waiting for LRU pressure. Store blobs
  once per (ws, hand), not per resolution. Longer term, store `HandRec` columns as numpy or array
  columns (one object per resolution instead of one per hand), which cuts the per-hand overhead
  ~5–10× (estimate).
- **Expected gain:** predictable RSS ceiling (estimate: −0.5 to −1 GB worst case at 214k).
- **Effort:** S for the byte budget and stale purge, L for columnar records.
- **Parity risk:** none. Only cache residency changes.

### F6 — Startup does 53 catalog probes, one per column (P3)

- **Where:** `backend/app/db.py:182-195` `_add_column_if_missing`, called for ~36 legacy columns
  plus every `H2N_COLUMNS` entry (`db.py:449-467`), plus a few other tables.
- **Evidence:** the 53 probes take 366–420 ms of a 390–450 ms `get_db()` (20k). At 214k one probe
  takes 4.2 ms, and listing all columns once takes 0.5 ms. The per-start UPDATEs (`db.py:470-480`
  game_mode backfill), the sequence resync `MAX(id)` and the `COUNT(*)` all stay ≈1 ms at 214k
  thanks to zonemaps. They are not a problem.
- **Proposal:** read `duckdb_columns()` once per table into a set and check membership. Gate the
  whole migration block on a `schema_version` settings key, so a current DB skips it.
- **Gain:** ≈0.4 s off every app start and every `TestClient` start (the test suite runs it many
  times). **Effort:** S. **Parity risk:** none.

### F7 — Electron's health wait gives the backend ~15–75 s, then shows a hard error (P2)

- **Where:** `electron/main.js:104-138` `waitForBackend(url, maxRetries = 30)`: 30 attempts,
  500 ms apart, each with a 2 s timeout. `startBackend` resolves after a fixed 200 ms (`:100`).
  `backend/app/main.py:100-103` runs `get_db()` (connect, WAL replay, migrations,
  `_check_stat_version`) in the startup hook before uvicorn accepts connections. `/api/health`
  therefore only answers after all migrations have run.
- **What happens:** a cold PyInstaller start (import 0.65–0.77 s wall measured, plus unpacking),
  a large WAL replay, a lock retry (`db.py:86-91`, up to 9 s), or a one-time heavy migration (e.g.
  `_migrate_config_sections` → `batch_update_player_types`) on a slow, swapping machine can go past
  ~15 s of failed connects. The user then sees "Backend did not start in time" and the app quits.
  The window is not created until the backend is ready, so the user sees nothing during that time.
- **Proposal:** create the window right away with a local splash page (or `backgroundColor` plus a
  loading view). Wait on a readiness line from the backend's stdout (`Uvicorn running on`) or on a
  `/api/health` that answers during migrations (run `get_db()` in a background thread, return
  `{"status":"starting"}` until done). Raise the budget to minutes, with progress text.
- **Gain:** removes a failure mode on large DBs. Perceived startup becomes instant. **Effort:** S–M.
  **Parity risk:** none.

### F8 — The DB file never shrinks: 77% of the 214k file is free blocks (P2)

- **Where:** bulk loads drop and recreate all indexes (`import_hands.py:78-87, 153, 927`).
  Rebuilds delete and re-insert, and workspace deletes free space. Nothing ever compacts.
- **Evidence:** 214k DB is 2.9 GiB, with 9,382 of 12,098 blocks free. That leaves ≈680 MB used, of
  which ≈228 MB is table data.
- **Proposal:** F3 removes most of the churn. Add a "Compact database" action on the Databases page
  (`EXPORT DATABASE` / `ATTACH` + `COPY FROM DATABASE` into a new file, then swap under the write
  lock). Show used vs file size from `pragma_database_size()` in `/api/system/info`
  (`api/config.py:75-84` currently reports only the file size).
- **Gain:** ~2.2 GB disk at 214k. Cold-cache reads also improve (less scattered blocks).
  **Effort:** M. **Parity risk:** none.

### F9 — Workspace delete binds one placeholder per hand and is not transactional (P2)

- **Where:** `backend/app/api/workspaces.py:182-215`. It builds `hand_id IN (?,?,…)` with one
  parameter per hand for 5 tables. The child tables already carry `workspace_id`
  (`db.py:727-755`).
- **Evidence (20k copy, inside a rolled-back transaction):** 5,000 placeholders: 579 ms wall /
  2.3 s CPU. 20,000: 121 ms (DuckDB switches strategy). `WHERE workspace_id = ?` alone: 1 ms. At
  200k+ parameters, the SQL text and binder cost are not measured but are clearly wasted. A failure
  halfway leaves orphan rows, because there is no `BEGIN`/`COMMIT`.
- **Proposal:** `DELETE FROM <child> WHERE workspace_id = ?` for each table, inside one
  transaction, then `CHECKPOINT`. **Gain:** O(1) SQL, atomic. **Effort:** S. **Parity risk:** none.

### F10 — Middleware, serialization and request plumbing (P3)

- `CursorCleanupMiddleware` (`backend/app/main.py:61-71`) is a `BaseHTTPMiddleware`. It routes
  every response body through an anyio memory stream and adds a task per request. For
  `StreamingResponse` (NDJSON import), its `finally` runs as soon as headers are sent, so cursors
  opened later by the generator land in an already-cleared list and are never closed (they are
  only freed at GC). Proposal: a pure ASGI middleware (≈15 lines) that cleans up after
  `http.response.body` with `more_body=False`. Effort S, no parity risk.
- Serialization is **not** a bottleneck on the installed FastAPI 0.162. With a `response_model` or
  return annotation it uses the Pydantic-core `dump_json` fast path (`fastapi/routing.py:758-780`):
  24.5 ms for the 8.1 MB Graph, against 462 ms for the old `jsonable_encoder` path.
  `requirements.txt` only pins `fastapi>=0.115`, and older versions take the slow path. Pin a
  version that has the fast path (or set `default_response_class=ORJSONResponse` and add orjson).
  Otherwise a CI build could silently pay ~20× on large payloads. Response re-validation
  (`field.validate`) is cheap for model instances. `-> dict` endpoints (`reports_lite.py`,
  `sessions.py`) validate only a shallow `dict`.
- No GZip middleware. That is correct for loopback (Electron and Vite proxy). Do not add it: it
  would cost ~100+ ms of CPU per 8 MB for no transfer gain.
- `chain.data_version` (`chain.py:781-788`) issues 2 queries on every resolve, about 1 ms each at
  214k. Once F1's per-workspace generation exists, the generation alone is enough.
- Health (`main.py:126-157`): 1.4 ms, polled only during a rebuild (`ImportContext.tsx:127-152`).
  Fine.

### F11 — One 1.6 MB JS chunk, no route-level code splitting (P3)

- **Where:** `frontend/src/App.tsx:13-28` imports every page eagerly, including `DesignPage` and
  the demo pages. `frontend/vite.config.ts` has no `manualChunks`.
- **Evidence:** one `index-*.js` of 1,616 KB (475 KB gzip). By source share (sourcemap): app
  components 16.7%, recharts 13.5% (+ redux toolkit / immer / react-redux / decimal.js-light /
  d3 ≈ 6%), react-dom 11%, react-router 7.2%, date-fns 4.5%, react-day-picker 3.2%, tanstack
  table/virtual/query ≈ 6%, fflate 1.8%.
- **Proposal:** `React.lazy` per route (Reports, Statistics, Sessions, Extras, Design, Databases,
  Configuration), and lazy-load the chart and replayer components. Electron loads from loopback, so
  the gain is parse and compile time only: estimated 50–150 ms off first paint on a slow machine.
  Low priority. **Effort:** S. **Parity risk:** none.

### F12 — Frontend cache keeps large payloads for 10 min, and DuckDB gets 4 GB (P2/P3)

- `frontend/src/lib/query-client.ts:3-12`: `staleTime` 2 min, `gcTime` 10 min,
  `refetchOnWindowFocus: false`, `retry: 1` (sensible defaults). But the Graph response is 8 MB at
  20k and 89 MB at 214k (report 02). Each filter combination stays in the renderer heap for
  10 minutes after the user leaves it, and that is parsed JS objects, several times the JSON size.
  Proposal: `gcTime: 30_000` (or `0`) on the heavy report keys, plus server-side downsampling
  (report 02). `retry: 1` on a 43 s request that fails by timeout doubles the cost. Use `retry: 0`
  for heavy POSTs. Effort S, no parity risk.
- Polling: auto-import status every 2 s (1 ms server-side, fine on its own; the cost is F1),
  `AutoImportSection.tsx:58` every 5 s, sessions live every 60 s (4.5 ms), `useDayStart` 60 s
  timer. No issue apart from F1.
- `backend/app/db.py:47` `SET memory_limit = '4GB'`. DuckDB's measured buffer use at 214k after
  scanning everything was only 192 MB, so DuckDB is not the source of the 11 GB. But the limit
  allows 4 GB of buffers and operator state (import transactions with `checkpoint_threshold =
  '10GB'`, `import_hands.py:155`) on top of the Python heap. Proposal: 1.5–2 GB, an explicit
  `temp_directory` under the data dir so spills go to disk instead of RAM, and `threads` capped at
  e.g. 4. Background DuckDB work should not starve the GIL-bound Python threads. Effort S, no
  parity risk.

### Considered and not proposed: a persisted per-(player, day, stakes) rollup layer

The General screen (`backend/app/api/general.py:86-110`) already aggregates its 64-bit opportunity
and case masks in SQL. That is about 20 ms of scanning at 214k and does not need a rollup. The
expensive screens are the ones that need per-hand Python state: chain or spot resolution, popup
replays, graph points, sessions. A rollup cannot serve those, because chains filter on per-hand
action lines. A per-(player, ws, hour, stakes, mode, pos) rollup would shrink General and Stats
input ~10× (estimate). It would add a second source of truth that must stay exact against
H2N parity, plus invalidation on rebuild and on `day_start_hour`. The fixes worth doing are F2
(cheaper per-hand fetch), F5 (columnar cached records) and F1 (incremental append). Revisit rollups
only if 1M-hand General latency becomes a problem.

## 4. Quick wins vs. larger refactors

**Quick wins (≤1 day each):** F1 steps 1 and 2 (scoped invalidation, per-workspace generation),
F2(a)(c) (`::DOUBLE` casts, narrow selects), F3 (drop indexes), F6 (one column probe per table),
F9 (workspace delete), F10 (ASGI middleware, pin FastAPI), F12 (`gcTime`/`retry` for heavy keys,
DuckDB limits), F11 (route `lazy()`).

**Larger refactors:** F4 (heavy-request limiter plus cooperative cancellation by slot), F5 (byte
budget, then columnar `HandRec` storage), F1 step 3 (append-only incremental resolutions), F2(b)
(numpy pipelines for Graph and sessions), F7 (splash plus async readiness), F8 (compact database
action).

## 5. Open questions / not measured

- **Popup `_RECORDS` bytes per entry.** The measurement script was stopped (the lead killed a
  related tracemalloc run that held the bench lock too long, and the follow-up script picked a
  non-existent postflop row). The 300–600 B estimate is unmeasured. Measure with `sys.getsizeof`
  on ~1,000 records.
- **The P01 spot-chain resolve timing (3.4 s at 20k)** was taken under tracemalloc, so it is
  inflated. Use report 01's numbers for resolve time.
- **The chain `_COLS` Decimal vs DOUBLE comparison** (local scratch scripts) was pruned
  before it ran. The F2 gain is inferred from the graph-like query with the same column types.
- **Not measured:** PyInstaller cold-start time (no packaged build here), Electron window
  time-to-first-paint, and renderer heap for the 89 MB Graph payload.
- **Not measured on a 214k copy:** startup migrations, ART index size and insert/delete cost (the
  rules allow only read-only access there). The 214k figures are extrapolated from the 20k copy and
  block counts.
- **Not tested:** whether DuckDB 1.4's lazy index loading keeps ARTs out of memory until the first
  write, which affects how much RSS F3 saves on a read-only session.
- **To confirm:** whether `field.validate` on `-> dict` endpoints with very large nested payloads
  (Split tables) is shallow in practice (believed shallow).
