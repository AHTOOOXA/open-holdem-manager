# OHM Feature Build — Implementation Summary

## Overview

Four-phase feature build adding **Workspaces**, **Checkpoints**, **Compare**, **Player Identities**, and **Analysis Views** to Open Holdem Manager. Total: **37 files changed/created**, **~5,200 lines of new code** (3,131 in 12 new files + 2,049 added across 25 modified files).

---

## Phase 1: Workspaces & Checkpoints

Workspaces let users maintain separate hand pools (e.g. different stakes, sites, accounts). Checkpoints mark points in time for "before/after" analysis.

### Database

- **`workspaces` table** — id, name, hero_username, hero_site, description, color, created_at
- **`checkpoints` table** — id, workspace_id FK, name, checkpoint_at, note, created_at
- **`hands.workspace_id`** column added with indexes; all existing hands backfilled to workspace 1
- Idempotent migration in `db.py:_migrate_to_workspaces()` moves legacy `hero_username`/`hero_site` from settings into the default "My Game" workspace

### Backend API

| File | Endpoints |
|------|-----------|
| `api/workspaces.py` (226 lines) | `GET/POST /api/workspaces`, `GET/PATCH/DELETE /api/workspaces/:id` |
| `api/checkpoints.py` (145 lines) | `GET/POST /api/workspaces/:id/checkpoints`, `GET/PATCH/DELETE .../checkpoints/:id` |

- All existing endpoints (`stats`, `reports`, `hands`, `sessions`, `cash_drop`, `population`, `players`, `settings`, `import`) updated to accept `workspace_id` query parameter
- `get_hero_player_id()` and `get_hero_username()` in `db.py` now read from workspace table
- `stats_engine.py` — `compute_hero_stats()` and `compute_player_stats()` scoped by workspace_id

### Frontend

| File | What |
|------|------|
| `WorkspaceContext.tsx` (190 lines) | React context: fetches workspaces/checkpoints, manages activeWorkspaceId in localStorage, provides setters |
| `WorkspaceSwitcher.tsx` (107 lines) | Sidebar dropdown to switch active workspace (later evolved to ViewSwitcher) |
| `WorkspaceSettingsPage.tsx` (508 lines) | Full CRUD for workspaces (edit name/hero/color/description) and checkpoints (create/edit/delete with date picker) |
| `api.ts` | `_addWorkspaceParam()` auto-injects workspace_id into all API calls; workspace/checkpoint CRUD functions |
| `FilterBar.tsx` | Added checkpoint dropdown ("Since") with in-place checkpoint creation |
| `GraphPage.tsx` | Checkpoint reference lines rendered as vertical markers on the results graph |
| `ImportOverlay.tsx` | Shows active workspace context during import |
| `SidebarFooterSettings.tsx` | Reads hero username from workspace instead of legacy settings |
| `AppSidebar.tsx` | WorkspaceSwitcher added to sidebar header; Compare and tools nav sections added |

---

## Phase 2: Compare Stats

Side-by-side stats comparison between two time periods (checkpoint-based or date-range).

### Backend

| File | What |
|------|------|
| `api/compare.py` (108 lines) | `GET /api/compare/stats` — accepts two date ranges, returns `PeriodStats` for each with hand counts, win rates, and full stat breakdown |
| `models.py` | `PeriodStats`, `CompareResponse` Pydantic models |

### Frontend

| File | What |
|------|------|
| `ComparePage.tsx` (481 lines) | Two-column period selectors with checkpoint quick-select buttons, stat diff table with color-coded deltas, expandable stat categories (preflop/postflop/showdown) |

---

## Phase 3: Player Identities & Population Exclusions

Player identities group usernames across workspaces into a single entity with tags. Population analysis gains exclusion controls.

### Database

- **`player_identities` table** — id, display_name, notes, color, tags (JSON), created_at
- **`player_aliases` table** — id, identity_id FK, workspace_id FK, player_id FK, UNIQUE(workspace_id, player_id)
- Idempotent migration in `db.py:_migrate_to_identities()`

### Backend

| File | What |
|------|------|
| `api/identities.py` (293 lines) | Full CRUD for identities + alias linking/unlinking; `GET /api/identities/:id/stats` aggregates stats across all aliased players; tag management via identity updates |
| `api/population.py` | Added `exclude_identity_ids` and `exclude_tags` params to all population endpoints; `_resolve_excluded_player_ids()` resolves identity/tag exclusions to player_id sets |
| `models.py` | `IdentityResponse`, `AliasResponse`, `CreateIdentity`, `UpdateIdentity`, `AddAlias` models |

### Frontend

| File | What |
|------|------|
| `PlayersPage.tsx` (~500 line diff) | Redesigned as identity registry: create identities, link/unlink player aliases from any workspace, tag management, identity list with stats summary |
| `IdentityDetailPage.tsx` (347 lines) | Identity detail view: edit name/notes/color/tags, manage aliases, view aggregated stats |
| `PopulationPage.tsx` | Added exclusion controls panel: checkbox lists for identity exclusions and tag exclusions, passed to all population API calls |
| `api.ts` | Identity CRUD functions, `getIdentityStats()`, population filter params extended with `exclude_identity_ids`/`exclude_tags` |
| `query-keys.ts` | Added `identities.list`, `identities.detail`, `identities.stats` query keys |

---

## Phase 4: Analysis Views

Views are saved analysis configurations that define what data to show (which workspaces, whose stats, what exclusions). They replace raw workspace selection as the primary data context.

### Database

- **`analysis_views` table** — id, name, view_type, source_workspace_ids (JSON), hero_identity_id FK, compare_identity_ids (JSON), exclude_identity_ids (JSON), exclude_tags (JSON), default_stakes, default_checkpoint_id FK, description, sort_order, created_at
- Default "My Stats" view (id=1, type=single_player, source=[1]) created on migration
- Idempotent migration in `db.py:_migrate_to_views()`

### Backend

| File | What |
|------|------|
| `api/views.py` (156 lines) | `GET/POST /api/views`, `GET/PATCH/DELETE /api/views/:id` |
| `models.py` | `ViewResponse`, `CreateView`, `UpdateView` models |

### Frontend

| File | What |
|------|------|
| `WorkspaceSwitcher.tsx` | Evolved from workspace picker to **ViewSwitcher**: shows views with type icons (BarChart3/Users/ArrowLeftRight), dropdown has "New View", "Manage Views", "Manage Workspaces" actions |
| `WorkspaceContext.tsx` | Extended with `views`, `activeViewId`, `activeView`, `setActiveViewId`, `refetchViews`; switching views syncs workspace_id to the view's first source workspace |
| `ViewSettingsPage.tsx` (159 lines) | `/settings/views` — list all views with type badges, switch/edit/delete controls |
| `ViewBuilderPage.tsx` (411 lines) | `/settings/views/new` and `/settings/views/:viewId/edit` — form with: name, description, workspace source checkboxes, analysis type radio (Single Player / Population / Compare Players), type-specific sections (hero identity select, compare identity multi-select 2-3, population exclusion checkboxes for identities + tags), default filters (stakes, checkpoint) |
| `api.ts` | `getViews()`, `createView()`, `updateView()`, `deleteView()` |
| `query-keys.ts` | Added `views.list`, `views.detail` query keys |
| `App.tsx` | Routes for `/settings/views`, `/settings/views/new`, `/settings/views/:viewId/edit` with breadcrumb support |

---

## File Inventory

### New Files (12 files, 3,131 lines)

| File | Lines |
|------|-------|
| `backend/app/api/workspaces.py` | 226 |
| `backend/app/api/checkpoints.py` | 145 |
| `backend/app/api/compare.py` | 108 |
| `backend/app/api/identities.py` | 293 |
| `backend/app/api/views.py` | 156 |
| `frontend/src/contexts/WorkspaceContext.tsx` | 190 |
| `frontend/src/components/WorkspaceSwitcher.tsx` | 107 |
| `frontend/src/pages/WorkspaceSettingsPage.tsx` | 508 |
| `frontend/src/pages/ComparePage.tsx` | 481 |
| `frontend/src/pages/IdentityDetailPage.tsx` | 347 |
| `frontend/src/pages/ViewSettingsPage.tsx` | 159 |
| `frontend/src/pages/ViewBuilderPage.tsx` | 411 |

### Modified Files (25 files, +2,049 / -440 lines)

Backend (9): `db.py`, `main.py`, `models.py`, `stats_engine.py`, `api/cash_drop.py`, `api/hands.py`, `api/import_hands.py`, `api/players.py`, `api/population.py`, `api/reports.py`, `api/sessions.py`, `api/settings.py`, `api/stats.py`

Frontend (12): `App.tsx`, `AppSidebar.tsx`, `FilterBar.tsx`, `ImportOverlay.tsx`, `SidebarFooterSettings.tsx`, `api.ts`, `query-keys.ts`, `CashDropPage.tsx`, `GraphPage.tsx`, `PlayersPage.tsx`, `PopulationPage.tsx`, `StatsPage.tsx`

---

## Architecture Decisions

1. **Workspace isolation via query parameter** — all existing endpoints got `workspace_id` param rather than path-prefix restructuring. Simpler migration, backward compatible (defaults to 1).

2. **JSON columns for lists** — `source_workspace_ids`, `compare_identity_ids`, `exclude_identity_ids`, `exclude_tags` stored as JSON strings in DuckDB VARCHAR columns. Parsed in Python/TypeScript. Avoids junction tables for small lists.

3. **Idempotent migrations** — each migration checks a settings key before running. Safe for repeated app startups. Migration order: workspaces -> identities -> views (views FK to both).

4. **View-driven context** — views abstract over workspaces. Selecting a view sets the underlying workspace_id for backward-compatible data fetching while exposing the full view config for pages that want richer filtering.

5. **Identity aggregation** — identity stats computed by collecting all aliased player_ids across workspaces and summing their hand_players flags. No denormalization needed.
