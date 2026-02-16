# OG Image Redesign: Poker Table Scene

## Summary

Replaced the flat two-column OG preview image with a poker table visualization — green felt oval with players positioned around it, board cards in the center, and hero's result shown in dollars.

## What changed

Single file: `frontend/api/og-image.ts` (Vercel serverless function).

## Before → After

**Before**: Two-column layout — hero cards on the left, board + BB result on the right. Small, bland, hard to read in messenger previews.

**After**: Poker table scene with felt oval, players around it at elliptical positions, board cards centered on felt, dollar result at the bottom. All elements sized for readability at Telegram/X.com preview scale (~400px wide).

## Architecture

### Decode pipeline

`d` query param → base64url decode → inflate (raw deflate) → JSON → `OgHandData`

Enhanced `decodeHandData()`:
- **Fold detection**: scans compact action array for `actionIndex === 0` (fold), builds `Set<playerIndex>`
- **Hero-first rotation**: sorts players by seat, finds hero, rotates array so hero is at index 0 (same logic as `useReplayerState.ts:76-82`)
- **Board kept as tuple**: `[flop[], turn[], river[]]` for gap rendering between streets
- **BB amount extracted**: `c.bb` used for dollar formatting

### Layout (1200×630, absolute positioning)

```
┌─────────────────────────────────────────────────────────┐
│  Open Holdem Manager (26px)        $0.25/$0.50 · 6-max  │  ← branding bar (52px)
│─────────────────────────────────────────────────────────│
│          [folded]           [folded]                     │
│                                                          │
│  [villain w/    ╭──────────────────────────╮  [folded]   │
│   cards]        │      green felt oval      │            │
│                 │   A  7  3    J    2       │            │  ← board 64×80 cards
│                 │                            │            │
│                 ╰──────────────────────────╯            │
│  [folded]                                    [folded]    │
│                      ┌──────────┐                        │
│                      │  A    A  │                        │  ← hero 80×100 cards
│                      │ BTN Hero │                        │
│                      └──────────┘                        │
│─────────────────────────────────────────────────────────│
│              Hero wins +$101 (40px)                       │  ← result bar (58px)
└─────────────────────────────────────────────────────────┘
```

### Seat positioning

Uses the same elliptical math as the app's replayer (`seatLayout.ts`):

```
cx=600, cy=290, rx=370, ry=175
angle = π/2 - (2π × i) / playerCount
x = cx - rx × cos(angle)
y = cy + ry × sin(angle)
```

Hero at index 0 → bottom center. Remaining seats distributed clockwise.

### Element sizes (optimized for ~3× downscale in messengers)

| Element | Size | Font |
|---------|------|------|
| Hero cards | 80×100 | 40px |
| Villain cards | 52×66 | 26px |
| Board cards | 64×80 | 32px |
| Result text | — | 40px bold |
| Branding | — | 26px bold |
| Stakes | — | 22px |
| Position labels | — | 16-20px bold |
| Usernames | — | 16-22px |

### Visual treatment

- **Hero seat**: indigo border (`#6366f1`), glow shadow, "Hero" label in indigo
- **Villain (winner)**: green border (`#22c55e`)
- **Villain (folded)**: opacity 0.3, no cards shown
- **Dealer button**: yellow "D" circle on BTN position
- **Felt**: radial gradient (`#1a3a2a` → `#0f2418`), border, inset shadow
- **Board gaps**: 6px within flop, 8px before turn/river (nearly uniform)
- **Result**: dollar amount via `wonBb × bbAmount`, green for wins, red for losses

### Money formatting

```
+$100.85  (wins < $100: 2 decimal places)
+$101     (wins ≥ $100: no decimals)
-$4.52    (losses)
```

## How it works end-to-end

1. User shares a hand from the app → `hand-codec.ts` compresses hand data into URL
2. Link pasted in Telegram/X.com → bot crawler hits `/hand?d=...`
3. Vercel rewrite (bot UA) → `/api/og` returns HTML with `og:image` pointing to `/api/og-image?d=...`
4. Bot fetches image → satori renders SVG → resvg converts to 1200×630 PNG
5. Messenger displays rich preview with poker table image

## Edge cases handled

- **No board** (preflop resolution): felt shown empty
- **Hero folded**: cards still shown (it's hero's perspective)
- **Any player count** (2-9): ellipse math adapts naturally
- **Villains without known cards**: no card row, shorter seat box
- **Heads-up**: two seats — hero bottom, villain top
- **Long usernames**: truncated to `…` + last 6 chars
