# Integrated Product + Marketing Roadmap

## Context

OHM is at v0.0.10 alpha -- core features work but the product hasn't been publicly launched. The goal is to create a coordinated roadmap where every development sprint produces something marketable, and every marketing action is timed to a feature that's ready to demo. Constraints: 5-15 hrs/week, zero budget, dual goal of user adoption + portfolio credibility.

## Core Principle

**Never build silently.** Every 2-3 week sprint ends with a release that has a story to tell. Development and marketing alternate in a rhythm: build -> ship -> promote -> listen -> build.

## Strategy: Three Launch Pillars

### Pillar 1: Multi-Site Support

Each new parser unlocks a new community to announce in. Launching with 3-4 sites means a stronger launch story and larger addressable audience. **DONE** -- all 7 parsers shipped (GG, PS, 888, WPN, Winamax, iPoker, partypoker). See [docs/archive/MULTI-SITE-PARSERS-PRD.md](docs/archive/MULTI-SITE-PARSERS-PRD.md) for the completed spec.

### Pillar 2: Natural Language Query Engine ("PostHog for Poker")

No poker tool lets you ask questions in plain English. This is ~20-25 hours of work but **changes what the product is** -- from "another tracker" to "poker analytics engine." See [docs/vision/PRODUCT-VISION.md](docs/vision/PRODUCT-VISION.md) for the full concept.

### Pillar 3: Open Platform & Extensibility

No poker tracker has a public API, JSON export, webhook system, or plugin architecture. OHM already has 60+ REST endpoints -- they just aren't documented or marketed. See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) for architecture details.

The three pillars reinforce each other:
- **Multi-site** proves it's serious (breadth)
- **Query engine** proves it's different (depth)
- **Open platform** creates the community flywheel (ecosystem)

Together they make the Reddit headline: **"I built a poker analytics engine -- ask any question about your game in English. Free, open-source, supports PokerStars/GGPoker/888/WPN. Full API included."**

---

## Phase 0: Parsers + Query Engine + API + Polish (Weeks 1-5)

### Product Work -- Parsers (Weeks 1-3) -- DONE
- ~~Build PokerStars, 888poker, and WPN parsers~~ All 7 parsers shipped (GG, PS, 888, WPN, Winamax, iPoker, partypoker)
- ~~Add auto-detection in import flow (detect site from file format)~~ `detect_parser()` registry working
- ~~Test all parsers end-to-end: import -> stats -> graph -> hand replay~~ 359 tests passing
- Spec completed and archived: [docs/archive/MULTI-SITE-PARSERS-PRD.md](docs/archive/MULTI-SITE-PARSERS-PRD.md)

### Product Work -- Query Engine (Weeks 2-4)

The "PostHog for Poker" feature. ~20-25 hours total. See [docs/vision/PRODUCT-VISION.md](docs/vision/PRODUCT-VISION.md) for design details.

1. **Document the schema** -- `SCHEMA.md` with every table, column, and plain-English description (2 hours)
2. **Build the semantic layer** -- YAML mapping poker terms -> SQL patterns, all 60+ stats (4 hours)
3. **Build the query endpoint** -- `POST /api/query/ask`, Claude Haiku, read-only DuckDB, agent retry (8 hours)
4. **Build the frontend** -- Query bar, results card, suggested questions, Copy SQL / Edit & Re-run (8 hours)
5. **API key strategy**: BYOK (user provides their own key in Settings)

### Product Work -- API & Platform Foundation (Weeks 4-5)

~4 hours of work, massive differentiation. See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 1.

1. **API documentation** -- Add descriptions to all 60+ endpoint docstrings, link `/docs`
2. **Export endpoints** -- `GET /api/export/hands?format=json|csv`, `GET /api/export/stats?format=json|csv`, `POST /api/query/sql`
3. **Port discovery for Electron** -- Write port to `~/.ohm/api-port`, permissive CORS for `127.0.0.1`

### Product Work -- Polish (Weeks 3-5)
- Fix hand replayer visual polish (most screenshot-able feature)
- Restore leak detection / drift analysis widgets on stat detail pages
- Fix any RIT/Cashout bugs that affect daily use for GGPoker grinders
- Ensure Electron installer works cleanly on macOS and Windows
- Test import flow end-to-end with fresh install (first-time user experience)
- Landing page: add real screenshots, query engine demo GIF

### Marketing Prep (parallel, weeks 4-5)
- Record 2-minute screen capture GIF: import -> stats -> ask a question -> get results -> graph -> hand replay
- Take 5-6 polished screenshots
- Write draft Reddit post for r/poker (don't post yet)
- Create GitHub README with screenshots, supported sites, query engine showcase, API docs link
- Set up GitHub Discussions

### Gate: Don't proceed to Phase 1 until a fresh install on a clean machine works without friction AND at least 3 site parsers AND the query engine AND API docs are ready.

---

## Phase 1: Launch -- "Poker Analytics Engine" (Week 6)

### The Headline

**"I built a poker analytics engine -- ask any question about your game in plain English. Free, open-source, supports PokerStars/GGPoker/888/WPN. Full API included."**

### Marketing Actions
1. **Reddit r/poker** -- Lead with query engine GIF. Mention: free, open-source, no HUD, modern UI, Mac+Windows+Linux, 4 sites, full API.
2. **Reddit r/GGPoker** -- Tailored post for GGPoker features + query engine
3. **Reddit r/pokerstars** -- Tailored post for Stars players
4. **TwoPlusTwo Software Forum** -- Lead with query engine + API. "Your data, your queries. Every column documented."
5. **GitHub repo polish** -- Star-worthy README with query engine demo

### Expected Outcome
- 200-500 downloads in first week
- 30-60 active users providing feedback
- Query engine generates social sharing (people screenshot their results)
- First API consumers

### Product Work During This Week
- Monitor and fix bugs reported by first users (priority #1)
- Respond to every comment within hours
- Parser-specific bugs get hot-fixed immediately
- Monitor query accuracy -- add failing questions to semantic layer

---

## Phase 2: Feedback Sprint + Query Hardening + Events (Weeks 7-10)

### Product Work -- Core
- Fix top 3-5 bugs reported by early users
- **Query engine hardening**: Add every failed/inaccurate query to the example set
- **Saved queries / views**: Let users save and share queries
- Build the #1 most-requested feature (unknown yet -- let users decide)
- Add any quick-win parsers requested by users

### Product Work -- Event System (3-5 days)

See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 2 for architecture.

1. **Internal event bus** -- Python `asyncio` pub/sub. Events: `hand_imported`, `import_completed`, `session_ended`
2. **WebSocket endpoint** -- `WS /api/ws/events` for real-time consumers
3. **Webhook delivery** -- `POST /api/settings/webhooks` to configure URLs
4. **Auto study tagger** -- Built-in feature using event system (configurable rules)

### Marketing Actions
- **Week 7**: Changelog post to 2+2 thread
- **Week 8**: Comment in relevant Reddit threads (don't spam, only when genuine)
- **Week 8**: Share Discord bot example using webhooks. Post to poker Discord servers.
- **Week 9-10**: Blog post: "Why I built a poker analytics engine" -- the PostHog thesis, tech decisions. SEO + portfolio.

### Expected Outcome
- 300-800 total users
- First webhook/Discord integrations built by community
- Query accuracy improving with every real-world question

---

## Phase 3: Hacker News + Parser Plugins + Stat Packs (Weeks 11-14)

### Product Work -- Features
- Hand sharing (shareable link/image for replayer) -- the viral feature
- **Community query library**: Curated saved queries users can browse and run
- Population stats polish (board texture analysis)
- Performance tuning for large databases (100k+ hands)

### Product Work -- Parser Plugin Interface (1 week)

See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 3 for plugin architecture.

1. Extract shared types to `parsers/common.py`
2. Define parser interface + plugin loader for `~/.ohm/plugins/`
3. Auto-detection: suggest plugins for unrecognized files
4. Template repo: `ohm-parser-template` on GitHub
5. Contribution guide: "How to add support for your poker site in a weekend"

### Product Work -- Custom Stat Packs (3-5 days)

JSON-based stat definitions that appear alongside built-in stats and auto-register in the NL query engine. See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) for the stat pack format.

### Marketing Actions
1. **Hacker News** -- "Show HN: PostHog for poker -- ask your hand history database anything in plain English." HN loves: open-source, DuckDB, LLM-powered, extensible platforms.
2. **GitHub release** -- Proper v0.2.0 with release notes
3. **YouTube video** (3-5 min): "Ask Any Question About Your Poker Game in English"
4. **"Build a parser" CTA** -- Post in Discords and 2+2
5. **Poker Discord servers** -- Join, be helpful, mention OHM when relevant

### Expected Outcome
- 600-2,000 total users
- 50-200 GitHub stars (more if HN hits front page)
- First community parser PR
- First community stat pack shared

---

## Phase 4: AI Deep Features + SEO (Months 4-6)

### Product Work -- AI Features
- **AI session summary**: "Summarize my last session" -> narrative from queried data
- **AI leak detection**: "What are my biggest leaks?" -> compare stats to benchmarks
- **AI opponent scouting**: "Give me a scouting report on RegShark99" -> actionable game plan
- **Solver bridge** (if feasible): Compare actual play to GTO output
- Drift detection polish

### Product Work -- Tilt Detector (built-in, uses event system)
- Monitor rolling VPIP/PFR/aggression over last 20-50 hands
- Desktop notification when stats deviate from baseline
- Log tilt episodes for later review

### Product Work -- SEO
- Landing page content targeting "free poker tracker," "poker analytics engine," etc.

### Marketing Actions
1. Reddit post: "My free poker tracker now finds your leaks, scouts opponents, and detects tilt"
2. Hand sharing viral loop: shared pages have "Analyzed with OHM" branding
3. 2+2 strategy subforums: Post OHM-generated analysis examples

### Expected Outcome
- 1,500-4,000 total users
- AI features create strong portfolio differentiation
- SEO starts producing organic traffic

---

## Phase 5: Streamers + Frontend Plugins + Product Hunt (Months 7-9)

### Product Work -- OBS Overlay
- Transparent HTML page at `http://127.0.0.1:{port}/overlay/session`
- Streamers add as OBS Browser Source
- Auto-updates via WebSocket. No competitor offers this.

### Product Work -- Frontend Plugin System (1-2 weeks)

See [docs/vision/EXTENSIBILITY.md](docs/vision/EXTENSIBILITY.md) Layer 3 for architecture.

- Plugin manifest (VS Code-inspired, declarative `contributes`)
- Frontend plugin loader for `~/.ohm/plugins/`
- Plugin API: `addStatPanel()`, `addPage()`, `addSettingTab()` with auto-cleanup
- `useOHMData()` hook + opinionated component library

### Product Work -- Session Replayer
- Walk through last session hand by hand with AI annotations
- More parsers based on community demand

### Marketing Actions
1. **Poker streamer outreach** -- Lead with OBS overlay. One yes = 1000s of eyeballs.
2. **Product Hunt launch** -- "Open-source poker analytics with AI and a plugin ecosystem"
3. **Plugin showcase** -- Highlight first community plugins

### Expected Outcome
- 2,000-5,000 total users
- Streamer coverage provides outsized ROI
- 3-5 community plugins live

---

## Phase 6: Marketplace + Scale + Monetize (Months 10-12)

### Product Work -- Plugin Marketplace
- `community-plugins.json` registry in GitHub repo (Obsidian model)
- In-app browser: search, filter by type, one-click install
- `create-ohm-plugin` CLI scaffolding tool
- Submission process: PR to registry -> automated validation -> code review

### Product Work -- Freemium
- **Free tier** (forever): All pre-built stats, graphs, replayer, sharing, 50 NL queries/day, community plugins, API access
- **Pro tier** ($8-15/mo): Unlimited NL queries, AI summaries/leak detection/scouting, solver bridge, cloud sync, saved views
- Pro users: proxied LLM calls (no BYOK needed)

### Product Work -- Scale
- Localization framework (Russian first -- huge GGPoker CIS market)
- Performance optimization for 1M+ hand databases
- Plugin system polish

### Marketing Actions
1. Freemium announcement on all channels
2. Plugin marketplace launch
3. Russian poker community outreach (if localized)
4. "State of OHM" year-in-review blog post
5. GitHub Sponsors / Open Collective

### Expected Outcome
- 3,000-8,000 total users
- First paying customers (target: 50-100 at $8-15/mo = $400-1,500/mo)
- 10+ community plugins

---

## Timeline Summary

```
Month 1    [PARSERS + QUERY ENGINE + API]------[LAUNCH]
              |                                   |
              v                                   v
           PS/888/WPN parsers               Reddit r/poker
           NL query endpoint + UI           "Ask anything about your game"
           Semantic layer + schema docs     r/GGPoker, r/pokerstars
           API docs + export + SQL endpoint TwoPlusTwo, GitHub polish
           Port discovery for Electron      "Only tracker with a public API"

Month 2-3  [HARDENING + EVENTS + HN]
              |                |
              v                v
           Query accuracy   Changelog posts
           Saved views      Discord bot example
           Event bus +      Hacker News Show HN
             webhooks       YouTube "Ask your data"
           Auto-tagger      Poker Discords

Month 3-4  [PARSER PLUGINS + STAT PACKS]
              |                |
              v                v
           Parser plugin     "Build a parser" CTA
             interface       First community parser PR
           Custom stat       Stat pack sharing
             packs (JSON)    Plugin contribution guide
           Hand sharing      Viral sharing loop

Month 4-6  [AI FEATURES + SEO]
              |                |
              v                v
           AI summaries     "OHM finds your leaks" post
           Leak detection   2+2 strategy posts
           Opponent scout   Tilt detector built-in
           Solver bridge    SEO pages

Month 7-9  [STREAMERS + FRONTEND PLUGINS + PH]
              |                |
              v                v
           OBS overlay      Streamer outreach
           Frontend plugin  Product Hunt launch
             system         Plugin showcase
           Session replay   SEO compounds

Month 10-12 [MARKETPLACE + SCALE + MONETIZE]
              |                |
              v                v
           Plugin browser   Marketplace launch
           Freemium tier    Freemium announcement
           Localization     Russian community
           Performance      Year-in-review post
```

## Feature -> Marketing Pairing (Quick Reference)

| Feature | Marketing Action | Why They're Paired |
|---------|-----------------|-------------------|
| **NL query engine** | **Reddit launch headline** | **"Ask any question in English" is the 10x differentiator** |
| Multi-site support | Reddit launch across subreddits | Each parser unlocks a new community |
| **API docs + export** | **Launch post + 2+2 thread** | **"Only poker tracker with a public API"** |
| Event system + webhooks | Discord bot example post | First community integration |
| Parser plugin interface | "Build a parser" CTA on HN + Discord | Community adds sites for you |
| Saved views + queries | HN "PostHog for poker" post | HN audience gets the platform play |
| Custom stat packs | Stat pack sharing on 2+2 | Community creates content |
| Hand sharing | YouTube video + Discord | Viral loop: every shared hand = exposure |
| AI leak detection | Reddit post + 2+2 strategy forums | "Wow" factor drives sharing |
| OBS stream overlay | Streamer outreach | Overlay is the pitch hook |
| Frontend plugin system | Product Hunt | "Open platform with plugin ecosystem" |
| Plugin marketplace | Marketplace launch post | Community flywheel |
| Freemium tier | Announcement across all channels | Only after proven demand |

## Platform Evolution

```
Phase 0-1          Phase 2-3            Phase 4-5            Phase 6
OPEN DATA          OPEN EVENTS          OPEN PLUGINS         MARKETPLACE
---------          -----------          ------------         -----------
API docs           Event bus            Parser plugins       Plugin browser
Export (JSON/CSV)  Webhooks             Stat packs           Community registry
Raw SQL endpoint   WebSocket stream     Frontend panels      create-ohm-plugin CLI
Schema docs        Auto-tagger          Custom pages         Submission review
Port discovery     Discord bot example  Plugin API + hooks   Update checker

"Your data"        "Your events"        "Your extensions"    "Your ecosystem"
```

## Key Rules

1. **Don't launch until install works on a clean machine.** First impressions are everything with zero budget.
2. **The query engine IS the launch.** "Ask any question in English" is the headline. Multi-site support is the credibility proof. The API is the platform signal. Don't launch without all three.
3. **Don't build features without a marketing moment.** If you can't tell a story about it, it's not the priority.
4. **Don't market without a feature to back it.** Every post should link to something tangible.
5. **Respond to every user within 24 hours.** At this scale, personal attention IS the marketing.
6. **Ship every 2-3 weeks.** Momentum matters more than perfection.
7. **The Reddit post is the highest-stakes moment.** You get one shot at a first-impression launch post. Don't waste it on a buggy build.
8. **Each new parser = a new community to reach.** Parsers are cheap to build and each one multiplies your addressable audience.
9. **Every failed query = training data.** Track accuracy. The engine gets better with use. This is the moat.
10. **The API is the flywheel.** Every external tool built on OHM increases switching costs.
