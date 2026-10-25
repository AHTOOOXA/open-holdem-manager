# Performance due diligence: summary

This summary combines the eight reports in this folder (see [README](README.md)). Finding IDs are
written `report/ID`: `01/F1` is finding F1 in `01-reports-stats-split.md`.

## What triggered the review

The user had a 214k-hand DB, and the dev backend sat at **11 GB** (peak 12 GB) after an import.
The Mac (16 GB RAM, 20 GB swap almost full) swapped so hard that the Reports page took minutes.
The Graph tab measured **43 s and 89 MB** on that backend.

Re-measured without swap, the real costs are smaller but still bad at 214k:

| Request (214k hands, no swap) | Today | Main cause |
|---|---|---|
| Reports page 0, cold (empty filter) | ~2.8 s CPU, +200–640 MB | one Python record per hand (01/F1, 02/G2) |
| Graph tab, cold | ~6.5 s, 89 MB JSON | one 14-field object per hand; the chart draws 1,000 points (02/G1) |
| Next Actions tab, page 0 | 5.0 s | every stored sequence decoded (01/F5, 01/F8) |
| Statistics: VPIP popup | 7.7 s cold, 1.4 s warm | replay + a cache smaller than one cell (04/F1, 04/F3) |
| Hands tab page / sort | ~0.35 s | 214k ids bound into SQL twice (03/F1) |
| Export (100k hands) | 7.1 s | 200 batches, each scanning `hands` (03/F2) |
| General grid, Sessions, Extras | 50–350 ms | fine |

## The 11 GB: what we know

- **It is not DuckDB.** DuckDB used about 192 MB at 214k (08/F12). About 9.2 GB sat in CPython
  small-object arenas: at one point about 9 GB of small Python objects were alive at once.
- **The import writer is ruled out (high confidence).** It stays flat: arena high-water 125–147 MB
  at 20k–60k, and per-batch objects are freed (06).
- **Most likely cause (medium confidence): read-side caches after the import.**
  - Every import path calls `data_generation.bump()` (`backend/app/api/import_hands.py:447`, `:474`,
    `:1185`, `:1347`, `:1419`), not `reports.chain.bump_generation()`, which also clears the cache.
    The old cached resolutions therefore stay in memory until enough new entries push them out.
  - The cache is bounded by hand-record count (`reports/chain.py:765`, 600k records ≈ 0.55–1.1 GB).
    Blobs and derived tables are not counted at all (01/F3, 01/F7).
  - The popup cache (`api/general_popup.py:713`, 300k records) is never cleared outside tests (04/F2).
  - After an import the UI refetches every open screen at once, so several cold 214k resolutions
    build in parallel.
  - CPython keeps the arenas after a peak (fragmentation). A 20k simulation of 4 import rounds
    (06/F1) went from 51 to 275 arenas.
- **Not reproduced at 9 GB.** To confirm next time it happens: add a debug endpoint that returns
  `sys._debugmallocstats()` and the cache sizes. If live bytes are close to the arena total, a cache
  or leak holds them. If live bytes are far below it, the memory is fragmentation.

## Cross-cutting themes

1. **Plain filters are turned into one Python object per hand.**
   - The default empty filter and every filter without spot steps build 214k `HandRec`s, then loop
     over them in Python. Hand ids are then passed back to SQL as a 214k-element list.
   - Three reports reached this independently (01/F1, 02/G2, 03/F1).
   - SQL aggregates do the same work in 22–25 ms, and passing the SQL condition instead of ids takes
     12–29 ms.
2. **Responses carry far more than the screen shows.** Graph sends 214k points and draws 1,000
   (02/G1). Session graphs and splits run to several MB at full float precision (05/S3, 05/S4).
   Hand-list rows carry detail-only fields (03/F8).
3. **Money values come back as `Decimal`.** Converting them is over 95% of every per-hand fetch:
   777 ms vs 124 ms with `::DOUBLE` at 214k. All 214,188 values were checked identical
   (01/F4, 08/F2). SQL `SUM`s stay on DECIMAL.
4. **Caches are bounded by count, not bytes, and miss invalidations.**
   - Stale entries survive imports (06/F1).
   - The popup cache is never released (04/F2).
   - One Reports entry can exceed the budget and is never evicted (01/F7).
   - The worst case is about 1 GB+ (08/F5), and Python doesn't return freed memory to the OS.
5. **Refetch storms, no cancellation, GIL contention.**
   - Auto-import marks every query stale on every tick (08/F1, 05/S1); an import invalidates everything.
   - Marking a hand refetches every hand list (03/F6); popups go stale after 60 s (04/F8).
   - Only about 8 of 70 queries can be cancelled, and the backend keeps computing after the browser
     gives up (03/F4, 08/F4).
   - Parallel CPU-heavy handlers share one GIL: 3 Graph requests take 1.7 s in parallel vs 1.09 s
     one after another.
6. **The same work is repeated.**
   - Each sequence is decoded up to 4× per page (01/F5).
   - Postflop popups re-parse `raw_text` although the parsed sequence is stored (04/F4).
   - Warm requests recompute `spot()` and the splits (01/F2); COUNT runs on every page (03/F3).
7. **Import and storage.**
   - 14 indexes no query uses. Dropping them shrinks used storage by 46%, makes inserts 2.5× and
     deletes ~25× faster (08/F3).
   - Player-id lookup is 31% of import CPU (06/F3). Monte Carlo equity dominates the money step (06/F2).
   - Import and rebuild use one core (06/F5). Every import pays a fixed cost that grows with DB size
     (06/F6).
   - The 214k DB file is 77% free blocks (08/F8).

## Prioritized backlog

Gains are at 214k hands. Parity means Hand2Note-compatible numbers: "none" means results stay
bit-identical, "low" means a test should prove it.

| # | Change | Findings | Gain | Effort | Parity |
|---|---|---|---|---|---|
| 1 | Clear Reports and popup caches when data changes (import, rebuild, workspace delete); bound caches by bytes | 06/F1, 04/F2, 01/F7, 08/F5 | stops the per-import memory ratchet (est. 0.5–1 GB+ per import) | S | none |
| 2 | Graph: send only the drawn points (~1,000 + last); variance, CI and sessions still over all hands; frontend uses `hand_number`, not `points.length` | 02/G1, 02/G3, 05/S3 | 3.7 s → 72 ms, 89 MB → 0.48 MB | S | none (checked point for point) |
| 3 | Cast per-row money to DOUBLE in SELECTs | 01/F4, 08/F2 | 1.7–1.9 s → 0.4–0.6 s per resolve | XS | none (all rows checked) |
| 4 | Cache finished `spot` / split responses on the resolution | 01/F2, 02/G4 | warm refetch 0.45–0.68 s → <1 ms | XS | none |
| 5 | Plain filters: aggregate in SQL; pass hand lists and graph a SQL condition, not an id list | 01/F1, 02/G2, 03/F1, 01/F6 | cold page 0 ~2.8 s → ~0.05 s; −200 MB per cached filter | M (2–3 d) | low (money last digit only) |
| 6 | Auto-import: refresh only cheap queries, show a "new hands" chip on heavy screens; per-workspace generation | 08/F1, 05/S1 | ends recompute loops while playing | S–M | none |
| 7 | Cancel stale requests (AbortSignal + server-side check between batches); limit heavy endpoints to ~2 at once | 03/F4, 08/F4, 01/F10 | no orphaned work; no GIL pile-ups | M | none |
| 8 | Export: one streaming ordered query | 03/F2 | 7.1 s → ~0.5 s | S | none |
| 9 | Fill Next / Faced tables inside the resolve loop (decode once) | 01/F5 | −0.7 to −2 s per spot page | S | none |
| 10 | Popup: cache sized to the working set; summary counts in SQL; stored sequences for postflop | 04/F1, 04/F3, 04/F4 | warm 1.4 s → ~0.4 s; cold postflop ~4× | S–M | low–medium (F4 needs a test) |
| 11 | Drop the 14 unused indexes; optional VACUUM / compaction | 08/F3, 08/F8, 06/F6 | −46% used storage; inserts 2.5× faster | S | none |
| 12 | Import: single Arrow join for player ids; memoize equity | 06/F3, 06/F2 | about −35% import time | S | none |
| 13 | Narrower invalidations: mark/unmark, tag edits, popup stale time | 03/F6, 04/F8 | −0.35 s to −8 s per action | XS | none |
| 14 | Extras: cache population aggregates; group-first Players query; batch identities | 07/F1, 07/F2, 07/F5 | 0.2–2.4 s → ms | S | none |
| 15 | Hands list: count from case ids; drop the dead `actions` query; trim row payload | 03/F3, 03/F5, 03/F8 | 5–80 ms per page | S | none |
| 16 | Process pool for parse and compute in import and rebuild | 06/F5, 06/F8 | est. 2–4× import / rebuild | M–L | low |
| 17 | Frontend bundle: lazy routes; shorter retention for big payloads | 08/F11, 08/F12 | faster first paint, less renderer heap | S | none |
| 18 | Electron: show a window while the backend starts; longer, softer health wait | 08/F7 | no hard error on slow first start | S | none |

Items 1–4 are each a few hours and together cover most of what the user hit. Item 5 is the
structural fix that makes Reports fast at 1M hands.

## Corrections to the first diagnosis

- The 43 s Graph was mostly swap. Without swap, a cold request takes ~6.5 s (02).
- FastAPI does not validate the response twice on the installed 0.162 (02/G6). The cost seen in the
  first profile came from the profiling script itself. Pin `fastapi>=0.162`: older versions encode
  ~20× slower (08/F10).
- "The Players split takes ~2 s at 20k" is the Reports Players split (`reports/split.py`), not the
  Extras Players page (07).

## Non-performance issues found along the way

- Stat detail (Extras) drops `last_n` from the URL, and its hand list ignores `game_mode`, so it can
  show a different sample than the cell (07).
- About 18 dead Population / stat-detail endpoints apply filters only to the player filter. They
  would return wrong numbers if anything called them (07/F10). `RangePage` is unused (02).
- Graph session markers use a 10-min gap between hands; the Sessions page uses the Hand2Note rule
  (282 vs 250 sessions at 214k) (05).
- Workspace delete is not transactional (08/F9). The cursor-cleanup middleware leaks cursors on
  streaming responses (08/F10).
- The `actions` table is never written (03/F5).

## Not measured anywhere

- A 9 GB reproduction of the import incident.
- Browser render time and renderer heap in the real app (no app was started).
- PT4 / HM3 import and zip uploads; PyInstaller cold start.
- 1M-hand figures (all linear extrapolations).
- Benchmark scripts and raw outputs were kept locally (not committed).
