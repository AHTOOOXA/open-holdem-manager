import type { VercelRequest, VercelResponse } from '@vercel/node';
import { decodeHandData } from './_lib/decode';
import { parseCard, formatRank, suitSymbol } from './_lib/card-format';

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatCardText(card: string | null): string {
  if (!card) return '?';
  const parsed = parseCard(card);
  if (!parsed) return '?';
  return `${formatRank(parsed.rank)}${suitSymbol(parsed.suit)}`;
}

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
