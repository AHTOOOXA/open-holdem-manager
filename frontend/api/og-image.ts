import type { VercelRequest, VercelResponse } from '@vercel/node';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { inflateRawSync } from 'node:zlib';

// ── Satori element helper (replaces JSX) ────────────────────────────

type SatoriNode = string | { type: string; props: Record<string, unknown> };

function h(type: string, style: Record<string, unknown>, ...children: (SatoriNode | SatoriNode[] | false | null | undefined)[]): SatoriNode {
  const flat = children.flat().filter((c): c is SatoriNode => c !== false && c !== null && c !== undefined);
  return { type, props: { style, children: flat.length === 1 ? flat[0] : flat } };
}

function text(s: string): SatoriNode {
  return s;
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

// ── Card formatting ─────────────────────────────────────────────────

const SUIT_COLORS: Record<string, string> = { s: '#3f3b36', h: '#dc2626', d: '#2563eb', c: '#16a34a' };
const SUIT_SYMBOLS: Record<string, string> = { s: '\u2660', h: '\u2665', d: '\u2666', c: '\u2663' };
const RANK_DISPLAY: Record<string, string> = { T: '10' };

function suitColor(suit: string): string { return SUIT_COLORS[suit] ?? '#3f3b36'; }

function cardElement(card: string | null): SatoriNode {
  if (!card || card.length < 2) {
    return h('div', { display: 'flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 72, borderRadius: 8, backgroundColor: '#292524', border: '1px solid #44403c', color: '#78716c', fontSize: 24 },
      text('?'));
  }
  const rank = RANK_DISPLAY[card[0]] ?? card[0];
  const suit = card[1];
  return h('div', { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: 52, height: 72, borderRadius: 8, backgroundColor: suitColor(suit), color: '#fff', fontSize: 20, fontWeight: 600 },
    h('span', {}, text(rank)),
    h('span', { fontSize: 18, marginTop: -4 }, text(SUIT_SYMBOLS[suit] ?? '')));
}

function cardRow(cards: (string | null)[], label?: string): SatoriNode {
  return h('div', { display: 'flex', alignItems: 'center', gap: 12 },
    label ? h('span', { color: '#a8a29e', fontSize: 16, width: 56 }, text(label)) : null,
    h('div', { display: 'flex', gap: 6 }, ...cards.map(c => cardElement(c))));
}

// ── Font ────────────────────────────────────────────────────────────

let fontCache: ArrayBuffer | null = null;

async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) return fontCache;
  const res = await fetch('https://fonts.gstatic.com/s/inter/v18/UcCo3FwrK3iLTcviYwY.ttf');
  fontCache = await res.arrayBuffer();
  return fontCache;
}

// ── Image builder ───────────────────────────────────────────────────

function buildImage(hand: OgHandData): SatoriNode {
  const resultColor = hand.heroWonBb >= 0 ? '#22c55e' : '#ef4444';
  const resultText = `Hero ${hand.heroWonBb >= 0 ? 'wins' : 'loses'} ${Math.abs(hand.heroWonBb).toFixed(1)} BB`;

  const visibleOpponents = hand.opponents
    .filter(o => o.cards[0] && o.cards[1])
    .slice(0, 3);

  return h('div', { display: 'flex', flexDirection: 'column', width: 1200, height: 630, backgroundColor: '#1c1917', padding: '48px 56px', fontFamily: 'Inter', color: '#e7e5e4' },
    // Header
    h('div', { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
      h('div', { display: 'flex', alignItems: 'center', gap: 16 },
        h('span', { color: '#d97706', fontSize: 24, fontWeight: 600 }, text('Open Holdem Manager'))),
      h('div', { display: 'flex', alignItems: 'center', gap: 16 },
        h('span', { color: '#a8a29e', fontSize: 20 }, text(`${hand.tableSize}-max`)),
        h('span', { fontSize: 24, fontWeight: 600 }, text(hand.stakes)))),
    // Hero
    h('div', { display: 'flex', flexDirection: 'column', marginTop: 40, gap: 16 },
      h('div', { display: 'flex', alignItems: 'center', gap: 12 },
        h('span', { fontSize: 20, fontWeight: 600 }, text(hand.heroName)),
        h('span', { color: '#a8a29e', fontSize: 18 }, text(`(${hand.heroPosition})`))),
      cardRow([hand.heroCards[0], hand.heroCards[1]], 'Hero')),
    // Board
    h('div', { display: 'flex', flexDirection: 'column', marginTop: 36, gap: 12 },
      hand.board.length > 0
        ? cardRow(hand.board, 'Board')
        : h('div', { display: 'flex', alignItems: 'center', gap: 12 },
            h('span', { color: '#a8a29e', fontSize: 16, width: 56 }, text('Board')),
            h('span', { color: '#78716c', fontSize: 18 }, text('No board')))),
    // Result
    h('div', { display: 'flex', marginTop: 36 },
      h('span', { fontSize: 36, fontWeight: 600, color: resultColor }, text(resultText))),
    // Opponents
    visibleOpponents.length > 0
      ? h('div', { display: 'flex', marginTop: 'auto', gap: 24 },
          ...visibleOpponents.map(opp =>
            h('div', { display: 'flex', alignItems: 'center', gap: 8 },
              h('span', { color: '#78716c', fontSize: 14 }, text(`${opp.name} (${opp.position})`)),
              h('div', { display: 'flex', gap: 4 },
                cardElement(opp.cards[0]),
                cardElement(opp.cards[1])))))
      : null);
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
