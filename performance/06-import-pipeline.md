# 06: Import pipeline, rebuild, import memory growth

Scope: `POST /api/import/files/stream` (upload, zip, split, dedup, parse, flags/H2N/equity, batched
Arrow insert), Hand2Note 4 DB import (`/api/import/h2n`), PT4/HM3 import (`/api/import/tracker`),
auto-import, stat rebuild (STAT_VERSION + user-triggered), `finalize_import`, index drop/recreate,
checkpointing, frontend progress. All numbers are from this machine (16 GB Mac, swapping, other
agents' benchmarks queued behind one lock), Python 3.12.12, DuckDB 1.4.4, pyarrow 23 (mimalloc).
Benchmark scripts were kept locally (not committed).

## 1. Summary

**The 11 GB is not the import writer.** I measured the import pipeline at 20k and 60k hands
(with player names rewritten so the player cache grows). Its Python small-object heap reaches a
high-water mark of 125 to 147 obmalloc arenas (about 125 to 150 MB). It grows only with the number
of distinct players, and nearly all of it is freed per batch. The ~9,200 one-MB untagged
VM_ALLOCATE regions the lead saw are CPython obmalloc arenas (checked: DuckDB memory shows up as
`MALLOC_MEDIUM` and Python small objects as 1 MB `VM_ALLOCATE`, section 2.3). Arenas are only
created when the heap needs them, so at some point about 9 GB of small Python objects were alive
at once. No import path can hold that much at 214k hands (estimated at most ~250 to 400 MB, section
2.2). The most likely cause, with medium confidence, is the **read side after an import**:
- every import (and every auto-import tick) bumps the data generation;
- the UI then calls `invalidateQueries()` and every open screen refetches at once;
- each refetch builds new report resolutions while the old ones stay in the LRU, which is not evicted.

At 20k I measured +44 MB of live heap kept per import+refetch round, ratcheting with each round,
plus fragmentation that keeps arenas allocated after the cache is cleared (finding F1). Reports 01
and 08 measure those caches at 214k.

Changes worth doing first:

| # | Change | Expected gain | Effort | Parity risk |
|---|---|---|---|---|
| F1 | Evict reports/popup caches when the data generation moves (import, auto-import tick, rebuild) instead of leaving stale entries in the LRU | Stops the per-import memory ratchet (20k: 230 → 54 MB live after 4 rounds; est. 0.5–1 GB+ at 214k) | S | none |
| F3 | Resolve player ids with one Arrow join instead of 500-placeholder `IN` lists | −4.4 s of 14 s CPU at 20k (31 % of import CPU); est. −45 s at 214k | S | none |
| F2 | Memoise the 3+-way preflop Monte Carlo equity (100k samples, 360 ms per hand) | −1.45 s of 2.5 s money time at 20k (4 hands!); est. −15 s at 214k import and again on every rebuild | S | none (same function, same seed) |
| F6 | Don't drop and recreate all 14 indexes, or run workspace-wide finalize, for small imports into a large DB | 2,000 hands into a 62k DB: 1.45 s of 2.78 s is index + finalize; est. 5–6 s fixed per import at 214k, 20 s+ at 1M | S–M | none (indexes), low (finalize scoping) |
| F5 | Process pool for parse + flags + money + column building (the pipeline is GIL-bound: CPU ≈ wall) | 2–4× import and rebuild throughput (est.) | M–L | low |

## 2. Baseline

### 2.1 Throughput (file import, empty DB, fixture `bench_sample_20k.txt`)

| Run | Wall | CPU | Peak RSS | h/s | parse / stats / money / db / index (ms) |
|---|---|---|---|---|---|
| 20k | 13.9 s | 14.2 s | 470 MB (script holds 2 text copies) | 1,458 | 4,111 / 4,453 / 3,110 / 7,925 / 833 |
| 60k (ids + players rewritten) | 40.6 s | 43.0 s | 645 MB (script holds 4 copies) | 1,496 | 12,832 / 13,121 / 9,484 / 23,700 / 1,758 |
| 2,000 new into 62k DB | 2.78 s | — | — | 720 | 342 / 401 / 131 / 314 / **1,148** |
| Rebuild 20k | 13.5 s | 13.3 s | 528 MB (footprint peak 448 MB) | 1,480 | — |
| Rebuild 60k | 40.5 s | 41.2 s | 491 MB (footprint peak 620 MB) | 1,480 | — |

`db_ms` at 20k breaks down as follows (timers patched in from the script, `incr.py`):
- `_batch_resolve_players`: **4,429 ms**;
- the rest of `_build_batch_arrays`: ~2,000 ms;
- `_insert_arrays` (the DuckDB insert itself): 1,324 ms;
- `_existing_hand_ids`: 154 ms;
- `finalize_import`: 67 ms;
- `CHECKPOINT`: 23 ms.

Single-thread compute alone (no DB) runs at 1,975 h/s: parse 36 %, flags 37 %, money 27 % (`prof.py`).
Throughput is linear in import size. CPU time is about equal to wall time, so the "overlap" between
the parse thread and the DB thread (`import_hands.py:867`) buys almost nothing: both need the GIL.

Scaling estimates (linear, single-core):

| | 200k import | 1M import | 216k rebuild |
|---|---|---|---|
| Time | ~140 s | ~11–12 min | ~146 s |

A single upload is capped at 500 MB of text (`import_hands.py:496`), which is about 420k hands.
The fixed per-import cost (indexes + finalize) grows with DB size (F6).

### 2.2 Memory: what each import path holds

| Object | Lifetime | 20k measured | 214k (est.) |
|---|---|---|---|
| Upload bytes `files_data` + decoded `text_contents` + `split_hands` list + stripped copies (`import_hands.py:972-988`) | endpoint body, before the job starts | ~4 × 24 MB | **~4 × 256 MB ≈ 1 GB transient** (malloc, not obmalloc) |
| `all_hands` (closure of `_stream_import`'s lambda, `:771`) | whole job | 24 MB | 256 MB |
| H2N: `texts`, `by_parser`, `all_hands` (`import_h2n.py:52-67`) | whole job | — | 256 MB + list copies |
| `existing_ids` set (`:852`) | whole job | ~2 MB | ~20 MB |
| 2 in-flight batches (2 × 2,000 prepared hands + column lists + Arrow tables) | per batch | ~1.4 M obmalloc blocks ≈ 100 MB | same (constant) |
| `_player_cache` (`:44`, module level, **never cleared after an import**) | process | 62.5k entries ≈ 252k blocks | 262k players (lead's 214k DB) ≈ 65 MB |
| `h2n._SHAPES` (`h2n/__init__.py:78`) | process | 887 shapes, 2.6 MB (sub-linear: 304 @2.5k → 887 @20k) | < 10 MB |
| `hand_value` lru_caches | process | 1.3 MB | bounded (rank masks) |
| NDJSON queue (`:695`) | job | 10 lines | ~110 lines |
| DuckDB (`duckdb_memory()` after import / rebuild) | process | 34 MB / 32 MB | est. 300–550 MB (60k: 84 MB import, 159 MB peak during rebuild) |

obmalloc arenas (`sys._debugmallocstats`), as created vs at their high-water mark:

| | 20k import | 60k import (3.5× players) | 20k rebuild | 60k rebuild |
|---|---|---|---|---|
| Arenas | 125 | 147 | 121 | 145 |

All four are flat, not super-linear. After the 20k import and `gc.collect()`, the retained blocks
(+252k) are the player cache.

### 2.3 Which allocator shows up where (`regions.py`)

- A 1 GB in-memory DuckDB table adds only to `MALLOC_MEDIUM` (1.9 G virtual).
- 5 M small Python tuples add **720 `VM_ALLOCATE` regions of 1 MB** (CPython 3.12 obmalloc arenas, untagged `mmap`).
- pyarrow's mimalloc is negligible here.

So the lead's ~9.2 GB in 1 MB untagged regions is Python small objects (≤ 512 B: ints, floats,
tuples, short strings, small dicts and dataclass instances). Hand texts (~1.2 KB) are malloc
`MALLOC_SMALL`, and DuckDB is `MALLOC_MEDIUM` (the ~1.9 GB the lead saw).

### 2.4 The read side after an import (`post4.py`, 20k)

Each round is one "import": `data_generation.bump()` followed by 9 Reports/Graph/General/Hands
requests in parallel, as the UI's `invalidateQueries()` fires them:

| Round | Cache entries | Cached HandRecs | Live small-object MB | Arenas |
|---|---|---|---|---|
| start | 0 | 0 | 52 | 51 |
| 1 | 3 | 32k | 98 | 147 |
| 2 | 6 | 64k | 142 | 199 |
| 3 | 9 | 96k | 186 | 242 |
| 4 | 12 | 128k | 230 | 275 |
| `chain.clear_cache()` | 0 | 0 | **54** | **155** (fragmentation keeps 100 MB) |

Each round keeps ~1.4 KB of live heap per cached hand record, and stale entries stay. Scaled
×10.8, one round costs ~470 MB at 214k. The LRU is capped at 600k HandRecs, not bytes
(`reports/chain.py:765`), so the cap alone allows ~0.85 GB, plus derived `tables`, which are not
counted. Add the transient peak of several concurrent full-workspace requests (Graph at 20k: +56
arenas transient, est. 0.6 GB at 214k) and fragmentation that pins arenas behind long-lived cache
objects. That makes a multi-GB high-water mark after a few imports or auto-import ticks with
Reports open plausible. I could not reproduce 9 GB within the 3 GB / 3 min budget (section 5).

## 3. Findings

### F1 (P1): Stale read caches survive every import; the import triggers a refetch storm
- **Location**: `backend/app/api/import_hands.py:447` and `:474` (`finalize_import` / `light_finalize` call `data_generation.bump()` only); `backend/app/reports/chain.py:765` (`_CACHE = _LRU(32, 600_000)`), `:774` (`bump_generation` clears it, but import never calls that), `:781` (`data_version` puts the generation in the key); `frontend/src/contexts/ImportContext.tsx:181` (`queryClient.invalidateQueries()` after every import), `:143`, `:394`, `:412`.
- **What happens**: the new generation makes every cached resolution unreachable but not evicted. The UI refetches everything that is open, so new resolutions are added next to the stale ones. Eviction only happens at 32 entries or 600k hand records. Auto-import bumps the generation on every tick that imports hands (`light_finalize`), so a session with Reports open keeps re-filling the cache.
- **Evidence**: section 2.4. Live heap goes up +44 MB per round at 20k and drops back to baseline only on `clear_cache()`. Arenas stay at 155 vs 51, which is fragmentation.
- **Proposal**:
  - when the generation moves, evict entries from older generations (the `_LRU` could hold the generation and drop on mismatch), or just call `chain.clear_cache()` from `finalize_import` / `light_finalize` / rebuild;
  - do the same for `general_popup._RECORDS` (report 08);
  - bound the LRU by an estimated byte size (hands × ~1.4 KB + blob bytes) rather than by record count;
  - on the frontend, keep `invalidateQueries()` (it only refetches active queries), but consider staggering the heavy Reports queries.
- **Gain**: removes the per-import ratchet (est. 0.5–1 GB+ per import or tick at 214k). Lower peak, which also means less fragmentation.
- **Effort**: S. **Parity risk**: none (cache only).

### F2 (P1): 3+-way preflop Monte Carlo dominates the money step
- **Location**: `backend/app/equity.py:140-144` (100,000 `rng.sample` + `eval7.evaluate` per hand), called from `backend/app/money.py:814`.
- **Evidence** (`mc.py`): over 20k hands the money step is 2,500 ms, and 4 Monte Carlo calls take **1,450 ms** (362 ms each). The other 169 exact flop/turn calls take 125 ms, and the 155 heads-up preflop table lookups take 11 ms. In cProfile, `random.sample` + `_ranks` are the top non-parser entries.
- **Proposal**: the result depends only on (sorted hands, board, samples). The RNG is seeded from those inputs (`equity.py:140`), so the result can be memoised exactly. Options:
  - an in-process dict, which helps rebuild-after-import and re-imports;
  - a small DuckDB table `equity_cache(key, shares)` that survives restarts, so every STAT_VERSION rebuild reuses it.

  A faster sampler (numpy or eval7's C Monte Carlo) would change the numbers, which is a parity change. Don't do that.
- **Gain**: −1.4 s per 20k import (10 % of wall), est. −15 s at 214k. The same again on every rebuild once the cache is persistent.
- **Effort**: S. **Parity risk**: none if keyed on the exact inputs (bit-identical floats).

### F3 (P1): Player-id lookup with 500-placeholder `IN` lists is 31 % of import CPU
- **Location**: `backend/app/api/import_hands.py:219-228` (`_batch_resolve_players`).
- **What happens**: each 2,000-hand batch has thousands of new Rush & Cash names (hashed ids: 62.5k distinct in 20k hands, 262k in the lead's 214k DB). Each 500-name chunk is a fresh prepared statement with 501 Python parameters to bind and plan.
- **Evidence**: 10 calls take 4,429 ms wall / 4,545 ms CPU of the 7,753 ms `db_ms` (`incr.py`).
- **Proposal**: build `pa.table({"username": uncached})`, then run a single `SELECT p.username, p.id FROM players p JOIN pa_names n USING (username) WHERE p.site_id = ?`. Keep the id-assignment loop unchanged so new ids come out in the same order. Do the same for `_existing_hand_ids` (`:950`, 154 ms).
- **Gain**: est. −4 s per 20k import (~25–30 % wall), est. −45 s at 214k. Rebuild gets the same win: it calls this per batch, all names hit the DB, and `reset_import_cache()` runs first.
- **Effort**: S. **Parity risk**: none (same ids).

### F4 (P2): Column building is ~300 Python appends per player row on the main thread
- **Location**: `backend/app/api/import_hands.py:309-356`, in particular `for k in _STAT_FLAG_KEYS: hp_cols[k].append(ps[k])` with ~300 keys.
- **Evidence**: `_build_batch_arrays` takes 6,427 ms, of which 4,429 ms is F3, leaving ~2.0 s for 120k player rows × ~315 columns.
- **Proposal**: make one tuple per row with `operator.itemgetter(*_STAT_FLAG_KEYS)(ps)`, then transpose with `zip(*rows)`. Or better, build the rows inside `_parse_batch` (the worker), so only `player_id` / hp `id` are filled in the DB thread (pairs with F5).
- **Gain**: est. −1 to −1.5 s per 20k. **Effort**: S. **Parity risk**: none (same values and types; keep `float()` casts).

### F5 (P2): The pipeline is single-core (GIL)
- **Location**: `backend/app/api/import_hands.py:867` (`ThreadPoolExecutor(max_workers=1)`); rebuild has no overlap at all (`:1237-1271`).
- **Evidence**: CPU ≈ wall at both 20k and 60k (14.2 / 13.9 s, 43.0 / 40.6 s). Parse + flags + money is ~0.5 ms per hand of pure Python.
- **Proposal**: use a `ProcessPoolExecutor` (N = cores − 1) for `_parse_batch`, returning per-batch column data (lists or Arrow IPC bytes) with usernames instead of player ids. The DB thread resolves ids (F3), assigns hp ids and inserts. Each process keeps its own `_SHAPES` and Monte Carlo memo. Notes:
  - PyInstaller builds need `multiprocessing.freeze_support()` in `backend/run_server.py`;
  - macOS/Windows use spawn (~1–2 s of worker start-up), so use the pool only above ~5k hands.

  The same pool serves rebuild.
- **Gain**: est. 2–4× on a 4–8-core machine. Import is then bound by DuckDB insert + id resolution (~2.5 s per 20k after F3/F4): est. 20k in ~5 s, 214k in ~50 s.
- **Effort**: M–L. **Parity risk**: low. Same code runs in workers, and the Monte Carlo seed is per hand. Run the parity suites with the pool enabled.

### F6 (P2): Every import pays O(DB-size) index rebuild + finalize
- **Location**: `backend/app/api/import_hands.py:153` (`_drop_indexes` on every bulk import), `:927` (`_create_indexes` rebuilds all 14 indexes over all rows), `:452-462` (first/last seen over all `hand_players ⋈ hands`), `:463` (`batch_update_player_types` for the whole workspace).
- **Evidence**: 2,000 hands into a 62k DB took 2.78 s, of which `_create_indexes` was 1,148 ms and `finalize_import` 304 ms. On an empty DB the same index step is 688 ms for 20k.
- **Estimates**: ~4–5 s index + ~1 s finalize per import at 216k; 20 s+ at 1M, even for a 50-hand drag-and-drop.
- **Proposal**: drop indexes only when the new hands exceed a fraction of the table (e.g. > 25 % of existing hands or > 50k hands). Otherwise insert with indexes in place, as auto-import already does (`import_hand_texts`, `:996`). Scope the first/last-seen update to the players touched by this import (a temp table of player ids from the batches).
- **Gain**: small imports into a big DB become O(import) (est. 5–6 s saved per import at 216k).
- **Effort**: S (index threshold), M (finalize scoping).
- **Parity risk**: none for the index threshold. Low for scoping first/last seen (MIN/MAX of a touched player's hands is the same). Scoping classification needs care if the reg rule reads workspace-wide thresholds; keep it workspace-wide unless verified.

### F7 (P2): Uploads and H2N DBs are materialised whole before the job starts
- **Location**: `backend/app/api/import_hands.py:972-988` (`await f.read()` of every file, decode, `re.split` list, `.strip()` copies, `all_hands` kept by the `_stream_import` closure `:771`); `backend/app/api/import_h2n.py:52` (`texts = [t.strip() for t in iter_hand_texts(...)]` plus `by_parser` and the flattened copies).
- **What happens**: peak ≈ 4 × upload size before the first progress line (est. ~1 GB at 214k / 256 MB of text). Then 256 MB is held for the whole job. Hand2Note DBs, which can hold far more than the user's own hands, are fully loaded too.
- **Proposal**:
  - write uploads to a temp dir in 1 MB chunks, then feed `_stream_source` a lazy generator that opens one file at a time and yields `re.finditer`-split hands in 2k batches. The lazy-batch contract already exists and the tracker import uses it (`import_tracker.py:86-94`);
  - H2N: pass `iter_hand_texts` lazily with `total = count_hands()`. `_chunks` already starts a new chunk when the parser changes, so the grouping-by-parser step is unnecessary.
- **Gain**: est. −0.8 to −1 GB peak at 214k, and a faster first progress line. **Effort**: M. **Parity risk**: none. Dedup order is the same for the same file order. Keep the per-file `detect_parser(content[:500])`.

### F8 (P2): Rebuild loads every raw_text up front and runs serially
- **Location**: `backend/app/api/import_hands.py:1200` (`fetchall()` of `id, workspace_id, site_id, raw_text` for all hands), `:1235` (pre-slices all chunks), `:1244-1262` (parse on the lock-holding thread, no overlap).
- **Evidence**: rebuild runs at 1,480 h/s and is linear: 13.5 s for 20k, 40.5 s for 60k. Peak footprint is 448 MB (20k) and 620 MB (60k).
- **Estimates at 216k**: ~146 s and ~1.3 GB peak (256 MB raw text + DuckDB transaction state + batches), all inside one write transaction.
- **Proposal**: stream rows with `fetchmany(2000)` from a cursor (or keyset pages on `played_at, id`), and reuse the import pipeline: F2 cache, F3 join, F4 rows, F5 pool.
- **Gain**: est. 146 s → ~60 s single-process, ~25 s with the pool; −250 MB peak.
- **Effort**: M. **Parity risk**: none, as long as order stays `played_at, id`, which hp-id assignment depends on.

### F9 (P3): Parser tries regexes line by line
- **Location**: `backend/app/parsers/ggpoker.py:362` (`parse_hand_history`, 1.93 s of a 4.86 s profile).
- **Evidence**: `re.Pattern.match` is called 2.43 M times per 5k hands (~490 per hand), and `search` 619k times.
- **Proposal**: dispatch on a cheap prefix or keyword test (`": raises "`, `": calls "`, `"*** "`, `"Seat "`) before running the matching regex.
- **Gain**: est. 20–30 % of parse time (~1 s per 20k). **Effort**: M. **Parity risk**: medium (parser behaviour); the parser tests and parity suites must pass unchanged.

### F10 (P3): Module-level `_player_cache` lives forever
- **Location**: `backend/app/api/import_hands.py:44`. It is only reset on rollback, clear, restore and rebuild (`:128`).
- **Evidence**: 62.5k entries (~252k obmalloc blocks) remain after a 20k import; est. ~65 MB at 262k players. These long-lived small objects are allocated between per-batch temporaries, which pins arenas after the import (fragmentation).
- **Proposal**: call `reset_import_cache()` at the end of `work()`, after finalize. With F3 the next import re-resolves cheaply.
- **Gain**: ~65 MB at 214k and less arena pinning. **Effort**: S. **Parity risk**: none.

### Checked and not a problem
- `h2n._SHAPES`: 887 entries / 2.6 MB at 20k, sub-linear; the 100k limit is never near.
- The NDJSON queue: one line per 2,000 hands.
- `existing_ids`: ~20 MB at 214k, job-scoped.
- One transaction with `checkpoint_threshold = 10GB` (`:155`): DuckDB memory stayed at 84 MB after a 60k import and peaked at 159 MB during the 60k rebuild, well under the 4 GB `memory_limit`.
- Arrow/DuckDB copies: Python lists → Arrow (mimalloc) → DuckDB storage; one copy per batch, freed.
- Frontend: progress is one `setProgress` per 2,000 hands (`ImportContext.tsx:212`). `ImportOverlay.tsx` only mounts dialogs.

## 4. Quick wins vs. larger refactors

**Quick wins** (S, no parity risk):
- F1 cache eviction on generation change;
- F3 one-join player lookup (+ `_existing_hand_ids`);
- F2 Monte Carlo memo (in-process first, persisted table second);
- F6 index-drop threshold;
- F10 reset the player cache after a job;
- F4 itemgetter row building.

Together, est. 20k import 14 s → ~8 s; 2k into 214k → < 1.5 s; plus the memory ratchet removed.

**Larger refactors**:
- F5 process pool for parse/compute (import + rebuild);
- F7 streaming uploads / lazy H2N source;
- F8 streaming rebuild on the shared pipeline;
- F6 finalize scoping;
- F9 parser dispatch.

## 5. Open questions / not measured

- **I could not reproduce the 9.2 GB.** Measured import/rebuild heaps are flat at 20k–60k. The read-side ratchet (F1) is measured at 20k only, and its 214k size is extrapolated. To confirm, run the lead's 214k process with `sys._debugmallocstats()` exposed (e.g. a debug endpoint), or use `tracemalloc` started at launch with a snapshot when idle. `_debugmallocstats` gives arenas vs live bytes: live ≈ arenas means a cache or leak, live ≪ arenas means fragmentation. Reports 01 / 08 have per-resolution and popup-record sizes at 214k.
- How the user's 214k got in: the lead's copy (a copy of the 214k DB, read-only count) has 216,754 hands with 6 distinct `imported_at` values. The biggest are 171,826 (Feb 13) and 37,383 (Oct 24 21:38). So the recent event was probably a ~37k import, or a rebuild, into an ~180k DB, followed by browsing. Under that scenario the fixed costs of F6 and the cache ratchet of F1 matter more than raw import throughput.
- Not measured:
  - zip uploads (`_read_uploads` adds one decompressed copy per entry);
  - PT4/HM3 import (needs PostgreSQL; it already streams in batches, `importers/tracker_db.py:402`);
  - H2N import memory on a real H2N DB;
  - auto-import ticks at scale (8 MB per tick, no index drop; `light_finalize` bumps the generation each tick, see F1);
  - multiprocessing start-up cost in the PyInstaller build.
- With `tracemalloc` on, compute ran ~10× slower (165 s for 20k), so retention was measured with obmalloc stats and vmmap instead.
