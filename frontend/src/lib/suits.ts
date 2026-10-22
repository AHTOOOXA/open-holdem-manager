/** Four-colour deck: tile background classes (tokens in src/index.css) and suit symbols. */
export const SUIT_BG: Record<string, string> = {
  s: 'bg-suit-s',
  h: 'bg-suit-h',
  d: 'bg-suit-d',
  c: 'bg-suit-c',
};

export const SUIT_BG_FALLBACK = 'bg-muted';

export const SUIT_SYMBOL: Record<string, string> = {
  s: '♠',
  h: '♥',
  d: '♦',
  c: '♣',
};
