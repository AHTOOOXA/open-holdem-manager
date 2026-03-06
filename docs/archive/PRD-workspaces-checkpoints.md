# PRD: Workspaces, Checkpoints & Multi-Player Analysis

> **Status**: Draft
> **Author**: Anton + Claude
> **Date**: 2026-02-16
> **App**: Open Holdem Manager (OHM)

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Phased Roadmap Overview](#3-phased-roadmap-overview)
4. [Phase 1: Workspaces + Checkpoints](#4-phase-1-workspaces--checkpoints)
5. [Phase 2: Compare Mode](#5-phase-2-compare-mode)
6. [Phase 3: Player Identities](#6-phase-3-player-identities)
7. [Phase 4: Analysis Views](#7-phase-4-analysis-views)
8. [Screen-by-Screen UI Changes](#8-screen-by-screen-ui-changes)
9. [Data Model](#9-data-model)
10. [API Endpoints](#10-api-endpoints)
11. [Frontend Architecture Changes](#11-frontend-architecture-changes)
12. [Migration & Backwards Compatibility](#12-migration--backwards-compatibility)
13. [Edge Cases & Error Handling](#13-edge-cases--error-handling)
14. [Open Questions](#14-open-questions)

---

## 1. Problem Statement

### 1.1 The Core Need

Poker players evolve. They get coached, change strategies, move up stakes, join staking funds, and study opponents. The hand history database is one continuous stream, but the player's journey has **chapters**. OHM currently has no way to segment, compare, or isolate these chapters.

### 1.2 Specific Pain Points

**Pain 1 — No time segmentation**
"Show me stats since I joined the fund" requires manually remembering and entering a date. There are no named markers, no quick filters, and no visual indicators on graphs. A player who makes a strategy change has no easy way to see only the hands played after that change.

**Pain 2 — No data isolation for different players**
Importing a coaching student's hand histories into the same database pollutes the hero's stats. GGPoker uses "Hero" as the anonymized player name for whoever downloaded the file — two different real humans both show up as "Hero." Currently there is no way to import both without corrupting stats.

**Pain 3 — Hand ID collisions across perspectives**
The same hand played at the same table exists in two players' exports (e.g., coach and student were at the same table). The hand has the same ID (e.g., `RC123456789`) but different hole cards. Importing both into one DB either deduplicates (losing the second perspective) or breaks the `hands.id` primary key.

**Pain 4 — No before/after comparison**
A coach says "focus on postflop." Two weeks later, there's no easy way to see if the student's C-Bet frequency improved. The user would have to manually note dates, run the stats page twice with different date filters, and mentally compare numbers.

**Pain 5 — No cross-player analysis**
Want to compare Student A to Student B? Or study the population while excluding coached students (who play differently from the field)? Or treat a known student as a "regular" and study their leaks from your own table perspective? All currently impossible without separate app installs.

**Pain 6 — No pool analysis across data sources**
A coach with 5 students' hand histories wants to build a picture of the NL25 player pool by combining all their data — but excluding the students themselves from the population stats (since they're coached and not representative). This requires merging data from multiple perspectives while selectively excluding specific players.

### 1.3 Real-World Scenarios

**Scenario A — The Fund Player**
Anton joins a poker staking fund on Feb 16. The coach tells him to focus on postflop play. Anton wants to:
1. Mark "Joined Fund" as a milestone
2. See all stats "since Joined Fund" with one click
3. After 2 weeks, compare his pre-fund vs post-fund 3-bet, C-Bet, and WTSD numbers
4. See a vertical marker on his profit graph at the fund start date

**Scenario B — The Coach**
A coach receives hand histories from 3 students (Mike, John, Sarah). The coach wants to:
1. Import each student's HH into separate isolated spaces
2. Review each student's stats individually
3. Compare Mike vs John side-by-side to see who improved more
4. Build a "NL25 Field" population view excluding all 3 students and themselves
5. Show each student how their stats compare to the field

**Scenario C — The Stake Mover**
A player takes a shot at NL50 for a week, then drops back to NL25. They want to:
1. Mark "NL50 Shot Start" and "NL50 Shot End" as checkpoints
2. Isolate the NL50 period to see their stats at that stake specifically
3. See their NL25 stats excluding the shot-taking period
4. Evaluate whether they're ready for another shot

---

## 2. Goals & Non-Goals

### 2.1 Goals

- Let users create named workspaces that isolate hand data by perspective/context
- Let users place named checkpoints (milestones) on their timeline and filter everything "since checkpoint X" with one click
- Show checkpoint markers as vertical lines on the Results profit graph
- Enable side-by-side stat comparison between two time periods (before/after checkpoint)
- Support importing hand histories from different players without any data collision
- Enable cross-workspace player identity linking for coaches analyzing multiple students
- Support population analysis across multiple workspaces with configurable player exclusion
- Support comparing two players' stats side-by-side
- Keep the default single-workspace experience completely unchanged for casual users who never need these features
- Ensure every existing API call continues to work without modification (backwards compatible)

### 2.2 Non-Goals

- Multi-user / cloud sync (OHM remains fully local, single-user)
- Real-time hand tracking / HUD overlay (remains post-session analysis only)
- Tournament support (cash game only for now)
- GTO solver integration
- Automatic player identification across anonymous GGPoker aliases (aliases are manually linked)
- Mobile / tablet support
- Cross-device synchronization

---

## 3. Phased Roadmap Overview

| Phase | Name | What It Delivers | Depends On |
|-------|------|-------------------|------------|
| **1** | Workspaces + Checkpoints | Data isolation between player perspectives. Named time markers with "since" filtering. Checkpoint lines on graph. | None |
| **2** | Compare Mode | Side-by-side stat comparison between two time periods within a workspace. | Phase 1 (checkpoints) |
| **3** | Player Identities | Cross-workspace player linking via aliases. Player tags (student, reg, etc.). Enhanced Players page as registry. | Phase 1 (workspaces) |
| **4** | Analysis Views | Saved multi-workspace query configs. Population views with exclusion. Player-vs-player comparison across workspaces. | Phase 1 + Phase 3 |

Each phase is independently shippable. Phase 2 and Phase 3 can be developed in parallel after Phase 1 ships.

---

## 4. Phase 1: Workspaces + Checkpoints

### 4.1 Workspaces

#### 4.1.1 Concept

A **workspace** is a named, isolated container for hand history data. Each workspace has its own hero identity (username + site) and its own collection of hands. Workspaces prevent data collision when importing hands from different players or different contexts.

Think of a workspace as a "database within the database" — logically separate, but physically stored in the same DuckDB file for simplicity.

#### 4.1.2 Workspace Properties

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | INTEGER | auto | auto-increment | Internal ID |
| `name` | VARCHAR | yes | — | Display name (e.g., "My Game", "Student Mike"). Must be unique. |
| `hero_username` | VARCHAR | yes | `'Hero'` | The player name that represents the hero in this workspace's hand histories. For GGPoker, this is typically "Hero" unless the user renamed it. |
| `hero_site` | VARCHAR | yes | `'GG'` | Site code. Currently only "GG" (GGPoker). |
| `description` | TEXT | no | NULL | Optional notes about this workspace (e.g., "Mike's NL25 hands from Jan-Mar 2026") |
| `color` | VARCHAR | no | NULL | Optional color for visual distinction in the workspace switcher (e.g., "blue", "green", "#ff6b6b") |
| `created_at` | TIMESTAMP | auto | CURRENT_TIMESTAMP | When the workspace was created |

#### 4.1.3 Workspace Rules & Behavior

1. **Every hand belongs to exactly one workspace.** The `hands` table gains a `workspace_id` foreign key.

2. **Hand uniqueness is scoped to workspace.** The same hand ID (e.g., `RC123456789`) can exist in workspace 1 (your perspective) and workspace 2 (student's perspective). Uniqueness constraint: `UNIQUE(workspace_id, id)`.

3. **Hero resolution is per-workspace.** When computing hero stats, the system looks up the hero player using the workspace's `hero_username` + `hero_site`, not a global setting.

4. **Switching workspace changes all data context.** Every page (Stats, Graph, Hands, Sessions, Players, Population, Cash Drop, Range) shows data from the active workspace only. The active workspace ID is passed to every API call.

5. **Default install experience is unchanged.** A fresh install creates one workspace named "My Game" with `hero_username='Hero'`. All existing UI flows work identically — the workspace switcher is visible but doesn't require interaction.

6. **Workspace names must be unique.** Attempting to create a duplicate name returns a validation error.

7. **At least one workspace must always exist.** The UI prevents deleting the last workspace.

8. **Deleting a workspace is destructive.** It cascades to all hands, hand_players, actions, board_cards, hand_tags, hand_notes, and checkpoints belonging to that workspace. The `players` table entries are NOT deleted (they may be referenced by other workspaces). Requires user confirmation with the workspace name typed to confirm.

9. **Settings migration.** The current global `hero_username` and `hero_site` keys in the `settings` table are migrated to the default workspace's fields. The global settings keys are then removed. The `GET /api/settings` and `PATCH /api/settings` endpoints are updated to read/write from the workspace.

#### 4.1.4 Workspace Switcher (UI Component)

**Location**: Top of sidebar, below the OHM logo, above the Import button.

**Appearance**: A shadcn `Select` dropdown showing the active workspace name with a colored dot indicator (if the workspace has a color).

**Collapsed sidebar mode**: Shows only the colored dot or first letter of the workspace name, with full name in tooltip.

**Dropdown contents**:
```
┌─────────────────────────────┐
│  🟢 My Game            ✓   │  ← active (checkmark)
│  🔵 Student Mike            │
│  🟣 Student John            │
│  ───────────────────────    │
│  + New Workspace            │
│  ⚙ Manage Workspaces        │
└─────────────────────────────┘
```

**"+ New Workspace"** opens a Dialog (shadcn Dialog component) with:
- Name (Input, required, auto-focused)
- Hero Username (Input, default: "Hero")
- Site (Select, default: "GGPoker", future: other sites)
- Description (Textarea, optional)
- Color picker (optional, small color swatches)
- [Cancel] [Create] buttons

**"Manage Workspaces"** navigates to `/settings/workspaces` (new settings sub-page).

**On workspace switch**:
1. Update `localStorage.setItem('ohm_active_workspace_id', newId)`
2. Update `WorkspaceContext` (React context)
3. Invalidate all React Query caches (`queryClient.invalidateQueries()`)
4. All pages re-fetch data for the new workspace

### 4.2 Checkpoints

#### 4.2.1 Concept

A **checkpoint** is a named point in time within a workspace. It marks a meaningful moment in the player's journey: a strategy change, coaching start, stake move, mental game reset, etc. Checkpoints enable quick date filtering and visual markers on graphs.

#### 4.2.2 Checkpoint Properties

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | INTEGER | auto | auto-increment | Internal ID |
| `workspace_id` | INTEGER FK | yes | — | Which workspace this belongs to. CASCADE on delete. |
| `name` | VARCHAR | yes | — | Display name (e.g., "Joined Fund", "New 3bet Strategy") |
| `checkpoint_at` | TIMESTAMP | yes | current time | The point in time this marks. User can pick any date. |
| `note` | TEXT | no | NULL | Optional longer description (e.g., "Coach told me to focus on postflop aggression") |
| `created_at` | TIMESTAMP | auto | CURRENT_TIMESTAMP | When the checkpoint record was created (different from checkpoint_at) |

#### 4.2.3 Checkpoint Rules & Behavior

1. **Checkpoints are per-workspace.** Each workspace has its own set of checkpoints. Deleting a workspace cascades to its checkpoints.

2. **No limit on checkpoints.** A workspace can have any number of checkpoints.

3. **Checkpoint names need not be unique** within a workspace (though it's good practice). The system uses IDs internally.

4. **checkpoint_at defaults to "now"** but the user can select any date. This allows retroactive checkpointing (e.g., "I should have marked this 2 weeks ago").

5. **Checkpoints are ordered by checkpoint_at** in all UI displays (most recent first in dropdown, chronological on graph).

#### 4.2.4 Checkpoint in FilterBar

The FilterBar component gains a new "Since" dropdown between the game mode selector and the date pickers:

```
[NL25 ▾]  [All Modes ▾]  [Since: ▾]  [From: ___]  [To: ___]  [Today] [Week] [Month] [All]
```

**"Since" dropdown contents** (ordered by `checkpoint_at` descending):
```
┌──────────────────────────────────────┐
│  All Time                        ✓   │
│  ─────────────────────────────────   │
│  New 3bet Strategy   (Mar 1)         │
│  Joined Fund         (Feb 16)        │
│  Started Tracking    (Jan 15)        │
│  ─────────────────────────────────   │
│  + New Checkpoint...                 │
└──────────────────────────────────────┘
```

**Interaction logic**:

- Selecting a checkpoint sets `date_from` to `checkpoint_at` and visually indicates the "From" field is auto-set (muted text, lock icon, or different styling)
- The "From" DatePicker becomes read-only while a checkpoint is selected (shows the date but doesn't allow manual editing). Clearing the checkpoint re-enables manual date entry.
- "To" remains freely editable (defaults to empty = now)
- Selecting "All Time" clears the checkpoint selection and resets `date_from` to empty
- Date presets (Today/Week/Month) override the checkpoint selection — they set both from and to, and deselect the checkpoint
- The "All" preset clears everything including the checkpoint selection

**"+ New Checkpoint..." quick-create flow**:

1. Clicking opens a Popover (shadcn Popover) anchored to the dropdown
2. Popover contains:
   - Name (Input, required, auto-focused, placeholder: "e.g., Strategy Change")
   - Date (DatePicker, defaults to today)
   - Note (Input, optional, placeholder: "Optional note...")
   - [Create] button
3. After creating, the popover closes and the new checkpoint is immediately selected in the dropdown
4. The FilterBar re-renders with the checkpoint active

**New FilterBar props**:
```typescript
interface FilterBarProps {
  // ... all existing props unchanged ...

  // New checkpoint props
  checkpointId?: string | null;           // Currently selected checkpoint ID, or null
  onCheckpointChange?: (id: string | null) => void; // Called when user selects/deselects a checkpoint
  checkpoints?: Checkpoint[];              // List of checkpoints for the active workspace
  showCheckpoints?: boolean;               // Whether to show the "Since" dropdown (default: true)
  onCreateCheckpoint?: (data: { name: string; checkpoint_at: string; note?: string }) => Promise<void>;
}

interface Checkpoint {
  id: number;
  name: string;
  checkpoint_at: string;  // ISO timestamp
  note: string | null;
}
```

Pages that currently use FilterBar (GraphPage, StatsPage, RangePage, CashDropPage) will need to:
1. Fetch checkpoints for the active workspace
2. Pass them to FilterBar
3. Handle checkpoint selection by setting `date_from` accordingly

#### 4.2.5 Checkpoints on the Results Graph

The Results/Graph page (GraphPage.tsx) shows checkpoint markers as vertical reference lines on the Recharts chart.

**Implementation using Recharts**:
```tsx
// For each checkpoint, add a ReferenceLine to the ComposedChart
{checkpoints.map(cp => (
  <ReferenceLine
    key={cp.id}
    x={cp.checkpoint_at}  // maps to the played_at x-axis
    stroke="#6b7280"       // gray-500, subtle
    strokeDasharray="4 4"  // dashed
    strokeWidth={1}
    label={{
      value: cp.name,
      position: 'top',
      fill: '#9ca3af',     // gray-400
      fontSize: 11,
    }}
  />
))}
```

**Toggle control**: A small toggle/checkbox in the graph controls area:
```
[Show Checkpoints ✓]
```
Default: on. Stored in localStorage per user preference.

**Hover behavior**: When hovering near a checkpoint line, a tooltip shows the full checkpoint name, date, and note (if any).

**Interaction**: Clicking a checkpoint line on the graph selects it in the FilterBar "Since" dropdown, filtering all data from that point forward.

---

## 5. Phase 2: Compare Mode

### 5.1 Concept

Compare Mode provides a dedicated page for viewing stats from two time periods side-by-side. This is the primary coaching proof tool — it shows whether a strategic change actually improved the player's game with concrete numbers and color-coded deltas.

### 5.2 New Page: `/compare`

#### 5.2.1 Route & Navigation

- Route: `/compare`
- Sidebar location: New nav group "Tools" below the main nav items

```
Sidebar:
├─ Import
├─ Stats
├─ Range
├─ Results
├─ Sessions
├─ Hands
├─ Cash Drop
├─ ──────────
├─ Tools              ← new group
│  └─ Compare         ← new item (icon: ArrowLeftRight from lucide)
├─ Opponents
│  ├─ Players
│  └─ Population
```

Also add to `PAGE_LABELS` in App.tsx:
```typescript
'/compare': 'Compare',
```

#### 5.2.2 Period Selection UI

The top of the page has two period selectors:

```
┌─── Period A ──────────────────────────┐  ┌─── Period B ──────────────────────────┐
│ Quick: [Before Fund         ▾]        │  │ Quick: [After Fund          ▾]        │
│ From:  [Jan 1, 2026 ]  To: [Feb 15 ] │  │ From:  [Feb 16, 2026]  To: [       ] │
│ Hands: 12,431          bb/100: +1.12  │  │ Hands: 8,127           bb/100: +4.87 │
└───────────────────────────────────────┘  └───────────────────────────────────────┘
```

**"Quick" dropdown options** (auto-generated from checkpoints):

1. **Checkpoint-based ranges**:
   - "Before [Checkpoint Name]" — earliest hand → checkpoint date
   - "After [Checkpoint Name]" — checkpoint date → latest hand (or next checkpoint)
   - "Between [A] and [B]" — checkpoint A → checkpoint B (shown for adjacent checkpoints)

2. **Preset ranges**:
   - "Last 7 days"
   - "Last 30 days"
   - "Last 3 months"
   - "All time"

3. **"Custom"** — clears the quick selection, enables manual date pickers

**Period summary line**: Below the date range, show the hand count and overall bb/100 for that period as a quick sanity check. This is fetched when the period dates change.

**Stakes filter**: Shared between both periods — above both cards:
```
Stakes: [All Stakes ▾]  Game Mode: [All Modes ▾]
```

#### 5.2.3 Comparison Stats Table

The core output — a large table with all stats grouped identically to the Stats page:

```
┌────────────────────────────────────────────────────────────────┐
│                  │ Period A  │ (sample) │ Period B  │ (sample) │  Delta   │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ PRE-FLOP         │          │          │          │          │          │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ VPIP             │  29.1%   │ (12431)  │  24.8%   │  (8127)  │ -4.3  🟢│
│ PFR              │  19.2%   │ (12431)  │  21.5%   │  (8127)  │ +2.3  🟢│
│ Open Raise       │  16.1%   │  (9823)  │  18.9%   │  (6412)  │ +2.8  🟢│
│ 3-Bet            │   7.1%   │  (4521)  │   9.8%   │  (3102)  │ +2.7  🟢│
│ Fold to 3-Bet    │  71.0%   │  (1823)  │  58.2%   │  (1456)  │-12.8  🟢│
│ 4-Bet            │   3.2%   │   (892)  │   4.8%   │   (623)  │ +1.6  🟢│
│ Call Open         │  11.2%   │  (7234)  │   8.9%   │  (5012)  │ -2.3  🟡│
│ Limp             │   3.1%   │ (12431)  │   1.2%   │  (8127)  │ -1.9  🟢│
│ Squeeze          │   4.5%   │   (312)  │   6.2%   │   (234)  │ +1.7  🟢│
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ STEAL             │          │          │          │          │          │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ Steal            │  42.1%   │  (3421)  │  48.3%   │  (2345)  │ +6.2  🟢│
│ Fold to 3Bet(stl)│  65.0%   │   (812)  │  55.2%   │   (623)  │ -9.8  🟢│
│ vs Steal Fold    │  72.1%   │  (2134)  │  65.8%   │  (1523)  │ -6.3  🟢│
│ vs Steal 3-Bet   │   8.9%   │  (2134)  │  12.1%   │  (1523)  │ +3.2  🟢│
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ POSTFLOP          │          │          │          │          │          │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ C-Bet Flop       │  48.0%   │  (2345)  │  63.2%   │  (1789)  │+15.2  🟢│
│ C-Bet Turn       │  41.2%   │  (1234)  │  52.1%   │   (912)  │+10.9  🟢│
│ Fold to CBet Flop│  52.1%   │  (1567)  │  44.8%   │  (1123)  │ -7.3  🟢│
│ Agg Freq Flop    │  38.2%   │  (4567)  │  45.1%   │  (3234)  │ +6.9  🟢│
│ Agg Freq Turn    │  32.1%   │  (3456)  │  38.9%   │  (2456)  │ +6.8  🟢│
│ Donk Bet Flop    │   5.2%   │   (456)  │   3.1%   │   (312)  │ -2.1  🟢│
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ SHOWDOWN          │          │          │          │          │          │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ WTSD             │  31.0%   │  (5678)  │  27.4%   │  (4123)  │ -3.6  🟡│
│ W$SD             │  51.2%   │  (1756)  │  54.1%   │  (1132)  │ +2.9  🟢│
│ WWSF             │  43.8%   │  (5678)  │  47.2%   │  (4123)  │ +3.4  🟢│
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ WIN RATE          │          │          │          │          │          │
│──────────────────│──────────│──────────│──────────│──────────│──────────│
│ bb/100           │  -2.31   │ (12431)  │  +4.87   │  (8127)  │ +7.18 🟢│
│ EV bb/100        │  +1.12   │ (12431)  │  +3.92   │  (8127)  │ +2.80 🟢│
└────────────────────────────────────────────────────────────────┘
```

#### 5.2.4 Delta Color Coding Logic

Each stat has a known "healthy direction" (already exists in OHM's benchmark/tooltip system). The delta column uses this:

| Color | CSS Class | Meaning | Example |
|-------|-----------|---------|---------|
| Green | `text-green` | Delta moved the stat toward the benchmark healthy range | VPIP dropped from 29% toward 24% (healthy ~24-27%) |
| Red | `text-red` | Delta moved the stat away from the healthy range | VPIP increased from 24% to 32% |
| Yellow | `text-yellow` | Direction is ambiguous or stat is already in healthy range and moved within it | WTSD changed but was already in range |
| Gray | `text-text-muted` | Insufficient sample in either period | Fewer than 50 opportunities in one period |

Stats with fewer than 50 opportunities in either period get muted styling (gray text, no delta color, row slightly dimmed).

#### 5.2.5 Sample Size Warnings

Prominent banner at top of stats table when relevant:

```
⚠ Period B has 8,127 hands. Stats may not be reliable below 10,000 hands.
   Especially postflop stats (C-Bet, Fold to CBet) which need 2,000+ opportunities.
```

Warning thresholds:
- Overall: < 10,000 hands per period
- Individual stat row: < 50 opportunities (row-level indicator)
- Individual stat row: < 200 opportunities (subtle indicator)

#### 5.2.6 API Implementation

This does NOT require a new stats computation engine. The backend simply calls the existing `compute_player_stats()` twice with different date ranges and returns both results:

**Endpoint**: `GET /api/compare/stats`

**Query parameters**:
```
workspace_id       (required)
period_a_from      (ISO date string)
period_a_to        (ISO date string)
period_b_from      (ISO date string)
period_b_to        (ISO date string)
stakes             (optional)
game_mode          (optional)
```

**Response** (reuses existing HeroStats model):
```json
{
  "period_a": {
    "from": "2026-01-01",
    "to": "2026-02-15",
    "hands": 12431,
    "stats": { /* HeroStats object — identical to GET /api/stats/hero response */ }
  },
  "period_b": {
    "from": "2026-02-16",
    "to": null,
    "hands": 8127,
    "stats": { /* HeroStats object */ }
  }
}
```

The frontend computes deltas and applies color coding. No backend delta computation needed — this keeps the API simple and the delta logic (which needs benchmark knowledge) in the frontend where it already lives.

---

## 6. Phase 3: Player Identities

### 6.1 Concept

A **Player Identity** represents a real-world person who may appear under different names in different workspaces. It's the glue that enables cross-workspace analysis.

**Example**:
- "Mike" is a real person (a coaching student)
- In Mike's own hand histories (Workspace: "Student Mike"), he appears as "Hero"
- In your hand histories (Workspace: "My Game"), he might appear as "Player#a8f3" (if you know his GGPoker alias)
- A Player Identity links these appearances so you can aggregate Mike's stats across both data sources

### 6.2 Player Identity Properties

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | INTEGER | auto | auto-increment | Internal ID |
| `display_name` | VARCHAR | yes | — | User-assigned name (e.g., "Mike", "John", "Me") |
| `tags` | TEXT | no | `'[]'` | JSON array of string tags: `["student", "reg"]` |
| `notes` | TEXT | no | NULL | Free-form notes about this player |
| `color` | VARCHAR | no | NULL | Color tag for visual distinction |
| `created_at` | TIMESTAMP | auto | CURRENT_TIMESTAMP | Creation time |

### 6.3 Player Aliases (Cross-Workspace Links)

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `identity_id` | INTEGER FK → player_identities | Which real person this links to |
| `workspace_id` | INTEGER FK → workspaces | Which workspace the player record lives in |
| `player_id` | INTEGER FK → players | The actual player record in that workspace |

**Constraints**:
- `UNIQUE(workspace_id, player_id)` — a player in a workspace maps to at most one identity
- `UNIQUE(identity_id, workspace_id)` — an identity has at most one alias per workspace (one person can't be two different players in the same hand history)

**Behavior**:
- Linking creates a connection; unlinking removes it. Neither creates nor deletes hand data.
- Deleting an identity cascades to its aliases (just the links, not the player or hand data).
- Deleting a workspace cascades to aliases in that workspace.

### 6.4 Tag System

Tags are freeform strings stored as a JSON array. Some well-known tag values unlock special behavior in the UI:

| Tag | UI Behavior |
|-----|-------------|
| `me` | Auto-excluded from population analysis. Shown with special icon in player list. |
| `student` | Shown in "Students" filter on Players page. Excludable from population with one click. |
| `reg` | Shown in "Regulars" filter. |
| `fish` | Shown in "Recreational" filter. |
| `coach` | Informational only. |

Users can create arbitrary tags beyond these (e.g., "fund-player", "aggro", "nitty"). Custom tags appear in the filter dropdown alongside the well-known ones.

### 6.5 Cross-Workspace Stats Computation

Once aliases are linked, stats for an identity are computed by aggregating across all workspaces:

```sql
-- Get all hand_players rows for identity #2 (Mike)
SELECT hp.*
FROM hand_players hp
JOIN player_aliases pa ON hp.player_id = pa.player_id
JOIN hands h ON hp.hand_id = h.id AND h.workspace_id = pa.workspace_id
WHERE pa.identity_id = 2
```

This feeds into the existing `compute_player_stats()` — we just need a variant that accepts an identity_id and resolves it to the correct player_id(s) across workspaces.

**New function**: `compute_identity_stats(db, identity_id, ...)` — resolves aliases, unions hand_players rows, runs the same aggregation SQL.

### 6.6 GGPoker Anonymization Caveat

On GGPoker anonymous tables (Rush & Cash), player names rotate. You can't reliably identify "Player#a8f3" as Mike across sessions from your own hand histories. However:

- From **Mike's own HH**, he's always "Hero" — his stats from his own data are always accurate
- On **non-anonymous tables** or **other poker sites**, player names are stable and aliases work perfectly
- The alias system degrades gracefully: if you can't identify someone, you just don't create an alias for them in that workspace. Their data in their own workspace is still fully usable.

---

## 7. Phase 4: Analysis Views

### 7.1 Concept

An **Analysis View** is a saved query configuration that defines: what data to look at, from whose perspective, and what to exclude. It decouples "where data lives" (workspaces) from "how you look at data" (analysis).

### 7.2 Analysis View Properties

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | INTEGER | auto | auto-increment | Internal ID |
| `name` | VARCHAR | yes | — | Display name (e.g., "My Stats (NL25)", "NL25 Field") |
| `view_type` | VARCHAR | yes | `'single_player'` | One of: `single_player`, `population`, `compare_players` |
| `source_workspace_ids` | TEXT | yes | — | JSON array of workspace IDs to pull data from |
| `hero_identity_id` | INTEGER FK | conditional | NULL | For `single_player`: whose stats to show. Required for single_player, NULL for population. |
| `compare_identity_ids` | TEXT | conditional | NULL | For `compare_players`: JSON array of identity IDs |
| `exclude_identity_ids` | TEXT | no | `'[]'` | JSON array of identity IDs to exclude from analysis |
| `exclude_tags` | TEXT | no | `'[]'` | JSON array of tags — all identities with any of these tags are excluded |
| `default_stakes` | VARCHAR | no | NULL | Pre-set stakes filter for this view |
| `default_checkpoint_id` | INTEGER FK | no | NULL | Pre-set "since" filter |
| `description` | TEXT | no | NULL | Optional description |
| `sort_order` | INTEGER | no | 0 | Display order in the view switcher |
| `created_at` | TIMESTAMP | auto | CURRENT_TIMESTAMP | Creation time |

### 7.3 View Types Explained

#### `single_player` — "Show me one person's stats"

The default mode. Equivalent to the current app experience but potentially spanning multiple workspaces.

- `hero_identity_id` points to the person whose stats you want to see
- `source_workspace_ids` lists which workspaces to search for that person's hands
- Stats/Graph/Hands pages all show data as if this person is the hero

**Example configs**:
- "My Stats" = identity(me), workspace([My Game])
- "Student Mike Review" = identity(Mike), workspace([Mike's HH])
- "Mike All Data" = identity(Mike), workspace([Mike's HH, My Game]) — combines Mike's perspective and your observations of Mike

#### `population` — "Show me how the field plays"

No hero. Aggregates all players across selected workspaces, minus exclusions.

- `hero_identity_id` = NULL (no individual hero)
- `exclude_identity_ids` + `exclude_tags` remove specific people
- Stats page shows population averages
- Useful for: studying the player pool, understanding field tendencies

**Example**: "NL25 Field" = workspaces([My Game, Mike's HH, John's HH]), exclude tags(["me", "student"])

#### `compare_players` — "Show me Player A vs Player B"

Side-by-side stat comparison between 2-3 player identities.

- `compare_identity_ids` lists the people to compare
- Stats page renders multi-column comparison table
- Useful for: coaches comparing students, comparing yourself to a student

**Example**: "Mike vs John" = identities([Mike, John]), workspaces([Mike's HH, John's HH])

### 7.4 Default Views

On fresh install or Phase 4 migration:
- One default view is created: "My Stats" (single_player, default workspace, auto-detected hero identity)

Users who never create custom views see identical behavior to Phase 1-3 — the view switcher just shows "My Stats" and workspace-derived views.

### 7.5 View Switcher

In Phase 4, the sidebar's workspace switcher evolves into an **Analysis View Switcher**:

```
┌─────────────────────────────┐
│  [📊 My Stats           ▾]  │
│    📊 My Stats               │
│    📊 Student Mike           │
│    📊 Mike vs John           │
│    📊 NL25 Field             │
│    ─────────────────────    │
│    + New View               │
│    ⚙ Manage Views            │
│    ⚙ Manage Workspaces       │
└─────────────────────────────┘
```

Switching views changes the entire data context — what workspaces are queried, whose stats are shown, what's excluded.

### 7.6 Analysis View Builder (New Page)

A form page at `/settings/views/new` (or `/settings/views/:id/edit`):

```
┌──────────────────────────────────────────────────────────────────┐
│  New Analysis View                                               │
│                                                                  │
│  Name: [NL25 Field Study                        ]                │
│                                                                  │
│  ── Data Sources ─────────────────────────────────────────────── │
│  Which workspaces to include:                                    │
│  [✓] My Game            (12.4k hands)                            │
│  [✓] Student Mike       (24.3k hands)                            │
│  [✓] Student John       (11.7k hands)                            │
│                                                                  │
│  ── Analysis Type ────────────────────────────────────────────── │
│                                                                  │
│  (●) Population — no single hero, aggregate all players          │
│  ( ) Single Player — view stats for one person                   │
│      └─ Hero: [select identity ▾]                                │
│  ( ) Compare Players — side-by-side stats for 2-3 players        │
│      └─ Players: [multi-select identities ▾]                     │
│                                                                  │
│  ── Exclusions (for Population mode) ─────────────────────────── │
│  Exclude identities:                                             │
│  [✓] Anton (#me)                                                 │
│  [✓] Mike (#student)                                             │
│  [✓] John (#student)                                             │
│  [ ] (other identities...)                                       │
│                                                                  │
│  Exclude by tag (excludes all identities with these tags):       │
│  [✓] student    [ ] reg    [ ] fish    [ ] me                    │
│                                                                  │
│  ── Default Filters ──────────────────────────────────────────── │
│  Stakes: [All Stakes ▾]                                          │
│  Since checkpoint: [All Time ▾]                                  │
│                                                                  │
│  Description: [Optional notes about this analysis view    ]      │
│                                                                  │
│  [Cancel]                                         [Save View]    │
└──────────────────────────────────────────────────────────────────┘
```

The form dynamically shows/hides sections based on Analysis Type selection:
- **Population**: shows exclusion controls
- **Single Player**: shows Hero identity dropdown (required)
- **Compare Players**: shows multi-select for 2-3 identities (required, min 2)

---

## 8. Screen-by-Screen UI Changes

### 8.1 Summary Matrix

| Screen | Phase 1 | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|---------|
| **Sidebar** | + Workspace switcher at top | + "Tools > Compare" nav item | No change | Workspace switcher → View switcher |
| **Sidebar Footer** | Hero name from workspace, hand count scoped | No change | No change | No change |
| **FilterBar** | + "Since" checkpoint dropdown | No change | No change | Filters scoped to active view |
| **Results Graph** | + Checkpoint vertical lines, + toggle | Optional split shading | No change | Multi-workspace data |
| **Stats** | Workspace-scoped queries | No change | No change | Population mode, compare mode |
| **Range** | Workspace-scoped queries | No change | No change | Scoped to view |
| **Hands** | Workspace-scoped queries | No change | No change | Cross-workspace browsing |
| **Sessions** | Workspace-scoped queries | No change | No change | Scoped to view |
| **Cash Drop** | Workspace-scoped queries | No change | No change | Scoped to view |
| **Players** | Workspace-scoped | No change | **Major**: identity registry + alias management | Scoped to view |
| **Population** | Workspace-scoped | No change | + Exclusion controls | Full view integration |
| **Import Overlay** | + Shows active workspace name | No change | No change | No change |
| **Settings** | + Workspace management, + Checkpoint management | No change | + Identity management | + View management |
| **Compare** | — | **NEW PAGE** | No change | + Cross-player mode |
| **View Builder** | — | — | — | **NEW PAGE** |

### 8.2 Detailed: Sidebar Changes

#### Phase 1 — Add Workspace Switcher

**File**: `frontend/src/components/AppSidebar.tsx`

Current structure:
```tsx
<Sidebar collapsible="icon">
  <SidebarHeader>
    <NavLink to="/graph">♠ OHM</NavLink>  // logo
  </SidebarHeader>
  <SidebarContent>
    <SidebarGroup>  // main nav: Import, Stats, Range, etc.
    <SidebarGroup>  // opponents: Players, Population
  </SidebarContent>
  <SidebarFooterSettings />
</Sidebar>
```

After Phase 1:
```tsx
<Sidebar collapsible="icon">
  <SidebarHeader>
    <NavLink to="/graph">♠ OHM</NavLink>  // logo
    <WorkspaceSwitcher />                  // NEW COMPONENT
  </SidebarHeader>
  <SidebarContent>
    <SidebarGroup>  // main nav: Import, Stats, Range, etc.
    <SidebarGroup>  // opponents: Players, Population
  </SidebarContent>
  <SidebarFooterSettings />  // now reads hero from workspace, not global settings
</Sidebar>
```

**New component**: `WorkspaceSwitcher.tsx` — shadcn Select with workspace list, "New" and "Manage" footer items.

#### Phase 2 — Add Compare Nav Item

```tsx
const toolItems = [
  { to: '/compare', label: 'Compare', icon: ArrowLeftRight },
];

// In SidebarContent, add new group:
<SidebarGroup>
  <SidebarGroupLabel>Tools</SidebarGroupLabel>
  <SidebarGroupContent>
    <SidebarMenu>
      {toolItems.map(item => (...))}
    </SidebarMenu>
  </SidebarGroupContent>
</SidebarGroup>
```

#### Phase 4 — Workspace Switcher → View Switcher

The `WorkspaceSwitcher` component evolves into `ViewSwitcher` — same visual position, but now shows analysis views instead of raw workspaces. Each view has an icon indicating its type:
- 📊 for single_player
- 👥 for population
- ⚖️ for compare_players

### 8.3 Detailed: FilterBar Changes

**File**: `frontend/src/components/FilterBar.tsx`

Current rendering order:
1. Stakes Select
2. Game Mode Select (conditional)
3. DatePicker (From)
4. DatePicker (To)
5. Date presets (Today/Week/Month/All)
6. Children slot

After Phase 1, insert between #2 and #3:
```
2. Game Mode Select
2.5 Checkpoint "Since" Select    ← NEW
3. DatePicker (From)
```

The "Since" Select uses shadcn Select component:
```tsx
{showCheckpoints && checkpoints && checkpoints.length > 0 && (
  <Select
    value={checkpointId || '__all_time__'}
    onValueChange={(v) => {
      if (v === '__all_time__') {
        onCheckpointChange?.(null);
      } else if (v === '__new__') {
        // open quick-create popover
      } else {
        onCheckpointChange?.(v);
      }
    }}
  >
    <SelectTrigger className="w-[180px] h-8 text-sm">
      <SelectValue placeholder="Since..." />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="__all_time__">All Time</SelectItem>
      <SelectSeparator />
      {checkpoints.map(cp => (
        <SelectItem key={cp.id} value={String(cp.id)}>
          {cp.name} ({formatDate(cp.checkpoint_at)})
        </SelectItem>
      ))}
      <SelectSeparator />
      <SelectItem value="__new__">+ New Checkpoint...</SelectItem>
    </SelectContent>
  </Select>
)}
```

### 8.4 Detailed: Import Overlay Changes

**File**: `frontend/src/components/ImportOverlay.tsx`

Add workspace context banner at top of overlay:

```tsx
<div className="flex items-center gap-2 px-4 py-2 bg-surface rounded-lg text-sm">
  <span className="text-text-muted">Importing into:</span>
  <span className="font-medium">{activeWorkspace.name}</span>
  {activeWorkspace.color && (
    <span className="w-2 h-2 rounded-full" style={{ background: activeWorkspace.color }} />
  )}
</div>
```

If the user has multiple workspaces, show a subtle hint:
```tsx
{workspaces.length > 1 && (
  <p className="text-xs text-text-muted mt-1">
    Wrong workspace? Switch in the sidebar first.
  </p>
)}
```

### 8.5 Detailed: Results/Graph Page Changes

**File**: `frontend/src/pages/GraphPage.tsx`

Current graph: Recharts `ComposedChart` with Area (profit line), Lines (EV, showdown, etc.), session markers.

Add checkpoint reference lines:

```tsx
import { ReferenceLine } from 'recharts';

// In the ComposedChart children:
{showCheckpoints && checkpoints.map(cp => {
  // Find the nearest graph point to this checkpoint's date
  const xValue = findNearestHandNumber(graphData.points, cp.checkpoint_at);
  if (xValue === null) return null;

  return (
    <ReferenceLine
      key={cp.id}
      x={xValue}
      stroke="var(--color-text-muted)"
      strokeDasharray="4 4"
      strokeWidth={1}
    >
      <Label value={cp.name} position="insideTopRight" fill="var(--color-text-muted)" fontSize={10} />
    </ReferenceLine>
  );
})}
```

Add toggle in the controls area (near existing BB/USD toggle):
```tsx
<div className="flex items-center gap-1.5">
  <Toggle
    size="sm"
    pressed={showCheckpoints}
    onPressedChange={setShowCheckpoints}
    className="h-7 text-xs"
  >
    Checkpoints
  </Toggle>
</div>
```

### 8.6 Detailed: Settings Page (New Sub-Pages)

Currently settings is just a dropdown in the sidebar footer. Phase 1 needs a proper settings area. Two approaches:

**Option A**: Dedicated `/settings` route with sub-pages
**Option B**: Keep settings in sidebar dropdown, add modals for workspace/checkpoint management

**Recommended: Option A** — cleaner, more room for Phase 3-4 features.

New routes:
```tsx
<Route path="/settings" element={<SettingsPage />} />
<Route path="/settings/workspaces" element={<WorkspaceSettingsPage />} />
<Route path="/settings/checkpoints" element={<CheckpointSettingsPage />} />
// Phase 3:
<Route path="/settings/identities" element={<IdentitySettingsPage />} />
// Phase 4:
<Route path="/settings/views" element={<ViewSettingsPage />} />
```

**Workspace management page** (`/settings/workspaces`):

Full CRUD list with inline editing:

```
┌────────────────────────────────────────────────────────────────┐
│  Workspaces                                    [+ New Workspace]│
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🟢 My Game                                              │  │
│  │    Hero: anton  |  Site: GGPoker  |  12,431 hands       │  │
│  │    Created: Jan 15, 2026                                │  │
│  │    Description: My personal hand histories              │  │
│  │                                                         │  │
│  │    Checkpoints (2):                                     │  │
│  │    🏁 Joined Fund — Feb 16, 2026                        │  │
│  │       "Entered poker fund, focusing on postflop"        │  │
│  │    🏁 New 3bet Strategy — Mar 1, 2026                   │  │
│  │                                                         │  │
│  │    [Edit Workspace]  [Manage Checkpoints]  [Delete]     │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ 🔵 Student Mike                                         │  │
│  │    Hero: Hero  |  Site: GGPoker  |  24,312 hands        │  │
│  │    Created: Feb 10, 2026                                │  │
│  │    Description: Mike's NL25 Rush & Cash hands           │  │
│  │                                                         │  │
│  │    Checkpoints (0): None                                │  │
│  │                                                         │  │
│  │    [Edit Workspace]  [Manage Checkpoints]  [Delete]     │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 8.7 Detailed: Players Page Changes (Phase 3)

**File**: `frontend/src/pages/PlayersPage.tsx`

Currently: flat list of opponents with VPIP/PFR/3-bet/AF columns, search, type filter.

After Phase 3: two-section layout:

**Section 1: Player Identities** (linked cross-workspace profiles)
- Cards showing display_name, tags (as badges), alias list, aggregated stats
- Click → navigate to identity detail page
- Filter by tag

**Section 2: Unlinked Opponents** (from active workspace)
- The existing opponent list, filtered to show only players NOT linked to any identity
- Each row gets a "Link to Identity" button → modal with existing identities or "Create New"

**New identity detail page** (`/players/identity/:id`):
- Full stats aggregated across all linked workspaces (reuse existing Stats table layout)
- Alias list with workspace name and player username
- [+ Link Alias] button → select workspace → select player from that workspace
- [Unlink] button next to each alias
- Tag editor (add/remove tags)
- Notes and color (existing functionality)

### 8.8 Detailed: Population Page Changes (Phase 3)

**File**: `frontend/src/pages/PopulationPage.tsx`

Add exclusion controls bar at the top, below the page title:

```tsx
<Card className="gap-0 py-0">
  <CardContent className="px-3 py-2 flex items-center gap-3">
    <span className="text-sm text-text-muted">Exclude:</span>
    {wellKnownTags.map(tag => (
      <Toggle
        key={tag}
        size="sm"
        pressed={excludedTags.includes(tag)}
        onPressedChange={() => toggleExcludeTag(tag)}
        className="h-7 text-xs capitalize"
      >
        {tag === 'me' ? 'Me' : tag}
      </Toggle>
    ))}
    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setShowExcludeModal(true)}>
      Edit...
    </Button>
  </CardContent>
</Card>
```

"Edit..." opens a Dialog listing all known identities with checkboxes. Each identity shows their tags as badges. Checking an identity adds them to `exclude_identity_ids`.

All population API calls now include:
```typescript
const sp = _buildPopParams(params);
if (excludeIdentityIds.length > 0) sp.set('exclude_identity_ids', excludeIdentityIds.join(','));
if (excludeTags.length > 0) sp.set('exclude_tags', excludeTags.join(','));
```

---

## 9. Data Model

### 9.1 New Tables — Complete DDL

#### `workspaces`

```sql
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    hero_username VARCHAR NOT NULL DEFAULT 'Hero',
    hero_site VARCHAR NOT NULL DEFAULT 'GG',
    description TEXT,
    color VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE IF NOT EXISTS seq_workspaces START 1;
```

#### `checkpoints`

```sql
CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    checkpoint_at TIMESTAMP NOT NULL,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE IF NOT EXISTS seq_checkpoints START 1;
CREATE INDEX IF NOT EXISTS idx_checkpoints_workspace ON checkpoints(workspace_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_at ON checkpoints(workspace_id, checkpoint_at);
```

#### `player_identities` (Phase 3)

```sql
CREATE TABLE IF NOT EXISTS player_identities (
    id INTEGER PRIMARY KEY,
    display_name VARCHAR NOT NULL,
    tags TEXT DEFAULT '[]',         -- JSON array: '["student", "reg"]'
    notes TEXT,
    color VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE IF NOT EXISTS seq_player_identities START 1;
```

#### `player_aliases` (Phase 3)

```sql
CREATE TABLE IF NOT EXISTS player_aliases (
    id INTEGER PRIMARY KEY,
    identity_id INTEGER NOT NULL REFERENCES player_identities(id) ON DELETE CASCADE,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id),
    UNIQUE(workspace_id, player_id),
    UNIQUE(identity_id, workspace_id)
);
CREATE SEQUENCE IF NOT EXISTS seq_player_aliases START 1;
CREATE INDEX IF NOT EXISTS idx_pa_identity ON player_aliases(identity_id);
CREATE INDEX IF NOT EXISTS idx_pa_workspace ON player_aliases(workspace_id);
CREATE INDEX IF NOT EXISTS idx_pa_player ON player_aliases(player_id);
```

#### `analysis_views` (Phase 4)

```sql
CREATE TABLE IF NOT EXISTS analysis_views (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    view_type VARCHAR NOT NULL DEFAULT 'single_player',
    source_workspace_ids TEXT NOT NULL DEFAULT '[]',     -- JSON array: '[1, 2]'
    hero_identity_id INTEGER REFERENCES player_identities(id),
    compare_identity_ids TEXT DEFAULT '[]',              -- JSON array: '[2, 3]'
    exclude_identity_ids TEXT DEFAULT '[]',              -- JSON array: '[1]'
    exclude_tags TEXT DEFAULT '[]',                      -- JSON array: '["student"]'
    default_stakes VARCHAR,
    default_checkpoint_id INTEGER REFERENCES checkpoints(id) ON DELETE SET NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE SEQUENCE IF NOT EXISTS seq_analysis_views START 1;
```

### 9.2 Modified Tables

#### `hands` — add `workspace_id`

```sql
ALTER TABLE hands ADD COLUMN workspace_id INTEGER DEFAULT 1 REFERENCES workspaces(id);
```

After migration (backfill all existing hands to workspace 1), add composite unique index:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_hands_workspace_id ON hands(workspace_id, id);
```

> **Note on DuckDB PK**: DuckDB's `hands.id VARCHAR PRIMARY KEY` stays as-is for Phase 1. The uniqueness within a workspace is enforced by the composite unique index. Across workspaces, duplicate hand IDs are allowed by design. If we later need to change the PK, a table recreation migration handles it.

#### `settings` — remove hero_username/hero_site

After migration copies these values to the default workspace:
```sql
DELETE FROM settings WHERE key IN ('hero_username', 'hero_site');
```

### 9.3 New Indexes for Workspace-Scoped Queries

```sql
CREATE INDEX IF NOT EXISTS idx_hands_workspace ON hands(workspace_id);
CREATE INDEX IF NOT EXISTS idx_hands_workspace_played ON hands(workspace_id, played_at);
CREATE INDEX IF NOT EXISTS idx_hands_workspace_stakes ON hands(workspace_id, stakes);
CREATE INDEX IF NOT EXISTS idx_hands_workspace_mode ON hands(workspace_id, game_mode);
```

### 9.4 Entity Relationship Diagram

```
                                workspaces
                               ┌──────────┐
                               │ id (PK)  │
                          ┌───→│ name     │←───┐
                          │    │ hero_*   │    │
                          │    └──────────┘    │
                          │         │          │
                     workspace_id   │     workspace_id
                          │    checkpoints     │
                          │    ┌──────────┐    │
                          │    │ id (PK)  │    │
                          │    │ name     │    │
                          │    │ at       │    │
                          │    └──────────┘    │
                          │                    │
                       hands              player_aliases
                    ┌──────────┐         ┌──────────────┐
                    │ id       │         │ identity_id  │──→ player_identities
                    │ wksp_id  │         │ workspace_id │    ┌────────────────┐
                    │ played_at│         │ player_id    │    │ id (PK)        │
                    │ raw_text │         └──────────────┘    │ display_name   │
                    └──────────┘              │              │ tags (JSON)    │
                         │              ┌─────┘              └────────────────┘
                    hand_players        │
                    ┌──────────┐    players
                    │ hand_id  │    ┌──────────┐
                    │ player_id│───→│ id (PK)  │
                    │ flags... │    │ username  │
                    └──────────┘    │ site_id   │
                                   └──────────┘

  analysis_views
  ┌──────────────────────┐
  │ id (PK)              │
  │ name                 │
  │ view_type            │
  │ source_workspace_ids │──→ JSON array → workspaces
  │ hero_identity_id     │──→ player_identities
  │ compare_identity_ids │──→ JSON array → player_identities
  │ exclude_identity_ids │──→ JSON array → player_identities
  │ exclude_tags         │──→ JSON array (freeform)
  └──────────────────────┘
```

---

## 10. API Endpoints

### 10.1 Phase 1: Workspace Endpoints

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/workspaces` | — | `Workspace[]` | List all workspaces with hand counts and date ranges |
| `POST` | `/api/workspaces` | `CreateWorkspace` | `Workspace` | Create workspace |
| `GET` | `/api/workspaces/:id` | — | `Workspace` | Get single workspace detail |
| `PATCH` | `/api/workspaces/:id` | `UpdateWorkspace` | `Workspace` | Update workspace fields |
| `DELETE` | `/api/workspaces/:id` | — | `{ status: "deleted" }` | Delete workspace + all data. 400 if last workspace. |

**Pydantic models**:

```python
class WorkspaceResponse(BaseModel):
    id: int
    name: str
    hero_username: str
    hero_site: str
    description: str | None = None
    color: str | None = None
    hand_count: int = 0
    date_range: dict[str, str | None] = {}  # {"min": "2026-01-15", "max": "2026-02-16"}
    created_at: datetime

class CreateWorkspace(BaseModel):
    name: str                        # required, unique
    hero_username: str = "Hero"
    hero_site: str = "GG"
    description: str | None = None
    color: str | None = None

class UpdateWorkspace(BaseModel):
    name: str | None = None
    hero_username: str | None = None
    hero_site: str | None = None
    description: str | None = None
    color: str | None = None
```

### 10.2 Phase 1: Checkpoint Endpoints

| Method | Path | Request Body | Response | Description |
|--------|------|-------------|----------|-------------|
| `GET` | `/api/workspaces/:wid/checkpoints` | — | `Checkpoint[]` | List checkpoints ordered by checkpoint_at desc |
| `POST` | `/api/workspaces/:wid/checkpoints` | `CreateCheckpoint` | `Checkpoint` | Create checkpoint |
| `PATCH` | `/api/workspaces/:wid/checkpoints/:id` | `UpdateCheckpoint` | `Checkpoint` | Update checkpoint |
| `DELETE` | `/api/workspaces/:wid/checkpoints/:id` | — | `{ status: "deleted" }` | Delete checkpoint |

**Pydantic models**:

```python
class CheckpointResponse(BaseModel):
    id: int
    workspace_id: int
    name: str
    checkpoint_at: datetime
    note: str | None = None
    created_at: datetime

class CreateCheckpoint(BaseModel):
    name: str                            # required
    checkpoint_at: datetime | None = None  # defaults to now
    note: str | None = None

class UpdateCheckpoint(BaseModel):
    name: str | None = None
    checkpoint_at: datetime | None = None
    note: str | None = None
```

### 10.3 Phase 1: Modified Existing Endpoints

**Every data endpoint** gains an optional `workspace_id` query parameter. When omitted, defaults to workspace ID 1.

**Complete list of modified endpoints** (46 endpoints):

```
GET  /api/stats/hero                         + ?workspace_id=
GET  /api/stats/range                        + ?workspace_id=
GET  /api/stats/detail/{key}/hands           + ?workspace_id=
GET  /api/stats/detail/{key}/trend           + ?workspace_id=
GET  /api/stats/detail/{key}/analysis        + ?workspace_id=
GET  /api/stats/detail/{key}/ev-breakdown    + ?workspace_id=
GET  /api/stats/detail/{key}/sizing          + ?workspace_id=
GET  /api/stats/detail/{key}/fold-equity     + ?workspace_id=
GET  /api/stats/detail/{key}/by-context      + ?workspace_id=
GET  /api/stats/detail/{key}/composition     + ?workspace_id=
GET  /api/stats/detail/{key}/money           + ?workspace_id=
GET  /api/stats/detail/{key}/postflop-bridge + ?workspace_id=
GET  /api/stats/detail/{key}/continuing-range+ ?workspace_id=
GET  /api/stats/detail/{key}/range           + ?workspace_id=
GET  /api/reports/graph                      + ?workspace_id=
GET  /api/reports/filter-options             + ?workspace_id=
GET  /api/reports/breakdown                  + ?workspace_id=
GET  /api/reports/drift                      + ?workspace_id=
GET  /api/reports/cash-drop                  + ?workspace_id=
GET  /api/hands                              + ?workspace_id=
GET  /api/hands/{id}                         + ?workspace_id=
POST /api/hands/{id}/tags                    + ?workspace_id=
DELETE /api/hands/{id}/tags/{tag}            + ?workspace_id=
GET  /api/tags                               + ?workspace_id=
PUT  /api/hands/{id}/note                    + ?workspace_id=
DELETE /api/hands/{id}/note                  + ?workspace_id=
GET  /api/sessions                           + ?workspace_id=
GET  /api/sessions/{index}                   + ?workspace_id=
GET  /api/players                            + ?workspace_id=
GET  /api/players/{id}                       + ?workspace_id=
GET  /api/players/{id}/stats                 + ?workspace_id=
GET  /api/players/{id}/head-to-head          + ?workspace_id=
PATCH /api/players/{id}/notes                + ?workspace_id=
GET  /api/population/overview                + ?workspace_id=
GET  /api/population/preflop                 + ?workspace_id=
GET  /api/population/segments                + ?workspace_id=
GET  /api/population/postflop                + ?workspace_id=
GET  /api/population/pot-types               + ?workspace_id=
GET  /api/population/hu-vs-mw                + ?workspace_id=
GET  /api/population/comparison              + ?workspace_id=
POST /api/import/files                       + workspace_id form field
POST /api/import/files/stream                + workspace_id form field
POST /api/import/rebuild                     + ?workspace_id=
GET  /api/settings                           → reads from workspace (workspace_id param)
PATCH /api/settings                          → writes to workspace (workspace_id param)
GET  /api/health                             + ?workspace_id= (for hand count scoping)
```

**Backend implementation pattern** — in every endpoint handler:

```python
@router.get("/some-endpoint")
def some_endpoint(workspace_id: int = 1, ...):
    db = get_read_cursor()
    hero_player_id = get_hero_player_id(db, workspace_id)
    # All queries add: AND h.workspace_id = :workspace_id
    ...
```

### 10.4 Phase 2: Compare Endpoint

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/compare/stats` | Compare hero stats between two time periods |

**Query parameters**:
```
workspace_id   (required, int)
period_a_from  (required, ISO date)
period_a_to    (required, ISO date)
period_b_from  (required, ISO date)
period_b_to    (optional, ISO date — defaults to now)
stakes         (optional)
game_mode      (optional)
```

**Response model**:
```python
class CompareResponse(BaseModel):
    period_a: PeriodStats
    period_b: PeriodStats

class PeriodStats(BaseModel):
    date_from: str
    date_to: str | None
    hands: int
    win_rate_bb100: float | None
    win_rate_ev_bb100: float | None
    stats: HeroStats  # reuse existing model
```

### 10.5 Phase 3: Identity Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/identities` | List all identities with aliases, tags, hand counts |
| `POST` | `/api/identities` | Create identity |
| `GET` | `/api/identities/:id` | Get identity detail |
| `PATCH` | `/api/identities/:id` | Update identity (name, tags, notes, color) |
| `DELETE` | `/api/identities/:id` | Delete identity (cascades aliases, not hand data) |
| `POST` | `/api/identities/:id/aliases` | Link a workspace player to this identity |
| `DELETE` | `/api/identities/:id/aliases/:alias_id` | Unlink an alias |
| `GET` | `/api/identities/:id/stats` | Stats aggregated across all aliases |

**Modified population endpoints** (Phase 3) — add params:
```
GET /api/population/*  + ?exclude_identity_ids=1,2,3  + ?exclude_tags=student,me
```

### 10.6 Phase 4: View Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/views` | List all analysis views |
| `POST` | `/api/views` | Create view |
| `GET` | `/api/views/:id` | Get view detail |
| `PATCH` | `/api/views/:id` | Update view |
| `DELETE` | `/api/views/:id` | Delete view |

---

## 11. Frontend Architecture Changes

### 11.1 New React Context: WorkspaceContext

```typescript
// frontend/src/contexts/WorkspaceContext.tsx

interface WorkspaceContextValue {
  workspaces: Workspace[];
  activeWorkspaceId: number;
  activeWorkspace: Workspace | null;
  checkpoints: Checkpoint[];
  setActiveWorkspaceId: (id: number) => void;
  refetchWorkspaces: () => Promise<void>;
  refetchCheckpoints: () => Promise<void>;
}
```

**Provider wraps the entire app** (in App.tsx, inside QueryClientProvider):
```tsx
<QueryClientProvider client={queryClient}>
  <WorkspaceProvider>
    <BrowserRouter>
      ...
    </BrowserRouter>
  </WorkspaceProvider>
</QueryClientProvider>
```

**On workspace switch**:
1. Update localStorage
2. Update context state
3. `queryClient.invalidateQueries()` — forces all pages to re-fetch
4. Refetch checkpoints for the new workspace

### 11.2 API Client Changes

**File**: `frontend/src/lib/api.ts`

Add a module-level workspace getter:

```typescript
// At top of api.ts
let _getWorkspaceId: () => number = () => {
  const stored = localStorage.getItem('ohm_active_workspace_id');
  return stored ? parseInt(stored, 10) : 1;
};

export function setWorkspaceIdGetter(fn: () => number) {
  _getWorkspaceId = fn;
}

function _addWorkspaceParam(sp: URLSearchParams) {
  sp.set('workspace_id', String(_getWorkspaceId()));
}
```

Then in every API function, add `_addWorkspaceParam(sp)`:

```typescript
export async function getHeroStats(params?: { ... }): Promise<HeroStats> {
  const sp = new URLSearchParams();
  _addWorkspaceParam(sp);  // ← ADD THIS
  setPositionParam(sp, params?.position);
  if (params?.stakes) sp.set('stakes', params.stakes);
  // ... rest unchanged
}
```

This is a mechanical change across all ~50 API functions. The workspace ID is injected transparently.

### 11.3 New API Functions

```typescript
// Workspaces
export async function getWorkspaces(): Promise<Workspace[]> { ... }
export async function createWorkspace(data: CreateWorkspace): Promise<Workspace> { ... }
export async function updateWorkspace(id: number, data: UpdateWorkspace): Promise<Workspace> { ... }
export async function deleteWorkspace(id: number): Promise<void> { ... }

// Checkpoints
export async function getCheckpoints(workspaceId: number): Promise<Checkpoint[]> { ... }
export async function createCheckpoint(workspaceId: number, data: CreateCheckpoint): Promise<Checkpoint> { ... }
export async function updateCheckpoint(workspaceId: number, id: number, data: UpdateCheckpoint): Promise<Checkpoint> { ... }
export async function deleteCheckpoint(workspaceId: number, id: number): Promise<void> { ... }

// Phase 2
export async function getCompareStats(params: CompareParams): Promise<CompareResponse> { ... }

// Phase 3
export async function getIdentities(): Promise<Identity[]> { ... }
export async function createIdentity(data: CreateIdentity): Promise<Identity> { ... }
export async function updateIdentity(id: number, data: UpdateIdentity): Promise<Identity> { ... }
export async function deleteIdentity(id: number): Promise<void> { ... }
export async function createAlias(identityId: number, data: CreateAlias): Promise<Alias> { ... }
export async function deleteAlias(identityId: number, aliasId: number): Promise<void> { ... }
export async function getIdentityStats(id: number, params?: StatParams): Promise<HeroStats> { ... }

// Phase 4
export async function getViews(): Promise<AnalysisView[]> { ... }
export async function createView(data: CreateView): Promise<AnalysisView> { ... }
export async function updateView(id: number, data: UpdateView): Promise<AnalysisView> { ... }
export async function deleteView(id: number): Promise<void> { ... }
```

### 11.4 New Frontend Components (Summary)

| Component | Phase | Location | Purpose |
|-----------|-------|----------|---------|
| `WorkspaceSwitcher` | 1 | Sidebar header | Dropdown to switch active workspace |
| `CheckpointSelect` | 1 | FilterBar | "Since" dropdown with checkpoint list |
| `CheckpointQuickCreate` | 1 | FilterBar popover | Inline form to create checkpoint |
| `CheckpointLines` | 1 | GraphPage | Recharts ReferenceLine wrappers |
| `WorkspaceSettingsPage` | 1 | /settings/workspaces | CRUD for workspaces |
| `CheckpointSettingsPage` | 1 | /settings/checkpoints | CRUD for checkpoints |
| `ComparePage` | 2 | /compare | Full compare UI |
| `PeriodSelector` | 2 | ComparePage | Period selection with checkpoint shortcuts |
| `CompareTable` | 2 | ComparePage | Side-by-side stat table with deltas |
| `IdentitySettingsPage` | 3 | /settings/identities | CRUD for identities |
| `AliasManager` | 3 | Identity detail | Add/remove workspace aliases |
| `TagEditor` | 3 | Identity detail | Tag management |
| `ExclusionBar` | 3 | PopulationPage | Quick exclude toggles |
| `ViewSwitcher` | 4 | Sidebar header (replaces WorkspaceSwitcher) | Switch analysis views |
| `ViewBuilder` | 4 | /settings/views/new | Create/edit analysis views |
| `ViewSettingsPage` | 4 | /settings/views | CRUD for views |

### 11.5 New Routes

```tsx
// Phase 1
<Route path="/settings" element={<SettingsPage />} />
<Route path="/settings/workspaces" element={<WorkspaceSettingsPage />} />

// Phase 2
<Route path="/compare" element={<ComparePage />} />

// Phase 3
<Route path="/settings/identities" element={<IdentitySettingsPage />} />
<Route path="/players/identity/:identityId" element={<IdentityProfilePage />} />

// Phase 4
<Route path="/settings/views" element={<ViewSettingsPage />} />
<Route path="/settings/views/new" element={<ViewBuilderPage />} />
<Route path="/settings/views/:viewId/edit" element={<ViewBuilderPage />} />
```

---

## 12. Migration & Backwards Compatibility

### 12.1 Phase 1 Migration Procedure

Runs automatically on app startup when `workspaces` table doesn't exist. Executed inside `init_schema()` in `backend/app/db.py`.

**Step-by-step**:

```python
def _migrate_to_workspaces(conn):
    """One-time migration: create workspaces, assign all existing hands to default workspace."""

    # 1. Create workspaces table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workspaces (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL UNIQUE,
            hero_username VARCHAR NOT NULL DEFAULT 'Hero',
            hero_site VARCHAR NOT NULL DEFAULT 'GG',
            description TEXT,
            color VARCHAR,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_workspaces START 2")  # start at 2 since we insert id=1

    # 2. Create default workspace from existing settings
    hero_username = conn.execute(
        "SELECT value FROM settings WHERE key = 'hero_username'"
    ).fetchone()
    hero_site = conn.execute(
        "SELECT value FROM settings WHERE key = 'hero_site'"
    ).fetchone()

    conn.execute(
        "INSERT INTO workspaces (id, name, hero_username, hero_site) VALUES (1, 'My Game', ?, ?)",
        [
            hero_username[0] if hero_username else 'Hero',
            hero_site[0] if hero_site else 'GG',
        ],
    )

    # 3. Add workspace_id column to hands
    conn.execute("ALTER TABLE hands ADD COLUMN workspace_id INTEGER DEFAULT 1")

    # 4. Backfill (all existing hands → workspace 1)
    conn.execute("UPDATE hands SET workspace_id = 1 WHERE workspace_id IS NULL")

    # 5. Add composite unique index
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_hands_workspace_id ON hands(workspace_id, id)")

    # 6. Add workspace-scoped indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_workspace ON hands(workspace_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_hands_workspace_played ON hands(workspace_id, played_at)")

    # 7. Create checkpoints table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            id INTEGER PRIMARY KEY,
            workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name VARCHAR NOT NULL,
            checkpoint_at TIMESTAMP NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_checkpoints START 1")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_workspace ON checkpoints(workspace_id)")

    # 8. Remove global hero settings (workspace has them now)
    conn.execute("DELETE FROM settings WHERE key IN ('hero_username', 'hero_site')")

    # 9. Mark migration complete
    conn.execute("INSERT OR REPLACE INTO settings VALUES ('workspace_migration', '1')")
```

**Detection**: Check `workspace_migration` setting key or try `SELECT 1 FROM workspaces LIMIT 1` — if table doesn't exist, run migration.

### 12.2 API Backwards Compatibility

All existing API calls work without any changes:
- `workspace_id` defaults to `1` when omitted
- The default workspace (id=1) contains all pre-existing data
- Frontend can be deployed incrementally — old frontend works with new backend

### 12.3 Import Cache Considerations

The `_player_cache` in `import_hands.py` maps `username → player_id`. Players are shared across workspaces (the `players` table is not workspace-scoped). This means:

- If "Hero" exists in workspace 1 and you create workspace 2 with hero "Hero", they share the same `players.id`
- But `get_hero_player_id(db, workspace_id)` correctly resolves per workspace
- The player cache doesn't need workspace awareness — it's already keyed by username

### 12.4 Stat Rebuild Considerations

The current rebuild mechanism (`/api/import/rebuild`) re-parses all hands from `raw_text`. After Phase 1:
- Rebuild should be workspace-scoped: `POST /api/import/rebuild?workspace_id=1` rebuilds only that workspace's hands
- The lock behavior stays the same (global write lock during rebuild)
- `STAT_VERSION` bump still triggers auto-rebuild of all hands across all workspaces

### 12.5 Export/Import Database

- `GET /api/import/export` — exports the entire DuckDB file (all workspaces). This is the simplest approach.
- `POST /api/import/database` — imports a full database file (replaces everything including all workspaces).
- Future consideration: per-workspace export/import (Phase 1 scope: not included, revisit later).

---

## 13. Edge Cases & Error Handling

### 13.1 Workspace Edge Cases

| Scenario | Behavior |
|----------|----------|
| Delete last workspace | API returns 400: "Cannot delete the last workspace" |
| Create workspace with duplicate name | API returns 400: "Workspace name already exists" |
| Switch to deleted workspace (race condition) | Frontend detects 404, falls back to first available workspace |
| Import with no workspace selected | Frontend always sends workspace_id from context; API defaults to 1 |
| Workspace has 0 hands | All pages show EmptyState with import CTA (existing behavior) |

### 13.2 Checkpoint Edge Cases

| Scenario | Behavior |
|----------|----------|
| Checkpoint date is in the future | Allowed — user might set a future strategy change date |
| Checkpoint date is before any hands | "Since" filter returns 0 hands — EmptyState shown |
| Two checkpoints at exact same time | Allowed — ordered by ID as tiebreaker |
| Delete checkpoint that's selected in FilterBar | Frontend clears the selection, reverts to "All Time" |
| Workspace deleted with checkpoints | Cascading delete removes all checkpoints |

### 13.3 Compare Edge Cases

| Scenario | Behavior |
|----------|----------|
| Periods overlap | Allowed — user's choice, but show warning: "Periods overlap by X days" |
| Period has 0 hands | Show "No hands in this period" instead of stats |
| Period has <50 hands | Show all stats but with low-confidence warning banner |
| Identical periods selected | Show stats but with info: "Both periods are identical" |

### 13.4 Identity Edge Cases (Phase 3)

| Scenario | Behavior |
|----------|----------|
| Link player that's already linked to another identity | API returns 400: "Player already linked to identity [name]" |
| Delete identity with aliases | Aliases are deleted (link removed), hand data untouched |
| Two identities linked to same workspace | Allowed (different players in the same workspace) |
| Identity with no aliases | Shown in list with "No aliases — link a player" prompt |

### 13.5 Hand ID Collision

| Scenario | Behavior |
|----------|----------|
| Same hand ID in two workspaces | Allowed by design (composite unique: workspace_id + id) |
| Same hand ID imported twice in same workspace | Treated as duplicate, skipped (existing dedup logic) |
| Hand from workspace A referenced in workspace B query | Not possible — all queries filter by workspace_id |

---

## 14. Open Questions

### 14.1 Design Decisions

1. **Workspace switcher location**: Top of sidebar (proposed) vs top header bar vs breadcrumb area? Sidebar is consistent with other tools (Notion, Linear) but takes space in collapsed mode.

2. **Settings page vs modals**: Should workspace/checkpoint management be a dedicated page (`/settings/workspaces`) or a modal triggered from the sidebar? Page is more spacious but adds navigation; modal is quicker but cramped for CRUD lists.

3. **Checkpoint quick-create scope**: Popover from FilterBar (proposed) or always navigate to Settings? The popover is faster but harder to implement well.

4. **Compare page stat selection**: Show ALL stats by default (long table, scrollable) or let users pick which stat groups to show? Recommendation: show all by default with collapsible sections.

5. **Export scope**: "Export Database" exports entire DB (all workspaces) or just active workspace? Recommendation: entire DB for simplicity; per-workspace export as future enhancement.

6. **Soft delete vs hard delete for workspaces**: Hard delete with confirmation (proposed) vs soft delete with recovery period? Given local-only nature, hard delete with strong confirmation (type workspace name) seems appropriate.

7. **Graph checkpoint click behavior**: Should clicking a checkpoint line on the graph filter "since that checkpoint"? Or is hover-to-see-name sufficient?

### 14.2 Technical Decisions

8. **DuckDB hand ID migration strategy**: Keep `hands.id` as VARCHAR PK and add a separate `UNIQUE(workspace_id, id)` index (simpler, proposed), or recreate the table with a composite PK (cleaner but requires careful data migration)?

9. **DuckDB JSON vs LIST type**: Analysis views use JSON text for array fields. DuckDB supports native `INTEGER[]` (LIST) type. Should we use LIST for better query performance, or stick with JSON TEXT for simplicity and cross-DB compatibility?

10. **Player cache invalidation**: The `_player_cache` in `import_hands.py` is global. With workspaces, players are shared. Does the cache need any workspace awareness? (Analysis: probably not — players are keyed by username, not workspace.)

11. **Stat rebuild scoping**: Should `STAT_VERSION` bumps rebuild all workspaces at once, or should rebuild be per-workspace? All-at-once is simpler; per-workspace allows faster startup if only one workspace is affected.

12. **Population query performance**: Cross-workspace population queries (Phase 4) scan hands from multiple workspaces. For large databases (100k+ hands), should we add materialized summary tables? Defer until performance is actually measured.

13. **Frontend state management**: Use React Context (proposed) or Zustand/Jotai for workspace state? Context is fine for a single global value; Zustand is lighter for derived state. Recommendation: React Context for workspace/view selection, React Query for data fetching (already used).

14. **URL state for active workspace**: Should the active workspace be in the URL (`/stats?workspace_id=3`) or only in localStorage? URL makes links shareable within the same machine; localStorage is simpler. Recommendation: localStorage only — this is a local app.

15. **Concurrent workspace access**: Can the user have two browser tabs showing different workspaces? With localStorage, switching workspace in one tab doesn't update the other. Consider: BroadcastChannel API to sync tabs, or just accept the limitation.

### 14.3 Future Considerations (Out of Scope)

16. **Per-workspace export**: Export only one workspace as a portable file (for sharing student HH bundles).

17. **Workspace templates**: Pre-configured workspace settings for common scenarios ("New Student", "My Game", "Field Study").

18. **Checkpoint goals**: Attach target stat values to a checkpoint (e.g., "goal: get VPIP to 24-26%"). Compare page could then show progress toward goals.

19. **Auto-checkpoints**: Automatically create checkpoints at stake changes, session gaps > 7 days, or other detectable milestones.

20. **Workspace sharing**: Export a workspace as a file that another OHM user can import.
