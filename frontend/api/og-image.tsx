import type { VercelRequest, VercelResponse } from '@vercel/node';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { decodeHandData, type OgHandData } from './_lib/decode';
import { parseCard, formatRank, suitSymbol, suitColor } from './_lib/card-format';
import { loadFont } from './_lib/font';
import React from 'react';

function Card({ card }: { card: string | null }) {
  const parsed = card ? parseCard(card) : null;
  if (!parsed) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 52, height: 72, borderRadius: 8, backgroundColor: '#292524', border: '1px solid #44403c', color: '#78716c', fontSize: 24 }}>
        ?
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', width: 52, height: 72, borderRadius: 8, backgroundColor: suitColor(parsed.suit), color: '#fff', fontSize: 20, fontWeight: 600, gap: 0 }}>
      <span>{formatRank(parsed.rank)}</span>
      <span style={{ fontSize: 18, marginTop: -4 }}>{suitSymbol(parsed.suit)}</span>
    </div>
  );
}

function CardRow({ cards, label }: { cards: (string | null)[]; label?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      {label && <span style={{ color: '#a8a29e', fontSize: 16, width: 56 }}>{label}</span>}
      <div style={{ display: 'flex', gap: 6 }}>
        {cards.map((c, i) => <Card key={i} card={c} />)}
      </div>
    </div>
  );
}

function buildImage(hand: OgHandData) {
  const resultColor = hand.heroWonBb >= 0 ? '#22c55e' : '#ef4444';
  const resultText = `Hero ${hand.heroWonBb >= 0 ? 'wins' : 'loses'} ${Math.abs(hand.heroWonBb).toFixed(1)} BB`;

  // Show up to 3 opponents that have visible cards
  const visibleOpponents = hand.opponents
    .filter(o => o.cards[0] && o.cards[1])
    .slice(0, 3);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', width: 1200, height: 630, backgroundColor: '#1c1917', padding: '48px 56px', fontFamily: 'Inter', color: '#e7e5e4' }}>
      {/* Header: branding + stakes */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#d97706', fontSize: 24, fontWeight: 600 }}>Open Holdem Manager</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ color: '#a8a29e', fontSize: 20 }}>{hand.tableSize}-max</span>
          <span style={{ fontSize: 24, fontWeight: 600 }}>{hand.stakes}</span>
        </div>
      </div>

      {/* Hero section */}
      <div style={{ display: 'flex', flexDirection: 'column', marginTop: 40, gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 20, fontWeight: 600 }}>{hand.heroName}</span>
          <span style={{ color: '#a8a29e', fontSize: 18 }}>({hand.heroPosition})</span>
        </div>
        <CardRow cards={[hand.heroCards[0], hand.heroCards[1]]} label="Hero" />
      </div>

      {/* Board */}
      <div style={{ display: 'flex', flexDirection: 'column', marginTop: 36, gap: 12 }}>
        {hand.board.length > 0 ? (
          <CardRow cards={hand.board} label="Board" />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ color: '#a8a29e', fontSize: 16, width: 56 }}>Board</span>
            <span style={{ color: '#78716c', fontSize: 18 }}>No board</span>
          </div>
        )}
      </div>

      {/* Result */}
      <div style={{ display: 'flex', marginTop: 36 }}>
        <span style={{ fontSize: 36, fontWeight: 600, color: resultColor }}>{resultText}</span>
      </div>

      {/* Opponents with visible cards */}
      {visibleOpponents.length > 0 && (
        <div style={{ display: 'flex', marginTop: 'auto', gap: 24 }}>
          {visibleOpponents.map((opp, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#78716c', fontSize: 14 }}>{opp.name} ({opp.position})</span>
              <div style={{ display: 'flex', gap: 4 }}>
                <Card card={opp.cards[0]} />
                <Card card={opp.cards[1]} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

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

  const svg = await satori(buildImage(hand), {
    width: 1200,
    height: 630,
    fonts: [{ name: 'Inter', data: fontData, weight: 600, style: 'normal' }],
  });

  const resvg = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } });
  const png = resvg.render().asPng();

  res.setHeader('Content-Type', 'image/png');
  res.setHeader('Cache-Control', 'public, s-maxage=604800');
  res.status(200).send(Buffer.from(png));
}
