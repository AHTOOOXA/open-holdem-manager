import type { VercelRequest, VercelResponse } from '@vercel/node';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { inflateRawSync } from 'node:zlib';

// ── Satori element helper (replaces JSX) ────────────────────────────

type SatoriNode = string | number | { type: string; props: Record<string, unknown> };

function h(type: string, style: Record<string, unknown>, ...children: (SatoriNode | SatoriNode[] | false | null | undefined)[]): SatoriNode {
  const flat = children.flat().filter((c): c is SatoriNode => c !== false && c !== null && c !== undefined);
  return { type, props: { style, children: flat.length === 1 ? flat[0] : flat } };
}

// ── Decode ──────────────────────────────────────────────────────────

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

interface OgHandData {
  stakes: string;
  tableSize: number;
  heroName: string;
  heroPosition: string;
  heroCards: [string | null, string | null];
  heroWonBb: number;
  board: string[];
  opponents: { name: string; position: string; cards: [string | null, string | null] }[];
}

function decodeHandData(encoded: string): OgHandData | null {
  try {
    const padded = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const compressed = Buffer.from(padded, 'base64');
    const json = inflateRawSync(compressed).toString('utf-8');
    const c = JSON.parse(json);
    if (c.v !== 1) return null;

    const heroIdx = c.p.findIndex((p: number[]) => p[7] === 1);
    if (heroIdx === -1) return null;
    const hero = c.p[heroIdx];

    const opponents = c.p
      .filter((_: unknown, i: number) => i !== heroIdx)
      .map((p: (string | number | null)[]) => ({
        name: p[2] as string,
        position: POSITIONS[p[1] as number] ?? 'EP',
        cards: [p[4], p[5]] as [string | null, string | null],
      }));

    return {
      stakes: c.s,
      tableSize: c.ts,
      heroName: hero[2],
      heroPosition: POSITIONS[hero[1]] ?? 'EP',
      heroCards: [hero[4], hero[5]],
      heroWonBb: hero[6],
      board: [...(c.b[0] ?? []), ...(c.b[1] ?? []), ...(c.b[2] ?? [])],
      opponents,
    };
  } catch {
    return null;
  }
}

// ── Card rendering (H2N-style boxes matching CardBox in the app) ────

// Spades lightened for dark bg visibility (app uses oklch 0.268)
const SUIT_COLORS: Record<string, string> = { s: '#57534e', h: '#dc2626', d: '#2563eb', c: '#16a34a' };
const RANK_DISPLAY: Record<string, string> = { T: '10' };

function cardBox(card: string | null, size: 'lg' | 'sm' = 'lg'): SatoriNode {
  const w = size === 'lg' ? 64 : 48;
  const ht = size === 'lg' ? 80 : 60;
  const fs = size === 'lg' ? 32 : 22;
  const r = size === 'lg' ? 8 : 6;

  if (!card || card.length < 2) {
    return h('div', { display: 'flex', alignItems: 'center', justifyContent: 'center', width: w, height: ht, borderRadius: r, backgroundColor: '#292524', border: '2px solid #44403c', color: '#78716c', fontSize: fs, fontWeight: 600 },
      '?');
  }
  const rank = RANK_DISPLAY[card[0]] ?? card[0];
  const suit = card[1];
  const bg = SUIT_COLORS[suit] ?? '#57534e';
  return h('div', { display: 'flex', alignItems: 'center', justifyContent: 'center', width: w, height: ht, borderRadius: r, backgroundColor: bg, color: '#fff', fontSize: fs, fontWeight: 600 },
    rank);
}

// ── Font ────────────────────────────────────────────────────────────

let fontCache: ArrayBuffer | null = null;

async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) return fontCache;
  const res = await fetch('https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf');
  fontCache = await res.arrayBuffer();
  return fontCache;
}

// ── Image builder ───────────────────────────────────────────────────

function buildImage(hand: OgHandData): SatoriNode {
  const isWin = hand.heroWonBb >= 0;
  const resultColor = isWin ? '#22c55e' : '#ef4444';
  const resultText = `${isWin ? '+' : ''}${hand.heroWonBb.toFixed(1)} BB`;

  const visibleOpponents = hand.opponents
    .filter(o => o.cards[0] && o.cards[1])
    .slice(0, 3);

  return h('div', { display: 'flex', flexDirection: 'column', width: 1200, height: 630, backgroundColor: '#1c1917', padding: '44px 56px', fontFamily: 'Inter', color: '#e7e5e4' },

    // ── Top bar: branding left, stakes right ──
    h('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
      h('span', { color: '#d97706', fontSize: 22, fontWeight: 600 }, 'Open Holdem Manager'),
      h('div', { display: 'flex', alignItems: 'center', gap: 12 },
        h('span', { color: '#78716c', fontSize: 18 }, `${hand.tableSize}-max`),
        h('span', { fontSize: 22, fontWeight: 600 }, hand.stakes))),

    // ── Divider ──
    h('div', { display: 'flex', width: '100%', height: 1, backgroundColor: '#292524', marginTop: 20, marginBottom: 28 }),

    // ── Main content: hero cards + board + result ──
    h('div', { display: 'flex', flex: 1, gap: 48 },

      // Left column: hero cards (big)
      h('div', { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 },
        h('div', { display: 'flex', gap: 8 },
          cardBox(hand.heroCards[0], 'lg'),
          cardBox(hand.heroCards[1], 'lg')),
        h('span', { fontSize: 16, color: '#a8a29e' }, `${hand.heroName} (${hand.heroPosition})`)),

      // Right column: board + result + opponents
      h('div', { display: 'flex', flexDirection: 'column', flex: 1, gap: 20 },

        // Board
        hand.board.length > 0
          ? h('div', { display: 'flex', flexDirection: 'column', gap: 8 },
              h('span', { fontSize: 14, color: '#78716c', textTransform: 'uppercase' as const, letterSpacing: 1 }, 'Board'),
              h('div', { display: 'flex', gap: 6 },
                ...hand.board.map(c => cardBox(c, 'sm'))))
          : h('div', { display: 'flex' },
              h('span', { fontSize: 14, color: '#78716c' }, 'No board')),

        // Result
        h('div', { display: 'flex', alignItems: 'baseline', gap: 12 },
          h('span', { fontSize: 48, fontWeight: 600, color: resultColor }, resultText),
          h('span', { fontSize: 20, color: '#a8a29e' }, isWin ? 'won' : 'lost')),

        // Opponents (at bottom of right column)
        visibleOpponents.length > 0
          ? h('div', { display: 'flex', marginTop: 'auto', gap: 20 },
              ...visibleOpponents.map(opp =>
                h('div', { display: 'flex', alignItems: 'center', gap: 8 },
                  h('span', { color: '#78716c', fontSize: 13 }, `${opp.name} (${opp.position})`),
                  h('div', { display: 'flex', gap: 3 },
                    cardBox(opp.cards[0], 'sm'),
                    cardBox(opp.cards[1], 'sm')))))
          : null)),

    // ── Bottom bar ──
    h('div', { display: 'flex', width: '100%', height: 1, backgroundColor: '#292524', marginTop: 20 }));
}

// ── Handler ─────────────────────────────────────────────────────────

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const d = req.query.d as string | undefined;
  if (!d) {
    res.status(400).json({ error: 'Missing d parameter' });
    return;
  }

  const hand = decodeHandData(d);
  if (!hand) {
    res.status(400).json({ error: 'Invalid hand data' });
    return;
  }

  const fontData = await loadFont();

  const svg = await satori(buildImage(hand) as React.ReactNode, {
    width: 1200,
    height: 630,
    fonts: [{ name: 'Inter', data: fontData, weight: 600, style: 'normal' as const }],
  });

  const resvg = new Resvg(svg, { fitTo: { mode: 'width' as const, value: 1200 } });
  const png = resvg.render().asPng();

  res.setHeader('Content-Type', 'image/png');
  res.setHeader('Cache-Control', 'public, s-maxage=604800');
  res.status(200).send(Buffer.from(png));
}
