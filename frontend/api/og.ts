import type { VercelRequest, VercelResponse } from '@vercel/node';
import { inflateRawSync } from 'node:zlib';

// ── Decode ──────────────────────────────────────────────────────────

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;

interface OgHandData {
  stakes: string;
  bbAmount: number;
  tableSize: number;
  heroPosition: string;
  heroCards: [string | null, string | null];
  heroWonBb: number;
  board: string[];
}

function decodeHandData(encoded: string): OgHandData | null {
  try {
    const padded = encoded.replace(/-/g, '+').replace(/_/g, '/');
    const compressed = Buffer.from(padded, 'base64');
    const json = inflateRawSync(compressed).toString('utf-8');
    const c = JSON.parse(json);
    if (c.v !== 1) return null;

    const hero = c.p.find((p: number[]) => p[7] === 1);
    if (!hero) return null;

    return {
      stakes: c.s,
      bbAmount: c.bb,
      tableSize: c.ts,
      heroPosition: POSITIONS[hero[1]] ?? 'EP',
      heroCards: [hero[4], hero[5]],
      heroWonBb: hero[6],
      board: [...(c.b[0] ?? []), ...(c.b[1] ?? []), ...(c.b[2] ?? [])],
    };
  } catch {
    return null;
  }
}

// ── Card formatting ─────────────────────────────────────────────────

const SUIT_SYMBOLS: Record<string, string> = { s: '\u2660', h: '\u2665', d: '\u2666', c: '\u2663' };
const RANK_DISPLAY: Record<string, string> = { T: '10' };

function formatCardText(card: string | null): string {
  if (!card || card.length < 2) return '?';
  const rank = RANK_DISPLAY[card[0]] ?? card[0];
  const suit = SUIT_SYMBOLS[card[1]] ?? '';
  return `${rank}${suit}`;
}

// ── HTML helpers ────────────────────────────────────────────────────

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// ── Handler ─────────────────────────────────────────────────────────

export default function handler(req: VercelRequest, res: VercelResponse) {
  const d = req.query.d as string | undefined;

  let title = 'Open Holdem Manager — Free Poker Tracker';
  let description = 'Free, open-source, local poker hand history tracker.';
  let imageUrl = '';

  if (d) {
    const hand = decodeHandData(d);
    if (hand) {
      const card1 = formatCardText(hand.heroCards[0]);
      const card2 = formatCardText(hand.heroCards[1]);
      const resultSign = hand.heroWonBb >= 0 ? '+' : '';
      const resultBb = `${resultSign}${hand.heroWonBb.toFixed(1)} BB`;

      title = `${hand.stakes} | ${card1} ${card2} | Hero ${hand.heroWonBb >= 0 ? 'wins' : 'loses'} ${Math.abs(hand.heroWonBb).toFixed(1)} BB`;
      const boardStr = hand.board.length > 0
        ? hand.board.map(c => formatCardText(c)).join(' ')
        : 'No board';
      description = `${hand.tableSize}-max poker hand — Hero (${hand.heroPosition}) ${resultBb} — Board: ${boardStr}`;

      const origin = `https://${req.headers.host || 'ohm.antonchaynik.ru'}`;
      imageUrl = `${origin}/api/og-image?d=${encodeURIComponent(d)}`;
    }
  }

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta property="og:title" content="${escapeHtml(title)}" />
  <meta property="og:description" content="${escapeHtml(description)}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Open Holdem Manager" />
  ${imageUrl ? `<meta property="og:image" content="${escapeHtml(imageUrl)}" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />` : ''}
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${escapeHtml(title)}" />
  <meta name="twitter:description" content="${escapeHtml(description)}" />
  ${imageUrl ? `<meta name="twitter:image" content="${escapeHtml(imageUrl)}" />` : ''}
</head>
<body></body>
</html>`;

  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'public, s-maxage=86400');
  res.status(200).send(html);
}
