# OHM Extensibility & Plugin Architecture

*March 2026*

---

## The Opportunity

No poker tracker has a public API, JSON export, webhook system, or plugin architecture. Zero. PT4 hides its PostgreSQL schema. H2N's formula language can't be extended. HM3 is a black box. This is like the analytics world before PostHog said "here's SQL access to your own data."

OHM already has **60+ REST endpoints** covering hands, stats, sessions, players, population, workspaces, checkpoints, compare, and identities. The API exists -- it just isn't documented, versioned, or marketed as a feature.

**Extensibility is the third pillar** alongside multi-site parsers and the NL query engine:

| Pillar | What It Does | Who It Serves |
|--------|-------------|---------------|
| Multi-site parsers | Breadth -- more users from more sites | All players |
| NL query engine | Depth -- ask anything about your data | Study-focused grinders |
| Extensibility / API | Platform -- let others build on top | Developers, coaches, content creators |

---

## What Poker Players Actually Build When Given Extensibility

Based on research across Hand2Note's HUD Store ($50-$599 stat packs), PT4's 125+ community reports, and forum/Reddit requests:

### Things People Pay For (H2N HUD Store)
- Custom HUD layouts with specialized stat arrangements ($99-$349)
- Population analysis popups (Mass Data Analysis packs)
- Stake-specific stat packs (6-max cash, MTT, Spins, PLO)
- Color-coded opponent categorization rules

### Things People Build for Free (PT4 Community)
- Situational reports: "CBet 2 Barrels & Lost the Hand," "Flopped Sets by Pocket Pair," "All-In Equity under 51%"
- Positional filters: "Hero=BB, Villain=SB, Unopened Pot"
- Leak-finding reports: "Winrate confidence," "Big Win Hands," "Bust Out Hands"
- Custom stat formulas combining base stats into derived metrics

### Things People Desperately Want But Can't Build
- **REST API access** to their own data (no tracker offers this)
- **CSV/JSON export** (only Poker Copilot does CSV)
- **Solver integration** -- compare actual play to PioSolver/GTO Wizard solutions
- **Discord/webhook alerts** -- session results posted automatically, tilt alerts
- **Cross-tool import** -- move data between H2N, PT4, HM3 without re-importing raw files
- **Automated leak detection** -- "find where I'm losing money" without manual digging
- **Custom parsers** for unsupported sites (Ignition, ClubGG, PokerMatch, CoinPoker)

---

## Ecosystem Research: What Works

### Best-Fit Models for OHM

| Ecosystem | Key Pattern to Steal | Why It Fits |
|-----------|---------------------|-------------|
| **Obsidian** | GitHub-based distribution, TypeScript plugins, built-in browser, auto-cleanup | Closest analog: local-first desktop app, niche community, 2000+ plugins |
| **VS Code** | Declarative manifest (`contributes`), lazy activation events | Register capabilities without loading code; activate on demand |
| **PostHog** | Pipeline hooks (processEvent, onEvent) | Maps to parse->compute->insert pipeline |
| **DuckDB** | Auto-loading extensions, community extension repo | When a PokerStars file is detected with no parser -> auto-suggest plugin |
| **Raycast** | Opinionated UI components, worker thread isolation | Fixed component set for plugins = visual consistency + security |

### What Makes Plugin Ecosystems Succeed (Ranked)

1. **Low barrier to entry** -- Use tech developers already know (TypeScript/Python)
2. **Rich but stable API** -- Expose enough to be useful, type it, version it
3. **First-party tooling** -- `create-plugin` CLI, template repo, hot reload
4. **Built-in discovery** -- In-app plugin browser, not a separate website
5. **GitHub as infrastructure** -- Source, releases, and review all on GitHub. Zero cost.
6. **Auto-cleanup** -- Obsidian's `registerEvent`/`addCommand` prevents leaks from disabled plugins

---

## Architecture: Three Extension Layers

```
+-----------------------------------------------------------+
|  Layer 3: Plugin System                                    |
|  Full Python/TypeScript plugins with lifecycle hooks       |
|  Parser plugins, stat plugins, UI panels, custom pages     |
|  -> For developers building tools on OHM                   |
+-----------------------------------------------------------+
|  Layer 2: Events & Webhooks                                |
|  Subscribe to events: hand_imported, session_ended,        |
|  stat_threshold_crossed                                    |
|  -> For automation (Discord bots, alerts, pipelines)       |
+-----------------------------------------------------------+
|  Layer 1: Documented REST API + Export                     |
|  60+ existing endpoints, documented, versioned             |
|  + JSON/CSV export + direct DuckDB SQL endpoint            |
|  -> For anyone wanting to read/analyze poker data          |
+-----------------------------------------------------------+
```

### Layer 1: Documented API + Export

**What to do**: Document and market what already exists. OHM has 60+ endpoints. No competitor has a public API at all.

**Concrete steps:**
1. Write `/api/docs` page (FastAPI already auto-generates Swagger at `/docs`)
2. Add `GET /api/export/hands?format=json|csv` -- export filtered hands as JSON or CSV
3. Add `GET /api/export/stats?format=json|csv` -- export stats breakdown
4. Add `POST /api/query/sql` -- execute arbitrary read-only SQL against DuckDB (power users)
5. Version the API: `/api/v1/...` prefix
6. Publish schema documentation (`SCHEMA.md`) -- every table, every column, plain English

**Existing endpoints to highlight as "API features":**

| Category | Endpoints | What It Enables |
|----------|-----------|----------------|
| Stats | `GET /api/stats/hero`, `/stats/range`, 12 stat detail endpoints | Build custom dashboards, coaching tools |
| Hands | `GET /api/hands`, `/hands/{id}` | Hand review tools, content creation |
| Sessions | `GET /api/sessions`, `/sessions/{idx}` | Session tracking apps, bankroll managers |
| Players | `GET /api/players`, `/players/{id}/stats`, `/players/{id}/head-to-head` | Opponent scouting tools |
| Population | 8 endpoints (overview, preflop, postflop, segments, etc.) | Population analysis tools, coaching platforms |
| Graph | `GET /api/reports/graph`, `/reports/breakdown`, `/reports/drift` | Custom visualizations, tracking dashboards |
| Compare | `GET /api/compare/stats` | A/B testing tools, progress tracking |
| Import | `POST /api/import/files/stream` (NDJSON) | Automated import pipelines |
| DB | `GET /api/import/export` | Backup tools, data migration |

### Layer 2: Events & Webhooks

**Event types:**

```python
# Import events
hand_imported(hand_id, workspace_id, stakes, won_bb)
import_completed(workspace_id, imported_count, duration_ms)

# Session events
session_detected(session_index, workspace_id, hands, won_bb, duration_min)
session_ended(session_index, workspace_id, summary)

# Threshold events (user-configurable)
stat_threshold_crossed(stat_key, current_value, threshold, direction)
# e.g., "your VPIP dropped below 20% over the last 500 hands"

loss_threshold_crossed(amount_bb, session_index)
# e.g., "you've lost more than 10 buy-ins this session"

# Player events
new_player_seen(player_id, username, workspace_id)
player_classified(player_id, player_type, workspace_id)
```

**Delivery mechanisms:**

| Method | Use Case | Complexity |
|--------|----------|------------|
| **In-app event bus** (pub/sub) | Plugin system, frontend reactivity | Low -- Python `asyncio` events |
| **Webhook (HTTP POST)** | Discord bots, external apps | Medium -- configurable URL in settings |
| **File watch / log** | Simple automation, scripting | Low -- append to `~/.ohm/events.jsonl` |
| **WebSocket** | Real-time dashboards, OBS overlay | Medium -- FastAPI WebSocket endpoint |

**Start with**: In-app event bus (needed for plugins anyway) + webhook delivery (most useful for users).

### Layer 3: Plugin System

Inspired by Obsidian (simplicity, GitHub distribution) + VS Code (declarative manifest, lazy activation) + PostHog (pipeline hooks).

#### Plugin Types

```
+--------------------------------------------------+
| Parser Plugin                                     |
| Adds support for a new poker site                 |
| Python only (backend)                             |
| Implements: detect(), split_hands(), parse()      |
| Example: pokerstars-parser, 888-parser            |
+--------------------------------------------------+
| Stat Plugin                                       |
| Adds custom computed statistics                   |
| Python (SQL expressions or compute functions)     |
| Registers: stat definitions with SQL formulas     |
| Example: mdf-stat, equity-realization-stat        |
+--------------------------------------------------+
| Panel Plugin                                      |
| Adds custom visualization to stats/hands pages    |
| TypeScript/React (frontend)                       |
| Renders: React component receiving OHM data       |
| Example: equity-graph, board-texture-chart         |
+--------------------------------------------------+
| Page Plugin                                       |
| Adds an entirely new page/tab to OHM              |
| TypeScript/React (frontend) + optional Python     |
| Full page with own route, data fetching, UI       |
| Example: tournament-tracker, bankroll-manager     |
+--------------------------------------------------+
| Hook Plugin                                       |
| Reacts to events in the pipeline                  |
| Python (backend)                                  |
| Hooks: before_insert, after_insert, on_session    |
| Example: auto-tagger, discord-notifier            |
+--------------------------------------------------+
```

#### Plugin Manifest (VS Code-inspired)

```json
{
  "id": "ohm-pokerstars-parser",
  "name": "PokerStars Support",
  "version": "1.0.0",
  "description": "Parse PokerStars hand histories",
  "author": "community",
  "repo": "https://github.com/user/ohm-pokerstars-parser",
  "minAppVersion": "0.2.0",
  "type": "parser",

  "contributes": {
    "parsers": [{
      "siteId": 2,
      "siteName": "PokerStars",
      "siteCode": "PS",
      "filePatterns": ["HH*.txt", "*.txt"],
      "detectionMarker": "PokerStars Hand #"
    }],
    "stats": [{
      "id": "wwsf",
      "name": "Won When Saw Flop",
      "category": "showdown",
      "sql": "COUNT(*) FILTER (WHERE saw_flop AND won_bb > 0) * 100.0 / NULLIF(COUNT(*) FILTER (WHERE saw_flop), 0)"
    }],
    "panels": [{
      "id": "equity-curve",
      "name": "Equity Curve",
      "page": "stats",
      "component": "EquityCurve"
    }],
    "pages": [{
      "id": "tournaments",
      "path": "/tournaments",
      "name": "Tournaments",
      "icon": "trophy"
    }],
    "settings": [{
      "id": "auto-tag",
      "type": "boolean",
      "title": "Auto-tag interesting hands",
      "default": true
    }],
    "hooks": [
      "after_insert"
    ]
  },

  "activationEvents": [
    "onImport:pokerstars",
    "onPage:tournaments"
  ]
}
```

#### Backend Plugin API (Python)

```python
from ohm_plugin import OHMPlugin, ParsedHand, HandContext

class PokerStarsParser(OHMPlugin):
    """Parser plugin for PokerStars hand histories."""

    # --- Parser interface ---

    def detect(self, raw_text: str) -> bool:
        """Return True if this text is from PokerStars."""
        return "PokerStars Hand #" in raw_text[:100]

    def split_hands(self, raw_text: str) -> list[str]:
        """Split a multi-hand file into individual hand texts."""
        return raw_text.split("PokerStars Hand #")[1:]

    def extract_hand_id(self, raw_text: str) -> str:
        """Extract the unique hand ID from a single hand text."""
        ...

    def parse_hand(self, raw_text: str) -> ParsedHand:
        """Parse a single hand history into a ParsedHand."""
        ...

    # --- Hook interface (optional) ---

    def after_insert(self, ctx: HandContext) -> None:
        """Called after a hand is inserted into the database."""
        if ctx.won_bb > 50:
            ctx.add_tag("big-pot")

    # --- Custom stat registration (optional) ---

    def register_stats(self) -> list[dict]:
        """Register custom stats computed from hand_players."""
        return [{
            "id": "wwsf",
            "name": "Won When Saw Flop",
            "sql": "COUNT(*) FILTER (WHERE saw_flop AND won_bb > 0) * 100.0 / ..."
        }]
```

#### Frontend Plugin API (TypeScript)

```typescript
import { OHMPlugin, StatPanel, useOHMData } from "@ohm/plugin-api";

// Panel plugin -- renders inside the stats page
export class EquityCurvePanel extends OHMPlugin {
  onload() {
    // Obsidian-style registration with auto-cleanup
    this.addStatPanel("equity-curve", EquityCurve);
    this.addSettingTab(EquityCurveSettings);
    this.registerEvent(this.app.on("hand_imported", this.onHand));
  }
}

// React component for the panel
function EquityCurve({ filters }: StatPanel.Props) {
  // useOHMData hook -- queries the API with current filters
  const { data, loading } = useOHMData("/api/reports/graph", filters);

  if (loading) return <Skeleton />;
  return <LineChart data={data.points} />;
}

// Page plugin -- adds a new route
export class TournamentPage extends OHMPlugin {
  onload() {
    this.addPage("/tournaments", {
      name: "Tournaments",
      icon: "trophy",
      component: TournamentView,
    });
  }
}
```

#### Plugin Discovery & Installation (Obsidian model)

```
1. Registry: community-plugins.json in github.com/ohm-poker/plugins

   [
     {
       "id": "ohm-pokerstars-parser",
       "name": "PokerStars Support",
       "author": "contributor",
       "description": "Parse PokerStars hand histories",
       "repo": "https://github.com/user/ohm-pokerstars-parser",
       "type": "parser"
     },
     ...
   ]

2. In-app browser: Settings > Plugins > Browse Community Plugins
   - Search, filter by type (parser, stat, panel, page, hook)
   - One-click install (downloads from GitHub Release)
   - Enable/disable toggle per plugin

3. Installation: Downloads manifest.json + plugin files to
   ~/.ohm/plugins/<plugin-id>/

4. Submission: Open PR to ohm-poker/plugins adding entry to JSON
   - Automated: manifest validation, lint, build check
   - Manual: code review by maintainer

5. Updates: App checks GitHub releases for new versions
   - Shows update indicator in plugin browser
   - One-click update
```

#### Plugin Development Workflow

```bash
# Scaffold a new plugin
npx create-ohm-plugin my-parser --type parser

# Develop with hot reload
cd my-parser
npm run dev  # loads into running OHM instance

# Test
npm run test

# Build for distribution
npm run build  # produces manifest.json + main.js/plugin.py

# Publish
# 1. Create GitHub Release with built files
# 2. Open PR to ohm-poker/plugins registry
```

---

## Security Model

### Approach: Obsidian-style (Trust, Don't Sandbox)

For a niche open-source desktop app with a small community:

| Concern | Mitigation |
|---------|------------|
| Malicious plugins | All plugins open source, code review on registry submission |
| Data safety | Backend plugins get read-only DB cursor by default. Write access requires explicit `"permissions": ["write"]` in manifest. |
| Network access | No restriction (plugins may need API calls). Trust model. |
| Frontend isolation | Plugin React components run in same process. Could use iframe sandbox later if needed. |
| SQL injection via stat plugins | Stat SQL expressions are parameterized and validated before execution |
| Plugin crashes | Try/except around plugin hooks. Failed plugin = disabled + error logged, app continues. |

### Why Not Sandbox?

- The user base is small and technical (poker grinders who code)
- Sandboxing adds massive complexity for minimal benefit at this scale
- Obsidian proved this works: 2000+ plugins, no sandbox, minimal security incidents
- If OHM reaches 10K+ users, consider adding iframe isolation for frontend plugins

---

## Integration Opportunities

### PioSolver UPI Bridge

PioSolver has a mature text-based protocol (UPI, inspired by UCI for chess). A plugin could:

```python
class PioSolverBridge(OHMPlugin):
    """Compare your actual play to PioSolver solutions."""

    def after_insert(self, ctx: HandContext):
        if not ctx.went_to_showdown:
            return

        # Build PioSolver tree for this spot
        solver = PioSolver(path=self.settings["pio_path"])
        solver.set_board(ctx.board)
        solver.set_ranges(ctx.position, ctx.villain_position)
        solver.go()  # solve

        # Compare hero's action to GTO
        gto_strategy = solver.show_strategy(ctx.node_id)
        hero_action = ctx.hero_action

        # Tag hands where hero deviated significantly from GTO
        if deviation(hero_action, gto_strategy) > 0.2:
            ctx.add_tag("gto-deviation")
            ctx.add_note(f"GTO: {gto_strategy}, You: {hero_action}")
```

### Discord Bot (via webhooks)

```python
# External Discord bot -- not a plugin, just consumes the webhook API

@bot.event
async def on_ohm_webhook(payload):
    if payload["event"] == "session_ended":
        summary = payload["data"]
        embed = discord.Embed(
            title=f"Session Complete -- {summary['duration_min']}min",
            description=f"**{summary['won_bb']:+.1f} bb** ({summary['bb_per_100']:+.1f} bb/100)",
            color=0x00ff00 if summary['won_bb'] > 0 else 0xff0000
        )
        embed.add_field(name="Hands", value=summary["hands"])
        embed.add_field(name="VPIP/PFR", value=f"{summary['vpip']}% / {summary['pfr']}%")
        await channel.send(embed=embed)
```

### Coaching Platform API

```
Poker coaching platform (RunItOnce, Pokercoaching.com)
  |
  Fetches student data via OHM API
  |
  GET /api/stats/hero?workspace_id=1
  GET /api/reports/drift?workspace_id=1
  GET /api/reports/breakdown?workspace_id=1
  |
  Generates coaching report
```

---

## Community Plugin Ideas

Ranked by user value, feasibility, and community demand. See [ROADMAP.md](../../ROADMAP.md) for timeline.

### 1. PokerStars Parser
Parses PokerStars .txt hand histories. Doubles OHM's addressable market. The "hello world" of OHM plugins. **Effort:** Medium (1-2 weekends).

### 2. Discord Session Bot
Automatically posts session summaries to Discord when you finish playing. **Depends on:** webhook/event system. **Effort:** Low (50-100 lines).

### 3. OBS Stream Overlay
Transparent HTML page showing live session stats as OBS Browser Source. Auto-updates via WebSocket. No poker tracker offers this. **Effort:** Medium.

### 4. PioSolver Bridge
Compares your actual play to PioSolver solutions. Flags GTO deviations. GTO Wizard charges $89-149/mo for this. **Effort:** High (2-4 weeks).

### 5. Tilt Detector
Monitors rolling VPIP/PFR/aggression over last 20-50 hands. Desktop notification when stats deviate from baseline. **Effort:** Low-Medium.

### 6. Bankroll Manager
Tracks bankroll across sites, sets buy-in rules, shows when to move up/down. **Effort:** Low-Medium.

### 7. Hand History Converter (Ignition/Bovada)
Converts anonymous-player hand histories into OHM's format. Largest US-facing network, no free tracking options. **Effort:** Medium.

### 8. Auto Study Tagger
Automatically tags hands for review based on configurable rules (big pots, coolers, bluffs, squeeze spots). **Effort:** Low.

### 9. Tournament Support (MTT/SNG)
Tournament tracking: buy-ins, finishes, ROI, ITM%, ICM analysis. Major architecture extension. **Effort:** High (3-4 weeks).

### 10. Coaching Dashboard
Read-only view for coaches reviewing student data. Annotate hands, assign homework, track progress. B2B monetization opportunity. **Effort:** Medium.

### Plugin Priority Matrix

| Plugin | User Value | Dev Effort | Who Builds | When |
|--------|-----------|------------|------------|------|
| PokerStars Parser | Very High | Medium | Community | Month 1-2 |
| Discord Session Bot | High | Low | Community | Month 2-3 |
| OBS Stream Overlay | Very High | Medium | Core team | Month 3-4 |
| Auto Study Tagger | High | Low | Community | Month 2-3 |
| Tilt Detector | High | Low-Med | Community | Month 3-4 |
| Bankroll Manager | Medium | Low-Med | Community | Month 4-6 |
| HH Converter (Ignition) | High | Medium | Community | Month 4-6 |
| PioSolver Bridge | Very High | High | Core/Advanced | Month 6-8 |
| Tournament Support | High | High | Dedicated contributor | Month 6-12 |
| Coaching Dashboard | High | Medium | Core team | Month 9-12 |

---

## The Platform Flywheel

```
More documented API -> more external tools built on OHM
       |
More tools -> more users choose OHM as their data layer
       |
More users -> more community plugins (parsers, stats, panels)
       |
More plugins -> more poker sites supported, more features
       |
More features -> more users -> more tools -> ...
```

The API is the moat. The plugins are the lock-in. The community is the growth engine.
