# Integrated Product + Marketing Roadmap

> Updated 2026-10-18. Replaces the "query engine is the launch" plan from March 2026.
> No dates: phases run in order, each item carries an effort estimate.

**Effort scale** (focused work, not calendar time):
**S** = a session or two · **M** = a few days · **L** = one to two weeks · **XL** = several weeks, split into milestones

## Where we are

OHM is at v0.0.10 alpha, not publicly launched. Constraints: 5-15 hrs/week, zero budget, dual goal of
user adoption + portfolio credibility. Done since the last roadmap:

- **7 site parsers** (GG, PS, 888, WPN, Winamax, iPoker, partypoker), each checked by a per-hand money
  invariant on every fixture hand.
- **25 data-safety and money bugs** from the uhayate fork fixed, plus ~10 more found along the way
  ([docs/specs/BUGS-FROM-FORK.md](docs/specs/BUGS-FROM-FORK.md)): clean shutdown, WAL recovery,
  transactional import and rebuild, all-in EV in packaged builds.
- **Import from Hand2Note 4** in one click ([docs/specs/H2N-IMPORT.md](docs/specs/H2N-IMPORT.md)):
  75,865 real hands, 0 errors.
- **Hand2Note-compatible stats and General screen**
  ([docs/specs/H2N-COMPATIBLE-STATS.md](docs/specs/H2N-COMPATIBLE-STATS.md)): 102/102 cells identical to
  Hand2Note on 75,849 real hands; stat popup (Range / Boards / Bet Sizes / Hands); Hand2Note's money rules
  for winnings, rake and all-in EV. The Stats page uses the same definitions.

## Strategy: "Hand2Note, free and open source"

Hand2Note dropped its free tier (Jan 2025) and is closed. OHM reads a Hand2Note database in one click and
shows the same numbers. That's the launch story, and it beats "PostHog for poker": players switch tools
for **their numbers and their HUD**, not for a query language.

Positioning:
- **Switch in one click, same numbers.** Import from Hand2Note (PT4 / HM3 next), parity 102/102.
- **Free and open source** (AGPL), Mac + Windows + Linux, fully local.
- **Open data**: DuckDB, documented schema, REST API, SQL. The NL query engine stays on the roadmap as a
  differentiator, not as the launch gate (see [docs/vision/MONETIZATION.md](docs/vision/MONETIZATION.md):
  it's a UX feature, not a revenue line).

Launch in two steps, because the main market can't use a HUD anyway: **GGPoker doesn't allow third-party
HUDs**, so GG grinders (and the CIS market) need exactly what's built now. Soft-launch to them first, then
the big launch once the HUD covers the sites that allow one.

## Core Principle

**Never build silently.** Every phase ends with a release that has a story to tell:
build -> ship -> promote -> listen -> build.

---

## Phase 0: Must-haves + soft launch

### Ship what's done
| Item | Effort |
|---|---|
| Split the `fix/fork-bugs` branch into reviewable commits, release **v0.1.0** (`STAT_VERSION` bump = one rebuild per install; release notes cover the money, position and stat-definition changes) | S |
| Clean-machine install test on macOS and Windows; verify Hand2Note's default database path on Windows | S |
| One source of truth per stat: decide the Stats page vs General page split (General = Hand2Note layout, Stats = OHM extras like BB defense) | S |

### Must-have features
| Item | Effort |
|---|---|
| **Auto-import**: watch hand history folders per site, import new hands as they're written. Also the foundation of the HUD | M |
| **Import from PokerTracker 4 / Holdem Manager 3**: both keep the original hand history text in PostgreSQL; extract it and reuse the parsers, like the Hand2Note import | M (S per tool once the first one exists) |
| **Line filters**: UI builder ("3-bet BTN -> called -> c-bet flop -> faced raise") on the Hand2Note-compatible action matcher that already exists; applies to every report, graph and the hand list. Builder part of [docs/specs/QUERY-ENGINE-PRD.md](docs/specs/QUERY-ENGINE-PRD.md) | L |
| **Preflop range grid** (13x13) in the stat popup for preflop stats | S |
| **Opponent selector** on the General page (any player, vs-hero values) | M |
| **Smart reports**: Hand2Note-style next-action drill-down (faced next / next actions) from the popup | M |

### Marketing -- soft launch
- GitHub README + release with screenshots: General screen side by side with Hand2Note
- **2+2 Software forum + r/GGPoker**: "Free open-source Hand2Note alternative -- import your H2N database in
  one click, same numbers (102/102 stats on 75k hands)". GG players first: they can't use a HUD anyway
- Russian GG community (Telegram, gipsyteam): the same post in Russian

### Gate: clean install works on both OSes, auto-import + PT4/HM3 import shipped, v0.1.0 released.

---

## Phase 1: HUD -- the key feature for poker players

The HUD is why most players pay for a tracker. It goes first, right after the must-haves. **Overall: XL.**

### Scope
- **Sites**: those that allow third-party HUDs -- PokerStars, WPN, iPoker, 888, Winamax, partypoker (check
  each site's current HUD policy before shipping). **Not GGPoker** (prohibited; GG players get the review
  tools instead)
- HUD numbers come from the same Hand2Note-compatible matcher, so they equal the General screen

| Item | Effort |
|---|---|
| Research: Hand2Note's default HUD and HUD-popup layouts (which stats, where), described in our own words like the General screen | S |
| **Real-time pipeline**: tail hand history files as hands finish (on top of auto-import), incremental stat updates per player, under 100 ms per table refresh with 20 tables open | M |
| **Table detection**: find table windows per site (title parsing), map seats per table size, follow move/resize/minimize | L |
| **Overlay windows**: transparent always-on-top panels per table, Windows first (most of the HUD market) | L |
| macOS overlay support (window APIs and permissions differ) | L |
| **HUD stats panel**: default layout VPIP / PFR / 3-Bet / Fold to 3-Bet / C-Bet / Fold to C-Bet / Steal / hands, sample-size display | M |
| **HUD popups**: click a stat -> the same popup as the General page (Range / Boards / Bet Sizes / Hands) | M |
| **Player notes, tags, color labels** (player type classification already exists) | M |
| **Layout editor**: drag stats, per table size, import/export layouts as JSON | L |

### Milestones
1. **HUD v0**: PokerStars on Windows, fixed default layout, real-time stats
2. **HUD v1**: all HUD-friendly sites, macOS, popups, notes, layout editor

### Marketing -- the big launch
**"Free, open-source Hand2Note alternative: HUD, same stats, one-click import. Mac + Windows."**
1. **Reddit r/poker**: GIF of importing an H2N database -> General screen -> HUD at a table
2. **Reddit r/pokerstars**, **TwoPlusTwo**: HUD + "your numbers match Hand2Note"
3. **GitHub release v0.2.0** with release notes

---

## Phase 2: Feedback sprint + Open Data

| Item | Effort |
|---|---|
| Fix the top bugs from launch users (priority #1), HUD reliability per site | ongoing |
| **API documentation**: describe all endpoints, link `/docs` ([docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 1) | S |
| **Export**: `GET /api/export/hands|stats?format=json|csv`, read-only `POST /api/query/sql` | S |
| **Import your custom stats from Hand2Note** (the user's own stat files -> OHM stat definitions) | M |
| **Saved filters / views** | M |

Marketing: changelog posts to the 2+2 thread; "Only tracker with a public API and SQL".

---

## Phase 3: NL Query Engine + Events

| Item | Effort |
|---|---|
| **NL query engine** ("PostHog for poker"): plain English -> SQL + results, BYOK. The Phase 0 line-filter builder is already the visual half. See [docs/specs/QUERY-ENGINE-PRD.md](docs/specs/QUERY-ENGINE-PRD.md), [docs/vision/PRODUCT-VISION.md](docs/vision/PRODUCT-VISION.md) | L |
| **Event bus** (`hand_imported`, `import_completed`, `session_ended`) + `WS /api/ws/events` (the HUD already needs a live channel) | M |
| Webhooks + auto study tagger ([docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 2) | M |

Marketing: **Hacker News** "Show HN: open-source poker tracker -- Hand2Note-compatible stats, HUD, ask
your database anything"; a short YouTube demo.

---

## Phase 4: Plugins + Stat Packs + Sharing

| Item | Effort |
|---|---|
| **Parser plugin interface** + template repo + "add your site in a weekend" guide ([docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 3) | L |
| **Custom stat packs**: stat definitions as data on the same matcher; show up in HUD, reports and queries | M |
| **Hand sharing** (link/image from the replayer): the viral loop | M |
| Population stats polish, performance for 1M+ hand databases | L |

Marketing: "Build a parser" CTA, stat pack sharing on 2+2, poker Discords.

---

## Phase 5: Streamers + AI as interface

| Item | Effort |
|---|---|
| **OBS overlay** (`/overlay/session` as a browser source, live via WebSocket) + streamer outreach | M |
| **AI as an interface** only: session summaries and leak lists computed from real stats and benchmarks. No "AI coach" claims without population data or a solver baseline ([docs/vision/MONETIZATION.md](docs/vision/MONETIZATION.md)) | M |
| Tilt detector (rolling stats vs baseline, desktop notification) | S |
| Product Hunt launch | S |

---

## Phase 6: Money + Scale

Follow [docs/vision/MONETIZATION.md](docs/vision/MONETIZATION.md): the realistic path is **B2B for
stables and coaches** (combined database = population sample, per-player leak views, coach exports),
validated by 5 conversations before building. Consumer freemium only with proven demand.

| Item | Effort |
|---|---|
| 5 conversations with stables / coaches (go / no-go) | S |
| Stable workspace: several players' databases, per-player leaks, pool analysis, coach exports | XL |
| Localization (Russian first: the GG CIS market) | M |
| Plugin registry / marketplace, if the plugin ecosystem took off | L |
| GitHub Sponsors / Open Collective | S |

---

## Phase order

```
0. MUST-HAVES        v0.1.0, auto-import, PT4/HM3 import,     -> soft launch to GG players
                     line filters, range grid, opponent          (2+2, r/GGPoker, RU community)
                     selector, smart reports
1. HUD (XL)          real-time pipeline, table detection,     -> big launch (r/poker, r/pokerstars, 2+2)
                     overlay (Win, then Mac), HUD stats =
                     General stats, popups, notes, editor
2. FEEDBACK + DATA   bugs, API docs, export, SQL, H2N stats   -> "public API + SQL" post
3. NL QUERY + EVENTS query engine, event bus, webhooks        -> Show HN, YouTube
4. PLUGINS + SHARING parser plugins, stat packs, hand sharing -> "build a parser" CTA
5. OBS + AI UI       OBS overlay, AI summaries, tilt detector -> streamers, Product Hunt
6. MONEY + SCALE     stables/coaches, localization            -> B2B pilots, RU community
```

## Feature -> Marketing Pairing

| Feature | Marketing Action | Why They're Paired |
|---------|-----------------|-------------------|
| **H2N import + parity** | **Soft launch: "same numbers, free"** | **Removes the #1 reason not to switch** |
| PT4 / HM3 import | Same post, more communities | Every tracker's users can move in a click |
| **HUD** | **Big launch on r/poker + 2+2** | **The feature players actually choose a tracker for** |
| Line filters | 2+2 study threads | Shows depth: any spot, any report |
| API + SQL + export | "Only tracker with a public API" | Platform signal for technical players |
| NL query engine | Show HN + YouTube | The "wow" demo for a broader audience |
| Parser plugins | "Build a parser" CTA | Community adds sites for you |
| Hand sharing | Discord / YouTube | Viral loop |
| OBS overlay | Streamer outreach | One yes = thousands of viewers |

## Key Rules

1. **Don't launch until install works on a clean machine.** First impressions are everything with zero budget.
2. **Parity is the launch.** "Your Hand2Note numbers, free and open source": every stat change keeps the
   parity check green (102/102).
3. **HUD comes right after the must-haves.** It's the key feature for players; nothing else jumps the queue.
4. **Respect site rules.** No HUD where a site prohibits it (GGPoker); no hand mining.
5. **Don't build features without a marketing moment**, and don't market without a feature to back it.
6. **Ship often.** Momentum matters more than perfection.
7. **Respond to every user within 24 hours.** At this scale, personal attention IS the marketing.
8. **Each new import source or HUD site = a new community to reach.**
9. **Interoperability only**: read the user's own data; no other tool's code or assets in this repo.
