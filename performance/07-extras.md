# 07 — OHM Extras: Stats, Compare, Cash Drop, Population, Players

Scope: `/extras/stats` (+ `/extras/stats/:statKey`), `/extras/compare`, `/extras/cash-drop`,
`/extras/population`, `/extras/players` (list, player profile, identity detail), and the
DriftPanel / LeakSummaryPanel on the Stats screen.

## 1. Summary

None of these screens is slow on its own, even at 214k hands. Without swap, the slowest call
is 350 ms wall time (Compare "vs Population"). The real cost is **CPU**. The population-wide
aggregates use 1.2–1.4 s of CPU per request at 214k because DuckDB spreads one query over all
cores. When the machine is swapping, or when several queries run at once, that CPU time turns
into wall time. Nothing is cached, so every page visit, filter change and Players page flip
pays it again. The "Players split ~2 s at 20k" the lead heard is not on this screen:
`/api/players` takes 77 ms at 20k and 211 ms at 214k. The Players *split* is in
`backend/app/reports/split.py` (report 01).

Changes worth doing first:

1. **Cache the population-wide results by data version** (Population full-stats/overview,
   Compare vs Population, Players list). Their results only change on import. The
   `data_version()` / `data_generation` pair already exists in `backend/app/reports/chain.py:781`.
   Expected gain: a repeat visit drops from 0.2–0.35 s wall / 0.7–1.4 s CPU at 214k to under 5 ms.
   Effort S–M. No parity risk.
2. **Players list: group `hand_players` first, then join** (`players.py:90-153`). Today it
   joins `players`, `hands` and `player_classifications` onto all 1.29M rows before grouping.
   Measured at 214k: count 57 → 5 ms, page 96 → 18 ms (about 7x less CPU). Effort S. No parity
   risk (the list uses OHM flags, not H2N cells).
3. **Population: skip the `eligible` CTE when it filters nothing, and drop the `hands` join
   when there is no hand-level filter** (`population.py:144-213`, `stats_engine.py:359-409`).
   The Population page always sends `min_hands=0` and Compare defaults to `min_hands=0`. Measured
   at 214k: full-stats 203 → 129 ms, overview 66 → 16 ms. Effort S. No parity risk.
4. **`/api/identities` N+1** (`identities.py:80-88`): 3 queries per identity, and one of them is a
   `COUNT(DISTINCT hand_id)` scan of `hand_players` (24 ms warm, 73 ms cold at 214k). That is about
   0.5 s for 20 identities and about 2.4 s for 100 (estimate). The Players page and the Population
   page both load it. Use one grouped query instead. Effort S. No parity risk.
5. **Stat detail hand page: two-phase fetch of `raw_text`** (`stats.py:282-292`). Measured at
   214k: 64 → 12 ms for 25 rows. The `per_page=1` header call on `/extras/stats/:statKey` gets the
   same gain. Effort XS. No parity risk.

## 2. Baseline

Method: `TestClient(app)` in-process. Each call is timed with `perf_counter` (wall) and
`getrusage` user+sys (CPU, which includes DuckDB worker threads). Runs were held under
`bench-lock`. Tables show the median of 3 runs at 20k and 2 runs at 214k. 20k = the shared
`bench_sample_20k` DB (118,842 `hand_players`, 62,524 players). 214k = a copy of the 214k DB,
opened read-only (216,754 hands, 1,286,048 `hand_players`, 262,328 players). Responses are JSON
bytes. The machine was swapping. The numbers below come from quiet locked runs, so they are the
real cost without swap.

| Screen | Endpoint | 20k wall / CPU | 214k wall / CPU | Payload (214k) |
|---|---|---|---|---|
| Stats | `/stats/hero` | 46 / 75 ms | 121 / 320 ms | 7.7 KB |
| Stats | `/reports/filter-options` | 11 / 14 | 36 / 92 | 0.1 KB |
| Stats | `/reports/drift` (runs at ≥ 20k hands) | 43 / 54 | 147 / 380 | 0.1 KB |
| Stats | `/workspaces/1/checkpoints` | 2 / 2 | 3 / 3 | 0.2 KB |
| Stat detail | `/stats/detail/vpip/hands?per_page=1` | 21 / 34 | 102 / 186 | 1.6 KB |
| Stat detail | `/hands?stat_key=vpip` (HandExplorer, report 03) | 23 / 34 | 53 / 130 | 22.8 KB |
| Compare | `mode=periods` | 71 / 134 | 246 / 560 | 15.6 KB |
| Compare | `mode=population` | 145 / 207 | **353 / 1411** | 15.7 KB |
| Compare | `mode=workspace` | 76 / 137 | 225 / 493 | 15.6 KB |
| Cash Drop | `/reports/cash-drop` | 22 / 31 | 60 / 185 | 42.7 KB |
| Population | `/population/overview?min_hands=0` | 22 / 26 | 180 / 293 (min 89) | 0.1 KB |
| Population | `/population/full-stats?min_hands=0` | 115 / 212 | **277 / 1212** | 7.8 KB |
| Population | `/identities` (0 identities) | 2 / 3 | 3 / 3 | — |
| Players | `/players?min_hands=20` p1 | 77 / 116 | 211 / 719 | 12.3 KB |
| Players | `/players` p2 / sort vpip / search "a" | 76 / 78 / 53 | 226 / 214 / 149 | 12 KB |
| Players | `/players?min_hands=1&per_page=20` (alias search) | 72 / 101 | 201 / 725 | 5.0 KB |
| Profile | `/players/{id}` + `/stats` + `/head-to-head` | 6 + 25 + 6 | 8 + 28 + 7 | 8 KB |
| Profile | `/players/{hero}/stats` | 35 / 57 | 115 / 242 | 7.7 KB |
| Identity | `/identities` (20 identities, 40 aliases) | 29 / 46 | ~0.5 s (est.) | 8.2 KB |
| Identity | `/identities/{id}/stats` | 46 / 123 | not measured (needs writes) | 7.2 KB |

Requests per page load (frontend):
- Stats: `stats/hero`, `filter-options`, `checkpoints` (WorkspaceContext), then `drift` once
  `stats.hands >= 20000` (`StatsPage.tsx:95-101`, a serial step).
- Population: `identities`, `overview`, then `full-stats` once the overview has arrived
  (`PopulationPage.tsx:63`, a waterfall), and `stats/hero` (shared cache with Stats).
- Players: `identities` + `players`. Profile: `players/{id}` + `stats` (Stats tab only),
  `head-to-head`, `stats/hero`, `color_markers` config.
- Compare: 1 request per parameter change (it runs 4–5 scans on the server, see F4).

Scaling (estimates; everything is linear in `hand_players` rows, about 6 rows per hand):

| Endpoint | 214k (measured) | 1M (est., ~6M rows) |
|---|---|---|
| Compare vs Population | 0.35 s / 1.4 s CPU | ~1.7 s / ~6.5 s CPU |
| Population full-stats | 0.28 s / 1.2 s CPU | ~1.3 s / ~5.5 s CPU |
| Players list page | 0.21 s / 0.72 s CPU | ~1.0 s / ~3.4 s CPU |
| `/identities` with 100 identities | ~2.4 s (est.) | ~11 s |
| Stats / hero-only endpoints | 0.05–0.25 s | 0.25–1.2 s |

All payloads are small (≤ 43 KB) and the Python post-processing is negligible
(`_compute_stats_from_query` folds at most 6 rows). This area has no transfer-size or
render-size problem.

## 3. Findings

### F1 — Population-wide aggregates are recomputed on every request (P1)
- **Location**: `population.py:172-213` (full-stats), `population.py:129-166` (overview),
  `compare.py:220-267`, `players.py:60-206`. None of them caches anything.
- **What happens**: each call runs `_AGG_SQL` (`stats_engine.py:55-85`): 73 H2N rows × 2 bit-shift
  SUMs plus about 14 more aggregates, over every non-hero row (1.07M at 214k), plus a GROUP BY
  over all 262k players for the `eligible` CTE.
- **Why it hurts**: the cost is CPU-bound and parallel (1.2 s CPU for 0.28 s wall). The result
  only changes on import or rebuild, but the client cache (`staleTime` 2 min,
  `lib/query-client.ts:6`) expires and every filter toggle (Exclude Hero, tag chips) is a new key.
- **Evidence**: full-stats 277 ms / 1212 ms CPU and Compare population 353 / 1411 at 214k. A
  one-pass hero+population variant (`GROUP BY position, player_id = hero`) costs 165 ms / 1052 ms,
  about the same as the population part alone.
- **Proposal**: a small LRU keyed by `(endpoint, params, data_version(db, ws))`, using the
  existing helper in `reports/chain.py:781-788`. `bump_generation()` is already called after
  writes. Use it for full-stats, overview, compare population and the players list (count and
  page). Optional: compute hero and population in one pass for Compare.
- **Gain**: repeat visits drop to under 5 ms. The first visit is unchanged unless F3 is also done.
- **Effort**: S–M. **Parity risk**: none (same SQL, memoised). Make sure tag and identity
  exclusions are part of the key.

### F2 — Players list joins everything, then groups 1.29M rows, twice (P1)
- **Location**: `players.py:90-103` (count) and `players.py:120-153` (page).
- **What happens**: `players ⋈ hand_players ⋈ hands ⋈ player_classifications` is built at full row
  width, and then grouped by `p.id, p.username, player_type, is_reg, color_tag` (string keys). The
  `hands` join only filters `workspace_id`, which `hand_players` already has (0 orphan rows at
  214k). The count query repeats the whole join only to count the groups.
- **Evidence (214k)**: count 57 ms / 200 ms CPU vs 5 / 30 ms when grouping `hand_players` alone.
  Page 96 / 356 ms vs 18 / 89 ms when pre-aggregating `hand_players`, filtering with HAVING, then
  joining `players` and `player_classifications` to the surviving rows. Rush & Cash anonymises
  seats, so 262k players have mostly 1–2 hands and only 4,401 have ≥ 20. Almost all the grouping
  work is thrown away. A search still groups every player, because the ILIKE is applied after
  the join.
- **Proposal**: build a `per_player` CTE from `hand_players WHERE workspace_id = ?` grouped by
  `player_id` with HAVING, then join `players` and `pc` for the name, type, search and type
  filters. Get the total with `COUNT(*) OVER ()` in the same query, which removes one round trip.
  Push `player_type` and `search` filters into a semi-join on the small tables. Combine with F1.
  Longer term, `batch_update_player_types` (`player_classification.py:79-104`) already groups all
  rows per player at import time. It could also store hands, VPIP, PFR, 3-Bet and AF, which would
  make the list a 262k-row scan with no join to `hand_players`.
- **Gain**: about 210 → about 30 ms wall and about 720 → about 120 ms CPU per page at 214k
  (estimate from the measured parts). Applies to page flips, sorts, search keystrokes (300 ms
  debounce) and the alias-search dialog.
- **Effort**: S (query rewrite), M (precomputed columns). **Parity risk**: none. The list uses
  OHM flags (`hp.vpip`, ...) with no H2N twin, and the numbers stay identical. Check with a
  before/after diff of the endpoint output.

### F3 — Population: a no-op `eligible` CTE and an unneeded `hands` join (P2)
- **Location**: `population.py:191-213` (CTE plus `IN (SELECT …)`), `population.py:144-156`
  (overview groups every player only to sum counts), `stats_engine.py:396-406` (same pattern,
  used by Compare with `min_hands=0`, `compare.py:104`), and `compare.py:73-82` (when
  `min_hands > 1`, a second full GROUP BY nested inside an IN).
- **What happens**: with `min_hands=0` and no `player_type`, the CTE keeps every player. It still
  costs a 262k-group aggregate plus a hash semi-join on 1.07M rows. `_AGG_SQL` always joins
  `hands`, even when the only filter is `workspace_id`.
- **Evidence (214k)**: shipped full-stats SQL 203 ms / 1187 ms CPU, the same without the CTE
  140 / 917, and also without the `hands` join 129 / 831. Overview: 66 ms → 16 ms as a single
  `COUNT(DISTINCT player_id), COUNT(*), MIN/MAX(played_at)`. The hero `_AGG_SQL` without the
  `hands` join: 98 → 47 ms wall.
- **Proposal**: emit the CTE only when `min_hands > 1` or `player_type` is set. Emit
  `JOIN hands` only when stakes, date or game-mode filters are present: add an `{hands_join}`
  slot in `_AGG_SQL` and use `hp.workspace_id`. Note that `POS_SQL` and `VALID_SQL` only reference
  `hp`. Fold the overview counts into the full-stats response, which also removes the frontend
  waterfall (`PopulationPage.tsx:55-64`).
- **Gain**: about 35–45% per population request at 214k, and about 50% on hero-only stats calls
  if the join drop is applied everywhere. Removes one serial round trip on page load.
- **Effort**: S. **Parity risk**: low. The rows are the same as long as every `hand_players` row
  has its hand, which is the import invariant (0 orphans measured). Run `test_stat_parity` and
  `test_h2n_parity_r1..r4`.

### F4 — Compare runs 4–5 full scans where 1–2 would do (P2)
- **Location**: `compare.py:119-170` (periods: `compute_hero_stats` twice and `_get_period_summary`
  twice), `compare.py:173-217`, `compare.py:220-267`.
- **What happens**: `_get_period_summary` recomputes hands, bb/100 and EV bb/100, which `_AGG_SQL`
  already returns (`stats_engine.py:58-60`, `HeroStats.hands / win_rate_*`). Compare
  population additionally runs `_get_population_summary` (another full non-hero scan).
- **Evidence**: periods 246 ms / 560 ms CPU and population 353 / 1411 at 214k. A hero `_AGG_SQL`
  costs about 100 ms and the summary about 25 ms per call.
- **Proposal**: take hands and win rates from the `HeroStats` already computed. Compute both
  periods in one query (`GROUP BY position, period` via `UNION ALL` of the two filters, because
  the periods may overlap). Get `player_count` from the same population pass
  (`COUNT(DISTINCT player_id)`). Combine with F1.
- **Gain**: about 35–50% wall per Compare request (estimate).
- **Effort**: S. **Parity risk**: the summary counts **all** hands, while `HeroStats.hands`
  leaves out `h2n_valid = FALSE` hands (61 of 216,754 at 214k). Reusing `HeroStats` changes the
  displayed Period hand count and bb/100 slightly. Treat that as a stat change, or keep the
  summary columns but compute them inside the same aggregate with
  `COUNT(*)` / `SUM(won_bb)` without `VALID_SQL` (with FILTER instead of WHERE).

### F5 — `/api/identities` is N+1 with a table scan per identity (P2)
- **Location**: `identities.py:80-88` calls `_build_identity` per id (`identities.py:18-77`):
  1 identity row, 1 alias join and 1 `COUNT(DISTINCT hand_id) FROM hand_players WHERE player_id IN (…)`.
- **Evidence**: 20 identities / 40 aliases: 29 ms at 20k. At 214k the per-identity count is 24 ms
  warm and 73 ms cold, so about 0.5 s for 20 identities and about 2.4 s for 100 (estimate). The
  Players page loads it on mount (`PlayersPage.tsx:220`), and so does the Population page
  (`PopulationPage.tsx:35`), plus the Aliases section. Every alias mutation invalidates it.
- **Proposal**: 3 queries total. One query for all identities, one for all aliases with joins,
  and one for the counts:
  `SELECT pa.identity_id, COUNT(DISTINCT hp.hand_id) FROM player_aliases pa JOIN hand_players hp ON hp.player_id = pa.player_id GROUP BY 1`.
  Assemble in Python.
- **Gain**: O(identities) scans become 1. About 2.4 s → about 40 ms for 100 identities at 214k
  (estimate). **Effort**: S. **Parity risk**: none.

### F6 — Stat detail page: sort + LIMIT reads `raw_text` for every candidate (P2)
- **Location**: `stats.py:282-292` (`/stats/detail/{key}/hands`). The detail header calls it with
  `per_page=1` (`StatDetailPanel.tsx:28-47`).
- **What happens**: `raw_text` is in the SELECT list of the `ORDER BY played_at DESC LIMIT n`
  query, so DuckDB materialises the hand text for every matching hero hand before the top-N.
- **Evidence (214k)**: with `raw_text` 64 ms; ids only 8 ms; two-phase (ids in a CTE with LIMIT,
  then join `hands` for `raw_text`) 12 ms. The endpoint also runs a separate count query
  (`stats.py:258-265`, 12 ms).
- **Proposal**: two-phase fetch. For the header, use a "counts only" mode (`per_page=0`) that skips
  the page query and `parse_actions_from_raw`. Report 03 should check whether `/api/hands` has the
  same pattern.
- **Gain**: about 102 → about 30 ms per detail open at 214k. **Effort**: XS. **Parity risk**: none.

### F7 — Drift: 12 sequential queries for 11 stats (P3)
- **Location**: `reports.py:485-488` (count), `499-530` (lifetime), `592-616` (up to 9 window
  queries, each `ORDER BY played_at DESC LIMIT 20%`), `648-660` (AFq window).
- **Evidence**: 147 ms / 380 ms CPU at 214k, about 33 ms per window query.
- **Proposal**: one query. Rank the hero's rows once (`ROW_NUMBER() OVER (PARTITION BY <opp group>
  ORDER BY played_at DESC, id DESC)`), or compute per-group ranks with
  `COUNT(*) FILTER … OVER (ORDER BY …)`, then aggregate the lifetime and window figures with FILTER.
  Cache with F1.
- **Gain**: about 147 → about 50 ms (estimate). **Effort**: M. **Parity risk**: none (drift is OHM-only).
  The rank tie-break must stay `played_at DESC, id DESC`.

### F8 — `/reports/filter-options`: 3 scans of the hero's rows (P3)
- **Location**: `reports.py:187-235`. DISTINCT stakes, DISTINCT game_mode and MIN/MAX date, each
  over hero `hand_players ⋈ hands`. 36 ms / 92 ms CPU at 214k. Every Extras page calls it
  (via `useFilterOptions`).
- **Proposal**: one query with `LIST(DISTINCT …)` and MIN/MAX, cached by data version. Shared with
  report 08. **Effort**: XS. **Parity risk**: none.

### F9 — Frontend: waterfalls and no `placeholderData` on paginated lists (P3)
- `PopulationPage.tsx:60-64`: `full-stats` waits for `overview` (`enabled: !!overview`). That adds
  overview latency (89–270 ms at 214k) to time-to-content. Fix it by folding the overview into
  full-stats (F3), or by firing both and gating only the render.
- `PlayersPage.tsx:241-244`: no `placeholderData: keepPreviousData`, so every page, sort or search
  change blanks the table to a loading state for the full request.
- `StatsPage.tsx:95-101`: drift only starts after `stats/hero` has resolved. This is fine (it is
  gated on hands ≥ 20k), but it adds a second round trip on large DBs.
- Rendering is not an issue. StatsCard and CompareTable are fixed-size grids. Players is ≤ 200
  rows. Cash Drop is ≤ 6 × 169 range cells.
- **Effort**: XS each. **Parity risk**: none.

### F10 — Dead endpoints (P3, maintenance)
- The frontend never calls these: `population/{preflop,segments,postflop,pot-types,showdown,
  hu-vs-mw,comparison}` (`population.py:242-902`), `stats/detail/{key}/{trend,analysis,
  ev-breakdown,sizing,fold-equity,by-context,composition,money,postflop-bridge,continuing-range,
  range}` (`stats.py:376-1116`), and `getStatRange`/`getContinuingRange` in `lib/api.ts`. They cost
  nothing at runtime. However, the population ones apply the stakes and date filters only inside
  the `eligible` CTE, not in the main aggregate (for example `population.py:285-290`), so they would
  return wrong numbers if anything wired them up. `sizing` reads `actions`, which has 0 rows in both
  benchmark DBs. Delete them, or fix them before use.

## 4. Quick wins vs. larger refactors

Quick wins (≤ half a day each, no parity change):
- F6 two-phase `raw_text` fetch, plus a counts-only mode for the detail header.
- F2 Players query rewrite (pre-aggregate `hand_players`, `COUNT(*) OVER ()`).
- F3 conditional `eligible` CTE and conditional `hands` join; overview as a single aggregate.
- F5 identities in 3 queries.
- F8 single filter-options query.
- F9 `keepPreviousData` on the Players list; remove the Population waterfall.

Larger refactors:
- F1 data-version result cache shared by Population, Compare, Players and Drift. It needs a
  decision on where the cache lives (reuse `reports/chain.py`'s LRU or a small shared module) and
  on invalidation coverage (imports, rebuild, identity and tag edits for the exclusion variants).
- F2b store per-player list stats in `player_classifications` at import time. This needs a
  schema change and a rebuild path.
- F4 one-pass Compare (both periods, or hero plus population, in one query). Decide whether
  Period hand counts should follow H2N validity, which is a stat change.
- F7 single-query drift.

## 5. Open questions / not measured

- **Swap vs. genuine cost**: every number above comes from locked, otherwise idle runs. I did not
  reproduce the user's swapping state. The CPU column shows what turns into wall time under
  contention: the population endpoints use 4–5x their wall time in CPU.
- **Memory**: peak RSS per request was not measured. Responses are small and the queries are
  aggregates, so the DuckDB working set (hash tables for 262k player groups) is the only
  candidate. It is likely tens of MB, not measured.
- `/identities/{id}/stats` and `/identities` at 214k were not run end-to-end, because they need
  identity rows and the 214k DB was opened read-only. The 214k figures are extrapolated from the
  per-identity query timing.
- The "Players split ~2 s at 20k" is in `reports/split.py` (report 01), not in this area.
- Not perf, seen in passing: `StatsDetailView` drops `last_n` from the URL (`StatsPage.tsx:32-37`)
  and the HandExplorer `fixedParams` omit `game_mode` (`StatDetailPanel.tsx:70-76`). The detail
  list can therefore show a different sample than the clicked cell.
- The frontend bundle and the Electron/IPC overhead are not covered (report 08).

Benchmark scripts (endpoints, and SQL variants at 214k read-only) were kept locally (not committed).
