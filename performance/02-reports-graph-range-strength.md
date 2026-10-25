# 02 — Reports: Graph, Preflop Range, Hand Strength tabs

Scope: `GET /api/reports/graph` (Graph upper tab, legacy `GraphPage`), `POST /api/reports/preflop-range`,
`POST /api/reports/hand-strength`, and the frontend that draws them (`GraphTab`, `ResultsChart`,
`PreflopRangeTab`, `HandStrengthTab`). How these endpoints use `chain.resolve` is covered here; the
resolver itself is report 01's area (cross-referenced as 01-F1 etc.).

All numbers below were measured on the 20k fixture DB (`/tmp/ohm-perf/02`, hero "Hero", 19,994
H2N-valid hands) or on the 214k DB opened read-only, unless marked **estimate**. "Wall" and "CPU"
are best of 3 unless the row says cold.

## 1. Summary: do these first

| # | Change | Gain at 214k hands | Effort | Parity risk |
|---|---|---|---|---|
| G1 | Graph: compute the cumulative series in one columnar pass (DOUBLE columns via Arrow, `pyarrow.compute.cumulative_sum`) and send **only the ~1000 points the chart draws** (same indices the frontend picks today) plus the last point. Sessions and variance are still computed over every hand | graph handler + JSON **3.7 s → 0.07 s**, payload **89 MB → 0.48 MB**, peak RSS **+661 MB → ~+30 MB (estimate)**; the browser no longer parses 89 MB (0.3 s, +81 MB heap per cached chain) | S (1 d incl. frontend + tests) | **none**: prototype is bit-identical on every sampled point, last point, sessions and variance (§2.3) |
| G2 | Graph with a plain chain (incl. page 0's `chain=[]`): put `COALESCE(hp.h2n_valid, TRUE)` + `plain_sql(chain)` in the graph query and don't resolve the chain (graph side of 01-F1) | cold page 0 Graph: removes the **2.6 s / +638 MB** resolve and the 214k-id `IN (UNNEST)` round trip (161 ms) | S (0.5 d) | none: same hand set (tested: 19,994 = 19,994 rows) |
| G3 | Frontend: stop using `points.length` as the hand count (`GraphTab.tsx:24`, `GraphPage.tsx:187`, `ResultsChart.tsx:263`); use the last point's `hand_number` | required for G1; otherwise "N hands" and bb/100 become wrong | XS (1 h) | none |
| G4 | Spot chains: keep the resolve (it is shared with the Stats / lower tabs through the cache) but cache the graph response on the `Resolution` (`res.tables`), as the split tables already are | warm Graph on a spot page **→ <1 ms** server time | XS | none |
| G5 | Preflop Range / Hand Strength on plain chains: SQL `GROUP BY` instead of a Python loop over the resolution (part of 01-F1). For spot chains, cache the view result on the `Resolution` | Range view **~160 ms → ~30–100 ms at 214k (estimate)**; nothing else to gain once the resolve is fixed | XS–S | none (0 mismatching classes vs the current view at 20k) |

The 43 s the user saw is mostly memory, not CPU: at 214k one cold page-0 Graph request holds
~940 MB of Python objects (638 MB for the resolution + ~220 MB for the 214k `GraphPoint`s and
`Decimal` rows + the 89 MB JSON) on a machine that is already swapping. Without swap it is ~6.3 s
wall (§2.2). G1 + G2 together make it ~0.1 s and a few MB.

## 2. Baseline

### 2.1 Endpoints at 20k hands (TestClient, in-process)

| Request | Wall | CPU | Payload |
|---|---|---|---|
| `GET /reports/graph?chain=[]`, resolve cold | 519 ms | 520 ms | 8.13 MB, 19,994 points, 186 sessions |
| same, resolve warm (cache hit) | 317 ms | 317 ms | 8.13 MB |
| `GET /reports/graph` (no chain param, legacy filters) | 263 ms | 259 ms | 8.13 MB, 20,000 points |
| `GET /reports/graph?chain=[row P01]` cold / warm | 365 / 49 ms | 363 / 50 ms | 1.29 MB, 3,092 points |
| `POST /reports/preflop-range` `[]` cold / warm | 249 / 18 ms | 260 / 18 ms | 9.9 KB |
| `POST /reports/preflop-range` `[pos BTN]` cold / warm | 43 / 6 ms | | 8.9 KB |
| `POST /reports/preflop-range` `[row P01]` cold / warm | 392 / 6 ms | 306 / 6 ms | 9.0 KB |
| `POST /reports/hand-strength` any chain, any street, resolution warm | 2.5–5.3 ms | | 1.3 KB |

Stage breakdown of the warm `chain=[]` graph request (20k):

| Stage | Wall | Note |
|---|---|---|
| `chain_hand_ids` warm (builds the 19,994-id `case_ids` list) | 1.3 ms | cold: 178 ms (= the resolve) |
| graph SELECT with `IN (SELECT UNNEST(?::VARCHAR[]))` + `fetchall` | 102 ms | 10 columns, 6 of them `DECIMAL(18,3)` → Python `Decimal` |
| same SELECT with the `h2n_valid` predicate instead of the id list | 88 ms | same 19,994 rows |
| Python loop: `float()`, 12 running sums, 12 `round()`, `datetime.isoformat`, `GraphPoint(...)` | ~110 ms | `GraphPoint(**d)` alone ×19,994 = 45 ms |
| `get_graph()` total | 253 ms | heap peak 54 MB (tracemalloc) |
| FastAPI `response_model`: `validate_python(from_attributes=True)` | **0.0 ms** | returns the instance unchanged (FastAPI 0.162, pydantic 2.14) |
| FastAPI `dump_json` (Rust serializer) | 23 ms | |

### 2.2 214k hands (real DB, read-only, no swap during the run)

| Stage | Wall | CPU | Memory |
|---|---|---|---|
| `_compute(chain=[])`: resolve of page 0 | 2.59 s | 4.55 s | maxrss **+638 MB** |
| `get_graph` handler fed the 214k case ids (`IN (UNNEST)`) | 3.41 s | 3.35 s | maxrss +221 MB more (process 940 MB) |
| `get_graph` handler, no chain | 3.42 s | 5.14 s | maxrss **+661 MB** |
| `dump_json` of the response | 0.26 s | 0.26 s | 89.4 MB body |
| just the `IN (SELECT UNNEST(214k ids))` filter (COUNT) | 161 ms | | |
| browser side (node 24 / V8): `JSON.parse` of the 89 MB body | 286 ms | | +81 MB JS heap, kept by react-query for `gcTime` 10 min per chain |
| browser: legacy checkpoint mapping (`ResultsChart.tsx:166-189`), 3 checkpoints × 214k `new Date()` | 110 ms | | |
| **G1 prototype** (Arrow + `cumulative_sum` + take 1000 + sessions) | **72 ms** | 143 ms | 0.48 MB body |
| G1 prototype variance (`AVG` / `STDDEV_SAMP` in SQL) | 14 ms | | |

Cold page-0 Graph today ≈ 2.6 + 3.4 + 0.26 + transfer/parse ≈ **6.5 s without swap**, ~940 MB peak;
the live run took 43 s because of swap. With G1 + G2: ≈ 0.1 s.

### 2.3 Prototype exactness (20k, against the current `get_graph(chain="[]")`)

`/tmp/ohm-perf/02/proto_graph2.py --compare`:

- 1000 sampled points × 12 cumulative fields: **0 mismatches**; `played_at` equal; the sampled
  `hand_number`s are exactly the ones `ResultsChart` keeps today (`round(i * step)`, plus the last).
- last point equal; 186 sessions equal (start/end hand and times); variance equal on all six fields.
- Why exact: the columns are cast to DOUBLE in SQL (same value as `float(Decimal)`) and summed
  **sequentially** (`pyarrow.compute.cumulative_sum`, or `itertools.accumulate`), in the same order
  as the Python loop; rounding stays Python `round(x, 2)` on the ~1000 kept values.
- What is *not* exact: a DuckDB window `SUM(DOUBLE) OVER (ORDER BY …)` (first prototype,
  `proto_graph.py`): 148 of 12,000 values differ by 0.01, because DuckDB adds in a different order.
  A `DECIMAL` window sum would be exact arithmetic but also differs from today's float output at
  `.xx5` boundaries. So do the running sums in Arrow/Python, not in a SQL window.

### 2.4 Scaling (estimate, linear in hero hands)

| | 20k | 214k (measured) | 1M (estimate) |
|---|---|---|---|
| Graph, cold page 0, today | 0.52 s, 8 MB | ~6.5 s, 89 MB, ~940 MB RSS | ~30 s, 420 MB body, >4 GB RSS (not usable) |
| Graph, G1 + G2 | ~25 ms, 0.45 MB | ~75 ms, 0.48 MB | ~0.35 s, 0.5 MB |
| Range / Strength, resolution warm | 18 / 5 ms | see F-G5 | ~1 s / ~0.1 s |
| Range / Strength, cold | = resolve (01) | 2.6 s + view | ~13 s (resolve) |

## 3. Findings

### G1 — Graph sends one 14-field object per hand; the chart draws 1000 (P0)

- **Where**: `backend/app/api/reports.py:84-151` (loop + `GraphPoint` per hand), `backend/app/models.py:19-55`;
  `frontend/src/components/results/ResultsChart.tsx:128-139` (keeps 1000).
- **What happens**: every hand becomes a `GraphPoint` with 12 rounded running sums and an ISO
  timestamp string; 214,246 of them are built, serialized (89 MB), sent, parsed into 214k JS objects,
  and then `ResultsChart` keeps 1000 of them. Each point costs 10 `Decimal` → `float`, 12 `round`,
  one `isoformat`, one pydantic init: ~16 µs per hand in CPython (5.1 s CPU at 214k), plus ~3 KB of
  peak heap per hand (+661 MB maxrss).
- **Proposal**:
  1. SELECT the 12 per-hand deltas as DOUBLE (`CAST(COALESCE(hp.won_bb, 0) AS DOUBLE)` …;
     showdown / non-showdown as `CASE WHEN sd THEN x ELSE 0.0 END`) plus `played_at` and
     `COALESCE(played_at - LAG(played_at) OVER (ORDER BY played_at, id) > INTERVAL 10 MINUTE, TRUE)
     AS sess_start`, ordered by `played_at, id`, fetched with `fetch_arrow_table()` (pyarrow is
     already a dependency, `backend/requirements.txt:7`).
  2. `pc.cumulative_sum` per column, `pc.take` at the sample indices (the frontend formula,
     `max_points` query param, default 1000; the last hand always included), `round(…, 2)` in Python
     on those only.
  3. Sessions from `pc.indices_nonzero(sess_start)` (end = next start − 1, last = N) and
     `pc.take(played_at, …)`: over every hand, as today.
  4. Variance: `COUNT, AVG, STDDEV_SAMP` of `won_bb` in SQL over every hand (14 ms at 214k).
  5. Add `hands: int` (N) to `GraphResponse` so callers don't have to infer it.
  6. `last_n` (legacy only): apply it in SQL (`ORDER BY played_at DESC, id DESC LIMIT ?` in a
     subquery, then re-sort) instead of fetching everything and slicing (`reports.py:81-82`).
  7. Return plain dicts from the handler or keep the model with ~1000 points: the
     `response_model` overhead is not a problem any more (see G6).
- **Visual fidelity**: identical to today, since the server picks the same 1000 points the
  client picks now. If fidelity is wanted later (a big swing inside one 214-hand bucket is
  invisible both today and after), send per-bucket min/max of `cumulative_bb` (M4 downsampling),
  ~2000 points, still < 1 MB.
- **Expected gain**: measured 3.7 s → 72 ms wall at 214k (51×), 89 MB → 0.48 MB; 20k: 276 ms →
  24 ms.
- **Effort**: S. **Parity risk**: none (bit-identical, §2.3). The Graph is not an H2N parity
  number, but it is shown next to the Stats tab's Won / bb/100, and they still agree.
- **Tests that must change**: seven assertions compare `len(points)` with a hand count and break
  as soon as a result has more than `max_points` hands (the 20k one at
  `backend/tests/test_reports_lite.py:608` certainly does): `test_reports_lite.py:301, 303, 319, 608, 647`,
  `test_sessions_h2n.py:363`, `test_reports_line.py:62`. Switch them to `g["hands"]` /
  `points[-1]["hand_number"]`, and add one test that the downsampled response's points equal the
  full series at the same hand numbers, and that sessions / variance don't change with `max_points`.

### G2 — A plain chain is resolved into 214k Python records just to get the hand ids back (P0)

- **Where**: `backend/app/api/reports.py:36-43, 73-75`, `backend/app/api/reports_lite.py:84-98`,
  `backend/app/reports/chain.py:566-568, 693-696`.
- **What happens**: `chain_hand_ids` runs `resolve()`; for a chain without spot steps (page 0 is
  `[]`) that is `SELECT … WHERE _BASE_WHERE + plain_sql` turned into one `HandRec` per hand
  (2.6 s, +638 MB at 214k), then `case_ids` (214k strings) goes back to DuckDB as a
  `VARCHAR[]` parameter for `h.id IN (SELECT UNNEST(?))` (161 ms just for that filter). The
  resolution is the same thing the graph query could do with the predicate it was built from.
- **Proposal**: in `get_graph`, parse the chain; if `not spot_steps(chain)`, call
  `target_player` (keeps the 404), read `day_start_hour`, and append
  `" AND COALESCE(hp.h2n_valid, TRUE)" + plain_sql(chain, day_start)` to the graph WHERE. Only spot
  chains go through `resolve()`. A shared helper (`chain_where(db, ws, player, chain) -> (sql, params) | ids`)
  serves `/api/hands` too (report 03) and is the graph half of 01-F1.
- **When it matters**: the resolution is usually already cached when the Graph tab opens, because
  the Stats tab or the lower tab (same chain when nothing is selected) resolved it. It is cold when
  the persisted upper tab is `graph` (`frontend/src/lib/reports/pages.ts:433, 493`), after any
  import (`bump_generation` + `invalidateQueries`), or after LRU eviction (one 214k plain
  resolution is a third of the 600k-record cap, `chain.py:765`).
- **Expected gain**: cold page-0 Graph −2.6 s / −638 MB at 214k; warm −160 ms.
- **Effort**: S. **Parity risk**: none; identical row set (`bench_graph.py`: 19,994 both ways).
  The no-chain legacy path keeps its current semantics (no `h2n_valid` filter; 20,000 vs 19,994).

### G3 — Frontend treats `points.length` as the number of hands (P1, blocks G1)

- **Where**: `frontend/src/components/reports/tabs/GraphTab.tsx:22-30` (hands, bb/100, EV bb/100),
  `frontend/src/pages/GraphPage.tsx:187-213` (n, every /100 rate, hands/hr),
  `frontend/src/components/results/ResultsChart.tsx:263` (`niceXTicks(data.length)`).
- **Consumers of `points` checked**:
  - tooltip (`ResultsChart.tsx:58-99`): shows the hovered point's `played_at` and `hand_number`; fine
    with sampled points.
  - session markers / active session (`:119-124, 281-303`): use `sessions[].start_hand/end_hand`,
    which stay exact; `ReferenceLine x` sits on a numeric axis, so it doesn't need a point at that
    hand. Fine.
  - CI band (`:141-164`): uses `hand_number` and `variance`; fine.
  - `hasEVData` (`:117`, `GraphPage.tsx:168`): `some(ev !== bb)` over the points; with samples it
    can only differ if cumulative EV and actual are equal at every sampled point but not between,
    which does not happen in practice; `GraphTab` already only checks the last point. Optional:
    a server `has_ev` flag.
  - checkpoints (`:166-189`, legacy `GraphPage` only): nearest point by time; after sampling it
    snaps to within ±N/2000 hands (±107 at 214k), sub-pixel. It also stops costing 110 ms per
    recompute.
  - `last_n` (legacy): cumulates from 0 inside the window, server side; unchanged.
  - landing mock (`frontend/landing/mock/graph-data.ts`): small point counts; works if the
    frontend falls back to `points.at(-1).hand_number`.
- **Proposal**: `const hands = data.hands ?? last.hand_number` everywhere `points.length` /
  `data.length` means hands; `niceXTicks(lastHandNumber)`. Leave the client-side sampling in place
  (it returns the array unchanged when it is ≤ 1000).
- **Effort**: XS. **Parity risk**: none.

### G4 — Spot-chain graphs are recomputed on every request (P2)

- **Where**: `reports.py:79-183`, `chain.py:559` (`Resolution.tables`).
- **What happens**: warm `[row P01]` Graph at 20k: 49 ms, all of it the SQL refetch + loop over
  3,092 hands; the resolution itself is a cache hit (0.6 ms). At 214k a P01 page has 34,702 cases
  (01 §2): ~0.6 s per request today (estimate), ~15 ms after G1.
- **Proposal**: store the G1 result in `res.tables[("graph", max_points)]` under `res.lock`, like
  `action_table`. For plain chains (G2, no resolution) G1 is fast enough not to need a cache.
- **Effort**: XS. **Parity risk**: none (the key is the resolution, which already carries the data
  version).

### G5 — Preflop Range / Hand Strength: cheap views, expensive resolve (P2)

- **Where**: `backend/app/api/reports_lite.py:67-76`, `backend/app/reports/views.py:224-270`.
- **What happens**: both endpoints resolve the chain and loop over `res.cases`. On a warm
  resolution they are cheap (20k: range view 15 ms, strength 0.8 ms; endpoint 2.5–18 ms incl.
  HTTP). Their cost is the cold resolve (249 ms at 20k for `[]`, 392 ms for `[row P01]` incl. the
  replay of the 1,440 hands without a stored `h2n_seq`), which 01-F1/F4/F5 address. At 214k the
  range view is ~160 ms and hand strength ~10 ms per request (estimate, linear from 20k; the
  214k run could not get the benchmark lock in time).
  `preflop_range` calls `card_class()` (string slicing, `RANKS.index`) per case on every request
  and the result isn't cached; switching the Hand Strength street is one request per street (each
  ~5 ms, react-query keeps them).
- **Proposal**:
  - plain chains: SQL `GROUP BY card_class_sql()` / `GROUP BY hp.hv_<street>` with
    `SUM(CAST(won_bb AS DOUBLE))` over the same WHERE as G2 (20k: 10.6 ms / 2.0 ms; 214k: ~30–100 ms / ~10 ms, estimate). Verified equal to the view: 0 of 169 classes differ in hands or won_bb.
  - spot chains: cache `preflop_range(res)` and `hand_strength(res, street)` in `res.tables`.
- **Payload**: 9.9 KB / 1.3 KB; nothing to do. (`won_bb` is sent unrounded, e.g.
  `-12.340000000000002`; harmless.)
- **Effort**: XS (cache) / S (SQL, shared with 01-F1). **Parity risk**: none; `won_bb` sums could
  differ in the last float bit from the Python loop's order, invisible after formatting.

### G6 — `response_model` double validation: not a cost on this FastAPI (P3, no action)

- **Where**: `reports.py:22`, FastAPI 0.162 `routing.serialize_response`.
- **Evidence**: FastAPI validates the returned `GraphResponse` with
  `TypeAdapter.validate_python(value, from_attributes=True)`, which for an instance of the same
  class is a pass-through (0.0 ms for 19,994 points), then serializes with the Rust `dump_json`
  fast path (23 ms at 20k, 0.26 s at 214k). The re-validation seen in the lead's profile came from
  the profiling script's explicit `GraphResponse.model_validate(...)`, not from the request path.
  `GraphPoint.model_construct` is *slower* than the validating constructor (79 vs 45 ms per 20k),
  so it is not a fix either. With G1 there are 1000 points and none of this matters.
- **Caveat**: `requirements.txt` allows `fastapi>=0.115`; FastAPI versions before the
  `dump_json` fast path serialize through Python dicts + `json.dumps`, several times slower on
  big bodies. Pinning a floor of the version that has it is cheap insurance, but G1 removes the
  exposure anyway.

### G7 — Graph handler holds the GIL for seconds (P2, fixed by G1)

- **Where**: `reports.py:22` (sync `def`, runs in the threadpool).
- **What happens**: at 214k the loop is ~3.4 s of pure Python. DuckDB releases the GIL during
  queries, but this loop doesn't, so every other request of the page (lower tab split, health
  poll, hands list) waits behind it. Measured CPU > wall for the no-chain handler (5.1 s vs 3.4 s)
  is DuckDB's parallel scan; the Python part is single-threaded.
- **Proposal**: none beyond G1 (72 ms, mostly in DuckDB/Arrow, which release the GIL).

### G8 — Frontend keeps the full series per chain for 10 minutes (P3, fixed by G1)

- **Where**: `frontend/src/lib/query-client.ts` (`staleTime` 2 min, `gcTime` 10 min),
  `GraphTab.tsx:15-18` (key per chain).
- **What happens**: each visited Graph page keeps its parsed response (81 MB JS heap at 214k for
  page 0) for 10 minutes; going back to a page after 2 minutes refetches it. With G1 a response is
  ~0.5 MB, so no change to the query defaults is needed.

### Legacy pages

- `frontend/src/pages/GraphPage.tsx` is not routed in the app (`App.tsx`); it renders only on the
  landing site (`frontend/landing/components/ShowcaseGraph.tsx`) against mock data. G3's fix is
  still needed there because the mock goes through the same component.
- `frontend/src/pages/RangePage.tsx` is dead code: nothing imports it. It used `GET /api/stats/range`
  (`backend/app/api/stats.py:62`), which is not one of the Reports endpoints. Candidate for deletion.

## 4. Quick wins vs. larger refactors

Quick wins (≤ 1 day, no parity risk):
1. G1 + G3 together (server-side sampling with exact running sums, frontend hand count from the last
   point, tests on `hands`). Biggest single gain; fixes the 89 MB payload and most of the memory.
2. G4 and the spot-chain half of G5: cache graph / range / strength results on the `Resolution`.
3. G2 for the graph: plain chains skip the resolve. Small on its own, but it removes the 638 MB
   cold path from the Graph tab.

Larger (with report 01):
- 01-F1's shared "plain chain → SQL" path, used by graph (G2), hands list, Range / Strength (G5),
  Stats and plain splits. Once it exists, the Reports tabs only pay for spot evaluation.
- Optional: M4 min/max downsampling for better visual fidelity, and a `from_hand`/`to_hand` window
  if the chart ever gets zoom.

## 5. Open questions / not measured

- The 43 s figure was not reproduced (by design: no runs against the live backend). The no-swap
  214k numbers above come from read-only runs of the same code; the gap is attributed to swap
  from the ~940 MB peak, not proven.
- Recharts render time with 1000 points was not measured in a browser (the app wasn't started).
  It is the same as today since the chart already draws 1000 points.
- The 214k DB has no `Hero` player; benchmarks used the player with the most hands (id 3796,
  214,188 hands, the same count as the lead's run).
- Preflop Range / Hand Strength view and SQL `GROUP BY` timings at 214k are linear estimates from 20k:
  the 214k run sat behind another agent's benchmark lock and was cancelled.
- Spot-chain graph at 214k after G1 is an estimate (≈ 34.7k-row semi-join + Arrow pass, ~15–40 ms).
- `STDDEV_SAMP` vs the Python two-pass formula matched after rounding at 20k; at 214k only the
  SQL side was run. A divergence would need the 4th decimal of the SD to sit on a rounding
  boundary; computing the SD from the Arrow column in Python (two-pass, as today) removes even that.

Scripts: `/tmp/ohm-perf/02/bench_graph.py`, `proto_graph.py`, `proto_graph2.py`, `big_handler.py`,
`big_resolve.py`, `bench_range.py`, `big_range.py`, `fe_parse.mjs`.
