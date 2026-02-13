# Stats Page Rebuild — Overview

## Goal

Rebuild the Stats page so coaches and students can immediately identify positional leaks — the #1 use case for a tracking tool. Promote key stats (VPIP, PFR, 4-Bet, Limp) from flat KV grids into the positional table, add new stats (BB Defense, Iso Raise, Check-Raise, C-Bet by pot type), and introduce two new detail-page widgets (IP/OOP Split, PvP Matrix).

Nothing is removed. Every existing stat cell, benchmark, and drill-down route is preserved.

## Cross-Phase Concerns

**Sample size warnings**: Stats with fewer than ~30 opportunities are unreliable. Every phase that renders stat values must show muted/dimmed display and a subscript sample count when the sample is below a configurable threshold (default: 30). This is not optional — showing low-sample stats at full confidence is a coaching anti-pattern that leads students to over-adjust based on noise.

**Multiway vs heads-up**: The `is_multiway` flag already exists in `hand_players`. Postflop stats (c-bet, fold-to-cbet, check-raise) differ massively between heads-up and multiway pots. Phase 4 and Phase 5 should expose a multiway filter or at minimum note this as a follow-up. Coaches frequently need to separate these when diagnosing postflop leaks.

## Phase Summary

| Phase | Name | Scope | Effort | Dependencies |
|-------|------|-------|--------|-------------|
| 1 | Promote Positional | Frontend only | Small | None |
| 2 | Steal CO Column | Backend (1-line fix) + Frontend | Tiny | None |
| 3 | Promote BB Defense / Iso Raise / Squeeze | Backend + Frontend | Medium | None |
| 4 | C-Bet by Pot Type + Positional | Backend + Frontend | Medium | None |
| 5 | Check-Raise + Fold to Check-Raise | Full stack (DB + stat_flags + engine + API + UI) | Large | None |
| 6 | IP/OOP Split Widget | Backend filter + Frontend widget | Medium | Benefits from Phase 5 (check-raise flags) |
| 7 | PvP Matrix Widget | Backend endpoint + Frontend widget | Medium | Benefits from Phase 3 (bb_defense positional) |

## Dependency Graph

```
Phase 1 ─┐
Phase 2 ─┤
Phase 3 ─┼──→ Phase 7 (PvP uses bb_defense positional data)
Phase 4 ─┤
Phase 5 ─┴──→ Phase 6 (IP/OOP uses check-raise flags)
```

Phases 1-5 are fully independent and can be implemented in parallel.
Phase 6 (IP/OOP Split) benefits from Phase 5 being done (check-raise flags exist for IP/OOP split). **This is the higher-priority widget** — a coach uses IP/OOP c-bet splits daily; PvP matrices are for deeper analysis.
Phase 7 (PvP Matrix) benefits from Phase 3 being done (bb_defense as PositionalStats).

## Implementation Order (Recommended)

1. **Phases 1 + 2** first — mostly frontend, near-zero risk, immediately visible improvement. Phase 2 includes a trivial backend fix (adding CO to three `_pos_steal` position lists).
2. **Phases 3 + 4** next — backend model changes that reshape HeroStats
3. **Phase 5** — the heaviest lift (new DB columns, stat_flags logic, rebuild). Must include Fold to Check-Raise alongside Check-Raise — tracking one without the other is useless for coaching. Over-folding to check-raises is one of the biggest leaks at low/mid stakes.
4. **Phase 6** (IP/OOP Split) before Phase 7 (PvP Matrix) — IP/OOP splits are used in every single coaching session to diagnose c-bet and defense leaks. PvP Matrix is for deeper positional matchup analysis and can wait.

## Key Files Touched (Cross-Phase)

| File | Phases |
|------|--------|
| `frontend/src/pages/StatsPage.tsx` | 1, 2, 3, 4, 5 |
| `frontend/src/lib/api.ts` | 3, 4, 5, 6, 7 |
| `frontend/src/lib/stat-registry.ts` | 1, 3, 4, 5, 6, 7 |
| `frontend/src/lib/benchmarks.ts` | 1, 3, 5 |
| `backend/app/models.py` | 3, 4, 5, 6, 7 |
| `backend/app/stats_engine.py` | 2, 3, 4, 5 |
| `backend/app/stat_registry.py` | 4, 5, 7 |
| `backend/app/api/stats.py` | 4, 5, 6, 7 |
| `backend/app/db.py` | 5 |
| `backend/app/stat_flags.py` | 5 |
| `backend/app/api/import_hands.py` | 5 |

## Design Spec Reference

Full layout spec: `docs/stats-page-redesign.md`

## What's Not in Scope (Future Work)

The following are important coaching features that are deliberately deferred but should be tracked:

- **Multiway postflop splits**: C-bet and fold-to-cbet in multiway pots vs heads-up. The `is_multiway` flag exists in the DB. This is a high-value coaching filter — c-bet frequency should drop significantly in multiway pots, and students who don't adjust are lighting money on fire.
- **Probe bet as a first-class stat row**: The backend already computes `vs_missed_cbet` data (betting into the previous aggressor when they miss a c-bet). This should eventually get its own row in the postflop grid rather than living only in the detail widgets.
- **BB Defense breakdown by raiser position (non-matrix)**: The PvP matrix covers this, but coaches often want a quick flat view: "BB defense vs EP open = 38%, vs BTN open = 62%". Consider a dedicated widget or stat variant.
- **Turn and river c-bet by pot type**: Phase 4 only adds flop c-bet SRP/3BP. Turn and river pot-type splits matter for barrel analysis but are lower frequency.
- **Positional win rates (bb/100 by position)**: Not a stat flag issue, but surfacing bb/100 per position on the Stats page would let students immediately see which positions are profitable and which are bleeding.

## Verification Strategy

Each phase includes its own verification steps. Cross-phase integration testing:

1. After all phases: load Stats page, confirm all sections render without errors
2. Click every stat cell → confirm drill-down page loads with correct widgets
3. Filter by stakes/date → confirm all sections respond to filters
4. Import fresh hands → confirm new stat flags (Phase 5) compute correctly
5. Run `python -m pytest tests/test_parser.py -v` → all existing tests pass
6. **Accuracy check**: For at least 3 stats (VPIP, 3-Bet, C-Bet Flop), manually verify the positional numbers against a hand-counted sample of 20+ hands. Automated tests catch regressions but not systematic miscounting.
7. **Sample size display**: Verify that stats with <30 sample opportunities render with dimmed/muted styling across all views (PosTable, detail pages, widgets)
