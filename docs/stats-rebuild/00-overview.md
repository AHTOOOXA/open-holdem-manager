# Stats Page Rebuild — Overview

## Goal

Rebuild the Stats page to surface positional breakdowns for key stats currently hidden in flat KV grids, add new stats (BB Defense, Iso Raise, Check-Raise, C-Bet by pot type), and introduce two new detail-page widgets (PvP Matrix, IP/OOP Split).

Nothing is removed. Every existing stat cell, benchmark, and drill-down route is preserved.

## Phase Summary

| Phase | Name | Scope | Effort | Dependencies |
|-------|------|-------|--------|-------------|
| 1 | Promote Positional | Frontend only | Small | None |
| 2 | Steal CO Column | Frontend only | Tiny | None |
| 3 | Promote BB Defense / Iso Raise / Squeeze | Backend + Frontend | Medium | None |
| 4 | C-Bet by Pot Type + Positional | Backend + Frontend | Medium | None |
| 5 | Check-Raise Stat Flags | Full stack (DB + stat_flags + engine + API + UI) | Large | None |
| 6 | PvP Matrix Widget | Backend endpoint + Frontend widget | Medium | Weak dep on Phase 3 (bb_defense positional) |
| 7 | IP/OOP Split Widget | Backend filter + Frontend widget | Medium | Weak dep on Phase 5 (check-raise) |

## Dependency Graph

```
Phase 1 ─┐
Phase 2 ─┤
Phase 3 ─┼──→ Phase 6 (PvP uses bb_defense positional data)
Phase 4 ─┤
Phase 5 ─┴──→ Phase 7 (IP/OOP uses check-raise flags)
```

Phases 1-5 are fully independent and can be implemented in parallel.
Phase 6 benefits from Phase 3 being done (bb_defense as PositionalStats).
Phase 7 benefits from Phase 5 being done (check-raise flags exist for IP/OOP split).

## Implementation Order (Recommended)

1. **Phases 1 + 2** first — frontend-only, zero risk, immediately visible improvement
2. **Phases 3 + 4** next — backend model changes that reshape HeroStats
3. **Phase 5** — the heaviest lift (new DB columns, stat_flags logic, rebuild)
4. **Phase 6 + 7** last — new widgets that consume data from earlier phases

## Key Files Touched (Cross-Phase)

| File | Phases |
|------|--------|
| `frontend/src/pages/StatsPage.tsx` | 1, 2, 3, 4, 5 |
| `frontend/src/lib/api.ts` | 3, 4, 5, 6, 7 |
| `frontend/src/lib/stat-registry.ts` | 1, 3, 4, 5, 6, 7 |
| `frontend/src/lib/benchmarks.ts` | 1, 3, 5 |
| `backend/app/models.py` | 3, 4, 5, 6, 7 |
| `backend/app/stats_engine.py` | 3, 4, 5 |
| `backend/app/stat_registry.py` | 4, 5, 6 |
| `backend/app/api/stats.py` | 4, 5, 6, 7 |
| `backend/app/db.py` | 5 |
| `backend/app/stat_flags.py` | 5 |
| `backend/app/api/import_hands.py` | 5 |

## Design Spec Reference

Full layout spec: `docs/stats-page-redesign.md`

## Verification Strategy

Each phase includes its own verification steps. Cross-phase integration testing:

1. After all phases: load Stats page, confirm all sections render without errors
2. Click every stat cell → confirm drill-down page loads with correct widgets
3. Filter by stakes/date → confirm all sections respond to filters
4. Import fresh hands → confirm new stat flags (Phase 5) compute correctly
5. Run `python -m pytest tests/test_parser.py -v` → all existing tests pass
