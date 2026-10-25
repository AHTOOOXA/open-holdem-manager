# Step 2: extend cached results on import instead of dropping them

Status: implemented (merged into `rework`). Background: [SUMMARY.md](SUMMARY.md), results:
[RESULTS.md](RESULTS.md).

## Problem

Every write path calls `data_generation.bump()`. Since the perf branch, each bump also clears
every in-process cache (`on_bump`). That is correct but cold: while auto-import runs, a tick
every few seconds throws away the Reports resolution (2–3 s per spot chain at 214k) and the
stat popup records (seconds per cell). The page then recomputes from scratch for a few dozen
new hands.

Hands are immutable once imported, and every cached value here is a fold over independent
hands. Old result + new hands = new result.

## Contract (`backend/app/data_generation.py`)

Three kinds of change:

| Kind | Call | Meaning | Who fires it |
|---|---|---|---|
| append | `bump_append(workspace_id, hand_ids)` | Only new hands (and their hand_players rows) were added to one workspace. No existing row changed. | the import paths: files, stream, H2N DB, tracker DB, auto-import |
| derived | `bump_derived(workspace_id)` | Only per-player derived data changed (player types / classification, first/last seen, hero list re-detection that keeps player ids). Hand rows unchanged. | finalize_import, player_classification |
| reset | `bump()` (unchanged signature) | Anything else: delete, clear, restore, rebuild, settings that change stats, workspace delete. | every other write path |

- All three increment the generation, so `current()` keeps meaning "something changed".
- `on_bump(fn)` keeps its meaning: run on every change of any kind. For caches that can't extend
  (SQL-backed ones that are cheap to recompute: graph, extras, sessions, General).
- `on_reset(fn)` (new): run on `reset` only. For caches that extend.
- `changes_since(gen, workspace_id) -> list[str] | None`: hand ids appended to `workspace_id`
  since generation `gen`, in import order. Returns None when a `reset` for that workspace (or a
  global one) happened since `gen`, or the bounded change log no longer reaches back to `gen`.
  `derived` events don't affect it. The log is bounded (a few hundred events / ~1M ids); past
  that, callers recompute.
- Thread safety: the log and the counter share `_lock`. A cache entry records the generation
  it was computed at, read before computing. If a bump lands mid-computation, the next lookup
  extends from that generation, so nothing is missed. A hand may be seen twice; extensions
  must dedupe by hand id.

## Caches that extend

1. **Reports resolutions** (`reports/chain.py` `_CACHE`)
   - Key without the generation: `(workspace, target player, canonical chain, day_start)`.
     The entry stores its generation.
   - On lookup at a newer generation, `changes_since` gives the new ids. Run the same
     per-hand pipeline as `_compute` (plain SQL filter + row bits + spot evaluation) on only
     those ids for the target player, append the HandRecs, and update `total_hands`.
   - Memoized responses and tables (`Resolution.memo`) are dropped or rebuilt from the
     merged records. They are cheap next to decoding and evaluating every hand.
   - Plain chains (pure SQL scope) need no extension: their count is a SQL query. Just keep
     them warm.
   - Not extendable: chains with date steps relative to "now", and anything whose key
     ingredients changed (hero re-detected to a different player id). Those recompute.
2. **Stat popup records** (`api/general_popup.py` `_RECORDS`): per-cell record segments. Replay
   or decode only the new hands for that (player, row, street), append, and dedupe by hand id.
3. **Anything else** that folds per-hand work in Python and is expensive cold. Audit the merged
   code. SQL-backed caches (graph, extras ResultCache, sessions, General, opponent view)
   stay on `on_bump` and recompute: they cost tens to hundreds of ms after the perf work.

## Frontend

With extension cheap, the visible screen can refresh itself after an auto-import tick (debounced,
at most once per tick, never double). Inactive heavy screens stay stale until shown.
`frontend/src/lib/query-policy.ts` decides this. The "New hands" chip stays as the fallback for
screens that would still be slow (e.g. an uncached cold chain).

## Proof obligations

- **Incremental equivalence.** Import the 20k fixture in chunks (e.g. 10k + 5k + 3k + 2k)
  through the real import endpoint. Between chunks, hit a broad set of endpoints so the caches
  are warm and must extend. Then capture every endpoint. The result must equal the golden
  capture of a one-shot 20k import (the golden base capture), with no new allow rules.
- **Reset still resets.** Delete, rebuild and clear after warm caches give the same output as a
  fresh process.
- **Parity tests and the full suite stay green.** No stored flag changes, no STAT_VERSION bump.
- **Measured:** an auto-import-sized append (50–200 hands) into the 214k copy with warm Reports,
  popup and graph caches: time to fresh results before vs after.
