// Suit colors matching the app (CardDisplay.tsx:52-55)
// Spades uses oklch in the app — converted to hex for satori compatibility
const SUIT_COLORS: Record<string, string> = {
  s: '#3f3b36',
  h: '#dc2626',
  d: '#2563eb',
  c: '#16a34a',
};

const SUIT_SYMBOLS: Record<string, string> = {
  s: '\u2660',
  h: '\u2665',
  d: '\u2666',
  c: '\u2663',
};

const RANK_DISPLAY: Record<string, string> = {
  T: '10',
};

export function suitColor(suit: string): string {
  return SUIT_COLORS[suit] ?? '#3f3b36';
}

export function suitSymbol(suit: string): string {
  return SUIT_SYMBOLS[suit] ?? '';
}

export function formatRank(rank: string): string {
  return RANK_DISPLAY[rank] ?? rank;
}

export function parseCard(card: string): { rank: string; suit: string } | null {
  if (!card || card.length < 2) return null;
  return { rank: card[0], suit: card[1] };
}
