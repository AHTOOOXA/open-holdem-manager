# Performance work: results

Branch `perf/fixes` (from `rework`). Plan and findings: [SUMMARY.md](SUMMARY.md); step 2 design:
[INCREMENTAL-CACHES.md](INCREMENTAL-CACHES.md).

## Numbers at 214k hands (the user's DB, production-style server, HTTP)

| Request | Before (`rework`, no swap) | After: first visit | After: repeat |
|---|---|---|---|
| Reports page 0, Stats | ~2.8 s CPU | 193 ms | 3 ms |
| Reports page 0, Results / Positions | ~0.7 s each, after the resolve | 69–81 ms | 3 ms |
| Graph (default filter) | ~6.5 s, 89 MB JSON | 157 ms, 437 KB | 5 ms |
| Hands tab page | ~350 ms + resolve | 54–67 ms | ~50 ms |
| Export, 100k hands | 7.1 s | 0.8 s (streamed) | |
| General grid | ~215 ms | 47 ms | 47 ms |
| Stat popup VPIP | 7.7 s cold / 1.4 s warm | 5.9 s | 0.22 s |
| Sessions list | ~50 ms | 66 ms | 8 ms |
| Players list (Extras) | ~210 ms | 74 ms | 9 ms |
| Population full-stats | 203 ms | 139 ms | 3 ms |
| **After a 100-hand auto-import, 12 warm screens** | 14.5 s to fresh results | | **0.87 s** |
| **Backend memory** | 11 GB after an import (12 GB peak) | ~1 GB after browsing everything; Reports cache bounded at 384 MB | |

Each number is checked against the old output:
- **One-shot golden diff:** 574 endpoint responses on the 20k fixture, 0 unexpected differences.
- **Chunked-import diff:** the 20k fixture imported in four chunks with warm caches in between, also 0 unexpected differences.
- **Allowed changes,** all intentional:
  - hand-list rows no longer carry the acting player and all-in flag of each action (only the detail view used them);
  - dead endpoints were removed;
  - `replayed`, a popup cache diagnostic, changes with cache warmth;
  - one rounding wobble that already varied between runs on `rework`.
- **Tests:** backend 1500 passed, plus Hand2Note parity and money invariants; frontend 321 tests, lint, typecheck and both builds.

## Still slow on a first visit (then cached, and extended on import)

| Request | First visit | Why | Fix |
|---|---|---|---|
| Next Actions, default filter | 4.4 s | decodes every hand to find hero's first decision | store that decision per hand at import (STAT_VERSION bump) |
| A spot filter on all hands (e.g. P01) | 2.3–3.3 s | per-hand matcher evaluation | the same kind of stored per-hand facts; imports already extend the cached result |
| Stat popup VPIP | 5.9 s | replays ~208k opportunities | store popup fields per hand |
| Players split over the whole DB (`chain=[]`) | 3.3 s, 122 MB | one row per opponent (262k) | not reachable from the UI (only session pages use it, ≤ ~5k rows); cap or page it if exposed |

## Not done (deliberately)

- **Multi-process import.** PyInstaller risk; import runs at ~1,450 hands/s.
- **DB file compaction.** 77% of the 214k file is free blocks.
- **Electron startup window.**
- **Server-side cancellation of abandoned requests.** The browser cancels; the server finishes its computation, limited to 2 heavy requests at once.
- **Per-hand stored facts (step 3) and per-player summary tables (step 4).** See SUMMARY.md.

## Found along the way

- `/api/identities` returned 500 on databases whose `player_identities` predates its `tags` column. Fixed in `0640432`: a migration adds the column.
- Player ids are assigned in Python set order during import, so the same files give different ids in different processes. Harmless for stats, but tests and diffs must not depend on ids.
- Graph session markers (10-minute gap, 282 sessions at 214k) and the Sessions page (Hand2Note rule, 250) still disagree.
