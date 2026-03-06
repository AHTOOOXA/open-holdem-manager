# Open Holdem Manager -- Product Strategy & Market Analysis

*March 2026*

---

## Table of Contents

1. [Current State Assessment](#1-current-state-assessment)
2. [Market Research](#2-market-research)
3. [Competitive Analysis](#3-competitive-analysis)
4. [Opportunity Analysis](#4-opportunity-analysis)
5. [Verdict & Recommendations](#5-verdict--recommendations)

---

## 1. Current State Assessment

### What's Built (v0.0.10 alpha)

| Area | Status | Details |
|------|--------|---------|
| Parser | Working | GGPoker Rush & Cash. Handles RIT, all-in EV, rake, null bytes, split pots |
| Stat Engine | Working | 60+ H2N-style flags (VPIP, PFR, 3bet, cbet, steal, etc.) with positional breakdowns |
| Import Pipeline | Working | Parse -> Compute -> Insert, batched 200/batch, NDJSON streaming progress, dedup |
| Stats Page | Polished | Full positional breakdowns, filters (stakes/date/last N hands), drift detection |
| Graph Page | Polished | Cumulative BB/USD curves, EV line, session detection, variance stats (SD/skew/kurtosis) |
| Hands Browser | Working | Paginated, sortable, filterable, hand detail drawer with replayer, tagging & notes |
| Range Page | Working | Preflop heatmaps per position with combo breakdown (frequency, win rate, EV) |
| Sessions Page | Working | Time-based session clustering with P/L curves |
| Population Page | Partial | Aggregate opponent stats, preflop matrices, sizing distributions -- board texture incomplete |
| Compare Page | Working | 3 modes: Periods, vs Population, vs Workspace |
| Players Page | Working | Opponent list with stats, classification (NIT/TAG/LAG/REC/MAN), identities |
| Workspaces | Working | Multi-account support, hero config per workspace, data scoping |
| Checkpoints | Working | Save stat snapshots for A/B comparison |
| Electron Desktop | Working | Auto-updates via GitHub Releases, free port detection, static serving |
| Landing Page | Working | Static site with mock data and live demo feel |

~20,000 lines of code across 31 Python backend files and 12 React frontend pages.

### Tech Stack

- **Backend**: Python 3.12, FastAPI, DuckDB (file-based, zero-config)
- **Frontend**: React 19, TypeScript 5.9, Vite 7, TailwindCSS v4, shadcn/ui
- **Desktop**: Electron 33 with auto-updates
- **No auth, no cloud, no external dependencies** -- fully local, single-user

### What's Missing

- No HUD (no real-time overlay while playing)
- Only GGPoker (no PokerStars, 888, WPN, etc.)
- RIT/Cashout architecture has tech debt (query-time parsing instead of parser-level)
- No AI/solver integration
- Population stats incomplete (board texture precomputation missing)
- Analysis widgets recently stripped from stat detail subpages

### Architecture Quality: 7/10

**Strengths**: Clean parse->compute->insert pipeline, site-independent stat computation, DuckDB (zero-config, fast analytics), modern frontend, streaming imports, request-scoped DB cursors, migration system.

**Weaknesses**: RIT/Cashout tech debt, no materialized views for scale, limited test coverage beyond parser.

---

## 2. Market Research

### 2.1 Market Size

| Metric | Value | Source |
|--------|-------|--------|
| Global online poker players | 100M+ across 500+ platforms | Clovr 2025 |
| Market valuation (2024) | $3.9B-$8.0B | Grand View Research / MarkNtel |
| Projected (2030) | $6.9B-$37B (10-29% CAGR) | Multiple |
| Peak concurrent cash players | ~32,000 (early 2024), ~23,000 (mid-2025) | RakeRace |
| GGPoker tournament record | 600,000 concurrent (WSOP Online 2025) | PokerScout |
| Tracking software paying users | Low hundreds of thousands (est.) | No public data |

### 2.2 Platform Landscape (Mid-2025)

| Site | Position | Concurrent Players | HUD Policy | Hand History |
|------|----------|-------------------|------------|--------------|
| **GGPoker** | #1 (51-60% share) | ~10,000 | **Banned** | Download via PokerCraft, opponents anonymized |
| **WPT Global** | #2 (surpassed Stars 2024) | ~2,000 | Varies | Limited |
| **PokerStars** | #3 (halved since 2022) | ~2,000 | Allowed (tightening) | Allowed (restricting) |
| **iPoker** | Stable | ~1,500-2,000 | Allowed | Allowed |
| **PartyPoker** | Declining | Smaller | **Banned** (cash) | Allowed |

GGPoker has been #1 since January 2022. PokerStars has fallen to third behind WPT Global.

### 2.3 HUD Ban Trend

**Sites that ban HUDs**: GGPoker (strict -- running trackers while client is open risks a ban), PartyPoker (cash games), 888poker (fast-fold), Winamax, most newer/recreational-focused sites.

**Sites that allow HUDs**: PokerStars (tightening), Americas Cardroom/WPN, iPoker, CoinPoker (re-allowed Jan 2025).

**Key insight**: HUD bans don't kill tracker demand -- they reshape it. Players still need post-session leak finding, bankroll tracking, positional analysis, population tendency analysis, and hand review. A tracker without a HUD is perfectly aligned with GGPoker's ecosystem.

### 2.4 Mobile vs Desktop

- 70-85% of poker play is now mobile
- Analysis and study remain desktop activities
- Workflow: play on phone -> download hand histories -> review on desktop
- OHM serves this workflow directly

### 2.5 AI & Solver Ecosystem

| Tool | Price | Category |
|------|-------|----------|
| GTO Wizard | $89-149/mo | Browser-based pre-solved spots, AI coaching |
| PioSolver | From $249 one-time | Postflop solver (gold standard) |
| GTO+ | Cheaper one-time | Budget solver |
| MonkerSolver | $250-1,000 | PLO/multiway specialist |
| PokerGPT/PokerOS | Varies | LLM-based coaching startups |

The trend is toward AI-powered study tools, but they all depend on hand history data as the foundation. Trackers feed the study ecosystem.

### 2.6 Demand for Free Alternatives

- **FPDB-3** (Free Poker Database) is the only open-source option -- functional but dated, GTK UI, 17 GitHub stars after 15+ years of development across forks
- **Hand2Note killed its free tier** in Jan 2025, pushing price-sensitive users to look for alternatives
- Multiple "best free poker tracker" articles rank highly in search, indicating active demand
- Reddit/2+2 threads regularly ask for free/cheap alternatives
- The gap: **no modern, polished, truly free tracker exists**

---

## 3. Competitive Analysis

### 3.1 Feature Comparison Matrix

| Feature | **OHM** | **Hand2Note** | **HM3** | **PT4** | **DriveHUD** | **Poker Copilot** |
|---------|---------|--------------|---------|---------|-------------|------------------|
| **Price** | **Free** | $49-62/mo | $60-160 + $45-70/yr | $65-160 + maint | $24-75/yr | ~$99 one-time |
| **Open source** | **Yes** | No | No | No | No | No |
| **Live HUD** | No | Yes (best-in-class) | Yes | Yes | Yes | Yes |
| **GGPoker support** | **Native** | Import only | Import only | Import only | Import only | Import only |
| **Supported sites** | 1 | 50+ | 12+ | 15+ | 20+ | 8+ |
| **Stats depth** | 60+ flags | 1000+ indicators | Deep | Deep | Moderate | 60+ |
| **Hand replayer** | Basic | Advanced | Yes | Yes | Yes | Yes |
| **Graph/bankroll** | Strong | Good | Good | Good | Good | Good |
| **Population analysis** | Partial | Yes (Range Research) | Limited | Limited | Limited | No |
| **Study tools** | Drift detection | Decision Analysis | Situational Views | LeakTracker | Quiz builder | Leak detectors |
| **Windows** | Yes | Yes | Yes | Yes | Yes | Yes |
| **Mac** | **Yes** | Beta (free) | **No** | Yes | **No** | Yes |
| **Linux** | **Yes** | No | No | No | No | No |
| **Setup complexity** | **Low** (DuckDB) | Medium | Medium | High (PostgreSQL) | Low | Low |
| **UI modernity** | **2025** | 2018-era | 2015-era | 2012-era | Modern-ish | Clean but basic |

### 3.2 Pricing Landscape

| Software | Model | Entry Price | Full Price | Annual Cost (Year 2+) |
|----------|-------|-------------|------------|----------------------|
| **OHM** | **Free** | **$0** | **$0** | **$0** |
| Hand2Note 4 | Subscription | $16/mo (Learner) | $49-62/mo (Pro) | $588-750 |
| HoldemManager 3 | One-time + maintenance | $60 | $100-160 | $45-70 |
| PokerTracker 4 | One-time + maintenance | $65 | $100-160 | Similar to HM3 |
| DriveHUD 2 | Annual license | $24/yr | $75/yr | $5-10 renewal |
| Poker Copilot 8 | One-time per version | ~$50 | ~$99 | $0 |

### 3.3 Competitor Vulnerabilities

1. **PT4/HM3 merger complacency**: Max Value Software bought both in 2014. No PT5 or HM4 announced. Both products aging. HM3 has **2.3/5 on Trustpilot** (86% one-star reviews).

2. **Hand2Note pricing shock**: Killed free tier Jan 2025. $49-62/month prices out micro-stakes grinders.

3. **Windows-only lock-in**: HM3 and DriveHUD are Windows-only. Mac users have PT4 and Poker Copilot only.

4. **Database headaches**: PT4 still requires PostgreSQL. HM2's PostgreSQL nightmares are legendary. DuckDB (zero config, file-based) is a genuine advantage.

5. **No modern UI anywhere**: Every competitor's UI was designed 2010-2015. None use modern web tech.

### 3.4 Common User Complaints (from Trustpilot, Reddit, 2+2)

- **HM3**: "Full of bugs," features removed from HM2 never came back, annual maintenance for bug fixes, support ignores reports
- **PT4**: Aging interface, no PT5 on horizon, PostgreSQL setup pain
- **Hand2Note**: Steep learning curve, crashes with 6+ tables, $49-62/mo "too expensive," overwhelming for beginners
- **DriveHUD**: Inaccurate EV calculations, doesn't save all hands, rude support, no refunds
- **Cross-cutting**: Database headaches, Windows-only dominance, subscription fatigue, outdated UI/UX, complex setup

### 3.5 Open-Source Landscape

| Project | GitHub Stars | Status | Why It Hasn't Gained Traction |
|---------|-------------|--------|-------------------------------|
| FPDB-3 | 17 | Active (beta) | GTK UI from 2008, hard to install, limited stats |
| easyPokerHUD | Low | Abandoned | C#/SQLite, very basic |
| GTOHelper | Low | Unknown | Niche (solver automation) |
| Poker-Hand-Tracker | 34 | Unknown | ACR only, CLI tool |

**No modern open-source poker tracker exists.** OHM would be the first credible one.

---

## 4. Opportunity Analysis

### 4.1 Unique Positioning

OHM can differentiate on six axes no paid competitor occupies simultaneously:

1. **Free + open source** -- No cost for micro-stakes grinders where $50/mo is a large % of winrate
2. **Modern UX** -- React 19 + shadcn/ui + Tailwind. Looks like a 2025 app, not a 2012 app
3. **Zero-config setup** -- DuckDB file-based, Electron installer. No PostgreSQL, no firewall config
4. **GGPoker-native** -- Built for the #1 platform from day one (others bolt on support)
5. **True cross-platform** -- Electron gives Mac/Linux/Windows. Covers the Mac gap HM3/DriveHUD ignore
6. **Transparency** -- No data collection, no phone-home, no license server. Fully local

### 4.2 Monetization Options (Ranked)

| Rank | Model | Viability | Notes |
|------|-------|-----------|-------|
| 1 | **Freemium** (core free, premium paid) | High | Cloud sync, AI coaching, advanced analysis as paid tier. Core tracking free forever. |
| 2 | **GitHub Sponsors / Donations** | Medium | Low revenue but builds goodwill. Works combined with freemium. |
| 3 | **Enterprise / B2B** | Medium | Poker coaching platforms (RIO, Pokercoaching.com) need analytics. White-label opportunity. |
| 4 | **Cloud sync / cross-device** | Medium | Natural paid tier. Sync between desktop/laptop, cloud backup. |
| 5 | **AI study tools add-on** | Medium-High | Leak detection AI, session review, solver integration. High perceived value. $10-20/mo. |
| 6 | **Marketplace** (community plugins) | Low (now) | Needs large user base first. Long-term play. |

### 4.3 Growth Strategies

**Community-driven development:**
- Open roadmap on GitHub Discussions. Let the community vote on features.
- "Add your site's parser" as a contribution pathway -- each parser unlocks a new user base.
- The poker + code overlap is small but passionate.

**Content & community:**
- Reddit r/poker launch post (500K+ members). Free tool posts reliably get upvoted.
- TwoPlusTwo Software Forum thread. This is where serious grinders discuss tools.
- YouTube demo (3-5 min): "How to track your GGPoker results for free."
- Poker streamer partnerships: give them the tool, they show it on stream.

**Localization:**
- Russian market is huge for poker (GGPoker popular in CIS).
- Portuguese (Brazil) and Spanish (LatAm) are growing markets.

### 4.4 Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| GGPoker changes HH format | High | Parser is modular. Community can help update quickly. |
| **GGPoker removes HH downloads** | **Critical** | **Diversify to other sites ASAP. Single biggest existential risk.** |
| Maintenance burden | Medium | Clean architecture helps. Community contributors. Keep scope tight. |
| Legal | Low | Analyzing your own hand histories is legal everywhere. No scraping, no bots, no RTA. |
| Competing with funded incumbents | Medium | Don't compete on features -- compete on price (free), UX (modern), values (open source). |
| HUD expectations from users | Medium | Be clear: OHM is an analysis tool, not a HUD. Market is moving this direction anyway. |

---

## 5. Verdict & Recommendations

### Scores

| Dimension | Score | Reasoning |
|-----------|-------|-----------|
| **Market Opportunity** | **7/10** | Large poker market ($4-8B), underserved tracking niche, aging incumbents, no credible free alternative. Docked for small absolute niche size, hard free->paid conversion, GGPoker platform dependency. |
| **Technical Readiness** | **6/10** | Core loop works, 60+ stats verified, modern stack, desktop app with auto-updates. Needs 2-3 months of polish: fix RIT/Cashout, restore analysis widgets, add PokerStars parser. |

### Top 3 Things to Build Next

1. **PokerStars parser** -- Immediately doubles addressable market. Stars is the most recognized brand, every poker player has an account. The parse->compute->insert architecture was designed for this -- only a new parser is needed.

2. **Fix RIT/Cashout + restore analysis widgets** -- Leak detection and drift analysis are the "wow" features that make people share the tool. A grinder who sees their positional leaks quantified will tell their study group.

3. **Hand replayer upgrade** -- A polished visual hand replayer is the #1 feature people screenshot and share on social media. Make it shareable (generate image/link). This is the viral loop.

### Top 3 Marketing Moves

1. **Reddit r/poker launch post** -- "I built a free, open-source poker tracker." Include screenshots of graph page, stats page, hand replayer. Follow up in r/pokerstrategy, r/GGPoker.

2. **TwoPlusTwo Software Forum thread** -- Official presence where serious grinders discuss tools. Post changelogs. Let users report bugs publicly. Transparency builds trust.

3. **YouTube demo video (3-5 min)** -- "How to track your GGPoker results for free." Show import -> stats -> graph -> hand review. Post to Reddit, 2+2, and poker Discord servers.

### Realistic Timeline

| Milestone | Timeline | Assumptions |
|-----------|----------|-------------|
| **100 users** | 1-2 months post-launch | Reddit/2+2 launch, GGPoker focus, tool polished enough for daily use |
| **1,000 users** | 6-12 months | PokerStars parser added, word-of-mouth, content marketing, active community presence |
| **10,000 users** | 18-36 months | Multi-site support (5+), freemium launched, YouTube/streamer presence, localization (Russian/Portuguese) |

### Monetization Recommendation

**Phase 1 (0-1,000 users)**: 100% free. No monetization. Focus on adoption and feedback. GitHub Sponsors link for early supporters.

**Phase 2 (1,000-5,000 users)**: Introduce freemium. Free core stays free forever. Paid tier ($8-15/mo):
- Cloud sync (cross-device)
- AI session review ("here's what you did wrong tonight")
- Advanced population analysis exports
- Priority support

**Phase 3 (5,000+ users)**: Explore B2B (coaching platforms, poker schools). Marketplace for community stat packs. Lifetime purchase option.

### Honest Take

**Worth pursuing seriously, but with eyes open.**

**The case for going all-in:**
- The market gap is real. No modern, free, well-designed poker tracker exists. FPDB-3 has 17 stars after 15 years. OHM is already 10x more polished.
- GGPoker-native positioning is smart. #1 platform + HUD ban = natural fit for offline analysis.
- The tech stack is modern and well-architected. Adding new parsers is weeks, not months.
- Cross-platform via Electron is a genuine advantage over Windows-only competitors.
- Poker players pay for tools that help them win. The monetization path exists.

**The case for caution:**
- Addressable market is small in absolute terms. Maybe 200K-500K tracking software users worldwide. Free->paid conversion: expect 2-5%.
- GGPoker hand history download is a **single point of failure**. If they remove or restrict downloads further, the primary use case evaporates.
- Maintenance burden is real. Sites change formats. Each parser needs ongoing updates.
- "Free and open-source" is not a durable moat. If Hand2Note restores a free tier or PT4 drops prices, the value prop weakens.
- Solo developer vs teams (Max Value Software, Hand2Note).

**Bottom line**: This is a **strong portfolio piece that could become a real product**. The technical foundation is solid. The market gap is real but niche. The best realistic outcome: build to 1,000-5,000 users as a free tool, introduce modest freemium ($8-15/mo), generate $2K-10K/mo in recurring revenue. That's a meaningful lifestyle-business outcome.

Going "all-in" (quitting a job) would be premature until demand is validated with the first 1,000 users. But as a serious side project with product ambitions -- absolutely worth it. The market gap is real, the tech is ready, and the poker community is hungry for something better than what exists.
