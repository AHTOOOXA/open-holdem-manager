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

interface OgPlayer {
  position: string;
  name: string;
  stackBb: number;
  cards: [string | null, string | null];
  wonBb: number;
  isHero: boolean;
  isFolded: boolean;
}

interface OgHandData {
  stakes: string;
  tableSize: number;
  players: OgPlayer[];       // hero-first rotation (hero at index 0)
  board: [string[], string[], string[]]; // [flop, turn, river]
}

function decodeHandData(encoded: string): OgHandData | null {
  try {
    const padded = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const compressed = Buffer.from(padded, 'base64');
    const json = inflateRawSync(compressed).toString('utf-8');
    const c = JSON.parse(json);
    if (c.v !== 1) return null;

    // Fold detection: actionIndex 0 = fold
    const foldedSet = new Set<number>();
    for (const a of c.a) {
      if (a[2] === 0) foldedSet.add(a[1]);
    }

    // Hero-first rotation (same logic as useReplayerState.ts:76-82)
    const indexed = c.p.map((p: (string | number | null)[], i: number) => ({ p, i }));
    indexed.sort(
      (a: { p: (string | number | null)[] }, b: { p: (string | number | null)[] }) =>
        (a.p[0] as number) - (b.p[0] as number),
    );
    const heroIdx = indexed.findIndex(
      (item: { p: (string | number | null)[] }) => item.p[7] === 1,
    );
    if (heroIdx === -1) return null;
    const rotated = [...indexed.slice(heroIdx), ...indexed.slice(0, heroIdx)];

    const players: OgPlayer[] = rotated.map(
      (item: { p: (string | number | null)[]; i: number }) => ({
        position: POSITIONS[item.p[1] as number] ?? 'EP',
        name: item.p[2] as string,
        stackBb: item.p[3] as number,
        cards: [item.p[4] as string | null, item.p[5] as string | null],
        wonBb: item.p[6] as number,
        isHero: item.p[7] === 1,
        isFolded: foldedSet.has(item.i),
      }),
    );

    const board: [string[], string[], string[]] = [
      c.b[0] ?? [],
      c.b[1] ?? [],
      c.b[2] ?? [],
    ];

    return { stakes: c.s, tableSize: c.ts, players, board };
  } catch {
    return null;
  }
}

// ── Card rendering ──────────────────────────────────────────────────

const SUIT_BG: Record<string, string> = {
  s: '#57534e', h: '#dc2626', d: '#2563eb', c: '#16a34a',
};
const RANK_DISPLAY: Record<string, string> = { T: '10' };

function cardBox(card: string | null, w: number, ht: number, fs: number, r: number): SatoriNode {
  if (!card || card.length < 2) {
    return h('div', {
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      width: w, height: ht, borderRadius: r,
      backgroundColor: '#292524', border: '2px solid #44403c',
      color: '#78716c', fontSize: fs, fontWeight: 600,
    }, '?');
  }
  const rank = RANK_DISPLAY[card[0]] ?? card[0];
  const bg = SUIT_BG[card[1]] ?? '#57534e';
  return h('div', {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    width: w, height: ht, borderRadius: r,
    backgroundColor: bg, color: '#fff', fontSize: fs, fontWeight: 600,
  }, rank);
}

// ── Font ────────────────────────────────────────────────────────────

let fontCache: ArrayBuffer | null = null;

async function loadFont(): Promise<ArrayBuffer> {
  if (fontCache) return fontCache;
  const res = await fetch('https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf');
  fontCache = await res.arrayBuffer();
  return fontCache;
}

// ── Seat positions (elliptical, hero at bottom) ─────────────────────

function getSeatPositions(count: number): { x: number; y: number }[] {
  const cx = 600, cy = 305, rx = 380, ry = 185;
  const seats: { x: number; y: number }[] = [];
  for (let i = 0; i < count; i++) {
    const angle = Math.PI / 2 - (2 * Math.PI * i) / count;
    seats.push({
      x: Math.round(cx - rx * Math.cos(angle)),
      y: Math.round(cy + ry * Math.sin(angle)),
    });
  }
  return seats;
}

// ── Board cards ─────────────────────────────────────────────────────

function renderBoard(board: [string[], string[], string[]]): SatoriNode | false {
  const [flop, turn, river] = board;
  if (flop.length === 0 && turn.length === 0 && river.length === 0) return false;

  const CW = 44, CH = 56, GAP = 5, STREET_GAP = 12;

  const items: { card: string; ml: number }[] = [];
  flop.forEach((c, i) => items.push({ card: c, ml: i > 0 ? GAP : 0 }));
  if (turn.length > 0) items.push({ card: turn[0], ml: items.length > 0 ? STREET_GAP : 0 });
  if (river.length > 0) items.push({ card: river[0], ml: items.length > 0 ? STREET_GAP : 0 });

  const totalW = items.length * CW + items.reduce((s, it) => s + it.ml, 0);

  return h('div', {
    position: 'absolute', display: 'flex',
    left: 600 - totalW / 2, top: 290 - CH / 2,
  },
    ...items.map(it =>
      h('div', { display: 'flex', marginLeft: it.ml },
        cardBox(it.card, CW, CH, 22, 5))));
}

// ── Player seat ─────────────────────────────────────────────────────

function truncName(name: string, isHero: boolean): string {
  if (isHero) return 'Hero';
  return name.length > 8 ? `…${name.slice(-6)}` : name;
}

function renderSeat(player: OgPlayer, pos: { x: number; y: number }, idx: number): SatoriNode {
  const isHero = idx === 0;
  const showCards = !!(player.cards[0] && player.cards[1]);

  // Card dimensions
  const cw = isHero ? 48 : 36;
  const ch = isHero ? 60 : 44;
  const cGap = isHero ? 5 : 3;
  const cFs = isHero ? 24 : 18;
  const cR = isHero ? 6 : 4;

  // Wrapper size for centering on the ellipse point
  const wrapW = isHero ? 160 : 120;
  const wrapH = isHero ? 140 : (showCards ? 110 : 65);

  // Visual styles
  const isWinner = player.wonBb > 0 && !isHero;
  const border = isHero
    ? '2px solid #6366f1'
    : isWinner ? '2px solid #22c55e' : '1px solid #44403c';
  const shadow = isHero ? '0 0 12px rgba(99,102,241,0.3)' : undefined;
  const opacity = !isHero && player.isFolded ? 0.35 : 1;
  const br = isHero ? 10 : 8;

  const nameStr = truncName(player.name, isHero);
  const nameColor = isHero ? '#6366f1' : '#a8a29e';
  const nameFs = isHero ? 14 : 11;
  const posFs = isHero ? 13 : 11;
  const isBtn = player.position === 'BTN';

  return h('div', {
    position: 'absolute', display: 'flex',
    justifyContent: 'center', alignItems: 'center',
    left: pos.x - wrapW / 2, top: pos.y - wrapH / 2,
    width: wrapW, height: wrapH,
  },
    h('div', {
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '8px 12px', backgroundColor: '#292524',
      border, borderRadius: br,
      ...(shadow ? { boxShadow: shadow } : {}),
      opacity, gap: 4,
    },
      // Cards row
      showCards && h('div', { display: 'flex', gap: cGap },
        cardBox(player.cards[0], cw, ch, cFs, cR),
        cardBox(player.cards[1], cw, ch, cFs, cR)),

      // Position label + dealer button
      h('div', { display: 'flex', alignItems: 'center', gap: 4 },
        h('span', { fontSize: posFs, fontWeight: 600, color: '#a8a29e' }, player.position),
        isBtn && h('div', {
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 18, height: 18, borderRadius: '50%',
          backgroundColor: '#eab308', color: '#1c1917',
          fontSize: 10, fontWeight: 700,
        }, 'D')),

      // Username
      h('span', { fontSize: nameFs, color: nameColor }, nameStr)));
}

// ── Image builder ───────────────────────────────────────────────────

function buildImage(hand: OgHandData): SatoriNode {
  const hero = hand.players[0];
  const isWin = hero.wonBb >= 0;
  const resultColor = isWin ? '#22c55e' : '#ef4444';
  const sign = isWin ? '+' : '';
  const resultText = `Hero ${isWin ? 'wins' : 'loses'} ${sign}${hero.wonBb.toFixed(1)} BB`;

  const seats = getSeatPositions(hand.players.length);

  return h('div', {
    position: 'relative', display: 'flex',
    width: 1200, height: 630,
    backgroundColor: '#1c1917', fontFamily: 'Inter', color: '#e7e5e4',
  },

    // Felt oval
    h('div', {
      position: 'absolute', display: 'flex',
      left: 260, top: 130, width: 680, height: 340,
      borderRadius: '50%',
      backgroundImage: 'radial-gradient(ellipse at 50% 40%, #1a3a2a, #0f2418)',
      border: '3px solid #2a4a38',
      boxShadow: 'inset 0 0 40px rgba(10,30,18,0.6), 0 4px 20px rgba(0,0,0,0.5)',
    }),

    // Board cards
    renderBoard(hand.board),

    // Player seats
    ...hand.players.map((p, i) => renderSeat(p, seats[i], i)),

    // Branding bar (top)
    h('div', {
      position: 'absolute', display: 'flex',
      left: 0, top: 0, width: 1200, height: 44,
      paddingLeft: 32, paddingRight: 32,
      justifyContent: 'space-between', alignItems: 'center',
    },
      h('span', { fontSize: 18, fontWeight: 600, color: '#d97706' }, 'Open Holdem Manager'),
      h('span', { fontSize: 16, color: '#78716c' }, `${hand.stakes} · ${hand.tableSize}-max`)),

    // Result bar (bottom)
    h('div', {
      position: 'absolute', display: 'flex',
      left: 0, top: 586, width: 1200, height: 44,
      justifyContent: 'center', alignItems: 'center',
      borderTop: '1px solid #292524',
    },
      h('span', { fontSize: 24, fontWeight: 600, color: resultColor }, resultText)));
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
