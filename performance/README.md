# Performance due diligence

One report per page / area. Each report covers the endpoints the screen calls, the backend code
behind them, and the frontend that renders the result. It lists where time and memory go, which
choices don't scale, and what to change. **Start with [SUMMARY.md](SUMMARY.md)**: themes across the
reports, the prioritized backlog, and what we know about the 11 GB incident.

| # | Report | Scope |
|---|---|---|
| 01 | [01-reports-stats-split.md](01-reports-stats-split.md) | Reports: Stats tab, lower tabs (Results, Positions, Next Actions), chain resolve + cache |
| 02 | [02-reports-graph-range-strength.md](02-reports-graph-range-strength.md) | Reports: Graph, Preflop Range, Hand Strength tabs |
| 03 | [03-hands-lists.md](03-hands-lists.md) | Hand lists (Reports Hands tab, Marked Hands), hand panel, replayer, export, data grid |
| 04 | [04-statistics-general.md](04-statistics-general.md) | Statistics: dashboards, General screen, stat popup |
| 05 | [05-sessions.md](05-sessions.md) | Sessions: list, live, drill-down, recipes |
| 06 | [06-import-pipeline.md](06-import-pipeline.md) | Import (files, H2N DB, trackers, auto-import), rebuild, import memory growth |
| 07 | [07-extras.md](07-extras.md) | OHM Extras: Stats, Compare, Cash Drop, Population, Players |
| 08 | [08-platform-infra.md](08-platform-infra.md) | DB layer, startup, serialization, caching, frontend bundle/query defaults, Electron, Databases/Configuration |

## Method

- Benchmark DB: the 20k-hand fixture `backend/tests/fixtures/bench_sample_20k.txt` (hero "Hero"),
  imported into a throwaway data dir. Numbers are extrapolated to the 214k-hand DB that triggered
  this review (Graph tab: 43 s and an 89 MB response at 214k hands).
- Timings report wall and CPU time. The dev machine was swapping during this review, so wall
  time alone overstates the cost.
- Every proposal states its effect on Hand2Note parity (`test_h2n_parity_*`, `test_stat_parity`,
  money invariants). A change that alters a number is a stat change, not a performance fix.

## Report format

1. **Summary**: the 3–5 changes worth doing first, with expected gain.
2. **Baseline**: endpoints, measured time / CPU / memory / payload at 20k hands, scaling estimate
   for 200k and 1M.
3. **Findings**: one block each with ID, severity (P0–P3), location (`file:line`), what happens,
   why it's slow (complexity, round trips, allocations), evidence, proposal, expected gain,
   effort, parity risk.
4. **Quick wins vs. larger refactors.**
5. **Open questions / not measured.**
