# Manual Testing — User Stories

Comprehensive test plan for Workspaces, Checkpoints, Compare, Player Identities, and Analysis Views.

**Prerequisites**: Start with `make dev`. Have at least one `.txt` hand history file ready for import.

---

## 1. Fresh Start & Migration

### 1.1 First launch on clean DB
- [ ] Delete `data/poker.duckdb` if present
- [ ] Run `make dev`
- [ ] Verify app loads at `localhost:4242` with no errors
- [ ] Verify default workspace "My Game" exists in sidebar switcher
- [ ] Verify default view "My Stats" exists in sidebar switcher
- [ ] Navigate to `/settings/workspaces` — confirm one workspace card with hero "Hero"
- [ ] Navigate to `/settings/views` — confirm one view card "My Stats" (Single Player)
- [ ] Check Swagger at `localhost:4243/docs` — all new endpoints listed

### 1.2 Migration from existing DB (if available)
- [x] Start with a pre-existing `poker.duckdb` that has hands but no workspaces table
- [x] Run `make dev` — verify migration runs (check backend logs for "Running workspace migration...")
- [x] Verify all existing hands appear under workspace "My Game"
- [x] Verify hero username carried over into the workspace (sidebar footer shows the correct name)
- [x] Click hero name in sidebar footer → change it → verify it saves per-workspace
- [x] Restart backend again — verify migrations are idempotent (no duplicate inserts)

---

## 2. Workspaces

### 2.1 Create workspace
- [ ] Open sidebar switcher dropdown → "Manage Workspaces"
- [ ] Note: only the "My Game" card exists, no delete button (can't delete last workspace)
- [ ] Open sidebar switcher dropdown → ~~"New Workspace"~~ (this was removed in ViewSwitcher — use Manage Workspaces page or create via View Builder)
- [ ] Go to `/settings/workspaces` → click pencil menu on "My Game" → "Edit Workspace"
- [ ] Verify form has Name, Hero Username, Description, Color fields
- [ ] Cancel → confirm nothing changed

### 2.2 Workspace CRUD via API (Swagger)
- [ ] `POST /api/workspaces` with `{"name": "NL50 Grind", "hero_username": "TestHero"}`
- [ ] Verify 201 response with generated id, hand_count=0, date_range nulls
- [ ] `GET /api/workspaces` — verify both workspaces listed
- [ ] `PATCH /api/workspaces/{id}` — update name, verify response
- [ ] Sidebar switcher now shows both workspaces (via views or direct)

### 2.3 Workspace isolation
- [ ] Import hands into workspace 1 (default "My Game")
- [ ] Switch to the second workspace (if created via API)
- [ ] Stats page → shows 0 hands, empty state
- [ ] Results graph → empty
- [ ] Hands browser → empty
- [ ] Sessions → empty
- [ ] Switch back to workspace 1 → all data present
- [ ] Import hands into workspace 2 → verify they appear only in workspace 2

### 2.4 Workspace settings page
- [ ] `/settings/workspaces` — verify card shows: name, hero, hand count, date range
- [ ] Active workspace has "Active" badge and ring highlight
- [ ] Non-active workspace shows "Switch" button
- [ ] Click "Switch" → workspace changes, all pages reload data
- [ ] Edit workspace: change name, hero, color → save → verify card updates
- [ ] Edit workspace: set description → verify it shows on card
- [ ] Verify color dot in card matches selected color

### 2.5 Delete workspace
- [ ] With 2+ workspaces, click pencil → "Delete Workspace" on non-active one
- [ ] Verify confirmation dialog asks to type workspace name
- [ ] Type wrong name → Delete button stays disabled
- [ ] Type correct name → Delete button enabled
- [ ] Confirm delete → workspace removed, hands gone
- [ ] With only 1 workspace left → verify delete option is hidden

### 2.6 Delete active workspace
- [ ] Create 2 workspaces, switch to the second one
- [ ] Delete the active workspace
- [ ] Verify app switches to the remaining workspace automatically
- [ ] All pages show the remaining workspace's data

### 2.7 Sidebar footer reads from workspace
- [ ] Verify sidebar footer shows hero username from the active workspace (not from settings table)
- [ ] Switch workspace → footer updates to show new workspace's hero

---

## 3. Checkpoints

### 3.1 Create checkpoint via settings page
- [ ] `/settings/workspaces` → pencil menu → "Add Checkpoint"
- [ ] Dialog shows: Name (required), Date (defaults to today), Note (optional)
- [ ] Enter name, pick a date in the past, add a note → Create
- [ ] Checkpoint appears under the workspace card in the checkpoints section
- [ ] Create another checkpoint with different date

### 3.2 Create checkpoint via FilterBar
- [ ] Go to Results graph page
- [ ] In FilterBar, find the checkpoint/since dropdown
- [ ] Select "+ New Checkpoint" option
- [ ] Dialog opens with name + date fields
- [ ] Create checkpoint → dropdown now shows it
- [ ] Select the new checkpoint → graph filters to hands after that date

### 3.3 Checkpoint CRUD
- [ ] On workspace settings page, hover a checkpoint → edit/delete buttons appear
- [ ] Edit checkpoint: change name, date, note → Save
- [ ] Verify changes reflected in settings page and FilterBar dropdown
- [ ] Delete checkpoint (single click, no confirmation) → disappears
- [ ] Verify deleted checkpoint no longer in FilterBar dropdown

### 3.4 Checkpoint reference lines on graph
- [ ] Create 2-3 checkpoints with dates within your hand history range
- [ ] Go to Results graph page
- [ ] Verify vertical reference lines appear at checkpoint dates
- [ ] Hover/check that lines are at correct x-positions
- [ ] Delete a checkpoint → line disappears on next graph load

### 3.5 Checkpoint filtering ("Since")
- [ ] On Stats page, select a checkpoint from the "Since" dropdown
- [ ] Verify stats recalculate using only hands after the checkpoint date
- [ ] Hand count should be lower than "All Time"
- [ ] Select "All Time" → full stats return
- [ ] Try on Results graph, Hands browser — same filtering behavior

### 3.6 Edge cases
- [ ] Create checkpoint with future date → appears in dropdown, filters to 0 hands
- [ ] Create checkpoint with very long name → truncation in dropdown
- [ ] Checkpoints only visible for the active workspace's card (non-active cards show no checkpoints section)
- [ ] Switching workspaces → checkpoint dropdown updates to new workspace's checkpoints

---

## 4. Compare Stats

### 4.1 Basic comparison
- [ ] Navigate to Compare page (sidebar → Tools → Compare)
- [ ] Verify two period selectors (A and B) with date pickers
- [ ] Set Period A: a date range covering your first half of hands
- [ ] Set Period B: a date range covering your second half
- [ ] Stats table appears with columns: Stat, Period A, Period B, Delta
- [ ] Verify deltas are color-coded (green = improvement on positive stats, red = decline)

### 4.2 Checkpoint quick-select
- [ ] Create a checkpoint at the midpoint of your data
- [ ] On Compare page, click checkpoint button for Period A → sets "to" date
- [ ] Click checkpoint button for Period B → sets "from" date
- [ ] Verify comparison loads with data split at checkpoint date
- [ ] Change checkpoint → dates update and stats reload

### 4.3 Filters
- [ ] Apply stakes filter → comparison scoped to those stakes
- [ ] Apply game mode filter (if multiple modes exist)
- [ ] Verify both periods respect the filter
- [ ] Clear filters → full comparison returns

### 4.4 Empty & edge states
- [ ] Set Period A to a range with 0 hands → verify graceful handling
- [ ] Set both periods to the same range → comparing stats with themselves (all deltas = 0)
- [ ] Set invalid range (From > To) → verify no crash
- [ ] Low sample size (< 10k hands) → verify warning or muted deltas
- [ ] No checkpoints → checkpoint buttons should be absent/hidden

### 4.5 Stat categories
- [ ] Verify preflop stats section: VPIP, PFR, 3Bet, etc.
- [ ] Verify postflop stats section: CBet, fold-to-CBet, etc.
- [ ] Verify showdown stats section: WTSD, WSD, WWSF
- [ ] Verify win rates section: bb/100, EV bb/100

---

## 5. Player Identities

### 5.1 Create identity from Players page
- [ ] Navigate to Players page
- [ ] Find a player in the table → click the link/identity button (UserPlus icon)
- [ ] Dialog opens in "select" mode — if no identities, shows "No identities yet"
- [ ] Click "Create New Identity"
- [ ] Name pre-fills with player's username
- [ ] Modify name if desired → "Create & Link"
- [ ] Identity created and player linked as alias

### 5.2 Link additional players
- [ ] Find another player → click link button
- [ ] Dialog shows existing identities in "select" mode
- [ ] Click an existing identity → player linked
- [ ] Identity card now shows 2 aliases
- [ ] Verify the link button disappears for already-linked players

### 5.3 Identity list on Players page
- [ ] Identity cards appear at the top of the Players page
- [ ] Each card shows: display name, color dot (if set), tags, linked player usernames
- [ ] Click an identity card → navigates to `/players/identity/{id}`

### 5.4 Identity detail page
- [ ] On identity detail page, verify: name, notes, color, tags sections
- [ ] Edit display name → save → verify updated
- [ ] Add/remove tags → verify badge updates
- [ ] Change color → verify dot updates
- [ ] Add notes → verify saved

### 5.5 Alias management
- [ ] On identity detail page, verify linked aliases listed (username + workspace name)
- [ ] Unlink an alias → player freed (link button reappears on Players page)
- [ ] Identity with 0 aliases → still exists, shows "No linked players"

### 5.6 Identity stats
- [ ] On identity detail page, verify aggregated stats across all linked aliases
- [ ] Link players from 2 different workspaces → stats should sum across both
- [ ] Verify hand count = sum of all aliased players' hands

### 5.7 Tag management
- [ ] Create identity with tags: "reg", "fish"
- [ ] On Players page, tag filter buttons appear
- [ ] Click "reg" filter → only identities tagged "reg" shown
- [ ] Click again to deselect → all shown
- [ ] Identity with no matching tag → hidden when filter active

### 5.8 Edge cases
- [ ] Try linking same player twice → should fail/show error ("Player may already be linked")
- [ ] Create identity with empty name → verify behavior (should use player name or reject)
- [ ] Delete identity → aliases freed, removed from Players page
- [ ] Identity with very many aliases (5+) → layout handles gracefully

---

## 6. Population Exclusions

### 6.1 Exclude by identity
- [ ] Navigate to Population page
- [ ] Verify exclusion controls panel exists
- [ ] Create identities for known players (friends, your own alt accounts)
- [ ] Check identity checkboxes in exclusion panel
- [ ] Verify population stats recalculate without excluded players
- [ ] Player count in overview should decrease
- [ ] Uncheck → stats return to full population

### 6.2 Exclude by tag
- [ ] Tag identities (e.g., "reg", "fish")
- [ ] On Population page, check tag exclusion checkboxes
- [ ] Verify all players with that tag excluded from analysis
- [ ] Combine identity + tag exclusions → both applied

### 6.3 Exclusion across population sub-pages
- [ ] With exclusions active, check each sub-section:
  - Overview (player count, observation count)
  - Preflop tendencies
  - Postflop lines
  - Segments
  - Showdown stats
  - Pot types
  - HU vs Multiway
  - Hero vs Population comparison
- [ ] All sub-sections should respect the same exclusions

### 6.4 Edge cases
- [ ] Exclude all identities → should still show non-identified players
- [ ] No identities or tags exist → exclusion panel shows empty message
- [ ] Exclude hero's identity from population → verify hero not double-excluded

---

## 7. Analysis Views

### 7.1 Default view
- [ ] On first load, "My Stats" view active in sidebar
- [ ] Icon is BarChart3 (single player type)
- [ ] All pages show data from workspace 1

### 7.2 View switcher (expanded sidebar)
- [ ] Click view switcher → dropdown shows:
  - "Views" label
  - "My Stats" with checkmark (active)
  - Separator
  - "+ New View" link
  - "Manage Views" link
  - Separator
  - "Manage Workspaces" link
- [ ] Click "Manage Views" → navigates to `/settings/views`
- [ ] Click "Manage Workspaces" → navigates to `/settings/workspaces`

### 7.3 View switcher (collapsed sidebar)
- [ ] Collapse sidebar → switcher shows icon-only button
- [ ] Hover → tooltip shows view name
- [ ] Click → same dropdown opens to the right
- [ ] All actions work same as expanded

### 7.4 Create view — Single Player
- [ ] Click "+ New View" or go to `/settings/views/new`
- [ ] Fill in name: "NL25 Grind"
- [ ] Check one workspace in data sources
- [ ] Select "Single Player" (default)
- [ ] If identities exist: hero identity dropdown shows "Use workspace hero" + identity list
- [ ] Leave as "Use workspace hero"
- [ ] Optionally set default stakes
- [ ] Click "Create View"
- [ ] Redirected to `/settings/views` — new view in list
- [ ] View appears in sidebar switcher

### 7.5 Create view — Population
- [ ] Create new view, select "Population" type
- [ ] Check workspace sources
- [ ] Exclusions section appears:
  - Identity checkboxes (if identities exist)
  - Tag checkboxes (if tags exist on identities)
  - "No identities or tags" message if none
- [ ] Check some exclusions
- [ ] Save → view created with exclusion config

### 7.6 Create view — Compare Players
- [ ] Create new view, select "Compare Players" type
- [ ] Compare Identities section appears
- [ ] Check 2 identities (min for meaningful comparison)
- [ ] Try checking a 4th → checkbox disabled at 3 max
- [ ] Save → view created

### 7.7 Edit view
- [ ] On `/settings/views`, click pencil on a view → navigates to edit page
- [ ] Form pre-fills with existing values
- [ ] Change name, toggle a workspace source, change type
- [ ] Type change: verify old type-specific fields clear (e.g., switching from single_player to population clears hero_identity_id)
- [ ] Save → changes persisted

### 7.8 Delete view
- [ ] On `/settings/views`, click trash icon on a non-active view
- [ ] Confirmation dialog appears
- [ ] Cancel → nothing happens
- [ ] Confirm → view deleted
- [ ] With only 1 view → delete button hidden

### 7.9 Delete active view
- [ ] Make a second view, switch to it
- [ ] Delete it → app switches to the first remaining view
- [ ] All pages reload with new view's context

### 7.10 Switch view → data context changes
- [ ] Create 2 views pointing to different workspaces
- [ ] Switch between them via sidebar
- [ ] Verify Stats page shows different data for each
- [ ] Verify Results graph changes
- [ ] Verify hand count in sidebar/health changes
- [ ] Check localStorage: `ohm_active_view_id` and `ohm_active_workspace_id` both update

### 7.11 View settings page
- [ ] `/settings/views` shows all views as cards
- [ ] Each card shows: grip handle, type icon, name, type badge, source workspace names
- [ ] Active view has "Active" badge and ring highlight
- [ ] Non-active views show "Switch" button
- [ ] Click "New View" button → navigates to builder

### 7.12 Edge cases
- [ ] Create view with no workspaces selected → Save button disabled
- [ ] Create view with empty name → Save button disabled
- [ ] Create view, then delete its source workspace → view still exists but sources show "None"
- [ ] Create compare view with 0 identities → save succeeds (empty array)
- [ ] Rapidly switch views → no stale data flashes
- [ ] Reload page with a saved view → correct view restored from localStorage

---

## 8. Cross-Feature Integration

### 8.1 Import respects active workspace
- [ ] Switch to workspace 2
- [ ] Import hands
- [ ] Verify hands appear in workspace 2 only
- [ ] Switch to workspace 1 → imported hands not there

### 8.2 Checkpoint + Compare workflow
- [ ] Import 100+ hands
- [ ] Create checkpoint "Strategy Change" at midpoint date
- [ ] Go to Compare → use checkpoint for period split
- [ ] Verify Period A (before) and Period B (after) show different stats

### 8.3 Identity + Population exclusion workflow
- [ ] Create identity "My Friend" → link a known player
- [ ] Tag it as "friend"
- [ ] Go to Population → exclude tag "friend"
- [ ] Verify friend's hands excluded from population stats
- [ ] Remove exclusion → stats include friend again

### 8.4 View with all features
- [ ] Create a Population view with:
  - 2 workspace sources
  - Exclusions: 1 identity + 1 tag
  - Default stakes filter
  - Default checkpoint
- [ ] Switch to this view
- [ ] Go to Population page → verify exclusions pre-applied
- [ ] Verify stakes filter reflects the default

### 8.5 Sidebar navigation consistency
- [ ] Navigate: Stats → Results → Hands → Sessions → Cash Drop → Players → Population → Compare
- [ ] At each page, verify the correct view/workspace context applies
- [ ] Switch view mid-navigation → current page reloads with new context
- [ ] Breadcrumbs show correct path at all times

### 8.6 Settings navigation
- [ ] Sidebar → "Manage Views" → `/settings/views` page
- [ ] Sidebar → "Manage Workspaces" → `/settings/workspaces` page
- [ ] From view settings → "New View" → builder page → back arrow → back to list
- [ ] Breadcrumbs: Settings > Views > New View (correct hierarchy)
- [ ] Breadcrumbs: Settings > Views > Edit View (when editing)

---

## 9. Persistence & State

### 9.1 LocalStorage persistence
- [ ] Select a non-default view → reload page → same view active
- [ ] Select a non-default workspace → reload → same workspace active
- [ ] Clear localStorage → reload → defaults to view 1, workspace 1

### 9.2 Multi-tab behavior
- [ ] Open app in 2 browser tabs
- [ ] Switch view in tab 1 → tab 2 still shows old view (localStorage read on mount only)
- [ ] Refresh tab 2 → now shows same view as tab 1

### 9.3 Backend restart
- [ ] With data loaded, stop and restart backend
- [ ] Verify all workspaces, checkpoints, identities, views preserved
- [ ] Migrations should be no-ops (check logs for absence of migration messages)

---

## 10. Error Handling & Edge Cases

### 10.1 API errors
- [ ] Stop backend → try switching workspace → verify graceful error (no white screen)
- [ ] Start backend → app recovers, data loads

### 10.2 Empty database
- [ ] Fresh DB, no imports
- [ ] All pages show empty states correctly
- [ ] Compare page → "Select date ranges" prompt
- [ ] Population → low/no data message
- [ ] Can still create workspaces, checkpoints, identities, views

### 10.3 Large data
- [ ] Import 10,000+ hands
- [ ] Verify workspace hand_count is correct
- [ ] Verify checkpoint filtering is fast
- [ ] Compare page loads within reasonable time
- [ ] Population analysis handles large player pool

### 10.4 Concurrent operations
- [ ] Import hands while viewing stats → stats should refresh after import completes
- [ ] Create checkpoint while on graph page → reference line appears on reload
- [ ] Delete workspace while another page is loading its data → no crash
