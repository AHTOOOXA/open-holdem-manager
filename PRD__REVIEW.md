PRD Review Summary                                                                                     
                                                                                                           
  M1: Find Leaks — Strong, 3 critical fixes needed                                                         
  ┌─────────────────┬───────────────────────┐                                                              
  │     Aspect      │        Rating         │
  ├─────────────────┼───────────────────────┤
  │ Completeness    │ Excellent             │
  ├─────────────────┼───────────────────────┤
  │ Spec quality    │ Very high             │
  ├─────────────────┼───────────────────────┤
  │ Effort estimate │ Realistic (9-12 days) │
  └─────────────────┴───────────────────────┘
  Critical fixes before implementation:
  1. Z-score formula bug in M1.3 — uses raw stddev instead of standard error. The denominator needs /
  sqrt(window_size). As written, drift will essentially never trigger.
  2. "View hands" deep links depend on stat-flag filtering in the hands API, which doesn't exist yet. Need
  to add ?stat_flag=fold_to_3bet param to GET /api/hands.
  3. Dual color system conflict — benchmark-based background tints vs. existing H2N-style text coloring.
  Decide: replace or layer?

  Other notes: Missing benchmarks for ~15 stats. Rush & Cash benchmarks may differ from standard 6-max.
  Consider user-editable ranges.

  ---
  M2: Study Spots — Excellent, most detailed PRD. ~30% effort underestimate
  ┌─────────────────────────────┬──────────────────────────────┐
  │           Aspect            │            Rating            │
  ├─────────────────────────────┼──────────────────────────────┤
  │ Completeness                │ Very thorough                │
  ├─────────────────────────────┼──────────────────────────────┤
  │ Alignment with PRD_STATS_V2 │ Perfect (supersedes it)      │
  ├─────────────────────────────┼──────────────────────────────┤
  │ Effort estimate             │ 34-48 days (spec says 26-39) │
  └─────────────────────────────┴──────────────────────────────┘
  Key concerns:
  1. Monolithic detail endpoint — computing hand strength + board texture + sizing + EV + trend in one
  request could be 3-5 seconds. Split into /summary, /hands, /analysis, /trend for progressive loading.
  2. Some "NEW" stats already exist — limp_fold, four_bet_fold, call_4bet, call_cbet_flop, raise_cbet_flop
  are already in stat_flags.py. Update the PRD.
  3. Float definition is inconsistent — spec says "IP flop call" but that's not a float (a float requires a
   follow-up turn bet). Clarify.
  4. T-9 vs Bxx texture overlap — T is a Broadway card but T-9 High is a separate category. Need explicit
  priority order.
  5. Pre-compute hand strength during insert rather than on-demand — on-demand evaluation of 5000 hands per
   detail click is slow.

  ---
  M3: Track Progress — Well-structured, some features already exist
  ┌─────────────────┬─────────────────────────────────────────────────────────────────────┐
  │     Aspect      │                               Rating                                │
  ├─────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Completeness    │ Good                                                                │
  ├─────────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Effort estimate │ Accurate (M3.4 overestimated since session markers + CI band exist) │
  └─────────────────┴─────────────────────────────────────────────────────────────────────┘
  Key concerns:
  1. Session gap inconsistency — existing code uses 10 minutes (reports.py), PRD specs 30 minutes. Will
  show different session counts on different pages. Reconcile.
  2. M3.4 features already built — session markers on graph and CI band already implemented. Mark as
  "Done."
  3. Annotation CRUD is completely unspecified — no endpoint paths, no creation flow UI, no CRUD operations
   detailed.
  4. Comparison direction logic is ambiguous — for stats like VPIP where both too high/low are bad,
  "improving" depends on which side of the benchmark you're on. Need per-stat direction config.
  5. DuckDB INTEGER PRIMARY KEY doesn't auto-increment — annotations table schema needs a sequence.
  6. Dependencies on M1.1 benchmarks not called out — trends and comparison both need benchmark ranges.

  ---
  M4: Know Opponents — Highest quality PRD. P1 and P6 underestimated
  ┌───────────────────────────────┬──────────────────────────────┐
  │            Aspect             │            Rating            │
  ├───────────────────────────────┼──────────────────────────────┤
  │ Completeness                  │ Excellent                    │
  ├───────────────────────────────┼──────────────────────────────┤
  │ Alignment with PRD_POPULATION │ Perfect (supersedes it)      │
  ├───────────────────────────────┼──────────────────────────────┤
  │ Effort estimate               │ 42-58 days (spec says 35-46) │
  └───────────────────────────────┴──────────────────────────────┘
  Key concerns:
  1. T/Broadway classification ambiguity — same as M2. T-9 High boards overlap with Bxx definition.
  2. is_3bet_pot column already exists — conflicts with new pot_type VARCHAR. Need migration strategy to
  deprecate old column.
  3. 3-Bet matrix query missing three_bet_opp filter — self-join denominator includes all players, not just
   those with opportunity to 3-bet.
  4. Population queries at scale — 6x6 self-joins on 6M rows could be slow. Need fallback plan
  (materialized views).
  5. Small database problem — at 10K-50K hands, most population cells will be yellow/red. Need "Data
  Sufficiency" indicator.
  6. Soft dependency on M2.2 not called out — population sections reference check-raise/probe stats that
  need M2.2's new flags.

  ---
  M5: Go Deep — Well-researched. Two code bugs, effort ~30-50% over
  ┌─────────────────┬───────────────────────────────────┐
  │     Aspect      │              Rating               │
  ├─────────────────┼───────────────────────────────────┤
  │ Completeness    │ Very good                         │
  ├─────────────────┼───────────────────────────────────┤
  │ Spec quality    │ Very high (includes working code) │
  ├─────────────────┼───────────────────────────────────┤
  │ Effort estimate │ 66-89 days (spec says 51-67)      │
  └─────────────────┴───────────────────────────────────┘
  Critical bugs in pseudocode:
  1. Pot tracking bet_pct_pot uses raise-to amount instead of increment. Must use increment / pot_before.
  2. Blind initialization missing — street_investments not seeded with SB/BB amounts for preflop.
  3. Turn classifier priority order bug — code checks paired_board before completed_draw, contradicting
  stated priority.

  Other concerns:
  - On-demand hand strength eval for 5000 hands = ~2.5 seconds per click. Pre-compute during insert
  instead.
  - parsed.all_actions doesn't exist on ParsedHand dataclass. Need to flatten actions_by_street.
  - Do all schema changes + one rebuild, not phased rebuilds.
  - Situational views navigation location unspecified.

  ---
  M6: Platform — Good overall. Electron significantly underspecified
  ┌─────────────────┬──────────────────────────────┐
  │     Aspect      │            Rating            │
  ├─────────────────┼──────────────────────────────┤
  │ Completeness    │ Good (except M6.3)           │
  ├─────────────────┼──────────────────────────────┤
  │ Effort estimate │ 34-50 days (spec says 27-38) │
  └─────────────────┴──────────────────────────────┘
  Key concerns:
  1. M6.3 (Electron) has no Technical Spec section — no IPC protocol, no health check, no shutdown
  handling, no code signing. Needs another pass. Effort is 12-18 days, not 7-10.
  2. DuckDB concurrency with auto-import — background watcher writing while user queries = lock contention.
   Batch size and lock strategy need specification.
  3. ParsedHand needs to move to shared module — currently in ggpoker.py, must move for multi-parser
  support. Not called out as prerequisite.
  4. File offset tracking > full-file hashing for auto-import. GGPoker appends to files, so re-hashing
  wastes work.
  5. Hand ID collision risk — prefix with site code (GG_, PS_) to prevent cross-site ID overlap.
  6. Consider Tauri over Electron — 10-50x smaller bundles, native webview, worth evaluating.

  ---
  Cross-Cutting Issues (Appear in Multiple PRDs)
  Issue: T-9 vs Bxx board texture overlap
  Affected PRDs: M2, M4, M5
  Fix: Add explicit priority: A > T-9 > B > 8-2
  ────────────────────────────────────────
  Issue: is_3bet_pot vs pot_type column overlap
  Affected PRDs: M4, M5
  Fix: Deprecate is_3bet_pot, migrate to pot_type
  ────────────────────────────────────────
  Issue: Pot tracking code bugs
  Affected PRDs: M5 (shared infra used by M2, M4)
  Fix: Fix bet_pct_pot and blind initialization
  ────────────────────────────────────────
  Issue: Pre-compute vs on-demand hand strength
  Affected PRDs: M2, M4, M5
  Fix: Pre-compute during insert (store on hand_players)
  ────────────────────────────────────────
  Issue: Single rebuild strategy
  Affected PRDs: M2, M4, M5
  Fix: Batch all schema changes, rebuild once
  ────────────────────────────────────────
  Issue: DuckDB single-writer concurrency
  Affected PRDs: M4, M6
  Fix: Small batch sizes, explicit lock strategy
  ────────────────────────────────────────
  Issue: Benchmarks dependency
  Affected PRDs: M1, M3
  Fix: M3 needs M1.1 benchmarks for trends/comparison