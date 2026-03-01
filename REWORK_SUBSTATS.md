# Rework: Stat Detail Subpages

## Why

The current stat detail (substat) pages have 18 widget components that are half-baked. ~25 stats show nothing but a trend sparkline. The "rich" widgets (range heatmap, composition, ev breakdown, etc.) work technically but produce mediocre analysis that doesn't match what a coach would actually want to see. Two major planned widgets (PvP Matrix, IP/OOP Split) were never built.

Rather than polish mediocre widgets, we're stripping them all out and shipping subpages as **header + hand explorer only**. This is honest — the hand list is the most useful thing anyway. Widgets will be rebuilt properly later with a clear spec per stat.

## What Was Removed

### Frontend

- All 17 widget components in `frontend/src/components/stats/widgets/` (except `AnalysisWidgets.tsx` which was gutted)
- Widget type definitions and registry mappings in `frontend/src/lib/stat-registry.ts`
- Widget-related API functions in `frontend/src/lib/api.ts` (`getStatTrend`, `getStatAnalysis`, `getStatRange`, `getEvBreakdown`, `getSizing`, `getFoldEquity`, `getByContext`, `getComposition`, `getMoney`, `getPostflopBridge`, `getContinuingRange`, `getRangeStats`)
- Widget-related query keys in `frontend/src/lib/query-keys.ts`
- Benchmark data used only by widgets in `frontend/src/lib/benchmarks.ts` (villain response benchmarks)

### Backend

- All `/api/stats/detail/{stat_key}/*` widget endpoints: `/trend`, `/analysis`, `/ev-breakdown`, `/sizing`, `/fold-equity`, `/by-context`, `/composition`, `/money`, `/postflop-bridge`, `/continuing-range`, `/range`
- Associated config dicts: `RESPONSE_DECOMPOSITION`, `EV_BREAKDOWN_CONFIG`, `SIZING_CONFIG`, `FOLD_EQUITY_CONFIG`, `BY_CONTEXT_CONFIG`, `COMPOSITION_CONFIG`, `MONEY_CONFIG`, `POSTFLOP_BRIDGE_CONFIG`
- The `/api/stats/detail/{stat_key}/hands` endpoint stays (used by HandExplorer)

### What stays

- `StatDetailPanel.tsx` — header (stat name, %, action/opp counts) + HandExplorer
- `stat-registry.ts` — display names, `heroStatsField`, `isPositional` (used by main stats page). `widgets` arrays emptied.
- Hand explorer with full filtering (position, stakes, date, tags, stat flags)
- All main stats page functionality (StatsCard, positional tables, etc.)

## What Subpages Look Like Now

```
┌─────────────────────────────────────┐
│ VPIP  EP                            │
│ 24.3%  (1,204 / 4,952)             │
├─────────────────────────────────────┤
│ [Hand Explorer]                     │
│ - Full hand table (cards, actions,  │
│   board, pot, won, EV diff, date)   │
│ - Filters (position, stakes, date,  │
│   tags, stat flags, search)         │
│ - Pagination                        │
│ - Click → hand drawer               │
└─────────────────────────────────────┘
```

## Future Rework Plan

When we rebuild widgets, each stat should get a curated set based on what actually helps a player improve. The design docs in `docs/stats-page-redesign.md` and `docs/stat-detail-panel.md` have the full spec. Key widgets to build properly:

1. **PvP Matrix** — Hero pos x Villain pos heatmap (spec in `docs/stats-page-redesign.md`)
2. **IP/OOP Split** — Side-by-side comparison
3. **Range Heatmap** — 13x13 combo grid (existed, needs better UX)
4. **Trend Sparkline** — Rolling average over time (existed, was fine)
5. **Response Distribution** — Fold/Call/Raise bar (existed, was fine)
6. **EV Breakdown** — bb/100 by scenario (existed, needs validation)

Build them one at a time, validate each with real data, then wire them to the right stats.
